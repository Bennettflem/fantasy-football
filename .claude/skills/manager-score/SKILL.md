---
name: manager-score
description: Composite grade for how well each person is managing their team - draft value, start/sit decisions, waiver work, trades and roster hygiene - with luck reported separately instead of scored. Use when the user asks who the best manager is, who's actually good at this, or how someone is doing apart from their record.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats manager-score
```

Options: `--season 2025`, `--week 8` (through that week), `--json` (component scores per owner).

Weights: draft 25%, start/sit process 25%, waivers 20%, trades 15%, lineup outcome 10%, roster hygiene 5%.

What makes it different from the power rankings: this grades decisions, not results.

- **Start/sit is process, not outcome.** It compares the projected points of the lineup they started against the best lineup they could have started by projection. Starting the higher-projected player and watching him bust is good management; the separate "lineup outcome" component (10%) is where actual-vs-optimal lives.
- **Draft VOR is injury-adjusted.** A drafted player who was projected 5+ and didn't play was a late scratch, so the pick gets credited the projection. A player ESPN already projected at zero was a known out - no credit, and starting him is charged as an unforced error instead. ESPN's weekly `injury_status` is useless for this (it's an export-time snapshot); an empty `stat_breakdown` is what actually identifies a player who didn't take the field.
- **Trades count hard, but a fresh verdict counts less.** A trade is graded as soon as the players have a week of scoring for their new team; one week counts at 25% and the weight ramps to full after four weeks (shown as `@%` in the Trades column). They are never shrunk by sample size, because trades are rare and risky: one that works moves you up, one that blows up costs you. Anyone who hasn't traded sits neutral rather than penalized. Trades come from `/trade-history`'s roster-movement reconstruction, not ESPN's transaction log, which loses them.
- **Luck is reported, never scored.** The luck column sits next to the score so people can argue with the right number.

Presenting it:
- Lead with the gap between manager score and actual standing - the person managing best while losing, and the person winning despite themselves.
- Quote the component that drove someone's score rather than just the total.
- Early in a season every component is thin. Say so; don't present week-2 numbers as a verdict.
- This league has completed four trades in three seasons, so the trade column will be empty for most people. That's expected, not a bug.
- End with the data freshness line the command prints.
