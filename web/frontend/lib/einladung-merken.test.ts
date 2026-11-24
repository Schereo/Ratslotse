import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { offeneEinladung, offeneEinladungMerken, offeneEinladungVergessen } from "./einladung-merken";
import { speicherStub } from "./__testhilfen/speicher";

describe("Rückweg zur Einladung nach dem Bestätigen der Adresse", () => {
  beforeEach(() => { vi.stubGlobal("localStorage", speicherStub()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("führt zur gemerkten Einladungsseite zurück, höchstens acht Tage lang", () => {
    expect(offeneEinladung()).toBeNull();
    offeneEinladungMerken("/notiz-einladung?i=abc_DEF-12");
    expect(offeneEinladung()).toBe("/notiz-einladung?i=abc_DEF-12");
    expect(offeneEinladung(Date.now() + 9 * 86_400_000)).toBeNull();
    offeneEinladungVergessen();
    expect(offeneEinladung()).toBeNull();
  });

  it("nie zu einem beliebigen Ziel", () => {
    for (const pfad of ["https://boese.example.org/", "//boese.example.org", "/dashboard", "/notiz-einladung?i=x&weiter=/admin"]) {
      offeneEinladungMerken(pfad);
      expect(offeneEinladung()).toBeNull();
    }
  });
});
