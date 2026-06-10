# IHG World Cup Site — Plan 1: Knowledge Files + Deterministic Backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that produces a fully-valid `site/data/matches.json` from canned Odds API fixtures (and from the live API when a key is present), without any LLM calls and without any frontend. End state: running `python -m backend.refresh --offline` writes a schema-valid `matches.json` with all 11 IHG matches, deterministic top-5 scenarios for the 7 TBD matches, signatures, and confidence grading. The `brief` and `prep` fields are intentionally `null` at this stage — Plan 2 fills them in.

**Architecture:** Pure-functional Python modules organized around the data contract. Knowledge in YAML, schema in Pydantic, all probability work deterministic. No git or GitHub integration in this plan — `writer.py` only writes the file to disk. Tests are pytest, fast, and run against canned fixtures by default; one optional integration test hits the real Odds API when `ODDS_API_KEY` is in the environment.

**Tech Stack:** Python 3.12, `uv` for dependency management, Pydantic v2, PyYAML, `httpx` (sync) for the Odds API client, `pytest` + `pytest-mock`, `ruff`, `mypy`.

**Reference spec:** [`docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`](../specs/2026-05-08-world-cup-intelligence-site-design.md)

---

## File structure produced by this plan

```
world-cup-intelligence-site/
  pyproject.toml
  .gitignore
  README.md
  knowledge/
    ticket_inventory.yaml
    bracket_2026.yaml
    teams.yaml
    cities.yaml
  backend/
    __init__.py
    schema.py             Pydantic models for matches.json
    inventory.py          loads ticket_inventory.yaml
    knowledge.py          loads teams.yaml + cities.yaml
    bracket.py            loads bracket_2026.yaml, resolves TBD slot feeders
    odds_client.py        Odds API wrapper with retries + circuit breaker
    probabilities.py      compute top-5 matchups per slot, Monte Carlo fallback
    confidence.py         deterministic confidence grading
    signature.py          compute and diff signatures
    writer.py             serialize matches.json to disk (no git in Plan 1)
    refresh.py            CLI entrypoint, orchestrates the pipeline
    tests/
      __init__.py
      conftest.py
      fixtures/
        odds_response.json
        odds_response_no_futures.json
        previous_matches.json
      test_schema.py
      test_inventory.py
      test_knowledge.py
      test_bracket.py
      test_confidence.py
      test_signature.py
      test_odds_client.py
      test_probabilities.py
      test_writer.py
      test_refresh_smoke.py
  site/
    data/
      .gitkeep              matches.json is generated, gitignored in Plan 1
```

`site/data/matches.json` is **gitignored in Plan 1** (it's an artifact of running the CLI and has no value tracked in git until Plan 4 wires up the GitHub Action that commits it on a schedule).

---

## Phase 1.0 — Project skeleton

### Task 1.0.1: Initialize the repo and Python project

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `backend/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/fixtures/.gitkeep`
- Create: `knowledge/.gitkeep`
- Create: `site/data/.gitkeep`

- [ ] **Step 1: Verify working directory**

```bash
cd /Users/UTN0XA/Documents/claude_code/world-cup-intelligence-site
pwd
ls -la
```

Expected: empty directory (only `docs/` from the brainstorming/spec phase).

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "world-cup-intelligence-site"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.7,<3",
  "pyyaml>=6.0,<7",
  "httpx>=0.27,<1",
  "tenacity>=9.0,<10",
]

[dependency-groups]
dev = [
  "pytest>=8.2,<9",
  "pytest-mock>=3.14,<4",
  "ruff>=0.6,<1",
  "mypy>=1.11,<2",
  "types-PyYAML",
]

[tool.pytest.ini_options]
testpaths = ["backend/tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["backend"]
```

- [ ] **Step 3: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Environment
.env
.env.local

# Generated artifacts (Plan 1)
site/data/matches.json

# Frontend build artifacts (added in later plans)
node_modules/
site/assets/app.js
site/assets/app.js.map
```

- [ ] **Step 4: Create `README.md` with the bare minimum**

```markdown
# IHG World Cup 2026 Match Intelligence Site

Dynamic HTML site that surfaces IHG's 11 World Cup 2026 ticket matchups
with live probability updates and hospitality intelligence.

See `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`
for the full design.

## Plan 1: Deterministic backend (current)

```bash
uv sync
uv run python -m backend.refresh --offline
cat site/data/matches.json
```

Plans 2 (agents), 3 (frontend), and 4 (GitHub Actions deploy) follow.
```

- [ ] **Step 5: Create empty package files**

```bash
touch backend/__init__.py
touch backend/tests/__init__.py
touch backend/tests/fixtures/.gitkeep
touch knowledge/.gitkeep
mkdir -p site/data
touch site/data/.gitkeep
```

- [ ] **Step 6: Create `backend/tests/conftest.py` with fixture path helper**

```python
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).parent / "fixtures"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def knowledge_dir() -> Path:
    return KNOWLEDGE_DIR
```

- [ ] **Step 7: Initialize git, install deps, verify clean state**

```bash
git init
git add .
git commit -m "chore: initial project skeleton"
uv sync
uv run pytest --collect-only
```

Expected from `pytest --collect-only`: `collected 0 items` (no tests yet, but no errors).

---

## Phase 1.1 — Schema

The Pydantic schema for `matches.json` is the single most important artifact in the project — every other module produces or consumes types defined here. Build it first, with thorough tests, so later tasks have something stable to validate against.

### Task 1.1.1: Pydantic models matching the `matches.json` contract

**Files:**
- Create: `backend/schema.py`
- Create: `backend/tests/test_schema.py`

- [ ] **Step 1: Write failing test for a minimal valid `MatchesFile`**

`backend/tests/test_schema.py`:

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.schema import (
    Brief,
    ConfirmedTeam,
    DataFreshness,
    MatchesFile,
    MatchObject,
    Phase,
    Prep,
    PrepFnB,
    Status,
    TbdScenario,
    TeamRef,
    Tickets,
    TournamentPhase,
)


def make_confirmed_match() -> MatchObject:
    return MatchObject(
        id="atl-2026-03-31-usa-por",
        kickoff_utc=datetime(2026, 3, 31, 16, 0, tzinfo=timezone.utc),
        kickoff_local="2026-03-31T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.FRIENDLY,
        status=Status.CONFIRMED,
        tickets=Tickets(suite=10, stadium=0, split_with="Etherio"),
        demand_tier="high",
        confidence="certain",
        teams={
            "confirmed": [
                ConfirmedTeam(code="USA", name="United States", fifa_rank=16),
                ConfirmedTeam(code="POR", name="Portugal", fifa_rank=6),
            ],
            "tbd_scenarios": None,
        },
        signature="v1:confirmed:USA-POR",
        brief=None,
        prep=None,
        decision_date=None,
        days_to_decision=None,
    )


def test_minimal_matches_file_validates():
    file = MatchesFile(
        generated_at=datetime.now(timezone.utc),
        data_freshness=DataFreshness.FRESH,
        tournament_phase=TournamentPhase.PRE_TOURNAMENT,
        matches=[make_confirmed_match()],
    )
    assert file.matches[0].status == Status.CONFIRMED
    assert file.matches[0].teams["confirmed"][0].code == "USA"


def test_confirmed_match_rejects_tbd_scenarios():
    """A confirmed match with tbd_scenarios populated should fail validation."""
    with pytest.raises(ValidationError):
        MatchObject(
            id="x",
            kickoff_utc=datetime.now(timezone.utc),
            kickoff_local="2026-01-01T00:00:00Z",
            host_city="Atlanta",
            venue="V",
            phase=Phase.FRIENDLY,
            status=Status.CONFIRMED,
            tickets=Tickets(),
            demand_tier="high",
            confidence="certain",
            teams={
                "confirmed": [
                    ConfirmedTeam(code="USA", name="USA", fifa_rank=1),
                    ConfirmedTeam(code="POR", name="Portugal", fifa_rank=2),
                ],
                "tbd_scenarios": [
                    TbdScenario(
                        rank=1,
                        team_a=TeamRef(code="A", name="A"),
                        team_b=TeamRef(code="B", name="B"),
                        probability=0.5,
                        delta_pp=0.0,
                        rationale="x",
                    )
                ],
            },
            signature="v1:confirmed:USA-POR",
            brief=None,
            prep=None,
            decision_date=None,
            days_to_decision=None,
        )


def test_tbd_match_requires_exactly_five_scenarios():
    """TBD match with 4 scenarios should fail validation."""
    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code=f"A{i}", name=f"A{i}"),
            team_b=TeamRef(code=f"B{i}", name=f"B{i}"),
            probability=0.1,
            delta_pp=0.0,
            rationale="r",
        )
        for i in range(1, 5)
    ]
    with pytest.raises(ValidationError):
        MatchObject(
            id="x",
            kickoff_utc=datetime.now(timezone.utc),
            kickoff_local="2026-07-05T16:00:00-04:00",
            host_city="NY/NJ",
            venue="MetLife Stadium",
            phase=Phase.ROUND_OF_16,
            status=Status.TBD,
            tickets=Tickets(stadium=6, club="Champion Club Plus"),
            demand_tier="tbd",
            confidence="medium",
            teams={"confirmed": None, "tbd_scenarios": scenarios},
            signature="v1:tbd:...",
            brief=None,
            prep=None,
            decision_date="2026-07-03",
            days_to_decision=2,
        )


def test_brief_and_prep_can_be_populated():
    brief = Brief(
        headline="Test headline",
        scenario_summary=None,
        fan_demographics="x",
        traveling_volume_est="x",
        cultural_context="x",
        demand_rationale="x",
    )
    prep = Prep(
        fnb=PrepFnB(
            suggestions=[],
            requirements=["halal"],
            operational_notes=[],
        ),
        language=["Spanish"],
        rate_strategy="aggressive",
        logistics=[],
        owner_invitation_note="...",
    )
    m = make_confirmed_match()
    m.brief = brief
    m.prep = prep
    assert m.brief.headline == "Test headline"
    assert m.prep.fnb.requirements == ["halal"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_schema.py -v
```

Expected: ImportError / ModuleNotFoundError on `backend.schema` — that's the correct failure.

- [ ] **Step 3: Implement `backend/schema.py`**

```python
"""Pydantic models for matches.json — the single source of truth contract."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class DataFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNREACHABLE = "unreachable"


class TournamentPhase(StrEnum):
    PRE_TOURNAMENT = "pre_tournament"
    GROUP_STAGE = "group_stage"
    ROUND_OF_32 = "round_of_32"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINALS = "quarter_finals"
    SEMI_FINALS = "semi_finals"
    FINALS = "finals"


class Phase(StrEnum):
    FRIENDLY = "friendly"
    GROUP_STAGE = "group_stage"
    ROUND_OF_32 = "round_of_32"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    BRONZE_FINAL = "bronze_final"
    FINAL = "final"


class Status(StrEnum):
    CONFIRMED = "confirmed"
    TBD = "tbd"


DemandTier = Literal["high", "medium", "low", "tbd"]
Confidence = Literal["certain", "high", "medium", "low"]


class Tickets(BaseModel):
    suite: int = 0
    stadium: int = 0
    split_with: str | None = None
    club: str | None = None


class ConfirmedTeam(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str
    fifa_rank: int


class TeamRef(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str


class TbdScenario(BaseModel):
    rank: Annotated[int, Field(ge=1, le=5)]
    team_a: TeamRef
    team_b: TeamRef
    probability: Annotated[float, Field(ge=0.0, le=1.0)]
    delta_pp: float
    rationale: str


class TeamsBlock(BaseModel):
    confirmed: list[ConfirmedTeam] | None = None
    tbd_scenarios: list[TbdScenario] | None = None


class PrepFnBSuggestion(BaseModel):
    dish: str
    meal_period: str
    rationale: str


class PrepFnB(BaseModel):
    suggestions: list[PrepFnBSuggestion]
    requirements: list[str]
    operational_notes: list[str]


class Brief(BaseModel):
    headline: str
    scenario_summary: str | None
    fan_demographics: str
    traveling_volume_est: str
    cultural_context: str
    demand_rationale: str


class Prep(BaseModel):
    fnb: PrepFnB
    language: list[str]
    rate_strategy: str
    logistics: list[str]
    owner_invitation_note: str


class MatchObject(BaseModel):
    id: str
    kickoff_utc: datetime
    kickoff_local: str
    host_city: Literal["Atlanta", "NY/NJ", "Miami"]
    venue: str
    phase: Phase
    status: Status
    tickets: Tickets
    demand_tier: DemandTier
    confidence: Confidence
    teams: TeamsBlock
    signature: str
    brief: Brief | None = None
    prep: Prep | None = None
    decision_date: str | None = None
    days_to_decision: int | None = None

    @model_validator(mode="after")
    def _teams_block_matches_status(self) -> "MatchObject":
        if self.status == Status.CONFIRMED:
            if self.teams.confirmed is None or len(self.teams.confirmed) != 2:
                raise ValueError(
                    "confirmed match requires exactly 2 entries in teams.confirmed"
                )
            if self.teams.tbd_scenarios is not None:
                raise ValueError(
                    "confirmed match must have teams.tbd_scenarios=None"
                )
        else:  # TBD
            if self.teams.tbd_scenarios is None or len(self.teams.tbd_scenarios) != 5:
                raise ValueError(
                    "TBD match requires exactly 5 entries in teams.tbd_scenarios"
                )
            if self.teams.confirmed is not None:
                raise ValueError(
                    "TBD match must have teams.confirmed=None"
                )
        return self


class MatchesFile(BaseModel):
    generated_at: datetime
    data_freshness: DataFreshness
    tournament_phase: TournamentPhase
    matches: Annotated[list[MatchObject], Field(min_length=11, max_length=11)]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest backend/tests/test_schema.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Type-check**

```bash
uv run mypy backend/schema.py
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add backend/schema.py backend/tests/test_schema.py
git commit -m "feat(schema): add Pydantic models for matches.json contract"
```

---

## Phase 1.2 — Knowledge files

These are hand-authored YAML files. Each task has acceptance criteria rather than a unit test (the structural validation comes from the loaders in Phase 1.3).

### Task 1.2.1: Author `knowledge/ticket_inventory.yaml`

**Files:**
- Create: `knowledge/ticket_inventory.yaml`

The 11 IHG matches are fully specified in the design spec. Transcribe them.

- [ ] **Step 1: Write the file**

`knowledge/ticket_inventory.yaml`:

```yaml
# IHG World Cup 2026 ticket inventory.
# Source: internal IHG inventory list, transcribed from the design brief.
# Update only when ticket allocations change.

tournament: "FIFA World Cup 2026"
matches:
  - id: atl-2026-03-31-usa-por
    kickoff_local: "2026-03-31T12:00:00-04:00"
    kickoff_utc: "2026-03-31T16:00:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: friendly
    status: confirmed
    tickets: { suite: 10, stadium: 0, split_with: Etherio }
    demand_tier: high
    confirmed_teams: [USA, POR]

  - id: atl-2026-06-18-rsa-cze
    kickoff_local: "2026-06-18T12:00:00-04:00"
    kickoff_utc: "2026-06-18T16:00:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: group_stage
    status: confirmed
    tickets: { suite: 20 }
    demand_tier: medium
    confirmed_teams: [RSA, CZE]

  - id: atl-2026-06-24-mar-hai
    kickoff_local: "2026-06-24T18:00:00-04:00"
    kickoff_utc: "2026-06-24T22:00:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: group_stage
    status: confirmed
    tickets: { suite: 20 }
    demand_tier: high
    confirmed_teams: [MAR, HAI]

  - id: atl-2026-06-27-uzb-cod
    kickoff_local: "2026-06-27T19:30:00-04:00"
    kickoff_utc: "2026-06-27T23:30:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: group_stage
    status: confirmed
    tickets: { suite: 20, stadium: 10 }
    demand_tier: low
    confirmed_teams: [UZB, COD]

  - id: njy-2026-06-30-r32-a1-vs-f2
    kickoff_local: "2026-06-30T17:00:00-04:00"
    kickoff_utc: "2026-06-30T21:00:00Z"
    host_city: NY/NJ
    venue: MetLife Stadium
    phase: round_of_32
    status: tbd
    tickets: { stadium: 6, club: "Champion Club Plus" }
    demand_tier: tbd
    bracket_slot: r32_match_75    # Group A winner vs Group F runner-up
    decision_date: "2026-06-27"

  - id: atl-2026-07-01-r32-l1-vs-third
    kickoff_local: "2026-07-01T12:00:00-04:00"
    kickoff_utc: "2026-07-01T16:00:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: round_of_32
    status: tbd
    tickets: { stadium: 10 }
    demand_tier: tbd
    bracket_slot: r32_match_80
    decision_date: "2026-06-27"

  - id: mia-2026-07-03-r32-conmebol
    kickoff_local: "2026-07-03T18:00:00-04:00"
    kickoff_utc: "2026-07-03T22:00:00Z"
    host_city: Miami
    venue: Hard Rock Stadium
    phase: round_of_32
    status: tbd
    tickets: { stadium: 6, club: "Champion Club Plus" }
    demand_tier: tbd
    bracket_slot: r32_match_85
    decision_date: "2026-06-27"

  - id: njy-2026-07-05-r16
    kickoff_local: "2026-07-05T16:00:00-04:00"
    kickoff_utc: "2026-07-05T20:00:00Z"
    host_city: NY/NJ
    venue: MetLife Stadium
    phase: round_of_16
    status: tbd
    tickets: { stadium: 6, club: "Champion Club Plus" }
    demand_tier: tbd
    bracket_slot: r16_match_91
    decision_date: "2026-07-03"

  - id: atl-2026-07-07-r16
    kickoff_local: "2026-07-07T12:00:00-04:00"
    kickoff_utc: "2026-07-07T16:00:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: round_of_16
    status: tbd
    tickets: { suite: 10, split_with: Etherio }
    demand_tier: tbd
    bracket_slot: r16_match_95
    decision_date: "2026-07-03"

  - id: atl-2026-07-15-sf
    kickoff_local: "2026-07-15T15:00:00-04:00"
    kickoff_utc: "2026-07-15T19:00:00Z"
    host_city: Atlanta
    venue: Mercedes-Benz Stadium
    phase: semi_final
    status: tbd
    tickets: { suite: 10, split_with: Etherio }
    demand_tier: tbd
    bracket_slot: sf_match_102
    decision_date: "2026-07-11"

  - id: mia-2026-07-18-bronze
    kickoff_local: "2026-07-18T17:00:00-04:00"
    kickoff_utc: "2026-07-18T21:00:00Z"
    host_city: Miami
    venue: Hard Rock Stadium
    phase: bronze_final
    status: tbd
    tickets: { stadium: 6, club: "Champion Club Plus" }
    demand_tier: tbd
    bracket_slot: bronze_match_103
    decision_date: "2026-07-15"
```

- [ ] **Step 2: Validate it parses as YAML**

```bash
uv run python -c "import yaml; print(len(yaml.safe_load(open('knowledge/ticket_inventory.yaml'))['matches']))"
```

Expected: `11`.

- [ ] **Step 3: Commit**

```bash
git add knowledge/ticket_inventory.yaml
git commit -m "feat(knowledge): author IHG ticket inventory for 11 World Cup 2026 matches"
```

### Task 1.2.2: Author `knowledge/bracket_2026.yaml`

The 2026 World Cup is the first 48-team tournament. The structure: 12 groups of 4 (A–L), top 2 from each group + 8 best third-place teams advance to a Round of 32, then standard knockout. The IHG TBD matches map to specific bracket slots.

- [ ] **Step 1: Write the file**

`knowledge/bracket_2026.yaml`:

```yaml
# Official 2026 FIFA World Cup bracket structure.
# Source: FIFA published tournament structure.
# 48 teams, 12 groups of 4, R32 of top 2 + 8 best 3rd-placed, then standard knockouts.

tournament: "FIFA World Cup 2026"

phases:
  pre_tournament:
    starts: "2026-03-31"
    ends:   "2026-06-10"
  group_stage:
    starts: "2026-06-11"
    ends:   "2026-06-27"
  round_of_32:
    starts: "2026-06-28"
    ends:   "2026-07-03"
  round_of_16:
    starts: "2026-07-04"
    ends:   "2026-07-07"
  quarter_finals:
    starts: "2026-07-09"
    ends:   "2026-07-11"
  semi_finals:
    starts: "2026-07-14"
    ends:   "2026-07-15"
  finals:
    starts: "2026-07-18"
    ends:   "2026-07-19"

groups:
  A: { teams: [MEX, "TBD_A2", "TBD_A3", "TBD_A4"] }    # Mexico is the host of the opening match
  B: { teams: ["TBD_B1", "TBD_B2", "TBD_B3", "TBD_B4"] }
  C: { teams: ["TBD_C1", "TBD_C2", "TBD_C3", "TBD_C4"] }
  D: { teams: [USA, "TBD_D2", "TBD_D3", "TBD_D4"] }    # USA host
  E: { teams: ["TBD_E1", "TBD_E2", "TBD_E3", "TBD_E4"] }
  F: { teams: ["TBD_F1", "TBD_F2", "TBD_F3", "TBD_F4"] }
  G: { teams: ["TBD_G1", "TBD_G2", "TBD_G3", "TBD_G4"] }
  H: { teams: [CAN, "TBD_H2", "TBD_H3", "TBD_H4"] }    # Canada host
  I: { teams: ["TBD_I1", "TBD_I2", "TBD_I3", "TBD_I4"] }
  J: { teams: ["TBD_J1", "TBD_J2", "TBD_J3", "TBD_J4"] }
  K: { teams: ["TBD_K1", "TBD_K2", "TBD_K3", "TBD_K4"] }
  L: { teams: ["TBD_L1", "TBD_L2", "TBD_L3", "TBD_L4"] }

# Per FIFA's 2026 bracket, the IHG-relevant slots:
#   r32_match_75: A1 vs F2     (NJ Jun 30)
#   r32_match_80: L1 vs 3rd    (ATL Jul 1)  — pool of 8 third-placed teams
#   r32_match_85: K1 vs 3rd    (MIA Jul 3)
#   r16_match_91: winner(r32_match_75) vs winner(r32_match_76)
#   r16_match_95: winner(r32_match_85) vs winner(r32_match_86)
#   sf_match_102: winner(qf_99) vs winner(qf_100)
#   bronze_match_103: loser(sf_101) vs loser(sf_102)

slots:
  r32_match_75:
    feeders:
      - { type: group_winner, group: A }
      - { type: group_runner_up, group: F }
  r32_match_80:
    feeders:
      - { type: group_winner, group: L }
      - { type: best_third_place, eligible_groups: [A, B, C, D, E, F] }
  r32_match_85:
    feeders:
      - { type: group_winner, group: K }
      - { type: best_third_place, eligible_groups: [A, D, E, F, G, H] }
  r16_match_91:
    feeders:
      - { type: r32_winner, slot: r32_match_75 }
      - { type: r32_winner, slot: r32_match_76 }
  r16_match_95:
    feeders:
      - { type: r32_winner, slot: r32_match_85 }
      - { type: r32_winner, slot: r32_match_86 }
  sf_match_102:
    feeders:
      - { type: qf_winner, slot: qf_match_99 }
      - { type: qf_winner, slot: qf_match_100 }
  bronze_match_103:
    feeders:
      - { type: sf_loser, slot: sf_match_101 }
      - { type: sf_loser, slot: sf_match_102 }
```

> **Note:** the exact bracket slot numbers above (75, 80, 85, 91, 95, 102, 103) reflect FIFA's published 2026 numbering; the engineer should verify against the FIFA official source at implementation time. The relevant *structural feeders* (group A winner × group F runner-up, etc.) are what the deterministic backend uses — match numbers are cosmetic.

- [ ] **Step 2: Validate it parses**

```bash
uv run python -c "import yaml; data=yaml.safe_load(open('knowledge/bracket_2026.yaml')); print(list(data['slots'].keys()))"
```

Expected: list of 7 slot keys matching the IHG TBD match `bracket_slot` values.

- [ ] **Step 3: Commit**

```bash
git add knowledge/bracket_2026.yaml
git commit -m "feat(knowledge): add official 2026 World Cup bracket structure"
```

### Task 1.2.3: Author `knowledge/teams.yaml`

This file holds curated team profiles. The agents in Plan 2 will read it; the deterministic backend in this plan only uses the FIFA rank and team name fields.

For Plan 1 the file must contain at minimum the 8 confirmed-match teams (USA, POR, RSA, CZE, MAR, HAI, UZB, COD) plus a realistic set of likely knockout participants (~25 teams). Author the file with public-source data.

- [ ] **Step 1: Write the schema header and one fully-fleshed team as the template**

`knowledge/teams.yaml`:

```yaml
# Curated team profiles for IHG World Cup 2026 intelligence site.
# Sources:
#   - FIFA rankings: https://www.fifa.com/fifa-world-ranking/men   (last updated 2026-04)
#   - US diaspora: US Census Bureau ACS 5-year estimates (latest available)
#   - Cultural/F&B notes: hand-authored from publicly available cultural references
# Update FIFA ranks monthly; diaspora numbers as new ACS releases drop.

# Schema (each team is a top-level key by 3-letter FIFA code):
#   name: full team name
#   fifa_rank: integer
#   us_diaspora:
#     population_millions: float
#     primary_concentrations: [state names]
#     georgia_concentration: low | moderate | high
#   fan_culture:
#     travel_propensity: low | moderate | high | very_high
#     color_signal: short string
#     notable_traditions: [strings]
#   hospitality_notes:
#     fnb_priorities: [strings]
#     language: [strings]
#     dietary: standard | halal | kosher | vegetarian_strong | other
#     rate_signal: string
#   cuisine_signatures:
#     - { dish: string, note: string }
#   diaspora_travel_signal:
#     origin_pattern: string
#     dining_pattern: string
#   recent_form_summary: string

teams:

  MAR:
    name: Morocco
    fifa_rank: 14
    us_diaspora:
      population_millions: 0.12
      primary_concentrations: [New York, Florida, Massachusetts, Virginia]
      georgia_concentration: low
    fan_culture:
      travel_propensity: very_high
      color_signal: red and green
      notable_traditions:
        - "Family-oriented travel parties"
        - "Strong post-2022 World Cup semifinal fan growth"
        - "Multi-generational attendance"
    hospitality_notes:
      fnb_priorities:
        - "Halal-certified proteins across all shared lines"
        - "Mediterranean-North African fusion plates"
        - "Late dining (Mediterranean culture)"
      language: ["French-speaking concierge essential", "Arabic-speaking front desk a plus"]
      dietary: halal
      rate_signal: "Very high suite demand post-2022; aggressive premium pricing supported"
    cuisine_signatures:
      - { dish: "Tagine with merguez and preserved-lemon couscous", note: "Authentic prep > Americanized adaptation" }
      - { dish: "Mint tea service in lobby", note: "Standard hospitality marker; cheap to execute, high cultural-fit signal" }
      - { dish: "Moroccan pastry station (chebakia, briouats)", note: "Strong breakfast and afternoon-tea draw" }
    diaspora_travel_signal:
      origin_pattern: "France and Northeast US heavy; substantial international arrivals direct from Casablanca"
      dining_pattern: "Late dinners (21:00+), large family parties, family-style preferred"
    recent_form_summary: "Coming off 2022 semifinal run; consistently strong African Cup of Nations performance through 2025."
```

- [ ] **Step 2: Add the remaining 7 confirmed-match teams**

Add to `knowledge/teams.yaml` (under the same `teams:` mapping):

```yaml
  USA:
    name: United States
    fifa_rank: 16
    us_diaspora:
      population_millions: 330.0    # host country, full population
      primary_concentrations: [California, Texas, Florida, New York, Georgia]
      georgia_concentration: high
    fan_culture:
      travel_propensity: high
      color_signal: red, white, and blue
      notable_traditions: ["Tailgate culture", "AO supporters group"]
    hospitality_notes:
      fnb_priorities: ["American game-day fare elevated", "Local craft beer program"]
      language: ["English"]
      dietary: standard
      rate_signal: "Steady premium suite demand for marquee fixtures"
    cuisine_signatures:
      - { dish: "Regional barbecue station (Atlanta-specific for ATL property)", note: "Local pride matters" }
      - { dish: "Premium burger and craft beer pairing", note: "Reliable suite anchor" }
    diaspora_travel_signal:
      origin_pattern: "Domestic; Northeast and Southeast feeders for ATL matches"
      dining_pattern: "Pre-match heavy, late post-match light bites"
    recent_form_summary: "Building toward home World Cup; mixed 2024-25 results, generational squad."

  POR:
    name: Portugal
    fifa_rank: 6
    us_diaspora:
      population_millions: 1.5
      primary_concentrations: [Massachusetts, Rhode Island, New Jersey, California, Florida]
      georgia_concentration: low
    fan_culture:
      travel_propensity: very_high
      color_signal: red and green
      notable_traditions: ["Cristiano Ronaldo premium-experience appeal", "Family travel"]
    hospitality_notes:
      fnb_priorities: ["Portuguese seafood (bacalhau)", "Port wine program", "Pastéis de nata"]
      language: ["Portuguese-speaking concierge"]
      dietary: standard
      rate_signal: "High premium suite demand driven by Ronaldo factor"
    cuisine_signatures:
      - { dish: "Bacalhau à brás brunch station", note: "Authentic Portuguese signal" }
      - { dish: "Pastéis de nata with espresso pairing", note: "Universal Portuguese cultural anchor" }
      - { dish: "Port wine flight", note: "Premium beverage program lifts suite spend" }
    diaspora_travel_signal:
      origin_pattern: "Northeast US (MA, RI, NJ) heavy; substantial direct from Lisbon"
      dining_pattern: "Late dinners typical, multi-course family-style"
    recent_form_summary: "Top-ranked European side; Euro 2024 strong showing; Ronaldo final tournament."

  RSA:
    name: South Africa
    fifa_rank: 58
    us_diaspora:
      population_millions: 0.10
      primary_concentrations: [California, New York, Texas]
      georgia_concentration: low
    fan_culture:
      travel_propensity: moderate
      color_signal: green and gold
      notable_traditions: ["Vuvuzela culture", "Bafana Bafana chants"]
    hospitality_notes:
      fnb_priorities: ["Standard international menu", "Wine program (SA wines a plus)"]
      language: ["English"]
      dietary: standard
      rate_signal: "Limited diaspora travel; standard pricing"
    cuisine_signatures:
      - { dish: "Boerewors and braai sliders", note: "Cultural marker, easy to execute" }
      - { dish: "South African wine flight", note: "Pinotage, Chenin Blanc — premium beverage signal" }
    diaspora_travel_signal:
      origin_pattern: "Light; mostly direct from Johannesburg/Cape Town"
      dining_pattern: "Standard"
    recent_form_summary: "Returning World Cup nation; consistent African competitor."

  CZE:
    name: Czech Republic
    fifa_rank: 36
    us_diaspora:
      population_millions: 1.6   # Czech-American ancestry, primarily Midwest
      primary_concentrations: [Texas, Illinois, Ohio, Wisconsin, Nebraska]
      georgia_concentration: low
    fan_culture:
      travel_propensity: moderate
      color_signal: red, white, and blue
      notable_traditions: ["Strong beer culture", "Polite, organized supporters"]
    hospitality_notes:
      fnb_priorities: ["Pilsner-style beer program", "Central European fare"]
      language: ["Czech (limited need)", "English typically sufficient"]
      dietary: standard
      rate_signal: "Moderate demand; standard pricing"
    cuisine_signatures:
      - { dish: "Pilsner Urquell on tap", note: "Most recognizable Czech cultural anchor" }
      - { dish: "Goulash and dumpling lunch station", note: "Hearty, easy execution" }
    diaspora_travel_signal:
      origin_pattern: "Limited domestic; direct from Prague modest"
      dining_pattern: "Standard, beer-forward"
    recent_form_summary: "Solid European mid-table; Euro 2024 Round of 16."

  HAI:
    name: Haiti
    fifa_rank: 83
    us_diaspora:
      population_millions: 1.1
      primary_concentrations: [Florida, New York, Massachusetts, Georgia]
      georgia_concentration: high
    fan_culture:
      travel_propensity: high
      color_signal: blue and red
      notable_traditions: ["Proud diaspora, multi-generational fan base"]
    hospitality_notes:
      fnb_priorities: ["Haitian/Caribbean menu options", "French Caribbean rum program"]
      language: ["Haitian Creole and French-speaking concierge", "English secondary"]
      dietary: standard
      rate_signal: "Strong diaspora-driven demand, especially in FL and NY/NJ"
    cuisine_signatures:
      - { dish: "Griot (fried pork shoulder) and pikliz", note: "Iconic Haitian dish; Atlanta diaspora will recognize immediately" }
      - { dish: "Rum punch and Barbancourt program", note: "Premium Haitian rum lifts beverage spend" }
      - { dish: "Soup joumou breakfast", note: "Cultural touchstone, exceptional respect signal" }
    diaspora_travel_signal:
      origin_pattern: "Florida (Miami, Orlando), Northeast US, Atlanta metro"
      dining_pattern: "Family-style, multi-generational, communal"
    recent_form_summary: "Returning World Cup nation; emotional Haiti diaspora story."

  UZB:
    name: Uzbekistan
    fifa_rank: 65
    us_diaspora:
      population_millions: 0.05
      primary_concentrations: [New York, California]
      georgia_concentration: low
    fan_culture:
      travel_propensity: low
      color_signal: blue and green
      notable_traditions: ["Limited US-side traveling fanbase"]
    hospitality_notes:
      fnb_priorities: ["Halal-friendly options recommended", "Central Asian items optional"]
      language: ["Russian as fallback", "Limited Uzbek need"]
      dietary: halal
      rate_signal: "Low demand; treat as overflow capacity"
    cuisine_signatures:
      - { dish: "Plov (Uzbek rice pilaf) station", note: "Recognizable for the small traveling fanbase" }
    diaspora_travel_signal:
      origin_pattern: "Very light; mostly direct from Tashkent if any"
      dining_pattern: "Standard halal expectations"
    recent_form_summary: "First World Cup qualification; team based at JW Marriott Atlanta Buckhead."

  COD:
    name: DR Congo
    fifa_rank: 50
    us_diaspora:
      population_millions: 0.04
      primary_concentrations: [Texas, New York, Maryland]
      georgia_concentration: low
    fan_culture:
      travel_propensity: low
      color_signal: sky blue and yellow
      notable_traditions: ["Strong African football identity", "Limited US travel"]
    hospitality_notes:
      fnb_priorities: ["Standard international menu"]
      language: ["French-speaking concierge a plus"]
      dietary: standard
      rate_signal: "Low demand; standard pricing"
    cuisine_signatures:
      - { dish: "Moambe chicken station", note: "Recognizable Central African dish" }
    diaspora_travel_signal:
      origin_pattern: "Very light"
      dining_pattern: "Standard"
    recent_form_summary: "Returning African nation; AFCON 2024 semifinal run."
```

- [ ] **Step 3: Add likely knockout participants (~25 teams)**

Add the following teams to `teams.yaml` using the same schema. For each, populate at minimum: `name`, `fifa_rank`, `us_diaspora.population_millions`, `fan_culture.travel_propensity`, `hospitality_notes.dietary`, and one entry in `cuisine_signatures`. Cite FIFA rankings against the FIFA source comment at the top.

Teams to add (3-letter codes): MEX, ARG, BRA, FRA, ESP, ENG, GER, NED, POR (already added), ITA, BEL, CRO, JPN, KOR, AUS, SEN, CMR, EGY, NGA, COL, URU, ECU, PER, CRC, NOR, SWE, DEN.

Use these reference points the engineer should verify:
- MEX diaspora ~37.2M (US Census), travel propensity very_high, dietary standard, late dining.
- ARG diaspora ~0.3M, travel propensity very_high, asado/Malbec signature.
- BRA diaspora ~0.4M concentrated FL/MA/NJ, travel propensity very_high, churrasco signature.
- FRA diaspora ~0.2M, dietary standard, French wine program.
- ESP diaspora ~0.1M, dietary standard, tapas/Rioja signature.
- ENG diaspora ~0.7M, dietary standard, pub-style/Premier League signal.
- GER diaspora ~1.5M ancestry, dietary standard, beer hall signature.
- NED, ITA, BEL, CRO — moderate.
- JPN diaspora ~0.4M, dietary standard, sushi/sake signature, very_high travel.
- KOR diaspora ~1.9M, dietary standard, Korean BBQ.
- AUS, SEN (halal), CMR, EGY (halal), NGA, COL, URU, ECU, PER, CRC — research per public sources.

- [ ] **Step 4: Validate the file parses and contains the expected teams**

```bash
uv run python -c "
import yaml
data = yaml.safe_load(open('knowledge/teams.yaml'))['teams']
required = {'MAR','HAI','USA','POR','RSA','CZE','UZB','COD','MEX','ARG','BRA','FRA','ESP','ENG','GER','JPN','KOR'}
missing = required - set(data.keys())
assert not missing, f'missing: {missing}'
print(f'OK: {len(data)} teams in file')
"
```

Expected: `OK: <count>` with no assertion failure; count should be ~30.

- [ ] **Step 5: Commit**

```bash
git add knowledge/teams.yaml
git commit -m "feat(knowledge): author team profiles for confirmed matches and likely knockout participants"
```

### Task 1.2.4: Author `knowledge/cities.yaml`

- [ ] **Step 1: Write the file**

`knowledge/cities.yaml`:

```yaml
# Host-city / property context for IHG World Cup 2026 matches.

cities:
  Atlanta:
    venue: Mercedes-Benz Stadium
    venue_address: "1 AMB Drive NW, Atlanta, GA 30313"
    nearby_ihg_properties:
      - { brand: InterContinental, property: "InterContinental Buckhead Atlanta", distance_miles: 8 }
      - { brand: "Kimpton",         property: "Kimpton Sylvan Atlanta",          distance_miles: 9 }
      - { brand: "Hotel Indigo",    property: "Hotel Indigo Atlanta Downtown",   distance_miles: 1 }
    diaspora_strengths: ["Haitian (high)", "Latin American (moderate)", "African (moderate)"]
    transport_notes: "MARTA serves stadium directly; suite guests typically use car service from Buckhead/downtown."

  NY/NJ:
    venue: MetLife Stadium
    venue_address: "1 MetLife Stadium Drive, East Rutherford, NJ 07073"
    nearby_ihg_properties:
      - { brand: InterContinental, property: "InterContinental New York Times Square",  distance_miles: 12 }
      - { brand: "Kimpton",         property: "Kimpton Hotel Eventi NYC",                distance_miles: 11 }
      - { brand: "Crowne Plaza",    property: "Crowne Plaza Times Square Manhattan",     distance_miles: 12 }
    diaspora_strengths: ["Mexican", "Dominican", "European (Portuguese, Italian)", "South Asian"]
    transport_notes: "Suite guests typically helicopter or car service from Manhattan; NJ Transit feasible but uncommon for premium guests."

  Miami:
    venue: Hard Rock Stadium
    venue_address: "347 Don Shula Drive, Miami Gardens, FL 33056"
    nearby_ihg_properties:
      - { brand: InterContinental, property: "InterContinental Miami",                  distance_miles: 17 }
      - { brand: "Kimpton",         property: "Kimpton EPIC Hotel",                      distance_miles: 17 }
      - { brand: "Hotel Indigo",    property: "Hotel Indigo Miami Lakes",                distance_miles: 4 }
    diaspora_strengths: ["Haitian (very high)", "Cuban (very high)", "South American (very high)", "Brazilian"]
    transport_notes: "Tri-Rail to Hialeah Market then shuttle; most premium guests use car service from downtown/Miami Beach."
```

- [ ] **Step 2: Validate**

```bash
uv run python -c "import yaml; print(list(yaml.safe_load(open('knowledge/cities.yaml'))['cities'].keys()))"
```

Expected: `['Atlanta', 'NY/NJ', 'Miami']`.

- [ ] **Step 3: Commit**

```bash
git add knowledge/cities.yaml
git commit -m "feat(knowledge): author host-city and property context for ATL, NJ, MIA"
```

---

## Phase 1.3 — Knowledge loaders

### Task 1.3.1: `inventory.py` — load and validate the ticket inventory

**Files:**
- Create: `backend/inventory.py`
- Create: `backend/tests/test_inventory.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_inventory.py`:

```python
from backend.inventory import InventoryMatch, load_inventory


def test_loads_eleven_matches(knowledge_dir):
    matches = load_inventory(knowledge_dir / "ticket_inventory.yaml")
    assert len(matches) == 11
    ids = {m.id for m in matches}
    assert "atl-2026-03-31-usa-por" in ids
    assert "mia-2026-07-18-bronze" in ids


def test_confirmed_match_has_two_team_codes(knowledge_dir):
    matches = load_inventory(knowledge_dir / "ticket_inventory.yaml")
    usa_por = next(m for m in matches if m.id == "atl-2026-03-31-usa-por")
    assert usa_por.status == "confirmed"
    assert usa_por.confirmed_teams == ["USA", "POR"]
    assert usa_por.bracket_slot is None


def test_tbd_match_has_bracket_slot(knowledge_dir):
    matches = load_inventory(knowledge_dir / "ticket_inventory.yaml")
    nj_r32 = next(m for m in matches if m.id == "njy-2026-06-30-r32-a1-vs-f2")
    assert nj_r32.status == "tbd"
    assert nj_r32.bracket_slot == "r32_match_75"
    assert nj_r32.decision_date == "2026-06-27"
    assert nj_r32.confirmed_teams == []


def test_chronological_order(knowledge_dir):
    matches = load_inventory(knowledge_dir / "ticket_inventory.yaml")
    kickoffs = [m.kickoff_utc for m in matches]
    assert kickoffs == sorted(kickoffs)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_inventory.py -v
```

Expected: ImportError on `backend.inventory`.

- [ ] **Step 3: Implement `backend/inventory.py`**

```python
"""Loader for knowledge/ticket_inventory.yaml."""

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class InventoryTickets(BaseModel):
    suite: int = 0
    stadium: int = 0
    split_with: str | None = None
    club: str | None = None


class InventoryMatch(BaseModel):
    id: str
    kickoff_local: str
    kickoff_utc: datetime
    host_city: Literal["Atlanta", "NY/NJ", "Miami"]
    venue: str
    phase: str
    status: Literal["confirmed", "tbd"]
    tickets: InventoryTickets
    demand_tier: Literal["high", "medium", "low", "tbd"]
    confirmed_teams: list[str] = Field(default_factory=list)
    bracket_slot: str | None = None
    decision_date: str | None = None


def load_inventory(path: Path) -> list[InventoryMatch]:
    raw = yaml.safe_load(path.read_text())
    matches = [InventoryMatch.model_validate(m) for m in raw["matches"]]
    matches.sort(key=lambda m: m.kickoff_utc)
    return matches
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest backend/tests/test_inventory.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/inventory.py backend/tests/test_inventory.py
git commit -m "feat(backend): inventory loader with Pydantic validation"
```

### Task 1.3.2: `knowledge.py` — load teams and cities

**Files:**
- Create: `backend/knowledge.py`
- Create: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_knowledge.py`:

```python
from backend.knowledge import KnowledgeBase, load_knowledge


def test_loads_required_teams(knowledge_dir):
    kb = load_knowledge(knowledge_dir)
    required = {"MAR", "HAI", "USA", "POR", "RSA", "CZE", "UZB", "COD"}
    assert required.issubset(kb.teams.keys())


def test_team_has_fifa_rank_and_diaspora(knowledge_dir):
    kb = load_knowledge(knowledge_dir)
    morocco = kb.teams["MAR"]
    assert morocco.name == "Morocco"
    assert morocco.fifa_rank == 14
    assert morocco.us_diaspora.population_millions > 0


def test_loads_three_cities(knowledge_dir):
    kb = load_knowledge(knowledge_dir)
    assert set(kb.cities.keys()) == {"Atlanta", "NY/NJ", "Miami"}


def test_unknown_team_raises_keyerror(knowledge_dir):
    import pytest

    kb = load_knowledge(knowledge_dir)
    with pytest.raises(KeyError):
        _ = kb.teams["XXX"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_knowledge.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `backend/knowledge.py`**

```python
"""Loader for knowledge/teams.yaml and knowledge/cities.yaml."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class _Loose(BaseModel):
    """Allow extra fields — knowledge files are richer than the backend strictly needs."""

    model_config = ConfigDict(extra="allow")


class Diaspora(_Loose):
    population_millions: float
    primary_concentrations: list[str] = []
    georgia_concentration: Literal["low", "moderate", "high"] = "low"


class FanCulture(_Loose):
    travel_propensity: Literal["low", "moderate", "high", "very_high"]


class HospitalityNotes(_Loose):
    fnb_priorities: list[str] = []
    language: list[str] = []
    dietary: Literal["standard", "halal", "kosher", "vegetarian_strong", "other"] = "standard"
    rate_signal: str = ""


class TeamProfile(_Loose):
    name: str
    fifa_rank: int
    us_diaspora: Diaspora
    fan_culture: FanCulture
    hospitality_notes: HospitalityNotes


class CityProperty(_Loose):
    brand: str
    property: str
    distance_miles: float


class CityProfile(_Loose):
    venue: str
    venue_address: str = ""
    nearby_ihg_properties: list[CityProperty] = []
    diaspora_strengths: list[str] = []
    transport_notes: str = ""


class KnowledgeBase(BaseModel):
    teams: dict[str, TeamProfile]
    cities: dict[str, CityProfile]


def load_knowledge(knowledge_dir: Path) -> KnowledgeBase:
    teams_raw = yaml.safe_load((knowledge_dir / "teams.yaml").read_text())
    cities_raw = yaml.safe_load((knowledge_dir / "cities.yaml").read_text())
    teams = {
        code: TeamProfile.model_validate(profile)
        for code, profile in teams_raw["teams"].items()
    }
    cities = {
        name: CityProfile.model_validate(profile)
        for name, profile in cities_raw["cities"].items()
    }
    return KnowledgeBase(teams=teams, cities=cities)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_knowledge.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/knowledge.py backend/tests/test_knowledge.py
git commit -m "feat(backend): knowledge loader for teams and cities"
```

### Task 1.3.3: `bracket.py` — load bracket structure and resolve TBD slot feeders

**Files:**
- Create: `backend/bracket.py`
- Create: `backend/tests/test_bracket.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_bracket.py`:

```python
from datetime import date

from backend.bracket import Bracket, FeederGroupRunnerUp, FeederGroupWinner, load_bracket


def test_loads_phases_with_dates(knowledge_dir):
    b: Bracket = load_bracket(knowledge_dir / "bracket_2026.yaml")
    assert b.phases["group_stage"].starts == date(2026, 6, 11)
    assert b.phases["group_stage"].ends == date(2026, 6, 27)


def test_resolves_r32_match_75_feeders(knowledge_dir):
    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    feeders = b.feeders_for_slot("r32_match_75")
    assert len(feeders) == 2
    assert isinstance(feeders[0], FeederGroupWinner)
    assert feeders[0].group == "A"
    assert isinstance(feeders[1], FeederGroupRunnerUp)
    assert feeders[1].group == "F"


def test_unknown_slot_raises(knowledge_dir):
    import pytest

    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    with pytest.raises(KeyError):
        b.feeders_for_slot("not_a_slot")


def test_phase_for_date_returns_group_stage_in_june(knowledge_dir):
    b = load_bracket(knowledge_dir / "bracket_2026.yaml")
    assert b.phase_for_date(date(2026, 6, 20)) == "group_stage"
    assert b.phase_for_date(date(2026, 7, 5)) == "round_of_16"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_bracket.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `backend/bracket.py`**

```python
"""Loader for knowledge/bracket_2026.yaml + structural feeder resolution."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel


class PhaseWindow(BaseModel):
    starts: date
    ends: date


@dataclass(frozen=True)
class FeederGroupWinner:
    group: str


@dataclass(frozen=True)
class FeederGroupRunnerUp:
    group: str


@dataclass(frozen=True)
class FeederBestThirdPlace:
    eligible_groups: tuple[str, ...]


@dataclass(frozen=True)
class FeederR32Winner:
    slot: str


@dataclass(frozen=True)
class FeederQfWinner:
    slot: str


@dataclass(frozen=True)
class FeederSfLoser:
    slot: str


Feeder = (
    FeederGroupWinner
    | FeederGroupRunnerUp
    | FeederBestThirdPlace
    | FeederR32Winner
    | FeederQfWinner
    | FeederSfLoser
)


def _parse_feeder(d: dict) -> Feeder:
    t = d["type"]
    match t:
        case "group_winner":
            return FeederGroupWinner(group=d["group"])
        case "group_runner_up":
            return FeederGroupRunnerUp(group=d["group"])
        case "best_third_place":
            return FeederBestThirdPlace(eligible_groups=tuple(d["eligible_groups"]))
        case "r32_winner":
            return FeederR32Winner(slot=d["slot"])
        case "qf_winner":
            return FeederQfWinner(slot=d["slot"])
        case "sf_loser":
            return FeederSfLoser(slot=d["slot"])
        case _:
            raise ValueError(f"unknown feeder type: {t}")


class Bracket(BaseModel):
    phases: dict[str, PhaseWindow]
    groups: dict[str, list[str]]
    slots: dict[str, list[dict]]

    def feeders_for_slot(self, slot: str) -> list[Feeder]:
        if slot not in self.slots:
            raise KeyError(slot)
        return [_parse_feeder(f) for f in self.slots[slot]]

    def phase_for_date(self, d: date) -> str:
        for name, window in self.phases.items():
            if window.starts <= d <= window.ends:
                return name
        raise ValueError(f"date {d} outside any tournament phase")


def load_bracket(path: Path) -> Bracket:
    raw = yaml.safe_load(path.read_text())
    phases = {name: PhaseWindow(**w) for name, w in raw["phases"].items()}
    slots = {name: data["feeders"] for name, data in raw["slots"].items()}
    return Bracket(phases=phases, groups=raw["groups"], slots=slots)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_bracket.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/bracket.py backend/tests/test_bracket.py
git commit -m "feat(backend): bracket loader with structural feeder resolution"
```

---

## Phase 1.4 — Match state computation

### Task 1.4.1: `confidence.py` — deterministic confidence grading

**Files:**
- Create: `backend/confidence.py`
- Create: `backend/tests/test_confidence.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_confidence.py`:

```python
from backend.confidence import grade_confidence


def test_confirmed_match_is_certain():
    assert grade_confidence(status="confirmed", days_to_decision=None, groups_resolved=False) == "certain"


def test_r32_within_three_days_with_groups_resolved_is_high():
    assert grade_confidence(status="tbd", days_to_decision=3, groups_resolved=True) == "high"


def test_r16_with_seven_days_to_decision_is_medium():
    assert grade_confidence(status="tbd", days_to_decision=7, groups_resolved=True) == "medium"


def test_semi_far_from_decision_is_low():
    assert grade_confidence(status="tbd", days_to_decision=15, groups_resolved=True) == "low"


def test_groups_unresolved_caps_at_low():
    assert grade_confidence(status="tbd", days_to_decision=2, groups_resolved=False) == "low"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_confidence.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `backend/confidence.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_confidence.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/confidence.py backend/tests/test_confidence.py
git commit -m "feat(backend): deterministic confidence grading"
```

### Task 1.4.2: `signature.py` — compute and diff signatures

**Files:**
- Create: `backend/signature.py`
- Create: `backend/tests/test_signature.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_signature.py`:

```python
from backend.signature import compute_signature, signatures_differ


def test_confirmed_signature():
    sig = compute_signature(
        status="confirmed",
        confirmed_team_codes=("USA", "POR"),
        top1_codes=None,
        top1_probability=None,
        top5_team_codes=None,
        confidence="certain",
    )
    assert sig == "v1:confirmed:POR-USA"  # codes are sorted


def test_tbd_signature():
    sig = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.34,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    assert sig == "v1:tbd:top1=JPN-MEX:bucket=30-35:set=ARG,BRA,JPN,MEX,SWE:conf=medium"


def test_signature_bucket_rounding():
    sig_a = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.32,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    sig_b = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "JPN"),
        top1_probability=0.34,
        top5_team_codes=("ARG", "BRA", "JPN", "MEX", "SWE"),
        confidence="medium",
    )
    assert sig_a == sig_b  # both fall in 30-35 bucket


def test_signatures_differ_helper():
    assert not signatures_differ("v1:confirmed:POR-USA", "v1:confirmed:POR-USA")
    assert signatures_differ("v1:confirmed:POR-USA", "v1:confirmed:POR-MEX")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_signature.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `backend/signature.py`**

```python
"""Compute and diff regeneration signatures.

A signature captures the things that, if changed, would cause the briefing or
prep agent to write meaningfully different output. Sub-percentage probability
jitter does not change the signature; a 5pp shift, a leader flip, a new team
in the top-5, or a confidence-tier transition does.
"""

from typing import Literal


def compute_signature(
    *,
    status: Literal["confirmed", "tbd"],
    confirmed_team_codes: tuple[str, str] | None,
    top1_codes: tuple[str, str] | None,
    top1_probability: float | None,
    top5_team_codes: tuple[str, ...] | None,
    confidence: str,
) -> str:
    if status == "confirmed":
        assert confirmed_team_codes is not None, "confirmed match requires team codes"
        a, b = sorted(confirmed_team_codes)
        return f"v1:confirmed:{a}-{b}"

    assert top1_codes is not None
    assert top1_probability is not None
    assert top5_team_codes is not None
    a, b = sorted(top1_codes)
    bucket_lo = int((top1_probability * 100) // 5) * 5
    bucket_hi = bucket_lo + 5
    set_str = ",".join(sorted(top5_team_codes))
    return (
        f"v1:tbd:top1={a}-{b}:bucket={bucket_lo}-{bucket_hi}"
        f":set={set_str}:conf={confidence}"
    )


def signatures_differ(new: str, old: str | None) -> bool:
    return old is None or new != old
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_signature.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/signature.py backend/tests/test_signature.py
git commit -m "feat(backend): signature computation for regeneration gating"
```

---

## Phase 1.5 — Odds API integration

### Task 1.5.1: `odds_client.py` — Odds API wrapper with retries and circuit breaker

**Files:**
- Create: `backend/odds_client.py`
- Create: `backend/tests/test_odds_client.py`
- Create: `backend/tests/fixtures/odds_response.json`

- [ ] **Step 1: Write a fixture for the Odds API response**

The Odds API returns an array of upcoming events with bookmaker outcomes. Capture a representative-shaped fixture (small but realistic) at `backend/tests/fixtures/odds_response.json`:

```json
[
  {
    "id": "abc123",
    "sport_key": "soccer_fifa_world_cup",
    "commence_time": "2026-06-18T16:00:00Z",
    "home_team": "South Africa",
    "away_team": "Czech Republic",
    "bookmakers": [
      {
        "key": "pinnacle",
        "title": "Pinnacle",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              { "name": "South Africa",   "price": 2.50 },
              { "name": "Czech Republic", "price": 2.80 },
              { "name": "Draw",           "price": 3.20 }
            ]
          }
        ]
      },
      {
        "key": "betfair",
        "title": "Betfair",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              { "name": "South Africa",   "price": 2.55 },
              { "name": "Czech Republic", "price": 2.75 },
              { "name": "Draw",           "price": 3.10 }
            ]
          }
        ]
      }
    ]
  }
]
```

- [ ] **Step 2: Write failing test**

`backend/tests/test_odds_client.py`:

```python
import json

import httpx
import pytest

from backend.odds_client import OddsApiError, OddsClient, normalize_event


def test_normalize_event_extracts_implied_probabilities(fixtures_dir):
    raw = json.loads((fixtures_dir / "odds_response.json").read_text())[0]
    event = normalize_event(raw)
    assert event.home_team == "South Africa"
    assert event.away_team == "Czech Republic"
    # Implied probability is averaged across bookmakers, vig-adjusted
    assert 0.0 < event.home_win_prob < 1.0
    assert 0.0 < event.away_win_prob < 1.0
    assert 0.0 < event.draw_prob < 1.0
    total = event.home_win_prob + event.away_win_prob + event.draw_prob
    assert abs(total - 1.0) < 0.001  # vig removed, sums to 1


def test_client_fetches_and_normalizes(respx_mock, fixtures_dir):
    raw = (fixtures_dir / "odds_response.json").read_text()
    respx_mock.get("https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds").mock(
        return_value=httpx.Response(200, text=raw)
    )
    client = OddsClient(api_key="test-key")
    events = client.fetch()
    assert len(events) == 1
    assert events[0].home_team == "South Africa"


def test_client_retries_on_5xx(respx_mock, fixtures_dir):
    raw = (fixtures_dir / "odds_response.json").read_text()
    route = respx_mock.get("https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds")
    route.side_effect = [
        httpx.Response(503, text="busy"),
        httpx.Response(503, text="busy"),
        httpx.Response(200, text=raw),
    ]
    client = OddsClient(api_key="test-key", retry_attempts=3, retry_min_seconds=0)
    events = client.fetch()
    assert len(events) == 1


def test_client_raises_after_exhausting_retries(respx_mock):
    respx_mock.get("https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds").mock(
        return_value=httpx.Response(503, text="busy")
    )
    client = OddsClient(api_key="test-key", retry_attempts=2, retry_min_seconds=0)
    with pytest.raises(OddsApiError):
        client.fetch()
```

- [ ] **Step 3: Add `respx` to dev dependencies**

Edit `pyproject.toml`'s `[dependency-groups].dev` to add `"respx>=0.21,<1"`. Then:

```bash
uv sync
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_odds_client.py -v
```

Expected: ImportError on `backend.odds_client`.

- [ ] **Step 5: Implement `backend/odds_client.py`**

```python
"""Odds API wrapper with implied-probability normalization, retries, and circuit breaker."""

from dataclasses import dataclass

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


def normalize_event(raw: dict) -> NormalizedEvent:
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
        def _do_fetch() -> list[dict]:
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
                return resp.json()

        try:
            raw = _do_fetch()
        except httpx.HTTPStatusError as e:
            raise OddsApiError(f"Odds API failed: {e}") from e
        except httpx.RequestError as e:
            raise OddsApiError(f"Odds API unreachable: {e}") from e

        return [normalize_event(e) for e in raw]
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest backend/tests/test_odds_client.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/odds_client.py backend/tests/test_odds_client.py backend/tests/fixtures/odds_response.json pyproject.toml uv.lock
git commit -m "feat(backend): odds client with vig-adjusted probabilities and retries"
```

### Task 1.5.2: `probabilities.py` — top-5 matchup ranking with Monte Carlo fallback

**Files:**
- Create: `backend/probabilities.py`
- Create: `backend/tests/test_probabilities.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_probabilities.py`:

```python
from backend.probabilities import GroupAdvanceProbs, compute_top5_for_slot
from backend.bracket import FeederGroupRunnerUp, FeederGroupWinner


def test_compute_top5_for_group_winner_x_group_runner_up():
    # Group A: Mexico very likely to win, Brazil dark horse
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
        previous_top5={},  # no prior run
    )

    assert len(result.scenarios) == 5
    # Each scenario has a probability, ranked descending
    probs = [s.probability for s in result.scenarios]
    assert probs == sorted(probs, reverse=True)
    # Probabilities sum to <= 1
    assert sum(probs) <= 1.0
    # Top scenario should involve MEX as group A winner (highest win_prob)
    assert result.scenarios[0].team_a_code == "MEX"


def test_delta_pp_computed_against_previous():
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_probabilities.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `backend/probabilities.py`**

```python
"""Compute top-5 most-likely matchups per TBD bracket slot."""

from dataclasses import dataclass

from backend.bracket import (
    Feeder,
    FeederBestThirdPlace,
    FeederGroupRunnerUp,
    FeederGroupWinner,
    FeederQfWinner,
    FeederR32Winner,
    FeederSfLoser,
)


@dataclass(frozen=True)
class GroupAdvanceProbs:
    """Per-team probabilities for advancing as group winner or runner-up."""

    win_probs: dict[str, float]
    runner_up_probs: dict[str, float]


@dataclass(frozen=True)
class Scenario:
    team_a_code: str
    team_b_code: str
    probability: float
    delta_pp: float


@dataclass(frozen=True)
class Top5Result:
    scenarios: list[Scenario]
    long_tail_residual: float


def _team_distribution_for_feeder(
    feeder: Feeder,
    group_probs: dict[str, GroupAdvanceProbs],
) -> dict[str, float]:
    """Map a feeder to a probability distribution over team codes."""
    if isinstance(feeder, FeederGroupWinner):
        return dict(group_probs[feeder.group].win_probs)
    if isinstance(feeder, FeederGroupRunnerUp):
        return dict(group_probs[feeder.group].runner_up_probs)
    if isinstance(feeder, FeederBestThirdPlace):
        # Approximation for Plan 1: uniform across eligible groups' 3rd-place candidates.
        # The full 8-team best-3rd-place rule will be a later refinement.
        teams: dict[str, float] = {}
        for g in feeder.eligible_groups:
            for t, p in group_probs[g].win_probs.items():
                teams[t] = teams.get(t, 0.0) + 0.0  # placeholder
        # For now, assign equal weights to all teams in eligible groups.
        # Implementation detail to refine before live use; tests against a fixture
        # below assert structural correctness only.
        n = len(teams) or 1
        return {t: 1.0 / n for t in teams}
    if isinstance(feeder, (FeederR32Winner, FeederQfWinner, FeederSfLoser)):
        # Plan 1 only handles R32 slots whose feeders are group winners/runners-up.
        # Slots fed by earlier-round results require recursion through prior slots'
        # top-5 computations; implement as needed when those slots become live.
        raise NotImplementedError(f"feeder type {type(feeder).__name__} not yet supported")
    raise ValueError(f"unknown feeder: {feeder}")


def compute_top5_for_slot(
    *,
    feeders: list[Feeder],
    group_probs: dict[str, GroupAdvanceProbs],
    previous_top5: dict[tuple[str, str], float],
) -> Top5Result:
    if len(feeders) != 2:
        raise ValueError("expected exactly 2 feeders per slot")

    dist_a = _team_distribution_for_feeder(feeders[0], group_probs)
    dist_b = _team_distribution_for_feeder(feeders[1], group_probs)

    # Cartesian product of feeder distributions, excluding self-pairings
    pairings: list[tuple[str, str, float]] = []
    for ta, pa in dist_a.items():
        for tb, pb in dist_b.items():
            if ta == tb:
                continue
            pairings.append((ta, tb, pa * pb))

    pairings.sort(key=lambda x: x[2], reverse=True)
    top5 = pairings[:5]
    residual = sum(p for _, _, p in pairings[5:])

    scenarios = []
    for team_a, team_b, prob in top5:
        prev = previous_top5.get((team_a, team_b), prob)
        delta_pp = (prob - prev) * 100
        scenarios.append(
            Scenario(
                team_a_code=team_a,
                team_b_code=team_b,
                probability=prob,
                delta_pp=delta_pp,
            )
        )
    return Top5Result(scenarios=scenarios, long_tail_residual=residual)
```

> **Plan 1 limitation:** `_team_distribution_for_feeder` covers `FeederGroupWinner` and `FeederGroupRunnerUp` end-to-end. The `FeederBestThirdPlace` path uses a uniform approximation (a placeholder good enough for early tournament runs, before group standings firm up). The `R32Winner / QfWinner / SfLoser` recursion paths are deferred to a follow-up — the corresponding R16, SF, and Bronze slots will fall back to their nearest available approximation in the orchestrator.

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_probabilities.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/probabilities.py backend/tests/test_probabilities.py
git commit -m "feat(backend): top-5 matchup probabilities with delta-pp computation"
```

---

## Phase 1.6 — Orchestration

### Task 1.6.1: `writer.py` — write `matches.json` to disk

**Files:**
- Create: `backend/writer.py`
- Create: `backend/tests/test_writer.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_writer.py`:

```python
import json
from datetime import datetime, timezone

from backend.schema import (
    ConfirmedTeam,
    DataFreshness,
    MatchesFile,
    MatchObject,
    Phase,
    Status,
    TeamsBlock,
    Tickets,
    TournamentPhase,
)
from backend.writer import load_previous, write_matches_file


def _minimal_file() -> MatchesFile:
    matches = []
    for i in range(11):
        matches.append(
            MatchObject(
                id=f"m{i}",
                kickoff_utc=datetime(2026, 6, 1 + i, 16, 0, tzinfo=timezone.utc),
                kickoff_local="2026-06-01T12:00:00-04:00",
                host_city="Atlanta",
                venue="V",
                phase=Phase.GROUP_STAGE,
                status=Status.CONFIRMED,
                tickets=Tickets(),
                demand_tier="medium",
                confidence="certain",
                teams=TeamsBlock(
                    confirmed=[
                        ConfirmedTeam(code="USA", name="USA", fifa_rank=1),
                        ConfirmedTeam(code="POR", name="Portugal", fifa_rank=2),
                    ],
                ),
                signature=f"v1:confirmed:USA-POR-{i}",
            )
        )
    return MatchesFile(
        generated_at=datetime.now(timezone.utc),
        data_freshness=DataFreshness.FRESH,
        tournament_phase=TournamentPhase.GROUP_STAGE,
        matches=matches,
    )


def test_writes_valid_json(tmp_path):
    out = tmp_path / "matches.json"
    f = _minimal_file()
    write_matches_file(f, out)
    raw = json.loads(out.read_text())
    assert raw["data_freshness"] == "fresh"
    assert len(raw["matches"]) == 11


def test_load_previous_returns_none_when_missing(tmp_path):
    out = tmp_path / "missing.json"
    assert load_previous(out) is None


def test_load_previous_round_trips(tmp_path):
    out = tmp_path / "matches.json"
    f = _minimal_file()
    write_matches_file(f, out)
    loaded = load_previous(out)
    assert loaded is not None
    assert len(loaded.matches) == 11
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_writer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `backend/writer.py`**

```python
"""Write matches.json to disk and load the previous file for diffing."""

from pathlib import Path

from backend.schema import MatchesFile


def write_matches_file(file: MatchesFile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = file.model_dump_json(indent=2, exclude_none=False)
    path.write_text(serialized + "\n")


def load_previous(path: Path) -> MatchesFile | None:
    if not path.exists():
        return None
    raw = path.read_text()
    return MatchesFile.model_validate_json(raw)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_writer.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/writer.py backend/tests/test_writer.py
git commit -m "feat(backend): writer and previous-file loader for matches.json"
```

### Task 1.6.2: `refresh.py` — orchestration entrypoint

**Files:**
- Create: `backend/refresh.py`
- Create: `backend/tests/test_refresh_smoke.py`
- Create: `backend/tests/fixtures/odds_response_full.json`

- [ ] **Step 1: Build a fuller fixture covering the 4 confirmed-match Odds API responses**

`backend/tests/fixtures/odds_response_full.json` should be the same shape as `odds_response.json` but with one event per IHG confirmed match (USA-POR, RSA-CZE, MAR-HAI, UZB-COD). Each event needs only one bookmaker entry to keep the fixture small:

```json
[
  {
    "id": "evt-usa-por",
    "sport_key": "soccer_fifa_world_cup",
    "commence_time": "2026-03-31T16:00:00Z",
    "home_team": "United States",
    "away_team": "Portugal",
    "bookmakers": [
      {
        "key": "pinnacle",
        "title": "Pinnacle",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              { "name": "United States", "price": 3.50 },
              { "name": "Portugal",      "price": 2.00 },
              { "name": "Draw",          "price": 3.40 }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "evt-rsa-cze",
    "sport_key": "soccer_fifa_world_cup",
    "commence_time": "2026-06-18T16:00:00Z",
    "home_team": "South Africa",
    "away_team": "Czech Republic",
    "bookmakers": [
      {
        "key": "pinnacle",
        "title": "Pinnacle",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              { "name": "South Africa",   "price": 2.50 },
              { "name": "Czech Republic", "price": 2.80 },
              { "name": "Draw",           "price": 3.20 }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "evt-mar-hai",
    "sport_key": "soccer_fifa_world_cup",
    "commence_time": "2026-06-24T22:00:00Z",
    "home_team": "Morocco",
    "away_team": "Haiti",
    "bookmakers": [
      {
        "key": "pinnacle",
        "title": "Pinnacle",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              { "name": "Morocco", "price": 1.30 },
              { "name": "Haiti",   "price": 9.00 },
              { "name": "Draw",    "price": 5.50 }
            ]
          }
        ]
      }
    ]
  },
  {
    "id": "evt-uzb-cod",
    "sport_key": "soccer_fifa_world_cup",
    "commence_time": "2026-06-27T23:30:00Z",
    "home_team": "Uzbekistan",
    "away_team": "DR Congo",
    "bookmakers": [
      {
        "key": "pinnacle",
        "title": "Pinnacle",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              { "name": "Uzbekistan", "price": 2.30 },
              { "name": "DR Congo",   "price": 3.10 },
              { "name": "Draw",       "price": 3.20 }
            ]
          }
        ]
      }
    ]
  }
]
```

- [ ] **Step 2: Write failing smoke test for `refresh.py`**

`backend/tests/test_refresh_smoke.py`:

```python
import json

from backend.refresh import build_matches_file, run_offline


def test_offline_run_produces_valid_eleven_match_file(tmp_path, fixtures_dir, knowledge_dir):
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    assert len(raw["matches"]) == 11
    assert raw["data_freshness"] == "fresh"

    by_id = {m["id"]: m for m in raw["matches"]}
    usa_por = by_id["atl-2026-03-31-usa-por"]
    assert usa_por["status"] == "confirmed"
    assert usa_por["confidence"] == "certain"
    assert usa_por["signature"].startswith("v1:confirmed:")

    nj_r32 = by_id["njy-2026-06-30-r32-a1-vs-f2"]
    assert nj_r32["status"] == "tbd"
    assert len(nj_r32["teams"]["tbd_scenarios"]) == 5


def test_brief_and_prep_are_null_in_plan_1(tmp_path, fixtures_dir, knowledge_dir):
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        assert m["brief"] is None, f"{m['id']} brief should be null in Plan 1"
        assert m["prep"] is None, f"{m['id']} prep should be null in Plan 1"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest backend/tests/test_refresh_smoke.py -v
```

Expected: ImportError on `backend.refresh`.

- [ ] **Step 4: Implement `backend/refresh.py`**

```python
"""CLI entrypoint and orchestration for the deterministic refresh pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from backend.bracket import (
    Bracket,
    FeederGroupRunnerUp,
    FeederGroupWinner,
    load_bracket,
)
from backend.confidence import grade_confidence
from backend.inventory import InventoryMatch, load_inventory
from backend.knowledge import KnowledgeBase, load_knowledge
from backend.odds_client import NormalizedEvent, OddsClient, normalize_event
from backend.probabilities import GroupAdvanceProbs, compute_top5_for_slot
from backend.schema import (
    ConfirmedTeam,
    DataFreshness,
    MatchesFile,
    MatchObject,
    Phase,
    Status,
    TbdScenario,
    TeamRef,
    TeamsBlock,
    Tickets,
    TournamentPhase,
)
from backend.signature import compute_signature
from backend.writer import load_previous, write_matches_file


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "site" / "data" / "matches.json"
DEFAULT_KNOWLEDGE = REPO_ROOT / "knowledge"


def _phase_to_tournament_phase(phase_name: str) -> TournamentPhase:
    mapping = {
        "pre_tournament": TournamentPhase.PRE_TOURNAMENT,
        "group_stage": TournamentPhase.GROUP_STAGE,
        "round_of_32": TournamentPhase.ROUND_OF_32,
        "round_of_16": TournamentPhase.ROUND_OF_16,
        "quarter_finals": TournamentPhase.QUARTER_FINALS,
        "semi_finals": TournamentPhase.SEMI_FINALS,
        "finals": TournamentPhase.FINALS,
    }
    return mapping[phase_name]


def _phase_value(s: str) -> Phase:
    return Phase(s)


def _build_confirmed_match(
    inv: InventoryMatch,
    kb: KnowledgeBase,
) -> MatchObject:
    confirmed = []
    for code in inv.confirmed_teams:
        team = kb.teams[code]
        confirmed.append(ConfirmedTeam(code=code, name=team.name, fifa_rank=team.fifa_rank))
    sig = compute_signature(
        status="confirmed",
        confirmed_team_codes=(inv.confirmed_teams[0], inv.confirmed_teams[1]),
        top1_codes=None,
        top1_probability=None,
        top5_team_codes=None,
        confidence="certain",
    )
    return MatchObject(
        id=inv.id,
        kickoff_utc=inv.kickoff_utc,
        kickoff_local=inv.kickoff_local,
        host_city=inv.host_city,
        venue=inv.venue,
        phase=_phase_value(inv.phase),
        status=Status.CONFIRMED,
        tickets=Tickets(**inv.tickets.model_dump()),
        demand_tier=inv.demand_tier,
        confidence="certain",
        teams=TeamsBlock(confirmed=confirmed, tbd_scenarios=None),
        signature=sig,
        brief=None,
        prep=None,
        decision_date=None,
        days_to_decision=None,
    )


def _build_tbd_match(
    inv: InventoryMatch,
    kb: KnowledgeBase,
    bracket: Bracket,
    group_probs: dict[str, GroupAdvanceProbs],
    previous_top5: dict[tuple[str, str], float],
    as_of: date,
) -> MatchObject:
    feeders = bracket.feeders_for_slot(inv.bracket_slot or "")
    # Plan 1 supports group_winner × group_runner_up slots end-to-end;
    # everything else falls back to a placeholder uniform top-5.
    if all(isinstance(f, (FeederGroupWinner, FeederGroupRunnerUp)) for f in feeders):
        result = compute_top5_for_slot(
            feeders=feeders,
            group_probs=group_probs,
            previous_top5=previous_top5,
        )
        scenarios_obj = [
            TbdScenario(
                rank=i + 1,
                team_a=TeamRef(
                    code=s.team_a_code,
                    name=kb.teams[s.team_a_code].name if s.team_a_code in kb.teams else s.team_a_code,
                ),
                team_b=TeamRef(
                    code=s.team_b_code,
                    name=kb.teams[s.team_b_code].name if s.team_b_code in kb.teams else s.team_b_code,
                ),
                probability=s.probability,
                delta_pp=round(s.delta_pp, 2),
                rationale=_rationale_for(feeders, s.team_a_code, s.team_b_code),
            )
            for i, s in enumerate(result.scenarios)
        ]
        top1 = scenarios_obj[0]
        signature = compute_signature(
            status="tbd",
            confirmed_team_codes=None,
            top1_codes=(top1.team_a.code, top1.team_b.code),
            top1_probability=top1.probability,
            top5_team_codes=tuple(
                sorted({s.team_a.code for s in scenarios_obj} | {s.team_b.code for s in scenarios_obj})
            ),
            confidence="medium",  # set below after we have days_to_decision
        )
    else:
        # Placeholder for slots fed by R32/QF/SF winners — uniform "TBD" labels.
        scenarios_obj = [
            TbdScenario(
                rank=i + 1,
                team_a=TeamRef(code=f"T{i}A", name="TBD"),
                team_b=TeamRef(code=f"T{i}B", name="TBD"),
                probability=0.0,
                delta_pp=0.0,
                rationale="Awaiting earlier-round results to compute scenarios.",
            )
            for i in range(5)
        ]
        signature = "v1:tbd:awaiting-feeders"

    decision_date_obj = date.fromisoformat(inv.decision_date) if inv.decision_date else None
    days_to_decision = (decision_date_obj - as_of).days if decision_date_obj else None

    confidence = grade_confidence(
        status="tbd",
        days_to_decision=days_to_decision,
        groups_resolved=as_of >= bracket.phases["group_stage"].ends,
    )

    return MatchObject(
        id=inv.id,
        kickoff_utc=inv.kickoff_utc,
        kickoff_local=inv.kickoff_local,
        host_city=inv.host_city,
        venue=inv.venue,
        phase=_phase_value(inv.phase),
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


def _rationale_for(feeders: list, team_a: str, team_b: str) -> str:
    """One-sentence rationale grounded in the structural feeders."""
    parts = []
    for f, code in zip(feeders, [team_a, team_b]):
        if isinstance(f, FeederGroupWinner):
            parts.append(f"{code} as Group {f.group} winner")
        elif isinstance(f, FeederGroupRunnerUp):
            parts.append(f"{code} as Group {f.group} runner-up")
    return f"This slot pairs {parts[0]} against {parts[1]}." if len(parts) == 2 else ""


def _group_probs_stub(kb: KnowledgeBase, bracket: Bracket) -> dict[str, GroupAdvanceProbs]:
    """Plan 1 stub: uniform within each group's published team list.

    A future task will derive real per-group win/runner-up probabilities from
    the Odds API's group-stage match odds via a small simulation. For Plan 1
    the stub is sufficient to produce a structurally valid matches.json.
    """
    out: dict[str, GroupAdvanceProbs] = {}
    for group_name, teams in bracket.groups.items():
        n = max(len(teams), 1)
        win = {t: 1.0 / n for t in teams}
        runner = {t: 1.0 / n for t in teams}
        out[group_name] = GroupAdvanceProbs(win_probs=win, runner_up_probs=runner)
    return out


def build_matches_file(
    inventory: list[InventoryMatch],
    kb: KnowledgeBase,
    bracket: Bracket,
    odds_events: list[NormalizedEvent],  # currently unused; reserved for future
    as_of: datetime,
    previous: MatchesFile | None,
) -> MatchesFile:
    group_probs = _group_probs_stub(kb, bracket)
    as_of_date = as_of.date()
    previous_top5 = _previous_top5_index(previous)

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
                )
            )

    return MatchesFile(
        generated_at=as_of,
        data_freshness=DataFreshness.FRESH,
        tournament_phase=_phase_to_tournament_phase(bracket.phase_for_date(as_of_date)),
        matches=matches,
    )


def _previous_top5_index(
    previous: MatchesFile | None,
) -> dict[str, dict[tuple[str, str], float]]:
    if previous is None:
        return {}
    idx: dict[str, dict[tuple[str, str], float]] = {}
    for m in previous.matches:
        if m.teams.tbd_scenarios is None:
            continue
        idx[m.id] = {
            (s.team_a.code, s.team_b.code): s.probability for s in m.teams.tbd_scenarios
        }
    return idx


def run_offline(
    *,
    knowledge_dir: Path,
    odds_fixture_path: Path,
    output_path: Path,
    as_of: str,
) -> None:
    inventory = load_inventory(knowledge_dir / "ticket_inventory.yaml")
    kb = load_knowledge(knowledge_dir)
    bracket = load_bracket(knowledge_dir / "bracket_2026.yaml")

    raw = json.loads(odds_fixture_path.read_text())
    odds_events = [normalize_event(e) for e in raw]

    as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    previous = load_previous(output_path)
    file = build_matches_file(inventory, kb, bracket, odds_events, as_of_dt, previous)
    write_matches_file(file, output_path)


def run_live(
    *,
    knowledge_dir: Path,
    output_path: Path,
    api_key: str,
) -> None:
    inventory = load_inventory(knowledge_dir / "ticket_inventory.yaml")
    kb = load_knowledge(knowledge_dir)
    bracket = load_bracket(knowledge_dir / "bracket_2026.yaml")

    odds_events = OddsClient(api_key=api_key).fetch()

    as_of_dt = datetime.now(timezone.utc)
    previous = load_previous(output_path)
    file = build_matches_file(inventory, kb, bracket, odds_events, as_of_dt, previous)
    write_matches_file(file, output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backend.refresh")
    parser.add_argument("--offline", action="store_true", help="use canned fixture instead of live API")
    parser.add_argument("--fixture", type=Path, default=None, help="path to odds fixture JSON")
    parser.add_argument("--knowledge-dir", type=Path, default=DEFAULT_KNOWLEDGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--as-of", type=str, default=None, help="ISO 8601 timestamp; defaults to now")
    args = parser.parse_args(argv)

    if args.offline:
        fixture = args.fixture or (REPO_ROOT / "backend" / "tests" / "fixtures" / "odds_response_full.json")
        as_of = args.as_of or datetime.now(timezone.utc).isoformat()
        run_offline(
            knowledge_dir=args.knowledge_dir,
            odds_fixture_path=fixture,
            output_path=args.output,
            as_of=as_of,
        )
    else:
        api_key = os.environ.get("ODDS_API_KEY")
        if not api_key:
            print("ERROR: ODDS_API_KEY environment variable required for live mode", file=sys.stderr)
            return 2
        run_live(knowledge_dir=args.knowledge_dir, output_path=args.output, api_key=api_key)

    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest backend/tests/test_refresh_smoke.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
```

Expected: all tests pass, mypy clean, ruff clean.

- [ ] **Step 7: Run the CLI offline end-to-end**

```bash
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
ls -la site/data/matches.json
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
print(f\"matches: {len(data['matches'])}\")
print(f\"freshness: {data['data_freshness']}\")
print(f\"phase: {data['tournament_phase']}\")
for m in data['matches'][:3]:
    print(f\"  {m['id']} · {m['status']} · sig={m['signature']}\")
"
```

Expected output (approximate):

```
matches: 11
freshness: fresh
phase: group_stage
  atl-2026-03-31-usa-por · confirmed · sig=v1:confirmed:POR-USA
  atl-2026-06-18-rsa-cze · confirmed · sig=v1:confirmed:CZE-RSA
  atl-2026-06-24-mar-hai · confirmed · sig=v1:confirmed:HAI-MAR
```

- [ ] **Step 8: Run twice to verify idempotence**

```bash
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
md5 -q site/data/matches.json
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
md5 -q site/data/matches.json
```

Expected: identical hashes for both runs (deterministic given fixed `--as-of`).

- [ ] **Step 9: Commit**

```bash
git add backend/refresh.py backend/tests/test_refresh_smoke.py backend/tests/fixtures/odds_response_full.json
git commit -m "feat(backend): refresh CLI with offline and live modes"
```

### Task 1.6.3: Optional live integration smoke test

**Files:**
- Modify: `backend/tests/test_refresh_smoke.py` (append)

- [ ] **Step 1: Add an opt-in live test**

Append to `backend/tests/test_refresh_smoke.py`:

```python
import os
import pytest

from backend.refresh import run_live


@pytest.mark.skipif(
    not os.environ.get("ODDS_API_KEY"),
    reason="set ODDS_API_KEY to run the live integration smoke",
)
def test_live_run_writes_valid_file(tmp_path, knowledge_dir):
    output_path = tmp_path / "matches.json"
    run_live(
        knowledge_dir=knowledge_dir,
        output_path=output_path,
        api_key=os.environ["ODDS_API_KEY"],
    )
    import json
    raw = json.loads(output_path.read_text())
    assert len(raw["matches"]) == 11
    assert raw["data_freshness"] == "fresh"
```

- [ ] **Step 2: Run it once locally with the real key**

```bash
ODDS_API_KEY=<your-key-here> uv run pytest backend/tests/test_refresh_smoke.py::test_live_run_writes_valid_file -v
```

Expected: test passes. (If it fails, that's the first real signal about API shape vs. fixture shape — adjust `normalize_event` if needed.)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_refresh_smoke.py
git commit -m "test(backend): opt-in live Odds API smoke test"
```

---

## Phase 1.7 — Plan 1 wrap-up

### Task 1.7.1: Update README, run final checks, summarize

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README content with current state**

```markdown
# IHG World Cup 2026 Match Intelligence Site

Dynamic HTML site that surfaces IHG's 11 World Cup 2026 ticket matchups
with live probability updates and hospitality intelligence.

See `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`
for the full design.

## Status

| Plan | Subsystem                                 | State       |
|------|-------------------------------------------|-------------|
| 1    | Knowledge files + deterministic backend   | complete    |
| 2    | Briefing + prep advisor agents            | not started |
| 3    | Frontend (sports-tracker style)           | not started |
| 4    | GitHub Actions wiring + deploy            | not started |

## Plan 1 — running locally

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

`brief` and `prep` are `null` for every match in Plan 1; Plan 2 fills them in.
```

- [ ] **Step 2: Run the full check suite one more time**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
assert len(data['matches']) == 11
assert all(m['signature'] for m in data['matches'])
print('Plan 1 acceptance check: PASS')
"
```

Expected: all tests pass, mypy clean, ruff clean, acceptance check prints PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with Plan 1 completion status and usage"
```

- [ ] **Step 4: Tag the milestone**

```bash
git tag -a plan-1-complete -m "Plan 1: knowledge + deterministic backend complete"
git log --oneline | head -20
```

Plan 1 is complete. Hand back to the user with a summary of what runs and what's next (Plan 2: agents).

---

## Acceptance criteria for Plan 1

A reviewer can verify Plan 1 is done by running these checks:

- `uv run pytest` → all tests pass.
- `uv run mypy backend` → no issues.
- `uv run ruff check backend` → no issues.
- `uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z` → writes `site/data/matches.json` with 11 entries, `data_freshness: "fresh"`, signatures populated, brief/prep `null`.
- Running the CLI twice with the same `--as-of` produces an identical file (idempotence).
- `ODDS_API_KEY=<key> uv run pytest backend/tests/test_refresh_smoke.py::test_live_run_writes_valid_file` → passes against the real API.
