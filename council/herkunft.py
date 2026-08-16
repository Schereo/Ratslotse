"""Woher eine gespeicherte Zahl stammt — ein Format für alle Finanz-Schichten.

Der Haushalts-Bereich trug seine Herkunft bis 08/2026 in drei verschiedenen
Schreibweisen: ``quelle_label``/``quelle_url`` in den einen Tabellen,
``label``/``url`` in der nächsten, ``source_url`` in den vier ältesten. Und
überall fehlte dasselbe: die Fundstelle **im** Dokument, die bestandene
Rechenprobe und ein Anker, der einen Dokumentwechsel überlebt.

Warum eine eigene Tabelle statt Spalten je Tabelle
---------------------------------------------------
Beide Wege standen zur Wahl. Entschieden hat der Blick auf die Schichten, die
noch kommen — Konzernabschluss, Beteiligungsbericht, Finanzhaushalt,
Stellenplan, Schuldenzeitreihe:

1. **Eine Tabelle trägt Zeilen aus verschiedenen Dokumenten.** Bei den
   Beteiligungen ist das der Normalfall: Dieselbe Kennzahl steht im
   Konzernabschluss, im Einzelabschluss der Gesellschaft und im
   Beteiligungsbericht — mit verschiedenen Stichtagen und
   Konsolidierungsstufen. Als Spaltensatz ließe sich das zwar auch je Zeile
   führen; als eigener Datensatz ist es aber **eine ID**, und die Frage „ist
   das dieselbe Herkunft?" beantwortet ein Vergleich statt neun Vergleichen.
2. **Ein neues Herkunftsfeld darf nicht neun ALTER TABLE kosten.** Käme
   morgen die Konsolidierungsstufe dazu, wäre das hier genau eine Spalte an
   genau einer Stelle — und alle Schichten hätten sie sofort.
3. **Wiederholung.** Ein Jahresabschluss-Jahrgang schreibt rund 200 Zeilen
   Ergebnisrechnung, alle aus demselben Dokument, an derselben Fundstelle,
   mit derselben Probe. Als Spalten wäre das dieselbe Angabe 200-mal.

Der Preis ist ein Join. Er fällt auf einer Tabelle mit einigen hundert Zeilen
nicht ins Gewicht, und die Lesewege des Bereichs holen ohnehin ganze
Jahrgänge auf einmal.

Was die alten Spalten angeht: Sie **bleiben**. ``quelle_label``,
``quelle_url`` und ``source_url`` stehen weiter dort, wo sie standen, und
werden weiter aus derselben Angabe gefüllt. Sie zu entfernen hieße, neun
Tabellen neu zu schreiben — darunter vier, deren Inhalt nur über einen
Download von oldenburg.de wiederzubeschaffen wäre. Der Gewinn wäre kosmetisch,
das Risiko echt. ``herkunft_id`` ist ab jetzt der kanonische Weg; die alten
Spalten sind die Rückfallebene, die kein Lesepfad zu ändern zwingt.

Was hier **nicht** hingehört
-----------------------------
Was von Zeile zu Zeile schwankt, bleibt an der Zeile. Die
Prüfungsfeststellungen führen ihre Textziffer und ihre Seite selbst — das ist
ihre Fundstelle, und sie ist je Feststellung eine andere. Die Herkunft
beschreibt das **Dokument und den Abschnitt**, aus dem ein Lauf gelesen hat,
nicht die Zeile darin.

Für einen neuen Parser
-----------------------
Drei Dinge, mehr nicht (ausführlich in ``docs-site/.../haushalt.md``):

1. Eine :class:`Herkunft` bauen — ``art`` und ``probe`` sind Pflicht, alles
   andere so vollständig, wie das Dokument es hergibt.
2. Sie an die ``save_*``-Methode des Stores geben. Die trägt sie ein und
   verknüpft die Zeilen (``store.merke_herkunft``).
3. Die Zieltabelle in :data:`HERKUNFT_TABELLEN` eintragen. Damit bekommt sie
   ihre ``herkunft_id``-Spalte, und ``store.herkunft_luecken()`` meldet ab
   sofort jede Zeile darin, die ohne Herkunft geschrieben wurde.

Vergessen ist damit nicht unmöglich, aber laut: Eine :class:`Herkunft` ohne
Probe lässt sich gar nicht erst bauen (``ValueError``), und eine Tabelle, die
ihre ``herkunft_id`` nicht füllt, steht nach jedem Lauf im Protokoll.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

#: Woher ein Dokument stammt. Absichtlich dieselben Werte wie
#: ``Finanzquelle.herkunft`` in ``council/finanzquellen.py`` — dort steht, ob
#: der Cron eine Schicht selbst nachziehen darf, hier, was ein Leser über die
#: Zahl vor sich wissen muss.
ARTEN: dict[str, str] = {
    "ris": "Anlage zu einer Ratsvorlage im Bürgerinformationssystem",
    "opendata": "Datensatz des Open-Data-Portals der Stadt Oldenburg",
    "stadt": "Veröffentlichung auf oldenburg.de",
}

#: Der ausdrückliche Verzicht. Keine Quelle darf ohne Angabe gespeichert
#: werden — aber manche tragen schlicht keine Rechenprobe, und das zu sagen
#: ist eine Angabe. Die Portal-CSVs sind der Fall: eine Zeile je Jahr, keine
#: Summe, gegen die sich etwas prüfen ließe.
UNGEPRUEFT = "ungeprueft"

#: Der Altbestand. Zeilen, die vor der Vereinheitlichung geschrieben wurden,
#: **sind** durch eine Probe gegangen — welche, steht nicht dabei. Diese
#: Marke sagt genau das, statt eine zu behaupten. Sie ist nichts, was ein
#: Parser je setzen sollte: Sie entsteht ausschließlich beim Nachrüsten
#: (``CouncilStore._migrate_herkunft``) und verschwindet, sobald der Jahrgang
#: das nächste Mal eingelesen wird.
UNBEKANNT = "unbekannt"

#: Die Rechenproben, die der Bereich kennt — Name → was sie zeigt.
#:
#: Der Text ist für Leserinnen geschrieben, nicht für uns: Er landet über die
#: API im Beleg-Chip und beantwortet dort die Frage „warum soll ich das
#: glauben?". Wer eine neue Probe baut, trägt sie hier ein; ein unbekannter
#: Name fliegt beim Bauen der :class:`Herkunft` auf.
PROBEN: dict[str, str] = {
    "summenzeile":
        "Die Teilbeträge ergeben die Summenzeile des Dokuments (Toleranz 1 %).",
    "strukturprobe":
        "Innerhalb der Ergebnisrechnung geht die Rechnung des Dokuments auf: "
        "Erträge (Posten 12) − Aufwendungen (Posten 20) = ordentliches Ergebnis "
        "(Posten 21), in Plan und Ist.",
    "summenprobe":
        "Die Teilhaushalte summieren sich auf die Gesamtrechnung desselben "
        "Dokuments — sonst wäre für einen Teilhaushalt die falsche, in sich "
        "stimmige Tabelle gelesen worden.",
    "vorjahreskette":
        "Das Ergebnis eines Jahres steht im Jahresabschluss des Folgejahres "
        "noch einmal als Vorjahreswert und stimmt damit überein.",
    "abweichungstext":
        "Die Erläuterung nennt ihre Abweichung doppelt, als Betrag und als "
        "Prozentsatz; beide passen zu der Tabellenzeile, die derselbe "
        "Jahrgang für diesen Posten führt.",
    "produktzeile":
        "Je Produktzeile: Erträge − Aufwendungen = ordentliches Ergebnis.",
    "legende_und_verzeichnis":
        "Die Randmarke der Feststellung steht in der Legende dieses Berichts, "
        "ihre Textziffer in seinem Inhaltsverzeichnis.",
    "eingangsformel":
        "Der Bericht nennt in seiner Eingangsformel die Kernverwaltung als "
        "geprüfte Stelle — nicht einen Eigenbetrieb oder eine Stiftung.",
    "textextrakt":
        "Der Buchstabenanteil des Volltexts belegt, dass das PDF eine "
        "Zeichenzuordnung mitbringt und kein Glyphen-Salat ist.",
    # Konzern Stadt Oldenburg (council/konzernabschluss.py). Die ersten drei
    # stehen im Gesamtabschluss nebeneinander und sichern ihn gemeinsam ab:
    # Erst wenn alle drei aufgehen, kommt ein Jahrgang herein.
    "konzern_ergebnisprobe":
        "In der Ergebnisrechnung des Konzerns geht die Rechnung des Dokuments "
        "auf: Summe der ordentlichen Erträge − Summe der ordentlichen "
        "Aufwendungen = ordentliches Ergebnis.",
    "konzern_ausserordentlich":
        "Dasselbe für die einmaligen Posten: außerordentliche Erträge − "
        "außerordentliche Aufwendungen = außerordentliches Ergebnis.",
    "konzern_gesamtergebnis":
        "Beide Teile zusammen ergeben das ausgewiesene Gesamtjahresergebnis — "
        "die Tabelle ist also von oben bis unten in sich stimmig.",
    "konzern_traegersumme":
        "Die einbezogenen Betriebe und Gesellschaften ergeben zusammen mit der "
        "Verrechnung untereinander genau die Summe, die der Bericht ausweist.",
    "konzern_querprobe":
        "Dieselbe Summe steht an zwei Stellen des Berichts — in der "
        "Ergebnisrechnung des Konzerns und in der Aufstellung, wer wie viel "
        "beiträgt. Beide stimmen überein.",
    "konzern_zeilenprobe":
        "Je Betrieb nennt der Bericht Jahr, Vorjahr und Veränderung; die "
        "Veränderung ist die Differenz der beiden anderen.",
    UNGEPRUEFT:
        "Diese Quelle trägt keine Rechenprobe: Sie liefert eine Zeile je Jahr "
        "ohne Summe, gegen die sich etwas prüfen ließe. Übernommen wie "
        "veröffentlicht.",
    UNBEKANNT:
        "Aus dem Bestand vor der Herkunfts-Vereinheitlichung übernommen. Die "
        "Zeilen haben eine Probe bestanden — welche, hielt der alte Bestand "
        "nicht fest. Der nächste Einlese-Lauf trägt es nach.",
}

#: Jede Tabelle, deren Zeilen eine ``herkunft_id`` tragen.
#:
#: Diese Liste ist die Arbeitsanweisung an drei Stellen: Sie legt die Spalte
#: an (``CouncilStore._migrate_herkunft``), sie füllt sie beim Nachrüsten aus
#: den alten Feldern, und sie ist der Prüfumfang von
#: ``CouncilStore.herkunft_luecken()``. Wer eine Tabelle hier vergisst,
#: bekommt keine Spalte; wer sie einträgt und nicht füllt, bekommt eine
#: Meldung nach jedem Lauf.
HERKUNFT_TABELLEN: tuple[str, ...] = (
    "council_haushalt",
    "council_steuern",
    "council_steuerkraft",
    "council_einwohner",
    "council_ergebnisrechnung",
    "council_abweichungsgruende",
    "council_pruefbericht_quellen",
    "council_produkte",
    "council_pruefberichte",
    # Beide neu mit dem Konzern-Bereich und ohne Altbestand: Sie führen ihre
    # Herkunft ausschließlich über `herkunft_id`, tragen also keine
    # `quelle_label`/`quelle_url`-Spalten mehr, aus denen etwas nachzutragen
    # wäre (s. `CouncilStore._HERKUNFT_ALTFELDER`).
    "council_konzern_posten",
    "council_konzern_traeger",
)


def _proben_normalisieren(roh: str | Sequence[str]) -> str:
    """Ein oder mehrere Probennamen → ein kanonischer, geprüfter String.

    Mehrere sind der Normalfall und nicht die Ausnahme: Die Gesamtrechnung
    eines Jahresabschlusses besteht die Strukturprobe **und** hängt in der
    Vorjahres-Kette. Beides zu nennen ist ehrlicher, als sich für eine zu
    entscheiden."""
    namen = [roh] if isinstance(roh, str) else list(roh)
    namen = [n.strip() for n in namen if n and n.strip()]
    if not namen:
        raise ValueError(
            "Herkunft ohne Probe. Womit ist die Zahl abgesichert? Trägt die "
            "Quelle keine Rechenprobe, ist das ausdrücklich zu sagen: "
            "probe=herkunft.UNGEPRUEFT.")
    for n in namen:
        if n not in PROBEN:
            raise ValueError(
                f"Unbekannte Probe {n!r}. Bekannt sind: {', '.join(sorted(PROBEN))}. "
                "Eine neue Probe gehört mit einem Satz für Leserinnen nach "
                "council/herkunft.py:PROBEN.")
    for allein in (UNGEPRUEFT, UNBEKANNT):
        if allein in namen and len(namen) > 1:
            raise ValueError(
                f"{allein!r} neben einer benannten Probe ist ein Widerspruch — "
                "entweder ist die Probe bekannt oder nicht.")
    # Reihenfolge des Aufrufers bleibt (sie erzählt, was zuerst greift),
    # Doppelnennungen fallen weg.
    gesehen: list[str] = []
    for n in namen:
        if n not in gesehen:
            gesehen.append(n)
    return ",".join(gesehen)


@dataclass(frozen=True)
class Herkunft:
    """Woher **ein Lauf** seine Zeilen genommen hat.

    Pflicht sind ``art`` und ``probe`` — ohne sie lässt sich der Datensatz
    nicht bauen. Dazu muss mindestens einer der beiden Verweise stehen:
    ``dokument_id`` (der stabile Anker) oder ``url``. Eine Herkunft, die auf
    nichts zeigt, wäre eine Behauptung.

    ``fundstelle`` bleibt leer, solange ein Parser sie nicht kennt — leer ist
    hier ehrlicher als geraten. Sie wird nachgerüstet, wo sie bekannt ist.
    """

    #: Schlüssel aus :data:`ARTEN`.
    art: str
    #: Name(n) aus :data:`PROBEN`, oder :data:`UNGEPRUEFT`.
    probe: str | Sequence[str]
    #: ``council_anlagen.document_id`` — überlebt Label- und URL-Wechsel.
    #: Der Gesamtabschluss 2016 heißt im Bürgerinfo schlicht „Anlage"; wer
    #: über das Label ankert, verliert ihn beim nächsten Umbenennen.
    dokument_id: int | None = None
    #: Wie das Dokument heißt — für Menschen, nicht als Schlüssel.
    label: str | None = None
    url: str | None = None
    #: Wo im Dokument: „Abschnitt 6.3.1", „Übersicht Ergebnishaushalt",
    #: „Datensatz 1104". Bei 300 Seiten ist die URL allein zu wenig.
    fundstelle: str | None = None
    #: Seitenzahl, falls das Dokument eine trägt — macht aus dem Link einen
    #: Sprung (``…pdf#page=161``).
    seite: int | None = None
    #: Der Messwert der Probe, wo sie einen liefert: „0,02 % Abweichung".
    #: Belegt, dass sie wirklich lief und nicht nur behauptet wird.
    probe_ergebnis: str | None = None
    #: Stichtag/Datenstand des Inhalts — nicht der Abrufzeitpunkt. Bei den
    #: Beteiligungen der Punkt, an dem sich Konzern- und Einzelabschluss
    #: unterscheiden.
    stand: str | None = None

    def __post_init__(self) -> None:
        if self.art not in ARTEN:
            raise ValueError(
                f"Unbekannte Quellenart {self.art!r}. Bekannt sind: "
                f"{', '.join(sorted(ARTEN))}.")
        # Der Aufrufer darf einen Namen oder eine Liste übergeben; gespeichert
        # wird immer die kanonische, geprüfte Fassung.
        object.__setattr__(self, "probe", _proben_normalisieren(self.probe))
        if self.dokument_id is None and not self.url:
            raise ValueError(
                "Herkunft ohne Verweis: mindestens dokument_id (der stabile "
                "Anker aus council_anlagen) oder url muss stehen.")

    @property
    def proben(self) -> list[str]:
        """Die Probennamen einzeln."""
        return [n for n in str(self.probe).split(",") if n]

    @property
    def geprueft(self) -> bool:
        """Trägt diese Quelle überhaupt eine Rechenprobe?

        ``UNBEKANNT`` gilt als geprüft: Diese Zeilen **haben** eine Probe
        bestanden, nur ist nicht festgehalten, welche. Nur ``UNGEPRUEFT``
        heißt, dass es keine gab."""
        return self.proben != [UNGEPRUEFT]

    def felder(self) -> dict:
        """Die Spaltenwerte für ``council_herkunft`` (ohne ``fetched_at``)."""
        return {"art": self.art, "dokument_id": self.dokument_id,
                "label": self.label, "url": self.url,
                "fundstelle": self.fundstelle, "seite": self.seite,
                "probe": str(self.probe), "probe_ergebnis": self.probe_ergebnis,
                "stand": self.stand}

    def schluessel(self) -> str:
        """Inhaltlicher Fingerabdruck — macht das Eintragen idempotent.

        Bewusst **ohne** ``fetched_at``: Wann wir zuletzt nachgesehen haben,
        ändert nicht, woher die Zahl kommt. Läge der Zeitpunkt im Schlüssel,
        legte jeder Lauf einen neuen Datensatz an und die Tabelle wüchse mit
        der Zahl der Läufe statt mit der Zahl der Quellen.

        Ein Hash statt eines UNIQUE-Index über die neun Spalten, weil SQLite
        ``NULL`` in einem UNIQUE-Index nicht als gleich behandelt: Zwei
        Herkünfte ohne Seitenzahl wären dort verschieden und lägen doppelt."""
        roh = json.dumps(self.felder(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def probe_texte(probe: str | None) -> list[str]:
    """Die Erklärsätze zu einer gespeicherten Probenliste — für die API.

    Unbekannte Namen (eine Probe, die es einmal gab und heute nicht mehr)
    fallen still weg: Die Oberfläche soll den Beleg zeigen können, auch wenn
    ein alter Bestand einen Namen trägt, den der Code nicht mehr kennt."""
    return [PROBEN[n] for n in (probe or "").split(",") if n in PROBEN]
