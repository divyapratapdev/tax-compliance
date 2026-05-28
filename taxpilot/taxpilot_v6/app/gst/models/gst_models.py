
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from app.database import Base
import enum

class GSTInvoiceSource(str, enum.Enum):
    UPLOADED = "uploaded"      # From client's purchase register / invoices
    GSTR2A = "gstr2a"          # From GST portal GSTR-2A/2B download
    GSTR2B = "gstr2b"          # From GST portal GSTR-2B (static statement)

class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    AMOUNT_MISMATCH = "amount_mismatch"
    MISSING_IN_2A = "missing_in_2a"
    MISSING_IN_BOOKS = "missing_in_books"
    GSTIN_MISMATCH = "gstin_mismatch"
    RESOLVED = "resolved"

class RunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class GSTInvoice(Base):
    __tablename__ = "gst_invoices"

    id = Column(String(36), primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    source = Column(String(20), default="uploaded")  # uploaded/gstr2a/gstr2b

    # Supplier details
    supplier_gstin = Column(String(15), nullable=False, index=True)
    supplier_name = Column(String(255), nullable=True)

    # Invoice details
    invoice_number = Column(String(100), nullable=False, index=True)
    invoice_date = Column(DateTime, nullable=False)

    # Financial details
    taxable_amount = Column(Float, default=0)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    cess = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    total_tax = Column(Float, default=0)  # cgst + sgst + igst + cess

    # Period for reconciliation
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)

    # Document reference
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)

    # Reconciliation state
    reconciliation_status = Column(String(50), default="pending")
    matched_with_id = Column(String(36), nullable=True)  # FK to matching invoice

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Composite index for fast reconciliation lookups
    __table_args__ = (
        Index('idx_gst_invoice_lookup', 'client_id', 'supplier_gstin', 'invoice_number', 'period_month', 'period_year'),
        Index('idx_gst_invoice_period', 'client_id', 'period_month', 'period_year'),
        {'extend_existing': True},
    )

class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id = Column(String(36), primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    # Period
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)

    # Status
    status = Column(String(20), default="running")
    error_message = Column(Text, nullable=True)

    # Counts
    total_invoices = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    amount_mismatch_count = Column(Integer, default=0)
    missing_in_2a_count = Column(Integer, default=0)
    missing_in_books_count = Column(Integer, default=0)
    gstin_mismatch_count = Column(Integer, default=0)

    # ITC amounts
    itc_safe_amount = Column(Float, default=0)      # Matched invoices
    itc_at_risk_amount = Column(Float, default=0)   # Missing in 2A or mismatched
    itc_missing_amount = Column(Float, default=0)   # Missing in books (supplier filed, we don't have)

    # Timestamps
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_recon_run_period', 'client_id', 'period_month', 'period_year'),
        {'extend_existing': True},
    )

class ReconciliationMismatch(Base):
    __tablename__ = "reconciliation_mismatches"

    id = Column(String(36), primary_key=True, index=True)
    run_id = Column(String(36), ForeignKey("reconciliation_runs.id"), nullable=False)

    # Mismatch classification
    mismatch_type = Column(String(50), nullable=False)  # amount_mismatch, missing_in_2a, missing_in_books, gstin_mismatch

    # Linked invoices (nullable depending on mismatch type)
    client_invoice_id = Column(String(36), ForeignKey("gst_invoices.id"), nullable=True)
    gstr2a_invoice_id = Column(String(36), ForeignKey("gst_invoices.id"), nullable=True)

    # Key identifiers for display
    supplier_gstin = Column(String(15), nullable=True)
    invoice_number = Column(String(100), nullable=True)

    # Amount comparison
    client_amount = Column(Float, nullable=True)
    gstr2a_amount = Column(Float, nullable=True)
    difference_amount = Column(Float, nullable=True)

    # Suggested action
    suggested_action = Column(Text, nullable=True)

    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(String(100), nullable=True)  # CA user ID or "system"
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('idx_mismatch_run', 'run_id', 'mismatch_type'),
        Index('idx_mismatch_unresolved', 'run_id', 'is_resolved'),
        {'extend_existing': True},
    )
