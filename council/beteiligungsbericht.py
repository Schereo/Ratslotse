"""Der Beteiligungsbericht — was die städtischen Gesellschaften eigentlich tun.

Der Konzernabschluss (``council/konzernabschluss.py``) sagt, **wie viel** Geld
die Stadt mit allen Eigenbetrieben und Beteiligungen bewegt: 2024 rund
1,24 Mrd. Euro statt der 799 Mio. der Kernverwaltung. Was diese Betriebe
*machen*, steht dort nicht — nur ihre Beiträge zur Ergebnisrechnung.

Das sagt der Beteiligungsbericht nach § 151 NKomVG. Die Stadt legt ihn einmal
im Jahr vor, rund 200 Seiten, und führt darin jede Gesellschaft mit demselben
Aufbau: Gegenstand, Beteiligungsverhältnisse, Aufsichtsorgane, Beteiligungen,
Geschäftsverlauf, Bilanz und Kennzahlen, öffentlicher Zweck, Auswirkungen auf
den Haushalt.

Woher die Dokumente kommen
---------------------------
**Nicht aus dem Ratsinformationssystem.** Sie stehen auf oldenburg.de und
werden von ``scripts/check_beteiligungsbericht.py`` heruntergeladen — der
erste Cron dieses Bereichs, der selbst ins Netz greift. ``check_finanzdaten``
tut das bewusst nicht; die Begründung steht in seinem Modulkopf.

Welche Jahrgänge — und warum nicht alle sieben
-----------------------------------------------
Auf oldenburg.de stehen sieben Jahrgänge (2018–2024). Gelesen werden **2022,
2023 und 2024**. Der Grund ist kein Ehrgeiz, sondern ein Formatbruch: Mit dem
Bericht für 2022 hat die Stadt das Dokument umgestellt.

============================  ===================  ====================
                              2018–2021            ab 2022
============================  ===================  ====================
Gliederung je Gesellschaft    frei betextet        acht nummerierte
                                                   Abschnitte ``1)``–``8)``
Bilanz                        Aktiva und Passiva   einspaltig, mit
                              **nebeneinander**    ``BILANZSUMME`` auf
                                                   beiden Seiten
Kennzahlen                    keine Tabelle        „Kennzahlen im
                                                   Zeitverlauf", 4–5 Jahre
============================  ===================  ====================

Gemessen am Bestand: „Kennzahlen im Zeitverlauf" kommt in den Jahrgängen
2018–2021 **null**-mal vor, ab 2022 je 14–16-mal (einmal pro Gesellschaft).
``BILANZSUMME`` ebenso: null gegen 28–32. Die zweispaltige Bilanz der alten
Jahrgänge verschränkt pypdf zu Zeilen, in denen Aktiv- und Passivbeträge
abwechselnd stehen — dort eine Zahl zu greifen hieße raten.

Der Verzicht kostet **nichts an Zahlen**: Die Kennzahlen-Tabellen der neuen
Berichte reichen selbst bis 2017 zurück (jede führt vier bis fünf Jahre). Der
Bestand deckt damit 2017–2024, aus Dokumenten, die ihre Rechenproben
mitbringen. Was fehlt, ist der *Fließtext* der Jahre 2018–2021 — und die Frage
„was macht die GSG eigentlich?" beantwortet ohnehin der jüngste Bericht.

Die Proben
-----------
Für die **Kennzahlen** gilt die Probenpflicht des Bereichs. Drei Proben, alle
im Dokument selbst dokumentiert:

``beteiligung_bilanzprobe``
    Die Bilanz weist ihre Summe zweimal aus — unter AKTIVA und unter PASSIVA —
    und die Kennzahlen-Tabelle desselben Abschnitts nennt sie ein drittes Mal.
    Drei Stellen, eine Zahl.

``beteiligung_ergebnisprobe``
    Dasselbe für das Jahresergebnis: Die Gewinn- und Verlustrechnung schließt
    mit dem Betrag, den die Kennzahlen-Tabelle führt.

``beteiligung_ueberlappung``
    Jeder Bericht führt vier bis fünf Jahre. Ein Jahr steht deshalb in bis zu
    drei Berichten — aus verschiedenen Veröffentlichungen, und sie müssen
    übereinstimmen.

Die ersten beiden decken auch den **jüngsten** Jahrgang ab, den die
Überlappung noch nicht bestätigen kann: Er steht bisher nur in einem Bericht.

Was **keine** dieser Proben deckt, ist die Eigenkapitalquote: Sie ist eine
abgeleitete Größe, und das Dokument leitet sie nirgends nach. Für die Jahre,
die in mehreren Berichten stehen, greift die Überlappung; für das jüngste Jahr
gibt es keine Probe, und dieser Wert wird nicht gespeichert. Er kommt mit dem
nächsten Bericht.

Für **Fließtext** (Gegenstand, Aufsichtsorgane, Auswirkungen) gibt es keine
Probe, und es wäre unredlich, eine zu erfinden: Diese Angaben stehen einmal im
Dokument und lassen sich gegen nichts rechnen. Sie tragen deshalb
``herkunft.UNGEPRUEFT``, und das steht auch auf der Seite.

Der Abgleich mit dem Gesamtabschluss — nachgerechnet
------------------------------------------------------
Dieselben Gesellschaften stehen auch im konsolidierten Gesamtabschluss
(``council_konzern_traeger``), dort mit ihren *ordentlichen Erträgen* und
*Aufwendungen* in Tausend Euro. Deren Differenz ist der Beitrag der
Gesellschaft zum Konzernergebnis — und damit die einzige Zahl beider
Dokumente, die sich überhaupt vergleichen lässt.

Nachgerechnet für 2024 (Gesamtabschluss zum 31.12.2024 gegen den
Beteiligungsbericht 2024, alles in TEUR):

===============================  ============  =============  ==========
Gesellschaft                     Konzern E−A   Jahresergebnis  Differenz
===============================  ============  =============  ==========
Klinikum Oldenburg AöR               −27.132        −27.132           0
Weser-Ems Halle                       −4.378         −4.378           0
Bäderbetriebsgesellschaft             −5.699         −5.709          10
Eigenbetrieb Gebäudewirtschaft        −2.701         −2.726          25
Abfallwirtschaftsbetrieb                 231            294         −63
Bäderbetrieb                             233              0         233
Verkehr und Wasser GmbH                  −77              0         −77
===============================  ============  =============  ==========

Zwei stimmen auf die Tausenderstelle, drei liegen dicht daneben, zwei
weichen deutlich ab. Das ist **kein Fehler**, sondern der Unterschied der
beiden Rechnungen:

- Der Gesamtabschluss zählt die *ordentlichen* Posten. Das Jahresergebnis der
  Gesellschaft enthält zusätzlich Steuern und einmalige Posten — daher die
  kleinen Abweichungen bei AWB, EGH und BBGO.
- Bäderbetrieb und Verkehr und Wasser weisen ein Jahresergebnis von **0,00 €**
  aus, weil ihr Ergebnis abgeführt beziehungsweise ausgeglichen wird. Der
  Konzern zeigt trotzdem, was sie erwirtschaftet haben. Beide Zahlen stimmen;
  sie beantworten verschiedene Fragen.

Deshalb ist das **keine Probe**. Eine Toleranz, die 233 TEUR durchgehen ließe,
prüfte bei der Bäderbetriebsgesellschaft nichts mehr, und eine engere
verwürfe die beiden Betriebe mit Ergebnisabführung — also gerade die, bei
denen die Quelle nachweislich recht hat. Was die Kennzahlen absichert, sind
die drei Proben oben.

Was der Abgleich stattdessen ist: eine **Einordnung**, und dafür wird er
gerechnet (:func:`konzernvergleich`). Der Cron protokolliert ihn bei jedem
Lauf, und die Seite zeigt beide Zahlen nebeneinander. Springt eine Abweichung,
die jahrelang null war, plötzlich auf Millionen, ist das den Blick wert —
nur eben als Frage, nicht als Urteil.

Die Zuordnung Abschnitt → Gesellschaft
---------------------------------------
Der eigentliche Fallstrick bei 200 Seiten: Welcher Abschnitt gehört zu wem?
Der Bericht beantwortet das selbst zweimal. Das Inhaltsverzeichnis nennt für
jede Gesellschaft ihre Gliederungsnummer und ihre Anfangsseite; auf genau
dieser Seite steht eine Trennseite, die dieselbe Nummer trägt. Stimmen beide
nicht überein, ist die Zuordnung nicht gesichert und der Jahrgang fällt weg
(:func:`classification`). In allen drei gelesenen Jahrgängen gehen 45 von 45
Zuordnungen auf.

Fünf Eigenheiten, an denen ein naiver Parser scheitert
-------------------------------------------------------
**Die Jahresspalten wechseln die Richtung.** Der EGH führt 2024 → 2020, der
AWB auf der übernächsten Seite 2020 → 2024. Wer die Reihenfolge annimmt,
schreibt die Zeitreihe rückwärts. Gelesen wird deshalb die Kopfzeile.

**Der Berichtsjahrgang steht nicht immer in der Tabelle.** Die Großleitstelle
führt noch im Bericht für 2024 die Jahre 2017–2021 — ihr Abschluss lag später
vor. Ein Parser, der „die letzte Spalte ist das Berichtsjahr" annimmt, legt
2021er-Zahlen unter 2024 ab.

**Beträge tragen Leerzeichen mitten drin.** ``650 .289,04``,
``23.439 .654,83``, ``376 .737.113,54`` — der Extrakt setzt Leerraum um den
Tausenderpunkt. :func:`_betrag` räumt das weg.

**Die Beschriftung schwankt.** ``Eigenkapitalquote``, ``Eigenkapitaquote``
(Tippfehler im Bericht 2022), ``Eigenkapital-\\nquote``,
``Eigenkapital -\\nQuote in Prozent``; die Einheit steht mal in Klammern, mal
ohne, mal auf der nächsten Zeile.

**Manche Zahl ist im Dokument falsch gesetzt.** Der Bericht 2022 führt für die
GSG ein Jahresergebnis ``5.698.082.44`` — Punkt statt Komma. Das ist kein
Betrag, und die Zeile wird verworfen statt zurechtgebogen. Im Bericht 2024
beginnt dieselbe Reihe erst 2020 und geht durch.

Was hier **nicht** gelesen wird
--------------------------------
Die beteiligungsspezifischen Kennzahlen (Fahrgastzahlen, Gästezahlen,
Abfallmengen) stehen je Gesellschaft in einer eigenen Tabelle mit eigenen
Zeilen — für die gibt es keine Probe und keine gemeinsame Einheit. Sie sind
lesenswert, aber nichts, was sich vergleichen ließe.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# --- Erkennung --------------------------------------------------------------

#: Der Bericht nennt sich auf jeder Seite in der Kopfzeile selbst beim Namen.
_TITEL = re.compile(
    r"Beteiligungsbericht\s+(?:für das Berichtsjahr\s+)?(20\d\d)")

#: Ab diesem Jahrgang trägt der Bericht die acht nummerierten Abschnitte und
#: die Kennzahlen-Tabellen. Alles davor ist ein anderes Dokument (s. Modulkopf)
#: — nicht „schlechter lesbar", sondern anders aufgebaut.
ERSTER_JAHRGANG = 2022


def budget_year(kopf: str | None) -> int | None:
    """Für welches Berichtsjahr ein Dokument gilt — ``None``, wenn unklar."""
    m = _TITEL.search(" ".join((kopf or "").split())[:4000])
    return int(m.group(1)) if m else None


# --- Gesellschaften ---------------------------------------------------------

#: Stabile Schlüssel je Gesellschaft: Muster auf den Namen → Schlüssel,
#: Anzeigename, und der passende Träger im Konzernabschluss.
#:
#: Der Schlüssel hängt bewusst **nicht** an der Gliederungsnummer: Die
#: verschiebt sich, sobald eine Gesellschaft dazukommt (die Stadion-
#: Gesellschaften haben 2023/2024 genau das getan). Und nicht am Wortlaut:
#: „Bäderbetrieb der Stadt Oldenburg (Oldb)" ist derselbe Betrieb wie
#: „Bäderbetrieb der Stadt Oldenburg".
#:
#: ``consolidated_key`` verweist auf ``konzernabschluss.TRAEGER`` — damit ist die
#: Gegenprobe ein Join und keine Namensraterei. Wo er ``None`` ist, führt der
#: Gesamtabschluss die Gesellschaft nicht als eigenen Träger; sie steckt dann
#: in der Konsolidierung oder ist zu klein für eine eigene Zeile.
GESELLSCHAFTEN: tuple[tuple[str, str, str, str | None], ...] = (
    ("egh", r"^eigenbetrieb gebäudewirtschaft",
     "Eigenbetrieb Gebäudewirtschaft und Hochbau", "egh"),
    ("awb", r"^abfallwirtschaftsbetrieb",
     "Abfallwirtschaftsbetrieb Stadt Oldenburg", "awb"),
    ("bbo", r"^bäderbetrieb der stadt",
     "Bäderbetrieb der Stadt Oldenburg", "bbo"),
    ("klinikum", r"^klinikum oldenburg",
     "Klinikum Oldenburg AöR", "klinikum"),
    ("gol", r"^großleitstelle",
     "Großleitstelle Oldenburger Land AöR", None),
    # Reihenfolge: die Beteiligungs-GmbH zuerst, sonst schluckt das kürzere
    # Muster der KG sie mit.
    ("weh_komplementaer", r"^weser-ems halle oldenburg beteiligungs",
     "Weser-Ems Halle Oldenburg Beteiligungs-GmbH", None),
    ("weh", r"^weser-ems halle",
     "Weser-Ems Halle Oldenburg GmbH & Co. KG", "weh"),
    ("bbgo", r"^bäderbetriebsgesellschaft",
     "Bäderbetriebsgesellschaft Oldenburg mbH", "bbgo"),
    ("tgo_besitz", r"^tgo besitz",
     "TGO Besitz GmbH & Co. KG", None),
    ("tgo", r"^tgo technologie",
     "TGO Technologie- und Gründerzentrum Oldenburg GmbH", None),
    ("otm", r"^oldenburg tourismus",
     "Oldenburg Tourismus und Marketing GmbH", None),
    ("vhs", r"^volkshochschule",
     "Volkshochschule Oldenburg gGmbH", None),
    ("vwg", r"^verkehr und wasser",
     "Verkehr und Wasser GmbH", "vwg"),
    ("gsg", r"^gsg oldenburg",
     "GSG Oldenburg Bau- und Wohngesellschaft mbH", None),
    ("stadion_komplementaer", r"^stadion oldenburg beteiligungs",
     "Stadion Oldenburg Beteiligungs-GmbH", None),
    ("stadion", r"^stadion oldenburg gmbh",
     "Stadion Oldenburg GmbH & Co. KG", None),
    ("stadionplanung", r"^stadionplanungsgesellschaft",
     "Stadionplanungsgesellschaft mbH", None),
)


def _slug(name: str) -> str:
    """Notschlüssel für eine Gesellschaft, die die Liste noch nicht kennt.

    Eine neue Beteiligung soll nicht stillschweigend verlorengehen, nur weil
    niemand sie eingetragen hat — sie kommt mit einem abgeleiteten Schlüssel
    herein, und der Lauf sagt es. Der Eintrag in :data:`GESELLSCHAFTEN` wird
    trotzdem nachgeholt: Nur er hält den Schlüssel über eine Umfirmierung
    hinweg stabil."""
    roh = unicodedata.normalize("NFKD", name.lower())
    roh = roh.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    roh = "".join(c for c in roh if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", roh).strip("_")[:40] or "unbekannt"


def erkenne_gesellschaft(name: str) -> tuple[str, str, str | None, bool]:
    """Name aus dem Bericht → ``(key, anzeigename, consolidated_key, bekannt)``."""
    klein = " ".join((name or "").lower().split())
    for key, muster, anzeige, konzern in GESELLSCHAFTEN:
        if re.match(muster, klein):
            return key, anzeige, konzern, True
    return _slug(name), " ".join((name or "").split()), None, False


#: Eine Zeile des Inhaltsverzeichnisses: „2.4.9 GSG Oldenburg … ....... 190".
_IVZ = re.compile(r"^(2\.\d+\.\d+)\s+(.+?)\s*\.{3,}\s*(\d+)\s*$")
#: Eine Trennseite trägt nur die Gliederungsnummer, allein auf einer Zeile.
_TRENN = re.compile(r"^\s*(2\.\d+\.\d+)\s*$", re.M)

#: Die Fußzeile zählt ohne das Titelblatt: PDF-Seite = Fußzeilenzahl + 1. Das
#: Inhaltsverzeichnis nennt die Fußzeilenzahl.
SEITENVERSATZ = 1


@dataclass
class Gesellschaft:
    """Eine Gesellschaft in einem Berichtsjahrgang."""

    key: str
    name: str
    classification: str
    #: PDF-Seite der Trennseite (1-basiert).
    page: int
    #: Fußzeilen-Seite — die steht im Inhaltsverzeichnis und im Dokument.
    seite_gedruckt: int
    consolidated_key: str | None = None
    bekannt: bool = True
    abschnitte: dict[str, str] = field(default_factory=dict)
    kennzahlen: dict[str, dict[int, float]] = field(default_factory=dict)
    #: Bilanzsummen aus der Bilanz, je Stichtagsjahr.
    bilanzsummen: dict[int, float] = field(default_factory=dict)
    #: Jahresergebnisse aus der Gewinn- und Verlustrechnung, je Stichtagsjahr.
    guv: dict[int, float] = field(default_factory=dict)


def classification(seiten: list[str]) -> tuple[list[Gesellschaft], list[str]]:
    """Welche Gesellschaft ab welcher Seite — und ob das Dokument es bestätigt.

    Zwei unabhängige Angaben desselben Berichts: das Inhaltsverzeichnis (Nummer
    → Anfangsseite) und die Trennseiten (Seite → Nummer). Übernommen wird nur,
    was beide gleich sehen. Eine Gesellschaft, bei der sie auseinanderlaufen,
    fällt heraus und wird gemeldet — dann stimmt entweder der Extrakt nicht
    oder der Aufbau hat sich geändert, und beides ist ein Grund, nichts zu
    speichern.

    Liefert ``(gesellschaften, warnungen)``."""
    kopf = "\n".join(seiten[:14])
    ivz: dict[str, tuple[str, int]] = {}
    for roh in kopf.split("\n"):
        m = _IVZ.match(" ".join(roh.split()))
        if m:
            ivz[m.group(1)] = (m.group(2), int(m.group(3)))

    aus: list[Gesellschaft] = []
    warnungen: list[str] = []
    gesehen: set[str] = set()
    for i, text in enumerate(seiten, 1):
        m = _TRENN.search(text or "")
        if not m:
            continue
        nr = m.group(1)
        if nr in gesehen:
            continue
        eintrag = ivz.get(nr)
        if not eintrag:
            warnungen.append(f"Trennseite {nr} auf Seite {i} steht nicht im "
                             f"Inhaltsverzeichnis — Abschnitt übersprungen")
            continue
        name, gedruckt = eintrag
        if gedruckt + SEITENVERSATZ != i:
            warnungen.append(
                f"{nr} „{name}“: Inhaltsverzeichnis nennt Seite {gedruckt}, die "
                f"Trennseite steht auf {i - SEITENVERSATZ} — Zuordnung nicht "
                f"gesichert, Abschnitt übersprungen")
            continue
        gesehen.add(nr)
        key, anzeige, konzern, bekannt = erkenne_gesellschaft(name)
        if not bekannt:
            warnungen.append(f"„{name}“ steht noch nicht in "
                             f"beteiligungsbericht.GESELLSCHAFTEN — "
                             f"Notschlüssel {key!r}")
        aus.append(Gesellschaft(key=key, name=anzeige, classification=nr, page=i,
                                seite_gedruckt=gedruckt, consolidated_key=konzern,
                                bekannt=bekannt))
    for nr, (name, _) in sorted(ivz.items()):
        if nr not in gesehen and not any(w.startswith(nr) for w in warnungen):
            warnungen.append(f"{nr} „{name}“ steht im Inhaltsverzeichnis, hat "
                             f"aber keine Trennseite — Abschnitt übersprungen")
    return aus, warnungen


# --- Beträge ----------------------------------------------------------------

#: Ein Zahlwert, so großzügig gefasst, wie der Extrakt ihn setzt: Vorzeichen
#: mit oder ohne Abstand, Leerraum um die Tausenderpunkte, Nachkommastellen
#: freiwillig (die Volkshochschule führt ein Jahresergebnis schlicht als „0").
_ZAHL = re.compile(r"[-–−]?\s?[\d.\s]*\d(?:,\d{1,2})?")

#: Einheiten und Beschriftungsreste, die zwischen den Zahlen stehen.
_EINHEIT = re.compile(r"\(?\s*[iI]n\s+(?:Euro|Prozent)\s*\)?|Quote|€|%", re.I)


def _entzerren(text: str) -> str:
    """Leerraum aus den Beträgen räumen, an genau drei Stellen.

    ``650 .289,04`` und ``376 .737.113,54`` stehen so im Extrakt, ebenso
    ``2.103.265, 69`` und ``25.000 ,00`` (Beteiligungsverhältnisse der
    Weser-Ems Halle Beteiligungs-GmbH im Bericht 2023). Es ist dieselbe Sorte
    Schaden, die schon der Gesamtabschluss zeigt (``105.667.339, 23``, s.
    ``council/konzernabschluss.py``): Der Satz bricht die Zahl, der Extraktor
    sieht ein Leerzeichen.

    Angefasst wird nur, was strukturell eine Zahl sein **muss**: ein Punkt mit
    genau drei folgenden Ziffern (Tausendertrennung) und ein Komma mit genau
    zwei folgenden Ziffern (Nachkommastellen) — davor wie dahinter. Ein Komma
    im Fließtext hat keine zwei Ziffern hinter sich, ein Satzpunkt keine
    drei."""
    text = text.replace("\u2013", "-").replace("\u2212", "-").replace("\u00a0", " ")
    text = re.sub(r"\s*\.\s*(?=\d{3}(?!\d))", ".", text)
    text = re.sub(r",\s+(?=\d{2}(?!\d))", ",", text)
    return re.sub(r"(?<=\d)\s+,(?=\d{2}(?!\d))", ",", text)


def _betrag(roh: str) -> float | None:
    """„- 2.726.407,50" → -2726407.5. ``None``, wenn es kein Betrag ist.

    Streng bei den Tausendergruppen: Nach dem ersten Punkt müssen es genau
    drei Ziffern sein. Genau daran scheitert ``5.698.082.44`` — der Tippfehler
    im Bericht 2022 (Punkt statt Komma), und er soll scheitern."""
    tok = re.sub(r"\s+", "", roh).replace("€", "").replace("%", "")
    neg = tok.startswith("-")
    tok = tok.lstrip("-+")
    if not tok:
        return None
    if "," in tok:
        ganz, _, dezimal = tok.rpartition(",")
        gruppen = ganz.split(".")
        if not dezimal.isdigit() or not all(g.isdigit() for g in gruppen):
            return None
        if len(gruppen) > 1 and any(len(g) != 3 for g in gruppen[1:]):
            return None
        wert = float(f"{''.join(gruppen)}.{dezimal}")
    else:
        gruppen = tok.split(".")
        if not all(g.isdigit() for g in gruppen):
            return None
        if len(gruppen) > 1 and any(len(g) != 3 for g in gruppen[1:]):
            return None
        wert = float("".join(gruppen))
    return -wert if neg else wert


def _zahlen(text: str) -> list[float]:
    """Alle Beträge einer Tabellenzeile, in der Reihenfolge des Dokuments."""
    return [w for t in _ZAHL.findall(_EINHEIT.sub(" ", text))
            if (w := _betrag(t)) is not None]


# --- Kennzahlen im Zeitverlauf ----------------------------------------------

#: Die Kennzahlen, die alle Gesellschaften gemeinsam führen. Der Rest der
#: Tabelle („Beteiligungsspezifische Kennzahlen") ist je Gesellschaft anders
#: und wird nicht gelesen.
KENNZAHLEN: tuple[tuple[str, str, str], ...] = (
    ("jahresergebnis", r"Jahresergebnis", "eur"),
    ("bilanzsumme", r"Bilanzsumme", "eur"),
    # „Eigenkapitaquote" ist der Tippfehler des Berichts 2022, „Eigenkapital-
    # Quote in Prozent" die Schreibweise des Klinikums.
    ("eigenkapitalquote", r"Eigenkapita\s*l?\s*-?\s*[qQ]uote", "prozent"),
)

_KENN_ANKER = re.compile(r"Kennzahlen im Zeitverlauf")
#: Steht „Beteiligungsspezifische" davor, ist es die andere Tabelle.
_SPEZIFISCH = re.compile(r"(?:Beteiligungs)?spezifische\s*$", re.I)
#: Die Kopfzeile: zwei bis sechs Jahreszahlen nebeneinander.
_JAHRZEILE = re.compile(r"((?:20\d\d[ \t]+){1,6}20\d\d)")
#: Die laufende Kopfzeile jeder Seite — sie darf nicht in eine Tabellenzeile
#: hineinlaufen.
_SEITENKOPF = re.compile(r"Stadt Oldenburg\s*[–-]\s*Beteiligungsbericht")


def kennzahlen(section: str) -> tuple[dict[str, dict[int, float]], list[str]]:
    """Die Tabelle „Kennzahlen im Zeitverlauf" eines Abschnitts lesen.

    Liefert ``({indicator: {year: wert}}, warnungen)``.

    Die Jahre kommen aus der Kopfzeile, nie aus der Reihenfolge: Der EGH führt
    2024 → 2020, der AWB 2020 → 2024 (s. Modulkopf). Und eine Zeile wird nur
    übernommen, wenn sie **genau so viele** Werte trägt wie die Kopfzeile
    Jahre hat. Alles andere hieße raten, welcher Wert zu welchem Jahr gehört —
    lieber keine Zeile als eine verschobene."""
    treffer = None
    for m in _KENN_ANKER.finditer(section):
        if _SPEZIFISCH.search(section[max(0, m.start() - 40):m.start()].rstrip()):
            continue
        treffer = m
        break
    if treffer is None:
        return {}, []

    ende = section.find("Beteiligungsspezifische", treffer.end())
    rumpf = _entzerren(section[treffer.end():ende if ende > 0 else treffer.end() + 900])

    jm = _JAHRZEILE.search(rumpf)
    if not jm:
        # „Historische Daten liegen noch nicht vor." — kein Fehler, nur nichts da.
        return {}, []
    jahre = [int(j) for j in jm.group(1).split()]
    rest = rumpf[jm.end():]

    stellen = []
    for key, muster, _ in KENNZAHLEN:
        m = re.search(muster, rest)
        if m:
            stellen.append((m.start(), m.end(), key))
    stellen.sort()

    reihen: dict[str, dict[int, float]] = {}
    warnungen: list[str] = []
    for i, (_, ab, key) in enumerate(stellen):
        bis = stellen[i + 1][0] if i + 1 < len(stellen) else len(rest)
        zeile = _SEITENKOPF.split(rest[ab:bis])[0]
        werte = _zahlen(zeile)
        if len(werte) == len(jahre):
            reihen[key] = dict(zip(jahre, werte))
        else:
            warnungen.append(
                f"{key}: {len(werte)} Werte für {len(jahre)} Jahre — Zeile "
                f"verworfen (Zuordnung Jahr↔Wert nicht gesichert)")
    return reihen, warnungen


# --- Bilanz -----------------------------------------------------------------

#: Die Bilanz weist ihre Summe unter AKTIVA und unter PASSIVA aus — in den
#: Jahrgängen ab 2022 in Großbuchstaben und einspaltig.
_BILANZSUMME = re.compile(r"BILANZSUMME\s*([^\n]*)")
#: Der Stichtagskopf der Bilanz: „31.12.2024 31.12.2023 31.12.2022".
_STICHTAGE = re.compile(r"((?:31\.12\.20\d\d\s+){1,5}31\.12\.20\d\d)")


def bilanzsummen(section: str) -> dict[int, float]:
    """Die Bilanzsumme je Stichtagsjahr — nur, wenn die Bilanz aufgeht.

    Die Probe ist die Bilanz selbst: Aktiva und Passiva müssen dieselbe Summe
    ausweisen. Weichen sie ab oder steht die Summe nur einmal da, gibt es
    nichts zurück — eine Bilanz, die nicht ausgeglichen ist, ist entweder
    falsch gelesen oder falsch gedruckt, und in beiden Fällen taugt sie nicht
    als Probe.

    Die Stichtagszeile wird **je Summenzeile** gesucht, und zwar rückwärts.
    Der erste Stichtagskopf des Abschnitts gehört nämlich oft gar nicht zur
    Bilanz: Die Verkehr und Wasser GmbH stellt ihre Lage im Geschäftsverlauf
    mit einer eigenen Zwei-Spalten-Übersicht dar („In tausend Euro 31.12.2024
    31.12.2023"), und wer deren Kopf auf die dreispaltige Bilanz anwendet,
    zählt zwei Jahre gegen drei Werte und verwirft eine Bilanz, die
    tadellos ist."""
    section = _entzerren(section)
    reihen: list[tuple[list[int], list[float]]] = []
    for m in _BILANZSUMME.finditer(section):
        koepfe = list(_STICHTAGE.finditer(section[:m.start()]))
        if not koepfe:
            continue
        jahre = [int(t.rsplit(".", 1)[1]) for t in koepfe[-1].group(1).split()]
        werte = _zahlen(m.group(1))
        if len(werte) == len(jahre):
            reihen.append((jahre, werte))
    if len(reihen) != 2 or reihen[0] != reihen[1]:
        return {}
    return dict(zip(reihen[0][0], reihen[0][1]))


#: Die Schlusszeile der Gewinn- und Verlustrechnung. Die Postennummer davor
#: schwankt zwischen den Gesellschaften (3., 9., 10., 11., 13.) — sie steht im
#: Muster, damit sie **nicht** als erster Betrag mitgelesen wird.
#: Der Rest der Zeile wird **ganz** aufgenommen, auch der Beschriftungsschwanz
#: („/-fehlbetrag", „(+) / Jahresfehlbetrag (-)"). Ihn per ``[^\n\d]*``
#: wegzuschneiden verschluckte das Minuszeichen des ersten Betrags — und aus
#: einem Fehlbetrag von 2,7 Mio. würde ein Überschuss. Beschriftungen tragen
#: keine Ziffern; was übrig bleibt, sortiert :func:`_zahlen` aus.
_GUV_SCHLUSS = re.compile(
    r"^[ \t]*\d{1,2}\.[ \t]*Jahres(?:überschuss|fehlbetrag|ergebnis)([^\n]*)$",
    re.M | re.I)


def guv_ergebnisse(section: str) -> dict[int, float]:
    """Das Jahresergebnis, wie die Gewinn- und Verlustrechnung es ausweist.

    Zweite, unabhängige Stelle für dieselbe Zahl — und die einzige, die auch
    den **jüngsten** Jahrgang deckt: Den kann die Überlappung noch nicht
    bestätigen, weil er erst in einem Bericht steht.

    Verglichen wird der **Betrag**, nicht das Vorzeichen. Das ist keine
    Nachlässigkeit, sondern die Quelle: Der Bericht setzt es uneinheitlich.
    Das Klinikum führt ``13. Jahresfehlbetrag 27.131.986,80`` ohne Minus, die
    Weser-Ems Halle ``13. Jahresfehlbetrag -4.378.473,17`` mit, und der
    Eigenbetrieb Gebäudewirtschaft schreibt ``13. Jahresüberschuss
    -2.726.407,50`` — Überschuss als Wort, Minus als Zahl. Wer daraus eine
    Vorzeichenregel bauen wollte, müsste eine erfinden. Das Vorzeichen deckt
    für alle übrigen Jahre die Überlappungsprobe ab.

    Nicht verwendet wird die Zeile ``V. Jahresüberschuss/Jahresfehlbetrag`` aus
    der Bilanz: Sie zeigt, was vom Ergebnis **im Unternehmen bleibt**. Die TGO
    weist dort 2023 und 2024 je 0,00 aus, weil der Gewinn abgeführt wurde,
    während die GuV 1.136,76 und 8.473,96 nennt. Beide stimmen — sie sagen
    Verschiedenes."""
    section = _entzerren(section)
    aus: dict[int, float] = {}
    for m in _GUV_SCHLUSS.finditer(section):
        koepfe = list(_STICHTAGE.finditer(section[:m.start()]))
        if not koepfe:
            continue
        jahre = [int(t.rsplit(".", 1)[1]) for t in koepfe[-1].group(1).split()]
        werte = _zahlen(m.group(1))
        if len(werte) == len(jahre):
            aus = dict(zip(jahre, werte))
    return aus


# --- Die acht Abschnitte ----------------------------------------------------

#: Welche der acht Abschnitte als Text gespeichert werden — Schlüssel, Nummer
#: im Bericht, Überschrift für die Seite.
#:
#: Nicht dabei sind 5) „Grundzüge des Geschäftsverlaufs" (der Lagebericht der
#: Gesellschaft, wörtlich übernommen, 10 bis 25 Seiten je Gesellschaft — das
#: ist ein eigenes Dokument im Dokument), 6) „Bilanzdaten" (der steht als
#: Zahlen in den Kennzahlen) und 7) „Vorliegen der Voraussetzungen des § 136"
#: (in allen 45 Abschnitten derselbe Satz: die Voraussetzungen sind erfüllt).
TEXTABSCHNITTE: tuple[tuple[str, int, str], ...] = (
    ("gegenstand", 1, "Was die Gesellschaft tut"),
    ("beteiligungsverhaeltnisse", 2, "Wem sie gehört"),
    ("aufsichtsorgane", 3, "Wer sie beaufsichtigt"),
    ("beteiligungen", 4, "Woran sie selbst beteiligt ist"),
    ("haushalt", 8, "Was sie für den städtischen Haushalt bedeutet"),
)

_ABSCHNITTSKOPF = re.compile(r"^[ \t]*([1-8])\)[ \t]+(\S[^\n]{2,150})$", re.M)

#: Kontaktangaben, die im Abschnitt „Besetzung der Aufsichtsorgane" mit auf der
#: Seite stehen. Sie gehören nicht zur Sache und werden nicht gespeichert:
#: Das Repo hält fremde E-Mail-Adressen bewusst draußen
#: (``scripts/lint_adressen.py``), und für eine Telefonnummer der Betriebs-
#: leitung gilt dasselbe. Die Namen der Aufsichtsratsmitglieder bleiben — sie
#: üben ein öffentliches Amt aus, und wer den Rat kontrolliert, ist der Punkt.
_KONTAKT = re.compile(
    r"^[ \t]*(?:E-?Mail|Telefon|Telefax|Fax|Internet|Anschrift)[ \t]*:.*$",
    re.M | re.I)
_ADRESSE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _ohne_kontakt(text: str) -> str:
    """Kontaktzeilen und E-Mail-Adressen aus einem Abschnitt entfernen."""
    return _ADRESSE.sub("", _KONTAKT.sub("", text)).strip()


def abschnitte(text: str) -> dict[str, str]:
    """Die acht nummerierten Abschnitte einer Gesellschaft trennen.

    Übernommen wird nur, was in der **Reihenfolge des Berichts** steht: Eine
    Überschrift zählt, wenn ihre Nummer größer ist als die zuletzt gefundene.
    Der Lagebericht in Abschnitt 5 gliedert sich selbst mit Aufzählungen, und
    ohne diese Regel risse ein „3)" mitten im Fließtext den Abschnitt an einer
    Stelle auf, an der keine Überschrift steht.

    Verlangt wird **aufsteigend**, nicht lückenlos. „Genau die nächste Nummer"
    wäre die schärfere Regel und die falsche: Fiele im Bericht einmal ein
    Abschnitt aus, verlöre sie stillschweigend auch alle danach. Gegen den
    Fließtext schützt schon das Aufsteigen — eine Aufzählung fängt wieder
    vorne an."""
    koepfe: list[tuple[int, int, int]] = []
    letzte = 0
    for m in _ABSCHNITTSKOPF.finditer(text):
        nr = int(m.group(1))
        if nr <= letzte:
            continue
        koepfe.append((nr, m.start(), m.end()))
        letzte = nr
    nach_nr = {nr: (start, ende) for nr, start, ende in koepfe}
    grenzen = [start for _, start, _ in koepfe] + [len(text)]

    aus: dict[str, str] = {}
    for key, nr, _ in TEXTABSCHNITTE:
        if nr not in nach_nr:
            continue
        _, ab = nach_nr[nr]
        bis = next((g for g in grenzen if g > ab), len(text))
        rumpf = _SEITENKOPF.split(text[ab:bis])[0]
        rumpf = _ohne_kontakt(re.sub(r"\n{3,}", "\n\n", rumpf))
        if rumpf:
            aus[key] = rumpf
    return aus


# --- Abschnitt 3: wer die Gesellschaft beaufsichtigt ------------------------
#
# Der Abschnitt sieht im Extrakt aus wie Fließtext, ist aber eine Tabelle mit
# zwei Spalten — und zwar eine, die pypdf **spaltenweise** ausliest: erst alle
# Namen untereinander, dann alle Funktionen untereinander. Was auf der
# gedruckten Seite nebeneinander steht, liegt im Extrakt fünfzehn Zeilen
# auseinander.
#
# DIE RECHENPROBE UND WARUM SIE HART IST
# ---------------------------------------
# Die Spalten wieder zu paaren geht nur über die Position: der n-te Name
# gehört zur n-ten Funktion. Das ist richtig, solange beide Listen gleich
# lang sind — und sobald sie es nicht sind, ist jede Zuordnung um mindestens
# einen Platz verschoben. Dann stünde an einer echten, namentlich genannten
# Person ein Amt, das sie nie hatte. Das ist keine Ungenauigkeit, das ist
# eine Falschaussage über einen Menschen.
#
# Deshalb: Zahl der Namen ≠ Zahl der Funktionen → **alle** Funktionen dieser
# Gesellschaft bleiben ``None`` und ``roles_assignable`` ist ``False`` —
# auch in einem zweiten Gremium, das für sich aufgegangen wäre. Kein „best
# effort", kein Verschieben, kein Auffüllen. Ein Name ohne Amt ist
# unvollständig; ein Name mit dem falschen Amt ist falsch.

#: Die Kopfzeile einer Gremiumsliste: „Mitglieder des Betriebsausschusses
#: Funktion/Legitimierung". Die zweite Spaltenüberschrift ist freiwillig —
#: die TGO Besitz GmbH & Co. KG führt gar keine Funktionsspalte.
_GREMIUM_KOPF = re.compile(
    r"^[ \t]*Mitglieder\s+(?:des|der)\s+(.+?)"
    r"[ \t]*(Funktion\s*/\s*Legitim\w*)?[ \t]*$", re.M)

#: Was in der Funktionsspalte steht — ein geschlossener Satz von Ämtern und
#: Legitimationen, gemessen an allen 45 Abschnitten der Berichte 2022–2024.
#:
#: Er ist die Grenze zwischen den beiden Spalten: Die Namensliste endet dort,
#: wo die erste Funktionszeile steht. Ein Muster, das aus Versehen auf einen
#: Namen passt, schneidet die Liste zu früh ab — deshalb sind es benannte
#: Ämter und keine Heuristik auf Groß-/Kleinschreibung.
#:
#: ``Vertreter`` braucht die Ausnahme: „Vertreter Mitgesellschafter" ist eine
#: Funktion, „Vertreter/in der Norddeutschen Landesbank" dagegen ein
#: **Sitz** in der Namensspalte der TGO Besitz — dort benennt der Bericht
#: keine Personen, sondern Entsendungsrechte. Der Schrägstrich trennt die
#: beiden Fälle.
_FUNKTION = re.compile(
    r"""^(?:
        \d+\.[ \t]*Kreisrat            # „1. Kreisrat (Vorsitzender)"
      | Rats(?:mitglied|frau|herr)
      | Ober-?[Bb]ürgermeister\w*
      | Bürgermeister\w*
      | Stadt(?:kämmer\w+|baur\w+|rat|rätin|direktor\w*)
      | Kreis(?:tagsmitglied|rat|rätin)
      | Land(?:rat|rätin|tagsmitglied)
      | Bundestagsmitglied
      | Beschäftigtenvertret\w+
      | Mitarbeitendenvertret\w+
      | Arbeitnehmervertret\w+
      | Personalrat\w*
      | Betriebsrat\w*
      | Vertreter(?:in)?(?![/\w])      # nicht „Vertreter/in der …"
      | Geschäftsführ\w+
      | geborenes[ \t]+Mitglied
      | Aufsichtsratsmitglied
    )\b""", re.X)

#: Der Seitenrand. Neben der Tabelle steht auf derselben Seite der
#: Steckbrief-Kasten der Gesellschaft — Anschrift, Satzungsdatum,
#: Handelsregister, Betriebsleitung —, und pypdf hängt ihn hinten an die
#: Spalten an. Er gehört nicht zur Aufsichtsliste.
#:
#: Erkannt wird der **Anfang** dieses Kastens; ab dort wird der Rest des
#: Blocks verworfen. Zeilenweise zu filtern wäre die schwächere Regel: Der
#: Kasten führt auch Namen („Betriebsleitung: Klaus Büscher"), und die
#: gehörten sonst als Aufsichtspersonen in die Liste.
_RANDMUELL = re.compile(
    r"""^(?:
        \d{5}[ \t]+\S                  # „26121 Oldenburg"
      | (?:Betriebssatzung|Gesellschaftsvertrag|Satzung|Stiftungssatzung
          |Handelsregister|Registernummer|Registergericht|Amtsgericht
          |Geschäftsführung|Betriebsleitung|Vorstand|Internet|Stand)\b
      | vom[ \t]*:
      | \(?zuletzt[ \t]+geändert
      | \d{1,2}\.[ \t]*[A-ZÄÖÜ]?\w*[ \t]+\d{4}\b   # nacktes Datum
      | \S*\.html\b
    )""", re.X)

#: Gruppenüberschriften **innerhalb** der Namensspalte: Die Großleitstelle
#: gehört vier Gebietskörperschaften und führt ihre Vertreter nach Träger
#: gegliedert („Stadt Oldenburg:", „Landkreis Ammerland:"). Das sind keine
#: Personen — und in der Funktionsspalte steht ihnen nichts gegenüber.
_GRUPPENKOPF = re.compile(r"^[^,]{3,40}:[ \t]*$")

#: Der Vorsitz, wie der Bericht ihn an den Namen hängt: „, Vorsitzende",
#: „, stellvertretender Vorsitzender", „(Vorsitzende)". Die Grammatik
#: schwankt (der Bäderbetrieb schreibt „stellvertretende Vorsitzender"),
#: deshalb greift das Muster auf den Wortstamm.
_STELLV = re.compile(r"stellv\w*\.?\s*(?:\w+\s+)?[Vv]orsitzend", re.I)
_VORSITZ = re.compile(r"^\(?[Vv]orsitzend", re.I)

#: Ein Zusatz zur Amtszeit — in Klammern oder hinter einem Komma. „(bis
#: 30. Juni 2022)", „, ab 28.11.2023", „(für V. Finke ab 09.10.2023)".
_ZEITRAUM = re.compile(r"^\(?(?:bis|ab|seit|vom|für|von)\b", re.I)


@dataclass
class Aufsichtsperson:
    """Eine Person in einem Aufsichtsorgan — so, wie der Bericht sie führt."""

    #: „Betriebsausschuss", „Aufsichtsrat", „Gesellschafterversammlung".
    gremium: str
    name: str
    #: Aus der zweiten Spalte — ``None``, wenn die Rechenprobe gerissen ist
    #: oder der Bericht für dieses Gremium keine Funktionsspalte führt.
    position: str | None
    #: ``"chair"`` | ``"deputy"`` | ``None``.
    chair_role: str | None
    #: Amtszeit-Zusatz, wörtlich: „bis 30. Juni 2022".
    note: str | None
    #: Position in der Liste des Berichts, je Gesellschaft fortlaufend.
    sort_order: int


def _zeilen_fuegen(rumpf: str) -> list[str]:
    """Die Zeilen eines Blocks — Umbrüche mitten im Namen wieder zusammen.

    Der Satz bricht lange Einträge um, und zwar an zwei Stellen: hinter einem
    Komma („Dr. Sebastian Rohe, stellvertretender Vorsitzender," / „bis zum
    27.02.2023") und mitten im Wort („stellvertretende Vor-" / „sitzende").
    Beides zählte sonst als eigener Eintrag, und die Namensspalte wäre länger
    als die Funktionsspalte — die Probe risse, obwohl das Dokument in Ordnung
    ist.

    Erkannt wird die Fortsetzung an ihrem **Anfang**: Sie beginnt klein. Ein
    neuer Eintrag beginnt mit einem Großbuchstaben, einem Titel oder einer
    Klammer — Personennamen tun das ausnahmslos."""
    aus: list[str] = []
    for roh in rumpf.split("\n"):
        zeile = " ".join(roh.replace(" ", " ").split())
        if not zeile:
            continue
        if aus and zeile[:1].islower():
            if aus[-1].endswith("-"):
                aus[-1] = aus[-1][:-1] + zeile       # „Vor-" + „sitzende"
            else:
                aus[-1] = f"{aus[-1]} {zeile}"
            continue
        aus.append(zeile)
    return aus


def _gremiumsname(roh: str) -> str:
    """„Betriebsausschusses" → „Betriebsausschuss".

    Die Kopfzeile steht im Genitiv, die Überschrift auf der Seite soll im
    Nominativ stehen. Angefasst wird nur, was der Genitiv anhängt (``-es``,
    ``-s``) — „Gesellschafterversammlung" endet auf keins von beidem und
    bleibt, wie sie ist (auch dort, wo der Bericht „des" davorsetzt: „Mitglieder
    des Gesellschafterversammlung" steht so in den Weser-Ems-Abschnitten)."""
    name = " ".join((roh or "").split()).strip(" :,")
    if name.endswith("es") and len(name) > 5:
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss") and len(name) > 4:
        return name[:-1]
    return name


def _person_zerlegen(zeile: str, gremium: str, sort_order: int) -> Aufsichtsperson:
    """Eine Zeile der Namensspalte → Name, Vorsitz und Amtszeit-Zusatz.

    Der Name ist, was **vor** dem ersten Komma und außerhalb aller Klammern
    steht. Alles dahinter ist Beiwerk und wird eingeordnet: Vorsitz, Zeitraum
    — oder, wo es weder das eine noch das andere ist („Dr. Julia Figura,
    Stadtkämmerin"), fallengelassen. Ein Amt aus der Namensspalte in das Feld
    ``position`` zu schreiben hieße, die Funktionsspalte zu übergehen, deren
    Zuordnung gerade die Probe absichert."""
    # „Hans -Georg Heß", „Prof. Dr. -Ing. Weisensee": Der Satz setzt Leerraum
    # vor den Bindestrich. Das ist derselbe Schaden wie bei den Beträgen.
    zeile = re.sub(r"\s+-\s*(?=\w)", "-", " ".join(zeile.split()))

    chair_role: str | None = None
    hinweise: list[str] = []

    def einordnen(teil: str) -> None:
        nonlocal chair_role
        teil = teil.strip(" ,;")
        if not teil:
            return
        if _STELLV.search(teil):
            chair_role = chair_role or "deputy"
        elif _VORSITZ.match(teil):
            chair_role = chair_role or "chair"
        elif _ZEITRAUM.match(teil):
            hinweise.append(teil.strip("()"))

    rest = re.sub(r"\(([^)]*)\)", lambda m: (einordnen(m.group(1)) or " "), zeile)
    teile = [t.strip() for t in rest.split(",")]
    for t in teile[1:]:
        einordnen(t)
    return Aufsichtsperson(
        gremium=gremium, name=" ".join(teile[0].split()), position=None,
        chair_role=chair_role, note=", ".join(hinweise) or None,
        sort_order=sort_order)


def aufsichtsorgane(text: str) -> tuple[list[Aufsichtsperson], bool]:
    """Abschnitt 3 zerlegen — ``(personen, roles_assignable)``.

    ``roles_assignable`` gilt für die **ganze** Gesellschaft und ist das
    Und über ihre Gremien: Eine GSG mit einem sauberen Aufsichtsrat und einer
    verrutschten Gesellschafterversammlung ist nicht „halb zuordenbar".
    Die Oberfläche zeigt dann für alle Gremien nur die Namen — und sagt das.

    Ein Gremium **ohne** Funktionsspalte (die TGO Besitz GmbH & Co. KG führt
    statt Personen Entsendungsrechte) besteht die Probe: Es wird nichts
    zugeordnet, also kann auch nichts verrutschen. Es gäbe hier nichts zu
    warnen — die Seite zeigt Namen ohne Ämter, weil der Bericht keine nennt."""
    koepfe = list(_GREMIUM_KOPF.finditer(text or ""))
    if not koepfe:
        return [], False

    personen: list[Aufsichtsperson] = []
    zuordenbar = True
    for i, kopf in enumerate(koepfe):
        gremium = _gremiumsname(kopf.group(1))
        bis = koepfe[i + 1].start() if i + 1 < len(koepfe) else len(text)
        zeilen = _zeilen_fuegen(text[kopf.end():bis])

        # Erst den Steckbrief-Kasten abschneiden, dann die Spalten trennen:
        # Sonst stünde „Betriebsleitung: Klaus Büscher" hinter der letzten
        # Funktionszeile und risse die Probe.
        for n, z in enumerate(zeilen):
            if _RANDMUELL.match(z):
                zeilen = zeilen[:n]
                break

        stellen = [n for n, z in enumerate(zeilen) if _FUNKTION.match(z)]
        if stellen:
            erste, letzte = stellen[0], stellen[-1]
            # Zwischen der ersten und der letzten Funktionszeile darf nichts
            # anderes stehen. Steht dort doch etwas, sind die Spalten nicht
            # sauber getrennt — und dann ist die Positionszählung wertlos.
            geschlossen = len(stellen) == letzte - erste + 1
            funktionen = zeilen[erste:letzte + 1] if geschlossen else []
            namenszeilen = zeilen[:erste]
        else:
            funktionen = []
            namenszeilen = zeilen
        namenszeilen = [z for z in namenszeilen if not _GRUPPENKOPF.match(z)]

        block = [_person_zerlegen(z, gremium, len(personen) + n)
                 for n, z in enumerate(namenszeilen)]
        haelt = len(block) == len(funktionen)
        if haelt:
            for p, f in zip(block, funktionen):
                p.position = f
        elif funktionen or kopf.group(2):
            # Nur wo der Bericht eine Funktionsspalte führt, ist eine
            # gerissene Probe ein Befund. Ohne Spalte gibt es nichts zu paaren.
            zuordenbar = False
        personen += block

    if not zuordenbar:
        # Und dann wirklich **alle**, auch die Gremien, die für sich in
        # Ordnung waren: Die Seite trägt eine Angabe je Gesellschaft. Stünden
        # im Aufsichtsrat Ämter und in der Gesellschafterversammlung darunter
        # keine, hieße der Hinweis „hier stimmt etwas nicht" für eine Liste,
        # die aussieht wie die andere — und niemand wüsste, welche gemeint ist.
        for p in personen:
            p.position = None
    return personen, zuordenbar


# --- Abschnitt 2: wem die Gesellschaft gehört -------------------------------

#: Die Kopfzeilen der Tabelle. „Trägerkörperschaft" steht beim Klinikum
#: (eine AöR hat keine Gesellschafter), „Kapitalanteil" bei den KGs.
_EIGNER_KOPF = re.compile(
    r"^(?:Gesellschafter|Trägerkörperschaft|Anteilseigner|Anteil|Kapitalanteil"
    r"|in\s+Euro|in\s+Prozent)\b", re.I)

#: Die Summenzeile. Sie trägt denselben Aufbau wie ein Eigentümer und ist
#: keiner: Sie ist die Probe, gegen die die Anteile laufen.
_STAMMKAPITAL = re.compile(r"^(?:gezeichnetes\s+)?(?:stamm|grund|start)?\s*kapital\b",
                           re.I)

#: Eine Wertzeile: irgendein Name, dann Betrag und Prozentsatz. Der Name darf
#: fehlen — bei den Kommanditgesellschaften steht er zwei Zeilen darüber.
_EIGNER_ZEILE = re.compile(
    r"^(?P<name>.*?)\s*(?P<eur>\d[\d.]*,\d{2})\s+(?P<proz>\d[\d.]*,\d+)\s*$")

#: Toleranz der Prozentprobe in Prozentpunkten. Der Bericht rundet auf zwei
#: Stellen; sechs Anteile zu je 16,67 % ergeben 100,02 %, und das ist keine
#: falsche Tabelle, sondern eine gerundete.
TOLERANZ_PROZENT = 0.5


def _deutsch(wert: float) -> str:
    """``22000000.0`` → ``„22.000.000,00"`` — für den Messwert der Probe.

    Der steht über die API im Beleg-Chip und wird gelesen, nicht gerechnet."""
    ganz, _, dezimal = f"{wert:,.2f}".partition(".")
    return f"{ganz.replace(chr(44), chr(46))},{dezimal}"


@dataclass
class Eigentuemer:
    """Ein Gesellschafter mit seinem Anteil."""

    name: str
    amount_eur: float | None
    share_pct: float | None
    sort_order: int


def beteiligungsverhaeltnisse(text: str) -> tuple[list[Eigentuemer], str | None]:
    """Abschnitt 2 zerlegen — ``(eigentuemer, probe_result)``.

    Die Probe rechnet nach, was das Dokument selbst vorrechnet: Die Anteile
    ergeben zusammen das Stammkapital, und ihre Prozentsätze ergeben 100.
    Beides muss stimmen. Der Prozentsatz allein wäre zu schwach (eine
    übersehene Zeile mit 0,0 % fiele nicht auf), der Betrag allein auch (bei
    zwei Gesellschaftern zu je der Hälfte ist eine vertauschte Zeile
    unsichtbar).

    **Die Stammkapital-Zeile ist kein Gesellschafter.** Sie sieht im Extrakt
    aus wie einer — Name, Betrag, Prozent —, ist aber die Summenzeile. Als
    Eigentümerin geführt hielte die Stadt Oldenburg an ihrem Eigenbetrieb
    50 % und ein „Stammkapital" die anderen 50 %.

    Reißt die Probe, kommt **nichts** zurück: keine halb gelesene Tabelle,
    keine Zeile „wahrscheinlich". Der Rohtext steht ohnehin daneben, und ein
    Mensch liest ihn richtig. ``probe_result`` ist der Messwert für die
    Herkunft; es ist ``None``, wenn die Probe gerissen ist."""
    zeilen = _zeilen_fuegen(_entzerren(text or ""))
    for n, z in enumerate(zeilen):
        if _RANDMUELL.match(z):
            zeilen = zeilen[:n]
            break

    eigner: list[Eigentuemer] = []
    summe: tuple[float, float] | None = None
    puffer: list[str] = []
    for zeile in zeilen:
        if _EIGNER_KOPF.match(zeile):
            continue
        m = _EIGNER_ZEILE.match(zeile)
        if not m:
            puffer.append(zeile)
            continue
        eur, proz = _betrag(m.group("eur")), _betrag(m.group("proz"))
        name = " ".join((" ".join(puffer) + " " + m.group("name")).split())
        puffer = []
        if eur is None or proz is None:
            continue
        if _STAMMKAPITAL.match(name):
            summe = (eur, proz)
            continue
        eigner.append(Eigentuemer(name=name, amount_eur=eur,
                                  share_pct=proz, sort_order=len(eigner)))

    if not eigner or summe is None:
        return [], None
    delta_eur = abs(sum(e.amount_eur or 0.0 for e in eigner) - summe[0])
    delta_proz = abs(sum(e.share_pct or 0.0 for e in eigner) - 100.0)
    if delta_eur > TOLERANZ_EUR or delta_proz > TOLERANZ_PROZENT:
        return [], None
    return eigner, (f"Die Anteile ergeben das ausgewiesene Stammkapital von "
                    f"{_deutsch(summe[0])} € (Δ {_deutsch(delta_eur)} €) und "
                    f"zusammen {_deutsch(100.0 + delta_proz)} %")


# --- Ein ganzer Jahrgang ----------------------------------------------------

#: Rundungstoleranz der Bilanzprobe in Euro. Die Beträge stehen auf den Cent
#: genau; ein Cent Spielraum fängt nur Gleitkomma-Rauschen.
TOLERANZ_EUR = 0.011


def lies(seiten: list[str]) -> dict:
    """Einen Beteiligungsbericht vollständig lesen, mit allen Proben.

    ``seiten`` ist der pypdf-Extrakt **seitenweise** — die Seitengrenzen sind
    keine Formatierung, sondern die Grundlage der Zuordnung: Eine Gesellschaft
    beginnt auf ihrer Trennseite, und die steht im Inhaltsverzeichnis.

    Liefert ``{"budget_year", "gesellschaften", "warnungen", "dokumentproben"}``.
    ``gesellschaften`` sind :class:`Gesellschaft`-Objekte; welche Kennzahl
    welche Probe bestanden hat, entscheidet erst :func:`pruefe` im
    Zusammenspiel mit den anderen Jahrgängen."""
    jg = budget_year("\n".join(seiten[:3]))
    ges, warnungen = classification(seiten)
    if jg is None:
        return {"budget_year": None, "gesellschaften": [],
                "warnungen": ["Kein Berichtsjahr im Dokumentkopf gefunden"],
                "dokumentproben": []}
    if jg < ERSTER_JAHRGANG:
        return {"budget_year": jg, "gesellschaften": [], "dokumentproben": [],
                "warnungen": [
                    f"Berichtsjahr {jg} liegt vor dem Formatbruch "
                    f"{ERSTER_JAHRGANG}: keine Kennzahlen-Tabellen, Bilanz "
                    f"zweispaltig — nicht maschinenlesbar (s. Modulkopf)"]}

    grenzen = [g.page for g in ges] + [len(seiten) + 1]
    dokumentproben: list[dict] = []
    for i, g in enumerate(ges):
        text = "\n".join(seiten[g.page - 1:grenzen[i + 1] - 1])
        g.abschnitte = abschnitte(text)
        g.kennzahlen, kw = kennzahlen(text)
        g.bilanzsummen = bilanzsummen(text)
        g.guv = guv_ergebnisse(text)
        warnungen += [f"{g.name}: {w}" for w in kw]

        # Zwei Proben aus dem Dokument selbst. Geprüft wird über ALLE
        # gemeinsamen Jahre, nicht nur über das Berichtsjahr: Die
        # Großleitstelle führt noch im Bericht für 2024 die Jahre 2017–2021,
        # und ihre Bilanz steht auf demselben Stand. Wer nur das Berichtsjahr
        # prüft, hat für sie nie eine Probe.
        for indicator, gegen, betragsweise in (
                ("bilanzsumme", g.bilanzsummen, False),
                ("jahresergebnis", g.guv, True)):
            series = g.kennzahlen.get(indicator) or {}
            gemeinsam = sorted(set(series) & set(gegen))
            for j in gemeinsam:
                links, rechts = series[j], gegen[j]
                if betragsweise:
                    links, rechts = abs(links), abs(rechts)
                delta = abs(links - rechts)
                dokumentproben.append(
                    {"gesellschaft": g.key, "indicator": indicator, "year": j,
                     "delta": delta, "ok": delta <= TOLERANZ_EUR})
            if series and not gemeinsam:
                warnungen.append(
                    f"{g.name}: {indicator} ohne Gegenstelle im Dokument "
                    f"(dort {sorted(gegen) or '—'}, in den Kennzahlen "
                    f"{sorted(series)})")
    return {"budget_year": jg, "gesellschaften": ges, "warnungen": warnungen,
            "dokumentproben": dokumentproben}


def ueberlappung(jahrgaenge: dict[int, list[Gesellschaft]]) -> dict:
    """Die Überlappungsprobe über mehrere Berichte.

    Jeder Bericht führt vier bis fünf Jahre. Ein Jahr steht deshalb in bis zu
    drei Berichten — aus verschiedenen Veröffentlichungen, und sie müssen
    übereinstimmen. Das ist dieselbe Bauart wie die Vorjahres-Kette der
    Jahresabschlüsse: Ein Wert, den zwei unabhängige Dokumente gleich nennen,
    ist bestätigt; wo sie sich widersprechen, verrät die Probe nicht, welches
    recht hat, und **beide** Werte fallen weg.

    Liefert ``{"bestaetigt": {(key, indicator, year) -> n}, "widersprueche":
    [...], "einzeln": n}``."""
    gesammelt: dict[tuple[str, str, int], dict[int, float]] = {}
    for bericht, liste in sorted(jahrgaenge.items()):
        for g in liste:
            for indicator, series in g.kennzahlen.items():
                for year, wert in series.items():
                    gesammelt.setdefault((g.key, indicator, year), {})[bericht] = wert

    bestaetigt: dict[tuple[str, str, int], int] = {}
    widersprueche: list[dict] = []
    einzeln = 0
    for schluessel, je_bericht in gesammelt.items():
        werte = {round(w, 2) for w in je_bericht.values()}
        if len(je_bericht) == 1:
            einzeln += 1
        elif len(werte) == 1:
            bestaetigt[schluessel] = len(je_bericht)
        else:
            widersprueche.append({"gesellschaft": schluessel[0],
                                  "indicator": schluessel[1], "year": schluessel[2],
                                  "werte": dict(je_bericht)})
    return {"bestaetigt": bestaetigt, "widersprueche": widersprueche,
            "einzeln": einzeln}


# --- Einlesen ---------------------------------------------------------------

#: Einheit je Kennzahl — für die Anzeige, und damit niemand Euro gegen Prozent
#: in dieselbe Achse zeichnet.
EINHEITEN = {key: einheit for key, _, einheit in KENNZAHLEN}


def alle_werte(jahrgaenge: dict[int, list[Gesellschaft]]
               ) -> dict[tuple[str, str, int], dict[int, float]]:
    """``(Gesellschaft, Kennzahl, Bezugsjahr) -> {Berichtsjahr: Wert}``.

    Die Umkehrung der Berichtsordnung: Der Bericht ordnet nach Gesellschaft
    und Jahrgang, gefragt ist aber „welche Berichte nennen diesen einen Wert?"
    — und das ist genau die Frage der Überlappungsprobe."""
    aus: dict[tuple[str, str, int], dict[int, float]] = {}
    for report_year, liste in sorted(jahrgaenge.items()):
        for g in liste:
            for indicator, series in g.kennzahlen.items():
                for year, wert in series.items():
                    aus.setdefault((g.key, indicator, year), {})[report_year] = wert
    return aus


def konzernvergleich(store, year: int) -> list[dict]:
    """Beitrag im Gesamtabschluss gegen Jahresergebnis im Beteiligungsbericht.

    Für jede Gesellschaft, die der Gesamtabschluss als eigenen Träger führt
    (``Gesellschaft.consolidated_key``), beide Zahlen desselben Jahres nebeneinander
    — in **Euro**, damit sie vergleichbar sind; der Gesamtabschluss rechnet in
    Tausend.

    Ausdrücklich **keine Probe**: Die beiden Rechnungen unterscheiden sich
    systematisch, und zwei Betriebe weisen wegen Ergebnisabführung 0,00 € aus,
    obwohl sie etwas erwirtschaftet haben (gemessene Zahlen im Modulkopf). Was
    hier herauskommt, ist eine Einordnung für die Seite und eine Kennzahl fürs
    Protokoll — nichts, was einen Wert verwirft."""
    entity: dict[str, dict[str, float]] = {}
    for z in store.get_konzern_traeger(year):
        entity.setdefault(z["entity_key"], {})[z["art"]] = z["amount_keur"]
    if not entity:
        return []

    ergebnisse = {z["gesellschaft"]: z["wert"]
                  for z in store.get_gesellschaft_kennzahlen()
                  if z["indicator"] == "jahresergebnis" and z["year"] == year}
    aus: list[dict] = []
    for g in store.get_gesellschaften():
        schluessel = g.get("consolidated_key")
        if not schluessel or schluessel not in entity:
            continue
        if g["gesellschaft"] not in ergebnisse:
            continue
        v = entity[schluessel]
        if "revenues" not in v or "expenses" not in v:
            continue
        beitrag = (v["revenues"] - v["expenses"]) * 1000.0
        eigen = ergebnisse[g["gesellschaft"]]
        aus.append({"gesellschaft": g["gesellschaft"], "name": g["name"],
                    "year": year, "konzern_beitrag": beitrag,
                    "jahresergebnis": eigen, "difference": beitrag - eigen})
    return sorted(aus, key=lambda z: abs(z["difference"]), reverse=True)


def _nachweis(delta: float | None, n_reports: int) -> str:
    """Was die Proben bei **dieser** Zahl gemessen haben.

    Nicht der Probenname (der steht in ``herkunft.PROBEN`` und wird dort für
    Leserinnen erklärt), sondern das Ergebnis — der Beleg, dass sie wirklich
    lief und nicht nur behauptet wird."""
    teile = []
    if delta is not None:
        teile.append(f"Dokumentprobe: Δ {delta + 0.0:.2f}".replace("-0.00", "0.00"))
    if n_reports > 1:
        teile.append(f"in {n_reports} Berichten übereinstimmend")
    return "; ".join(teile)


def einlesen(store, dokumente: dict[int, dict], p, schuetzen: bool = True) -> dict:
    """Alle vorliegenden Berichte lesen, prüfen und den Bestand ersetzen.

    ``dokumente`` ist ``{report_year: {"seiten": [str], "url": str,
    "label": str}}`` — was der Cron geholt und ``pypdf`` extrahiert hat.

    **Immer alle auf einmal**, nie einzeln. Die Überlappungsprobe vergleicht
    Berichte miteinander; wer nur den neuen liest, hat nichts zu vergleichen,
    und die Angabe „in wie vielen Berichten steht dieser Wert?" veraltete in
    jeder zweiten Zeile. Teuer ist das nicht: Heruntergeladen wird ohnehin nur,
    was sich geändert hat (``council/stadtdownload.py``), und drei PDFs zu
    parsen dauert Sekunden.

    Gespeichert wird nur, was eine Probe trägt. Ein Wert ohne Probe wird
    **verworfen, nicht geschätzt**. In der Praxis trifft das die älteste Spalte
    des ältesten Berichts (sie hat weder eine Bilanz daneben noch einen zweiten
    Bericht) und die Eigenkapitalquote des jüngsten Jahres."""
    from council import herkunft as _h
    from council.finanzquellen import bestandsschutz

    gelesen: dict[int, dict] = {}
    for dateijahr in sorted(dokumente):
        d = dokumente[dateijahr]
        result = lies(d["seiten"])
        for w in result["warnungen"]:
            p.warnen(f"  {dateijahr}: {w}")
        if not result["gesellschaften"]:
            continue
        # Über den Jahrgang entscheidet das Dokument, nicht der Dateiname.
        echt = result["budget_year"]
        if echt != dateijahr:
            p.warnen(f"  Datei für {dateijahr} nennt sich im Kopf "
                     f"„Beteiligungsbericht {echt}“ — es gilt das Dokument")
        gerissen = [x for x in result["dokumentproben"] if not x["ok"]]
        for x in gerissen:
            p.warnen(f"  {echt}: {x['gesellschaft']}/{x['indicator']} {x['year']}: "
                     f"Dokumentprobe gerissen (Δ {x['delta']:.2f}) — verworfen")
        gelesen[echt] = {**result, **d, "report_year": echt}
        p.sagen(f"  {echt}: {len(result['gesellschaften'])} Gesellschaften, "
                f"{len(result['dokumentproben']) - len(gerissen)}/"
                f"{len(result['dokumentproben'])} Dokumentproben bestanden")

    if not gelesen:
        p.warnen("  Kein lesbarer Jahrgang — Bestand bleibt unangetastet")
        return {"gesellschaften": 0, "texte": 0, "kennzahlen": 0, "verworfen": 0,
                "widersprueche": 0, "bestand_geschuetzt": 0, "jahrgaenge": []}

    # Welche (Gesellschaft, Kennzahl, Bezugsjahr) hat im Dokument eine
    # bestandene Probe — und wie groß war die gemessene Abweichung?
    dokumentprobe: dict[tuple[str, str, int], tuple[str, float]] = {}
    for e in gelesen.values():
        for x in e["dokumentproben"]:
            if not x["ok"]:
                continue
            name = ("beteiligung_bilanzprobe" if x["indicator"] == "bilanzsumme"
                    else "beteiligung_ergebnisprobe")
            s = (x["gesellschaft"], x["indicator"], x["year"])
            # Die **größte** gemessene Abweichung gewinnt: Belegen mehrere
            # Berichte dieselbe Zahl, ist der schlechteste Messwert die
            # ehrliche Angabe, nicht der schönste.
            if s not in dokumentprobe or x["delta"] > dokumentprobe[s][1]:
                dokumentprobe[s] = (name, x["delta"])

    nach_jahrgang = {j: e["gesellschaften"] for j, e in gelesen.items()}
    u = ueberlappung(nach_jahrgang)
    strittig = {(w["gesellschaft"], w["indicator"], w["year"])
                for w in u["widersprueche"]}
    for w in u["widersprueche"]:
        p.warnen(f"  {w['gesellschaft']}/{w['indicator']} {w['year']}: Berichte "
                 f"widersprechen sich ({w['werte']}) — Wert verworfen")

    def anker(e: dict, g: Gesellschaft) -> dict:
        return {"art": "stadt", "url": e["url"], "label": e["label"],
                "page": g.seite_gedruckt,
                "stand": f"Beteiligungsbericht {e['report_year']}"}

    stammdaten: list[dict] = []
    texte: list[dict] = []
    personen: list[dict] = []
    eigentuemer: list[dict] = []
    ohne_zuordnung: list[str] = []
    for year, e in sorted(gelesen.items()):
        for g in e["gesellschaften"]:
            gemeinsam = anker(e, g)
            stammdaten.append({
                "report_year": year, "gesellschaft": g.key, "name": g.name,
                "classification": g.classification, "page": g.seite_gedruckt,
                "consolidated_key": g.consolidated_key,
                "herkunft": _h.Herkunft(
                    probe="beteiligung_seitenprobe",
                    citation=f"Abschnitt {g.classification} — {g.name}",
                    probe_result=f"Inhaltsverzeichnis und Trennseite nennen "
                                   f"beide Seite {g.seite_gedruckt}",
                    **gemeinsam)})
            for key, _, heading in TEXTABSCHNITTE:
                if key not in g.abschnitte:
                    continue
                texte.append({
                    "report_year": year, "gesellschaft": g.key, "section": key,
                    "text": g.abschnitte[key],
                    # Fließtext trägt keine Rechenprobe, und eine zu behaupten
                    # wäre gelogen. Woher er stammt, steht trotzdem da.
                    "herkunft": _h.Herkunft(
                        probe=_h.UNGEPRUEFT,
                        citation=f"Abschnitt {g.classification} — {heading}",
                        **gemeinsam)})

            # Zwei der fünf Abschnitte sind in Wahrheit Tabellen. Sie bleiben
            # als Text stehen (die Seite zeigt sie, wo die Struktur nicht
            # trägt) und kommen zusätzlich zerlegt herein.
            liste, zuordenbar = aufsichtsorgane(g.abschnitte.get("aufsichtsorgane", ""))
            if not zuordenbar and liste:
                ohne_zuordnung.append(f"{year}/{g.key}")
            for person in liste:
                personen.append({
                    "report_year": year, "gesellschaft": g.key,
                    "sort_order": person.sort_order, "gremium": person.gremium,
                    "name": person.name, "position": person.position,
                    "chair_role": person.chair_role, "note": person.note,
                    "roles_assignable": zuordenbar,
                    # Der Name selbst trägt keine Probe — er steht einmal im
                    # Bericht. Geprüft ist die **Zuordnung** des Amtes; wo sie
                    # gerissen ist, steht auch kein Amt da, und die Zeile sagt
                    # ausdrücklich „ungeprüft" statt eine Probe zu behaupten.
                    "herkunft": _h.Herkunft(
                        probe=("beteiligung_spaltenprobe" if person.position
                               else _h.UNGEPRUEFT),
                        citation=f"Abschnitt {g.classification} — "
                                   f"{person.gremium}",
                        probe_result=(f"{len(liste)} Namen, "
                                        f"{len(liste)} Funktionen"
                                        if person.position else None),
                        **gemeinsam)})

            eigner, anteilsprobe = beteiligungsverhaeltnisse(
                g.abschnitte.get("beteiligungsverhaeltnisse", ""))
            for e_ in eigner:
                eigentuemer.append({
                    "report_year": year, "gesellschaft": g.key,
                    "sort_order": e_.sort_order, "name": e_.name,
                    "amount_eur": e_.amount_eur,
                    "share_pct": e_.share_pct,
                    "herkunft": _h.Herkunft(
                        probe="beteiligung_anteilsprobe",
                        citation=f"Abschnitt {g.classification} — "
                                   f"Beteiligungsverhältnisse",
                        probe_result=anteilsprobe,
                        **gemeinsam)})

    if ohne_zuordnung:
        p.sagen(f"  Spaltenprobe gerissen bei {len(ohne_zuordnung)} "
                f"Gesellschaft(en) ({', '.join(ohne_zuordnung)}) — dort stehen "
                f"die Namen ohne Amt")

    kennzahlen_zeilen: list[dict] = []
    verworfen = 0
    for schluessel, je_bericht in sorted(alle_werte(nach_jahrgang).items()):
        key, indicator, year = schluessel
        if schluessel in strittig:
            verworfen += 1
            continue
        probes: list[str] = []
        delta = None
        if schluessel in dokumentprobe:
            name, delta = dokumentprobe[schluessel]
            probes.append(name)
        if len(je_bericht) > 1:
            probes.append("beteiligung_ueberlappung")
        if not probes:
            verworfen += 1
            continue
        juengster = max(je_bericht)
        e = gelesen[juengster]
        g = next(x for x in e["gesellschaften"] if x.key == key)
        kennzahlen_zeilen.append({
            "gesellschaft": key, "indicator": indicator, "year": year,
            "wert": je_bericht[juengster], "einheit": EINHEITEN[indicator],
            "report_year": juengster, "n_reports": len(je_bericht),
            "herkunft": _h.Herkunft(
                probe=probes,
                citation=f"Abschnitt {g.classification} — Kennzahlen im Zeitverlauf",
                probe_result=_nachweis(delta, len(je_bericht)),
                **anker(e, g))})

    # Bestandsschutz: Ein leeres oder deutlich geschrumpftes Ergebnis ersetzt
    # nie einen gefüllten Bestand. Der Job läuft unbeaufsichtigt, und ein
    # geänderter Berichtsaufbau sieht für den Parser aus wie „nichts gefunden".
    alt = len(store.get_gesellschaft_kennzahlen())
    if not bestandsschutz(p, "Beteiligungsbericht (Kennzahlen)", alt,
                          len(kennzahlen_zeilen), schuetzen):
        return {"gesellschaften": 0, "texte": 0, "kennzahlen": 0, "personen": 0,
                "eigentuemer": 0, "ohne_zuordnung": len(ohne_zuordnung),
                "verworfen": verworfen, "widersprueche": len(u["widersprueche"]),
                "bestand_geschuetzt": 1, "jahrgaenge": sorted(gelesen)}

    bericht = store.save_beteiligungsbericht(stammdaten, texte, kennzahlen_zeilen,
                                             personen, eigentuemer)
    p.sagen(f"  gespeichert: {bericht['gesellschaften']} Gesellschafts-Einträge, "
            f"{bericht['texte']} Textabschnitte, {bericht['kennzahlen']} Kennzahlen, "
            f"{bericht['personen']} Aufsichtspersonen, "
            f"{bericht['eigentuemer']} Eigentümer "
            f"({verworfen} ohne Probe verworfen)")

    # Einordnung, keine Probe: Wie weit liegen Gesamtabschluss und
    # Beteiligungsbericht für dieselbe Gesellschaft auseinander? Steht im
    # Protokoll, damit ein Sprung auffällt — verwirft aber nichts.
    juengster_bericht = max(gelesen)
    vergleich = konzernvergleich(store, juengster_bericht)
    if vergleich:
        p.sagen(f"  Abgleich mit dem Gesamtabschluss {juengster_bericht}: "
                f"{len(vergleich)} Gesellschaft(en) in beiden, größte Differenz "
                f"{vergleich[0]['difference'] / 1000:,.0f} TEUR "
                f"({vergleich[0]['gesellschaft']})")
    return {**bericht, "verworfen": verworfen,
            "widersprueche": len(u["widersprueche"]), "bestand_geschuetzt": 0,
            "ohne_zuordnung": len(ohne_zuordnung),
            "jahrgaenge": sorted(gelesen), "konzernvergleich": len(vergleich)}
