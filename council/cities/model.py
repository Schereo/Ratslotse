"""Die acht OParl-Objekte als Datenklassen — plus die kanonischen Regeln.

**Warum OParl und kein eigenes Modell.** Vier Hersteller liefern
Ratsinformationen bereits in dieser Form, und Oldenburgs SessionNet-Bestand
bildet sich verlustfrei darauf ab. Die Dialekte der Hersteller gehören in die
Adapter (``council/cities/adapters/``), nicht ins Datenmodell — danach weiß
keine Auswertung mehr, aus welchem System ein Papier kam, und muss es auch
nicht.

**Die kanonischen Felder sind bewusst kurz.** ``PaperKind`` und ``Outcome``
haben so wenige Werte wie möglich, weil jeder zusätzliche Wert eine
Fallunterscheidung in jeder Auswertung erzwingt. Der Rohwert steht immer
daneben (``paper_type_raw``, ``result_raw``): Eine bessere Regel kann später
neu ableiten, ohne dass jemand die Quelle erneut abruft.

**Was hier NICHT hingehört:** alles, was ein Modell über ein Objekt *sagt* —
Themenfeld, Zusammenfassung, Übertragbarkeit. Das sind Annotationen
(Schicht 3, Tabelle ``annotations``), keine Eigenschaften des Objekts.
``tests/test_cities_guards.py`` hält die Grenze.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class PaperKind(StrEnum):
    """Was für ein Papier ist das? Die Vorlagenarten der Städte sind bunt
    (Osnabrück kennt 4, Köln über 40); diese neun tragen jede davon."""

    MOTION = "motion"           #: Antrag, Anregung, Resolution — aus der Politik
    AMENDMENT = "amendment"     #: Änderungsantrag zu einer anderen Vorlage
    INQUIRY = "inquiry"         #: Anfrage an die Verwaltung
    ANSWER = "answer"           #: Antwort/Stellungnahme der Verwaltung darauf
    PROPOSAL = "proposal"       #: Beschlussvorlage der Verwaltung
    REPORT = "report"           #: Informations-/Berichtsvorlage, Kenntnisnahme
    NOTICE = "notice"           #: Mitteilung
    PETITION = "petition"       #: Einwohnerantrag, Petition, Anregung nach § 24 GO NRW
    OTHER = "other"


class Outcome(StrEnum):
    """Wie ist ein Tagesordnungspunkt ausgegangen? Dieselben Werte wie
    ``council_decisions.outcome`` in Oldenburg, plus zwei, die es dort nicht
    braucht (``amended``, ``referred``) und die andere Städte ausweisen."""

    ACCEPTED = "accepted"
    AMENDED = "amended"         #: geändert beschlossen
    REJECTED = "rejected"
    POSTPONED = "postponed"
    NOTED = "noted"             #: zur Kenntnis genommen
    REFERRED = "referred"       #: verwiesen/überwiesen an ein anderes Gremium
    WITHDRAWN = "withdrawn"
    NONE = "none"               #: kein Ergebnis ausgewiesen (der Normalfall bei ~42 %)


class OrgKind(StrEnum):
    """Gremium, Fraktion oder Amt? Entscheidend für den Vergleich: Braunschweig
    hat 128 Stadtbezirksräte unter 267 Gremien, deren Kleinanträge Oldenburg
    (kreisfrei, ohne Ortsräte) gar nicht kennt."""

    COUNCIL = "council"
    COMMITTEE = "committee"
    DISTRICT = "district"       #: Ortsrat, Bezirksvertretung, Stadtbezirksrat
    FACTION = "faction"
    ADMINISTRATION = "administration"
    OTHER = "other"


class FileRole(StrEnum):
    """Wofür steht die Datei am Objekt? ``MAIN`` ist das, was den Inhalt
    trägt — bei ALLRIS das „Sammeldokument", bei Somacos eine Anlage mit
    passendem Namen."""

    MAIN = "main"
    AUXILIARY = "auxiliary"
    RESOLUTION = "resolution"   #: Beschlussausfertigung am Tagesordnungspunkt
    INVITATION = "invitation"
    PROTOCOL = "protocol"
    OTHER = "other"


@dataclass(frozen=True)
class Body:
    id: str
    name: str
    state: str
    ris_vendor: str
    oparl_url: str | None = None
    license: str | None = None
    population: int | None = None


@dataclass(frozen=True)
class Organization:
    id: str
    body_id: str
    name: str
    kind_raw: str | None
    kind: OrgKind


@dataclass(frozen=True)
class Meeting:
    id: str
    body_id: str
    organization_id: str | None
    name: str
    start: str | None
    end: str | None = None
    state_raw: str | None = None
    cancelled: bool = False


@dataclass(frozen=True)
class AgendaItem:
    id: str
    meeting_id: str
    name: str
    number: str | None = None
    position: int | None = None
    public: bool = True
    result_raw: str | None = None
    outcome: Outcome = Outcome.NONE
    resolution_text: str | None = None


@dataclass(frozen=True)
class Paper:
    id: str
    body_id: str
    name: str
    reference: str | None = None
    date: str | None = None
    paper_type_raw: str | None = None
    kind: PaperKind = PaperKind.OTHER
    originator_org_id: str | None = None
    under_direction_of_id: str | None = None
    web: str | None = None


@dataclass(frozen=True)
class File:
    id: str
    body_id: str
    role: FileRole
    paper_id: str | None = None
    agenda_item_id: str | None = None
    meeting_id: str | None = None
    name: str | None = None
    mime: str | None = None
    size: int | None = None
    access_url: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class Consultation:
    id: str
    paper_id: str
    meeting_id: str | None = None
    agenda_item_id: str | None = None
    organization_id: str | None = None
    role_raw: str | None = None
    authoritative: bool | None = None


@dataclass
class Batch:
    """Was ein Adapter aus einer Rohernte macht — alles auf einmal.

    Die Schreibseite (``CitiesStore.upsert_batch``) arbeitet damit in EINER
    Transaktion: Bricht ein Lauf mitten drin ab, bleibt kein halber Jahrgang
    stehen (dieselbe Regel wie für die Ingests in ``council/``).
    """

    organizations: list[Organization] = field(default_factory=list)
    meetings: list[Meeting] = field(default_factory=list)
    agenda_items: list[AgendaItem] = field(default_factory=list)
    papers: list[Paper] = field(default_factory=list)
    files: list[File] = field(default_factory=list)
    consultations: list[Consultation] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "organizations": len(self.organizations),
            "meetings": len(self.meetings),
            "agenda_items": len(self.agenda_items),
            "papers": len(self.papers),
            "files": len(self.files),
            "consultations": len(self.consultations),
        }

    def extend(self, other: Batch) -> None:
        self.organizations.extend(other.organizations)
        self.meetings.extend(other.meetings)
        self.agenda_items.extend(other.agenda_items)
        self.papers.extend(other.papers)
        self.files.extend(other.files)
        self.consultations.extend(other.consultations)


# ---------------------------------------------------------------------------
# Kanonische Regeln. Reihenfolge ist Priorität — der erste Treffer gewinnt.
# ---------------------------------------------------------------------------

#: Muster → Art. **Reihenfolge ist entscheidend:** „Änderungsantrag" enthält
#: „antrag", „Beantwortung einer Anfrage" enthält „anfrage". Wer die Liste
#: umsortiert, ändert die Klassifikation — ``tests/test_cities_model.py``
#: hält genau diese Fälle fest.
_PAPER_KIND_RULES: tuple[tuple[tuple[str, ...], PaperKind], ...] = (
    (("änderungsantrag", "aenderungsantrag", "ergänzungsantrag", "ergaenzungsantrag"), PaperKind.AMENDMENT),
    (("antwort", "beantwortung", "stellungnahme"), PaperKind.ANSWER),
    (("anfrage",), PaperKind.INQUIRY),
    (("petition", "einwohnerantrag", "einwohnerfrage", "bürgerantrag", "buergerantrag"), PaperKind.PETITION),
    (("antrag", "anregung", "resolution"), PaperKind.MOTION),
    (("informationsvorlage", "berichtsvorlage", "kenntnisnahme", "bericht"), PaperKind.REPORT),
    (("beschlussvorlage", "entscheidungsvorlage", "beschlußvorlage"), PaperKind.PROPOSAL),
    (("mitteilung",), PaperKind.NOTICE),
)

#: Vorlagenarten, die für sich allein stehen (nicht als Teilwort gesucht):
#: Münster nennt seine Verwaltungsvorlagen schlicht „Vorlagen".
_PAPER_KIND_EXACT: dict[str, PaperKind] = {
    "vorlage": PaperKind.PROPOSAL,
    "vorlagen": PaperKind.PROPOSAL,
    "anhörung": PaperKind.REPORT,
    "anhoerung": PaperKind.REPORT,
}


def paper_kind(raw: str | None) -> PaperKind:
    """Vorlagenart → kanonische Art.

    Der Rohwert bleibt in ``papers.paper_type_raw`` stehen; diese Funktion ist
    jederzeit neu anwendbar.
    """
    text = (raw or "").strip().lower()
    if not text:
        return PaperKind.OTHER
    # Katalog-Klammern wie „Berichtsvorlage (bis 31.12.2022)" abschneiden —
    # das RIS Oldenburg führt 3.060 von 4.983 Vorlagen so.
    text = re.sub(r"\s*\(bis [^)]*\)\s*", " ", text).strip()
    if text in _PAPER_KIND_EXACT:
        return _PAPER_KIND_EXACT[text]
    for needles, kind in _PAPER_KIND_RULES:
        if any(n in text for n in needles):
            return kind
    return PaperKind.OTHER


#: Muster → Ergebnis. „geändert beschlossen" und „abgelehnt" MÜSSEN vor
#: „beschlossen" stehen, sonst frisst der ACCEPTED-Zweig sie.
_OUTCOME_RULES: tuple[tuple[tuple[str, ...], Outcome], ...] = (
    (("geändert beschlossen", "geaendert beschlossen", "geänderte empfehlung",
      "geaenderte empfehlung", "mit änderung", "mit aenderung", "geändert zugestimmt"), Outcome.AMENDED),
    (("abgelehnt", "nicht beschlossen", "keine zustimmung", "abgelehnt."), Outcome.REJECTED),
    # „geschoben" fängt auch „verschoben" und „aufgeschoben" — und vor allem
    # Münsters „ohne Beschlussfassung geschoben", das 288-mal als ANGENOMMEN
    # dastand, weil „beschlussfassung" in der Zustimmungsliste steht. Dieselbe
    # Falle wie „nicht empfohlen", nur mit einem anderen Wort davor: Der
    # Zustimmungs-Zweig ist der letzte, also fängt ihn jede frühere Regel ab.
    (("vertagt", "zurückgestellt", "zurueckgestellt", "abgesetzt", "geschoben",
      "verschoben"), Outcome.POSTPONED),
    (("verwiesen", "überwiesen", "ueberwiesen", "weitergeleitet"), Outcome.REFERRED),
    (("zurückgezogen", "zurueckgezogen", "erledigt", "zurückgenommen"), Outcome.WITHDRAWN),
    (("kenntnis",), Outcome.NOTED),
    (("beschlossen", "angenommen", "genehmigt", "empfohlen", "empfehlung",
      "zugestimmt", "beschlussfassung"), Outcome.ACCEPTED),
)

#: Verneinte Zustimmung — steht VOR den Zustimmungswörtern, weil sie sie
#: enthält. „nicht empfohlen" ist eine Ablehnung; als ``ACCEPTED" gezählt war
#: sie 275-mal (Magdeburg, 08.09.2026) das genaue Gegenteil dessen, was im
#: Protokoll steht. Dieselbe Komposita-Falle wie bei „ungeändert beschlossen",
#: nur mit einem getrennt geschriebenen „nicht" — deshalb reicht das
#: Ersetzen dort nicht, und es braucht eine eigene Regel.
#: Die Wörter sind genau die Zustimmungswörter der Regel darüber — ein
#: verneintes Wort, das dort nicht steht, könnte diesen Zweig nie erreichen.
_ABLEHNUNG_RE = re.compile(
    r"nicht\s+(beschlossen|angenommen|genehmigt|empfohlen|zugestimmt)")

#: Kein Ergebnis, obwohl ein Zustimmungswort im Satz steht: „keine
#: Beschlussfassung wegen Sitzungsabsage" (Münster, 10-mal), „Kein explizites
#: Abstimmungsergebnis im Protokoll vermerkt" (Oldenburg, 6-mal). Beide
#: standen als ``ACCEPTED`` da. Läuft NACH der Kenntnisnahme-Regel: „Kein
#: Beschluss, nur Bericht zur Kenntnis genommen" ist eine Kenntnisnahme.
_KEIN_ERGEBNIS_RE = re.compile(
    r"\bkein(?:e|en|es)?\b[^.]{0,40}?"
    r"\b(ergebnis|beschlussfassung|abstimmung|beschluss)\b")


def outcome(raw: str | None) -> Outcome:
    """Ergebnistext eines Tagesordnungspunkts → kanonisches Ergebnis.

    Rund 42 % der Tagesordnungspunkte tragen gar kein Ergebnis (gemessen über
    22.494 Punkte aus fünf Städten); dafür steht ``NONE``, nicht ``None`` —
    ein Ergebnis ist immer gesetzt, nur manchmal leer.

    **Die Falle, an der die erste Fassung scheiterte:** „ungeändert
    beschlossen" enthält wörtlich „geändert beschlossen". Deutsche Komposita
    verschieben die Wortgrenze (dieselbe Regel wie für Regexe in
    ``council/CLAUDE.md``), deshalb wird die Verneinung vorher entschärft.

    **Dieselbe Falle mit Abstand dazwischen**, gefunden erst, als Magdeburgs
    Vokabular dazukam: „nicht empfohlen" enthält „empfohlen", „keine
    Beschlussfassung" enthält „beschlussfassung". Ein Ersetzen hilft hier
    nicht — die Verneinung steht als eigenes Wort davor. Sie wird deshalb
    geprüft, bevor die Zustimmungswörter zugreifen, und zwar **nach** der
    Kenntnisnahme: „Kein Beschluss, nur Bericht zur Kenntnis genommen" ist
    eine Kenntnisnahme und kein fehlendes Ergebnis.
    """
    text = (raw or "").strip().lower()
    if not text:
        return Outcome.NONE
    # „ungeändert" → „unveraendert": enthält kein „geändert" mehr, bleibt aber
    # als Wort erhalten, falls eine spätere Regel darauf zugreifen will.
    text = text.replace("ungeänder", "unveraender").replace("ungeaender", "unveraender")
    for needles, value in _OUTCOME_RULES:
        if any(n in text for n in needles):
            # Erst hier, weil die Verneinung nur die Zustimmung umdrehen darf:
            # „nicht verwiesen" gibt es nicht, „nicht empfohlen" schon.
            if value is Outcome.ACCEPTED:
                if _ABLEHNUNG_RE.search(text):
                    return Outcome.REJECTED
                if _KEIN_ERGEBNIS_RE.search(text):
                    return Outcome.NONE
            return value
    return Outcome.NONE


_ORG_DISTRICT = ("stadtbezirk", "bezirksrat", "bezirksvertretung", "ortsrat",
                 "ortsbeirat", "ortschaftsrat", "bürgerforum", "buergerforum",
                 "bezirksverwaltung")
_ORG_FACTION = ("fraktion", "gruppe ", "ratsgruppe", "parlamentarische gruppe")
#: Der Rat selbst — als Regex mit vorderer Wortgrenze. Ohne sie wäre
#: „Aufsichtsrat der Stadtwerke" der Stadtrat (es enthält „rat der stadt").
_ORG_COUNCIL_RE = re.compile(
    r"(?<![a-zäöüß])(rat der stadt|stadtrat|stadtverordnetenversammlung"
    r"|ratsversammlung|bürgerschaft|buergerschaft)")
_ORG_COMMITTEE = ("ausschuss", "beirat", "kommission", "ältestenrat", "aeltestenrat")
_ORG_ADMIN = ("amt für", "amt fuer", "dezernat", "fachbereich", "stabsstelle",
              "referat", "verwaltung", "eigenbetrieb", "geschäftsbereich",
              "geschaeftsbereich")


def org_kind(name: str, raw_type: str | None = None) -> OrgKind:
    """Gremienname → kanonische Art.

    Ortsteil-Ebene wird zuerst geprüft: „Stadtbezirksrat im Stadtbezirk 330"
    enthält kein „ausschuss", aber „Ausschuss für Vielfalt im Stadtbezirk"
    gäbe es — und der wäre trotzdem Ortsteil-Ebene.
    """
    text = (name or "").strip().lower()
    typ = (raw_type or "").strip().lower()
    if typ == "verwaltungsbereich":
        return OrgKind.ADMINISTRATION
    if any(n in text for n in _ORG_DISTRICT):
        return OrgKind.DISTRICT
    if any(n in text for n in _ORG_FACTION):
        return OrgKind.FACTION
    if _ORG_COUNCIL_RE.search(text) or text == "rat":
        return OrgKind.COUNCIL
    if any(n in text for n in _ORG_COMMITTEE):
        return OrgKind.COMMITTEE
    if any(n in text for n in _ORG_ADMIN):
        return OrgKind.ADMINISTRATION
    return OrgKind.OTHER


#: Namen, an denen Somacos-Session das Hauptdokument erkennbar macht — dort
#: gibt es kein ``mainFile``, alles hängt unter ``auxiliaryFile``.
_MAIN_FILE_NAMES = ("sammeldokument", "vorlage", "antrag", "anfrage",
                    "beschlussvorlage", "mitteilung", "stellungnahme")


def file_role(name: str | None, oparl_key: str) -> FileRole:
    """Dateiname und OParl-Schlüssel → Rolle der Datei."""
    key = (oparl_key or "").strip()
    if key == "mainFile":
        return FileRole.MAIN
    if key == "resolutionFile":
        return FileRole.RESOLUTION
    if key == "invitation":
        return FileRole.INVITATION
    if key in ("resultsProtocol", "verbatimProtocol"):
        return FileRole.PROTOCOL
    if key == "auxiliaryFile":
        text = (name or "").strip().lower()
        if any(n in text for n in _MAIN_FILE_NAMES):
            return FileRole.MAIN
        return FileRole.AUXILIARY
    return FileRole.OTHER


# --------------------------------------------------------------- Urheber

#: Modelle schreiben gelegentlich das WORT „null" statt eines leeren Feldes.
_LEERE_WERTE = {"null", "none", "nil", "-", "–", "k.a.", "keine angabe", "unbekannt"}


def display_originator(raw: str | None, kind: str | None = None) -> str | None:
    """Der Urheber, so wie er angezeigt werden darf.

    **Namen von Ratsmitgliedern bleiben stehen** (Tims Entscheidung
    08.09.2026). Wer einen Antrag stellt oder eine Anfrage einreicht, tut das
    als Mandatsträgerin in einem öffentlichen Verfahren; der Name gehört zur
    Sache. Gemessen am Bestand stehen alle 1.860 Urheber-Angaben an Anträgen,
    Anfragen, Änderungsanträgen, Antworten, Berichten, Vorlagen und
    Mitteilungen — also durchweg an Papieren aus Rat und Verwaltung.

    **Bei einer Eingabe ist es umgekehrt.** Einwohneranträge, Bürgeranträge
    und Anregungen nach § 24 GO NRW kommen von Privatpersonen. Deren Namen
    stehen zwar im Ratsinformationssystem der jeweiligen Stadt, aber sie von
    dort auf eine Oldenburger Beschlussseite zu heben, ist etwas anderes, als
    sie dort zu belassen. Für ``PaperKind.PETITION`` gibt es deshalb keinen
    Urheber — die Sache zählt, nicht wer sie eingereicht hat.

    Der Bestand enthält heute **keine** Eingabe; die Regel greift für den Tag,
    an dem eine Stadt dazukommt, die welche veröffentlicht.
    """
    text = (raw or "").strip()
    if not text or text.casefold() in _LEERE_WERTE:
        return None
    if (kind or "") == PaperKind.PETITION.value:
        return None
    return text
