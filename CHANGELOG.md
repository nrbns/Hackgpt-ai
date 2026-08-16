# Changelog

## 2026-08-16 — Closed-beta hardening

### Security & tenancy
- Org RBAC / tenancy foundation; engagement `scope_json` tool policy
- Cross-tenant isolation tests (assets, findings, risks, chats)
- AI security suite (guardrails, scope bypass, approval consume-once)
- Docker Compose hardened: required bootstrap password, restrictive CORS, Postgres/Redis not publicly published; `saas` / `debug-ports` profiles

### Data & AI
- Postgres dual-backend selection (`DATABASE_URL`); SQLite remains lab default
- RAG queries can scope to `org_id` + global knowledge (tenant filter)

### Docs
- Production hardening, closed-beta checklist, connector validation matrix
- Partner onboarding, backup/restore drill, TLS deploy, commercial go-live, status notes
- Feature freeze: validate/harden/commercialize — no new scanners/agents/frameworks this cycle

### UI
- Assistant composer compact dock; vulnerability management layout polish; topbar/tabs fixes
