"""Wächter: Seiten liegen auf EINEM Stapel, und Lotti steht über ihm.

Zwei Befunde vom Drehen der Release-Clips für 3.0.0 (10/2026), beide aus
derselben Ursache — es gab mehr als einen Ort, an dem Seiten lagen:

1. **Ideen öffneten sich hinter dem Mehr-Blatt.** Das Blatt hatte einen
   eigenen ``NavigationStack``. Die Links auf den Seiten darin schieben aber
   auf den Stapel der App (``model.navigation``), und der lag unter dem
   Blatt: Ein Tipp auf eine Idee unter „Gerade in Bewegung" zeigte nichts,
   bis man das Blatt wegwischte. Genau diesen Weg bewarb die 3.0.0-Karte.
2. **Auf der Beschluss-Seite gab es keinen Lotti-Knopf.** Er hing an
   ``MainTabsView``, der Wurzel des Stapels; jede geschobene Seite (Beschluss,
   Sitzung, Person, Thema, Ort, Bewegung, Mein Viertel …) legte sich darüber.

Beides kommt beim nächsten „kleinen" eigenen Stapel von allein zurück, und
man sieht es dem Code nicht an — deshalb steht es hier und nicht nur in
einem Kommentar. Die Lage des Knopfs rechnet ``LottiPlacement``
(``swift test`` in ``ios/Packages/RatslotseAPI``).
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
QUELLEN = WURZEL / "ios" / "Packages" / "RatslotseFeatures" / "Sources" / "RatslotseFeatures"
ZIEL_FUER_ROUTEN = re.compile(r"\.navigationDestination\(\s*for:\s*AppRoute\.self")


def swift_dateien() -> list[Path]:
    return sorted(QUELLEN.glob("*.swift"))


def text(name: str) -> str:
    return (QUELLEN / name).read_text(encoding="utf-8")


def struct_rumpf(quelle: str, kopf: str) -> str:
    """Der Text einer Struktur bis zur nächsten auf oberster Ebene."""
    start = quelle.index(kopf)
    naechste = re.search(r"\n(?:private |fileprivate )?(?:struct|final class|enum|extension) ",
                         quelle[start + len(kopf):])
    return quelle[start:start + len(kopf) + naechste.start()] if naechste else quelle[start:]


def test_die_quellen_sind_ueberhaupt_da():
    """Ohne diese Zeile wäre der Wächter nach einem Umzug still grün."""
    assert swift_dateien(), f"keine Swift-Dateien unter {QUELLEN}"


def test_routen_haben_genau_ein_ziel():
    """Ein zweites ``navigationDestination(for: AppRoute.self)`` ist ein zweiter
    Stapel. Seine Seiten schieben weiter auf ``model.navigation`` — also unter
    das Blatt, in dem sie stehen —, und Lotti kennt sie nicht.

    Bis 10/2026 gab es drei: die Wurzel, das Mehr-Blatt und das Blatt der
    Analyse mit den Beschlüssen eines Themenfelds.
    """
    fundorte = [(d.name, len(ZIEL_FUER_ROUTEN.findall(d.read_text(encoding="utf-8"))))
                for d in swift_dateien()]
    fundorte = [(name, n) for name, n in fundorte if n]
    assert fundorte == [("NativeRootView.swift", 1)], (
        f"Routen-Ziele: {fundorte}. Seiten gehören auf den Stapel der Wurzel — "
        "ein Blatt, aus dem heraus eine Seite aufgeht, schließt sich und hängt "
        "die Route an `model.navigation` (Muster: `MoreHubView.openPage`, "
        "`DistrictProjectSheet`).")


def test_geschoben_wird_nur_ueber_routen():
    """Eine eingebettete Zielansicht (``NavigationLink { … }``) liegt am Stapel
    vorbei: ohne Kopfzeile, ohne Zurück-Geste — und Lotti erklärte darauf die
    Seite darunter. So stand bis 10/2026 die Merkliste in der Beschlussliste."""
    funde = []
    for datei in swift_dateien():
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"NavigationLink\s*\{|NavigationLink\(\s*destination:", zeile):
                funde.append(f"{datei.name}:{nr}")
    assert not funde, (
        f"Eingebettete Zielansicht in {funde}. Stattdessen "
        "`NavigationLink(value: AppRoute.…)` und die Ansicht in "
        "`RouteDestinationView` eintragen.")


def test_das_mehr_blatt_ist_ein_menue():
    """Das Mehr-Blatt öffnet seine Seiten im Stapel der App und schließt sich
    dabei — es hat keinen eigenen Stapel und keine eigenen Links mehr."""
    rumpf = struct_rumpf(text("MoreHubView.swift"), "struct MoreHubView: View {")
    assert "NavigationStack" not in rumpf, (
        "Das Mehr-Blatt hat wieder einen eigenen Stapel. Links auf den Seiten "
        "darin öffnen sich dann unsichtbar dahinter.")
    assert "NavigationLink" not in rumpf
    assert "func openPage(" in rumpf and "dismiss()" in rumpf
    assert "model.navigation.append(route)" in rumpf


def test_lotti_wohnt_nur_im_host():
    """Knopf, Blase und Blatt gibt es genau einmal — im Host über dem Stapel."""
    for baustein in ("LottiFloatingButton(", "LottiNudgeBubble(", "AssistantSheet("):
        orte = [d.name for d in swift_dateien()
                if re.search(r"(?<!struct )" + re.escape(baustein), d.read_text(encoding="utf-8"))]
        assert orte == ["LottiHost.swift"], (
            f"`{baustein}` steht in {orte}. Lotti gehört an EINE Stelle "
            "(`LottiHost`); eine zweite läge wieder unter den geschobenen Seiten "
            "oder führte eine eigene Uhr fürs Anklopfen.")


def test_der_host_haengt_aussen_am_stapel_der_wurzel():
    """Innerhalb des Stapels (an ``MainTabsView``) verdeckt jede geschobene
    Seite den Knopf. Außen am Stapel liegt er über allen."""
    quelle = text("NativeRootView.swift")
    assert quelle.count(".lottiHost(") == 1, "Der Host hängt nicht genau einmal."
    wurzel = struct_rumpf(quelle, "public struct NativeRootView: View {")
    assert ".lottiHost(" in wurzel, "Der Host hängt nicht an der Wurzel-Ansicht."
    stapel = wurzel.index("NavigationStack(path: $model.navigation)")
    ziel = wurzel.index(".navigationDestination(for: AppRoute.self)")
    assert stapel < ziel < wurzel.index(".lottiHost("), (
        "Der Host muss NACH dem Stapel samt seinem Routen-Ziel kommen — also "
        "außen an ihm, nicht an einer Ansicht darin.")
    tabs = struct_rumpf(quelle, "private struct MainTabsView: View {")
    assert "LottiFloatingButton" not in tabs and ".sheet(item: $lotti" not in tabs


def test_geschobene_seiten_halten_platz_fuer_den_knopf():
    """Der Knopf schwebt über der Seite; ohne Rand läge ihr letzter Eintrag
    unter ihm, egal wie weit man scrollt (derselbe Befund wie bei der
    Tab-Leiste, Tim 09.09.2026)."""
    quelle = text("NativeRootView.swift")
    geruest = quelle[quelle.index("private var routeContent: some View {"):]
    geruest = geruest[:geruest.index("private var activeDestination")]
    assert ".safeAreaPadding(.bottom, lottiInset)" in geruest
    assert "LottiPlacement.pageInset(" in quelle
