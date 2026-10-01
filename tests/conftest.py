"""A tiny synthetic league, so tests never depend on the real export (league_data/ is gitignored).

Four owners, a four-week regular season, and two seasons: one finished, one in progress with the
back half unplayed. Scores are hand-picked so every record and matchup below is deterministic.

The current season also carries the signals the manager score needs:
  - Ben starts a player projected at 0 who doesn't play  -> a foreseeable zero (unforced error)
  - Dee starts a player projected at 12 who doesn't play -> a late scratch (bad luck)
  - Ann and Ben trade in week 1; the players move teams in week 2
  - Cy adds a waiver hero in week 2; Dee drops a player who then scores for Cy
"""
from __future__ import annotations

import pandas as pd
import pytest

from ffstats.data import Season
from ffstats.identity import Identity

OWNERS = {1: ("o1", "Ann", "Adams"), 2: ("o2", "Ben", "Baker"), 3: ("o3", "Cy", "Clark"), 4: ("o4", "Dee", "Dunn")}
SCHEDULE = {1: [(1, 2), (3, 4)], 2: [(1, 3), (2, 4)], 3: [(1, 4), (2, 3)], 4: [(1, 2), (3, 4)]}
SCORES = {
    1: {1: 100.0, 2: 90.0, 3: 120.0, 4: 80.0},
    2: {1: 110.0, 2: 95.0, 3: 85.0, 4: 105.0},
    3: {1: 130.0, 2: 70.0, 3: 100.0, 4: 90.0},
    4: {1: 60.0, 2: 140.0, 3: 95.0, 4: 115.0},
}
# Resulting records: Ann 3-1, Cy 2-2, Dee 2-2, Ben 1-3.
# (label, position, lineup slot, share of the team's score). Every team starts the same six every
# week, so the slot structure stays stable; traded and added players replace an occupant rather
# than appearing as an extra starter.
STARTERS = [("QB", "QB", "QB", .30), ("RB", "RB", "RB", .25), ("WR", "WR", "WR", .20),
            ("WR2", "WR", "WR", .10), ("TE", "TE", "RB/WR/TE", .10), ("K", "K", "K", .05)]
FINAL_STANDING = {1: 1, 2: 4, 3: 2, 4: 3}

PLAYED = '{"receivingTargets": 3.0, "teamWin": 1.0}'
DID_NOT_PLAY = "{}"
TRADE_WEEK = 1
STAR_ID, DUD_ID, HERO_ID, DROPPED_ID = 9101, 9102, 9001, 406


def team_name(tid: int, year: int) -> str:
    return f"{OWNERS[tid][1]}'s {year} Team"


def _members(year: int) -> pd.DataFrame:
    return pd.DataFrame([{"season": year, "member_id": oid, "display_name": first.lower(),
                          "first_name": first, "last_name": last, "is_league_manager": tid == 1}
                         for tid, (oid, first, last) in OWNERS.items()])


def _teams(year: int, complete: bool) -> pd.DataFrame:
    rows = []
    for tid, (oid, first, _) in OWNERS.items():
        pf = sum(SCORES[w][tid] for w in SCORES)
        rows.append({"season": year, "team_id": tid, "team_name": team_name(tid, year),
                     "team_abbrev": first[:2].upper(), "owners": f"{OWNERS[tid][1]} {OWNERS[tid][2]}",
                     "owner_ids": oid, "division": "League", "wins": 0, "losses": 0, "ties": 0,
                     "points_for": pf, "points_against": pf, "streak": "WIN 1",
                     "playoff_seed_or_current_standing": tid,
                     "final_standing": FINAL_STANDING[tid] if complete else 0,
                     "playoff_pct_espn_sim": 50.0, "draft_day_projected_rank": tid, "waiver_rank": tid,
                     "acquisitions": 3, "faab_spent": 10, "drops": 2, "trades": 0, "moves_to_ir": 0,
                     "logo_url": ""})
    return pd.DataFrame(rows)


def _matchups(year: int, final_through: int) -> pd.DataFrame:
    rows = []
    for week, games in SCHEDULE.items():
        for home, away in games:
            final = week <= final_through
            hs, as_ = (SCORES[week][home], SCORES[week][away]) if final else (0.0, 0.0)
            rows.append({
                "season": year, "matchup_period": week, "nfl_weeks": str(week),
                "game_type": "regular_season", "playoff_tier": "NONE",
                "status": "final" if final else "not_final",
                "home_team_id": home, "home_team": team_name(home, year),
                "home_owner": f"{OWNERS[home][1]} {OWNERS[home][2]}", "home_score": hs,
                "away_team_id": away, "away_team": team_name(away, year),
                "away_owner": f"{OWNERS[away][1]} {OWNERS[away][2]}", "away_score": as_,
                "winner": ("HOME" if hs > as_ else "AWAY") if final else "UNDECIDED",
                "winning_team": "", "margin": abs(hs - as_) if final else 0.0,
            })
    return pd.DataFrame(rows)


def _row(year: int, week: int, tid: int, player: str, pid: int, pos: str, slot: str,
         started: bool, points: float, projected: float, stats: str | None = None) -> dict:
    opponents = {h: a for h, a in SCHEDULE[week]} | {a: h for h, a in SCHEDULE[week]}
    return {"nfl_week": week, "matchup_period": week, "is_playoff": False,
            "team_id": tid, "team": team_name(tid, year), "owner": OWNERS[tid][1],
            "opponent": team_name(opponents[tid], year), "opponent_owner": OWNERS[opponents[tid]][1],
            "team_week_score": SCORES[week][tid], "team_week_projected": SCORES[week][tid],
            "player": player, "player_id": pid, "position": pos, "nfl_team": "NE",
            "lineup_slot": slot, "started": started, "points": points, "projected_points": projected,
            "nfl_opponent": "BUF", "opponent_rank_vs_position": 10, "on_bye": False,
            "injury_status": "ACTIVE",
            "stat_breakdown": stats if stats is not None else (PLAYED if points > 0 else DID_NOT_PLAY),
            "points_breakdown": "{}"}


STAR = ("Traded Star", STAR_ID, 25.0, 20.0)
DUD = ("Traded Dud", DUD_ID, 2.0, 9.0)


def _occupant(tid: int, week: int, label: str) -> tuple | None:
    """Who fills a starting slot when it isn't the team's own generic player."""
    if label == "WR2" and tid in (1, 2):
        # Ann starts the star until the week-1 trade sends him to Ben.
        before = tid == 1
        return (STAR if before else DUD) if week <= TRADE_WEEK else (DUD if before else STAR)
    if tid == 3 and week > TRADE_WEEK:
        if label == "RB":
            return ("Waiver Hero", HERO_ID, 15.0, 11.0)      # Cy's week-2 waiver claim
        if label == "WR2":
            return ("Dee bench WR", DROPPED_ID, 12.0, 6.0)   # the player Dee dropped
    return None


def _lineups(year: int, final_through: int, zero_starter_team: int | None = None,
             unlucky_team: int | None = None, moves: bool = False) -> pd.DataFrame:
    rows = []
    for week in range(1, final_through + 1):
        for tid in OWNERS:
            score = SCORES[week][tid]
            for i, (label, pos, slot, share) in enumerate(STARTERS):
                swap = _occupant(tid, week, label) if moves else None
                if swap:
                    name, pid, pts, proj = swap
                else:
                    name, pid = f"{OWNERS[tid][1]} {label}", tid * 100 + i
                    pts, proj = round(score * share, 2), round(score * share * 1.1, 2)
                    if label == "TE" and zero_starter_team == tid:
                        pts, proj = 0.0, 0.0    # ESPN knew he was out; starting him is on the manager
                    if label == "TE" and unlucky_team == tid:
                        pts, proj = 0.0, 12.0   # projected to play, then scratched: bad luck
                rows.append(_row(year, week, tid, name, pid, pos, slot, True, pts, proj))
            # Ann's bench monster was projected for nothing: a good call that blew up on her.
            bench = [("WR", 40.0, 4.0), ("RB", 3.0, 3.0)] if tid == 1 else [("WR", 4.0, 4.0), ("RB", 3.0, 3.0)]
            for i, (pos, pts, proj) in enumerate(bench, start=len(STARTERS)):
                pid = tid * 100 + i
                if moves and pid == DROPPED_ID and week > TRADE_WEEK:
                    continue                    # Dee dropped him after week 1
                rows.append(_row(year, week, tid, f"{OWNERS[tid][1]} bench {pos}", pid, pos, "BE",
                                 False, pts, proj))
    return pd.DataFrame(rows)


def _draft(year: int) -> pd.DataFrame:
    # Ann drafts well, Ben drafts badly; the rest are in between.
    quality = {1: 1.4, 2: 0.6, 3: 1.0, 4: 1.0}
    rows, pick = [], 0
    for rnd in range(1, 6):
        for tid in OWNERS:
            pick += 1
            pos = ["RB", "WR", "QB", "TE", "K"][rnd - 1]
            # Dee's fourth-rounder is the tight end who gets scratched, so his raw points look bad.
            pid = tid * 100 + 4 if (tid == 4 and rnd == 4) else 1000 + pick
            rows.append({"overall_pick": pick, "round": rnd, "round_pick": tid,
                         "team_id": tid, "team": team_name(tid, year), "owner": OWNERS[tid][1],
                         "player": f"{OWNERS[tid][1]} pick {rnd}", "player_id": pid,
                         "position": pos, "nfl_team": "NE", "is_keeper": False,
                         "auction_price": 0, "nominated_by": "",
                         "player_season_points": round(200 * quality[tid] / rnd, 1),
                         "player_avg_points": 10.0, "player_position_rank": rnd})
    return pd.DataFrame(rows)


def _rosters(year: int) -> pd.DataFrame:
    # Ann is deep at RB and thin at WR; Ben is the mirror image. A trade exists between them.
    books = {
        1: [("RB", 18.0), ("RB", 16.0), ("RB", 14.0), ("WR", 6.0), ("WR", 5.0), ("QB", 15.0), ("TE", 8.0)],
        2: [("WR", 17.0), ("WR", 15.0), ("WR", 13.0), ("RB", 5.0), ("RB", 4.0), ("QB", 14.0), ("TE", 7.0)],
        3: [("RB", 11.0), ("RB", 10.0), ("WR", 11.0), ("WR", 10.0), ("QB", 12.0), ("TE", 9.0), ("K", 8.0)],
        4: [("RB", 10.0), ("RB", 9.0), ("WR", 10.0), ("WR", 9.0), ("QB", 11.0), ("TE", 8.0), ("K", 7.0)],
    }
    rows = []
    for tid, players in books.items():
        for i, (pos, avg) in enumerate(players):
            rows.append({"snapshot_date": f"{year}-10-01", "team_id": tid, "team": team_name(tid, year),
                         "owner": OWNERS[tid][1], "player": f"{OWNERS[tid][1]} {pos}{i}",
                         "player_id": tid * 1000 + i, "position": pos, "eligible_slots": pos,
                         "nfl_team": "NE", "lineup_slot": pos if i < 2 else "BE",
                         "acquisition_type": "DRAFT", "injury_status": "ACTIVE",
                         "season_points": avg * 4, "avg_points": avg, "projected_season_points": avg * 14,
                         "position_rank": i + 1, "pct_rostered_espn": 90.0, "pct_started_espn": 80.0})
    return pd.DataFrame(rows)


def _tx(year: int, tid: str, week: int, ttype: str, status: str, item: str, player: str,
        pid: int, from_team: str, to_team: str, bid: int = 0) -> dict:
    return {"season": year, "transaction_id": tid, "related_transaction_id": "", "nfl_week": week,
            "proposed_date": "", "processed_date": f"{year}-09-0{week} 03:18:02",
            "transaction_type": ttype, "status": status, "initiating_team": to_team or from_team,
            "initiating_owner": "", "faab_bid": bid, "item_type": item, "player": player,
            "player_id": pid, "from_team": from_team, "to_team": to_team,
            "from_owner": "", "to_owner": ""}


def _transactions(year: int, moves: bool) -> pd.DataFrame:
    pool = "Free Agency/Waivers"
    rows = [
        _tx(year, "t1", 2, "WAIVER", "EXECUTED", "ADD", "Waiver Hero", HERO_ID, pool, team_name(3, year), 5),
        _tx(year, "t2", 2, "WAIVER", "FAILED_INVALID_PLAYER_SOURCE", "ADD", "The One That Got Away",
            9002, pool, team_name(4, year), 3),
    ]
    if moves:
        rows += [
            _tx(year, "t3", TRADE_WEEK, "TRADE_ACCEPT", "EXECUTED", "TRADE", "Traded Star", STAR_ID,
                team_name(1, year), team_name(2, year)),
            _tx(year, "t3", TRADE_WEEK, "TRADE_ACCEPT", "EXECUTED", "TRADE", "Traded Dud", DUD_ID,
                team_name(2, year), team_name(1, year)),
            _tx(year, "t4", 1, "FREEAGENT", "EXECUTED", "DROP", "Dee bench WR", DROPPED_ID,
                team_name(4, year), pool),
        ]
    return pd.DataFrame(rows)


def make_season(year: int, final_through: int, complete: bool, zero_starter_team: int | None = None,
                unlucky_team: int | None = None, moves: bool = False) -> Season:
    settings = {
        "league_name": "Test League", "team_count": 4, "regular_season_matchups": 4,
        "playoff_team_count": 2, "playoff_matchup_period_length_weeks": 1,
        "first_scoring_week": 1, "final_scoring_week": 4, "current_week_at_export": final_through,
        "current_matchup_period_at_export": final_through, "exported_at": f"{year}-10-01T00:00:00",
        "playoff_seed_tie_rule": "TOTAL_POINTS_SCORED", "trade_deadline": "none",
    }
    return Season(year=year, settings=settings, members=_members(year), teams=_teams(year, complete),
                  matchups=_matchups(year, final_through), draft=_draft(year),
                  transactions=_transactions(year, moves), rosters=_rosters(year),
                  lineups=_lineups(year, final_through, zero_starter_team, unlucky_team, moves))


def build_seasons() -> dict[int, Season]:
    """2100 is finished; 2101 has weeks 1-2 played and 3-4 still on the schedule."""
    return {2100: make_season(2100, 4, complete=True, moves=True),
            2101: make_season(2101, 2, complete=False, zero_starter_team=2, unlucky_team=4, moves=True)}


@pytest.fixture
def seasons() -> dict[int, Season]:
    return build_seasons()


@pytest.fixture
def ident(seasons) -> Identity:
    return Identity(seasons)
