"""Pydantic models for matches.json — the single source of truth contract."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class DataFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNREACHABLE = "unreachable"


class TournamentPhase(StrEnum):
    PRE_TOURNAMENT = "pre_tournament"
    GROUP_STAGE = "group_stage"
    ROUND_OF_32 = "round_of_32"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINALS = "quarter_finals"
    SEMI_FINALS = "semi_finals"
    FINALS = "finals"


class Phase(StrEnum):
    FRIENDLY = "friendly"
    GROUP_STAGE = "group_stage"
    ROUND_OF_32 = "round_of_32"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    BRONZE_FINAL = "bronze_final"
    FINAL = "final"


class Status(StrEnum):
    CONFIRMED = "confirmed"
    TBD = "tbd"


Confidence = Literal["certain", "high", "medium", "low"]
PopularityTier = Literal["popular", "moderate", "standard"]


class Popularity(BaseModel):
    tier: PopularityTier
    rationale: str


class ConfirmedTeam(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str
    fifa_rank: int


class TeamRef(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str


class TbdScenario(BaseModel):
    rank: Annotated[int, Field(ge=1, le=3)]
    team_a: TeamRef
    team_b: TeamRef
    probability: Annotated[float, Field(ge=0.0, le=1.0)]
    delta_pp: float
    rationale: str


class FeederTeam(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str
    probability: Annotated[float, Field(ge=0.0, le=1.0)]


class FeederDistribution(BaseModel):
    label: str
    teams: list[FeederTeam]


class TeamsBlock(BaseModel):
    confirmed: list[ConfirmedTeam] | None = None
    tbd_scenarios: list[TbdScenario] | None = None
    feeder_distributions: list[FeederDistribution] | None = None


class Brief(BaseModel):
    headline: str
    scenario_summary: str | None
    fan_demographics: str
    traveling_volume_est: str
    cultural_context: str


class TeamWinProb(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str
    win_prob: Annotated[float, Field(ge=0.0, le=1.0)]


class MatchPrediction(BaseModel):
    method: Literal["fifa_rank_elo"]
    teams: Annotated[list[TeamWinProb], Field(min_length=2, max_length=2)]
    draw_prob: Annotated[float, Field(ge=0.0, le=1.0)] | None = None


class MatchObject(BaseModel):
    id: str
    kickoff_utc: datetime
    kickoff_local: str
    host_city: str
    venue: str
    phase: Phase
    status: Status
    popularity: Popularity
    confidence: Confidence
    teams: TeamsBlock
    signature: str
    brief: Brief | None = None
    prediction: MatchPrediction | None = None
    decision_date: str | None = None
    days_to_decision: int | None = None

    @model_validator(mode="after")
    def _teams_block_matches_status(self) -> MatchObject:
        if self.status == Status.CONFIRMED:
            if self.teams.confirmed is None or len(self.teams.confirmed) != 2:
                raise ValueError(
                    "confirmed match requires exactly 2 entries in teams.confirmed"
                )
            if self.teams.tbd_scenarios is not None:
                raise ValueError("confirmed match must have teams.tbd_scenarios=None")
            if self.teams.feeder_distributions is not None:
                raise ValueError("confirmed match must have teams.feeder_distributions=None")
        else:  # TBD
            if self.teams.tbd_scenarios is None or len(self.teams.tbd_scenarios) != 3:
                raise ValueError(
                    "TBD match requires exactly 3 entries in teams.tbd_scenarios"
                )
            if self.teams.confirmed is not None:
                raise ValueError("TBD match must have teams.confirmed=None")
        return self


class MatchesFile(BaseModel):
    generated_at: datetime
    data_freshness: DataFreshness
    tournament_phase: TournamentPhase
    matches: Annotated[list[MatchObject], Field(min_length=1, max_length=104)]
