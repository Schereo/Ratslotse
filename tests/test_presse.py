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
