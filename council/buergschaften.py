"""Wofür die Stadt geradesteht — der Bürgschaftsbestand aus dem Jahresabschluss.

Die Stadt hatte Ende 2024 **43,7 Millionen Euro** eigene Geldschulden. Im
selben Jahresabschluss steht eine zweite Zahl, fünfmal so groß: **220,3
Millionen Euro** Bürgschaften. Das ist kein Geld, das die Stadt schuldet —
es ist Geld, für das sie einspringt, wenn jemand anderes nicht zahlt. Wer nur
die erste Zahl kennt, kennt die kleinere Hälfte.

Der Sprung, um den es geht
--------------------------
Der Bestand lag jahrelang bei 75 Millionen und verdreifachte sich 2022 auf
217,6 Millionen. Der Grund steht im Dokument selbst: die Übernahme von
Bürgschaften zugunsten des **Klinikums Oldenburg AöR über 135,9 Millionen
Euro**. Das ist die Zahl, die die Reihe erklärt, und sie wird deshalb
mitgeliefert statt der Leserschaft überlassen.

ZWEI DARREICHUNGSFORMEN, UND SIE SIND NICHT GLEICH GENAU
--------------------------------------------------------
Die Quelle wechselt mitten in der Reihe die Form, und das muss an der Zahl
sichtbar bleiben:

* **2019 und 2020** — eine frühe Übersichtstabelle des Jahresabschlusses
  nennt „Bürgschaftsverpflichtungen" **auf den Cent** (2019:
  74.991.739,16 €). 2020 führt daneben noch „davon nicht genehmigungspflichtig
  (< 500.000 Euro)".
* **ab 2022** — Abschnitt **6.2.10 „Eventualverbindlichkeiten"** des Anhangs
  nennt nur noch **gerundete Millionen** („rd. 220,3 Millionen Euro"). Die
  frühe Tabelle gibt es dort nicht mehr.

Deshalb trägt jede Zeile ``exact``. Eine Anzeige, die 220,3 Mio. und
74.991.739,16 € nebeneinander gleich formatiert, behauptet eine Genauigkeit,
die die Quelle für das eine Jahr hat und für das andere nicht.

**2021 hat gar keine eigene Fundstelle.** Der Jahresabschluss 2021 nennt den
Bestand nicht; die Zahl (83,7 Mio.) steht nur als *Anfangsbestand* im
Dokument des Folgejahres. Sie kommt deshalb mit ``out_next_year=True`` herein
— eine echte Zahl aus einem amtlichen Dokument, aber nicht aus dem Abschluss
des Jahres, das sie beschreibt.

DIE PROBE: DIE KETTE ÜBER DIE DOKUMENTE
----------------------------------------
Ab 2022 nennt jeder Abschnitt 6.2.10 **beide** Enden — „hat sich von X
(31.12. Vorjahr) auf Y (31.12. Jahr) erhöht". Der Anfangsbestand eines
Jahrgangs muss der Endbestand des vorigen sein. Das ist eine Probe, die kein
Rechenweg von uns ist, sondern ein Abgleich zweier unabhängiger Dokumente:
2023 nennt 217,6 als Anfang, 2022 nennt 217,6 als Ende.

Was hier bewusst NICHT passiert
-------------------------------
**Wir addieren nie selbst.** Es liegt nahe, die einzelnen
Bürgschafts-Beschlüsse des Rates zusammenzuzählen — das Ergebnis wäre falsch:
Verlängerungen und Anpassungen *ersetzen* einander, statt sich zu addieren,
und eine über zehn Jahre verlängerte Bürgschaft käme mehrfach in die Summe.
Addierbar ist allein der Bestand aus dem Anhang, weil ihn die Stadt selbst
als Bestand ausweist.

ABGRENZUNG ZU BILANZPOSTEN 3.7
-------------------------------
Die Bilanz führt „Rückstellungen für drohende Verpflichtungen aus
Bürgschaften, Gewährleistungen und anhängigen Gerichtsverfahren" — 2024
**1.301.337,58 €**. Das ist **nicht** der Bürgschaftsbestand, sondern das,
womit die Stadt an Ausfall tatsächlich rechnet: 0,6 % des Volumens. Beide
Zahlen gehören nebeneinander, und keine darf für die andere stehen. Der
Konstante :data:`RUECKSTELLUNG_ROLLE` sagt, welcher Bilanzposten gemeint ist.
"""
from __future__ import annotations

import re

#: Bilanzposten mit der Rückstellung für erwartete Ausfälle — die Gegenzahl
#: zum Bestand. `council/bilanz.py` führt die Posten unter Namen, nicht unter
#: Gliederungsnummern; im Dokument ist es Passivposten 3.7.
RUECKSTELLUNG_ROLLE = "buergschaftsrueckstellung"

#: Die andere Gegenzahl: was die Stadt selbst schuldet. 2024 standen 43,7 Mio. €
#: Geldschulden 220,3 Mio. € Bürgschaften gegenüber — Faktor fünf. Der Bestand
#: ohne diese Zahl daneben ist eine Zahl ohne Maßstab.
GELDSCHULDEN_ROLLE = "geldschulden"

#: Der Abschnitt des Anhangs, aus dem der Bestand ab 2022 kommt.
ABSCHNITT = "6.2.10 Eventualverbindlichkeiten"

#: Die Zeile der frühen Übersichtstabelle (2019/2020).
TABELLENZEILE = "Bürgschaftsverpflichtungen"

#: Was diese Zahl ist und was sie nicht ist — reist mit den Zahlen statt im
#: Frontend zu stehen, dieselbe Regel wie bei `ausgabenreihe.ABGRENZUNG`: Eine
#: Erklärung, die es in zwei Sprachen gibt, driftet. Und ohne sie liest sich
#: „220 Millionen" wie eine Rechnung, die demnächst kommt.
ABGRENZUNG = (
    "Eine Bürgschaft ist keine Schuld der Stadt. Sie verspricht damit, für ein "
    "Darlehen einzuspringen, das jemand anderes aufgenommen hat — meist eine "
    "ihrer eigenen Gesellschaften. Gezahlt wird nur, wenn die zahlungsunfähig "
    "wird. Deshalb steht der Bestand nicht in der Bilanz, sondern als "
    "„Eventualverbindlichkeit“ im Anhang.")

PROBE_KETTE = "buergschaft_kette"
PROBE_TABELLE = "buergschaft_tabelle"

PROBEN: dict[str, str] = {
    PROBE_KETTE: ("Der Anfangsbestand dieses Jahrgangs stimmt mit dem "
                  "Endbestand überein, den der Jahresabschluss des Vorjahres "
                  "nennt — zwei Dokumente, dieselbe Zahl."),
    PROBE_TABELLE: ("Der Betrag steht auf den Cent in der Übersichtstabelle "
                    "des Jahresabschlusses."),
}

#: Wie weit Anfangs- und Endbestand auseinanderliegen dürfen, damit die Kette
#: noch als geschlossen gilt: 50.000 €. Die Quelle rundet ab 2022 auf
#: Zehntel-Millionen (100.000 €), zwei Rundungen können sich also um eine
#: halbe Stelle unterscheiden, ohne dass ein Widerspruch vorliegt.
KETTE_TOLERANZ = 50_000.0

_MIO = re.compile(
    r"(?:rd\.\s*)?(\d{1,3}(?:,\d+)?)\s*Millionen\s*Euro\s*\(\s*31\.12\.(\d{4})\s*\)")
_EURO = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")
#: „Der Bürgschaftsbestand hat sich …" — der Satz, der beide Enden nennt. Die
#: Jahreszahl steht mal als „in 2024", mal als „im Jahr 2022"; beides zählt.
_SATZ = re.compile(
    r"Der\s+Bürgschaftsbestand\s+hat\s+sich\s+(?:in|im\s+Jahr)\s+(\d{4})(.{0,400}?)"
    r"(?:erhöht|verringert|verändert)", re.S)
#: Der Grund, den das Dokument selbst nennt — der VOLLSTÄNDIGE Satz, samt
#: seiner Einleitung („Der Grund für die deutliche Erhöhung ist …"). Ein
#: erster Entwurf schnitt die Einleitung ab und lieferte „die Übernahme von
#: Bürgschaften …" — inhaltlich richtig, aber als kleingeschriebenes
#: Satzfragment, das auf der Seite falsch aussieht. Den Satz zu kürzen und
#: dann seinen ersten Buchstaben groß zu schreiben wäre die schlechtere
#: Lösung: Das ist dann nicht mehr der Wortlaut der Stadt.
_GRUND = re.compile(
    r"((?:Der\s+Grund[^.]{0,60}?ist|Hintergrund\s+ist)\b.{0,320}?\.)", re.S)
_KLINIKUM = re.compile(
    r"(\d{1,3},\d)\s*Millionen\s*Euro", re.S)


def _zahl(roh: str) -> float:
    return float(roh.replace(".", "").replace(",", "."))


def _glatt(text: str) -> str:
    """Trennstriche am Zeilenende auflösen, dann Zwischenraum vereinheitlichen.

    Die PDF-Extraktion bricht Wörter um („ver- bürgten", „zurech- nen"). Ohne
    diesen Schritt findet kein Muster den Satz, in dem so ein Bruch liegt."""
    return re.sub(r"\s+", " ", re.sub(r"(\w)-\s+(\w)", r"\1\2", text))


def parse_bestand(text: str, year: int) -> dict | None:
    """Den Bürgschaftsbestand aus einem Jahresabschluss lesen.

    Liefert ``None``, wenn der Jahrgang ihn nicht nennt (2017, 2018, 2021).
    Sonst ein dict mit ``bestand``, ``exact`` und — wo die Quelle ihn nennt —
    ``prior_year_stock``/``prior_year_year`` für die Kettenprobe.
    """
    t = _glatt(text)

    # Weg 1: der Anhang (ab 2022). Er nennt beide Enden und den Grund.
    satz = _SATZ.search(t)
    if satz and int(satz.group(1)) == year:
        enden = _MIO.findall(satz.group(0))
        nach_jahr = {int(j): float(b.replace(",", ".")) * 1e6 for b, j in enden}
        if year in nach_jahr:
            gefunden: dict = {
                "year": year,
                "bestand": nach_jahr[year],
                "exact": False,
                "quelle": "anhang",
                "citation": ABSCHNITT,
                "out_next_year": False,
            }
            vor = [j for j in nach_jahr if j == year - 1]
            if vor:
                gefunden["prior_year_year"] = year - 1
                gefunden["prior_year_stock"] = nach_jahr[year - 1]
            grund = _GRUND.search(t[satz.start():satz.start() + 900])
            if grund:
                gefunden["grund"] = _glatt(grund.group(1)).strip()
            return gefunden

    # Weg 2: die frühe Übersichtstabelle (2019/2020) — auf den Cent.
    stelle = t.find(TABELLENZEILE)
    if stelle >= 0:
        amount = _EURO.search(t[stelle:stelle + 260])
        if amount:
            return {
                "year": year,
                "bestand": _zahl(amount.group(1)),
                "exact": True,
                "quelle": "tabelle",
                "citation": TABELLENZEILE,
                "out_next_year": False,
            }
    return None


def out_next_year(gefunden: dict) -> dict | None:
    """Den Anfangsbestand eines Jahrgangs als eigene Zeile ausgeben.

    Für 2021 die einzige Quelle: Der Abschluss 2021 nennt den Bestand nicht,
    der von 2022 nennt ihn als Anfangswert. Die Zeile trägt deshalb
    ``out_next_year=True`` — sie ist belegt, aber nicht aus dem Abschluss des
    Jahres, das sie beschreibt, und die Anzeige muss das sagen dürfen."""
    if "prior_year_stock" not in gefunden:
        return None
    return {
        "year": gefunden["prior_year_year"],
        "bestand": gefunden["prior_year_stock"],
        "exact": False,
        "quelle": "anhang",
        "citation": f"{ABSCHNITT} (Jahresabschluss {gefunden['year']})",
        "out_next_year": True,
    }


def series(gefundene: list[dict]) -> list[dict]:
    """Die fertige Reihe: eigene Fundstellen, Lücken aus dem Folgejahr gefüllt.

    Die Regel steht hier und nicht beim Aufrufer, weil sie leicht falsch
    herum gerät: Ab 2022 nennt **jeder** Jahrgang auch den Anfangsbestand,
    also den Endbestand des Vorjahres. Wer die alle übernimmt, überschreibt
    sechs Jahrgänge mit der Zweitnennung aus dem Folgejahr — inhaltlich
    dieselbe Zahl, aber mit schlechterer Fundstelle und, für 2019/2020, unter
    Verlust der Cent-Genauigkeit. Ein Nachtrag zählt deshalb nur da, wo der
    Jahrgang selbst schweigt. Das ist genau 2021."""
    nach_jahr = {g["year"]: g for g in gefundene}
    for g in gefundene:
        supplement = out_next_year(g)
        if supplement and supplement["year"] not in nach_jahr:
            nach_jahr[supplement["year"]] = supplement
    return [nach_jahr[j] for j in sorted(nach_jahr)]


def klinikum_amount(gefunden: dict) -> float | None:
    """Die Zahl aus dem Grund-Satz, wo er eine nennt (2022: 135,9 Mio. €)."""
    grund = gefunden.get("grund")
    if not grund:
        return None
    treffer = _KLINIKUM.search(grund)
    return float(treffer.group(1).replace(",", ".")) * 1e6 if treffer else None


def kettenprobe(zeilen: list[dict]) -> list[str]:
    """Wo die Kette reißt — leere Liste heißt: sie schließt überall.

    Geprüft wird nur, wo ein Jahrgang **beide** Enden nennt; ein fehlender
    Anfangsbestand ist kein Riss, sondern eine Quelle, die schweigt."""
    nach_jahr = {z["year"]: z for z in zeilen if not z.get("out_next_year")}
    risse = []
    for z in zeilen:
        if "prior_year_stock" not in z:
            continue
        prior_rate = nach_jahr.get(z["prior_year_year"])
        if not prior_rate:
            continue
        ab = abs(prior_rate["bestand"] - z["prior_year_stock"])
        if ab > KETTE_TOLERANZ:
            risse.append(
                f"{z['year']}: nennt {z['prior_year_stock']/1e6:.1f} Mio. € als Stand "
                f"31.12.{z['prior_year_year']}, der Abschluss {z['prior_year_year']} nennt "
                f"{prior_rate['bestand']/1e6:.1f} Mio. € ({ab/1e6:.1f} Mio. Unterschied)")
    return risse
