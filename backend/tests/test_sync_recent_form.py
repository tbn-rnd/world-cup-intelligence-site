"""Tests for backend.sync_recent_form.

Focused on the pure functions that don't need to mock api-football or Claude.
The end-to-end pipeline is intentionally not tested here — the real api-football
response shapes are verified at first workflow_dispatch run instead.
"""

from __future__ import annotations

from backend.sync_recent_form import (
    _normalize_team_name,
    format_fixtures_for_prompt,
    resolve_team_id_from_roster,
    update_summaries_in_yaml,
)


def test_update_summaries_in_yaml_replaces_target_team_only() -> None:
    text = (
        "teams:\n"
        "\n"
        "  MAR:\n"
        "    name: Morocco\n"
        "    fifa_rank: 14\n"
        '    recent_form_summary: "old morocco summary"\n'
        "\n"
        "  USA:\n"
        "    name: United States\n"
        "    fifa_rank: 16\n"
        '    recent_form_summary: "old usa summary"\n'
    )
    result = update_summaries_in_yaml(text, {"USA": "new usa summary"})
    assert '"old morocco summary"' in result
    assert '"new usa summary"' in result
    assert '"old usa summary"' not in result


def test_update_summaries_in_yaml_preserves_comments_and_blank_lines() -> None:
    text = (
        "# top-level comment\n"
        "teams:\n"
        "\n"
        "  # block comment for Morocco\n"
        "  MAR:\n"
        "    name: Morocco\n"
        '    recent_form_summary: "old"\n'
        "\n"
    )
    result = update_summaries_in_yaml(text, {"MAR": "new summary"})
    assert "# top-level comment" in result
    assert "# block comment for Morocco" in result
    assert '"new summary"' in result
    # Blank-line spacing between block comment and the team key should survive.
    assert "\n\n" in result


def test_update_summaries_in_yaml_escapes_special_chars() -> None:
    text = "teams:\n  MAR:\n    name: Morocco\n    recent_form_summary: \"old\"\n"
    nasty = 'has "quotes" and a \\ backslash'
    result = update_summaries_in_yaml(text, {"MAR": nasty})
    # JSON encoding produces a YAML-flow-safe scalar.
    assert r'"has \"quotes\" and a \\ backslash"' in result


def test_update_summaries_in_yaml_noop_when_team_missing() -> None:
    text = "teams:\n  MAR:\n    name: Morocco\n    recent_form_summary: \"old\"\n"
    result = update_summaries_in_yaml(text, {"USA": "unrelated"})
    assert result == text


def test_normalize_team_name_strips_punct_and_case() -> None:
    assert _normalize_team_name("United States") == "unitedstates"
    assert _normalize_team_name("USA") == "usa"
    assert _normalize_team_name("Côte d'Ivoire") == "côtedivoire"
    assert _normalize_team_name("DR Congo") == "drcongo"


def test_resolve_team_id_from_roster_exact_name_match() -> None:
    roster = {"brazil": 6, "argentina": 26}
    assert resolve_team_id_from_roster("Brazil", "BRA", roster) == 6


def test_resolve_team_id_from_roster_falls_back_to_code() -> None:
    # api-football's WC roster names "USA", not "United States".
    roster = {"usa": 2384, "brazil": 6}
    assert resolve_team_id_from_roster("United States", "USA", roster) == 2384


def test_resolve_team_id_from_roster_uses_alias_when_present() -> None:
    # _NAME_ALIASES has "United States" → "USA" already, so reuse it as a check.
    roster = {"usa": 2384}
    assert resolve_team_id_from_roster("United States", "XXX", roster) == 2384


def test_resolve_team_id_from_roster_returns_none_when_all_miss() -> None:
    roster = {"brazil": 6}
    assert resolve_team_id_from_roster("Atlantis", "ATL", roster) is None


def test_format_fixtures_handles_missing_fields() -> None:
    fixtures = [
        {
            "fixture": {"date": "2026-03-22T19:00:00+00:00", "status": {"short": "FT"}},
            "league": {"name": "Friendlies"},
            "teams": {"home": {"name": "Mexico"}, "away": {"name": "Brazil"}},
            "goals": {"home": 2, "away": 1},
        },
        # Missing nested fields — should render as ? rather than crash.
        {},
    ]
    output = format_fixtures_for_prompt(fixtures)
    assert "2026-03-22 (Friendlies): Mexico 2-1 Brazil [FT]" in output
    assert "? ?-? ?" in output
