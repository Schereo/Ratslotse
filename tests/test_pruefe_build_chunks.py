"""Der Wächter gegen einen in sich unstimmigen Next-Build (``scripts/pruefe_build_chunks.py``)
und der Bau neben dem laufenden Server in den drei Deploys.

Hintergrund 15.09.2026: Prod lieferte ``/wahlabend`` als weiße Seite, weil
die vorgerenderte HTML ein Skript verlangte, das der Build nicht geschrieben
hatte — der Name kam aus dem alten Webpack-Cache. Deploy und Rauchprobe waren
grün. 08.11.2026 auf dev: dieselbe Ursache im CSS, die Schriftklassen am
``<html>`` standen in keinem verlinkten Stylesheet, alles in Times. Am selben
Tag fiel auf, dass jede Seite während des Deploys ungestaltet kam: Der Build
schrieb in das Verzeichnis, aus dem der alte Server auslieferte.

Diese Tests halten fest, dass der Wächter beide Fälle erkennt und einen
stimmigen Build in Ruhe lässt, und dass jeder Deploy neben dem laufenden
Server baut, prüft und erst unmittelbar vor dem Neustart umschaltet.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.pruefe_build_chunks import (  # noqa: E402
    html_font_classes,
    missing_files,
    undefined_font_classes,
)


def _build(tmp_path: Path, html: str, dateien: dict[str, str] | list[str]) -> Path:
    nxt = tmp_path / ".next"
    (nxt / "server" / "app" / "wahlabend").mkdir(parents=True)
    (nxt / "server" / "app" / "wahlabend.html").write_text(html, encoding="utf-8")
    if isinstance(dateien, list):
        dateien = {d: "//" for d in dateien}
    for d, inhalt in dateien.items():
        ziel = nxt / "static" / d
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt, encoding="utf-8")
    return nxt


HTML = ('<link rel="stylesheet" href="/_next/static/css/fb8ffdbd.css"/>'
        '<script src="/_next/static/chunks/app/wahlabend/page-7e835db6.js" async=""></script>'
        '<script src="/_next/static/chunks/main-app-1a2b.js"></script>')


def test_ein_stimmiger_build_hat_keine_befunde(tmp_path):
    nxt = _build(tmp_path, HTML, ["css/fb8ffdbd.css", "chunks/app/wahlabend/page-7e835db6.js", "chunks/main-app-1a2b.js"])
    assert missing_files(nxt) == []


def test_der_fall_vom_15_09_wird_erkannt(tmp_path):
    """Die Seite verlangt page-7e835db6, auf der Platte liegt page-8069d7d4."""
    nxt = _build(tmp_path, HTML, ["css/fb8ffdbd.css", "chunks/app/wahlabend/page-8069d7d4.js", "chunks/main-app-1a2b.js"])
    aus = missing_files(nxt)
    assert [v for _, v in aus] == ["/_next/static/chunks/app/wahlabend/page-7e835db6.js"]
    assert aus[0][0].name == "wahlabend.html"


def test_ein_fehlendes_stylesheet_zaehlt_auch(tmp_path):
    nxt = _build(tmp_path, HTML, ["chunks/app/wahlabend/page-7e835db6.js", "chunks/main-app-1a2b.js"])
    assert [v for _, v in missing_files(nxt)] == ["/_next/static/css/fb8ffdbd.css"]


# Dynamische Routen: Next schreibt den Verweis URL-kodiert, die Datei heißt
# im Klartext. Am 08.11.2026 hielt das den Dev-Deploy an (21 Phantom-Befunde).
DYNAMISCH_HTML = ('<script src="/_next/static/chunks/app/kommunalwahl/liste/%5Bliste%5D/page-7e4ed721.js"'
                  ' async=""></script>')


def test_ein_kodierter_verweis_findet_seine_datei(tmp_path):
    nxt = _build(tmp_path, DYNAMISCH_HTML, ["chunks/app/kommunalwahl/liste/[liste]/page-7e4ed721.js"])
    assert missing_files(nxt) == []


def test_ein_kodierter_verweis_ohne_datei_bleibt_ein_befund(tmp_path):
    nxt = _build(tmp_path, DYNAMISCH_HTML, ["chunks/app/kommunalwahl/liste/[liste]/page-0fff7c93.js"])
    assert [v for _, v in missing_files(nxt)] == [
        "/_next/static/chunks/app/kommunalwahl/liste/%5Bliste%5D/page-7e4ed721.js"]


# --- Schriftklassen (08.11.2026) -------------------------------------------

#: So sah das ``<html>`` auf dev aus — und so steht es in einem heutigen Build.
SCHRIFT_HTML = ('<!DOCTYPE html><html lang="de" class="__variable_d8ebd1 __variable_1243c3">'
                '<head><link rel="stylesheet" href="/_next/static/css/fb8ffdbdcb03c98b.css"'
                ' data-precedence="next"/></head><body class="min-h-screen"></body></html>')
NEU_CSS = (".__variable_d8ebd1{--font-inter:'__Inter_d8ebd1','__Inter_Fallback_d8ebd1'}"
           ".__variable_1243c3{--font-display:'__Bricolage_Grotesque_1243c3'}")
ALT_CSS = (".__variable_f367f3{--font-inter:'__Inter_f367f3'}"
           ".__variable_a4bae9{--font-display:'__Bricolage_Grotesque_a4bae9'}")


def test_schriftklassen_vom_html_tag():
    assert html_font_classes(SCHRIFT_HTML) == ["__variable_d8ebd1", "__variable_1243c3"]
    # Nur das <html>: Klassen weiter unten im Dokument zählen nicht.
    assert html_font_classes('<html lang="de"><body class="__variable_abc"></body></html>') == []
    assert html_font_classes("<html class='dark __variable_ab12'>") == ["__variable_ab12"]


def test_stimmige_schriftklassen_haben_keine_befunde(tmp_path):
    nxt = _build(tmp_path, SCHRIFT_HTML, {"css/fb8ffdbdcb03c98b.css": NEU_CSS})
    assert undefined_font_classes(nxt) == []
    assert missing_files(nxt) == []


def test_der_fall_vom_08_11_wird_erkannt(tmp_path):
    """Das CSS liegt da (die erste Prüfung ist zufrieden), definiert aber die
    Schriftklassen des VORIGEN Builds."""
    nxt = _build(tmp_path, SCHRIFT_HTML, {"css/fb8ffdbdcb03c98b.css": ALT_CSS})
    assert missing_files(nxt) == []
    aus = undefined_font_classes(nxt)
    assert [k for _, k in aus] == ["__variable_d8ebd1", "__variable_1243c3"]
    assert {s.name for s, _ in aus} == {"wahlabend.html"}


def test_nur_das_verlinkte_css_zaehlt(tmp_path):
    """Die Definition in einem Stylesheet, das die Seite nicht lädt, rettet sie nicht."""
    nxt = _build(tmp_path, SCHRIFT_HTML, {"css/fb8ffdbdcb03c98b.css": ALT_CSS, "css/anderes.css": NEU_CSS})
    assert [k for _, k in undefined_font_classes(nxt)] == ["__variable_d8ebd1", "__variable_1243c3"]


def test_ein_praefix_ist_keine_definition(tmp_path):
    """``.__variable_d8ebd1x`` definiert ``__variable_d8ebd1`` nicht."""
    css = ".__variable_d8ebd1x{--a:1}.__variable_1243c3{--b:2}"
    nxt = _build(tmp_path, SCHRIFT_HTML, {"css/fb8ffdbdcb03c98b.css": css})
    assert [k for _, k in undefined_font_classes(nxt)] == ["__variable_d8ebd1"]


def test_die_definition_darf_in_einem_von_mehreren_stylesheets_stehen(tmp_path):
    html = SCHRIFT_HTML.replace(
        "</head>", '<link rel="stylesheet" href="/_next/static/css/zwei.css"/></head>')
    nxt = _build(tmp_path, html, {
        "css/fb8ffdbdcb03c98b.css": ".__variable_d8ebd1{--a:1}",
        "css/zwei.css": ".x{}.__variable_1243c3{--b:2}",
    })
    assert undefined_font_classes(nxt) == []


def test_das_skript_meldet_den_fall_mit_exit_1(tmp_path):
    nxt = _build(tmp_path, SCHRIFT_HTML, {"css/fb8ffdbdcb03c98b.css": ALT_CSS})
    lauf = subprocess.run([sys.executable, str(WURZEL / "scripts" / "pruefe_build_chunks.py"), str(nxt)],
                          capture_output=True, text=True)
    assert lauf.returncode == 1
    assert ".__variable_d8ebd1" in lauf.stdout and "Times" in lauf.stdout


# --- Bauen neben dem laufenden Server --------------------------------------

#: Workflow → die Zeile, die das Frontend neu startet (wörtlich, s. sudoers).
DEPLOYS = {
    "deploy.yml": "sudo /bin/systemctl restart nwz-web-frontend",
    "deploy-dev.yml": "sudo systemctl restart nwz-web-api nwz-web-frontend",
    "deploy-feature.yml": "sudo systemctl restart nwz-feature-api nwz-feature-frontend",
}
UMSCHALTEN = "mv web/frontend/.next-build web/frontend/.next"


def _befehle(name: str) -> list[str]:
    """Die Befehlszeilen eines Workflows, ohne Kommentare und Leerzeilen."""
    text = (WURZEL / ".github" / "workflows" / name).read_text(encoding="utf-8")
    return [z.strip() for z in text.splitlines() if z.strip() and not z.strip().startswith("#")]


def _zeile(befehle: list[str], teil: str, genau: bool = False) -> int:
    treffer = [i for i, z in enumerate(befehle) if (z == teil if genau else teil in z)]
    assert len(treffer) == 1, f"{teil!r}: {len(treffer)} Treffer statt genau einem"
    return treffer[0]


def _frontend_build(befehle: list[str]) -> tuple[int, list[str]]:
    """Zeile und ganzer Befehl des Frontend-Builds. deploy.yml baut vorher
    auch die Technik-Doku mit ``npm run build`` — der Frontend-Build ist der,
    der den Kartenschlüssel einkompiliert."""
    for i, z in enumerate(befehle):
        if not z.endswith("npm run build"):
            continue
        befehl = [z]
        j = i - 1
        while j >= 0 and befehle[j].endswith("\\"):
            befehl.insert(0, befehle[j])
            j -= 1
        if any("NEXT_PUBLIC_CARTO_API_KEY=" in t for t in befehl):
            return i, befehl
    raise AssertionError("kein Frontend-Build (npm run build mit NEXT_PUBLIC_CARTO_API_KEY) gefunden")


@pytest.mark.parametrize("name", DEPLOYS)
def test_der_build_entsteht_neben_dem_laufenden_server(name):
    """``npm run build`` mit ``NEXT_DIST_DIR=.next-build`` — nie in ``.next``,
    aus dem der alte ``next start`` gerade ausliefert. Und leer begonnen: kein
    Webpack-Cache aus dem vorigen Lauf."""
    b = _befehle(name)
    build, befehl = _frontend_build(b)
    assert any(z.startswith("NEXT_DIST_DIR=.next-build") for z in befehl), befehl
    assert _zeile(b, "rm -rf .next-build", genau=True) < build - len(befehl) + 1
    # Der Cache des Builds wandert nicht ins ausgelieferte Verzeichnis.
    assert build < _zeile(b, "rm -rf .next-build/cache/webpack", genau=True)


@pytest.mark.parametrize("name", DEPLOYS)
def test_der_waechter_prueft_den_neuen_build_vor_dem_umschalten(name):
    b = _befehle(name)
    build, _ = _frontend_build(b)
    waechter = _zeile(b, "scripts/pruefe_build_chunks.py web/frontend/.next-build")
    umschalten = _zeile(b, UMSCHALTEN)
    assert build < waechter < umschalten


@pytest.mark.parametrize("name,neustart", DEPLOYS.items())
def test_umgeschaltet_wird_unmittelbar_vor_dem_neustart(name, neustart):
    """Zwischen Umschalten und Neustart liefert der alte Prozess aus dem NEUEN
    Verzeichnis aus. Das darf nur so lange dauern wie ein Zeilenwechsel:
    kein Befehl dazwischen, und das Wegräumen des alten Builds danach."""
    b = _befehle(name)
    umschalten = _zeile(b, UMSCHALTEN)
    assert b[umschalten + 1] == neustart
    assert b[umschalten - 1] == "if [ -d web/frontend/.next ]; then mv web/frontend/.next web/frontend/.next-alt; fi"
    assert b[umschalten - 2] == "rm -rf web/frontend/.next-alt"
    assert b[umschalten + 2] == "rm -rf web/frontend/.next-alt"


def test_prod_prueft_vor_dem_api_stopp_und_schaltet_nach_der_migration_um():
    """Die Reihenfolge ist der Sinn: Der Wächter nach ``npm run build``, vor
    ``systemctl stop nwz-web-api`` — danach wäre die API schon unten. Das
    Umschalten erst nach Migration und Vorprobe: Bricht der Cutover ab, läuft
    das Frontend heil auf dem alten Build weiter."""
    b = _befehle("deploy.yml")
    build, _ = _frontend_build(b)
    waechter = _zeile(b, "pruefe_build_chunks.py")
    stopp = _zeile(b, "systemctl stop nwz-web-api")
    migration = _zeile(b, "scripts/prepare_release_databases.py")
    umschalten = _zeile(b, UMSCHALTEN)
    assert build < waechter < stopp < migration < umschalten
    assert b[waechter + 1] == "touch web/frontend/.next-build/.geprueft"


def test_der_rsync_laesst_die_build_verzeichnisse_in_ruhe():
    """Ohne Ausschluss UND Schutzregel räumt ``--delete`` sie weg — oder
    scheitert an ihnen mit Exit 23 (06.09.2026, node_modules)."""
    text = (WURZEL / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    for verz in (".next-build", ".next-alt"):
        assert f"--exclude 'web/frontend/{verz}/'" in text
        assert f"--filter 'P /web/frontend/{verz}/'" in text


def test_frontend_restart_schaltet_nur_einen_geprueften_build_ein():
    b = _befehle("ops-wartungsbarriere.yml")
    marke = _zeile(b, "if [ -f web/frontend/.next-build/.geprueft ]; then")
    waechter = _zeile(b, "scripts/pruefe_build_chunks.py web/frontend/.next-build")
    umschalten = _zeile(b, UMSCHALTEN)
    neustart = _zeile(b, "sudo -n /bin/systemctl restart nwz-web-frontend")
    assert marke < waechter < umschalten < neustart


_NODE = shutil.which("node")


@pytest.mark.skipif(_NODE is None, reason="Node fehlt")
def test_next_config_nimmt_das_bauverzeichnis_nur_beim_bauen():
    """``next start`` muss ``.next`` lesen, auch wenn ``NEXT_DIST_DIR`` in
    seiner Umgebung stünde — sonst sucht der Dienst den Build in einem
    Verzeichnis, das das Umschalten gerade weggeräumt hat."""
    skript = (
        "const m = await import(process.argv[1]);"
        "const phasen = ['phase-production-build', 'phase-production-server', 'phase-development-server'];"
        "console.log(JSON.stringify(Object.fromEntries(phasen.map(p => [p, m.default(p).distDir ?? null]))));"
    )
    config = (WURZEL / "web" / "frontend" / "next.config.mjs").as_uri()

    def lauf(env_extra: dict[str, str]) -> dict[str, str | None]:
        env = {"PATH": "/usr/bin:/bin", **env_extra}
        aus = subprocess.run([_NODE, "--input-type=module", "-e", skript, config],
                             capture_output=True, text=True, env=env, check=True)
        return json.loads(aus.stdout)

    mit = lauf({"NEXT_DIST_DIR": ".next-build"})
    assert mit == {"phase-production-build": ".next-build",
                   "phase-production-server": None,
                   "phase-development-server": ".next-dev"}
    ohne = lauf({})
    assert ohne["phase-production-build"] is None
