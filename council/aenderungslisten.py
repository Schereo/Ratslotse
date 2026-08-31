"""Die Änderungslisten zum Haushalt — der Inhalt, den der Streit bisher nicht hatte.

Die Streit-Seite (/haushalt/mitreden#streit) sagt seit jeher ehrlich: Welche
Position eine Liste um welchen Betrag verschieben wollte, „steht in den
Anlagen-PDFs der Vorlage". Dieses Modul liest genau diese PDFs.

DIE FUNDLAGE, GEMESSEN AM 24.08.2026 — sie begrenzt, was hier je stehen kann:

* **Die Fraktions-Änderungslisten sind nicht im RIS.** Die Listen der
  Fraktionen (Grüne, BSW, Für Oldenburg, die Koalitionsliste SPD/CDU/FDP)
  tauchen im Protokoll als Abstimmungen auf, aber weder an der
  Haushalts-Vorlage noch an den Sitzungen (Rat 09.02.2026 = ksinr 4726,
  AFB 04.02.2026 = ksinr 4635 — beide Seiten geprüft) hängt ein Dokument
  dazu: Tischvorlagen. Was es je Jahrgang GIBT, sind die Änderungslisten
  **der Verwaltung** (Verw. I/II/III — die Fortschreibungen des Entwurfs im
  Verfahren, z. B. nach der November-Steuerschätzung) und die Datei
  „beschlossene Änderungen AFB". Wer Fraktions-Positionen zeigen will,
  braucht eine andere Quelle — nicht ein besseres Parsing.
* **Nur der Ergebnishaushalt (EHH).** Die FHH-Listen (Finanzhaushalt) tragen
  eine andere Bauform (Investitionszeilen mit Jahresspalten), die
  EGH-Dateien gehören dem Eigenbetrieb Gebäudewirtschaft, die
  Stiftungs-Listen den Stiftungshaushalten. Alle drei bleiben hier bewusst
  draußen; `liste_aus_label` sortiert sie aus.

Die Bauform (an allen 18 EHH-Dokumenten der Jahrgänge 2019–2026 bewiesen)
--------------------------------------------------------------------------
Querformat-Tabellen: ``Lfd. Nr. | THH | Seite im HH-Entwurf | Produkt/
Leistung | Bezeichnung | Ertrag +/− | Aufwand +/− | Erläuterungen``, in
Abschnitten je Planjahr („Änderungen 2026" … „Änderungen 2029"), am Ende eine
„Zusammenstellung der Veränderungen" je Planjahr mit Verwaltungsentwurf,
jeder Änderungsliste und dem Überschuss/Fehlbedarf. Varianten, die der
Bestand wirklich führt: „Verw.-Entwurf v. …" und nackte Jahres-Überschriften
(frühe AFB-Übersichten), ein Block nur mit „Stand: …" (244160), THH „alle"
(2019), Bezeichnungen über mehrere Grundlinien gewickelt (die Nachlese holt
sie zurück; ~1 % bleibt lieber leer als falsch zugeordnet).

WAS DIE AFB-DATEIEN ZUSÄTZLICH TRAGEN: die POLITISCH beschlossene Änderung
als eigene Zusammenstellungs-Zeile mit Urheber-Label — „SPD/CDU/FDP
0 / −218.299" (2026), „SPD/ BÜNDNIS 90/DIE GRÜNEN" (2021). Die Salden der
Koalitions-Änderungslisten stehen damit doch im Bestand, obwohl die Listen
selbst Tischvorlagen blieben.

Warum Wort-Koordinaten statt Textextraktion
-------------------------------------------
Beides wurde gebaut und gemessen, bevor diese Fassung blieb: Der
pypdf-Fließtext zerreißt Zahlen („13.9 69.144") und verliert die Spalten
ganz. Der Layout-Modus behält beides — staucht aber einspaltige Zeilen
gelegentlich so, dass ein Aufwand AUF der Ertrag-Spalte landet (gemessen in
300528: Position 25 endet auf derselben Zeichenspalte wie zwei echte Erträge
daneben), und ein Summen-Abgleich, der das heilen wollte, war bei runden
Beträgen mehrdeutig. Erst die ECHTEN Wortkoordinaten (pymupdf, nach
Derotation der Querformat-Seiten) trennen sicher: Ertrags-Beträge enden bei
x ≈ 407–415, Aufwands-Beträge bei ≈ 446–473, die Erläuterung beginnt bei
≈ 480 — dazwischen liegen ganze Spaltenbreiten, keine Toleranzfenster.

``pymupdf`` ist dafür Voraussetzung und bewusst KEINE Abhängigkeit in
``requirements.txt`` — dieselbe Entscheidung wie bei den PDF-Renderern der
OCR (council/ocr.py): Deploy und Web-Service bleiben unberührt, die
Ingest-Maschine installiert sich das Paket einmal von Hand.

Die Proben — ohne sie wird nichts gespeichert
---------------------------------------------
1. **Zeilenprobe** je Summenzeile: Erträge − Aufwendungen = Saldo (±2 Euro
   Rundung; die Dokumente runden selbst — Verw. I trägt 2026 in zwei
   Dateien 16.629.632 bzw. 16.629.633).
2. **Kettenprobe** je Planjahr: Verwaltungsentwurf + alle Listen =
   Überschuss/Fehlbedarf, je Spalte.
3. **Positionsprobe** je Planjahr: Die Summe der gelesenen Positionen muss
   GENAU EINE Zusammenstellungs-Zeile treffen (das ist dann „die eigene"
   Liste des Dokuments) — oder, bei den kumulierten Beschluss-Dateien, die
   Summe aller Zeilen. Weist eine Zusammenstellung ihre Endsumme nicht
   vollständig in Zeilen aus (Kettenprobe reißt), tritt an ihre Stelle die
   härtere Referenz „Endsumme − Entwurf". Diese Probe ist der Wächter über
   die Spaltenzuordnung: Stünde ein Betrag auf der falschen Seite, ginge
   sie nicht auf.

Die ERLÄUTERUNGS-Spalte (seit 26.08.2026) hat keine Schlusssumme, gegen die
man Text beweisen könnte — an die Stelle der Rechenprobe tritt Geometrie:
Alle Dokumente zeichnen ihre Tabellen als echtes Linienraster, und die
waagerechten Linien machen die Zuordnung der mehrzeilig gewickelten Texte
zur Zeile eindeutig (:func:`_erlaeuterungen_anbauen`). Ohne Linien bleibt
das Feld leer statt geraten.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from council.herkunft import Herkunft

# --------------------------------------------------------------- Label-Sortierung

#: Was dieses Modul liest: EHH-Änderungslisten des Kernhaushalts.
_LABEL_EHH = re.compile(r"EHH|Ergebnishaushalt", re.I)
#: Was bewusst draußen bleibt: andere Bauform (FHH mit Jahresspalten) oder
#: anderer Haushalt (Eigenbetrieb Gebäudewirtschaft EGH, Bäderbetrieb BBO,
#: Wirtschaftsförderung WFO, die beiden Stiftungen). Die Labels helfen dabei
#: nicht immer — „EGH - Ergebnishaushalt, beschlossene Änderungen“ trägt
#: beide Wörter; deshalb schlägt RAUS vor EHH.
_LABEL_RAUS = re.compile(
    r"EGH|FHH|Finanzhaushalt|Erfolgsplan|Vermögensplan|Stiftung|Synopse"
    r"|\bBBO\b|\bWFO\b", re.I)
#: „Verwaltung I“ (2022–2026), „Verw. I“ (2019–2021), vereinzelt „Verwaltung 1“.
_LABEL_VERW = re.compile(r"Verw(?:altung|\.)\s*(III|II|I|[123])\b", re.I)
_LABEL_AFB = re.compile(r"beschlossene\s+Änderungen", re.I)

_ROEMISCH = {"I": 1, "II": 2, "III": 3, "1": 1, "2": 2, "3": 3}


def liste_aus_label(label: str | None) -> str | None:
    """Anlagen-Label → Listen-Schlüssel, oder ``None`` für „gehört nicht her“.

    ``administration_1``/``_2``/``_3`` für die Verwaltungslisten,
    ``fc_decided`` für die kumulierte Beschluss-Datei des
    Finanzausschusses. Die Reihenfolge der Prüfungen ist die Sortierung:
    Erst raus, was sicher nicht gemeint ist — „2026 FHH Änderungsliste
    Verwaltung I“ enthält schließlich auch „Verwaltung I“.
    """
    t = label or ""
    if _LABEL_RAUS.search(t):
        return None
    if _LABEL_AFB.search(t) and _LABEL_EHH.search(t):
        return "fc_decided"
    m = _LABEL_VERW.search(t)
    if m and _LABEL_EHH.search(t) and "nderungsliste" in t:
        return f"administration_{_ROEMISCH[m.group(1).upper()]}"
    return None


class ListenFehler(ValueError):
    """Eine Liste, die ihre eigenen Proben nicht besteht, wird nicht gelesen."""


# ------------------------------------------------------------------- Datenformen

#: Ein Wort mit seiner Lage auf der (derotierten) Seite: x0, x1, y, Text.
#: Als nacktes Tupel, damit Test-Fixtures es als JSON führen können.
Wort = tuple[float, float, float, str]


@dataclass
class Zeile:
    """Eine Position einer Änderungsliste — ein Planjahr, eine Zeile."""

    year: int
    seq: int
    #: ``None`` = die Position gilt pauschal „alle“ Teilhaushalte — so führt
    #: der 2019er-Jahrgang globale Minderausgaben (Zeilen 16/17, je „diverse“
    #: Produkte, zusammen −3,35 Mio. € Aufwand).
    sub_budget: int | None
    page_draft: int | None
    product: str | None
    label: str
    #: Euro, negativ = Minderung. ``None`` = Zeile ohne Betrag in dieser
    #: Spalte (auch beides ``None`` kommt vor: reine Haushaltsvermerke).
    revenue: int | None
    expense: int | None
    #: Der Text der Erläuterungs-Spalte — was diese Änderung IST („VWG: Der
    #: Entwurf des Wirtschaftsplans 2026 weist einen Zuschussbedarf …“).
    #: ``None``, wenn die Zelle leer ist oder ihre Zuordnung nicht eindeutig
    #: über die Tabellenlinien läuft (s. ``_erlaeuterungen_anbauen``).
    explanation: str | None = None
    #: WER diese Position vorgeschlagen hat — aus der Spalte „Vorschlag von“.
    #: ``None`` überall dort, wo das Dokument die Spalte nicht führt (17 von
    #: 18 EHH-Dokumenten); s. ``_urheber_anbauen``.
    author: str | None = None


@dataclass
class SummenZeile:
    """Eine Zeile der Zusammenstellung: Entwurf, eine Liste oder die Endsumme."""

    year: int
    typ: str  # "draft" | "list" | "final_total"
    label: str
    revenues: int
    expenses: int
    balance: int


@dataclass
class Ergebnis:
    zeilen: list[Zeile] = field(default_factory=list)
    summen: list[SummenZeile] = field(default_factory=list)
    #: Je Planjahr das Label der Zusammenstellungs-Zeile, die die eigenen
    #: Positionen summiert — oder "alle", wenn das Dokument kumuliert.
    eigene_zeile: dict[int, str] = field(default_factory=dict)
    #: „Stand: 24.11.2025“ vom Deckblatt, wenn vorhanden.
    as_of: str | None = None

    @property
    def budget_year(self) -> int:
        """Der Haushaltsjahrgang = das erste Planjahr der Liste."""
        return min(z.year for z in self.zeilen)


# ----------------------------------------------------------------- PDF → Wörter

def seiten_woerter(pdf_bytes: bytes) -> list[list[Wort]]:
    """Je Seite die Wörter mit derotierten Koordinaten.

    Die Tabellen stehen im Querformat (``/Rotate 90``); ``get_text("words")``
    liefert Koordinaten aber im UNROTIERTEN Seitenraum — dort ist die
    Leserichtung die y-Achse. Die ``rotation_matrix`` der Seite dreht jede
    Wortbox in den angezeigten Raum, danach ist x wieder „links → rechts“.
    """
    try:
        import pymupdf  # noqa: PLC0415 — bewusst optional, s. Modulkopf
    except ImportError as e:  # pragma: no cover — auf Maschinen mit Paket unerreichbar
        raise ListenFehler(
            "pymupdf fehlt — die Spaltenzuordnung braucht Wortkoordinaten. "
            "Einmalig installieren: .venv/bin/pip install pymupdf"
        ) from e

    aus: list[list[Wort]] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            mat = page.rotation_matrix
            woerter: list[Wort] = []
            for w in page.get_text("words"):
                r = pymupdf.Rect(w[:4]) * mat
                woerter.append((round(r.x0, 1), round(r.x1, 1),
                                round(r.y0, 1), w[4]))
            aus.append(woerter)
    return aus


#: Je Seite die Tabellenlinien: (waagerechte y-Werte, senkrechte x-Werte).
Linien = tuple[list[float], list[float]]


def seiten_linien(pdf_bytes: bytes) -> list[Linien]:
    """Je Seite die gezeichneten Tabellenlinien, derotiert wie die Wörter.

    Alle 19 EHH-Dokumente 2019–2026 zeichnen ihre Tabellen als echtes
    Linienraster (gemessen: 11–17 waagerechte, 18 senkrechte Strecken je
    Tabellenseite). Die waagerechten Linien sind die Zeilengrenzen — sie
    machen die Zuordnung der mehrzeiligen Erläuterungs-Texte zur richtigen
    Position zur Geometrie statt zum Abstands-Raten. Linien kommen teils als
    ``l``-Strecken, teils als hauchdünne ``re``-Rechtecke (beide Kanten
    einer 1-pt-Linie); ``_linien_buendeln`` legt die Doppel zusammen.
    """
    import pymupdf  # noqa: PLC0415 — bewusst optional, s. Modulkopf

    aus: list[Linien] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            mat = page.rotation_matrix
            waagerecht: list[float] = []
            senkrecht: list[float] = []
            for zug in page.get_drawings():
                for item in zug["items"]:
                    if item[0] == "l":
                        p1, p2 = item[1] * mat, item[2] * mat
                        if abs(p1.y - p2.y) <= 0.5 and abs(p1.x - p2.x) > 20:
                            waagerecht.append((p1.y + p2.y) / 2)
                        elif abs(p1.x - p2.x) <= 0.5 and abs(p1.y - p2.y) > 20:
                            senkrecht.append((p1.x + p2.x) / 2)
                    elif item[0] == "re":
                        r = item[1] * mat
                        if r.height <= 1.5 and r.width > 20:
                            waagerecht.append((r.y0 + r.y1) / 2)
                        elif r.width <= 1.5 and r.height > 20:
                            senkrecht.append((r.x0 + r.x1) / 2)
            aus.append((_linien_buendeln(waagerecht), _linien_buendeln(senkrecht)))
    return aus


def _linien_buendeln(werte: list[float]) -> list[float]:
    """Nahezu deckungsgleiche Linien (≤ 2 pt) auf einen Wert zusammenlegen."""
    aus: list[float] = []
    for w in sorted(werte):
        if aus and w - aus[-1] <= 2:
            continue
        aus.append(w)
    return aus


def _zeilen_bilden(woerter: list[Wort]) -> list[list[Wort]]:
    """Wörter → visuelle Zeilen: nach y gruppiert, in der Zeile nach x.

    Alle Zellen einer Tabellenzeile teilen ihre Grundlinie auf ein Zehntel
    (gemessen); die Toleranz von 2,5 pt fängt Hoch-/Tiefstellungen. Die
    mehrzeiligen Erläuterungs-Absätze haben eigene Grundlinien und werden so
    von selbst zu eigenen Zeilen — die der Positions-Parser dann ignoriert.
    """
    zeilen: list[list[Wort]] = []
    for w in sorted(woerter, key=lambda w: (w[2], w[0])):
        if zeilen and abs(w[2] - zeilen[-1][0][2]) <= 2.5:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    for z in zeilen:
        z.sort(key=lambda w: w[0])
    return zeilen


def _zeilentext(row: list[Wort]) -> str:
    return " ".join(w[3] for w in row)


# ---------------------------------------------------------------------- Parsing

_STAND = re.compile(r"Stand:\s*([\d.]+)")
_JAHR_MARKER = re.compile(r"Änderungen\s+(20\d\d)")
_BLOCK_JAHR = re.compile(r"Ergebnishaushalt\s+(20\d\d)")
_ZAHL = re.compile(r"-?\d{1,3}(?:\.\d{3})+|-?\d+")
#: Produkt-/Leistungs-Codes: „P10.111011.003“, auch „I10.090126“.
_PRODUKT = re.compile(r"^[A-Z]\d[\w.]*$")
#: Drei Schreibweisen für dieselbe Zeile: „Verwaltungsentwurf, Stand: …“
#: (Normalfall), „Verw.-Entwurf v. 07.10.2020“ (die frühen AFB-Übersichten)
#: und nur „Stand: 07.02.2022 …“ (der 2023er-Block in 244160). Der Anker ^
#: ist gefahrlos: Geprüft werden ohnehin nur Zeilen mit drei Beträgen, das
#: Deckblatt-„Stand:“ hat keine.
_ENTWURF = re.compile(r"Verwaltungsentwurf|Verw\.-Entwurf|^Stand:")
_LISTE = re.compile(r"Änderungsliste")
_ENDSUMME = re.compile(r"Überschuss\s*/?\s*Fehlbedarf")


@dataclass(frozen=True)
class Spalten:
    """Die gemessenen Betragsspalten einer Tabellenseite.

    Aus den Kopf-Wörtern „Ertrag“ und „Aufwand“ (ihren x-Mitten). Beträge
    sind rechtsbündig und enden gemessen bis 31 pt neben ihrer Kopfmitte
    (302944: 1.500.000 endet bei Kopf + 30,4); die Erläuterungs-Spalte
    beginnt frühestens 33 pt dahinter, und ihre kürzeste gepunktete Zahl
    endete nie vor Kopf + 55. Der Puffer von 35 liegt zwischen beiden
    Messreihen. Eine ZONE um die Köpfe statt einer Grenze zur
    Erläuterungs-Spalte, weil deren zentrierter KOPF je Seite um über
    100 pt wandert („Zuschussbedarf von 1.422.430 Euro“ war der Fall, den
    eine Kopf-Grenze fraß). Reißt ein künftiges Dokument die Messreihen,
    reißt die Positionsprobe — leiser Drift ist ausgeschlossen.
    """

    revenue: float   # x-Mitte des Kopfs „Ertrag“
    expense: float  # x-Mitte des Kopfs „Aufwand“
    #: Linke Kante des Kopfworts „Bezeichnung“ — für die Fragment-Nachlese
    #: mehrzeiliger Bezeichnungen. ``None``, wenn der Kopf fehlt.
    label: float | None = None
    #: Die GEZEICHNETE Bezeichnungs-Spalte (linke/rechte senkrechte Linie um
    #: den Kopf). Wo die Seite ihr Raster zeichnet, gilt es statt der aus dem
    #: Kopfwort geschätzten Zone — s. :func:`_bezeichnungsfragment`.
    bez_spalte: tuple[float, float] | None = None

    @property
    def mitte(self) -> float:
        return (self.revenue + self.expense) / 2

    @property
    def zone(self) -> tuple[float, float]:
        """(links, rechts): Wo Beträge ENDEN dürfen."""
        return (self.revenue - 35, self.expense + 35)


def _spalten(zeilen: list[list[Wort]],
             senkrecht: list[float] | None = None) -> Spalten | None:
    """Die Betragsspalten aus den Kopf-Wörtern „Ertrag“ und „Aufwand“.
    Fehlen sie, ist es keine Tabellenseite (Deckblatt, Zusammenstellung —
    dort heißen die Spalten „Erträge“/„Aufwendungen“).

    ``senkrecht`` (die gezeichneten Spaltenlinien der Seite) ist optional und
    trägt nur die Bezeichnungs-Spalte bei — das Linienpaar, das den Kopf
    „Bezeichnung“ einschließt.
    """
    revenue = expense = label = None
    for row in zeilen[:14]:
        for x0, x1, _y, text in row:
            if text == "Ertrag" and revenue is None:
                revenue = (x0 + x1) / 2
            elif text == "Aufwand" and expense is None:
                expense = (x0 + x1) / 2
            elif text == "Bezeichnung" and label is None:
                label = x0
    if revenue is None or expense is None:
        return None
    spalte = None
    if senkrecht and label is not None:
        links = [x for x in senkrecht if x < label]
        rechts = [x for x in senkrecht if x > label]
        if links and rechts:
            spalte = (max(links), min(rechts))
    return Spalten(revenue=revenue, expense=expense, label=label,
                   bez_spalte=spalte)


def _zahl(text: str) -> int:
    return int(text.replace(".", ""))


def _position_lesen(row: list[Wort], year: int, spalten: Spalten) -> Zeile:
    seq = int(row[0][3])
    sub_budget = int(row[1][3]) if row[1][3] != "alle" else None

    page_draft: int | None = None
    product: str | None = None
    label: list[str] = []
    revenue: int | None = None
    expense: int | None = None

    zone_links, zone_rechts = spalten.zone
    for x0, x1, _y, text in row[2:]:
        if re.fullmatch(_ZAHL, text):
            if zone_links <= x1 <= zone_rechts:
                # Ein Betrag — rechtsbündig in seiner Spalte, die Seite der
                # Mitte entscheidet. Auch ungepunktet: „-470“ ist ein echter
                # Aufwand aus 300528 (Beträge unter 1.000 Euro gibt es).
                if x1 <= spalten.mitte:
                    revenue = _zahl(text) if revenue is None else revenue
                elif expense is None:
                    expense = _zahl(text)
                continue
            if x1 > zone_rechts:
                break  # Zahl in der Erläuterung — dahinter kommt nichts mehr
            # Kleine Zahl vor der Bezeichnung: die Seite im HH-Entwurf.
            if (text.isdigit() and page_draft is None
                    and not label and product is None):
                page_draft = int(text)
            continue
        if x0 > spalten.mitte:
            break  # erster Text rechts der Mitte: die Erläuterung beginnt
        if _PRODUKT.match(text) and not label and product is None:
            product = text
            continue
        label.append(text)

    return Zeile(year=year, seq=seq, sub_budget=sub_budget, page_draft=page_draft,
                 product=product, label=" ".join(label),
                 revenue=revenue, expense=expense)


def _ist_position(row: list[Wort], spalten: Spalten | None) -> bool:
    """Positionszeilen beginnen mit Lfd. Nr. und zweistelligem THH — und
    zwar am linken Tabellenrand, nicht mitten in einer Erläuterung."""
    return (spalten is not None and len(row) >= 3
            and re.fullmatch(r"\d{1,3}", row[0][3]) is not None
            and (re.fullmatch(r"\d{2}", row[1][3]) is not None
                 or row[1][3] == "alle")
            and row[0][0] < spalten.mitte / 2)


def _bezeichnungsfragment(row: list[Wort], spalten: Spalten) -> str | None:
    """Der Bezeichnungs-Anteil einer Wickelzeile — oder ``None``.

    Lange Bezeichnungen wickeln auf eigene Grundlinien; die Positionszeile
    selbst trägt dann nur Nummern und Beträge (14 % der Zeilen im ersten
    Vollbestand standen so ohne Namen da). Auf derselben Grundlinie darf
    dabei ERLÄUTERUNGS-Text weiterlaufen (212801: „Verbraucherschutz und |
    Lebensmittelkontrolleuren durchgeführt …“) — er wird ignoriert, nicht
    zum Ausschlusskriterium. Ausgeschlossen bleibt, was die Zeile zu etwas
    anderem macht: Wörter LINKS der Spalte (dann ist es eine Nummern- oder
    Kopfzeile) und Zahlen in der Betragszone (dann eine verrutschte
    Betragszeile — lieber gar kein Name als einer mit fremder Herkunft).

    Die Spaltengrenzen kommen aus dem GEZEICHNETEN Raster, wo die Seite eines
    hat (:attr:`Spalten.bez_spalte`) — dieselbe Entscheidung wie bei der
    Erläuterungs-Spalte: Geometrie schlägt Schätzung. Wie weit der zentrierte
    Kopf neben seiner Spalte liegt, schwankt nämlich je Jahrgang: Gemessen
    über alle 18 EHH-Dokumente fielen aus der geschätzten Zone 12–72 % der
    Wörter, die zwischen den gedruckten Linien stehen — im fertigen Feld
    175 von 1.799 Positionen (9,7 %), die dadurch einen angeschnittenen
    Namen trugen („für SGB II“ statt „Grundsicherung für Arbeitssuchende
    SGB II“, „von und Frauen“ statt „Chancengleichstellung von Männern und
    Frauen“). Ohne Linien bleibt die alte Schätzung: Der Text beginnt
    gemessen bis 18 pt vor der Kopfkante (212801: Spalte ab 264, Kopf ab
    282), links davon endet die Produkt-Spalte (212) — die 25 pt Vorlauf
    lassen dazwischen Luft."""
    zone_links, zone_rechts = spalten.zone
    if spalten.bez_spalte is not None:
        # 1 pt Luft an beiden Kanten: Wortboxen setzen gelegentlich haarscharf
        # auf ihrer Linie auf (gemessen 230011: „Männern“ endet bei 355,0 bei
        # einer Spaltenlinie 359,4 — die Kante ist die Linie, nicht das Wort).
        links, rechts = spalten.bez_spalte[0] - 1, spalten.bez_spalte[1] + 1
    elif spalten.label is not None:
        links, rechts = spalten.label - 25, zone_links - 2
    else:
        return None
    part = [w for w in row if links <= w[0] and w[1] <= rechts]
    if not part:
        return None
    if any(w[1] < links for w in row):
        return None
    if any(re.fullmatch(_ZAHL, w[3]) and zone_links <= w[1] <= zone_rechts
           for w in row):
        return None
    return " ".join(w[3] for w in part)


def _betrag_tokens(row: list[Wort]) -> list[Wort]:
    """Wörter, die als Ganzes eine Zahl sind — die Betrags-Kandidaten einer
    Summenzeile. Ein Datum wie „01.10.2025“ ist EIN Wort und besteht den
    Vollabgleich nicht (Zweiergruppen, vierstelliges Jahr)."""
    return [w for w in row if re.fullmatch(_ZAHL, w[3])]


def _ist_summenzeile(kandidaten: list[Wort]) -> bool:
    """Drei Beträge, davon mindestens zwei gepunktet.

    Nur auf Punkte zu bestehen fräße echte Summen: Die Verw.-II-Zeile des
    2023er-Blocks in 244160 lautet „−390.000 **0** −390.000“. Gar nicht
    darauf zu bestehen ließe Zähl-Zeilen durch („Seite 7“, Lfd.-Nummern) —
    zwei gepunktete Millionenbeträge hat dagegen jede echte Summenzeile."""
    return (len(kandidaten) >= 3
            and sum(1 for w in kandidaten if "." in w[3]) >= 2)


def _summen_zeile(year: int, typ: str, row: list[Wort]) -> SummenZeile:
    """Eine Zusammenstellungs-Zeile: die ersten drei Beträge sind
    Erträge/Aufwendungen/Saldo, was davor und dahinter steht, gehört zum
    Label (die Beschluss-Dateien schreiben „Verw. I“ HINTER die Zahlen)."""
    betraege = _betrag_tokens(row)
    if len(betraege) < 3:
        raise ListenFehler(
            f"Zusammenstellung {year}: Zeile mit weniger als drei Beträgen: "
            f"{_zeilentext(row)[:90]!r}")
    e, a, s = (_zahl(w[3]) for w in betraege[:3])
    if abs(e - a - s) > 2:
        raise ListenFehler(
            f"Zusammenstellung {year}: Erträge − Aufwendungen ≠ Saldo "
            f"({e:,} − {a:,} ≠ {s:,}) in {_zeilentext(row)[:90]!r}")
    x_erster, x_dritter = betraege[0][0], betraege[2][1]
    label = " ".join(w[3] for w in row
                     if w[1] <= x_erster or w[0] >= x_dritter).strip()
    return SummenZeile(year=year, typ=typ, label=label or typ,
                       revenues=e, expenses=a, balance=s)


def parse_ehh_seiten(seiten: list[list[Wort]],
                     linien: list[Linien] | None = None) -> Ergebnis:
    """Die Seiten (Wortlisten) einer EHH-Änderungsliste → geprüfte Zeilen.

    Wirft :class:`ListenFehler`, sobald eine der drei Proben aus dem
    Modulkopf nicht aufgeht — halb gelesene Listen gibt es nicht.

    ``linien`` (je Seite die Tabellenlinien, s. :func:`seiten_linien`) ist
    optional und trägt die Textspalten bei: die Erläuterungen, die
    Bezeichnungs-Spalte und den Urheber je Position. Ohne Linien bleiben die
    Beträge vollständig, ``explanation`` und ``author`` einfach ``None``
    und die Bezeichnungs-Nachlese fällt auf ihre Kopf-Schätzung zurück.
    """
    aus = Ergebnis()
    if seiten and (m := _STAND.search(_zeilentext([w for z in _zeilen_bilden(seiten[0]) for w in z]))):
        aus.as_of = m.group(1)

    for seiten_nr, woerter in enumerate(seiten):
        # Blocküberschriften („Ergebnishaushalt JJJJ") gelten nur auf IHRER
        # Seite: Die Beschluss-Dateien haben auf der Zusammenstellungs-Seite
        # gar keine — ein dokumentweiter Merker ließe dort das Jahr der
        # letzten Tabellenseite weitergelten, und alle Blöcke fielen auf
        # dasselbe Planjahr (der 303358-Befund: viermal 2029).
        block_jahr: int | None = None
        zeilen = _zeilen_bilden(woerter)
        seitentext = " ".join(_zeilentext(z) for z in zeilen)
        marker = _JAHR_MARKER.search(seitentext)
        year = int(marker.group(1)) if marker else None
        seiten_linien_ = (linien[seiten_nr]
                          if linien is not None and seiten_nr < len(linien) else None)
        senkrecht = seiten_linien_[1] if seiten_linien_ else None
        spalten = _spalten(zeilen, senkrecht)
        urheber_links = (_urheber_grenze(woerter, senkrecht, spalten)
                         if senkrecht and spalten is not None else None)

        seiten_positionen: list[tuple[float, Zeile]] = []
        fragmente: list[tuple[float, str]] = []
        for row in zeilen:
            text = _zeilentext(row)
            if (b := _BLOCK_JAHR.search(text)):
                block_jahr = int(b.group(1))
            elif spalten is None and re.fullmatch(r"20\d\d", text.strip()):
                # Die frühen AFB-Übersichten überschreiben ihre Blöcke mit der
                # nackten Jahreszahl statt „Ergebnishaushalt JJJJ“.
                block_jahr = int(text.strip())
            if year is not None and spalten is not None:
                if _ist_position(row, spalten):
                    position = _position_lesen(row, year, spalten)
                    aus.zeilen.append(position)
                    seiten_positionen.append((row[0][2], position))
                    continue
                if (fragment := _bezeichnungsfragment(row, spalten)):
                    fragmente.append((row[0][2], fragment))
                    continue
            # Zusammenstellungs-Zeilen erkennt man an ihren DREI Beträgen —
            # das Deckblatt („Änderungsvorschläge … zum Verwaltungsentwurf“)
            # und Fließtext-Erwähnungen tragen dieselben Wörter ohne Zahlen.
            betraege = _betrag_tokens(row)
            if spalten is not None or not _ist_summenzeile(betraege):
                # Auf Tabellenseiten wäre so eine Zeile eine zweispaltige
                # Position — Zusammenstellungen stehen auf eigenen Seiten.
                continue
            if _ENTWURF.search(text):
                aus.summen.append(_summen_zeile(_block_jahr(block_jahr, aus, "draft"), "draft", row))
            elif _ENDSUMME.search(text):
                aus.summen.append(_summen_zeile(_block_jahr(block_jahr, aus, "final_total"), "final_total", row))
            elif _LISTE.search(text):
                aus.summen.append(_summen_zeile(_block_jahr(block_jahr, aus, "list"), "list", row))
            else:
                # Die frühen AFB-Übersichten führen die POLITISCH beschlossene
                # Liste ohne jedes Stichwort: nur drei Beträge plus Urheber in
                # der „Vorschlag von“-Spalte („0 1.728.605 -1.728.605
                # SPD/ BÜNDNIS 90/DIE GRÜNEN“). Das Label hinter den Zahlen
                # ist die Bedingung — eine nackte Zahlenreihe bleibt draußen.
                kandidat = _summen_zeile(_block_jahr(block_jahr, aus, "list"), "list", row)
                if kandidat.label != "list":
                    aus.summen.append(kandidat)

        _fragmente_anbauen(seiten_positionen, fragmente)
        if spalten is not None and seiten_linien_ is not None:
            _erlaeuterungen_anbauen(seiten_positionen, zeilen, spalten,
                                    seiten_linien_, urheber_links)
            if urheber_links is not None:
                _urheber_anbauen(seiten_positionen, zeilen, seiten_linien_,
                                 urheber_links)

    if not aus.zeilen:
        raise ListenFehler("Keine Positionszeilen gefunden — andere Bauform?")
    if not aus.summen:
        raise ListenFehler("Keine Zusammenstellung gefunden — ohne sie keine Probe.")

    _proben(aus)
    return aus


def _fragmente_anbauen(positionen: list[tuple[float, Zeile]],
                       fragmente: list[tuple[float, str]]) -> None:
    """Übergelaufene Bezeichnungs-Zeilen ihrer Position zuschlagen.

    Zugeordnet wird nur, was EINDEUTIG ist: Die nächstgelegene Position muss
    binnen 13 pt liegen (Wickelabstand gemessen 10 pt) und die zweitnächste
    mindestens doppelt so weit weg sein — sonst bleibt das Fragment liegen.
    Eine Lücke im Namen ist billiger als ein Name an der falschen Zeile;
    die Beträge berührt das ohnehin nicht, über die wachen die Proben.
    """
    if not positionen or not fragmente:
        return
    anbau: dict[int, list[tuple[float, str]]] = {}
    for fy, ftext in fragmente:
        sortiert = sorted(positionen, key=lambda p: abs(p[0] - fy))
        if abs(sortiert[0][0] - fy) > 13:
            continue
        if len(sortiert) > 1 and abs(sortiert[1][0] - fy) < 2 * abs(sortiert[0][0] - fy):
            continue
        anbau.setdefault(id(sortiert[0][1]), []).append((fy, ftext))
    for py, position in positionen:
        teile = anbau.get(id(position))
        if not teile:
            continue
        # Nach Grundlinie sortiert, die Zeile der Position an ihrem Platz.
        alle = sorted(teile + [(py, position.label)])
        position.label = " ".join(t for _, t in alle if t)


def _urheber_grenze(woerter: list[Wort], senkrecht: list[float],
                    spalten: Spalten) -> float | None:
    """Die linke Kante der Spalte „Vorschlag von“ — oder ``None``.

    Genau EIN Dokument des Bestands führt sie je Position: die
    Beschluss-Datei zum Haushalt 2021 (230011, dazu ihre inhaltsgleiche
    Zweitablage 230030), auf 20 ihrer 21 Seiten. Die übrigen sechzehn
    Dokumente kennen den Urheber nur in der Zusammenstellung — dort steht er
    ohnehin schon als Label seiner Summenzeile.

    Gesucht wird der zweizeilig gesetzte KOPF, nicht das Wort: „Vorschlag“
    mit „von“ direkt darunter in derselben Spalte. Das Wort allein reicht
    nicht — in 271304 steht „Der eingebrachte **Vorschlag** zur Erhöhung der
    Bewohnerparkgebühren der Politik …“ mitten in einer Erläuterung, und eine
    Wortsuche hielt diese Seite prompt für eine mit Urheber-Spalte. Dazu zwei
    Bedingungen aus dem Linienraster: Die Spalte liegt RECHTS der Beträge und
    ist die LETZTE der Seite (rechts von ihrer Kante steht nur noch der
    Tabellenrand). Ohne all das gibt es keine Grenze — dann läuft die
    Erläuterung wie bisher bis zum Blattrand.
    """
    kopf = [w for w in woerter if w[3] == "Vorschlag"]
    for x0, x1, y, _text in kopf:
        # „von“ direkt darunter: dieselbe Spalte, die nächste Grundlinie.
        if not any(v[3] == "von" and 0 < v[2] - y <= 22
                   and v[0] < x1 and v[1] > x0 for v in woerter):
            continue
        links = [x for x in senkrecht if x < x0]
        rechts = [x for x in senkrecht if x >= x1]
        if not links or len(rechts) != 1:
            continue
        if max(links) <= spalten.expense:
            continue
        return max(links)
    return None


def _urheber_anbauen(positionen: list[tuple[float, Zeile]],
                     zeilen: list[list[Wort]], linien: Linien,
                     grenze: float) -> None:
    """Die Spalte „Vorschlag von“ ihren Positionen zuschlagen.

    Dieselbe Geometrie wie bei den Erläuterungen — die waagerechten Linien
    teilen die Seite in Zeilenbänder, ein Band gehört genau einer Position.
    Das ist hier nicht Bequemlichkeit, sondern Notwendigkeit: Die Labels
    wickeln über drei Grundlinien („SPD/“ / „BÜNDNIS 90/“ / „DIE GRÜNEN“)
    und stehen dabei ober- UND unterhalb der Positions-Grundlinie, weil die
    Zellen vertikal zentriert sind. Nach Abstand geraten träfe es die
    Nachbarzeile.

    Bewiesen wird das Ergebnis NICHT hier, sondern in :func:`_proben`: Die
    Summe der Positionen je Urheber muss die Zusammenstellungs-Zeile dieses
    Urhebers treffen. Wem die Stadt eine Kürzung zuschreibt, ist die
    folgenreichste Angabe dieses Moduls — sie wird gerechnet, nicht gelesen.
    """
    waagerecht, _senkrecht = linien
    if not positionen or len(waagerecht) < 2:
        return
    baender: dict[int, list[Wort]] = {}
    for row in zeilen:
        for w in row:
            if w[0] < grenze - 1:
                continue
            band = _band(waagerecht, w[2])
            if band is not None:
                baender.setdefault(band, []).append(w)

    for py, position in positionen:
        band = _band(waagerecht, py)
        if band is None:
            continue
        if sum(1 for qy, _ in positionen if _band(waagerecht, qy) == band) > 1:
            continue
        woerter = sorted(baender.get(band, []), key=lambda w: (w[2], w[0]))
        if woerter:
            # Ohne `_zeilen_falten`: Ein Label ist keine Prosa, seine
            # Schrägstriche sind Trennzeichen zwischen Fraktionen und keine
            # Silbentrennung („SPD/“ + „BÜNDNIS 90/“ bleibt „SPD/ BÜNDNIS 90/“).
            position.author = " ".join(
                " ".join(w[3] for w in z) for z in _zeilen_bilden(woerter))


def _erlaeuterungen_anbauen(positionen: list[tuple[float, Zeile]],
                            zeilen: list[list[Wort]], spalten: Spalten,
                            linien: Linien, urheber_grenze: float | None = None) -> None:
    """Die Erläuterungs-Spalte einer Seite ihren Positionen zuschlagen.

    Text hat keine Schlusssumme, gegen die man ihn beweisen könnte — an die
    Stelle der Rechenprobe tritt Geometrie: Die WAAGERECHTEN Tabellenlinien
    teilen die Seite in Zeilenbänder, und ein Band gehört genau der
    Position, deren Grundlinie darin liegt. Mehrzeilige Erläuterungen wickeln
    innerhalb ihres Bandes ober- UND unterhalb der Positions-Grundlinie
    (die Zellen sind vertikal zentriert) — mit den Linien ist das keine
    Abstandsfrage mehr. Die Spaltengrenze ist die erste SENKRECHTE Linie
    rechts der Aufwand-Kopfmitte: die rechte Kante der Aufwand-Spalte.

    Konservativ wie die Bezeichnungs-Nachlese: Ein Band mit zwei Positionen
    (käme nur bei gerissenen Linien vor) bleibt draußen, Wörter außerhalb
    des Linienrasters (Fußzeilen wie „Seite 2 Verw. I 2026“) auch, und ohne
    brauchbare Linien bekommt die Seite gar keine Erläuterungen — lieber
    leer als per Raten an der falschen Zeile.

    RECHTS endet die Spalte an ``urheber_grenze``, wo das Dokument eine
    Spalte „Vorschlag von“ führt. Ohne diese Grenze zog die Erläuterung den
    Urheber mit hinein, und zwar mitten in den Satz — die Labels wickeln auf
    eigenen Grundlinien, also fielen sie beim Falten zwischen die Wörter der
    Erläuterung („… gegen Gewalt an SPD/ Frauen u. häusl. Gewalt …“). Alle
    187 Positionen von 230011 waren so verunreinigt.
    """
    if not positionen:
        return
    waagerecht, senkrecht = linien
    grenzen = [x for x in senkrecht if x > spalten.expense]
    if not grenzen or len(waagerecht) < 2:
        return
    erl_links = grenzen[0]
    erl_rechts = urheber_grenze if urheber_grenze is not None else float("inf")

    baender: dict[int, list[Wort]] = {}
    for row in zeilen:
        for w in row:
            if w[0] < erl_links - 1 or w[0] >= erl_rechts - 1:
                continue
            band = _band(waagerecht, w[2])
            if band is not None:
                baender.setdefault(band, []).append(w)

    for py, position in positionen:
        band = _band(waagerecht, py)
        if band is None:
            continue
        if sum(1 for qy, _ in positionen if _band(waagerecht, qy) == band) > 1:
            continue
        woerter = sorted(baender.get(band, []), key=lambda w: (w[2], w[0]))
        if woerter:
            position.explanation = _zeilen_falten(_zeilen_bilden(woerter))


#: Wörter, vor denen ein Trennstrich am Zeilenende KEIN Trennstrich ist,
#: sondern ein Ergänzungsstrich („Brand- und Katastrophenschutz“) — dieselbe
#: Regel wie in council/pruefberichte.py, dort am RPA-Bestand geeicht.
_ERGAENZUNG = {"und", "oder", "sowie", "bzw", "beziehungsweise", "wie", "als",
               "noch", "je", "bis"}


def _zeilen_falten(zeilen: list[list[Wort]]) -> str:
    """Die Grundlinien einer Erläuterungs-Zelle zu einem Text falten.

    Die Silbentrennung wird nur AM Zeilenumbruch zusammengezogen — wo der
    war, sagen die Wortkoordinaten, nicht eine Textheuristik: Ein Strich
    mitten in der Zeile („D-Ticket“, „Brand- und …“) bleibt grundsätzlich
    unberührt. Am Umbruch gelten die Regeln aus council/pruefberichte.py:
    vor Ergänzungswörtern bleibt „- “, vor Großbuchstaben wird es ein
    Bindestrich („Programm-Updates“), sonst war es eine Trennung
    („Bescheini-/gungen“ → „Bescheinigungen“).
    """
    aus = ""
    for row in zeilen:
        text = " ".join(w[3] for w in row)
        if not aus:
            aus = text
        elif aus.endswith("-") and len(aus) > 1 and aus[-2].isalnum():
            erstes = text.split(" ", 1)[0]
            if erstes.lower().rstrip(".") in _ERGAENZUNG:
                aus += " " + text
            elif erstes[:1].isupper():
                aus += text
            else:
                aus = aus[:-1] + text
        else:
            aus += " " + text
    return aus


def _band(waagerecht: list[float], y: float) -> int | None:
    """In welchem Zeilenband (Index der Linie darüber) liegt die Grundlinie?

    ``y`` ist die OBERKANTE der Wortbox; die kleine Toleranz fängt Boxen,
    die haarscharf auf ihrer Linie beginnen. Oberhalb der ersten oder
    unterhalb der letzten Linie ist kein Band — dort stehen Überschriften
    und Fußzeilen, nicht die Tabelle.
    """
    for i in range(len(waagerecht) - 1):
        if waagerecht[i] - 0.5 <= y < waagerecht[i + 1] - 0.5:
            return i
    return None


def _block_jahr(block_jahr: int | None, aus: Ergebnis, typ: str) -> int:
    """Das Planjahr eines Zusammenstellungs-Blocks.

    Die Verwaltungs-Dateien überschreiben jeden Block mit „Ergebnishaushalt
    JJJJ“; die Beschluss-Dateien lassen die Überschrift ganz weg. Dann gilt:
    Die Blöcke kommen in derselben Reihenfolge wie die Planjahre der
    Positionen, und jeder beginnt mit seinem Verwaltungsentwurf — der
    wievielte Entwurf, das wievielte Jahr. Listen und Endsumme gehören zum
    ZULETZT begonnenen Block, nicht zum nächsten (der Zähler zählt den
    eigenen Entwurf sonst mit — der 303358-Befund).
    """
    if block_jahr is not None:
        return block_jahr
    years = sorted({z.year for z in aus.zeilen})
    entwuerfe = sum(1 for s in aus.summen if s.typ == "draft")
    idx = entwuerfe if typ == "draft" else entwuerfe - 1
    if 0 <= idx < len(years):
        return years[idx]
    raise ListenFehler("Zusammenstellungs-Block ohne erkennbares Planjahr.")


def _proben(aus: Ergebnis) -> None:
    """Kettenprobe und Positionsprobe je Planjahr (die Zeilenprobe lief schon
    beim Lesen jeder Summenzeile)."""
    years = sorted({z.year for z in aus.zeilen})
    for year in years:
        entwurf = [s for s in aus.summen if s.year == year and s.typ == "draft"]
        listen = [s for s in aus.summen if s.year == year and s.typ == "list"]
        ende = [s for s in aus.summen if s.year == year and s.typ == "final_total"]
        if len(entwurf) != 1 or len(ende) != 1 or not listen:
            raise ListenFehler(
                f"Zusammenstellung {year}: erwartet 1×Entwurf, ≥1×Liste, "
                f"1×Endsumme — gefunden {len(entwurf)}/{len(listen)}/{len(ende)}.")

        # Kettenprobe: Entwurf + alle Listen = Endsumme, je Spalte. Toleranz
        # 2 Euro je Summand — die Dokumente runden selbst (s. Modulkopf).
        #
        # Die Beschluss-Datei des AFB besteht sie NICHT, und zwar zu Recht:
        # Ihre Endsumme rechnet auch die politisch beschlossenen Änderungen
        # ein (2026: 218.298 Euro Aufwandsminderung — die im Ausschuss
        # gestrichene Position der Koalitionsliste), weist als Zeilen aber
        # nur die Verwaltungslisten aus. Dann trägt eine andere, härtere
        # Referenz: Die Positionen müssen GENAU auf „Endsumme − Entwurf“
        # summieren — alles, was das Dokument insgesamt ändert.
        toleranz = 2 * (len(listen) + 1)
        kette_ok = all(
            abs(getattr(entwurf[0], field)
                + sum(getattr(s, field) for s in listen)
                - getattr(ende[0], field)) <= toleranz
            for field in ("revenues", "expenses"))

        # Positionsprobe: Wessen Zeile summieren wir hier eigentlich? Die
        # Kandidaten sind jede Listen-Zeile und — für die kumulierten
        # Beschluss-Dateien — die Summe aller Zeilen bzw. (wenn die Kette
        # nicht aufgeht, s. o.) allein „Endsumme − Entwurf“.
        pos_e = sum(z.revenue or 0 for z in aus.zeilen if z.year == year)
        pos_a = sum(z.expense or 0 for z in aus.zeilen if z.year == year)
        if kette_ok:
            ziele = [(s.label, s.revenues, s.expenses) for s in listen]
            if len(listen) > 1:
                ziele.append(("alle", sum(s.revenues for s in listen),
                              sum(s.expenses for s in listen)))
        else:
            ziele = [("beschlossen",
                      ende[0].revenues - entwurf[0].revenues,
                      ende[0].expenses - entwurf[0].expenses)]
        treffer = [label for label, e, a in ziele
                   if abs(e - pos_e) <= toleranz and abs(a - pos_a) <= toleranz]
        if len(treffer) != 1:
            raise ListenFehler(
                f"Positionsprobe {year}: Die Positionen summieren auf "
                f"{pos_e:,} / {pos_a:,} — "
                + ("keine Zusammenstellungs-Zeile trifft das" if not treffer
                   else "mehrere Zusammenstellungs-Zeilen träfen das")
                + ": " + "; ".join(f"{label}: {e:,}/{a:,}" for label, e, a in ziele))
        aus.eigene_zeile[year] = treffer[0]

        _urheber_probe(aus, year, listen, toleranz)


def _urheber_probe(aus: Ergebnis, year: int, listen: list[SummenZeile],
                   toleranz: int) -> None:
    """Die Summe der Positionen je Urheber muss SEINE Zusammenstellungs-Zeile
    treffen — sonst gilt das Dokument als nicht gelesen.

    Diese Probe ist der Grund, warum überhaupt ein Urheber gespeichert wird.
    Wem die Stadt eine Streichung zuschreibt, ist die folgenreichste Angabe
    dieses Moduls; sie darf nicht an einer Spaltenkante hängen. Das Dokument
    rechnet sie sich selbst vor: 230011 teilt seine 187 Positionen auf
    „Verw. I“, „Verw. II“ und „SPD/ BÜNDNIS 90/DIE GRÜNEN“ auf, und für
    jedes der vier Planjahre steht die Summe jeder Gruppe als eigene Zeile
    in der Zusammenstellung. Gemessen: 9 von 9 Gruppen treffen auf den Cent.

    Sie ist HART wie die anderen — reißt sie, wird nichts gespeichert, auch
    nicht die Beträge. Ein Dokument, das die Spalte führt und dessen
    Zuordnung nicht aufgeht, soll im Ingest als „nicht gelesen“ auffallen und
    nicht still ohne Urheber durchlaufen: Eine stumme Lücke sähe aus wie ein
    Dokument ohne die Spalte, und genau die Unterscheidung ist hier wertvoll.

    Die Labels der beiden Seiten sind NICHT deckungsgleich — die Position
    sagt „Verw. I“, die Zusammenstellung „Änderungsliste v. 19.11.2020
    Verw. I“. Zugeordnet wird deshalb über die Beträge; das Label muss
    danach nur noch dazu passen (Teilzeichenkette), damit zwei betragsgleiche
    Gruppen nicht die Zeilen tauschen können.
    """
    mit = [z for z in aus.zeilen if z.year == year and z.author]
    if not mit:
        return
    ohne = [z for z in aus.zeilen if z.year == year and not z.author]
    if ohne:
        raise ListenFehler(
            f"Urheberprobe {year}: {len(ohne)} von {len(mit) + len(ohne)} "
            f"Positionen ohne Urheber, obwohl die Seite die Spalte führt "
            f"(erste: seq. {ohne[0].seq}).")

    gruppen: dict[str, list[int]] = {}
    for z in mit:
        summe = gruppen.setdefault(z.author, [0, 0])
        summe[0] += z.revenue or 0
        summe[1] += z.expense or 0

    vergeben: set[str] = set()
    for author, (e, a) in sorted(gruppen.items()):
        treffer = [s for s in listen
                   if s.label not in vergeben
                   and abs(s.revenues - e) <= toleranz
                   and abs(s.expenses - a) <= toleranz
                   and _label_passt(author, s.label)]
        if len(treffer) != 1:
            raise ListenFehler(
                f"Urheberprobe {year}: „{author}“ summiert auf {e:,} / {a:,} — "
                + ("keine Zusammenstellungs-Zeile trifft das" if not treffer
                   else "mehrere Zeilen träfen das")
                + ": " + "; ".join(
                    f"{s.label}: {s.revenues:,}/{s.expenses:,}" for s in listen))
        vergeben.add(treffer[0].label)


def _label_passt(author: str, summen_label: str) -> bool:
    """Steckt der Urheber der Position im Label seiner Summenzeile?

    Verglichen wird ohne Leerzeichen und ohne Groß-/Kleinschreibung: Die
    Zusammenstellung setzt „SPD/ BÜNDNIS 90/DIE GRÜNEN“, die Positionsspalte
    bricht dasselbe Label anders um („SPD/ BÜNDNIS 90/ DIE GRÜNEN“) — es ist
    das Papier, das dort verschieden umbricht, nicht die Aussage.
    """
    def kern(s: str) -> str:
        return re.sub(r"\s+", "", s).casefold()
    return kern(author) in kern(summen_label)


def lies_ehh_liste(pdf_bytes: bytes) -> Ergebnis:
    """PDF → geprüfte Änderungsliste. Wirft :class:`ListenFehler`."""
    return parse_ehh_seiten(seiten_woerter(pdf_bytes), seiten_linien(pdf_bytes))


# ---------------------------------------------------------------------- Herkunft

def herkunft_fuer(label: str, url: str | None, document_id: int) -> Herkunft:
    return Herkunft(
        art="ris",
        probe=("aenderungsliste_summen", "aenderungsliste_positionen",
               "aenderungsliste_erlaeuterungen", "aenderungsliste_urheber"),
        label=label,
        url=url or f"https://buergerinfo.oldenburg.de/getfile.php?id={document_id}&type=do",
        document_id=document_id,
    )


# ------------------------------------------------- Geteilt mit dem FHH-Parser

#: Der Finanzhaushalt hat eine eigene Bauform (fünf Betragsspalten statt zwei)
#: und deshalb ein eigenes Modul — ``council/aenderungslisten_fhh.py``. Die
#: GEOMETRIE ist aber dieselbe: Wortzeilen aus Grundlinien, Zeilenbänder aus
#: den gezeichneten Linien, Silbentrennung am gemessenen Umbruch. Statt sie
#: dort noch einmal zu schreiben, stehen die drei Funktionen hier unter einem
#: öffentlichen Namen. Der EHH-Parser bleibt dabei unangetastet: Er ruft
#: weiter seine privaten Namen auf, und diese Zeilen sind reine Aliase.
zeilen_bilden = _zeilen_bilden
band = _band
zeilen_falten = _zeilen_falten
