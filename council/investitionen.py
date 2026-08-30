"""Die Investitionen des Finanzhaushalts — was die Stadt bauen und kaufen will.

Der Haushalts-Bereich hing bis 08/2026 vollständig am **Ergebnishaushalt**:
laufende Erträge und Aufwendungen, Personal, Zuschüsse, Abschreibungen. Darin
steht keine einzige Investition. Ein Schulneubau taucht dort nur als
Abschreibung auf, verteilt über Jahrzehnte, lange nachdem gebaut wurde — der
Bau selbst, das Grundstück, die Feuerwehrfahrzeuge, die Radwege stehen im
**Finanzhaushalt**, der zweiten Hälfte jedes Haushaltsplans. Sie nach Ein- und
Auszahlungen zu führen statt nach Erträgen und Aufwendungen ist keine
Formsache: Es ist der Unterschied zwischen „was verbraucht die Stadt in diesem
Jahr?" und „was legt sie in diesem Jahr an?".

Die Quelle
----------
Datensatz 1101 des Open-Data-Portals (``opendata.oldenburg.de``, Lizenz
dl-de/by-2-0) — derselbe Datensatz, aus dem schon der Plan-Ergebnishaushalt
kommt (``haushalt.OPENDATA_CSV_URLS``), nur das zweite Tabellenblatt. Je
Jahrgang eine Datei mit 15 Zeilen::

    Teilhaushalt;Bezeichnung;Einzahlungen [Euro];Auszahlungen [Euro]
    THH01;Verwaltungsfuehrung;0;44500
    …
    THH13;Nicht rechtsfaehige Stiftungen;27900;0
    Finanzhaushalt Gesamtinvestitionen;;39672063;80781520
    Gesamtbetrag des Finanzhaushaltes;;743796496;850520503

Die Rechenprobe
---------------
Die Datei rechnet sich selbst vor: Die Teilhaushalts-Zeilen ergeben die Zeile
*Finanzhaushalt Gesamtinvestitionen* — in **beiden** Spalten. Über die vier
verfügbaren Jahrgänge (2022–2025) geht sie auf den Euro genau auf, acht Proben,
Restbetrag jeweils 0 €. Sie ist damit die einzige Portal-Quelle des Bereichs
mit einer Probe im Dokument selbst; die drei anderen CSVs (Steuern,
Steuerkraft, Einwohner) tragen ausdrücklich keine (``herkunft.UNGEPRUEFT``).

Die zweite Summenzeile, *Gesamtbetrag des Finanzhaushaltes*, ist **nicht** von
dieser Probe gedeckt: Sie zählt auch die laufende Verwaltungstätigkeit mit
(Personal, Zuschüsse, Steuern) und ist deshalb um ein Vielfaches größer als die
Investitionen. Kein Wert der Datei summiert sich auf sie. Sie wird trotzdem
übernommen, weil sie die Bezugsgröße ist, die aus „80,8 Mio. €" erst eine
Aussage macht (2025: 9,5 % aller Auszahlungen) — aber als das, was sie ist,
mit ``herkunft.UNGEPRUEFT``.

Was diese Zahlen **nicht** hergeben
------------------------------------
Zwei Grenzen, die auf die Seite gehören und nicht in eine Fußnote:

1. **Kein einzelnes Vorhaben.** Die Datei sagt „Verkehr und Straßenbau:
   10,5 Mio. €", nicht welche Straße. Wer wissen will, ob eine bestimmte
   Schule saniert wird, findet das hier nicht — dafür braucht es das
   Investitionsprogramm aus dem Haushaltsplan-PDF, eine eigene Schicht.
2. **Plan, nicht Ist.** Der Datensatz heißt „Haushaltsplan Stadt Oldenburg
   <Jahr>". Was am Jahresende wirklich verbaut wurde, steht nicht darin. Bei
   Investitionen ist der Abstand notorisch groß (Planung zieht sich, Aufträge
   werden nicht vergeben) — eine Seite, die „so viel wird gebaut" behauptet,
   behauptet mehr als die Quelle.

Und eine dritte, die nur diese Datei betrifft: **Das Jahr steht nicht in der
Datei.** Es steht im Dateinamen und im Titel des Datensatzes. Der Jahrgang
kommt deshalb aus der URL (:func:`jahrgang_aus_url`) und wird in der Herkunft
als solcher benannt — geraten wird er nicht.
"""
from __future__ import annotations

import re

#: Rundungstoleranz der Rechenprobe in Euro.
#:
#: **Kleiner als ein Euro, und das ist der Punkt.** Die Datei führt volle Euro
#: ohne Nachkommastellen; die kleinste Abweichung, die es hier überhaupt geben
#: kann, ist damit 1 €. Eine Toleranz von 1 € ließe genau diesen Fall durch —
#: die Probe wäre dann für den einzigen Fehler blind, den sie sehen könnte
#: (aufgefallen beim Schreiben von ``tests/test_investitionen.py``). Ein halber
#: Euro nimmt Cent-Rundungen auf, falls das Portal eines Tages auf
#: Cent-Darstellung umstellt, und weist jede Abweichung ab, die in der heutigen
#: Darstellung überhaupt entstehen kann. Gemessen geht die Probe in allen vier
#: Jahrgängen auf **0,00 €** auf.
TOLERANZ_EUR = 0.5

#: So viele Teilhaushalts-Zeilen muss eine Datei mindestens tragen, damit ihre
#: Summenprobe etwas bedeutet. Die vier gemessenen Jahrgänge haben je 13; eine
#: Datei mit zwei Zeilen, deren Summe zufällig aufgeht, ist keine Tabelle,
#: sondern ein Rest. Bewusst nicht auf 13 festgenagelt: Ein neuer
#: Teilhaushalts-Zuschnitt soll den Import nicht stoppen.
MINDEST_TEILHAUSHALTE = 5

#: Wie die Summenzeilen in der ersten Spalte heißen.
_GESAMT = "Finanzhaushalt Gesamtinvestitionen"
_FINANZHAUSHALT = "Gesamtbetrag des Finanzhaushaltes"

#: „THH01" → 1.
_THH = re.compile(r"^THH\s*0*(\d+)$", re.IGNORECASE)

#: Der Jahrgang aus dem Dateinamen des Portals.
_JAHR_IN_URL = re.compile(r"(20\d\d)_Finanzhaushalt", re.IGNORECASE)

#: Das Portal transliteriert Umlaute („Verwaltungsfuehrung") und ist dabei
#: nicht einmal über die Jahrgänge hinweg konsistent: 2022 schreibt „Verkehr
#: und Straßenbau" und „Gruen u Friedhoefe", 2025 „Strassenbau" und „Gruen und
#: Friedhoefe". Bekannte Schreibweisen werden auf eine Form zurückgeführt,
#: damit ein Teilhaushalt über die Jahre denselben Namen trägt; unbekannte
#: laufen unverändert durch (ein neuer Zuschnitt soll nicht stillstehen).
#:
#: KEIN generisches ue→ü: „Steuer" und „Neubau" würden dabei zerschossen.
#:
#: Verwandt mit ``haushalt._CSV_NAMEN`` (dieselbe Portal-Eigenheit im
#: Ergebnishaushalt-Blatt), aber bewusst eigenständig: Dort sind es
#: Bereichsnamen einer anderen Tabelle, hier Teilhaushalte mit Nummer. Der
#: Schlüssel dieser Zeilen ist ohnehin ``thh_nr`` — der Name ist Beschriftung,
#: nicht Identität.
NAMEN: dict[str, str] = {
    "Verwaltungsfuehrung": "Verwaltungsführung",
    "Wirtschaftsfoerderung, Liegenschaften": "Wirtschaftsförderung, Liegenschaften",
    "Verkehr und Strassenbau": "Verkehr und Straßenbau",
    "Umwelt, Bauordnung, Gruen und Friedhoefe": "Umwelt, Bauordnung, Grün und Friedhöfe",
    "Umwelt, Bauordnung, Gruen u Friedhoefe": "Umwelt, Bauordnung, Grün und Friedhöfe",
    "Nicht rechtsfaehige Stiftungen": "Nicht rechtsfähige Stiftungen",
}


def _eur(s: str) -> float | None:
    """Betrag aus dem Portal-CSV → Euro. ``None`` bei leerer Zelle.

    Die Datei führt heute volle Euro ohne Tausenderzeichen („44500"). Die
    deutsche Schreibweise („44.500,00") wird trotzdem verstanden — dasselbe
    Portal liefert sie im Ergebnishaushalt-Blatt, und ein Formatwechsel soll
    hier keine falschen Zahlen ergeben, sondern gar keine."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _de(betrag: float, vorzeichen: bool = False) -> str:
    """Betrag in deutscher Schreibweise — „80.781.520,00".

    Nicht bloß Kosmetik: Der Rückgabewert von :func:`nachweis` landet als
    ``probe_ergebnis`` in der Herkunft und steht damit im Beleg neben der Zahl
    auf der Seite. Pythons ``{:,.2f}`` liefert dort englische Trennzeichen —
    „80,781,520.00" liest sich für Leser*innen wie ein anderer Betrag."""
    s = f"{abs(betrag):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if vorzeichen:
        return ("+" if betrag >= 0 else "−") + s
    return ("−" if betrag < 0 else "") + s


def name(roh: str) -> str:
    """Teilhaushalts-Bezeichnung des Portals → lesbare Schreibweise."""
    return NAMEN.get(" ".join((roh or "").split()), " ".join((roh or "").split()))


def jahrgang_aus_url(url: str | None) -> int | None:
    """Für welchen Haushaltsjahrgang eine Portal-Datei gilt.

    Die Datei selbst trägt **keine** Jahresangabe — keine Spalte, keine
    Kopfzeile, nichts. Sie steht im Dateinamen
    (``…_StadtOL_2025_Finanzhaushalt.csv``) und im Titel des Datensatzes
    („Finanzhaushalt der Stadt Oldenburg 2025"). Beides ist dieselbe Angabe der
    Stadt; der Dateiname ist die, die der Abruf ohnehin schon in der Hand hat.

    Das ist die schwächste Stelle dieser Quelle, und sie wird deshalb
    ausgewiesen statt weggelassen: Die Herkunft nennt den Dateinamen als
    Fundstelle des Jahrgangs."""
    m = _JAHR_IN_URL.search(url or "")
    return int(m.group(1)) if m else None


def kopfprobe(kopfzeile: str) -> bool:
    """Steht in der Kopfzeile, was wir zu lesen glauben?

    Kein Ersatz für die Rechenprobe, sondern der Schutz davor, eine ganz
    andere Datei zu parsen: Läge unter der URL eines Tages das
    Ergebnishaushalt-Blatt, hätte es Erträge statt Einzahlungen — und die
    Summenprobe ginge womöglich trotzdem auf."""
    k = (kopfzeile or "").lower()
    return ("teilhaushalt" in k and "einzahlung" in k and "auszahlung" in k)


def summenprobe(zeilen: list[dict], gesamt: dict | None,
                toleranz: float = TOLERANZ_EUR) -> tuple[bool, str]:
    """Die Pflicht-Probe: Ergeben die Teilhaushalte die Summenzeile der Datei?

    Geprüft werden **beide** Spalten. Nur die Auszahlungen zu prüfen wäre die
    halbe Probe: Eine verrutschte Spalte fiele dort nicht auf, und die
    Einzahlungen (Zuschüsse, Grundstücksverkäufe) sind die Zahl, an der die
    Nettobelastung hängt.

    Gibt ``(besteht, begruendung)`` zurück; die Begründung nennt die Spalte und
    den Restbetrag — er ist die Zahl, die im Beleg steht."""
    if gesamt is None:
        return False, f"die Zeile „{_GESAMT}“ fehlt"
    if len(zeilen) < MINDEST_TEILHAUSHALTE:
        return False, (f"nur {len(zeilen)} Teilhaushalts-Zeilen gelesen "
                       f"(mindestens {MINDEST_TEILHAUSHALTE} erwartet)")
    for feld, spalte in (("einzahlungen", "Einzahlungen"),
                         ("auszahlungen", "Auszahlungen")):
        gerechnet = sum(z[feld] for z in zeilen)
        rest = gerechnet - gesamt[feld]
        if abs(rest) > toleranz:
            return False, (f"{spalte}: die {len(zeilen)} Teilhaushalte ergeben "
                           f"{_de(gerechnet)} €, die Summenzeile nennt "
                           f"{_de(gesamt[feld])} € ({_de(rest, vorzeichen=True)} €)")
    return True, ""


def nachweis(zeilen: list[dict], gesamt: dict | None, ok: bool, warum: str) -> str:
    """Ein Satz für den Beleg-Chip: was gerechnet wurde und wie es ausging.

    In Zahlen statt in Namen — „13 Teilhaushalte, Rest 0 €" ist nachprüfbar,
    „summenprobe ok" ist eine Behauptung."""
    if not ok:
        return f"Summenprobe gerissen — {warum}"
    reste = [abs(sum(z[f] for z in zeilen) - gesamt[f])
             for f in ("einzahlungen", "auszahlungen")]
    return (f"{len(zeilen)} Teilhaushalte ergeben die Summenzeile der Datei in "
            f"beiden Spalten (größter Restbetrag {_de(max(reste))} €)")


def lies(csv_text: str, year: int) -> dict:
    """Eine Finanzhaushalts-Datei des Portals auswerten.

    Liefert ``{year, zeilen, gesamt, finanzhaushalt, bestanden, nachweis}``:

    * ``zeilen`` — je Teilhaushalt ein dict mit ``thh_nr``, ``bezeichnung``,
      ``einzahlungen``, ``auszahlungen``.
    * ``gesamt`` — die Summenzeile *Finanzhaushalt Gesamtinvestitionen*, also
      das Ziel der Rechenprobe.
    * ``finanzhaushalt`` — die Zeile *Gesamtbetrag des Finanzhaushaltes*
      (Investitionen **und** laufende Verwaltungstätigkeit) oder ``None``.
      Von keiner Probe der Datei gedeckt, s. Modulkopf.
    * ``bestanden`` — ob die Summenprobe aufgeht. Ist sie ``False``, sind
      ``zeilen`` und ``gesamt`` leer bzw. ``None``: Eine Tabelle, die nicht
      aufgeht, gibt keine halben Zahlen her.
    """
    roh = [ln for ln in (csv_text or "").splitlines() if ln.strip()]
    leer = {"year": year, "zeilen": [], "gesamt": None, "finanzhaushalt": None,
            "bestanden": False}
    if not roh:
        return {**leer, "nachweis": "Datei ist leer"}
    if not kopfprobe(roh[0]):
        return {**leer, "nachweis": f"Kopfzeile nicht in der erwarteten Form: {roh[0]!r}"}

    zeilen: list[dict] = []
    gesamt: dict | None = None
    finanzhaushalt: dict | None = None
    for line in roh[1:]:
        teile = line.split(";")
        if len(teile) < 4:
            continue
        schluessel = " ".join(teile[0].split())
        ein, aus = _eur(teile[2]), _eur(teile[3])
        if ein is None or aus is None:
            continue
        werte = {"einzahlungen": ein, "auszahlungen": aus}
        m = _THH.match(schluessel)
        if m:
            zeilen.append({"thh_nr": int(m.group(1)),
                           "bezeichnung": name(teile[1]), **werte})
        elif schluessel.startswith(_GESAMT):
            gesamt = {"bezeichnung": _GESAMT, **werte}
        elif schluessel.startswith(_FINANZHAUSHALT):
            finanzhaushalt = {"bezeichnung": _FINANZHAUSHALT, **werte}

    ok, warum = summenprobe(zeilen, gesamt)
    text = nachweis(zeilen, gesamt, ok, warum)
    if not ok:
        # Die Bezugsgröße fällt mit: Ohne geprüfte Investitionssumme daneben
        # wäre sie eine große Zahl ohne Aussage.
        return {**leer, "nachweis": text}
    return {"year": year, "zeilen": sorted(zeilen, key=lambda z: z["thh_nr"]),
            "gesamt": gesamt, "finanzhaushalt": finanzhaushalt,
            "bestanden": True, "nachweis": text}
