from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.fixtures import load_fixtures

FIX = Path(__file__).parent / "fixtures" / "sample_fixtures.yaml"


def test_load_fixtures_returns_sorted_list() -> None:
    matches = load_fixtures(FIX)
    assert len(matches) == 2
    assert matches[0].id == "mex-2026-06-11-grpA-mex-kor"
    assert matches[0].kickoff_utc < matches[1].kickoff_utc


def test_confirmed_entry_has_teams_and_group() -> None:
    matches = load_fixtures(FIX)
    confirmed = matches[0]
    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_teams == ["MEX", "KOR"]
    assert confirmed.group == "A"
    assert confirmed.bracket_slot is None
    assert confirmed.decision_date is None


def test_tbd_entry_has_slot_and_decision_date() -> None:
    matches = load_fixtures(FIX)
    tbd = matches[1]
    assert tbd.status == "tbd"
    assert tbd.bracket_slot == "r32_match_75"
    assert tbd.decision_date == "2026-06-27"
    assert tbd.confirmed_teams == []
    assert tbd.group is None


def test_fixture_match_has_no_tickets_or_demand_tier() -> None:
    matches = load_fixtures(FIX)
    m = matches[0]
    # Sanity: FixtureMatch must not carry the dropped fields.
    assert not hasattr(m, "tickets")
    assert not hasattr(m, "demand_tier")


def test_load_fixtures_rejects_unknown_status(tmp_path: Path) -> None:
    bad = tmp_path / "bad_fixtures.yaml"
    bad.write_text(
        "tournament: x\nmatches:\n"
        "  - id: x\n    kickoff_local: '2026-06-11T12:00:00-06:00'\n"
        "    kickoff_utc: '2026-06-11T18:00:00Z'\n"
        "    host_city: Mexico City\n    venue: V\n    phase: group_stage\n"
        "    status: pending\n"
    )
    with pytest.raises(ValidationError):
        load_fixtures(bad)
