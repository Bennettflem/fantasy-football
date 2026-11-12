---
name: eye-test
description: Rankings the way a football person would argue them - wins first, then the talent on the roster, who you beat, your defense, and whether you have a floor. No all-play, no luck, no expected wins. Use when the user wants eye-test rankings, "real" NFL-style rankings, a ranking where wins and the roster count more, or a second opinion on the power rankings.
---

Run in PowerShell (the `Set-Location` makes it work from any starting folder):

```powershell
Set-Location C:\Users\benne\personal-workspace\fantasy-football; python -m ffstats eye-test
```

Options: `--season 2025`, `--week 8` (rank through that week), `--json` (every raw input and component per team).

## What this is, and why it exists next to /power-rankings

`/power-rankings` is a measurement. It leans hardest on all-play - what would have happened
against nine opponents you never played - and on last week, which is why it's accurate and why
it reads like a spreadsheet.

This is an argument. It ranks the way NFL power rankings do, using only numbers a league-mate
would say out loud. **The two lists will disagree, and that's the feature.** When they do, say
so and explain which input caused it.

## The six components

| Component | Late weight | Weeks 1-3 | What it is |
|---|---|---|---|
| **Record** | 30% | 20% | Win percentage, tiebroken on total points. The eye test starts with wins. |
| **Roster talent** | 25% | 35% | The best lineup they could start *next* week off today's roster, valued at each player's season average. Reads the roster snapshot, so a trade or a waiver claim counts immediately and a guy dropped in week 3 counts for nobody. IR is excluded. |
| **Quality of wins** | 15% | 10% | For each win, credit equal to the beaten team's win percentage, summed. Beating a 6-2 team is worth more than beating a 2-6 team, and padding a record against the bottom earns less than a thinner record against real teams. |
| **Defense** | 10% | 10% | Points per week from the started D/ST slot. The one real defense in fantasy football. |
| **Floor** | 10% | 10% | The mean of a team's two worst weeks. One disaster is bad luck; two is a floor. This is the eye test's stand-in for a defense that keeps you in games. |
| **Momentum** | 10% | 15% | Win rate over the last three weeks. Results only - not scoring, not all-play. |

Each raw stat is rank-scaled 0-1 across the league, then weighted and summed to a 0-100 score.
Early in the season the roster carries more of the argument, because three weeks of results
aren't a record yet.

**Deliberately absent: all-play, expected wins, luck, lineup efficiency, bench points.** Don't
add them back in the write-up. If someone's rank looks wrong because they've been unlucky, that
belongs in `/power-rankings` - the whole point of this list is that it doesn't care.

## Blurbs

Every team gets a one-line Why next to its name, the same as the power rankings. The generated
line names the component carrying a top-half team or sinking a bottom-half one and quotes its
number, and superlative phrasings ("best record in the league") are only ever handed to the team
that actually leads that component. Use the generated line when it fits, but you have free reign
to write your own. Rules when you do:

- **Argue, don't measure.** This is the list where you're allowed to say a team is a fraud, or
  that a roster is scary, or that nobody wants to play someone in December. Write like a guy
  talking about the NFL, not like a model.
- Lead with wins, the roster, or a specific player. Those are the eye-test currencies. `--json`
  gives you each team's best player and their average, plus a count of their top-12 players.
- Stay factual. Every claim has to be checkable in the table or `--json` - no invented scores,
  players or streaks.
- One line per team, phone-length, and no two reading alike.
- Punch at the manager's decisions and the roster, not at anyone personally.

## Presenting it

- Show the table, then 3-5 sentences. **The most useful commentary is always where this list
  and `/power-rankings` disagree** - run both, name the biggest mover between them, and say
  which component did it.
- Refer to people as "First Last (team name)" the first time, then first name.
- If someone asks why a team is where it is, rerun with `--json` and walk the six components.
  Each is a 0-1 rank-scale across the league.
- End with the data freshness line the command prints.
