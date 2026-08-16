# SecuraIQ — Priority checklist (feature freeze)

Map of the ordered harden+validate plan against the repo. **Do not add scanners/agents/frameworks.**

## Edition split

| Edition | Database | Auth |
|---------|----------|------|
| Community / lab | SQLite OK | optional |
| SecuraIQ Cloud / production | **PostgreSQL only** (`DATABASE_URL`) | required + MFA for admin |

## P0 — before public internet

| # | Item | Status |
|---|------|--------|
| 1 | Production Docker (no default passwords, no CORS `*`, DB/Redis internal, named network) | Done |
| 1b | Reverse proxy + TLS | Done scaffolding (`deploy/`, Caddy profile `proxy`) — operator owns DNS/certs |
| 1c | Secure cookies + HSTS / security headers | Done (`COOKIE_SECURE`, `FORCE_HTTPS_HEADERS`) |
| 2 | Postgres SaaS-only + Alembic | Done guard + baseline migration + `scripts/db_migrate_and_run.py` |
| 3 | Tenant isolation tests | Partial — assets/vulns/risks/chats/engagements/RAG/investigation; expand reports/incidents/evidence |
| 4 | Auth matrix (login/logout/session/MFA/API keys/RBAC) | Partial — tests added; OIDC/recovery E2E still manual |
| 5 | AI security (injection / RAG / scope) | Partial — see `tests/test_ai_security.py`, `test_rag_tenancy.py` |
| 6 | AI tool policy / scope / audit | Partial — engagement scope + tool_policy |
| 7 | Scope enforcement before ops | Partial — tools/run blocks out-of-scope |
| 8 | Secrets (no defaults, `.env` not committed) | Ongoing — audit logs/prompts for leakage |

## P1 — commercial strength (next, after P0 green)

| # | Item | Status |
|---|------|--------|
| 9–12 | Canonical assets / normalizer / finding lifecycle / deterministic risk | Risk score API done; full normalizer/lifecycle still open |
| 13 | AI Investigation flagship | Done API: `POST /api/ai/investigate` |
| 14–15 | RAG tenancy + knowledge graph usefulness | RAG filter done; graph polish open |
| 16–18 | Integration E2E / reports / Stripe lifecycle | Operator + test tenants |

## P2 / P3

Onboarding, MSP, observability board (`GET /api/admin/health`), deeper test matrix, enterprise later — see `docs/closed-beta-checklist.md`.

## Short “20 things” (current)

```text
01–04  Docker/Postgres/secrets/HTTPS     → largely done (TLS DNS operator)
05–08  Isolation/RBAC/MFA/secrets        → in progress (expand API tests)
09–11  AI injection/tools/scope          → partial
12–14  Assets/findings/risk              → risk engine started
15     AI Investigation                  → shipped API
16–20  RAG/integrations/Stripe/monitor/e2e → open / operator
```

## Verify

```bash
python -m pytest tests/test_tenancy_rbac.py tests/test_cross_tenant_isolation.py \
  tests/test_auth_and_investigation.py tests/test_ai_security.py \
  tests/test_engagement_scope.py tests/test_rag_tenancy.py -q
```

## SaaS bring-up

```bash
# .env: BOOTSTRAP_ADMIN_PASSWORD, POSTGRES_PASSWORD, CORS_ORIGINS=https://...
docker compose --profile saas --profile proxy up --build -d
```
