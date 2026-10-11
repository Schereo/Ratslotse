import { describe, expect, it } from "vitest";
import { chunkFehlerHeilen, istChunkFehler } from "./chunk-fehler";
import { speicherStub } from "./__testhilfen/speicher";

const chunk = Object.assign(new Error("Loading chunk 4512 failed. (error: https://ratslotse.de/_next/static/chunks/4512-abc.js)"), { name: "ChunkLoadError" });

describe("istChunkFehler", () => {
  it("erkennt die Fassungen von Webpack, Vite und Firefox", () => {
    expect(istChunkFehler(chunk)).toBe(true);
    expect(istChunkFehler(new Error("Loading CSS chunk 77 failed."))).toBe(true);
    expect(istChunkFehler(new TypeError("Failed to fetch dynamically imported module: /x.js"))).toBe(true);
    expect(istChunkFehler(new TypeError("error loading dynamically imported module"))).toBe(true);
  });
  it("lässt gewöhnliche Fehler in Ruhe", () => {
    expect(istChunkFehler(new TypeError("Cannot read properties of undefined"))).toBe(false);
    expect(istChunkFehler(null)).toBe(false);
    expect(istChunkFehler("Loading chunk")).toBe(false);
  });
});

describe("chunkFehlerHeilen", () => {
  it("lädt einmal neu und dann innerhalb einer Minute nicht wieder", () => {
    const s = speicherStub();
    let geladen = 0;
    expect(chunkFehlerHeilen(chunk, s, () => geladen++, 1_000_000)).toBe(true);
    expect(chunkFehlerHeilen(chunk, s, () => geladen++, 1_030_000)).toBe(false);
    expect(geladen).toBe(1);
    expect(chunkFehlerHeilen(chunk, s, () => geladen++, 1_070_000)).toBe(true);
    expect(geladen).toBe(2);
  });
  it("lädt bei anderen Fehlern nie neu", () => {
    let geladen = 0;
    expect(chunkFehlerHeilen(new Error("kaputt"), speicherStub(), () => geladen++)).toBe(false);
    expect(geladen).toBe(0);
  });
  it("lädt ohne Speicher lieber gar nicht als in Schleife", () => {
    const s = speicherStub(); s.kaputt(true);
    let geladen = 0;
    expect(chunkFehlerHeilen(chunk, s, () => geladen++)).toBe(false);
    expect(geladen).toBe(0);
  });
});
