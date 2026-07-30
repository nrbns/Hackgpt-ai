# SecuraIQ — Beta Deploy Guide

Deploy SecuraIQ for **closed beta / design partners** with auth, MFA, and optional SSO.

## Minimum beta configuration

```env
AUTH_ENABLED=true
AUTH_ALLOW_REGISTER=false
BOOTSTRAP_ADMIN_PASSWORD=<strong-password>
MFA_REQUIRED_FOR_ADMIN=true
HOST=0.0.0.0   # only behind firewall / reverse proxy
CORS_ORIGINS=https://securaiq.yourdomain.com
```

## Docker Compose (recommended)

```bash
export BOOTSTRAP_ADMIN_PASSWORD='your-strong-password'
export MFA_REQUIRED_FOR_ADMIN=true
docker compose up --build
```

Login: `admin` + bootstrap password. Enroll MFA via API after first login:

```bash
# 1. Login → get token
TOKEN=$(curl -s -X POST http://127.0.0.1:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"YOUR_PASSWORD"}' | jq -r .token)

# 2. Enroll MFA
curl -s -X POST http://127.0.0.1:8080/api/auth/mfa/enroll \
  -H "Authorization: Bearer $TOKEN"

# 3. Confirm with code from authenticator app
curl -s -X POST http://127.0.0.1:8080/api/auth/mfa/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"code":"123456"}'
```

**Enforcement:** with `MFA_REQUIRED_FOR_ADMIN=true`, admin accounts without MFA enrolled now get a hard `403` from every authenticated endpoint except `/api/auth/status`, `/api/auth/logout`, and the three `/api/auth/mfa/*` enrollment routes — so an admin literally cannot use the API until they enroll. Previously this flag only drove a UI prompt (`mfa_enrollment_required` in `/api/auth/status`) with no server-side block; that gap is now closed in `app/commercial_api.py::require_user`.

## Secrets encryption

API keys, tokens, and the bootstrap admin password written through Settings (or `/api/settings`) are now encrypted at rest in `.env` — values are stored as `enc:v1:<ciphertext>` instead of plaintext (`app/secrets_crypto.py`, Fernet/AES under the hood). This was a real gap: `app/secrets.py` only masked secrets in API *responses*, it never protected the `.env` file itself.

For production, set the encryption key explicitly rather than relying on the auto-generated `data/.secret.key`:

```env
ENV_SECRET_ENCRYPTION_KEY=<43-char urlsafe base64 Fernet key>
```

Generate one with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Inject it via your secrets manager / container orchestrator — not through `.env` itself (that would defeat the point). If unset, SecuraIQ auto-generates `data/.secret.key` (owner-only permissions) on first use; back that file up separately from `data/` app-data backups, per `docs/backup-dr.md`.

## OIDC / SSO (Keycloak or Authentik)

```env
OIDC_ENABLED=true
OIDC_ISSUER=https://keycloak.example/realms/securaiq
OIDC_CLIENT_ID=securaiq
OIDC_CLIENT_SECRET=<secret>
OIDC_REDIRECT_URI=https://securaiq.yourdomain.com/api/auth/oidc/callback
```

UI: **Account → Sign in with SSO** or visit `/api/auth/oidc/login`.

## GitHub live connector

1. Set `GITHUB_WEBHOOK_SECRET` in Settings or `.env`.
2. In GitHub repo/org → Webhooks → URL: `https://your-host/api/integrations/github/webhook`
3. Events: **Code scanning alerts**, **Dependabot alerts**, **Secret scanning alerts**
4. Verify: `GET /api/integrations/github/status`

## TLS (production)

SecuraIQ itself binds plain HTTP (`HOST`/`PORT`) — TLS termination is handled by a reverse proxy in front of it, which is standard practice and keeps cert renewal out of the app's own process. Two ready-to-use configs:

- `deploy/Caddyfile` — Caddy auto-provisions and renews Let's Encrypt certs for you; just point DNS at the host and run `caddy run --config deploy/Caddyfile`.
- `deploy/nginx.conf.example` — nginx + certbot, for teams already standardized on nginx.

Both configs disable proxy buffering on `/api/chat`, `/api/realtime`, and `/api/tools/run/stream` since those are SSE streams — buffering them turns streaming responses into one big delayed chunk.

**What you still have to do yourself:** own a domain, point its DNS A/AAAA record at this host, and run the cert issuance step (Caddy does this automatically on first request; nginx needs `certbot` run once). That's infrastructure only you control — not something achievable from inside the codebase.

## Postgres / Redis (optional SaaS profile)

```bash
docker compose --profile saas up -d
export DATABASE_URL=postgresql://securaiq:securaiq@127.0.0.1:5432/securaiq
export REDIS_URL=redis://127.0.0.1:6379/0
```

See [postgres-migration.md](./postgres-migration.md) — full PG adapter is staged; SQLite remains default for alpha.

## Local dev with auth on

```powershell
# .env
AUTH_ENABLED=true
BOOTSTRAP_ADMIN_PASSWORD=change-me-local
.\scripts\start.ps1
```

## Beta exit checklist

See [launch-readiness.md](./launch-readiness.md) Stage 2 (Closed Beta) and [commercial-roadmap.md](./commercial-roadmap.md).
