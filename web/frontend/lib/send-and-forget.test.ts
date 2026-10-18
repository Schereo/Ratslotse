import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { sendAndForget } from "./send-and-forget";

/**
 * Wächter für Anfragen, deren Antwort niemand braucht.
 *
 * Der Anlass steht in `send-and-forget.ts`: Ein ungelesener Antwortkörper
 * hielt in Chromium die Anfrage offen, und Playwrights `networkidle` wartete
 * darauf bis zum Timeout — `14-layout.spec.ts` war dadurch in jedem zweiten
 * CI-Lauf rot. Der Fehler war unsichtbar, weil die Seite selbst nichts davon
 * merkt; deshalb hält ihn ein Test fest und keine Absicht.
 */

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Lässt die Mikrotasks durchlaufen, an denen `then`/`catch` hängen. */
const nachlaufen = () => new Promise((r) => setTimeout(r, 0));

describe("sendAndForget", () => {
  it("liest den Antwortkörper zu Ende", async () => {
    const gelesen = vi.fn(() => Promise.resolve(new ArrayBuffer(0)));
    vi.stubGlobal("fetch", () => Promise.resolve({ arrayBuffer: gelesen } as unknown as Response));
    sendAndForget("/x", { method: "POST" });
    await nachlaufen();
    expect(gelesen).toHaveBeenCalledOnce();
  });

  it("wirft nicht, wenn fetch sofort wirft", () => {
    vi.stubGlobal("fetch", () => { throw new TypeError("kein fetch"); });
    expect(() => sendAndForget("/x", {})).not.toThrow();
  });

  it("verschluckt ein abgelehntes fetch und einen scheiternden Körper", async () => {
    const unbehandelt = vi.fn();
    process.on("unhandledRejection", unbehandelt);
    try {
      vi.stubGlobal("fetch", () => Promise.reject(new TypeError("offline")));
      sendAndForget("/x", {});
      vi.stubGlobal("fetch", () => Promise.resolve({
        arrayBuffer: () => Promise.reject(new Error("abgebrochen")),
      } as unknown as Response));
      sendAndForget("/x", {});
      await nachlaufen();
      expect(unbehandelt).not.toHaveBeenCalled();
    } finally {
      process.off("unhandledRejection", unbehandelt);
    }
  });
});

describe("kein `void fetch(` im Bestand", () => {
  // Wer eine Antwort wegwirft, nimmt `sendAndForget` — sonst ist der Hänger
  // wieder da, und er zeigt sich erst als wechselnder Timeout in der CI.
  const wurzel = join(__dirname, "..");

  function dateien(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
      const pfad = join(dir, name);
      if (statSync(pfad).isDirectory()) return name === "node_modules" ? [] : dateien(pfad);
      return /\.(ts|tsx)$/.test(name) && !/\.test\.ts$/.test(name) ? [pfad] : [];
    });
  }

  it("findet keine Stelle in app/, components/ und lib/", () => {
    const treffer = ["app", "components", "lib"]
      .flatMap((d) => dateien(join(wurzel, d)))
      .filter((pfad) => /\bvoid\s+fetch\(/.test(readFileSync(pfad, "utf8")))
      .map((pfad) => relative(wurzel, pfad))
      // Die eine erlaubte Stelle: der Helfer selbst, der den Körper liest.
      .filter((pfad) => pfad !== join("lib", "send-and-forget.ts"));
    expect(treffer).toEqual([]);
  });
});
