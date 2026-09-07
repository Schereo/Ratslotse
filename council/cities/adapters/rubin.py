"""more! rubin — Freiburg, Darmstadt. Noch OParl 1.0.

Zwei Unterschiede zu den anderen Dialekten:

1. **Zeitfilter werden ignoriert**, aber ``links.last`` gibt es — also
   rückwärts blättern wie bei ALLRIS, mit echtem ``date`` als Abbruch.
2. **Der Volltext liegt schon im Dateiobjekt** (``mainFile.text``). Das spart
   den PDF-Abruf und die Extraktion; ``pipeline.extract`` erkennt das am
   Extraktor-Namen ``oparl-text``.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator

from council.cities.adapters._common import normalize_common
from council.cities.adapters.allris4 import _seiten_rueckwaerts
from council.cities.model import Batch
from council.cities.oparl import OParlClient, as_list
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.rubin")

#: Extraktor-Name für Texte, die die Schnittstelle selbst mitliefert.
OPARL_TEXT = "oparl-text"


class RubinAdapter:
    dialect = "rubin"

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        if not spec.system_url:
            raise ValueError(f"{spec.id}: kein Endpunkt in der Registry")
        system = client.get_json(spec.system_url, kind="system")
        liste = client.get_json(system["body"], kind="body")
        bodies = as_list(liste.get("data")) or [liste]
        body = bodies[min(spec.body_index, len(bodies) - 1)]
        return {"body": body, "license": body.get("license") or system.get("license"),
                "name": body.get("name")}

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]:
        url = body.get("organization")
        if not url:
            return
        seiten = 0
        while url and seiten < 40:
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
            if isinstance(obj, dict):
                client.raw.put_raw_object(client.body_id, "meeting", obj.get("id") or "", obj)
                yield obj

    def iter_papers(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        url = body.get("paper")
        if not url:
            return
        for obj in _seiten_rueckwaerts(client, url, "paper", since):
            if isinstance(obj, dict):
                client.raw.put_raw_object(client.body_id, "paper", obj.get("id") or "", obj)
                yield obj

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        return normalize_common(body_id, raw)

    def file_url(self, file_json: dict, url: str | None) -> str | None:
        return url

    def inline_texts(self, raw: CitiesStore, body_id: str) -> list[tuple[str, str]]:
        """``(file_id, text)`` für alles, was die Schnittstelle mitgeliefert hat."""
        out: list[tuple[str, str]] = []
        for p in raw.raw_objects(body_id, "paper"):
            for key in ("mainFile", "auxiliaryFile"):
                for datei in as_list(p.get(key)):
                    if isinstance(datei, dict) and datei.get("text") and datei.get("id"):
                        out.append((datei["id"], datei["text"]))
        return out
