import { describe, expect, it } from "vitest";
import { featureAktiv } from "./features";

// Der Kern der Schalter-Logik. Die Regel, auf die es ankommt: Was nicht
// ausdrücklich AN ist, ist AUS — auch beim Laden, auch bei einem Fehler, auch
// bei einer älteren Antwort ohne das Feld.

const config = (features?: string[]) => ({ min_build: 0, note: null, features });

describe("featureAktiv", () => {
  it("erkennt einen eingeschalteten Schalter", () => {
    expect(featureAktiv(config(["haushalt-labor"]), "haushalt-labor")).toBe(true);
  });

  it("sagt nein zu einem Schalter, der nicht dabei ist", () => {
    expect(featureAktiv(config(["etwas-anderes"]), "haushalt-labor")).toBe(false);
    expect(featureAktiv(config([]), "haushalt-labor")).toBe(false);
  });

  it("sagt nein, solange nichts geladen ist", () => {
    // Der Grund ist derselbe wie bei den Rechten: Eine Fläche, die kurz
    // aufblitzt und dann verschwindet, ist schlechter als eine, die eine
    // halbe Sekunde später erscheint.
    expect(featureAktiv(undefined, "haushalt-labor")).toBe(false);
    expect(featureAktiv(null, "haushalt-labor")).toBe(false);
  });

  it("sagt nein bei einer Antwort ohne das Feld", () => {
    // Eine ältere App oder eine Antwort aus dem Cache von vor dem Umbau.
    expect(featureAktiv(config(undefined), "haushalt-labor")).toBe(false);
    expect(featureAktiv({ min_build: 0, note: null } as never, "haushalt-labor")).toBe(false);
  });

  it("prüft genau, nicht auf Teilzeichenketten", () => {
    expect(featureAktiv(config(["haushalt-labor-neu"]), "haushalt-labor")).toBe(false);
    expect(featureAktiv(config(["haushalt"]), "haushalt-labor")).toBe(false);
  });

  it("gibt immer einen echten Wahrheitswert zurück", () => {
    // `includes` auf `undefined` liefert sonst `undefined`, und ein
    // `hidden={undefined}` ist nicht dasselbe wie `hidden={false}`.
    expect(typeof featureAktiv(undefined, "x")).toBe("boolean");
  });
});
