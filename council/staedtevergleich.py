"""Was sich zwischen Städten vergleichen lässt — die amtliche Statistik des LSN.

Diese Schicht liest zwei Veröffentlichungen des **Landesamts für Statistik
Niedersachsen** (LSN) ein und macht daraus einen Städtevergleich, der ohne
Fußnote trägt:

1. **Kommunaler Finanzausgleich**, Blatt ``ST_KR_MESS_VGL`` — die
   Steuerkraftmesszahl je Gemeinde, zwei Ausgleichsjahre nebeneinander.
2. **Realsteuervergleich**, Blätter ``2_1`` und ``5_1`` — Hebesätze,
   Ist-Aufkommen je Einwohner und die Steuereinnahmekraft über drei Jahre.

Warum ausgerechnet diese beiden Größen
--------------------------------------
Weil sie die einzigen sind, bei denen ein Städtevergleich nicht in die Irre
führt. Der naheliegende Vergleich — Ausgaben, Personal, Schulden je Einwohner
aus dem Kernhaushalt — misst zuerst, **wie weit eine Stadt ausgelagert hat**,
und erst danach ihre Politik. Oldenburg führt Gebäudewirtschaft, Abfall und
Bäder als Eigenbetriebe, das Klinikum als Anstalt; im Kernhaushalt stehen
darum nur rund 64 % dessen, was der Konzern bewegt. Bei Osnabrück sind es
knapp 48 %, weil dort die Stadtwerke dazugehören. Wer zwei Kernhaushalte
nebeneinanderstellt, vergleicht zuerst zwei Organisationsformen.

Das ist keine Vermutung dieses Projekts. Die Stadt Oldenburg hat genau diesen
Vergleich 2018 auf Antrag der FDP-Fraktion selbst angestellt — sieben Städte,
neun Jahrgänge — und ihn im selben Dokument entwertet (``document_id``
196525): *„Die heterogenen Strukturen der verschiedenen Städte lassen einen
aussagefähigen Vergleich in dem Sinne nicht zu, dass eine niedrigere Quote
‚besser' als eine höhere Quote ist."* Dasselbe sagen der Runderlass des Nds.
Innenministeriums vom 13.12.2017 und das Statistische Bundesamt.

Steuerkraft und Hebesätze sind davon **nicht** betroffen: Steuern erhebt nie
ein Eigenbetrieb, und die Steuerkraftmesszahl rechnet § 11 NFAG für alle
Gemeinden mit denselben Nivellierungshebesätzen. Dieselbe Kennzahl, dieselbe
Stelle, dieselbe Abgrenzung, alle Gemeinden.

Drei Fallen, die dieser Parser bewusst umgeht
---------------------------------------------
1. **Der Städtename ist nicht stabil.** Der Jahrgang 2025 schreibt
   ``Oldenburg (Oldb), Stadt``, der Jahrgang 2026 ``Oldenburg (Oldenburg),
   Stadt``; ``Bad Zwischenahn`` bekommt zwischendurch ein ``*``. Verbunden
   wird deshalb **ausschließlich über die Schlüsselnummer**.
2. **Die Schlüsselnummer hat zwei Schreibweisen.** Der Finanzausgleich führt
   sie sechsstellig (``403000``), der Realsteuervergleich dreistellig
   (``403``). :func:`schluessel_normalisieren` bringt beide auf dieselbe Form —
   sonst fänden die zwei Reihen einander nie.
3. **Die Spaltenposition ist keine Zusage.** Gelesen wird über den
   ausgeschriebenen Tabellenkopf, den das LSN als Vorlesehilfe für
   Screenreader mitliefert — und **wo** der steht, sagt die Datei in ihren
   ersten Zeilen selbst („Der Tabellenkopf für Vorlesehilfen befindet sich in
   Zeile 14"). Genau die Falle, an der die PDF-Parser dieses Projekts
   wiederholt hingen, entfällt damit.

Kein neues Paket
----------------
XLSX ist ein ZIP mit XML darin; beides steht in der Standardbibliothek. Ein
Extra-Paket nur für einen Ingest, der einmal im Jahr von Hand läuft, käme in
``requirements.txt`` und damit auf den Server — dieselbe Überlegung, aus der
``fastembed`` bewusst draußen steht.

Der Jahresversatz, der hier NICHT auftaucht
--------------------------------------------
Unser Open-Data-Datensatz 1106 (``council_steuerkraft``) trägt dieselben
Beträge wie das LSN, aber unter einer um **ein Jahr verschobenen**
Jahresangabe: Was das LSN „KFA 2026" nennt, heißt dort „Ausgleichsjahr 2025"
(drei Wertepaare geprüft, zwei unabhängige Wege). Welche Beschriftung stimmt,
ist offen und wird bei der Statistikstelle geklärt.

Bis dahin gilt die Regel, an der sich diese Schicht ausrichtet: **Zahlen aus
dieser Tabelle stehen nie unkommentiert neben Zahlen aus
``council_steuerkraft``.** Sie liegen in einer eigenen Tabelle, tragen die
Jahresangabe des LSN und sagen das auf der Seite auch. Beides
zusammenzuwerfen hieße, zwei Jahre gegeneinander zu plotten, die nicht
dasselbe meinen.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_DOC = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_NS_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

#: Die acht kreisfreien Städte Niedersachsens — Schlüsselnummer → Name.
#:
#: Fest verdrahtet, weil die Menge eine Rechtsfrage ist und keine Datenfrage:
#: Sie steht in Blatt ``9a`` der KFA-Datei und ändert sich nur, wenn ein Land
#: seine Kreisgliederung ändert. Hannover und Göttingen fehlen mit Absicht —
#: beide sind *kreisangehörig* mit Sonderrechten. Hannovers Sozialhilfe,
#: Kliniken, Abfallwirtschaft und Berufsschulen liegen bei der Region, wofür
#: 2026 rund 539 Mio. € Regionsumlage abfließen; ein Vergleich mit Oldenburg
#: verglich zwei verschiedene Aufgabenpakete.
KREISFREIE_STAEDTE: dict[str, str] = {
    "101000": "Braunschweig",
    "102000": "Salzgitter",
    "103000": "Wolfsburg",
    "401000": "Delmenhorst",
    "402000": "Emden",
    "403000": "Oldenburg",
    "404000": "Osnabrück",
    "405000": "Wilhelmshaven",
}

#: Oldenburg — die Stadt, um die es geht.
OLDENBURG = "403000"

#: Die Gemeinden unter 100.000 Einwohnern. Das NFAG rechnet ihre
#: Steuerkraftmesszahl mit **anderen** Nivellierungshebesätzen (KFA 2026:
#: Grundsteuer B 387 statt 483 v. H.). Für die Steuerkraft gehört dieser
#: Hinweis an den Wert, für die Steuereinnahmekraft nicht — die kennt die
#: Schwelle nicht.
UNTER_100K: frozenset[str] = frozenset({"401000", "402000", "405000"})


def schluessel_normalisieren(roh: object) -> str | None:
    """Schlüsselnummer auf die sechsstellige Form bringen.

    Der Finanzausgleich führt ``403000``, der Realsteuervergleich ``403`` —
    dieselbe Stadt, zwei Schreibweisen. Ohne diese Angleichung fänden die
    beiden Reihen einander nie, und der Fehler wäre still: Es käme keine
    falsche Zahl heraus, sondern gar keine.

    Alles, was keine Zahl ist (Zwischenüberschriften wie „Statistische Region
    Braunschweig") ergibt ``None``.
    """
    if roh is None:
        return None
    text = str(roh).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    if not text.isdigit():
        return None
    if len(text) <= 3:
        return text.zfill(3) + "000"
    return text.zfill(6)


# --- XLSX ohne Fremdpaket ---------------------------------------------------

def _spaltenindex(ref: str) -> int:
    """Zellbezug ``B14`` → Spaltenindex 1 (zählt ab 0)."""
    n = 0
    for zeichen in ref:
        if not zeichen.isalpha():
            break
        n = n * 26 + (ord(zeichen.upper()) - 64)
    return n - 1


def _xml(roh: bytes) -> ET.Element:
    """XML einlesen — und vorher eine Dokumenttyp-Deklaration ablehnen.

    ``xml.etree`` löst keine externen Entitäten auf (XXE greift hier also
    nicht), lässt sich aber über **intern** definierte Entitäten aufblähen
    („billion laughs"): Ein paar Zeilen DTD genügen, um beim Auspacken
    Gigabyte zu erzeugen. Beides braucht ein ``<!DOCTYPE``, und eine XLSX-Mappe
    hat keins — die Deklaration zu verweigern kostet damit nichts und schließt
    die Lücke ohne ein zusätzliches Paket (``defusedxml`` stünde sonst in
    ``requirements.txt`` und damit auf dem Server, s. Modulkopf).
    """
    if re.search(rb"<!DOCTYPE", roh[:4096], re.IGNORECASE):
        raise ValueError(
            "Diese XLSX-Datei bringt eine Dokumenttyp-Deklaration mit. Echte "
            "Tabellenmappen haben keine; wir lesen sie deshalb nicht ein.")
    return ET.fromstring(roh)


def _texte(z: zipfile.ZipFile) -> list[str]:
    """Die ``sharedStrings``-Tabelle — dort liegt jeder Text der Mappe."""
    try:
        roh = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    aus = []
    for si in _xml(roh).findall(f"{_NS}si"):
        # Nur ``<t>`` direkt und ``<r><t>`` (formatierte Teilstücke). Bewusst
        # NICHT alles rekursiv: ``<rPh>`` trägt phonetische Lesehilfen, die
        # sonst stumm mitten im Text landeten.
        teile = []
        for kind in si:
            if kind.tag == f"{_NS}t":
                teile.append(kind.text or "")
            elif kind.tag == f"{_NS}r":
                teile.extend(t.text or "" for t in kind.iter(f"{_NS}t"))
        aus.append("".join(teile))
    return aus


def _blattpfad(z: zipfile.ZipFile, name: str) -> str:
    """Blattname → Pfad im ZIP. Der Umweg über die Beziehungsdatei ist nötig,
    weil ``sheet1.xml`` nicht zwangsläufig das erste Blatt ist."""
    mappe = _xml(z.read("xl/workbook.xml"))
    rels = _xml(z.read("xl/_rels/workbook.xml.rels"))
    ziele = {r.get("Id"): r.get("Target") for r in rels.iter(f"{_NS_PKG}Relationship")}
    for blatt in mappe.iter(f"{_NS}sheet"):
        if blatt.get("name") == name:
            ziel = ziele.get(blatt.get(f"{_NS_DOC}id")) or ""
            if ziel.startswith("/"):
                return ziel.lstrip("/")
            return ziel if ziel.startswith("xl/") else f"xl/{ziel}"
    raise KeyError(f"Blatt {name!r} gibt es in dieser Datei nicht")


def blatt_lesen(pfad: str, name: str) -> list[list[object]]:
    """Ein Tabellenblatt als Liste von Zeilen; Index 0 ist Zeile 1.

    Ausgelassene Zeilen und Zellen füllt die Funktion auf: XLSX speichert nur,
    was belegt ist, und eine Zeilennummer, die man abzählt statt sie zu lesen,
    zeigt beim ersten leeren Feld auf die falsche Zeile.
    """
    with zipfile.ZipFile(pfad) as z:
        texte = _texte(z)
        wurzel = _xml(z.read(_blattpfad(z, name)))
        zeilen: dict[int, list[object]] = {}
        for zeile in wurzel.iter(f"{_NS}row"):
            nr = int(zeile.get("r") or 0)
            if not nr:
                continue
            werte: dict[int, object] = {}
            for zelle in zeile.findall(f"{_NS}c"):
                idx = _spaltenindex(zelle.get("r") or "")
                if idx < 0:
                    continue
                typ = zelle.get("t")
                if typ == "inlineStr":
                    knoten = zelle.find(f"{_NS}is")
                    wert: object = ("".join(t.text or "" for t in knoten.iter(f"{_NS}t"))
                                    if knoten is not None else None)
                else:
                    v = zelle.find(f"{_NS}v")
                    wert = v.text if v is not None else None
                    if wert is not None and typ == "s":
                        i = int(wert)
                        wert = texte[i] if 0 <= i < len(texte) else None
                    elif wert is not None:
                        try:
                            wert = float(wert)
                        except ValueError:
                            pass
                if wert is not None and wert != "":
                    werte[idx] = wert
            zeilen[nr] = ([werte.get(i) for i in range(max(werte) + 1)]
                          if werte else [])
        if not zeilen:
            return []
        return [zeilen.get(i, []) for i in range(1, max(zeilen) + 1)]


def _kopfzeile(zeilen: list[list[object]]) -> int:
    """Der Index der ausgeschriebenen Kopfzeile — aus der Datei selbst.

    Das LSN legt für Screenreader einen vollständig ausgeschriebenen
    Tabellenkopf ab („Grundsteuer B; Hebesatz; in %") und sagt in den ersten
    Zeilen, **wo** er steht. Diesen Hinweis zu lesen ist verlässlicher, als
    eine Zeilennummer zu raten: Er wandert mit, wenn das LSN eine Fußnote
    einfügt.

    **Den Satz gibt es in zwei Fassungen.** Der Realsteuervergleich schreibt
    „Der Tabellenkopf für Vorlesehilfen befindet sich in Zeile 7.", die
    Gewerbesteuerstatistik „Vorlesbarer Tabellenkopf in Zeile 8". Gesucht wird
    deshalb nach dem, was beide gemeinsam haben — dem Wort „Tabellenkopf" und
    einer Zeilennummer dahinter. Die erste Fassung allein hätte den zweiten
    Bericht nicht gefunden, und zwar mit einer Fehlermeldung über den Aufbau
    der Datei statt über den Satz, der fehlt.
    """
    for i, zeile in enumerate(zeilen[:12]):
        for zelle in zeile:
            text = str(zelle or "")
            if "Tabellenkopf" not in text:
                continue
            treffer = re.search(r"Zeile\s*(\d+)", text)
            if treffer:
                return int(treffer.group(1)) - 1
    raise ValueError(
        "Kein Hinweis auf die Vorlesehilfe-Kopfzeile gefunden — das Blatt ist "
        "nicht so aufgebaut wie die geprüften LSN-Dateien. Lieber abbrechen "
        "als über Spaltenpositionen raten.")


def _spalten(kopf: list[object]) -> dict[int, str]:
    """Spaltenindex → ausgeschriebener Kopftext (Zeilenumbrüche geglättet)."""
    aus = {}
    for i, zelle in enumerate(kopf):
        text = " ".join(str(zelle or "").split())
        if text and text != "Zeilenende":
            aus[i] = text
    return aus


def _finde(spalten: dict[int, str], muster: str) -> int | None:
    """Erste Spalte, deren Kopftext auf ``muster`` passt."""
    for i, text in sorted(spalten.items()):
        if re.search(muster, text, re.IGNORECASE):
            return i
    return None


def _zahl(wert: object) -> float | None:
    """Zellwert → Zahl. ``x`` (»nicht anwendbar«) und Text ergeben ``None``."""
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    text = str(wert).strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


# --- Kommunaler Finanzausgleich: Steuerkraftmesszahl ------------------------

@dataclass
class KfaJahrgang:
    """Ein Ausgleichsjahr aus ``ST_KR_MESS_VGL``.

    ``year`` ist das Ausgleichsjahr, das die Datei selbst benennt — **nicht**
    das, unter dem unser Open-Data-Bestand dieselben Beträge führt (s.
    Modulkopf).
    """

    year: int
    #: Das mitgelieferte Vorjahr. Es ist die Rechenprobe: Es muss die
    #: Hauptspalte des Vorjahrgangs wiederholen.
    prior_year: int
    stand: str | None
    #: Schlüssel → {city, einwohner, tax_index_keur, vorjahr_tax_index_keur}
    staedte: dict[str, dict] = field(default_factory=dict)


def lies_kfa(pfad: str) -> KfaJahrgang:
    """Blatt ``ST_KR_MESS_VGL`` einer KFA-Datei einlesen — alle Gemeinden.

    Bewusst alle 403 und nicht nur die acht kreisfreien Städte: Die
    Zwei-Jahres-Überlappung (:func:`probe_ueberlappung`) ist nur dann eine
    ernsthafte Probe, wenn sie über den ganzen Bestand läuft. Eingeengt wird
    erst beim Speichern.
    """
    zeilen = blatt_lesen(pfad, "ST_KR_MESS_VGL")
    if not zeilen:
        raise ValueError(f"{pfad}: Blatt ST_KR_MESS_VGL ist leer")
    kopf_idx = _kopfzeile(zeilen)
    spalten = _spalten(zeilen[kopf_idx])

    c_key = _finde(spalten, r"Schlüsselnummer")
    c_name = _finde(spalten, r"Bezeichnung")
    c_ew = _finde(spalten, r"Einwohnerzahl")
    jahre = [(i, int(m.group(1))) for i, t in sorted(spalten.items())
             if (m := re.search(r"Steuerkraftmesszahlen\s+(\d{4})", t))]
    if c_key is None or c_name is None or c_ew is None or len(jahre) < 2:
        raise ValueError(
            f"{pfad}: Der Tabellenkopf trägt nicht die erwarteten Spalten "
            f"(gefunden: {sorted(spalten.values())[:8]}…)")
    # Die Datei stellt das Vorjahr links, das Ausgleichsjahr rechts.
    (c_vor, j_vor), (c_jahr, j_jahr) = jahre[0], jahre[1]

    stand = None
    for zeile in zeilen[:6]:
        for zelle in zeile:
            if (m := re.search(r"Stand:\s*([\d.]+)", str(zelle or ""))):
                stand = m.group(1)

    budget_year = KfaJahrgang(year=j_jahr, prior_year=j_vor, stand=stand)
    for zeile in zeilen[kopf_idx + 1:]:
        if not zeile:
            continue
        key = schluessel_normalisieren(zeile[c_key] if c_key < len(zeile) else None)
        if not key:
            continue
        tax_index = _zahl(zeile[c_jahr]) if c_jahr < len(zeile) else None
        if tax_index is None:
            continue
        budget_year.staedte[key] = {
            "city": " ".join(str(zeile[c_name] or "").split()),
            "einwohner": _zahl(zeile[c_ew]) if c_ew < len(zeile) else None,
            "tax_index_keur": tax_index,
            "prior_year_tax_index_keur": _zahl(zeile[c_vor]) if c_vor < len(zeile) else None,
        }
    return budget_year


def probe_ueberlappung(alt: KfaJahrgang, neu: KfaJahrgang) -> dict:
    """Zwei-Jahres-Überlappung: Der neue Jahrgang muss den alten wiederholen.

    Jede KFA-Datei führt zwei Ausgleichsjahre nebeneinander. Das ältere davon
    ist in der Datei des Vorjahres das jüngere — beide Angaben stammen aus
    verschiedenen Veröffentlichungen und müssen trotzdem übereinstimmen. Das
    ist die stärkste Probe, die dieser Bestand hergibt: Sie prüft nicht eine
    Rechnung innerhalb eines Dokuments, sondern zwei Dokumente gegeneinander.

    Geprüft wird über **alle** Gemeinden, nicht nur über die acht Städte.
    """
    if neu.prior_year != alt.year:
        raise ValueError(
            f"Die Jahrgänge greifen nicht ineinander: {alt.year} und "
            f"{neu.year} (Vorjahresspalte {neu.prior_year}).")
    gemeinsam = sorted(set(alt.staedte) & set(neu.staedte))
    abweichungen = []
    for key in gemeinsam:
        a = alt.staedte[key]["tax_index_keur"]
        b = neu.staedte[key]["prior_year_tax_index_keur"]
        if b is None or abs(a - b) > 0.5:
            abweichungen.append({"schluessel": key,
                                 "city": alt.staedte[key]["city"],
                                 "alt": a, "neu": b})
    return {"geprueft": len(gemeinsam), "abweichungen": abweichungen,
            "ok": not abweichungen,
            "result": (f"{len(gemeinsam) - len(abweichungen)} von "
                         f"{len(gemeinsam)} Gemeinden identisch")}


# --- Realsteuervergleich: Hebesätze und Steuereinnahmekraft -----------------

#: Die drei Realsteuern, wie sie im Tabellenkopf heißen → unser Kennzahl-Suffix.
_REALSTEUERN = {"Grundsteuer A": "grundsteuer_a",
                "Grundsteuer B": "grundsteuer_b",
                "Gewerbesteuer": "gewerbesteuer"}


@dataclass
class Realsteuerjahrgang:
    """Ein Berichtsjahr des Realsteuervergleichs (Blätter ``2_1`` und ``5_1``)."""

    year: int
    stand: str | None
    #: Schlüssel → {city, rate_*, grundbetrag_*_teur, ist_*_teur, …}
    hebesaetze: dict[str, dict] = field(default_factory=dict)
    #: Schlüssel → {city, einwohner_schnitt, je_jahr: {year: (teur, je_ew)}, …}
    einnahmekraft: dict[str, dict] = field(default_factory=dict)


def lies_realsteuervergleich(pfad: str) -> Realsteuerjahrgang:
    """Die beiden Blätter des Realsteuervergleichs einlesen.

    ``2_1`` trägt Hebesätze und Ist-Aufkommen der kreisfreien Städte, ``5_1``
    die Steuereinnahmekraft über drei Jahre. Beide führen dieselben acht
    Städte unter derselben Schlüsselnummer — verbunden wird darüber, nie über
    den Namen.
    """
    year, stand = _realsteuer_kopf(pfad)
    budget_year = Realsteuerjahrgang(year=year, stand=stand)

    # --- Blatt 2_1: Hebesätze, Grundbeträge, Ist-Aufkommen ---
    zeilen = blatt_lesen(pfad, "2_1")
    kopf_idx = _kopfzeile(zeilen)
    spalten = _spalten(zeilen[kopf_idx])
    c_key = _finde(spalten, r"Schlüsselnummer")
    c_name = _finde(spalten, r"Kreisfreie Stadt")
    if c_key is None:
        raise ValueError(f"{pfad}: Blatt 2_1 ohne Schlüsselnummer-Spalte")

    bezug: dict[str, dict[str, int | None]] = {}
    for kopf, suffix in _REALSTEUERN.items():
        # ZWEI VERSCHIEDENE SPALTEN, UND DER UNTERSCHIED IST WICHTIG.
        # Die Gewerbesteuer steht dreimal da: brutto, Umlage, netto. Für die
        # Rechenprobe gilt `Grundbetrag × Hebesatz = BRUTTO` — die Umlage wird
        # erst danach abgezogen. Angezeigt wird dagegen **netto**, denn nur das
        # bleibt der Stadt. Die erste Fassung prüfte gegen netto und verwarf
        # deshalb alle acht Städte; die Abweichung war jedes Mal auf die
        # Tausend Euro genau die Gewerbesteuerumlage.
        ist = (r"Gewerbesteuer; Ist-Aufkommen brutto; in 1000"
               if suffix == "gewerbesteuer"
               else rf"{kopf}; Ist-Aufkommen; in 1000")
        ist_ew = (r"Gewerbesteuer; Ist-Aufkommen netto; EUR je"
                  if suffix == "gewerbesteuer"
                  else rf"{kopf}; Ist-Aufkommen; EUR je")
        bezug[suffix] = {
            "rate": _finde(spalten, rf"{kopf}; Hebesatz"),
            "grundbetrag": _finde(spalten, rf"{kopf}; Grundbetrag; in 1000"),
            "ist": _finde(spalten, ist),
            "ist_je_ew": _finde(spalten, ist_ew),
        }
    bezug["gewerbesteuer"]["umlage"] = _finde(
        spalten, r"Gewerbesteuerumlage\d*\); in 1000")
    bezug["gewerbesteuer"]["netto"] = _finde(
        spalten, r"Gewerbesteuer; Ist-Aufkommen netto; in 1000")

    for zeile in zeilen[kopf_idx + 1:]:
        if not zeile:
            continue
        key = schluessel_normalisieren(zeile[c_key] if c_key < len(zeile) else None)
        if key not in KREISFREIE_STAEDTE:
            continue
        eintrag: dict = {"city": " ".join(str(
            zeile[c_name] if c_name is not None and c_name < len(zeile) else "").split())}
        for suffix, cols in bezug.items():
            for feld, idx in cols.items():
                eintrag[f"{feld}_{suffix}"] = (
                    _zahl(zeile[idx]) if idx is not None and idx < len(zeile) else None)
        budget_year.hebesaetze[key] = eintrag

    # --- Blatt 5_1: Steuereinnahmekraft, drei Jahre + Durchschnitt ---
    zeilen = blatt_lesen(pfad, "5_1")
    kopf_idx = _kopfzeile(zeilen)
    spalten = _spalten(zeilen[kopf_idx])
    c_key = _finde(spalten, r"Schlüsselnummer")
    c_name = _finde(spalten, r"Kreisfreie Stadt")
    c_ew = _finde(spalten, r"Durchschnittliche Zahl der Einwohner")
    c_mittel = _finde(spalten, r"Dreijahresdurchschnitt; in 1000")
    c_mittel_ew = _finde(spalten, r"Dreijahresdurchschnitt; EUR je")
    jahresspalten: dict[int, dict[str, int]] = {}
    for i, text in sorted(spalten.items()):
        if (m := re.search(r"Steuereinnahmekraft; Jahr (\d{4}); (in 1000|EUR je)", text)):
            jahresspalten.setdefault(int(m.group(1)), {})[
                "teur" if m.group(2) == "in 1000" else "je_ew"] = i
    if c_key is None or not jahresspalten:
        raise ValueError(f"{pfad}: Blatt 5_1 trägt nicht die erwarteten Spalten")

    for zeile in zeilen[kopf_idx + 1:]:
        if not zeile:
            continue
        key = schluessel_normalisieren(zeile[c_key] if c_key < len(zeile) else None)
        if key not in KREISFREIE_STAEDTE:
            continue
        je_jahr = {}
        for j, cols in sorted(jahresspalten.items()):
            teur = _zahl(zeile[cols["teur"]]) if cols["teur"] < len(zeile) else None
            je_ew = _zahl(zeile[cols["je_ew"]]) if cols["je_ew"] < len(zeile) else None
            if teur is not None and je_ew is not None:
                je_jahr[j] = {"teur": teur, "je_ew": je_ew}
        budget_year.einnahmekraft[key] = {
            "city": " ".join(str(
                zeile[c_name] if c_name is not None and c_name < len(zeile) else "").split()),
            "einwohner_schnitt": (_zahl(zeile[c_ew])
                                  if c_ew is not None and c_ew < len(zeile) else None),
            "je_jahr": je_jahr,
            "mittel_teur": (_zahl(zeile[c_mittel])
                            if c_mittel is not None and c_mittel < len(zeile) else None),
            "mittel_je_ew": (_zahl(zeile[c_mittel_ew])
                             if c_mittel_ew is not None and c_mittel_ew < len(zeile) else None),
        }
    return budget_year


def _realsteuer_kopf(pfad: str) -> tuple[int, str | None]:
    """Berichtsjahr und Stand vom Titelblatt.

    Das Jahr steht dort als „Realsteuervergleich 2025"; der Stand nur, wenn
    das LSN nachgebessert hat („Korrigierte Version vom 30.07.2026"). Genau
    das gehört an die Zahl: Die Fassung, die wir gelesen haben, ist nicht
    zwingend die erste, die es gab.
    """
    year, stand = None, None
    for zeile in blatt_lesen(pfad, "Titel"):
        for zelle in zeile:
            text = " ".join(str(zelle or "").split())
            if (m := re.search(r"Realsteuervergleich\s+(\d{4})", text)):
                year = int(m.group(1))
            if (m := re.search(r"(Korrigierte Version vom [\d.]+)", text)):
                stand = m.group(1)
    if year is None:
        raise ValueError(f"{pfad}: Auf dem Titelblatt steht kein Berichtsjahr")
    return year, stand


def probe_hebesatz(eintrag: dict) -> dict:
    """Grundbetrag × Hebesatz = Ist-Aufkommen — die Definition einer Realsteuer.

    Das ist keine erfundene Kontrollrechnung, sondern die Rechenvorschrift
    selbst: Der Grundbetrag ist die Summe der Steuermessbeträge, der Hebesatz
    der Faktor, den der Rat beschließt. Geht sie nicht auf, wurde die falsche
    Spalte gelesen.

    **Die Toleranz folgt der Rundung, nicht dem Gefühl.** Das LSN weist
    Grundbetrag und Ist-Aufkommen auf volle Tausend Euro gerundet aus. Ein
    Rundungsfehler von ±0,5 T€ im Grundbetrag wird mit dem Hebesatz
    multipliziert; bei 500 % sind das ±2,5 T€, dazu ±0,5 T€ aus der Rundung
    des Ist-Aufkommens. Eine feste Prozentschranke würde deshalb genau die
    Grundsteuer A verwerfen, deren Beträge so klein sind (13–44 T€), dass die
    Rundung dort 1–3 % ausmacht — ein stiller Totalausfall der Art, vor der
    die Parser-Regeln dieses Projekts warnen.
    """
    ergebnisse, schlimmster = [], 0.0
    for kopf, suffix in _REALSTEUERN.items():
        grundbetrag = eintrag.get(f"grundbetrag_{suffix}")
        rate = eintrag.get(f"rate_{suffix}")
        ist = eintrag.get(f"ist_{suffix}")   # bei der Gewerbesteuer: brutto
        if grundbetrag is None or rate is None or ist is None:
            continue
        erwartet = grundbetrag * rate / 100
        deviation = abs(erwartet - ist)
        toleranz = 0.5 * rate / 100 + 0.5
        ergebnisse.append({"steuer": kopf, "deviation": deviation,
                           "toleranz": toleranz, "ok": deviation <= toleranz})
        schlimmster = max(schlimmster, deviation)

    # Zweiter Teil, nur für die Gewerbesteuer: brutto − Umlage = netto. Er
    # sichert genau den Wert ab, den die Seite zeigt — die erste Rechnung
    # bestätigt nur das Brutto, das die Stadt gar nicht behält.
    brutto = eintrag.get("ist_gewerbesteuer")
    umlage = eintrag.get("umlage_gewerbesteuer")
    netto = eintrag.get("netto_gewerbesteuer")
    if None not in (brutto, umlage, netto):
        deviation = abs((brutto - umlage) - netto)
        ergebnisse.append({"steuer": "Gewerbesteuer netto",
                           "deviation": deviation, "toleranz": 1.0,
                           "ok": deviation <= 1.0})
        schlimmster = max(schlimmster, deviation)

    ok = bool(ergebnisse) and all(e["ok"] for e in ergebnisse)
    return {"ok": ok, "teilproben": ergebnisse,
            "result": f"größte Abweichung {schlimmster:.1f} Tsd. Euro"}


def probe_dreijahresmittel(eintrag: dict) -> dict:
    """Der ausgewiesene Dreijahresdurchschnitt ist das Mittel der drei Jahre.

    Prüft beides, was die Zeile behauptet: den Durchschnittsbetrag gegen das
    Mittel der drei Jahresbeträge und den Pro-Kopf-Wert gegen denselben Betrag
    geteilt durch die mitgelieferte durchschnittliche Einwohnerzahl.

    Der zweite Teil ist der wichtigere, weil er die **Bezugsgröße** festnagelt:
    Die Pro-Kopf-Werte der einzelnen Jahre rechnet das LSN mit der jeweiligen
    Jahresbevölkerung, der Durchschnitt mit dem Dreijahresmittel. Wer das
    verwechselt, liegt um bis zu 20 Euro je Einwohner daneben — genug, um eine
    Rangfolge zu drehen.
    """
    jahre = eintrag.get("je_jahr") or {}
    mittel, ew = eintrag.get("mittel_teur"), eintrag.get("einwohner_schnitt")
    if len(jahre) < 3 or mittel is None:
        return {"ok": False, "result": "kein vollständiger Dreijahresblock"}
    rechnung = sum(j["teur"] for j in jahre.values()) / len(jahre)
    # Das Mittel dritteln erzeugt Rundungsreste von bis zu 2/3 Tsd. Euro.
    amount_ok = abs(rechnung - mittel) <= 1.0
    je_ew_ok, je_ew_abw = True, 0.0
    if ew and eintrag.get("mittel_je_ew") is not None:
        je_ew_abw = abs(rechnung * 1000 / ew - eintrag["mittel_je_ew"])
        je_ew_ok = je_ew_abw <= 0.05
    return {"ok": amount_ok and je_ew_ok,
            "result": (f"Mittel {rechnung:.0f} gegen ausgewiesene {mittel:.0f} "
                         f"Tsd. Euro, je Einwohner {je_ew_abw:.3f} Euro Abstand")}


# --- Was in die Datenbank geht ---------------------------------------------

def zeilen_steuerkraft(budget_year: KfaJahrgang) -> list[dict]:
    """Die acht kreisfreien Städte eines KFA-Jahrgangs als Speicherzeilen.

    Gespeichert werden **Messzahl und Einwohnerzahl getrennt**, nicht der
    Pro-Kopf-Wert. Der Grund ist Ehrlichkeit: Das LSN weist die
    Steuerkraft je Einwohner gar nicht aus — diese Division ist unsere. Wer
    sie als gespeicherte Kennzahl führte, könnte später nicht mehr
    unterscheiden, was amtlich ist und was gerechnet. Die Oberfläche teilt
    und schreibt dazu, dass sie teilt.
    """
    aus = []
    for key, name in KREISFREIE_STAEDTE.items():
        eintrag = budget_year.staedte.get(key)
        if not eintrag:
            continue
        gemeinsam = {"series": "steuerkraft", "year": budget_year.year,
                     "schluessel": key, "city": name}
        aus.append({**gemeinsam, "indicator": "steuerkraftmesszahl",
                    "wert": eintrag["tax_index_keur"], "einheit": "teur"})
        if eintrag.get("einwohner"):
            aus.append({**gemeinsam, "indicator": "einwohner",
                        "wert": eintrag["einwohner"], "einheit": "anzahl"})
    return aus


def zeilen_realsteuern(budget_year: Realsteuerjahrgang) -> tuple[list[dict], list[dict]]:
    """Speicherzeilen des Realsteuervergleichs — und was daran scheiterte.

    Gibt ``(zeilen, verworfen)`` zurück. Eine Stadt, deren Hebesatzprobe nicht
    aufgeht, kommt **gar nicht** herein: Lieber eine Lücke, die man sieht, als
    eine Zahl, die falsch sein könnte. Der Grund steht in ``verworfen`` und
    landet im Protokoll des Ingests.
    """
    zeilen: list[dict] = []
    verworfen: list[dict] = []

    for key, eintrag in sorted(budget_year.hebesaetze.items()):
        probe = probe_hebesatz(eintrag)
        if not probe["ok"]:
            verworfen.append({"schluessel": key, "city": KREISFREIE_STAEDTE[key],
                              "series": "realsteuern", "grund": "Hebesatzprobe",
                              "result": probe["result"]})
            continue
        gemeinsam = {"series": "realsteuern", "year": budget_year.year,
                     "schluessel": key, "city": KREISFREIE_STAEDTE[key]}
        for suffix in _REALSTEUERN.values():
            if (wert := eintrag.get(f"rate_{suffix}")) is not None:
                zeilen.append({**gemeinsam, "indicator": f"hebesatz_{suffix}",
                               "wert": wert, "einheit": "prozent"})
            if (wert := eintrag.get(f"ist_je_ew_{suffix}")) is not None:
                zeilen.append({**gemeinsam, "indicator": f"ist_je_ew_{suffix}",
                               "wert": wert, "einheit": "eur_je_ew"})

    for key, eintrag in sorted(budget_year.einnahmekraft.items()):
        probe = probe_dreijahresmittel(eintrag)
        if not probe["ok"]:
            verworfen.append({"schluessel": key, "city": KREISFREIE_STAEDTE[key],
                              "series": "realsteuern", "grund": "Dreijahresmittel",
                              "result": probe["result"]})
            continue
        # Jeder Jahreswert trägt SEIN Jahr, nicht das Berichtsjahr der Datei.
        # Der Realsteuervergleich 2025 führt auch 2023 und 2024 — eine Zeile,
        # die alles unter 2025 ablegte, machte aus drei Jahren eines.
        for year, werte in sorted(eintrag["je_jahr"].items()):
            zeilen.append({"series": "realsteuern", "year": year,
                           "schluessel": key, "city": KREISFREIE_STAEDTE[key],
                           "indicator": "steuereinnahmekraft_je_ew",
                           "wert": werte["je_ew"], "einheit": "eur_je_ew"})
    return zeilen, verworfen
