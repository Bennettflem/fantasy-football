---
name: league-news
description: League news headlines (trades, waiver moves, injuries, streaks, standings moves, playoff odds, trade deadline, next week's matchups). Use when the user asks what's going on in the league or wants a news update.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats league-news
```

Options: `--season 2025`, `--week 8` (news after that week), `--json`.

The output is grouped bullets: Trades, Waiver wire, Injury report (current rosters only), Streaks, Standings, Playoff odds (ESPN's simulation), Calendar, and a preview of next week with a Game of the Week (highest combined power score) and a Beer Mile Bowl (lowest).

Presenting it:
- Rewrite the bullets as short punchy headlines with a sentence each, like a league newsletter. Keep every fact from the bullets; don't add facts that aren't there.
- A "(!)" after a dropped player means he was drafted in the first six rounds or averages 8+ points; call those out.
- "missed on X (claim failed)" means a waiver claim lost to another team or was invalid.
- End with the data freshness line the command prints.
