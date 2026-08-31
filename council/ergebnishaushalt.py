"""Der Gesamtergebnishaushalt: was die Stadt für ein **Planjahr** ansetzt.

``council_ergebnisrechnung`` (aus den Jahresabschlüssen) kann die Erträge nach
Arten nur für Jahre zeigen, die **abgeschlossen** sind — 2025 und 2026 haben
noch keinen Jahresabschluss und stehen deshalb dort gar nicht. Die Zahlen
existieren trotzdem längst: Jeder Haushaltsplan trägt als Anlage 005 den
*Gesamtergebnishaushalt*, 16–18 Seiten mit genau derselben Postengliederung
(01 Steuern, 02 Zuwendungen, … 11 sonstige ordentliche Erträge).

Der wichtigste Satz dieses Moduls
---------------------------------
**Von den sechs Wertespalten ist genau eine der Haushaltsansatz.** Der
Tabellenkopf lautet::

    Erträge und Aufwendungen | Ergebnis 2024 | Ansatz 2025 | Ansatz 2026
                             | Ansatz 2027   | Ansatz 2028 | Ansatz 2029

Das Dokument schreibt über alle fünf Planspalten „Ansatz". Das ist die
Sprache des Haushaltsrechts, nicht die der Sache: Aufgestellt wird **ein**
Jahr — hier 2026. 2027–2029 sind die *mittelfristige Finanzplanung* nach
§ 8 NKomVG: eine Vorausschau, die jeder neue Haushalt neu schreibt. Wie neu,
lässt sich messen: Von 23 Posten stimmen zwischen dem Plan eines Jahres und
dem des Folgejahres für dasselbe Finanzplanungsjahr **0 bis 2** überein. Wer
diese Spalten als Ansatz speichert, behauptet für 2029 einen Plan, den es
nicht gibt.

Deshalb trägt jede Zeile ihre ``art`` (``ansatz`` oder ``finanzplanung``) und
den ``plan_budget_year``, aus dem sie stammt. Erst beides zusammen ist eine
ehrliche Angabe: „Finanzplanung für 2029, aufgestellt im Haushalt 2026".

Die **Vorjahresspalte** (hier: Ansatz 2025) wird bewusst **nicht** gespeichert,
obwohl sie wie ein Ansatz aussieht. Sie ist der *fortgeschriebene* Stand des
Vorjahres und weicht vom ursprünglich beschlossenen ab — über sieben
Jahrgangspaare gemessen stimmen nur 7 bis 11 von 23 Posten überein
(Nachträge, Umschichtungen). Zwei Zeilen mit demselben Jahr und demselben
Posten, aber verschiedenen Beträgen, und keine Regel, welche gilt: Das wäre
eine Lücke, die aussieht wie ein Bestand.

Die Rechenproben
----------------
Wie überall im Haushalts-Bereich gilt: Was sich nicht am Dokument selbst
nachrechnen lässt, kommt nicht in die Datenbank.

1. **Summenzeilen** (:func:`summenprobe`) — die Tabelle führt sie selbst:
   Posten 01–11 ergeben 12 („Summe ordentliche Erträge"), 13–19 ergeben 20,
   und 12 − 20 = 21. Geprüft wird das in **allen sechs Spalten**, also 18-mal
   je Dokument. Eine verrutschte Spalte fällt damit sofort auf.
2. **Planspalte** (:func:`planspaltenprobe`) — das eigentlich Heikle: Welche
   der sechs Spalten ist der Haushaltsansatz? Der Kopf beantwortet das
   der Reihenfolge nach (dritte Spalte), aber eine Reihenfolge ist eine
   Annahme. Das Dokument sagt es zum Glück selbst: Die Planjahr-Spalte steht
   in jeder Zeile **ein zweites Mal**, am Ende der Zahlenkolonne — im PDF ist
   sie hervorgehoben und wird beim Textextrakt doppelt ausgegeben. Übernommen
   wird ein Dokument nur, wenn diese Wiederholung in **jeder** gelesenen Zeile
   steht und auf dieselbe Spalte zeigt wie der Kopf.

Was der Parser nicht liest
--------------------------
Die Einzelkonten über den Postenzeilen („30110000 Grundsteuer A …") bleiben
liegen. Ihre Spaltenreihenfolge ist eine andere als die der Postenzeilen — die
Planjahr-Spalte steht dort **hinten** statt an dritter Stelle. Für die
Postenzeilen ist das bewiesen (die Summenprobe geht in allen sechs Spalten
auf), für die Kontenzeilen wäre es geraten. Gebraucht werden sie ohnehin
nicht: Die Einnahmearten sind die Posten.

Es ist der Entwurf, nicht der Beschluss
---------------------------------------
Die Anlage 005 hängt an der Vorlage, mit der die Verwaltung den Haushalt
**einbringt** — vier der acht Dokumente sagen das im Titel („Haushalt 2026
Verwaltungsentwurf", „2024 005 IVw"). Was der Rat in seinen Beratungen daran
noch ändert, steht hier nicht drin.

Nachgemessen an den sechs Jahren, für die es inzwischen einen Jahresabschluss
gibt: Der Ansatz dieser Tabelle liegt bei den ordentlichen Erträgen um 0,7 bis
13,1 Mio. € **unter** dem Ansatz, den der Jahresabschluss desselben Jahres als
Bezugsgröße führt. Das ist eine Größenordnung mehr, als die Stiftungen erklären
(die machen an der Ist-Spalte höchstens 0,45 Mio. aus) — es ist der Abstand
zwischen Entwurf und Beschluss.

Deshalb trägt jede Herkunft dieser Schicht ``stand="Haushaltsplan JJJJ, Anlage
005 — Stand der Einbringung"``. Wer die Zahl anzeigt, zeigt den Vorschlag der
Verwaltung; das gehört dazugesagt, sonst steht dort „der Rat hat 388,4 Mio. €
Steuern eingeplant", und beschlossen hat er womöglich etwas anderes.

Was das Dokument nicht enthält
------------------------------
**Keine Aufteilung nach Teilhaushalten.** Der Jahresabschluss führt in
Abschnitt 5 je Bereich eine „Teil-Ergebnisrechnung THH01…"; hier gibt es das
nicht. In allen acht Dokumenten kommt weder „THH" noch „Teilhaushalt" noch
„Teilergebnishaushalt" auch nur einmal vor (nachgezählt 16.08.2026) — sie
sind eine einzige stadtweite Tabelle über 16 bis 18 Seiten.

Für ein Bild, das die Herkunft des Geldes seiner Verwendung gegenüberstellt,
liefert diese Schicht deshalb nur die **linke** Seite. Die rechte müsste aus
einer der beiden anderen kommen, und beide haben einen Haken, der benannt
gehört, statt ihn zu überkleben:

* ``council_produkte`` (aus den THH-Plänen) deckt nur 8 bis 10 der 13
  Teilhaushalte ab — für die Jahrgänge 2019–2023 summieren sich die Produkte
  auf 17 bis 36 % **weniger** als der Gesamtergebnishaushalt für dasselbe Jahr
  ausweist. Und die THH-Pläne reichen bis zum Ansatzjahr 2025, nicht 2026.
* ``council_haushalt`` trägt für 2025 und 2026 dreizehn Bereiche samt
  Summenzeile, ist also vollständig — aber eine **andere Gliederung**: Für
  2026 nennt es 812,9 Mio. € Erträge und 883,9 Mio. € Aufwendungen, wo diese
  Tabelle 788,6 und 880,8 Mio. € führt. Die Differenz ist echt und nicht
  aufgeklärt; beide Zahlen in ein Bild zu legen, ohne sie zu erklären, wäre
  die Sorte stille Falschaussage, gegen die dieses Modul geschrieben ist.
"""
from __future__ import annotations

import re

from council.finanzberichte import ERGEBNIS_POSTEN, SUMMEN_POSTEN

#: Beträge der Postenzeilen. Anders als im Jahresabschluss stehen hier
#: Planwerte **ohne** Nachkommastellen („332.705.720"): Ein Haushaltsansatz
#: wird in vollen Euro beschlossen. Nur die Ist-Spalte trägt Cent.
_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")

#: Fußnotenzeichen hinter einem Postennamen („… u. allgemeine Umlagen 1)").
#: Ohne diesen Schnitt wäre die „1" die erste Zahl der Zeile, und die Posten 02
#: und 05 fielen in den Jahrgängen 2025 und 2026 aus der Tabelle — mit ihnen
#: die Summenprobe und damit beide Jahrgänge, die dieses Modul überhaupt erst
#: nötig machen.
_FUSSNOTE = re.compile(r"(?<=[A-Za-zÄÖÜäöüß)])\s\d\)")

#: Rundungstoleranz der Rechenproben in Euro. Die Stadt rundet ihre
#: Summenzeilen kaufmännisch; über sieben Summanden kommen so bis zu ein paar
#: Cent zusammen, in der Praxis nie mehr als 1 €.
TOLERANZ_EUR = 1.0

#: Der Tabellenkopf: eine Ist-Spalte, dann fünf Planspalten.
_KOPF = re.compile(r"(Ergebnis|Ansatz)\s+(20\d\d)")

#: So viele Wertespalten hat die Tabelle.
SPALTEN = 6

#: Welche Spalte welche Bedeutung hat — die einzige Stelle, an der die
#: Zuordnung steht. ``None`` heißt: gelesen, aber nicht gespeichert.
#: Spalte 0 ist das Ist des Vorvorjahres (Gegenprobe, s. Modulkopf),
#: Spalte 1 der fortgeschriebene Vorjahresansatz.
SPALTEN_ARTEN: tuple[str | None, ...] = (
    None, None, "ansatz", "finanzplanung", "finanzplanung", "finanzplanung")

#: Die Summenbeziehungen, die das Dokument selbst führt:
#: ``(Summenposten, Teilposten…)``.
_SUMMEN: tuple[tuple[int, tuple[int, ...]], ...] = (
    (12, tuple(range(1, 12))),
    (20, tuple(range(13, 20))),
)


def _eur(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _erstes_wort(text: str) -> str:
    m = re.match(r"[A-Za-zÄÖÜäöüß]+", text.strip())
    return m.group(0).lower() if m else ""


def kopfjahre(text: str) -> list[int]:
    """Die sechs Jahre des Tabellenkopfs, in Spaltenreihenfolge.

    Leer, wenn der Kopf nicht die erwartete Form hat: eine Ist-Spalte, fünf
    Planspalten, alle Jahre lückenlos aufsteigend. Geraten wird nichts — ein
    Dokument mit anderem Kopf ist ein anderes Dokument."""
    treffer = _KOPF.findall(text[:2500])[:SPALTEN]
    if len(treffer) != SPALTEN:
        return []
    arten = [a for a, _ in treffer]
    jahre = [int(j) for _, j in treffer]
    if arten != ["Ergebnis"] + ["Ansatz"] * (SPALTEN - 1):
        return []
    if jahre != list(range(jahre[0], jahre[0] + SPALTEN)):
        return []
    return jahre


def budget_year(text: str | None) -> int | None:
    """Für welches Planjahr dieses Dokument der Haushalt ist.

    Das ist die **dritte** Kopfspalte, nicht die erste und nicht die letzte:
    Die erste ist das Ist des Vorvorjahres, die letzten drei sind
    Finanzplanung. Auch nicht die Jahreszahl im Label — die trägt nur die
    Hälfte der Dokumente (vier von acht heißen schlicht
    „005 Gesamtergebnishaushalt")."""
    jahre = kopfjahre(text or "")
    return jahre[2] if jahre else None


def _zeilen_lesen(text: str) -> dict[int, list[float | None]]:
    """Je Postennummer die sechs Spaltenwerte plus die Wiederholung der
    Planjahr-Spalte (Index 6) — oder nichts, wo die Zeile keine Zahlen führt.

    Drei Dinge, die hier schiefgehen können und deshalb ausdrücklich
    behandelt sind:

    * **Der Postenname läuft über zwei Zeilen** („02. Zuwendungen u.
      allgemeine\\nUmlagen"). Deshalb wird der Text vorher flachgezogen.
    * **Ein Posten hat gar keine Werte.** Posten 10 (Bestandsveränderungen)
      ist in allen acht Jahrgängen leer; hinter seiner Nummer steht direkt die
      nächste Kontenzeile („10. Bestandsveränderungen 35111004
      Konzessionsabgabe …"). Aus deren Kontonummer würde die Betrags-Regex
      „351", „110", „04" machen. Der Schutz ist die erste Spalte: Sie ist
      immer ein Ist-Wert und trägt immer Cent. Wo sie das nicht tut, ist die
      Zeile keine Postenzeile — und die Summenprobe beweist am Ende, dass die
      fehlenden Posten wirklich 0 waren.
    * **Hinter Posten 24 steht eine Zeile ohne Nummer** („Jahresergebnis
      Überschuss (+)/Fehlbetrag (−)"). Ihre Zahlen gehörten sonst noch zu
      Posten 24."""
    flach = _FUSSNOTE.sub("", re.sub(r"\s*\n\s*", " ", text))
    # An den Postennummern aufteilen („01. …", „20.= …"); zwischen zwei Posten
    # darf beliebig viel Seitenkopf stehen.
    teile = re.split(r"(?<![\d,.])(\d\d)\.(?:\s*=)?\s", flach)
    roh: dict[int, str] = {}
    for i in range(1, len(teile) - 1, 2):
        # Erster Treffer gewinnt: Wiederholungen sind Seitenköpfe.
        roh.setdefault(int(teile[i]), teile[i + 1])

    aus: dict[int, list[float | None]] = {}
    for nr, label in ERGEBNIS_POSTEN.items():
        block = roh.get(nr)
        if not block:
            continue
        if _erstes_wort(block) != _erstes_wort(label):
            # Die Nummerierung hat sich verschoben (im Gesamtabschluss des
            # Konzerns ist genau das passiert). Lieber nichts als eine Zahl
            # unter falschem Namen.
            continue
        zahlen = _BETRAG.findall(re.split(r"Jahresergebnis", block[:300])[0])
        if len(zahlen) < SPALTEN or "," not in zahlen[0]:
            continue
        werte: list[float | None] = [_eur(z) for z in zahlen[:SPALTEN]]
        werte.append(_eur(zahlen[SPALTEN]) if len(zahlen) > SPALTEN else None)
        aus[nr] = werte
    return aus


def summenprobe(zeilen: dict[int, list[float | None]],
                toleranz: float = TOLERANZ_EUR) -> tuple[bool, str]:
    """Die Pflicht-Probe: Die Tabelle muss in **jeder** Spalte aufgehen.

    ``01–11 = 12``, ``13–19 = 20`` und ``12 − 20 = 21`` — dreimal je Spalte,
    achtzehnmal je Dokument. Fehlende Einzelposten zählen als 0; wenn die
    Summe trotzdem stimmt, hat das Dokument selbst bewiesen, dass sie 0 waren
    (Posten 10 ist in allen acht Jahrgängen dieser Fall).

    Gibt ``(besteht, begruendung)`` zurück; die Begründung nennt die erste
    gerissene Beziehung samt Spalte und Restbetrag."""
    for nr in (12, 20, 21):
        if nr not in zeilen:
            return False, f"Summenzeile {nr} fehlt"
    for sp in range(SPALTEN):
        for summe, teile in _SUMMEN:
            gerechnet = sum(zeilen[n][sp] or 0.0 for n in teile if n in zeilen)
            rest = gerechnet - (zeilen[summe][sp] or 0.0)
            if abs(rest) > toleranz:
                return False, (f"Spalte {sp + 1}: Posten {teile[0]}–{teile[-1]} "
                               f"ergeben {gerechnet:,.2f}, Zeile {summe} nennt "
                               f"{zeilen[summe][sp]:,.2f} ({rest:+,.2f} €)")
        rest = ((zeilen[12][sp] or 0.0) - (zeilen[20][sp] or 0.0)
                - (zeilen[21][sp] or 0.0))
        if abs(rest) > toleranz:
            return False, f"Spalte {sp + 1}: 12 − 20 − 21 = {rest:+,.2f} €"
    return True, ""


def planspaltenprobe(zeilen: dict[int, list[float | None]],
                     toleranz: float = TOLERANZ_EUR) -> tuple[bool, str]:
    """Zeigt die Wiederholung am Zeilenende auf die dritte Spalte?

    Der Kopf sagt, dass die dritte Spalte das Planjahr ist. Diese Probe ist
    die zweite, unabhängige Stimme dafür — und die einzige, die nicht auf
    einer Reihenfolge beruht: Das PDF hebt die Planjahr-Spalte hervor und gibt
    sie beim Textextrakt ein zweites Mal aus, am Ende der Zahlenkolonne.

    Verlangt wird sie in **jeder** gelesenen Zeile. Eine Wiederholung, die in
    der Hälfte der Zeilen fehlt, wäre kein Beleg, sondern ein Zufall."""
    if not zeilen:
        return False, "keine Zeile gelesen"
    for nr, werte in sorted(zeilen.items()):
        echo = werte[SPALTEN]
        if echo is None:
            return False, (f"Posten {nr}: die hervorgehobene Planjahr-Spalte "
                           f"wird nicht wiederholt")
        if abs(echo - (werte[2] or 0.0)) > toleranz:
            return False, (f"Posten {nr}: die Wiederholung nennt {echo:,.2f}, "
                           f"die dritte Spalte {werte[2]:,.2f} — sie zeigt "
                           f"nicht auf das Planjahr")
    return True, ""


def lies(text: str) -> dict:
    """Einen Gesamtergebnishaushalt auswerten.

    Liefert ``{budget_year, jahre, zeilen, ist, ist_jahr, probes, bestanden,
    nachweis}``:

    * ``zeilen`` — je Posten und Planjahr ein dict mit ``year``, ``art``
      (``ansatz``/``finanzplanung``), ``nr``, ``label``, ``amount``,
      ``is_total``. Nur, was gespeichert werden darf.
    * ``ist`` — die Ist-Spalte des Vorvorjahres, ``{nr: amount}``. Sie wird
      **nicht** gespeichert (dafür gibt es ``council_ergebnisrechnung``),
      sondern dient als Gegenprobe gegen den Jahresabschluss.
    * ``bestanden`` — ob beide Pflicht-Proben aufgehen. Ist sie ``False``, ist
      ``zeilen`` leer: Ein Dokument, dessen Tabelle nicht aufgeht, gibt keine
      halben Zahlen her."""
    jahre = kopfjahre(text)
    if not jahre:
        return {"budget_year": None, "jahre": [], "zeilen": [], "ist": {},
                "ist_jahr": None, "probes": [], "bestanden": False,
                "nachweis": "Tabellenkopf nicht in der erwarteten Form"}

    gelesen = _zeilen_lesen(text)
    probes = []
    for name, fn in (("ergebnishaushalt_summenzeilen", summenprobe),
                     ("ergebnishaushalt_planspalte", planspaltenprobe)):
        ok, warum = fn(gelesen)
        probes.append({"probe": name, "ok": ok, "warum": warum})
    bestanden = all(p["ok"] for p in probes)

    zeilen: list[dict] = []
    if bestanden:
        for sp, art in enumerate(SPALTEN_ARTEN):
            if art is None:
                continue
            for nr, werte in sorted(gelesen.items()):
                zeilen.append({
                    "year": jahre[sp], "art": art, "nr": nr,
                    "label": ERGEBNIS_POSTEN[nr],
                    "amount": werte[sp],
                    "is_total": 1 if nr in SUMMEN_POSTEN else 0,
                })
    return {
        "budget_year": jahre[2], "jahre": jahre, "zeilen": zeilen,
        "ist": {nr: w[0] for nr, w in gelesen.items()},
        "ist_jahr": jahre[0], "probes": probes, "bestanden": bestanden,
        "nachweis": nachweis(gelesen, probes),
    }


def nachweis(zeilen: dict[int, list[float | None]], probes: list[dict]) -> str:
    """Ein Satz für den Beleg-Chip: was gerechnet wurde und wie es ausging.

    Steht später neben der Zahl auf der Seite, deshalb in Zahlen statt in
    Namen — „18 Summenproben" ist nachvollziehbar, „summenprobe ok" nicht."""
    gerissen = [p["warum"] for p in probes if not p["ok"]]
    if gerissen:
        return "; ".join(gerissen)
    return (f"{len(_SUMMEN) * SPALTEN + SPALTEN} Summenproben über "
            f"{SPALTEN} Spalten aufgegangen · Planjahr-Spalte in "
            f"{len(zeilen)} von {len(zeilen)} Zeilen wiederholt")


#: Wie weit die Ist-Spalte vom gespeicherten Jahresabschluss abweichen darf,
#: bevor der Lauf sie meldet — gemessen am Summenposten 12, nicht am einzelnen
#: Posten (ein kleiner Posten mit 5 % Abweichung bewegt nichts, die Summe
#: schon). Über acht Jahrgänge liegt der schlechteste Wert bei 0,075 %; 0,5 %
#: lässt also das Siebenfache Luft und schlägt trotzdem an, wenn eine Spalte
#: aus dem falschen Jahr oder dem falschen Dokument stammt.
GEGENPROBE_GRENZE = 0.005


def gegenprobe(ist: dict[int, float], gespeichert: dict[int, float],
               toleranz: float = TOLERANZ_EUR,
               grenze: float = GEGENPROBE_GRENZE) -> dict:
    """Die Ist-Spalte gegen einen bereits gespeicherten Jahrgang halten.

    **Achtung, hier liegt eine Falle.** Der Gesamtergebnishaushalt ist die
    *Gesamt*ebene — Kernverwaltung **einschließlich** der nicht rechtsfähigen
    Stiftungen. ``council_ergebnisrechnung`` führt die Kernverwaltung allein.
    Beide Zahlen sind richtig, beide heißen „Ergebnis 2024", und sie sind
    nicht dieselben: Über acht Jahrgänge stimmen 6 bis 8 von 23 Posten exakt
    überein, der Rest liegt um bis zu 0,45 Mio. € bei 800 Mio. auseinander.

    Gegen die *Gesamt*ergebnisrechnung desselben Jahresabschlusses trifft die
    Spalte dagegen auf den Cent — 184 von 184 Posten in allen acht
    Jahrgängen. Damit ist die Ebene bewiesen und nicht bloß vermutet.

    Diese Funktion **verwirft deshalb nichts**. Sie misst den Abstand zur
    Kernverwaltung und sagt, ob er in der Größenordnung liegt, die die
    Stiftungen erklären (``plausibel``). Ein Gate wäre sie nur, wenn wir die
    Gesamtebene selbst gespeichert hätten; als Gate über eine andere Ebene
    würde sie irgendwann einen richtigen Jahrgang wegwerfen."""
    gemeinsam = sorted(set(ist) & set(gespeichert))
    if not gemeinsam:
        return {"geprueft": 0, "gleich": 0, "groesste_abweichung": 0.0,
                "posten": None, "anteil": 0.0, "plausibel": None}
    treffer = [nr for nr in gemeinsam if abs(ist[nr] - gespeichert[nr]) <= toleranz]
    groesste, posten = max((abs(ist[nr] - gespeichert[nr]), nr) for nr in gemeinsam)
    bezug = abs(ist.get(12) or gespeichert.get(12) or 0) or None
    anteil = groesste / bezug if bezug else 0.0
    return {"geprueft": len(gemeinsam), "gleich": len(treffer),
            "groesste_abweichung": groesste, "posten": posten,
            "anteil": anteil, "plausibel": anteil <= grenze}
