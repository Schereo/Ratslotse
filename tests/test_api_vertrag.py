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
    ("get", "/api/council/sitzungspause"),
    ("get", "/api/council/heute"),
    ("get", "/api/council/wochenvorschau"),
    ("get", "/api/council/haushalt"),
    ("get", "/api/council/session/{ksinr}"),
    ("get", "/api/council/decision/{decision_id}"),
    ("get", "/api/council/qa-share/{token}"),
    ("get", "/api/council/deep-research/{job_id}"),
    ("get", "/api/council/analysis"),
    ("get", "/api/council/trends"),
    ("get", "/api/council/public-stats"),
    ("get", "/api/council/entity/{slug}"),
    ("get", "/api/council/person/{slug}"),
    ("get", "/api/council/person/{slug}/wortbeitraege"),
    ("get", "/api/admin/llm-usage"),
    ("get", "/api/admin/users/{user_id}"),
    ("put", "/api/admin/place-candidates/{location_slug}"),
    ("get", "/api/social/sitzungen/{tag}"),
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

    Ausgenommen bleibt, was sich nicht zusammenziehen LÄSST: ein ``$ref``
    neben ``null``. Diese vier sind bekannt und in der App von Hand zu
    ergänzen — wächst die Liste, ist das eine bewusste Entscheidung, kein
    Versehen.
    """
    import json

    bekannt = {
        "Abzeichen.progress",
        "AbzeichenStand.next",
        "QaSharePartei.kernaussage",
        "QuizTagesrunde.done",
    }
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
