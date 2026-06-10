import { describe, expect, it, test } from "vitest";
import {
  formatProbability,
  formatLocalKickoff,
  computeWallClockFreshness,
  formatRefreshTimestamp,
} from "../utils/format.js";
import { POPULARITY_LABEL } from "../utils/format.js";

describe("formatProbability", () => {
  it("formats fractions to 1-decimal percent", () => {
    expect(formatProbability(0.643)).toBe("64.3%");
    expect(formatProbability(0)).toBe("0.0%");
    expect(formatProbability(1)).toBe("100.0%");
  });
});

describe("formatLocalKickoff", () => {
  it("renders date and time", () => {
    const out = formatLocalKickoff("2026-06-30T17:00:00-04:00");
    expect(out).toMatch(/Jun 30/);
    expect(out).toMatch(/5:00/);
  });
});

describe("computeWallClockFreshness", () => {
  it("returns fresh when generated_at is recent", () => {
    const now = new Date("2026-06-30T17:30:00Z");
    expect(
      computeWallClockFreshness("2026-06-30T17:25:00Z", "fresh", "group_stage", now),
    ).toBe("fresh");
  });

  it("returns stale when generated_at is older than threshold", () => {
    const now = new Date("2026-06-30T18:00:00Z");
    expect(
      computeWallClockFreshness("2026-06-30T17:00:00Z", "fresh", "group_stage", now),
    ).toBe("stale");
  });

  it("respects unreachable from server even when fresh by clock", () => {
    const now = new Date("2026-06-30T17:01:00Z");
    expect(
      computeWallClockFreshness("2026-06-30T17:00:00Z", "unreachable", "group_stage", now),
    ).toBe("unreachable");
  });

  it("knockout phase has tighter 20-minute threshold", () => {
    const now = new Date("2026-07-05T16:25:00Z");
    expect(
      computeWallClockFreshness("2026-07-05T16:00:00Z", "fresh", "round_of_16", now),
    ).toBe("stale");
  });
});

describe("POPULARITY_LABEL", () => {
  test("labels are the bare tier names", () => {
    expect(POPULARITY_LABEL.popular).toBe("Popular");
    expect(POPULARITY_LABEL.moderate).toBe("Moderate");
    expect(POPULARITY_LABEL.standard).toBe("Standard");
  });
});

describe("formatRefreshTimestamp", () => {
  // Same instant — 2026-06-04 01:28 UTC = 9:28 PM EDT = 6:28 PM PDT
  const UTC = "2026-06-04T01:28:00Z";

  it("renders in the viewer's zone with a short tz abbreviation", () => {
    expect(formatRefreshTimestamp(UTC, "America/New_York")).toBe("Jun 3 · 9:28 PM EDT");
  });

  it("re-localizes to a different viewer zone", () => {
    expect(formatRefreshTimestamp(UTC, "America/Los_Angeles")).toBe("Jun 3 · 6:28 PM PDT");
  });

  it("uses BST for a UK viewer in June", () => {
    expect(formatRefreshTimestamp(UTC, "Europe/London")).toBe("Jun 4 · 2:28 AM GMT+1");
  });

  it("returns the raw ISO on a malformed input", () => {
    expect(formatRefreshTimestamp("not-a-date", "America/New_York")).toBe("not-a-date");
  });
});
