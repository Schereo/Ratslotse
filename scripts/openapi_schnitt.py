#!/usr/bin/env python3
"""Schreibt das OpenAPI-Schema der API nach ``api/openapi.json``.

**Wozu.** Die Datei ist der eingecheckte Vertrag zwischen Backend und den
beiden Frontends (Web und iOS). Zwei Dinge fallen dadurch ab:

1. **Schnittstellenänderungen stehen im PR-Diff.** Wer ein Feld umbenennt,
   sieht es beim Review — und merkt, dass die App das auch braucht. Ohne die
   Datei fällt so etwas erst auf, wenn ein Client nichts mehr anzeigt.
2. **Beide Clients können daraus generieren** statt Typen abzuschreiben:
   ``openapi-typescript`` fürs Web, ``swift-openapi-generator`` für iOS.

Aufruf::

    python scripts/openapi_schnitt.py            # schreibt api/openapi.json
    python scripts/openapi_schnitt.py --pruefen  # nur vergleichen (CI, Exit 1)

Das Schema hängt an keiner Datenbank — die Endpunkte werden nur eingelesen,
nicht aufgerufen. ``WEB_JWT_SECRET`` wird gesetzt, weil die Konfiguration es
beim Import verlangt; ein Wert aus der Umgebung hätte hier keine Wirkung.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
ZIEL = WURZEL / "api" / "openapi.json"


# Schlüssel, die einen Zweig zu etwas anderem als einem schlichten `type`
# machen — solche Zweige lassen sich nicht in ein `type`-Array zusammenziehen.
_KEIN_TYP = {"anyOf", "allOf", "oneOf", "$ref", "not"}


def _nullbar_zusammenziehen(knoten):
    """``anyOf: [{type: T}, {type: null}]`` → ``{type: [T, "null"]}``.

    **Warum das sein muss.** Pydantic/FastAPI schreiben ein optionales Feld als
    ``anyOf`` mit einem ``null``-Zweig. Das ist gültiges OpenAPI 3.1 — aber
    ``swift-openapi-generator`` (1.x) lässt solche Eigenschaften einfach WEG,
    still, samt CodingKeys. Gemessen am 30.08.2026: **139 Felder in 55
    Schemata** fehlten im erzeugten Swift-Code, darunter ``ConversationList
    .saves_conversations`` und ``AdminJob.age_h``. Eine iOS-App daraus hätte Felder
    verloren, ohne dass irgendwo etwas rot geworden wäre.

    Die andere 3.1-Schreibweise — ein ``type``-Array — versteht der Generator.
    Sie sagt dasselbe; Einschränkungen (``minimum``, ``maxLength`` …) reisen
    mit. Nach dem Umbau fehlten noch 4 Felder, alle vom Muster
    ``anyOf: [{$ref}, null]``, das sich nicht zusammenziehen lässt (s.
    ``offene_nullable``). Für TypeScript ändert sich nichts: ``openapi-
    typescript`` erzeugt aus beiden Formen dasselbe ``T | null``.
    """
    if isinstance(knoten, dict):
        zweige = knoten.get("anyOf")
        if isinstance(zweige, list) and len(zweige) == 2 and {"type": "null"} in zweige:
            rest = next(z for z in zweige if z != {"type": "null"})
            if isinstance(rest, dict) and "type" in rest and not (set(rest) & _KEIN_TYP):
                neu = dict(rest)
                neu["type"] = [rest["type"], "null"]
                for field in ("title", "description"):
                    if field in knoten:
                        neu.setdefault(field, knoten[field])
                return _nullbar_zusammenziehen(neu)
        return {k: _nullbar_zusammenziehen(v) for k, v in knoten.items()}
    if isinstance(knoten, list):
        return [_nullbar_zusammenziehen(x) for x in knoten]
    return knoten


def _nullbare_refs_inlinen(spec: dict) -> dict:
    """``anyOf: [{$ref: X}, {type: null}]`` → X ausgeschrieben mit
    ``type: [..., "null"]``.

    Der Swift-Generator lässt auch diese Form weg — und hier wiegt das
    schwerer als bei einem Skalar: Es sind ganze Objekte (etwa
    ``BookmarkEntry.session``). Solange der Nachbar ein offener ``dict`` war,
    kam wenigstens ein Container an; sobald er einen NAMEN bekam, verschwand
    das Feld ganz. Ausschreiben löst beides: Das Feld ist da und trägt seine
    Felder. Preis ist eine Kopie im Schema statt eines Verweises.
    """
    schemas = spec.get("components", {}).get("schemas", {})

    def gehe(knoten, chain: tuple[str, ...] = ()):
        if isinstance(knoten, dict):
            zweige = knoten.get("anyOf")
            if isinstance(zweige, list) and len(zweige) == 2 and {"type": "null"} in zweige:
                rest = next(z for z in zweige if z != {"type": "null"})
                if isinstance(rest, dict) and set(rest) == {"$ref"}:
                    name = rest["$ref"].split("/")[-1]
                    # Zyklusschutz: Ein Schema, das sich selbst (mittelbar)
                    # enthält, würde sonst endlos ausgeschrieben.
                    if name in schemas and name not in chain:
                        ziel = copy.deepcopy(schemas[name])
                        ziel["type"] = [ziel.get("type", "object"), "null"]
                        for field in ("title", "description"):
                            if field in knoten:
                                ziel.setdefault(field, knoten[field])
                        return gehe(ziel, chain + (name,))
            return {k: gehe(v, chain) for k, v in knoten.items()}
        if isinstance(knoten, list):
            return [gehe(x, chain) for x in knoten]
        return knoten

    return gehe(spec)


def offene_nullable(spec: dict) -> list[str]:
    """Nullable Felder, die sich NICHT zusammenziehen ließen — der Swift-
    Generator lässt sie weg. Wer eins davon in der App braucht, schreibt es
    dort von Hand oder gibt der Form im Backend einen nicht-nullbaren Vertreter."""
    offen = []
    for name, s in (spec.get("components", {}).get("schemas", {})).items():
        for field, p in (s.get("properties") or {}).items():
            zweige = p.get("anyOf")
            if isinstance(zweige, list) and {"type": "null"} in zweige:
                offen.append(f"{name}.{field}")
    return sorted(offen)


def schema() -> dict:
    sys.path.insert(0, str(WURZEL / "web" / "backend"))
    os.environ.setdefault("WEB_JWT_SECRET", "schema-export")
    from app.main import app

    return _nullbare_refs_inlinen(_nullbar_zusammenziehen(app.openapi()))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pruefen", action="store_true",
                   help="nicht schreiben, nur vergleichen (für die CI)")
    args = p.parse_args()

    text = json.dumps(schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.pruefen:
        if not ZIEL.exists():
            print(f"FEHLT: {ZIEL.relative_to(WURZEL)} — einmal ohne --pruefen laufen lassen.")
            return 1
        if ZIEL.read_text() != text:
            print(f"VERALTET: {ZIEL.relative_to(WURZEL)} passt nicht zum Code.\n"
                  f"  python scripts/openapi_schnitt.py   # neu erzeugen und mitcommitten")
            return 1
        print(f"{ZIEL.relative_to(WURZEL)} ist aktuell.")
        return 0

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    vorher = ZIEL.read_text() if ZIEL.exists() else None
    ZIEL.write_text(text)
    spec = json.loads(text)
    print(f"{'unverändert' if vorher == text else 'geschrieben'}: {ZIEL.relative_to(WURZEL)} "
          f"({len(spec['paths'])} Pfade)")
    offen = offene_nullable(spec)
    if offen:
        print(f"  Hinweis: {len(offen)} nullable Felder bleiben als `anyOf` stehen und fehlen "
              f"deshalb im Swift-Generat: {', '.join(offen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
