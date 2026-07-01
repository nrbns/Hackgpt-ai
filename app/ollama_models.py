"""Ollama model management helpers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings

RECOMMENDED_MODELS = [
    {
        "id": "llama3",
        "name": "Llama 3 8B",
        "pull": "llama3",
        "description": "Strong general reasoning; good for methodology and writeups.",
    },
    {
        "id": "llama3.1",
        "name": "Llama 3.1 8B",
        "pull": "llama3.1",
        "description": "Updated Llama 3; better instruction following.",
    },
    {
        "id": "mistral",
        "name": "Mistral 7B",
        "pull": "mistral",
        "description": "Fast, efficient default for local chat.",
    },
    {
        "id": "codellama",
        "name": "Code Llama 7B",
        "pull": "codellama",
        "description": "Best for exploit scripts, payloads, and code-heavy answers.",
    },
    {
        "id": "deepseek-coder",
        "name": "DeepSeek Coder 6.7B",
        "pull": "deepseek-coder:6.7b",
        "description": "Strong coding assistant for CTF and scripting.",
    },
]


async def ollama_reachable() -> bool:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            return (await client.get(url)).status_code == 200
    except httpx.HTTPError:
        return False


async def list_installed_models() -> list[str]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return []
            data = response.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except httpx.HTTPError:
        return []


async def pull_model(model_name: str) -> AsyncIterator[str]:
    """Stream pull progress from Ollama."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/pull"
    payload = {"name": model_name, "stream": True}
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    yield f"Error {response.status_code}: {body.decode()}"
                    return
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    status = data.get("status", "")
                    if status:
                        yield status + "\n"
                    if data.get("error"):
                        yield f"Error: {data['error']}\n"
    except httpx.ConnectError:
        yield "Cannot connect to Ollama. Install from https://ollama.com and start the service.\n"
