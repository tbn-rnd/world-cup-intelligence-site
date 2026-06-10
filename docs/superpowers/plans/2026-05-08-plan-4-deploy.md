# IHG World Cup Site — Plan 4: GitHub Actions + GitHub Pages Deploy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Wire the existing CLI and frontend up to GitHub Actions so `matches.json` refreshes automatically on a cron schedule, the frontend bundle rebuilds when `src/**` changes, every PR runs the full test suite, and the resulting site is published to a GitHub Pages URL that leadership and hotel owners can visit. End state: pushing to `main` triggers a Pages deploy; an empty `git push` (or just waiting 30 min) results in fresh `matches.json` content; visitors hit `https://<owner>.github.io/<repo>/` and see the live site.

**Architecture:** Three GitHub Actions workflows. **`refresh.yml`** runs on two cron schedules (every 30 min for the group-stage cadence, every 15 min for knockouts), each phase-gated inside `refresh.py` so only one acts at a time. It runs the deterministic backend + agents (when keys are set) and commits the resulting `matches.json` to `main` if it changed. **`build-frontend.yml`** watches for pushes to `src/**` and rebuilds the bundle, committing the result back to `main`. **`ci.yml`** runs on every PR — pytest + mypy + ruff for the backend, tsc + vitest for the frontend. GitHub Pages is configured to deploy from `main` `/site`, so any commit to `main` triggers a Pages redeploy.

**Tech Stack:** GitHub Actions (existing), `astral-sh/setup-uv`, `actions/setup-node@v4`, `actions/checkout@v4`. No new dependencies in the codebase.

**Reference spec:** [`docs/superpowers/specs/2026-05-08-world-cup-intelligence-site-design.md`](../specs/2026-05-08-world-cup-intelligence-site-design.md), Section 7.

**Predecessor:** Plan 3, tagged `plan-3-complete`.

---

## File structure produced by this plan

```
.github/
  workflows/
    refresh.yml          Scheduled refresh (cron + workflow_dispatch)
    build-frontend.yml   Frontend bundle on src/** push
    ci.yml               PR validation
backend/
  refresh.py             Modified — add --cadence flag with phase gating
.gitignore               Modified — untrack site/assets/app.js + .map
README.md                Modified — bootstrap + deploy instructions
```

---

## Phase 4.1 — Phase-gated refresh CLI

Before adding the cron workflow, extend `refresh.py` so the same CLI works for both crons via `--cadence group_stage|knockouts` and exits cleanly when the cadence doesn't match the current tournament phase.

### Task 4.1.1: Add `--cadence` argument with phase gating

**Files:**
- Modify: `backend/refresh.py`
- Modify: `backend/tests/test_refresh_smoke.py`

- [ ] **Step 1: Read the existing CLI to find the argparse block**

```bash
grep -n "argparse\|add_argument\|main(" backend/refresh.py
```

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_refresh_smoke.py`:

```python
from backend.refresh import should_run_for_cadence


class TestCadenceGating:
    def test_group_stage_cadence_runs_in_pre_tournament(self) -> None:
        assert should_run_for_cadence("group_stage", "pre_tournament") is True

    def test_group_stage_cadence_runs_in_group_stage(self) -> None:
        assert should_run_for_cadence("group_stage", "group_stage") is True

    def test_group_stage_cadence_skips_in_knockouts(self) -> None:
        for phase in ("round_of_32", "round_of_16", "quarter_finals", "semi_finals", "finals"):
            assert should_run_for_cadence("group_stage", phase) is False, f"failed at {phase}"

    def test_knockouts_cadence_skips_in_pre_tournament_and_group_stage(self) -> None:
        for phase in ("pre_tournament", "group_stage"):
            assert should_run_for_cadence("knockouts", phase) is False, f"failed at {phase}"

    def test_knockouts_cadence_runs_in_all_knockout_phases(self) -> None:
        for phase in ("round_of_32", "round_of_16", "quarter_finals", "semi_finals", "finals"):
            assert should_run_for_cadence("knockouts", phase) is True, f"failed at {phase}"
```

- [ ] **Step 3: Run test (expect ImportError)**

```bash
uv run pytest backend/tests/test_refresh_smoke.py::TestCadenceGating -v
```

- [ ] **Step 4: Implement `should_run_for_cadence` and the `--cadence` arg**

In `backend/refresh.py`, add (near the other helpers):

```python
GROUP_STAGE_PHASES = {"pre_tournament", "group_stage"}
KNOCKOUT_PHASES = {"round_of_32", "round_of_16", "quarter_finals", "semi_finals", "finals"}


def should_run_for_cadence(cadence: str, current_phase: str) -> bool:
    """Return True if the given cron cadence should act during the given phase.

    The same refresh script is invoked from two crons:
      - group_stage cadence (every 30 min) — acts during pre_tournament + group_stage
      - knockouts cadence (every 15 min) — acts during R32 → finals

    The "off" cadence early-exits in <2 seconds with no work done.
    """
    if cadence == "group_stage":
        return current_phase in GROUP_STAGE_PHASES
    if cadence == "knockouts":
        return current_phase in KNOCKOUT_PHASES
    raise ValueError(f"unknown cadence: {cadence!r}")
```

In `main()`, add the argparse argument:

```python
    parser.add_argument(
        "--cadence",
        choices=["group_stage", "knockouts"],
        default=None,
        help="Cron cadence label. When set, the script computes the active "
             "tournament phase and exits cleanly if cadence doesn't match.",
    )
```

After argparse parsing and BEFORE the offline/live branch, add the gating check:

```python
    if args.cadence is not None:
        bracket = load_bracket(args.knowledge_dir / "bracket_2026.yaml")
        current_phase = bracket.phase_for_date(datetime.now(timezone.utc).date())
        if not should_run_for_cadence(args.cadence, current_phase):
            print(
                f"cadence={args.cadence} skipped (active phase: {current_phase})",
                file=sys.stderr,
            )
            return 0
```

- [ ] **Step 5: Run tests + mypy + ruff**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
```

All must pass. Test count goes up by 5.

- [ ] **Step 6: Commit**

```bash
git add backend/refresh.py backend/tests/test_refresh_smoke.py
git commit -m "feat(backend): --cadence flag with phase gating for cron workflows"
```

---

## Phase 4.2 — Untrack the frontend bundle

The frontend bundle (`site/assets/app.js` and its `.map`) is currently in `.gitignore`. The `build-frontend.yml` workflow needs to commit the bundle to `main` so GitHub Pages can serve it. Easiest fix: remove the bundle from `.gitignore` and commit the current build output.

### Task 4.2.1: Stop ignoring the frontend bundle

**Files:**
- Modify: `.gitignore`
- Add: `site/assets/app.js`, `site/assets/app.js.map` (commit current build)

- [ ] **Step 1: Edit `.gitignore`**

Remove these two lines:

```
site/assets/app.js
site/assets/app.js.map
```

(Leave `node_modules/`, `.venv/`, etc.)

- [ ] **Step 2: Rebuild and commit the current bundle**

```bash
npm run build
git add .gitignore site/assets/app.js site/assets/app.js.map
git commit -m "build: untrack frontend bundle so CI can commit it"
```

The bundle now lives in git. Local dev rebuilds will produce git diffs — that's expected; reviewers can verify or revert as needed.

---

## Phase 4.3 — `refresh.yml` workflow

### Task 4.3.1: Create the scheduled refresh workflow

**Files:**
- Create: `.github/workflows/refresh.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: refresh-match-data

on:
  schedule:
    # Group-stage cadence: every 30 min. Acts during pre_tournament + group_stage.
    - cron: "*/30 * * * *"
    # Knockout cadence: every 15 min. Acts during R32 → finals.
    - cron: "*/15 * * * *"
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: refresh
  cancel-in-progress: false

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Determine cadence from cron
        id: cadence
        run: |
          # GitHub Actions sets github.event.schedule to the exact cron string
          # that triggered this run, so we can distinguish the two schedules
          # cleanly even when both fire at the same minute mark (:00 / :30).
          SCHEDULE='${{ github.event.schedule }}'
          if [ "$SCHEDULE" = "*/15 * * * *" ]; then
            echo "cadence=knockouts" >> "$GITHUB_OUTPUT"
          else
            # Default to group_stage for the */30 schedule and for
            # workflow_dispatch (which leaves github.event.schedule empty).
            echo "cadence=group_stage" >> "$GITHUB_OUTPUT"
          fi
          echo "Cadence selected: cadence from schedule='$SCHEDULE'"

      - uses: astral-sh/setup-uv@v3
        with:
          version: latest

      - name: uv sync
        run: uv sync

      - name: Run refresh
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            # Manual run: skip cadence gating, refresh regardless of phase.
            uv run python -m backend.refresh
          else
            uv run python -m backend.refresh --cadence "${{ steps.cadence.outputs.cadence }}"
          fi

      - name: Commit changed matches.json
        run: |
          if [ -z "$(git status --porcelain site/data/matches.json)" ]; then
            echo "no changes to matches.json — exiting cleanly"
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add site/data/matches.json
          git commit -m "refresh: matches.json at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          # Use --rebase to handle the rare case where another workflow pushed during our run
          git pull --rebase origin main
          git push origin main
```

> **Notes on the cadence selection:**
>
> `github.event.schedule` contains the exact cron string that triggered the run, so the two schedules disambiguate cleanly even when both fire at the same minute mark (:00 / :30). For `workflow_dispatch` triggers `github.event.schedule` is empty, so we fall back to "group_stage" — but the actual run path uses the `else` branch in the "Run refresh" step (no `--cadence`) so the gating doesn't kick in. GitHub Actions cron is "best effort"; a delayed fire is harmless because each cadence's gating check uses the *current* phase, not the expected one.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/refresh.yml
git commit -m "feat(ci): scheduled refresh workflow with cadence-based cron gating"
```

---

## Phase 4.4 — `build-frontend.yml` workflow

### Task 4.4.1: Create the frontend bundle workflow

**Files:**
- Create: `.github/workflows/build-frontend.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: build-frontend

on:
  push:
    branches: [main]
    paths:
      - "src/**"
      - "package.json"
      - "package-lock.json"
      - "tsconfig.json"
      - "scripts/**"
      - "site/index.html"
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: build-frontend
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - run: npm ci

      - run: npm run typecheck

      - run: npm test

      - run: npm run build

      - name: Commit refreshed bundle
        run: |
          if [ -z "$(git status --porcelain site/assets/)" ]; then
            echo "bundle unchanged — exiting cleanly"
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add site/assets/app.js site/assets/app.js.map site/assets/flags
          git commit -m "build: refresh frontend bundle [skip ci]"
          git pull --rebase origin main
          git push origin main
```

> **`[skip ci]`** in the commit message prevents `ci.yml` from triggering when the bot pushes (its own pushes wouldn't trigger workflows by default anyway, but it's clean to be explicit).

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/build-frontend.yml
git commit -m "feat(ci): frontend bundle build workflow"
```

---

## Phase 4.5 — `ci.yml` workflow

### Task 4.5.1: Create the PR validation workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: ci

on:
  pull_request:
    branches: [main]
  workflow_dispatch: {}

permissions:
  contents: read

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: latest
      - run: uv sync
      - run: uv run pytest -v
      - run: uv run mypy backend
      - run: uv run ruff check backend

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
      - run: npm ci
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat(ci): PR validation workflow for backend + frontend"
```

---

## Phase 4.6 — README bootstrap instructions

### Task 4.6.1: Document deployment

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append a "Deployment" section to `README.md`**

Add after the "Frontend dev" section, before the end of the file:

```markdown
## Deployment

The site auto-deploys to GitHub Pages via three GitHub Actions workflows:

| Workflow                  | Trigger                                              | Output                                  |
|---------------------------|------------------------------------------------------|-----------------------------------------|
| `.github/workflows/refresh.yml`        | Cron */30 (group stage) + */15 (knockouts) + dispatch | Commits fresh `site/data/matches.json` to `main` |
| `.github/workflows/build-frontend.yml` | Push to `main` touching `src/**`                     | Commits rebuilt bundle to `main`        |
| `.github/workflows/ci.yml`             | Pull request                                         | Runs full test suite (no commit)        |

GitHub Pages serves from `main` `/site`. Any commit to `main` triggers a redeploy.

### One-time setup

1. **Push the repo to GitHub** (private or public — both work). If private, GitHub Pages requires a paid plan.

2. **Add repo secrets** at Settings → Secrets and variables → Actions:
    - `ODDS_API_KEY` — your paid Odds API tier key
    - `ANTHROPIC_API_KEY` — your Anthropic API key

3. **Enable GitHub Pages** at Settings → Pages:
    - Source: **Deploy from a branch**
    - Branch: `main`
    - Folder: `/site`

4. **Trigger the first refresh manually** at Actions → `refresh-match-data` → Run workflow. After ~30 seconds, `site/data/matches.json` is committed to `main` and the Pages deploy starts. Public URL is shown on the Pages settings screen — typically `https://<owner>.github.io/<repo>/`.

### Daily operation

- The refresh workflow runs on its own. No manual intervention needed during the tournament.
- If the Odds API or Anthropic API has an outage, `data_freshness` flips to `unreachable` in the JSON and the site header shows a red dot. Once the upstream recovers, the next cron tick fixes it.
- To force a regeneration of one match (e.g., after editing `knowledge/teams.yaml`), edit the match's signature in `matches.json` directly via a commit, or just delete the file — the next refresh will produce a fresh one.
- Manual workflow run: Actions → `refresh-match-data` → Run workflow. This skips the cadence gate and runs regardless of phase.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: deployment instructions for GitHub Actions + Pages"
```

---

## Phase 4.7 — Final acceptance + tag

### Task 4.7.1: Verify everything still works locally + tag

**Files:**
- (No file changes; this is verification + tagging)

- [ ] **Step 1: Local test pass**

```bash
uv run pytest -v
uv run mypy backend
uv run ruff check backend
npm run typecheck
npm test
npm run build
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z
ls -la site/data/matches.json site/assets/app.js
```

All commands must pass cleanly.

- [ ] **Step 2: Verify cadence gating works (unit tests cover the full matrix; this is a quick CLI smoke)**

The unit tests in Task 4.1.1 already cover all five (cadence, phase) combinations deterministically. As an end-to-end CLI smoke, just confirm the flag is wired:

```bash
uv run python -m backend.refresh --help 2>&1 | grep cadence
```

Expected: a line describing the `--cadence` flag with `group_stage` and `knockouts` choices. The deterministic gating logic is verified by `pytest`.

- [ ] **Step 3: Lint the workflow YAML**

```bash
# Use yamllint or just verify they parse
for f in .github/workflows/*.yml; do
  uv run python -c "import yaml; yaml.safe_load(open('$f'))" && echo "$f: OK"
done
```

All three workflows should print "OK".

- [ ] **Step 4: Move the milestone tag**

```bash
git tag -d plan-3-complete
git tag -a plan-4-complete -m "Plan 4: GitHub Actions + Pages deploy"
git log --oneline | head -15
git tag
```

`git tag` should show only `plan-4-complete`.

- [ ] **Step 5: Final summary**

The project is now end-to-end shippable. The user's only remaining steps are the bootstrap actions in the README:
1. Push to GitHub
2. Add the two API keys to repo secrets
3. Enable Pages
4. Trigger the first refresh

After that, the site auto-updates throughout the tournament with no manual work.

---

## Acceptance criteria for Plan 4

- `uv run pytest && uv run mypy backend && uv run ruff check backend` → all clean (cadence gating tests pass).
- `npm run typecheck && npm test && npm run build` → all clean.
- `uv run python -m backend.refresh --offline --as-of <pre_tournament_date> --cadence knockouts` → exits 0 with a "skipped" log line, no file changes.
- `uv run python -m backend.refresh --offline --as-of <group_stage_date> --cadence group_stage` → writes a fresh `matches.json`.
- All three workflow YAML files parse cleanly.
- `.gitignore` no longer ignores `site/assets/app.js` or its `.map`.
- `site/assets/app.js` is tracked in git.
- README has a "Deployment" section with the four bootstrap steps.
- Tag `plan-4-complete` is at HEAD.

The actual on-GitHub verification (push, secrets, enable Pages, first refresh) is the user's bootstrap and is NOT part of the automated acceptance — that's a one-time manual sequence per the README.
