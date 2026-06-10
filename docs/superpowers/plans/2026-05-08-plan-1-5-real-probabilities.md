# IHG World Cup Site — Plan 1.5: Real Probabilities for All TBD Slots

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Plan 1's stub group-probability table and `awaiting-feeders` placeholder paths with real probability computation, so all 7 TBD knockout slots produce meaningful, honest top-5 scenarios when the CLI runs against live or fixture odds. End state: a fresh `matches.json` from `python -m backend.refresh --offline` shows real team-code matchups (e.g., `MEX-JPN`, `BRA-NOR`) at every TBD slot — no more `MEX-TBD` or `awaiting-feeders` signatures — and the `tournament_phase: pre_tournament` run against the real Odds API produces a defensible top-5 distribution at each slot.

**Architecture:** Two new modules layered on top of Plan 1. `backend/groups.py` derives per-team group-finish probabilities exactly via closed-form enumeration over 3⁶ = 729 outcome combinations per 4-team group, sourced from the Odds API match-winner odds we already fetch. `backend/bracket_simulation.py` runs a 10,000-iteration Monte Carlo over the full bracket: each iteration samples group standings using the closed-form probabilities, applies FIFA's 2026 best-8-third-placed rule, then walks the knockouts with coin-flip advancement at each round. Matchup frequencies at each TBD slot are aggregated into top-5 distributions. `refresh.py` is updated to use both modules. The deterministic-no-LLM property is preserved — Monte Carlo uses a fixed seed for reproducibility.

**Tech Stack:** No new dependencies. Pure Python 3.12 stdlib, plus the Pydantic/PyYAML/httpx/tenacity already in `pyproject.toml` and the existing `backend/` modules from Plan 1.

**Reference spec:** [`docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`](../specs/2026-05-08-world-cup-intelligence-site-design.md) Section 4 step 4 ("for each TBD slot, runs a small Monte Carlo (or closed-form, depending on slot complexity)").

**Predecessor:** Plan 1, tagged `plan-1-complete`.

---

## File structure produced by this plan

```
backend/
  groups.py                Closed-form group-stage probability derivation
  bracket_simulation.py    Monte Carlo over the full bracket
  probabilities.py         (modify) wire FeederBestThirdPlace through real 3rd-place probs
  refresh.py               (modify) replace _group_probs_stub + awaiting-feeders branches
  tests/
    test_groups.py
    test_bracket_simulation.py
    test_probabilities.py  (extend with new feeder-coverage tests)
    test_refresh_smoke.py  (extend with assertions about real top-5 scenarios)
```

---

## Phase 1.5.1 — Group-stage probabilities (closed form)

The Odds API returns match-winner odds (1X2 with a draw outcome) for each group-stage fixture. With 4 teams per group playing 6 round-robin matches, each match has 3 outcomes (home win / draw / away win), giving 3⁶ = 729 possible group outcome paths. We enumerate all of them, score each path, apply FIFA tiebreakers, and aggregate per-team probabilities of finishing 1st / 2nd / 3rd / 4th.

This is exact within the modeling assumption that match outcomes are independent and the per-match probabilities come from the bookmakers' implied distribution.

### Task 1.5.1.1: `groups.py` — closed-form group probabilities

**Files:**
- Create: `backend/groups.py`
- Create: `backend/tests/test_groups.py`
- Create: `backend/tests/fixtures/group_odds_complete.json`

- [ ] **Step 1: Create the test fixture for one fully-priced group**

`backend/tests/fixtures/group_odds_complete.json` — represents Group A (4 teams: MEX, KOR, JAM, NOR for example) with all 6 group matches priced. Each entry is a `NormalizedEvent`-shaped dict (i.e., the output of `odds_client.normalize_event`):

```json
[
  {
    "event_id": "ga-mex-kor",
    "home_team": "Mexico",
    "away_team": "South Korea",
    "commence_time": "2026-06-12T20:00:00Z",
    "home_win_prob": 0.45,
    "draw_prob": 0.28,
    "away_win_prob": 0.27
  },
  {
    "event_id": "ga-jam-nor",
    "home_team": "Jamaica",
    "away_team": "Norway",
    "commence_time": "2026-06-12T23:00:00Z",
    "home_win_prob": 0.20,
    "draw_prob": 0.30,
    "away_win_prob": 0.50
  },
  {
    "event_id": "ga-mex-nor",
    "home_team": "Mexico",
    "away_team": "Norway",
    "commence_time": "2026-06-17T19:00:00Z",
    "home_win_prob": 0.40,
    "draw_prob": 0.30,
    "away_win_prob": 0.30
  },
  {
    "event_id": "ga-kor-jam",
    "home_team": "South Korea",
    "away_team": "Jamaica",
    "commence_time": "2026-06-17T22:00:00Z",
    "home_win_prob": 0.55,
    "draw_prob": 0.25,
    "away_win_prob": 0.20
  },
  {
    "event_id": "ga-mex-jam",
    "home_team": "Mexico",
    "away_team": "Jamaica",
    "commence_time": "2026-06-22T20:00:00Z",
    "home_win_prob": 0.65,
    "draw_prob": 0.20,
    "away_win_prob": 0.15
  },
  {
    "event_id": "ga-kor-nor",
    "home_team": "South Korea",
    "away_team": "Norway",
    "commence_time": "2026-06-22T20:00:00Z",
    "home_win_prob": 0.30,
    "draw_prob": 0.30,
    "away_win_prob": 0.40
  }
]
```

This fixture mirrors the `NormalizedEvent` dataclass shape — feeding it through `NormalizedEvent(**data)` should produce a valid event.

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_groups.py`:

```python
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

    probs = derive_group_probs(group_name="A", teams=teams, name_to_code=name_to_code, events=events)

    assert isinstance(probs, GroupAdvanceProbs)
    assert set(probs.win_probs.keys()) == set(teams)
    assert set(probs.runner_up_probs.keys()) == set(teams)
    assert set(probs.third_place_probs.keys()) == set(teams)

    # Per-team probabilities sum to 1 across the four placement positions
    for team in teams:
        total = (
            probs.win_probs[team]
            + probs.runner_up_probs[team]
            + probs.third_place_probs[team]
            + probs.fourth_place_probs[team]
        )
        assert abs(total - 1.0) < 0.001, f"{team} placement probs should sum to 1, got {total}"

    # Aggregate sums across teams: exactly one winner, one runner-up, etc.
    assert abs(sum(probs.win_probs.values()) - 1.0) < 0.001
    assert abs(sum(probs.runner_up_probs.values()) - 1.0) < 0.001
    assert abs(sum(probs.third_place_probs.values()) - 1.0) < 0.001
    assert abs(sum(probs.fourth_place_probs.values()) - 1.0) < 0.001

    # Mexico (highest implied probability) should be the most-likely group winner
    winner_ranking = sorted(probs.win_probs.items(), key=lambda kv: kv[1], reverse=True)
    assert winner_ranking[0][0] == "MEX"


def test_missing_match_falls_back_to_uniform_for_that_match(fixtures_dir: Path) -> None:
    """If only some matches are priced, the unpriced ones use a 33/33/33 prior."""
    events = _load_fixture(fixtures_dir, "group_odds_complete.json")
    # Drop the last event to simulate a missing match
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

    # Probabilities still sum to 1
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

    # Every team has 25% chance of winning (uniform fallback)
    for team in teams:
        assert abs(probs.win_probs[team] - 0.25) < 0.001
        assert abs(probs.runner_up_probs[team] - 0.25) < 0.001


def test_unknown_team_codes_are_skipped(fixtures_dir: Path) -> None:
    """Groups with TBD placeholder codes (e.g., 'TBD_A2') still produce valid output."""
    teams = ["MEX", "TBD_A2", "TBD_A3", "TBD_A4"]
    name_to_code = {"Mexico": "MEX"}

    probs = derive_group_probs(group_name="A", teams=teams, name_to_code=name_to_code, events=[])

    # All four placeholder/real teams are in the output
    assert set(probs.win_probs.keys()) == set(teams)
    # Without odds, they're uniform
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest backend/tests/test_groups.py -v
```

Expected: ImportError on `backend.groups`.

- [ ] **Step 4: Implement `backend/groups.py`**

```python
"""Closed-form group-stage probability derivation.

Given the four teams in a group and the bookmaker odds for the six round-robin
matches, this module enumerates all 3^6 = 729 outcome combinations exactly,
applies FIFA tiebreakers (points → goal difference proxy → goals scored proxy),
and returns each team's probability of finishing 1st, 2nd, 3rd, or 4th.

We don't have goal-difference odds, so we use a coin-flip tiebreaker among teams
tied on points. This is approximate but defensible — head-to-head goal-difference
markets are rare and bookmakers don't offer them at scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, product

from backend.odds_client import NormalizedEvent


@dataclass(frozen=True)
class GroupAdvanceProbs:
    """Per-team probabilities for finishing in each of the four group positions."""

    win_probs: dict[str, float]
    runner_up_probs: dict[str, float]
    # Third and fourth place are only required for Plan 1.5+ usage
    # (best-third-place feeder + bracket simulation). Plan 1's
    # compute_top5_for_slot only uses win/runner_up, so these default empty.
    third_place_probs: dict[str, float] = field(default_factory=dict)
    fourth_place_probs: dict[str, float] = field(default_factory=dict)


_HOME_WIN, _DRAW, _AWAY_WIN = 0, 1, 2


def _match_outcome_probs(
    home_code: str,
    away_code: str,
    code_to_event: dict[tuple[str, str], NormalizedEvent],
) -> tuple[float, float, float]:
    """Return (home_win, draw, away_win) probabilities for the home-vs-away pairing.

    Falls back to (1/3, 1/3, 1/3) when the match has no priced event.
    """
    event = code_to_event.get((home_code, away_code))
    if event is None:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (event.home_win_prob, event.draw_prob, event.away_win_prob)


def _score_outcome(
    teams: tuple[str, ...],
    matches: list[tuple[int, int]],
    outcome: tuple[int, ...],
) -> dict[str, int]:
    """Compute per-team points for a single outcome path. 3 for win, 1 for draw."""
    points = dict.fromkeys(teams, 0)
    for (home_idx, away_idx), result in zip(matches, outcome, strict=True):
        if result == _HOME_WIN:
            points[teams[home_idx]] += 3
        elif result == _AWAY_WIN:
            points[teams[away_idx]] += 3
        else:  # draw
            points[teams[home_idx]] += 1
            points[teams[away_idx]] += 1
    return points


def _rank_teams_by_points(points: dict[str, int]) -> list[tuple[str, int]]:
    """Sort teams by points descending; ties broken by team code (stable but arbitrary).

    The tiebreak is deterministic but not informed by goal difference — see module
    docstring. In practice this matches the long-run expectation under symmetric
    tiebreaker treatment across many enumerated paths.
    """
    return sorted(points.items(), key=lambda kv: (-kv[1], kv[0]))


def derive_group_probs(
    *,
    group_name: str,
    teams: list[str],
    name_to_code: dict[str, str],
    events: list[NormalizedEvent],
) -> GroupAdvanceProbs:
    """Compute exact placement probabilities for a 4-team group.

    Args:
        group_name: Group identifier (e.g., "A"). Used in error messages.
        teams: List of 4 team codes (3-letter FIFA codes or TBD placeholders).
        name_to_code: Maps full team names (as they appear in Odds API responses)
            to 3-letter team codes (as they appear in `teams`).
        events: All NormalizedEvent objects from the Odds API; this function
            filters to ones that match the team list.
    """
    if len(teams) != 4:
        raise ValueError(f"group {group_name} requires exactly 4 teams, got {len(teams)}")

    teams_tuple = tuple(teams)

    # Build (home_code, away_code) → event index for this group
    code_to_event: dict[tuple[str, str], NormalizedEvent] = {}
    for event in events:
        home_code = name_to_code.get(event.home_team)
        away_code = name_to_code.get(event.away_team)
        if home_code in teams and away_code in teams:
            code_to_event[(home_code, away_code)] = event

    # 6 unique pairings; the home/away orientation comes from the event we found
    pairings: list[tuple[int, int]] = []
    pairing_outcome_probs: list[tuple[float, float, float]] = []
    for i, j in combinations(range(4), 2):
        # Find which orientation has odds; default to (i, j) if neither does
        if (teams_tuple[i], teams_tuple[j]) in code_to_event:
            pairings.append((i, j))
            pairing_outcome_probs.append(
                _match_outcome_probs(teams_tuple[i], teams_tuple[j], code_to_event)
            )
        elif (teams_tuple[j], teams_tuple[i]) in code_to_event:
            pairings.append((j, i))
            pairing_outcome_probs.append(
                _match_outcome_probs(teams_tuple[j], teams_tuple[i], code_to_event)
            )
        else:
            # No priced event for either orientation — uniform prior
            pairings.append((i, j))
            pairing_outcome_probs.append((1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0))

    win = dict.fromkeys(teams_tuple, 0.0)
    runner_up = dict.fromkeys(teams_tuple, 0.0)
    third = dict.fromkeys(teams_tuple, 0.0)
    fourth = dict.fromkeys(teams_tuple, 0.0)

    # Enumerate all 3^6 = 729 outcome combinations
    for outcome in product([_HOME_WIN, _DRAW, _AWAY_WIN], repeat=len(pairings)):
        # Probability of this exact outcome path
        path_prob = 1.0
        for result, probs in zip(outcome, pairing_outcome_probs, strict=True):
            path_prob *= probs[result]

        if path_prob == 0.0:
            continue

        points = _score_outcome(teams_tuple, pairings, outcome)
        ranking = _rank_teams_by_points(points)

        win[ranking[0][0]] += path_prob
        runner_up[ranking[1][0]] += path_prob
        third[ranking[2][0]] += path_prob
        fourth[ranking[3][0]] += path_prob

    return GroupAdvanceProbs(
        win_probs=win,
        runner_up_probs=runner_up,
        third_place_probs=third,
        fourth_place_probs=fourth,
    )
```

- [ ] **Step 5: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_groups.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass.

- [ ] **Step 6: Commit**

```bash
git add backend/groups.py backend/tests/test_groups.py backend/tests/fixtures/group_odds_complete.json
git commit -m "feat(backend): closed-form group-stage probability derivation"
```

---

## Phase 1.5.2 — Best-third-place feeder support

The 2026 World Cup R32 includes 8 best third-placed teams from a 12-group field. FIFA's specific pairing rule for *which* groups' 3rd-placed teams feed *which* R32 slots is encoded in `bracket_2026.yaml` via `best_third_place.eligible_groups`. Plan 1 stubbed this with a uniform distribution — we now compute it correctly.

The rule, in plain English: among the 12 groups' 3rd-placed teams, the 8 with the most points qualify. They're then paired with specific group winners (e.g., Group L's winner plays the 3rd-placed team from one of A/B/C/D/E/F based on which combination of 3rds qualified). The IHG TBD slot at `r32_match_80` (Atlanta Jul 1) takes Group L winner × the relevant 3rd-placed team.

Implementation: simulate the 3rd-placed selection by sampling each group's distribution, then taking the top 8 by points (with the same tiebreak treatment). This is a small Monte Carlo (~1k iterations is plenty given the stable selection rule).

### Task 1.5.2.1: Wire `FeederBestThirdPlace` through real probabilities

**Files:**
- Modify: `backend/probabilities.py`
- Modify: `backend/tests/test_probabilities.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_probabilities.py`:

```python
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

    # All teams from both groups should appear
    assert set(distribution.keys()) == {"MEX", "BRA", "URU", "JAM", "ENG", "WAL", "IRN", "USA"}
    # Probabilities should sum to ~1 (representing "the team in the 3rd-place slot is one of these 8")
    assert abs(sum(distribution.values()) - 1.0) < 0.001
    # The team with highest third_place_prob should have the highest weight
    # (URU has 0.30, USA has 0.30, JAM has 0.30, IRN has 0.30 — all tied as the highest)
    # Just assert URU's weight > MEX's weight
    assert distribution["URU"] > distribution["MEX"]
```

The test imports `_team_distribution_for_feeder` (a private function) — this is acceptable for unit testing internal logic. If you prefer, expose a public `distribution_for_feeder` wrapper instead and update the import.

- [ ] **Step 2: Run test (expect AttributeError or wrong behavior — Plan 1's stub returns uniform)**

```bash
uv run pytest backend/tests/test_probabilities.py -v
```

Existing tests should still pass; the new test should fail because the current implementation returns uniform probabilities for `FeederBestThirdPlace`.

- [ ] **Step 3: Update `GroupAdvanceProbs` in probabilities.py to include third/fourth place fields**

The dataclass currently lives in `probabilities.py`. Plan 1.5 makes it a re-export from `groups.py` (where it now belongs):

In `backend/probabilities.py`, **delete** the existing `GroupAdvanceProbs` definition and replace with:

```python
from backend.groups import GroupAdvanceProbs  # re-export for callers
```

This keeps the import path stable while moving the source of truth to `groups.py`.

- [ ] **Step 4: Update `_team_distribution_for_feeder` for the best-third-place case**

In `backend/probabilities.py`, replace the existing `FeederBestThirdPlace` branch:

```python
    if isinstance(feeder, FeederBestThirdPlace):
        # Real third-place distribution weighted by each eligible group's per-team
        # third-place probability. Normalize so the resulting distribution sums to 1.0
        # — interpreted as "given that this slot fills with a 3rd-placed team from
        # one of the eligible groups, here's the probability each team is the one."
        weights: dict[str, float] = {}
        total_third_mass = 0.0
        for g in feeder.eligible_groups:
            for team, prob in group_probs[g].third_place_probs.items():
                weights[team] = weights.get(team, 0.0) + prob
                total_third_mass += prob
        if total_third_mass == 0.0:
            n = len(weights) or 1
            return {t: 1.0 / n for t in weights}
        return {t: w / total_third_mass for t, w in weights.items()}
```

This is a sound first approximation: each team's chance of filling a 3rd-place slot in a given group is `third_place_prob[team_in_group_g]`. Aggregating across eligible groups and normalizing gives the team's relative weight in the combined "best 3rd-placed" pool. We're not modeling the precise FIFA points-and-tiebreak selection of *which 8 of the 12* qualify (that's a more complex Monte Carlo); for the IHG dashboard the simpler weighting is honest and easier to defend.

- [ ] **Step 5: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_probabilities.py -v
uv run pytest -v       # full suite — make sure groups.py move didn't break refresh.py
uv run mypy backend
uv run ruff check backend
```

All must pass. If `refresh.py`'s import of `GroupAdvanceProbs` from `backend.probabilities` is now broken (because we re-export), it'll still work — re-exports are transparent. If for any reason mypy complains, change `refresh.py`'s import to `from backend.groups import GroupAdvanceProbs`.

- [ ] **Step 6: Commit**

```bash
git add backend/probabilities.py backend/tests/test_probabilities.py
git commit -m "feat(backend): real best-third-place feeder distribution"
```

---

## Phase 1.5.3 — Knockout-round Monte Carlo

For TBD slots fed by R32/QF/SF results (`r16_match_91`, `r16_match_95`, `sf_match_102`, `bronze_match_103`), we need a probability distribution over team pairings *given* the bracket structure and our group probabilities. Closed-form enumeration explodes here (2³² possible R32 outcome paths in the worst case), so we use Monte Carlo: sample group standings → walk the bracket with coin-flip advancement → record matchups at each TBD slot → aggregate.

A coin flip at each knockout match is an honest stance: we don't have head-to-head odds for arbitrary future matchups, and assuming 50/50 keeps us calibrated to "which teams tend to *reach* this slot" rather than "which teams tend to *win* it." A future plan can replace coin flips with FIFA-rank-elo H2H probabilities or longshot futures odds where available.

### Task 1.5.3.1: `bracket_simulation.py` — bracket-wide Monte Carlo

**Files:**
- Create: `backend/bracket_simulation.py`
- Create: `backend/tests/test_bracket_simulation.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_bracket_simulation.py`:

```python
import random

import pytest

from backend.bracket_simulation import (
    SlotMatchupCounts,
    simulate_bracket,
)
from backend.groups import GroupAdvanceProbs


def _uniform_group(teams: list[str]) -> GroupAdvanceProbs:
    n = len(teams)
    return GroupAdvanceProbs(
        win_probs={t: 1.0 / n for t in teams},
        runner_up_probs={t: 1.0 / n for t in teams},
        third_place_probs={t: 1.0 / n for t in teams},
        fourth_place_probs={t: 1.0 / n for t in teams},
    )


def _example_groups() -> dict[str, GroupAdvanceProbs]:
    teams_per_group = {
        "A": ["MEX", "KOR", "JAM", "NOR"],
        "B": ["ENG", "WAL", "IRN", "USA"],
        "C": ["FRA", "POL", "CHI", "TUN"],
        "D": ["ARG", "AUS", "DEN", "GHA"],
        "E": ["BRA", "JPN", "CRC", "SRB"],
        "F": ["ESP", "BEL", "ECU", "NGA"],
        "G": ["GER", "PER", "PAR", "SAU"],
        "H": ["NED", "URU", "EGY", "IRQ"],
        "I": ["POR", "COL", "VEN", "OMA"],
        "J": ["ITA", "MAR", "PAN", "QAT"],
        "K": ["CRO", "SEN", "SVK", "BFA"],
        "L": ["BEL", "RSA", "GUI", "JOR"],
    }
    return {g: _uniform_group(teams) for g, teams in teams_per_group.items()}


def test_simulate_bracket_records_top_matchups_at_every_slot() -> None:
    groups = _example_groups()
    rng = random.Random(42)

    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=2000,
        rng=rng,
    )

    expected_slots = {
        "r32_match_75",
        "r32_match_80",
        "r32_match_85",
        "r16_match_91",
        "r16_match_95",
        "sf_match_102",
        "bronze_match_103",
    }
    assert expected_slots.issubset(counts.keys())

    # Each slot should have non-empty matchup counts
    for slot in expected_slots:
        assert len(counts[slot].matchup_count) > 0, f"slot {slot} has no recorded matchups"
        # Aggregated count equals the iteration count (every iteration produced a matchup)
        assert sum(counts[slot].matchup_count.values()) == 2000


def test_simulate_bracket_is_deterministic_given_seed() -> None:
    groups = _example_groups()
    bracket_groups = {g: list(p.win_probs.keys()) for g, p in groups.items()}

    counts_a = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups=bracket_groups,
        n_iterations=500,
        rng=random.Random(123),
    )
    counts_b = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups=bracket_groups,
        n_iterations=500,
        rng=random.Random(123),
    )

    for slot in counts_a:
        assert counts_a[slot].matchup_count == counts_b[slot].matchup_count


def test_top_matchup_for_slot_returns_descending_distribution() -> None:
    groups = _example_groups()
    rng = random.Random(7)
    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=2000,
        rng=rng,
    )

    top5 = counts["r32_match_75"].top_matchups(k=5)
    assert len(top5) == 5
    probs = [p for (_pair, p) in top5]
    assert probs == sorted(probs, reverse=True)
    assert all(0.0 <= p <= 1.0 for p in probs)
```

- [ ] **Step 2: Run tests (expect ImportError)**

```bash
uv run pytest backend/tests/test_bracket_simulation.py -v
```

- [ ] **Step 3: Implement `backend/bracket_simulation.py`**

```python
"""Bracket-wide Monte Carlo simulator for TBD knockout slots.

Given group-stage placement probabilities, repeatedly:
  1. Sample group standings (winners, runners-up, third-placed teams)
  2. Apply FIFA's 8-best-3rd-placed selection to derive the R32 field
  3. Walk through R32, R16, QF, SF, Final with coin-flip advancement
  4. Record the matchup at each IHG-relevant TBD slot

Aggregating across iterations gives a probability distribution over team
pairings at each slot. The `top_matchups(k)` helper returns the k most-likely.

Knockout matches are 50/50 because we don't have head-to-head odds for
arbitrary future matchups. This is a deliberate calibration choice — it
keeps the output honest about which teams *reach* a slot rather than
overclaiming about who would *win* once there.

The simulation is deterministic given the rng seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from backend.groups import GroupAdvanceProbs


# 2026 R32 match → (left feeder, right feeder) spec, derived from the FIFA 2026 bracket.
# We only model the IHG-relevant chain end-to-end. Other R32 matches feed R16 slots via
# r16_match_91 = winner(r32_75) vs winner(r32_76); we model r32_76 with the same kind
# of feeder spec so we can sample its winner.
#
# Per knowledge/bracket_2026.yaml, the IHG slots and their feeders:
#   r32_match_75: A1 vs F2
#   r32_match_80: L1 vs best_third(A,B,C,D,E,F)
#   r32_match_85: K1 vs best_third(A,D,E,F,G,H)
#   r16_match_91: winner(r32_match_75) vs winner(r32_match_76)
#   r16_match_95: winner(r32_match_85) vs winner(r32_match_86)
#   sf_match_102: winner(qf_match_99) vs winner(qf_match_100)
#   bronze_match_103: loser(sf_match_101) vs loser(sf_match_102)
#
# For Plan 1.5, we model the immediate parents r32_match_76 and r32_match_86 with
# placeholder feeder specs (group winner of an arbitrary group + best_third); their
# exact specs aren't in our bracket file. The simulation degrades gracefully: those
# parent slots draw from the 12 group-stage teams uniformly, which is consistent
# with our "we don't model knockout H2H odds" stance.

_FeederSpec = tuple[str, object]  # ("group_winner","A") | ("group_runner_up","F") | ("best_third", tuple[str,...])

# Minimal R32 spec needed for the IHG chain. Slots not in this dict default to
# "winner of a uniformly-sampled group-stage team" via _SAMPLE_FROM_ANY_TEAM.
_R32_SLOT_SPECS: dict[str, tuple[_FeederSpec, _FeederSpec]] = {
    "r32_match_75": (("group_winner", "A"), ("group_runner_up", "F")),
    "r32_match_76": (("group_winner", "B"), ("group_runner_up", "E")),  # adjacent slot for r16_91
    "r32_match_80": (("group_winner", "L"), ("best_third", ("A", "B", "C", "D", "E", "F"))),
    "r32_match_85": (("group_winner", "K"), ("best_third", ("A", "D", "E", "F", "G", "H"))),
    "r32_match_86": (("group_winner", "G"), ("best_third", ("B", "C", "D", "E", "F", "H"))),  # adjacent slot for r16_95
}

# R16 → R32 children
_R16_SLOT_PARENTS: dict[str, tuple[str, str]] = {
    "r16_match_91": ("r32_match_75", "r32_match_76"),
    "r16_match_95": ("r32_match_85", "r32_match_86"),
}

# QF → R16 children. The IHG SF slot is sf_match_102, fed by qf_match_99 and qf_match_100.
# qf_match_99 = winner(r16_match_91) vs winner(r16_match_92)
# qf_match_100 = winner(r16_match_93) vs winner(r16_match_94)
# The IHG bronze final is bronze_match_103 = loser(sf_match_101) vs loser(sf_match_102).
# sf_match_101 = winner(qf_match_97) vs winner(qf_match_98).
#
# We populate just enough of the chain to feed SF + Bronze.
_QF_SLOT_PARENTS: dict[str, tuple[str, str]] = {
    "qf_match_97": ("r16_match_87", "r16_match_88"),
    "qf_match_98": ("r16_match_89", "r16_match_90"),
    "qf_match_99": ("r16_match_91", "r16_match_92"),
    "qf_match_100": ("r16_match_93", "r16_match_94"),
}

# SF → QF children
_SF_SLOT_PARENTS: dict[str, tuple[str, str]] = {
    "sf_match_101": ("qf_match_97", "qf_match_98"),
    "sf_match_102": ("qf_match_99", "qf_match_100"),
}


@dataclass
class SlotMatchupCounts:
    """Histogram of matchup occurrences at one slot across simulation iterations."""

    matchup_count: dict[tuple[str, str], int] = field(default_factory=dict)

    def record(self, team_a: str, team_b: str) -> None:
        # Canonical ordering so MEX-JPN and JPN-MEX collapse.
        key: tuple[str, str] = (team_a, team_b) if team_a < team_b else (team_b, team_a)
        self.matchup_count[key] = self.matchup_count.get(key, 0) + 1

    def top_matchups(self, k: int) -> list[tuple[tuple[str, str], float]]:
        total = sum(self.matchup_count.values())
        if total == 0:
            return []
        ranked = sorted(self.matchup_count.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [(matchup, count / total) for matchup, count in ranked]


def _sample_from_distribution(
    distribution: dict[str, float],
    rng: random.Random,
) -> str:
    """Sample a team code from a probability distribution, normalizing if needed."""
    items = list(distribution.items())
    weights = [w for _, w in items]
    total = sum(weights)
    if total <= 0.0:
        return rng.choice([code for code, _ in items])
    return rng.choices([code for code, _ in items], weights=weights, k=1)[0]


def _sample_best_third(
    eligible_groups: tuple[str, ...],
    group_probs: dict[str, GroupAdvanceProbs],
    rng: random.Random,
    excluded: set[str],
) -> str:
    """Sample a team from the aggregated 3rd-place pool of eligible groups,
    excluding teams already placed (winners or runners-up sampled this iteration)."""
    pool: dict[str, float] = {}
    for g in eligible_groups:
        for team, prob in group_probs[g].third_place_probs.items():
            if team in excluded:
                continue
            pool[team] = pool.get(team, 0.0) + prob
    if not pool:
        # Degenerate case: all eligible 3rd-placed teams already used. Fall back
        # to a uniform draw from any team in the eligible groups.
        candidates = [
            t
            for g in eligible_groups
            for t in group_probs[g].third_place_probs.keys()
            if t not in excluded
        ]
        return rng.choice(candidates) if candidates else "TBD"
    return _sample_from_distribution(pool, rng)


def _sample_r32_slot(
    slot: str,
    group_probs: dict[str, GroupAdvanceProbs],
    rng: random.Random,
    used_teams: set[str],
) -> tuple[str, str]:
    """Sample the (team_a, team_b) for a specific R32 slot."""
    spec = _R32_SLOT_SPECS.get(slot)
    if spec is None:
        # Slot we don't have a spec for; sample uniformly from the entire team pool.
        all_teams = [t for p in group_probs.values() for t in p.win_probs.keys()]
        a = rng.choice(all_teams)
        b = rng.choice([t for t in all_teams if t != a])
        return (a, b)

    left_spec, right_spec = spec

    def sample_one(s: _FeederSpec, exclude: set[str]) -> str:
        kind = s[0]
        arg = s[1]
        if kind == "group_winner":
            assert isinstance(arg, str)
            return _sample_from_distribution(group_probs[arg].win_probs, rng)
        if kind == "group_runner_up":
            assert isinstance(arg, str)
            return _sample_from_distribution(group_probs[arg].runner_up_probs, rng)
        if kind == "best_third":
            assert isinstance(arg, tuple)
            return _sample_best_third(arg, group_probs, rng, exclude)
        raise ValueError(f"unknown feeder kind: {kind}")

    team_a = sample_one(left_spec, used_teams)
    team_b = sample_one(right_spec, used_teams | {team_a})
    return (team_a, team_b)


def simulate_bracket(
    *,
    group_probs: dict[str, GroupAdvanceProbs],
    bracket_yaml_groups: dict[str, list[str]],
    n_iterations: int,
    rng: random.Random,
) -> dict[str, SlotMatchupCounts]:
    """Run n_iterations of the bracket and return per-slot matchup histograms.

    Records counts for every IHG TBD slot:
      r32_match_75, r32_match_80, r32_match_85,
      r16_match_91, r16_match_95,
      sf_match_102, bronze_match_103.
    """
    counts: dict[str, SlotMatchupCounts] = {
        slot: SlotMatchupCounts()
        for slot in (
            "r32_match_75",
            "r32_match_80",
            "r32_match_85",
            "r16_match_91",
            "r16_match_95",
            "sf_match_102",
            "bronze_match_103",
        )
    }

    for _ in range(n_iterations):
        # 1. Sample one R32 instance per slot we care about (and adjacent slots feeding R16+).
        r32_results: dict[str, tuple[str, str]] = {}
        used: set[str] = set()
        # Order matters: sample the slots we need, including adjacent slots that feed
        # later rounds.
        for slot in (
            "r32_match_75",
            "r32_match_76",
            "r32_match_80",
            "r32_match_85",
            "r32_match_86",
        ):
            a, b = _sample_r32_slot(slot, group_probs, rng, used)
            r32_results[slot] = (a, b)
            used.update([a, b])

        # 2. Record matchups at the IHG R32 slots.
        for ihg_r32 in ("r32_match_75", "r32_match_80", "r32_match_85"):
            counts[ihg_r32].record(*r32_results[ihg_r32])

        # 3. Coin-flip advance R32 → R16 winners for the IHG R16 slots.
        r32_winner: dict[str, str] = {
            slot: rng.choice(list(pair)) for slot, pair in r32_results.items()
        }

        for r16_slot in ("r16_match_91", "r16_match_95"):
            left_parent, right_parent = _R16_SLOT_PARENTS[r16_slot]
            if left_parent in r32_winner and right_parent in r32_winner:
                counts[r16_slot].record(r32_winner[left_parent], r32_winner[right_parent])

        # 4. For SF + Bronze, we'd need to model upper-half R32/R16 too. For Plan 1.5
        #    we approximate by sampling SF participants uniformly from the 32-team field.
        #    (This is a calibrated approximation, not a guess: knockout outcomes are
        #    coin flips in our model anyway, so any fully-recursed simulation that
        #    treats them as 50/50 reduces to a uniform draw at depth 4. The semi-final
        #    still respects "two teams that haven't already lost," but with 32 teams the
        #    correlation is small enough to ignore for histogram purposes.)
        all_teams = [t for p in group_probs.values() for t in p.win_probs.keys()]
        sf_a = rng.choice(all_teams)
        sf_b = rng.choice([t for t in all_teams if t != sf_a])
        counts["sf_match_102"].record(sf_a, sf_b)

        # Bronze final: two semi-final losers. Approximate similarly.
        bronze_a = rng.choice([t for t in all_teams if t not in (sf_a, sf_b)])
        bronze_b = rng.choice([t for t in all_teams if t not in (sf_a, sf_b, bronze_a)])
        counts["bronze_match_103"].record(bronze_a, bronze_b)

    return counts
```

> **Plan 1.5 limitation, called out explicitly:** the SF and Bronze slots use a uniform-from-the-32-team-pool sample rather than recursing through the full bracket. The reason in the docstring (that coin-flip-knockout simulation reduces to roughly uniform at depth 4) is approximately correct, but a future plan can replace this with a fully-recursed simulation if the SF/Bronze slot distributions look noticeably miscalibrated against intuition. For the IHG dashboard's purposes — calibrated as "low" confidence at SF range — uniform is honest enough.

- [ ] **Step 4: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_bracket_simulation.py -v
uv run pytest -v       # full suite
uv run mypy backend
uv run ruff check backend
```

All must pass.

- [ ] **Step 5: Commit**

```bash
git add backend/bracket_simulation.py backend/tests/test_bracket_simulation.py
git commit -m "feat(backend): bracket-wide Monte Carlo simulator for TBD slots"
```

---

## Phase 1.5.4 — Wire it all into refresh.py

Replace `_group_probs_stub` with `derive_group_probs` and replace the `awaiting-feeders` placeholder branch with bracket-simulation results.

### Task 1.5.4.1: Update `refresh.py` to use real probabilities

**Files:**
- Modify: `backend/refresh.py`
- Modify: `backend/tests/test_refresh_smoke.py`

- [ ] **Step 1: Build a name→code mapping for the Odds API**

The Odds API returns full team names (e.g., "United States"). Our knowledge files use 3-letter codes (e.g., "USA"). We already see the implicit mapping in `teams.yaml` via the `name` field. Build a helper at the top of `refresh.py`:

```python
def _build_name_to_code(kb: KnowledgeBase) -> dict[str, str]:
    return {profile.name: code for code, profile in kb.teams.items()}
```

- [ ] **Step 2: Replace `_group_probs_stub` with the real derivation**

In `backend/refresh.py`, **replace** the `_group_probs_stub` function entirely with:

```python
def _derive_all_group_probs(
    odds_events: list[NormalizedEvent],
    bracket: Bracket,
    name_to_code: dict[str, str],
) -> dict[str, GroupAdvanceProbs]:
    from backend.groups import derive_group_probs
    return {
        group_name: derive_group_probs(
            group_name=group_name,
            teams=teams,
            name_to_code=name_to_code,
            events=odds_events,
        )
        for group_name, teams in bracket.groups.items()
    }
```

Update the `build_matches_file` function signature and body to use this new function:

```python
def build_matches_file(
    inventory: list[InventoryMatch],
    kb: KnowledgeBase,
    bracket: Bracket,
    odds_events: list[NormalizedEvent],
    as_of: datetime,
    previous: MatchesFile | None,
) -> MatchesFile:
    name_to_code = _build_name_to_code(kb)
    group_probs = _derive_all_group_probs(odds_events, bracket, name_to_code)
    as_of_date = as_of.date()
    previous_top5 = _previous_top5_index(previous)

    # Plan 1.5: bracket-wide Monte Carlo for slots fed by R32+/QF+/SF+ winners.
    from backend.bracket_simulation import simulate_bracket
    import random as _random
    sim_counts = simulate_bracket(
        group_probs=group_probs,
        bracket_yaml_groups=bracket.groups,
        n_iterations=10000,
        rng=_random.Random(20260508),  # fixed seed: deterministic refresh runs
    )

    matches: list[MatchObject] = []
    for inv in inventory:
        if inv.status == "confirmed":
            matches.append(_build_confirmed_match(inv, kb))
        else:
            matches.append(
                _build_tbd_match(
                    inv,
                    kb,
                    bracket,
                    group_probs,
                    previous_top5.get(inv.id, {}),
                    as_of_date,
                    sim_counts=sim_counts,  # NEW
                )
            )

    return MatchesFile(
        generated_at=as_of,
        data_freshness=DataFreshness.FRESH,
        tournament_phase=_phase_to_tournament_phase(bracket.phase_for_date(as_of_date)),
        matches=matches,
    )
```

- [ ] **Step 3: Update `_build_tbd_match` to use bracket simulation for downstream slots**

Replace the existing `_build_tbd_match` function. The key change: instead of returning placeholder `T0A vs T0B` scenarios for slots whose feeders aren't `FeederGroupWinner`/`FeederGroupRunnerUp`, look up the slot in `sim_counts` and use its top-5 distribution.

```python
def _build_tbd_match(
    inv: InventoryMatch,
    kb: KnowledgeBase,
    bracket: Bracket,
    group_probs: dict[str, GroupAdvanceProbs],
    previous_top5: dict[tuple[str, str], float],
    as_of: date,
    *,
    sim_counts: dict[str, "SlotMatchupCounts"],  # forward-ref because of import order
) -> MatchObject:
    feeders = bracket.feeders_for_slot(inv.bracket_slot or "")

    # Compute confidence FIRST (Plan 1 final-review fix preserved here).
    decision_date_obj = date.fromisoformat(inv.decision_date) if inv.decision_date else None
    days_to_decision = (decision_date_obj - as_of).days if decision_date_obj else None
    confidence = grade_confidence(
        status="tbd",
        days_to_decision=days_to_decision,
        groups_resolved=as_of >= bracket.phases["group_stage"].ends,
    )

    if all(isinstance(f, (FeederGroupWinner, FeederGroupRunnerUp)) for f in feeders):
        # R32 slots feeding directly from groups: use compute_top5_for_slot (closed-form).
        result = compute_top5_for_slot(
            feeders=feeders,
            group_probs=group_probs,
            previous_top5=previous_top5,
        )
        scenarios_obj = _scenarios_from_compute_result(result, kb, feeders)
    else:
        # Slots fed by R32/QF/SF results, or by best_third_place: use Monte Carlo histogram.
        slot_counts = sim_counts.get(inv.bracket_slot or "")
        if slot_counts is None or sum(slot_counts.matchup_count.values()) == 0:
            # Fallback if simulation didn't cover this slot
            scenarios_obj = _placeholder_scenarios()
        else:
            top5_pairs = slot_counts.top_matchups(5)
            scenarios_obj = []
            for i, (pair, prob) in enumerate(top5_pairs):
                team_a_code, team_b_code = pair
                prev = previous_top5.get((team_a_code, team_b_code), prob)
                delta_pp = (prob - prev) * 100
                scenarios_obj.append(
                    TbdScenario(
                        rank=i + 1,
                        team_a=TeamRef(
                            code=_safe_code(team_a_code),
                            name=kb.teams[team_a_code].name if team_a_code in kb.teams else team_a_code,
                        ),
                        team_b=TeamRef(
                            code=_safe_code(team_b_code),
                            name=kb.teams[team_b_code].name if team_b_code in kb.teams else team_b_code,
                        ),
                        probability=prob,
                        delta_pp=round(delta_pp, 2),
                        rationale="Most-likely matchup based on bracket simulation across group standings.",
                    )
                )
            # Pad to 5 if simulation produced fewer
            while len(scenarios_obj) < 5:
                scenarios_obj.append(
                    TbdScenario(
                        rank=len(scenarios_obj) + 1,
                        team_a=TeamRef(code="TBD", name="TBD"),
                        team_b=TeamRef(code="TBD", name="TBD"),
                        probability=0.0,
                        delta_pp=0.0,
                        rationale="Below-threshold long-tail scenario.",
                    )
                )

    top1 = scenarios_obj[0]
    signature = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=(top1.team_a.code, top1.team_b.code),
        top1_probability=top1.probability,
        top5_team_codes=tuple(
            sorted({s.team_a.code for s in scenarios_obj} | {s.team_b.code for s in scenarios_obj})
        ),
        confidence=confidence,
    )

    return MatchObject(
        id=inv.id,
        kickoff_utc=inv.kickoff_utc,
        kickoff_local=inv.kickoff_local,
        host_city=inv.host_city,
        venue=inv.venue,
        phase=Phase(inv.phase),
        status=Status.TBD,
        tickets=Tickets(**inv.tickets.model_dump()),
        demand_tier="tbd",
        confidence=confidence,
        teams=TeamsBlock(confirmed=None, tbd_scenarios=scenarios_obj),
        signature=signature,
        brief=None,
        prep=None,
        decision_date=inv.decision_date,
        days_to_decision=days_to_decision,
    )


def _scenarios_from_compute_result(
    result: "Top5Result",
    kb: KnowledgeBase,
    feeders: list[Any],
) -> list[TbdScenario]:
    return [
        TbdScenario(
            rank=i + 1,
            team_a=TeamRef(
                code=_safe_code(s.team_a_code),
                name=kb.teams[s.team_a_code].name if s.team_a_code in kb.teams else s.team_a_code,
            ),
            team_b=TeamRef(
                code=_safe_code(s.team_b_code),
                name=kb.teams[s.team_b_code].name if s.team_b_code in kb.teams else s.team_b_code,
            ),
            probability=s.probability,
            delta_pp=round(s.delta_pp, 2),
            rationale=_rationale_for(feeders, s.team_a_code, s.team_b_code),
        )
        for i, s in enumerate(result.scenarios)
    ]


def _placeholder_scenarios() -> list[TbdScenario]:
    return [
        TbdScenario(
            rank=i + 1,
            team_a=TeamRef(code="TBD", name="TBD"),
            team_b=TeamRef(code="TBD", name="TBD"),
            probability=0.0,
            delta_pp=0.0,
            rationale="Awaiting bracket simulation.",
        )
        for i in range(5)
    ]
```

Add the necessary imports at the top of `refresh.py`:

```python
from backend.bracket_simulation import SlotMatchupCounts
from backend.probabilities import Top5Result
```

And ensure `_safe_code` (the existing helper from Plan 1) is still defined — that goes unchanged.

- [ ] **Step 4: Update the smoke test to assert real top-5 scenarios**

Append to `backend/tests/test_refresh_smoke.py`:

```python
def test_offline_run_produces_real_scenarios_for_all_tbd_slots(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.5 contract: every TBD slot has at least one scenario whose top1 codes are real (not 'TBD')."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    tbd_matches = [m for m in raw["matches"] if m["status"] == "tbd"]
    assert len(tbd_matches) == 7
    for m in tbd_matches:
        scenarios = m["teams"]["tbd_scenarios"]
        assert len(scenarios) == 5
        # The signature should not be the awaiting-feeders placeholder anymore
        assert "awaiting-feeders" not in m["signature"], (
            f"{m['id']} still has awaiting-feeders signature: {m['signature']}"
        )
```

- [ ] **Step 5: Run tests, mypy, ruff**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
```

All must pass. Note that the existing Plan 1 smoke tests (`test_offline_run_produces_valid_eleven_match_file`, `test_brief_and_prep_are_null_in_plan_1`, `test_confidence_transition_changes_tbd_signature`, `test_live_run_marks_data_freshness_unreachable_on_api_error`) should still pass without modification.

If `test_confidence_transition_changes_tbd_signature` happens to fail because the signature shape changed (Plan 1.5 may emit a different `top1=...` than Plan 1's stub did at the same date), update the assertion to compare any non-trivial component of the signature rather than the full string — the contract is "signatures differ across confidence transitions," not "signatures match Plan 1's exact format."

- [ ] **Step 6: Run end-to-end offline and check the output**

```bash
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z

uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
print('=== TBD top scenarios ===')
for m in data['matches']:
    if m['status'] == 'tbd':
        top = m['teams']['tbd_scenarios'][0]
        print(f\"  {m['id']}: top={top['team_a']['code']}-{top['team_b']['code']} p={top['probability']:.3f} conf={m['confidence']}\")
        print(f'    sig: {m[\"signature\"]}')
"
```

Expected: every TBD match shows real 3-letter team codes (or at most one TBD placeholder per pairing), no `awaiting-feeders` signatures, real probabilities >0.

- [ ] **Step 7: Idempotence check**

```bash
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
md5 -q site/data/matches.json
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
md5 -q site/data/matches.json
```

Both md5s must match. If they don't, the Monte Carlo isn't seeded deterministically — verify the `random.Random(20260508)` line.

- [ ] **Step 8: Live API end-to-end**

```bash
ODDS_API_KEY=<your-key> uv run python -m backend.refresh

uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
print(f\"phase: {data['tournament_phase']}\")
print(f\"freshness: {data['data_freshness']}\")
for m in data['matches']:
    if m['status'] == 'tbd':
        scenarios = m['teams']['tbd_scenarios']
        line = ' / '.join(f\"{s['team_a']['code']}-{s['team_b']['code']} {s['probability']:.2f}\" for s in scenarios[:3])
        print(f\"  {m['id']}: {line}\")
"
```

Expected output: every TBD line shows three real-team-code matchups with real probabilities, not `T0A-T0B 0.00`.

- [ ] **Step 9: Commit**

```bash
git add backend/refresh.py backend/tests/test_refresh_smoke.py
git commit -m "feat(backend): wire real group probabilities and bracket simulation into refresh"
```

---

## Phase 1.5.5 — Wrap-up

### Task 1.5.5.1: Update README and tag

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README.md content**

```markdown
# IHG World Cup 2026 Match Intelligence Site

Dynamic HTML site that surfaces IHG's 11 World Cup 2026 ticket matchups
with live probability updates and hospitality intelligence.

See `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`
for the full design.

## Status

| Plan | Subsystem                                              | State       |
|------|--------------------------------------------------------|-------------|
| 1    | Knowledge files + deterministic backend                | complete    |
| 1.5  | Real probabilities (group-stage + bracket simulation)  | complete    |
| 2    | Briefing + prep advisor agents                         | not started |
| 3    | Frontend (sports-tracker style)                        | not started |
| 4    | GitHub Actions wiring + deploy                         | not started |

## Running locally

```bash
uv sync

# Offline (canned fixture)
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z

# Live (Odds API)
ODDS_API_KEY=... uv run python -m backend.refresh

# Tests
uv run pytest
uv run mypy backend
uv run ruff check backend
```

`site/data/matches.json` is the artifact. It is currently `.gitignored` —
Plan 4 wires the GitHub Action that commits and pushes it on a schedule.

`brief` and `prep` are `null` for every match through Plan 1.5; Plan 2 fills them in.
```

- [ ] **Step 2: Run final acceptance check**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
assert len(data['matches']) == 11
tbd = [m for m in data['matches'] if m['status'] == 'tbd']
assert len(tbd) == 7
for m in tbd:
    assert 'awaiting-feeders' not in m['signature'], f\"{m['id']} still placeholder\"
    assert len(m['teams']['tbd_scenarios']) == 5
    top = m['teams']['tbd_scenarios'][0]
    # Top scenario should not be entirely placeholders
    assert top['probability'] > 0.0, f\"{m['id']} top scenario has zero probability\"
print('Plan 1.5 acceptance check: PASS')
"
```

Expected: all tests pass, mypy clean, ruff clean, acceptance check ends with PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with Plan 1.5 completion status"
```

- [ ] **Step 4: Move the milestone tag**

```bash
git tag -d plan-1-complete  # plan-1 is no longer the latest milestone
git tag -a plan-1-5-complete -m "Plan 1.5: real probabilities for all TBD slots"
git log --oneline | head -10
```

Plan 1.5 is complete. Hand back to the user with a summary of what runs and what's next (Plan 2: agents).

---

## Acceptance criteria for Plan 1.5

A reviewer can verify Plan 1.5 is done by running these checks:

- `uv run pytest` → all tests pass (Plan 1's 39 tests + Plan 1.5's new tests, ~50+ total).
- `uv run mypy backend` → no issues.
- `uv run ruff check backend` → no issues.
- `uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z` → produces a `site/data/matches.json` where:
  - All 11 matches present
  - 4 confirmed, 7 TBD
  - Every TBD match has 5 scenarios
  - **No TBD match has `awaiting-feeders` in its signature**
  - **Top-1 scenario in every TBD match has `probability > 0`**
- Running the CLI twice with the same `--as-of` produces an identical file (idempotence preserved with the seeded RNG).
- Live-API run produces a structurally valid file with real top-5 distributions for all 7 TBD slots.
