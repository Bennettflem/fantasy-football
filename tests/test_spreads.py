import math

from ffstats.spreads import half_point, spreads, win_probability


def test_even_teams_are_a_coin_flip():
    assert math.isclose(win_probability(110, 110, 20, 20), 0.5)


def test_better_team_is_favored_and_probabilities_complement():
    p = win_probability(130, 100, 20, 20)
    assert p > .8
    assert math.isclose(p + win_probability(100, 130, 20, 20), 1.0)


def test_more_variance_pulls_toward_even():
    tight = win_probability(130, 100, 5, 5)
    loose = win_probability(130, 100, 40, 40)
    assert tight > loose > .5


def test_half_point_rounding():
    assert half_point(3.2) == 3.0
    assert half_point(3.3) == 3.5
    assert half_point(0.1) == 0.0


def test_spreads_cover_every_game(seasons, ident):
    df = spreads(seasons, 2101, week=3, ident=ident)
    assert len(df) == 2                                   # two games a week in the fixture
    assert df.attrs["week"] == 3 and df.attrs["through"] == 2
    assert (df.p_fav >= .5).all()                         # the favorite is always the favorite
    assert (df.spread >= 0).all()
    assert not df.played.any()                            # week 3 hasn't been played
    for _, r in df.iterrows():
        assert r.fav in (r.home, r.away) and r.dog in (r.home, r.away) and r.fav != r.dog


def test_played_weeks_carry_the_result(seasons, ident):
    df = spreads(seasons, 2101, week=1, ident=ident)
    assert df.played.all()
    assert {r.home_score for _, r in df.iterrows()} == {100.0, 120.0}
