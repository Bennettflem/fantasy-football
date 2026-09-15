---
name: group-chat
description: Plain-text weekly recap sized for the league's iMessage group chat (awards, power rankings, beer mile odds, headlines), with emoji and first names and no tables. Use when the user wants something to send to the league, a text-message version, or anything "for the group chat".
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats group-chat
```

For one section only, add `awards`, `power`, `beer`, or `news`:

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats group-chat power
```

Options: `--week 8`, `--season 2025`.

Presenting it (the user is often on their phone and will copy-paste into iMessage):
- Put the output in a single ```text code block so it can be copied in one tap. Nothing else inside the block.
- Keep your own words outside the block to one short line, e.g. "Ready to paste:".
- Don't convert it to markdown, tables, or bold. iMessage shows raw text.
- If the user asks for trash talk or a different tone, edit the text inside the block, but keep every number and fact from the command output. Never invent stats.
- If the data looks stale (the header week is behind the current NFL week), suggest `/refresh-data` first.
