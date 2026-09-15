from __future__ import annotations

from .core import weekly_scores
from .data import Season
from .identity import Identity
from .power import profile
from .render import pct, signed, table


def owner_history(seasons: dict[int, Season], query: str, ident: Identity | None = None) -> str:
    ident = ident or Identity(seasons)
    oid = ident.find(query)
    rows = []
    for y, s in sorted(seasons.items()):
        p = profile(s, ident)
        if p.empty or oid not in p.index:
            continue
        r = p.loc[oid]
        finish = int(r.final_standing) if s.is_complete else f"#{int(r['rank'])} so far"
        rows.append({
            "Year": y, "Team": r.team, "Record": f"{int(r.W)}-{int(r.L)}", "Finish": finish, "Seed": int(r.seed) or "",
            "PF/G": r.pf_pg, "PA/G": r.pa_pg, "All-play": f"{int(r.ap_w)}-{int(r.ap_l)}", "Luck": signed(float(r.luck)),
            "Waiver pts": pct(float(r.waiver_share)), "Lineup eff": pct(float(r.efficiency)),
            "Best wk": r.best_week, "Worst wk": r.worst_week,
        })
    h2h = []
    for other in ident.owners():
        if other == oid:
            continue
        w = l = 0
        for y, s in sorted(seasons.items()):
            sc = weekly_scores(s, ident, regular_only=False)
            g = sc[(sc.owner_id == oid) & (sc.opp_owner_id == other)]
            w, l = w + int((g.result == "W").sum()), l + int((g.result == "L").sum())
        if w + l:
            h2h.append({"Opponent": ident.label(other), "Record": f"{w}-{l}", "_w": w / (w + l)})
    h2h.sort(key=lambda r: -r["_w"])
    picks = []
    for y, s in sorted(seasons.items()):
        d = s.draft
        tid = ident.owner_team_id.get((y, oid))
        if d.empty or tid is None:
            continue
        first = d[(d.team_id == tid) & (d["round"] <= 2)].sort_values("overall_pick")
        picks.append({"Year": y, "Rounds 1-2": ", ".join(f"{p.player} ({p.player_season_points})" for _, p in first.iterrows())})
    return "\n\n".join([
        f"# {ident.name(oid)}: league history",
        "## By season", table(rows, floatfmt="{:.1f}"),
        "## Head-to-head (all games incl. playoffs)", table(h2h, [("Opponent", "Opponent"), ("Record", "Record")]),
        "## Early draft picks (season points)", table(picks),
    ])
