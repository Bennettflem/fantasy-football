import pandas as pd

from ffstats.manager import (KNOWN_OUT_PROJ, TRADE_FULL_SWING, TRADE_FULL_WEEKS, WEIGHTS, absences,
                             draft_component,
                             hygiene_component, lineup_component, manager_score,
                             manager_score_markdown, played, trade_component, waiver_component)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_played_reads_the_stat_breakdown(seasons):
    l = seasons[2101].lineups
    flags = played(l)
    assert flags[l.points > 0].all()                      # anyone who scored, played
    assert not flags[l.player == "Ben TE"].any()          # the zero starter never played


def test_missing_column_defaults_to_played(seasons):
    l = seasons[2101].lineups.drop(columns=["stat_breakdown"])
    assert played(l).all()


def test_unexpected_absences_are_separated_from_known_outs(seasons):
    miss = absences(seasons[2101], 2)
    ben = miss[miss.player == "Ben TE"]      # projected 0: ESPN knew
    dee = miss[miss.player == "Dee TE"]      # projected 12: late scratch
    assert len(ben) == 2 and not ben.unexpected.any()
    assert len(dee) == 2 and dee.unexpected.all()


def test_draft_credits_only_the_unlucky_absence(seasons, ident):
    _, picks = draft_component(seasons[2101], ident, 2)
    dee = picks[(picks.owner_id == "o4") & (picks["round"] == 4)].iloc[0]
    assert dee.credit == 24.0                # 12 projected points across two scratched weeks
    assert dee.pts == dee.raw + 24.0
    assert picks[picks.owner_id == "o2"].credit.sum() == 0.0   # known outs earn nothing


def test_starting_a_known_out_is_an_unforced_error(seasons, ident):
    lin = lineup_component(seasons[2101], ident, 2).set_index("owner_id")
    assert lin.loc["o2", "unforced"] == 2                 # both weeks
    assert lin.loc["o4", "unforced"] == 0                 # a scratch isn't an unforced error
    assert lin.loc["o2", "process"] < lin.loc["o1", "process"]


def test_process_ignores_whether_the_call_worked_out(seasons, ident):
    lin = lineup_component(seasons[2101], ident, 2).set_index("owner_id")
    assert (lin.process <= 1.0).all() and (lin.process > 0).all()
    # Ann benched a 40-point monster that was projected for 4, so the call was right at the time.
    assert lin.loc["o1", "proj_lost"] == 0.0
    assert lin.loc["o1", "process"] == 1.0


def test_projected_points_lost_is_reported_in_points(seasons, ident):
    lin = lineup_component(seasons[2101], ident, 2).set_index("owner_id")
    assert lin.loc["o1", "proj_lost"] == 0.0
    # Ben's bench WR was projected for 4 and his tight end for 0, in both played weeks.
    assert lin.loc["o2", "proj_lost"] == 8.0


def test_waivers_net_out_drop_regret(seasons, ident):
    wire = waiver_component(seasons[2101], ident, 2).set_index("owner_id")
    assert wire.loc["o3", "wire_points"] == 15.0          # the waiver hero started and scored
    assert wire.loc["o4", "drop_regret"] == 12.0          # the player Dee dropped scored for Cy
    assert wire.loc["o4", "failed_claims"] == 1
    assert wire.loc["o3", "wire_net"] == 15.0


def test_trade_is_graded_and_cuts_both_ways(seasons, ident):
    # The players land on their new rosters in week 2, so by week 4 there are three weeks of value:
    # Ann gave up 25 a week and got back 2 a week.
    tr = trade_component(seasons[2100], ident, 4).set_index("owner_id")
    assert tr.loc["o1", "trade_net"] == -69.0
    assert tr.loc["o2", "trade_net"] == 69.0
    assert tr.loc["o1", "trades_graded"] == 1
    assert "o3" not in tr.index                           # never traded, so nothing to grade


def test_one_week_of_scoring_counts_but_only_partly(seasons, ident):
    fresh = trade_component(seasons[2100], ident, 2).set_index("owner_id")
    assert fresh.loc["o1", "trade_weeks"] == 1            # graded off a single week
    assert fresh.loc["o1", "trade_net"] == -23.0          # the raw verdict is the full week's value
    assert fresh.loc["o1", "trade_weighted"] == -23.0 / TRADE_FULL_WEEKS   # discounted for scoring it


def test_confidence_ramps_as_weeks_accumulate(seasons, ident):
    early = trade_component(seasons[2100], ident, 2).set_index("owner_id")
    later = trade_component(seasons[2100], ident, 4).set_index("owner_id")
    assert later.loc["o2", "trade_weighted"] == 69.0 * (3 / TRADE_FULL_WEEKS)
    assert later.loc["o2", "trade_weighted"] > early.loc["o2", "trade_weighted"]


def test_a_fresh_trade_moves_the_score_less_than_a_proven_one(seasons, ident):
    early = manager_score(seasons, 2100, week=2, ident=ident)
    later = manager_score(seasons, 2100, week=4, ident=ident)
    assert 0.5 > early.loc["o1", "c_trades"] > later.loc["o1", "c_trades"]


def test_non_traders_sit_neutral(seasons, ident):
    df = manager_score(seasons, 2100, week=4, ident=ident)
    assert df.loc["o3", "c_trades"] == 0.5                # neutral, not penalized
    assert df.loc["o4", "c_trades"] == 0.5
    assert df.loc["o2", "c_trades"] > 0.5                 # the trade winner gains
    assert df.loc["o1", "c_trades"] < 0.5                 # the trade loser pays


def test_a_trade_moves_the_score():
    # 23 net points is a real but bounded swing: it can't be worth more than the whole component.
    swing = (23.0 / TRADE_FULL_SWING) * WEIGHTS["trades"] * 100
    assert 0 < swing < WEIGHTS["trades"] * 100


def test_score_covers_everyone_and_stays_in_range(seasons, ident):
    df = manager_score(seasons, 2101, week=2, ident=ident)
    assert set(df.index) == {"o1", "o2", "o3", "o4"}
    assert (df.score >= 0).all() and (df.score <= 100).all()
    assert list(df["rank"]) == sorted(df["rank"])          # sorted best first
    assert df.attrs["week"] == 2


def test_luck_is_reported_but_never_scored(seasons, ident):
    df = manager_score(seasons, 2101, week=2, ident=ident)
    assert "luck" in df.columns
    assert not any(c.startswith("c_") and "luck" in c for c in df.columns)
    # The score is exactly the weighted components, so luck cannot be leaking in.
    for oid, r in df.iterrows():
        assert abs(r.score - 100 * sum(r[f"c_{k}"] * w for k, w in WEIGHTS.items())) < 1e-9


def test_hygiene_counts_dead_weight(seasons, ident):
    hyg = hygiene_component(seasons[2101], ident, 2, {"o4": 1}).set_index("owner_id")
    assert hyg.loc["o4", "failed_claims"] == 1


def test_markdown_explains_itself(seasons, ident):
    text = manager_score_markdown(manager_score(seasons, 2101, week=2, ident=ident), seasons[2101])
    assert "Manager Score" in text
    assert "decision, not the result" in text
    assert "Luck" in text
