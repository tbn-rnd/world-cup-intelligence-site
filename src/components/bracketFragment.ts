import type { MatchObject } from "../types.js";
import { escapeHtml } from "../utils/escape.js";

export function renderBracketFragment(match: MatchObject): string {
  const fd = match.teams.feeder_distributions;
  if (!fd || fd.length === 0) return "";
  const labels = fd.map((f) => f.label);

  return `
    <svg class="bracket-fragment" viewBox="0 0 480 140" role="img"
         aria-label="Bracket position diagram for ${match.id}">
      ${labels[0] ? feederBox(20, 16, labels[0]) : ""}
      ${labels[1] ? feederBox(20, 84, labels[1]) : ""}
      <line x1="200" y1="40" x2="280" y2="60" stroke="#cbd2dc" stroke-width="2"/>
      <line x1="200" y1="108" x2="280" y2="80" stroke="#cbd2dc" stroke-width="2"/>
      ${centerBox(280, 50, match)}
    </svg>
  `;
}

function feederBox(x: number, y: number, label: string): string {
  return `
    <g>
      <rect x="${x}" y="${y}" width="180" height="48" rx="6"
            fill="#f1f3f6" stroke="#cbd2dc" />
      <text x="${x + 12}" y="${y + 28}" font-size="12" font-family="sans-serif"
            fill="#0f172a">${escapeHtml(label)}</text>
    </g>
  `;
}

function centerBox(x: number, y: number, m: MatchObject): string {
  const phaseLabel = m.phase.replace(/_/g, " ");
  return `
    <g>
      <rect x="${x}" y="${y}" width="180" height="48" rx="6"
            fill="#002c5f" stroke="#002c5f" />
      <text x="${x + 12}" y="${y + 22}" font-size="12" font-family="sans-serif"
            fill="#ffffff" font-weight="600">${escapeHtml(phaseLabel)}</text>
      <text x="${x + 12}" y="${y + 38}" font-size="11" font-family="sans-serif"
            fill="#cdd9e6">${escapeHtml(m.host_city)}</text>
    </g>
  `;
}

