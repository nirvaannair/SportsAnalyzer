"""Trained machine-learning match models: XGBoost (GPU) and a PyTorch neural net (GPU).

Both learn from backend.models.features only (football data, never odds) and predict
home/draw/away, Over/Under 2.5, both-teams-to-score and each side's expected goals.

Global + per-league
    Each family first trains one GLOBAL model on all leagues (teams from different leagues
    meet, and promoted/relegated teams move between them, so strength must share one scale).
    Then a copy is FINE-TUNED on each league's own matches (XGBoost: extra trees grown on the
    league; neural net: a few more epochs on the league at a lower learning rate).
    The "auto" variant picks, per league, whichever of global/league predicted better on
    earlier seasons (never on the season being predicted).

Validation is walk-forward by season: to predict season S, models are trained only on
seasons before S; inside each training set the latest 15% of matches (by date) are held out
for early stopping, so a model never tunes itself on the future.

Heavy libraries (xgboost, torch) are imported lazily so the rest of the app works without them.
"""

from __future__ import annotations

import copy
import json
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.core.settings import cfg
from backend.models.features import FEATURE_COLUMNS, LEAGUE_CODES, assert_features_odds_free

Progress = Callable[[dict[str, Any]], None]
ML_MODELS = ("xgb", "nn")
VARIANTS = ("global", "league", "auto")
OUTPUT_COLUMNS = ("p_home", "p_draw", "p_away", "p_over25", "p_btts", "exp_home_goals", "exp_away_goals")


def _noop(_: dict[str, Any]) -> None:
    pass


def stored_name(family: str, variant: str) -> str:
    """Name in model_runs: xgb, xgb_league, xgb_auto, nn, ..."""
    return family if variant == "global" else f"{family}_{variant}"


def training_rows(feats: pd.DataFrame) -> pd.DataFrame:
    """Finished matches with enough history behind them to have meaningful features."""
    first = feats["date"].min() + pd.Timedelta(days=cfg("training.warmup_days"))
    return feats[(feats["status"] == "finished") & feats["y_1x2"].notna() & (feats["date"] >= first)]


def time_split(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(fit, validation): validation is the latest share (settings: training.validation_share) of the training matches."""
    train = train.sort_values(["date", "match_id"])
    cut = int(len(train) * (1 - cfg("training.validation_share")))
    return train.iloc[:cut], train.iloc[cut:]


def cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def gpu_name() -> str | None:
    try:
        import torch
        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except ImportError:
        return None


def _x(frame: pd.DataFrame) -> np.ndarray:
    assert_features_odds_free(FEATURE_COLUMNS)
    return frame[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float32)


def _tuned_leagues(train: pd.DataFrame) -> list[str]:
    counts = train["league"].value_counts()
    return sorted(str(lg) for lg, n in counts.items() if n >= cfg("training.min_league_rows"))


def _empty_predictions() -> pd.DataFrame:
    return pd.DataFrame(columns=["match_id", *OUTPUT_COLUMNS])


# ---------------------------------------------------------------------------
# XGBoost
# ---------------------------------------------------------------------------

_XGB_TASKS = {
    # task: (objective, eval metric, target column)
    "1x2": ("multi:softprob", "mlogloss", "y_1x2"),
    "over25": ("binary:logistic", "logloss", "y_over25"),
    "btts": ("binary:logistic", "logloss", "y_btts"),
    "home_goals": ("count:poisson", "poisson-nloglik", "home_goals"),
    "away_goals": ("count:poisson", "poisson-nloglik", "away_goals"),
}


def _xgb_reporter(task: str, metric: str, progress: Progress, steps: int):
    """xgboost callback: report the train/validation metric every 10 rounds.

    `epoch` counts from 0 in each xgb.train call (also when continuing from a base model),
    while best_iteration counts the base model's trees too.
    """
    import xgboost as xgb

    class Reporter(xgb.callback.TrainingCallback):
        def after_iteration(self, model, epoch, evals_log) -> bool:
            step = epoch + 1
            if step % cfg("training.xgb.report_every") == 1:
                progress({"task": task, "step": step, "steps": steps,
                          "train_loss": float(evals_log["train"][metric][-1]),
                          "val_loss": float(evals_log["val"][metric][-1])})
            return False

    return Reporter()


class XGBMatchModel:
    name = "xgb"

    def __init__(self, device: str | None = None) -> None:
        self.device = device or ("cuda" if cuda_available() else "cpu")
        self.boosters: dict[str, Any] = {}
        self.rounds: dict[str, int] = {}
        self.league_boosters: dict[str, dict[str, Any]] = {}
        self.league_rounds: dict[str, dict[str, int]] = {}

    def _params(self, objective: str, metric: str, **extra: Any) -> dict[str, Any]:
        return {**cfg("training.xgb.params"), "objective": objective, "eval_metric": metric, "device": self.device, "seed": 7,
                **({"num_class": 3} if objective.startswith("multi") else {}), **extra}

    def fit(self, train: pd.DataFrame, progress: Progress = _noop, per_league: bool = True) -> XGBMatchModel:
        import xgboost as xgb

        fit_part, val_part = time_split(train)
        x_fit, x_val = _x(fit_part), _x(val_part)
        for task, (objective, metric, target) in _XGB_TASKS.items():
            d_fit = xgb.DMatrix(x_fit, label=fit_part[target].to_numpy(), missing=np.nan)
            d_val = xgb.DMatrix(x_val, label=val_part[target].to_numpy(), missing=np.nan)
            rounds = cfg("training.xgb.rounds")
            booster = xgb.train(self._params(objective, metric), d_fit, rounds,
                                evals=[(d_fit, "train"), (d_val, "val")],
                                early_stopping_rounds=cfg("training.xgb.patience"), verbose_eval=False,
                                callbacks=[_xgb_reporter(f"global · {task}", metric, progress, rounds)])
            self.rounds[task] = int(booster.best_iteration) + 1
            self.boosters[task] = booster[: self.rounds[task]]  # drop the trees grown after the best round

        if per_league:
            for league in _tuned_leagues(train):
                self._fine_tune(league, train[train["league"] == league], progress)
        return self

    def _fine_tune(self, league: str, rows: pd.DataFrame, progress: Progress) -> None:
        """Grow extra trees on top of the global model using only this league's matches."""
        import xgboost as xgb

        fit_part, val_part = time_split(rows)
        x_fit, x_val = _x(fit_part), _x(val_part)
        self.league_boosters[league], self.league_rounds[league] = {}, {}
        for task, (objective, metric, target) in _XGB_TASKS.items():
            base = self.boosters[task]
            d_fit = xgb.DMatrix(x_fit, label=fit_part[target].to_numpy(), missing=np.nan)
            d_val = xgb.DMatrix(x_val, label=val_part[target].to_numpy(), missing=np.nan)
            rounds = cfg("training.xgb.tune_rounds")
            booster = xgb.train(self._params(objective, metric, eta=cfg("training.xgb.tune_eta")), d_fit, rounds,
                                evals=[(d_fit, "train"), (d_val, "val")],
                                early_stopping_rounds=cfg("training.xgb.tune_patience"),
                                verbose_eval=False, xgb_model=base,
                                callbacks=[_xgb_reporter(f"{league} · {task}", metric, progress, rounds)])
            rounds = int(booster.best_iteration) + 1  # counts the global model's trees too
            self.league_rounds[league][task] = rounds
            self.league_boosters[league][task] = booster[:rounds]

    def _run(self, boosters: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
        import xgboost as xgb

        matrix = xgb.DMatrix(_x(frame), missing=np.nan)
        out = {task: booster.predict(matrix) for task, booster in boosters.items()}
        p1x2 = out["1x2"] / out["1x2"].sum(axis=1, keepdims=True)
        return pd.DataFrame({
            "match_id": frame["match_id"].to_numpy(),
            "p_home": p1x2[:, 0], "p_draw": p1x2[:, 1], "p_away": p1x2[:, 2],
            "p_over25": out["over25"], "p_btts": out["btts"],
            "exp_home_goals": out["home_goals"], "exp_away_goals": out["away_goals"],
        })

    def predict(self, frame: pd.DataFrame, variant: str = "global") -> pd.DataFrame:
        if frame.empty:
            return _empty_predictions()
        if variant == "global":
            return self._run(self.boosters, frame)
        parts = [self._run(self.league_boosters.get(str(league), self.boosters), rows)
                 for league, rows in frame.groupby("league")]
        return pd.concat(parts, ignore_index=True)

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for task, booster in self.boosters.items():
            booster.save_model(str(folder / f"{task}.ubj"))
        for league, boosters in self.league_boosters.items():
            (folder / league).mkdir(exist_ok=True)
            for task, booster in boosters.items():
                booster.save_model(str(folder / league / f"{task}.ubj"))
        meta = {"rounds": self.rounds, "league_rounds": self.league_rounds, "features": list(FEATURE_COLUMNS)}
        _merge_meta(folder, meta)

    @classmethod
    def load(cls, folder: Path) -> XGBMatchModel:
        import xgboost as xgb

        meta = json.loads((folder / "meta.json").read_text())
        if meta["features"] != list(FEATURE_COLUMNS):
            raise ValueError("Saved XGBoost model was trained on different features; retrain it.")

        def read(path: Path):
            booster = xgb.Booster()
            booster.load_model(str(path))
            booster.set_param({"device": "cpu"})
            return booster

        model = cls(device="cpu")
        model.rounds, model.league_rounds = meta["rounds"], meta.get("league_rounds", {})
        model.boosters = {task: read(folder / f"{task}.ubj") for task in _XGB_TASKS}
        model.league_boosters = {lg: {task: read(folder / lg / f"{task}.ubj") for task in _XGB_TASKS}
                                 for lg in model.league_rounds}
        return model


# ---------------------------------------------------------------------------
# Neural net (PyTorch)
# ---------------------------------------------------------------------------



class _Preprocessor:
    """Median-impute, add missing flags, standardise; one-hot the league. Fitted on training data only."""

    def __init__(self) -> None:
        self.numeric = [c for c in FEATURE_COLUMNS if c != "league_code"]
        self.medians: np.ndarray | None = None
        self.means: np.ndarray | None = None
        self.stds: np.ndarray | None = None
        self.flag_columns: list[int] = []

    @property
    def width(self) -> int:
        return len(self.numeric) + len(self.flag_columns) + len(LEAGUE_CODES) + 1

    def fit(self, frame: pd.DataFrame) -> _Preprocessor:
        x = frame[self.numeric].to_numpy(dtype=np.float64)
        with warnings.catch_warnings():  # all-NaN columns (stats a league never had) -> 0
            warnings.simplefilter("ignore", RuntimeWarning)
            self.medians = np.nan_to_num(np.nanmedian(x, axis=0), nan=0.0)
        self.flag_columns = [i for i in range(x.shape[1]) if np.isnan(x[:, i]).any()]
        filled = np.where(np.isnan(x), self.medians, x)
        self.means, self.stds = filled.mean(axis=0), filled.std(axis=0) + 1e-6
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        x = frame[self.numeric].to_numpy(dtype=np.float64)
        flags = np.isnan(x[:, self.flag_columns]).astype(np.float64)
        clip = cfg("training.nn.clip_std")
        filled = np.clip((np.where(np.isnan(x), self.medians, x) - self.means) / self.stds, -clip, clip)
        league = frame["league_code"].to_numpy()
        onehot = np.zeros((len(frame), len(LEAGUE_CODES) + 1))
        onehot[np.arange(len(frame)), np.where(league >= 0, league, len(LEAGUE_CODES)).astype(int)] = 1
        return np.hstack([filled, flags, onehot]).astype(np.float32)

    def state(self) -> dict[str, Any]:
        return {"medians": self.medians.tolist(), "means": self.means.tolist(), "stds": self.stds.tolist(),
                "flag_columns": self.flag_columns, "numeric": self.numeric}

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> _Preprocessor:
        p = cls()
        if state["numeric"] != p.numeric:
            raise ValueError("Saved neural net was trained on different features; retrain it.")
        p.medians, p.means, p.stds = (np.array(state[k]) for k in ("medians", "means", "stds"))
        p.flag_columns = state["flag_columns"]
        return p


def _build_net(n_inputs: int):
    import torch
    from torch import nn

    class Block(nn.Module):
        """Residual MLP block: x + MLP(LayerNorm(x))."""

        def __init__(self, width: int, dropout: float) -> None:
            super().__init__()
            self.mlp = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, width * 2), nn.GELU(),
                                     nn.Dropout(dropout), nn.Linear(width * 2, width))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return x + self.mlp(x)

    class MatchNet(nn.Module):
        """Shared residual body; one head per market. Goals come out as log Poisson rates."""

        def __init__(self) -> None:
            super().__init__()
            width, dropout = cfg("training.nn.width"), cfg("training.nn.dropout")
            self.stem = nn.Sequential(nn.Linear(n_inputs, width), nn.GELU(), nn.Dropout(dropout))
            self.body = nn.Sequential(*(Block(width, dropout) for _ in range(cfg("training.nn.blocks"))),
                                      nn.LayerNorm(width))
            self.outcome = nn.Linear(width, 3)
            self.over25 = nn.Linear(width, 1)
            self.btts = nn.Linear(width, 1)
            self.goals = nn.Linear(width, 2)

        def forward(self, x: torch.Tensor):
            h = self.body(self.stem(x))
            return self.outcome(h), self.over25(h).squeeze(-1), self.btts(h).squeeze(-1), self.goals(h)

    return MatchNet()


class NeuralMatchModel:
    name = "nn"

    def __init__(self, device: str | None = None) -> None:
        self.device = device or ("cuda" if cuda_available() else "cpu")
        self.pre = _Preprocessor()
        self.net = None
        self.league_nets: dict[str, Any] = {}
        self.epochs: dict[str, int] = {}

    def _tensors(self, frame: pd.DataFrame):
        import torch

        dev = torch.device(self.device)
        x = torch.tensor(self.pre.transform(frame), device=dev)
        y = (torch.tensor(frame["y_1x2"].to_numpy(), dtype=torch.long, device=dev),
             torch.tensor(frame["y_over25"].to_numpy(), dtype=torch.float32, device=dev),
             torch.tensor(frame["y_btts"].to_numpy(), dtype=torch.float32, device=dev),
             torch.tensor(frame[["home_goals", "away_goals"]].to_numpy(), dtype=torch.float32, device=dev))
        return x, y

    @staticmethod
    def _loss(outputs, targets):
        import torch.nn.functional as f

        outcome, over, btts, log_goals = outputs
        y_outcome, y_over, y_btts, y_goals = targets
        return (f.cross_entropy(outcome, y_outcome)
                + f.binary_cross_entropy_with_logits(over, y_over)
                + f.binary_cross_entropy_with_logits(btts, y_btts)
                + cfg("training.nn.goals_loss_weight") * f.poisson_nll_loss(log_goals, y_goals, log_input=True))

    def _train(self, net, rows: pd.DataFrame, lr: float, epochs: int, patience: int,
               task: str, progress: Progress) -> int:
        """Train `net` in place with early stopping; returns the best epoch."""
        import torch

        fit_part, val_part = time_split(rows)
        x_fit, y_fit = self._tensors(fit_part)
        x_val, y_val = self._tensors(val_part)
        optimiser = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=cfg("training.nn.weight_decay"))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)
        generator = torch.Generator(device="cpu").manual_seed(7)
        best, best_state, best_epoch, waited = float("inf"), None, 0, 0
        for epoch in range(1, epochs + 1):
            net.train()
            order = torch.randperm(len(x_fit), generator=generator).to(x_fit.device)
            total = 0.0
            for start in range(0, len(order), cfg("training.nn.batch")):
                idx = order[start:start + cfg("training.nn.batch")]
                optimiser.zero_grad()
                loss = self._loss(net(x_fit[idx]), [t[idx] for t in y_fit])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
                optimiser.step()
                total += float(loss.detach()) * len(idx)
            scheduler.step()
            net.eval()
            with torch.no_grad():
                val_loss = float(self._loss(net(x_val), y_val))
            progress({"task": task, "step": epoch, "steps": epochs,
                      "train_loss": total / len(x_fit), "val_loss": val_loss})
            if val_loss < best - 1e-4:
                best, best_epoch, waited = val_loss, epoch, 0
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            else:
                waited += 1
                if waited >= patience:
                    break
        if best_state is not None:
            net.load_state_dict(best_state)
        net.eval()
        return best_epoch

    def fit(self, train: pd.DataFrame, progress: Progress = _noop, per_league: bool = True) -> NeuralMatchModel:
        import torch

        torch.manual_seed(7)
        self.pre.fit(time_split(train)[0])
        self.net = _build_net(self.pre.width).to(torch.device(self.device))
        self.epochs["global"] = self._train(self.net, train, cfg("training.nn.learning_rate"),
                                            cfg("training.nn.epochs"), cfg("training.nn.patience"),
                                            "global · all markets", progress)
        if per_league:
            for league in _tuned_leagues(train):
                net = copy.deepcopy(self.net)
                self.epochs[league] = self._train(net, train[train["league"] == league],
                                                  cfg("training.nn.tune_learning_rate"), cfg("training.nn.tune_epochs"),
                                                  cfg("training.nn.tune_patience"), f"{league} · fine-tune", progress)
                self.league_nets[league] = net
        return self

    def _run(self, net, frame: pd.DataFrame) -> pd.DataFrame:
        import torch

        dev = next(net.parameters()).device
        with torch.no_grad():
            outcome, over, btts, log_goals = net(torch.tensor(self.pre.transform(frame), device=dev))
            p1x2 = torch.softmax(outcome, dim=1).cpu().numpy()
            goals = torch.exp(log_goals).cpu().numpy()
            return pd.DataFrame({
                "match_id": frame["match_id"].to_numpy(),
                "p_home": p1x2[:, 0], "p_draw": p1x2[:, 1], "p_away": p1x2[:, 2],
                "p_over25": torch.sigmoid(over).cpu().numpy(), "p_btts": torch.sigmoid(btts).cpu().numpy(),
                "exp_home_goals": goals[:, 0], "exp_away_goals": goals[:, 1],
            })

    def predict(self, frame: pd.DataFrame, variant: str = "global") -> pd.DataFrame:
        if frame.empty:
            return _empty_predictions()
        if variant == "global":
            return self._run(self.net, frame)
        parts = [self._run(self.league_nets.get(str(league), self.net), rows)
                 for league, rows in frame.groupby("league")]
        return pd.concat(parts, ignore_index=True)

    def save(self, folder: Path) -> None:
        import torch

        folder.mkdir(parents=True, exist_ok=True)
        torch.save({"global": {k: v.cpu() for k, v in self.net.state_dict().items()},
                    **{lg: {k: v.cpu() for k, v in net.state_dict().items()} for lg, net in self.league_nets.items()}},
                   folder / "nets.pt")
        _merge_meta(folder, {"pre": self.pre.state(), "epochs": self.epochs, "leagues": sorted(self.league_nets),
                             "features": list(FEATURE_COLUMNS)})

    @classmethod
    def load(cls, folder: Path) -> NeuralMatchModel:
        import torch

        meta = json.loads((folder / "meta.json").read_text())
        model = cls(device="cpu")
        model.pre = _Preprocessor.from_state(meta["pre"])
        states = torch.load(folder / "nets.pt", weights_only=True, map_location="cpu")

        def make(state):
            net = _build_net(model.pre.width)
            net.load_state_dict(state)
            return net.eval()

        model.net = make(states["global"])
        model.league_nets = {lg: make(states[lg]) for lg in meta.get("leagues", [])}
        model.epochs = meta.get("epochs", {})
        return model


MODEL_CLASSES: dict[str, type] = {"xgb": XGBMatchModel, "nn": NeuralMatchModel}


def _merge_meta(folder: Path, values: dict[str, Any]) -> None:
    path = folder / "meta.json"
    meta = json.loads(path.read_text()) if path.exists() else {}
    path.write_text(json.dumps({**meta, **values}))


def save_league_choice(folder: Path, choice: dict[str, str]) -> None:
    _merge_meta(folder, {"league_choice": choice})


def save_feature_groups(folder: Path, groups: dict[str, bool]) -> None:
    _merge_meta(folder, {"feature_groups": groups})


def load_feature_groups(folder: Path) -> dict[str, bool]:
    path = folder / "meta.json"
    return json.loads(path.read_text()).get("feature_groups", {}) if path.exists() else {}


def load_league_choice(folder: Path) -> dict[str, str]:
    path = folder / "meta.json"
    return json.loads(path.read_text()).get("league_choice", {}) if path.exists() else {}


# ---------------------------------------------------------------------------
# Choosing global vs league per league, and the ensemble
# ---------------------------------------------------------------------------

def logloss_1x2(preds: pd.DataFrame, outcomes: pd.Series) -> np.ndarray:
    """Per-row 1X2 log loss; `outcomes` indexed like preds (0 home, 1 draw, 2 away)."""
    p = preds[["p_home", "p_draw", "p_away"]].to_numpy()
    y = outcomes.to_numpy().astype(int)
    return -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1))


class LeagueChooser:
    """Keeps a running per-league score of each variant and picks the better one.

    Fed fold by fold in season order, so the pick for season S only uses seasons before S.
    """

    def __init__(self) -> None:
        self.totals: dict[tuple[str, str], list[float]] = {}  # (league, variant) -> [sum loss, n]

    def choice(self, league: str) -> str:
        g, lg = self.totals.get((league, "global")), self.totals.get((league, "league"))
        if not g or not lg or lg[1] < cfg("training.league_switch_min_rows"):
            return "global"
        return "league" if lg[0] / lg[1] < g[0] / g[1] else "global"

    def update(self, league: str, variant: str, losses: np.ndarray) -> None:
        total = self.totals.setdefault((league, variant), [0.0, 0])
        total[0] += float(losses.sum())
        total[1] += len(losses)

    def all_choices(self) -> dict[str, str]:
        return {league: self.choice(league) for league in sorted({lg for lg, _ in self.totals})}

    def summary(self) -> dict[str, dict[str, Any]]:
        out = {}
        for league in sorted({lg for lg, _ in self.totals}):
            row = {"choice": self.choice(league)}
            for variant in ("global", "league"):
                t = self.totals.get((league, variant))
                row[variant] = round(t[0] / t[1], 5) if t and t[1] else None
                row["n"] = t[1] if t else 0
            out[league] = row
        return out


def compose_auto(variant_preds: dict[str, pd.DataFrame], frame: pd.DataFrame,
                 choice: dict[str, str]) -> pd.DataFrame:
    """Per league, take the rows of the chosen variant."""
    if frame.empty:
        return _empty_predictions()
    league_of = frame.set_index("match_id")["league"]
    parts = []
    for variant in ("global", "league"):
        preds = variant_preds[variant]
        chosen = preds["match_id"].map(lambda m, v=variant: choice.get(str(league_of.get(m)), "global") == v)
        parts.append(preds[chosen.to_numpy()])
    return pd.concat(parts, ignore_index=True)


def ensemble(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Average of several models' predictions on the matches they all cover."""
    parts = [p for p in parts if not p.empty]
    if not parts:
        return _empty_predictions()
    common = set(parts[0]["match_id"])
    for p in parts[1:]:
        common &= set(p["match_id"])
    aligned = [p[p["match_id"].isin(common)].set_index("match_id").sort_index()[list(OUTPUT_COLUMNS)]
               for p in parts]
    mean = sum(aligned) / len(aligned)
    return mean.reset_index()


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------

def walk_forward(feats: pd.DataFrame, family: str, first_test_season: int, progress: Progress = _noop,
                 device: str | None = None, per_league: bool = True
                 ) -> tuple[dict[str, pd.DataFrame], LeagueChooser]:
    """Predictions for every finished match from `first_test_season` on, for each variant.

    Each season is predicted by models trained only on earlier seasons. Returns the
    predictions per variant (global, league, auto) and the chooser with per-league scores.
    """
    rows = training_rows(feats)
    seasons = sorted(int(s) for s in rows["season"].unique() if s >= first_test_season)
    chooser = LeagueChooser()
    out: dict[str, list[pd.DataFrame]] = {v: [] for v in VARIANTS}
    for i, season in enumerate(seasons, start=1):
        train, test = rows[rows["season"] < season], rows[rows["season"] == season]
        if len(train) < cfg("training.min_train_rows") or test.empty:
            continue

        def fold_progress(event: dict[str, Any], season=season, i=i) -> None:
            progress({**event, "fold": i, "folds": len(seasons), "season": season})

        model = MODEL_CLASSES[family](device=device).fit(train, fold_progress, per_league=per_league)
        preds = {"global": model.predict(test, "global"),
                 "league": model.predict(test, "league") if per_league else model.predict(test, "global")}
        choice = {lg: chooser.choice(lg) for lg in test["league"].unique()}  # from earlier seasons only
        preds["auto"] = compose_auto(preds, test, choice)
        outcomes = test.set_index("match_id")["y_1x2"]
        league_of = test.set_index("match_id")["league"]
        for variant in ("global", "league"):
            p = preds[variant]
            losses = logloss_1x2(p, outcomes.loc[p["match_id"]])
            for league, mask in p.groupby(league_of.loc[p["match_id"]].to_numpy()).groups.items():
                chooser.update(str(league), variant, losses[np.asarray(mask)])
        for variant in VARIANTS:
            out[variant].append(preds[variant])
    return ({v: pd.concat(parts, ignore_index=True) if parts else _empty_predictions() for v, parts in out.items()},
            chooser)


def upcoming_rows(feats: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Matches still to be played (including last week's with no result yet)."""
    return feats[(feats["status"] == "scheduled") & (feats["date"] >= as_of - pd.Timedelta(days=7))]
