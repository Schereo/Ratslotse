"""Jeder Punkt der Tagesordnungs-Mail trägt seine Überschrift.

Tims Befund am 19.09.2026 an der Rats-Mail zum 28.09.: „irgendwie fehlen in
dieser Mail Überschriften für die TOPs?" — zwanzig Zeilen der Form „Ö 6.3:
Beantragt sind 9.512.500 Euro zusätzlich …", und bei keiner stand, wie der
Punkt heißt. Der Kartentext nennt den Titel bewusst nicht, weil er in der App
UNTER dem Titel steht; in der Mail fehlte der Titel aber ganz.

Zwei Dinge stehen hier unter Beobachtung: dass Nummer und Titel über dem Satz
stehen (und die Push-Vorschau die beiden nicht zusammenklebt), und dass ein
schon gecachter Block aus der Zeit davor beim nächsten Versand neu gebaut
wird — ohne Modell, aus den gespeicherten Sätzen.
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


@pytest.fixture
def stumm(monkeypatch):
    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees_ueberschriften", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    import council.impact

    monkeypatch.setattr(modul.social_text, "schreibe_fehlende", lambda *a, **kw: (0, 0))
    monkeypatch.setattr(council.impact, "rate_agenda_batch", lambda *a, **kw: [])
    return modul


def _sitzung(store, ksinr=1):
    tag = (date.today() + timedelta(days=7)).isoformat()
    store._conn.execute(
        "INSERT OR REPLACE INTO council_sessions (ksinr, committee, session_date, "
        "session_time, location, fetched_at) VALUES (?, 'Rat', ?, '18:00', 'PFL', 'x')",
        (ksinr, tag))
    store._conn.commit()


def _punkt(store, ksinr, nummer, title):
    store._conn.execute(
        "INSERT INTO council_agenda_items (ksinr, item_number, title, is_public) "
        "VALUES (?, ?, ?, 1)", (ksinr, nummer, title))
    store._conn.commit()


def test_nummer_und_titel_stehen_ueber_dem_satz(store, stumm):
    _sitzung(store)
    _punkt(store, 1, "Ö 6.3", "Überplanmäßige Aufwendungen im Sozialetat 2026 - Beschluss")
    html = stumm._aufzaehlung(store, 1, [
        {"number": "Ö 6.3", "summary": "Beantragt sind 9.512.500 Euro zusätzlich für Wohngeld."},
    ])
    assert ("<b>Ö 6.3 · Überplanmäßige Aufwendungen im Sozialetat 2026 - Beschluss</b>\n"
            "Beantragt sind 9.512.500 Euro zusätzlich für Wohngeld.") in html
    # Der alte Doppelpunkt-Stil ist weg.
    assert "</b>: " not in html


def test_ein_titel_mit_sonderzeichen_bleibt_text(store, stumm):
    _sitzung(store)
    _punkt(store, 1, "Ö 5", "Antrag <SPD> & Grüne")
    html = stumm._aufzaehlung(store, 1, [{"number": "Ö 5", "summary": "Es geht um X."}])
    assert "<b>Ö 5 · Antrag &lt;SPD&gt; &amp; Grüne</b>" in html


def test_ohne_titel_steht_die_nummer_allein(store, stumm):
    """Ein Punkt, den der Store nicht (mehr) kennt, bekommt keine erfundene
    Überschrift — nur seine Nummer."""
    _sitzung(store)
    html = stumm._aufzaehlung(store, 1, [{"number": "Ö 5", "summary": "Es geht um X."}])
    assert "<b>Ö 5</b>\nEs geht um X." in html


def test_die_push_vorschau_klebt_titel_und_satz_nicht_zusammen(store, stumm):
    _sitzung(store)
    _punkt(store, 1, "Ö 5", "Bebauungsplan 837")
    html = stumm._aufzaehlung(store, 1, [{"number": "Ö 5", "summary": "Geplant ist ein Wohngebiet."}])
    assert stumm._push_kurz(html) == "Ö 5 · Bebauungsplan 837 Geplant ist ein Wohngebiet."


def test_ein_alter_block_ohne_ueberschriften_wird_neu_gebaut(store, stumm):
    """Der Block wird je Tagesordnung einmal gebaut und dann jedem weiteren
    Abonnenten unverändert geschickt. Wer den Rat heute abonniert, bekäme
    sonst für den 28.09. noch die Liste ohne Titel."""
    _sitzung(store)
    _punkt(store, 1, "Ö 5", "Bebauungsplan 837")
    store.save_item_summaries(1, "h1", [{"number": "Ö 5", "summary": "Geplant ist ein Wohngebiet."}])
    store.save_summary(1, "h1", "• <b>Ö 5</b>: Geplant ist ein Wohngebiet.")

    neu = stumm._gecachte_aufzaehlung(store, 1, "h1")
    assert "<b>Ö 5 · Bebauungsplan 837</b>\nGeplant ist ein Wohngebiet." in neu
    # … und steht ab jetzt so im Cache, damit das nur einmal passiert.
    assert store.get_cached_summary(1, "h1") == neu
    assert stumm._gecachte_aufzaehlung(store, 1, "h1") == neu


def test_der_neubau_braucht_die_saetze_zu_diesem_stand(store, stumm):
    """Sätze zu einer anderen Tagesordnung sind keine — dann bleibt der alte
    Block stehen. Lieber der als keiner, und lieber der als ein falscher."""
    _sitzung(store)
    _punkt(store, 1, "Ö 5", "Bebauungsplan 837")
    store.save_item_summaries(1, "h0", [{"number": "Ö 5", "summary": "Alter Satz."}])
    alt = "• <b>Ö 5</b>: Alter Satz."
    store.save_summary(1, "h1", alt)

    assert stumm._gecachte_aufzaehlung(store, 1, "h1") == alt
    assert store.get_cached_summary(1, "h1") == alt


def test_routine_und_cache_miss_bleiben_wie_sie_sind(store, stumm):
    """'' heißt „nur Routine" und ist ein gültiger Treffer; None ist keiner —
    beide gehen unverändert durch, sonst baute der Aufrufer neu."""
    _sitzung(store)
    assert stumm._gecachte_aufzaehlung(store, 1, "h1") is None
    store.save_summary(1, "h1", "")
    assert stumm._gecachte_aufzaehlung(store, 1, "h1") == ""
