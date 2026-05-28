# Product Requirements Document — TaxPilot

| Field                  | Value                                            |
| ---------------------- | ------------------------------------------------ |
| Document version       | 1.0                                              |
| Last updated           | January 2026                                     |
| Owner                  | Sahil Kumar (Founder)                            |
| Status                 | MVP                                              |
| Distribution           | Internal · selected design partners              |

---

## 1. Vision

> **"Make every Indian CA firm 3× more productive without hiring 3× more juniors."**

In India, the chartered-accountancy profession is in the middle of a margin squeeze: junior CA salaries have risen 12-15% YoY since 2022, while client-facing fees have not. The bottleneck is not advice — it is the volume of deterministic, transformation-style work (ingestion, categorisation, reconciliation, computation, filing prep) that today consumes 60-70% of a junior's time.

TaxPilot replaces that pipeline with an automated, audit-friendly engine while keeping the senior CA's judgement at the centre. The pitch surface is the **dashboard**: the place where a CA partner sees, at a glance, what across all their clients needs attention this week.

## 2. Ideal Customer Profile (ICP)

| Attribute               | Value                                                      |
| ----------------------- | ---------------------------------------------------------- |
| Type                    | Indian CA firm (proprietor or partnership)                 |
| Size                    | 3–25 staff · ₹50 L – ₹5 Cr annual revenue                  |
| Clients served          | 30–500 SME clients in same firm                            |
| Tech stack today        | Tally Prime / Zoho Books + Excel + WhatsApp + Email        |
| Pain point              | Spend 60-70% of staff hours on rote compliance work        |
| Buying authority        | Founding partner or office head                            |
| Geography (Yr 1)        | Tier-2/Tier-3 metros via founder's network                 |
| Geography (Yr 2-3)      | Pan-India via channel partnerships + ICAI events           |

**Anti-ICP (do NOT sell to):**
- Solo proprietors with <5 clients (too small, churn risk)
- Big-4 / Tier-1 firms (have in-house tech, RFP cycles too long)
- Direct-to-business (skips the CA — destroys the channel)

## 3. Jobs-To-Be-Done

A CA partner hires TaxPilot to do **3 jobs**:

### Job 1 — "Give me a single screen that tells me what's burning today."

Across 50 clients, the CA needs to know:

- Whose return is due this week?
- Where is ITC at risk?
- Which client missed a TDS deduction?

Today this lives in 50 Excel files and a junior's head. **Acceptance:** Executive Dashboard surfaces this in ≤ 3 seconds with no clicks.

### Job 2 — "Reconcile 2 days of work in 4 minutes."

GSTR-2A/2B reconciliation is the most painful monthly task — junior CAs spend 2-3 days matching purchase invoices to the GSTN portal output, line by line.

**Acceptance:** Upload purchase Excel + GSTR-2A Excel → see ITC safe / at risk / missing-in-books split with a per-mismatch suggested action in under 5 minutes.

### Job 3 — "Don't let me miss a TDS deduction."

Missed TDS deductions are silent killers — penalties accrue at 1% per month and only surface at scrutiny. Today they get caught at audit when 6-18 months of interest has already piled up.

**Acceptance:** Every payment above relevant section thresholds (194C/J/I/H etc.) flagged within 24 hours of bank-statement ingestion. Penalty estimate visible.

## 4. Core Features (MVP — built)

| # | Feature                  | Status        | Page in dashboard       |
| - | ------------------------ | ------------- | ----------------------- |
| 1 | Document ingestion + OCR | ✅ v9 engine  | Documents               |
| 2 | Auto-categorisation      | ✅ v9 engine  | (server-side)           |
| 3 | GST reconciliation       | ✅ v9 engine  | GST Reconciliation      |
| 4 | TDS computation          | ✅ v9 engine  | TDS Alerts              |
| 5 | Compliance calendar      | ✅ v9 engine  | Compliance              |
| 6 | Draft returns            | ✅ v9 engine  | (via 26Q export)        |
| 7 | Executive dashboard      | ✅ this build | Dashboard               |
| 8 | Multi-client view        | ✅ this build | Clients                 |
| 9 | Firm profile & alerts    | ✅ this build | Settings                |

## 5. Out of Scope (MVP)

- ❌ Direct GSTN portal filing (CA still uploads via portal/DSC)
- ❌ Mobile native apps (web responsive only)
- ❌ Direct integration with Tally Prime (CSV export only)
- ❌ Income Tax computation (Form 3CD, transfer pricing) — Phase 2
- ❌ Audit working papers — Phase 3
- ❌ Multi-language UI (English only — Hindi in Phase 2)

## 6. Success Metrics

### North-Star Metric
**Active CA firms** (≥ 5 logins / week, ≥ 1 reconciliation run / month).

### Activation funnel (per CA firm)
| Stage              | Definition                                       | Target |
| ------------------ | ------------------------------------------------ | ------ |
| Signed up          | Firm account created                             | 100%   |
| Onboarded          | ≥ 1 client added                                 | 80%    |
| Activated          | ≥ 1 bank statement uploaded & processed          | 60%    |
| Habituated         | ≥ 1 reconciliation run                           | 40%    |
| Paying             | First invoice paid                               | 25%    |
| Retained (90d)     | Still paying after 90 days                       | 90% of paying |

### Quality metrics (engine accuracy)
| Metric                                   | Target    | v9 actual           |
| ---------------------------------------- | --------- | ------------------- |
| Bank narration categorisation F1         | ≥ 92%     | 97% (benchmark)     |
| GST mismatch false-positive rate         | ≤ 2%      | TBD — needs pilot   |
| GST mismatch false-negative rate         | ≤ 5%      | TBD — needs pilot   |
| OCR field extraction accuracy            | ≥ 92%     | 75% baseline · vision-LLM fallback planned |
| TDS-section detection accuracy           | ≥ 95%     | Deterministic mapping — close to 100% |

### Business metrics
| Metric                | Year 1 target | Year 2 target |
| --------------------- | ------------- | ------------- |
| Paying CA firms       | 50            | 500           |
| ARR                   | ₹30 L         | ₹6 Cr         |
| Gross margin          | ≥ 75%         | ≥ 80%         |
| Net Revenue Retention | ≥ 100%        | ≥ 115%        |

## 7. Pricing

| Plan     | Monthly       | Clients incl. | Overage          | Persona                       |
| -------- | ------------- | ------------- | ---------------- | ----------------------------- |
| Starter  | ₹ 2,999/mo    | 5 clients     | ₹ 600 / client   | Solo CA, 1 office             |
| Growth   | ₹ 9,999/mo    | 25 clients    | ₹ 500 / client   | 3-10 staff partnership        |
| Scale    | ₹ 24,999/mo   | 100 clients   | ₹ 400 / client   | 10-25 staff firm              |
| Enterprise | Custom      | Unlimited     | n/a              | 25+ staff, multi-branch       |

Annual plans discounted 17% (₹ 2,999 × 10 = ₹ 29,990 / year).

## 8. Top Risks (excerpted; full register in `12_MONTH_ROADMAP.md`)

| Risk                                                    | Severity     | Mitigation                                            |
| ------------------------------------------------------- | ------------ | ----------------------------------------------------- |
| Compliance liability for wrong returns                  | 🔴 Existential | DRAFT watermark · ToS · ₹1 cr professional indemnity   |
| GSTR-2A deprecated in favour of GSTR-2B                 | 🔴 High       | Ship GSTR-2B parser in Phase 1                        |
| GSTN portal format changes silently                     | 🟠 Medium     | ASP/GSP licence path; column-version detector + alarms |
| OCR accuracy below threshold on phone-scanned bills     | 🟠 Medium     | Vision-LLM fallback (Gemini 3 Flash) for low confidence |
| Sales cycle 6-9 months for first CA pilot               | 🟠 Medium     | Pilot in father's firm (Kumar & Associates) Month 1   |
| Solo founder risk                                       | 🟡 Medium     | Hire CA-co-founder by Month 6                         |

## 9. Open Questions

- **Brand/Identity:** Keep "TaxPilot" or rebrand to something more conservative ("Auditly", "Numeric") that signals seriousness?
- **Channel commercials:** What is the optimum referral commission to CAs who introduce other CAs? (industry norm: 20-30% recurring for 12 months)
- **Insurance:** Lockheed-style "vendor errors & omissions" cover or pure indemnity?
- **Filing integration:** Build GSTN ASP/GSP licence in-house (12-18 months, ₹15-25 L) or partner with existing ASP (faster, lower margin)?

## 10. Appendix — Persona

> **Mahesh Agarwal, 47, CA partner at "Agarwal & Sharma, Chartered Accountants" — Pune.**
>
> 3 partners, 11 staff (5 of whom are articleship/semi-qualified). Serves 73 SME clients across textile manufacturing, IT services and trading. Bills ₹2.1 Cr/yr. Pays staff ₹1.4 Cr/yr.
>
> Logs into TaxPilot every morning at 9:30 AM over chai. Glances at the Executive Dashboard. Reds first, then yellows.
>
> Today he sees: "ITC at risk ₹1.2 L" → 2 clicks → Acme Manufacturing has a missing invoice from Sharma Electronics → he WhatsApps Sharma's accounts head with one tap. Total time: 90 seconds. Pre-TaxPilot, this would have surfaced at month-end close, three weeks later.
>
> Mahesh is the user. The articleships use the platform too — but Mahesh is the budget holder, the one who renews, the one who recommends.
