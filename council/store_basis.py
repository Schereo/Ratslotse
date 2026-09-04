"""Was jedes Store-Mixin von der zusammengesetzten Klasse erwartet.

**Das Problem.** ``CouncilStore`` ist seit dem Schnitt (09/2026) aus einem
Dutzend Mixins zusammengesetzt, und jedes davon greift auf ``self._conn`` zu —
eine Verbindung, die es selbst nie anlegt. Sie entsteht in
``CouncilStore.__init__``. Für einen Menschen ist das offensichtlich; für ein
Werkzeug steht in ``store_haushalt.py`` schlicht ``class HaushaltMixin:``, und
``self._conn`` ist ein Zugriff ins Leere.

Gemessen am 03.09.2026 waren das **1.007 von 1.309** Befunden der Typprüfung —
aus dieser einen Ursache. Ein Bereich, der so laut ist, wird nicht gelesen; die
echten Befunde darin sind unsichtbar. Genau deshalb stand ``council/`` bis
hierher außerhalb der Prüfung.

**Die Lösung, und warum sie zur Laufzeit nichts tut.** Der Körper steht
vollständig unter ``TYPE_CHECKING``. Beim Ausführen ist diese Klasse also
*leer* — sie legt kein Attribut an, überschreibt keine Methode und bringt
keinen Zustand mit. Ein Mixin, das von ihr erbt, verhält sich exakt wie
vorher; die einzige Änderung ist ein zusätzlicher, leerer Eintrag in der
Methodenauflösung. Für die Typprüfung dagegen steht hier, was ein Mixin
voraussetzen darf.

**Was hier NICHT hingehört.** Alles, was nur ein Mixin braucht. Diese Klasse
beschreibt den gemeinsamen Nenner der zusammengesetzten Klasse, nicht die
Kopplung zweier Nachbarn. Wer hier etwas einträgt, das ein einziges Mixin
benutzt, hat die Konstante am falschen Ort — sie gehört in das Mixin selbst
(so, wie 44 Klassenattribute im selben Zug aus ``store.py`` dorthin gewandert
sind).
"""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING


class StoreBasis:
    """Die Zusicherungen der zusammengesetzten Klasse. Zur Laufzeit leer."""

    if TYPE_CHECKING:
        from collections.abc import Iterator
        from contextlib import AbstractContextManager
        from pathlib import Path

        #: Die offene Verbindung zur Rats-Datenbank. Angelegt in
        #: ``CouncilStore.__init__``, mit ``row_factory = sqlite3.Row``.
        _conn: sqlite3.Connection

        #: Die Konten-Datenbank daneben — nur die Schema-Ecke braucht sie.
        _ratslotse_db_path: str | Path | None

        #: Sammelt gerade eine äußere ``transaktion()``?
        _sammelt: bool

        def transaktion(self) -> AbstractContextManager[None]:
            """Mehrere ``save_*``-Aufrufe zu EINER Transaktion klammern."""
            ...

        def merke_herkunft(self, h, fetched_at: str | None = None) -> int:
            """Eine ``council.herkunft.Herkunft`` eintragen, ID zurück."""
            ...

        def _beleg(self, herkunft_id: int | None) -> dict | None:
            """Fundstelle einer Zahl: Dokument, Stelle darin, Stichtag."""
            ...

        @classmethod
        def _trifft(cls, text: str | None, begriffe: list[str]) -> int:
            """Wie viele Suchbegriffe stecken in ``text``? 0 = kein Treffer."""
            ...
