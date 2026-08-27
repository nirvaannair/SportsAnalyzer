from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ProviderRateLimitConfig:
    """
    User-controlled rate-limit configuration for one provider.

    None means that the limit is not configured locally. The application
    must not invent a provider limit when the provider does not expose one
    or the user has not configured one.
    """

    requests_per_second: float | None = None
    requests_per_minute: int | None = None
    requests_per_hour: int | None = None
    requests_per_day: int | None = None

    def __post_init__(self) -> None:
        if self.requests_per_second is not None:
            if self.requests_per_second <= 0:
                raise ValueError(
                    "requests_per_second must be greater than zero."
                )

        for field_name in (
            "requests_per_minute",
            "requests_per_hour",
            "requests_per_day",
        ):
            value = getattr(self, field_name)

            if value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be greater than zero."
                )


@dataclass(frozen=True, slots=True)
class ProviderQuotaConfig:
    """
    User-controlled quota configuration for one provider.

    These values are intentionally optional because providers expose
    different quota models. Never fabricate quota values.
    """

    requests_per_minute: int | None = None
    requests_per_hour: int | None = None
    requests_per_day: int | None = None
    requests_per_month: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "requests_per_minute",
            "requests_per_hour",
            "requests_per_day",
            "requests_per_month",
        ):
            value = getattr(self, field_name)

            if value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be greater than zero."
                )


@dataclass(frozen=True, slots=True)
class ProviderRetryConfig:
    """Retry behavior for transient provider failures."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0
    exponential_base: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one.")

        if self.initial_backoff_seconds < 0:
            raise ValueError(
                "initial_backoff_seconds cannot be negative."
            )

        if self.max_backoff_seconds < 0:
            raise ValueError(
                "max_backoff_seconds cannot be negative."
            )

        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError(
                "max_backoff_seconds cannot be lower than "
                "initial_backoff_seconds."
            )

        if self.exponential_base < 1:
            raise ValueError(
                "exponential_base must be at least one."
            )


@dataclass(frozen=True, slots=True)
class ProviderCacheConfig:
    """Caching behavior for one provider."""

    enabled: bool = True
    default_ttl_seconds: int | None = None

    def __post_init__(self) -> None:
        if (
            self.default_ttl_seconds is not None
            and self.default_ttl_seconds < 0
        ):
            raise ValueError(
                "default_ttl_seconds cannot be negative."
            )


@dataclass(frozen=True, slots=True)
class ProviderSyncConfig:
    """
    Synchronization configuration for one provider.

    Intervals are optional because different data types will eventually
    have different synchronization policies.
    """

    enabled: bool = True
    upcoming_fixtures_interval_seconds: int | None = None
    historical_data_interval_seconds: int | None = None
    live_data_interval_seconds: int | None = None
    news_interval_seconds: int | None = None
    odds_interval_seconds: int | None = None

    def __post_init__(self) -> None:
        interval_fields = (
            "upcoming_fixtures_interval_seconds",
            "historical_data_interval_seconds",
            "live_data_interval_seconds",
            "news_interval_seconds",
            "odds_interval_seconds",
        )

        for field_name in interval_fields:
            value = getattr(self, field_name)

            if value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be greater than zero."
                )


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """
    Runtime configuration for an external provider.

    This class contains configuration only. It does not contain provider
    entities, canonical entities, sports data, or provider-specific IDs.
    """

    name: str
    enabled: bool = True

    base_url: str | None = None

    api_key: str | None = None
    access_token: str | None = None

    request_timeout_seconds: float = 30.0

    rate_limit: ProviderRateLimitConfig = field(
        default_factory=ProviderRateLimitConfig
    )

    quota: ProviderQuotaConfig = field(
        default_factory=ProviderQuotaConfig
    )

    retry: ProviderRetryConfig = field(
        default_factory=ProviderRetryConfig
    )

    cache: ProviderCacheConfig = field(
        default_factory=ProviderCacheConfig
    )

    sync: ProviderSyncConfig = field(
        default_factory=ProviderSyncConfig
    )

    metadata: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        normalized_name = self.name.strip().lower()

        if not normalized_name:
            raise ValueError("Provider name must not be empty.")

        if self.request_timeout_seconds <= 0:
            raise ValueError(
                "request_timeout_seconds must be greater than zero."
            )

        if self.base_url is not None and not self.base_url.strip():
            raise ValueError(
                "base_url cannot be an empty string when provided."
            )

        object.__setattr__(
            self,
            "name",
            normalized_name,
        )


class ProviderConfigRegistry:
    """
    Registry containing runtime configuration for external providers.

    Provider configurations are supplied by the application bootstrap layer.
    This registry deliberately does not contain a predefined list of
    providers, because the system must remain extensible.
    """

    def __init__(
        self,
        configurations: tuple[ProviderConfig, ...] = (),
    ) -> None:
        self._configs: dict[str, ProviderConfig] = {}

        for configuration in configurations:
            self.register(configuration)

    def register(
        self,
        configuration: ProviderConfig,
    ) -> None:
        """Register one provider configuration."""
        provider_name = configuration.name

        if provider_name in self._configs:
            raise ValueError(
                f"Configuration for provider '{provider_name}' "
                "is already registered."
            )

        self._configs[provider_name] = configuration

    def replace(
        self,
        configuration: ProviderConfig,
    ) -> None:
        """Replace an existing configuration."""
        self._configs[configuration.name] = configuration

    def remove(
        self,
        provider_name: str,
    ) -> ProviderConfig:
        """Remove and return a provider configuration."""
        normalized_name = provider_name.strip().lower()

        try:
            return self._configs.pop(normalized_name)
        except KeyError as exc:
            raise KeyError(
                f"Provider '{normalized_name}' is not configured."
            ) from exc

    def get(
        self,
        provider_name: str,
        *,
        require_enabled: bool = True,
    ) -> ProviderConfig:
        """Return configuration for a provider."""
        normalized_name = provider_name.strip().lower()

        try:
            configuration = self._configs[normalized_name]
        except KeyError as exc:
            raise KeyError(
                f"Provider '{normalized_name}' is not configured."
            ) from exc

        if require_enabled and not configuration.enabled:
            raise KeyError(
                f"Provider '{normalized_name}' is configured but disabled."
            )

        return configuration

    def is_configured(
        self,
        provider_name: str,
    ) -> bool:
        """Return whether a provider has configuration."""
        return provider_name.strip().lower() in self._configs

    def is_enabled(
        self,
        provider_name: str,
    ) -> bool:
        """Return whether a provider is configured and enabled."""
        normalized_name = provider_name.strip().lower()

        configuration = self._configs.get(normalized_name)

        return configuration is not None and configuration.enabled

    def all(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[ProviderConfig, ...]:
        """Return configured providers in deterministic name order."""
        configurations = self._configs.values()

        if enabled_only:
            configurations = (
                configuration
                for configuration in configurations
                if configuration.enabled
            )

        return tuple(
            sorted(
                configurations,
                key=lambda configuration: configuration.name,
            )
        )