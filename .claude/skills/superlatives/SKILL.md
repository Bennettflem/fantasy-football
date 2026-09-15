---
name: superlatives
description: Weekly awards for the fantasy league (high/low score, blowout, closest game, best bench, worst start/sit, player and bust of the week, pickup of the week). Use when the user asks for weekly awards, superlatives, or what happened this week.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats superlatives
```

Options: `--week 3` (defaults to the last fully completed week, including playoff weeks), `--season 2025`, `--json`.

Presenting it:
- Show the table, then add a short line of color for the two or three best awards (the worst start/sit and unluckiest loss are usually the fun ones).
- If the user asks for a specific week, pass `--week`. Week 15+ are playoff/consolation weeks.
- "Beer Mile Watch" is the week's lowest score. "All-play king" is the team that would have beaten the most opponents that week.
- End with the data freshness line the command prints.
