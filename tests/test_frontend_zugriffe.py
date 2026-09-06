"""Das Web-Frontend ruft nur Pfade auf, die es im Vertrag gibt.

**Die Lücke.** ``tsc --noEmit`` prüft Typen, nicht Zeichenketten. Ein Pfad in
``api.get("/council/…")`` ist für den Übersetzer eine beliebige Zeichenkette;
ob das Backend ihn kennt, erfährt man erst, wenn jemand auf den Knopf drückt
und eine 404 bekommt.

Genau das lag am 02.09.2026 auf ``dev``: Der Umbau der Adressen auf Englisch
(#915) hatte in ``components/follow-button.tsx`` das POST auf
``/council/template/{kvonr}/follow`` gezogen, das DELETE daneben aber auf
``/council/vorlage/…`` stehen lassen. Folgen ging, Entfolgen nicht. Weder die
Typprüfung noch die Testsuite noch der Vertragstest konnten das sehen.

Dazu die zweite Regel dieser Schicht: **ans Backend nur über ``lib/api.ts``.**
Ein nacktes ``fetch("/api/…")`` funktioniert im Browser und zeigt in der
Capacitor-Hülle ins Nichts, weil das Bundle dort unter
``capacitor://localhost`` läuft.

Der Test steht in der Python-Suite und nicht im Frontend-Workflow, aus dem
gleichen Grund wie die Prüfung der generierten Typen: Der Frontend-Workflow
läuft nur bei Frontend-Änderungen und sähe eine Umbenennung im **Backend**
nie.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "web" / "frontend"

#: Dateien, die den Wrapper selbst bauen und deshalb roh zugreifen dürfen.
EIGENE_SACHE = {"lib/api.ts", "lib/platform.ts", "lib/api-schema.ts",
                "lib/vertrag.ts"}


def _dateien():
    for pfad in sorted(list(FRONTEND.rglob("*.ts")) + list(FRONTEND.rglob("*.tsx"))):
        if "node_modules" in pfad.parts or ".next" in str(pfad):
            continue
        # `.test.ts` sind die vitest-Logiktests neben ihrem Modul. Sie rufen
        # ABSICHTLICH Pfade auf, die es nicht gibt (`/x`), um die Hülle selbst
        # zu prüfen — welche Kopfzeilen sie setzt, was sie aus einem Fehler
        # macht. Ein Fund dort wäre immer falsch.
        #
        # Die Browsertests (`tests/e2e/*.spec.ts`) bleiben ausdrücklich DRIN:
        # Die rufen echte Endpunkte auf, und ein Pfad, den sie anfahren und den
        # es nicht mehr gibt, ist genau der Fehler, den dieser Wächter sucht.
        if pfad.name.endswith(".test.ts"):
            continue
        rel = pfad.relative_to(FRONTEND).as_posix()
        if rel in EIGENE_SACHE:
            continue
        yield rel, pfad.read_text()


def _erstes_argument(text: str, ab: int) -> str | None:
    """Liest ein String- oder Template-Literal ab Position ``ab``.

    Eingesetzte Ausdrücke werden zu ``\x00`` — auch über mehrere Zeilen und
    mit verschachtelten geschweiften Klammern. Sonst zerschneidet der Parser
    mehrzeilige Aufrufe und meldet Pfade, die es gar nicht gibt.
    """
    while ab < len(text) and text[ab] in " \t\n\r":
        ab += 1
    if ab >= len(text) or text[ab] not in "\"'`":
        return None                      # Variable statt Literal — nicht prüfbar
    anfuehrung, i, teile = text[ab], ab + 1, []
    while i < len(text):
        z = text[i]
        if z == "\\":
            i += 2
            continue
        if z == anfuehrung:
            return "".join(teile)
        if anfuehrung == "`" and text.startswith("${", i):
            tiefe, i = 1, i + 2
            while i < len(text) and tiefe:
                tiefe += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            teile.append("\x00")
            continue
        teile.append(z)
        i += 1
    return None


AUFRUF = re.compile(r"\b(?:api\.(?:get|post|put|del)|apiUrl)\s*(?:<[^<>()]*>)?\s*\(")


def _aufrufe() -> list[tuple[str, str]]:
    """``[(datei, pfad)]`` aller Aufrufe mit wörtlich hingeschriebenem Pfad."""
    aus = []
    for rel, text in _dateien():
        for m in AUFRUF.finditer(text):
            pfad = _erstes_argument(text, m.end())
            if pfad is not None:
                aus.append((rel, pfad))
    return aus


def _kandidat(roh: str) -> str | None:
    """Aus dem geschriebenen Pfad die Form, die gegen den Vertrag passen muss.

    Ein Platzhalter, der ein **ganzes** Segment füllt (``/follow/{x}/ab``),
    bleibt ein Segment. Steht er mitten in einem Segment oder hängt er hinten
    an (``/decisions${qs({…})}`` — das ist die Abfrage, nicht der Pfad), wird
    der Pfad dort abgeschnitten und muss exakt passen.
    """
    pfad = roh.split("?")[0]
    i = pfad.find("\x00")
    while i != -1:
        ganzes_segment = pfad[i - 1] == "/" and (i + 1 == len(pfad) or pfad[i + 1] == "/")
        if not ganzes_segment:
            pfad = pfad[:i]
            break
        i = pfad.find("\x00", i + 1)
    pfad = pfad.rstrip("/") or "/"
    if not pfad.startswith("/"):
        return None
    return "/api" + pfad.replace("\x00", "SEGMENT")


def _vertragsmuster() -> list[re.Pattern]:
    pfade = json.loads((WURZEL / "api" / "openapi.json").read_text())["paths"]
    return [re.compile(re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(p)) + "$")
            for p in pfade]


def test_jeder_aufgerufene_pfad_steht_im_vertrag():
    muster = _vertragsmuster()
    aufrufe = _aufrufe()
    assert len(aufrufe) > 50, (
        f"Nur {len(aufrufe)} Aufrufe gefunden — der Parser in dieser Datei "
        f"greift nicht mehr. Solange das so ist, prüft der Test nichts."
    )

    unbekannt: dict[str, set[str]] = {}
    for datei, roh in aufrufe:
        if not roh.startswith("/"):
            continue                      # zusammengesetzt, nicht auflösbar
        kandidat = _kandidat(roh)
        if kandidat and not any(rx.match(kandidat) for rx in muster):
            unbekannt.setdefault(roh.replace("\x00", "${…}"), set()).add(datei)

    assert not unbekannt, (
        "Diese Pfade ruft das Frontend auf, im API-Vertrag gibt es sie nicht:\n"
        + "\n".join(f"  {p}\n      in {', '.join(sorted(d))}"
                    for p, d in sorted(unbekannt.items()))
        + "\n\nEntweder ist der Pfad im Backend umbenannt worden und das "
          "Frontend hinkt nach, oder api/openapi.json ist veraltet "
          "(`python scripts/openapi_schnitt.py`)."
    )


def test_ans_backend_nur_ueber_den_wrapper():
    """Ein nacktes ``fetch("/api/…")`` zeigt in der App-Hülle ins Nichts."""
    treffer: list[str] = []
    roh = re.compile(r"""fetch\s*\(\s*["'`]/api/""")
    for rel, text in _dateien():
        for nr, zeile in enumerate(text.splitlines(), 1):
            if roh.search(zeile):
                treffer.append(f"{rel}:{nr}")
    assert not treffer, (
        "Diese Stellen gehen mit einem relativen Pfad direkt ans Backend:\n  "
        + "\n  ".join(treffer)
        + "\n\nDer Pfad wird im Browser aufgelöst, in der Capacitor-Hülle "
          "läuft das Bundle aber unter capacitor://localhost und der Aufruf "
          "geht ins Leere. Nimm `api.get/post/put/del` aus `lib/api.ts` — "
          "oder, wenn der Wrapper nicht passt (Streams), `apiUrl()` und "
          "`authHeaders()` aus demselben Modul."
    )
