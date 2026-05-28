import os
from typing import List, Dict, Any, Tuple
from datetime import datetime
import motor.motor_asyncio
from pydantic import BaseModel

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "taxpilot")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

def normalize_invoice_number(inv: str) -> str:
    if not inv: return ""
    return ''.join(e for e in inv if e.isalnum()).upper().lstrip('0')

async def reconcile_gst_period(client_id: str, firm_id: str, month: int, year: int) -> Dict[str, Any]:
    """
    Core GST Reconciliation Engine.
    Matches books (purchase register) against portal (GSTR-2B).
    """
    # 1. Fetch data
    books_cursor = db.purchase_register.find({
        "client_id": client_id,
        "ca_firm_id": firm_id,
        "period_month": month,
        "period_year": year
    })
    portal_cursor = db.gstr2b_data.find({
        "client_id": client_id,
        "ca_firm_id": firm_id,
        "period_month": month,
        "period_year": year
    })

    books = await books_cursor.to_list(length=None)
    portal = await portal_cursor.to_list(length=None)

    # 2. Index GSTR-2B for fast lookup
    # Key: (supplier_gstin, normalized_invoice_number)
    portal_index = {}
    for p in portal:
        key = (p.get("supplier_gstin", "").strip().upper(), normalize_invoice_number(p.get("invoice_number", "")))
        portal_index[key] = p

    mismatches = []
    matched_itc = 0.0
    blocked_itc = 0.0
    partial_itc = 0.0

    # 3. Match Books against Portal
    for b in books:
        key = (b.get("supplier_gstin", "").strip().upper(), normalize_invoice_number(b.get("invoice_number", "")))
        books_tax = float(b.get("total_tax", 0))

        if key in portal_index:
            p = portal_index[key]
            portal_tax = float(p.get("total_tax", 0))
            diff = abs(books_tax - portal_tax)
            
            if diff <= 1.0: # Tolerance of 1 rupee
                matched_itc += books_tax
            else:
                blocked_itc += max(0, books_tax - portal_tax)
                partial_itc += min(books_tax, portal_tax)
                mismatches.append({
                    "type": "amount_mismatch",
                    "supplier_gstin": key[0],
                    "supplier_name": b.get("supplier_name", ""),
                    "invoice_number": b.get("invoice_number", ""),
                    "books_tax": books_tax,
                    "portal_tax": portal_tax,
                    "difference": round(diff, 2)
                })
            # Remove from index so we can find MISSING_IN_BOOKS later
            del portal_index[key]
        else:
            # MISSING IN GSTR-2B
            blocked_itc += books_tax
            mismatches.append({
                "type": "missing_in_2b",
                "supplier_gstin": key[0],
                "supplier_name": b.get("supplier_name", ""),
                "invoice_number": b.get("invoice_number", ""),
                "books_tax": books_tax,
                "portal_tax": 0,
                "difference": round(books_tax, 2)
            })

    # 4. Check remaining portal entries (MISSING_IN_BOOKS)
    for key, p in portal_index.items():
        portal_tax = float(p.get("total_tax", 0))
        mismatches.append({
            "type": "missing_in_books",
            "supplier_gstin": key[0],
            "supplier_name": p.get("supplier_name", ""),
            "invoice_number": p.get("invoice_number", ""),
            "books_tax": 0,
            "portal_tax": portal_tax,
            "difference": round(portal_tax, 2)
        })

    total_books = len(books)
    matched_count = total_books - len([m for m in mismatches if m["type"] in ["missing_in_2b", "amount_mismatch"]])
    
    # Identify top defaulting suppliers
    supplier_defaults = {}
    for m in mismatches:
        if m["type"] == "missing_in_2b":
            gstin = m["supplier_gstin"]
            if gstin not in supplier_defaults:
                supplier_defaults[gstin] = {"supplier_name": m["supplier_name"], "missing_invoices": 0, "blocked_itc": 0.0}
            supplier_defaults[gstin]["missing_invoices"] += 1
            supplier_defaults[gstin]["blocked_itc"] += m["books_tax"]

    action_items = sorted(
        [{"supplier_gstin": k, **v} for k, v in supplier_defaults.items()],
        key=lambda x: x["blocked_itc"],
        reverse=True
    )

    return {
        "summary": {
            "itc_claimable": round(matched_itc + partial_itc, 2),
            "itc_blocked": round(blocked_itc, 2),
            "match_rate_percent": round((matched_count / total_books * 100) if total_books > 0 else 100, 2),
            "supplier_default_count": len(supplier_defaults),
            "action_items": action_items[:5] # Top 5
        },
        "mismatches": mismatches
    }
