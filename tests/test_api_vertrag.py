"""Der API-Vertrag: Jeder Endpunkt muss seine Antwortform beschreiben.

**Warum das ein Test ist und keine Konvention.** Es gibt zwei Frontends
(Next.js-Web und die iOS-App), die featuregleich bleiben sollen. Ein Handler
mit ``-> dict`` erzeugt im OpenAPI nur ``{"additionalProperties": true,
"type": "object"}`` — daraus kann kein Generator Swift- oder TypeScript-Typen
ableiten, und kein PR-Diff zeigt, dass sich ein Feld geändert hat. Ohne Gate
schleicht sich das mit jedem neuen Endpunkt zurück; die Formen stehen deshalb
in ``web/backend/app/antworten.py`` und dieser Test hält sie dort fest.

Die Ausnahmeliste unten ist keine Schlupflücke, sondern die sichtbare
Restschuld: Diese Nutzlasten reicht der Handler unverändert aus dem Store
durch (breite ``SELECT``-Zeilen). Sie sind absichtlich offen, weil eine
unvollständige Aufzählung Felder STILL aus der Antwort entfernen würde — ein
TypedDict filtert, was es nicht kennt. Wer eine davon sauber typisiert,
streicht ihren Eintrag hier. Wer einen NEUEN Endpunkt ohne Form baut, wird
rot.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")


# Nutzlasten, die direkt aus einer breiten Store-Abfrage kommen. Sie tragen in
# `antworten.py` einen sprechenden Namen, aber (noch) keine Felder.
OFFEN = {
    ("get", "/api/council/places"),
    ("get", "/api/council/wochenvorschau"),
    ("get", "/api/council/haushalt"),
    ("get", "/api/council/session/{ksinr}"),
    ("get", "/api/council/decision/{decision_id}"),
    ("get", "/api/council/qa-share/{token}"),
    ("get", "/api/council/deep-research/{job_id}"),
    ("get", "/api/council/public-stats"),
    ("get", "/api/council/entity/{slug}"),
    ("get", "/api/council/person/{slug}"),
    ("get", "/api/council/person/{slug}/wortbeitraege"),
    ("get", "/api/admin/llm-usage"),
    ("get", "/api/admin/users/{user_id}"),
    ("put", "/api/admin/place-candidates/{location_slug}"),
}

# Kein JSON-Body: zwei SSE-Ströme und eine Bilddatei.
KEIN_JSON = {
    ("post", "/api/council/ask"),
    ("get", "/api/council/deep-research/{job_id}/events"),
    ("get", "/api/council/plan-bild/{document_id}"),
}


def _beschrieben(schema: dict | None) -> bool:
    """Trägt das Schema echte Felder — oder nur „irgendein Objekt"?"""
    if not schema:
        return False
    if "$ref" in schema or "properties" in schema:
        return True
    if schema.get("type") == "array":
        return _beschrieben(schema.get("items", {}))
    for k in ("anyOf", "allOf", "oneOf"):
        if k in schema:
            return any(_beschrieben(x) for x in schema[k])
    return False


@pytest.fixture(scope="module")
def endpunkte():
    from app.main import app

    spec = app.openapi()
    out = []
    for pfad, ops in spec["paths"].items():
        for methode, op in ops.items():
            if methode not in ("get", "post", "put", "patch", "delete"):
                continue
            antworten = op.get("responses", {})
            schema = None
            for code in ("200", "201", "202"):
                treffer = antworten.get(code, {}).get("content", {}).get("application/json", {})
                if treffer:
                    schema = treffer.get("schema")
                    break
            leer = "204" in antworten and schema is None
            out.append((methode, pfad, schema, leer))
    return out


def test_jeder_endpunkt_beschreibt_seine_antwort(endpunkte):
    """Neue Endpunkte ohne Antwortform sind ein Fehler, kein Schönheitsmakel."""
    fehlend = [
        f"{m.upper()} {p}"
        for m, p, schema, leer in endpunkte
        if not leer and not _beschrieben(schema)
        and (m, p) not in OFFEN and (m, p) not in KEIN_JSON
    ]
    assert not fehlend, (
        "Diese Endpunkte liefern keine beschriebene Antwortform. Trag ihre Form in "
        "web/backend/app/antworten.py ein und annotiere den Handler damit "
        "(nicht `-> dict`):\n  " + "\n  ".join(sorted(fehlend))
    )


def test_ausnahmeliste_ist_nicht_veraltet(endpunkte):
    """Wer eine offene Nutzlast typisiert, soll ihren Eintrag auch streichen —
    sonst wächst die Liste nie wieder."""
    beschrieben = {(m, p) for m, p, schema, leer in endpunkte if _beschrieben(schema)}
    ueberfluessig = sorted(f"{m.upper()} {p}" for m, p in (OFFEN & beschrieben))
    assert not ueberfluessig, (
        "Diese Endpunkte stehen in OFFEN, sind aber inzwischen typisiert — "
        "bitte aus der Liste streichen:\n  " + "\n  ".join(ueberfluessig)
    )


def test_bekannte_endpunkte_sind_nicht_verschwunden(endpunkte):
    """Die Listen oben nennen echte Pfade — ein Tippfehler oder ein
    umbenannter Endpunkt soll auffallen, nicht stillschweigend durchrutschen."""
    vorhanden = {(m, p) for m, p, _, _ in endpunkte}
    verwaist = sorted(f"{m.upper()} {p}" for m, p in ((OFFEN | KEIN_JSON) - vorhanden))
    assert not verwaist, (
        "Diese Einträge in OFFEN/KEIN_JSON gibt es als Endpunkt nicht (mehr):\n  "
        + "\n  ".join(verwaist)
    )


def test_eingecheckter_vertrag_passt_zum_code():
    """``api/openapi.json`` ist der Vertrag, aus dem beide Clients generieren.

    Läuft er dem Code hinterher, generiert die iOS-Seite gegen eine Fassung,
    die es nicht mehr gibt — deshalb ein Test und keine Bitte im Review.
    """
    import subprocess

    wurzel = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, "scripts/openapi_schnitt.py", "--pruefen"],
                       cwd=wurzel, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_generierte_frontend_typen_passen_zum_vertrag():
    """``web/frontend/lib/api-schema.ts`` wird aus ``api/openapi.json``
    erzeugt — veraltet also, sobald sich das BACKEND ändert.

    Warum der Test hier und nicht im Frontend-Workflow: Der läuft nur bei
    Frontend-Änderungen und sähe genau diese Drift nie. Geprüft wird die
    SHA-256-Zeile, die der Generator ans Dateiende schreibt; damit braucht
    diese Prüfung kein Node.
    """
    import hashlib

    wurzel = Path(__file__).resolve().parents[1]
    vertrag = wurzel / "api" / "openapi.json"
    typen = wurzel / "web" / "frontend" / "lib" / "api-schema.ts"
    assert typen.exists(), "lib/api-schema.ts fehlt — `npm run api:typen` im Frontend laufen lassen."

    summe = hashlib.sha256(vertrag.read_bytes()).hexdigest()
    letzte = typen.read_text().rstrip().splitlines()[-1]
    assert letzte == f"// vertrag-sha256: {summe}", (
        "Die generierten Frontend-Typen passen nicht zu api/openapi.json.\n"
        "  cd web/frontend && npm run api:typen   # neu erzeugen und mitcommitten"
    )


def test_nullable_felder_sind_swift_lesbar():
    """Optionale Felder müssen als ``type: [T, "null"]`` im Vertrag stehen.

    Pydantic schreibt sie als ``anyOf`` mit einem ``null``-Zweig — gültiges
    OpenAPI 3.1, aber ``swift-openapi-generator`` lässt solche Eigenschaften
    STILL weg (gemessen 30.08.2026: 139 Felder in 55 Schemata, u. a.
    ``GespraecheListe.einstellung``). ``scripts/openapi_schnitt.py`` zieht sie
    deshalb zusammen; dieser Test hält fest, dass das auch weiter passiert.

    Auch ``$ref`` neben ``null`` fällt darunter — der Schnitt schreibt solche
    Objekte aus, statt sie zu verweisen, weil der Generator sie sonst ebenfalls
    weglässt (``Merkeintrag.session`` war genau dieser Fall).
    """
    import json

    # Leer, seit der Schnitt auch `anyOf: [{$ref}, null]` ausschreibt. Wächst
    # die Menge wieder, ist das eine bewusste Entscheidung — kein Versehen.
    bekannt: set[str] = set()
    spec = json.loads((Path(__file__).resolve().parents[1] / "api" / "openapi.json").read_text())
    offen = set()
    for name, s in spec["components"]["schemas"].items():
        for feld, p in (s.get("properties") or {}).items():
            zweige = p.get("anyOf")
            if isinstance(zweige, list) and {"type": "null"} in zweige:
                offen.add(f"{name}.{feld}")

    neu = offen - bekannt
    assert not neu, (
        "Diese nullable Felder stehen als `anyOf` im Vertrag und fehlen damit im "
        "Swift-Generat:\n  " + "\n  ".join(sorted(neu)) +
        "\nEntweder zusammenziehbar machen (scripts/openapi_schnitt.py) oder "
        "bewusst in `bekannt` aufnehmen."
    )
    verschwunden = bekannt - offen
    assert not verschwunden, (
        "Diese Einträge stehen in `bekannt`, sind aber nicht mehr offen — bitte "
        "streichen:\n  " + "\n  ".join(sorted(verschwunden))
    )


def test_zeilen_typen_kennen_alle_spalten_ihrer_tabelle():
    """``Beschlusszeile``/``Sitzungszeile`` zählen Spalten auf — das ist nur
    sicher, solange die Aufzählung vollständig bleibt.

    Ein TypedDict ENTFERNT, was es nicht kennt. Bekäme ``council_decisions``
    eine neue Spalte, verschwände sie stillschweigend aus der API — kein
    Fehler, nur fehlende Daten in Web und App. Dieser Test macht daraus einen
    roten Lauf.
    """
    import tempfile
    from typing import get_type_hints

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.antworten import Beschlusszeile, Sitzungszeile
    from council.store import CouncilStore

    with tempfile.TemporaryDirectory() as d:
        store = CouncilStore(Path(d) / "council.sqlite")
        try:
            spalten = {
                "council_decisions": {r[1] for r in store._conn.execute(
                    "PRAGMA table_info(council_decisions)")},
                "council_sessions": {r[1] for r in store._conn.execute(
                    "PRAGMA table_info(council_sessions)")},
            }
        finally:
            store.close()

    for typ, tabelle in ((Beschlusszeile, "council_decisions"),
                         (Sitzungszeile, "council_sessions")):
        deklariert = set(get_type_hints(typ, include_extras=True))
        fehlend = spalten[tabelle] - deklariert
        assert not fehlend, (
            f"{typ.__name__} kennt diese Spalten von {tabelle} nicht — sie fallen "
            f"damit still aus der API:\n  " + "\n  ".join(sorted(fehlend)) +
            "\nIn web/backend/app/antworten.py ergänzen (als NotRequired)."
        )


def test_keine_wirkungslosen_migrationspaare():
    """Ein Umbenennungspaar ``("x", "x")`` tut nichts — und fällt sonst nie auf.

    Beim Umbau auf englische Namen ist mir das DREIMAL passiert: Ein
    Suchen-und-Ersetzen über die Datei nimmt den ALTEN Namen in der
    Migrationsliste mit, und aus ``("stadtteil", "district")`` wird
    ``("district", "district")``. Frische Datenbanken legen ohnehin das neue
    Schema an, also bleibt alles grün — nur BESTEHENDE Datenbanken werden nie
    migriert und behalten still die deutschen Spalten. Einmal ist es so schon
    in einen Merge gerutscht (#859, behoben).

    Deshalb dieser Test: Er liest die Quelltexte und meldet jedes Paar, dessen
    beide Seiten gleich sind.
    """
    import re

    wurzel = Path(__file__).resolve().parents[1]
    muster = re.compile(r'\(\s*"([a-z_]+)"\s*,\s*"\1"\s*\)')
    treffer = []
    for datei in (wurzel / "kern" / "store.py", wurzel / "council" / "store.py"):
        for nr, zeile in enumerate(datei.read_text().splitlines(), 1):
            if muster.search(zeile):
                treffer.append(f"{datei.relative_to(wurzel)}:{nr}: {zeile.strip()}")

    assert not treffer, (
        "Diese Umbenennungspaare sind wirkungslos — vermutlich hat ein "
        "Suchen-und-Ersetzen den alten Namen mitgenommen:\n  " + "\n  ".join(treffer)
    )


#: Pfade, die von AUSSERHALB dieses Repos aufgerufen werden. Eine URL ist eine
#: öffentliche Schnittstelle, kein Bezeichner — sie wandert bei einer
#: Umbenennung nicht mit.
#:
#: Die vier ``/social/``-Pfade ruft der Instagram-Bot (Repo ratslotse-social,
#: ``ratslotse_social/quellen.py``) über HTTP auf. Genau das ist beim
#: Beschluss-Schnitt schiefgegangen: Aus ``/hoechste-beschluss-id`` wurde
#: ``/hoechste-official_text-id``, der Bot rief ins Leere, und weil er in
#: einem anderen Repo lebt, wurde dort nichts rot.
#:
#: Nicht in der Liste: ``/api/social/orte``. Den Pfad ruft der Bot zwar auf,
#: aber dieses Repo hat ihn NIE angeboten (keine Spur in der Historie) — der
#: Bot fällt dort auf seinen direkten Datenbankweg zurück. Das ist ein Befund
#: für das andere Repo, kein Ziel für einen Wächter hier.
OEFFENTLICHE_PFADE = (
    "/api/social/hoechste-beschluss-id",
    "/api/social/neue-beschluesse",
    "/api/social/wochenvorschau",
)


def test_oeffentliche_pfade_bleiben_stehen(endpunkte):
    """Pfade mit Aufrufern ausserhalb dieses Repos dürfen sich nicht ändern.

    Wer einen davon wirklich umbenennen will, zieht den Aufrufer mit nach —
    und ändert diese Liste bewusst, nicht als Beifang eines Ersetzens.
    """
    vorhanden = {p for _, p, _, _ in endpunkte}
    fehlend = [p for p in OEFFENTLICHE_PFADE if p not in vorhanden]
    assert not fehlend, (
        "Diese Pfade werden von ausserhalb aufgerufen und gibt es nicht mehr:\n  "
        + "\n  ".join(fehlend)
        + "\nEine URL ist eine öffentliche Schnittstelle. Entweder den Pfad "
          "zurückbenennen oder den Aufrufer (ratslotse-social) mitziehen."
    )
