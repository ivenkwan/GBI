"""Application configuration via pydantic-settings.

All settings load from environment variables with sensible defaults.
Secrets are NEVER hardcoded — always use env vars or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GenBI application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- LLM ---
    ANTHROPIC_API_KEY: str = ""
    LLM_REASONING_MODEL: str = "claude-opus-4"
    LLM_FAST_MODEL: str = "claude-haiku-4"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://genbi:genbi@localhost:5432/genbi"
    DATABASE_URL_SYNC: str = "postgresql://genbi:genbi@localhost:5432/genbi"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Semantic Layer ---
    CUBE_API_URL: str = "http://localhost:4000/cubejs-api/v1"
    CUBE_API_SECRET: str = ""

    # --- Observability ---
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # --- Auth ---
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # --- Tenant ---
    TENANT_ENCRYPTION_KEY: str = ""

    # --- Flint Chart MCP ---
    FLINT_MCP_BACKENDS: str = "vegalite,echarts,chartjs"
    FLINT_MCP_DATA_ROOTS: str = "/tmp/genbi-charts"


settings = Settings()
