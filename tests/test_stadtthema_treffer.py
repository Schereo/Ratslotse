"""Die Brücke von einer Frage zu einem kuratierten Stadtthema (Teil B / PR 5).

Sie ist bewusst deterministisch: ein Satz Muster gegen den Fragetext, kein
Modell. Was hier festgehalten wird, ist deshalb weniger die Trefferquote als
die Zusagen — dass eine Frage ohne Treffer sauber ``None`` liefert, dass die
Reihenfolge der Registry entscheidet, und dass die Muster nicht auf halbe
Wörter anspringen.
"""
from __future__ import annotations

from council.city_topics import CITY_TOPICS, match_question


def test_klare_fragen_treffen_ihr_thema():
    for frage, erwartet in (
        ("Was wurde zum Radverkehr beschlossen?", "Radverkehr"),
        ("Wie steht es um den Kita-Ausbau in Oldenburg?", "Kitas"),
        ("Was wurde zum Stadionneubau entschieden?", "Stadion-Neubau"),
    ):
        t = match_question(frage)
        assert t is not None and t.name == erwartet, (frage, t.name if t else None)


def test_ohne_treffer_kommt_nichts():
    """Der Normalfall — an fünfzehn echten Fragen traf es bei vieren.

    Wichtig ist, dass das ``None`` ist und nicht ein schwacher Treffer: Die
    Oberfläche zeigt dann ihren eigenen Weg statt einer Kachel, die danebenliegt.
    """
    for frage in ("Was ist eine Ausfallbürgschaft?",
                  "Wie viele Schulden hat die Stadt Oldenburg?",
                  "Was hat der Jugendhilfeausschuss am 17.06.2026 beschlossen?"):
        assert match_question(frage) is None, frage


def test_zu_kurzes_wird_gar_nicht_erst_geprueft():
    for roh in ("", "  ", "ok", None):
        assert match_question(roh) is None


def test_bei_mehreren_treffern_gewinnt_die_registry_reihenfolge():
    """Eine feste, nachlesbare Regel statt einer geratenen Gewichtung."""
    frage = "Was wurde zu Schulen und Kitas beschlossen?"
    t = match_question(frage)
    assert t is not None
    namen = [x.name for x in CITY_TOPICS if x.name in ("Schulen", "Kitas")]
    assert t.name == namen[0], f"{t.name} statt {namen[0]} — Registry-Reihenfolge missachtet"


def test_muster_springen_nicht_auf_halbe_woerter_an():
    """`schul` darf nicht in „Schulden" oder „Hochschule" anspringen — das
    steht als Negativ-Blick im Muster und ist genau die Sorte Regel, die beim
    nächsten Umbau verloren geht."""
    t = match_question("Wie hoch sind die Schulden der Stadt?")
    assert t is None or t.name != "Schulen"
