import { describe, expect, it } from "vitest";

import { gemeldeterSetupSchritt, LETZTER_SETUP_SCHRITT } from "./onboarding-setup";

describe("gemeldeterSetupSchritt", () => {
  it("meldet die Pfad-Schritte unverändert", () => {
    for (const s of [0, 1, 2, 3, 4]) expect(gemeldeterSetupSchritt(s)).toBe(s);
  });

  it("meldet das Auffangnetz (Schritt 5) als letzten echten Schritt — sonst 422", () => {
    expect(gemeldeterSetupSchritt(5)).toBe(LETZTER_SETUP_SCHRITT);
  });

  it("bleibt in der Spanne, die das Backend annimmt (SetupUpdate: ge=0, le=4)", () => {
    expect(gemeldeterSetupSchritt(-1)).toBe(0);
    expect(LETZTER_SETUP_SCHRITT).toBe(4);
  });
});
