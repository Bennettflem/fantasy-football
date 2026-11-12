from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from .beer_mile import beer_mile_markdown, beer_mile_odds
from .data import load_all
from .draft_grades import draft_grades, draft_grades_markdown
from .eye_test import eye_test, eye_test_markdown
from .groupchat import SECTIONS, group_chat
from .identity import Identity
from .league_stats import TOPICS, league_stats
from .manager import (career_manager_score, career_manager_score_markdown, manager_score,
                      manager_score_markdown)
from .news import league_news, news_markdown
from .owner import owner_history
from .playoff_odds import playoff_odds, playoff_odds_markdown
from .power import power_markdown, power_rankings
from .report import weekly_report
from .rivalry import rivalry, rivalry_markdown
from .roast import roast, roast_markdown
from .spreads import spreads, spreads_markdown
from .superlatives import superlatives, superlatives_markdown
from .trade_finder import trade_finder, trade_finder_markdown
from .backtest import backtest, backtest_markdown
from .trades import trade_history, trade_history_markdown
from .whatif import what_if, what_if_markdown


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.reset_index().to_json(orient="records"))


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--season", type=int, help="season year (default: latest exported)")
    common.add_argument("--week", type=int, help="through this week (default: last completed)")
    common.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser = argparse.ArgumentParser(prog="ffstats", description="League analytics from league_data/.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("power-rankings", parents=[common])
    sub.add_parser("eye-test", parents=[common], help="rank by wins, roster and defense - no all-play")
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
    po = sub.add_parser("playoff-odds", parents=[common], help="simulate the rest of the season")
    po.add_argument("--sims", type=int, default=5000)
    po.add_argument("--seed", type=int, default=0)
    sub.add_parser("what-if", parents=[common], help="everyone's record under everyone's schedule")
    sub.add_parser("spreads", parents=[common], help="betting lines for a week's games")
    sub.add_parser("roast", parents=[common], help="one roast per owner for a week")
    rv = sub.add_parser("rivalry", parents=[common], help="head-to-head report for two owners")
    rv.add_argument("names", nargs="*", help="two names; omit for the next game of the week")
    tf = sub.add_parser("trade-finder", parents=[common], help="two-player swaps that help both sides")
    tf.add_argument("--top", type=int, default=10)
    sub.add_parser("draft-grades", parents=[common], help="draft value over replacement")
    ms = sub.add_parser("manager-score", parents=[common], help="composite manager grade, luck removed")
    ms.add_argument("--all-time", action="store_true", help="every season, weighted by weeks played")
    sub.add_parser("trade-history", parents=[common], help="every trade, rebuilt from roster movement")
    bt = sub.add_parser("backtest", parents=[common], help="score power-ranking schemes against next week")
    bt.add_argument("--min-week", type=int, default=2, help="first week to rank from (default 2)")
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
        elif args.cmd == "eye-test":
            df = eye_test(seasons, year, args.week, ident)
            print(json.dumps(_records(df), default=str, indent=1) if args.json
                  else eye_test_markdown(df, season))
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
        elif args.cmd == "playoff-odds":
            df = playoff_odds(seasons, year, args.week, ident, args.sims, args.seed)
            print(json.dumps(_records(df), indent=1) if args.json else playoff_odds_markdown(df, season))
        elif args.cmd == "what-if":
            df = what_if(seasons, year, args.week, ident)
            print(json.dumps(_records(df), indent=1) if args.json else what_if_markdown(df, season, ident))
        elif args.cmd == "spreads":
            df = spreads(seasons, year, args.week, ident)
            print(json.dumps(_records(df), indent=1) if args.json else spreads_markdown(df, season, ident))
        elif args.cmd == "roast":
            from .core import default_week
            W = default_week(season, args.week, regular_only=False)
            items = roast(seasons, year, W, ident)
            print(json.dumps(items, indent=1) if args.json else roast_markdown(items, season, W))
        elif args.cmd == "rivalry":
            if len(args.names) not in (0, 2):
                sys.exit("Give two names, or none for the next game of the week.")
            a, b = (args.names + [None, None])[:2]
            rep = rivalry(seasons, ident, a, b, year, args.week)
            if args.json:
                print(json.dumps({"a": rep["a"], "b": rep["b"], "record": rep["record"],
                                  "meetings": _records(rep["games"])}, indent=1))
            else:
                print(rivalry_markdown(rep, ident))
        elif args.cmd == "trade-finder":
            deals = trade_finder(seasons, year, ident, args.top)
            print(json.dumps(_records(deals), indent=1) if args.json
                  else trade_finder_markdown(deals, season, ident))
        elif args.cmd == "backtest":
            df = backtest(seasons, ident, min_week=args.min_week)
            print(json.dumps(_records(df), indent=1) if args.json else backtest_markdown(df))
        elif args.cmd == "trade-history":
            legs = trade_history(seasons, ident)
            print(json.dumps(_records(legs), indent=1) if args.json else trade_history_markdown(legs, ident))
        elif args.cmd == "manager-score":
            if getattr(args, "all_time", False):
                df = career_manager_score(seasons, ident)
                print(json.dumps(_records(df), indent=1) if args.json
                      else career_manager_score_markdown(df))
            else:
                df = manager_score(seasons, year, args.week, ident)
                print(json.dumps(_records(df), indent=1) if args.json
                      else manager_score_markdown(df, season))
        elif args.cmd == "draft-grades":
            reports = draft_grades(seasons, args.season, ident)
            if args.json:
                print(json.dumps([{"year": r["year"], "rows": r["rows"]} for r in reports], indent=1))
            else:
                print(draft_grades_markdown(reports, ident))
    except ValueError as e:
        sys.exit(str(e))
    if not args.json:
        print(f"\n_Data exported {season.exported_at}._")


if __name__ == "__main__":
    main()
