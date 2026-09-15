from __future__ import annotations

import argparse
import json
import sys

from .beer_mile import beer_mile_markdown, beer_mile_odds
from .data import load_all
from .groupchat import SECTIONS, group_chat
from .identity import Identity
from .league_stats import TOPICS, league_stats
from .news import league_news, news_markdown
from .owner import owner_history
from .power import power_markdown, power_rankings
from .report import weekly_report
from .superlatives import superlatives, superlatives_markdown


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--season", type=int, help="season year (default: latest exported)")
    common.add_argument("--week", type=int, help="through this week (default: last completed)")
    common.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser = argparse.ArgumentParser(prog="ffstats", description="League analytics from league_data/.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("power-rankings", parents=[common])
    sub.add_parser("beer-mile-odds", parents=[common])
    sub.add_parser("superlatives", parents=[common])
    sub.add_parser("league-news", parents=[common])
    ls = sub.add_parser("league-stats", parents=[common])
    ls.add_argument("topic", nargs="?", choices=TOPICS)
    oh = sub.add_parser("owner-history", parents=[common])
    oh.add_argument("name")
    wr = sub.add_parser("weekly-report", parents=[common])
    wr.add_argument("--no-write", action="store_true")
    gc = sub.add_parser("group-chat", parents=[common], help="plain-text recap for iMessage")
    gc.add_argument("section", nargs="?", choices=SECTIONS)
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    seasons = load_all()
    if not seasons:
        sys.exit("No seasons found in league_data/. Run espn_league_export.py first.")
    ident = Identity(seasons)
    year = args.season or max(seasons)
    if year not in seasons:
        sys.exit(f"Season {year} is not exported. Available: {sorted(seasons)}")
    season = seasons[year]

    try:
        if args.cmd == "power-rankings":
            df = power_rankings(seasons, year, args.week, ident)
            print(json.dumps(df.reset_index().to_dict("records"), default=str, indent=1) if args.json
                  else power_markdown(df, season))
        elif args.cmd == "beer-mile-odds":
            df = beer_mile_odds(seasons, year, args.week, ident)
            print(json.dumps(df.reset_index().to_dict("records"), default=str, indent=1) if args.json
                  else beer_mile_markdown(df, season))
        elif args.cmd == "superlatives":
            from .core import default_week
            W = default_week(season, args.week, regular_only=False)
            awards = superlatives(seasons, year, W, ident)
            print(json.dumps(awards, indent=1) if args.json else superlatives_markdown(awards, season, W))
        elif args.cmd == "league-news":
            from .core import default_week
            W = default_week(season, args.week)
            sections = league_news(seasons, year, W, ident)
            print(json.dumps(dict(sections), indent=1) if args.json else news_markdown(sections, season, W))
        elif args.cmd == "league-stats":
            print(league_stats(seasons, ident, args.topic))
        elif args.cmd == "owner-history":
            print(owner_history(seasons, args.name, ident))
        elif args.cmd == "weekly-report":
            text, path = weekly_report(seasons, year, args.week, ident, write=not args.no_write)
            print(text)
            if path:
                print(f"\n_(saved to {path})_")
        elif args.cmd == "group-chat":
            print(group_chat(seasons, year, args.week, ident, args.section))
            return
    except ValueError as e:
        sys.exit(str(e))
    if not args.json:
        print(f"\n_Data exported {season.exported_at}._")


if __name__ == "__main__":
    main()
