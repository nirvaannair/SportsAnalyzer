"""Forward test: mock bets, settlement maths, and learning a correction from misses."""

import numpy as np

from backend.forward import apply_temperature, fit_temperature, mock_picks


def test_mock_picks_favourite_and_value() -> None:
    p = {"p_home": 0.5, "p_draw": 0.3, "p_away": 0.2, "p_over25": 0.6}
    picks = mock_picks(p, {"1x2_home": 2.5, "1x2_away": 3.0, "ou25_over": 1.5})
    assert {(b["rule"], b["selection"]) for b in picks} == {("favourite", "home"), ("value", "home")}
    # 0.5 × 2.5 − 1 = 0.25 edge on home; away 0.2 × 3.0 − 1 < 0; over 0.6 × 1.5 − 1 < 0.05
    assert mock_picks(p, {})[0]["price"] is None  # a favourite pick is recorded even without a price


def test_temperature_keeps_probabilities_valid() -> None:
    probs = np.array([[0.6, 0.25, 0.15], [0.2, 0.3, 0.5]])
    for t in (0.7, 1.0, 1.5):
        out = apply_temperature(probs, t)
        assert np.allclose(out.sum(axis=1), 1)
    assert apply_temperature(probs, 1.5)[0, 0] < 0.6 < apply_temperature(probs, 0.7)[0, 0]


def test_overconfident_model_is_softened() -> None:
    rng = np.random.default_rng(0)
    true = rng.dirichlet([3, 2, 2], size=3000)
    outcome = np.array([rng.choice(3, p=p) for p in true])
    overconfident = apply_temperature(true, 0.6)  # sharper than reality
    assert fit_temperature(overconfident, outcome) > 1.2
