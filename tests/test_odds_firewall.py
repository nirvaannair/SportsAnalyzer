"""The most important rule: prediction models never learn from bookmaker odds (README §5.0).

Two checks:
1. Static: no source file in backend/models mentions the odds table, the odds ORM class,
   or the evaluation package (the only place prices are allowed).
2. Runtime: the model data whitelist rejects anything odds-like.
"""

import ast
from pathlib import Path

import pandas as pd
import pytest

from backend.models.data import ALLOWED_COLUMNS, OddsLeakError, assert_odds_free
from backend.models.dixon_coles import DixonColesModel
from backend.models.elo import pre_match_ratings

MODELS_DIR = Path(__file__).resolve().parents[1] / "backend" / "models"
FORBIDDEN_NAMES = {"OddsQuote", "odds_quotes", "load_prices"}
FORBIDDEN_MODULES = ("backend.evaluation", "backend.pipeline", "backend.ingestion")


def _model_sources():
    files = sorted(MODELS_DIR.glob("*.py"))
    assert files, "no model source files found"
    return files


@pytest.mark.parametrize("path", _model_sources(), ids=lambda p: p.name)
def test_model_code_never_touches_odds(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            assert name not in FORBIDDEN_NAMES, f"{path.name} uses {name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(FORBIDDEN_MODULES), f"{path.name} imports {node.module}"
            assert all(alias.name not in FORBIDDEN_NAMES for alias in node.names), f"{path.name} imports odds"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "odds_quotes" not in node.value, f"{path.name} references the odds table"


@pytest.mark.parametrize("column", ["b365_home", "avg_price", "implied_home", "market_prob", "closing_line",
                                    "pinnacle_draw", "odds_home", "bookmaker_margin"])
def test_odds_like_columns_are_rejected(column: str) -> None:
    with pytest.raises(OddsLeakError):
        assert_odds_free([*sorted(ALLOWED_COLUMNS), column])


def test_unknown_columns_are_rejected() -> None:
    with pytest.raises(OddsLeakError):
        assert_odds_free(["match_id", "something_new"])


def test_models_refuse_frames_with_odds() -> None:
    frame = pd.DataFrame({"match_id": [1], "date": [pd.Timestamp("2024-01-01")], "avg_home_price": [2.1]})
    with pytest.raises(OddsLeakError):
        pre_match_ratings(frame)
    with pytest.raises(OddsLeakError):
        DixonColesModel().fit(frame, as_of=pd.Timestamp("2024-02-01"))
