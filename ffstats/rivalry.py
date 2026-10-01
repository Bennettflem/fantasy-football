from __future__ import annotations

import pandas as pd

from .core import default_week, standings, streaks, weekly_scores
from .data import Season, last_completed_week
from .identity import Identity
from .power import power_rankings
from .render import bullets, table


def meetings(seasons: dict[int, Season], a: str, b: str, ident: Identity) -> pd.DataFrame:
    """Every game these two have played, oldest first."""
    rows = []
    for y, s in sorted(seasons.items()):
        sc = weekly_scores(s, ident, regular_only=False)
        if sc.empty:
            continue
        mine = sc[(sc.owner_id == a) & (sc.opp_owner_id == b)]
        for _, r in mine.iterrows():
            rows.append({"year": y, "week": int(r.week), "playoff": r.game_type != "regular_season",
                         "a_score": float(r.points), "b_score": float(r.opp_points),
                         "winner": a if r.points > r.opp_points else (b if r.opp_points > r.points else ""),
                         "margin": abs(float(r.margin))})
    return pd.DataFrame(rows, columns=["year", "week", "playoff", "a_score", "b_score", "winner", "margin"])


def upcoming_game(seasons: dict[int, Season], year: int, ident: Identity,
                  week: int | None = None) -> tuple[str, str, int]:
    """The highest-profile scheduled game: best combined power score among that week's matchups."""
    season = seasons[year]
    done = last_completed_week(season)
    W = week if week is not None else done + 1
    games = season.matchups[(season.matchups.matchup_period == W) & (season.matchups.away_team != "BYE")]
    if games.empty:
        raise ValueError(f"No matchups scheduled for {year} week {W}.")
    pr = power_rankings(seasons, year, done, ident, with_movement=False) if done else None
    best, pick = None, None
    for _, g in games.iterrows():
        h = ident.team_owner.get((year, int(g.home_team_id)), "")
        a = ident.team_owner.get((year, int(g.away_team_id)), "")
        if not h or not a:
            continue
        combined = float(pr.score.get(h, 0) + pr.score.get(a, 0)) if pr is not None else 0.0
        if best is None or combined > best:
            best, pick = combined, (h, a)
    if not pick:
        raise ValueError(f"No head-to-head matchups in {year} week {W}.")
    return pick[0], pick[1], W


def rivalry(seasons: dict[int, Season], ident: Identity | None = None, name_a: str | None = None,
            name_b: str | None = None, year: int | None = None, week: int | None = None) -> dict:
    ident = ident or Identity(seasons)
    year = year or max(seasons)
    upcoming_week = None
    if name_a and name_b:
        a, b = ident.find(name_a), ident.find(name_b)
    elif name_a or name_b:
        raise ValueError("Give two names, or none to report on the next game of the week.")
    else:
        a, b, upcoming_week = upcoming_game(seasons, year, ident, week)

    games = meetings(seasons, a, b, ident)
    a_wins = int((games.winner == a).sum())
    b_wins = int((games.winner == b).sum())
    ties = int((games.winner == "").sum())
    results = ["W" if w == a else ("L" if w == b else "T") for w in games.winner]

    rep = {
        "a": a, "b": b, "year": year, "upcoming_week": upcoming_week, "games": games,
        "record": (a_wins, b_wins, ties), "streak": streaks(results),
        "a_points": float(games.a_score.sum()), "b_points": float(games.b_score.sum()),
        "playoff_games": int(games.playoff.sum()),
    }
    if len(games):
        rep["biggest"] = games.loc[games.margin.idxmax()]
        rep["closest"] = games.loc[games.margin.idxmin()]
    if upcoming_week:
        done = last_completed_week(seasons[year])
        if done:
            pr = power_rankings(seasons, year, done, ident, with_movement=False)
            st = standings(weekly_scores(seasons[year], ident, through_week=done))
            rep["form"] = {o: {"rank": int(pr.loc[o, "rank"]), "score": float(pr.loc[o, "score"]),
                               "record": f"{int(st.loc[o, 'W'])}-{int(st.loc[o, 'L'])}",
                               "pf_pg": float(st.loc[o, "pf_pg"]), "why": pr.loc[o, "why"]}
                           for o in (a, b) if o in pr.index}
    return rep


def rivalry_markdown(rep: dict, ident: Identity) -> str:
    a, b, year = rep["a"], rep["b"], rep["year"]
    A, B = ident.short(a), ident.short(b)
    aw, bw, t = rep["record"]
    games = rep["games"]
    head = f"## Rivalry: {ident.label(a, year)} vs {ident.label(b, year)}"
    if rep["upcoming_week"]:
        head += f"\n\n_Preview of {year} week {rep['upcoming_week']}._"

    if games.empty:
        return head + "\n\n_These two have never played._"

    lead = f"**{A} leads {aw}-{bw}**" if aw > bw else (f"**{B} leads {bw}-{aw}**" if bw > aw else f"**Tied {aw}-{bw}**")
    facts = [
        f"{lead}{f' with {t} tie(s)' if t else ''} across {len(games)} meeting{'s' if len(games) != 1 else ''}",
        f"Total points: {A} {rep['a_points']:.1f}, {B} {rep['b_points']:.1f} "
        f"({(rep['a_points'] - rep['b_points']) / len(games):+.1f} a game for {A})",
    ]
    sk = rep["streak"]
    if sk["current_len"]:
        who = A if sk["current_type"] == "W" else B
        facts.append(f"{who} has won the last {sk['current_len']}" if sk["current_len"] > 1 else f"{who} won the most recent meeting")
    if rep["playoff_games"]:
        facts.append(f"{rep['playoff_games']} playoff meeting(s)")
    big, close = rep.get("biggest"), rep.get("closest")
    if big is not None:
        facts.append(f"Biggest blowout: {ident.short(big.winner)} by {big.margin:.1f} "
                     f"({big.year} wk {big.week}, {max(big.a_score, big.b_score):.1f}-{min(big.a_score, big.b_score):.1f})")
    if close is not None:
        facts.append(f"Closest: {ident.short(close.winner)} by {close.margin:.1f} ({close.year} wk {close.week})")

    rows = [{"Season": int(g.year), "Week": int(g.week) if not g.playoff else f"{int(g.week)} (P)",
             A: f"{g.a_score:.1f}", B: f"{g.b_score:.1f}",
             "Winner": ident.short(g.winner) if g.winner else "tie", "Margin": f"{g.margin:.1f}"}
            for _, g in games.iterrows()]

    parts = [head, "", bullets(facts), "", "### Every meeting", "", table(rows)]
    form = rep.get("form")
    if form:
        parts += ["", "### Form", "", table([
            {"Owner": ident.label(o, year), "Power rank": f"#{f['rank']} ({f['score']:.1f})",
             "Record": f["record"], "PF/G": f"{f['pf_pg']:.1f}", "Why": f["why"]}
            for o, f in form.items()])]
    return "\n".join(parts)
