"""ALLRIS 4 (CC e-gov) — Osnabrück, Braunschweig, Potsdam, Leipzig, Bonn.

Vier Eigenheiten, alle am 07.09.2026 gemessen, alle still (keine wirft einen
Fehler, jede liefert stattdessen falsche oder gar keine Daten):

1. **Listen laufen alt → neu**, die neuesten Objekte stehen auf der
   **letzten** Seite. Osnabrück: Seite 1.955 von 1.955.
2. **Die Seitengröße ist fest 10**; ``limit`` wird ignoriert.
3. **Zeitfilter sind wirkungslos.** ``created`` und ``modified`` stehen bei
   *allen* Objekten auf ``2000-01-01``, also liefert ``created_since`` null
   Treffer und ``modified_since`` alles.
4. **Alte Papiere tragen kein Datum.** Wer eine undatierte Zeile als „noch im
   Fenster" zählt, blättert bis 1997 zurück.

Daraus folgt der einzige gangbare Weg: erste Seite holen, ``links.last``
lesen, rückwärts blättern, und abbrechen, sobald eine Seite nichts mehr im
Zeitfenster hat.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from council.cities.adapters._common import (
    link_by_title, normalize_common, parse_date,
)
from council.cities.model import Batch
from council.cities.oparl import OParlClient, as_list
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.allris4")

#: Sicherheitsdeckel je Lauf und Liste. 600 Seiten × 10 Objekte reichen für
#: gut drei Jahrgänge der größten Stadt; ohne Deckel liefe ein Fehler in der
#: Abbruchbedingung bis 1997 durch.
MAX_PAGES = 600

#: So viele Objekte außerhalb des Zeitfensters, bis abgebrochen wird. Nicht
#: eins: Die Sortierung ist nicht streng, ein einzelner Ausreißer beendet
#: sonst den Lauf zu früh.
ALTE_BIS_ABBRUCH = 80


def _page(url: str, n: int) -> str:
    return re.sub(r"page=\d+", f"page={n}", url)


def _datum_von(o: dict) -> str:
    """Das Datum eines Listenobjekts — egal ob Vorlage oder Sitzung.

    **Eine Vorlage hat ``date``, eine Sitzung hat ``start``.** Die erste
    Fassung fragte überall nach ``date``; bei Sitzungen kam damit immer
    ``None`` heraus, und weil undatiert bewusst als „alt" zählt (s. u.), brach
    die Rückwärts-Blätterung nach zwei Seiten ab — bei jedem Lauf, für jede
    ALLRIS-Stadt. Gemessen am 08.09.2026: Osnabrück hatte 137 Sitzungen zu
    2.864 Vorlagen, Braunschweig 218 zu 6.000, Potsdam 222 zu 5.994. Ohne
    Sitzung gibt es keinen Tagesordnungspunkt und damit kein Ergebnis — der
    Fehler war also nicht, dass Sitzungen fehlten, sondern dass die halbe
    Beschlusslage fehlte, und zwar unsichtbar.

    ``0000-00-00`` heißt „unbekannt und damit alt": Osnabrücks Altbestände
    tragen kein Datum, und „unbekannt = vielleicht neu" führt zum Vollabzug.
    """
    return parse_date(o.get("date") or o.get("start")) or "0000-00-00"


def _juengstes(objekte: list) -> str:
    """Das jüngste Datum einer Seite — ``""``, wenn keins dasteht."""
    daten = [_datum_von(o) for o in objekte if isinstance(o, dict)]
    return max(daten) if daten else ""


def _neueste_zuerst(client: OParlClient, listen_url: str, erste: dict,
                    letzte_url: str, merker: dict) -> bool:
    """Steht das Neue auf der ERSTEN Seite? Gemessen, nicht angenommen.

    **Nicht jede ALLRIS-4-Instanz sortiert gleich.** Osnabrück, Braunschweig,
    Potsdam und Langenhagen legen das Neueste ans Ende — deshalb blättert
    dieser Adapter rückwärts. **Peine legt es an den Anfang** (gemessen
    10.09.2026: Seite 1 vom 17.12.2026, letzte Seite vom 13.09.2006). Wer die
    Richtung annimmt statt sie zu messen, erntet dort den Jahrgang 2006 und
    merkt es an nichts: Der Lauf ist grün, die Zahlen sehen plausibel aus, und
    die Stadt steht mit zwanzig Jahre alten Beschlüssen im Vergleich.

    Kostet **nichts**: Die dafür geholte letzte Seite ist beim
    Rückwärtsblättern ohnehin die erste, die gebraucht wird.
    """
    vorn = _juengstes(as_list(erste.get("data")))
    try:
        letzte = client.get_json(letzte_url, kind="list_page")
    except Exception:  # noqa: BLE001 — im Zweifel bei der bisherigen Annahme
        return False
    # Die letzte Seite ist beim Rückwärtsblättern gleich die erste, die
    # gebraucht wird — sie wird gemerkt und nicht zweimal geholt.
    merker["letzte"] = letzte
    hinten = _juengstes(as_list(letzte.get("data")))
    if not vorn or not hinten:
        return False
    return vorn > hinten


def _seiten_rueckwaerts(client: OParlClient, listen_url: str, kind: str,
                        since: str, max_pages: int = MAX_PAGES) -> Iterator[dict]:
    """Vom neuen Ende her blättern, bis das Zeitfenster verlassen ist.

    Welches Ende das neue ist, sagt ``_neueste_zuerst`` — es hängt an der
    Instanz, nicht am Hersteller.
    """
    erste = client.get_json(listen_url, kind="list_page")
    links = erste.get("links") or {}
    letzte_url = links.get("last")
    pagination = erste.get("pagination") or {}
    gesamt_seiten = pagination.get("totalPages")

    if not letzte_url or not gesamt_seiten:
        # Keine Rückwärts-Navigation: dann eben vorwärts, mit Deckel.
        for obj in as_list(erste.get("data")):
            yield obj
        naechste = links.get("next")
        seiten = 1
        while naechste and seiten < max_pages:
            d = client.get_json(naechste, kind="list_page")
            for obj in as_list(d.get("data")):
                yield obj
            naechste = (d.get("links") or {}).get("next")
            seiten += 1
        return

    merker: dict = {}
    vorwaerts = _neueste_zuerst(client, listen_url, erste, letzte_url, merker)
    if vorwaerts:
        logger.info("%s: Diese Instanz führt das Neueste auf Seite 1 — vorwärts",
                    kind)
    seiten = (range(1, int(gesamt_seiten) + 1) if vorwaerts
              else range(int(gesamt_seiten), 0, -1))

    alte = 0
    for i, n in enumerate(seiten):
        if i >= max_pages:
            logger.warning("%s: Seitendeckel erreicht (%s Seiten)", kind, max_pages)
            break
        gemerkt = merker.pop("letzte", None) if n == int(gesamt_seiten) else None
        d = gemerkt or client.get_json(_page(letzte_url, n), kind="list_page")
        objekte = as_list(d.get("data"))
        if not objekte:
            break
        for obj in objekte:
            yield obj
        # Undatiert zählt als ALT: In Osnabrück tragen die Altbestände kein
        # `date`, und „unbekannt = vielleicht neu" führt zum Vollabzug.
        alte += sum(1 for o in objekte if _datum_von(o) < since)
        if alte > ALTE_BIS_ABBRUCH:
            break


class Allris4Adapter:
    dialect = "allris4"

    # ---------------------------------------------------------------- Suche

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        if not spec.system_url:
            raise ValueError(f"{spec.id}: kein Endpunkt in der Registry")
        system = client.get_json(spec.system_url, kind="system")
        bodies_url = system.get("body")
        if not bodies_url:
            raise ValueError(f"{spec.id}: System nennt keine Bodies")
        liste = client.get_json(bodies_url, kind="body")
        bodies = as_list(liste.get("data")) or [liste]
        body = bodies[min(spec.body_index, len(bodies) - 1)]
        return {
            "body": body,
            "license": body.get("license") or system.get("license"),
            "name": body.get("name"),
        }

    # ------------------------------------------------------------- Abrufen

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]:
        url = body.get("organization")
        if not url:
            return
        seiten = 0
        while url and seiten < 80:
            d = client.get_json(url, params={"limit": 100} if seiten == 0 else None,
                                kind="list_page")
            for obj in as_list(d.get("data")):
                if isinstance(obj, dict):
                    client.raw.put_raw_object(client.body_id, "organization",
                                              obj.get("id") or "", obj)
                    yield obj
            url = (d.get("links") or {}).get("next")
            seiten += 1

    def iter_meetings(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        url = body.get("meeting")
        if not url:
            return
        for obj in _seiten_rueckwaerts(client, url, "meeting", since):
            if not isinstance(obj, dict):
                continue
            client.raw.put_raw_object(client.body_id, "meeting", obj.get("id") or "", obj)
            yield obj

    def iter_papers(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        url = body.get("paper")
        if not url:
            return
        for obj in _seiten_rueckwaerts(client, url, "paper", since):
            if not isinstance(obj, dict):
                continue
            client.raw.put_raw_object(client.body_id, "paper", obj.get("id") or "", obj)
            yield obj

    # --------------------------------------------------------- Normalisieren

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        batch = normalize_common(body_id, raw)
        # Die Beratungsfolge eines ALLRIS-Papiers nennt oft keinen
        # Tagesordnungspunkt — ohne Titelabgleich hätte kein Papier ein Ergebnis.
        ergaenzt = link_by_title(batch)
        if ergaenzt:
            logger.info("%s: %s Papier-Ergebnisse über den Titel verbunden", body_id, ergaenzt)
        return batch

    def file_url(self, file_json: dict, url: str | None) -> str | None:
        return url
