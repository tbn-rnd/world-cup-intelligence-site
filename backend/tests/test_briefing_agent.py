from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from backend.agents.briefing import build_match_user_message, run_briefing
from backend.agents.client import AgentClient
from backend.schema import (
    ConfirmedTeam,
    FeederDistribution,
    FeederTeam,
    MatchObject,
    Phase,
    Popularity,
    Status,
    TbdScenario,
    TeamRef,
    TeamsBlock,
)


def _make_confirmed_match() -> MatchObject:
    return MatchObject(
        id="atl-2026-03-31-usa-por",
        kickoff_utc=datetime(2026, 3, 31, 16, 0, tzinfo=UTC),
        kickoff_local="2026-03-31T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.FRIENDLY,
        status=Status.CONFIRMED,
        popularity=Popularity(tier="popular", rationale="Top-10 FIFA matchup."),
        confidence="certain",
        teams=TeamsBlock(
            confirmed=[
                ConfirmedTeam(code="USA", name="United States", fifa_rank=16),
                ConfirmedTeam(code="POR", name="Portugal", fifa_rank=6),
            ],
        ),
        signature="v2:confirmed:POR-USA",
    )


def _make_tbd_match() -> MatchObject:
    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code="MEX", name="Mexico"),
            team_b=TeamRef(code=code, name=name),
            probability=p,
            delta_pp=0.0,
            rationale="r",
        )
        for i, (code, name, p) in enumerate(
            [("NED", "Netherlands", 0.11), ("JPN", "Japan", 0.10), ("SWE", "Sweden", 0.10)],
            start=1,
        )
    ]
    feeders = [
        FeederDistribution(
            label="Group A winner",
            teams=[
                FeederTeam(code="MEX", name="Mexico", probability=0.64),
                FeederTeam(code="CZE", name="Czech Republic", probability=0.14),
            ],
        ),
        FeederDistribution(
            label="Group F runner-up",
            teams=[
                FeederTeam(code="NED", name="Netherlands", probability=0.32),
                FeederTeam(code="JPN", name="Japan", probability=0.30),
            ],
        ),
    ]
    return MatchObject(
        id="njy-2026-06-30-r32-a1-vs-f2",
        kickoff_utc=datetime(2026, 6, 30, 21, 0, tzinfo=UTC),
        kickoff_local="2026-06-30T17:00:00-04:00",
        host_city="NY/NJ",
        venue="MetLife Stadium",
        phase=Phase.ROUND_OF_32,
        status=Status.TBD,
        popularity=Popularity(tier="popular", rationale="Mexico is the heavy feeder favorite."),
        confidence="medium",
        teams=TeamsBlock(
            confirmed=None,
            tbd_scenarios=scenarios,
            feeder_distributions=feeders,
        ),
        signature="v2:tbd:...",
        decision_date="2026-06-27",
        days_to_decision=3,
    )


def test_build_user_message_for_confirmed_match_includes_team_codes() -> None:
    match = _make_confirmed_match()
    msg = build_match_user_message(match)
    assert "USA" in msg
    assert "POR" in msg
    assert "Atlanta" in msg
    assert "Mercedes-Benz Stadium" in msg


def test_build_user_message_for_tbd_match_includes_feeder_distributions() -> None:
    match = _make_tbd_match()
    msg = build_match_user_message(match)
    assert "Group A winner" in msg
    assert "Group F runner-up" in msg
    assert "Mexico" in msg
    assert "medium" in msg.lower()
    assert "2026-06-27" in msg


def test_run_briefing_returns_validated_brief(
    knowledge_dir: Path,
    fixtures_dir: Path,
) -> None:
    raw_text = (fixtures_dir / "mock_brief_response.json").read_text()
    block = MagicMock()
    block.type = "text"
    block.text = raw_text
    response = MagicMock()
    response.content = [block]
    sdk = MagicMock()
    sdk.messages.create.return_value = response

    agent_client = AgentClient(api_key="k", sdk=sdk)
    match = _make_tbd_match()
    brief = run_briefing(match=match, client=agent_client, knowledge_dir=knowledge_dir)
    assert brief.headline.startswith("Mexico-Netherlands")
    assert brief.scenario_summary is not None
    assert "Mexican diaspora" in brief.fan_demographics
    assert brief.cultural_context
    assert not hasattr(brief, "demand_rationale")
