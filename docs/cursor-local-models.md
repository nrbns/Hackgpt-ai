# Cursor Local Models

This project supports safe local-model workflows with **Ollama**, **LM Studio**, or direct **Hugging Face Transformers** inference.

## Option 1: Ollama

1. Install [Ollama](https://ollama.com).

Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

macOS:

```bash
brew install ollama
```

2. Pull a model:

```bash
ollama pull tinyllama
```

For better quality (larger download): `ollama pull mistral`

3. In `.env`, use:

```env
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=tinyllama
```

4. Start the app:

Windows:

```powershell
.\scripts\start.ps1
```

Linux/macOS:

```bash
bash scripts/start.sh
```

## Option 2: LM Studio

1. Install [LM Studio](https://lmstudio.ai/).
2. Load a local model in LM Studio.
3. Start the local server in **OpenAI-compatible** mode on `http://localhost:1234/v1`.
4. In `.env`, use:

```env
MODEL_BACKEND=openai_compat
OPENAI_COMPAT_BASE_URL=http://localhost:1234/v1
OPENAI_COMPAT_MODEL=local-model
OPENAI_COMPAT_API_KEY=lm-studio
```

Replace `OPENAI_COMPAT_MODEL` with the model name exposed by LM Studio if needed.

## Option 3: Direct Hugging Face inference

1. Install optional packages:

Windows:

```powershell
.\.venv\Scripts\pip install torch transformers accelerate
```

Linux/macOS:

```bash
.venv/bin/python -m pip install torch transformers accelerate
```

2. Switch the app config:

Windows:

```powershell
.\scripts\use_huggingface.ps1
```

Linux/macOS:

```bash
bash scripts/use_huggingface.sh
```

3. In `.env`, confirm:

```env
MODEL_BACKEND=huggingface
HF_MODEL=Qwen/Qwen2.5-0.5B-Instruct
```

4. Start the app:

Windows:

```powershell
.\scripts\start.ps1
```

Linux/macOS:

```bash
bash scripts/start.sh
```

This backend runs inference directly in Python. On **CPU-only** machines, use `Qwen/Qwen2.5-0.5B-Instruct` for practical response times.

## Cursor usage

Use Cursor normally while pointing this app at a local backend. Do not modify Cursor binaries or disable safety systems.

Recommended project behavior:

- Use local models for privacy/offline workflows
- Keep prompts scoped to authorized pentests, blue-team work, CTFs, and sandbox analysis
- Prefer `tinyllama` or `mistral` on CPU; `llama3` if you have more RAM
- Prefer code-focused models for scripting help in labs

## Verify the backend

Open:

- `http://localhost:8080/api/health`
- `http://localhost:8080/api/status`

The health response shows the active backend, model, and indexed RAG documents.
