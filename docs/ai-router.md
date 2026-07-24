# SecuraIQ AI Router

There is no single “cybersecurity-pretrained” API that replaces scanners, frameworks, and threat intel. SecuraIQ routes each question by **intent**, then combines a **general LLM** with knowledge bases, scanner imports, and feeds.

```
User Question → Intent Router → Agent lane
                    │
     ┌──────────────┼──────────────┐
     │              │              │
   Code         Compliance     Threat Intel
     │              │              │
 Qwen Coder /    Claude-class    NVD + CISA KEV
 OpenRouter      / OpenAI        + MITRE + AI
```

## Why a router

| Need | Better source than a single model |
|------|-----------------------------------|
| Reasoning / reports | OpenAI, Anthropic (via OpenRouter), Gemini, Groq, Together, Fireworks, or local Ollama |
| Code review | Coder models + Semgrep / Gitleaks / Trivy imports |
| Compliance | Framework JSON + RAG (ISO, NIST, CIS, SOC 2, PCI, ASVS) |
| Threat intel | CISA KEV, NVD, MITRE — AI interprets, does not invent CVEs |
| Scans | Proven tools; AI writes findings & remediations |

**Do not** build the product on an “uncensored cybersecurity model.” Enterprise value is accuracy, citations, predictable behavior, and controls — not removed safeguards.

## Lanes & agents

| Intent | Agent role | Typical enrichments |
|--------|------------|---------------------|
| `code` | Secure Code Reviewer | Scanners |
| `compliance` | Compliance Officer | Framework RAG |
| `threat_intel` | Threat Hunter / SOC | KEV snapshot |
| `report` | Executive Report Writer | Frameworks + graph |
| `scan` | Assessment interpreter | Tools / scanner JSON |
| `cloud` | Cloud Security Advisor | IAM / config reasoning |
| `general` | Security advisor | Current backend |

## Providers

**Local:** Ollama, LM Studio (`openai_compat`), Hermes, Hugging Face, Unsloth.

**Cloud (OpenAI-compatible):** OpenAI, OpenRouter, Groq, Together AI, Fireworks.

- Set keys in **Settings → AI Router / Cloud providers** or `.env` (see `.env.example`).
- With `ROUTER_ENABLED=true` and no cloud keys, intent still runs; chat stays on `MODEL_BACKEND`.
- With keys, the router may switch the stream to a recommended cloud backend for that turn.

## API

- `GET /api/router` — provider catalog, lanes, agents
- `POST /api/router/plan` — `{ "message", "mode" }` → intent plan
- Chat stream markers: `[[live:route:intent]]`, `[[router:Agent|intent|backend]]`

## Config knobs

| Env | Purpose |
|-----|---------|
| `ROUTER_ENABLED` | Master switch |
| `OPENAI_*` / `OPENROUTER_*` / `GROQ_*` / `TOGETHER_*` / `FIREWORKS_*` | Cloud endpoints |
| `OLLAMA_CODER_MODEL` | Code lane when on Ollama |
| `ROUTER_CODE_MODEL` etc. | Preferred model ids per lane |

See also [open-source-architecture.md](./open-source-architecture.md) for scanners, intel feeds, and frameworks.
