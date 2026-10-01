from __future__ import annotations

import pandas as pd

from .data import Season
from .identity import Identity
from .render import bullets, table
from .trade_finder import starting_counts

GRADES = [(1.25, "A+"), (.75, "A"), (.25, "B"), (-.25, "C"), (-.75, "D")]
# Graded on a curve: one great draft shouldn't drag everyone else's z-score down with it.
CURVE = [(.10, "A+"), (.30, "A"), (.55, "B"), (.80, "C"), (.95, "D")]


def letter(z: float) -> str:
    for cut, g in GRADES:
        if z >= cut:
            return g
    return "F"


def curve_grade(rank: int, n: int) -> str:
    """Grade by finishing position within the draft class, 1 = best."""
    p = (rank - 1) / max(n - 1, 1)
    for cut, g in CURVE:
        if p <= cut:
            return g
    return "F"


def replacement_levels(picks: pd.DataFrame, counts: dict[str, float], team_count: int) -> dict[str, float]:
    """Points of a freely-available player at each position: the last one who'd start league-wide.

    A 12th-best QB in a 10-team league is replaceable; the 12th-best RB is not. Grading on raw
    points rewards whoever drafted the most quarterbacks, so every pick is scored against this.
    """
    levels = {}
    for pos, g in picks.groupby("position"):
        starters = max(1, int(round(team_count * counts.get(pos, 1))))
        vals = g.pts.sort_values(ascending=False).tolist()
        window = vals[starters - 1:starters + 2] or vals[-1:]
        levels[pos] = float(sum(window) / len(window)) if window else 0.0
    return levels


def season_grades(season: Season, ident: Identity) -> dict:
    d = season.draft
    if d.empty or "player_season_points" not in d.columns:
        return {}
    picks = d.assign(
        pts=pd.to_numeric(d.player_season_points, errors="coerce").fillna(0.0),
        owner_id=[ident.team_owner.get((season.year, int(t)), "") for t in d.team_id],
    )
    levels = replacement_levels(picks, starting_counts(season), season.team_count)
    picks["replacement"] = picks.position.map(levels).fillna(0.0)
    picks["vor"] = picks.pts - picks.replacement

    by_owner = picks.groupby("owner_id").vor.sum()
    mean, sd = float(by_owner.mean()), float(by_owner.std(ddof=0)) or 1.0
    rows = []
    n = len(by_owner)
    for rank, (oid, total) in enumerate(by_owner.sort_values(ascending=False).items(), start=1):
        mine = picks[picks.owner_id == oid]
        best = mine.loc[mine.vor.idxmax()]
        early = mine[mine["round"] <= 5]
        worst = early.loc[early.vor.idxmin()] if len(early) else mine.loc[mine.vor.idxmin()]
        rows.append({
            "owner_id": oid, "vor": float(total), "points": float(mine.pts.sum()), "rank": rank,
            "z": (float(total) - mean) / sd, "grade": curve_grade(rank, n),
            "best": f"{best.player} ({best.position}, rd {int(best['round'])}, {best.vor:+.0f} VOR)",
            "worst": f"{worst.player} ({worst.position}, rd {int(worst['round'])}, {worst.vor:+.0f} VOR)",
        })
    redraft = picks.sort_values("pts", ascending=False).head(10)
    return {"year": season.year, "complete": season.is_complete, "rows": rows,
            "levels": levels, "redraft": redraft, "picks": picks}


def draft_grades(seasons: dict[int, Season], year: int | None = None,
                 ident: Identity | None = None) -> list[dict]:
    ident = ident or Identity(seasons)
    years = [year] if year else sorted(seasons)
    out = [season_grades(seasons[y], ident) for y in years]
    return [o for o in out if o]


def draft_grades_markdown(reports: list[dict], ident: Identity) -> str:
    if not reports:
        return "## Draft Grades\n\n_(no draft data)_"
    parts = ["# Draft Grades (value over replacement)"]
    career: dict[str, list[float]] = {}
    for rep in reports:
        tag = "" if rep["complete"] else " (season in progress)"
        rows = [{"Grade": r["grade"], "Owner": ident.label(r["owner_id"], rep["year"]),
                 "VOR": f"{r['vor']:+.0f}", "Drafted points": f"{r['points']:.0f}",
                 "Best pick": r["best"], "Worst early pick": r["worst"]} for r in rep["rows"]]
        for r in rep["rows"]:
            career.setdefault(r["owner_id"], []).append(r["z"])
        redraft = [f"{i}. {p.player} ({p.position}, {p.pts:.0f} pts) — actually went "
                   f"round {int(p['round'])} pick {int(p.round_pick)} to {ident.short(p.owner_id)}"
                   for i, (_, p) in enumerate(rep["redraft"].iterrows(), start=1)]
        levels = ", ".join(f"{p} {v:.0f}" for p, v in sorted(rep["levels"].items()))
        parts += [f"## {rep['year']}{tag}", "", table(rows), "",
                  "### The 10 best players drafted that year", "", bullets(redraft), "",
                  f"_Replacement level by position: {levels}._"]
    if len(reports) > 1:
        ranked = sorted(career.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
        rows = [{"Grade": curve_grade(i, len(ranked)), "Owner": ident.label(o),
                 "Avg z-score": f"{sum(z) / len(z):+.2f}", "Drafts": len(z)}
                for i, (o, z) in enumerate(ranked, start=1)]
        parts += ["## All-time drafting", "", table(rows)]
    parts += ["", "_VOR = a pick's season points minus what a replacement-level player at that position "
              "returned, so drafting a quarterback early is not automatically rewarded. Grades are "
              "z-scores of total VOR within each draft._"]
    return "\n".join(parts)
