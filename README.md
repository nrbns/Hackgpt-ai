# SecuraIQ

**Local security AI workspace** for authorized pentesting, blue-team / SOC workflows, CTFs, GRC, and sandboxed malware analysis.

On-prem friendly. Not a ChatGPT clone — Mission Control, engagements, scanners, RAG, and local or cloud model backends.

> Use only on labs, VMs, CTFs (HTB / THM / PortSwigger), or systems you own and are authorized to test.

---

## Quick start (no `.env` editing)

You never need to create or edit a `.env` by hand. Start scripts create the venv, copy `.env.example` → `.env`, and boot the server. Optional API keys go in **Settings** in the UI later.

### Requirements

- [Python 3.11+](https://www.python.org/downloads/) on PATH (Windows: tick **Add python.exe to PATH**)
- Internet once for `pip` (and optional model download)

### Windows

```powershell
git clone https://github.com/nrbns/Hackgpt-ai.git
cd Hackgpt-ai
.\run_proper.cmd
```

After the first setup, double-click or run:

```powershell
.\start.cmd
```

Open **http://127.0.0.1:8080**

| Command | Purpose |
|---------|---------|
| `.\run_proper.cmd` | First-time setup + start |
| `.\start.cmd` | Start only (localhost) |
| `.\scripts\start.cmd -Lan` | Start reachable on Wi‑Fi (phones) |
| `.\scripts\enable_secure_mode.cmd` | Turn on login + lock register |

### Linux / macOS

```bash
git clone https://github.com/nrbns/Hackgpt-ai.git
cd Hackgpt-ai
bash scripts/run_proper.sh
# later:
bash scripts/start.sh
```

### Docker

```bash
export BOOTSTRAP_ADMIN_PASSWORD='your-strong-password'
docker compose up --build
```

Auth is on by default in Compose. Sign in as `admin`.

Optional profiles:

```bash
docker compose --profile vectors up -d    # Qdrant
docker compose --profile prefect up -d    # Prefect UI
```

---

## How to use

1. Open **Mission Control** (starts at score **0** / empty workspace).
2. **Import a scan** (Vulnerabilities) or run **Gap analysis**.
3. Triage findings → remediations → optional Jira.
4. Use chat agents (SOC, XDR, CISO, …) for authorized lab work.
5. Connect Wazuh / Slack / webhooks under **Integrations** when ready.

**In-app manual:** http://127.0.0.1:8080/manual/ · source: [`docs/user-manual.md`](docs/user-manual.md)

### Secured mode (password login)

Default lab mode is open on **localhost only**. For a gated install:

```powershell
.\scripts\enable_secure_mode.cmd
.\start.cmd
```

This enables auth, disables public registration, binds `127.0.0.1`, and prints an `admin` password once.

### Zero-start vs keep data

| Setting | Default | Meaning |
|---------|---------|---------|
| `HOST` | `127.0.0.1` | Localhost only (use `-Lan` for Wi‑Fi) |
| `AUTH_ENABLED` | `false` | Open lab on localhost |
| `WORKSPACE_ZERO_START` | `true` | Wipe local workspace on each start when auth is off |
| `AUTH_ALLOW_REGISTER` | `false` | No public signup when auth is on |

Set `WORKSPACE_ZERO_START=false` (or use secured mode) to keep assets and findings across restarts.

---

## Features

- **Mission Control** — security score, KPIs, first-run checklist, morning brief
- **18 agent modes** — CTF, red/blue/purple, XDR, IR, cloud, AppSec, CISO, awareness, …
- **Gap analysis** — ISO / NIST / CIS controls + remediations
- **Vuln import** — CSV / JSON / XML + lab fixtures
- **SOC / XDR** — incidents, detections, optional **Wazuh** sync
- **Threat intel** — KEV, NVD, free intel APIs, password exposure check (k-anonymity)
- **Automation** — background jobs + optional Prefect
- **RAG** — local knowledge base (Re-index in UI)
- **PWA** — installable on phone/tablet browsers

### Model backends (optional)

First start prefers **Ollama** if installed, otherwise the configured Hugging Face path. Switch anytime in **Settings** or with scripts:

| Backend | Windows | Linux / macOS |
|---------|---------|---------------|
| Ollama | `.\scripts\use_ollama.cmd` | `bash scripts/use_ollama.sh` |
| LM Studio | `.\scripts\use_lmstudio.ps1` | `bash scripts/use_lmstudio.sh` |
| Hermes Agent | `.\scripts\use_hermes.ps1` | `bash scripts/use_hermes.sh` |
| Unsloth | `.\scripts\use_unsloth.ps1` | `bash scripts/use_unsloth.sh` |
| Hugging Face | `.\scripts\use_huggingface.ps1` | `bash scripts/use_huggingface.sh` |
| Wazuh SIEM | `.\scripts\use_wazuh.cmd` | — (prompted SecureString password) |

---

## Modes

| Mode | Focus |
|------|-------|
| Default | Pentest + defense |
| CTF / Lab | Flags, DVWA, Juice Shop |
| Red / Blue / Purple | Attack, detect, fix loops |
| Threat hunt / XDR | Hypothesis hunts, alert correlation |
| IR | Containment playbooks |
| Malware lab | Sandbox, YARA, IOC (authorized samples) |
| Cloud / AppSec | Posture + ASVS |
| CISO / Awareness / Tabletop | GRC, phishing sims, exercises |

---

## Verify install

With the server running:

```powershell
.\.venv\Scripts\python scripts\smoke_test.py
.\.venv\Scripts\python scripts\check_openapi_gets.py
.\.venv\Scripts\python scripts\commercial_integration_check.py
```

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/check_openapi_gets.py
```

---

## API (high level)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Backend + RAG status |
| `GET /api/dashboard` | Mission Control data |
| `GET /api/settings` | Masked settings (secrets never cleartext) |
| `POST /api/chat` | Streaming chat |
| `GET /api/platform` | OS + LAN URLs |
| `GET /api/wazuh/status` | Wazuh connector |
| `POST /api/intel/password/check` | HIBP k-anonymity (body only) |

Full OpenAPI: http://127.0.0.1:8080/docs

---

## Docs

| Doc | Topic |
|-----|--------|
| [`docs/user-manual.md`](docs/user-manual.md) | End-user guide |
| [`docs/enterprise-integrations.md`](docs/enterprise-integrations.md) | Connectors |
| [`docs/security-baseline.md`](docs/security-baseline.md) | Hardening checklist |
| [`docs/commercial-roadmap.md`](docs/commercial-roadmap.md) | Product roadmap |
| [`docs/launch-readiness.md`](docs/launch-readiness.md) | Ship checklist |
| [`docs/cursor-local-models.md`](docs/cursor-local-models.md) | Local models in Cursor |

---

## Project layout

```
app/           FastAPI backend
static/        Web UI (primary)
scripts/       Zero-config start + backend helpers
data/knowledge RAG corpus
docs/          Manuals and runbooks
```

Cursor rule for authorized-only security work: [`.cursor/rules/authorized-security-assistant.mdc`](.cursor/rules/authorized-security-assistant.mdc)

---

## License / use

Authorized security work only. Do not use this project for unauthorized access, malware deployment, or credential theft.
