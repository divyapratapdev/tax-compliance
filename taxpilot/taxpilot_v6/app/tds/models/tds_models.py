
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from app.database import Base
import enum

class Quarter(str, enum.Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"

class VendorType(str, enum.Enum):
    INDIVIDUAL = "individual"
    HUF = "huf"
    COMPANY = "company"
    LLP = "llp"
    AOP = "aop"
    TRUST = "trust"
    UNKNOWN = "unknown"

class TDSEntry(Base):
    __tablename__ = "tds_entries"

    id = Column(String(36), primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=True)

    # Vendor details
    vendor_pan = Column(String(10), nullable=True, index=True)
    vendor_name = Column(String(255), nullable=True)
    vendor_type = Column(String(20), default="unknown")  # individual/company/llp etc.
    vendor_gstin = Column(String(15), nullable=True)

    # Payment details
    payment_date = Column(DateTime, nullable=False)
    payment_amount = Column(Float, nullable=False, default=0)

    # TDS computation
    tds_section = Column(String(10), nullable=False, index=True)  # 194C, 194J, 194I etc.
    tds_rate = Column(Float, nullable=False, default=0)
    tds_amount = Column(Float, nullable=False, default=0)  # computed TDS
    tds_deducted = Column(Float, nullable=False, default=0)  # actually deducted (0 if missed)

    # Flags
    is_deducted = Column(Boolean, default=False)  # Whether TDS was actually deducted
    missed_deduction = Column(Boolean, default=False)  # Should have been deducted but wasn't
    is_pan_available = Column(Boolean, default=True)

    # Penalty estimate for missed deductions
    # 1% per month from due date (simplified: from payment date)
    penalty_estimate = Column(Float, default=0)
    months_delayed = Column(Integer, default=0)

    # Period
    financial_year = Column(String(7), nullable=False, index=True)  # e.g. 2025-26
    quarter = Column(String(2), nullable=False, index=True)  # Q1/Q2/Q3/Q4

    # Source
    source_category = Column(String(100), nullable=True)  # from categorization engine
    source_narration = Column(Text, nullable=True)  # original transaction narration

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Indexes for common queries
    __table_args__ = (
        Index('idx_tds_client_fy', 'client_id', 'financial_year'),
        Index('idx_tds_client_quarter', 'client_id', 'financial_year', 'quarter'),
        Index('idx_tds_vendor_fy', 'client_id', 'vendor_pan', 'financial_year'),
        Index('idx_tds_missed', 'client_id', 'missed_deduction', 'is_deducted'),
        {'extend_existing': True},
    )

class TDSVendorCumulative(Base):
    __tablename__ = "tds_vendor_cumulative"

    id = Column(String(36), primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    # Vendor identification
    vendor_pan = Column(String(10), nullable=False, index=True)
    vendor_name = Column(String(255), nullable=True)
    vendor_type = Column(String(20), default="unknown")

    # Section tracking
    tds_section = Column(String(10), nullable=False)
    financial_year = Column(String(7), nullable=False)

    # Cumulative amounts
    total_payments = Column(Float, default=0)  # cumulative payments this FY
    total_tds_computed = Column(Float, default=0)
    total_tds_deducted = Column(Float, default=0)
    total_tds_missed = Column(Float, default=0)

    # Threshold tracking
    threshold_single = Column(Float, default=0)
    threshold_aggregate = Column(Float, default=0)
    threshold_crossed = Column(Boolean, default=False)
    threshold_crossed_date = Column(DateTime, nullable=True)

    # Counts
    payment_count = Column(Integer, default=0)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_tds_cum_vendor', 'client_id', 'vendor_pan', 'tds_section', 'financial_year'),
        Index('idx_tds_cum_threshold', 'client_id', 'threshold_crossed'),
        {'extend_existing': True},
    )

class TDSReturnBatch(Base):
    """Tracks 26Q return filing batches"""
    __tablename__ = "tds_return_batches"

    id = Column(String(36), primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    # Return details
    financial_year = Column(String(7), nullable=False)
    quarter = Column(String(2), nullable=False)
    tan = Column(String(10), nullable=True)  # TAN of deductor
    pan = Column(String(10), nullable=True)  # PAN of deductor

    # Status
    status = Column(String(20), default="draft")  # draft/filed/verified
    filed_at = Column(DateTime, nullable=True)
    filed_by = Column(String(100), nullable=True)

    # Counts
    total_entries = Column(Integer, default=0)
    total_tds_amount = Column(Float, default=0)

    # File paths
    xml_path = Column(String(500), nullable=True)
    fvu_path = Column(String(500), nullable=True)  # FVU file for NSDL upload

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = {'extend_existing': True}
