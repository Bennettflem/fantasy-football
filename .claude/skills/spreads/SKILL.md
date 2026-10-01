---
name: spreads
description: Betting lines for a week's games - point spread, over/under, win probability and fair moneylines for every matchup. Use when the user asks who's favored, for odds or lines on this week's games, or wants a preview with numbers.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats spreads
```

Defaults to the next week that hasn't been played. Options: `--season 2025`, `--week 11`, `--json`.

How it works: each team's projected score comes from its scoring distribution through the last completed week, shrunk toward its prior-season average. Win probability treats the two scores as independent normals; moneylines are the fair price with no juice. Past weeks show the actual result next to the line.

Presenting it:
- Lead with the biggest mismatch and the closest game.
- Early in the season everything regresses toward the league average, so most lines sit near a pick'em. Say that rather than pretending a 1-point line is a real read.
- Pairs well with `/rivalry` for the marquee game and `/group-chat` for posting.
- End with the data freshness line the command prints.
