from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


_WHITESPACE_PATTERN = re.compile(r"\s+")
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^\w\s]", flags=re.UNICODE)
_UNDERSCORE_PATTERN = re.compile(r"_+")


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """
    Result of deterministic text normalization.

    The normalized value is a comparison aid only. It is not an identity
    and must never be treated as proof that two entities are equivalent.
    """

    original: str
    normalized: str

    def __post_init__(self) -> None:
        if not self.original.strip():
            raise ValueError(
                "Original text must not be empty."
            )

        if not self.normalized:
            raise ValueError(
                "Normalized text must not be empty."
            )


class EntityNameNormalizer:
    """
    Deterministic normalizer for provider entity names.

    This class performs textual normalization only. It does not perform
    entity resolution, fuzzy matching, candidate selection, or merging.

    Provider-specific aliases and known mappings must not be embedded here.
    Those belong to the identity-resolution layer or persisted configuration.
    """

    def __init__(
        self,
        *,
        remove_tokens: Iterable[str] = (),
        preserve_tokens: Iterable[str] = (),
    ) -> None:
        self._remove_tokens = frozenset(
            self._normalize_token(token)
            for token in remove_tokens
            if token.strip()
        )

        self._preserve_tokens = frozenset(
            self._normalize_token(token)
            for token in preserve_tokens
            if token.strip()
        )

    def normalize(
        self,
        value: str,
    ) -> NormalizedText:
        """
        Normalize one piece of entity text.

        Operations are deliberately conservative:

        1. Unicode normalization.
        2. Unicode case normalization.
        3. Removal of combining marks.
        4. Punctuation normalization.
        5. Whitespace normalization.
        6. Optional configured token removal.

        No provider-specific identity assumptions are made.
        """
        if not isinstance(value, str):
            raise TypeError(
                "Entity names must be strings."
            )

        original = value

        if not value.strip():
            raise ValueError(
                "Entity name must not be empty."
            )

        normalized = unicodedata.normalize(
            "NFKD",
            value,
        )

        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

        normalized = normalized.casefold()

        normalized = _NON_ALPHANUMERIC_PATTERN.sub(
            " ",
            normalized,
        )

        normalized = _UNDERSCORE_PATTERN.sub(
            " ",
            normalized,
        )

        normalized = _WHITESPACE_PATTERN.sub(
            " ",
            normalized,
        ).strip()

        if self._remove_tokens:
            normalized = self._remove_configured_tokens(
                normalized
            )

        normalized = _WHITESPACE_PATTERN.sub(
            " ",
            normalized,
        ).strip()

        if not normalized:
            raise ValueError(
                "Entity name became empty after normalization."
            )

        return NormalizedText(
            original=original,
            normalized=normalized,
        )

    def normalize_many(
        self,
        values: Iterable[str],
    ) -> tuple[NormalizedText, ...]:
        """
        Normalize multiple values deterministically.
        """
        return tuple(
            self.normalize(value)
            for value in values
        )

    def normalize_aliases(
        self,
        values: Iterable[str],
    ) -> tuple[str, ...]:
        """
        Normalize aliases and return unique normalized values.

        Original aliases are not retained here because this method is intended
        specifically for generating comparison values. The original provider
        values must remain available in the provider/raw layers.
        """
        normalized_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = self.normalize(value).normalized

            if normalized in seen:
                continue

            seen.add(normalized)
            normalized_values.append(normalized)

        return tuple(normalized_values)

    def tokens(
        self,
        value: str,
    ) -> tuple[str, ...]:
        """
        Return normalized whitespace-separated tokens.
        """
        normalized = self.normalize(value).normalized

        if not normalized:
            return ()

        return tuple(normalized.split())

    def token_set(
        self,
        value: str,
    ) -> frozenset[str]:
        """
        Return normalized tokens as a set.
        """
        return frozenset(
            self.tokens(value)
        )

    def _remove_configured_tokens(
        self,
        value: str,
    ) -> str:
        """
        Remove only explicitly configured comparison tokens.

        No real-world team, league, player, or provider-specific values are
        built into the implementation.
        """
        tokens = value.split()

        filtered_tokens = [
            token
            for token in tokens
            if (
                token not in self._remove_tokens
                or token in self._preserve_tokens
            )
        ]

        return " ".join(filtered_tokens)

    @staticmethod
    def _normalize_token(
        value: str,
    ) -> str:
        """
        Normalize a configuration token using the same basic rules as names.
        """
        normalized = unicodedata.normalize(
            "NFKD",
            value,
        )

        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

        normalized = normalized.casefold()

        normalized = _NON_ALPHANUMERIC_PATTERN.sub(
            " ",
            normalized,
        )

        normalized = _WHITESPACE_PATTERN.sub(
            " ",
            normalized,
        ).strip()

        return normalized


def normalize_for_comparison(
    value: str,
) -> str:
    """
    Convenience function for basic deterministic normalization.

    This function performs no identity matching.
    """
    return EntityNameNormalizer().normalize(value).normalized


def normalized_tokens(
    value: str,
) -> tuple[str, ...]:
    """
    Return normalized tokens for comparison algorithms.
    """
    return EntityNameNormalizer().tokens(value)


def normalized_token_set(
    value: str,
) -> frozenset[str]:
    """
    Return normalized tokens as a set for comparison algorithms.
    """
    return EntityNameNormalizer().token_set(value)