"""Tagesordnungs-Diff für die Änderungs-Meldung (Tims Wunsch 12.08.):
nur die Unterschiede, grün/gelb/rot — und ein Einschub darf nicht die halbe
Liste gelb färben, nur weil sich Nummern verschieben."""
from __future__ import annotations

from council.agenda_diff import diff_html, diff_tagesordnung, hat_aenderungen


def _i(nr: str, titel: str, vorlage: str = "") -> dict:
    return {"item_number": nr, "title": titel, "vorlage_nr": vorlage}


def test_nachgereichte_vorlage_ist_eine_aenderung():
    """Der echte Fall vom 17.08.2026 (Sitzung 4696): An „Ö 5" hing plötzlich
    die Vorlage 26/0019/9 — Nummer und Titel unverändert. Der Hash sprang, der
    Diff fand nichts, und die Mail sagte „Details einzelner Punkte wurden
    angepasst": eine Meldung ohne Information."""
    alt = [_i("Ö 5", "Beratung nichtöffentlicher TOPs - Bericht")]
    neu = [_i("Ö 5", "Beratung nichtöffentlicher TOPs - Bericht", "26/0019/9")]
    d = diff_tagesordnung(alt, neu)
    assert [(a["vorlage_nr"], n["vorlage_nr"]) for a, n in d["vorlage"]] == [("", "26/0019/9")]
    assert d["neu"] == [] and d["entfernt"] == [] and d["verschoben"] == []
    assert hat_aenderungen(d)
    html = diff_html(d)
    assert "Vorlage nachgereicht · TOP Ö 5" in html and "26/0019/9" in html


def test_zurueckgezogene_und_getauschte_vorlage():
    d = diff_tagesordnung([_i("Ö 5", "Radweg", "26/0100")], [_i("Ö 5", "Radweg")])
    assert "Vorlage zurückgezogen · TOP Ö 5" in diff_html(d)

    d = diff_tagesordnung([_i("Ö 5", "Radweg", "26/0100")], [_i("Ö 5", "Radweg", "26/0100/1")])
    html = diff_html(d)
    assert "Andere Vorlage · TOP Ö 5" in html and "26/0100 → 26/0100/1" in html


def test_verschoben_schlaegt_vorlage():
    """Ein Punkt, der wandert UND eine Vorlage bekommt, steht einmal in der
    Liste — als Verschiebung, nicht zweimal."""
    d = diff_tagesordnung([_i("Ö 5", "Radweg")], [_i("Ö 7", "Radweg", "26/0100")])
    assert len(d["verschoben"]) == 1 and d["vorlage"] == []


def test_nichtoeffentliche_punkte_sind_markiert():
    neu = [{"item_number": "N 3", "title": "Grundstücksverkauf",
            "vorlage_nr": "", "is_public": False}]
    html = diff_html(diff_tagesordnung([], neu))
    assert "Neu · TOP N 3" in html and "(nichtöffentlich)" in html


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


def _check_committees():
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees_diff", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_ohne_nennbare_aenderung_gibt_es_keine_meldung():
    """Sprang der Hash ohne sichtbaren Grund, schickte die Mail den Satz
    „Details einzelner Punkte wurden angepasst" — eine Meldung, die nicht sagt,
    was los ist (Tims Befund 17.08.2026). Jetzt bleibt sie aus; "" ist das
    Zeichen dafür."""
    modul = _check_committees()
    gleich = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": "", "is_public": True}]
    assert modul._aenderungs_teil(list(gleich), gleich) == ""
    # Ohne Vergleichsbasis bleibt es bei der vollständigen Tagesordnung.
    assert modul._aenderungs_teil(None, gleich) is None
    # Und die nachgereichte Vorlage ist wieder eine echte Meldung.
    neu = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": "26/0100", "is_public": True}]
    assert "Vorlage nachgereicht" in modul._aenderungs_teil(list(gleich), neu)


def test_alter_snapshot_erfindet_keine_neuen_punkte():
    """Snapshots von vor dem 17.08.2026 kennen nur die öffentlichen Punkte.
    Gegen die neue Vollliste verglichen gälte jeder nichtöffentliche TOP als
    frisch eingefügt — die erste Änderungsmeldung nach dem Deploy wäre eine
    Liste erfundener Neuigkeiten."""
    modul = _check_committees()
    alt = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": ""}]       # ohne is_public
    jetzt = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": "", "is_public": True},
             {"item_number": "N 1", "title": "Grundstück", "vorlage_nr": "", "is_public": False}]
    assert modul._aenderungs_teil(alt, jetzt) == ""

    # Mit is_public im Altstand zählt der nichtöffentliche Punkt normal mit.
    alt_neu = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": "", "is_public": True}]
    assert "Neu · TOP N 1" in modul._aenderungs_teil(alt_neu, jetzt)


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
