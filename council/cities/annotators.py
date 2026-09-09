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
