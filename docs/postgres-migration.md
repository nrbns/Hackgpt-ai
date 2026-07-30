# SecuraIQ — Postgres Migration (planned)

**Status:** Compose profiles + `DATABASE_URL` config shipped; **SQLite remains the default runtime** for alpha. SQLAlchemy migration is the next engineering milestone.

## Why migrate

- Multi-tenant SaaS concurrency
- Connection pooling for background jobs
- Enterprise backup/restore expectations

## Compose profiles

```bash
# Postgres only
docker compose --profile postgres up -d postgres

# Postgres + Redis (SaaS staging)
docker compose --profile saas up -d
```

Environment:

```env
DATABASE_URL=postgresql://securaiq:securaiq@127.0.0.1:5432/securaiq
REDIS_URL=redis://127.0.0.1:6379/0
```

## Migration plan (engineering)

| Phase | Work |
|-------|------|
| 1 | Alembic + SQLAlchemy models mirroring `app/db.py` schema |
| 2 | Dual-backend `get_conn()` — SQLite if `DATABASE_URL` empty |
| 3 | Data export/import script SQLite → Postgres |
| 4 | CI matrix against Postgres |
| 5 | Default Compose SaaS profile to Postgres |

## Tables to migrate

All tables in `app/db.py` `init_schema` plus commercial_ext org tables, webhooks, entity_links, intel cache.

## Redis usage (when enabled)

- Rate limit buckets (replace in-memory middleware)
- Session store (optional)
- Job queue for report scheduling (future)

Until Redis adapter lands, `REDIS_URL` is reserved and reported in `/api/settings`.

## Rollback

Keep SQLite backup of `data/securaiq.db` before any cutover. Beta partners should stay on SQLite until PG path is CI-green.
