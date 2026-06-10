"""Bracket-wide Monte Carlo simulator for TBD knockout slots.

Given group-stage placement probabilities, repeatedly:
  1. Sample group winners and runners-up
  2. Sample best-third-place teams from eligible groups
  3. Walk every R32 slot (all 16) and coin-flip to advance to R16
  4. Walk every R16 slot (all 8) and coin-flip to advance to QF
  5. Walk every QF slot (all 4) and coin-flip to advance to SF
  6. Walk both SF slots and resolve Final + Bronze from winners/losers

Aggregating across iterations gives a probability distribution over team
pairings at each slot. The `top_matchups(k)` helper returns the k most-likely.

Knockout matches are 50/50 because we don't have head-to-head odds for
arbitrary future matchups. This is a deliberate calibration choice — it
keeps the output honest about which teams *reach* a slot rather than
overclaiming about who would *win* once there.

The simulation is deterministic given the rng seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from backend.groups import GroupAdvanceProbs

# Spec for one feeder side of an R32 slot.
# ("group_winner", "A") or ("group_runner_up", "F") or ("best_third", ("A","B",...))
_FeederSpec = (
    tuple[Literal["group_winner"], str]
    | tuple[Literal["group_runner_up"], str]
    | tuple[Literal["best_third"], tuple[str, ...]]
)

# 2026 R32 → (left feeder, right feeder) spec per the published 2026 bracket.
# All 16 slots are tracked uniformly. Sourced from knowledge/bracket_2026.yaml.
_R32_SLOT_SPECS: dict[str, tuple[_FeederSpec, _FeederSpec]] = {
    "r32_match_73": (("group_runner_up", "A"), ("group_runner_up", "B")),
    "r32_match_74": (("group_winner", "E"), ("best_third", ("A", "B", "C", "D", "F"))),
    "r32_match_75": (("group_winner", "F"), ("group_runner_up", "C")),
    "r32_match_76": (("group_winner", "C"), ("group_runner_up", "F")),
    "r32_match_77": (("group_winner", "I"), ("best_third", ("C", "D", "F", "G", "H"))),
    "r32_match_78": (("group_runner_up", "E"), ("group_runner_up", "I")),
    "r32_match_79": (("group_winner", "A"), ("best_third", ("C", "E", "F", "H", "I"))),
    "r32_match_80": (("group_winner", "L"), ("best_third", ("E", "H", "I", "J", "K"))),
    "r32_match_81": (("group_winner", "D"), ("best_third", ("B", "E", "F", "I", "J"))),
    "r32_match_82": (("group_winner", "G"), ("best_third", ("A", "E", "H", "I", "J"))),
    "r32_match_83": (("group_runner_up", "K"), ("group_runner_up", "L")),
    "r32_match_84": (("group_winner", "H"), ("group_runner_up", "J")),
    "r32_match_85": (("group_winner", "B"), ("best_third", ("E", "F", "G", "I", "J"))),
    "r32_match_86": (("group_winner", "J"), ("group_runner_up", "H")),
    "r32_match_87": (("group_winner", "K"), ("best_third", ("D", "E", "I", "J", "L"))),
    "r32_match_88": (("group_runner_up", "D"), ("group_runner_up", "G")),
}

# 2026 R16 → (left R32 parent, right R32 parent) per the published bracket tree.
_R16_SLOT_PARENTS: dict[str, tuple[str, str]] = {
    "r16_match_89": ("r32_match_74", "r32_match_77"),
    "r16_match_90": ("r32_match_73", "r32_match_75"),
    "r16_match_91": ("r32_match_76", "r32_match_78"),
    "r16_match_92": ("r32_match_79", "r32_match_80"),
    "r16_match_93": ("r32_match_83", "r32_match_84"),
    "r16_match_94": ("r32_match_81", "r32_match_82"),
    "r16_match_95": ("r32_match_86", "r32_match_88"),
    "r16_match_96": ("r32_match_85", "r32_match_87"),
}

# 2026 QF → (left R16 parent, right R16 parent).
_QF_SLOT_PARENTS: dict[str, tuple[str, str]] = {
    "qf_match_97": ("r16_match_89", "r16_match_90"),
    "qf_match_98": ("r16_match_93", "r16_match_94"),
    "qf_match_99": ("r16_match_91", "r16_match_92"),
    "qf_match_100": ("r16_match_95", "r16_match_96"),
}

# 2026 SF → (left QF parent, right QF parent).
_SF_SLOT_PARENTS: dict[str, tuple[str, str]] = {
    "sf_match_101": ("qf_match_97", "qf_match_98"),
    "sf_match_102": ("qf_match_99", "qf_match_100"),
}

# Final = winners of both SFs. Bronze = losers of both SFs.
_FINAL_SLOT = "final_match_104"
_BRONZE_SLOT = "bronze_match_103"
_SF_SLOTS_IN_ORDER: tuple[str, str] = ("sf_match_101", "sf_match_102")


@dataclass
class SlotMatchupCounts:
    """Histogram of matchup occurrences at one slot across simulation iterations."""

    matchup_count: dict[tuple[str, str], int] = field(default_factory=dict)
    winner_count: dict[str, int] = field(default_factory=dict)

    def record(self, team_a: str, team_b: str) -> None:
        # Canonical ordering so MEX-JPN and JPN-MEX collapse into one bucket.
        key: tuple[str, str] = (team_a, team_b) if team_a < team_b else (team_b, team_a)
        self.matchup_count[key] = self.matchup_count.get(key, 0) + 1

    def record_winner(self, team: str) -> None:
        self.winner_count[team] = self.winner_count.get(team, 0) + 1

    def top_matchups(self, k: int) -> list[tuple[tuple[str, str], float]]:
        total = sum(self.matchup_count.values())
        if total == 0:
            return []
        ranked = sorted(self.matchup_count.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [(matchup, count / total) for matchup, count in ranked]

    def top_winners(self, k: int) -> list[tuple[str, float]]:
        total = sum(self.winner_count.values())
        if total == 0:
            return []
        ranked = sorted(self.winner_count.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [(team, count / total) for team, count in ranked]


def _sample_from_distribution(
    distribution: dict[str, float],
    rng: random.Random,
) -> str:
    items = list(distribution.items())
    if not items:
        return "TBD"
    weights = [w for _, w in items]
    total = sum(weights)
    if total <= 0.0:
        return rng.choice([code for code, _ in items])
    return rng.choices([code for code, _ in items], weights=weights, k=1)[0]


def _sample_best_third(
    eligible_groups: tuple[str, ...],
    group_probs: dict[str, GroupAdvanceProbs],
    rng: random.Random,
    excluded: set[str],
) -> str:
    """Sample a team from the aggregated 3rd-place pool of eligible groups,
    excluding teams already placed (winners or runners-up sampled this iteration)."""
    pool: dict[str, float] = {}
    for g in eligible_groups:
        for team, prob in group_probs[g].third_place_probs.items():
            if team in excluded:
                continue
            pool[team] = pool.get(team, 0.0) + prob
    if not pool:
        # All eligible 3rd-placed teams already used; fall back to uniform draw
        # from any team in the eligible groups not yet placed.
        candidates = [
            t
            for g in eligible_groups
            for t in group_probs[g].third_place_probs.keys()
            if t not in excluded
        ]
        return rng.choice(candidates) if candidates else "TBD"
    return _sample_from_distribution(pool, rng)


def _sample_r32_slot(
    slot: str,
    group_probs: dict[str, GroupAdvanceProbs],
    rng: random.Random,
    used_teams: set[str],
) -> tuple[str, str]:
    spec = _R32_SLOT_SPECS.get(slot)
    if spec is None:
        # Unknown slot; sample uniformly from the entire team pool.
        all_teams = [t for p in group_probs.values() for t in p.win_probs.keys()]
        a = rng.choice(all_teams)
        b = rng.choice([t for t in all_teams if t != a])
        return (a, b)

    left_spec, right_spec = spec

    def sample_one(s: _FeederSpec, exclude: set[str]) -> str:
        kind = s[0]
        if kind == "group_winner":
            group = s[1]
            assert isinstance(group, str)
            return _sample_from_distribution(group_probs[group].win_probs, rng)
        if kind == "group_runner_up":
            group = s[1]
            assert isinstance(group, str)
            return _sample_from_distribution(group_probs[group].runner_up_probs, rng)
        if kind == "best_third":
            eligible = s[1]
            assert isinstance(eligible, tuple)
            return _sample_best_third(eligible, group_probs, rng, exclude)
        raise ValueError(f"unknown feeder kind: {kind}")

    team_a = sample_one(left_spec, used_teams)
    team_b = sample_one(right_spec, used_teams | {team_a})
    return (team_a, team_b)


def _all_tracked_slots() -> tuple[str, ...]:
    """Every knockout slot the simulator records matchup + winner histograms for."""
    return (
        *_R32_SLOT_SPECS.keys(),
        *_R16_SLOT_PARENTS.keys(),
        *_QF_SLOT_PARENTS.keys(),
        *_SF_SLOT_PARENTS.keys(),
        _FINAL_SLOT,
        _BRONZE_SLOT,
    )


def simulate_bracket(
    *,
    group_probs: dict[str, GroupAdvanceProbs],
    bracket_yaml_groups: dict[str, list[str]],
    n_iterations: int,
    rng: random.Random,
) -> dict[str, SlotMatchupCounts]:
    """Run n_iterations of the bracket and return per-slot matchup histograms.

    Every TBD knockout slot is tracked uniformly:
      - 16 R32 (r32_match_73 through r32_match_88)
      - 8  R16 (r16_match_89 through r16_match_96)
      - 4  QF  (qf_match_97 through qf_match_100)
      - 2  SF  (sf_match_101, sf_match_102)
      - 1  Final (final_match_104) — from SF winners
      - 1  Bronze (bronze_match_103) — from SF losers

    Each slot's `SlotMatchupCounts` carries both the matchup histogram
    (which two teams meet here, across iterations) and the winner
    histogram (which team advances, since knockouts are coin flips in
    this model).
    """
    # bracket_yaml_groups is accepted for forward compatibility (e.g., a future
    # plan that uses it for knockout-side seeding). Not consumed here beyond
    # serving as documentation that the simulator runs against a known
    # group-team mapping.
    _ = bracket_yaml_groups

    counts: dict[str, SlotMatchupCounts] = {
        slot: SlotMatchupCounts() for slot in _all_tracked_slots()
    }

    for _ in range(n_iterations):
        # ─── R32 ───────────────────────────────────────────────────────
        r32_results: dict[str, tuple[str, str]] = {}
        used: set[str] = set()
        for slot in _R32_SLOT_SPECS:
            a, b = _sample_r32_slot(slot, group_probs, rng, used)
            r32_results[slot] = (a, b)
            used.update([a, b])
            counts[slot].record(a, b)

        r32_winner: dict[str, str] = {
            slot: rng.choice(list(pair)) for slot, pair in r32_results.items()
        }
        for slot, winner in r32_winner.items():
            counts[slot].record_winner(winner)

        # ─── R16 ───────────────────────────────────────────────────────
        r16_winner: dict[str, str] = {}
        for r16_slot, (left_parent, right_parent) in _R16_SLOT_PARENTS.items():
            a = r32_winner[left_parent]
            b = r32_winner[right_parent]
            counts[r16_slot].record(a, b)
            winner = rng.choice([a, b])
            r16_winner[r16_slot] = winner
            counts[r16_slot].record_winner(winner)

        # ─── QF ────────────────────────────────────────────────────────
        qf_winner: dict[str, str] = {}
        for qf_slot, (left_parent, right_parent) in _QF_SLOT_PARENTS.items():
            a = r16_winner[left_parent]
            b = r16_winner[right_parent]
            counts[qf_slot].record(a, b)
            winner = rng.choice([a, b])
            qf_winner[qf_slot] = winner
            counts[qf_slot].record_winner(winner)

        # ─── SF (also remember losers for Bronze) ──────────────────────
        sf_winner: dict[str, str] = {}
        sf_loser: dict[str, str] = {}
        for sf_slot, (left_parent, right_parent) in _SF_SLOT_PARENTS.items():
            a = qf_winner[left_parent]
            b = qf_winner[right_parent]
            counts[sf_slot].record(a, b)
            winner = rng.choice([a, b])
            loser = b if winner == a else a
            sf_winner[sf_slot] = winner
            sf_loser[sf_slot] = loser
            counts[sf_slot].record_winner(winner)

        # ─── Final = SF winners ───────────────────────────────────────
        sf_left, sf_right = _SF_SLOTS_IN_ORDER
        f_a = sf_winner[sf_left]
        f_b = sf_winner[sf_right]
        counts[_FINAL_SLOT].record(f_a, f_b)
        counts[_FINAL_SLOT].record_winner(rng.choice([f_a, f_b]))

        # ─── Bronze = SF losers ───────────────────────────────────────
        b_a = sf_loser[sf_left]
        b_b = sf_loser[sf_right]
        counts[_BRONZE_SLOT].record(b_a, b_b)
        counts[_BRONZE_SLOT].record_winner(rng.choice([b_a, b_b]))

    return counts
