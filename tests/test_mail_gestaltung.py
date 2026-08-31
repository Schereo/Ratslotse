"""Wie eine Benachrichtigung aussieht und wohin sie führt.

Gemeldet am 05.08.2026: „Das Mailtemplate ist hässlich ohne Logo, der Body ist
nicht gut strukturiert, und der Hauptlink sollte zu Ratslotse führen."

Beim Nachsehen kam ein dritter, unsichtbarer Fehler dazu: Die Adresse, die an
die Warteschlange ging, war die des Ratsinformationssystems — und
``lib/push.ts`` springt nur bei einem führenden „/". Das Antippen einer
Mitteilung tat also nichts. Genau diese Regel hält der erste Test fest.
"""
from __future__ import annotations

from dataclasses import dataclass

from council import watcher
from kern import digest_email


@dataclass
class _Item:
    item_number: str
    title: str


@dataclass
class _Sitzung:
    ksinr: int
    committee: str
    session_date: str
    session_time: str
    url: str
    agenda_items: list


def _sitzung(*tops: tuple[str, str]) -> _Sitzung:
    return _Sitzung(
        ksinr=4711,
        committee="Ausschuss für Stadtgrün, Umwelt und Klima",
        session_date="2026-08-13",
        session_time="17:00",
        url="https://buergerinfo.oldenburg.de/si0057.php?__ksinr=4711",
        agenda_items=[_Item(n, t) for n, t in tops],
    )


# --- wohin die Meldung führt ------------------------------------------------

def test_absolut_macht_aus_dem_pfad_eine_mailtaugliche_adresse():
    """In einer E-Mail gibt es keine Basis, gegen die ein relativer Link
    aufgelöst werden könnte — der Pfad der Warteschlange muss vollständig
    werden. (Das Tap-Ziel selbst bleibt ein Pfad, siehe test_notify.)"""
    assert digest_email.absolut("/council?x=1") == f"{digest_email.APP_BASE_URL}/council?x=1"
    # Ein Ratsinfo-Link ist schon vollständig und bleibt unangetastet.
    fremd = "https://buergerinfo.oldenburg.de/si0057.php?__ksinr=1"
    assert digest_email.absolut(fremd) == fremd
    assert digest_email.absolut("") == digest_email.APP_BASE_URL


def test_hauptweg_fuehrt_in_die_app_ratsinfo_bleibt_nebenlink():
    s = _sitzung(("Ö 6", "Baumschutzsatzung"))
    html = watcher._format_alert(s, {0: ["Ö 6"]}, [{"name": "Bäume"}])

    assert f"{digest_email.APP_BASE_URL}/council?tab=sessions&ksinr=4711" in html
    assert "si0057.php?__ksinr=4711" in html          # Quelle bleibt erreichbar
    # …aber als Nebenlink NACH dem Knopf, nicht als Hauptweg.
    assert html.index("Tagesordnung ansehen") < html.index("Ratsinformationssystem")


# --- wie sie aussieht -------------------------------------------------------

def test_tagesordnungspunkte_stehen_als_liste():
    """Vorher waren sie mit „; " zu einem Absatz verkettet — bei einem halben
    Dutzend Treffern fand man den eigenen Punkt darin nicht wieder."""
    s = _sitzung(("Ö 6", "Baumschutzsatzung"), ("Ö 9", "Kompensation"), ("Ö 13", "Windkraft"))
    html = watcher._format_alert(s, {0: ["Ö 6", "Ö 9", "Ö 13"]}, [{"name": "Bäume"}])

    assert html.count("<li") == 3
    kopf = html.split("<ul")[0]
    assert "; " not in kopf
    assert "Ausschuss für Stadtgrün, Umwelt und Klima" in kopf and "13. August" in kopf


def test_huelle_traegt_das_logo_als_absolute_adresse():
    """Mail-Programme laden nur absolute HTTPS-Bilder — ein Pfad bliebe leer."""
    html = digest_email.render_html_email("Betreff", "<p>Text</p>", greeting_name="Tim")
    assert digest_email.LOGO_URL.startswith("https://")
    assert digest_email.LOGO_URL in html
    assert "Moin Tim," in html


def test_kopfzeile_ist_eine_tabelle():
    """Outlook rendert mit der Word-Engine und kennt kein flex/gap — Logo und
    Schriftzug lägen dort untereinander."""
    html = digest_email.kopfzeile("Unterzeile")
    assert "<table role='presentation'" in html
    assert "display:flex" not in html


# --- was Nutzertext anrichten darf -----------------------------------------

def test_top_titel_wird_entschaerft():
    s = _sitzung(("Ö 6", "Kompensation <script>alert(1)</script>"))
    html = watcher._format_alert(s, {0: ["Ö 6"]}, [{"name": "x"}])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_betreff_bleibt_einzeilig_und_gekappt():
    """Themennamen kommen von Nutzer*innen. Ein Zeilenumbruch hat in einer
    Betreffzeile nichts zu suchen — Mail-Header sind zeilenbasiert."""
    assert "\n" not in watcher._einzeilig("Zeile eins\nZeile zwei")
    assert watcher._einzeilig("Zeile eins\nZeile zwei") == "Zeile eins Zeile zwei"

    lang = watcher._einzeilig("x" * 200)
    assert len(lang) <= 90 and lang.endswith("…")

    title = watcher._titel_thema(_sitzung(), "Bäume\nund\tGrünflächen")
    assert title == "„Bäume und Grünflächen“ kommt auf den Tisch"
