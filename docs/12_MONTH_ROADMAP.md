# 12-Month Roadmap — TaxPilot

> Owner: Sahil Kumar · Version 1.0 · Updated January 2026
> Driving question: **"What gets us from prototype to ₹30 L ARR in 12 months without burning more than ₹5 L?"**

---

## Phase 0 — Stabilise (Weeks 1-2) · "Make v9 + dashboard demoable"

| Workstream | Tasks                                                                                                 |
| ---------- | ----------------------------------------------------------------------------------------------------- |
| Engine     | Apply the 7 patches from `/app/memory/BUG_FIX_CHEATSHEET.md` to v9; tag `v10`                          |
| Engine     | Update v9 README to reflect Modules 5 & 6 are built (currently claims they aren't)                    |
| Dashboard  | Pilot the dashboard internally (you + 1 friend posing as a CA) for 1 week. Capture every UX friction. |
| Legal      | Buy domain `taxpilot.in` (₹1k/yr); register sole-proprietorship under your name (1 day)              |
| Brand      | 2-page case study template ready (filled with father's firm data in Phase 1)                          |

**Exit criteria:** Demo runs end-to-end in < 8 minutes on real Acme-Manufacturing-style data without crashing.

---

## Phase 1 — First paying customer (Weeks 3-12) · "Father's firm + 4 more"

### Engineering

| Priority | Task                                                                                          | Time est. |
| -------- | --------------------------------------------------------------------------------------------- | --------- |
| P0       | Wire dashboard → v9 Python engine via API (replace MongoDB demo backend)                       | 2 weeks   |
| P0       | Add JWT auth + RBAC (firm_admin / staff / read_only)                                          | 1 week    |
| P0       | DRAFT watermark on every PDF / XML / JSON output                                               | 2 days    |
| P0       | GSTR-2B JSON support (currently only 2A)                                                       | 3 days    |
| P0       | Ship the `extend_existing` bug patches + 3 crash bug fixes from EVALUATION.md                  | 1 day     |
| P1       | Vision-LLM fallback for OCR confidence < 70% (Gemini 3 Flash @ ₹0.30/page)                    | 1 week    |
| P1       | Per-firm logo upload (appears on generated PDFs)                                              | 2 days    |
| P1       | Mongo Atlas migration (move off self-hosted)                                                  | 2 days    |
| P2       | TDS section 194T (new in FY 25-26), 194BA                                                     | 2 days    |
| P2       | Self-serve signup (replace founder-CLI provisioning)                                          | 1 week    |

### Sales / GTM

- **Week 3-4:** Run dashboard live in your father's firm. Document every minute saved per client per task.
- **Week 5-6:** Write the 2-page case study. PDF format. Include exact numbers (₹ saved, hours saved, mismatches caught early).
- **Week 7-10:** Personal pitches to 10 CAs in your father's network. Aim for 5 paid pilots at **₹2,999/month starter tier**.
- **Week 11-12:** Course-correct based on first-customer feedback. Iterate.

### Legal / Compliance

- ToS + Privacy Policy reviewed (cost: ~₹15-25k, founder-friendly tax-law firm like Quagga Partners or Spice Route Legal)
- Buy ₹1 cr Professional Indemnity insurance (~₹40-60k/yr) — HDFC Ergo or ICICI Lombard
- DPDP Act notice & consent flow in onboarding

### Hiring

- **Week 6:** Bring on a CA articleship-completed (semi-qualified) as a part-time domain advisor — ₹15-20k/month. They sanity-check every output before customers see it. **This is non-negotiable.**

### Phase 1 exit metrics

| Metric             | Target  |
| ------------------ | ------- |
| Paying firms       | 5       |
| Active clients (under those firms) | 25 |
| MRR                | ₹15-20k |
| Case studies       | 2 written |
| Negative reviews   | 0       |

---

## Phase 2 — Channel ignition (Weeks 13-26) · "From 5 to 50 firms"

### Engineering

| Priority | Task                                                                                          |
| -------- | --------------------------------------------------------------------------------------------- |
| P0       | React Native Lite (mobile-web responsive really, no native app yet) for on-the-go CA partners |
| P0       | Tally Prime CSV import / Tally XML export                                                     |
| P0       | Bank statement bulk-upload (50+ files in one go)                                              |
| P0       | Excel-export from every screen (CAs love Excel)                                               |
| P1       | Audit log surfaces in the UI (Phase 1 only writes — Phase 2 reads in a "History" tab)         |
| P1       | Hindi UI (translation pass; not full localisation)                                            |
| P1       | e-Invoice IRP integration (for clients ≥ ₹5 Cr turnover, mandatory)                           |
| P2       | Custom report builder (drag-drop fields → PDF/Excel)                                          |
| P2       | API access (paid add-on) for the 1-2 tech-savvy CAs                                           |

### Sales / GTM

- **Channel program:** 25% recurring commission for first 12 months to any CA who refers a paying CA.
- **Content:** Weekly blog post (own newsletter via `taxpilot.in/blog`) on actual CA workflow problems (not SEO fluff). 12 posts in this phase.
- **ICAI presence:** Sponsor 1 chapter event (cost: ₹50k-1 L); offer free CPE webinar (1 CPE credit) on "Automating GST Reconciliation" — 200+ attendees per webinar typical.
- **Direct sales:** Cold-email 200 CAs from ICAI's public member directory. Realistic conversion: 5% replies → 5% trial → 30% paid = ~3 firms / 200 emails. Iterate copy.
- **Pricing experiment:** Try ₹4,999 vs ₹2,999 entry on the next 20 prospects. Track conversion. Pick winner.

### Phase 2 exit metrics

| Metric                  | Target   |
| ----------------------- | -------- |
| Paying firms            | 50       |
| Active clients          | 500      |
| MRR                     | ₹2 L     |
| ARR run-rate            | ₹24 L    |
| Channel-sourced revenue | ≥ 30% MRR|
| NRR (Net Revenue Retention) | ≥ 105% |
| Average cost per customer acquisition (CAC) | ≤ ₹8k |

---

## Phase 3 — Build the moat (Weeks 27-52) · "From 50 to 500 firms"

### Engineering

| Priority | Task                                                                                          |
| -------- | --------------------------------------------------------------------------------------------- |
| P0       | GSTN ASP/GSP licence path — either get licensed (12-18 mo) or partner with existing ASP (3-6 mo). Decide by Month 8. |
| P0       | Income Tax — Form 3CD audit report draft, transfer-pricing reports                            |
| P0       | GSTR-9 annual return prefill                                                                  |
| P0       | Compliance graph — supplier credit-score (signal to CAs that supplier X is ITC-risky) — the data moat starts here |
| P0       | SOC 2 Type I readiness (Vanta / Sprinto)                                                      |
| P1       | Per-client ML model fine-tuning (categorisation adapts to each client's narration patterns)   |
| P1       | DSC (Digital Signature) integration for actual filing                                         |
| P1       | Spring Boot API Gateway (the one referenced in v9 README) — auth, billing, usage metering     |

### Sales / GTM

- Hire first **AE (Account Executive)** with CA / tax-tech background — ₹8-12 L total comp. Run the rep-led pipeline.
- ICAI Tier-1 sponsorship: present at a national conference. Cost: ₹3-5 L, gets 1,500+ CAs in the room.
- 2 reference customers featured on the website with their permission.
- **First retention play:** "Year-end Concierge" — TaxPilot team helps each Growth/Scale customer finish their FY26-27 annual filings end-to-end. Sticky AF.

### Phase 3 exit metrics

| Metric                  | Target   |
| ----------------------- | -------- |
| Paying firms            | 500      |
| MRR                     | ₹20 L    |
| ARR                     | ₹2.4 Cr  |
| Gross margin            | ≥ 80%    |
| Logo churn (annual)     | ≤ 10%    |
| NRR                     | ≥ 110%   |
| Customers on Scale tier (₹24,999/mo) | ≥ 20 |

---

## Hiring plan

| When            | Role                                | Cost (₹/yr) | Why                                                |
| --------------- | ----------------------------------- | ----------- | -------------------------------------------------- |
| Month 1 (now)   | Sahil — Founder / Engineering       | —           | You                                                |
| Month 2         | Part-time CA advisor (15h/week)     | 3 L         | Domain truth-check + customer reference            |
| Month 6         | Co-founder / CTO-equivalent or CA-co-founder | Equity 15-25% | Solo-founder risk is real                          |
| Month 7         | Customer success (1 person)         | 6 L         | Onboard each new firm in their first week          |
| Month 9         | Full-stack engineer #2              | 12-15 L     | Ship Phase 3 backlog faster                        |
| Month 10        | Account executive (sales)           | 12 L base   | First sales hire; ramp time 60-90 days             |
| Month 12        | Designer (part-time)                | 4 L         | When everything stops looking the same in Phase 3  |

Total Year-1 personnel cost (incl. you): ~₹40-50 L. Funded from: founder savings + first revenue + pre-seed cheque (₹50 L on ₹4-5 cr cap, target Month 9 once 50 firms paying).

---

## Risk register (priorities for active management)

| #  | Risk                                                                          | Severity | Owner    | Mitigation                                                |
| -- | ----------------------------------------------------------------------------- | -------- | -------- | --------------------------------------------------------- |
| 1  | Wrong-output liability — TaxPilot generates incorrect TDS, CA files, notice arrives | 🔴 Existential | Sahil | DRAFT watermark + ToS + indemnity insurance + CA review gate |
| 2  | GSTR-2A deprecation — ITC must be claimed from 2B not 2A                      | 🔴 High        | Sahil | 2B parser Phase 1 must-have                                |
| 3  | Solo-founder burnout / illness / drop-out                                     | 🟠 Medium      | Sahil | Co-founder by Month 6; document everything                |
| 4  | OCR accuracy < 75% on real phone-scanned invoices                              | 🟠 Medium      | Sahil | Vision-LLM fallback (Gemini 3 Flash)                       |
| 5  | Tally / Zoho launch a competing product                                       | 🟠 Medium      | Sahil | 18-month window; move fast; channel-lock CAs               |
| 6  | GSTN portal format change breaks parsing                                      | 🟠 Medium      | Sahil | Column-version detector + on-call alarm                    |
| 7  | DPDP Act enforcement triggers a fine for non-compliance                       | 🟡 Low-Medium  | Sahil | Privacy policy in Phase 1; DPO assigned (Sahil)            |
| 8  | First 5 firms all churn after 90 days (= product market fit failure)           | 🟡 Medium      | Sahil | Weekly CSAT calls; NRR target ≥ 105%                       |
| 9  | Cash runs out at Month 9 before first revenue compound                        | 🟡 Medium      | Sahil | Keep monthly burn ≤ ₹2 L until paying ≥ 30 firms           |
| 10 | A junior CA at a customer firm leaks customer GSTINs / PANs                   | 🟡 Low-Medium  | Sahil | Audit log + RBAC + per-action permissions                  |

---

## Key milestones / decision gates

| Date         | Milestone                              | Decision if missed                                  |
| ------------ | -------------------------------------- | --------------------------------------------------- |
| End of Month 1 | First demo runs without crashing (v10) | Spend 1 more week stabilising before pilot          |
| End of Month 3 | 1 paying customer (father's firm)      | Re-examine ICP — maybe wrong segment                |
| End of Month 6 | 10 paying firms · ₹50k MRR             | Question pricing — maybe lower to ₹1,499 starter     |
| End of Month 9 | 50 firms · ₹2 L MRR · pre-seed in motion | If MRR < ₹1 L, pause hiring, re-focus on retention   |
| End of Month 12 | 100 firms · ₹4 L MRR · profitable on contribution margin | If churn > 15%, full Phase 3 rethink |

---

## Things to deliberately NOT do in Year 1

- ❌ Build a native mobile app (mobile-web responsive is enough)
- ❌ Build a marketplace / community / forum
- ❌ Add LLM chat ("ask TaxPilot anything") — it's a distraction in MVP
- ❌ International expansion (UAE / Singapore CA market is tempting; ignore)
- ❌ Cross-sell to non-CA businesses ("Use TaxPilot direct for your company!") — destroys the channel
- ❌ Open-source any core engine code
- ❌ Take VC money before Month 9 — you'll get bad terms with no leverage

---

## Closing principle

> **The job in Year 1 is not to build the best product. It is to find out, in the shortest time possible, whether a CA firm in your father's network is willing to pay ₹2,999/month every month for 12 months.**

If yes → scale. If no → pivot the ICP or pivot the wedge before the cash runs out.
