"""Somacos Session — Münster, Magdeburg, Köln, Dresden, Wuppertal, Düsseldorf.

Drei Eigenheiten, gemessen am 07.09.2026:

1. **Der ``next``-Link verliert den Zeitfilter ab Seite 3.** Seite 1 und 2
   tragen ``created_since`` im Folge-Link, danach fehlt er. Wer ``next``
   folgt, blättert ab da unbemerkt den **Gesamtbestand seit 1997** ab und
   hält das Ergebnis für gefiltert — Münster lieferte so 6.000 Papiere, von
   denen 376 ins Fenster fielen. Deshalb wird ``page=N`` samt Filter bei
   **jeder** Anfrage selbst gesetzt.
2. **Kein ``mainFile``.** Das Hauptdokument hängt unter ``auxiliaryFile`` und
   ist nur am Namen erkennbar (``file_role`` in ``model.py``).
3. **Magdeburgs Datei-URLs antworten 404** — sowohl ``accessUrl`` als auch
   ``downloadUrl``, bei jedem geprüften Dokument. Dieselben Dateien liegen
   unter ``getfile.asp?id=<Zahl>&type=do``. Der Umbau steht in ``FILE_URL_FIX``:
   Die nächste Stadt mit kaputten Adressen ist eine Zeile.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from council.cities.adapters._common import link_by_title, normalize_common
from council.cities.model import Batch
from council.cities.oparl import OParlClient, as_list
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.session")

PAGE_SIZE = 100
MAX_PAGES = 80


def _magdeburg_url(datei: dict, url: str | None) -> str | None:
    """``…/downloadfiles/a/00692749.pdf`` (404) → ``…/getfile.asp?id=692749&type=do``."""
    name = datei.get("fileName") or ""
    m = re.search(r"(\d+)\.pdf$", name) or re.search(r"(\d+)\.pdf$", url or "")
    if not m:
        return url
    return f"https://ratsinfo.magdeburg.de/getfile.asp?id={int(m.group(1))}&type=do"


#: Host-Präfix → Umbau der Datei-Adresse. Greift nur, wo gemessen nötig.
FILE_URL_FIX = {
    "https://ratsinfo.magdeburg.de/": _magdeburg_url,
}


def url_fix_for(body: dict):
    kennung = str(body.get("id") or "")
    for prefix, fn in FILE_URL_FIX.items():
        if kennung.startswith(prefix):
            return fn
    return None


def _seiten_vorwaerts(client: OParlClient, listen_url: str, since: str,
                      max_pages: int = MAX_PAGES) -> Iterator[dict]:
    """Vorwärts blättern — mit dem Filter bei JEDER Anfrage.

    Nicht ``links.next`` folgen: Der verliert ``created_since`` ab Seite 3.
    """
    for seite in range(1, max_pages + 1):
        d = client.get_json(listen_url, params={
            "limit": PAGE_SIZE,
            "created_since": f"{since}T00:00:00+02:00",
            "page": seite,
        }, kind="list_page")
        objekte = as_list(d.get("data"))
        if not objekte:
            return
        yield from objekte
        if len(objekte) < PAGE_SIZE:
            return
    logger.warning("Seitendeckel (%s) erreicht bei %s", max_pages, listen_url)


class SessionAdapter:
    dialect = "session"

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        if not spec.system_url:
            raise ValueError(f"{spec.id}: kein Endpunkt in der Registry")
        system = client.get_json(spec.system_url, kind="system")
        liste = client.get_json(system["body"], kind="body")
        bodies = as_list(liste.get("data")) or [liste]
        body = bodies[min(spec.body_index, len(bodies) - 1)]
        return {
            "body": body,
            "license": body.get("license") or system.get("license"),
            "name": body.get("name"),
        }

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]:
        url = body.get("organization")
        if not url:
            return
        for seite in range(1, 20):
            d = client.get_json(url, params={"limit": PAGE_SIZE, "page": seite}, kind="list_page")
            objekte = as_list(d.get("data"))
            if not objekte:
                return
            for obj in objekte:
                if isinstance(obj, dict):
                    client.raw.put_raw_object(client.body_id, "organization",
                                              obj.get("id") or "", obj)
                    yield obj
            if len(objekte) < PAGE_SIZE:
                return

    def iter_meetings(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        url = body.get("meeting")
        if not url:
            return
        for obj in _seiten_vorwaerts(client, url, since):
            if not isinstance(obj, dict):
                continue
            # Manche Instanzen (Magdeburg) liefern die Sitzung in der Liste
            # OHNE Tagesordnungspunkte. Ohne sie gäbe es keine Ergebnisse —
            # dann lohnt der Einzelabruf.
            if not obj.get("agendaItem") and obj.get("id"):
                try:
                    obj = client.get_json(obj["id"], kind="meeting")
                except Exception as e:      # noqa: BLE001 — eine Sitzung, kein Lauf
                    logger.info("Sitzung nicht einzeln abrufbar: %s (%s)",
                                obj.get("id"), type(e).__name__)
            client.raw.put_raw_object(client.body_id, "meeting", obj.get("id") or "", obj)
            yield obj

    def iter_papers(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        url = body.get("paper")
        if not url:
            return
        for obj in _seiten_vorwaerts(client, url, since):
            if not isinstance(obj, dict):
                continue
            client.raw.put_raw_object(client.body_id, "paper", obj.get("id") or "", obj)
            yield obj

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        # Der Umbau der Datei-Adressen hängt an der Stadt, nicht am Objekt —
        # die Body-Kennung steht in jedem Rohobjekt.
        fix = None
        for obj in raw.raw_objects(body_id, "paper"):
            fix = url_fix_for({"id": obj.get("body") or obj.get("id") or ""})
            break
        batch = normalize_common(body_id, raw, url_fix=fix)
        # Münsters Beratungsfolge nennt den Tagesordnungspunkt, Magdeburgs
        # nicht — derselbe Notnagel wie bei ALLRIS. Er überspringt alles,
        # was schon verbunden ist, und kostet deshalb nichts, wo er nicht
        # gebraucht wird.
        ergaenzt = link_by_title(batch)
        if ergaenzt:
            logger.info("%s: %s Papier-Ergebnisse über den Titel verbunden", body_id, ergaenzt)
        return batch

    def file_url(self, file_json: dict, url: str | None) -> str | None:
        return url
