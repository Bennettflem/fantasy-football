import pandas as pd
from pytest import approx

from ffstats.draft_grades import (curve_grade, draft_grades, draft_grades_markdown,
                                  replacement_levels, season_grades)


def test_curve_spans_the_alphabet():
    grades = [curve_grade(i, 10) for i in range(1, 11)]
    assert grades[0] == "A+"
    assert grades[-1] == "F"
    assert set(grades) >= {"A+", "A", "B", "C", "D", "F"}
    assert curve_grade(1, 1) == "A+"        # a one-team league doesn't divide by zero


def test_replacement_level_is_the_last_startable_player():
    picks = pd.DataFrame({"position": ["RB"] * 6, "pts": [300.0, 250.0, 200.0, 150.0, 100.0, 50.0]})
    # Two teams starting 2 RBs each means the 4th RB is the last starter.
    levels = replacement_levels(picks, {"RB": 2}, team_count=2)
    assert levels["RB"] == approx(sum([150.0, 100.0, 50.0]) / 3)


def test_replacement_falls_back_when_the_pool_is_short():
    picks = pd.DataFrame({"position": ["QB"] * 2, "pts": [300.0, 200.0]})
    levels = replacement_levels(picks, {"QB": 1}, team_count=10)   # wants the 10th QB, only 2 exist
    assert levels["QB"] == 200.0


def test_position_scarcity_changes_the_grade():
    # Same raw points at different positions should not score the same.
    picks = pd.DataFrame({"position": ["QB", "QB", "RB", "RB"], "pts": [300.0, 290.0, 300.0, 100.0]})
    levels = replacement_levels(picks, {"QB": 1, "RB": 1}, team_count=2)
    assert levels["QB"] > levels["RB"]      # quarterbacks are deeper, so they're worth less


def test_best_drafter_wins_the_season(seasons, ident):
    rep = season_grades(seasons[2100], ident)
    rows = {r["owner_id"]: r for r in rep["rows"]}
    assert rows["o1"]["grade"] == "A+"      # conftest gives Ann the best picks
    assert rows["o2"]["grade"] == "F"       # and Ben the worst
    assert rows["o1"]["vor"] > rows["o2"]["vor"]
    assert len(rep["redraft"]) == 10


def test_every_season_is_graded(seasons, ident):
    reports = draft_grades(seasons, ident=ident)
    assert [r["year"] for r in reports] == [2100, 2101]
    text = draft_grades_markdown(reports, ident)
    assert "All-time drafting" in text
    assert "season in progress" in text     # 2101 isn't finished
