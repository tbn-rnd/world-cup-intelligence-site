# World Cup 2026 Insight Aggregator

Dynamic HTML site that surfaces all 104 World Cup 2026 matches with
deterministic popularity tiering, deep fan-flow and hospitality context on the
matches that draw the most interest, and a navigation guide.

## Running locally

```bash
uv sync

# Offline (canned fixture, no agents — brief/prep stay null)
uv run python -m backend.refresh --offline --as-of 2026-06-20T12:00:00Z

# Live (Odds API + agents)
ODDS_API_KEY=... ANTHROPIC_API_KEY=... uv run python -m backend.refresh

# Tests
uv run pytest
uv run mypy backend
uv run ruff check backend
```

When `ANTHROPIC_API_KEY` is set, the briefing and prep advisor agents
populate `brief` and `prep` in `matches.json`. When unset, those fields
remain `null` (the deterministic backend still produces a valid file).

`site/data/matches.json` is the production artifact. It is **not shipped in
this repo** — it's built from The Odds API and api-football responses, and
redistributing that data may be restricted by the providers' terms. Generate
it yourself with your own API keys (or with `--offline` for the canned
fixture). See "Data licensing" below before committing it anywhere public.

## Frontend dev

```bash
npm install                    # one-time setup
npm run build                  # bundle to site/assets/app.js
npm run dev                    # watch mode
npm run typecheck              # tsc --noEmit
npm test                       # vitest
```

### Viewing the site locally

**You must serve the site through a local HTTP server, not open the file
directly.** Modern browsers block `fetch()` requests under the `file://`
protocol for security, which means the JS can't load `site/data/matches.json`
and the page renders empty.

```bash
# From the repo root, with site/data/matches.json already generated:
cd site && python3 -m http.server 8765

# Then open http://localhost:8765/ in any browser.
# Stop the server with Ctrl-C, or:
#   kill $(lsof -ti:8765)
```

In production (GitHub Pages, see Deployment below), the site is served over
HTTPS and no local server is needed — visitors just open the public URL.

The frontend reads `site/data/matches.json` produced by the backend; with no
data file, the header shows an "Offline" status and the rest is empty.

## Deployment

The site auto-deploys to GitHub Pages via these GitHub Actions workflows:

| Workflow                                  | Trigger                                                  | Output                                           |
|-------------------------------------------|----------------------------------------------------------|--------------------------------------------------|
| `.github/workflows/refresh.yml`           | Cron hourly (group stage) + `*/30` (knockouts) + dispatch | Commits fresh `site/data/matches.json` to `main` |
| `.github/workflows/deploy-pages.yml`      | Push to `main` touching the site surface; refresh runs   | Builds the bundle and deploys to GitHub Pages    |
| `.github/workflows/sync-recent-form.yml`  | Cron monthly + dispatch                                  | Opens a PR updating `knowledge/teams.yaml`       |
| `.github/workflows/ci.yml`                | Pull request                                             | Runs full test suite (no commit)                 |

Note that the refresh workflow **commits fetched provider data into your
repo**. That's a deliberate opt-in (the workflow force-adds past the
`.gitignore` entry) — see "Data licensing" below before enabling it on a
public repository.

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

4. **Trigger the first refresh manually** at Actions → `refresh-match-data` → Run workflow. After ~30 seconds, `site/data/matches.json` is committed to `main` and the Pages deploy starts. The public URL is shown on the Pages settings screen — typically `https://<owner>.github.io/<repo>/`.

### Daily operation

- The refresh workflow runs on its own. No manual intervention needed during the tournament.
- If the Odds API or Anthropic API has an outage, `data_freshness` flips to `unreachable` in the JSON and the site header shows a red dot. Once the upstream recovers, the next cron tick fixes it.
- To force a regeneration of one match (e.g., after editing `knowledge/teams.yaml`), edit the match's signature in `matches.json` directly via a commit, or just delete the file — the next refresh will produce a fresh one.
- Manual workflow run: Actions → `refresh-match-data` → Run workflow. This skips the cadence gate and runs regardless of phase.

## Data licensing

The **code** in this repository is MIT-licensed (see `LICENSE`). The **data**
it fetches is not: match odds come from [The Odds API](https://the-odds-api.com)
and team form data from [api-football](https://www.api-football.com), each
under their own terms of service. This repo therefore ships no fetched data —
you bring your own API keys and generate `site/data/matches.json` yourself.

If you deploy this with the scheduled refresh workflow, the generated data is
committed to your repo and served from your GitHub Pages site. Check your
data providers' terms before doing that from a public repository.

## License

MIT — see [LICENSE](LICENSE).
