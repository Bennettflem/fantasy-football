from __future__ import annotations

import numpy as np
import pandas as pd

from .core import default_week, record_str, scoring_profile, standings, weekly_scores
from .data import Season
from .identity import Identity
from .power import prior_seasons
from .render import pct, table

SIMS = 5000


def remaining_schedule(season: Season, ident: Identity, after_week: int) -> list[tuple[int, str, str]]:
    """Regular-season games not yet played, as (week, home_owner, away_owner)."""
    m = season.matchups
    if m.empty:
        return []
    left = m[(m.game_type == "regular_season") & (m.status != "final") & (m.away_team != "BYE")
             & (m.matchup_period > after_week) & (m.matchup_period <= season.reg_weeks)]
    out = []
    for _, g in left.iterrows():
        h = ident.team_owner.get((season.year, int(g.home_team_id)), "")
        a = ident.team_owner.get((season.year, int(g.away_team_id)), "")
        if h and a:
            out.append((int(g.matchup_period), h, a))
    return out


def _bracket(order: np.ndarray, seeds: np.ndarray, playoff_teams: int, play) -> np.ndarray | None:
    """Single-elimination bracket with byes, reseeded each round. Returns the champion per sim.

    `order[:, k]` is the team holding seed k+1. Supported field sizes cover every common league
    shape; anything else returns None rather than inventing a format.
    """
    def seed_of(team: np.ndarray) -> np.ndarray:
        return np.take_along_axis(seeds, team[:, None], axis=1).ravel()

    def reseed(*teams: np.ndarray) -> list[np.ndarray]:
        """Best remaining seed first."""
        stacked = np.stack(teams, axis=1)
        keys = np.stack([seed_of(t) for t in teams], axis=1)
        picks = np.argsort(keys, axis=1)
        return [np.take_along_axis(stacked, picks[:, k:k + 1], axis=1).ravel() for k in range(len(teams))]

    if playoff_teams == 2:
        return play(order[:, 0], order[:, 1])
    if playoff_teams == 4:
        a, b = play(order[:, 0], order[:, 3]), play(order[:, 1], order[:, 2])
        return play(*reseed(a, b))
    if playoff_teams == 6:                      # seeds 1-2 get byes
        a, b = play(order[:, 2], order[:, 5]), play(order[:, 3], order[:, 4])
        low, high = reseed(a, b)                # best remaining faces the 2 seed
        s1, s2 = play(order[:, 0], high), play(order[:, 1], low)
        return play(*reseed(s1, s2))
    if playoff_teams == 8:
        quarters = [play(order[:, k], order[:, 7 - k]) for k in range(4)]
        semis = reseed(*quarters)
        s1 = play(semis[0], semis[3])
        s2 = play(semis[1], semis[2])
        return play(*reseed(s1, s2))
    return None


def simulate(owners: list[str], wins: dict[str, float], pf: dict[str, float],
             schedule: list[tuple[int, str, str]], mu: dict[str, float], sigma: dict[str, float],
             playoff_teams: int, sims: int = SIMS, seed: int = 0,
             round_weeks: int = 1) -> pd.DataFrame:
    """Monte Carlo the rest of the regular season. Pure: no data loading, seeded, so tests can pin it."""
    idx = {o: i for i, o in enumerate(owners)}
    n = len(owners)
    rng = np.random.default_rng(seed)
    W = np.tile(np.array([float(wins[o]) for o in owners]), (sims, 1))
    P = np.tile(np.array([float(pf[o]) for o in owners]), (sims, 1))
    for _, h, a in schedule:
        i, j = idx[h], idx[a]
        sh = rng.normal(mu[h], sigma[h], sims)
        sa = rng.normal(mu[a], sigma[a], sims)
        W[:, i] += sh > sa
        W[:, j] += sa > sh
        P[:, i] += sh
        P[:, j] += sa
    key = W + P / 1e6  # wins, then total points, matching ESPN's seeding tiebreak
    order = np.argsort(-key, axis=1)
    seeds = np.empty_like(order)
    np.put_along_axis(seeds, order, np.tile(np.arange(1, n + 1), (sims, 1)), axis=1)

    mus = np.array([mu[o] for o in owners]) * round_weeks
    sds = np.array([sigma[o] for o in owners]) * np.sqrt(round_weeks)

    def play(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """One playoff game per sim between two arrays of team indices."""
        return np.where(rng.normal(mus[a], sds[a]) > rng.normal(mus[b], sds[b]), a, b)

    champ = _bracket(order, seeds, playoff_teams, play) if n >= playoff_teams else None
    title = np.zeros(n)
    if champ is not None:
        title = np.bincount(champ, minlength=n) / sims

    return pd.DataFrame({
        "playoff_pct": (seeds <= playoff_teams).mean(axis=0),
        "bye_pct": (seeds <= max(1, 2 * playoff_teams - n)).mean(axis=0),
        "seed1_pct": (seeds == 1).mean(axis=0),
        "title_pct": title,
        "last_pct": (seeds == n).mean(axis=0),
        "proj_wins": W.mean(axis=0),
        "avg_seed": seeds.mean(axis=0),
    }, index=owners)


def playoff_odds(seasons: dict[int, Season], year: int, week: int | None = None,
                 ident: Identity | None = None, sims: int = SIMS, seed: int = 0) -> pd.DataFrame:
    ident = ident or Identity(seasons)
    season = seasons[year]
    W = default_week(season, week)
    st = standings(weekly_scores(season, ident, through_week=W))
    prof = scoring_profile(season, ident, W, prior_seasons(seasons, year))
    owners = list(st.index)
    sched = remaining_schedule(season, ident, W)
    out = simulate(
        owners,
        {o: st.loc[o, "W"] + 0.5 * st.loc[o, "T"] for o in owners},
        {o: st.loc[o, "PF"] for o in owners},
        sched,
        {o: float(prof.loc[o, "mu"]) for o in owners},
        {o: float(prof.loc[o, "sigma"]) for o in owners},
        season.playoff_teams, sims, seed,
        int(season.settings.get("playoff_matchup_period_length_weeks") or 1),
    )
    out["label"] = [ident.label(o, year) for o in owners]
    out["record"] = [record_str(st.loc[o]) for o in owners]
    out["pf_pg"] = [st.loc[o, "pf_pg"] for o in owners]
    out["espn_pct"] = [_espn_pct(season, ident, year, o) for o in owners]
    out.attrs["week"] = W
    out.attrs["games_left"] = len(sched)
    out.attrs["sims"] = sims
    return out.sort_values(["playoff_pct", "proj_wins"], ascending=False)


def _espn_pct(season: Season, ident: Identity, year: int, oid: str) -> float:
    t = season.teams
    if t.empty or "playoff_pct_espn_sim" not in t.columns:
        return float("nan")
    tid = ident.owner_team_id.get((year, oid))
    row = t[t.team_id == tid]
    return float(row.playoff_pct_espn_sim.iloc[0]) if len(row) else float("nan")


def playoff_odds_markdown(df: pd.DataFrame, season: Season) -> str:
    W, left = df.attrs["week"], df.attrs["games_left"]
    rows = []
    for _, r in df.iterrows():
        espn = "" if pd.isna(r.espn_pct) else f"{r.espn_pct:.0f}%"
        diff = "" if pd.isna(r.espn_pct) else f"{100 * r.playoff_pct - r.espn_pct:+.0f}"
        rows.append({"Team (Owner)": r.label, "Record": r.record, "PF/G": f"{r.pf_pg:.1f}",
                     "Playoffs": pct(r.playoff_pct), "Bye": pct(r.bye_pct), "#1 seed": pct(r.seed1_pct),
                     "Title": pct(r.title_pct), "Last": pct(r.last_pct),
                     "Proj wins": f"{r.proj_wins:.1f}", "ESPN": espn, "vs ESPN": diff})
    return "\n".join([
        f"## Playoff Odds: {season.year}, through week {W}",
        "",
        table(rows),
        "",
        f"_{df.attrs['sims']:,} simulations of the {left} remaining regular-season games **and the "
        f"playoff bracket**. Each team's weekly score is drawn from its own scoring distribution "
        f"(shrunk toward its prior-season average early on). Seeding uses wins, then total points; "
        f"the top {season.playoff_teams} make the playoffs and the bracket reseeds each round._",
    ])
