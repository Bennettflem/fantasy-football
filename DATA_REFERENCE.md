# League Data Reference

This document describes every file produced by `espn_league_export.py`, every column in each file, and the known gaps. Upload it to the Claude Project alongside the data so Claude knows how to read the files.

The league began on ESPN in 2024, so the export covers 2024, 2025, and 2026 (the current season). All three seasons are 2019 or later, which means ESPN's full box-score and transaction endpoints are available for every year.

## File overview

Each season produces its own set of files, prefixed with the year (for example `2025_matchups.csv`). After every run, the script also rebuilds four all-time files by stacking the season files together.

| File | One row per | Purpose |
|---|---|---|
| `YYYY_settings.json` | season | League rules, scoring, roster slots, playoff format |
| `YYYY_settings_raw.json` | season | ESPN's unedited settings object (safety net) |
| `YYYY_members.csv` | league member | Real names and ESPN display names |
| `YYYY_teams.csv` | team | Final (or current) record, points, standings, move counts |
| `YYYY_matchups.csv` | matchup | Every head-to-head result, regular season and playoffs |
| `YYYY_draft.csv` | draft pick | Full draft board with how each player turned out |
| `YYYY_transactions.csv` | player moved | Adds, drops, waiver claims (incl. failed bids), trades, trade proposals and vetoes |
| `YYYY_rosters.csv` | rostered player | Roster snapshot at the moment of export |
| `YYYY_weekly_lineups.csv` | player per team per week | Who started, who sat, and what everyone scored |
| `YYYY_message_board.json` | post | League message board posts (raw ESPN format) |
| `ALL_SEASONS_teams.csv` | team-season | All-time standings table |
| `ALL_SEASONS_matchups.csv` | matchup | All-time head-to-head history |
| `ALL_SEASONS_draft.csv` | pick | Every draft in league history |
| `ALL_SEASONS_transactions.csv` | player moved | Every move in league history |

## YYYY_settings.json

**League structure:** league name, number of teams, number of regular-season matchups, number of playoff teams, how many weeks each playoff round lasts, the mapping of matchup periods to NFL weeks, first and final scoring weeks, and divisions.

**Status at export time:** the current NFL week and current matchup period, plus the timestamp of the export. For the current season, these tell Claude how fresh the data is.

**Rules:** keeper count, trade deadline, veto votes required, tie-breaking rules for regular season, playoffs, and playoff seeding, and whether median (top-half win bonus) scoring is on.

**Scoring and rosters:** scoring type (e.g. head-to-head points), every scoring rule with its stat ID and point value (e.g. passing TD = 4), and starting lineup slot counts by position.

**Waivers:** whether FAAB is used and the season budget.

**History:** the list of prior seasons ESPN has on file for this league.

`YYYY_settings_raw.json` is ESPN's complete settings object. It exists because the summarized version relies on the library's labeling, which occasionally mislabels lineup slots; if anything in the summary looks off, the raw file is authoritative.

## YYYY_members.csv

`season`, `member_id` (ESPN's permanent ID), `display_name` (ESPN username), `first_name`, `last_name`, `is_league_manager`.

This is the most reliable way to track a person across seasons, since team names change.

## YYYY_teams.csv

**Identity:** `season`, `team_id`, `team_name`, `team_abbrev`, `owners` (real names, joined with "&" for co-owned teams), `division`.

**Record:** `wins`, `losses`, `ties`, `points_for`, `points_against`, `streak` (e.g. "WIN 3").

**Standing:** `playoff_seed_or_current_standing` (the current rank during a season, the playoff seed after it) and `final_standing` (final finish including playoffs; 1 = champion; 0 until the season ends).

**ESPN projections:** `playoff_pct_espn_sim` (ESPN's simulated playoff odds) and `draft_day_projected_rank`.

**Activity:** `waiver_rank`, `acquisitions`, `faab_spent`, `drops`, `trades`, `moves_to_ir`.

**Other:** `logo_url`.

## YYYY_matchups.csv

Every matchup in the season's schedule, including playoff and consolation games. Future matchups for the current season appear with `status = not_final` and zero scores, so the full remaining schedule is visible.

| Column | Meaning |
|---|---|
| `season`, `matchup_period` | Season and ESPN matchup number |
| `nfl_weeks` | NFL week(s) the matchup covers; two-week playoff rounds show as e.g. `15/16` |
| `game_type` | `regular_season` or `postseason` |
| `playoff_tier` | `NONE`, `WINNERS_BRACKET`, `LOSERS_CONSOLATION_LADDER`, or similar ESPN labels |
| `status` | `final` or `not_final` |
| `home_team_id`, `home_team`, `home_owner`, `home_score` | Home side |
| `away_team_id`, `away_team`, `away_owner`, `away_score` | Away side (`BYE` for playoff byes) |
| `winner` | `HOME`, `AWAY`, `TIE`, or `UNDECIDED` |
| `winning_team` | Name of the winner |
| `margin` | Point difference |

Scores here are official matchup totals, so for multi-week playoff rounds they are the combined total.

## YYYY_draft.csv

| Column | Meaning |
|---|---|
| `overall_pick`, `round`, `round_pick` | Draft slot |
| `team_id`, `team`, `owner` | Who drafted |
| `player`, `player_id`, `position`, `nfl_team` | Who was drafted |
| `is_keeper` | Whether the pick was a keeper |
| `auction_price`, `nominated_by` | Auction drafts only (0 / blank in snake drafts) |
| `player_season_points`, `player_avg_points`, `player_position_rank` | How the player performed that season, for hindsight draft grades |

For the current season, the performance columns reflect the season to date.

## YYYY_transactions.csv

One row per player involved in a move. A trade of two players for one produces three rows sharing the same `transaction_id`.

| Column | Meaning |
|---|---|
| `transaction_id`, `related_transaction_id` | Groups the rows of one move; links proposals to their acceptance or veto |
| `nfl_week` | Week the move was made (0 = preseason) |
| `proposed_date`, `processed_date` | When it was submitted and when it went through |
| `transaction_type` | `FREEAGENT`, `WAIVER`, `WAIVER_ERROR` (failed claim), `TRADE_PROPOSAL`, `TRADE_ACCEPT`, `TRADE_DECLINE`, `TRADE_VETO`, `TRADE_UPHOLD`, `TRADE_ERROR` |
| `status` | e.g. `EXECUTED`, `CANCELED`, `FAILED_...`, `VETOED`, `PENDING` |
| `initiating_team` | Team that made the move or proposed the trade |
| `faab_bid` | FAAB amount bid, including losing bids |
| `item_type` | `ADD`, `DROP`, or `TRADE` |
| `player`, `player_id` | Player moved |
| `from_team`, `to_team` | Where the player came from and went ("Free Agency/Waivers" for the pool) |

This file supports questions like who overpaid on waivers, which trades were proposed and rejected, and who was involved in vetoed deals. Lineup changes and IR moves are deliberately excluded because they add thousands of low-value rows.

If ESPN's detailed transaction endpoint returns nothing for a season, the script falls back to ESPN's activity feed. In that case the file only has completed adds, drops, and trades, with fewer columns, and no failed bids or proposals.

## YYYY_rosters.csv

A snapshot of every roster at the moment the script runs. For past seasons, this is the roster ESPN has on file at season's end. For the current season, it is today's roster.

Columns: `snapshot_date`, `team_id`, `team`, `owner`, `player`, `player_id`, `position`, `eligible_slots`, `nfl_team`, `lineup_slot`, `acquisition_type` (DRAFT, ADD, TRADE), `injury_status`, `season_points`, `avg_points`, `projected_season_points`, `position_rank`, `pct_rostered_espn`, `pct_started_espn` (ESPN-wide ownership).

## YYYY_weekly_lineups.csv

The largest and most detailed file: every player on every roster for every week played so far, starters and bench.

| Column | Meaning |
|---|---|
| `nfl_week`, `matchup_period`, `is_playoff` | When |
| `team_id`, `team`, `owner`, `opponent` | Whose lineup and who they played |
| `team_week_score`, `team_week_projected` | The team's total and projection for the matchup |
| `player`, `player_id`, `position`, `nfl_team` | The player |
| `lineup_slot` | Slot used (QB, RB, FLEX-type slots, D/ST, K, `BE` = bench, `IR`) |
| `started` | True if in a starting slot |
| `points`, `projected_points` | Actual and ESPN-projected fantasy points that week |
| `nfl_opponent`, `opponent_rank_vs_position` | NFL matchup and how that defense ranks against the position |
| `on_bye`, `injury_status` | Availability |
| `stat_breakdown` | Raw stats as JSON (yards, TDs, receptions, etc.) |
| `points_breakdown` | Fantasy points earned from each stat, as JSON |

This file answers questions about points left on the bench, optimal lineups, start/sit decisions, player value to each team, and weekly high and low scorers.

For the current season, the script includes the week in progress. A row with zero points for a player who hasn't played yet is not final; `YYYY_matchups.csv` shows which matchups are finished.

For two-week playoff rounds, each NFL week has its own rows, and `team_week_score` may reflect ESPN's running matchup total rather than a single week. Use `YYYY_matchups.csv` for official playoff results.

## YYYY_message_board.json

Posts from the league's ESPN message board, saved in ESPN's raw format. It may be empty if the league doesn't use the board, and its structure isn't documented by ESPN.

## What the export does NOT capture

**Not available from ESPN's API:** ESPN group chat messages, trade proposal notes, and league-wide chat outside the message board.

**Excluded on purpose:** lineup-setting moves and IR moves in the transaction log, and players who were never on a fantasy roster.

**Not stored, but Claude can compute:** power rankings, all-play records, luck metrics, head-to-head records, and optimal lineups can all be derived from the matchups and weekly lineups files.

**Not in the data at all:** anything the league decides outside ESPN (side bets, punishments, trophies, rule-change discussions, nicknames, league lore). Put these in the Project's custom instructions.

## Freshness

Past seasons (2024, 2025) are final and never need re-exporting. The current season (2026) is only as current as the last `--current` run; check `current_week_at_export` and `exported_at` in `2026_settings.json`.
