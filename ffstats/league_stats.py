from __future__ import annotations

import pandas as pd

from .core import lineup_efficiency, pickups, standings, streaks, weekly_scores
from .data import Season
from .identity import Identity
from .power import profile
from .render import signed, table

TOPICS = ["standings", "h2h", "luck", "streaks", "records", "draft", "waivers", "lineups", "trades"]


def league_stats(seasons: dict[int, Season], ident: Identity | None = None, topic: str | None = None) -> str:
    ident = ident or Identity(seasons)
    topics = [topic] if topic else TOPICS
    if topic and topic not in TOPICS:
        raise ValueError(f"Unknown topic '{topic}'. Choose from: {', '.join(TOPICS)}")
    parts = ["# League History Stats", ""]
    for t in topics:
        parts += [globals()[f"stat_{t}"](seasons, ident), ""]
    return "\n".join(parts).rstrip()


def _all_scores(seasons, ident, regular_only=True) -> pd.DataFrame:
    frames = []
    for y, s in sorted(seasons.items()):
        sc = weekly_scores(s, ident, regular_only=regular_only)
        if not sc.empty:
            frames.append(sc.assign(year=y))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def stat_standings(seasons, ident) -> str:
    rows = []
    for oid in ident.owners():
        w = l = t = 0
        pf = pa = 0.0
        titles = lasts = playoffs = 0
        best = None
        for y, s in sorted(seasons.items()):
            p = profile(s, ident)
            if p.empty or oid not in p.index:
                continue
            r = p.loc[oid]
            w, l, t, pf, pa = w + int(r.W), l + int(r.L), t + int(r["T"]), pf + float(r.PF), pa + float(r.PA)
            if s.is_complete:
                titles += int(r.final_standing == 1)
                lasts += int(r.final_standing == s.team_count)
                playoffs += int(r.seed <= s.playoff_teams)
                best = min(best, int(r.final_standing)) if best else int(r.final_standing)
        games = w + l + t
        if not games:
            continue
        rows.append({"Owner": ident.label(oid), "W-L": f"{w}-{l}" + (f"-{t}" if t else ""),
                     "Win%": (w + 0.5 * t) / games, "PF/G": pf / games, "PA/G": pa / games,
                     "Titles": titles, "Playoffs": playoffs, "Last place": lasts, "Best finish": best or ""})
    rows.sort(key=lambda r: (-r["Win%"], -r["PF/G"]))
    for r in rows:
        r["PF/G"], r["PA/G"] = f"{r['PF/G']:.1f}", f"{r['PA/G']:.1f}"
    return "## All-time standings (regular season)\n\n" + table(rows, floatfmt="{:.3f}")


def stat_h2h(seasons, ident) -> str:
    sc = _all_scores(seasons, ident, regular_only=False)
    owners = ident.owners()
    rows = []
    for a in owners:
        row = {"Owner": ident.short(a)}
        for b in owners:
            if a == b:
                row[ident.short(b)] = "—"
                continue
            g = sc[(sc.owner_id == a) & (sc.opp_owner_id == b)]
            row[ident.short(b)] = f"{(g.result == 'W').sum()}-{(g.result == 'L').sum()}" if len(g) else "0-0"
        rows.append(row)
    return "## Head-to-head (all games incl. playoffs, row vs column)\n\n" + table(rows)


def stat_luck(seasons, ident) -> str:
    rows = []
    years = sorted(seasons)
    for oid in ident.owners():
        row, total = {"Owner": ident.label(oid)}, 0.0
        for y in years:
            p = profile(seasons[y], ident)
            v = float(p.loc[oid, "luck"]) if not p.empty and oid in p.index else None
            row[str(y)] = signed(v) if v is not None else ""
            total += v or 0
        row["Total"] = signed(total)
        row["_t"] = total
        rows.append(row)
    rows.sort(key=lambda r: -r["_t"])
    cols = [("Owner", "Owner")] + [(str(y), str(y)) for y in years] + [("Total", "Total")]
    return ("## Luck index (actual wins minus all-play expected wins; + = lucky)\n\n"
            + table(rows, cols))


def stat_streaks(seasons, ident) -> str:
    sc = _all_scores(seasons, ident, regular_only=False).sort_values(["year", "week"])
    rows = []
    for oid in ident.owners():
        s = streaks(sc[sc.owner_id == oid].result)
        rows.append({"Owner": ident.label(oid), "Longest win streak": s["longest_w"],
                     "Longest losing streak": s["longest_l"], "Current": s["current"]})
    rows.sort(key=lambda r: -r["Longest win streak"])
    return "## Streaks (all games incl. playoffs)\n\n" + table(rows)


def stat_records(seasons, ident) -> str:
    sc = _all_scores(seasons, ident, regular_only=False)
    lab = lambda r: f"{ident.name(r.owner_id)} ({r.year} wk {r.week})"
    top = [{"Owner": lab(r), "Points": r.points, "Opponent": ident.short(r.opp_owner_id), "Result": r.result}
           for _, r in sc.sort_values("points", ascending=False).head(5).iterrows()]
    low = [{"Owner": lab(r), "Points": r.points, "Opponent": ident.short(r.opp_owner_id), "Result": r.result}
           for _, r in sc.sort_values("points").head(5).iterrows()]
    wins = sc[sc.result == "W"]
    blow = [{"Winner": lab(r), "Loser": ident.short(r.opp_owner_id), "Score": f"{r.points:.2f}-{r.opp_points:.2f}", "Margin": r.margin}
            for _, r in wins.sort_values("margin", ascending=False).head(3).iterrows()]
    close = [{"Winner": lab(r), "Loser": ident.short(r.opp_owner_id), "Score": f"{r.points:.2f}-{r.opp_points:.2f}", "Margin": r.margin}
             for _, r in wins.sort_values("margin").head(3).iterrows()]
    return "\n\n".join(["## Single-week records", "### Highest scores", table(top, floatfmt="{:.2f}"),
                        "### Lowest scores", table(low, floatfmt="{:.2f}"), "### Biggest blowouts", table(blow, floatfmt="{:.2f}"),
                        "### Closest games", table(close, floatfmt="{:.2f}")])


def stat_draft(seasons, ident) -> str:
    parts = ["## Draft hindsight (season points of drafted players)"]
    drafter_ranks: dict[str, list[int]] = {}
    for y, s in sorted(seasons.items()):
        d = s.draft
        if d.empty or "player_season_points" not in d.columns:
            continue
        d = d.assign(pts=pd.to_numeric(d.player_season_points, errors="coerce").fillna(0),
                     owner_id=[ident.team_owner.get((y, int(t)), "") for t in d.team_id])
        by_owner = d.groupby("owner_id").pts.sum().sort_values(ascending=False)
        for i, oid in enumerate(by_owner.index, start=1):
            drafter_ranks.setdefault(oid, []).append(i)
        rows = [{"Owner": ident.label(o, y), "Drafted points": v} for o, v in by_owner.items()]
        steal = d[d["round"] >= 6].sort_values("pts", ascending=False).head(1)
        bust = d[d["round"] <= 3].sort_values("pts").head(1)
        tag = "" if s.is_complete else " (season in progress)"
        parts += [f"### {y}{tag}", table(rows)]
        notes = []
        if len(steal):
            r = steal.iloc[0]
            notes.append(f"- Steal: {r.player} ({r.position}) by {ident.name(r.owner_id)}, round {int(r['round'])} pick {int(r.round_pick)}, {r.pts:.1f} pts")
        if len(bust):
            r = bust.iloc[0]
            notes.append(f"- Bust: {r.player} ({r.position}) by {ident.name(r.owner_id)}, round {int(r['round'])} pick {int(r.round_pick)}, {r.pts:.1f} pts")
        if notes:
            parts.append("\n".join(notes))
    if drafter_ranks:
        rows = [{"Owner": ident.label(o), "Avg draft rank": sum(v) / len(v), "Seasons": len(v)}
                for o, v in drafter_ranks.items()]
        rows.sort(key=lambda r: r["Avg draft rank"])
        parts += ["### Best drafters (average rank of drafted points)", table(rows)]
    return "\n\n".join(parts)


def stat_waivers(seasons, ident) -> str:
    frames = []
    for y, s in sorted(seasons.items()):
        pk = pickups(s, ident)
        if not pk.empty:
            frames.append(pk.assign(year=y))
    if not frames:
        return "## Waiver wire\n\n_(no pickups)_"
    pk = pd.concat(frames, ignore_index=True)
    wire = pk[pk.via.isin(["WAIVER", "FREEAGENT"])]
    top = [{"Player": r.player, "Owner": ident.name(r.owner_id), "Year": r.year, "Picked up wk": r.acq_week,
            "Points as starter": r.points_after, "Starts": r.starts_after}
           for _, r in wire.sort_values("points_after", ascending=False).head(10).iterrows()]
    rows = []
    for oid, g in wire.groupby("owner_id"):
        best = g.loc[g.points_after.idxmax()]
        rows.append({"Owner": ident.label(oid), "Pickups": len(g), "Points from pickups": g.points_after.sum(),
                     "Best pickup": f"{best.player} ({best.year}, {best.points_after:.1f})"})
    rows.sort(key=lambda r: -r["Points from pickups"])
    return "\n\n".join(["## Waiver wire hall of fame", "### Top pickups (points scored as a starter after pickup)",
                        table(top), "### By owner", table(rows)])


def stat_lineups(seasons, ident) -> str:
    years = sorted(seasons)
    rows = []
    for oid in ident.owners():
        row, effs, bench, chw = {"Owner": ident.label(oid)}, [], 0.0, 0
        for y in years:
            s = seasons[y]
            eff = lineup_efficiency(s, ident)
            eff = eff[eff.owner_id == oid]
            if eff.empty:
                row[str(y)] = ""
                continue
            row[str(y)] = f"{100 * eff.efficiency.mean():.1f}%"
            effs.append(eff.efficiency.mean())
            bench += eff.bench.sum()
            sc = weekly_scores(s, ident)
            losses = sc[(sc.owner_id == oid) & (sc.result == "L")].merge(eff, on=["week", "owner_id"])
            chw += int((losses.optimal >= losses.opp_points).sum())
        row["All-time"] = f"{100 * sum(effs) / len(effs):.1f}%" if effs else ""
        row["Bench points"] = bench
        row["Losses a perfect lineup would have flipped"] = chw
        row["_e"] = sum(effs) / len(effs) if effs else 0
        rows.append(row)
    rows.sort(key=lambda r: -r["_e"])
    cols = [("Owner", "Owner")] + [(str(y), str(y)) for y in years] + [
        ("All-time", "All-time"), ("Bench points", "Bench points"),
        ("Losses a perfect lineup would have flipped", "Losses a perfect lineup would have flipped")]
    return "## Lineup efficiency (started points / optimal points)\n\n" + table(rows, cols)


def stat_trades(seasons, ident) -> str:
    rows = []
    for oid in ident.owners():
        done = proposed = vetoed = 0
        for y, s in sorted(seasons.items()):
            tx = s.transactions
            if tx.empty or "initiating_owner" not in tx.columns:
                continue
            team = ident.team(oid, y)
            mine = tx[(tx.initiating_team == team) | (tx.from_team == team) | (tx.to_team == team)]
            done += mine[(mine.transaction_type == "TRADE_ACCEPT") & (mine.status == "EXECUTED")].transaction_id.nunique()
            proposed += mine[(mine.transaction_type == "TRADE_PROPOSAL") & (mine.initiating_team == team)].transaction_id.nunique()
            vetoed += mine[mine.transaction_type == "TRADE_VETO"].transaction_id.nunique()
        rows.append({"Owner": ident.label(oid), "Trades completed": done, "Proposals sent": proposed, "Vetoed": vetoed})
    rows.sort(key=lambda r: (-r["Trades completed"], -r["Proposals sent"]))
    return "## Trade activity\n\n" + table(rows)
