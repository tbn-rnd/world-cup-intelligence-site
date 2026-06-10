# IHG World Cup Site — Plan 1.6: Per-Feeder Team Distributions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Surface the per-feeder team distributions for every TBD slot (e.g., "Group A winner: Mexico 64%, Czech Republic 14%, …" / "Group F runner-up: Netherlands 32%, Japan 30%, …") in `matches.json`, so leadership scanning the site sees *which teams could plausibly play this match*, not just the most-likely cross-product matchup. Trim the cross-product top-5 to top-3 (now supporting detail rather than primary signal). Update the regeneration signature so a leading-team flip in any feeder triggers agent regeneration.

**Architecture:** Build on top of Plan 1.5. The closed-form group probabilities (`groups.py`) and the bracket simulation (`bracket_simulation.py`) already produce the data we need; this plan exposes it. Two additions: extend `bracket_simulation.SlotMatchupCounts` to also track per-slot *winner* histograms (needed to derive R16-feeder distributions), and have `refresh.py` emit a new `feeder_distributions` field per TBD match. For slots where we use the uniform-from-32-pool approximation (SF/Bronze), `feeder_distributions` is omitted and the UI falls back to the trimmed cross-product top-3.

**Tech Stack:** No new dependencies.

**Reference spec:** [`docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`](../specs/2026-05-08-world-cup-intelligence-site-design.md). Plan 1.6 is a small extension; the spec's data model (Section 3) gets a small documented additive change, the frontend section (Section 5) gets a one-paragraph note about the new primary scenario display.

**Predecessor:** Plan 1.5, tagged `plan-1-5-complete`.

---

## File structure produced by this plan

```
backend/
  schema.py                Add FeederDistribution + FeederTeam models; extend TeamsBlock
  bracket_simulation.py    Extend SlotMatchupCounts to track per-slot winner histograms
  refresh.py               Emit feeder_distributions; trim cross-product to top-3; update signature
  signature.py             Optionally extend to include leading-feeder-team component
  tests/                   New + extended tests

docs/
  superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md   Section 3 + 5 update
```

---

## Phase 1.6.1 — Schema: add `FeederDistribution`

### Task 1.6.1.1: Extend `backend/schema.py` with the new models

**Files:**
- Modify: `backend/schema.py`
- Modify: `backend/tests/test_schema.py`

- [ ] **Step 1: Add the new tests first (TDD)**

Append to `backend/tests/test_schema.py`:

```python
def test_feeder_distribution_validates() -> None:
    from backend.schema import FeederDistribution, FeederTeam

    fd = FeederDistribution(
        label="Group A winner",
        teams=[
            FeederTeam(code="MEX", name="Mexico", probability=0.64),
            FeederTeam(code="CZE", name="Czech Republic", probability=0.14),
        ],
    )
    assert fd.label == "Group A winner"
    assert len(fd.teams) == 2


def test_feeder_team_probability_bounds() -> None:
    from pydantic import ValidationError

    from backend.schema import FeederTeam

    with pytest.raises(ValidationError):
        FeederTeam(code="MEX", name="Mexico", probability=1.5)
    with pytest.raises(ValidationError):
        FeederTeam(code="MEX", name="Mexico", probability=-0.1)


def test_tbd_match_can_carry_feeder_distributions() -> None:
    from backend.schema import (
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

    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code=f"A{i}", name=f"A{i}"),
            team_b=TeamRef(code=f"B{i}", name=f"B{i}"),
            probability=0.1,
            delta_pp=0.0,
            rationale="r",
        )
        for i in range(1, 4)
    ]
    feeders = [
        FeederDistribution(
            label="Group A winner",
            teams=[FeederTeam(code="MEX", name="Mexico", probability=0.64)],
        ),
    ]
    m = MatchObject(
        id="x",
        kickoff_utc=datetime.now(timezone.utc),
        kickoff_local="2026-01-01T00:00:00Z",
        host_city="NY/NJ",
        venue="V",
        phase=Phase.ROUND_OF_32,
        status=Status.TBD,
        tickets=Tickets(stadium=6),
        demand_tier="tbd",
        confidence="medium",
        teams=TeamsBlock(
            confirmed=None,
            tbd_scenarios=scenarios,
            feeder_distributions=feeders,
        ),
        signature="v1:tbd:...",
        decision_date="2026-01-01",
        days_to_decision=10,
    )
    assert m.teams.feeder_distributions is not None
    assert m.teams.feeder_distributions[0].label == "Group A winner"


def test_confirmed_match_rejects_feeder_distributions() -> None:
    """Confirmed matches must NOT carry feeder_distributions."""
    from datetime import datetime, timezone

    from pydantic import ValidationError

    from backend.schema import (
        ConfirmedTeam,
        FeederDistribution,
        FeederTeam,
        MatchObject,
        Phase,
        Status,
        TeamsBlock,
        Tickets,
    )

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
            teams=TeamsBlock(
                confirmed=[
                    ConfirmedTeam(code="USA", name="USA", fifa_rank=1),
                    ConfirmedTeam(code="POR", name="Portugal", fifa_rank=2),
                ],
                tbd_scenarios=None,
                feeder_distributions=[
                    FeederDistribution(
                        label="x",
                        teams=[FeederTeam(code="MEX", name="Mexico", probability=0.5)],
                    )
                ],
            ),
            signature="v1:confirmed:USA-POR",
        )
```

Also update the existing `test_tbd_match_requires_exactly_five_scenarios` test to use 3 scenarios instead of 4 (the rank constraint was 1–5 in Plan 1; we'll keep that since the schema allows 1–5 entries — see Step 4 below for the rank constraint adjustment).

Wait — important detail: the existing schema's `TbdScenario.rank` has `Field(ge=1, le=5)`, and the existing `MatchObject.model_validator` currently enforces `len(tbd_scenarios) == 5`. We're trimming to 3, so the validator changes too. Update the test in lockstep:

- Replace `test_tbd_match_requires_exactly_five_scenarios` with `test_tbd_match_requires_exactly_three_scenarios` that asserts a 4-scenario list raises `ValidationError`.
- Update the test fixture in `test_brief_and_prep_can_be_populated` if it constructs a TBD match (it constructs a confirmed match, so it's unaffected — verify).

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest backend/tests/test_schema.py -v
```

Expected: ImportError on `FeederDistribution` / `FeederTeam`.

- [ ] **Step 3: Add the new models to `backend/schema.py`**

Add (alongside existing models):

```python
class FeederTeam(BaseModel):
    code: Annotated[str, Field(min_length=3, max_length=3)]
    name: str
    probability: Annotated[float, Field(ge=0.0, le=1.0)]


class FeederDistribution(BaseModel):
    label: str
    teams: list[FeederTeam]
```

Modify `TbdScenario.rank` to use `Field(ge=1, le=3)` (was `le=5`). Cross-product is now 3 entries.

Modify `TeamsBlock`:

```python
class TeamsBlock(BaseModel):
    confirmed: list[ConfirmedTeam] | None = None
    tbd_scenarios: list[TbdScenario] | None = None
    feeder_distributions: list[FeederDistribution] | None = None
```

- [ ] **Step 4: Update the model validator on `MatchObject`**

Change the validator so:

- Confirmed matches require `teams.confirmed` of length exactly 2, AND require BOTH `teams.tbd_scenarios` and `teams.feeder_distributions` to be `None`.
- TBD matches require `teams.tbd_scenarios` of length exactly **3** (was 5), require `teams.confirmed` to be `None`. `teams.feeder_distributions` MAY be populated (list of 1–N distributions) OR may be `None` (e.g., for SF/Bronze approximation slots that don't compute distributions).

Replace the existing `_teams_block_matches_status` body:

```python
    @model_validator(mode="after")
    def _teams_block_matches_status(self) -> "MatchObject":
        if self.status == Status.CONFIRMED:
            if self.teams.confirmed is None or len(self.teams.confirmed) != 2:
                raise ValueError(
                    "confirmed match requires exactly 2 entries in teams.confirmed"
                )
            if self.teams.tbd_scenarios is not None:
                raise ValueError("confirmed match must have teams.tbd_scenarios=None")
            if self.teams.feeder_distributions is not None:
                raise ValueError("confirmed match must have teams.feeder_distributions=None")
        else:  # TBD
            if self.teams.tbd_scenarios is None or len(self.teams.tbd_scenarios) != 3:
                raise ValueError(
                    "TBD match requires exactly 3 entries in teams.tbd_scenarios"
                )
            if self.teams.confirmed is not None:
                raise ValueError("TBD match must have teams.confirmed=None")
        return self
```

- [ ] **Step 5: Update `test_tbd_match_requires_exactly_five_scenarios`**

Rename the function and adjust the loop:

```python
def test_tbd_match_requires_exactly_three_scenarios() -> None:
    """TBD match with 2 scenarios should fail validation."""
    scenarios = [
        TbdScenario(
            rank=i,
            team_a=TeamRef(code=f"A{i}", name=f"A{i}"),
            team_b=TeamRef(code=f"B{i}", name=f"B{i}"),
            probability=0.1,
            delta_pp=0.0,
            rationale="r",
        )
        for i in range(1, 3)  # only 2 scenarios — should fail
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
            teams=TeamsBlock(confirmed=None, tbd_scenarios=scenarios),
            signature="v1:tbd:...",
            brief=None,
            prep=None,
            decision_date="2026-07-03",
            days_to_decision=2,
        )
```

- [ ] **Step 6: Run tests, mypy, ruff**

```bash
uv run pytest backend/tests/test_schema.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass. Note that other tests (`test_writer.py`, `test_refresh_smoke.py`) depend on the current `MatchesFile` shape; they construct TBD matches with 5 scenarios. Those will need updating in subsequent tasks, but they shouldn't break solely from this task because those test files don't directly assert on the rank-3 constraint — they construct `MatchesFile` from real refresh runs (which we update in Task 1.6.3) or from confirmed-match fixtures.

If `test_writer.py`'s `_minimal_file` builds 11 confirmed matches (it does), it's unaffected. If `test_refresh_smoke.py` asserts `len(scenarios) == 5`, it'll break — adjust to `len(scenarios) == 3` only after Task 1.6.3 lands. For now, the schema task should leave `test_refresh_smoke.py` as-is and accept that it may temporarily fail; we mark this in the commit message.

Run JUST `test_schema.py`, `test_writer.py`, `test_inventory.py`, `test_knowledge.py`, `test_bracket.py`, `test_confidence.py`, `test_signature.py`, `test_odds_client.py`, `test_probabilities.py`, `test_groups.py`, `test_bracket_simulation.py` — all of these should pass.

`test_refresh_smoke.py` may fail at the assertion `len(nj_r32["teams"]["tbd_scenarios"]) == 5`. Note this in your commit message; it'll be re-stabilized by Task 1.6.3.

- [ ] **Step 7: Commit**

```bash
git add backend/schema.py backend/tests/test_schema.py
git commit -m "feat(schema): add FeederDistribution model; trim TBD scenarios to 3"
```

---

## Phase 1.6.2 — Bracket simulation: track per-slot winner histograms

For R16 slots fed by R32 winners, we need a probability distribution over teams that reach the R16 slot — i.e., the marginal "team X wins r32_match_75" distribution. The current simulation samples `r32_winner` per iteration but only uses it to record R16 matchups, not to maintain a winner histogram.

### Task 1.6.2.1: Extend `SlotMatchupCounts` with `winner_count`

**Files:**
- Modify: `backend/bracket_simulation.py`
- Modify: `backend/tests/test_bracket_simulation.py`

- [ ] **Step 1: Add the failing test**

Append to `backend/tests/test_bracket_simulation.py`:

```python
def test_slot_records_winner_histogram() -> None:
    """SlotMatchupCounts.record_winner builds a per-team count for the slot's winner."""
    counts = SlotMatchupCounts()
    counts.record_winner("MEX")
    counts.record_winner("MEX")
    counts.record_winner("NED")
    assert counts.winner_count == {"MEX": 2, "NED": 1}
    top = counts.top_winners(k=2)
    assert top[0] == ("MEX", 2 / 3)
    assert top[1] == ("NED", 1 / 3)


def test_simulate_bracket_records_r32_winner_histogram_for_ihg_slots() -> None:
    """Plan 1.6 contract: bracket simulator records winner histograms at every IHG R32 slot."""
    groups = _example_groups()
    counts = simulate_bracket(
        group_probs=groups,
        bracket_yaml_groups={g: list(p.win_probs.keys()) for g, p in groups.items()},
        n_iterations=2000,
        rng=random.Random(11),
    )
    for slot in ("r32_match_75", "r32_match_80", "r32_match_85"):
        assert sum(counts[slot].winner_count.values()) == 2000, (
            f"slot {slot} winner_count incomplete"
        )
```

- [ ] **Step 2: Run test (expect AttributeError)**

```bash
uv run pytest backend/tests/test_bracket_simulation.py -v
```

- [ ] **Step 3: Extend `SlotMatchupCounts` and the simulator**

In `backend/bracket_simulation.py`, modify `SlotMatchupCounts`:

```python
@dataclass
class SlotMatchupCounts:
    matchup_count: dict[tuple[str, str], int] = field(default_factory=dict)
    winner_count: dict[str, int] = field(default_factory=dict)

    def record(self, team_a: str, team_b: str) -> None:
        key: tuple[str, str] = (team_a, team_b) if team_a < team_b else (team_b, team_a)
        self.matchup_count[key] = self.matchup_count.get(key, 0) + 1

    def record_winner(self, team: str) -> None:
        self.winner_count[team] = self.winner_count.get(team, 0) + 1

    def top_matchups(self, k: int) -> list[tuple[tuple[str, str], float]]:
        total = sum(self.matchup_count.values())
        if total == 0:
            return []
        ranked = sorted(self.matchup_count.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [(matchup, count / total) for matchup, count in ranked]

    def top_winners(self, k: int) -> list[tuple[str, float]]:
        total = sum(self.winner_count.values())
        if total == 0:
            return []
        ranked = sorted(self.winner_count.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [(team, count / total) for team, count in ranked]
```

In `simulate_bracket`, in the per-iteration loop, AFTER computing `r32_winner`, also record winners for the IHG R32 slots:

```python
        for slot, winner in r32_winner.items():
            if slot in counts:  # only record for slots we care about
                counts[slot].record_winner(winner)
```

This means R32 IHG slots get both `matchup_count` and `winner_count` populated. R16 slots get only `matchup_count` (no winner_count, since we don't simulate R16 winners — that recursion is deferred). SF/Bronze get only `matchup_count` (uniform-pool sample).

- [ ] **Step 4: Run tests**

```bash
uv run pytest backend/tests/test_bracket_simulation.py -v
uv run mypy backend
uv run ruff check backend
```

All must pass.

- [ ] **Step 5: Commit**

```bash
git add backend/bracket_simulation.py backend/tests/test_bracket_simulation.py
git commit -m "feat(backend): track per-slot winner histograms in bracket simulator"
```

---

## Phase 1.6.3 — `refresh.py`: emit `feeder_distributions` and trim cross-product

This is the substantive integration. For each TBD match:

1. **Direct group-feeder slots** (R32 NJ/ATL/MIA, in part — NJ is fully direct; ATL/MIA have one direct + one best-third-place):
   - Each `FeederGroupWinner(group=X)` → emit a `FeederDistribution(label=f"Group {X} winner", teams=...)` from `group_probs[X].win_probs`
   - Each `FeederGroupRunnerUp(group=X)` → emit from `runner_up_probs`
   - Each `FeederBestThirdPlace(eligible_groups=...)` → emit a single distribution from the aggregated weighting (already computed by `_team_distribution_for_feeder` in `probabilities.py`)

2. **R16 slots** fed by `FeederR32Winner(slot=X)` → emit a distribution from `sim_counts[X].top_winners()` (every team that won that R32 slot in simulation)

3. **SF/Bronze slots** with `FeederQfWinner` / `FeederSfLoser`: these are computed via the uniform-from-32-pool approximation in the simulator. We DO NOT emit `feeder_distributions` for these (the result would be uninformative — every team at ~3%). Set `feeder_distributions=None`. The cross-product top-3 (already populated) provides the visual, with the confidence label honestly graded as "low."

Cross-product `tbd_scenarios` is trimmed to top-3 in all cases.

### Task 1.6.3.1: Update `_build_tbd_match` in `refresh.py`

**Files:**
- Modify: `backend/refresh.py`
- Modify: `backend/tests/test_refresh_smoke.py`

- [ ] **Step 1: Add helpers to `refresh.py` for label/distribution generation**

Add near the existing helpers:

```python
def _label_for_feeder(f: Any) -> str:
    if isinstance(f, FeederGroupWinner):
        return f"Group {f.group} winner"
    if isinstance(f, FeederGroupRunnerUp):
        return f"Group {f.group} runner-up"
    if isinstance(f, FeederBestThirdPlace):
        groups = ", ".join(f.eligible_groups)
        return f"Best 3rd-place team (groups {groups})"
    if isinstance(f, FeederR32Winner):
        return f"Winner of {f.slot}"
    if isinstance(f, FeederQfWinner):
        return f"Winner of {f.slot}"
    if isinstance(f, FeederSfLoser):
        return f"Loser of {f.slot}"
    return "TBD"


def _feeder_distribution(
    feeder: Any,
    group_probs: dict[str, GroupAdvanceProbs],
    sim_counts: dict[str, "SlotMatchupCounts"],
    kb: KnowledgeBase,
) -> FeederDistribution | None:
    """Return a populated FeederDistribution for a feeder, or None if not derivable."""
    label = _label_for_feeder(feeder)

    if isinstance(feeder, FeederGroupWinner):
        dist = group_probs[feeder.group].win_probs
    elif isinstance(feeder, FeederGroupRunnerUp):
        dist = group_probs[feeder.group].runner_up_probs
    elif isinstance(feeder, FeederBestThirdPlace):
        from backend.probabilities import _team_distribution_for_feeder
        dist = _team_distribution_for_feeder(feeder, group_probs)
    elif isinstance(feeder, FeederR32Winner):
        slot_counts = sim_counts.get(feeder.slot)
        if slot_counts is None or sum(slot_counts.winner_count.values()) == 0:
            return None
        total = sum(slot_counts.winner_count.values())
        dist = {team: count / total for team, count in slot_counts.winner_count.items()}
    else:
        # FeederQfWinner / FeederSfLoser: uniform-pool approximation; don't emit a
        # feeder_distribution — the SF/Bronze fallback uses cross-product only.
        return None

    teams = sorted(
        (
            FeederTeam(
                code=_safe_code(code),
                name=kb.teams[code].name if code in kb.teams else code,
                probability=prob,
            )
            for code, prob in dist.items()
        ),
        key=lambda t: t.probability,
        reverse=True,
    )
    return FeederDistribution(label=label, teams=teams)
```

- [ ] **Step 2: Update `_build_tbd_match` to assemble feeder_distributions, trim cross-product, and pass into TeamsBlock**

Modify the existing `_build_tbd_match` function:

1. After `feeders = bracket.feeders_for_slot(...)`, compute:

```python
    feeder_distributions: list[FeederDistribution] = []
    for f in feeders:
        fd = _feeder_distribution(f, group_probs, sim_counts, kb)
        if fd is not None:
            feeder_distributions.append(fd)
    feeder_distributions_or_none = feeder_distributions if feeder_distributions else None
```

2. After computing `scenarios_obj` from the existing logic, **trim** to the top 3:

```python
    scenarios_obj = scenarios_obj[:3]
```

Existing code constructs scenarios in descending probability order with rank=1..5, so trimming to `[:3]` leaves rank=1,2,3 correctly populated — no re-rank needed.

3. Pass `feeder_distributions_or_none` into the `TeamsBlock`:

```python
    teams=TeamsBlock(
        confirmed=None,
        tbd_scenarios=scenarios_obj,
        feeder_distributions=feeder_distributions_or_none,
    ),
```

The rest of `_build_tbd_match` (signature computation, MatchObject construction) stays the same.

- [ ] **Step 3: Add new test in `test_refresh_smoke.py`**

Append:

```python
def test_offline_run_emits_feeder_distributions_for_direct_group_slots(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.6 contract: every direct-group-feeder TBD slot has populated feeder_distributions."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())

    nj_r32 = next(m for m in raw["matches"] if m["id"] == "njy-2026-06-30-r32-a1-vs-f2")
    fd = nj_r32["teams"]["feeder_distributions"]
    assert fd is not None
    assert len(fd) == 2  # Group A winner + Group F runner-up
    labels = {entry["label"] for entry in fd}
    assert labels == {"Group A winner", "Group F runner-up"}
    # Each distribution should sum to ~1.0
    for entry in fd:
        assert abs(sum(t["probability"] for t in entry["teams"]) - 1.0) < 0.01
        # Teams sorted descending by probability
        probs = [t["probability"] for t in entry["teams"]]
        assert probs == sorted(probs, reverse=True)


def test_offline_run_trims_cross_product_to_three(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.6 contract: tbd_scenarios is exactly 3 entries (was 5 in Plan 1.5)."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    for m in raw["matches"]:
        if m["status"] == "tbd":
            assert len(m["teams"]["tbd_scenarios"]) == 3, (
                f"{m['id']} has {len(m['teams']['tbd_scenarios'])} scenarios"
            )


def test_offline_run_omits_feeder_distributions_for_sf_bronze(
    tmp_path: Path,
    fixtures_dir: Path,
    knowledge_dir: Path,
) -> None:
    """Plan 1.6 contract: SF and Bronze slots use uniform-pool approximation; no feeder_distributions."""
    output_path = tmp_path / "matches.json"
    run_offline(
        knowledge_dir=knowledge_dir,
        odds_fixture_path=fixtures_dir / "odds_response_full.json",
        output_path=output_path,
        as_of="2026-06-20T12:00:00Z",
    )
    raw = json.loads(output_path.read_text())
    for slot_id in ("atl-2026-07-15-sf", "mia-2026-07-18-bronze"):
        m = next(x for x in raw["matches"] if x["id"] == slot_id)
        assert m["teams"]["feeder_distributions"] is None
```

Also: update the existing `test_offline_run_produces_valid_eleven_match_file` to assert `len(nj_r32["teams"]["tbd_scenarios"]) == 3` (was 5).

- [ ] **Step 4: Run the full suite**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
```

All must pass. The earlier-mentioned `test_offline_run_produces_valid_eleven_match_file` assertion update is required.

- [ ] **Step 5: Run end-to-end offline**

```bash
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
nj = next(m for m in data['matches'] if m['id'] == 'njy-2026-06-30-r32-a1-vs-f2')
print(f'NJ R32 feeder_distributions:')
for entry in nj['teams']['feeder_distributions']:
    print(f'  {entry[\"label\"]}:')
    for t in entry['teams']:
        bar = chr(0x2588) * int(t['probability'] * 50)
        print(f\"    {t['code']:>3} {t['name']:<20s} {bar} {t['probability']*100:.1f}%\")
print(f'\\nNJ R32 cross-product top-3:')
for s in nj['teams']['tbd_scenarios']:
    print(f\"  rank{s['rank']}: {s['team_a']['name']} vs {s['team_b']['name']}  p={s['probability']:.3f}\")
"
```

Should print two feeder distributions (Group A winner, Group F runner-up) with each team's probability, then 3 cross-product scenarios.

- [ ] **Step 6: Idempotence check**

```bash
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
md5 -q site/data/matches.json
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
md5 -q site/data/matches.json
```

Both md5s must match.

- [ ] **Step 7: Commit**

```bash
git add backend/refresh.py backend/tests/test_refresh_smoke.py
git commit -m "feat(backend): emit per-feeder team distributions; trim cross-product to top-3"
```

---

## Phase 1.6.4 — Signature: include leading-feeder team

A leading team flip in any feeder distribution should trigger Plan 2's agent regeneration. Currently the signature only captures the cross-product top-1 leader; we add a feeder-leaders component.

### Task 1.6.4.1: Extend `compute_signature` and update callers

**Files:**
- Modify: `backend/signature.py`
- Modify: `backend/tests/test_signature.py`
- Modify: `backend/refresh.py`

- [ ] **Step 1: Add the test**

Append to `backend/tests/test_signature.py`:

```python
def test_signature_includes_feeder_leaders() -> None:
    """When feeder_leaders is populated, the signature embeds them deterministically."""
    sig = compute_signature(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "NED"),
        top1_probability=0.11,
        top5_team_codes=("CZE", "JPN", "MEX", "NED", "SWE"),
        confidence="low",
        feeder_leaders=("MEX", "NED"),
    )
    assert "feeders=MEX,NED" in sig


def test_signature_changes_when_feeder_leader_flips() -> None:
    base_kwargs = dict(
        status="tbd",
        confirmed_team_codes=None,
        top1_codes=("MEX", "NED"),
        top1_probability=0.11,
        top5_team_codes=("CZE", "JPN", "MEX", "NED", "SWE"),
        confidence="low",
    )
    sig_a = compute_signature(**base_kwargs, feeder_leaders=("MEX", "NED"))
    sig_b = compute_signature(**base_kwargs, feeder_leaders=("MEX", "JPN"))
    assert sig_a != sig_b
```

- [ ] **Step 2: Update `compute_signature` to accept and embed `feeder_leaders`**

In `backend/signature.py`:

```python
def compute_signature(
    *,
    status: Literal["confirmed", "tbd"],
    confirmed_team_codes: tuple[str, str] | None,
    top1_codes: tuple[str, str] | None,
    top1_probability: float | None,
    top5_team_codes: tuple[str, ...] | None,
    confidence: str,
    feeder_leaders: tuple[str, ...] | None = None,
) -> str:
    if status == "confirmed":
        assert confirmed_team_codes is not None
        a, b = sorted(confirmed_team_codes)
        return f"v1:confirmed:{a}-{b}"

    assert top1_codes is not None
    assert top1_probability is not None
    assert top5_team_codes is not None
    a, b = sorted(top1_codes)
    bucket_lo = int((top1_probability * 100) // 5) * 5
    bucket_hi = bucket_lo + 5
    set_str = ",".join(sorted(top5_team_codes))
    feeders_str = ""
    if feeder_leaders:
        feeders_str = f":feeders={','.join(feeder_leaders)}"
    return (
        f"v1:tbd:top1={a}-{b}:bucket={bucket_lo}-{bucket_hi}"
        f":set={set_str}:conf={confidence}{feeders_str}"
    )
```

The default `None` keeps it backwards-compatible with existing call sites that don't yet pass `feeder_leaders`.

- [ ] **Step 3: Update `refresh.py` to pass feeder_leaders**

In `_build_tbd_match`, after computing `feeder_distributions`, derive the leaders tuple:

```python
    feeder_leaders: tuple[str, ...] | None = None
    if feeder_distributions:
        feeder_leaders = tuple(fd.teams[0].code for fd in feeder_distributions)
```

Pass it into `compute_signature(...)` along with the other args.

- [ ] **Step 4: Run tests**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
```

All must pass. Note that the signature for TBD matches now changes shape — the `test_confidence_transition_changes_tbd_signature` test from Plan 1 should still pass (its contract is "signatures should differ across confidence transitions," which they do).

- [ ] **Step 5: Commit**

```bash
git add backend/signature.py backend/refresh.py backend/tests/test_signature.py
git commit -m "feat(backend): embed feeder leaders in TBD signatures for tighter regen triggers"
```

---

## Phase 1.6.5 — Spec update + README + verification

### Task 1.6.5.1: Update the design spec and README

**Files:**
- Modify: `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`
- Modify: `README.md`

- [ ] **Step 1: Update Section 3 (data model) of the spec**

Find the `TbdScenario` block in Section 3. After the `tbd_scenarios` description, add:

```markdown
**`feeder_distributions`** is the primary signal for who could plausibly play this match. For each feeder of the slot (e.g., "Group A winner" and "Group F runner-up"), it carries a distribution over the teams that could fill that role with their probabilities. This is more informationally dense than the cross-product `tbd_scenarios` for leadership scanning — it answers "which teams could be at this match in any scenario" directly, rather than enumerating specific pairings.

For SF and Bronze slots that use the uniform-from-32-pool approximation, `feeder_distributions` is `null` and the UI falls back to the cross-product top-3.

`tbd_scenarios` is trimmed to **top-3** (was top-5) — supporting detail rather than primary signal.
```

Also adjust the example JSON in Section 3 to show `feeder_distributions` populated and `tbd_scenarios` with 3 entries.

- [ ] **Step 2: Update Section 5 (frontend) of the spec**

In Section 5's "TBD-match tile" component description, change:

```markdown
5. **TBD-match tile (the centerpiece component)** — date and slot context at top
   ("Group A winner × Group F runner-up — Round of 32"), then the **per-feeder team
   distributions as horizontal probability bars** showing which teams could fill each
   feeder slot (e.g., "Group A winner: Mexico 64%, Czech Republic 14%..."). Below
   that, a smaller "Most-likely specific matchups" subsection shows the top-3
   cross-product scenarios with country flags, codes, percentages, and delta arrows.
   Decision-date countdown badge in the top-right that turns amber at T-3 and red at
   T-1.
```

- [ ] **Step 3: Update README**

Add a row to the status table:

```markdown
| 1.6  | Per-feeder team distributions in TBD matches           | complete    |
```

- [ ] **Step 4: Final acceptance check**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
uv run python -c "
import json
data = json.load(open('site/data/matches.json'))
tbd = [m for m in data['matches'] if m['status'] == 'tbd']
assert len(tbd) == 7
direct = [m for m in tbd if m['teams']['feeder_distributions'] is not None]
assert len(direct) >= 3, f'expected at least 3 TBD slots with feeder_distributions, got {len(direct)}'
for m in direct:
    fd = m['teams']['feeder_distributions']
    assert len(fd) >= 1
    for entry in fd:
        assert 'label' in entry and 'teams' in entry
        assert len(entry['teams']) >= 1
for m in tbd:
    assert len(m['teams']['tbd_scenarios']) == 3
print('Plan 1.6 acceptance check: PASS')
"
```

Expected: ends with `Plan 1.6 acceptance check: PASS`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md README.md
git commit -m "docs: document feeder_distributions in spec and README"
```

- [ ] **Step 6: Move the milestone tag**

```bash
git tag -d plan-1-5-complete
git tag -a plan-1-6-complete -m "Plan 1.6: per-feeder team distributions in TBD matches"
git log --oneline | head -10
git tag
```

---

## Acceptance criteria for Plan 1.6

- `uv run pytest` → all tests pass (~55+ tests).
- `uv run mypy backend` → no issues.
- `uv run ruff check backend` → no issues.
- `uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z` → produces a `matches.json` where every TBD match has `tbd_scenarios` length 3, R32 NJ/ATL/MIA + R16 NJ/ATL slots have populated `feeder_distributions`, and SF/Bronze slots have `feeder_distributions = null`.
- Idempotence preserved.
- Live-API run produces real team names in `feeder_distributions[*].teams[*].name`.
- Spec Section 3 documents `feeder_distributions`; Section 5 mentions it as primary scenario display.
