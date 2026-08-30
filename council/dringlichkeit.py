"""Dringlichkeitsanträge sichtbar machen — sie stehen nirgends, wo jemand sucht.

Ein Dringlichkeitsantrag wird kurzfristig auf die Tagesordnung gehoben. Im
Ratsinformationssystem hat er deshalb **keinen eigenen Tagesordnungspunkt**:
Er hängt als Dokument an der Zeile von „Ö 2 Genehmigung der Tagesordnung",
denn genau dort wird über seine Aufnahme abgestimmt.

Damit fällt er durch jedes Raster dieses Projekts, gleich dreifach:

1. ``council_agenda_items`` kennt nur „Ö 2 Genehmigung der Tagesordnung" —
   der Antrag selbst hat keine Zeile.
2. Diese Überschrift ist eine Formalie und fliegt überall heraus
   (``_FORMALIE_RE``): Wochenvorschau, Tragweite, Karten.
3. Die Labels der Zeilen-Dokumente liest für die Vorschau niemand.

Wie oft das vorkommt, ist am Bestand gemessen (40 Ratssitzungen, Juli 2022
bis August 2026): **zwölfmal, also in 30 % der Sitzungen** — elfmal als
Dokument an Ö 2, einmal nur an einem inhaltlichen Punkt (der dadurch ohnehin
sichtbar war). Und es sind keine Randthemen: Resolution Iran, Anwohnerparken,
Lachgas, Fliegerhorst, Schutz der Platanen am Stadtmuseum.

Dieses Modul macht aus so einem Dokument einen eigenen Punkt. Er bekommt die
Kennung ``DZT n`` — die Abkürzung stammt aus dem Ratsinformationssystem
selbst, das die Zeile mit „DZT" markiert. Bewusst KEINE Ö-Nummer: Der Punkt
ist abgeleitet, nicht amtlich, und das soll man ihm ansehen.
"""
from __future__ import annotations

import re

#: Die Kennung, die dieses Modul vergibt (``DZT 1``, ``DZT 2``, …). Wer
#: wissen will, ob ein Punkt ein Dringlichkeitsantrag ist, fragt
#: ``ist_dringlichkeitsantrag`` — nicht den Titel: „Dringlichkeit" kann auch
#: im Titel einer gewöhnlichen Vorlage stehen („Dringlichkeitsliste –
#: Fortschreibung 2021", Vorlage 21/0193).
KENNUNG_RE = re.compile(r"^\s*DZT\b")


def ist_dringlichkeitsantrag(item_number: str | None) -> bool:
    """Ist dieser Punkt einer der hier erzeugten Zusatzpunkte?

    Die eine Quelle für diese Frage — die Tragweite braucht sie für ihren
    Boden (``impact.dringlichkeits_boden``), die Sitzungsansicht für die
    Hervorhebung im Web.
    """
    return bool(KENNUNG_RE.match(item_number or ""))


#: Was ein Dringlichkeitsantrag heißt. Teilstring statt Präfix, weil die
#: Labels uneinheitlich sind — am Bestand gemessen kommen vor:
#: „Dringlichkeitsantrag CDU Quellenweg", „250523 Antrag Dringlichkeit
#: Fliegerhorst-Fraktionen", „TV Dringlichkeitsantrag Resolution Iran".
#: Ein Präfix-Vergleich hätte zwei von zwölf Fällen verloren.
IST_DRINGLICH_RE = re.compile(r"dringlichkeit", re.IGNORECASE)

#: Tagesordnungspunkte, an denen ein Dringlichkeitsantrag hängen KANN, ohne
#: dass er schon ein eigenes Thema hätte. Hängt er dagegen an einem
#: inhaltlichen Punkt, ist dieser Punkt bereits sichtbar — dann entsteht hier
#: nichts, sonst stünde dasselbe Thema zweimal auf der Karte.
_FORMALIE_RE = re.compile(
    r"Genehmigung der Tagesordnung|Feststellung der Beschlussf[äa]higkeit|"
    r"Genehmigung des Protokolls", re.IGNORECASE)

#: Was in den Labels vor dem eigentlichen Thema steht: Datumsstempel
#: („250523", „2025-09-04"), die Hauskürzel des Systems („TV", „DZT") und der
#: Dateityp. Erhoben an den zwölf Fundstellen, nicht geraten.
_VORSPANN_RE = re.compile(
    r"^(?:\s*(?:\d{6,8}|\d{4}-\d{2}-\d{2}|TV|DZT|TOP)\b[\s\-_.]*)+", re.IGNORECASE)
#: Und was hinten dranhängt: das Sitzungsdatum.
_NACHSPANN_RE = re.compile(r"[\s\-_.]*\d{1,2}\.\d{1,2}\.\d{2,4}\s*$")


#: Schreibfehler der Stadt, die im Dateinamen stehen und damit im Titel
#: landen würden. Korrigiert wird NUR, was zweifelsfrei ein Verschreiber ist
#: (Tims Vorgabe 30.08.26: „auch die von der Stadt") — ein amtlicher Titel
#: wird hier nicht umformuliert, nur entstolpert. Wer den Antrag im
#: Ratsinformationssystem sucht, findet ihn über den Link der Anlage, nicht
#: über diese Zeile.
#:
#: Erhoben an den zwölf Fundstellen, nicht geraten. Neue Fälle kommen dazu,
#: wenn sie auftreten — eine Rechtschreibprüfung wäre hier falsch: Sie würde
#: auch Eigennamen und Fachwörter „korrigieren", die stimmen.
_TIPPFEHLER = {
    "festegestellte": "festgestellte",
    "festgestelte": "festgestellte",
    "Belastungen ": "Belastungen ",
}

#: Abkürzungen, die im Dateinamen ohne Bindestrich an ihr Grundwort stoßen:
#: „PAK Belastung" ist „PAK-Belastung". Nur für Abkürzungen in Großbuchstaben
#: — bei gewöhnlichen Wörtern wäre die Regel falsch.
_ABK_KOMPOSITUM_RE = re.compile(r"\b([A-ZÄÖÜ]{2,6})\s+([A-ZÄÖÜ][a-zäöüß]{3,})")

#: … außer bei Parteien und Gruppen: „CDU Anwohnerparken" heißt, WER den
#: Antrag stellt, nicht WORUM es geht. Ein Bindestrich machte daraus ein
#: Kompositum, das es nicht gibt (aufgefallen beim Antrag vom 26.06.2023).
_KEIN_KOMPOSITUM = frozenset(
    {"CDU", "SPD", "FDP", "AFD", "BSW", "MDL", "MDB", "OB"}
)


def _entstolpern(text: str) -> str:
    """Offensichtliche Verschreiber im Dateinamen glätten."""
    for falsch, richtig in _TIPPFEHLER.items():
        text = re.sub(re.escape(falsch), richtig, text, flags=re.IGNORECASE)

    def _binden(m: re.Match) -> str:
        if m.group(1).upper() in _KEIN_KOMPOSITUM:
            return m.group(0)
        return f"{m.group(1)}-{m.group(2)}"

    return _ABK_KOMPOSITUM_RE.sub(_binden, text)


def titel_aus_label(label: str) -> str:
    """Aus dem Dateinamen einen Titel machen, der auf einer Karte steht.

    „250523 Antrag Dringlichkeit Fliegerhorst-Fraktionen" wird zu
    „Dringlichkeitsantrag: Fliegerhorst-Fraktionen". Bleibt nach dem Abräumen
    kein Thema übrig (es gibt Labels, die nur „Dringlichkeitsantrag" heißen),
    steht genau das da — eine ehrliche Zeile ohne Thema ist besser als ein
    erfundenes.
    """
    text = _NACHSPANN_RE.sub("", _VORSPANN_RE.sub("", (label or "").strip()))
    # Das Wort selbst raus, egal in welcher Schreibweise, samt Füllwörtern
    # drumherum („Antrag Dringlichkeit …", „Dringlichkeitsantrag …").
    thema = re.sub(r"\b(antrag\s+)?dringlichkeits?(antrag)?\b[\s:–-]*", "", text,
                   flags=re.IGNORECASE).strip(" -–:_.")
    thema = _entstolpern(re.sub(r"\s{2,}", " ", thema))
    return f"Dringlichkeitsantrag: {thema}" if thema else "Dringlichkeitsantrag"


def _ist_formalie(titel: str) -> bool:
    return bool(_FORMALIE_RE.search(titel or ""))


def zusatz_punkte(items: list) -> list:
    """Aus den Zeilen-Dokumenten einer Sitzung eigene Punkte machen.

    ``items`` sind die geparsten ``AgendaItem`` der Sitzungsseite; das
    Ergebnis kommt zusätzlich in dieselbe Liste. Jeder erzeugte Punkt trägt
    das Dokument als eigene Anlage weiter — nur so findet der Kartentext-Lauf
    später das PDF, in dem der Inhalt wirklich steht.
    """
    from .scraper import AgendaItem  # noqa: PLC0415 — sonst Ringschluss

    raus: list = []
    for item in items:
        if not _ist_formalie(item.title):
            continue          # hängt er inhaltlich, ist der Punkt schon da
        for anlage in item.anlagen or []:
            if not IST_DRINGLICH_RE.search(anlage.get("label") or ""):
                continue
            raus.append(AgendaItem(
                item_number=f"DZT {len(raus) + 1}",
                title=titel_aus_label(anlage["label"]),
                is_public=item.is_public,
                anlagen=[{**anlage, "raw_text": _pdf_text_leise(anlage.get("url"))}],
            ))
    return raus


def _pdf_text_leise(url: str | None) -> str:
    """Den Antrag auslesen — der einzige Ort, an dem sein Inhalt steht.

    Ohne ihn bewertet die Tragweite den DATEINAMEN: Der PAK-Antrag vom
    31.08.26 kam so auf 55 von 100 und verpasste die Karte, obwohl im PDF
    eine Schadstoffbelastung eines Gewässers und Sofortmaßnahmen standen.

    Der Griff ins Netz steht bewusst hier und nicht im Kartentext-Lauf: So
    liest ihn AUCH die Bewertung, und beide sehen dasselbe. Er kostet einen
    Download je Dringlichkeitsantrag — an 40 Ratssitzungen gemessen sind das
    zwölf in vier Jahren. Schlägt er fehl, bleibt es beim Titel; ein Antrag
    ohne Text ist besser als kein Antrag.
    """
    if not url:
        return ""
    try:
        from .vorlagen import _pdf_text  # noqa: PLC0415 — sonst Ringschluss

        text, _seiten = _pdf_text(url)
        return text
    except Exception:  # noqa: BLE001 — ein kaputtes PDF kippt keine Tagesordnung
        return ""
