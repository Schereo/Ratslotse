"""Privatpersonen in fremden Vorlagentiteln — nur mit Anfangsbuchstaben.

Hannover setzt Namen in den Titel („Antrag von Herrn Lars Mesch
(Stadtjugendring)", „Beihilfen aus Bezirksratsmitteln; hier: Herr …",
Petitionen samt Wohnanschrift). Die Regel steht an
``council.cities.model.display_title``; hier stehen die Fälle aus dem Bestand
(03.10.2026), an denen sie gemessen ist.
"""
from __future__ import annotations

import pytest

from council.cities.model import display_title


@pytest.mark.parametrize("roh, gezeigt", [
    ("Antrag von Herrn Lars Mesch (Stadtjugendring) zum Intranet",
     "Antrag von Herrn L. M. (Stadtjugendring) zum Intranet"),
    ("Beihilfen aus Bezirksratsmitteln; hier: Herr Edin Bajrić",
     "Beihilfen aus Bezirksratsmitteln; hier: Herr E. B."),
    ("Petition von Herrn Rudolf Binder, Fliederweg 13 A",
     "Petition von Herrn R. B., Fliederweg 13 A"),
    ("Dringlichkeitsanfrage: Abschiebung von Herrn Dönmezler verhindern",
     "Dringlichkeitsanfrage: Abschiebung von Herrn D. verhindern"),
    ("Antrag der Elternvertreter (Herr Ralf Popp und Herr Michael Balke) zu DS 1",
     "Antrag der Elternvertreter (Herr R. P. und Herr M. B.) zu DS 1"),
    # Ein Fraktionsantrag GEGEN eine Person macht die Person nicht zur Amtsträgerin.
    ("Antrag der AfD-Fraktion zur Rückzahlungsaufforderung an Herrn Frank Herbert",
     "Antrag der AfD-Fraktion zur Rückzahlungsaufforderung an Herrn F. H."),
])
def test_privatpersonen_werden_gekuerzt(roh, gezeigt):
    assert display_title(roh) == gezeigt


@pytest.mark.parametrize("titel", [
    "Antwort zur Ratsanfrage von Herrn Eilers: Fraktionsmittel",
    "Antwort zur Ratsanfrage von Herrn Dr. Mommsen: Städtischer Zuschuss Wasserwelt",
    "Amtsmissbrauch des Beigeordneten Herrn Ronni Krug?",
    "Wahl von Frau Oberbürgermeisterin Pötter in die Gesellschafterversammlung",
    "Antrag von Herrn Samieske, Mitglied des Stadtrates Peine, DIE LINKE",
    "Ernennung des Herrn Dennis Fella zum Ortsbrandmeister der Ortsfeuerwehr Röhrse",
    "Benennung einer Straße / eines Platzes nach Frau Margot Friedländer",
])
def test_amtstraeger_behalten_ihren_namen(titel):
    """Wie beim Urheber: Wer in einem öffentlichen Verfahren als Amts- oder
    Mandatsträger handelt, gehört mit Namen zur Sache."""
    assert display_title(titel) == titel


@pytest.mark.parametrize("titel", [
    "Gewalt gegen Frauen und häusliche Gewalt bekämpfen",
    "Herr der Lage bleiben: Hochwasserschutz",
    "Kommunale Wärmeplanung",
    "",
])
def test_ohne_anrede_und_name_aendert_sich_nichts(titel):
    assert display_title(titel) == titel


def test_none_wird_zur_leeren_zeichenkette():
    assert display_title(None) == ""
