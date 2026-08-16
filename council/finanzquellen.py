"""Woher die Finanzzahlen des Haushalts-Bereichs stammen — eine Definition je
Datenart, und das Einlesen dazu.

Fünf Schichten tragen den Bereich. Vier davon hängen als **Anlagen** an
Ratsvorlagen und liegen mit Volltext in ``council_anlagen``; woran man sie
dort erkennt (Label-Muster, Mindestseitenzahl, Ausschlüsse), stand bis 08/2026
verstreut in zwei Ingest-Skripten. Hier steht es einmal. ``ingest_finanz-
berichte.py``, ``ingest_pruefberichte.py`` und der Cron ``check_finanzdaten.py``
lesen dieselbe Definition — auf die Frage „ist das ein Jahresabschluss?" gibt
es sonst zwei Antworten, und eine davon veraltet still.

Der Takt der Stadt, gemessen an acht Jahrgängen Sitzungsdaten:

===========================================  ==================
Was                                          Wann im Rat
===========================================  ==================
Jahresabschluss + Schlussbericht des RPA     Anfang September
Haushaltsplan samt Teilhaushalten            Anfang Oktober
===========================================  ==================

Der Cron rechnet damit **nicht**. Er fragt den Bestand, nicht den Kalender:
„Welcher Jahrgang fehlt mir, und liegt inzwischen ein Dokument dafür vor?"
Ein Job, der im September nach dem Jahresabschluss sucht, bricht in dem Jahr,
in dem die Stadt später dran ist. ``erwarteter_monat`` dient deshalb einem
einzigen Zweck: zu sagen, ab wann ein fehlender Jahrgang eine **Meldung** wert
ist — nicht, wann gesucht wird.

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

from council import finanzberichte, pruefberichte
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
    """Eine Datenart: woran man sie erkennt, was sie füllt, wann sie kommt."""

    key: str
    #: Überschrift für Menschen — steht so im Datenstand auf ``/haushalt``.
    label: str
    #: Ein Satz für Leserinnen, was diese Schicht beantwortet.
    was: str
    #: Zieltabelle (bei mehreren die führende — sie entscheidet den Bestand).
    tabelle: str
    #: In welchem Monat der Rat das Dokument üblicherweise bekommt (1–12).
    erwarteter_monat: int
    #: Kalenderjahr der Einbringung = Jahrgang + ``versatz``.
    versatz: int
    #: Wo das Dokument herkommt: ``ris`` = Anlage im Ratsinformationssystem
    #: (der Cron liest sie aus), ``stadt`` = Download von oldenburg.de (der
    #: Cron lädt bewusst nichts herunter, s. Modul-Kopf von check_finanzdaten).
    herkunft: str
    #: Welche Jahrgänge schon im Bestand sind.
    bestand: Callable[[CouncilStore], list[int]]
    erkennung: Erkennung | None = None
    #: Jahrgang eines Kandidaten — aus Label bzw. Textkopf, nie aus ``fetched_at``.
    jahrgang: Callable[[dict], int | None] | None = None
    #: Einlesen: ``(store, protokoll, nur_fehlende) -> dict``.
    einlesen: Callable[..., dict] | None = None
    #: Weitere Tabellen, die derselbe Lauf mitfüllt.
    nebentabellen: tuple[str, ...] = ()

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
        """Anlagen, die ein Dokument dieser Datenart sein könnten — mit
        Jahrgang, aber **ohne** Volltext.

        ``raw_text`` wird auf den Kopf beschnitten: Ein Jahresabschluss bringt
        400.000 Zeichen mit, und für die Frage „welcher Jahrgang ist das?"
        reichen die ersten Zeilen. Wer wirklich einliest, holt sich die Zeile
        noch einmal ganz (das tun die ``_lies_*``-Funktionen unten)."""
        if self.erkennung is None:
            return []
        sql, werte = self.erkennung.abfrage(
            f"document_id, label, url, n_pages, substr(raw_text, 1, {int(kopf_zeichen)}) AS kopf")
        rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
        for r in rows:
            r["jahrgang"] = self.jahrgang(r) if self.jahrgang else None
        return rows


# --- Jahrgang eines Kandidaten ----------------------------------------------

def _jahr_aus_label(row: dict) -> int | None:
    m = re.search(r"(20\d\d)", row.get("label") or "")
    return int(m.group(1)) if m else None


def _jahr_schlussbericht(row: dict) -> int | None:
    treffer = finanzberichte.pruefbericht_aus_anlage(row.get("label"), row.get("kopf"))
    return treffer["jahr"] if treffer else None


def _jahr_feststellungen(row: dict) -> int | None:
    return pruefberichte.erkenne_jahrgang(row.get("kopf") or "")


#: Erste Ansatzspalte im Tabellenkopf eines Teilhaushalts-Plans.
_ANSATZ = re.compile(r"Ansatz\s+(20\d\d)")


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


def _jahr_teilhaushalt(row: dict) -> int | None:
    return teilhaushalt_jahrgang(row.get("kopf"))


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


def bestandsschutz(p: Protokoll, was: str, alt: int, neu: int) -> bool:
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
    """
    if neu <= 0:
        if alt > 0:
            p.warnen(f"    {was}: 0 Zeilen gelesen, {alt} stehen in der Tabelle — "
                     f"Bestand bleibt unangetastet")
        return False
    if alt > 0 and neu < alt * SCHRUMPF_GRENZE:
        p.warnen(f"    {was}: nur {neu} statt bisher {alt} Zeilen "
                 f"({neu / alt * 100:.0f} %) — Bestand bleibt unangetastet")
        return False
    if alt and neu < alt:
        p.sagen(f"    {was}: {neu} Zeilen statt bisher {alt} — ersetzt")
    return True


def lies_jahresabschluesse(store: CouncilStore, p: Protokoll,
                           nur_fehlende: bool = False) -> dict:
    """Gesamtdokumente der Jahresabschlüsse — nicht die Rechenschaftsberichte
    und nicht die Prüfberichte, die dieselbe Jahreszahl im Titel tragen.

    Zwei Durchgänge: erst alle Jahrgänge lesen und prüfen, dann speichern.
    Die Vorjahres-Kette lässt sich nur über Dokumentgrenzen hinweg prüfen —
    dafür müssen der Jahrgang und sein Nachbar gelesen vorliegen. Deshalb
    liest auch der Cron-Lauf **alle** Dokumente und speichert nur die neuen:
    Ein neuer Jahrgang ohne seinen Vorgänger hätte keine Kette."""
    sql, werte = QUELLEN["jahresabschluss"].erkennung.abfrage("label, url, raw_text")
    rows = store._conn.execute(sql, werte).fetchall()  # noqa: SLF001
    vorhanden = set(store.ergebnisrechnung_jahre()) if nur_fehlende else set()

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
                         "label": r["label"], "url": r["url"]}

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
    mit_thh = verworfen = gruende_gesamt = geschuetzt = 0
    for jahr in sorted(gelesen):
        if jahr in verdaechtig:
            uebersprungen += 1
            continue
        if jahr in vorhanden:
            continue  # steht schon in der Tabelle — der Job fasst Bestand nicht an
        v = gelesen[jahr]
        posten, label, url = v["posten"], v["label"], v["url"]
        # Ersetzen heißt löschen und neu schreiben — nur gegen ein Ergebnis,
        # das den vorhandenen Stand trägt (siehe bestandsschutz).
        alt = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnisrechnung "
                             "WHERE jahr = ? AND thh_nr IS NULL", (jahr,))
        if not bestandsschutz(p, f"{jahr} Ergebnisrechnung", alt, len(posten)):
            geschuetzt += 1
            uebersprungen += 1
            continue
        store.save_ergebnisrechnung(jahr, posten, label, url)
        neu.append(jahr)
        e = next(x for x in posten if x["nr"] == 12)
        a = next(x for x in posten if x["nr"] == 20)
        arten = sorted({x["plan_art"] for x in posten})
        p.sagen(f"  {jahr}: {len(posten)} Posten · Erträge {e['plan']/1e6:.1f} → "
                f"{e['ergebnis']/1e6:.1f} · Aufwendungen {a['plan']/1e6:.1f} → "
                f"{a['ergebnis']/1e6:.1f} · Bezug {'/'.join(arten)}")
        if a["plan"] != a["ansatz"] or e["plan"] != e["ansatz"]:
            p.sagen(f"      ursprünglicher Ansatz: Erträge {e['ansatz']/1e6:.1f} · "
                    f"Aufwendungen {a['ansatz']/1e6:.1f}")

        # Zweite Ebene: dieselbe Rechnung je Teilhaushalt. Sie wird nur
        # übernommen, wenn ihre Summe zur Gesamtrechnung passt — in Plan UND
        # Ist. Sonst wurde für einen Teilhaushalt die falsche (in sich
        # stimmige) Tabelle gelesen, was zeilenweise nicht auffällt.
        thh = finanzberichte.parse_teilergebnisrechnungen(v["text"], jahr)
        alt_thh = _anzahl(store, "SELECT COUNT(*) FROM council_ergebnisrechnung "
                                 "WHERE jahr = ? AND thh_nr IS NOT NULL", (jahr,))
        if not bestandsschutz(p, f"{jahr} Teilhaushalte", alt_thh,
                              sum(len(x["posten"]) for x in thh)):
            geschuetzt += 1 if alt_thh else 0
        elif thh:
            passt, abweichung = finanzberichte.summenprobe(thh, posten)
            if not passt:
                p.warnen(f"    Teilhaushalte verworfen: Summe weicht um {abweichung*100:.1f} % "
                         f"von der Gesamtrechnung ab")
                verworfen += 1
            else:
                for x in thh:
                    store.save_ergebnisrechnung(jahr, x["posten"], label, url,
                                                thh_nr=x["thh_nr"], thh_name=x["thh_name"])
                p.sagen(f"    + {len(thh)} Teilhaushalte "
                        f"(Summenprobe {abweichung*100:.2f} % Abweichung)")
                mit_thh += 1

        # Das „Warum": Abschnitt 6.3.1 je Posten. Eintrittskarte ist der
        # Abgleich mit der Tabellenzeile — Betrag und Prozentsatz stehen in
        # der Überschrift des Blocks und müssen beide passen.
        roh = finanzberichte.parse_abweichungsgruende(v["text"], jahr)
        angenommen, abgelehnt = finanzberichte.pruefe_abweichungsgruende(roh, posten)
        for grund in abgelehnt:
            p.warnen(f"    Erläuterung verworfen — {grund}")
        alt_gruende = _anzahl(store, "SELECT COUNT(*) FROM council_abweichungsgruende "
                                     "WHERE jahr = ?", (jahr,))
        if bestandsschutz(p, f"{jahr} Erläuterungen", alt_gruende, len(angenommen)):
            store.save_abweichungsgruende(jahr, angenommen, label, url)
            gruende_gesamt += len(angenommen)
            p.sagen(f"    + {len(angenommen)} Erläuterungen zu Abweichungen")
        elif alt_gruende:
            geschuetzt += 1

    return {"neue_jahrgaenge": neu,
            "jahre": len(gelesen) - len(verdaechtig), "uebersprungen": uebersprungen,
            "jahre_mit_teilhaushalten": mit_thh, "thh_verworfen": verworfen,
            "kettenglieder_geprueft": glieder, "kette_gerissen": len(kette),
            "vorzeichen_repariert": vorzeichen_repariert,
            "bestand_geschuetzt": geschuetzt,
            "abweichungsgruende": gruende_gesamt}


def lies_schlussbericht_fundstellen(store: CouncilStore, p: Protokoll,
                                    nur_fehlende: bool = False) -> dict:
    """Schlussberichte des Rechnungsprüfungsamts als Fundstelle merken —
    nur Verweis, kein Inhalt („Das Rechnungsprüfungsamt hat diesen Abschluss
    geprüft")."""
    sql, werte = QUELLEN["rpa_fundstelle"].erkennung.abfrage("label, url, n_pages, raw_text")
    rows = store._conn.execute(sql, werte).fetchall()  # noqa: SLF001
    vorhanden = ({q["jahr"] for q in store.get_pruefbericht_quellen()}
                 if nur_fehlende else set())
    neu: list[int] = []
    gefunden = unlesbar = 0
    for r in rows:
        treffer = finanzberichte.pruefbericht_aus_anlage(r["label"], r["raw_text"])
        if not treffer:
            continue
        if treffer["jahr"] in vorhanden:
            continue
        store.save_pruefbericht_quelle(treffer["jahr"], r["label"], r["url"],
                                       r["n_pages"], treffer["lesbar"])
        neu.append(treffer["jahr"])
        gefunden += 1
        hinweis = "" if treffer["lesbar"] else "  (Volltext unbrauchbar, nur Verweis)"
        p.sagen(f'  {treffer["jahr"]}: {r["n_pages"]} Seiten{hinweis}')
        unlesbar += 0 if treffer["lesbar"] else 1
    return {"neue_jahrgaenge": neu,
            "pruefberichte": gefunden, "pruefberichte_ohne_text": unlesbar}


def lies_teilhaushalte(store: CouncilStore, p: Protokoll,
                       nur_fehlende: bool = False) -> dict:
    """Produktebene aus den Teilhaushalts-Plänen: was einzelne Aufgaben kosten,
    mit Produktnummer, Amt und Steckbrief.

    ``nur_fehlende`` schränkt auf Dokumente ein, deren Ansatz-Jahrgang noch
    nicht in ``council_produkte`` steht (siehe ``teilhaushalt_jahrgang``)."""
    sql, werte = QUELLEN["teilhaushalt"].erkennung.abfrage("label, url, raw_text")
    rows = [dict(r) for r in store._conn.execute(sql, werte)]  # noqa: SLF001
    vorhanden = set(store.produkte_jahre()) if nur_fehlende else set()
    if nur_fehlende:
        rows = [r for r in rows
                if teilhaushalt_jahrgang(r["raw_text"]) not in vorhanden]

    je_jahr: dict[int, int] = {}
    mit_feld: dict[str, int] = {f: 0 for f in STECKBRIEF}
    ohne = geschuetzt = 0
    for r in rows:
        produkte = finanzberichte.parse_teilergebnishaushalt(r["raw_text"] or "")
        if not produkte:
            ohne += 1
            continue
        for jahr in {x["jahr"] for x in produkte}:
            if jahr in vorhanden:
                continue
            teil = [x for x in produkte if x["jahr"] == jahr]
            # ``save_produkte`` löscht nichts, überschreibt aber Zeile für
            # Zeile. Verglichen wird deshalb je Teilhaushalt, nicht je Jahr:
            # Ein Dokument trägt immer nur seinen eigenen THH bei, gegen den
            # Jahresbestand gehalten sähe jedes Dokument wie ein Einbruch aus.
            for thh_nr in sorted({x.get("thh_nr") for x in teil}, key=lambda v: v or 0):
                stueck = [x for x in teil if x.get("thh_nr") == thh_nr]
                alt = _anzahl(store, "SELECT COUNT(*) FROM council_produkte "
                                     "WHERE jahr = ? AND thh_nr IS ?", (jahr, thh_nr))
                if not bestandsschutz(p, f"{jahr} THH{thh_nr}", alt, len(stueck)):
                    geschuetzt += 1 if alt else 0
                    continue
                store.save_produkte(jahr, stueck, r["label"], r["url"])
                je_jahr[jahr] = je_jahr.get(jahr, 0) + len(stueck)
                for feld in STECKBRIEF:
                    mit_feld[feld] += sum(1 for x in stueck if x.get(feld))
    for jahr in sorted(je_jahr):
        p.sagen(f"  {jahr}: {je_jahr[jahr]} Produkt-Zeilen")
    if ohne:
        # Der eigentliche Frühwarnwert dieses Laufs: Dokumente, die aussehen
        # wie ein Teilhaushalts-Plan, aus denen der Parser aber nichts holt.
        p.warnen(f"  {ohne} Dokument(e) ohne lesbare Produkt-Tabelle")

    # Abdeckung je Feld — gezählt wird der TABELLENSTAND, nicht die Zahl der
    # gelesenen Zeilen: Dieselbe Produktnummer kommt in mehreren Dokumenten
    # desselben Jahres vor und überschreibt sich, die Summe oben ist also
    # größer als die Tabelle. Auf der Seite steht später der Tabellenstand.
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
    return {"neue_jahrgaenge": sorted(je_jahr), "dokumente": len(rows),
            "ohne_treffer": ohne, "bestand_geschuetzt": geschuetzt,
            "produkte": sum(je_jahr.values()),
            "in_tabelle": gesamt, "steckbrief": abdeckung}


def lies_pruefungsfeststellungen(store: CouncilStore, p: Protokoll,
                                 nur_fehlende: bool = False,
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
    vorhanden = set(store.pruefbericht_jahre()) if nur_fehlende else set()

    je_jahr: dict[int, dict] = {}
    geschuetzt = 0
    for r in rows:
        ergebnis = pruefberichte.parse_feststellungen(r["raw_text"] or "")
        jahr = ergebnis["jahr"]
        if jahr is None:
            continue  # Stiftung, Eigenbetrieb oder kaputter Textextrakt
        if jahr in vorhanden:
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
        if not bestandsschutz(p, f"{jahr} Feststellungen", alt, len(gefunden)):
            geschuetzt += 1 if alt else 0
            continue
        marken = Counter(f["marke"] for f in gefunden)
        if not trocken:
            store.save_pruefbericht(jahr, gefunden, r["label"], r["url"])
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
        jahrgang=_jahr_aus_label,
        bestand=lambda s: s.ergebnisrechnung_jahre(),
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
        jahrgang=_jahr_schlussbericht,
        bestand=lambda s: [q["jahr"] for q in s.get_pruefbericht_quellen()],
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
        jahrgang=_jahr_feststellungen,
        bestand=lambda s: s.pruefbericht_jahre(),
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
        erkennung=Erkennung(label_muster=("%THH%",), mindest_seiten=40),
        jahrgang=_jahr_teilhaushalt,
        bestand=lambda s: s.produkte_jahre(),
        einlesen=lies_teilhaushalte,
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
        bestand=lambda s: s.haushalt_years(),
    ),
):
    QUELLEN[_q.key] = _q

#: Reihenfolge für Oberfläche und Protokoll — vom Groben zum Feinen.
REIHENFOLGE = ("haushaltsplan", "jahresabschluss", "teilhaushalt",
               "rpa_fundstelle", "pruefungsfeststellungen")


def datenstand(store: CouncilStore, heute: date | None = None) -> list[dict]:
    """Was für welchen Jahrgang vorliegt — und was als Nächstes erwartet wird.

    Eine Zeile je Datenart mit den vorhandenen Jahrgängen, den Lücken
    dazwischen, dem nächsten erwarteten Jahrgang und der Angabe, ob er
    überfällig ist. Beantwortet die Leserfrage „warum steht hier 2024 und
    nicht 2025?" an einer Stelle, statt sie auf neun Seiten zu wiederholen."""
    heute = heute or date.today()
    zeilen = []
    for key in REIHENFOLGE:
        q = QUELLEN[key]
        jahre = sorted(set(q.bestand(store)))
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
            "automatisch": q.automatisch,
            "jahrgaenge": jahre, "luecken": luecken,
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
