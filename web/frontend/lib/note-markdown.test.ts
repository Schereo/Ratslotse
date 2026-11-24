import { describe, expect, it } from "vitest";
import { parseInline, parseNote, serializeInline, serializeNote, type NoteNode } from "./note-markdown";
import { RIS_FRUEHER } from "./ris";

const t = (text: string, ...marks: ("bold" | "italic")[]): NoteNode =>
  marks.length ? { type: "text", text, marks: marks.map((type) => ({ type })) } : { type: "text", text };
const p = (...content: NoteNode[]): NoteNode => (content.length ? { type: "paragraph", content } : { type: "paragraph" });
const li = (...content: NoteNode[]): NoteNode => ({ type: "listItem", content });
const task = (checked: boolean, ...content: NoteNode[]): NoteNode => ({ type: "taskItem", attrs: { checked }, content });
const doc = (...content: NoteNode[]): NoteNode => ({ type: "doc", content });

/** Text → Dokument → Text muss genau den Text zurückgeben. */
const rund = (text: string) => expect(serializeNote(parseNote(text))).toBe(text);

describe("parseNote", () => {
  it("eine Zeile ist ein Absatz — auch ohne Leerzeile dazwischen", () => {
    expect(parseNote("eins\nzwei")).toEqual(doc(p(t("eins")), p(t("zwei"))));
  });

  it("Tims Notiz: die Zeile unter der Liste bleibt ein eigener Absatz", () => {
    const text = "- Defizit 182 Millionen €, kann Oldenburg nicht selber schließen\n- Steht unter Konsolidierungvorgaben\nKonsolidierung durch:\n- Konzernsteuerung";
    expect(parseNote(text)).toEqual(doc(
      { type: "bulletList", content: [li(p(t("Defizit 182 Millionen €, kann Oldenburg nicht selber schließen"))), li(p(t("Steht unter Konsolidierungvorgaben")))] },
      p(t("Konsolidierung durch:")),
      { type: "bulletList", content: [li(p(t("Konzernsteuerung")))] },
    ));
    rund(text);
  });

  it("nummerierte Liste mit Startwert, Aufgaben offen und erledigt", () => {
    expect(parseNote("3. drei\n4. vier")).toEqual(doc({ type: "orderedList", attrs: { start: 3 },
      content: [li(p(t("drei"))), li(p(t("vier")))] }));
    expect(parseNote("- [x] gelesen\n- [ ] fragen")).toEqual(doc({ type: "taskList",
      content: [task(true, p(t("gelesen"))), task(false, p(t("fragen")))] }));
  });

  it("zwei Leerzeichen je Ebene verschachteln, eine eingerückte Zeile setzt den Punkt fort", () => {
    const text = "- oben\n  - unten\n    1. ganz unten\n  weiter oben\n- zweiter";
    expect(parseNote(text)).toEqual(doc({ type: "bulletList", content: [
      li(p(t("oben")), { type: "bulletList", content: [li(p(t("unten")),
        { type: "orderedList", content: [li(p(t("ganz unten")))] })] }, p(t("weiter oben"))),
      li(p(t("zweiter"))),
    ] }));
    rund(text);
  });

  it("wechselt die Art der Liste, beginnt eine neue", () => {
    expect(parseNote("- a\n1. b").content!.map((n) => n.type)).toEqual(["bulletList", "orderedList"]);
  });

  it("leerer Text und Leerzeilen sind leere Absätze", () => {
    expect(parseNote("")).toEqual(doc(p()));
    expect(parseNote("a\n\nb")).toEqual(doc(p(t("a")), p(), p(t("b"))));
  });
});

describe("Überschriften", () => {
  const h = (level: number, ...content: NoteNode[]): NoteNode => ({ type: "heading", attrs: { level }, content });

  it("# und ## sind die beiden Größen, tiefere lesen sich als ##", () => {
    expect(parseNote("# Haushalt 2027\n## Fragen\n### noch kleiner")).toEqual(doc(
      h(1, t("Haushalt 2027")), h(2, t("Fragen")), h(2, t("noch kleiner"))));
  });

  it("beendet eine Liste und trägt Hervorhebung", () => {
    const text = "- a\n## Zur **Sitzung**\n- b";
    expect(parseNote(text)).toEqual(doc(
      { type: "bulletList", content: [li(p(t("a")))] },
      h(2, t("Zur "), t("Sitzung", "bold")),
      { type: "bulletList", content: [li(p(t("b")))] },
    ));
    rund(text);
  });

  it("ohne Leerzeichen, eingerückt oder als Absatz-Text keine Überschrift", () => {
    expect(parseNote("#hashtag").content![0].type).toBe("paragraph");
    expect(parseNote("- a\n  # b").content![0].content![0].content!.map((n) => n.type)).toEqual(["paragraph", "paragraph"]);
    const d = doc(p(t("# keine Überschrift")));
    expect(serializeNote(d)).toBe("\\# keine Überschrift");
    expect(parseNote(serializeNote(d))).toEqual(d);
  });

  it("leere Überschrift bleibt eine", () => {
    expect(serializeNote(doc({ type: "heading", attrs: { level: 1 } }))).toBe("# ");
    expect(parseNote("# ")).toEqual(doc({ type: "heading", attrs: { level: 1 } }));
  });
});

describe("Inline", () => {
  it("fett, kursiv und beides verschachtelt", () => {
    expect(parseInline("die **Verwaltung** *fragen*")).toEqual([t("die "), t("Verwaltung", "bold"), t(" "), t("fragen", "italic")]);
    expect(parseInline("**fett *und kursiv***")).toEqual([t("fett ", "bold"), t("und kursiv", "bold", "italic")]);
  });

  it("Code, Links und HTML bleiben Text", () => {
    expect(parseInline("`x` [a](b) <b> ~~s~~")).toEqual([t("`x` [a](b) <b> ~~s~~")]);
  });

  it("Marken schachteln wie ein Stapel und gehen verlustfrei zurück", () => {
    const nodes = [t("ab", "bold"), t("cd", "bold", "italic"), t(" ef")];
    expect(serializeInline(nodes)).toBe("**ab*cd*** ef");
    expect(parseInline("**ab*cd*** ef")).toEqual(nodes);
  });

  it("Leerzeichen bleiben außerhalb der Marken", () => {
    expect(serializeInline([t("die "), t(" Verwaltung ", "bold"), t("fragen")])).toBe("die  **Verwaltung** fragen");
  });

  it("Sternchen, Unterstriche und Backslashes im Text kommen unverändert zurück", () => {
    for (const s of ["2*3*4", "_x_", "max_mustermann", "C:\\Pfad\\*", "\\_", "`a*b`"]) {
      expect(parseInline(serializeInline([t(s)]))).toEqual([t(s)]);
    }
    expect(serializeInline([t("max_mustermann")])).toBe("max_mustermann");
  });
});

describe("serializeNote", () => {
  it("ein Absatz, der wie ein Listenpunkt aussieht, bleibt ein Absatz", () => {
    for (const s of ["- kein Punkt", "1. Januar", "2) b"]) {
      const d = doc(p(t(s)));
      expect(parseNote(serializeNote(d))).toEqual(d);
    }
    const d = doc({ type: "bulletList", content: [li(p(t("[ ] keine Aufgabe")))] });
    expect(parseNote(serializeNote(d))).toEqual(d);
  });

  it("schreibt Listen mit fortlaufender Nummer und Haken", () => {
    expect(serializeNote(doc(
      p(t("Fragen", "bold")),
      { type: "orderedList", content: [li(p(t("eins"))), li(p(t("zwei")))] },
      p(),
      { type: "taskList", content: [task(true, p(t("lesen"))), task(false, p())] },
    ))).toBe("**Fragen**\n1. eins\n2. zwei\n\n- [x] lesen\n- [ ] ");
  });

  it("hin und zurück ohne Verlust", () => {
    for (const s of [
      "# Haushalt 2027\nFragen an die **Verwaltung**\n1. Wie viel zahlt die Stadt?\n2. Was passiert mit dem *Schülerticket*?\n\nVor der Sitzung\n- [x] Vorlage lesen\n- [ ] Mit der Fraktion abstimmen",
      "nur Text",
      "- a\n  - b\n- c",
      "5. fünf\n6. sechs",
    ]) rund(s);
  });

  it("Fremdes liest es, und danach bleibt es stabil", () => {
    // Aus der App oder von Hand: `*`-Punkte, `_kursiv_`, Tabs.
    const einmal = serializeNote(parseNote("* a\n\t* b\n_kursiv_"));
    expect(einmal).toBe("- a\n  - b\n*kursiv*");
    rund(einmal);
  });
});

describe("Verweise auf Unterlagen", () => {
  const URL = "https://ratsinfo.oldenburg.de/bi/getfile.asp?id=312295&type=do";
  const ref = (page: number | null, label = "Anlage 1 VBN Tariferhöhung"): NoteNode =>
    ({ type: "docRef", attrs: { documentId: 312295, page, label, href: URL } });

  it("eine Seite: lesbarer Link im Text, Chip im Dokument", () => {
    const text = `Preise: [Anlage 1 VBN Tariferhöhung, S. 14](${URL}#page=14) prüfen`;
    expect(parseNote(text)).toEqual(doc(p(t("Preise: "), ref(14), t(" prüfen"))));
    rund(text);
  });

  it("ohne Seite die ganze Unterlage, auch im Listenpunkt und neben Fett", () => {
    const text = `- **Kosten** [Vorlage 26/0622](${URL})`;
    expect(parseNote(text).content![0].content![0].content![0].content).toEqual(
      [t("Kosten", "bold"), t(" "), ref(null, "Vorlage 26/0622")]);
    rund(text);
  });

  it("Klammern und Sternchen im Titel kommen heil zurück", () => {
    const d = doc(p(ref(3, "Plan [Entwurf] *neu*_2")));
    expect(parseNote(serializeNote(d))).toEqual(d);
  });

  it("andere Links bleiben Text, wie sie dastanden", () => {
    for (const s of ["[NWZ](https://www.nwz-online.de/x)", "[Rat](https://ratsinfo.oldenburg.de/bi/si0057.asp?__ksinr=1)",
      "[kaputt](getfile.asp?id=1)"]) {
      expect(parseNote(s)).toEqual(doc(p(t(s))));
      rund(s);
    }
  });

  it("die alte Adresse des Ratsinfos zählt auch", () => {
    const href = `https://${RIS_FRUEHER[0]}/getfile.php?id=7&type=do`;
    expect(parseNote(`[A](${href}#page=2)`).content![0].content).toEqual([
      { type: "docRef", attrs: { documentId: 7, page: 2, label: "A", href } }]);
  });
});
