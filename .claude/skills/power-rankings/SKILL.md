---
name: power-rankings
description: Weekly power rankings for the fantasy league (all-play record, scoring, recent form, roster management, owner history). Use when the user asks who's actually good, for power rankings, or how teams stack up.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats power-rankings
```

Options: `--season 2025`, `--week 8` (rank through that week), `--json` (component breakdown per team).

The output is a markdown table: rank, movement since last week, team (owner), score 0-100, record, points per game, all-play record, and a "Why" line for that team. Weights are listed under the table; early in the season (weeks 1-3) owner history counts more because there's little current data.

The Why line is picked from the strongest claim a team actually qualifies for (juggernaut, scoring, lucky/unlucky, fraud, hot/cold streak, riser/faller, bench points, lineup efficiency, waiver build, points against, owner history). At most two teams share a reason in a week, and the second one gets a different phrasing, so no two teams ever read alike. Claims that need a sample (luck, fraud, bench, waiver, points against) are suppressed in the first weeks, so early rankings lean on generic rank-tier lines - that's expected, not a bug.

**Tone follows movement.** A team that climbed only ever gets a line that reads as praise; a team that fell only ever gets a knock, and the knock gets harsher at 3+ spots lost. A team that held its rank can take any tone. This is enforced in the code, so the table that prints is already correct on this.

**You may write your own Why lines.** The preset ones are a floor, not a ceiling. Use the generated line whenever it genuinely fits, but if you can see something truer or funnier in the data - a specific player, a renamed team, a rivalry, a number nobody has said out loud - write that instead and say you did. Rules when you do:
- Keep the movement rule: up means positive, down means negative, bigger drop means harsher.
- Stay factual. Every claim has to be checkable in the data you just pulled; no invented scores, players or streaks.
- One line per team, phone-length, and still no two teams reading alike.
- Punch at the manager's decisions, not at anyone personally.

**In group chat form, leave the score out.** The 0-100 score is a ranking input, not a
talking point - nobody in the chat knows what 79.4 means and it invites arguing with the
decimal instead of the rank. Give rank, first name, record, movement and the Why line. Keep
the score in the markdown table, where the weights note underneath explains it.

Presenting it:
- Show the table as-is, then add 3-5 sentences of commentary: who moved and why, the biggest gap between record and power rank (lucky or unlucky teams), and anything surprising.
- Refer to people as "First Last (team name)" the first time, then first name. Team names change every season; the owner is the constant.
- If the user wants to know why a team is ranked where it is, rerun with `--json` and explain the component scores (each is a 0-1 rank-scale across the league).
- End with the data freshness line the command prints. If it's older than a week, suggest `/refresh-data`.
