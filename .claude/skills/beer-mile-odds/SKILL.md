---
name: beer-mile-odds
description: Betting odds on who finishes last and runs the beer mile (reverse power rankings plus a bad-luck factor). Use when the user asks about the beer mile, last place, reverse rankings, or who's in trouble.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats beer-mile-odds
```

Options: `--season 2025`, `--week 8`, `--json` (misery components per team).

The output lists every owner with American odds (+450 style), implied probability, record, and the biggest reason they're in danger. Misery = 60% inverse power ranking + 40% bad luck (schedule luck, points against, close losses, games a perfect lineup would have won, and prior-season finishes including past last places). Once the regular season is over it also prints the OFFICIAL beer mile runner from ESPN's final standings.

Presenting it:
- Show the table, then write it up like a sportsbook preview: the favorite and why, the value pick (someone whose odds seem too long or short given their record), and who's safe.
- Keep it playful; this is a punishment league. But don't invent facts: every claim should trace to the table or to `--json` components.
- "Why" reasons are the single largest factor for that team, not the only one.
- End with the data freshness line the command prints.
