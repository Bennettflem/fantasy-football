"""
ESPN Fantasy Football League Exporter (for a Claude Project)
=============================================================

Exports your ESPN fantasy football league into clean CSV/JSON files that you
upload to a Claude Project as knowledge.

TWO MODES
---------
  Full history (run once, or any time you want a clean rebuild):
      python espn_league_export.py

  Current season only (run weekly, e.g. Tuesday morning after MNF):
      python espn_league_export.py --current

  One specific season:
      python espn_league_export.py --season 2025

Requires:  pip install espn-api
Tested against espn-api 0.46.0.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

# =============================================================================
# CONFIG: fill these in (or set them as environment variables)
# =============================================================================
LEAGUE_ID = int(os.environ.get("ESPN_LEAGUE_ID", "0"))          # from your league URL: ...?leagueId=XXXXXXX
ESPN_S2 = os.environ.get("ESPN_S2", "PASTE_ESPN_S2_COOKIE_HERE")  # long cookie value
SWID = os.environ.get("ESPN_SWID", "{PASTE-SWID-HERE}")          # includes the curly braces

FIRST_SEASON = 2024      # the league's first season on ESPN
CURRENT_SEASON = None    # None = auto-detect (NFL season year). Or hardcode, e.g. 2026

OUTPUT_DIR = "league_data"
INCLUDE_MESSAGE_BOARD = True   # league message board posts (trash talk, commish notes)
REQUEST_PAUSE_SECONDS = 0.4    # polite pause between ESPN requests
# =============================================================================

try:
    from espn_api.football import League
except ImportError:
    sys.exit("Missing library. Run:  pip install espn-api")

# Transaction types worth keeping (lineup-setting moves are excluded as noise)
TXN_TYPES = [
    "FREEAGENT", "WAIVER", "WAIVER_ERROR",
    "TRADE_PROPOSAL", "TRADE_ACCEPT", "TRADE_DECLINE",
    "TRADE_VETO", "TRADE_UPHOLD", "TRADE_ERROR",
]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def pause():
    time.sleep(REQUEST_PAUSE_SECONDS)


def detect_current_season():
    now = datetime.now()
    # NFL fantasy seasons run Sep-Jan; Jan/Feb still belong to last year's season
    return now.year if now.month >= 3 else now.year - 1


def ms_to_iso(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def write_csv(path, rows, fieldnames=None):
    if not rows:
        log(f"  (no rows) {os.path.basename(path)} skipped")
        return
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log(f"  wrote {os.path.basename(path)} ({len(rows)} rows)")


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
    log(f"  wrote {os.path.basename(path)}")


def safe(fn, default=None, label=""):
    try:
        return fn()
    except Exception as e:
        if label:
            log(f"  WARNING: {label} failed: {e}")
        return default


def owner_names(team):
    owners = getattr(team, "owners", None) or []
    names = []
    for o in owners:
        if isinstance(o, dict):
            full = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
            names.append(full or o.get("displayName", ""))
        else:
            names.append(str(o))
    if not names and getattr(team, "owner", None):
        names.append(str(team.owner))
    return " & ".join(n for n in names if n)


def owner_ids(team):
    owners = getattr(team, "owners", None) or []
    return "|".join(o.get("id", "") for o in owners if isinstance(o, dict))


def team_lookup(league):
    return {t.team_id: t for t in league.teams}


# -----------------------------------------------------------------------------
# Exporters
# -----------------------------------------------------------------------------
def export_settings(league, year, out):
    s = league.settings
    settings = {
        "season": year,
        "league_name": s.name,
        "team_count": s.team_count,
        "regular_season_matchups": s.reg_season_count,
        "playoff_team_count": s.playoff_team_count,
        "playoff_matchup_period_length_weeks": getattr(s, "playoff_matchup_period_length", None),
        "matchup_periods_to_weeks": s.matchup_periods,
        "first_scoring_week": getattr(league, "firstScoringPeriod", None),
        "final_scoring_week": getattr(league, "finalScoringPeriod", None),
        "current_week_at_export": league.current_week,
        "current_matchup_period_at_export": getattr(league, "currentMatchupPeriod", None),
        "keeper_count": s.keeper_count,
        "trade_deadline": ms_to_iso(s.trade_deadline) if s.trade_deadline else "none",
        "veto_votes_required": s.veto_votes_required,
        "scoring_type": s.scoring_type,
        "median_scoring_enabled": getattr(s, "median_scoring", None),
        "tie_rule": s.tie_rule,
        "playoff_tie_rule": s.playoff_tie_rule,
        "playoff_seed_tie_rule": s.playoff_seed_tie_rule,
        "uses_faab": s.faab,
        "faab_budget": s.acquisition_budget,
        "divisions": s.division_map,
        "lineup_slot_counts": getattr(s, "position_slot_counts", {}),
        "scoring_rules": getattr(s, "scoring_format", []),
        "previous_seasons_on_espn": getattr(league, "previousSeasons", []),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(os.path.join(out, f"{year}_settings.json"), settings)

    # Raw settings too, as a safety net for anything the summary misses
    raw = safe(lambda: league.espn_request.league_get(params={"view": "mSettings"}),
               label="raw settings")
    if raw and "settings" in raw:
        write_json(os.path.join(out, f"{year}_settings_raw.json"), raw["settings"])


def export_members(league, year, out):
    rows = []
    for m in getattr(league, "members", []) or []:
        rows.append({
            "season": year,
            "member_id": m.get("id"),
            "display_name": m.get("displayName"),
            "first_name": m.get("firstName"),
            "last_name": m.get("lastName"),
            "is_league_manager": m.get("isLeagueManager"),
        })
    write_csv(os.path.join(out, f"{year}_members.csv"), rows)


def export_teams(league, year, out):
    rows = []
    for t in league.teams:
        rows.append({
            "season": year,
            "team_id": t.team_id,
            "team_name": t.team_name,
            "team_abbrev": t.team_abbrev,
            "owners": owner_names(t),
            "owner_ids": owner_ids(t),
            "division": t.division_name,
            "wins": t.wins,
            "losses": t.losses,
            "ties": t.ties,
            "points_for": round(t.points_for, 2),
            "points_against": t.points_against,
            "playoff_seed_or_current_standing": t.standing,
            "final_standing": t.final_standing,
            "streak": f"{t.streak_type} {t.streak_length}",
            "playoff_pct_espn_sim": round(t.playoff_pct, 1),
            "draft_day_projected_rank": t.draft_projected_rank,
            "waiver_rank": getattr(t, "waiver_rank", ""),
            "acquisitions": t.acquisitions,
            "faab_spent": getattr(t, "acquisition_budget_spent", ""),
            "drops": t.drops,
            "trades": t.trades,
            "moves_to_ir": t.move_to_ir,
            "logo_url": t.logo_url,
        })
    write_csv(os.path.join(out, f"{year}_teams.csv"), rows)


def export_matchups(league, year, out):
    """One row per matchup (per matchup period), including playoffs/consolation."""
    teams = team_lookup(league)
    data = safe(lambda: league.espn_request.league_get(params={"view": "mMatchupScore"}),
                label="matchup schedule")
    rows = []
    reg_count = league.settings.reg_season_count
    periods = league.settings.matchup_periods or {}

    for m in (data or {}).get("schedule", []):
        mp = m.get("matchupPeriodId")
        home = m.get("home", {}) or {}
        away = m.get("away", {}) or {}
        h_id, a_id = home.get("teamId"), away.get("teamId")
        h_t, a_t = teams.get(h_id), teams.get(a_id)
        h_pts, a_pts = home.get("totalPoints"), away.get("totalPoints")
        winner = m.get("winner", "UNDECIDED")
        tier = m.get("playoffTierType", "NONE")

        if winner == "HOME":
            win_id = h_id
        elif winner == "AWAY":
            win_id = a_id
        else:
            win_id = None

        rows.append({
            "season": year,
            "matchup_period": mp,
            "nfl_weeks": "/".join(str(w) for w in periods.get(str(mp), periods.get(mp, []))),
            "game_type": "regular_season" if (mp or 0) <= reg_count else "postseason",
            "playoff_tier": tier,  # e.g. WINNERS_BRACKET, LOSERS_CONSOLATION_LADDER, NONE
            "status": "bye" if not a_t else ("final" if winner != "UNDECIDED" else "not_final"),
            "home_team_id": h_id,
            "home_team": h_t.team_name if h_t else "",
            "home_owner": owner_names(h_t) if h_t else "",
            "home_score": h_pts,
            "away_team_id": a_id if a_id is not None else "BYE",
            "away_team": a_t.team_name if a_t else "BYE",
            "away_owner": owner_names(a_t) if a_t else "",
            "away_score": a_pts if a_t else "",
            "winner": winner,
            "winning_team": teams[win_id].team_name if win_id in teams else ("TIE" if winner == "TIE" else ""),
            "margin": round(abs((h_pts or 0) - (a_pts or 0)), 2) if a_t and winner != "UNDECIDED" else "",
        })
    rows.sort(key=lambda r: (r["matchup_period"] or 0, str(r["home_team_id"])))
    write_csv(os.path.join(out, f"{year}_matchups.csv"), rows)


def export_weekly_lineups(league, year, out):
    """Every rostered player, every week: slot, points, projections, stat breakdown."""
    teams = team_lookup(league)
    last_week = min(league.current_week, getattr(league, "finalScoringPeriod", league.current_week))
    period_for_week = {}
    for mp, weeks in (league.settings.matchup_periods or {}).items():
        for w in weeks:
            period_for_week[w] = mp

    cache = {}
    rows = []
    for week in range(1, last_week + 1):
        log(f"  box scores week {week}/{last_week}")
        boxes = safe(lambda: league.box_scores(week=week, player_team_cache=cache),
                     default=[], label=f"box scores week {week}")
        pause()
        for b in boxes:
            sides = [
                (b.home_team, b.home_score, b.home_projected, b.home_lineup, b.away_team),
                (b.away_team, b.away_score, b.away_projected, b.away_lineup, b.home_team),
            ]
            for team, score, proj, lineup, opp in sides:
                if not team or isinstance(team, int):
                    continue
                opp_real = opp if opp and not isinstance(opp, int) else None
                opp_name = opp_real.team_name if opp_real else "BYE"
                opp_owner = owner_names(opp_real) if opp_real else ""
                for p in lineup:
                    slot = getattr(p, "slot_position", "")
                    rows.append({
                        "season": year,
                        "nfl_week": week,
                        "matchup_period": period_for_week.get(week, ""),
                        "is_playoff": b.is_playoff,
                        "team_id": team.team_id,
                        "team": team.team_name,
                        "owner": owner_names(team),
                        "opponent": opp_name,
                        "opponent_owner": opp_owner,
                        "team_week_score": score,
                        "team_week_projected": round(proj, 2) if isinstance(proj, (int, float)) else proj,
                        "player": p.name,
                        "player_id": p.playerId,
                        "position": p.position,
                        "nfl_team": getattr(p, "proTeam", ""),
                        "lineup_slot": slot,
                        "started": slot not in ("BE", "IR"),
                        "points": round(p.points or 0, 2),
                        "projected_points": round(p.projected_points or 0, 2),
                        "nfl_opponent": getattr(p, "pro_opponent", ""),
                        "opponent_rank_vs_position": getattr(p, "pro_pos_rank", ""),
                        "on_bye": getattr(p, "on_bye_week", ""),
                        "injury_status": getattr(p, "injuryStatus", ""),
                        "stat_breakdown": json.dumps(getattr(p, "breakdown", {}) or {}, default=str),
                        "points_breakdown": json.dumps(getattr(p, "points_breakdown", {}) or {}, default=str),
                    })
    write_csv(os.path.join(out, f"{year}_weekly_lineups.csv"), rows)


def export_rosters(league, year, out):
    """Roster snapshot as of the export (end-of-season rosters for past years)."""
    rows = []
    for t in league.teams:
        for p in t.roster:
            rows.append({
                "season": year,
                "snapshot_date": datetime.now().strftime("%Y-%m-%d"),
                "team_id": t.team_id,
                "team": t.team_name,
                "owner": owner_names(t),
                "player": p.name,
                "player_id": p.playerId,
                "position": p.position,
                "eligible_slots": "/".join(s for s in (p.eligibleSlots or []) if s),
                "nfl_team": p.proTeam,
                "lineup_slot": p.lineupSlot,
                "acquisition_type": p.acquisitionType,
                "injury_status": p.injuryStatus,
                "season_points": round(p.total_points or 0, 2),
                "avg_points": round(p.avg_points or 0, 2),
                "projected_season_points": round(p.projected_total_points or 0, 2),
                "position_rank": p.posRank,
                "pct_rostered_espn": p.percent_owned,
                "pct_started_espn": p.percent_started,
            })
    write_csv(os.path.join(out, f"{year}_rosters.csv"), rows)


def export_draft(league, year, out):
    picks = league.draft or []
    if not picks:
        log("  no draft data (draft may not have happened)")
        return

    # Batch-lookup player info for position / NFL team / season points
    info = {}
    ids = [p.playerId for p in picks if p.playerId]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        res = safe(lambda: league.player_info(playerId=chunk), default=[], label="draft player lookup")
        if res and not isinstance(res, list):
            res = [res]
        for pl in res or []:
            info[pl.playerId] = pl
        pause()

    rows = []
    for idx, p in enumerate(picks, start=1):
        pl = info.get(p.playerId)
        team = p.team if p.team and not isinstance(p.team, (int, str)) else None
        nom = p.nominatingTeam if p.nominatingTeam and not isinstance(p.nominatingTeam, (int, str)) else None
        rows.append({
            "season": year,
            "overall_pick": idx,
            "round": p.round_num,
            "round_pick": p.round_pick,
            "team_id": team.team_id if team else "",
            "team": team.team_name if team else "",
            "owner": owner_names(team) if team else "",
            "player": p.playerName,
            "player_id": p.playerId,
            "position": pl.position if pl else "",
            "nfl_team": pl.proTeam if pl else "",
            "is_keeper": p.keeper_status,
            "auction_price": p.bid_amount,
            "nominated_by": nom.team_name if nom else "",
            "player_season_points": round(pl.total_points or 0, 2) if pl else "",
            "player_avg_points": round(pl.avg_points or 0, 2) if pl else "",
            "player_position_rank": pl.posRank if pl else "",
        })
    write_csv(os.path.join(out, f"{year}_draft.csv"), rows)


def export_transactions(league, year, out):
    """Adds, drops, waiver claims (incl. failed bids), trades, trade proposals/vetoes."""
    teams = team_lookup(league)
    pmap = league.player_map
    last_week = min(league.current_week, getattr(league, "finalScoringPeriod", league.current_week))
    seen = set()
    rows = []

    def tname(tid):
        t = teams.get(tid)
        return t.team_name if t else ("Free Agency/Waivers" if tid in (0, -1, None) else str(tid))

    def towner(tid):
        t = teams.get(tid)
        return owner_names(t) if t else ""

    for week in range(0, last_week + 1):  # week 0 = preseason moves
        headers = {"x-fantasy-filter": json.dumps({"transactions": {"filterType": {"value": TXN_TYPES}}})}
        data = safe(lambda: league.espn_request.league_get(
            params={"view": "mTransactions2", "scoringPeriodId": week}, headers=headers),
            default={}, label=f"transactions week {week}")
        pause()
        for tx in (data or {}).get("transactions", []):
            if tx.get("id") in seen:
                continue
            seen.add(tx.get("id"))
            items = tx.get("items", []) or []
            for it in items:
                if it.get("type") == "LINEUP":
                    continue
                rows.append({
                    "season": year,
                    "transaction_id": tx.get("id"),
                    "related_transaction_id": tx.get("relatedTransactionId", ""),
                    "nfl_week": tx.get("scoringPeriodId"),
                    "proposed_date": ms_to_iso(tx.get("proposedDate")),
                    "processed_date": ms_to_iso(tx.get("processDate")),
                    "transaction_type": tx.get("type"),
                    "status": tx.get("status"),
                    "initiating_team": tname(tx.get("teamId")),
                    "initiating_owner": towner(tx.get("teamId")),
                    "faab_bid": tx.get("bidAmount", ""),
                    "item_type": it.get("type"),  # ADD, DROP, TRADE
                    "player": pmap.get(it.get("playerId"), it.get("playerId")),
                    "player_id": it.get("playerId"),
                    "from_team": tname(it.get("fromTeamId")),
                    "from_owner": towner(it.get("fromTeamId")),
                    "to_team": tname(it.get("toTeamId")),
                    "to_owner": towner(it.get("toTeamId")),
                })

    if not rows:
        # Fallback: ESPN's activity feed (completed moves only, no failed bids)
        log("  falling back to recent activity feed")
        offset = 0
        while offset < 5000:
            acts = safe(lambda: league.recent_activity(size=100, offset=offset),
                        default=[], label="recent activity")
            pause()
            if not acts:
                break
            for a in acts:
                for (team, action, player, bid) in a.actions:
                    rows.append({
                        "season": year,
                        "processed_date": ms_to_iso(a.date),
                        "transaction_type": action,
                        "status": "EXECUTED",
                        "initiating_team": getattr(team, "team_name", str(team)),
                        "initiating_owner": owner_names(team) if not isinstance(team, (int, str)) else "",
                        "faab_bid": bid,
                        "player": getattr(player, "name", str(player)),
                        "player_id": getattr(player, "playerId", ""),
                    })
            offset += 100

    rows.sort(key=lambda r: (r.get("processed_date") or r.get("proposed_date") or ""))
    write_csv(os.path.join(out, f"{year}_transactions.csv"), rows)


def export_message_board(league, year, out):
    msgs = safe(lambda: league.message_board(), default=[], label="message board")
    if msgs:
        write_json(os.path.join(out, f"{year}_message_board.json"), msgs)


def rebuild_combined(out):
    """Stack every season's teams/matchups/draft into all-time files."""
    for kind in ("teams", "matchups", "draft", "transactions"):
        combined = []
        for fn in sorted(os.listdir(out)):
            if fn.endswith(f"_{kind}.csv") and fn[:4].isdigit():
                with open(os.path.join(out, fn), encoding="utf-8") as f:
                    combined.extend(csv.DictReader(f))
        write_csv(os.path.join(out, f"ALL_SEASONS_{kind}.csv"), combined)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def export_season(year, out):
    log(f"=== Season {year} ===")
    league = League(league_id=LEAGUE_ID, year=year, espn_s2=ESPN_S2, swid=SWID)
    log(f"  connected: {league.settings.name} ({len(league.teams)} teams, "
        f"current week {league.current_week})")
    export_settings(league, year, out)
    export_members(league, year, out)
    export_teams(league, year, out)
    export_matchups(league, year, out)
    export_draft(league, year, out)
    export_transactions(league, year, out)
    export_rosters(league, year, out)
    export_weekly_lineups(league, year, out)
    if INCLUDE_MESSAGE_BOARD:
        export_message_board(league, year, out)


def main():
    parser = argparse.ArgumentParser(description="Export an ESPN fantasy football league.")
    parser.add_argument("--current", action="store_true", help="export only the current season")
    parser.add_argument("--season", type=int, help="export one specific season")
    args, _ = parser.parse_known_args()  # parse_known_args keeps Colab/Jupyter happy

    if not LEAGUE_ID or "PASTE" in ESPN_S2 or "PASTE" in SWID:
        sys.exit("Fill in LEAGUE_ID, ESPN_S2 and SWID at the top of the script first.")

    current = CURRENT_SEASON or detect_current_season()
    if args.season:
        seasons = [args.season]
    elif args.current:
        seasons = [current]
    else:
        seasons = list(range(FIRST_SEASON, current + 1))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for yr in seasons:
        try:
            export_season(yr, OUTPUT_DIR)
        except Exception as e:
            log(f"!! Season {yr} failed: {e}")
            log("   (401/403 usually means expired or wrong espn_s2 / SWID cookies)")

    rebuild_combined(OUTPUT_DIR)
    log(f"Done. Files are in ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
