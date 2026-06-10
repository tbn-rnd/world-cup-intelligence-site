import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.odds_client import OddsApiError
from backend.refresh import run_live, run_offline


def test_offline_run_produces_valid_104_match_file(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    assert len(raw["matches"]) == 104
    assert raw["data_freshness"] == "fresh"

    by_id = {m["id"]: m for m in raw["matches"]}

    # Group A opener (MEX vs RSA) — host nation, confirmed.
    opener_match = by_id["mex-2026-06-11-grpA-mex-rsa"]
    assert opener_match["status"] == "confirmed"
    assert opener_match["confidence"] == "certain"
    assert ":confirmed:" in opener_match["signature"]
    assert opener_match["signature"].split(":", 1)[0] in {"v1", "v2", "v3", "v4"}

    # An R32 slot at NY/NJ on Jun 30 — bracket M77 (I1 vs 3rd).
    nj_r32 = by_id["nyj-2026-06-30-r32-match-77"]
    assert nj_r32["status"] == "tbd"
    assert len(nj_r32["teams"]["tbd_scenarios"]) == 3

    # Popularity wiring — every match must carry a valid tier and a non-empty rationale.
    for m in raw["matches"]:
        assert m["popularity"]["tier"] in {"popular", "moderate", "standard"}
        assert m["popularity"]["rationale"]
    # Host-nation opener should be Popular by rule.
    opener = next(m for m in raw["matches"] if m["id"] == "mex-2026-06-11-grpA-mex-rsa")
    assert opener["popularity"]["tier"] == "popular"


def test_brief_is_null_in_plan_1(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        assert m["brief"] is None, f"{m['id']} brief should be null in Plan 1"


@pytest.mark.skipif(
    not os.environ.get("ODDS_API_KEY"),
    reason="set ODDS_API_KEY to run the live integration smoke",
)
def test_live_run_writes_valid_file(tmp_path: Path, knowledge_dir: Path) -> None:
    output_path = tmp_path / "matches.json"
    run_live(
        knowledge_dir=knowledge_dir,
        output_path=output_path,
        api_key=os.environ["ODDS_API_KEY"],
    )
    raw = json.loads(output_path.read_text())
    assert len(raw["matches"]) == 104
    assert raw["data_freshness"] == "fresh"


def test_confidence_transition_changes_tbd_signature(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Signatures for TBD matches must reflect actual confidence, not a hardcoded value.

    At 2026-06-20 the group stage is unresolved → confidence=low for all TBDs.
    At 2026-06-30 the group stage has ended (2026-06-27) and the r32 decision_date
    (2026-06-27) is within 3 days → confidence=high for at least one TBD match.
    The signature string must differ between the two runs.
    """
    output_path = tmp_path / "matches.json"

    # First run: groups not yet resolved → confidence=low
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw_early = json.loads(output_path.read_text())
    sigs_early = {m["id"]: m["signature"] for m in raw_early["matches"] if m["status"] == "tbd"}

    # Second run: groups resolved → confidence=high for r32 matches near decision date
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-30T12:00:00Z",
    )
    raw_late = json.loads(output_path.read_text())
    sigs_late = {m["id"]: m["signature"] for m in raw_late["matches"] if m["status"] == "tbd"}

    # At least one TBD match must have a different signature because conf= changed.
    changed = [
        match_id
        for match_id in sigs_early
        if match_id in sigs_late and sigs_early[match_id] != sigs_late[match_id]
    ]
    assert changed, (
        "Expected at least one TBD signature to change between 2026-06-20 and 2026-06-30 "
        f"due to conf= transition, but all signatures were identical.\n"
        f"Early sigs: {sigs_early}\n"
        f"Late sigs: {sigs_late}"
    )


def test_offline_run_produces_real_scenarios_for_all_tbd_slots(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.5 contract: every TBD slot has a non-placeholder signature."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    tbd_matches = [m for m in raw["matches"] if m["status"] == "tbd"]
    # 32 knockout slots in the new full schedule (16 R32 + 8 R16 + 4 QF + 2 SF
    # + 1 bronze + 1 final).
    assert len(tbd_matches) == 32
    for m in tbd_matches:
        scenarios = m["teams"]["tbd_scenarios"]
        assert len(scenarios) == 3
        assert "awaiting-feeders" not in m["signature"], (
            f"{m['id']} still has awaiting-feeders signature: {m['signature']}"
        )


def test_live_run_marks_data_freshness_unreachable_on_api_error(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """When OddsApiError is raised and a previous matches.json exists,
    run_live must write back the previous data with data_freshness='unreachable'."""
    output_path = tmp_path / "matches.json"

    # Pre-populate output_path with a valid offline-generated file.
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    original_raw = json.loads(output_path.read_text())
    assert original_raw["data_freshness"] == "fresh"

    # Mock the OddsClient to raise OddsApiError on fetch().
    mock_client = MagicMock()
    mock_client.fetch.side_effect = OddsApiError("Odds API unreachable: connection refused")

    run_live(
        knowledge_dir=knowledge_dir,
        output_path=output_path,
        api_key="dummy-key",
        client=mock_client,
    )

    result = json.loads(output_path.read_text())
    assert result["data_freshness"] == "unreachable", (
        f"Expected data_freshness='unreachable', got {result['data_freshness']!r}"
    )
    # Matches should be preserved from the previous file.
    assert len(result["matches"]) == len(original_raw["matches"])
    # generated_at should have been updated (not the original timestamp).
    assert result["generated_at"] != original_raw["generated_at"]


def test_offline_run_emits_feeder_distributions_for_direct_group_slots(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.6 contract: every direct-group-feeder TBD slot has populated feeder_distributions."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())

    # r32_match_76 — the Houston Jun 29 R32 (C1 vs F2), a direct-group
    # feeder slot used to verify feeder_distribution wiring.
    direct_group_r32 = next(
        m for m in raw["matches"] if m["id"] == "hou-2026-06-29-r32-match-76"
    )
    fd = direct_group_r32["teams"]["feeder_distributions"]
    assert fd is not None
    assert len(fd) == 2  # Group C winner + Group F runner-up
    labels = {entry["label"] for entry in fd}
    assert labels == {"Group C winner", "Group F runner-up"}
    for entry in fd:
        assert abs(sum(t["probability"] for t in entry["teams"]) - 1.0) < 0.01
        probs = [t["probability"] for t in entry["teams"]]
        assert probs == sorted(probs, reverse=True)


def test_offline_run_trims_cross_product_to_three(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.6 contract: tbd_scenarios is exactly 3 entries (was 5 in Plan 1.5)."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        if m["status"] == "tbd":
            assert len(m["teams"]["tbd_scenarios"]) == 3


def test_offline_run_omits_feeder_distributions_for_sf_bronze(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.6 contract: SF and Bronze slots use uniform-pool approximation; no feeder_distributions."""  # noqa: E501
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    for slot_id in ("atl-2026-07-15-sf-match-102", "mia-2026-07-18-bronze-match-103"):
        m = next(x for x in raw["matches"] if x["id"] == slot_id)
        assert m["teams"]["feeder_distributions"] is None


class TestCadenceGating:
    def test_group_stage_cadence_runs_in_pre_tournament(self) -> None:
        from backend.refresh import should_run_for_cadence
        assert should_run_for_cadence("group_stage", "pre_tournament") is True

    def test_group_stage_cadence_runs_in_group_stage(self) -> None:
        from backend.refresh import should_run_for_cadence
        assert should_run_for_cadence("group_stage", "group_stage") is True

    def test_group_stage_cadence_skips_in_knockouts(self) -> None:
        from backend.refresh import should_run_for_cadence
        for phase in ("round_of_32", "round_of_16", "quarter_finals", "semi_finals", "finals"):
            assert should_run_for_cadence("group_stage", phase) is False, f"failed at {phase}"

    def test_knockouts_cadence_skips_in_pre_tournament_and_group_stage(self) -> None:
        from backend.refresh import should_run_for_cadence
        for phase in ("pre_tournament", "group_stage"):
            assert should_run_for_cadence("knockouts", phase) is False, f"failed at {phase}"

    def test_knockouts_cadence_runs_in_all_knockout_phases(self) -> None:
        from backend.refresh import should_run_for_cadence
        for phase in ("round_of_32", "round_of_16", "quarter_finals", "semi_finals", "finals"):
            assert should_run_for_cadence("knockouts", phase) is True, f"failed at {phase}"

    def test_unknown_cadence_raises(self) -> None:
        import pytest

        from backend.refresh import should_run_for_cadence
        with pytest.raises(ValueError, match="unknown cadence"):
            should_run_for_cadence("invalid", "group_stage")
