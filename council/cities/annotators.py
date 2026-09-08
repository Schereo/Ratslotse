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

from pydantic import BaseModel, Field

from council.topics import POLICY_FIELDS

FIELD_KEYS = tuple(POLICY_FIELDS)

#: Wie übertragbar ist eine fremde Vorlage auf Oldenburg?
TRANSFER_VALUES = ("local", "one_off", "jurisdiction", "adaptable", "direct")
#: Die zwei Stufen, die eine Idee ausmachen — die Entscheidung, die das
#: Produkt trifft. Die feinere Fünfteilung ist Beiwerk.
USABLE = ("adaptable", "direct")
#: Wer müsste das in Oldenburg tun?
COMPETENCE_VALUES = ("council", "administration", "utility", "holding", "state")


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
}


def active_annotators(object_kind: str | None = None) -> list[Annotator]:
    return [a for a in ANNOTATORS.values()
            if a.active and (object_kind is None or object_kind in a.applies_to)]


def get(key: str) -> Annotator:
    if key not in ANNOTATORS:
        raise KeyError(f"unbekannter Annotator {key!r}; bekannt: {sorted(ANNOTATORS)}")
    return ANNOTATORS[key]
