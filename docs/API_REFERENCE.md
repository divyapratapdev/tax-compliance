# API Reference — TaxPilot Dashboard

Base URL: `{REACT_APP_BACKEND_URL}/api`

All endpoints return JSON. All timestamps are ISO-8601 in UTC. All currency amounts are in INR rupees (not paise) as JavaScript numbers (max 9.007 × 10¹⁵ — safe for any realistic CA-firm dataset).

---

## Conventions

- **Auth:** None in MVP. Phase 2 will add `Authorization: Bearer <jwt>`.
- **Tenancy:** Single-firm demo. Multi-tenant cohort added via `ca_firm_id` derived from JWT in Phase 2.
- **Errors:** Standard HTTP codes + `{ "detail": "<message>" }` body. 4xx for client mistakes, 5xx for engine faults.
- **Idempotency:** Mutations are not yet idempotent — add `Idempotency-Key` header support in Phase 2.

---

## 1. Health & utility

### `GET /api/health`

```json
{ "status": "ok", "service": "taxpilot-dashboard", "timestamp": "2026-01-26T..." }
```

### `POST /api/seed/reset`

Wipes all collections and re-seeds demo data. Returns counts.

```json
{
  "status": "reseeded",
  "counts": { "firms": 1, "clients": 3, "documents": 6, "mismatches": 6, "tds_entries": 5, "compliance_items": 9 }
}
```

---

## 2. Profile

### `GET /api/profile`

Returns the current CA firm profile.

```json
{
  "id": "firm-demo-001",
  "name": "Kumar & Associates",
  "registration_number": "FRN-302345E",
  "email": "office@kumarca.in",
  "plan": "growth",
  "created_at": "...",
  "alert_preferences": {
    "whatsapp_enabled": true,
    "email_enabled": true,
    "reminder_7day": true,
    "reminder_1day": true,
    "escalation_on_missed": true
  }
}
```

### `PUT /api/settings/profile`

Body (any subset):
```json
{ "name": "...", "registration_number": "...", "email": "...", "plan": "starter|growth|scale" }
```
Returns the updated firm document.

### `PUT /api/settings/alerts`

Body — boolean flags:
```json
{
  "whatsapp_enabled": true,
  "email_enabled": true,
  "reminder_7day": true,
  "reminder_1day": false,
  "escalation_on_missed": true
}
```

---

## 3. Dashboard

### `GET /api/dashboard/summary`

Returns:

```json
{
  "kpis": {
    "total_clients": 3,
    "itc_at_risk": 48814.0,
    "missed_tds": 16300.0,
    "missed_penalty": 411.0,
    "upcoming_compliance": 8,
    "overdue_compliance": 1
  },
  "client_health": { "safe": 1, "at_risk": 1, "critical": 1 },
  "upcoming_deadlines": [
    {
      "id": "...",
      "client_id": "client-001",
      "client_name": "Acme Manufacturing Pvt Ltd",
      "type": "GSTR1",
      "description": "GSTR-1 for April 2025",
      "due_date": "...",
      "status": "pending",
      "days_to_due": 2,
      "penalty_per_day": 50
    }
  ],
  "top_missed_tds": [
    {
      "id": "...",
      "client_id": "...",
      "client_name": "...",
      "vendor_name": "Sharma & Co Chartered Accountants",
      "tds_section": "194J",
      "tds_amount": 8500.0,
      "penalty_estimate": 255.0
    }
  ]
}
```

---

## 4. Clients

### `GET /api/clients?search=&health=`

Query parameters:
- `search` (optional) — matches name, GSTIN, or PAN (case-insensitive)
- `health` (optional) — `safe | at_risk | critical`

```json
{
  "count": 3,
  "clients": [
    {
      "id": "client-001",
      "name": "Acme Manufacturing Pvt Ltd",
      "gstin": "27AABCA1234E1Z5",
      "pan": "AABCA1234E",
      "turnover_category": "medium",
      "registration_type": "regular",
      "industry": "Manufacturing",
      "health": "critical",
      "open_mismatches": 4,
      "missed_tds": 11800.0,
      "missed_penalty": 321.0,
      "upcoming_compliance": 3,
      "overdue_compliance": 1
    }
  ]
}
```

### `GET /api/clients/{client_id}`

Returns the single enriched client (404 if missing).

---

## 5. Documents

### `GET /api/documents?client_id=&status=`

```json
{
  "count": 6,
  "documents": [
    {
      "id": "uuid",
      "client_id": "client-001",
      "client_name": "Acme Manufacturing Pvt Ltd",
      "type": "bank_statement",
      "original_filename": "HDFC_Acme_Apr-2025.pdf",
      "ocr_status": "completed",
      "ocr_error": null,
      "extracted_count": 42,
      "uploaded_at": "...",
      "completed_at": "..."
    }
  ]
}
```

### `POST /api/documents/upload`

Multipart form:
- `client_id` (text) — required
- `doc_type` (text) — `bank_statement | invoice | gstr2a` — required
- `file` (file) — required, ≤ 10 MB, PDF/Excel/CSV/JPG/PNG

Returns the created document record (`ocr_status: "processing"`).

Errors:
- `400` — missing or invalid doc_type
- `413` — file too large

---

## 6. GST Reconciliation

### `GET /api/gst/reconciliation/summary?client_id=...&month=4&year=2025`

```json
{
  "client_id": "client-001",
  "period": { "month": 4, "year": 2025 },
  "summary": {
    "matched": 16,
    "by_type": {
      "missing_in_2a": 1,
      "amount_mismatch": 1,
      "gstin_mismatch": 1,
      "missing_in_books": 1
    },
    "total_mismatches": 4
  },
  "itc_summary": {
    "safe_to_claim":    { "amount": 72000.0, "invoice_count": 16 },
    "at_risk":          { "amount": 30154.0, "invoice_count": 3 },
    "missing_in_books": { "amount": 1900.0,  "invoice_count": 1 }
  }
}
```

### `GET /api/gst/mismatches?client_id=&mismatch_type=&is_resolved=`

`mismatch_type` ∈ `{missing_in_2a, missing_in_books, amount_mismatch, gstin_mismatch}`.

Returns:

```json
{
  "count": 6,
  "mismatches": [
    {
      "id": "uuid",
      "client_id": "...",
      "client_name": "...",
      "type": "missing_in_2a",
      "supplier_gstin": "27AABFS9876P1ZK",
      "supplier_name": "Sharma Electronics",
      "invoice_number": "INV-2026-0142",
      "invoice_date": "...",
      "books_amount": 47200.0,
      "gstr2a_amount": null,
      "difference": 47200.0,
      "books_tax": 7200.0,
      "suggested_action": "Follow up with supplier to file GSTR-1 for April 2025",
      "is_resolved": false
    }
  ]
}
```

### `POST /api/gst/mismatches/{mismatch_id}/resolve`

Body:
```json
{ "notes": "Followed up with supplier", "resolved_by": "ca_user" }
```
Returns `{ "status": "resolved", "id": "..." }`. 404 if not found.

---

## 7. TDS

### `GET /api/tds/summary?client_id=&fy=2025-26`

```json
{
  "client_id": null,
  "financial_year": "2025-26",
  "overall": {
    "entries": 5,
    "tds_computed": 46280.0,
    "tds_deducted": 29680.0,
    "tds_missed": 16600.0,
    "penalty_estimate": 411.0,
    "missed_count": 3,
    "compliance_rate": 64.13
  },
  "quarterly": {
    "Q1": { "entries": 5, "computed": 46280.0, "deducted": 29680.0, "missed": 16600.0, "penalty": 411.0 },
    "Q2": { "entries": 0, "computed": 0.0, "deducted": 0.0, "missed": 0.0, "penalty": 0.0 },
    "Q3": { "entries": 0, "computed": 0.0, "deducted": 0.0, "missed": 0.0, "penalty": 0.0 },
    "Q4": { "entries": 0, "computed": 0.0, "deducted": 0.0, "missed": 0.0, "penalty": 0.0 }
  },
  "by_section": {
    "194J": { "count": 3, "computed": 14680.0, "deducted": 1680.0, "missed": 13000.0 },
    "194C": { "count": 1, "computed": 3300.0,  "deducted": 0.0,    "missed": 3300.0 },
    "194I": { "count": 1, "computed": 28000.0, "deducted": 28000.0, "missed": 0.0 }
  }
}
```

### `GET /api/tds/missed?client_id=&fy=2025-26`

Returns all entries where `missed_deduction = true`, sorted by penalty descending.

### `GET /api/tds/vendors?client_id=&fy=2025-26`

Returns aggregated `(vendor_pan, tds_section)` groups with `total_payments`, `total_tds_computed`, `total_tds_deducted`, `compliance_pct`, and `payment_count`.

---

## 8. Compliance

### `GET /api/compliance/calendar?client_id=&status=`

`status` ∈ `{pending, filed, missed}`.

```json
{
  "count": 9,
  "items": [
    {
      "id": "uuid",
      "client_id": "client-001",
      "client_name": "Acme Manufacturing Pvt Ltd",
      "type": "GSTR1",
      "description": "GSTR-1 for April 2025",
      "due_date": "2026-01-28T00:00:00+00:00",
      "status": "pending",
      "filed_at": null,
      "penalty_per_day": 50,
      "penalty_description": "₹50/day late fee u/s 47 CGST",
      "reminder_7day_sent": true,
      "reminder_1day_sent": false,
      "days_to_due": 2
    }
  ]
}
```

### `POST /api/compliance/{item_id}/mark-filed`

Body (optional):
```json
{ "filed_by": "ca_user" }
```
Returns `{ "status": "filed", "id": "..." }`. 404 if not found.

---

## 9. Error model

All errors return:
```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning                                  |
| ------ | ---------------------------------------- |
| 400    | Bad request (missing / invalid params)   |
| 404    | Resource not found                       |
| 413    | Payload too large                        |
| 500    | Internal server error                    |

---

## 10. Rate limits (planned, Phase 2)

- 60 requests/min per IP (anonymous)
- 600 requests/min per authenticated firm
- `429 Too Many Requests` with `Retry-After` header

---

## 11. Versioning

Phase 2 introduces `/api/v1/...` versioning with a 12-month deprecation policy for breaking changes. Today's endpoints will be aliased under `/api/v1/` automatically.
