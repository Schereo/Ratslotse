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
# (`quelle_label`/`quelle_url`, `label`/`url`, `source_url`), keine
# `herkunft_id`, keine `council_herkunft`.

ALTES_SCHEMA = """
CREATE TABLE council_anlagen (
  document_id INTEGER PRIMARY KEY, kvonr INTEGER NOT NULL, label TEXT,
  url TEXT, is_antrag INTEGER NOT NULL DEFAULT 0, antragsteller TEXT,
  raw_text TEXT, n_pages INTEGER, fetched_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'listed');
CREATE TABLE council_ergebnisrechnung (
  jahr INTEGER NOT NULL, thh_nr INTEGER, thh_name TEXT,
  nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL,
  vorjahr REAL, ansatz REAL, plan REAL, plan_art TEXT,
  ergebnis REAL, abweichung REAL, ist_summe INTEGER NOT NULL DEFAULT 0,
  quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL,
  PRIMARY KEY (jahr, thh_nr, nr));
CREATE TABLE council_abweichungsgruende (
  jahr INTEGER NOT NULL, nr INTEGER NOT NULL, bezeichnung TEXT NOT NULL,
  delta_mio REAL, prozent REAL, text TEXT NOT NULL,
  quelle_label TEXT, quelle_url TEXT, fetched_at TEXT NOT NULL,
  PRIMARY KEY (jahr, nr));
CREATE TABLE council_pruefbericht_quellen (
  jahr INTEGER PRIMARY KEY, label TEXT, url TEXT, n_pages INTEGER,
  lesbar INTEGER NOT NULL DEFAULT 1, fetched_at TEXT NOT NULL);
CREATE TABLE council_haushalt (
  id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL,
  bereich TEXT NOT NULL, ertraege REAL, aufwendungen REAL, ergebnis REAL,
  is_summe INTEGER NOT NULL DEFAULT 0,
  source_url TEXT, fetched_at TEXT NOT NULL, UNIQUE(year, bereich));
CREATE TABLE council_steuern (
  jahr INTEGER NOT NULL, art TEXT NOT NULL, betrag REAL,
  source_url TEXT, fetched_at TEXT NOT NULL, PRIMARY KEY (jahr, art));
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
        "INSERT INTO council_ergebnisrechnung (jahr, thh_nr, thh_name, nr, bezeichnung, "
        " vorjahr, ansatz, plan, plan_art, ergebnis, abweichung, ist_summe, "
        " quelle_label, quelle_url, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
        "INSERT INTO council_abweichungsgruende (jahr, nr, bezeichnung, delta_mio, "
        " prozent, text, quelle_label, quelle_url, fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (2023, 1, "Steuern und ähnliche Abgaben", 75.1, 24.82,
         "Die Mehrerträge entfallen nahezu auf den Bereich der Gewerbesteuer.",
         JA_LABEL, JA_URL, "2026-08-14T07:12:00"))
    cn.execute(
        "INSERT INTO council_pruefbericht_quellen (jahr, label, url, n_pages, lesbar, "
        " fetched_at) VALUES (2023, 'Schlussbericht 2023', ?, 61, 1, '2026-08-14T07:13:00')",
        (JA_URL,))
    cn.executemany(
        "INSERT INTO council_haushalt (year, bereich, ertraege, aufwendungen, ergebnis, "
        " is_summe, source_url, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
        [(2026, "Jugend und Familie", 40e6, 210e6, -170e6, 0, PLAN_URL, "2026-08-01T06:00:00"),
         (2026, "Summe", 52e6, 271e6, -219e6, 1, PLAN_URL, "2026-08-01T06:00:00")])
    cn.execute("INSERT INTO council_steuern (jahr, art, betrag, source_url, fetched_at) "
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
    vorher = {t: _spalten(alte_db, t)
              for t in herkunft.HERKUNFT_TABELLEN if _spalten(alte_db, t)}
    CouncilStore(alte_db).close()
    for tabelle, alt in vorher.items():
        neu = _spalten(alte_db, tabelle)
        assert set(alt) <= set(neu), f"{tabelle}: Spalte verschwunden"
        assert "herkunft_id" in neu, f"{tabelle}: ohne herkunft_id"


def test_kein_einziger_bestehender_wert_aendert_sich(alte_db):
    """Der Kern der Zusage. Verglichen wird **zeilenweise über alle alten
    Spalten**, nicht über Zeilenzahlen: Eine Migration, die die richtige
    Anzahl behält und in einer Zeile den Betrag verschiebt, zählt korrekt und
    ist trotzdem der schlimmste denkbare Ausgang."""
    snapshot = {}
    for tabelle in herkunft.HERKUNFT_TABELLEN:
        spalten = _spalten(alte_db, tabelle)
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
    zeile = store._conn.execute(
        "SELECT h.* FROM council_ergebnisrechnung e "
        "JOIN council_herkunft h ON h.id = e.herkunft_id "
        "WHERE e.jahr = 2023 AND e.thh_nr IS NULL AND e.nr = 12").fetchone()
    store.close()
    assert zeile["label"] == JA_LABEL
    assert zeile["url"] == JA_URL
    assert zeile["art"] == "ris"
    assert zeile["dokument_id"] == 280861     # der Anker, den der Altbestand nicht hatte
    # Der Zeitstempel der Zeilen, nicht der Zeitpunkt der Migration.
    assert zeile["fetched_at"] == "2026-08-14T07:12:01"


def test_altbestand_bekommt_unbekannt_statt_einer_erfundenen_probe(alte_db):
    """Was der Altbestand nicht festhielt, wird nicht erfunden.

    Die Zeilen SIND durch eine Probe gegangen — welche, steht nirgends. Also
    steht `unbekannt` da und `fundstelle` bleibt leer, statt „Abschnitt 6.3.1"
    zu behaupten, weil es meistens stimmt. Der nächste Einlese-Lauf trägt
    beides nach."""
    store = CouncilStore(alte_db)
    alle = store.get_herkunft()
    store.close()
    assert alle, "keine Herkunft angelegt"
    assert {h["probe"] for h in alle} == {herkunft.UNBEKANNT}
    assert all(h["fundstelle"] is None for h in alle)
    assert all(h["probe_ergebnis"] is None for h in alle)
    # Der Erklärsatz sagt es der Leserin auch.
    assert any("nächste Einlese-Lauf" in t for t in alle[0]["proben"])


def test_die_quellenart_kommt_aus_der_url_nicht_aus_der_tabelle(alte_db):
    """`council_haushalt` trägt beide Arten: Manche Jahrgänge kamen als PDF von
    oldenburg.de, 2024 als CSV aus dem Open-Data-Portal. Eine feste Zuordnung
    „Tabelle → Quellenart" verfehlte den zweiten Fall still."""
    store = CouncilStore(alte_db)
    art = dict(store._conn.execute(
        "SELECT h.url, h.art FROM council_haushalt x "
        "JOIN council_herkunft h ON h.id = x.herkunft_id").fetchall())
    steuer_art = store._conn.execute(
        "SELECT h.art FROM council_steuern s "
        "JOIN council_herkunft h ON h.id = s.herkunft_id").fetchone()[0]
    store.close()
    assert art == {PLAN_URL: "stadt"}
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
        {"nr": 12, "bezeichnung": "Summe ordentliche Erträge", "ansatz": 693.6e6,
         "plan": 693.6e6, "plan_art": "ansatz", "ergebnis": 799.1e6, "ist_summe": 1},
    ], Herkunft(
        art="ris", probe=["strukturprobe", "vorjahreskette"], dokument_id=280863,
        label="Jahresabschluss 2024 der Kernverwaltung",
        url="https://buergerinfo.oldenburg.de/getfile.php?id=280863&type=do",
        fundstelle="Ergebnisrechnung der Kernverwaltung, Posten 1–24",
        seite=161, stand="Jahresabschluss 2024"))

    zeile = store._conn.execute(
        "SELECT e.ergebnis, h.fundstelle, h.seite, h.probe, h.dokument_id, h.stand "
        "FROM council_ergebnisrechnung e "
        "JOIN council_herkunft h ON h.id = e.herkunft_id").fetchone()
    assert zeile["ergebnis"] == 799.1e6
    assert zeile["fundstelle"] == "Ergebnisrechnung der Kernverwaltung, Posten 1–24"
    assert zeile["seite"] == 161
    assert zeile["probe"] == "strukturprobe,vorjahreskette"
    assert zeile["dokument_id"] == 280863
    assert zeile["stand"] == "Jahresabschluss 2024"

    # Und lesbar für die Oberfläche: zwei Erklärsätze, einer je Probe.
    (h,) = store.get_herkunft()
    assert len(h["proben"]) == 2
    assert "Posten 12" in h["proben"][0] and "Vorjahres" in h["proben"][1]
    assert "schluessel" not in h        # interner Fingerabdruck, kein Lesestoff
    store.close()


def test_die_alten_spalten_tragen_weiter_dieselben_werte(tmp_path):
    """`quelle_label`/`quelle_url` verschwinden nicht — sie werden aus
    derselben Angabe gefüllt. Kein Lesepfad muss sich ändern."""
    store = CouncilStore(tmp_path / "c.sqlite")
    q = Herkunft(art="ris", probe="produktzeile", dokument_id=7,
                 label="007 THH01", url="https://example.org/thh01.pdf",
                 fundstelle="Teilergebnishaushalt THH01, Produktebene")
    store.save_produkte(2023, [{"produkt_nr": "P10.111023", "produkt_name": "Archivierung",
                                "thh_nr": 1, "ertraege": 1.0, "aufwendungen": 2.0,
                                "ergebnis": -1.0}], q)
    zeile = store.get_produkte(2023)[0]
    assert zeile["quelle_label"] == "007 THH01"
    assert zeile["quelle_url"] == "https://example.org/thh01.pdf"
    assert zeile["herkunft_id"] is not None
    store.close()


def test_zwei_ebenen_desselben_dokuments_bekommen_zwei_herkuenfte(tmp_path):
    """Gesamtrechnung und Teilhaushalte stehen im selben PDF, aber an
    verschiedenen Stellen und hinter verschiedenen Proben. Eine gemeinsame
    Herkunft wäre für beide ungenau — und genau dieser Fall wiederholt sich
    bei den Beteiligungen (Konzern- gegen Einzelabschluss)."""
    store = CouncilStore(tmp_path / "c.sqlite")
    gemeinsam = dict(art="ris", dokument_id=99, label="JA 2023",
                     url="https://example.org/ja.pdf")
    posten = [{"nr": 12, "bezeichnung": "Summe ordentliche Erträge", "ansatz": 1.0,
               "ergebnis": 2.0, "ist_summe": 1}]
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        probe="strukturprobe", fundstelle="Ergebnisrechnung der Kernverwaltung",
        **gemeinsam))
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        probe="summenprobe", fundstelle="Teil-Ergebnisrechnung THH07",
        probe_ergebnis="0.00 % Abweichung zur Gesamtrechnung", **gemeinsam),
        thh_nr=7, thh_name="Stadtplanung")

    nach_ebene = dict(store._conn.execute(
        "SELECT COALESCE(e.thh_nr, -1), h.fundstelle FROM council_ergebnisrechnung e "
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
    q = Herkunft(art="opendata", probe=herkunft.UNGEPRUEFT, url=CSV_URL,
                 fundstelle="Datensatz 1104")
    erste = store.merke_herkunft(q)
    zweite = store.merke_herkunft(q)
    assert erste == zweite
    assert len(store.get_herkunft()) == 1
    # Eine andere Fundstelle im selben Dokument ist eine andere Herkunft.
    assert store.merke_herkunft(
        Herkunft(art="opendata", probe=herkunft.UNGEPRUEFT, url=CSV_URL,
                 fundstelle="Datensatz 1106")) != erste
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
        Herkunft(art="ris", probe=[], url="https://example.org/x")
    with pytest.raises(ValueError, match="Unbekannte Probe"):
        Herkunft(art="ris", probe="augenmass", url="https://example.org/x")
    with pytest.raises(ValueError, match="Unbekannte Quellenart"):
        Herkunft(art="irgendwoher", probe="summenzeile", url="https://example.org/x")
    with pytest.raises(ValueError, match="ohne Verweis"):
        Herkunft(art="ris", probe="summenzeile")
    with pytest.raises(ValueError, match="Widerspruch"):
        Herkunft(art="ris", probe=[herkunft.UNGEPRUEFT, "summenzeile"],
                 url="https://example.org/x")
    # Der ausdrückliche Verzicht geht — und ist als solcher erkennbar.
    ohne = Herkunft(art="opendata", probe=herkunft.UNGEPRUEFT, url=CSV_URL)
    assert ohne.geprueft is False
    assert Herkunft(art="ris", probe=herkunft.UNBEKANNT, url=JA_URL).geprueft is True


def test_luecken_melden_zeilen_ohne_herkunft(tmp_path):
    """Das Frühwarnsystem: Eine Zieltabelle, die ihre `herkunft_id` nicht
    füllt, steht nach jedem Ingest-Lauf im Protokoll."""
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.herkunft_luecken() == {}
    store._conn.execute(
        "INSERT INTO council_steuern (jahr, art, betrag, source_url, fetched_at) "
        "VALUES (2025, 'Hundesteuer', 1.0, 'https://example.org/x.csv', '2026-01-01')")
    store._conn.commit()
    assert store.herkunft_luecken() == {"council_steuern": 1}
    store.close()


def test_verwaiste_herkunft_wird_aufgeraeumt(tmp_path):
    """Ein erneuter Lauf ersetzt einen Jahrgang; die Herkunft der alten Zeilen
    bliebe sonst liegen. Aufgeräumt wird auf Ansage aus den Ingest-Skripten,
    nicht beim Öffnen der Datenbank."""
    store = CouncilStore(tmp_path / "c.sqlite")
    posten = [{"nr": 12, "bezeichnung": "Summe", "ansatz": 1.0, "ergebnis": 2.0}]
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        art="ris", probe=herkunft.UNBEKANNT, url=JA_URL))
    store.save_ergebnisrechnung(2023, posten, Herkunft(
        art="ris", probe="strukturprobe", url=JA_URL,
        fundstelle="Ergebnisrechnung der Kernverwaltung"))
    assert len(store.get_herkunft()) == 2      # die alte hängt noch herum

    assert store.herkunft_aufraeumen() == 1
    (uebrig,) = store.get_herkunft()
    assert uebrig["probe"] == "strukturprobe"
    assert store.herkunft_luecken() == {}
    assert store.herkunft_aufraeumen() == 0    # zweimal aufräumen tut nichts
    store.close()


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
        {"nr": 12, "bezeichnung": "Summe", "ansatz": 1.0, "ergebnis": 2.0}],
        Herkunft(art="ris", probe="strukturprobe", url=JA_URL,
                 fundstelle="Ergebnisrechnung der Kernverwaltung"))

    # Eine Schicht, die es in `HERKUNFT_TABELLEN` nie geschafft hat.
    with store._conn:
        store._conn.execute(
            "CREATE TABLE council_beteiligungen_kennzahlen ("
            "jahr INTEGER, wert REAL, herkunft_id INTEGER)")
        hid = store.merke_herkunft(Herkunft(
            art="ris", probe="summenzeile", url=JA_URL,
            fundstelle="Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern"))
        store._conn.execute(
            "INSERT INTO council_beteiligungen_kennzahlen VALUES (2023, 1.0, ?)", (hid,))
    assert "council_beteiligungen_kennzahlen" not in herkunft.HERKUNFT_TABELLEN

    assert store.herkunft_aufraeumen() == 0        # nichts ist verwaist
    assert {h["id"] for h in store.get_herkunft()} == {hid, hid - 1}
    # Und der Verweis zeigt weiter auf genau das Dokument, aus dem er stammt.
    (probe,) = store._conn.execute(
        "SELECT h.fundstelle FROM council_beteiligungen_kennzahlen k "
        "JOIN council_herkunft h ON h.id = k.herkunft_id").fetchone()
    assert probe == "Abschnitt 4.1.1, Aufstellung nach Aufgabenträgern"

    # Und sie ist auch für die Lücken-Meldung sichtbar, statt stillgestellt.
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_beteiligungen_kennzahlen VALUES (2024, 2.0, NULL)")
    assert store.herkunft_luecken() == {"council_beteiligungen_kennzahlen": 1}
    store.close()
