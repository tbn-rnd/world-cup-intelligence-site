import json
from pathlib import Path

import httpx
import pytest
import respx

from backend.odds_client import OddsApiError, OddsClient, normalize_event


def test_normalize_event_extracts_implied_probabilities(fixtures_dir: Path) -> None:
    raw = json.loads((fixtures_dir / "odds_response.json").read_text())[0]
    event = normalize_event(raw)
    assert event.home_team == "South Africa"
    assert event.away_team == "Czech Republic"
    assert 0.0 < event.home_win_prob < 1.0
    assert 0.0 < event.away_win_prob < 1.0
    assert 0.0 < event.draw_prob < 1.0
    total = event.home_win_prob + event.away_win_prob + event.draw_prob
    assert abs(total - 1.0) < 0.001  # vig removed, sums to 1


@respx.mock
def test_client_fetches_and_normalizes(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "odds_response.json").read_text()
    respx.get("https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds").mock(
        return_value=httpx.Response(200, text=raw)
    )
    client = OddsClient(api_key="test-key")
    events = client.fetch()
    assert len(events) == 1
    assert events[0].home_team == "South Africa"


@respx.mock
def test_client_retries_on_5xx(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "odds_response.json").read_text()
    route = respx.get("https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds")
    route.side_effect = [
        httpx.Response(503, text="busy"),
        httpx.Response(503, text="busy"),
        httpx.Response(200, text=raw),
    ]
    client = OddsClient(api_key="test-key", retry_attempts=3, retry_min_seconds=0)
    events = client.fetch()
    assert len(events) == 1


@respx.mock
def test_client_raises_after_exhausting_retries() -> None:
    respx.get("https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds").mock(
        return_value=httpx.Response(503, text="busy")
    )
    client = OddsClient(api_key="test-key", retry_attempts=2, retry_min_seconds=0)
    with pytest.raises(OddsApiError):
        client.fetch()
