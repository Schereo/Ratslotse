"""Was sich bei jedem Abruf ändert, darf nicht als Änderung gelten.

Wolfsburgs ALLRIS 4 liefert dieselbe Seite nie bitgleich aus: Wicket vergibt
seine Element-IDs je Anfrage neu, das Suchformular trägt ein frisches
Sitzungs-Token, und die Seitenversion in den Selbstaufruf-Adressen zählt
hoch. Gemessen am 14.09.2026 an zwei Fassungen derselben Sitzungsseite —
beide **13.735 Zeichen**, 22 Zeilen verschieden, kein Wort davon Inhalt.

Die Folge war teuer: 1.956 Rohzeilen für 652 Sitzungen (genau drei Ernten),
und weil `iter_papers` an frisch hereingekommenen Sitzungen erkennt, was
aufzufrischen ist, wurden jedes Mal ALLE 1.571 Vorlagen neu geholt —
**2.261 Abrufe statt 251** wie bei Hannover.
"""
from __future__ import annotations

from council.cities.adapters.allris4_html import ohne_wicket_ids
from council.cities.store import CitiesStore

#: Die drei Formen, die in den echten Seiten vorkommen.
EINS = (
    '<div id="id12cd4" class="x">'
    "<script>var elem = $('#id12cd2').find('.searchfield');"
    'Wicket.Ajax.ajax({"u":"https://x/to010?848-1.0-tagesordnung-showHideLink",'
    '"c":"showHideLink_id12be1"});</script>'
    '<form action="https://x/vo020?2416-1.-head-searchform">'
    '<input type="hidden" name="sectoken" value="1cd8c0963c392d81c8600422d279c69d" />'
    "<td>Trinkwasserbrunnen im Stadtbezirk</td></form></div>"
)
ZWEI = (
    '<div id="id12cf8" class="x">'
    "<script>var elem = $('#id12cf6').find('.searchfield');"
    'Wicket.Ajax.ajax({"u":"https://x/to010?848-1.0-tagesordnung-showHideLink",'
    '"c":"showHideLink_id12bf5"});</script>'
    '<form action="https://x/vo020?2417-1.-head-searchform">'
    '<input type="hidden" name="sectoken" value="8dd2a9a72304c8516fde00043f647ba0" />'
    "<td>Trinkwasserbrunnen im Stadtbezirk</td></form></div>"
)


def test_zwei_abrufe_derselben_seite_gelten_als_gleich():
    assert ohne_wicket_ids(EINS) == ohne_wicket_ids(ZWEI)


def test_eine_echte_aenderung_bleibt_eine_aenderung():
    """Der Preis dafür wäre, Inhalt zu verschlucken — das darf nicht sein."""
    geaendert = ZWEI.replace("Trinkwasserbrunnen", "Sitzbänke")
    assert ohne_wicket_ids(ZWEI) != ohne_wicket_ids(geaendert)


def test_der_inhalt_bleibt_im_text_stehen():
    """Bereinigt wird für den VERGLEICH, nicht für das Lesen."""
    assert "Trinkwasserbrunnen im Stadtbezirk" in ohne_wicket_ids(EINS)


def test_abgelegt_wird_die_antwort_selbst_nicht_die_bereinigte(tmp_path):
    """Die Rohschicht hält fest, was der Server gesagt hat — unverändert.

    `hash_basis` entscheidet nur, ob eine Zeile als NEU gilt.
    """
    with CitiesStore(tmp_path / "raw.sqlite") as s:
        obj = {"id": "m/1", "html": EINS}
        assert s.put_raw_object("wolfsburg", "meeting", "m/1", obj,
                                hash_basis=ohne_wicket_ids(EINS))
        # Derselbe Inhalt, andere Wicket-IDs: keine zweite Zeile.
        assert not s.put_raw_object("wolfsburg", "meeting", "m/1",
                                    {"id": "m/1", "html": ZWEI},
                                    hash_basis=ohne_wicket_ids(ZWEI))
        (zeile,) = list(s.raw_objects("wolfsburg", "meeting"))
        assert zeile["html"] == EINS, "abgelegt wird die Antwort, nicht die Bereinigung"


def test_der_adapter_vergleicht_bereinigt():
    """Der Wächter: ohne `hash_basis` legt jeder Lauf neue Zeilen an."""
    import inspect

    from council.cities.adapters import get_adapter

    for name in ("iter_meetings", "iter_papers"):
        quelle = inspect.getsource(getattr(get_adapter("allris4_html"), name))
        assert "hash_basis=ohne_wicket_ids" in quelle, (
            f"allris4_html.{name} legt wieder bei jedem Abruf eine neue "
            "Rohzeile an — und `iter_papers` hält daraufhin jede Sitzung für "
            "frisch.")
