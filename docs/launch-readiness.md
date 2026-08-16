# SecuraIQ — Launch Readiness

**Honest status (Aug 2026):** a FastAPI backend + web UI that orchestrates five security disciplines — red team/VAPT, blue team/XDR, threat intel, compliance/GRC, and an AI layer — around real data (RAG citations, background jobs, audit logs), not a demo.

Suitable for **closed beta / design partners**. **Not** ready for public enterprise launch.

**Feature freeze (Aug 2026):** stop adding scanners, agents, frameworks, and report formats. Next 30 days = harden, validate connectors, commercialize, and run 5–10 design partners. See [closed-beta-checklist.md](./closed-beta-checklist.md) and [production-hardening.md](./production-hardening.md).

Overall launch readiness: **~7.2 / 10**. Strongest areas are vision, UI, AI, backend, and **cross-discipline correlation**. Weakest remains legal. Live-tenant proof and counsel still required.

| Area | Score (/10) | Notes |
|------|------------:|-------|
| Vision | 9.8 | AI Security OS — orchestrate tools, evidence, GRC, agents |
| UI/UX | 8.8 | ChatGPT-style assistant + industrial Control Board; workflow polish still needed |
| AI capabilities | 8.6 | Router, guardrails, RAG with citations/confidence, human-approval gates shipped |
| Backend architecture | 8.2 | Rate limiting, encrypted secrets, backup/DR, CI security scanning, SIEM log forwarding, job runner |
| Security features | 7.4 | EDR/XDR, Wazuh, inventory, HardeningKitty, **TheHive**, **cloud posture (AWS/Azure/GCP)** shipped. Still **unverified** on live tenants — use `scripts/connector_verify.py` + trials |
| Enterprise readiness | 7.5 | MFA, OIDC SSO, **SCIM Users** (`/scim/v2` list/create/PATCH/DELETE; no Groups/Bulk), usage metering, notifications, multi-project lifecycle. Live Stripe still needs a real account + price IDs |
| Compliance | 6.5 | Catalogs + gap analysis + evidence queue + audit packs. Scoring methodology now explicit on every assessment (`methodology.auditor_grade=false`) — still heuristic, not auditor-certified |
| Legal readiness | 4.5 | All ten draft policies exist under `/legal/` … **None reviewed by counsel** |
| **Launch readiness** | **~7.2** | Closed beta candidate; public launch blocked on counsel, payments, TLS domain, and live connector validation |

See also: [commercial-roadmap.md](./commercial-roadmap.md) · [enterprise-integrations.md](./enterprise-integrations.md) · [beta-deploy.md](./beta-deploy.md) · [production-hardening.md](./production-hardening.md) · [connector-validation-matrix.md](./connector-validation-matrix.md) · [closed-beta-checklist.md](./closed-beta-checklist.md)

---

## 30-day plan (feature freeze)

| Week | Focus | In-repo |
|------|--------|---------|
| 1 | Production hardening | Compose secrets/CORS/internal DB; tenant isolation tests |
| 2 | AI security | Guardrails + scope + approval suites (`tests/test_ai_security.py`) |
| 3 | Live integrations | `scripts/connector_verify.py --matrix` + partner trials |
| 4 | Commercial + beta | Stripe end-to-end; 5–10 design partners; Investigate workflow feedback |

**Flagship bet:** Investigate (assets → findings → risk → intel → graph → remediation → report) — not more navigation.

---

## Public-launch priorities (worst first)

1. **Counsel review of `/legal/` drafts** — single hard blocker; outside engineering.
2. **Real Stripe account + live price IDs** — Business/Enterprise billing code exists; needs a business decision.
3. **Production domain + TLS** — Caddy/nginx configs ready (`deploy/`); needs DNS + cert issuance.
4. **Live-tenant validation** for EDR/XDR/SIEM/TheHive/cloud — trial accounts; harness: `python scripts/connector_verify.py`
5. **Compliance depth** — human attestation + fuller catalogs; scoring is documented as heuristic (`methodology` on gap results) — not auditor-grade yet

Shipped this pass: **STIX 2.1 / TAXII poll** (`/api/intel/stix/*`), **Redis-optional realtime bus** (`REDIS_URL`), **GitLab webhooks**, knowledge-graph correlation, SCIM Users CRUD (minimal PATCH/DELETE), gap scoring methodology disclosure.

Target: every area **9.5+**, validated with real design partners.

---

## XDR/EDR, SIEM, inventory & hardening

- `app/connectors/{sophos,crowdstrike,sentinelone,defender}.py` — REST clients gated by `is_configured()`.
- `app/xdr.py` + `xdr_sync` job — detections → incidents; missing patches → vulns; SOC panel + Sync.
- `app/wazuh.py` / `app/wazuh_api.py` — SIEM sync into incidents/alerts (authorized labs).
- `app/openaudit.py` / `app/openaudit_api.py` — network inventory sync into Assets (UI branding: “Network inventory”).
- `app/hardeningkitty.py` / `app/hardeningkitty_api.py` — Windows CIS Audit/Config only (HailMary blocked); CIS Downloads linked as external account flow.
- `hardening_baseline` tool — TLS/headers/email-auth/exposed-services scoring + EDR patch data when connected.

**Real-time, not just faster polling:** `app/realtime_bus.py` is an in-process pub/sub that every write path (assets, risks, vulns, incidents, remediation, playbooks, campaigns, jobs, notifications, XDR events, cloud/SIEM syncs) publishes to; `GET /api/realtime` (SSE) wakes on publish instead of sleeping on a fixed tick, so the UI reflects a change within milliseconds of it happening, with a 3s heartbeat as a safety net if the bus is quiet. Three inbound paths skip polling entirely: `POST /api/xdr/ingest` (generic authenticated push, any SIEM/relay), `POST /api/wazuh/webhook` (native Wazuh alert format), and the GitHub code-scanning webhook. `app/xdr_stream.py` holds open the CrowdStrike Falcon Streaming API (needs "Event streams: Read") for true push, and runs a **near-real-time poll** (default every 60s via `XDR_NEAR_REALTIME_INTERVAL_SEC`) for Sophos, SentinelOne, and Defender — those vendors have no Falcon-style client-held detection stream without a public webhook, so the tight poll is the local-first substitute; status for all four is at `GET /api/xdr/status` → `streaming.<vendor>` (`mode: stream` vs `near_realtime_poll`). The slower `xdr_sync` job (default 30 min) remains as reconciliation.

**Honest gap:** none of the vendor clients — poll or stream — have been exercised against a real tenant. “Matches the docs” ≠ “verified working”; the CrowdStrike streaming path and the near-realtime polls carry the same caveat. Use `scripts/connector_verify.py` against a trial tenant before relying on any of this for alerting.

---

## Do not claim

Avoid (and refuse in marketing copy):

- “100% secure” / “unhackable”
- “Guaranteed compliance” / “certified” (unless you hold the certification)
- “Detects every attack”
- “Enterprise launch-ready” / “production SaaS” until counsel + payments + live connector validation

Prefer: exact capabilities, evidence sources, and human-in-the-loop language.

SecuraIQ **maps controls** and helps gather evidence. It does **not** make your organization ISO/SOC2/PCI certified.

---

## Launch stages

### Stage 1 — Private Alpha (now)

- Internal / Swana Techno dogfood
- Core AI workflows + Control Board / Assistant
- Scanner JSON import + gap analysis
- Draft legal pages (not counsel-approved)

### Stage 2 — Closed Beta

- Selected design partners
- Feedback loops + security hardening
- MFA + OIDC shipped — enforce on deploy (`docs/beta-deploy.md`)
- Postgres/Redis compose profiles — **Postgres mandatory for SaaS** (`--profile saas`); SQLite remains lab/community default
- Validated connectors: GitHub webhook + Jira + Slack webhook; **live-tenant proof** for any EDR/SIEM sold as “working” — see [connector-validation-matrix.md](./connector-validation-matrix.md)

### Stage 3 — Public

- Counsel-approved legal
- Live Stripe billing
- Production TLS, secrets, DR runbooks
- Stable docs + support process
- Status page + changelog

### Stage 4 — Enterprise

- SCIM
- Advanced RBAC + audit exports
- SLA + dedicated support
- Customer DPA executed

---

## Before public launch (checklist)

### Product

- [x] Auth (optional local / enable for SaaS)
- [x] Organizations (basic)
- [x] Multi-project lifecycle (engagements)
- [x] RBAC (basic roles) — see `docs/rbac-matrix.md`
- [x] MFA (TOTP enroll/verify)
- [x] OIDC SSO (Keycloak/Authentik compatible)
- [x] MFA enforced for admins when `MFA_REQUIRED_FOR_ADMIN=true`
- [x] Audit logs (basic)
- [x] API keys
- [x] Webhooks
- [~] Integrations (catalog + imports; EDR/SIEM/inventory **built**, **not live-tenant verified**)
- [x] Background jobs / workers (`app/jobs.py`)
- [x] Notifications (`app/notifications.py`)
- [~] SCIM provisioning — Users list/create/PATCH/DELETE at `/scim/v2` (opt-in); no Groups/Bulk/Filter yet
- [x] TheHive case management (`/api/thehive/*`)
- [x] Cloud posture AWS / Azure / GCP (`/api/cloud/*` + JSON import)
- [x] STIX 2.1 ingest/export + TAXII 2.1 poll (`/api/intel/stix/*`)
- [~] Realtime bus — in-process default; set `REDIS_URL` (+ `pip install redis`) for multi-worker
- [x] GitLab webhooks (`/api/integrations/gitlab/webhook`) — mirrors GitHub pattern

### Security

- [~] TLS in production — configs shipped; domain/DNS/cert still an operator step
- [~] Encryption at rest — `.env` secrets via `app/secrets_crypto.py`; DB volume encryption recommended until Postgres/SQLCipher
- [x] Secrets management
- [x] Backups + DR plan (`docs/backup-dr.md`)
- [x] Rate limiting
- [x] Input validation / guardrails (partial)
- [x] Dependency / container / IaC scanning in CI
- [x] Security logging / SIEM forward (`app/siem.py`)

### AI

- [x] RAG path + trusted framework catalogs
- [x] Prompt injection / crimeware guardrails (partial)
- [x] File validation
- [x] AI memory (engagement)
- [x] Source citations UI + confidence indicators
- [x] Human approval for high-impact actions
- [x] Model routing
- [x] AI guardrails (authorized scope)

### Compliance product

Shipped **subset catalogs** for gap analysis (not certification):

ISO 27001:2022 · ISO 27701:2025 · NIST CSF 2.0 · NIST 800-53 Rev.5 · NIST 800-171 · CMMC L2 · CIS v8.1 · SOC 2 TSC · PCI DSS 4.0.1 · HIPAA · GDPR · NIS2 · ASVS 5.0 · OWASP Top 10:2025

Still incomplete: fuller human attestation workflows and NIST 800-53 depth. **Shipped:** evidence collect-next queue (`GET /api/gap/evidence-queue`) and ZIP audit packs (`GET /api/gap/assessments/{id}/audit-pack`).

### Legal (drafts in `/legal/`)

Privacy · Terms · Acceptable Use · Cookie · DPA outline · Security Policy · Vulnerability Disclosure · AI Usage · Third-party Notices · Copyright

**All drafts** until counsel signs off. This is the one gap on this list that engineering cannot close.

### Business

Usage metering + plan model shipped (`app/billing.py`, `GET /api/billing/usage`). Live payment collection (`app/billing_stripe.py`) is written but inert until Stripe account + price IDs. Invitations, support portal, status page, changelog, and public docs remain **todo**.

---

## Target before public launch

Every area **9.5+**, validated with real design partners — not more AI connectors alone.

Biggest gap: **legal sign-off, payments, TLS ops, live connector verification, and compliance evidence** — not “more models.”
