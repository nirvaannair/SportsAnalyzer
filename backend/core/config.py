from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="SPORTSANALYZER_DB_",
        case_sensitive=False,
        extra="ignore",
    )

    url: str = Field(
        default="",
        description="Database connection URL.",
    )

    pool_size: int = Field(
        default=5,
        ge=1,
        description="Base database connection pool size.",
    )

    max_overflow: int = Field(
        default=10,
        ge=0,
        description="Maximum additional database connections.",
    )

    pool_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Maximum time to wait for a database connection.",
    )

    pool_recycle_seconds: int = Field(
        default=1800,
        ge=0,
        description="Connection recycle interval.",
    )


class ProviderSettings(BaseSettings):
    """
    Generic configuration shared by external providers.

    Provider-specific settings must remain inside their own provider
    configuration rather than being coupled to the canonical domain model.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="SPORTSANALYZER_PROVIDER_",
        case_sensitive=False,
        extra="ignore",
    )

    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Default timeout for provider requests.",
    )

    connect_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Connection establishment timeout.",
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for retryable provider failures.",
    )

    backoff_base_seconds: float = Field(
        default=1.0,
        ge=0,
        description="Base delay used for exponential retry backoff.",
    )

    cache_enabled: bool = Field(
        default=True,
        description="Whether provider response caching is enabled.",
    )


class SchedulerSettings(BaseSettings):
    """Settings for the centralized ingestion scheduler."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="SPORTSANALYZER_SCHEDULER_",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Whether scheduled ingestion is enabled.",
    )

    worker_count: int = Field(
        default=1,
        ge=1,
        description="Number of scheduler workers.",
    )

    poll_interval_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Interval between scheduler queue checks.",
    )

    max_concurrent_provider_requests: int = Field(
        default=5,
        ge=1,
        description="Global upper bound for concurrent provider requests.",
    )


class IdentityResolutionSettings(BaseSettings):
    """Settings for the provider entity identity-resolution system."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="SPORTSANALYZER_IDENTITY_",
        case_sensitive=False,
        extra="ignore",
    )

    automatic_resolution_enabled: bool = Field(
        default=True,
        description=(
            "Whether high-confidence identity mappings may be "
            "accepted automatically."
        ),
    )

    minimum_resolution_confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum confidence required for automatic resolution."
        ),
    )

    unresolved_retention_enabled: bool = Field(
        default=True,
        description=(
            "Whether unresolved provider entities remain available "
            "for later resolution."
        ),
    )


class ApplicationSettings(BaseSettings):
    """
    Root application configuration.

    Environment variables are the primary source of deployment-specific
    configuration. No provider IDs, teams, players, odds, matches, or other
    real-world sports data belong here.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(
        default="development",
        description="Application environment.",
    )

    log_level: str = Field(
        default="INFO",
        description="Application logging level.",
    )

    timezone: str = Field(
        default="UTC",
        description=(
            "Timezone used for application scheduling and timestamps."
        ),
    )

    api_host: str = Field(
        default="127.0.0.1",
        description="Backend API bind host.",
    )

    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Backend API bind port.",
    )

    database: DatabaseSettings = Field(
        default_factory=lambda: DatabaseSettings(
            _env_file=ENV_FILE,
            _env_file_encoding="utf-8",
        ),
    )

    provider: ProviderSettings = Field(
        default_factory=lambda: ProviderSettings(
            _env_file=ENV_FILE,
            _env_file_encoding="utf-8",
        ),
    )

    scheduler: SchedulerSettings = Field(
        default_factory=lambda: SchedulerSettings(
            _env_file=ENV_FILE,
            _env_file_encoding="utf-8",
        ),
    )

    identity: IdentityResolutionSettings = Field(
        default_factory=lambda: IdentityResolutionSettings(
            _env_file=ENV_FILE,
            _env_file_encoding="utf-8",
        ),
    )

    @property
    def project_root(self) -> Path:
        """Return the repository root directory."""
        return PROJECT_ROOT

    @property
    def environment_name(self) -> str:
        """Return the normalized application environment name."""
        return self.environment.strip().lower()

    def validate_runtime(self) -> None:
        """
        Validate settings that are required before starting runtime services.

        Database connectivity is intentionally not tested here because this
        method should validate configuration structure without performing I/O.
        """
        if not self.environment_name:
            raise ValueError(
                "Application environment must not be empty."
            )

        if not self.log_level.strip():
            raise ValueError(
                "Log level must not be empty."
            )

        if not self.timezone.strip():
            raise ValueError(
                "Timezone must not be empty."
            )

        if not self.database.url.strip():
            raise ValueError(
                "Database URL is not configured. "
                "Set SPORTSANALYZER_DB_URL in the environment."
            )


@lru_cache(maxsize=1)
def get_settings() -> ApplicationSettings:
    """
    Return the singleton application settings instance.

    Caching prevents repeated parsing of environment/configuration values
    throughout the application lifecycle.
    """
    settings = ApplicationSettings()

    if settings.environment_name != "test":
        settings.validate_runtime()

    return settings


def settings_as_dict(
    settings: ApplicationSettings | None = None,
) -> dict[str, Any]:
    """
    Return a serializable representation of application settings.

    Secrets are not deliberately introduced by this module. If sensitive
    settings are added later, they must be masked before this helper is used
    for logging or diagnostics.
    """
    active_settings = settings or get_settings()

    return active_settings.model_dump(mode="python")