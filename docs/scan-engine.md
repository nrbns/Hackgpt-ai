# SecuraIQ Scan Engine

## Scanners (all engine-enabled)

| Id | Requires | Best for |
|----|----------|----------|
| `securaiq` | nothing | Always-on discovery |
| `nmap` | `nmap` on PATH / Docker image | Ports / services |
| `nuclei` | `nuclei` on PATH / Docker image | Web / CVE templates |
| `zap` | OWASP ZAP / `zap-baseline.py` | Web config, XSS, headers |

## Flow

```text
POST /api/scans → queued → scan_execute
  → scope + authorization
  → securaiq | nmap | nuclei | zap
  → evidence/scans/{id}/
  → normalize → assets + findings
```

AI interprets findings later. It does **not** run scanners.

## Batch: all available scanners

```http
POST /api/scans
{ "target": "192.168.56.101", "scanner": "all", "profile": "full", "authorized": true }
```

Queues every scanner that is installed (`securaiq` always; plus nmap/nuclei/zap when on PATH). Response includes `scans[]` and `skipped[]`.

## Docker build

```bash
docker compose build
# Nmap + Nuclei always; ZAP included when INSTALL_ZAP=true (default)
docker compose build --build-arg INSTALL_ZAP=false   # smaller image
```

## Lab tip

Scan the **VM IP** (e.g. `192.168.56.101`), not the VirtualBox host gateway `.1`.
Private Windows ports 135/139/445 are down-ranked to **info** and de-duped across tools.

## Reports

On completion the engine writes `evidence/scans/{id}/report.md` and exposes:

- `GET /api/scans/{id}/report` — download Markdown report
- `GET /api/scans/{id}/report.pdf` — same report as PDF (VA export)
- **Reports** workspace — each completed scan appears as MD + PDF cards
- `POST /api/scans/clear` — remove old scans, evidence, and scan/tool findings before a fresh run
