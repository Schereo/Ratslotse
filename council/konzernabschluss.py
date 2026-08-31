"""Der Konzern Stadt Oldenburg — aus dem konsolidierten Gesamtabschluss.

Der Haushalts-Bereich zeigt bis hierher die **Kernverwaltung**: den Haushalt,
den der Rat beschließt, und den Jahresabschluss, der ihn abrechnet. Das ist
nicht die ganze Stadt. Klinikum, Verkehr und Wasser, Abfallwirtschaftsbetrieb,
Bäderbetrieb, Weser-Ems Halle und der Eigenbetrieb Gebäudewirtschaft haben
eigene Bücher; im Kernhaushalt stehen sie bestenfalls als Zuschusszeile.

Einmal im Jahr rechnet die Stadt beides zusammen — den **konsolidierten
Gesamtabschluss** nach § 128 NKomVG. Das Rechnungsprüfungsamt prüft ihn und
legt seinen Bericht dem Rat als Anlage vor. Dieses eine Dokument ist der
einzige Ort im Bestand, an dem Kernverwaltung, Eigenbetriebe und Beteiligungen
in *einer* Rechnung stehen.

Zwei Tabellen daraus sind maschinenlesbar, und beide dokumentieren ihre
eigenen Rechenproben:

**3.2 Gesamtergebnisrechnung** — die Ergebnisrechnung des Konzerns, Posten für
Posten, mit Vorjahresspalte. Drei Proben stehen in der Tabelle selbst:

    Summe ordentliche Erträge − Summe ordentliche Aufwendungen = ordentliches Ergebnis
    außerordentliche Erträge  − außerordentliche Aufwendungen  = außerordentliches Ergebnis
    ordentliches Ergebnis     + außerordentliches Ergebnis     = Gesamtjahresergebnis

**4.1.1 Trägeraufstellung** — dieselben Summen noch einmal, aber aufgeteilt auf
die einbezogenen Aufgabenträger, mit Konsolidierungszeile. Auch hier zwei
Proben: je Zeile ``Jahr − Vorjahr = Veränderung``, und über die Spalte
``Summe der Träger + Konsolidierung = Gesamtsumme``.

Was eine Probe reißt, kommt nicht in die Datenbank. Das ist keine Zierde: Der
Volltext dieser PDFs ist stellenweise zerschossen — in den Jahrgängen bis 2016
stehen Leerzeichen mitten in Beträgen (``105.667.339, 23``), und 2017 ist die
Veränderungsspalte der Aufwendungssumme schlicht falsch extrahiert
(``- 1.665.521`` statt ``+ 49.357``). Ohne Probe wäre nicht zu unterscheiden,
was davon Zahl und was Artefakt ist.

Drei Eigenheiten, an denen ein naiver Parser scheitert:

**Die Postennummern wechseln.** Bis 2018 ist Posten 15 die Summe der
ordentlichen Erträge, ab 2019 ist es Posten 13. Wer weiter 15 liest, bekommt
ab 2019 „Versorgungsaufwendungen" — 8,4 Mio. statt 1,14 Mrd., und keine Zeile
im Log. Erkannt wird deshalb an der **Beschriftung**, gespeichert wird die
Rolle (:data:`ROLLEN`), nicht die Nummer.

**Die Vorjahresspalte ist nicht immer in Euro.** 2014–2016 führt der
Tabellenkopf ``EUR EUR TEUR``: Die Vorjahreszahlen stehen in Tausend. Wer das
übersieht, liest einen Konzern, der über Nacht auf ein Tausendstel schrumpft.
Die Einheit kommt deshalb aus dem Kopf, nicht aus einer Annahme.

**2019 hat keine Zeilenumbrüche.** Der Extrakt dieses einen Jahrgangs setzt die
ganze Tabelle in eine Zeile, und die nächste Postennummer klebt am
Vorjahreswert: ``269.835.099,832. Zuwendungen``. Auflösbar ist das, weil
deutsche Beträge immer genau zwei Nachkommastellen haben — mehr macht
:func:`entzerren` nicht, und die drei Proben entscheiden anschließend wie bei
jedem anderen Jahrgang.

Nicht gelesen wird die Liste der einbezogenen Gesellschaften: In den jüngeren
Jahrgängen ist der Konsolidierungskreis eine **Grafik ohne Textebene** („Aus
der nachfolgenden Grafik ist ersichtlich, welche Aufgabenträger …") — dieselbe
Sackgasse wie bei der Schuldenübersicht. Wer dazugehört, sagt stattdessen die
Trägeraufstellung, und die trägt Zahlen.
"""
from __future__ import annotations

import re

# --- Erkennung --------------------------------------------------------------
#
# Die Labels der Anlagen taugen für diese Reihe nicht: Der Gesamtabschluss 2016
# heißt schlicht „Anlage", 2013 ebenso, und „Schlussbericht" trägt ein anderes
# Dokument. Verlässlich trennt allein der Textanfang — der Bericht nennt sich
# auf Seite 1 selbst beim Namen, und zwar in allen zwölf Jahrgängen gleich.

#: SQL-LIKE-Vorfilter auf ``raw_text``. Bewusst kürzer als die Titelzeile: Im
#: Rohtext ist der Titel umbrochen, ein LIKE auf den ganzen Satz fände nichts.
TEXT_MUSTER = "%konsolidierten Gesamtabschlusses%"

_TITEL = re.compile(
    r"Prüfung des konsolidierten Gesamtabschlusses zum 31\.12\.(20\d\d)")


def _flach(text: str) -> str:
    """Zeilenumbrüche und Mehrfach-Leerraum zu je einem Leerzeichen."""
    return re.sub(r"\s+", " ", text or "")


def budget_year(kopf: str | None) -> int | None:
    """Welchen Jahrgang ein Kandidat abdeckt — ``None``, wenn es keiner ist.

    Der Titel steht im Rohtext über mehrere Zeilen verteilt und trägt in den
    jüngeren Jahrgängen ein Aktenzeichen-Deckblatt davor; gesucht wird deshalb
    im geglätteten Text. Für Dokumente, die den Titel nicht führen (Schluss-
    berichte, Teilhaushalts-Pläne — beide fallen in denselben Vorfilter), gibt
    es kein Ergebnis, und das ist die ganze Trennschärfe, die es braucht."""
    m = _TITEL.search(_flach(kopf or "")[:3000])
    return int(m.group(1)) if m else None


# --- Beträge ----------------------------------------------------------------

#: Ein Euro-Betrag mit zwei Nachkommastellen. Das Minuszeichen darf ein
#: Leerzeichen hinter sich haben — der Extrakt setzt „- 510.903,43".
_EUR = r"-\s?\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}(?:\.\d{3})*,\d{2}"
#: Ein Tausend-Euro-Betrag: ohne Nachkommastellen, Vorzeichen auch als „+".
_TEUR = r"[-+]\s?\d{1,3}(?:\.\d{3})*|\d{1,3}(?:\.\d{3})*"

#: Rundungstoleranz der Cent-Proben in Euro. Die Gesamtergebnisrechnung geht
#: auf den Cent auf; ein Cent Spielraum fängt nur Gleitkomma-Rauschen.
TOLERANZ_EUR = 0.011
#: Rundungstoleranz der TEUR-Proben. Die Trägeraufstellung rundet jede Zeile
#: einzeln auf Tausend, die Summenzeile ist die Summe der *ungerundeten* Werte
#: — bei neun Zeilen sind zwei Tausend Abweichung Rundung, nicht Fehler.
TOLERANZ_TEUR = 2.0


def _zahl(s: str, dezimal: bool = True) -> float | None:
    """„- 510.903,43" → -510903.43. ``None``, wenn es kein Betrag ist."""
    s = s.replace(" ", "").replace(" ", "")
    vorzeichen = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-")
    if dezimal:
        if not re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d{2}", s):
            return None
        return vorzeichen * float(s.replace(".", "").replace(",", "."))
    if not re.fullmatch(r"\d{1,3}(?:\.\d{3})*", s):
        return None
    return vorzeichen * float(s.replace(".", ""))


def entzerren(text: str) -> str:
    """Fehlende Zeilenumbrüche der Postentabelle wiederherstellen.

    Betrifft genau einen Jahrgang (2019): Dessen PDF-Extrakt setzt die ganze
    Gesamtergebnisrechnung in eine einzige Zeile, sodass die nächste
    Postennummer am Vorjahreswert klebt::

        1. Steuern und ähnliche Abgaben 274.850.289,05 269.835.099,832. Zuwen…

    Eindeutig auflösbar, weil ein deutscher Betrag immer genau zwei
    Nachkommastellen hat: Was hinter ``,83`` steht, kann keine dritte
    Nachkommastelle sein. Verlangt wird zusätzlich das Leerzeichen hinter dem
    Punkt der Postennummer, damit „1.234" nicht als Posten 1 zerfällt.

    Auf sauber umbrochenen Jahrgängen ändert die Funktion nichts — dort folgt
    auf einen Betrag ein Leerzeichen oder ein Zeilenende, nie eine Ziffer."""
    return re.sub(r"(,\d\d)(\d{1,2}\.\s)", r"\1\n\2", text or "")


# --- Gesamtergebnisrechnung (3.2) -------------------------------------------

#: Die Rollen, auf die es ankommt — erkannt an der Beschriftung, weil die
#: Postennummer zwischen 2018 und 2019 springt (15/25/26 → 13/21/22).
#: Reihenfolge ist Absicht: „außerordentliche Erträge" muss vor der
#: Ertragssumme geprüft werden, sonst fängt die Summe es ein.
ROLLEN: tuple[tuple[str, str], ...] = (
    ("extraordinary_revenues", r"^außerordentliche\s+erträge"),
    ("extraordinary_expenses", r"^außerordentliche\s+aufwendungen"),
    # 2019 schreibt „Außerordentlichen Ergebnis" — Tippfehler der Quelle, der
    # sich über vier Jahrgänge hält. Die Endung bleibt deshalb offen.
    ("extraordinary_result", r"^außerordentliche[nrs]?\s+(gesamt)?ergebnis"),
    ("total_result", r"^gesamtjahres(ergebnis|überschuss|fehlbetrag)"),
    ("revenues_total", r"^(ordentliche\s+gesamterträge|summe\s+ordentliche\s+erträge)"),
    ("expenses_total",
     r"^(ordentliche\s+gesamtaufwendungen|summe\s+ordentliche\s+aufwendungen)"),
    ("ordinary_result", r"^ordentliche[ns]?\s+(gesamt)?ergebnis"),
    ("interest_expenses",
     r"^zinsen und (ähnliche|sonstige) (aufwendungen|finanzaufwendungen)"),
    ("personnel_expenses",
     r"^(personalaufwendungen|aufwendungen für aktives personal)"),
    ("taxes", r"^taxes und ähnliche abgaben"),
)

#: Rollen, die Summen oder Salden sind — keine eigenständige Ertrags- oder
#: Aufwandsart. Eine Torte aus allen Posten wäre sonst doppelt gezählt.
SUMMEN_ROLLEN = frozenset({
    "revenues_total", "expenses_total", "ordinary_result",
    "extraordinary_result", "total_result"})

_ANKER = re.compile(r"1\.\s*Steuern und ähnliche Abgaben")
#: Eine Postenzeile: Nummer, Punkt, Beschriftung ab einem Buchstaben. Das
#: Buchstaben-Verlangen hält Unterposten draußen — „8.1. Gewinnanteile" wäre
#: sonst Posten 8 mit der Beschriftung „1. Gewinnanteile".
_POSTEN = re.compile(r"^(\d{1,2})\.\s+(?=[A-Za-zÄÖÜäöüß])(.*)$")
#: Ein Unterposten („19.1 Abschreibungen auf …"). Er beendet den Hauptposten:
#: Dessen Summe steht danach auf einer Zeile ganz ohne Nummer, und die einem
#: offenen Posten zuzuschlagen hieße, den ersten Unterposten für das Ganze zu
#: halten — 2014 wären das 11,2 statt 12,1 Mio. Zinsaufwand, ohne dass eine
#: Probe es merkt.
_UNTERPOSTEN = re.compile(r"^\d{1,2}\.\d")
_EINHEIT = re.compile(r"TEUR|T€|EUR|€")
#: Eine Beschriftung trägt keine Zahlenkolonne. Der Extrakt setzt in den
#: schlechteren Jahrgängen Leerzeichen mitten in Beträge („160.026.568 ,55"),
#: und dann ist der erste *saubere* Betrag der Zeile nicht mehr der Wert des
#: Haushaltsjahres, sondern der des Vorjahres. Diese Prüfung fängt das ab:
#: Steht vor dem gefundenen Betrag noch eine Ziffernfolge, ist die Zeile
#: zerschossen und fällt weg.
_ZAHL_IM_TEXT = re.compile(r"\d[\d.]{2,}")


def _vorjahr_in_tausend(kopf: str) -> bool:
    """Steht die Vorjahresspalte in Tausend Euro?

    2014–2016 führt der Kopf drei Spalten (``EUR EUR TEUR``): eine für
    Unterposten, eine für die Summe, und die Vorjahreszahlen in Tausend. Ab
    2017 sind es zwei Spalten in Euro. Entschieden wird an der **letzten**
    Einheitenangabe vor der Tabelle — sie gehört zur letzten Spalte."""
    treffer = _EINHEIT.findall(kopf[-300:])
    return bool(treffer) and treffer[-1].startswith("T")


def _rolle(label: str) -> str | None:
    klein = " ".join(label.lower().split())
    for name, muster in ROLLEN:
        if re.match(muster, klein):
            return name
    return None


def _posten_zeilen(rumpf: str, tausend: bool) -> list[dict]:
    """Die Postenzeilen eines Tabellenrumpfs, mit umbrochenen Beschriftungen.

    Der Extrakt bricht lange Beschriftungen um und lässt die Beträge auf der
    Folgezeile stehen („2. Zuwendungen und allgemeine Umlagen, außer" /
    „für Investitionstätigkeit 178.870.264,53 182.773.472,90"). Eine Zeile
    ohne Beträge ist deshalb kein Fehler, sondern ein Anfang.

    Die **Vorjahresspalte ist optional**, und das ist keine Bequemlichkeit:
    2017 steht in ihr durchgehend Bruch („808.081. 595,51"), während der Wert
    des Haushaltsjahres daneben sauber ist. Beides zu verlangen hieße, die
    Summe der ordentlichen Aufwendungen wegzuwerfen — und mit ihr die erste
    Rechenprobe und damit den ganzen Jahrgang."""
    erster = re.compile(rf"({_EUR})")
    only_prior_year = re.compile(rf"^\s*({_TEUR if tausend else _EUR})\s*$")
    offen_nr: int | None = None
    offen_text = ""
    aus: list[dict] = []
    for roh in rumpf.split("\n"):
        zeile = roh.strip()
        if not zeile:
            continue
        if _UNTERPOSTEN.match(zeile):
            offen_nr, offen_text = None, ""
            continue
        m = _POSTEN.match(zeile)
        if m:
            offen_nr, zeile = int(m.group(1)), m.group(2).strip()
            offen_text = ""
        if offen_nr is None:
            continue
        treffer = erster.search(zeile)
        if not treffer:
            # Reine Beschriftungszeile — Text merken, Beträge folgen.
            offen_text = f"{offen_text} {zeile}".strip()
            continue
        text = " ".join(f"{offen_text} {zeile[:treffer.start()]}".split())
        amount = _zahl(treffer.group(1))
        offen_text = ""
        nr, offen_nr = offen_nr, None
        if amount is None or not text or _ZAHL_IM_TEXT.search(text):
            continue
        rest = only_prior_year.match(zeile[treffer.end():])
        prior_year = _zahl(rest.group(1), dezimal=not tausend) if rest else None
        if prior_year is not None and tausend:
            prior_year *= 1000.0
        aus.append({"nr": nr, "label": text, "role": _rolle(text),
                    "amount": amount, "prior_year": prior_year})
        # Das Gesamtjahresergebnis schließt die Tabelle ab. Ohne diesen Halt
        # liest der Parser in die Anlagenübersicht weiter, die gleich darauf
        # folgt und ebenfalls mit „1." beginnt.
        if aus[-1]["role"] == "total_result":
            break
    return aus


def _probe(label: str, links: float | None, rechts: float | None) -> dict | None:
    """Eine Rechenprobe als Nachweis — ``None``, wenn sie nicht rechenbar ist."""
    if links is None or rechts is None:
        return None
    delta = round(links - rechts, 2)
    return {"probe": label, "delta": delta, "ok": abs(delta) <= TOLERANZ_EUR}


def parse_gesamtergebnisrechnung(text: str) -> dict | None:
    """Abschnitt 3.2 lesen — oder ``None``, wenn keine Tabelle da ist.

    Zurück kommt ``{"posten": [...], "probes": [...], "bestanden": bool}``.
    Die Posten sind vollständig, aber nur die drei Proben entscheiden, ob der
    Jahrgang gespeichert werden darf; das trennt der Aufrufer nicht selbst."""
    roh = entzerren(text or "")
    for m in _ANKER.finditer(roh):
        kopf, rumpf = roh[max(0, m.start() - 600):m.start()], roh[m.start():m.start() + 12000]
        posten = _posten_zeilen(rumpf, _vorjahr_in_tausend(kopf))
        nach_rolle = {p["role"]: p for p in posten if p["role"]}
        if "revenues_total" not in nach_rolle or "total_result" not in nach_rolle:
            continue  # Anlagenübersicht o. Ä. — sieht am Anfang ähnlich aus.

        def value(role: str) -> float | None:
            eintrag = nach_rolle.get(role)
            return eintrag["amount"] if eintrag else None

        ord_ergebnis = value("ordinary_result")
        ao_ergebnis = value("extraordinary_result")
        probes = [p for p in (
            _probe("Erträge − Aufwendungen = ordentliches Ergebnis",
                   (value("revenues_total") or 0) - (value("expenses_total") or 0)
                   if value("revenues_total") is not None
                   and value("expenses_total") is not None else None,
                   ord_ergebnis),
            _probe("a.o. Erträge − a.o. Aufwendungen = a.o. Ergebnis",
                   (value("extraordinary_revenues") or 0) - (value("extraordinary_expenses") or 0)
                   if value("extraordinary_revenues") is not None
                   and value("extraordinary_expenses") is not None else None,
                   ao_ergebnis),
            _probe("ordentliches + a.o. Ergebnis = Gesamtjahresergebnis",
                   (ord_ergebnis or 0) + (ao_ergebnis or 0)
                   if ord_ergebnis is not None and ao_ergebnis is not None else None,
                   value("total_result")),
        ) if p]
        return {"posten": posten, "probes": probes,
                "bestanden": len(probes) == 3 and all(p["ok"] for p in probes)}
    return None


# --- Trägeraufstellung (4.1.1) ----------------------------------------------

#: Kurzschlüssel je Aufgabenträger. Der Wortlaut schwankt zwischen den
#: Jahrgängen („Bäderbetriebsgesellschaft Oldenburg mbH" / „… mbH (BBGO)"),
#: die Reihe soll aber über acht Jahre dieselbe Farbe und denselben Platz
#: behalten — dafür braucht sie einen Schlüssel, der nicht am Wortlaut hängt.
TRAEGER: tuple[tuple[str, str, str], ...] = (
    ("stadt", r"^stadt oldenburg", "Kernverwaltung (Stadt Oldenburg)"),
    ("klinikum", r"^klinikum", "Klinikum Oldenburg AöR"),
    ("weh", r"^weser-ems halle", "Weser-Ems Halle"),
    ("vwg", r"^verkehr und wasser", "Verkehr und Wasser GmbH"),
    ("awb", r"^abfallwirtschaftsbetrieb", "Abfallwirtschaftsbetrieb"),
    ("bbo", r"^bäderbetrieb der stadt", "Bäderbetrieb"),
    ("bbgo", r"^bäderbetriebsgesellschaft", "Bäderbetriebsgesellschaft"),
    ("egh", r"^eigenbetrieb gebäudewirtschaft", "Eigenbetrieb Gebäudewirtschaft und Hochbau"),
    ("konsolidierung", r"^konsolidierung", "Verrechnung untereinander"),
)

#: Womit die beiden Aufstellungen anfangen. Der Bericht kündigt sie wörtlich
#: an; die Überschrift „4.1.1" steht im Extrakt nicht zuverlässig davor.
_TRAEGER_ANKER = (
    ("revenues", re.compile(r"ordentlichen Gesamterträge entwickelten sich")),
    ("expenses", re.compile(r"ordentlichen Gesamtaufwendungen entwickelten sich")),
)
_TRAEGER_ZEILE = re.compile(
    rf"^(.{{4,70}}?)\s+({_TEUR})\s+({_TEUR})\s+({_TEUR})\s*$")
#: Die Summenzeile trägt keine Beschriftung, nur drei Zahlen.
_SUMMEN_ZEILE = re.compile(rf"^({_TEUR})\s+({_TEUR})\s+({_TEUR})\s*$")


def _traeger_key(name: str) -> tuple[str, str] | None:
    klein = " ".join(name.lower().split())
    for key, muster, anzeige in TRAEGER:
        if re.match(muster, klein):
            return key, anzeige
    return None


def parse_traeger(text: str) -> list[dict]:
    """Abschnitt 4.1.1 lesen: wer wie viel zum Konzern beiträgt.

    Je Aufstellung (Erträge, Aufwendungen) eine Liste von Trägerzeilen in
    **TEUR**, dazu die Konsolidierungszeile und die Gesamtsumme. Übernommen
    wird nur, was die Zeilenprobe ``Jahr − Vorjahr = Veränderung`` besteht —
    2017 scheitert daran genau eine Zeile, und zwar zu Recht: Dort steht in
    der Veränderungsspalte der Aufwendungssumme ``- 1.665.521`` statt der
    tatsächlichen ``+ 49.357``."""
    aus: list[dict] = []
    for art, anker in _TRAEGER_ANKER:
        m = anker.search(text or "")
        if not m:
            continue
        zeilen: list[dict] = []
        summe: dict | None = None
        for roh in text[m.end():m.end() + 2200].split("\n"):
            zeile = roh.strip()
            if not zeile:
                continue
            treffer = _TRAEGER_ZEILE.match(zeile)
            if treffer:
                erkannt = _traeger_key(treffer.group(1))
                if not erkannt:
                    continue
                werte = [_zahl(treffer.group(i), dezimal=False) for i in (2, 3, 4)]
                if any(w is None for w in werte):
                    continue
                key, anzeige = erkannt
                zeilen.append({"art": art, "entity_key": key, "entity": anzeige,
                               "amount_keur": werte[0], "prior_year_keur": werte[1],
                               "change_keur": werte[2],
                               "probe_ok": abs((werte[0] - werte[1]) - werte[2])
                               <= TOLERANZ_TEUR})
                continue
            if zeilen and summe is None:
                treffer = _SUMMEN_ZEILE.match(zeile)
                if treffer:
                    werte = [_zahl(treffer.group(i), dezimal=False) for i in (1, 2, 3)]
                    if all(w is not None for w in werte):
                        summe = {"amount_keur": werte[0], "prior_year_keur": werte[1]}
                        break
        if not zeilen or summe is None:
            continue
        gut = [z for z in zeilen if z["probe_ok"]]
        gerechnet = sum(z["amount_keur"] for z in zeilen)
        aus.append({
            "art": art,
            "zeilen": gut,
            "verworfen": len(zeilen) - len(gut),
            "total_keur": summe["amount_keur"],
            # Spaltenprobe: alle Träger plus Konsolidierungszeile ergeben die
            # ausgewiesene Gesamtsumme. Die Konsolidierungszeile steht in
            # `zeilen` und trägt ihr Minus selbst — nichts abzuziehen.
            "spaltenprobe_ok": abs(gerechnet - summe["amount_keur"]) <= TOLERANZ_TEUR,
            "spaltenprobe_delta": round(gerechnet - summe["amount_keur"], 2),
        })
    return aus


# --- Beides zusammen --------------------------------------------------------

#: Welche Rolle der Gesamtergebnisrechnung zu welcher Trägeraufstellung gehört.
_QUERPROBE = {"revenues": "revenues_total", "expenses": "expenses_total"}


def lies(text: str) -> dict:
    """Einen Gesamtabschluss vollständig lesen, mit allen Proben.

    Liefert ``{"posten", "entity", "probes", "bestanden", "verworfen"}``.
    ``bestanden`` sagt nur etwas über die Gesamtergebnisrechnung — sie ist der
    Kern, ohne den der Jahrgang wertlos ist. Die Trägeraufstellung wird je
    Aufstellung einzeln beurteilt: 2018 weist die Aufwendungsseite eine
    Konsolidierungszeile aus, die zur eigenen Summe nicht passt (−80.462
    statt −80.398, wie der Bericht des Folgejahres sie führt). Diese eine
    Aufstellung fällt weg, die Ertragsseite desselben Jahrgangs bleibt.

    Die **Querprobe** ist die dritte unabhängige Prüfung: Die Summe der
    Trägeraufstellung muss den Summenposten der Gesamtergebnisrechnung
    wiedergeben — zwei Tabellen aus verschiedenen Kapiteln desselben Berichts,
    die einander bestätigen müssen."""
    ger = parse_gesamtergebnisrechnung(text)
    posten = ger["posten"] if ger else []
    nach_rolle = {p["role"]: p for p in posten if p["role"]}
    entity, verworfen = [], 0
    gefunden = parse_traeger(text)
    for block in gefunden:
        verworfen += block["verworfen"]
        summenposten = nach_rolle.get(_QUERPROBE[block["art"]])
        block["querprobe_delta"] = (
            round(block["total_keur"] - summenposten["amount"] / 1000.0, 2)
            if summenposten else None)
        block["querprobe_ok"] = (block["querprobe_delta"] is not None
                                 and abs(block["querprobe_delta"]) <= TOLERANZ_TEUR)
        if block["spaltenprobe_ok"] and block["querprobe_ok"]:
            entity.append(block)
        else:
            verworfen += len(block["zeilen"])
    return {"posten": posten if ger and ger["bestanden"] else [],
            "entity": entity,
            # Wie viele Aufstellungen im Dokument stehen — nicht dasselbe wie
            # die Zahl der übernommenen. 2014–2016 kennen den Abschnitt 4.1.1
            # noch gar nicht; das ist eine Lücke der Quelle, keine gerissene
            # Probe, und darf nicht als Warnung im Protokoll landen.
            "traeger_gefunden": len(gefunden),
            "probes": ger["probes"] if ger else [],
            "bestanden": bool(ger and ger["bestanden"]),
            "verworfen": verworfen}


def probennachweis(probes: list[dict]) -> str:
    """Der **Messwert** der Rechenproben, als eine Zeile.

    Nicht zu verwechseln mit dem Probennamen: Der steht in
    ``herkunft.PROBEN`` und wird dort einmal für Leserinnen erklärt. Hier
    steht, was bei diesem Jahrgang tatsächlich herauskam — der Nachweis, dass
    die Probe wirklich lief und nicht nur behauptet wird."""
    # `+ 0.0` macht aus der negativen Null eine gewöhnliche: Sonst steht im
    # Beleg „Δ -0.00 €", und das liest sich wie ein Rest, wo keiner ist.
    return "; ".join(f"{p['probe']}: Δ {p['delta'] + 0.0:.2f} €".replace("-0.00", "0.00")
                     for p in probes if p["ok"])


def traegernachweis(entity: list[dict]) -> str:
    """Dasselbe für die Trägeraufstellung: die größte gemessene Abweichung
    der Spalten- und der Querprobe, in TEUR."""
    if not entity:
        return ""
    spalte = max(abs(b["spaltenprobe_delta"]) for b in entity)
    quer = max(abs(b["querprobe_delta"] or 0.0) for b in entity)
    return (f"Trägersumme: Δ {spalte:.0f} TEUR; "
            f"Abgleich mit der Ergebnisrechnung: Δ {quer:.0f} TEUR")
