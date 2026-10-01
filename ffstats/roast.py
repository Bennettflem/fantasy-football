from __future__ import annotations

import pandas as pd

from .core import default_week, eligible_slots, lineup_efficiency, weekly_scores
from .data import Season
from .identity import Identity
from .power import _norm, assign_reasons
from .render import table

# One roast per owner, one owner per category (cap=1), so nobody gets the same joke.
ROASTS = {
    "low": ("Low score of the week with {pts:.1f}. Somebody has to be last.",),
    "sat_star": ("Had {player} and his {pts:.1f} points on the bench. The highest score of the week, watching from a chair.",),
    "goose": ("Started {player}, who scored zero. An actual zero, in a starting slot.",),
    "benched": ("Benched {bench} ({bpts:.1f}) and started {starter} ({spts:.1f}) instead. A {gap:.1f} point decision.",),
    "kicker": ("Their kicker ({k}, {kpts:.1f}) outscored their quarterback ({qb}, {qbpts:.1f}).",),
    "bench_points": ("Left {b:.1f} points on the bench. That's a whole other team over there.",),
    "blowout_loss": ("Lost by {m:.1f} to {opp}. Not a game so much as a public service announcement.",),
    "close_loss": ("Lost by {m:.1f}. One more catch, one fewer kneel-down, any of it.",),
    "lost_to_low": ("Lost to {opp}, who scored {opp_pts:.1f}. One of the worst scores of the week beat them.",),
    "under_proj": ("Projected for {proj:.1f}, scored {actual:.1f}. Missed by {diff:.1f}.",),
    "failed_waiver": ("Missed on {player} at the waiver wire. Someone wanted him more.",),
    "won_ugly": ("Won with {pts:.1f}, the kind of score that usually loses. Take it and don't look back.",),
}
ROAST_FALLBACKS = [
    "Suspiciously clean week. Nothing to work with here.",
    "No disasters to report, which is its own kind of boring.",
    "Got away with one this week.",
    "Quietly did nothing wrong. Weird.",
    "Nothing incriminating in the box score. Yet.",
    "A perfectly adequate week by a perfectly adequate manager.",
    "Survived the week without embarrassing themselves.",
    "No notes. Deeply unsatisfying.",
    "Managed to avoid the spotlight entirely.",
    "Clean week. Enjoy it while it lasts.",
]


def _owner_of(ident: Identity, year: int, team_id) -> str:
    return ident.team_owner.get((year, int(team_id)), "")


def roast_pool(season: Season, ident: Identity, W: int, wk: pd.DataFrame,
               l: pd.DataFrame, eff: pd.DataFrame) -> dict[str, list[tuple]]:
    year = season.year
    pool: dict[str, list[tuple]] = {}
    lo_cut = wk.points.quantile(.34) if len(wk) else 0
    low_id = wk.loc[wk.points.idxmin()].owner_id if len(wk) else None
    star = l.loc[l.points.idxmax()] if not l.empty else None

    for _, r in wk.iterrows():
        oid = r.owner_id
        cands: list[tuple] = []

        def add(key: str, strength: float, **fields):
            cands.append((round(float(strength), 4), key, fields))

        if oid == low_id:
            add("low", 1.0, pts=r.points)
        if r.result == "L":
            if r.margin <= -40:
                add("blowout_loss", .50 + .20 * _norm(-r.margin, 40, 90), m=-r.margin, opp=ident.short(r.opp_owner_id))
            elif r.margin >= -3:
                add("close_loss", .45, m=-r.margin)
            if r.opp_points <= lo_cut:
                add("lost_to_low", .50, opp=ident.short(r.opp_owner_id), opp_pts=r.opp_points)
        elif r.result == "W" and r.points <= lo_cut:
            add("won_ugly", .30, pts=r.points)

        mine = l[l.team_id == ident.owner_team_id.get((year, oid), -1)] if not l.empty else l
        if len(mine):
            starters, bench = mine[mine.started], mine[mine.lineup_slot == "BE"]
            if star is not None and _owner_of(ident, year, star.team_id) == oid and not star.started:
                add("sat_star", .75, player=star.player, pts=star.points)
            zeros = starters[starters.points == 0]
            if len(zeros):
                add("goose", .60, player=zeros.iloc[0].player)
            gap, best = 0.0, None
            for _, b in bench.iterrows():
                elig = starters[starters.lineup_slot.isin(eligible_slots(b.position))]
                if elig.empty:
                    continue
                worst = elig.loc[elig.points.idxmin()]
                if float(b.points - worst.points) > gap:
                    gap, best = float(b.points - worst.points), (b, worst)
            if best and gap >= 8:
                b, worst = best
                add("benched", .50 + .30 * _norm(gap, 8, 40), bench=b.player, bpts=b.points,
                    starter=worst.player, spts=worst.points, gap=gap)
            ks, qbs = starters[starters.position == "K"], starters[starters.position == "QB"]
            if len(ks) and len(qbs):
                k, qb = ks.loc[ks.points.idxmax()], qbs.loc[qbs.points.idxmax()]
                if k.points > qb.points:
                    add("kicker", .55, k=k.player, kpts=k.points, qb=qb.player, qbpts=qb.points)
            proj = float(starters.projected_points.sum())
            actual = float(starters.points.sum())
            if proj > 0 and proj - actual >= 20:
                add("under_proj", .40 + .20 * _norm(proj - actual, 20, 60), proj=proj, actual=actual,
                    diff=proj - actual)

        e = eff[eff.owner_id == oid]
        if len(e) and float(e.bench.iloc[0]) >= 50:
            add("bench_points", .40 + .20 * _norm(float(e.bench.iloc[0]), 50, 130), b=float(e.bench.iloc[0]))

        tx = season.transactions
        if not tx.empty and "nfl_week" in tx.columns and "to_team" in tx.columns:
            failed = tx[tx.status.astype(str).str.startswith("FAILED") & (tx.item_type == "ADD")
                        & (pd.to_numeric(tx.nfl_week, errors="coerce") == W)]
            for _, f in failed.iterrows():
                if ident.owner_of_team_name(year, f.to_team) == oid or ident.owner_of_team_name(year, f.initiating_team) == oid:
                    add("failed_waiver", .35, player=f.player)
                    break
        pool[oid] = cands
    return pool


def roast(seasons: dict[int, Season], year: int, week: int | None = None,
          ident: Identity | None = None) -> list[dict]:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week, regular_only=False)
    scores = weekly_scores(season, ident, through_week=W, regular_only=False)
    wk = scores[scores.week == W]
    if wk.empty:
        raise ValueError(f"No final matchups for {year} week {W}.")
    l = season.lineups[season.lineups.matchup_period == W] if not season.lineups.empty else season.lineups
    eff = lineup_efficiency(season, ident, W, regular_only=False)
    eff = eff[eff.week == W]

    pool = roast_pool(season, ident, W, wk, l, eff)
    order = list(wk.sort_values("points", ascending=False).owner_id)
    picked = assign_reasons(pool, order, cap=1, phrasings=ROASTS, fallbacks=ROAST_FALLBACKS)
    out = []
    for oid in order:
        key, line = picked[oid]
        row = wk[wk.owner_id == oid].iloc[0]
        out.append({"owner_id": oid, "label": ident.label(oid, year), "key": key, "line": line,
                    "points": float(row.points), "result": row.result})
    return out


def roast_markdown(items: list[dict], season: Season, week: int) -> str:
    rows = [{"Owner": i["label"], "Week": f"{i['points']:.1f} ({i['result']})", "Roast": i["line"]} for i in items]
    return "\n".join([f"## Week {week} Roast: {season.year}", "", table(rows), "",
                      "_Everyone gets exactly one, and no two people get the same category._"])
