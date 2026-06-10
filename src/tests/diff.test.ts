import { describe, expect, it } from "vitest";
import { signaturesByMatchId, changedMatchIds } from "../data/diff.js";
import type { MatchesFile, MatchObject, PopularityTier } from "../types.js";

const minimal = (
  id: string,
  signature: string,
  tier: PopularityTier = "popular",
): MatchObject => ({
  id,
  kickoff_utc: "2026-06-30T21:00:00Z",
  kickoff_local: "2026-06-30T17:00:00-04:00",
  host_city: "NY/NJ",
  venue: "V",
  phase: "round_of_32",
  status: "confirmed",
  popularity: { tier, rationale: "r" },
  confidence: "certain",
  teams: {
    confirmed: [
      { code: "USA", name: "USA", fifa_rank: 1 },
      { code: "POR", name: "Portugal", fifa_rank: 2 },
    ],
    tbd_scenarios: null,
    feeder_distributions: null,
  },
  signature,
  brief: null,
  prediction: null,
  decision_date: null,
  days_to_decision: null,
});

const fileWith = (matches: MatchObject[]): MatchesFile => ({
  generated_at: "2026-05-08T12:00:00Z",
  data_freshness: "fresh",
  tournament_phase: "pre_tournament",
  matches,
});

describe("signaturesByMatchId", () => {
  it("indexes by id", () => {
    const f = fileWith([minimal("a", "s1"), minimal("b", "s2")]);
    const idx = signaturesByMatchId(f);
    expect(idx.get("a")).toBe("s1");
    expect(idx.get("b")).toBe("s2");
  });
});

describe("changedMatchIds", () => {
  it("returns all match ids on first render (no previous)", () => {
    const next = fileWith([minimal("a", "s1"), minimal("b", "s1")]);
    expect(changedMatchIds(null, next)).toEqual(["a", "b"]);
  });

  it("returns only matches whose signature changed", () => {
    const prev = fileWith([minimal("a", "s1"), minimal("b", "s2")]);
    const next = fileWith([minimal("a", "s1"), minimal("b", "s3")]);
    expect(changedMatchIds(prev, next)).toEqual(["b"]);
  });

  it("returns new match ids that didn't exist before", () => {
    const prev = fileWith([minimal("a", "s1")]);
    const next = fileWith([minimal("a", "s1"), minimal("c", "sX")]);
    expect(changedMatchIds(prev, next)).toEqual(["c"]);
  });

  it("moderate-tier match still triggers a re-render when its signature changes", () => {
    const prev = fileWith([minimal("moderate-match", "s1", "moderate")]);
    const next = fileWith([minimal("moderate-match", "s2", "moderate")]);
    const ids = changedMatchIds(prev, next);
    expect(ids).toContain("moderate-match");
  });

  it("standard-tier match still triggers a re-render when its signature changes", () => {
    const prev = fileWith([minimal("standard-match", "s1", "standard")]);
    const next = fileWith([minimal("standard-match", "s2", "standard")]);
    const ids = changedMatchIds(prev, next);
    expect(ids).toContain("standard-match");
  });
});
