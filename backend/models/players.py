"""Player impact ratings and lineup features, point-in-time. Football data only, never odds.

Impact ("with / without") for a player = the team's goal difference per 90 minutes while he
is on the pitch minus while he is off it (in the team's matches he was part of), each side
shrunk towards 0 until there are enough minutes, with older matches fading (half-life 1 year).

Lineup features for a match (from ratings *before* that match):
  xi_impact            sum of the starters' impact ratings
  xi_minutes           average recent minutes of the starters (experience / continuity)
  regulars_out         how many of the team's 11 most-used players (last 6 matches) don't start
  regulars_out_impact  sum of the impact of those missing regulars
For matches whose lineup isn't known yet (upcoming), the expected XI is the regulars.
Matches without lineup data get NaN features (the models handle missing values).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SHRINK_90S = 8.0  # ratings start at 0 and need ~8 full matches on and off to move halfway
HALF_LIFE_DAYS = 365.0
REGULAR_WINDOW = 6
PLAYER_FEATURES: tuple[str, ...] = ("xi_impact", "xi_minutes", "regulars_out", "regulars_out_impact")


@dataclass
class _PlayerState:
    on_gd: float = 0.0
    on_90s: float = 0.0
    off_gd: float = 0.0
    off_90s: float = 0.0
    minutes: float = 0.0  # decayed minutes played
    last: pd.Timestamp | None = None

    def decay(self, day: pd.Timestamp) -> None:
        if self.last is not None:
            factor = 0.5 ** (max(0, (day - self.last).days) / HALF_LIFE_DAYS)
            self.on_gd *= factor
            self.on_90s *= factor
            self.off_gd *= factor
            self.off_90s *= factor
            self.minutes *= factor
        self.last = day

    @property
    def impact(self) -> float:
        on = self.on_gd / (self.on_90s + SHRINK_90S)
        off = self.off_gd / (self.off_90s + SHRINK_90S)
        return on - off


@dataclass
class PlayerRatings:
    """Final state after processing all matches (for player pages)."""

    players: dict[int, _PlayerState] = field(default_factory=dict)
    team_of: dict[int, int] = field(default_factory=dict)
    apps: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    starts: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    total_minutes: dict[int, float] = field(default_factory=lambda: defaultdict(float))
    last_played: dict[int, pd.Timestamp] = field(default_factory=dict)


def _assign_goals(matches: pd.DataFrame, goals: pd.DataFrame) -> dict[int, list[tuple[int, float]]]:
    """match_id -> [(team that scored, minute)], own goals credited to the team the score says is short."""
    score = matches.set_index("match_id")[["home_id", "away_id", "home_goals", "away_goals"]]
    out: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for match_id, events in goals.groupby("match_id"):
        if match_id not in score.index:
            continue
        s = score.loc[match_id]
        need = {int(s.home_id): s.home_goals, int(s.away_id): s.away_goals}
        normal = events[events["kind"] != "own_goal"] if "kind" in events else events
        own = events[events["kind"] == "own_goal"] if "kind" in events else events.iloc[0:0]
        counts: dict[int, int] = defaultdict(int)
        for e in normal.itertuples(index=False):
            out[match_id].append((int(e.team_id), float(e.minute if pd.notna(e.minute) else 45)))
            counts[int(e.team_id)] += 1
        for e in own.itertuples(index=False):
            short = [t for t, n in need.items() if pd.notna(n) and counts[t] < n]
            team = short[0] if short else int(e.team_id)
            out[match_id].append((team, float(e.minute if pd.notna(e.minute) else 45)))
            counts[team] += 1
    return out


def player_features(matches: pd.DataFrame, lineups: pd.DataFrame, goals: pd.DataFrame,
                    ratings_out: PlayerRatings | None = None) -> pd.DataFrame:
    """match_id + home_/away_ PLAYER_FEATURES, computed in date order from earlier matches only."""
    columns = ["match_id", *(f"{side}_{f}" for side in ("home", "away") for f in PLAYER_FEATURES)]
    if lineups.empty:
        return pd.DataFrame(columns=columns)
    goal_list = _assign_goals(matches, goals)
    by_match = {mid: grp for mid, grp in lineups.groupby("match_id")}
    state: dict[int, _PlayerState] = {}
    recent: dict[int, deque] = defaultdict(lambda: deque(maxlen=REGULAR_WINDOW))  # team -> [(player, minutes)]
    ratings = ratings_out or PlayerRatings()
    rows = []

    def regulars(team: int) -> list[int]:
        total: dict[int, float] = defaultdict(float)
        for appearance in recent[team]:
            for player, minutes in appearance:
                total[player] += minutes
        return [p for p, _ in sorted(total.items(), key=lambda kv: -kv[1])[:11]]

    def impact(player: int) -> float:
        return state[player].impact if player in state else 0.0

    ordered = matches.sort_values(["date", "match_id"])
    for m in ordered.itertuples(index=False):
        lineup = by_match.get(m.match_id)
        known = lineup is not None and len(lineup) > 0
        feats: dict[str, float] = {"match_id": m.match_id}
        for side, team in (("home", m.home_id), ("away", m.away_id)):
            if not recent[team] and not known:
                continue  # no player history for this team yet
            regs = regulars(team)
            if known:
                starters = lineup[(lineup["team_id"] == team) & lineup["started"]]["player_id"].tolist()
                if not starters:
                    continue
            elif m.status == "scheduled":
                starters = regs  # expected XI
            else:
                continue  # finished match with no lineup data
            missing = [p for p in regs if p not in set(starters)] if regs else []
            feats[f"{side}_xi_impact"] = float(sum(impact(p) for p in starters))
            feats[f"{side}_xi_minutes"] = float(np.mean([state[p].minutes if p in state else 0.0 for p in starters]))
            feats[f"{side}_regulars_out"] = float(len(missing)) if regs else np.nan
            feats[f"{side}_regulars_out_impact"] = float(sum(impact(p) for p in missing)) if regs else np.nan
        rows.append(feats)

        if not known or m.status != "finished":
            continue
        # Update ratings with this match (after its features were recorded).
        day = pd.Timestamp(m.date)
        scored = goal_list.get(m.match_id, [])
        for team, opponent in ((m.home_id, m.away_id), (m.away_id, m.home_id)):
            players = lineup[lineup["team_id"] == team]
            match_gd = sum(1 for t, _ in scored if t == team) - sum(1 for t, _ in scored if t == opponent)
            appearance = []
            for p in players.itertuples(index=False):
                on = 0.0 if p.started else (float(p.minute_on) if pd.notna(p.minute_on) else None)
                if on is None:
                    continue  # unused substitute
                off = float(p.minute_off) if pd.notna(p.minute_off) else 90.0
                minutes = max(0.0, off - on)
                on_gd = sum(1 for t, mi in scored if t == team and on <= mi < off) - \
                    sum(1 for t, mi in scored if t == opponent and on <= mi < off)
                s = state.setdefault(int(p.player_id), _PlayerState())
                s.decay(day)
                s.on_gd += on_gd
                s.on_90s += minutes / 90
                s.off_gd += match_gd - on_gd
                s.off_90s += (90 - minutes) / 90
                s.minutes += minutes
                appearance.append((int(p.player_id), minutes))
                ratings.team_of[int(p.player_id)] = int(team)
                ratings.apps[int(p.player_id)] += 1
                ratings.starts[int(p.player_id)] += int(bool(p.started))
                ratings.total_minutes[int(p.player_id)] += minutes
                ratings.last_played[int(p.player_id)] = day
            recent[team].append(appearance)
    ratings.players = state
    return pd.DataFrame(rows).reindex(columns=columns)
