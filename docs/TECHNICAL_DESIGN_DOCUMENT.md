# Technical Design Document — TaxPilot Dashboard

| Field             | Value                                     |
| ----------------- | ----------------------------------------- |
| Version           | 1.0                                       |
| Last updated      | January 2026                              |
| Status            | Implemented (MVP)                         |
| Audience          | Engineering · Architecture review         |

---

## 1. Scope of this document

This TDD covers the **TaxPilot Dashboard** layer (this repository): a React 19 + FastAPI + MongoDB system that provides multi-tenant, CA-firm-facing dashboards over the TaxPilot v9 compliance engine.

Out of scope (covered in separate engine TDD): OCR pipeline, ML categorisation training, 3-pass reconciliation algorithm internals, 26Q XML schema generation — all of which live in `/app/taxpilot/taxpilot_v6/` (Python, MySQL).

## 2. High-level architecture

```
                  ┌──────────────────────────────────────────────────────┐
   CA Partner ───►│  React 19 SPA (Tailwind, shadcn/ui, lucide-react)    │
                  │  · 7 pages, single-tenant client switcher            │
                  │  · axios baseURL = REACT_APP_BACKEND_URL/api         │
                  └─────────────────────┬────────────────────────────────┘
                                        │ HTTPS / JSON
                                        ▼
                  ┌──────────────────────────────────────────────────────┐
                  │  FastAPI Gateway (this repo, /backend/server.py)     │
                  │  · /api/* router                                     │
                  │  · CORS, rate-limit (planned), JWT (planned)         │
                  │  · Aggregations / projections for dashboard          │
                  │  · Idempotent seed for demo data                     │
                  └─────────────────────┬────────────────────────────────┘
                                        │
            ┌───────────────────────────┼────────────────────────────────┐
            ▼                                                             ▼
  ┌──────────────────┐                              ┌──────────────────────────┐
  │  MongoDB 7       │                              │  TaxPilot v9 Engine      │
  │  (multi-tenant)  │                              │  (Python, MySQL — async  │
  │  collections:    │                              │   workers, OCR, ML)      │
  │   firms          │   ⇆ contract-compatible      │  · ingestion             │
  │   clients        │     response shapes          │  · categorisation        │
  │   documents      │                              │  · reconciliation        │
  │   mismatches     │                              │  · TDS engine            │
  │   tds_entries    │                              │  · compliance scheduler  │
  │   compliance_*   │                              │                          │
  └──────────────────┘                              └──────────────────────────┘
```

### Why two stores?

- **MongoDB** for the dashboard layer = flexible projections, fast aggregations for KPIs, document-native (mismatches, compliance items vary in shape per client).
- **MySQL** for the engine layer = strict typed transactions, ACID guarantees for compute that touches money (TDS amounts, 26Q numbers), already battle-tested in v9.

The two stores are bridged via the dashboard API: the dashboard either reads its own demo/cached projections (today) or proxies to the engine's `/api/v1/*` endpoints (production). This is the key design decision that lets the dashboard ship now and the engine plug in later without UI changes.

## 3. Data model — MongoDB

All collections are scoped by `ca_firm_id` (multi-tenant). Indexes are noted under each collection.

### 3.1 `firms`
```json
{
  "id": "firm-demo-001",
  "name": "Kumar & Associates",
  "registration_number": "FRN-302345E",
  "email": "office@kumarca.in",
  "plan": "growth",
  "alert_preferences": {
    "whatsapp_enabled": true,
    "email_enabled": true,
    "reminder_7day": true,
    "reminder_1day": true,
    "escalation_on_missed": true
  },
  "created_at": "ISO-8601 string"
}
```
Indexes: `{ id: 1, unique: true }`, `{ email: 1, unique: true }`.

### 3.2 `clients`
```json
{
  "id": "client-001",
  "ca_firm_id": "firm-demo-001",
  "name": "Acme Manufacturing Pvt Ltd",
  "gstin": "27AABCA1234E1Z5",
  "pan": "AABCA1234E",
  "turnover_category": "small | medium | large",
  "registration_type": "regular | composition | unregistered",
  "industry": "string",
  "created_at": "ISO-8601 string"
}
```
Indexes: `{ ca_firm_id: 1, id: 1 }`, `{ gstin: 1, ca_firm_id: 1, unique: true }`.

### 3.3 `documents`
```json
{
  "id": "uuid",
  "client_id": "client-001",
  "type": "bank_statement | invoice | gstr2a",
  "original_filename": "...",
  "ocr_status": "processing | completed | failed",
  "ocr_error": "string | null",
  "extracted_count": 42,
  "uploaded_at": "...",
  "completed_at": "... | null"
}
```
Indexes: `{ client_id: 1, uploaded_at: -1 }`, `{ ocr_status: 1, uploaded_at: -1 }`.

### 3.4 `mismatches`
```json
{
  "id": "uuid",
  "client_id": "client-001",
  "type": "missing_in_2a | missing_in_books | amount_mismatch | gstin_mismatch",
  "supplier_gstin": "...",
  "supplier_name": "...",
  "invoice_number": "...",
  "invoice_date": "ISO-8601",
  "books_amount": 47200.00,
  "gstr2a_amount": null,
  "difference": 47200.00,
  "books_tax": 7200.00,
  "suggested_action": "...",
  "is_resolved": false,
  "resolution_notes": null,
  "period_month": 4,
  "period_year": 2025
}
```
Indexes: `{ client_id: 1, is_resolved: 1, period_year: -1, period_month: -1 }`.

### 3.5 `tds_entries`
```json
{
  "id": "uuid",
  "client_id": "client-001",
  "vendor_pan": "ABCPS1234A",
  "vendor_name": "...",
  "payment_date": "...",
  "payment_amount": 85000,
  "tds_section": "194J",
  "tds_rate": 10.0,
  "tds_amount": 8500,
  "tds_deducted": 0,
  "is_deducted": false,
  "missed_deduction": true,
  "penalty_estimate": 255,
  "months_delayed": 3,
  "financial_year": "2025-26",
  "quarter": "Q1"
}
```
Indexes: `{ client_id: 1, financial_year: 1, quarter: 1 }`, `{ missed_deduction: 1, penalty_estimate: -1 }`.

### 3.6 `compliance_items`
```json
{
  "id": "uuid",
  "client_id": "client-001",
  "type": "GSTR1 | GSTR3B | TDS_RETURN | TDS_PAYMENT | ADVANCE_TAX | ITR | ROC",
  "due_date": "ISO-8601",
  "description": "...",
  "status": "pending | filed | missed",
  "filed_at": "... | null",
  "penalty_per_day": 50,
  "penalty_description": "₹50/day late fee u/s 47 CGST",
  "reminder_7day_sent": true,
  "reminder_1day_sent": false
}
```
Indexes: `{ client_id: 1, due_date: 1 }`, `{ status: 1, due_date: 1 }`.

## 4. API surface

All endpoints under `/api`. See `API_REFERENCE.md` for full request/response payloads. Summary:

| Resource          | Endpoints                                                              |
| ----------------- | ---------------------------------------------------------------------- |
| Profile           | `GET /profile`, `PUT /settings/profile`, `PUT /settings/alerts`        |
| Dashboard         | `GET /dashboard/summary`                                               |
| Clients           | `GET /clients`, `GET /clients/{id}`                                    |
| Documents         | `GET /documents`, `POST /documents/upload`                             |
| GST Recon         | `GET /gst/reconciliation/summary`, `GET /gst/mismatches`, `POST /gst/mismatches/{id}/resolve` |
| TDS               | `GET /tds/summary`, `GET /tds/missed`, `GET /tds/vendors`             |
| Compliance        | `GET /compliance/calendar`, `POST /compliance/{id}/mark-filed`        |
| Utility           | `GET /health`, `POST /seed/reset`                                      |

## 5. Frontend architecture

```
/frontend/src/
├── App.js                          # Router, shell mount, profile fetch
├── lib/
│   ├── api.js                      # axios instance + endpoint wrappers
│   └── format.js                   # Indian INR/date formatters
├── components/
│   ├── Sidebar.jsx                 # Dark navy nav, 7 links
│   ├── Topbar.jsx                  # Client switcher + user chip
│   ├── ClientContext.jsx           # Global selected-client state
│   ├── KPICard.jsx                 # 4-tone KPI tile
│   ├── PageHeader.jsx              # H1 + subtitle + actions row
│   ├── StatusBadge.jsx             # Semantic pills (safe/warning/danger/info)
│   └── EmptyState.jsx              # Friendly zero-data card
└── pages/
    ├── Dashboard.jsx               # KPI strip + 2-column main area
    ├── Clients.jsx                 # Table with search + health filters
    ├── Documents.jsx               # Dropzone + processing queue
    ├── GSTReconciliation.jsx       # ITC cards + mismatch table
    ├── TDSAlerts.jsx               # Hero alert + missed table + vendor table
    ├── Compliance.jsx              # Grouped sections (overdue/today/week/30/later/filed)
    └── Settings.jsx                # Firm profile + alert toggles
```

### Design tokens

- **Fonts** — Cabinet Grotesk (headings, via Fontshare) + IBM Plex Sans (body) + IBM Plex Mono (numerics)
- **Colors** — Deep Navy `#0B2B5B` (brand) · Slate (neutrals) · Red/Amber/Green/Sky (semantic)
- **Density** — Tables `py-3 px-4`, KPI cards `p-6`, full layout `p-8`
- **Numerics** — `font-variant-numeric: tabular-nums` everywhere, `Intl.NumberFormat('en-IN')` (lakhs/crores grouping)

### Cross-cutting

- **Routing:** `react-router-dom` v7
- **State:** Hook-local + `ClientContext` for selected client across pages
- **Data fetch:** axios in `useEffect`; no SWR/React-Query yet (KISS for MVP, add when staleness becomes a pain)
- **Error/empty/loading:** every page has all 3 states
- **`data-testid`:** every interactive + critical-info element (per Emergent guidelines)

## 6. Sequence diagrams

### 6.1 Dashboard load

```
React (Dashboard.jsx)        FastAPI               MongoDB
       │                       │                      │
       │  GET /api/dashboard/summary                  │
       │──────────────────────►│                      │
       │                       │  find clients        │
       │                       │─────────────────────►│
       │                       │ ◄────────────────────│
       │                       │  aggregate mismatches│
       │                       │─────────────────────►│
       │                       │ ◄────────────────────│
       │                       │  aggregate tds       │
       │                       │─────────────────────►│
       │                       │ ◄────────────────────│
       │                       │  upcoming compliance │
       │                       │─────────────────────►│
       │                       │ ◄────────────────────│
       │ ◄──────────────────── │ kpis + alerts        │
       │ renders KPI strip + 2-column area            │
```

### 6.2 GST mismatch resolution

```
React            FastAPI            MongoDB
  │   GET /gst/mismatches?client_id=X&is_resolved=false
  │──────────────►│                    │
  │              │ find(...)           │
  │              │────────────────────►│
  │              │ ◄───────────────────│
  │ ◄────────────│ mismatches list     │
  │  user clicks "Resolve"
  │   POST /gst/mismatches/{id}/resolve
  │──────────────►│                    │
  │              │ updateOne(...)      │
  │              │────────────────────►│
  │              │ ◄───────────────────│
  │ ◄────────────│ {status: resolved}  │
  │  optimistic remove from local state
```

## 7. Non-functional requirements

| Concern         | Target                                                       | Status |
| --------------- | ------------------------------------------------------------ | ------ |
| TTFB            | < 200 ms p95                                                 | OK (Mongo + small payloads) |
| Page load (FCP) | < 1.5 s on 4G                                                | OK (small JS bundle, no images) |
| Time to interact| < 2.5 s                                                      | OK |
| API uptime SLA  | 99.5% (Tier-1 — paid tier)                                  | TBD — multi-region in Phase 2 |
| Data retention  | 7 years (Indian tax retention law)                           | TBD — cold-storage to S3-IA |
| Backups         | Daily snapshot, 30-day rolling                               | TBD (managed MongoDB Atlas) |
| Encryption      | TLS 1.3 in transit · AES-256 at rest                         | TBD (Atlas default) |
| Audit log       | Every state change (mismatch resolution, mark-filed, profile change) | Planned |

## 8. Scaling assumptions

| Tier              | Firms | Clients/firm | Mismatches/month | Storage / yr      |
| ----------------- | ----- | ------------ | ---------------- | ----------------- |
| MVP (today)       | 10    | 5            | 20               | < 1 GB            |
| Year-1            | 100   | 20           | 50               | 25 GB             |
| Year-2            | 500   | 30           | 80               | 250 GB            |
| Year-3            | 2,000 | 40           | 100              | 2 TB              |

At Year-2 scale: MongoDB Atlas M30 (~₹16k/mo) handles comfortably; FastAPI horizontally scaled to 3-4 nodes behind a single load balancer.

## 9. Open technical questions

1. **JWT vs Emergent Google OAuth** for auth — final pick in next iteration; current dashboard is unauthenticated (acceptable for demo only).
2. **Audit log** — separate collection vs change-stream? Lean towards change-stream once we move to Atlas.
3. **Engine bridge** — REST call vs Kafka event-stream? REST for MVP, evaluate Kafka when reconciliation runs go > 1 minute.
4. **PDF generation** — keep ReportLab (Python engine) or render server-side via Puppeteer? ReportLab wins on dependency footprint.

## 10. Decision log

| Date       | Decision                                          | Rationale                                                    |
| ---------- | ------------------------------------------------- | ------------------------------------------------------------ |
| Jan 2026   | Build dashboard on MongoDB, keep engine on MySQL  | Time-to-pilot > schema purity. Bridge contracts cleanly.     |
| Jan 2026   | Cabinet Grotesk + IBM Plex Sans                   | Distinctive without being decorative. Plex Mono = trust signal for numbers. |
| Jan 2026   | Deep navy + Swiss density (not startup gradients) | CA partners are conservative buyers. Visual conservatism = trust. |
| Jan 2026   | No auth in MVP                                    | Demo-first. Auth = Phase 2 priority #1 before any real customer data. |
