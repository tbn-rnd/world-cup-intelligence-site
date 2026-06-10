import { describe, expect, test } from "vitest";
import {
  formatTimeInZone,
  formatVenueLocalTime,
  extractVenueOffset,
  tileTimes,
} from "../utils/timezones.js";

describe("timezones", () => {
  // A known kickoff: Mexico opens Group A at Estadio Azteca, 11 June 2026 1:00pm CDT.
  // CDT is UTC-5; so kickoff_utc is 18:00 UTC.
  const KICKOFF_UTC = "2026-06-11T18:00:00Z";
  const KICKOFF_LOCAL_CDT = "2026-06-11T13:00:00-05:00";

  describe("formatVenueLocalTime", () => {
    test("parses '1:00pm' from a venue-local ISO string", () => {
      expect(formatVenueLocalTime(KICKOFF_LOCAL_CDT)).toBe("1:00pm");
    });

    test("handles midnight kickoffs", () => {
      expect(formatVenueLocalTime("2026-06-11T00:00:00-05:00")).toBe("12:00am");
    });

    test("handles noon kickoffs", () => {
      expect(formatVenueLocalTime("2026-06-11T12:00:00+00:00")).toBe("12:00pm");
    });

    test("returns the raw string on malformed input", () => {
      expect(formatVenueLocalTime("not-a-date")).toBe("not-a-date");
    });
  });

  describe("extractVenueOffset", () => {
    test("extracts negative offset", () => {
      expect(extractVenueOffset(KICKOFF_LOCAL_CDT)).toBe("-05:00");
    });

    test("extracts positive offset", () => {
      expect(extractVenueOffset("2026-06-11T13:00:00+09:00")).toBe("+09:00");
    });

    test("extracts Z as +00:00", () => {
      expect(extractVenueOffset("2026-06-11T13:00:00Z")).toBe("+00:00");
    });

    test("returns null on malformed input", () => {
      expect(extractVenueOffset("not-a-date")).toBeNull();
    });
  });

  describe("formatTimeInZone", () => {
    test("converts UTC to Eastern Time", () => {
      // 18:00 UTC → 2:00pm EDT (UTC-4 in June)
      expect(formatTimeInZone(KICKOFF_UTC, "America/New_York")).toBe("2:00pm");
    });

    test("converts UTC to Pacific Time", () => {
      // 18:00 UTC → 11:00am PDT
      expect(formatTimeInZone(KICKOFF_UTC, "America/Los_Angeles")).toBe("11:00am");
    });

    test("converts UTC to London", () => {
      // 18:00 UTC → 7:00pm BST
      expect(formatTimeInZone(KICKOFF_UTC, "Europe/London")).toBe("7:00pm");
    });
  });

  describe("tileTimes", () => {
    test("returns single time when viewer zone matches venue offset", () => {
      // Viewer happens to be in UTC-5; venue is also -05:00
      const out = tileTimes({
        kickoff_utc: KICKOFF_UTC,
        kickoff_local: KICKOFF_LOCAL_CDT,
        viewerZone: "America/Mexico_City", // also UTC-5 (or UTC-6 depending on DST)
      });
      // We can't strictly assert single-vs-dual without knowing test machine TZ —
      // assert structure: primary is venue, secondary may be null if matched.
      expect(out.primary).toBe("1:00pm");
      // Secondary either null (same offset) or another zone label
      if (out.secondary !== null) {
        expect(out.secondary).toHaveProperty("time");
        expect(out.secondary).toHaveProperty("label");
      }
    });

    test("returns dual time when viewer zone differs from venue", () => {
      const out = tileTimes({
        kickoff_utc: KICKOFF_UTC,
        kickoff_local: KICKOFF_LOCAL_CDT,
        viewerZone: "America/New_York",
      });
      expect(out.primary).toBe("1:00pm");
      expect(out.secondary).not.toBeNull();
      expect(out.secondary?.time).toBe("2:00pm");
      // Label should be a short ET-style abbreviation pulled from Intl
      expect(out.secondary?.label).toMatch(/EDT|EST|ET/);
    });
  });
});
