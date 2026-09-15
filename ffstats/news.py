from __future__ import annotations

from datetime import datetime

import pandas as pd

from .core import default_week, standings, streaks, weekly_scores
from .data import Season
from .identity import Identity
from .power import power_rankings
from .render import bullets

INJURED = {"OUT", "INJURY_RESERVE", "DOUBTFUL", "SUSPENSION"}


def league_news(seasons: dict[int, Season], year: int, week: int | None = None,
                ident: Identity | None = None) -> list[tuple[str, list[str]]]:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    sections: list[tuple[str, list[str]]] = []
    name = lambda o: ident.name(o) if o else "?"
    owner_of = lambda team: ident.owner_of_team_name(year, team)

    tx = season.transactions
    recent = tx[pd.to_numeric(tx.nfl_week, errors="coerce") >= W] if not tx.empty and "nfl_week" in tx.columns else pd.DataFrame()

    trades: list[str] = []
    if not recent.empty:
        for tid, g in recent[recent.transaction_type.str.startswith("TRADE", na=False)].groupby("transaction_id"):
            items = g[g.item_type == "TRADE"]
            if items.empty:
                continue
            ttype, status = g.transaction_type.iloc[0], str(g.status.iloc[0])
            if ttype == "TRADE_PROPOSAL" and status == "CANCELED":
                continue
            legs = []
            for from_team, gg in items.groupby("from_team"):
                to_team = gg.to_team.iloc[0]
                legs.append(f"{name(owner_of(from_team))} sends {', '.join(gg.player)} to {name(owner_of(to_team))}")
            label = {"TRADE_ACCEPT": "Trade completed", "TRADE_PROPOSAL": f"Trade proposed ({status.lower()})",
                     "TRADE_VETO": "Trade VETOED", "TRADE_DECLINE": "Trade declined",
                     "TRADE_UPHOLD": "Trade upheld after review"}.get(ttype, ttype)
            trades.append(f"{label}: " + "; ".join(legs))
    sections.append(("Trades", trades))

    moves: list[str] = []
    if not recent.empty:
        adds = recent[(recent.status == "EXECUTED") & recent.transaction_type.isin(["WAIVER", "FREEAGENT"])]
        notable = _notable_players(season)
        for tid, g in adds.groupby("transaction_id", sort=False):
            owner = name(owner_of(g.to_team.iloc[0]) or owner_of(g.from_team.iloc[0]))
            added = [p for p, t in zip(g.player, g.item_type) if t == "ADD"]
            dropped = [p for p, t in zip(g.player, g.item_type) if t == "DROP"]
            if not added and not dropped:
                continue
            line = f"{owner}"
            if added:
                line += f" adds {', '.join(added)}"
            if dropped:
                flag = [p + (" (!)" if p in notable else "") for p in dropped]
                line += (", drops " if added else " drops ") + ", ".join(flag)
            bid = g.faab_bid.iloc[0]
            if pd.notna(bid) and float(bid) > 0:
                line += f" (${int(bid)} FAAB)"
            moves.append(line)
        failed = recent[recent.status.astype(str).str.startswith("FAILED") & (recent.item_type == "ADD")]
        for _, f in failed.iterrows():
            moves.append(f"{name(owner_of(f.to_team) or owner_of(f.initiating_team))} missed on {f.player} (claim failed)")
    sections.append(("Waiver wire and free agency", moves))

    if year == max(seasons):
        r = season.rosters
        hurt = r[r.injury_status.isin(INJURED)] if not r.empty else r
        inj = [f"{name(ident.team_owner.get((year, int(x.team_id)), ''))}: {x.player} ({x.position}) is {str(x.injury_status).replace('_', ' ').title()}"
               for _, x in hurt.sort_values(["team_id", "position"]).iterrows()]
        sections.append(("Injury report (current rosters)", inj))

    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    hot: list[str] = []
    for oid, g in scores.sort_values("week").groupby("owner_id"):
        s = streaks(g.result)
        if s["current_len"] >= 3:
            verb = "won" if s["current_type"] == "W" else "lost"
            hot.append(f"{ident.label(oid, year)} has {verb} {s['current_len']} straight")
    sections.append(("Streaks", hot))

    standing_lines: list[str] = []
    if W > 1:
        prev = standings(weekly_scores(season, ident, through_week=W - 1))
        for oid in st.index:
            d = int(prev.loc[oid, "rank"]) - int(st.loc[oid, "rank"]) if oid in prev.index else 0
            if abs(d) >= 2:
                standing_lines.append(f"{ident.label(oid, year)} {'climbs' if d > 0 else 'drops'} {abs(d)} spots to #{int(st.loc[oid, 'rank'])}")
    leader = st.sort_values("rank").index[0]
    standing_lines.insert(0, f"{ident.label(leader, year)} leads the league at {int(st.loc[leader, 'W'])}-{int(st.loc[leader, 'L'])}")
    sections.append(("Standings", standing_lines))

    t = season.teams
    if "playoff_pct_espn_sim" in t.columns and (t.playoff_pct_espn_sim > 0).any():
        top = t.sort_values("playoff_pct_espn_sim", ascending=False)
        po = [f"{ident.label(ident.team_owner.get((year, int(x.team_id)), ''), year)}: {x.playoff_pct_espn_sim:.0f}%" for _, x in top.iterrows()]
        sections.append(("Playoff odds (ESPN simulation)", po))

    misc: list[str] = []
    deadline = str(season.settings.get("trade_deadline", "none"))
    if deadline and deadline != "none":
        try:
            dl = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
            days = (dl - datetime.now()).days
            if days >= 0:
                misc.append(f"{days} days until the trade deadline ({dl:%b %d})")
        except ValueError:
            pass
    weeks_left = season.reg_weeks - W
    if weeks_left > 0:
        misc.append(f"{weeks_left} regular-season week{'s' if weeks_left != 1 else ''} left; top {season.playoff_teams} make the playoffs")
    sections.append(("Calendar", misc))

    upcoming: list[str] = []
    nxt = season.matchups[(season.matchups.matchup_period == W + 1) & (season.matchups.status == "not_final")]
    if len(nxt):
        pr = power_rankings(seasons, year, W, ident, with_movement=False)
        games = []
        for _, m in nxt.iterrows():
            h = ident.team_owner.get((year, int(m.home_team_id)), "")
            a = ident.team_owner.get((year, int(m.away_team_id)), "") if str(m.away_team_id) != "BYE" else ""
            if not a:
                continue
            combined = float(pr.score.get(h, 0) + pr.score.get(a, 0))
            rec = lambda o: f"{int(st.loc[o, 'W'])}-{int(st.loc[o, 'L'])}" if o in st.index else "0-0"
            games.append((combined, f"{ident.label(h, year)} ({rec(h)}) vs {ident.label(a, year)} ({rec(a)})"))
        games.sort(reverse=True)
        if games:
            upcoming.append(f"Game of the Week: {games[0][1]}")
            if len(games) > 1:
                upcoming.append(f"Beer Mile Bowl: {games[-1][1]}")
            upcoming += [f"{g[1]}" for g in games[1:-1]]
    sections.append((f"Week {W + 1} preview", upcoming))
    return sections


def _notable_players(season: Season) -> set[str]:
    notable: set[str] = set()
    d = season.draft
    if not d.empty:
        notable |= set(d[d["round"] <= 6].player)
    l = season.lineups
    if not l.empty:
        avg = l[l.points != 0].groupby("player").points.mean()
        notable |= set(avg[avg >= 8].index)
    return notable


def news_markdown(sections: list[tuple[str, list[str]]], season: Season, week: int) -> str:
    out = [f"## League News: {season.year}, after week {week}", ""]
    for title, items in sections:
        if items:
            out += [f"### {title}", bullets(items), ""]
    return "\n".join(out).rstrip()
