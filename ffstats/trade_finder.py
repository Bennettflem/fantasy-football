from __future__ import annotations

import pandas as pd

from .data import Season, slot_structure
from .identity import Identity
from .render import bullets, table

BASE_SLOTS = {"QB", "RB", "WR", "TE", "K", "D/ST"}
UNAVAILABLE = {"OUT", "INJURY_RESERVE", "SUSPENSION"}
MIN_GAIN = 0.8      # fantasy points per game; below this it isn't worth a text message
MAX_UNFAIR = 3.0    # per-game value gap before one side is just getting fleeced


def starting_counts(season: Season) -> dict[str, int]:
    """How many of each base position a team starts, counting flex slots toward RB/WR/TE."""
    slots = slot_structure(season)
    counts = {p: int(slots.get(p, 0)) for p in BASE_SLOTS}
    flex = sum(n for s, n in slots.items() if s not in BASE_SLOTS and s not in ("BE", "IR"))
    for p in ("RB", "WR"):  # flex almost always ends up an RB or WR
        counts[p] = counts.get(p, 0) + flex / 2
    return counts


def roster_values(season: Season, ident: Identity) -> pd.DataFrame:
    """One row per rostered player with per-game value and whether they're a starter-quality piece."""
    r = season.rosters
    if r.empty:
        return pd.DataFrame(columns=["owner_id", "player", "position", "avg_points", "rank_on_team"])
    df = r.assign(
        owner_id=[ident.team_owner.get((season.year, int(t)), "") for t in r.team_id],
        avg_points=pd.to_numeric(r.avg_points, errors="coerce").fillna(0.0),
        injury_status=r.injury_status.fillna("") if "injury_status" in r.columns else "",
    )
    df = df[df.position.isin(BASE_SLOTS)]
    df["rank_on_team"] = df.groupby(["owner_id", "position"]).avg_points.rank(ascending=False, method="first")
    return df


def team_needs(values: pd.DataFrame, counts: dict[str, int]) -> pd.DataFrame:
    """Per owner and position: starter strength, the league gap, and the best spare player."""
    rows = []
    league = {p: g.avg_points.mean() for p, g in values.groupby("position")}
    for (oid, pos), g in values.groupby(["owner_id", "position"]):
        need = max(1, round(counts.get(pos, 1)))
        starters = g[g.rank_on_team <= need]
        spares = g[(g.rank_on_team > need) & (~g.injury_status.isin(UNAVAILABLE))]
        rows.append({
            "owner_id": oid, "position": pos,
            "starter_avg": float(starters.avg_points.mean()) if len(starters) else 0.0,
            "worst_starter": float(starters.avg_points.min()) if len(starters) else 0.0,
            "worst_starter_name": starters.loc[starters.avg_points.idxmin()].player if len(starters) else "",
            "best_spare": float(spares.avg_points.max()) if len(spares) else 0.0,
            "best_spare_name": spares.loc[spares.avg_points.idxmax()].player if len(spares) else "",
            "league_avg": float(league.get(pos, 0.0)),
        })
    df = pd.DataFrame(rows)
    df["surplus"] = df.best_spare - df.worst_starter
    return df


def find_trades(needs: pd.DataFrame, min_gain: float = MIN_GAIN, max_unfair: float = MAX_UNFAIR) -> pd.DataFrame:
    """Two-player swaps where each side upgrades a starting spot from the other's bench."""
    deals = []
    owners = sorted(needs.owner_id.unique())
    for i, a in enumerate(owners):
        for b in owners[i + 1:]:
            na, nb = needs[needs.owner_id == a], needs[needs.owner_id == b]
            for _, give in na.iterrows():            # a sends a spare at give.position
                if not give.best_spare_name:
                    continue
                want_b = nb[nb.position == give.position]
                if want_b.empty:
                    continue
                gain_b = float(want_b.iloc[0].worst_starter)
                gain_b = give.best_spare - gain_b
                if gain_b < min_gain:
                    continue
                for _, get in nb.iterrows():         # b sends a spare at get.position
                    if not get.best_spare_name or get.position == give.position:
                        continue
                    want_a = na[na.position == get.position]
                    if want_a.empty:
                        continue
                    gain_a = get.best_spare - float(want_a.iloc[0].worst_starter)
                    if gain_a < min_gain or abs(give.best_spare - get.best_spare) > max_unfair:
                        continue
                    deals.append({
                        "a": a, "b": b,
                        "a_sends": give.best_spare_name, "a_sends_pos": give.position, "a_sends_avg": give.best_spare,
                        "b_sends": get.best_spare_name, "b_sends_pos": get.position, "b_sends_avg": get.best_spare,
                        "a_upgrades": want_a.iloc[0].worst_starter_name, "a_gain": gain_a,
                        "b_upgrades": want_b.iloc[0].worst_starter_name, "b_gain": gain_b,
                        "fairness": abs(give.best_spare - get.best_spare),
                        "score": min(gain_a, gain_b),
                    })
    df = pd.DataFrame(deals)
    if df.empty:
        return df
    # One offer per pair of owners; the same two managers don't need five variations of the same idea.
    df = df.sort_values(["score", "fairness"], ascending=[False, True])
    return df.drop_duplicates(subset=["a", "b"], keep="first")


def trade_finder(seasons: dict[int, Season], year: int, ident: Identity | None = None,
                 top: int = 10) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    season = seasons[year]
    values = roster_values(season, ident)
    if values.empty:
        raise ValueError(f"No roster snapshot for {year}.")
    needs = team_needs(values, starting_counts(season))
    deals = find_trades(needs)
    deals.attrs["snapshot"] = str(season.rosters.snapshot_date.iloc[0]) if "snapshot_date" in season.rosters.columns and len(season.rosters) else ""
    deals.attrs["needs"] = needs
    return deals.head(top) if len(deals) else deals


def trade_finder_markdown(deals: pd.DataFrame, season: Season, ident: Identity) -> str:
    head = f"## Trade Finder: {season.year}"
    if deals.empty:
        return head + "\n\n_No two-for-one-position swaps clear the fairness and upgrade bar right now._"
    rows = [{
        "Deal": f"{ident.short(d.a)} ⇄ {ident.short(d.b)}",
        "First sends": f"{d.a_sends} ({d.a_sends_pos}, {d.a_sends_avg:.1f}/g)",
        "Second sends": f"{d.b_sends} ({d.b_sends_pos}, {d.b_sends_avg:.1f}/g)",
        "First gains": f"+{d.a_gain:.1f}/g over {d.a_upgrades}",
        "Second gains": f"+{d.b_gain:.1f}/g over {d.b_upgrades}",
    } for _, d in deals.iterrows()]
    notes = [
        f"{ident.short(d.a)} sends {d.a_sends} and gets {d.b_sends}: "
        f"{ident.short(d.a)} upgrades {d.a_upgrades} by {d.a_gain:.1f}/g, "
        f"{ident.short(d.b)} upgrades {d.b_upgrades} by {d.b_gain:.1f}/g"
        for _, d in deals.iterrows()
    ]
    snap = deals.attrs.get("snapshot", "")
    return "\n".join([
        head, "", table(rows), "", "### In plain terms", "", bullets(notes), "",
        f"_Based on season-to-date points per game from the roster snapshot{' ' + snap if snap else ''}. "
        f"Each deal sends a bench player who would start for the other team, both sides gain at least "
        f"{MIN_GAIN}/g, and the two players are within {MAX_UNFAIR}/g of each other. Injured and IR players "
        "are never offered._",
    ])
