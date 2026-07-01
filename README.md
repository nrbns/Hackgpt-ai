# PentestGPT — Local Security AI

Real-time local security assistant for authorized pentesting, blue-team workflows, CTFs, and sandboxed malware analysis.

## Run

```powershell
.\scripts\start.ps1
```

Open **http://localhost:8080**

## Local model backends

### Ollama

```powershell
.\scripts\use_ollama.ps1
.\scripts\setup_ollama.ps1
```

Or manually:

```powershell
ollama pull llama3
```

### LM Studio

```powershell
.\scripts\use_lmstudio.ps1
```

Then start the LM Studio local server in **OpenAI-compatible** mode on `http://localhost:1234/v1`.

### Direct Hugging Face

```powershell
.\scripts\use_huggingface.ps1
.\.venv\Scripts\pip install torch transformers accelerate
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
- `POST /api/models/preload` — preload HuggingFace model
- `GET /api/modes` — modes + quick prompts
- `GET /api/status` — RAG sources list
- `POST /api/ingest` — re-index knowledge

## Smoke test

```powershell
.\.venv\Scripts\python scripts\smoke_test.py
.\.venv\Scripts\python scripts\smoke_test.py --chat
```

`--chat` sends a short message (can be slow on HuggingFace CPU).

## Fine-tuning

```powershell
python -m app.fine_tune.train_lora --epochs 2
```

36 training examples in `data/ethical_pentest_dataset.jsonl`
