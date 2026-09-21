import { describe, expect, it } from "vitest";

import { tastaturHoehe } from "./tastatur";

describe("Tastaturhöhe", () => {
  it("ist null, solange nichts verdeckt ist", () => {
    expect(tastaturHoehe({ height: 800, offsetTop: 0 }, 800)).toBe(0);
  });

  it("ist der verdeckte Streifen, wenn die Tastatur steht", () => {
    expect(tastaturHoehe({ height: 460, offsetTop: 0 }, 800)).toBe(340);
  });

  it("rechnet den verschobenen Ausschnitt mit", () => {
    // Safari scrollt den sichtbaren Ausschnitt nach unten, statt ihn zu
    // verkleinern — ohne `offsetTop` käme eine zu große Höhe heraus.
    expect(tastaturHoehe({ height: 460, offsetTop: 40 }, 800)).toBe(300);
  });

  it("ignoriert die ein- und ausfahrende Adressleiste", () => {
    // Sonst wackelte das Fenster bei jedem Scrollen.
    expect(tastaturHoehe({ height: 755, offsetTop: 0 }, 800)).toBe(0);
  });

  it("schiebt das Fenster nie über die halbe Höhe hinaus", () => {
    expect(tastaturHoehe({ height: 100, offsetTop: 0 }, 800)).toBe(400);
  });

  it("bleibt bei null, wo es keinen Viewport gibt", () => {
    // Ältere Browser und der Server-Durchlauf kennen `visualViewport` nicht.
    expect(tastaturHoehe(null, 800)).toBe(0);
    expect(tastaturHoehe(undefined, 800)).toBe(0);
    expect(tastaturHoehe({ height: 400, offsetTop: 0 }, 0)).toBe(0);
  });
});
