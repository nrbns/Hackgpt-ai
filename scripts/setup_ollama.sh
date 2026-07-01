#!/usr/bin/env bash
# Ollama setup helper for PentestGPT (Linux/macOS)
# Usage: bash scripts/setup_ollama.sh

set -e

MODELS=("llama3" "mistral" "codellama")

echo "PentestGPT Ollama Setup"
echo ""

if ! command -v ollama &> /dev/null; then
    echo "Ollama not found. Install from: https://ollama.com/download"
    exit 1
fi

ollama --version
echo ""

for model in "${MODELS[@]}"; do
    echo "Pulling $model ..."
    ollama pull "$model"
done

echo ""
echo "Installed models:"
ollama list

echo ""
echo "Start PentestGPT: python run.py"
echo "Open: http://localhost:8080"
