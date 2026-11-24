import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  einladungenRaeumen, geheimnisLesen, geheimnisMerken, offeneEinladung, offeneEinladungMerken, offeneEinladungVergessen,
} from "./einladung-merken";
import { speicherStub } from "./__testhilfen/speicher";

describe("Rückweg zur Einladung nach dem Bestätigen der Adresse", () => {
  beforeEach(() => { vi.stubGlobal("localStorage", speicherStub()); vi.stubGlobal("sessionStorage", speicherStub()); });
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

describe("Das Geheimnis aus dem Link im Browser", () => {
  beforeEach(() => { vi.stubGlobal("localStorage", speicherStub()); vi.stubGlobal("sessionStorage", speicherStub()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("überlebt einen neuen Tab, gehört dann dem ersten Konto — kein zweites bekommt es", () => {
    geheimnisMerken("e1", "geheim");
    sessionStorage.clear();                       // der neue Tab aus der Bestätigungsmail
    expect(geheimnisLesen("e1", null)).toBe("geheim");
    expect(geheimnisLesen("e1", 7)).toBe("geheim");
    expect(geheimnisLesen("e1", 8)).toBeNull();   // anderes Konto im selben Browser
    expect(geheimnisLesen("e1", 7)).toBeNull();   // … und danach ist es ganz weg
  });

  it("höchstens 48 Stunden, und das Abmelden räumt alles", () => {
    geheimnisMerken("e2", "a", Date.now() - 49 * 3_600_000);
    sessionStorage.clear();
    expect(geheimnisLesen("e2", null)).toBeNull();
    geheimnisMerken("e3", "b");
    geheimnisMerken("e4", "c");
    einladungenRaeumen();
    expect(geheimnisLesen("e3", null)).toBeNull();
    expect(geheimnisLesen("e4", null)).toBeNull();
    expect(offeneEinladung()).toBeNull();
  });
});
