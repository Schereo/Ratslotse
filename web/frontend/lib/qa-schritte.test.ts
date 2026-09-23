import { describe, expect, it } from "vitest";

import { ASK_SCHRITTE, ERKLAER_SCHRITTE, lottiSchrittText } from "./qa-schritte";

describe("lottiSchrittText", () => {
  it("nennt für die Erklärung, was gerade passiert", () => {
    expect(lottiSchrittText("context")).toBe("Lotti liest die Seite");
    expect(lottiSchrittText("answer")).toBe("Lotti schreibt");
  });

  it("nimmt auf dem Ratsweg die Schritte der KI-Frage", () => {
    expect(lottiSchrittText("search", true)).toBe(ASK_SCHRITTE.search);
    expect(lottiSchrittText("expand", true)).toBe(ASK_SCHRITTE.expand);
  });

  it("unterscheidet die beiden `answer` — sie heißen nicht dasselbe", () => {
    // Beide Endpunkte melden `answer`; im Fenster spricht Lotti, auf der
    // Fragen-Seite antwortet „Ratslotse". Eine gemeinsame Tabelle hätte den
    // einen Text in den anderen Zusammenhang gezogen.
    expect(lottiSchrittText("answer", false)).not.toBe(lottiSchrittText("answer", true));
    expect(lottiSchrittText("answer", true)).toBe(ASK_SCHRITTE.answer);
  });

  it("fällt auf einen wahren Satz zurück, wenn noch kein Schritt gemeldet ist", () => {
    // Der deterministische Weg (Glossar, Seitenwissen) meldet gar keinen
    // Schritt und ist in Millisekunden fertig — leer bliebe die Anzeige
    // stumm, und genau das war der Befund.
    for (const s of [null, undefined, "", "unbekannt"]) {
      expect(lottiSchrittText(s)).toBe("Lotti überlegt");
      expect(lottiSchrittText(s, true)).toBe("Lotti überlegt");
    }
  });

  it("sagt beim Gang ins Archiv, WARUM jetzt etwas anderes passiert", () => {
    // PR 23: Lotti geht bei einer Archivfrage von selbst ins Archiv. Ohne
    // diesen Satz sähe man nur, dass es plötzlich länger dauert.
    expect(lottiSchrittText("archiv")).toMatch(/Ratsarchiv/);
    // Er gilt auch auf dem Ratsweg — dort läuft die Frage ja weiter.
    expect(lottiSchrittText("archiv", true)).toBe(lottiSchrittText("archiv"));
  });

  it("ein Schritt des einen Wegs gilt nicht auf dem anderen", () => {
    // `context` gibt es nur bei `/explain`, `search` nur bei `/ask`.
    expect(lottiSchrittText("context", true)).toBe("Lotti überlegt");
    expect(lottiSchrittText("search", false)).toBe("Lotti überlegt");
  });

  it("deckt genau die Schritte ab, die die beiden Ströme senden", () => {
    // Kommt im Backend ein Schritt dazu, fällt er hier auf — und nicht erst
    // als „Lotti überlegt" im Fenster, wo niemand ihn vermisst.
    expect(Object.keys(ERKLAER_SCHRITTE).sort()).toEqual(["answer", "archiv", "context"]);
    expect(Object.keys(ASK_SCHRITTE).sort()).toEqual(["answer", "expand", "search"]);
  });
});
