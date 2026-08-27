from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .base import ProviderAdapter, ProviderCapability


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """
    Metadata describing a registered provider adapter.

    The registry stores adapter instances and their declared capabilities.
    It does not contain provider-specific sports data or canonical entities.
    """

    name: str
    adapter: ProviderAdapter
    enabled: bool = True

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        """Return the capabilities declared by the provider."""
        return self.adapter.capabilities


class ProviderRegistry:
    """
    Central registry for external provider adapters.

    The registry provides a single dependency boundary between the rest of
    SportsAnalyzer and external data providers.

    Provider adapters remain responsible for provider-specific communication.
    The registry does not perform requests, entity resolution, normalization,
    or canonical database writes.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderRegistration] = {}

    def register(
        self,
        adapter: ProviderAdapter,
        *,
        enabled: bool = True,
    ) -> None:
        """
        Register a provider adapter.

        Provider names must be unique and are normalized to lowercase for
        registry lookups.
        """
        provider_name = self._normalize_name(adapter.name)

        if not provider_name:
            raise ValueError("Provider name must not be empty.")

        if provider_name in self._providers:
            raise ValueError(
                f"Provider '{provider_name}' is already registered."
            )

        self._providers[provider_name] = ProviderRegistration(
            name=provider_name,
            adapter=adapter,
            enabled=enabled,
        )

    def unregister(self, provider_name: str) -> ProviderRegistration:
        """
        Remove and return a registered provider.

        Raises:
            KeyError: If the provider is not registered.
        """
        normalized_name = self._normalize_name(provider_name)
        return self._providers.pop(normalized_name)

    def get(
        self,
        provider_name: str,
        *,
        require_enabled: bool = True,
    ) -> ProviderAdapter:
        """
        Return a registered provider adapter.

        Args:
            provider_name: Provider name.
            require_enabled: Whether disabled providers should be rejected.

        Raises:
            KeyError: If the provider is not registered or is disabled when
                require_enabled is True.
        """
        normalized_name = self._normalize_name(provider_name)

        try:
            registration = self._providers[normalized_name]
        except KeyError as exc:
            raise KeyError(
                f"Provider '{normalized_name}' is not registered."
            ) from exc

        if require_enabled and not registration.enabled:
            raise KeyError(
                f"Provider '{normalized_name}' is registered but disabled."
            )

        return registration.adapter

    def get_registration(
        self,
        provider_name: str,
    ) -> ProviderRegistration:
        """Return complete registration metadata for a provider."""
        normalized_name = self._normalize_name(provider_name)

        try:
            return self._providers[normalized_name]
        except KeyError as exc:
            raise KeyError(
                f"Provider '{normalized_name}' is not registered."
            ) from exc

    def enable(self, provider_name: str) -> None:
        """Enable a registered provider."""
        normalized_name = self._normalize_name(provider_name)
        registration = self.get_registration(normalized_name)

        self._providers[normalized_name] = ProviderRegistration(
            name=registration.name,
            adapter=registration.adapter,
            enabled=True,
        )

    def disable(self, provider_name: str) -> None:
        """Disable a registered provider without removing its adapter."""
        normalized_name = self._normalize_name(provider_name)
        registration = self.get_registration(normalized_name)

        self._providers[normalized_name] = ProviderRegistration(
            name=registration.name,
            adapter=registration.adapter,
            enabled=False,
        )

    def is_registered(self, provider_name: str) -> bool:
        """Return whether a provider is registered."""
        normalized_name = self._normalize_name(provider_name)
        return normalized_name in self._providers

    def is_enabled(self, provider_name: str) -> bool:
        """Return whether a provider exists and is enabled."""
        normalized_name = self._normalize_name(provider_name)

        registration = self._providers.get(normalized_name)

        if registration is None:
            return False

        return registration.enabled

    def providers(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[ProviderRegistration, ...]:
        """
        Return registered providers.

        Results are sorted by provider name to keep behavior deterministic.
        """
        registrations: Iterable[ProviderRegistration] = self._providers.values()

        if enabled_only:
            registrations = (
                registration
                for registration in registrations
                if registration.enabled
            )

        return tuple(
            sorted(
                registrations,
                key=lambda registration: registration.name,
            )
        )

    def providers_with_capability(
        self,
        capability: ProviderCapability,
        *,
        enabled_only: bool = True,
    ) -> tuple[ProviderRegistration, ...]:
        """
        Return providers that advertise a specific capability.
        """
        registrations = self.providers(enabled_only=enabled_only)

        return tuple(
            registration
            for registration in registrations
            if capability in registration.capabilities
        )

    async def initialize_enabled(self) -> None:
        """Initialize every enabled provider."""
        for registration in self.providers(enabled_only=True):
            await registration.adapter.initialize()

    async def close_enabled(self) -> None:
        """Close every enabled provider."""
        for registration in self.providers(enabled_only=True):
            await registration.adapter.close()

    @staticmethod
    def _normalize_name(provider_name: str) -> str:
        """Normalize a provider name for registry operations."""
        return provider_name.strip().lower()
    