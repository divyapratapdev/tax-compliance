
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from app.database import SessionLocal
from app.models import models
from app.gst.models.gst_models import GSTInvoice, ReconciliationRun, ReconciliationMismatch
from app.gst.gstr2a_parser import GSTR2AParser
from app.gst.reconciliation_engine import GSTReconciliationEngine

logger = logging.getLogger(__name__)

class GSTService:
    """
    High-level service for GST reconciliation operations.
    Orchestrates parser, engine, and database operations.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.parser = GSTR2AParser()
        self.engine = GSTReconciliationEngine()

    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return SessionLocal()

    def upload_gstr2a(self, 
                      client_id: int, 
                      file_path: str, 
                      file_format: str,
                      period_month: int, 
                      period_year: int) -> Dict[str, Any]:
        """
        Upload and parse GSTR-2A/2B data from GST portal.

        Args:
            client_id: Client ID
            file_path: Path to uploaded file
            file_format: "excel" or "json"
            period_month: Month (1-12)
            period_year: Year (YYYY)

        Returns:
            {"status": "success", "invoices_parsed": N, "errors": M}
        """
        db = self._get_db()

        try:
            # Parse file
            if file_format.lower() in ["excel", "xlsx", "xls"]:
                invoices = self.parser.parse_excel(file_path, period_month, period_year)
            elif file_format.lower() == "json":
                invoices = self.parser.parse_json(file_path, period_month, period_year)
            else:
                raise ValueError(f"Unsupported format: {file_format}")

            # Store in database
            stored_count = 0
            for inv_data in invoices:
                gst_inv = GSTInvoice(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    source="gstr2a",
                    supplier_gstin=inv_data["supplier_gstin"],
                    supplier_name=inv_data.get("supplier_name"),
                    invoice_number=inv_data["invoice_number"],
                    invoice_date=inv_data.get("invoice_date"),
                    taxable_amount=inv_data.get("taxable_amount", 0),
                    cgst=inv_data.get("cgst", 0),
                    sgst=inv_data.get("sgst", 0),
                    igst=inv_data.get("igst", 0),
                    cess=inv_data.get("cess", 0),
                    total_amount=inv_data.get("total_amount", 0),
                    total_tax=inv_data.get("total_tax", 0),
                    period_month=period_month,
                    period_year=period_year,
                    reconciliation_status="pending"
                )
                db.add(gst_inv)
                stored_count += 1

            db.commit()

            stats = self.parser.get_parse_stats()
            return {
                "status": "success",
                "invoices_parsed": stats["parsed"],
                "invoices_stored": stored_count,
                "errors": stats["errors"],
                "success_rate": stats["success_rate"]
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error uploading GSTR-2A: {str(e)}")
            raise
        finally:
            if not self.db:
                db.close()

    def run_reconciliation(self, client_id: int, period_month: int, period_year: int) -> Dict[str, Any]:
        """
        Run reconciliation for a client and period.

        Returns:
            {"run_id": str, "status": "completed", "summary": {...}}
        """
        db = self._get_db()

        try:
            # Create reconciliation run record
            run_id = str(uuid.uuid4())
            run = ReconciliationRun(
                id=run_id,
                client_id=client_id,
                period_month=period_month,
                period_year=period_year,
                status="running"
            )
            db.add(run)
            db.commit()

            # Fetch client invoices (uploaded/purchase register)
            client_invoices = db.query(GSTInvoice).filter(
                GSTInvoice.client_id == client_id,
                GSTInvoice.period_month == period_month,
                GSTInvoice.period_year == period_year,
                GSTInvoice.source == "uploaded"
            ).all()

            # Fetch GSTR-2A invoices
            gstr2a_invoices = db.query(GSTInvoice).filter(
                GSTInvoice.client_id == client_id,
                GSTInvoice.period_month == period_month,
                GSTInvoice.period_year == period_year,
                GSTInvoice.source.in_(["gstr2a", "gstr2b"])
            ).all()

            # Convert to dicts for engine
            books_data = [self._invoice_to_dict(inv) for inv in client_invoices]
            gstr2a_data = [self._invoice_to_dict(inv) for inv in gstr2a_invoices]

            # Run reconciliation
            results = self.engine.reconcile(books_data, gstr2a_data)

            # Store results
            self._store_reconciliation_results(db, run_id, results)

            # Update run record
            summary = results["summary"]
            run.status = "completed"
            run.total_invoices = summary["total_books_invoices"]
            run.matched_count = summary["matched_count"]
            run.amount_mismatch_count = summary["amount_mismatch_count"]
            run.missing_in_2a_count = summary["missing_in_2a_count"]
            run.missing_in_books_count = summary["missing_in_books_count"]
            run.gstin_mismatch_count = summary["gstin_mismatch_count"]
            run.itc_safe_amount = summary["itc_safe_amount"]
            run.itc_at_risk_amount = summary["itc_at_risk_amount"]
            run.itc_missing_amount = summary["itc_missing_in_books_amount"]
            run.completed_at = datetime.utcnow()

            db.commit()

            return {
                "run_id": run_id,
                "status": "completed",
                "summary": summary
            }

        except Exception as e:
            db.rollback()
            # Update run as failed
            run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_message = str(e)[:500]
                db.commit()
            logger.error(f"Reconciliation failed: {str(e)}")
            raise
        finally:
            if not self.db:
                db.close()

    def get_reconciliation_results(self, run_id: str) -> Dict[str, Any]:
        """Get detailed reconciliation results by run ID"""
        db = self._get_db()

        try:
            run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
            if not run:
                raise ValueError(f"Reconciliation run not found: {run_id}")

            mismatches = db.query(ReconciliationMismatch).filter(
                ReconciliationMismatch.run_id == run_id
            ).all()

            return {
                "run_id": run_id,
                "status": run.status,
                "period": f"{run.period_month}/{run.period_year}",
                "summary": {
                    "total_invoices": run.total_invoices,
                    "matched": run.matched_count,
                    "amount_mismatch": run.amount_mismatch_count,
                    "missing_in_2a": run.missing_in_2a_count,
                    "missing_in_books": run.missing_in_books_count,
                    "gstin_mismatch": run.gstin_mismatch_count,
                    "itc_safe": run.itc_safe_amount,
                    "itc_at_risk": run.itc_at_risk_amount,
                    "itc_missing": run.itc_missing_amount,
                },
                "mismatches": [self._mismatch_to_dict(m) for m in mismatches]
            }
        finally:
            if not self.db:
                db.close()

    def get_itc_summary(self, client_id: int, period_month: int, period_year: int) -> Dict[str, Any]:
        """
        Get ITC summary for a client and period.
        The money shot for CA demos.
        """
        db = self._get_db()

        try:
            # Get latest completed run
            run = db.query(ReconciliationRun).filter(
                ReconciliationRun.client_id == client_id,
                ReconciliationRun.period_month == period_month,
                ReconciliationRun.period_year == period_year,
                ReconciliationRun.status == "completed"
            ).order_by(ReconciliationRun.completed_at.desc()).first()

            if not run:
                return {
                    "client_id": client_id,
                    "period": f"{period_month}/{period_year}",
                    "status": "no_data",
                    "message": "No reconciliation data found. Run reconciliation first."
                }

            # Get unresolved mismatches count
            unresolved = db.query(ReconciliationMismatch).filter(
                ReconciliationMismatch.run_id == run.id,
                ReconciliationMismatch.is_resolved == False
            ).count()

            return {
                "client_id": client_id,
                "period": f"{period_month}/{period_year}",
                "run_id": run.id,
                "status": "ready",
                "itc_summary": {
                    "safe_to_claim": {
                        "amount": run.itc_safe_amount,
                        "description": "Matched invoices — ITC fully claimable",
                        "invoice_count": run.matched_count
                    },
                    "at_risk": {
                        "amount": run.itc_at_risk_amount,
                        "description": "Missing in GSTR-2A or amount mismatch — follow up with suppliers",
                        "invoice_count": run.missing_in_2a_count + run.amount_mismatch_count
                    },
                    "missing_in_books": {
                        "amount": run.itc_missing_amount,
                        "description": "Supplier filed but not in your books — add missing entries",
                        "invoice_count": run.missing_in_books_count
                    },
                    "total_potential": run.itc_safe_amount + run.itc_at_risk_amount + run.itc_missing_amount
                },
                "action_items": {
                    "unresolved_mismatches": unresolved,
                    "suppliers_to_follow_up": run.missing_in_2a_count,
                    "missing_entries_to_add": run.missing_in_books_count
                }
            }
        finally:
            if not self.db:
                db.close()

    def resolve_mismatch(self, mismatch_id: str, resolution: str, resolved_by: str) -> Dict[str, Any]:
        """Mark a mismatch as resolved with notes"""
        db = self._get_db()

        try:
            mismatch = db.query(ReconciliationMismatch).filter(
                ReconciliationMismatch.id == mismatch_id
            ).first()

            if not mismatch:
                raise ValueError(f"Mismatch not found: {mismatch_id}")

            mismatch.is_resolved = True
            mismatch.resolution_notes = resolution
            mismatch.resolved_by = resolved_by
            mismatch.resolved_at = datetime.utcnow()

            db.commit()

            return {
                "mismatch_id": mismatch_id,
                "status": "resolved",
                "resolution": resolution,
                "resolved_at": mismatch.resolved_at
            }
        finally:
            if not self.db:
                db.close()

    def _invoice_to_dict(self, inv: GSTInvoice) -> Dict[str, Any]:
        """Convert GSTInvoice ORM to dict for engine"""
        return {
            "id": inv.id,
            "supplier_gstin": inv.supplier_gstin,
            "supplier_name": inv.supplier_name,
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date,
            "taxable_amount": inv.taxable_amount,
            "cgst": inv.cgst,
            "sgst": inv.sgst,
            "igst": inv.igst,
            "cess": inv.cess,
            "total_amount": inv.total_amount,
            "total_tax": inv.total_tax,
        }

    def _store_reconciliation_results(self, db: Session, run_id: str, results: Dict):
        """Store reconciliation results in database"""

        # Store amount mismatches
        for mm in results["amount_mismatch"]:
            self._create_mismatch(db, run_id, "amount_mismatch", mm)

        # Store missing in 2A
        for mm in results["missing_in_2a"]:
            self._create_mismatch(db, run_id, "missing_in_2a", mm)

        # Store missing in books
        for mm in results["missing_in_books"]:
            self._create_mismatch(db, run_id, "missing_in_books", mm)

        # Store GSTIN mismatches
        for mm in results["gstin_mismatch"]:
            self._create_mismatch(db, run_id, "gstin_mismatch", mm)

        db.commit()

    def _create_mismatch(self, db: Session, run_id: str, mismatch_type: str, data: Dict):
        """Create a mismatch record"""
        books_inv = data.get("books_invoice")
        gstr2a_inv = data.get("gstr2a_invoice")

        mismatch = ReconciliationMismatch(
            id=str(uuid.uuid4()),
            run_id=run_id,
            mismatch_type=mismatch_type,
            client_invoice_id=books_inv.get("id") if books_inv else None,
            gstr2a_invoice_id=gstr2a_inv.get("id") if gstr2a_inv else None,
            supplier_gstin=(books_inv or gstr2a_inv).get("supplier_gstin"),
            invoice_number=(books_inv or gstr2a_inv).get("invoice_number"),
            client_amount=books_inv.get("total_amount") if books_inv else None,
            gstr2a_amount=gstr2a_inv.get("total_amount") if gstr2a_inv else None,
            difference_amount=data.get("difference"),
            suggested_action=data.get("suggested_action", "Review required")
        )
        db.add(mismatch)

    def _mismatch_to_dict(self, mm: ReconciliationMismatch) -> Dict[str, Any]:
        """Convert mismatch ORM to dict"""
        return {
            "id": mm.id,
            "type": mm.mismatch_type,
            "supplier_gstin": mm.supplier_gstin,
            "invoice_number": mm.invoice_number,
            "client_amount": mm.client_amount,
            "gstr2a_amount": mm.gstr2a_amount,
            "difference": mm.difference_amount,
            "suggested_action": mm.suggested_action,
            "is_resolved": mm.is_resolved,
            "resolved_at": mm.resolved_at,
            "resolution_notes": mm.resolution_notes
        }
