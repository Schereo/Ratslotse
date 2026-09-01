"""Beteiligungen werden fortgeschrieben statt ersetzt (13.08.2026).

Das Portal der Stadt zeigt ausschließlich Verfahren, zu denen GERADE eine
Beteiligung möglich ist; abgeschlossene sind dort spurlos weg (geprüft: ältere
Planfall-IDs liefern nur noch eine leere Hülle). Wer die Zeile beim nächsten
Lauf löscht, verliert sie für immer — deshalb hier: markieren, nicht löschen.
"""
from council.store import CouncilStore


def _row(title, url, schritt="Auslegung", bis="2026-08-17"):
    return {"title": title, "ort": "Ort", "schritt": schritt, "valid_from": "2026-07-06",
            "valid_until": bis, "url": url, "plan_nrs": ["bp-81"]}


def test_verschwundene_beteiligung_wird_beendet_statt_geloescht(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        s1 = store.save_beteiligungen([_row("B-Plan 81", "https://x/81"),
                                       _row("B-Plan 831", "https://x/831")])
        assert (s1["neu"], s1["beendet"]) == (2, 0)
        assert len(store.list_beteiligungen()) == 2

        # Nächster Lauf: nur noch eine steht im Portal.
        s2 = store.save_beteiligungen([_row("B-Plan 81", "https://x/81")])
        assert (s2["neu"], s2["aktualisiert"], s2["beendet"]) == (0, 1, 1)

        laufend = store.list_beteiligungen()
        assert [b["title"] for b in laufend] == ["B-Plan 81"]
        alle = store.list_beteiligungen(nur_laufende=False)
        assert len(alle) == 2                      # nichts verloren
        beendet = [b for b in alle if b["status"] == "beendet"]
        assert beendet[0]["title"] == "B-Plan 831" and beendet[0]["beendet_am"]
    finally:
        store.close()


def test_wiederauftauchen_setzt_status_zurueck(tmp_path):
    """Ein Verfahren kann in einen neuen Schritt gehen und wieder auftauchen —
    dann ist es wieder laufend, ohne Dublette."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_beteiligungen([_row("B-Plan 81", "https://x/81")])
        store.save_beteiligungen([])                       # Portal leer
        assert store.list_beteiligungen() == []
        s = store.save_beteiligungen([_row("B-Plan 81", "https://x/81", bis="2026-09-30")])
        assert (s["neu"], s["aktualisiert"]) == (0, 1)     # kein zweiter Eintrag
        laufend = store.list_beteiligungen()
        assert len(laufend) == 1 and laufend[0]["valid_until"] == "2026-09-30"
        assert len(store.list_beteiligungen(nur_laufende=False)) == 1
    finally:
        store.close()


def test_neuer_schritt_ist_ein_eigener_eintrag(tmp_path):
    """Auslegung → Abwägungsergebnis: zwei Stationen desselben Plans, beide
    bleiben dokumentiert (der Schritt gehört zum Schlüssel)."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store.save_beteiligungen([_row("B-Plan 81", "https://x/81", schritt="Auslegung")])
        s = store.save_beteiligungen([_row("B-Plan 81", "https://x/81",
                                           schritt="Abwägungsergebnis", bis=None)])
        assert s["neu"] == 1 and s["beendet"] == 1
        alle = store.list_beteiligungen(nur_laufende=False)
        assert {b["schritt"] for b in alle} == {"Auslegung", "Abwägungsergebnis"}
    finally:
        store.close()
