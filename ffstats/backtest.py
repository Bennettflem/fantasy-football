"""Does a power-ranking scheme actually predict next week?

Every scheme here is scored the same way: build it from data through week W only, then check
it against what happened in week W+1. Nothing from W+1 may enter a scheme except published
projections, which are known before kickoff.

The point is to settle design arguments with evidence instead of taste - whether recency
weighting helps, whether the week-4 weight switch earns its keep, whether roster projections
beat results-to-date.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from .core import all_play, lineup_efficiency, rank_scale, standings, waiver_share, weekly_scores
from .data import Season
from .identity import Identity
from .power import WEIGHTS_EARLY, WEIGHTS_LATE, history_factors
from .render import table

MIN_WEEK = 2          # a one-game ranking predicts nothing; start once there are two
Scheme = Callable[[dict, int, Identity, int], pd.Series]


def spearman(a: pd.Series, b: pd.Series) -> float:
    """Rank correlation, as Pearson on the ranks. Avoids a scipy dependency for one call."""
    ra, rb = a.rank(), b.rank()
    return float(ra.corr(rb))


def decay_weights(weeks: pd.Series, through: int, half_life: float) -> pd.Series:
    """Exponential recency weights: a game `half_life` weeks back counts half as much."""
    return pd.Series(0.5 ** ((through - weeks) / half_life), index=weeks.index)


def decayed_mean(df: pd.DataFrame, value: str, through: int, half_life: float | None) -> pd.Series:
    """Per-owner mean of `value`, optionally weighted toward recent weeks."""
    if half_life is None:
        return df.groupby("owner_id")[value].mean()
    w = decay_weights(df.week, through, half_life)
    num = (df[value] * w).groupby(df.owner_id).sum()
    den = w.groupby(df.owner_id).sum()
    return num / den


def projected_strength(season: Season, ident: Identity, week: int) -> pd.Series:
    """ESPN's projected total for each team's week-`week` starting lineup, by owner.

    Published before kickoff, so a ranking is allowed to use it. This is the forward-looking
    signal results-to-date cannot see: it already knows who is hurt, benched or on bye.
    """
    lineups = season.lineups
    if lineups.empty:
        return pd.Series(dtype=float)
    g = lineups[(lineups.matchup_period == week) & lineups.started]
    if g.empty:
        return pd.Series(dtype=float)
    out = {}
    for tid, v in g.groupby("team_id").projected_points.sum().items():
        oid = ident.team_owner.get((season.year, int(tid)), "")
        if oid:
            out[oid] = float(v)
    return pd.Series(out, dtype=float)


# --- schemes -------------------------------------------------------------------------------
# Each returns a score per owner_id built only from information available at the end of week W.

def _weighted(seasons, year, ident, W, weights, half_life, proj_weight=0.0) -> pd.Series:
    """The shipped component structure, with recency and projection made adjustable."""
    season = seasons[year]
    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    ap = all_play(scores)

    comp = pd.DataFrame(index=st.index)
    comp["all_play"] = rank_scale(decayed_mean(ap, "ap_pct", W, half_life).reindex(st.index))
    comp["pf"] = rank_scale(decayed_mean(scores, "points", W, half_life).reindex(st.index))
    comp["record"] = rank_scale(st.win_pct + st.PF / 1e6)
    recent = ap[ap.week > W - 3].groupby("owner_id").ap_pct.mean()
    comp["recent"] = rank_scale(recent.reindex(st.index))
    eff = lineup_efficiency(season, ident, W).groupby("owner_id").efficiency.mean()
    comp["roster"] = (rank_scale(waiver_share(season, ident, W).reindex(st.index))
                      + rank_scale(eff.reindex(st.index))) / 2

    w = dict(weights)
    hist = history_factors(seasons, ident, year)
    if hist.empty:
        w.pop("history", None)
    else:
        comp["history"] = (rank_scale(hist.turnaround.reindex(st.index))
                           + rank_scale(hist.waiver_share.reindex(st.index))) / 2

    if proj_weight:
        proj = projected_strength(season, ident, W + 1)
        if proj.empty:
            return pd.Series(dtype=float)
        comp["proj"] = rank_scale(proj.reindex(st.index))
        w = {k: v * (1 - proj_weight) for k, v in w.items()}
        w["proj"] = proj_weight

    total = sum(w.values())
    return sum(comp[k].fillna(0.5) * v for k, v in w.items()) / total * 100


def scheme_current(seasons, year, ident, W) -> pd.Series:
    """What the project ships today, including the week-4 weight switch."""
    from .power import power_rankings
    return power_rankings(seasons, year, week=W, ident=ident, with_movement=False).score


def scheme_flat_early(seasons, year, ident, W) -> pd.Series:
    """Shipped scheme with the early weights held all season - isolates the switch."""
    return _weighted(seasons, year, ident, W, WEIGHTS_EARLY, None)


def scheme_flat_late(seasons, year, ident, W) -> pd.Series:
    """Shipped scheme with the late weights used from week 2 - the other half of that test."""
    return _weighted(seasons, year, ident, W, WEIGHTS_LATE, None)


def scheme_decay(half_life: float) -> Scheme:
    def f(seasons, year, ident, W):
        return _weighted(seasons, year, ident, W,
                         WEIGHTS_EARLY if W <= 3 else WEIGHTS_LATE, half_life)
    f.__name__ = f"decay_hl{half_life:g}"
    return f


def scheme_projection(proj_weight: float) -> Scheme:
    def f(seasons, year, ident, W):
        return _weighted(seasons, year, ident, W,
                         WEIGHTS_EARLY if W <= 3 else WEIGHTS_LATE, None, proj_weight)
    f.__name__ = f"proj_{proj_weight:g}"
    return f


def scheme_pf_only(seasons, year, ident, W) -> pd.Series:
    """Baseline: season points per game. If nothing beats this, the machinery is decoration."""
    return standings(weekly_scores(seasons[year], ident, through_week=W)).pf_pg


def scheme_all_play_only(seasons, year, ident, W) -> pd.Series:
    return standings(weekly_scores(seasons[year], ident, through_week=W)).ap_pct


def scheme_recent3(seasons, year, ident, W) -> pd.Series:
    """Baseline: last three weeks of all-play and nothing else. Pure recency."""
    ap = all_play(weekly_scores(seasons[year], ident, through_week=W))
    return ap[ap.week > W - 3].groupby("owner_id").ap_pct.mean()


def scheme_record_only(seasons, year, ident, W) -> pd.Series:
    st = standings(weekly_scores(seasons[year], ident, through_week=W))
    return st.win_pct + st.PF / 1e6


def scheme_espn_projection(seasons, year, ident, W) -> pd.Series:
    """Baseline: rank purely by next week's projected lineup total."""
    return projected_strength(seasons[year], ident, W + 1)


SCHEMES: dict[str, Scheme] = {
    "current (shipped)": scheme_current,
    "early weights only": scheme_flat_early,
    "late weights only": scheme_flat_late,
    "decay hl=2": scheme_decay(2),
    "decay hl=4": scheme_decay(4),
    "decay hl=8": scheme_decay(8),
    "proj 20%": scheme_projection(.20),
    "proj 35%": scheme_projection(.35),
    "proj 50%": scheme_projection(.50),
    "-- points/game": scheme_pf_only,
    "-- all-play": scheme_all_play_only,
    "-- last 3 weeks": scheme_recent3,
    "-- record": scheme_record_only,
    "-- projection": scheme_espn_projection,
}


# --- evaluation ----------------------------------------------------------------------------

def evaluate(seasons: dict[int, Season], ident: Identity, scheme: Scheme,
             min_week: int = MIN_WEEK) -> dict:
    """Score a scheme on every (season, week) where a next week exists and was played.

    Three measures, because they answer different questions:
      spearman       - does the whole ordering track next week's scoring?
      h2h_pct        - would the ranking have picked next week's actual winners?
      top_half_edge  - does the top half of the ranking outscore the bottom half?
    """
    rhos: list[float] = []
    gaps: list[float] = []
    hits = games = n_weeks = 0
    for year in sorted(seasons):
        season = seasons[year]
        for W in range(min_week, season.reg_weeks):
            nxt = weekly_scores(season, ident, through_week=W + 1)
            nxt = nxt[nxt.week == W + 1]
            if nxt.empty:
                continue
            s = scheme(seasons, year, ident, W)
            if s is None or len(s) == 0:
                continue
            s = s.dropna()
            actual = nxt.set_index("owner_id").points
            common = s.index.intersection(actual.index)
            if len(common) < 4:
                continue
            n_weeks += 1
            rho = spearman(s[common], actual[common])
            if pd.notna(rho):
                rhos.append(float(rho))
            for _, g in nxt.iterrows():
                o, p = g.owner_id, g.opp_owner_id
                # `o > p` keeps one row per matchup; ties have no winner to pick.
                if o not in s.index or p not in s.index or g.result == "T" or o > p:
                    continue
                games += 1
                favored = o if s[o] > s[p] else p
                hits += favored == (o if g.result == "W" else p)
            half = len(common) // 2
            ordered = s[common].sort_values(ascending=False).index
            gaps.append(float(actual[ordered[:half]].mean() - actual[ordered[-half:]].mean()))
    return {
        "spearman": float(np.mean(rhos)) if rhos else float("nan"),
        "h2h_pct": hits / games if games else float("nan"),
        "top_half_edge": float(np.mean(gaps)) if gaps else float("nan"),
        "weeks": n_weeks,
        "games": games,
    }


def backtest(seasons: dict[int, Season], ident: Identity | None = None,
             schemes: dict[str, Scheme] | None = None, min_week: int = MIN_WEEK) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    rows = {name: evaluate(seasons, ident, fn, min_week)
            for name, fn in (schemes or SCHEMES).items()}
    df = pd.DataFrame(rows).T
    df.index.name = "scheme"
    return df.sort_values("spearman", ascending=False)


def backtest_markdown(df: pd.DataFrame) -> str:
    rows = [{"Scheme": name,
             "Spearman": f"{r.spearman:+.3f}",
             "Picks next week": f"{r.h2h_pct:.1%}",
             "Top-half edge": f"{r.top_half_edge:+.1f}",
             "Weeks": f"{int(r.weeks)}",
             "Games": f"{int(r.games)}"}
            for name, r in df.iterrows()]
    return "\n".join([
        "## Power ranking backtest",
        "",
        table(rows),
        "",
        "_Each scheme is built from data through week W and scored against week W+1._",
        "",
        "_**Spearman** is the rank correlation with next week's scoring; 0 means no signal. "
        "**Picks next week** is how often the higher-ranked team won the actual matchup, where "
        "50% is a coin flip. **Top-half edge** is how many more points the top half of the "
        "ranking scored than the bottom half. Rows starting `--` are single-component "
        "baselines, not candidate schemes._",
    ])
