"""Wächter: Web und App erkennen Namen im Fließtext mit denselben Wörtern.

Das Personen-Badge hinter einem Nachnamen entsteht in beiden Oberflächen im
Client — im Web in ``web/frontend/lib/person-badge.ts``, in der App in
``QuestionsView.swift``. Seit 11/2026 bekommt ein eindeutiger Nachname es nur
noch, wenn der Text ihn als Namen ausweist: Vorname, Anrede oder Amt davor,
ein Verb des Sagens daneben (Tims Befund: „Danke der Nachfrage!" trug das
Badge von André Danke, „gab es Streit" das von Tim Streit).

Die Wortlisten dafür stehen zweimal. Ergänzt jemand ein Verb nur im Web,
zeigt die App dieselbe Antwort mit anderen Badges — und niemand sieht es,
weil niemand beide nebeneinander liest. Deshalb hier.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
WEB = WURZEL / "web" / "frontend" / "lib" / "person-badge.ts"
APP = (WURZEL / "ios" / "Packages" / "RatslotseFeatures" / "Sources"
       / "RatslotseFeatures" / "QuestionsView.swift")

#: Name im Web → Name in der App.
LISTEN = {
    "NAME_TITLES": "questionNameTitles",
    "NAME_OFFICE_ENDINGS": "questionNameOfficeEndings",
    "NAME_VERBS": "questionNameVerbs",
    "NAME_PARTICLES": "questionNameParticles",
}


def liste(quelle: str, kopf: str) -> list[str]:
    treffer = re.search(re.escape(kopf) + r"\s*=\s*\[(.*?)\]", quelle, re.S)
    assert treffer, f"{kopf} nicht gefunden"
    return re.findall(r'"([^"]+)"', treffer.group(1))


def test_wortlisten_sind_gleich():
    web = WEB.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    for web_name, app_name in LISTEN.items():
        im_web = liste(web, f"export const {web_name}")
        in_der_app = liste(app, f"let {app_name}")
        assert im_web, f"{web_name} ist leer"
        assert im_web == in_der_app, (
            f"{web_name} (Web) und {app_name} (App) weichen ab: "
            f"nur Web {sorted(set(im_web) - set(in_der_app))}, "
            f"nur App {sorted(set(in_der_app) - set(im_web))}. "
            f"Beide in derselben Reihenfolge nachziehen: {WEB.relative_to(WURZEL)} "
            f"und {APP.relative_to(WURZEL)}")


def test_woerter_sind_gefaltet():
    """Verglichen wird gegen gefaltete Wörter (ä → ae, ß → ss). Ein Eintrag
    mit Umlaut passte nie — er stünde in der Liste und wirkte nicht."""
    web = WEB.read_text(encoding="utf-8")
    for web_name in LISTEN:
        for wort in liste(web, f"export const {web_name}"):
            assert re.fullmatch(r"[a-z]+", wort), f"{web_name}: „{wort}“ ist nicht gefaltet"


def test_beratend_nicht_als_datenbankwert():
    """Bis 11/2026 stand im Web „advisory" auf dem Badge — beim Umbenennen der
    Datenbankwerte (#950) war das Label mit umbenannt worden."""
    web = WEB.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert re.search(r'p\.art === "advisory" \? "beratend"', web)
    assert re.search(r'case "advisory": return "beratend"', app)
