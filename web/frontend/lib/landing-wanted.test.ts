import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";
import { EARLY_LANDING_SCRIPT, LANDING_WANTED_KEY } from "./landing-wanted";
import { speicherStub } from "./__testhilfen/speicher";

/** Führt das <head>-Skript so aus, wie der Browser es täte: in einem eigenen
 *  Kontext, der nur eine Adresse und einen Speicher kennt. Das Skript ist eine
 *  Konstante dieses Repos, keine Eingabe. */
function ausfuehren(pathname: string, search: string, speicher = speicherStub()) {
  runInNewContext(EARLY_LANDING_SCRIPT, { location: { pathname, search }, sessionStorage: speicher, URLSearchParams });
  return speicher;
}

describe("EARLY_LANDING_SCRIPT", () => {
  it("merkt sich die Fluchttür, bevor irgendetwas hydriert ist", () => {
    expect(ausfuehren("/", "?start=1").getItem(LANDING_WANTED_KEY)).toBe("1");
    // Der Rückfall im Browser fragt `get("start") != null` — ein Parameter
    // ohne Wert zählt dort, also auch hier.
    expect(ausfuehren("/", "?start").getItem(LANDING_WANTED_KEY)).toBe("1");
    expect(ausfuehren("/", "?utm=x&start=1").getItem(LANDING_WANTED_KEY)).toBe("1");
  });

  it("setzt ohne den Parameter nichts", () => {
    expect(ausfuehren("/", "").getItem(LANDING_WANTED_KEY)).toBeNull();
    expect(ausfuehren("/", "?restart=1").getItem(LANDING_WANTED_KEY)).toBeNull();
  });

  it("gilt nur für die Startseite", () => {
    expect(ausfuehren("/dashboard", "?start=1").getItem(LANDING_WANTED_KEY)).toBeNull();
    expect(ausfuehren("/council", "?start=1").getItem(LANDING_WANTED_KEY)).toBeNull();
  });

  it("stört die Seite nicht, wenn der Speicher gesperrt ist", () => {
    const gesperrt = speicherStub();
    gesperrt.kaputt(true);
    expect(() => ausfuehren("/", "?start=1", gesperrt)).not.toThrow();
  });
});
