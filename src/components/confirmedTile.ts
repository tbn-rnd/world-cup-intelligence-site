import type { ConfirmedTeam, MatchObject } from "../types.js";
import { flagPath, flagAltText } from "../utils/flags.js";
import { escapeHtml } from "../utils/escape.js";
import { POPULARITY_LABEL, formatProbability, probabilityBarBackground } from "../utils/format.js";
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
  // Second time chip is rendered in the same strip but tagged so CSS can
  // de-emphasize it relative to the venue-local primary.
  return `<span>${escapeHtml(head)}</span>
          <span class="sep">·</span>
          <span class="tile-strip-viewer-time" title="Your local time">${escapeHtml(t.secondary.time)} ${escapeHtml(t.secondary.label)}</span>`;
}


export function renderConfirmedTile(match: MatchObject): string {
  if (match.teams.confirmed === null || match.teams.confirmed.length !== 2) {
    return `<div class="match-tile error">invalid confirmed match: ${match.id}</div>`;
  }
  const [a, b] = match.teams.confirmed;
  const tier = match.popularity.tier;
  const tierLabel = POPULARITY_LABEL[tier];

  return `
    <article class="match-tile confirmed-tile popularity-${tier}"
             id="match-${match.id}" data-signature="${match.signature}"
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
      ${match.prediction ? renderPrediction(match.prediction) : ""}
      <div class="popularity-why">${escapeHtml(match.popularity.rationale)}</div>
      <footer class="tile-foot">
        <span class="tile-foot-meta">
          <span class="venue">${escapeHtml(match.venue)}</span>
        </span>
        ${expandButton(match.id)}
      </footer>
    </article>
  `;
}

function expandButton(id: string): string {
  return `
    <button type="button" class="tile-expand"
            aria-controls="match-${id}"
            data-expand-for="${id}">
      <span class="tile-expand-label" data-collapsed>View brief</span>
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

function renderPrediction(pred: NonNullable<MatchObject["prediction"]>): string {
  const rows = pred.teams.map((t) => predictionRow(t.name, t.win_prob));
  if (pred.draw_prob !== null) {
    rows.splice(1, 0, predictionRow("Draw", pred.draw_prob));
  }
  return `
    <div class="prediction">
      <div class="prediction-label">Win probability</div>
      <ul class="prediction-list">${rows.join("")}</ul>
      <div class="prediction-caption">Model estimate from FIFA ranking</div>
    </div>
  `;
}

function predictionRow(label: string, p: number): string {
  const widthPct = (p * 100).toFixed(1);
  const barStyle = `width: ${widthPct}%; background: ${probabilityBarBackground(p)}`;
  return `
    <li class="prediction-row">
      <span class="prediction-name">${escapeHtml(label)}</span>
      <span class="prediction-bar"><span class="prediction-bar-fill" style="${barStyle}"></span></span>
      <span class="prediction-pct">${formatProbability(p)}</span>
    </li>
  `;
}
