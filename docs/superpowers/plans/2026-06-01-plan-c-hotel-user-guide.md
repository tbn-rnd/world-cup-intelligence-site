# Plan C — Hotel-User Guide (HTML + Printable Markdown)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prereq:** Plan B is recommended-merged (so the Guide link in the header has a destination), but this plan can be developed in parallel against `main` and merged afterwards. The Markdown source has no runtime dependency on Plans A/B.

**Goal:** Publish a standalone hotel-user guide for the site — `site/guide.html`, generated at build time from a single `site/guide.md` source, with print styles so users get a clean PDF via browser File → Print.

**Architecture:**
- `site/guide.md` is the source of truth. Authored once; rebuilt to HTML when the bundle builds.
- `scripts/build.mjs` gains a small Markdown-to-HTML step using a minimal converter (no client-side parsing).
- `site/assets/styles.css` gets a `@media print` block to drop chrome and enforce page breaks.

**Tech Stack:** Node ESM scripts, esbuild (existing), `marked` (lightweight Markdown → HTML), TypeScript types unaffected.

**Spec:** `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`.

---

## Pre-flight

- [ ] **Step 0.1: Sync and branch**

```bash
git fetch origin
git checkout main
git pull --rebase origin main
git checkout -b feat/hotel-user-guide
npm install
```

- [ ] **Step 0.2: Add `marked` as a dev dependency**

```bash
npm install --save-dev marked
```

`marked` is a tiny, well-maintained Markdown → HTML library with no runtime browser need (we use it at build time only).

- [ ] **Step 0.3: Commit dep addition**

```bash
git add package.json package-lock.json
git commit -m "chore(deps): add marked for build-time guide markdown rendering"
```

---

## Task 1: Author `site/guide.md`

**Files:**
- Create: `site/guide.md`

- [ ] **Step 1.1: Write the guide content**

Create `site/guide.md`:

```markdown
# World Cup 2026 Match Intelligence — Hotel User Guide

A reference for IHG property General Managers using the World Cup 2026 Match Intelligence Site.

## What this site is

This site surfaces live, refreshed intelligence on all 104 matches of the FIFA World Cup 2026 (11 June – 19 July 2026). It is intended for property General Managers and operations leaders who need a single place to scan upcoming matches, see at a glance which ones will draw heightened guest interest, and read deeper hospitality context for the matches that matter most for their market.

## How to read a match tile

Every match in the list is rendered as a tile. The tile is consistent across confirmed and TBD knockout matches; the level of detail depends on the match's **popularity tier**.

A tile shows, top to bottom:

- **Date strip** — kickoff date and local time, host city, phase (Group Stage / Round of 16 / etc.).
- **Popularity badge** — `Popular`, `Moderate`, or `Standard` (top-right).
- **Match body** — for confirmed matches, the two teams with flags and FIFA ranks. For TBD knockout matches, the feeder distributions (which group winners or runners-up are most likely to fill this slot) and the most-likely specific matchups.
- **Popularity rationale** — one short line explaining why this match earned its tier.
- **Venue + (Popular tiles only) expand control** — Popular tiles show a "View brief & prep" button. Moderate and Standard tiles do not — they are intentionally lightweight.

## Match popularity, explained

Every match is automatically labeled `Popular`, `Moderate`, or `Standard`. The rules are deterministic — no human curation, no surprises:

| Tier | Triggers |
| --- | --- |
| **Popular** | Final, Semi-final, or Bronze-final. Or any team is FIFA top-10. Or (in group stage) any team is a host nation (USA / Mexico / Canada) or a global-draw brand (Brazil, Argentina, France, England, Germany, Spain, Portugal, Netherlands, Belgium). |
| **Moderate** | Any knockout round (R32, R16, QF) that didn't already qualify as Popular. Or a group-stage match where at least one team is FIFA top-25. |
| **Standard** | Everything else — most often group-stage matches between teams outside the top 25. |

The rationale string on each tile tells you which trigger fired ("Brazil (FIFA #1) draws a global audience," "Host-nation match in Mexico City," "Group stage; teams outside the top 25 FIFA," etc.). If you ever wonder *why* a match is labeled the way it is, that string is the answer.

## TBD knockout matches

For knockout slots whose teams aren't yet known, the tile shows:

- **Feeder distributions** — the probability that each candidate team fills this slot, based on group-standings simulation.
- **Specific matchups** — the top-3 most-likely specific team-vs-team pairings, with their joint probabilities.
- **Decision date** — when this slot's teams will be fully confirmed.

As the bracket resolves, the popularity tier may upgrade. A round-of-16 slot may start as `Moderate` (phase-only), then flip to `Popular` once a feeder distribution's leader passes 60% confidence and that leader is a top-10 / host-nation / global-draw team.

## The deep brief (Popular matches only)

Clicking a Popular tile opens a deeper card:

- **Headline** — one sentence on what this match means for hotels in the host market.
- **Scenario summary** (TBD only) — narrative around the most-likely matchups.
- **Fan demographics** — who's traveling and from where, grounded in curated diaspora data.
- **Traveling volume estimate** — light / moderate / heavy with reasoning.
- **Cultural context** — food traditions, religious and dietary observances, fan rituals. This is **background** for awareness, not a checklist of things to execute.
- **Why this match is popular** — the same rationale text shown on the tile.
- **Property preparation** — Language requirements, Rate strategy, Logistics.

Moderate and Standard matches deliberately stop at the tile. The deep brief is reserved for the matches that warrant the property's planning attention.

## Data freshness and timing

A status dot in the site header shows the live data state:

- **Green dot — Live**: data was refreshed within the last cycle. During the group stage the data refreshes every 30 minutes; during knockouts, every 15 minutes.
- **Stale**: green dot but with a tooltip — data is older than expected; the next refresh tick should resolve it.
- **Red dot — Offline**: the upstream data source is unreachable. The site continues to show the last good snapshot.

## Glossary

- **Bracket slot** — A position in the knockout tree, named by round (e.g., `r32_match_75`). Filled by the winner or qualifier of an earlier stage.
- **Bronze final** — The third-place playoff. Played the day before the Final.
- **Confirmed match** — A match whose two teams are known. All 72 group-stage matches are confirmed before kickoff; knockout matches become confirmed as the bracket resolves.
- **Cultural context** — Background on food, religious or dietary observances, and fan rituals for the teams' traveling fans. Awareness, not a to-do list.
- **Decision date** — The date by which a TBD slot's teams are fully confirmed.
- **Diaspora** — Communities of a team's nationality living abroad. Used to estimate traveling fan volume.
- **FIFA rank** — World football's official team ranking. Lower numbers are stronger; FIFA #1 is the top-ranked nation.
- **Final draw** — The 5 December 2025 ceremony that assigned the 48 nations to the 12 groups.
- **Fixture** — A scheduled match (id, kickoff, host city, venue, phase). The site's data is driven by the 104-match fixture file.
- **Global-draw brand** — A team whose appearance reliably draws an out-of-market global audience: Brazil, Argentina, France, England, Germany, Spain, Portugal, Netherlands, Belgium.
- **Group stage** — The opening round: 12 groups of 4, 6 matches per group, 72 matches total. Top two from each group plus the eight best third-placed teams advance.
- **Host city** — The metro region of the venue (Atlanta, NY/NJ, Mexico City, Toronto, etc.).
- **Host nation** — USA, Mexico, or Canada — the tournament's three co-hosts. Their matches are automatically Popular at group stage.
- **Kickoff (local vs UTC)** — `kickoff_local` is the time at the venue (with its time-zone offset). `kickoff_utc` is the same moment in Coordinated Universal Time. Use UTC for cross-property comparisons.
- **Knockout phase** — Single-elimination rounds from Round of 32 through the Final.
- **Logistics** — Transport, late-dining, and group-booking notes in the deep brief.
- **Match popularity** — The three-tier label (`Popular` / `Moderate` / `Standard`) auto-assigned to every match.
- **Moderate** — A popularity tier — a knockout match without a Popular trigger, or a group-stage match with at least one top-25 team.
- **Phase** — Where the match sits in the tournament: group stage, R32, R16, quarter-final, semi-final, bronze final, or final.
- **Popular** — A popularity tier — the highest. The only tier that opens a deep brief.
- **Popularity rationale** — The short sentence on each tile explaining which trigger produced the tier.
- **Quarter-final** — The eight teams remaining after Round of 16 play four matches to reach the semi-finals.
- **Rate strategy** — One-sentence pricing posture for the property on this match's date.
- **Round of 16** — The eight matches that follow Round of 32; sixteen teams enter, eight advance.
- **Round of 32** — The first knockout round in the 48-team format. Thirty-two teams enter, sixteen advance.
- **Scenario** — In a TBD knockout slot, a specific team-vs-team matchup that *could* fill the slot, with its probability.
- **Semi-final** — Two matches that decide the two finalists.
- **Standard** — A popularity tier — most group-stage matches where neither team is FIFA top-25 and no host or global-draw brand is involved.
- **TBD** — A knockout slot whose teams are not yet known. Carries scenarios and feeder distributions instead of confirmed teams.
- **Venue** — The stadium hosting the match.

## Questions

For site questions or data corrections, contact the IHG hospitality intelligence team.
```

- [ ] **Step 1.2: Commit**

```bash
git add site/guide.md
git commit -m "docs(guide): hotel-user guide markdown source"
```

---

## Task 2: Build step — render guide.md → guide.html

**Files:**
- Modify: `scripts/build.mjs`
- Create: `site/assets/guide-template.html`

- [ ] **Step 2.1: Create the HTML template**

Create `site/assets/guide-template.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Guide · IHG World Cup 2026 Match Intelligence</title>
    <meta name="theme-color" content="#0a1628" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800&family=Geist:wght@300..700&family=JetBrains+Mono:wght@400..600&display=swap"
    />
    <link rel="stylesheet" href="assets/styles.css" />
  </head>
  <body class="guide-body">
    <div class="grain" aria-hidden="true"></div>
    <header class="guide-header">
      <a class="guide-back" href="index.html">← Back to Match Centre</a>
    </header>
    <main class="guide-main">
      <!-- GUIDE_BODY -->
    </main>
    <footer class="guide-footer">
      <span>IHG · Hospitality Intelligence · World Cup 2026</span>
    </footer>
  </body>
</html>
```

- [ ] **Step 2.2: Add the build step**

Replace `scripts/build.mjs` with:

```js
import { build, context } from "esbuild";
import { marked } from "marked";
import { readFile, writeFile } from "node:fs/promises";

const watch = process.argv.includes("--watch");

const opts = {
  entryPoints: ["src/main.ts"],
  bundle: true,
  outfile: "site/assets/app.js",
  format: "esm",
  target: "es2022",
  sourcemap: true,
  minify: !watch,
  logLevel: "info",
};

async function buildGuide() {
  const md = await readFile("site/guide.md", "utf8");
  const template = await readFile("site/assets/guide-template.html", "utf8");
  const html = marked.parse(md, { mangle: false, headerIds: true });
  const out = template.replace("<!-- GUIDE_BODY -->", html);
  await writeFile("site/guide.html", out, "utf8");
  console.log("built site/guide.html");
}

if (watch) {
  const ctx = await context(opts);
  await ctx.watch();
  console.log("watching src/...");
  await buildGuide();
  // Re-render the guide on each rebuild trigger is overkill; users editing the md
  // can re-run `npm run build:guide` if a dedicated script is desired. For now,
  // a one-shot at watch start is sufficient.
} else {
  await build(opts);
  console.log("built site/assets/app.js");
  await buildGuide();
}
```

- [ ] **Step 2.3: Test the build**

```bash
npm run build
ls -la site/guide.html
```

Expected: `site/guide.html` exists and contains the rendered Markdown.

- [ ] **Step 2.4: Commit**

```bash
git add scripts/build.mjs site/assets/guide-template.html
git commit -m "feat(build): render guide.md to guide.html at build time"
```

---

## Task 3: Guide CSS — readable layout + print styles

**Files:**
- Modify: `site/assets/styles.css`

- [ ] **Step 3.1: Append guide and print styles**

Append to `site/assets/styles.css`:

```css
/* ---------------- Guide page (guide.html) ---------------- */
.guide-body {
  background: #fafaf7;
  color: #14202c;
}
.guide-header {
  padding: 1rem 2rem;
  max-width: 760px;
  margin: 0 auto;
}
.guide-back {
  color: inherit;
  font-size: 0.85rem;
  text-decoration: none;
  opacity: 0.75;
}
.guide-back:hover { opacity: 1; }
.guide-main {
  max-width: 760px;
  margin: 0 auto;
  padding: 1rem 2rem 4rem;
  font-family: "Newsreader", Georgia, serif;
  font-size: 1.05rem;
  line-height: 1.65;
}
.guide-main h1 {
  font-size: 2.25rem;
  margin: 1.5rem 0 0.5rem;
  letter-spacing: -0.01em;
}
.guide-main h2 {
  font-size: 1.5rem;
  margin: 2.5rem 0 0.75rem;
  border-bottom: 1px solid rgba(0,0,0,0.1);
  padding-bottom: 0.3rem;
}
.guide-main h3 { font-size: 1.15rem; margin: 1.5rem 0 0.5rem; }
.guide-main table {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
  font-size: 0.95rem;
}
.guide-main th, .guide-main td {
  border: 1px solid rgba(0,0,0,0.12);
  padding: 0.55rem 0.75rem;
  text-align: left;
  vertical-align: top;
}
.guide-main th { background: rgba(0,0,0,0.04); font-weight: 600; }
.guide-main ul, .guide-main ol { padding-left: 1.4rem; }
.guide-main li { margin: 0.35rem 0; }
.guide-main code {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 0.9em;
  background: rgba(0,0,0,0.05);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.guide-footer {
  max-width: 760px;
  margin: 0 auto;
  padding: 0 2rem 2rem;
  font-size: 0.78rem;
  opacity: 0.6;
  text-align: center;
}

/* ---------------- Print / PDF styles for the guide ---------------- */
@media print {
  body, .guide-body {
    background: #fff !important;
    color: #000 !important;
  }
  .grain, .guide-header, .guide-back, .guide-footer { display: none !important; }
  .guide-main {
    max-width: none;
    margin: 0;
    padding: 0;
    font-size: 11pt;
    line-height: 1.45;
  }
  .guide-main h2 {
    page-break-before: auto;
    break-before: auto;
    border-bottom-color: #000;
  }
  .guide-main h2:not(:first-of-type) {
    page-break-before: always;
    break-before: page;
  }
  .guide-main table, .guide-main tr, .guide-main td, .guide-main th {
    page-break-inside: avoid;
    break-inside: avoid;
  }
  a { color: inherit; text-decoration: none; }
  @page { margin: 0.6in; }
}
```

- [ ] **Step 3.2: Rebuild and visually verify**

```bash
npm run build
cd site && python3 -m http.server 8765 &
SERVER_PID=$!
sleep 1
open http://localhost:8765/guide.html
```

In the browser:
- Confirm the guide renders with a readable serif layout, 760px max width, clear section headings.
- Cmd+P → preview the print layout. Confirm: no grain/header/footer chrome in print; each `## Heading` starts on a fresh page; the table is intact and not split across pages.

```bash
kill $SERVER_PID
```

- [ ] **Step 3.3: Commit**

```bash
git add site/assets/styles.css
git commit -m "feat(ui): guide page styles + print/PDF media query"
```

---

## Task 4: Push and PR

- [ ] **Step 4.1: Push branch**

```bash
git push -u origin feat/hotel-user-guide
gh pr create --title "Guide: hotel-user one-pager (HTML + printable Markdown)" --body "$(cat <<'EOF'
## Summary
- `site/guide.md` — single Markdown source for the hotel-user guide, including the glossary
- `scripts/build.mjs` renders guide.md to `site/guide.html` at build time using marked
- Guide-page styles and `@media print` block in styles.css; browser File→Print produces a clean PDF
- Header nav link to guide.html added in Plan B

## Test plan
- [ ] `npm run build` produces `site/guide.html`
- [ ] Browser preview at /guide.html renders readably
- [ ] Cmd+P preview drops nav and page-breaks per section
- [ ] Glossary table renders correctly in both web and print

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Plan C complete.
