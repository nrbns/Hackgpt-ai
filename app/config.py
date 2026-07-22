from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_backend: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "tinyllama"
    openai_compat_base_url: str = "http://localhost:1234/v1"
    openai_compat_model: str = "local-model"
    openai_compat_api_key: str = "lm-studio"
    hermes_base_url: str = "http://127.0.0.1:8642/v1"
    hermes_model: str = "hermes-agent"
    hermes_api_key: str = "change-me-local-dev"
    # Stable memory scope for Hermes (X-Hermes-Session-Key); optional
    hermes_session_key: str = "hackgpt-pentest"
    hermes_show_tool_progress: bool = True
    hf_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    hf_token: str = ""
    # Unsloth — https://github.com/unslothai/unsloth
    unsloth_model: str = "unsloth/Qwen2.5-0.5B-Instruct-bnb-4bit"
    unsloth_adapter_dir: str = "./models/pentestgpt-unsloth"
    unsloth_max_seq_length: int = 2048
    unsloth_load_in_4bit: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    chroma_persist_dir: str = "./data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
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


settings = Settings()
