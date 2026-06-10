"""Deterministic confidence grading rule for match states."""

from typing import Literal

Confidence = Literal["certain", "high", "medium", "low"]


def grade_confidence(
    *,
    status: Literal["confirmed", "tbd"],
    days_to_decision: int | None,
    groups_resolved: bool,
) -> Confidence:
    if status == "confirmed":
        return "certain"
    if not groups_resolved:
        return "low"
    if days_to_decision is None:
        return "low"
    if days_to_decision <= 3:
        return "high"
    if days_to_decision <= 10:
        return "medium"
    return "low"
