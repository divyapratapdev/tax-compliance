# TaxPilot Dashboard — Frontend

The CA-facing web app. React 19 + Tailwind 3 + shadcn/ui.

## Develop

```bash
yarn install
yarn start    # http://localhost:3000
```

Set `REACT_APP_BACKEND_URL` in `.env` to point at the FastAPI backend.

## Lint

```bash
yarn lint                  # via eslint (auto-runs in CI)
```

## Build for production

```bash
yarn build       # output in /build, static — host on any CDN/S3/Vercel
```

## Folder structure

```
src/
├── App.js                          Router + shell
├── lib/
│   ├── api.js                      axios client + endpoints
│   └── format.js                   Indian INR / date formatters
├── components/
│   ├── Sidebar.jsx                 navy nav (7 links)
│   ├── Topbar.jsx                  client switcher + user chip
│   ├── ClientContext.jsx           global selected-client state
│   ├── KPICard.jsx
│   ├── PageHeader.jsx
│   ├── StatusBadge.jsx
│   ├── EmptyState.jsx
│   └── ui/                         shadcn primitives (kept for future use)
└── pages/
    ├── Dashboard.jsx               KPI strip + alerts
    ├── Clients.jsx                 searchable client table
    ├── Documents.jsx               upload zone + queue
    ├── GSTReconciliation.jsx       ITC cards + mismatch table
    ├── TDSAlerts.jsx               missed deductions + vendors + 26Q
    ├── Compliance.jsx              grouped timeline view
    └── Settings.jsx                firm profile + alerts
```

## Design system

- **Fonts:** Cabinet Grotesk (headings), IBM Plex Sans (body), IBM Plex Mono (numerics) — loaded from Fontshare + Google Fonts in `index.css`
- **Color palette:** Deep Navy `#0B2B5B`, Slate neutrals, Red/Amber/Green/Sky for semantics
- **Density:** Tables `py-3 px-4`, KPI cards `p-6`, page `p-8`
- **Numerics:** Always `font-mono tabular-nums` + `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })`

## Testing

Every interactive element has a `data-testid` attribute (kebab-case, descriptive). See `TECHNICAL_DESIGN_DOCUMENT.md` §5 for naming conventions.
