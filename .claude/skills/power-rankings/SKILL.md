---
name: power-rankings
description: Weekly power rankings for the fantasy league (all-play record, scoring, recent form, roster management, owner history). Use when the user asks who's actually good, for power rankings, or how teams stack up.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats power-rankings
```

Options: `--season 2025`, `--week 8` (rank through that week), `--json` (component breakdown per team).

The output is a markdown table: rank, movement since last week, team (owner), score 0-100, record, points per game, all-play record, and the top driver of that team's score. Weights are listed under the table; early in the season (weeks 1-3) owner history counts more because there's little current data.

Presenting it:
- Show the table as-is, then add 3-5 sentences of commentary: who moved and why, the biggest gap between record and power rank (lucky or unlucky teams), and anything surprising.
- Refer to people as "First Last (team name)" the first time, then first name. Team names change every season; the owner is the constant.
- If the user wants to know why a team is ranked where it is, rerun with `--json` and explain the component scores (each is a 0-1 rank-scale across the league).
- End with the data freshness line the command prints. If it's older than a week, suggest `/refresh-data`.
