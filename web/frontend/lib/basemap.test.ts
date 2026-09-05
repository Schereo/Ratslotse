import { afterEach, describe, expect, it, vi } from "vitest";

// Die Kachel-URL ist die Stelle, an der ein Tippfehler NICHT als Fehler
// auffällt: CARTO liefert auch ohne (oder mit falsch benanntem) Key Status 200
// — nur mit einem „API KEY REQUIRED" quer über jedem PNG, eingebrannt.
// Deshalb wird hier die URL geprüft und nicht die Karte angeschaut.

async function frisch(key: string | undefined) {
  vi.resetModules();                    // KEY wird beim Modul-Import gelesen
  if (key === undefined) vi.stubEnv("NEXT_PUBLIC_CARTO_API_KEY", "");
  else vi.stubEnv("NEXT_PUBLIC_CARTO_API_KEY", key);
  return (await import("./basemap")).basemapUrl;
}

afterEach(() => vi.unstubAllEnvs());

describe("basemapUrl", () => {
  it("hängt den Key als `key` an — nicht als `api_key`", () => {
    // `api_key` wird stillschweigend ignoriert: Status 200, Wasserzeichen
    // bleibt. Der Fehler sähe aus wie „der Key wirkt nicht".
    return frisch("geheim").then((basemapUrl) => {
      const url = basemapUrl();
      expect(url).toContain("?key=geheim");
      expect(url).not.toContain("api_key");
    });
  });

  it("lässt die URL ohne Key unverändert — Karte mit Wasserzeichen schlägt keine Karte", () => {
    return frisch(undefined).then((basemapUrl) => {
      expect(basemapUrl()).not.toContain("?");
    });
  });

  it("kodiert einen Key mit Sonderzeichen", () => {
    return frisch("a+b/c=").then((basemapUrl) => {
      expect(basemapUrl()).toContain("key=a%2Bb%2Fc%3D");
    });
  });

  it("behält die Leaflet-Platzhalter — sonst lädt keine einzige Kachel", () => {
    return frisch("k").then((basemapUrl) => {
      for (const p of ["{s}", "{z}", "{x}", "{y}", "{r}"]) {
        expect(basemapUrl()).toContain(p);
      }
    });
  });

  it("kennt die drei Styles und baut für jeden einen eigenen Pfad", () => {
    return frisch("k").then((basemapUrl) => {
      const urls = (["voyager", "light", "dark"] as const).map((s) => basemapUrl(s));
      expect(new Set(urls).size).toBe(3);
      expect(urls[0]).toContain("rastertiles/voyager");
      expect(urls[1]).toContain("light_all");
      expect(urls[2]).toContain("dark_all");
    });
  });

  it("nimmt ohne Angabe voyager", () => {
    return frisch("k").then((basemapUrl) => {
      expect(basemapUrl()).toBe(basemapUrl("voyager"));
    });
  });
});
