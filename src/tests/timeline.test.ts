import { describe, expect, it } from "vitest";

import { computeTimelineSummary, renderTimeline } from "../components/timeline.js";
import type { MatchObject, Phase, Status, PopularityTier } from "../types.js";

function makeMatch(
  id: string,
  kickoffUtc: string,
  phase: Phase,
  status: Status,
  tier: PopularityTier = "standard",
): MatchObject {
  return {
    id,
    kickoff_utc: kickoffUtc,
    kickoff_local: kickoffUtc,
    host_city: "TestCity",
    venue: "TestVenue",
    phase,
    status,
    popularity: { tier, rationale: "test" },
    confidence: "certain",
    teams: { confirmed: null, tbd_scenarios: null, feeder_distributions: null },
    signature: "test",
    brief: null,
    prediction: null,
    decision_date: null,
    days_to_decision: null,
  };
}

describe("computeTimelineSummary", () => {
  it("countdown phase: days countdown + global totals", () => {
    const matches = [
      makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("b", "2026-07-19T18:00:00Z", "final", "tbd"),
    ];
    const now = new Date("2026-06-03T18:00:00Z");
    const s = computeTimelineSummary(matches, matches, false, now);
    expect(s.phaseLabel).toBe("Countdown");
    expect(s.countdown).toBe("Next kickoff in 8d");
    expect(s.totalsLine).toBe("2 matches · 1 confirmed · 1 TBD");
  });

  it("tournament active: phase-active label + hours countdown when <24h", () => {
    const matches = [
      makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("b", "2026-06-12T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("c", "2026-07-19T18:00:00Z", "final", "tbd"),
    ];
    // a is already played; b kicks off in 10h; c is far away
    const now = new Date("2026-06-12T08:00:00Z");
    const s = computeTimelineSummary(matches, matches, false, now);
    expect(s.phaseLabel).toBe("Group Stage active");
    expect(s.countdown).toBe("Next kickoff in 10h");
  });

  it("filter active: countdown and totals reflect filtered subset", () => {
    const matches = [
      makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("b", "2026-06-20T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("c", "2026-07-19T18:00:00Z", "final", "tbd"),
    ];
    const filtered = [matches[1]]; // only b
    const now = new Date("2026-06-03T18:00:00Z");
    const s = computeTimelineSummary(matches, filtered, true, now);
    expect(s.countdown).toBe("Next kickoff in 17d");
    expect(s.totalsLine).toBe("1 of 3 · 1 confirmed · 0 TBD");
  });

  it("filter with no upcoming match: explicit empty label", () => {
    const matches = [
      makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("b", "2026-06-20T18:00:00Z", "group_stage", "confirmed"),
    ];
    const now = new Date("2026-06-03T18:00:00Z");
    const s = computeTimelineSummary(matches, [], true, now);
    expect(s.countdown).toBe("No upcoming matches in filter");
    expect(s.totalsLine).toBe("0 of 2 · 0 confirmed · 0 TBD");
  });

  it("tournament complete: no countdown", () => {
    const matches = [
      makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed"),
      makeMatch("b", "2026-07-19T18:00:00Z", "final", "confirmed"),
    ];
    const now = new Date("2026-08-01T00:00:00Z");
    const s = computeTimelineSummary(matches, matches, false, now);
    expect(s.phaseLabel).toBe("Tournament Complete");
    expect(s.countdown).toBeNull();
    expect(s.totalsLine).toBe("2 matches · 2 confirmed · 0 TBD");
  });
});

describe("renderTimeline", () => {
  it("emits a tl-banner element with phase, countdown, and totals spans", () => {
    const matches = [makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed")];
    const html = renderTimeline(matches, matches, false, new Date("2026-06-03T18:00:00Z"));
    expect(html).toContain('class="tl-banner"');
    expect(html).toContain('class="tl-phase"');
    expect(html).toContain('class="tl-countdown"');
    expect(html).toContain('class="tl-totals"');
    expect(html).toContain("Countdown");
    expect(html).toContain("Next kickoff in 8d");
  });

  it("omits the countdown span when the tournament is complete", () => {
    const matches = [makeMatch("a", "2026-06-11T18:00:00Z", "group_stage", "confirmed")];
    const html = renderTimeline(matches, matches, false, new Date("2026-08-01T00:00:00Z"));
    expect(html).toContain('class="tl-phase"');
    expect(html).not.toContain('class="tl-countdown"');
    expect(html).toContain('class="tl-totals"');
  });
});
