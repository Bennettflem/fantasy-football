import pandas as pd
from pytest import approx

from ffstats.power import (DOWN_FALLBACKS_HARSH, DOWN_FALLBACKS_MILD, FALLBACKS, HARSH_DROP,
                           POLARITY, REASON_CAP, REASONS, UP_FALLBACKS, assign_reasons,
                           power_rankings)


def test_no_more_than_two_teams_share_a_reason():
    order = [f"o{i}" for i in range(10)]
    pool = {oid: [(0.9, "hot", {"n": 3})] for oid in order}  # everyone qualifies for the same thing
    out = assign_reasons(pool, order)
    assert sum(1 for key, _ in out.values() if key == "hot") == REASON_CAP
    assert all(oid in out for oid in order)


def test_every_team_reads_differently():
    order = [f"o{i}" for i in range(10)]
    pool = {oid: [(0.9, "hot", {"n": 3}), (0.8, "cold", {"n": 2})] for oid in order}
    texts = [text for _, text in assign_reasons(pool, order).values()]
    assert len(set(texts)) == len(order)


def test_strongest_claim_wins():
    pool = {"a": [(0.5, "hot", {"n": 2}), (0.95, "points", {"pf": 130.0})], "b": []}
    key, text = assign_reasons(pool, ["a", "b"])["a"]
    assert key == "points" and "130" in text


def test_unqualified_team_gets_a_rank_appropriate_fallback():
    order = ["first", "last"]
    out = assign_reasons({"first": [], "last": []}, order)
    assert out["first"][1] == FALLBACKS[0]
    assert out["last"][0] == "fallback" and out["last"][1] != out["first"][1]


def test_climbing_teams_never_get_a_negative_blurb():
    """The whole point of the movement rule: an arrow up must not come with an insult."""
    pool = {"up": [(.9, "bench", {"b": 80.0, "e": .80}), (.5, "hot", {"n": 3})],
            "down": [(.9, "juggernaut", {"ap": "20-5"}), (.5, "cold", {"n": 2})]}
    out = assign_reasons(pool, ["up", "down"], movement={"up": 3, "down": -3})
    assert POLARITY[out["up"][0]] in ("good", "neutral"), out["up"]
    assert POLARITY[out["down"][0]] in ("bad", "neutral"), out["down"]


def test_a_flat_team_can_take_any_tone():
    pool = {"flat": [(.9, "bench", {"b": 80.0, "e": .80})]}
    assert assign_reasons(pool, ["flat"], movement={"flat": 0})["flat"][0] == "bench"
    assert assign_reasons(pool, ["flat"], movement={"flat": None})["flat"][0] == "bench"


def test_movers_with_no_matching_reason_get_a_directional_fallback():
    pool = {"up": [(.9, "cold", {"n": 4})],            # only a knock available
            "mild": [(.9, "hot", {"n": 4})],           # only praise available
            "hard": [(.9, "hot", {"n": 4})]}
    out = assign_reasons(pool, ["up", "mild", "hard"],
                         movement={"up": 2, "mild": -1, "hard": -5})
    assert out["up"][0] == "up" and out["up"][1] in UP_FALLBACKS
    assert out["mild"][0] == "down_mild" and out["mild"][1] in DOWN_FALLBACKS_MILD
    assert out["hard"][0] == "down_harsh" and out["hard"][1] in DOWN_FALLBACKS_HARSH


def test_a_bigger_drop_reads_harsher_than_a_small_one():
    pool = {"a": [], "b": []}
    out = assign_reasons(pool, ["a", "b"], movement={"a": -1, "b": -HARSH_DROP})
    assert out["a"][1] in DOWN_FALLBACKS_MILD
    assert out["b"][1] in DOWN_FALLBACKS_HARSH


def test_every_reason_key_has_a_declared_polarity():
    """A new reason with no polarity would silently default to neutral and dodge the rule."""
    assert set(REASONS) == set(POLARITY), set(REASONS) ^ set(POLARITY)


def test_real_rankings_respect_the_movement_rule(seasons, ident):
    df = power_rankings(seasons, 2101, week=2, ident=ident)
    for oid, r in df.iterrows():
        if pd.isna(r.movement) or int(r.movement) == 0:
            continue
        want = "good" if int(r.movement) > 0 else "bad"
        pol = POLARITY.get(r.why_key, "neutral")
        if r.why_key in ("up", "down_mild", "down_harsh", "fallback"):
            continue                                   # directional fallbacks carry their own tone
        assert pol in (want, "neutral"), f"{oid} moved {r.movement} but got {r.why_key}"


def test_startsit_claims_describe_the_latest_week_not_the_season(seasons, ident):
    """A manager who set a perfect lineup last week must not be told he benches points."""
    from ffstats.core import lineup_efficiency, standings, weekly_scores
    from ffstats.power import reason_pool

    season, W = seasons[2100], 4
    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    eff_df = lineup_efficiency(season, ident, W)
    season_eff = eff_df.groupby("owner_id").efficiency.mean()
    season_bench = eff_df.groupby("owner_id").bench.mean()
    last = eff_df[eff_df.week == W].set_index("owner_id")

    # A manager who was sloppy all year but perfect in week W.
    victim = season_eff.idxmin()
    patched_eff = last.efficiency.copy()
    patched_bench = last.bench.copy()
    patched_eff[victim], patched_bench[victim] = 1.0, 0.0

    comp = pd.DataFrame({"pf": 0.5, "history": 0.5}, index=st.index)
    pool = reason_pool(st, scores, comp, season_eff, season_bench,
                       pd.Series(0.0, index=st.index), pd.Series(0, index=st.index),
                       pd.Series(1, index=st.index), patched_eff, patched_bench)
    keys = {k for _, k, _ in pool[victim]}
    assert "bench" not in keys, "season-average bench leaked into a perfect week"
    assert "efficient" in keys


def test_season_long_claims_still_use_the_whole_season(seasons, ident):
    """Scoring and all-play describe accumulated play, so they must not narrow to one week."""
    from ffstats.core import lineup_efficiency, standings, weekly_scores
    from ffstats.power import reason_pool

    season, W = seasons[2100], 4
    scores = weekly_scores(season, ident, through_week=W)
    st = standings(scores)
    eff_df = lineup_efficiency(season, ident, W)
    last = eff_df[eff_df.week == W].set_index("owner_id")
    comp = pd.DataFrame({"pf": 1.0, "history": 0.5}, index=st.index)
    pool = reason_pool(st, scores, comp, eff_df.groupby("owner_id").efficiency.mean(),
                       eff_df.groupby("owner_id").bench.mean(),
                       pd.Series(0.0, index=st.index), pd.Series(0, index=st.index),
                       pd.Series(1, index=st.index), last.efficiency, last.bench)
    best = st.pf_pg.idxmax()
    pts = [f for strength, k, f in pool[best] if k == "points"]
    assert pts, "top scorer lost its season-long scoring claim"
    assert pts[0]["pf"] == approx(st.loc[best, "pf_pg"])
