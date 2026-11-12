"""Eye-test rankings: how a football person would rank these teams.

The power rankings are a measurement. This is an argument. `power.py` leans hardest on
all-play - a stat that asks what would have happened against nine opponents you never
played - and on last week. That makes it accurate and makes it read like a spreadsheet.

This ranks the way NFL power rankings do. Wins come first. The players on the roster come
second, because a football person looks at who you can trot out next week, not at what you
averaged in September. Beating good teams counts more than beating bad ones. A defense that
shows up counts. And a team that cannot be trusted to clear 100 does not get to be ranked
highly on the strength of its average.

Nothing here uses all-play, expected wins, luck or lineup efficiency. That omission is the
whole point: every number in this table is one a league-mate would say out loud.
"""

from __future__ import annotations

import pandas as pd

from .core import (default_week, optimal_lineup, rank_scale, record_str, standings,
                   weekly_scores)
from .data import Season, slot_structure
from .identity import Identity
from .render import table

# Wins lead, because this is the eye test and the eye test starts with the record. Talent is
# next and weighted nearly as heavily - it is the one input here that describes the team you
# would face next week rather than the one that played in September.
WEIGHTS = {"record": .30, "talent": .25, "quality": .15, "defense": .10, "floor": .10,
           "momentum": .10}

# Three weeks of results is not a record, so early on the roster carries the argument.
WEIGHTS_EARLY = {"record": .20, "talent": .35, "quality": .10, "defense": .10, "floor": .10,
                 "momentum": .15}

COMPONENT_NAMES = {"record": "Record", "talent": "Roster talent", "quality": "Quality of wins",
                   "defense": "Defense", "floor": "Floor", "momentum": "Momentum"}

MOMENTUM_WEEKS = 3
FLOOR_WEEKS = 2       # how many bad weeks define a team's floor
STUD_RANK = 12        # position rank that counts as a genuine starter-quality player

# One line per component, for whichever one is carrying a team or sinking it. The eye test is
# an argument, so these are phrased as claims rather than as readings off a dial. The first
# phrasing in each list claims a superlative, so it is only ever handed to the team that
# actually leads (or trails) that component; everyone else takes a later one, which also keeps
# two teams from reading alike.
STRENGTH = {
    "record": ["Best record in the league at {rec}",
               "The record is the argument: {rec}",
               "Wins on the board, {rec}, and that is the case"],
    "talent": ["Most talent on hand - {talent:.0f} points of starters, {studs} of them top-{sr}",
               "{talent:.0f} points of startable talent, {studs} top-{sr} players",
               "A roster you would take into a playoff game - {studs} top-{sr} players"],
    "quality": ["Has beaten the good teams, not just the bad ones",
                "Every win on the resume came against someone real",
                "No padding on this record"],
    "defense": ["Best D/ST in the league at {dst:.1f} a week",
                "The defense travels: {dst:.1f} a week from the D/ST slot",
                "Gets real points out of the D/ST slot, {dst:.1f} a week"],
    "floor": ["Highest floor in the league - bad weeks still average {floor:.0f}",
              "Never gets blown out; worst weeks still average {floor:.0f}",
              "Even the bad days are {floor:.0f}-point days"],
    "momentum": ["Playing the best football in the league right now",
                 "Hot, and it does not look accidental",
                 "Winning the games in front of them lately"],
}
WEAKNESS = {
    "record": ["Worst record in the league at {rec}",
               "The record says what it says: {rec}",
               "{rec}, and the standings are not lying about it"],
    "talent": ["Thinnest roster in the league - {talent:.0f} points of startable talent",
               "Only {talent:.0f} points of startable talent, {studs} top-{sr} players",
               "Not enough on this roster to win with"],
    "quality": ["Hasn't beaten anybody who matters",
                "The wins are all against the bottom of the league",
                "No scalp on this resume"],
    "defense": ["Worst D/ST in the league: {dst:.1f} a week",
                "Gets nothing from the D/ST slot, {dst:.1f} a week",
                "The defense is a wasted roster spot ({dst:.1f} a week)"],
    "floor": ["No floor at all - bad weeks average {floor:.0f}",
              "Bottoms out hard; worst weeks average {floor:.0f}",
              "Can't be trusted on a bad day ({floor:.0f})"],
    "momentum": ["Playing the worst football in the league right now",
                 "Has lost the thread over the last {mw} weeks",
                 "Going backwards, and has been for weeks"],
}


def roster_talent(season: Season, ident: Identity) -> pd.DataFrame:
    """The best lineup each team could start next week, valued at each player's season average.

    Reads the roster snapshot rather than the weekly lineups on purpose: the eye test asks who
    is on the team *now*, so a trade or a waiver claim counts immediately and a player who was
    dropped in week 3 counts for nobody. IR is excluded the same way `optimal_lineup` excludes
    it - you cannot start those players.
    """
    r = season.rosters
    cols = ["owner_id", "talent", "studs", "best_player", "best_avg"]
    if r.empty:
        return pd.DataFrame(columns=cols).set_index("owner_id")
    slots = slot_structure(season)
    rows = []
    for tid, g in r.groupby("team_id"):
        oid = ident.team_owner.get((season.year, int(tid)), "")
        if not oid:
            continue
        players = [{"position": p.position, "points": float(p.avg_points or 0.0),
                    "lineup_slot": p.lineup_slot, "player": p.player}
                   for p in g.itertuples()]
        total, chosen = optimal_lineup(players, slots)
        studs = int((pd.to_numeric(g.position_rank, errors="coerce") <= STUD_RANK).sum())
        top = max(chosen, key=lambda p: p["points"]) if chosen else {"player": "", "points": 0.0}
        rows.append({"owner_id": oid, "talent": total, "studs": studs,
                     "best_player": top["player"], "best_avg": top["points"]})
    return pd.DataFrame(rows).set_index("owner_id")


def defense_points(season: Season, ident: Identity, through_week: int | None = None) -> pd.Series:
    """Points per week from the started D/ST slot. The one real defense in fantasy football."""
    l = season.lineups
    if l.empty:
        return pd.Series(dtype=float)
    d = l[(l.lineup_slot == "D/ST") & l.started & (l.matchup_period <= season.reg_weeks)]
    if through_week is not None:
        d = d[d.matchup_period <= through_week]
    if d.empty:
        return pd.Series(dtype=float)
    d = d.assign(owner_id=[ident.team_owner.get((season.year, int(t)), "") for t in d.team_id])
    return d.groupby("owner_id").points.mean()


def floor_score(scores: pd.DataFrame, weeks: int = FLOOR_WEEKS) -> pd.Series:
    """What a team looks like on a bad day: the mean of its worst `weeks` scores.

    A single disaster is bad luck; two of them is a floor. This is the eye test's stand-in for
    a defense that keeps you in games - it asks whether a team can be trusted when nothing
    goes right, which an average cannot tell you.
    """
    return scores.groupby("owner_id").points.apply(lambda s: s.nsmallest(min(weeks, len(s))).mean())


def quality_wins(scores: pd.DataFrame, st: pd.DataFrame) -> pd.Series:
    """Credit for each win, sized by how good the team you beat turned out to be.

    Beating a 6-2 team is worth more than beating a 2-6 team, and the sum - not the average -
    is what counts, so padding a record against the bottom of the league still earns less than
    a thinner record built on real opponents.
    """
    wins = scores[scores.result == "W"]
    if wins.empty:
        return pd.Series(0.0, index=st.index)
    wp = st.win_pct
    credit = wins.assign(q=wins.opp_owner_id.map(wp).fillna(0.5)).groupby("owner_id").q.sum()
    return credit.reindex(st.index).fillna(0.0)


def momentum(scores: pd.DataFrame, through_week: int, weeks: int = MOMENTUM_WEEKS) -> pd.Series:
    """Win rate over the last few weeks - results only, not scoring.

    Deliberately blunt. A football person says "they've won three straight", not "their
    all-play has trended up", so this counts wins and nothing else.
    """
    recent = scores[scores.week > through_week - weeks]
    if recent.empty:
        return pd.Series(dtype=float)
    return recent.groupby("owner_id").result.apply(lambda s: (s == "W").mean())


def eye_test(seasons: dict[int, Season], year: int, week: int | None = None,
             ident: Identity | None = None, with_movement: bool = True) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    tal = roster_talent(season, ident)
    dst = defense_points(season, ident, W)

    raw = pd.DataFrame(index=st.index)
    raw["rec_pct"] = st.win_pct
    raw["talent"] = tal.talent.reindex(st.index)
    raw["quality"] = quality_wins(scores, st)
    raw["dst"] = dst.reindex(st.index)
    raw["floor"] = floor_score(scores).reindex(st.index)
    raw["mom"] = momentum(scores, W).reindex(st.index)
    raw["studs"] = tal.studs.reindex(st.index)
    raw["best_player"] = tal.best_player.reindex(st.index)
    raw["best_avg"] = tal.best_avg.reindex(st.index)

    comp = pd.DataFrame(index=st.index)
    # Record is tiebroken on total points so two teams at the same win rate are not held level
    # by a component worth 30%.
    comp["record"] = rank_scale(raw.rec_pct + st.PF / 1e6)
    comp["talent"] = rank_scale(raw.talent)
    comp["quality"] = rank_scale(raw.quality)
    comp["defense"] = rank_scale(raw.dst)
    comp["floor"] = rank_scale(raw.floor)
    comp["momentum"] = rank_scale(raw.mom)

    weights = dict(WEIGHTS_EARLY if W <= 3 else WEIGHTS)
    score = sum(comp[k] * w for k, w in weights.items()) * 100

    out = pd.DataFrame({"score": score}, index=st.index)
    out["rank"] = (out.score + raw.talent.fillna(0) / 1e6).rank(ascending=False,
                                                                method="first").astype(int)
    out["label"] = [ident.label(o, year) for o in out.index]
    out["record"] = [record_str(st.loc[o]) for o in out.index]
    out["pf_pg"] = st.pf_pg
    for c in raw.columns:
        out[c] = raw[c]
    for k in weights:
        out[f"c_{k}"] = comp[k]
    out.attrs["weights"] = weights
    out.attrs["week"] = W

    if with_movement and W > 1:
        prev = eye_test(seasons, year, W - 1, ident, with_movement=False)
        out["prev_rank"] = prev["rank"].reindex(out.index)
        out["movement"] = out.prev_rank - out["rank"]
    else:
        out["prev_rank"] = pd.NA
        out["movement"] = pd.NA

    out = out.sort_values(["rank", "score"], ascending=[True, False])
    leaders = {k: str(comp[k].idxmax()) for k in comp}
    trailers = {k: str(comp[k].idxmin()) for k in comp}
    used: dict[str, int] = {}
    keys, whys = [], []
    for oid, r in out.iterrows():
        c = comp.loc[oid]
        # Top half gets credited for what carries it, bottom half gets charged for what sinks
        # it. Either way the line names a component and quotes its number, so the claim is
        # checkable against the table.
        top_half = int(r["rank"]) <= len(out) / 2
        key = str(c.idxmax() if top_half else c.idxmin())
        bank = (STRENGTH if top_half else WEAKNESS)[key]
        extreme = (leaders if top_half else trailers)[key] == oid
        # Hand out the superlative phrasing only to the team that genuinely owns the component;
        # everyone else starts at the first non-superlative line and walks down the list.
        i = used.get(key, 0) if extreme else max(1, used.get(key, 1))
        used[key] = min(i + 1, len(bank) - 1)
        keys.append(key)
        whys.append(bank[min(i, len(bank) - 1)].format(
            rec=r.record, talent=r.talent or 0, studs=int(r.studs or 0), sr=STUD_RANK,
            dst=r.dst or 0, floor=r.floor or 0, mw=MOMENTUM_WEEKS))
    out["why_key"] = keys
    out["why"] = whys
    return out


def eye_test_markdown(df: pd.DataFrame, season: Season) -> str:
    from .power import movement_str
    W = df.attrs["week"]
    rows = [{"#": r["rank"], "Move": movement_str(r.movement), "Team (Owner)": r.label,
             "Score": round(r.score, 1), "Record": r.record, "Talent": r.talent,
             "D/ST": r.dst, "Floor": r.floor, "Why": r.why} for _, r in df.iterrows()]
    w = df.attrs["weights"]
    return "\n".join([
        f"## Eye-Test Rankings: {season.year}, through week {W}", "",
        table(rows), "",
        "_Weights: " + ", ".join(f"{COMPONENT_NAMES[k]} {v:.0%}" for k, v in w.items()) + "._",
        "",
        f"_Talent = best startable lineup from today's roster, valued at season averages. "
        f"Floor = mean of a team's {FLOOR_WEEKS} worst weeks. No all-play, no luck, no "
        f"expected wins._",
    ])
