# Plan B — Frontend Refactor (Lite/Full Tiles, Popularity Badges, Drop Tickets/F&B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prereq:** Plan A merged or on `main`. The JSON consumed by the frontend now has `popularity` instead of `demand_tier`, no `tickets`, no `fnb`, no `owner_invitation_note`, no `demand_rationale`.

**Goal:** Update TypeScript types and every UI component to consume the new JSON shape. Introduce two render modes per tile (Lite = no expand for moderate/standard; Full = expand for popular). Replace the demand filter with popularity + a phase filter. Drop all ticket and F&B rendering.

**Architecture:**
- `src/types.ts` is the contract; update it first, let the TypeScript compiler drive the component fixes.
- Tile components (`confirmedTile.ts`, `tbdTile.ts`) branch on `match.popularity.tier`. Lite mode skips the expand button.
- `expandedDetail.ts` drops the F&B section and the owner-invitation blockquote; renames the rationale heading.
- `hero.ts` uses popularity instead of demand to label the tag.
- `timeline.ts` uses `popularity.tier` for color encoding (same CSS slots as before, just renamed).
- `filters.ts` swaps the "status" filter for a "popularity" filter; the existing "phase" filter stays.
- `header.ts` adds a Guide link.

**Tech Stack:** TypeScript, esbuild, vitest, tsc, vanilla DOM templating.

**Spec:** `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`.

---

## Pre-flight

- [ ] **Step 0.1: Sync and branch**

```bash
git fetch origin
git checkout main
git pull --rebase origin main
git checkout -b feat/frontend-popularity-and-lite-tiles
npm install
```

- [ ] **Step 0.2: Verify clean baseline**

```bash
npm run typecheck
npm test -- --run
```

Expected: typecheck fails because `matches.json` shape moved; tests likely fail too. That's the starting point.

---

## Task 1: Types

**Files:**
- Modify: `src/types.ts`

- [ ] **Step 1.1: Update `src/types.ts`**

Delete:

```ts
export type DemandTier = "high" | "medium" | "low" | "tbd";
export type HostCity = "Atlanta" | "NY/NJ" | "Miami";

export interface Tickets {
  suite: number;
  stadium: number;
  split_with: string | null;
  club: string | null;
}

export interface PrepFnBSuggestion { ... }
export interface PrepFnB { ... }
```

Add:

```ts
export type PopularityTier = "popular" | "moderate" | "standard";
export type HostCity = string;

export interface Popularity {
  tier: PopularityTier;
  rationale: string;
}
```

Update `Brief` — drop `demand_rationale`:

```ts
export interface Brief {
  headline: string;
  scenario_summary: string | null;
  fan_demographics: string;
  traveling_volume_est: string;
  cultural_context: string;
}
```

Update `Prep` — drop `fnb` and `owner_invitation_note`:

```ts
export interface Prep {
  language: string[];
  rate_strategy: string;
  logistics: string[];
}
```

Update `MatchObject` — drop `tickets` and `demand_tier`, add `popularity`:

```ts
export interface MatchObject {
  id: string;
  kickoff_utc: string;
  kickoff_local: string;
  host_city: HostCity;
  venue: string;
  phase: Phase;
  status: Status;
  popularity: Popularity;
  confidence: Confidence;
  teams: TeamsBlock;
  signature: string;
  brief: Brief | null;
  prep: Prep | null;
  decision_date: string | null;
  days_to_decision: number | null;
}
```

- [ ] **Step 1.2: Commit**

```bash
git add src/types.ts
git commit -m "feat(types): drop tickets/demand_tier/fnb/owner_note; add popularity"
```

---

## Task 2: confirmedTile — lite/full branch, popularity badge

**Files:**
- Modify: `src/components/confirmedTile.ts`

- [ ] **Step 2.1: Rewrite the file**

Replace `src/components/confirmedTile.ts` with:

```ts
import type { ConfirmedTeam, MatchObject } from "../types.js";
import { flagPath, flagAltText } from "../utils/flags.js";
import { escapeHtml } from "../utils/escape.js";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function shortDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  const month = MONTHS[parseInt(m[2], 10) - 1];
  const day = parseInt(m[3], 10);
  const h24 = parseInt(m[4], 10);
  const mm = m[5];
  const ampm = h24 >= 12 ? "pm" : "am";
  const h12 = ((h24 + 11) % 12) + 1;
  return `${month} ${day} · ${h12}:${mm}${ampm}`;
}

const POPULARITY_LABEL = {
  popular: "Popular",
  moderate: "Moderate",
  standard: "Standard",
} as const;

export function renderConfirmedTile(match: MatchObject): string {
  if (match.teams.confirmed === null || match.teams.confirmed.length !== 2) {
    return `<div class="match-tile error">invalid confirmed match: ${match.id}</div>`;
  }
  const [a, b] = match.teams.confirmed;
  const tier = match.popularity.tier;
  const tierLabel = POPULARITY_LABEL[tier];
  const isFull = tier === "popular";

  return `
    <article class="match-tile confirmed-tile popularity-${tier}"
             id="match-${match.id}" data-signature="${match.signature}"
             aria-expanded="false">
      <header class="tile-strip">
        <span class="tile-strip-left">
          <span>${escapeHtml(shortDate(match.kickoff_local))}</span>
          <span class="sep">/</span>
          <span>${escapeHtml(match.host_city)}</span>
          <span class="sep">/</span>
          <span class="phase">${escapeHtml(phaseLabel(match.phase))}</span>
        </span>
        <span class="tile-strip-right">
          <span class="popularity popularity-badge-${tier}"
                title="${escapeHtml(match.popularity.rationale)}">
            ${escapeHtml(tierLabel)}
          </span>
        </span>
      </header>
      <div class="tile-body">
        ${teamBlock(a, "left")}
        <span class="vs-glyph">vs</span>
        ${teamBlock(b, "right")}
      </div>
      <div class="popularity-why">${escapeHtml(match.popularity.rationale)}</div>
      <footer class="tile-foot">
        <span class="tile-foot-meta">
          <span class="venue">${escapeHtml(match.venue)}</span>
        </span>
        ${isFull ? expandButton(match.id) : ""}
      </footer>
    </article>
  `;
}

function expandButton(id: string): string {
  return `
    <button type="button" class="tile-expand"
            aria-controls="match-${id}"
            data-expand-for="${id}">
      <span class="tile-expand-label" data-collapsed>View brief &amp; prep</span>
      <span class="tile-expand-label" data-expanded>Hide brief</span>
      <svg class="tile-expand-chevron" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  `;
}

function teamBlock(t: ConfirmedTeam, side: "left" | "right"): string {
  return `
    <div class="team-block ${side}">
      <img class="team-flag" src="${flagPath(t.code)}" alt="${escapeHtml(flagAltText(t.code, t.name))}" />
      <div class="team-name">${escapeHtml(t.name)}</div>
      <div class="team-meta">
        <span class="rank">${escapeHtml(t.code)}</span> · FIFA #${t.fifa_rank}
      </div>
    </div>
  `;
}

function phaseLabel(phase: string): string {
  const map: Record<string, string> = {
    friendly: "Friendly",
    group_stage: "Group Stage",
    round_of_32: "Round of 32",
    round_of_16: "Round of 16",
    quarter_final: "Quarter Final",
    semi_final: "Semi Final",
    bronze_final: "Bronze Final",
    final: "Final",
  };
  return map[phase] ?? phase;
}
```

- [ ] **Step 2.2: Commit**

```bash
git add src/components/confirmedTile.ts
git commit -m "feat(ui): confirmed tile uses popularity tier; lite mode for non-popular"
```

---

## Task 3: tbdTile — lite/full branch, popularity badge

**Files:**
- Modify: `src/components/tbdTile.ts`

- [ ] **Step 3.1: Update the tile header and footer**

Open `src/components/tbdTile.ts`. Make three changes:

(a) Replace the `<span class="demand demand-tbd">TBD</span>` chip in the header with a popularity badge. Update the article opening tag's class list.

In `renderTbdTile`, replace this header block:

```ts
      <header class="tile-strip">
        <span class="tile-strip-left">
          <span>${escapeHtml(shortDate(match.kickoff_local))}</span>
          <span class="sep">/</span>
          <span>${escapeHtml(match.host_city)}</span>
          <span class="sep">/</span>
          <span class="phase">${escapeHtml(phaseLabel(match.phase))}</span>
        </span>
        <span class="tile-strip-right">
          <span class="demand demand-tbd">TBD</span>
        </span>
      </header>
```

with:

```ts
      <header class="tile-strip">
        <span class="tile-strip-left">
          <span>${escapeHtml(shortDate(match.kickoff_local))}</span>
          <span class="sep">/</span>
          <span>${escapeHtml(match.host_city)}</span>
          <span class="sep">/</span>
          <span class="phase">${escapeHtml(phaseLabel(match.phase))}</span>
        </span>
        <span class="tile-strip-right">
          <span class="popularity popularity-badge-${match.popularity.tier}"
                title="${escapeHtml(match.popularity.rationale)}">
            ${escapeHtml(popularityLabel(match.popularity.tier))}
          </span>
        </span>
      </header>
```

Update the article opening tag — change `class="match-tile tbd-tile"` to `class="match-tile tbd-tile popularity-${match.popularity.tier}"`.

(b) Conditional expand button. Wrap the existing `<button type="button" class="tile-expand" ...>` block in a ternary:

```ts
        ${match.popularity.tier === "popular" ? `
          <button type="button" class="tile-expand"
                  aria-controls="match-${match.id}"
                  data-expand-for="${match.id}">
            <span class="tile-expand-label" data-collapsed>View brief &amp; prep</span>
            <span class="tile-expand-label" data-expanded>Hide brief</span>
            <svg class="tile-expand-chevron" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        ` : ""}
```

(c) Add the helper at the bottom of the file:

```ts
function popularityLabel(tier: "popular" | "moderate" | "standard"): string {
  return { popular: "Popular", moderate: "Moderate", standard: "Standard" }[tier];
}
```

Also add a `<div class="popularity-why">${escapeHtml(match.popularity.rationale)}</div>` line right above the `<footer class="tile-foot">` opening, to match the confirmed tile.

- [ ] **Step 3.2: Commit**

```bash
git add src/components/tbdTile.ts
git commit -m "feat(ui): tbd tile uses popularity tier; lite mode for non-popular"
```

---

## Task 4: expandedDetail — drop F&B, drop owner note, rename rationale

**Files:**
- Modify: `src/components/expandedDetail.ts`

- [ ] **Step 4.1: Rewrite the file**

Replace `src/components/expandedDetail.ts` with:

```ts
import type { MatchObject } from "../types.js";
import { renderBracketFragment } from "./bracketFragment.js";
import { escapeHtml } from "../utils/escape.js";

export function renderExpandedDetail(match: MatchObject): string {
  return `
    <section class="expanded-detail">
      ${match.brief ? renderBrief(match.brief, match.popularity.rationale) : `<p class="expanded-empty">Brief not yet generated.</p>`}
      ${match.prep ? renderPrep(match.prep) : `<p class="expanded-empty">Prep recommendations not yet generated.</p>`}
      ${match.status === "tbd" ? renderBracketFragment(match) : ""}
    </section>
  `;
}

function renderBrief(brief: NonNullable<MatchObject["brief"]>, popularityRationale: string): string {
  return `
    <div class="brief">
      <header class="brief-header">
        <span class="brief-eyebrow">Section I</span>
        <h3 class="brief-headline">${escapeHtml(brief.headline)}</h3>
      </header>
      ${brief.scenario_summary ? `<div class="brief-section brief-summary"><h4>Scenario summary</h4><p>${escapeHtml(brief.scenario_summary)}</p></div>` : ""}
      <div class="brief-grid">
        <div class="brief-section"><h4>Fan demographics</h4><p>${escapeHtml(brief.fan_demographics)}</p></div>
        <div class="brief-section"><h4>Traveling volume</h4><p>${escapeHtml(brief.traveling_volume_est)}</p></div>
        <div class="brief-section"><h4>Cultural context</h4><p>${escapeHtml(brief.cultural_context)}</p></div>
        <div class="brief-section"><h4>Why this match is popular</h4><p>${escapeHtml(popularityRationale)}</p></div>
      </div>
    </div>
  `;
}

function renderPrep(prep: NonNullable<MatchObject["prep"]>): string {
  return `
    <div class="prep">
      <header class="prep-header">
        <span class="prep-eyebrow">Section II</span>
        <h3>Property preparation</h3>
      </header>
      <div class="prep-grid">
        <div class="prep-section"><h4>Language</h4><ul>${prep.language.map((l) => `<li>${escapeHtml(l)}</li>`).join("")}</ul></div>
        <div class="prep-section"><h4>Rate strategy</h4><p>${escapeHtml(prep.rate_strategy)}</p></div>
        <div class="prep-section"><h4>Logistics</h4><ul>${prep.logistics.map((l) => `<li>${escapeHtml(l)}</li>`).join("")}</ul></div>
      </div>
    </div>
  `;
}
```

- [ ] **Step 4.2: Commit**

```bash
git add src/components/expandedDetail.ts
git commit -m "feat(ui): expanded detail drops fnb and owner note; surface popularity rationale"
```

---

## Task 5: hero — popularity-based tag, drop demand label map

**Files:**
- Modify: `src/components/hero.ts`

- [ ] **Step 5.1: Update `renderHero`**

In `src/components/hero.ts`, replace the `demandLabel` map and the `tagText` line with:

```ts
  const tagText = match.status === "confirmed"
    ? popularityTag(match.popularity.tier)
    : `Decides in ${match.days_to_decision ?? "?"}d`;
```

Add at the bottom of the file:

```ts
function popularityTag(tier: "popular" | "moderate" | "standard"): string {
  return { popular: "Popular Match", moderate: "Moderate Interest", standard: "Standard" }[tier];
}
```

Update `pickNextUp` to prefer popular matches when ranking the hero candidate. After the existing `candidates.sort(...)` call, add:

```ts
  // Prefer the next popular match; if none in the candidate window, fall back to the next any-tier match.
  const popular = candidates.find((m) => m.popularity.tier === "popular");
  return popular ?? candidates[0];
```

Replace the existing `return candidates[0];` with the two lines above (so we read `popular` first).

- [ ] **Step 5.2: Commit**

```bash
git add src/components/hero.ts
git commit -m "feat(ui): hero prefers next popular match; popularity-based tag"
```

---

## Task 6: timeline — popularity color encoding, drop demand_tier

**Files:**
- Modify: `src/components/timeline.ts`

- [ ] **Step 6.1: Update marker class generation**

In `src/components/timeline.ts`, replace:

```ts
    const tierClass = `tier-${m.demand_tier}`;
```

with:

```ts
    const tierClass = `popularity-${m.popularity.tier}`;
```

Update the `total / confirmed / tbd` counter header — change the literal "allocations" label to "matches" since we no longer hold any IHG inventory. Replace:

```ts
      <div class="tl-allocations">
        <span class="tl-alloc-total">${total} <em>allocations</em></span>
        <span class="tl-alloc-detail">${confirmedCount} confirmed · ${tbdCount} TBD${
          upcoming
            ? ` · next in <strong>${nextDays}d</strong>`
            : ""
        }</span>
      </div>
```

with:

```ts
      <div class="tl-allocations">
        <span class="tl-alloc-total">${total} <em>matches</em></span>
        <span class="tl-alloc-detail">${confirmedCount} confirmed · ${tbdCount} TBD${
          upcoming
            ? ` · next in <strong>${nextDays}d</strong>`
            : ""
        }</span>
      </div>
```

- [ ] **Step 6.2: Commit**

```bash
git add src/components/timeline.ts
git commit -m "feat(ui): timeline marker colors keyed on popularity tier; rename allocations→matches"
```

---

## Task 7: filters — popularity filter + keep phase, broaden city options

**Files:**
- Modify: `src/components/filters.ts`

- [ ] **Step 7.1: Replace the demand filter with popularity, broaden cities**

Replace `src/components/filters.ts` with:

```ts
import type { MatchObject } from "../types.js";

export interface FilterState {
  city: string | "all";
  popularity: "popular" | "moderate" | "standard" | "all";
  phase: string | "all";
}

export const DEFAULT_FILTERS: FilterState = { city: "all", popularity: "all", phase: "all" };

export function renderFilters(state: FilterState, totalMatches: number, visibleMatches: number, cities: string[]): string {
  const countLabel = visibleMatches === totalMatches
    ? `All ${totalMatches} matches`
    : `${visibleMatches} of ${totalMatches} matches`;
  return `
    <div class="filters">
      <div class="filters-heading">
        <span class="filters-eyebrow">Filter the match list</span>
        <span class="filters-count">${countLabel}</span>
      </div>
      <div class="filters-controls">
        <label>City
          <select data-filter="city">
            ${cityOptions(state.city, cities)}
          </select>
        </label>
        <label>Popularity
          <select data-filter="popularity">
            <option value="all"${state.popularity === "all" ? " selected" : ""}>All</option>
            <option value="popular"${state.popularity === "popular" ? " selected" : ""}>Popular</option>
            <option value="moderate"${state.popularity === "moderate" ? " selected" : ""}>Moderate</option>
            <option value="standard"${state.popularity === "standard" ? " selected" : ""}>Standard</option>
          </select>
        </label>
        <label>Phase
          <select data-filter="phase">
            ${phaseOptions(state.phase)}
          </select>
        </label>
      </div>
    </div>
  `;
}

function cityOptions(selected: string, cities: string[]): string {
  const opts = ["all", ...cities];
  return opts
    .map((c) => `<option value="${c}"${c === selected ? " selected" : ""}>${c === "all" ? "All cities" : c}</option>`)
    .join("");
}

function phaseOptions(selected: string): string {
  const phases = [
    "all",
    "group_stage",
    "round_of_32",
    "round_of_16",
    "quarter_final",
    "semi_final",
    "bronze_final",
    "final",
  ];
  return phases
    .map(
      (p) =>
        `<option value="${p}"${p === selected ? " selected" : ""}>${p === "all" ? "All phases" : p.replace(/_/g, " ")}</option>`,
    )
    .join("");
}

export function applyFilters(matches: MatchObject[], state: FilterState): MatchObject[] {
  return matches.filter((m) => {
    if (state.city !== "all" && m.host_city !== state.city) return false;
    if (state.popularity !== "all" && m.popularity.tier !== state.popularity) return false;
    if (state.phase !== "all" && m.phase !== state.phase) return false;
    return true;
  });
}

export function uniqueCities(matches: MatchObject[]): string[] {
  return Array.from(new Set(matches.map((m) => m.host_city))).sort();
}
```

- [ ] **Step 7.2: Update main.ts wiring**

In `src/main.ts`, two adjustments:

(a) Import `uniqueCities`:

```ts
import {
  DEFAULT_FILTERS,
  applyFilters,
  renderFilters,
  uniqueCities,
  type FilterState,
} from "./components/filters.js";
```

(b) Replace the `renderFiltersUI` function:

```ts
function renderFiltersUI(file: MatchesFile | null): void {
  const total = file?.matches.length ?? 0;
  const visible = file ? applyFilters(file.matches, filters).length : 0;
  const cities = file ? uniqueCities(file.matches) : [];
  document.getElementById("filters")!.innerHTML = renderFilters(filters, total, visible, cities);
}
```

(c) Update the filter change listener to handle `popularity` as a valid key:

```ts
    if (key === "city" || key === "popularity" || key === "phase") {
      filters = { ...filters, [key]: target.value };
```

Replace `if (key === "city" || key === "status" || key === "phase") {` with the above.

- [ ] **Step 7.3: Commit**

```bash
git add src/components/filters.ts src/main.ts
git commit -m "feat(ui): popularity filter replaces status; dynamic city list from matches"
```

---

## Task 8: header — Guide nav link

**Files:**
- Modify: `src/components/header.ts`

- [ ] **Step 8.1: Add the Guide link**

In `src/components/header.ts`, replace the middle `<div></div>` placeholder with a nav block:

```ts
    <div class="header-nav">
      <a class="header-nav-link" href="guide.html">Guide</a>
    </div>
```

- [ ] **Step 8.2: Commit**

```bash
git add src/components/header.ts
git commit -m "feat(ui): add Guide nav link to header"
```

---

## Task 9: CSS — popularity badge styles, lite-tile tweaks, alias migration

**Files:**
- Modify: `site/assets/styles.css`

- [ ] **Step 9.1: Search-and-replace demand classes**

In `site/assets/styles.css`:
- Find every selector starting with `.demand` and rename to `.popularity` with the equivalent tier name. Specifically:
  - `.demand-high` → `.popularity-badge-popular`
  - `.demand-medium` → `.popularity-badge-moderate`
  - `.demand-low` → `.popularity-badge-standard`
  - `.demand-tbd` → delete (no longer used)
  - `.demand` (the shared class) → `.popularity`
- Find every selector starting with `.tier-high|medium|low|tbd` (used by timeline + tiles) and rename:
  - `.tier-high` → `.popularity-popular`
  - `.tier-medium` → `.popularity-moderate`
  - `.tier-low` → `.popularity-standard`
  - `.tier-tbd` → delete
- Search for `.fnb-list`, `.fnb-dish`, `.fnb-period`, `.fnb-rationale`, `.fnb-more`, `.fnb-requirements`, `.fnb-notes`, `.prep-fnb`, `.owner-note*` and delete those rule blocks entirely.

- [ ] **Step 9.2: Add the popularity-why text block**

Append to `site/assets/styles.css`:

```css
.popularity-why {
  font-size: 0.78rem;
  color: var(--ihg-ink-muted, #5a6678);
  padding: 0.25rem 1rem 0.5rem;
  border-top: 1px dashed rgba(0,0,0,0.05);
}

/* Lite tile — no expand button, no expanded panel ever opens */
.match-tile.popularity-moderate .tile-foot,
.match-tile.popularity-standard .tile-foot {
  justify-content: flex-start;
}

/* Header nav */
.header-nav { display: flex; justify-content: center; }
.header-nav-link {
  color: inherit; text-decoration: none; font-size: 0.85rem;
  padding: 0.35rem 0.8rem; border: 1px solid currentColor; border-radius: 6px;
  opacity: 0.7;
}
.header-nav-link:hover { opacity: 1; }
```

- [ ] **Step 9.3: Commit**

```bash
git add site/assets/styles.css
git commit -m "feat(ui): popularity badge styles; drop demand/fnb/owner-note classes; lite-tile tweaks"
```

---

## Task 10: Frontend tests — types and tile rendering

**Files:**
- Modify: `src/tests/types.test.ts`
- Modify: `src/tests/diff.test.ts`
- Create: `src/tests/tiles.test.ts`

- [ ] **Step 10.1: Update `types.test.ts`**

Every fixture must use `popularity` instead of `demand_tier` and drop `tickets`. Replace any `demand_tier: "high"` with `popularity: { tier: "popular", rationale: "x" }`. Delete `tickets: {...}` lines.

- [ ] **Step 10.2: Update `diff.test.ts`**

Same fixture treatment. Add at least one assertion that a moderate-tier match in `next` triggers re-render when the `signature` changes (proving the lite tile still participates in diffing).

- [ ] **Step 10.3: Create `src/tests/tiles.test.ts`**

```ts
import { describe, expect, test } from "vitest";
import { renderConfirmedTile } from "../components/confirmedTile.js";
import type { MatchObject } from "../types.js";

function fixture(overrides: Partial<MatchObject> = {}): MatchObject {
  return {
    id: "atl-2026-06-18-rsa-cze",
    kickoff_utc: "2026-06-18T16:00:00Z",
    kickoff_local: "2026-06-18T12:00:00-04:00",
    host_city: "Atlanta",
    venue: "Mercedes-Benz Stadium",
    phase: "group_stage",
    status: "confirmed",
    popularity: { tier: "standard", rationale: "Group stage; teams outside top 25." },
    confidence: "certain",
    teams: {
      confirmed: [
        { code: "RSA", name: "South Africa", fifa_rank: 60 },
        { code: "CZE", name: "Czechia", fifa_rank: 41 },
      ],
      tbd_scenarios: null,
      feeder_distributions: null,
    },
    signature: "v2:confirmed:CZE-RSA",
    brief: null,
    prep: null,
    decision_date: null,
    days_to_decision: null,
    ...overrides,
  };
}

describe("renderConfirmedTile", () => {
  test("lite tile (standard) does not include expand button", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "standard", rationale: "x" } }));
    expect(html).not.toContain('class="tile-expand"');
    expect(html).toContain('class="popularity popularity-badge-standard"');
  });

  test("lite tile (moderate) does not include expand button", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "moderate", rationale: "x" } }));
    expect(html).not.toContain('class="tile-expand"');
    expect(html).toContain('class="popularity popularity-badge-moderate"');
  });

  test("full tile (popular) includes expand button", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "popular", rationale: "x" } }));
    expect(html).toContain('class="tile-expand"');
    expect(html).toContain('class="popularity popularity-badge-popular"');
  });

  test("popularity rationale is rendered as text", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "popular", rationale: "Brazil draws a global audience." } }));
    expect(html).toContain("Brazil draws a global audience.");
  });
});
```

- [ ] **Step 10.4: Run tests**

```bash
npm run typecheck
npm test -- --run
```

Expected: all green.

- [ ] **Step 10.5: Commit**

```bash
git add src/tests/types.test.ts src/tests/diff.test.ts src/tests/tiles.test.ts
git commit -m "test(ui): lite vs full tile rendering; types and diff fixtures on new shape"
```

---

## Task 11: Build, manual smoke, and PR

- [ ] **Step 11.1: Build the bundle**

```bash
npm run build
```

Expected: writes `site/assets/app.js`. No errors.

- [ ] **Step 11.2: Serve locally and spot-check**

```bash
cd site && python3 -m http.server 8765 &
SERVER_PID=$!
sleep 1
open http://localhost:8765/
```

In the browser:
- Confirm the header shows the new "Guide" link.
- Confirm the match list shows ~104 tiles.
- Apply the Popularity filter; confirm Popular / Moderate / Standard each filter independently.
- Click a Popular tile — confirm the expanded detail opens, shows cultural_context, language, rate strategy, logistics. No F&B section. No owner note blockquote.
- Click a Moderate or Standard tile — confirm there is no expand affordance (button is absent).
- Print preview (Cmd+P) is OK to leave for Plan C.

```bash
kill $SERVER_PID
```

- [ ] **Step 11.3: Push branch and open PR**

```bash
git push -u origin feat/frontend-popularity-and-lite-tiles
gh pr create --title "Frontend: popularity tiers, lite/full tiles, drop tickets/F&B UI" --body "$(cat <<'EOF'
## Summary
- Types updated to new JSON shape (`popularity` replaces `demand_tier`; tickets/fnb/owner_note dropped)
- Confirmed and TBD tiles branch on popularity tier — Lite (no expand) for moderate/standard, Full for popular
- Expanded detail drops F&B and owner-note sections; surfaces "Why this match is popular"
- Hero prefers next Popular match
- Filter swap: status → popularity
- Header gains a Guide link (Plan C builds the page)

## Test plan
- [ ] `npm run typecheck` clean
- [ ] `npm test -- --run` green
- [ ] Local browser pass: 104 tiles render; Popular tiles expand, Moderate/Standard don't; no F&B or owner note anywhere

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Plan B complete.
