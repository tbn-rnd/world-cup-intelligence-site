import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schema import (
    ConfirmedTeam,
    DataFreshness,
    MatchesFile,
    MatchObject,
    Phase,
    Popularity,
    Status,
    TeamsBlock,
    TournamentPhase,
)
from backend.writer import load_previous, write_matches_file


def _minimal_file() -> MatchesFile:
    matches = []
    for i in range(11):
        matches.append(
            MatchObject(
                id=f"m{i}",
                kickoff_utc=datetime(2026, 6, 1 + i, 16, 0, tzinfo=UTC),
                kickoff_local="2026-06-01T12:00:00-04:00",
                host_city="Atlanta",
                venue="V",
                phase=Phase.GROUP_STAGE,
                status=Status.CONFIRMED,
                popularity=Popularity(
                    tier="popular",
                    rationale="United States (FIFA #16) draws a global audience.",
                ),
                confidence="certain",
                teams=TeamsBlock(
                    confirmed=[
                        ConfirmedTeam(code="USA", name="USA", fifa_rank=1),
                        ConfirmedTeam(code="POR", name="Portugal", fifa_rank=2),
                    ],
                ),
                signature=f"v1:confirmed:USA-POR-{i}",
            )
        )
    return MatchesFile(
        generated_at=datetime.now(UTC),
        data_freshness=DataFreshness.FRESH,
        tournament_phase=TournamentPhase.GROUP_STAGE,
        matches=matches,
    )


def test_writes_valid_json(tmp_path: Path) -> None:
    out = tmp_path / "matches.json"
    f = _minimal_file()
    write_matches_file(f, out)
    raw = json.loads(out.read_text())
    assert raw["data_freshness"] == "fresh"
    assert len(raw["matches"]) == 11


def test_load_previous_returns_none_when_missing(tmp_path: Path) -> None:
    out = tmp_path / "missing.json"
    assert load_previous(out) is None


def test_load_previous_round_trips(tmp_path: Path) -> None:
    out = tmp_path / "matches.json"
    f = _minimal_file()
    write_matches_file(f, out)
    loaded = load_previous(out)
    assert loaded is not None
    assert len(loaded.matches) == 11


def test_match_object_requires_popularity() -> None:
    """MatchObject construction without popularity must fail validation."""
    with pytest.raises(ValidationError):
        MatchObject.model_validate(
            {
                "id": "x",
                "kickoff_utc": datetime(2026, 6, 1, 16, 0, tzinfo=UTC),
                "kickoff_local": "2026-06-01T12:00:00-04:00",
                "host_city": "Atlanta",
                "venue": "V",
                "phase": "group_stage",
                "status": "confirmed",
                "confidence": "certain",
                "teams": {
                    "confirmed": [
                        {"code": "USA", "name": "USA", "fifa_rank": 1},
                        {"code": "POR", "name": "Portugal", "fifa_rank": 2},
                    ],
                },
                "signature": "v1:confirmed:USA-POR",
            }
        )
