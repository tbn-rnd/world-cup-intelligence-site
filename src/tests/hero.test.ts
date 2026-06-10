import { describe, expect, test } from "vitest";
import { pickNextUpDay } from "../components/hero.js";
import type { MatchObject } from "../types.js";

function fixture(
  id: string,
  kickoffUtc: string,
  kickoffLocal: string,
  overrides: Partial<MatchObject> = {},
): MatchObject {
  return {
    id,
    kickoff_utc: kickoffUtc,
    kickoff_local: kickoffLocal,
    host_city: "TestCity",
    venue: "TestVenue",
    phase: "group_stage",
    status: "confirmed",
    popularity: { tier: "standard", rationale: "" },
    confidence: "certain",
    teams: { confirmed: null, tbd_scenarios: null, feeder_distributions: null },
    signature: "test",
    brief: null,
    prediction: null,
    decision_date: null,
    days_to_decision: null,
    ...overrides,
  };
}

describe("pickNextUpDay", () => {
  test("returns all matches on the next kickoff date, sorted by kickoff", () => {
    const matches = [
      fixture("late", "2026-06-11T22:00:00Z", "2026-06-11T17:00:00-05:00"),
      fixture("noon", "2026-06-11T17:00:00Z", "2026-06-11T12:00:00-05:00"),
      fixture("nextday", "2026-06-12T17:00:00Z", "2026-06-12T12:00:00-05:00"),
    ];
    const now = new Date("2026-06-11T10:00:00Z");
    const out = pickNextUpDay(matches, now);
    expect(out.map((m) => m.id)).toEqual(["noon", "late"]);
  });

  test("returns the next date's full slate when today is already over", () => {
    const matches = [
      fixture("yesterday", "2026-06-10T22:00:00Z", "2026-06-10T17:00:00-05:00"),
      fixture("tomA", "2026-06-12T17:00:00Z", "2026-06-12T12:00:00-05:00"),
      fixture("tomB", "2026-06-12T22:00:00Z", "2026-06-12T17:00:00-05:00"),
    ];
    const now = new Date("2026-06-11T10:00:00Z");
    const out = pickNextUpDay(matches, now);
    expect(out.map((m) => m.id)).toEqual(["tomA", "tomB"]);
  });

  test("excludes matches that kicked off more than 6h ago, even on the same date", () => {
    // A match early in the day already played > 6h ago shouldn't dominate
    // the "next" date selection.
    const matches = [
      fixture("longgone", "2026-06-11T02:00:00Z", "2026-06-11T21:00:00-05:00"),
      fixture("upcoming", "2026-06-11T22:00:00Z", "2026-06-11T17:00:00-05:00"),
    ];
    const now = new Date("2026-06-11T18:00:00Z");
    const out = pickNextUpDay(matches, now);
    // Both share kickoff_local date 2026-06-11, but the early one is >6h
    // past — only the upcoming one should make the slate.
    expect(out.map((m) => m.id)).toEqual(["upcoming"]);
  });

  test("returns empty when the tournament is over", () => {
    const matches = [
      fixture("done", "2026-06-10T22:00:00Z", "2026-06-10T17:00:00-05:00"),
    ];
    const now = new Date("2026-07-20T00:00:00Z");
    expect(pickNextUpDay(matches, now)).toEqual([]);
  });

  test("groups by the venue-local date — handles same UTC-day, different local-day", () => {
    // A late-night LA kickoff and an early-morning Mexico City kickoff
    // might sit on the same UTC date but different local dates.
    const matches = [
      fixture("la-late", "2026-06-12T03:00:00Z", "2026-06-11T20:00:00-07:00"),
      fixture("mex-noon", "2026-06-12T17:00:00Z", "2026-06-12T12:00:00-05:00"),
    ];
    const now = new Date("2026-06-11T18:00:00Z");
    const out = pickNextUpDay(matches, now);
    // The "next" date by venue-local kickoff is 2026-06-11 (LA evening).
    expect(out.map((m) => m.id)).toEqual(["la-late"]);
  });
});
