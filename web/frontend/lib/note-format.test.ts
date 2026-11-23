import { describe, expect, it } from "vitest";
import { activeList, applyEdit, continueList, lineInfo, toggleList, toggleTask, toggleWrap, type Edit } from "./note-format";

/** `|` marks the caret, `«` … `»` a selection. */
function at(src: string): { value: string; start: number; end: number } {
  const open = src.indexOf("«");
  if (open !== -1) {
    const close = src.indexOf("»", open);
    return { value: src.slice(0, open) + src.slice(open + 1, close) + src.slice(close + 1), start: open, end: close - 1 };
  }
  const i = src.indexOf("|");
  return { value: src.slice(0, i) + src.slice(i + 1), start: i, end: i };
}

function show(value: string, e: Edit): string {
  const v = applyEdit(value, e);
  if (e.selStart === e.selEnd) return v.slice(0, e.selStart) + "|" + v.slice(e.selStart);
  return v.slice(0, e.selStart) + "«" + v.slice(e.selStart, e.selEnd) + "»" + v.slice(e.selEnd);
}

describe("lineInfo", () => {
  it("erkennt die drei Listen und lässt Fließtext in Ruhe", () => {
    expect(lineInfo("- [x] erledigt")).toMatchObject({ kind: "task", checked: true, prefixLen: 6 });
    expect(lineInfo("  * Punkt")).toMatchObject({ kind: "bullet", indent: "  ", prefixLen: 4 });
    expect(lineInfo("12) zwölf")).toMatchObject({ kind: "number", num: 12, delim: ")" });
    expect(lineInfo("-kein Punkt").kind).toBeNull();
    expect(lineInfo("2026 war ein Jahr").kind).toBeNull();
  });
});

describe("toggleList", () => {
  it("macht aus der Zeile am Cursor einen Punkt und behält die Stelle im Text", () => {
    const { value, start, end } = at("Kosten nach|fragen");
    expect(show(value, toggleList(value, start, end, "bullet"))).toBe("- Kosten nach|fragen");
  });

  it("nimmt den Punkt wieder weg, wenn die Zeile schon einer ist", () => {
    const { value, start, end } = at("- Kosten|");
    expect(show(value, toggleList(value, start, end, "bullet"))).toBe("Kosten|");
  });

  it("nummeriert mehrere Zeilen durch und überspringt Leerzeilen", () => {
    const { value, start, end } = at("«eins\n\nzwei\ndrei»");
    expect(applyEdit(value, toggleList(value, start, end, "number"))).toBe("1. eins\n\n2. zwei\n3. drei");
  });

  it("wandelt eine andere Liste um, statt Marker zu stapeln", () => {
    const { value, start, end } = at("«- eins\n- zwei»");
    expect(applyEdit(value, toggleList(value, start, end, "task"))).toBe("- [ ] eins\n- [ ] zwei");
  });

  it("eine Auswahl bis hinter den Zeilenumbruch fasst die nächste Zeile nicht an", () => {
    const value = "eins\nzwei";
    expect(applyEdit(value, toggleList(value, 0, 5, "bullet"))).toBe("- eins\nzwei");
  });

  it("eine leere Zeile wird zum ersten Punkt", () => {
    const { value, start, end } = at("Text\n|");
    expect(show(value, toggleList(value, start, end, "task"))).toBe("Text\n- [ ] |");
  });

  it("der Cursor im alten Marker landet am Anfang des Inhalts", () => {
    const { value, start, end } = at("1|. eins");
    expect(show(value, toggleList(value, start, end, "bullet"))).toBe("- |eins");
  });
});

describe("toggleWrap", () => {
  it("ohne Auswahl ist das Wort am Cursor gemeint", () => {
    const { value, start, end } = at("die Ver|waltung fragen");
    expect(show(value, toggleWrap(value, start, end, "**"))).toBe("die **«Verwaltung»** fragen");
  });

  it("zwischen Wörtern entsteht ein leeres Paar, der Cursor steht darin", () => {
    const { value, start, end } = at("fragen | ");
    expect(show(value, toggleWrap(value, start, end, "**"))).toBe("fragen **|** ");
  });

  it("Leerzeichen am Rand der Auswahl bleiben draußen", () => {
    const { value, start, end } = at("die« Verwaltung »fragen");
    expect(applyEdit(value, toggleWrap(value, start, end, "**"))).toBe("die **Verwaltung** fragen");
  });

  it("schaltet aus, wenn die Marker schon um die Auswahl stehen", () => {
    const { value, start, end } = at("die **«Verwaltung»** fragen");
    expect(show(value, toggleWrap(value, start, end, "**"))).toBe("die «Verwaltung» fragen");
  });

  it("schaltet aus, wenn die Marker in der Auswahl stehen", () => {
    const { value, start, end } = at("die «*Verwaltung*» fragen");
    expect(show(value, toggleWrap(value, start, end, "*"))).toBe("die «Verwaltung» fragen");
  });

  it("kursiv in fett macht aus fett nicht kursiv", () => {
    const { value, start, end } = at("**«fett»**");
    expect(applyEdit(value, toggleWrap(value, start, end, "*"))).toBe("***fett***");
  });

  it("fett und kursiv zugleich: fett geht weg, kursiv bleibt", () => {
    const { value, start, end } = at("***«beides»***");
    expect(applyEdit(value, toggleWrap(value, start, end, "**"))).toBe("*beides*");
  });

  it("über mehrere Zeilen je Zeile ein Paar, hinter dem Listenmarker", () => {
    const { value, start, end } = at("«- eins\n- zwei»");
    expect(applyEdit(value, toggleWrap(value, start, end, "**"))).toBe("- **eins**\n- **zwei**");
    expect(applyEdit("- **eins**\n- **zwei**", toggleWrap("- **eins**\n- **zwei**", 0, 20, "**"))).toBe("- eins\n- zwei");
  });
});

describe("continueList", () => {
  it("setzt den Punkt in der nächsten Zeile fort", () => {
    const { value, start, end } = at("- eins|");
    const e = continueList(value, start, end)!;
    expect(show(value, e)).toBe("- eins\n- |");
  });

  it("zählt Nummern hoch und behält Einrückung und Trenner", () => {
    const { value, start, end } = at("  3) drei|");
    expect(show(value, continueList(value, start, end)!)).toBe("  3) drei\n  4) |");
  });

  it("eine neue Aufgabe beginnt offen", () => {
    const { value, start, end } = at("- [x] erledigt|");
    expect(show(value, continueList(value, start, end)!)).toBe("- [x] erledigt\n- [ ] |");
  });

  it("nimmt den Rest der Zeile mit in den neuen Punkt", () => {
    const { value, start, end } = at("- Kosten| prüfen");
    expect(show(value, continueList(value, start, end)!)).toBe("- Kosten\n- | prüfen");
  });

  it("Enter auf einem leeren Punkt beendet die Liste", () => {
    const { value, start, end } = at("- eins\n- |");
    expect(show(value, continueList(value, start, end)!)).toBe("- eins\n|");
  });

  it("außerhalb einer Liste, im Marker oder mit Auswahl: der Browser macht es", () => {
    expect(continueList("Text", 4, 4)).toBeNull();
    expect(continueList("- eins", 1, 1)).toBeNull();
    expect(continueList("- eins", 2, 4)).toBeNull();
  });
});

describe("toggleTask und activeList", () => {
  it("hakt die Aufgabe am Cursor ab und wieder auf", () => {
    const { value, start } = at("- [ ] Antrag| lesen");
    const e = toggleTask(value, start)!;
    expect(applyEdit(value, e)).toBe("- [x] Antrag lesen");
    expect(e.selStart).toBe(start);
    expect(applyEdit("- [x] a", toggleTask("- [x] a", 7)!)).toBe("- [ ] a");
    expect(toggleTask("- kein Haken", 3)).toBeNull();
  });

  it("nennt die Liste der Zeile am Cursor", () => {
    expect(activeList("eins\n2. zwei", 8)).toBe("number");
    expect(activeList("eins\n2. zwei", 2)).toBeNull();
  });
});
