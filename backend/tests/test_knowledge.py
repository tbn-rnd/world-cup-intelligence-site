from pathlib import Path

import pytest

from backend.knowledge import load_knowledge


def test_loads_required_teams(knowledge_dir: Path) -> None:
    kb = load_knowledge(knowledge_dir)
    required = {"MAR", "HAI", "USA", "POR", "RSA", "CZE", "UZB", "COD"}
    assert required.issubset(kb.teams.keys())


def test_team_has_fifa_rank_and_diaspora(knowledge_dir: Path) -> None:
    kb = load_knowledge(knowledge_dir)
    morocco = kb.teams["MAR"]
    assert morocco.name == "Morocco"
    assert morocco.fifa_rank == 14
    assert morocco.us_diaspora.population_millions > 0


def test_loads_three_cities(knowledge_dir: Path) -> None:
    kb = load_knowledge(knowledge_dir)
    assert set(kb.cities.keys()) == {"Atlanta", "NY/NJ", "Miami"}


def test_unknown_team_raises_keyerror(knowledge_dir: Path) -> None:
    kb = load_knowledge(knowledge_dir)
    with pytest.raises(KeyError):
        _ = kb.teams["XXX"]
