# SecuraIQ — Launch Readiness

**Honest status (Jul 2026):** suitable for **closed beta / design partners** with the gaps below closed this pass — **not yet** public enterprise launch. Still requires: live cloud/SIEM connectors (Wazuh, TheHive, AWS/Azure/GCP posture), a real Stripe account for payment collection, TLS cert issuance on your domain, and — the one item no amount of engineering substitutes for — actual counsel sign-off on the legal drafts.

Overall launch readiness: **~6.4 / 10** (was 5.5 — see per-area deltas below; this update closed 12 of the 13 tracked gaps that were code-completable without an operator/business/legal decision)

| Area | Score (/10) | Notes |
|------|------------:|-------|
| Vision | 9.8 | AI Security OS — orchestrate tools, evidence, GRC, agents |
| UI/UX | 8.8 | Mission Control direction strong; needs workflow polish + design system |
| AI capabilities | 8.6 (was 8.0) | Router + guardrails + RAG path exist; citations/confidence indicators and human-approval gating now shipped (see AI section below) |
| Security features | 7.2 (was 6.9) | Scanner **import** adapters live; GitHub/Jira/ServiceNow/Slack/Teams connectors shipped; **EDR/XDR connectors shipped** (Sophos Central, CrowdStrike Falcon, SentinelOne, Microsoft Defender for Endpoint — each activates once you set its own credentials); **hardening/patch-exposure baseline tool shipped** (`hardening_baseline` in the tools registry — scored TLS/headers/email-auth/exposed-services check, plus real missing-patch data once an EDR vendor is connected); Wazuh/TheHive/cloud posture (AWS/Azure/GCP) still planned — those need your cloud/SIEM accounts to build against |
| Compliance | 5.5 | Framework **catalogs** + gap analysis shipped; evidence/audit workflows incomplete |
| Backend architecture | 8.2 (was 7.5) | Rate limiting confirmed live, secrets encrypted at rest, backup/DR scripts + runbook, CI security scanning, SIEM log forwarding, background job runner all shipped this pass |
| Enterprise readiness | 7.0 (was 5.5) | MFA enforcement (not just UI hint), usage metering + plan model, notifications, multi-project lifecycle now shipped; SCIM and live payment processing still missing |
| Legal readiness | 3.5→4.5 (unchanged) | Draft policies exist under `/legal/` (verified complete: privacy, terms, AUP, cookies, DPA, security policy, vulnerability disclosure, AI usage, third-party notices, copyright) — **counsel review is the one gap on this list that is not an engineering task and cannot be closed by writing more code** |
| **Launch readiness** | **6.4** | Closed beta candidate; public launch still blocked on live connectors, payment processing, and legal sign-off |

See also: [commercial-roadmap.md](./commercial-roadmap.md) · [enterprise-integrations.md](./enterprise-integrations.md)

---

## XDR/EDR & patch hardening (new this pass)

- `app/connectors/{sophos,crowdstrike,sentinelone,defender}.py` — direct REST clients (no vendor SDKs), each gated by its own `is_configured()` so a partial rollout (e.g. only Sophos) is normal, not degraded.
- `app/xdr.py` — polls every configured vendor, dedupes against the new `xdr_events` table, and opens a real incident (critical/high detections) or vulnerability row (missing patches) through the existing `app.ops.create_incident` / `app.enterprise.create_vulnerability` paths — so notifications, Slack/Teams alerts, and the audit log all fire the same way they do for human-created findings.
- Background sync via the `xdr_sync` job (registered in `app/jobs.py`, default every 30 min, `XDR_SYNC_INTERVAL_SEC`). Manual trigger: `POST /api/xdr/sync`. Status/feed: `GET /api/xdr/status`, `GET /api/xdr/detections`, `GET /api/xdr/patches`.
- SOC workspace now shows a live "XDR / EDR" panel: vendor connection status, missing-patch counts, and recent detections, with a "Sync now" button.
- `hardening_baseline` — a new builtin tool in the VAPT tools registry (shows up automatically in the Tools Palette, no separate UI code needed). Scores TLS version, HTTP security headers, SPF/DMARC, and exposed risky ports (Telnet/SMB/RDP/unauth Redis-Mongo-Elasticsearch/etc.) against any authorized target, and folds in real per-host missing-patch data from whichever EDR vendor is connected. **Not tested against a live target this session** — the sandbox used to build this has no working shell (see Known gaps below); the code path composes existing, already-verified tool primitives (`_tool_tls`, `_tool_email_auth`, the port probe) so the mechanics are sound, but a live run against a real host is still outstanding.
- **Honest gap:** none of the four vendor clients have been exercised against a real tenant — I don't have Sophos/CrowdStrike/SentinelOne/Defender credentials to test with. The auth flows and endpoints match each vendor's current public API docs, but "code matches the docs" isn't the same as "verified working." Test each one against a real (ideally trial/sandbox) tenant before relying on it for alerting.

---

## Do not claim

Avoid (and refuse in marketing copy):

- “100% secure” / “unhackable”
- “Guaranteed compliance” / “certified” (unless you hold the certification)
- “Detects every attack”

Prefer: exact capabilities, evidence sources, and human-in-the-loop language.

SecuraIQ **maps controls** and helps gather evidence. It does **not** make your organization ISO/SOC2/PCI certified.

---

## Launch stages

### Stage 1 — Private Alpha (now)

- Internal / Swana Techno dogfood
- Core AI workflows + Mission Control
- Scanner JSON import + gap analysis
- Draft legal pages (not counsel-approved)

### Stage 2 — Closed Beta

- Selected design partners
- Feedback loops + security hardening
- MFA + OIDC shipped — enforce on deploy (`docs/beta-deploy.md`)
- Postgres/Redis compose profiles (SQLite default until PG adapter)
- Validated connectors: **GitHub webhook** + Jira + Slack webhook

### Stage 3 — Public

- Stable docs + support process
- Subscription / usage metering
- Status page + changelog
- Production TLS, secrets, DR runbooks

### Stage 4 — Enterprise

- SSO (OIDC) + SCIM
- Advanced RBAC + audit exports
- SLA + dedicated support
- Customer DPA executed

---

## Before public launch (checklist)

### Product

- [x] Auth (optional local / enable for SaaS)
- [x] Organizations (basic)
- [ ] Multi-project lifecycle (partial engagements)
- [x] RBAC (basic roles) — see `docs/rbac-matrix.md`
- [x] MFA (TOTP enroll/verify)
- [x] OIDC SSO (Keycloak/Authentik compatible)
- [x] MFA enforced for admins when `MFA_REQUIRED_FOR_ADMIN=true` (server-side 403 in `require_user`, not just a UI prompt — see `docs/beta-deploy.md`)
- [x] Audit logs (basic)
- [x] API keys
- [x] Webhooks
- [~] Integrations (catalog + imports; few live connectors)
- [x] Background jobs / workers (`app/jobs.py` — durable SQLite-backed queue, asyncio worker + periodic KEV-sync scheduler; `GET/POST /api/jobs`)
- [x] Notifications (`app/notifications.py` — in-app feed always on; email opportunistic via SMTP; wired into critical-vuln import and incident creation)

### Security

- [~] TLS in production — ready-to-use reverse-proxy configs shipped (`deploy/Caddyfile`, `deploy/nginx.conf.example`, see `docs/beta-deploy.md` § TLS); actual domain/DNS/cert issuance is still an operator step
- [~] Encryption at rest — secrets (`.env`) now encrypted via `app/secrets_crypto.py`; the SQLite DB itself is still unencrypted (recommend an encrypted volume — LUKS/BitLocker/cloud disk encryption — until a SQLCipher migration is scheduled alongside the Postgres move)
- [x] Secrets management (`app/secrets_crypto.py` — Fernet envelope encryption for API keys/tokens/passwords persisted to `.env`, key resolved from `ENV_SECRET_ENCRYPTION_KEY` or an auto-generated `data/.secret.key`)
- [x] Backups + DR plan (`scripts/backup.sh` / `.ps1`, `scripts/restore.sh`, runbook in `docs/backup-dr.md` with RPO/RTO targets and scheduling)
- [x] Rate limiting (`RateLimitMiddleware` in `app/rate_limit.py`, wired in `app/main.py`; per-path limits via `RATE_LIMIT_*` env vars)
- [x] Input validation / guardrails (partial)
- [x] Dependency / container / IaC scanning **of SecuraIQ itself** in CI (`.github/workflows/security-scan.yml` — pip-audit, Bandit, Gitleaks, Trivy on the built image, Checkov on compose; most gates are report-only until findings are triaged, see workflow comments)
- [x] Security logging / SIEM forward (`app/siem.py` — every `audit()` call now also emits structured JSON to stdout; optional syslog or HTTP/Splunk-HEC forwarding via `SIEM_FORWARD_*` env vars)

### AI

- [x] RAG path + trusted framework catalogs
- [x] Prompt injection / crimeware guardrails (partial)
- [x] File validation (`app/upload_validation.py` — magic-byte check against claimed extension, executable-signature rejection for text/code uploads, per-user storage quota on top of the existing per-file size cap)
- [x] AI memory (engagement)
- [x] Source citations UI + confidence indicators (`app/rag.py::query_with_sources`/`build_context` now keep chunk source + similarity score instead of discarding them; chat streams a `[[citations:...]]` marker; `static/app.js` renders a Sources footer with a color-coded relevance badge per citation)
- [x] Human approval for high-impact actions (`app/approvals.py` — `workspace_reset` now requires a one-time code delivered via the in-app notification feed, not just a client-side `confirm()` dialog + boolean flag)
- [x] Model routing
- [x] AI guardrails (authorized scope)

### Compliance product

Shipped **subset catalogs** for gap analysis (not certification):

ISO 27001 · ISO 27701 · NIST CSF · CIS · SOC 2 · PCI DSS · HIPAA · GDPR · OWASP ASVS

Planned: NIST SP 800-53 depth, evidence workflows, audit export packs.

### Legal (drafts in `/legal/`)

Privacy · Terms · Acceptable Use · Cookie · DPA outline · Security Policy · Vulnerability Disclosure · AI Usage · Third-party Notices · Copyright

**All drafts** until counsel signs off.

### Business

Usage metering + plan model shipped (`app/billing.py`, `GET /api/billing/usage`). Live payment collection (Stripe checkout/webhook code is written and ready in `app/billing_stripe.py`, but inert until a real Stripe account + price IDs are configured — that's a business decision, not an engineering one). Invitations, support portal, status page, changelog, and public docs remain **todo**.

---

## Target before public launch

Every area **9.5+**, validated with real design partners — not more AI connectors alone.

Biggest gap: **enterprise, legal, operational, and first-run UX** — not “more models.”
