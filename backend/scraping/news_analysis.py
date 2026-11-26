"""Read a football news headline + summary: is it good or bad news for the team, and is it about injuries?

A transparent word-list approach tuned for football news (no black box, easy to inspect):
  * sentiment in [-1, 1] from positive/negative phrases, the headline counting double;
  * flags for injury, manager/turmoil, form and transfer stories.
Odds and betting words are ignored entirely (we never learn from the market).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from backend.core.settings import cfg

WORD_START = WORD_END = r"\b"  # regex word boundary


def _words(kind: str) -> tuple[str, ...]:
    """Word lists live in config/settings.toml under [news.words]."""
    return tuple(cfg(f"news.words.{kind}"))


def _terms(text: str, terms: tuple[str, ...]) -> list[str]:
    """Whole words/phrases found in `text` (prefix match for the few stems in PREFIXES)."""
    found = []
    for term in terms:
        tail = "" if term in _words("prefixes") else WORD_END
        if re.search(WORD_START + re.escape(term) + tail, text):
            found.append(term)
    return found


@lru_cache(maxsize=1)
def _vader_analyzer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return SentimentIntensityAnalyzer()


def _vader(headline: str, summary: str | None, headline_weight: float) -> float:
    """VADER compound score (-1..1) of the headline (weighted) and summary, betting words removed."""
    def clean(text: str) -> str:
        text = text or ""
        for word in _words("betting"):
            text = re.sub(re.escape(word), " ", text, flags=re.I)
        return text

    head = _vader_analyzer().polarity_scores(clean(headline))["compound"]
    if not summary:
        return head
    body = _vader_analyzer().polarity_scores(clean(summary))["compound"]
    return (headline_weight * head + body) / (headline_weight + 1)


def analyse(headline: str, summary: str | None) -> dict[str, Any]:
    head = (headline or "").lower()
    body = (summary or "").lower()
    for word in _words("betting"):  # strip betting talk before scoring
        head, body = head.replace(word, " "), body.replace(word, " ")
    weight = cfg("news.headline_weight")
    pos = _terms(head, _words("positive")) * weight + _terms(body, _words("positive"))
    neg = _terms(head, _words("negative")) * weight + _terms(body, _words("negative"))
    text = f"{head} {body}"
    words_score = (len(pos) - len(neg)) / (len(pos) + len(neg) + weight)
    vader_score = _vader(headline, summary, weight)
    weights = cfg("news.sentiment_weights")
    total = weights["words"] + weights["vader"]
    score = (weights["words"] * words_score + weights["vader"] * vader_score) / total if total else 0.0
    return {
        "sentiment": round(max(-1.0, min(1.0, score)), 3),
        "injury": bool(_terms(text, _words("injury"))),
        "signals": {
            "words_score": round(words_score, 3), "vader_score": round(vader_score, 3),
            "positive": sorted(set(pos)), "negative": sorted(set(neg)),
            "injury_terms": sorted(set(_terms(text, _words("injury")))),
            "manager": bool(_terms(text, _words("manager"))), "form": bool(_terms(text, _words("form"))),
            "transfer": bool(_terms(text, _words("transfer"))),
        },
    }
