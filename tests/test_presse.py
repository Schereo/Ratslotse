"""Stadt-Pressemitteilungen (council/presse.py + Store + QA-Kontext).

Parser laufen gegen eingebettete Fixture-Schnipsel — kein Netz.
"""
import json

import pytest

from council import presse, qa
from council.store import CouncilStore

_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
  <item>
    <guid isPermaLink="false">news-34614</guid>
    <title>Kommunalwahl: Jetzt startet die Briefwahl</title>
    <link>https://www.oldenburg.de/metanavigation/presse/pressemitteilung/news/briefwahl.html</link>
    <pubDate>Fri, 07 Aug 2026 17:13:15 +0200</pubDate>
  </item>
  <item>
    <guid isPermaLink="false">news-34600</guid>
    <title>Mehr Grün für den Bahnhofsvorplatz</title>
    <link>/metanavigation/presse/pressemitteilung/news/bahnhof.html</link>
    <pubDate>Wed, 05 Aug 2026 09:00:00 +0200</pubDate>
  </item>
</channel></rss>"""


def test_feed_parst_items(monkeypatch):
    class R:
        text = _RSS
        def raise_for_status(self): pass
    monkeypatch.setattr(presse._session, "get", lambda *a, **k: R())
    items = presse.fetch_feed()
    assert len(items) == 2
    assert items[0]["news_id"] == 34614
    assert items[0]["datum"] == "2026-08-07"
    assert items[1]["url"].startswith("https://www.oldenburg.de/")


_DETAIL = """<html><head>
<meta property="og:title" content="Mehr Grün für den Bahnhofsvorplatz">
<script type="application/ld+json">{"@type":"NewsArticle","datePublished" : "2026-08-05"}</script>
</head><body>
<h1 class="headline-title">Pressemitteilung</h1>
<div class="news-text-wrap"><p>Oldenburg. Nach dem Ende der Stadtgärten ziehen Dutzende
Wanderbäume zum Hauptbahnhof. Die Stadt begrünt den Vorplatz dauerhaft.</p></div>
</body></html>"""


def test_detail_nimmt_ogtitle_und_jsonld_datum(monkeypatch):
    class R:
        text = _DETAIL
        status_code = 200
        def raise_for_status(self): pass
    monkeypatch.setattr(presse, "_DELAY", 0)
    monkeypatch.setattr(presse._session, "get", lambda *a, **k: R())
    d = presse.fetch_detail("https://example.invalid/pm.html")
    assert d["titel"] == "Mehr Grün für den Bahnhofsvorplatz"
    assert d["datum"] == "2026-08-05"
    assert "Wanderbäume" in d["text"]


def test_detail_ohne_textkoerper_ist_none(monkeypatch):
    class R:
        text = "<html><body><p>nur Navigation</p></body></html>"
        status_code = 200
        def raise_for_status(self): pass
    monkeypatch.setattr(presse, "_DELAY", 0)
    monkeypatch.setattr(presse._session, "get", lambda *a, **k: R())
    assert presse.fetch_detail("https://example.invalid/x.html") is None


def test_store_upsert_und_fts(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    pid = store.save_presse("https://x/пm1.html", 1, "Radweg eröffnet",
                            "2026-08-01", "Die Stadt eröffnet den Radweg an der Alexanderstraße.")
    # Upsert: gleiche URL überschreibt, gleiche id.
    assert store.save_presse("https://x/пm1.html", 1, "Radweg eröffnet (aktualisiert)",
                             "2026-08-01", "Die Stadt eröffnet den Radweg an der Alexanderstraße feierlich.") == pid
    hits = store.search_presse_fts("Radweg Alexanderstrasse")
    assert hits and hits[0][0] == pid
    rows = store.presse_by_ids([pid])
    assert rows[0]["titel"].endswith("(aktualisiert)")
    missing = store.presse_missing_embeddings()
    assert [m["id"] for m in missing] == [pid]
    store.replace_presse_embeddings(pid, missing[0]["text_hash"], [("chunk", b"\x00\x00\x80?")])
    assert store.presse_missing_embeddings() == []  # hash-idempotent
    store.close()


def test_presse_block_im_antwortprompt():
    messages, _ = qa._answer_messages(
        "Was wurde aus dem Radweg?", [],
        presse=[{"titel": "Radweg eröffnet", "datum": "2026-08-01", "auszug": "Die Stadt eröffnet…"}])
    inhalt = messages[0]["content"]
    assert "AKTUELLES VON DER STADT" in inhalt
    assert "Radweg eröffnet" in inhalt
    # Ohne Presse-Treffer taucht der Block gar nicht auf.
    messages, _ = qa._answer_messages("Frage?", [])
    assert "AKTUELLES VON DER STADT" not in messages[0]["content"]


def test_presse_chunks_fenster():
    from council import embeddings
    text = "Wort " * 800  # ~4000 Zeichen
    chunks = embeddings.presse_chunks(text)
    assert 2 <= len(chunks) <= embeddings.PRESSE_MAX_CHUNKS
    assert all(len(c) <= embeddings.PRESSE_CHUNK_SIZE for c in chunks)
    assert embeddings.presse_chunks("") == []


# ---- Stufe 3b: Planungsbeteiligung ------------------------------------------

_PLANFAELLE = """<main><section class='articles'>
<article><section><h3>Bebauungsplan 831 &amp; Änd. 82 Flächennutzungsplan</h3>
<p>Stadion Maastrichter Straße</p><p><strong>Abwägungsergebnis der eingegangenen Stellungnahmen</strong></p>
<nav class='level'><a href='../PLANUNGSUNTERLAGEN/list.asp?PTID=1&amp;PFID=580'>Planungsunterlagen</a></nav>
</section></article>
<article><section><h3>Vorhabenbezogener Bebauungsplan 81</h3><p>Sandkruger Straße</p>
<p><strong>Beteiligung der Öffentlichkeit gemäß § 3 (2) BauGB</strong></p>
<nav class='level'><a href='../PLANUNGSUNTERLAGEN/list.asp?PTID=1&amp;PFID=573'>Planungsunterlagen</a></nav>
</section><section class='periods'><div>Zeitraum der Beteiligung der Öffentlichkeit</div>
<div>06.07.2026&#160;bis&#160;17.08.2026</div></section></article>
</section></main>"""


def test_planfaelle_parser(monkeypatch):
    from council import beteiligung
    class R:
        text = _PLANFAELLE
        def raise_for_status(self): pass
    monkeypatch.setattr(beteiligung._session, "get", lambda *a, **k: R())
    faelle = beteiligung.fetch_planfaelle()
    assert len(faelle) == 2
    assert faelle[0]["plan_nrs"] == ["bp-831", "fnp-82"]
    assert faelle[0]["bis"] is None  # Abwägungsschritt ohne Zeitraum
    assert faelle[1]["plan_nrs"] == ["bp-81"]
    assert faelle[1]["von"] == "2026-07-06" and faelle[1]["bis"] == "2026-08-17"
    assert faelle[1]["url"].startswith("https://oldenburg.planungsbeteiligung.de/FRONTEND/")


def test_plan_nummern_matching_ohne_fehlgriffe():
    from council.beteiligung import passt_zu_titel, plan_nummern
    assert plan_nummern("82. Änderung des Flächennutzungsplans") == ["fnp-82"]
    # 81 matcht NICHT 831 und keine Geldbeträge:
    assert passt_zu_titel(["bp-81"], "Bebauungsplan 831 Stadion — Satzungsbeschluss") is False
    assert passt_zu_titel(["bp-81"], "Zuschuss von 81.000 € für den Sportverein") is False
    assert passt_zu_titel(["bp-81"], "Vorhabenbezogener Bebauungsplan 81 (Sandkruger Straße) — Entwurf") is True
    assert passt_zu_titel(["bp-831", "fnp-82"], "Bebauungsplan 831 — Abwägung") is True


def test_beteiligung_store_roundtrip(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    stat = store.save_beteiligungen([{"titel": "Bebauungsplan 831", "ort": "Stadion",
                                      "schritt": "Abwägung", "von": None, "bis": None,
                                      "url": "https://x", "plan_nrs": ["bp-831"]}])
    assert stat["neu"] == 1 and stat["laufend"] == 1
    rows = store.list_beteiligungen()
    assert rows[0]["plan_nrs"] == ["bp-831"]
    # Zweiter Lauf: aus der Portal-Liste verschwunden — die Zeile wird als
    # beendet markiert, aber NICHT gelöscht (die Stadt löscht, wir nicht;
    # sonst wäre das Verfahren nirgends mehr dokumentiert).
    stat2 = store.save_beteiligungen([])
    assert stat2["beendet"] == 1
    assert store.list_beteiligungen() == []
    historie = store.list_beteiligungen(nur_laufende=False)
    assert len(historie) == 1 and historie[0]["status"] == "beendet"
    store.close()


def test_kontext_zeigt_beteiligung():
    ctx = qa._build_context([{"id": 1, "title": "Bebauungsplan 81",
                              "beteiligung": "Öffentliche Auslegung bis 2026-08-17"}])
    assert "BÜRGERBETEILIGUNG LÄUFT" in ctx
