---
name: what-if
description: Replays the season with the schedules swapped - everyone's record under every other owner's schedule, plus a schedule-luck number. Use when the user asks who got screwed by the schedule, who's a fraud, or "what if I had played their games".
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats what-if
```

Options: `--season 2025`, `--week 10` (through that week), `--json`.

How it works: everyone keeps their own weekly scores and inherits someone else's opponents. If the host played you that week, you inherit the host as your opponent. Schedule luck = actual wins minus the average across all ten schedules.

Presenting it:
- Lead with the biggest gap between actual record and average record, in both directions.
- The full grid is a lot; show the summary table unless the user wants the whole thing.
- This league has used the same schedule all three seasons, which makes recurring schedule luck a real, repeating pattern rather than noise. Worth saying out loud.
- Early in a season most schedules tie, so best/worst cases show a count instead of naming one owner. That's expected.
- End with the data freshness line the command prints.
