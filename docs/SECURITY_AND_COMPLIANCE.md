# Security & Compliance — TaxPilot

| Field       | Value                          |
| ----------- | ------------------------------ |
| Version     | 1.0                            |
| Last review | January 2026                   |
| Owner       | Sahil Kumar (Founder, DPO)     |

---

This document describes TaxPilot's security posture and compliance roadmap. It is intended to be shared with prospects (CA firms) doing due diligence, and used internally as a planning artefact for the path to SOC 2 / ISO 27001.

---

## 1. Regulatory environment

TaxPilot processes data that is:

1. **Personally Identifiable Information (PII)** under the **Digital Personal Data Protection Act 2023 (India)** — names, addresses, phone numbers, email, PAN, GSTIN of company directors and proprietors.
2. **Financial data** — bank statements, GST invoices, TDS records — that is implicitly sensitive even though not explicitly listed in the DPDP Act.
3. **Tax records** — covered under the **Income Tax Act 1961 (retention obligations)** and **CGST Act 2017 (return audit trail obligations)**.

### 1.1 Applicable laws

| Law / standard                              | Status      | Notes                                                            |
| ------------------------------------------- | ----------- | ---------------------------------------------------------------- |
| Digital Personal Data Protection Act 2023   | In scope    | Notice + consent flows; rights to erasure & portability          |
| Information Technology Act 2000 (sec. 43A)  | In scope    | "Reasonable security practices" — read as ISO 27001-aligned      |
| Income Tax Act 1961 — sec. 44AA / 92D       | In scope    | 6-8 year retention of tax records                                |
| CGST Act 2017 — rule 56                     | In scope    | 72-month retention of GST records                                |
| RBI Master Directions on Outsourcing of IT  | Out of scope (we are not a regulated entity) — but relevant if we serve NBFC clients |
| SOC 2 Type II                               | Roadmap     | Year-2 target for enterprise pipeline                            |
| ISO 27001                                   | Roadmap     | Year-2 target — required by Big 4 channel partners               |

## 2. Data classification

| Class      | Examples                                                   | Encryption | Access control            |
| ---------- | ---------------------------------------------------------- | ---------- | ------------------------- |
| Public     | Marketing site copy, demo data                             | n/a        | n/a                       |
| Internal   | Application logs, infra metrics                            | TLS        | Engineering only          |
| Confidential | CA firm names, contact info, billing                     | TLS + AES-256 at rest | Firm + admin    |
| Restricted | Client GSTIN, PAN, bank statements, invoices, TDS amounts | TLS + AES-256 at rest + audit log | Firm + their delegated staff only |

## 3. Security controls — implementation status

### 3.1 Network & transport

| Control                                                    | Status            |
| ---------------------------------------------------------- | ----------------- |
| TLS 1.3 enforced on all external endpoints                 | ✅ Done (Emergent edge / Cloudflare) |
| HSTS with 1-year max-age + preload                         | ✅ Done            |
| Certificate auto-renewal (Let's Encrypt)                   | ✅ Done            |
| Cipher suites: only forward-secret AEAD ciphers            | ✅ Done            |
| WAF (Cloudflare) blocks OWASP Top 10 by default            | ✅ Done            |
| DDoS protection (Cloudflare Pro tier)                      | Planned Phase 1   |

### 3.2 Application

| Control                                                    | Status            |
| ---------------------------------------------------------- | ----------------- |
| CORS allow-list (no wildcard in prod)                      | ⚠️ Hardening pending (currently `*` for dev) |
| Authentication — JWT with 1-hour expiry + refresh tokens   | Planned Phase 1   |
| Authorization — RBAC: `firm_admin`, `firm_staff`, `read_only` | Planned Phase 1 |
| Input validation — Pydantic v2 schemas everywhere          | ✅ Done            |
| Output encoding — React auto-escapes JSX                    | ✅ Done            |
| Rate limiting — 60 req/min anon, 600 req/min auth          | Planned Phase 1   |
| Idempotency keys on mutations                              | Planned Phase 2   |
| File upload: size limit 10MB · MIME check · virus scan via ClamAV | ✅ Size limit · Virus scan planned Phase 2 |

### 3.3 Data at rest

| Control                                                    | Status            |
| ---------------------------------------------------------- | ----------------- |
| MongoDB Atlas — AES-256 disk encryption (default)          | ✅ When on Atlas (Phase 1 migration) |
| MySQL engine database — InnoDB tablespace encryption       | Planned Phase 1   |
| Object storage (Cloudflare R2) — server-side encryption     | ✅ Default (AES-256-GCM) |
| Backups — encrypted snapshots, daily, 30-day rolling       | Planned Phase 1   |
| Cross-region replication                                   | Planned Phase 2 (Atlas M30 cluster) |

### 3.4 Identity & access (internal)

| Control                                                    | Status            |
| ---------------------------------------------------------- | ----------------- |
| All production access via SSH key (no passwords)           | ✅ Done            |
| 2FA required on GitHub, MongoDB Atlas, Cloudflare          | ✅ Done            |
| Principle of least privilege — separate IAM roles per service | Planned Phase 1 |
| Secrets in env vars; never committed; rotated quarterly    | ✅ Done            |
| HashiCorp Vault or AWS Secrets Manager                     | Planned Phase 2   |
| Audit log of every admin action                            | Planned Phase 2   |

### 3.5 Application audit log

The TaxPilot dashboard records every state-changing action in a `audit_log` collection (Phase 2):

```json
{
  "id": "uuid",
  "ca_firm_id": "firm-demo-001",
  "actor_user_id": "user-xyz",
  "actor_role": "firm_admin",
  "action": "mismatch.resolve",
  "resource_type": "mismatch",
  "resource_id": "...",
  "before": { "is_resolved": false },
  "after":  { "is_resolved": true, "resolution_notes": "..." },
  "ip_address": "1.2.3.4",
  "user_agent": "...",
  "timestamp": "..."
}
```

Audit retention: 7 years (matches tax retention obligation).

### 3.6 Vendor / sub-processor list

| Vendor             | Purpose                          | Data residency      | DPA signed |
| ------------------ | -------------------------------- | ------------------- | ---------- |
| MongoDB Atlas      | Primary application database     | AWS Mumbai (ap-south-1) | Planned    |
| Cloudflare         | CDN, WAF, DNS                    | Global anycast      | Planned    |
| Cloudflare R2      | Document storage (PDFs, Excels)  | EU / global         | Planned    |
| Resend / SendGrid  | Transactional email              | EU                  | Planned    |
| Meta WhatsApp BSP  | WhatsApp Business reminders      | US                  | Planned    |
| Sentry             | Error tracking                   | EU                  | Planned    |
| GitHub             | Source code, CI/CD               | US                  | Planned    |
| OpenAI / Google AI | Optional vision-LLM OCR fallback | US                  | Planned (data not used for training, zero-retention API config) |

All sub-processors will be enumerated in the public Privacy Policy in Phase 1.

## 4. DPDP Act 2023 obligations

### 4.1 Notice & consent

- On first login a CA firm sees a privacy notice covering: what data we collect, why, who it is shared with (sub-processors), retention duration, and rights.
- Clients' PII is processed on behalf of the CA firm under a **data-processor** relationship (not data-fiduciary). The CA firm remains the data-fiduciary for their clients' data — TaxPilot's terms make this explicit.

### 4.2 Data principal rights

| Right                  | Implementation                                                |
| ---------------------- | ------------------------------------------------------------- |
| Right to access        | `GET /api/me/data-export` (Phase 1) returns a ZIP of all firm data |
| Right to correction    | All editable fields exposed in the UI                         |
| Right to erasure       | `DELETE /api/firms/me` schedules a 30-day hard-delete         |
| Right to portability   | Same as right to access — exported as JSON                    |
| Right to grievance     | Privacy contact email displayed in UI footer + privacy policy |

### 4.3 Children's data

Out of scope — TaxPilot is B2B; we do not knowingly process children's data.

### 4.4 Cross-border data transfer

Default: all data in `ap-south-1` (Mumbai). Sub-processors that operate globally (Cloudflare, Meta, OpenAI) are documented and a Standard Contractual Clauses (SCC) equivalent is on file.

### 4.5 Data breach notification

Per DPDP Act sec. 8(6): notify the Data Protection Board of India and affected data principals **within 72 hours** of becoming aware of a personal-data breach. We will maintain:

- An on-call rotation for incident response
- A pre-drafted notice template (Schedule II equivalent)
- A logging-and-monitoring system (Sentry + MongoDB Atlas audit) capable of detecting unauthorised access

## 5. Compliance roadmap

| Quarter      | Milestone                                                                  |
| ------------ | -------------------------------------------------------------------------- |
| Q1 2026      | Privacy Policy + Terms of Service published. Cookie consent. DPA template. |
| Q1 2026      | Production indemnity insurance — ₹1 cr cover (HDFC Ergo / ICICI Lombard).  |
| Q2 2026      | JWT auth + RBAC + audit log. CORS hardening. WAF tuning.                   |
| Q3 2026      | SOC 2 Type I readiness audit (Vanta / Sprinto-assisted).                   |
| Q4 2026      | SOC 2 Type I report.                                                       |
| Q2 2027      | SOC 2 Type II + ISO 27001 lead-implementer engagement.                     |
| Q4 2027      | ISO 27001 certification.                                                   |

## 6. Liability framework

Three layers of protection:

### 6.1 Contractual (ToS)

Every generated output (GSTR-3B JSON, 26Q XML, P&L PDF) carries an embedded **"DRAFT — REQUIRES CA REVIEW"** watermark. The Terms of Service assign final review and filing responsibility to the CA firm, not TaxPilot. This is also explicit in the click-through onboarding.

### 6.2 Insurance

- **Professional Indemnity** — ₹1 cr cover (renewable annually) protects against claims arising from defects in the engine output. Annual premium ~₹40-60k.
- **Cyber Liability** — ₹2 cr cover for data breach, notification cost, regulatory fines. Annual premium ~₹80k-1.2 L.

Both written via Indian general insurers familiar with the SaaS profile (HDFC Ergo, Bajaj Allianz, ICICI Lombard).

### 6.3 Engineering

- DRAFT watermark on every export (PDF + XML + JSON)
- Confidence indicators on every ML/OCR output (`category_confidence`, `ocr_status`)
- Diff / "what changed since last run" view so CAs can audit
- Bug-bounty program (Phase 2, via HackerOne) — payout ₹10k-1 L per severity

## 7. Threat model — quick summary

| Threat                                                | Likelihood | Impact     | Primary mitigation                                |
| ----------------------------------------------------- | ---------- | ---------- | ------------------------------------------------- |
| Account takeover (credential stuffing)                | High       | High       | JWT short-lived + refresh + MFA (Phase 2)         |
| SQL/NoSQL injection                                   | Medium     | High       | Pydantic schemas; parameterised queries           |
| File upload — malicious PDF / Excel macro             | Medium     | Medium     | MIME validation, sandboxed parser; ClamAV scan    |
| Cross-tenant data leak                                | Low        | Critical   | `ca_firm_id` scoped on every DB query; integration tests |
| Insider exfiltration (employee)                       | Low        | High       | Audit log + 2FA + least-privilege IAM             |
| Supply-chain (npm dependency)                         | Medium     | Medium     | Renovate-bot + GitHub Dependabot + lockfile pinning |
| DDoS                                                  | Medium     | Medium     | Cloudflare Pro + autoscaling                      |
| GSTN portal scraping abuse (if we build it)           | Low        | High       | Per-firm rate-limits, exponential backoff         |

## 8. Contact

- **Security disclosures:** security@taxpilot.in (PGP key on website)
- **Privacy / Data Protection Officer:** dpo@taxpilot.in
- **Grievance Redressal Officer (DPDP Act):** sahil@kumarca.in
