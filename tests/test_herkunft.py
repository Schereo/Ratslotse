"""Das Herkunfts-Fundament: woher eine gespeicherte Finanzzahl stammt.

Drei Fragen stehen hier auf dem Prüfstand, und die dritte ist die wichtigste:

1. Rüstet sich eine Datenbank im alten Format sauber nach?
2. Hält eine frisch geschriebene Zeile fest, **wo** sie steht und **womit**
   sie abgesichert ist?
3. Bleibt dabei jeder bestehende Wert unverändert?

Frage 3 wird zeilenweise beantwortet, nicht über Zeilenzahlen: Eine Migration,
die 1.566 Zeilen behält und in dreien den Betrag verschiebt, zählt richtig und
ist trotzdem der schlimmste denkbare Ausgang.
"""
from __future__ import annotations

import sqlite3

import pytest

from council import herkunft
from council.herkunft import Herkunft
from council.store import CouncilStore

# --- Eine Datenbank, wie sie vor der Umstellung aussah ------------------------
#
# Wörtlich der Stand von vor 08/2026: drei Schreibweisen für dieselbe Sache
# (`source_label`/`source_url`, `label`/`url`, `source_url`), keine
# `herkunft_id`, keine `council_herkunft`.

ALTES_SCHEMA = """
CREATE TABLE council_anlagen (
  document_id INTEGER PRIMARY KEY, kvonr INTEGER NOT NULL, label TEXT,
  url TEXT, is_motion INTEGER NOT NULL DEFAULT 0, applicants TEXT,
  raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'listed');
CREATE TABLE council_ergebnisrechnung (
  year INTEGER NOT NULL, sub_budget_no INTEGER, sub_budget_name TEXT,
  nr INTEGER NOT NULL, label TEXT NOT NULL,
  prior_year REAL, budgeted REAL, plan REAL, plan_kind TEXT,
  result REAL, deviation REAL, is_total INTEGER NOT NULL DEFAULT 0,
  source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL,
  PRIMARY KEY (year, sub_budget_no, nr));
CREATE TABLE council_abweichungsgruende (
  year INTEGER NOT NULL, nr INTEGER NOT NULL, label TEXT NOT NULL,
  delta_meur REAL, percent REAL, text TEXT NOT NULL,
  source_label TEXT, source_url TEXT, fetched_at TEXT NOT NULL,
  PRIMARY KEY (year, nr));
CREATE TABLE council_pruefbericht_quellen (
  year INTEGER PRIMARY KEY, label TEXT, url TEXT, n_pages INTEGER,
  readable INTEGER NOT NULL DEFAULT 1, fetched_at TEXT NOT NULL);
CREATE TABLE council_haushalt (
  id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL,
  area TEXT NOT NULL, revenues REAL, expenses REAL, result REAL,
  is_total INTEGER NOT NULL DEFAULT 0,
  source_url TEXT, fetched_at TEXT NOT NULL, UNIQUE(year, area));
CREATE TABLE council_steuern (
  year INTEGER NOT NULL, art TEXT NOT NULL, amount REAL,
  source_url TEXT, fetched_at TEXT NOT NULL, PRIMARY KEY (year, art));
"""

#: Ein Jahresabschluss aus dem Ratsinformationssystem — Label und URL so, wie
#: der Altbestand sie führt, plus die `document_id`, die er NICHT führte.
JA_URL = "https://buergerinfo.oldenburg.de/getfile.php?id=280861&type=do"
JA_LABEL = "Jahresabschluss 2023 der Kernverwaltung"
PLAN_URL = "https://www.oldenburg.de/fileadmin/oldenburg/haushalt-2026.pdf"
CSV_URL = "https://opendata.oldenburg.de/sites/default/files/1104_Steuern.csv"


@pytest.fixture
def alte_db(tmp_path):
    """Eine befüllte Datenbank im Format von vor der Umstellung."""
    pfad = tmp_path / "alt.sqlite"
    cn = sqlite3.connect(pfad)
    cn.executescript(ALTES_SCHEMA)
    cn.execute("INSERT INTO council_anlagen (document_id, kvonr, label, url, "
               "n_pages, fetched_at) VALUES (280861, 4711, ?, ?, 312, '2026-08-10T09:00:00')",
               (JA_LABEL, JA_URL))
    cn.executemany(
        "INSERT INTO council_ergebnisrechnung (year, sub_budget_no, sub_budget_name, nr, label, "
        " prior_year, budgeted, plan, plan_kind, result, deviation, is_total, "
        " source_label, source_url, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(2023, None, None, 12, "Summe ordentliche Erträge", 696_600_000.0,
          664_574_528.42, 664_574_528.42, "ansatz", 732_987_197.61, 68_412_669.19, 1,
          JA_LABEL, JA_URL, "2026-08-14T07:12:00"),
         (2023, None, None, 20, "Summe ordentliche Aufwendungen", 661_700_000.0,
          674_300_000.0, 674_300_000.0, "ansatz", 683_000_000.0, 8_700_000.0, 1,
          JA_LABEL, JA_URL, "2026-08-14T07:12:00"),
         (2023, 7, "Stadtplanung", 20, "Summe ordentliche Aufwendungen", None,
          21_000_000.0, 21_000_000.0, "ansatz", 20_400_000.0, -600_000.0, 1,
          JA_LABEL, JA_URL, "2026-08-14T07:12:01")])
    cn.execute(
        "INSERT INTO council_abweichungsgruende (year, nr, label, delta_meur, "
        " percent, text, source_label, source_url, fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (2023, 1, "Steuern und ähnliche Abgaben", 75.1, 24.82,
         "Die Mehrerträge entfallen nahezu auf den Bereich der Gewerbesteuer.",
         JA_LABEL, JA_URL, "2026-08-14T07:12:00"))
    cn.execute(
        "INSERT INTO council_pruefbericht_quellen (year, label, url, n_pages, readable, "
        " fetched_at) VALUES (2023, 'Schlussbericht 2023', ?, 61, 1, '2026-08-14T07:13:00')",
        (JA_URL,))
    cn.executemany(
        "INSERT INTO council_haushalt (year, area, revenues, expenses, result, "
        " is_total, source_url, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
        [(2026, "Jugend und Familie", 40e6, 210e6, -170e6, 0, PLAN_URL, "2026-08-01T06:00:00"),
         (2026, "Summe", 52e6, 271e6, -219e6, 1, PLAN_URL, "2026-08-01T06:00:00")])
    cn.execute("INSERT INTO council_steuern (year, art, amount, source_url, fetched_at) "
               "VALUES (2025, 'Gewerbesteuer (-umlage)', 214000000.0, ?, '2026-08-02T06:00:00')",
               (CSV_URL,))
    cn.commit()
    cn.close()
    return pfad


def _alles(pfad, tabelle: str, spalten: list[str]) -> list[tuple]:
    """Jede Zeile einer Tabelle, auf die genannten Spalten beschränkt."""
    cn = sqlite3.connect(pfad)
    auswahl = ", ".join(spalten)
    zeilen = cn.execute(f"SELECT {auswahl} FROM {tabelle} ORDER BY {auswahl}").fetchall()
    cn.close()
    return zeilen


def _spalten(pfad, tabelle: str) -> list[str]:
    cn = sqlite3.connect(pfad)
    aus = [r[1] for r in cn.execute(f"PRAGMA table_info({tabelle})")]
    cn.close()
    return aus


# --- 1. Nachrüsten -----------------------------------------------------------

def test_alte_datenbank_bekommt_die_spalte_und_verliert_keine(alte_db):
    """Rein additiv: `herkunft_id` kommt dazu, nichts geht weg."""
    #: Spalten, die eine Umbenennung ABLÖST — dort ist das Verschwinden der
    #: Auftrag. Die Liste steht als Literal da, damit jede andere
    #: verschwundene Spalte weiter auffliegt.
    UMBENANNT = {("council_steuern", "art")}
    vorher = {t: _spalten(alte_db, t)
              for t in herkunft.HERKUNFT_TABELLEN if _spalten(alte_db, t)}
    CouncilStore(alte_db).close()
    for tabelle, alt in vorher.items():
        neu = _spalten(alte_db, tabelle)
        erwartet = {s for s in alt if (tabelle, s) not in UMBENANNT}
        assert erwartet <= set(neu), f"{tabelle}: Spalte verschwunden"
        assert "herkunft_id" in neu, f"{tabelle}: ohne herkunft_id"


def test_kein_einziger_bestehender_wert_aendert_sich(alte_db):
    """Der Kern der Zusage. Verglichen wird **zeilenweise über alle alten
    Spalten**, nicht über Zeilenzahlen: Eine Migration, die die richtige
    Anzahl behält und in einer Zeile den Betrag verschiebt, zählt korrekt und
    ist trotzdem der schlimmste denkbare Ausgang.

    Ausgenommen sind die Spalten, für die eine WERT-Migration angemeldet ist
    (`_werte_umschreiben`): Dort ist das Umschreiben ja der Auftrag. Die
    Ausnahme steht als Liste hier, nicht als Automatik — eine Spalte, die
    sich ohne Eintrag ändert, soll weiter auffliegen."""
    #: (Tabelle, Spalte) → hier darf sich der Wert ändern.
    ERLAUBT = {("council_ergebnisrechnung", "plan_kind"),
               ("council_finanzrechnung", "plan_kind"),
               ("council_steuern", "art")}
    snapshot = {}
    for tabelle in herkunft.HERKUNFT_TABELLEN:
        spalten = [s for s in _spalten(alte_db, tabelle)
                   if (tabelle, s) not in ERLAUBT]
        if spalten:
            snapshot[tabelle] = (spalten, _alles(alte_db, tabelle, spalten))

    CouncilStore(alte_db).close()

    geprueft = 0
    for tabelle, (spalten, vorher) in snapshot.items():
        nachher = _alles(alte_db, tabelle, spalten)
        assert nachher == vorher, f"{tabelle}: Werte verändert"
        geprueft += len(vorher)
    assert geprueft == 8  # alle Zeilen des Fixtures, nicht nur ein paar


def test_altbestand_erbt_label_und_url_und_gewinnt_den_anker(alte_db):
    """Übernommen wird, was in den Daten steht — und die `document_id` kommt
    dazu: Sie lässt sich über die URL eindeutig in `council_anlagen`
    auflösen. Das ist Ableitung, keine Vermutung."""
    store = CouncilStore(alte_db)
    row = store._conn.execute(
        "SELECT h.* FROM council_ergebnisrechnung e "
        "JOIN council_herkunft h ON h.id = e.herkunft_id "
        "WHERE e.year = 2023 AND e.sub_budget_no IS NULL AND e.nr = 12").fetchone()
    store.close()
    assert row["label"] == JA_LABEL
    assert row["url"] == JA_URL
    assert row["kind"] == "ris"
    assert row["document_id"] == 280861     # der Anker, den der Altbestand nicht hatte
    # Der Zeitstempel der Zeilen, nicht der Zeitpunkt der Migration.
    assert row["fetched_at"] == "2026-08-14T07:12:01"


def test_altbestand_bekommt_unbekannt_statt_einer_erfundenen_probe(alte_db):
    """Was der Altbestand nicht festhielt, wird nicht erfunden.

    Die Zeilen SIND durch eine Probe gegangen — welche, steht nirgends. Also
    steht `unbekannt` da und `citation` bleibt leer, statt „Abschnitt 6.3.1"
    zu behaupten, weil es meistens stimmt. Der nächste Einlese-Lauf trägt
    beides nach."""
    store = CouncilStore(alte_db)
    alle = store.get_herkunft()
    store.close()
    assert alle, "keine Herkunft angelegt"
    assert {h["probe"] for h in alle} == {herkunft.UNBEKANNT}
    assert all(h["citation"] is None for h in alle)
    assert all(h["probe_result"] is None for h in alle)
    # Der Erklärsatz sagt es der Leserin auch.
    assert any("nächste Einlese-Lauf" in t for t in alle[0]["probes"])


def test_die_quellenart_kommt_aus_der_url_nicht_aus_der_tabelle(alte_db):
    """`council_haushalt` trägt beide Arten: Manche Jahrgänge kamen als PDF von
    oldenburg.de, 2024 als CSV aus dem Open-Data-Portal. Eine feste Zuordnung
    „Tabelle → Quellenart" verfehlte den zweiten Fall still."""
    store = CouncilStore(alte_db)
    art = dict(store._conn.execute(
        "SELECT h.url, h.kind FROM council_haushalt x "
        "JOIN council_herkunft h ON h.id = x.herkunft_id").fetchall())
    steuer_art = store._conn.execute(
        "SELECT h.kind FROM council_steuern s "
        "JOIN council_herkunft h ON h.id = s.herkunft_id").fetchone()[0]
    store.close()
    assert art == {PLAN_URL: "city"}
    assert steuer_art == "opendata"


def test_nachruesten_ist_idempotent(alte_db):
    """Zweimal öffnen legt nicht zweimal an."""
    CouncilStore(alte_db).close()
    store = CouncilStore(alte_db)
    erste = len(store.get_herkunft())
    store.close()
    CouncilStore(alte_db).close()
    store = CouncilStore(alte_db)
    assert len(store.get_herkunft()) == erste
    assert store.herkunft_luecken() == {}
    store.close()


# --- 2. Was eine frisch geschriebene Zeile festhält ---------------------------

def test_geschriebene_zeile_weiss_wo_sie_steht_und_womit_sie_gedeckt_ist(tmp_path):
    """Die eigentliche Zusage: Fundstelle **und** Probe stehen an der Zahl."""
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_ergebnisrechnung(2024, [
        {"nr": 12, "label": "Summe ordentliche Erträge", "budgeted": 693.6e6,
         "plan": 693.6e6, "plan_kind": "budget", "result": 799.1e6, "is_total": 1},
    ], Herkunft(
        kind="ris", probe=["structure_check", "prior_year_chain"], document_id=280863,
        label="Jahresabschluss 2024 der Kernverwaltung",
        url="https://buergerinfo.oldenburg.de/getfile.php?id=280863&type=do",
        citation="Ergebnisrechnung der Kernverwaltung, Posten 1–24",
        page=161, as_of="Jahresabschluss 2024"))

    row = store._conn.execute(
        "SELECT e.result, h.citation, h.page, h.probe, h.document_id, h.as_of "
        "FROM council_ergebnisrechnung e "
        "JOIN council_herkunft h ON h.id = e.herkunft_id").fetchone()
    assert row["result"] == 799.1e6
    assert row["citation"] == "Ergebnisrechnung der Kernverwaltung, Posten 1–24"
    assert row["page"] == 161
    assert row["probe"] == "structure_check,prior_year_chain"
    assert row["document_id"] == 280863
    assert row["as_of"] == "Jahresabschluss 2024"

    # Und lesbar für die Oberfläche: zwei Erklärsätze, einer je Probe.
    (h,) = store.get_herkunft()
    assert len(h["probes"]) == 2
    assert "Posten 12" in h["probes"][0] and "Vorjahres" in h["probes"][1]
    assert "key" not in h        # interner Fingerabdruck, kein Lesestoff
    store.close()


def test_die_alten_spalten_tragen_weiter_dieselben_werte(tmp_path):
    """`source_label`/`source_url` verschwinden nicht — sie werden aus
    derselben Angabe gefüllt. Kein Lesepfad muss sich ändern."""
    store = CouncilStore(tmp_path / "c.sqlite")
    q = Herkunft(kind="ris", probe="product_row", document_id=7,
                 label="007 THH01", url="https://example.org/thh01.pdf",
                 citation="Teilergebnishaushalt THH01, Produktebene")
    store.save_produkte(2023, [{"product_no": "P10.111023", "product_name": "Archivierung",
                                "sub_budget_no": 1, "revenues": 1.0, "expenses": 2.0,
                                "result": -1.0}], q)
    row = store.get_produkte(2023)[0]
    assert row["source_label"] == "007 THH01"
    assert row["source_url"] == "https://example.org/thh01.pdf"
    assert row["herkunft_id"] is not None
    store.close()


def test_zwei_ebenen_desselben_dokuments_bekommen_zwei_herkuenfte(tmp_path):
    """Gesamtrechnung und Teilhaushalte stehen im selben PDF, aber an
    verschiedenen Stellen und hinter verschiedenen Proben. Eine gemeinsame
    Herkunft wäre für beide ungenau — und genau dieser Fall wiederholt sich
    bei den Beteiligungen (Konzern- gegen Einzelabschluss)."""
    store = CouncilStore(tmp_path / "c.sqlite")
    gemeinsam = dict(kind="ris", document_id=99, label="JA 2023",
                     url="https://example.org/ja.pdf")
    posten = [{"nr": 12, "label": "Summe ordentliche Erträge", "budgeted": 1.0,
               "result": 2.0, "is_total": 1}]
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        probe="structure_check", citation="Ergebnisrechnung der Kernverwaltung",
        **gemeinsam))
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        probe="sub_budget_sum_check", citation="Teil-Ergebnisrechnung THH07",
        probe_result="0.00 % Abweichung zur Gesamtrechnung", **gemeinsam),
        sub_budget_no=7, sub_budget_name="Stadtplanung")

    nach_ebene = dict(store._conn.execute(
        "SELECT COALESCE(e.sub_budget_no, -1), h.citation FROM council_ergebnisrechnung e "
        "JOIN council_herkunft h ON h.id = e.herkunft_id").fetchall())
    assert nach_ebene[-1] == "Ergebnisrechnung der Kernverwaltung"
    assert nach_ebene[7] == "Teil-Ergebnisrechnung THH07"
    assert len(store.get_herkunft()) == 2
    store.close()


def test_dieselbe_herkunft_wird_nicht_zweimal_angelegt(tmp_path):
    """Idempotenz über den inhaltlichen Fingerabdruck: Ein zweiter Lauf
    derselben Quelle bekommt dieselbe ID. Ohne das wüchse die Tabelle mit der
    Zahl der Läufe statt mit der Zahl der Quellen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    q = Herkunft(kind="opendata", probe=herkunft.UNGEPRUEFT, url=CSV_URL,
                 citation="Datensatz 1104")
    erste = store.merke_herkunft(q)
    zweite = store.merke_herkunft(q)
    assert erste == zweite
    assert len(store.get_herkunft()) == 1
    # Eine andere Fundstelle im selben Dokument ist eine andere Herkunft.
    assert store.merke_herkunft(
        Herkunft(kind="opendata", probe=herkunft.UNGEPRUEFT, url=CSV_URL,
                 citation="Datensatz 1106")) != erste
    store.close()


# --- 3. Damit es die nächsten fünf Quellen nicht anders machen können ---------

def test_jede_registrierte_tabelle_traegt_die_spalte(tmp_path):
    """Die Arbeitsanweisung an einen neuen Parser, als Prüfung.

    Wer eine Zieltabelle in `HERKUNFT_TABELLEN` einträgt, bekommt die Spalte
    beim nächsten Öffnen — und wer sie einträgt, ohne sie im Schema anzulegen,
    fällt hier auf."""
    store = CouncilStore(tmp_path / "c.sqlite")
    for tabelle in herkunft.HERKUNFT_TABELLEN:
        spalten = {r[1] for r in store._conn.execute(f"PRAGMA table_info({tabelle})")}
        assert spalten, f"{tabelle} steht in HERKUNFT_TABELLEN, existiert aber nicht"
        assert "herkunft_id" in spalten, f"{tabelle} ohne herkunft_id"
    store.close()


def test_ohne_probe_gibt_es_keine_herkunft():
    """„Womit ist die Zahl abgesichert?" lässt sich nicht überspringen —
    höchstens ausdrücklich verneinen."""
    with pytest.raises(ValueError, match="ohne Probe"):
        Herkunft(kind="ris", probe=[], url="https://example.org/x")
    with pytest.raises(ValueError, match="Unbekannte Probe"):
        Herkunft(kind="ris", probe="augenmass", url="https://example.org/x")
    with pytest.raises(ValueError, match="Unbekannte Quellenart"):
        Herkunft(kind="irgendwoher", probe="total_row", url="https://example.org/x")
    with pytest.raises(ValueError, match="ohne Verweis"):
        Herkunft(kind="ris", probe="total_row")
    with pytest.raises(ValueError, match="Widerspruch"):
        Herkunft(kind="ris", probe=[herkunft.UNGEPRUEFT, "total_row"],
                 url="https://example.org/x")
    # Der ausdrückliche Verzicht geht — und ist als solcher erkennbar.
    ohne = Herkunft(kind="opendata", probe=herkunft.UNGEPRUEFT, url=CSV_URL)
    assert ohne.geprueft is False
    assert Herkunft(kind="ris", probe=herkunft.UNBEKANNT, url=JA_URL).geprueft is True


def test_luecken_melden_zeilen_ohne_herkunft(tmp_path):
    """Das Frühwarnsystem: Eine Zieltabelle, die ihre `herkunft_id` nicht
    füllt, steht nach jedem Ingest-Lauf im Protokoll."""
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.herkunft_luecken() == {}
    store._conn.execute(
        "INSERT INTO council_steuern (year, kind, amount, source_url, fetched_at) "
        "VALUES (2025, 'Hundesteuer', 1.0, 'https://example.org/x.csv', '2026-01-01')")
    store._conn.commit()
    assert store.herkunft_luecken() == {"council_steuern": 1}
    store.close()


def test_verwaiste_herkunft_wird_aufgeraeumt(tmp_path):
    """Ein erneuter Lauf ersetzt einen Jahrgang; die Herkunft der alten Zeilen
    bliebe sonst liegen. Aufgeräumt wird auf Ansage aus den Ingest-Skripten,
    nicht beim Öffnen der Datenbank."""
    store = CouncilStore(tmp_path / "c.sqlite")
    posten = [{"nr": 12, "label": "Summe", "budgeted": 1.0, "result": 2.0}]
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        kind="ris", probe=herkunft.UNBEKANNT, url=JA_URL))
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        kind="ris", probe="structure_check", url=JA_URL,
        citation="Ergebnisrechnung der Kernverwaltung"))
    assert len(store.get_herkunft()) == 2      # die alte hängt noch herum

    assert store.herkunft_aufraeumen() == 1
    (uebrig,) = store.get_herkunft()
    assert uebrig["probe"] == "structure_check"
    assert store.herkunft_luecken() == {}
    assert store.herkunft_aufraeumen() == 0    # zweimal aufräumen tut nichts
    store.close()


# --- 4. Vom Beleg zum Dokument -----------------------------------------------
#
# Das Quellenverzeichnis der Haushalts-Seiten beschreibt eine Quelle über alle
# Jahrgänge hinweg („Die Jahresabschlüsse 2017–2024"). Sein Link führte
# deshalb auf `https://buergerinfo.oldenburg.de` — die Startseite, auf der man
# das Dokument selbst suchen darf. `haushalt_dokumente()` liefert die fehlende
# Hälfte: welches PDF zu welchem Jahrgang gehört.

def test_dokumente_je_quelle_und_jahrgang(tmp_path):
    """Zwei Jahrgänge derselben Quelle führen auf zwei verschiedene PDFs —
    genau das war der Fehler: Ein Beleg an einer Zahl von 2023 zeigte auf
    dieselbe Startseite wie einer von 2017."""
    store = CouncilStore(tmp_path / "c.sqlite")
    posten = [{"nr": 12, "label": "Summe", "budgeted": 1.0, "result": 2.0}]
    for year, doc in ((2023, 280861), (2024, 295294)):
        store.save_ergebnisrechnung(year, posten, Herkunft(
            kind="ris", probe="structure_check", document_id=doc,
            label=f"Jahresabschluss {year}",
            url=f"https://buergerinfo.oldenburg.de/getfile.php?id={doc}&type=do",
            citation="Ergebnisrechnung der Kernverwaltung", page=161))

    nach_jahr = {d["year"]: d for d in store.haushalt_dokumente()["jahresabschluss"]}
    assert nach_jahr[2023]["url"].endswith("id=280861&type=do")
    assert nach_jahr[2024]["url"].endswith("id=295294&type=do")
    # Die Fundstelle fährt mit: Ohne sie ist die URL bei 300 Seiten zu wenig.
    assert nach_jahr[2024]["citation"] == "Ergebnisrechnung der Kernverwaltung"
    assert nach_jahr[2024]["page"] == 161
    store.close()


def test_dokumente_trennen_die_zwei_ebenen_eines_jahresabschlusses(tmp_path):
    """Gesamtrechnung und Teilhaushalts-Ebene sind im Verzeichnis zwei
    Quellen. Sie stehen im selben PDF, aber an verschiedenen Stellen — und
    genau die Stelle ist der Gewinn gegenüber einem nackten Link."""
    store = CouncilStore(tmp_path / "c.sqlite")
    gemeinsam = dict(kind="ris", document_id=99, label="JA 2023", url=JA_URL)
    posten = [{"nr": 12, "label": "Summe", "budgeted": 1.0, "result": 2.0}]
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        probe="structure_check", citation="Ergebnisrechnung der Kernverwaltung",
        **gemeinsam))
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        probe="sub_budget_sum_check", citation="Teil-Ergebnisrechnung THH07",
        **gemeinsam), sub_budget_no=7, sub_budget_name="Stadtplanung")

    doks = store.haushalt_dokumente()
    assert doks["jahresabschluss"][0]["citation"] == "Ergebnisrechnung der Kernverwaltung"
    assert doks["ergebnisrechnung_thh"][0]["citation"] == "Teil-Ergebnisrechnung THH07"
    store.close()


def test_ein_jahrgang_darf_mehrere_dokumente_tragen(tmp_path):
    """Ein Produkt-Jahrgang verteilt sich auf mehrere Teilhaushalts-Anlagen.
    Eine davon zu verlinken und die übrigen zu verschweigen wäre wieder die
    halbe Wahrheit — die API nennt alle, die Seite entscheidet."""
    store = CouncilStore(tmp_path / "c.sqlite")
    for sub_budget in (1, 4):
        store.save_produkte(2023, [
            {"product_no": f"P{sub_budget}", "product_name": "Aufgabe", "sub_budget_no": sub_budget,
             "revenues": 1.0, "expenses": 2.0, "result": -1.0}],
            Herkunft(kind="ris", probe="product_row", document_id=sub_budget,
                     label=f"007 THH0{sub_budget}",
                     url=f"https://buergerinfo.oldenburg.de/getfile.php?id={sub_budget}&type=do"))

    part = store.haushalt_dokumente()["teilhaushalt"]
    assert {d["year"] for d in part} == {2023}
    assert {d["label"] for d in part} == {"007 THH01", "007 THH04"}
    store.close()


def test_ohne_dokument_meldet_sich_die_quelle_gar_nicht(tmp_path):
    """Kein toter Link: Wo wir keine Adresse haben, fehlt der Schlüssel — die
    Oberfläche fällt dann auf die statische Adresse zurück und schreibt
    „Im Ratsinformationssystem suchen" statt „Dokument öffnen"."""
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.haushalt_dokumente() == {}

    # Altbestand ohne Herkunft, aber mit URL an der Datenzeile: Der Rückfall
    # auf die Alt-Spalte greift, sonst verlöre die Umstellung Belege, die es
    # vorher schon gab.
    store._conn.execute(
        "INSERT INTO council_haushalt (year, area, expenses, is_total, "
        " source_url, fetched_at) VALUES (2020, 'Summe', 1.0, 1, ?, '2026-01-01')",
        (PLAN_URL,))
    store._conn.commit()
    # `official_text` steht auch hier — als None. Der Altbestand hängt an keiner
    # Anlage, also gibt es keinen Ratsvorgang zu zeigen; das Feld fehlt aber
    # nicht, sonst müsste die Oberfläche zwei Formen unterscheiden.
    assert store.haushalt_dokumente()["plan"] == [
        {"year": 2020, "url": PLAN_URL, "label": None, "citation": None,
         "page": None, "official_text": None}]
def test_vergessene_zieltabelle_verliert_ihre_herkunft_nicht(tmp_path):
    """Der Schritt, den man vergisst: eine neue Zieltabelle nicht in
    ``HERKUNFT_TABELLEN`` eintragen.

    Bis 08/2026 kostete das die Herkunft. Aufräumen und Lücken-Meldung gingen
    beide nur die handgepflegte Liste durch — eine Tabelle, die dort fehlt,
    hat aus Sicht des DELETE keine Verweise, ihre Herkünfte gälten als
    verwaist. Ihre Zeilen zeigten danach auf eine Nummer, die es nicht mehr
    gibt oder, nach der nächsten Vergabe, auf ein **fremdes Dokument**.

    Beides wird jetzt am Schema entschieden, nicht an der Liste."""
    store = CouncilStore(tmp_path / "c.sqlite")
    store.save_ergebnisrechnung(2023, [
        {"nr": 12, "label": "Summe", "budgeted": 1.0, "result": 2.0}],
        Herkunft(kind="ris", probe="structure_check", url=JA_URL,
                 citation="Ergebnisrechnung der Kernverwaltung"))

    # Eine Schicht, die es in `HERKUNFT_TABELLEN` nie geschafft hat.
    with store._conn:
        store._conn.execute(
            "CREATE TABLE council_beteiligungen_kennzahlen ("
            "year INTEGER, value REAL, herkunft_id INTEGER)")
        hid = store.merke_herkunft(Herkunft(
            kind="ris", probe="total_row", url=JA_URL,
            citation="Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern"))
        store._conn.execute(
            "INSERT INTO council_beteiligungen_kennzahlen VALUES (2023, 1.0, ?)", (hid,))
    assert "council_beteiligungen_kennzahlen" not in herkunft.HERKUNFT_TABELLEN

    assert store.herkunft_aufraeumen() == 0        # nichts ist verwaist
    assert {h["id"] for h in store.get_herkunft()} == {hid, hid - 1}
    # Und der Verweis zeigt weiter auf genau das Dokument, aus dem er stammt.
    (probe,) = store._conn.execute(
        "SELECT h.citation FROM council_beteiligungen_kennzahlen k "
        "JOIN council_herkunft h ON h.id = k.herkunft_id").fetchone()
    assert probe == "Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern"

    # Und sie ist auch für die Lücken-Meldung sichtbar, statt stillgestellt.
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_beteiligungen_kennzahlen VALUES (2024, 2.0, NULL)")
    assert store.herkunft_luecken() == {"council_beteiligungen_kennzahlen": 1}
    store.close()


# --- Der Ratsvorgang hinter der Zahl -----------------------------------------
#
# Der Beleg-Chip kannte bisher das Dokument. Was fehlte, war der Weg vom
# Dokument zu dem Beschluss, der es verabschiedet hat — die Strecke
# `council_herkunft.document_id` → `council_anlagen.kvonr` →
# `council_decisions.kvonr`. Erst damit wird aus „steht im Jahresabschluss
# 2024" ein „der Rat hat das am … beschlossen".

def _vorgang(store, *, kvonr=900, document_id=7001, stationen=()):
    """Eine Vorlage mit einer Anlage und ihren Stationen durch die Gremien."""
    from council.scraper import AgendaItem, CouncilSession

    store.save_vorlage({"kvonr": kvonr, "template_number": "24/0815",
                        "title": "Jahresabschluss 2024", "raw_text": ""})
    store.save_anlagen(kvonr, [{"document_id": document_id,
                                "label": "Jahresabschluss 2024",
                                "url": "https://example.org/ja2024.pdf"}])
    for ksinr, committee, date, outcome in stationen:
        store.save_session(CouncilSession(
            ksinr=ksinr, committee=committee, session_date=date,
            session_time="17:00", location="Rathaus",
            agenda_items=[AgendaItem(item_number="5", title="Jahresabschluss 2024",
                                     kvonr=kvonr)]))
        store.save_protocol(
            ksinr, {"document_id": ksinr, "url": f"https://example.org/p{ksinr}.pdf"},
            {"protocol_nr": "01/25"}, "Kurzbericht.", 4, "test",
            [{"item_number": "5", "title": "Jahresabschluss 2024",
              "outcome": outcome, "vote": "majority", "kvonr": kvonr}], [])


def _herkunft_mit_dokument(store, document_id=7001):
    with store.transaktion():
        return store.merke_herkunft(Herkunft(
            kind="ris", probe="total_row", document_id=document_id,
            label="Jahresabschluss 2024", url="https://example.org/ja2024.pdf",
            citation="Ergebnisrechnung der Kernverwaltung"))


def test_beschluss_haengt_am_dokument(tmp_path):
    """Die Zahl kennt nicht nur ihr Papier, sondern ihren Vorgang."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _vorgang(store, stationen=[(41, "Rat", "2025-09-16", "accepted")])
    hid = _herkunft_mit_dokument(store)

    (h,) = store.get_herkunft([hid])
    assert h["official_text"]["date"] == "2025-09-16"
    assert h["official_text"]["committee"] == "Rat"
    assert h["official_text"]["outcome"] == "accepted"
    assert h["official_text"]["kvonr"] == 900
    store.close()


def test_rat_sticht_den_ausschuss(tmp_path):
    """Eine Vorlage läuft durch mehrere Gremien — verabschiedet wird sie im Rat.

    Der Ausschuss tagt vorher und trägt bei derselben Vorlage ein eigenes
    Ergebnis. Entschieden wird deshalb am Gremium, nicht am Datum."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _vorgang(store, stationen=[
        (40, "Ausschuss für Finanzen und Beteiligungen", "2025-09-02", "noted"),
        (41, "Rat", "2025-09-16", "accepted"),
    ])
    hid = _herkunft_mit_dokument(store)

    (h,) = store.get_herkunft([hid])
    assert h["official_text"]["committee"] == "Rat"
    assert h["official_text"]["date"] == "2025-09-16"
    store.close()


def test_vertagter_vorgang_wird_nicht_verschwiegen(tmp_path):
    """Ein laufender Vorgang ist keine Zahl ohne Beleg.

    Wer hier auf `angenommen` filterte, ließe genau die interessanten Fälle
    stumm verschwinden — die Seite soll sagen können, dass noch nichts
    entschieden ist."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _vorgang(store, stationen=[(41, "Rat", "2025-09-16", "postponed")])
    hid = _herkunft_mit_dokument(store)

    (h,) = store.get_herkunft([hid])
    assert h["official_text"]["outcome"] == "postponed"
    store.close()


def test_anlage_ohne_vorgang_erfindet_keinen(tmp_path):
    """Kein Beschluss im Bestand heißt: kein Beschluss auf der Seite."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _vorgang(store, stationen=[])          # Vorlage und Anlage, aber keine Sitzung
    hid = _herkunft_mit_dokument(store)

    (h,) = store.get_herkunft([hid])
    assert h["official_text"] is None
    store.close()


# --- Der Datenstand fällt aus dem Bestand ------------------------------------

def test_jahrgaenge_kommen_aus_dem_bestand(tmp_path):
    """Das Quellenverzeichnis soll seine Jahresspanne nicht mehr behaupten.

    Und zwar getrennt von der Frage, ob ein Dokument verlinkt ist: Ein
    Jahrgang, der im Bestand steht, dessen Herkunft aber keine Adresse führt,
    ist für den Datenstand da und für den Dokumentlink nicht. Wer beides aus
    einer Abfrage nähme, verschwiege im Datenstand genau die Jahrgänge, die
    ohnehin am dünnsten belegt sind."""
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.haushalt_jahrgaenge() == {}

    with store._conn:
        store._conn.execute(
            "INSERT INTO council_haushalt (year, area, expenses, is_total, "
            " source_url, fetched_at) VALUES (2019, 'Summe', 1.0, 1, NULL, '2026-01-01')")
        store._conn.execute(
            "INSERT INTO council_haushalt (year, area, expenses, is_total, "
            " source_url, fetched_at) VALUES (2020, 'Summe', 1.0, 1, ?, '2026-01-01')",
            (PLAN_URL,))

    assert store.haushalt_jahrgaenge()["plan"] == [2019, 2020]
    # Der Dokumentlink kennt nur den Jahrgang mit Adresse — genau der
    # Unterschied, wegen dem das zwei Abfragen sind.
    assert [d["year"] for d in store.haushalt_dokumente()["plan"]] == [2020]
    store.close()


def test_jahrgaenge_trennen_die_zwei_ebenen_des_abschlusses(tmp_path):
    """Gesamtrechnung und Teilhaushalte stehen in DERSELBEN Tabelle und sind
    zwei Quellen mit eigenem Datenstand — die Teilhaushalts-Ebene kann an
    ihrer Summenprobe scheitern, während die Gesamtrechnung steht."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        for year, sub_budget in ((2022, None), (2023, None), (2022, 7)):
            store._conn.execute(
                "INSERT INTO council_ergebnisrechnung (year, sub_budget_no, nr, label, "
                " fetched_at) VALUES (?, ?, 12, 'Erträge', '2026-01-01')", (year, sub_budget))

    years = store.haushalt_jahrgaenge()
    assert years["jahresabschluss"] == [2022, 2023]
    assert years["ergebnisrechnung_thh"] == [2022]
    store.close()


def test_herkunft_ohne_dokument_bleibt_unberuehrt(tmp_path):
    """Die Schichten von oldenburg.de und vom Landesamt haben keine Anlage —
    sie dürfen an der neuen Abfrage nicht hängenbleiben."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store.transaktion():
        hid = store.merke_herkunft(Herkunft(
            kind="city", probe="total_row",
            url="https://oldenburg.de/haushalt.pdf",
            citation="Gesamtergebnisplan"))

    (h,) = store.get_herkunft([hid])
    assert h["official_text"] is None
    assert h["document_id"] is None
    store.close()
