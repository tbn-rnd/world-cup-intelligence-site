"""Loader for knowledge/fixtures_2026.yaml — replaces backend/inventory.py."""

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

HostCity = Literal[
    "Atlanta", "NY/NJ", "Miami", "Mexico City", "Guadalajara", "Monterrey",
    "Toronto", "Vancouver", "Boston", "Dallas", "Houston", "Kansas City",
    "Los Angeles", "Philadelphia", "San Francisco Bay Area", "Seattle",
]


class FixtureMatch(BaseModel):
    id: str
    kickoff_local: str
    kickoff_utc: datetime
    host_city: HostCity
    venue: str
    phase: str
    status: Literal["confirmed", "tbd"]
    confirmed_teams: list[str] = Field(default_factory=list)
    group: str | None = None
    bracket_slot: str | None = None
    decision_date: str | None = None


def load_fixtures(path: Path) -> list[FixtureMatch]:
    raw = yaml.safe_load(path.read_text())
    matches = [FixtureMatch.model_validate(m) for m in raw["matches"]]
    matches.sort(key=lambda m: m.kickoff_utc)
    return matches
