---
name: playoff-odds
description: Monte Carlo playoff odds for the current season (make the playoffs, bye, #1 seed, last place, projected wins), compared against ESPN's own simulation. Use when the user asks about playoff chances, seeding, who's in trouble, or what a team needs.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats playoff-odds
```

Options: `--season 2025`, `--week 8` (odds as of that week), `--sims 20000`, `--seed 7`, `--json`.

How it works: each team's weekly score is drawn from its own scoring distribution, shrunk toward its prior-season average early in the year (and only half of last season's scoring edge carries over, because rosters turn over every draft). Every remaining regular-season game is simulated 5,000 times. Seeding uses wins, then total points, matching ESPN's tiebreak.

Presenting it:
- Lead with who's safe, who's on the bubble, and who's in real trouble - not the whole table, unless asked.
- The `vs ESPN` column is the fun part: where this model and ESPN's disagree most is usually the story.
- The `Last` column is the beer mile column; pair it with `/beer-mile-odds` if the user cares about the punishment.
- Early in the season the odds are wide and the model knows it. Don't present week-2 odds as settled.
- End with the data freshness line the command prints.
