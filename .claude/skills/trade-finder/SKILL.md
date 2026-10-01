---
name: trade-finder
description: Finds realistic two-player trades where both teams upgrade a starting spot from the other's bench. Use when the user asks about trades, who they should trade with, or what a team needs.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats trade-finder
```

Options: `--season 2025`, `--top 5`, `--json`.

How it works: each team's starting requirement per position comes from the actual lineup slots (flex counts toward RB/WR). A player is "spare" if he's behind a starter at his position. A deal is proposed when each side sends a spare who would start for the other team, both sides gain at least 0.8 points per game, and the two players are within 3.0 points per game of each other. Injured and IR players are never offered. Only the best offer per pair of owners is shown.

Presenting it:
- Lead with the one or two deals that help both sides most, in plain language: who sends whom, and what each side fixes.
- Values are season-to-date points per game from the roster snapshot, so early in the year they're noisy. Say so, and sanity-check a proposal against what the player actually is before pitching it.
- This league completed four trades in three seasons, so frame these as conversation starters rather than obvious wins.
- End with the data freshness line the command prints.
