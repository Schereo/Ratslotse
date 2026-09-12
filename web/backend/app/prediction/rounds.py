"""Die Tipprunden — welche es gibt, wie sie heißen, ob sie auf der Website stehen.

**Warum eine Registry im Code und keine Tabelle mit Verwaltung.** Eine
zweite Runde kam am 12.09.2026 auf Zuruf („eine Bekannte will mit ihren
Leuten unter sich tippen"). Das ist selten, und jede Runde braucht ohnehin
einen Link, den Tim weitergibt. Ein Eintrag hier ist ein Fünf-Zeilen-PR;
eine Verwaltungsoberfläche dafür wäre mehr Fläche als Nutzen — und mehr,
was am Wahlabend schiefgehen kann.

**Was eine Runde trennt:** Spieler*innen, Tipps, Ergebnisse (Entwurf und
veröffentlicht), Ränge, Protokoll, der Cookie — alles je Runde
(``prediction_game.id`` als ``game_id``, s. ``kern/store.py``). **Was sie
teilt:** den Wahlabend selbst (dieselbe Hochrechnung, derselbe Auto-Lock
aus derselben Quelle), die Listen und OB-Kandidaturen, die Punkteregeln
und den Feature-Schalter ``tippspiel``.

**Die Hauptrunde hat keinen Parameter.** ``/tipp`` und ``/api/tipp/…`` ohne
``?runde=`` bzw. ``?round=`` sind die Ratswahl-Runde — so bleibt jede
Adresse, die schon irgendwo steht (QR, Heute-Karte, Doku), gültig. Nur die
übrigen Runden tragen den Parameter, und nur die Hauptrunde ist ``listed``:
Eine Runde, die unter sich bleiben will, erscheint auf keiner Seite, in
keiner Karte und in keiner Sitemap — ihr Link ist ihr Zugang.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Round:
    #: Kennung in Adresse (``?runde=vally``) und API (``?round=vally``).
    slug: str
    #: Titel beim Anlegen der Spielzeile — danach zählt die Zeile.
    title: str
    #: Steht die Runde auf der Website (Heute-Karte, Beamer-Fußzeile)?
    listed: bool

    @property
    def is_default(self) -> bool:
        return self.slug == DEFAULT


DEFAULT = "ratswahl"

ROUNDS: dict[str, Round] = {
    "ratswahl": Round(slug="ratswahl", title="Tippspiel zur Ratswahl", listed=True),
    # Vallys Runde (12.09.2026): eigener Kreis, eigener Link, nicht gelistet.
    "vally": Round(slug="vally", title="Vallys Tippspiel", listed=False),
}


def get(slug: str | None) -> Round | None:
    """Die Runde zu einem Parameter — ``None`` heißt Hauptrunde, ein
    unbekannter Wert ``None`` zurück (der Router macht daraus 404)."""
    return ROUNDS.get(slug or DEFAULT)


def public_path(runde: Round, basis: str = "/tipp") -> str:
    """Der Pfad, den Menschen bekommen: ``/tipp`` bzw. ``/tipp?runde=vally``."""
    return basis if runde.is_default else f"{basis}?runde={runde.slug}"
