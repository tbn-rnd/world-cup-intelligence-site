# Plan A — Backend Shape, Fixtures, Popularity & Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the backend from an 11-match IHG-ticket portfolio to a 104-match public tournament view. Drop tickets/demand_tier/fnb/owner_invitation_note/demand_rationale; add a deterministic three-tier `popularity` object with displayed rationale; tier-gate the briefing and prep agents so they only run on `popular` matches.

**Architecture:**
- A new `knowledge/fixtures_2026.yaml` replaces `knowledge/ticket_inventory.yaml`. `backend/inventory.py` is renamed/repurposed as `backend/fixtures.py` and adapted to the new shape.
- A new `backend/popularity.py` computes `(tier, rationale)` per match using FIFA ranks, host-nation membership, a curated `GLOBAL_DRAW_BRANDS` set, and phase weighting. It runs inside `build_matches_file`.
- `_apply_agents_to_matches` in `backend/refresh.py` skips briefing+prep for any match whose `popularity.tier != "popular"`.
- Briefing/prep prompts drop the IHG ticket inventory knowledge block. Briefing's `cultural_context` is expanded to absorb food traditions; `demand_rationale` is removed. Prep loses `fnb` and `owner_invitation_note`.

**Tech Stack:** Python 3, Pydantic, PyYAML, pytest, mypy, ruff, Anthropic SDK.

**Spec:** `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`.

---

## Pre-flight

- [ ] **Step 0.1: Sync and branch**

```bash
git fetch origin
git checkout main
git pull --rebase origin main
git checkout -b feat/backend-104-match-reframe
```

- [ ] **Step 0.2: Verify clean baseline**

```bash
uv sync
uv run pytest -x -q
uv run mypy backend
uv run ruff check backend
```

Expected: all green.

---

## Task 1: Fixtures schema + loader (TDD)

**Files:**
- Create: `backend/fixtures.py`
- Create: `backend/tests/test_fixtures.py`
- Create: `backend/tests/fixtures/sample_fixtures.yaml`
- (Existing `backend/inventory.py` and `ticket_inventory.yaml` left in place until Task 6 cuts over.)

- [ ] **Step 1.1: Write the failing test (loader contract)**

Create `backend/tests/fixtures/sample_fixtures.yaml`:

```yaml
tournament: "FIFA World Cup 2026"
matches:
  - id: mex-2026-06-11-grpA-mex-kor
    kickoff_local: "2026-06-11T12:00:00-06:00"
    kickoff_utc:   "2026-06-11T18:00:00Z"
    host_city: Mexico City
    venue: Estadio Azteca
    phase: group_stage
    status: confirmed
    group: A
    confirmed_teams: [MEX, KOR]

  - id: nyj-2026-06-30-r32-a1-vs-f2
    kickoff_local: "2026-06-30T17:00:00-04:00"
    kickoff_utc:   "2026-06-30T21:00:00Z"
    host_city: NY/NJ
    venue: MetLife Stadium
    phase: round_of_32
    status: tbd
    bracket_slot: r32_match_75
    decision_date: "2026-06-27"
```

Create `backend/tests/test_fixtures.py`:

```python
from datetime import datetime, UTC
from pathlib import Path

import pytest

from backend.fixtures import FixtureMatch, load_fixtures

FIX = Path(__file__).parent / "fixtures" / "sample_fixtures.yaml"


def test_load_fixtures_returns_sorted_list():
    matches = load_fixtures(FIX)
    assert len(matches) == 2
    assert matches[0].id == "mex-2026-06-11-grpA-mex-kor"
    assert matches[0].kickoff_utc < matches[1].kickoff_utc


def test_confirmed_entry_has_teams_and_group():
    matches = load_fixtures(FIX)
    confirmed = matches[0]
    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_teams == ["MEX", "KOR"]
    assert confirmed.group == "A"
    assert confirmed.bracket_slot is None
    assert confirmed.decision_date is None


def test_tbd_entry_has_slot_and_decision_date():
    matches = load_fixtures(FIX)
    tbd = matches[1]
    assert tbd.status == "tbd"
    assert tbd.bracket_slot == "r32_match_75"
    assert tbd.decision_date == "2026-06-27"
    assert tbd.confirmed_teams == []
    assert tbd.group is None


def test_fixture_match_has_no_tickets_or_demand_tier():
    matches = load_fixtures(FIX)
    m = matches[0]
    # Sanity: FixtureMatch must not carry the dropped fields.
    assert not hasattr(m, "tickets")
    assert not hasattr(m, "demand_tier")


def test_load_fixtures_rejects_unknown_status():
    bad = FIX.parent / "bad_fixtures.yaml"
    bad.write_text(
        "tournament: x\nmatches:\n"
        "  - id: x\n    kickoff_local: '2026-06-11T12:00:00-06:00'\n"
        "    kickoff_utc: '2026-06-11T18:00:00Z'\n"
        "    host_city: Mexico City\n    venue: V\n    phase: group_stage\n"
        "    status: pending\n"
    )
    try:
        with pytest.raises(Exception):
            load_fixtures(bad)
    finally:
        bad.unlink()
```

- [ ] **Step 1.2: Run test to verify failure**

```bash
uv run pytest backend/tests/test_fixtures.py -q
```

Expected: ImportError — `backend.fixtures` doesn't exist yet.

- [ ] **Step 1.3: Implement `backend/fixtures.py`**

```python
"""Loader for knowledge/fixtures_2026.yaml — replaces backend/inventory.py."""

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

HostCity = Literal[
    "Atlanta", "NY/NJ", "Miami", "Mexico City", "Guadalajara", "Monterrey",
    "Toronto", "Vancouver", "Boston", "Dallas", "Houston", "Kansas City",
    "Los Angeles", "Philadelphia", "San Francisco Bay Area", "Seattle",
]


class FixtureMatch(BaseModel):
    id: str
    kickoff_local: str
    kickoff_utc: datetime
    host_city: HostCity
    venue: str
    phase: str
    status: Literal["confirmed", "tbd"]
    confirmed_teams: list[str] = Field(default_factory=list)
    group: str | None = None
    bracket_slot: str | None = None
    decision_date: str | None = None


def load_fixtures(path: Path) -> list[FixtureMatch]:
    raw = yaml.safe_load(path.read_text())
    matches = [FixtureMatch.model_validate(m) for m in raw["matches"]]
    matches.sort(key=lambda m: m.kickoff_utc)
    return matches
```

- [ ] **Step 1.4: Run tests to verify pass**

```bash
uv run pytest backend/tests/test_fixtures.py -q
uv run mypy backend/fixtures.py
uv run ruff check backend/fixtures.py
```

Expected: all green.

- [ ] **Step 1.5: Commit**

```bash
git add backend/fixtures.py backend/tests/test_fixtures.py backend/tests/fixtures/sample_fixtures.yaml
git commit -m "feat(backend): add fixtures.py loader for new all-104-match yaml shape"
```

---

## Task 2: Schema rewrite — drop tickets/demand_tier/fnb/owner_note, add popularity

**Files:**
- Modify: `backend/schema.py`
- Modify: `backend/tests/test_schema.py`

- [ ] **Step 2.1: Write the failing test for new shape**

Open `backend/tests/test_schema.py`. Replace any test that asserts on `tickets`, `demand_tier`, `fnb`, `owner_invitation_note`, or `demand_rationale`. Add:

```python
import pytest
from datetime import datetime, UTC
from backend.schema import (
    Brief, MatchObject, Popularity, Prep, Status, Phase,
    TeamsBlock, ConfirmedTeam, MatchesFile, DataFreshness, TournamentPhase,
)


def _ct(code: str, name: str, rank: int) -> ConfirmedTeam:
    return ConfirmedTeam(code=code, name=name, fifa_rank=rank)


def _base_confirmed_match(**overrides) -> dict:
    defaults = dict(
        id="atl-2026-06-18-rsa-cze",
        kickoff_utc=datetime(2026, 6, 18, 16, 0, tzinfo=UTC),
        kickoff_local="2026-06-18T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.GROUP_STAGE,
        status=Status.CONFIRMED,
        popularity=Popularity(tier="standard", rationale="Group stage; teams outside the top 25."),
        confidence="certain",
        teams=TeamsBlock(confirmed=[_ct("RSA", "South Africa", 60), _ct("CZE", "Czechia", 41)]),
        signature="v1:confirmed:CZE-RSA",
    )
    defaults.update(overrides)
    return defaults


def test_match_object_has_popularity_and_no_tickets():
    m = MatchObject(**_base_confirmed_match())
    assert m.popularity.tier == "standard"
    assert "top 25" in m.popularity.rationale
    assert not hasattr(m, "tickets")
    assert not hasattr(m, "demand_tier")


def test_brief_has_no_demand_rationale_field():
    b = Brief(
        headline="x",
        scenario_summary=None,
        fan_demographics="x",
        traveling_volume_est="x",
        cultural_context="x",
    )
    assert not hasattr(b, "demand_rationale")


def test_prep_has_no_fnb_or_owner_note():
    p = Prep(language=["English"], rate_strategy="hold", logistics=["late dining"])
    assert not hasattr(p, "fnb")
    assert not hasattr(p, "owner_invitation_note")


def test_matches_file_allows_more_than_eleven():
    base = _base_confirmed_match()
    matches = [
        MatchObject(**{**base, "id": f"x-{i}", "signature": f"v1:confirmed:A-B-{i}"})
        for i in range(104)
    ]
    f = MatchesFile(
        generated_at=datetime.now(UTC),
        data_freshness=DataFreshness.FRESH,
        tournament_phase=TournamentPhase.GROUP_STAGE,
        matches=matches,
    )
    assert len(f.matches) == 104


def test_popularity_tier_literal_rejects_unknown():
    with pytest.raises(Exception):
        Popularity(tier="legendary", rationale="x")
```

- [ ] **Step 2.2: Run test to verify failure**

```bash
uv run pytest backend/tests/test_schema.py -q
```

Expected: failures (missing `Popularity`, removed fields still present).

- [ ] **Step 2.3: Rewrite `backend/schema.py`**

Apply these edits to the existing file:

Remove `DemandTier` and `Tickets`:

```python
# DELETE these lines:
DemandTier = Literal["high", "medium", "low", "tbd"]

class Tickets(BaseModel):
    suite: int = 0
    stadium: int = 0
    split_with: str | None = None
    club: str | None = None
```

Add `Popularity`:

```python
PopularityTier = Literal["popular", "moderate", "standard"]


class Popularity(BaseModel):
    tier: PopularityTier
    rationale: str
```

Remove `PrepFnBSuggestion` and `PrepFnB` classes entirely.

Update `Brief` — drop `demand_rationale`:

```python
class Brief(BaseModel):
    headline: str
    scenario_summary: str | None
    fan_demographics: str
    traveling_volume_est: str
    cultural_context: str
```

Update `Prep` — drop `fnb` and `owner_invitation_note`:

```python
class Prep(BaseModel):
    language: list[str]
    rate_strategy: str
    logistics: list[str]
```

Update `MatchObject` — replace `tickets`, `demand_tier` with `popularity`, broaden `host_city`:

```python
class MatchObject(BaseModel):
    id: str
    kickoff_utc: datetime
    kickoff_local: str
    host_city: str  # was Literal[Atlanta, NY/NJ, Miami]; now any FIFA host city.
    venue: str
    phase: Phase
    status: Status
    popularity: Popularity
    confidence: Confidence
    teams: TeamsBlock
    signature: str
    brief: Brief | None = None
    prep: Prep | None = None
    decision_date: str | None = None
    days_to_decision: int | None = None

    # _teams_block_matches_status validator UNCHANGED — keep as-is.
```

Update `MatchesFile` — raise the per-file cap from 11 to 104:

```python
class MatchesFile(BaseModel):
    generated_at: datetime
    data_freshness: DataFreshness
    tournament_phase: TournamentPhase
    matches: Annotated[list[MatchObject], Field(min_length=1, max_length=104)]
```

- [ ] **Step 2.4: Run tests to verify pass**

```bash
uv run pytest backend/tests/test_schema.py -q
```

Expected: all pass. (Other backend tests will still fail — fixed in subsequent tasks.)

- [ ] **Step 2.5: Stage but DO NOT commit yet**

```bash
git add backend/schema.py backend/tests/test_schema.py
```

The schema change alone leaves `backend/refresh.py` and the agent files referring to removed `Tickets` / `demand_tier`. Tasks 3 and 4 below fix those references; we commit all of it together at the end of Task 4 (one logically cohesive change) so no intermediate commit is broken.

---

## Task 3: Popularity computation (TDD)

**Files:**
- Create: `backend/popularity.py`
- Create: `backend/tests/test_popularity.py`

- [ ] **Step 3.1: Write the failing tests**

Create `backend/tests/test_popularity.py`:

```python
from dataclasses import dataclass

from backend.popularity import (
    HOST_NATIONS,
    GLOBAL_DRAW_BRANDS,
    TeamLookup,
    compute_popularity,
)


@dataclass(frozen=True)
class _Team:
    name: str
    fifa_rank: int


def _lookup(*ranks: tuple[str, int]) -> TeamLookup:
    return {code: _Team(name=code, fifa_rank=rank) for code, rank in ranks}


def test_final_is_popular_regardless_of_teams():
    lookup = _lookup(("XYZ", 80), ("ABC", 90))
    p = compute_popularity(
        phase="final", status="confirmed",
        confirmed_team_codes=("XYZ", "ABC"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Final" in p.rationale or "knockout" in p.rationale.lower()


def test_semifinal_is_popular():
    lookup = _lookup(("XYZ", 80), ("ABC", 90))
    p = compute_popularity(
        phase="semi_final", status="confirmed",
        confirmed_team_codes=("XYZ", "ABC"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"


def test_bronze_final_is_popular():
    lookup = _lookup(("XYZ", 80), ("ABC", 90))
    p = compute_popularity(
        phase="bronze_final", status="confirmed",
        confirmed_team_codes=("XYZ", "ABC"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"


def test_top10_team_in_group_stage_is_popular():
    lookup = _lookup(("BRA", 1), ("MAR", 14))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("BRA", "MAR"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Brazil" in p.rationale or "BRA" in p.rationale or "FIFA" in p.rationale


def test_host_nation_in_group_stage_is_popular():
    lookup = _lookup(("USA", 20), ("PAR", 50))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("USA", "PAR"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"
    assert "Host-nation" in p.rationale or "host" in p.rationale.lower()


def test_global_draw_brand_in_group_stage_is_popular():
    lookup = _lookup(("ENG", 5), ("PAN", 60))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("ENG", "PAN"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "popular"


def test_r32_default_is_moderate():
    lookup = _lookup(("RSA", 60), ("CZE", 41))
    p = compute_popularity(
        phase="round_of_32", status="confirmed",
        confirmed_team_codes=("RSA", "CZE"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_r16_default_is_moderate():
    lookup = _lookup(("RSA", 60), ("CZE", 41))
    p = compute_popularity(
        phase="round_of_16", status="confirmed",
        confirmed_team_codes=("RSA", "CZE"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_qf_default_is_moderate():
    lookup = _lookup(("RSA", 60), ("CZE", 41))
    p = compute_popularity(
        phase="quarter_final", status="confirmed",
        confirmed_team_codes=("RSA", "CZE"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_group_stage_top25_no_brand_is_moderate():
    lookup = _lookup(("AUS", 24), ("HAI", 75))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("AUS", "HAI"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "moderate"


def test_group_stage_no_top25_no_brand_is_standard():
    lookup = _lookup(("HAI", 75), ("UZB", 68))
    p = compute_popularity(
        phase="group_stage", status="confirmed",
        confirmed_team_codes=("HAI", "UZB"),
        feeder_distributions=None, team_lookup=lookup,
    )
    assert p.tier == "standard"
    assert "top 25" in p.rationale


def test_tbd_r32_phase_only_when_no_feeder_leader_above_threshold():
    lookup = _lookup(("BRA", 1), ("GER", 8))
    # Feeder distributions present but leader is below 60% threshold.
    fd = [
        {"label": "Group A winner", "leader_code": "BRA", "leader_prob": 0.45},
        {"label": "Group F runner-up", "leader_code": "GER", "leader_prob": 0.30},
    ]
    p = compute_popularity(
        phase="round_of_32", status="tbd",
        confirmed_team_codes=None,
        feeder_distributions=fd, team_lookup=lookup,
    )
    assert p.tier == "moderate"  # phase-only; team triggers don't fire


def test_tbd_r32_uses_leader_when_above_threshold_top10():
    lookup = _lookup(("BRA", 1), ("XYZ", 30))
    fd = [
        {"label": "Group A winner", "leader_code": "BRA", "leader_prob": 0.72},
        {"label": "Group F runner-up", "leader_code": "XYZ", "leader_prob": 0.20},
    ]
    p = compute_popularity(
        phase="round_of_32", status="tbd",
        confirmed_team_codes=None,
        feeder_distributions=fd, team_lookup=lookup,
    )
    assert p.tier == "popular"  # BRA top-10 fires once leader confidence ≥ 0.60


def test_host_nations_constant():
    assert HOST_NATIONS == frozenset({"USA", "MEX", "CAN"})


def test_global_draw_brands_constant():
    assert GLOBAL_DRAW_BRANDS == frozenset(
        {"BRA", "ARG", "FRA", "ENG", "GER", "ESP", "POR", "NED", "BEL"}
    )
```

- [ ] **Step 3.2: Run tests to verify failure**

```bash
uv run pytest backend/tests/test_popularity.py -q
```

Expected: ImportError — `backend.popularity` doesn't exist.

- [ ] **Step 3.3: Implement `backend/popularity.py`**

```python
"""Deterministic match popularity — tier and short rationale string.

Tiers: "popular" / "moderate" / "standard". Triggered by phase, FIFA top-10
membership, host-nation membership, or membership in a curated set of
global-TV-draw brands. TBD knockout slots use phase-only popularity until
a feeder distribution's leader passes a 60% threshold.
"""

from __future__ import annotations

from typing import Literal, Mapping, Protocol, TypedDict

from backend.schema import Popularity

PopularityTier = Literal["popular", "moderate", "standard"]


class TeamInfo(Protocol):
    name: str
    fifa_rank: int


TeamLookup = Mapping[str, TeamInfo]


HOST_NATIONS: frozenset[str] = frozenset({"USA", "MEX", "CAN"})
GLOBAL_DRAW_BRANDS: frozenset[str] = frozenset(
    {"BRA", "ARG", "FRA", "ENG", "GER", "ESP", "POR", "NED", "BEL"}
)
FEEDER_LEADER_THRESHOLD: float = 0.60

_TOP10_MAX_RANK: int = 10
_TOP25_MAX_RANK: int = 25


class FeederLeader(TypedDict):
    label: str
    leader_code: str
    leader_prob: float


_PHASE_LABEL: dict[str, str] = {
    "final": "Final",
    "semi_final": "Semi-final",
    "bronze_final": "Bronze final",
    "quarter_final": "Quarter-final",
    "round_of_16": "Round of 16",
    "round_of_32": "Round of 32",
    "group_stage": "Group stage",
    "friendly": "Friendly",
}


def _phase_inherent_popular(phase: str) -> bool:
    return phase in {"final", "semi_final", "bronze_final"}


def _phase_inherent_moderate(phase: str) -> bool:
    return phase in {"quarter_final", "round_of_16", "round_of_32"}


def _team_rank(code: str, lookup: TeamLookup) -> int | None:
    team = lookup.get(code)
    return team.fifa_rank if team else None


def _team_name(code: str, lookup: TeamLookup) -> str:
    team = lookup.get(code)
    return team.name if team else code


def _top10_codes(codes: tuple[str, ...], lookup: TeamLookup) -> list[str]:
    out: list[str] = []
    for c in codes:
        rank = _team_rank(c, lookup)
        if rank is not None and rank <= _TOP10_MAX_RANK:
            out.append(c)
    return out


def _top25_codes(codes: tuple[str, ...], lookup: TeamLookup) -> list[str]:
    out: list[str] = []
    for c in codes:
        rank = _team_rank(c, lookup)
        if rank is not None and rank <= _TOP25_MAX_RANK:
            out.append(c)
    return out


def _effective_team_codes(
    *,
    status: str,
    confirmed_team_codes: tuple[str, ...] | None,
    feeder_distributions: list[FeederLeader] | None,
) -> tuple[str, ...]:
    if status == "confirmed" and confirmed_team_codes:
        return tuple(confirmed_team_codes)
    if status == "tbd" and feeder_distributions:
        leaders: list[str] = []
        for fd in feeder_distributions:
            if fd["leader_prob"] >= FEEDER_LEADER_THRESHOLD:
                leaders.append(fd["leader_code"])
        return tuple(leaders)
    return ()


def compute_popularity(
    *,
    phase: str,
    status: str,
    confirmed_team_codes: tuple[str, ...] | None,
    feeder_distributions: list[FeederLeader] | None,
    team_lookup: TeamLookup,
) -> Popularity:
    codes = _effective_team_codes(
        status=status,
        confirmed_team_codes=confirmed_team_codes,
        feeder_distributions=feeder_distributions,
    )
    code_set = set(codes)

    if _phase_inherent_popular(phase):
        return Popularity(
            tier="popular",
            rationale=f"{_PHASE_LABEL[phase]} — knockout intensity.",
        )

    top10 = _top10_codes(codes, team_lookup)
    if top10:
        names = ", ".join(
            f"{_team_name(c, team_lookup)} (FIFA #{_team_rank(c, team_lookup)})"
            for c in top10
        )
        return Popularity(tier="popular", rationale=f"{names} draws a global audience.")

    if phase == "group_stage":
        host_present = code_set & HOST_NATIONS
        if host_present:
            host = sorted(host_present)[0]
            return Popularity(
                tier="popular",
                rationale=f"Host-nation match ({_team_name(host, team_lookup)}).",
            )

        brand_present = code_set & GLOBAL_DRAW_BRANDS
        if brand_present:
            brand = sorted(brand_present)[0]
            return Popularity(
                tier="popular",
                rationale=f"{_team_name(brand, team_lookup)} is a global TV draw.",
            )

    if _phase_inherent_moderate(phase):
        return Popularity(
            tier="moderate",
            rationale=f"{_PHASE_LABEL[phase]} — knockout round.",
        )

    if phase == "group_stage":
        top25 = _top25_codes(codes, team_lookup)
        if top25:
            return Popularity(
                tier="moderate",
                rationale="Group stage; at least one team inside the top 25 FIFA.",
            )
        return Popularity(
            tier="standard",
            rationale="Group stage; teams outside the top 25 FIFA.",
        )

    return Popularity(tier="standard", rationale=f"{_PHASE_LABEL.get(phase, phase)}.")
```

- [ ] **Step 3.4: Run tests to verify pass**

```bash
uv run pytest backend/tests/test_popularity.py -q
uv run mypy backend/popularity.py
uv run ruff check backend/popularity.py
```

Expected: all green.

- [ ] **Step 3.5: Commit**

```bash
git add backend/popularity.py backend/tests/test_popularity.py
git commit -m "feat(backend): deterministic three-tier popularity with phase + FIFA + host + brand signals"
```

---

## Task 4: Wire popularity into refresh + drop tickets/demand_tier from inventory pipeline

**Files:**
- Modify: `backend/refresh.py`
- Modify: `backend/agents/briefing.py`
- Modify: `backend/agents/prep.py`

- [ ] **Step 4.1: Switch refresh.py from inventory to fixtures and inject popularity**

In `backend/refresh.py`:

Replace the `from backend.inventory import ...` line with:

```python
from backend.fixtures import FixtureMatch, load_fixtures
```

Replace the `from backend.schema import (...)` block — delete `Tickets`, add `Popularity`:

```python
from backend.schema import (
    ConfirmedTeam,
    DataFreshness,
    FeederDistribution,
    FeederTeam,
    MatchesFile,
    MatchObject,
    Phase,
    Popularity,
    Status,
    TbdScenario,
    TeamRef,
    TeamsBlock,
    TournamentPhase,
)
```

Add at top:

```python
from backend.popularity import FEEDER_LEADER_THRESHOLD, FeederLeader, compute_popularity
```

Rewrite `_build_confirmed_match` to take `FixtureMatch` and a `KnowledgeBase`, and to populate `popularity`:

```python
def _build_confirmed_match(
    inv: FixtureMatch,
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
    popularity = compute_popularity(
        phase=inv.phase,
        status="confirmed",
        confirmed_team_codes=tuple(inv.confirmed_teams),
        feeder_distributions=None,
        team_lookup=kb.teams,
    )
    return MatchObject(
        id=inv.id,
        kickoff_utc=inv.kickoff_utc,
        kickoff_local=inv.kickoff_local,
        host_city=inv.host_city,
        venue=inv.venue,
        phase=Phase(inv.phase),
        status=Status.CONFIRMED,
        popularity=popularity,
        confidence="certain",
        teams=TeamsBlock(confirmed=confirmed, tbd_scenarios=None),
        signature=sig,
        brief=None,
        prep=None,
        decision_date=None,
        days_to_decision=None,
    )
```

Rewrite `_build_tbd_match` similarly. Replace the `tickets=Tickets(**inv.tickets.model_dump())` and `demand_tier="tbd"` lines. Compute `popularity` using feeder leaders. The relevant changes:

In the body of `_build_tbd_match`, after `feeder_distributions_or_none = ...`, add:

```python
    feeder_leaders_for_pop: list[FeederLeader] = []
    if feeder_distributions:
        for fd in feeder_distributions:
            if fd.teams:
                top = fd.teams[0]
                feeder_leaders_for_pop.append(
                    {
                        "label": fd.label,
                        "leader_code": top.code,
                        "leader_prob": top.probability,
                    }
                )
    popularity = compute_popularity(
        phase=inv.phase,
        status="tbd",
        confirmed_team_codes=None,
        feeder_distributions=feeder_leaders_for_pop or None,
        team_lookup=kb.teams,
    )
```

Replace the trailing `return MatchObject(...)` so it has `popularity=popularity` instead of `tickets=...` and `demand_tier="tbd"`.

Update the call sites: replace `load_inventory(knowledge_dir / "ticket_inventory.yaml")` with `load_fixtures(knowledge_dir / "fixtures_2026.yaml")` in `run_offline` and `run_live`.

Replace any `InventoryMatch` parameter types with `FixtureMatch`. Replace `inventory: list[InventoryMatch]` with `inventory: list[FixtureMatch]` in `build_matches_file`.

- [ ] **Step 4.2: Update agent user-message builders (drop demand_tier and tickets)**

In `backend/agents/briefing.py`, modify `build_match_user_message`:

Replace:

```python
    lines.append(f"DEMAND TIER (deterministic): {match.demand_tier}")
```

with:

```python
    lines.append(f"POPULARITY (deterministic): {match.popularity.tier}")
    lines.append(f"POPULARITY RATIONALE: {match.popularity.rationale}")
```

Delete the `# NOTE: ticket allocation ...` comment block (lines 26-28).

In `backend/agents/prep.py`, modify `build_match_user_message`:

Replace:

```python
    lines.append(f"DEMAND TIER (deterministic): {match.demand_tier}")
```

with:

```python
    lines.append(f"POPULARITY (deterministic): {match.popularity.tier}")
    lines.append(f"POPULARITY RATIONALE: {match.popularity.rationale}")
```

Delete the `tix = match.tickets` block and the `TICKET ALLOCATION` line entirely (lines 22-30 in the current file).

Also delete the `Demand rationale` line from the BRIEF echo block (current line 51):

```python
    lines.append(f"  Demand rationale: {brief.demand_rationale}")  # DELETE
```

- [ ] **Step 4.3: Add the agent tier gate**

In `backend/refresh.py`, modify `_apply_agents_to_matches`. Right after the `for i, m in enumerate(new_matches):` line and before the prior-signature reuse check, add:

```python
        if m.popularity.tier != "popular":
            continue
```

This causes non-popular matches to keep `brief=None` and `prep=None`. The signature reuse and agent call branches below are unchanged.

- [ ] **Step 4.4: Run targeted tests**

```bash
uv run mypy backend
uv run ruff check backend
```

Expected: clean. The smoke and integration tests will be updated in Tasks 5 and 7; failures there are expected at this point.

- [ ] **Step 4.5: Commit the combined schema + popularity + wiring change**

```bash
git add backend/refresh.py backend/agents/briefing.py backend/agents/prep.py
git commit -m "feat(backend): replace demand_tier+tickets with popularity; wire into refresh; tier-gate brief/prep"
```

This commit folds in the schema changes from Task 2 (staged earlier but not committed) plus the popularity module from Task 3 (already committed independently) plus the wiring fixes in Task 4. After this commit, `mypy backend` and `ruff check backend` should be clean. Verify:

```bash
uv run mypy backend
uv run ruff check backend
```

If anything is red, fix in place and amend the commit.

---

## Task 5: Update agent system prompts (drop fnb, drop owner note, drop demand block, expand cultural_context)

**Files:**
- Modify: `backend/agents/prompts.py`
- Modify: `backend/signature.py` (bump `prompt_version`)
- Modify: `backend/tests/test_briefing_agent.py`
- Modify: `backend/tests/test_prep_agent.py`

- [ ] **Step 5.1: Rewrite the system prompts**

Open `backend/agents/prompts.py`. Replace the two `_BRIEFING_SYSTEM_PROMPT` and `_PREP_SYSTEM_PROMPT` strings with:

```python
_BRIEFING_SYSTEM_PROMPT = """You are the World Cup 2026 briefing agent. Your job is to write a single match's intelligence brief for IHG hotel property General Managers.

**Defensibility rules (non-negotiable):**

1. **Quantitative claims must come from the curated team profiles below.** Diaspora population numbers, FIFA ranks, language requirements. If the curated profile doesn't say it, don't claim it as a number.
2. **Qualitative color may use your training knowledge** — recent form, fan culture nuance, traveling temperament, regional food traditions, religious observances, fan rituals. Prefer the curated knowledge; never contradict it.
3. **Be honest about uncertainty.** For TBD knockout slots, frame the brief in scenario-aware language ("if Mexico advances as expected from Group A...") rather than overclaiming a specific matchup.
4. **Match the audience.** This is for hotel GMs preparing their property for traveling fans. Keep it concise and operationally useful; skip generic football commentary.

**Output:** a single JSON object matching the requested schema, with NO surrounding prose, NO code fences. Just the JSON. The fields:

- `headline`: one short sentence (under 25 words) capturing what this match means for hotels in the host market.
- `scenario_summary`: ONE paragraph for TBD matches summarizing the scenario landscape ("the most likely matchups all involve Mexico..."). Use JSON `null` for confirmed matches.
- `fan_demographics`: 2-4 sentences about who's traveling and from where. Ground in curated diaspora data.
- `traveling_volume_est`: 1-2 sentences with a defensible volume estimate ("light," "moderate," "heavy," with reasoning).
- `cultural_context`: 3-5 sentences as cultural background — food traditions, religious/dietary observances, key fan rituals. This is BACKGROUND for awareness, NOT a list of instructions for the property to execute.

Total brief should be approximately 200-300 words across all fields combined.
"""

_PREP_SYSTEM_PROMPT = """You are the World Cup 2026 prep advisor agent. Your job is to turn a match's intelligence brief into concrete hospitality preparation recommendations for the hosting property's GM.

**Defensibility rules:**

1. **Quantitative claims come from the curated team profiles.** Diaspora numbers, language needs.
2. **Be operational, not aspirational.** Recommendations should be things a GM can execute in 4-8 weeks of lead time.
3. **No food and beverage suggestions.** Food traditions are covered as cultural background in the brief; do not output any F&B suggestions, requirements, or operational notes here.

**Output:** a single JSON object matching the requested schema, with NO surrounding prose, NO code fences. The fields:

- `language`: array of strings — concierge and front-desk language requirements.
- `rate_strategy`: one sentence pricing posture for this match.
- `logistics`: array of strings — transport, late-dining, group-booking notes.

Total prep should be approximately 150-250 words across all fields combined.
"""
```

Then update both `build_briefing_prefix` and `build_prep_prefix` to drop the inventory knowledge block. Replace the bodies of both functions with:

```python
def build_briefing_prefix(*, knowledge_dir: Path) -> list[TextBlockParam]:
    teams = _read_text(knowledge_dir / "teams.yaml")
    cities = _read_text(knowledge_dir / "cities.yaml")
    blocks: list[TextBlockParam] = [
        {"type": "text", "text": _BRIEFING_SYSTEM_PROMPT},
        _build_knowledge_block("CURATED TEAM PROFILES (teams.yaml)", teams),
        _build_knowledge_block("HOST CITY CONTEXT (cities.yaml)", cities),
    ]
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return blocks


def build_prep_prefix(*, knowledge_dir: Path) -> list[TextBlockParam]:
    teams = _read_text(knowledge_dir / "teams.yaml")
    cities = _read_text(knowledge_dir / "cities.yaml")
    blocks: list[TextBlockParam] = [
        {"type": "text", "text": _PREP_SYSTEM_PROMPT},
        _build_knowledge_block("CURATED TEAM PROFILES (teams.yaml)", teams),
        _build_knowledge_block("HOST CITY CONTEXT (cities.yaml)", cities),
    ]
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return blocks
```

- [ ] **Step 5.2: Bump signature prompt_version**

In `backend/signature.py`, change the default:

```python
    prompt_version: str = "v2",  # was "v1"
```

This forces every match's brief/prep to regenerate on the next refresh — the prompts changed materially.

- [ ] **Step 5.3: Update briefing and prep agent tests**

Open `backend/tests/test_briefing_agent.py`. Remove any assertion on `demand_rationale`. Update fixture inputs so `MatchObject` constructors use `popularity=Popularity(tier="popular", rationale="...")` instead of `demand_tier="..."` and have no `tickets=...`. Add an assertion that the generated brief has a `cultural_context` field and no `demand_rationale` attribute.

Open `backend/tests/test_prep_agent.py`. Remove all `fnb` and `owner_invitation_note` references. Update fixture matches to use `popularity` and no `tickets`. Add an assertion that the generated prep has no `fnb` and no `owner_invitation_note` attributes.

Concrete fixture replacement — every occurrence of:

```python
    tickets=Tickets(suite=10, stadium=0, split_with=None, club=None),
    demand_tier="high",
```

becomes:

```python
    popularity=Popularity(tier="popular", rationale="Top-10 FIFA matchup."),
```

Remove any `from backend.schema import Tickets` and `DemandTier` imports; add `Popularity`.

- [ ] **Step 5.4: Run agent tests**

```bash
uv run pytest backend/tests/test_briefing_agent.py backend/tests/test_prep_agent.py -q
uv run mypy backend
uv run ruff check backend
```

Expected: all green.

- [ ] **Step 5.5: Commit**

```bash
git add backend/agents/prompts.py backend/signature.py backend/tests/test_briefing_agent.py backend/tests/test_prep_agent.py
git commit -m "feat(agents): expand cultural_context for food traditions; drop fnb, owner note, demand_rationale; drop inventory knowledge block; bump prompt_version"
```

---

## Task 6: Write `knowledge/fixtures_2026.yaml` (all 104 matches)

**Files:**
- Create: `knowledge/fixtures_2026.yaml`
- Delete: `knowledge/ticket_inventory.yaml`
- Delete: `backend/inventory.py`
- Modify: `backend/tests/test_writer.py`
- Modify: `backend/tests/test_refresh_smoke.py`

> **Source of truth:** FIFA's official 2026 World Cup match schedule (post Final Draw, 2025-12-05). Cross-verify against Wikipedia's "2026 FIFA World Cup" page before committing. All 104 matches: 72 group-stage + 16 R32 + 8 R16 + 4 QF + 2 SF + 1 bronze + 1 final = 104.

- [ ] **Step 6.1: Author `knowledge/fixtures_2026.yaml`**

Create the file with this structure for every match. Header + first three group-stage matches shown as the pattern; transcribe the remaining 101 from the FIFA schedule using the same shape.

```yaml
# All 104 matches of the FIFA World Cup 2026.
# Source: FIFA published 2026 match schedule (post Final Draw 2025-12-05).
# Cross-verified against Wikipedia "2026 FIFA World Cup" on the date below.

tournament: "FIFA World Cup 2026"

matches:
  # ---------- GROUP A ----------
  - id: mex-2026-06-11-grpA-mex-kor
    kickoff_local: "2026-06-11T12:00:00-06:00"
    kickoff_utc:   "2026-06-11T18:00:00Z"
    host_city: Mexico City
    venue: Estadio Azteca
    phase: group_stage
    status: confirmed
    group: A
    confirmed_teams: [MEX, KOR]

  - id: gua-2026-06-12-grpA-rsa-cze
    kickoff_local: "2026-06-12T18:00:00-06:00"
    kickoff_utc:   "2026-06-13T00:00:00Z"
    host_city: Guadalajara
    venue: Estadio Akron
    phase: group_stage
    status: confirmed
    group: A
    confirmed_teams: [RSA, CZE]

  # ... transcribe the remaining group-stage matches (one block per matchday per group) ...

  # ---------- ROUND OF 32 ----------
  - id: nyj-2026-06-30-r32-a1-vs-f2
    kickoff_local: "2026-06-30T17:00:00-04:00"
    kickoff_utc:   "2026-06-30T21:00:00Z"
    host_city: NY/NJ
    venue: MetLife Stadium
    phase: round_of_32
    status: tbd
    bracket_slot: r32_match_75
    decision_date: "2026-06-27"

  # ... transcribe all 16 R32, 8 R16, 4 QF, 2 SF, bronze, final ...
```

ID convention: `<city-prefix>-YYYY-MM-DD-<phase-or-group>-<teamA>-<teamB>` for confirmed; `<city-prefix>-YYYY-MM-DD-<slot>` for TBD knockout entries.

> **Quality gate before committing this file:** open it in an editor and verify:
> - Total `id:` count = 104. Run `grep -c '^  - id:' knowledge/fixtures_2026.yaml`.
> - Per-phase counts: 72 group_stage, 16 round_of_32, 8 round_of_16, 4 quarter_final, 2 semi_final, 1 bronze_final, 1 final.
> - Every `kickoff_local` ISO offset matches its host city's local time zone.
> - Every confirmed `confirmed_teams` pair matches the group's published draw (cross-check `knowledge/bracket_2026.yaml`).

- [ ] **Step 6.2: Delete the old inventory file and loader**

```bash
git rm knowledge/ticket_inventory.yaml
git rm backend/inventory.py
```

- [ ] **Step 6.3: Update writer and smoke tests**

Open `backend/tests/test_writer.py`. Find every test fixture that constructs a `MatchObject`. Replace each `tickets=Tickets(...)` + `demand_tier="..."` with `popularity=Popularity(tier=..., rationale=...)`. Drop `Tickets` import.

Open `backend/tests/test_refresh_smoke.py`. Replace any `load_inventory` import with `load_fixtures`. Replace `ticket_inventory.yaml` path with `fixtures_2026.yaml`. Update fixture construction the same way.

If a test referenced `inv.tickets` or `inv.demand_tier` directly, those references just delete (they don't exist on `FixtureMatch`).

- [ ] **Step 6.4: Run the full backend suite**

```bash
uv run pytest -q
uv run mypy backend
uv run ruff check backend
```

Expected: all green. If a test fails on a popularity tier that the test was hard-coding (e.g., "expected demand_tier=high"), update the assertion to the new shape.

- [ ] **Step 6.5: Generate matches.json offline and spot-check**

```bash
rm -f site/data/matches.json
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
```

Inspect `site/data/matches.json`:
- `matches` array length is 104.
- No entry has a `tickets` or `demand_tier` key.
- Every entry has a `popularity` object with `tier` and `rationale`.
- Spot-check that ARG, BRA, FRA, ENG, GER, ESP, POR, NED, BEL group-stage matches show `tier: "popular"`.
- Spot-check that knockout entries (R32 / R16 / QF) show at least `tier: "moderate"`.

- [ ] **Step 6.6: Commit**

```bash
git add knowledge/fixtures_2026.yaml backend/tests/test_writer.py backend/tests/test_refresh_smoke.py site/data/matches.json
git commit -m "feat(data): all 104 matches in fixtures_2026.yaml; drop ticket_inventory + inventory.py"
```

---

## Task 7: Refresh integration test — agent tier-gate behavior

**Files:**
- Modify: `backend/tests/test_refresh_agents_integration.py`

- [ ] **Step 7.1: Add tier-gate assertions**

Open `backend/tests/test_refresh_agents_integration.py`. Add a test that verifies:
- A match whose popularity tier is `moderate` or `standard` results in `brief is None` and `prep is None`.
- The mocked `AgentClient.call_structured` is never invoked for those matches.
- For a `popular` match, the agent client is invoked twice (briefing + prep) and `brief` / `prep` populate.

Concrete assertion shape (adapt to existing test scaffolding):

```python
def test_only_popular_matches_invoke_agents(monkeypatch, tmp_path):
    # ... existing setup that produces a list of MatchObjects ...
    # Make sure inventory contains one popular and one standard match.

    calls: list[str] = []

    class StubClient:
        def call_structured(self, *, system_prefix, user_message, response_model):
            calls.append(response_model.__name__)
            # Return a minimal valid instance of the response model.
            ...

    # Run the pipeline.
    # Assert: calls contains exactly two entries (Brief, Prep) for the popular match,
    # and the standard match has brief=None, prep=None.
    assert calls.count("Brief") == 1
    assert calls.count("Prep") == 1
```

Remove any existing assertions about `fnb`, `owner_invitation_note`, or `demand_rationale` from the file.

- [ ] **Step 7.2: Run the test**

```bash
uv run pytest backend/tests/test_refresh_agents_integration.py -q
```

Expected: pass.

- [ ] **Step 7.3: Run full suite + lint + typecheck**

```bash
uv run pytest -q
uv run mypy backend
uv run ruff check backend
```

Expected: all green.

- [ ] **Step 7.4: Commit**

```bash
git add backend/tests/test_refresh_agents_integration.py
git commit -m "test(agents): assert tier gate skips non-popular matches"
```

---

## Task 8: Plan A self-verification

- [ ] **Step 8.1: Re-run full backend gate**

```bash
uv run pytest -q
uv run mypy backend
uv run ruff check backend
```

Expected: all green.

- [ ] **Step 8.2: Confirm artifact shape**

```bash
python -c "import json; f=json.load(open('site/data/matches.json')); print('matches:', len(f['matches']));
print('popular:', sum(1 for m in f['matches'] if m['popularity']['tier']=='popular'));
print('moderate:', sum(1 for m in f['matches'] if m['popularity']['tier']=='moderate'));
print('standard:', sum(1 for m in f['matches'] if m['popularity']['tier']=='standard'));
print('has tickets field:', 'tickets' in f['matches'][0]);
print('has demand_tier field:', 'demand_tier' in f['matches'][0]);"
```

Expected: 104 total, `has tickets field: False`, `has demand_tier field: False`, popular > 0.

- [ ] **Step 8.3: Push branch and open PR**

```bash
git push -u origin feat/backend-104-match-reframe
gh pr create --title "Backend: 104-match expansion, popularity, agent tier gate" --body "$(cat <<'EOF'
## Summary
- Replace `ticket_inventory.yaml` with `fixtures_2026.yaml` (all 104 matches)
- Drop `tickets`, `demand_tier`, `fnb`, `owner_invitation_note`, `demand_rationale`
- Add deterministic `popularity` object (`popular` / `moderate` / `standard` + rationale)
- Tier-gate briefing + prep agents to popular matches only
- Expand briefing `cultural_context` to absorb food traditions as background

## Test plan
- [ ] `uv run pytest -q` green
- [ ] `uv run mypy backend` clean
- [ ] `uv run ruff check backend` clean
- [ ] Offline refresh produces 104-match `matches.json` with no tickets/demand_tier
- [ ] Spot-check a few popular / moderate / standard tiers against expectations

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Plan A complete. **Plan B (frontend) consumes the JSON shape produced by this plan and should not start until this is merged or at minimum on `main`.**