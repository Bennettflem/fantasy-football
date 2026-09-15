# Fantasy Football League Export

Exports our ESPN fantasy football league (2024–present) to CSV/JSON files for a Claude Project. See [DATA_REFERENCE.md](DATA_REFERENCE.md) for what every file and column means.

## Setup (once)

Requires Python 3.9+.

```powershell
python -m pip install --user -r requirements.txt
```

(`--user` is needed when Python is installed system-wide in `C:\Python311`, which isn't writable without admin.)

The script needs three values. Set them as environment variables rather than pasting them into the script, so they never end up in git:

| Variable | Where to find it |
|---|---|
| `ESPN_LEAGUE_ID` | The number after `leagueId=` in the league URL |
| `ESPN_S2` | Log into ESPN, press F12 → Application (Chrome) or Storage (Firefox) → Cookies → espn.com → `espn_s2` |
| `ESPN_SWID` | Same place, `SWID` cookie. Keep the curly braces. |

PowerShell (current window only):

```powershell
$env:ESPN_LEAGUE_ID = "1234567"
$env:ESPN_S2 = "AEB..."
$env:ESPN_SWID = "{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}"
```

To avoid retyping, put those three lines in a `set_env.ps1` file (already gitignored) and run `. .\set_env.ps1` before exporting.

Treat the two cookies like a password. They expire periodically; if the script fails with 401/403 errors, grab fresh ones.

## Running

| When | Command | What it does |
|---|---|---|
| First time | `python espn_league_export.py` | Exports every season, 2024 through the current one |
| Weekly (Tuesday after MNF) | `python espn_league_export.py --current` | Re-exports only the current season |
| Rebuild one year | `python espn_league_export.py --season 2025` | Re-exports just that season |

Output goes to `league_data/` (gitignored). The four `ALL_SEASONS_*` files are rebuilt on every run.

Scores don't change between Tuesday and the next game, so once a week is enough.

## Stats and skills

`ffstats/` computes league analytics from `league_data/`. Run it directly or through the Claude Code skills in `.claude/skills/`:

| Skill | Command | What it gives you |
|---|---|---|
| `/refresh-data` | `. .\set_env.ps1; python espn_league_export.py --current` | Fresh export of the current season |
| `/power-rankings` | `python -m ffstats power-rankings` | Weekly power rankings with movement and the reason behind each rank |
| `/beer-mile-odds` | `python -m ffstats beer-mile-odds` | Betting odds on who finishes last |
| `/superlatives` | `python -m ffstats superlatives` | Weekly awards (high/low score, worst start/sit, bust, pickup of the week...) |
| `/league-news` | `python -m ffstats league-news` | Headlines: trades, waivers, injuries, streaks, next week's preview |
| `/league-stats` | `python -m ffstats league-stats [topic]` | All-time history: standings, head-to-head, luck, streaks, records, draft, waivers, lineups, trades |
| `/owner-history` | `python -m ffstats owner-history <name>` | One person's history across every season and team name |
| `/weekly-report` | `python -m ffstats weekly-report` | Everything above in one file under `reports/` |
| `/group-chat` | `python -m ffstats group-chat [awards\|power\|beer\|news]` | Plain-text recap with emoji, ready to paste into iMessage |

**From your phone:** run `/remote-control` in a Claude Code session on this PC (opened in this folder), then open the Claude iPhone app, tap **Code**, and pick the session. The skills run on the PC, so it has to stay on. Use `/group-chat` and tap copy on the result to paste it into the league chat.

Every command accepts `--season YYYY`, `--week N`, and `--json`. Defaults are the latest season and the last completed week.

**Power rankings** blend six rank-scaled components: all-play win% (30%), points per game (20%), record (15%), last three weeks (15%), roster management (waiver points + lineup efficiency, 10%), and owner history (prior seasons' second-half turnarounds and waiver usage, 10%; 25% in weeks 1-3).

**Beer mile odds** = softmax over a misery score that is 60% inverse power ranking and 40% bad luck (schedule luck, points against, close losses, games a perfect lineup would have won, and prior-season finishes).

Everything is keyed by ESPN owner ID, so a person's history holds together across team renames.

Tests: `python -m pytest tests/`.

## Claude Project

1. First time: upload every file in `league_data/` plus `DATA_REFERENCE.md`.
2. Each week: replace the `2026_*` files and the four `ALL_SEASONS_*` files. Past seasons never change.
3. Put anything ESPN doesn't track (trophies, punishments, side bets, nicknames, rule changes) in the Project's custom instructions.

## Alternative: Google Colab

No local install needed. In a new notebook at colab.research.google.com: run `!pip install espn-api`, upload the script via the folder icon, fill in the three config values at the top of the script, run `!python espn_league_export.py`, then download `league_data/` from the file panel. Don't save a copy with your cookies filled in anywhere shared.
