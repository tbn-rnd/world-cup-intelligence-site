import { fetchMatches, type FetchResult } from "./data/fetcher.js";
import { changedMatchIds } from "./data/diff.js";
import { renderHeader } from "./components/header.js";
import { renderFooter } from "./components/footer.js";
import { renderTimeline } from "./components/timeline.js";
import { renderConfirmedTile } from "./components/confirmedTile.js";
import { renderTbdTile } from "./components/tbdTile.js";
import { pickNextUpDay, renderHero } from "./components/hero.js";
import { renderExpandedDetail } from "./components/expandedDetail.js";
import { renderBackToTop, attachBackToTop } from "./components/backToTop.js";
import {
  DEFAULT_FILTERS,
  applyFilters,
  renderFilters,
  uniqueCities,
  type FilterState,
} from "./components/filters.js";
import { computeWallClockFreshness } from "./utils/format.js";
import type { MatchObject, MatchesFile } from "./types.js";

const POLL_INTERVAL_MS = 60_000;
const DATA_URL = "data/matches.json";

let lastFile: MatchesFile | null = null;
let filters: FilterState = { ...DEFAULT_FILTERS };
const expandedIds = new Set<string>();

function renderHeaderFooter(file: MatchesFile): void {
  const wallFreshness = computeWallClockFreshness(
    file.generated_at,
    file.data_freshness,
    file.tournament_phase,
  );
  document.getElementById("app-header")!.innerHTML = renderHeader({
    generatedAt: file.generated_at,
    freshness: wallFreshness,
  });
  document.getElementById("app-footer")!.innerHTML = renderFooter({
    generatedAt: file.generated_at,
  });
}

function renderUnreachableHeader(): void {
  document.getElementById("app-header")!.innerHTML = renderHeader({
    generatedAt: new Date().toISOString(),
    freshness: "unreachable",
  });
}

function isFilterActive(state: FilterState): boolean {
  return (
    state.city !== "all" ||
    state.popularity !== "all" ||
    state.phase !== "all" ||
    state.team !== "all"
  );
}

function renderTimelineBanner(file: MatchesFile): void {
  const visible = applyFilters(file.matches, filters);
  document.getElementById("timeline")!.innerHTML = renderTimeline(
    file.matches,
    visible,
    isFilterActive(filters),
  );
}

function renderHeroPanel(file: MatchesFile): void {
  document.getElementById("hero")!.innerHTML = renderHero(pickNextUpDay(file.matches));
}

function renderTimelineAndHero(file: MatchesFile): void {
  renderTimelineBanner(file);
  renderHeroPanel(file);
}

function renderFiltersUI(file: MatchesFile | null): void {
  const total = file?.matches.length ?? 0;
  const visible = file ? applyFilters(file.matches, filters).length : 0;
  const cities = file ? uniqueCities(file.matches) : [];
  document.getElementById("filters")!.innerHTML = renderFilters(filters, total, visible, cities);
}

function renderTile(m: MatchObject): string {
  return m.status === "confirmed" ? renderConfirmedTile(m) : renderTbdTile(m);
}

function renderMatchList(file: MatchesFile): void {
  const visible = applyFilters(file.matches, filters);
  const matchList = document.getElementById("match-list")!;
  matchList.innerHTML = visible.map(renderTile).join("");
  for (const id of expandedIds) {
    const tile = document.getElementById(`match-${id}`);
    const match = file.matches.find((m) => m.id === id);
    if (tile && match) {
      tile.insertAdjacentHTML("beforeend", renderExpandedDetail(match));
      tile.classList.add("is-expanded");
    }
  }
}

function diffRenderMatchList(prev: MatchesFile, next: MatchesFile): void {
  const visible = applyFilters(next.matches, filters);
  const visibleIds = new Set(visible.map((m) => m.id));
  const matchList = document.getElementById("match-list")!;

  for (const tile of Array.from(matchList.querySelectorAll<HTMLElement>(".match-tile"))) {
    const id = tile.id.replace(/^match-/, "");
    if (!visibleIds.has(id)) tile.remove();
  }

  const ids = changedMatchIds(prev, next);
  const nextById = new Map(next.matches.map((m) => [m.id, m] as const));

  for (const id of ids) {
    const match = nextById.get(id);
    if (!match || !visibleIds.has(id)) continue;
    const existing = document.getElementById(`match-${id}`);
    const html = renderTile(match);
    if (existing) {
      existing.outerHTML = html;
    } else {
      matchList.insertAdjacentHTML("beforeend", html);
    }
    if (expandedIds.has(id)) {
      const tile = document.getElementById(`match-${id}`);
      tile?.insertAdjacentHTML("beforeend", renderExpandedDetail(match));
      tile?.classList.add("is-expanded");
    }
  }
}

function attachInteractions(): void {
  const matchList = document.getElementById("match-list")!;
  matchList.addEventListener("click", (ev) => {
    const target = ev.target as Element;
    if (target.closest("a, details > summary")) return;
    // Selecting text or interacting inside an open brief should not collapse it.
    // Only the explicit .tile-expand button (and the tile chrome above the panel) toggles.
    if (target.closest(".expanded-detail")) return;
    const tile = target.closest<HTMLElement>(".match-tile");
    if (!tile) return;
    const id = tile.id.replace(/^match-/, "");
    const match = lastFile?.matches.find((m) => m.id === id);
    if (!match) return;

    const existing = tile.querySelector(".expanded-detail");
    if (existing) {
      existing.remove();
      tile.classList.remove("is-expanded");
      tile.setAttribute("aria-expanded", "false");
      expandedIds.delete(id);
      if (location.hash === `#match-${id}`) {
        history.replaceState(null, "", location.pathname + location.search);
      }
    } else {
      tile.insertAdjacentHTML("beforeend", renderExpandedDetail(match));
      tile.classList.add("is-expanded");
      tile.setAttribute("aria-expanded", "true");
      expandedIds.add(id);
      history.replaceState(null, "", `#match-${id}`);
    }
  });

  // Keyboard support: Enter / Space on a focused .tile-expand button is already
  // handled natively. We also enable Enter / Space anywhere a tile has focus
  // (defensive — buttons cover the primary path).
  matchList.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const target = ev.target as Element;
    if (!target.closest(".tile-expand")) return;
    // Native button activation fires click — no extra work needed; preventDefault
    // only for Space to avoid page scroll.
    if (ev.key === " ") ev.preventDefault();
  });

  document.getElementById("filters")!.addEventListener("change", (ev) => {
    const target = ev.target as HTMLSelectElement;
    const key = target.dataset.filter;
    if (key === "city" || key === "popularity" || key === "phase") {
      filters = { ...filters, [key]: target.value };
      if (lastFile) {
        renderTimelineBanner(lastFile);
        renderMatchList(lastFile);
        renderFiltersUI(lastFile);
      }
    }
  });

  document.getElementById("filters")!.addEventListener("click", (ev) => {
    const target = ev.target as Element;
    const chip = target.closest<HTMLElement>("[data-team]");
    if (!chip) return;
    const code = chip.dataset.team!;
    // Click the active chip again to clear; click another chip to switch.
    const next = code === filters.team ? "all" : code;
    filters = { ...filters, team: next };
    if (lastFile) {
      renderTimelineBanner(lastFile);
      renderMatchList(lastFile);
      renderFiltersUI(lastFile);
    }
  });
}

function autoExpandFromHash(): void {
  const hashId = location.hash.replace(/^#match-/, "");
  if (!hashId || !lastFile) return;
  const match = lastFile.matches.find((m) => m.id === hashId);
  if (!match) return;
  const tile = document.getElementById(`match-${hashId}`);
  if (!tile) return;
  tile.scrollIntoView({ behavior: "smooth", block: "start" });
  if (!tile.querySelector(".expanded-detail")) tile.click();
}

async function poll(): Promise<void> {
  const result: FetchResult = await fetchMatches(DATA_URL);
  if (result.kind === "unreachable") {
    renderUnreachableHeader();
    return;
  }
  const file = result.file;
  renderHeaderFooter(file);
  renderTimelineAndHero(file);
  renderFiltersUI(file);

  if (lastFile === null) {
    renderMatchList(file);
  } else {
    diffRenderMatchList(lastFile, file);
  }
  lastFile = file;
}

/**
 * Returns true when the page is loading because the user hit reload
 * (vs. arriving fresh from a typed URL, pasted link, or in-app
 * navigation). Used to decide whether to honor a `#match-...` hash
 * on load: a fresh navigation respects the deep link, a reload
 * resets to the home state.
 */
function isReload(): boolean {
  const entries = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
  return entries[0]?.type === "reload";
}

/**
 * Sets the home state on bootstrap:
 *   - Disable the browser's scroll-restoration so a mid-page reload
 *     doesn't snap back to wherever the user was.
 *   - If this is a reload AND the URL carries a `#match-...` hash,
 *     strip it. Without this, hitting reload while a brief is open
 *     would re-expand the same brief and the user never gets a clean
 *     "back to the top" view. A fresh navigation with the same hash
 *     (i.e. a pasted link) is left alone so deep-link sharing still
 *     works.
 *   - Scroll to top, unconditionally on reload; on fresh navigation
 *     only when there's nothing for the existing anchor / autoExpand
 *     logic to land on.
 */
function resetHomeStateOnLoad(): void {
  if ("scrollRestoration" in history) {
    history.scrollRestoration = "manual";
  }
  const hash = location.hash;
  const reload = isReload();
  if (reload && hash) {
    // Clear the URL so autoExpandFromHash treats this load as a fresh-home arrival.
    history.replaceState(null, "", location.pathname + location.search);
  }
  if (reload || !hash) {
    window.scrollTo(0, 0);
  }
}

async function bootstrap(): Promise<void> {
  resetHomeStateOnLoad();
  renderFiltersUI(null);
  document.getElementById("back-to-top-mount")!.innerHTML = renderBackToTop();
  attachBackToTop();
  attachInteractions();
  await poll();
  autoExpandFromHash();
  setInterval(() => void poll(), POLL_INTERVAL_MS);
}

void bootstrap();
