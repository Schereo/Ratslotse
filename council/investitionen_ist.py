"""Was die Stadt wirklich gebaut hat — Tabellen 1107 und 1107-1 des
Statistischen Jahrbuchs, 2003 bis heute.

Der Haushalts-Bereich zeigt seit 08/2026, was die Stadt bauen und kaufen
**will**: Datensatz 1101 des Open-Data-Portals, der Finanzhaushalt des
beschlossenen Haushaltsplans (``council/investitionen.py``). Das sind
Planzahlen, und ihr eigener Modulkopf sagt es deutlich: „Was am Jahresende
wirklich verbaut wurde, steht nicht darin."

Hier steht es. Das Statistische Jahrbuch führt die Rechnungsergebnisse — was
im Jahr tatsächlich abgeflossen ist, aufgeteilt nach Auszahlungsart.

Zwei Tabellen, zwei Rechnungswesen — und das ist keine Formsache
--------------------------------------------------------------
Die Stadt veröffentlicht beide in **einer** PDF-Datei, aber als **zwei**
Tabellen, und sie sagt in einer Fußnote selbst, warum:

    „Einführung Neues Komunales Rechnungswesens (NKR) zum 01. Januar 2010."

Vor 2010 rechnete die Stadt kameral, danach doppisch. Das ist der Grund für
den Schnitt, und er ist tiefer als ein Spaltenname:

* **1107 (2003–2009)** heißt „**Ausgaben** der Stadt Oldenburg für eigene
  Investitionen" und zählt vier Arten — darunter „Gewährung von Darlehen".
* **1107-1 (2010–2025)** heißt „**Auszahlungen** der Stadt Oldenburg für
  Investitionstätigkeiten" und zählt sechs Arten, nach den Positionen, die
  § 3 GemHKVO für die Finanzrechnung vorgibt. Der Untertitel nennt zusätzlich
  die Abgrenzung: „Rechnungsergebnisse laut Finanzrechnung der
  **Kernverwaltung**".

Deshalb trägt jeder Jahrgang sein :data:`REGELWERK` mit, deshalb hat jedes
Regelwerk seine **eigenen** Arten (:data:`SPALTEN`), und deshalb zieht kein
Lesepfad eine Linie über 2009/2010 hinweg. Wer die beiden Reihen zu einer
Kurve verbindet, behauptet eine Vergleichbarkeit, die das Dokument mit seiner
Fußnote gerade bestreitet.

Die eine Probe — und die Suche nach einer zweiten
-------------------------------------------------
:func:`zeilensumme` ist die Probe, die das Dokument selbst mitbringt: Die
Auszahlungsarten einer Zeile müssen die Summe ergeben, die dieselbe Zeile
daneben als „insgesamt" ausweist. Sie greift in 22 von 23 Jahrgängen — in
allen sieben kameralen und in 15 von 16 doppischen.

**2019 reißt sie**, im Dokument selbst: Die sechs Arten ergeben 66.595 T€,
ausgewiesen sind 67.899 T€. 1,304 Mio. € Unterschied. Welche der sieben
Zahlen danebenliegt, sagt die Tabelle nicht.

Bei der Schuldenzeitreihe (``council/schulden.py``) rettete an dieser Stelle
eine **zweite, unabhängige** Probe den Jahrgang: Die Tabelle führt dort einen
Pro-Kopf-Betrag, und der ließ sich gegen die Einwohnerzahl aus einer anderen
Veröffentlichung der Stadt nachrechnen. Die Summe war damit belegt, nur die
Aufteilung nicht — also kam die Summe herein und die Aufteilung nicht.

Für 1107-1 wurde dieselbe zweite Probe gesucht. Es gibt sie nicht:

1. **Keine Pro-Kopf-Spalte.** 1107-1 führt sieben Wertspalten, alle in Tausend
   Euro, keine davon je Einwohner*in. Eine Division wäre unsere Rechnung und
   stünde in keinem Dokument — sie könnte einen Übertragungsfehler nicht
   aufdecken, weil beide Seiten von uns kämen.
2. **Keine zweite Ausgabe.** Die Übersichtsseite des Jahrbuchs führt Tabellen
   aus zwei Jahrgängen (2024 und 2025), aber für Kapitel 11 nur den von 2025.
   Die Vorjahresdatei ist nicht mehr abrufbar; eine Überlappungsprobe wie beim
   Beteiligungsbericht ist damit nicht zu haben.
3. **Kein Spiegel im Open-Data-Portal.** Das Portal führt 91 Datensätze,
   darunter die kameralen Ausgaben bis 2009 und die ordentlichen Aufwendungen
   seit 2010 — die Investitions-Ist-Zahlen sind nicht dabei.
4. **Der Plan ist keine Probe**, sondern eine andere Größe (s. unten).

Also gilt hier die Grundregel ohne Rettungsanker: **2019 wird verworfen**, mit
allen sieben Zahlen. Nicht nur die Aufteilung — denn anders als 2022 bei den
Schulden ist hier auch die Summe durch nichts gedeckt. Geschätzt wird nichts,
gerundet wird nichts, und die Seite sagt, dass das Jahr fehlt und warum.

Warum Plan und Ist hier **nicht** gegeneinander stehen
-------------------------------------------------------
Die naheliegende Seite wäre „geplant gegen gebaut": ``council_investitionen``
führt für 2022–2025 die geplanten Auszahlungen, diese Schicht die
tatsächlichen. Gerechnet ergäbe das Quoten zwischen 41 % und 75 %.

Diese Quote wird **nicht** gezeigt, und zwar nicht aus Vorsicht, sondern weil
sie in keinem Dokument steht und ihre beiden Hälften verschieden abgegrenzt
sind:

* Der Plan kommt aus dem **Finanzhaushalt des Haushaltsplans**, gegliedert
  nach **Teilhaushalten** (THH01–13, also nach Organisation).
* Das Ist kommt aus der **Finanzrechnung der Kernverwaltung**, gegliedert nach
  **Auszahlungsarten** (also nach Wirtschaftlichkeit).

Keine der beiden Quellen nennt die andere, keine weist die Differenz aus, und
keine sagt, dass ihre Gesamtsumme dieselbe Menge zählt. Eine „Umsetzungsquote"
daraus wäre eine Zahl, die wir erfinden — und sie wäre die interessanteste
Zahl der Seite, also genau die, die niemand ungeprüft lesen sollte. Die Seite
verlinkt die Planseite und sagt den Grund; sie subtrahiert nicht.

Was der Extrakt anrichtet
-------------------------
Dieselbe Falle wie bei Tabelle 1108, nur an einer anderen Stelle: Die
**Fußnotenziffer klebt im Titel an der Jahreszahl**. Aus „in Tausend Euro 2010
bis 2025" mit Fußnote 1 wird im Textextrakt ``2010 bis 20251``. Ein Parser,
der die Spanne stur als vier Ziffern liest, findet dort das Jahr 2025 und eine
Ziffer, die er nicht unterbringt — oder, schlimmer, er liest 20251 als Jahr
und hält die Tabelle für unlesbar. :func:`erkenne` nimmt die Ziffer deshalb
ausdrücklich als Fußnotenmarke an (Jahreszahlen haben vier Stellen, fünf gibt
es nicht).

In den Datenzeilen selbst tragen die Beträge **keine** Marken — geprüft an
allen 23 Zeilen mit einem Positions-Dump des PDFs. Die Zellen-Regel
(:func:`_zelle`) bringt sie trotzdem mit: Sie kostet nichts und fängt den Tag
ab, an dem die Stadt eine Fußnote an einen Betrag hängt.
"""
from __future__ import annotations

import re

#: Woher die Reihe kommt. Wie bei Tabelle 1108 trägt die Datei den Jahrgang im
#: Namen — ``scripts/ingest_investitionen_ist.py`` liest deshalb die
#: Übersichtsseite und nimmt den Link, der dort auf 1107 zeigt. Diese Konstante
#: ist der Stand vom 17.08.2026 und die Rückfallebene.
#:
#: Bemerkenswert und der Grund für das Muster unten: Beide Tabellen stecken in
#: **einer** Datei, und deren Name führt beide Nummern („1107-1107-1-…").
JAHRBUCH_URL = ("https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/"
                "stadtverwaltung/statistik/statistisches-jahrbuch.html")
TABELLE_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
               "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/"
               "1107-1107-1-2025-AZ.pdf")

#: Wie die Übersichtsseite den Link zu dieser Datei schreibt. Bewusst auf
#: ``1107`` und nicht auf ``1107-1`` gemustert: Der Dateiname beginnt mit der
#: ersten Nummer, und die Stadt hat die beiden Tabellen schon einmal anders
#: zusammengefasst (die Nachbarn heißen ``1104-1105-…``).
LINK_MUSTER = re.compile(r'href="([^"]*/1107[^"]*\.pdf)"', re.IGNORECASE)

#: Was diese Zahlen zählen — der Satz, der neben der Zahl stehen kann.
#:
#: „Kernverwaltung" steht so im Untertitel von 1107-1 und ist die engere
#: Abgrenzung als bei den Schulden: Dort zählt die Tabelle die Stadt als
#: Rechtsträger einschließlich der Eigenbetriebe, hier nur die Kernverwaltung.
#: Was der Eigenbetrieb Gebäudewirtschaft und Hochbau baut — und das ist seit
#: 2010 ein großer Teil des städtischen Hochbaus —, steht in dieser Reihe
#: NICHT. Ohne diesen Satz liest sich „60,8 Mio. € gebaut" als Gesamtbild der
#: städtischen Bautätigkeit, und das ist es nicht.
ABGRENZUNG = ("Rechnungsergebnisse der Kernverwaltung: was im Haushaltsjahr "
              "tatsächlich für Investitionen abgeflossen ist. Ohne die "
              "Eigenbetriebe und ohne die städtischen Gesellschaften — was "
              "etwa die Gebäudewirtschaft baut, steht hier nicht.")

#: Die beiden Rechnungswesen, unter denen die Stadt gezählt hat.
#: Schlüssel → wie es auf der Seite heißt.
REGELWERK: dict[str, str] = {
    "kameral": "Kamerales Rechnungswesen (bis 2009)",
    "doppik": "Doppisches Rechnungswesen (ab 2010)",
}

#: Die Wertspalten je Tabelle, in ihrer Reihenfolge — Feldname und die
#: Überschrift, wie die Tabelle sie schreibt. Die letzte ist jeweils die
#: Summenspalte und damit das Ziel der Probe; alle davor sind die Arten.
#:
#: Die Feldnamen sind je Regelwerk EIGENE, auch wo sich zwei Überschriften
#: ähneln: „Neuanschaffungen von beweglichen Vermögen" (kameral) und „Erwerb
#: von beweglichem Sachvermögen" (doppisch) sind zwei Begriffe aus zwei
#: Rechnungswesen. Ein gemeinsamer Feldname lüde dazu ein, sie zu einer Reihe
#: zu verbinden — genau das, was die Fußnote des Dokuments untersagt.
SPALTEN: dict[str, tuple[tuple[str, str], ...]] = {
    "kameral": (
        ("darlehen", "Gewährung von Darlehen"),
        ("grundvermoegen", "Erwerb von Grundvermögen"),
        ("baumassnahmen_k", "Baumaßnahmen"),
        ("bewegliches_k", "Neuanschaffungen von beweglichen Vermögen"),
        ("insgesamt", "insgesamt"),
    ),
    "doppik": (
        ("zuwendungen", "Aktivierbare Zuwendungen"),
        ("grundstuecke", "Erwerb von Grundstücken und Gebäuden"),
        ("baumassnahmen", "Baumaßnahmen"),
        ("bewegliches", "Erwerb von beweglichem Sachvermögen"),
        ("finanzanlagen", "Erwerb von Finanzanlagevermögen"),
        ("sonstige", "Sonstige Investitionstätigkeit"),
        ("insgesamt", "insgesamt"),
    ),
}

#: Die Arten je Regelwerk — alles außer der Summenspalte.
ARTEN: dict[str, tuple[str, ...]] = {
    r: tuple(f for f, _ in s[:-1]) for r, s in SPALTEN.items()
}

#: Erkennt die beiden Tabellen. ``1107-1`` muss VOR ``1107`` geprüft werden,
#: sonst schluckt das kürzere Muster den längeren Titel.
#:
#: Die Jahresspanne endet mit einer optionalen Ziffer: Im Textextrakt klebt die
#: Fußnotenmarke an der Jahreszahl (``2010 bis 20251``). Fünfstellige Jahre gibt
#: es nicht, die Ziffer ist also eindeutig die Marke — s. Modulkopf.
_TITEL: dict[str, re.Pattern] = {
    "doppik": re.compile(
        r"1107-1\s+Auszahlungen der Stadt Oldenburg für Investitionstätigkeiten\s+"
        r"in Tausend Euro\s+((?:19|20)\d\d)\s+bis\s+((?:19|20)\d\d)\d?"),
    "kameral": re.compile(
        r"1107\s+Ausgaben der Stadt Oldenburg für eigene Investitionen\s+"
        r"in Tausend Euro\s+((?:19|20)\d\d)\s+bis\s+((?:19|20)\d\d)\d?"),
}

#: Eine Datenzeile beginnt mit der Jahreszahl in der ersten Spalte.
_ZEILE = re.compile(r"^((?:19|20)\d\d)\s+(\S.*)$")

#: Ein Tabellenfeld: deutsche Tausendergruppen, dahinter höchstens eine
#: Fußnotenziffer. Wie in ``council/schulden.py`` sind die Dreiergruppen der
#: Trick — ``\.\d{3}`` lässt eine fünfte Ziffer gar nicht erst zur Zahl
#: gehören, sodass aus ``26.5981`` nicht 265.981 wird.
_ZELLE = re.compile(r"^(\d{1,3}(?:\.\d{3})*)([1-9])?$")

#: Die Quelle rechnet in Tausend Euro, gespeichert wird wie überall im
#: Bereich in Euro.
TAUSEND = 1000


def de_zahl(zahl: float, nachkomma: int = 0, vorzeichen: bool = False) -> str:
    """Eine Zahl in deutscher Schreibweise: 1.304.000 statt 1,304,000.

    Steht in den Gründen der verworfenen Jahrgänge und im Beleg-Messwert —
    beides liest ein Mensch. Ein Helfer und kein ``.replace`` auf dem ganzen
    Satz: Das verwandelte auch ein Dezimalkomma in einen Punkt und schriebe
    aus „60,8 Mio. €" ein „60.8 Mio. €"."""
    text = f"{zahl:{'+' if vorzeichen else ''},.{nachkomma}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _zelle(feld: str) -> float | None:
    """Ein Tabellenfeld → Zahl, oder ``None``, wenn es keine ist.

    Ohne Tausenderpunkt gilt das Feld ungeteilt: ``239`` sind 239 und nicht 23
    mit Fußnote 9. Die Tabelle setzt bei jedem vierstelligen Wert einen Punkt;
    eine Fußnote an einem punktlosen Feld gäbe es nur bei einem Formatwechsel,
    und dann soll die Zahl lieber unverändert durch die Probe fallen, als still
    um eine Stelle zu schrumpfen. (Wortgleich zu ``schulden._zelle`` gedacht,
    aber ohne das ``r`` für „revidiert" — 1107 kennt keine revidierten Werte.)
    """
    feld = feld.strip()
    if "." not in feld:
        return float(feld) if feld.isdigit() else None
    m = _ZELLE.match(feld)
    return float(m.group(1).replace(".", "")) if m else None


def erkenne(text: str) -> dict[str, tuple[int, int]]:
    """Welche der beiden Tabellen steckt im Text — und welche Spanne deckt sie?

    Rückgabe ``{regelwerk: (von, bis)}``, leer wenn keine gefunden wurde. Die
    Spannen kommen aus den Titeln und nicht aus den gelesenen Zeilen: Sie sind
    damit Angaben des Dokuments, gegen die sich prüfen lässt, ob der Parser
    alle Jahrgänge erwischt hat (:func:`lies` tut das)."""
    flach = re.sub(r"\s+", " ", text or "")
    gefunden: dict[str, tuple[int, int]] = {}
    for regelwerk, muster in _TITEL.items():
        m = muster.search(flach)
        if m:
            gefunden[regelwerk] = (int(m.group(1)), int(m.group(2)))
    return gefunden


def _abschnitte(text: str) -> dict[str, str]:
    """Den Volltext in die beiden Tabellenabschnitte zerlegen.

    Beide stehen in derselben Datei und auf derselben Seite, untereinander.
    Getrennt wird am Titel von 1107-1 — alles davor gehört zu 1107, alles
    danach zu 1107-1. Ohne diesen Schnitt liefen die kameralen Zeilen (fünf
    Felder) und die doppischen (sieben) durch dieselbe Feldzahl-Prüfung, und
    eine der beiden Tabellen fiele komplett als „unlesbar" heraus.

    Fehlt der Titel von 1107-1, ist der ganze Text ein kameraler Abschnitt —
    das ist der Fall, wenn die Stadt die Tabellen eines Tages wieder trennt.
    """
    zeilen = (text or "").splitlines()
    schnitt = next((i for i, z in enumerate(zeilen) if "1107-1" in z), None)
    if schnitt is None:
        return {"kameral": text or ""}
    return {"kameral": "\n".join(zeilen[:schnitt]),
            "doppik": "\n".join(zeilen[schnitt:])}


def parse(text: str, regelwerk: str) -> list[dict]:
    """Die Datenzeilen **eines** Abschnitts → je Jahrgang ein dict in Euro.

    Die Quelle rechnet in Tausend Euro; die dabei behauptete Genauigkeit ist
    die der Quelle — auf Tausend gerundet, und das bleibt sie auch nach der
    Multiplikation.

    Zeilen, deren Felderzahl nicht zum Regelwerk passt, werden als
    ``unlesbar`` markiert statt zurechtgebogen; welche das waren, sagt
    :func:`lies`."""
    spalten = SPALTEN[regelwerk]
    zeilen: list[dict] = []
    for roh in (text or "").splitlines():
        m = _ZEILE.match(roh.strip())
        if not m:
            continue
        felder = [_zelle(f) for f in m.group(2).split()]
        if len(felder) != len(spalten) or any(w is None for w in felder):
            zeilen.append({"jahr": int(m.group(1)), "regelwerk": regelwerk,
                           "unlesbar": roh.strip()})
            continue
        zeile: dict = {"jahr": int(m.group(1)), "regelwerk": regelwerk,
                       "unlesbar": None}
        for (feld, _), wert in zip(spalten, felder):
            zeile[feld] = wert * TAUSEND
        zeilen.append(zeile)
    return zeilen


def zeilensumme(zeile: dict) -> tuple[bool, float]:
    """Ergeben die Auszahlungsarten die ausgewiesene Summe der Zeile?

    Rückgabe ``(bestanden, Abweichung in Euro)``. Ohne Toleranz: Die Quelle
    rundet jede Spalte auf volle Tausend und geht in 22 von 23 Jahrgängen auf
    den Euro auf. Eine Toleranz würde hier nur den einen Jahrgang durchwinken,
    für den sie gedacht wäre — und der ist mit 1,3 Mio. € ohnehin zu weit weg,
    um von einer Rundungstoleranz gedeckt zu sein."""
    arten = ARTEN[zeile["regelwerk"]]
    summe = sum(zeile.get(a) or 0.0 for a in arten)
    abweichung = summe - (zeile.get("insgesamt") or 0.0)
    return abweichung == 0.0, abweichung


def lies(text: str) -> dict:
    """Beide Tabellen einlesen und jeden Jahrgang durch die Probe schicken.

    Rückgabe:

    ``zeilen``
        Die übernommenen Jahrgänge, aufsteigend. Jede trägt ihr ``regelwerk``.
    ``verworfen``
        Jahrgänge, die die Probe nicht bestanden haben, mit ``grund`` und
        ``differenz``. Ihre sieben Zahlen stehen nirgends in der Datenbank —
        anders als bei den Schulden gibt es hier keine zweite Probe, die
        wenigstens die Summe trüge (s. Modulkopf).

        ``differenz`` ist die gemessene Lücke in Euro (Arten minus
        ausgewiesene Summe, vorzeichenbehaftet) — als **Zahl** neben dem
        Fließtext und nicht nur in ihm. Der Grund ist ein Satz für Menschen;
        die Zahl daraus zurückzuparsen wäre eine zweite, stille Schnittstelle.
        Dieselbe Rolle wie ``aufteilung_verworfen`` bei den Schulden
        (``council/schulden.py``): Sie hält fest, wie groß die Lücke war,
        damit die Seite die Lücke **beziffern** kann statt sie nur zu
        behaupten. ``None``, wo es nichts zu messen gab — eine Zeile, die
        sich nicht einmal in ihre Felder zerlegen ließ, hat keine Differenz,
        und eine erfundene Null wäre dort die Behauptung „es passte genau".
    ``spannen``
        Was die Titel für jede Tabelle ankündigen.
    ``fehlende_jahrgaenge``
        Was daraus fehlt, je Regelwerk. Ein Befund, keine Geschmacksfrage.
    ``proben``
        Was gerechnet wurde, in Zahlen — Grundlage des Beleg-Texts.
    """
    spannen = erkenne(text)
    zeilen: list[dict] = []
    verworfen: list[dict] = []
    bestanden = gerissen = 0

    for regelwerk, abschnitt in _abschnitte(text).items():
        if regelwerk not in spannen:
            # Kein Titel, keine Tabelle: Ein Abschnitt ohne seinen eigenen
            # Titel ist Beifang aus dem Seitenkopf und keine Datenquelle.
            continue
        for zeile in parse(abschnitt, regelwerk):
            if zeile.get("unlesbar"):
                verworfen.append({
                    "jahr": zeile["jahr"], "regelwerk": regelwerk,
                    # Keine Differenz: Ohne zerlegte Felder gibt es keine
                    # Summe, die man gegen die ausgewiesene halten könnte.
                    "differenz": None,
                    "grund": f"Zeile nicht in {len(SPALTEN[regelwerk])} Felder "
                             f"zerlegbar: {zeile['unlesbar']!r}"})
                continue
            ok, abweichung = zeilensumme(zeile)
            bestanden += bool(ok)
            gerissen += not ok
            if not ok:
                verworfen.append({
                    "jahr": zeile["jahr"], "regelwerk": regelwerk,
                    # Die Zahl neben dem Satz — s. Rückgabe-Beschreibung.
                    "differenz": abweichung,
                    "grund": f"Zeilensumme um "
                             f"{de_zahl(abweichung, vorzeichen=True)} € gerissen; "
                             f"eine zweite Probe trägt diese Tabelle nicht"})
                continue
            uebernommen = dict(zeile)
            uebernommen.pop("unlesbar", None)
            uebernommen["probe"] = "investitionen_ist_zeilensumme"
            zeilen.append(uebernommen)

    zeilen.sort(key=lambda z: z["jahr"])
    luecken: dict[str, list[int]] = {}
    for regelwerk, (von, bis) in spannen.items():
        da = {z["jahr"] for z in zeilen if z["regelwerk"] == regelwerk}
        fehlt = [j for j in range(von, bis + 1) if j not in da]
        if fehlt:
            luecken[regelwerk] = fehlt

    return {
        "zeilen": zeilen,
        "verworfen": verworfen,
        "spannen": spannen,
        "fehlende_jahrgaenge": luecken,
        "proben": {"bestanden": bestanden, "gerissen": gerissen},
    }


def probennachweis(ergebnis: dict) -> str:
    """Der Messwert für die Herkunft — „was ist wirklich gelaufen?".

    Steht später im Beleg auf der Seite; deshalb Zahlen und keine Adjektive."""
    p = ergebnis["proben"]
    gesamt = p["bestanden"] + p["gerissen"]
    text = f"Zeilensumme {p['bestanden']} von {gesamt} Jahrgängen"
    if p["gerissen"]:
        jahre = ", ".join(str(v["jahr"]) for v in ergebnis["verworfen"])
        text += f"; verworfen: {jahre}"
    return text
