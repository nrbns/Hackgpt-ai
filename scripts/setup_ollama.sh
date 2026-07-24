#!/usr/bin/env bash
# Ollama setup helper for SecuraIQ (Linux/macOS)
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/common.sh

echo "SecuraIQ Ollama Setup"
echo ""

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama not found. Install from: https://ollama.com/download"
  echo "Linux: curl -fsSL https://ollama.com/install.sh | sh"
  echo "macOS: brew install ollama or install the app from ollama.com"
  exit 1
fi

ollama --version
echo ""

echo "Pulling tinyllama (fast CPU default)..."
ollama pull tinyllama

echo ""
echo "Installed models:"
ollama list

set_env_value MODEL_BACKEND ollama
set_env_value OLLAMA_MODEL tinyllama

echo ""
echo "Configured .env for Ollama + tinyllama."
echo "Optional larger models: ollama pull mistral | ollama pull llama3"
echo "Start SecuraIQ: bash scripts/start.sh"
echo "Open: http://localhost:8080"