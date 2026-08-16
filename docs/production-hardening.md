# SecuraIQ — Production hardening (Sprint 1)

Feature freeze is in effect for closed-beta: **validate and harden**, do not add scanners/agents/frameworks.

## Docker / Compose (done)

| Control | Status |
|---------|--------|
| `CORS_ORIGINS=*` removed from default Compose | Done — defaults to localhost origins |
| Weak bootstrap password default removed | Done — `BOOTSTRAP_ADMIN_PASSWORD` required via `.env` |
| Postgres/Redis not published to all interfaces | Done — `expose` only on saas/postgres/redis profiles |
| Debug ports bound to `127.0.0.1` only | Done — `--profile debug-ports` |
| SaaS profile: Postgres + Redis + MFA admin | Done — `docker compose --profile saas up -d` |

### Lab

```bash
# .env must include:
# BOOTSTRAP_ADMIN_PASSWORD=<strong>
docker compose up --build
```

### SaaS / staging (behind reverse proxy)

```bash
# .env:
# BOOTSTRAP_ADMIN_PASSWORD=...
# POSTGRES_PASSWORD=...
# CORS_ORIGINS=https://securaiq.example.com
docker compose --profile saas up --build -d
```

Requires `pip install 'psycopg[binary]'` in the image/venv when `DATABASE_URL` is Postgres.

**Do not** expose `5432` / `6379` on a public IP. Put Caddy/nginx in front (`deploy/`).

## Source of truth

| Edition | Database |
|---------|----------|
| Lab / community | SQLite (`DATA_DIR/securaiq.db`) OK |
| Closed beta SaaS / production | **PostgreSQL mandatory** (`DATABASE_URL`) |

## Verification commands

```bash
# Tenant isolation + AI security
python -m pytest tests/test_tenancy_rbac.py tests/test_cross_tenant_isolation.py tests/test_ai_security.py tests/test_engagement_scope.py -q

# Connectors (status only unless --sync)
python scripts/connector_verify.py --matrix
```

## Still operator-owned (not code)

- [ ] TLS cert + DNS
- [ ] Offsite backup restore drill
- [ ] Counsel review of `/legal/`
- [ ] Live Stripe prices + webhook
- [ ] Live XDR/SIEM trial tenants
