import json
from pathlib import Path

import pytest

from backend.groups import GroupAdvanceProbs, derive_group_probs
from backend.odds_client import NormalizedEvent


def _load_fixture(fixtures_dir: Path, name: str) -> list[NormalizedEvent]:
    raw = json.loads((fixtures_dir / name).read_text())
    return [NormalizedEvent(**e) for e in raw]


def test_complete_group_yields_consistent_distributions(fixtures_dir: Path) -> None:
    events = _load_fixture(fixtures_dir, "group_odds_complete.json")
    teams = ["MEX", "KOR", "JAM", "NOR"]
    name_to_code = {
        "Mexico": "MEX",
        "South Korea": "KOR",
        "Jamaica": "JAM",
        "Norway": "NOR",
    }

    probs = derive_group_probs(
        group_name="A", teams=teams, name_to_code=name_to_code, events=events
    )

    assert isinstance(probs, GroupAdvanceProbs)
    assert set(probs.win_probs.keys()) == set(teams)
    assert set(probs.runner_up_probs.keys()) == set(teams)
    assert set(probs.third_place_probs.keys()) == set(teams)

    for team in teams:
        total = (
            probs.win_probs[team]
            + probs.runner_up_probs[team]
            + probs.third_place_probs[team]
            + probs.fourth_place_probs[team]
        )
        assert abs(total - 1.0) < 0.001, f"{team} placement probs should sum to 1, got {total}"

    assert abs(sum(probs.win_probs.values()) - 1.0) < 0.001
    assert abs(sum(probs.runner_up_probs.values()) - 1.0) < 0.001
    assert abs(sum(probs.third_place_probs.values()) - 1.0) < 0.001
    assert abs(sum(probs.fourth_place_probs.values()) - 1.0) < 0.001

    winner_ranking = sorted(probs.win_probs.items(), key=lambda kv: kv[1], reverse=True)
    assert winner_ranking[0][0] == "MEX"


def test_missing_match_falls_back_to_uniform_for_that_match(fixtures_dir: Path) -> None:
    events = _load_fixture(fixtures_dir, "group_odds_complete.json")
    partial_events = events[:-1]
    teams = ["MEX", "KOR", "JAM", "NOR"]
    name_to_code = {
        "Mexico": "MEX",
        "South Korea": "KOR",
        "Jamaica": "JAM",
        "Norway": "NOR",
    }

    probs = derive_group_probs(
        group_name="A", teams=teams, name_to_code=name_to_code, events=partial_events
    )

    for team in teams:
        total = (
            probs.win_probs[team]
            + probs.runner_up_probs[team]
            + probs.third_place_probs[team]
            + probs.fourth_place_probs[team]
        )
        assert abs(total - 1.0) < 0.001


def test_no_matches_returns_uniform_probs(fixtures_dir: Path) -> None:
    teams = ["MEX", "KOR", "JAM", "NOR"]
    name_to_code: dict[str, str] = {}

    probs = derive_group_probs(group_name="A", teams=teams, name_to_code=name_to_code, events=[])

    for team in teams:
        assert abs(probs.win_probs[team] - 0.25) < 0.001
        assert abs(probs.runner_up_probs[team] - 0.25) < 0.001


def test_unknown_team_codes_are_skipped(fixtures_dir: Path) -> None:
    teams = ["MEX", "TBD_A2", "TBD_A3", "TBD_A4"]
    name_to_code = {"Mexico": "MEX"}

    probs = derive_group_probs(group_name="A", teams=teams, name_to_code=name_to_code, events=[])

    assert set(probs.win_probs.keys()) == set(teams)
    for team in teams:
        assert abs(probs.win_probs[team] - 0.25) < 0.001


def test_raises_for_group_with_wrong_team_count() -> None:
    with pytest.raises(ValueError, match="exactly 4 teams"):
        derive_group_probs(
            group_name="A",
            teams=["MEX", "KOR", "JAM"],
            name_to_code={},
            events=[],
        )
