"""Wer was über ein Objekt sagt — als Code, wie ``kern/features.py``.

**Der Kern der Flexibilität.** Eine neue Frage an die Dokumente ist ein
Eintrag hier plus ein Prompt in ``kern/prompts.py`` — keine Schemaänderung,
keine Migration. Zwei Fassungen desselben Annotators liegen nebeneinander in
``annotations`` und lassen sich gegeneinander messen, statt dass die neue die
alte überschreibt.

**Was der Probelauf darüber gelernt hat.** Dasselbe Modell traf mit der ersten
Prompt-Fassung 73 % der Übertragbarkeits-Entscheidungen, mit der zweiten rund
87 % (fünf Läufe, 84 bis 91 %). Ein elfmal teureres Modell lag bei 71 %. Der
Prompt ist der Hebel, nicht das Modell — deshalb trägt jeder Annotator seine
Fassung im Schlüssel und wird gegen ein Golden Set gemessen
(``eval/run_cities_transfer.py``).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from council.topics import POLICY_FIELDS

FIELD_KEYS = tuple(POLICY_FIELDS)

#: Wie übertragbar ist eine fremde Vorlage auf Oldenburg?
TRANSFER_VALUES = ("local", "one_off", "jurisdiction", "adaptable", "direct")
#: Die zwei Stufen, die eine Idee ausmachen — die Entscheidung, die das
#: Produkt trifft. Die feinere Fünfteilung ist Beiwerk.
USABLE = ("adaptable", "direct")
#: Wer müsste das in Oldenburg tun?
COMPETENCE_VALUES = ("council", "administration", "utility", "holding", "state")

#: Hat Oldenburg GENAU dieses Instrument schon? Drei Stufen, weil zwei zu grob
#: sind: „teilweise" ist der häufigste ehrliche Befund — ein Antrag ohne
#: Beschluss, ein Prüfauftrag, ein kleinerer Zuschnitt.
FIT_STATUS = ("present", "partial", "missing")
#: Lohnt ein Antrag im Oldenburger Rat? Eine EIGENE Frage, nicht die Umkehrung
#: des Status: Auch bei „partial" kann gerade der Unterschied die Idee sein.
FIT_WORTH = ("yes", "maybe", "no")
CONFIDENCE_VALUES = ("high", "medium", "low")


#: Was es kostet, diese Idee in Oldenburg zu verfolgen — von der Frage bis zum
#: Haushaltsposten. **Das ist keine Verfeinerung der Übertragbarkeit, sondern
#: eine andere Frage:** „Eine Anfrage zu Fußwegbreiten stellen" und „ein
#: Darlehensprogramm für Genossenschaften einführen" standen bisher
#: gleichberechtigt auf einer Liste, obwohl ein Ratsmitglied sie sofort
#: unterscheidet. 31 % der übertragbaren Vorlagen sind Anfragen oder deren
#: Antworten (gemessen 08.09.2026).
EFFORT_VALUES = ("inquiry", "review", "resolution", "decision", "budget")


#: Was eine Vorlage mit der gemeinsamen Sache ihrer Gruppe vorhat.
#:
#: **Warum das gebraucht wird.** „Verpackungssteuersatzung erlassen"
#: (Braunschweig) und „Verpackungssteuer-Prüfung einstellen" (Magdeburg)
#: liegen im selben Cluster — zu Recht, es ist dieselbe Sache — und standen
#: beide als fehlende Idee auf der Liste. ``cluster_check`` hat das gesehen
#: und die Gruppe ausdrücklich BEHALTEN: Sie ist richtig, nur die Richtung
#: ist verschieden. Was fehlte, war ein Feld, das die Richtung trägt.
STANCE_VALUES = ("for", "against", "review")


class IdeaStance(BaseModel):
    """Wohin diese Vorlage die gemeinsame Sache bewegen will.

    - ``for``: Die Vorlage WILL die Sache — sie einführen, ausweiten,
      fortschreiben, umsetzen.
    - ``against``: Sie will sie NICHT — verhindern, einstellen, zurücknehmen,
      einschränken.
    - ``review``: Erst prüfen, berichten, Machbarkeit klären. Noch keine
      Festlegung.

    **Drei Klassen und nicht fünf, und das ist gemessen.** Die erste Fassung
    unterschied ``introduce`` / ``expand`` / ``restrict`` / ``stop`` /
    ``review``. Ergebnis am 09.09.2026 gegen 46 Handfälle: **72 %**, und
    sechs der dreizehn Fehler waren ``introduce`` gegen ``expand`` — „Lärm-
    aktionsplan fortschreiben" ist beides, je nachdem ob man den Plan oder
    seine Fortschreibung für die Sache hält. Ich konnte die Grenze selbst
    nicht scharf ziehen; eine Klasse, für die es keine Regel gibt, ist keine
    Klasse. Zusammengelegt: **87 %**, über der Schranke.

    Für die Karte ist es ohnehin das, was man lesen will: „4 Räte dafür,
    1 dagegen, 2 prüfen erst".

    **Die Richtung ist RELATIV zur Sache, nicht zum Verb der Überschrift.**
    Das ist die Falle, an der eine naive Umsetzung scheitert:
    „Straßenausbaubeiträge abschaffen" ist ``introduce``, wenn die Sache der
    Gruppe „Straßenausbaubeiträge abschaffen" heißt — die Abschaffung IST
    die Sache, und die Vorlage will sie. ``stop`` wäre dort ein Antrag, der
    die Abschaffung verhindert. Gemessen am 09.09.2026 tragen 24 Vorlagen in
    Gruppen mit drei oder mehr Städten ein solches Gegen-Wort im Instrument,
    und die Hälfte davon meint damit die Sache selbst.

    Deshalb bekommt das Modell das LABEL der Gruppe aus ``cluster_check`` als
    Bezugspunkt — es liegt für alle 81 Gruppen mit drei oder mehr Städten vor.
    """

    stance: Literal[STANCE_VALUES]  # type: ignore[valid-type]
    reason: str = Field(default="", max_length=200)


#: Anrede oder Funktion, dahinter ein Name. Der Name fällt weg, die Funktion
#: bleibt. Bewusst großzügig: Ein zu viel entfernter Nachname kostet nichts,
#: ein stehengebliebener bricht eine Zusage.
_FUNKTIONEN = ("Stadtrat", "Stadträtin", "Ratsherr", "Ratsfrau", "Ratsmitglied",
               "Oberbürgermeister", "Oberbürgermeisterin", "Bürgermeister",
               "Bürgermeisterin", "Bezirksbürgermeister", "Ausschussvorsitzender",
               "Ausschussvorsitzende", "Ratsvorsitzender", "Ratsvorsitzende",
               "Beigeordneter", "Beigeordnete", "Dezernent", "Dezernentin",
               "Erster Stadtrat", "Ortsvorsteherin", "Ortsvorsteher",
               # Die riskanteste Gruppe steht zuerst im Sinn, nicht zuletzt:
               # Ratsmitglieder dürften genannt werden, diese nicht.
               "Sachkundiger Einwohner", "Sachkundige Einwohnerin",
               "Sachkundiger Bürger", "Sachkundige Bürgerin",
               "Bürgermitglied", "Einwohnerin", "Einwohner", "Gast",
               "Bezirksbürgermeisterin", "Ortsbürgermeister", "Ortsbürgermeisterin",
               "Fachbereichsleiter", "Fachbereichsleiterin", "Amtsleiter",
               "Amtsleiterin", "Protokollführer", "Protokollführerin")
_NAMEN_RE = re.compile(
    r"\b(?:(" + "|".join(sorted(_FUNKTIONEN, key=len, reverse=True)) + r")|Herr|Frau)"
    r"\s+(?:Dr\.\s+|Prof\.\s+)*"
    r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?"
    r"(?:\s+[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)?")


def _ohne_name(m: re.Match) -> str:
    """``Frau Schiller`` -> ``Frau N.``, ``Stadtrat Rohne`` -> ``Stadtrat N.``

    Anrede und Funktion bleiben stehen, der Name fällt weg. Das ist der
    einzige Ersatz, der die Grammatik heil lässt: „von Frau N." liest sich,
    „von eine Person" nicht — und ein Satz, den niemand lesen mag, ist auf
    einer Vergleichskarte nichts wert.
    """
    return f"{m.group(1) or m.group(0).split()[0]} N."


class OutcomeReason(BaseModel):
    """Was in der Niederschrift zu diesem Tagesordnungspunkt steht.

    **Das ist eine Wiedergabe, keine Erklärung** — und dieser Unterschied ist
    der ganze Zweck der Klasse. Warum ein fremder Rat so entschieden hat, ist
    für die Diskussion in Oldenburg das Wertvollste, was der Vergleich zu
    bieten hat; ein Modell, das es *erfindet*, ist zugleich das Schädlichste.
    Deshalb trägt die Antwort ein Feld, das die Frage selbst beantwortet:

    ``grounded`` sagt, ob im Abschnitt eine **Begründung** steht — ein
    Argument, ein Einwand, eine Wortmeldung — oder nur ein Ergebnis. Der
    häufigere Fall ist „nur Ergebnis": Die meisten Beschlüsse fallen ohne
    Aussprache. Dann bleibt ``why`` leer, ``grounded`` ist ``False``, und die
    Karte zeigt an dieser Stelle nichts. Ein falsches ``True`` — Begründung
    behauptet, wo keine steht — zählt im Prüfstand wie eine erfundene
    Beleg-Kennung bei ``fit``: als harter Fehler, Schranke null.

    ``vote`` ist das Abstimmungsergebnis im Wortlaut („einstimmig",
    „12 dafür, 8 dagegen"), nicht umgerechnet. Es steht fast immer wörtlich
    da und ist damit die verlässlichste der vier Angaben.

    **Keine Personennamen.** Der Prompt verlangt Fraktionen und Rollen statt
    Namen. Die Protokolle sind öffentlich, unsere Wiedergabe muss es nicht
    sein — und ein Satz wie „Herr X hielt das für zu teuer" ist auf einer
    Vergleichskarte etwas anderes als in einer Niederschrift.
    """

    discussed: str = ""
    decided: str = ""
    vote: str | None = None
    why: str = ""
    grounded: bool = False

    #: Wie lang die Felder auf der Karte höchstens werden. **Gekürzt, nicht
    #: abgewiesen** — und das ist gemessen: Mit ``max_length`` warf die
    #: Prüfung fünf von 36 Antworten komplett weg, weil eine gute
    #: Zusammenfassung 417 statt 400 Zeichen lang war. Eine Längengrenze ist
    #: eine Anzeigefrage, keine inhaltliche; sie darf eine richtige Antwort
    #: nicht in einen Totalausfall verwandeln.
    GRENZEN: ClassVar[dict[str, int]] = {
        "discussed": 600, "decided": 300, "vote": 140, "why": 400}

    @field_validator("discussed", "decided", "why", mode="before")
    @classmethod
    def _kuerzen(cls, v, info: ValidationInfo) -> str:
        text = " ".join(str(v or "").split())
        grenze = cls.GRENZEN.get(info.field_name or "", 400)
        return text if len(text) <= grenze else text[:grenze - 1].rstrip() + "…"

    @field_validator("vote", mode="before")
    @classmethod
    def _vote_kuerzen(cls, v) -> str | None:
        text = " ".join(str(v or "").split())
        return text[:cls.GRENZEN["vote"]] or None

    @field_validator("discussed", "decided", "why")
    @classmethod
    def _ohne_namen(cls, v: str) -> str:
        """Personennamen aus der Ausgabe nehmen — im CODE, nicht im Prompt.

        Der Prompt verlangt Fraktionen und Rollen statt Namen, und das Modell
        hält sich meistens daran. **Meistens reicht nicht:** Gemessen am
        10.09.2026 standen in 2 von 36 Antworten trotzdem Namen („Frau
        Schiller", „Frau Tabea"). Eine Zusage, die bei null liegen soll, darf
        nicht an einer Bitte hängen — dieselbe Bauweise wie bei ``fit``, das
        erfundene Beleg-Kennungen nicht erbittet, sondern verwirft.

        Anrede und Funktion bleiben stehen, der Name fällt weg: „Stadtrat
        Rohne fragt" wird „Stadtrat N. fragt". Für die Karte zählt das
        Argument, nicht wer es vorgetragen hat.

        **Strenger als die Projektregel, und mit Absicht.** Ratsmitglieder
        dürften genannt werden — private Personen nicht. Nur steht in einem
        Protokoll beides nebeneinander („Sachkundiger Einwohner Fassl
        erkundigt sich …"), und weder ein Modell noch eine Regel unterscheidet
        das verlässlich. Also fällt jeder Name weg.
        """
        return _NAMEN_RE.sub(_ohne_name, v)


class IdeaEffort(BaseModel):
    """Was diese Idee den Oldenburger Rat kosten würde.

    Die fünf Stufen sind nach STEIGENDEM Aufwand geordnet, und die Grenze
    zwischen ihnen ist die Art des Ratsbeschlusses, nicht seine Größe:

    - ``inquiry``: eine Anfrage an die Verwaltung. Kostet eine Sitzung
      Aufmerksamkeit und sonst nichts.
    - ``review``: ein Prüfauftrag — „die Verwaltung möge prüfen und berichten".
      Kostet Verwaltungsarbeit, bindet den Rat aber zu nichts.
    - ``resolution``: eine Resolution an Land oder Bund. Kostet nichts und
      bewirkt unmittelbar auch nichts; die Zuständigkeit liegt woanders.
    - ``decision``: ein Beschluss mit unmittelbarer Wirkung — Satzung,
      Richtlinie, Konzept, Programm — ohne nennenswerten Haushaltsposten.
    - ``budget``: ein Beschluss, der Geld bindet: Förderprogramm, Stelle, Bau.
    """

    effort: Literal[EFFORT_VALUES]  # type: ignore[valid-type]
    #: Wer es in Oldenburg TUN müsste, wenn nicht die Stadt selbst — „Eigenbetrieb
    #: Gebäudewirtschaft", „VWG", „Großleitstelle Oldenburger Land". ``None``,
    #: wenn die Stadt es selbst entscheidet.
    #:
    #: Das ist die Frage, an der im Golden Set die meisten „lohnt sich"-Urteile
    #: hängen: Hausverbote in Bussen sind Sache der VWG, nicht des Rates.
    addressee: str | None = Field(default=None, max_length=60)

    @field_validator("addressee", mode="before")
    @classmethod
    def _kurz_genug(cls, v: object) -> object:
        """Zu langen Freitext kürzen statt den ganzen Eintrag zu verwerfen.

        Dieselbe Lehre wie bei ``OldenburgFit``: Ein um zwanzig Zeichen zu
        langer Adressat macht ein richtiges Urteil nicht falsch.
        """
        return v[:60] if isinstance(v, str) else v


class ClusterCheck(BaseModel):
    """Gehören wirklich alle Mitglieder eines Clusters zusammen?

    **Warum ein Modell und nicht eine höhere Schwelle.** Die Gruppierung
    kettet: Wer A und B für dieselbe Idee hält und B und C auch, steckt A und
    C in eine Menge, ohne sie je verglichen zu haben. Gemessen an acht
    Stichproben (09.09.2026) war einer von acht Clustern so entstanden — er
    mischte „Lärmaktionsplan evaluieren" mit „Tempo-30-Anordnung prüfen".
    Verwandt, aber nicht dasselbe. Eine höhere Schwelle zerreißt dagegen
    genau die Ketten, die den Wert ausmachen: Die Verpackungssteuer läuft
    über fünf Städte mit fünf Formulierungen.

    **Warum das seit PR 22 dringender ist.** Bis dahin war ein falscher
    Cluster eine Zahl in einem Bericht. Jetzt steht auf der Karte „auch in 4
    anderen Städten" — ein falscher Cluster ist damit eine falsche
    öffentliche Aussage.
    """

    #: Der gemeinsame Nenner in wenigen Wörtern. Dient der Kontrolle, nicht
    #: der Anzeige — den Namen vergibt weiterhin das typischste Mitglied.
    label: str = Field(default="", max_length=80)
    #: Papier-Kennungen, die NICHT zu diesem gemeinsamen Nenner gehören.
    #: Leer ist der Normalfall und die erwünschte Antwort.
    drop: list[str] = Field(default_factory=list)
    #: Ein Satz, warum sie herausfallen. Leer, wenn nichts herausfällt.
    reason: str = Field(default="", max_length=300)

    @field_validator("label", "reason", mode="before")
    @classmethod
    def _kuerzen(cls, v: object, info: ValidationInfo) -> object:
        """Freitext kürzen statt den ganzen Eintrag verwerfen — wie bei `fit`."""
        grenzen = {"label": 80, "reason": 300}
        return v[:grenzen.get(info.field_name or "", 300)] if isinstance(v, str) else v


class PaperClassification(BaseModel):
    """Was ein Modell über eine fremde Vorlage sagt.

    Die Felder sind geschlossene Listen, damit sie zählbar bleiben: Ein
    Freitext-Themenfeld wäre nach zehn Städten unbrauchbar.
    """

    field: Literal[FIELD_KEYS]  # type: ignore[valid-type]
    transfer: Literal[TRANSFER_VALUES]  # type: ignore[valid-type]
    competence: Literal[COMPETENCE_VALUES]  # type: ignore[valid-type]
    #: Der übertragbare Kern in zwei bis sechs Wörtern, ohne Ortsnamen.
    #: ``None`` bei reinen Personal-, Ehrungs- oder Formalvorgängen.
    instrument: str | None = None
    #: Antragstellende Fraktion, wörtlich wie im Text. Bei
    #: Verwaltungsvorlagen ``None``. Eine ORGANISATION, keine Person.
    originator: str | None = None
    summary: str = Field(default="", max_length=400)

    @property
    def usable(self) -> bool:
        return self.transfer in USABLE


class OldenburgStatus(BaseModel):
    """Hat Oldenburg dieses Instrument schon? — und sonst nichts.

    **Warum „lohnt sich?" hier nicht mehr steht.** Über drei Fassungen und
    vierzehn Messläufe traf das Modell den STATUS zu 62–69 % und zitierte
    seine Belege zu 100 % sauber; die Frage „lohnt sich ein Antrag?" traf es
    zu 46–58 % mit bis zu 20 Punkten Streuung, und die verschärfte Regel in
    Fassung 2 machte sie messbar schlechter statt besser (32 %). Es kann
    Tatsachen und keine Werturteile.

    Das ist keine Schwäche des Modells, sondern die richtige Arbeitsteilung:
    Ob sich ein Antrag lohnt, hängt an Mehrheiten, Haushaltslage und dem, was
    eine Fraktion gerade vorhat — nichts davon steht in einem
    Ratsinformationssystem. Die Oberfläche zeigt stattdessen fünf Tatsachen,
    aus denen ein Ratsmitglied in zwei Sekunden selbst schließt: Status,
    Belege, Aufwandsklasse, Adressat und die Zahl der Städte.

    Nebeneffekt, gemessen: Der Prompt wird um ein Drittel kürzer und die
    Antwort um die Hälfte — rund 40 % weniger Kosten je Urteil.
    """

    status: Literal[FIT_STATUS]  # type: ignore[valid-type]
    #: Kennungen aus der vorgelegten Beleg-Liste, höchstens drei. Leer nur bei
    #: ``missing`` — dort IST die leere Liste die Aussage.
    evidence: list[str] = Field(default_factory=list, max_length=3)
    reason: str = Field(default="", max_length=300)
    confidence: Literal[CONFIDENCE_VALUES]  # type: ignore[valid-type]

    @property
    def braucht_beleg(self) -> bool:
        """``present`` und ``partial`` sind Behauptungen über Oldenburg."""
        return self.status in ("present", "partial")

    @field_validator("reason", mode="before")
    @classmethod
    def _kuerzen(cls, v: object) -> object:
        """Zu langen Freitext kürzen statt das Urteil verwerfen.

        Zwei richtige Urteile gingen in einem Messlauf an einer Überlänge von
        zwanzig Zeichen verloren. Die BEHAUPTUNGEN bleiben streng — ein
        erfundener Beleg fliegt weiterhin ganz raus.
        """
        return v[:300] if isinstance(v, str) else v


class OldenburgFit(BaseModel):
    """Was ein Modell über die Eignung einer fremden Vorlage für Oldenburg sagt.

    **Ohne Beleg kein Urteil.** ``evidence`` trägt die Kennungen der Belege, auf
    die sich der Befund stützt — und ``council/cities/annotate.py`` prüft, dass
    jede davon dem Modell auch vorgelegen hat. Ein erfundener Beleg macht den
    ganzen Eintrag ungültig; er wird verworfen und gezählt. Das ist die Regel
    aus Schicht 1 („trägt keine Meinung") eine Ebene weiter: Eine Meinung darf
    gespeichert werden, aber nur mit ihrer Grundlage daneben.
    """
    status: Literal[FIT_STATUS]  # type: ignore[valid-type]
    #: Kennungen aus der vorgelegten Beleg-Liste, höchstens drei. Leer nur bei
    #: ``missing`` — dort IST die Leere die Aussage.
    evidence: list[str] = Field(default_factory=list, max_length=3)
    reason: str = Field(default="", max_length=300)
    worth: Literal[FIT_WORTH]  # type: ignore[valid-type]
    why_worth: str = Field(default="", max_length=300)
    #: Was dagegen spricht — Zuständigkeit, fehlende Struktur, schon gescheitert.
    obstacles: str | None = Field(default=None, max_length=200)
    confidence: Literal[CONFIDENCE_VALUES]  # type: ignore[valid-type]

    @field_validator("reason", "why_worth", "obstacles", mode="before")
    @classmethod
    def _kuerzen(cls, wert, info: ValidationInfo):
        """Freitext wird gekürzt, nicht verworfen.

        Die Längen oben sind Anzeige-Grenzen, keine Zusagen: `reason` und
        `why_worth` stehen als ein Satz auf einer Karte. Ein Modell, das einen
        Satz zwanzig Zeichen zu lang schreibt, hat deshalb nicht falsch
        geurteilt — im Bestandslauf über 300 Vorlagen gingen so zwei
        vollständig richtige Urteile verloren, beide an `obstacles`.

        Die BEHAUPTUNGEN — `status`, `worth`, `evidence` — bleiben streng.
        Dort ist ein unerwarteter Wert kein Formfehler, sondern ein Urteil,
        das niemand einordnen kann.
        """
        grenzen = {"reason": 300, "why_worth": 300, "obstacles": 200}
        if isinstance(wert, str):
            return wert.strip()[:grenzen[info.field_name or "reason"]]
        return wert

    @property
    def braucht_beleg(self) -> bool:
        """``present`` und ``partial`` sind Behauptungen über Oldenburg."""
        return self.status in ("present", "partial")


@dataclass(frozen=True)
class Annotator:
    key: str
    version: str
    #: Objektarten, auf die er anwendbar ist.
    applies_to: tuple[str, ...]
    prompt_system: str
    prompt_user: str
    model: str
    payload: type[BaseModel]
    batch_size: int = 6
    #: Reasoning-Modelle verbrauchen ihr Budget beim Denken; ein knapper Wert
    #: liefert eine LEERE Antwort mit Status 200 statt eines Fehlers.
    max_tokens: int = 16000
    temperature: float = 0.2
    #: So viele Zeichen des Volltexts gehen ins Modell. 2.200 waren im
    #: Probelauf der Punkt, an dem mehr Text die Trefferquote nicht mehr hob.
    input_chars: int = 2200
    active: bool = True
    #: Darf dieser Annotator ohne die ZDR-Provider-Beschränkung laufen?
    #: Hier gehen ausschließlich öffentliche Ratsdokumente anderer Städte
    #: durchs Modell, kein Nutzertext — anders als bei der KI-Frage. Die
    #: Beschränkung kostete messbar: ``gpt-5.6-luna`` lieferte mit ihr 53 %
    #: der Ergebnisse, ohne sie 100 % bei doppelter Geschwindigkeit.
    routing_free: bool = True
    #: Braucht der Annotator die Nachbarschaften? Dann läuft er NACH dem Index,
    #: nicht davor — sonst urteilt er über eine Stadt, deren nächste Verwandte
    #: er noch gar nicht kennt.
    needs_index: bool = False
    #: Nur Vorlagen, die die Einordnung als übertragbar führt? Für Fragen, die
    #: sich an einem Bebauungsplan gar nicht stellen. Spart hier drei Viertel
    #: der Kosten: 1.511 übertragbare von 24.591 Papieren.
    only_usable: bool = False
    #: Woran man erkennt, dass die Fassung reif ist — wie ``fertig_wenn`` bei
    #: den Feature-Schaltern.
    gut_wenn: str = ""

    @property
    def feature(self) -> str:
        """Der Schlüssel fürs Kosten-Tracking (``llm_usage.feature``).

        Steht hier statt an der Aufrufstelle, damit ``tests/test_feature_namen.py``
        ihn findet: Das Admin-Panel beschriftet jeden Schlüssel, und ein
        dynamisch zusammengesetzter wäre dort für immer roh.
        """
        return f"cities_{self.key}"


ANNOTATORS: dict[str, Annotator] = {
    "classify": Annotator(
        key="classify", version="2", applies_to=("paper",),
        prompt_system="cities_classify_system", prompt_user="cities_classify_user",
        model=os.environ.get("CITIES_CLASSIFY_MODEL", "deepseek/deepseek-v4-flash"),
        payload=PaperClassification,
        gut_wenn="eval/run_cities_transfer.py bleibt bei „taugt/taugt nicht“ über "
                 "80 % — darunter ist es eine Regression, darüber Rauschen "
                 "(gemessen: fünf Läufe zwischen 84 und 91 %).",
    ),
    "fit": Annotator(
        # Fassung 2 seit 09.09.2026: Ideen-Cluster und Aufwandsklasse im
        # Prompt, ein strengeres „lohnt sich" und drei Stimmen je Vorlage
        # statt einer. Fassung 1 bleibt in der Tabelle liegen, bis die
        # Oberfläche umgestellt ist (PR 22) — beide nebeneinander zu haben
        # ist der Zweck des Fassungs-Schlüssels.
        key="fit", version="3", applies_to=("paper",),
        prompt_system="cities_fit_system", prompt_user="cities_fit_user",
        model=os.environ.get("CITIES_FIT_MODEL", "deepseek/deepseek-v4-flash"),
        payload=OldenburgStatus,
        # Ein Aufruf je Vorlage: Jede hat ihre eigenen Belege, ein Batch
        # teilte sie sich und das Modell verwechselte, welcher zu welcher gehört.
        # 6.000 statt 4.000 seit dem Ausbau auf vier Beleg-Arme: Zwölf Belege
        # statt acht heißen mehr abzuwägen, und ein zu knappes Budget liefert
        # keine Fehlermeldung, sondern eine ABGESCHNITTENE Antwort mit Status
        # 200 — im Prüfstand als „unlesbare Antwort“ sichtbar geworden.
        batch_size=1, input_chars=3500, max_tokens=6000, needs_index=True,
        gut_wenn="eval/run_cities_fit.py hält drei Schranken, und ZWEI davon "
                 "sind harte Zusagen, die bei NULL stehen: erfundene "
                 "Beleg-Kennungen und falsche „vorhanden“ (das Modell "
                 "behauptet, Oldenburg habe etwas, das fehlt — in vierzehn "
                 "Läufen nie vorgekommen; es nimmt eine Idee von der Liste). "
                 "Die dritte ist eine Regressions-Schranke: Status über 55 % "
                 "(gemessen 62–69 % über drei Fassungen). Die drei Klassen "
                 "sind auch unter Menschen strittig.\n\n"
                 "Fassung 3 fragt „lohnt sich ein Antrag?“ NICHT mehr. Über "
                 "drei Fassungen traf das Modell den Status zu 62–69 % und die "
                 "Nutzenfrage zu 46–58 % bei bis zu 20 Punkten Streuung — die "
                 "verschärfte Regel in Fassung 2 machte sie messbar schlechter "
                 "(32 %). Es kann Tatsachen und keine Werturteile, und das ist "
                 "die richtige Arbeitsteilung: Ob sich ein Antrag lohnt, hängt "
                 "an Mehrheiten und Haushaltslage, und nichts davon steht in "
                 "einem Ratsinformationssystem.",
    ),
    "cluster_check": Annotator(
        key="cluster_check", version="1", applies_to=("cluster",),
        prompt_system="cities_cluster_check_system",
        prompt_user="cities_cluster_check_user",
        model=os.environ.get("CITIES_CLUSTER_MODEL", "deepseek/deepseek-v4-flash"),
        payload=ClusterCheck,
        # Ein Cluster je Aufruf: Die Frage ist ein Vergleich INNERHALB der
        # Menge, und zwei Mengen in einem Aufruf lädt genau zu der
        # Verwechslung ein, die hier gefunden werden soll.
        batch_size=1, input_chars=2000, max_tokens=4000,
        gut_wenn="Die MENGE entscheidet, nicht die Quote. Im ersten Messlauf "
                 "(09.09.2026) wollte das Modell aus 12 von 17 Gruppen etwas "
                 "entfernen, darunter 9 von 16 Mitgliedern einer einzigen — es "
                 "hatte das Label zu eng gefasst („Klimaschutz-Berichtswesen“) "
                 "und warf danach jedes „Konzept“ hinaus. Nach der Korrektur "
                 "(erst die Mehrheit suchen, dann filtern; höchstens ein "
                 "Drittel) fällt je Gruppe eines heraus. Steigt der Schnitt "
                 "wieder über ein Mitglied je Gruppe oder schlägt die "
                 "Ein-Drittel-Sicherung oft an (`zu_viel` in den Kennzahlen), "
                 "ist das Label wieder zu eng.",
    ),
    "stance": Annotator(
        key="stance", version="1", applies_to=("paper",),
        prompt_system="cities_stance_system", prompt_user="cities_stance_user",
        model=os.environ.get("CITIES_STANCE_MODEL", "deepseek/deepseek-v4-flash"),
        payload=IdeaStance,
        # Ein Aufruf je Vorlage, weil jede ihr eigenes Gruppen-Label als
        # Bezugspunkt braucht. Sechs Vorlagen aus sechs Gruppen in einem
        # Aufruf hieße sechs Bezugspunkte — genau die Verwechslung, die die
        # Frage kaputt macht.
        # 4.000 nicht, weil die Antwort lang wird — sie ist zwei Felder —,
        # sondern weil ein knappes Budget keine Fehlermeldung liefert,
        # sondern eine ABGESCHNITTENE Antwort mit Status 200.
        batch_size=1, input_chars=1200, max_tokens=4000,
        # Nur Vorlagen in einer Gruppe: Ohne gemeinsame Sache gibt es keine
        # Richtung, auf die sich das Urteil beziehen könnte.
        only_usable=True, needs_index=True,
        gut_wenn="eval/run_cities_stance.py gegen 40 Handfälle aus Gruppen mit "
                 "drei oder mehr Städten. Schranke 85 % — höher als bei "
                 "`transfer`, weil die Kanten schärfer sind: Eine Vorlage will "
                 "eine Sache oder sie will sie nicht. Strittig ist nur die "
                 "Grenze zwischen `introduce` und `review` (verlangt sie eine "
                 "Entscheidung oder erst Wissen?); steht die Verwechslungs-"
                 "matrix voll davon, ist der Prompt an dieser Stelle zu "
                 "unscharf und nicht das Modell zu schlecht.",
    ),
    "reason": Annotator(
        key="reason", version="1", applies_to=("agenda_item",),
        prompt_system="cities_reason_system", prompt_user="cities_reason_user",
        model=os.environ.get("CITIES_REASON_MODEL", "deepseek/deepseek-v4-flash"),
        payload=OutcomeReason,
        # Ein Abschnitt je Aufruf: Zwei Niederschriften in einem Aufruf laden
        # dazu ein, die Begründung der einen an den Beschluss der anderen zu
        # hängen — dieselbe Verwechslung, die `fit` und `stance` zu je einem
        # Objekt gezwungen hat.
        # 6.000 Zeichen, weil ein Abschnitt so lang wird; 4.000 Tokens, weil
        # ein knappes Budget keine Fehlermeldung liefert, sondern eine
        # ABGESCHNITTENE Antwort mit Status 200.
        batch_size=1, input_chars=6000, max_tokens=4000,
        # AUS, und zwar nicht wegen des Modells. Der erste Messlauf am
        # 10.09.2026 gegen 36 echte Abschnitte hat den Prüfstand widerlegt,
        # nicht den Annotator: Der einzige gemeldete „erfundene" Fall war
        # richtig — das Modell zitierte „auf Grund der kurzfristigen
        # Einreichung der Vorlage" aus dem Text, und mein Label war falsch,
        # weil ich beim Setzen nur die ersten Zeilen des Abschnitts gelesen
        # hatte. Ein Golden Set, das man per Regel setzt, misst die Regel.
        #
        # Was das Modell wirklich tut, sah in allen durchgesehenen Antworten
        # sauber aus: gute Zusammenfassungen der Beratung, konservatives
        # `grounded` (1 von 16 — es behauptet lieber keinen Grund als einen
        # falschen). Genau die richtige Richtung. Aber solange der Maßstab
        # nicht steht, läuft hier kein bezahlter Cron.
        #
        # Was fehlt: 40 Abschnitte, ganz gelesen, `has_reason` und `vote` von
        # Hand gesetzt. `eval/build_cities_reason_cases.py` zieht die
        # Stichprobe; das Urteil muss ein Mensch fällen.
        active=False,
        gut_wenn="eval/run_cities_reason.py gegen Handfälle aus echten "
                 "Niederschriften. Drei Schranken, und die erste ist eine "
                 "harte Zusage bei NULL: `grounded=true`, wo im Abschnitt gar "
                 "keine Begründung steht. Das ist derselbe Fehler wie eine "
                 "erfundene Beleg-Kennung bei `fit` — die Karte behauptet "
                 "dann ein „Warum“, das es nicht gibt, und genau dafür ist "
                 "das Feature da.\n\n"
                 "Die zweite: `vote` über 90 %. Es steht wörtlich im Text; "
                 "wer es nicht trifft, hat den Abschnitt falsch geschnitten "
                 "und nicht falsch gelesen. Die dritte ist eine Handdurchsicht "
                 "von `why` — trifft der Satz die Begründung? — mit Schranke "
                 "80 %.",
    ),
    "effort": Annotator(
        key="effort", version="1", applies_to=("paper",),
        prompt_system="cities_effort_system", prompt_user="cities_effort_user",
        model=os.environ.get("CITIES_EFFORT_MODEL", "deepseek/deepseek-v4-flash"),
        payload=IdeaEffort,
        # Kleiner Batch und wenig Text: Die Frage hängt am Titel und an der
        # Vorlagenart, nicht am Volltext. 1.500 Zeichen reichen, und acht
        # Einträge je Aufruf halten die Antwort kurz genug, dass keiner
        # ausgelassen wird.
        batch_size=8, input_chars=1500, max_tokens=4000, only_usable=True,
        gut_wenn="eval/run_cities_effort.py bleibt über 80 % über fünf Klassen. "
                 "Die Kanten sind schärfer als bei `transfer` — eine Anfrage ist "
                 "keine Satzung —, deshalb liegt die Schranke höher.",
    ),
}


def active_annotators(object_kind: str | None = None) -> list[Annotator]:
    return [a for a in ANNOTATORS.values()
            if a.active and (object_kind is None or object_kind in a.applies_to)]


def get(key: str) -> Annotator:
    if key not in ANNOTATORS:
        raise KeyError(f"unbekannter Annotator {key!r}; bekannt: {sorted(ANNOTATORS)}")
    return ANNOTATORS[key]
