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
teilt:** den Wahlabend ihrer Wahl (dieselbe Hochrechnung, derselbe Auto-Lock
aus derselben Quelle), die Punkteregeln und den Feature-Schalter
``tippspiel``.

**Seit 14.09.2026 nennt eine Runde ihre WAHL** (``election``). Vorher gab es
nur „den Wahlabend", und der ist beim nächsten Mal ein anderer: Eine Runde
von 2026 hätte 2031 gegen die neuen Zahlen gepunktet und jeden Rang
rückwirkend verschoben.

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
    #: Auf WELCHE Wahl getippt wird (Slug aus ``kommunalwahl/wahlen/``).
    #: ``None`` heißt „die aktive Ratswahl" — bis 14.09.2026 gab es keine
    #: andere Möglichkeit, und beide bestehenden Runden meinen sie.
    election: str | None = None
    #: Wer mitspielen darf: ``oeffentlich`` (jede*r mit dem Link, ohne Konto)
    #: oder ``konto`` (nur angemeldet, ein Tipp je Konto). Die beiden Runden
    #: zur Ratswahl sind öffentlich und bleiben es — ihr QR-Code hing an einer
    #: Leinwand. Eine Runde, die von selbst zu einer Wahl entsteht, startet
    #: dagegen bei ``konto``; der Admin kann sie freigeben.
    visibility: str = "oeffentlich"

    @property
    def is_default(self) -> bool:
        return self.slug == DEFAULT


DEFAULT = "ratswahl"

ROUNDS: dict[str, Round] = {
    "ratswahl": Round(slug="ratswahl", title="Tippspiel zur Ratswahl", listed=True),
    # Vallys Runde (12.09.2026): eigener Kreis, eigener Link, nicht gelistet.
    "vally": Round(slug="vally", title="Vallys Tippspiel", listed=False),
    # Die OB-Stichwahl am 27.09.2026 (Tims Auftrag 19.09.2026: „schon
    # freischalten"). Öffentlich wie die Ratswahl-Runden — Name statt Konto,
    # dazu freiwillig die Parteizugehörigkeit — und mit kurzem Slug, weil die
    # Adresse geteilt und getippt wird: ``/tipp?runde=stichwahl``. Der Admin
    # kann sie wie jede Runde wieder auf Konten beschränken.
    "stichwahl": Round(slug="stichwahl", title="Tippspiel zur OB-Stichwahl", listed=True,
                       election="ob-stichwahl-2026"),
}


def fuer_wahl(slug: str) -> Round | None:
    """Die Runde, die zu einer Wahl gehört — angelegt, sobald jemand sie öffnet.

    Tims Wunsch vom 14.09.2026: „wollen wir auch immer direkt ein öffentliches
    Tippspiel verlinken?" Ja — und dafür braucht es keinen Eintrag von Hand.
    Steht eine Wahl in ``kommunalwahl/wahlen/``, gibt es ihre Runde unter
    demselben Slug (``/tipp?runde=ob-stichwahl-2026``).

    **Sie startet bei ``konto``**, also nur für Angemeldete. Ein Tippspiel, das
    ohne Zutun entsteht und sofort öffentlich ist, wäre eine Einladung an
    jeden Bot; der Admin schaltet es frei, wenn es so weit ist.

    Einträge in ``ROUNDS`` gehen vor — sowohl unter ihrem eigenen Slug als
    auch unter dem ihrer Wahl: ``ratswahl`` ist die Hauptrunde und bleibt
    öffentlich, auch wenn die Wahl ``ratswahl-2026`` heißt.
    """
    from ..election import elections

    wahl = elections.get(slug)
    if wahl is None or wahl.status == "entwurf":
        return None
    # **Eine von Hand angelegte Runde geht vor.** Die Hauptrunde ``ratswahl``
    # meint dieselbe Wahl wie ``ratswahl-2026`` — sie hat nur einen kürzeren
    # Namen, weil ihre Adresse seit dem Wahlabend im Umlauf ist. Ohne diesen
    # Vorrang zeigte die Übersicht auf eine LEERE zweite Runde, während die
    # laufende mit ihren Mitspielenden daneben stünde.
    aktiv = elections.active().slug
    for eintrag in ROUNDS.values():
        if eintrag.listed and (eintrag.election or aktiv) == wahl.slug:
            return eintrag
    return Round(slug=wahl.slug, title=f"Tippspiel zur {wahl.short_title}",
                 listed=True, election=wahl.slug, visibility="konto")


def get(slug: str | None) -> Round | None:
    """Die Runde zu einem Parameter — ``None`` heißt Hauptrunde, ein
    unbekannter Wert ``None`` zurück (der Router macht daraus 404).

    Gesucht wird erst in ``ROUNDS`` (von Hand angelegt), dann unter den
    Wahlen: Jede Wahl bringt ihre eigene Runde mit."""
    gewaehlt = slug or DEFAULT
    return ROUNDS.get(gewaehlt) or fuer_wahl(gewaehlt)


def public_path(runde: Round, basis: str = "/tipp") -> str:
    """Der Pfad, den Menschen bekommen: ``/tipp`` bzw. ``/tipp?runde=vally``."""
    return basis if runde.is_default else f"{basis}?runde={runde.slug}"
