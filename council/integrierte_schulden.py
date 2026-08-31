"""Die dritte Schuldenzahl — was der ganze „Konzern Stadt" schuldet.

Über Oldenburgs Schulden hört man drei Zahlen, und alle drei stimmen. Sie
unterscheiden sich um das Siebzehnfache, weil sie Verschiedenes zählen:

===================================================  ==============  ==========
Abgrenzung                                            31.12.2024      je Kopf
===================================================  ==============  ==========
Kernhaushalt (Investitionskredite)                     43,69 Mio. €      248 €
Stadt als Rechtsträger, mit Eigenbetrieben            294,9  Mio. €    1.673 €
Integriert: dazu Extrahaushalte und Beteiligungen     740,33 Mio. €    4.198 €
===================================================  ==============  ==========

Die mittlere Zahl zeigt der Bereich seit Langem (Jahrbuch-Tabelle 1108,
``council/schulden.py``). Diese Schicht bringt die äußere dazu.

WARUM DAS ERST JETZT GEHT
-------------------------
Die Zahl allein wäre eine Behauptung: 740 Millionen, aus einer fremden Tabelle,
ohne Möglichkeit zu prüfen, ob sie überhaupt von dieser Stadt handelt. Seit die
Bilanz geparst ist (``council/bilanz.py``), gibt es eine: Der Tabellenband führt
die Schulden des **Kernhaushalts** getrennt aus, und dieser Wert muss der
Geldschulden-Position unserer eigenen Bilanz entsprechen. Am 31.12.2024:

* Tabellenband: 43.690.972 € (auf ganze Euro gerundet)
* unsere Bilanz: 43.690.971,71 €

Zwei Behörden, zwei Wege, 29 Cent Unterschied — das ist Rundung. Ohne diese
Probe käme die Zahl nicht herein.

DREI SÄTZE, DIE MITKOMMEN MÜSSEN
---------------------------------
Der Tabellenband ist keine Zahl zum Danebenlegen, er ist eine Modellrechnung,
und die Quelle schreibt selbst dazu, was man aus ihr **nicht** folgern darf:

1. **Der größte Brocken ist fremdes Geld.** 431,5 der 740,3 Millionen (58 %)
   sind anteilige Schulden von Unternehmen, an denen die Stadt **unter 50 %**
   hält. Der Tabellenband sagt, das erlaube „keine Rückschlüsse auf eine
   mögliche Haftung". Der Satz „Oldenburg hat 740 Millionen Schulden" ist
   deshalb falsch. Der Anteil steht in :func:`anteil_unter_50` und wird aus den
   Daten gerechnet, nicht abgeschrieben.
2. **Keine Zeitreihe.** Der Berichtskreis wechselt zwischen den Ausgaben; die
   Publikation warnt ausdrücklich davor, Jahrgänge zu vergleichen. Deshalb
   speichert diese Schicht **einen Stichtag je Ausgabe** und liefert keine
   Kurve. Die prozentuale Veränderung, die der Band je Spalte selbst ausweist,
   kommt als Angabe der Quelle mit — sie ist deren Rechnung, nicht unsere.
3. **Zuordnung über den Regionalschlüssel, nie über den Namen.** Im Blatt ``NI``
   stehen „Oldenburg (Oldb), Stadt" (ARS 034030000000), der Landkreis Oldenburg
   und „Lohne (Oldenburg), Stadt". Ein Namensvergleich träfe irgendwann das
   Falsche; :data:`ARS_OLDENBURG` trifft es nicht.

Quelle: Statistikportal der Statistischen Ämter des Bundes und der Länder,
„Integrierte Schulden der Gemeinden und Gemeindeverbände — Anteilige
Modellrechnung für den interkommunalen Vergleich", Tabelle 2, Blatt ``NI``.
Lizenz DL-DE/BY-2.0. Die Datei erscheint jährlich unter wechselnder Adresse
(der Ordner trägt Jahr und Monat der Veröffentlichung), deshalb sucht der
Ingest den Link auf der Übersichtsseite, statt eine Adresse hochzuzählen.
"""
from __future__ import annotations

import re

#: Amtlicher Regionalschlüssel der Stadt Oldenburg (Oldb).
ARS_OLDENBURG = "034030000000"

#: Das Blatt mit den niedersächsischen Gemeinden.
BLATT = "NI"

#: Übersichtsseite, auf der der Link zum Tabellenband steht.
UEBERSICHT_URL = ("https://www.statistikportal.de/de/veroeffentlichungen/"
                  "integrierte-schulden-der-gemeinden-und-gemeindeverbaende")

#: Der Link auf der Übersichtsseite. Der Ordner wechselt jährlich
#: („2025-12"), der Dateiname trägt den Stichtag und manchmal ein „_0".
LINK_MUSTER = re.compile(
    r'href="([^"]*Integrierte_Schulden[^"]*\.xlsx)"', re.IGNORECASE)

PROBE_KERNHAUSHALT = "integrierte_schulden_kernhaushalt"

PROBEN: dict[str, str] = {
    PROBE_KERNHAUSHALT: (
        "Der Tabellenband weist die Schulden des Kernhaushalts getrennt aus. "
        "Dieser Wert stimmt mit der Geldschulden-Position der städtischen "
        "Bilanz überein — zwei Behörden, zwei Wege, dieselbe Zahl."),
}

#: Wie weit die beiden Kernhaushalts-Zahlen auseinanderliegen dürfen. Der
#: Tabellenband rundet auf ganze Euro, die Bilanz führt Cent — mehr als ein
#: Euro Unterschied ist keine Rundung mehr.
KERN_TOLERANZ = 1.0

#: Die Spalten des Blatts, in ihrer Reihenfolge. Namen sind die der Quelle,
#: gekürzt. Die Nummern sind Spaltenindizes, keine Tabellennummern.
SPALTEN: dict[str, int] = {
    "ars": 0, "name": 1, "verwaltungsform": 2, "population": 3,
    "insgesamt": 4, "insgesamt_change": 5, "je_einwohner": 6,
    "gesamthaushalt": 7, "gesamthaushalt_change": 8,
    "kernhaushalt": 9, "kernhaushalt_change": 10,
    "extra_budgets": 11, "extrahaushalte_change": 12,
    "extra_100": 13, "extra_50_100": 14, "extra_under_50": 15,
    "sonstige": 16, "sonstige_change": 17,
    "sonstige_100": 18, "sonstige_50_100": 19, "other_below_50": 20,
}

#: Der Satz, den die Quelle selbst über ihre Grenzen schreibt — reist mit den
#: Zahlen, damit er nicht im Frontend steht und dort vergessen werden kann.
ABGRENZUNG = (
    "Diese Zahl ist eine Modellrechnung: Sie rechnet der Stadt die Schulden "
    "ihrer Betriebe und Beteiligungen anteilig zu — nach Höhe der Beteiligung, "
    "nicht nach Haftung. Der größere Teil davon stammt aus Unternehmen, an "
    "denen die Stadt weniger als die Hälfte hält; für deren Schulden haftet "
    "sie nicht. „Oldenburg hat 740 Millionen Euro Schulden“ wäre deshalb "
    "falsch.")

#: Warum es hier keine Kurve gibt.
KEINE_REIHE = (
    "Nur ein Stichtag, keine Zeitreihe: Welche Unternehmen mitgerechnet "
    "werden, ändert sich zwischen den Ausgaben — die Statistischen Ämter "
    "raten selbst davon ab, die Jahrgänge zu vergleichen.")

_STICHTAG = re.compile(r"am\s+31\.12\.(\d{4})")


def _zahl(wert: object) -> float | None:
    if wert is None:
        return None
    try:
        return float(str(wert).replace(".", "").replace(",", ".")
                     if isinstance(wert, str) and "," in str(wert) else wert)
    except (TypeError, ValueError):
        return None


def as_of_date(zeilen: list[list[object]]) -> int | None:
    """Das Jahr aus der Tabellenüberschrift („… am 31.12.2024 …").

    Aus dem Blatt gelesen und nicht aus dem Dateinamen: Der Dateiname trägt
    mal „2024_Tabellenband", mal ein angehängtes „_0", und ein Ordner
    „2025-12" nennt das Jahr der Veröffentlichung, nicht das der Zahlen."""
    for zeile in zeilen[:12]:
        for wert in zeile:
            treffer = _STICHTAG.search(str(wert or ""))
            if treffer:
                return int(treffer.group(1))
    return None


def lies_gemeinde(zeilen: list[list[object]], ars: str = ARS_OLDENBURG) -> dict | None:
    """Die Zeile einer Gemeinde, über ihren Regionalschlüssel gefunden."""
    for zeile in zeilen:
        if zeile and str(zeile[0]).strip() == ars:
            gefunden = {}
            for name, index in SPALTEN.items():
                roh = zeile[index] if index < len(zeile) else None
                gefunden[name] = roh if name in ("ars", "name", "verwaltungsform") \
                    else _zahl(roh)
            year = as_of_date(zeilen)
            if year is None:
                return None
            gefunden["year"] = year
            gefunden["ars"] = ars
            return gefunden
    return None


def anteil_unter_50(gefunden: dict) -> float | None:
    """Welcher Anteil der Summe aus Beteiligungen **unter 50 %** stammt.

    Gerechnet statt abgeschrieben: Der Wert entscheidet, wie die Zahl gelesen
    werden darf, und er ändert sich mit jeder Ausgabe. 2024 sind es 58 %."""
    gesamt = gefunden.get("insgesamt")
    if not gesamt:
        return None
    unter = (gefunden.get("extra_under_50") or 0.0) + (gefunden.get("other_below_50") or 0.0)
    return unter / gesamt


def kernprobe(gefunden: dict, bilanz_geldschulden: float | None) -> tuple[bool, str]:
    """Stimmt der Kernhaushalt des Tabellenbands mit unserer Bilanz überein?

    Die einzige Probe dieser Schicht — und ohne sie käme die Zahl nicht
    herein. Sie prüft nicht die 740 Millionen (die kann niemand gegenrechnen),
    sondern dass die Tabelle **von dieser Stadt** handelt und ihre Systematik
    zu unserer passt."""
    kern = gefunden.get("kernhaushalt")
    if kern is None:
        return False, "der Tabellenband nennt keinen Kernhaushalt"
    if bilanz_geldschulden is None:
        return False, ("die eigene Bilanz führt für diesen Stichtag keine "
                       "Geldschulden — ohne Gegenstück keine Probe")
    ab = abs(kern - bilanz_geldschulden)
    if ab > KERN_TOLERANZ:
        return False, (f"Kernhaushalt {kern:,.2f} € gegen Bilanz "
                       f"{bilanz_geldschulden:,.2f} € — {ab:,.2f} € Unterschied")
    return True, f"Kernhaushalt und Bilanz stimmen auf {ab:.2f} € überein"
