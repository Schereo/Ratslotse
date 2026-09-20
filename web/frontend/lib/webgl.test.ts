import { afterEach, describe, expect, it, vi } from "vitest";
import { webglProbeZuruecksetzen, webglVerfuegbar } from "./webgl";

/** Ein `document`, dessen Leinwand tut, was der Test vorgibt (vitest läuft ohne DOM). */
function dokumentMit(getContext: (art: string) => unknown) {
  vi.stubGlobal("document", { createElement: () => ({ getContext }) });
}

describe("webglVerfuegbar", () => {
  afterEach(() => {
    webglProbeZuruecksetzen();
    vi.unstubAllGlobals();
  });

  it("sagt nein ohne Browser (kein document)", () => {
    expect(webglVerfuegbar()).toBe(false);
  });

  it("sagt nein, wenn der Browser keinen Kontext hergibt", () => {
    dokumentMit(() => null);
    expect(webglVerfuegbar()).toBe(false);
  });

  it("sagt ja, wenn ein Kontext entsteht — und gibt ihn gleich wieder frei", () => {
    const loseContext = vi.fn();
    dokumentMit(() => ({ getExtension: () => ({ loseContext }) }));
    expect(webglVerfuegbar()).toBe(true);
    expect(loseContext).toHaveBeenCalledTimes(1);
  });

  it("merkt sich das Ergebnis, statt jedes Mal einen Kontext zu bauen", () => {
    // Ein Kontext beim ersten Versuch (webgl2) — sonst zählt der Ersatzversuch
    // mit "webgl" als zweiter Aufruf.
    const getContext = vi.fn(() => ({ getExtension: () => null }));
    dokumentMit(getContext);
    webglVerfuegbar();
    webglVerfuegbar();
    expect(getContext).toHaveBeenCalledTimes(1);
  });

  it("sagt nein, wenn getContext selbst wirft", () => {
    dokumentMit(() => {
      throw new Error("kaputt");
    });
    expect(webglVerfuegbar()).toBe(false);
  });
});
