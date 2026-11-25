import pytest

from backend.identity.normalization import (
    EntityNameNormalizer,
    normalize_for_comparison,
    normalized_token_set,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bayern München", "bayern munchen"),
        ("  Atlético   Madrid ", "atletico madrid"),
        ("Brighton & Hove Albion", "brighton hove albion"),
        ("PARIS SAINT-GERMAIN", "paris saint germain"),
    ],
)
def test_normalize_for_comparison(raw: str, expected: str) -> None:
    assert normalize_for_comparison(raw) == expected


def test_configured_tokens_are_removed_but_preserved_tokens_kept() -> None:
    normalizer = EntityNameNormalizer(remove_tokens=["FC", "AFC"], preserve_tokens=["afc"])
    assert normalizer.normalize("Liverpool FC").normalized == "liverpool"
    assert normalizer.normalize("AFC Bournemouth").normalized == "afc bournemouth"


def test_aliases_are_deduplicated_in_order() -> None:
    normalizer = EntityNameNormalizer()
    assert normalizer.normalize_aliases(["Man Utd", "MAN UTD", "Manchester United"]) == (
        "man utd",
        "manchester united",
    )


def test_token_set() -> None:
    assert normalized_token_set("Real Madrid C.F.") == frozenset({"real", "madrid", "c", "f"})


@pytest.mark.parametrize("bad", ["", "   ", "!!!"])
def test_empty_names_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_for_comparison(bad)
