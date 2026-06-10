from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from backend.schema import (
    Brief,
    ConfirmedTeam,
    DataFreshness,
    MatchesFile,
    MatchObject,
    MatchPrediction,
    Phase,
    Popularity,
    Status,
    TbdScenario,
    TeamRef,
    TeamsBlock,
    TeamWinProb,
    TournamentPhase,
)


def _ct(code: str, name: str, rank: int) -> ConfirmedTeam:
    return ConfirmedTeam(code=code, name=name, fifa_rank=rank)


def _base_confirmed_match(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = dict(
        id="atl-2026-06-18-rsa-cze",
        kickoff_utc=datetime(2026, 6, 18, 16, 0, tzinfo=UTC),
        kickoff_local="2026-06-18T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.GROUP_STAGE,
        status=Status.CONFIRMED,
        popularity=Popularity(
            tier="standard", rationale="Group stage; teams outside the top 25."
        ),
        confidence="certain",
        teams=TeamsBlock(
            confirmed=[_ct("RSA", "South Africa", 60), _ct("CZE", "Czechia", 41)]
        ),
        signature="v1:confirmed:CZE-RSA",
    )
    defaults.update(overrides)
    return defaults


def make_confirmed_match() -> MatchObject:
    return MatchObject(**_base_confirmed_match())


def test_minimal_matches_file_validates() -> None:
    file = MatchesFile(
        generated_at=datetime.now(UTC),
        data_freshness=DataFreshness.FRESH,
        tournament_phase=TournamentPhase.PRE_TOURNAMENT,
        matches=[make_confirmed_match()],
    )
    assert file.matches[0].status == Status.CONFIRMED
    assert file.matches[0].teams.confirmed is not None
    assert file.matches[0].teams.confirmed[0].code == "RSA"


def test_confirmed_match_rejects_tbd_scenarios() -> None:
    """A confirmed match with tbd_scenarios populated should fail validation."""
    with pytest.raises(ValidationError):
        MatchObject(
            id="x",
            kickoff_utc=datetime.now(UTC),
            kickoff_local="2026-01-01T00:00:00Z",
            host_city="Atlanta",
            venue="V",
            phase=Phase.FRIENDLY,
            status=Status.CONFIRMED,
            popularity=Popularity(tier="popular", rationale="x"),
            confidence="certain",
            teams=TeamsBlock(
                confirmed=[
                    ConfirmedTeam(code="USA", name="USA", fifa_rank=1),
                    ConfirmedTeam(code="POR", name="Portugal", fifa_rank=2),
                ],
                tbd_scenarios=[
                    TbdScenario(
                        rank=1,
                        team_a=TeamRef(code="A00", name="A"),
                        team_b=TeamRef(code="B00", name="B"),
                        probability=0.5,
                        delta_pp=0.0,
                        rationale="x",
                    )
                ],
            ),
            signature="v1:confirmed:USA-POR",
            brief=None,
            decision_date=None,
            days_to_decision=None,
        )


def test_tbd_match_requires_exactly_three_scenarios() -> None:
    """TBD match with 2 scenarios should fail validation (must have exactly 3)."""
    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code=f"AA{i}", name=f"A{i}"),
            team_b=TeamRef(code=f"BB{i}", name=f"B{i}"),
            probability=0.1,
            delta_pp=0.0,
            rationale="r",
        )
        for i in range(1, 3)  # only 2 scenarios
    ]
    with pytest.raises(ValidationError):
        MatchObject(
            id="x",
            kickoff_utc=datetime.now(UTC),
            kickoff_local="2026-07-05T16:00:00-04:00",
            host_city="NY/NJ",
            venue="MetLife Stadium",
            phase=Phase.ROUND_OF_16,
            status=Status.TBD,
            popularity=Popularity(tier="popular", rationale="knockout"),
            confidence="medium",
            teams=TeamsBlock(confirmed=None, tbd_scenarios=scenarios),
            signature="v1:tbd:...",
            brief=None,
            decision_date="2026-07-03",
            days_to_decision=2,
        )


def test_feeder_distribution_validates() -> None:
    from backend.schema import FeederDistribution, FeederTeam

    fd = FeederDistribution(
        label="Group A winner",
        teams=[
            FeederTeam(code="MEX", name="Mexico", probability=0.64),
            FeederTeam(code="CZE", name="Czech Republic", probability=0.14),
        ],
    )
    assert fd.label == "Group A winner"
    assert len(fd.teams) == 2


def test_feeder_team_probability_bounds() -> None:
    from backend.schema import FeederTeam

    with pytest.raises(ValidationError):
        FeederTeam(code="MEX", name="Mexico", probability=1.5)
    with pytest.raises(ValidationError):
        FeederTeam(code="MEX", name="Mexico", probability=-0.1)


def test_tbd_match_can_carry_feeder_distributions() -> None:
    from backend.schema import (
        FeederDistribution,
        FeederTeam,
    )

    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code=f"AA{i}", name=f"A{i}"),
            team_b=TeamRef(code=f"BB{i}", name=f"B{i}"),
            probability=0.1,
            delta_pp=0.0,
            rationale="r",
        )
        for i in range(1, 4)
    ]
    feeders = [
        FeederDistribution(
            label="Group A winner",
            teams=[FeederTeam(code="MEX", name="Mexico", probability=0.64)],
        ),
    ]
    m = MatchObject(
        id="x",
        kickoff_utc=datetime.now(UTC),
        kickoff_local="2026-01-01T00:00:00Z",
        host_city="NY/NJ",
        venue="V",
        phase=Phase.ROUND_OF_32,
        status=Status.TBD,
        popularity=Popularity(tier="moderate", rationale="knockout TBD"),
        confidence="medium",
        teams=TeamsBlock(
            confirmed=None,
            tbd_scenarios=scenarios,
            feeder_distributions=feeders,
        ),
        signature="v1:tbd:...",
        decision_date="2026-01-01",
        days_to_decision=10,
    )
    assert m.teams.feeder_distributions is not None
    assert m.teams.feeder_distributions[0].label == "Group A winner"


def test_confirmed_match_rejects_feeder_distributions() -> None:
    """Confirmed matches must NOT carry feeder_distributions."""
    from backend.schema import FeederDistribution, FeederTeam

    with pytest.raises(ValidationError):
        MatchObject(
            id="x",
            kickoff_utc=datetime.now(UTC),
            kickoff_local="2026-01-01T00:00:00Z",
            host_city="Atlanta",
            venue="V",
            phase=Phase.FRIENDLY,
            status=Status.CONFIRMED,
            popularity=Popularity(tier="popular", rationale="x"),
            confidence="certain",
            teams=TeamsBlock(
                confirmed=[
                    ConfirmedTeam(code="USA", name="USA", fifa_rank=1),
                    ConfirmedTeam(code="POR", name="Portugal", fifa_rank=2),
                ],
                tbd_scenarios=None,
                feeder_distributions=[
                    FeederDistribution(
                        label="x",
                        teams=[FeederTeam(code="MEX", name="Mexico", probability=0.5)],
                    )
                ],
            ),
            signature="v1:confirmed:USA-POR",
        )


def test_brief_can_be_populated() -> None:
    brief = Brief(
        headline="Test headline",
        scenario_summary=None,
        fan_demographics="x",
        traveling_volume_est="x",
        cultural_context="x",
    )
    m = make_confirmed_match()
    m.brief = brief
    assert m.brief is not None
    assert m.brief.headline == "Test headline"


def test_match_object_has_popularity_and_no_tickets() -> None:
    m = MatchObject(**_base_confirmed_match())
    assert m.popularity.tier == "standard"
    assert "top 25" in m.popularity.rationale
    assert not hasattr(m, "tickets")
    assert not hasattr(m, "demand_tier")


def test_brief_has_no_demand_rationale_field() -> None:
    b = Brief(
        headline="x",
        scenario_summary=None,
        fan_demographics="x",
        traveling_volume_est="x",
        cultural_context="x",
    )
    assert not hasattr(b, "demand_rationale")


def test_matches_file_allows_more_than_eleven() -> None:
    base = _base_confirmed_match()
    matches = [
        MatchObject(**{**base, "id": f"x-{i}", "signature": f"v1:confirmed:A-B-{i}"})
        for i in range(104)
    ]
    f = MatchesFile(
        generated_at=datetime.now(UTC),
        data_freshness=DataFreshness.FRESH,
        tournament_phase=TournamentPhase.GROUP_STAGE,
        matches=matches,
    )
    assert len(f.matches) == 104


def test_popularity_tier_literal_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        Popularity(tier="legendary", rationale="x")  # type: ignore[arg-type]


def test_match_prediction_can_be_populated() -> None:
    pred = MatchPrediction(
        method="fifa_rank_elo",
        teams=[
            TeamWinProb(code="USA", name="United States", win_prob=0.55),
            TeamWinProb(code="POR", name="Portugal", win_prob=0.45),
        ],
        draw_prob=None,
    )
    m = make_confirmed_match()
    m.prediction = pred
    assert m.prediction is not None
    assert m.prediction.teams[0].code == "USA"
    assert m.prediction.draw_prob is None


def test_match_object_has_no_prep_field() -> None:
    m = make_confirmed_match()
    assert not hasattr(m, "prep")


def test_team_win_prob_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        TeamWinProb(code="USA", name="United States", win_prob=1.5)
