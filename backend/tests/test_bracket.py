from datetime import date
from pathlib import Path

import pytest

from backend.bracket import (
    FeederGroupRunnerUp,
    FeederGroupWinner,
    load_bracket,
)


def test_loads_phases_with_dates(knowledge_dir: Path) -> None:
    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    assert b.phases["group_stage"].starts == date(2026, 6, 11)
    assert b.phases["group_stage"].ends == date(2026, 6, 27)


def test_resolves_r32_match_76_feeders(knowledge_dir: Path) -> None:
    # FIFA bracket M76 (Houston, Jun 29): C1 vs F2.
    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    feeders = b.feeders_for_slot("r32_match_76")
    assert len(feeders) == 2
    assert isinstance(feeders[0], FeederGroupWinner)
    assert feeders[0].group == "C"
    assert isinstance(feeders[1], FeederGroupRunnerUp)
    assert feeders[1].group == "F"


def test_unknown_slot_raises(knowledge_dir: Path) -> None:
    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    with pytest.raises(KeyError):
        b.feeders_for_slot("not_a_slot")


def test_phase_for_date_returns_group_stage_in_june(knowledge_dir: Path) -> None:
    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    assert b.phase_for_date(date(2026, 6, 20)) == "group_stage"
    assert b.phase_for_date(date(2026, 7, 5)) == "round_of_16"
