import math

import pandas as pd
from pytest import approx

from ffstats.backtest import (SCHEMES, backtest, decay_weights, decayed_mean, evaluate,
                              projected_strength, scheme_pf_only, spearman)
from ffstats.core import weekly_scores


def test_decay_weights_halve_over_one_half_life():
    weeks = pd.Series([1, 2, 3, 4])
    w = decay_weights(weeks, through=4, half_life=2)
    assert w.iloc[3] == approx(1.0)          # current week counts fully
    assert w.iloc[1] == approx(0.5)          # two weeks back counts half
    assert w.iloc[0] < w.iloc[1] < w.iloc[2] < w.iloc[3]


def test_no_decay_is_the_plain_mean():
    df = pd.DataFrame({"week": [1, 2, 3], "owner_id": ["a"] * 3, "v": [10.0, 20.0, 60.0]})
    assert decayed_mean(df, "v", 3, None)["a"] == approx(30.0)


def test_decay_pulls_the_mean_toward_recent_weeks():
    df = pd.DataFrame({"week": [1, 2, 3], "owner_id": ["a"] * 3, "v": [0.0, 0.0, 90.0]})
    flat = decayed_mean(df, "v", 3, None)["a"]
    fast = decayed_mean(df, "v", 3, half_life=1)["a"]
    slow = decayed_mean(df, "v", 3, half_life=8)["a"]
    assert fast > slow > flat                # shorter half-life leans harder on week 3
    assert fast < 90.0                       # but never discards the earlier weeks entirely


def test_spearman_is_rank_only():
    a = pd.Series([1.0, 2.0, 3.0, 4.0])
    assert spearman(a, pd.Series([10.0, 20.0, 30.0, 40.0])) == approx(1.0)
    assert spearman(a, pd.Series([40.0, 30.0, 20.0, 10.0])) == approx(-1.0)
    # Monotone but wildly non-linear still scores a perfect 1.
    assert spearman(a, pd.Series([1.0, 2.0, 3.0, 4000.0])) == approx(1.0)


def test_projected_strength_sums_only_starters(seasons, ident):
    proj = projected_strength(seasons[2100], ident, week=1)
    assert len(proj) == 4
    assert (proj > 0).all()
    started = seasons[2100].lineups
    started = started[(started.matchup_period == 1) & started.started]
    assert proj.sum() == approx(started.projected_points.sum())


def test_projected_strength_is_empty_for_a_week_with_no_data(seasons, ident):
    assert projected_strength(seasons[2100], ident, week=99).empty


def test_a_perfect_oracle_scores_perfectly(seasons, ident):
    """Validates the harness itself: a scheme that already knows next week must max out."""
    def oracle(seasons, year, ident, W):
        nxt = weekly_scores(seasons[year], ident, through_week=W + 1)
        return nxt[nxt.week == W + 1].set_index("owner_id").points

    out = evaluate(seasons, ident, oracle)
    assert out["weeks"] > 0 and out["games"] > 0
    assert out["spearman"] == approx(1.0)
    assert out["h2h_pct"] == approx(1.0)
    assert out["top_half_edge"] > 0


def test_an_inverted_oracle_scores_as_badly_as_possible(seasons, ident):
    def anti(seasons, year, ident, W):
        nxt = weekly_scores(seasons[year], ident, through_week=W + 1)
        return -nxt[nxt.week == W + 1].set_index("owner_id").points

    out = evaluate(seasons, ident, anti)
    assert out["spearman"] == approx(-1.0)
    assert out["h2h_pct"] == approx(0.0)
    assert out["top_half_edge"] < 0


def test_schemes_never_see_the_week_they_predict(seasons, ident):
    """The whole result is worthless if a scheme can peek, so pin it."""
    seen = []

    def spy(seasons, year, ident, W):
        scores = weekly_scores(seasons[year], ident, through_week=W)
        seen.append((year, W, int(scores.week.max())))
        return scores.groupby("owner_id").points.mean()

    evaluate(seasons, ident, spy)
    assert seen, "the spy scheme was never called"
    for _year, W, max_week_seen in seen:
        assert max_week_seen <= W


def test_evaluate_counts_one_row_per_matchup(seasons, ident):
    out = evaluate(seasons, ident, scheme_pf_only)
    # Fixture: 4 owners = 2 games a week. Only 2100 has a played week after W>=2.
    assert out["games"] == 2 * out["weeks"]
    assert 0.0 <= out["h2h_pct"] <= 1.0


def test_min_week_controls_where_the_backtest_starts(seasons, ident):
    early = evaluate(seasons, ident, scheme_pf_only, min_week=2)
    late = evaluate(seasons, ident, scheme_pf_only, min_week=3)
    assert early["weeks"] > late["weeks"]


def test_backtest_returns_a_row_per_scheme_sorted_by_spearman(seasons, ident):
    df = backtest(seasons, ident)
    assert set(df.index) == set(SCHEMES)
    assert list(df.columns) == ["spearman", "h2h_pct", "top_half_edge", "weeks", "games"]
    ordered = df.spearman.dropna().tolist()
    assert ordered == sorted(ordered, reverse=True)


def test_every_shipped_scheme_runs_without_error(seasons, ident):
    df = backtest(seasons, ident)
    assert (df.weeks > 0).all(), f"produced nothing: {df[df.weeks == 0].index.tolist()}"
    assert not df.h2h_pct.isna().any()
