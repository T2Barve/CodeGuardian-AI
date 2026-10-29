import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Mode
    PROJECT_NAME: str = "CodeGuardian AI"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "development-secret-key-change-in-production-min-32-chars-long"

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # PostgreSQL Relational Database
    DATABASE_URL: str = "postgresql+asyncpg://codeguardian:codeguardian_password@localhost:5432/codeguardian_db"
    POSTGRES_USER: str = "codeguardian"
    POSTGRES_PASSWORD: str = "codeguardian_password"
    POSTGRES_DB: str = "codeguardian_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Redis Queue & Broker
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Vector Database (ChromaDB)
    CHROMA_PERSIST_DIRECTORY: str = "./data/chromadb"

    # GitHub App & Webhook Ingestion
    GITHUB_APP_ID: str = ""
    GITHUB_PRIVATE_KEY_PATH: str = ""
    GITHUB_WEBHOOK_SECRET: str = "development_webhook_secret"
    GITHUB_TOKEN: str = ""

    # AI / LLM Configuration
    LLM_PROVIDER: str = "gemini"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "gemini-3.8-flash"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096

    # Scanner Toggles & Timeouts
    ENABLE_SEMGREP: bool = True
    ENABLE_BANDIT: bool = True
    ENABLE_GITLEAKS: bool = True
    ENABLE_ESLINT: bool = True
    SCANNER_TIMEOUT_SECONDS: int = 45

    # Sandboxed Remediation
    SANDBOX_TIMEOUT_SECONDS: int = 60
    SANDBOX_MAX_MEMORY_MB: int = 1024


settings = Settings()
