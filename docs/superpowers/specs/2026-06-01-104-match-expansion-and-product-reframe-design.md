# 104-Match Expansion & Product Reframe — Design Spec

**Date:** 2026-06-01
**Supersedes (in part):** `2026-05-08-world-cup-intelligence-site-design.md`

## Purpose

Reframe the site from an IHG ticket-portfolio view (11 matches with hand-curated demand tier and per-property F&B/owner-invitation advice) to a public tournament-intelligence view covering all 104 matches of the FIFA World Cup 2026. The deep intelligence layer (cultural context, language, rate strategy, logistics) is preserved but tier-gated so it appears only on the matches that drive real interest.

## Scope

Five coordinated changes:

1. **API data expansion** — surface all 104 FIFA matches in the public site.
2. **Popularity (replaces demand)** — three-tier (`Popular` / `Moderate` / `Standard`) deterministic label with displayed rationale; ticket-specific demand tier dropped.
3. **One-pager / hotel-user guide** — standalone HTML page and printable Markdown source, including a glossary.
4. **F&B suggestions removal** — drop the `fnb` block from the prep agent; food traditions fold into `cultural_context` as background.
5. **Ticket information removal** — full removal of `tickets`, `demand_tier`, `ticket_inventory.yaml`, and any owner-invitation framing across schema, agents, UI, and docs.

Out of scope: backend infra changes (cron cadence, deploy pipeline, GitHub Actions). The existing refresh-and-publish architecture stays as-is.

## Architecture (recommended approach: tier-gated agents)

Two render modes per match, gated by `popularity.tier`:

- **Lite tile** (`moderate` / `standard`) — teams, kickoff, host city, venue, phase chip, popularity badge, one-line popularity rationale. No expand affordance.
- **Full tile** (`popular`) — Lite tile + expand affordance that opens the briefing/prep card.

The briefing and prep agents only run for `popular` matches; non-popular matches carry `brief: null` and `prep: null`. This keeps per-refresh agent cost roughly in line with today while expanding the public view from 11 to 104 matches.

## Data model

### New file: `knowledge/fixtures_2026.yaml`

Replaces `knowledge/ticket_inventory.yaml`. Contains all 104 matches transcribed from FIFA's published 2026 schedule.

Schema per entry:

```yaml
- id: <city>-<date>-<groupOrSlot>-<teamA>-<teamB>
  kickoff_local: "2026-06-11T12:00:00-06:00"
  kickoff_utc:   "2026-06-11T18:00:00Z"
  host_city: Mexico City
  venue: Estadio Azteca
  phase: group_stage   # group_stage | round_of_32 | round_of_16 | quarter_finals | semi_finals | bronze_final | final
  status: confirmed    # confirmed for the 72 group-stage matches; tbd for the 32 knockout slots
  # if status == confirmed
  confirmed_teams: [MEX, KOR]
  group: A
  # if status == tbd
  bracket_slot: r32_match_75
  decision_date: "2026-06-27"
```

Tournament-format note: 48 teams × 12 groups × 6 matches/group = 72 group-stage matches; knockout rounds (R32 → final + bronze) = 32 matches. Total = 104. The implementation plan re-verifies the per-phase counts before transcription.

### `MatchObject` schema changes

Removed: `tickets`, `demand_tier`.
Added: `popularity` object —

```json
{
  "tier": "popular" | "moderate" | "standard",
  "rationale": "Brazil (FIFA #1) draws a global audience."
}
```

### `prep` schema changes

Removed: `fnb` block (all of `suggestions`, `requirements`, `operational_notes`), `owner_invitation_note`.
Retained: `language`, `rate_strategy`, `logistics`.

### `brief` schema changes

Removed: `demand_rationale` (replaced by deterministic `popularity.rationale`).
Modified: `cultural_context` expands from 2-3 sentences to 3-5 sentences, with explicit instruction to weave in food traditions, religious/dietary observances, and fan rituals as cultural background — not as instructions for the property.

## Popularity computation

New module: `backend/popularity.py`. Called inside `build_matches_file` for every match. Fully deterministic — no LLM.

**Constants (curated in code):**

```python
HOST_NATIONS = {"USA", "MEX", "CAN"}
GLOBAL_DRAW_BRANDS = {"BRA", "ARG", "FRA", "ENG", "GER", "ESP", "POR", "NED", "BEL"}
```

**Rules (first match wins):**

| Tier | Trigger |
|---|---|
| **Popular** | Phase ∈ {final, semi_finals, bronze_final}. OR any confirmed team has FIFA rank ≤ 10. OR phase = group_stage AND any confirmed team is in HOST_NATIONS or GLOBAL_DRAW_BRANDS. |
| **Moderate** | Phase ∈ {quarter_finals, round_of_16, round_of_32} (if not already Popular). OR phase = group_stage AND at least one team has FIFA rank ≤ 25. |
| **Standard** | Everything else. |

**Rationale text:** deterministic short sentence, joined from the matched triggers. Examples:

- "Brazil (FIFA #1) draws a global audience."
- "Quarter-final — knockout intensity."
- "Host-nation match in Mexico City."
- "Group stage; teams outside the top 25."

**TBD-slot handling:** for knockout slots with unconfirmed teams, popularity is phase-only until the feeder distribution narrows. Once any feeder's leading team passes 60% probability, the team-based triggers (top-10, host nation, global-draw) fire against the leader. Below threshold the tier stays phase-based.

## Agent pipeline changes

### Tier gate

In `_apply_agents_to_matches` (`backend/refresh.py`), wrap the briefing + prep calls in `if match.popularity.tier != "popular": continue`. Signature-cache reuse continues to apply for popular matches.

### Briefing agent (`backend/agents/briefing.py`, `backend/agents/prompts.py`)

- Output schema: drop `demand_rationale`.
- `cultural_context`: 3-5 sentences; prompt instructs the model to include food traditions, observances, and fan rituals as cultural background, not as operational F&B prescriptions for the property.
- System prompt: drop all references to demand tier, IHG ticket inventory, and owner invitation decisions.

### Prep agent (`backend/agents/prep.py`, `backend/agents/prompts.py`)

- Output schema: drop `fnb` block and `owner_invitation_note`.
- Retains `language`, `rate_strategy`, `logistics`.
- System prompt: audience reframed from "IHG strategy team making invitation decisions" to "any IHG property GM in the host-city market." No ticket framing.

### Prompt prefix changes

`build_briefing_prefix` and `build_prep_prefix` no longer load `ticket_inventory.yaml`. The cached prefix contains only `teams.yaml` and `cities.yaml`. First refresh after deploy pays one cache miss per agent invocation; steady state recovers.

## Frontend changes

### Components

- `confirmedTile.ts`, `tbdTile.ts` — branch on `popularity.tier`. Lite mode skips the brief/prep summary and the expand button. Drop all `tickets` rendering (suite/stadium/club lines). Render popularity badge + rationale.
- `expandedDetail.ts` — drop the `fnb` section and `owner_invitation_note` block. Rename "Demand rationale" heading to "Why this match is popular." Allow `cultural_context` more vertical space.
- `hero.ts` — surface the highest-popularity confirmed match instead of highest-demand. Drop ticket-count language.
- `timeline.ts` — replace `demand_tier` color encoding with `popularity.tier` encoding using the same color slots.
- `filters.ts` — replace "Demand: high/medium/low" filter with "Popularity: popular/moderate/standard." Add a phase filter.
- `header.ts` — add a "Guide" nav link pointing to `/guide.html`.

### Types (`src/types.ts`)

Drop `Tickets` type, drop `demand_tier`. Add `Popularity` type. Drop `fnb` block and `owner_invitation_note` from `Prep`. Drop `demand_rationale` from `Brief`.

### Popularity badge

Uses the existing chip pattern. Three colors: Popular (warm accent), Moderate (neutral), Standard (muted).

## Hotel-user guide (one-pager)

### Source and delivery

- **Source of truth:** `site/guide.md` — single Markdown file.
- **Web rendering:** build step in `scripts/build.mjs` renders `guide.md` → `site/guide.html` at build time. No client-side Markdown parser.
- **Print/PDF:** `@media print` block in `site/assets/styles.css` strips nav, drops backgrounds to white, sets serif body, enforces page breaks per major section. Users get a PDF via browser File → Print → Save as PDF. No headless Chrome dependency.

### Content outline

1. **What this site is** — one paragraph. Live tournament intelligence for IHG properties across all 104 FIFA World Cup 2026 matches.
2. **How to read a match tile** — annotated walkthrough of a Popular tile and a Lite tile, with each element labeled.
3. **Match popularity, explained** — what `Popular` / `Moderate` / `Standard` mean and the deterministic rules behind them.
4. **TBD knockout matches** — how to interpret a slot with scenarios instead of confirmed teams, what feeder-distribution percentages mean, why a slot's popularity may upgrade as the bracket resolves.
5. **The deep brief** (Popular matches only) — what to expect inside an expanded tile: cultural context, language requirements, rate strategy, logistics. Framed as background and operational guidance, not prescriptive.
6. **Data freshness & timing** — refresh cadence and what the freshness indicator means.
7. **Glossary** — alphabetical. Covers: Bracket slot, Bronze final, Confirmed match, Cultural context, Decision date, Diaspora, FIFA rank, Final draw, Fixture, Global-draw brand, Group stage, Host city, Host nation, Kickoff (local vs UTC), Knockout phase, Logistics, Match popularity, Moderate, Phase, Popular, Popularity rationale, Quarter-final, Rate strategy, Round of 16, Round of 32, Scenario, Semi-final, Standard, TBD, Venue.
8. **Where to send questions** — placeholder contact line.

## Testing

### Backend

- **New:** `backend/tests/test_popularity.py` — per-rule unit tests, TBD-slot phase-only path, 60% feeder-leader threshold for team-based triggers.
- `test_schema.py` — drop assertions on `tickets`, `demand_tier`, `fnb`, `owner_invitation_note`, `demand_rationale`; add assertions on `popularity` object shape.
- `test_refresh_agents_integration.py` — assert that `moderate` and `standard` matches never invoke the agent client; only `popular` matches do.
- `test_writer.py` — fixture updates.
- `test_briefing_agent.py`, `test_prep_agent.py` — drop dropped-field assertions; assert expanded `cultural_context` carries food-tradition phrasing.
- `test_refresh_smoke.py` — drop `fnb` and ticket references; point to `fixtures_2026.yaml`.

### Frontend

- `src/tests/types.test.ts`, `src/tests/diff.test.ts` — schema updates.
- **New:** verify Lite tiles render no expand affordance.

## Cleanup

Files removed:

- `knowledge/ticket_inventory.yaml`
- `backend/inventory.py` if its sole role is reading that file; otherwise rename to `backend/fixtures.py` and adapt the loader to the new YAML shape.

Strings purged (search-and-update pass):

- `README.md` — drop "11 ticket matchups" framing; restate as 104-match tournament view.
- `site/index.html` methodology footer — drop ticket-inventory references.
- `2026-05-08-world-cup-intelligence-site-design.md` — leave as historical record; add a top-line pointer to this newer spec.

## Rollout order

One PR per step is acceptable; bundling is also fine where dependencies allow.

1. New `fixtures_2026.yaml` (all 104 matches) + schema changes (remove `tickets`, `demand_tier`, `fnb`, `owner_invitation_note`, `demand_rationale`; add `popularity`).
2. `backend/popularity.py` + tier gate in `_apply_agents_to_matches` + popularity unit tests.
3. Agent prompt + schema updates (drop fnb / owner note / demand_rationale; expand cultural_context).
4. Frontend: drop ticket/fnb UI, add popularity badge, Lite/Full tile split, add Guide nav link.
5. Guide content (`site/guide.md`) + build step + print styles.
6. README + methodology footer cleanup.

## Risks and mitigations

- **First refresh after deploy** invalidates the agent prompt cache (the inventory knowledge block is gone from the prefix). Expect one cache-miss per agent invocation on first run; steady state recovers.
- **104-match transcription** is manual data entry. Mitigation: spot-check per-phase counts (group=72, R32=16, R16=8, QF=4, SF=2, bronze=1, final=1 = 104) and validate per-group kickoff times against FIFA's published schedule before committing.
- **Time-zone surface** is wider with 16 venues. The existing `kickoff_local` / `kickoff_utc` pattern handles it; transcription discipline is the safeguard.
- **TBD popularity tier flips** as feeder distributions narrow. Visible to users via the rationale string update; not a correctness issue but the guide flags this so hotel users understand why a slot's badge can change.
- **Bracket coverage gap.** `knowledge/bracket_2026.yaml` today defines only the 7 IHG-relevant knockout slots. To compute feeder distributions for the remaining 25 knockout slots, the implementation plan must decide whether to expand `bracket_2026.yaml` to all 32 slots (more accurate TBD popularity) or fall back to phase-only popularity for slots not in the bracket file (simpler, no simulation extension). Default in this design is the latter; the plan can revisit.