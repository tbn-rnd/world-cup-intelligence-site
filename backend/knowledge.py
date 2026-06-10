"""Loader for knowledge/teams.yaml and knowledge/cities.yaml."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    """Allow extra fields — knowledge files are richer than the backend strictly needs."""

    model_config = ConfigDict(extra="allow")


class Diaspora(_Loose):
    population_millions: float
    primary_concentrations: list[str] = Field(default_factory=list)
    georgia_concentration: Literal["low", "moderate", "high"] = "low"


class FanCulture(_Loose):
    travel_propensity: Literal["low", "moderate", "high", "very_high"]


class HospitalityNotes(_Loose):
    fnb_priorities: list[str] = Field(default_factory=list)
    language: list[str] = Field(default_factory=list)
    dietary: Literal["standard", "halal", "kosher", "vegetarian_strong", "other"] = "standard"
    rate_signal: str = ""


class TeamProfile(_Loose):
    name: str
    fifa_rank: int
    us_diaspora: Diaspora
    fan_culture: FanCulture
    hospitality_notes: HospitalityNotes


class CityProfile(_Loose):
    venue: str
    venue_address: str = ""
    diaspora_strengths: list[str] = Field(default_factory=list)
    transport_notes: str = ""


class KnowledgeBase(BaseModel):
    teams: dict[str, TeamProfile]
    cities: dict[str, CityProfile]


def load_knowledge(knowledge_dir: Path) -> KnowledgeBase:
    teams_raw = yaml.safe_load((knowledge_dir / "teams.yaml").read_text())
    cities_raw = yaml.safe_load((knowledge_dir / "cities.yaml").read_text())
    teams = {
        code: TeamProfile.model_validate(profile)
        for code, profile in teams_raw["teams"].items()
    }
    cities = {
        name: CityProfile.model_validate(profile)
        for name, profile in cities_raw["cities"].items()
    }
    return KnowledgeBase(teams=teams, cities=cities)
