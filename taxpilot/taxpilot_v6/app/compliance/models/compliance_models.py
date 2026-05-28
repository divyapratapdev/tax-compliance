from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from app.database import Base
import enum


class ComplianceType(str, enum.Enum):
    GSTR1       = "GSTR1"
    GSTR3B      = "GSTR3B"
    TDS_RETURN  = "TDS_RETURN"   # 26Q
    ADVANCE_TAX = "ADVANCE_TAX"
    ITR         = "ITR"
    ROC         = "ROC"


class ComplianceStatus(str, enum.Enum):
    PENDING = "pending"
    FILED   = "filed"
    MISSED  = "missed"


class ComplianceItem(Base):
    __tablename__ = "compliance_items"

    id         = Column(String(36), primary_key=True, index=True)
    client_id  = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    # What and when
    type       = Column(String(30), nullable=False)   # ComplianceType value
    due_date   = Column(DateTime, nullable=False)
    period_month = Column(Integer, nullable=True)     # 1-12, null for non-monthly items
    period_year  = Column(Integer, nullable=True)
    quarter      = Column(String(2), nullable=True)   # Q1/Q2/Q3/Q4 for TDS returns
    description  = Column(String(255), nullable=True) # human-readable label

    # Status
    status     = Column(String(20), default="pending")  # ComplianceStatus value
    filed_at   = Column(DateTime, nullable=True)
    filed_by   = Column(String(100), nullable=True)

    # Reminder flags  (APScheduler sets these; prevents duplicate sends)
    reminder_7day_sent  = Column(Boolean, default=False)
    reminder_1day_sent  = Column(Boolean, default=False)
    escalation_sent     = Column(Boolean, default=False)

    # Penalty metadata (displayed in overdue list)
    penalty_per_day     = Column(Float, default=0)    # ₹ per day late fee where applicable
    penalty_description = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_ci_client_status",   "client_id", "status"),
        Index("idx_ci_client_due",      "client_id", "due_date"),
        Index("idx_ci_client_type",     "client_id", "type"),
        Index("idx_ci_reminders",       "status", "reminder_7day_sent", "due_date"),
        {"extend_existing": True},
    )
