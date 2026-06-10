import { describe, expect, test } from "vitest";
import { applyFilters, DEFAULT_FILTERS } from "../components/filters.js";
import type { MatchObject } from "../types.js";

function confirmed(overrides: Partial<MatchObject> = {}): MatchObject {
  return {
    id: "atl-2026-06-18-rsa-cze",
    kickoff_utc: "2026-06-18T16:00:00Z",
    kickoff_local: "2026-06-18T12:00:00-04:00",
    host_city: "Atlanta",
    venue: "Mercedes-Benz Stadium",
    phase: "group_stage",
    status: "confirmed",
    popularity: { tier: "standard", rationale: "" },
    confidence: "certain",
    teams: {
      confirmed: [
        { code: "RSA", name: "South Africa", fifa_rank: 60 },
        { code: "CZE", name: "Czechia", fifa_rank: 41 },
      ],
      tbd_scenarios: null,
      feeder_distributions: null,
    },
    signature: "v3:confirmed:CZE-RSA",
    brief: null,
    prediction: null,
    decision_date: null,
    days_to_decision: null,
    ...overrides,
  };
}

function tbd(overrides: Partial<MatchObject> = {}): MatchObject {
  return {
    id: "nyc-2026-07-11-sf1",
    kickoff_utc: "2026-07-11T19:00:00Z",
    kickoff_local: "2026-07-11T15:00:00-04:00",
    host_city: "New York",
    venue: "MetLife Stadium",
    phase: "semi_final",
    status: "tbd",
    popularity: { tier: "popular", rationale: "" },
    confidence: "medium",
    teams: {
      confirmed: null,
      tbd_scenarios: null,
      feeder_distributions: [
        {
          label: "QF1 winner",
          teams: [
            { code: "BRA", name: "Brazil", probability: 0.42 },
            { code: "ARG", name: "Argentina", probability: 0.18 },
            { code: "URU", name: "Uruguay", probability: 0.1 },
          ],
        },
        {
          label: "QF2 winner",
          teams: [
            { code: "ENG", name: "England", probability: 0.31 },
            { code: "FRA", name: "France", probability: 0.22 },
          ],
        },
      ],
    },
    signature: "v3:tbd:top1=BRA-ENG:bucket=10-15:set=ARG,BRA,ENG,FRA,URU:conf=medium",
    brief: null,
    prediction: null,
    decision_date: "2026-07-04",
    days_to_decision: 7,
    ...overrides,
  };
}

describe("applyFilters", () => {
  test("defaults pass everything through", () => {
    const matches = [confirmed(), tbd()];
    expect(applyFilters(matches, DEFAULT_FILTERS)).toHaveLength(2);
  });

  test("city filter narrows to host city", () => {
    const matches = [confirmed({ host_city: "Atlanta" }), confirmed({ id: "x", host_city: "Dallas" })];
    expect(applyFilters(matches, { ...DEFAULT_FILTERS, city: "Atlanta" })).toHaveLength(1);
  });

  test("popularity filter narrows to tier", () => {
    const matches = [
      confirmed({ popularity: { tier: "popular", rationale: "" } }),
      confirmed({ id: "x", popularity: { tier: "standard", rationale: "" } }),
    ];
    expect(applyFilters(matches, { ...DEFAULT_FILTERS, popularity: "popular" })).toHaveLength(1);
  });

  describe("team filter", () => {
    test("matches confirmed teams by code", () => {
      const matches = [
        confirmed(), // RSA + CZE
        confirmed({ id: "x", teams: { confirmed: [{ code: "BRA", name: "Brazil", fifa_rank: 5 }, { code: "ARG", name: "Argentina", fifa_rank: 1 }], tbd_scenarios: null, feeder_distributions: null } }),
      ];
      const out = applyFilters(matches, { ...DEFAULT_FILTERS, team: "BRA" });
      expect(out).toHaveLength(1);
      expect(out[0].id).toBe("x");
    });

    test("matches TBD slots where the team appears in any feeder distribution", () => {
      const matches = [tbd(), confirmed()];
      const out = applyFilters(matches, { ...DEFAULT_FILTERS, team: "ENG" });
      expect(out).toHaveLength(1);
      expect(out[0].status).toBe("tbd");
    });

    test("returns empty when team appears in nothing", () => {
      const matches = [confirmed(), tbd()];
      expect(applyFilters(matches, { ...DEFAULT_FILTERS, team: "JPN" })).toHaveLength(0);
    });

    test("'all' is a no-op", () => {
      const matches = [confirmed(), tbd()];
      expect(applyFilters(matches, { ...DEFAULT_FILTERS, team: "all" })).toHaveLength(2);
    });

    test("composes with other filters (intersection)", () => {
      // Two BRA matches in different cities; team+city should AND
      const matches = [
        confirmed({ id: "a", host_city: "Miami", teams: { confirmed: [{ code: "BRA", name: "Brazil", fifa_rank: 5 }, { code: "MEX", name: "Mexico", fifa_rank: 14 }], tbd_scenarios: null, feeder_distributions: null } }),
        confirmed({ id: "b", host_city: "Dallas", teams: { confirmed: [{ code: "BRA", name: "Brazil", fifa_rank: 5 }, { code: "USA", name: "United States", fifa_rank: 16 }], tbd_scenarios: null, feeder_distributions: null } }),
      ];
      const out = applyFilters(matches, { ...DEFAULT_FILTERS, team: "BRA", city: "Dallas" });
      expect(out).toHaveLength(1);
      expect(out[0].id).toBe("b");
    });
  });
});
