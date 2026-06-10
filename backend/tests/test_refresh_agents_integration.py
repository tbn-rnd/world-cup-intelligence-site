import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.refresh import run_offline


def _agent_response_for(content: dict[str, Any]) -> Any:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(content)
    response = MagicMock()
    response.content = [block]
    return response


def _make_mock_sdk(brief_response: dict[str, Any]) -> MagicMock:
    """Mock SDK that returns the brief response for every call."""
    sdk = MagicMock()
    sdk.messages.create.side_effect = [
        _agent_response_for(brief_response) for _ in range(256)
    ]
    return sdk


def test_run_offline_populates_brief_for_every_match(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    brief_payload = json.loads((fixtures_dir / "mock_brief_response.json").read_text())
    sdk = _make_mock_sdk(brief_payload)

    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk,
    )
    raw = json.loads(output_path.read_text())

    # Every match — regardless of tier — gets a brief populated.
    assert raw["matches"], "expected at least one match in the fixture"
    for m in raw["matches"]:
        assert m["brief"] is not None, f"{m['id']} brief missing"
        assert m["brief"]["headline"]


def test_run_offline_skips_agent_calls_when_signature_unchanged(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Second run with same as-of should not call agents — previous brief reused."""
    brief_payload = json.loads((fixtures_dir / "mock_brief_response.json").read_text())

    output_path = tmp_path / "matches.json"

    sdk1 = _make_mock_sdk(brief_payload)
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk1,
    )
    first_call_count = sdk1.messages.create.call_count
    assert first_call_count > 0

    sdk2 = MagicMock()
    sdk2.messages.create.side_effect = AssertionError("agents should not be called")
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk2,
    )
    assert sdk2.messages.create.call_count == 0


def test_run_offline_continues_when_agents_disabled(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """If anthropic_api_key is None and no SDK provided, brief stays null."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key=None,
        anthropic_sdk=None,
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        assert m["brief"] is None


def test_agent_called_once_per_match(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Every match invokes the briefing agent exactly once on a fresh run."""
    brief_payload = json.loads((fixtures_dir / "mock_brief_response.json").read_text())
    sdk = _make_mock_sdk(brief_payload)

    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk,
    )

    raw = json.loads(output_path.read_text())
    assert raw["matches"], "fixture should produce at least one match"
    assert sdk.messages.create.call_count == len(raw["matches"])


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="set ANTHROPIC_API_KEY to run the live agent integration smoke",
)
def test_live_briefing_agent_returns_valid_brief(
    knowledge_dir: Path,
) -> None:
    """Hits the real Anthropic API to confirm the briefing agent's prompt produces valid output."""
    from datetime import UTC, datetime

    from backend.agents.briefing import run_briefing
    from backend.agents.client import AgentClient
    from backend.schema import (
        ConfirmedTeam,
        MatchObject,
        Phase,
        Popularity,
        Status,
        TeamsBlock,
    )

    match = MatchObject(
        id="atl-2026-03-31-usa-por",
        kickoff_utc=datetime(2026, 3, 31, 16, 0, tzinfo=UTC),
        kickoff_local="2026-03-31T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.FRIENDLY,
        status=Status.CONFIRMED,
        popularity=Popularity(tier="popular", rationale="Top-10 FIFA matchup (Portugal)."),
        confidence="certain",
        teams=TeamsBlock(
            confirmed=[
                ConfirmedTeam(code="USA", name="United States", fifa_rank=16),
                ConfirmedTeam(code="POR", name="Portugal", fifa_rank=6),
            ],
        ),
        signature="v2:confirmed:POR-USA",
    )

    client = AgentClient(api_key=os.environ["ANTHROPIC_API_KEY"])
    brief = run_briefing(match=match, client=client, knowledge_dir=knowledge_dir)

    assert brief.headline
    assert (
        "USA" in brief.fan_demographics
        or "Portugal" in brief.fan_demographics
        or "diaspora" in brief.fan_demographics.lower()
    )
