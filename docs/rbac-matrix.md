# SecuraIQ — RBAC Matrix (beta)

**Roles:** `admin` (global) · `user` (global) · org roles: `admin` · `analyst` · `viewer`

When `AUTH_ENABLED=false`, all API writes use synthetic user `local` with `admin` role (lab mode).

## Global roles

| Capability | admin | user | local (auth off) |
|------------|:-----:|:----:|:----------------:|
| All workspace CRUD | ✓ | ✓ | ✓ |
| View audit log | ✓ | ✗ | ✓ |
| Export audit CSV | ✓ | ✗ | ✓ |
| Create API keys | ✓ | ✓ | ✗ |
| MFA enroll/disable (self) | ✓ | ✓ | n/a |
| Settings (incl. secrets) | ✓ | ✓ | ✓ |
| Workspace reset | ✓ | ✓ | ✓ |

## Org roles (`/api/orgs/{id}/members`)

| Capability | org admin | analyst | viewer |
|------------|:---------:|:-------:|:------:|
| Invite member | ✓ | ✗ | ✗ |
| List members | ✓ | ✓ | ✓ |
| Evidence links | ✓ | ✓ | read |

Org checks enforced in `app/commercial_ext.py` — viewer is read-only for org admin actions.

## Auth endpoints

| Route | Auth | Notes |
|-------|------|-------|
| `POST /api/auth/login` | Public | Returns `mfa_required` when MFA on |
| `POST /api/auth/mfa/verify` | Public | Completes MFA step-up |
| `POST /api/auth/mfa/enroll` | User | Returns TOTP secret + otpauth URI |
| `POST /api/auth/mfa/confirm` | User | Enables MFA |
| `GET /api/auth/oidc/login` | Public | Redirect to IdP |
| `GET /api/auth/oidc/callback` | Public | OIDC callback → session |

## Integration webhooks

| Route | Auth | Notes |
|-------|------|-------|
| `POST /api/integrations/github/webhook` | HMAC secret | No session; attributes to first admin |

## Hardening notes

- Enforce `MFA_REQUIRED_FOR_ADMIN=true` on beta/production deploys.
- Enable `AUTH_ENABLED=true`; disable open registration (`AUTH_ALLOW_REGISTER=false`) for team use.
- Review write routes periodically — new endpoints must use `require_user` and org checks where applicable.

See [beta-deploy.md](./beta-deploy.md) · [security-baseline.md](./security-baseline.md)
