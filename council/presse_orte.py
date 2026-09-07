"""Pressemitteilungen der Stadt einem Ortsbereich zuordnen — für „Mein Viertel".

Die Stadt schreibt täglich, was sie tut: Sperrungen, Eröffnungen, Bauabschnitte,
Beteiligungen. Die Mitteilungen liegen seit 2024 in ``council_press``
(``scripts/check_presse.py``), bisher nur für die KI-Frage. Für die Tafel
eines Viertels braucht es die eine Zeile mehr: **welchen Ortsbereich meint
sie?** Das erledigt dieselbe Orts-Erkennung, mit der die Beschlüsse verortet
werden (``locations.extract_explicit_locations``, ``places.find_mentions``) —
regelbasiert, kostenlos, kein Modell:

1. **Katalog-Orte** im Titel und im Anfang des Textes: Ortsbereiche und
   kuratierte Teilräume samt Aliassen („Fliegerhorst", „Bürgerfelde",
   „Neu-Donnerschwee"). Ein Teilraum zählt für seine Ortsbereiche.
2. **Straßen und Plätze** aus demselben Text, die die Orts-Pipeline schon
   kennt (``council_locations`` + ``council_location_districts``): Die
   „Nadorster Straße" liegt zu 100 % in Bürgeresch, also zählt Bürgeresch.

**Was NICHT zählt** — gemessen am Bestand (3.180 Mitteilungen, 06.09.2026):

- Stadtweite Mitteilungen (``affects_whole_city``: Haushalt, Kommunalwahl,
  Verwaltung als Ganzes) und Rundumschläge, die mehr als ``MAX_PLACES``
  Ortsbereiche nennen („Glasfaser in mehreren Stadtteilen") — die stünden
  sonst auf jeder Tafel und sagten nirgends etwas.
- **Sitzungsankündigungen** („Am Montag, 24. August, tagt der
  Verkehrsausschuss"): Sie zählen Tagesordnungspunkte aus der halben Stadt
  auf; die Tafel hat dafür „Demnächst im Rat" aus der Tagesordnung selbst.
- **Straßen nur aus dem Titel.** Im Text stehen Umleitungen: Die
  „Fahrbahnsanierung in der Wunderburgstraße" nannte im Text die
  Bahnhofsallee als Umleitung und landete so in Kreyenbrück. Katalog-Orte
  gelten aus Titel und Vorspann (``TEXT_ZEICHEN``) — „Repair-Café in
  Bloherfelde" erwähnte Eversten erst weiter hinten.

Jede geprüfte Mitteilung bekommt einen Eintrag, auch wenn nichts gefunden
wurde (``place_id`` NULL), damit der Lauf sie nicht jede Nacht neu liest.
"""
from __future__ import annotations

import re

from council import locations, places

#: Wie viel vom Text für Katalog-Orte mitgelesen wird: der Vorspann. Weiter
#: hinten stehen Umleitungen, Veranstaltungsorte und Ansprechpartner.
TEXT_ZEICHEN = 300
MAX_PLACES = 5
#: „Am Montag, 24. August, tagt der Verkehrsausschuss" / „… tagt der Rat".
_SITZUNG_RE = re.compile(r"\btagt\b|\btagen\b|Tagesordnung", re.IGNORECASE)


def verorte_eine(store, title: str | None, text: str | None) -> list[dict]:
    """``[{place_id, via, evidence}]`` für eine Mitteilung — leer, wenn sie
    stadtweit ist oder nichts Belastbares nennt."""
    title = " ".join((title or "").split())
    vorspann = f"{title}. {' '.join((text or '')[:TEXT_ZEICHEN].split())}"
    if not vorspann.strip("."):
        return []
    if locations.affects_whole_city(title) or _SITZUNG_RE.search(title):
        return []
    gefunden: dict[str, dict] = {}
    for place in places.find_mentions(vorspann, max_n=8):
        for parent in places.primary_parents(place):
            gefunden.setdefault(parent.id, {"place_id": parent.id, "via": "catalog", "evidence": place.name})
    strassen = [c for c in locations.extract_explicit_locations(title, source="title")
                if c["kind"] in ("street", "square")]
    if strassen:
        slugs = [locations.location_slug(c["name"]) for c in strassen]
        for slug, place_id in store.location_primary_places(slugs).items():
            name = next((c["name"] for c in strassen if locations.location_slug(c["name"]) == slug), slug)
            gefunden.setdefault(place_id, {"place_id": place_id, "via": "street", "evidence": name})
    if len(gefunden) > MAX_PLACES:
        return []
    return list(gefunden.values())


def verorte(store, rows: list[dict]) -> dict:
    """Mitteilungen (``id``, ``title``, ``text``) verorten und speichern."""
    mit = ohne = 0
    for r in rows:
        treffer = verorte_eine(store, r.get("title"), r.get("text"))
        store.save_press_places(int(r["id"]), treffer)
        if treffer:
            mit += 1
        else:
            ohne += 1
    return {"verortet": mit, "ohne Ort": ohne}
