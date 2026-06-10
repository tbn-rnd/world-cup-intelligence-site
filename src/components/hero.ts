import type { MatchObject } from "../types.js";
import { flagPath, flagAltText } from "../utils/flags.js";
import { escapeHtml } from "../utils/escape.js";
import { POPULARITY_LABEL } from "../utils/format.js";

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

/**
 * Pick every match scheduled on the next kickoff day. Returns up to N
 * matches sharing the same venue-local kickoff date, sorted by kickoff
 * instant. A match is "next" if its kickoff_utc is at most six hours in
 * the past — same tolerance the single-match picker used to extend the
 * "current" match through full-time + extra time + post-match coverage.
 */
export function pickNextUpDay(
  matches: MatchObject[],
  now: Date = new Date(),
): MatchObject[] {
  if (matches.length === 0) return [];
  const cutoff = now.getTime() - SIX_HOURS_MS;
  const upcoming = matches
    .filter((m) => new Date(m.kickoff_utc).getTime() >= cutoff)
    .sort(
      (a, b) =>
        new Date(a.kickoff_utc).getTime() - new Date(b.kickoff_utc).getTime(),
    );
  if (upcoming.length === 0) return [];
  // Use the venue-local kickoff date for grouping — a late-night LA match
  // and an early-morning Tokyo match might share a UTC date but belong to
  // different local days from the hotel team's perspective.
  const slateDate = upcoming[0].kickoff_local.slice(0, 10);
  return upcoming.filter((m) => m.kickoff_local.slice(0, 10) === slateDate);
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function parseDateParts(
  iso: string,
): { month: string; day: number; time: string } | null {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return null;
  const month = MONTHS[parseInt(m[2], 10) - 1];
  const day = parseInt(m[3], 10);
  const h24 = parseInt(m[4], 10);
  const mm = m[5];
  const ampm = h24 >= 12 ? "pm" : "am";
  const h12 = ((h24 + 11) % 12) + 1;
  return { month, day, time: `${h12}:${mm} ${ampm}` };
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

/**
 * Render the "Next Up" hero. Accepts the full slate of matches sharing
 * the next kickoff date. A single-match slate renders one wide card;
 * a multi-match slate renders an auto-fit grid of compact mini-cards
 * so all of that day's matches sit above the fold.
 */
export function renderHero(matches: MatchObject[]): string {
  if (matches.length === 0) {
    return `<div class="hero-empty">Tournament complete — no upcoming match.</div>`;
  }
  const first = matches[0];
  const date = parseDateParts(first.kickoff_local);
  const month = date?.month ?? "—";
  const day = date?.day ?? 0;
  const matchWord = matches.length === 1 ? "match" : "matches";
  return `
    <article class="hero hero-slate" data-count="${matches.length}">
      <header class="hero-slate-header">
        <span class="hero-eyebrow">Next Up</span>
        <span class="hero-slate-date">
          <span class="hero-slate-month">${escapeHtml(month)}</span>
          <span class="hero-slate-day">${day}</span>
          <span class="hero-slate-count">${matches.length} ${matchWord}</span>
        </span>
      </header>
      <div class="hero-slate-grid">
        ${matches.map(renderMiniCard).join("")}
      </div>
    </article>
  `;
}

function renderMiniCard(match: MatchObject): string {
  const date = parseDateParts(match.kickoff_local);
  const time = date?.time ?? "";
  const phase = phaseLabel(match.phase);
  const tag =
    match.status === "confirmed"
      ? POPULARITY_LABEL[match.popularity.tier]
      : `Decides in ${match.days_to_decision ?? "?"}d`;

  return `
    <a class="hero-mini popularity-${match.popularity.tier}" href="#match-${escapeHtml(match.id)}">
      <div class="hero-mini-strip">
        <span class="hero-mini-time">${escapeHtml(time)}</span>
        <span class="hero-mini-phase">${escapeHtml(phase)}</span>
      </div>
      ${match.status === "confirmed" ? renderConfirmedMatchup(match) : renderTbdMatchup(match)}
      <div class="hero-mini-foot">
        <span class="hero-mini-tag hero-mini-tag-${match.popularity.tier}">${escapeHtml(tag)}</span>
        <span class="hero-mini-city">${escapeHtml(match.host_city)}</span>
        <span class="hero-mini-cta">View brief →</span>
      </div>
    </a>
  `;
}

function renderConfirmedMatchup(match: MatchObject): string {
  if (match.teams.confirmed === null || match.teams.confirmed.length !== 2) return "";
  const [a, b] = match.teams.confirmed;
  return `
    <div class="hero-mini-matchup">
      <span class="hero-mini-team">
        <img class="hero-mini-flag" src="${flagPath(a.code)}" alt="${escapeHtml(flagAltText(a.code, a.name))}" />
        <span>${escapeHtml(a.name)}</span>
      </span>
      <span class="hero-mini-vs">vs</span>
      <span class="hero-mini-team">
        <img class="hero-mini-flag" src="${flagPath(b.code)}" alt="${escapeHtml(flagAltText(b.code, b.name))}" />
        <span>${escapeHtml(b.name)}</span>
      </span>
    </div>
  `;
}

function renderTbdMatchup(match: MatchObject): string {
  const fd = match.teams.feeder_distributions;
  if (!fd || fd.length === 0) {
    return `<div class="hero-mini-matchup hero-mini-tbd"><span>Knockout slot · TBD</span></div>`;
  }
  const labels = fd.map((f) => escapeHtml(f.label)).join(" <em>×</em> ");
  return `
    <div class="hero-mini-matchup hero-mini-tbd">
      <span class="hero-mini-tbd-label">Slot</span>
      <span class="hero-mini-tbd-leaders">${labels}</span>
    </div>
  `;
}
