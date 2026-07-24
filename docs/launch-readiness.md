# SecuraIQ — Launch Readiness

**Honest status (Jul 2026):** suitable for **private alpha / internal dogfood**, **not** enterprise public launch.

Overall launch readiness: **~5.5 / 10**

| Area | Score (/10) | Notes |
|------|------------:|-------|
| Vision | 9.8 | AI Security OS — orchestrate tools, evidence, GRC, agents |
| UI/UX | 8.8 | Mission Control direction strong; needs workflow polish + design system |
| AI capabilities | 8.0 | Router + guardrails + RAG path exist; citations/confidence/approval UX still thin |
| Security features | 6.5 | Scanner **import** adapters live; live connectors (Wazuh, cloud, SCM) mostly planned |
| Compliance | 5.5 | Framework **catalogs** + gap analysis shipped; evidence/audit workflows incomplete |
| Backend architecture | 7.5 | FastAPI + SQLite solid for alpha; Postgres/Redis/hardening for production |
| Enterprise readiness | 5.5 | Basic orgs/RBAC/audit/API keys/webhooks; MFA/SSO/SCIM/billing missing |
| Legal readiness | 3.5→4.5 | Draft policies added under `/legal/` — counsel review required before launch |
| **Launch readiness** | **5.5** | Internal alpha only |

See also: [commercial-roadmap.md](./commercial-roadmap.md) · [enterprise-integrations.md](./enterprise-integrations.md)

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
- MFA, backups, monitoring, rate limits
- Validated connectors (GitHub, Jira, Slack webhook, 1–2 scanners live)

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
- [x] RBAC (basic roles)
- [ ] MFA
- [x] Audit logs (basic)
- [x] API keys
- [x] Webhooks
- [~] Integrations (catalog + imports; few live connectors)
- [ ] Background jobs / workers
- [ ] Notifications (in-app + email)

### Security

- [ ] TLS in production (deploy concern)
- [ ] Encryption at rest
- [ ] Secrets management (env + UI masks today)
- [ ] Backups + DR plan
- [ ] Rate limiting
- [x] Input validation / guardrails (partial)
- [ ] Dependency / container / IaC scanning **of SecuraIQ itself** in CI
- [ ] Security logging / SIEM forward

### AI

- [x] RAG path + trusted framework catalogs
- [x] Prompt injection / crimeware guardrails (partial)
- [~] File validation
- [x] AI memory (engagement)
- [ ] Source citations UI + confidence indicators
- [~] Human approval for high-impact actions
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

Billing · plans · usage · invitations · support portal · status page · changelog · public docs — mostly **todo**.

---

## Target before public launch

Every area **9.5+**, validated with real design partners — not more AI connectors alone.

Biggest gap: **enterprise, legal, operational, and first-run UX** — not “more models.”
