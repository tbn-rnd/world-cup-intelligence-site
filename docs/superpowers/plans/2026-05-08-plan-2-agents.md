# IHG World Cup Site — Plan 2: Briefing + Prep Advisor Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the `null` placeholders in `matches.json` for `brief` and `prep` with real LLM-generated content. Build two focused agents — a **briefing agent** that writes the narrative intelligence brief and a **prep advisor agent** that turns that brief into property hospitality recommendations — both targeting Claude Sonnet 4.6 with prompt caching, both wired into the existing signature-gated regeneration pipeline. End state: every match in `matches.json` has populated `brief` (headline + named sub-fields) and `prep` (F&B suggestions with rationales, language, rate strategy, logistics, owner invitation note).

**Architecture:** Two-agent pipeline. The briefing agent runs first per match; the prep advisor runs second consuming the brief plus the team profiles. Both agents use the Anthropic SDK with explicit prompt caching on the static prefix (system prompt + curated knowledge files + inventory). Variable suffix is per-match state (feeder distributions, confirmed teams, demand tier, etc., from Plan 1.6's data model). Output is structured JSON validated by Pydantic; one retry on schema failure; on second failure, keep the previous brief/prep rather than writing garbage.

**Tech Stack:** Anthropic Python SDK (`anthropic>=0.40,<1`), targeting model `claude-sonnet-4-6`. No new infra dependencies beyond that.

**Reference spec:** [`docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`](../specs/2026-05-08-world-cup-intelligence-site-design.md), Section 5.

**Predecessor:** Plan 1.6, tagged `plan-1-6-complete`.

---

## File structure produced by this plan

```
backend/
  agents/
    __init__.py
    client.py            Anthropic SDK wrapper with prompt caching helpers
    briefing.py          Briefing agent — Brief output
    prep.py              Prep advisor agent — Prep output
    prompts.py           System prompts and prompt-construction helpers
  refresh.py             Modified — call agents for matches whose signature changed
  tests/
    test_briefing_agent.py
    test_prep_agent.py
    test_agents_client.py
    test_refresh_agents_integration.py
    fixtures/
      mock_brief_response.json
      mock_prep_response.json

docs/
  superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md   No changes — spec already covers Plan 2

pyproject.toml         Add anthropic>=0.40,<1 to dependencies
```

---

## Phase 2.1 — Anthropic client wrapper

Build a thin wrapper that handles auth, caching, validation, retry, and the keep-previous fallback. Both agents share this.

### Task 2.1.1: `backend/agents/client.py` — SDK wrapper

**Files:**
- Modify: `pyproject.toml` (add `anthropic` dep)
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/client.py`
- Create: `backend/tests/test_agents_client.py`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`'s `[project].dependencies`, add `"anthropic>=0.40,<1"`. Then:

```bash
uv sync
```

Verify the package installed:

```bash
uv run python -c "import anthropic; print(anthropic.__version__)"
```

- [ ] **Step 2: Create empty `__init__.py`**

```bash
touch backend/agents/__init__.py
```

- [ ] **Step 3: Write the failing tests**

`backend/tests/test_agents_client.py`:

```python
import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from backend.agents.client import AgentClient, AgentSchemaError


class _StubModel(BaseModel):
    headline: str
    detail: str


def _mock_anthropic_response(text: str) -> Any:
    """Build a fake Anthropic Messages API response carrying a text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_call_returns_validated_pydantic_model() -> None:
    raw = _mock_anthropic_response(json.dumps({"headline": "test", "detail": "ok"}))
    sdk = MagicMock()
    sdk.messages.create.return_value = raw

    client = AgentClient(api_key="k", sdk=sdk)
    result = client.call_structured(
        system_prefix=[{"type": "text", "text": "system", "cache_control": {"type": "ephemeral"}}],
        user_message="hello",
        response_model=_StubModel,
    )
    assert result.headline == "test"
    assert result.detail == "ok"


def test_call_retries_once_on_schema_failure_then_succeeds() -> None:
    bad = _mock_anthropic_response("not valid json at all")
    good = _mock_anthropic_response(json.dumps({"headline": "test", "detail": "ok"}))
    sdk = MagicMock()
    sdk.messages.create.side_effect = [bad, good]

    client = AgentClient(api_key="k", sdk=sdk)
    result = client.call_structured(
        system_prefix=[{"type": "text", "text": "system"}],
        user_message="hello",
        response_model=_StubModel,
    )
    assert result.headline == "test"
    assert sdk.messages.create.call_count == 2


def test_call_raises_after_two_failures() -> None:
    bad = _mock_anthropic_response("still not json")
    sdk = MagicMock()
    sdk.messages.create.return_value = bad

    client = AgentClient(api_key="k", sdk=sdk)
    with pytest.raises(AgentSchemaError):
        client.call_structured(
            system_prefix=[{"type": "text", "text": "system"}],
            user_message="hello",
            response_model=_StubModel,
        )
    assert sdk.messages.create.call_count == 2  # one retry, then raise


def test_extract_json_handles_fenced_code_blocks() -> None:
    """Models sometimes wrap JSON in ```json ... ``` fences. Strip them."""
    from backend.agents.client import _extract_json_text

    fenced = "Here is the JSON:\n```json\n{\"headline\": \"x\", \"detail\": \"y\"}\n```\n"
    assert json.loads(_extract_json_text(fenced)) == {"headline": "x", "detail": "y"}

    plain = '{"headline": "x", "detail": "y"}'
    assert json.loads(_extract_json_text(plain)) == {"headline": "x", "detail": "y"}
```

- [ ] **Step 4: Run tests (expect ImportError)**

```bash
uv run pytest backend/tests/test_agents_client.py -v
```

- [ ] **Step 5: Implement `backend/agents/client.py`**

```python
"""Anthropic SDK wrapper with prompt caching, schema validation, and retry semantics.

Used by both the briefing and prep advisor agents to share auth handling,
caching, structured-output validation, and error recovery in one place.

Output protocol: the agent prompt instructs the model to emit a single JSON
object matching the requested Pydantic schema. We strip optional ``` fences,
validate, retry once on failure, and raise AgentSchemaError after two
failures so the caller can keep the previous brief/prep instead of writing
garbage.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048


class AgentSchemaError(RuntimeError):
    """Raised after the model fails twice to emit valid JSON for the requested schema."""


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(text: str) -> str:
    """Extract a JSON payload from a model response, stripping optional code fences."""
    text = text.strip()
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


class AgentClient:
    """Thin wrapper over the Anthropic Messages API for structured outputs."""

    def __init__(
        self,
        api_key: str,
        *,
        sdk: Any | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self._sdk = sdk if sdk is not None else Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def call_structured(
        self,
        *,
        system_prefix: list[dict[str, Any]],
        user_message: str,
        response_model: type[T],
        max_attempts: int = 2,
    ) -> T:
        """Call the model with a cacheable system prefix and validate the JSON output.

        Args:
            system_prefix: list of system content blocks. The caller is responsible
                for setting `cache_control: {"type": "ephemeral"}` on the blocks
                that should be cached. The wrapper passes the list through unmodified.
            user_message: plain-text variable suffix (per-match state).
            response_model: Pydantic class the response must validate against.
            max_attempts: total tries (including retries). Defaults to 2.
        """
        last_error: Exception | None = None
        for _ in range(max_attempts):
            response = self._sdk.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prefix,
                messages=[{"role": "user", "content": user_message}],
            )
            text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            try:
                payload = json.loads(_extract_json_text(text))
                return response_model.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                continue

        raise AgentSchemaError(
            f"agent failed to produce valid {response_model.__name__} JSON after {max_attempts} attempts: {last_error}"
        )
```

- [ ] **Step 6: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_agents_client.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass. Mypy may complain about `MagicMock` typing in tests — those test functions need the `Any` type annotation if mypy strict is unhappy. The `sdk: Any | None = None` parameter annotation in `AgentClient.__init__` is intentional (the SDK object is opaque).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock backend/agents/__init__.py backend/agents/client.py backend/tests/test_agents_client.py
git commit -m "feat(agents): Anthropic SDK wrapper with prompt caching and retry"
```

---

## Phase 2.2 — Prompt construction helpers

Both agents share the same cached prefix structure: a system prompt that explains the agent's role and defensibility rules, plus the curated knowledge files. Build the helper that constructs this prefix once.

### Task 2.2.1: `backend/agents/prompts.py` — system prompts and prefix builder

**Files:**
- Create: `backend/agents/prompts.py`
- Create: `backend/tests/test_agents_prompts.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_agents_prompts.py`:

```python
from pathlib import Path

from backend.agents.prompts import (
    build_briefing_prefix,
    build_prep_prefix,
)


def test_briefing_prefix_includes_cache_control(knowledge_dir: Path) -> None:
    prefix = build_briefing_prefix(knowledge_dir=knowledge_dir)
    # Last block should carry cache_control=ephemeral so the prefix is cached
    assert prefix[-1].get("cache_control") == {"type": "ephemeral"}


def test_briefing_prefix_contains_curated_knowledge(knowledge_dir: Path) -> None:
    prefix = build_briefing_prefix(knowledge_dir=knowledge_dir)
    combined = " ".join(block.get("text", "") for block in prefix)
    # System role keyword
    assert "briefing" in combined.lower()
    # Curated team data should be in the prefix
    assert "MEX" in combined or "Mexico" in combined
    # Defensibility rule
    assert "curated" in combined.lower()


def test_prep_prefix_contains_role_and_knowledge(knowledge_dir: Path) -> None:
    prefix = build_prep_prefix(knowledge_dir=knowledge_dir)
    combined = " ".join(block.get("text", "") for block in prefix)
    assert "prep" in combined.lower() or "hospitality" in combined.lower()
    assert "halal" in combined.lower()  # mentioned somewhere in either prompt or knowledge


def test_prefix_blocks_are_well_typed(knowledge_dir: Path) -> None:
    """Each block has type='text' and a string 'text' field; cache_control optional."""
    for builder in (build_briefing_prefix, build_prep_prefix):
        prefix = builder(knowledge_dir=knowledge_dir)
        assert len(prefix) >= 2  # system prompt + at least one knowledge block
        for block in prefix:
            assert block["type"] == "text"
            assert isinstance(block["text"], str)
            assert block["text"]  # non-empty
```

- [ ] **Step 2: Run tests (expect ImportError)**

```bash
uv run pytest backend/tests/test_agents_prompts.py -v
```

- [ ] **Step 3: Implement `backend/agents/prompts.py`**

```python
"""System prompts and prefix-construction helpers for the briefing and prep agents.

The prefix is the cacheable portion of each prompt — system prompt + curated
knowledge files. The variable suffix (per-match state) is constructed by each
agent's `run()` function and passed in as the user message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


_BRIEFING_SYSTEM_PROMPT = """You are the IHG World Cup 2026 briefing agent. Your job is to write a single match's intelligence brief for hotel owners and IHG senior leadership.

**Defensibility rules (non-negotiable):**

1. **Quantitative claims must come from the curated team profiles below.** Diaspora population numbers, FIFA ranks, demand tier, language requirements. If the curated profile doesn't say it, don't claim it as a number.
2. **Qualitative color may use your training knowledge** — recent form, fan culture nuance, traveling temperament, regional dish traditions. Prefer the curated knowledge; never contradict it.
3. **Be honest about uncertainty.** For TBD knockout slots, frame the brief in scenario-aware language ("if Mexico advances as expected from Group A...") rather than overclaiming a specific matchup.
4. **Match the audience.** This is for hospitality leaders making invitation decisions and GMs preparing properties. Keep it concise, action-oriented, and skip generic football commentary.

**Output:** a single JSON object matching the requested schema, with NO surrounding prose, NO code fences. Just the JSON. The fields:

- `headline`: one short sentence (under 25 words) capturing what this match means for IHG.
- `scenario_summary`: ONE paragraph for TBD matches summarizing the scenario landscape ("the most likely matchups all involve Mexico..."). NULL for confirmed matches.
- `fan_demographics`: 2-4 sentences about who's traveling and from where. Ground in curated diaspora data.
- `traveling_volume_est`: 1-2 sentences with a defensible volume estimate ("light," "moderate," "heavy," with reasoning).
- `cultural_context`: 2-3 sentences about cultural and dietary considerations relevant to hospitality.
- `demand_rationale`: 2 sentences justifying the demand tier (HIGH/medium/low) for IHG owners reading this.

Total brief should be approximately 200-300 words across all fields combined.
"""

_PREP_SYSTEM_PROMPT = """You are the IHG World Cup 2026 prep advisor agent. Your job is to turn a match's intelligence brief into concrete hospitality preparation recommendations for the hosting property's GM.

**Defensibility rules:**

1. **Ground every F&B suggestion in who is traveling.** If the brief says Moroccan diaspora travels heavily from France-influenced regions, your tagine suggestion should reference that connection in the rationale.
2. **Quantitative claims come from the curated team profiles.** Diaspora numbers, language needs, dietary requirements.
3. **Be operational, not aspirational.** Recommendations should be things a GM can execute in 4-8 weeks of lead time. No "build a new restaurant"; yes "stock these 3 spirits and add this prep station."
4. **Owner invitation note** is one sentence the IHG strategy team can paste verbatim into an invitation email — make it persuasive and specific.

**Output:** a single JSON object matching the requested schema, with NO surrounding prose, NO code fences. The fields:

- `fnb`:
  - `suggestions`: array of 2-4 items, each `{dish, meal_period, rationale}`. The rationale must tie the dish to traveling fan demographics or cultural context — not generic.
  - `requirements`: array of strings — non-negotiable operational requirements (e.g., "Halal certification on shared protein lines"). Empty array if none.
  - `operational_notes`: array of strings — practical kitchen/service adjustments (extending dining hours, sourcing notes).
- `language`: array of strings — concierge and front-desk language requirements.
- `rate_strategy`: one sentence pricing posture for this match.
- `logistics`: array of strings — transport, late-dining, group-booking notes.
- `owner_invitation_note`: one sentence (under 30 words) the strategy team can paste verbatim.

Total prep should be approximately 250-400 words across all fields combined.
"""


def _read_text(path: Path) -> str:
    return path.read_text()


def _build_knowledge_block(label: str, body: str) -> dict[str, Any]:
    return {
        "type": "text",
        "text": f"=== {label} ===\n{body}",
    }


def build_briefing_prefix(*, knowledge_dir: Path) -> list[dict[str, Any]]:
    """Construct the cacheable system prefix for the briefing agent."""
    teams = _read_text(knowledge_dir / "teams.yaml")
    cities = _read_text(knowledge_dir / "cities.yaml")
    inventory = _read_text(knowledge_dir / "ticket_inventory.yaml")

    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": _BRIEFING_SYSTEM_PROMPT},
        _build_knowledge_block("CURATED TEAM PROFILES (teams.yaml)", teams),
        _build_knowledge_block("HOST CITY CONTEXT (cities.yaml)", cities),
        _build_knowledge_block("IHG TICKET INVENTORY (ticket_inventory.yaml)", inventory),
    ]
    # Cache control on the LAST block — Anthropic's caching uses prefix matching, so
    # marking the last block as cacheable causes the entire prefix up to that point
    # to be cached.
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def build_prep_prefix(*, knowledge_dir: Path) -> list[dict[str, Any]]:
    """Construct the cacheable system prefix for the prep advisor agent."""
    teams = _read_text(knowledge_dir / "teams.yaml")
    cities = _read_text(knowledge_dir / "cities.yaml")
    inventory = _read_text(knowledge_dir / "ticket_inventory.yaml")

    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": _PREP_SYSTEM_PROMPT},
        _build_knowledge_block("CURATED TEAM PROFILES (teams.yaml)", teams),
        _build_knowledge_block("HOST CITY CONTEXT (cities.yaml)", cities),
        _build_knowledge_block("IHG TICKET INVENTORY (ticket_inventory.yaml)", inventory),
    ]
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks
```

- [ ] **Step 4: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_agents_prompts.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/prompts.py backend/tests/test_agents_prompts.py
git commit -m "feat(agents): system prompts and cacheable prefix builders"
```

---

## Phase 2.3 — Briefing agent

### Task 2.3.1: `backend/agents/briefing.py` — generate `Brief` JSON for one match

**Files:**
- Create: `backend/agents/briefing.py`
- Create: `backend/tests/test_briefing_agent.py`
- Create: `backend/tests/fixtures/mock_brief_response.json`

- [ ] **Step 1: Create the mock response fixture**

`backend/tests/fixtures/mock_brief_response.json`:

```json
{
  "headline": "Mexico-Netherlands at MetLife is the highest-leverage R32 matchup in IHG's portfolio.",
  "scenario_summary": "Across the top scenarios for this slot, Mexico is the heavy favorite to win Group A and the most likely opponent rotates among Netherlands, Japan, and Sweden as Group F runner-up.",
  "fan_demographics": "Mexican diaspora fans dominate any Mexico fixture, with 37M+ Mexican-Americans concentrated in California, Texas, and Arizona. Substantial NJ-area concentration also drives strong local turnout. Netherlands brings a smaller but premium-segment European following.",
  "traveling_volume_est": "Heavy. Mexican fan base alone supports a near-sellout; NJ-area Dutch and Japanese expat communities add incremental high-spend demand.",
  "cultural_context": "Spanish-speaking front-of-house is essential. Late-dining culture shifts dinner peak past 21:00. No dietary restrictions for either fanbase.",
  "demand_rationale": "Tier: HIGH. Combination of Mexico's diaspora gravity and the Champion Club Plus seat tier supports premium pricing. Owners with Mexican-American or NY-area properties should be prioritized."
}
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_briefing_agent.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.agents.briefing import build_match_user_message, run_briefing
from backend.agents.client import AgentClient
from backend.schema import (
    ConfirmedTeam,
    FeederDistribution,
    FeederTeam,
    MatchObject,
    Phase,
    Status,
    TbdScenario,
    TeamRef,
    TeamsBlock,
    Tickets,
)
from datetime import datetime, timezone


def _make_confirmed_match() -> MatchObject:
    return MatchObject(
        id="atl-2026-03-31-usa-por",
        kickoff_utc=datetime(2026, 3, 31, 16, 0, tzinfo=timezone.utc),
        kickoff_local="2026-03-31T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.FRIENDLY,
        status=Status.CONFIRMED,
        tickets=Tickets(suite=10, split_with="Etherio"),
        demand_tier="high",
        confidence="certain",
        teams=TeamsBlock(
            confirmed=[
                ConfirmedTeam(code="USA", name="United States", fifa_rank=16),
                ConfirmedTeam(code="POR", name="Portugal", fifa_rank=6),
            ],
        ),
        signature="v1:confirmed:POR-USA",
    )


def _make_tbd_match() -> MatchObject:
    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code="MEX", name="Mexico"),
            team_b=TeamRef(code=code, name=name),
            probability=p,
            delta_pp=0.0,
            rationale="r",
        )
        for i, (code, name, p) in enumerate(
            [("NED", "Netherlands", 0.11), ("JPN", "Japan", 0.10), ("SWE", "Sweden", 0.10)],
            start=1,
        )
    ]
    feeders = [
        FeederDistribution(
            label="Group A winner",
            teams=[
                FeederTeam(code="MEX", name="Mexico", probability=0.64),
                FeederTeam(code="CZE", name="Czech Republic", probability=0.14),
            ],
        ),
        FeederDistribution(
            label="Group F runner-up",
            teams=[
                FeederTeam(code="NED", name="Netherlands", probability=0.32),
                FeederTeam(code="JPN", name="Japan", probability=0.30),
            ],
        ),
    ]
    return MatchObject(
        id="njy-2026-06-30-r32-a1-vs-f2",
        kickoff_utc=datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc),
        kickoff_local="2026-06-30T17:00:00-04:00",
        host_city="NY/NJ",
        venue="MetLife Stadium",
        phase=Phase.ROUND_OF_32,
        status=Status.TBD,
        tickets=Tickets(stadium=6, club="Champion Club Plus"),
        demand_tier="tbd",
        confidence="medium",
        teams=TeamsBlock(
            confirmed=None,
            tbd_scenarios=scenarios,
            feeder_distributions=feeders,
        ),
        signature="v1:tbd:...",
        decision_date="2026-06-27",
        days_to_decision=3,
    )


def test_build_user_message_for_confirmed_match_includes_team_codes() -> None:
    match = _make_confirmed_match()
    msg = build_match_user_message(match)
    assert "USA" in msg
    assert "POR" in msg
    assert "Atlanta" in msg
    assert "Mercedes-Benz Stadium" in msg


def test_build_user_message_for_tbd_match_includes_feeder_distributions() -> None:
    match = _make_tbd_match()
    msg = build_match_user_message(match)
    assert "Group A winner" in msg
    assert "Group F runner-up" in msg
    assert "Mexico" in msg
    # Confidence and decision date are part of the brief context
    assert "medium" in msg.lower()
    assert "2026-06-27" in msg


def test_run_briefing_returns_validated_brief(
    knowledge_dir: Path,
    fixtures_dir: Path,
) -> None:
    raw_text = (fixtures_dir / "mock_brief_response.json").read_text()
    block = MagicMock()
    block.type = "text"
    block.text = raw_text
    response = MagicMock()
    response.content = [block]
    sdk = MagicMock()
    sdk.messages.create.return_value = response

    agent_client = AgentClient(api_key="k", sdk=sdk)
    match = _make_tbd_match()
    brief = run_briefing(match=match, client=agent_client, knowledge_dir=knowledge_dir)
    assert brief.headline.startswith("Mexico-Netherlands")
    assert brief.scenario_summary is not None
    assert "Mexican diaspora" in brief.fan_demographics
```

- [ ] **Step 3: Run tests (expect ImportError)**

```bash
uv run pytest backend/tests/test_briefing_agent.py -v
```

- [ ] **Step 4: Implement `backend/agents/briefing.py`**

```python
"""Briefing agent — produces a Brief JSON for one match."""

from __future__ import annotations

from pathlib import Path

from backend.agents.client import AgentClient
from backend.agents.prompts import build_briefing_prefix
from backend.schema import Brief, MatchObject, Status


def build_match_user_message(match: MatchObject) -> str:
    """Construct the variable per-match suffix for the briefing prompt."""
    lines: list[str] = []
    lines.append(f"MATCH ID: {match.id}")
    lines.append(f"KICKOFF: {match.kickoff_local} (local) / {match.kickoff_utc} (UTC)")
    lines.append(f"HOST CITY: {match.host_city}")
    lines.append(f"VENUE: {match.venue}")
    lines.append(f"PHASE: {match.phase.value}")
    lines.append(f"STATUS: {match.status.value}")
    lines.append(f"DEMAND TIER (deterministic): {match.demand_tier}")
    lines.append(f"CONFIDENCE: {match.confidence}")
    if match.decision_date:
        lines.append(f"DECISION DATE: {match.decision_date} (in {match.days_to_decision} days)")

    tix = match.tickets
    parts = []
    if tix.suite:
        parts.append(f"{tix.suite} suite")
    if tix.stadium:
        parts.append(f"{tix.stadium} stadium")
    if tix.club:
        parts.append(tix.club)
    if tix.split_with:
        parts.append(f"split with {tix.split_with}")
    lines.append(f"TICKET ALLOCATION: {', '.join(parts) if parts else 'none recorded'}")

    if match.status == Status.CONFIRMED and match.teams.confirmed:
        lines.append("")
        lines.append("CONFIRMED TEAMS:")
        for t in match.teams.confirmed:
            lines.append(f"  - {t.code} ({t.name}, FIFA rank {t.fifa_rank})")

    if match.status == Status.TBD and match.teams.feeder_distributions:
        lines.append("")
        lines.append("PER-FEEDER TEAM DISTRIBUTIONS (primary scenario signal):")
        for fd in match.teams.feeder_distributions:
            lines.append(f"  {fd.label}:")
            for team in fd.teams[:6]:  # limit for prompt size
                lines.append(f"    - {team.code} ({team.name}): {team.probability:.1%}")

    if match.status == Status.TBD and match.teams.tbd_scenarios:
        lines.append("")
        lines.append("TOP-3 CROSS-PRODUCT MATCHUPS (supporting detail):")
        for s in match.teams.tbd_scenarios:
            lines.append(
                f"  rank{s.rank}: {s.team_a.code} vs {s.team_b.code}  p={s.probability:.3f}  Δ={s.delta_pp:+.2f}pp"
            )

    lines.append("")
    lines.append("Produce the brief now as a single JSON object matching the Brief schema. No prose, no fences.")
    return "\n".join(lines)


def run_briefing(
    *,
    match: MatchObject,
    client: AgentClient,
    knowledge_dir: Path,
) -> Brief:
    prefix = build_briefing_prefix(knowledge_dir=knowledge_dir)
    user_message = build_match_user_message(match)
    return client.call_structured(
        system_prefix=prefix,
        user_message=user_message,
        response_model=Brief,
    )
```

- [ ] **Step 5: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_briefing_agent.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/briefing.py backend/tests/test_briefing_agent.py backend/tests/fixtures/mock_brief_response.json
git commit -m "feat(agents): briefing agent producing Brief JSON for one match"
```

---

## Phase 2.4 — Prep advisor agent

### Task 2.4.1: `backend/agents/prep.py` — generate `Prep` JSON for one match

**Files:**
- Create: `backend/agents/prep.py`
- Create: `backend/tests/test_prep_agent.py`
- Create: `backend/tests/fixtures/mock_prep_response.json`

- [ ] **Step 1: Create the mock response fixture**

`backend/tests/fixtures/mock_prep_response.json`:

```json
{
  "fnb": {
    "suggestions": [
      {
        "dish": "Regional taco bar (al pastor, barbacoa, lengua)",
        "meal_period": "lunch and late dinner",
        "rationale": "Mexican diaspora travels heavily from California and Texas; signals regional authenticity over generic Tex-Mex."
      },
      {
        "dish": "Mezcal/tequila flight pairings",
        "meal_period": "evening / suite reception",
        "rationale": "Premium spirits program lifts suite spend for the affluent Mexican-American segment."
      },
      {
        "dish": "Stroopwafel and Dutch coffee station",
        "meal_period": "breakfast / matchday",
        "rationale": "Easy nod to the Netherlands fanbase if they fill the runner-up slot; cheap to execute, high cultural-fit signal."
      }
    ],
    "requirements": [],
    "operational_notes": [
      "Extend room service to 01:00 to accommodate late Mexican dining culture.",
      "Pre-stock 200+ bottles of premium tequila and mezcal across F&B outlets."
    ]
  },
  "language": ["Spanish-speaking front desk and concierge essential", "Dutch a plus, not required"],
  "rate_strategy": "Aggressive premium suite pricing; this is a sellout-grade demand profile.",
  "logistics": [
    "Coordinate car service from Manhattan for suite guests.",
    "Group-booking allowance for multi-generational Mexican families (5-8 rooms per booking)."
  ],
  "owner_invitation_note": "Mexico-Netherlands is the highest-leverage R32 in our portfolio — Mexican diaspora gravity plus premium NJ demand. Prioritize owners with West Coast or NY-area properties."
}
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_prep_agent.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.agents.prep import build_match_user_message, run_prep
from backend.agents.client import AgentClient
from backend.schema import (
    Brief,
    MatchObject,
    Phase,
    Status,
    TeamsBlock,
    Tickets,
    ConfirmedTeam,
)
from datetime import datetime, timezone


def _make_brief() -> Brief:
    return Brief(
        headline="USA-Portugal at MBS — high diaspora demand",
        scenario_summary=None,
        fan_demographics="USA fans dominate ATL home games. Portugal brings ~1.5M-strong diaspora primarily from MA/RI/NJ.",
        traveling_volume_est="Heavy.",
        cultural_context="Portuguese-speaking concierge essential.",
        demand_rationale="HIGH. Ronaldo-era marquee fixture.",
    )


def _make_match() -> MatchObject:
    return MatchObject(
        id="atl-2026-03-31-usa-por",
        kickoff_utc=datetime(2026, 3, 31, 16, 0, tzinfo=timezone.utc),
        kickoff_local="2026-03-31T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.FRIENDLY,
        status=Status.CONFIRMED,
        tickets=Tickets(suite=10, split_with="Etherio"),
        demand_tier="high",
        confidence="certain",
        teams=TeamsBlock(
            confirmed=[
                ConfirmedTeam(code="USA", name="United States", fifa_rank=16),
                ConfirmedTeam(code="POR", name="Portugal", fifa_rank=6),
            ],
        ),
        signature="v1:confirmed:POR-USA",
    )


def test_build_user_message_includes_brief_and_match() -> None:
    msg = build_match_user_message(match=_make_match(), brief=_make_brief())
    assert "USA-Portugal" in msg or "USA" in msg
    assert "Portuguese-speaking" in msg  # brief content propagates
    assert "Atlanta" in msg
    assert "high" in msg.lower()  # demand tier


def test_run_prep_returns_validated_prep(
    knowledge_dir: Path,
    fixtures_dir: Path,
) -> None:
    raw_text = (fixtures_dir / "mock_prep_response.json").read_text()
    block = MagicMock()
    block.type = "text"
    block.text = raw_text
    response = MagicMock()
    response.content = [block]
    sdk = MagicMock()
    sdk.messages.create.return_value = response

    agent_client = AgentClient(api_key="k", sdk=sdk)
    prep = run_prep(
        match=_make_match(),
        brief=_make_brief(),
        client=agent_client,
        knowledge_dir=knowledge_dir,
    )
    assert len(prep.fnb.suggestions) >= 2
    assert "Spanish" in " ".join(prep.language)
    assert prep.owner_invitation_note  # populated
```

- [ ] **Step 3: Run tests (expect ImportError)**

```bash
uv run pytest backend/tests/test_prep_agent.py -v
```

- [ ] **Step 4: Implement `backend/agents/prep.py`**

```python
"""Prep advisor agent — produces a Prep JSON for one match given the briefing output."""

from __future__ import annotations

from pathlib import Path

from backend.agents.client import AgentClient
from backend.agents.prompts import build_prep_prefix
from backend.schema import Brief, MatchObject, Prep, Status


def build_match_user_message(*, match: MatchObject, brief: Brief) -> str:
    """Construct the variable per-match suffix for the prep advisor prompt."""
    lines: list[str] = []
    lines.append(f"MATCH ID: {match.id}")
    lines.append(f"HOST CITY: {match.host_city}")
    lines.append(f"VENUE: {match.venue}")
    lines.append(f"PHASE: {match.phase.value}")
    lines.append(f"DEMAND TIER (deterministic): {match.demand_tier}")
    lines.append(f"CONFIDENCE: {match.confidence}")

    tix = match.tickets
    parts = []
    if tix.suite:
        parts.append(f"{tix.suite} suite")
    if tix.stadium:
        parts.append(f"{tix.stadium} stadium")
    if tix.club:
        parts.append(tix.club)
    lines.append(f"TICKET ALLOCATION: {', '.join(parts) if parts else 'none recorded'}")

    lines.append("")
    if match.status == Status.CONFIRMED and match.teams.confirmed:
        lines.append("CONFIRMED TEAMS:")
        for t in match.teams.confirmed:
            lines.append(f"  - {t.code} ({t.name})")
    elif match.teams.feeder_distributions:
        lines.append("PER-FEEDER TEAM DISTRIBUTIONS (which teams could play this match):")
        for fd in match.teams.feeder_distributions:
            top_codes = [t.code for t in fd.teams[:5]]
            lines.append(f"  {fd.label}: {', '.join(top_codes)}")

    lines.append("")
    lines.append("BRIEF (just produced by the briefing agent — use this for context):")
    lines.append(f"  Headline: {brief.headline}")
    if brief.scenario_summary:
        lines.append(f"  Scenario summary: {brief.scenario_summary}")
    lines.append(f"  Fan demographics: {brief.fan_demographics}")
    lines.append(f"  Traveling volume: {brief.traveling_volume_est}")
    lines.append(f"  Cultural context: {brief.cultural_context}")
    lines.append(f"  Demand rationale: {brief.demand_rationale}")

    lines.append("")
    lines.append("Produce the prep recommendations now as a single JSON object matching the Prep schema. No prose, no fences.")
    return "\n".join(lines)


def run_prep(
    *,
    match: MatchObject,
    brief: Brief,
    client: AgentClient,
    knowledge_dir: Path,
) -> Prep:
    prefix = build_prep_prefix(knowledge_dir=knowledge_dir)
    user_message = build_match_user_message(match=match, brief=brief)
    return client.call_structured(
        system_prefix=prefix,
        user_message=user_message,
        response_model=Prep,
    )
```

- [ ] **Step 5: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_prep_agent.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/prep.py backend/tests/test_prep_agent.py backend/tests/fixtures/mock_prep_response.json
git commit -m "feat(agents): prep advisor agent producing Prep JSON from brief output"
```

---

## Phase 2.5 — Wire agents into `refresh.py`

The signature-gated regeneration logic from Plan 1's design lives here. For each match:
- If signature matches the previous file's signature AND brief/prep are populated → keep them
- Otherwise → call briefing agent, then prep advisor agent, store both

Failures keep the previous brief/prep rather than writing nulls.

### Task 2.5.1: Integrate agents into `build_matches_file`

**Files:**
- Modify: `backend/refresh.py`
- Create: `backend/tests/test_refresh_agents_integration.py`

- [ ] **Step 1: Add the integration test**

`backend/tests/test_refresh_agents_integration.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.refresh import run_offline


def _agent_response_for(content: dict) -> object:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(content)
    response = MagicMock()
    response.content = [block]
    return response


def _make_mock_sdk(brief_response: dict, prep_response: dict) -> MagicMock:
    """Mock SDK that alternates brief / prep responses across calls."""
    sdk = MagicMock()
    # Each match calls briefing then prep, so alternate the responses.
    responses = []
    for _ in range(20):  # enough for 11 matches × 2 agents = 22, plus headroom
        responses.append(_agent_response_for(brief_response))
        responses.append(_agent_response_for(prep_response))
    sdk.messages.create.side_effect = responses
    return sdk


def test_run_offline_populates_brief_and_prep_for_every_match(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    brief_payload = json.loads((fixtures_dir / "mock_brief_response.json").read_text())
    prep_payload = json.loads((fixtures_dir / "mock_prep_response.json").read_text())
    sdk = _make_mock_sdk(brief_payload, prep_payload)

    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk,
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        assert m["brief"] is not None, f"{m['id']} brief missing"
        assert m["prep"] is not None, f"{m['id']} prep missing"
        assert m["brief"]["headline"]
        assert m["prep"]["owner_invitation_note"]


def test_run_offline_skips_agent_calls_when_signature_unchanged(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Second run with same as-of should not call agents — previous brief/prep reused."""
    brief_payload = json.loads((fixtures_dir / "mock_brief_response.json").read_text())
    prep_payload = json.loads((fixtures_dir / "mock_prep_response.json").read_text())

    output_path = tmp_path / "matches.json"

    # First run — agents populate everything
    sdk1 = _make_mock_sdk(brief_payload, prep_payload)
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk1,
    )
    first_call_count = sdk1.messages.create.call_count
    assert first_call_count > 0

    # Second run, same as-of, same fixture — signatures match, no agent calls
    sdk2 = MagicMock()
    sdk2.messages.create.side_effect = AssertionError("agents should not be called")
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key="test-key",
        anthropic_sdk=sdk2,
    )
    assert sdk2.messages.create.call_count == 0


def test_run_offline_continues_when_agents_disabled(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """If anthropic_api_key is None and no SDK provided, brief/prep stay null and refresh succeeds."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
        anthropic_api_key=None,
        anthropic_sdk=None,
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        assert m["brief"] is None
        assert m["prep"] is None
```

- [ ] **Step 2: Run tests (expect failures since refresh doesn't accept anthropic_api_key/sdk yet)**

```bash
uv run pytest backend/tests/test_refresh_agents_integration.py -v
```

- [ ] **Step 3: Update `backend/refresh.py`**

Three changes:

A. **Add anthropic_api_key + anthropic_sdk parameters to `run_offline` and `run_live`.** Both default to `None` so existing callers work. When `None`, agents are skipped (brief/prep stay null).

B. **Add a function `_apply_agents_to_matches(...)`** that takes the new MatchesFile, the previous MatchesFile, the knowledge_dir, the AgentClient, and:
- For each match in the new file, look up the matching match in the previous file by id.
- If previous match exists AND signatures match AND previous brief/prep are populated → reuse previous brief/prep.
- Otherwise → call `run_briefing()` then `run_prep()`. Catch `AgentSchemaError`: if previous match's brief/prep exists, reuse them; otherwise leave brief/prep as `None` and log.

C. **Call `_apply_agents_to_matches(...)` from `build_matches_file`** if the AgentClient is provided. Otherwise leave brief/prep at None as before.

Concrete implementation outline (you will need to study the existing refresh.py to find exact insertion points):

```python
# Near the top with other imports:
from backend.agents.briefing import run_briefing
from backend.agents.client import AgentClient, AgentSchemaError
from backend.agents.prep import run_prep


def _apply_agents_to_matches(
    new_matches: list[MatchObject],
    previous: MatchesFile | None,
    knowledge_dir: Path,
    client: AgentClient,
) -> list[MatchObject]:
    previous_by_id: dict[str, MatchObject] = {}
    if previous is not None:
        previous_by_id = {m.id: m for m in previous.matches}

    for i, m in enumerate(new_matches):
        prior = previous_by_id.get(m.id)
        if (
            prior is not None
            and prior.signature == m.signature
            and prior.brief is not None
            and prior.prep is not None
        ):
            new_matches[i] = m.model_copy(update={"brief": prior.brief, "prep": prior.prep})
            continue

        try:
            brief = run_briefing(match=m, client=client, knowledge_dir=knowledge_dir)
            prep = run_prep(match=m, brief=brief, client=client, knowledge_dir=knowledge_dir)
            new_matches[i] = m.model_copy(update={"brief": brief, "prep": prep})
        except AgentSchemaError:
            # Keep previous brief/prep if available; otherwise leave as None.
            if prior is not None and prior.brief is not None and prior.prep is not None:
                new_matches[i] = m.model_copy(update={"brief": prior.brief, "prep": prior.prep})

    return new_matches
```

In `build_matches_file`, after constructing the matches list (and BEFORE constructing `MatchesFile(...)`), if a client is provided, apply the agents:

```python
def build_matches_file(
    inventory: list[InventoryMatch],
    kb: KnowledgeBase,
    bracket: Bracket,
    odds_events: list[NormalizedEvent],
    as_of: datetime,
    previous: MatchesFile | None,
    *,
    agent_client: AgentClient | None = None,
    knowledge_dir: Path | None = None,
) -> MatchesFile:
    # ... existing logic that builds `matches` list ...

    if agent_client is not None and knowledge_dir is not None:
        matches = _apply_agents_to_matches(matches, previous, knowledge_dir, agent_client)

    return MatchesFile(...)
```

In `run_offline`, accept the new args and instantiate the client:

```python
def run_offline(
    *,
    knowledge_dir: Path,
    odds_fixture_path: Path,
    output_path: Path,
    as_of: str,
    anthropic_api_key: str | None = None,
    anthropic_sdk: Any | None = None,
) -> None:
    # ... existing setup ...

    agent_client: AgentClient | None = None
    if anthropic_api_key is not None or anthropic_sdk is not None:
        agent_client = AgentClient(
            api_key=anthropic_api_key or "stub",
            sdk=anthropic_sdk,
        )

    file = build_matches_file(
        inventory, kb, bracket, odds_events, as_of_dt, previous,
        agent_client=agent_client,
        knowledge_dir=knowledge_dir,
    )
    write_matches_file(file, output_path)
```

Same change to `run_live`.

D. **Update `main()`** to read `ANTHROPIC_API_KEY` from env and pass it to `run_live` (and optionally `run_offline`):

```python
    if args.offline:
        # ... existing offline path ...
        run_offline(
            knowledge_dir=args.knowledge_dir,
            odds_fixture_path=fixture,
            output_path=args.output,
            as_of=as_of,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
    else:
        # ... existing live path ...
        run_live(
            knowledge_dir=args.knowledge_dir,
            output_path=args.output,
            api_key=api_key,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
```

Then in `main()`, the existing `api_key = os.environ.get("ODDS_API_KEY")` is unchanged. Add a similar pattern for `ANTHROPIC_API_KEY` (don't fail if missing — agents are optional in this plan; the CLI just runs without them when the key is absent).

- [ ] **Step 4: Run tests**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
```

All must pass. Note: existing `test_brief_and_prep_are_null_in_plan_1` smoke test will likely need to be repurposed or kept as-is — it asserts brief/prep are null when `anthropic_api_key=None`, which is still the default behavior. So it should still pass without changes.

- [ ] **Step 5: Run end-to-end offline with mock agents**

This step is just `uv run pytest backend/tests/test_refresh_agents_integration.py -v` — already verifies the integration works.

- [ ] **Step 6: Idempotence with agents enabled**

Add to the integration test (or run inline):

```bash
ANTHROPIC_API_KEY=stub uv run pytest backend/tests/test_refresh_agents_integration.py::test_run_offline_skips_agent_calls_when_signature_unchanged -v
```

This verifies the second run does NOT call agents (because signatures match).

- [ ] **Step 7: Commit**

```bash
git add backend/refresh.py backend/tests/test_refresh_agents_integration.py
git commit -m "feat(backend): wire briefing + prep agents into refresh pipeline"
```

---

## Phase 2.6 — Live integration smoke test (opt-in)

### Task 2.6.1: Add an opt-in live agent test

**Files:**
- Modify: `backend/tests/test_refresh_agents_integration.py`

- [ ] **Step 1: Append the live test**

```python
import os

import pytest


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="set ANTHROPIC_API_KEY to run the live agent integration smoke",
)
def test_live_briefing_agent_returns_valid_brief(
    knowledge_dir: Path,
) -> None:
    """Hits the real Anthropic API to confirm the briefing agent's prompt produces valid output."""
    from datetime import datetime, timezone

    from backend.agents.briefing import run_briefing
    from backend.agents.client import AgentClient
    from backend.schema import (
        ConfirmedTeam,
        MatchObject,
        Phase,
        Status,
        TeamsBlock,
        Tickets,
    )

    match = MatchObject(
        id="atl-2026-03-31-usa-por",
        kickoff_utc=datetime(2026, 3, 31, 16, 0, tzinfo=timezone.utc),
        kickoff_local="2026-03-31T12:00:00-04:00",
        host_city="Atlanta",
        venue="Mercedes-Benz Stadium",
        phase=Phase.FRIENDLY,
        status=Status.CONFIRMED,
        tickets=Tickets(suite=10, split_with="Etherio"),
        demand_tier="high",
        confidence="certain",
        teams=TeamsBlock(
            confirmed=[
                ConfirmedTeam(code="USA", name="United States", fifa_rank=16),
                ConfirmedTeam(code="POR", name="Portugal", fifa_rank=6),
            ],
        ),
        signature="v1:confirmed:POR-USA",
    )

    client = AgentClient(api_key=os.environ["ANTHROPIC_API_KEY"])
    brief = run_briefing(match=match, client=client, knowledge_dir=knowledge_dir)

    assert brief.headline
    assert "USA" in brief.fan_demographics or "Portugal" in brief.fan_demographics or "diaspora" in brief.fan_demographics.lower()
```

- [ ] **Step 2: Run locally with the real key (the user will do this once)**

```bash
ANTHROPIC_API_KEY=<key> uv run pytest backend/tests/test_refresh_agents_integration.py::test_live_briefing_agent_returns_valid_brief -v
```

Should pass against the real API. Don't run this in this task; the user will run it.

- [ ] **Step 3: Verify default test run still skips it cleanly**

```bash
unset ANTHROPIC_API_KEY
uv run pytest -v
```

Should show 1 skipped test (the new live agent test) plus the existing 1 skipped (live Odds API).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_refresh_agents_integration.py
git commit -m "test(agents): opt-in live Anthropic agent smoke test"
```

---

## Phase 2.7 — Wrap-up

### Task 2.7.1: Update README and tag

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the README status table**

Mark Plan 2 as complete:

```markdown
| 2    | Briefing + prep advisor agents                         | complete    |
```

Add a usage section:

```markdown
## Live agent run

```bash
ODDS_API_KEY=... ANTHROPIC_API_KEY=... uv run python -m backend.refresh
```

When `ANTHROPIC_API_KEY` is set, the briefing and prep advisor agents populate `brief` and `prep` in `matches.json`. When unset, `brief` and `prep` remain `null` (the deterministic backend still produces a valid file).
```

- [ ] **Step 2: Final acceptance check**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
# Without ANTHROPIC_API_KEY in env, brief/prep should still be None
all_null = all(m['brief'] is None and m['prep'] is None for m in data['matches'])
assert all_null, 'with no anthropic key, brief/prep should be null'
print('Plan 2 acceptance check (no key): PASS')
"
```

If `ANTHROPIC_API_KEY` is set in the user's env, also verify a real run:

```bash
# (User will run this once)
ANTHROPIC_API_KEY=<key> ODDS_API_KEY=<key> uv run python -m backend.refresh
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
populated = [m for m in data['matches'] if m['brief'] is not None and m['prep'] is not None]
print(f'matches with brief+prep: {len(populated)}/{len(data[\"matches\"])}')
for m in populated[:3]:
    print(f\"  {m['id']}: {m['brief']['headline']}\")
"
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with Plan 2 completion and live agent usage"
```

- [ ] **Step 4: Move the milestone tag**

```bash
git tag -d plan-1-6-complete
git tag -a plan-2-complete -m "Plan 2: briefing + prep advisor agents"
git log --oneline | head -10
git tag
```

---

## Acceptance criteria for Plan 2

- `uv run pytest` → all tests pass (~75+ total).
- `uv run mypy backend` → no issues.
- `uv run ruff check backend` → no issues.
- `uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z` (no `ANTHROPIC_API_KEY`) → `brief` and `prep` are `null` everywhere; backend still produces a schema-valid `matches.json`.
- With mocked agents (in tests), `brief` and `prep` are populated for every match and validated against schema.
- With `ANTHROPIC_API_KEY` set and live API access, the live integration smoke test passes (manual user verification).
- Idempotence preserved: second refresh with no upstream change makes zero agent calls (signature-gated regeneration confirmed by `test_run_offline_skips_agent_calls_when_signature_unchanged`).
- Failure mode: when an agent raises `AgentSchemaError` and a previous brief/prep exists, the previous brief/prep are reused (no nulls written over real content).
