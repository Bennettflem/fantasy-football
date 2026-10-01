import pytest

from ffstats.rivalry import meetings, rivalry, rivalry_markdown, upcoming_game


def test_meetings_span_every_season(seasons, ident):
    games = meetings(seasons, "o1", "o2", ident)
    # Ann and Ben play in weeks 1 and 4 of 2100, and week 1 of 2101 (week 4 hasn't been played).
    assert len(games) == 3
    assert list(games.year) == [2100, 2100, 2101]
    assert list(games.week) == [1, 4, 1]
    assert list(games.a_score) == [100.0, 60.0, 100.0]
    assert list(games.winner) == ["o1", "o2", "o1"]


def test_meetings_are_symmetric(seasons, ident):
    ab = meetings(seasons, "o1", "o2", ident)
    ba = meetings(seasons, "o2", "o1", ident)
    assert list(ab.a_score) == list(ba.b_score)
    assert list(ab.winner) == list(ba.winner)


def test_series_record_and_streak(seasons, ident):
    rep = rivalry(seasons, ident, "Ann", "Ben")
    assert rep["record"] == (2, 1, 0)
    assert rep["streak"]["current_type"] == "W"      # Ann won the most recent meeting
    assert rep["biggest"].margin == 80.0             # 140-60 in 2100 week 4
    assert rep["closest"].margin == 10.0


def test_no_names_previews_the_next_week(seasons, ident):
    a, b, week = upcoming_game(seasons, 2101, ident)
    assert week == 3                                  # weeks 1-2 are played
    assert {a, b} <= {"o1", "o2", "o3", "o4"} and a != b
    rep = rivalry(seasons, ident, year=2101)
    assert rep["upcoming_week"] == 3
    assert "form" in rep


def test_one_name_is_rejected(seasons, ident):
    with pytest.raises(ValueError):
        rivalry(seasons, ident, "Ann")


def test_markdown_names_the_leader(seasons, ident):
    text = rivalry_markdown(rivalry(seasons, ident, "Ann", "Ben"), ident)
    assert "Ann leads 2-1" in text
    assert "Every meeting" in text
