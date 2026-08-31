"""Die Bilanz der Stadt aus dem Jahresabschluss — was die Stadt **besitzt**.

Der Haushalts-Bereich zeigte bis hierher, was die Stadt einnimmt, ausgibt und
schuldet. Die Vermögensseite fehlte ganz. Und der größte Posten steht dort:
die **Pensionsrückstellungen**, ein Vielfaches der Kreditschulden. Auf die
naheliegende Frage „Oldenburg hat kaum Kredite, also keine Schulden?" ist das
die Antwort.

Fundstelle ist Abschnitt 2.1 „Bilanz der Stadt Oldenburg zum 31.12.JJJJ" des
Jahresabschlusses (``council_anlagen``) — dasselbe Dokument, aus dem
``council/finanzberichte.py`` schon Ergebnis- und Finanzrechnung liest. Kein
neuer Download.

Zwei Zahlen, die beide „die Pensionsrückstellungen" heißen
-----------------------------------------------------------
Der Bilanzauszug 2024 schreibt untereinander::

    3.      Rückstellungen                              329.095.270,90  337.210.902,05
    3.1     Pensionsrückstellungen und
            ähnliche Verpflichtungen 1)                 290.925.292,00  311.789.660,00
    3.1.1   Pensionsrückstellungen                      249.721.281,00  266.259.316,00
    3.1.2   Beihilferückstellungen                       41.204.011,00   45.530.344,00

**Beide Zahlen stimmen, sie messen nur Verschiedenes.** 311,79 Mio. € ist die
Oberposition 3.1 einschließlich der Beihilfe, 266,26 Mio. € die Pension allein
(3.1.1). Die Differenz ist Position 3.1.2, und sie geht auf den Cent auf —
in jedem gelesenen Jahrgang (:data:`PROBE_GLIEDERUNG`). Der Rechenschafts-
bericht desselben Jahres bestätigt es ein drittes Mal in Worten: „Die
Pensionsrückstellungen wurden um 16,5 Millionen Euro erhöht […], die
Beihilferückstellungen um 4,3 Millionen Euro […]. Für die Beihilfe-
rückstellungen wurden 17,10% […] der Pensionsrückstellungen angesetzt."
Nachgerechnet: 266.259.316 − 249.721.281 = 16.538.035, und
45.530.344 / 266.259.316 = 17,10 %.

Wer eine der beiden Zahlen zeigt, muss sagen welche — deshalb trägt jede
Zeile ihre :data:`ROLLEN`-Marke und ihren Wortlaut aus dem Dokument.

Das Layout wechselt zweimal, und nicht an derselben Stelle
-----------------------------------------------------------
Naheliegend wäre „bis 2020 so, ab 2021 anders". Am Bestand nachgesehen sind
es aber **zwei** Änderungen in **zwei verschiedenen Jahren**:

===========  ================  =====================================
Jahrgang     Nummerierung      Anordnung
===========  ================  =====================================
2017–2019    römisch (I.–V.)   erst der ganze Aktiva-Block, dann Passiva
2020         römisch (I.–V.)   zweispaltig ineinander verschränkt
2021–2024    arabisch (1.–5.)  zweispaltig ineinander verschränkt
===========  ================  =====================================

2020 ist also der Jahrgang, den eine Fallunterscheidung „römisch = Blocksatz"
falsch liest — und zwar lautlos, weil die Hälfte der Zeilen trotzdem ankommt.

Verschränkt heißt: Beide Seiten teilen sich die Textzeile, und die rechte
Spalte fängt **mitten in der Zeile** an, direkt hinter den Beträgen der
linken::

    1.2.3  Rücklagen aus Investitions-
    zuwendungen für nicht abnutzbare
    Vermögensgegenstände
    4.372.861,06 4.439.504,15 2.   Sachvermögen 1) 608.118.677,60 605.573.107,06
                              └─ hier beginnt die Aktivseite wieder

Ein Parser, der Zeilen an ``^`` aufteilt, verliert damit jeden zweiten
Hauptposten. :data:`_POSITION` verankert deshalb **nicht** am Zeilenanfang,
sondern an „steht hinter Leerraum und vor einem Buchstaben" — Beträge fangen
nie mit einem Buchstaben an, Gliederungsnummern immer.

Und die **Nummer ist als Schlüssel wertlos**: „1.1" gibt es auf beiden
Seiten, und welche der beiden gerade dran ist, verrät die Reihenfolge nicht
mehr. Deshalb erkennt dieser Parser seine Zeilen wie
``finanzberichte.ROLLEN`` an dem **Namen, den das Dokument ihnen selbst
gibt** — die sechs Aktiv- und neun Passivzeilen aus :data:`ROLLEN`. Die
Nummer wird mitgeschrieben, aber nichts hängt an ihr. Alle drei Layouts
lesen sich damit ohne eine einzige Fallunterscheidung.

Was hier **nicht** gelesen wird
--------------------------------
Die vollständige Bilanz hat über hundert Unterpositionen. Gespeichert wird
nur, was :data:`ROLLEN` benennt. Der Grund ist der eben genannte: Eine Zeile
ohne Rollen-Marke ließe sich im Layout ab 2021 keiner Seite sicher zuordnen,
und eine Bilanzzeile auf der falschen Seite wäre schlimmer als eine fehlende.

Ebenfalls nicht hier: die Anlagen zum Anhang (Abschnitt 8 — Anlagen-,
Forderungs-, Schulden- und Rückstellungsübersicht). Sie fallen dem Textlimit
von ``scripts/backfill_anlagen_texte.py`` zum Opfer und stehen in **keinem**
Jahrgang im Volltext.
"""
from __future__ import annotations

import re

# --- Was die Bilanz führt ----------------------------------------------------

#: Aktiva oder Passiva — die Seite, auf der ein Posten steht.
AKTIVA = "aktiva"
PASSIVA = "passiva"

#: Die Zeilen, auf die es ankommt, erkannt am Wortlaut des Dokuments.
#:
#: ``(rolle, seite, ebene, muster)``. ``ebene`` 1 sind die Hauptposten, aus
#: denen die Bilanzsumme besteht; ``ebene`` 2 und 3 sind Unterposten, die
#: einzeln etwas erzählen.
#:
#: Die Muster sind mit ``$`` verankert, und das ist keine Kosmetik: Ohne den
#: Anker verschluckte „Rückstellungen" jede der acht Unterzeilen, die so
#: heißen, und „Schulden" auch die Geldschulden. Wo ein Jahrgang abkürzt,
#: steht die Kurzform mit im Muster — 2019 schreibt „Pensionsrückst. und
#: ähnliche Verpflichtungen", 2024 schreibt es aus.
ROLLEN: tuple[tuple[str, str, int, str], ...] = (
    # --- Aktiva: was die Stadt hat ---
    ("immaterielles_vermoegen", AKTIVA, 1, r"^Immaterielles Verm[öo]gen$"),
    ("sachvermoegen", AKTIVA, 1, r"^Sachverm[öo]gen$"),
    ("infrastrukturvermoegen", AKTIVA, 2, r"^Infrastrukturverm[öo]gen$"),
    ("finanzvermoegen", AKTIVA, 1, r"^Finanzverm[öo]gen$"),
    ("liquide_mittel", AKTIVA, 1, r"^Liquide Mittel$"),
    ("aktive_rap", AKTIVA, 1, r"^Aktive Rechnungsabgrenzung$"),
    # --- Passiva: wem es zusteht ---
    ("nettoposition", PASSIVA, 1, r"^Nettoposition$"),
    # Die Rücklage, aus der ein geplanter Fehlbetrag ausgeglichen werden kann,
    # ist NICHT der Hauptposten „Rücklagen" insgesamt. Maßgeblich ist die
    # Unterzeile 1.2.1; zweckgebundene Rücklagen und Rücklagen aus
    # Investitionszuwendungen stehen nicht frei für den Haushaltsausgleich.
    ("ruecklagen_gesamt", PASSIVA, 2, r"^R[üu]cklagen$"),
    ("ueberschussruecklage_ordentlich", PASSIVA, 3,
     r"^R[üu]cklagen aus [Üü]bersch[üu]ssen des ordentlichen Ergebnisses$"),
    # Das Jahresergebnis steht am Bilanzstichtag noch neben der Rücklage und
    # wird erst danach zugeführt. Für den verfügbaren Stand „unter
    # Berücksichtigung des Ergebnisses" gehören beide deshalb zusammen.
    ("jahresergebnis_bilanz", PASSIVA, 2, r"^Jahresergebnis$"),
    ("sonderposten", PASSIVA, 2, r"^Sonderposten$"),
    ("schulden", PASSIVA, 1, r"^Schulden$"),
    ("geldschulden", PASSIVA, 2, r"^Geldschulden$"),
    ("rueckstellungen", PASSIVA, 1, r"^R[üu]ckstellungen$"),
    # Die drei Zeilen aus dem Kopf dieser Datei. Reihenfolge egal — die
    # `$`-Anker schließen sich gegenseitig aus.
    ("pensionen_gesamt", PASSIVA, 2,
     r"^Pensionsr[üu]ckst(?:ellungen)?\.?\s+und\s+[äa]hnliche\s+Verpflichtungen$"),
    ("pensionsrueckstellungen", PASSIVA, 3, r"^Pensionsr[üu]ckstellungen$"),
    ("beihilferueckstellungen", PASSIVA, 3, r"^Beihilfer[üu]ckstellungen$"),
    # Die Gegenzahl zum Bürgschaftsbestand (`council/buergschaften.py`): Was
    # die Stadt an Ausfall tatsächlich erwartet — 2024 rund 1,3 Mio. € gegen
    # 220,3 Mio. € verbürgtes Volumen, also 0,6 %. Ohne diese Zeile stünde der
    # Bestand ohne seine Einordnung da, und 220 Millionen lesen sich dann wie
    # eine drohende Zahlung. Ebene 3: ein Unterposten der Rückstellungen, kein
    # Hauptposten — die Bilanzsumme rührt sie nicht an.
    ("buergschaftsrueckstellung", PASSIVA, 3,
     r"^R[üu]ckstellungen f[üu]r drohende Verpflichtungen aus B[üu]rgschaften"),
    ("passive_rap", PASSIVA, 1, r"^Passive\s+Rechnungsabgrenzung$"),
)

#: Die Hauptposten je Seite — ihre Summe ist die Bilanzsumme.
HAUPTPOSTEN: dict[str, tuple[str, ...]] = {
    seite: tuple(r for r, s, e, _ in ROLLEN if s == seite and e == 1)
    for seite in (AKTIVA, PASSIVA)
}

#: Ohne diese Zeilen ist ein Jahrgang wertlos: Fehlt einer der neun
#: Hauptposten, lässt sich die Bilanz nicht ausgleichen, und dann ist nicht
#: nachweisbar, dass die richtige Tabelle gelesen wurde.
PFLICHT_ROLLEN: tuple[str, ...] = HAUPTPOSTEN[AKTIVA] + HAUPTPOSTEN[PASSIVA]

#: Rundungstoleranz in Euro. Die Bilanz rechnet auf den Cent; ein Euro Luft
#: deckt die Cent-Rundung und sonst nichts. Dieselbe Größe wie in
#: ``finanzberichte._TOLERANZ``.
TOLERANZ = 1.0

#: Die Gliederungsprobe, die den Rückstellungs-Widerspruch auflöst:
#: 3.1.1 + 3.1.2 = 3.1. Sie ist Kür, keine Pflicht — ein Jahrgang, der die
#: Aufschlüsselung nicht druckt, verliert nur sie, nicht seine Bilanz.
PROBE_GLIEDERUNG = ("pensionsrueckstellungen", "beihilferueckstellungen",
                    "pensionen_gesamt")

_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")

#: Beginn einer Bilanzzeile: eine Gliederungsnummer, römisch (bis 2020) oder
#: arabisch (ab 2021), ein- bis vierstufig („2.1.4.1").
#:
#: **Kein Zeilenanker** — der Grund steht im Kopf dieser Datei: Ab 2020 fängt
#: die rechte Tabellenspalte mitten in der Zeile an. Stattdessen zwei
#: Bedingungen, die zusammen genauso scharf sind:
#:
#: * ``(?<!\S)`` — davor steht Leerraum (oder der Textanfang), die Nummer
#:   klebt also nicht im Wortinneren („i.V.m.", „Vermögensgeg.").
#: * ``(?=[A-Za-z…])`` — dahinter beginnt ein **Buchstabe**. Das ist die
#:   Trennlinie zu den Beträgen: „1.156.033.798,05" sieht aus wie eine
#:   vierstufige Gliederungsnummer, hinter ihr steht aber nie ein Wort.
#:
#: Dass die Zifferngruppen auf ``\d{1,2}`` begrenzt sind, ist die zweite
#: Sperre gegen Beträge: Tausendergruppen haben immer genau drei Ziffern.
_POSITION = re.compile(
    r"(?<!\S)((?:[IVX]{1,4}|\d{1,2})(?:\.\d{1,2})*)\.?[ \t]+(?=[A-Za-zÄÖÜäöü])")

#: Seitenfuß mitten in der Tabelle („JA 17"). Steht auf eigener Zeile.
_SEITENFUSS = re.compile(r"^[ \t]*JA\s*\d{1,3}[ \t]*$", re.M)

#: Der Spaltenkopf, der sich auf jeder Seite wiederholt. Im Blocksatz steht er
#: einzeln („Aktiva 2018 2019"), im verschränkten Layout tragen ihn beide
#: Seiten gemeinsam auf einer Zeile („Aktiva 2019 2020 Passiva 2019 2020"),
#: gefolgt von zwei oder vier „- Euro -".
_SPALTENKOPF = re.compile(
    r"^[ \t]*(?:(?:Aktiva|Passiva|Bilanzsumme)[ \t]+\d{4}[ \t]+\d{4}[ \t]*)+$"
    r"|^[ \t]*(?:-\s*Euro\s*-[ \t]*)+$", re.M)

#: Eine Fußnotenmarke mitten in der Zeile („1)", „3)"). Sie steht zwischen
#: Label und Beträgen und manchmal auf einer eigenen Folgezeile.
_FUSSNOTE = re.compile(r"(?<!\d[.,]\d)\b\d\)")

#: Ein eingeklammerter Betrag — die nachrichtliche Vorbelastung aus
#: Haushaltsresten, die unter dem Jahresergebnis steht („(6.003.088,68)").
#: Sie gehört zu keiner Bilanzposition und würde sonst als dritter und
#: vierter Betrag der Zeile davor gelesen.
_KLAMMERBETRAG = re.compile(r"\(\s*-?\d{1,3}(?:\.\d{3})*,\d{2}\s*\)")

#: Überschrift des Abschnitts. „2.1 Bilanz [der] Stadt Oldenburg zum
#: 31.12.JJJJ" — mit „der" im Inhaltsverzeichnis, ohne es über der Tabelle.
_UEBERSCHRIFT = re.compile(r"Bilanz\s+(?:der\s+)?Stadt\s+Oldenburg\s+zum\s+31\.12\.(\d{4})")

#: Die gedruckte Bilanzsumme, wo der Jahrgang sie führt (2017–2020). Sie steht
#: unter einer eigenen Kopfzeile, die Beträge auf der Folgezeile — und das
#: Ganze zweimal hintereinander, einmal je Spaltenblock.
_BILANZSUMME = re.compile(
    r"Bilanzsumme\s+\d{4}\s+\d{4}\s*\n\s*(?:-\s*Euro\s*-\s*)+\n\s*"
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2})\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})")


def _eur(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _rolle(bezeichnung: str) -> tuple[str, str, int] | None:
    """Welche Bilanzposition diese Zeile ist — oder ``None``."""
    for name, seite, ebene, muster in ROLLEN:
        if re.search(muster, bezeichnung):
            return name, seite, ebene
    return None


def _abschnitt(text: str, year: int) -> str:
    """Der Bilanz-Abschnitt der **Kernverwaltung** aus dem Volltext.

    Zwei Fallen stecken in der Auswahl der Fundstelle:

    1. Der erste Treffer ist das **Inhaltsverzeichnis** („2.1 Bilanz der Stadt
       Oldenburg zum 31.12.2024 JA 17").
    2. Weiter hinten stehen die Bilanzen der **neun nicht rechtsfähigen
       Stiftungen** (Abschnitt 7). Sie haben dieselbe Gliederung, dieselben
       Zeilennamen und gehen genauso auf — nur sind es Bilanzsummen um
       300.000 € statt um 1,5 Mrd. €. Ein Parser, der die erwischt, merkt es
       an keiner einzigen Probe.

    Beides erledigt dieselbe Regel: Genommen wird die Fundstelle mit den
    meisten Beträgen dahinter. Die Stiftungsbilanzen sind fast leer (die
    meisten Positionen führen sie gar nicht), die der Kernverwaltung ist
    dicht — dazwischen liegt ein Faktor von über zehn.
    """
    stellen = [m.start() for m in _UEBERSCHRIFT.finditer(text)]
    if not stellen:
        # Ältere Jahrgänge über den Spaltenkopf: „Aktiva 2016 2017".
        stellen = [m.start() for m in
                   re.finditer(rf"^[ \t]*Aktiva[ \t]+{year - 1}[ \t]+{year}[ \t]*$",
                               text, re.M)]
    if not stellen:
        return ""
    start = max(stellen, key=lambda i: len(_BETRAG.findall(text[i:i + 12000])))
    # Die Bilanz endet vor der Ergebnisrechnung. Wo deren Überschrift fehlt,
    # begrenzt ein großzügiges Fenster — der Parser nimmt ohnehin nur Zeilen,
    # die er benennen kann.
    rest = text[start:start + 14000]
    ende = re.search(r"^[ \t]*3\.?1?\s*Ergebnisrechnung", rest, re.M)
    return rest[:ende.start()] if ende else rest


def _saeubern(block: str) -> str:
    """Seitenfüße, Spaltenköpfe und Klammerbeträge aus dem Block nehmen."""
    block = _SEITENFUSS.sub("", block)
    block = _SPALTENKOPF.sub("", block)
    block = _KLAMMERBETRAG.sub("", block)
    return block


def _label(roh: str) -> str:
    """Der Zeilenname, wie das Dokument ihn schreibt — aus dem Textstück vor
    dem ersten Betrag.

    Drei Dinge sind zu glätten, und alle drei kommen aus dem PDF-Extrakt:
    Der Name läuft über bis zu drei Zeilen („Geleistete\\nInvestitions-
    zuweisungen und -\\nzuschüsse"), er wird dabei mit Trennstrich getrennt,
    und zwischen Name und Betrag steht manchmal eine Fußnotenmarke. Dieselbe
    Glättung wie ``finanzberichte._kopf_normalisieren``."""
    ohne_trennung = re.sub(r"-\s*\n\s*", "", roh)
    ohne_fussnote = _FUSSNOTE.sub(" ", ohne_trennung)
    return " ".join(ohne_fussnote.split()).strip(" .:;")


def parse_bilanz(text: str, year: int) -> dict:
    """Die Bilanz eines Jahresabschlusses lesen.

    Liefert ``{year, prior_year, posten}``. ``posten`` ist eine Liste aus
    ``{rolle, seite, ebene, nr, bezeichnung, wert, value_prior_year}`` — ``wert``
    ist der Stand zum Bilanzstichtag des Jahrgangs, ``value_prior_year`` der
    Stand ein Jahr davor, den dieselbe Tabelle in ihrer ersten Spalte führt.

    ``gedruckte_summe`` steht dabei, wo der Jahrgang die Bilanzsumme unter
    die Tabelle druckt (2017–2020) — sonst ``None``. Das ist kein Mangel:
    Die Bilanz ist über den Ausgleich beider Seiten auch ohne sie belegt.

    Geprüft wird hier **nichts** — das tut :func:`bilanzprobe`.
    """
    roh = _abschnitt(text, year)
    if not roh:
        return {"year": year, "prior_year": year - 1, "posten": [],
                "gedruckte_summe": None}

    # Die gedruckte Bilanzsumme **zuerst** lesen und die Tabelle dann dort
    # abschneiden. Sie steht ohne eigene Gliederungsnummer unter der letzten
    # Zeile — bliebe sie stehen, hingen ihre beiden Beträge am Posten
    # „Passive Rechnungsabgrenzung", der damit vier statt zwei Spalten hätte
    # und über die Zwei-Spalten-Regel unten herausfiele. Genau so ist in der
    # ersten Fassung dieses Parsers in allen vier Blocksatz-Jahrgängen der
    # letzte Passivposten verschwunden — und mit ihm der Bilanzausgleich.
    gedruckt = _BILANZSUMME.search(roh)
    schnitt = re.search(r"^[ \t]*Bilanzsumme\b", roh, re.M)
    block = _saeubern(roh[:schnitt.start()] if schnitt else roh)

    treffer = list(_POSITION.finditer(block))
    gesehen: set[str] = set()
    posten: list[dict] = []
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(block)
        satz = block[m.end():ende]
        betraege = _BETRAG.findall(satz)
        bezeichnung = _label(satz[:satz.find(betraege[0])] if betraege else satz)
        rolle = _rolle(bezeichnung)
        if rolle is None:
            continue
        name, seite, ebene = rolle
        # Eine Bilanzzeile führt genau zwei Spalten: Vorjahr und Stichtag.
        # Alles andere ist ein Lesefehler — meist eine verschluckte
        # Zeilengrenze, hinter der die Beträge der nächsten Zeile mithängen.
        # Eine leere Position (die Bilanz führt viele) hat gar keinen Betrag
        # und wird als 0 geführt: Sie steht in der Tabelle, sie ist nur nicht
        # belegt.
        if len(betraege) not in (0, 2):
            continue
        # Derselbe Name zweimal: Der Block reicht in den nächsten Abschnitt
        # oder eine Zeile wurde doppelt erfasst. Der erste Treffer gilt.
        if name in gesehen:
            continue
        gesehen.add(name)
        posten.append({
            "rolle": name, "seite": seite, "ebene": ebene,
            "nr": m.group(1).rstrip("."), "bezeichnung": bezeichnung,
            "value_prior_year": _eur(betraege[0]) if betraege else 0.0,
            "wert": _eur(betraege[1]) if betraege else 0.0,
        })

    return {"year": year, "prior_year": year - 1, "posten": posten,
            "gedruckte_summe": (_eur(gedruckt.group(1)), _eur(gedruckt.group(2)))
            if gedruckt else None}


# --- Die Proben --------------------------------------------------------------

def _wert(posten: list[dict], rolle: str, spalte: str = "wert") -> float | None:
    for p in posten:
        if p["rolle"] == rolle:
            return p[spalte]
    return None


def summe(posten: list[dict], seite: str, spalte: str = "wert") -> float | None:
    """Die Summe der Hauptposten einer Seite — oder ``None``, wenn einer fehlt."""
    werte = [_wert(posten, r, spalte) for r in HAUPTPOSTEN[seite]]
    return sum(werte) if all(w is not None for w in werte) else None


def bilanzprobe(gelesen: dict) -> tuple[dict | None, list[str], list[str]]:
    """Trägt dieser Jahrgang? Liefert ``(jahrgang, fehler, hinweise)``.

    Die **Pflichtprobe** ist der Bilanzausgleich: Aktiva = Passiva, auf den
    Cent. Sie ist die Eintrittskarte, und sie ist streng — eine Bilanz, die
    nicht ausgeglichen ist, ist keine Bilanz, sondern ein Lesefehler. Reißt
    sie, wird der Jahrgang ganz verworfen.

    Zwei **Kür-Proben** kosten, wenn sie reißen, nur sich selbst:

    * die gedruckte Bilanzsumme als dritte Bestätigung (nur 2017–2020),
    * die Gliederung der Rückstellungen (3.1.1 + 3.1.2 = 3.1).

    Die beiden Proben über Dokumentgrenzen hinweg — die Vorjahreskette und
    der Abgleich mit der Finanzrechnung — stehen nicht hier: Sie brauchen
    mehr als einen Jahrgang und laufen in :func:`vorjahreskette` bzw.
    :func:`kassenprobe`.
    """
    posten, fehler, hinweise = gelesen["posten"], [], []
    if not posten:
        return None, ["kein Bilanz-Abschnitt gefunden"], []

    fehlend = [r for r in PFLICHT_ROLLEN if _wert(posten, r) is None]
    if fehlend:
        return None, [f"Hauptposten fehlen: {', '.join(fehlend)}"], []

    aktiva, passiva = summe(posten, AKTIVA), summe(posten, PASSIVA)
    difference = abs(aktiva - passiva)
    if difference > TOLERANZ:
        return None, [f"Bilanz gleicht nicht aus: Aktiva {aktiva:,.2f} € gegen "
                      f"Passiva {passiva:,.2f} €, Differenz {difference:,.2f} €"], []

    jahrgang = {"year": gelesen["year"], "posten": posten,
                "bilanzsumme": aktiva, "proben": ["bilanz_ausgleich"],
                "balancing_difference": difference}

    gedruckt = gelesen.get("gedruckte_summe")
    if gedruckt is not None:
        if abs(gedruckt[1] - aktiva) <= TOLERANZ:
            jahrgang["proben"].append("bilanzsumme_gedruckt")
            jahrgang["gedruckte_summe"] = gedruckt[1]
        else:
            hinweise.append(
                f"gedruckte Bilanzsumme {gedruckt[1]:,.2f} € weicht von der "
                f"gerechneten {aktiva:,.2f} € ab — nicht als Probe gezählt")

    pension, beihilfe, gesamt = (_wert(posten, r) for r in PROBE_GLIEDERUNG)
    if None not in (pension, beihilfe, gesamt):
        if abs(pension + beihilfe - gesamt) <= TOLERANZ:
            jahrgang["proben"].append("rueckstellungs_gliederung")
        else:
            hinweise.append(
                f"Rückstellungs-Gliederung geht nicht auf: {pension:,.2f} + "
                f"{beihilfe:,.2f} ≠ {gesamt:,.2f} €")
    return jahrgang, fehler, hinweise


def vorjahreskette(jahrgaenge: dict[int, dict]) -> list[tuple[int, int, str]]:
    """Steht der Stand eines Jahres im Abschluss des Folgejahres noch einmal?

    Jede Bilanz führt zwei Spalten: den Stichtag und den davor. Der
    Vorjahreswert im Abschluss 2024 muss also der Stichtagswert des
    Abschlusses 2023 sein — zwei getrennt gelesene Dokumente, dieselbe Zahl,
    und das für jeden Hauptposten.

    Liefert die **gerissenen** Glieder als ``(year, folgejahr, warum)``.
    """
    risse: list[tuple[int, int, str]] = []
    for year in sorted(jahrgaenge):
        folge = year + 1
        if folge not in jahrgaenge:
            continue
        for rolle in PFLICHT_ROLLEN:
            hier = _wert(jahrgaenge[year]["posten"], rolle)
            dort = _wert(jahrgaenge[folge]["posten"], rolle, "value_prior_year")
            if hier is None or dort is None:
                continue
            if abs(hier - dort) > TOLERANZ:
                risse.append((year, folge,
                              f"{rolle}: {hier:,.2f} € im Abschluss {year}, "
                              f"{dort:,.2f} € als Vorjahr im Abschluss {folge}"))
                break
    return risse


def _abschnitt_62(text: str) -> str:
    """Der Anhang-Abschnitt 6.2 im **Fließtext** — nicht im Inhaltsverzeichnis.

    Die naheliegende Regel „nimm die Fundstelle mit den meisten 6.2.x
    dahinter" führt hier genau falsch herum: Im Inhaltsverzeichnis stehen alle
    zehn Überschriften **dichter** beieinander als irgendwo sonst, weil kein
    Text dazwischen steht. Sechs von acht Jahrgängen landeten so im
    Verzeichnis und lieferten neun leere Erläuterungen.

    Der Unterschied, auf den es ankommt, ist deshalb nicht die Dichte, sondern
    die **Spannweite**: Im Verzeichnis liegen 6.2.1 und 6.2.9 rund 250 Zeichen
    auseinander, im Fließtext rund 14.000.
    """
    erste = [m.start() for m in re.finditer(r"6\.2\.1\s+Immaterielles", text)]
    weit: tuple[int, int] | None = None
    for s in erste:
        m = re.search(r"6\.2\.9\s+Passive", text[s:])
        if m and (weit is None or m.start() > weit[1]):
            weit = (s, m.start())
    if weit is None:
        return ""
    # Bis zum Ende von 6.2.9 — 6.2.10 (Eventualverbindlichkeiten) gehört zu
    # keiner Bilanzposition und bleibt draußen.
    ende = re.search(r"6\.2\.10\s+Eventual|^\s*6\.3\s", text[weit[0]:], re.M)
    return text[weit[0]:weit[0] + (ende.start() if ende else weit[1] + 4000)]


def parse_erlaeuterungen(text: str, year: int) -> list[dict]:
    """Was die Verwaltung zu jedem Hauptposten schreibt — Anhang 6.2.

    Der Anhang erläutert die Bilanz Position für Position: 6.2.1
    Immaterielles Vermögen, 6.2.2 Sachvermögen, … 6.2.9 Passive
    Rechnungsabgrenzung. Das sind **genau** die neun Hauptposten aus
    :data:`PFLICHT_ROLLEN`, in genau deren Reihenfolge — erst die Aktivseite
    von oben nach unten, dann die Passivseite.

    Warum das mehr ist als Beiwerk: Die Bilanz 2024 weist Schulden von
    207,1 Mio. € aus, nach 84,4 Mio. € im Vorjahr. Ohne 6.2.7 sähe das nach
    einer Verdreifachung der Schulden aus. Der Abschnitt sagt, dass es keine
    ist — die Stadt muss dieselben Cash-Pooling-Mittel seit 2024 auf beiden
    Bilanzseiten ausweisen, und die 138,2 Mio. € haben einen Gegenposten im
    Finanzvermögen. **Diese Zahl darf ohne diesen Text nicht angezeigt
    werden.**

    Liefert je Abschnitt ``{rolle, nr, ueberschrift, text}``. Zwei Abschnitte
    (6.2.2 Sachvermögen, 6.2.3 Finanzvermögen) betten Tabellen in ihren Text
    ein; als Fließtext gelesen sind das Zahlenkolonnen ohne Spalten. Sie
    werden gespeichert, aber nichts zwingt eine Seite, sie anzuzeigen.
    """
    block = _abschnitt_62(text)
    if not block:
        return []

    kopf = list(re.finditer(r"6\.2\.(\d{1,2})\s+([A-ZÄÖÜ][^\n]{0,55})", block))
    raus: list[dict] = []
    for i, m in enumerate(kopf):
        nr = int(m.group(1))
        if not 1 <= nr <= len(PFLICHT_ROLLEN):
            continue
        ende = kopf[i + 1].start() if i + 1 < len(kopf) else len(block)
        roh = block[m.end():ende]
        # Seitenfüße stehen mitten im Fließtext und zerreißen sonst Sätze.
        roh = _SEITENFUSS.sub("", roh)
        # Silbentrennung am Zeilenende zusammenziehen, dann Absätze erhalten,
        # aber Umbrüche innerhalb eines Absatzes glätten.
        roh = re.sub(r"-\s*\n\s*", "", roh)
        absaetze = [" ".join(a.split()) for a in re.split(r"\n\s*\n", roh)]
        inhalt = "\n\n".join(a for a in absaetze if a)
        raus.append({"rolle": PFLICHT_ROLLEN[nr - 1], "nr": nr,
                     "ueberschrift": " ".join(m.group(2).split()),
                     "text": inhalt})
    return raus


def erlaeuterungsprobe(erlaeuterungen: list[dict]) -> tuple[bool, str]:
    """Trägt Abschnitt 6.2.x wirklich die Erläuterung zu Hauptposten x?

    Ein Text ist keine Zahl — es gibt nichts nachzurechnen. Was sich prüfen
    lässt, ist die **Zuordnung**, und die ist hier auch das einzige Risiko:
    Ein Erläuterungstext unter der falschen Bilanzposition wäre eine
    Falschaussage, die keine Rechenprobe je bemerkte.

    Geprüft wird deshalb, dass die Überschrift von 6.2.N auf das
    :data:`ROLLEN`-Muster des N-ten Hauptpostens passt — mit demselben
    Muster, mit dem der Bilanzparser oben seine Zeile erkennt. Verschiebt
    die Stadt einen Abschnitt oder benennt sie einen um, fällt das hier auf
    und nicht erst auf der Seite.
    """
    if len(erlaeuterungen) != len(PFLICHT_ROLLEN):
        return False, (f"{len(erlaeuterungen)} Abschnitte statt "
                       f"{len(PFLICHT_ROLLEN)}")
    muster = {r: m for r, _, _, m in ROLLEN}
    for e in erlaeuterungen:
        erwartet = PFLICHT_ROLLEN[e["nr"] - 1]
        if not re.search(muster[erwartet], e["ueberschrift"]):
            return False, (f"6.2.{e['nr']} heißt {e['ueberschrift']!r}, "
                           f"erwartet war die Erläuterung zu {erwartet}")
        if not e["text"].strip():
            return False, f"6.2.{e['nr']} ({erwartet}) hat keinen Text"
    return True, f"{len(erlaeuterungen)} Abschnitte in Bilanzreihenfolge"


def kassenprobe(jahrgaenge: dict[int, dict],
                endbestaende: dict[int, float]) -> list[tuple[int, str]]:
    """Die stärkste Probe des Bereichs: Bilanz gegen Finanzrechnung.

    Die Bilanzposition „Liquide Mittel" und der Posten „Endbestand an
    Zahlungsmitteln" der Finanzrechnung sind dieselbe Zahl — das Dokument
    sagt es selbst, indem es die Finanzrechnungs-Zeile „Endbestand an
    Zahlungsmitteln (Liquide Mittel am Ende d. Jahres)" nennt.

    Was sie so stark macht: Beide Tabellen stehen zwar im selben Heft, aber
    zehn Seiten auseinander, in verschiedenen Layouts, und werden von zwei
    getrennten Parsern gelesen (``council/finanzberichte.py`` und dieser).
    Wenn beide dieselbe Zahl herausbekommen, hat sich keiner von beiden
    verlesen.

    Liefert die **gerissenen** Jahrgänge als ``(year, warum)``. Jahrgänge
    ohne eingelesene Finanzrechnung fallen still weg — fehlende Gegenprobe
    ist kein Fehler.
    """
    risse: list[tuple[int, str]] = []
    for year in sorted(jahrgaenge):
        kasse = endbestaende.get(year)
        bilanz = _wert(jahrgaenge[year]["posten"], "liquide_mittel")
        if kasse is None or bilanz is None:
            continue
        if abs(kasse - bilanz) > TOLERANZ:
            risse.append((year, f"Liquide Mittel {bilanz:,.2f} € gegen "
                                f"Endbestand der Finanzrechnung {kasse:,.2f} €"))
    return risse
