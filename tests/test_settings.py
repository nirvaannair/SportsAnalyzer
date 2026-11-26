"""The owner's rule: no hard-coded values. Tunables live in config/settings.toml.

1. Every setting the code asks for (cfg("...") in Python, setting('...') in the dashboard) exists.
2. No module-level numeric constants or fixed dates creep back into the backend.
3. Dashboard edits are validated and written to the local override file only.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from backend.core import settings as store
from backend.core.settings import cfg

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"

# Names allowed to be numbers in code: maths and fixed identifiers, not tunables.
ALLOWED_NUMERIC_CONSTANTS = {"EPS", "LOADER_LOCK", "PROJECT_ROOT"}  # PROJECT_ROOT: folder depth


def _exists(path: str) -> bool:
    try:
        cfg(path)
        return True
    except KeyError:
        return False


def _python_keys() -> set[str]:
    keys = set()
    for file in BACKEND.rglob("*.py"):
        for match in re.finditer(r"""cfg\(\s*f?["']([a-z0-9_.]+)["']""", file.read_text(encoding="utf-8")):
            keys.add(match.group(1))
    return keys


def _frontend_keys() -> set[str]:
    keys = set()
    for file in FRONTEND.rglob("*.tsx"):
        for match in re.finditer(r"setting(?:<[^>]+>)?\('([a-z0-9_.]+)'\)", file.read_text(encoding="utf-8")):
            keys.add(match.group(1))
    for match in re.finditer(r"refresh\('([a-z_]+)'\)", "".join(f.read_text(encoding="utf-8") for f in FRONTEND.rglob("*.tsx"))):
        keys.add(f"ui.refresh_seconds.{match.group(1)}")
    return keys


@pytest.mark.parametrize("key", sorted(_python_keys()))
def test_backend_setting_exists(key: str) -> None:
    assert _exists(key), f"cfg({key!r}) is used in the backend but missing from config/settings.toml"


@pytest.mark.parametrize("key", sorted(_frontend_keys()))
def test_dashboard_setting_exists(key: str) -> None:
    assert _exists(key), f"setting({key!r}) is used in the dashboard but missing from config/settings.toml"


@pytest.mark.parametrize("path", sorted(BACKEND.rglob("*.py")), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_numeric_constants_or_fixed_dates(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:  # module level only
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            value = node.value
            if value is None or not names or not all(n.isupper() for n in names):
                continue
            if set(names) & ALLOWED_NUMERIC_CONSTANTS:
                continue
            numbers = [n for n in ast.walk(value) if isinstance(n, ast.Constant)
                       and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
            assert not numbers, f"{path.name}: {names[0]} holds a number; move it to config/settings.toml"
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "date" and node.args \
                and all(isinstance(a, ast.Constant) for a in node.args):
            raise AssertionError(f"{path.name}:{node.lineno} has a fixed date; put it in config/settings.toml")


def test_leagues_come_from_settings() -> None:
    from backend.core.leagues import LEAGUES

    assert [lg.code for lg in LEAGUES] == [lg["code"] for lg in cfg("leagues")]


def test_dashboard_edits_are_validated_and_saved_locally(tmp_path, monkeypatch) -> None:
    from fastapi import HTTPException

    from backend.api.routes_settings import _check

    monkeypatch.setattr(store, "LOCAL_FILE", tmp_path / "settings.local.json")
    defaults = store.defaults()
    _check({"players": {"half_life_days": 200}}, defaults)
    for bad in ({"players": {"half_life_days": "soon"}}, {"nope": 1}, {"players": {"made_up": 1}}):
        with pytest.raises(HTTPException):
            _check(bad, defaults)
    store.save_overrides({"players": {"half_life_days": 200}})
    assert json.loads((tmp_path / "settings.local.json").read_text())["players"]["half_life_days"] == 200
    assert cfg("players.half_life_days") == 200
    assert cfg("players.shrink_90s") == defaults["players"]["shrink_90s"]  # untouched values keep their default
    store.reset_overrides("players")
    assert cfg("players.half_life_days") == defaults["players"]["half_life_days"]
