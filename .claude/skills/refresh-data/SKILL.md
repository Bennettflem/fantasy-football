---
name: refresh-data
description: Re-export the ESPN league data (current season by default) so the stats skills use fresh numbers. Run on Tuesday mornings after Monday Night Football, or whenever the user asks for fresh data.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; . .\set_env.ps1; python espn_league_export.py --current
```

If the user says "full" or wants every season rebuilt, drop `--current`:

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; . .\set_env.ps1; python espn_league_export.py
```

Notes:
- `set_env.ps1` holds the ESPN cookies and league ID. It is gitignored. Never print its contents or paste the cookie values into chat.
- A 401/403 or "League ... does not exist" error on every season means the `espn_s2`/`SWID` cookies expired. Tell the user to refresh them in `set_env.ps1` (espn.com, F12, Application/Storage, Cookies) and re-run.
- "message board failed" warnings for past seasons are expected; ESPN only serves the current season's board.
- The current run takes about a minute; a full run about three.

When it finishes, report the current week from the output ("connected: ... current week N") and the row counts for matchups, transactions, and weekly lineups. Then offer to run `/weekly-report`.
