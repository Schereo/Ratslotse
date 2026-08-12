"""Tagesordnungs-Diff für die Änderungs-Meldung (Tims Wunsch 12.08.):
nur die Unterschiede, grün/gelb/rot — und ein Einschub darf nicht die halbe
Liste gelb färben, nur weil sich Nummern verschieben."""
from __future__ import annotations

from council.agenda_diff import diff_html, diff_tagesordnung, hat_aenderungen


def _i(nr: str, titel: str) -> dict:
    return {"item_number": nr, "title": titel, "vorlage_nr": ""}


def test_einschub_verschiebt_nur_nummern():
    alt = [_i("Ö 5", "Baumschutzsatzung"), _i("Ö 6", "Regentonnen")]
    neu = [_i("Ö 5", "Baumschutzsatzung"), _i("Ö 6", "Rattenbefall"), _i("Ö 7", "Regentonnen")]
    d = diff_tagesordnung(alt, neu)
    assert [i["title"] for i in d["neu"]] == ["Rattenbefall"]
    assert [(a["item_number"], n["item_number"]) for a, n in d["verschoben"]] == [("Ö 6", "Ö 7")]
    assert d["entfernt"] == [] and d["umformuliert"] == []


def test_umformulierung_und_entfernung():
    alt = [_i("Ö 5", "Sachstand EU-Verordnung"), _i("Ö 6", "Aktionswochen")]
    neu = [_i("Ö 5", "Sachstandsbericht zur EU-Wiederherstellungsverordnung")]
    d = diff_tagesordnung(alt, neu)
    assert [(a["title"], n["title"]) for a, n in d["umformuliert"]] == [
        ("Sachstand EU-Verordnung", "Sachstandsbericht zur EU-Wiederherstellungsverordnung")]
    assert [i["title"] for i in d["entfernt"]] == ["Aktionswochen"]
    assert hat_aenderungen(d)


def test_identisch_ist_leer_und_html_faerbt():
    items = [_i("Ö 5", "Baumschutzsatzung")]
    d = diff_tagesordnung(items, list(items))
    assert not hat_aenderungen(d) and diff_html(d) == ""

    d2 = diff_tagesordnung([], [_i("Ö 9", "Windkraft <Bornhorst>")])
    html = diff_html(d2)
    assert "Neu · TOP Ö 9" in html and "&lt;Bornhorst&gt;" in html
    assert "#2f9e44" in html  # grüner Balken


def test_snapshot_roundtrip(tmp_path):
    from council.store import CouncilStore
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        items = [_i("Ö 5", "Baumschutzsatzung"), _i("Ö 6", "Regentonnen")]
        store.save_agenda_snapshot(4666, "hash-a", items)
        store.save_agenda_snapshot(4666, "hash-a", [_i("Ö 9", "anderes")])  # ignoriert
        assert store.get_agenda_snapshot(4666, "hash-a") == items
        assert store.get_agenda_snapshot(4666, "unbekannt") is None
    finally:
        store.close()
