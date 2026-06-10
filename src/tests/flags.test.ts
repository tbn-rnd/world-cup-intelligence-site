import { describe, expect, it } from "vitest";
import { flagPath, flagAltText } from "../utils/flags.js";

describe("flags", () => {
  it("flagPath returns the expected static path", () => {
    expect(flagPath("MEX")).toBe("assets/flags/MEX.svg");
  });

  it("flagAltText prefers the team name when available", () => {
    expect(flagAltText("MEX", "Mexico")).toBe("Mexico flag");
    expect(flagAltText("MEX")).toBe("MEX flag");
  });
});
