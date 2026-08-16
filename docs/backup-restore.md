# SecuraIQ — Backup & restore drill

Run this once per beta host before onboarding partners. Goal: prove you can restore after disk loss.

## What to back up

| Path / resource | Contains |
|-----------------|----------|
| `DATA_DIR/securaiq.db` (+ `-wal`/`-shm` if present) | SQLite lab DB |
| Postgres volume / dump | SaaS SoT when `DATABASE_URL` is set |
| `DATA_DIR/chroma/` | RAG embeddings |
| `.env` (offline, encrypted) | Secrets — store separately from DB backup |
| Uploaded evidence under `DATA_DIR` | Partner files |

## SQLite lab backup

```bash
# App stopped or brief maintenance window preferred
cp data/securaiq.db backups/securaiq-$(date +%Y%m%d).db
# optional: zip chroma
tar -czf backups/chroma-$(date +%Y%m%d).tgz data/chroma
```

Restore:

```bash
cp backups/securaiq-YYYYMMDD.db data/securaiq.db
# restart SecuraIQ
```

## Postgres SaaS backup

```bash
docker compose --profile saas exec postgres \
  pg_dump -U securaiq securaiq > backups/securaiq-$(date +%Y%m%d).sql
```

Restore into empty DB:

```bash
docker compose --profile saas exec -T postgres \
  psql -U securaiq securaiq < backups/securaiq-YYYYMMDD.sql
```

## Drill checklist (sign off)

- [ ] Backup taken and copied **off the app host**
- [ ] Restore into a throwaway directory / staging compose project
- [ ] Login works; org assets/findings visible for a test user
- [ ] RAG document count non-zero after chroma restore (if used)
- [ ] Date / operator initials: ________

Do not claim DR readiness until this drill has a signed date.
