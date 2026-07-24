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
    # Jira integration (optional)
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""


settings = Settings()
