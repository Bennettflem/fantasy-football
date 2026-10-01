---
name: trade-history
description: Every trade in league history, rebuilt from weekly roster movement because ESPN's transaction log loses them. Use when the user asks what trades have happened, about a specific trade, or who trades the most.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats trade-history
```

Options: `--json`.

Why this exists: ESPN stores a trade's players on the original proposal and purges that record once the trade resolves. What survives is an accept/veto/uphold record pointing at an id that returns nothing, so completed trades vanish from `YYYY_transactions.csv`. Ten trades happened across 2024-2026; the transaction log only has the players for three of them.

How it's rebuilt: `weekly_lineups.csv` shows which team every rostered player was on each week. A player changing teams was either added from the wire (the log does record adds) or traded. Unexplained moves are kept only when players crossed between the same two rosters in both directions in the same week - one-way moves are treated as unlogged waiver pickups and excluded, since the log is missing ordinary adds too.

The `ESPN log` column says how well ESPN corroborates each leg: **accepted** (ESPN recorded the completed swap), **proposal** (only the offer survived), **roster only** (nothing in the log).

Presenting it:
- Weeks are the first week the players appeared on their new rosters, which can be a week after the trade was agreed.
- The same reconstruction feeds `/manager-score`'s trade component and `/league-stats trades`, so those agree with this.
- If a trade looks wrong, check it against `ESPN log` and say which evidence it rests on.
- End with the data freshness line the command prints.
