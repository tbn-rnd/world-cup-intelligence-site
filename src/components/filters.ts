import type { MatchObject } from "../types.js";
import { flagPath, flagAltText } from "../utils/flags.js";
import { escapeHtml } from "../utils/escape.js";

export interface FilterState {
  city: string | "all";
  popularity: "popular" | "moderate" | "standard" | "all";
  phase: string | "all";
  team: string | "all";
}

export const DEFAULT_FILTERS: FilterState = {
  city: "all",
  popularity: "all",
  phase: "all",
  team: "all",
};

/**
 * "Global-following" nations whose traveling fans hotels see the most of.
 * Order matches the order in backend/popularity.py — Brazil and Argentina
 * lead because they're the marquee South American sides for North America
 * hotels; the European order tracks expected traveling-fan volume.
 */
export const QUICK_FILTER_TEAMS: { code: string; name: string }[] = [
  { code: "BRA", name: "Brazil" },
  { code: "ARG", name: "Argentina" },
  { code: "ENG", name: "England" },
  { code: "FRA", name: "France" },
  { code: "GER", name: "Germany" },
  { code: "ESP", name: "Spain" },
  { code: "POR", name: "Portugal" },
  { code: "NED", name: "Netherlands" },
  { code: "BEL", name: "Belgium" },
];

export function renderFilters(
  state: FilterState,
  totalMatches: number,
  visibleMatches: number,
  cities: string[],
): string {
  const countLabel =
    visibleMatches === totalMatches
      ? `All ${totalMatches} matches`
      : `${visibleMatches} of ${totalMatches} matches`;
  return `
    <div class="filters">
      ${renderQuickFilters(state.team)}
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

function renderQuickFilters(selectedTeam: string): string {
  const chips = QUICK_FILTER_TEAMS.map((t) => {
    const active = t.code === selectedTeam;
    return `<button
      type="button"
      class="quick-chip${active ? " is-active" : ""}"
      data-team="${t.code}"
      aria-pressed="${active ? "true" : "false"}"
    ><img class="quick-chip-flag" src="${flagPath(t.code)}" alt="${escapeHtml(flagAltText(t.code, t.name))}" width="18" height="13" loading="lazy" /><span>${escapeHtml(t.name)}</span></button>`;
  }).join("");
  const clear =
    selectedTeam === "all"
      ? ""
      : `<button type="button" class="quick-clear" data-team="all" aria-label="Clear team filter">✕ Clear</button>`;
  return `
    <div class="quick-filter">
      <div class="quick-filter-heading">
        <span class="quick-filter-eyebrow">Click a team to follow them through the tournament</span>
        ${clear}
      </div>
      <div class="quick-filter-chips" role="group" aria-label="Filter by team">
        ${chips}
      </div>
    </div>
  `;
}

function cityOptions(selected: string, cities: string[]): string {
  const opts = ["all", ...cities];
  return opts
    .map(
      (c) =>
        `<option value="${c}"${c === selected ? " selected" : ""}>${
          c === "all" ? "All cities" : c
        }</option>`,
    )
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
    if (state.team !== "all" && !matchInvolvesTeam(m, state.team)) return false;
    return true;
  });
}

function matchInvolvesTeam(m: MatchObject, code: string): boolean {
  // Confirmed: either side is the team.
  if (m.teams.confirmed) {
    if (m.teams.confirmed.some((t) => t.code === code)) return true;
  }
  // TBD: the team appears as a candidate in any feeder distribution.
  // tbd_scenarios are derived from the same candidate pool, so checking
  // feeder_distributions alone is sufficient.
  if (m.teams.feeder_distributions) {
    for (const fd of m.teams.feeder_distributions) {
      if (fd.teams.some((t) => t.code === code)) return true;
    }
  }
  return false;
}

export function uniqueCities(matches: MatchObject[]): string[] {
  return Array.from(new Set(matches.map((m) => m.host_city))).sort();
}
