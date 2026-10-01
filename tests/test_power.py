from ffstats.power import FALLBACKS, REASON_CAP, assign_reasons


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
