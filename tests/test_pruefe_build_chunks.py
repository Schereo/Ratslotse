"""Der Wächter gegen einen in sich unstimmigen Next-Build (``scripts/pruefe_build_chunks.py``).

Hintergrund 15.09.2026: Prod lieferte ``/wahlabend`` als weiße Seite, weil
die vorgerenderte HTML ein Skript verlangte, das der Build nicht geschrieben
hatte — der Name kam aus dem alten Webpack-Cache. Deploy und Rauchprobe waren
grün. Diese Tests halten fest, dass der Wächter den Fall erkennt, einen
stimmigen Build in Ruhe lässt und Stylesheets mitprüft.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.pruefe_build_chunks import fehlende  # noqa: E402


def _build(tmp_path: Path, html: str, dateien: list[str]) -> Path:
    nxt = tmp_path / ".next"
    (nxt / "server" / "app" / "wahlabend").mkdir(parents=True)
    (nxt / "server" / "app" / "wahlabend.html").write_text(html, encoding="utf-8")
    for d in dateien:
        ziel = nxt / "static" / d
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text("//", encoding="utf-8")
    return nxt


HTML = ('<link rel="stylesheet" href="/_next/static/css/fb8ffdbd.css"/>'
        '<script src="/_next/static/chunks/app/wahlabend/page-7e835db6.js" async=""></script>'
        '<script src="/_next/static/chunks/main-app-1a2b.js"></script>')


def test_ein_stimmiger_build_hat_keine_befunde(tmp_path):
    nxt = _build(tmp_path, HTML, ["css/fb8ffdbd.css", "chunks/app/wahlabend/page-7e835db6.js", "chunks/main-app-1a2b.js"])
    assert fehlende(nxt) == []


def test_der_fall_vom_15_09_wird_erkannt(tmp_path):
    """Die Seite verlangt page-7e835db6, auf der Platte liegt page-8069d7d4."""
    nxt = _build(tmp_path, HTML, ["css/fb8ffdbd.css", "chunks/app/wahlabend/page-8069d7d4.js", "chunks/main-app-1a2b.js"])
    aus = fehlende(nxt)
    assert [v for _, v in aus] == ["/_next/static/chunks/app/wahlabend/page-7e835db6.js"]
    assert aus[0][0].name == "wahlabend.html"


def test_ein_fehlendes_stylesheet_zaehlt_auch(tmp_path):
    nxt = _build(tmp_path, HTML, ["chunks/app/wahlabend/page-7e835db6.js", "chunks/main-app-1a2b.js"])
    assert [v for _, v in fehlende(nxt)] == ["/_next/static/css/fb8ffdbd.css"]


def test_der_deploy_ruft_den_waechter_vor_dem_umschalten():
    """Die Reihenfolge ist der Sinn: nach ``npm run build``, vor ``systemctl
    stop nwz-web-api``. Danach wäre die Seite schon umgeschaltet."""
    text = (WURZEL / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    build = text.index("npm run build")
    waechter = text.index("pruefe_build_chunks.py")
    stopp = text.index("systemctl stop nwz-web-api")
    assert build < waechter < stopp, "der Wächter gehört zwischen Build und API-Stopp"
