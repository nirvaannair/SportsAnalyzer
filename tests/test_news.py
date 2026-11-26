"""News: scoring headlines, parsing ESPN's feed, point-in-time news features, feature switches."""

import numpy as np
import pandas as pd

from backend.models.features import (
    FEATURE_GROUPS,
    _news_features,
    apply_feature_groups,
    build_features,
)
from backend.scraping.news_analysis import analyse
from backend.scraping.spiders.espn_news import parse_articles
from tests.test_models import synthetic_league


def test_good_bad_and_injury_news() -> None:
    good = analyse("Haaland hat-trick as Man City thrash Spurs to go top", "City extend lead with dominant win")
    bad = analyse("Arteta under pressure as Arsenal slump to third straight defeat", None)
    hurt = analyse("Saka ruled out for six weeks with hamstring injury", "Blow for Arsenal")
    neutral = analyse("Transfer rumors: Barcelona eyeing defender", None)
    assert good["sentiment"] > 0.5 and not good["injury"]
    assert bad["sentiment"] < -0.5
    assert hurt["sentiment"] < 0 and hurt["injury"]
    assert abs(neutral["sentiment"]) < 0.15 and neutral["signals"]["transfer"]


def test_betting_words_do_not_score() -> None:
    scored = analyse("Betting tips and odds for the weekend", None)
    assert scored["signals"]["words_score"] == 0 and abs(scored["sentiment"]) < 0.15


def test_parse_espn_articles_keeps_tags_and_no_betting_fields() -> None:
    payload = {"articles": [{
        "id": 1, "headline": "H", "description": "D", "published": "2026-11-26T08:57:49Z",
        "links": {"web": {"href": "https://espn.com/x"}},
        "categories": [{"type": "team", "teamId": 360, "description": "Manchester United"},
                       {"type": "athlete", "athleteId": 7, "description": "A Player"},
                       {"type": "topic", "description": "soccer transfers"}],
    }, {"id": 2, "headline": None}]}
    [article] = parse_articles(payload, "ENG1")
    assert article["teams"] == [{"id": "360", "name": "Manchester United"}]
    assert article["players"] == [{"id": "7", "name": "A Player"}]
    assert article["url"] == "https://espn.com/x" and article["league"] == "ENG1"


def test_news_features_only_use_articles_before_the_match_day() -> None:
    matches = synthetic_league(1).head(20)
    day = matches.iloc[10]["date"]
    home = int(matches.iloc[10]["home_id"])
    news = pd.DataFrame({
        "team_id": [home, home, home],
        "published_at": [day - pd.Timedelta(days=3), day + pd.Timedelta(hours=2), day - pd.Timedelta(days=9)],
        "sentiment": [-0.8, 0.9, 0.9], "injury": [True, False, False], "weight": [1.0, 1.0, 1.0],
    })
    feats = _news_features(matches, news).set_index("match_id")
    row = feats.loc[matches.iloc[10]["match_id"]]
    assert row["home_news_n7"] == 1  # only the article 3 days before; not same-day, not 9 days before
    assert row["home_news_sentiment7"] == -0.8
    assert row["home_news_injury7"] == 1


def test_switched_off_groups_are_blanked() -> None:
    feats = build_features(synthetic_league(2))
    feats[list(FEATURE_GROUPS["news"])] = 1.0
    off = apply_feature_groups(feats, {"players": True, "news": False})
    assert off[list(FEATURE_GROUPS["news"])].isna().all().all()
    on = apply_feature_groups(feats, {"news": True})
    assert np.allclose(on[list(FEATURE_GROUPS["news"])].to_numpy(), 1.0)


def test_rss_items_become_articles() -> None:
    from backend.scraping.spiders.rss_news import parse_feed

    items = [{"title": "Spurs held by Wolves", "description": "A draw.", "link": "https://x/1", "guid": "g1",
              "pubDate": "Wed, 26 Nov 2026 08:57:49 GMT"},
             {"title": "No date", "description": "", "link": "", "guid": "", "pubDate": ""}]
    [article] = parse_feed(items, "bbc")
    assert article["source"] == "bbc" and article["published"].startswith("2026-11-26T08:57:49")
    assert article["id"].startswith("bbc:") and article["teams"] == []


def test_team_names_in_headlines(settings_override) -> None:
    from backend.scraping.news_loader import _alias, teams_in_text

    settings_override({"news": {"team_names": {"ambiguous": ["united", "city", "inter", "reading"]}}})
    aliases = {a: i for n, i in {"Manchester City FC": 1, "Manchester United": 2, "Arsenal": 3, "Inter": 4,
                                  "Reading": 5}.items() if (a := _alias(n))}
    assert "inter" not in aliases and "reading" not in aliases and aliases["manchester city"] == 1
    found = dict(teams_in_text("Arsenal beat Manchester City as Manchester United watch", aliases))
    assert set(found) == {1, 2, 3}
    assert teams_in_text("United and City fans protest while reading the news", aliases) == []


def test_team_stat_features_use_only_earlier_matches(settings_override) -> None:
    from backend.models.features import _team_stat_features

    settings_override({"features": {"team_stats": ["possessionPct", "af_expected_goals"], "team_stats_window": 2}})
    matches = synthetic_league(1).head(30)
    stats = pd.DataFrame([{"match_id": m.match_id, "team_id": t, "possessionPct": 40.0 + i,
                           "af_expected_goals": 1.0 + (t == m.home_id)}
                          for i, m in enumerate(matches.itertuples()) for t in (m.home_id, m.away_id)])
    feats = _team_stat_features(matches, stats).set_index("match_id")
    first = matches.iloc[0]
    assert np.isnan(feats.loc[first["match_id"], "home_ts_possessionPct_for"])  # no earlier match
    changed = stats.copy()
    target = matches.iloc[20]["match_id"]
    changed.loc[changed["match_id"] == target, "possessionPct"] = 99.0
    after = _team_stat_features(matches, changed).set_index("match_id")
    upto = matches[matches["date"] <= matches.iloc[20]["date"]]["match_id"]
    pd.testing.assert_frame_equal(feats.loc[upto], after.loc[upto])
