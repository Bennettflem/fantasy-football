"""Trade history, reconstructed from roster movement.

ESPN's transaction log is not a reliable source for trades. The player legs live on the original
proposal, and ESPN purges that record once the trade resolves - the accept/veto/uphold records that
survive only point back to an id that no longer returns anything. So a completed trade can leave no
trace of who was actually swapped.

Roster movement does survive: weekly_lineups says which team every rostered player was on each week.
A player who changes teams either was added from the wire (which the transaction log does record) or
was traded. Anything unexplained by an add is a trade.
"""
from __future__ import annotations

import pandas as pd

from .data import Season
from .identity import Identity
from .render import table

LEG_COLS = ["season", "trade_id", "week", "player_id", "player", "from_owner", "to_owner", "evidence"]


def _rostered(season: Season, through_week: int | None = None) -> pd.DataFrame:
    l = season.lineups
    if l.empty:
        return pd.DataFrame(columns=["player_id", "player", "matchup_period", "team_id"])
    if through_week is not None:
        l = l[l.matchup_period <= through_week]
    return l[["player_id", "player", "matchup_period", "team_id"]].drop_duplicates(
        subset=["player_id", "matchup_period"], keep="first").sort_values(["player_id", "matchup_period"])


def _add_events(season: Season, ident: Identity) -> dict[int, set[tuple[int, int]]]:
    """player_id -> {(week, team_id)} for executed waiver and free-agent adds."""
    tx = season.transactions
    out: dict[int, set[tuple[int, int]]] = {}
    if tx.empty or "item_type" not in tx.columns:
        return out
    adds = tx[(tx.item_type == "ADD") & tx.transaction_type.isin(["WAIVER", "FREEAGENT"])]
    for _, r in adds.iterrows():
        oid = ident.owner_of_team_name(season.year, r.to_team)
        tid = ident.owner_team_id.get((season.year, oid)) if oid else None
        if tid is None:
            continue
        week = int(pd.to_numeric(pd.Series([r.nfl_week]), errors="coerce").fillna(0).iloc[0])
        out.setdefault(int(r.player_id), set()).add((week, int(tid)))
    return out


def player_moves(season: Season, ident: Identity, through_week: int | None = None) -> pd.DataFrame:
    """Every roster-to-roster move not explained by a waiver or free-agent add."""
    cols = ["player_id", "player", "from_team_id", "to_team_id", "week", "prev_week"]
    ros = _rostered(season, through_week)
    if ros.empty:
        return pd.DataFrame(columns=cols)
    adds = _add_events(season, ident)
    rows = []
    for pid, g in ros.groupby("player_id"):
        recs = list(g.itertuples())
        for prev, cur in zip(recs, recs[1:]):
            if prev.team_id == cur.team_id:
                continue
            span = range(int(prev.matchup_period), int(cur.matchup_period) + 1)
            if any((w, int(cur.team_id)) in adds.get(int(pid), set()) for w in span):
                continue  # picked up off the wire, not traded for
            rows.append({"player_id": int(pid), "player": cur.player,
                         "from_team_id": int(prev.team_id), "to_team_id": int(cur.team_id),
                         "week": int(cur.matchup_period), "prev_week": int(prev.matchup_period)})
    return pd.DataFrame(rows, columns=cols)


def logged_legs(season: Season, ident: Identity) -> dict[tuple[int, str, str], set[str]]:
    """(player_id, from_owner, to_owner) -> the transaction types ESPN recorded for that leg."""
    tx = season.transactions
    out: dict[tuple[int, str, str], set[str]] = {}
    if tx.empty or "item_type" not in tx.columns:
        return out
    legs = tx[(tx.item_type == "TRADE") & tx.transaction_type.astype(str).str.startswith("TRADE")]
    for _, r in legs.iterrows():
        a = ident.owner_of_team_name(season.year, r.from_team)
        b = ident.owner_of_team_name(season.year, r.to_team)
        if a and b:
            out.setdefault((int(r.player_id), a, b), set()).add(str(r.transaction_type))
    return out


def evidence_for(kinds: set[str]) -> str:
    """How well ESPN's own log corroborates a leg we reconstructed from roster movement."""
    if kinds & {"TRADE_ACCEPT", "TRADE_UPHOLD"}:
        return "accepted"      # ESPN recorded this exact swap as completed
    if kinds:
        return "proposal"      # only the offer survived; ESPN purged the completed record
    return "roster only"       # nothing in the log at all


def infer_trades(season: Season, ident: Identity, through_week: int | None = None) -> pd.DataFrame:
    """Trade legs grouped into trades: same week, same pair of teams, moving in both directions.

    Reciprocity is the test that makes this trustworthy. This league's transaction log is missing a
    lot of ordinary waiver activity too - players change teams with no transaction row at all - so an
    unexplained one-way move is just as likely to be an unlogged pickup as a trade. Players crossing
    between the same two rosters in the same week, in both directions, is not something the waiver
    wire produces by accident. One-way moves are kept aside in `.attrs["one_way"]`, never reported
    as trades.
    """
    moves = player_moves(season, ident, through_week)
    empty = pd.DataFrame(columns=LEG_COLS)
    if moves.empty:
        empty.attrs["one_way"] = []
        return empty
    logged = logged_legs(season, ident)
    owner = lambda tid: ident.team_owner.get((season.year, int(tid)), "")

    rows = []
    for _, m in moves.iterrows():
        a, b = owner(m.from_team_id), owner(m.to_team_id)
        if not a or not b:
            continue
        pair = "-".join(sorted([a, b]))
        rows.append({"season": season.year, "trade_id": f"{season.year}-w{m.week}-{pair}",
                     "week": int(m.week), "player_id": int(m.player_id), "player": m.player,
                     "from_owner": a, "to_owner": b,
                     "evidence": evidence_for(logged.get((int(m.player_id), a, b), set()))})
    df = pd.DataFrame(rows, columns=LEG_COLS)
    if df.empty:
        df.attrs["one_way"] = []
        return df

    two_way, one_way = [], []
    for trade_id, g in df.groupby("trade_id"):
        (two_way if g.from_owner.nunique() > 1 else one_way).append(g)
    out = pd.concat(two_way, ignore_index=True) if two_way else empty.copy()
    out.attrs["one_way"] = (pd.concat(one_way, ignore_index=True).to_dict("records") if one_way else [])
    return out.sort_values(["season", "week", "trade_id"]) if len(out) else out


def trade_history(seasons: dict[int, Season], ident: Identity | None = None) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    per_season = [infer_trades(s, ident) for s in seasons.values()]
    one_way = [m for f in per_season for m in (f.attrs.get("one_way") or [])]
    frames = [f for f in per_season if not f.empty]
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=LEG_COLS)
    out.attrs["one_way"] = one_way

    # Anything ESPN logged that roster movement did not surface (e.g. a player traded then dropped
    # before ever appearing on the new roster) would be invisible above; count it so it isn't lost.
    missed = []
    for year, s in sorted(seasons.items()):
        found = {(int(r.player_id), r.from_owner, r.to_owner) for _, r in out[out.season == year].iterrows()}
        for (pid, a, b), kinds in sorted(logged_legs(s, ident).items()):
            if (pid, a, b) not in found and evidence_for(kinds) == "accepted":
                missed.append({"season": year, "player_id": pid, "from_owner": a, "to_owner": b})
    out.attrs["logged_but_not_inferred"] = missed
    return out


def trade_history_markdown(legs: pd.DataFrame, ident: Identity) -> str:
    if legs.empty:
        return "# Trade History\n\n_No trades found in any season._"
    parts = ["# Trade History", "",
             "_Reconstructed from weekly roster movement, then kept only where players crossed "
             "between the same two rosters in both directions in the same week._", "",
             "_ESPN log: **accepted** = ESPN recorded the completed swap; **proposal** = only the "
             "offer survived, because ESPN purges the completed record; **roster only** = nothing in "
             "the log at all._", ""]
    for trade_id, g in legs.groupby("trade_id", sort=True):
        year, week = int(g.season.iloc[0]), int(g.week.iloc[0])
        sides = sorted({g.from_owner.iloc[0], g.to_owner.iloc[0]})
        a, b = sides[0], sides[1]
        parts.append(f"## {year}, first week on new rosters: week {week}")
        parts.append("")
        rows = []
        for _, r in g.sort_values(["from_owner", "player"]).iterrows():
            rows.append({"Player": r.player, "From": ident.short(r.from_owner),
                         "To": ident.short(r.to_owner), "ESPN log": r.evidence})
        parts += [table(rows), ""]
        out_a = ", ".join(g[g.from_owner == a].player) or "(nothing)"
        out_b = ", ".join(g[g.from_owner == b].player) or "(nothing)"
        parts += [f"- {ident.name(a)} sent: {out_a}", f"- {ident.name(b)} sent: {out_b}", ""]
    one_way = legs.attrs.get("one_way") or []
    if one_way:
        parts += [f"## Not counted: {len(one_way)} one-way moves", "",
                  "_These players changed rosters with no add or drop in the transaction log, but "
                  "nothing came back the other way that week. This league's log is missing a lot of "
                  "ordinary waiver activity, so these are treated as unlogged pickups, not trades._", "",
                  table([{"Season": m["season"], "Week": m["week"], "Player": m["player"],
                          "From": ident.short(m["from_owner"]), "To": ident.short(m["to_owner"])}
                         for m in sorted(one_way, key=lambda m: (m["season"], m["week"], m["player"]))]),
                  ""]
    missed = legs.attrs.get("logged_but_not_inferred") or []
    if missed:
        parts += ["## In ESPN's log but not visible in roster movement", "",
                  table([{"Season": m["season"], "Player id": m["player_id"],
                          "From": ident.short(m["from_owner"]), "To": ident.short(m["to_owner"])}
                         for m in missed]), ""]
    return "\n".join(parts).rstrip()
