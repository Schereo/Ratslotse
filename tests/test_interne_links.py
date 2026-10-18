"""Jeder interne Link im Web-Frontend zeigt auf eine Seite, die es gibt.

Anlass (Review 10/2026): Vier Verweise im Haushalt führten ins Leere oder auf
eine Seite, die seit August nur noch als Umleitung existierte — ``/suche``
(404), ``/haushalt/bereiche`` und ``/haushalt/streit`` (beide 08/2026 in
Sammelseiten aufgegangen). Ein Redirect in ``next.config.mjs`` hilft dabei
nicht: Im statischen Export der App gibt es ihn gar nicht (s.
``web/frontend/CLAUDE.md``), der Link muss selbst stimmen.

Geprüft werden nur **Literale** — ``href="/…"``, ``href={"/…"}``,
``href={`/…${x}`}`` (bis zum ersten Platzhalter) und ``href: "/…"`` in
Datenlisten. Zusammengebaute Adressen sieht der Test nicht; dafür gibt es die
Navigations-Browsertests. Er ist bewusst leicht: ein Muster, eine Routenliste
aus ``app/``, eine Ausnahmeliste, die in beide Richtungen gehalten wird.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "web" / "frontend"
APP = FRONTEND / "app"
QUELLEN = ("app", "components", "lib")

#: Ziele, die es nicht als Seite unter ``app/`` gibt und trotzdem geben darf.
#: Jeder Eintrag mit Grund — und der zweite Test unten meldet, wenn einer
#: nicht mehr gebraucht wird.
AUSNAHMEN: dict[str, str] = {
    "/docs": "Technik-Doku (Astro, docs-site/), vom Reverse-Proxy ausgeliefert",
}

_HREF = re.compile(
    r"""(?:\bhref\s*=\s*\{?\s*|\bhref\s*:\s*)(["'`])(/[^"'`]*)\1?""")


def _routen() -> list[re.Pattern]:
    """Alle Seiten unter ``app/`` als Muster — Routengruppen ``(x)`` fallen
    weg, dynamische Segmente ``[x]`` passen auf jedes Segment."""
    muster = []
    for page in APP.rglob("page.tsx"):
        teile = [t for t in page.parent.relative_to(APP).parts
                 if not (t.startswith("(") and t.endswith(")"))]
        rx = "".join(
            "/[^/]+" if t.startswith("[") else "/" + re.escape(t) for t in teile)
        muster.append(re.compile(f"^{rx or '/'}$"))
    return muster


def _ziel(roh: str) -> str | None:
    """Den Pfadteil eines Link-Literals: bis zum ersten Platzhalter, Query
    oder Anker. ``None`` für alles, was kein Seitenpfad ist."""
    pfad = re.split(r"[?#]|\$\{", roh, maxsplit=1)[0]
    if pfad.startswith(("//", "/api/")):
        return None
    pfad = pfad.rstrip("/") or "/"
    if roh.startswith(pfad + "${") or (pfad != "/" and roh[len(pfad):].startswith("${")):
        # „/council/${x}" — der feste Teil endet mitten im Segment; geprüft
        # wird nur, was davor als ganze Segmente steht.
        pfad = pfad.rsplit("/", 1)[0] or "/"
    return pfad


def _links() -> list[tuple[str, str]]:
    funde = []
    for ordner in QUELLEN:
        for datei in (FRONTEND / ordner).rglob("*.ts*"):
            if ".test." in datei.name or "__testhilfen" in datei.parts:
                continue
            text = datei.read_text(encoding="utf-8")
            for m in _HREF.finditer(text):
                ziel = _ziel(m.group(2))
                if ziel:
                    funde.append((str(datei.relative_to(FRONTEND)), ziel))
    return funde


def _gibt_es(ziel: str, routen: list[re.Pattern]) -> bool:
    if ziel in AUSNAHMEN or any(ziel.startswith(a + "/") for a in AUSNAHMEN):
        return True
    if (FRONTEND / "public" / ziel.lstrip("/")).is_file():
        return True
    # Ein Präfix aus einem Template („/council" aus „/council/${x}") zählt,
    # wenn es selbst eine Seite ist oder eine Seite darunter liegt.
    return any(r.match(ziel) for r in routen) or any(
        r.pattern.startswith("^" + re.escape(ziel) + "/") for r in routen)


def test_das_muster_findet_ueberhaupt_links():
    """Gegen den stillen Fall: Ein kaputtes Muster fände nichts und wäre
    damit immer grün."""
    assert len(_links()) > 200


@pytest.mark.parametrize("roh, ziel", [
    ('/haushalt/mitreden?year=${j}#streit', "/haushalt/mitreden"),
    ('/council/decision?id=${d.id}', "/council/decision"),
    ('/haushalt/${slug}', "/haushalt"),
    ('/', "/"),
    ('/api/council', None),
])
def test_ziel_aus_einem_literal(roh, ziel):
    assert _ziel(roh) == ziel


def test_jeder_interne_link_hat_eine_seite():
    routen = _routen()
    tote = sorted({f"{datei}: {ziel}" for datei, ziel in _links()
                   if not _gibt_es(ziel, routen)})
    assert not tote, (
        "Diese Links zeigen auf keine Seite unter web/frontend/app/:\n  "
        + "\n  ".join(tote)
        + "\nZiel korrigieren (eine Umleitung in next.config.mjs gibt es im "
          "App-Export nicht) — oder, wenn die Seite woanders ausgeliefert "
          "wird, mit Grund in AUSNAHMEN eintragen.")


def test_keine_ueberfluessige_ausnahme():
    routen = _routen()
    benutzt = {z for _, z in _links()}
    ueberfluessig = [a for a in AUSNAHMEN
                     if not any(z == a or z.startswith(a + "/") for z in benutzt)
                     or any(r.match(a) for r in routen)]
    assert not ueberfluessig, (
        f"AUSNAHMEN in {Path(__file__).name} braucht diese Einträge nicht mehr: "
        f"{ueberfluessig} — bitte streichen.")
