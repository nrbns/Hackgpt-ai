#!/usr/bin/env bash
# One-command setup + start for SecuraIQ (Linux/macOS)
# Secure localhost by default; pass --lan for Wi-Fi devices
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/common.sh

LAN=0
for arg in "$@"; do
  case "$arg" in
    --lan|-Lan) LAN=1 ;;
  esac
done

echo "SecuraIQ setup"
ensure_venv
echo "Installing / verifying Python packages..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if ! python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "ERROR: fastapi still missing after install. Try: rm -rf .venv && ./run_proper.sh" >&2
  exit 1
fi
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

if [ "$LAN" -eq 1 ]; then
  set_env_value HOST 0.0.0.0
  set_env_value CORS_ORIGINS "*"
  set_env_value WORKSPACE_ZERO_START false
else
  set_env_value HOST 127.0.0.1
  set_env_value CORS_ORIGINS "http://127.0.0.1:8080,http://localhost:8080"
fi

stop_port_8080

echo ""
if [ "$LAN" -eq 1 ]; then
  echo "Starting SecuraIQ (LAN mode) at http://0.0.0.0:8080"
  echo "  Or: ./start_lan.sh"
else
  echo "Starting SecuraIQ (secure — localhost) at http://127.0.0.1:8080"
  echo "For phones: ./start_lan.sh"
fi
python run.py
