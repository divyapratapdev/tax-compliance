
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum

class DocumentType(str, enum.Enum):
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"

class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"

class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    MISSING_IN_2A = "missing_in_2a"
    MISSING_IN_BOOKS = "missing_in_books"

class ComplianceStatus(str, enum.Enum):
    PENDING = "pending"
    FILED = "filed"
    MISSED = "missed"

class CAFirm(Base):
    __tablename__ = "ca_firms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    registration_number = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    api_key_hash = Column(String(255), nullable=True)
    plan = Column(String(50), default="free")  # free, starter, growth, scale
    created_at = Column(DateTime, server_default=func.now())

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    ca_firm_id = Column(Integer, ForeignKey("ca_firms.id"), nullable=False)
    company_name = Column(String(255), nullable=False)
    gstin = Column(String(15), unique=True, nullable=True)  # 15 char GSTIN
    pan = Column(String(10), unique=True, nullable=True)  # 10 char PAN
    turnover_category = Column(String(50), nullable=True)  # small, medium, large
    registration_type = Column(String(50), nullable=True)  # regular, composition, etc.
    created_at = Column(DateTime, server_default=func.now())

class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    bank_name = Column(String(100), nullable=False)
    account_number_last4 = Column(String(4), nullable=True)
    account_type = Column(String(50), nullable=True)  # savings, current, etc.
    connected_at = Column(DateTime, server_default=func.now())

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    type = Column(String(50), nullable=False)  # invoice, bank_statement, other
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    ocr_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    ocr_error = Column(Text, nullable=True)  # Full error message if failed (FIXED: separate field)
    ocr_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    date = Column(DateTime, nullable=True)
    narration = Column(Text, nullable=True)
    amount = Column(Float, nullable=False, default=0)
    type = Column(String(10), nullable=True)  # credit/debit
    category = Column(String(100), default="uncategorized")
    category_confidence = Column(Float, default=0.0)  # 1.0 for rule-matched, 0.0 for uncategorized, ML confidence later
    is_reviewed = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)  # ML flagged for CA review
    ledger_entry_suggested = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

# GSTInvoice is defined in app/gst/models/gst_models.py — import from there.
# ReconciliationResult is defined in app/gst/models/gst_models.py — import from there.
