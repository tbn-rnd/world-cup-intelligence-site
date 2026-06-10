# Plan D — Docs Cleanup (README, Index Footer, Old Spec Pointer)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prereq:** Plans A and B merged or on `main` (the README and methodology footer reference the new shape and behavior).

**Goal:** Purge IHG-ticket-portfolio language from the README, the in-app methodology footer, and the older design spec so the project's prose matches its new public-tournament framing.

**Architecture:** Pure documentation edits. No code, no tests.

**Spec:** `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`.

---

## Pre-flight

- [ ] **Step 0.1: Sync and branch**

```bash
git fetch origin
git checkout main
git pull --rebase origin main
git checkout -b chore/docs-cleanup-104-match
```

---

## Task 1: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1.1: Rewrite the top-of-file framing**

Open `README.md`. Replace the title and opening paragraph:

Old:

```markdown
# IHG World Cup 2026 Match Intelligence Site

Dynamic HTML site that surfaces IHG's 11 World Cup 2026 ticket matchups
with live probability updates and hospitality intelligence.

See `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`
for the full design.
```

New:

```markdown
# IHG World Cup 2026 Match Intelligence Site

Dynamic HTML site that surfaces all 104 FIFA World Cup 2026 matches with
deterministic popularity tiering, deep hospitality intelligence on the
matches that draw the most interest, and a hotel-user guide.

See `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`
for the active design. The earlier
`docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`
is preserved as a historical record of the IHG-ticket-portfolio scope.
```

Replace the Status table:

```markdown
## Status

| Plan | Subsystem                                                | State       |
|------|----------------------------------------------------------|-------------|
| A    | Backend: fixtures (104), popularity, agent tier gate     | complete    |
| B    | Frontend: lite/full tiles, popularity badges, drop F&B   | complete    |
| C    | Hotel-user guide (HTML + printable Markdown)             | complete    |
| D    | Docs cleanup                                             | complete    |
```

(Update each row's state to match reality at merge time — `complete` if the corresponding plan is merged; `in progress` otherwise.)

- [ ] **Step 1.2: Update knowledge-file references**

Search the README for `ticket_inventory.yaml` and replace every occurrence with `fixtures_2026.yaml`. Search for `tickets`, `demand_tier`, `fnb`, `owner_invitation_note`, `owner invitation`, `11 World Cup 2026 ticket matchups`, `IHG's 11`, and either delete those sentences or rewrite them to refer to the new shape.

Concrete spot to check — the "Daily operation" bullet that says:

```markdown
- To force a regeneration of one match (e.g., after editing `knowledge/teams.yaml`), edit the match's signature in `matches.json` directly via a commit, or just delete the file — the next refresh will produce a fresh one.
```

That stays — `teams.yaml` is still authoritative.

- [ ] **Step 1.3: Commit**

```bash
git add README.md
git commit -m "docs(readme): reframe as 104-match public view; point to new design spec"
```

---

## Task 2: Methodology footer in `site/index.html`

**Files:**
- Modify: `site/index.html`

- [ ] **Step 2.1: Rewrite the `<section id="methodology">` content**

In `site/index.html`, replace the existing `<section id="methodology" class="methodology" hidden>` block (currently 27-40) with:

```html
      <section id="methodology" class="methodology" hidden>
        <h2>How match popularity is computed</h2>
        <p>
          Every match is auto-labeled <strong>Popular</strong>,
          <strong>Moderate</strong>, or <strong>Standard</strong> by a
          deterministic rule: finals and semi-finals are inherently popular;
          group-stage matches go popular if any team is FIFA top-10, a host
          nation (USA, Mexico, Canada), or a global-draw brand (Brazil,
          Argentina, France, England, Germany, Spain, Portugal, Netherlands,
          Belgium); knockout matches that didn't qualify default to moderate;
          group-stage matches with at least one top-25 team are moderate;
          everything else is standard. Probabilities and TBD-slot scenarios
          continue to come from the Odds API match-winner odds plus the
          official FIFA bracket structure, with closed-form enumeration over
          all 729 group outcomes and 10,000-iteration Monte Carlo simulation
          for downstream knockout slots.
          See <code>docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md</code>
          for the full spec.
        </p>
      </section>
```

- [ ] **Step 2.2: Commit**

```bash
git add site/index.html
git commit -m "docs(index): methodology footer describes popularity rule, not demand tier"
```

---

## Task 3: Pointer in the original design spec

**Files:**
- Modify: `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`

- [ ] **Step 3.1: Add a top-of-file pointer to the new spec**

At the very top of `docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`, insert before the existing first line:

```markdown
> **Historical record.** This document captures the IHG ticket-portfolio scope
> (11 matches, demand tier, F&B suggestions, owner-invitation framing). That
> scope was superseded on 2026-06-01 by the public-tournament reframe.
> See `docs/superpowers/specs/2026-06-01-104-match-expansion-and-product-reframe-design.md`
> for the active design.

```

- [ ] **Step 3.2: Commit**

```bash
git add docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md
git commit -m "docs(spec): point original design spec to the 2026-06-01 reframe"
```

---

## Task 4: Final grep pass for stragglers

- [ ] **Step 4.1: Find any lingering references**

```bash
grep -rn "demand_tier\|ticket_inventory\|owner_invitation\|demand tier\|11 World Cup\|IHG's 11" \
  --include="*.md" --include="*.html" --include="*.css" \
  --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git \
  --exclude-dir=worktrees --exclude="*-2026-05-08-*" \
  .
```

Expected: no matches outside `docs/superpowers/specs/2026-05-08-*.md` (which is intentionally preserved as history) and the worktree cache.

If matches surface, decide per-file whether to delete or update the reference, then commit each fix as its own small commit.

- [ ] **Step 4.2: Push and PR**

```bash
git push -u origin chore/docs-cleanup-104-match
gh pr create --title "Docs: purge IHG-ticket framing; point to 2026-06-01 spec" --body "$(cat <<'EOF'
## Summary
- README reframed as 104-match public tournament view
- Methodology footer describes popularity rule (not demand tier)
- Original 2026-05-08 design spec now carries a historical-record pointer
- Stragglers swept with grep pass

## Test plan
- [ ] grep finds no `demand_tier` / `ticket_inventory` / `owner_invitation` in markdown/html/css outside the preserved historical spec

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Plan D complete.
