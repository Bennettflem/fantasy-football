---
name: beer-mile-odds
description: Betting odds on who finishes last and runs the beer mile (reverse power rankings plus a bad-luck factor). Use when the user asks about the beer mile, last place, reverse rankings, or who's in trouble.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats beer-mile-odds
```

Options: `--season 2025`, `--week 8`, `--json` (misery components per team).

The output lists every owner with American odds (+450 style), implied probability, record, and the biggest reason they're in danger. Misery = 60% inverse power ranking + 40% bad luck (schedule luck, points against, close losses, games a perfect lineup would have won, and prior-season finishes including past last places). Once the regular season is over it also prints the OFFICIAL beer mile runner.

**The beer mile goes to the regular-season loser.** Last place by record at the end of the
regular season runs it - not ESPN's `final_standing`, which is the post-playoff placement and
puts the consolation-bracket winner above teams that were worse all year. The two are different
people in this league, so never quote a final standing when the question is who runs:
- 2024: **Cooper Anderson** ran it (2-12). ESPN's final standing says Jonathan Cowan.
- 2025: **Whitt Phillips** ran it (4-10). ESPN's final standing says Luke Phillips.

The `curse` component scores past regular-season finishes for the same reason.

**Every owner gets a blurb.** Like the power rankings, each person in the list carries a
one-line Why written next to their name - not just the bare table. The generated `why` is the
single largest misery component and works as a floor, but you have free reign to write your own
when the data gives you something better (a specific number, a past beer mile, a bench total, a
rivalry). Rules when you do:
- **Tone follows the odds, not movement.** The favorite gets the harshest line; the middle of the
  board gets nervous or teasing; the longest shots get relief, smugness or a light ribbing. The
  tone should get gentler as the odds get longer.
- Stay factual. Every claim has to be checkable in the table, `--json`, or data you just pulled -
  no invented scores, streaks or past punishments.
- One line per person, phone-length, and no two reading alike.
- Punch at the manager's decisions and their luck, not at anyone personally.

Presenting it:
- Show the table with its blurbs, then write it up like a sportsbook preview: the favorite and why, the value pick (someone whose odds seem too long or short given their record), and who's safe.
- Keep it playful; this is a punishment league. But don't invent facts: every claim should trace to the table or to `--json` components.
- "Why" reasons are the single largest factor for that team, not the only one.
- End with the data freshness line the command prints.
