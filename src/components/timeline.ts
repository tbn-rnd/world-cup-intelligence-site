import type { MatchObject } from "../types.js";
import { escapeHtml } from "../utils/escape.js";

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

export interface TimelineSummary {
  phaseLabel: string;
  countdown: string | null;
  totalsLine: string;
}

/**
 * Slim phase banner that replaces the prior 104-dot timeline. Renders three
 * sections on one line: tournament phase, countdown to the next kickoff in
 * the filtered subset, and an at-a-glance match-totals line. The hero block
 * directly below carries the next-match detail; per-match navigation lives
 * in the match list. Re-rendered on data refresh AND on filter change.
 */
export function renderTimeline(
  allMatches: MatchObject[],
  filteredMatches: MatchObject[],
  filterActive: boolean,
  now: Date = new Date(),
): string {
  const summary = computeTimelineSummary(allMatches, filteredMatches, filterActive, now);
  const parts: string[] = [
    `<span class="tl-phase">${escapeHtml(summary.phaseLabel)}</span>`,
  ];
  if (summary.countdown !== null) {
    parts.push(`<span class="tl-countdown">${escapeHtml(summary.countdown)}</span>`);
  }
  parts.push(`<span class="tl-totals">${escapeHtml(summary.totalsLine)}</span>`);
  return `<div class="tl-banner">${parts.join("")}</div>`;
}

export function computeTimelineSummary(
  allMatches: MatchObject[],
  filteredMatches: MatchObject[],
  filterActive: boolean,
  now: Date,
): TimelineSummary {
  if (allMatches.length === 0) {
    return { phaseLabel: "No matches scheduled", countdown: null, totalsLine: "0 matches" };
  }

  const nowTs = now.getTime();
  const sortedTourney = allMatches
    .filter((m) => m.phase !== "friendly")
    .sort((a, b) => new Date(a.kickoff_utc).getTime() - new Date(b.kickoff_utc).getTime());
  const firstTourneyTs =
    sortedTourney.length > 0 ? new Date(sortedTourney[0].kickoff_utc).getTime() : null;
  const lastTourneyTs =
    sortedTourney.length > 0
      ? new Date(sortedTourney[sortedTourney.length - 1].kickoff_utc).getTime()
      : null;

  const sortedFiltered = [...filteredMatches].sort(
    (a, b) => new Date(a.kickoff_utc).getTime() - new Date(b.kickoff_utc).getTime(),
  );
  const nextFilteredMatch = sortedFiltered.find(
    (m) => new Date(m.kickoff_utc).getTime() > nowTs,
  );

  // ---- Phase label ------------------------------------------------------
  let phaseLabel: string;
  let tournamentComplete = false;
  if (firstTourneyTs === null || lastTourneyTs === null) {
    phaseLabel = "Off-Season";
  } else if (nowTs < firstTourneyTs) {
    // "Countdown" reads sharper than "Pre-Tournament" once a kickoff
    // counter sits next to it (e.g. "COUNTDOWN · NEXT KICKOFF IN 8D").
    phaseLabel = "Countdown";
  } else if (nowTs > lastTourneyTs + DAY_MS) {
    phaseLabel = "Tournament Complete";
    tournamentComplete = true;
  } else {
    // Tournament window — label by the next upcoming tournament match's phase
    // (across the full schedule, not the filtered subset, so the label
    // describes the tournament rather than the GM's filter).
    const nextOverall = sortedTourney.find(
      (m) => new Date(m.kickoff_utc).getTime() > nowTs,
    );
    phaseLabel = nextOverall ? `${phaseFull(nextOverall.phase)} active` : "Tournament Complete";
    if (!nextOverall) tournamentComplete = true;
  }

  // ---- Countdown --------------------------------------------------------
  let countdown: string | null;
  if (tournamentComplete) {
    countdown = null;
  } else if (nextFilteredMatch) {
    const deltaMs = new Date(nextFilteredMatch.kickoff_utc).getTime() - nowTs;
    countdown = `Next kickoff in ${formatCountdown(deltaMs)}`;
  } else if (filterActive) {
    countdown = "No upcoming matches in filter";
  } else {
    countdown = null;
  }

  // ---- Totals -----------------------------------------------------------
  const totalAll = allMatches.length;
  const confirmedFiltered = filteredMatches.filter((m) => m.status === "confirmed").length;
  const tbdFiltered = filteredMatches.length - confirmedFiltered;
  const totalsLine = filterActive
    ? `${filteredMatches.length} of ${totalAll} · ${confirmedFiltered} confirmed · ${tbdFiltered} TBD`
    : `${totalAll} matches · ${confirmedFiltered} confirmed · ${tbdFiltered} TBD`;

  return { phaseLabel, countdown, totalsLine };
}

function formatCountdown(ms: number): string {
  if (ms < HOUR_MS) {
    const mins = Math.max(1, Math.ceil(ms / (60 * 1000)));
    return `${mins}m`;
  }
  if (ms < DAY_MS) {
    const hrs = Math.ceil(ms / HOUR_MS);
    return `${hrs}h`;
  }
  const days = Math.ceil(ms / DAY_MS);
  return `${days}d`;
}

function phaseFull(phase: string): string {
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
