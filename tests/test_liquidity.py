"""Der Liquiditätsstand — die Grafik als Zahlenreihe (council/liquidity.py).

Zwei echte Grafiken aus dem Bestand: „2022–2025" zum 31.08.2025 und
„2023–2026" zum 31.01.2026 — sie teilen sich die Jahrgänge 2023 bis 2025."""
import pytest

from council import herkunft as h, liquidity
from council.store import CouncilStore

G_2025 = "20\n202\nStand: 31.08.2025  01.09.2025\n108,1\n138,9\n126,4\n112,7\n135,7\n134,6\n110,5\n136,8\n128,3\n129,2\n142,2\n145,4\n128,7\n158,0\n166,8\n153,5\n164,1\n159,5\n170,1\n182,1\n147,8\n138,5\n158,5\n138,6\n124,0\n151,3\n136,1\n117,7\n146,1\n126,2\n124,3\n180,1\n158,2\n148,5\n146,4\n116,0\n105,0\n142,3\n123,8\n97,6\n136,0\n114,7\n103,9\n130,6\n-10,0\n0,0\n10,0\n20,0\n30,0\n40,0\n50,0\n60,0\n70,0\n80,0\n90,0\n100,0\n110,0\n120,0\n130,0\n140,0\n150,0\n160,0\n170,0\n180,0\n190,0\n200,0\nJanuar\nFebruar\nMärz\nApril\nMai\nJuni\nJuli\nAugust\nSeptember\nOktober\nNovember\nDezember\nin Mio. EUR\nMonatsendstand\nLiquiditätsstand zum Monatsende\n2022, 2023, 2024 und 2025  im Vergleich\n2022\n2023\n2024\n2025"
G_2026 = "20\n202\nStand: 31.01.2026  02.02.2026\n128,7\n158,0\n166,8\n153,5\n164,1\n159,5\n170,1\n182,1\n147,8\n138,5\n158,5\n138,6\n124,0\n151,3\n136,1\n117,7\n146,1\n126,2\n124,3\n180,1\n158,2\n148,5\n146,4\n116,0\n105,0\n142,3\n123,8\n97,6\n136,0\n114,7\n103,9\n130,6\n108,4\n95,6\n108,4\n108,0\n84,8\n-10,0\n0,0\n10,0\n20,0\n30,0\n40,0\n50,0\n60,0\n70,0\n80,0\n90,0\n100,0\n110,0\n120,0\n130,0\n140,0\n150,0\n160,0\n170,0\n180,0\n190,0\n200,0\nJanuar\nFebruar\nMärz\nApril\nMai\nJuni\nJuli\nAugust\nSeptember\nOktober\nNovember\nDezember\nin Mio. EUR\nMonatsendstand\nLiquiditätsstand zum Monatsende\n2023, 2024, 2025 und 2026  im Vergleich\n2023\n2024\n2025\n2026"


def _anlagen():
    return [{"template_number": "25/0588", "document_id": 296188, "label": "Liquiditätsstand 2022 - 2025 20250831",
             "url": "https://example.org/a", "raw_text": G_2025},
            {"template_number": "26/0115", "document_id": 300001, "label": "Liquiditätsstand 2023 - 2026 20260131",
             "url": "https://example.org/b", "raw_text": G_2026}]


def test_grafik_jahresweise_gelesen():
    g = liquidity.lies_grafik(G_2025, "Liquiditätsstand 2022 - 2025 20250831")
    assert g["as_of"] == "2025-08-31" and g["years"] == [2022, 2023, 2024, 2025]
    assert len(g["values"]) == 44
    assert g["values"]["2022-01"] == pytest.approx(108.1e6)
    assert g["values"]["2023-01"] == pytest.approx(128.7e6)
    assert g["values"]["2024-12"] == pytest.approx(116.0e6)
    assert g["values"]["2025-08"] == pytest.approx(130.6e6)
    assert "2025-09" not in g["values"]


def test_ueberlappung_bestaetigt_und_juengster_beleg_gewinnt():
    r = liquidity.lies(_anlagen())
    rows = {x["month"]: x for x in r["rows"]}
    assert len(rows) == 12 + 12 + 12 + 12 + 1 and not r["strittig"]
    assert rows["2023-01"]["confirmations"] == 2 and liquidity.UEBERLAPPUNG in rows["2023-01"]["probes"]
    assert rows["2023-01"]["template_number"] == "26/0115"      # jüngster Beleg
    assert rows["2022-01"]["confirmations"] == 1 and rows["2022-01"]["template_number"] == "25/0588"
    assert rows["2026-01"]["amount"] == pytest.approx(84.8e6)


def test_korrektur_juengster_wert_gilt_und_der_alte_reist_mit():
    a = _anlagen()
    a[1]["raw_text"] = a[1]["raw_text"].replace("128,7", "199,9", 1)
    r = liquidity.lies(a)
    assert [s["month"] for s in r["strittig"]] == ["2023-01"]
    m = next(x for x in r["rows"] if x["month"] == "2023-01")
    assert m["amount"] == pytest.approx(199.9e6) and m["revised_from"] == pytest.approx(128.7e6)
    assert liquidity.UEBERLAPPUNG not in m["probes"]
    assert "korrigiert" in liquidity.probennachweis(r)


def test_falsche_wertzahl_wird_nicht_gelesen():
    kaputt = G_2025.replace("130,6", "", 1)
    assert liquidity.lies_grafik(kaputt, "Liquiditätsstand 2022 - 2025") is None
    assert liquidity.lies_grafik("Bericht: siehe Grafik", "Anlage") is None


def test_store_rundlauf(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    r = liquidity.lies(_anlagen())
    lauf = h.Herkunft(kind="ris", url="https://example.org", label="Lauf", probe=[liquidity.WERTZAHL], probe_result="x")
    for row in r["rows"]:
        row["herkunft"] = h.Herkunft(kind="ris", document_id=row["document_id"], url=row["url"],
                                     label=f"Grafik {row['template_number']}", citation=liquidity.FUNDSTELLE,
                                     probe=row["probes"], probe_result="ok")
    assert store.save_liquidity(r["rows"], lauf) == 49
    reihe = store.get_liquidity()
    assert reihe[0]["month"] == "2022-01" and reihe[-1]["month"] == "2026-01"
    assert all(x["herkunft_id"] for x in reihe)
    assert (2026, 1) in store.liquidity_einheiten() and len(store.liquidity_einheiten()) == 49
    store.save_liquidity(r["rows"], lauf)
    assert len(store.get_liquidity()) == 49
    store.close()
