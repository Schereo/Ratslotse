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


def parse_teilergebnishaushalt(text: str) -> list[dict]:
    """Produkte eines Teilhaushalts-Plans → je Produkt ein dict mit
    ``{thh_nr, thh_name, produkt_nr, produkt_name, amt, jahr, ertraege,
    aufwendungen, ergebnis}`` für das **Haushaltsjahr** des Dokuments — das
    ist der ERSTE Ansatz im Tabellenkopf; die weiteren Spalten sind die
    mittelfristige Finanzplanung und keine beschlossenen Ansätze.

    Nur die Summenzeilen (12/20/21) werden gelesen: Die Einzelposten sind im
    PDF-Text oft verschmolzen („355.188334.704“). Die Zahl der Wertespalten
    kommt aus dem Tabellenkopf („Ergebnis 2018 · Ansatz 2019 … Ansatz 2023“) —
    blind die letzte Zahl zu nehmen ginge schief, weil hinter der
    Ergebniszeile die Seitenzahl klebt („−451.635\n601“).

    Übernommen wird ein Produkt nur, wenn ``Erträge − Aufwendungen =
    ordentliches Ergebnis`` aufgeht."""
    gefunden: dict[str, dict] = {}
    for m in _PRODUKT_KOPF.finditer(text):
        thh_nr, thh_name, produkt_name, produkt_nr, amt = m.groups()
        if produkt_nr in gefunden:
            continue  # Fortsetzungsseite desselben Produkts
        # Nur bis zum nächsten Produkt-Kopf lesen: Fehlt einem Produkt die
        # Summenzeile, würden sonst die Werte des FOLGENDEN Produkts gelesen —
        # zwei Produkte trügen dieselben Zahlen (aufgefallen bei „Soziale
        # Beratung" und „Grundsicherung für Arbeitsuchende", beide 54,0 Mio.).
        naechster = _PRODUKT_KOPF.search(text, m.end())
        block = text[m.end():naechster.start() if naechster else m.end() + 4000]

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
        }
    return list(gefunden.values())
