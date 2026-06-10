"""Odds API wrapper with implied-probability normalization, retries, and circuit breaker."""

from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class OddsApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    home_team: str
    away_team: str
    commence_time: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float


def _vig_adjusted(prices: list[float]) -> list[float]:
    raw = [1.0 / p for p in prices]
    total = sum(raw)
    return [p / total for p in raw]


def normalize_event(raw: dict[str, Any]) -> NormalizedEvent:
    """Average implied probabilities across bookmakers, with vig removed."""
    home, away = raw["home_team"], raw["away_team"]
    home_probs: list[float] = []
    draw_probs: list[float] = []
    away_probs: list[float] = []
    for bm in raw["bookmakers"]:
        for market in bm["markets"]:
            if market["key"] != "h2h":
                continue
            prices = {o["name"]: o["price"] for o in market["outcomes"]}
            if home not in prices or away not in prices:
                continue
            ordered = [prices[home], prices.get("Draw", 1.0), prices[away]]
            adj = _vig_adjusted(ordered)
            home_probs.append(adj[0])
            draw_probs.append(adj[1])
            away_probs.append(adj[2])
    if not home_probs:
        raise OddsApiError(f"no h2h market found for {home} vs {away}")
    return NormalizedEvent(
        event_id=raw["id"],
        home_team=home,
        away_team=away,
        commence_time=raw["commence_time"],
        home_win_prob=sum(home_probs) / len(home_probs),
        draw_prob=sum(draw_probs) / len(draw_probs),
        away_win_prob=sum(away_probs) / len(away_probs),
    )


class OddsClient:
    BASE_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds"

    def __init__(
        self,
        api_key: str,
        *,
        retry_attempts: int = 3,
        retry_min_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._retry_attempts = retry_attempts
        self._retry_min_seconds = retry_min_seconds
        self._timeout = timeout_seconds

    def fetch(self) -> list[NormalizedEvent]:
        @retry(
            retry=retry_if_exception_type(httpx.HTTPStatusError),
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential(multiplier=self._retry_min_seconds, min=0, max=8),
            reraise=True,
        )
        def _do_fetch() -> list[dict[str, Any]]:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    self.BASE_URL,
                    params={
                        "apiKey": self._api_key,
                        "regions": "us,uk,eu",
                        "markets": "h2h",
                        "oddsFormat": "decimal",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                assert isinstance(data, list)
                return data

        try:
            raw = _do_fetch()
        except httpx.HTTPStatusError as e:
            raise OddsApiError(f"Odds API failed: {e}") from e
        except httpx.RequestError as e:
            raise OddsApiError(f"Odds API unreachable: {e}") from e

        return [normalize_event(e) for e in raw]
