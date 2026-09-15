from __future__ import annotations

import pandas as pd

from .core import all_play, default_week, eligible_slots, lineup_efficiency, weekly_scores
from .data import Season
from .identity import Identity
from .render import table


def _player(p) -> str:
    return p.player if str(p.player).endswith(str(p.position)) else f"{p.player} ({p.position})"


def superlatives(seasons: dict[int, Season], year: int, week: int | None = None,
                 ident: Identity | None = None) -> list[dict]:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week, regular_only=False)
    scores = weekly_scores(season, ident, through_week=W, regular_only=False)
    wk = scores[scores.week == W]
    if wk.empty:
        raise ValueError(f"No final matchups for {year} week {W}.")
    l = season.lineups[season.lineups.matchup_period == W]
    lab = lambda oid: ident.label(oid, year)
    opp = lambda r: ident.short(r.opp_owner_id)
    awards: list[dict] = []

    def add(award, who, detail):
        awards.append({"Award": award, "Who": who, "Detail": detail})

    hi, lo = wk.loc[wk.points.idxmax()], wk.loc[wk.points.idxmin()]
    add("High score", lab(hi.owner_id), f"{hi.points:.2f} vs {opp(hi)} ({hi.result})")
    add("Beer Mile Watch (low score)", lab(lo.owner_id), f"{lo.points:.2f} vs {opp(lo)} ({lo.result})")

    winners, losers = wk[wk.result == "W"], wk[wk.result == "L"]
    if len(winners):
        b = winners.loc[winners.margin.idxmax()]
        add("Biggest blowout", lab(b.owner_id), f"beat {opp(b)} by {b.margin:.2f} ({b.points:.2f}-{b.opp_points:.2f})")
        c = winners.loc[winners.margin.idxmin()]
        add("Closest game", lab(c.owner_id), f"edged {opp(c)} by {c.margin:.2f} ({c.points:.2f}-{c.opp_points:.2f})")
        lucky = winners.loc[winners.points.idxmin()]
        add("Luckiest win", lab(lucky.owner_id), f"won with only {lucky.points:.2f}")
    if len(losers):
        unlucky = losers.loc[losers.points.idxmax()]
        add("Unluckiest loss", lab(unlucky.owner_id), f"lost despite {unlucky.points:.2f} (vs {opp(unlucky)})")

    ap = all_play(wk)
    king = ap.loc[ap.ap_w.idxmax()]
    add("All-play king", lab(king.owner_id), f"would have gone {king.ap_w}-{king.ap_l} against the league")

    eff = lineup_efficiency(season, ident, W, regular_only=False)
    eff = eff[eff.week == W]
    if len(eff):
        bb = eff.loc[eff.bench.idxmax()]
        add("Best bench", lab(bb.owner_id), f"{bb.bench:.2f} points left on the bench")

    if not l.empty:
        _lineup_awards(l, season, ident, add)
        _pickup_award(l, season, W, ident, add)
    return awards


def _lineup_awards(l: pd.DataFrame, season: Season, ident: Identity, add):
    year = season.year
    lab = lambda tid: ident.label(ident.team_owner.get((year, int(tid)), ""), year)
    best_gap, best = 0.0, None
    over, under = None, None
    for tid, g in l.groupby("team_id"):
        starters, bench = g[g.started], g[g.lineup_slot == "BE"]
        for _, b in bench.iterrows():
            cands = starters[starters.lineup_slot.isin(eligible_slots(b.position))]
            if cands.empty:
                continue
            worst = cands.loc[cands.points.idxmin()]
            gap = float(b.points - worst.points)
            if gap > best_gap:
                best_gap, best = gap, (tid, b.player, b.points, worst.player, worst.points, worst.lineup_slot)
        actual, proj = float(starters.points.sum()), float(starters.projected_points.sum())
        if proj > 0:
            diff = actual - proj
            if over is None or diff > over[1]:
                over = (tid, diff, actual, proj)
            if under is None or diff < under[1]:
                under = (tid, diff, actual, proj)
    if best:
        tid, bp, bpts, sp, spts, slot = best
        add("Worst start/sit", lab(tid), f"benched {bp} ({bpts:.1f}) behind {sp} ({spts:.1f}) at {slot}")
    if over:
        add("Overachiever (vs ESPN projection)", lab(over[0]), f"{over[2]:.2f} vs projected {over[3]:.2f} ({over[1]:+.1f})")
    if under:
        add("Underachiever (vs ESPN projection)", lab(under[0]), f"{under[2]:.2f} vs projected {under[3]:.2f} ({under[1]:+.1f})")

    starters = l[l.started]
    if len(starters):
        p = starters.loc[starters.points.idxmax()]
        add("Player of the week", _player(p), f"{p.points:.1f} for {lab(p.team_id)}")
        busts = starters[starters.projected_points >= 8].assign(diff=lambda d: d.points - d.projected_points)
        if len(busts):
            b = busts.loc[busts["diff"].idxmin()]
            add("Bust of the week", _player(b),
                f"{b.points:.1f} on a {b.projected_points:.1f} projection for {lab(b.team_id)}")


def _pickup_award(l: pd.DataFrame, season: Season, W: int, ident: Identity, add):
    tx = season.transactions
    if tx.empty or "to_team" not in tx.columns:
        return
    adds = tx[(tx.item_type == "ADD") & (tx.status == "EXECUTED")
              & tx.transaction_type.isin(["WAIVER", "FREEAGENT"]) & (tx.nfl_week == W)]
    if adds.empty:
        return
    keys = {(ident.owner_team_id.get((season.year, ident.owner_of_team_name(season.year, t))), int(p))
            for t, p in zip(adds.to_team, adds.player_id)}
    starters = l[l.started]
    mine = starters[[(int(t), int(p)) in keys for t, p in zip(starters.team_id, starters.player_id)]]
    if mine.empty:
        return
    p = mine.loc[mine.points.idxmax()]
    add("Pickup of the week", _player(p),
        f"{p.points:.1f} in first start for {ident.label(ident.team_owner.get((season.year, int(p.team_id)), ''), season.year)}")


def superlatives_markdown(awards: list[dict], season: Season, week: int) -> str:
    return "\n".join([f"## Week {week} Superlatives: {season.year}", "", table(awards)])
