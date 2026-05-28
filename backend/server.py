"""
TaxPilot Dashboard API — FastAPI + MongoDB

Mirrors the data contracts of the TaxPilot v9 Python engine (which uses MySQL),
so the React dashboard can run standalone today and be wired to the real engine
later by switching the data source. Single-tenant for demo; multi-tenant via
ca_firm_id on every document.

Routes (all under /api):

    Auth/profile
        GET    /api/profile                       — Current CA firm profile

    Dashboard
        GET    /api/dashboard/summary             — KPIs + top alerts

    Clients
        GET    /api/clients                       — List with filters
        GET    /api/clients/{client_id}           — One client detail

    Documents
        GET    /api/documents                     — Documents/uploads queue
        POST   /api/documents/upload              — Simulated upload (no real OCR)

    GST Reconciliation
        GET    /api/gst/reconciliation/summary    — ITC summary for client+period
        GET    /api/gst/mismatches                — Mismatch list (filterable)
        POST   /api/gst/mismatches/{id}/resolve   — Resolve a mismatch

    TDS
        GET    /api/tds/summary                   — TDS overall + quarterly
        GET    /api/tds/missed                    — Missed deductions list
        GET    /api/tds/vendors                   — Cumulative per-vendor

    Compliance
        GET    /api/compliance/calendar           — All items for client
        POST   /api/compliance/{id}/mark-filed    — Mark item filed

    Settings
        PUT    /api/settings/profile              — Update firm profile
        PUT    /api/settings/alerts               — Update alert preferences

    Utility
        POST   /api/seed/reset                    — Reset & re-seed demo data
        GET    /api/health                        — Health check
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Query, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from auth_utils import verify_password, get_password_hash, create_access_token, decode_access_token
from local_ocr import process_document_background
import re

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "taxpilot")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("taxpilot")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# --------------------------------------------------------------------------- #
# Pydantic models (response shapes)
# --------------------------------------------------------------------------- #

class FirmProfile(BaseModel):
    id: str
    name: str
    registration_number: str
    email: str
    plan: str
    created_at: datetime
    alert_preferences: Dict[str, bool] = Field(default_factory=dict)


class ClientOut(BaseModel):
    id: str
    name: str
    gstin: str
    pan: str
    turnover_category: str
    registration_type: str
    health: str  # safe | at_risk | critical
    open_mismatches: int
    missed_tds: float
    upcoming_compliance: int
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    client_id: str
    client_name: str
    type: str
    original_filename: str
    ocr_status: str
    ocr_error: Optional[str] = None
    uploaded_at: datetime
    completed_at: Optional[datetime] = None
    extracted_count: Optional[int] = None  # txns/invoices extracted


class MismatchOut(BaseModel):
    id: str
    client_id: str
    type: str
    supplier_gstin: str
    supplier_name: str
    invoice_number: str
    invoice_date: datetime
    books_amount: Optional[float] = None
    gstr2a_amount: Optional[float] = None
    difference: Optional[float] = None
    suggested_action: str
    is_resolved: bool
    resolution_notes: Optional[str] = None


class TDSEntryOut(BaseModel):
    id: str
    client_id: str
    vendor_pan: str
    vendor_name: str
    payment_date: datetime
    payment_amount: float
    tds_section: str
    tds_rate: float
    tds_amount: float
    tds_deducted: float
    is_deducted: bool
    missed_deduction: bool
    penalty_estimate: float
    months_delayed: int
    financial_year: str
    quarter: str


class ComplianceItemOut(BaseModel):
    id: str
    client_id: str
    client_name: str
    type: str
    due_date: datetime
    description: str
    status: str
    filed_at: Optional[datetime] = None
    penalty_per_day: float
    penalty_description: str
    reminder_7day_sent: bool
    reminder_1day_sent: bool
    days_to_due: int


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    user = await db.users.find_one({"email": payload["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "_id"}


def _client_health(open_mismatches: int, missed_tds: float, overdue_compliance: int) -> str:
    if missed_tds > 25000 or overdue_compliance >= 1 or open_mismatches >= 5:
        return "critical"
    if missed_tds > 0 or open_mismatches >= 1:
        return "at_risk"
    return "safe"


# --------------------------------------------------------------------------- #
# Seed data (idempotent)
# --------------------------------------------------------------------------- #

DEMO_FIRM_ID = "firm-demo-001"

async def seed_demo_data(force: bool = False) -> Dict[str, int]:
    """Idempotent seed. Returns counts of seeded items."""
    existing = await db.firms.find_one({"id": DEMO_FIRM_ID})
    if existing and not force:
        return {"status": "already_seeded"}

    # Wipe & re-seed (scoped to demo firm only — never touch other firms' data)
    await db.firms.delete_many({"id": DEMO_FIRM_ID})
    demo_clients = await db.clients.find({"ca_firm_id": DEMO_FIRM_ID}, {"id": 1}).to_list(500)
    demo_client_ids = [c["id"] for c in demo_clients]
    if demo_client_ids:
        for coll in ["documents", "mismatches", "tds_entries", "compliance_items"]:
            await db[coll].delete_many({"client_id": {"$in": demo_client_ids}})
    await db.clients.delete_many({"ca_firm_id": DEMO_FIRM_ID})

    now = _now()

    # --- Firm ---
    await db.firms.insert_one({
        "id": DEMO_FIRM_ID,
        "name": "Kumar & Associates",
        "registration_number": "FRN-302345E",
        "email": "office@kumarca.in",
        "plan": "growth",
        "created_at": (now - timedelta(days=365)).isoformat(),
        "alert_preferences": {
            "whatsapp_enabled": True,
            "email_enabled": True,
            "reminder_7day": True,
            "reminder_1day": True,
            "escalation_on_missed": True,
        },
    })

    # --- User ---
    admin_user = await db.users.find_one({"email": "admin@taxpilot.com"})
    if not admin_user:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "name": "Admin User",
            "email": "admin@taxpilot.com",
            "hashed_password": get_password_hash("password123"),
            "firm_id": DEMO_FIRM_ID,
            "created_at": now.isoformat(),
        })
    else:
        await db.users.update_one({"email": "admin@taxpilot.com"}, {"$set": {"firm_id": DEMO_FIRM_ID}})

    # --- Clients ---
    clients_seed = [
        {
            "id": "client-001",
            "name": "Acme Manufacturing Pvt Ltd",
            "gstin": "27AABCA1234E1Z5",
            "pan": "AABCA1234E",
            "turnover_category": "medium",
            "registration_type": "regular",
            "industry": "Manufacturing",
        },
        {
            "id": "client-002",
            "name": "Bharat Tech Services LLP",
            "gstin": "29AABCB5678F1ZQ",
            "pan": "AABCB5678F",
            "turnover_category": "small",
            "registration_type": "regular",
            "industry": "IT Services",
        },
        {
            "id": "client-003",
            "name": "Sunrise Retail Co",
            "gstin": "07AABCS9012G1ZX",
            "pan": "AABCS9012G",
            "turnover_category": "small",
            "registration_type": "composition",
            "industry": "Retail",
        },
    ]
    for c in clients_seed:
        c["ca_firm_id"] = DEMO_FIRM_ID
        c["created_at"] = (now - timedelta(days=180)).isoformat()
    await db.clients.insert_many(clients_seed)

    # --- Documents ---
    docs = [
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "bank_statement",
            "original_filename": "HDFC_Acme_Apr-2025.pdf",
            "ocr_status": "completed",
            "extracted_count": 42,
            "uploaded_at": (now - timedelta(days=3)).isoformat(),
            "completed_at": (now - timedelta(days=3, minutes=-2)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "invoice",
            "original_filename": "Vendor_Sharma_INV-2026-0142.pdf",
            "ocr_status": "completed",
            "extracted_count": 1,
            "uploaded_at": (now - timedelta(days=2)).isoformat(),
            "completed_at": (now - timedelta(days=2, minutes=-1)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-002",
            "type": "bank_statement",
            "original_filename": "SBI_BharatTech_Q1FY26.xlsx",
            "ocr_status": "completed",
            "extracted_count": 38,
            "uploaded_at": (now - timedelta(days=5)).isoformat(),
            "completed_at": (now - timedelta(days=5, minutes=-3)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-002",
            "type": "gstr2a",
            "original_filename": "GSTR-2A_Apr-2025.xlsx",
            "ocr_status": "completed",
            "extracted_count": 24,
            "uploaded_at": (now - timedelta(days=1)).isoformat(),
            "completed_at": (now - timedelta(days=1, minutes=-1)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-003",
            "type": "invoice",
            "original_filename": "Tax_Invoice_Mishra_Traders.png",
            "ocr_status": "processing",
            "uploaded_at": (now - timedelta(minutes=4)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "invoice",
            "original_filename": "scan_blurry_invoice.jpg",
            "ocr_status": "failed",
            "ocr_error": "OCR confidence < 30%, vendor name unreadable",
            "uploaded_at": (now - timedelta(days=4)).isoformat(),
        },
    ]
    await db.documents.insert_many(docs)

    # --- GST Mismatches (Module 3) ---
    mismatches = [
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "missing_in_2a",
            "supplier_gstin": "27AABFS9876P1ZK",
            "supplier_name": "Sharma Electronics",
            "invoice_number": "INV-2026-0142",
            "invoice_date": (now - timedelta(days=18)).isoformat(),
            "books_amount": 47200.00,
            "gstr2a_amount": None,
            "difference": 47200.00,
            "books_tax": 7200.00,
            "suggested_action": "Follow up with supplier to file GSTR-1 for April 2025",
            "is_resolved": False,
            "period_month": 4,
            "period_year": 2025,
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "amount_mismatch",
            "supplier_gstin": "27AABCM2345Q1ZD",
            "supplier_name": "Mittal Polymers",
            "invoice_number": "MP/2025-26/0033",
            "invoice_date": (now - timedelta(days=22)).isoformat(),
            "books_amount": 118000.00,
            "gstr2a_amount": 116800.00,
            "difference": 1200.00,
            "books_tax": 18000.00,
            "suggested_action": "Verify correct amount with supplier (1.0% variance)",
            "is_resolved": False,
            "period_month": 4,
            "period_year": 2025,
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "gstin_mismatch",
            "supplier_gstin": "29AABFR7766R1Z9",
            "supplier_name": "Rao Logistics",
            "invoice_number": "RL/24-25/887",
            "invoice_date": (now - timedelta(days=27)).isoformat(),
            "books_amount": 32500.00,
            "gstr2a_amount": 32500.00,
            "difference": 0.0,
            "books_tax": 4954.00,
            "suggested_action": "Supplier appears registered in Karnataka, not Maharashtra. Verify state code.",
            "is_resolved": False,
            "period_month": 4,
            "period_year": 2025,
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "type": "missing_in_books",
            "supplier_gstin": "27AAAFK1010P1ZL",
            "supplier_name": "Kale Stationers",
            "invoice_number": "KS-789",
            "invoice_date": (now - timedelta(days=15)).isoformat(),
            "books_amount": None,
            "gstr2a_amount": 12500.00,
            "difference": 12500.00,
            "books_tax": 1900.00,
            "suggested_action": "Add missing purchase entry to books",
            "is_resolved": False,
            "period_month": 4,
            "period_year": 2025,
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-002",
            "type": "missing_in_2a",
            "supplier_gstin": "29AABCH4455L1ZP",
            "supplier_name": "Hegde Cloud Services",
            "invoice_number": "HCS-2025-218",
            "invoice_date": (now - timedelta(days=12)).isoformat(),
            "books_amount": 84000.00,
            "gstr2a_amount": None,
            "difference": 84000.00,
            "books_tax": 12814.00,
            "suggested_action": "Follow up with supplier to file GSTR-1",
            "is_resolved": False,
            "period_month": 4,
            "period_year": 2025,
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-002",
            "type": "amount_mismatch",
            "supplier_gstin": "27AAACJ8001R1ZF",
            "supplier_name": "Joshi Office Rentals",
            "invoice_number": "JOR/Apr/2025",
            "invoice_date": (now - timedelta(days=29)).isoformat(),
            "books_amount": 70800.00,
            "gstr2a_amount": 75000.00,
            "difference": -4200.00,
            "books_tax": 10800.00,
            "suggested_action": "Amount in books appears understated by ₹4,200",
            "is_resolved": False,
            "period_month": 4,
            "period_year": 2025,
            "created_at": now.isoformat(),
        },
    ]
    await db.mismatches.insert_many(mismatches)

    # --- TDS Entries (Module 4) ---
    fy = "2025-26"
    tds = [
        # Acme — missed 194J professional fees
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "vendor_pan": "ABCPS1234A",
            "vendor_name": "Sharma & Co Chartered Accountants",
            "payment_date": (now - timedelta(days=92)).isoformat(),
            "payment_amount": 85000.00,
            "tds_section": "194J",
            "tds_rate": 10.0,
            "tds_amount": 8500.00,
            "tds_deducted": 0.0,
            "is_deducted": False,
            "missed_deduction": True,
            "penalty_estimate": 255.00,
            "months_delayed": 3,
            "financial_year": fy,
            "quarter": "Q1",
            "source_category": "professional_fees",
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "vendor_pan": "AXNPK2233B",
            "vendor_name": "Krishna Contractors",
            "payment_date": (now - timedelta(days=65)).isoformat(),
            "payment_amount": 165000.00,
            "tds_section": "194C",
            "tds_rate": 2.0,
            "tds_amount": 3300.00,
            "tds_deducted": 0.0,
            "is_deducted": False,
            "missed_deduction": True,
            "penalty_estimate": 66.00,
            "months_delayed": 2,
            "financial_year": fy,
            "quarter": "Q1",
            "source_category": "vendor_payment",
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-001",
            "vendor_pan": "BNRPP9988M",
            "vendor_name": "Premier Office Rentals",
            "payment_date": (now - timedelta(days=30)).isoformat(),
            "payment_amount": 280000.00,
            "tds_section": "194I",
            "tds_rate": 10.0,
            "tds_amount": 28000.00,
            "tds_deducted": 28000.00,
            "is_deducted": True,
            "missed_deduction": False,
            "penalty_estimate": 0.0,
            "months_delayed": 0,
            "financial_year": fy,
            "quarter": "Q1",
            "source_category": "office_expense",
        },
        # Bharat Tech — clean compliance
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-002",
            "vendor_pan": "AKTPS5511C",
            "vendor_name": "Hegde Cloud Services",
            "payment_date": (now - timedelta(days=12)).isoformat(),
            "payment_amount": 84000.00,
            "tds_section": "194J",
            "tds_rate": 2.0,
            "tds_amount": 1680.00,
            "tds_deducted": 1680.00,
            "is_deducted": True,
            "missed_deduction": False,
            "penalty_estimate": 0.0,
            "months_delayed": 0,
            "financial_year": fy,
            "quarter": "Q1",
            "source_category": "professional_fees",
        },
        {
            "id": str(uuid.uuid4()),
            "client_id": "client-002",
            "vendor_pan": "AKLPM7733N",
            "vendor_name": "Mehta Legal Advisors",
            "payment_date": (now - timedelta(days=55)).isoformat(),
            "payment_amount": 45000.00,
            "tds_section": "194J",
            "tds_rate": 10.0,
            "tds_amount": 4500.00,
            "tds_deducted": 0.0,
            "is_deducted": False,
            "missed_deduction": True,
            "penalty_estimate": 90.00,
            "months_delayed": 2,
            "financial_year": fy,
            "quarter": "Q1",
            "source_category": "professional_fees",
        },
    ]
    await db.tds_entries.insert_many(tds)

    # --- Compliance items (Module 5) ---
    today = date.today()
    upcoming_dates = [
        ("client-001", "GSTR1", today + timedelta(days=2), "GSTR-1 for April 2025", 50, "₹50/day late fee u/s 47 CGST"),
        ("client-001", "GSTR3B", today + timedelta(days=11), "GSTR-3B for April 2025", 50, "₹50/day + 18% p.a. interest u/s 47"),
        ("client-001", "TDS_RETURN", today + timedelta(days=33), "26Q TDS Return – Q1 FY 2025-26", 200, "₹200/day u/s 234E NSDL"),
        ("client-002", "GSTR1", today + timedelta(days=2), "GSTR-1 for April 2025", 50, "₹50/day late fee u/s 47 CGST"),
        ("client-002", "GSTR3B", today + timedelta(days=11), "GSTR-3B for April 2025", 50, "₹50/day + 18% p.a. interest u/s 47"),
        ("client-003", "GSTR1", today + timedelta(days=2), "GSTR-1 for April 2025", 50, "₹50/day late fee u/s 47 CGST"),
        ("client-001", "ADVANCE_TAX", today + timedelta(days=18), "Advance Tax – 15% (Jun)", 0, "1% per month u/s 234B/234C"),
        ("client-002", "ITR", today + timedelta(days=85), "ITR Filing – FY 2024-25 (Non-Audit)", 0, "₹5,000 late fee u/s 234F"),
    ]
    overdue_dates = [
        ("client-001", "TDS_PAYMENT", today - timedelta(days=4), "TDS deposit for May 2025", 0, "Interest @ 1.5% per month u/s 201(1A)"),
    ]
    items = []
    for cid, ctype, dt, desc, pen, pen_desc in upcoming_dates + overdue_dates:
        days_to_due = (dt - today).days
        status = "pending" if days_to_due >= 0 else "missed"
        items.append({
            "id": str(uuid.uuid4()),
            "client_id": cid,
            "type": ctype,
            "due_date": datetime.combine(dt, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
            "description": desc,
            "status": status,
            "filed_at": None,
            "penalty_per_day": pen,
            "penalty_description": pen_desc,
            "reminder_7day_sent": days_to_due <= 7 and days_to_due >= 0,
            "reminder_1day_sent": days_to_due <= 1 and days_to_due >= 0,
            "created_at": now.isoformat(),
        })
    await db.compliance_items.insert_many(items)

    counts = {
        "firms": await db.firms.count_documents({}),
        "clients": await db.clients.count_documents({}),
        "documents": await db.documents.count_documents({}),
        "mismatches": await db.mismatches.count_documents({}),
        "tds_entries": await db.tds_entries.count_documents({}),
        "compliance_items": await db.compliance_items.count_documents({}),
    }
    logger.info("Seeded demo data: %s", counts)
    return counts


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #

app = FastAPI(title="TaxPilot Dashboard API", version="1.0.0")
api = APIRouter(prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    # Create indexes for query performance
    await db.users.create_index("email", unique=True)
    await db.clients.create_index("ca_firm_id")
    await db.clients.create_index("id", unique=True)
    await db.documents.create_index("client_id")
    await db.mismatches.create_index([("client_id", 1), ("is_resolved", 1)])
    await db.tds_entries.create_index([("client_id", 1), ("financial_year", 1)])
    await db.compliance_items.create_index([("client_id", 1), ("status", 1)])
    await seed_demo_data(force=False)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    client.close()


@api.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "taxpilot-dashboard", "timestamp": _now().isoformat()}


# Removed /seed/reset for security


# ---------- Auth ----------

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    firm_name: str

@api.post("/auth/register")
async def register(payload: RegisterRequest):
    # Validate email format
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', payload.email):
        raise HTTPException(400, "Invalid email format")
    # Validate password strength
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if await db.users.find_one({"email": payload.email}):
        raise HTTPException(400, "Email already registered")
    
    firm_id = f"firm-{uuid.uuid4().hex[:8]}"
    now = _now().isoformat()
    
    await db.firms.insert_one({
        "id": firm_id,
        "name": payload.firm_name,
        "registration_number": "PENDING",
        "email": payload.email,
        "plan": "starter",
        "created_at": now,
        "alert_preferences": {
            "whatsapp_enabled": False,
            "email_enabled": True,
            "reminder_7day": True,
            "reminder_1day": True,
            "escalation_on_missed": False,
        },
    })
    
    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "email": payload.email,
        "hashed_password": get_password_hash(payload.password),
        "firm_id": firm_id,
        "created_at": now,
    })
    
    return {"status": "success"}

@api.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user["email"], "firm_id": user["firm_id"]})
    return {"access_token": access_token, "token_type": "bearer"}


# ---------- Profile ----------

@api.get("/profile")
async def get_profile(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    firm = await db.firms.find_one({"id": current_user["firm_id"]})
    if not firm:
        raise HTTPException(404, "Firm not found")
    return _strip_id(firm)


@api.put("/settings/profile")
async def update_profile(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    allowed = {"name", "registration_number", "email", "plan"}
    update = {k: v for k, v in payload.items() if k in allowed}
    if not update:
        raise HTTPException(400, "No valid fields to update")
    await db.firms.update_one({"id": current_user["firm_id"]}, {"$set": update})
    firm = await db.firms.find_one({"id": current_user["firm_id"]})
    return _strip_id(firm)


@api.put("/settings/alerts")
async def update_alert_prefs(payload: Dict[str, bool], current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    await db.firms.update_one(
        {"id": current_user["firm_id"]},
        {"$set": {"alert_preferences": payload}}
    )
    firm = await db.firms.find_one({"id": current_user["firm_id"]})
    return _strip_id(firm)


# ---------- Clients ----------

async def _enrich_client(c: Dict[str, Any]) -> Dict[str, Any]:
    cid = c["id"]
    open_mismatches = await db.mismatches.count_documents({"client_id": cid, "is_resolved": False})
    missed_agg = await db.tds_entries.aggregate([
        {"$match": {"client_id": cid, "missed_deduction": True}},
        {"$group": {"_id": None, "total": {"$sum": "$tds_amount"}, "penalty": {"$sum": "$penalty_estimate"}}}
    ]).to_list(1)
    missed_tds = missed_agg[0]["total"] if missed_agg else 0.0
    missed_penalty = missed_agg[0]["penalty"] if missed_agg else 0.0
    upcoming = await db.compliance_items.count_documents({
        "client_id": cid, "status": "pending"
    })
    overdue = await db.compliance_items.count_documents({
        "client_id": cid, "status": "missed"
    })
    health = _client_health(open_mismatches, missed_tds, overdue)
    return {
        **_strip_id(c),
        "health": health,
        "open_mismatches": open_mismatches,
        "missed_tds": missed_tds,
        "missed_penalty": missed_penalty,
        "upcoming_compliance": upcoming,
        "overdue_compliance": overdue,
    }


@api.get("/clients")
async def list_clients(
    search: Optional[str] = None,
    health: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {"ca_firm_id": current_user["firm_id"]}
    if search:
        safe_search = re.escape(search)
        q["$or"] = [
            {"name": {"$regex": safe_search, "$options": "i"}},
            {"gstin": {"$regex": safe_search, "$options": "i"}},
            {"pan": {"$regex": safe_search, "$options": "i"}},
        ]
    docs = await db.clients.find(q).to_list(500)
    enriched = [await _enrich_client(c) for c in docs]
    if health:
        enriched = [c for c in enriched if c["health"] == health]
    return {"count": len(enriched), "clients": enriched}


@api.get("/clients/{client_id}")
async def get_client(client_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    c = await db.clients.find_one({"id": client_id, "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found")
    return await _enrich_client(c)


class ClientCreate(BaseModel):
    name: str
    pan: str
    gstin: str
    entity_type: str = "Private Limited"

@api.post("/clients")
async def create_client(payload: ClientCreate, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    client_id = f"cli-{uuid.uuid4().hex[:8]}"
    client_doc = {
        "id": client_id,
        "ca_firm_id": current_user["firm_id"],
        "name": payload.name,
        "pan": payload.pan,
        "gstin": payload.gstin,
        "entity_type": payload.entity_type,
        "created_at": _now().isoformat()
    }
    await db.clients.insert_one(client_doc)
    return await _enrich_client(client_doc)

@api.put("/clients/{client_id}")
async def update_client(client_id: str, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    c = await db.clients.find_one({"id": client_id, "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found")
    allowed = {"name", "pan", "gstin", "entity_type"}
    update = {k: v for k, v in payload.items() if k in allowed}
    if not update:
        raise HTTPException(400, "No valid fields to update")
    await db.clients.update_one({"id": client_id}, {"$set": update})
    return await get_client(client_id, current_user)

@api.delete("/clients/{client_id}")
async def delete_client(client_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    c = await db.clients.find_one({"id": client_id, "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found")
    await db.clients.delete_one({"id": client_id})
    # Cascade: remove orphaned data for deleted client
    await db.documents.delete_many({"client_id": client_id})
    await db.mismatches.delete_many({"client_id": client_id})
    await db.tds_entries.delete_many({"client_id": client_id})
    await db.compliance_items.delete_many({"client_id": client_id})
    return {"status": "success"}


# ---------- Dashboard ----------

@api.get("/dashboard/summary")
async def dashboard_summary(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}).to_list(500)
    enriched = [await _enrich_client(c) for c in clients]

    total_clients = len(enriched)
    at_risk = sum(1 for c in enriched if c["health"] == "at_risk")
    critical = sum(1 for c in enriched if c["health"] == "critical")
    safe = sum(1 for c in enriched if c["health"] == "safe")

    # Scope all aggregations to this firm's clients only (multi-tenant isolation)
    firm_client_ids = [c["id"] for c in clients]

    # ITC at risk = sum of mismatch difference (missing_in_2a + amount_mismatch only)
    itc_agg = await db.mismatches.aggregate([
        {"$match": {"is_resolved": False, "type": {"$in": ["missing_in_2a", "amount_mismatch"]}, "client_id": {"$in": firm_client_ids}}},
        {"$group": {"_id": None, "total": {"$sum": "$books_tax"}}}
    ]).to_list(1)
    itc_at_risk = itc_agg[0]["total"] if itc_agg else 0.0

    # Missed TDS
    tds_agg = await db.tds_entries.aggregate([
        {"$match": {"missed_deduction": True, "client_id": {"$in": firm_client_ids}}},
        {"$group": {"_id": None, "missed": {"$sum": "$tds_amount"}, "penalty": {"$sum": "$penalty_estimate"}}}
    ]).to_list(1)
    missed_tds = tds_agg[0]["missed"] if tds_agg else 0.0
    missed_penalty = tds_agg[0]["penalty"] if tds_agg else 0.0

    upcoming_count = await db.compliance_items.count_documents({"status": "pending", "client_id": {"$in": firm_client_ids}})
    overdue_count = await db.compliance_items.count_documents({"status": "missed", "client_id": {"$in": firm_client_ids}})

    # Next 7 days
    today = _now()
    seven_days = today + timedelta(days=7)
    upcoming_items = await db.compliance_items.find({
        "status": "pending",
        "client_id": {"$in": firm_client_ids},
    }).to_list(500)
    upcoming_7 = sorted(
        [i for i in upcoming_items if i.get("due_date") and i["due_date"] <= seven_days.isoformat()],
        key=lambda x: x.get("due_date", "")
    )[:5]
    # enrich with client name
    cname = {c["id"]: c["name"] for c in clients}
    upcoming_enriched = []
    for it in upcoming_7:
        item = _strip_id(it)
        item["client_name"] = cname.get(item["client_id"], "—")
        # days to due
        try:
            dt = datetime.fromisoformat(item["due_date"].replace("Z", "+00:00"))
            item["days_to_due"] = (dt.date() - today.date()).days
        except Exception:
            item["days_to_due"] = 0
        upcoming_enriched.append(item)

    # Top missed TDS
    top_missed = await db.tds_entries.find({"missed_deduction": True, "client_id": {"$in": firm_client_ids}}).sort("tds_amount", -1).limit(5).to_list(5)
    top_missed_enriched = [{**_strip_id(t), "client_name": cname.get(t["client_id"], "—")} for t in top_missed]

    return {
        "kpis": {
            "total_clients": total_clients,
            "itc_at_risk": round(itc_at_risk, 2),
            "missed_tds": round(missed_tds, 2),
            "missed_penalty": round(missed_penalty, 2),
            "upcoming_compliance": upcoming_count,
            "overdue_compliance": overdue_count,
        },
        "client_health": {
            "safe": safe,
            "at_risk": at_risk,
            "critical": critical,
        },
        "upcoming_deadlines": upcoming_enriched,
        "top_missed_tds": top_missed_enriched,
    }


# ---------- Documents ----------

@api.get("/documents")
async def list_documents(
    client_id: Optional[str] = None, 
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    firm_clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}, {"id": 1, "name": 1}).to_list(500)
    firm_client_ids = [c["id"] for c in firm_clients]
    q: Dict[str, Any] = {"client_id": {"$in": firm_client_ids}}
    if client_id:
        if client_id not in firm_client_ids:
            return {"count": 0, "documents": []}
        q["client_id"] = client_id
    if status:
        q["ocr_status"] = status
    docs = await db.documents.find(q).sort("uploaded_at", -1).to_list(500)
    cname = {c["id"]: c["name"] for c in firm_clients}
    return {
        "count": len(docs),
        "documents": [{**_strip_id(d), "client_name": cname.get(d["client_id"], "—")} for d in docs]
    }


@api.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    client_id: str = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    c = await db.clients.find_one({"id": client_id, "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found or access denied")
    
    if not file.filename:
        raise HTTPException(400, "No file provided")
    allowed = {"bank_statement", "invoice", "gstr2a"}
    if doc_type not in allowed:
        raise HTTPException(400, f"doc_type must be one of {allowed}")
    # Check size before reading full file to prevent OOM attacks
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10MB)")
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10MB)")
        
    doc_id = str(uuid.uuid4())
    # Sanitize filename to prevent path traversal attacks
    safe_filename = Path(file.filename).name
    file_path = f"uploads/{doc_id}_{safe_filename}"
    with open(file_path, "wb") as f:
        f.write(contents)
        
    doc = {
        "id": doc_id,
        "client_id": client_id,
        "type": doc_type,
        "original_filename": file.filename,
        "ocr_status": "processing",
        "size_bytes": len(contents),
        "uploaded_at": _now().isoformat(),
        "file_path": file_path,
    }
    await db.documents.insert_one(doc.copy())
    
    background_tasks.add_task(process_document_background, db, doc_id, file_path, doc_type)
    
    return _strip_id(doc)


# ---------- GST Reconciliation ----------

@api.get("/gst/reconciliation/summary")
async def gst_recon_summary(client_id: str, month: int = 4, year: int = 2025, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    c = await db.clients.find_one({"id": client_id, "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found or access denied")
    all_mm = await db.mismatches.find({
        "client_id": client_id,
        "period_month": month,
        "period_year": year,
    }).to_list(500)
    by_type: Dict[str, int] = {}
    for m in all_mm:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1

    itc_safe = 0.0  # In reality matched count × avg tax; here we'll estimate
    matched_count = max(0, 20 - len(all_mm))  # demo: assume 20 invoices, mismatches are the gap
    # Simulate safe ITC from matched
    itc_safe = round(matched_count * 4500, 2)

    itc_at_risk = sum(
        m.get("books_tax", 0) for m in all_mm
        if m["type"] in ("missing_in_2a", "amount_mismatch", "gstin_mismatch")
    )
    itc_missing_in_books = sum(
        m.get("books_tax", 0) for m in all_mm if m["type"] == "missing_in_books"
    )

    return {
        "client_id": client_id,
        "period": {"month": month, "year": year},
        "summary": {
            "matched": matched_count,
            "by_type": by_type,
            "total_mismatches": len(all_mm),
        },
        "itc_summary": {
            "safe_to_claim": {"amount": itc_safe, "invoice_count": matched_count},
            "at_risk": {
                "amount": round(itc_at_risk, 2),
                "invoice_count": sum(by_type.get(t, 0) for t in ["missing_in_2a", "amount_mismatch", "gstin_mismatch"]),
            },
            "missing_in_books": {
                "amount": round(itc_missing_in_books, 2),
                "invoice_count": by_type.get("missing_in_books", 0),
            },
        },
    }


@api.get("/gst/mismatches")
async def list_mismatches(
    client_id: Optional[str] = None,
    mismatch_type: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    firm_clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}, {"id": 1, "name": 1}).to_list(500)
    firm_client_ids = [c["id"] for c in firm_clients]
    q: Dict[str, Any] = {"client_id": {"$in": firm_client_ids}}
    if client_id:
        if client_id not in firm_client_ids:
            return {"count": 0, "mismatches": []}
        q["client_id"] = client_id
    if mismatch_type:
        q["type"] = mismatch_type
    if is_resolved is not None:
        q["is_resolved"] = is_resolved
    docs = await db.mismatches.find(q).sort("created_at", -1).to_list(500)
    cname = {c["id"]: c["name"] for c in firm_clients}
    return {
        "count": len(docs),
        "mismatches": [{**_strip_id(d), "client_name": cname.get(d["client_id"], "—")} for d in docs]
    }


@api.post("/gst/mismatches/{mismatch_id}/resolve")
async def resolve_mismatch(mismatch_id: str, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    mm = await db.mismatches.find_one({"id": mismatch_id})
    if not mm:
        raise HTTPException(404, "Mismatch not found")
    c = await db.clients.find_one({"id": mm["client_id"], "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found or access denied")
    notes = payload.get("notes", "")
    resolved_by = payload.get("resolved_by", "ca_user")
    result = await db.mismatches.update_one(
        {"id": mismatch_id},
        {"$set": {
            "is_resolved": True,
            "resolution_notes": notes,
            "resolved_by": resolved_by,
            "resolved_at": _now().isoformat(),
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Mismatch not found")
    return {"status": "resolved", "id": mismatch_id}


# ---------- TDS ----------

@api.get("/tds/summary")
async def tds_summary(client_id: Optional[str] = None, fy: str = "2025-26", current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    firm_clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}, {"id": 1}).to_list(500)
    firm_client_ids = [c["id"] for c in firm_clients]
    q: Dict[str, Any] = {"financial_year": fy, "client_id": {"$in": firm_client_ids}}
    if client_id:
        if client_id not in firm_client_ids:
            return {"overall": {}, "quarterly": {}, "by_section": {}}
        q["client_id"] = client_id
    entries = await db.tds_entries.find(q).to_list(500)

    total_computed = sum(e["tds_amount"] for e in entries)
    total_deducted = sum(e["tds_deducted"] for e in entries)
    total_missed = total_computed - total_deducted
    total_penalty = sum(e.get("penalty_estimate", 0) for e in entries)
    missed_count = sum(1 for e in entries if e["missed_deduction"])

    # Quarterly
    quarters: Dict[str, Dict[str, float]] = {qtr: {"entries": 0, "computed": 0.0, "deducted": 0.0, "missed": 0.0, "penalty": 0.0} for qtr in ("Q1", "Q2", "Q3", "Q4")}
    for e in entries:
        qk = e["quarter"]
        if qk in quarters:
            quarters[qk]["entries"] += 1
            quarters[qk]["computed"] += e["tds_amount"]
            quarters[qk]["deducted"] += e["tds_deducted"]
            quarters[qk]["missed"] += (e["tds_amount"] - e["tds_deducted"])
            quarters[qk]["penalty"] += e.get("penalty_estimate", 0)

    # Section-wise
    by_section: Dict[str, Dict[str, float]] = {}
    for e in entries:
        sec = e["tds_section"]
        if sec not in by_section:
            by_section[sec] = {"count": 0, "computed": 0.0, "deducted": 0.0, "missed": 0.0}
        by_section[sec]["count"] += 1
        by_section[sec]["computed"] += e["tds_amount"]
        by_section[sec]["deducted"] += e["tds_deducted"]
        by_section[sec]["missed"] += (e["tds_amount"] - e["tds_deducted"])

    compliance_rate = round((total_deducted / max(total_computed, 1)) * 100, 2)

    return {
        "client_id": client_id,
        "financial_year": fy,
        "overall": {
            "entries": len(entries),
            "tds_computed": round(total_computed, 2),
            "tds_deducted": round(total_deducted, 2),
            "tds_missed": round(total_missed, 2),
            "penalty_estimate": round(total_penalty, 2),
            "missed_count": missed_count,
            "compliance_rate": compliance_rate,
        },
        "quarterly": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in quarters.items()},
        "by_section": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_section.items()},
    }


@api.get("/tds/missed")
async def tds_missed(client_id: Optional[str] = None, fy: str = "2025-26", current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    firm_clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}, {"id": 1, "name": 1}).to_list(500)
    firm_client_ids = [c["id"] for c in firm_clients]
    q: Dict[str, Any] = {"missed_deduction": True, "financial_year": fy, "client_id": {"$in": firm_client_ids}}
    if client_id:
        if client_id not in firm_client_ids:
            return {"count": 0, "entries": []}
        q["client_id"] = client_id
    entries = await db.tds_entries.find(q).sort("penalty_estimate", -1).to_list(500)
    cname = {c["id"]: c["name"] for c in firm_clients}
    return {
        "count": len(entries),
        "total_missed": round(sum(e["tds_amount"] for e in entries), 2),
        "total_penalty": round(sum(e.get("penalty_estimate", 0) for e in entries), 2),
        "entries": [{**_strip_id(e), "client_name": cname.get(e["client_id"], "—")} for e in entries],
    }


@api.get("/tds/vendors")
async def tds_vendors(client_id: Optional[str] = None, fy: str = "2025-26", current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    firm_clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}, {"id": 1}).to_list(500)
    firm_client_ids = [c["id"] for c in firm_clients]
    q: Dict[str, Any] = {"financial_year": fy, "client_id": {"$in": firm_client_ids}}
    if client_id:
        if client_id not in firm_client_ids:
            return {"count": 0, "vendors": []}
        q["client_id"] = client_id
    entries = await db.tds_entries.find(q).to_list(500)
    # Group by (vendor_pan, section)
    vendors: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        key = f"{e['vendor_pan']}::{e['tds_section']}"
        if key not in vendors:
            vendors[key] = {
                "vendor_pan": e["vendor_pan"],
                "vendor_name": e["vendor_name"],
                "tds_section": e["tds_section"],
                "total_payments": 0.0,
                "total_tds_computed": 0.0,
                "total_tds_deducted": 0.0,
                "payment_count": 0,
            }
        vendors[key]["total_payments"] += e["payment_amount"]
        vendors[key]["total_tds_computed"] += e["tds_amount"]
        vendors[key]["total_tds_deducted"] += e["tds_deducted"]
        vendors[key]["payment_count"] += 1
    rows = list(vendors.values())
    for r in rows:
        for f in ("total_payments", "total_tds_computed", "total_tds_deducted"):
            r[f] = round(r[f], 2)
        r["compliance_pct"] = round((r["total_tds_deducted"] / max(r["total_tds_computed"], 1)) * 100, 1)
    rows.sort(key=lambda x: x["total_payments"], reverse=True)
    return {"count": len(rows), "vendors": rows}


# ---------- Compliance ----------

@api.get("/compliance/calendar")
async def compliance_calendar(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    firm_clients = await db.clients.find({"ca_firm_id": current_user["firm_id"]}, {"id": 1, "name": 1}).to_list(500)
    firm_client_ids = [c["id"] for c in firm_clients]
    q: Dict[str, Any] = {"client_id": {"$in": firm_client_ids}}
    if client_id:
        if client_id not in firm_client_ids:
            return {"count": 0, "items": []}
        q["client_id"] = client_id
    if status:
        q["status"] = status
    items = await db.compliance_items.find(q).sort("due_date", 1).to_list(500)
    cname = {c["id"]: c["name"] for c in firm_clients}
    today = _now().date()
    enriched: List[Dict[str, Any]] = []
    for it in items:
        item = _strip_id(it)
        item["client_name"] = cname.get(item["client_id"], "—")
        try:
            dt = datetime.fromisoformat(item["due_date"].replace("Z", "+00:00"))
            item["days_to_due"] = (dt.date() - today).days
        except Exception:
            item["days_to_due"] = 0
        enriched.append(item)
    return {"count": len(enriched), "items": enriched}


@api.post("/compliance/{item_id}/mark-filed")
async def mark_filed(item_id: str, payload: Optional[Dict[str, Any]] = None, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    item = await db.compliance_items.find_one({"id": item_id})
    if not item:
        raise HTTPException(404, "Compliance item not found")
    c = await db.clients.find_one({"id": item["client_id"], "ca_firm_id": current_user["firm_id"]})
    if not c:
        raise HTTPException(404, "Client not found or access denied")
    filed_by = (payload or {}).get("filed_by", "ca_user")
    result = await db.compliance_items.update_one(
        {"id": item_id},
        {"$set": {
            "status": "filed",
            "filed_at": _now().isoformat(),
            "filed_by": filed_by,
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Compliance item not found")
    return {"status": "filed", "id": item_id}


# Mount router
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
