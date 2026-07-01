"""Persist runtime settings to .env for restart survival."""

from __future__ import annotations

import re
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def update_env_value(key: str, value: str) -> None:
    if not ENV_PATH.exists():
        return

    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    text = ENV_PATH.read_text(encoding="utf-8")

    if pattern.search(text):
        text = pattern.sub(line, text)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"

    ENV_PATH.write_text(text, encoding="utf-8")
