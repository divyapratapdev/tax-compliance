
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from app.database import SessionLocal
from app.models import models
from app.tds.models.tds_models import TDSEntry, TDSVendorCumulative, TDSReturnBatch
from app.tds.tds_engine import TDSEngine
from app.tds.form_26q_generator import Form26QGenerator
from app.tds.tds_rate_table import TDS_SECTIONS

logger = logging.getLogger(__name__)

class TDSService:
    """
    High-level service for TDS operations.
    Orchestrates engine, DB operations, and XML generation.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.engine = TDSEngine(db=db)

    def _get_db(self) -> Session:
        if self.db:
            return self.db
        return SessionLocal()

    def compute_tds(self, client_id: int, financial_year: Optional[str] = None,
                    quarter: Optional[str] = None) -> Dict[str, Any]:
        """Compute TDS for all transactions"""
        return self.engine.compute_tds_for_client(client_id, financial_year, quarter)

    def get_tds_entries(self, client_id: int, financial_year: Optional[str] = None,
                        quarter: Optional[str] = None, section: Optional[str] = None) -> List[Dict]:
        """Get TDS entries with filters"""
        db = self._get_db()

        try:
            query = db.query(TDSEntry).filter(TDSEntry.client_id == client_id)

            if financial_year:
                query = query.filter(TDSEntry.financial_year == financial_year)
            if quarter:
                query = query.filter(TDSEntry.quarter == quarter)
            if section:
                query = query.filter(TDSEntry.tds_section == section)

            entries = query.order_by(TDSEntry.payment_date.desc()).all()

            return [self._entry_to_dict(e) for e in entries]
        finally:
            if not self.db:
                db.close()

    def get_missed_deductions(self, client_id: int, financial_year: Optional[str] = None) -> Dict[str, Any]:
        """Get all missed deductions with penalty estimates"""
        db = self._get_db()

        try:
            query = db.query(TDSEntry).filter(
                TDSEntry.client_id == client_id,
                TDSEntry.missed_deduction == True
            )

            if financial_year:
                query = query.filter(TDSEntry.financial_year == financial_year)

            entries = query.order_by(TDSEntry.penalty_estimate.desc()).all()

            total_penalty = sum(e.penalty_estimate for e in entries)
            total_missed = sum(e.tds_amount for e in entries)

            return {
                "client_id": client_id,
                "financial_year": financial_year,
                "missed_count": len(entries),
                "total_missed_amount": round(total_missed, 2),
                "total_penalty_estimate": round(total_penalty, 2),
                "entries": [self._entry_to_dict(e) for e in entries]
            }
        finally:
            if not self.db:
                db.close()

    def get_cumulative_summary(self, client_id: int, financial_year: str) -> Dict[str, Any]:
        """Get per-vendor cumulative payment summary"""
        db = self._get_db()

        try:
            cumulatives = db.query(TDSVendorCumulative).filter(
                TDSVendorCumulative.client_id == client_id,
                TDSVendorCumulative.financial_year == financial_year
            ).order_by(TDSVendorCumulative.total_payments.desc()).all()

            return {
                "client_id": client_id,
                "financial_year": financial_year,
                "vendor_count": len(cumulatives),
                "vendors": [self._cumulative_to_dict(c) for c in cumulatives]
            }
        finally:
            if not self.db:
                db.close()

    def generate_26q_xml(self, client_id: int, financial_year: str, quarter: str,
                         tan: str, pan: str, deductor_name: str) -> Dict[str, Any]:
        """Generate Form 26Q XML for filing"""
        db = self._get_db()

        try:
            # Get entries for the quarter
            entries = db.query(TDSEntry).filter(
                TDSEntry.client_id == client_id,
                TDSEntry.financial_year == financial_year,
                TDSEntry.quarter == quarter,
                TDSEntry.missed_deduction == False  # Only filed entries
            ).all()

            if not entries:
                return {
                    "status": "no_data",
                    "message": "No TDS entries found for the specified period"
                }

            # Convert to dicts
            entry_dicts = [self._entry_to_dict(e) for e in entries]

            # Generate XML
            generator = Form26QGenerator(tan, pan, deductor_name)
            xml_content = generator.generate_26q(entry_dicts, financial_year, quarter)

            # Save to file
            file_name = f"26Q_{client_id}_{financial_year}_{quarter}.xml"
            file_path = f"./uploads/{file_name}"
            generator.save_to_file(xml_content, file_path)

            # Create batch record
            batch = TDSReturnBatch(
                id=str(uuid.uuid4()),
                client_id=client_id,
                financial_year=financial_year,
                quarter=quarter,
                tan=tan,
                pan=pan,
                status="draft",
                total_entries=len(entries),
                total_tds_amount=sum(e.tds_amount for e in entries),
                xml_path=file_path
            )
            db.add(batch)
            db.commit()

            return {
                "status": "generated",
                "batch_id": batch.id,
                "file_path": file_path,
                "file_name": file_name,
                "total_entries": len(entries),
                "total_tds": round(sum(e.tds_amount for e in entries), 2),
                "download_url": f"/download/{file_name}"
            }

        finally:
            if not self.db:
                db.close()

    def get_tds_summary(self, client_id: int, financial_year: str) -> Dict[str, Any]:
        """
        Get complete TDS summary for a financial year.
        Shows total liability, deducted, missed, by quarter and section.
        """
        db = self._get_db()

        try:
            # Get all entries for the FY
            entries = db.query(TDSEntry).filter(
                TDSEntry.client_id == client_id,
                TDSEntry.financial_year == financial_year
            ).all()

            # Quarter-wise breakdown
            quarters = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
            for e in entries:
                if e.quarter in quarters:
                    quarters[e.quarter].append(e)

            quarter_summary = {}
            for q, q_entries in quarters.items():
                quarter_summary[q] = {
                    "entries": len(q_entries),
                    "tds_computed": round(sum(e.tds_amount for e in q_entries), 2),
                    "tds_deducted": round(sum(e.tds_deducted for e in q_entries), 2),
                    "tds_missed": round(sum(e.tds_amount - e.tds_deducted for e in q_entries), 2),
                    "penalty": round(sum(e.penalty_estimate for e in q_entries), 2)
                }

            # Section-wise breakdown
            sections = {}
            for e in entries:
                sec = e.tds_section
                if sec not in sections:
                    sections[sec] = {"count": 0, "amount": 0, "missed": 0}
                sections[sec]["count"] += 1
                sections[sec]["amount"] += e.tds_amount
                sections[sec]["missed"] += (e.tds_amount - e.tds_deducted)

            # Overall totals
            total_computed = sum(e.tds_amount for e in entries)
            total_deducted = sum(e.tds_deducted for e in entries)
            total_missed = total_computed - total_deducted
            total_penalty = sum(e.penalty_estimate for e in entries)

            return {
                "client_id": client_id,
                "financial_year": financial_year,
                "overall": {
                    "total_entries": len(entries),
                    "total_tds_computed": round(total_computed, 2),
                    "total_tds_deducted": round(total_deducted, 2),
                    "total_tds_missed": round(total_missed, 2),
                    "total_penalty_estimate": round(total_penalty, 2),
                    "compliance_rate": round((total_deducted / max(total_computed, 1)) * 100, 2)
                },
                "quarterly": quarter_summary,
                "by_section": {k: {sk: round(sv, 2) if isinstance(sv, float) else sv 
                                   for sk, sv in v.items()} 
                              for k, v in sections.items()}
            }

        finally:
            if not self.db:
                db.close()

    def _entry_to_dict(self, entry: TDSEntry) -> Dict[str, Any]:
        """Convert TDSEntry to dict"""
        return {
            "id": entry.id,
            "transaction_id": entry.transaction_id,
            "vendor_pan": entry.vendor_pan,
            "vendor_name": entry.vendor_name,
            "vendor_type": entry.vendor_type,
            "payment_date": entry.payment_date,
            "payment_amount": entry.payment_amount,
            "tds_section": entry.tds_section,
            "tds_rate": entry.tds_rate,
            "tds_amount": entry.tds_amount,
            "tds_deducted": entry.tds_deducted,
            "is_deducted": entry.is_deducted,
            "missed_deduction": entry.missed_deduction,
            "penalty_estimate": entry.penalty_estimate,
            "months_delayed": entry.months_delayed,
            "financial_year": entry.financial_year,
            "quarter": entry.quarter,
            "source_category": entry.source_category,
        }

    def _cumulative_to_dict(self, cum: TDSVendorCumulative) -> Dict[str, Any]:
        """Convert TDSVendorCumulative to dict"""
        return {
            "vendor_pan": cum.vendor_pan,
            "vendor_name": cum.vendor_name,
            "vendor_type": cum.vendor_type,
            "tds_section": cum.tds_section,
            "total_payments": round(cum.total_payments, 2),
            "total_tds_computed": round(cum.total_tds_computed, 2),
            "total_tds_deducted": round(cum.total_tds_deducted, 2),
            "total_tds_missed": round(cum.total_tds_missed, 2),
            "threshold_crossed": cum.threshold_crossed,
            "payment_count": cum.payment_count,
        }
