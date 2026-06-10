> **Historical record.** This document captures the IHG ticket-portfolio scope
> (11 matches, demand tier, F&B suggestions, owner-invitation framing). That
> scope was superseded on 2026-06-01 by the public-tournament reframe.
> See `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`
> for the active design.

# IHG World Cup 2026 Match Intelligence Site — Design

**Date:** 2026-05-08
**Status:** Approved
**Audience:** IHG senior leadership and hotel owners (external franchisees)
**Deliverable:** Dynamic HTML site hosted on GitHub Pages, refreshed automatically by a scheduled GitHub Action

---

## 1. Purpose and scope

IHG holds tickets to 11 matches at the FIFA World Cup 2026 across Atlanta, NY/NJ, and Miami. Four are confirmed fixtures. Seven are knockout-stage slots whose participating teams are not known until shortly before kickoff. Hospitality leaders need lead time to make invitation decisions and to prepare properties for guests with very different cultural and operational profiles.

The site solves two problems:

1. **For senior leadership** (Jolie, Erin, the strategy team) — surface the most likely matchups in advance, with honest confidence grading, so invitation decisions to hotel owners can be made with enough lead time.
2. **For hotel property owners and GMs** — convert team intelligence into operational readiness: F&B preparation, language staffing, rate strategy, and dining-hour adjustments tailored to who is actually traveling to each match.

The site is **dynamic**: it reads from a JSON file produced by an automated backend that runs on a cron schedule throughout the 39-day tournament. Stakeholders leave the page open and updates land in place.

The site is **defensible**: every probability and confidence label is a deterministic function of public inputs (The Odds API + the official 2026 bracket structure). LLM-generated content is restricted to qualitative briefs and prep recommendations, all reasoning over a curated knowledge file in the repo.

The site is **bounded**: 11 matches, three host cities, six-week tournament window. No general-purpose sports analytics ambitions.

## 2. Architecture

```
GitHub repo (private)
├── site/         static frontend served by GitHub Pages
│   └── data/matches.json    single source of truth
├── knowledge/    curated team profiles, diaspora data, bracket structure
├── backend/      Python: refresh script, agents, bracket logic
└── .github/workflows/refresh.yml    scheduled refresh

Scheduled GitHub Action runs every 30 min (group stage) or 15 min
(knockouts):

  1. Pull current odds (The Odds API, key in repo secret)
  2. Apply 2026 bracket logic → per-feeder team distributions and top-3 matchups per TBD slot
  3. Compute deltas vs. previous matches.json
  4. For each match whose signature has materially changed:
       a. briefing-agent  → narrative intelligence brief
       b. prep-advisor    → property prep checklist (incl. F&B suggestions)
  5. Write matches.json + commit + push
  6. GitHub Pages auto-redeploys

Frontend: fetches matches.json on load, polls every 60s for updates,
renders 11 chronological match tiles. No backend calls from the browser.
No secrets in client code.
```

**Properties:**

- Zero servers to manage. The "backend" is a GitHub Action.
- Odds API key and Anthropic API key live in repo secrets, never reach the browser.
- The site is fully static — frontend only reads JSON.
- Agents run only when a match's *signature* (defined below) has materially changed. In the steady state, almost every refresh regenerates zero briefs. Cost is bounded.
- Single source of truth: `matches.json`. No database, no external state.

## 3. Data model: `matches.json`

`matches.json` is the contract between every part of the system. The backend writes it; the frontend reads it; agents emit fragments of it.

Top-level fields:

- `generated_at` — ISO-8601 UTC timestamp of when this file was written.
- `data_freshness` — `"fresh" | "stale" | "unreachable"`. Drives the header status dot.
- `tournament_phase` — `"pre_tournament" | "group_stage" | "round_of_32" | "round_of_16" | "quarter_finals" | "semi_finals" | "finals"`.
- `matches` — array of exactly 11 match objects, chronologically ordered.

Each match object:

```json
{
  "id": "atl-2026-03-31-usa-por",
  "kickoff_utc": "2026-03-31T16:00:00Z",
  "kickoff_local": "2026-03-31T12:00:00-04:00",
  "host_city": "Atlanta",
  "venue": "Mercedes-Benz Stadium",
  "phase": "friendly | group_stage | round_of_32 | round_of_16 | quarter_final | semi_final | bronze_final | final",
  "status": "confirmed | tbd",
  "tickets": { "suite": 10, "stadium": 0, "split_with": "Etherio | null", "club": "Champion Club Plus | null" },
  "demand_tier": "high | medium | low | tbd",
  "confidence": "certain | high | medium | low",

  "teams": {
    "confirmed": [ /* exactly 2 entries, populated when status=confirmed; null otherwise */ ],
    "tbd_scenarios": [ /* exactly 3 entries, populated when status=tbd; null otherwise */ ],
    "feeder_distributions": [ /* array of feeder distributions, or null for SF/Bronze; present when status=tbd */ ]
  },

  "signature": "v1:...",

  "brief": {
    "headline": "...",
    "scenario_summary": "... (TBD only; null for confirmed)",
    "fan_demographics": "...",
    "traveling_volume_est": "...",
    "cultural_context": "...",
    "demand_rationale": "..."
  },
  "prep": {
    "fnb": {
      "suggestions": [
        { "dish": "...", "meal_period": "...", "rationale": "..." }
      ],
      "requirements": ["..."],
      "operational_notes": ["..."]
    },
    "language": ["..."],
    "rate_strategy": "...",
    "logistics": ["..."],
    "owner_invitation_note": "one sentence the strategy team can paste verbatim into an invitation email"
  },

  "decision_date": "YYYY-MM-DD | null",
  "days_to_decision": 0
}
```

**`status` is a strict either/or:** `teams.confirmed` is populated only when status is `confirmed`; `teams.tbd_scenarios` is populated only when status is `tbd`. Never both, never neither.

**`brief` and `prep` are always present**, even for TBD matches — the briefing agent writes them in scenario-aware language ("if Mexico advances as expected…"). When the matchup is officially confirmed, the agent rewrites them in confirmed-fixture language.

**`feeder_distributions` is the primary signal for who could plausibly play this match.** For each feeder of the slot (e.g., "Group A winner" and "Group F runner-up"), it carries a labeled distribution over the teams that could fill that role with their probabilities. This is more informationally dense than the cross-product `tbd_scenarios` for leadership scanning — it answers "which teams could be at this match in any scenario" directly, rather than enumerating specific pairings. For SF and Bronze slots that use the uniform-from-32-pool approximation, `feeder_distributions` is `null` and the UI falls back to the cross-product top-3.

**`tbd_scenarios` is always exactly 3 entries** when populated — supporting detail rather than primary signal. Each scenario:

```json
{
  "rank": 1,
  "team_a": { "code": "MEX", "name": "Mexico" },
  "team_b": { "code": "JPN", "name": "Japan" },
  "probability": 0.34,
  "delta_pp": 2.1,
  "rationale": "Group A winner vs Group F runner-up; Mexico's win probability in Group A is currently…"
}
```

The three probabilities will not sum to 100% — the long tail of less-likely scenarios is honestly surfaced in the UI as "+others (~X% combined)."

**The `signature` field is the regeneration trigger.** It is stored in `matches.json` itself (no sidecar, no database). On each refresh, the backend recomputes the signature from the new state and compares to the stored value:

- For confirmed matches: `v1:confirmed:{team_a_code}-{team_b_code}`. Stable for the whole tournament after first generation.
- For TBD matches: `v1:tbd:top1={A_code}-{B_code}:bucket={N}-{N+5}:set={5_team_codes_sorted}:conf={tier}`. Where `bucket` is the leading scenario's probability rounded down to the nearest 5pp.

The agents are called for a match only when its signature changes (or its `brief` / `prep` are missing entirely, e.g. first run).

## 4. Deterministic backend pipeline

This is everything the cron-fired script does *before* any LLM is invoked.

**Module layout under `backend/`:**

- `refresh.py` — entrypoint called by the GitHub Action.
- `odds_client.py` — The Odds API wrapper, with retries, backoff, and a circuit breaker.
- `bracket.py` — pure functions over the official 2026 World Cup bracket structure.
- `groups.py` — closed-form group-stage placement probabilities from match-winner odds.
- `bracket_simulation.py` — bracket-wide Monte Carlo for slots fed by R32+ winners.
- `probabilities.py` — per-feeder team distributions and top-3 cross-product matchup ranking per TBD slot.
- `signature.py` — compute and diff signatures.
- `inventory.py` — loads `knowledge/ticket_inventory.yaml`.
- `knowledge.py` — loads `knowledge/teams.yaml` and `knowledge/cities.yaml`.
- `writer.py` — serializes `matches.json`, commits, and pushes.
- `agents/briefing.py`, `agents/prep.py`, `agents/client.py` — the LLM layer.
- `tests/` — pytest suite.

**One refresh run, in order:**

1. **`inventory.load()`** — read `knowledge/ticket_inventory.yaml`. Hand-authored, rarely changes.
2. **`odds_client.fetch()`** — single call to The Odds API for the World Cup market. Returns per-match win probabilities and (where available) group-standing futures.
3. **`bracket.resolve_tbd_slots()`** — for each TBD match, return its structural feeders (e.g., `R32-Slot-3 = winner(Group_A) × runner-up(Group_F)`). Hardcoded from FIFA's published bracket.
4. **`groups.derive_group_probs` + `bracket_simulation.simulate_bracket` + `probabilities.compute_top5_for_slot`** — derive closed-form group placement probabilities from match-winner odds, run a 10k-iteration bracket Monte Carlo for slots fed by R32+ winners, and rank the top-3 cross-product matchups per TBD slot. Each slot also gets per-feeder team distributions (the primary scenario display per Section 3). Returns probabilities and deltas vs. the previous run.
5. **`confidence.grade(slot, days_to_decision, groups_resolved)`** — deterministic rule mapping phase + days-to-decision + group resolution status to `low | medium | high`. Semi-finals are graded `low` until very close to their decision date.
6. **`signature.compute(match_state)`** — produce the signature string per Section 3.
7. **`signature.diff(new, old)`** — return the list of match IDs whose signature changed.
8. **For each changed match ID:** call `agents.briefing.run(...)` then `agents.prep.run(...)`.
9. **`writer.write_and_commit()`** — write `site/data/matches.json`, commit only if changed (with a structured message), push.

**Key properties:**

- No LLM is involved in steps 1–7. Every probability and confidence label is a deterministic function of two public inputs.
- Top-5 probabilities do not sum to 100%. The residual is surfaced honestly.
- Idempotent: two consecutive runs with no upstream change result in zero agent calls and zero commits.
- Failure modes:
  - Odds API failures: exponential backoff with three retries; if three *consecutive runs* fail, write `data_freshness: "unreachable"` to `matches.json` (and commit it) so the UI flips to red.
  - Anthropic API failures during agent calls: keep the previous brief/prep, log the error, do not fail the run.

**Static knowledge files** (`knowledge/`):

- `ticket_inventory.yaml` — the 11 IHG matches with kickoff, venue, ticket counts, demand tier (where pre-known).
- `bracket_2026.yaml` — official 2026 World Cup bracket structure and phase date ranges.
- `teams.yaml` — one entry per team that could appear (~33 teams: 8 confirmed-match teams + ~25 realistic knockout participants).
- `cities.yaml` — host-city / property context for ATL, NJ, MIA.

`teams.yaml` schema includes the F&B-relevant fields needed by the prep agent:

```yaml
MEX:
  name: Mexico
  fifa_rank: 12
  us_diaspora:
    population_millions: 37.2
    primary_concentrations: [California, Texas, Illinois, Arizona]
    georgia_concentration: moderate
  fan_culture:
    travel_propensity: very_high
    color_signal: green
    notable_traditions: ["large group bookings", "multi-generational travel"]
  hospitality_notes:
    fnb_priorities: ["late dining", "tequila/mezcal program", "Spanish menus"]
    language: ["Spanish-speaking front desk and concierge essential"]
    dietary: standard
    rate_signal: "premium suite demand consistently strong; price aggressively"
  cuisine_signatures:
    - { dish: "Regional taco bar (al pastor, barbacoa, lengua)", note: "Avoid generic 'Tex-Mex'; signal regional authenticity" }
    - { dish: "Mezcal/tequila flight pairings", note: "Premium spirits program lifts suite spend" }
  diaspora_travel_signal:
    origin_pattern: "Western US (CA, TX, AZ) heavy; multi-generational group bookings common"
    dining_pattern: "Late dinners, large parties, family-style preferred"
  recent_form_summary: "Brief one-paragraph summary; updated by hand if material."
```

A top-of-file comment block in `teams.yaml` cites sources (US Census Bureau tables, FIFA rankings page, etc.).

## 5. The two agents

Both agents target **Claude Sonnet 4.6** via the Anthropic SDK, both use prompt caching on the curated knowledge prefix, and both return structured JSON validated against the schema fragments in Section 3 before being written to `matches.json`.

**Knowledge sourcing rule:**

- **Quantitative claims must come from `teams.yaml`** — diaspora population, FIFA rank, demand tier, language requirements. These are the lines owners may fact-check.
- **Qualitative color may use training knowledge** — recent form, fan culture nuance, traveling temperament, regional dish traditions. Agents are instructed to *prefer* curated data and *never contradict* it.

This split gives richer briefs without losing defensibility on the numbers.

### 5.1 Briefing agent (`agents/briefing.py`)

**Inputs:**

- The match state (kickoff, venue, phase, status, per-feeder team distributions and top-3 cross-product scenarios *or* confirmed teams).
- The relevant team entries from `teams.yaml`.
- The relevant city entry from `cities.yaml`.
- The IHG ticket inventory line for this match.

**Prompt structure** (cache-aware):

- Cached prefix (~5–10K tokens, reused across all matches in a refresh): system role, defensibility rules, output JSON schema, tone guidelines, full `teams.yaml`, full `cities.yaml`, inventory context.
- Variable suffix (per match): this match's state and the teams or scenarios in play; instruction to produce the brief as JSON.

**Output:** JSON object matching the `brief` sub-schema. Validated with Pydantic; one retry on schema failure; on second failure, log error and keep the previous brief. Never write garbage to `matches.json`.

### 5.2 Prep advisor agent (`agents/prep.py`)

**Inputs:**

- The brief just produced by the briefing agent.
- The same team entries from `teams.yaml` (so it sees `hospitality_notes`, `cuisine_signatures`, and `diaspora_travel_signal` directly).
- The host city / property context from `cities.yaml`.
- The demand tier (deterministically set in inventory).

**Output:** JSON matching the `prep` sub-schema:

- `fnb.suggestions` — concrete dishes with `meal_period` and `rationale`. The agent is explicitly told to ground each suggestion in *who is traveling and from where* (the diaspora data) and to give the GM a one-line rationale they can repeat to their F&B director.
- `fnb.requirements` — non-negotiable operational requirements (e.g., "Halal certification on all shared protein lines").
- `fnb.operational_notes` — practical kitchen / service adjustments.
- `language` — concierge and front-desk language requirements.
- `rate_strategy` — pricing posture for this match.
- `logistics` — transport, late-dining, group-booking notes.
- `owner_invitation_note` — one sentence the strategy team can paste verbatim into an owner invitation email.

### 5.3 Why two agents, not one

- **Iteration:** prep recommendations can be tuned without disturbing the brief.
- **Defensibility:** the prep advisor is the more sensitive output (owners actually act on it). A focused single-purpose prompt is easier to evaluate and adjust.

### 5.4 Cost ceiling

Maximum ~14 agent calls per refresh in the worst case (7 TBD matches × 2 agents). At ~8K cached input tokens and ~1K output tokens per call, well under $1 per fully-saturated refresh. Most refreshes will regenerate zero briefs. Estimated total Anthropic spend across the full 39-day tournament: under $20.

## 6. Frontend

Static HTML/CSS/JS, no framework. TypeScript source in `src/`, bundled via `esbuild` to `site/assets/app.js`. Files in `site/` are what GitHub Pages serves.

**Visual register: modern football tracker.** Reference aesthetic: FotMob, Onefootball, ESPN match center. Country flags as primary visual anchors; animated probability bars; bracket fragments where they belong; urgency cues for decision dates. Light IHG brand cues only — IHG accent color, IHG wordmark in the header, IHG-style footer. Otherwise neutral, polished, serious.

**Components:**

1. **Header status bar** — IHG wordmark, title, live status dot driven by `data_freshness` and a wall-clock staleness check (green = fresh, amber = stale, red = unreachable).
2. **Tournament timeline strip** — horizontal date axis Mar 31 → Jul 18 with one marker per match. Solid markers for confirmed, ringed markers for TBD; marker color encodes demand tier. Click a marker to scroll to that match's tile.
3. **"Next up" hero card** — the match closest to kickoff gets a hero treatment with full team flags, FIFA ranks, kickoff countdown, venue, demand call, and the brief headline. Auto-cycles to the next match once kickoff passes.
4. **Confirmed-match tile** — large flags, "TEAM A vs TEAM B" headline typography, FIFA ranks under each crest, kickoff and venue, ticket allocation, and a row of small **prep flag chips** (e.g., `⚑ Halal F&B`, `Français`, `Late dining`, `Premium rates`) so leadership sees the operational read at a glance without expanding.
5. **TBD-match tile (the centerpiece component)** — date and slot context at top ("Group A winner × Group F runner-up — Round of 32"), then the **per-feeder team distributions as horizontal probability bars** showing which teams could fill each feeder slot (e.g., "Group A winner: Mexico 64%, Czech Republic 14%..."). Below that, a smaller "Most-likely specific matchups" subsection shows the top-3 cross-product scenarios with country flags, codes, percentages, and delta arrows (shown when |delta| ≥ 3pp). For SF and Bronze slots that use the uniform-pool approximation, the per-feeder distributions are omitted and the cross-product top-3 is the primary scenario display, with confidence honestly graded "low." Decision-date countdown badge in the top-right that turns amber at T-3 and red at T-1.
6. **Bracket fragment** (inside expanded detail panel for TBD matches) — small SVG bracket showing the slot in question, with feeder lines from relevant groups or earlier rounds.
7. **Expanded detail panel** (inline expansion under the tile, not a modal) — brief headline + named sub-fields, full per-feeder team distributions and top-3 cross-product scenarios with rationale strings, prep section (F&B suggestions table, language, rate strategy, logistics, owner invitation note in a quote-style block), bracket fragment for TBDs.
8. **Filters** — city, status, phase. Narrows the visible tiles.
9. **Footer** — IHG sign-off, last data refresh timestamp, link to "How probabilities are computed" methodology page (auto-generated from the bracket logic + odds source notes).

**Visual language:**

- Country flags from a bundled SVG set (twemoji-country-flags or flag-icons), not loaded externally.
- Probability bars use a single accent color (an IHG blue) at varying widths — length = probability.
- Delta arrows: green up, red down, only shown when |delta| ≥ 3pp.
- Demand tier: labeled chip with icon, never color alone (colorblind-safe).
- Decision-date countdown: large numerals in a pill that transitions neutral → amber at T-3 → red at T-1 → "DECIDED" once locked.
- Typography: one display face for headlines, one body sans, generous line height.

**Animation, sparingly:**

- Probability bars animate width on update (200ms ease-out).
- Delta arrows pulse briefly on appearance.
- Tiles fade in on initial load, staggered by 30ms.

**Live updating:** the page polls `matches.json` every 60 seconds with `cache: "no-cache"`. If `generated_at` changed, the JS diff-renders only the tiles that changed (an open expanded panel does not collapse if its content was unchanged).

**Mobile:** timeline strip becomes vertical; tiles stack full-width; probability bars stay horizontal.

**No JS framework, no auth, no analytics, no cookies.** Single HTML, one CSS, one JS bundle, ~30 flag SVGs, one JSON fetch.

**Performance budget:** total payload under 250KB. No external webfonts. One self-hosted display face if needed.

**Deep linking:** expanding a tile updates the URL hash to `#match=<id>` so leadership can email a link to a specific match.

**Accessibility baseline:** semantic HTML, color-blind-safe demand-tier indicators (icon + label, not color alone), keyboard-navigable tiles, sufficient contrast.

## 7. GitHub Actions, secrets, and bootstrap

### 7.1 Repository layout

```
world-cup-intelligence-site/
  site/                      published by GitHub Pages
    index.html
    assets/
      styles.css
      app.js                 bundled output
      flags/                 bundled SVG flag set
    data/
      matches.json           committed by the refresh action
  src/                       frontend source (esbuild input)
    main.ts
    components/...
  backend/
    refresh.py
    odds_client.py
    bracket.py
    probabilities.py
    signature.py
    inventory.py
    knowledge.py
    writer.py
    agents/
      briefing.py
      prep.py
      client.py
    tests/
  knowledge/
    teams.yaml
    cities.yaml
    ticket_inventory.yaml
    bracket_2026.yaml
  .github/
    workflows/
      refresh.yml
      build-frontend.yml
      ci.yml
  pyproject.toml             uv-managed Python deps
  package.json               esbuild + tsc only
  README.md
```

### 7.2 Secrets

Two repository-scoped secrets:

- **`ODDS_API_KEY`** — paid Odds API tier ($30/mo, 20K req). Masked in workflow logs.
- **`ANTHROPIC_API_KEY`** — Sonnet 4.6 calls.

`GITHUB_TOKEN` for repo writes is provided automatically by Actions.

### 7.3 Workflow: `refresh.yml`

- **Trigger:** two cron schedules — `*/30 * * * *` (group stage default) and `*/15 * * * *` (knockout boost). Plus `workflow_dispatch` for manual runs.
- **Phase gating:** the script reads tournament phase from `bracket_2026.yaml` and early-exits when the current cadence does not match the active phase. So during group stage the 15-min cron fires but exits in <2 seconds, and during knockouts the 30-min cron fires but exits in <2 seconds.
- **Concurrency:** `concurrency: { group: refresh, cancel-in-progress: false }`.
- **Steps:** checkout → set up Python via `uv` → run `python -m backend.refresh` → if `matches.json` changed, configure bot identity, commit, push.
- **Manual trigger:** `workflow_dispatch` accepts an optional input to force-regenerate a specific match by ID.

### 7.4 Workflow: `build-frontend.yml`

- **Trigger:** push to `main` touching `src/**`, `package.json`, or `package-lock.json`.
- **Steps:** install Node deps → `tsc --noEmit` → `esbuild` → copy bundled output and assets into `site/assets/` → commit back to `main` with `[skip ci]`.
- **Scope:** only writes `site/index.html` and `site/assets/*`. Never touches `site/data/`.

The two writers (refresh and build-frontend) have disjoint write scopes, so practical merge conflicts do not arise.

### 7.5 Workflow: `ci.yml`

- **Trigger:** every PR.
- **Python:** `pytest backend/tests/`, `ruff`, `mypy`.
- **Frontend:** `tsc --noEmit`, `eslint`, a Playwright smoke test that loads built `site/index.html` against a fixture `matches.json` and asserts the timeline + tiles render.
- **Schema:** validate `knowledge/*.yaml` and a fixture `matches.json` against the JSON Schema in `backend/schema.py`.

### 7.6 Bootstrap path

1. Initialize git repo locally; push to a private GitHub repo (paid plan).
2. Add the two secrets in repo settings.
3. Enable GitHub Pages: Settings → Pages → "Deploy from a branch" → `main` / `/site`.
4. Author `knowledge/ticket_inventory.yaml` (the 11 matches — transcription from this spec).
5. Author `knowledge/bracket_2026.yaml` (official 2026 bracket).
6. Author `knowledge/teams.yaml` for the 8 confirmed-match teams first, then ~25 realistic knockout participants.
7. Author `knowledge/cities.yaml` for ATL, NJ, MIA.
8. Build `backend/refresh.py` end-to-end against a canned Odds API fixture. Get a valid `matches.json` writing.
9. Build the two agents against the same fixture. Validate outputs.
10. Build the frontend against the seeded `matches.json`. Confirm the layout from Section 6 renders.
11. Wire in the real Odds API. Run `refresh.py` once locally. Confirm output.
12. Push to GitHub. Manual-dispatch the refresh workflow. Watch it commit `matches.json`.
13. Wait for the cron to fire. Confirm a no-op exit when nothing has changed.
14. Hand the URL to leadership.

### 7.7 Cost ceiling, all-in

- **GitHub Actions:** ~720 min/month worst case, well under the 3000 free minutes on a paid plan.
- **The Odds API:** paid tier confirmed, $30/mo, 20K req — comfortably covers 30-min/15-min cadence for 39 days.
- **Anthropic (Sonnet 4.6 with caching):** under $20 across the full tournament given signature-gated regeneration.

## 8. Defensibility properties

Recapping the design choices that make every line on the site defensible to an external owner audience:

- All probabilities and confidence labels are deterministic functions of two public inputs: The Odds API and the static 2026 bracket structure.
- Top-5 probabilities do not sum to 100%; the long-tail residual is surfaced honestly.
- Confidence is graded explicitly (`low` for early-tournament knockouts, `high` near decision date with groups resolved). Stakeholders see uncertainty rather than false precision.
- Quantitative claims in agent-generated briefs (diaspora numbers, FIFA ranks, demand tiers) come from the curated `teams.yaml` and are auditable via git history.
- Qualitative claims (cultural color, fan temperament) may use the model's training knowledge but are instructed to never contradict the curated file.
- Failure modes are honest: Odds API outages flip the UI to red; agent failures preserve the previous brief rather than degrading content.
- Every refresh is a git commit with a structured message — full audit trail of when content changed and what changed.

## 9. Out of scope for v1

Explicitly deferred to a possible v2:

- Live "ask a question about this matchup" chat agent on each match tile.
- Tool-using research agents that pull live news/Wikipedia at refresh time.
- Per-property hotel manager logins or owner-specific filtered views.
- Email/Slack notifications when signatures change.
- Printable PDF brief export.
- Multi-tenant template for other tentpole events (Olympics, Super Bowl, etc.).
- Live in-match score tickers or post-match recaps.
- Group-stage standings tables.
