import { describe, expect, test } from "vitest";
import { renderConfirmedTile } from "../components/confirmedTile.js";
import type { MatchObject } from "../types.js";

function fixture(overrides: Partial<MatchObject> = {}): MatchObject {
  return {
    id: "atl-2026-06-18-rsa-cze",
    kickoff_utc: "2026-06-18T16:00:00Z",
    kickoff_local: "2026-06-18T12:00:00-04:00",
    host_city: "Atlanta",
    venue: "Mercedes-Benz Stadium",
    phase: "group_stage",
    status: "confirmed",
    popularity: { tier: "standard", rationale: "Group stage; teams outside top 25." },
    confidence: "certain",
    teams: {
      confirmed: [
        { code: "RSA", name: "South Africa", fifa_rank: 60 },
        { code: "CZE", name: "Czechia", fifa_rank: 41 },
      ],
      tbd_scenarios: null,
      feeder_distributions: null,
    },
    signature: "v2:confirmed:CZE-RSA",
    brief: null,
    prediction: null,
    decision_date: null,
    days_to_decision: null,
    ...overrides,
  };
}

describe("renderConfirmedTile", () => {
  test("standard tile includes the View brief expander", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "standard", rationale: "x" } }));
    expect(html).toContain('class="tile-expand"');
    expect(html).toContain("View brief");
    expect(html).not.toContain("View brief &amp; prep");
    expect(html).toContain('class="popularity popularity-badge-standard"');
  });

  test("moderate tile includes the View brief expander", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "moderate", rationale: "x" } }));
    expect(html).toContain('class="tile-expand"');
    expect(html).toContain('class="popularity popularity-badge-moderate"');
  });

  test("full tile (popular) includes expand button", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "popular", rationale: "x" } }));
    expect(html).toContain('class="tile-expand"');
    expect(html).toContain('class="popularity popularity-badge-popular"');
  });

  test("popularity rationale is rendered as text", () => {
    const html = renderConfirmedTile(fixture({ popularity: { tier: "popular", rationale: "Brazil draws a global audience." } }));
    expect(html).toContain("Brazil draws a global audience.");
  });

  test("renders win-probability bars with a draw row for group stage", () => {
    const html = renderConfirmedTile(
      fixture({
        phase: "group_stage",
        prediction: {
          method: "fifa_rank_elo",
          teams: [
            { code: "RSA", name: "South Africa", win_prob: 0.4 },
            { code: "CZE", name: "Czechia", win_prob: 0.3 },
          ],
          draw_prob: 0.3,
        },
      }),
    );
    expect(html).toContain('class="prediction"');
    expect(html).toContain("Win probability");
    expect(html).toContain("40.0%");
    expect(html).toContain("30.0%");
    expect(html).toContain("Draw");
    expect(html).toContain("Model estimate from FIFA ranking");
  });

  test("omits the draw row when draw_prob is null (knockout)", () => {
    const html = renderConfirmedTile(
      fixture({
        phase: "round_of_16",
        prediction: {
          method: "fifa_rank_elo",
          teams: [
            { code: "RSA", name: "South Africa", win_prob: 0.55 },
            { code: "CZE", name: "Czechia", win_prob: 0.45 },
          ],
          draw_prob: null,
        },
      }),
    );
    expect(html).toContain('class="prediction"');
    expect(html).toContain("55.0%");
    expect(html).toContain("45.0%");
    expect(html).not.toContain(">Draw<");
  });
});
