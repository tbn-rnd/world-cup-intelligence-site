/**
 * Floating "back to top" affordance. The dashboard list runs long
 * (~104 tiles); after a long scroll the only way home is a full-page
 * swipe up. This puts a small memo-style button bottom-right so a
 * user one click away from the banner.
 *
 * Aesthetically the button reads as part of the existing card system:
 * cream surface, navy text, the same shadow stack as a tile. On hover
 * it inverts to the navy/champagne palette used everywhere else for
 * emphasis.
 */
export function renderBackToTop(): string {
  return `
    <button type="button" class="back-to-top" aria-label="Back to top">
      <span class="back-to-top-arrow" aria-hidden="true">↑</span>
      <span class="back-to-top-label">Top</span>
    </button>
  `;
}

export function attachBackToTop(root: ParentNode = document): void {
  const button = root.querySelector<HTMLButtonElement>(".back-to-top");
  if (!button) return;
  button.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}
