from backend.confidence import grade_confidence


def test_confirmed_match_is_certain() -> None:
    result = grade_confidence(
        status="confirmed", days_to_decision=None, groups_resolved=False
    )
    assert result == "certain"


def test_r32_within_three_days_with_groups_resolved_is_high() -> None:
    assert grade_confidence(status="tbd", days_to_decision=3, groups_resolved=True) == "high"


def test_r16_with_seven_days_to_decision_is_medium() -> None:
    assert grade_confidence(status="tbd", days_to_decision=7, groups_resolved=True) == "medium"


def test_semi_far_from_decision_is_low() -> None:
    assert grade_confidence(status="tbd", days_to_decision=15, groups_resolved=True) == "low"


def test_groups_unresolved_caps_at_low() -> None:
    assert grade_confidence(status="tbd", days_to_decision=2, groups_resolved=False) == "low"


def test_confirmed_match_is_certain_even_with_groups_resolved() -> None:
    result = grade_confidence(status="confirmed", days_to_decision=None, groups_resolved=True)
    assert result == "certain"
