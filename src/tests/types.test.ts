import { describe, expect, it } from "vitest";
import type { MatchObject, MatchesFile } from "../types.js";

describe("types", () => {
  it("MatchObject narrows correctly via status discriminator", () => {
    const m: MatchObject = {
      id: "x",
      kickoff_utc: "2026-06-30T21:00:00Z",
      kickoff_local: "2026-06-30T17:00:00-04:00",
      host_city: "NY/NJ",
      venue: "MetLife Stadium",
      phase: "round_of_32",
      status: "tbd",
      popularity: {
        tier: "popular",
        rationale: "High-profile knockout featuring potential top-10 sides.",
      },
      confidence: "low",
      teams: {
        confirmed: null,
        tbd_scenarios: [
          {
            rank: 1,
            team_a: { code: "MEX", name: "Mexico" },
            team_b: { code: "NED", name: "Netherlands" },
            probability: 0.11,
            delta_pp: 0,
            rationale: "r",
          },
        ],
        feeder_distributions: null,
      },
      signature: "v2:tbd:...",
      brief: null,
      prediction: null,
      decision_date: "2026-06-27",
      days_to_decision: 3,
    };
    expect(m.status).toBe("tbd");
    expect(m.popularity.tier).toBe("popular");
  });

  it("MatchesFile has matches array", () => {
    const f: MatchesFile = {
      generated_at: "2026-05-08T12:00:00Z",
      data_freshness: "fresh",
      tournament_phase: "pre_tournament",
      matches: [],
    };
    expect(f.matches).toHaveLength(0);
  });
});
