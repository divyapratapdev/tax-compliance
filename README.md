# TaxPilot

> AI-powered compliance engine for Indian Chartered Accountant firms.
> One senior CA manages the work that previously required ten juniors.

[![Status](https://img.shields.io/badge/status-MVP-blue)]() [![Stack](https://img.shields.io/badge/stack-React%20%2B%20FastAPI%20%2B%20MongoDB-success)]() [![License](https://img.shields.io/badge/license-Proprietary-red)]()

TaxPilot automates the entire junior-CA pipeline for Indian compliance work:

1. **Document ingestion** — Bank statements (PDF/Excel/CSV) and GST invoices (PDF/image) parsed via Tesseract OCR + Indian bank format auto-detection.
2. **Transaction categorisation** — Hybrid rules + scikit-learn TF-IDF/LinearSVC classifier trained on Indian bank narrations. 97% F1 on benchmark.
3. **GST reconciliation** — 3-pass matcher (Exact / Pattern-fuzzy / GSTIN-PAN logic) producing ITC-safe / ITC-at-risk / Missing-in-books buckets.
4. **TDS computation** — 35+ sections (192, 194A/B/C/H/I/J etc.), single & aggregate thresholds, vendor cumulative tracking, missed-deduction penalty estimator, Form 26Q export.
5. **Compliance calendar** — Auto-generated deadline calendar (GSTR-1/3B, 26Q, Advance Tax, ITR, ROC) with 7-day & 1-day WhatsApp + email reminders.
6. **Draft return preparation** — GSTR-3B JSON prefill, 26Q XML, P&L PDF.

This repository contains:

- **`/backend`** — FastAPI dashboard API (MongoDB) — the data plane consumed by the React UI.
- **`/frontend`** — React 19 + Tailwind + shadcn/ui dashboard (7 pages) — the surface CAs see daily.
- **`/app/taxpilot/taxpilot_v6/`** — The original Python compliance engine (v9 code, MySQL) — pluggable behind the dashboard via env switch.
- **`/docs`** — Production-grade documentation (PRD, TDD, API, Security & Compliance, Deployment, Roadmap).

---

## Quick Start

```bash
# Backend (FastAPI + MongoDB) — auto-seeds demo data on first start
cd backend && pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Frontend (React + Tailwind)
cd frontend && yarn install && yarn start
```

Demo data: 1 CA firm "Kumar & Associates", 3 client companies (Acme Manufacturing, Bharat Tech Services, Sunrise Retail), 6 documents, 6 GST mismatches, 5 TDS entries, 9 compliance items. Reset any time via the sidebar.

## Architecture

```
┌─────────────────┐   HTTPS    ┌──────────────────┐
│  React Dashboard│ ─────────► │  FastAPI Gateway │
│  (Vercel/Netlify)            │  (this repo)     │
└─────────────────┘            └────────┬─────────┘
                                        │
                                        ▼
                          ┌─────────────────────────┐
                          │ MongoDB (multi-tenant)  │
                          │   firms, clients,       │
                          │   documents, mismatches │
                          │   tds_entries,          │
                          │   compliance_items      │
                          └─────────────────────────┘
                                        │ (planned wire)
                                        ▼
                          ┌─────────────────────────┐
                          │ TaxPilot v9 Engine      │
                          │ (Python, MySQL)         │
                          │ OCR + ML + Recon + TDS  │
                          └─────────────────────────┘
```

The dashboard's data contracts mirror the v9 engine's response shapes, so swapping the demo MongoDB layer for the production engine is a query-router change, not a UI rewrite.

## Pages

| Page                    | Path                       | Purpose                                                    |
| ----------------------- | -------------------------- | ---------------------------------------------------------- |
| Executive Dashboard     | `/`                        | KPIs, top alerts, upcoming deadlines                       |
| Clients                 | `/clients`                 | Searchable client table with health badges                 |
| Documents               | `/documents`               | Drag-drop upload + OCR queue                               |
| GST Reconciliation      | `/gst-reconciliation`      | ITC summary + 3-pass mismatch table                        |
| TDS Alerts              | `/tds-alerts`              | Missed deductions, vendor cumulative, Form 26Q export      |
| Compliance Calendar     | `/compliance`              | Statutory deadlines grouped by urgency                     |
| Settings                | `/settings`                | Firm profile, alert preferences, security card             |

## Tech Stack

| Layer          | Technology                                                              |
| -------------- | ----------------------------------------------------------------------- |
| Frontend       | React 19, React Router 7, Tailwind 3.4, shadcn/ui, lucide-react, recharts |
| Backend (API)  | FastAPI 0.110, Pydantic 2, Motor (async MongoDB driver)                 |
| Engine (v9)    | Python 3.11, scikit-learn, Tesseract OCR, pdfplumber, MySQL 8 + SQLAlchemy |
| Datastore      | MongoDB 7 (dashboard) · MySQL 8 (engine)                                |
| Auth (planned) | JWT + Emergent Google Sign-In                                           |
| Deployment     | Docker Compose · Hetzner CX32 VPS · Nginx · Certbot                     |
| CI             | GitHub Actions                                                          |

## Documentation Map

| Document                                                                       | What it covers                                       |
| ------------------------------------------------------------------------------ | ---------------------------------------------------- |
| [`docs/PRODUCT_REQUIREMENTS_DOCUMENT.md`](docs/PRODUCT_REQUIREMENTS_DOCUMENT.md) | Vision, ICP, jobs-to-be-done, features, success metrics |
| [`docs/TECHNICAL_DESIGN_DOCUMENT.md`](docs/TECHNICAL_DESIGN_DOCUMENT.md)         | Architecture, data model, sequence diagrams, scaling |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)                                 | Every endpoint with request/response examples         |
| [`docs/SECURITY_AND_COMPLIANCE.md`](docs/SECURITY_AND_COMPLIANCE.md)             | DPDP Act 2023, ISO 27001 roadmap, audit log design   |
| [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)                           | Docker, VPS, CI/CD, observability                    |
| [`docs/12_MONTH_ROADMAP.md`](docs/12_MONTH_ROADMAP.md)                           | Phased plan, milestones, hiring                      |
| [`memory/EVALUATION.md`](memory/EVALUATION.md)                                   | Independent v9 engine audit & market analysis        |
| [`memory/BUG_FIX_CHEATSHEET.md`](memory/BUG_FIX_CHEATSHEET.md)                   | v9 → v10 patch guide (3 crash + 4 silent bugs)       |

## License

Proprietary — © 2026 Kumar & Associates / Sahil Kumar. All rights reserved.

## Author

**Sahil Kumar** — IEM Kolkata, B.Tech IT (3rd year, 2026)
