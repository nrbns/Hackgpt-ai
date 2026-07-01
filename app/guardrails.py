import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None


BLOCK_PATTERNS = [
    r"\b(clone|skim|rip)\s+(a\s+)?(credit\s+)?card",
    r"\bcredit\s+card\s+(fraud|dump|cvv|bin)",
    r"\b(stalk|doxx?|swat)\b",
    r"\b(ransomware|ransom)\s+(deploy|spread|target)",
    r"\bwithout\s+(permission|consent|authorization)\b.*\b(hack|attack|exploit|break\s+into)\b",
    r"\bhack\s+(my\s+)?(ex|neighbor|boss|school|bank|government)\b",
    r"\bsteal\s+(passwords?|credentials?|money|crypto)\b",
    r"\bdeploy\s+rootkit\b",
    r"\bkeylogger\b.*\b(install|deploy|spread)\b",
    r"\b(wormgpt|worm\s*gpt)\b",
    r"\b(self[- ]?replicat|polymorphic)\b.*\b(worm|malware|payload)\b",
    r"\b(build|write|create|code)\b.*\b(worm|botnet|ransomware|stealer|clipper)\b",
    r"\bc2\s+(server|infrastructure)\b.*\b(set\s*up|deploy|build)\b",
    r"\bexfiltrat(e|ion)\b.*\b(without|no)\s+(auth|permission|consent)\b",
    r"\b(clipper|stealer|infostealer)\b.*\b(build|write|deploy|use)\b",
    r"\bcredential\s+theft\b",
    r"\bbrowser\s+(cookie|credential)\s+steal",
    r"\btelegram\s+stealer\b",
]

REFUSAL_MESSAGE = (
    "I can't help with that request. PentestGPT only supports **authorized** security work — "
    "systems you own or have explicit written permission to test. "
    "I can help with lab setups, CTF challenges, OWASP testing methodology, malware analysis in sandboxes, and defensive hardening instead."
)


def check_request(message: str) -> GuardrailResult:
    text = message.lower().strip()
    if not text:
        return GuardrailResult(allowed=False, reason="Empty message.")

    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)

    return GuardrailResult(allowed=True)
