"""Tagesordnungs-Diff für die Änderungs-Meldung (Tims Wunsch 12.08.):
nur die Unterschiede, grün/gelb/rot — und ein Einschub darf nicht die halbe
Liste gelb färben, nur weil sich Nummern verschieben."""
from __future__ import annotations

from council.agenda_diff import diff_html, diff_satz, diff_tagesordnung, hat_aenderungen


def _i(nr: str, titel: str, vorlage: str = "") -> dict:
    return {"item_number": nr, "title": titel, "vorlage_nr": vorlage}


def _a(*ids_labels: tuple[str, str]) -> list[dict]:
    """Anlagen-Liste aus (getfile-id, Label)-Paaren."""
    return [{"label": label,
             "url": f"https://buergerinfo.oldenburg.de/getfile.php?id={gid}&type=do"}
            for gid, label in ids_labels]


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


def test_neue_anlage_ist_eine_aenderung():
    """Tims Wunsch 18.08.: Hängt an einem TOP plötzlich ein neuer Anhang
    (Änderungsliste, Stellungnahme), soll die Mail das als Anlagen-Änderung
    benennen — mit Label, nicht nur als Hash-Sprung."""
    alt = [dict(_i("Ö 5", "Radweg"), anlagen=[])]
    neu = [dict(_i("Ö 5", "Radweg"), anlagen=_a(("111", "Änderungsliste der CDU-Fraktion")))]
    d = diff_tagesordnung(alt, neu)
    assert len(d["anlagen"]) == 1 and hat_aenderungen(d)
    assert d["neu"] == [] and d["vorlage"] == []
    html = diff_html(d)
    assert "Neue Anlage · TOP Ö 5" in html and "Änderungsliste der CDU-Fraktion" in html


def test_anlagen_entfernt_und_getauscht():
    alt = [dict(_i("Ö 5", "Radweg"), anlagen=_a(("111", "Lageplan")))]
    neu = [dict(_i("Ö 5", "Radweg"), anlagen=[])]
    assert "Anlage entfernt · TOP Ö 5" in diff_html(diff_tagesordnung(alt, neu))

    alt = [dict(_i("Ö 5", "Radweg"), anlagen=_a(("111", "Lageplan")))]
    neu = [dict(_i("Ö 5", "Radweg"), anlagen=_a(("222", "Lageplan (aktualisiert)")))]
    html = diff_html(diff_tagesordnung(alt, neu))
    assert "Anlagen geändert · TOP Ö 5" in html
    assert "neu: Lageplan (aktualisiert)" in html and "entfernt: Lageplan" in html


def test_label_wechsel_ohne_neue_id_ist_keine_aenderung():
    """Icon- und Textlink tragen dieselbe getfile-id, Labels schwanken beim
    Parsen — die Identität eines Anhangs ist die id, nicht der Text."""
    alt = [dict(_i("Ö 5", "Radweg"), anlagen=_a(("111", "Anlage")))]
    neu = [dict(_i("Ö 5", "Radweg"), anlagen=_a(("111", "Lageplan Nord")))]
    d = diff_tagesordnung(alt, neu)
    assert not hat_aenderungen(d)


def test_vorlage_schlaegt_anlagen():
    """Eine nachgereichte Vorlage hängt ihr PDF meist auch als Anlage an die
    Zeile — das ist EINE Meldung (Vorlage), nicht zwei."""
    alt = [dict(_i("Ö 5", "Radweg"), anlagen=[])]
    neu = [dict(_i("Ö 5", "Radweg", "26/0100"), anlagen=_a(("111", "Vorlage")))]
    d = diff_tagesordnung(alt, neu)
    assert len(d["vorlage"]) == 1 and d["anlagen"] == []


def test_diff_satz_nennt_die_aenderungsarten():
    alt = [_i("Ö 5", "Baumschutzsatzung"),
           _i("Ö 6", "Regentonnen"),
           dict(_i("Ö 7", "Radweg"), anlagen=[])]
    neu = [_i("Ö 5", "Baumschutzsatzung"),
           _i("Ö 5.1", "Rattenbefall"),
           dict(_i("Ö 7", "Radweg"), anlagen=_a(("111", "Lageplan")))]
    d = diff_tagesordnung(alt, neu)
    satz = diff_satz(d)
    assert satz == ("Ein Punkt ist neu, die Anlagen zu einem Punkt haben sich "
                    "geändert und ein Punkt wurde von der Tagesordnung genommen.")
    # Der Satz steht über der Liste in der Mail.
    assert satz in diff_html(d)

    # Mehrzahl und Vorlagen-Fälle:
    d2 = diff_tagesordnung(
        [_i("Ö 1", "Alpha"), _i("Ö 2", "Beta"), _i("Ö 3", "Gamma", "26/0100")],
        [_i("Ö 1", "Alpha"), _i("Ö 4", "Neu A"), _i("Ö 5", "Neu B"),
         _i("Ö 2", "Beta", "26/0200"), _i("Ö 3", "Gamma")])
    satz2 = diff_satz(d2)
    assert "2 Punkte sind neu" in satz2
    assert "eine Vorlage wurde nachgereicht" in satz2
    assert "eine Vorlage wurde zurückgezogen" in satz2


def test_gleichnamige_tops_erzeugen_keine_phantom_verschiebungen():
    """Der Befund aus der Demo-Mail vom 18.08. (Jugendhilfeausschuss 4674):
    Nichtöffentliche Teile führen reihenweise TOPs namens „gesperrte
    Information". Alle dockten am ERSTEN Namensvetter an — ein unveränderter
    Block meldete „Verschoben · N 11 → N 12" und „N 11 → N 13"."""
    items = [_i("Ö 1", "Einwohnerfragestunde"),
             _i("N 11", "gesperrte Information"),
             _i("N 12", "gesperrte Information"),
             _i("N 13", "gesperrte Information")]
    d = diff_tagesordnung(items, list(items))
    assert not hat_aenderungen(d)

    # Ein NEUER Namensvetter ist neu — nicht „verschoben".
    mehr = items + [_i("N 14", "gesperrte Information")]
    d2 = diff_tagesordnung(items, mehr)
    assert [i["item_number"] for i in d2["neu"]] == ["N 14"]
    assert d2["verschoben"] == []

    # Ein weggefallener Namensvetter ist entfernt — früher unsichtbar,
    # weil der Titel ja „noch da" war.
    d3 = diff_tagesordnung(mehr, items)
    assert [i["item_number"] for i in d3["entfernt"]] == ["N 14"]
    assert d3["verschoben"] == [] and d3["neu"] == []


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


def test_alter_snapshot_ohne_anlagen_meldet_keine_anlagen():
    """Snapshots von vor dem 18.08.2026 kennen keine Anhänge. Gegen den neuen
    Stand verglichen gälte jede längst vorhandene Anlage als frisch — die
    erste Meldung nach dem Deploy wäre wieder eine Liste erfundener
    Neuigkeiten (dieselbe Falle wie bei is_public)."""
    modul = _check_committees()
    alt = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": "", "is_public": True}]
    jetzt = [{"item_number": "Ö 5", "title": "Radweg", "vorlage_nr": "", "is_public": True,
              "anlagen": _a(("111", "Lageplan"))}]
    assert modul._aenderungs_teil(alt, jetzt) == ""

    # Kennt der Altstand die Anlagen, ist der Neuzugang eine echte Meldung.
    alt_neu = [dict(alt[0], anlagen=[])]
    assert "Neue Anlage" in modul._aenderungs_teil(alt_neu, jetzt)


def test_agenda_hash_zaehlt_anlagen_mit():
    """Eine neue Anlage muss den Hash springen lassen (sonst gibt es nie eine
    Änderungsmeldung dazu); ein bloßer Label-Wechsel derselben getfile-id
    darf es nicht."""
    from types import SimpleNamespace

    modul = _check_committees()

    def _item(anlagen):
        return SimpleNamespace(item_number="Ö 5", title="Radweg", vorlage_nr="",
                               is_public=True, anlagen=anlagen)

    ohne = modul._agenda_hash([_item([])])
    mit = modul._agenda_hash([_item(_a(("111", "Lageplan")))])
    umbenannt = modul._agenda_hash([_item(_a(("111", "Lageplan Nord")))])
    assert ohne != mit and mit == umbenannt


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


def test_aenderungs_chronik_roundtrip(tmp_path):
    """„Zuletzt geändert" auf der Sitzungsseite (Tims Wunsch 18.08.): Der Diff
    überlebt die JSON-Runde — Paare kommen als 2er-Listen zurück, diff_zeilen
    und diff_satz arbeiten damit wie mit den Original-Tupeln."""
    from council.agenda_diff import diff_zeilen
    from council.store import CouncilStore
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        assert store.get_latest_agenda_snapshot(4666) is None
        alt = [_i("Ö 5", "Radweg")]
        neu = [_i("Ö 5", "Radweg", "26/0100"), _i("Ö 6", "Neubau Kita")]
        store.save_agenda_snapshot(4666, "hash-a", alt)
        assert store.get_latest_agenda_snapshot(4666) == alt

        d = diff_tagesordnung(alt, neu)
        store.save_agenda_change(4666, d)
        chronik = store.agenda_changes(4666)
        assert len(chronik) == 1
        zeilen = diff_zeilen(chronik[0]["diff"])
        assert {z["art"] for z in zeilen} == {"neu", "vorlage"}
        assert diff_satz(chronik[0]["diff"]) == (
            "Ein Punkt ist neu und eine Vorlage wurde nachgereicht.")
        assert store.agenda_changes(999) == []
    finally:
        store.close()
