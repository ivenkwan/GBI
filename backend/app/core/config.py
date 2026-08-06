"""Application configuration via pydantic-settings.

All settings load from environment variables with sensible defaults.
Secrets are NEVER hardcoded — always use env vars or .env file.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Secret values that must not ship to non-development environments. Any match
# here in production/staging fails fast at Settings() construction time rather
# than silently signing JWTs with a publicly known key.
_INSECURE_SECRET_VALUES = frozenset({
    "change-me",
    "change-me-in-production",
    "change-me-in-production-use-openssl-rand-64",
    "",
})


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

    # --- Prompts ---
    # Directory holding versioned prompt templates (loaded by llm_client.load_prompt).
    # Defaults to the repo's .claude/prompts/ on host runs; override for containers
    # where the working dir differs. The Dockerfile bakes the prompts into /app/.claude.
    PROMPT_DIR: str = ""

    @model_validator(mode="after")
    def _enforce_production_secrets(self):
        """Fail fast if production is launched with an insecure secret.

        A known-default or empty JWT secret in any non-development environment
        would let anyone forge tokens. Better to refuse to boot than to run
        with a publicly-known signing key.
        """
        if self.APP_ENV not in ("development", "test") and self.JWT_SECRET_KEY in _INSECURE_SECRET_VALUES:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong random value in "
                f"APP_ENV={self.APP_ENV} (generate one with `openssl rand -hex 32`). "
                "Aborting boot to avoid running with a default/known secret."
            )
        return self


settings = Settings()
