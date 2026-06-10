import type { DataFreshness } from "../types.js";
import { formatRefreshTimestamp } from "../utils/format.js";

export function renderHeader(opts: {
  generatedAt: string;
  freshness: DataFreshness;
}): string {
  // Fresh and stale both render as a plain "Last refreshed" stamp;
  // unreachable prefixes "Offline ·". No status dot — the timestamp
  // alone is the freshness signal.
  const stamp = formatRefreshTimestamp(opts.generatedAt);
  const text =
    opts.freshness === "unreachable"
      ? `Offline · last refreshed ${stamp}`
      : `Last refreshed ${stamp}`;
  return `
    <div class="brand">
      <span class="brand-eyebrow">World Cup 2026</span>
      <span class="brand-mark"><em>Insight Aggregator</em></span>
    </div>
    <div class="header-nav">
      <a class="header-nav-link" href="guide.html" aria-label="Open the navigation guide">
        <svg class="header-nav-icon" viewBox="0 0 20 20" aria-hidden="true">
          <!-- Open-book glyph drawn with two leaves meeting at the spine.
               Two crisp curves + a center spine read clearly even at 14px. -->
          <path d="M2.5 4.5 C5 4 7.5 4 10 5.5 C12.5 4 15 4 17.5 4.5 L17.5 15.5 C15 15 12.5 15 10 16.5 C7.5 15 5 15 2.5 15.5 Z"
                fill="none" stroke="currentColor" stroke-width="1.4"
                stroke-linejoin="round" stroke-linecap="round"/>
          <path d="M10 5.5 L10 16.5" stroke="currentColor" stroke-width="1.4"
                stroke-linecap="round"/>
        </svg>
        <span>Click here for navigation guide</span>
      </a>
    </div>
    <div class="header-meta">
      <span class="header-status" title="generated ${opts.generatedAt}">
        <span>${text}</span>
      </span>
    </div>
  `;
}
