from ffstats.manager import WEIGHTS, career_manager_score, career_manager_score_markdown, manager_score


def test_career_covers_every_owner_and_season(seasons, ident):
    df = career_manager_score(seasons, ident)
    assert set(df.index) == {"o1", "o2", "o3", "o4"}
    assert df.attrs["years"] == [2100, 2101]
    assert df.attrs["weeks"] == {2100: 4, 2101: 2}       # 2101 is only two weeks in
    assert list(df["rank"]) == sorted(df["rank"])


def test_seasons_are_weighted_by_weeks_played(seasons, ident):
    df = career_manager_score(seasons, ident)
    full, partial = manager_score(seasons, 2100, None, ident), manager_score(seasons, 2101, None, ident)
    for oid in df.index:
        expected = (full.loc[oid, "c_draft"] * 4 + partial.loc[oid, "c_draft"] * 2) / 6
        assert abs(df.loc[oid, "c_draft"] - expected) < 1e-9
        assert df.loc[oid, "weeks"] == 6


def test_score_is_the_weighted_components(seasons, ident):
    df = career_manager_score(seasons, ident)
    for _, r in df.iterrows():
        assert abs(r.score - 100 * sum(r[f"c_{k}"] * w for k, w in WEIGHTS.items())) < 1e-9


def test_raw_columns_are_career_totals(seasons, ident):
    df = career_manager_score(seasons, ident)
    full, partial = manager_score(seasons, 2100, None, ident), manager_score(seasons, 2101, None, ident)
    for oid in df.index:
        assert abs(df.loc[oid, "luck"] - (full.loc[oid, "luck"] + partial.loc[oid, "luck"])) < 1e-9
        assert df.loc[oid, "unforced"] == full.loc[oid, "unforced"] + partial.loc[oid, "unforced"]


def test_markdown_names_the_span(seasons, ident):
    text = career_manager_score_markdown(career_manager_score(seasons, ident))
    assert "all time" in text
    assert "2101 (2w)" in text                           # the partial season is disclosed
