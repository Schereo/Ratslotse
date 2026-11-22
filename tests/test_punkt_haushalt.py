"""Der Kasten „Im Haushalt" der Punkt-Seite (``council/punkt_haushalt.py``):
zugeordnet wird nur, was die Vorlage ausdrücklich nennt — lieber nichts als
etwas Falsches. Jede Regel hier stammt aus der Prüfung an 59 echten Punkten
(13.11.2026)."""
import pytest

from council import punkt_haushalt as ph
from council.store import CouncilStore

JETZT = "2026-11-13T00:00:00"


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(str(tmp_path / "c.sqlite"))
    c = s._conn  # noqa: SLF001 — Testdaten
    with c:
        c.execute("INSERT INTO council_provenance (id, key, kind, label, url, probe, as_of, fetched_at) "
                  "VALUES (1, 'k1', 'budget', 'Beschlossener Haushaltsplan 2025', 'https://example.org/hh25.pdf', '[]', '2025', ?)", (JETZT,))
        for jahr, th5, th4_aufwand, th4_ertrag in ((2024, 56.0e6, 95e6, 500e6), (2025, 60.2e6, 98e6, 515e6), (2026, 65.4e6, 100.7e6, 529.3e6)):
            c.execute("INSERT INTO council_budget (year, area, revenues, expenses, is_total, fetched_at, herkunft_id) VALUES (?,?,?,?,0,?,1)",
                      (jahr, "Sicherheit und Ordnung", 30e6, th5, JETZT))
            c.execute("INSERT INTO council_budget (year, area, revenues, expenses, is_total, fetched_at, herkunft_id) VALUES (?,?,?,?,0,?,1)",
                      (jahr, "Finanzmanagement und Recht", th4_ertrag, th4_aufwand, JETZT))
            c.execute("INSERT INTO council_budget (year, area, revenues, expenses, is_total, fetched_at, herkunft_id) VALUES (?,?,?,?,1,?,1)",
                      (jahr, "Summe", 800e6, 880e6, JETZT))
            for nr, name, pno, pname in ((5, "Sicherheit und Ordnung", "P10.127000", "Rettungsdienst"),
                                         (4, "Finanzmanagement und Recht", "P10.111003", "Allgemeine Finanzwirtschaft")):
                c.execute("INSERT INTO council_products (year, product_no, product_name, sub_budget_no, sub_budget_name, revenues, expenses, "
                          "short_description, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,1)",
                          (jahr, pno, pname, nr, name, 1e6, 12e6, "Notfallrettung und Krankentransport.", JETZT))
            for kennung, name, erg in (("stadion", "Stadion Oldenburg GmbH & Co. KG", -1.0), ("stadion_planung", "Stadionplanungsgesellschaft mbH", -9.0)):
                c.execute("INSERT INTO council_business_plans (enterprise, year, enterprise_name, template_number, revenues, expenses, result, "
                          "probes, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,'[]',1,?)", (kennung, jahr, name, "x", 5.0, 6.0, erg, JETZT))
        for jahr, satz in ((2011, 430), (2015, 445), (2025, 539)):
            c.execute("INSERT INTO council_tax_rates (year, kind, rate, herkunft_id, fetched_at) VALUES (?, 'Grundsteuer B', ?, 1, ?)", (jahr, satz, JETZT))
        for jahr, satz in ((2011, 430), (2015, 439), (2025, 439)):
            c.execute("INSERT INTO council_tax_rates (year, kind, rate, herkunft_id, fetched_at) VALUES (?, 'Gewerbesteuer', ?, 1, ?)", (jahr, satz, JETZT))
        for jahr in (2023, 2024, 2025):
            c.execute("INSERT INTO council_taxes (year, kind, amount, fetched_at, herkunft_id) VALUES (?, 'Grundsteuer A+B', 33e6, ?, 1)", (jahr, JETZT))
            c.execute("INSERT INTO council_debt (year, total, per_capita, revised, herkunft_id, fetched_at) VALUES (?, 300e6, 1700, 0, 1, ?)", (jahr, JETZT))
    yield s
    s.close()


def _kontext(store, titel, vorschlag="", datum="2025-12-01"):
    return ph.item_budget_context(store, {"item": {"title": titel}, "session_date": datum}, {"proposed_decision": vorschlag})


def _keys(k):
    return [b["key"] for b in (k or {}).get("blocks", [])]


def test_nachbewilligung_zeigt_den_teilhaushalt_mit_anteil_und_nur_aufwendungen(store):
    k = _kontext(store, "Überplanmäßige Bewilligung von Mehraufwendungen in Höhe von 481.300 Euro für den Rettungsdienst - Beschluss",
                 "Für das Budget des Rettungsdienstes (Budget 23.1) im Teilhaushalt 05 werden zusätzliche Haushaltsmittel in Höhe von "
                 "481.300 Euro bewilligt. Der Mehrbedarf wird durch Mehrerträge bei der Gewerbesteuer (Budget 20.3) im Teilhaushalt 04 gedeckt.")
    assert _keys(k) == ["sub_budget:5"]          # nicht Teilhaushalt 04 — das ist die Deckung
    b = k["blocks"][0]
    assert b["title"] == "Teilhaushalt 05 · Sicherheit und Ordnung" and b["basis"] == "plan"
    assert b["columns"] == ["Aufwendungen"]       # die Erträge daneben führten in die Irre
    assert [r["year"] for r in b["rows"]] == [2024, 2025, 2026]
    # Anteil am Ansatz des Sitzungsjahrs, exakt (die Seite rundet einmal)
    assert b["share"]["year"] == 2025 and b["share"]["percent"] == pytest.approx(481300 / 60.2e6 * 100)
    assert b["sources"] == [{"label": "Beschlossener Haushaltsplan 2025", "year": 2025, "url": "https://example.org/hh25.pdf"}]


def test_investive_mehrauszahlung_bekommt_keinen_teilhaushalt(store):
    """Investition gegen laufende Aufwendungen: zwei Töpfe."""
    k = _kontext(store, "Überplanmäßige Bewilligung einer Mehrauszahlung in Höhe von 65.000 Euro für einen Einsatzleitwagen",
                 "Für das Budget des Rettungsdienstes im Teilhaushalt 05 wird eine überplanmäßige Mehrauszahlung bewilligt.")
    assert k is None


def test_produkt_aus_dem_deckungssatz_zaehlt_nicht(store):
    k = _kontext(store, "Mehr Geld für den Rettungsdienst",
                 "Beim Produkt P10.127000 werden Mittel bereitgestellt. Zur Deckung stehen Mehrerträge beim Produkt P10.111003 zur Verfügung.")
    assert _keys(k) == ["product:P10.127000"]
    assert k["blocks"][0]["description"] == "Notfallrettung und Krankentransport."


def test_betrieb_nur_mit_finanzwort_und_genau_dieser_betrieb(store):
    assert _kontext(store, "Sitzungstermine 2026 - Stadion Oldenburg GmbH & Co. KG") is None
    k = _kontext(store, "Stadion Oldenburg GmbH & Co. KG: Wirtschaftsplan 2026 - Beschluss")
    assert _keys(k) == ["enterprise:stadion"]
    b = k["blocks"][0]
    # nicht die Stadionplanungsgesellschaft, die der Name „Stadion" auch träfe
    assert b["title"] == "Stadion Oldenburg GmbH & Co. KG" and b["rows"][-1]["values"][2] == -1.0


def test_hebesatzsatzung_zeigt_beide_saetze_ohne_wiederholte_zeile(store):
    k = _kontext(store, "Satzung über die Festsetzung der Realsteuerhebesätze für die Grundsteuer A und B - Beschluss", datum="2025-12-15")
    assert _keys(k) == ["series:hebesatz_grundsteuer_b", "series:hebesatz_gewerbesteuer", "series:grundsteuer"]
    gewerbe = k["blocks"][1]
    assert gewerbe["basis"] == "rate" and gewerbe["unit"] == "percent"
    assert [(r["year"], r["values"][0]) for r in gewerbe["rows"]] == [(2011, 430), (2015, 439)]   # 2025 wiederholte 439 nur
    assert k["blocks"][2]["basis"] == "actual"   # Einnahmen sind Ist — nie in einer Reihe mit Plan


def test_grundsteuer_c_bekommt_satz_und_einnahmen(store):
    k = _kontext(store, "Einführung einer Grundsteuer C zur Bekämpfung von Bodenspekulation (BSW-Fraktion) - Beschlussantrag", datum="2026-10-26")
    assert _keys(k) == ["series:hebesatz_grundsteuer_b", "series:grundsteuer"]


def test_haushalt_als_ganzes_aber_nicht_ein_teil_oder_sein_zeitplan(store):
    assert _keys(_kontext(store, "Haushalt 2026 - Verwaltungsentwurf -Bericht Beschluss: zur Kenntnis genommen")) == ["budget:total"]
    assert _kontext(store, "Haushalt 2026 - Verwaltungsentwurf - Rechtsfähige Stiftungen") is None
    assert _kontext(store, "Zeitplan Aufstellung Haushaltsplan 2027") is None


def test_teilhaushalt_ueber_den_namen(store):
    k = _kontext(store, "Haushalt 2026 - Verwaltungsentwurf - Teilhaushalt Sicherheit und Ordnung - Bericht")
    assert _keys(k) == ["sub_budget:5"]
    assert k["blocks"][0]["columns"] == ["Aufwendungen", "Erträge"]   # beim Entwurf gehören die Erträge dazu
    assert k["blocks"][0]["share"] is None


def test_schulden_und_gewoehnlicher_punkt(store):
    assert _keys(_kontext(store, "Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen")) \
        == ["series:schulden", "series:schulden_je_einwohner"]
    assert _kontext(store, "Bebauungsplan 871 (Etzhorner Weg) - Aufstellungsbeschluss") is None
    assert _kontext(store, "Bericht", datum="") is None
