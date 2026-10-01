from __future__ import annotations

import pandas as pd

from .core import default_week, weekly_scores
from .data import Season
from .identity import Identity
from .render import table


def grids(season: Season, ident: Identity, through_week: int | None = None) -> tuple[dict, dict]:
    """(points[week][owner], opponent[week][owner]) for the regular season played so far."""
    sc = weekly_scores(season, ident, through_week=through_week)
    points: dict[int, dict[str, float]] = {}
    opponents: dict[int, dict[str, str]] = {}
    for _, r in sc.iterrows():
        points.setdefault(int(r.week), {})[r.owner_id] = float(r.points)
        opponents.setdefault(int(r.week), {})[r.owner_id] = r.opp_owner_id
    return points, opponents


def record_under(points: dict, opponents: dict, me: str, host: str) -> tuple[int, int, int]:
    """My weekly scores, run against the schedule `host` actually played.

    If the host played me that week, I inherit the host as my opponent instead of playing myself.
    """
    w = l = t = 0
    for week, pts in points.items():
        opp = opponents.get(week, {}).get(host)
        if opp is None or me not in pts:
            continue
        if opp == me:
            opp = host
        if opp not in pts or opp == me:
            continue
        mine, theirs = pts[me], pts[opp]
        w, l, t = (w + 1, l, t) if mine > theirs else ((w, l + 1, t) if mine < theirs else (w, l, t + 1))
    return w, l, t


def what_if(seasons: dict[int, Season], year: int, week: int | None = None,
            ident: Identity | None = None) -> pd.DataFrame:
    """Every owner's record under every owner's schedule."""
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    points, opponents = grids(season, ident, W)
    owners = sorted({o for wk in points.values() for o in wk}, key=lambda o: ident.name(o))

    rows = []
    for me in owners:
        recs = {host: record_under(points, opponents, me, host) for host in owners}
        actual = recs[me]
        wins = {h: r[0] + 0.5 * r[2] for h, r in recs.items()}
        best, worst = max(wins, key=lambda h: wins[h]), min(wins, key=lambda h: wins[h])
        best_n = sum(1 for v in wins.values() if v == wins[best])
        worst_n = sum(1 for v in wins.values() if v == wins[worst])
        rows.append({
            "owner_id": me, "label": ident.label(me, year),
            "actual": f"{actual[0]}-{actual[1]}" + (f"-{actual[2]}" if actual[2] else ""),
            "actual_wins": wins[me], "avg_wins": sum(wins.values()) / len(wins),
            "best_wins": wins[best], "best_host": best, "best_n": best_n,
            "worst_wins": wins[worst], "worst_host": worst, "worst_n": worst_n,
            "swing": wins[best] - wins[worst],
            **{f"vs_{h}": f"{recs[h][0]}-{recs[h][1]}" for h in owners},
        })
    df = pd.DataFrame(rows).set_index("owner_id")
    df["luck"] = df.actual_wins - df.avg_wins
    df.attrs["week"] = W
    df.attrs["owners"] = owners
    return df.sort_values("luck", ascending=False)


def what_if_markdown(df: pd.DataFrame, season: Season, ident: Identity) -> str:
    W, owners = df.attrs["week"], df.attrs["owners"]
    def case(wins: float, host: str, n: int) -> str:
        # Early in a season many schedules tie; naming one of them would be arbitrary.
        return f"{wins:g} ({n} of {len(owners)} schedules)" if n > 1 else f"{wins:g} ({ident.short(host)}'s)"

    summary = [{
        "Owner": r.label, "Actual": r.actual, "Avg under all schedules": f"{r.avg_wins:.1f} wins",
        "Best case": case(r.best_wins, r.best_host, int(r.best_n)),
        "Worst case": case(r.worst_wins, r.worst_host, int(r.worst_n)),
        "Schedule luck": f"{r.luck:+.1f}",
    } for _, r in df.iterrows()]

    grid = []
    for oid in df.index:
        row = {"Owner": ident.short(oid)}
        for h in owners:
            row[ident.short(h)] = df.loc[oid, f"vs_{h}"] + (" *" if h == oid else "")
        grid.append(row)

    return "\n".join([
        f"## What If: {season.year}, through week {W}",
        "",
        "### Every owner's record under every schedule",
        "",
        table(summary),
        "",
        "### Full grid (row = owner's scores, column = whose schedule they played)",
        "",
        table(grid),
        "",
        "_Everyone keeps their own weekly scores and inherits someone else's opponents. A star marks the "
        "real schedule. Schedule luck = actual wins minus the average across all ten schedules._",
    ])
