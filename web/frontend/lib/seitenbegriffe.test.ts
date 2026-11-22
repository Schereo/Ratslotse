import { describe, expect, it } from "vitest";
import { fuerKarte, zerlege, type SeitenBegriff } from "./seitenbegriffe";

const b = (form: string, snippet: string, offset: number): SeitenBegriff =>
  ({ term: form, form, snippet, offset, explanation: "…", kind: "glossary" });

describe("zerlege", () => {
  const satz = "Der Antrag befasst sich mit der Einführung einer Grundsteuer C zur Bekämpfung von Bodenspekulation.";
  const gc = b("Grundsteuer C", "it der Einführung einer Grundsteuer C zur Bekämpfung von Bode", 24);

  it("schneidet an der gemeldeten Stelle", () => {
    const s = zerlege(satz, [gc]);
    expect(s).toHaveLength(3);
    expect(s[1]).toMatchObject({ text: "Grundsteuer C" });
    expect(s.map((x) => (typeof x === "string" ? x : x.text)).join("")).toBe(satz);
  });

  it("ein Text, der die Fundstelle nicht trägt, bleibt wie er ist", () => {
    // Derselbe Begriff weiter unten auf der Seite: nur die erste Nennung ist erklärt.
    expect(zerlege("Die Grundsteuer C wird später beraten.", [gc])).toEqual(["Die Grundsteuer C wird später beraten."]);
    expect(zerlege(satz, [])).toEqual([satz]);
  });

  it("mehrere Begriffe in Lesereihenfolge, auch wenn der Server sie anders sortiert", () => {
    const text = "Der Hebesatz der Grundsteuer steigt.";
    const s = zerlege(text, [b("Grundsteuer", "Der Hebesatz der Grundsteuer steigt.", 17), b("Hebesatz", "Der Hebesatz der Grundsteuer steigt.", 4)]);
    expect(s.filter((x) => typeof x !== "string").map((x) => (x as { text: string }).text)).toEqual(["Hebesatz", "Grundsteuer"]);
  });

  it("vor einem Emoji verschiebt sich die Zählung — dann zählt die Form im Stück", () => {
    const text = "🏗️ Neuer Bebauungsplan für Etzhorn";
    // Python zählt „🏗️" als 2 Zeichen, JavaScript als 3 Einheiten.
    const s = zerlege(text, [b("Bebauungsplan", text, 9)]);
    expect(s[1]).toMatchObject({ text: "Bebauungsplan" });
  });

  it("eine Stelle, die nicht zur Form passt, wird nicht unterstrichen", () => {
    expect(zerlege("abc def", [b("xyz", "abc def", 4)])).toEqual(["abc def"]);
  });
});

describe("fuerKarte", () => {
  const an = (item?: string): SeitenBegriff => ({ ...b("Satzung", "Die Satzung gilt.", 4), ...(item ? { item } : {}) });

  it("auf der Sitzungsseite gilt eine Fundstelle nur an ihrer Karte", () => {
    // Sechs Bebauungspläne hintereinander tragen dieselbe Kurzfassung — nur die erste Karte unterstreicht.
    const begriffe = [an("Ö 7.1")];
    expect(fuerKarte(begriffe, "Ö 7.1")).toHaveLength(1);
    expect(fuerKarte(begriffe, "Ö 7.2")).toHaveLength(0);
  });

  it("ohne Punkt (Punkt- und Beschluss-Seite) gelten alle, und Begriffe ohne Karte überall", () => {
    expect(fuerKarte([an("Ö 1"), an()])).toHaveLength(2);
    expect(fuerKarte([an()], "Ö 3")).toHaveLength(1);
  });
});
