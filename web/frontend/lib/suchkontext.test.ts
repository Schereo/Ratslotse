import { beforeEach, describe, expect, it, vi } from "vitest";
import { speicherStub } from "./__testhilfen/speicher";
import {
  aendereSuche, istSucheinstieg, letzteSuche, merkeSuche, merkeSuchPosition,
  suchAdresse, suchPosition, suchRueckweg,
} from "./suchkontext";

let speicher: ReturnType<typeof speicherStub>;
beforeEach(() => {
  speicher = speicherStub();
  vi.stubGlobal("sessionStorage", speicher);
});

describe("Suchadresse", () => {
  it("erhält sämtliche Filter und Unicode über den teilbaren Link", () => {
    const p = new URLSearchParams({
      q: "Straße & Schule", committee: "Ausschuss für Finanzen", outcome: "accepted",
      sort: "importance", field: "bildung", party: "Bündnis 90/Die Grünen",
      district: "kreyenbrueck", location: "Klingenbergplatz", location_name: "Platz",
      date_from: "2024-01-01", date_to: "2026-09-11", cat: "all", subvotes: "1",
      topic: "42", page: "3",
    });
    const result = new URL(suchAdresse(p.toString()), "https://ratslotse.invalid");
    for (const [key, value] of p) expect(result.searchParams.get(key)).toBe(value);
    expect(suchAdresse(result.search)).toBe(result.pathname + result.search);
  });

  it.each(["", "0", "-1", "1.5", "NaN", "Infinity", "99999999999999999"])(
    "beginnt bei ungültiger Seite %s auf Seite 1", (page) => {
      expect(suchAdresse(`page=${page}`)).toBe("/council?tab=decisions&page=1");
    },
  );

  it("setzt bei einem Filterwechsel die Seite zurück und ändert mehrere Filter gemeinsam", () => {
    const ziel = aendereSuche("q=Rad&outcome=accepted&sort=importance&page=4", { cat: "report", outcome: "" });
    const p = new URLSearchParams(ziel.split("?")[1]);
    expect(Object.fromEntries(p)).toEqual({ tab: "decisions", q: "Rad", sort: "importance", cat: "report", page: "1" });
    expect(aendereSuche(p.toString(), { page: "2" })).toContain("page=2");
  });

  it("unterscheidet den Navigationseinstieg von expliziten, auch ungefilterten Suchen", () => {
    expect(istSucheinstieg("")).toBe(true);
    expect(istSucheinstieg("tab=decisions")).toBe(true);
    for (const p of ["page=1", "q=", "field=bildung", "tab=sessions"]) expect(istSucheinstieg(p)).toBe(false);
  });
});

describe("Rückweg und gespeicherte Position", () => {
  it.each([null, "https://example.org", "//example.org/council", "/\\example.org/council",
    "javascript:alert(1)", "/account", "/council?tab=sessions", "/council/decision?id=1"])(
    "akzeptiert kein fremdes Ziel: %s", (href) => expect(suchRueckweg(href)).toBeNull(),
  );

  it("nimmt auch Export-Adressen mit Slash an und hält den konkreten Treffer", () => {
    expect(suchRueckweg("/council/?q=Rad&page=2#beschluss-8679"))
      .toBe("/council?tab=decisions&q=Rad&page=2#beschluss-8679");
  });

  it("vermischt weder Seiten noch Filter miteinander", () => {
    for (const href of ["/council?tab=decisions&page=1", "/council?tab=decisions&page=2"]) {
      merkeSuchPosition({ href, treffer: "beschluss-42", oben: 250, detail: "/council/decision?id=42" });
    }
    expect(suchPosition("/council?tab=decisions&page=2#beschluss-42")?.oben).toBe(250);
    expect(suchPosition("/council?tab=decisions&q=Rad&page=2")).toBeUndefined();
  });

  it("begrenzt den Sitzungsspeicher und ersetzt die Position derselben Suche", () => {
    for (let i = 1; i <= 14; i++) {
      merkeSuchPosition({ href: `page=${i}`, treffer: `beschluss-${i}`, oben: 80, detail: "detail" });
    }
    expect(suchPosition("page=1")).toBeUndefined();
    merkeSuchPosition({ href: "page=14", treffer: "beschluss-50", oben: 160, detail: "detail" });
    expect(suchPosition("page=14")?.treffer).toBe("beschluss-50");
  });

  it("fällt bei gesperrtem oder beschädigtem Speicher auf den URL-Weg zurück", () => {
    speicher.setItem("ratslotse:suche:positionen", "[null,{}]");
    expect(suchPosition("beliebig")).toBeUndefined();
    merkeSuche("/council?q=Rad&page=2");
    expect(letzteSuche()).toContain("q=Rad&page=2");
    speicher.kaputt(true);
    expect(() => merkeSuche("/council?page=1")).not.toThrow();
    expect(letzteSuche()).toBeNull();
    expect(suchPosition("beliebig")).toBeUndefined();
  });
});
