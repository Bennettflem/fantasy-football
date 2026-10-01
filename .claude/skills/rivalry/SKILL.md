---
name: rivalry
description: Head-to-head report between two owners - series record, every meeting, biggest blowout, closest game, current streak, and current form. With no names it previews the upcoming game of the week. Use when the user asks about a matchup, a rivalry, or the game of the week.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats rivalry              # next game of the week
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats rivalry Bennett Dean
```

Names can be a first name, last name, or team name. Ambiguous names (two Coopers) return the list of matches - rerun with a last name.

Options: `--season 2025`, `--week 9` (preview that week instead of the next one), `--json`.

Presenting it:
- Lead with the series record and the single most interesting pattern, then the meeting table.
- This league's schedule repeats every season, so pairs meet in the same weeks every year. If one owner owns a particular week, say so - it's a real pattern, not a coincidence.
- With no names given, the pick is the game with the highest combined power score that week. Say which game it chose.
- Good input for a promo image prompt; the series record and current form are the lines worth putting on the graphic.
- End with the data freshness line the command prints.
