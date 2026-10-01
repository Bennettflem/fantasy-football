from __future__ import annotations

import pandas as pd

from .core import (all_play, default_week, lineup_efficiency, rank_scale, record_str, season_profile,
                   standings, streaks, waiver_share, weekly_scores)
from .data import Season
from .identity import Identity
from .render import table

WEIGHTS_LATE = {"all_play": .30, "pf": .20, "record": .15, "recent": .15, "roster": .10, "history": .10}
WEIGHTS_EARLY = {"all_play": .30, "pf": .20, "record": .10, "recent": .05, "roster": .10, "history": .25}
COMPONENT_NAMES = {
    "all_play": "All-play win%", "pf": "Points/game", "record": "Record", "recent": "Last 3 weeks",
    "roster": "Roster management", "history": "Owner history",
}

# Why a team landed where it did. Each reason has two phrasings and is used by at most
# REASON_CAP teams in a week, so the rankings never read like the same sentence ten times.
REASON_CAP = 2
REASONS = {
    "juggernaut": ("Would beat almost anyone, any week ({ap} all-play)",
                   "Nobody wants to see them on the schedule ({ap} all-play)"),
    "points": ("Scoring machine, {pf:.0f} a game",
               "Just drops {pf:.0f} a week and lets the math do the rest"),
    "lucky": ("Winning games the box score says they lost ({luck:+.1f} vs expected wins)",
              "Living right: {luck:+.1f} wins above what they've actually earned"),
    "unlucky": ("Best team with a bad record ({luck:+.1f} vs expected wins)",
                "The schedule keeps mugging them ({luck:+.1f} vs expected wins)"),
    "fraud": ("Record says contender, box score says fraud ({ap} all-play)",
              "{rec} is a magic trick, not a team ({ap} all-play)"),
    "hot": ("Won {n} straight and looks the part",
            "Riding a {n}-game heater"),
    "cold": ("Lost {n} straight and it isn't bad luck",
             "{n} straight Ls and the vibes are gone"),
    "riser": ("Up {m} spots this week; someone finally woke up",
              "Climbing fast, {m} spots in a week"),
    "faller": ("Down {m} spots and still going",
               "In free fall, {m} spots this week"),
    "bench": ("Leaves {b:.0f} points on the bench every week",
              "The optimal lineup is right there, man ({e:.0%} of it started)"),
    "efficient": ("Squeezes every point out of the roster ({e:.0%} lineup efficiency)",
                  "Perfect-lineup merchant ({e:.0%} lineup efficiency)"),
    "waiver": ("Built off the wire: {w:.0%} of their points are pickups",
               "Waiver-wire gremlin, {w:.0%} of their points came from adds"),
    "pa": ("Everyone's best game comes against them ({pa:.0f} allowed a game)",
           "The league's get-right game, {pa:.0f} allowed a game"),
    "history": ("History says they turn seasons around",
                "Slow starter by trade; the back half is usually theirs"),
    # Honest off a single game, so these keep the early weeks from reading generic.
    "blowout": ("Won by {m:.0f}; that wasn't a game",
                "Beat somebody by {m:.0f} and coasted in"),
    "squeaker": ("Won by {m:.1f} and nobody's asking how",
                 "Survived by {m:.1f}"),
    "heartbreak": ("Lost by {m:.1f} and it still stings",
                   "{m:.1f} points from a completely different week"),
    "buzzsaw": ("Ran into the week's high scorer",
                "Drew the buzzsaw and paid for it"),
}
# Used only when a team qualifies for nothing above; indexed by rank so the tone fits the tier.
FALLBACKS = [
    "Best team in the league until someone proves otherwise", "Nobody has a better case right now",
    "Quietly good; nobody's talking about them", "Sneaky good, and fine with it",
    "Dead center of the league in every direction", "A coin flip with a team name",
    "Live body, bad vibes", "Needs a win before this gets away from them",
    "Rebuilding, apparently", "The beer mile is starting to make eye contact",
]


def _norm(v: float, lo: float, hi: float) -> float:
    """Clamp v into 0..1 across the lo..hi band."""
    if hi == lo:
        return 0.0
    return float(min(max((v - lo) / (hi - lo), 0.0), 1.0))


def reason_pool(st: pd.DataFrame, scores: pd.DataFrame, comp: pd.DataFrame, eff: pd.Series,
                bench: pd.Series, ws: pd.Series, movement: pd.Series,
                rank: pd.Series) -> dict[str, list[tuple]]:
    """Every reason each owner honestly qualifies for, as (strength, key, fields)."""
    pa_scale = rank_scale(st.pa_pg)
    high = scores.groupby("week").points.max() if not scores.empty else pd.Series(dtype=float)
    pool: dict[str, list[tuple]] = {}
    for oid in st.index:
        r = st.loc[oid]
        g = int(r.games)  # luck, lineup and points-against claims need more than a game or two
        ap = f"{int(r.ap_w)}-{int(r.ap_l)}"
        e, b, w = float(eff.get(oid, float("nan"))), float(bench.get(oid, 0.0)), float(ws.get(oid, 0.0))
        mv = movement.get(oid)
        mv = None if pd.isna(mv) else int(mv)
        own = scores[scores.owner_id == oid].sort_values("week")
        sk = streaks(own.result)
        cands: list[tuple] = []

        def add(key: str, strength: float, **fields):
            cands.append((round(float(strength), 4), key, fields))

        if r.ap_pct >= .65:
            add("juggernaut", .55 + .40 * _norm(r.ap_pct, .65, .95), ap=ap)
        if comp.loc[oid, "pf"] >= .78:
            add("points", .55 + .35 * comp.loc[oid, "pf"], pf=r.pf_pg)
        if g >= 3 and r.luck >= .8:
            add("lucky", .45 + .45 * _norm(r.luck, .8, 3), luck=r.luck)
        if g >= 3 and r.luck <= -.8:
            add("unlucky", .45 + .45 * _norm(-r.luck, .8, 3), luck=r.luck)
        if g >= 3 and r.win_pct >= .6 and r.ap_pct <= .45:
            add("fraud", .60 + .30 * _norm(r.win_pct - r.ap_pct, .2, .6), ap=ap, rec=record_str(r))
        if sk["current_type"] == "W" and sk["current_len"] >= 2:
            add("hot", min(.90, .50 + .10 * sk["current_len"]), n=sk["current_len"])
        if sk["current_type"] == "L" and sk["current_len"] >= 2:
            add("cold", min(.90, .50 + .10 * sk["current_len"]), n=sk["current_len"])
        if mv is not None and mv >= 2:
            add("riser", min(.85, .45 + .10 * mv), m=mv)
        if mv is not None and mv <= -2:
            add("faller", min(.85, .45 + .10 * -mv), m=-mv)
        if g >= 2 and pd.notna(e) and e <= .88:
            add("bench", .40 + .50 * _norm(.88 - e, 0, .15), b=b, e=e)
        if g >= 2 and pd.notna(e) and e >= .95:
            add("efficient", .40 + .50 * _norm(e - .95, 0, .05), e=e)
        if g >= 2 and w >= .15:
            add("waiver", .45 + .45 * _norm(w, .15, .45), w=w)
        if g >= 2 and pa_scale.get(oid, 0) >= .8:
            add("pa", .40 + .35 * pa_scale[oid], pa=r.pa_pg)
        if "history" in comp.columns and comp.loc[oid, "history"] >= .8:
            add("history", .35 + .30 * comp.loc[oid, "history"])
        if len(own):
            last = own.iloc[-1]
            m = abs(float(last.margin))
            brag = int(rank.get(oid, 1)) <= .7 * len(st)  # a bottom team's one good game isn't the story
            if last.result == "W" and m >= 25 and brag:
                add("blowout", .45 + .20 * _norm(m, 25, 60), m=m)
            elif last.result == "W" and m <= 5 and brag:
                add("squeaker", .35, m=m)
            elif last.result == "L" and m <= 5:
                add("heartbreak", .38, m=m)
            if last.result == "L" and float(last.opp_points) >= float(high.get(int(last.week), 0)) - 1e-9:
                add("buzzsaw", .42)
        pool[oid] = cands
    return pool


def assign_reasons(pool: dict[str, list[tuple]], order: list[str], cap: int = REASON_CAP,
                   phrasings: dict[str, tuple] | None = None,
                   fallbacks: list[str] | None = None) -> dict[str, tuple[str, str]]:
    """Give each owner one reason, strongest first, with at most `cap` owners per reason key.

    The nth owner to take a key gets the nth phrasing, so no two teams read alike. Owners who
    qualify for nothing (or whose reasons are used up) fall back to a rank-appropriate line.
    `phrasings` and `fallbacks` are swappable so other sections (the roast) can reuse the mechanism.
    """
    phrasings = REASONS if phrasings is None else phrasings
    fallbacks = FALLBACKS if fallbacks is None else fallbacks
    rank_of = {oid: i for i, oid in enumerate(order)}
    ranked = sorted(((s, k, oid, f) for oid, cands in pool.items() for s, k, f in cands),
                    key=lambda c: (-c[0], c[1], rank_of.get(c[2], 0)))
    used: dict[str, int] = {}
    out: dict[str, tuple[str, str]] = {}
    for strength, key, oid, fields in ranked:
        n = used.get(key, 0)
        if oid in out or n >= min(cap, len(phrasings[key])):
            continue
        out[oid] = (key, phrasings[key][n].format(**fields))
        used[key] = n + 1
    taken: set[int] = set()
    for oid in order:
        if oid in out:
            continue
        start = min(2 * (rank_of[oid] // 2), len(fallbacks) - 1)
        pick = next((i for i in list(range(start, len(fallbacks))) + list(range(start))
                     if i not in taken), None)
        if pick is None:  # more owners than fallback lines; reuse the last tier
            pick = len(fallbacks) - 1
        taken.add(pick)
        out[oid] = ("fallback", fallbacks[pick])
    return out

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
    eff_df = lineup_efficiency(season, ident, W)
    eff = eff_df.groupby("owner_id").efficiency.mean()
    bench = eff_df.groupby("owner_id").bench.mean()
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

    out = out.sort_values(["rank", "score"], ascending=[True, False])
    reasons = assign_reasons(reason_pool(st, scores, comp, eff, bench, ws, out.movement, out["rank"]),
                             list(out.index))
    out["why_key"] = [reasons[o][0] for o in out.index]
    out["why"] = [reasons[o][1] for o in out.index]
    return out


def movement_str(m) -> str:
    if pd.isna(m):
        return "new"
    m = int(m)
    return "—" if m == 0 else (f"▲{m}" if m > 0 else f"▼{-m}")


def power_markdown(df: pd.DataFrame, season: Season) -> str:
    W = df.attrs["week"]
    rows = [{
        "#": r["rank"], "Move": movement_str(r.movement), "Team (Owner)": r.label, "Score": r.score,
        "Record": r.record, "PF/G": r.pf_pg, "All-play": r.ap_record, "Why": r.why,
    } for _, r in df.iterrows()]
    weights = ", ".join(f"{COMPONENT_NAMES[k]} {int(v * 100)}%" for k, v in df.attrs["weights"].items())
    return "\n".join([
        f"## Power Rankings: {season.year}, through week {W}",
        "",
        table(rows),
        "",
        f"_Weights: {weights}. Each component is rank-scaled across the league._",
    ])
