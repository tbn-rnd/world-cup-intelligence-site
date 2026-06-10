from backend.bracket import FeederGroupRunnerUp, FeederGroupWinner
from backend.probabilities import GroupAdvanceProbs, compute_top5_for_slot


def test_compute_top5_for_group_winner_x_group_runner_up() -> None:
    group_a = GroupAdvanceProbs(
        win_probs={"MEX": 0.55, "BRA": 0.25, "URU": 0.15, "JAM": 0.05},
        runner_up_probs={"MEX": 0.20, "BRA": 0.35, "URU": 0.30, "JAM": 0.15},
    )
    group_f = GroupAdvanceProbs(
        win_probs={"JPN": 0.40, "SWE": 0.30, "CIV": 0.20, "TBD_F4": 0.10},
        runner_up_probs={"JPN": 0.30, "SWE": 0.35, "CIV": 0.25, "TBD_F4": 0.10},
    )

    result = compute_top5_for_slot(
        feeders=[FeederGroupWinner(group="A"), FeederGroupRunnerUp(group="F")],
        group_probs={"A": group_a, "F": group_f},
        previous_top5={},
    )

    assert len(result.scenarios) == 5
    probs = [s.probability for s in result.scenarios]
    assert probs == sorted(probs, reverse=True)
    assert sum(probs) <= 1.0
    assert result.scenarios[0].team_a_code == "MEX"


def test_delta_pp_computed_against_previous() -> None:
    group_a = GroupAdvanceProbs(
        win_probs={"MEX": 0.55, "BRA": 0.25, "URU": 0.15, "JAM": 0.05},
        runner_up_probs={"MEX": 0.20, "BRA": 0.35, "URU": 0.30, "JAM": 0.15},
    )
    group_f = GroupAdvanceProbs(
        win_probs={"JPN": 0.40, "SWE": 0.30, "CIV": 0.20, "TBD_F4": 0.10},
        runner_up_probs={"JPN": 0.30, "SWE": 0.35, "CIV": 0.25, "TBD_F4": 0.10},
    )
    previous = {("MEX", "JPN"): 0.20, ("MEX", "SWE"): 0.15}
    result = compute_top5_for_slot(
        feeders=[FeederGroupWinner(group="A"), FeederGroupRunnerUp(group="F")],
        group_probs={"A": group_a, "F": group_f},
        previous_top5=previous,
    )
    mex_jpn = next(s for s in result.scenarios if s.team_a_code == "MEX" and s.team_b_code == "JPN")
    expected_delta = (mex_jpn.probability - 0.20) * 100
    assert abs(mex_jpn.delta_pp - expected_delta) < 0.01


def test_best_third_place_distribution_uses_eligible_group_thirds() -> None:
    """When eligible_groups are specified, the distribution favors high-3rd-place groups."""
    group_a = GroupAdvanceProbs(
        win_probs={"MEX": 0.55, "BRA": 0.25, "URU": 0.15, "JAM": 0.05},
        runner_up_probs={"MEX": 0.20, "BRA": 0.35, "URU": 0.30, "JAM": 0.15},
        third_place_probs={"MEX": 0.15, "BRA": 0.25, "URU": 0.30, "JAM": 0.30},
        fourth_place_probs={"MEX": 0.10, "BRA": 0.15, "URU": 0.25, "JAM": 0.50},
    )
    group_b = GroupAdvanceProbs(
        win_probs={"ENG": 0.50, "WAL": 0.20, "IRN": 0.20, "USA": 0.10},
        runner_up_probs={"ENG": 0.25, "WAL": 0.30, "IRN": 0.25, "USA": 0.20},
        third_place_probs={"ENG": 0.15, "WAL": 0.25, "IRN": 0.30, "USA": 0.30},
        fourth_place_probs={"ENG": 0.10, "WAL": 0.25, "IRN": 0.25, "USA": 0.40},
    )

    from backend.bracket import FeederBestThirdPlace
    from backend.probabilities import _team_distribution_for_feeder
    feeder = FeederBestThirdPlace(eligible_groups=("A", "B"))

    distribution = _team_distribution_for_feeder(
        feeder, {"A": group_a, "B": group_b}
    )

    assert set(distribution.keys()) == {"MEX", "BRA", "URU", "JAM", "ENG", "WAL", "IRN", "USA"}
    assert abs(sum(distribution.values()) - 1.0) < 0.001
    # URU has third_place=0.30, MEX has third_place=0.15 — URU should weight higher
    assert distribution["URU"] > distribution["MEX"]
