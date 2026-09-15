import math

import pandas as pd

from ffstats.core import all_play, optimal_lineup, standings, streaks
from ffstats.beer_mile import american_odds, softmax


def _scores():
    rows = []
    weeks = {1: {"a": 120, "b": 100, "c": 90}, 2: {"a": 80, "b": 110, "c": 95}}
    pairs = {1: [("a", "b"), ("c", "a")], 2: [("a", "c"), ("b", "a")]}
    for w, games in pairs.items():
        for x, y in games:
            px, py = weeks[w][x], weeks[w][y]
            for me, opp, p, q in ((x, y, px, py), (y, x, py, px)):
                rows.append({"week": w, "owner_id": me, "team_id": 0, "team": me, "points": p, "opp_owner_id": opp,
                             "opp_points": q, "result": "W" if p > q else "L", "margin": p - q,
                             "game_type": "regular_season", "playoff_tier": "NONE"})
    return pd.DataFrame(rows)


def test_all_play_counts_wins_against_everyone():
    scores = _scores().drop_duplicates(["week", "owner_id"])
    ap = all_play(scores)
    assert ap[(ap.week == 1) & (ap.owner_id == "a")].ap_w.iloc[0] == 2
    assert ap[(ap.week == 2) & (ap.owner_id == "a")].ap_w.iloc[0] == 0
    assert ap[ap.week == 1].ap_w.sum() == 3  # n*(n-1)/2 for 3 teams


def test_standings_luck():
    scores = _scores().drop_duplicates(["week", "owner_id"])
    st = standings(scores)
    assert st.loc["a", "exp_wins"] == 1.0
    assert math.isclose(st.loc["a", "luck"], st.loc["a", "W"] - 1.0)


def test_optimal_lineup_uses_flex_for_best_leftover():
    players = [
        {"position": "QB", "points": 20, "lineup_slot": "QB", "player": "qb"},
        {"position": "RB", "points": 15, "lineup_slot": "RB", "player": "rb1"},
        {"position": "RB", "points": 12, "lineup_slot": "BE", "player": "rb2"},
        {"position": "WR", "points": 9, "lineup_slot": "WR", "player": "wr1"},
        {"position": "TE", "points": 4, "lineup_slot": "RB/WR/TE", "player": "te"},
        {"position": "RB", "points": 30, "lineup_slot": "IR", "player": "ir"},
    ]
    total, chosen = optimal_lineup(players, {"QB": 1, "RB": 1, "WR": 1, "RB/WR/TE": 1})
    assert total == 56
    assert {p["player"] for p in chosen} == {"qb", "rb1", "wr1", "rb2"}


def test_streaks():
    s = streaks(["W", "W", "L", "L", "L", "W"])
    assert s["current"] == "W1" and s["longest_w"] == 2 and s["longest_l"] == 3


def test_odds_math():
    p = softmax(pd.Series([0.9, 0.5, 0.1]), 0.2)
    assert math.isclose(p.sum(), 1.0)
    assert american_odds(0.6).startswith("-") and american_odds(0.2).startswith("+")
