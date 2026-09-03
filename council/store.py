from __future__ import annotations

import contextlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sqlite3
from council import geld as _geld

from .parties import order_key, parties_for_faction
from . import importance as _importance
from council.kontaktdaten import maskieren
from kern.dbfehler import tabelle_fehlt
from council.store_helfer import _dedup_keys, _int_or_none
from council.store_fundstuecke import FundstueckeMixin
from council.store_haushalt import HaushaltMixin
from council.store_orte import CONCRETE_LOCATION_KINDS, OrteMixin
from council.store_personen import PersonenMixin
from council.store_presse import PresseMixin
from council.store_quiz import QuizMixin
# Schema, Migration und die Vokabulare des Umbenennungs-Umbaus liegen seit
# 09/2026 in `store_schema.py` — `_migrate` allein war 2.458 Zeilen. Sie werden
# hier weiter angeboten, weil mehrere Wächter-Tests sie über `council.store`
# holen: Der Umzug hat die Datei geteilt, nicht die Zuständigkeit.
from council.store_schema import (  # noqa: F401
    _FACH_SPALTEN,
    _GELD_SPALTEN,
    _REST_SPALTEN,
    _STRUKTUR_SPALTEN,
    SCHEMA,
    TABELLEN_UMBENANNT,
    SchemaMixin,
)
from council.store_sitzungen import SitzungenMixin
from council.store_themen import ThemenMixin
from council.store_wortbeitraege import WortbeitraegeMixin












#: Tabellen dieser Datenbank, die an einem Konto hängen.
#:
#: Die Konto-Löschung wohnt in ``kern.store`` und räumte lange nur die dortigen
#: Tabellen ab — der Wächter-Test (``test_account_deletion``) prüfte ebenfalls
#: nur jenes Schema und konnte diese Lücke also gar nicht sehen. Hier liegen
#: aber Verhaltensspuren: *welche* Sitzungen jemandem gemeldet wurden. Das ist
#: personenbezogen und muss beim Löschen mit weg (DSGVO, Recht auf Löschung).
COUNCIL_USER_OWNED_TABLES: tuple[tuple[str, str], ...] = (
    ("committee_notifications", "owner_id"),
    ("session_followups_sent", "owner_id"),
    # KI-Feedback (5a/I-03): Frage und Grund sind Freitext und können
    # Persönliches tragen — beim Konto-Löschen mit weg, kein Sonderfall.
    ("council_qa_feedback", "user_id"),
)











# Die Store-Mixins der Modul-Facetten (council/geld/): je Facette eine
# Methode `(woerter, year=None)`, die mit `_conn`, `_trifft` und `_beleg`
# arbeitet. Der Stern ist Absicht — wer eine Facette baut, fasst diese
# Datei nicht an.
class CouncilStore(FundstueckeMixin, HaushaltMixin, OrteMixin, PersonenMixin,
                   PresseMixin, QuizMixin, SchemaMixin, SitzungenMixin,
                   ThemenMixin, WortbeitraegeMixin, *_geld.MIXINS):
    def __init__(self, path: str | Path, ratslotse_db_path: str | Path | None = None):
        self._path = path
        # Sibling ratslotse.sqlite holds the chat_id→owner_id map for the migration.
        if ratslotse_db_path is None and isinstance(path, (str, Path)) and str(path) != ":memory:":
            ratslotse_db_path = Path(path).parent / "ratslotse.sqlite"
        self._ratslotse_db_path = ratslotse_db_path
        # check_same_thread=False wie im Konten-Store: FastAPI führt sync-Dependencies
        # und Endpoint in (potenziell verschiedenen) Threadpool-Threads aus — die
        # Verbindung wandert also zwischen Threads. Sicher, weil jede Anfrage ihre
        # eigene Store-Instanz bekommt (keine parallele Nutzung EINER Verbindung).
        self._conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Kontaktdaten aus dem Text nehmen, der in einen SUCHINDEX geht — als
        # SQLite-Funktion, damit `rebuild_fts()` eine einzige INSERT-SELECT
        # bleibt und nicht zu einer Schleife in Python wird
        # (`council/kontaktdaten.py`). Gespeichert wird weiterhin alles.
        self._conn.create_function("ohne_kontaktdaten", 1, maskieren,
                                   deterministic=True)
        # WAL + busy_timeout: scraper cron and the web API share this file.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        # VOR dem Schema: Sonst legt `CREATE TABLE IF NOT EXISTS` die neue,
        # englische Tabelle leer an, der Zielname ist belegt, und die
        # Umbenennung unterbleibt für immer — die Daten lägen weiter unter dem
        # alten Namen, unsichtbar. Genau so ist am 01.09.2026 die Einwilligung
        # in `web_users` verschwunden, nur eben spaltenweise.
        self._tabellen_umbenennen()
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._migrate()
        #: Läuft gerade eine geklammerte Transaktion (siehe ``transaktion``)?
        self._sammelt = False
        #: Zwischenspeicher für ``personen_kanon`` — je Instanz, also je Anfrage.
        self._kanon: dict[str, str] | None = None
        # Namensvarianten derselben Person (s. _personen_varianten): einmal je
        # Store-Instanz gebaut, also einmal je Web-Anfrage.
        self._varianten_cache: dict[str, str] | None = None
        self._runtime_places_cache: tuple | None = None
        self._place_aliases_cache: dict[str, str] | None = None

    @contextlib.contextmanager
    def transaktion(self):
        """Mehrere ``save_*``-Aufrufe zu **einer** Transaktion klammern.

        Ohne die Klammer committet jeder Aufruf für sich. Für einen
        Jahresabschluss sind das 1 + n + 1 Transaktionen (Gesamtrechnung, je
        Teilhaushalt eine, Erläuterungen) — bricht der Lauf dazwischen ab,
        bleibt der Jahrgang halb in der Datenbank stehen. Genau das darf einem
        unbeaufsichtigten Cron nicht passieren, der einen halben Jahrgang
        anschließend für erledigt hält.

        Verschachtelung ist erlaubt und tut nichts: Die innerste Klammer
        überlässt Commit und Rollback der äußersten. Die ``save_*``-Methoden
        benutzen sie deshalb selbst — ein Aufruf ohne äußere Klammer verhält
        sich wie vorher."""
        if self._sammelt:
            yield  # schon geklammert — die äußere Klammer committet
            return
        self._sammelt = True
        try:
            with self._conn:
                yield
        finally:
            self._sammelt = False


    #: Die Eimer eines Tagesordnungs-Diffs. NUR die oberste Ebene — `anlagen`
    #: ist dort ein Eimer, INNERHALB eines Punktes aber dessen Anlagenliste,
    #: und die heißt weiter so.
    _DIFF_EIMER = {
        "neu": "new", "entfernt": "removed", "verschoben": "moved",
        "umformuliert": "reworded", "vorlage": "template", "anlagen": "attachments",
    }






    #: `art` → `kind` in zehn Tabellen. Steht GANZ VORNE in `_migrate`, weil
    #: mehrere Wert-Migrationen weiter unten auf der Spalte arbeiten
    #: (`council_group_entities`, `council_taxes`, `council_tax_plan`):
    #: Liefe die Umbenennung später, fänden sie ihre Spalte nicht und kehrten
    #: still zurück — die Werte blieben deutsch, ohne dass etwas auffiele.
    _ART_TABELLEN = (
        "council_income_budget", "council_tax_rates", "council_provenance",
        "council_group_entities", "council_supplementary_approvals", "council_staff_plan",
        "council_taxes", "council_tax_plan", "council_templates",
        "council_speeches",
    )







    #: Wie eine Tabelle ihre Herkunft bisher führte: (Label-Spalte,
    #: URL-Spalte, Quellenart). Drei Schreibweisen für dieselbe Sache — genau
    #: das war der Anlass für `council/herkunft.py`.
    #:
    #: Die Quellenart steht hier nur, wo sie aus der Tabelle folgt. Bei
    #: `council_budget` folgt sie das nicht: Ein Jahrgang kam als PDF von
    #: oldenburg.de, ein anderer als CSV aus dem Open-Data-Portal — dort
    #: entscheidet die URL (s. `_herkunft_art_aus_url`).
    _HERKUNFT_ALTFELDER: dict[str, tuple[str | None, str, str | None]] = {
        "council_budget":             (None, "source_url", None),
        "council_taxes":              (None, "source_url", "opendata"),
        "council_tax_capacity":          (None, "source_url", "opendata"),
        "council_einwohner":            (None, "source_url", "opendata"),
        "council_income_statement":     ("source_label", "source_url", "ris"),
        # Neu mit der Kassensicht, ohne Altbestand — nichts nachzutragen.
        "council_cash_flow_statement":       (None, None, "ris"),
        # Ebenso die Bilanz und ihre Erläuterungen: erst mit der Herkunft
        # entstanden, keine Altspalten.
        "council_balance_sheet":               (None, None, "ris"),
        "council_balance_sheet_notes": (None, None, "ris"),
        "council_variance_reasons":   ("source_label", "source_url", "ris"),
        "council_audit_report_sources": ("label", "url", "ris"),
        "council_products":             ("source_label", "source_url", "ris"),
        "council_audit_reports":        ("source_label", "source_url", "ris"),
        # Die beiden Konzern-Tabellen sind erst mit der Herkunft entstanden
        # und tragen gar keine Altspalten. Sie stehen hier trotzdem, weil
        # `_herkunft_nachtragen` jede Tabelle aus `HERKUNFT_TABELLEN`
        # nachschlägt; ohne URL-Spalte kehrt es sofort zurück, ohne etwas zu
        # tun. Ein Eintrag „nichts nachzutragen" ist billiger als eine
        # Ausnahme im Nachrüst-Weg.
        "council_group_items":       (None, "source_url", "ris"),
        "council_group_entities":      (None, "source_url", "ris"),
        # Ebenso der Städtevergleich: erst mit der Herkunft entstanden, keine
        # Altspalten, nichts nachzutragen.
        "council_city_comparison":     (None, "source_url", "lsn"),
        # Und die Gewerbesteuerstatistik, ebenfalls vom Landesamt.
        "council_trade_tax_statistics": (None, "source_url", "lsn"),
        # Und die Planjahre aus dem Gesamtergebnishaushalt.
        "council_income_budget":     (None, "source_url", "ris"),
        # Ebenso die Investitionen des Finanzhaushalts: neu, ohne Altspalten,
        # Herkunft ausschließlich über `herkunft_id`.
        "council_investments":        (None, "source_url", "opendata"),
        # Und die Maßnahmen aus Anlage 004: ebenfalls neu, ebenfalls ohne
        # Altspalten. Der Eintrag muss trotzdem stehen — `_herkunft_nachtragen`
        # schlägt hier nach, bevor es merkt, dass es nichts nachzutragen gibt.
        "council_investment_measures": (None, "source_url", "ris"),
        # Das Ist-Gegenstück aus dem Statistischen Jahrbuch — anders als Plan
        # und Programm kommt es weder vom Portal noch aus dem RIS, sondern von
        # oldenburg.de.
        "council_investments_actual":       (None, "source_url", "city"),
        "council_investments_actual_kinds": (None, "source_url", "city"),
        "council_investments_actual_rejected": (None, "source_url", "city"),
        # Der Stellenplan — ebenfalls neu und ohne Altbestand.
        "council_staff_plan":          (None, "source_url", "ris"),
        # Und die Schuldenzeitreihe aus dem Statistischen Jahrbuch.
        "council_debt":             (None, "source_url", "city"),
        # Die lange Ausgabenreihe: zwei Quellen — das Jahrbuch der Stadt und
        # das Open-Data-Portal —, deshalb keine feste Art. Nachzutragen ist
        # ohnehin nichts, die Tabelle ist neu.
        "council_expense_series":        (None, "source_url", None),
        # Der Bürgschaftsbestand: eine Quelle, der Jahresabschluss als Anlage
        # im Ratsinformationssystem.
        "council_buergschaften":        (None, "source_url", "ris"),
        "council_fixed_assets":       (None, "source_url", "ris"),
        # Die Kennzahlen und ihre Rechenwege: Anlage des Rechenschaftsberichts,
        # also ebenfalls ein Dokument im Ratsinformationssystem.
        "council_indicators":           (None, "source_url", "ris"),
        "council_indicator_formulas":     (None, "source_url", "ris"),
        "council_vermoegensgruppen":    (None, "source_url", "ris"),
        # Die dritte Schuldenzahl: Tabellenband der Statistischen Ämter,
        # also weder Stadt noch Ratsinformationssystem — eigene Art "lsn"
        # wie beim Städtevergleich.
        "council_integrated_debt": (None, "source_url", "lsn"),
        # Die Nachbewilligungen: neu, ohne Altspalten. Beide Quellen liegen im
        # Ratsinformationssystem — die Vorlagen selbst und der
        # Rechenschaftsbericht als Anlage zum Jahresabschluss.
        "council_supplementary_approvals":        (None, "source_url", "ris"),
        "council_supplementary_years":    (None, "source_url", "ris"),
        "council_supplementary_channels":  (None, "source_url", "ris"),
        # Die Zuwendungen: Quelle sind Ratsvorlagen im Bürgerinfo, also „ris".
        # Nachzutragen ist nichts, beide Tabellen sind neu.
        "council_donations":              (None, "source_url", "ris"),
        "council_donations_rejected":    (None, "source_url", "ris"),
        # Die beiden Steuertabellen des Jahrbuchs — neu, ohne Altbestand.
        "council_tax_plan":           (None, "source_url", "city"),
        "council_tax_rates":           (None, "source_url", "city"),
        # Gebührenbedarf und Anlage-4-Tarife sind neu mit Herkunft entstanden;
        # sie haben keine doppelten Altspalten, die nachzutragen wären.
        "council_fees":            (None, "source_url", "ris"),
        "council_fee_rates":      (None, "source_url", "ris"),
        # Der Beteiligungsbericht: ebenfalls erst mit der Herkunft entstanden.
        # Seine Dokumente kommen von oldenburg.de, nicht aus dem Bürgerinfo.
        "council_companies":            (None, "source_url", "city"),
        "council_company_texts":        (None, "source_url", "city"),
        "council_company_indicators":   (None, "source_url", "city"),
        "council_company_people":     (None, "source_url", "city"),
        "council_company_owners":  (None, "source_url", "city"),
        # Der Haushaltsvollzug: neu, ohne Altbestand, ohne Altspalten. Der
        # Eintrag muss trotzdem stehen — `_herkunft_nachtragen` schlägt hier
        # nach, bevor es merkt, dass es nichts nachzutragen gibt.
        "council_budget_execution": (None, "source_url", "ris"),
        "council_liquidity": (None, "url", "ris"),
    "council_enterprise_accounts": (None, None, "ris"),
        # Kredite und Zinsen: neu, ohne Altbestand — derselbe Platzhalter.
        "council_loan_notices": (None, "document_url", "ris"),
        "council_loan_items": (None, "document_url", "ris"),
    }

    @staticmethod
    def _herkunft_art_aus_url(url: str | None) -> str | None:
        """Quellenart aus einer gespeicherten URL — abgeleitet, nicht geraten.

        Entschieden wird an Zeichenketten, die wörtlich in der URL stehen —
        das Portal, die Stadt-Domain, das Bürgerinfo. Alles andere (etwa ein
        ``file:``-Pfad aus einem Lauf mit ``--pdf``) bleibt ohne Herkunft,
        statt eine Art zu erfinden; ``herkunft_luecken()`` zeigt es dann an."""
        if not url:
            return None
        if "opendata.oldenburg.de" in url:
            return "opendata"
        if "oldenburg.de" in url:
            return "city"
        if "buergerinfo" in url or "/getfile" in url:
            return "ris"
        return None



    def _dokument_zu_url(self, url: str | None) -> int | None:
        """Die `council_attachments.document_id` zu einer Anlagen-URL.

        Der stabile Anker, den der Altbestand nicht mitführte. Nur bei einem
        **eindeutigen** Treffer — zwei Anlagen unter derselben URL wären ein
        Fall für einen Blick, nicht für eine Vermutung."""
        if not url:
            return None
        try:
            treffer = self._conn.execute(
                "SELECT document_id FROM council_attachments WHERE url = ? LIMIT 2",
                (url,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return treffer[0][0] if len(treffer) == 1 else None


    def delete_owner_data(self, owner_id: int) -> int:
        """Alles aus dieser Datenbank löschen, was an einem Konto hängt.

        Gegenstück zu ``Store.delete_web_user``: Die Konto-Löschung muss beide
        Datenbanken abräumen, es gibt zwischen ihnen keine Fremdschlüssel, die
        das von allein täten. Gibt die Zahl gelöschter Zeilen zurück.
        """
        n = 0
        with self._conn:
            for tabelle, spalte in COUNCIL_USER_OWNED_TABLES:
                cur = self._conn.execute(f"DELETE FROM {tabelle} WHERE {spalte} = ?", (owner_id,))
                n += cur.rowcount or 0
        return n

    def close(self) -> None:
        self._conn.close()

    def admin_stats(self) -> dict:
        """Council counts for the admin dashboard (read-only)."""
        c = self._conn

        def one(sql: str, *p):
            row = c.execute(sql, p).fetchone()
            return row[0] if row else 0

        # „Läuft der Scraper?“ ist eine andere Frage als „gab es neue Sitzungen?“:
        # council_sessions wird nur beschrieben, wenn eine Sitzung mit
        # veröffentlichter Tagesordnung im Kalender steht — in der sitzungsfreien
        # Zeit also wochenlang gar nicht. Der Terminplan dagegen wird bei jedem
        # Lauf neu geschrieben und ist damit der verlässliche Puls.
        last_session_import = one("SELECT MAX(fetched_at) FROM council_sessions") or None
        last_scheduled = one("SELECT MAX(fetched_at) FROM council_scheduled_sessions") or None
        last_fetch = max([t for t in (last_session_import, last_scheduled) if t], default=None)
        return {
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "upcoming": one("SELECT COUNT(*) FROM council_sessions WHERE session_date >= date('now')"),
            "agenda_items": one("SELECT COUNT(*) FROM council_agenda_items"),
            "committees": one("SELECT COUNT(*) FROM committees"),
            # Design 20a — Ratsinfo-Import-Karte:
            "decisions": one("SELECT COUNT(*) FROM council_decisions"),
            "decisions_with_ki": one("SELECT COUNT(*) FROM council_decisions WHERE policy_field IS NOT NULL"),
            "last_fetch": last_fetch,
            # Stunden seit dem letzten Lauf — die Ampel darf nicht „heute schon
            # gelaufen?“ fragen, sonst steht sie jeden Morgen vor dem 8-Uhr-Cron
            # auf Rot, obwohl alles läuft (Läufe: 8 und 14 Uhr → max. ~18 h).
            "hours_since_fetch": (
                round((datetime.utcnow() - datetime.fromisoformat(last_fetch)).total_seconds() / 3600, 1)
                if last_fetch else None),
            "last_session_import": last_session_import,
            "next_session": one(
                "SELECT MIN(session_date) FROM ("
                " SELECT session_date FROM council_sessions WHERE session_date >= date('now')"
                " UNION ALL"
                " SELECT session_date FROM council_scheduled_sessions WHERE session_date >= date('now'))") or None,
            "fetched_today": one(
                "SELECT (SELECT COUNT(*) FROM council_sessions WHERE substr(fetched_at,1,10) = date('now'))"
                " + (SELECT COUNT(*) FROM council_scheduled_sessions WHERE substr(fetched_at,1,10) = date('now'))"),
        }

    def public_stats(self) -> dict:
        """Headline aggregate counts for the public landing page (no content)."""
        c = self._conn

        def one(sql: str) -> int:
            row = c.execute(sql).fetchone()
            return row[0] if row else 0

        return {
            "decisions": one("SELECT COUNT(*) FROM council_decisions WHERE kind = 'decision'"),
            "sessions": one("SELECT COUNT(*) FROM council_sessions"),
            "entities": one("SELECT COUNT(*) FROM council_entities"),
        }

    def alert_already_sent(self, ksinr: int, topic_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM council_alerts_sent WHERE ksinr = ? AND topic_id = ?",
            (ksinr, topic_id),
        ).fetchone()
        return row is not None

    def mark_alert_sent(self, ksinr: int, topic_id: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO council_alerts_sent (ksinr, topic_id, sent_at) VALUES (?,?,?)",
                (ksinr, topic_id, now),
            )

    # Kommende Sitzungen kommen aus ZWEI Quellen: echten Sitzungen mit
    # Tagesordnung und bloß terminierten aus dem Kalender. Liste und Zählung
    # müssen dieselbe Menge meinen — deshalb steht die Bedingung genau einmal
    # hier und wird von beiden benutzt.
    _UPCOMING_FROM = """
        FROM (
            SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                   COUNT(ci.id) AS n_items
            FROM council_sessions cs
            LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
            WHERE cs.session_date >= ?
            GROUP BY cs.ksinr
            UNION ALL
            SELECT NULL AS ksinr, ss.committee, ss.session_date, ss.session_time, ss.location,
                   0 AS n_items
            FROM council_scheduled_sessions ss
            WHERE ss.session_date >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM council_sessions cs2
                  WHERE cs2.committee = ss.committee AND cs2.session_date = ss.session_date
              )
        )
    """





    #: Tagesordnungspunkte, die in jeder Sitzung stehen und niemanden
    #: interessieren. Am Bestand gemessen: 20 von 53 kommenden TOPs.
    #: „- Bericht der Verwaltung" ist ein ZUSATZ, kein Punkt: Er hängt an den
    #: spannendsten Titeln der Woche („Ermittlungen Abfallentsorgung
    #: Fliegerhorst (CDU-Fraktion) - Bericht der Verwaltung"). Ein auf das
    #: Zeilenende verankertes Muster warf davon neun weg, darunter fast alle
    #: Fraktionsanträge — deshalb greift die Formalie nur, wenn der Punkt
    #: NICHTS ANDERES ist als diese Floskel.
    _FORMALIE_RE = re.compile(
        r"Beschlussf[äa]higkeit|Genehmigung der Tagesordnung|Genehmigung des Protokolls|"
        r"Einwohnerfragestunde|^Mitteilungen|Anfragen und Anregungen|Verschiedenes|"
        r"^\s*Bericht(?:e)? der Verwaltung\s*$|Wahl der Schriftf[üu]hrung",
        re.IGNORECASE)

    #: „(CDU-Fraktion vom 10.06.2026)", „(Fraktionen BSW und SPD)", „(FDP-Fraktion …)"
    _ANTRAG_RE = re.compile(r"\(\s*(?:die\s+)?(?:Fraktion(?:en)?|Gruppe|Ratsherr|Ratsfrau)\b|"
                            r"[A-ZÄÖÜ][\wÄÖÜäöüß/. ]{1,24}-Fraktion\b", re.IGNORECASE)

    _PERSONALIE_RE = re.compile(
        r"Berufung|Umbesetzung|Bestellung\s+(?:eines|einer)|"
        r"Wahl\s+(?:des|der|eines|einer)\s+(?:stellv|Vorsitz|Schriftf)|"
        r"beratende[sn]?\s+Mitglied", re.IGNORECASE)

    #: Bindende Gegenstände: Was hier greift, wirkt über den Tag hinaus —
    #: Satzungen, Gebühren, Haushalt, Bauleitplanung, Verträge, Grundsätze.
    #: Genau die Rubrik „Bindungswirkung" des Tragweite-Prompts, nur als Regel.
    _BINDEND_RE = re.compile(
        r"Satzung|Geb[üu]hren|Beitrags|Entgelt|Haushalt|Nachtragshaushalt|"
        r"Bebauungsplan|Fl[äa]chennutzungsplan|Bauleitplan|Grundsatzbeschluss|"
        r"Vertrag|Vereinbarung|Konzession|Verordnung|Richtlinie", re.IGNORECASE)

    #: Wo entschieden wird, wiegt schwerer als wo vorberaten wird. Der Rat und
    #: der Verwaltungsausschuss binden die Stadt, ein Fachausschuss bereitet vor.
    _GREMIUM_GEWICHT = ((("stadtrat", "rat der stadt"), 1.5), (("verwaltungsausschuss",), 1.0))

    #: Ab hier gilt ein Punkt als Schwerpunkt der Woche und wird hervorgehoben.
    #: Darunter zeigt die Karte ihre Zeilen ohne Hervorhebung — lieber kein
    #: Schwerpunkt als ein behaupteter.
    TOP_MINDEST = 60

    #: Mehr als zwei Hervorhebungen entwerten sich gegenseitig.
    TOP_MAX = 2

    #: Unter diesem Wert kommt ein Punkt gar nicht auf die Karte. Skala ist die
    #: Tragweite (0–100, s. council/impact.py): 20 ≈ Bericht zur Kenntnis,
    #: 35 ≈ Maßnahme an einer Einrichtung. Darunter lohnt keine Zeile.
    WICHTIG_MINDEST = 30

    #: Alte Heuristik-Schwelle — nur noch für die Umrechnung relevant.
    RANG_MINDEST = 1.5

    #: Lazy geladener Wiederkehr-Zähler (s. _wiederkehr).
    _wiederkehr_cache: dict[str, int] | None = None

    #: „(CDU-Fraktion vom 14.07.2026)" → Antragsteller „CDU-Fraktion"; der
    #: Zusatz frisst sonst die halbe Zeile auf der Karte (im Browser gesehen).
    _ANTRAGSTELLER_RE = re.compile(
        r"\s*\(\s*(?:die\s+)?(?P<wer>[^)]*?)\s*(?:vom\s+\d{1,2}\.\d{1,2}\.\d{2,4})?\s*\)")
    #: Verfahrens-Anhängsel am Titelende, die auf der Karte nichts erklären.
    _TITEL_ANHANG_RE = re.compile(
        r"\s*[-–]\s*(?:\w*[Aa]ntrag mit Bericht der Verwaltung|Bericht(?:e)? der Verwaltung|"
        r"Beschlussantrag|Berichtsantrag|Antrag|Bericht|Beschluss|Vorlage|Kenntnisnahme)\s*$",
        re.IGNORECASE)

    #: „Ö 11.3" → Präfix „Ö", Nummer „11.3". Das Präfix ist zugleich der
    #: Öffentlichkeitsmarker (Ö/N) und gehört zur Nummer, nicht davor weg.
    _TOP_NUMMER_RE = re.compile(r"^\s*([A-Za-zÖÄÜöäü]+)\s+([\d.]+?)\.?\s*$")

    #: Wörter, die in Tagesordnungs-Überschriften stehen, ohne einen
    #: Gegenstand zu benennen — sie dürfen keine Gruppe begründen.
    _RUBRIK_WORTE = frozenset({
        "antraege", "antrag", "fraktionen", "fraktion", "gruppen", "gruppe",
        "ratsund", "ausschussmitglieder", "mitglieder", "berichte", "bericht",
        "anfragen", "anregungen", "mitteilungen", "verschiedenes", "verwaltung",
        "beschluss", "beschluesse", "vorlagen", "sonstiges", "genehmigung",
        "protokolle", "protokolls", "tagesordnung", "oeffentlicher", "teil",
    })
















    def anlagen_fuer(self, kvonr: int) -> list[dict]:
        """Anlagen einer Vorlage mit Text — Anträge zuerst, dann die kürzeste.

        Die Reihenfolge ist die halbe Miete: Der Antrag einer Fraktion hat
        3.000 Zeichen und sagt, was jemand WILL. Der „Materialband
        Lupenpläne" derselben Vorlage hat 400.000 und ist als OCR-Text eine
        Kartensammlung. Wer nach Länge sortiert, bekommt zuerst das Argument
        und läuft nicht Gefahr, sein Budget mit Planwerk zu füllen.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT label, is_motion, applicants, raw_text FROM council_attachments "
            "WHERE kvonr = ? AND raw_text IS NOT NULL AND length(raw_text) > 0 "
            "ORDER BY is_motion DESC, length(raw_text) ASC", (kvonr,))]


















    # ---- protocols / decisions / attendance ----


    def _insert_decision(self, ksinr, position, kind, parent_item, item_number, title,
                         official_text, outcome, vote, no_votes, abstentions, factions,
                         template_number, kvonr, raw_result) -> None:
        cur = self._conn.execute(
            "INSERT INTO council_decisions "
            "(ksinr, position, kind, parent_item, item_number, title, official_text, outcome, "
            " vote, no_votes, abstentions, factions, template_number, kvonr, raw_result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ksinr, position, kind, parent_item, item_number, title, official_text, outcome,
             vote, _int_or_none(no_votes), _int_or_none(abstentions),
             json.dumps(factions or [], ensure_ascii=False),
             template_number, _int_or_none(kvonr), raw_result),
        )
        # Nennt der Abstimmungssatz Fraktionen ausdrücklich (Gegenstimmen/
        # Enthaltungen), landen sie strukturiert in council_decision_votes —
        # neue Protokolle tragen ihre Teilvoten damit ab Import.
        if raw_result:
            from council.votes import parse_raw_result
            parsed = parse_raw_result(raw_result)
            if parsed:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO council_decision_votes (decision_id, faction, stance) "
                    "VALUES (?, ?, ?)",
                    [(cur.lastrowid, f, s) for f, s in parsed],
                )

    def save_protocol(
        self,
        ksinr: int,
        document: dict,
        meta: dict,
        raw_text: str,
        n_pages: int,
        model: str,
        decisions: list[dict],
        attendance: list[dict],
        status: str = "ok",
        page_offsets: list[int] | None = None,
    ) -> None:
        """Persist a parsed protocol with its decisions + attendance (replacing any
        prior rows for this session). One transaction."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, protocol_nr, session_start, session_end, "
                " raw_text, n_pages, page_offsets, model, extracted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ksinr, document.get("document_id"), document.get("url"), meta.get("protocol_nr"),
                 meta.get("session_start"), meta.get("session_end"), raw_text, n_pages,
                 json.dumps(page_offsets) if page_offsets else None, model, now, status),
            )
            # Teilvoten hängen an den decision-ids — vor dem Ersetzen der
            # Beschlüsse mitlöschen, sonst bleiben Waisen zurück (dieselbe
            # Falle wie bei den Themen-Treffern, #340).
            self._conn.execute(
                "DELETE FROM council_decision_votes WHERE decision_id IN "
                "(SELECT id FROM council_decisions WHERE ksinr = ?)", (ksinr,))
            self._conn.execute("DELETE FROM council_decisions WHERE ksinr = ?", (ksinr,))
            self._conn.execute("DELETE FROM council_attendance WHERE ksinr = ?", (ksinr,))
            pos = 0
            for d in decisions:
                self._insert_decision(ksinr, pos, "decision", None,
                                      d.get("item_number"), d.get("title"), d.get("official_text"),
                                      d.get("outcome"), d.get("vote"), d.get("no_votes"),
                                      d.get("abstentions"), d.get("factions"),
                                      d.get("template_number"), d.get("kvonr"), d.get("raw_result"))
                pos += 1
                for sv in d.get("sub_votes") or []:
                    self._insert_decision(ksinr, pos, "subvote", d.get("item_number"),
                                          d.get("item_number"), sv.get("description"), None,
                                          sv.get("outcome"), sv.get("vote"), sv.get("no_votes"),
                                          sv.get("abstentions"), sv.get("factions"),
                                          None, None, sv.get("raw_result"))
                    pos += 1
            for a in attendance:
                self._conn.execute(
                    "INSERT INTO council_attendance (ksinr, name, party, role, note) VALUES (?, ?, ?, ?, ?)",
                    (ksinr, a.get("name"), a.get("party"), a.get("role"), a.get("note")),
                )
            # Regex-Ernte (council.ernte): Sitzungsort aus dem Protokollkopf in die
            # Session übernehmen (der Terminplan liefert ihn leer) und Beschlüsse
            # über die Vorlagen-Nummer an ihre kvonr hängen.
            from council import ernte

            ort = ernte.sitzungsort(raw_text)
            if ort:
                self._conn.execute(
                    "UPDATE council_sessions SET location = ? WHERE ksinr = ? AND location = ''",
                    (ort, ksinr),
                )
            # Auch Revisions-Zitate („22/0348/1") an die Basis-Vorlage
            # („22/0348") hängen — exakter Treffer gewinnt vor dem Präfix
            # (Review-Befund E2: sonst blieben kvonr und deviation NULL,
            # obwohl get_vorlage_by_nr die Vorlage längst auflöst).
            self._conn.execute(
                "UPDATE council_decisions SET kvonr = COALESCE("
                "(SELECT MAX(v.kvonr) FROM council_templates v WHERE v.template_number = council_decisions.template_number), "
                "(SELECT MAX(v.kvonr) FROM council_templates v "
                " WHERE instr(council_decisions.template_number, v.template_number || '/') = 1)) "
                "WHERE ksinr = ? AND kvonr IS NULL AND template_number IS NOT NULL",
                (ksinr,),
            )
        self.refresh_abweichung(ksinr=ksinr)


    def mark_protocol_failed(self, ksinr: int, document: dict) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_protocols "
                "(ksinr, document_id, document_url, extracted_at, status) VALUES (?, ?, ?, ?, 'failed')",
                (ksinr, document.get("document_id"), document.get("url"), now),
            )

    def get_decisions(self, ksinr: int) -> list[dict]:
        # Sitzungs-Spalten mitziehen wie in get_decision(): sonst fehlten
        # committee/session_date/protocol_url ausgerechnet hier, obwohl der
        # Frontend-Typ CouncilDecision sie überall zusichert.
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.ksinr = ? ORDER BY d.position""",
            (ksinr,),
        ).fetchall()
        return [self._decision_row(r) for r in rows]


    # ------------------------------------------------------------------
    # Vorläufige Ergebnisse aus der Videoaufzeichnung (council/videos.py)




    @staticmethod
    def _decision_row(r) -> dict:
        d = dict(r)
        for key in ("factions", "policy_tags"):
            try:
                d[key] = json.loads(d.get(key) or "[]")
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        # Normalised Antragsteller parties (real factions only, deduped).
        # Multi-Mapping: ein Gruppen-Label („FDP/Volt") zählt für jede Partei.
        d["parties"] = sorted({p for f in d["factions"] for p in parties_for_faction(f)}, key=order_key)
        return d

    # Outcomes grouped into "real votes" vs "reports / no decision".
    _VOTE_OUTCOMES = ("accepted", "rejected", "postponed")
    _REPORT_OUTCOMES = ("noted", "no_decision")

    def decision_ids_for_party(self, party: str) -> list[int]:
        """IDs of main decisions whose Antragsteller includes ``party`` —
        Gruppen-Labels („FDP/Volt") matchen für jede beteiligte Partei."""
        ids = []
        for row in self._conn.execute("SELECT id, factions FROM council_decisions WHERE kind = 'decision'"):
            try:
                arr = json.loads(row["factions"] or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            if any(party in parties_for_faction(f) for f in arr):
                ids.append(row["id"])
        return ids

    def _decision_where(self, query, committee, outcome, faction, date_from, date_to,
                        kind, category, field="", party_ids=None, include_subvotes=False,
                        only_ids=None, district="", location_slug=""):
        """Build the WHERE clause + params shared by search and count."""
        filters: list[str] = []
        params: list = []
        if only_ids is not None:
            # Design 28a/S4: Vorgegebene Beschluss-Menge (die semantischen Treffer
            # eines Nutzer-Themas). Die Zuordnung liegt in ratslotse.sqlite, also in
            # einer anderen Datei — ein JOIN ist unmöglich, der Router reicht
            # die ids herein. Bewusst getrennt von party_ids, damit sich beide
            # Einschränkungen kombinieren lassen.
            if only_ids:
                filters.append(f"d.id IN ({','.join('?' * len(only_ids))})")
                params += list(only_ids)
            else:
                filters.append("0")  # Thema ohne Treffer
        if party_ids is not None:
            # Restrict to a party's decisions (ids precomputed via normalisation).
            if party_ids:
                filters.append(f"d.id IN ({','.join('?' * len(party_ids))})")
                params += party_ids
            else:
                filters.append("0")  # party given but no matches
        if query:
            filters.append("(d.title LIKE ? OR d.official_text LIKE ? OR d.summary LIKE ?)")
            like = f"%{query}%"
            params += [like, like, like]
        if committee:
            filters.append("cs.committee = ?")
            params.append(committee)
        if field:
            filters.append("d.policy_field = ?")
            params.append(field)
        if district:
            # EXISTS vermeidet doppelte Beschlusszeilen bei mehreren Ortslinks.
            # Primäre Ortsbereiche matchen die geometrisch abgeleitete Eltern-ID,
            # feinere Katalogorte ihre exakte stabile Orts-ID bzw. Alt-Aliase.
            place = self.resolve_place(district)
            if place:
                condition, place_params = self._place_location_condition(place)
                filters.append(
                    "EXISTS (SELECT 1 FROM council_decision_locations dl "
                    "JOIN council_locations l ON l.slug = dl.location_slug "
                    f"WHERE dl.decision_id = d.id AND {condition})"
                )
                params += place_params
            else:
                filters.append("0")
        if location_slug:
            filters.append(
                "EXISTS (SELECT 1 FROM council_decision_locations dl "
                "WHERE dl.decision_id=d.id AND dl.location_slug=?)"
            )
            params.append(location_slug)
        if outcome:
            filters.append("d.outcome = ?")
            params.append(outcome)
        if category == "vote":
            filters.append(f"d.outcome IN ({','.join('?' * len(self._VOTE_OUTCOMES))})")
            params += list(self._VOTE_OUTCOMES)
        elif category == "report":
            filters.append(f"(d.outcome IN ({','.join('?' * len(self._REPORT_OUTCOMES))}) OR d.outcome IS NULL)")
            params += list(self._REPORT_OUTCOMES)
        if kind:
            filters.append("d.kind = ?")
            params.append(kind)
        elif not include_subvotes:
            # Design 23a: Änderungsanträge (kind='subvote') tauchen standardmäßig
            # NICHT als eigene Treffer auf — sie hängen als Kontext am Ursprungs-
            # official_text. include_subvotes=True (Filter „einzeln zeigen") bringt sie
            # zurück; ein expliziter kind-Filter behält Vorrang.
            filters.append("d.kind = 'decision'")
        if faction:
            filters.append("d.factions LIKE ?")
            params.append(f"%{faction}%")
        if date_from:
            filters.append("cs.session_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("cs.session_date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        return where, params

    def search_decisions(
        self,
        query: str = "",
        committee: str = "",
        outcome: str = "",
        faction: str = "",
        date_from: str = "",
        date_to: str = "",
        kind: str = "",
        category: str = "",
        sort: str = "date_desc",
        field: str = "",
        party: str = "",
        limit: int = 50,
        offset: int = 0,
        include_subvotes: bool = False,
        only_ids: list[int] | None = None,
        district: str = "",
        location_slug: str = "",
    ) -> list[dict]:
        """Search extracted decisions, joined with their session (committee + date).
        ``category`` is "vote" (decided) or "report" (zur Kenntnis / no decision).
        ``field`` filters by policy field, ``party`` by normalised Antragsteller;
        ``sort`` ∈ {date_desc, date_asc, faction, importance}."""
        order = {
            "date_asc": "cs.session_date ASC, d.position",
            # Non-empty factions first ('["…' < '[]'), grouped, newest within.
            "faction": "d.factions ASC, cs.session_date DESC",
            # Wichtigste zuerst — mit Alters-Dämpfung. Ohne sie dominieren die
            # Haushaltsbeschlüsse: Sie haben strukturell die höchste Tragweite
            # und verdrängen alles Aktuelle, egal wie alt sie sind. Der Wert
            # halbiert sich nach 2 Jahren (1 / (1 + Alter/2 Jahre)) — bewusst
            # hyperbolisch statt exponentiell, damit historische Großbeschlüsse
            # nach hinten rutschen, aber nicht völlig verschwinden.
            # MAX(0, …) fängt künftig datierte Sitzungen ab (kein Auftrieb).
            "importance": (
                "d.importance IS NULL, "
                "d.importance / (1.0 + MAX(0.0, julianday('now') - julianday(cs.session_date)) / 730.0) DESC, "
                "cs.session_date DESC"
            ),
            # RL-U15: Unterhaltungs-Sortierung — Gesprächswert statt Priorität.
            "interest": "d.interest IS NULL, d.interest DESC, cs.session_date DESC",
        }.get(sort, "cs.session_date DESC, d.position")
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                              date_from, date_to, kind, category, field, party_ids,
                                              include_subvotes=include_subvotes, only_ids=only_ids,
                                              district=district, location_slug=location_slug)
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
                {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def backfill_importance(self, only_missing: bool = False) -> int:
        """(Neu-)Berechnung des Wichtigkeits-Scores (``council.importance``) für
        alle Beschlüsse → Spalte ``council_decisions.importance``. Braucht das
        Gremium (JOIN Sitzung) und die Länge der Beratungsfolge (COUNT über
        ``kvonr``). Idempotent; gibt die Zahl aktualisierter Zeilen zurück.
        Läuft in ``scripts/weekly_enrich.py`` (nach dem Scrapen von Beschlüssen
        und Beratungen) und im Erstlauf-Skript ``scripts/score_importance.py``."""
        from council import importance as _imp
        where = "WHERE d.importance IS NULL" if only_missing else ""
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee,
                       (SELECT COUNT(*) FROM council_deliberations b WHERE b.kvonr = d.kvonr) AS n_beratungen
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                {where}"""
        ).fetchall()
        n = 0
        with self._conn:
            for r in rows:
                d = dict(r)
                score = _imp.importance_score(d, n_beratungen=(d.get("n_beratungen") or None))
                # RL-U16: Tragweite (LLM) mischt 50/50 in den Wichtig-Wert,
                # sobald sie befüllt ist — die Heuristik bleibt der Boden.
                # Vor dem ersten rate_impact-Lauf ändert sich damit nichts.
                if d.get("impact") is not None:
                    score = round((score + int(d["impact"])) / 2)
                self._conn.execute(
                    "UPDATE council_decisions SET importance = ? WHERE id = ?", (score, d["id"]))
                n += 1
        return n

    def count_decisions(
        self, query="", committee="", outcome="", faction="", date_from="", date_to="",
        kind="", category="", field="", party="", include_subvotes=False,
        only_ids: list[int] | None = None, district: str = "", location_slug: str = "",
    ) -> int:
        party_ids = self.decision_ids_for_party(party) if party else None
        where, params = self._decision_where(query, committee, outcome, faction,
                                             date_from, date_to, kind, category, field, party_ids,
                                             include_subvotes=include_subvotes, only_ids=only_ids,
                                             district=district, location_slug=location_slug)
        row = self._conn.execute(
            f"""SELECT COUNT(*) FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr {where}""",
            params,
        ).fetchone()
        return row[0] if row else 0


    def decisions_needing_simple_summary(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne „einfach erklärt"-Kurzfassung (RL-904): nur echte
        Beschlüsse mit substanziellem Beschlusstext, neueste zuerst — so holt
        ein limitierter Backfill die relevantesten zuerst nach."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.simple_summary IS NULL
                   AND d.official_text IS NOT NULL AND length(d.official_text) >= 200
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def save_simple_summary(self, decision_id: int, text: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET simple_summary = ? WHERE id = ?",
                (text, decision_id),
            )

    # ---- Interessantheit + Fundstück (RL-U11) --------------------------------

    def decisions_needing_interest(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne Interessantheits-Score: nur echte Beschlüsse mit
        Titel, neueste zuerst (ein limitierter Backfill holt die relevantesten
        zuerst nach — wie bei „einfach erklärt")."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.amount_eur,
                        cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision' AND d.interest IS NULL
                   AND d.title IS NOT NULL AND length(d.title) >= 8
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    def save_interest(self, decision_id: int, score: int, reason: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET interest = ?, interest_reason = ? WHERE id = ?",
                (max(0, min(100, int(score))), reason, decision_id),
            )

    def decisions_needing_impact(self, limit: int | None = None) -> list[dict]:
        """Beschlüsse ohne Tragweite-Score (RL-U16), neueste zuerst — mit den
        Struktur-Signalen, die der Prompt neben dem Text sehen soll."""
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.kind,
                        d.amount_eur, d.vote, d.no_votes, cs.committee, cs.session_date
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind IN ('decision', 'subvote') AND d.impact IS NULL
                   AND d.title IS NOT NULL AND length(d.title) >= 8
                 ORDER BY cs.session_date DESC, d.id"""
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (limit,)
        return [dict(r) for r in self._conn.execute(sql, args).fetchall()]

    #: Titel auf seinen Kern eindampfen, damit „Annahme von Zuwendungen durch
    #: den Rat - Beschluss (ungeändert beschlossen)" und dieselbe Zeile drei
    #: Sitzungen später als EIN Punkt zählen: Klammern raus, Zahlen zu #,
    #: Ergebniszusatz weg.
    _WIEDERKEHR_UNWICHTIG = re.compile(
        r"\([^)]*\)|\b(?:ungeändert|geändert)\s+beschlossen\b|"
        r"\s+-\s+(?:beschluss|bericht|antrag|vorlage)\b", re.IGNORECASE)





    def save_impact(self, decision_id: int, score: int, reason: str | None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET impact = ?, impact_reason = ? WHERE id = ?",
                (max(0, min(100, int(score))), reason, decision_id),
            )

    #: Gewichte des Fundwerts. Erzählbarkeit zählt etwas mehr als Tragweite
    #: — ein Haushaltsbeschluss ist bedeutend, aber kein Fundstück. Die
    #: Sperren darunter sind der eigentliche Hebel: Ohne sie gewinnt die
    #: Kuriosität, weil sie leichter hohe Interest-Werte erreicht.
    FUND_GEWICHT_INTERESSE = 0.55
    FUND_GEWICHT_TRAGWEITE = 0.45
    FUND_MIN_INTERESSE = 50
    FUND_MIN_TRAGWEITE = 50







    def get_decision(self, decision_id: int) -> dict | None:
        row = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.id = ?""",
            (decision_id,),
        ).fetchone()
        return self._decision_row(row) if row else None

    def get_subvotes(self, ksinr: int, parent_item: str) -> list[dict]:
        rows = self._conn.execute(
            """SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
               WHERE d.ksinr = ? AND d.kind = 'subvote' AND d.parent_item = ?
               ORDER BY d.position""",
            (ksinr, parent_item),
        ).fetchall()
        return [self._decision_row(r) for r in rows]

    def subvote_summaries(self, pairs: list[tuple[int, str]]) -> dict[tuple[int, str], dict]:
        """Design 23a: je Ursprungsbeschluss (ksinr, item_number) eine kompakte
        Änderungsantrags-Zusammenfassung für die Trefferliste — Anzahl,
        beteiligte Fraktionen, Ergebnisse. So kann die Karte „n Änderungsantrag ·
        Fraktion · angenommen" als Unterzeile zeigen, ohne die subvotes selbst
        als eigene Treffer zu listen."""
        wanted = {(int(k), str(i)) for k, i in pairs if i}
        if not wanted:
            return {}
        ksinrs = sorted({k for k, _ in wanted})
        ph = ",".join("?" * len(ksinrs))
        rows = self._conn.execute(
            f"SELECT ksinr, parent_item, factions, outcome FROM council_decisions "
            f"WHERE kind = 'subvote' AND ksinr IN ({ph}) ORDER BY position",
            ksinrs,
        ).fetchall()
        out: dict[tuple[int, str], dict] = {}
        for r in rows:
            key = (r["ksinr"], r["parent_item"])
            if key not in wanted:
                continue
            e = out.setdefault(key, {"count": 0, "factions": [], "outcomes": []})
            e["count"] += 1
            try:
                for f in json.loads(r["factions"] or "[]"):
                    if f and f not in e["factions"]:
                        e["factions"].append(f)
            except (ValueError, TypeError):
                pass
            if r["outcome"] and r["outcome"] not in e["outcomes"]:
                e["outcomes"].append(r["outcome"])
        return out

    def vorlage_journey(self, template_number: str) -> list[dict]:
        """All sessions where a Vorlage appears on the agenda — its path through
        the committees and the council, oldest first."""
        rows = self._conn.execute(
            """SELECT DISTINCT cs.ksinr, cs.committee, cs.session_date, ci.item_number
               FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.template_number = ?
               ORDER BY cs.session_date""",
            (template_number,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Vorlagen (full text of proposal documents, council.vorlagen) ----------

    def missing_vorlage_kvonrs(self, limit: int | None = None) -> list[int]:
        """kvonrs referenced by agenda items but not ingested yet, newest sessions
        first (so the daily capped run always covers the current business). Rows
        with status 'failed' count as missing — they get retried."""
        sql = (
            "SELECT ci.kvonr FROM council_agenda_items ci "
            "JOIN council_sessions cs ON cs.ksinr = ci.ksinr "
            "WHERE ci.kvonr IS NOT NULL AND ci.kvonr NOT IN "
            "  (SELECT kvonr FROM council_templates WHERE status != 'failed') "
            "GROUP BY ci.kvonr ORDER BY MAX(cs.session_date) DESC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def save_vorlage(self, row: dict) -> None:
        from council import ernte

        now = datetime.utcnow().isoformat(timespec="seconds")
        # Regex-Ernte direkt beim Speichern — so tragen neue Vorlagen die
        # Felder automatisch, das Backfill-Skript ist nur für den Bestand.
        text = row.get("raw_text") or ""
        aus = ernte.auswirkungen(text)
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_templates "
                "(kvonr, template_number, title, kind, document_id, document_url, "
                " raw_text, n_pages, fetched_at, status, office, climate_impact, "
                " financial_impact, proposed_decision) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["kvonr"], row.get("template_number"), row.get("title"), row.get("kind"),
                 row.get("document_id"), row.get("document_url"), row.get("raw_text"),
                 row.get("n_pages"), now, row.get("status", "ok"),
                 ernte.federfuehrendes_amt(text), aus["klima"], aus["finanzen"],
                 ernte.proposed_decision(text)),
            )
        if row.get("template_number"):
            self.refresh_abweichung(template_number=row["template_number"])

    def mark_vorlage_failed(self, kvonr: int) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_templates (kvonr, fetched_at, status) "
                "VALUES (?, ?, 'failed')", (kvonr, now),
            )

    def get_vorlage_by_nr(self, template_number: str) -> dict | None:
        """The Vorlage row for a decision's template_number. Falls back to the base
        number ("22/0348/1" → "22/0348") because protocols sometimes cite a
        revision the agenda linked under its base document."""
        nr = (template_number or "").strip()
        if not nr:
            return None
        base = "/".join(nr.split("/")[:2])
        row = self._conn.execute(
            "SELECT * FROM council_templates WHERE template_number IN (?, ?) "
            "ORDER BY (template_number = ?) DESC, kvonr DESC LIMIT 1",
            (nr, base, nr),
        ).fetchone()
        return dict(row) if row else None

    def get_vorlage(self, kvonr: int) -> dict | None:
        """Die Vorlage zu ihrer Ratsinfo-Id. Gegenstück zu get_vorlage_by_nr —
        für alles, was am Vorgang selbst hängt (Design 28a/W1: verfolgen)."""
        row = self._conn.execute(
            "SELECT * FROM council_templates WHERE kvonr = ?", (kvonr,)
        ).fetchone()
        return dict(row) if row else None

    def vorlage_texts_for(self, vorlage_nrs: list[str]) -> dict[str, str]:
        """Batch raw texts for Q&A context enrichment: exact template_number → text
        (only rows that actually have text). Best-effort — no base-nr fallback."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"SELECT template_number, raw_text FROM council_templates "
            f"WHERE template_number IN ({ph}) AND status = 'ok'", nrs,
        ).fetchall()
        return {r["template_number"]: r["raw_text"] for r in rows if r["raw_text"]}

    # --- Anlagen (documents attached to a Vorlage, incl. fraction motions) -----

    def save_anlagen(self, kvonr: int, rows: list[dict]) -> int:
        """Store the Anlagen of one Vorlage and mark it scanned. Existing
        document_ids are kept (their text was ingested earlier); only new ones
        are inserted — so daily re-scans of recent sessions stay cheap."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        new = 0
        with self._conn:
            for r in rows:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO council_attachments "
                    "(document_id, kvonr, label, url, is_motion, applicants, "
                    " raw_text, n_pages, fetched_at, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r["document_id"], kvonr, r.get("label"), r.get("url"),
                     r.get("is_motion", 0),
                     json.dumps(r.get("applicants") or [], ensure_ascii=False),
                     r.get("raw_text"), r.get("n_pages"), now, r.get("status", "listed")),
                )
                new += cur.rowcount
            self._conn.execute(
                "UPDATE council_templates SET attachments_scanned = 1 WHERE kvonr = ?", (kvonr,)
            )
        return new

    def kvonrs_without_anlagen_scan(self, limit: int | None = None) -> list[int]:
        """Ingested Vorlagen whose page has not been scanned for Anlagen yet,
        newest first (kvonr is monotonic enough for that)."""
        sql = ("SELECT kvonr FROM council_templates WHERE attachments_scanned = 0 "
               "ORDER BY kvonr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def kvonrs_for_anlagen_rescan(self, days_back: int = 45) -> list[dict]:
        """Vorlagen on agendas of recent/upcoming sessions — re-scanned daily
        because Änderungsanträge often land on the page days after the Vorlage.
        Returns ``[{kvonr, known_ids}]`` so the fetcher skips known documents."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT DISTINCT ci.kvonr FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.kvonr IS NOT NULL AND cs.session_date >= ?""", (cutoff,),
        ).fetchall()
        out = []
        for r in rows:
            known = [k[0] for k in self._conn.execute(
                "SELECT document_id FROM council_attachments WHERE kvonr = ?", (r[0],)).fetchall()]
            out.append({"kvonr": r[0], "known_ids": known})
        return out

    def anlagen_for_vorlage_nr(self, template_number: str) -> list[dict]:
        """Anlagen for a decision's Vorlage (base-nr fallback like
        ``get_vorlage_by_nr``), motions first, each with parsed Antragsteller."""
        v = self.get_vorlage_by_nr(template_number)
        if not v:
            return []
        rows = self._conn.execute(
            "SELECT document_id, label, url, is_motion, applicants, status, is_image "
            "FROM council_attachments WHERE kvonr = ? ORDER BY is_motion DESC, label",
            (v["kvonr"],),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["applicants"] = json.loads(d.get("applicants") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["applicants"] = []
            out.append(d)
        return out

    # --- Beratungsfolge (official per-Vorlage consultation path) ---------------

    def save_beratungen(self, kvonr: int, rows: list[dict]) -> int:
        """Replace the Beratungsfolge of one Vorlage. Full replace per kvonr —
        stations get added over time and results are filled in afterwards, so a
        merge would leave stale planned rows behind."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_deliberations WHERE kvonr = ?", (kvonr,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_deliberations "
                    "(kvonr, date, committee, top, is_public, result, ksinr, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (kvonr, r.get("date"), r.get("committee") or "", r.get("top"),
                     None if r.get("is_public") is None else int(bool(r.get("is_public"))),
                     r.get("result"), r.get("ksinr"), now),
                )
        return len(rows)

    def get_beratungen(self, kvonr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT date, committee, top, is_public, result, ksinr "
            "FROM council_deliberations WHERE kvonr = ? "
            "ORDER BY date IS NULL, date", (kvonr,),
        ).fetchall()
        return [dict(r) for r in rows]

    def geplante_beratungen_fuer(self, kvonrs: list[int]) -> list[dict]:
        """Künftige Stationen (Datum ab heute) der Vorlagen — der „Wie es
        weitergeht"-Stoff.

        Das Datum entscheidet, NICHT das Ergebnis-Feld. Die erste Fassung
        verlangte zusätzlich ein leeres ``result`` — und lieferte damit
        dauerhaft nichts: Bei künftigen Stationen trägt das Feld die geplante
        BEHANDLUNG („Vorberatung", „Kenntnisnahme"), kein Resultat. Am
        11.08.2026 nachgemessen: 22 Termine ab heute, davon 0 mit leerem
        ``result`` — der Block blieb also immer leer, auch im
        Recherche-Bericht. Die Behandlungsart kommt als ``art`` mit; sie sagt
        dem Leser, was dort passieren soll.
        """
        kvonrs = [k for k in kvonrs if k]
        if not kvonrs:
            return []
        ph = ",".join("?" * len(kvonrs))
        rows = self._conn.execute(
            f"SELECT b.kvonr, b.date, b.committee, b.result AS kind, "
            f"       v.template_number, v.title AS template_title "
            f"FROM council_deliberations b JOIN council_templates v ON v.kvonr = b.kvonr "
            f"WHERE b.kvonr IN ({ph}) AND b.date >= date('now') ORDER BY b.date",
            kvonrs).fetchall()
        return [dict(r) for r in rows]

    #: Wörter, die in fast jeder Frage stehen und jede Tagesordnung treffen
    #: würden. „stand" ist der Klassiker: Als Teilwort-Suche traf es
    #: „Sachstandsbericht" und „Baumstandort" und hängte einer Frage nach der
    #: Cäcilienbrücke einen EU-Verordnungs-Termin an (gemessen 11.08.).
    #: „strasse" (gefaltet) ist derselbe Fehler in Grün: Fragen zu einer
    #: Adresse enthalten das Wort fast immer, und es steckt in jedem zweiten
    #: Vorlagentitel — Straßenwidmungen, B-Plan-Sachstände, Straßenbau. Bei
    #: der Stadion-Frage („Maastrichter Straße") hängte es drei fremde
    #: Verkehrsausschuss-Termine an „Wie es weitergeht" (gemessen 19.08.,
    #: Tims Screenshot-Befund — nur „strasse" traf, kein n>=2 gefordert).
    _AUSBLICK_STOPP = {
        "stand", "sachstand", "aktuell", "beschluss", "beschlusse", "beschluesse",
        "stadt", "oldenburg", "planung", "bericht", "vorlage", "thema", "themen",
        "strasse",
    }

    def kommende_beratungen(self, begriffe: list[str], limit: int = 3) -> list[dict]:
        """Kommende Beratungen, deren Vorlagen-Titel zur Frage passt.

        Der Ausblick über die zitierten Vorlagen allein läuft ins Leere, und
        zwar systematisch: Auf der Tagesordnung stehen die Vorlagen, über die
        noch NICHT entschieden wurde — die Suche findet aber Beschlüsse. Am
        11.08.2026 gemessen: 22 Termine ab heute, keiner davon zu einer
        Vorlage mit vorhandenem Beschluss.

        Deshalb hier der zweite Weg: Titel-Abgleich gegen die Suchbegriffe der
        Frage. Deterministisch (kein Modell, kein Embedding), und die Menge ist
        winzig — es geht nur um die nächsten Sitzungen.
        """
        worte = {self._falte_namen(w) for w in begriffe if len(w) >= 5}
        worte -= self._AUSBLICK_STOPP
        if not worte:
            return []
        rows = self._conn.execute(
            "SELECT b.kvonr, b.date, b.committee, b.result AS kind, "
            "       v.template_number, v.title AS template_title "
            "FROM council_deliberations b JOIN council_templates v ON v.kvonr = b.kvonr "
            "WHERE b.date >= date('now') ORDER BY b.date").fetchall()
        bewertet: dict[int, tuple[int, dict]] = {}
        for r in rows:
            titel_worte = re.split(r"[^a-z0-9]+", self._falte_namen(r["template_title"] or ""))
            n = sum(1 for w in worte if any(tw.startswith(w) for tw in titel_worte if tw))
            if not n:
                continue
            # Je Vorlage nur die nächste Station (nach Datum sortiert gelesen).
            if r["kvonr"] not in bewertet:
                bewertet[r["kvonr"]] = (n, dict(r))
        beste = sorted(bewertet.values(), key=lambda t: (-t[0], t[1]["date"]))
        return [d for _n, d in beste[:limit]]

    def kvonrs_without_beratungen(self, limit: int | None = None) -> list[int]:
        """Ingested Vorlagen whose Beratungsfolge has never been fetched,
        newest first."""
        sql = ("SELECT v.kvonr FROM council_templates v "
               "WHERE v.kvonr NOT IN (SELECT DISTINCT kvonr FROM council_deliberations) "
               "ORDER BY v.kvonr DESC")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in self._conn.execute(sql).fetchall()]

    def kvonrs_for_beratungen_rescan(self, days_back: int = 45, days_ahead: int = 120) -> list[int]:
        """Vorlagen whose Beratungsfolge is likely still moving: on an agenda of
        a recent session OR with a planned/unresolved station (future date or
        missing result) — those get re-fetched daily so nachgetragene
        Ergebnisse und neue Stationen ankommen."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        rows = self._conn.execute(
            """SELECT DISTINCT ci.kvonr FROM council_agenda_items ci
               JOIN council_sessions cs ON cs.ksinr = ci.ksinr
               WHERE ci.kvonr IS NOT NULL AND cs.session_date >= ?
               UNION
               SELECT DISTINCT b.kvonr FROM council_deliberations b
               WHERE (b.result IS NULL AND b.date <= ?) OR b.date >= ?""",
            (cutoff, horizon, date.today().isoformat()),
        ).fetchall()
        return [r[0] for r in rows]

    # --- Personen-Stammdaten (Mandatsträger + Mitgliedschaften) ----------------



    def stammdaten_stats(self) -> dict:
        one = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "personen": one("SELECT COUNT(*) FROM council_persons"),
            "mitgliedschaften": one("SELECT COUNT(*) FROM council_memberships"),
            "vorlagen_mit_beratungen": one("SELECT COUNT(DISTINCT kvonr) FROM council_deliberations"),
            "beratungen": one("SELECT COUNT(*) FROM council_deliberations"),
            "geplante_beratungen": one(
                "SELECT COUNT(*) FROM council_deliberations WHERE date > date('now')"),
        }

    # --- Quiz (generierte Fragen je Gebiet) -----------------------------------












    # Themen ohne Entität dahinter (kuratierte Spezial-Gebiete) → Anzeigename.
    _THEMA_LABELS = {"haushalt": "Stadt-Haushalt"}


    # --- Herkunft der Finanzzahlen (council.herkunft) ------------------------

    def merke_herkunft(self, h, fetched_at: str | None = None) -> int:
        """Eine :class:`council.herkunft.Herkunft` eintragen und ihre ID
        liefern — der eine Weg, auf dem Herkunft in die Datenbank kommt.

        Idempotent über den inhaltlichen Fingerabdruck: Derselbe Abschnitt
        desselben Dokuments mit derselben Probe bekommt bei jedem Lauf
        dieselbe ID. Was sich ändert, ist `fetched_at` — „zuletzt bestätigt",
        nicht „zuerst gesehen".

        Der Zeitstempel wandert dabei nur **vorwärts** (``MAX``). Beim
        Nachrüsten teilen sich mehrere Tabellen eine Herkunft und bringen je
        einen eigenen Zeitstempel mit; ohne diese Regel gewönne schlicht die
        zuletzt bearbeitete Tabelle, und „zuletzt bestätigt" stünde auf einem
        älteren Datum als eine Zeile, die darauf zeigt.

        Läuft absichtlich **ohne** eigene Transaktion: Der Aufrufer schreibt
        Herkunft und Datenzeilen zusammen, oder gar nicht."""
        jetzt = fetched_at or datetime.utcnow().isoformat(timespec="seconds")
        key = h.key()
        vorhanden = self._conn.execute(
            "SELECT id FROM council_provenance WHERE key = ?",
            (key,)).fetchone()
        if vorhanden:
            self._conn.execute(
                "UPDATE council_provenance SET fetched_at = MAX(fetched_at, ?) "
                "WHERE id = ?", (jetzt, vorhanden[0]))
            return int(vorhanden[0])
        f = h.felder()
        cur = self._conn.execute(
            "INSERT INTO council_provenance (key, kind, document_id, label, url, "
            " citation, page, probe, probe_result, as_of, fetched_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (key, f["kind"], f["document_id"], f["label"], f["url"],
             f["citation"], f["page"], f["probe"], f["probe_result"],
             f["as_of"], jetzt))
        return int(cur.lastrowid)

    #: Welcher Beschluss zu einem Dokument der maßgebliche ist. Der Rat zuerst
    #: — eine Vorlage läuft durch mehrere Gremien, aber verabschiedet wird sie
    #: dort. Innerhalb eines Gremiums die jüngste Sitzung: Ein vertagter Punkt
    #: kommt wieder, und es gilt, was zuletzt entschieden wurde. Dieselbe
    #: Ordnung nutzt schon `vorlage_beschluesse` (s. u. „committee LIKE 'Rat%'").
    _BESCHLUSS_ORDNUNG = ("ORDER BY (cs.committee LIKE 'Rat%') DESC, "
                          "cs.session_date DESC, d.id DESC")

    def beschluesse_zu_dokumenten(self, dokument_ids: list[int]) -> dict[int, dict]:
        """Zu jedem Dokument der Ratsbeschluss, der es verabschiedet hat.

        Der Weg ist dreigliedrig und steht so nirgends sonst im Code:
        ``council_provenance.document_id`` → ``council_attachments.kvonr`` (an
        welcher Vorlage die Anlage hängt) → ``council_decisions.kvonr`` (was
        der Rat mit dieser Vorlage gemacht hat).

        Damit wird aus „steht im Jahresabschluss 2024" ein „der Rat hat das am
        16.09.2025 beschlossen" — dieselbe Zahl, aber mit dem Vorgang dahinter
        statt nur mit dem Papier.

        **Das Ergebnis wird mitgeliefert, nicht gefiltert.** Ein Dokument, das
        an einer vertagten Vorlage hängt, ist keine Zahl ohne Beleg — es ist
        eine Zahl, deren Vorgang noch läuft, und genau das soll die Seite
        sagen können. Wer hier auf ``outcome = 'accepted'`` einschränkte,
        ließe die interessanteren Fälle stumm verschwinden.

        Eine Anlage ohne Vorlage im Bestand liefert **keinen** Eintrag; die
        Herkunft bleibt dann bei ihrem Dokument, und der Beleg-Chip zeigt, was
        er hat. Erfundene Vorgänge wären der schlimmere Fehler.
        """
        if not dokument_ids:
            return {}
        platz = ",".join("?" * len(dokument_ids))
        try:
            rows = self._conn.execute(
                "SELECT a.document_id, d.id AS decision_id, d.ksinr, d.item_number, "
                "       d.title, d.outcome, d.vote, d.template_number, a.kvonr, "
                "       cs.committee, cs.session_date "
                "FROM council_attachments a "
                "JOIN council_decisions d ON d.kvonr = a.kvonr "
                "JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                f"WHERE a.document_id IN ({platz}) AND d.kind = 'decision' "
                + self._BESCHLUSS_ORDNUNG,
                list(dokument_ids)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        # Die Ordnung entscheidet: Der erste Treffer je Dokument gewinnt, alle
        # weiteren sind frühere Stationen derselben Vorlage.
        aus: dict[int, dict] = {}
        for r in rows:
            aus.setdefault(int(r["document_id"]), {
                "id": r["decision_id"], "ksinr": r["ksinr"],
                "kvonr": r["kvonr"], "top": r["item_number"],
                "title": (r["title"] or "").strip() or None,
                "outcome": r["outcome"], "vote": r["vote"],
                "template_number": r["template_number"],
                "committee": r["committee"], "date": r["session_date"],
            })
        return aus

    def get_herkunft(self, ids: list[int] | None = None) -> list[dict]:
        """Herkunfts-Datensätze — alle oder eine Auswahl, mit den Erklärsätzen
        zu ihren Proben.

        Die Sätze kommen aus dem Code (``herkunft.PROBEN``) und nicht aus der
        Datenbank: Sie sind Text für Leserinnen und dürfen sich verbessern,
        ohne dass ein Jahrgang neu eingelesen werden muss."""
        from council import herkunft as _h

        try:
            if ids is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_provenance ORDER BY id").fetchall()
            elif not ids:
                return []
            else:
                platz = ",".join("?" * len(ids))
                rows = self._conn.execute(
                    f"SELECT * FROM council_provenance WHERE id IN ({platz}) ORDER BY id",
                    list(ids)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        aus = []
        for r in rows:
            d = dict(r)
            d.pop("key", None)   # interner Fingerabdruck, kein Lesestoff
            d["probes"] = _h.probe_texte(d.get("probe"))
            aus.append(d)
        # Der Ratsvorgang zu allen Dokumenten in EINER Abfrage — nicht je
        # Datensatz eine. Ein Beleg-Apparat zeigt dreizehn Teilhaushalts-Anlagen
        # nebeneinander; dreizehn Nachschläge daraus zu machen wäre ein N+1 an
        # genau der Stelle, an der die Seite ohnehin am meisten holt.
        beschluesse = self.beschluesse_zu_dokumenten(
            sorted({d["document_id"] for d in aus if d.get("document_id")}))
        for d in aus:
            d["official_text"] = beschluesse.get(d.get("document_id"))
        return aus

    def _herkunft_verweistabellen(self) -> list[str]:
        """Jede Tabelle **dieser Datenbank**, die eine ``herkunft_id`` führt.

        Gefragt wird das Schema und nicht ``herkunft.HERKUNFT_TABELLEN``. Die
        Liste dort ist die Arbeitsanweisung fürs Anlegen der Spalte und fürs
        Nachrüsten aus den Altfeldern; sie wird von Hand gepflegt, und der
        Modulkopf von `council/herkunft.py` nennt das Eintragen ausdrücklich
        als Schritt 3 für einen neuen Parser. Genau dieser Schritt ist der,
        den man vergisst.

        Fürs Aufräumen wäre das teuer: Eine Tabelle, die die Liste nicht
        kennt, hat aus Sicht des DELETE **keine** Verweise. Ihre Herkünfte
        gälten als verwaist und fielen weg — während ihre Zeilen weiter auf
        deren Nummern zeigen. Weil die Nummern danach neu vergeben werden
        können, zeigt so eine Zeile am Ende nicht ins Leere (das fiele auf),
        sondern auf ein **fremdes Dokument**. Und ``herkunft_luecken()``
        schwiege dazu, weil auch sie nur die Liste durchging.

        Das Schema kennt die Tabelle trotzdem. Deshalb entscheidet es."""
        aus: list[str] = []
        for (name,) in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
            cols = {r[1] for r in self._conn.execute(f'PRAGMA table_info("{name}")')}
            if "herkunft_id" in cols:
                aus.append(name)
        return aus

    def herkunft_aufraeumen(self) -> int:
        """Herkunfts-Datensätze löschen, auf die keine Zeile mehr zeigt.

        Nötig, weil ein erneuter Einlesen-Lauf einen Jahrgang **ersetzt**: Die
        alten Zeilen verschwinden, ihre Herkunft bliebe sonst liegen. Das
        passiert planmäßig einmal beim Nachrüsten (die `unbekannt`-Datensätze
        des Altbestands werden von den echten abgelöst) und danach immer, wenn
        sich eine Fundstelle oder eine Probe ändert.

        Gefragt wird, wer wirklich zeigt — ``_herkunft_verweistabellen()``
        liest das Schema, nicht die handgepflegte Liste. Dort steht auch,
        warum: Eine vergessene Zieltabelle verlöre hier sonst ihre Herkunft.

        Läuft **nur auf Ansage** aus den Ingest-Skripten, nicht beim Öffnen der
        Datenbank: Aufräumen ist eine Schreiboperation, und die gehört nicht in
        den Startpfad eines Webservers."""
        verweise = [f'SELECT herkunft_id FROM "{t}" WHERE herkunft_id IS NOT NULL'
                    for t in self._herkunft_verweistabellen()]
        if not verweise:
            return 0
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM council_provenance WHERE id NOT IN ("
                + " UNION ".join(verweise) + ")")
        return cur.rowcount

    def herkunft_luecken(self) -> dict[str, int]:
        """Je Zieltabelle: wie viele Zeilen ohne Herkunft dastehen.

        Das Frühwarnsystem der Umstellung. Eine Tabelle, die eine
        ``herkunft_id`` trägt, sie aber nicht füllt, taucht hier nach jedem
        Lauf auf — und die Ingest-Skripte schreiben es ins Protokoll. Genannt
        werden nur Tabellen mit Lücken; eine leere Antwort heißt „jede Zeile
        weiß, woher sie kommt".

        Der Prüfumfang kommt wie beim Aufräumen aus dem Schema: Eine Tabelle,
        die in ``HERKUNFT_TABELLEN`` vergessen wurde, ist damit **nicht**
        stillgestellt, sondern meldet sich hier — sie ist ja gerade der Fall,
        der eine Meldung verdient."""
        aus: dict[str, int] = {}
        for tabelle in self._herkunft_verweistabellen():
            n = self._conn.execute(
                f'SELECT COUNT(*) FROM "{tabelle}" WHERE herkunft_id IS NULL'
            ).fetchone()[0]
            if n:
                aus[tabelle] = n
        return aus

    #: Welches **Dokument** hinter einer Quelle des Haushalts-Bereichs steht —
    #: je Schlüssel die Tabelle, ihre Jahresspalte, eine Einschränkung und die
    #: Alt-Spalte mit der URL.
    #:
    #: Die Schlüssel sind die des Quellenverzeichnisses im Frontend
    #: (``web/frontend/lib/haushalt-quellen.ts``). Das ist Absicht und der
    #: einzige Grund, warum diese Zuordnung hier steht und nicht dort: Welche
    #: Zeile aus welchem Dokument stammt, weiß die Datenbank — das Frontend
    #: kennt nur den Absatz, der eine ganze Seite beschreibt. Wer einen
    #: Schlüssel dort ergänzt, ergänzt ihn hier; wer ihn hier vergisst,
    #: bekommt keinen kaputten Link, sondern den Rückfall auf die statische
    #: Adresse (und das Frontend schreibt dann „im Ratsinformationssystem
    #: suchen" statt „Dokument öffnen").
    #:
    #: Die Alt-Spalte ist die Rückfallebene für Bestände, die vor der
    #: Herkunfts-Vereinheitlichung (#513) geschrieben wurden: Dort steht die
    #: URL an der Datenzeile, aber noch keine ``herkunft_id``. Die beiden
    #: Konzern-Tabellen haben keine — sie sind erst mit der Herkunft
    #: entstanden (s. ``_HERKUNFT_ALTFELDER``).
    _DOKUMENT_QUELLEN: dict[str, tuple[str, str, str | None, str | None]] = {
        "plan":                 ("council_budget", "year", None, "source_url"),
        # Die zwei Ebenen eines Jahresabschlusses stehen in derselben Tabelle
        # und im selben Dokument, tragen aber verschiedene Herkünfte (eigene
        # Abschnitte, eigene Proben). Beide Schlüssel gibt es im Verzeichnis.
        "jahresabschluss":      ("council_income_statement", "year",
                                 "sub_budget_no IS NULL", "source_url"),
        "ergebnisrechnung_thh": ("council_income_statement", "year",
                                 "sub_budget_no IS NOT NULL", "source_url"),
        # Dritte Ebene desselben Dokuments: Abschnitt 4.1, die Kassensicht.
        "cash_flow_statement":       ("council_cash_flow_statement", "year", None, None),
        # Der Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — dieselbe
        # Postengliederung für Jahre ohne Abschluss.
        #
        # Der Filter auf ``kind = 'budget'`` ist hier PFLICHT und keine
        # Verfeinerung: Ein Dokument trägt sein Planjahr UND drei
        # Finanzplanungsjahre, dieselbe Jahreszahl kommt also in drei
        # Haushaltsplänen vor (2026 im Plan 2024 als Vorausschau, im Plan 2025
        # als Vorausschau, im Plan 2026 als Ansatz). Ohne den Filter stünden an
        # einer Ansatz-Zahl bis zu drei Dokumente, und zwei davon meinen etwas
        # anderes. Mit ihm gilt ``year == plan_budget_year``, und es bleibt genau
        # eines.
        "income_budget":     ("council_income_budget", "year",
                                 "t.kind = 'budget'", None),
        # Vierte Ebene: Abschnitt 2.1, die Bilanz. Der älteste Stichtag (2016)
        # stammt aus der Vorjahresspalte des Abschlusses 2017 — er trägt
        # deshalb dessen Dokument, mit eigener Fundstelle.
        "bilanz":               ("council_balance_sheet", "year", None, None),
        # Der einzige Schlüssel, hinter dem je Jahrgang MEHRERE Dokumente
        # stehen: Ein Produkt-Jahrgang verteilt sich auf zwölf bis dreizehn
        # Teilhaushalts-Anlagen (s. finanzquellen.Finanzquelle).
        "teilhaushalt":         ("council_products", "year", None, "source_url"),
        "pruefbericht":         ("council_audit_report_sources", "year", None, "url"),
        "gesamtabschluss":      ("council_group_items", "year", None, None),
        # Nur die geprüften Zeilen: Die Bezugsgröße „Gesamtbetrag des
        # Finanzhaushaltes" steht in derselben Datei, aber an einer anderen
        # Fundstelle und ohne Probe — ohne diesen Filter stünden je Jahrgang
        # zwei Dokumente im Verzeichnis, wo es eines ist.
        "investitionen":        ("council_investments", "year",
                                 "t.level = 'sub_budget'", None),
        # Alle Zeilen eines Jahrgangs teilen sich eine Herkunft; die
        # `gesamt`-Zeile gibt es genau einmal und steht hier für das Dokument.
        "investitionsprogramm": ("council_investment_measures", "year",
                                 "t.level = 'total'", None),
        # Ein Jahrgang, zwei Herkünfte (Teil A und Teil B im selben PDF, aber
        # unter verschiedenen Proben). Beide zeigen auf dieselbe Datei; die
        # Fundstelle unterscheidet sie, und `DISTINCT` fasst sie deshalb nicht
        # zusammen — genau richtig, denn ein Beleg an einer Beamtenzahl soll
        # „Teil A" sagen und nicht „Stellenplan".
        "stellenplan":          ("council_staff_plan", "budget_year", None, None),
        # Der einzige Schlüssel, dessen Jahresspalte NICHT das Datenjahr ist:
        # Ein Bericht liefert fünf Jahrgänge, gehört aber zu genau einem
        # Dokument — und das ist seines.
        "indicators":           ("council_indicators", "report_year", None, None),
        # Die drei Schichten vom 20.08.2026. Sie standen bis zum 21.08. NICHT
        # hier, und man hat es der Seite angesehen: Unter 33 Wirtschaftsplänen
        # aus sieben Betrieben stand eine einzige Quelle, deren Link auf die
        # Startseite des Ratsinformationssystems führte. Der Eintrag hier ist
        # der ganze Unterschied zwischen „kommt aus dem RIS" und „steht in
        # diesem PDF".
        #
        # Wie ``teilhaushalt`` tragen alle drei je Jahrgang MEHRERE Dokumente,
        # und das ist hier keine Eigenheit, sondern der Kern: Ein Jahrgang
        # Wirtschaftsplan besteht aus sieben Plänen von sieben Betrieben, und
        # jeder ist ein eigenes Papier mit eigener Vorlagennummer.
        "wirtschaftsplan":      ("council_business_plans", "year", None, None),
        # Nachträge tragen eine eigene Satzung und ein eigenes Dokument; der
        # Schlüssel unterscheidet sie nicht, die Fundstelle tut es.
        "budget_bylaw":     ("council_budget_bylaw", "year", None, None),
        "fees":            ("council_fees", "year", None, None),
        # Der Haushaltsvollzug trägt je Jahrgang bis zu ACHT Dokumente (vier
        # Stichtage × zwei Haushalte), und jedes ist ein eigenes Papier mit
        # eigener Vorlagennummer — dieselbe Lage wie beim Wirtschaftsplan.
        # Gefiltert wird auf die Summenzeile, damit der Join nicht jede der
        # 42 Zeilen einer Tabelle anfasst; ihre Herkunft ist dieselbe.
        "budget_execution": ("council_budget_execution", "budget_year",
                             "t.is_total = 1", None),
        # Kredite und Zinsen: je Unterrichtung eine Vorlage mit eigener
        # Herkunft — die Papierliste eines Jahrgangs sind die Berichte des
        # Jahres. `document_url` ist die Rückfallebene der Zeile.
        "loans":            ("council_loan_notices", "year", None, "document_url"),
        # Der Liquiditätsstand: je Monat die Grafik, aus der der Wert zuletzt
        # bestätigt wurde — die Papierliste eines Jahrgangs sind die Grafiken.
        "liquidity":        ("council_liquidity", "year", None, "url"),
        # Die Jahresabschlüsse der Eigenbetriebe: je Jahrgang bis zu vier
        # Prüfberichte (ein Betrieb, ein Papier), jede Kennzahl zeigt auf den
        # jüngsten Bericht, der sie nennt.
        "enterprise_accounts": ("council_enterprise_accounts", "year", None, None),
        # Die Änderungslisten zum Haushalt. Wie `wirtschaftsplan` stehen je
        # Jahrgang MEHRERE Papiere dahinter (Verw. I–III und die
        # Beschluss-Datei des AFB) — die Summen-Tabelle trägt je Dokument
        # eine Herkunft, DISTINCT macht daraus die Papierliste des Jahrgangs.
        "aenderungsliste":      ("council_budget_amendments_totals",
                                 "budget_year", None, None),
    }

    #: Jahresquellen, die KEIN Dokument im Ratsinformationssystem haben und
    #: deshalb nicht in ``_DOKUMENT_QUELLEN`` stehen — Downloads von
    #: oldenburg.de, Open Data und die Landesstatistik. Für die Frage „welche
    #: Jahrgänge deckt diese Quelle ab?" zählen sie genauso.
    _WEITERE_JAHRESQUELLEN: dict[str, tuple[str, str, str | None]] = {
        "taxes":     ("council_taxes", "year", None),
        "tax_capacity": ("council_tax_capacity", "year", None),
        "population":   ("council_einwohner", "year", None),
        "schulden":    ("council_debt", "year", None),
        "gebaut":      ("council_investments_actual", "year", None),
        "expense_series": ("council_expense_series", "year", None),
        "buergschaften": ("council_buergschaften", "year", None),
        "anlagenspiegel": ("council_fixed_assets", "year", None),
        "vermoegensgruppen": ("council_vermoegensgruppen", "year", None),
        "integrierte_schulden": ("council_integrated_debt", "year", None),
        "donations":     ("council_donations", "year", None),
        "loans":         ("council_loan_notices", "year", None),
        "liquidity":     ("council_liquidity", "year", None),
        "enterprise_accounts": ("council_enterprise_accounts", "year", None),
        "tax_plan":  ("council_tax_plan", "year", None),
        "tax_rates":  ("council_tax_rates", "year", None),
    }



    # --- Stadt-Haushalt (council.haushalt) -----------------------------------














    def get_plan_ist(self, year: int) -> dict:
        """„Geplant und geworden" eines Jahres: die Summenzeilen (Erträge 12,
        Aufwendungen 20) für die Kernverwaltung und je Teilhaushalt.

        Liefert ``{gesamt: {...}, bereiche: [...]}`` — die Bereiche nach
        geplanten Aufwendungen absteigend, damit die größten oben stehen."""
        rows = [dict(r) for r in self._conn.execute(
            "SELECT sub_budget_no, sub_budget_name, nr, budgeted, plan, plan_kind, result, deviation "
            "FROM council_income_statement WHERE year = ? AND nr IN (12, 20) "
            "ORDER BY sub_budget_no, nr", (year,))]

        def plan_von(r: dict):
            """Bezugsgröße der Abweichung — mit Rückfall auf den Ansatz.

            Der Rückfall ist kein Schönheitsfehler, sondern der Normalfall für
            jeden Bestand, der vor #510 geschrieben wurde: `plan` und
            `plan_kind` kamen damals per ALTER TABLE dazu, und ALTER TABLE füllt
            nichts nach — alle vorhandenen Zeilen tragen dort seither NULL,
            obwohl `budgeted` danebensteht und richtig ist. Auf `/haushalt/
            plan-ist` hieß das: „Die Planwerte der Gesamtrechnung konnten wir
            für diesen Jahrgang nicht auslesen" für **jeden** Jahrgang, bis
            jemand von Hand neu einliest.

            Bis 16.08.2026 stand hier ``r.get("plan", r.get("budgeted"))``. Das
            sieht aus wie genau dieser Rückfall und ist keiner: `r` kommt aus
            einem ``SELECT plan, …``, der Schlüssel ist also **immer** da, und
            `dict.get` greift seinen Vorgabewert nur bei fehlendem Schlüssel
            ab — nie bei ``None``. Der Zweig war toter Code."""
            value = r.get("plan")
            return r.get("budgeted") if value is None else value

        def bauen(part: list[dict]) -> dict:
            e = next((r for r in part if r["nr"] == 12), {})
            a = next((r for r in part if r["nr"] == 20), {})
            # `plan` ist die Bezugsgröße der Abweichung, `ansatz` der
            # ursprüngliche Haushaltsansatz — 2018 und 2020 fallen auseinander.
            return {"revenues_planned": plan_von(e),
                    "revenues_budgeted": e.get("budgeted"),
                    "revenues_actual": e.get("result"),
                    "expenses_planned": plan_von(a),
                    "expenses_budgeted": a.get("budgeted"),
                    "expenses_actual": a.get("result"),
                    "plan_kind": a.get("plan_kind") or e.get("plan_kind")}

        gesamt = [r for r in rows if r["sub_budget_no"] is None]
        bereiche = []
        for nr in sorted({r["sub_budget_no"] for r in rows if r["sub_budget_no"] is not None}):
            part = [r for r in rows if r["sub_budget_no"] == nr]
            bereiche.append({"sub_budget_no": nr, "sub_budget_name": part[0]["sub_budget_name"], **bauen(part)})
        bereiche.sort(key=lambda b: -(b["expenses_planned"] or 0))
        return {"year": year, "gesamt": bauen(gesamt) if gesamt else None, "bereiche": bereiche}




    # --- Finanzrechnung der Kernverwaltung (council.finanzberichte) ----------



    def finanzrechnung_jahre(self) -> list[int]:
        """Jahre mit eingelesener Finanzrechnung (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_cash_flow_statement ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Bilanz der Stadt (council.bilanz) -----------------------------------








    # --- Gesamtergebnishaushalt (Planjahre, council.ergebnishaushalt) --------





    # --- Stellenplan (council.stellenplan) ----------------------------------




    # --- Investitionen des Finanzhaushalts (council.investitionen) ----------




    # --- Investitionsprogramm (Anlage 004 des Haushaltsplans) ---------------




    # --- Konzern Stadt Oldenburg (konsolidierter Gesamtabschluss) -----------





    # --- Beteiligungsbericht (§ 151 NKomVG) ---------------------------------










    # --- Schuldenstand (Tabelle 1108 des Statistischen Jahrbuchs) ------------



    # --- Lange Ausgabenreihe (Datensatz 1102, seit 1972) --------------------

    def save_ausgabenreihe(self, zeilen: list[dict], herkunft) -> int:
        """Jahrgänge der langen Ausgabenreihe ersetzen — je Jahr eine Zeile.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an einer Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen (dieselbe Regel wie bei ``save_schulden``).

        Übergeben wird nur, was seine Proben bestanden hat — diese Methode
        prüft nichts nach, sie schreibt. Welche Proben das waren, kommt als
        Liste in ``probes`` an und wird kommagetrennt gespeichert; die Namen
        stehen in ``council/herkunft.PROBEN``.

        Aufgerufen wird sie einmal je Herkunfts-Gruppe, nicht einmal für die
        ganze Reihe: Ein Jahrgang von 1974 steht nur im Open-Data-Portal, einer
        von 2024 zusätzlich im Jahrbuch und im Jahresabschluss — das sind
        verschiedene Belege, und jeder soll für seine Zeilen gelten."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_expense_series "
                "(year, accounting_system, amount, source, probes, conflict_amount, "
                " conflict_source, revised, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["year"], z["accounting_system"], z["amount"], z["source"],
                  ",".join(z.get("probes") or []), z.get("conflict_amount"),
                  z.get("conflict_source"), int(bool(z.get("revised"))),
                  hid, now) for z in zeilen])
        return len(zeilen)


    # --- Bürgschaften: wofür die Stadt geradesteht --------------------------

    def save_wirtschaftsplan(self, plan, herkunft) -> int:
        """Einen Wirtschaftsplan speichern — ein Betrieb, ein Haushaltsjahr.

        Aufgerufen wird sie **je Plan** und nicht für eine ganze Lieferung:
        Jeder Jahrgang steht in seiner eigenen Ratsvorlage, also hat jeder
        seine eigene Herkunft. Ein gemeinsamer Beleg wäre für sieben von acht
        Zeilen der falsche — dieselbe Überlegung wie bei
        ``save_buergschaften``.

        ``plan`` ist ein :class:`council.wirtschaftsplan.Wirtschaftsplan`; die
        Proben stehen dort und werden nicht hier noch einmal gerechnet.
        """
        # Die Proben kommen aus der HERKUNFT und stehen nicht hier: Welche
        # gelaufen sind, weiß der Parser, und es sind je nach Quelle andere —
        # der Beschlusstext prüft anders als der Erfolgsplan einer Anlage. Eine
        # feste Liste an dieser Stelle behauptete für jede Zeile dieselben.
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_business_plans "
                "(enterprise, year, enterprise_name, template_number, revenues, expenses, "
                " taxes, result, capital_plan, investments, commitments, "
                " draft_date, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan.enterprise, plan.year, plan.enterprise_name, plan.template_number,
                 plan.revenues, plan.expenses, plan.taxes, plan.result,
                 plan.capital_plan, plan.investments, plan.commitments,
                 plan.draft_date, probes, hid, now))
        return 1





    def gebuehren_jahre(self) -> list[int]:
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_fees ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def save_haushalt_aenderungen(self, document_id: int, liste: str,
                                  result, herkunft) -> int:
        """Eine geprüfte Änderungsliste speichern — Positionen und Summen.

        Ersetzt wird je ``(budget_year, liste)``: Ein Jahrgang hat genau ein
        Verw.-I-Dokument usw. Ob zwei ANLAGEN dasselbe Dokument sind (die
        2021er-Beschlussdatei liegt doppelt im Bestand), entscheidet der
        Ingest VOR dem Speichern — diese Methode prüft nichts nach, sie
        schreibt, was seine Proben bestanden hat (council/aenderungslisten.py).
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        budget_year = result.budget_year
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for tabelle in ("council_budget_amendments",
                            "council_budget_amendments_totals"):
                self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE budget_year = ? AND list_key = ?",
                    (budget_year, liste))
            self._conn.executemany(
                "INSERT INTO council_budget_amendments (budget_year, list_key, "
                " year, seq, sub_budget, page_draft, product, label, "
                " revenue, expense, explanation, author, document_id, "
                " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, z.year, z.seq, z.sub_budget, z.page_draft,
                  z.product, z.label, z.revenue, z.expense,
                  z.explanation, z.author, document_id, hid, now)
                 for z in result.zeilen])
            self._conn.executemany(
                "INSERT INTO council_budget_amendments_totals (budget_year, "
                " list_key, year, kind, label, revenues, expenses, balance, "
                " own, document_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, s.year, s.typ, s.label, s.revenues,
                  s.expenses, s.balance,
                  1 if result.eigene_zeile.get(s.year) == s.label else 0,
                  document_id, hid, now) for s in result.summen])
        return len(result.zeilen)

    def save_haushalt_aenderungen_fhh(self, document_id: int, liste: str,
                                      result, herkunft) -> int:
        """Eine FHH-Änderungsliste speichern — Positionen und Zusammenstellung.

        Wie beim Ergebnishaushalt: Die Proben liefen im Parser
        (council/aenderungslisten_fhh.py), hier wird nur geschrieben. Je
        (Jahrgang, Liste) wird gelöscht und neu geschrieben, ein zweiter Lauf
        ersetzt den Stand also gefahrlos.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        budget_year = result.budget_year
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for tabelle in ("council_budget_amendments_cash",
                            "council_budget_amendments_cash_totals"):
                self._conn.execute(
                    f"DELETE FROM {tabelle} WHERE budget_year = ? AND list_key = ?",
                    (budget_year, liste))
            self._conn.executemany(
                "INSERT INTO council_budget_amendments_cash (budget_year, "
                " list_key, year, seq, sub_budget, page_draft, product, label, "
                " planned_draft, inflow, outflow, commitment_authorizations, planned_new, "
                " explanation, author, document_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, z.year, z.seq, z.sub_budget, z.page_draft,
                  z.product, z.label, z.planned_draft, z.inflow,
                  z.outflow, z.commitment_authorizations, z.planned_new, z.explanation, z.author,
                  document_id, hid, now) for z in result.zeilen])
            self._conn.executemany(
                "INSERT INTO council_budget_amendments_cash_totals (budget_year, "
                " list_key, year, kind, label, inflows, outflows, balance, "
                " commitment_authorizations, own, document_id, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, liste, s.year, s.typ, s.label, s.inflows,
                  s.outflows, s.balance, s.commitment_authorizations,
                  1 if result.eigene_zeile.get(s.year) == s.label else 0,
                  document_id, hid, now) for s in result.summen])
        return len(result.zeilen)





    def haushaltssatzung_jahre(self) -> list[int]:
        """Jahrgänge, für die eine Satzung vorliegt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_budget_bylaw ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Haushaltsvollzug (council.budget_execution) ------------------------






    def wirtschaftsplan_jahre(self, enterprise: str) -> list[int]:
        """Haushaltsjahre, für die ein Plan dieses Betriebs vorliegt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_business_plans WHERE enterprise = ? "
                "ORDER BY year", (enterprise,))]
        except sqlite3.OperationalError:
            return []




    def get_kennzahl_formeln(self) -> list[dict]:
        """Die gedruckten Rechenwege, ältester Bericht zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_indicator_formulas ORDER BY indicator, report_year")]
        except sqlite3.OperationalError:
            return []








    # --- Nachbewilligungen nach § 117 NKomVG --------------------------------

    def anlage_text(self, document_id: int) -> str | None:
        """Der Volltext einer Anlage — oder ``None``, wenn keiner da ist.

        „Kein Text" ist der Normalfall und kein Fehler: Der Bestand führt
        Anlagen, die noch nie geladen wurden (``scripts/backfill_anlagen_texte
        .py``), und solche, die als Scan gar keinen Text hergeben. Beide
        sollen den Aufrufer nicht in einen Fehlerpfad zwingen, sondern in die
        Meldung „für dieses Jahr liegt die Quelle nicht vor"."""
        try:
            row = self._conn.execute(
                "SELECT raw_text FROM council_attachments WHERE document_id = ?",
                (document_id,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return (row["raw_text"] or None) if row else None






    def ausgabenreihe_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — Grundlage des Bestandsschutzes
        vor dem Schreiben (``council/finanzquellen.bestandsschutz``)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_expense_series ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    # --- Zuwendungen an die Stadt (aus den Ratsbeschlüssen) ----------------


    # --- Marken der Skriptläufe (scripts/check_finanzdaten.py) --------------

    def ingest_marke(self, key: str) -> dict | None:
        """Bei welcher Dokumentmarke das Skript dieser Datenart zuletzt lief."""
        try:
            r = self._conn.execute(
                "SELECT key, marke, ran_at, ok, summary FROM council_ingest_marks WHERE key = ?",
                (key,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return dict(r) if r else None

    def setze_ingest_marke(self, key: str, marke: int, ok: bool, summary: str = "") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_ingest_marks (key, marke, ran_at, ok, summary) "
                "VALUES (?,?,?,?,?)",
                (key, int(marke), datetime.utcnow().isoformat(timespec="seconds"), int(ok), summary[:2000]))

    # --- Liquiditätsstand (council/liquidity.py) ----------------------------


    def anlagentext_nachtragen(self, document_id: int, text: str, n_pages: int) -> None:
        """Den heruntergeladenen Text einer Anlage ablegen — damit der nächste
        Lauf (und die KI-Frage) ihn haben, ohne noch einmal zu laden."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_attachments SET raw_text = ?, n_pages = ?, status = 'ok', "
                "fetched_at = datetime('now') WHERE document_id = ?", (text, n_pages, document_id))




    # --- Jahresabschlüsse der Eigenbetriebe (council/eigenbetriebe_abschluss.py) --

    def eigenbetrieb_abschluss_anlagen(self) -> list[dict]:
        """Die Anlagen der Jahresabschluss-Vorlagen der Eigenbetriebe — mit
        Titel der Vorlage, denn Betrieb und Jahr stehen dort, nicht im Label."""
        from council.eigenbetriebe_abschluss import TITEL_MUSTER, TITEL_SQL
        try:
            return [dict(r) for r in self._conn.execute(
                f"""SELECT t.kvonr, t.template_number, t.title, a.document_id, a.label,
                           a.url, a.raw_text, a.n_pages, a.status
                      FROM council_templates t JOIN council_attachments a ON a.kvonr = t.kvonr
                     WHERE {TITEL_SQL}
                     ORDER BY t.template_number, a.document_id""", list(TITEL_MUSTER))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def save_enterprise_accounts(self, rows: list[dict], herkunft) -> int:
        """Die Kennzahlen schreiben — je Zeile ihre Herkunft (``row["herkunft"]``)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            for r in rows:
                hid = self.merke_herkunft(r["herkunft"], fetched_at=now) if r.get("herkunft") else rueck
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_enterprise_accounts (enterprise, year, metric, "
                    " value, unit, report_year, confirmations, conflicts, document_id, probes, "
                    " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["enterprise"], r["year"], r["metric"], r["value"], r["unit"],
                     r["report_year"], r.get("confirmations", 1), r.get("conflicts", 0),
                     r.get("document_id"), ",".join(r.get("probes") or []), hid, now))
        return len(rows)



    # --- Kredite und Zinsen (council/loans.py) ------------------------------


    def save_loan_notices(self, notices: list[dict], items: list[dict], herkunft) -> int:
        """Die Unterrichtungen und ihre Posten schreiben — je Vorlage ihre
        eigene Herkunft (``row["herkunft"]``), sonst die des Laufs.

        ``INSERT OR REPLACE`` je Vorlage; die Posten einer Vorlage werden
        vorher gelöscht, damit ein neu gelesener Bericht keine alten Posten
        neben den neuen stehen lässt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            for n in notices:
                hid = (self.merke_herkunft(n["herkunft"], fetched_at=now)
                       if n.get("herkunft") else rueck)
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_loan_notices "
                    "(template_number, year, period_from, period_to, document_date, "
                    " none_reported, items, interest_saving, saving_from, saving_to, "
                    " document_id, document_url, probes, herkunft_id, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (n["template_number"], n["year"], n["period_from"], n["period_to"],
                     n.get("document_date"), int(bool(n.get("none_reported"))), n.get("items", 0),
                     n.get("interest_saving"), n.get("saving_from"), n.get("saving_to"),
                     n.get("document_id"), n.get("document_url"), ",".join(n.get("probes") or []),
                     hid, now))
                self._conn.execute("DELETE FROM council_loan_items WHERE template_number = ?",
                                   (n["template_number"],))
                for it in (i for i in items if i["template_number"] == n["template_number"]):
                    self._conn.execute(
                        "INSERT OR REPLACE INTO council_loan_items "
                        "(template_number, seq, year, kind, borrower, heading, amount, rate_pct, "
                        " fixed_years, fixed_until, decided_at, summary, herkunft_id, fetched_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (it["template_number"], it["seq"], it["year"], it["kind"], it.get("borrower"),
                         it["heading"], it.get("amount"), it.get("rate_pct"), it.get("fixed_years"),
                         it.get("fixed_until"), it.get("decided_at"), it.get("summary"), hid, now))
        return len(notices)





    def spenden_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — Grundlage des Bestandsschutzes."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_donations ORDER BY year")]
        except sqlite3.OperationalError:
            return []


    # --- Steuertabellen des Jahrbuchs (1103 und 1105) -----------------------







    # --- Ist-Investitionen (Tabellen 1107/1107-1 des Jahrbuchs) -------------





    def investitionen_ist_kontext(self, year: int | None = None) -> dict | None:
        """Was die Stadt zuletzt wirklich investiert hat — für die KI-Frage.

        Wenige Zeilen statt Bestand, wie bei allen Geld-Bausteinen: der
        jüngste Jahrgang mit seiner Aufteilung, das Vorjahr als Maßstab und
        der höchste Stand der doppischen Reihe.

        **Nur die doppische Reihe.** Die kameralen Jahrgänge bis 2009 zählen
        etwas anderes (s. ``council/investitionen_ist.py``); in einem
        Prompt-Baustein nebeneinander wären sie eine Einladung, sie zu einer
        Reihe zu addieren.
        """
        from council import investitionen_ist as _ii

        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investments_actual "
                "WHERE accounting_system = 'doppik' ORDER BY year")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        idx = next((i for i, r in enumerate(rows) if r["year"] == year), len(rows) - 1)
        abweicht = year is not None and rows[idx]["year"] != year
        rows_bis = rows[:idx + 1]
        neu = rows[idx]
        try:
            arten = [(r["title"], r["amount"]) for r in self._conn.execute(
                "SELECT title, amount FROM council_investments_actual_kinds "
                "WHERE year = ? ORDER BY sort_order", (neu["year"],))]
        except sqlite3.OperationalError:
            arten = []
        hoch = max(rows, key=lambda r: r["total"])
        # Welche Jahre die Quelle ankündigt, aber nicht belegt — die Lücke
        # gehört in den Kontext, sonst liest ein Modell die Reihe als
        # lückenlos und rechnet Durchschnitte über ein Loch.
        fehlend = [j for j in range(rows[0]["year"], neu["year"] + 1)
                   if j not in {r["year"] for r in rows}]
        return {
            "year": neu["year"],
            "total": neu["total"],
            "arten": arten,
            "davor": ({"year": rows_bis[-2]["year"], "total": rows_bis[-2]["total"]}
                      if len(rows_bis) > 1 else None),
            "hoch": ({"year": hoch["year"], "total": hoch["total"]}
                     if hoch["year"] != neu["year"] else None),
            "reihe_ab": rows[0]["year"],
            "fehlend": fehlend,
            "abgrenzung": _ii.ABGRENZUNG,
            "beleg": self._beleg(neu.get("herkunft_id")),
            **({"year_asked": year} if abweicht else {}),
        }



    # --- Städtevergleich (amtliche Statistik des LSN) ------------------------

















    def top_amount_since(self, date_from: str) -> dict | None:
        """Größter im Beschlusstext erkannter Betrag seit ``date_from`` — die
        „Zahl der Woche" fürs Heute-Briefing (RL-905)."""
        row = self._conn.execute(
            """SELECT d.id, d.title, d.amount_eur, s.session_date
               FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ? AND d.amount_eur IS NOT NULL
                 AND d.kind = 'decision'
               ORDER BY d.amount_eur DESC LIMIT 1""",
            (date_from,),
        ).fetchone()
        return dict(row) if row else None

    def count_decisions_since(self, date_from: str) -> int:
        """Anzahl Beschlüsse seit ``date_from`` (Fallback der Zahl der Woche)."""
        return int(self._conn.execute(
            """SELECT COUNT(*) FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date >= ?""",
            (date_from,),
        ).fetchone()[0])

    def antrag_stats(self) -> dict:
        """Erfolgsquoten der Fraktions-Anträge: Antrag-Anlage → Vorlage → deren
        Beschlüsse. Gezählt wird je Antragsteller-Partei der KLARE Endstand der
        Vorlage — bevorzugt der Beschluss des Rats selbst, sonst der letzte
        Ausschuss-Beschluss mit angenommen/abgelehnt. Mehrparteien-Anträge zählen
        für jede Partei. Methodik entspricht bewusst politik-vor-ort (Rat zuerst,
        nur klare Outcomes), aber über unsere volle Historie."""
        from council.parties import CANONICAL_ORDER, order_key

        antraege = self._conn.execute(
            """SELECT a.document_id, a.applicants, v.template_number
               FROM council_attachments a JOIN council_templates v ON v.kvonr = a.kvonr
               WHERE a.is_motion = 1 AND a.applicants != '[]'
                 AND v.template_number IS NOT NULL AND v.template_number != ''""",
        ).fetchall()

        per_party: dict[str, dict] = {}
        n_mit_beschluss = 0
        for row in antraege:
            base = "/".join(row["template_number"].split("/")[:2])
            # Trägt eine Vorlage mehrere Antrag-Anlagen (Änderungsanträge mehrerer
            # Parteien), zählt der Vorlagen-Endstand für jeden dieser Anträge.
            decision = self._conn.execute(
                """SELECT d.outcome, cs.committee FROM council_decisions d
                   JOIN council_sessions cs ON cs.ksinr = d.ksinr
                   WHERE d.kind = 'decision' AND d.outcome IN ('accepted','rejected')
                     AND (d.template_number = ? OR d.template_number LIKE ?)
                   ORDER BY (cs.committee LIKE 'Rat%') DESC, cs.session_date DESC
                   LIMIT 1""", (base, base + "/%"),
            ).fetchone()
            if not decision:
                continue
            n_mit_beschluss += 1
            try:
                parties = json.loads(row["applicants"] or "[]")
            except (json.JSONDecodeError, TypeError):
                parties = []
            for p in parties:
                # Nur anerkannte Parteien zählen — in älteren Anlagen-Zeilen
                # können inzwischen entfernte Labels (z. B. WFO/LKR) stehen.
                if p not in CANONICAL_ORDER:
                    continue
                s = per_party.setdefault(p, {"party": p, "n": 0, "accepted": 0, "rejected": 0})
                s["n"] += 1
                s[decision["outcome"]] += 1

        stats = sorted(per_party.values(), key=lambda s: (-s["n"], order_key(s["party"])))
        return {
            "parties": stats,
            "n_antraege": len(antraege),
            "n_mit_beschluss": n_mit_beschluss,
        }

    def get_unclassified_decisions(self, limit: int | None = None) -> list[dict]:
        """Decisions without a policy field yet — for the classification backfill/cron.
        Returns id + the fields the classifier needs (title, official_text, committee)."""
        sql = ("SELECT d.id, d.title, d.official_text, cs.committee "
               "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
               "WHERE d.policy_field IS NULL ORDER BY d.id")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(sql).fetchall()]

    def set_classifications(self, results: dict) -> int:
        """Bulk-write classification results: id -> {field, tags, summary}."""
        rows = [
            (r["field"], json.dumps(r.get("tags") or [], ensure_ascii=False), r.get("summary"), did)
            for did, r in results.items()
        ]
        with self._conn:
            self._conn.executemany(
                "UPDATE council_decisions SET policy_field = ?, policy_tags = ?, summary = ? WHERE id = ?",
                rows,
            )
        return len(rows)

    def reset_classifications(self) -> None:
        """Clear all topic classifications — for a full re-classify (e.g. taxonomy change)."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_decisions SET policy_field = NULL, policy_tags = NULL, summary = NULL"
            )

    def rebuild_fts(self) -> int:
        """(Re)build the full-text index from all main decisions (title + official_text +
        summary + the first chunk of the Vorlage text + the first chunk of attached
        motion texts, so Sachverhalt AND original Antrag wording are findable). The
        joins are grouped because distinct kvonrs can in theory share a template_number —
        duplicate rowids would break the FTS insert."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decisions_fts")
            self._conn.execute(
                "INSERT INTO council_decisions_fts(rowid, content) "
                "SELECT d.id, REPLACE(COALESCE(d.title,'') || ' ' || COALESCE(d.official_text,'') || ' ' "
                "|| COALESCE(d.summary,'') || ' ' || COALESCE(sv.stext,'') || ' ' "
                "|| COALESCE(v.vtext,'') || ' ' || COALESCE(an.atext,''), "
                "'ß', 'ss') "  # unicode61 folds ä/ö/ü but not ß
                "FROM council_decisions d "
                "LEFT JOIN (SELECT template_number, ohne_kontaktdaten("
                "             substr(MAX(raw_text), 1, 8000)) AS vtext "
                "           FROM council_templates WHERE status = 'ok' GROUP BY template_number) v "
                "  ON v.template_number = d.template_number "
                # `ohne_kontaktdaten()` ist eine SQLite-Funktion (s.
                # `_verbinden`): Sie nimmt Kontonummern, Telefonnummern,
                # E-Mail-Adressen und Anschriften aus dem Text, BEVOR er in
                # den Volltextindex geht. Gespeichert bleibt er vollständig.
                "LEFT JOIN (SELECT cv.template_number, ohne_kontaktdaten("
                "             substr(GROUP_CONCAT(a.raw_text, ' '), 1, 4000)) AS atext "
                "           FROM council_attachments a JOIN council_templates cv ON cv.kvonr = a.kvonr "
                "           WHERE a.is_motion = 1 AND a.status = 'ok' GROUP BY cv.template_number) an "
                "  ON an.template_number = d.template_number "
                # Teilabstimmungen (Änderungsanträge) haben keine eigene FTS-Zeile —
                # ihre Titel zählen zum Haupt-TOP, damit „Änderungsantrag der X zu Y"
                # den zitierfähigen Hauptbeschluss findet (Design 23a: subvote-Inhalt
                # steht im title, official_text ist immer NULL).
                "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' '), 1, 2000) AS stext "
                "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
                "           GROUP BY ksinr, parent_item) sv "
                "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
                "WHERE d.kind = 'decision'"
            )
        return self._conn.execute("SELECT COUNT(*) FROM council_decisions_fts").fetchone()[0]

    def search_decisions_fts(self, query: str, limit: int = 40) -> list[tuple]:
        """BM25 keyword search → ``[(decision_id, score, snippet)]`` (larger = better).
        Terms are OR-combined for recall; returns ``[]`` on an empty or invalid query.

        Das FTS5-``snippet()`` liefert die FUNDSTELLE im indexierten Text — bei
        Treffern tief im Vorlagen-Volltext ist das der Kontext, den der Reranker
        sehen muss (der Textanfang verrät dort nichts über den Match)."""
        terms = [t for t in re.findall(r"[0-9a-zäöü]+", query.lower().replace("ß", "ss")) if len(t) >= 3][:12]
        if not terms:
            return []
        match = " OR ".join(terms)
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank, snippet(council_decisions_fts, 0, '', '', ' … ', 16) "
                "FROM council_decisions_fts WHERE council_decisions_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        # FTS5 rank is negative (more negative = better); flip so larger = better.
        return [(r[0], -float(r[1]), r[2] or "") for r in rows]







    # ---- Explizite Ortszuordnungen je Beschluss ---------------------------

    def decision_location_batches(self, *, batch_size: int = 12,
                                  pending_only: bool = True,
                                  limit: int | None = None):
        """Beschlüsse samt Vorlage speicherschonend in Batches liefern.

        Im Tageslauf kommen nur ungescannte Vorgänge oder solche mit einer
        später geladenen Vorlage zurück. ``pending_only=False`` ist der
        bewusste Voll-Backfill nach dem Leeren der Scan-Tabelle.
        """
        inner = """SELECT d.id, d.title, d.official_text, d.template_number,
                      COALESCE(
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1)
                      ) AS vorlage_text,
                      COALESCE(
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1),
                        ''
                      ) AS vorlage_fetched_at,
                      s.source_hash AS existing_source_hash,
                      s.scanned_at
               FROM council_decisions d
               LEFT JOIN council_decision_location_scans s ON s.decision_id = d.id
               WHERE d.kind = 'decision'"""
        sql = f"SELECT * FROM ({inner}) q"
        if pending_only:
            sql += (" WHERE existing_source_hash IS NULL OR "
                    "(vorlage_fetched_at != '' AND "
                    "datetime(vorlage_fetched_at) > datetime(scanned_at))")
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += f" LIMIT {max(0, int(limit))}"
        cursor = self._conn.execute(sql)
        while True:
            rows = cursor.fetchmany(max(1, int(batch_size)))
            if not rows:
                break
            yield [dict(r) for r in rows]

    def decisions_for_location_extraction(self) -> list[dict]:
        """Kompatible Listenansicht; große Backfills nutzen die Batch-Methode."""
        return [row for batch in self.decision_location_batches(pending_only=False)
                for row in batch]

    def location_scan_hashes(self) -> dict[int, str]:
        return {r["decision_id"]: r["source_hash"] for r in self._conn.execute(
            "SELECT decision_id, source_hash FROM council_decision_location_scans")}

    def place_observations_for_decisions(self, ids: list[int]) -> dict[int, list[dict]]:
        """Einmalige alte NER-Orte als günstige Startbasis übernehmen."""
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT decision_id, name FROM council_entity_obs "
            f"WHERE kind = 'place' AND decision_id IN ({ph})", ids).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append({
                "name": r["name"], "kind": "other", "source": "official_text",
                "evidence": r["name"], "method": "entity_obs", "confidence": 0.86,
            })
        return out

    # ---- gemeinsamer, redaktionell erweiterbarer Ortskatalog -----------------







    def location_candidates(self, status_filter: str = "pending", *, limit: int = 200,
                            min_decisions: int = 3) -> list[dict]:
        """Häufige, noch nicht statisch katalogisierte Ortsnamen samt Belegen."""
        status_filter = status_filter if status_filter in {
            "pending", "concrete", "approved", "alias", "rejected", "all"
        } else "pending"
        # Auch zur Laufzeit freigegebene Katalogorte zählen als bekannt. So
        # verschwinden nach dem Backfill nicht nur statische Stadtteile,
        # sondern ebenso Schreibvarianten neuer redaktioneller Orte aus
        # der offenen Kandidatenliste.
        known_ids = sorted(place.id for place in self.all_places())
        review_where = ""
        review_params: list = []
        if status_filter == "pending":
            review_where = "AND r.status IS NULL"
        elif status_filter != "all":
            review_where = "AND r.status = ?"
            review_params.append(status_filter)
        known_placeholders = ",".join("?" for _ in known_ids)
        known_where = (
            f"AND (r.status IS NOT NULL OR l.place_id IS NULL "
            f"OR l.place_id NOT IN ({known_placeholders}))"
            if known_ids else ""
        )
        # Die offene Liste ist eine Prioritätenliste, kein Dump aller einmalig
        # erwähnten Namen. Bereits geprüfte Einträge müssen dagegen auch dann
        # sichtbar bleiben, wenn sie nur in einem Beschluss vorkommen.
        effective_min = max(1, int(min_decisions)) if status_filter == "pending" else 1
        rows = self._conn.execute(
            f"""SELECT l.*, r.status AS review_status, r.place_id AS review_place_id,
                      r.name AS review_name, r.kind AS review_kind, r.parent_id,
                      r.aliases, r.description, r.source_url, r.quiz_enabled,
                      r.canonical_place_id, r.note, r.updated_by, r.updated_at AS reviewed_at,
                      COUNT(DISTINCT dl.decision_id) AS decision_count,
                      MAX(cs.session_date) AS last_date,
                      AVG(dl.confidence) AS avg_confidence
               FROM council_locations l
               JOIN council_decision_locations dl ON dl.location_slug=l.slug
               JOIN council_decisions d ON d.id=dl.decision_id AND d.kind='decision'
               JOIN council_sessions cs ON cs.ksinr=d.ksinr
               LEFT JOIN council_place_reviews r ON r.location_slug=l.slug
               WHERE l.kind IN ('district','area','other') {review_where} {known_where}
               GROUP BY l.slug
               HAVING COUNT(DISTINCT dl.decision_id) >= ?
               ORDER BY decision_count DESC, last_date DESC, l.name
               LIMIT ?""", (*review_params, *known_ids, effective_min,
                              max(1, min(int(limit), 500)))
        ).fetchall()
        out = []
        for row in rows:
            state = row["review_status"] or "pending"
            evidence = self._conn.execute(
                """SELECT d.id,d.title,cs.session_date,dl.evidence,dl.method,dl.confidence
                   FROM council_decision_locations dl
                   JOIN council_decisions d ON d.id=dl.decision_id
                   JOIN council_sessions cs ON cs.ksinr=d.ksinr
                   WHERE dl.location_slug=? AND d.kind='decision'
                   ORDER BY cs.session_date DESC,d.id DESC LIMIT 3""",
                (row["slug"],),
            ).fetchall()
            item = dict(row)
            item["status"] = state
            try:
                item["aliases"] = json.loads(row["aliases"] or "[]")
            except (TypeError, json.JSONDecodeError):
                item["aliases"] = []
            item["evidence"] = [dict(sample) for sample in evidence]
            out.append(item)
        return out

    def review_location_candidate(self, location_slug: str, *, status: str,
                                  place_id: str | None = None, name: str | None = None,
                                  kind: str | None = None, parent_id: str | None = None,
                                  aliases: list[str] | None = None,
                                  description: str | None = None,
                                  source_url: str | None = None,
                                  quiz_enabled: bool = False,
                                  canonical_place_id: str | None = None,
                                  note: str | None = None,
                                  updated_by: str | None = None) -> dict:
        """Redaktionelles Urteil speichern und stabile IDs an Rohorte schreiben."""
        from council import places
        from council.locations import location_slug as slugify

        if status not in {"concrete", "approved", "alias", "rejected"}:
            raise ValueError("Unbekannter Prüfstatus")
        observed = self._conn.execute(
            "SELECT * FROM council_locations WHERE slug=?", (location_slug,)).fetchone()
        if not observed:
            raise KeyError(location_slug)
        allowed_kinds = {key for key in places.catalog()["kinds"] if key != "local_area"}
        if status == "approved":
            place_id = slugify(place_id or name or observed["name"])
            name = (name or observed["name"]).strip()
            kind = kind or "neighborhood"
            if not place_id or not name or kind not in allowed_kinds:
                raise ValueError("Freigegebener Ort braucht Name, gültige ID und Ortstyp")
            if not (source_url or "").startswith(("https://", "http://")):
                raise ValueError("Freigegebener Ort braucht eine Quellen-URL")
            if places.resolve(place_id) or any(p.id == place_id for p in self._reviewed_places()
                                                if p.id != observed["place_id"]):
                raise ValueError("Orts-ID ist bereits vergeben")
            parent = places.resolve(parent_id) if parent_id else None
            if parent_id and (not parent or not parent.is_primary):
                raise ValueError("Elternort muss ein primärer Ortsbereich sein")
        elif status == "concrete":
            name = (name or observed["name"]).strip()
            if not name or kind not in CONCRETE_LOCATION_KINDS:
                raise ValueError("Konkreter Ort braucht Name und gültigen Ortstyp")
            # Konkrete Punkte bleiben exakte Fundorte und werden absichtlich
            # nicht Teil des flächigen Ortskatalogs.
            place_id = None
            canonical_place_id = None
            parent_id = observed["local_area_id"]
            source_url = None
            quiz_enabled = False
        elif status == "alias":
            target = self.resolve_place(canonical_place_id)
            if not target:
                raise ValueError("Alias-Ziel ist unbekannt")
            canonical_place_id = target.id
            parents = self.primary_parents(target)
            parent_id = parents[0].id if len(parents) == 1 else None
            place_id = target.id
        else:
            place_id = None
            parent_id = None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        clean_aliases = list(dict.fromkeys(value.strip() for value in (aliases or []) if value.strip()))
        with self._conn:
            self._conn.execute(
                """INSERT INTO council_place_reviews
                   (location_slug,status,place_id,name,kind,parent_id,aliases,description,
                    source_url,quiz_enabled,canonical_place_id,note,updated_by,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(location_slug) DO UPDATE SET
                    status=excluded.status,place_id=excluded.place_id,name=excluded.name,
                    kind=excluded.kind,parent_id=excluded.parent_id,aliases=excluded.aliases,
                    description=excluded.description,source_url=excluded.source_url,
                    quiz_enabled=excluded.quiz_enabled,
                    canonical_place_id=excluded.canonical_place_id,note=excluded.note,
                    updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (location_slug, status, place_id, name, kind, parent_id,
                 json.dumps(clean_aliases, ensure_ascii=False), description, source_url,
                 int(quiz_enabled), canonical_place_id, note, updated_by, now),
            )
            if status == "concrete":
                self._conn.execute(
                    "UPDATE council_locations SET place_id=NULL,updated_at=? WHERE slug=?",
                    (now, location_slug),
                )
            else:
                self._conn.execute(
                    "UPDATE council_locations SET place_id=?,local_area_id=?,updated_at=? WHERE slug=?",
                    (place_id, parent_id, now, location_slug),
                )
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        return next(item for item in self.location_candidates("all", limit=500)
                    if item["slug"] == location_slug)

    def delete_location_review(self, location_slug: str) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM council_place_reviews WHERE location_slug=?", (location_slug,))
        if not cur.rowcount:
            return False
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        self.backfill_location_place_ids()
        return True

    def save_decision_locations(self, decision_id: int, rows: list[dict],
                                source_hash: str | None) -> int:
        """Zuordnungen eines Beschlusses atomar ersetzen und ggf. Scanstand merken.

        ``source_hash=None`` speichert sichere Regex-/Bestandsfunde nach einem
        LLM-Fehler, markiert den Vorgang aber nicht als fertig: der nächste
        inkrementelle Lauf versucht die semantische Ergänzung erneut.
        """
        from council.locations import location_slug

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        by_slug: dict[str, dict] = {}
        for row in rows:
            slug = row.get("slug") or location_slug(row.get("name") or "")
            if not slug:
                continue
            if slug not in by_slug or float(row.get("confidence") or 0) > float(by_slug[slug].get("confidence") or 0):
                by_slug[slug] = row
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_locations WHERE decision_id = ?", (decision_id,))
            for slug, row in by_slug.items():
                place = self.resolve_place(row.get("name"))
                parents = self.primary_parents(place)
                primary = parents[0] if len(parents) == 1 else None
                self._conn.execute(
                    "INSERT INTO council_locations"
                    "(slug,name,kind,district,place_id,local_area_id,updated_at) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                    "place_id=COALESCE(excluded.place_id,council_locations.place_id), "
                    "local_area_id=COALESCE(excluded.local_area_id,council_locations.local_area_id), "
                    "district=COALESCE(excluded.district,council_locations.district), "
                    "updated_at=excluded.updated_at",
                    (slug, place.name if place else row["name"],
                     "district" if place and place.is_primary else row.get("kind") or "other",
                     primary.name if primary else None, place.id if place else None,
                     primary.id if primary else None, now),
                )
                self._conn.execute(
                    "INSERT INTO council_decision_locations "
                    "(decision_id,location_slug,source,evidence,method,confidence,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (decision_id, slug, row.get("source") or "official_text",
                     (row.get("evidence") or row["name"])[:500], row.get("method") or "llm",
                     max(0.0, min(1.0, float(row.get("confidence") or 0))), now),
                )
            if source_hash is not None:
                self._conn.execute(
                    "INSERT INTO council_decision_location_scans(decision_id,source_hash,scanned_at) "
                    "VALUES (?,?,?) ON CONFLICT(decision_id) DO UPDATE SET "
                    "source_hash=excluded.source_hash, scanned_at=excluded.scanned_at",
                    (decision_id, source_hash, now),
                )
        return len(by_slug)

    def reset_decision_location_scans(self) -> None:
        """Vollständigen Neu-Lauf erlauben; Geocodes der Orte bleiben erhalten."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decision_locations")
            self._conn.execute("DELETE FROM council_decision_location_scans")

    def decision_locations(self, decision_id: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT l.*, dl.source, dl.evidence, dl.method, dl.confidence
               FROM council_decision_locations dl
               JOIN council_locations l ON l.slug = dl.location_slug
               WHERE dl.decision_id = ?
               ORDER BY dl.confidence DESC, l.name""", (decision_id,)).fetchall()
        return [dict(r) for r in rows]



    def decision_location_district_stats(self) -> list[dict]:
        """Kompatible Statistik der 31 primären Ortsbereiche."""
        primary_ids = {place.id for place in self.all_places() if place.is_primary}
        return [{key: value for key, value in row.items() if key != "place_id"}
                for row in self.decision_location_place_stats()
                if row["place_id"] in primary_ids]


    def decision_ids_for_place(self, place_id: str, limit: int | None = None) -> list[int]:
        """Beschlüsse mit belegtem Bezug zu einem Katalogort, neueste zuerst."""
        place = self.resolve_place(place_id)
        if not place:
            return []
        condition, params = self._place_location_condition(place)
        sql = f"""SELECT DISTINCT dl.decision_id
                  FROM council_decision_locations dl
                  JOIN council_locations l ON l.slug = dl.location_slug
                  JOIN council_decisions d ON d.id = dl.decision_id
                  JOIN council_sessions cs ON cs.ksinr = d.ksinr
                  WHERE {condition} AND d.kind = 'decision'
                  ORDER BY cs.session_date DESC, dl.decision_id DESC"""
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        return [row[0] for row in self._conn.execute(sql, params).fetchall()]




    #: Ab welchem Anteil der Stützpunkte ein Ortsbereich als berührt gilt.
    #: Zehn Prozent von bis zu 60 Punkten sind ein echtes Straßenstück, keine
    #: angeschnittene Ecke — und die zusätzliche Mindestzahl fängt sehr kurze
    #: Geometrien ab, bei denen ein einzelner Punkt schon 10 % wäre.
    ORTSBEREICH_ANTEIL = 0.10
    ORTSBEREICH_MINDESTPUNKTE = 2











    def trending_tags(self, days_back: int = 180, limit: int = 12) -> list[dict]:
        """Häufigste policy_tags der letzten Monate — Futter für anklickbare
        Themen-Vorschläge („was gerade den Rat beschäftigt")."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        rows = self._conn.execute(
            """SELECT je.value AS tag, COUNT(*) AS n
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr, json_each(d.policy_tags) je
               WHERE d.kind = 'decision' AND d.policy_tags IS NOT NULL
                 AND cs.session_date >= ?
               GROUP BY je.value ORDER BY n DESC, tag LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [{"tag": r["tag"], "n": r["n"]} for r in rows]

    def most_interesting_recent(self, days_back: int = 7) -> dict | None:
        """RL-U15 (13a-A): der interessanteste Beschluss der letzten Tage —
        füllt auf „Heute" den Treffer-Leerzustand („Diese Woche im Rat")."""
        row = self._conn.execute(
            """SELECT d.id, d.title, d.outcome, d.interest_reason, cs.committee, cs.session_date
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision' AND d.interest IS NOT NULL
                 AND cs.session_date >= date('now', ?)
               ORDER BY d.interest DESC, cs.session_date DESC LIMIT 1""",
            (f"-{int(days_back)} days",),
        ).fetchone()
        return dict(row) if row else None


    #: Ab wie vielen Ortsbereichen eine Entität als stadtweit gilt. Auf dem
    #: Prod-Bestand (01.09.2026) trennt 4 sauber: „Startchancen-Programm" (8),
    #: „Lärmaktionsplan" (7), „Mobilitätsplan Oldenburg 2030" (6) und „Housing
    #: First" (5) fallen raus, alles Ortsgebundene bleibt.
    CITYWIDE_FROM_DISTRICTS = 4

    #: Ab wie vielen Beschlüssen im Fenster ein bloßer Straßenname als
    #: Vorschlag taugt. Darunter ist er eine Adresse aus einem Bebauungsplan.
    STRASSE_MINDESTENS = 5

    #: Was nach Adresse klingt statt nach Vorhaben. Starke Straßen bleiben
    #: (s. STRASSE_MINDESTENS) — und rutschen hinter alles andere.
    _STRASSE = re.compile(r"(stra(ß|ss)e|str\.|weg|allee|ring|damm|chaussee|gasse|pfad|steig)$",
                          re.IGNORECASE)
    _STRASSE_VORNE = re.compile(r"^(am|an der|an den|auf dem|auf der|zum|zur|im|in der)\s",
                                re.IGNORECASE)





    def location_by_slug(self, slug: str) -> dict | None:
        row = self._conn.execute(
            "SELECT slug,name,kind,lat,lon,place_id,local_area_id FROM council_locations WHERE slug=?",
            (slug,),
        ).fetchone()
        return dict(row) if row else None












    # --- Entitäts-Anker der Suche (Akkuratheits-Paket, 10.08.26) -------------




    def neueste_stationen_fuer(self, kvonrs: list[int],
                               vorlage_basen: list[str]) -> list[dict]:
        """Alle Beschlüsse (id, kvonr, template_number, session_date, committee) der
        genannten Vorlagen-Familien — Grundlage für den „ältere Station"-Marker:
        derselbe Text durchläuft mehrere Gremien (gleiches kvonr), Revisionen
        hängen ein Suffix an die Vorlagen-Nummer (26/0100 → 26/0100-1)."""
        kvonrs = sorted({k for k in kvonrs if k})
        basen = sorted({(b or "").strip() for b in vorlage_basen if b and str(b).strip()})
        if not kvonrs and not basen:
            return []
        teile, params = [], []
        if kvonrs:
            teile.append(f"d.kvonr IN ({','.join('?' * len(kvonrs))})")
            params += kvonrs
        for b in basen[:60]:
            teile.append("d.template_number = ? OR d.template_number LIKE ?")
            params += [b, b + "-%"]
        rows = self._conn.execute(
            "SELECT d.id, d.kvonr, d.template_number, cs.session_date, cs.committee "
            "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
            "WHERE " + " OR ".join(teile), params).fetchall()
        return [dict(r) for r in rows]








    def decision_texts(self) -> list[dict]:
        """(id, text) per decision for the text match — title + Beschluss + summary."""
        rows = self._conn.execute(
            "SELECT id, title, official_text, summary FROM council_decisions").fetchall()
        return [{"id": r["id"],
                 "text": " ".join(x for x in (r["title"], r["official_text"], r["summary"]) if x)}
                for r in rows]







    # --- Personen-Paket (10.08.26): Stammdaten für Auflösung + Fragetyp -----

    # Vertretungs- und Zeit-Notizen sind keine Ämter („Für Oberbürgermeister
    # Krogmann", „bis TOP 8.2") — nur echte Amtsbezeichnungen zählen.
    _ROLLEN_RE = re.compile(
        r"(?i)^(erste[rn]?\s+)?(oberbürgermeister(in)?|stadtkämmer(er|in)|"
        r"stadtbaur(at|ätin)|stadtr(at|ätin))$")


    #: Funktionsangabe des Beteiligungsberichts, die „diese Person sitzt im
    #: Stadtrat" behauptet — mit optionalem Klammerzusatz, wie ihn der Bericht
    #: auch anderswo führt („1. Kreisrat (Vorsitzender)").
    _FUNKTION_RATSMITGLIED = re.compile(r"(?i)^ratsmitglied(\s*\(.*\))?$")

    @staticmethod
    def _ein_buchstabe_abstand(a: str, b: str) -> bool:
        """Unterscheiden sich die beiden Zeichenketten um höchstens einen
        Buchstaben (Levenshtein ≤ 1)? Gleichheit zählt mit."""
        if abs(len(a) - len(b)) > 1:
            return False
        if len(a) == len(b):
            return sum(x != y for x, y in zip(a, b)) <= 1
        kurz, lang = (a, b) if len(a) < len(b) else (b, a)
        i = 0
        while i < len(kurz) and kurz[i] == lang[i]:
            i += 1
        return kurz[i:] == lang[i + 1:]   # ein Zeichen im langen übersprungen










    # --- Council members (from attendance: who sits on the council) ------------------
    #: Das ganze Rollen-Vokabular der Anwesenheitsliste. `advisory` vergibt
    #: der Protokoll-Prompt nicht mehr (er nennt fünf Rollen); die Zeilen aus
    #: seiner früheren Fassung tragen den Wert weiter und sollen dabei
    #: richtig einsortiert bleiben — deshalb steht er hier.
    ATTENDANCE_ROLES = ("chair", "member", "administration", "minutes", "guest", "advisory")
    _MEMBER_ROLES = ("member", "chair")   # der Rest ist kein Mandat



    # --- Eine Person, zwei Namensformen (council.namensformen) ----------------





    #: Name des Plenar-Gremiums in den Sitzungsdaten. Es ist der Prüfstein für
    #: ein Ratsmandat (s. list_members) — die Ausschüsse führen daneben
    #: beratende Mitglieder, die dem Rat nicht angehören.
    PLENUM = "Rat"

    #: Wörter, die im Fraktions-Feld nur die ROLLE beschreiben („Beratendes
    #: Mitglied", „beratend", „Verwaltung") — sie benennen keine entsendende
    #: Organisation und taugen deshalb nicht als Herkunfts-Label.
    _ROLLEN_LABEL = re.compile(
        r"^(beratend\w*|beratende[sr]?\s+mitglied\w*|gast|gäste|verwaltung|"
        r"protokoll\w*|stellv\w*|vertretung|mitglied\w*)$", re.IGNORECASE)











    def decisions_for_amount(self, only_missing: bool = False) -> list[dict]:
        """Main decisions with their text, for the € extraction backfill."""
        sql = "SELECT id, title, official_text FROM council_decisions WHERE kind = 'decision'"
        if only_missing:
            sql += " AND amount_eur IS NULL"
        return [dict(r) for r in self._conn.execute(sql)]

    def set_amounts(self, rows: list[tuple]) -> int:
        """Bulk-write amount_eur. rows = (amount_or_None, decision_id)."""
        with self._conn:
            self._conn.executemany("UPDATE council_decisions SET amount_eur = ? WHERE id = ?", rows)
        return len(rows)

    # Titles excluded from the "largest" view: accounting / whole-budget reports
    # (balance totals, not a discrete decision) and treasury operations (debt
    # refinancing / credit reporting) — neither is "the city spends X on Y".
    #
    # Die Liste lebt in `council/importance.py` (Blatt-Modul, kein Zirkel) und
    # wird hier nur weitergereicht. Vorher stand sie ausschließlich hier — mit
    # der Folge, dass die drei Geld-Ansichten filterten, das Geld-Signal des
    # Wichtig-Werts aber nicht.
    _NON_SPENDING_TITLES = _importance.NON_SPENDING_TITLES

    def activity_trends(self, quarters: int = 12) -> dict:
        """Council activity over time for the trends view: decisions and recognised €
        volume per quarter (split by the busiest policy fields), plus the most active
        tags in the recent quarters."""
        from collections import Counter

        q_expr = ("substr(cs.session_date,1,4) || '-Q' || "
                  "((CAST(substr(cs.session_date,6,2) AS INTEGER)+2)/3)")
        rows = self._conn.execute(
            f"""SELECT {q_expr} AS q, d.policy_field AS field, COUNT(*) AS n
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND cs.session_date IS NOT NULL
                      AND d.policy_field IS NOT NULL
                GROUP BY q, field"""
        ).fetchall()
        all_q = sorted({r["q"] for r in rows})[-quarters:]
        qset = set(all_q)
        per_field: dict[str, dict] = {}
        for r in rows:
            if r["q"] not in qset:
                continue
            per_field.setdefault(r["field"], {q: 0 for q in all_q})[r["q"]] = r["n"]
        top_fields = sorted(per_field, key=lambda f: -sum(per_field[f].values()))[:6]

        # Recognised € per quarter — exclude accounting/treasury docs (Haushaltsplan,
        # Jahresabschluss …) so the bars reflect actual spending, not budget volumes.
        mclauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        mparams = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        money = {q: 0.0 for q in all_q}
        for r in self._conn.execute(
            f"""SELECT {q_expr} AS q, COALESCE(SUM(d.amount_eur), 0) AS eur
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND cs.session_date IS NOT NULL AND {mclauses}
                GROUP BY q""",
            mparams,
        ):
            if r["q"] in qset:
                money[r["q"]] = r["eur"] or 0

        # Procedural tags aren't "topics" — keep them out of the emerging list.
        procedural = {"bericht", "annahme", "vertagung", "kenntnisnahme", "beschluss",
                      "antrag", "anfrage", "mitteilung", "vorlage", "abstimmung", "resolution"}
        recent = set(all_q[-2:])
        tagc: Counter = Counter()
        for r in self._conn.execute(
            f"""SELECT d.policy_tags AS tags, {q_expr} AS q
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.policy_tags IS NOT NULL
                      AND cs.session_date IS NOT NULL"""
        ):
            if r["q"] in recent:
                try:
                    for t in json.loads(r["tags"] or "[]"):
                        t = str(t).strip()
                        if t and t.lower() not in procedural:
                            tagc[t] += 1
                except (ValueError, TypeError):
                    pass

        # Biggest single financial decision per quarter (excl. accounting, reusing the
        # filter above) — the factual "what drove this quarter" behind the money bars.
        drivers: dict[str, dict] = {}
        for r in self._conn.execute(
            f"""SELECT {q_expr} AS q, d.id AS id, d.title AS title, d.amount_eur AS eur
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND cs.session_date IS NOT NULL AND {mclauses}
                ORDER BY d.amount_eur DESC""",
            mparams,
        ):
            if r["q"] in qset and r["q"] not in drivers:
                drivers[r["q"]] = {"id": r["id"], "title": r["title"], "eur": round(r["eur"] or 0)}

        return {
            "quarters": all_q,
            "fields": top_fields,
            "by_field": {f: [per_field[f][q] for q in all_q] for f in top_fields},
            "money": [round(money[q]) for q in all_q],
            "money_drivers": [drivers.get(q) for q in all_q],
            "emerging": [{"tag": t, "n": c} for t, c in tagc.most_common(12) if c >= 2],
        }

    def largest_financial_decisions(self, limit: int = 25) -> list[dict]:
        """Decisions with the largest recognised € amount, deduped across committees
        (same Vorlage decided in Ausschuss + Rat → one entry) and excluding
        accounting/treasury items."""
        clauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        params = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        rows = self._conn.execute(
            f"""SELECT d.*, cs.committee, cs.session_date, p.document_url AS protocol_url
                FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_protocols p ON p.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC LIMIT 300""",
            params,
        ).fetchall()
        seen: set = set()
        out: list[dict] = []
        for r in rows:
            # Collapse the same matter (shared Vorlage across committees/revisions) and
            # recurring series (same title, different Vorlage). Rows are amount-desc, so
            # the kept entry is the largest.
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(self._decision_row(r))
            if len(out) >= limit:
                break
        return out

    def money_by_field(self) -> list[dict]:
        """Recognised € volume per policy field (excl. accounting/treasury), deduped
        like the largest-list so the same matter across committees/revisions isn't
        double-counted. For the 'Wofür fließt das Geld?' breakdown."""
        clauses = " AND ".join(["LOWER(d.title) NOT LIKE ?"] * len(self._NON_SPENDING_TITLES))
        params = [f"%{k}%" for k in self._NON_SPENDING_TITLES]
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.template_number, d.policy_field AS field, d.amount_eur AS eur
                FROM council_decisions d
                WHERE d.kind = 'decision' AND d.amount_eur IS NOT NULL
                      AND d.policy_field IS NOT NULL AND {clauses}
                ORDER BY d.amount_eur DESC""",
            params,
        ).fetchall()
        seen: set = set()
        agg: dict[str, dict] = {}
        for r in rows:
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            a = agg.setdefault(r["field"], {"field": r["field"], "total": 0.0, "n": 0})
            a["total"] += r["eur"] or 0
            a["n"] += 1
        out = sorted(agg.values(), key=lambda x: -x["total"])
        for a in out:
            a["total"] = round(a["total"])
        return out

    def policy_field_stats(self) -> list[dict]:
        """Count of classified decisions per policy field, most frequent first."""
        rows = self._conn.execute(
            "SELECT policy_field AS field, COUNT(*) AS count FROM council_decisions "
            "WHERE policy_field IS NOT NULL GROUP BY policy_field ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def party_analysis(self, top_parties: int = 8) -> dict:
        """Aggregate party behaviour from motions (Antragsteller = the ``factions``
        on a decision): a party × policy-field heatmap, per-party success rates,
        per-field contention and party co-sponsorships. Only ~13 % of decisions name
        an Antragsteller, so this reflects *active motions*, not every vote."""
        from collections import Counter
        from itertools import combinations

        from council.parties import order_key, parties_for_faction

        rows = self._conn.execute(
            "SELECT factions, policy_field, outcome, no_votes, abstentions "
            "FROM council_decisions WHERE kind = 'decision'"
        ).fetchall()

        party_field: dict[str, Counter] = {}
        party_outcome: dict[str, Counter] = {}
        party_total: Counter = Counter()
        field_motion: Counter = Counter()      # motions per field (heatmap columns)
        field_total: Counter = Counter()       # decided votes per field (contention)
        field_contested: Counter = Counter()
        pairs: Counter = Counter()
        with_factions = 0

        for fac, field, outcome, gegen, enth in rows:
            if field and outcome in ("accepted", "rejected", "postponed"):
                field_total[field] += 1
                if (gegen or 0) > 0 or (enth or 0) > 0:
                    field_contested[field] += 1
            try:
                arr = json.loads(fac or "[]")
            except (json.JSONDecodeError, TypeError):
                arr = []
            # Multi-Mapping: „Gruppe FDP/Volt" zählt für FDP UND Volt.
            parties = sorted({p for x in arr for p in parties_for_faction(x)}, key=order_key)
            if not parties:
                continue
            with_factions += 1
            for p in parties:
                party_total[p] += 1
                if field:
                    party_field.setdefault(p, Counter())[field] += 1
                    field_motion[field] += 1
                if outcome:
                    party_outcome.setdefault(p, Counter())[outcome] += 1
            for a, b in combinations(parties, 2):
                pairs[(a, b)] += 1

        top = sorted((p for p, _ in party_total.most_common(top_parties)), key=order_key)
        fields_present = [f for f, _ in field_motion.most_common()]
        matrix = {p: {f: party_field.get(p, Counter()).get(f, 0) for f in fields_present} for p in top}

        success = []
        for p in party_total:
            oc = party_outcome.get(p, Counter())
            decided = oc["accepted"] + oc["rejected"]
            success.append({
                "party": p, "motions": party_total[p],
                "accepted": oc["accepted"], "rejected": oc["rejected"], "postponed": oc["postponed"],
                "rate": round(oc["accepted"] / decided, 3) if decided else None,
            })
        success.sort(key=lambda s: s["motions"], reverse=True)

        contention = [
            {"field": f, "total": field_total[f], "contested": field_contested[f],
             "contested_rate": round(field_contested[f] / field_total[f], 3)}
            for f in sorted(field_total, key=lambda f: field_total[f], reverse=True)
        ]
        alliances = [{"a": a, "b": b, "count": c} for (a, b), c in pairs.most_common(12)]

        return {
            "coverage": {"with_factions": with_factions, "total": len(rows)},
            "topic_matrix": {"parties": top, "fields": fields_present, "matrix": matrix},
            "success_rates": success,
            "contention": contention,
            "alliances": alliances,
        }

    # --- Goal tracking ------------------------------------------------------
    def get_goal_candidates(self, keywords: list[str], limit: int = 400,
                            exclude_goal: str | None = None) -> list[dict]:
        """Decisions whose text/tags match any of a goal's keywords (candidates
        for LLM relevance + stance assessment). With ``exclude_goal`` set, skips
        decisions already linked to that goal — for the incremental daily cron."""
        if not keywords:
            return []
        clause = " OR ".join(
            ["d.title LIKE ? OR d.official_text LIKE ? OR d.summary LIKE ? OR d.policy_tags LIKE ?"] * len(keywords)
        )
        params: list = []
        for kw in keywords:
            p = f"%{kw}%"
            params += [p, p, p, p]
        exclude_sql = ""
        if exclude_goal:
            exclude_sql = " AND d.id NOT IN (SELECT decision_id FROM council_goal_links WHERE goal = ?)"
            params.append(exclude_goal)
        params.append(limit)
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.official_text, d.summary, d.outcome, cs.session_date
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND ({clause}){exclude_sql}
                ORDER BY cs.session_date DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def save_goal_links(self, goal: str, results: dict) -> int:
        """Upsert assessment results for a goal: id -> {relevant, stance, grund}."""
        rows = [(goal, did, 1 if r.get("relevant") else 0, r.get("stance"), r.get("reason"))
                for did, r in results.items()]
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_goal_links (goal, decision_id, relevant, stance, rationale) "
                "VALUES (?, ?, ?, ?, ?)", rows,
            )
        return len(rows)

    def clear_goal_links(self, goal: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM council_goal_links WHERE goal = ?", (goal,))

    def linked_decision_ids(self, goal: str) -> set:
        """Decision ids already linked to a goal (any relevance) — for incremental runs."""
        return {r[0] for r in self._conn.execute(
            "SELECT decision_id FROM council_goal_links WHERE goal = ?", (goal,))}

    def goal_summary(self) -> dict:
        """Per goal: counts of relevant decisions by stance."""
        agg: dict[str, dict] = {}
        for goal, stance, c in self._conn.execute(
            "SELECT goal, stance, COUNT(*) FROM council_goal_links WHERE relevant = 1 GROUP BY goal, stance"
        ):
            g = agg.setdefault(goal, {"advances": 0, "hinders": 0, "neutral": 0, "total": 0})
            g[stance] = c
            g["total"] += c
        return agg

    def goal_detail(self, goal: str) -> list[dict]:
        """Relevant decisions linked to a goal, newest first, with stance + rationale."""
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, gl.stance, gl.rationale
               FROM council_goal_links gl
               JOIN council_decisions d ON d.id = gl.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE gl.goal = ? AND gl.relevant = 1
               ORDER BY cs.session_date DESC""",
            (goal,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Semantic similarity (precomputed offline) --------------------------
    def decisions_for_embedding(self) -> list[dict]:
        """All main decisions with a short text for embedding (id + text).

        Teilabstimmungs-Titel (Änderungsanträge, Design 23a) zählen zum Text des
        Haupt-TOPs — sie tragen oft die konkreten Begriffe („Änderungsantrag der
        Fraktion X: Tempo 30 auf …"), die im knappen Hauptbeschluss fehlen."""
        rows = self._conn.execute(
            "SELECT d.id, d.title, d.summary, d.official_text, sv.stext FROM council_decisions d "
            "LEFT JOIN (SELECT ksinr, parent_item, substr(GROUP_CONCAT(title, ' · '), 1, 400) AS stext "
            "           FROM council_decisions WHERE kind = 'subvote' AND parent_item IS NOT NULL "
            "           GROUP BY ksinr, parent_item) sv "
            "  ON sv.ksinr = d.ksinr AND sv.parent_item = d.item_number "
            "WHERE d.kind = 'decision'"
        ).fetchall()
        out = []
        for r in rows:
            text = f"{r['title'] or ''}. {r['summary'] or r['official_text'] or ''}".strip()[:500]
            if r["stext"]:
                text = f"{text} · {r['stext']}"[:800]
            out.append({"id": r["id"], "text": text})
        return out

    def set_similar(self, rows: list[tuple]) -> int:
        """Replace all similarity links. ``rows`` = (decision_id, neighbor_id, rank, score)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_similar")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_similar (decision_id, neighbor_id, rank, score) "
                "VALUES (?, ?, ?, ?)", rows,
            )
        return len(rows)

    def save_embeddings(self, rows: list[tuple]) -> int:
        """Replace all decision vectors. ``rows`` = (decision_id, float32 bytes)."""
        with self._conn:
            self._conn.execute("DELETE FROM council_embeddings")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_embeddings (decision_id, vector) VALUES (?, ?)", rows,
            )
        return len(rows)

    def get_embeddings(self) -> list:
        """All (decision_id, vector-blob) rows — caller rebuilds the matrix."""
        return self._conn.execute(
            "SELECT decision_id, vector FROM council_embeddings ORDER BY decision_id"
        ).fetchall()

    def embeddings_version(self) -> tuple:
        """Billiger Versionsschlüssel des Embedding-Bestands. Der Matrix-Cache in
        council/embeddings.py lädt neu, sobald sich der Wert ändert — ohne den
        früher nötigen Service-Neustart nach embed_decisions.py. ``data_version``
        deckt dabei auch ein Re-Embedding ab, das Anzahl und ids unverändert
        lässt (Modellwechsel): Es zählt hoch, sobald ein *anderer* Prozess die
        DB-Datei geschrieben hat."""
        count, max_id = self._conn.execute(
            "SELECT COUNT(*), COALESCE(MAX(decision_id), 0) FROM council_embeddings"
        ).fetchone()
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, max_id, data_version)

    # ---- Vorlagen-Chunk-Embeddings (semantische Suche im Sachverhalt) ----

    def vorlagen_missing_embeddings(self) -> list[dict]:
        """Vorlagen (mit Text, an ≥1 Beschluss hängend), deren Chunk-Vektoren
        fehlen oder deren Text sich seit dem letzten Embedding geändert hat.
        Der Abgleich läuft über den SHA-256 des Volltexts (text_hash)."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT template_number, MIN(text_hash) FROM council_template_embeddings GROUP BY template_number"
        ).fetchall())
        rows = self._conn.execute(
            "SELECT v.template_number, MAX(v.raw_text) AS raw_text FROM council_templates v "
            "WHERE v.status = 'ok' AND v.template_number IN "
            "  (SELECT DISTINCT template_number FROM council_decisions "
            "   WHERE kind = 'decision' AND template_number IS NOT NULL AND template_number != '') "
            "GROUP BY v.template_number"
        ).fetchall()
        out = []
        for r in rows:
            text = r["raw_text"] or ""
            if not text.strip():
                continue
            h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            if stored.get(r["template_number"]) != h:
                out.append({"template_number": r["template_number"], "raw_text": text, "text_hash": h})
        return out

    def replace_vorlage_embeddings(self, template_number: str, text_hash: str,
                                   chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Vorlage komplett ersetzen (alte Chunk-Anzahl
        kann abweichen, deshalb erst löschen)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_template_embeddings WHERE template_number = ?", (template_number,))
            self._conn.executemany(
                "INSERT INTO council_template_embeddings "
                "(template_number, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(template_number, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_vorlage_embeddings(self) -> list:
        """Alle (template_number, chunk_text, vector)-Zeilen — der Aufrufer baut die Matrix."""
        return self._conn.execute(
            "SELECT template_number, chunk_text, vector FROM council_template_embeddings "
            "ORDER BY template_number, chunk_idx"
        ).fetchall()

    def vorlage_embeddings_version(self) -> tuple:
        """Versionsschlüssel analog embeddings_version(), für den Chunk-Matrix-Cache."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_template_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    # ---- Anlagen-Embeddings (Task 33, Dokumentenkanal) ---------------------

    def anlagen_missing_embeddings(self, limit: int | None = None) -> list[dict]:
        """Anlagen mit Text, deren Chunk-Vektoren fehlen oder deren Text sich
        geändert hat (SHA-256-Abgleich wie bei den Vorlagen). Neueste zuerst —
        frisches Material zuerst durchsuchbar."""
        import hashlib

        stored = dict(self._conn.execute(
            "SELECT document_id, MIN(text_hash) FROM council_anlage_embeddings "
            "GROUP BY document_id").fetchall())
        # `status = 'ok'` schließt nur ungelesene und kaputte Anlagen aus. Wie
        # der Text entstanden ist — Textebene oder Sehmodell — steht in
        # `ocr_model` und ist hier KEIN Kriterium: Ein gescannter
        # Wirtschaftsplan ist so durchsuchbar wie ein getippter.
        rows = self._conn.execute(
            "SELECT a.document_id, a.label, a.raw_text, v.template_number, "
            "       v.title AS template_title FROM council_attachments a "
            "LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            "WHERE a.status = 'ok' AND a.raw_text IS NOT NULL AND a.raw_text != '' "
            "ORDER BY a.document_id DESC").fetchall()
        out = []
        for r in rows:
            # HIER wird maskiert und nicht beim Speichern: `raw_text` bleibt
            # vollständig (die Parser brauchen ihn), aber was in die
            # Chunk-Vektoren und damit in Antworten der KI-Frage geht, trägt
            # keine Kontonummern, Telefonnummern, E-Mail-Adressen und
            # Anschriften mehr (`council/kontaktdaten.py`).
            text = maskieren(r["raw_text"])
            # v2 nimmt Metadaten in Hash und Vektor auf. Ohne Vorlagentitel
            # waren gleichnamige Umweltberichte verschiedener Baugebiete kaum
            # zu unterscheiden. Der Hash verwendet den maskierten Text: In
            # Vektoren und Antwortfundstellen gelangen weiterhin keine
            # Kontaktdaten.
            material = "\0".join(("anlage-v2", r["label"] or "",
                                  r["template_number"] or "", r["template_title"] or "",
                                  text))
            h = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
            if stored.get(r["document_id"]) != h:
                out.append({"document_id": r["document_id"], "label": r["label"],
                            "template_number": r["template_number"],
                            "template_title": r["template_title"],
                            "raw_text": text, "text_hash": h})
                if limit and len(out) >= limit:
                    break
        return out

    def replace_anlage_embeddings(self, document_id: int, text_hash: str,
                                  chunks: list[tuple[str, bytes]]) -> None:
        """Chunk-Text+Vektor einer Anlage komplett ersetzen."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_anlage_embeddings WHERE document_id = ?", (document_id,))
            self._conn.executemany(
                "INSERT INTO council_anlage_embeddings "
                "(document_id, chunk_idx, text_hash, chunk_text, vector) VALUES (?, ?, ?, ?, ?)",
                [(document_id, i, text_hash, text, vec) for i, (text, vec) in enumerate(chunks)],
            )

    def get_anlage_embeddings(self) -> list:
        """Alle (document_id, chunk_text, vector)-Zeilen für die Matrix."""
        return self._conn.execute(
            "SELECT document_id, chunk_text, vector FROM council_anlage_embeddings "
            "ORDER BY document_id, chunk_idx"
        ).fetchall()

    def anlage_embeddings_version(self) -> tuple:
        count = self._conn.execute(
            "SELECT COUNT(*) FROM council_anlage_embeddings").fetchone()[0]
        data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        return (count, data_version)

    def anlagen_by_ids(self, document_ids: list[int]) -> list[dict]:
        """Anzeige-Zeilen der Anlagen-Treffer, Reihenfolge der ids bleibt:
        Label, PDF-Link und die Vorlage (Nummer + Titel), zu der sie gehören."""
        if not document_ids:
            return []
        ph = ",".join("?" * len(document_ids))
        rows = self._conn.execute(
            f"SELECT a.document_id, a.label, a.url, a.kvonr, "
            f"       v.template_number, v.title AS template_title "
            f"FROM council_attachments a LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            f"WHERE a.document_id IN ({ph})", document_ids).fetchall()
        by_id = {r["document_id"]: dict(r) for r in rows}
        return [by_id[i] for i in document_ids if i in by_id]

    def anlagen_metadata_rows(self) -> list[dict]:
        """Kleine Metadatenliste für den lexikalischen Anlagen-Sicherungsweg.

        Volltexte und Vektoren bleiben in ihren spezialisierten Tabellen; für
        exakte Angaben wie „Bodengutachten Kaiserstraße/Bleicherstraße“ reichen
        Label, Vorlagennummer und -titel. Rund 5.000 kompakte Zeilen sind
        billiger als ein zweiter großer Suchindex.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT a.document_id, a.label, v.template_number, "
            "       v.title AS template_title FROM council_attachments a "
            "LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            "WHERE a.status = 'ok' AND a.raw_text IS NOT NULL AND a.raw_text != '' "
            "ORDER BY a.document_id DESC").fetchall()]

    def decision_ids_for_vorlagen(self, vorlage_nrs: list[str]) -> dict[str, list[int]]:
        """template_number → Beschluss-ids (alle Beratungsstationen), neueste zuerst.
        Bildet Vorlagen-Chunk-Treffer der semantischen Suche auf zitierbare
        Beschlüsse ab."""
        nrs = sorted({(n or "").strip() for n in vorlage_nrs if n and str(n).strip()})
        if not nrs:
            return {}
        ph = ",".join("?" * len(nrs))
        rows = self._conn.execute(
            f"""SELECT d.template_number, d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE d.kind = 'decision' AND d.template_number IN ({ph})
                ORDER BY cs.session_date DESC, d.id DESC""",
            nrs,
        ).fetchall()
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r["template_number"], []).append(r["id"])
        return out

    # ---- Laufende Bauleitplan-Beteiligungen (council/beteiligung.py) ----



    # ---- Haushalt als Geldfragen-Quelle (Tim, 09.08.) ----

    #: Themenwörter, die auf einen Teilhaushalt zeigen, ohne dessen Namen zu
    #: teilen. „Kongresshalle" und „Kultur, Museen, Sport" haben keinen
    #: gemeinsamen Wortstamm — rein lexikalisch ist die Zuordnung nicht zu
    #: finden, obwohl sie eindeutig ist. Bewusst knapp gehalten: Jede Zeile
    #: ist eine Behauptung darüber, wo etwas im Haushalt steht.
    HAUSHALTS_SYNONYME = {
        "verkehr": ("mobilität", "radverkehr", "fahrrad", "bus", "parken",
                    "parkgebühren", "straßenbahn", "fußverkehr", "damm"),
        "kultur": ("veranstaltung", "kongress", "halle", "museum", "theater",
                   "bibliothek", "stadion", "schwimmbad", "bäder"),
        "klima": ("baum", "baumschutz", "grünfläche", "natur",
                  "naturschutz", "umweltschutz", "emission"),
        "stadtplanung": ("bebauungsplan", "sanierungsgebiet", "stadtentwicklung",
                         "isek", "flächennutzungsplan", "wohnraum", "leerstand"),
        "schule": ("bildung", "schulbau", "ganztag"),
        "jugend": ("kita", "kindertagesstätte", "krippe", "jugendhilfe",
                   "spielplatz", "familie"),
        # Gemessen 02.09.2026 an der Live-Antwort: „Was stand 2022 im Haushalt
        # für die Feuerwehr?" fand keinen Teilhaushalt — die Feuerwehr heißt
        # dort „Sicherheit und Ordnung", und das sagt kein Fragewortlaut.
        "sicherheit": ("feuerwehr", "brandschutz", "rettungsdienst",
                       "katastrophenschutz", "ordnungsamt", "bürgeramt",
                       "ordnungsdienst"),
        "soziales": ("sozialhilfe", "grundsicherung", "wohngeld", "pflege",
                     "asyl", "geflüchtete", "obdachlos", "gesundheitsamt"),
        "finanzmanagement": ("kämmerei", "stadtkasse", "steuern"),
    }

    @staticmethod
    def _bereich_passt(area: str, woerter: list[str]) -> bool:
        """Trifft eines der Suchwörter diesen Teilhaushalt?

        Der frühere Test lief in die falsche Richtung: ``wort in area``
        findet „Verkehr" in „Verkehr und Straßenbau", aber nicht
        „Radverkehr" — und deutsche Suchbegriffe sind fast immer die
        längeren Komposita. Gemessen am 20.08.2026: „Verkehr" traf, aber
        „Mobilitätsplan", „Radverkehr", „Kongresshalle" und
        „Baumschutzsatzung" lieferten allesamt null Zeilen, obwohl es für
        jedes einen passenden Bereich gibt.

        Deshalb wird der Bereichsname in Wortmarken zerlegt und beidseitig
        geprüft — ein Kompositum trägt sein Grundwort am Ende („Radverkehr"),
        eine Ableitung am Anfang („Mobilitätsplan").
        """
        marken = [t for t in re.split(r"[^a-zäöüß]+", area.lower()) if len(t) >= 4]
        for wort in woerter:
            for mark in marken:
                if wort == mark:
                    return True
                kurz, lang = sorted((wort, mark), key=len)
                # Nur Anfang oder Ende: „Transport" enthält zwar „sport",
                # aber eben nicht am Rand.
                if len(kurz) >= 5 and (lang.startswith(kurz) or lang.endswith(kurz)):
                    return True
                for kopf, synonyme in CouncilStore.HAUSHALTS_SYNONYME.items():
                    if mark.startswith(kopf) and any(
                            wort.startswith(s) or wort.endswith(s) for s in synonyme):
                        return True
        return False

    def haushalt_fuer_begriffe(self, begriffe: list[str], limit: int = 3,
                               year: int | None = None) -> list[dict]:
        """Teilhaushalts-Zeilen des neuesten Jahres, deren Bereich zu einem der
        Suchbegriffe passt („Radverkehr" → „Verkehr und Straßenbau"); fragt
        jemand nach dem Haushalt insgesamt, kommt die Summenzeile. Für den
        Geld-Kontext der KI-Frage — Plan-Zahlen, klar getrennt von Beschlüssen."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_budget", "year", gefragt)
        if not year:
            return []
        # 16 statt 10: Die Begriffe der Gründlichen Recherche kommen aus
        # mehreren Facetten, das treffende Wort steht dort oft weiter hinten.
        woerter = [w.lower() for w in begriffe if len(w) >= 4][:16]
        rows = self._conn.execute(
            "SELECT year, area, revenues, expenses, result, is_total "
            "FROM council_budget WHERE year = ?", (year,)).fetchall()
        out = []
        for r in rows:
            if r["is_total"]:
                if any(w in ("haushalt", "gesamthaushalt", "haushaltsplan") for w in woerter):
                    out.append(dict(r))
                continue
            if self._bereich_passt(r["area"] or "", woerter):
                out.append(dict(r))
        out = out[:limit]
        if abweicht:
            for r in out:
                r["year_asked"] = gefragt
        # Entwicklung mitgeben: derselbe Bereich im ältesten vorhandenen Jahr.
        # Nur bei EXAKT gleichem Namen — die Teilhaushalts-Zuschnitte ändern
        # sich über die Jahre, ein Vergleich über Zuschnittgrenzen wäre falsch.
        if out:
            frueh = self._conn.execute("SELECT MIN(year) FROM council_budget").fetchone()[0]
            if frueh and frueh != year:
                namen = [r["area"] for r in out]
                platz = ",".join("?" * len(namen))
                alt = {
                    r["area"]: r for r in self._conn.execute(
                        f"SELECT area, revenues, expenses FROM council_budget "
                        f"WHERE year = ? AND area IN ({platz})", (frueh, *namen))
                }
                for r in out:
                    a = alt.get(r["area"])
                    if a:
                        r["year_before"] = frueh
                        r["expenses_before"] = a["expenses"]
                        r["revenues_before"] = a["revenues"]
        return out

    #: Suchbegriffe → Steuerart, wie sie im Open-Data-CSV heißt. Bewusst
    #: kuratiert statt Substring-Suche: „Steuer" allein trifft sonst jede Art,
    #: und „Grundsteuer" steckt in „Grundsteuer A+B".
    _STEUER_SYNONYME = {
        "gewerbesteuer": "Gewerbesteuer (-umlage)",
        "gewerbe": "Gewerbesteuer (-umlage)",
        "grundsteuer": "Grundsteuer A+B",
        "grundbesitz": "Grundsteuer A+B",
        "einkommensteuer": "Einkommensteueranteil",
        "einkommenssteuer": "Einkommensteueranteil",
        "umsatzsteuer": "Gemeindeanteil an der Umsatzsteuer",
        "mehrwertsteuer": "Gemeindeanteil an der Umsatzsteuer",
        "vergnügungssteuer": "Vergnügungssteuer",
        "vergnuegungssteuer": "Vergnügungssteuer",
        "getränkesteuer": "Getränkesteuer",
    }

    def steuern_fuer_begriffe(self, begriffe: list[str],
                              year: int | None = None) -> list[dict]:
        """IST-Steuereinnahmen zu den gefragten Steuerarten: neuester Wert plus
        der Wert von vor zehn Jahren (Entwicklung), je Art. Fragt jemand
        allgemein nach „Steuern"/„Einnahmen", kommt die Gesamtsumme.

        Klar getrennt vom Haushalt: Das hier sind ABRECHNUNGSZAHLEN, keine
        Planwerte — der Prompt-Baustein muss das benennen."""
        woerter = {w.lower().strip(".,;:!?") for w in begriffe}
        arten: list[str] = []
        for w in woerter:
            art = self._STEUER_SYNONYME.get(w)
            if art and art not in arten:
                arten.append(art)
        if not arten and woerter & {"steuern", "steuereinnahmen", "steuer",
                                    "einnahmen", "steuerkraft"}:
            arten = ["total"]
        if not arten:
            return []
        neuestes, abweicht = _geld.jahrgang(self._conn, "council_taxes", "year", year)
        if not neuestes:
            return []
        out: list[dict] = []
        for art in arten[:3]:
            rows = self._conn.execute(
                "SELECT year, amount FROM council_taxes WHERE kind = ? AND year IN (?, ?)",
                (art, neuestes, neuestes - 10)).fetchall()
            werte = {r["year"]: r["amount"] for r in rows}
            if neuestes not in werte:
                continue
            out.append({"kind": art, "year": neuestes, "amount": werte[neuestes],
                        "year_before": neuestes - 10 if (neuestes - 10) in werte else None,
                        "amount_before": werte.get(neuestes - 10),
                        **({"year_asked": year} if abweicht else {})})
        return out

    def steuerkraft_kontext(self, year: int | None = None) -> dict | None:
        """Steuerkraftmesszahl + Schlüsselzuweisungen der beiden jüngsten Jahre.

        Für Fragen nach Hebesätzen und „mehr Steuern einnehmen": Steigt die
        eigene Steuerkraft, sinken die Zuweisungen des Landes (NFAG) — ohne
        diesen Kontext klingt jede Mehreinnahme nach vollem Gewinn."""
        wo = "tax_index IS NOT NULL AND allocations IS NOT NULL"
        gewaehlt, abweicht = _geld.jahrgang(self._conn, "council_tax_capacity", "year", year, wo)
        if gewaehlt is None:
            return None
        rows = self._conn.execute(
            f"SELECT year, tax_index, allocations FROM council_tax_capacity WHERE {wo} "
            "AND year <= ? ORDER BY year DESC LIMIT 2", (gewaehlt,)).fetchall()
        if len(rows) < 2:
            return None
        neu, alt = dict(rows[0]), dict(rows[1])
        return {"year": neu["year"], "tax_index": neu["tax_index"], "allocations": neu["allocations"],
                "year_before": alt["year"], "tax_index_before": alt["tax_index"],
                "zuweisungen_davor": alt["allocations"],
                **({"year_asked": year} if abweicht else {})}

    # ---- Der Haushalts-Bestand als Quelle der KI-Frage (Tim, 16.08.) -------
    #
    # Bis hierher kannte die KI-Frage drei Geld-Quellen: Plan (council_budget),
    # Ist-Steuern (council_taxes) und die NFAG-Mechanik (council_tax_capacity).
    # Der Bestand darunter — Jahresabschlüsse, Produktebene, Prüfberichte,
    # Konzern, Städtevergleich — war für sie unsichtbar.
    #
    # ZWEI REGELN GELTEN FÜR ALLE METHODEN HIER:
    #
    # 1. Jede liefert wenige Zeilen, nicht den Bestand. Der Antwort-Prompt hat
    #    ein Zeichenbudget; ein Baustein, der 377 Produkte anhängt, verdrängt
    #    die Beschlüsse, nach denen gefragt wurde.
    # 2. Jede liefert ihren **Beleg** mit (`_beleg`). Eine Zahl ohne Fundstelle
    #    ist in diesem Bereich keine Zahl, sondern eine Behauptung — und der
    #    Prompt kann nur zitieren, was im Kontext steht.

    @staticmethod
    def _falte_wort(wort: str) -> str:
        """Kleingeschrieben, Umlaute ausgeschrieben, Satzzeichen ab."""
        w = wort.lower().strip(".,;:!?\"'()[]")
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            w = w.replace(a, b)
        return w

    @classmethod
    def _stamm(cls, wort: str) -> str:
        """Grober Wortstamm für den Begriffs-Abgleich — auf 6 Zeichen gekappt.

        Die Kappung ist der ganze Zweck. „Gewerbesteuer" und „Steuern und
        ähnliche Abgaben" haben kein gemeinsames Wort und in der einen
        Richtung auch keine gemeinsame Teilzeichenkette
        (``"steuern" not in "gewerbesteuer"``) — wohl aber denselben Stamm
        ``steuer``. Ohne ihn findet „Warum kam mehr Gewerbesteuer rein?" die
        zugehörige Erläuterung des Jahresabschlusses nicht."""
        return cls._falte_wort(wort)[:6]

    @classmethod
    def _trifft(cls, text: str | None, begriffe: list[str]) -> int:
        """Wie viele Suchbegriffe stecken in ``text``? 0 = kein Treffer.

        BEIDE RICHTUNGEN, und das ist nötig: Der Begriff kann im Text stecken
        („Feuerwehr" in „Brandschutz und Feuerwehr") und der Text im Begriff
        („Steuern" in „Gewerbesteuer"). Eine Richtung allein verfehlt je einen
        der beiden Fälle, und beide kommen im Bestand vor."""
        if not text:
            return 0
        worte = [w for w in re.split(r"[^\wÄÖÜäöüß]+", text) if w]
        text_voll = " ".join(cls._falte_wort(w) for w in worte)
        text_staemme = [s for s in (cls._stamm(w) for w in worte) if len(s) >= 4]
        n = 0
        for b in begriffe:
            b_voll = cls._falte_wort(b)
            b_stamm = cls._stamm(b)
            if len(b_stamm) < 4:
                continue
            if b_stamm in text_voll or any(s in b_voll for s in text_staemme):
                n += 1
        return n

    def _beleg(self, herkunft_id: int | None) -> dict | None:
        """Fundstelle einer Zahl: Dokument, Stelle darin, Stichtag.

        Bewusst ohne die Erklärsätze zu den Proben (``get_herkunft``): Die
        gehören auf die Haushalts-Seiten, wo Platz für sie ist. Im Prompt
        zählt, was die Antwort zitieren können muss — Dokument und Stelle."""
        if herkunft_id is None:
            return None
        try:
            r = self._conn.execute(
                "SELECT label, citation, page, as_of, url FROM council_provenance "
                "WHERE id = ?", (herkunft_id,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return dict(r) if r else None

    def gebuehren_fuer_begriffe(self, begriffe: list[str],
                                limit_jahre: int = 4, year: int | None = None) -> dict | None:
        """Gebührenbedarfsberechnungen passend zur Frage, jüngste zuerst.

        Die Tabelle enthält drei getrennte Kalkulationen. Eine Müllfrage
        braucht beide Abfallbereiche, eine Frage zur Straßenreinigung nur
        deren Anlage; bei einer allgemeinen Gebührenfrage kommen alle drei.
        Jede Zeile trägt ihren eigenen Beleg, weil die Bereiche aus
        unterschiedlichen Anlagen stammen.
        """
        worte = {self._falte_wort(w) for w in begriffe if w}
        text = " ".join(sorted(worte))
        bereiche: list[str] = []
        if any(w in text for w in ("abfall", "muell", "tonne", "behaelter",
                                   "restmuell", "biomuell")):
            bereiche.extend(("waste_treatment", "waste_collection"))
        if any(w in text for w in ("strassenreinig", "kehrgeb", "kehrdienst")):
            bereiche.append("street_cleaning")
        if not bereiche and any(w in text for w in ("gebuehr", "gebuehrenbedarf")):
            bereiche = ["waste_treatment", "waste_collection", "street_cleaning"]
        bereiche = list(dict.fromkeys(bereiche))
        if not bereiche:
            return None
        try:
            platz = ",".join("?" for _ in bereiche)
            rows = [dict(r) for r in self._conn.execute(
                "SELECT year, area, area_name, cost_calculation, deductions, "
                "costs_to_cover, reference_quantity, reference_unit, fee, "
                "fee_proposed, template_number, herkunft_id "
                f"FROM council_fees WHERE area IN ({platz}) "
                "ORDER BY area, year DESC", bereiche)]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        gruppen: list[dict] = []
        # Das gefragte Jahr zuerst, wenn der Bereich es führt — sonst bleibt
        # die Reihenfolge „jüngste zuerst", und der Baustein sagt, dass das
        # gefragte Jahr fehlt.
        vorhanden = {r["year"] for r in rows}
        abweicht = year is not None and year not in vorhanden
        for area in bereiche:
            werte = [r for r in rows if r["area"] == area]
            if year in vorhanden:
                werte = ([r for r in werte if r["year"] == year]
                         + [r for r in werte if r["year"] != year])
            werte = werte[:limit_jahre]
            if not werte:
                continue
            for r in werte:
                r["beleg"] = self._beleg(r.get("herkunft_id"))
            gruppen.append({"area": area,
                            "area_name": werte[0]["area_name"],
                            "werte": werte})
        if not gruppen:
            return None
        return {"bereiche": gruppen, **({"year_asked": year} if abweicht else {})}

    def result_actual_for_terms(self, begriffe: list[str], limit: int = 2,
                                year: int | None = None) -> dict | None:
        """„Geplant und tatsächlich" aus dem jüngsten Jahresabschluss.

        Der Unterschied zu ``haushalt_fuer_begriffe`` ist das ganze Anliegen:
        Dort stehen Planwerte, hier steht, was daraus geworden ist. Geliefert
        werden die Summenzeilen der Gesamtrechnung (Erträge 12, Aufwendungen
        20) und — wenn die Frage einen Bereich nennt — bis zu ``limit``
        Teilhaushalte.

        ``plan_kind`` reist mit: „Plan" heißt 2018 Gesamtermächtigung und 2020
        Ansatz samt Nachtrag. Eine Abweichung ohne ihre Bezugsgröße zu nennen,
        wäre in genau den zwei Jahrgängen falsch, in denen es darauf ankommt."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_income_statement", "year",
                                        gefragt, "result IS NOT NULL")
        if not year:
            return None
        # Die Gesamtrechnung mit ALLEN Posten, die Teilhaushalte nur mit ihren
        # Summen: „Was kostet das Personal?" braucht Posten 13 der Gesamt-
        # rechnung — bis 09/2026 lieferte diese Methode nur die Summen 12/20,
        # und die Antwort kannte den Personalaufwand nicht, obwohl er dastand.
        rows = [dict(r) for r in self._conn.execute(
            "SELECT sub_budget_no, sub_budget_name, nr, label, budgeted, plan, plan_kind, "
            " result, deviation, herkunft_id FROM council_income_statement "
            "WHERE year = ? AND (sub_budget_no IS NULL OR nr IN (12, 20)) "
            "ORDER BY sub_budget_no, nr", (year,))]
        if not rows:
            return None

        def paar(part: list[dict]) -> dict:
            e = next((r for r in part if r["nr"] == 12), {})
            a = next((r for r in part if r["nr"] == 20), {})
            # `plan` fällt auf `ansatz` zurück — Zeilen von vor #510 tragen
            # dort NULL (ALTER TABLE füllt nichts nach), s. get_plan_ist.
            return {
                "name": (a.get("sub_budget_name") or e.get("sub_budget_name")),
                "revenues_planned": e.get("budgeted") if e.get("plan") is None else e.get("plan"),
                "revenues_actual": e.get("result"),
                "expenses_planned": a.get("budgeted") if a.get("plan") is None else a.get("plan"),
                "expenses_actual": a.get("result"),
                "plan_kind": a.get("plan_kind") or e.get("plan_kind"),
                "herkunft_id": a.get("herkunft_id") or e.get("herkunft_id"),
            }

        gesamt_rows = [r for r in rows if r["sub_budget_no"] is None]
        gesamt = paar(gesamt_rows)

        def wert(r: dict) -> tuple:
            return (r.get("budgeted") if r.get("plan") is None else r.get("plan"), r.get("result"))

        # Die Ergebniszeilen (21 ordentlich, 24 außerordentlich) immer: „Wie
        # war das Jahresergebnis?" ist die schlichteste Frage an den Abschluss,
        # und die Summen 12/20 beantworten sie nur über eine Rechnung, die
        # das Modell nicht anstellen soll.
        ergebnis = {}
        for r in gesamt_rows:
            if r["nr"] == 21:
                ergebnis["ordentlich"] = wert(r)
            elif r["nr"] == 24:
                ergebnis["ausserordentlich"] = wert(r)
        # Die einzelnen Posten NUR bei Begriffstreffer (Personal, Zinsen,
        # Transfer, Abschreibungen …) — sonst wären es 22 Zeilen je Frage.
        posten: list[dict] = []
        if begriffe:
            kandidaten = [r for r in gesamt_rows if r["nr"] not in (12, 20, 21, 24)]
            bewertet = [(self._trifft(r.get("label"), begriffe), r) for r in kandidaten]
            posten = [{"nr": r["nr"], "label": r["label"], "planned": wert(r)[0],
                       "actual": r.get("result"), "deviation": r.get("deviation")}
                      for n, r in sorted(bewertet,
                                         key=lambda x: (-x[0], -abs(x[1].get("deviation") or 0)))
                      if n][:3]
        bereiche: list[dict] = []
        if begriffe:
            nach_thh: dict[int, list[dict]] = {}
            for r in rows:
                if r["sub_budget_no"] is not None:
                    nach_thh.setdefault(r["sub_budget_no"], []).append(r)
            bewertet = [(self._trifft(t[0].get("sub_budget_name"), begriffe), paar(t))
                        for t in nach_thh.values()]
            bereiche = [b for n, b in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        return {"year": year, "gesamt": gesamt, "bereiche": bereiche,
                "posten": posten, "ergebnis": ergebnis,
                "beleg": self._beleg(gesamt.get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def abweichungsgruende_fuer_begriffe(self, begriffe: list[str],
                                         limit: int = 3, year: int | None = None) -> list[dict]:
        """Das *Warum* zu den Abweichungen, in den Worten der Verwaltung.

        Passt kein Begriff, kommen die **größten** Abweichungen: Wer „Warum
        wich der Haushalt ab?" fragt, meint die, über die es sich zu reden
        lohnt — und der Fragetyp-Filter davor sorgt dafür, dass diese Methode
        gar nicht erst läuft, wenn es nicht um Geld geht."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_variance_reasons", "year", gefragt)
        if not year:
            return []
        rows = [dict(r) for r in self._conn.execute(
            "SELECT year, nr, label, delta_meur, percent, text, herkunft_id "
            "FROM council_variance_reasons WHERE year = ? ORDER BY nr", (year,))]
        treffer = [(self._trifft(f"{r['label']} {r['text']}", begriffe), r) for r in rows]
        passend = [r for n, r in sorted(treffer, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            passend = sorted(rows, key=lambda r: -abs(r.get("delta_meur") or 0))[:limit]
        for r in passend:
            r["beleg"] = self._beleg(r.get("herkunft_id"))
            if abweicht:
                r["year_asked"] = gefragt
        return passend

    def pruefberichte_fuer_begriffe(self, begriffe: list[str], limit: int = 4,
                                    year: int | None = None) -> dict | None:
        """Feststellungen des Rechnungsprüfungsamts zum jüngsten geprüften
        Jahrgang.

        Ohne Begriffs-Treffer kommen die **wiederholten** Beanstandungen
        zuerst: Etwas, das der Prüfer zum wiederholten Mal aufschreibt, ist der
        Kern der Frage „Was wurde beanstandet?" — eine einmalige Randnotiz
        nicht."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_audit_reports", "year", gefragt)
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT year, mark, mark_name, text_number, section, chain, page, text, "
            " herkunft_id FROM council_audit_reports WHERE year = ? ORDER BY seq", (year,))]
        if not rows:
            return None
        rang = {"WB": 0, "B": 1, "H": 2, "K": 3}
        bewertet = [(self._trifft(f"{r['section']} {r['text']}", begriffe), r) for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            passend = sorted(rows, key=lambda r: rang.get(r["mark"], 9))[:limit]
        # Wie viele Feststellungen es insgesamt gibt, gehört dazu: Ohne die
        # Zahl liest sich eine Auswahl von vier wie der ganze Bericht.
        zaehl: dict[str, int] = {}
        for r in rows:
            zaehl[r["mark_name"]] = zaehl.get(r["mark_name"], 0) + 1
        return {"year": year, "feststellungen": passend, "gesamt": len(rows),
                "nach_marke": zaehl, "beleg": self._beleg(rows[0].get("herkunft_id"))}

    def produkte_fuer_begriffe(self, begriffe: list[str], limit: int = 4,
                               year: int | None = None) -> dict | None:
        """Aufgaben der Stadt mit Kosten, Amt, **Rechtsgrundlage** und der
        Spielraum-Selbstauskunft des Plans.

        Die Rechtsgrundlage ist der Grund, warum diese Quelle in der KI-Frage
        etwas kann, das keine andere kann: „Muss die Stadt das Theater
        betreiben?" beantwortet kein Beschluss und keine Haushaltszeile —
        ``legal_basis`` schon.

        Anders als ``get_produkte(suche=…)`` verlangt diese Suche **nicht**,
        dass jeder Begriff trifft: Die Suchbegriffe kommen aus der
        Query-Expansion und enthalten Synonyme, die absichtlich nicht alle
        passen. Sortiert wird nach Trefferzahl, dann nach Zuschussbedarf."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_products", "year", gefragt)
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT product_no, product_name, office, expenses, result, "
            " short_description, legal_basis, controllability, herkunft_id "
            "FROM council_products WHERE year = ?", (year,))]
        bewertet = [(self._trifft(f"{r['product_name']} {r.get('office') or ''} "
                                  f"{r.get('short_description') or ''}", begriffe), r)
                    for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: (-x[0], x[1].get("result") or 0))
                   if n][:limit]
        if not passend:
            return None
        for r in passend:
            r["beleg"] = self._beleg(r.get("herkunft_id"))
        return {"year": year, "produkte": passend,
                **({"year_asked": gefragt} if abweicht else {})}

    def konzern_kontext(self, year: int | None = None) -> dict | None:
        """Der Konzern Stadt: Erträge, Aufwendungen und die größten Träger.

        Dazu die Kernverwaltung desselben Jahres aus dem Jahresabschluss — die
        Differenz ist der ganze Punkt. „Was kostet die Stadt?" beantwortet der
        Kernhaushalt zu klein, weil Klinikum, Eigenbetriebe und Beteiligungen
        nicht darin stehen."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_group_items", "year", gefragt)
        if not year:
            return None
        # Über die ROLLE, nicht über die Nummer: Posten 15 ist bis 2018 die
        # Ertragssumme und ab 2019 der Versorgungsaufwand (s. Schema-Kommentar).
        summen = {r["role"]: dict(r) for r in self._conn.execute(
            "SELECT role, label, amount, herkunft_id FROM council_group_items "
            "WHERE year = ? AND role IN ('revenues_total', 'expenses_total')", (year,))}
        entity = [dict(r) for r in self._conn.execute(
            "SELECT kind, entity, amount_keur FROM council_group_entities "
            "WHERE year = ? AND kind = 'expenses' AND entity_key != 'konsolidierung' "
            "ORDER BY amount_keur DESC LIMIT 5", (year,))]
        if not summen and not entity:
            return None
        revenues = summen.get("revenues_total") or {}
        expense = summen.get("expenses_total") or {}
        return {"year": year, "revenues": revenues.get("amount"),
                "expenses": expense.get("amount"), "entity": entity,
                "kern": self.kernverwaltung_ist().get(year) or {},
                "beleg": self._beleg(expense.get("herkunft_id")
                                     or revenues.get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def staedtevergleich_kontext(self, series: str = "tax_capacity",
                                 year: int | None = None) -> dict | None:
        """Die jüngste Kennzahl einer Reihe für alle acht kreisfreien Städte.

        Eine Kennzahl, nicht alle: Der Vergleich soll die Antwort einordnen
        („Oldenburg liegt auf Platz 5 von 8"), nicht eine Tabelle in den
        Prompt schreiben."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_city_comparison", "year", gefragt,
                                        f"series = '{series}'")
        if not year:
            return None
        indicator = self._conn.execute(
            "SELECT indicator FROM council_city_comparison WHERE series = ? AND year = ? "
            "GROUP BY indicator ORDER BY COUNT(*) DESC, indicator LIMIT 1",
            (series, year)).fetchone()
        if not indicator:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT city, value, unit, herkunft_id FROM council_city_comparison "
            "WHERE series = ? AND year = ? AND indicator = ? ORDER BY value DESC",
            (series, year, indicator[0]))]
        if not rows:
            return None
        return {"year": year, "series": series, "indicator": indicator[0],
                "unit": rows[0].get("unit"), "staedte": rows,
                "beleg": self._beleg(rows[0].get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def ansatz_fuer_begriffe(self, begriffe: list[str], limit: int = 4,
                             year: int | None = None,
                             frage: list[str] | None = None) -> dict | None:
        """Einnahme- und Ausgabearten des jüngsten **Planjahres** aus dem
        Gesamtergebnishaushalt.

        Nur ``kind='budget'``: Die Finanzplanungsjahre desselben Dokuments sind
        eine Vorausschau nach § 8 NKomVG und kein beschlossener Haushalt. Sie
        in einen Antwort-Kontext zu legen hieße, dem Modell einen Plan für
        2029 anzubieten, den nie jemand aufgestellt hat."""
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_income_budget", "year", gefragt,
                                        "kind = 'budget'")
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT nr, label, amount, is_total, herkunft_id "
            "FROM council_income_budget WHERE year = ? AND kind = 'budget' ORDER BY nr",
            (year,))]
        if not rows:
            return None
        bewertet = [(self._trifft(r["label"], begriffe), r) for r in rows]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        # `treffer` sagt dem Aufrufer, ob die Begriffe einen Posten getroffen
        # haben: Dann ist der Baustein die Antwort (Personalaufwendungen,
        # Zinsen, Transfer) und gehört in den Kontext, auch wenn `council_budget`
        # schon einen Teilhaushalt liefert.
        # Gemessen am ROHEN Fragewortlaut, wenn er mitkommt: Die expandierten
        # Begriffe sind zum Finden gut und zum Entscheiden zu weit.
        treffer = bool(passend) and (frage is None or any(
            self._trifft(r["label"], frage) for r in passend))
        # Zu jedem getroffenen Posten das jüngste Ist derselben Nummer aus der
        # Ergebnisrechnung: „Personalaufwendungen: Ansatz 2026 209,4 Mio. €,
        # zuletzt abgerechnet 2024: 184,8 Mio. €". Die Facette `ist` feuert bei
        # „Was kostet das Personal?" nicht (kein Ist-Wort), und ohne diese
        # Spalte bliebe die Antwort beim Plan — die Live-Messung vom 02.09.
        # zeigte genau das.
        if treffer:
            for r in passend:
                try:
                    z = self._conn.execute(
                        "SELECT year, result FROM council_income_statement "
                        "WHERE sub_budget_no IS NULL AND nr = ? AND result IS NOT NULL "
                        "ORDER BY year DESC LIMIT 1", (r["nr"],)).fetchone()
                except sqlite3.OperationalError:
                    z = None
                if z:
                    r["actual_year"], r["actual"] = z["year"], z["result"]
        if not passend:
            # Ohne Treffer die Summenzeilen — sie beantworten „was nimmt die
            # Stadt ein, was gibt sie aus" und sind nie daneben.
            passend = [r for r in rows if r["is_total"]][:limit]
        if not passend:
            return None
        return {"year": year, "posten": passend, "treffer": treffer,
                "beleg": self._beleg(passend[0].get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    # ---- Vier Schichten, die die KI-Frage nicht kannte (Tim, 17.08.) -------
    #
    # Der Bestand ist seit der Runde oben um vier Schichten gewachsen, und die
    # KI-Frage beantwortete deren Fragen mit den Quellen, die sie schon kannte
    # — also falsch:
    #
    #   „Wie viel Schulden hat Oldenburg?"      → Ergebnishaushalt. Schulden
    #        sind ein BESTAND am Stichtag, kein Jahresverlauf; in der
    #        Ergebnisrechnung stehen sie überhaupt nicht.
    #   „Was wird gebaut?"                      → Ergebnishaushalt, in dem
    #        keine einzige Investition steht (ein Schulneubau taucht dort nur
    #        als Abschreibung auf, verteilt über Jahrzehnte).
    #   „Wie viele Stellen sind unbesetzt?"     → Personalaufwendungen in Euro.
    #   „Wer wollte den Haushalt ändern?"       → gar nichts, obwohl 664
    #        Änderungslisten im Bestand liegen.
    #
    # Es gelten dieselben zwei Regeln wie für den Abschnitt darüber: wenige
    # Zeilen statt Bestand, und jede Zahl mit ihrem Beleg.


    def haushalts_anschluss(self, decision_id: int, template_number: str | None) -> dict | None:
        """Wo dieser Beschluss im Haushalts-Bereich wieder auftaucht.

        Die Beschluss-Seite verweist seit H-21 auf den Haushalt — aber
        pauschal („wie sich das im Gesamthaushalt ausnimmt"). Das ist für
        jeden Beschluss derselbe Satz und deshalb für keinen eine Auskunft.

        Hier steht nur, was **belegt** ist. Zwei Fälle gibt es im Bestand, und
        beide hängen an einer echten Verknüpfung, nicht an einer Textsuche:

        * **Nachbewilligung** — ``council_supplementary_approvals.decision_id``
          zeigt auf genau diese Zeile. Der Betrag steht dann in der
          Jahressumme, die ``/haushalt/plan-ist`` zeigt.
        * **Bürgschaft** — die Vorlage steht im Zeitstrahl auf
          ``/haushalt/schulden``.

        Trifft keiner der beiden zu, kommt ``None`` — und die Seite lässt die
        Karte weg, statt einen Satz zu zeigen, der überall gleich stünde.
        """
        try:
            r = self._conn.execute(
                "SELECT template_number, title, amount, year FROM council_supplementary_approvals "
                "WHERE decision_id = ? LIMIT 1", (decision_id,)).fetchone()
        except sqlite3.OperationalError:
            r = None
        if r:
            return {"art": "nachbewilligung", "href": "/haushalt/plan-ist",
                    "year": r["year"], "amount": r["amount"],
                    "title": r["title"], "template_number": r["template_number"]}

        if template_number:
            try:
                b = self._conn.execute(
                    "SELECT title FROM council_templates "
                    "WHERE template_number = ? AND title LIKE '%bürgschaft%'",
                    (template_number,)).fetchone()
            except sqlite3.OperationalError:
                b = None
            if b:
                return {"art": "buergschaft", "href": "/haushalt/schulden",
                        "title": b["title"], "template_number": template_number}
        return None



    def bilanz_kontext(self, year: int | None = None) -> dict | None:
        """Was der Stadt gehört und wem es zusteht — der jüngste Stichtag.

        Die Bilanz ist die einzige Quelle des Bereichs, die einen **Stichtag**
        zählt und kein Jahr. Ihre Beträge mit Erträgen oder Aufwendungen zu
        verrechnen wäre der Fehler, gegen den diese Methode gebaut ist: „Die
        Stadt hat 1,48 Mrd. €" und „die Stadt gibt 799 Mio. € aus" sind zwei
        Sätze über zwei verschiedene Dinge.
        """
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_balance_sheet", "year", gefragt)
        if year is None:
            return None
        posten = {r["role"]: r["value"] for r in self._conn.execute(
            "SELECT role, value FROM council_balance_sheet WHERE year = ? AND role IS NOT NULL",
            (year,))}
        aktiva = ("intangible_assets", "tangible_assets", "financial_assets",
                  "cash_and_equivalents", "prepaid_expenses")
        summe = sum(posten[r] for r in aktiva if r in posten) or None
        beleg = self._conn.execute(
            "SELECT herkunft_id FROM council_balance_sheet WHERE year = ? LIMIT 1",
            (year,)).fetchone()
        return {
            "year": year,
            "bilanzsumme": summe,
            "posten": [(r, posten[r]) for r in
                       ("tangible_assets", "infrastructure_assets", "financial_assets",
                        "cash_and_equivalents", "net_position", "special_items",
                        "provisions", "pension_provisions", "liabilities")
                       if r in posten],
            "beleg": self._beleg(beleg["herkunft_id"] if beleg else None),
            **({"year_asked": gefragt} if abweicht else {}),
        }

    def kassensicht_kontext(self, year: int | None = None) -> dict | None:
        """Was tatsächlich geflossen ist — die Finanzrechnung (Abschnitt 4.1).

        Die zweite Rechnung desselben Jahresabschlusses, und sie kann der
        ersten scheinbar widersprechen: Für 2024 weist die Ergebnisrechnung
        einen Überschuss aus und die Finanzrechnung einen Fehlbetrag an
        Finanzmitteln. Beides stimmt — die eine bucht, wenn ein Anspruch
        entsteht, die andere, wenn Geld fließt. Ohne die zweite Zahl entsteht
        ein falscher Eindruck, und zwar in beide Richtungen.
        """
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_cash_flow_statement", "year", gefragt)
        if year is None:
            return None
        zeilen = [dict(r) for r in self._conn.execute(
            "SELECT nr, label, result, role, herkunft_id "
            "FROM council_cash_flow_statement WHERE year = ? ORDER BY nr", (year,))]
        if not zeilen:
            return None
        # Nur die Summenzeilen: Die Einzelposten sind die Ertragsarten und
        # stehen schon im Ergebnisrechnungs-Block.
        summen = [z for z in zeilen if z.get("role")]
        return {"year": year,
                "zeilen": [(z["label"], z["result"], z["role"]) for z in summen],
                "beleg": self._beleg(zeilen[0].get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def nachbewilligungen_kontext(self, year: int | None = None) -> dict | None:
        """Was beschlossen wurde, NACHDEM der Haushalt beschlossen war (§ 117).

        Die Zahl, die der Haushaltsplan nicht kennt und der Jahresabschluss
        nur als Summe zeigt. Sie ist außerdem die einzige Stelle, an der
        sichtbar wird, wie viel der Rat selbst entschieden hat: 2022 waren es
        89 % der Nachbewilligungen, 2024 nur noch 73 %.
        """
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_supplementary_years ORDER BY year")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        row = next((r for r in rows if r["year"] == year), rows[-1])
        abweicht = year is not None and row["year"] != year
        channels = []
        try:
            channels = [(r["channel"], r["amount_operating"], r["amount_capital"])
                       for r in self._conn.execute(
                           "SELECT channel, amount_operating, amount_capital "
                           "FROM council_supplementary_channels WHERE year = ?",
                           (row["year"],))]
        except sqlite3.OperationalError:
            pass
        return {"year": row["year"],
                "konsumtiv": row.get("total_operating"),
                "investiv": row.get("total_capital"),
                "gesamt": (row.get("total_operating") or 0)
                          + (row.get("total_capital") or 0),
                "commitments": row.get("commitments_amount"),
                "channels": channels,
                "probe_text": row.get("probe_text") if not row.get("probe_ok") else None,
                "beleg": self._beleg(row.get("herkunft_id")),
                **({"year_asked": year} if abweicht else {})}

    def kennzahlen_kontext(self, limit: int = 13, year: int | None = None) -> dict | None:
        """Die dreizehn Kennzahlen — jeweils der jüngste Stand, mit Rechenweg.

        Die einzige Quelle des Bereichs, die ihre eigenen Formeln mitliefert.
        Deshalb darf die Antwort eine Quote nennen, ohne sie zu erfinden — und
        deshalb steht der Rechenweg im Kontext, nicht nur der Wert.

        ``korrekturen`` sind die Stellen, an denen ein späterer Bericht eine
        Zahl still geändert hat. Wer nach der Steuerquote 2021 fragt, soll
        nicht die erste gedruckte Fassung bekommen, ohne dass jemand sagt,
        dass es eine zweite gab.
        """
        from council import indicators as _kz

        staende = self.get_kennzahlen()
        if not staende:
            return None
        series = _kz.neueste(staende)
        _, funde = _kz.ueberlappungsprobe(staende)
        formeln = {}
        for f in self.get_kennzahl_formeln():
            formeln[f["indicator"]] = f["formula"]
        jahre = {z["year"] for z in series}
        juengstes = year if year in jahre else max(jahre)
        abweicht = year is not None and juengstes != year
        aktuell = [z for z in series if z["year"] == juengstes][:limit]
        label = {k.key: k.label for k in _kz.KENNZAHLEN}
        unit = {k.key: k.unit for k in _kz.KENNZAHLEN}
        return {
            "year": juengstes,
            "werte": [(label.get(z["indicator"], z["indicator"]), z["value"],
                       unit.get(z["indicator"], "eur"), z["decimals"],
                       formeln.get(z["indicator"]))
                      for z in aktuell],
            # Mit Einheit, damit der Prompt-Baustein „45,90 %" schreiben kann
            # und nicht „45.9" — im deutschen Fließtext ist das ein Zahlwort
            # mit falschem Trennzeichen und ohne Einheit.
            "korrekturen": [(label.get(f["indicator"], f["indicator"]), f["year"],
                             f["alt"], f["alt_bericht"], f["neu"], f["neu_bericht"],
                             unit.get(f["indicator"], "eur"))
                            for f in funde if f["art"] == "revision"],
            "beleg": self._beleg(aktuell[0].get("herkunft_id") if aktuell else None),
            **({"year_asked": year} if abweicht else {}),
        }


    def investitionen_fuer_begriffe(self, begriffe: list[str],
                                    limit: int = 3, year: int | None = None) -> dict | None:
        """Was die Stadt bauen und kaufen will — Summenzeile und die
        Teilhaushalte, die zur Frage passen.

        Die andere Hälfte des Haushaltsplans. Sie mit dem Ergebnishaushalt in
        einem Satz zu verrechnen wäre der Fehler, gegen den diese Methode
        gebaut ist: Es sind zwei Haushalte mit zwei Zahlenwerken.

        Geliefert wird die **Summenzeile der Datei** (``level``
        ``investitionen``) — das Ziel der Rechenprobe, nicht unsere Addition.
        Der *Gesamtbetrag des Finanzhaushaltes* (``level``
        ``finanzhaushalt``) bleibt bewusst draußen: Er zählt die laufende
        Verwaltungstätigkeit mit, ist von keiner Probe der Datei gedeckt und
        stünde im Prompt direkt neben einer geprüften Zahl.
        """
        gefragt = year
        year, abweicht = _geld.jahrgang(self._conn, "council_investments", "year", gefragt,
                                        "level = 'investments'")
        if not year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT level, sub_budget_no, label, inflows, outflows, herkunft_id "
            "FROM council_investments WHERE year = ? AND level IN "
            "('investments', 'sub_budget') ORDER BY sub_budget_no", (year,))]
        gesamt = next((r for r in rows if r["level"] == "investments"), None)
        if not gesamt:
            return None
        teile = [r for r in rows if r["level"] == "sub_budget"]
        bewertet = [(self._trifft(r["label"], begriffe), r) for r in teile]
        passend = [r for n, r in sorted(bewertet, key=lambda x: -x[0]) if n][:limit]
        if not passend:
            # Ohne Begriffs-Treffer die größten Brocken: „Was wird gebaut?"
            # meint die, über die zu reden sich lohnt.
            passend = sorted(teile, key=lambda r: -(r["outflows"] or 0))[:limit]
        return {"year": year, "gesamt": gesamt, "teilhaushalte": passend,
                "beleg": self._beleg(gesamt.get("herkunft_id")),
                **({"year_asked": gefragt} if abweicht else {})}

    def stellenplan_kontext(self, budget_year: int | None = None) -> dict | None:
        """Die Gesamtzeilen des Stellenplans — Stellen, filled, nicht besetzt.

        Die einzige Schicht des Haushalts, die nicht in Euro rechnet. Auf
        „Wie viele Stellen sind unbesetzt?" antwortet keine Euro-Zahl.

        DREI DINGE, DIE MITREISEN MÜSSEN, weil die Zahlen sonst falsch gelesen
        werden:

        1. Die Besetzungszahlen gehören zur **Vorjahresspalte**, nicht zum
           Haushaltsjahr — geplant wird vorwärts, gezählt werden kann nur
           rückwärts (``as_of_date`` sagt, auf welchen Tag). ``positions_planned``
           minus ``besetzt`` mischt zwei Stichtage und steht in keinem
           Dokument; ``vacant`` steht dort, und zwar als eigene Spalte.
        2. Teil A und Teil B sind zwei Tabellen mit zwei Rechenproben, und sie
           kommen einzeln herein. ``fehlend`` sagt, welcher Teil eines
           Jahrgangs **nicht** vorliegt — ohne das sähe ein halber Jahrgang
           wie ein ganzer aus.
        3. Es gibt im Plan keine Zeile „Stellen insgesamt". Diese Methode
           bildet auch keine: Was hier steht, steht so im Dokument.
        """
        gefragt = budget_year
        budget_year, abweicht = _geld.jahrgang(self._conn, "council_staff_plan", "budget_year",
                                               gefragt, "kind = 'total'")
        if not budget_year:
            return None
        rows = [dict(r) for r in self._conn.execute(
            "SELECT part, label, positions_planned, positions_prior_year, filled, "
            " vacant, as_of_date, herkunft_id FROM council_staff_plan "
            "WHERE budget_year = ? AND kind = 'total' ORDER BY part", (budget_year,))]
        if not rows:
            return None
        from council import stellenplan as _stellenplan

        for r in rows:
            r["teil_name"] = _stellenplan.TEIL_NAMEN.get(r["part"], r["part"])
        fehlend = [t for t in sorted(_stellenplan.TEIL_NAMEN)
                   if t not in {r["part"] for r in rows}]
        return {
            "budget_year": budget_year,
            "as_of_date": next((r["as_of_date"] for r in rows if r.get("as_of_date")), None),
            "teile": rows,
            "fehlend": [_stellenplan.TEIL_NAMEN[t] for t in fehlend],
            "beleg": self._beleg(rows[0].get("herkunft_id")),
            **({"year_asked": gefragt} if abweicht else {}),
        }

    def haushaltsantraege_kontext(self, year: int | None = None,
                                  limit: int = 8) -> dict | None:
        """Wer wollte am Haushalt etwas ändern — und kam damit durch?

        Die leichte Schwester von ``haushalt_streit``: dieselben Anker, aber
        ohne Debatte und ohne Protokoll-Volltext. Die Wortbeiträge kommen im
        Antwort-Prompt ohnehin über ``_debatten_block``; das Zerlegen jedes
        Protokolls kostete in einem Web-Request mehr, als es dort einbrächte.

        Gezählt statt aufgezählt: Ein Jahrgang bringt es auf mehrere Dutzend
        Änderungslisten, und „CDU: 9 Listen, 2 angenommen, 7 abgelehnt" sagt
        dasselbe wie neun Titelzeilen, die alle „Änderungsliste der
        CDU-Fraktion zum Ergebnishaushalt" heißen.

        ``year`` ist das **Haushaltsjahr**, nicht das Sitzungsjahr: Der
        Haushalt 2026 wurde im Februar 2026 beschlossen, der Haushalt 2023 im
        Dezember 2022. Ohne Angabe kommt der jüngste Jahrgang.

        WAS DIESE QUELLE NICHT WEISS, und was der Baustein dazu deshalb
        ausdrücklich sagt: den **Inhalt** einer Änderungsliste. Welche Position
        um welchen Betrag — das liegt in den Anlagen-PDFs der Vorlage, die
        nicht als Volltext im Bestand sind.
        """
        from council import haushaltsdebatte as hd

        try:
            rows = self._conn.execute(
                "SELECT d.ksinr, d.item_number, d.title, d.outcome, d.vote, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.kind = 'decision' AND (d.title LIKE 'Haushaltssatzung und Haushaltsplan%' "
                "   OR d.title LIKE 'Haushalt 2%')").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        anker: dict[int, dict[int, dict]] = {}
        for r in rows:
            title = (r["title"] or "").strip()
            satzung = self._STREIT_SATZUNG.match(title)
            sammel = self._STREIT_SAMMEL.match(title)
            if not satzung and not sammel:
                continue
            j = int((satzung or sammel).group(1))
            st = anker.setdefault(j, {}).setdefault(r["ksinr"], {
                "ksinr": r["ksinr"], "committee": r["committee"],
                "date": r["session_date"], "top": None, "official_text": None})
            if sammel:
                # Der Sammelpunkt selbst ist die verlässlichste Angabe.
                st["top"] = (r["item_number"] or "").strip() or st["top"]
            else:
                if not st["top"]:
                    st["top"] = self._streit_oberpunkt(r["item_number"])
                st["official_text"] = {"outcome": r["outcome"], "vote": r["vote"]}
        if not anker:
            return None
        gewaehlt = year if year in anker else max(anker)
        abweicht = year is not None and gewaehlt != year

        stationen = []
        for st in sorted(anker[gewaehlt].values(),
                         key=lambda s: (s["date"], s["committee"] == "Rat", s["ksinr"])):
            if not st["top"]:
                continue
            praefix = st["top"] + "."
            entity: dict[str, dict] = {}
            verwaltung = gesamt = 0
            for r in self._conn.execute(
                    "SELECT ksinr, item_number, title, outcome, vote FROM council_decisions "
                    "WHERE ksinr = ? AND kind = 'subvote' ORDER BY position",
                    (st["ksinr"],)).fetchall():
                nr = (r["item_number"] or "").strip()
                if nr != st["top"] and not nr.startswith(praefix):
                    continue
                antrag = hd.antrag_aus_zeile(dict(r))
                if not antrag:
                    continue
                gesamt += 1
                if antrag.ist_verwaltung:
                    verwaltung += 1
                    continue
                # Gemeinsame Listen zählen für ALLE Beteiligten — „SPD/Grüne"
                # ist keine Fraktion, sondern zwei, die sich zusammengetan
                # haben. Sie unter einem Kunstnamen zu führen ließe die Frage
                # „Wie viele Anträge stellte die SPD?" ins Leere laufen.
                for name in (antrag.author or "").split(" / "):
                    if not name:
                        continue
                    e = entity.setdefault(name, {"name": name, "count": 0,
                                                  "accepted": 0, "rejected": 0})
                    e["count"] += 1
                    if antrag.outcome == "accepted":
                        e["accepted"] += 1
                    elif antrag.outcome == "rejected":
                        e["rejected"] += 1
            if not gesamt:
                continue
            stationen.append({
                "committee": st["committee"], "date": st["date"],
                "author": sorted(entity.values(), key=lambda u: (-u["count"], u["name"]))[:limit],
                "verwaltung": verwaltung, "gesamt": gesamt,
                "official_text": st["official_text"],
            })
        if not stationen:
            return None
        # Die LETZTEN beiden Stationen, nicht die ersten: In Oldenburg sind das
        # der Ausschuss für Finanzen und Beteiligungen und der Rat, und der Rat
        # tagt zuletzt. Käme je eine dritte Station dazu, fiele damit die
        # früheste heraus — nie die entscheidende.
        return {"year": gewaehlt, "years": sorted(anker),
                "stationen": stationen[-2:],
                **({"year_asked": year} if abweicht else {})}

    # ---- Teilvoten aus raw_result (welche Fraktion stimmte wie) ----

    def save_decision_votes(self, decision_id: int, votes: list[tuple[str, str]]) -> None:
        """Geparste (faction, stance)-Zeilen eines Beschlusses ersetzen."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_votes WHERE decision_id = ?", (decision_id,))
            self._conn.executemany(
                "INSERT OR IGNORE INTO council_decision_votes (decision_id, faction, stance) "
                "VALUES (?, ?, ?)",
                [(decision_id, f, s) for f, s in votes],
            )

    def decision_votes_for(self, decision_ids: list[int]) -> dict[int, list[dict]]:
        """decision_id → [{faction, stance}] für Anzeige/Auswertung."""
        if not decision_ids:
            return {}
        ph = ",".join("?" * len(decision_ids))
        rows = self._conn.execute(
            f"SELECT decision_id, faction, stance FROM council_decision_votes "
            f"WHERE decision_id IN ({ph}) ORDER BY faction", decision_ids,
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append(
                {"faction": r["faction"], "stance": r["stance"]})
        return out

    def decisions_with_raw_result(self) -> list[dict]:
        """Alle Beschlüsse mit Abstimmungssatz — Eingabe für den Teilvoten-Backfill."""
        return [dict(r) for r in self._conn.execute(
            "SELECT id, raw_result FROM council_decisions "
            "WHERE raw_result IS NOT NULL AND raw_result != ''"
        ).fetchall()]

    # ---- Pressemitteilungen der Stadt (council/presse.py) ----









    # ---- field recaps (auto-generated LLM summaries per policy field) ----




    def get_similar(self, decision_id: int, limit: int = 5) -> list[dict]:
        """The most similar decisions to ``decision_id`` (precomputed), best first.
        Near-duplicate twins (the same matter in another committee, or a recurring
        series) are collapsed via the normalised title, so the neighbours shown are
        genuinely distinct rather than the Ausschuss/Rat copy of this very decision."""
        base = self._conn.execute(
            "SELECT title, template_number FROM council_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.summary, d.policy_field, d.outcome,
                      cs.session_date, cs.committee, sl.score
               FROM council_similar sl
               JOIN council_decisions d ON d.id = sl.neighbor_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE sl.decision_id = ? ORDER BY sl.rank LIMIT ?""",
            (decision_id, limit * 5),
        ).fetchall()
        seen = set(_dedup_keys(base["title"], base["template_number"], decision_id)) if base else set()
        out: list[dict] = []
        for r in rows:
            keys = _dedup_keys(r["title"], r["template_number"], r["id"])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            out.append(dict(r))
            if len(out) >= limit:
                break
        return out

    def orte_fuer_decisions(self, ids: list[int]) -> dict[int, dict]:
        """Bestbelegter Ort je Beschluss für die Mini-Karte.

        Die explizite Orts-Pipeline gewinnt; alte Themen-Entitäten bleiben als
        Fallback, solange der historische Backfill noch nicht vollständig ist.
        """
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        direct = self._conn.execute(
            f"""SELECT dl.decision_id, l.name, l.lat, l.lon
                FROM council_decision_locations dl
                JOIN council_locations l ON l.slug = dl.location_slug
                WHERE dl.decision_id IN ({ph}) AND l.lat IS NOT NULL
                  AND l.district IS NOT NULL AND l.district != ''
                ORDER BY dl.confidence DESC, l.name""", ids).fetchall()
        out: dict[int, dict] = {}
        for r in direct:
            out.setdefault(r["decision_id"], {"ort_name": r["name"],
                                              "lat": r["lat"], "lon": r["lon"]})
        rows = self._conn.execute(
            f"""SELECT l.decision_id, e.name, m.lat, m.lon
                FROM council_entity_links l
                JOIN council_entities e ON e.id = l.entity_id
                JOIN council_entity_meta m ON m.slug = e.slug
                WHERE l.decision_id IN ({ph}) AND m.lat IS NOT NULL
                  AND e.kind = 'place'
                ORDER BY e.n DESC""",
            ids,
        ).fetchall()
        from council import geo

        for r in rows:
            # Alte Entitäts-Geocodes entstanden vor der expliziten
            # Orts-Pipeline und können Vergleichsorte außerhalb Oldenburgs
            # enthalten. Nur Koordinaten innerhalb eines Ratslotse-
            # Ortsbereichspolygons dürfen als Karten-Pin erscheinen.
            if not geo.ortsbereich_for(r["lat"], r["lon"]):
                continue
            out.setdefault(r["decision_id"], {"ort_name": r["name"],
                                              "lat": r["lat"], "lon": r["lon"]})
        return out

    # ---- Wortbeiträge aus Protokollen (Task 16) ----------------------------











    def replace_protocol_text(self, ksinr: int, raw_text: str, n_pages: int,
                              page_offsets: list[int]) -> None:
        """Backfill: Volltext + Seiten-Offsets gemeinsam ersetzen — die
        Offsets gelten exakt für DIESEN Text, getrennt gespeichert wären
        sie wertlos."""
        with self._conn:
            self._conn.execute(
                "UPDATE council_protocols SET raw_text = ?, n_pages = ?, page_offsets = ? "
                "WHERE ksinr = ?",
                (raw_text, n_pages, json.dumps(page_offsets), ksinr))

    def protokoll_urls_fuer(self, ksinrs: list[int | None]) -> dict[int, str]:
        """ksinr → getfile-URL des öffentlichen Protokoll-PDFs. Macht die
        Wortbeitrags-Belege der KI-Frage nachlesbar: Jeder Beitrag stammt aus
        genau einem Protokoll, und dessen URL steht längst in der DB."""
        ids = sorted({int(k) for k in ksinrs if k})
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT ksinr, document_url FROM council_protocols "
            f"WHERE ksinr IN ({ph}) AND document_url IS NOT NULL", ids).fetchall()
        return {r["ksinr"]: r["document_url"] for r in rows}

    # Sammel-TOPs: Hier landet alles, was sonst nirgends hingehört. Ein Treffer
    # darauf koppelt keine Debatte ZUR SACHE, sondern eine Wundertüte.
    _SAMMEL_TOPS = ("anfragen und anregungen", "einwohnerfragestunde",
                    "genehmigung der tagesordnung", "mitteilungen",
                    "verschiedenes", "niederschrift")







    def partei_meinungen_cache_get(self, key: str, max_age_days: int = 14):
        row = self._conn.execute(
            "SELECT result FROM council_partei_meinungen_cache "
            "WHERE key = ? AND created_at >= datetime('now', ?)",
            (key, f"-{int(max_age_days)} days")).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (ValueError, TypeError):
            return None

    def partei_meinungen_cache_set(self, key: str, question: str, result) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_partei_meinungen_cache "
                "(key, question, result, created_at) VALUES (?, ?, ?, datetime('now'))",
                (key, question[:300], json.dumps(result, ensure_ascii=False)))
            # Alt-Einträge räumen sich beim Schreiben mit weg (klein halten).
            self._conn.execute(
                "DELETE FROM council_partei_meinungen_cache "
                "WHERE created_at < datetime('now', '-30 days')")


    def save_qa_feedback(self, question: str, answer_excerpt: str | None,
                         rating: str, reason: str | None,
                         user_id: int | None = None) -> None:
        """Daumen hoch/runter zu einer KI-Antwort (5a/I-03).

        Ein Konto hat je Frage **eine** Stimme: Der nachgereichte Grund und die
        korrigierte Bewertung (Daumen runter → hoch) überschreiben die frühere
        Zeile, statt sich als widersprüchliches Paar in der Tabelle zu stapeln —
        sonst zählte jede Meinungsänderung doppelt. Anonyme Rückmeldungen haben
        keinen Schlüssel und werden weiterhin angehängt.
        """
        if rating not in ("up", "down"):
            raise ValueError(f"rating muss up/down sein, nicht {rating!r}")
        now = datetime.utcnow().isoformat(timespec="seconds")
        werte = (question[:300], (answer_excerpt or "")[:500] or None, rating,
                 (reason or "").strip()[:500] or None, user_id, now)
        with self._conn:
            if user_id is not None:
                vorher = self._conn.execute(
                    "SELECT id FROM council_qa_feedback WHERE user_id = ? AND question = ? "
                    "ORDER BY id DESC LIMIT 1", (user_id, werte[0])).fetchone()
                if vorher:
                    self._conn.execute(
                        "UPDATE council_qa_feedback SET answer_excerpt = ?, rating = ?, "
                        "reason = ?, created = ? WHERE id = ?",
                        (werte[1], rating, werte[3], now, vorher[0]))
                    return
            self._conn.execute(
                "INSERT INTO council_qa_feedback (question, answer_excerpt, rating, reason, user_id, created) "
                "VALUES (?, ?, ?, ?, ?, ?)", werte,
            )


    def get_decisions_by_ids(self, ids: list[int]) -> list[dict]:
        """Fetch decisions by id, preserving the given order (for Q&A citations).

        Liefert auch Abstimmung (vote/no_votes/abstentions/raw_result) und
        amount_eur mit: raw_result geht bei strittigen Beschlüssen in den
        QA-Kontext (dort stehen oft die Fraktionen der Gegenstimmen), und die
        Fallback-Folgefragen in council/qa.py prüfen no_votes/amount_eur —
        ohne diese Felder liefen die Zweige ins Leere."""
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT d.id, d.title, d.summary, d.official_text, d.template_number,
                       d.kvonr,
                       -- ksinr + item_number: Adresse der Station in der
                       -- Sitzung — darüber koppelt wortbeitraege_zu_beschluessen
                       -- die Aussprache an den Beschluss.
                       d.ksinr, d.item_number,
                       d.policy_field, d.outcome, d.impact, d.impact_reason,
                       d.vote, d.no_votes, d.abstentions, d.raw_result,
                       d.amount_eur, d.factions, d.deviation,
                       v.office, v.climate_impact,
                       cs.session_date, cs.committee
                FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
                LEFT JOIN council_templates v ON v.kvonr = d.kvonr
                WHERE d.id IN ({ph})""",
            ids,
        ).fetchall()
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def antrag_decision_ids(self, party: str, terms: str = "", limit: int = 12) -> list[int]:
        """Beschluss-ids, bei denen die Fraktion/Gruppe ``party`` als Antragsteller
        auftritt — aus dem factions-Feld des Protokolls ODER über eine als Antrag
        erkannte Anlage der Vorlage. Mit ``terms`` wird thematisch eingegrenzt
        (Schnitt mit der FTS-Trefferliste), sonst kommen die neuesten zuerst.
        Für das Fragetyp-Routing der KI-Frage (typ=partei)."""
        like = f'%{party.strip()}%'
        rows = self._conn.execute(
            """SELECT DISTINCT d.id FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               LEFT JOIN council_templates v ON v.template_number = d.template_number
               LEFT JOIN council_attachments a ON a.kvonr = v.kvonr AND a.is_motion = 1
               WHERE d.kind = 'decision'
                 AND (d.factions LIKE ? OR a.applicants LIKE ?)
               ORDER BY cs.session_date DESC, d.id DESC LIMIT 400""",
            (like, like),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if terms:
            fts = {i for i, *_ in self.search_decisions_fts(terms, limit=250)}
            thematisch = [i for i in ids if i in fts]
            # Thematischer Schnitt zuerst; ohne Schnitt-Treffer die neuesten Anträge
            # der Fraktion — besser als gar kein Partei-Signal im Kandidaten-Pool.
            ids = thematisch or ids
        return ids[:limit]

    def find_decision_ids(self, *, template_number: str | None = None, committee: str | None = None,
                          session_date: str | None = None, title_like: str | None = None) -> list[int]:
        """Beschluss-ids über natürliche Schlüssel statt AUTOINCREMENT-ids.

        Für DB-portable Eval-Gold-Cases (eval/cases_qa.json): Vorlagen-Nummer,
        Sitzungsdatum und Titel sind auf jeder Kopie der Datenbank gleich, die
        ids nicht. Filter sind UND-verknüpft, mindestens einer ist Pflicht;
        Teilabstimmungen bleiben außen vor (nicht eigenständig zitierbar)."""
        conds, params = ["d.kind = 'decision'"], []
        if template_number:
            conds.append("d.template_number = ?"); params.append(str(template_number).strip())
        if committee:
            conds.append("cs.committee LIKE ?"); params.append(f"%{committee.strip()}%")
        if session_date:
            conds.append("cs.session_date = ?"); params.append(str(session_date).strip())
        if title_like:
            conds.append("d.title LIKE ?"); params.append(f"%{title_like.strip()}%")
        if len(conds) == 1:
            raise ValueError("find_decision_ids braucht mindestens einen Filter")
        rows = self._conn.execute(
            f"""SELECT d.id FROM council_decisions d
                JOIN council_sessions cs ON cs.ksinr = d.ksinr
                WHERE {' AND '.join(conds)}
                ORDER BY cs.session_date DESC, d.id DESC""",
            params,
        ).fetchall()
        return [r["id"] for r in rows]

    def get_protocols_raw(self) -> list[dict]:
        """All stored protocols with their raw text — for re-extraction without
        re-downloading the PDFs."""
        rows = self._conn.execute(
            "SELECT ksinr, document_id, document_url, raw_text, n_pages "
            "FROM council_protocols WHERE raw_text IS NOT NULL AND raw_text != ''"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- Der Weg eines Haushalts durch den Rat (A6, 08/2026) ---------------
    #
    # Gebaut aus dem, was das Ratsinformationssystem ohnehin führt: der
    # Beratungsfolge (`council_deliberations`), den Tagesordnungen
    # (`council_agenda_items`) und den Protokoll-Beschlüssen
    # (`council_decisions`). Kein eigener Datenbestand, kein Cron.
    #
    # `council_attachments.fetched_at` ist hier KEINE Quelle: Bei allen
    # Finanzdokumenten steht dort der 10.08.2026 — der Tag unseres
    # Volltext-Backfills, nicht der Tag der Veröffentlichung. Das Datum einer
    # Station kommt ausschließlich aus `council_sessions.session_date`.

    #: Ein Haushaltsjahr trägt drei Sorten Vorlagen, und sie heißen nicht
    #: einheitlich. Die Jahreszahl steht immer vorn, das Wort davor variiert
    #: („Haushalt 2026", „Haushaltsentwurf 2024", „HH 2020").
    _HH_TITEL = re.compile(r"^(?:Haushaltsentwurf|Haushalt|HH)\s*(\d{4})")

    #: Woran ein Verwaltungsentwurf als Teilhaushalts-Bericht erkennbar ist —
    #: er geht in den jeweiligen Fachausschuss, nicht in den Finanzausschuss.
    _HH_TEILBERICHT = ("Teilhaushalt", "THH", "Budget", "Stiftung")





    # ---- Der Streit ums Geld (08/2026) ------------------------------------
    #
    # Die Zahlen des Haushalts stehen in den Finanzdokumenten; dass über sie
    # gestritten wurde, steht nur im Protokoll. Diese Methode setzt beides
    # zusammen, was die Ratsdaten dazu hergeben: welche Änderungslisten zur
    # Abstimmung standen (`council_decisions` mit `kind='subvote'`), was in
    # der Debatte gesagt wurde (`council_protocols.raw_text`, zerlegt in
    # `council.haushaltsdebatte`) und wie am Ende abgestimmt wurde.
    #
    # Kein eigener Datenbestand und kein Cron: Alles wird beim Lesen aus dem
    # gerechnet, was der Protokoll-Import ohnehin schreibt. Damit kann die
    # Seite nicht veralten, und ein nachgetragenes Protokoll erscheint ohne
    # Backfill.

    #: Die Schlussabstimmung trägt in jedem Jahrgang denselben Titel; die
    #: Jahreszahl darin ist das HAUSHALTSJAHR, nicht das Sitzungsjahr (der
    #: Haushalt 2023 wurde im Dezember 2022 beschlossen, der Haushalt 2026
    #: erst im Februar 2026).
    _STREIT_SATZUNG = re.compile(r"^Haushaltssatzung und Haushaltsplan\s+(\d{4})")
    #: Der Sammelpunkt, unter dem die Debatte geführt wird. Er steht nicht in
    #: jedem Protokoll als eigene Beschlusszeile — wo er fehlt, wird der
    #: Oberpunkt aus der Nummer der Schlussabstimmung abgeleitet.
    _STREIT_SAMMEL = re.compile(r"^Haushalt\s+(\d{4})\s*$")



