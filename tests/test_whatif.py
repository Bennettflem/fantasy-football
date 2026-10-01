from ffstats.whatif import grids, record_under, what_if


def test_own_schedule_reproduces_the_real_record(seasons, ident):
    points, opponents = grids(seasons[2100], ident)
    # Ann went 3-1, Ben 1-3 (see conftest).
    assert record_under(points, opponents, "o1", "o1") == (3, 1, 0)
    assert record_under(points, opponents, "o2", "o2") == (1, 3, 0)


def test_playing_your_own_schedule_host_swaps_in_the_host(seasons, ident):
    points, opponents = grids(seasons[2100], ident)
    # Under Ben's schedule, Ann inherits Ben's opponents; the weeks Ben played Ann become Ann vs Ben.
    w, l, t = record_under(points, opponents, "o1", "o2")
    assert w + l + t == 4
    # Week 1 Ben played Ann, so Ann plays Ben and wins 100-90; week 4 she plays Ben and loses 60-140.
    assert (w, l, t) == (3, 1, 0)


def test_nobody_plays_themselves(seasons, ident):
    points, opponents = grids(seasons[2100], ident)
    for host in ("o1", "o2", "o3", "o4"):
        w, l, t = record_under(points, opponents, "o1", host)
        assert w + l + t == 4          # every week still produces a game


def test_what_if_table_is_consistent(seasons, ident):
    df = what_if(seasons, 2100, ident=ident)
    assert len(df) == 4
    for oid, r in df.iterrows():
        assert r.actual == df.loc[oid, f"vs_{oid}"]                 # the star column is the real record
        assert r.worst_wins <= r.actual_wins <= r.best_wins
        assert abs(r.luck - (r.actual_wins - r.avg_wins)) < 1e-9
    # Every schedule is played by every owner, so total wins across the grid are conserved per column.
    assert df.avg_wins.sum() == sum(df.actual_wins)
