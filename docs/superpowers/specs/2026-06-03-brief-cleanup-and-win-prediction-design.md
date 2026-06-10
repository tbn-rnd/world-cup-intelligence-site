# Brief cleanup, pill consistency & confirmed-match win prediction

**Date:** 2026-06-03
**Status:** Approved (pending spec review)

## Goal

Tighten the public match view: trim the brief, purge property-preparation /
rate-strategy content from the entire stack, make popularity pills consistent,
expose the "View brief" expander on every match, and add a win-probability
prediction to confirmed matches (TBD matches already surface "which team is
likely to play").

## Scope decisions (confirmed with user)

1. Prep / rate-strategy removal goes **frontend + backend** — fully purged.
2. The **View brief** expander shows on **all 104 matches**, not just popular.
3. Confirmed-match win probability is a **backend-computed, persisted field**,
   with a **surgical backfill** into the existing `matches.json` (no recompute
   of TBD probabilities).

## Changes

### A. Brief content (frontend)
`src/components/expandedDetail.ts`
- Remove the **"Why this match is popular"** grid cell and the
  `popularityRationale` parameter threaded into `renderBrief`.
- Delete `renderPrep` entirely and its call site (and the
  "Prep recommendations not yet generated" empty state). No property-preparation
  section, no rate strategy — ever.

### B. Prep / rate-strategy removal (backend)
- `backend/schema.py`: delete the `Prep` model and the `prep` field on
  `MatchObject`.
- `backend/agents/prep.py`: delete the file (prep agent).
- `backend/agents/prompts.py`: remove `_PREP_SYSTEM_PROMPT`, `build_prep_prefix`,
  and prep references in the module docstring; keep the briefing prompt.
- `backend/refresh.py`: remove the `run_prep` import, the two `prep=None`
  constructor args, and the prep branch of `_apply_agents_to_matches`
  (now brief-only).
- Tests: delete `backend/tests/test_prep_agent.py`; strip prep assertions and
  mocks from `test_refresh_agents_integration.py`, `test_refresh_smoke.py`,
  `test_schema.py`, and `test_agents_prompts.py`.

### C. Rename "View brief & prep" → "View brief"
`confirmedTile.ts`, `tbdTile.ts`, `hero.ts` — collapsed-state label only;
expanded-state stays "Hide brief".

### D. View brief on all matches
Remove the `tier === "popular"` gate on the expander button in
`confirmedTile.ts` (`isFull`) and `tbdTile.ts`. Every match renders the
expander.

### E. Consistent popularity pills
`src/components/hero.ts` `popularityTag` returns "Popular Match" /
"Moderate Interest" / "Standard". Change to **"Popular" / "Moderate" /
"Standard"** to match `confirmedTile.ts`, `tbdTile.ts`, and the filter dropdown.
Single source of truth: introduce a shared `POPULARITY_LABEL` map (e.g. in
`src/utils/format.ts`) and consume it from all three components so labels can't
drift again.

### F. Confirmed-match win prediction (the one new feature)

**Model.** A FIFA-ranking Elo-style heuristic, clearly labelled as a model
estimate (NOT bookmaker odds — those drive the existing TBD/group math but are
unavailable per-confirmed-match here).

Two-way base from the rank gap (lower rank number = stronger):

```
p_a = 1 / (1 + 10 ** ((rank_a - rank_b) / S))      # S = 50 (tunable constant)
p_b = 1 - p_a
```

- **Group stage:** add a draw, largest when teams are even:
  `draw = D_MAX * (1 - |p_a - p_b|)` with `D_MAX = 0.30`; then scale the win
  probs by `(1 - draw)` so the three sum to 1.0.
- **Knockouts (R32…final, bronze):** `draw = None`; `p_a + p_b = 1.0`
  (interpreted as "to advance", i.e. includes ET/penalties).

**Backend model** (`backend/schema.py`):
```python
class TeamWinProb(BaseModel):
    code: str
    name: str
    win_prob: Annotated[float, Field(ge=0.0, le=1.0)]

class MatchPrediction(BaseModel):
    method: Literal["fifa_rank_elo"]
    teams: list[TeamWinProb]          # length 2, same order as teams.confirmed
    draw_prob: float | None = None    # group stage only

# MatchObject gains:
    prediction: MatchPrediction | None = None
```
TBD matches keep `prediction = None` (their prediction is `tbd_scenarios` /
`feeder_distributions`).

**Computation** — new pure module `backend/match_prediction.py`:
`predict_from_fifa_rank(team_a, team_b, phase) -> MatchPrediction`. Called from
`_build_confirmed_match` in `refresh.py`. Does not affect match signatures, so
brief-reuse logic is unchanged.

**Backfill** — `scripts/backfill_predictions.py`: load the committed
`site/data/matches.json` via `MatchesFile`, compute `prediction` for each
confirmed match from the `fifa_rank` already present, leave every other field
(including all TBD probabilities and `generated_at`) untouched, and rewrite with
the existing `writer.write_matches_file`. Idempotent.

**Frontend render** (`src/components/confirmedTile.ts`):
- `src/types.ts`: mirror `TeamWinProb` / `MatchPrediction` and the `prediction`
  field.
- Render a "Win probability" block in the confirmed tile body: one bar per team
  (reusing `formatProbability` + `probabilityBarBackground`), plus a Draw row
  when `draw_prob` is present. Caption: "Model estimate from FIFA ranking."
- New CSS in `site/assets/styles.css` for the prediction bars (mirror the
  feeder-bar styling).

## Data flow

`fixtures + knowledge → _build_confirmed_match` now also calls
`predict_from_fifa_rank` → `MatchObject.prediction` → serialized to
`matches.json` → fetched client-side → `renderConfirmedTile` draws the bars.
The backfill script bridges the *existing* committed file forward without a full
refresh.

## Testing

- **pytest:** `test_match_prediction.py` (probabilities sum to 1.0; favorite
  ordering; group draw present, knockout draw None; symmetry), a schema test for
  `MatchPrediction`, and a backfill test (confirmed populated, TBD untouched,
  byte-identical for non-prediction fields). Remove all prep tests.
- **vitest:** confirmed-tile test asserts the win bars render with correct
  percentages and draw row gating; tile test asserts the expander shows on
  non-popular tiers; a label test asserts hero/tile/filter pills all read
  "Popular"/"Moderate"/"Standard".
- Run `npm run typecheck`, `npm test`, and the backend test suite; rebuild via
  `npm run build`.

## Out of scope

- Live odds-based win probabilities for confirmed matches (FIFA-rank heuristic
  only for now).
- Recomputing TBD probabilities or running a full live/offline refresh.
