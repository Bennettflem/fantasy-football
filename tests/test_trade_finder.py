from ffstats.trade_finder import (find_trades, roster_values, starting_counts, team_needs,
                                  trade_finder)


def _needs(season, ident):
    return team_needs(roster_values(season, ident), starting_counts(season))


def test_flex_slots_count_toward_rb_and_wr(seasons):
    counts = starting_counts(seasons[2101])
    assert counts["QB"] == 1
    # The fixture starts two WRs and one flex, and the flex is split between RB and WR.
    assert counts["RB"] == 1.5 and counts["WR"] == 2.5


def test_spares_are_ranked_behind_starters(seasons, ident):
    needs = _needs(seasons[2101], ident)
    ann_rb = needs[(needs.owner_id == "o1") & (needs.position == "RB")].iloc[0]
    assert ann_rb.worst_starter == 16.0                     # starts the 18 and the 16
    assert ann_rb.best_spare == 14.0                        # the 14 is on the bench


def test_finds_the_obvious_swap(seasons, ident):
    deals = find_trades(_needs(seasons[2101], ident))
    pair = deals[(deals.a == "o1") & (deals.b == "o2")]
    assert len(pair) == 1
    d = pair.iloc[0]
    assert d.a_sends_pos == "RB" and d.b_sends_pos == "WR"
    assert d.a_gain == 8.0 and d.b_gain == 10.0             # each upgrades its weakest starter
    assert d.fairness == 1.0


def test_lopsided_and_pointless_deals_are_rejected(seasons, ident):
    needs = _needs(seasons[2101], ident)
    assert find_trades(needs, min_gain=50).empty            # nothing gains 50 a game
    assert find_trades(needs, max_unfair=0.1).empty         # no two spares are that close in value


def test_injured_players_are_never_offered(seasons, ident):
    season = seasons[2101]
    r = season.rosters
    season.rosters = r.assign(injury_status=[
        "OUT" if (t == 1 and p == "Ann RB2") else s
        for t, p, s in zip(r.team_id, r.player, r.injury_status)])
    deals = find_trades(_needs(season, ident))
    assert deals.empty or deals[(deals.a == "o1") & (deals.b == "o2")].empty


def test_one_offer_per_pair(seasons, ident):
    deals = trade_finder(seasons, 2101, ident)
    assert deals.empty or not deals.duplicated(subset=["a", "b"]).any()
