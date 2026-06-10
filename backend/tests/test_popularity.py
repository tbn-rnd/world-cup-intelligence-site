from dataclasses import dataclass
from typing import cast

from backend.popularity import (
    GLOBAL_DRAW_BRANDS,
    HOST_NATIONS,
    FeederLeader,
    TeamLookup,
    compute_popularity,
)


@dataclass(frozen=True)
class _Team:
    name: str
    fifa_rank: int


def _lookup(*ranks: tuple[str, int]) -> TeamLookup:
    return {code: _Team(name=code, fifa_rank=rank) for code, rank in ranks}


def test_final_is_popular_regardless_of_teams() -> None:
    lookup = _lookup(("XYZ", 80), ("ABC", 90))
    p = compute_popularity(
        phase="final", status="confirmed",
        confirmed_team_codes=("XYZ", "ABC"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Final" in p.rationale or "knockout" in p.rationale.lower()


def test_semifinal_is_popular() -> None:
    lookup = _lookup(("XYZ", 80), ("ABC", 90))
    p = compute_popularity(
        phase="semi_final", status="confirmed",
        confirmed_team_codes=("XYZ", "ABC"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"


def test_bronze_final_is_popular() -> None:
    lookup = _lookup(("XYZ", 80), ("ABC", 90))
    p = compute_popularity(
        phase="bronze_final", status="confirmed",
        confirmed_team_codes=("XYZ", "ABC"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"


def test_top10_team_in_group_stage_is_popular() -> None:
    lookup = _lookup(("BRA", 1), ("MAR", 14))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("BRA", "MAR"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Brazil" in p.rationale or "BRA" in p.rationale or "FIFA" in p.rationale


def test_host_nation_in_group_stage_is_popular() -> None:
    lookup = _lookup(("USA", 20), ("PAR", 50))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("USA", "PAR"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Host-nation" in p.rationale or "host" in p.rationale.lower()


def test_global_draw_brand_in_group_stage_is_popular() -> None:
    lookup = _lookup(("ENG", 5), ("PAN", 60))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("ENG", "PAN"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"


def test_group_stage_host_and_brand_present_prefers_host() -> None:
    # When both a host nation and a global-draw brand are in the same group-stage
    # match (neither in the top 10), the host-nation rule fires first.
    lookup = _lookup(("MEX", 15), ("BRA", 12))
    p = compute_popularity(
        phase="group_stage",
        status="confirmed",
        confirmed_team_codes=("MEX", "BRA"),
        feeder_distributions=None,
        team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Host-nation" in p.rationale
    assert "TV draw" not in p.rationale


def test_r32_default_is_moderate() -> None:
    lookup = _lookup(("RSA", 60), ("CZE", 41))
    p = compute_popularity(
        phase="round_of_32", status="confirmed",
        confirmed_team_codes=("RSA", "CZE"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_r16_default_is_moderate() -> None:
    lookup = _lookup(("RSA", 60), ("CZE", 41))
    p = compute_popularity(
        phase="round_of_16", status="confirmed",
        confirmed_team_codes=("RSA", "CZE"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_qf_default_is_moderate() -> None:
    lookup = _lookup(("RSA", 60), ("CZE", 41))
    p = compute_popularity(
        phase="quarter_final", status="confirmed",
        confirmed_team_codes=("RSA", "CZE"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_group_stage_top25_no_brand_is_moderate() -> None:
    lookup = _lookup(("AUS", 24), ("HAI", 75))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("AUS", "HAI"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_group_stage_no_top25_no_brand_is_standard() -> None:
    lookup = _lookup(("HAI", 75), ("UZB", 68))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("HAI", "UZB"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "standard"
    assert "top 25" in p.rationale


def test_tbd_r32_phase_only_when_no_feeder_leader_above_threshold() -> None:
    lookup = _lookup(("BRA", 1), ("GER", 8))
    # Feeder distributions present but leader is below 60% threshold.
    fd = [
        {"label": "Group A winner", "leader_code": "BRA", "leader_prob": 0.45},
        {"label": "Group F runner-up", "leader_code": "GER", "leader_prob": 0.30},
    ]
    p = compute_popularity(
        phase="round_of_32", status="tbd",
        confirmed_team_codes=None,
        feeder_distributions=cast(list[FeederLeader], fd), team_lookup=lookup,
    )
    assert p.tier == "moderate"  # phase-only; team triggers don't fire


def test_tbd_r32_uses_leader_when_above_threshold_top10() -> None:
    lookup = _lookup(("BRA", 1), ("XYZ", 30))
    fd = [
        {"label": "Group A winner", "leader_code": "BRA", "leader_prob": 0.72},
        {"label": "Group F runner-up", "leader_code": "XYZ", "leader_prob": 0.20},
    ]
    p = compute_popularity(
        phase="round_of_32", status="tbd",
        confirmed_team_codes=None,
        feeder_distributions=cast(list[FeederLeader], fd), team_lookup=lookup,
    )
    assert p.tier == "popular"  # BRA top-10 fires once leader confidence >= 0.60


def test_host_nations_constant() -> None:
    assert HOST_NATIONS == frozenset({"USA", "MEX", "CAN"})


def test_global_draw_brands_constant() -> None:
    assert GLOBAL_DRAW_BRANDS == frozenset(
        {"BRA", "ARG", "FRA", "ENG", "GER", "ESP", "POR", "NED", "BEL"}
    )
