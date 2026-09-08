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
from dataclasses import dataclass
from typing import Literal

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
        key="fit", version="1", applies_to=("paper",),
        prompt_system="cities_fit_system", prompt_user="cities_fit_user",
        model=os.environ.get("CITIES_FIT_MODEL", "deepseek/deepseek-v4-flash"),
        payload=OldenburgFit,
        # Ein Aufruf je Vorlage: Jede hat ihre eigenen Belege, ein Batch
        # teilte sie sich und das Modell verwechselte, welcher zu welcher gehört.
        # 6.000 statt 4.000 seit dem Ausbau auf vier Beleg-Arme: Zwölf Belege
        # statt acht heißen mehr abzuwägen, und ein zu knappes Budget liefert
        # keine Fehlermeldung, sondern eine ABGESCHNITTENE Antwort mit Status
        # 200 — im Prüfstand als „unlesbare Antwort“ sichtbar geworden.
        batch_size=1, input_chars=3500, max_tokens=6000, needs_index=True,
        gut_wenn="eval/run_cities_fit.py hält fünf Schranken. Zwei sind harte "
                 "Zusagen und stehen bei NULL: erfundene Beleg-Kennungen und "
                 "falsche „vorhanden“ (Oldenburg habe etwas, das fehlt — in "
                 "sieben Läufen nie vorgekommen). Drei sind "
                 "Regressions-Schranken, zehn Punkte unter dem gemessenen Stand: "
                 "Status über 55 % (gemessen 64 %), „lohnt sich“ über 50 % "
                 "(gemessen 59 %), Beleg-Disziplin über 95 %. Die drei Klassen "
                 "sind auch unter Menschen strittig; was zählt, ist dass das "
                 "Modell nie behauptet, Oldenburg habe etwas, das fehlt.",
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
