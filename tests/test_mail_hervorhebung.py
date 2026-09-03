"""Die Tagesordnungs-Mail hebt das Wichtigste hervor — und bleibt vollständig.

Tims Befund am 03.09.2026 an der Mail des Ausschusses für Stadtgrün: elf
Punkte, elf gleich aussehende Zeilen, „einfach eine lange Liste, die schwer zu
überblicken ist". Die Bewertung, nach der die Wochen-Karte hervorhebt
(``agenda_item_impact``), lag längst vor und wurde in der Mail nicht benutzt.

Zwei Dinge stehen hier unter Beobachtung: dass oben nur landet, was die
Schwelle wirklich nimmt (sonst kürt die Mail auf einer Routine-Tagesordnung
drei Belanglosigkeiten), und dass unten trotzdem ALLES steht.
"""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

from council.store import CouncilStore


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _check_committees():
    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees_hervorhebung", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _sitzung(store, ksinr=1, tage=7):
    tag = (date.today() + timedelta(days=tage)).isoformat()
    store._conn.execute(
        "INSERT OR REPLACE INTO council_sessions (ksinr, committee, session_date, "
        "session_time, location, fetched_at) VALUES (?, 'Ausschuss für Stadtgrün', ?, "
        "'17:00', 'Alte Fleiwa', 'x')", (ksinr, tag))
    store._conn.commit()


def _punkt(store, ksinr, nummer, title):
    store._conn.execute(
        "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
        "VALUES (?, ?, ?, 1)", (ksinr, nummer, title))
    store._conn.commit()


#: Die Sitzung aus Tims Mail, auf das Nötige gekürzt.
_TOPS = [
    ("Ö 5", "Bericht: Altarm an der Haaren", "Der Ausschuss erhält einen Bericht zum Altarm.", 20),
    ("Ö 6", "Beratungsangebot für Wohnungseigentümergemeinschaften",
     "Vorgestellt wird ein Beratungsangebot.", 25),
    ("Ö 7", "Förderprogramm 2026 Klimaschutz im Altbau",
     "Der Ausschuss informiert sich über den Stand des Förderprogramms.", 35),
    ("Ö 8.1.2", "Antrag der CDU-Fraktion: Baumschutzsatzung aussetzen",
     "Die CDU beantragt, die Baumschutzsatzung auszusetzen.", 80),
    ("Ö 8.3", "Antrag der CDU-Fraktion: Ehemaliger Schießstand",
     "Die CDU beantragt Ermittlungen zu Materialien auf dem Schießstand.", 70),
    ("Ö 8.6", "Kastanien-Miniermotte", "Der Ausschuss befasst sich mit der Miniermotte.", 30),
]


def _tagesordnung(store, ksinr=1, mit_bewertung=True):
    _sitzung(store, ksinr)
    for nummer, title, _satz, wert in _TOPS:
        _punkt(store, ksinr, nummer, title)
        if mit_bewertung:
            store.save_agenda_impact(ksinr, nummer, wert, f"Begründung zu {nummer}")
    return [{"number": n, "summary": satz} for n, _t, satz, _w in _TOPS]


@pytest.fixture
def stumm(monkeypatch):
    """Kein LLM in diesen Tests: Kartentexte und Nachbewertung sind anderswo
    geprüft, hier geht es um die Gliederung."""
    modul = _check_committees()
    import council.impact

    monkeypatch.setattr(modul.social_text, "schreibe_fehlende", lambda *a, **kw: (0, 0))
    monkeypatch.setattr(council.impact, "rate_agenda_batch", lambda *a, **kw: [])
    return modul


def test_das_wichtigste_steht_oben_und_die_liste_bleibt_vollstaendig(store, stumm):
    punkte = _tagesordnung(store)
    html = stumm._aufzaehlung(store, 1, punkte)

    assert "Das Wichtigste" in html and "Alle Punkte" in html
    # Die Zahl neben dem Kicker ist die echte Zahl der Punkte, nicht „viele".
    assert ">6</td>" in html
    oben, unten = html.split("Alle Punkte", 1)
    # Oben die beiden Anträge über der Schwelle (80 und 70) plus Ö 7 (35).
    assert "<b>Ö 8.1.2</b>" in oben and "<b>Ö 8.3</b>" in oben and "<b>Ö 7</b>" in oben
    assert "<b>Ö 5</b>" not in oben and "<b>Ö 6</b>" not in oben
    # Unten steht die ganze Tagesordnung, die hervorgehobenen Punkte ein
    # zweites Mal an ihrem Platz.
    for nummer, _t, _s, _w in _TOPS:
        assert f"<b>{nummer}</b>" in unten


def test_hoechstens_drei_und_in_der_reihenfolge_der_tagesordnung(store, stumm):
    """Vier wären keine Auswahl mehr — und die Reihenfolge oben ist die der
    Sitzung, nicht die der Punktzahl: Ein Rang wäre eine Aussage über den
    Abstand zweier Punkte, den die Bewertung nicht genau genug misst."""
    punkte = _tagesordnung(store)
    store.save_agenda_impact(1, "Ö 6", 90, "jetzt der stärkste Punkt")
    oben = stumm._aufzaehlung(store, 1, punkte).split("Alle Punkte", 1)[0]

    assert oben.count("• <b>") == 3
    assert oben.index("<b>Ö 6</b>") < oben.index("<b>Ö 8.1.2</b>") < oben.index("<b>Ö 8.3</b>")
    # Ö 7 (35) ist jetzt der vierte und fällt heraus.
    assert "<b>Ö 7</b>" not in oben


def test_routine_tagesordnung_bekommt_keine_hervorhebung(store, stumm):
    """Nichts über der Schwelle heißt: kein Block. Drei künstlich gekürte
    Belanglosigkeiten wären schlechter als die Liste von vorher."""
    _sitzung(store)
    punkte = []
    for i in range(6):
        nummer = f"Ö {i + 5}"
        _punkt(store, 1, nummer, f"Widmung eines Weges {i}")
        store.save_agenda_impact(1, nummer, 15, "Formalie")
        punkte.append({"number": nummer, "summary": f"Es geht um Weg {i}."})

    html = stumm._aufzaehlung(store, 1, punkte)
    assert "Das Wichtigste" not in html and "Alle Punkte" not in html
    assert html.startswith("• <b>Ö 5</b>")


def test_kurze_tagesordnung_bleibt_eine_liste(store, stumm):
    """Bei vier Punkten gibt es nichts zu überblicken."""
    _sitzung(store)
    punkte = []
    for i in range(4):
        nummer = f"Ö {i + 5}"
        _punkt(store, 1, nummer, f"Ein gewichtiger Punkt {i}")
        store.save_agenda_impact(1, nummer, 80, "wichtig")
        punkte.append({"number": nummer, "summary": f"Es geht um Sache {i}."})

    assert "Das Wichtigste" not in stumm._aufzaehlung(store, 1, punkte)


def test_ohne_bewertung_bleibt_alles_wie_vorher(store, stumm):
    """Reißt die Bewertung (Modell weg, Provider-Fehler), gibt es keine
    geratene Rangfolge — nur die Liste."""
    punkte = _tagesordnung(store, mit_bewertung=False)
    html = stumm._aufzaehlung(store, 1, punkte)
    assert "Das Wichtigste" not in html
    assert html.count("• <b>") == len(_TOPS)


def test_ein_fehlschlag_der_nachbewertung_kostet_die_mail_nichts(store, monkeypatch):
    modul = _check_committees()
    import council.impact

    punkte = _tagesordnung(store, mit_bewertung=False)
    monkeypatch.setattr(modul.social_text, "schreibe_fehlende", lambda *a, **kw: (0, 0))

    def kaputt(*a, **kw):
        raise RuntimeError("OpenRouter 502")

    monkeypatch.setattr(council.impact, "rate_agenda_batch", kaputt)
    html = modul._aufzaehlung(store, 1, punkte)
    assert html.count("• <b>") == len(_TOPS)


def test_die_push_vorschau_faengt_beim_wichtigsten_punkt_an(store, stumm):
    """180 Zeichen auf dem Sperrbildschirm — keiner davon geht an „Das
    Wichtigste"."""
    punkte = _tagesordnung(store)
    kurz = stumm._push_kurz(stumm._aufzaehlung(store, 1, punkte))

    assert not kurz.startswith("Das Wichtigste")
    assert "Alle Punkte" not in kurz
    assert kurz.startswith("• Ö 7:")   # der Aufzählungspunkt wie eh und je


def test_die_bewertung_der_mail_holt_nur_diese_sitzung_und_ohne_zeitfenster(store):
    """Der Tranchen-Lauf schaut 21 Tage voraus; die Mail geht raus, sobald die
    Tagesordnung erscheint — und die kann früher da sein."""
    _sitzung(store, ksinr=1, tage=60)
    _sitzung(store, ksinr=2, tage=3)
    _punkt(store, 1, "Ö 5", "Ein inhaltlicher Punkt dieser Sitzung")
    _punkt(store, 2, "Ö 5", "Ein Punkt der anderen Sitzung")

    offen = store.agenda_items_needing_impact(ksinr=1)
    assert [(p["ksinr"], p["item_number"]) for p in offen] == [(1, "Ö 5")]
    assert [p["ksinr"] for p in store.agenda_items_needing_impact()] == [2]
    # Auch mit Deckel bleibt der Sitzungs-Filter stehen (der Deckel hängt an
    # denselben Parametern wie die Sitzung).
    assert [p["ksinr"] for p in store.agenda_items_needing_impact(limit=5, ksinr=1)] == [1]


def test_widmung_und_dringlichkeit_gelten_auch_in_der_mail(store):
    """Dieselben lesezeitigen Korrekturen wie auf der Wochen-Karte — sonst
    hieße ein Punkt an zwei Stellen verschieden wichtig."""
    _sitzung(store)
    _punkt(store, 1, "Ö 5", "Widmung der Straße Im Technologiepark")
    _punkt(store, 1, "DZT 1", "Dringlichkeitsantrag der Fraktion")
    store.save_agenda_impact(1, "Ö 5", 70, "hoch bewertet")
    store.save_agenda_impact(1, "DZT 1", 30, "niedrig bewertet")

    wichtig = store.agenda_wichtigkeit(1)
    assert wichtig["Ö 5"] <= 15
    assert wichtig["DZT 1"] > 30
