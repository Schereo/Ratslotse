"""Woher die Finanzzahlen des Haushalts-Bereichs stammen — eine Definition je
Datenart, und das Einlesen dazu.

Neun Schichten tragen den Bereich. Sechs davon hängen als **Anlagen** an
Ratsvorlagen und liegen mit Volltext in ``council_anlagen``; woran man sie
dort erkennt (Label-Muster, Mindestseitenzahl, Ausschlüsse), stand bis 08/2026
verstreut in zwei Ingest-Skripten. Hier steht es einmal. ``ingest_finanz-
berichte.py``, ``ingest_pruefberichte.py`` und der Cron ``check_finanzdaten.py``
lesen dieselbe Definition — auf die Frage „ist das ein Jahresabschluss?" gibt
es sonst zwei Antworten, und eine davon veraltet still.

Der Takt der Stadt, gemessen an acht Jahrgängen Sitzungsdaten:

=================================================  ==================
Was                                                Wann im Rat
=================================================  ==================
Jahresabschluss + Schlussbericht des RPA           Anfang September
Haushaltsplan: Gesamtergebnishaushalt + Teil-      Anfang Oktober
haushalte
=================================================  ==================

Die drei übrigen kommen **nicht** aus dem Ratsinformationssystem: der
Haushaltsplan als Download von oldenburg.de, der Städtevergleich in zwei
Reihen vom Landesamt für Statistik Niedersachsen. Deren Takt ist an den
Dokumenten selbst gemessen, nicht geschätzt (16.08.2026):

===========================================  ===========================
Was                                          Wann veröffentlicht
===========================================  ===========================
Kommunaler Finanzausgleich, **endgültig**    März/April des Ausgleichs-
(Blatt ``ST_KR_MESS_VGL``)                   jahres — Stand der Dateien:
                                             25.04.2023, 02.04.2024,
                                             25.03.2025, 26.03.2026
Realsteuervergleich                          im Folgejahr des Berichts-
(Statistischer Bericht L II 7 / L II 9)      jahres, zuletzt Juni 2022,
                                             August 2023, November 2024,
                                             November 2025, Juli 2026
===========================================  ===========================

Beim Finanzausgleich zählt ausdrücklich die **endgültige** Fassung: Die
vorläufige erscheint zwar schon im November davor (19.11.2025 für 2026),
enthält aber gar kein Blatt ``ST_KR_MESS_VGL`` — nachgesehen in den Dateien
beider Jahrgänge. Sie kann diese Schicht also nicht füllen.

Der Cron rechnet damit **nicht**. Er fragt den Bestand, nicht den Kalender:
„Welche Einheit fehlt mir, und liegt inzwischen ein Dokument dafür vor?"
Ein Job, der im September nach dem Jahresabschluss sucht, bricht in dem Jahr,
in dem die Stadt später dran ist. ``erwarteter_monat`` dient deshalb einem
einzigen Zweck: zu sagen, ab wann ein fehlender Jahrgang eine **Meldung** wert
ist — nicht, wann gesucht wird.

Buchgeführt wird über **Einheiten**, nicht über Jahrgänge — was eine Einheit
ist und warum das der Unterschied zwischen „läuft" und „veraltet still" ist,
steht bei :class:`Finanzquelle`.

.. warning::
   ``council_anlagen.fetched_at`` taugt nicht als Veröffentlichungsdatum: Bei
   allen Finanzdokumenten steht dort der 10.08.2026, der Tag des Volltext-
   Backfills. Der Jahrgang kommt deshalb aus dem Dokument selbst.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from council import (ergebnishaushalt, finanzberichte, herkunft, konzernabschluss,
                     pruefberichte)
from council.store import CouncilStore

#: Wie lange nach dem erwarteten Monat ein fehlender Jahrgang als „die Stadt
#: ist eben spät dran" durchgeht. Danach ist er eine Meldung wert — nicht als
#: Fehler, sondern als Frage: Ist die Stadt spät, oder greift ein Muster nicht
#: mehr? Vier Wochen, weil die Einbringung in acht Jahren zweimal um einen
#: Monat verrutscht ist (Jahresabschluss einmal August, Plan einmal November).
KARENZ = timedelta(weeks=4)


class Protokoll:
    """Wohin ein Ingest-Lauf spricht.

    Die Ingest-Skripte schreiben nach stdout/stderr wie eh und je, der Cron
    sammelt dieselben Zeilen ein und hängt sie an seine Meldung. Ohne diese
    Umleitung müsste der Cron das Einlesen nachbauen — und hätte damit einen
    zweiten Satz Prüfungen, der irgendwann vom ersten abweicht.
    """

    def __init__(self, still: bool = False) -> None:
        self.still = still
        self.zeilen: list[str] = []
        self.warnungen: list[str] = []

    def sagen(self, text: str) -> None:
        self.zeilen.append(text)
        if not self.still:
            print(text)

    def warnen(self, text: str) -> None:
        """Etwas ist nicht in die Datenbank gekommen. Immer mit Grund."""
        self.warnungen.append(text)
        self.zeilen.append(text)
        if not self.still:
            print(text, file=sys.stderr)


@dataclass(frozen=True)
class Erkennung:
    """Wie eine Datenart ihre Dokumente in ``council_anlagen`` findet.

    Bewusst grob: Der SQL-Filter soll nur verhindern, dass der Parser den
    ganzen Anlagenbestand durchkaut. Entschieden wird am Dokument selbst
    (``jahrgang``) — bei den Prüfberichten sogar ausschließlich dort, weil die
    Labels zwischen Kernverwaltung, Eigenbetrieb und vier Stiftungen nicht
    unterscheiden.
    """

    #: SQL-LIKE-Muster auf ``label``.
    label_muster: tuple[str, ...] = ()
    #: SQL-LIKE-Muster auf ``raw_text``.
    text_muster: tuple[str, ...] = ()
    #: Muster mit ODER statt UND verknüpfen (nur die Schlussbericht-Fundstelle).
    oder: bool = False
    #: ``n_pages`` muss größer sein — hält Deckblätter und Auszüge draußen.
    mindest_seiten: int = 0
    #: Label-Muster, die ein Dokument ausschließen.
    ausschluesse: tuple[str, ...] = ()
    #: ORDER BY der Kandidatenabfrage.
    ordnung: str = "label"

    def where(self) -> tuple[str, list]:
        """WHERE-Klausel und Parameter — eine Quelle für Skript und Cron."""
        teile: list[str] = []
        werte: list = []
        for m in self.label_muster:
            teile.append("label LIKE ?")
            werte.append(m)
        for m in self.text_muster:
            teile.append("raw_text LIKE ?")
            werte.append(m)
        wo = [f"({(' OR ' if self.oder else ' AND ').join(teile)})"] if teile else []
        if self.mindest_seiten:
            wo.append("n_pages > ?")
            werte.append(self.mindest_seiten)
        for m in self.ausschluesse:
            wo.append("label NOT LIKE ?")
            werte.append(m)
        return " AND ".join(wo) or "1", werte

    def abfrage(self, spalten: str) -> tuple[str, list]:
        wo, werte = self.where()
        return (f"SELECT {spalten} FROM council_anlagen WHERE {wo} "
                f"ORDER BY {self.ordnung}"), werte


@dataclass(frozen=True)
class Finanzquelle:
    """Eine Datenart: woran man sie erkennt, was sie füllt, wann sie kommt.

    Buchgeführt wird über **Einheiten**, nicht über Jahrgänge. Eine Einheit ist
    das, was **ein** Dokument liefert — und das ist bei zwei der fünf Schichten
    kleiner als ein Jahrgang:

    - Ein Produkt-Jahrgang verteilt sich auf rund neun Teilhaushalts-Anlagen
      (``council/store.py`` sagt es bei ``save_produkte`` selbst: „Die Produkte
      eines Jahres verteilen sich auf mehrere Teilhaushalts-Dokumente, die
      nacheinander eingelesen werden").
    - Ein Jahresabschluss trägt zwei Ebenen: die Gesamtrechnung und die
      Teil-Ergebnisrechnungen. Die Summenprobe kann die zweite verwerfen,
      während die erste steht.

    Wer je Jahrgang buchführt, hält beides für erledigt, sobald das erste
    Stück drin ist — und zieht den Rest nie nach. Genau so ist es im Betrieb
    zu erwarten: Teilhaushalts-Anlagen kommen über ``check_protocols`` ohne
    Volltext herein, den holt ``backfill_anlagen_texte.py`` erst später und
    tranchenweise. Zwischen zwei Läufen liegt also regelmäßig ein Jahrgang,
    von dem die Hälfte lesbar ist.

    Eine Einheit ist ein Tupel, dessen **erstes** Element immer der Jahrgang
    ist (``(2024, 7)`` für Teilhaushalt 7, ``(2024, "gesamt")`` für die
    Gesamtrechnung, ``(2024,)`` wo ein Dokument den ganzen Jahrgang trägt).
    """

    key: str
    #: Überschrift für Menschen — steht so im Datenstand auf ``/haushalt``.
    label: str
    #: Ein Satz für Leserinnen, was diese Schicht beantwortet.
    was: str
    #: Zieltabelle (bei mehreren die führende — sie entscheidet den Bestand).
    tabelle: str
    #: In welchem Monat das Dokument üblicherweise vorliegt (1–12) — bei den
    #: Rats-Schichten der Monat der Einbringung, bei der Landesstatistik der
    #: der Veröffentlichung.
    erwarteter_monat: int
    #: Kalenderjahr, in dem das passiert = Jahrgang + ``versatz``.
    versatz: int
    #: Wo das Dokument herkommt: ``ris`` = Anlage im Ratsinformationssystem
    #: (der Cron liest sie aus), ``stadt`` = Download von oldenburg.de,
    #: ``lsn`` = Tabelle des Landesamts für Statistik Niedersachsen (bei
    #: beiden lädt der Cron bewusst nichts herunter, s. Modul-Kopf von
    #: check_finanzdaten).
    herkunft: str
    #: Welche **Einheiten** schon im Bestand stehen (Menge von Tupeln).
    bestand: Callable[[CouncilStore], set[tuple]]
    #: Wie eine Einheit für Leserinnen heißt — ``None``, wo ein Dokument den
    #: ganzen Jahrgang trägt und „vollständig" keine Frage ist.
    einheit: str | None = None
    erkennung: Erkennung | None = None
    #: Welche Einheiten ein Kandidat füllen könnte — aus Label bzw. Textkopf,
    #: nie aus ``fetched_at``.
    einheiten_von: Callable[[dict], set[tuple]] | None = None
    #: Einlesen: ``(store, protokoll, nur_fehlende, schuetzen) -> dict``.
    einlesen: Callable[..., dict] | None = None
    #: Weitere Tabellen, die derselbe Lauf mitfüllt.
    nebentabellen: tuple[str, ...] = ()
    #: Was ein Mensch tut, wenn diese Schicht ausbleibt — Quelle und Skript im
    #: Klartext. Nur bei ``automatisch is False`` gesetzt; der Cron schreibt es
    #: in seine Meldung. Dort stand es bis 08/2026 fest verdrahtet als
    #: „Download von oldenburg.de, scripts/ingest_haushalt.py" und wurde mit
    #: der ersten Schicht einer anderen Stelle still falsch.
    nachschub: str | None = None

    @property
    def automatisch(self) -> bool:
        """Kann der Cron diese Schicht allein nachziehen?"""
        return self.einlesen is not None

    def faellig_ab(self, jahrgang: int) -> date:
        """Wann dieser Jahrgang üblicherweise im Rat liegt."""
        return date(jahrgang + self.versatz, self.erwarteter_monat, 1)

    def neuester_erwarteter(self, heute: date) -> int:
        """Der jüngste Jahrgang, der heute schon vorliegen müsste."""
        jahrgang = heute.year - self.versatz
        if heute < self.faellig_ab(jahrgang):
            jahrgang -= 1
        return jahrgang

    def kandidaten(self, store: CouncilStore, kopf_zeichen: int = 4000) -> list[dict]:
        """Anlagen, die ein Dokument dieser Datenart sein könnten — mit den
        Einheiten, die sie füllen könnten, aber **ohne** Volltext.

        ``raw_text`` wird auf den Kopf beschnitten: Ein Jahresabschluss bringt
        400.000 Zeichen mit, und für die Frage „welche Einheit ist das?"
        reichen die ersten Zeilen. Wer wirklich einliest, holt sich die Zeile
        noch einmal ganz (das tun die ``lies_*``-Funktionen unten)."""
        if self.erkennung is None:
            return []
        sql, werte = self.erkennung.abfrage(
            f"document_id, label, url, n_pages, substr(raw_text, 1, {int(kopf_zeichen)}) AS kopf")
        rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
        for r in rows:
            r["einheiten"] = self.einheiten_von(r) if self.einheiten_von else set()
            r["jahrgang"] = next(iter(sorted(e[0] for e in r["einheiten"])), None)
        return rows

    def offene_einheiten(self, store: CouncilStore) -> set[tuple]:
        """Einheiten, für die ein Dokument vorliegt, die aber fehlen."""
        vorhanden = self.bestand(store)
        moeglich: set[tuple] = set()
        for r in self.kandidaten(store):
            moeglich |= r["einheiten"]
        return moeglich - vorhanden


def jahrgaenge(einheiten: set[tuple]) -> list[int]:
    """Die Jahrgänge einer Einheitenmenge, aufsteigend."""
    return sorted({e[0] for e in einheiten})


# --- Welche Einheiten ein Kandidat füllen könnte ----------------------------

def _jahr_aus_label(row: dict) -> int | None:
    m = re.search(r"(20\d\d)", row.get("label") or "")
    return int(m.group(1)) if m else None


#: Die zwei Ebenen eines Jahresabschlusses. Die Erläuterungen aus Abschnitt
#: 6.3.1 sind bewusst **keine** dritte Einheit: Ob ein Jahrgang welche hat,
#: entscheidet der Bericht (und die Rechenprobe), nicht wir — als Einheit
#: geführt gälte jeder Jahrgang ohne Erläuterungen für immer als unvollständig
#: und würde alle zwei Wochen neu geparst. Sie werden trotzdem nachgetragen,
#: sobald der Jahrgang aus einem anderen Grund noch einmal gelesen wird.
EBENEN = ("gesamt", "teilhaushalte")


def _einheiten_jahresabschluss(row: dict) -> set[tuple]:
    jahr = _jahr_aus_label(row)
    return {(jahr, e) for e in EBENEN} if jahr else set()


def _einheiten_schlussbericht(row: dict) -> set[tuple]:
    treffer = finanzberichte.pruefbericht_aus_anlage(row.get("label"), row.get("kopf"))
    return {(treffer["jahr"],)} if treffer else set()


def _einheiten_feststellungen(row: dict) -> set[tuple]:
    jahr = pruefberichte.erkenne_jahrgang(row.get("kopf") or "")
    return {(jahr,)} if jahr else set()


#: Erste Ansatzspalte im Tabellenkopf eines Teilhaushalts-Plans.
_ANSATZ = re.compile(r"Ansatz\s+(20\d\d)")

#: Nummer des Teilhaushalts aus dem Label — „007 THH01", „2024 007 IVw THH01",
#: „TOP 5 - Anlage III - THH 08". Führende Nullen und der Zwischenraum
#: schwanken zwischen den Jahrgängen.
_LABEL_THH = re.compile(r"THH\s*0*(\d+)")


def teilhaushalt_nummer(label: str | None) -> int | None:
    """Welchen Teilhaushalt ein Plan-Dokument abdeckt.

    Zusammen mit ``teilhaushalt_jahrgang`` ist das der Schlüssel, unter dem
    dieses Dokument im Bestand steht — geprüft gegen alle 79 Teilhaushalts-
    Anlagen: Label-Nummer und Textkopf-Jahrgang treffen genau das Paar, das
    ``parse_teilergebnishaushalt`` am Ende vergibt (Test in
    ``tests/test_finanzquellen.py``)."""
    m = _LABEL_THH.search(label or "")
    return int(m.group(1)) if m else None


def teilhaushalt_jahrgang(text: str | None) -> int | None:
    """Für welchen Jahrgang ein Teilhaushalts-Plan Ansätze liefert.

    Nicht das Jahr aus dem Dateinamen: Der Plan „2024 007 IVw THH01" ist der
    Haushaltsplan **2024**, seine erste Ansatzspalte trägt aber 2023 — genau
    den Wert, den ``parse_teilergebnishaushalt`` übernimmt (die späteren
    Spalten sind mittelfristige Finanzplanung, keine beschlossenen Ansätze).
    Wer hier das Label läse, suchte einen Jahrgang, den die Tabelle nie
    zurückgibt, und der Cron liefe in eine Endlosschleife aus Nachladen und
    Nichtfinden.

    Geprüft gegen alle 79 Teilhaushalts-Anlagen des Bestands: Der erste
    ``Ansatz JJJJ`` im Dokumentkopf ist immer der Jahrgang, den der Parser am
    Ende vergibt (siehe ``tests/test_finanzquellen.py``)."""
    m = _ANSATZ.search(text or "")
    return int(m.group(1)) if m else None


def _einheiten_teilhaushalt(row: dict) -> set[tuple]:
    jahr = teilhaushalt_jahrgang(row.get("kopf"))
    nr = teilhaushalt_nummer(row.get("label"))
    return {(jahr, nr)} if jahr and nr else set()


# --- Was schon im Bestand steht ---------------------------------------------

def _jahre(store: CouncilStore, sql: str) -> list:
    try:
        return store._conn.execute(sql).fetchall()  # noqa: SLF001
    except sqlite3.OperationalError:
        return []


def _bestand_jahresabschluss(store: CouncilStore) -> set[tuple]:
    """Je Jahrgang bis zu zwei Einheiten: Gesamtrechnung und Teilhaushalte.

    ``ergebnisrechnung_jahre()`` genügt hier **nicht** — es liefert „irgendeine
    Zeile" und hielte einen Jahrgang, dessen Teilhaushalts-Ebene an der
    Summenprobe gescheitert ist, für fertig."""
    aus = {(r[0], "gesamt") for r in _jahre(
        store, "SELECT DISTINCT jahr FROM council_ergebnisrechnung WHERE thh_nr IS NULL")}
    aus |= {(r[0], "teilhaushalte") for r in _jahre(
        store, "SELECT DISTINCT jahr FROM council_ergebnisrechnung WHERE thh_nr IS NOT NULL")}
    return aus


def _bestand_produkte(store: CouncilStore) -> set[tuple]:
    """Je Jahrgang eine Einheit **pro Teilhaushalt** — die Granularität, in der
    die Dokumente hereinkommen."""
    return {(r[0], r[1]) for r in _jahre(
        store, "SELECT DISTINCT jahr, thh_nr FROM council_produkte WHERE thh_nr IS NOT NULL")}


def _bestand_schlussberichte(store: CouncilStore) -> set[tuple]:
    return {(q["jahr"],) for q in store.get_pruefbericht_quellen()}


def _bestand_feststellungen(store: CouncilStore) -> set[tuple]:
    return {(j,) for j in store.pruefbericht_jahre()}


def _bestand_haushaltsplan(store: CouncilStore) -> set[tuple]:
    return {(j,) for j in store.haushalt_years()}


def _einheiten_ergebnishaushalt(row: dict) -> set[tuple]:
    """Der Jahrgang kommt aus dem **Tabellenkopf**, nicht aus dem Label.

    Vier der acht Dokumente heißen schlicht „005 Gesamtergebnishaushalt" und
    tragen gar keine Jahreszahl; die anderen vier tragen sie, aber an
    verschiedenen Stellen. Der Kopf dagegen sagt es immer und sagt es genau:
    Die dritte Spalte ist das Planjahr (s. ``ergebnishaushalt.jahrgang``)."""
    jahr = ergebnishaushalt.jahrgang(row.get("kopf"))
    return {(jahr,)} if jahr else set()


def _bestand_ergebnishaushalt(store: CouncilStore) -> set[tuple]:
    """Ein Dokument trägt einen ganzen Plan-Jahrgang — Einheit = Jahrgang.

    Gezählt wird nach ``plan_jahrgang``, nicht nach ``jahr``: Sonst hielte ein
    Finanzplanungsjahr, das ein älterer Plan nebenbei mitliefert, den
    zugehörigen Haushalt für schon eingelesen."""
    return {(j,) for j in store.ergebnishaushalt_jahrgaenge()}


def _bestand_konzernabschluss(store: CouncilStore) -> set[tuple]:
    """Ein Dokument trägt einen ganzen Jahrgang — die Einheit ist der Jahrgang.

    Gemessen wird an den Posten, nicht an der Trägeraufstellung: Die Posten
    sind der Kern (ohne sie kommt der Jahrgang gar nicht herein), die
    Trägeraufstellung kann einzeln an ihrer Probe scheitern, ohne dass der
    Jahrgang deswegen unvollständig wäre — 2018 ist genau dieser Fall."""
    return {(j,) for j in store.konzern_jahre()}


def _einheiten_konzernabschluss(row: dict) -> set[tuple]:
    jahr = konzernabschluss.jahrgang(row.get("kopf"))
    return {(jahr,)} if jahr else set()


def _bestand_lsn_steuerkraft(store: CouncilStore) -> set[tuple]:
    """Die Ausgleichsjahre, für die eine Steuerkraftmesszahl vorliegt.

    Eine Datei trägt genau **ein** Ausgleichsjahr in den Bestand: Das zweite,
    das sie mitführt, ist die Rechenprobe (``probe_ueberlappung``) und wird
    nicht gespeichert. Die Einheit ist deshalb der Jahrgang, und „da" heißt
    hier tatsächlich „fertig"."""
    return {(r[0],) for r in _jahre(
        store, "SELECT DISTINCT jahr FROM council_staedtevergleich "
               "WHERE reihe = 'steuerkraft'")}


def _bestand_lsn_realsteuern(store: CouncilStore) -> set[tuple]:
    """Die Berichtsjahre des Realsteuervergleichs.

    Ein Bericht füllt **drei** Jahrgänge: Hebesätze und Ist-Aufkommen für sein
    Berichtsjahr, die Steuereinnahmekraft für dieses und die zwei davor
    (``zeilen_realsteuern`` sagt es selbst: „Jeder Jahreswert trägt SEIN
    Jahr"). Gezählt wird trotzdem je Jahr und nicht je Bericht — die Frage der
    Seite ist „bis wann reichen die Zahlen?", und darauf antwortet das Jahr an
    der Zahl, nicht das Deckblatt, auf dem sie stand."""
    return {(r[0],) for r in _jahre(
        store, "SELECT DISTINCT jahr FROM council_staedtevergleich "
               "WHERE reihe = 'realsteuern'")}


# --- Einlesen ---------------------------------------------------------------
#
# Der Code stand bis 08/2026 in scripts/ingest_finanzberichte.py und
# scripts/ingest_pruefberichte.py. Er ist hierher gewandert, weil der Cron
# ihn Zeile für Zeile mitbenutzt: Jede Probe, die dort einen Jahrgang
# zurückweist, weist ihn auch im automatischen Lauf zurück.
#
# ``nur_fehlende=True`` ist die einzige Zutat des Cron-Betriebs — sie schränkt
# das SPEICHERN auf Jahrgänge ein, die noch nicht in der Tabelle stehen. Der
# Job ergänzt nur, was fehlt; einen verbesserten Parser über den Bestand zu
# ziehen bleibt Sache der Skripte von Hand. Sonst schriebe jeder Lauf alle
# Zeilen neu, und „zweimal laufen tut beim zweiten Mal nichts" wäre gelogen.

#: Steckbrief-Felder, deren Abdeckung ein Lauf ausweist. Die Zahl gehört ins
#: Protokoll, weil sie später auf der Seite steht: „Von 377 Produkten tragen
#: 371 eine Kurzbeschreibung" ist eine Angabe, die stimmen muss.
STECKBRIEF = ("kurzbeschreibung", "auftragsgrundlage", "beeinflussbarkeit",
              "wirkungskreis", "zielgruppe")

#: Die Produkt-Felder, die aus dem Dokument kommen — alles, was
#: ``save_produkte`` aus der gelesenen Zeile schreibt, ohne Herkunft und
#: Zeitstempel. Grundlage von :func:`_produkt_signatur`.
PRODUKT_FELDER = ("produkt_nr", "produkt_name", "thh_nr", "thh_name", "amt",
                  "ertraege", "aufwendungen", "ergebnis",
                  "beeinflussbarkeit_roh") + STECKBRIEF

#: Wie stark ein neu gelesener Jahrgang gegenüber dem gespeicherten Stand
#: schrumpfen darf, bevor der Lauf ihn zurückweist. 20 % Spielraum: Ein
#: Jahrgang kann echt ein paar Zeilen verlieren (ein Posten entfällt, eine
#: Erläuterung weniger), aber nicht ein Viertel.
SCHRUMPF_GRENZE = 0.8


def _anzahl(store: CouncilStore, sql: str, args: tuple) -> int:
    """Zeilenzahl einer Zieltabelle — 0, wenn es die Tabelle noch nicht gibt."""
    try:
        return store._conn.execute(sql, args).fetchone()[0]  # noqa: SLF001
    except sqlite3.OperationalError:
        return 0


def _produkt_signatur(zeilen: list[dict]) -> tuple:
    """Der Inhalt eines Teilhaushalts, unabhängig vom Dokument, aus dem er
    stammt — die Antwort auf „sagen zwei Dokumente dasselbe?".

    Sortiert wird **nur** nach Produktnummer (im Dokument eindeutig), nicht
    über die ganze Zeile: Sonst vergliche die Sortierung irgendwann ``None``
    mit einem Text, und ein leeres Steckbrief-Feld risse einen unbeaufsichtigten
    Lauf mit einem ``TypeError`` ab."""
    return tuple(tuple(z.get(feld) for feld in PRODUKT_FELDER)
                 for z in sorted(zeilen, key=lambda z: z["produkt_nr"]))


def bestandsschutz(p: Protokoll, was: str, alt: int, neu: int,
                   schuetzen: bool = True) -> bool:
    """Darf ein frisch gelesenes Ergebnis einen vorhandenen Stand ersetzen?

    Alle Speicherwege dieser Datei ersetzen einen Jahrgang: Sie löschen ihn und
    schreiben ihn neu. Solange ein Mensch danebensteht, ist das richtig — er
    sieht, was herauskommt. Der Cron läuft alle zwei Wochen unbeaufsichtigt,
    und dann kippt die Rechnung: Ändert die Stadt ihre PDF-Struktur, liefert
    ein Parser irgendwann null oder halb so viele Zeilen. Wer das speichert,
    tauscht einen gefüllten Bestand gegen ein kaputtes Ergebnis — und es fällt
    erst auf, wenn die Seite leer ist.

    Die Regel ist deshalb: **Ein leeres Ergebnis ersetzt nie etwas**, ein
    deutlich kleineres auch nicht (``SCHRUMPF_GRENZE``). Gemeldet wird beides;
    stillschweigend zu schrumpfen wäre der eigentliche Schaden. Das ist die
    Gegenrichtung zu den Pflicht-Proben: Die halten falsche Daten draußen,
    diese Regel hält richtige drin.

    Beinahe-Unfall vom 16.08.2026: Ein Übertragungsskript auf die Dev-VM hätte
    257 Prüfungsfeststellungen gelöscht, weil die Quelltabelle leer war.

    ``schuetzen=False`` ist der **bewusste Handgriff**: Die Ingest-Skripte
    ziehen einen verbesserten Parser über den Bestand, und dabei ist ein
    kleinerer Jahrgang oft genau die Absicht — ein früherer, zu großzügiger
    Lauf hatte mehr Zeilen. Ein Schutz, der das blockiert, macht den einzigen
    Weg unbenutzbar, auf dem sich ein Parser-Fehler je korrigieren ließe.
    Gemeldet wird der Schrumpf trotzdem, deutlich. **Ein leeres Ergebnis
    bleibt auch dann tabu:** Null Zeilen sind nie eine Absicht."""
    if neu <= 0:
        if alt > 0:
            p.warnen(f"    {was}: 0 Zeilen gelesen, {alt} stehen in der Tabelle — "
                     f"Bestand bleibt unangetastet")
        return False
    if alt > 0 and neu < alt * SCHRUMPF_GRENZE:
        if schuetzen:
            p.warnen(f"    {was}: nur {neu} statt bisher {alt} Zeilen "
                     f"({neu / alt * 100:.0f} %) — Bestand bleibt unangetastet")
            return False
        p.warnen(f"    {was}: nur {neu} statt bisher {alt} Zeilen "
                 f"({neu / alt * 100:.0f} %) — wird auf Ansage trotzdem ersetzt")
        return True
    if alt and neu < alt:
        p.sagen(f"    {was}: {neu} Zeilen statt bisher {alt} — ersetzt")
    return True


def lies_jahresabschluesse(store: CouncilStore, p: Protokoll,
                           nur_fehlende: bool = False,
                           schuetzen: bool = True) -> dict:
    """Gesamtdokumente der Jahresabschlüsse — nicht die Rechenschaftsberichte
    und nicht die Prüfberichte, die dieselbe Jahreszahl im Titel tragen.

    Zwei Durchgänge: erst alle Jahrgänge lesen und prüfen, dann speichern.
    Die Vorjahres-Kette lässt sich nur über Dokumentgrenzen hinweg prüfen —
    dafür müssen der Jahrgang und sein Nachbar gelesen vorliegen. Deshalb
    liest auch der Cron-Lauf **alle** Dokumente und speichert nur die neuen:
    Ein neuer Jahrgang ohne seinen Vorgänger hätte keine Kette.

    ``nur_fehlende`` prüft **je Ebene**, nicht je Jahrgang: Ein Jahrgang, dessen
    Teilhaushalts-Ebene an der Summenprobe gescheitert ist, steht mit seiner
    Gesamtrechnung in der Tabelle — „Jahr ist da" hieße hier also „Jahr ist
    fertig", und die zweite Ebene käme nie nach.

    Was ein Jahrgang bekommt, bekommt er in **einer** Transaktion
    (``store.transaktion()``): Ein Abbruch mittendrin ließe ihn sonst halb
    zurück, und halb sieht für den nächsten Lauf aus wie fertig."""
    sql, werte = QUELLEN["jahresabschluss"].erkennung.abfrage(
        "document_id, label, url, raw_text")
    rows = store._conn.execute(sql, werte).fetchall()  # noqa: SLF001
    vorhanden = _bestand_jahresabschluss(store) if nur_fehlende else set()

    gelesen: dict[int, dict] = {}
    uebersprungen = vorzeichen_repariert = 0
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        jahr = int(m.group(1))
        text = r["raw_text"] or ""
        posten = finanzberichte.parse_ergebnisrechnung(text, jahr)
        # Ohne beide Summenzeilen ist der Jahrgang für „Plan gegen Ist" wertlos.
        if {p_["nr"] for p_ in posten} < {12, 20}:
            p.warnen(f"  {jahr}: nur {len(posten)} Posten, keine Summenzeilen — übersprungen")
            uebersprungen += 1
            continue
        # Innerhalb der Tabelle: 12 − 20 = 21, in Plan und Ist.
        ok, warum = finanzberichte.strukturprobe(posten)
        if not ok:
            p.warnen(f"  {jahr}: Strukturprobe gerissen ({warum}) — übersprungen")
            uebersprungen += 1
            continue
        repariert = sum(1 for x in posten if x.get("vorzeichen_repariert"))
        if repariert:
            # Zählen und melden: Wird das häufiger, stimmt etwas anderes nicht.
            p.warnen(f"  {jahr}: {repariert} Zeile(n) mit fehlendem Minuszeichen im Dokument — "
                     f"Betrag passte auf den Cent, Vorzeichen ergänzt")
            vorzeichen_repariert += repariert
        gelesen[jahr] = {"posten": posten, "text": text,
                         "label": r["label"], "url": r["url"],
                         "document_id": r["document_id"]}

    # Vorjahres-Kette: Das Ist eines Jahres steht im Folgejahrgang noch einmal.
    # Ein gerissenes Glied verrät nicht, welche Seite falsch ist — also fallen
    # beide raus. In der Praxis schließen alle Glieder.
    kette = finanzberichte.vorjahreskette({j: v["posten"] for j, v in gelesen.items()})
    verdaechtig: set[int] = set()
    for jahr, folge, warum in kette:
        p.warnen(f"  Vorjahres-Kette {jahr}→{folge} gerissen: {warum} — beide Jahrgänge "
                 f"werden nicht gespeichert")
        verdaechtig |= {jahr, folge}
    glieder = sum(1 for j in gelesen if j + 1 in gelesen) * 2

    neu: list[int] = []
    neue_einheiten: set[tuple] = set()
    mit_thh = verworfen = gruende_gesamt = geschuetzt = 0
    for jahr in sorted(gelesen):
        if jahr in verdaechtig:
            uebersprungen += 1
            continue
        braucht_gesamt = (jahr, "gesamt") not in vorhanden
        braucht_thh = (jahr, "teilhaushalte") not in vorhanden
        if not (braucht_gesamt or braucht_thh):
            continue  # beide Ebenen stehen — der Job fasst Bestand nicht an
        v = gelesen[jahr]
        posten, label, url = v["posten"], v["label"], v["url"]

        # Woher diese Zeilen kommen — je Ebene eine eigene Angabe. Beide
        # stehen im selben Dokument, aber an verschiedenen Stellen und hinter
        # verschiedenen Proben; eine gemeinsame Herkunft wäre für beide
        # ungenau. Die Vorjahres-Kette wird nur genannt, wo sie greift: Ohne
        # gelesenen Nachbarjahrgang gibt es kein Glied, das schließen könnte.
        anker = dict(art="ris", dokument_id=v["document_id"], label=label,
                     url=url, stand=f"Jahresabschluss {jahr}")
        proben_gesamt = ["strukturprobe"]
        if jahr - 1 in gelesen or jahr + 1 in gelesen:
            proben_gesamt.append("vorjahreskette")

        # Ein Jahrgang, eine Transaktion: Gesamtrechnung, Teilhaushalte und
        # Erläuterungen stehen zusammen in der Datenbank oder gar nicht.
        with store.transaktion():
            if braucht_gesamt:
                # Ersetzen heißt löschen und neu schreiben — nur gegen ein
                # Ergebnis, das den vorhandenen Stand trägt (s. bestandsschutz).
                alt = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnisrechnung "
                                     "WHERE jahr = ? AND thh_nr IS NULL", (jahr,))
                if not bestandsschutz(p, f"{jahr} Ergebnisrechnung", alt,
                                      len(posten), schuetzen):
                    geschuetzt += 1
                    uebersprungen += 1
                    continue
                store.save_ergebnisrechnung(jahr, posten, herkunft.Herkunft(
                    probe=proben_gesamt,
                    fundstelle="Ergebnisrechnung der Kernverwaltung, Posten 1–24",
                    **anker))
                neue_einheiten.add((jahr, "gesamt"))
                e = next(x for x in posten if x["nr"] == 12)
                a = next(x for x in posten if x["nr"] == 20)
                arten = sorted({x["plan_art"] for x in posten})
                p.sagen(f"  {jahr}: {len(posten)} Posten · Erträge {e['plan']/1e6:.1f} → "
                        f"{e['ergebnis']/1e6:.1f} · Aufwendungen {a['plan']/1e6:.1f} → "
                        f"{a['ergebnis']/1e6:.1f} · Bezug {'/'.join(arten)}")
                if a["plan"] != a["ansatz"] or e["plan"] != e["ansatz"]:
                    p.sagen(f"      ursprünglicher Ansatz: Erträge {e['ansatz']/1e6:.1f} · "
                            f"Aufwendungen {a['ansatz']/1e6:.1f}")
            else:
                p.sagen(f"  {jahr}: Gesamtrechnung steht bereits — nur die fehlende "
                        f"Teilhaushalts-Ebene wird nachgezogen")

            # Zweite Ebene: dieselbe Rechnung je Teilhaushalt. Sie wird nur
            # übernommen, wenn ihre Summe zur Gesamtrechnung passt — in Plan
            # UND Ist. Sonst wurde für einen Teilhaushalt die falsche (in sich
            # stimmige) Tabelle gelesen, was zeilenweise nicht auffällt.
            if braucht_thh:
                thh = finanzberichte.parse_teilergebnisrechnungen(v["text"], jahr)
                alt_thh = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnisrechnung "
                                         "WHERE jahr = ? AND thh_nr IS NOT NULL", (jahr,))
                if not bestandsschutz(p, f"{jahr} Teilhaushalte", alt_thh,
                                      sum(len(x["posten"]) for x in thh), schuetzen):
                    geschuetzt += 1 if alt_thh else 0
                else:
                    passt, abweichung = finanzberichte.summenprobe(thh, posten)
                    if not passt:
                        p.warnen(f"    Teilhaushalte verworfen: Summe weicht um "
                                 f"{abweichung*100:.1f} % von der Gesamtrechnung ab")
                        verworfen += 1
                    else:
                        for x in thh:
                            store.save_ergebnisrechnung(
                                jahr, x["posten"], herkunft.Herkunft(
                                    probe="summenprobe",
                                    fundstelle=f"Teil-Ergebnisrechnung THH"
                                               f"{x['thh_nr']:02d} — {x['thh_name']}",
                                    probe_ergebnis=f"{abweichung * 100:.2f} % "
                                                   f"Abweichung zur Gesamtrechnung",
                                    **anker),
                                thh_nr=x["thh_nr"], thh_name=x["thh_name"])
                        p.sagen(f"    + {len(thh)} Teilhaushalte "
                                f"(Summenprobe {abweichung*100:.2f} % Abweichung)")
                        neue_einheiten.add((jahr, "teilhaushalte"))
                        mit_thh += 1

            # Das „Warum": Abschnitt 6.3.1 je Posten. Eintrittskarte ist der
            # Abgleich mit der Tabellenzeile — Betrag und Prozentsatz stehen in
            # der Überschrift des Blocks und müssen beide passen.
            #
            # Keine eigene Einheit (s. EBENEN), aber sie reiten mit: Wird ein
            # Jahrgang aus einem anderen Grund noch einmal gelesen, kommen die
            # Erläuterungen nach, falls sie fehlen.
            alt_gruende = _anzahl(store, "SELECT COUNT(*) FROM council_abweichungsgruende "
                                         "WHERE jahr = ?", (jahr,))
            if braucht_gesamt or not alt_gruende:
                roh = finanzberichte.parse_abweichungsgruende(v["text"], jahr)
                angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(roh, posten)
                for grund in abgelehnt:
                    p.warnen(f"    Erläuterung verworfen — {grund}")
                if bestandsschutz(p, f"{jahr} Erläuterungen", alt_gruende,
                                  len(angenommen), schuetzen):
                    store.save_abweichungsgruende(jahr, angenommen, herkunft.Herkunft(
                        probe="abweichungstext",
                        fundstelle="Abschnitt 6.3.1 — Erläuterungen zu den "
                                   "Abweichungen gegenüber dem Plan",
                        probe_ergebnis=f"{len(angenommen)} von {len(roh)} "
                                       f"Erläuterungen bestanden",
                        **anker))
                    gruende_gesamt += len(angenommen)
                    p.sagen(f"    + {len(angenommen)} Erläuterungen zu Abweichungen")
                elif alt_gruende:
                    geschuetzt += 1
        if (jahr, "gesamt") in neue_einheiten or (jahr, "teilhaushalte") in neue_einheiten:
            neu.append(jahr)

    return {"neue_jahrgaenge": sorted(set(neu)),
            "neue_einheiten": sorted(neue_einheiten, key=repr),
            "jahre": len(gelesen) - len(verdaechtig), "uebersprungen": uebersprungen,
            "jahre_mit_teilhaushalten": mit_thh, "thh_verworfen": verworfen,
            "kettenglieder_geprueft": glieder, "kette_gerissen": len(kette),
            "vorzeichen_repariert": vorzeichen_repariert,
            "bestand_geschuetzt": geschuetzt,
            "abweichungsgruende": gruende_gesamt}


def lies_ergebnishaushalte(store: CouncilStore, p: Protokoll,
                           nur_fehlende: bool = False,
                           schuetzen: bool = True) -> dict:
    """Die Planjahre aus dem Gesamtergebnishaushalt der Haushaltspläne.

    Die einzige Schicht, die etwas über **Jahre ohne Jahresabschluss** sagen
    kann: Die Einnahmearten (Steuern, Zuwendungen, Gebühren …) stehen dort in
    derselben Gliederung wie später im Abschluss, nur eben als Ansatz.

    Zwei Pflicht-Proben entscheiden, beide in
    ``council/ergebnishaushalt.py``: Die Summenzeilen müssen in allen sechs
    Spalten aufgehen, und die hervorgehobene Planjahr-Spalte muss sich in
    jeder Zeile wiederholen. Die zweite ist die wichtigere — sie ist der
    Beleg dafür, welche Spalte der **Haushaltsansatz** ist und welche bloß
    Finanzplanung. Ohne sie wäre die Trennung eine Reihenfolgeannahme.

    Die Ist-Spalte des Vorvorjahres wird **nicht gespeichert**, sondern gegen
    ``council_ergebnisrechnung`` gehalten und im Protokoll ausgewiesen. Sie
    trifft dort bewusst nicht auf den Cent: Der Gesamtergebnishaushalt ist die
    Gesamtebene (mit den nicht rechtsfähigen Stiftungen), der gespeicherte
    Jahresabschluss die Kernverwaltung. Der Abstand liegt über acht Jahrgänge
    bei höchstens 0,075 % der Ertragssumme; wird er größer, meldet der Lauf
    es — dann stammt eine Spalte aus dem falschen Jahr.

    **Gespeichert wird der Entwurf, nicht der Beschluss** — die Anlage hängt
    an der Einbringungs-Vorlage. Das steht in der Herkunft (``stand``), damit
    eine Seite es anschreiben kann; die Begründung samt Messwerten im
    Modulkopf von ``council/ergebnishaushalt.py``."""
    quelle = QUELLEN["ergebnishaushalt"]
    sql, werte = quelle.erkennung.abfrage("document_id, label, url, raw_text")
    rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
    vorhanden = _bestand_ergebnishaushalt(store) if nur_fehlende else set()

    # Die Ist-Werte der Kernverwaltung einmal holen — Grundlage der Gegenprobe.
    ist_bestand: dict[int, dict[int, float]] = {}
    for zeile in store.get_ergebnisrechnung():
        if zeile.get("thh_nr") is None and zeile.get("ergebnis") is not None:
            ist_bestand.setdefault(zeile["jahr"], {})[zeile["nr"]] = zeile["ergebnis"]

    je_jahrgang: dict[int, dict] = {}
    geschuetzt = verworfen = 0
    gegenproben: list[dict] = []
    for r in rows:
        gelesen = ergebnishaushalt.lies(r["raw_text"] or "")
        jahrgang = gelesen["jahrgang"]
        if jahrgang is None:
            p.warnen(f"  Dokument {r['document_id']} ({r['label']!r}): Tabellenkopf "
                     f"nicht lesbar — übersprungen")
            verworfen += 1
            continue
        if (jahrgang,) in vorhanden:
            continue
        if jahrgang in je_jahrgang:
            p.warnen(f"  {jahrgang}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        if not gelesen["bestanden"]:
            p.warnen(f"  {jahrgang}: {gelesen['nachweis']} — Dokument "
                     f"{r['document_id']}, nicht gespeichert")
            verworfen += 1
            continue

        alt = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnishaushalt "
                             "WHERE plan_jahrgang = ?", (jahrgang,))
        if not bestandsschutz(p, f"{jahrgang} Ergebnishaushalt", alt,
                              len(gelesen["zeilen"]), schuetzen):
            geschuetzt += 1 if alt else 0
            continue

        # Gegenprobe VOR dem Speichern, damit ihr Messwert in die Herkunft
        # kommt: Der Beleg auf der Seite soll sagen, woran die Zahl hängt.
        gp = ergebnishaushalt.gegenprobe(
            gelesen["ist"], ist_bestand.get(gelesen["ist_jahr"], {}))
        if gp["plausibel"] is False:
            p.warnen(f"  {jahrgang}: die Ist-Spalte {gelesen['ist_jahr']} weicht um "
                     f"{gp['groesste_abweichung']:,.2f} € ({gp['anteil']*100:.3f} % der "
                     f"Ertragssumme) vom gespeicherten Jahresabschluss ab — mehr, als "
                     f"die Stiftungen erklären. Bitte das Dokument ansehen.")
        gp["jahrgang"] = jahrgang
        gegenproben.append(gp)

        store.save_ergebnishaushalt(jahrgang, gelesen["zeilen"], herkunft.Herkunft(
            art="ris", probe=["ergebnishaushalt_summenzeilen",
                              "ergebnishaushalt_planspalte"],
            dokument_id=r["document_id"], label=r["label"], url=r["url"],
            fundstelle="Gesamtergebnishaushalt, Posten 1–24 — Spalte "
                       f"„Ansatz {jahrgang}“ und die drei Finanzplanungsjahre",
            probe_ergebnis=gelesen["nachweis"],
            # NICHT „Haushaltsplan {jahrgang}" schlechthin: Die Anlage hängt
            # an der Vorlage, mit der die Verwaltung den Haushalt einbringt.
            # Was der Rat in den Beratungen ändert, steht nicht drin — bei den
            # ordentlichen Erträgen sind das 0,7 bis 13,1 Mio. € gegenüber dem
            # Ansatz, den der spätere Jahresabschluss führt. Der Beleg auf der
            # Seite muss das sagen können.
            stand=f"Haushaltsplan {jahrgang}, Anlage 005 — Stand der Einbringung"))

        ansatz = [z for z in gelesen["zeilen"] if z["art"] == "ansatz"]
        e = next((z["betrag"] for z in ansatz if z["nr"] == 12), None)
        a = next((z["betrag"] for z in ansatz if z["nr"] == 20), None)
        fp = sorted({z["jahr"] for z in gelesen["zeilen"] if z["art"] == "finanzplanung"})
        je_jahrgang[jahrgang] = {"zeilen": len(gelesen["zeilen"]),
                                 "ansatz": len(ansatz), "finanzplanung": fp}
        p.sagen(f"  {jahrgang}: Ansatz {e/1e6:.1f} Mio. Erträge / {a/1e6:.1f} Mio. "
                f"Aufwendungen · {len(ansatz)} Posten · Finanzplanung "
                f"{'/'.join(map(str, fp))} getrennt gespeichert · Dokument "
                f"{r['document_id']}")
        p.sagen(f"      Gegenprobe Ist {gelesen['ist_jahr']}: {gp['gleich']}/"
                f"{gp['geprueft']} Posten deckungsgleich mit dem Jahresabschluss, "
                f"größter Abstand {gp['groesste_abweichung']:,.0f} € "
                f"({gp['anteil']*100:.3f} % — Gesamtebene gegen Kernverwaltung)")

    # Die Schlüssel jenseits von `neue_jahrgaenge`, `neue_einheiten` und
    # `bestand_geschuetzt` tragen einen eigenen Namen: Der gemeinsame Bericht
    # in `scripts/ingest_finanzberichte.py` legt alle Schichten in ein dict,
    # und ein zweites `verworfen` überschriebe stumm das der Nachbarschicht.
    return {"neue_jahrgaenge": sorted(je_jahrgang),
            "neue_einheiten": [(j,) for j in sorted(je_jahrgang)],
            "bestand_geschuetzt": geschuetzt,
            "je_plan_jahrgang": je_jahrgang,
            "planzeilen": sum(d["zeilen"] for d in je_jahrgang.values()),
            "plan_verworfen": verworfen,
            "plan_gegenprobe": [{"jahrgang": g["jahrgang"], "gleich": g["gleich"],
                                 "geprueft": g["geprueft"],
                                 "anteil_prozent": round(g["anteil"] * 100, 4)}
                                for g in gegenproben]}


def lies_schlussbericht_fundstellen(store: CouncilStore, p: Protokoll,
                                    nur_fehlende: bool = False,
                                    schuetzen: bool = True) -> dict:
    """Schlussberichte des Rechnungsprüfungsamts als Fundstelle merken —
    nur Verweis, kein Inhalt („Das Rechnungsprüfungsamt hat diesen Abschluss
    geprüft").

    Eine Zeile je Jahrgang, ein Dokument je Zeile — hier ist die Einheit
    tatsächlich der Jahrgang, und „da" heißt „fertig"."""
    sql, werte = QUELLEN["rpa_fundstelle"].erkennung.abfrage(
        "document_id, label, url, n_pages, raw_text")
    rows = store._conn.execute(sql, werte).fetchall()  # noqa: SLF001
    vorhanden = _bestand_schlussberichte(store) if nur_fehlende else set()
    neu: list[int] = []
    gefunden = unlesbar = 0
    for r in rows:
        treffer = finanzberichte.pruefbericht_aus_anlage(r["label"], r["raw_text"])
        if not treffer:
            continue
        if (treffer["jahr"],) in vorhanden:
            continue
        # Der Buchstabenanteil steht auch dann dabei, wenn er die Probe
        # REISST (2024: 0,00) — dann fehlt `textextrakt` in der Liste, und
        # die Zahl daneben sagt, warum. Eine gerissene Probe zu verschweigen
        # wäre schlimmer, als sie zu nennen.
        proben = ["eingangsformel"] + (["textextrakt"] if treffer["lesbar"] else [])
        store.save_pruefbericht_quelle(
            treffer["jahr"],
            herkunft.Herkunft(
                art="ris", probe=proben, dokument_id=r["document_id"],
                label=r["label"], url=r["url"],
                fundstelle="Deckblatt und Eingangsformel des Schlussberichts",
                probe_ergebnis=f"Buchstabenanteil im Volltext "
                               f"{treffer['buchstabenanteil']:.2f}",
                stand=f"Jahresabschluss {treffer['jahr']}"),
            r["n_pages"], treffer["lesbar"])
        neu.append(treffer["jahr"])
        gefunden += 1
        hinweis = "" if treffer["lesbar"] else "  (Volltext unbrauchbar, nur Verweis)"
        p.sagen(f'  {treffer["jahr"]}: {r["n_pages"]} Seiten{hinweis}')
        unlesbar += 0 if treffer["lesbar"] else 1
    return {"neue_jahrgaenge": neu, "neue_einheiten": [(j,) for j in neu],
            "pruefberichte": gefunden, "pruefberichte_ohne_text": unlesbar}


def lies_teilhaushalte(store: CouncilStore, p: Protokoll,
                       nur_fehlende: bool = False,
                       schuetzen: bool = True) -> dict:
    """Produktebene aus den Teilhaushalts-Plänen: was einzelne Aufgaben kosten,
    mit Produktnummer, Amt und Steckbrief.

    ``nur_fehlende`` schränkt auf Dokumente ein, deren **Teilhaushalt** noch
    fehlt — nicht deren Jahrgang. Ein Produkt-Jahrgang verteilt sich auf rund
    neun Anlagen, die einzeln und zu verschiedenen Zeiten lesbar werden: Über
    ``check_protocols`` kommen sie ohne Volltext herein, den holt
    ``backfill_anlagen_texte.py`` später und tranchenweise nach. Wer den
    Jahrgang sperrt, sobald das erste Dokument gelesen ist, verliert die
    anderen acht dauerhaft — und merkt es nie, weil der Jahrgang „da" ist.

    **Ein Teilhaushalt wird genau einmal versorgt, vom ersten Dokument.**
    Sechs (Jahrgang, Teilhaushalt)-Paare hängen an zwei Vorlagen — dieselbe
    PDF-Datei, ein zweites Mal unter einem anderen Tagesordnungspunkt
    hochgeladen (2018/THH08, 2018/THH11, 2019/THH11, 2020/THH08, 2021/THH08,
    2022/THH08; nachgemessen 08/2026, der Volltext ist Byte für Byte
    derselbe). Ohne Regel entschied die Sortierung der Kandidaten, welches
    Dokument als Quelle in der Zeile steht — und das fiel zugunsten der
    schlechteren Angabe aus: „TOP 5 - Anlage III - THH 08" sagt außerhalb
    seiner Sitzung nichts, und „2019 THH 08" trägt am Plan für **2018** die
    falsche Jahreszahl. Das erste Dokument ist die Anlage der Haushalts-
    vorlage selbst und führt die Zählung des Plans („014 THH08").

    Weichen die Zahlen des zweiten Dokuments ab, ist das eine **neue Lage** —
    ein Nachtragshaushalt etwa, der einen Ansatz wirklich ändert. Dann wird
    gemeldet statt still überschrieben; welcher Stand gilt, entscheidet
    niemand nebenbei in einem unbeaufsichtigten Lauf."""
    sql, werte = QUELLEN["teilhaushalt"].erkennung.abfrage(
        "document_id, label, url, raw_text")
    rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
    vorhanden = _bestand_produkte(store) if nur_fehlende else set()
    if nur_fehlende:
        rows = [r for r in rows if (teilhaushalt_jahrgang((r["raw_text"] or "")[:4000]),
                                    teilhaushalt_nummer(r["label"])) not in vorhanden]

    je_jahr: dict[int, int] = {}
    neue_einheiten: set[tuple] = set()
    mit_feld: dict[str, int] = {f: 0 for f in STECKBRIEF}
    ohne = geschuetzt = dubletten = 0
    # (jahr, thh_nr) → (Signatur, Dokument), das den Teilhaushalt versorgt hat.
    versorgt: dict[tuple, tuple] = {}
    for r in rows:
        produkte = finanzberichte.parse_teilergebnishaushalt(r["raw_text"] or "")
        if not produkte:
            ohne += 1
            continue
        for jahr in {x["jahr"] for x in produkte}:
            teil = [x for x in produkte if x["jahr"] == jahr]
            # ``save_produkte`` löscht nichts, überschreibt aber Zeile für
            # Zeile. Verglichen wird deshalb je Teilhaushalt, nicht je Jahr:
            # Ein Dokument trägt immer nur seinen eigenen THH bei, gegen den
            # Jahresbestand gehalten sähe jedes Dokument wie ein Einbruch aus.
            with store.transaktion():
                for thh_nr in sorted({x.get("thh_nr") for x in teil}, key=lambda v: v or 0):
                    if (jahr, thh_nr) in vorhanden:
                        continue
                    stueck = [x for x in teil if x.get("thh_nr") == thh_nr]
                    # Zweites Dokument für denselben Teilhaushalt: Das erste
                    # hat ihn versorgt (siehe Docstring). Nur die Herkunft
                    # würde hier noch getauscht — und mit ihr entstünde ein
                    # Herkunfts-Datensatz, auf den am Ende des Laufs keine
                    # Zeile mehr zeigt (`herkunft_aufraeumen` fegte sechs
                    # Stück je Lauf wieder weg).
                    if (jahr, thh_nr) in versorgt:
                        signatur, quelle = versorgt[(jahr, thh_nr)]
                        if _produkt_signatur(stueck) != signatur:
                            p.warnen(
                                f"  {jahr} THH{thh_nr}: Dokument {r['document_id']} "
                                f"({r['label']!r}) trägt ANDERE Zahlen als "
                                f"Dokument {quelle['document_id']} "
                                f"({quelle['label']!r}), das den Teilhaushalt "
                                f"versorgt hat — es gilt weiter das erste. "
                                f"Bitte prüfen, welcher Stand der richtige ist.")
                        dubletten += 1
                        continue
                    alt = _anzahl(store, "SELECT COUNT(*) FROM council_produkte "
                                         "WHERE jahr = ? AND thh_nr IS ?", (jahr, thh_nr))
                    if not bestandsschutz(p, f"{jahr} THH{thh_nr}", alt,
                                          len(stueck), schuetzen):
                        geschuetzt += 1 if alt else 0
                        continue
                    store.save_produkte(jahr, stueck, herkunft.Herkunft(
                        art="ris", probe="produktzeile",
                        dokument_id=r["document_id"], label=r["label"], url=r["url"],
                        fundstelle=(f"Teilergebnishaushalt THH{thh_nr:02d}, "
                                    f"Produktebene mit Steckbrief" if thh_nr
                                    else "Teilergebnishaushalt, Produktebene"),
                        probe_ergebnis=f"{len(stueck)} Produktzeilen mit "
                                       f"aufgehender Ergebnis-Rechnung",
                        stand=f"Haushaltsplan {jahr}"))
                    versorgt[(jahr, thh_nr)] = (_produkt_signatur(stueck), r)
                    neue_einheiten.add((jahr, thh_nr))
                    je_jahr[jahr] = je_jahr.get(jahr, 0) + len(stueck)
                    for feld in STECKBRIEF:
                        mit_feld[feld] += sum(1 for x in stueck if x.get(feld))
    for jahr in sorted(je_jahr):
        p.sagen(f"  {jahr}: {je_jahr[jahr]} Produkt-Zeilen")
    if dubletten:
        # Keine Warnung: Das ist der bekannte, gemessene Normalfall (sechs
        # Paare). Auffällig wäre erst, wenn die Zahl wächst — dann steht eine
        # Vorlage mehrfach im Bestand, die vorher einmal dastand.
        p.sagen(f"  {dubletten}× ein zweites Dokument zu einem bereits "
                f"versorgten Teilhaushalt — übersprungen")
    if ohne:
        # Der eigentliche Frühwarnwert dieses Laufs: Dokumente, die aussehen
        # wie ein Teilhaushalts-Plan, aus denen der Parser aber nichts holt.
        p.warnen(f"  {ohne} Dokument(e) ohne lesbare Produkt-Tabelle")

    # Abdeckung je Feld — gezählt wird der TABELLENSTAND, nicht die Zahl der
    # gelesenen Zeilen: Der Lauf liest nur, was ihm fehlt, die Tabelle trägt
    # aber auch die Jahrgänge früherer Läufe. Auf der Seite steht später der
    # Tabellenstand.
    gesamt = store._conn.execute(  # noqa: SLF001
        "SELECT COUNT(*) FROM council_produkte").fetchone()[0]
    p.sagen(f"  Steckbrief-Abdeckung ({gesamt} Produkte in der Tabelle):")
    abdeckung: dict[str, int] = {}
    for feld in STECKBRIEF:
        n = store._conn.execute(  # noqa: SLF001
            f"SELECT COUNT(*) FROM council_produkte WHERE {feld} IS NOT NULL "
            f"AND {feld} != ''").fetchone()[0]
        abdeckung[feld] = n
        anteil = f"{n / gesamt * 100:.1f} %" if gesamt else "–"
        p.sagen(f"    {feld:20s} {n:>5}  ({anteil})")
    return {"neue_jahrgaenge": sorted(je_jahr),
            "neue_einheiten": sorted(neue_einheiten), "dokumente": len(rows),
            "ohne_treffer": ohne, "bestand_geschuetzt": geschuetzt,
            "dubletten": dubletten, "produkte": sum(je_jahr.values()),
            "in_tabelle": gesamt, "steckbrief": abdeckung}


def lies_pruefungsfeststellungen(store: CouncilStore, p: Protokoll,
                                 nur_fehlende: bool = False,
                                 schuetzen: bool = True,
                                 trocken: bool = False) -> dict:
    """Prüfungsfeststellungen aus den Schlussberichten des RPA.

    Die Auswahl der Dokumente läuft **nicht über das Label**: „Schlussbericht
    JA 2017" ist der Bericht zum Eigenbetrieb Gebäudewirtschaft, dazu kommen
    jedes Jahr die formgleichen Berichte zur Klävemann-Stiftung, zur Vereinten
    Oldenburger Sozialstiftung, zu AWB und EGH — alle mit ähnlichem Titel und
    derselben Jahreszahl. Getrennt wird über den Textanfang
    (``pruefberichte.erkenne_jahrgang``), der zugleich sagt, zu welchem
    Jahresabschluss der Bericht gehört.

    Die Zahl der **verworfenen** Feststellungen ist die eigentliche Kennzahl:
    Sie bleibt bei 0, solange das Dokumentformat hält. Steigt sie, ist es Zeit
    für einen Blick in den Bericht — nicht für eine gelockerte Regel."""
    from collections import Counter

    sql, werte = QUELLEN["pruefungsfeststellungen"].erkennung.abfrage(
        "document_id, label, url, raw_text")
    rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
    vorhanden = _bestand_feststellungen(store) if nur_fehlende else set()

    je_jahr: dict[int, dict] = {}
    geschuetzt = 0
    for r in rows:
        ergebnis = pruefberichte.parse_feststellungen(r["raw_text"] or "")
        jahr = ergebnis["jahr"]
        if jahr is None:
            continue  # Stiftung, Eigenbetrieb oder kaputter Textextrakt
        if (jahr,) in vorhanden:
            continue
        gefunden = ergebnis["feststellungen"]
        if not gefunden:
            p.warnen(f"  {jahr}: keine Feststellung lesbar "
                     f"(Legende {sorted(ergebnis['legende']) or '—'}) — übersprungen")
        if jahr in je_jahr:
            p.warnen(f"  {jahr}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        # save_pruefbericht leert den Jahrgang, bevor es schreibt — gegen ein
        # leeres oder deutlich kleineres Ergebnis passiert das nicht.
        alt = _anzahl(store, "SELECT COUNT(*) FROM council_pruefberichte WHERE jahr = ?",
                      (jahr,))
        if not bestandsschutz(p, f"{jahr} Feststellungen", alt, len(gefunden), schuetzen):
            geschuetzt += 1 if alt else 0
            continue
        marken = Counter(f["marke"] for f in gefunden)
        if not trocken:
            store.save_pruefbericht(jahr, gefunden, herkunft.Herkunft(
                art="ris", probe="legende_und_verzeichnis",
                dokument_id=r["document_id"], label=r["label"], url=r["url"],
                # Grob mit Absicht: Die genaue Fundstelle einer Feststellung
                # ist ihre Textziffer und ihre Seite, und die stehen je Zeile
                # in der Tabelle.
                fundstelle="Randmarken B, WB, H und K im Fließtext",
                probe_ergebnis=f"{len(gefunden)} Feststellungen übernommen, "
                               f"{len(ergebnis['verworfen'])} verworfen",
                stand=f"Schlussbericht zum Jahresabschluss {jahr}"))
        je_jahr[jahr] = {"feststellungen": len(gefunden),
                         "verworfen": len(ergebnis["verworfen"]),
                         "marken": dict(marken)}
        marken_text = " · ".join(
            f"{m} {marken[m]}" for m in pruefberichte.MARKEN if marken.get(m))
        p.sagen(f"  {jahr}: {len(gefunden)} Feststellungen ({marken_text})"
                f" · verworfen {len(ergebnis['verworfen'])}"
                f" · Dokument {r['document_id']}")
        for v in ergebnis["verworfen"]:
            p.warnen(f"      verworfen: {v}")
    return {"neue_jahrgaenge": sorted(je_jahr), "je_jahr": je_jahr,
            "bestand_geschuetzt": geschuetzt,
            "feststellungen": sum(d["feststellungen"] for d in je_jahr.values()),
            "verworfen": sum(d["verworfen"] for d in je_jahr.values())}


def lies_konzernabschluesse(store: CouncilStore, p: Protokoll,
                            nur_fehlende: bool = False,
                            schuetzen: bool = True) -> dict:
    """Der Konzern Stadt Oldenburg aus den konsolidierten Gesamtabschlüssen.

    Vier Proben entscheiden, und zwar in dieser Reihenfolge:

    1. die drei **Rechenproben der Gesamtergebnisrechnung** — sie sind das
       Eintrittsbillett; ohne sie kommt der Jahrgang gar nicht erst herein;
    2. die **Spaltenprobe** je Trägeraufstellung (Träger + Konsolidierung =
       Summe);
    3. die **Querprobe** zwischen beiden Tabellen (Trägersumme = Summenposten
       der Gesamtergebnisrechnung);
    4. die **Vorjahres-Kette** über Dokumentgrenzen: Die Vorjahresspalte des
       Jahrgangs N muss die Jahresspalte von N−1 aus einem *anderen* Dokument
       wiedergeben.

    Die Kette ist bewusst **kein** Ausschlussgrund, sondern eine Meldung: Sie
    prüft zwei Jahrgänge gegeneinander, und wer bei Streit beide wegwirft,
    verliert einen guten wegen eines schlechten. Sie steht deshalb im
    Protokoll und in der Rückgabe — schlägt sie an, hat sich etwas an der
    Quelle geändert, und das gehört angesehen, nicht automatisch entschieden.
    """
    quelle = QUELLEN["konzernabschluss"]
    sql, werte = quelle.erkennung.abfrage("document_id, label, url, n_pages, raw_text")
    rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
    vorhanden = _bestand_konzernabschluss(store) if nur_fehlende else set()

    je_jahr: dict[int, dict] = {}
    gelesen: dict[int, list[dict]] = {}
    geschuetzt = verworfen_gesamt = 0
    for r in rows:
        jahr = konzernabschluss.jahrgang(r["raw_text"])
        if jahr is None:
            continue  # Schlussbericht oder Teilhaushalts-Plan im selben Vorfilter
        if (jahr,) in vorhanden:
            continue
        if jahr in je_jahr:
            p.warnen(f"  {jahr}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        ergebnis = konzernabschluss.lies(r["raw_text"] or "")
        if not ergebnis["bestanden"]:
            gerissen = [x["probe"] for x in ergebnis["proben"] if not x["ok"]]
            grund = (f"Probe gerissen: {'; '.join(gerissen)}" if gerissen
                     else f"nur {len(ergebnis['proben'])} von 3 Proben rechenbar")
            p.warnen(f"  {jahr}: {grund} — Dokument {r['document_id']}, nicht gespeichert")
            verworfen_gesamt += ergebnis["verworfen"]
            continue
        alt = _anzahl(store, "SELECT COUNT(*) FROM council_konzern_posten WHERE jahr = ?",
                      (jahr,))
        if not bestandsschutz(p, f"{jahr} Konzern-Posten", alt,
                              len(ergebnis["posten"]), schuetzen):
            geschuetzt += 1 if alt else 0
            continue
        traeger = [z | {"art": block["art"]}
                   for block in ergebnis["traeger"] for z in block["zeilen"]]

        # Zwei Herkünfte, weil es zwei Abschnitte sind: Die Posten stehen in
        # 3.2, die Trägeraufstellung in 4.1.1, und sie sind durch verschiedene
        # Proben gedeckt. `stand` nennt den Stichtag des Inhalts — bei den
        # Beteiligungen ist genau das der Punkt, an dem sich Konzern- und
        # Einzelabschluss unterscheiden werden.
        anker = dict(art="ris", dokument_id=r["document_id"], label=r["label"],
                     url=r["url"], stand=f"Gesamtabschluss zum 31.12.{jahr}")
        h_posten = herkunft.Herkunft(
            probe=["konzern_ergebnisprobe", "konzern_ausserordentlich",
                   "konzern_gesamtergebnis"],
            fundstelle="Abschnitt 3.2, Gesamtergebnisrechnung des Konzerns",
            probe_ergebnis=konzernabschluss.probennachweis(ergebnis["proben"]),
            **anker)
        h_traeger = herkunft.Herkunft(
            probe=["konzern_zeilenprobe", "konzern_traegersumme", "konzern_querprobe"],
            fundstelle="Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern",
            probe_ergebnis=konzernabschluss.traegernachweis(ergebnis["traeger"]),
            **anker) if traeger else None
        store.save_konzern_jahrgang(jahr, ergebnis["posten"], traeger,
                                    h_posten, h_traeger)
        gelesen[jahr] = ergebnis["posten"]
        verworfen_gesamt += ergebnis["verworfen"]
        je_jahr[jahr] = {"posten": len(ergebnis["posten"]), "traeger": len(traeger),
                         "aufstellungen": len(ergebnis["traeger"]),
                         "verworfen": ergebnis["verworfen"]}
        p.sagen(f"  {jahr}: {len(ergebnis['posten'])} Posten · {len(traeger)} Trägerzeilen "
                f"aus {len(ergebnis['traeger'])} Aufstellungen"
                f" · verworfen {ergebnis['verworfen']} · Dokument {r['document_id']}")
        # Nur melden, wenn eine *vorhandene* Aufstellung durchgefallen ist.
        # Bis 2016 führt der Bericht den Abschnitt 4.1.1 noch nicht — das ist
        # eine Lücke der Quelle und keine Meldung wert.
        if len(ergebnis["traeger"]) < ergebnis["traeger_gefunden"]:
            p.warnen(f"  {jahr}: {ergebnis['traeger_gefunden'] - len(ergebnis['traeger'])} "
                     f"von {ergebnis['traeger_gefunden']} Trägeraufstellungen an ihrer "
                     "Spalten- oder Querprobe gescheitert")

    kette = _kette_pruefen(gelesen, p)
    return {"neue_jahrgaenge": sorted(je_jahr),
            "neue_einheiten": [(j,) for j in sorted(je_jahr)],
            "je_jahr": je_jahr, "bestand_geschuetzt": geschuetzt,
            "konzern_posten": sum(d["posten"] for d in je_jahr.values()),
            "konzern_traeger": sum(d["traeger"] for d in je_jahr.values()),
            "verworfen": verworfen_gesamt, **kette}


#: Rollen, deren Vorjahresspalte gegen den Vorjahrgang geprüft wird.
_KETTEN_ROLLEN = ("ertraege_summe", "aufwendungen_summe", "ord_ergebnis",
                  "gesamtergebnis")


def _kette_pruefen(gelesen: dict[int, list[dict]], p: Protokoll) -> dict:
    """Vorjahresspalte gegen den Vorjahrgang — über Dokumentgrenzen hinweg.

    Bis 2016 führt der Bericht die Vorjahreszahlen in Tausend Euro; die
    Toleranz muss dort eine halbe Rundungseinheit hergeben, sonst schlägt
    jede Zeile an, die auf Tausend gerundet wurde."""
    geprueft = bestanden = 0
    for jahr in sorted(gelesen):
        if jahr - 1 not in gelesen:
            continue
        jetzt = {x["rolle"]: x for x in gelesen[jahr] if x["rolle"]}
        vorher = {x["rolle"]: x for x in gelesen[jahr - 1] if x["rolle"]}
        toleranz = 1000.0 if jahr <= 2016 else konzernabschluss.TOLERANZ_EUR
        for rolle in _KETTEN_ROLLEN:
            a = (jetzt.get(rolle) or {}).get("vorjahr")
            b = (vorher.get(rolle) or {}).get("betrag")
            if a is None or b is None:
                continue
            geprueft += 1
            if abs(a - b) <= toleranz:
                bestanden += 1
            else:
                p.warnen(f"  Vorjahres-Kette {jahr - 1}→{jahr} {rolle}: "
                         f"{b:,.2f} gegen {a:,.2f} — Abweichung {a - b:+,.2f}")
    if geprueft:
        p.sagen(f"  Vorjahres-Kette: {bestanden}/{geprueft} über Dokumentgrenzen geschlossen")
    return {"kette_geprueft": geprueft, "kette_bestanden": bestanden}


# --- Die Registry -----------------------------------------------------------

QUELLEN: dict[str, Finanzquelle] = {}

for _q in (
    Finanzquelle(
        key="jahresabschluss",
        label="Jahresabschluss",
        was="Was die Stadt in einem Jahr wirklich eingenommen und ausgegeben hat — "
            "neben dem, was sie geplant hatte.",
        tabelle="council_ergebnisrechnung",
        nebentabellen=("council_abweichungsgruende",),
        erwarteter_monat=9,
        versatz=1,
        herkunft="ris",
        erkennung=Erkennung(
            label_muster=("%Jahresabschluss%",),
            mindest_seiten=100,
            # Der Rechenschaftsbericht und der Schlussbericht des RPA tragen
            # dieselbe Jahreszahl im Titel und sind ein anderes Dokument.
            ausschluesse=("%Rechenschaft%", "%Schlussbericht%"),
        ),
        einheit="Ebenen",
        einheiten_von=_einheiten_jahresabschluss,
        bestand=_bestand_jahresabschluss,
        einlesen=lies_jahresabschluesse,
    ),
    Finanzquelle(
        key="rpa_fundstelle",
        label="Schlussbericht des Rechnungsprüfungsamts",
        was="Der Nachweis, dass eine unabhängige Stelle diesen Abschluss geprüft hat.",
        tabelle="council_pruefbericht_quellen",
        erwarteter_monat=9,
        versatz=1,
        herkunft="ris",
        erkennung=Erkennung(
            label_muster=("%chlussbericht%",),
            text_muster=("Schlussbericht%",),
            oder=True,
        ),
        einheiten_von=_einheiten_schlussbericht,
        bestand=_bestand_schlussberichte,
        einlesen=lies_schlussbericht_fundstellen,
    ),
    Finanzquelle(
        key="pruefungsfeststellungen",
        label="Prüfungsfeststellungen",
        was="Was das Rechnungsprüfungsamt an der Verwaltung beanstandet, im Wortlaut.",
        tabelle="council_pruefberichte",
        erwarteter_monat=9,
        versatz=1,
        herkunft="ris",
        erkennung=Erkennung(
            # Grob mit Absicht: Im Extrakt steht der Titel über vier Zeilen
            # verteilt, ein LIKE auf den ganzen Satz fände keinen Bericht.
            text_muster=("%Rechnungsprüfungsamtes%",),
            mindest_seiten=30,
            ordnung="document_id",
        ),
        einheiten_von=_einheiten_feststellungen,
        bestand=_bestand_feststellungen,
        einlesen=lies_pruefungsfeststellungen,
    ),
    Finanzquelle(
        key="teilhaushalt",
        label="Teilhaushalts-Pläne (Produktebene)",
        was="Was einzelne Aufgaben kosten — von der Musikschule bis zur Straßenreinigung.",
        tabelle="council_produkte",
        erwarteter_monat=10,
        versatz=0,
        herkunft="ris",
        # ``document_id`` ist die getfile-Nummer des Ratsinformationssystems
        # und steigt mit jedem Upload — die Kandidaten kommen damit in
        # VERÖFFENTLICHUNGS-Reihenfolge. Das ist hier keine Kosmetik: Sechs
        # Teilhaushalte hängen an zwei Vorlagen, und die Regel „das erste
        # Dokument versorgt den Teilhaushalt" (siehe `lies_teilhaushalte`)
        # braucht ein Kriterium, das etwas bedeutet. Nach `label` sortiert
        # gewänne sonst der Zufall der Schreibweise.
        erkennung=Erkennung(label_muster=("%THH%",), mindest_seiten=40,
                            ordnung="document_id"),
        # Die Einheit ist der Teilhaushalt, nicht der Jahrgang: Ein Jahr
        # verteilt sich auf rund neun Anlagen, die einzeln lesbar werden.
        einheit="Teilhaushalte",
        einheiten_von=_einheiten_teilhaushalt,
        bestand=_bestand_produkte,
        einlesen=lies_teilhaushalte,
    ),
    Finanzquelle(
        key="konzernabschluss",
        label="Konsolidierter Gesamtabschluss (Konzern Stadt)",
        was="Was die Stadt mit Klinikum, Bussen, Bädern und Gebäudewirtschaft "
            "zusammen bewegt — nicht nur die Kernverwaltung.",
        tabelle="council_konzern_posten",
        nebentabellen=("council_konzern_traeger",),
        # Der Rat bekam den Bericht zuletzt zwischen Juni und Februar; er
        # entsteht erst, wenn alle einbezogenen Jahresabschlüsse geprüft sind,
        # und liegt damit rund zwei Jahre hinter dem Haushaltsjahr.
        erwarteter_monat=2,
        versatz=2,
        herkunft="ris",
        erkennung=Erkennung(
            # Bewusst nur auf dem Text: Die Labels dieser Reihe sind wertlos —
            # der Jahrgang 2016 heißt „Anlage", 2013 ebenso, und „Prüfbericht
            # GA 2021" trifft nur drei der zwölf. Was der Vorfilter zu viel
            # hereinlässt (Schlussberichte, Teilhaushalts-Pläne), wirft
            # `konzernabschluss.jahrgang` am Textkopf wieder hinaus.
            text_muster=(konzernabschluss.TEXT_MUSTER,),
            mindest_seiten=40,
            ordnung="document_id",
        ),
        einheiten_von=_einheiten_konzernabschluss,
        bestand=_bestand_konzernabschluss,
        einlesen=lies_konzernabschluesse,
    ),
    Finanzquelle(
        key="ergebnishaushalt",
        label="Gesamtergebnishaushalt (Planjahre)",
        was="Woher das Geld im kommenden Jahr kommen soll und wofür es "
            "ausgegeben wird — nach Arten, für Jahre, die noch keinen "
            "Jahresabschluss haben.",
        tabelle="council_ergebnishaushalt",
        # Anlage 005 des Haushaltsplans, also derselbe Takt wie die
        # Teilhaushalte: Einbringung Anfang Oktober des Vorjahres. Über acht
        # Jahrgänge gemessen 7 von 8 im Oktober, einer im November.
        erwarteter_monat=10,
        versatz=-1,
        herkunft="ris",
        erkennung=Erkennung(
            # Das Label reicht hier ausnahmsweise: „Gesamtergebnishaushalt"
            # steht bei genau diesen acht Anlagen im Titel. Ein Textfilter
            # zöge 45 weitere herein (Vorberichte, Rechenschaftsberichte,
            # Finanz- und Leistungsberichte), die das Wort bloß erwähnen.
            label_muster=("%Gesamtergebnishaushalt%",),
            # Die Dokumente haben 16–18 Seiten; die Schwelle hält Deckblätter
            # und Auszüge draußen, ohne den kleinsten Jahrgang zu verlieren.
            mindest_seiten=10,
            ordnung="document_id",
        ),
        einheiten_von=_einheiten_ergebnishaushalt,
        bestand=_bestand_ergebnishaushalt,
        einlesen=lies_ergebnishaushalte,
    ),
    Finanzquelle(
        key="haushaltsplan",
        label="Haushaltsplan",
        was="Der Plan, den der Rat beschließt: was die Stadt im kommenden Jahr "
            "einnehmen und ausgeben will.",
        tabelle="council_haushalt",
        erwarteter_monat=10,
        # Der Plan für 2027 wird im Oktober 2026 beschlossen.
        versatz=-1,
        # Kommt NICHT aus council_anlagen, sondern als PDF/CSV von oldenburg.de
        # (scripts/ingest_haushalt.py). Der Cron lädt nichts herunter — er
        # beobachtet diese Schicht nur und meldet, wenn ein Jahrgang ausbleibt.
        herkunft="stadt",
        nachschub="Download von oldenburg.de, scripts/ingest_haushalt.py",
        bestand=_bestand_haushaltsplan,
    ),
    Finanzquelle(
        key="lsn_steuerkraft",
        label="Steuerkraft im Städtevergleich",
        was="Wie viel Steuerkraft Oldenburg gegenüber den anderen sieben "
            "kreisfreien Städten Niedersachsens auf die Waage bringt.",
        tabelle="council_staedtevergleich",
        # Die endgültigen Tabellen tragen den Stand März/April des
        # Ausgleichsjahres (vier Jahrgänge nachgesehen, s. Modul-Kopf). April
        # ist der späteste gemessene Monat — wer März nähme, meldete 2023 und
        # 2024 einen Rückstand, den es nicht gab.
        erwarteter_monat=4,
        versatz=0,
        herkunft="lsn",
        nachschub="Download vom Landesamt für Statistik, "
                  "scripts/ingest_staedtevergleich.py --kfa",
        bestand=_bestand_lsn_steuerkraft,
    ),
    Finanzquelle(
        key="lsn_realsteuern",
        # Der amtliche Titel, und bewusst ohne „und": Die Fußzeile des
        # Datenstands reiht die Namen der Schichten zu einer Aufzählung
        # („A und B") — ein Label, das selbst ein „und" trägt, ergibt darin
        # „A und B und C" und liest sich wie drei Dinge. Was drinsteckt, sagt
        # der Satz darunter.
        label="Realsteuervergleich",
        was="Was die acht Städte bei Grund- und Gewerbesteuer verlangen — und "
            "was am Ende je Einwohnerin hereinkommt.",
        tabelle="council_staedtevergleich",
        # Immer im Folgejahr, aber mit fünf Monaten Streuung (Juni bis
        # November, fünf Jahrgänge gemessen). Der November ist der späteste
        # gemessene Fall und deshalb die Schwelle: Früher ist nie ein Problem,
        # zu früh gemeldet dagegen schon.
        erwarteter_monat=11,
        versatz=1,
        herkunft="lsn",
        nachschub="Download vom Landesamt für Statistik, "
                  "scripts/ingest_staedtevergleich.py --realsteuer",
        bestand=_bestand_lsn_realsteuern,
    ),
):
    QUELLEN[_q.key] = _q

#: Reihenfolge für Oberfläche und Protokoll — vom Groben zum Feinen.
#: Der Gesamtabschluss steht am Ende: Er ist die weiteste Sicht, kommt aber
#: zeitlich zuletzt und beantwortet eine andere Frage als die davor.
#: Der Gesamtergebnishaushalt steht direkt hinter dem Haushaltsplan — beide
#: beantworten „was ist geplant?", nur in verschiedener Auflösung. Ganz hinten
#: der Städtevergleich, denn der verlässt Oldenburg.
#:
#: Beim Städtevergleich zwei Zeilen und nicht eine, obwohl beide aus derselben
#: Tabelle kommen: Die Jahresangaben bedeuten Verschiedenes — beim
#: Finanzausgleich ist es das **Ausgleichsjahr** (läuft dem Kalender voraus),
#: beim Realsteuervergleich das **Berichtsjahr** (hinkt ihm nach).
#: Zusammengelegt ergäbe das eine Spanne „2023–2026", in der zwei verschiedene
#: Dinge dasselbe zu meinen scheinen — genau die Verwechslung, gegen die die
#: eigene Tabelle des Städtevergleichs angelegt wurde
#: (s. Kopf von ``council/staedtevergleich``).
REIHENFOLGE = ("haushaltsplan", "ergebnishaushalt", "jahresabschluss",
               "teilhaushalt", "rpa_fundstelle", "pruefungsfeststellungen",
               "konzernabschluss", "lsn_steuerkraft", "lsn_realsteuern")

#: Die Stelle hinter einer Herkunft, im Klartext. Sie steht in der Fußzeile des
#: Datenstands („Nicht dabei: … — die Zahlen holen wir bei …") und muss deshalb
#: aus den Daten kommen: Der Satz nannte bis 08/2026 pauschal das „Portal der
#: Stadt" und wurde mit der ersten Schicht einer Landesbehörde falsch.
STELLEN = {
    "ris": "Ratsinformationssystem",
    "stadt": "Portal der Stadt",
    "lsn": "Landesamt für Statistik Niedersachsen",
}


def datenstand(store: CouncilStore, heute: date | None = None) -> list[dict]:
    """Was für welchen Jahrgang vorliegt — und was als Nächstes erwartet wird.

    Eine Zeile je Datenart mit den vorhandenen Jahrgängen, den Lücken
    dazwischen, dem nächsten erwarteten Jahrgang und der Angabe, ob er
    überfällig ist. Beantwortet die Leserfrage „warum steht hier 2024 und
    nicht 2025?" an einer Stelle, statt sie auf jeder Unterseite von
    ``/haushalt`` zu wiederholen.

    ``teilweise`` ist der ehrliche Teil davon: Ein Jahrgang, von dem nur drei
    von neun Teilhaushalten gelesen sind, steht sonst in derselben
    Jahresspanne wie ein vollständiger und sieht aus wie einer. Gemessen wird
    an der bestbelegten Jahrgangs-Zeile desselben Bestands — mehr wissen wir
    nicht, und weniger zu behaupten wäre falsche Bescheidenheit."""
    heute = heute or date.today()
    zeilen = []
    for key in REIHENFOLGE:
        q = QUELLEN[key]
        einheiten = q.bestand(store)
        je_jahr: dict[int, int] = {}
        for e in einheiten:
            je_jahr[e[0]] = je_jahr.get(e[0], 0) + 1
        jahre = sorted(je_jahr)
        voll = max(je_jahr.values()) if je_jahr else 0
        teilweise = [j for j in jahre if je_jahr[j] < voll]
        neuester = q.neuester_erwarteter(heute)
        luecken = ([j for j in range(jahre[0], jahre[-1]) if j not in jahre]
                   if jahre else [])
        # Was seit dem jüngsten vorhandenen Jahrgang fehlt — historische
        # Lücken stehen getrennt daneben, sie sind eine andere Geschichte.
        offen = [j for j in range(((jahre[-1] + 1) if jahre else neuester), neuester + 1)]
        ueberfaellig = [j for j in offen if heute > q.faellig_ab(j) + KARENZ]
        naechster = (jahre[-1] + 1) if jahre else neuester
        zeilen.append({
            "key": q.key, "label": q.label, "was": q.was,
            "tabelle": q.tabelle, "herkunft": q.herkunft,
            "quelle": STELLEN.get(q.herkunft, q.herkunft),
            "automatisch": q.automatisch,
            "jahrgaenge": jahre, "luecken": luecken,
            # Je Jahrgang die Zahl der Einheiten (Teilhaushalte bzw. Ebenen) —
            # und wie viele der bestbelegte Jahrgang hat.
            "einheit": q.einheit,
            "einheiten": {str(j): n for j, n in sorted(je_jahr.items())},
            "einheiten_voll": voll if q.einheit else None,
            "teilweise": teilweise if q.einheit else [],
            "neuester": jahre[-1] if jahre else None,
            "offen": offen, "ueberfaellig": ueberfaellig,
            "naechster_jahrgang": naechster,
            "naechster_ab": q.faellig_ab(naechster).isoformat(),
            "erwarteter_monat": q.erwarteter_monat,
        })
    return zeilen


#: Monatsnamen für die Meldung — ``date.strftime('%B')`` hängt am Locale des
#: Servers und lieferte dort „September" nur zufällig.
MONATE = ("", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")
