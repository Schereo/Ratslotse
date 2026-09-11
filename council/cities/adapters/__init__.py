"""Ein Adapter je Dialekt — danach sieht jede Auswertung dieselben Objekte.

Die Unterschiede der Hersteller sind hier eingesperrt: Wie man blättert, wo
die Dateien hängen, welche Adresse wirklich antwortet. Wer eine Auswertung
schreibt, merkt davon nichts mehr.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from council.cities.model import Batch
from council.cities.oparl import OParlClient
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore


class Adapter(Protocol):
    """Was jeder Dialekt können muss."""

    dialect: str

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        """``{"body": <rohes Body-Objekt>, "license": …, "name": …}``."""
        ...

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]: ...

    def iter_meetings(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]: ...

    def iter_papers(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]: ...

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        """Rohablage → Batch. **Rein**: liest nie das Netz."""
        ...


def get_adapter(dialect: str) -> Adapter:
    if dialect == "allris4":
        from council.cities.adapters.allris4 import Allris4Adapter
        return Allris4Adapter()
    if dialect == "session":
        from council.cities.adapters.session import SessionAdapter
        return SessionAdapter()
    if dialect == "allris4_html":
        from council.cities.adapters.allris4_html import Allris4HtmlAdapter
        return Allris4HtmlAdapter()
    if dialect == "allris_classic":
        from council.cities.adapters.allris_classic import AllrisClassicAdapter
        return AllrisClassicAdapter()
    if dialect == "rubin":
        from council.cities.adapters.rubin import RubinAdapter
        return RubinAdapter()
    if dialect == "oldenburg":
        from council.cities.adapters.oldenburg import OldenburgAdapter
        return OldenburgAdapter()
    raise ValueError(f"kein Adapter für Dialekt {dialect!r}")
