import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { aufzaehlung, istNichtGefunden, rueckmeldungsFehler, standZeilen } from "./ideen";

describe("standZeilen", () => {
  it("nennt den Stand und eine hinterherhinkende Stadt", () => {
    const z = standZeilen({
      as_of: "2026-09-10",
      lagging: [{ body_id: "wolfsburg", city: "Wolfsburg", latest_paper: "2026-06-25" }],
    });
    expect(z.stand).toBe("Stand: 10.09.2026");
    expect(z.luecke).toBe("Aus Wolfsburg liegen Vorlagen nur bis 25.06.2026 vor.");
  });

  it("zählt mehrere Städte als Satz auf", () => {
    const z = standZeilen({
      as_of: "2026-09-10",
      lagging: [
        { body_id: "a", city: "Langenhagen", latest_paper: "2026-06-19" },
        { body_id: "b", city: "Wolfsburg", latest_paper: "2026-06-25" },
      ],
    });
    expect(z.luecke).toContain("Langenhagen (bis 19.06.2026) und Wolfsburg (bis 25.06.2026)");
  });

  it("erfindet ohne Abgleich kein Datum", () => {
    expect(standZeilen({ as_of: null, lagging: [] })).toEqual({ stand: null, luecke: null });
    expect(standZeilen(undefined)).toEqual({ stand: null, luecke: null });
  });

  it("verspricht keinen Takt", () => {
    const z = standZeilen({ as_of: "2026-09-10", lagging: [] });
    expect(`${z.stand} ${z.luecke ?? ""}`).not.toMatch(/wöchentlich|täglich|monatlich/);
  });
});

describe("rueckmeldungsFehler", () => {
  it("unterscheidet fehlendes Konto, unbestätigtes Konto und Bremse", () => {
    expect(rueckmeldungsFehler(new ApiError(401, "x"))).toMatch(/Konto\./);
    expect(rueckmeldungsFehler(new ApiError(403, "x"))).toMatch(/bestätigt/);
    expect(rueckmeldungsFehler(new ApiError(429, "x"))).toMatch(/zu viele/);
    expect(rueckmeldungsFehler(new Error("Netz"))).toMatch(/nicht geklappt/);
  });
});

describe("istNichtGefunden", () => {
  it("nur ein 404 heißt „gibt es nicht“", () => {
    expect(istNichtGefunden(new ApiError(404, "x"))).toBe(true);
    expect(istNichtGefunden(new ApiError(500, "x"))).toBe(false);
    expect(istNichtGefunden(new TypeError("Failed to fetch"))).toBe(false);
  });
});

describe("aufzaehlung", () => {
  it("setzt das „und“ vor die letzte", () => {
    expect(aufzaehlung([])).toBe("");
    expect(aufzaehlung(["A"])).toBe("A");
    expect(aufzaehlung(["A", "B", "C"])).toBe("A, B und C");
  });
});
