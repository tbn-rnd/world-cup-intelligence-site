import { describe, expect, it, vi } from "vitest";
import { fetchMatches } from "../data/fetcher.js";

describe("fetchMatches", () => {
  it("returns parsed MatchesFile on success", async () => {
    const data = {
      generated_at: "2026-05-08T12:00:00Z",
      data_freshness: "fresh",
      tournament_phase: "pre_tournament",
      matches: [],
    };
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(data), { status: 200 }));
    const result = await fetchMatches("data/matches.json", fetchImpl);
    expect(result.kind).toBe("ok");
    if (result.kind === "ok") {
      expect(result.file.matches).toEqual([]);
    }
  });

  it("returns unreachable on network error", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("offline"));
    const result = await fetchMatches("data/matches.json", fetchImpl);
    expect(result.kind).toBe("unreachable");
  });

  it("returns unreachable on 5xx", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("err", { status: 503 }));
    const result = await fetchMatches("data/matches.json", fetchImpl);
    expect(result.kind).toBe("unreachable");
  });
});
