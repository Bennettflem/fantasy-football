---
name: owner-history
description: One owner's full league history across every season and team name (records, finishes, all-play, luck, waiver usage, lineup efficiency, head-to-head vs everyone, early draft picks). Use when the user asks about a specific person's history or track record.
---

Run in PowerShell with a first name, last name, or team name (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats owner-history Dean
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats owner-history "First Down"
```

If the name is ambiguous (two Coopers), the command lists the matches; rerun with a last name.

Presenting it:
- Show the by-season table, then summarize the arc in 2-4 sentences: trajectory, signature strength or weakness (waiver activity, lineup efficiency, luck), and their best and worst rival from the head-to-head list.
- Team names change yearly; always say "Dean (then Burrows Pound Town, now Sutton on this Dih)" style when it helps.
- End with the data freshness line the command prints.
