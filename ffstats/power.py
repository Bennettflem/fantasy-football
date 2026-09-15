from __future__ import annotations

import pandas as pd

from .core import (all_play, default_week, lineup_efficiency, rank_scale, record_str, season_profile,
                   standings, waiver_share, weekly_scores)
from .data import Season
from .identity import Identity
from .render import table

WEIGHTS_LATE = {"all_play": .30, "pf": .20, "record": .15, "recent": .15, "roster": .10, "history": .10}
WEIGHTS_EARLY = {"all_play": .30, "pf": .20, "record": .10, "recent": .05, "roster": .10, "history": .25}
DRIVERS = {
    "all_play": "Would beat almost anyone, any week",
    "pf": "Scoring machine",
    "record": "Winning the games that count",
    "recent": "Hot over the last 3 weeks",
    "roster": "Working the wire and nailing lineups",
    "history": "History says they turn seasons around",
}
COMPONENT_NAMES = {
    "all_play": "All-play win%", "pf": "Points/game", "record": "Record", "recent": "Last 3 weeks",
    "roster": "Roster management", "history": "Owner history",
}

_profiles: dict[int, pd.DataFrame] = {}


def profile(season: Season, ident: Identity) -> pd.DataFrame:
    if season.year not in _profiles:
        _profiles[season.year] = season_profile(season, ident)
    return _profiles[season.year]


def prior_seasons(seasons: dict[int, Season], before_year: int) -> list[Season]:
    return [s for y, s in sorted(seasons.items()) if y < before_year and s.is_complete]


def history_factors(seasons: dict[int, Season], ident: Identity, before_year: int) -> pd.DataFrame:
    frames = [profile(s, ident)[["turnaround", "waiver_share"]] for s in prior_seasons(seasons, before_year)]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["turnaround", "waiver_share"])
    return pd.concat(frames).groupby(level=0).mean()


def power_rankings(seasons: dict[int, Season], year: int, week: int | None = None,
                   ident: Identity | None = None, with_movement: bool = True) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    ap = all_play(scores)
    recent = ap[ap.week > W - 3].groupby("owner_id").ap_pct.mean()
    ws = waiver_share(season, ident, W)
    eff = lineup_efficiency(season, ident, W).groupby("owner_id").efficiency.mean()
    hist = history_factors(seasons, ident, year)

    comp = pd.DataFrame(index=st.index)
    comp["all_play"] = rank_scale(st.ap_pct)
    comp["pf"] = rank_scale(st.pf_pg)
    comp["record"] = rank_scale(st.win_pct + st.PF / 1e6)
    comp["recent"] = rank_scale(recent.reindex(st.index))
    comp["roster"] = (rank_scale(ws.reindex(st.index)) + rank_scale(eff.reindex(st.index))) / 2
    weights = dict(WEIGHTS_EARLY if W <= 3 else WEIGHTS_LATE)
    if hist.empty:
        weights.pop("history")
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}
    else:
        comp["history"] = (rank_scale(hist.turnaround.reindex(st.index))
                           + rank_scale(hist.waiver_share.reindex(st.index))) / 2

    score = sum(comp[k] * w for k, w in weights.items()) * 100
    out = pd.DataFrame({"owner_id": st.index, "score": score.values}).set_index("owner_id")
    out["rank"] = out.score.rank(ascending=False, method="min").astype(int)
    out["label"] = [ident.label(o, year) for o in out.index]
    out["record"] = [record_str(st.loc[o]) for o in out.index]
    out["pf_pg"] = st.pf_pg
    out["ap_record"] = [f"{int(st.loc[o].ap_w)}-{int(st.loc[o].ap_l)}" for o in out.index]
    out["driver"] = [DRIVERS[max(weights, key=lambda k: (comp.loc[o, k], weights[k]))] for o in out.index]
    for k in weights:
        out[f"c_{k}"] = comp[k]
    out.attrs["weights"] = weights
    out.attrs["week"] = W

    if with_movement and W > 1:
        prev = power_rankings(seasons, year, W - 1, ident, with_movement=False)
        out["prev_rank"] = prev["rank"].reindex(out.index)
        out["movement"] = out.prev_rank - out["rank"]
    else:
        out["prev_rank"] = pd.NA
        out["movement"] = pd.NA
    return out.sort_values(["rank", "score"], ascending=[True, False])


def movement_str(m) -> str:
    if pd.isna(m):
        return "new"
    m = int(m)
    return "—" if m == 0 else (f"▲{m}" if m > 0 else f"▼{-m}")


def power_markdown(df: pd.DataFrame, season: Season) -> str:
    W = df.attrs["week"]
    rows = [{
        "#": r["rank"], "Move": movement_str(r.movement), "Team (Owner)": r.label, "Score": r.score,
        "Record": r.record, "PF/G": r.pf_pg, "All-play": r.ap_record, "Why": r.driver,
    } for _, r in df.iterrows()]
    weights = ", ".join(f"{COMPONENT_NAMES[k]} {int(v * 100)}%" for k, v in df.attrs["weights"].items())
    return "\n".join([
        f"## Power Rankings: {season.year}, through week {W}",
        "",
        table(rows),
        "",
        f"_Weights: {weights}. Each component is rank-scaled across the league._",
    ])
