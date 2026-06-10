"""Win-probability prediction for confirmed matches, from FIFA ranking.

A transparent Elo-style heuristic on the FIFA rank gap (lower rank number =
stronger). This is a MODEL ESTIMATE, not bookmaker odds — bookmaker odds drive
the group-stage/TBD math elsewhere and are unavailable per confirmed match here.
"""

from __future__ import annotations

from backend.schema import ConfirmedTeam, MatchPrediction, Phase, TeamWinProb

# Tunable constants.
RANK_SCALE = 50.0  # larger => rank gaps matter less (flatter favourites)
MAX_DRAW = 0.30    # peak draw probability when teams are evenly matched

# Knockout phases resolve to a single winner (incl. extra time / penalties),
# so they carry no draw probability. Everything else (group stage, friendly)
# can end level.
_DECISIVE_PHASES = {
    Phase.ROUND_OF_32,
    Phase.ROUND_OF_16,
    Phase.QUARTER_FINAL,
    Phase.SEMI_FINAL,
    Phase.BRONZE_FINAL,
    Phase.FINAL,
}


def _logistic_win_shares(rank_a: int, rank_b: int) -> tuple[float, float]:
    """No-draw win shares from the rank gap; lower rank number is stronger."""
    p_a = 1.0 / (1.0 + 10.0 ** ((rank_a - rank_b) / RANK_SCALE))
    return p_a, 1.0 - p_a


def predict_from_fifa_rank(
    team_a: ConfirmedTeam, team_b: ConfirmedTeam, phase: Phase
) -> MatchPrediction:
    """Predict match outcome probabilities from the FIFA rank gap.

    Args:
        team_a: First confirmed team, including its current FIFA rank.
        team_b: Second confirmed team, including its current FIFA rank.
        phase: Tournament phase of the match (e.g. GROUP_STAGE, ROUND_OF_16).

    Returns:
        A MatchPrediction whose ``teams`` list contains two-way win shares
        derived from the logistic function on the FIFA rank gap.  For knockout
        phases (ROUND_OF_32 through FINAL) ``draw_prob`` is ``None`` because
        those legs always produce a winner.  For group-stage and friendly
        matches a draw probability is included and the three probabilities sum
        to 1.0.

    Note:
        Assumes realistic FIFA ranks (~1-211).  Extreme synthetic ranks could
        cause the ``10**x`` term to overflow to infinity.
    """
    p_a, p_b = _logistic_win_shares(team_a.fifa_rank, team_b.fifa_rank)
    if phase in _DECISIVE_PHASES:
        draw: float | None = None
    else:
        draw = MAX_DRAW * (1.0 - abs(p_a - p_b))
        p_a *= 1.0 - draw
        p_b *= 1.0 - draw
    return MatchPrediction(
        method="fifa_rank_elo",
        teams=[
            TeamWinProb(code=team_a.code, name=team_a.name, win_prob=p_a),
            TeamWinProb(code=team_b.code, name=team_b.name, win_prob=p_b),
        ],
        draw_prob=draw,
    )
