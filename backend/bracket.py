"""Loader for knowledge/bracket_2026.yaml + structural feeder resolution."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel


class PhaseWindow(BaseModel):
    starts: date
    ends: date


@dataclass(frozen=True)
class FeederGroupWinner:
    group: str


@dataclass(frozen=True)
class FeederGroupRunnerUp:
    group: str


@dataclass(frozen=True)
class FeederBestThirdPlace:
    eligible_groups: tuple[str, ...]


@dataclass(frozen=True)
class FeederR32Winner:
    slot: str


@dataclass(frozen=True)
class FeederQfWinner:
    slot: str


@dataclass(frozen=True)
class FeederSfLoser:
    slot: str


Feeder = (
    FeederGroupWinner
    | FeederGroupRunnerUp
    | FeederBestThirdPlace
    | FeederR32Winner
    | FeederQfWinner
    | FeederSfLoser
)


def _parse_feeder(d: dict[str, object]) -> Feeder:
    t = d["type"]
    match t:
        case "group_winner":
            return FeederGroupWinner(group=str(d["group"]))
        case "group_runner_up":
            return FeederGroupRunnerUp(group=str(d["group"]))
        case "best_third_place":
            raw = d["eligible_groups"]
            assert isinstance(raw, list)
            return FeederBestThirdPlace(eligible_groups=tuple(str(g) for g in raw))
        case "r32_winner":
            return FeederR32Winner(slot=str(d["slot"]))
        case "qf_winner":
            return FeederQfWinner(slot=str(d["slot"]))
        case "sf_loser":
            return FeederSfLoser(slot=str(d["slot"]))
        case _:
            raise ValueError(f"unknown feeder type: {t}")


class Bracket(BaseModel):
    phases: dict[str, PhaseWindow]
    groups: dict[str, list[str]]
    slots: dict[str, list[dict[str, object]]]

    def feeders_for_slot(self, slot: str) -> list[Feeder]:
        if slot not in self.slots:
            raise KeyError(slot)
        return [_parse_feeder(f) for f in self.slots[slot]]

    def phase_for_date(self, d: date) -> str:
        for name, window in self.phases.items():
            if window.starts <= d <= window.ends:
                return name
        raise ValueError(f"date {d} outside any tournament phase")


def load_bracket(path: Path) -> Bracket:
    raw: dict[str, object] = yaml.safe_load(path.read_text())
    assert isinstance(raw, dict)

    raw_phases = raw["phases"]
    assert isinstance(raw_phases, dict)
    phases = {name: PhaseWindow(**w) for name, w in raw_phases.items()}

    raw_groups = raw["groups"]
    assert isinstance(raw_groups, dict)
    groups = {name: data["teams"] for name, data in raw_groups.items()}

    raw_slots = raw["slots"]
    assert isinstance(raw_slots, dict)
    slots = {name: data["feeders"] for name, data in raw_slots.items()}

    return Bracket(phases=phases, groups=groups, slots=slots)
