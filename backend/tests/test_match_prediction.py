from backend.match_prediction import predict_from_fifa_rank
from backend.schema import ConfirmedTeam, Phase


def _team(code: str, rank: int) -> ConfirmedTeam:
    return ConfirmedTeam(code=code, name=code, fifa_rank=rank)


def test_group_stage_has_draw_and_sums_to_one() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 5), _team("BBB", 30), Phase.GROUP_STAGE)
    assert pred.draw_prob is not None
    total = pred.teams[0].win_prob + pred.teams[1].win_prob + pred.draw_prob
    assert abs(total - 1.0) < 1e-9


def test_favorite_has_higher_win_prob() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 5), _team("BBB", 30), Phase.GROUP_STAGE)
    assert pred.teams[0].win_prob > pred.teams[1].win_prob


def test_even_teams_have_equal_win_prob_and_max_draw() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 12), _team("BBB", 12), Phase.GROUP_STAGE)
    assert abs(pred.teams[0].win_prob - pred.teams[1].win_prob) < 1e-9
    assert pred.draw_prob is not None
    assert abs(pred.draw_prob - 0.30) < 1e-9


def test_knockout_has_no_draw_and_sums_to_one() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 5), _team("BBB", 30), Phase.ROUND_OF_16)
    assert pred.draw_prob is None
    total = pred.teams[0].win_prob + pred.teams[1].win_prob
    assert abs(total - 1.0) < 1e-9


def test_symmetry() -> None:
    ab = predict_from_fifa_rank(_team("AAA", 8), _team("BBB", 25), Phase.ROUND_OF_16)
    ba = predict_from_fifa_rank(_team("BBB", 25), _team("AAA", 8), Phase.ROUND_OF_16)
    assert abs(ab.teams[0].win_prob - ba.teams[1].win_prob) < 1e-9


def test_method_label() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 5), _team("BBB", 30), Phase.FINAL)
    assert pred.method == "fifa_rank_elo"


def test_friendly_phase_has_draw() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 5), _team("BBB", 30), Phase.FRIENDLY)
    assert pred.draw_prob is not None


def test_unequal_teams_have_suppressed_draw() -> None:
    pred = predict_from_fifa_rank(_team("AAA", 5), _team("BBB", 30), Phase.GROUP_STAGE)
    assert pred.draw_prob is not None
    assert pred.draw_prob < 0.30
