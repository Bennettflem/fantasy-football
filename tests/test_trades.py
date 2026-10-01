from ffstats.trades import (evidence_for, infer_trades, logged_legs, player_moves, trade_history,
                            trade_history_markdown)


def test_detects_players_changing_rosters(seasons, ident):
    moves = player_moves(seasons[2100], ident)
    by_player = {m.player: (m.from_team_id, m.to_team_id, m.week) for _, m in moves.iterrows()}
    assert by_player["Traded Star"] == (1, 2, 2)
    assert by_player["Traded Dud"] == (2, 1, 2)


def test_waiver_pickups_are_not_moves(seasons, ident):
    # The waiver hero joins Cy in week 2 with an ADD in the transaction log, so he isn't a move.
    moves = player_moves(seasons[2100], ident)
    assert "Waiver Hero" not in set(moves.player)


def test_one_way_moves_are_not_trades(seasons, ident):
    # Dee's dropped player turns up on Cy's roster with nothing going back: an unlogged pickup.
    legs = infer_trades(seasons[2100], ident)
    assert "Dee bench WR" not in set(legs.player)
    assert "Dee bench WR" in {m["player"] for m in legs.attrs["one_way"]}


def test_a_trade_needs_both_directions(seasons, ident):
    legs = infer_trades(seasons[2100], ident)
    assert set(legs.player) == {"Traded Star", "Traded Dud"}
    assert legs.trade_id.nunique() == 1
    g = legs[legs.trade_id == legs.trade_id.iloc[0]]
    assert set(g.from_owner) == {"o1", "o2"}          # players crossed in both directions
    assert set(g.week) == {2}


def test_evidence_grades_how_well_espn_backs_it_up():
    assert evidence_for({"TRADE_ACCEPT"}) == "accepted"
    assert evidence_for({"TRADE_UPHOLD", "TRADE_PROPOSAL"}) == "accepted"
    assert evidence_for({"TRADE_PROPOSAL"}) == "proposal"
    assert evidence_for({"TRADE_VETO"}) == "proposal"   # an offer existed, but not a completed swap
    assert evidence_for(set()) == "roster only"


def test_logged_legs_reads_the_transaction_log(seasons, ident):
    # The fixture logs the trade as TRADE_ACCEPT, so both legs should corroborate.
    legs = logged_legs(seasons[2100], ident)
    assert any("TRADE_ACCEPT" in kinds for kinds in legs.values())


def test_history_spans_seasons_and_renders(seasons, ident):
    legs = trade_history(seasons, ident)
    assert set(legs.season) == {2100, 2101}
    text = trade_history_markdown(legs, ident)
    assert "Traded Star" in text
    assert "Trade History" in text
    assert "one-way moves" in text                     # the exclusions are disclosed, not hidden
