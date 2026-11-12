"""The eye test is an opinion, but its inputs are still arithmetic, so they get pinned down.

The fixture league has no D/ST slot at all, which is deliberate here: a friend's league that
doesn't start a defense should get a ranking rather than a traceback.
"""
from __future__ import annotations

from pytest import approx

from ffstats.eye_test import (STRENGTH, WEAKNESS, WEIGHTS, WEIGHTS_EARLY, defense_points,
                              eye_test, floor_score, quality_wins, roster_talent)
from ffstats.core import weekly_scores, standings


def test_a_better_record_outranks_nearly_equal_scoring(seasons, ident):
    """Ann is 3-1 on 400 points, Ben 1-3 on 395. The eye test starts with the record."""
    df = eye_test(seasons, 2100, ident=ident, with_movement=False)
    assert df.loc["o1"]["rank"] < df.loc["o2"]["rank"]
    assert df.loc["o1"].pf_pg == approx(100.0)
    assert df.loc["o2"].pf_pg == approx(98.75)


def test_talent_is_the_best_startable_lineup_at_season_averages(seasons, ident):
    """Ann's book is RB 18/16/14, WR 6/5, QB 15, TE 8 and no kicker.

    Best lineup is QB 15 + RB 18 + WR 6 + WR 5 + flex 16 = 60, with the K slot empty because
    she doesn't roster one. The point of the assertion is that it reads `avg_points` off the
    roster snapshot, not anything the team actually started.
    """
    tal = roster_talent(seasons[2100], ident)
    assert tal.loc["o1"].talent == approx(60.0)
    assert tal.loc["o1"].best_avg == approx(18.0)
    # Ann is deep at RB and thin at WR; Dee is flat. Depth should show up as talent.
    assert tal.loc["o1"].talent > tal.loc["o4"].talent


def test_floor_is_the_mean_of_the_two_worst_weeks(seasons, ident):
    scores = weekly_scores(seasons[2100], ident)
    # Ann scored 100, 110, 130, 60. Her two worst are 60 and 100.
    assert floor_score(scores).loc["o1"] == approx(80.0)
    # Ben scored 90, 95, 70, 140 -> 70 and 90.
    assert floor_score(scores).loc["o2"] == approx(80.0)


def test_quality_of_wins_sums_the_win_rate_of_the_teams_you_beat(seasons, ident):
    """Ann beat Ben (1-3, .25), Cy (2-2, .50) and Dee (2-2, .50). That is 1.25 of credit."""
    scores = weekly_scores(seasons[2100], ident)
    st = standings(scores)
    assert quality_wins(scores, st).loc["o1"] == approx(1.25)
    # Ben's single win came against the best team in the league, so one win is worth .75.
    assert quality_wins(scores, st).loc["o2"] == approx(0.75)


def test_a_league_with_no_defense_slot_still_ranks(seasons, ident):
    """No D/ST anywhere in the fixture. The component should go flat, not explode."""
    assert defense_points(seasons[2100], ident).empty
    df = eye_test(seasons, 2100, ident=ident, with_movement=False)
    assert len(df) == 4
    assert set(df.c_defense) == {0.5}


def test_it_uses_none_of_the_power_ranking_inputs(seasons, ident):
    """All-play, luck and expected wins are absent by design, not by accident."""
    df = eye_test(seasons, 2100, ident=ident, with_movement=False)
    components = {c[2:] for c in df.columns if c.startswith("c_")}
    assert components == {"record", "talent", "quality", "defense", "floor", "momentum"}
    assert not {"all_play", "luck", "exp_wins", "ap_pct"} & set(df.columns)


def test_no_two_teams_read_alike(seasons, ident):
    df = eye_test(seasons, 2100, ident=ident, with_movement=False)
    assert len(set(df.why)) == len(df)


def test_a_superlative_line_only_goes_to_the_team_that_owns_the_component(seasons, ident):
    """"Best record in the league" has to belong to the team with the best record."""
    df = eye_test(seasons, 2100, ident=ident, with_movement=False)
    firsts = {bank[0] for bank in STRENGTH.values()} | {bank[0] for bank in WEAKNESS.values()}
    templates = {t.split("{")[0] for t in firsts}
    for oid, r in df.iterrows():
        if any(r.why.startswith(t) and t for t in templates):
            col = f"c_{r.why_key}"
            assert r[col] in (df[col].max(), df[col].min()), r.why


def test_the_weights_are_a_distribution_in_both_phases():
    assert sum(WEIGHTS.values()) == approx(1.0)
    assert sum(WEIGHTS_EARLY.values()) == approx(1.0)
    assert set(WEIGHTS) == set(WEIGHTS_EARLY)
    # Wins lead late; the roster leads while the record is still noise.
    assert max(WEIGHTS, key=WEIGHTS.get) == "record"
    assert max(WEIGHTS_EARLY, key=WEIGHTS_EARLY.get) == "talent"


def test_every_component_has_both_a_strength_and_a_weakness_phrasing():
    assert set(STRENGTH) == set(WEIGHTS)
    assert set(WEAKNESS) == set(WEIGHTS)
    for bank in list(STRENGTH.values()) + list(WEAKNESS.values()):
        assert len(bank) >= 3
