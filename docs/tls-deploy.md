# SecuraIQ — TLS / reverse proxy deploy

DNS + certificate issuance are operator steps. App configs are ready under `deploy/`.

## Recommended (Caddy)

1. Point `A`/`AAAA` for `securaiq.yourdomain.com` at the host
2. Edit `deploy/Caddyfile` — replace the domain
3. Ensure SecuraIQ listens on `127.0.0.1:8080` (or compose published only to localhost via proxy)
4. Set `CORS_ORIGINS=https://securaiq.yourdomain.com`
5. Run:

```bash
caddy run --config deploy/Caddyfile
```

SSE paths (`/api/chat`, `/api/realtime`, `/api/tools/run/stream`) already flush without buffering.

## Alternative (nginx + certbot)

1. `certbot certonly --nginx -d securaiq.yourdomain.com`
2. Copy `deploy/nginx.conf.example` → site config; fix cert paths + domain
3. `nginx -t && systemctl reload nginx`

## Checklist

- [ ] HTTPS redirects from HTTP
- [ ] HSTS header present
- [ ] Chat streaming works over HTTPS
- [ ] `CORS_ORIGINS` matches the HTTPS origin (no `*`)
- [ ] App not exposed on `:8080` to the public internet (proxy only)
