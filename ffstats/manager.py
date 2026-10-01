from __future__ import annotations

import pandas as pd

from .core import (default_week, lineup_efficiency, optimal_lineup, pickups, rank_scale,
                   standings, weekly_scores)
from .data import Season, slot_structure
from .draft_grades import replacement_levels
from .identity import Identity
from .render import bullets, table
from .trade_finder import starting_counts
from .trades import infer_trades

WEIGHTS = {"draft": .25, "lineup": .25, "waivers": .20, "trades": .15, "efficiency": .10, "hygiene": .05}
COMPONENT_NAMES = {
    "draft": "Draft (VOR, injury-adjusted)", "lineup": "Start/sit process", "waivers": "Waivers and drops",
    "trades": "Trades", "efficiency": "Lineup outcome", "hygiene": "Roster hygiene",
}
SURPRISE_PROJ = 5.0       # a no-show projected for this much was a late scratch, not a bad decision
KNOWN_OUT_PROJ = 1.0      # ESPN projects ~0 for players it knows are inactive
TRADE_FULL_SWING = 80.0   # net points that move the trade component from neutral to an extreme
TRADE_MIN_WEEKS = 1       # a trade needs at least one week of scoring on the new rosters
TRADE_FULL_WEEKS = 4      # ...and four weeks before that verdict counts at full weight


def played(l: pd.DataFrame) -> pd.Series:
    """Did the player actually take the field?

    ESPN's weekly injury_status is a snapshot from export time, so it can't answer this. An empty
    stat_breakdown can: it is empty for players who didn't play and never empty for one who scored.
    """
    if "stat_breakdown" not in l.columns:
        return pd.Series(True, index=l.index)
    sb = l.stat_breakdown.astype(str).str.strip()
    return ~sb.isin(["{}", "", "nan", "None", "null"])


def absences(season: Season, through_week: int) -> pd.DataFrame:
    """Player-weeks where someone didn't play, split into foreseeable and genuinely unlucky."""
    l = season.lineups
    if l.empty:
        return pd.DataFrame(columns=["player_id", "matchup_period", "projected_points", "unexpected", "started"])
    l = l[l.matchup_period <= through_week]
    miss = l[~played(l)].copy()
    miss["unexpected"] = miss.projected_points >= SURPRISE_PROJ
    return miss


def draft_component(season: Season, ident: Identity, W: int) -> tuple[pd.Series, pd.DataFrame]:
    """Value over replacement, crediting picks for points lost to unforeseeable absences."""
    d = season.draft
    if d.empty or "player_season_points" not in d.columns:
        return pd.Series(dtype=float), pd.DataFrame()
    miss = absences(season, W)
    credit = miss[miss.unexpected].groupby("player_id").projected_points.sum() if len(miss) else pd.Series(dtype=float)
    picks = d.assign(
        owner_id=[ident.team_owner.get((season.year, int(t)), "") for t in d.team_id],
        raw=pd.to_numeric(d.player_season_points, errors="coerce").fillna(0.0))
    picks["credit"] = picks.player_id.map(credit).fillna(0.0)
    picks["pts"] = picks.raw + picks.credit
    levels = replacement_levels(picks, starting_counts(season), season.team_count)
    picks["vor"] = picks.pts - picks.position.map(levels).fillna(0.0)
    return picks.groupby("owner_id").vor.sum(), picks


def lineup_component(season: Season, ident: Identity, W: int) -> pd.DataFrame:
    """Grade the decision, not the result: how close the lineup was to the best *projected* one."""
    l = season.lineups
    cols = ["owner_id", "process", "proj_lost", "unforced"]
    if l.empty:
        return pd.DataFrame(columns=cols)
    slots = slot_structure(season)
    rows = []
    for (week, tid), g in l[l.matchup_period <= W].groupby(["matchup_period", "team_id"]):
        players = g[["position", "points", "projected_points", "lineup_slot", "player"]].to_dict("records")
        by_proj = [{**p, "points": p["projected_points"]} for p in players]
        best_proj, _ = optimal_lineup(by_proj, slots)
        started = g[g.started]
        chosen_proj = float(started.projected_points.sum())
        rows.append({
            "owner_id": ident.team_owner.get((season.year, int(tid)), ""),
            "process": round(chosen_proj / best_proj, 6) if best_proj else 1.0,
            # The same thing in points, because "99.7%" hides how much was actually given away.
            "proj_lost": round(max(best_proj - chosen_proj, 0.0), 2),
            # Starting someone ESPN already projected at zero is an unforced error, not bad luck.
            "unforced": int((started.projected_points < KNOWN_OUT_PROJ).sum()),
        })
    df = pd.DataFrame(rows)
    return df.groupby("owner_id").agg(process=("process", "mean"), proj_lost=("proj_lost", "sum"),
                                      unforced=("unforced", "sum")).reset_index()


def waiver_component(season: Season, ident: Identity, W: int) -> pd.DataFrame:
    """Points gained from the wire, minus the points dropped players went on to score elsewhere."""
    pk = pickups(season, ident, W)
    wire = pk[pk.via.isin(["WAIVER", "FREEAGENT"])] if not pk.empty else pk
    gained = wire.groupby("owner_id").points_after.sum() if len(wire) else pd.Series(dtype=float)
    moves = wire.groupby("owner_id").size() if len(wire) else pd.Series(dtype=int)

    regret: dict[str, float] = {}
    failed: dict[str, int] = {}
    tx, l = season.transactions, season.lineups
    if not tx.empty and "item_type" in tx.columns and not l.empty:
        drops = tx[(tx.item_type == "DROP") & (tx.status == "EXECUTED")]
        for _, r in drops.iterrows():
            oid = ident.owner_of_team_name(season.year, r.from_team)
            if not oid:
                continue
            tid = ident.owner_team_id.get((season.year, oid))
            wk = int(pd.to_numeric(pd.Series([r.nfl_week]), errors="coerce").fillna(0).iloc[0])
            later = l[(l.player_id == r.player_id) & (l.matchup_period > wk) & (l.matchup_period <= W)
                      & (l.team_id != tid) & l.started]
            regret[oid] = regret.get(oid, 0.0) + float(later.points.sum())
        bad = tx[tx.status.astype(str).str.startswith("FAILED") & (tx.item_type == "ADD")]
        for _, r in bad.iterrows():
            oid = ident.owner_of_team_name(season.year, r.to_team) or ident.owner_of_team_name(season.year, r.initiating_team)
            if oid:
                failed[oid] = failed.get(oid, 0) + 1

    owners = set(gained.index) | set(regret) | set(failed)
    return pd.DataFrame([{"owner_id": o, "wire_points": float(gained.get(o, 0.0)),
                          "drop_regret": float(regret.get(o, 0.0)), "failed_claims": int(failed.get(o, 0)),
                          "pickups": int(moves.get(o, 0)),
                          "wire_net": float(gained.get(o, 0.0)) - float(regret.get(o, 0.0))}
                         for o in sorted(owners)])


def _started_points(l: pd.DataFrame, player_ids, team_id, after_week: int, W: int) -> float:
    g = l[l.player_id.isin(list(player_ids)) & (l.matchup_period > after_week) & (l.matchup_period <= W)
          & (l.team_id == team_id) & l.started]
    return float(g.points.sum())


def trade_component(season: Season, ident: Identity, W: int) -> pd.DataFrame:
    """Net starting points a trade produced for each side.

    Deliberately not shrunk by sample size: trades are rare and risky, so one that works (or blows
    up) should move the needle. A trade is graded only once a week has passed and the players
    involved have actually recorded a score for their new team.
    """
    cols = ["owner_id", "trade_net", "trade_weighted", "trades_graded", "trade_weeks"]
    l = season.lineups
    if l.empty:
        return pd.DataFrame(columns=cols)
    legs = infer_trades(season, ident, W)   # ESPN's log loses trades; roster movement doesn't
    if legs.empty:
        return pd.DataFrame(columns=cols)
    net: dict[str, float] = {}
    weighted: dict[str, float] = {}
    graded: dict[str, int] = {}
    weeks_seen: dict[str, int] = {}
    for _, g in legs.groupby("trade_id"):
        eff = int(g.week.min())             # first week the players showed up on their new rosters
        weeks = W - eff + 1                 # weeks of scoring on the new rosters, including that one
        if weeks < TRADE_MIN_WEEKS:
            continue
        # One week is real evidence, just thin evidence. Ramp to full weight over a month.
        confidence = min(weeks / TRADE_FULL_WEEKS, 1.0)
        moved = l[l.player_id.isin(g.player_id.tolist()) & (l.matchup_period >= eff) & (l.matchup_period <= W)]
        if moved.empty or not played(moved).any():
            continue  # nobody has recorded a score on their new squad yet
        for oid in set(g.from_owner) | set(g.to_owner):
            tid = ident.owner_team_id.get((season.year, oid))
            if tid is None:
                continue
            got = _started_points(l, g[g.to_owner == oid].player_id, tid, eff - 1, W)
            gave = 0.0
            for _, leg in g[g.from_owner == oid].iterrows():
                new_tid = ident.owner_team_id.get((season.year, leg.to_owner), -1)
                gave += _started_points(l, [leg.player_id], new_tid, eff - 1, W)
            net[oid] = net.get(oid, 0.0) + got - gave
            weighted[oid] = weighted.get(oid, 0.0) + (got - gave) * confidence
            graded[oid] = graded.get(oid, 0) + 1
            weeks_seen[oid] = max(weeks_seen.get(oid, 0), weeks)
    return pd.DataFrame([{"owner_id": o, "trade_net": v, "trade_weighted": weighted.get(o, 0.0),
                          "trades_graded": graded.get(o, 0), "trade_weeks": weeks_seen.get(o, 0)}
                         for o, v in net.items()], columns=cols)


def hygiene_component(season: Season, ident: Identity, W: int, failed: dict[str, int]) -> pd.DataFrame:
    """Dead weight on the bench and waiver claims that failed."""
    l = season.lineups
    rot: dict[str, float] = {}
    if not l.empty:
        wk = l[l.matchup_period <= W]
        dead = wk[(~wk.started) & (wk.projected_points < KNOWN_OUT_PROJ) & (~played(wk))]
        for tid, g in dead.groupby("team_id"):
            oid = ident.team_owner.get((season.year, int(tid)), "")
            if oid:
                rot[oid] = len(g) / max(W, 1)
    owners = set(rot) | set(failed)
    return pd.DataFrame([{"owner_id": o, "roster_rot": float(rot.get(o, 0.0)),
                          "failed_claims": int(failed.get(o, 0))} for o in sorted(owners)])


def manager_score(seasons: dict[int, Season], year: int, week: int | None = None,
                  ident: Identity | None = None) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    st = standings(weekly_scores(season, ident, through_week=W))
    owners = list(st.index)
    idx = pd.Index(owners, name="owner_id")

    vor, _ = draft_component(season, ident, W)
    lineup = lineup_component(season, ident, W).set_index("owner_id").reindex(idx)
    wire = waiver_component(season, ident, W).set_index("owner_id").reindex(idx).fillna(0.0)
    trades = trade_component(season, ident, W).set_index("owner_id").reindex(idx).fillna(0.0)
    eff = lineup_efficiency(season, ident, W).groupby("owner_id").efficiency.mean().reindex(idx)
    hyg = hygiene_component(season, ident, W, wire.failed_claims.to_dict()).set_index("owner_id").reindex(idx).fillna(0.0)

    comp = pd.DataFrame(index=idx)
    comp["draft"] = rank_scale(vor.reindex(idx))
    comp["lineup"] = rank_scale(lineup.process)
    comp["waivers"] = rank_scale(wire.wire_net)
    comp["efficiency"] = rank_scale(eff)
    comp["hygiene"] = rank_scale(-(hyg.roster_rot + hyg.failed_claims))
    # Absolute, not ranked: an owner who hasn't traded sits neutral instead of being punished for it.
    # The weighted figure already discounts trades that have only had a week or two to prove out.
    comp["trades"] = (0.5 + (trades.trade_weighted / TRADE_FULL_SWING).clip(-0.5, 0.5)).fillna(0.5)

    out = pd.DataFrame(index=idx)
    out["score"] = sum(comp[k] * w for k, w in WEIGHTS.items()) * 100
    out["rank"] = out.score.rank(ascending=False, method="min").astype(int)
    out["label"] = [ident.label(o, year) for o in owners]
    out["draft_vor"] = vor.reindex(idx)
    out["process"] = lineup.process
    out["proj_lost"] = lineup.proj_lost
    out["unforced"] = lineup.unforced.fillna(0).astype(int)
    out["wire_net"] = wire.wire_net
    out["drop_regret"] = wire.drop_regret
    out["trade_net"] = trades.trade_net
    out["trade_weighted"] = trades.trade_weighted
    out["trade_weeks"] = trades.trade_weeks.astype(int)
    out["trades_graded"] = trades.trades_graded.astype(int)
    out["efficiency"] = eff
    out["luck"] = st.luck.reindex(idx)
    for k in WEIGHTS:
        out[f"c_{k}"] = comp[k]
    out.attrs["week"] = W
    out.attrs["weights"] = WEIGHTS
    return out.sort_values("score", ascending=False)


def career_manager_score(seasons: dict[int, Season], ident: Identity | None = None) -> pd.DataFrame:
    """Manager score across every season, weighted by weeks played.

    Each season is scored on its own (so a component always means "best in the league that year"),
    then the component scores are averaged with weeks played as the weight. A two-week season
    therefore counts for two weeks, not for a third of someone's career.
    """
    ident = ident or Identity(seasons)
    per: dict[int, pd.DataFrame] = {}
    for year in sorted(seasons):
        try:
            per[year] = manager_score(seasons, year, None, ident)
        except ValueError:
            continue  # no completed weeks yet
    if not per:
        raise ValueError("No completed weeks in any season.")

    owners = sorted({o for df in per.values() for o in df.index}, key=lambda o: ident.name(o))
    rows = []
    for oid in owners:
        comps = {k: 0.0 for k in WEIGHTS}
        totals = {"draft_vor": 0.0, "wire_net": 0.0, "trade_net": 0.0, "proj_lost": 0.0,
                  "unforced": 0, "luck": 0.0, "trades_graded": 0}
        weeks = 0.0
        process = 0.0
        years = []
        for year, df in per.items():
            if oid not in df.index:
                continue
            r, w = df.loc[oid], float(df.attrs["week"])
            for k in WEIGHTS:
                comps[k] += float(r[f"c_{k}"]) * w
            for key in ("draft_vor", "wire_net", "trade_net", "proj_lost", "luck"):
                if pd.notna(r[key]):
                    totals[key] += float(r[key])
            totals["unforced"] += int(r.unforced)
            totals["trades_graded"] += int(r.trades_graded)
            process += float(r.process) * w if pd.notna(r.process) else 0.0
            weeks += w
            years.append(year)
        if not weeks:
            continue
        scaled = {k: v / weeks for k, v in comps.items()}
        rows.append({"owner_id": oid, "label": ident.label(oid),
                     "score": sum(scaled[k] * w for k, w in WEIGHTS.items()) * 100,
                     "seasons": len(years), "weeks": int(weeks), "process": process / weeks,
                     **totals, **{f"c_{k}": v for k, v in scaled.items()}})

    out = pd.DataFrame(rows).set_index("owner_id").sort_values("score", ascending=False)
    out["rank"] = range(1, len(out) + 1)
    out.attrs["years"] = sorted(per)
    out.attrs["weights"] = WEIGHTS
    out.attrs["weeks"] = {y: int(df.attrs["week"]) for y, df in per.items()}
    return out


def career_manager_score_markdown(df: pd.DataFrame) -> str:
    span = ", ".join(f"{y} ({w}w)" for y, w in df.attrs["weeks"].items())
    rows = [{
        "#": int(r["rank"]), "Manager": r.label, "Score": f"{r.score:.1f}",
        "Draft VOR": f"{r.draft_vor:+.0f}", "Start/sit": f"{100 * r.process:.1f}%",
        "Proj lost": f"{r.proj_lost:.0f}", "Wire net": f"{r.wire_net:+.0f}",
        "Trades": f"{r.trade_net:+.0f} ({int(r.trades_graded)})" if int(r.trades_graded) else "—",
        "Unforced": int(r.unforced), "Luck": f"{r.luck:+.1f}",
    } for _, r in df.iterrows()]
    weights = ", ".join(f"{COMPONENT_NAMES[k]} {int(v * 100)}%" for k, v in df.attrs["weights"].items())
    return "\n".join([
        f"## Manager Score: all time ({span})", "", table(rows), "",
        f"_Weights: {weights}. Each season is scored on its own, then averaged with weeks played as "
        "the weight, so a partial season counts for what it is. Raw columns are career totals. "
        "Luck is reported, never scored._",
    ])


def _trade_cell(r) -> str:
    """Net points, how many trades, and how much of it is counted yet."""
    if not int(r.trades_graded):
        return "—"
    weeks = int(r.trade_weeks)
    cell = f"{r.trade_net:+.0f} ({int(r.trades_graded)})"
    return cell if weeks >= TRADE_FULL_WEEKS else f"{cell} @{weeks / TRADE_FULL_WEEKS:.0%}"


def manager_score_markdown(df: pd.DataFrame, season: Season) -> str:
    W = df.attrs["week"]
    rows = [{
        "#": int(r["rank"]), "Manager": r.label, "Score": f"{r.score:.1f}",
        "Draft VOR": f"{r.draft_vor:+.0f}" if pd.notna(r.draft_vor) else "",
        "Start/sit": f"{100 * r.process:.1f}%" if pd.notna(r.process) else "",
        "Proj lost": f"{r.proj_lost:.0f}" if pd.notna(r.proj_lost) else "",
        "Wire net": f"{r.wire_net:+.0f}",
        "Trades": _trade_cell(r),
        "Unforced": int(r.unforced), "Luck": f"{r.luck:+.1f}",
    } for _, r in df.iterrows()]
    weights = ", ".join(f"{COMPONENT_NAMES[k]} {int(v * 100)}%" for k, v in df.attrs["weights"].items())
    notes = [
        "**Start/sit** grades the decision, not the result: the projected points of the lineup you "
        "started, over the best lineup you could have started by projection. Being right for the "
        "wrong reason doesn't count, and neither does a bust you couldn't have seen.",
        "**Draft VOR** credits picks for points lost to *unforeseeable* absences - a player projected "
        f"for {SURPRISE_PROJ:.0f}+ who didn't play was a late scratch. A player ESPN already projected "
        "at zero was not, so starting him is charged as an unforced error instead.",
        "**Trades** are graded as soon as the players have a week of scoring for their new team, but "
        f"a fresh verdict is discounted: one week counts at {1 / TRADE_FULL_WEEKS:.0%} and the weight "
        f"ramps to full after {TRADE_FULL_WEEKS} weeks (the @% in the column). They are never shrunk "
        "by sample size - a trade that works moves you, one that blows up costs you - and anyone who "
        "hasn't traded sits neutral rather than penalized.",
        "**Luck** is reported, never scored. It's what happened to you, not what you did.",
    ]
    return "\n".join([
        f"## Manager Score: {season.year}, through week {W}", "", table(rows), "",
        f"_Weights: {weights}. Each component except trades is rank-scaled across the league._", "",
        "### How to read it", "", bullets(notes),
    ])
