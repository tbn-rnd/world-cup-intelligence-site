export function renderFooter(opts: { generatedAt: string }): string {
  return `
    <div class="footer-inner">
      <div class="footer-left">World Cup 2026 · Insight Aggregator</div>
      <div class="footer-right">
        Data refreshed <span data-generated-at="${opts.generatedAt}">${opts.generatedAt}</span>
        · <a href="#ai-disclosure">AI · sources &amp; methodology</a>
      </div>
    </div>
  `;
}
