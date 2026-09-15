from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("FF_LEAGUE_DATA", os.path.join(REPO_ROOT, "league_data"))

BOOL_COLS = {"started", "is_playoff", "on_bye", "is_keeper", "is_league_manager"}
BENCH_SLOTS = ("BE", "IR")


def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8")
    for c in BOOL_COLS & set(df.columns):
        df[c] = df[c].astype(str).str.lower().eq("true")
    return df


@dataclass
class Season:
    year: int
    settings: dict
    members: pd.DataFrame
    teams: pd.DataFrame
    matchups: pd.DataFrame
    draft: pd.DataFrame
    transactions: pd.DataFrame
    rosters: pd.DataFrame
    lineups: pd.DataFrame

    @property
    def team_count(self) -> int:
        return int(self.settings.get("team_count") or len(self.teams))

    @property
    def reg_weeks(self) -> int:
        return int(self.settings.get("regular_season_matchups") or 14)

    @property
    def playoff_teams(self) -> int:
        return int(self.settings.get("playoff_team_count") or 6)

    @property
    def exported_at(self) -> str:
        return str(self.settings.get("exported_at", ""))

    @property
    def is_complete(self) -> bool:
        return last_completed_week(self) >= self.reg_weeks and bool((self.teams.final_standing > 0).all())


def available_seasons(data_dir: str = DATA_DIR) -> list[int]:
    years = []
    for fn in os.listdir(data_dir):
        m = re.match(r"^(\d{4})_settings\.json$", fn)
        if m:
            years.append(int(m.group(1)))
    return sorted(years)


def load_season(year: int, data_dir: str = DATA_DIR) -> Season:
    def p(kind: str) -> str:
        return os.path.join(data_dir, f"{year}_{kind}")

    with open(p("settings.json"), encoding="utf-8") as f:
        settings = json.load(f)
    lineups = _read_csv(p("weekly_lineups.csv"))
    if not lineups.empty:
        lineups["matchup_period"] = pd.to_numeric(lineups["matchup_period"], errors="coerce").fillna(lineups["nfl_week"]).astype(int)
    matchups = _read_csv(p("matchups.csv"))
    if not matchups.empty:
        matchups["matchup_period"] = matchups["matchup_period"].astype(int)
    return Season(
        year=year,
        settings=settings,
        members=_read_csv(p("members.csv")),
        teams=_read_csv(p("teams.csv")),
        matchups=matchups,
        draft=_read_csv(p("draft.csv")),
        transactions=_read_csv(p("transactions.csv")),
        rosters=_read_csv(p("rosters.csv")),
        lineups=lineups,
    )


def load_all(data_dir: str = DATA_DIR) -> dict[int, Season]:
    return {y: load_season(y, data_dir) for y in available_seasons(data_dir)}


def last_completed_week(season: Season, regular_only: bool = True) -> int:
    """Highest week W such that every played matchup in weeks 1..W is final."""
    m = season.matchups
    if m.empty:
        return 0
    m = m[m.status != "bye"]
    if regular_only:
        m = m[m.game_type == "regular_season"]
    done = {int(w): bool((g.status == "final").all()) for w, g in m.groupby("matchup_period")}
    week = 0
    while done.get(week + 1):
        week += 1
    return week


def slot_structure(season: Season) -> dict[str, int]:
    """Starting-slot counts derived from the lineup data itself (mode per slot)."""
    l = season.lineups
    if l.empty:
        return {}
    starters = l[~l.lineup_slot.isin(BENCH_SLOTS)]
    counts = starters.groupby(["matchup_period", "team_id", "lineup_slot"]).size().reset_index(name="n")
    return {slot: int(g.n.mode().iloc[0]) for slot, g in counts.groupby("lineup_slot")}
