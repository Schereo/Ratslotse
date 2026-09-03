"""Wächter über das Rechte-Gate des Haushalts-Bereichs.

Der Bereich ist Ratsmitgliedern und Admins vorbehalten (Recht ``budget``,
siehe ``kern/roles.py``). Bis 09/2026 hing er stattdessen an einem
Umgebungs-Gate und war auf Prod für alle ein 404; die Rolle leistet dasselbe,
aber richtig herum — der Bereich fährt mit nach Prod und ist dort für die
sichtbar, für die er gebaut ist.

**Die eigentliche Sperre sitzt im Backend** und wird in ``test_rollen.py``
geprüft: Alle zwanzig ``/api/council/budget…``-Routen verlangen das Recht.
Was hier steht, ist die Oberfläche davor — und ein Gate ist nur so gut wie
seine Lücken: Vergisst jemand einen Link, steht der bei allen anderen weiter
da und führt in ein 404. Genau diese Falle gab es schon einmal bei der
Kommunalwahl-Metadata.

Diese Datei prüft deshalb nicht, ob das Gate *existiert* (das sieht man),
sondern ob es *vollständig* ist:

1. Jede Seite unter app/(app)/haushalt/ liegt unter dem Layout mit dem Gate.
2. Kein Verweis auf /haushalt außerhalb des Bereichs steht ungeschützt da.
3. Die Geld-Bausteine der KI-Frage bleiben bei leeren Tabellen still leer —
   eine Umgebung ohne Haushalts-Ingest hat die Tabellen leer.

Der dritte Punkt ist der wichtigste: Er ist der einzige Weg, auf dem ein
leerer Haushalts-Bestand die Antworten trotzdem verschlechtern könnte.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "web" / "frontend"
BEREICH = FRONTEND / "app" / "(app)" / "haushalt"
#: Die Hilfsfunktion, an der das Gate hängt. Ein Name, keine Konstante mehr:
#: Ob jemand darf, hängt am KONTO und lässt sich nicht mehr beim Bauen
#: entscheiden.
GATE_FUNKTION = "darfHaushalt"


def test_die_rechte_hilfe_ist_die_einzige_quelle():
    """`lib/rechte.ts` fragt die Rechte des Kontos — und nichts sonst.

    Der Punkt der Datei ist, dass NIRGENDS ein Rollenname steht: Wer hier
    `roles.includes("council_member")` schriebe, müsste bei jeder neuen Rolle
    jede Prüfstelle anfassen, und die vergessene meldet sich nicht.
    """
    quelle = (FRONTEND / "lib" / "rechte.ts").read_text(encoding="utf-8")
    assert f"export function {GATE_FUNKTION}" in quelle
    assert "permissions" in quelle
    assert "council_member" not in quelle, (
        "lib/rechte.ts prüft gegen einen ROLLENNAMEN statt gegen ein Recht — "
        "damit wandert die Rollenlogik ins Frontend zurück.")


def test_kein_umgebungs_gate_mehr_am_haushalt():
    """Das alte Gate ist weg, nicht bloß umgangen.

    Bliebe `lib/haushalt-frei.ts` mit stehen, gäbe es zwei Wahrheiten
    nebeneinander — und die nächste Seite hinge an der falschen.
    """
    assert not (FRONTEND / "lib" / "haushalt-frei.ts").exists(), (
        "lib/haushalt-frei.ts lebt noch — der Haushalt hängt jetzt am Recht "
        "'budget' (lib/rechte.ts), nicht mehr an NEXT_PUBLIC_RATSLOTSE_ENV.")
    reste = [str(p.relative_to(FRONTEND))
             for p in list((FRONTEND / "app").rglob("*.tsx"))
             + list((FRONTEND / "components").rglob("*.tsx"))
             + list((FRONTEND / "lib").rglob("*.ts"))
             if "HAUSHALT_FREI" in p.read_text(encoding="utf-8")]
    assert not reste, f"Reste des Umgebungs-Gates: {reste}"


def test_layout_gated_den_ganzen_bereich():
    """Ein Layout statt zwanzig Einzelgates — sonst fehlt beim einundzwanzigsten eins."""
    layout = BEREICH / "layout.tsx"
    assert layout.exists(), "app/(app)/haushalt/layout.tsx fehlt — der Bereich ist offen"
    source = layout.read_text(encoding="utf-8")
    assert GATE_FUNKTION in source
    assert "notFound()" in source
    # Und es darf nicht zuschlagen, BEVOR die Sitzung geladen ist: Sonst träfe
    # das 404 jedes Ratsmitglied beim ersten Aufruf und bei jedem Neuladen.
    assert "loading" in source, (
        "Das Layout prüft die Rechte, ohne auf `loading` aus useAuth() zu "
        "warten — dann ist beim ersten Rendern noch niemand angemeldet und "
        "der Bereich zeigt allen ein 404.")


def test_jede_seite_liegt_unter_dem_layout():
    """Keine Haushalts-Seite darf am Layout vorbei erreichbar sein.

    Next.js wendet ein Layout auf alles an, was unter seinem Verzeichnis liegt.
    Der Test hält fest, dass niemand eine Seite daneben legt (etwa unter
    app/(app)/haushalt-neu/), wo das Gate nicht greift.
    """
    seiten = sorted(BEREICH.rglob("page.tsx"))
    assert len(seiten) >= 13, f"nur {len(seiten)} Seiten gefunden — Fund verschoben?"
    for page in seiten:
        assert (BEREICH / "layout.tsx").exists()
        assert BEREICH in page.parents, f"{page} liegt nicht unter dem Gate"

    # Keine zweite Haushalts-Route außerhalb des gegateten Verzeichnisses.
    app = FRONTEND / "app"
    fremde = [p for p in app.rglob("page.tsx")
              if "haushalt" in str(p.relative_to(app)).lower()
              and BEREICH not in p.parents]
    assert not fremde, f"Haushalts-Seiten außerhalb des Gates: {fremde}"


def test_kein_ungegateter_verweis_auf_den_bereich():
    """Jeder Link auf /haushalt außerhalb des Bereichs braucht das Gate.

    Geprüft wird bewusst grob (Datei enthält Link *und* Prüfung), nicht
    zeilengenau: Ein falsch-negativer Treffer wäre schlimmer als ein
    gelegentlicher Fehlalarm, der beim Lesen sofort auffliegt.
    """
    verdaechtig: list[str] = []
    for pfad in list((FRONTEND / "app").rglob("*.tsx")) + \
            list((FRONTEND / "components").rglob("*.tsx")):
        if BEREICH in pfad.parents:
            continue                      # der Bereich selbst liegt hinterm Layout
        if (FRONTEND / "components" / "haushalt") in pfad.parents:
            continue                      # Bausteine, die nur dort eingebunden sind
        text = pfad.read_text(encoding="utf-8")
        # href="/haushalt…" — echte Navigationsziele, keine API-Pfade
        if not re.search(r'href=(?:"|\{")/haushalt', text):
            continue
        if GATE_FUNKTION not in text:
            verdaechtig.append(str(pfad.relative_to(FRONTEND)))
    assert not verdaechtig, (
        "Verweise auf /haushalt ohne Rechte-Gate — für Konten ohne das Recht "
        f"'budget' führen sie in ein 404: {verdaechtig}")


def _alle_bausteine():
    """Jede Kontext-Bausteinfunktion in qa.py, aus dem Quelltext gelesen.

    Bewusst nicht als Liste von Namen: Die erste Fassung zählte drei Bausteine
    auf und versprach im selben Atemzug, „den vierten" zu fangen. Als sie
    geschrieben wurde, gab es fünf; inzwischen sind es sechzehn, und keiner der
    dreizehn neuen war je geprüft. Wer eine Prüfung an eine Aufzählung bindet,
    prüft ab dem nächsten Commit die Vergangenheit.
    """
    from council import qa

    source = Path(qa.__file__).read_text(encoding="utf-8")
    gefunden = set(re.findall(r"^def (_\w+_block)\(", source, re.M))
    return sorted(gefunden - AUSNAHMEN)


#: Bausteine, die ohne Daten absichtlich Text liefern — geprüft, nicht geraten.
#:
#: ``_bisher_block`` ist der einzige: Er reicht keine Daten durch, sondern eine
#: Anweisung ans Modell. Liegt keine frühere Antwort vor (ältere App-Versionen
#: schicken das Feld nicht mit), sagt er das ausdrücklich — sonst hantierte das
#: Modell mit einem leeren Zitat-Block. Wer hier etwas einträgt, muss denselben
#: Nachweis führen: Der Text ist Anweisung, nicht Inhalt.
AUSNAHMEN = {"_bisher_block"}


def test_die_bausteinliste_ist_nicht_leer():
    """Sicherung gegen den stillen Ausfall: Findet der Regex nichts, liefe die
    Prüfung darunter über eine leere Liste und wäre grün, ohne etwas zu tun."""
    assert len(_alle_bausteine()) >= 10


@pytest.mark.parametrize("baustein", _alle_bausteine())
def test_bausteine_bleiben_bei_leeren_daten_still(baustein):
    """Ohne Daten kein Text — für jeden Baustein, nicht nur die Geld-Bausteine.

    In einer Umgebung ohne Haushalts-Ingest sind die Tabellen leer, und auch
    sonst kann jede Quelle einmal nichts liefern. Ein Baustein, der daraus eine
    Überschrift ohne Inhalt oder eine Zeile aus „–" macht, verschlechtert die
    Antwort, statt sie zu ergänzen.
    """
    from council import qa

    fn = getattr(qa, baustein)
    assert fn(None) == "", f"{baustein}(None) liefert Text statt Leerstring"


def test_jede_geld_quelle_wird_abgesichert_abgefragt():
    """Die Abfragen selbst dürfen die Antwort nie blockieren.

    Existiert eine der Haushalts-Tabellen nicht, darf die KI-Frage trotzdem
    nicht ausfallen.

    Die erste Fassung dieses Tests suchte die Aufrufe im Router und ihr
    ``try:`` davor. Das war zu eng an einer Struktur festgemacht: #543 hat sie
    nach ``qa.geld_kontext`` gebündelt, wo jede Quelle in ``_sicher(...)``
    steht — die Absicherung blieb, der Test fiel trotzdem. Er prüft jetzt die
    Eigenschaft statt den Ort.
    """
    from council import qa

    source = (Path(__file__).resolve().parents[1] / "council" / "qa.py").read_text(encoding="utf-8")
    körper = source[source.index("def geld_kontext("):]
    körper = körper[:körper.index("\ndef ", 1)]

    ungeschützt = [
        row.strip()
        for row in körper.splitlines()
        if "store." in row and "_sicher(" not in row and not row.strip().startswith("#")
    ]
    assert not ungeschützt, (
        "Store-Abfrage in geld_kontext() ohne _sicher() — bei fehlender Tabelle "
        f"fällt die ganze Antwort aus: {ungeschützt}")

    # Und der Wrapper tut, was sein Name sagt.
    assert qa._sicher(lambda: 1 / 0, standard=[]) == []
