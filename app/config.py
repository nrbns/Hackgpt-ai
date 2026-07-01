from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_backend: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    openai_compat_base_url: str = "http://localhost:1234/v1"
    openai_compat_model: str = "local-model"
    openai_compat_api_key: str = "lm-studio"
    hf_model: str = "microsoft/Phi-3-mini-4k-instruct"
    host: str = "0.0.0.0"
    port: int = 8080
    chroma_persist_dir: str = "./data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"


settings = Settings()
