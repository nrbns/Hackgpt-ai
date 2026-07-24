#!/usr/bin/env bash
# One-command setup + start for SecuraIQ (Linux/macOS)
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/common.sh

echo "SecuraIQ setup"
ensure_venv

echo "Installing dependencies..."
python -m pip install -r requirements.txt -q
ensure_env

if command -v ollama >/dev/null 2>&1; then
  echo "Ollama found - configuring Ollama backend."
  bash scripts/use_ollama.sh >/dev/null
  if ollama list 2>/dev/null | grep -q "tinyllama"; then
    echo "TinyLlama model ready."
  else
    echo "Pulling tinyllama model (one-time download)..."
    ollama pull tinyllama
  fi
else
  echo "Ollama not found - using HuggingFace CPU model (Qwen2.5-0.5B)."
  python -m pip install torch transformers accelerate -q
  set_env_value MODEL_BACKEND huggingface
  set_env_value HF_MODEL Qwen/Qwen2.5-0.5B-Instruct
fi

echo "Indexing RAG knowledge base..."
python scripts/ingest_rag.py

stop_port_8080

echo ""
echo "Starting SecuraIQ at http://localhost:8080"
python run.py