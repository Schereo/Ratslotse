"""Die Kontenebene — Parser (``council/budget_accounts.py``), Ingest
(``finanzquellen.lies_budget_accounts``) und Facette ``accounts``.

Der Anlass sind echte Fragen vom 10.10.2026: „Wie hoch sind die Einnahmen
durch die Parkgebühren im Jahr?" und „Kann man Abweichungen sehen von Soll
und Ist?". Die Parkgebühren standen in keiner Tabelle; die Antwort griff auf
einen Anlagentext von 2023 zurück und bog beim Soll-Ist-Vergleich auf die
Gewerbesteuer ab.

Die Ausschnitte in ``fixtures/budget_accounts_thh.json`` sind die
THH-Tabellen dreier echter Teilhaushalts-Pläne (öffentliche Anlagen des
Ratsinformationssystems), jeweils bis zum Teilfinanzhaushalt.
"""
import json
from pathlib import Path

import pytest

from council import budget_accounts as parser, finanzquellen, qa
from council.geld import accounts
from council.store import CouncilStore

NAME = accounts.NAME
_FIX = json.loads((Path(__file__).resolve().parent / "fixtures" /
                   "budget_accounts_thh.json").read_text(encoding="utf-8"))


def _konto(parsed: dict, nr: str) -> dict:
    return next(a for a in parsed["accounts"] if a["account_no"] == nr)


# ---------------------------------------------------------------------------
# Der Parser
# ---------------------------------------------------------------------------

def test_plan_2026_parkgebuehren_mit_allen_spalten():
    p = parser.parse(_FIX["plan_2026_thh08"]["text"])
    assert p["sub_budget_no"] == 8 and p["sub_budget_name"] == "Verkehr und Straßenbau"
    assert p["columns"][0] == ("Ergebnis", 2024) and p["columns"][2] == ("Ansatz", 2026)
    park = _konto(p, "33211000")
    assert park["label"] == "Parkgebühren"
    assert park["kind"] == "revenue" and park["posten_label"] == "öffentlich-rechtliche Entgelte"
    assert park["values"][("Ergebnis", 2024)] == pytest.approx(4482612.19)
    assert park["values"][("Ansatz", 2025)] == 4394100
    assert park["values"][("Ansatz", 2027)] == 5228979


def test_bezeichnung_ueber_zwei_zeilen_und_aufwand():
    p = parser.parse(_FIX["plan_2026_thh08"]["text"])
    beleuchtung = _konto(p, "42124000")
    assert beleuchtung["label"] == "Unterhaltung Straßenbeleuchtung"
    assert beleuchtung["kind"] == "expense"
    assert beleuchtung["values"][("Ergebnis", 2024)] == pytest.approx(1970874.21)


def test_teilzeile_wird_ueber_die_postensumme_zugeordnet():
    """„31400000 Zuweisungen … Bund 80.000" (Plan 2019): eine einzige Zahl ohne
    Cent, also ein Ansatz — aber welcher? Die Postensumme sagt es: 2019."""
    p = parser.parse(_FIX["plan_2019_thh08"]["text"])
    bund = _konto(p, "31400000")
    assert bund["values"] == {("Ansatz", 2019): 80000}
    # Nur Cent → Ergebnis-Spalte.
    privat = _konto(p, "31470000")
    assert privat["values"] == {("Ergebnis", 2017): pytest.approx(19373.23)}


def test_seitenkopf_mitten_in_der_tabelle_stoert_nicht():
    """Der wiederholte Kopf trägt „Ansatz 2018 … - Euro -" — als Zahlen gelesen
    hinge „2018" an der Bezeichnung des nächsten Kontos."""
    p = parser.parse(_FIX["plan_2019_thh08"]["text"])
    leistung = _konto(p, "34610000")
    assert leistung["label"].startswith("Sonstige privatrechtliche")
    assert "2018" not in leistung["label"] and "Euro" not in leistung["label"]


def test_rundung_der_ansaetze_bricht_die_probe_nicht():
    """Posten 3 im Plan 2026: Die Konten ergeben 10.181.036, die Postenzeile
    sagt 10.181.037 — die Ansätze sind je Konto gerundet."""
    p = parser.parse(_FIX["plan_2026_thh08"]["text"])
    assert 3 in p["posten_ok"]
    assert _konto(p, "33710000")["values"][("Ansatz", 2026)] == 7822715


def test_vertauschbare_teilzeilen_bleiben_draussen_der_rest_nicht():
    """Plan 2026, THH02, Posten 7: zwei Konten mit derselben Teilzeile
    „50 50 50 50" — welches in welcher Spalte steht, ist nicht zu entscheiden.
    Die übrigen Konten des Postens sind es."""
    p = parser.parse(_FIX["plan_2026_thh02"]["text"])
    unklar = [r for r in p["posten_rejected"] if r["posten"] == 7]
    assert unklar and set(unklar[0]["accounts"]) >= {"34850201", "34850202"}
    assert _konto(p, "34851302")["values"][("Ansatz", 2026)] == 200000
    assert not any(a["account_no"] in ("34850201", "34850202") for a in p["accounts"])


def test_kein_teilhaushalt_kein_ergebnis():
    assert parser.parse("Vorbericht zum Haushalt 2026\nErgebnis 2024 Ansatz 2025") is None


# ---------------------------------------------------------------------------
# Der Ingest
# ---------------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    st = CouncilStore(tmp_path / "c.sqlite")
    for i, key in enumerate(("plan_2019_thh08", "plan_2026_thh08", "plan_2026_thh02")):
        f = _FIX[key]
        st._conn.execute(  # noqa: SLF001
            "INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, "
            "n_pages, fetched_at, status) VALUES (?,?,?,?,?,?,?,?)",
            (f["document_id"], 100 + i, f["label"], f["url"], f["text"], 90,
             "2026-10-11T00:00:00", "ok"))
    st._conn.commit()  # noqa: SLF001
    p = finanzquellen.Protokoll()
    bericht = finanzquellen.lies_budget_accounts(st, p)
    assert bericht["neue_einheiten"] == [(2019, 8), (2026, 2), (2026, 8)]
    return st


def test_ingest_schreibt_je_plan_und_teilhaushalt_mit_herkunft(tmp_path):
    st = _store(tmp_path)
    assert st.budget_accounts_einheiten() == {(2019, 8), (2026, 2), (2026, 8)}
    assert not st.herkunft_luecken().get("council_budget_accounts")
    # Ein zweiter Lauf, der nur Fehlendes liest, schreibt nichts.
    zweiter = finanzquellen.lies_budget_accounts(st, finanzquellen.Protokoll(), nur_fehlende=True)
    assert zweiter["neue_einheiten"] == []
    st.close()


# ---------------------------------------------------------------------------
# Die Facette
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Wie hoch sind die Einnahmen durch die Parkgebühren im Jahr?",
    "Was gibt die Stadt für Straßenbeleuchtung aus?",
    "Wie viel kostet die Unterhaltung der Straßen?",
    "Wie hoch wären die Mehreinnahmen durch die letzte Parkgebührenerhöhung?",
])
def test_zieht(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    "Wie ist der Stand beim Stadion?",
    "Was ist am Fliegerhorst geplant?",
    "Wie viele Anträge stellen die Fraktionen?",
    "Wie viele Bürgerinnen und Bürger hat Oldenburg?",
])
def test_zieht_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def test_parkgebuehren_ist_ansatz_und_soll_ist(tmp_path):
    st = _store(tmp_path)
    d = st.budget_accounts_context(["Parkgebühren"])
    erstes = d["accounts"][0]
    assert erstes["label"] == "Parkgebühren" and erstes["account_no"] == "33211000"
    assert erstes["actual"][2024] == pytest.approx(4482612.19)
    assert erstes["actual"][2017] == pytest.approx(3362532.01)
    # Ansatz 2025: der fortgeschriebene Vorjahresansatz aus dem Plan 2026.
    assert erstes["budget"][2025] == [4394100, "adopted"]
    assert erstes["budget"][2026] == [4394100, "draft"]
    assert erstes["planning"] == {2027: 5228979, 2028: 5228979, 2029: 5228979}
    text = accounts.block(d)
    assert "Parkgebühren (Konto 33211000, Teilhaushalt 08 Verkehr und Straßenbau" in text
    assert "Ist (Rechnungsergebnis) 2017–2024: 2017: 3,4 Mio. €" in text
    assert "2024: 4,5 Mio. €" in text and "2026: 4,4 Mio. € (Entwurf)" in text
    assert "Finanzplanung 2027–2029 (Plan 2026)" in text
    assert "nie auf sie ausweichen" in text and "Beleg:" in text
    st.close()


def test_gattungswort_waehlt_kein_konto(tmp_path):
    """„Einnahmen", „Gebühren", „sonstige" stehen in der Frage und in vielen
    Kontennamen — sie wählen nichts aus."""
    st = _store(tmp_path)
    assert st.budget_accounts_context(["Einnahmen", "Gebühren", "sonstige", "Haushalt"]) is None
    st.close()


def test_teilwort_tritt_hinter_fachquelle_zurueck(tmp_path, monkeypatch):
    """„Schulden" trifft „Schuldendiensthilfen" nur als Wortteil. Hat die
    Schuldenquelle geantwortet, fällt der Kontenbaustein weg."""
    st = _store(tmp_path)
    monkeypatch.setattr(st, "budget_accounts_context",
                        lambda terms, year=None: {"accounts": [{"label": "x"}], "match": 1},
                        raising=False)
    monkeypatch.setattr(st, "schulden_kontext", lambda **kw: {"year": 2025}, raising=False)
    g = qa.geld_kontext(st, "Wie viele Schulden hat die Stadt?", "", "money")
    assert "accounts" not in g
    st.close()


def test_kontentreffer_verdraengt_steuern_und_grafik_zeigt_das_konto(tmp_path):
    """Die echte Frage vom 10.10.2026 — Soll und Ist bei den Parkgebühren
    bekam den Steuerplan (Gewerbesteuer) und die Grafik „Steuereinnahmen
    insgesamt"."""
    st = _store(tmp_path)
    frage = ("Wie hoch sind die Abweichungen zwischen den geplanten Soll-Einnahmen und den "
             "tatsächlichen Ist-Einnahmen bei den Parkgebühren in Oldenburg?")
    g = qa.geld_kontext(st, frage, frage, "money")
    assert g.get("accounts")
    for weg in ("taxes", "tax_plan", "kassensicht", "ist", "ansatz"):
        assert weg not in g, weg
    grafik = qa.geld_grafik(st, g)
    assert grafik["kind"] == "budget_account"
    assert grafik["title"] == "Parkgebühren — Einnahmen (Ist)"
    assert grafik["series"][-1] == {"year": 2024, "value": 4.48}
    st.close()


def test_parkgebuehren_ziehen_keine_abfallkalkulation(tmp_path):
    """„Parkgebühren" ist ein Kompositum mit fremdem Gegenstand — die
    Gebührenbedarfsberechnung (Abfall, Straßenreinigung) gehört nicht dazu."""
    st = CouncilStore(tmp_path / "c.sqlite")
    assert st.gebuehren_fuer_begriffe(["Parkgebühren"]) is None
    st.close()


def test_finanzielle_auswirkungen_der_vorlage_stehen_im_kontext():
    """Die Zahl, die am 10.10.2026 fehlte: „Mehreinnahmen von rd. 1.100.000
    Euro jährlich" steht in Vorlage 23/0101 NUR im Abschnitt „Finanzielle
    Auswirkungen" — der Router legt ihn bei Geldfragen dazu."""
    text = qa._build_context([{
        "id": 18022, "title": "Änderung der Parkgebühren", "committee": "Rat",
        "session_date": "2023-02-27", "outcome": "accepted",
        "official_text": "Die Gebühren für Kurzzeitparken werden stufenweise erhöht.",
        "vorlage_finanzen": "könnten Mehreinnahmen von rd. 1.100.000 Euro jährlich erzielt werden"}])
    assert "Finanzielle Auswirkungen laut Vorlage: könnten Mehreinnahmen von rd. 1.100.000" in text


def test_vorlagentext_nur_bekannte_spalten(tmp_path):
    st = CouncilStore(tmp_path / "c.sqlite")
    with pytest.raises(ValueError):
        st.vorlage_texts_for(["23/0101"], "raw_text; DROP TABLE x")
    st.close()
