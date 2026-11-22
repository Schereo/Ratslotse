import { describe, expect, it } from "vitest";
import { courseInput, layoutCourse, ownPageItems, stageLabel, type Buoy, type CourseInput, type SessionCourse } from "./course";

// Die Testfälle stehen im Plan (§ 4.1): die vier Datensätze des Entwurfs in
// zwei Breiten. Die Zellenzahl zählt Start und Leerzellen mit — eine Etappe
// mit nur einer Boje bekommt eine dazu, damit ihr Name Platz hat.

const boje = (label: string, extra: Partial<Buoy> = {}): Buoy => ({
  label, items: [label], title: label, shortTitle: label, icon: "statute",
  important: false, postponed: false, outcome: null, provisional: false, ...extra,
});

/** Etappen aus Anzahlen; `null` = nichtöffentlich. */
function sitzung(etappen: (number | null)[]): CourseInput {
  let nr = 0;
  return {
    start: "17:00",
    stages: etappen.map((n, i) => n === null
      ? { name: "Nichtöffentlicher Teil", nameMedium: "Nichtöffentlich", nameShort: null, closed: true,
          closedLabel: "N 13–15", closedCount: 5, buoys: [] }
      : { name: `Etappe ${i + 1}`, nameMedium: null, nameShort: `E${i + 1}`, closed: false,
          buoys: Array.from({ length: n }, () => boje(`Ö ${++nr}`)) }),
  };
}

// Sportausschuss 07.10.: Start 2 · Anträge 2 · Schluss 1 · nö → 9 Zellen
const WENIG = sitzung([2, 2, 1, null]);
// Verkehrsausschuss 21.09.: Start 2 · Beschlüsse 6 · Anträge 3 · Schluss 1 · nö → 16
const NORMAL = sitzung([2, 6, 3, 1, null]);
// Verkehrsausschuss 08.06.: Start 2 · Beschlüsse 10 · Anträge 4 · Schluss 1 · nö → 21
const NACH = sitzung([2, 10, 4, 1, null]);
// Rat 31.08. (wie im Entwurf, ohne Dringlich): 3 · 2 · 2 · 2 · 8 · 7 · 1 · nö → 29
const VIEL = sitzung([3, 2, 2, 2, 8, 7, 1, null]);

const zellen = (l: ReturnType<typeof layoutCourse>) => l.rows.flatMap((r) => r.cells).filter((c) => c.kind !== "pad").length;

describe("layoutCourse — die Fälle aus dem Plan", () => {
  it.each([
    ["wenig", WENIG, 9, 1174, 1, 9, false, true],
    ["normal", NORMAL, 16, 1176, 1, 16, false, false],
    ["nach", NACH, 21, 1176, 2, 11, false, false],
    ["viel", VIEL, 29, 1174, 2, 15, false, false],
    ["wenig", WENIG, 9, 320, 1, 9, true, false],
    ["normal", NORMAL, 16, 320, 2, 8, true, false],
    ["viel", VIEL, 29, 320, 4, 8, true, false],
  ] as const)("%s bei %i Zellen und %i px", (_name, input, n, breite, zeilen, spalten, kompakt, kurz) => {
    const l = layoutCourse(input, breite);
    expect(zellen(l)).toBe(n);
    expect(l.rows).toHaveLength(zeilen);
    expect(l.columns).toBe(spalten);
    expect(l.compact).toBe(kompakt);
    expect(l.rows[0].cells.some((c) => c.showShortTitle)).toBe(kurz);
  });

  it("kein seitliches Scrollen: Spalten × Mindestbreite passt immer", () => {
    for (const breite of [280, 320, 390, 768, 1024, 1360, 2200]) {
      for (const input of [WENIG, NORMAL, NACH, VIEL]) {
        const l = layoutCourse(input, breite);
        const min = l.compact ? 30 : 60;
        // Unter 3 Spalten geht es nie — darunter wird es eng, aber nie breiter als das Fenster.
        if (l.columns > 3) expect(l.columns * min).toBeLessThanOrEqual(Math.max(120, breite - 36));
      }
    }
  });

  it("jede zweite Zeile läuft rückwärts, die Reihenfolge der Zellen bleibt", () => {
    const l = layoutCourse(VIEL, 320);
    expect(l.rows.map((r) => r.reverse)).toEqual([false, true, false, true]);
    const nummern = l.rows.flatMap((r) => r.cells).map((c) => c.buoy?.label).filter(Boolean);
    expect(nummern.slice(0, 3)).toEqual(["Ö 1", "Ö 2", "Ö 3"]);
    // Die Kehre gibt es zwischen den Zeilen, nicht nach der letzten.
    expect(l.rows.map((r) => r.turn !== null)).toEqual([true, true, true, false]);
  });

  it("eine einzige Zeile wird gedeckelt, sonst stehen drei Bojen über 1.200 px", () => {
    expect(layoutCourse(WENIG, 1174).rows[0].maxWidth).toBe(9 * 150 + 36);
    expect(layoutCourse(NACH, 1176).rows[0].maxWidth).toBeNull();
  });

  it("Leerzelle: hinter der Etappe, bei der letzten davor", () => {
    const zs = layoutCourse(WENIG, 1174).rows[0].cells;
    // Schluss (1 Boje) → Boje, dann Leerzelle; nichtöffentlich (letzte) → Leerzelle, dann Schloss.
    expect(zs.map((c) => c.kind)).toEqual(["start", "buoy", "buoy", "buoy", "buoy", "buoy", "empty", "empty", "lock"]);
  });
});

describe("Linie, Dimmen und aktive Boje", () => {
  it("vor dem Schloss gestrichelt", () => {
    const zs = layoutCourse(WENIG, 1174).rows[0].cells;
    const schloss = zs.findIndex((c) => c.kind === "lock");
    expect(zs[schloss].lineBefore).toBe("dashed");
    expect(zs[schloss - 2].lineAfter).toBe("dashed");   // letzte öffentliche Boje
    expect(zs[0].lineBefore).toBe("none");
    expect(zs[zs.length - 1].lineAfter).toBe("none");
  });

  it("aktiv: Linie bis dorthin voll, frühere gedimmt, Position gezählt", () => {
    const l = layoutCourse(NORMAL, 1176, "auto", "Ö 5");
    const zs = l.rows.flatMap((r) => r.cells);
    const i = zs.findIndex((c) => c.active);
    expect(zs[i].buoy?.label).toBe("Ö 5");
    expect(zs[i].lineBefore).toBe("solid");
    expect(zs[i].lineAfter).toBe("normal");
    expect(zs[i - 1].passed).toBe(true);
    expect(zs[i].passed).toBe(false);
    expect(l.activeIndex).toBe(5);              // Ö 1 … Ö 5, jede eine Boje
    expect(l.buoyCount).toBe(13);               // 12 Punkte + Schloss
  });

  it("die Formalien-Boje ist aktiv, sobald einer ihrer Punkte läuft", () => {
    const input: CourseInput = {
      start: "17:00",
      stages: [{ name: "Zum Start", nameMedium: null, nameShort: "Start", closed: false, buoys: [
        boje("Ö 1–3", { items: ["Ö 1", "Ö 2", "Ö 3", "Ö 3.1"] }), boje("Ö 4"),
      ] }],
    };
    const zs = layoutCourse(input, 1000, "auto", "Ö 3.1").rows[0].cells;
    expect(zs.find((c) => c.active)?.buoy?.label).toBe("Ö 1–3");
  });

  it("kompakt: kleine Punkte ohne Link, wichtige und die aktive bleiben antippbar", () => {
    const input = sitzung([2, 6, 3, 1, null]);
    input.stages[1].buoys[2].important = true;          // Ö 5
    const zs = layoutCourse(input, 320, "auto", "Ö 7").rows.flatMap((r) => r.cells);
    const nach = (nr: string) => zs.find((c) => c.buoy?.label === nr)!;
    expect(nach("Ö 4").kind).toBe("dot");
    expect(nach("Ö 4").interactive).toBe(false);
    expect(nach("Ö 5").kind).toBe("important");
    expect(nach("Ö 5").interactive).toBe(true);
    expect(nach("Ö 7").kind).toBe("buoy");               // aktiv: wieder eine Boje
    expect(nach("Ö 7").interactive).toBe(true);
    // Nummern kompakt ohne „Ö", nur am Etappenanfang, an wichtigen, an der aktiven.
    expect(nach("Ö 3").number).toBe("3");
    expect(nach("Ö 4").number).toBeNull();
    expect(nach("Ö 5").number).toBe("5");
    expect(nach("Ö 7").number).toBe("7");
  });
});

describe("Etappenname", () => {
  it("nimmt die längste Form, die passt", () => {
    expect(stageLabel("Beschlüsse und Berichte", null, "Beschlüsse", 6, 400, false)).toBe("Beschlüsse und Berichte · 6");
    expect(stageLabel("Beschlüsse und Berichte", null, "Beschlüsse", 6, 170, false)).toBe("Beschlüsse und Berichte");
    expect(stageLabel("Stadtplanung & Bauen", "Stadtplanung", "Bauen", 8, 100, false)).toBe("Stadtplanung");
    expect(stageLabel("Stadtplanung & Bauen", "Stadtplanung", "Bauen", 8, 40, false)).toBe("Bauen");
    expect(stageLabel("Zum Start", null, "Start", 2, 400, true)).toBe("Start");
    // Ohne knappste Form bleibt kompakt nichts — kein abgeschnittener Name.
    expect(stageLabel("Nichtöffentlicher Teil", "Nichtöffentlich", null, 1, 400, true)).toBe("");
  });

  it("steht am ersten Stück mit mindestens zwei Zellen", () => {
    // 12 Zellen kompakt zu 2 × 6: Etappe 2 (Ö 5–7) beginnt mit EINER Zelle am
    // Ende der ersten Zeile und läuft in der zweiten weiter — dort steht ihr Name.
    const zs = layoutCourse(sitzung([4, 3, 2, null]), 320).rows.flatMap((r) => r.cells);
    const zwei = zs.filter((c) => c.stage === 1);
    expect(zwei.filter((c) => c.label).length).toBe(1);
    expect(zwei.find((c) => c.label)?.buoy?.label).toBe("Ö 6");
  });
});

describe("courseInput — vom Vertrag zur Eingabe", () => {
  const kurs: SessionCourse = {
    start: "17:00", public_count: 6, closed_count: 2, substantive_count: 2, summary: null, summary_source: "rule", next_session: null, protocol_estimate: null,
    stages: [
      { kind: "start", name: "Zum Start", name_medium: null, name_short: "Start", subtitle: null,
        range: "Ö 1 – Ö 2", count: 3, cells: [
          { label: "Ö 1", title: "Formalien", items: ["Ö 1", "Ö 1.1"] },
          { label: "Ö 2", title: null, items: ["Ö 2"] }] },
      { kind: "content", name: "Beschlüsse und Berichte", name_medium: null, name_short: "Beschlüsse",
        subtitle: null, range: "Ö 3 – Ö 4", count: 2, cells: [
          { label: "Ö 3", title: null, items: ["Ö 3"] },
          { label: "Ö 4", title: null, items: ["Ö 4"] }] },
      { kind: "closed", name: "Nichtöffentlicher Teil", name_medium: "Nichtöffentlich", name_short: null,
        subtitle: null, range: "N 5 – N 6", count: 2, cells: [{ label: "N 5–6", title: null, items: [] }] },
    ],
    items: Object.fromEntries(["Ö 1", "Ö 1.1", "Ö 2", "Ö 3", "Ö 4"].map((nr) => [nr, {
      short_title: `Titel ${nr}`, type: "report", type_label: "Bericht", icon: nr === "Ö 3" ? "bike" : "report",
      applicant: null, important: nr === "Ö 3", important_reason: null, postponed: nr === "Ö 4" ? 1 : 0,
      amendments_label: null, amendment_parties: [], cost_label: null,
      formality: nr.startsWith("Ö 1"), formal_act: false, own_page: !nr.startsWith("Ö 1"), group: null, journey: [], next_on_agenda: null,
    }])) as SessionCourse["items"],
  };

  it("übernimmt Zeichen, wichtig, vertagt und Ergebnis, Protokoll vor Übertragung", () => {
    const e = courseInput(kurs, {
      outcomeByItem: { "3": "accepted" },
      provisionalByItem: { "3": "rejected", "4": "postponed" },
    }, (nr) => `#top-${nr}`);
    const [start, inhalt, zu] = e.stages;
    expect(start.buoys[0]).toMatchObject({ label: "Ö 1", shortTitle: "Formalien", important: false, outcome: null });
    expect(inhalt.buoys[0]).toMatchObject({ icon: "bike", important: true, outcome: "accepted", provisional: false,
      href: "#top-Ö 3", title: "Ö 3 · Titel Ö 3 · Angenommen" });
    expect(inhalt.buoys[1]).toMatchObject({ postponed: true, outcome: "postponed", provisional: true,
      title: "Ö 4 · Titel Ö 4 · Vertagt (vorläufig)" });
    expect(zu).toMatchObject({ closed: true, closedLabel: "N 5–6", closedCount: 2 });
  });

  it("der eigene Mitschrieb färbt nur, wo Protokoll und Übertragung schweigen", () => {
    const e = courseInput(kurs, {
      outcomeByItem: { "3": "accepted" },
      provisionalByItem: {},
      ownByItem: { "3": "rejected", "4": "noted", "1": "accepted" },
    });
    const [start, inhalt] = e.stages;
    expect(start.buoys[0]).toMatchObject({ outcome: null });                       // Formalien bleiben ohne
    expect(inhalt.buoys[0]).toMatchObject({ outcome: "accepted", provisional: false });   // Protokoll geht vor
    expect(inhalt.buoys[1]).toMatchObject({ outcome: "noted", provisional: true,
      title: "Ö 4 · Titel Ö 4 · Zur Kenntnis (mein Mitschrieb)" });
  });
});

describe("ownPageItems — welche Punkte eine eigene Seite haben", () => {
  it("nimmt nur, was das Backend verspricht", () => {
    const items = {
      "Ö 1": { own_page: false }, "Ö 6": { own_page: true }, "Ö 6.1": { own_page: true }, "Ö 7": { own_page: false },
    } as unknown as SessionCourse["items"];
    expect([...ownPageItems({ items } as SessionCourse)].sort()).toEqual(["Ö 6", "Ö 6.1"]);
  });
  it("ohne Kurs eine leere Menge", () => {
    expect(ownPageItems(undefined).size).toBe(0);
    expect(ownPageItems(null).size).toBe(0);
  });
});
