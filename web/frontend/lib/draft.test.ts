import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";

// Wer zwei Minuten an einer KI-Frage geschrieben hat und dabei in einen 401
// läuft, fand vorher ein leeres Feld. Die Rettung ist rein client-seitig und
// hat drei Eigenschaften, die keine Oberfläche zeigt: Sie nimmt den LÄNGSTEN
// Entwurf, sie gibt ihn nur EINMAL zurück, und sie vergisst ihn nach 30 min.

let speicher: ReturnType<typeof speicherStub>;
let d: typeof import("./draft");

beforeEach(async () => {
  speicher = speicherStub();
  vi.stubGlobal("sessionStorage", speicher);
  vi.resetModules();
  d = await import("./draft");
});

const melden = (feld: string, text: string) => d.entwurfMelden(feld, () => text);

describe("entwurfSichern", () => {
  it("sichert einen angemeldeten Entwurf", () => {
    melden("frage", "Wie steht es um das Stadion?");
    d.entwurfSichern("/fragen?q=x");
    expect(d.entwurfAbholen("frage")).toBe("Wie steht es um das Stadion?");
  });

  it("nimmt den LÄNGSTEN — zurück kommt man nur an eine Stelle", () => {
    melden("kurz", "hallo");
    melden("lang", "eine deutlich längere Frage an den Rat");
    d.entwurfSichern("/fragen");
    expect(d.entwurfAbholen("lang")).toContain("deutlich längere");
    expect(d.entwurfAbholen("kurz")).toBeNull();
  });

  it("ignoriert zu kurze und leere Eingaben", () => {
    melden("frage", "ab");           // 2 Zeichen
    d.entwurfSichern("/fragen");
    expect(d.entwurfAbholen("frage")).toBeNull();
  });

  it("schneidet Leerraum weg, bevor es die Länge misst", () => {
    melden("frage", "   ab   ");
    d.entwurfSichern("/fragen");
    expect(d.entwurfAbholen("frage")).toBeNull();
  });

  it("überlebt ein Feld, dessen Komponente schon weg ist", () => {
    d.entwurfMelden("kaputt", () => { throw new Error("unmounted"); });
    melden("gut", "ein brauchbarer Text");
    expect(() => d.entwurfSichern("/x")).not.toThrow();
    expect(d.entwurfAbholen("gut")).toBe("ein brauchbarer Text");
  });

  it("wirft nicht, wenn der Speicher gesperrt ist", () => {
    melden("frage", "ein brauchbarer Text");
    speicher.kaputt(true);
    expect(() => d.entwurfSichern("/x")).not.toThrow();
  });
});

describe("entwurfMelden — Abmeldung", () => {
  it("ein abgemeldetes Feld wird nicht mehr gesichert", () => {
    const ab = melden("frage", "ein brauchbarer Text");
    ab();
    d.entwurfSichern("/x");
    expect(d.entwurfAbholen("frage")).toBeNull();
  });
});

describe("entwurfAbholen", () => {
  it("gibt den Text nur EINMAL heraus", () => {
    melden("frage", "ein brauchbarer Text");
    d.entwurfSichern("/x");
    expect(d.entwurfAbholen("frage")).toBe("ein brauchbarer Text");
    expect(d.entwurfAbholen("frage")).toBeNull();
  });

  it("gibt nichts an ein fremdes Feld", () => {
    melden("frage", "ein brauchbarer Text");
    d.entwurfSichern("/x");
    expect(d.entwurfAbholen("anderes")).toBeNull();
    // und der Entwurf ist dabei NICHT verbraucht worden
    expect(d.entwurfAbholen("frage")).toBe("ein brauchbarer Text");
  });

  it("verwirft kalten Kaffee nach 30 Minuten", () => {
    melden("frage", "ein brauchbarer Text");
    d.entwurfSichern("/x");
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31 * 60 * 1000);
    expect(d.entwurfAbholen("frage")).toBeNull();
    vi.restoreAllMocks();
  });

  it("verträgt kaputten Inhalt im Speicher", () => {
    sessionStorage.setItem("ratslotse:entwurf", "{kein json");
    expect(d.entwurfAbholen("frage")).toBeNull();
  });

  it("liefert null, wenn gar nichts da ist", () => {
    expect(d.entwurfAbholen("frage")).toBeNull();
  });
});

describe("entwurfZiel", () => {
  it("nennt das Rücksprungziel, ohne den Entwurf zu verbrauchen", () => {
    melden("frage", "ein brauchbarer Text");
    d.entwurfSichern("/fragen?q=stadion");
    expect(d.entwurfZiel()).toBe("/fragen?q=stadion");
    expect(d.entwurfZiel()).toBe("/fragen?q=stadion");   // immer noch da
    expect(d.entwurfAbholen("frage")).toBe("ein brauchbarer Text");
  });

  it("räumt ein abgelaufenes Ziel weg", () => {
    melden("frage", "ein brauchbarer Text");
    d.entwurfSichern("/fragen");
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31 * 60 * 1000);
    expect(d.entwurfZiel()).toBeNull();
    vi.restoreAllMocks();
    expect(sessionStorage.getItem("ratslotse:entwurf")).toBeNull();
  });

  it("liefert null ohne Entwurf", () => {
    expect(d.entwurfZiel()).toBeNull();
  });
});
