# Project rules for Claude

## Project overview
Local analytics for "Blood, Sweats, and Beers", a 10-team ESPN fantasy football league
(on ESPN since 2024; 14-week regular season, top 6 make playoffs). Everything runs on
this machine; there is no website or scheduled job.

Data flow: `espn_league_export.py` (ESPN API) -> `league_data/` (CSV/JSON per season)
-> `ffstats/` (Python stats package) -> Claude Code skills in `.claude/skills/`.

- Run every command from this folder (`C:\Users\benne\personal-workspace\fantasy-football`);
  `python -m ffstats` fails anywhere else.
- Weekly routine (manual, user-triggered): `/refresh-data` on Tuesday after Monday Night
  Football, then `/weekly-report`. Reports save to `reports/`.
- Skills: `/refresh-data`, `/power-rankings`, `/beer-mile-odds`, `/superlatives`,
  `/league-news`, `/league-stats`, `/owner-history`, `/weekly-report`, `/group-chat`.
  Each runs a `python -m ffstats <command>` and its SKILL.md says how to present the output.
- The user often drives this from the Claude iPhone app via Remote Control and pastes
  results into the league's iMessage group chat. `/group-chat` is the plain-text version
  for that; keep replies to it copy-paste friendly.
- The beer mile is the league's punishment for the last-place finisher.
- Track people by owner, never by team name. Almost everyone renames their team every
  season. `ffstats/identity.py` keys everything by ESPN member ID.
- Details: `README.md` (setup, commands, ranking formulas) and `DATA_REFERENCE.md`
  (every exported file and column). Read them before changing `ffstats/` or the export.
- Tests: `python -m pytest tests/`.

## Secrets and private data
- `set_env.ps1` holds the ESPN league ID and login cookies. Never print, echo, or quote
  its contents. Load it with `. .\set_env.ps1` only when running the export.
- `league_data/` and `set_env.ps1` are gitignored; keep them that way.
- The current season's `*_message_board.json` can contain direct messages.

## Git
- Never run `git commit`, `git push`, `git merge`, or any history-rewriting
  command. Stage nothing. Leave all changes in the working tree and tell me
  what you changed so I can review and commit myself.
- Never create pull requests or branches unless I explicitly ask.

## Working style
- (add your own rules here)
