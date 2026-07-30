# SecuraIQ — Security Baseline (self-host)

Lightweight hardening checklist for beta/production SecuraIQ deployments.

## Network

- [ ] Bind `HOST=127.0.0.1` for local-only, or `0.0.0.0` only behind firewall + TLS reverse proxy
- [ ] Restrict CORS to known origins (never `*` in production)
- [ ] Do not expose Ollama/Hermes/LM Studio ports to the internet

## Authentication

- [ ] `AUTH_ENABLED=true`
- [ ] `AUTH_ALLOW_REGISTER=false` for team deploys
- [ ] Strong `BOOTSTRAP_ADMIN_PASSWORD`; rotate after first login
- [ ] `MFA_REQUIRED_FOR_ADMIN=true`
- [ ] OIDC SSO for team login where available
- [ ] Revoke unused API keys (`DELETE /api/auth/api-keys/{id}`)

## Application

- [ ] Rate limits enabled (defaults in `.env`)
- [ ] Secrets in `.env` only — not in git
- [ ] `GITHUB_WEBHOOK_SECRET` set if using live GitHub connector
- [ ] Intel API keys scoped to minimum required providers
- [ ] Upload limit `UPLOAD_MAX_MB` appropriate for tenant

## Data

- [ ] Backup `data/securaiq.db` and `data/chroma/` regularly
- [ ] Audit export monthly: `GET /api/audit/export` (admin)
- [ ] Workspace reset tested for offboarding: `POST /api/workspace/reset`

## Legal / process

- [ ] Counsel review of `/legal/*` before customer data
- [ ] Authorized use policy communicated to users (labs / owned systems only)
- [ ] Incident response contact published

## Threat model (summary)

| Threat | Mitigation |
|--------|------------|
| Stolen session token | HTTPS, short session hygiene, MFA |
| Brute-force login | Rate limit on `/api/auth/login` |
| Webhook spoofing | HMAC verification (GitHub) |
| Prompt injection via RAG | Guardrails + human review for actions |
| Data exfil via cloud AI | Local backends default; cloud keys optional |

See [rbac-matrix.md](./rbac-matrix.md) · [beta-deploy.md](./beta-deploy.md)
