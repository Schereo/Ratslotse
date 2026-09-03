"""Die Facette `amendments` — was in den Änderungslisten steht."""
import os

import pytest

from council import qa
from council.geld import amendments
from council.store import CouncilStore

NAME = amendments.NAME

ZIEHT = [
    "Was änderte die Verwaltung noch am Haushaltsentwurf 2026?",
    "Wie kam der Haushalt 2026 vom Entwurf zum Beschluss?",
    "Welche Änderungslisten gab es zum Haushalt 2026?",
    "Wer wollte den Haushalt 2024 ändern?",
    "Was hat die Steuerschätzung am Haushalt 2026 verändert?",
]
ZIEHT_NICHT = [
    "Was wurde zum Radweg beschlossen?",
    "Wie lief die Debatte um das Stadion?",
    "Wie ist der Stand beim Stadion?",
    "Wer ist Oberbürgermeister von Oldenburg?",
    "Was steht im Bebauungsplan-Entwurf für den Fliegerhorst?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_zieht(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_zieht_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def test_dockt_an_antraege_an():
    f = qa.geld_facetten("Wer wollte den Haushalt 2024 ändern?", "topic")
    assert {"antraege", NAME} <= f


def _store(tmp_path) -> CouncilStore:
    st = CouncilStore(tmp_path / "c.sqlite")
    with st._conn:
        st._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            " as_of, fetched_at) VALUES (1, 'k', 'ris', 'Änderungslisten Haushalt 2026', "
            " 'https://example.org/al', 'Beschluss-Datei des AFB', 'p', '2026', '2026-09-02')")
        summen = [
            ("administration_1", "draft", "Verwaltungsentwurf", 792.4, 881.7, -89.3, 0),
            ("administration_1", "list", "Änderungsliste Verw. I", 19.5, 2.8, 16.6, 1),
            ("administration_1", "final_total", "Überschuss/ Fehlbedarf", 811.9, 884.5, -72.7, 0),
            ("fc_decided", "draft", "Verwaltungsentwurf", 792.4, 881.7, -89.3, 0),
            ("fc_decided", "final_total", "Überschuss/ Fehlbedarf:", 815.0, 883.7, -68.7, 0),
        ]
        for key, kind, label, e, a, s, own in summen:
            st._conn.execute(
                "INSERT INTO council_budget_amendments_totals (budget_year, list_key, year, kind, "
                " label, revenues, expenses, balance, own, document_id, herkunft_id, fetched_at) "
                "VALUES (2026,?,2026,?,?,?,?,?,?,1,1,'')", (key, kind, label, e * 1e6, a * 1e6, s * 1e6, own))
        pos = [
            ("fc_decided", 1, 4, "Allgemeine Finanzwirtschaft", 18_410_747.0, None,
             "Das Landesamt hat die vorläufige Steuerkraft mitgeteilt.", None),
            ("fc_decided", 2, 11, "Kindertagesstätten Betriebskosten", None, 2_400_000.0,
             "Mehr Plätze im Krippenbereich.", None),
            ("fc_decided", 3, 6, "Museum Zuschuss", None, 150_000.0, None, None),
            ("administration_1", 1, 4, "Allgemeine Finanzwirtschaft", 12_228_500.0, None,
             "November-Steuerschätzung.", None),
        ]
        for key, seq, thh, label, rev, exp, erkl, author in pos:
            st._conn.execute(
                "INSERT INTO council_budget_amendments (budget_year, list_key, year, seq, sub_budget, "
                " product, label, revenue, expense, explanation, author, document_id, herkunft_id, "
                " fetched_at) VALUES (2026,?,2026,?,?,NULL,?,?,?,?,?,1,1,'')",
                (key, seq, thh, label, rev, exp, erkl, author))
        # 2021: die eine Beschluss-Datei mit „Vorschlag von"
        st._conn.execute(
            "INSERT INTO council_budget_amendments_totals (budget_year, list_key, year, kind, "
            " label, revenues, expenses, balance, own, document_id, herkunft_id, fetched_at) "
            "VALUES (2021,'fc_decided',2021,'final_total','Überschuss/ Fehlbedarf:',700e6,688.4e6,11.6e6,0,2,1,'')")
        st._conn.execute(
            "INSERT INTO council_budget_amendments (budget_year, list_key, year, seq, sub_budget, "
            " product, label, revenue, expense, explanation, author, document_id, herkunft_id, "
            " fetched_at) VALUES (2021,'fc_decided',2021,1,6,NULL,'Kulturförderung',NULL,300000,"
            " 'Mehr für die freie Szene.','SPD/ BÜNDNIS 90/ DIE GRÜNEN',2,1,'')")
    return st


def test_endstand_kommt_aus_dem_juengsten_dokument(tmp_path):
    st = _store(tmp_path)
    d = st.amendments_context([], 2026)
    assert d["final_document"] == "fc_decided"
    assert d["final"]["balance"] == pytest.approx(-68.7e6)
    assert d["draft"]["balance"] == pytest.approx(-89.3e6)
    assert [s["label"] for s in d["lists"]] == ["Änderungsliste Verw. I"]
    # ohne Begriffe: die größten Positionen des Endstands, nicht der Verwaltungsliste
    assert [z["label"] for z in d["positions"]][0] == "Allgemeine Finanzwirtschaft"
    assert d["positions"][0]["revenue"] == pytest.approx(18_410_747.0)
    text = amendments.block(d)
    assert "Verwaltungsentwurf 2026" in text and "Saldo -68,7 Mio. €" in text
    assert "Nenne keine Fraktion als Urheber" in text
    assert "Beleg: Änderungslisten Haushalt 2026" in text
    st.close()


def test_begriffe_waehlen_die_position(tmp_path):
    st = _store(tmp_path)
    d = st.amendments_context(["Kita", "Krippe"], 2026)
    assert d["matched"] and d["positions"][0]["label"].startswith("Kindertagesstätten")
    assert "Positionen zur Frage" in amendments.block(d)
    st.close()


def test_urheber_nur_wo_die_quelle_sie_fuehrt(tmp_path):
    st = _store(tmp_path)
    d = st.amendments_context([], 2021)
    assert d["authors"] == [("SPD/ BÜNDNIS 90/ DIE GRÜNEN", 1)]
    text = amendments.block(d)
    assert "vorgeschlagen von SPD/ BÜNDNIS 90/ DIE GRÜNEN" in text
    assert "Nenne keine Fraktion" not in text
    st.close()


def test_fehlendes_jahr_faellt_mit_vermerk_zurueck(tmp_path):
    st = _store(tmp_path)
    d = st.amendments_context([], 2019)
    assert d["year"] == 2026 and d["year_asked"] == 2019
    st.close()


# ACHTUNG, warum NICHT `COUNCIL_DB`: Drei Testmodule setzen diese Variable
# beim Import auf eine Wegwerf-Datenbank (`test_backend_api`, `test_live_window`,
# `test_social_api`). In einem vollständigen Lauf ist sie also IMMER gesetzt —
# die Bedingung übersprang dann nichts, und der Test lief gegen eine leere oder
# längst weggeräumte Datei („unable to open database file", roter Lauf auf dev
# am 02.09.2026). Ein eigener Name ist das einzige verlässliche Ja.
@pytest.mark.skipif(not os.environ.get("COUNCIL_DB_ECHT"),
                    reason="echte Datenbank nur auf Ansage: COUNCIL_DB_ECHT=… setzen")
def test_groesse_an_der_echten_datenbank():
    from council import geld
    st = geld.lesestore(os.environ["COUNCIL_DB_ECHT"])
    for frage, terms in (("Welche Änderungslisten gab es zum Haushalt 2026?", ["Haushalt"]),
                         ("Was hat die Steuerschätzung am Haushalt 2026 verändert?", ["Steuerschätzung", "Steuern"]),
                         ("Wer wollte den Haushalt 2021 ändern?", ["Haushalt"])):
        d = st.amendments_context(terms, qa.haushaltsjahr(frage))
        text = amendments.block(d)
        assert text and len(text) <= amendments.FACETTE.grenze, (frage, len(text))
    st.close()


def _mit_finanzhaushalt(st):
    """Dazu die FHH-Listen 2026 — die Positionen sind Investitionen."""
    with st._conn:
        for key, kind, label, ein, aus, saldo, own in (
                ("administration_1", "draft", "Verwaltungsentwurf", 39.7, 80.8, -41.1, 0),
                ("administration_1", "list", "Änderungsliste Verw. I", 0.0, 0.6, -0.6, 1),
                ("administration_1", "final_total", "Summe", 39.7, 81.4, -41.7, 0)):
            st._conn.execute(
                "INSERT INTO council_budget_amendments_cash_totals (budget_year, list_key, year, kind, "
                "label, inflows, outflows, balance, commitment_authorizations, own, document_id, "
                "herkunft_id, fetched_at) VALUES (2026, ?, 2026, ?, ?, ?, ?, ?, 0, ?, 1, 1, '2026-09-02')",
                (key, kind, label, ein * 1e6, aus * 1e6, saldo * 1e6, own))
        for seq, label, product, ein, aus, erl in (
                (1, "Feuerwache Süd, Neubau", "I10.126001.500", 0, 400_000, "Bedarfsanpassung"),
                (2, "Radweg Alexanderstraße", "I10.541100.500", 0, 200_000, "Förderung eingeplant")):
            st._conn.execute(
                "INSERT INTO council_budget_amendments_cash (budget_year, list_key, year, seq, sub_budget, "
                "page_draft, product, label, planned_draft, inflow, outflow, commitment_authorizations, "
                "planned_new, explanation, author, document_id, herkunft_id, fetched_at) VALUES "
                "(2026, 'administration_1', 2026, ?, 5, '70', ?, ?, 0, ?, ?, 0, ?, ?, NULL, 1, 1, '2026-09-02')",
                (seq, product, label, ein, aus, aus, erl))
    return st


def test_finanzhaushalt_kommt_nur_auf_anfrage(tmp_path):
    """„Welche Änderungen am Finanzhaushalt?“ bekam bis 09/2026 nur den
    Ergebnishaushalt (live gemessen). Mit „Finanzhaushalt“ oder „Investition“
    in den Begriffen kommen die FHH-Listen dazu — ohne bleibt es beim EHH."""
    st = _mit_finanzhaushalt(_store(tmp_path))
    try:
        ohne = st.amendments_context(["haushalt", "verwaltung"], 2026)
        assert ohne["cash"] is None
        assert "FINANZHAUSHALT" not in amendments.block(ohne)
        mit = st.amendments_context(["finanzhaushalt", "feuerwache"], 2026)
        assert mit["cash"]["final"]["outflows"] == 81.4e6
        assert mit["cash"]["positions"][0]["label"] == "Feuerwache Süd, Neubau"
        text = amendments.block(mit)
        assert "FINANZHAUSHALT (Investitionen)" in text
        assert "Verwaltungsentwurf 2026: Einzahlungen 39,7 Mio. €, Auszahlungen 80,8 Mio. €" in text
        assert "Feuerwache Süd, Neubau (I10.126001.500): Auszahlungen 0,4 Mio. €" in text
    finally:
        st.close()
