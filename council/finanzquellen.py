"""Woher die Finanzzahlen des Haushalts-Bereichs stammen — eine Definition je
Datenart, und das Einlesen dazu.

Dreizehn Schichten tragen den Bereich. Sieben davon hängen als **Anlagen** an
Ratsvorlagen und liegen mit Volltext in ``council_anlagen``; woran man sie
dort erkennt (Label-Muster, Mindestseitenzahl, Ausschlüsse), stand bis 08/2026
verstreut in zwei Ingest-Skripten. Hier steht es einmal. ``ingest_finanz-
n_reports.py``, ``ingest_pruefberichte.py`` und der Cron ``check_finanzdaten.py``
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

Die sechs übrigen kommen **nicht** aus dem Ratsinformationssystem: der
Haushaltsplan, die Investitionen des Finanzhaushalts, der Beteiligungsbericht
und die Schuldenzeitreihe als Downloads von oldenburg.de beziehungsweise aus
dem Open-Data-Portal, dazu der Städtevergleich in zwei Reihen vom Landesamt
für Statistik Niedersachsen. Deren Takt ist an den
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

from council import (anlagenspiegel, bilanz, buergschaften, kennzahlen, ergebnishaushalt, finanzberichte,
                     herkunft, investitionsprogramm, konzernabschluss,
                     pruefberichte, stellenplan)
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
    (``budget_year``) — bei den Prüfberichten sogar ausschließlich dort, weil die
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
    das, was **ein** Dokument liefert — und das ist nicht überall ein ganzer
    Jahrgang. Wo die Einheit kleiner ist, sagt es ``einheiten_von``; zwei
    Beispiele, an denen die Regel hängt:

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

    def faellig_ab(self, budget_year: int) -> date:
        """Wann dieser Jahrgang üblicherweise im Rat liegt."""
        return date(budget_year + self.versatz, self.erwarteter_monat, 1)

    def neuester_erwarteter(self, heute: date) -> int:
        """Der jüngste Jahrgang, der heute schon vorliegen müsste."""
        budget_year = heute.year - self.versatz
        if heute < self.faellig_ab(budget_year):
            budget_year -= 1
        return budget_year

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
            r["budget_year"] = next(iter(sorted(e[0] for e in r["einheiten"])), None)
        return rows

    def dokumente(self, store: CouncilStore, spalten: str) -> list[dict]:
        """Die Dokumente dieser Datenart — mit **ganzem** Volltext, anders als
        bei ``kandidaten``.

        Der Griff an ``store._conn`` vorbei stand bis 08/2026 achtmal
        gleichlautend in den ``lies_*``-Funktionen, jedes Mal mit eigenem
        ``noqa``. Einmal genügt: Wer an der Kandidatenabfrage etwas ändert,
        ändert sie hier, und alle Datenarten erben es.
        """
        sql, werte = self.erkennung.abfrage(spalten)
        return [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001

    def vorhandene(self, store: CouncilStore, nur_fehlende: bool) -> set[tuple]:
        """Welche Einheiten ein Lauf überspringen darf — leer, wenn er alles
        neu lesen soll.

        Sieht nach einem Einzeiler aus, schließt aber eine Lücke: Die
        ``lies_*``-Funktionen riefen ihre ``_bestand_*``-Funktion bis 08/2026
        **direkt** auf, an ihrem eigenen Registry-Eintrag vorbei. Damit gab es
        auf die Frage „was habe ich schon?" zwei Antworten — die des Crons
        (über ``bestand``) und die des Einlesens —, und ein Wechsel an einer
        Stelle wäre an der anderen still unbemerkt geblieben. Genau die
        Doppelung, gegen die es diese Registry gibt (s. Modulkopf).
        """
        return self.bestand(store) if nur_fehlende else set()

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


#: Die vier Ebenen eines Jahresabschlusses: die Ergebnisrechnung der
#: Kernverwaltung, dieselbe Rechnung je Teilhaushalt, die Finanzrechnung und
#: die Bilanz — was gebucht wurde, wo es gebucht wurde, was tatsächlich
#: geflossen ist, und was am Stichtag da ist.
#:
#: Die **Erläuterungstexte** des Anhangs sind bewusst keine eigenen Einheiten,
#: weder die zu den Abweichungen (6.3.1) noch die zu den Bilanzpositionen
#: (6.2.1–6.2.9): Ob ein Jahrgang welche hat, entscheidet der Bericht (und
#: die Zuordnungsprobe), nicht wir — als Einheit geführt gälte jeder Jahrgang
#: ohne Erläuterungen für immer als unvollständig und würde alle zwei Wochen
#: neu geparst. Sie werden trotzdem nachgetragen, sobald der Jahrgang aus
#: einem anderen Grund noch einmal gelesen wird.
EBENEN = ("gesamt", "teilhaushalte", "kasse", "bilanz")


def _einheiten_jahresabschluss(row: dict) -> set[tuple]:
    year = _jahr_aus_label(row)
    return {(year, e) for e in EBENEN} if year else set()


def _einheiten_schlussbericht(row: dict) -> set[tuple]:
    treffer = finanzberichte.pruefbericht_aus_anlage(row.get("label"), row.get("kopf"))
    return {(treffer["year"],)} if treffer else set()


def _einheiten_feststellungen(row: dict) -> set[tuple]:
    year = pruefberichte.erkenne_jahrgang(row.get("kopf") or "")
    return {(year,)} if year else set()


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
    year = teilhaushalt_jahrgang(row.get("kopf"))
    nr = teilhaushalt_nummer(row.get("label"))
    return {(year, nr)} if year and nr else set()


# --- Was schon im Bestand steht ---------------------------------------------

def _jahre(store: CouncilStore, sql: str) -> list:
    try:
        return store._conn.execute(sql).fetchall()  # noqa: SLF001
    except sqlite3.OperationalError:
        return []


def _bestand_jahresabschluss(store: CouncilStore) -> set[tuple]:
    """Je Jahrgang bis zu vier Einheiten: Gesamtrechnung, Teilhaushalte,
    Finanzrechnung, Bilanz.

    ``ergebnisrechnung_jahre()`` genügt hier **nicht** — es liefert „irgendeine
    Zeile" und hielte einen Jahrgang, dessen Teilhaushalts-Ebene an der
    Summenprobe gescheitert ist, für fertig."""
    aus = {(r[0], "gesamt") for r in _jahre(
        store, "SELECT DISTINCT year FROM council_ergebnisrechnung WHERE sub_budget_no IS NULL")}
    aus |= {(r[0], "teilhaushalte") for r in _jahre(
        store, "SELECT DISTINCT year FROM council_ergebnisrechnung WHERE sub_budget_no IS NOT NULL")}
    aus |= {(r[0], "kasse") for r in _jahre(
        store, "SELECT DISTINCT year FROM council_finanzrechnung")}
    # Die Bilanz zählt für das Jahr **des Dokuments**, nicht für den
    # Stichtag: Der älteste Stichtag (2016) stammt aus der Vorjahresspalte des
    # Abschlusses 2017 und hat kein eigenes Dokument. Stünde er hier als
    # eigene Einheit, suchte der Cron ewig nach einem Jahresabschluss 2016.
    aus |= {(r[0], "bilanz") for r in _jahre(
        store, "SELECT DISTINCT year FROM council_bilanz WHERE year > "
               "(SELECT MIN(year) FROM council_bilanz)")}
    return aus


def _bestand_produkte(store: CouncilStore) -> set[tuple]:
    """Je Jahrgang eine Einheit **pro Teilhaushalt** — die Granularität, in der
    die Dokumente hereinkommen."""
    return {(r[0], r[1]) for r in _jahre(
        store, "SELECT DISTINCT year, sub_budget_no FROM council_produkte WHERE sub_budget_no IS NOT NULL")}


def _einheiten_kennzahlen(row: dict) -> set[tuple]:
    """Ein Bericht = eine Einheit, auch wenn er fünf Jahrgänge zeigt.

    Gezählt wird das Dokument, nicht sein Inhalt: Sonst gälte der Bericht 2024
    als Beleg für 2020, und der ausstehende Bericht 2025 fiele nicht auf, weil
    „2020–2024 ist ja da".
    """
    m = re.search(r"(20\d\d)", row.get("label") or "")
    return {(int(m.group(1)),)} if m else set()


def _bestand_kennzahlen(store: CouncilStore) -> set[tuple]:
    return {(z["report_year"],) for z in store.get_kennzahlen()}


def _bestand_schlussberichte(store: CouncilStore) -> set[tuple]:
    return {(q["year"],) for q in store.get_pruefbericht_quellen()}


def _bestand_feststellungen(store: CouncilStore) -> set[tuple]:
    return {(j,) for j in store.pruefbericht_jahre()}


def _bestand_haushaltsplan(store: CouncilStore) -> set[tuple]:
    return {(j,) for j in store.haushalt_years()}


def _einheiten_ergebnishaushalt(row: dict) -> set[tuple]:
    """Der Jahrgang kommt aus dem **Tabellenkopf**, nicht aus dem Label.

    Vier der acht Dokumente heißen schlicht „005 Gesamtergebnishaushalt" und
    tragen gar keine Jahreszahl; die anderen vier tragen sie, aber an
    verschiedenen Stellen. Der Kopf dagegen sagt es immer und sagt es genau:
    Die dritte Spalte ist das Planjahr (s. ``ergebnishaushalt.budget_year``)."""
    year = ergebnishaushalt.budget_year(row.get("kopf"))
    return {(year,)} if year else set()


def _bestand_ergebnishaushalt(store: CouncilStore) -> set[tuple]:
    """Ein Dokument trägt einen ganzen Plan-Jahrgang — Einheit = Jahrgang.

    Gezählt wird nach ``plan_budget_year``, nicht nach ``year``: Sonst hielte ein
    Finanzplanungsjahr, das ein älterer Plan nebenbei mitliefert, den
    zugehörigen Haushalt für schon eingelesen."""
    return {(j,) for j in store.ergebnishaushalt_jahrgaenge()}


def _einheiten_stellenplan(row: dict) -> set[tuple]:
    """Je Dokument zwei Einheiten: Teil A und Teil B.

    Beide werden angemeldet, obwohl der Kopf nur Teil A sehen kann (Teil B
    beginnt auf Seite 5, der Kandidaten-Ausschnitt endet bei 4.000 Zeichen).
    Das ist Absicht: Der Stellenplan **hat** zwei Teile, und ein Jahrgang, bei
    dem nur einer hereinkommt, ist unvollständig — genau das soll die
    Buchführung sagen. Im Jahrgang 2026 ist das der Fall, weil Teil B im PDF
    keine Zeichenzuordnung mitbringt; der Cron meldet ihn einmal als offen und
    schweigt danach (``_schon_gemeldet``)."""
    year = stellenplan.budget_year(row.get("kopf"))
    return {(year, t) for t in sorted(stellenplan.TEIL_SPALTEN)} if year else set()


def _bestand_stellenplan(store: CouncilStore) -> set[tuple]:
    return store.stellenplan_einheiten()


def _bestand_investitionen(store: CouncilStore) -> set[tuple]:
    """Die Haushaltsjahre, für die Investitionen vorliegen.

    Eine Portal-Datei trägt einen ganzen Jahrgang — die Einheit ist der
    Jahrgang, und „da" heißt hier tatsächlich „fertig". Gezählt wird an der
    Summenzeile (``store.investitionen_jahre``): Sie steht nur in der Tabelle,
    wenn die Rechenprobe aufging."""
    return {(j,) for j in store.investitionen_jahre()}


def _einheiten_investitionsprogramm(row: dict) -> set[tuple]:
    """Ein Dokument trägt einen ganzen Jahrgang — die Einheit ist der Jahrgang.

    Der Jahrgang kommt aus dem Textkopf, nicht aus dem Label: Vier der acht
    Anlagen heißen nur „004 Investitionsprogramm" (s.
    ``investitionsprogramm.budget_year``)."""
    year = investitionsprogramm.budget_year(row.get("kopf"))
    return {(year,)} if year else set()


def _bestand_investitionsprogramm(store: CouncilStore) -> set[tuple]:
    """Gezählt an der ``gesamt``-Zeile: Sie steht nur in der Tabelle, wenn alle
    drei Proben des Dokuments aufgingen."""
    return {(j,) for j in store.investitionsprogramm_jahre()}


def _bestand_konzernabschluss(store: CouncilStore) -> set[tuple]:
    """Ein Dokument trägt einen ganzen Jahrgang — die Einheit ist der Jahrgang.

    Gemessen wird an den Posten, nicht an der Trägeraufstellung: Die Posten
    sind der Kern (ohne sie kommt der Jahrgang gar nicht herein), die
    Trägeraufstellung kann einzeln an ihrer Probe scheitern, ohne dass der
    Jahrgang deswegen unvollständig wäre — 2018 ist genau dieser Fall."""
    return {(j,) for j in store.konzern_jahre()}


def _einheiten_konzernabschluss(row: dict) -> set[tuple]:
    year = konzernabschluss.budget_year(row.get("kopf"))
    return {(year,)} if year else set()


def _bestand_gebuehren(store: CouncilStore) -> set[tuple]:
    """Die Jahrgänge, für die eine Gebührenbedarfsberechnung im Bestand steht.

    Einheit ist das JAHR und nicht das Paar (Jahr, Bereich): Die drei Bereiche
    stehen in derselben Anlage und kommen gemeinsam oder gar nicht. Nähme man
    das Paar, meldete die Ampel für einen Jahrgang, dessen Abfallsammlung an
    einer Probe scheitert, dauerhaft zwei fehlende Bereiche — und eine Ampel,
    die dauerhaft rot steht, wird überlesen.
    """
    try:
        return {(int(j),) for (j,) in store._conn.execute(  # noqa: SLF001
            "SELECT DISTINCT year FROM council_gebuehren")}
    except Exception:  # noqa: BLE001 — Tabelle kann fehlen
        return set()


def _bestand_haushaltssatzung(store: CouncilStore) -> set[tuple]:
    """Die Haushaltsjahre, für die eine Satzung im Bestand steht.

    Einheit ist das Jahr. Nachträge zählen bewusst NICHT mit: Sie sind kein
    eigener Jahrgang, sondern eine Änderung an einem vorhandenen — und ein
    Jahr ohne Nachtrag ist der Normalfall, nicht eine Lücke.
    """
    try:
        return {(int(j),) for (j,) in store._conn.execute(  # noqa: SLF001
            "SELECT DISTINCT year FROM council_haushaltssatzung WHERE supplement = 0")}
    except Exception:  # noqa: BLE001 — Tabelle kann fehlen
        return set()


def _bestand_wirtschaftsplan(store: CouncilStore) -> set[tuple]:
    """Die Haushaltsjahre, für die ein Wirtschaftsplan im Bestand steht.

    Die Einheit ist das **Jahr**, nicht das Paar (Jahr, Betrieb). Das ist eine
    bewusste Entscheidung und keine Vereinfachung: Gelesen wird bisher nur der
    Eigenbetrieb Gebäudewirtschaft und Hochbau, weil als einziger er seine
    Eckwerte in den Beschlusstext schreibt. Nähme man das Paar, meldete der
    Cron ab sofort jeden Monat vier fehlende Betriebe — für etwas, das wir
    nicht gebaut haben und dessen Fehlen an anderer Stelle dokumentiert steht
    (haushalt.md, „Der Haushalt neben dem Haushalt"). Eine Ampel, die
    dauerhaft rot steht, wird überlesen.
    """
    try:
        return {(r[0],) for r in store._conn.execute(  # noqa: SLF001
            "SELECT DISTINCT year FROM council_wirtschaftsplaene")}
    except sqlite3.OperationalError:
        return set()


def _bestand_schulden(store: CouncilStore) -> set[tuple]:
    """Die Jahrgänge der Schuldenzeitreihe.

    Ein Dokument trägt die ganze Reihe von 1995 bis heute — die Einheit ist
    trotzdem der Jahrgang und nicht das Dokument: Die Frage der Seite ist „bis
    wann reichen die Zahlen?", und die beantwortet der jüngste Jahrgang. Dass
    ein Jahrgang fehlen kann, ohne dass die Lieferung fehlt, ist hier kein
    Sonderfall, sondern eingeplant (s. ``council/schulden.py``)."""
    return {(r[0],) for r in _jahre(
        store, "SELECT DISTINCT year FROM council_schulden")}
def _bestand_beteiligungsbericht(store: CouncilStore) -> set[tuple]:
    """Die **Berichts**jahrgänge, die eingelesen sind.

    Gezählt wird nach dem Bericht, nicht nach den Bezugsjahren seiner
    Kennzahlen: Ein Bericht führt vier bis fünf Jahre mit, und wer die als
    Jahrgänge zählte, hielte den Bestand nach einem einzigen Dokument für bis
    2017 zurückreichend — und meldete nie wieder, dass ein Bericht fehlt."""
    return {(j,) for j in store.beteiligungsbericht_jahre()}


def _bestand_lsn_steuerkraft(store: CouncilStore) -> set[tuple]:
    """Die Ausgleichsjahre, für die eine Steuerkraftmesszahl vorliegt.

    Eine Datei trägt genau **ein** Ausgleichsjahr in den Bestand: Das zweite,
    das sie mitführt, ist die Rechenprobe (``probe_ueberlappung``) und wird
    nicht gespeichert. Die Einheit ist deshalb der Jahrgang, und „da" heißt
    hier tatsächlich „fertig"."""
    return {(r[0],) for r in _jahre(
        store, "SELECT DISTINCT year FROM council_staedtevergleich "
               "WHERE series = 'steuerkraft'")}


def _bestand_lsn_realsteuern(store: CouncilStore) -> set[tuple]:
    """Die Berichtsjahre des Realsteuervergleichs.

    Ein Bericht füllt **drei** Jahrgänge: Hebesätze und Ist-Aufkommen für sein
    Berichtsjahr, die Steuereinnahmekraft für dieses und die zwei davor
    (``zeilen_realsteuern`` sagt es selbst: „Jeder Jahreswert trägt SEIN
    Jahr"). Gezählt wird trotzdem je Jahr und nicht je Bericht — die Frage der
    Seite ist „bis wann reichen die Zahlen?", und darauf antwortet das Jahr an
    der Zahl, nicht das Deckblatt, auf dem sie stand."""
    return {(r[0],) for r in _jahre(
        store, "SELECT DISTINCT year FROM council_staedtevergleich "
               "WHERE series = 'realsteuern'")}


def _bestand_lsn_gewerbesteuer(store: CouncilStore) -> set[tuple]:
    """Die Erhebungsjahre der Gewerbesteuerstatistik.

    Gezählt wird das **Erhebungsjahr der Veranlagung**, nicht das Jahr, in dem
    der Bericht erschien — dazwischen liegen rund fünf Jahre. Die Frage der
    Seite ist „bis wann reichen die Zahlen?", und darauf antwortet nur das
    erste."""
    return {(r[0],) for r in _jahre(
        store, "SELECT DISTINCT year FROM council_gewerbesteuerstatistik")}


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
STECKBRIEF = ("short_description", "legal_basis", "controllability",
              "scope", "target_group")

#: Die Produkt-Felder, die aus dem Dokument kommen — alles, was
#: ``save_produkte`` aus der gelesenen Zeile schreibt, ohne Herkunft und
#: Zeitstempel. Grundlage von :func:`_produkt_signatur`.
PRODUKT_FELDER = ("product_no", "product_name", "sub_budget_no", "sub_budget_name", "office",
                  "revenues", "expenses", "result",
                  "controllability_raw") + STECKBRIEF

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
                 for z in sorted(zeilen, key=lambda z: z["product_no"]))


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
    quelle = QUELLEN["jahresabschluss"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)

    gelesen: dict[int, dict] = {}
    uebersprungen = vorzeichen_repariert = 0
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        year = int(m.group(1))
        text = r["raw_text"] or ""
        posten = finanzberichte.parse_ergebnisrechnung(text, year)
        # Ohne beide Summenzeilen ist der Jahrgang für „Plan gegen Ist" wertlos.
        if {p_["nr"] for p_ in posten} < {12, 20}:
            p.warnen(f"  {year}: nur {len(posten)} Posten, keine Summenzeilen — übersprungen")
            uebersprungen += 1
            continue
        # Innerhalb der Tabelle: 12 − 20 = 21, in Plan und Ist.
        ok, warum = finanzberichte.strukturprobe(posten)
        if not ok:
            p.warnen(f"  {year}: Strukturprobe gerissen ({warum}) — übersprungen")
            uebersprungen += 1
            continue
        repariert = sum(1 for x in posten if x.get("vorzeichen_repariert"))
        if repariert:
            # Zählen und melden: Wird das häufiger, stimmt etwas anderes nicht.
            p.warnen(f"  {year}: {repariert} Zeile(n) mit fehlendem Minuszeichen im Dokument — "
                     f"Betrag passte auf den Cent, Vorzeichen ergänzt")
            vorzeichen_repariert += repariert
        # Die Kassensicht aus demselben Dokument, dreißig Seiten weiter. Sie
        # hängt an ihrer eigenen Kaskade und teilt das Schicksal der
        # Ergebnisrechnung ausdrücklich NICHT: Reißt sie, fehlt die
        # Finanzrechnung des Jahrgangs, und „geplant gegen tatsächlich" steht
        # trotzdem auf der Seite.
        kasse_roh = finanzberichte.parse_finanzrechnung(text, year)
        kasse, kasse_fehler, kasse_hinweise = finanzberichte.finanzprobe(kasse_roh)
        for x in kasse_fehler:
            p.warnen(f"  {year}: Finanzrechnung verworfen — {x}")
        for x in kasse_hinweise:
            p.sagen(f"  {year}: Finanzrechnung — {x}")

        # Die Vermögensseite, dreißig Seiten davor (Abschnitt 2.1). Sie hängt
        # wie die Kasse an ihrer eigenen Probe und teilt das Schicksal der
        # Ergebnisrechnung nicht: Reißt der Bilanzausgleich, fehlt die Bilanz
        # dieses Jahrgangs, und alles andere steht trotzdem auf der Seite.
        bil, bil_fehler, bil_hinweise = bilanz.bilanzprobe(
            bilanz.parse_bilanz(text, year))
        for x in bil_fehler:
            p.warnen(f"  {year}: Bilanz verworfen — {x}")
        for x in bil_hinweise:
            p.sagen(f"  {year}: Bilanz — {x}")

        # Der Anhang dazu: 6.2.1–6.2.9, ein Abschnitt je Hauptposten. Ohne
        # bestandene Zuordnungsprobe gar nichts — ein Erläuterungstext unter
        # der falschen Bilanzposition wäre eine Falschaussage.
        erl = bilanz.parse_erlaeuterungen(text, year)
        erl_ok, erl_warum = bilanz.erlaeuterungsprobe(erl)
        if not erl_ok:
            p.warnen(f"  {year}: Bilanz-Erläuterungen verworfen — {erl_warum}")
            erl = []

        gelesen[year] = {"posten": posten, "text": text, "kasse": kasse,
                         "bilanz": bil, "erlaeuterungen": erl,
                         "erlaeuterungsprobe": erl_warum,
                         "label": r["label"], "url": r["url"],
                         "document_id": r["document_id"]}

    # Vorjahres-Kette: Das Ist eines Jahres steht im Folgejahrgang noch einmal.
    # Ein gerissenes Glied verrät nicht, welche Seite falsch ist — also fallen
    # beide raus. In der Praxis schließen alle Glieder.
    kette = finanzberichte.vorjahreskette({j: v["posten"] for j, v in gelesen.items()})
    verdaechtig: set[int] = set()
    for year, folge, warum in kette:
        p.warnen(f"  Vorjahres-Kette {year}→{folge} gerissen: {warum} — beide Jahrgänge "
                 f"werden nicht gespeichert")
        verdaechtig |= {year, folge}
    glieder = sum(1 for j in gelesen if j + 1 in gelesen) * 2

    # Dasselbe für die Kasse: Der Endbestand eines Jahres steht im Folgejahr
    # als Anfangsbestand. Ein gerissenes Glied kostet hier nur die
    # Finanzrechnung der beiden Jahrgänge, nicht ihre Ergebnisrechnung — es
    # sind verschiedene Abschnitte hinter verschiedenen Proben.
    kassenkette = finanzberichte.kassenkette({j: v["kasse"] for j, v in gelesen.items()})
    kasse_verdaechtig: set[int] = set()
    for year, folge, warum in kassenkette:
        p.warnen(f"  Kassen-Kette {year}→{folge} gerissen: {warum} — die "
                 f"Finanzrechnung beider Jahrgänge wird nicht gespeichert")
        kasse_verdaechtig |= {year, folge}
    kassenglieder = sum(1 for j in gelesen if j + 1 in gelesen
                        and gelesen[j]["kasse"] and gelesen[j + 1]["kasse"])

    # Und dasselbe für die Bilanz, mit zwei Proben über Dokumentgrenzen:
    #
    # 1. Die Vorjahres-Kette: Jede Bilanz führt zwei Stichtage nebeneinander,
    #    der ältere muss der aktuelle des Vorjahrgangs sein — je Hauptposten.
    # 2. Die Kreuzprobe gegen die Finanzrechnung: „Liquide Mittel" der Bilanz
    #    ist derselbe Betrag wie „Endbestand an Zahlungsmitteln" der
    #    Finanzrechnung. Die stärkste Probe des Bereichs, weil hier zwei
    #    getrennt geschriebene Parser dieselbe Zahl liefern müssen.
    #
    # Der Anfangsbestand steht mit in der Nachschlagetabelle: Er ist der
    # Endbestand des Vorjahres und deckt damit den ältesten Stichtag ab, der
    # aus der Vorjahresspalte stammt und selbst keine Finanzrechnung hat.
    bilanzen = {j: v["bilanz"] for j, v in gelesen.items() if v["bilanz"]}
    bil_kette = bilanz.vorjahreskette(bilanzen)
    bil_verdaechtig: set[int] = set()
    for year, folge, warum in bil_kette:
        p.warnen(f"  Bilanz-Vorjahreskette {year}→{folge} gerissen: {warum} — die "
                 f"Bilanz beider Jahrgänge wird nicht gespeichert")
        bil_verdaechtig |= {year, folge}
    bilanzglieder = sum(1 for j in bilanzen if j + 1 in bilanzen)

    endbestaende: dict[int, float] = {}
    for year, v in gelesen.items():
        for z in v["kasse"] or ():
            if z.get("role") == "closing_balance" and z.get("result") is not None:
                endbestaende[year] = z["result"]
            elif z.get("role") == "opening_balance" and z.get("result") is not None:
                endbestaende.setdefault(year - 1, z["result"])
    for year, warum in bilanz.kassenprobe(bilanzen, endbestaende):
        p.warnen(f"  Bilanz {year}: Kreuzprobe gegen die Finanzrechnung gerissen "
                 f"({warum}) — Bilanz wird nicht gespeichert")
        bil_verdaechtig.add(year)
    bil_kreuzproben = sum(1 for j in bilanzen if j in endbestaende)

    neu: list[int] = []
    neue_einheiten: set[tuple] = set()
    mit_thh = verworfen = gruende_gesamt = geschuetzt = mit_kasse = 0
    mit_bilanz = mit_erlaeuterungen = 0
    for year in sorted(gelesen):
        if year in verdaechtig:
            uebersprungen += 1
            continue
        braucht_gesamt = (year, "gesamt") not in vorhanden
        braucht_thh = (year, "teilhaushalte") not in vorhanden
        braucht_kasse = (year, "kasse") not in vorhanden
        braucht_bilanz = (year, "bilanz") not in vorhanden
        if not (braucht_gesamt or braucht_thh or braucht_kasse or braucht_bilanz):
            continue  # alle Ebenen stehen — der Job fasst Bestand nicht an
        v = gelesen[year]
        posten, label, url = v["posten"], v["label"], v["url"]

        # Woher diese Zeilen kommen — je Ebene eine eigene Angabe. Beide
        # stehen im selben Dokument, aber an verschiedenen Stellen und hinter
        # verschiedenen Proben; eine gemeinsame Herkunft wäre für beide
        # ungenau. Die Vorjahres-Kette wird nur genannt, wo sie greift: Ohne
        # gelesenen Nachbarjahrgang gibt es kein Glied, das schließen könnte.
        anker = dict(art="ris", document_id=v["document_id"], label=label,
                     url=url, stand=f"Jahresabschluss {year}")
        proben_gesamt = ["strukturprobe"]
        if year - 1 in gelesen or year + 1 in gelesen:
            proben_gesamt.append("vorjahreskette")

        # Ein Jahrgang, eine Transaktion: Gesamtrechnung, Teilhaushalte und
        # Erläuterungen stehen zusammen in der Datenbank oder gar nicht.
        with store.transaktion():
            if braucht_gesamt:
                # Ersetzen heißt löschen und neu schreiben — nur gegen ein
                # Ergebnis, das den vorhandenen Stand trägt (s. bestandsschutz).
                alt = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnisrechnung "
                                     "WHERE year = ? AND sub_budget_no IS NULL", (year,))
                if not bestandsschutz(p, f"{year} Ergebnisrechnung", alt,
                                      len(posten), schuetzen):
                    geschuetzt += 1
                    uebersprungen += 1
                    continue
                store.save_ergebnisrechnung(year, posten, herkunft.Herkunft(
                    probe=proben_gesamt,
                    citation="Ergebnisrechnung der Kernverwaltung, Posten 1–24",
                    **anker))
                neue_einheiten.add((year, "gesamt"))
                e = next(x for x in posten if x["nr"] == 12)
                a = next(x for x in posten if x["nr"] == 20)
                arten = sorted({x["plan_art"] for x in posten})
                p.sagen(f"  {year}: {len(posten)} Posten · Erträge {e['plan']/1e6:.1f} → "
                        f"{e['result']/1e6:.1f} · Aufwendungen {a['plan']/1e6:.1f} → "
                        f"{a['result']/1e6:.1f} · Bezug {'/'.join(arten)}")
                if a["plan"] != a["ansatz"] or e["plan"] != e["ansatz"]:
                    p.sagen(f"      ursprünglicher Ansatz: Erträge {e['ansatz']/1e6:.1f} · "
                            f"Aufwendungen {a['ansatz']/1e6:.1f}")
            else:
                p.sagen(f"  {year}: Gesamtrechnung steht bereits — nur die fehlende "
                        f"Teilhaushalts-Ebene wird nachgezogen")

            # Zweite Ebene: dieselbe Rechnung je Teilhaushalt. Sie wird nur
            # übernommen, wenn ihre Summe zur Gesamtrechnung passt — in Plan
            # UND Ist. Sonst wurde für einen Teilhaushalt die falsche (in sich
            # stimmige) Tabelle gelesen, was zeilenweise nicht auffällt.
            if braucht_thh:
                sub_budget = finanzberichte.parse_teilergebnisrechnungen(v["text"], year)
                alt_thh = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnisrechnung "
                                         "WHERE year = ? AND sub_budget_no IS NOT NULL", (year,))
                if not bestandsschutz(p, f"{year} Teilhaushalte", alt_thh,
                                      sum(len(x["posten"]) for x in sub_budget), schuetzen):
                    geschuetzt += 1 if alt_thh else 0
                else:
                    passt, deviation = finanzberichte.summenprobe(sub_budget, posten)
                    if not passt:
                        p.warnen(f"    Teilhaushalte verworfen: Summe weicht um "
                                 f"{deviation*100:.1f} % von der Gesamtrechnung ab")
                        verworfen += 1
                    else:
                        for x in sub_budget:
                            store.save_ergebnisrechnung(
                                year, x["posten"], herkunft.Herkunft(
                                    probe="summenprobe",
                                    citation=f"Teil-Ergebnisrechnung THH"
                                               f"{x['sub_budget_no']:02d} — {x['sub_budget_name']}",
                                    probe_result=f"{deviation * 100:.2f} % "
                                                   f"Abweichung zur Gesamtrechnung",
                                    **anker),
                                sub_budget_no=x["sub_budget_no"], sub_budget_name=x["sub_budget_name"])
                        p.sagen(f"    + {len(sub_budget)} Teilhaushalte "
                                f"(Summenprobe {deviation*100:.2f} % Abweichung)")
                        neue_einheiten.add((year, "teilhaushalte"))
                        mit_thh += 1

            # Dritte Ebene: die Finanzrechnung. Was `finanzprobe` hier liefert,
            # ist bereits durchgerechnet — leer heißt „Kaskade gerissen", und
            # dann steht für diesen Jahrgang eben keine Kassensicht auf der
            # Seite. Ein Beleg nennt jede Probe, die den Jahrgang wirklich
            # trägt: die Ermächtigungsspalte nur, wo sie überlebt hat, die
            # Kassen-Kette nur, wo es einen Nachbarjahrgang zum Schließen gibt.
            if braucht_kasse and v["kasse"] and year not in kasse_verdaechtig:
                alt_kasse = _anzahl(store, "SELECT COUNT(*) FROM council_finanzrechnung "
                                           "WHERE year = ?", (year,))
                if not bestandsschutz(p, f"{year} Finanzrechnung", alt_kasse,
                                      len(v["kasse"]), schuetzen):
                    geschuetzt += 1
                else:
                    roles = {x["role"] for x in v["kasse"] if x.get("role")}
                    probes = ["finanzkaskade"]
                    if any(x.get("authorization") is not None for x in v["kasse"]):
                        probes.append("finanz_ermaechtigungen")
                    if "closing_balance" in roles:
                        probes.append("finanz_bestandskette")
                    if any((year + s) in gelesen and gelesen[year + s]["kasse"]
                           for s in (-1, 1)):
                        probes.append("kassenkette")
                    store.save_finanzrechnung(year, v["kasse"], herkunft.Herkunft(
                        probe=probes,
                        citation="Abschnitt 4.1 — Finanzrechnung der "
                                   "Kernverwaltung (Ein- und Auszahlungen)",
                        **anker))
                    neue_einheiten.add((year, "kasse"))
                    mit_kasse += 1
                    balance = next((x["result"] for x in v["kasse"]
                                  if x["role"] == "cash_surplus"), None)
                    p.sagen(f"    + Finanzrechnung: {len(v['kasse'])} Zeilen · "
                            f"Finanzmittelsaldo {balance/1e6:+.1f} Mio. €")

            # Vierte Ebene: die Bilanz (Abschnitt 2.1) und die Erläuterungen
            # des Anhangs dazu (6.2.1–6.2.9). Was `bilanzprobe` liefert, ist
            # bereits ausgeglichen; leer heißt „Aktiva ≠ Passiva", und dann
            # steht für diesen Stichtag eben keine Vermögensseite auf der
            # Seite. Genannt wird jede Probe, die den Jahrgang wirklich trägt.
            if braucht_bilanz and v["bilanz"] and year not in bil_verdaechtig:
                bil = v["bilanz"]
                alt_bil = _anzahl(store, "SELECT COUNT(*) FROM council_bilanz "
                                         "WHERE year = ?", (year,))
                if not bestandsschutz(p, f"{year} Bilanz", alt_bil,
                                      len(bil["posten"]), schuetzen):
                    geschuetzt += 1
                else:
                    probes = list(bil["probes"])
                    if any((year + s) in bilanzen for s in (-1, 1)):
                        probes.append("bilanz_vorjahreskette")
                    if year in endbestaende:
                        probes.append("bilanz_kassenprobe")
                    summe_de = f"{bil['bilanzsumme'] / 1e6:.2f}".replace(".", ",")
                    store.save_bilanz(year, bil["posten"], herkunft.Herkunft(
                        probe=probes,
                        citation=f"Abschnitt 2.1 — Bilanz der Stadt Oldenburg "
                                   f"zum 31.12.{year}",
                        probe_result=f"Aktiva und Passiva stimmen auf den Cent "
                                       f"überein (Bilanzsumme {summe_de} Mio. €)",
                        stand=f"31.12.{year}",
                        art="ris", document_id=v["document_id"],
                        label=label, url=url))
                    neue_einheiten.add((year, "bilanz"))
                    mit_bilanz += 1
                    werte = {x["role"]: x["wert"] for x in bil["posten"]}
                    p.sagen(f"    + Bilanz: {len(bil['posten'])} Posten · Bilanzsumme "
                            f"{bil['bilanzsumme']/1e6:.1f} Mio. € · Pensionsrückstellungen "
                            f"{werte.get('pensionen_gesamt', 0)/1e6:.1f} Mio. € "
                            f"(davon Beihilfe {werte.get('beihilferueckstellungen', 0)/1e6:.1f})")

                    # Der älteste Stichtag hat kein eigenes Dokument: 2016
                    # steht nur in der Vorjahresspalte des Abschlusses 2017.
                    # Er wird mitgenommen, wenn seine Spalte für sich
                    # ausgeglichen ist — sonst nicht. Eine eigene Einheit ist
                    # er ausdrücklich nicht (s. `_bestand_jahresabschluss`).
                    if year == min(bilanzen):
                        prior_year = year - 1
                        a = bilanz.summe(bil["posten"], bilanz.AKTIVA, "value_prior_year")
                        pa = bilanz.summe(bil["posten"], bilanz.PASSIVA, "value_prior_year")
                        if a and pa and abs(a - pa) <= bilanz.TOLERANZ:
                            vorposten = [{**x, "wert": x["value_prior_year"]}
                                         for x in bil["posten"]]
                            vorproben = ["bilanz_ausgleich"]
                            if prior_year in endbestaende:
                                vorproben.append("bilanz_kassenprobe")
                            store.save_bilanz(prior_year, vorposten, herkunft.Herkunft(
                                probe=vorproben,
                                citation=f"Abschnitt 2.1 — Bilanz zum 31.12.{year}, "
                                           f"Vorjahresspalte (Stand 31.12.{prior_year})",
                                probe_result="Aktiva und Passiva der Vorjahresspalte "
                                               "stimmen auf den Cent überein",
                                stand=f"31.12.{prior_year}",
                                art="ris", document_id=v["document_id"],
                                label=label, url=url))
                            p.sagen(f"      + Stichtag {prior_year} aus der "
                                    f"Vorjahresspalte ({a/1e6:.1f} Mio. €)")

                    if v["erlaeuterungen"]:
                        store.save_bilanz_erlaeuterungen(
                            year, v["erlaeuterungen"], herkunft.Herkunft(
                                probe="bilanz_erlaeuterung",
                                citation="Abschnitt 6.2 — Erläuterung der "
                                           "wesentlichen Bilanzpositionen",
                                probe_result=v["erlaeuterungsprobe"],
                                stand=f"Jahresabschluss {year}",
                                art="ris", document_id=v["document_id"],
                                label=label, url=url))
                        mit_erlaeuterungen += 1
                        p.sagen(f"      + {len(v['erlaeuterungen'])} Erläuterungen "
                                f"zu den Bilanzpositionen")

            # Das „Warum": Abschnitt 6.3.1 je Posten. Eintrittskarte ist der
            # Abgleich mit der Tabellenzeile — Betrag und Prozentsatz stehen in
            # der Überschrift des Blocks und müssen beide passen.
            #
            # Keine eigene Einheit (s. EBENEN), aber sie reiten mit: Wird ein
            # Jahrgang aus einem anderen Grund noch einmal gelesen, kommen die
            # Erläuterungen nach, falls sie fehlen.
            alt_gruende = _anzahl(store, "SELECT COUNT(*) FROM council_abweichungsgruende "
                                         "WHERE year = ?", (year,))
            if braucht_gesamt or not alt_gruende:
                roh = finanzberichte.parse_abweichungsgruende(v["text"], year)
                angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(roh, posten)
                for grund in abgelehnt:
                    p.warnen(f"    Erläuterung verworfen — {grund}")
                if bestandsschutz(p, f"{year} Erläuterungen", alt_gruende,
                                  len(angenommen), schuetzen):
                    store.save_abweichungsgruende(year, angenommen, herkunft.Herkunft(
                        probe="abweichungstext",
                        citation="Abschnitt 6.3.1 — Erläuterungen zu den "
                                   "Abweichungen gegenüber dem Plan",
                        probe_result=f"{len(angenommen)} von {len(roh)} "
                                       f"Erläuterungen bestanden",
                        **anker))
                    gruende_gesamt += len(angenommen)
                    p.sagen(f"    + {len(angenommen)} Erläuterungen zu Abweichungen")
                elif alt_gruende:
                    geschuetzt += 1
        if any((year, e) in neue_einheiten for e in EBENEN):
            neu.append(year)

    return {"neue_jahrgaenge": sorted(set(neu)),
            "neue_einheiten": sorted(neue_einheiten, key=repr),
            "jahre": len(gelesen) - len(verdaechtig), "uebersprungen": uebersprungen,
            "jahre_mit_teilhaushalten": mit_thh, "thh_verworfen": verworfen,
            "kettenglieder_geprueft": glieder, "kette_gerissen": len(kette),
            "vorzeichen_repariert": vorzeichen_repariert,
            "bestand_geschuetzt": geschuetzt,
            "jahre_mit_finanzrechnung": mit_kasse,
            "kassenglieder_geprueft": kassenglieder,
            "kassenkette_gerissen": len(kassenkette),
            "jahre_mit_bilanz": mit_bilanz,
            "bilanzglieder_geprueft": bilanzglieder,
            "bilanzkette_gerissen": len(bil_kette),
            "bilanz_kreuzproben": bil_kreuzproben,
            "bilanz_erlaeuterungen": mit_erlaeuterungen,
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
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)

    # Die Ist-Werte der Kernverwaltung einmal holen — Grundlage der Gegenprobe.
    ist_bestand: dict[int, dict[int, float]] = {}
    for zeile in store.get_ergebnisrechnung():
        if zeile.get("sub_budget_no") is None and zeile.get("result") is not None:
            ist_bestand.setdefault(zeile["year"], {})[zeile["nr"]] = zeile["result"]

    je_jahrgang: dict[int, dict] = {}
    geschuetzt = verworfen = 0
    gegenproben: list[dict] = []
    for r in rows:
        gelesen = ergebnishaushalt.lies(r["raw_text"] or "")
        budget_year = gelesen["budget_year"]
        if budget_year is None:
            p.warnen(f"  Dokument {r['document_id']} ({r['label']!r}): Tabellenkopf "
                     f"nicht lesbar — übersprungen")
            verworfen += 1
            continue
        if (budget_year,) in vorhanden:
            continue
        if budget_year in je_jahrgang:
            p.warnen(f"  {budget_year}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        if not gelesen["bestanden"]:
            p.warnen(f"  {budget_year}: {gelesen['nachweis']} — Dokument "
                     f"{r['document_id']}, nicht gespeichert")
            verworfen += 1
            continue

        alt = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnishaushalt "
                             "WHERE plan_budget_year = ?", (budget_year,))
        if not bestandsschutz(p, f"{budget_year} Ergebnishaushalt", alt,
                              len(gelesen["zeilen"]), schuetzen):
            geschuetzt += 1 if alt else 0
            continue

        # Gegenprobe VOR dem Speichern, damit ihr Messwert in die Herkunft
        # kommt: Der Beleg auf der Seite soll sagen, woran die Zahl hängt.
        gp = ergebnishaushalt.gegenprobe(
            gelesen["ist"], ist_bestand.get(gelesen["ist_jahr"], {}))
        if gp["plausibel"] is False:
            p.warnen(f"  {budget_year}: die Ist-Spalte {gelesen['ist_jahr']} weicht um "
                     f"{gp['groesste_abweichung']:,.2f} € ({gp['anteil']*100:.3f} % der "
                     f"Ertragssumme) vom gespeicherten Jahresabschluss ab — mehr, als "
                     f"die Stiftungen erklären. Bitte das Dokument ansehen.")
        gp["budget_year"] = budget_year
        gegenproben.append(gp)

        store.save_ergebnishaushalt(budget_year, gelesen["zeilen"], herkunft.Herkunft(
            art="ris", probe=["ergebnishaushalt_summenzeilen",
                              "ergebnishaushalt_planspalte"],
            document_id=r["document_id"], label=r["label"], url=r["url"],
            citation="Gesamtergebnishaushalt, Posten 1–24 — Spalte "
                       f"„Ansatz {budget_year}“ und die drei Finanzplanungsjahre",
            probe_result=gelesen["nachweis"],
            # NICHT „Haushaltsplan {jahrgang}" schlechthin: Die Anlage hängt
            # an der Vorlage, mit der die Verwaltung den Haushalt einbringt.
            # Was der Rat in den Beratungen ändert, steht nicht drin — bei den
            # ordentlichen Erträgen sind das 0,7 bis 13,1 Mio. € gegenüber dem
            # Ansatz, den der spätere Jahresabschluss führt. Der Beleg auf der
            # Seite muss das sagen können.
            stand=f"Haushaltsplan {budget_year}, Anlage 005 — Stand der Einbringung"))

        ansatz = [z for z in gelesen["zeilen"] if z["art"] == "ansatz"]
        e = next((z["amount"] for z in ansatz if z["nr"] == 12), None)
        a = next((z["amount"] for z in ansatz if z["nr"] == 20), None)
        fp = sorted({z["year"] for z in gelesen["zeilen"] if z["art"] == "finanzplanung"})
        je_jahrgang[budget_year] = {"zeilen": len(gelesen["zeilen"]),
                                 "ansatz": len(ansatz), "finanzplanung": fp}
        p.sagen(f"  {budget_year}: Ansatz {e/1e6:.1f} Mio. Erträge / {a/1e6:.1f} Mio. "
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
            "plan_gegenprobe": [{"budget_year": g["budget_year"], "gleich": g["gleich"],
                                 "geprueft": g["geprueft"],
                                 "share_pct": round(g["anteil"] * 100, 4)}
                                for g in gegenproben]}


def lies_investitionsprogramme(store: CouncilStore, p: Protokoll,
                               nur_fehlende: bool = False,
                               schuetzen: bool = True) -> dict:
    """Die einzelnen Vorhaben aus Anlage 004 der Haushaltspläne.

    Die Ebene unter ``council_investitionen``: nicht „Schule und Bildung:
    8,3 Mio. €", sondern die Maßnahme mit Namen. Drei Pflicht-Proben
    entscheiden, alle drei im Dokument selbst (``investitionsprogramm.pruefe``);
    reißt eine, kommt der ganze Jahrgang nicht herein.

    Gespeichert wird **nur die Gesamtinvestitionssumme** je Maßnahme, nicht die
    Jahresraten — der Textextrakt gibt sie nicht sicher her (Begründung im Kopf
    von ``council/investitionsprogramm.py``).

    Wie beim Gesamtergebnishaushalt hängt die Anlage an der
    Einbringungs-Vorlage: Es ist der **Entwurf der Verwaltung**, nicht der
    Stand nach den Beratungen. Das steht in der Herkunft (``stand``)."""
    quelle = QUELLEN["investitionsprogramm"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)

    je_jahrgang: dict[int, dict] = {}
    geschuetzt = verworfen = 0
    for r in rows:
        year = investitionsprogramm.budget_year((r["raw_text"] or "")[:4000])
        if year is None:
            p.warnen(f"  Dokument {r['document_id']} ({r['label']!r}): kein "
                     f"„Ansatz JJJJ“ im Tabellenkopf — übersprungen")
            verworfen += 1
            continue
        if (year,) in vorhanden:
            continue
        if year in je_jahrgang:
            # Zwei Dokumente je Jahrgang sind der Normalfall, nicht die
            # Ausnahme: Neben dem Verwaltungsentwurf steht regelmäßig eine
            # zweite Fassung an einer späteren Vorlage. `ordnung="document_id"`
            # sortiert nach Veröffentlichung, das erste Dokument gewinnt.
            p.sagen(f"  {year}: zweites Dokument ({r['document_id']}) — "
                    f"übersprungen, der Jahrgang steht schon")
            continue

        gelesen = investitionsprogramm.lies(r["raw_text"] or "", year)
        if not gelesen["bestanden"]:
            p.warnen(f"  {year}: {gelesen['nachweis']} — Dokument "
                     f"{r['document_id']}, nicht gespeichert")
            verworfen += 1
            continue

        n = sum(len(a["massnahmen"]) for a in gelesen["abschnitte"].values())
        alt = _anzahl(store, "SELECT COUNT(*) FROM council_investitionsmassnahmen "
                             "WHERE year = ? AND level = 'massnahme'", (year,))
        if not bestandsschutz(p, f"{year} Investitionsprogramm", alt, n, schuetzen):
            geschuetzt += 1 if alt else 0
            continue

        store.save_investitionsprogramm(year, gelesen, herkunft.Herkunft(
            art="ris", probe=["investitionsprogramm_abschnitt",
                              "investitionsprogramm_wiederholung",
                              "investitionsprogramm_kopftabelle"],
            document_id=r["document_id"], label=r["label"], url=r["url"],
            citation="Investitionsprogramm — Gesamtinvestitionsprogramm und "
                       "die Abschnitte je Teilhaushalt, Spalte "
                       "„Gesamtinvestitionssumme“",
            probe_result=gelesen["nachweis"],
            stand=f"Haushaltsplan {year}, Anlage 004 — Stand der Einbringung"))

        je_jahrgang[year] = {"massnahmen": n,
                             "teilhaushalte": len(gelesen["abschnitte"]),
                             "grand_total": gelesen["kopfsumme"]}
        p.sagen(f"  {year}: {n} Maßnahmen in {len(gelesen['abschnitte'])} "
                f"Teilhaushalten · {(gelesen['kopfsumme'] or 0)/1e6:.1f} Mio. € "
                f"Gesamtinvestitionsprogramm · Dokument {r['document_id']}")

    return {"neue_jahrgaenge": sorted(je_jahrgang),
            "neue_einheiten": [(j,) for j in sorted(je_jahrgang)],
            "bestand_geschuetzt": geschuetzt,
            "je_investitionsjahrgang": je_jahrgang,
            "investitionsmassnahmen": sum(d["massnahmen"]
                                          for d in je_jahrgang.values()),
            "investitionsprogramm_verworfen": verworfen}


def lies_stellenplaene(store: CouncilStore, p: Protokoll,
                       nur_fehlende: bool = False,
                       schuetzen: bool = True) -> dict:
    """Die Stellenpläne aus den Haushaltsplänen — Teil A und Teil B getrennt.

    Die einzige Schicht des Bereichs, die nicht in Euro rechnet: Sie sagt, wie
    viele Menschen hinter dem größten Ausgabenblock stehen — und wie viele
    Stellen davon **nicht besetzt** sind. Das ist die Zahl, wegen der es sich
    lohnt: Bleiben die Personalaufwendungen unter dem Plan, hat die Stadt
    nicht gespart, sondern niemanden gefunden.

    Gespeichert wird je **Teil**, nicht je Jahrgang. Die beiden Teile stehen
    im selben PDF, kommen aber einzeln durch ihre Proben — im Jahrgang 2026
    liefert der Textextrakt für Teil B Glyphen-Nummern statt Buchstaben, für
    Teil A tadellosen Text. Ein Jahrgang, der so halb hereinkommt, steht mit
    ``teilweise`` im Datenstand und nicht als vollständiger.

    Welche Proben entscheiden, steht in ``council/stellenplan.py``. Eine
    Besonderheit: Zeilen, in denen sich der Plan selbst widerspricht (2023
    hat zwei davon), werden **gekennzeichnet statt verworfen** — die
    Summenzeilen darüber gehen auf, und ein Teil mit 140 Zeilen wegen eines
    städtischen Übertragsfehlers wegzuwerfen hieße, eine belegte Zahl gegen
    gar keine zu tauschen. Die Zahl steht im Protokoll."""
    quelle = QUELLEN["stellenplan"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)

    je_jahrgang: dict[int, dict] = {}
    neue_einheiten: set[tuple] = set()
    geschuetzt = verworfen = unstimmig_gesamt = 0
    for r in rows:
        gelesen = stellenplan.lies(r["raw_text"] or "")
        budget_year = gelesen["budget_year"]
        if budget_year is None:
            p.warnen(f"  Dokument {r['document_id']} ({r['label']!r}): kein "
                     f"Haushaltsjahr im Tabellenkopf — übersprungen")
            verworfen += 1
            continue
        if budget_year in je_jahrgang:
            p.warnen(f"  {budget_year}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        je_jahrgang[budget_year] = {"teile": {}, "unstimmig": 0}

        gefunden = {t["teil"] for t in gelesen["teile"]}
        fehlend = sorted(set(stellenplan.TEIL_SPALTEN) - gefunden)
        if fehlend:
            # Der Unterschied, den ein Leser sonst nicht sähe: „gibt es nicht"
            # gegen „steht drin, ist aber nicht lesbar".
            grund = ("das PDF gibt dort Glyphen statt Buchstaben aus"
                     if gelesen["glyphen"] else "im Dokument nicht gefunden")
            p.warnen(f"  {budget_year}: Teil {', '.join(fehlend)} fehlt — {grund} "
                     f"(Dokument {r['document_id']})")

        for teil in gelesen["teile"]:
            name = teil["teil"]
            if (budget_year, name) in vorhanden:
                continue
            if not teil["bestanden"]:
                p.warnen(f"  {budget_year} Teil {name}: {teil['nachweis']} — "
                         f"Dokument {r['document_id']}, nicht gespeichert")
                verworfen += 1
                continue

            alt = _anzahl(store, "SELECT COUNT(*) FROM council_stellenplan "
                                 "WHERE budget_year = ? AND teil = ?", (budget_year, name))
            if not bestandsschutz(p, f"{budget_year} Stellenplan Teil {name}", alt,
                                  len(teil["zeilen"]), schuetzen):
                geschuetzt += 1 if alt else 0
                continue

            store.save_stellenplan(
                budget_year, name, teil["zeilen"],
                herkunft.Herkunft(
                    art="ris", probe=[pr["probe"] for pr in teil["probes"]],
                    document_id=r["document_id"], label=r["label"], url=r["url"],
                    citation=f"Teil {name}: {stellenplan.TEIL_NAMEN[name]}",
                    probe_result=teil["nachweis"],
                    # Wie beim Gesamtergebnishaushalt: Die Anlage hängt an der
                    # Vorlage, mit der die Verwaltung den Haushalt einbringt.
                    stand=f"Stellenplan {budget_year} — Stand der Einbringung, "
                          f"Besetzung am {teil['as_of_date']}"),
                as_of_date=teil["as_of_date"])
            neue_einheiten.add((budget_year, name))

            gesamt = next((z for z in teil["zeilen"] if z["art"] == "gesamt"), None)
            je_jahrgang[budget_year]["teile"][name] = {
                "zeilen": len(teil["zeilen"]),
                "stellen": gesamt["positions_planned"] if gesamt else None,
                "vacant": gesamt["vacant"] if gesamt else None,
            }
            je_jahrgang[budget_year]["unstimmig"] += len(teil["unstimmig"])
            unstimmig_gesamt += len(teil["unstimmig"])
            if gesamt:
                anteil = (gesamt["vacant"] / gesamt["positions_prior_year"] * 100
                          if gesamt["positions_prior_year"] else 0.0)
                p.sagen(f"  {budget_year} Teil {name}: {gesamt['positions_planned']:,.2f} Stellen "
                        f"geplant · am {teil['as_of_date']} waren {gesamt['vacant']:,.2f} "
                        f"von {gesamt['positions_prior_year']:,.2f} nicht besetzt "
                        f"({anteil:.1f} %) · {len(teil['zeilen'])} Zeilen · "
                        f"Dokument {r['document_id']}")
            for u in teil["unstimmig"]:
                p.warnen(f"      Zeile {u['seq_no']} ({u['label']}): der Plan "
                         f"weicht hier um {u['deviation']:+.2f} Stellen von sich "
                         f"selbst ab — gespeichert und gekennzeichnet")

    voll = sorted(j for j, d in je_jahrgang.items() if len(d["teile"]) == 2)
    return {"neue_jahrgaenge": sorted({e[0] for e in neue_einheiten}),
            "neue_einheiten": sorted(neue_einheiten, key=repr),
            "bestand_geschuetzt": geschuetzt,
            "je_stellenplan_jahrgang": {j: d["teile"] for j, d in je_jahrgang.items()},
            "stellenplan_vollstaendig": voll,
            "stellenplan_zeilen": sum(t["zeilen"] for d in je_jahrgang.values()
                                      for t in d["teile"].values()),
            "stellenplan_verworfen": verworfen,
            "stellenplan_unstimmig": unstimmig_gesamt}


def lies_buergschaften(store: CouncilStore, p: Protokoll) -> dict:
    """Den Bürgschaftsbestand aus den Jahresabschlüssen lesen.

    Ein eigener Leser statt eines Blocks in ``lies_jahresabschluesse``, obwohl
    er dieselben Dokumente noch einmal aufmacht: Der Bestand hängt an keiner
    der dortigen Proben — reißt die Ergebnisrechnung eines Jahrgangs, ist sein
    Bürgschaftsbestand trotzdem richtig, und umgekehrt. Zwei Schichten, die
    einander nicht mitreißen sollen, gehören nicht in dieselbe Schleife.

    Erst alles lesen, dann speichern: Die Kettenprobe braucht den Nachbarn
    (``council/buergschaften.kettenprobe``), und ein Riss darf gar nicht erst
    in den Bestand.
    """
    quelle = QUELLEN["jahresabschluss"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")

    gefunden: list[dict] = []
    beleg: dict[int, dict] = {}
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        year = int(m.group(1))
        g = buergschaften.parse_bestand(r["raw_text"] or "", year)
        if not g:
            continue
        gefunden.append(g)
        beleg[year] = r

    risse = buergschaften.kettenprobe(gefunden)
    for x in risse:
        p.warnen(f"  Bürgschafts-Kette gerissen: {x} — nichts gespeichert")
    if risse:
        # Anders als bei der Ergebnisrechnung fällt hier ALLES aus: Die Reihe
        # hat sechs Zeilen, ein Widerspruch darin trifft ihre Aussage im Kern
        # („der Bestand hat sich so und so entwickelt"). Einzelne Jahrgänge zu
        # retten hieße, eine Entwicklung zu zeigen, die man gerade widerlegt
        # hat.
        return {"jahrgaenge": 0, "kette_gerissen": len(risse), "glieder": 0}

    zeilen = buergschaften.series(gefunden)
    glieder = sum(1 for g in gefunden if "prior_year_stock" in g)
    for z in zeilen:
        # Der Beleg ist das Dokument, in dem die Zahl STEHT — für 2021 also
        # der Abschluss 2022. Auf den Abschluss 2021 zu zeigen wäre bequem
        # und falsch: Dort steht sie nicht.
        quell_jahr = z["year"] + 1 if z["out_next_year"] else z["year"]
        r = beleg.get(quell_jahr)
        if not r:
            continue
        probes = [buergschaften.PROBE_TABELLE] if z["exact"] else []
        if quell_jahr in {g["year"] for g in gefunden if "prior_year_stock" in g}:
            probes.append(buergschaften.PROBE_KETTE)
        einzeln = buergschaften.klinikum_amount(z)
        store.save_buergschaften(
            [{**z, "single_amount": einzeln, "probes": probes}],
            herkunft.Herkunft(
                art="ris", probe=probes or [buergschaften.PROBE_KETTE],
                document_id=r["document_id"], label=r["label"], url=r["url"],
                citation=z["citation"],
                probe_result=(f"{z['bestand']/1e6:.1f} Mio. € Bestand"
                                + ("" if z["exact"] else ", von der Quelle gerundet")),
                stand=f"Jahresabschluss {quell_jahr}"))
        woher = " (aus dem Folgejahr)" if z["out_next_year"] else ""
        p.sagen(f"  {z['year']}: {z['bestand']/1e6:7.1f} Mio. €{woher}")
    return {"jahrgaenge": len(zeilen), "kette_gerissen": 0, "glieder": glieder}


def lies_anlagenspiegel(store: CouncilStore, p: Protokoll) -> dict:
    """Den Anlagenspiegel aus den Jahresabschlüssen lesen (Abschnitt 8.1).

    Wie ``lies_buergschaften`` ein eigener Leser auf denselben Dokumenten: Die
    Tabelle hängt an keiner Probe der Ergebnisrechnung, und umgekehrt.

    ANDERS ALS DIE BÜRGSCHAFTEN FÄLLT HIER NICHT ALLES AUS. Die Bürgschaften
    sind eine Reihe, deren Aussage die Entwicklung ist — ein Widerspruch darin
    trifft sie im Kern. Der Anlagenspiegel ist je Jahrgang eine eigene
    Tabelle: Reißt eine Kette in 2019, sagt das nichts über 2024. Ein
    gerissener Jahrgang wird verworfen und benannt, die übrigen bleiben.
    """
    quelle = QUELLEN["jahresabschluss"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")

    jahrgaenge = verworfen = zeilen_gesamt = 0
    geprueft = gerissen = 0
    gruppen_gesamt = 0
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        year = int(m.group(1))
        text = r["raw_text"] or ""
        zeilen = anlagenspiegel.parse_anlagenspiegel(text, year)
        if not zeilen:
            continue

        risse: list[str] = []
        for z in zeilen:
            ok, kaputt = anlagenspiegel.probe(z)
            z["probes"] = ok
            geprueft += len(ok) + len(kaputt)
            risse += kaputt
        balance, umb_risse = anlagenspiegel.umbuchungsprobe(zeilen)
        risse += umb_risse
        # Die Gegenprobe an der Bilanz — eine andere Quelle im selben Heft.
        bilanz_posten = [dict(x) for x in store._conn.execute(  # noqa: SLF001
            "SELECT role, wert FROM council_bilanz WHERE year = ?", (year,))]
        bilanz_risse = anlagenspiegel.gegen_bilanz(zeilen, bilanz_posten)
        if not bilanz_risse and bilanz_posten:
            for z in zeilen:
                if z["nr"] in anlagenspiegel.BILANZ_ROLLE:
                    z["probes"] = [*z["probes"], anlagenspiegel.PROBE_BILANZ]
        risse += bilanz_risse

        if risse:
            gerissen += len(risse)
            verworfen += 1
            for x in risse[:3]:
                p.warnen(f"  Anlagenspiegel {year}: {x}")
            p.warnen(f"  Anlagenspiegel {year} verworfen — {len(risse)} Beanstandung(en)")
            continue

        if abs(balance) <= anlagenspiegel.TOLERANZ and zeilen[0]["spalten"] == 12:
            for z in zeilen:
                z["probes"] = [*z["probes"], anlagenspiegel.PROBE_UMBUCHUNG]

        store.save_anlagenspiegel(
            year, zeilen,
            herkunft.Herkunft(
                art="ris", probe=sorted({x for z in zeilen for x in z["probes"]}),
                document_id=r["document_id"], label=r["label"], url=r["url"],
                citation=anlagenspiegel.ABSCHNITT,
                probe_result=f"{geprueft} Rechenwege geprüft, keiner gerissen",
                stand=f"Jahresabschluss {year}"))
        jahrgaenge += 1
        zeilen_gesamt += len(zeilen)

        gruppen = anlagenspiegel.parse_sachvermoegen_gruppen(text, year)
        if gruppen:
            store.save_vermoegensgruppen(
                year, gruppen,
                herkunft.Herkunft(
                    art="ris", probe=[anlagenspiegel.PROBE_BUCHWERT],
                    document_id=r["document_id"], label=r["label"], url=r["url"],
                    citation="Erläuterungen zum Sachvermögen",
                    probe_result=f"{len(gruppen)} Untergruppen",
                    stand=f"Jahresabschluss {year}"))
            gruppen_gesamt += len(gruppen)
        p.sagen(f"  {year}: {len(zeilen)} Positionen, {len(gruppen)} Untergruppen")

    return {"anlagenspiegel_jahrgaenge": jahrgaenge,
            "anlagenspiegel_zeilen": zeilen_gesamt,
            "anlagenspiegel_geprueft": geprueft,
            "anlagenspiegel_gerissen": gerissen,
            "anlagenspiegel_verworfen": verworfen,
            "vermoegensgruppen": gruppen_gesamt}


def lies_kennzahlen(store: CouncilStore, p: Protokoll) -> dict:
    """Die Kennzahlenübersicht aus den Rechenschaftsberichten (Anlage am Ende).

    Ein Bericht liefert fünf Jahrgänge, und die Jahrgänge überlappen sich
    zwischen den Berichten. Genau daraus zieht diese Schicht ihren Wert:

    * :func:`kennzahlen.ueberlappungsprobe` vergleicht jede doppelt gedruckte
      Zelle. 221 Paare stimmen exakt, sieben nicht — und diese sieben sind
      Korrekturen, die die Stadt vorgenommen und nirgends angesagt hat.
    * :func:`kennzahlen.gegen_bilanz` rechnet drei Quoten aus **unserer**
      Bilanz nach; sie stimmen auf die letzte gedruckte Nachkommastelle.
    * :func:`kennzahlen.vermoegensprobe` nimmt zwei Zeilen derselben Tabelle
      mal — und heraus kommt die Bilanzsumme ohne Rechnungsabgrenzung.

    VERWORFEN WIRD JE BERICHT, nicht insgesamt: Reißt eine Probe im Bericht
    2022, sagt das nichts über den Bericht 2024. Die Überlappungsprobe läuft
    dagegen erst **nach** allen Berichten — sie braucht mindestens zwei.
    """
    quelle = QUELLEN["kennzahlen"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")

    # ERSTER DURCHGANG: alles lesen. Die Fassungsnummer eines Rechenwegs lässt
    # sich erst vergeben, wenn ALLE Berichte vorliegen — sie sagt ja gerade,
    # der wievielte Rechenweg dieser Kennzahl das über die Jahre ist. Wer je
    # Bericht nummeriert, schreibt überall eine Eins, und der Wechsel von
    # „Aufwand für Personal (inklusive Versorgung)" zu „Aufwendungen für
    # aktives Personal" sähe aus wie eine Korrektur der Stadt.
    gelesen: list[tuple[dict, int, list[dict], list[dict], list[str]]] = []
    ohne_tabelle = 0
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        report_year = int(m.group(1))
        text = r["raw_text"] or ""
        zeilen, unbekannt = kennzahlen.parse_kennzahlen(text, report_year)
        if not zeilen:
            # 2017 und 2018 zeigen dieselben Kennzahlen nur als Diagramm. Ihre
            # Jahrgänge stehen als Tabelle im Bericht 2019 — hier fehlt also
            # nichts, und es ist keine Warnung wert.
            ohne_tabelle += 1
            continue
        gelesen.append((r, report_year, zeilen,
                        kennzahlen.parse_formeln(text, report_year), unbekannt))

    alle_formeln = [f for _, _, _, formeln, _ in gelesen for f in formeln]
    nummern = kennzahlen.fassungen(alle_formeln)

    n_reports = verworfen = 0
    werte_gesamt = formeln_gesamt = 0
    bilanz_geprueft = vermoegen_geprueft = 0
    gesammelt: list[dict] = []

    bilanz_posten = [dict(x) for x in store._conn.execute(  # noqa: SLF001
        "SELECT year, role, wert FROM council_bilanz WHERE role IS NOT NULL")]

    # ZWEITER DURCHGANG: prüfen und schreiben, Bericht für Bericht.
    for r, report_year, zeilen, formeln, unbekannt in sorted(
            gelesen, key=lambda g: g[1]):
        for z in zeilen:
            z["fassung"] = nummern.get((z["indicator"], report_year))
        for f in formeln:
            f["fassung"] = nummern[(f["indicator"], report_year)]

        if unbekannt:
            for u in unbekannt[:3]:
                p.warnen(f"  Kennzahlen {report_year}: Zeile nicht zugeordnet — {u}")
            p.warnen(f"  Rechenschaftsbericht {report_year} verworfen — "
                     f"{len(unbekannt)} unzuordenbare Zeile(n)")
            verworfen += 1
            continue

        bilanz_ok, bilanz_risse = kennzahlen.gegen_bilanz(zeilen, bilanz_posten)
        verm_ok, verm_risse = kennzahlen.vermoegensprobe(zeilen, bilanz_posten)
        if bilanz_risse or verm_risse:
            for x in (bilanz_risse + verm_risse)[:3]:
                p.warnen(f"  Kennzahlen {report_year}: {x}")
            p.warnen(f"  Rechenschaftsbericht {report_year} verworfen — "
                     f"{len(bilanz_risse) + len(verm_risse)} Gegenprobe(n) gerissen")
            verworfen += 1
            continue

        probes = [kennzahlen.PROBE_BILANZ] if bilanz_ok else []
        if verm_ok:
            probes.append(kennzahlen.PROBE_VERMOEGEN)
        bilanz_geprueft += bilanz_ok
        vermoegen_geprueft += verm_ok

        store.save_kennzahlen(
            report_year, zeilen, formeln,
            herkunft.Herkunft(
                art="ris", probe=probes or herkunft.UNGEPRUEFT,
                document_id=r["document_id"], label=r["label"], url=r["url"],
                citation="Anlage: Kennzahlenübersicht und Berechnungsmethoden",
                probe_result=f"{bilanz_ok} Quoten und {verm_ok} Jahrgänge "
                               f"gegen die Bilanz nachgerechnet",
                stand=f"Rechenschaftsbericht {report_year}"))
        n_reports += 1
        werte_gesamt += len(zeilen)
        formeln_gesamt += len(formeln)
        gesammelt += zeilen
        jahre = sorted({z["year"] for z in zeilen})
        p.sagen(f"  Bericht {report_year}: {len(zeilen)} Werte "
                f"({jahre[0]}–{jahre[-1]}), {len(formeln)} Rechenwege")

    bestaetigt, funde = kennzahlen.ueberlappungsprobe(gesammelt)
    arten = {a: sum(1 for f in funde if f["art"] == a)
             for a in ("revision", "definition", "umbenennung")}
    for f in funde:
        if f["art"] == "revision":
            p.sagen(f"  Korrektur: {f['indicator']} {f['year']} — {f['alt']} "
                    f"(Bericht {f['alt_bericht']}) → {f['neu']} "
                    f"(Bericht {f['neu_bericht']})")
    p.sagen(f"  Überlappung: {bestaetigt} Paare identisch, "
            f"{arten['revision']} Korrekturen, "
            f"{arten['definition']} Definitionswechsel, "
            f"{arten['umbenennung']} bloße Umbenennungen")

    return {"kennzahlen_berichte": n_reports,
            "kennzahlen_werte": werte_gesamt,
            "kennzahlen_formeln": formeln_gesamt,
            "kennzahlen_ohne_tabelle": ohne_tabelle,
            "kennzahlen_verworfen": verworfen,
            "kennzahlen_bilanz_geprueft": bilanz_geprueft,
            "kennzahlen_vermoegen_geprueft": vermoegen_geprueft,
            "kennzahlen_ueberlappung": bestaetigt,
            "kennzahlen_korrekturen": arten["revision"],
            "kennzahlen_definitionswechsel": arten["definition"]}


def lies_schlussbericht_fundstellen(store: CouncilStore, p: Protokoll,
                                    nur_fehlende: bool = False,
                                    schuetzen: bool = True) -> dict:
    """Schlussberichte des Rechnungsprüfungsamts als Fundstelle merken —
    nur Verweis, kein Inhalt („Das Rechnungsprüfungsamt hat diesen Abschluss
    geprüft").

    Eine Zeile je Jahrgang, ein Dokument je Zeile — hier ist die Einheit
    tatsächlich der Jahrgang, und „da" heißt „fertig"."""
    quelle = QUELLEN["rpa_fundstelle"]
    rows = quelle.dokumente(store, "document_id, label, url, n_pages, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)
    neu: list[int] = []
    gefunden = unlesbar = 0
    for r in rows:
        treffer = finanzberichte.pruefbericht_aus_anlage(r["label"], r["raw_text"])
        if not treffer:
            continue
        if (treffer["year"],) in vorhanden:
            continue
        # Der Buchstabenanteil steht auch dann dabei, wenn er die Probe
        # REISST (2024: 0,00) — dann fehlt `textextrakt` in der Liste, und
        # die Zahl daneben sagt, warum. Eine gerissene Probe zu verschweigen
        # wäre schlimmer, als sie zu nennen.
        probes = ["eingangsformel"] + (["textextrakt"] if treffer["readable"] else [])
        store.save_pruefbericht_quelle(
            treffer["year"],
            herkunft.Herkunft(
                art="ris", probe=probes, document_id=r["document_id"],
                label=r["label"], url=r["url"],
                citation="Deckblatt und Eingangsformel des Schlussberichts",
                probe_result=f"Buchstabenanteil im Volltext "
                               f"{treffer['buchstabenanteil']:.2f}",
                stand=f"Jahresabschluss {treffer['year']}"),
            r["n_pages"], treffer["readable"])
        neu.append(treffer["year"])
        gefunden += 1
        note = "" if treffer["readable"] else "  (Volltext unbrauchbar, nur Verweis)"
        p.sagen(f'  {treffer["year"]}: {r["n_pages"]} Seiten{note}')
        unlesbar += 0 if treffer["readable"] else 1
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
    quelle = QUELLEN["teilhaushalt"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)
    if nur_fehlende:
        rows = [r for r in rows if (teilhaushalt_jahrgang((r["raw_text"] or "")[:4000]),
                                    teilhaushalt_nummer(r["label"])) not in vorhanden]

    je_jahr: dict[int, int] = {}
    neue_einheiten: set[tuple] = set()
    mit_feld: dict[str, int] = {f: 0 for f in STECKBRIEF}
    ohne = geschuetzt = dubletten = 0
    # (year, thh_nr) → (Signatur, Dokument), das den Teilhaushalt versorgt hat.
    versorgt: dict[tuple, tuple] = {}
    for r in rows:
        produkte = finanzberichte.parse_teilergebnishaushalt(r["raw_text"] or "")
        if not produkte:
            ohne += 1
            continue
        for year in {x["year"] for x in produkte}:
            teil = [x for x in produkte if x["year"] == year]
            # ``save_produkte`` löscht nichts, überschreibt aber Zeile für
            # Zeile. Verglichen wird deshalb je Teilhaushalt, nicht je Jahr:
            # Ein Dokument trägt immer nur seinen eigenen THH bei, gegen den
            # Jahresbestand gehalten sähe jedes Dokument wie ein Einbruch aus.
            with store.transaktion():
                for sub_budget_no in sorted({x.get("sub_budget_no") for x in teil}, key=lambda v: v or 0):
                    if (year, sub_budget_no) in vorhanden:
                        continue
                    stueck = [x for x in teil if x.get("sub_budget_no") == sub_budget_no]
                    # Zweites Dokument für denselben Teilhaushalt: Das erste
                    # hat ihn versorgt (siehe Docstring). Nur die Herkunft
                    # würde hier noch getauscht — und mit ihr entstünde ein
                    # Herkunfts-Datensatz, auf den am Ende des Laufs keine
                    # Zeile mehr zeigt (`herkunft_aufraeumen` fegte sechs
                    # Stück je Lauf wieder weg).
                    if (year, sub_budget_no) in versorgt:
                        signatur, quelle = versorgt[(year, sub_budget_no)]
                        if _produkt_signatur(stueck) != signatur:
                            p.warnen(
                                f"  {year} THH{sub_budget_no}: Dokument {r['document_id']} "
                                f"({r['label']!r}) trägt ANDERE Zahlen als "
                                f"Dokument {quelle['document_id']} "
                                f"({quelle['label']!r}), das den Teilhaushalt "
                                f"versorgt hat — es gilt weiter das erste. "
                                f"Bitte prüfen, welcher Stand der richtige ist.")
                        dubletten += 1
                        continue
                    alt = _anzahl(store, "SELECT COUNT(*) FROM council_produkte "
                                         "WHERE year = ? AND sub_budget_no IS ?", (year, sub_budget_no))
                    if not bestandsschutz(p, f"{year} THH{sub_budget_no}", alt,
                                          len(stueck), schuetzen):
                        geschuetzt += 1 if alt else 0
                        continue
                    store.save_produkte(year, stueck, herkunft.Herkunft(
                        art="ris", probe="produktzeile",
                        document_id=r["document_id"], label=r["label"], url=r["url"],
                        citation=(f"Teilergebnishaushalt THH{sub_budget_no:02d}, "
                                    f"Produktebene mit Steckbrief" if sub_budget_no
                                    else "Teilergebnishaushalt, Produktebene"),
                        probe_result=f"{len(stueck)} Produktzeilen mit "
                                       f"aufgehender Ergebnis-Rechnung",
                        stand=f"Haushaltsplan {year}"))
                    versorgt[(year, sub_budget_no)] = (_produkt_signatur(stueck), r)
                    neue_einheiten.add((year, sub_budget_no))
                    je_jahr[year] = je_jahr.get(year, 0) + len(stueck)
                    for feld in STECKBRIEF:
                        mit_feld[feld] += sum(1 for x in stueck if x.get(feld))
    for year in sorted(je_jahr):
        p.sagen(f"  {year}: {je_jahr[year]} Produkt-Zeilen")
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

    quelle = QUELLEN["pruefungsfeststellungen"]
    rows = quelle.dokumente(store, "document_id, label, url, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)

    je_jahr: dict[int, dict] = {}
    geschuetzt = 0
    for r in rows:
        result = pruefberichte.parse_feststellungen(r["raw_text"] or "")
        year = result["year"]
        if year is None:
            continue  # Stiftung, Eigenbetrieb oder kaputter Textextrakt
        if (year,) in vorhanden:
            continue
        gefunden = result["feststellungen"]
        if not gefunden:
            p.warnen(f"  {year}: keine Feststellung readable "
                     f"(Legende {sorted(result['legende']) or '—'}) — übersprungen")
        if year in je_jahr:
            p.warnen(f"  {year}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        # save_pruefbericht leert den Jahrgang, bevor es schreibt — gegen ein
        # leeres oder deutlich kleineres Ergebnis passiert das nicht.
        alt = _anzahl(store, "SELECT COUNT(*) FROM council_pruefberichte WHERE year = ?",
                      (year,))
        if not bestandsschutz(p, f"{year} Feststellungen", alt, len(gefunden), schuetzen):
            geschuetzt += 1 if alt else 0
            continue
        marken = Counter(f["mark"] for f in gefunden)
        if not trocken:
            store.save_pruefbericht(year, gefunden, herkunft.Herkunft(
                art="ris", probe="legende_und_verzeichnis",
                document_id=r["document_id"], label=r["label"], url=r["url"],
                # Grob mit Absicht: Die genaue Fundstelle einer Feststellung
                # ist ihre Textziffer und ihre Seite, und die stehen je Zeile
                # in der Tabelle.
                citation="Randmarken B, WB, H und K im Fließtext",
                probe_result=f"{len(gefunden)} Feststellungen übernommen, "
                               f"{len(result['verworfen'])} verworfen",
                stand=f"Schlussbericht zum Jahresabschluss {year}"))
        je_jahr[year] = {"feststellungen": len(gefunden),
                         "verworfen": len(result["verworfen"]),
                         "marken": dict(marken)}
        marken_text = " · ".join(
            f"{m} {marken[m]}" for m in pruefberichte.MARKEN if marken.get(m))
        p.sagen(f"  {year}: {len(gefunden)} Feststellungen ({marken_text})"
                f" · verworfen {len(result['verworfen'])}"
                f" · Dokument {r['document_id']}")
        for v in result["verworfen"]:
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
    rows = quelle.dokumente(store, "document_id, label, url, n_pages, raw_text")
    vorhanden = quelle.vorhandene(store, nur_fehlende)

    je_jahr: dict[int, dict] = {}
    gelesen: dict[int, list[dict]] = {}
    geschuetzt = verworfen_gesamt = 0
    for r in rows:
        year = konzernabschluss.budget_year(r["raw_text"])
        if year is None:
            continue  # Schlussbericht oder Teilhaushalts-Plan im selben Vorfilter
        if (year,) in vorhanden:
            continue
        if year in je_jahr:
            p.warnen(f"  {year}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        result = konzernabschluss.lies(r["raw_text"] or "")
        if not result["bestanden"]:
            gerissen = [x["probe"] for x in result["probes"] if not x["ok"]]
            grund = (f"Probe gerissen: {'; '.join(gerissen)}" if gerissen
                     else f"nur {len(result['probes'])} von 3 Proben rechenbar")
            p.warnen(f"  {year}: {grund} — Dokument {r['document_id']}, nicht gespeichert")
            verworfen_gesamt += result["verworfen"]
            continue
        alt = _anzahl(store, "SELECT COUNT(*) FROM council_konzern_posten WHERE year = ?",
                      (year,))
        if not bestandsschutz(p, f"{year} Konzern-Posten", alt,
                              len(result["posten"]), schuetzen):
            geschuetzt += 1 if alt else 0
            continue
        entity = [z | {"art": block["art"]}
                   for block in result["entity"] for z in block["zeilen"]]

        # Zwei Herkünfte, weil es zwei Abschnitte sind: Die Posten stehen in
        # 3.2, die Trägeraufstellung in 4.1.1, und sie sind durch verschiedene
        # Proben gedeckt. `stand` nennt den Stichtag des Inhalts — bei den
        # Beteiligungen ist genau das der Punkt, an dem sich Konzern- und
        # Einzelabschluss unterscheiden werden.
        anker = dict(art="ris", document_id=r["document_id"], label=r["label"],
                     url=r["url"], stand=f"Gesamtabschluss zum 31.12.{year}")
        h_posten = herkunft.Herkunft(
            probe=["konzern_ergebnisprobe", "konzern_ausserordentlich",
                   "konzern_gesamtergebnis"],
            citation="Abschnitt 3.2, Gesamtergebnisrechnung des Konzerns",
            probe_result=konzernabschluss.probennachweis(result["probes"]),
            **anker)
        h_traeger = herkunft.Herkunft(
            probe=["konzern_zeilenprobe", "konzern_traegersumme", "konzern_querprobe"],
            citation="Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern",
            probe_result=konzernabschluss.traegernachweis(result["entity"]),
            **anker) if entity else None
        store.save_konzern_jahrgang(year, result["posten"], entity,
                                    h_posten, h_traeger)
        gelesen[year] = result["posten"]
        verworfen_gesamt += result["verworfen"]
        je_jahr[year] = {"posten": len(result["posten"]), "entity": len(entity),
                         "aufstellungen": len(result["entity"]),
                         "verworfen": result["verworfen"]}
        p.sagen(f"  {year}: {len(result['posten'])} Posten · {len(entity)} Trägerzeilen "
                f"aus {len(result['entity'])} Aufstellungen"
                f" · verworfen {result['verworfen']} · Dokument {r['document_id']}")
        # Nur melden, wenn eine *vorhandene* Aufstellung durchgefallen ist.
        # Bis 2016 führt der Bericht den Abschnitt 4.1.1 noch nicht — das ist
        # eine Lücke der Quelle und keine Meldung wert.
        if len(result["entity"]) < result["traeger_gefunden"]:
            p.warnen(f"  {year}: {result['traeger_gefunden'] - len(result['entity'])} "
                     f"von {result['traeger_gefunden']} Trägeraufstellungen an ihrer "
                     "Spalten- oder Querprobe gescheitert")

    kette = _kette_pruefen(gelesen, p)
    return {"neue_jahrgaenge": sorted(je_jahr),
            "neue_einheiten": [(j,) for j in sorted(je_jahr)],
            "je_jahr": je_jahr, "bestand_geschuetzt": geschuetzt,
            "konzern_posten": sum(d["posten"] for d in je_jahr.values()),
            "konzern_traeger": sum(d["entity"] for d in je_jahr.values()),
            "verworfen": verworfen_gesamt, **kette}


#: Rollen, deren Vorjahresspalte gegen den Vorjahrgang geprüft wird.
_KETTEN_ROLLEN = ("revenues_total", "expenses_total", "ordinary_result",
                  "total_result")


def _kette_pruefen(gelesen: dict[int, list[dict]], p: Protokoll) -> dict:
    """Vorjahresspalte gegen den Vorjahrgang — über Dokumentgrenzen hinweg.

    Bis 2016 führt der Bericht die Vorjahreszahlen in Tausend Euro; die
    Toleranz muss dort eine halbe Rundungseinheit hergeben, sonst schlägt
    jede Zeile an, die auf Tausend gerundet wurde."""
    geprueft = bestanden = 0
    for year in sorted(gelesen):
        if year - 1 not in gelesen:
            continue
        jetzt = {x["role"]: x for x in gelesen[year] if x["role"]}
        vorher = {x["role"]: x for x in gelesen[year - 1] if x["role"]}
        toleranz = 1000.0 if year <= 2016 else konzernabschluss.TOLERANZ_EUR
        for role in _KETTEN_ROLLEN:
            a = (jetzt.get(role) or {}).get("prior_year")
            b = (vorher.get(role) or {}).get("amount")
            if a is None or b is None:
                continue
            geprueft += 1
            if abs(a - b) <= toleranz:
                bestanden += 1
            else:
                p.warnen(f"  Vorjahres-Kette {year - 1}→{year} {role}: "
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
        nebentabellen=("council_abweichungsgruende", "council_finanzrechnung",
                       "council_bilanz", "council_bilanz_erlaeuterungen"),
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
        key="kennzahlen",
        label="Kennzahlen des Rechenschaftsberichts",
        was="Die dreizehn Zahlen, auf die die Stadt ihren Jahresabschluss "
            "selbst eindampft — mit den Rechenwegen, die sie danebendruckt.",
        tabelle="council_kennzahlen",
        nebentabellen=("council_kennzahl_formeln",),
        erwarteter_monat=9,
        versatz=1,
        herkunft="ris",
        erkennung=Erkennung(
            # „Rechenschaftsbericht" endet auf -chaftsbericht, das Muster der
            # Schlussberichte auf -chlussbericht. Die Berichte 2017–2021 lagen
            # deshalb bis 08/2026 ohne Volltext im Bestand; 2022–2024
            # rutschten nur durch, weil ihr Titel „Jahresabschluss" enthält.
            label_muster=("%Rechenschaftsbericht%",),
            # Namentlich ausschließen, NICHT über „Stiftung": Der städtische
            # Bericht heißt selbst „… der Kernverwaltung und ihrer nicht
            # rechtsfähigen Stiftungen" und fiele mit heraus.
            ausschluesse=("%Schlussbericht%", "%Klävemann%", "%Sozialstiftung%"),
            mindest_seiten=60,
        ),
        einheit="Berichte",
        einheiten_von=_einheiten_kennzahlen,
        bestand=_bestand_kennzahlen,
        einlesen=lies_kennzahlen,
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
            # `konzernabschluss.budget_year` am Textkopf wieder hinaus.
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
        key="stellenplan",
        label="Stellenplan",
        was="Wie viele Stellen die Stadt vorhält — und wie viele davon nicht "
            "besetzt sind.",
        tabelle="council_stellenplan",
        # Anlage 21/22 des Haushaltsplans, also derselbe Takt wie der
        # Gesamtergebnishaushalt: Einbringung Anfang Oktober des Vorjahres.
        erwarteter_monat=10,
        versatz=-1,
        herkunft="ris",
        erkennung=Erkennung(
            label_muster=("%Stellenplan%",),
            # „Geänderter Stellenplan Teil B" (2021, für das Haushaltsjahr
            # 2020) und die „Geänderte Übersicht zum Stellenplan Teil A" sind
            # Änderungen des Plans, nicht der eingebrachte Plan — und die
            # erste trägt nur Teil B. Ein Jahr, das nur die Tarifhälfte zeigt,
            # läse sich wie ein Jahr ohne Beamtenstellen (s. Kopf von
            # council/stellenplan.py).
            ausschluesse=("%eändert%",),
            # Die vier Dokumente haben 20–22 Seiten; die Schwelle hält
            # Deckblätter und Auszüge draußen.
            mindest_seiten=10,
            ordnung="document_id",
        ),
        # Die Einheit ist der Teil, nicht der Jahrgang: Teil A und Teil B
        # kommen einzeln durch ihre Proben.
        einheit="Teile",
        einheiten_von=_einheiten_stellenplan,
        bestand=_bestand_stellenplan,
        einlesen=lies_stellenplaene,
    ),
    Finanzquelle(
        key="investitionen",
        label="Investitionen (Finanzhaushalt)",
        was="Was die Stadt bauen und kaufen will — die andere Hälfte des "
            "Haushaltsplans, in der die Schulen, Straßen und Fahrzeuge stehen.",
        tabelle="council_investitionen",
        # Gemessen an den vier Lieferungen des Portals, nicht geschätzt: Der
        # Jahrgang erscheint im FOLGEJAHR (2022 → 24.04.2024 als Nachzügler,
        # 2023 → 19.06.2024, 2024 → 16.06.2025, 2025 → 14.07.2026). Juli ist
        # der späteste gemessene Monat und deshalb die Schwelle — wer Juni
        # nähme, meldete den Jahrgang 2025 drei Wochen lang als überfällig,
        # obwohl das Portal nur seinem üblichen Takt folgte.
        erwarteter_monat=7,
        versatz=1,
        # Kommt NICHT aus council_anlagen, sondern als CSV vom Open-Data-Portal
        # (scripts/ingest_finanzen_opendata.py). Der Cron lädt nichts herunter
        # — er beobachtet diese Schicht nur und meldet, wenn sie ausbleibt.
        herkunft="opendata",
        nachschub="Download vom Open-Data-Portal, "
                  "scripts/ingest_finanzen_opendata.py",
        bestand=_bestand_investitionen,
    ),
    Finanzquelle(
        key="investitionsprogramm",
        label="Investitionsprogramm (einzelne Vorhaben)",
        was="Welche einzelnen Vorhaben hinter den Investitionssummen stehen — "
            "vom Kunstrasenplatz über den Straßenabschnitt bis zum "
            "Feuerwehrfahrzeug, jedes mit seiner Gesamtsumme.",
        tabelle="council_investitionsmassnahmen",
        # Anlage 004 des Haushaltsplans, also derselbe Takt wie der
        # Gesamtergebnishaushalt (Anlage 005) und der Stellenplan: Einbringung
        # Anfang Oktober des Vorjahres. Über die acht Jahrgänge 2019–2026
        # gemessen liegen alle im Oktober oder November.
        erwarteter_monat=10,
        versatz=-1,
        herkunft="ris",
        erkennung=Erkennung(
            # Das Label reicht: „Investitionsprogramm" steht bei genau diesen
            # acht Anlagen im Titel — die Schreibweise davor schwankt
            # („004 Investitionsprogramm" bis „2026 004 Vw Investitionsprogramm
            # Haushalt 2026 Verwaltungsentwurf"), das Wort selbst nicht.
            label_muster=(investitionsprogramm.LABEL_MUSTER,),
            # Die Dokumente haben 76–84 Seiten; die Schwelle hält Deckblätter,
            # Auszüge und die Änderungslisten der Beratung draußen.
            mindest_seiten=40,
            # Nach Veröffentlichung, damit bei zwei Fassungen eines Jahrgangs
            # der Verwaltungsentwurf gewinnt und nicht der Zufall der
            # Schreibweise (vgl. `teilhaushalt`).
            ordnung="document_id",
        ),
        einheiten_von=_einheiten_investitionsprogramm,
        bestand=_bestand_investitionsprogramm,
        einlesen=lies_investitionsprogramme,
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
        key="gebuehren",
        label="Gebührenbedarfsberechnung",
        was="Die Rechnung, aus der die Abfall- und Straßenreinigungsgebühren "
            "entstehen: Was der Bereich kostet, was davon Dritte tragen, was "
            "aus Vorjahren ausgeglichen wird — und was übrig bleibt, geteilt "
            "durch die Abfallmenge bzw. die gebührenpflichtige Fläche. Von "
            "allen Zahlen des Haushalts landet keine so direkt im "
            "Portemonnaie.",
        tabelle="council_gebuehren",
        # Gemessen an den vier Jahrgängen im Bestand: Die Berechnung für das
        # kommende Jahr trägt das Datum des Vorjahres-Herbstes (01.10.2024 für
        # 2025, 10.10.2023 für 2024). Sie reist mit dem Haushaltsentwurf.
        erwarteter_monat=11,
        versatz=-1,
        herkunft="ris",
        erkennung=Erkennung(
            label_muster=("%Gebührenbedarf%",),
        ),
        nachschub="scripts/ingest_gebuehren.py",
        bestand=_bestand_gebuehren,
    ),
    Finanzquelle(
        key="haushaltssatzung",
        label="Haushaltssatzung",
        was="Der Rahmen, den der Haushaltsplan bekommt: wie viel die Stadt "
            "sich für Investitionen leihen darf (§ 2), wie hoch ihr Dispo sein "
            "darf (§ 4, Liquiditätskredite), welche Verpflichtungen sie für "
            "kommende Jahre eingehen darf (§ 3) — und der Finanzhaushalt als "
            "Ganzes (§ 1.2), aus dem der Bereich bisher nur die Investitionen "
            "las. ACHTUNG: Im Ratsinformationssystem stehen ausschließlich "
            "Verwaltungsentwürfe; die beschlossene Fassung erscheint im "
            "Amtsblatt.",
        tabelle="council_haushaltssatzung",
        # Gemessen an den sieben Jahrgängen im Bestand: Die Satzung für das
        # kommende Jahr liegt mit dem Haushaltsentwurf vor, also im Herbst.
        # Dieselbe Schwelle wie bei den Wirtschaftsplänen, aus demselben
        # Grund — beide reisen als Teil des Verwaltungsentwurfs.
        erwarteter_monat=11,
        versatz=-1,
        herkunft="ris",
        erkennung=Erkennung(
            label_muster=("%Haushaltssatzung%",),
            # Der Nachtrag trägt dasselbe Wort im Label und eine ganz andere
            # Tabelle. Er fliegt schon im Parser raus; hier steht er noch
            # einmal, damit der Backfill ihn gar nicht erst holt.
            ausschluesse=("%Nachtrag%",),
        ),
        nachschub="scripts/ingest_haushaltssatzung.py",
        bestand=_bestand_haushaltssatzung,
    ),
    Finanzquelle(
        key="wirtschaftsplan",
        label="Wirtschaftspläne der Eigenbetriebe",
        was="Was der Rat den Eigenbetrieben für das kommende Jahr genehmigt — "
            "eigene Erfolgs- und Vermögenspläne neben dem Kernhaushalt. Bisher "
            "nur der Eigenbetrieb Gebäudewirtschaft und Hochbau; die übrigen "
            "Betriebe nennen ihre Zahlen nur in einer Anlage.",
        tabelle="council_wirtschaftsplaene",
        # Gemessen an den acht Entwurfsdaten im Bestand, nicht geschätzt:
        # 04.09.2020, 17.09.2019, 01.10.2025, 02.10.2024, 04.10.2023,
        # 05.10.2018, 12.10.2022, 22.11.2021. Die Schwelle steht auf dem
        # SPÄTESTEN gemessenen Monat — zu früh gemeldet wäre der teurere
        # Fehler, und 2021 zeigt, dass der November vorkommt.
        erwarteter_monat=11,
        # Der Plan FÜR 2026 wird im Herbst 2025 eingebracht.
        versatz=-1,
        herkunft="ris",
        # Die Erkennung dient hier NICHT dem Cron — er kann diese Schicht nicht
        # lesen, ihre Einheit ist eine Vorlage und keine Anlage. Sie steht für
        # `backfill_anlagen_texte.py --nur-finanz`: Das Skript zieht seine
        # Label-Muster aus dieser Registry, und ohne Eintrag blieben die
        # Wirtschaftsplan-Anlagen der ÜBRIGEN Betriebe für immer auf 'listed'
        # liegen — also unlesbar, ohne dass es jemand merkt.
        # `oder=True` ist hier PFLICHT und war es von Anfang an: Die drei Muster
        # sind drei Schreibweisen DESSELBEN Worts. Mit dem Vorgabewert (UND)
        # müsste ein Label alle drei gleichzeitig enthalten — die Erkennung traf
        # also nie ein Dokument. Aufgefallen ist das erst am 20.08.2026, weil
        # bis dahin nur `finanz_muster()` diese Muster las und sich sein ODER
        # selbst baut. Der Wächter dazu steht in tests/test_finanzquellen.py.
        erkennung=Erkennung(
            label_muster=("%Wirtschaftsplan%", "%Wirtschafts- und Finanzplan%",
                          "%Wirtschafts-und Finanzplan%"),
            oder=True,
        ),
        nachschub="liegt schon im Bestand (council_vorlagen), "
                  "scripts/ingest_wirtschaftsplaene.py",
        bestand=_bestand_wirtschaftsplan,
    ),
    Finanzquelle(
        key="schulden",
        label="Schuldenstand",
        was="Wie viel die Stadt schuldet und wie sich das seit 1995 entwickelt "
            "hat — für die Stadt als Rechtsträger, also mit ihren "
            "Eigenbetrieben und ohne die eigenständigen Beteiligungen.",
        tabelle="council_schulden",
        # Gemessen am Dokument, nicht geschätzt: Die Tabelle für den Jahrgang
        # 2025 steht seit dem 08.07.2026 online (Last-Modified des PDF, das
        # Dokument selbst ist vom 07.07.2026). Das ist EIN Messpunkt für diese
        # Tabelle — die Schwelle steht trotzdem auf September, weil das
        # Jahrbuch seine Tabellen einzeln über das Jahr verteilt nachzieht und
        # die letzten Blätter eines Jahrgangs erst Ende September kamen
        # (0229-2024: 29.09.2025). Zu früh gemeldet wäre der teurere Fehler.
        erwarteter_monat=9,
        # Der Schuldenstand zum 31.12. eines Jahres erscheint im Folgejahr.
        versatz=1,
        # Kommt NICHT aus council_anlagen, sondern als PDF von oldenburg.de.
        # Der Cron beobachtet diese Schicht nur und meldet, wenn sie ausbleibt.
        herkunft="stadt",
        nachschub="Download von oldenburg.de, scripts/ingest_schulden.py",
        bestand=_bestand_schulden,
    ),
    Finanzquelle(
        key="beteiligungsbericht",
        label="Beteiligungsbericht",
        was="Was die städtischen Gesellschaften tun, wer sie beaufsichtigt "
            "und was sie erwirtschaften — vom Klinikum bis zur Volkshochschule.",
        tabelle="council_gesellschaft_kennzahlen",
        # Gemessen an den sieben Jahrgängen auf oldenburg.de (Last-Modified des
        # Servers): Der Bericht erscheint immer im **zweiten** Folgejahr,
        # zwischen Januar und Juni — 2018→Feb 2020, 2019→Jan 2021, 2020→Apr
        # 2022, 2021→Feb 2023, 2022→Jun 2024, 2023→Jan 2025, 2024→Mär 2026.
        # Juni ist der späteste gemessene Monat und deshalb die Schwelle: zu
        # früh gemeldet ist der teurere Fehler.
        erwarteter_monat=6,
        versatz=2,
        # Kommt von oldenburg.de, nicht aus dem Bürgerinfo — und anders als bei
        # den übrigen `stadt`-Schichten holt ihn ein Cron **selbst**. Er steht
        # hier trotzdem als `automatisch=False`: `check_finanzdaten` lädt nichts
        # herunter (seine Regel 1), beobachtet diese Schicht aber mit und meldet,
        # wenn ein Jahrgang ausbleibt.
        herkunft="stadt",
        nachschub="eigener Cron scripts/check_beteiligungsbericht.py "
                  "(lädt von oldenburg.de)",
        bestand=_bestand_beteiligungsbericht,
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
    Finanzquelle(
        key="lsn_gewerbesteuer",
        label="Gewerbesteuerstatistik",
        was="Wie viele Betriebe die Gewerbesteuer aufbringen — und wie viele "
            "von ihnen überhaupt eine zahlen.",
        tabelle="council_gewerbesteuerstatistik",
        # DIE SCHICHT MIT DEM GRÖSSTEN VERZUG DES GANZEN BEREICHS, und das ist
        # keine Nachlässigkeit des Landesamts: Eine Veranlagung ist erst nach
        # den Betriebsprüfungen endgültig. Gemessen an drei Jahrgängen —
        # 2019 → August 2024, 2020 → September 2025, 2021 → März 2026. Fünf
        # Jahre Versatz, und der September ist der späteste gemessene Monat;
        # wer den März nähme, meldete für 2019 und 2020 einen Rückstand, den es
        # nicht gab (dieselbe Überlegung wie beim Finanzausgleich darüber).
        erwarteter_monat=9,
        versatz=5,
        herkunft="lsn",
        nachschub="Download vom Landesamt für Statistik, "
                  "scripts/ingest_gewerbesteuerstatistik.py",
        bestand=_bestand_lsn_gewerbesteuer,
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
#: Die Investitionen stehen direkt hinter dem Gesamtergebnishaushalt: Beide
#: sind Plan, und zusammen sind sie der ganze Haushaltsplan — der eine die
#: laufenden Erträge und Aufwendungen, der andere das, was gebaut und gekauft
#: wird. Getrennt aufgeführt und nicht unter „Haushaltsplan" zusammengefasst,
#: weil sie aus verschiedenen Dateien kommen, verschieden weit reichen
#: (2022–2025 gegen 2020–2026) und verschiedene Proben tragen.
#:
#: Der Stellenplan steht hinter den Teilhaushalten: Er kommt mit demselben
#: Dokument wie sie, beantwortet aber die Frage eine Stufe feiner — erst was
#: eine Aufgabe kostet, dann wie viele Menschen sie tun sollen.
#: Der Schuldenstand steht hinter dem Gesamtabschluss und vor dem
#: Städtevergleich: Er ist die einzige Schicht, die einen **Bestand** zeigt
#: statt eines Jahresverlaufs — was am Stichtag noch offen ist, nicht was in
#: zwölf Monaten geflossen ist. Deshalb steht er nicht zwischen den
#: Rechnungen, sondern hinter ihnen.
#:
#: Der Beteiligungsbericht steht direkt hinter dem Gesamtabschluss und vor dem
#: Schuldenstand: Beide verlassen die Kernverwaltung, und der Gesamtabschluss
#: sagt, wie viel die Betriebe bewegen, der Beteiligungsbericht, was sie tun.
#: Die Zahl kommt zuerst, die Erklärung gleich danach.
#: Das Investitionsprogramm steht direkt hinter den Investitionen: Es ist
#: dieselbe Frage eine Stufe feiner — erst wie viel ein Bereich investiert,
#: dann welches Vorhaben das ist. Dieselbe Ordnung wie bei Teilhaushalten und
#: Stellenplan, und aus demselben Grund.
REIHENFOLGE = ("haushaltsplan", "ergebnishaushalt", "investitionen",
               "investitionsprogramm", "jahresabschluss", "teilhaushalt",
               "stellenplan", "kennzahlen", "rpa_fundstelle",
               "pruefungsfeststellungen",
               "konzernabschluss", "beteiligungsbericht", "gebuehren",
               "haushaltssatzung",
               "wirtschaftsplan",
               "schulden",
               "lsn_steuerkraft", "lsn_realsteuern", "lsn_gewerbesteuer")

#: Die Stelle hinter einer Herkunft, im Klartext. Sie steht in der Fußzeile des
#: Datenstands („Nicht dabei: … — die Zahlen holen wir bei …") und muss deshalb
#: aus den Daten kommen: Der Satz nannte bis 08/2026 pauschal das „Portal der
#: Stadt" und wurde mit der ersten Schicht einer Landesbehörde falsch.
STELLEN = {
    "ris": "Ratsinformationssystem",
    "stadt": "Portal der Stadt",
    "opendata": "Open-Data-Portal der Stadt",
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
