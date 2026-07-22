"""Persist runtime settings to .env for restart survival."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def ensure_env_file() -> None:
    if ENV_PATH.exists():
        return
    if ENV_EXAMPLE.exists():
        ENV_PATH.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        ENV_PATH.write_text("MODEL_BACKEND=ollama\n", encoding="utf-8")


def update_env_value(key: str, value: str) -> None:
    ensure_env_file()

    raw = ENV_PATH.read_bytes()
    # Detect newline style from file bytes
    if b"\r\n" in raw:
        newline = "\r\n"
        text = raw.decode("utf-8").replace("\r\n", "\n")
    else:
        newline = "\n"
        text = raw.decode("utf-8").replace("\r", "\n")

    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"

    if pattern.search(text):
        text = pattern.sub(line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"

    ENV_PATH.write_bytes(text.replace("\n", newline).encode("utf-8"))
