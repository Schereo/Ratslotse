"""Ist der Bestand einer Stadt plausibel? — der Wächter für stumme Ernte-Fehler.

**Warum es diese Datei gibt.** Am 08.09.2026 lagen vier Fehler gleichzeitig im
Bestand, und **kein einziger** hat sich gemeldet: Kein Lauf ist abgestürzt,
kein Test war rot, keine Kennzahl sah verdächtig aus. Die Daten waren nur
falsch.

1. Magdeburgs Beratungen zeigten auf Tagesordnungspunkte aus einem zweiten
   Kennungsraum — **0 von 700** Vorlagen hatten ein Ergebnis, obwohl fast
   6.000 Punkte eines tragen.
2. Magdeburg und Münster vergaben dieselbe Beratungs-Kennung mehrfach; die
   Stationen überschrieben sich gegenseitig (575 bzw. 467 verloren).
3. Die Rückwärts-Blätterung von ALLRIS las bei Sitzungen das Feld ``date``,
   das es dort nicht gibt — jede Sitzung galt als undatiert und damit als alt,
   der Abruf brach nach zwei Seiten ab. Osnabrück hatte 137 Sitzungen zu 2.864
   Vorlagen, Potsdam 222 zu 5.994.
4. „nicht empfohlen" wurde als Zustimmung gezählt (275-mal das Gegenteil
   dessen, was im Protokoll steht).

Ein Adapter je Ratsinformationssystem sorgt dafür, dass eine Reparatur allen
Städten desselben Herstellers zugutekommt — Leipzig und Bonn erben die vier
oben, ohne dass sie jemand dort noch einmal findet. Was er **nicht** leistet:
den nächsten, noch unbekannten Fehler bemerken. Dafür ist diese Datei da.

**Die Bänder sind gemessen, nicht gesetzt.** Jede Regel nennt den Bereich, in
dem die sechs Städte des Bestands liegen, und ist so weit gefasst, dass eine
gesunde siebte hineinpasst. Ein Befund heißt nicht „kaputt", sondern „sieh
nach, bevor du diese Stadt benutzt".
"""
from __future__ import annotations

from dataclasses import dataclass

from council.cities.store import CitiesStore

#: Ab wie vielen Vorlagen eine Stadt überhaupt geprüft wird. Darunter sind
#: alle Anteile Rauschen — eine Stadt mit zwölf Vorlagen hat entweder gerade
#: erst angefangen oder einen ganz anderen Fehler.
MIN_PAPIERE = 200


@dataclass(frozen=True)
class Befund:
    body_id: str
    regel: str
    wert: float
    band: tuple[float, float]
    #: Was der Wert für die Daten bedeutet — nicht was er ist.
    text: str

    def __str__(self) -> str:
        return (f"{self.body_id}: {self.regel} = {self.wert:.2f} "
                f"(erwartet {self.band[0]:g}–{self.band[1]:g}) — {self.text}")


def _anteil(zaehler: float, nenner: float) -> float | None:
    return zaehler / nenner if nenner else None


#: Regel → (Band, was ein Ausreißer bedeutet). Die Bänder stammen aus dem
#: Bestand vom 08.09.2026, nachdem die vier Fehler oben behoben waren.
REGELN: dict[str, tuple[tuple[float, float], str]] = {
    "papiere_je_sitzung": (
        (0.5, 15.0),
        "Zu viele Vorlagen je Sitzung heißt: Sitzungen fehlen. Ohne Sitzung "
        "gibt es keinen Tagesordnungspunkt und damit kein Ergebnis — genau "
        "so sah die kaputte Rückwärts-Blätterung aus (Osnabrück: 20,9)."),
    "anteil_mit_ergebnis": (
        (0.15, 1.0),
        "So wenige Vorlagen mit Beratungsergebnis heißt fast immer: Die "
        "Beratungen finden ihren Tagesordnungspunkt nicht (Magdeburg: 0,00)."),
    "anteil_mit_text": (
        (0.50, 1.0),
        "Ohne Text wird eine Vorlage nicht eingeordnet und ist für den "
        "Vergleich unsichtbar. Meist ist die Textstufe nie gelaufen "
        "(Osnabrück: 0,29) oder die Dateien wurden nie geholt (Potsdam: 0,12)."),
    "anteil_mit_beratung": (
        (0.30, 1.0),
        "Vorlagen ganz ohne Beratungsfolge: Entweder liefert die "
        "Schnittstelle sie nicht, oder ihre Kennungen kollidieren und "
        "überschreiben sich beim Schreiben."),
}


def pruefe(main: CitiesStore, embed_model: str = "") -> list[Befund]:
    """Jede Stadt gegen die Bänder halten. Leere Liste heißt: unauffällig."""
    befunde: list[Befund] = []
    for z in main.stats(embed_model):
        if (z["papers"] or 0) < MIN_PAPIERE:
            continue
        werte = {
            "papiere_je_sitzung": _anteil(z["papers"], z["meetings"]),
            "anteil_mit_ergebnis": _anteil(z["papers_with_outcome"], z["papers"]),
            "anteil_mit_text": _anteil(z["papers_with_text"], z["papers"]),
            "anteil_mit_beratung": _anteil(z["papers_with_consultation"], z["papers"]),
        }
        for regel, (band, text) in REGELN.items():
            wert = werte[regel]
            if wert is None or band[0] <= wert <= band[1]:
                continue
            befunde.append(Befund(z["id"], regel, wert, band, text))
    return befunde


def unbekanntes_vokabular(main: CitiesStore, body_id: str,
                          limit: int = 10) -> list[tuple[str, int]]:
    """Häufige Ergebnistexte, die auf ``none`` fallen — je Stadt.

    Das ist die Liste, mit der man eine **neue** Stadt anschließt: Was hier
    oben steht, versteht ``council.cities.model.outcome`` nicht. Manches
    gehört dorthin („schriftliche Stellungnahme" ist wirklich kein Ergebnis),
    manches ist eine Lücke in der Regel — und eine Lücke, die tausendfach
    vorkommt, macht die halbe Beschlusslage einer Stadt unsichtbar.

    Sie ist bewusst **kein** Befund mit Schwelle: Welcher Text was bedeutet,
    kann nur ein Mensch entscheiden.
    """
    return [(r["result_raw"], r["n"]) for r in main.unmapped_outcomes(body_id, limit)]
