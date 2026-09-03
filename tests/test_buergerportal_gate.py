"""Wächter für Sichtbarkeit und Feature-only-Beispieldaten des Bürgerportals."""
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web" / "frontend"
GATE = "PROBLEME_FREI"
SEED_COMMAND = "scripts/saat_buergerportal_feature.py"


def test_problem_route_and_entry_points_share_the_environment_gate():
    gate = (FRONTEND / "lib" / "probleme-frei.ts").read_text()
    page = (FRONTEND / "app" / "(app)" / "probleme" / "page.tsx").read_text()
    detail_page = (FRONTEND / "app" / "(app)" / "probleme" / "[id]" / "page.tsx").read_text()
    nav = (FRONTEND / "components" / "nav.tsx").read_text()
    sitemap = (FRONTEND / "app" / "sitemap.ts").read_text()

    assert 'process.env.NEXT_PUBLIC_BUERGERPORTAL === "1"' in gate, (
        "lib/probleme-frei.ts muss den eigenen Feature-Build-Schalter prüfen."
    )
    assert f"export const {GATE}" in gate, "PROBLEME_FREI wieder exportieren."
    assert GATE in page and "notFound()" in page, (
        "app/(app)/probleme/page.tsx muss außerhalb von app-feature 404 liefern."
    )
    assert "generateMetadata" in page and "metadataFrei" in page, (
        "Auch die Metadaten in probleme/page.tsx hinter PROBLEME_FREI legen."
    )
    assert GATE in detail_page and "notFound()" in detail_page, (
        "Die dynamische Problem-Detailseite muss dasselbe Feature-Gate verwenden."
    )
    assert "generateMetadata" in detail_page and "if (!PROBLEME_FREI) return {};" in detail_page, (
        "Auch Detail-Metadaten außerhalb von app-feature geschlossen halten."
    )
    assert GATE in nav and 'href: "/probleme"' in nav, (
        "Den /probleme-Link in components/nav.tsx mit PROBLEME_FREI schützen."
    )
    assert GATE in sitemap and "`${BASE}/probleme`" in sitemap, (
        "Den Sitemap-Eintrag in app/sitemap.ts mit PROBLEME_FREI schützen."
    )


def test_android_registers_canonical_problem_app_links():
    manifest = ET.parse(FRONTEND / "android" / "app" / "src" / "main" / "AndroidManifest.xml")
    android = "{http://schemas.android.com/apk/res/android}"

    app_links = set()
    for intent_filter in manifest.findall(".//intent-filter"):
        actions = frozenset(
            action.get(f"{android}name")
            for action in intent_filter.findall("action")
        )
        categories = frozenset(
            category.get(f"{android}name")
            for category in intent_filter.findall("category")
        )
        if "android.intent.action.VIEW" not in actions:
            continue
        for data in intent_filter.findall("data"):
            app_links.add((
                intent_filter.get(f"{android}autoVerify"),
                categories,
                data.get(f"{android}scheme"),
                data.get(f"{android}host"),
                data.get(f"{android}pathPrefix"),
            ))

    expected = {(
        "true",
        frozenset({
            "android.intent.category.DEFAULT",
            "android.intent.category.BROWSABLE",
        }),
        "https",
        "ratslotse.de",
        "/probleme/",
    )}
    assert app_links == expected, (
        "AndroidManifest.xml auf genau den verifizierten HTTPS-App-Link "
        "ratslotse.de/probleme/* mit DEFAULT+BROWSABLE begrenzen; danach "
        "`.venv/bin/pytest tests/test_buergerportal_gate.py -q` ausführen."
    )


def test_only_feature_deployment_can_invoke_the_example_seeder():
    workflows = ROOT / ".github" / "workflows"
    callers = []
    for workflow in workflows.glob("*.yml"):
        if SEED_COMMAND in workflow.read_text():
            callers.append(workflow.name)

    assert callers == ["deploy-feature.yml"], (
        "Den Beispiel-Seed-Aufruf aus allen Workflows außer deploy-feature.yml entfernen."
    )
    feature = (workflows / "deploy-feature.yml").read_text()
    assert "cd ~/app-feature" in feature, "Feature-Deploy muss vor dem Seed nach ~/app-feature wechseln."
    assert f"RATSLOTSE_FEATURE_SEED=1 .venv/bin/python {SEED_COMMAND}" in feature, (
        "Feature-Seed in deploy-feature.yml nur mit RATSLOTSE_FEATURE_SEED=1 aufrufen."
    )
    assert "NEXT_PUBLIC_BUERGERPORTAL=1" in feature, (
        "Nur deploy-feature.yml darf die Bürgerportal-Oberfläche freischalten."
    )
    unlocked = sorted(
        path.name
        for path in workflows.glob("*.yml")
        if "NEXT_PUBLIC_BUERGERPORTAL=1" in path.read_text()
    )
    assert unlocked == ["deploy-feature.yml"], (
        "NEXT_PUBLIC_BUERGERPORTAL=1 aus allen Workflows außer deploy-feature.yml entfernen."
    )
