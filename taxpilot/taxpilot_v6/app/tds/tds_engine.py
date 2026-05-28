
import uuid
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.database import SessionLocal
from app.models import models
from app.tds.models.tds_models import TDSEntry, TDSVendorCumulative, TDSReturnBatch
from app.tds.tds_rate_table import (
    TDS_SECTIONS, get_tds_rate, get_section_from_category, 
    get_section_from_narration, get_threshold, VendorType
)

logger = logging.getLogger(__name__)

class TDSEngine:
    """
    TDS Computation Engine.

    Core logic:
    1. Identify TDS section from transaction category/narration
    2. Check single payment threshold
    3. Check cumulative FY threshold per vendor
    4. Compute TDS amount
    5. Check if actually deducted (from transaction data)
    6. Flag missed deductions with penalty estimate
    7. Track quarterly liability for 26Q
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.penalty_rate_per_month = 0.01  # 1% per month for late deduction

    def _get_db(self) -> Session:
        if self.db:
            return self.db
        return SessionLocal()

    def compute_tds_for_transaction(self, transaction: models.Transaction, 
                                    vendor_type: VendorType = VendorType.UNKNOWN,
                                    vendor_pan: Optional[str] = None,
                                    has_pan: bool = True) -> Optional[Dict[str, Any]]:
        """
        Compute TDS for a single transaction.

        Returns TDS entry dict or None if no TDS applicable.
        """
        # Step 1: Identify TDS section
        section = self._identify_section(transaction)
        if not section:
            return None

        # Skip salary (handled separately, not in 26Q)
        if section == "192":
            return None

        # Step 2: Get section details
        section_details = TDS_SECTIONS.get(section)
        if not section_details:
            return None

        payment_amount = transaction.amount
        payment_date = transaction.date or datetime.utcnow()
        fy = self._get_financial_year(payment_date)
        quarter = self._get_quarter(payment_date)

        # Step 3: Check single payment threshold
        if section_details.threshold_single > 0:
            if payment_amount < section_details.threshold_single:
                return None

        # Step 4: Check cumulative threshold (if db available)
        cumulative = self._get_cumulative(transaction.client_id, vendor_pan or "", section, fy)
        cumulative_total = cumulative.total_payments + payment_amount if cumulative else payment_amount

        threshold_crossed = False
        if section_details.threshold_aggregate > 0:
            if cumulative_total >= section_details.threshold_aggregate:
                threshold_crossed = True
            elif cumulative and cumulative.threshold_crossed:
                threshold_crossed = True
        else:
            threshold_crossed = True  # No aggregate threshold

        if not threshold_crossed:
            return None

        # Step 5: Compute TDS
        rate = get_tds_rate(section, vendor_type, has_pan)
        tds_amount = round(payment_amount * rate / 100, 2)

        # Step 6: Check if TDS was actually deducted
        # Heuristic: Look for "TDS" or section code in narration
        narration_lower = (transaction.narration or "").lower()
        tds_deducted = 0.0
        is_deducted = False

        # Check if transaction already has TDS component
        if "tds" in narration_lower or section.lower() in narration_lower:
            # TDS was likely deducted — estimate from narration or assume full
            tds_deducted = tds_amount  # Assume correct deduction
            is_deducted = True

        # Step 7: Check for missed deduction
        missed_deduction = False
        penalty = 0.0
        months_delayed = 0

        if not is_deducted and tds_amount > 0:
            missed_deduction = True
            # Penalty: 1% per month from payment date
            months_delayed = self._calculate_months_delayed(payment_date)
            penalty = round(tds_amount * self.penalty_rate_per_month * months_delayed, 2)

        return {
            "client_id": transaction.client_id,
            "transaction_id": transaction.id,
            "vendor_pan": vendor_pan,
            "vendor_type": vendor_type.value,
            "payment_date": payment_date,
            "payment_amount": payment_amount,
            "tds_section": section,
            "tds_rate": rate,
            "tds_amount": tds_amount,
            "tds_deducted": tds_deducted,
            "is_deducted": is_deducted,
            "missed_deduction": missed_deduction,
            "penalty_estimate": penalty,
            "months_delayed": months_delayed,
            "financial_year": fy,
            "quarter": quarter,
            "source_category": transaction.category,
            "source_narration": transaction.narration,
            "threshold_crossed": threshold_crossed,
        }

    def compute_tds_for_client(self, client_id: int, financial_year: Optional[str] = None,
                               quarter: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute TDS for all transactions of a client.

        Returns summary of computations.
        """
        db = self._get_db()

        try:
            # Get transactions for the period
            query = db.query(models.Transaction).filter(
                models.Transaction.client_id == client_id,
                models.Transaction.type == "debit",  # Only payments
                models.Transaction.is_reviewed == True  # Only reviewed transactions
            )

            if financial_year:
                # Filter by FY range (April to March)
                fy_start, fy_end = self._get_fy_date_range(financial_year)
                query = query.filter(
                    models.Transaction.date >= fy_start,
                    models.Transaction.date <= fy_end
                )

            if quarter:
                q_start, q_end = self._get_quarter_date_range(financial_year, quarter)
                query = query.filter(
                    models.Transaction.date >= q_start,
                    models.Transaction.date <= q_end
                )

            transactions = query.all()

            # Compute TDS for each
            entries = []
            for txn in transactions:
                # Try to extract vendor PAN from narration (simplified)
                vendor_pan = self._extract_pan_from_narration(txn.narration or "")

                result = self.compute_tds_for_transaction(
                    txn, 
                    vendor_type=VendorType.UNKNOWN,
                    vendor_pan=vendor_pan,
                    has_pan=bool(vendor_pan)
                )

                if result:
                    entries.append(result)

            # Store entries
            stored_count = self._store_tds_entries(db, entries)

            # Update cumulative tracking
            self._update_cumulative_tracking(db, client_id, financial_year)

            # Generate summary
            summary = self._generate_summary(entries)

            db.commit()

            return {
                "client_id": client_id,
                "financial_year": financial_year,
                "quarter": quarter,
                "transactions_processed": len(transactions),
                "tds_entries_created": stored_count,
                "summary": summary
            }

        except Exception as e:
            db.rollback()
            logger.error(f"TDS computation failed: {str(e)}")
            raise
        finally:
            if not self.db:
                db.close()

    def _identify_section(self, transaction: models.Transaction) -> Optional[str]:
        """Identify TDS section from transaction"""
        # Priority 1: Category mapping
        section = get_section_from_category(transaction.category)
        if section:
            return section

        # Priority 2: Narration keywords
        section = get_section_from_narration(transaction.narration or "")
        if section:
            return section

        return None

    def _get_cumulative(self, client_id: int, vendor_pan: str, section: str, fy: str) -> Optional[TDSVendorCumulative]:
        """Get cumulative tracking for vendor"""
        if not self.db:
            return None

        return self.db.query(TDSVendorCumulative).filter(
            TDSVendorCumulative.client_id == client_id,
            TDSVendorCumulative.vendor_pan == vendor_pan,
            TDSVendorCumulative.tds_section == section,
            TDSVendorCumulative.financial_year == fy
        ).first()

    def _store_tds_entries(self, db: Session, entries: List[Dict]) -> int:
        """Store computed TDS entries in database"""
        count = 0
        for entry in entries:
            # Check if entry already exists for this transaction
            existing = db.query(TDSEntry).filter(
                TDSEntry.transaction_id == entry["transaction_id"]
            ).first()

            if existing:
                # Update existing
                existing.tds_amount = entry["tds_amount"]
                existing.tds_deducted = entry["tds_deducted"]
                existing.is_deducted = entry["is_deducted"]
                existing.missed_deduction = entry["missed_deduction"]
                existing.penalty_estimate = entry["penalty_estimate"]
                existing.months_delayed = entry["months_delayed"]
            else:
                # Create new
                tds_entry = TDSEntry(
                    id=str(uuid.uuid4()),
                    **{k: v for k, v in entry.items() if k != "threshold_crossed"}
                )
                db.add(tds_entry)
                count += 1

        return count

    def _update_cumulative_tracking(self, db: Session, client_id: int, financial_year: Optional[str]):
        """Update per-vendor cumulative tracking"""
        # Get all TDS entries for the FY
        query = db.query(TDSEntry).filter(
            TDSEntry.client_id == client_id,
            TDSEntry.missed_deduction == False  # Only deducted/computed entries
        )

        if financial_year:
            query = query.filter(TDSEntry.financial_year == financial_year)

        entries = query.all()

        # Group by vendor + section
        vendor_groups = {}
        for entry in entries:
            key = (entry.vendor_pan, entry.tds_section)
            if key not in vendor_groups:
                vendor_groups[key] = []
            vendor_groups[key].append(entry)

        # Update cumulative records
        for (vendor_pan, section), group in vendor_groups.items():
            total_payments = sum(e.payment_amount for e in group)
            total_tds = sum(e.tds_amount for e in group)
            total_deducted = sum(e.tds_deducted for e in group)

            # Get threshold
            section_details = TDS_SECTIONS.get(section)
            threshold_agg = section_details.threshold_aggregate if section_details else 0

            # Check if threshold crossed
            threshold_crossed = False
            if threshold_agg > 0 and total_payments >= threshold_agg:
                threshold_crossed = True

            # Find or create cumulative record
            cumulative = db.query(TDSVendorCumulative).filter(
                TDSVendorCumulative.client_id == client_id,
                TDSVendorCumulative.vendor_pan == vendor_pan,
                TDSVendorCumulative.tds_section == section,
                TDSVendorCumulative.financial_year == financial_year
            ).first()

            if cumulative:
                cumulative.total_payments = total_payments
                cumulative.total_tds_computed = total_tds
                cumulative.total_tds_deducted = total_deducted
                cumulative.total_tds_missed = total_tds - total_deducted
                cumulative.threshold_crossed = threshold_crossed
                cumulative.payment_count = len(group)
            else:
                cumulative = TDSVendorCumulative(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    vendor_pan=vendor_pan,
                    vendor_type=group[0].vendor_type if group else "unknown",
                    tds_section=section,
                    financial_year=financial_year,
                    total_payments=total_payments,
                    total_tds_computed=total_tds,
                    total_tds_deducted=total_deducted,
                    total_tds_missed=total_tds - total_deducted,
                    threshold_single=section_details.threshold_single if section_details else 0,
                    threshold_aggregate=threshold_agg,
                    threshold_crossed=threshold_crossed,
                    payment_count=len(group)
                )
                db.add(cumulative)

    def _generate_summary(self, entries: List[Dict]) -> Dict[str, Any]:
        """Generate TDS computation summary"""
        total_computed = sum(e["tds_amount"] for e in entries)
        total_deducted = sum(e["tds_deducted"] for e in entries)
        total_missed = sum(e["tds_amount"] for e in entries if e["missed_deduction"])
        total_penalty = sum(e["penalty_estimate"] for e in entries)

        missed_count = sum(1 for e in entries if e["missed_deduction"])

        # Group by section
        by_section = {}
        for entry in entries:
            section = entry["tds_section"]
            if section not in by_section:
                by_section[section] = {"count": 0, "amount": 0, "missed": 0}
            by_section[section]["count"] += 1
            by_section[section]["amount"] += entry["tds_amount"]
            if entry["missed_deduction"]:
                by_section[section]["missed"] += entry["tds_amount"]

        return {
            "total_entries": len(entries),
            "total_tds_computed": round(total_computed, 2),
            "total_tds_deducted": round(total_deducted, 2),
            "total_tds_missed": round(total_missed, 2),
            "total_penalty_estimate": round(total_penalty, 2),
            "missed_deduction_count": missed_count,
            "by_section": {k: {sk: round(sv, 2) if isinstance(sv, float) else sv 
                               for sk, sv in v.items()} 
                          for k, v in by_section.items()}
        }

    def _get_financial_year(self, date_obj: datetime) -> str:
        """Get financial year string (e.g., 2025-26) from date"""
        if date_obj.month >= 4:
            return f"{date_obj.year}-{str(date_obj.year + 1)[2:]}"
        else:
            return f"{date_obj.year - 1}-{str(date_obj.year)[2:]}"

    def _get_quarter(self, date_obj: datetime) -> str:
        """Get quarter from date"""
        month = date_obj.month
        if month in [4, 5, 6]:
            return "Q1"
        elif month in [7, 8, 9]:
            return "Q2"
        elif month in [10, 11, 12]:
            return "Q3"
        else:
            return "Q4"

    def _get_fy_date_range(self, fy: str) -> Tuple[datetime, datetime]:
        """Get start and end dates for financial year"""
        start_year = int(fy.split("-")[0])
        return (
            datetime(start_year, 4, 1),
            datetime(start_year + 1, 3, 31, 23, 59, 59)
        )

    def _get_quarter_date_range(self, fy: str, quarter: str) -> Tuple[datetime, datetime]:
        """Get start and end dates for quarter"""
        start_year = int(fy.split("-")[0])

        quarter_months = {
            "Q1": (4, 6), "Q2": (7, 9), "Q3": (10, 12), "Q4": (1, 3)
        }

        start_month, end_month = quarter_months.get(quarter, (4, 6))

        if quarter == "Q4":
            start_year += 1

        return (
            datetime(start_year, start_month, 1),
            datetime(start_year, end_month, 31, 23, 59, 59)
        )

    def _calculate_months_delayed(self, payment_date: datetime) -> int:
        """Calculate months delayed for penalty (simplified)"""
        now = datetime.utcnow()
        if payment_date > now:
            return 0

        months = (now.year - payment_date.year) * 12 + (now.month - payment_date.month)
        return max(0, months)

    def _extract_pan_from_narration(self, narration: str) -> Optional[str]:
        """Extract PAN from transaction narration (simplified)"""
        import re
        # PAN pattern: 5 letters + 4 digits + 1 letter
        match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', narration.upper())
        if match:
            return match.group(0)
        return None
