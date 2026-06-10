"""Compute top-5 most-likely matchups per TBD bracket slot."""

from dataclasses import dataclass

from backend.bracket import (
    Feeder,
    FeederBestThirdPlace,
    FeederGroupRunnerUp,
    FeederGroupWinner,
    FeederQfWinner,
    FeederR32Winner,
    FeederSfLoser,
)
from backend.groups import GroupAdvanceProbs

__all__ = ["GroupAdvanceProbs", "Scenario", "Top5Result", "compute_top5_for_slot"]


@dataclass(frozen=True)
class Scenario:
    team_a_code: str
    team_b_code: str
    probability: float
    delta_pp: float


@dataclass(frozen=True)
class Top5Result:
    scenarios: list[Scenario]
    long_tail_residual: float


def _team_distribution_for_feeder(
    feeder: Feeder,
    group_probs: dict[str, GroupAdvanceProbs],
) -> dict[str, float]:
    """Map a feeder to a probability distribution over team codes."""
    if isinstance(feeder, FeederGroupWinner):
        return dict(group_probs[feeder.group].win_probs)
    if isinstance(feeder, FeederGroupRunnerUp):
        return dict(group_probs[feeder.group].runner_up_probs)
    if isinstance(feeder, FeederBestThirdPlace):
        # Real third-place distribution weighted by each eligible group's per-team
        # third-place probability. Normalize so the resulting distribution sums to 1.0
        # — interpreted as "given that this slot fills with a 3rd-placed team from
        # one of the eligible groups, here's the probability each team is the one."
        weights: dict[str, float] = {}
        total_third_mass = 0.0
        for g in feeder.eligible_groups:
            for team, prob in group_probs[g].third_place_probs.items():
                weights[team] = weights.get(team, 0.0) + prob
                total_third_mass += prob
        if total_third_mass == 0.0:
            n = len(weights) or 1
            return {t: 1.0 / n for t in weights}
        return {t: w / total_third_mass for t, w in weights.items()}
    if isinstance(feeder, (FeederR32Winner, FeederQfWinner, FeederSfLoser)):
        # Plan 1 only handles R32 slots whose feeders are group winners/runners-up.
        # Slots fed by earlier-round results require recursion through prior slots'
        # top-5 computations; deferred.
        raise NotImplementedError(f"feeder type {type(feeder).__name__} not yet supported")
    raise ValueError(f"unknown feeder: {feeder}")


def compute_top5_for_slot(
    *,
    feeders: list[Feeder],
    group_probs: dict[str, GroupAdvanceProbs],
    previous_top5: dict[tuple[str, str], float],
) -> Top5Result:
    if len(feeders) != 2:
        raise ValueError("expected exactly 2 feeders per slot")

    dist_a = _team_distribution_for_feeder(feeders[0], group_probs)
    dist_b = _team_distribution_for_feeder(feeders[1], group_probs)

    pairings: list[tuple[str, str, float]] = []
    for ta, pa in dist_a.items():
        for tb, pb in dist_b.items():
            if ta == tb:
                continue
            pairings.append((ta, tb, pa * pb))

    pairings.sort(key=lambda x: x[2], reverse=True)
    top5 = pairings[:5]
    residual = sum(p for _, _, p in pairings[5:])

    scenarios = []
    for team_a, team_b, prob in top5:
        prev = previous_top5.get((team_a, team_b), prob)
        delta_pp = (prob - prev) * 100
        scenarios.append(
            Scenario(
                team_a_code=team_a,
                team_b_code=team_b,
                probability=prob,
                delta_pp=delta_pp,
            )
        )
    return Top5Result(scenarios=scenarios, long_tail_residual=residual)
