"""Der Split von „Meine Themen" und „Ausschuss-Abos" (28.08.2026).

Die Abos hingen als Block unter den Themen: kein eigener Weg dorthin, und die
Themen bekamen nur so viel Platz, wie über dem Block übrig blieb. Jetzt sind es
zwei Seiten. Diese Tests halten die drei Stellen fest, an denen so ein Split
sonst still etwas kaputt macht — Deep-Links aus alten Mails, der Weg über die
Navigation, und die Mail selbst.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lies(rel: str) -> str:
    return (ROOT / "web" / "frontend" / rel).read_text(encoding="utf-8")


def test_abo_seite_existiert():
    for datei in ("app/(app)/abos/page.tsx", "app/(app)/abos/view.tsx"):
        assert (ROOT / "web" / "frontend" / datei).exists(), datei


def test_alter_deep_link_aus_den_mails_landet_weiter_am_ziel():
    """Tagesordnungs-Mails tragen „Gremien-Abos verwalten" als
    ``/topics?zeig=abos`` — bis zum Split hob das den Block auf der
    Themen-Seite hervor. Diese Mails sind draußen und werden noch geöffnet:
    Ohne Weiterleitung landete der Klick auf einer Seite, die keine Abos mehr
    kennt."""
    view = _lies("app/(app)/topics/view.tsx")
    assert 'sp.get("zeig") === "abos"' in view
    assert 'router.replace("/abos")' in view


def test_neue_mails_zeigen_direkt_auf_die_abo_seite():
    mail = (ROOT / "kern" / "digest_email.py").read_text(encoding="utf-8")
    assert 'link("/abos", "Gremien-Abos verwalten")' in mail
    assert '"/topics?zeig=abos"' not in mail


def test_navigation_fuehrt_zu_den_abos():
    """Auf beiden Wegen: Seitenleiste am Desktop, „Mehr"-Blatt auf dem Telefon.
    Die Tab-Leiste bleibt fünfteilig (Design 9a③), die Abos wohnen deshalb
    mobil hinter „Mehr" — und der Tab muss dort als aktiv gelten, sonst steht
    man auf der Abo-Seite ohne jede Markierung in der Leiste."""
    nav = _lies("components/nav.tsx")
    assert 'href: "/abos"' in nav                       # Seitenleiste
    assert 'href="/abos"' in nav                        # „Mehr"-Blatt
    assert '"/abos", "/bookmarks"' in nav               # MEHR_AKTIV


def test_beide_seiten_verweisen_aufeinander():
    """Wer Themen sucht und Abos findet (oder umgekehrt), soll nicht über die
    Navigation zurück müssen — der Split darf die beiden nicht auseinander-
    reißen, nur trennen."""
    assert 'href="/abos"' in _lies("app/(app)/topics/view.tsx")
    assert 'href="/topics"' in _lies("app/(app)/abos/view.tsx")
