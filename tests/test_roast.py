from collections import Counter

from ffstats.roast import ROASTS, roast, roast_markdown


def test_everyone_gets_exactly_one_roast(seasons, ident):
    items = roast(seasons, 2101, week=2, ident=ident)
    assert len(items) == 4
    assert len({i["owner_id"] for i in items}) == 4
    assert all(i["line"].strip() for i in items)


def test_no_two_owners_share_a_category(seasons, ident):
    items = roast(seasons, 2101, week=2, ident=ident)
    counts = Counter(i["key"] for i in items if i["key"] != "fallback")
    assert all(n == 1 for n in counts.values())


def test_every_line_is_unique(seasons, ident):
    lines = [i["line"] for i in roast(seasons, 2101, week=2, ident=ident)]
    assert len(set(lines)) == len(lines)


def test_a_zero_in_the_lineup_gets_called_out(seasons, ident):
    # conftest gives both Ben and Dee a starter who scored zero; one of them gets the goose,
    # and because the cap is 1 the other has to be roasted for something else.
    items = {i["owner_id"]: i for i in roast(seasons, 2101, week=2, ident=ident)}
    goose = [oid for oid, i in items.items() if i["key"] == "goose"]
    assert len(goose) == 1 and goose[0] in {"o2", "o4"}
    assert "zero" in items[goose[0]]["line"]


def test_low_scorer_is_roasted_for_it(seasons, ident):
    # Week 2 scores: Ann 110, Dee 105, Ben 95, Cy 85.
    items = {i["owner_id"]: i for i in roast(seasons, 2101, week=2, ident=ident)}
    assert items["o3"]["key"] == "low"
    assert "85" in items["o3"]["line"]


def test_every_template_formats(seasons, ident):
    # A template with a typo'd field would only blow up in the week it fires; check them all now.
    fields = {"pts": 1.0, "player": "X", "bench": "B", "bpts": 1.0, "starter": "S", "spts": 1.0,
              "gap": 1.0, "k": "K", "kpts": 1.0, "qb": "Q", "qbpts": 1.0, "b": 1.0, "m": 1.0,
              "opp": "O", "opp_pts": 1.0, "proj": 1.0, "actual": 1.0, "diff": 1.0}
    for key, phrasings in ROASTS.items():
        for text in phrasings:
            assert text.format(**fields)


def test_markdown_lists_everyone(seasons, ident):
    items = roast(seasons, 2101, week=2, ident=ident)
    text = roast_markdown(items, seasons[2101], 2)
    for i in items:
        assert i["label"] in text
