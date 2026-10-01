---
name: roast
description: One personalized roast per owner for a given week, drawn from the week's worst decisions (benchings, zeros, low scores, kickers outscoring quarterbacks, failed waiver claims). Use when the user wants trash talk, burns, or something mean for the group chat.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats roast
```

Options: `--season 2025`, `--week 6`, `--json`.

How it works: every owner qualifies for a set of roast categories based on what actually happened that week, and the strongest claim wins. Each category is used by exactly one owner, so no two people get the same joke. Owners with a genuinely clean week get a "nothing to see here" line - that's the joke for them.

Presenting it:
- Every number in the output is real. Never invent a burn; if it isn't in the data, it doesn't go in.
- For the group chat, strip the table and send first names plus the roast, one per line.
- If the user wants it meaner, sharpen the wording but keep every name, player and number exactly as the command produced them.
- End with the data freshness line the command prints.
