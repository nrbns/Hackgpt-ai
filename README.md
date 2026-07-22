# HackGPT — Local Security AI

Real-time local security assistant for authorized pentesting, blue-team workflows, CTFs, and sandboxed malware analysis.

## Run

### Windows PowerShell

```powershell
.\scripts\run_proper.ps1
```

Or quick start:

```powershell
.\scripts\start.ps1
```

### Linux / macOS

```bash
bash scripts/run_proper.sh
```

Or quick start:

```bash
bash scripts/start.sh
```

Open **http://localhost:8080**

### Phones / tablets (Android & iOS)

The UI is a responsive web/PWA. Run the server on a Windows, Linux, or macOS host (`HOST=0.0.0.0`), then open a **LAN URL** from your phone (same Wi‑Fi), e.g. `http://192.168.x.x:8080`.

- **Settings** shows detected LAN URLs and API keys for every backend.
- Use **Add to Home Screen** / Install for an app-like icon.
- Model runtimes (Ollama, Hermes, Unsloth, LM Studio) stay on the host — phones are clients only.

Check host capabilities: `GET /api/platform`

## Local model backends

### Ollama

Windows:

```powershell
.\scripts\use_ollama.ps1
.\scripts\setup_ollama.ps1
```

Linux/macOS:

```bash
bash scripts/use_ollama.sh
bash scripts/setup_ollama.sh
```

Or manually:

```bash
ollama pull tinyllama
```

### LM Studio

Windows:

```powershell
.\scripts\use_lmstudio.ps1
```

Linux/macOS:

```bash
bash scripts/use_lmstudio.sh
```

Then start the LM Studio local server in **OpenAI-compatible** mode on `http://localhost:1234/v1`.

### Hermes Agent (Nous Research)

HackGPT can use [Hermes Agent](https://github.com/NousResearch/hermes-agent) as a full agent backend via its OpenAI-compatible API server (tools, memory, skills, session continuity).

Windows:

```powershell
.\scripts\use_hermes.ps1
```

Linux/macOS:

```bash
bash scripts/use_hermes.sh
```

Then:

1. Install Hermes (`install.ps1` / `install.sh` from the [Hermes docs](https://hermes-agent.nousresearch.com/docs/)).
2. Run `hermes setup` (or `hermes setup --portal`).
3. Ensure Hermes `.env` has `API_SERVER_ENABLED=true` and `API_SERVER_KEY` matching `HERMES_API_KEY` (script tries to set this; also editable in **Settings**).
4. Start `hermes gateway` (API on `http://127.0.0.1:8642/v1`).
5. Select **Hermes Agent** in the UI (or `MODEL_BACKEND=hermes`).

**HackGPT Hermes features:**

- Streaming chat with HackGPT guardrails + modes + RAG
- `X-Hermes-Session-Id` continuity (**New Hermes** button)
- `X-Hermes-Session-Key` memory scope (Settings)
- Inline **tool progress** from Hermes SSE events
- `GET /api/hermes/status` — models + capabilities

Keep Hermes bound to localhost. Scope tools to labs/VMs you own.

### Unsloth (train + infer)

[Unsloth](https://github.com/unslothai/unsloth) accelerates LoRA/QLoRA fine-tuning and can run the adapter for chat.

Windows:

```powershell
.\scripts\use_unsloth.ps1
.\.venv\Scripts\pip install unsloth
.\.venv\Scripts\pip install datasets trl peft accelerate bitsandbytes
```

Linux/macOS/WSL:

```bash
bash scripts/use_unsloth.sh
.venv/bin/pip install unsloth
.venv/bin/pip install datasets trl peft accelerate bitsandbytes
```

1. Open **Settings** in the UI and set `HF_TOKEN` if you use gated models.
2. Select **Unsloth** in the backend dropdown (or `MODEL_BACKEND=unsloth`).
3. Optional: **Train** / Settings → Start Unsloth train (uses `data/ethical_pentest_dataset.jsonl`).
4. **Preload** or send a chat to load the model (uses adapter dir if present, else `UNSLOTH_MODEL`).

CLI train:

```powershell
python -m app.fine_tune.train_unsloth --epochs 1
```

GPU + CUDA strongly recommended.

### Direct Hugging Face

Windows:

```powershell
.\scripts\use_huggingface.ps1
.\.venv\Scripts\pip install torch transformers accelerate
```

Linux/macOS:

```bash
bash scripts/use_huggingface.sh
.venv/bin/python -m pip install torch transformers accelerate
```

More details: `docs/cursor-local-models.md`

## 6 modes + quick prompts

| Mode | Focus |
|------|-------|
| Default | Pentest + defense |
| CTF | Flags, challenges |
| Lab | DVWA, Juice Shop |
| Red Team Lab | Metasploit, BEEF (VMs) |
| Blue Team | Sigma, ATT&CK, IR |
| Malware Analysis | Sandbox, YARA, IOC |

Click **quick prompts** in the UI for mode-specific starters.

## 24 RAG knowledge docs

OWASP, XSS, SQLi, CTF, HTB, THM, PortSwigger, tools, CVEs, Burp, Metasploit lab, MITRE detection, IR, malware analysis, YARA, **threat hunting**, **AD security**, **cloud security**, **Sigma library**, **network defense**, **local Evilginx training lab**, **WormGPT-style threat intel**, **stealer / clipper detection**, **C2 / exfil detection**

## UI features

- Model switcher + **Pull** for Ollama
- **Settings** panel for API keys (HF, Hermes, LM Studio), Ollama URLs, Unsloth paths, LAN tips
- Mobile-friendly layout (Android/iOS browsers) + PWA manifest / Add to Home Screen
- **Unsloth** backend with Preload + Train
- **Re-index** RAG button
- RAG document count in status bar
- Mode-specific quick prompts

## Cursor project setup

- Project rule: `.cursor/rules/authorized-security-assistant.mdc`
- Workspace settings: `.vscode/settings.json`
- Local-model guidance: `docs/cursor-local-models.md`

These keep the project aligned with authorized security work while supporting local inference.

## API

- `GET /api/health` — backend + RAG status
- `GET /api/backend` — current backend + available options
- `POST /api/backend` — switch backend (persisted to `.env`)
- `GET /api/platform` — host OS, LAN URLs, backend capabilities (Win/Linux/macOS + mobile clients)
- `GET /api/backends/probe` — which AI backends are ready + recommended auto-fallback
- `GET /api/hermes/status` — Hermes reachability, models, capabilities
- `GET /api/settings` — masked API keys + model paths
- `POST /api/settings` — update keys/URLs (persisted to `.env`; blank secrets keep existing)
- `GET /api/finetune` — Unsloth train job status
- `POST /api/finetune` — start Unsloth fine-tune (`engine=unsloth`)
- `POST /api/models/preload` — preload HuggingFace or Unsloth model
- `GET /api/modes` — modes + quick prompts
- `GET /api/status` — RAG sources list
- `POST /api/ingest` — re-index knowledge

## Smoke test

Windows:

```powershell
.\.venv\Scripts\python scripts\smoke_test.py
.\.venv\Scripts\python scripts\integration_check.py
.\.venv\Scripts\python scripts\smoke_test.py --chat
```

Linux/macOS:

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/integration_check.py
.venv/bin/python scripts/smoke_test.py --chat
```

`integration_check.py` verifies static UI, all backends, settings, platform, ingest, and chat streaming.

## Fine-tuning

Classic PEFT LoRA:

```powershell
python -m app.fine_tune.train_lora --epochs 2
```

Unsloth (faster, less VRAM — GPU recommended):

```powershell
python -m app.fine_tune.train_unsloth --epochs 1
```

Or use **Settings → Start Unsloth train** / `POST /api/finetune` in the UI.

36 training examples in `data/ethical_pentest_dataset.jsonl`
