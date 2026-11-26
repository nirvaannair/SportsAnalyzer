"""Read a football news headline + summary: is it good or bad news for the team, and is it about injuries?

A transparent word-list approach tuned for football news (no black box, easy to inspect):
  * sentiment in [-1, 1] from positive/negative phrases, the headline counting double;
  * flags for injury, manager/turmoil, form and transfer stories.
Odds and betting words are ignored entirely (we never learn from the market).
"""

from __future__ import annotations

import re
from typing import Any

POSITIVE = (
    "win", "wins", "won", "victory", "victories", "beat", "beats", "thrash", "thrashed", "rout", "routed",
    "unbeaten", "winning run", "winning streak", "top of the table", "go top", "goes top", "title race",
    "comeback", "boost", "boosted", "returns", "return from injury", "back in training", "fit again",
    "record", "stunning", "impressive", "dominant", "dominate", "clinch", "clinched", "extend lead",
    "extends lead", "in form", "flying", "brilliant", "masterclass", "hat-trick", "clean sheet",
    "promotion", "promoted", "back to winning", "statement win", "cruise", "cruised",
)
NEGATIVE = (
    "loss", "lose", "loses", "lost", "defeat", "defeats", "defeated", "beaten", "crisis", "sacked", "sack",
    "under pressure", "pressure mounts", "slump", "winless", "without a win", "relegation", "relegated",
    "bottom of the table", "injury", "injured", "ruled out", "out for", "sidelined", "suspended", "suspension",
    "ban", "banned", "doubt", "doubtful", "setback", "blow", "turmoil", "row", "fined", "embarrass",
    "humiliat", "collapse", "collapsed", "struggle", "struggling", "poor form", "dropped points", "draw blank",
    "frustrat", "dismal", "woeful", "red card", "sent off", "unrest", "protest", "points deduction",
    "error", "errors", "costly", "blunder", "mistake", "mistakes", "overshadow", "concern", "concerns",
    "worry", "worried", "blasts", "slams", "criticis", "miss out", "disappointing", "disappointment",
)
INJURY = (
    "injury", "injured", "ruled out", "sidelined", "out for", "hamstring", "knee", "ankle", "groin", "calf",
    "thigh", "muscle", "surgery", "fitness doubt", "doubtful", "set to miss", "will miss", "misses",
    "concussion", "fracture", "ligament", "acl", "strain", "knock",
)
MANAGER = ("sacked", "sack", "manager", "head coach", "coach", "appointed", "resign", "interim", "under pressure")
FORM = ("unbeaten", "winless", "winning run", "losing run", "streak", "in form", "poor form", "slump", "run of")
TRANSFER = ("transfer", "signs", "signing", "bid", "loan", "deal", "linked with", "rumour", "rumor")
BETTING = ("odds", "betting", "bet ", "bookmaker", "tips", "prediction", "accumulator", "acca")


WORD_START = WORD_END = r"\b"  # regex word boundary
PREFIXES = ("humiliat", "frustrat", "embarrass", "criticis")  # match any ending (humiliating, frustrated, ...)


def _terms(text: str, terms: tuple[str, ...]) -> list[str]:
    """Whole words/phrases found in `text` (prefix match for the few stems in PREFIXES)."""
    found = []
    for term in terms:
        tail = "" if term in PREFIXES else WORD_END
        if re.search(WORD_START + re.escape(term) + tail, text):
            found.append(term)
    return found


def analyse(headline: str, summary: str | None) -> dict[str, Any]:
    head = (headline or "").lower()
    body = (summary or "").lower()
    for word in BETTING:  # strip betting talk before scoring
        head, body = head.replace(word, " "), body.replace(word, " ")
    pos = _terms(head, POSITIVE) * 2 + _terms(body, POSITIVE)
    neg = _terms(head, NEGATIVE) * 2 + _terms(body, NEGATIVE)
    text = f"{head} {body}"
    score = (len(pos) - len(neg)) / (len(pos) + len(neg) + 2)
    return {
        "sentiment": round(max(-1.0, min(1.0, score)), 3),
        "injury": bool(_terms(text, INJURY)),
        "signals": {
            "positive": sorted(set(pos)), "negative": sorted(set(neg)),
            "injury_terms": sorted(set(_terms(text, INJURY))),
            "manager": bool(_terms(text, MANAGER)), "form": bool(_terms(text, FORM)),
            "transfer": bool(_terms(text, TRANSFER)),
        },
    }
