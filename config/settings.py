from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "Enterprise AI Chatbot"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    auth_enabled: bool = False
    jwt_secret: str = "change-me"
    rate_limit_per_minute: int = 60

    llm_provider: Literal["mock", "openai", "groq", "anthropic", "gemini", "ollama", "vllm"] = "mock"
    llm_model: str = "gpt-4.1"
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    vllm_base_url: str = "http://localhost:8001/v1"

    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-large"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "enterprise_knowledge"
    qdrant_enabled: bool = False
    embedding_dimension: int = 384

    sqlserver_dsn: str | None = None
    sqlserver_host: str | None = None
    sqlserver_database: str | None = "Subscription_Analysis"
    sqlserver_user: str | None = None
    sqlserver_password: str | None = None
    sqlserver_driver: str = Field(default="ODBC Driver 18 for SQL Server")
    sqlserver_trusted_connection: bool = True
    sqlserver_encrypt: bool = False
    postgresql_host: str | None = None
    postgresql_port: int = 5432
    postgresql_database: str | None = None
    postgresql_user: str | None = None
    postgresql_password: str | None = None
    postgresql_sslmode: str = "prefer"
    deep_sql_max_rounds: int = Field(default=20, ge=2, le=60)
    deep_sql_distinct_limit: int = Field(default=50, ge=5, le=200)
    deep_sql_step_seconds: float = Field(default=15, ge=0, le=60)
    deep_sql_large_step_seconds: float = Field(default=30, ge=0, le=120)
    deep_sql_large_token_threshold: int = Field(default=4000, ge=1)

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator(
        "openai_api_key",
        "groq_api_key",
        "anthropic_api_key",
        "gemini_api_key",
        "sqlserver_dsn",
        "sqlserver_host",
        "sqlserver_database",
        "sqlserver_user",
        "sqlserver_password",
        "postgresql_host",
        "postgresql_database",
        "postgresql_user",
        "postgresql_password",
        "langfuse_public_key",
        "langfuse_secret_key",
        "otel_exporter_otlp_endpoint",
        mode="before",
    )
    @classmethod
    def blank_strings_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
