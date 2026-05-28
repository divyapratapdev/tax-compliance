# TaxPilot — Project PRD (Living Document)

## Original Problem Statement

User Sahil Kumar (3rd-year IT student, IEM Kolkata, 2026) building TaxPilot — AI compliance engine for Indian CA firms. v9 Python/MySQL engine exists. User asked E1 to: (1) evaluate the project, (2) report changes/fixes, (3) continue development.

## Sessions Completed

### Session 1 — Evaluation & Code Audit (analysis only, Jan 2026)
- Read entire `taxpilot-v9.zip` (Python FastAPI + MySQL engine, 6 modules)
- Wrote `/app/memory/EVALUATION.md` — full 600-line market + technical evaluation
- Wrote `/app/memory/BUG_FIX_CHEATSHEET.md` — copy-paste patches for 3 crash bugs + 4 silent bugs in v9
- Verdict: Idea 8/10 · Tech 6.5/10 · UX 2/10 · GTM 3/10 — clear path to 9/10

### Session 2 — Emergent Starter Template Fixes (Jan 2026)
- Fixed `src/App.js`, `src/hooks/use-toast.js`, `craco.config.js`, `backend/server.py` per code-quality report
- All lint clean, services healthy
- Note: these files were Emergent scaffolding, unrelated to TaxPilot

### Session 3 — Dashboard Build (THIS SESSION, Jan 2026) ✅
**User picked:** 1b (7 pages) · 2h (all docs) · 3d (design agent decides)

**What was built:**
- **Design system** — Cabinet Grotesk + IBM Plex Sans + IBM Plex Mono · Deep Navy `#0B2B5B` + Slate · Swiss density · Indian `₹` + en-IN formatting throughout
- **Backend** (FastAPI + MongoDB) — 22 endpoints under `/api`, all mirroring v9 contracts, auto-seed on startup (1 firm · 3 clients · 6 documents · 6 mismatches · 5 TDS entries · 9 compliance items)
- **Frontend** (React 19 + Tailwind + shadcn/ui) — 7 pages: Dashboard, Clients, Documents, GST Reconciliation, TDS Alerts, Compliance Calendar, Settings — with sidebar nav, client switcher, reset-demo
- **7 production-grade docs** in `/app/docs/`:
  1. `README.md` (root, polished)
  2. `PRODUCT_REQUIREMENTS_DOCUMENT.md` (PRD)
  3. `TECHNICAL_DESIGN_DOCUMENT.md` (TDD with sequence diagrams)
  4. `API_REFERENCE.md` (every endpoint, full payloads)
  5. `SECURITY_AND_COMPLIANCE.md` (DPDP Act 2023, SOC 2 roadmap)
  6. `DEPLOYMENT_GUIDE.md` (Docker, VPS, CI/CD, runbooks)
  7. `12_MONTH_ROADMAP.md` (P0/1/2 backlog, hiring, risk register)

**Testing:** 100% green — 27/27 backend pytest cases · 12/12 frontend Playwright checks across all 7 pages. No critical or minor blocking issues. Indian formatting, fonts, sidebar nav, client switcher, status badges, Resolve/Mark Filed actions all verified.

## Architecture Decision Log

| Date     | Decision                                   | Rationale                                                |
| -------- | ------------------------------------------ | -------------------------------------------------------- |
| Jan 2026 | Dashboard on MongoDB, engine stays on MySQL | Time-to-pilot > schema purity. Contracts bridge cleanly.|
| Jan 2026 | Cabinet Grotesk + IBM Plex                  | Distinctive without being decorative.                    |
| Jan 2026 | Deep navy + Swiss density                   | CA partners are conservative buyers. Trust > flash.      |
| Jan 2026 | No auth in MVP                              | Demo-first. Auth = Phase 2 P0.                           |

## Backlog (Prioritised)

### P0 — Pre-pilot
- [ ] Apply 7 patches from `BUG_FIX_CHEATSHEET.md` to v9 engine
- [ ] Wire dashboard → v9 engine (replace MongoDB demo backend in production mode)
- [ ] JWT auth + RBAC (firm_admin / staff / read_only)
- [ ] DRAFT watermark on every PDF/XML/JSON export
- [ ] Buy domain `taxpilot.in`, ToS, Privacy Policy, ₹1cr indemnity insurance

### P1 — First 10 customers
- [ ] GSTR-2B JSON parser
- [ ] Vision-LLM fallback for low-OCR-confidence invoices (Gemini 3 Flash)
- [ ] Per-firm logo upload
- [ ] MongoDB Atlas migration

### P2 — Scale
- [ ] Tally Prime CSV/XML integration
- [ ] e-Invoice IRP integration
- [ ] Audit log surfaced in UI
- [ ] Hindi UI
- [ ] GSTN ASP/GSP licence path
- [ ] SOC 2 Type I readiness

### Future
- React Native mobile
- Per-client ML fine-tuning
- Supplier credit-score moat

## Files / Structure

```
/app/
├── README.md                              ← Polished root README
├── design_guidelines.json                 ← Swiss financial design tokens
├── backend/
│   ├── server.py                          ← FastAPI + MongoDB · all 22 endpoints
│   ├── requirements.txt
│   └── tests/backend_test.py              ← 27 pytest cases (created by testing agent)
├── frontend/
│   ├── package.json                       ← React 19 + Tailwind + shadcn
│   ├── tailwind.config.js                 ← Navy palette + Cabinet Grotesk fonts
│   ├── README.md
│   └── src/
│       ├── App.js                         ← Router + Shell
│       ├── App.css · index.css            ← Fontshare/Google fonts + design tokens
│       ├── lib/{api,format}.js            ← axios + Indian INR formatters
│       ├── components/                    ← Sidebar, Topbar, KPICard, etc.
│       └── pages/                         ← 7 pages
├── docs/                                  ← Production-grade docs
│   ├── PRODUCT_REQUIREMENTS_DOCUMENT.md
│   ├── TECHNICAL_DESIGN_DOCUMENT.md
│   ├── API_REFERENCE.md
│   ├── SECURITY_AND_COMPLIANCE.md
│   ├── DEPLOYMENT_GUIDE.md
│   └── 12_MONTH_ROADMAP.md
├── memory/
│   ├── PRD.md                             ← This file
│   ├── EVALUATION.md                      ← v9 engine audit (Session 1)
│   ├── BUG_FIX_CHEATSHEET.md              ← v9 patches (Session 1)
│   └── test_credentials.md
├── taxpilot/taxpilot_v6/                  ← Original v9 Python engine (untouched)
└── test_reports/iteration_1.json          ← 100% green test report
```

## What's Live

- **Preview URL:** `https://tds-calculator-dev.preview.emergentagent.com`
- **API base:** Same domain + `/api`
- **MongoDB:** Auto-seeded on backend boot

## Next Actions (for Sahil)

1. Walk through all 7 pages of the dashboard — note any wording / micro-UX you'd change
2. Read `/app/docs/PRODUCT_REQUIREMENTS_DOCUMENT.md` and `/app/docs/12_MONTH_ROADMAP.md` — these are the artefacts to share with a CA mentor or first co-founder
3. Pick path forward:
   - **(a) Polish + ship** — connect a custom domain, add Google Sign-In, run on father's firm next week
   - **(b) Wire the v9 engine** — replace the demo MongoDB layer with calls to the real Python engine
   - **(c) Add Phase 1 P0 features** — JWT auth, DRAFT watermark, GSTR-2B parser
