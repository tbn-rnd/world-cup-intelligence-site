import type {
  FeederDistribution,
  MatchObject,
  TbdScenario,
} from "../types.js";
import { flagPath, flagAltText } from "../utils/flags.js";
import { formatProbability, probabilityBarBackground, POPULARITY_LABEL } from "../utils/format.js";
import { escapeHtml } from "../utils/escape.js";
import { tileTimes, venueShortDate } from "../utils/timezones.js";

function renderKickoffSegment(match: MatchObject): string {
  const t = tileTimes({
    kickoff_utc: match.kickoff_utc,
    kickoff_local: match.kickoff_local,
  });
  const head = `${venueShortDate(match.kickoff_local)} · ${t.primary}`;
  if (t.secondary === null) {
    return `<span>${escapeHtml(head)}</span>`;
  }
  return `<span>${escapeHtml(head)}</span>
          <span class="sep">·</span>
          <span class="tile-strip-viewer-time" title="Your local time">${escapeHtml(t.secondary.time)} ${escapeHtml(t.secondary.label)}</span>`;
}

export function renderTbdTile(match: MatchObject): string {
  const fd = match.teams.feeder_distributions;
  const scenarios = match.teams.tbd_scenarios ?? [];
  const slotContext = slotContextLabel(match);

  return `
    <article class="match-tile tbd-tile popularity-${match.popularity.tier}" id="match-${match.id}" data-signature="${match.signature}"
             aria-expanded="false">
      <header class="tile-strip">
        <span class="tile-strip-left">
          ${renderKickoffSegment(match)}
          <span class="sep">/</span>
          <span>${escapeHtml(match.host_city)}</span>
          <span class="sep">/</span>
          <span class="phase">${escapeHtml(phaseLabel(match.phase))}</span>
        </span>
        <span class="tile-strip-right">
          <span class="popularity popularity-badge-${match.popularity.tier}"
                title="${escapeHtml(match.popularity.rationale)}">
            ${escapeHtml(POPULARITY_LABEL[match.popularity.tier])}
          </span>
        </span>
      </header>
      <div class="tile-body">
        <div>
          <p class="tbd-context">${slotContext}</p>
          ${fd && fd.length > 0 ? renderFeeders(fd) : renderApproximationNotice()}
          ${scenarios.length > 0 ? renderCrossProduct(scenarios) : ""}
        </div>
        ${renderCountdownRing(match.days_to_decision)}
      </div>
      <div class="popularity-why">${escapeHtml(match.popularity.rationale)}</div>
      <footer class="tile-foot">
        <span class="tile-foot-meta">
          <span class="confidence">${escapeHtml(match.venue)} · Confidence <strong>${escapeHtml(match.confidence)}</strong></span>
        </span>
        <button type="button" class="tile-expand"
                aria-controls="match-${match.id}"
                data-expand-for="${match.id}">
          <span class="tile-expand-label" data-collapsed>View brief</span>
          <span class="tile-expand-label" data-expanded>Hide brief</span>
          <svg class="tile-expand-chevron" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </footer>
    </article>
  `;
}

function renderFeeders(fd: FeederDistribution[]): string {
  return `
    <div class="feeders">
      ${fd.map(renderOneFeeder).join("")}
    </div>
  `;
}

function renderOneFeeder(feeder: FeederDistribution): string {
  const top = feeder.teams.slice(0, 5);
  return `
    <div class="feeder">
      <div class="feeder-label">${escapeHtml(feeder.label)}</div>
      <div class="feeder-sublabel">% probability of filling this slot</div>
      <ul class="feeder-list">
        ${top.map((t, i) => renderFeederRow(t, i === 0)).join("")}
      </ul>
    </div>
  `;
}

function renderFeederRow(
  t: { code: string; name: string; probability: number },
  isLeader: boolean,
): string {
  const widthPct = (t.probability * 100).toFixed(1);
  const barStyle = `width: ${widthPct}%; background: ${probabilityBarBackground(t.probability)}`;
  return `
    <li class="feeder-row ${isLeader ? "is-leader" : ""}">
      <img class="flag-sm" src="${flagPath(t.code)}" alt="${escapeHtml(flagAltText(t.code, t.name))}" />
      <span class="feeder-name">${escapeHtml(t.name)}</span>
      <span class="feeder-bar"><span class="feeder-bar-fill" style="${barStyle}"></span></span>
      <span class="feeder-pct">${formatProbability(t.probability)}</span>
    </li>
  `;
}

function renderApproximationNotice(): string {
  return `
    <div class="feeder-approx-notice">
      Per-feeder distributions for this slot use a uniform-pool approximation —
      full bracket recursion is deferred for downstream knockouts. See cross-product top-3 below.
    </div>
  `;
}

function renderCrossProduct(scenarios: TbdScenario[]): string {
  return `
    <details class="cross-product">
      <summary>Most-likely specific matchups · top 3</summary>
      <div class="cp-sublabel">% probability of this exact matchup occurring</div>
      <ul class="cp-list">
        ${scenarios.map(renderCrossProductRow).join("")}
      </ul>
    </details>
  `;
}

function renderCrossProductRow(s: TbdScenario): string {
  const arrow = arrowFor(s.delta_pp);
  const widthPct = (s.probability * 100).toFixed(1);
  const barStyle = `width: ${widthPct}%; background: ${probabilityBarBackground(s.probability)}`;
  return `
    <li class="cp-row">
      <span class="cp-rank">${s.rank}</span>
      <img class="flag-sm" src="${flagPath(s.team_a.code)}" alt="${escapeHtml(flagAltText(s.team_a.code, s.team_a.name))}" />
      <span class="cp-name">${escapeHtml(s.team_a.name)}</span>
      <span class="cp-vs">vs</span>
      <img class="flag-sm" src="${flagPath(s.team_b.code)}" alt="${escapeHtml(flagAltText(s.team_b.code, s.team_b.name))}" />
      <span class="cp-name">${escapeHtml(s.team_b.name)}</span>
      <span class="cp-bar"><span class="cp-bar-fill" style="${barStyle}"></span></span>
      <span class="cp-pct">${formatProbability(s.probability)}</span>
      ${arrow}
    </li>
  `;
}

function arrowFor(delta_pp: number): string {
  if (delta_pp >= 3) return `<span class="delta delta-up" title="+${delta_pp.toFixed(1)}pp">▲</span>`;
  if (delta_pp <= -3) return `<span class="delta delta-down" title="${delta_pp.toFixed(1)}pp">▼</span>`;
  return "";
}

/**
 * Circular SVG countdown ring. Fills as the decision date approaches.
 * Visual progress: 30+ days = empty ring; 0 days = full ring.
 */
function renderCountdownRing(days: number | null): string {
  if (days === null) return "";
  // SVG radius 32, circumference ~201
  const RADIUS = 32;
  const CIRC = 2 * Math.PI * RADIUS;
  // Map days-to-decision (0..30) to fill fraction (1..0). Clamp at 30 days.
  const fillFraction = Math.max(0, Math.min(1, 1 - days / 30));
  const dashOffset = CIRC * (1 - fillFraction);

  let ringClass = "";
  if (days <= 1) ringClass = "urgent";
  else if (days <= 3) ringClass = "warn";

  return `
    <div class="tbd-side">
      <div class="ring ${ringClass}">
        <svg viewBox="0 0 80 80">
          <circle class="ring-track" cx="40" cy="40" r="${RADIUS}"></circle>
          <circle class="ring-fill" cx="40" cy="40" r="${RADIUS}"
                  stroke-dasharray="${CIRC.toFixed(2)}"
                  stroke-dashoffset="${dashOffset.toFixed(2)}"></circle>
        </svg>
        <div class="ring-label">
          <span class="ring-number">${days}</span>
          <span class="ring-unit">day${days === 1 ? "" : "s"}</span>
        </div>
      </div>
      <span class="tbd-side-label">Decides in</span>
    </div>
  `;
}

function slotContextLabel(match: MatchObject): string {
  const fd = match.teams.feeder_distributions;
  if (fd && fd.length === 2) {
    return `${escapeHtml(fd[0].label)} <em>×</em> ${escapeHtml(fd[1].label)}`;
  }
  if (fd && fd.length === 1) {
    return escapeHtml(fd[0].label);
  }
  return "TBD slot — feeders awaiting bracket resolution.";
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
