---
name: weekly-report
description: Build the full weekly league report (news, superlatives, power rankings, beer mile odds, stat of the week) and save it to reports/. Use on Tuesdays after refreshing data, or when the user wants the whole package to share with the league.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats weekly-report
```

Options: `--week 8`, `--season 2025`, `--no-write` (print only). The report is saved to `reports/<year>_week<NN>.md` and printed.

Presenting it:
- Don't paste the whole report back; it's long. Give the file path, then a tight summary: top 3 power rankings, the beer mile favorite, two or three superlatives worth talking about, and the biggest news item.
- For something to send to the league, use `/group-chat` (plain text for iMessage) rather than this report.
- If the data freshness line is older than a week, run `/refresh-data` first and then rerun this.
- Never commit the report; the user decides what goes into git.
