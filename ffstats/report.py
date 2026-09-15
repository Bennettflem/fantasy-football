from __future__ import annotations

import os

from .beer_mile import beer_mile_markdown, beer_mile_odds
from .core import default_week
from .data import REPO_ROOT, Season
from .identity import Identity
from .league_stats import TOPICS, league_stats
from .news import league_news, news_markdown
from .power import power_markdown, power_rankings
from .superlatives import superlatives, superlatives_markdown

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def weekly_report(seasons: dict[int, Season], year: int, week: int | None = None,
                  ident: Identity | None = None, write: bool = True) -> tuple[str, str | None]:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    parts = [
        f"# Blood, Sweats, and Beers: {year} Week {W} Report",
        f"_Data exported {season.exported_at}_",
        "",
        news_markdown(league_news(seasons, year, W, ident), season, W),
        "",
        superlatives_markdown(superlatives(seasons, year, W, ident), season, W),
        "",
        power_markdown(power_rankings(seasons, year, W, ident), season),
        "",
        beer_mile_markdown(beer_mile_odds(seasons, year, W, ident), season),
        "",
        "## Stat of the week",
        league_stats(seasons, ident, TOPICS[W % len(TOPICS)]).split("\n", 2)[-1].strip(),
    ]
    text = "\n".join(parts)
    path = None
    if write:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        path = os.path.join(REPORTS_DIR, f"{year}_week{W:02d}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return text, path
