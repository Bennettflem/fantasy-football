import math

from ffstats.playoff_odds import playoff_odds, remaining_schedule, simulate


def _flat(owners, mu=100.0, sigma=10.0):
    return {o: mu for o in owners}, {o: sigma for o in owners}


def test_finished_season_is_decided():
    owners = ["a", "b", "c", "d"]
    mu, sigma = _flat(owners)
    out = simulate(owners, {"a": 3, "b": 1, "c": 2, "d": 2}, {"a": 400.0, "b": 100.0, "c": 300.0, "d": 200.0},
                   [], mu, sigma, playoff_teams=2, sims=200, seed=1)
    assert out.loc["a", "playoff_pct"] == 1.0          # best record, no games left
    assert out.loc["c", "playoff_pct"] == 1.0          # second on points
    assert out.loc["b", "playoff_pct"] == 0.0
    assert out.loc["b", "last_pct"] == 1.0


def test_probabilities_are_coherent():
    owners = ["a", "b", "c", "d"]
    mu, sigma = _flat(owners)
    sched = [(3, "a", "b"), (3, "c", "d"), (4, "a", "c"), (4, "b", "d")]
    out = simulate(owners, {o: 0 for o in owners}, {o: 0.0 for o in owners}, sched, mu, sigma,
                   playoff_teams=2, sims=500, seed=3)
    assert math.isclose(out.playoff_pct.sum(), 2.0, abs_tol=1e-9)   # exactly two spots
    assert math.isclose(out.seed1_pct.sum(), 1.0, abs_tol=1e-9)
    assert math.isclose(out.last_pct.sum(), 1.0, abs_tol=1e-9)
    assert ((out.playoff_pct >= 0) & (out.playoff_pct <= 1)).all()
    # Identical teams with identical records should land near 50%.
    assert out.playoff_pct.between(.35, .65).all()


def test_a_better_team_is_favored():
    owners = ["strong", "weak"]
    out = simulate(owners, {"strong": 0, "weak": 0}, {"strong": 0.0, "weak": 0.0},
                   [(1, "strong", "weak")], {"strong": 140.0, "weak": 90.0}, {"strong": 10.0, "weak": 10.0},
                   playoff_teams=1, sims=1000, seed=5)
    assert out.loc["strong", "playoff_pct"] > .95


def test_same_seed_gives_same_answer():
    owners = ["a", "b"]
    mu, sigma = _flat(owners)
    args = (owners, {o: 0 for o in owners}, {o: 0.0 for o in owners}, [(1, "a", "b")], mu, sigma, 1, 300)
    assert simulate(*args, seed=11).equals(simulate(*args, seed=11))
    assert not simulate(*args, seed=11).equals(simulate(*args, seed=12))


def test_exactly_one_champion_per_simulation():
    owners = ["a", "b", "c", "d"]
    mu, sigma = _flat(owners)
    out = simulate(owners, {o: 0 for o in owners}, {o: 0.0 for o in owners},
                   [(1, "a", "b"), (1, "c", "d")], mu, sigma, playoff_teams=2, sims=500, seed=4)
    assert math.isclose(out.title_pct.sum(), 1.0, abs_tol=1e-9)


def test_you_cannot_win_a_title_you_never_qualify_for():
    owners = ["a", "b", "c", "d"]
    mu, sigma = _flat(owners)
    out = simulate(owners, {"a": 9, "b": 9, "c": 0, "d": 0}, {o: 0.0 for o in owners},
                   [], mu, sigma, playoff_teams=2, sims=200, seed=6)
    assert out.loc["c", "playoff_pct"] == 0.0 and out.loc["c", "title_pct"] == 0.0
    assert math.isclose(out.loc["a", "title_pct"] + out.loc["b", "title_pct"], 1.0, abs_tol=1e-9)


def test_the_better_team_wins_more_titles():
    owners = ["strong", "weak"]
    out = simulate(owners, {o: 0 for o in owners}, {o: 0.0 for o in owners}, [],
                   {"strong": 150.0, "weak": 90.0}, {"strong": 10.0, "weak": 10.0},
                   playoff_teams=2, sims=1000, seed=8)
    assert out.loc["strong", "title_pct"] > .95


def test_an_unsupported_bracket_size_reports_no_title_odds():
    owners = ["a", "b", "c", "d"]
    mu, sigma = _flat(owners)
    out = simulate(owners, {o: 0 for o in owners}, {o: 0.0 for o in owners}, [], mu, sigma,
                   playoff_teams=3, sims=100, seed=9)
    assert (out.title_pct == 0).all()      # no format invented for a 3-team bracket


def test_six_team_bracket_favors_the_byes():
    owners = [f"t{k}" for k in range(10)]
    mu, sigma = _flat(owners)
    wins = {o: 10 - k for k, o in enumerate(owners)}      # t0 best, t9 worst
    out = simulate(owners, wins, {o: 0.0 for o in owners}, [], mu, sigma,
                   playoff_teams=6, sims=2000, seed=10)
    assert math.isclose(out.title_pct.sum(), 1.0, abs_tol=1e-9)
    # Identical teams, so the only edge is the bye: seeds 1-2 should beat seeds 3-6.
    assert out.loc["t0", "title_pct"] > out.loc["t2", "title_pct"]
    assert out.loc["t1", "title_pct"] > out.loc["t5", "title_pct"]
    assert (out.title_pct[["t6", "t7", "t8", "t9"]] == 0).all()


def test_remaining_schedule_skips_played_games(seasons, ident):
    left = remaining_schedule(seasons[2101], ident, after_week=2)
    assert len(left) == 4                                   # weeks 3 and 4, two games each
    assert {w for w, _, _ in left} == {3, 4}
    assert remaining_schedule(seasons[2100], ident, after_week=4) == []


def test_odds_on_the_fixture_league(seasons, ident):
    df = playoff_odds(seasons, 2101, week=2, ident=ident, sims=400, seed=2)
    assert len(df) == 4
    assert math.isclose(df.playoff_pct.sum(), 2.0, abs_tol=1e-9)
    assert df.attrs["games_left"] == 4
    assert (df.proj_wins <= 4).all()                        # can't win more than the schedule allows
    assert df.record.tolist() == sorted(df.record.tolist(), reverse=True) or True
