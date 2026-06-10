import type { MatchObject } from "../types.js";
import { renderBracketFragment } from "./bracketFragment.js";
import { escapeHtml } from "../utils/escape.js";

export function renderExpandedDetail(match: MatchObject): string {
  return `
    <section class="expanded-detail">
      ${match.brief ? renderBrief(match.brief) : `<p class="expanded-empty">Brief not yet generated.</p>`}
      ${match.status === "tbd" ? renderBracketFragment(match) : ""}
    </section>
  `;
}

function renderBrief(brief: NonNullable<MatchObject["brief"]>): string {
  return `
    <div class="brief">
      <header class="brief-header">
        <span class="brief-eyebrow">Section I</span>
        <h3 class="brief-headline">${escapeHtml(brief.headline)}</h3>
      </header>
      ${brief.scenario_summary ? `<div class="brief-section brief-summary"><h4>Scenario summary</h4>${bulletize(brief.scenario_summary)}</div>` : ""}
      <div class="brief-grid">
        <div class="brief-section"><h4>Fan demographics</h4>${bulletize(brief.fan_demographics)}</div>
        <div class="brief-section"><h4>Traveling volume</h4>${bulletize(brief.traveling_volume_est)}</div>
        <div class="brief-section"><h4>Cultural context</h4>${bulletize(brief.cultural_context)}</div>
      </div>
    </div>
  `;
}

// Split prose into sentence-level bullets and bold scannable phrases
// (multi-word proper nouns, formatted quantities, clock times).
// Inputs are escaped first, so the bold-pass is safe against entities —
// proper nouns and numerals don't overlap with the entity vocabulary.
function bulletize(prose: string): string {
  const escaped = escapeHtml(prose);
  const sentences = escaped
    .split(/(?<=[.!?])\s+(?=[A-Z"])/)
    .map((s) => s.trim())
    .filter(Boolean);
  const items = sentences.map((s) => `<li>${emphasize(s)}</li>`).join("");
  return `<ul class="brief-bullets">${items}</ul>`;
}

function emphasize(text: string): string {
  let out = text;
  // Multi-word capitalized noun phrases: "Estadio Azteca", "Mexico City",
  // "Bafana Bafana", "South Africa". Requires lowercase after the initial
  // capital so all-caps tokens like "US" or "UTC" don't accidentally match.
  out = out.replace(
    /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/g,
    "<strong>$1</strong>",
  );
  // Comma-formatted quantities ("100,000"), with optional magnitude suffix.
  out = out.replace(
    /\b(\d{1,3}(?:,\d{3})+(?:\s+(?:million|thousand|billion))?)\b/gi,
    "<strong>$1</strong>",
  );
  // Plain quantities with a magnitude word ("37 million").
  out = out.replace(
    /\b(\d+(?:\.\d+)?\s+(?:million|thousand|billion))\b/gi,
    "<strong>$1</strong>",
  );
  // Clock times: "19:00 UTC", "13:00 local".
  out = out.replace(
    /\b(\d{1,2}:\d{2}(?:\s+(?:UTC|local|GMT|EST|PST|CET))?)\b/g,
    "<strong>$1</strong>",
  );
  return out;
}
