from __future__ import annotations

import math

import pandas as pd

from .beer_mile import american_odds
from .core import record_str, scoring_profile, standings, weekly_scores
from .data import Season, last_completed_week
from .identity import Identity
from .power import prior_seasons
from .render import pct, table


def win_probability(mu_a: float, mu_b: float, sd_a: float, sd_b: float) -> float:
    """P(A outscores B) for two independent normal scores."""
    spread = math.sqrt(sd_a ** 2 + sd_b ** 2)
    if spread <= 0:
        return 1.0 if mu_a > mu_b else (0.0 if mu_a < mu_b else 0.5)
    return 0.5 * (1 + math.erf((mu_a - mu_b) / (spread * math.sqrt(2))))


def half_point(x: float) -> float:
    return round(x * 2) / 2


def spreads(seasons: dict[int, Season], year: int, week: int | None = None,
            ident: Identity | None = None) -> pd.DataFrame:
    """Betting lines for one week's games. Defaults to the next week that hasn't been played."""
    ident = ident or Identity(seasons)
    season = seasons[year]
    done = last_completed_week(season)
    W = week if week is not None else done + 1
    games = season.matchups[(season.matchups.matchup_period == W) & (season.matchups.away_team != "BYE")]
    if games.empty:
        raise ValueError(f"No matchups scheduled for {year} week {W}.")
    prof = scoring_profile(season, ident, done, prior_seasons(seasons, year))
    st = standings(weekly_scores(season, ident, through_week=done)) if done else pd.DataFrame()

    rows = []
    for _, g in games.iterrows():
        h = ident.team_owner.get((year, int(g.home_team_id)), "")
        a = ident.team_owner.get((year, int(g.away_team_id)), "")
        if not h or not a or h not in prof.index or a not in prof.index:
            continue
        mh, sh = float(prof.loc[h, "mu"]), float(prof.loc[h, "sigma"])
        ma, sa = float(prof.loc[a, "mu"]), float(prof.loc[a, "sigma"])
        p_home = win_probability(mh, ma, sh, sa)
        fav, dog, p_fav = (h, a, p_home) if p_home >= .5 else (a, h, 1 - p_home)
        rows.append({
            "week": W, "home": h, "away": a, "fav": fav, "dog": dog,
            "spread": half_point(abs(mh - ma)), "total": half_point(mh + ma),
            "p_fav": p_fav, "fav_ml": american_odds(p_fav), "dog_ml": american_odds(1 - p_fav),
            "home_rec": record_str(st.loc[h]) if h in getattr(st, "index", []) else "0-0",
            "away_rec": record_str(st.loc[a]) if a in getattr(st, "index", []) else "0-0",
            "played": g.status == "final",
            "home_score": float(g.home_score), "away_score": float(g.away_score),
        })
    df = pd.DataFrame(rows)
    df.attrs["week"] = W
    df.attrs["through"] = done
    return df


def spreads_markdown(df: pd.DataFrame, season: Season, ident: Identity) -> str:
    W = df.attrs["week"]
    short = lambda o: ident.short(o)
    rows = []
    for _, r in df.iterrows():
        line = f"{short(r.fav)} -{r.spread:g}" if r.spread else "PK"
        row = {"Matchup": f"{short(r.away)} ({r.away_rec}) at {short(r.home)} ({r.home_rec})",
               "Line": line, "Total": f"{r.total:g}", "Favorite win prob": pct(r.p_fav),
               "Moneyline": f"{short(r.fav)} {r.fav_ml} / {short(r.dog)} {r.dog_ml}"}
        if r.played:
            won = r.home if r.home_score > r.away_score else r.away
            row["Result"] = f"{short(won)} won {max(r.home_score, r.away_score):.1f}-{min(r.home_score, r.away_score):.1f}"
        rows.append(row)
    return "\n".join([
        f"## Week {W} Spreads: {season.year}",
        "",
        table(rows),
        "",
        f"_Lines from each team's scoring distribution through week {df.attrs['through']}, shrunk toward its "
        "prior-season average. Win probability assumes independent normal scores; moneylines are the fair "
        "price with no juice._",
    ])
