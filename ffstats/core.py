from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .data import BENCH_SLOTS, Season, last_completed_week, slot_structure
from .identity import Identity

FLEX_ELIGIBLE = {
    "RB/WR/TE": {"RB", "WR", "TE"},
    "FLEX": {"RB", "WR", "TE"},
    "RB/WR": {"RB", "WR"},
    "WR/TE": {"WR", "TE"},
    "OP": {"QB", "RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}


def eligible_slots(position: str) -> set[str]:
    return {position} | {slot for slot, ok in FLEX_ELIGIBLE.items() if position in ok}


def weekly_scores(season: Season, ident: Identity, through_week: int | None = None,
                  regular_only: bool = True) -> pd.DataFrame:
    """One row per team per played matchup: week, owner_id, points, opponent, result, margin."""
    m = season.matchups
    if m.empty:
        return pd.DataFrame(columns=["week", "owner_id", "team_id", "team", "points", "opp_owner_id",
                                     "opp_points", "result", "margin", "game_type", "playoff_tier"])
    m = m[m.status == "final"]
    if regular_only:
        m = m[m.game_type == "regular_season"]
    if through_week is not None:
        m = m[m.matchup_period <= through_week]
    rows = []
    for _, g in m.iterrows():
        h_id, a_id = int(g.home_team_id), int(g.away_team_id)
        h_o, a_o = ident.team_owner.get((season.year, h_id), ""), ident.team_owner.get((season.year, a_id), "")
        h_pts, a_pts = float(g.home_score), float(g.away_score)
        for oid, tid, team, pts, opp_oid, opp_pts in (
            (h_o, h_id, g.home_team, h_pts, a_o, a_pts),
            (a_o, a_id, g.away_team, a_pts, h_o, h_pts),
        ):
            result = "W" if pts > opp_pts else ("L" if pts < opp_pts else "T")
            rows.append({
                "week": int(g.matchup_period), "owner_id": oid, "team_id": tid, "team": str(team).strip(),
                "points": pts, "opp_owner_id": opp_oid, "opp_points": opp_pts, "result": result,
                "margin": round(pts - opp_pts, 2), "game_type": g.game_type, "playoff_tier": g.playoff_tier,
            })
    return pd.DataFrame(rows).sort_values(["week", "owner_id"]).reset_index(drop=True)


def all_play(scores: pd.DataFrame) -> pd.DataFrame:
    """Per team per week: how many of the other teams it would have beaten."""
    rows = []
    for week, g in scores.groupby("week"):
        pts = list(g.points)
        for _, r in g.iterrows():
            w = sum(1 for p in pts if r.points > p)
            t = sum(1 for p in pts if r.points == p) - 1
            l = len(pts) - 1 - w - t
            rows.append({"week": int(week), "owner_id": r.owner_id, "ap_w": w, "ap_l": l, "ap_t": t,
                         "ap_pct": (w + 0.5 * t) / max(len(pts) - 1, 1)})
    return pd.DataFrame(rows, columns=["week", "owner_id", "ap_w", "ap_l", "ap_t", "ap_pct"])


def standings(scores: pd.DataFrame) -> pd.DataFrame:
    """Season-to-date table indexed by owner_id: record, points, all-play, luck."""
    if scores.empty:
        return pd.DataFrame()
    ap = all_play(scores)
    out = []
    for oid, g in scores.groupby("owner_id"):
        a = ap[ap.owner_id == oid]
        w, l, t = (g.result == "W").sum(), (g.result == "L").sum(), (g.result == "T").sum()
        exp_wins = float(a.ap_pct.sum())
        out.append({
            "owner_id": oid, "W": int(w), "L": int(l), "T": int(t), "games": len(g),
            "win_pct": (w + 0.5 * t) / len(g), "PF": round(g.points.sum(), 2), "PA": round(g.opp_points.sum(), 2),
            "pf_pg": g.points.mean(), "pa_pg": g.opp_points.mean(),
            "ap_w": int(a.ap_w.sum()), "ap_l": int(a.ap_l.sum()), "ap_t": int(a.ap_t.sum()),
            "ap_pct": float(a.ap_pct.mean()), "exp_wins": exp_wins, "luck": float(w + 0.5 * t - exp_wins),
        })
    df = pd.DataFrame(out).set_index("owner_id")
    df["rank"] = df.sort_values(["win_pct", "PF"], ascending=False).reset_index().reset_index().set_index("owner_id")["index"] + 1
    return df


def record_str(row) -> str:
    rec = f"{int(row['W'])}-{int(row['L'])}"
    return rec + (f"-{int(row['T'])}" if int(row.get("T", 0)) else "")


def optimal_lineup(players: list[dict], slots: dict[str, int]) -> tuple[float, list[dict]]:
    """Greedy best lineup. players: dicts with position, points, lineup_slot (IR excluded)."""
    pool = sorted((p for p in players if p.get("lineup_slot") != "IR"), key=lambda p: -p["points"])
    chosen: list[dict] = []
    used: set[int] = set()

    def take(eligible: set[str], count: int, slot: str):
        n = 0
        for i, p in enumerate(pool):
            if n >= count:
                break
            if i not in used and p["position"] in eligible:
                used.add(i)
                chosen.append({**p, "optimal_slot": slot})
                n += 1

    for slot, count in slots.items():
        if slot not in FLEX_ELIGIBLE:
            take({slot}, count, slot)
    for slot, count in sorted(((s, c) for s, c in slots.items() if s in FLEX_ELIGIBLE),
                              key=lambda sc: len(FLEX_ELIGIBLE[sc[0]])):
        take(FLEX_ELIGIBLE[slot], count, slot)
    return round(sum(p["points"] for p in chosen), 2), chosen


def lineup_efficiency(season: Season, ident: Identity, through_week: int | None = None,
                      regular_only: bool = True) -> pd.DataFrame:
    """Per team-week: started points, optimal points, bench points, efficiency."""
    l = season.lineups
    if l.empty:
        return pd.DataFrame(columns=["week", "owner_id", "actual", "optimal", "bench", "efficiency"])
    if regular_only:
        l = l[l.matchup_period <= season.reg_weeks]
    if through_week is not None:
        l = l[l.matchup_period <= through_week]
    slots = slot_structure(season)
    rows = []
    for (week, tid), g in l.groupby(["matchup_period", "team_id"]):
        players = g[["position", "points", "lineup_slot", "player"]].to_dict("records")
        optimal, _ = optimal_lineup(players, slots)
        actual = float(g[g.started].points.sum())
        bench = float(g[g.lineup_slot == "BE"].points.sum())
        rows.append({"week": int(week), "owner_id": ident.team_owner.get((season.year, int(tid)), ""),
                     "actual": round(actual, 2), "optimal": optimal, "bench": round(bench, 2),
                     "efficiency": actual / optimal if optimal else 1.0})
    return pd.DataFrame(rows)


def streaks(results: Iterable[str]) -> dict:
    results = list(results)
    cur_type, cur_len, longest = "", 0, {"W": 0, "L": 0}
    run_type, run_len = "", 0
    for r in results:
        if r == run_type:
            run_len += 1
        else:
            run_type, run_len = r, 1
        if r in longest:
            longest[r] = max(longest[r], run_len)
    if results:
        cur_type, cur_len = run_type, run_len
    return {"current": f"{cur_type}{cur_len}" if cur_type else "", "current_type": cur_type,
            "current_len": cur_len, "longest_w": longest["W"], "longest_l": longest["L"]}


def pickups(season: Season, ident: Identity, through_week: int | None = None) -> pd.DataFrame:
    """Players acquired in-season (waiver, free agent, trade) and the points they scored as starters after."""
    tx = season.transactions
    cols = ["owner_id", "player_id", "player", "acq_week", "via", "points_after", "starts_after"]
    if tx.empty or "to_team" not in tx.columns:
        return pd.DataFrame(columns=cols)
    adds = tx[(tx.item_type == "ADD") & (tx.status == "EXECUTED") & tx.transaction_type.isin(["WAIVER", "FREEAGENT"])]
    trades = tx[(tx.item_type == "TRADE") & (tx.transaction_type == "TRADE_ACCEPT") & (tx.status == "EXECUTED")]
    acq = pd.concat([adds, trades])
    if acq.empty:
        return pd.DataFrame(columns=cols)
    acq = acq.assign(owner_id=[ident.owner_of_team_name(season.year, t) for t in acq.to_team],
                     acq_week=pd.to_numeric(acq.nfl_week, errors="coerce").fillna(0).astype(int).clip(lower=1),
                     via=acq.transaction_type.map({"TRADE_ACCEPT": "TRADE"}).fillna(acq.transaction_type))
    acq = acq.dropna(subset=["owner_id"]).sort_values("acq_week").drop_duplicates(["owner_id", "player_id"])

    limit = through_week if through_week is not None else season.reg_weeks
    l = season.lineups
    l = l[l.started & (l.matchup_period <= min(limit, season.reg_weeks))] if not l.empty else l
    rows = []
    for _, a in acq.iterrows():
        tid = ident.owner_team_id.get((season.year, a.owner_id))
        mine = l[(l.team_id == tid) & (l.player_id == a.player_id) & (l.matchup_period >= a.acq_week)] if not l.empty else l
        rows.append({"owner_id": a.owner_id, "player_id": int(a.player_id), "player": a.player,
                     "acq_week": int(a.acq_week), "via": a.via,
                     "points_after": round(float(mine.points.sum()), 2) if not mine.empty else 0.0,
                     "starts_after": int(len(mine))})
    return pd.DataFrame(rows, columns=cols)


def waiver_share(season: Season, ident: Identity, through_week: int | None = None) -> pd.Series:
    """Share of each owner's started points that came from waiver/free-agent pickups."""
    pk = pickups(season, ident, through_week)
    l = season.lineups
    limit = through_week if through_week is not None else season.reg_weeks
    l = l[l.started & (l.matchup_period <= min(limit, season.reg_weeks))] if not l.empty else l
    total = {}
    for tid, g in l.groupby("team_id"):
        total[ident.team_owner.get((season.year, int(tid)), "")] = float(g.points.sum())
    wp = pk[pk.via.isin(["WAIVER", "FREEAGENT"])].groupby("owner_id").points_after.sum() if not pk.empty else pd.Series(dtype=float)
    return pd.Series({oid: (float(wp.get(oid, 0.0)) / t if t else 0.0) for oid, t in total.items()})


def season_profile(season: Season, ident: Identity) -> pd.DataFrame:
    """Per-owner summary of one season, used for owner history and historical factors."""
    scores = weekly_scores(season, ident)
    if scores.empty:
        return pd.DataFrame()
    st = standings(scores)
    ap = all_play(scores)
    half = season.reg_weeks // 2
    ws = waiver_share(season, ident)
    eff = lineup_efficiency(season, ident)
    rows = []
    for oid in st.index:
        a = ap[ap.owner_id == oid]
        first, second = a[a.week <= half].ap_pct.mean(), a[a.week > half].ap_pct.mean()
        t = season.teams[season.teams.team_id == ident.owner_team_id.get((season.year, oid), -1)]
        e = eff[eff.owner_id == oid]
        own = scores[scores.owner_id == oid]
        rows.append({
            "owner_id": oid, "year": season.year, "team": ident.team(oid, season.year),
            **st.loc[oid].to_dict(),
            "final_standing": int(t.final_standing.iloc[0]) if len(t) else 0,
            "seed": int(t.playoff_seed_or_current_standing.iloc[0]) if len(t) else 0,
            "first_half_ap": first, "second_half_ap": second,
            "turnaround": (second - first) if pd.notna(second) and pd.notna(first) else float("nan"),
            "waiver_share": float(ws.get(oid, 0.0)),
            "efficiency": float(e.efficiency.mean()) if len(e) else float("nan"),
            "bench_points": float(e.bench.sum()) if len(e) else 0.0,
            "best_week": float(own.points.max()), "worst_week": float(own.points.min()),
            "complete": season.is_complete,
        })
    return pd.DataFrame(rows).set_index("owner_id")


def rank_scale(s: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Rank-scale to 0..1 across the league; NaN -> league median before scaling."""
    s = s.astype(float)
    if s.notna().sum() == 0:
        return pd.Series(0.5, index=s.index)
    s = s.fillna(s.median())
    r = s.rank(method="average", ascending=higher_is_better)
    n = len(s)
    return (r - 1) / (n - 1) if n > 1 else pd.Series(1.0, index=s.index)


def default_week(season: Season, week: int | None, regular_only: bool = True) -> int:
    w = week if week is not None else last_completed_week(season, regular_only)
    if w < 1:
        raise ValueError(f"No completed weeks in {season.year} yet.")
    return w
