"""Jahresabschlüsse und Teilhaushalte aus dem Ratsinformationssystem lesen.

Beide Dokumenttypen liegen längst als Anlagen zu Ratsvorlagen in
``council_anlagen`` — mit Volltext, den der Protokoll-Scraper ohnehin zieht.
Kein neuer Download, keine neue Quelle:

- **Jahresabschluss** (300+ Seiten, jährlich): enthält die Ergebnisrechnung
  der Kernverwaltung mit **Ansatz UND Ergebnis nebeneinander** — die Grundlage
  für „geplant gegen tatsächlich", und zugleich die Aufschlüsselung der
  Erträge nach Arten (Steuern, Zuwendungen, Entgelte, Kostenerstattungen).
- **Teilhaushalts-Pläne** (THH01–13, je bis 234 Seiten): enthalten die
  **Produktebene** — was einzelne Aufgaben kosten („Archivierung",
  „Kindertagesbetreuung"), mit Produktnummer und zuständigem Amt.

Beide Parser sind bewusst misstrauisch: Aus PDF-Text extrahierte Tabellen
verschmelzen gerne Zahlen („355.188334.704" statt zweier Werte). Deshalb
werden nur Zeilen übernommen, die eine im Dokument selbst dokumentierte
Rechenbeziehung erfüllen:

- Jahresabschluss: Abweichung = Ergebnis − Ansatz (Fußnote 4 der Tabelle)
- Teilhaushalt: Erträge − Aufwendungen = ordentliches Ergebnis

Was diese Probe nicht besteht, fällt raus. Lieber eine Lücke als eine Zahl,
die niemand nachrechnen kann.
"""
from __future__ import annotations

import re

# --- Jahresabschluss: Ergebnisrechnung der Kernverwaltung --------------------

#: Die Posten der Ergebnisrechnung, wie sie in der Tabelle nummeriert sind.
#: Nur diese Nummern werden gelesen; Zwischenüberschriften fallen weg.
ERGEBNIS_POSTEN = {
    1: "Steuern und ähnliche Abgaben",
    2: "Zuwendungen und allgemeine Umlagen",
    3: "Auflösungserträge aus Sonderposten",
    4: "sonstige Transfererträge",
    5: "öffentlich-rechtliche Entgelte",
    6: "privatrechtliche Entgelte",
    7: "Kostenerstattungen und Kostenumlagen",
    8: "Zinsen und ähnliche Finanzerträge",
    9: "aktivierungsfähige Eigenleistungen",
    10: "Bestandsveränderungen",
    11: "sonstige ordentliche Erträge",
    12: "Summe ordentliche Erträge",
    13: "Personalaufwendungen",
    14: "Versorgungsaufwendungen",
    15: "Aufwendungen für Sach- und Dienstleistungen",
    16: "Abschreibungen",
    17: "Zinsen und ähnliche Aufwendungen",
    18: "Transferaufwendungen",
    19: "sonstige ordentliche Aufwendungen",
    20: "Summe ordentliche Aufwendungen",
    21: "ordentliches Ergebnis",
    22: "außerordentliche Erträge",
    23: "außerordentliche Aufwendungen",
    24: "außerordentliches Ergebnis",
}

#: Posten 12/20/21/24 sind Summen bzw. Salden, keine eigenständigen Arten.
SUMMEN_POSTEN = {12, 20, 21, 24}

_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")


def _eur(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse_ergebnisrechnung(text: str, jahr: int) -> list[dict]:
    """Ergebnisrechnung der Kernverwaltung aus dem Jahresabschluss-Volltext.

    Liefert je Posten ``{nr, bezeichnung, vorjahr, ansatz, ergebnis,
    abweichung}`` in Euro. ``ansatz`` ist der Planwert des Jahres,
    ``ergebnis`` das tatsächliche Ergebnis — genau das Paar, aus dem
    „geplant gegen tatsächlich" wird.

    Die Tabelle hat sieben Spalten, von denen zwei (Nachtrag, Ermächtigung)
    meist leer bleiben. Welche Zahl zu welcher Spalte gehört, lässt sich aus
    der Reihenfolge allein nicht sicher sagen — deshalb prüft der Parser die
    in der Tabellen-Fußnote dokumentierte Beziehung
    ``Abweichung = Ergebnis − Ansatz`` und übernimmt nur, was passt.
    """
    # Auf den Abschnitt der Kernverwaltung beschränken: Danach folgt die
    # Gesamtergebnisrechnung (inkl. Stiftungen), die andere Werte trägt.
    # „3.1 Ergebnisrechnung [der] Kernverwaltung" — ältere Jahrgänge schreiben
    # das „der" mit. Der erste Treffer ist das Inhaltsverzeichnis, deshalb die
    # Fundstelle mit den meisten Beträgen dahinter nehmen.
    stellen = [m.start() for m in re.finditer(
        r"Ergebnisrechnung\s+(?:der\s+)?Kernverwaltung", text)]
    if not stellen:
        return []
    start = max(stellen, key=lambda i: len(_BETRAG.findall(text[i:i + 6000])))
    # Bis zur Gesamtergebnisrechnung lesen, aber mindestens so weit, dass die
    # Aufwendungen (Posten 13–24 auf der Folgeseite) noch drin sind.
    ende = text.find("Gesamtergebnisrechnung", start + 6000)
    block = text[start:ende if ende > 0 else start + 12000]

    return _posten_aus_block(block, jahr)


def _posten_aus_block(block: str, jahr: int) -> list[dict]:
    """Die Posten einer Ergebnisrechnungs-Tabelle lesen — gemeinsam genutzt
    von der Gesamtrechnung und den Teil-Ergebnisrechnungen je Teilhaushalt,
    die dieselbe Tabellenform haben."""
    # Zeilenumbrüche in Bezeichnungen zusammenziehen: Der Postenname kann über
    # zwei Zeilen laufen („07. Kostenerstattungen und\nKostenumlagen 119.0…").
    flach = re.sub(r"\s*\n\s*", " ", block)

    # An den Posten-Nummern aufteilen: „01. …“, „02. …“ — robuster als ein
    # Lookahead, weil zwischen zwei Posten beliebig viel Seitenkopf stehen darf.
    teile = re.split(r"(?<![\d,.])(\d\d)\.\s", flach)
    inhalt: dict[int, str] = {}
    for i in range(1, len(teile) - 1, 2):
        nr = int(teile[i])
        # Erster Treffer gewinnt: Wiederholungen sind Seitenköpfe.
        inhalt.setdefault(nr, teile[i + 1])

    out: list[dict] = []
    for nr, bezeichnung in ERGEBNIS_POSTEN.items():
        roh = inhalt.get(nr)
        if not roh:
            continue
        # Nur bis zum Ende der Zahlenkolonne dieser Zeile lesen.
        zahlen = [_eur(z) for z in _BETRAG.findall(roh[:200])]
        werte = _spalten_zuordnen(zahlen)
        if werte is None:
            continue
        out.append({"nr": nr, "bezeichnung": bezeichnung, "jahr": jahr,
                    "ist_summe": 1 if nr in SUMMEN_POSTEN else 0, **werte})
    return out


#: Kopf einer Teil-Ergebnisrechnung: „A. Teil-Ergebnisrechnung THH01 Name".
#: Die Schreibweise schwankt zwischen den Jahrgängen (mit/ohne Bindestrich,
#: ein oder zwei Leerzeichen), deshalb großzügig.
_THH_ABSCHNITT = re.compile(r"Teil-?\s?Ergebnisrechnung\s+THH\s?(\d\d)\s*([^\n]{0,60})")


def parse_teilergebnisrechnungen(text: str, jahr: int) -> list[dict]:
    """Teil-Ergebnisrechnungen je Teilhaushalt aus dem Jahresabschluss.

    Liefert dieselben Posten wie ``parse_ergebnisrechnung``, zusätzlich mit
    ``thh_nr`` und ``thh_name`` — die Grundlage für „geplant gegen
    tatsächlich" je Bereich (Design H-16).

    Je Teilhaushalt stehen im Dokument mehrere Abschnitte (Ergebnis-, dann
    Finanzrechnung, dazu Fortsetzungsseiten). Genommen wird der erste, der
    beide Summenzeilen (12 und 20) liefert — so landet nie die Finanzrechnung
    in der Ergebnis-Tabelle."""
    treffer: dict[int, dict] = {}
    stellen = list(_THH_ABSCHNITT.finditer(text))
    for i, m in enumerate(stellen):
        thh_nr = int(m.group(1))
        if thh_nr in treffer:
            continue
        # Bis zum nächsten Abschnitt lesen, damit keine Werte des folgenden
        # Teilhaushalts hineinrutschen.
        ende = stellen[i + 1].start() if i + 1 < len(stellen) else m.end() + 9000
        posten = _posten_aus_block(text[m.end():ende], jahr)
        nummern = {p["nr"] for p in posten}
        if not {12, 20} <= nummern:
            continue  # kein vollständiger Ergebnis-Abschnitt
        name = re.sub(r"^\s*(THH\s?\d\d)?\s*", "", m.group(2)).strip(" -–—:")
        treffer[thh_nr] = {"thh_nr": thh_nr, "thh_name": name, "posten": posten}
    return list(treffer.values())


def summenprobe(teilhaushalte: list[dict], gesamt: list[dict],
                toleranz: float = 0.01) -> tuple[bool, float]:
    """Zweite Absicherung: Die Summe der Teilhaushalts-Ansätze muss der
    Gesamt-Ergebnisrechnung entsprechen.

    Nötig, weil die zeilenweise Prüfung (``Abweichung = Ergebnis − Ansatz``)
    einen Fall nicht fängt: Wird für einen Teilhaushalt versehentlich eine
    andere, in sich stimmige Tabelle gelesen, sind die Zahlen konsistent —
    aber falsch. Im Jahresabschluss 2022 wurde THH09 so mit 0,1 statt
    26,8 Mio. € gelesen; erst die Summe über alle Teilhaushalte machte es
    sichtbar (26,7 Mio. Differenz).

    Gibt ``(besteht, abweichung_anteil)`` zurück."""
    def summe(posten_liste, nr):
        return sum(next((p["ansatz"] for p in x["posten"] if p["nr"] == nr), 0) or 0
                   for x in posten_liste)
    ganz = next((p["ansatz"] for p in gesamt if p["nr"] == 20), None)
    if not ganz:
        return False, 1.0
    teil = summe(teilhaushalte, 20)
    anteil = abs(teil - ganz) / ganz
    return anteil <= toleranz, anteil


def _spalten_zuordnen(zahlen: list[float]) -> dict | None:
    """Zahlenfolge einer Tabellenzeile den Spalten zuordnen — validiert.

    Erwartete Reihenfolge (leere Spalten fehlen einfach):
    Vorjahr, Ansatz, [Nachtrag], Ergebnis, Abweichung, [Ermächtigung].
    Übernommen wird nur, wenn ``Abweichung ≈ Ergebnis − Ansatz`` gilt
    (1 Euro Toleranz für Rundungen)."""
    if len(zahlen) < 4:
        return None
    for versatz in (0, 1):  # mit/ohne führenden Vorjahreswert
        rest = zahlen[versatz:]
        if len(rest) < 3:
            continue
        vorjahr = zahlen[0] if versatz else None
        ansatz, ergebnis, abweichung = rest[0], rest[1], rest[2]
        if abs((ergebnis - ansatz) - abweichung) <= 1.0:
            return {"vorjahr": vorjahr, "ansatz": ansatz,
                    "ergebnis": ergebnis, "abweichung": abweichung}
    return None


# --- Teilhaushalte: Produktebene --------------------------------------------

_PRODUKT_KOPF = re.compile(
    r"Teilergebnishaushalt\s+THH(\d+):\s*([^\n]+?)\s*\n\s*"
    r"Produkt:\s*(.+?)\s*\((P[\d.]+)\)\s*\n\s*([^\n]+)")
#: Zahlen in den THH-Tabellen stehen teils ohne Nachkommastellen („484.239").
_THH_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")


def _thh_zahlen(zeile: str) -> list[float]:
    out = []
    for s in _THH_BETRAG.findall(zeile):
        if s in {"-", ""}:
            continue
        out.append(float(s.replace(".", "").replace(",", ".")))
    return out


# --- Teilhaushalte: Produkt-Steckbrief ---------------------------------------
#
# Zu jedem Produkt führen die Pläne einen Steckbrief: was die Aufgabe umfasst,
# auf welchem Gesetz sie beruht, wie viel Spielraum die Stadt bei ihr hat.
# Genau das beantwortet die häufigste Bürgerfrage zum Haushalt („was kostet
# eigentlich das Stadtarchiv?") — und belegt die Pflicht/Kür-Einordnung, statt
# sie zu schätzen.
#
# ZWEI FALLEN, beide beim Bauen aufgelaufen:
#
# 1. **Die Label stehen im extrahierten Text NACH ihrem Inhalt.** Im PDF sitzt
#    „Kurzbeschreibung:" als Spaltenüberschrift links neben dem Absatz; die
#    Textextraktion schiebt sie dahinter. Die Reihenfolge im Text ist also:
#    Absatz, dann `Kurzbeschreibung:`, dann der Rechtsgrundlagen-Absatz, dann
#    `Auftragsgrundlage:`. Wer vorwärts liest, bekommt jedes Feld um genau
#    eines verschoben — die Kurzbeschreibung wäre dann das Gesetz.
#    Kurze Werte passen im PDF neben ihr Label und stehen deshalb DAHINTER
#    („Grad der Beeinflussbarkeit: mittel"). Beide Fälle stehen unten
#    ausdrücklich als `rueckwaerts` markiert, statt sie zu erraten.
#
# 2. **Jede Leistung trägt einen eigenen Steckbrief.** Ein Produkt zerfällt in
#    Leistungen („Leistung: Interne Gleichstellungsarbeit (P10.111000.001)"),
#    und die haben dieselben Felder. Ungefiltert bekäme das Produkt den Text
#    einer beliebigen Unterposition. Deshalb wird der Produktblock vor der
#    ersten Leistungs-Überschrift abgeschnitten (in 661 von 664 Blöcken des
#    Bestands steht der Produkt-Steckbrief davor; in den übrigen bleiben die
#    Felder leer — lieber eine Lücke als ein fremder Text).

#: Felder, die wir übernehmen: (Spalte, Label-Regex, Inhalt steht davor?).
_STECKBRIEF_FELDER: tuple[tuple[str, str, bool], ...] = (
    ("kurzbeschreibung", r"Kurzbeschreibung", True),
    ("auftragsgrundlage", r"Auftragsgrundlage", True),
    ("beeinflussbarkeit_roh", r"Grad der Beeinflussbarkeit", False),
    ("wirkungskreis", r"Wirkungskreis", False),
    ("zielgruppe", r"Zielgruppe\(n\)", True),
)

#: Weitere Label des Steckbriefs. Wir lesen sie nicht, aber sie begrenzen die
#: rückwärts gelesenen Felder — ohne sie liefe die Zielgruppe bis in die
#: Kennzahlen-Tabelle.
_WEITERE_LABEL = (
    r"Ziel\(e\)", r"Kennzahl\(en\)", r"Maßnahme\(n\)", r"Erläuterung\(en\)",
    r"Grunddaten", r"Haushaltsvermerk\(e\)", r"Zuweisungen und Zuschüsse an Dritte",
    r"Leistungen", r"Das Produkt enthält [^\n:]{0,40}Leistungen", r"Projekte",
    r"Investitionen", r"Städtische Einrichtungen", r"Verantwortlich", r"Hinweis",
)

#: Alle Label als eine Alternative — Zeilenanfang, damit „… im eigenen
#: Wirkungskreis:" mitten im Fließtext keine Grenze zieht.
_LABEL = re.compile(
    r"^[ \t]*(" + "|".join([r for _, r, _ in _STECKBRIEF_FELDER] + list(_WEITERE_LABEL))
    + r"):", re.M)

#: Zeilen, die kein Fließtext sind: Tabellenkopf der Grunddaten/Kennzahlen,
#: Tabellenzeile (endet auf mehreren Zahlen), nacktes Einheiten-Kürzel,
#: Seitenzahl.
_KEIN_FLIESSTEXT = re.compile(
    r"^\s*(?:\d{1,4}"                                  # Seitenzahl
    r"|(?:PRS|ST|EUR|VZÄ|%|Anzahl)"                    # nacktes Einheiten-Kürzel
    r"|.*\bEinheit\b.*(?:Ist|Plan)\s+20\d\d.*"         # Tabellenkopf
    r"|.*?(?:\s-?[\d.,]+){2,}"                         # Tabellenzeile
    r")\s*$")

#: Erste Zeile eines wiederholten Seitenkopfs. Der Kopf ist mehrzeilig
#: (Teilergebnishaushalt · Produkt · [Leistung ·] Amt) und muss als Einheit
#: fallen: Die Amtszeile allein sieht aus wie Fließtext und stand sonst vorn
#: in der Zielgruppe („Amt für Umweltschutz und Bauordnung Verwaltung und
#: Politik sowie alle …").
_KOPFZEILE = re.compile(r"^\s*Teilergebnishaushalt\b")


def _ohne_seitenkopf(zeilen: list[str]) -> list[str]:
    """Wiederholte Seitenköpfe aus einem Steckbrief-Abschnitt entfernen."""
    out: list[str] = []
    i = 0
    while i < len(zeilen):
        if not _KOPFZEILE.match(zeilen[i]):
            out.append(zeilen[i])
            i += 1
            continue
        i += 1  # „Teilergebnishaushalt THH…"
        for muster in (r"^\s*Produkt:", r"^\s*Leistung:"):
            if i < len(zeilen) and re.match(muster, zeilen[i]):
                i += 1
        if i < len(zeilen) and zeilen[i].strip():
            i += 1  # die Amtszeile
    return out

#: Überschrift einer Leistung — die Grenze des Produkt-Steckbriefs.
_LEISTUNG_KOPF = re.compile(r"^[ \t]*Leistung:[^\n]*\(P[\d.]+\.\d+\)[ \t]*$", re.M)

#: Die Stadt schreibt denselben Spielraum mal „niedrig", mal „gering" — und
#: mal groß. Wir vereinheitlichen für Filter und Vergleich, behalten den
#: Rohwert aber in `beeinflussbarkeit_roh`: Was im Plan steht, bleibt
#: nachlesbar, auch wenn wir es anders einsortieren.
_BEEINFLUSSBARKEIT = {
    "niedrig": "niedrig", "gering": "niedrig",
    "mittel": "mittel", "hoch": "hoch",
}


def normalisiere_beeinflussbarkeit(roh: str | None) -> str | None:
    """„gering"/„Niedrig"/„niedrig" → ``"niedrig"``; Unbekanntes → ``None``.

    Bewusst streng: Mischformen („niedrig - mittel") bekommen keine der drei
    Stufen zugewiesen, weil jede Wahl eine Behauptung wäre. Sie bleiben über
    den Rohwert sichtbar."""
    if not roh:
        return None
    return _BEEINFLUSSBARKEIT.get(roh.strip().strip(".").lower())


def _saeubern(roh: str) -> str | None:
    """Absatz aus dem PDF-Text zu einem lesbaren Satz zusammenziehen.

    Der Text ist an der Satzbreite umbrochen, nicht am Satzende — Zeilenumbrüche
    sind hier also Layout, keine Bedeutung und werden zu Leerzeichen.

    Vom Ende her gelesen: Der gesuchte Absatz steht unmittelbar VOR seinem
    Label; was davor liegt, kann eine Tabelle sein. Zwischen „Wirkungskreis:"
    und „Zielgruppe(n):" steht bei einigen Produkten die ganze Grunddaten-
    Tabelle („Einheit · Ist 2021 · Plan 2022 …", Zeilen wie „PRS 3,46 3,44 …"),
    weil deren Label ausnahmsweise VOR seinem Inhalt steht. Ungefiltert stand
    diese Zahlenwüste als „Zielgruppe" auf der Seite. Deshalb wird nur der
    zusammenhängende Fließtext-Block am Ende übernommen."""
    absatz: list[str] = []
    for zeile in reversed(_ohne_seitenkopf(roh.split("\n"))):
        if not zeile.strip():
            continue
        if _KEIN_FLIESSTEXT.match(zeile):
            break
        absatz.append(zeile)
    text = re.sub(r"\s+", " ", " ".join(reversed(absatz))).strip(" -–—·\t")
    # Zu kurz ist kein Inhalt (etwa ein übrig gebliebener Doppelpunkt), zu lang
    # heißt: Ein Label fehlte und wir haben doch eine Tabelle mitgelesen.
    if not (3 <= len(text) <= 2000):
        return None
    return text


def _steckbrief(block: str) -> dict[str, str | None]:
    """Steckbrief-Felder eines Produktblocks lesen.

    ``block`` reicht vom Produktkopf bis zum Kopf des NÄCHSTEN Produkts. Alles
    ab der ersten Leistungs-Überschrift wird verworfen (Falle 2 oben)."""
    leistung = _LEISTUNG_KOPF.search(block)
    stamm = block[:leistung.start()] if leistung else block

    marken = list(_LABEL.finditer(stamm))
    out: dict[str, str | None] = {name: None for name, _, _ in _STECKBRIEF_FELDER}
    for i, m in enumerate(marken):
        name, rueckwaerts = next(
            ((n, r) for n, muster, r in _STECKBRIEF_FELDER
             if re.fullmatch(muster, m.group(1))), (None, None))
        if name is None or out[name] is not None:
            continue  # unbekanntes Label oder Wiederholung (erster Treffer gilt)
        if rueckwaerts:
            # Inhalt steht VOR dem Label: vom Ende der vorigen Marke bis hierher.
            # Ohne vorige Marke ab Blockanfang — dann steht der Seitenkopf davor,
            # den `_saeubern` entfernt.
            #
            # Und zwar ab dem ZEILENENDE der vorigen Marke, nicht ab dem Label:
            # Trägt die vorige Marke ihren Wert auf derselben Zeile
            # („Verantwortlich: Leitung des Gleichstellungsbüros"), rutscht er
            # sonst vorn in dieses Feld — jede Kurzbeschreibung begänne mit dem
            # Namen der Amtsleitung, jede Zielgruppe mit dem Wirkungskreis.
            beginn = 0
            if i:
                zeilenende = stamm.find("\n", marken[i - 1].end())
                beginn = zeilenende + 1 if zeilenende >= 0 else marken[i - 1].end()
            out[name] = _saeubern(stamm[beginn:m.start()])
        else:
            # Inhalt steht hinter dem Doppelpunkt, auf DERSELBEN Zeile: Ein
            # Umbruch bedeutet hier, dass der Wert fehlt — die nächste Zeile
            # gehört schon zum nächsten Feld.
            zeile = stamm[m.end():].split("\n", 1)[0]
            out[name] = _saeubern(zeile)
    return out


def parse_teilergebnishaushalt(text: str) -> list[dict]:
    """Produkte eines Teilhaushalts-Plans → je Produkt ein dict mit
    ``{thh_nr, thh_name, produkt_nr, produkt_name, amt, jahr, ertraege,
    aufwendungen, ergebnis}`` für das **Haushaltsjahr** des Dokuments — das
    ist der ERSTE Ansatz im Tabellenkopf; die weiteren Spalten sind die
    mittelfristige Finanzplanung und keine beschlossenen Ansätze.

    Dazu der Steckbrief des Produkts (``kurzbeschreibung``,
    ``auftragsgrundlage``, ``beeinflussbarkeit`` + ``beeinflussbarkeit_roh``,
    ``wirkungskreis``, ``zielgruppe``), soweit der Plan ihn führt — fehlende
    Felder bleiben ``None``, nichts wird vom Nachbarprodukt übernommen.
    Zu den beiden Fallen dabei siehe den Abschnitt „Produkt-Steckbrief" oben.

    Nur die Summenzeilen (12/20/21) werden gelesen: Die Einzelposten sind im
    PDF-Text oft verschmolzen („355.188334.704“). Die Zahl der Wertespalten
    kommt aus dem Tabellenkopf („Ergebnis 2018 · Ansatz 2019 … Ansatz 2023“) —
    blind die letzte Zahl zu nehmen ginge schief, weil hinter der
    Ergebniszeile die Seitenzahl klebt („−451.635\n601“).

    Übernommen wird ein Produkt nur, wenn ``Erträge − Aufwendungen =
    ordentliches Ergebnis`` aufgeht."""
    koepfe = list(_PRODUKT_KOPF.finditer(text))
    gefunden: dict[str, dict] = {}
    for i, m in enumerate(koepfe):
        thh_nr, thh_name, produkt_name, produkt_nr, amt = m.groups()
        if produkt_nr in gefunden:
            continue  # Fortsetzungsseite desselben Produkts
        # Nur bis zum nächsten Produkt-Kopf lesen: Fehlt einem Produkt die
        # Summenzeile, würden sonst die Werte des FOLGENDEN Produkts gelesen —
        # zwei Produkte trügen dieselben Zahlen (aufgefallen bei „Soziale
        # Beratung" und „Grundsicherung für Arbeitsuchende", beide 54,0 Mio.).
        naechster = koepfe[i + 1] if i + 1 < len(koepfe) else None
        block = text[m.end():naechster.start() if naechster else m.end() + 4000]

        # Der Steckbrief steht ein paar Seiten weiter, hinter den Fortsetzungs-
        # köpfen DESSELBEN Produkts — sein Block reicht deshalb bis zum ersten
        # Kopf eines ANDEREN Produkts. Dieselbe Grenzziehung wie oben, nur eine
        # Ebene weiter: Wer hier am nächstbesten Kopf abschneidet, findet den
        # Steckbrief nie; wer gar nicht abschneidet, holt den des Nachbarn.
        fremd = next((k for k in koepfe[i + 1:] if k.group(4) != produkt_nr), None)
        steckbrief = _steckbrief(text[m.end():fremd.start() if fremd else len(text)])

        # Spalten aus dem Kopf: „Ergebnis JJJJ“ + n × „Ansatz JJJJ“.
        # Das HAUSHALTSJAHR ist der ERSTE Ansatz — die weiteren Spalten sind
        # die mittelfristige Finanzplanung (bis +4 Jahre). Die letzte Spalte
        # zu nehmen hieße, Finanzplanungswerte als Haushaltsansatz auszugeben.
        kopf = re.findall(r"(Ergebnis|Ansatz)\s+(20\d\d)", block[:600])
        jahre = [int(j) for _, j in kopf]
        if len(jahre) < 2:
            continue
        spalten = len(jahre)
        ansatz_idx = next((i for i, (art, _) in enumerate(kopf) if art == "Ansatz"), None)
        if ansatz_idx is None:
            continue

        werte = {}
        for schluessel, muster in (
            ("ertraege", r"12\.\s*=?\s*Summe ordentliche\s*Erträge([^\n]*(?:\n[^\n]*)?)"),
            ("aufwendungen", r"20\.\s*=?\s*Summe ordentliche\s*Aufwendungen([^\n]*(?:\n[^\n]*)?)"),
            ("ergebnis", r"21\.\s*ordentliches Ergebnis([^\n]*(?:\n[^\n]*)?)"),
        ):
            mm = re.search(muster, block)
            if not mm:
                continue
            zahlen = _thh_zahlen(mm.group(1))
            # Genau so viele Werte wie Spalten — alles danach ist Seitenzahl.
            if len(zahlen) < spalten:
                continue
            werte[schluessel] = zahlen[ansatz_idx]
        if len(werte) < 3:
            continue
        # Prüfsumme des Dokuments: Erträge − Aufwendungen = Ergebnis.
        if abs((werte["ertraege"] - werte["aufwendungen"]) - werte["ergebnis"]) > 1.0:
            continue
        gefunden[produkt_nr] = {
            "thh_nr": int(thh_nr), "thh_name": thh_name.strip(),
            "produkt_nr": produkt_nr, "produkt_name": produkt_name.strip(),
            "amt": amt.strip(), "jahr": jahre[ansatz_idx], **werte,
            **steckbrief,
            "beeinflussbarkeit": normalisiere_beeinflussbarkeit(
                steckbrief["beeinflussbarkeit_roh"]),
        }
    return list(gefunden.values())
