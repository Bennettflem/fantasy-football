---
name: draft-grades
description: Draft grades by value over replacement - who actually won each draft, best and worst picks, and the 10 best players from that draft class. Use when the user asks who drafted well, for draft grades, or about a specific draft.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats draft-grades              # every draft
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats draft-grades --season 2025
```

Options: `--season 2025`, `--json`.

How it works: each pick is scored against replacement level at its own position - what the last startable player at that position returned across the league - so drafting a quarterback early isn't automatically rewarded. Grades are a curve within each draft class, because one outlier draft would otherwise drag everyone else down. The current season's numbers are season-to-date.

Presenting it:
- Lead with who won and lost the draft, then the single best and worst pick.
- The "10 best players drafted that year" list is where the arguments come from - point out any that went late.
- Distinguish drafting well from finishing well; this league has a person who drafts best and finishes worst.
- Grades are relative, so someone always gets an F. Say that, rather than implying their draft was objectively terrible.
- End with the data freshness line the command prints.
