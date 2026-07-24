"""Enterprise integration catalog — orchestrate mature tools; do not rebuild them.

Status legend:
  shipped   — usable in SecuraIQ today (import, API, or live path)
  import    — JSON/CSV import adapter ready
  path      — runs when binary is on PATH (local tools)
  planned   — documented target; connector not shipped yet
  commercial — optional paid product (customer brings license)
"""

from __future__ import annotations

from typing import Any


# MVP focus (limited budget / open-source-first)
MVP_STACK: list[dict[str, str]] = [
    {"category": "AI", "tool": "Qwen + OpenRouter / Ollama", "status": "shipped"},
    {"category": "SAST", "tool": "Semgrep", "status": "import"},
    {"category": "Code quality", "tool": "SonarQube Community", "status": "import"},
    {"category": "Secrets", "tool": "Gitleaks", "status": "import"},
    {"category": "Containers / SCA", "tool": "Trivy + Grype", "status": "import"},
    {"category": "IaC", "tool": "Checkov", "status": "import"},
    {"category": "DAST", "tool": "OWASP ZAP + Nuclei", "status": "path+import"},
    {"category": "Threat intel", "tool": "MITRE + NVD + CISA KEV", "status": "shipped"},
    {"category": "SIEM", "tool": "Wazuh", "status": "planned"},
    {"category": "Automation", "tool": "n8n via webhooks", "status": "shipped"},
    {"category": "Case mgmt", "tool": "TheHive", "status": "planned"},
    {"category": "Identity", "tool": "Keycloak / Authentik", "status": "planned"},
    {"category": "Database", "tool": "SQLite now → PostgreSQL", "status": "partial"},
    {"category": "Vector DB", "tool": "Chroma + Qdrant profile", "status": "shipped"},
    {"category": "Storage", "tool": "Local data/ → MinIO", "status": "partial"},
    {"category": "Backend", "tool": "FastAPI", "status": "shipped"},
    {"category": "Frontend", "tool": "Mission Control (Next.js later)", "status": "shipped"},
]


CATALOG: list[dict[str, Any]] = [
    # AI
    {"id": "openai", "name": "OpenAI", "category": "ai", "status": "shipped", "hint": "Cloud chat via AI Router"},
    {"id": "anthropic", "name": "Anthropic", "category": "ai", "status": "planned", "hint": "Via OpenRouter or direct API later"},
    {"id": "gemini", "name": "Google Gemini", "category": "ai", "status": "planned", "hint": "Via OpenRouter or direct API later"},
    {"id": "groq", "name": "Groq", "category": "ai", "status": "shipped", "hint": "Fast cloud inference"},
    {"id": "openrouter", "name": "OpenRouter", "category": "ai", "status": "shipped", "hint": "Many models, one key"},
    {"id": "together", "name": "Together AI", "category": "ai", "status": "shipped"},
    {"id": "fireworks", "name": "Fireworks AI", "category": "ai", "status": "shipped"},
    {"id": "ollama", "name": "Ollama (Qwen/Llama/Mistral/DeepSeek/Gemma)", "category": "ai", "status": "shipped"},
    # SAST
    {"id": "sonarqube", "name": "SonarQube", "category": "sast", "status": "import", "hint": "Import issues JSON export"},
    {"id": "semgrep", "name": "Semgrep", "category": "sast", "status": "import"},
    {"id": "codeql", "name": "CodeQL", "category": "sast", "status": "planned"},
    {"id": "bandit", "name": "Bandit", "category": "sast", "status": "import", "hint": "Python SAST JSON"},
    {"id": "eslint_security", "name": "ESLint Security", "category": "sast", "status": "planned"},
    {"id": "pmd", "name": "PMD", "category": "sast", "status": "planned"},
    {"id": "spotbugs", "name": "SpotBugs", "category": "sast", "status": "planned"},
    {"id": "brakeman", "name": "Brakeman", "category": "sast", "status": "planned"},
    # SCA
    {"id": "dependency_track", "name": "Dependency-Track", "category": "sca", "status": "planned"},
    {"id": "syft", "name": "Syft", "category": "sca", "status": "planned", "hint": "SBOM → feed Grype/Trivy"},
    {"id": "grype", "name": "Grype", "category": "sca", "status": "import"},
    {"id": "trivy", "name": "Trivy", "category": "sca", "status": "import"},
    {"id": "owasp_dc", "name": "OWASP Dependency-Check", "category": "sca", "status": "planned"},
    # Secrets
    {"id": "gitleaks", "name": "Gitleaks", "category": "secrets", "status": "import"},
    {"id": "trufflehog", "name": "TruffleHog", "category": "secrets", "status": "planned"},
    {"id": "gitguardian", "name": "GitGuardian", "category": "secrets", "status": "commercial"},
    # Container / K8s
    {"id": "kubescape", "name": "Kubescape", "category": "container", "status": "planned"},
    {"id": "falco", "name": "Falco", "category": "container", "status": "planned"},
    {"id": "docker_scout", "name": "Docker Scout", "category": "container", "status": "commercial"},
    {"id": "kube_bench", "name": "kube-bench", "category": "kubernetes", "status": "planned"},
    {"id": "kube_hunter", "name": "kube-hunter", "category": "kubernetes", "status": "planned"},
    # IaC
    {"id": "checkov", "name": "Checkov", "category": "iac", "status": "import"},
    {"id": "terrascan", "name": "Terrascan", "category": "iac", "status": "planned"},
    {"id": "tfsec", "name": "tfsec", "category": "iac", "status": "planned"},
    # DAST
    {"id": "zap", "name": "OWASP ZAP", "category": "dast", "status": "path+import", "hint": "PATH tool + JSON report import"},
    {"id": "nuclei", "name": "Nuclei", "category": "dast", "status": "path"},
    {"id": "nikto", "name": "Nikto", "category": "dast", "status": "path"},
    # Vuln mgmt
    {"id": "openvas", "name": "Greenbone / OpenVAS", "category": "vuln_mgmt", "status": "path"},
    {"id": "nessus", "name": "Nessus", "category": "vuln_mgmt", "status": "commercial"},
    {"id": "qualys", "name": "Qualys", "category": "vuln_mgmt", "status": "commercial"},
    {"id": "rapid7", "name": "Rapid7 InsightVM", "category": "vuln_mgmt", "status": "commercial"},
    # Threat intel
    {"id": "mitre_attack", "name": "MITRE ATT&CK", "category": "intel", "status": "shipped", "hint": "Heuristics + knowledge"},
    {"id": "mitre_d3fend", "name": "MITRE D3FEND", "category": "intel", "status": "planned"},
    {"id": "cisa_kev", "name": "CISA KEV", "category": "intel", "status": "shipped"},
    {"id": "nvd", "name": "NVD", "category": "intel", "status": "shipped"},
    {"id": "cwe", "name": "CWE", "category": "intel", "status": "partial"},
    {"id": "capec", "name": "CAPEC", "category": "intel", "status": "planned"},
    {"id": "otx", "name": "AlienVault OTX", "category": "intel", "status": "planned"},
    {"id": "virustotal", "name": "VirusTotal", "category": "intel", "status": "commercial"},
    {"id": "abuseipdb", "name": "AbuseIPDB", "category": "intel", "status": "planned"},
    {"id": "shodan", "name": "Shodan", "category": "intel", "status": "commercial"},
    # SIEM / SOAR / IR / EDR
    {"id": "wazuh", "name": "Wazuh", "category": "siem", "status": "planned"},
    {"id": "elastic", "name": "Elastic Stack", "category": "siem", "status": "planned"},
    {"id": "graylog", "name": "Graylog", "category": "siem", "status": "planned"},
    {"id": "security_onion", "name": "Security Onion", "category": "siem", "status": "planned"},
    {"id": "shuffle", "name": "Shuffle", "category": "soar", "status": "planned"},
    {"id": "stackstorm", "name": "StackStorm", "category": "soar", "status": "planned"},
    {"id": "n8n", "name": "n8n", "category": "soar", "status": "shipped", "hint": "Outbound webhooks"},
    {"id": "thehive", "name": "TheHive", "category": "ir", "status": "planned"},
    {"id": "cortex", "name": "Cortex", "category": "ir", "status": "planned"},
    {"id": "velociraptor", "name": "Velociraptor", "category": "edr", "status": "planned"},
    {"id": "osquery", "name": "Osquery", "category": "edr", "status": "planned"},
    # Cloud
    {"id": "aws_security_hub", "name": "AWS Security Hub", "category": "cloud", "status": "planned"},
    {"id": "azure_defender", "name": "Microsoft Defender for Cloud", "category": "cloud", "status": "planned"},
    {"id": "gcp_scc", "name": "Google Security Command Center", "category": "cloud", "status": "planned"},
    # Compliance frameworks (catalogs)
    {"id": "iso27001", "name": "ISO 27001", "category": "compliance", "status": "shipped"},
    {"id": "iso27701", "name": "ISO 27701", "category": "compliance", "status": "shipped"},
    {"id": "nist_csf", "name": "NIST CSF", "category": "compliance", "status": "shipped"},
    {"id": "nist_800_53", "name": "NIST SP 800-53", "category": "compliance", "status": "planned"},
    {"id": "cis", "name": "CIS Controls", "category": "compliance", "status": "shipped"},
    {"id": "soc2", "name": "SOC 2", "category": "compliance", "status": "shipped"},
    {"id": "pci", "name": "PCI DSS", "category": "compliance", "status": "shipped"},
    {"id": "hipaa", "name": "HIPAA", "category": "compliance", "status": "shipped"},
    {"id": "gdpr", "name": "GDPR", "category": "compliance", "status": "shipped"},
    {"id": "asvs", "name": "OWASP ASVS", "category": "compliance", "status": "shipped"},
    # Identity / platform
    {"id": "keycloak", "name": "Keycloak", "category": "identity", "status": "planned"},
    {"id": "authentik", "name": "Authentik", "category": "identity", "status": "planned"},
    {"id": "authelia", "name": "Authelia", "category": "identity", "status": "planned"},
    {"id": "qdrant", "name": "Qdrant", "category": "vectors", "status": "shipped"},
    {"id": "weaviate", "name": "Weaviate", "category": "vectors", "status": "planned"},
    {"id": "milvus", "name": "Milvus", "category": "vectors", "status": "planned"},
    {"id": "pgvector", "name": "pgvector", "category": "vectors", "status": "planned"},
    {"id": "postgres", "name": "PostgreSQL", "category": "database", "status": "planned"},
    {"id": "redis", "name": "Redis", "category": "database", "status": "planned"},
    {"id": "minio", "name": "MinIO", "category": "storage", "status": "planned"},
    {"id": "r2", "name": "Cloudflare R2", "category": "storage", "status": "planned"},
    {"id": "rabbitmq", "name": "RabbitMQ", "category": "queue", "status": "planned"},
    {"id": "kafka", "name": "Kafka", "category": "queue", "status": "planned"},
    {"id": "nats", "name": "NATS", "category": "queue", "status": "planned"},
    {"id": "grafana", "name": "Grafana", "category": "observability", "status": "planned"},
    {"id": "prometheus", "name": "Prometheus", "category": "observability", "status": "planned"},
    {"id": "loki", "name": "Loki", "category": "observability", "status": "planned"},
    {"id": "otel", "name": "OpenTelemetry", "category": "observability", "status": "planned"},
    {"id": "sentry", "name": "Sentry", "category": "observability", "status": "planned"},
    # SCM / PM / Comms
    {"id": "github", "name": "GitHub", "category": "scm", "status": "planned"},
    {"id": "gitlab", "name": "GitLab", "category": "scm", "status": "planned"},
    {"id": "azure_devops", "name": "Azure DevOps", "category": "scm", "status": "planned"},
    {"id": "bitbucket", "name": "Bitbucket", "category": "scm", "status": "planned"},
    {"id": "jira", "name": "Jira", "category": "pm", "status": "shipped"},
    {"id": "linear", "name": "Linear", "category": "pm", "status": "planned"},
    {"id": "azure_boards", "name": "Azure Boards", "category": "pm", "status": "planned"},
    {"id": "trello", "name": "Trello", "category": "pm", "status": "planned"},
    {"id": "slack", "name": "Slack", "category": "comms", "status": "planned", "hint": "Use webhook bridge today"},
    {"id": "teams", "name": "Microsoft Teams", "category": "comms", "status": "planned"},
    {"id": "discord", "name": "Discord", "category": "comms", "status": "planned"},
    {"id": "smtp", "name": "Email (SMTP)", "category": "comms", "status": "planned"},
    # Docs
    {"id": "pdf", "name": "PDF parsing / export", "category": "documents", "status": "shipped"},
    {"id": "docx", "name": "DOCX", "category": "documents", "status": "shipped"},
    {"id": "xlsx", "name": "Excel", "category": "documents", "status": "shipped"},
    {"id": "markdown", "name": "Markdown", "category": "documents", "status": "shipped"},
    {"id": "ocr", "name": "OCR", "category": "documents", "status": "planned"},
]


CATEGORY_LABELS = {
    "ai": "AI providers",
    "sast": "Secure coding (SAST)",
    "sca": "Software composition",
    "secrets": "Secret detection",
    "container": "Container security",
    "kubernetes": "Kubernetes",
    "iac": "Infrastructure as Code",
    "dast": "DAST",
    "vuln_mgmt": "Vulnerability management",
    "intel": "Threat intelligence",
    "siem": "SIEM / logs",
    "soar": "SOAR / automation",
    "ir": "Incident response",
    "edr": "Endpoint detection",
    "cloud": "Cloud security",
    "compliance": "Compliance frameworks",
    "identity": "Identity & access",
    "vectors": "Vector database",
    "database": "Database",
    "storage": "Object storage",
    "queue": "Message queue",
    "observability": "Monitoring",
    "scm": "SCM",
    "pm": "Project management",
    "comms": "Communication",
    "documents": "Document processing",
}

ACTIONABLE_STATUSES = frozenset({"shipped", "import", "path", "path+import", "partial"})
SCANNER_IDS = frozenset(
    {
        "sonarqube",
        "semgrep",
        "bandit",
        "grype",
        "trivy",
        "gitleaks",
        "checkov",
        "zap",
        "nuclei",
        "nikto",
        "openvas",
    }
)
AI_IDS = frozenset({"openai", "groq", "openrouter", "together", "fireworks", "ollama"})
INTEL_IDS = frozenset({"mitre_attack", "cisa_kev", "nvd", "cwe"})
DOC_IDS = frozenset({"pdf", "docx", "xlsx", "markdown"})
WEBHOOK_IDS = frozenset({"n8n", "slack"})


def resolve_ui_action(item: dict[str, Any]) -> dict[str, str]:
    """Map catalog entry → UI Connect target (honest: planned stays disabled)."""
    status = item.get("status") or "planned"
    iid = item.get("id") or ""
    cat = item.get("category") or ""

    if status in {"planned", "commercial"}:
        return {"kind": "planned", "label": "Planned"}

    if iid == "jira":
        return {"kind": "settings", "label": "Configure Jira", "focus": "jira"}
    if iid in WEBHOOK_IDS or (cat == "soar" and status == "shipped"):
        return {"kind": "webhooks", "label": "Add webhook"}
    if iid in AI_IDS or cat == "ai":
        return {"kind": "settings", "label": "AI settings", "focus": "ai"}
    if iid in SCANNER_IDS or (
        status in {"import", "path", "path+import"}
        and cat in {"sast", "sca", "secrets", "iac", "dast", "vuln_mgmt", "container"}
    ):
        return {"kind": "workspace", "target": "vulns", "label": "Import scan"}
    if iid in INTEL_IDS or cat == "intel":
        return {"kind": "workspace", "target": "intel", "label": "Open intel"}
    if cat == "compliance":
        return {"kind": "workspace", "target": "frameworks", "label": "Open frameworks"}
    if iid in DOC_IDS or cat == "documents":
        return {"kind": "workspace", "target": "evidence", "label": "Open evidence"}
    if cat == "vectors" or iid == "qdrant":
        return {"kind": "settings", "label": "Settings", "focus": "ai"}
    if status in ACTIONABLE_STATUSES:
        return {"kind": "info", "label": "Available"}
    return {"kind": "planned", "label": "Planned"}


def resolve_enterprise_action(feat: dict[str, Any]) -> dict[str, str]:
    status = feat.get("status") or "planned"
    fid = feat.get("id") or ""
    if status == "planned":
        return {"kind": "planned", "label": "Planned"}
    if fid == "orgs" or fid == "multi_tenancy" or fid == "rbac":
        return {"kind": "workspace", "target": "orgs", "label": "Open orgs"}
    if fid in {"webhooks", "automation"}:
        return {"kind": "webhooks", "label": "Webhooks"}
    if fid in {"api_keys", "audit"}:
        return {"kind": "settings", "label": "Settings", "focus": "api"}
    return {"kind": "info", "label": "Available"}


def catalog_payload() -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for raw in CATALOG:
        item = {**raw, "ui_action": resolve_ui_action(raw)}
        enriched.append(item)

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in enriched:
        by_cat.setdefault(item["category"], []).append(item)
    groups = [
        {
            "id": cat,
            "label": CATEGORY_LABELS.get(cat, cat),
            "items": items,
        }
        for cat, items in by_cat.items()
    ]
    shipped = sum(1 for i in enriched if i["status"] in ACTIONABLE_STATUSES)
    enterprise = [
        {**f, "ui_action": resolve_enterprise_action(f)}
        for f in (
            {"id": "multi_tenancy", "name": "Multi-tenancy", "status": "shipped"},
            {"id": "rbac", "name": "RBAC", "status": "shipped"},
            {"id": "sso", "name": "SSO", "status": "planned"},
            {"id": "mfa", "name": "MFA", "status": "planned"},
            {"id": "audit", "name": "Audit logs", "status": "shipped"},
            {"id": "api_keys", "name": "API keys", "status": "shipped"},
            {"id": "webhooks", "name": "Webhooks", "status": "shipped"},
            {"id": "automation", "name": "Workflow automation", "status": "partial"},
            {"id": "report_schedules", "name": "Report scheduling", "status": "planned"},
            {"id": "white_label", "name": "White-labeling", "status": "planned"},
            {"id": "orgs", "name": "Organization & projects", "status": "shipped"},
        )
    ]
    mvp = [{**m, "ui_action": _mvp_ui_action(m)} for m in MVP_STACK]
    return {
        "doctrine": "Integrate mature tools — SecuraIQ orchestrates findings, evidence, and AI; it does not replace scanners or SIEMs.",
        "mvp": mvp,
        "counts": {
            "total": len(enriched),
            "actionable": shipped,
            "planned": sum(1 for i in enriched if i["status"] == "planned"),
        },
        "groups": groups,
        "agents": [
            {"name": "SOC Analyst", "mode": "blueteam", "prompt": "Act as SOC Analyst: summarize open incidents and critical vulns, recommend next 3 actions"},
            {"name": "Threat Hunter", "mode": "threat_hunt", "prompt": "Act as Threat Hunter: prioritize hunts from our critical findings and intel watchlist"},
            {"name": "Malware Analyst", "mode": "blueteam", "prompt": "Act as Malware Analyst: outline a safe sandboxed triage workflow for a suspicious sample (authorized lab only)"},
            {"name": "Compliance Officer", "mode": "ciso", "prompt": "Act as Compliance Officer: review framework gaps and evidence needed this week"},
            {"name": "Risk Manager", "mode": "assess", "prompt": "Act as Risk Manager: prioritize open risks with residual risk and owners"},
            {"name": "Cloud Security Architect", "mode": "assess", "prompt": "Act as Cloud Security Architect: propose hardening for our top cloud assets"},
            {"name": "Secure Code Reviewer", "mode": "assess", "prompt": "Act as Secure Code Reviewer: triage imported SAST findings and recommend remediations"},
            {"name": "DevSecOps Engineer", "mode": "blueteam", "prompt": "Act as DevSecOps Engineer: design a CI pipeline that imports Trivy/Semgrep/Gitleaks into SecuraIQ"},
            {"name": "Incident Commander", "mode": "blueteam", "prompt": "Act as Incident Commander: draft an IR runbook for our open incidents"},
            {"name": "Executive Advisor", "mode": "ciso", "prompt": "Act as Executive Advisor: draft a board-ready security posture summary"},
        ],
        "enterprise_features": enterprise,
    }


def _mvp_ui_action(m: dict[str, str]) -> dict[str, str]:
    status = m.get("status") or "planned"
    tool = (m.get("tool") or "").lower()
    cat = (m.get("category") or "").lower()
    if status == "planned":
        return {"kind": "planned", "label": "Planned"}
    if "jira" in tool:
        return {"kind": "settings", "label": "Configure", "focus": "jira"}
    if "n8n" in tool or "webhook" in tool or cat == "automation":
        return {"kind": "webhooks", "label": "Connect"}
    if cat in {"sast", "code quality", "secrets", "containers / sca", "iac", "dast"} or status in {
        "import",
        "path+import",
    }:
        return {"kind": "workspace", "target": "vulns", "label": "Import"}
    if "intel" in cat or "mitre" in tool or "kev" in tool:
        return {"kind": "workspace", "target": "intel", "label": "Open"}
    if cat == "ai" or "ollama" in tool or "openrouter" in tool:
        return {"kind": "settings", "label": "AI settings", "focus": "ai"}
    if status in ACTIONABLE_STATUSES:
        return {"kind": "info", "label": "Available"}
    return {"kind": "planned", "label": "Planned"}
