import random

from backend.bracket_simulation import (
    SlotMatchupCounts,
    simulate_bracket,
)
from backend.groups import GroupAdvanceProbs


def _uniform_group(teams: list[str]) -> GroupAdvanceProbs:
    n = len(teams)
    return GroupAdvanceProbs(
        win_probs={t: 1.0 / n for t in teams},
        runner_up_probs={t: 1.0 / n for t in teams},
        third_place_probs={t: 1.0 / n for t in teams},
        fourth_place_probs={t: 1.0 / n for t in teams},
    )


def _example_groups() -> dict[str, GroupAdvanceProbs]:
    teams_per_group = {
        "A": ["MEX", "KOR", "JAM", "NOR"],
        "B": ["ENG", "WAL", "IRN", "USA"],
        "C": ["FRA", "POL", "CHI", "TUN"],
        "D": ["ARG", "AUS", "DEN", "GHA"],
        "E": ["BRA", "JPN", "CRC", "SRB"],
        "F": ["ESP", "BEL", "ECU", "NGA"],
        "G": ["GER", "PER", "PAR", "SAU"],
        "H": ["NED", "URU", "EGY", "IRQ"],
        "I": ["POR", "COL", "VEN", "OMA"],
        "J": ["ITA", "MAR", "PAN", "QAT"],
        "K": ["CRO", "SEN", "SVK", "BFA"],
        "L": ["BHM", "RSA", "GUI", "JOR"],
    }
    return {g: _uniform_group(teams) for g, teams in teams_per_group.items()}


def test_simulate_bracket_records_every_knockout_slot() -> None:
    """All 32 knockout slots (16 R32 + 8 R16 + 4 QF + 2 SF + Final + Bronze)
    must each receive matchup + winner histograms across n iterations."""
    groups = _example_groups()
    rng = random.Random(42)

    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=2000,
        rng=rng,
    )

    expected_r32 = {f"r32_match_{n}" for n in range(73, 89)}
    expected_r16 = {f"r16_match_{n}" for n in range(89, 97)}
    expected_qf = {f"qf_match_{n}" for n in range(97, 101)}
    expected_sf = {"sf_match_101", "sf_match_102"}
    expected_final_bronze = {"final_match_104", "bronze_match_103"}
    expected_all = expected_r32 | expected_r16 | expected_qf | expected_sf | expected_final_bronze

    assert set(counts.keys()) == expected_all, (
        f"missing: {expected_all - set(counts.keys())}, "
        f"extra: {set(counts.keys()) - expected_all}"
    )

    for slot in expected_all:
        assert len(counts[slot].matchup_count) > 0, f"slot {slot} has no recorded matchups"
        assert sum(counts[slot].matchup_count.values()) == 2000, (
            f"slot {slot} matchup_count incomplete"
        )
        assert sum(counts[slot].winner_count.values()) == 2000, (
            f"slot {slot} winner_count incomplete"
        )


def test_simulate_bracket_is_deterministic_given_seed() -> None:
    groups = _example_groups()
    bracket_groups = {g: list(p.win_probs.keys()) for g, p in groups.items()}

    counts_a = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups=bracket_groups,
        n_iterations=500,
        rng=random.Random(123),
    )
    counts_b = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups=bracket_groups,
        n_iterations=500,
        rng=random.Random(123),
    )

    for slot in counts_a:
        assert counts_a[slot].matchup_count == counts_b[slot].matchup_count


def test_top_matchup_for_slot_returns_descending_distribution() -> None:
    groups = _example_groups()
    rng = random.Random(7)
    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=2000,
        rng=rng,
    )

    top5 = counts["r32_match_77"].top_matchups(k=5)
    assert len(top5) == 5
    probs = [p for (_pair, p) in top5]
    assert probs == sorted(probs, reverse=True)
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_slot_matchup_counts_record_canonicalizes_order() -> None:
    counts = SlotMatchupCounts()
    counts.record("MEX", "JPN")
    counts.record("JPN", "MEX")  # same pairing, opposite order
    assert sum(counts.matchup_count.values()) == 2
    # Both should land in the same canonical key
    assert len(counts.matchup_count) == 1


def test_slot_records_winner_histogram() -> None:
    """SlotMatchupCounts.record_winner builds a per-team count for the slot's winner."""
    counts = SlotMatchupCounts()
    counts.record_winner("MEX")
    counts.record_winner("MEX")
    counts.record_winner("NED")
    assert counts.winner_count == {"MEX": 2, "NED": 1}
    top = counts.top_winners(k=2)
    assert top[0] == ("MEX", 2 / 3)
    assert top[1] == ("NED", 1 / 3)


def test_simulate_bracket_records_r32_winner_histogram_for_every_slot() -> None:
    """Every R32 slot gets a winner histogram, not just a subset."""
    groups = _example_groups()
    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=2000,
        rng=random.Random(11),
    )
    for n in range(73, 89):
        slot = f"r32_match_{n}"
        assert sum(counts[slot].winner_count.values()) == 2000, (
            f"slot {slot} winner_count incomplete"
        )


def test_top_winners_empty_returns_empty_list() -> None:
    counts = SlotMatchupCounts()
    assert counts.top_winners(k=5) == []


def test_simulate_bracket_records_final_and_bronze_from_sf_results() -> None:
    """Final teams must be SF winners; Bronze teams must be SF losers, with
    no team appearing in both — a basic sanity check on the SF→Final/Bronze
    routing."""
    groups = _example_groups()
    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=1000,
        rng=random.Random(99),
    )

    # Every team that ever reaches the Final is one that won an SF.
    sf_winners = set(counts["sf_match_101"].winner_count) | set(
        counts["sf_match_102"].winner_count
    )
    final_teams: set[str] = set()
    for (a, b) in counts["final_match_104"].matchup_count:
        final_teams.update((a, b))
    assert final_teams.issubset(sf_winners), (
        f"Final teams not subset of SF winners: extras {final_teams - sf_winners}"
    )

    # Bronze matchup teams should never overlap with the corresponding Final
    # teams in the same iteration. We can't check that directly per-iteration
    # without instrumentation, but every Bronze team must have appeared as an
    # SF participant in *some* iteration.
    sf_participants: set[str] = set()
    for slot in ("sf_match_101", "sf_match_102"):
        for (a, b) in counts[slot].matchup_count:
            sf_participants.update((a, b))
    bronze_teams: set[str] = set()
    for (a, b) in counts["bronze_match_103"].matchup_count:
        bronze_teams.update((a, b))
    assert bronze_teams.issubset(sf_participants), (
        f"Bronze teams not subset of SF participants: extras {bronze_teams - sf_participants}"
    )
