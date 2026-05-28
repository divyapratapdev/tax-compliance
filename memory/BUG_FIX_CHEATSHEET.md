# TaxPilot — Quick Bug Cheat-Sheet (v9 → v10 patch guide)

Companion to `/app/memory/EVALUATION.md`. This is the file you copy-paste fixes from.

---

## 🔴 BUG #1 — TDS Quarter date range crashes for Q1, Q2

**File:** `app/tds/tds_engine.py`
**Method:** `_get_quarter_date_range`
**Why:** `datetime(year, 6, 31)` and `datetime(year, 9, 31)` raise `ValueError` because June and September have 30 days, not 31. Q1 (Apr-Jun) and Q2 (Jul-Sep) both crash.

**Reproduce:**
```python
from app.tds.tds_engine import TDSEngine
TDSEngine()._get_quarter_date_range('2025-26', 'Q2')
# ValueError: day is out of range for month
```

**Fix — replace the method body with:**
```python
def _get_quarter_date_range(self, fy: str, quarter: str):
    import calendar
    start_year = int(fy.split("-")[0])
    quarter_months = {"Q1": (4, 6), "Q2": (7, 9), "Q3": (10, 12), "Q4": (1, 3)}
    start_month, end_month = quarter_months.get(quarter, (4, 6))
    if quarter == "Q4":
        start_year += 1
    last_day = calendar.monthrange(start_year, end_month)[1]
    return (
        datetime(start_year, start_month, 1),
        datetime(start_year, end_month, last_day, 23, 59, 59),
    )
```

---

## 🔴 BUG #2 — `process_invoice` violates NOT NULL constraints

**File:** `main.py`
**Function:** `process_invoice` (lines 306-353)
**Why:**
1. `GSTInvoice.period_month` and `period_year` are NOT NULL but you never set them.
2. You pass `vendor_gstin=...` to `GSTInvoice(...)` — but the model column is `supplier_gstin`. SQLAlchemy will raise `TypeError`.
3. `invoice_date` is NOT NULL but OCR may return `None`.

**Reproduce:** Upload any invoice via `POST /ingest/invoice` and check logs.

**Fix — replace the function:**
```python
def process_invoice(doc_id, storage_path, file_ext, client_id, period_month=None, period_year=None):
    db = SessionLocal()
    try:
        ocr = InvoiceOCR()
        invoice_data = ocr.process_pdf(storage_path) if file_ext == '.pdf' else ocr.process_image(storage_path)

        inv_date = invoice_data.get("invoice_date") or datetime.utcnow()
        gstin    = invoice_data.get("vendor_gstin")  or ""
        inv_no   = invoice_data.get("invoice_number") or f"OCR_FAIL_{doc_id[:8]}"

        # Default period from invoice date or now
        period_month = period_month or inv_date.month
        period_year  = period_year  or inv_date.year

        gst_invoice = GSTInvoice(
            id=str(uuid.uuid4()),
            client_id=client_id,
            document_id=doc_id,
            source="uploaded",
            supplier_gstin=gstin,                       # ← was vendor_gstin (wrong name)
            supplier_name=invoice_data.get("vendor_name") or "Unknown",
            invoice_number=inv_no,
            invoice_date=inv_date,
            taxable_amount=invoice_data.get("taxable_amount", 0),
            cgst=invoice_data.get("cgst", 0),
            sgst=invoice_data.get("sgst", 0),
            igst=invoice_data.get("igst", 0),
            total_amount=invoice_data.get("total", 0),
            total_tax=(invoice_data.get("cgst", 0)
                       + invoice_data.get("sgst", 0)
                       + invoice_data.get("igst", 0)),
            period_month=period_month,                  # ← was missing
            period_year=period_year,                    # ← was missing
            reconciliation_status="pending",
        )
        db.add(gst_invoice)

        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.ocr_status = "completed"
            doc.ocr_completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Processed invoice {doc_id}: {gstin} / {inv_no}")
    except Exception as e:
        logger.error(f"Failed to process invoice {doc_id}: {e}")
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.ocr_status = "failed"
            doc.ocr_error = str(e)[:500]
        db.commit()
    finally:
        db.close()
```

And update the `/ingest/invoice` route signature + `background_tasks.add_task` call to pass `period_month` and `period_year` query params (optional).

---

## 🔴 BUG #3 — Invoice number normalisation over-strips

**File:** `app/gst/reconciliation_engine.py`
**Method:** `_normalize_invoice_number`
**Why:** The regex `(20)?[0-9]{2}[-/]?(20)?[0-9]{2}$` and `[-/]?(20)?[0-9]{4}$` strip any 4-digit suffix, collapsing `INV1234` → `INV` and merging unrelated invoices.

**Reproduce:**
```python
from app.gst.reconciliation_engine import GSTReconciliationEngine
e = GSTReconciliationEngine()
print(e._normalize_invoice_number("INV1234"))   # 'INV' ← bug
print(e._normalize_invoice_number("INV/2025-26/0007"))   # 'INV' ← bug
```

**Fix — replace the method:**
```python
def _normalize_invoice_number(self, inv_no: str) -> str:
    if not inv_no:
        return ""
    normalized = inv_no.upper()
    for ch in ["/", "-", "\\", "_", "#", "@", "$", "%", "&", "*", " "]:
        normalized = normalized.replace(ch, "")
    # Strip leading zeros only at very start
    normalized = normalized.lstrip("0")
    # Strip ONLY clearly FY-shaped suffixes: e.g. "FY2425", "2025-26", "FY25"
    import re
    normalized = re.sub(r"FY?(20)?\d{2}(20)?\d{2}$", "", normalized)
    normalized = re.sub(r"FY\d{2,4}$", "", normalized)
    # Safety: if we stripped too much, keep at least 3 chars of core ID
    if len(normalized) < 3:
        return inv_no.upper().replace(" ", "")
    return normalized.strip()
```

Also add a minimum-length guard at the top of `_pattern_match`:
```python
if len(books_inv_norm) < 3:
    return None  # too short to match safely, fall through to MISSING_IN_2A
```

---

## 🟠 BUG #4 — Migration 004 chain broken

**File:** `migrations/004_add_compliance_table.py`

```python
# Change:
revision      = "004"
down_revision = "003"
# To:
revision      = "004_add_compliance_table"
down_revision = "003_add_tds_tables"
```

---

## 🟠 BUG #5 — TDS compute silently skips unreviewed transactions

**File:** `app/tds/tds_engine.py` line 154

```python
# Change:
models.Transaction.is_reviewed == True
# To: (remove the filter entirely OR add a count to response)
```

And in the return payload of `compute_tds_for_client`, add:
```python
"transactions_skipped_pending_review": len([t for t in transactions if not t.is_reviewed]),
```

---

## 🟠 BUG #6 — PAN over-extraction

**File:** `app/tds/tds_engine.py` line 432

```python
# Change:
match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', narration.upper())
# To: only accept PAN after an explicit marker
match = re.search(r'\bPAN\s*[:\-]?\s*([A-Z]{5}\d{4}[A-Z])\b', narration.upper())
if match:
    return match.group(1)
```

---

## 🟠 BUG #7 — `return_generator.py` bogus query + wrong income cats

**File:** `app/returns/return_generator.py`

Replace the query block (lines 259-269) with:
```python
txns = (
    db.query(Transaction)
    .filter(
        Transaction.client_id == client_id,
        Transaction.date >= from_dt,
        Transaction.date <= to_dt,
    )
    .all()
)
```

Replace `_INCOME_CATS = {"interest_income", "upi_transfer", "neft_rtgs"}` with `_INCOME_CATS = {"interest_income"}` and rely on `txn.type == "credit"` as primary income signal.

---

## 🟡 Hygiene fixes (do in same patch)

1. Remove `Base.metadata.create_all(bind=engine)` from `main.py` line 30 once Alembic chain is healthy.
2. `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000","https://yourdomain.com"], ...)` — remove the `*` + `credentials=True` combo.
3. Move TAN/PAN out of query params on `/v1/tds/26q/{client_id}` and fetch from the Client record.
4. Add `if __name__ == "__main__": start_scheduler()` guard so multi-worker uvicorn doesn't multi-fire.
5. Rename folder `taxpilot_v6` → `taxpilot` (drop version from folder name).
6. Pick ONE URL prefix (`/api/v1/`) and migrate the old `/ingest/`, `/v1/gst/`, `/v1/tds/` routes.

---

## 🟢 Verification script (run after patches)

Save as `verify_v10.py`:

```python
"""Smoke test for v10 patches."""
import os
os.environ["USE_SQLITE"] = "true"

# 1. Imports cleanly
import main
print("[OK] Import")

# 2. Quarter ranges all valid
from app.tds.tds_engine import TDSEngine
e = TDSEngine()
for q in ["Q1", "Q2", "Q3", "Q4"]:
    r = e._get_quarter_date_range("2025-26", q)
    print(f"[OK] {q} → {r[0].date()} to {r[1].date()}")

# 3. Invoice normalisation preserves IDs
from app.gst.reconciliation_engine import GSTReconciliationEngine
g = GSTReconciliationEngine()
assert g._normalize_invoice_number("INV1234") != "INV", "Over-stripped!"
assert g._normalize_invoice_number("INV/2025-26") == "INV"
print("[OK] Invoice normalisation")

# 4. PAN extraction restricted
assert e._extract_pan_from_narration("IMPS/AXISH3450K/TXN") is None
assert e._extract_pan_from_narration("Vendor PAN: ABCDE1234F payment") == "ABCDE1234F"
print("[OK] PAN extraction")

print("\nAll patches verified ✅")
```

Run: `python verify_v10.py`

---

## Order of operations

1. Apply Bugs 1-3 (crash bugs) → app no longer crashes on real workflows.
2. Apply Bug 4 (migration chain) → DB can be migrated cleanly.
3. Apply Bugs 5-7 (silent bugs) → output is correct.
4. Apply hygiene fixes → app is ready for first demo.
5. Tag v10. Update README.
6. Build the React dashboard. (Separate session.)
