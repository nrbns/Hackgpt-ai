"""Request guardrails — block clear criminal misuse, allow full authorized cyber research."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None


# Narrow blocks: real-world crime / unauthorized targeting — not normal pentest vocabulary.
BLOCK_PATTERNS = [
    r"\b(clone|skim|rip)\s+(a\s+)?(credit\s+)?card",
    r"\bcredit\s+card\s+(fraud|dump|cvv|bin)",
    r"\b(stalk|doxx?|swat)\b",
    r"\b(ransomware|ransom)\s+(deploy|spread)\b.*\b(company|hospital|victim|production)\b",
    r"\bwithout\s+(permission|consent|authorization)\b.*\b(hack|attack|exploit|break\s+into)\b",
    r"\bhack\s+(my\s+)?(ex|neighbor|boss|school|bank|government)\b",
    r"\b(steal|phish|breach)\b.*\b(my\s+)?(ex|neighbor|boss|girlfriend|boyfriend)\b",
    r"\b(wormgpt|worm\s*gpt|evilgpt|evil\s*gpt|fraudgpt|fraud\s*gpt)\b",
    r"\b(build|write|create)\b.*\b(botnet|ransomware)\b.*\b(deploy|spread|sell)\b",
    r"\btelegram\s+stealer\b.*\b(build|sell|spread)\b",
    # Crimeware-assistant / “zero safety” framing (not authorized lab technique questions)
    r"\bzero\s*safety\b",
    r"\bturn\s+it\s+into\s+a\s+weapon\b",
    r"\bweaponize\b.*\b(ai|model|llm|securaiq)\b",
    r"\b(uncensored|jailbreak)\b.*\b(model|llm|gpt)\b.*\b(malware|botnet|crime|steal|c2)\b",
    r"\bself[- ]improv\w*\b.*\b(exploit|payload|poc)\b.*\b(fine[- ]?tun|nightly|reload)\b",
    r"\b(tor|onion)\b.*\b(hidden\s+service|hiddenservice)\b.*\b(securaiq|gradio|c2|payload)\b",
    r"\bautonomous\b.*\b(pentest\s+drone|payload\s+deploy|deploy\s+payloads)\b",
]

# Phrases that indicate authorized / educational context → never hard-block on dual-use wording
ALLOW_CONTEXT = re.compile(
    r"(?:"
    r"\b("
    r"lab|ctf|htb|hackthebox|tryhackme|thm|portswigger|dvwa|webgoat|juice\s*shop|"
    r"metasploitable|vulnhub|authorized|engagement|scope|pentest|red\s*team|"
    r"blue\s*team|purple\s*team|malware\s*analysis|sandbox|yara|sigma|detection|mitigation|"
    r"lab\s*offensive|owned\s*vm|local\s*lab|owasp|cve-\d{4}|writeup|forensics|incident\s*response|"
    r"vulnerabilit\w*|assessment|in[\s-]?scope|engagement\s*scope|"
    r"ciso|awareness|phishing\s*simulat|gophish|knowbe4|tabletop|"
    r"greenbone|openvas|burp|acunetix|zap|iso\s*27001|nist\s*csf|cis\s*control|"
    r"soc\s*2|pci\s*dss|asvs|remediation|evidence|gap\s*analysis|mission\s*control"
    r")\b|"
    r"\b(?:192\.168\.|10\.\d+\.|172\.(?:1[6-9]|2\d|3[0-1])\.)\d"
    r")",
    re.IGNORECASE,
)

REFUSAL_MESSAGE = (
    "I can't help with that request. SecuraIQ only supports **authorized** security work — "
    "systems you own or have explicit written permission to test. "
    "It is **not** a crimeware / EvilGPT / zero-safety assistant. "
    "I can help with lab setups, CTFs, scanner import (Trivy/Semgrep/Gitleaks), "
    "gap analysis, risk/vuln registers, malware **analysis** in sandboxes, and defensive hardening instead."
)


def check_request(message: str) -> GuardrailResult:
    text = message.lower().strip()
    if not text:
        return GuardrailResult(allowed=False, reason="Empty message.")

    # Hard crimeware-assistant asks are refused even if mixed with lab words
    for pattern in (
        r"\b(wormgpt|worm\s*gpt|evilgpt|evil\s*gpt|fraudgpt)\b",
        r"\bzero\s*safety\b",
        r"\bturn\s+it\s+into\s+a\s+weapon\b",
    ):
        if re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)

    # Educational / scoped cyber language is allowed even if dual-use terms appear
    if ALLOW_CONTEXT.search(text):
        return GuardrailResult(allowed=True)

    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)

    return GuardrailResult(allowed=True)
