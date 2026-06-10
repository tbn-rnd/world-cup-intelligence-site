"""Closed-form group-stage probability derivation.

Given the four teams in a group and the bookmaker odds for the six round-robin
matches, this module enumerates all 3^6 = 729 outcome combinations exactly,
applies a points-based ranking, and returns each team's probability of finishing
1st, 2nd, 3rd, or 4th.

We don't have goal-difference odds, so we use a coin-flip tiebreaker among teams
tied on points. This is approximate but defensible — head-to-head goal-difference
markets are rare and bookmakers don't offer them at scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, permutations, product

from backend.odds_client import NormalizedEvent


@dataclass(frozen=True)
class GroupAdvanceProbs:
    """Per-team probabilities for finishing in each of the four group positions."""

    win_probs: dict[str, float]
    runner_up_probs: dict[str, float]
    # Third and fourth place are only required for Plan 1.5+ usage
    # (best-third-place feeder + bracket simulation). Plan 1's
    # compute_top5_for_slot only uses win/runner_up, so these default empty.
    third_place_probs: dict[str, float] = field(default_factory=dict)
    fourth_place_probs: dict[str, float] = field(default_factory=dict)


_HOME_WIN, _DRAW, _AWAY_WIN = 0, 1, 2


def _match_outcome_probs(
    home_code: str,
    away_code: str,
    code_to_event: dict[tuple[str, str], NormalizedEvent],
) -> tuple[float, float, float]:
    """Return (home_win, draw, away_win) probabilities for the home-vs-away pairing.

    Falls back to (1/3, 1/3, 1/3) when the match has no priced event.
    """
    event = code_to_event.get((home_code, away_code))
    if event is None:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (event.home_win_prob, event.draw_prob, event.away_win_prob)


def _score_outcome(
    teams: tuple[str, ...],
    matches: list[tuple[int, int]],
    outcome: tuple[int, ...],
) -> dict[str, int]:
    """Compute per-team points for a single outcome path. 3 for win, 1 for draw."""
    points = dict.fromkeys(teams, 0)
    for (home_idx, away_idx), result in zip(matches, outcome, strict=True):
        if result == _HOME_WIN:
            points[teams[home_idx]] += 3
        elif result == _AWAY_WIN:
            points[teams[away_idx]] += 3
        else:  # draw
            points[teams[home_idx]] += 1
            points[teams[away_idx]] += 1
    return points


def _rank_groups_by_points(points: dict[str, int]) -> list[list[str]]:
    """Group teams into tiers by points descending.

    Returns a list of tiers; each tier is a list of team codes that have the
    same number of points.  Within a tier the order is arbitrary — callers
    must handle ties by splitting weight equally among all permutations.
    """
    sorted_pts = sorted(set(points.values()), reverse=True)
    tiers: list[list[str]] = []
    for pt in sorted_pts:
        tier = sorted(team for team, p in points.items() if p == pt)
        tiers.append(tier)
    return tiers


def derive_group_probs(
    *,
    group_name: str,
    teams: list[str],
    name_to_code: dict[str, str],
    events: list[NormalizedEvent],
) -> GroupAdvanceProbs:
    """Compute exact placement probabilities for a 4-team group.

    Args:
        group_name: Group identifier (e.g., "A"). Used in error messages.
        teams: List of 4 team codes (3-letter FIFA codes or TBD placeholders).
        name_to_code: Maps full team names (as they appear in Odds API responses)
            to 3-letter team codes (as they appear in `teams`).
        events: All NormalizedEvent objects from the Odds API; this function
            filters to ones that match the team list.
    """
    if len(teams) != 4:
        raise ValueError(f"group {group_name} requires exactly 4 teams, got {len(teams)}")

    teams_tuple = tuple(teams)

    # Build (home_code, away_code) → event for matches whose teams are both in this group.
    code_to_event: dict[tuple[str, str], NormalizedEvent] = {}
    for event in events:
        home_code = name_to_code.get(event.home_team)
        away_code = name_to_code.get(event.away_team)
        if home_code in teams and away_code in teams:
            code_to_event[(home_code, away_code)] = event

    # 6 unique pairings; orientation comes from the priced event we found, else default.
    pairings: list[tuple[int, int]] = []
    pairing_outcome_probs: list[tuple[float, float, float]] = []
    for i, j in combinations(range(4), 2):
        if (teams_tuple[i], teams_tuple[j]) in code_to_event:
            pairings.append((i, j))
            pairing_outcome_probs.append(
                _match_outcome_probs(teams_tuple[i], teams_tuple[j], code_to_event)
            )
        elif (teams_tuple[j], teams_tuple[i]) in code_to_event:
            pairings.append((j, i))
            pairing_outcome_probs.append(
                _match_outcome_probs(teams_tuple[j], teams_tuple[i], code_to_event)
            )
        else:
            pairings.append((i, j))
            pairing_outcome_probs.append((1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0))

    win = dict.fromkeys(teams_tuple, 0.0)
    runner_up = dict.fromkeys(teams_tuple, 0.0)
    third = dict.fromkeys(teams_tuple, 0.0)
    fourth = dict.fromkeys(teams_tuple, 0.0)

    buckets = [win, runner_up, third, fourth]

    for outcome in product([_HOME_WIN, _DRAW, _AWAY_WIN], repeat=len(pairings)):
        path_prob = 1.0
        for result, probs in zip(outcome, pairing_outcome_probs, strict=True):
            path_prob *= probs[result]

        if path_prob == 0.0:
            continue

        points = _score_outcome(teams_tuple, pairings, outcome)
        tiers = _rank_groups_by_points(points)

        # Enumerate all consistent full-rankings by permuting within each tier.
        # Split path_prob equally across all such permutations so that teams
        # tied on points each receive a fair share.
        full_rankings: list[list[str]] = [[]]
        for tier in tiers:
            expanded: list[list[str]] = []
            for perm in permutations(tier):
                for prefix in full_rankings:
                    expanded.append(prefix + list(perm))
            full_rankings = expanded

        share = path_prob / len(full_rankings)
        for ranking in full_rankings:
            for pos, bucket in enumerate(buckets):
                bucket[ranking[pos]] += share

    return GroupAdvanceProbs(
        win_probs=win,
        runner_up_probs=runner_up,
        third_place_probs=third,
        fourth_place_probs=fourth,
    )
