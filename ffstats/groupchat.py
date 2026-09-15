from __future__ import annotations

import pandas as pd

from .beer_mile import beer_mile_odds
from .core import default_week
from .data import Season
from .identity import Identity
from .news import league_news
from .power import power_rankings
from .superlatives import superlatives

SECTIONS = ["awards", "power", "beer", "news"]
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
AWARD_EMOJI = {
    "High score": "🔥",
    "Beer Mile Watch (low score)": "🍺",
    "Biggest blowout": "💥",
    "Closest game": "😬",
    "Unluckiest loss": "💔",
    "Worst start/sit": "🤡",
    "Player of the week": "⭐",
    "Bust of the week": "💩",
    "Pickup of the week": "🛒",
}
AWARD_LABEL = {"Beer Mile Watch (low score)": "Low score"}


def shorten(text: str, ident: Identity, year: int) -> str:
    """Replace 'Full Name (Team)' and 'Full Name' with the owner's short name."""
    owners = ident.owners()
    for oid in owners:
        for full in (ident.label(oid, year), ident.label(oid)):
            text = text.replace(full, ident.short(oid))
    for oid in owners:
        text = text.replace(ident.name(oid), ident.short(oid))
    return text


def _awards(seasons, year, week, ident) -> list[str]:
    lines = []
    for a in superlatives(seasons, year, week, ident):
        emoji = AWARD_EMOJI.get(a["Award"])
        if emoji:
            name = AWARD_LABEL.get(a["Award"], a["Award"])
            lines.append(f"{emoji} {name}: {shorten(a['Who'], ident, year)}, {shorten(a['Detail'], ident, year)}")
    return lines


def _power(seasons, year, week, ident) -> list[str]:
    lines = []
    for oid, r in power_rankings(seasons, year, week, ident).iterrows():
        rank = int(r["rank"])
        mv = r.movement
        move = "" if pd.isna(mv) or int(mv) == 0 else (f" ▲{int(mv)}" if mv > 0 else f" ▼{-int(mv)}")
        lines.append(f"{MEDALS.get(rank, f'{rank}.')} {ident.short(oid)} ({ident.team(oid, year)}) {r.record}{move}")
    return lines


def _beer(seasons, year, week, ident) -> list[str]:
    df = beer_mile_odds(seasons, year, week, ident)
    if df.attrs.get("official"):
        return [f"OFFICIAL: {shorten(df.attrs['official'], ident, year)} runs the beer mile"]
    lines = []
    for i, (oid, r) in enumerate(df.head(4).iterrows(), start=1):
        line = f"{i}. {ident.short(oid)} {r.odds}"
        if i == 1:
            line += f" ({r.why.lower()})"
        lines.append(line)
    lines.append(f"Safest: {ident.short(df.index[-1])} {df.iloc[-1].odds}")
    return lines


def _news(seasons, year, week, ident) -> list[str]:
    sections = dict(league_news(seasons, year, week, ident))
    picked = sections.get("Trades", []) + sections.get("Streaks", []) + sections.get(f"Week {week + 1} preview", [])[:2]
    return [shorten(x, ident, year) for x in picked]


def group_chat(seasons: dict[int, Season], year: int, week: int | None = None,
               ident: Identity | None = None, section: str | None = None) -> str:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    award_week = week if week is not None else default_week(season, None, regular_only=False)
    thru = f" (thru wk {W})" if W != award_week else ""
    blocks = {
        "awards": (f"🏅 WEEK {award_week} AWARDS", lambda: _awards(seasons, year, award_week, ident)),
        "power": (f"📊 POWER RANKINGS{thru}", lambda: _power(seasons, year, W, ident)),
        "beer": (f"🍺 BEER MILE ODDS{thru}", lambda: _beer(seasons, year, W, ident)),
        "news": ("📰 AROUND THE LEAGUE", lambda: _news(seasons, year, W, ident)),
    }
    out = []
    if section is None:
        name = str(season.settings.get("league_name", "League")).upper()
        out.append(f"🏈 {name}: WEEK {award_week} RECAP")
    for key in ([section] if section else SECTIONS):
        title, build = blocks[key]
        lines = build()
        if lines:
            out.append("\n".join([title, *lines]))
    return "\n\n".join(out)
