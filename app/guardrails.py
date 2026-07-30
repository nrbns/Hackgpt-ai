"""Request guardrails — block clear criminal misuse, allow full authorized cyber research.

Hard-blocks ransomware / worm / botnet / stealer *kits* even when framed as “lab,”
“educational,” or “no warnings.” Malware **analysis**, IR, and detection remain allowed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None


REFUSAL_MESSAGE = (
    "I can't help with that request. SecuraIQ refuses **deployable malware kits** "
    "(ransomware, worms, botnets, stealers, C2 implants) — including “encrypt all files,” "
    "“no warnings,” or crimeware-style prompts — even if framed as a lab exercise.\n\n"
    "I **can** help with authorized work instead:\n"
    "- Malware **analysis** of samples you own in a sandbox (REMnux / FLARE / snapshot VM)\n"
    "- **Detection** (YARA / Sigma / KQL) and IR playbooks for ransomware\n"
    "- Lab offensive techniques on CTF / HTB / owned VMs (without mass-encrypt kits)\n"
    "- Gap analysis, risk/vuln registers, scanner import, awareness tabletops\n\n"
    "Switch to **malware** or **IR** mode for sandbox analysis and defensive guidance."
)

# Always refuse kit-building / mass-encrypt asks (even with lab/CTF framing).
HARD_BLOCK_PATTERNS = [
    r"\b(write|create|build|generate|code|implement|develop|make|craft)\b.{0,100}\b(ransomware|ransom[\s_-]?ware)\b",
    r"\b(ransomware|ransom[\s_-]?ware)\b.{0,100}\b(script|python|powershell|batch|encryptor|encrypts?|kit|builder|payload)\b",
    r"\bencrypt(s|ing)?\b.{0,80}\b(all|every|entire)\b.{0,60}\b(files?|documents?|folder|directory|drive|disk|computer|home\s*dir)\b",
    r"\b(mass|bulk|recursive)\s*encrypt",
    r"\bencrypt.{0,40}\b(current\s+directory|cwd|workdir|home\s*folder)\b",
    r"\bno\s+warnings?\b.{0,120}\b(ransomware|ransom|encrypt|malware|worm|botnet|stealer|c2)\b",
    r"\b(ransomware|ransom|encrypt|malware|worm|botnet|stealer)\b.{0,120}\bno\s+warnings?\b",
    r"\b(write|create|build|generate|code|implement|develop|make)\b.{0,80}\b(botnet|worm)\b",
    r"\b(write|create|build|generate|code|implement|develop|make)\b.{0,80}\b(stealer|infostealer|info[\s_-]?stealer|credential\s*stealer|keylogger)\b",
    r"\b(write|create|build|generate|code|implement|develop|make)\b.{0,100}\b(c2|command[\s_-]*and[\s_-]*control)\b.{0,50}\b(server|implant|beacon|agent)\b",
]

# Asking to author a kit (not detection rules / IR playbooks).
WRITE_KIT = re.compile(
    r"\b(write|create|build|generate|code|implement|develop|make|craft)\b"
    r"(?!\s+(?:a\s+|an\s+|the\s+|some\s+)?(?:yara|sigma|kql|spl|detection|playbook|rule|alert|ioc|report|brief))"
    r".{0,100}\b(ransomware|ransom[\s_-]?ware|botnet|worm|stealer|infostealer|encryptor|"
    r"c2\s*(?:server|implant|beacon)|command[\s_-]*and[\s_-]*control)\b",
    re.IGNORECASE | re.DOTALL,
)

# Pure analysis / defense / IR — can mention ransomware without requesting a kit.
ANALYSIS_CONTEXT = re.compile(
    r"\b("
    r"analy[sz]e|analysis|sandbox|remnux|flare|yara|sigma|detect(?:ion)?|forensic|"
    r"incident\s*response|\bir\b|containment|eradication|recover(?:y)?|"
    r"mitigat(?:e|ion)|remediat(?:e|ion)|harden(?:ing)?|tabletop|awareness|briefing|"
    r"how\s+does|how\s+do|behavioral|ttp|ioc|family|unpack|"
    r"static\s+analysis|dynamic\s+analysis|detonate|triage|playbook|detection\s+rule"
    r")\b",
    re.IGNORECASE,
)

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
    r"\bzero\s*safety\b",
    r"\bturn\s+it\s+into\s+a\s+weapon\b",
    r"\bweaponize\b.*\b(ai|model|llm|securaiq)\b",
    r"\b(uncensored|jailbreak)\b.*\b(model|llm|gpt)\b.*\b(malware|botnet|crime|steal|c2)\b",
    r"\bself[- ]improv\w*\b.*\b(exploit|payload|poc)\b.*\b(fine[- ]?tun|nightly|reload)\b",
    r"\b(tor|onion)\b.*\b(hidden\s+service|hiddenservice)\b.*\b(securaiq|gradio|c2|payload)\b",
    r"\bautonomous\b.*\b(pentest\s+drone|payload\s+deploy|deploy\s+payloads)\b",
]

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


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE | re.DOTALL) for p in patterns)


def check_request(message: str) -> GuardrailResult:
    text = (message or "").lower().strip()
    if not text:
        return GuardrailResult(allowed=False, reason="Empty message.")

    for pattern in (
        r"\b(wormgpt|worm\s*gpt|evilgpt|evil\s*gpt|fraudgpt)\b",
        r"\bzero\s*safety\b",
        r"\bturn\s+it\s+into\s+a\s+weapon\b",
    ):
        if re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)

    hard = _matches_any(text, HARD_BLOCK_PATTERNS) or bool(WRITE_KIT.search(text))
    if hard:
        # Analysis / IR / YARA about ransomware is OK; authoring a kit is not.
        if ANALYSIS_CONTEXT.search(text) and not WRITE_KIT.search(text):
            # Block “write … encrypt all files” even when mixed with analysis words
            if re.search(
                r"\b(write|create|build|generate|code|implement|script)\b.{0,100}"
                r"\bencrypt(s|ing)?\b.{0,60}\b(all|every|entire|directory|folder|drive|disk|cwd)\b",
                text,
                re.IGNORECASE | re.DOTALL,
            ):
                return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)
            return GuardrailResult(allowed=True)
        return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)

    if ALLOW_CONTEXT.search(text):
        return GuardrailResult(allowed=True)

    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            return GuardrailResult(allowed=False, reason=REFUSAL_MESSAGE)

    return GuardrailResult(allowed=True)
