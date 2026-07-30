from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_backend: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "tinyllama"
    openai_compat_base_url: str = "http://localhost:1234/v1"
    openai_compat_model: str = "local-model"
    openai_compat_api_key: str = "lm-studio"
    # Cloud OpenAI-compatible providers (AI Router)
    router_enabled: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    together_api_key: str = ""
    together_model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
    fireworks_api_key: str = ""
    fireworks_model: str = "accounts/fireworks/models/llama-v3p1-70b-instruct"
    router_code_model: str = "qwen/qwen2.5-coder-32b-instruct"
    router_compliance_model: str = "gpt-4o-mini"
    router_report_model: str = "gpt-4o-mini"
    router_intel_model: str = "llama-3.3-70b-versatile"
    router_cloud_model: str = "openai/gpt-4o-mini"
    ollama_coder_model: str = ""  # e.g. qwen2.5-coder:7b when pulled
    hermes_base_url: str = "http://127.0.0.1:8642/v1"
    hermes_model: str = "hermes-agent"
    hermes_api_key: str = "change-me-local-dev"
    # Stable memory scope for Hermes (X-Hermes-Session-Key); optional
    hermes_session_key: str = "securaiq-pentest"
    hermes_show_tool_progress: bool = True
    hf_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    hf_token: str = ""
    # Hosted HF inference (router) — reuses hf_token, no local model download
    huggingface_api_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    # Unsloth — https://github.com/unslothai/unsloth
    unsloth_model: str = "unsloth/Qwen2.5-0.5B-Instruct-bnb-4bit"
    unsloth_adapter_dir: str = "./models/securaiq-unsloth"
    unsloth_max_seq_length: int = 2048
    unsloth_load_in_4bit: bool = True
    host: str = "127.0.0.1"
    port: int = 8080
    chroma_persist_dir: str = "./data/chroma"
    data_dir: str = "./data"
    embedding_model: str = "all-MiniLM-L6-v2"
    # When false, knowledge files are not indexed until the user clicks Re-index (empty/fast start).
    rag_auto_ingest: bool = False
    # Optional Qdrant vector store (compose profile). Empty = use Chroma only.
    qdrant_url: str = ""
    qdrant_collection: str = "securaiq_knowledge"
    # Live web search for Research mode (DuckDuckGo HTML, or SearXNG if set)
    web_search_enabled: bool = True
    web_search_max_results: int = 8
    web_search_timeout_sec: float = 5.0
    searxng_url: str = ""
    # Network assess: light TCP/HTTP probes (+ nmap if installed)
    net_assess_enabled: bool = True
    net_assess_use_nmap: bool = True
    # Local security tools registry (builtins + PATH binaries)
    local_tools_enabled: bool = True
    local_tools_auto: bool = True  # auto light tools on assess / when target set
    local_tools_allow_heavy: bool = False  # nuclei/nikto/ffuf only when instructed
    # Commercial / team foundations
    auth_enabled: bool = False
    auth_allow_register: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""
    upload_max_mb: int = 15
    upload_quota_mb_per_user: int = 500
    # Jira integration (optional)
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    # Notifications: in-app always on; email is optional (SMTP)
    notifications_enabled: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "securaiq@localhost"
    smtp_use_tls: bool = True
    # Free / optional threat-intel API keys (https://free-apis.github.io/#/categories/Security)
    abuseipdb_api_key: str = ""
    virustotal_api_key: str = ""
    shodan_api_key: str = ""
    otx_api_key: str = ""
    urlscan_api_key: str = ""
    hibp_api_key: str = ""
    greynoise_api_key: str = ""
    pulsedive_api_key: str = ""
    malwarebazaar_api_key: str = ""
    emailrep_api_key: str = ""
    github_webhook_secret: str = ""
    slack_webhook_url: str = ""
    teams_webhook_url: str = ""
    servicenow_instance_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""
    urlhaus_api_key: str = ""  # abuse.ch Auth-Key
    # MFA / SSO (beta enterprise)
    mfa_required_for_admin: bool = False
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://127.0.0.1:8080/api/auth/oidc/callback"
    oidc_scopes: str = "openid profile email"
    # Infra (beta SaaS — Postgres/Redis via compose profiles)
    database_url: str = ""  # empty = SQLite at DATA_DIR/securaiq.db
    redis_url: str = ""
    # Security hardening
    cors_origins: str = "http://127.0.0.1:8080,http://localhost:8080"
    rate_limit_per_minute: int = 180
    rate_limit_auth_per_minute: int = 20
    rate_limit_chat_per_minute: int = 45
    # Billing / usage metering
    billing_enforcement_enabled: bool = False  # soft by default — enable once plans are real
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""
    # Error reporting / monitoring (optional)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_environment: str = "alpha"
    # SIEM / security log forwarding (optional — audit events always log locally as JSON)
    siem_forward_enabled: bool = False
    siem_forward_url: str = ""       # generic HTTP sink or Splunk HEC endpoint
    siem_hec_token: str = ""         # set if siem_forward_url is a Splunk HEC collector
    siem_syslog_host: str = ""
    siem_syslog_port: int = 514


settings = Settings()


def _decrypt_secret_fields_in_place() -> None:
    """Secret fields written via Settings/env_persist may be stored as
    `enc:v1:...` (see app/secrets_crypto.py). Pydantic loads the raw string
    from .env — this decrypts it in place right after construction so the
    rest of the app only ever sees plaintext in memory.
    """
    from app.secrets_crypto import decrypt_value, is_encrypted

    for name in settings.model_fields:
        value = getattr(settings, name, None)
        if isinstance(value, str) and is_encrypted(value):
            setattr(settings, name, decrypt_value(value))


try:
    _decrypt_secret_fields_in_place()
except Exception:
    # Never block app startup on crypto issues (e.g. cryptography not
    # installed yet in an older venv) — worst case, an encrypted value is
    # treated as "not set" until the dependency is installed.
    pass


def cors_origin_list() -> list[str]:
    raw = (settings.cors_origins or "").strip()
    if not raw or raw == "*":
        # Local-dev convenience when explicitly wildcarded
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
