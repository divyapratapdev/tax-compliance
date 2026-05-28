
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime
import logging

from app.database import get_db, engine, Base, SessionLocal
from app.models import models
from app.parsers.bank_statement_parser import BankStatementParser
from app.ocr.invoice_ocr import InvoiceOCR
from app.categorization.categorization_engine import TransactionCategorizer, TallyExporter
from app.gst.gst_service import GSTService
from app.tds.tds_service import TDSService
from app.gst.models.gst_models import GSTInvoice, ReconciliationRun, ReconciliationMismatch
from app.schemas import schemas
from app.compliance.compliance_router import router as compliance_router
from app.returns.returns_router import router as returns_router
from app.compliance.compliance_engine import start_scheduler
from app.compliance.models.compliance_models import ComplianceItem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TaxPilot Ingestion Service",
    description="Document ingestion engine for CA firms - bank statements & invoices",
    version="1.0.0"
)

# Compliance router
app.include_router(compliance_router)

# Returns router
app.include_router(returns_router)

# Start APScheduler for daily compliance alerts
start_scheduler()

# Initialize categorizer (loads pre-trained model if available)
categorizer = TransactionCategorizer()
tally_exporter = TallyExporter()

# CORS — TODO: Change to actual frontend URL before production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DEV ONLY: Change to ["https://yourdomain.com"] in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# File size limit: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ingestion", "timestamp": datetime.utcnow()}

@app.post("/ingest/bank-statement", response_model=schemas.IngestionResponse)
async def ingest_bank_statement(
    background_tasks: BackgroundTasks,
    client_id: int,
    bank_account_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and parse a bank statement (PDF, Excel, CSV).
    Supports HDFC, SBI, ICICI, Axis formats.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate extension
    allowed_extensions = {'.pdf', '.xlsx', '.xls', '.csv'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported format: {file_ext}. Allowed: {allowed_extensions}"
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

    # Save file
    doc_id = str(uuid.uuid4())
    storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}{file_ext}")

    try:
        with open(storage_path, "wb") as f:
            f.write(content)

        # Create document record in request session
        document = models.Document(
            id=doc_id,
            client_id=client_id,
            type="bank_statement",
            original_filename=file.filename,
            storage_path=storage_path,
            ocr_status="processing",
            created_at=datetime.utcnow()
        )
        db.add(document)
        db.commit()

        # Pass data to background task — create FRESH session inside the task
        background_tasks.add_task(
            process_bank_statement,
            doc_id,
            storage_path,
            file_ext,
            client_id,
            bank_account_id
        )

        return schemas.IngestionResponse(
            document_id=doc_id,
            status="processing",
            message="Bank statement uploaded and queued for parsing",
            file_type="bank_statement",
            original_filename=file.filename
        )

    except Exception as e:
        logger.error(f"Error processing bank statement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/ingest/invoice", response_model=schemas.IngestionResponse)
async def ingest_invoice(
    background_tasks: BackgroundTasks,
    client_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and OCR an invoice (PDF, JPG, PNG).
    Extracts: vendor name, GSTIN, invoice number, date, amount, tax components.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {file_ext}. Allowed: {allowed_extensions}"
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

    doc_id = str(uuid.uuid4())
    storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}{file_ext}")

    try:
        with open(storage_path, "wb") as f:
            f.write(content)

        document = models.Document(
            id=doc_id,
            client_id=client_id,
            type="invoice",
            original_filename=file.filename,
            storage_path=storage_path,
            ocr_status="processing",
            created_at=datetime.utcnow()
        )
        db.add(document)
        db.commit()

        # Pass data to background task — create FRESH session inside the task
        background_tasks.add_task(
            process_invoice,
            doc_id,
            storage_path,
            file_ext,
            client_id
        )

        return schemas.IngestionResponse(
            document_id=doc_id,
            status="processing",
            message="Invoice uploaded and queued for OCR",
            file_type="invoice",
            original_filename=file.filename
        )

    except Exception as e:
        logger.error(f"Error processing invoice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/documents/{document_id}", response_model=schemas.DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get document status and extracted data"""
    doc = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    transactions = db.query(models.Transaction).filter(
        models.Transaction.document_id == document_id
    ).all() if doc.type == "bank_statement" else []

    gst_invoices = db.query(GSTInvoice).filter(
        GSTInvoice.document_id == document_id
    ).all() if doc.type == "invoice" else []

    return schemas.DocumentResponse(
        document=doc,
        transactions=transactions,
        gst_invoices=gst_invoices
    )

@app.get("/clients/{client_id}/transactions")
def get_client_transactions(
    client_id: int, 
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all transactions for a client"""
    transactions = db.query(models.Transaction).filter(
        models.Transaction.client_id == client_id
    ).offset(skip).limit(limit).all()
    return transactions

# Background processing functions — CREATE FRESH DB SESSION
def process_bank_statement(doc_id, storage_path, file_ext, client_id, bank_account_id):
    """Parse bank statement, store transactions, and auto-categorize using ML. Runs in background thread."""
    db = SessionLocal()  # FRESH session — never reuse request session
    try:
        parser = BankStatementParser()

        if file_ext == '.pdf':
            transactions = parser.parse_pdf(storage_path, bank_name="auto")
        elif file_ext in ['.xlsx', '.xls']:
            transactions = parser.parse_excel(storage_path)
        elif file_ext == '.csv':
            transactions = parser.parse_csv(storage_path)
        else:
            raise ValueError(f"Unsupported format: {file_ext}")

        # Store transactions with auto-categorization
        stored_count = 0
        for txn in transactions:
            narration = txn.get("narration", "")

            # Use ML categorizer for intelligent classification
            prediction = categorizer.predict(narration)

            db_txn = models.Transaction(
                id=str(uuid.uuid4()),
                client_id=client_id,
                bank_account_id=bank_account_id,
                document_id=doc_id,
                date=txn.get("date"),
                narration=narration,
                amount=txn.get("amount", 0),
                type=txn.get("type", "debit"),
                category=prediction["category"],
                category_confidence=prediction["confidence"],
                is_reviewed=not prediction["needs_review"],  # Auto-reviewed if high confidence
                needs_review=prediction["needs_review"],
                ledger_entry_suggested=None,
                created_at=datetime.utcnow()
            )
            db.add(db_txn)
            stored_count += 1

        # Update document status
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.ocr_status = "completed"
            doc.ocr_completed_at = datetime.utcnow()

        db.commit()
        logger.info(f"Processed {stored_count} transactions from bank statement {doc_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process bank statement {doc_id}: {str(e)}")
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.ocr_status = "failed"
            doc.ocr_error = str(e)[:500]  # Store error separately, truncated
        db.commit()
    finally:
        db.close()  # ALWAYS close the session

def process_invoice(doc_id, storage_path, file_ext, client_id):
    """OCR invoice and extract GST details. Runs in background thread."""
    db = SessionLocal()  # FRESH session
    try:
        ocr = InvoiceOCR()

        if file_ext == '.pdf':
            invoice_data = ocr.process_pdf(storage_path)
        else:
            invoice_data = ocr.process_image(storage_path)

        # Store GST invoice
        gst_invoice = GSTInvoice(
            id=str(uuid.uuid4()),
            client_id=client_id,
            document_id=doc_id,
            vendor_gstin=invoice_data.get("vendor_gstin", ""),
            vendor_name=invoice_data.get("vendor_name", ""),
            invoice_number=invoice_data.get("invoice_number", ""),
            invoice_date=invoice_data.get("invoice_date"),
            taxable_amount=invoice_data.get("taxable_amount", 0),
            cgst=invoice_data.get("cgst", 0),
            sgst=invoice_data.get("sgst", 0),
            igst=invoice_data.get("igst", 0),
            total=invoice_data.get("total", 0),
            source="uploaded",
            reconciliation_status="pending"
        )
        db.add(gst_invoice)

        # Update document status
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.ocr_status = "completed"
            doc.ocr_completed_at = datetime.utcnow()

        db.commit()
        logger.info(f"Processed invoice {doc_id}: {invoice_data.get('vendor_name', 'Unknown')}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process invoice {doc_id}: {str(e)}")
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.ocr_status = "failed"
            doc.ocr_error = str(e)[:500]
        db.commit()
    finally:
        db.close()


@app.post("/categorize/{client_id}")
def categorize_client_transactions(
    client_id: int,
    min_confidence: float = 0.0,
    db: Session = Depends(get_db)
):
    """
    Categorize all uncategorized transactions for a client.
    Returns summary of categorizations and flagged items for review.
    """
    # Get uncategorized transactions
    transactions = db.query(models.Transaction).filter(
        models.Transaction.client_id == client_id,
        models.Transaction.category == "uncategorized"
    ).all()

    if not transactions:
        return {
            "client_id": client_id,
            "processed": 0,
            "message": "No uncategorized transactions found"
        }

    results = {
        "client_id": client_id,
        "processed": 0,
        "categorized": 0,
        "flagged_for_review": 0,
        "by_category": {},
        "needs_review": []
    }

    for txn in transactions:
        prediction = categorizer.predict(txn.narration)

        txn.category = prediction["category"]
        txn.category_confidence = prediction["confidence"]
        txn.is_reviewed = not prediction["needs_review"]

        results["processed"] += 1

        if prediction["category"] != "uncategorized":
            results["categorized"] += 1

        if prediction["needs_review"]:
            results["flagged_for_review"] += 1
            results["needs_review"].append({
                "transaction_id": txn.id,
                "narration": txn.narration,
                "predicted_category": prediction["category"],
                "confidence": prediction["confidence"],
                "method": prediction["method"]
            })

        cat = prediction["category"]
        results["by_category"][cat] = results["by_category"].get(cat, 0) + 1

    db.commit()

    return results

@app.post("/train-categorizer/{client_id}")
def train_categorizer(
    client_id: int,
    db: Session = Depends(get_db)
):
    """
    Train ML classifier on reviewed transactions for a client.
    Requires at least 50 reviewed transactions across multiple categories.
    """
    # Get reviewed transactions with categories
    transactions = db.query(models.Transaction).filter(
        models.Transaction.client_id == client_id,
        models.Transaction.is_reviewed == True,
        models.Transaction.category != "uncategorized"
    ).all()

    if len(transactions) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 50 reviewed transactions for training. Found: {len(transactions)}"
        )

    training_data = [
        {"narration": txn.narration, "category": txn.category}
        for txn in transactions
    ]

    metrics = categorizer.train(training_data, force=True)

    return {
        "client_id": client_id,
        "training_samples": len(training_data),
        "metrics": metrics
    }

@app.get("/clients/{client_id}/export-tally")
def export_tally_xml(
    client_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Export categorized transactions to Tally-compatible XML.
    Optional date range filter (YYYY-MM-DD format).
    """
    query = db.query(models.Transaction).filter(
        models.Transaction.client_id == client_id,
        models.Transaction.category != "uncategorized"
    )

    if start_date:
        query = query.filter(models.Transaction.date >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(models.Transaction.date <= datetime.strptime(end_date, "%Y-%m-%d"))

    transactions = query.all()

    if not transactions:
        raise HTTPException(status_code=404, detail="No categorized transactions found for export")

    # Convert to dicts for exporter
    txn_dicts = []
    for txn in transactions:
        txn_dicts.append({
            "id": txn.id,
            "date": txn.date,
            "narration": txn.narration,
            "amount": txn.amount,
            "type": txn.type,
            "category": txn.category
        })

    xml_content = tally_exporter.generate_voucher_xml(txn_dicts)

    # Save to file
    export_path = os.path.join(UPLOAD_DIR, f"tally_export_client_{client_id}.xml")
    tally_exporter.save_to_file(xml_content, export_path)

    return {
        "client_id": client_id,
        "transactions_exported": len(transactions),
        "export_path": export_path,
        "download_url": f"/download/{os.path.basename(export_path)}"
    }

@app.get("/clients/{client_id}/category-stats")
def get_category_stats(client_id: int, db: Session = Depends(get_db)):
    """
    Get distribution of transaction categories for a client.
    Shows where manual review is concentrated.
    """
    transactions = db.query(models.Transaction).filter(
        models.Transaction.client_id == client_id
    ).all()

    distribution = categorizer.get_category_distribution(
        [{"category": txn.category} for txn in transactions]
    )

    flagged = db.query(models.Transaction).filter(
        models.Transaction.client_id == client_id,
        models.Transaction.is_reviewed == False
    ).count()

    return {
        "client_id": client_id,
        "total_transactions": len(transactions),
        "flagged_for_review": flagged,
        "category_distribution": distribution,
        "model_trained": categorizer.is_trained
    }


# === GST Reconciliation Endpoints (Module 3) ===

@app.post("/v1/gst/gstr2a/upload")
async def upload_gstr2a(
    client_id: int,
    period_month: int,
    period_year: int,
    file_format: str = "excel",  # excel or json
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload GSTR-2A/2B data from GST portal.
    Accepts Excel or JSON format downloaded from portal.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate period
    if not (1 <= period_month <= 12):
        raise HTTPException(status_code=400, detail="period_month must be 1-12")

    # Save file
    file_ext = os.path.splitext(file.filename)[1].lower()
    doc_id = str(uuid.uuid4())
    storage_path = os.path.join(UPLOAD_DIR, f"gstr2a_{doc_id}{file_ext}")

    try:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large. Max 10MB.")

        with open(storage_path, "wb") as f:
            f.write(content)

        # Parse and store
        gst_service = GSTService(db=db)
        result = gst_service.upload_gstr2a(
            client_id=client_id,
            file_path=storage_path,
            file_format=file_format,
            period_month=period_month,
            period_year=period_year
        )

        return {
            "status": "success",
            "client_id": client_id,
            "period": f"{period_month}/{period_year}",
            **result
        }

    except Exception as e:
        logger.error(f"Error uploading GSTR-2A: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/v1/gst/reconcile/{client_id}")
def trigger_reconciliation(
    client_id: int,
    period_month: int,
    period_year: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger GST reconciliation for a client and period.
    Runs in background. Returns run_id to track progress.
    """
    # Validate period
    if not (1 <= period_month <= 12):
        raise HTTPException(status_code=400, detail="period_month must be 1-12")

    run_id = str(uuid.uuid4())

    # Start background reconciliation
    background_tasks.add_task(
        run_reconciliation_background,
        run_id,
        client_id,
        period_month,
        period_year
    )

    return {
        "run_id": run_id,
        "status": "running",
        "client_id": client_id,
        "period": f"{period_month}/{period_year}",
        "message": "Reconciliation started. Check /v1/gst/reconciliation/{run_id} for results."
    }

def run_reconciliation_background(run_id: str, client_id: int, period_month: int, period_year: int):
    """Background task for reconciliation"""
    db = SessionLocal()
    try:
        gst_service = GSTService(db=db)
        result = gst_service.run_reconciliation(client_id, period_month, period_year)
        logger.info(f"Reconciliation completed: {result}")
    except Exception as e:
        db.rollback()
        logger.error(f"Reconciliation failed: {str(e)}")
        # Update run status to failed
        run = db.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.error_message = str(e)[:500]
            db.commit()
    finally:
        db.close()

@app.get("/v1/gst/reconciliation/{run_id}")
def get_reconciliation_results(run_id: str, db: Session = Depends(get_db)):
    """Get reconciliation results by run ID"""
    gst_service = GSTService(db=db)
    try:
        return gst_service.get_reconciliation_results(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/v1/gst/itc-summary/{client_id}")
def get_itc_summary(
    client_id: int,
    period_month: int,
    period_year: int,
    db: Session = Depends(get_db)
):
    """
    Get ITC summary for a client and period.

    Returns:
        {
            "itc_summary": {
                "safe_to_claim": {"amount": X, "invoice_count": Y},
                "at_risk": {"amount": X, "invoice_count": Y},
                "missing_in_books": {"amount": X, "invoice_count": Y}
            },
            "action_items": {
                "suppliers_to_follow_up": N,
                "missing_entries_to_add": N
            }
        }
    """
    if not (1 <= period_month <= 12):
        raise HTTPException(status_code=400, detail="period_month must be 1-12")

    gst_service = GSTService(db=db)
    return gst_service.get_itc_summary(client_id, period_month, period_year)

@app.get("/v1/gst/mismatches/{client_id}")
def get_unresolved_mismatches(
    client_id: int,
    period_month: Optional[int] = None,
    period_year: Optional[int] = None,
    mismatch_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all unresolved mismatches for a client"""
    query = db.query(ReconciliationMismatch).join(ReconciliationRun).filter(
        ReconciliationRun.client_id == client_id,
        ReconciliationMismatch.is_resolved == False
    )

    if period_month and period_year:
        query = query.filter(
            ReconciliationRun.period_month == period_month,
            ReconciliationRun.period_year == period_year
        )

    if mismatch_type:
        query = query.filter(ReconciliationMismatch.mismatch_type == mismatch_type)

    mismatches = query.order_by(ReconciliationMismatch.created_at.desc()).all()

    return {
        "client_id": client_id,
        "unresolved_count": len(mismatches),
        "mismatches": [
            {
                "id": mm.id,
                "type": mm.mismatch_type,
                "supplier_gstin": mm.supplier_gstin,
                "invoice_number": mm.invoice_number,
                "client_amount": mm.client_amount,
                "gstr2a_amount": mm.gstr2a_amount,
                "difference": mm.difference_amount,
                "suggested_action": mm.suggested_action,
                "created_at": mm.created_at
            }
            for mm in mismatches
        ]
    }

@app.post("/v1/gst/mismatches/{mismatch_id}/resolve")
def resolve_mismatch(
    mismatch_id: str,
    resolution: str,
    resolved_by: str = "ca_user",
    db: Session = Depends(get_db)
):
    """Mark a mismatch as resolved with notes"""
    gst_service = GSTService(db=db)
    try:
        return gst_service.resolve_mismatch(mismatch_id, resolution, resolved_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/v1/gst/suppliers/{client_id}")
def get_supplier_summary(
    client_id: int,
    period_month: int,
    period_year: int,
    db: Session = Depends(get_db)
):
    """
    Get supplier-wise summary for a period.
    Shows which suppliers have filed and which haven't.
    """
    # Get latest run
    run = db.query(ReconciliationRun).filter(
        ReconciliationRun.client_id == client_id,
        ReconciliationRun.period_month == period_month,
        ReconciliationRun.period_year == period_year,
        ReconciliationRun.status == "completed"
    ).order_by(ReconciliationRun.completed_at.desc()).first()

    if not run:
        raise HTTPException(status_code=404, detail="No reconciliation data found")

    # Get mismatches grouped by supplier
    mismatches = db.query(ReconciliationMismatch).filter(
        ReconciliationMismatch.run_id == run.id
    ).all()

    supplier_stats = {}
    for mm in mismatches:
        gstin = mm.supplier_gstin or "UNKNOWN"
        if gstin not in supplier_stats:
            supplier_stats[gstin] = {
                "gstin": gstin,
                "mismatches": 0,
                "types": set(),
                "total_difference": 0
            }
        supplier_stats[gstin]["mismatches"] += 1
        supplier_stats[gstin]["types"].add(mm.mismatch_type)
        if mm.difference_amount:
            supplier_stats[gstin]["total_difference"] += mm.difference_amount

    # Convert sets to lists for JSON
    for stats in supplier_stats.values():
        stats["types"] = list(stats["types"])

    return {
        "client_id": client_id,
        "period": f"{period_month}/{period_year}",
        "suppliers_with_issues": len(supplier_stats),
        "suppliers": list(supplier_stats.values())
    }


# === TDS Computation Endpoints (Module 4) ===

@app.post("/v1/tds/compute/{client_id}")
def compute_tds(
    client_id: int,
    financial_year: Optional[str] = None,
    quarter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Compute TDS for all transactions of a client.
    Identifies applicable sections, checks thresholds, flags missed deductions.
    """
    tds_service = TDSService(db=db)
    result = tds_service.compute_tds(client_id, financial_year, quarter)
    return result

@app.get("/v1/tds/entries/{client_id}")
def get_tds_entries(
    client_id: int,
    financial_year: Optional[str] = None,
    quarter: Optional[str] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get TDS entries with optional filters"""
    tds_service = TDSService(db=db)
    return {
        "client_id": client_id,
        "entries": tds_service.get_tds_entries(client_id, financial_year, quarter, section)
    }

@app.get("/v1/tds/missed/{client_id}")
def get_missed_deductions(
    client_id: int,
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all missed TDS deductions with penalty estimates.
    This is the compliance risk dashboard for CAs.
    """
    tds_service = TDSService(db=db)
    return tds_service.get_missed_deductions(client_id, financial_year)

@app.get("/v1/tds/cumulative/{client_id}")
def get_cumulative_summary(
    client_id: int,
    financial_year: str,
    db: Session = Depends(get_db)
):
    """Get per-vendor cumulative payment summary for a financial year"""
    tds_service = TDSService(db=db)
    return tds_service.get_cumulative_summary(client_id, financial_year)

@app.get("/v1/tds/26q/{client_id}")
def generate_26q(
    client_id: int,
    financial_year: str,
    quarter: str,
    tan: str,
    pan: str,
    deductor_name: str,
    db: Session = Depends(get_db)
):
    """
    Generate Form 26Q XML for NSDL filing.

    Args:
        tan: TAN of deductor
        pan: PAN of deductor
        deductor_name: Name of deductor company
    """
    tds_service = TDSService(db=db)
    return tds_service.generate_26q_xml(client_id, financial_year, quarter, tan, pan, deductor_name)

@app.get("/v1/tds/summary/{client_id}")
def get_tds_summary(
    client_id: int,
    financial_year: str,
    db: Session = Depends(get_db)
):
    """
    Get complete TDS summary for a financial year.
    Shows liability, deducted, missed, by quarter and section.
    """
    tds_service = TDSService(db=db)
    return tds_service.get_tds_summary(client_id, financial_year)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
