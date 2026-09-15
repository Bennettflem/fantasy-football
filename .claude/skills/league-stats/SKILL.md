---
name: league-stats
description: All-time league history stats (standings, head-to-head grid, luck index, streaks, single-week records, draft hindsight, waiver hall of fame, lineup efficiency, trade activity). Use when the user asks about league history, records, or who's best all-time at something.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats league-stats       # every section
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats league-stats h2h   # one section
```

Topics: `standings`, `h2h`, `luck`, `streaks`, `records`, `draft`, `waivers`, `lineups`, `trades`.

Presenting it:
- If the user asked a specific question ("who's the luckiest owner?"), run only the relevant topic and answer the question directly, quoting the numbers.
- Everything is keyed by owner, not team name, so cross-season comparisons are fair even though most owners rename their team every year.
- Luck index = actual wins minus all-play expected wins; positive is lucky.
- "Losses a perfect lineup would have flipped" counts games where the optimal lineup would have beaten the opponent's actual score.
- Draft "steal" is the highest-scoring pick from round 6 or later; "bust" is the lowest-scoring pick from rounds 1-3.
- End with the data freshness line the command prints.
