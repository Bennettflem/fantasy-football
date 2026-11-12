from __future__ import annotations

import numpy as np
import pandas as pd

from .core import default_week, lineup_efficiency, rank_scale, record_str, standings, weekly_scores
from .data import Season
from .identity import Identity
from .power import power_rankings, prior_seasons
from .render import pct, table

REASONS = {
    "power": "Bottom of the power rankings",
    "sched": "Schedule victim: fewer wins than they deserve",
    "pa": "Everyone's best game comes against them",
    "close": "Heartbreak losses",
    "chw": "Bench points have cost them games",
    "curse": "History repeating",
}


def softmax(s: pd.Series, temperature: float) -> pd.Series:
    z = (s - s.max()) / temperature
    e = np.exp(z)
    return e / e.sum()


def american_odds(p: float) -> str:
    p = min(max(p, 1e-6), 1 - 1e-6)
    if p >= 0.5:
        o = max(100, 5 * round(100 * p / (1 - p) / 5))
        return f"-{int(o)}"
    o = max(100, 5 * round(100 * (1 - p) / p / 5))
    return f"+{int(o)}"


def regular_season_rank(season: Season, ident: Identity) -> pd.Series:
    """Finishing order by regular-season record, worst last. ESPN's `final_standing` is the
    post-playoff placement, which drops the consolation bracket winner below teams that were
    better all year - this league runs the beer mile on the regular-season loser, so that is
    the only order that decides it."""
    st = standings(weekly_scores(season, ident))
    return pd.Series(dtype=int) if st.empty else st["rank"]


def beer_mile_odds(seasons: dict[int, Season], year: int, week: int | None = None,
                   ident: Identity | None = None) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    pr = power_rankings(seasons, year, W, ident, with_movement=False)
    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    eff = lineup_efficiency(season, ident, W)

    comp = pd.DataFrame(index=st.index)
    comp["power"] = 1 - pr.score.reindex(st.index) / 100
    comp["sched"] = rank_scale(st.exp_wins - st.W)
    comp["pa"] = rank_scale(st.pa_pg)
    losses = scores[scores.result == "L"]
    comp["close"] = rank_scale(losses[losses.margin > -5].groupby("owner_id").size().reindex(st.index).fillna(0))
    merged = losses.merge(eff, on=["week", "owner_id"], how="left")
    chw = merged[merged.optimal >= merged.opp_points].groupby("owner_id").size()
    comp["chw"] = rank_scale(chw.reindex(st.index).fillna(0))
    prior = [regular_season_rank(s, ident) for s in prior_seasons(seasons, year)]
    prior = [p for p in prior if not p.empty]
    if prior:
        last_places = pd.concat([(p == p.max()).astype(int) for p in prior]).groupby(level=0).sum()
        curse = pd.concat(prior).groupby(level=0).mean() + last_places
        comp["curse"] = rank_scale(curse.reindex(st.index))
    else:
        comp["curse"] = 0.5

    bad_luck = comp[["sched", "pa", "close", "chw", "curse"]].mean(axis=1)
    misery = 0.6 * comp.power + 0.4 * bad_luck
    temperature = max(0.12, 0.28 - 0.012 * W)
    prob = softmax(misery, temperature)

    out = pd.DataFrame({"prob": prob, "misery": misery}, index=st.index)
    out["rank"] = out.prob.rank(ascending=False, method="min").astype(int)
    out["label"] = [ident.label(o, year) for o in out.index]
    out["odds"] = [american_odds(p) for p in out.prob]
    out["record"] = [record_str(st.loc[o]) for o in out.index]
    out["why"] = [REASONS[comp.loc[o].idxmax()] for o in out.index]
    for k in comp.columns:
        out[f"c_{k}"] = comp[k]
    out.attrs["week"] = W
    out.attrs["official"] = None
    if season.is_complete:
        order = regular_season_rank(season, ident)
        if not order.empty:
            out.attrs["official"] = ident.label(str(order.idxmax()), year)
    return out.sort_values("prob", ascending=False)


def beer_mile_markdown(df: pd.DataFrame, season: Season) -> str:
    W = df.attrs["week"]
    rows = [{"#": r["rank"], "Team (Owner)": r.label, "Odds": r.odds, "Implied": pct(r.prob),
             "Record": r.record, "Why": r.why} for _, r in df.iterrows()]
    lines = [f"## Beer Mile Odds: {season.year}, through week {W}", "", table(rows), "",
             "_Misery = 60% inverse power ranking + 40% bad-luck factor (schedule luck, points against, "
             "close losses, games lost to bench points, history). Odds are softmax over misery._"]
    if df.attrs.get("official"):
        lines += ["", f"**OFFICIAL:** {df.attrs['official']} finished last in the regular season and runs the beer mile."]
    return "\n".join(lines)
