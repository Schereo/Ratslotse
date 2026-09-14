"""Die Referenzordner gelaufener Wahlen — einer je Wahl, alle nach einem Schema.

`kommunalwahl/referenz-2021/` war bis 09/2026 ein Einzelstück: von Hand
angelegt, von genau einer Stelle gelesen. Seit `referenz-2026/` daneben liegt,
ist es eine **Gattung**, und diese Tests halten sie zusammen:

* Jeder Ordner trägt genau eine Meta-Datei `<name>-<jahr>.json` und die drei
  CSVs mit deren Namen als Präfix (das ist die Konvention, nach der
  `reference.meta_path` sucht).
* Die Meta-Datei nennt so viele Mandate, wie die Wahl Sitze hatte, und jedes
  Mandat gehört zu einer Liste, die auch in `parteien` steht.
* `reference.load()` kommt mit jedem Ordner zurecht.

**Warum das mehr ist als Formprüfung.** Der Inhalt eines Referenzordners
lässt sich nicht nachbessern: Die Quelle (`votemanager.kdo.de/<wahltag>/…`)
verschwindet irgendwann. Ein Schaden fällt erst bei der nächsten Wahl auf —
also fünf Jahre später, wenn niemand mehr etwas holen kann. Diese Tests sind
der einzige Zeitpunkt, zu dem er auffallen kann.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import reference  # noqa: E402
from app.election import votemanager  # noqa: E402

KOMMUNALWAHL = WURZEL / "kommunalwahl"
ORDNER = sorted(p for p in KOMMUNALWAHL.glob("referenz-*") if p.is_dir())
#: Die drei Gebietsebenen, aus denen eine Referenz besteht.
EBENEN = ("stadt", "wahlbereiche", "wahlbezirke")


def test_es_gibt_referenzordner():
    """Ohne diesen Test wäre eine leere Liste ein grüner Lauf."""
    assert [p.name for p in ORDNER] == ["referenz-2021", "referenz-2026"], (
        "Neuen Referenzordner? Dann gehört er in diese Liste — und der Grund ist, dass "
        "ein versehentlich gelöschter Ordner sonst als „nichts zu prüfen“ durchginge.")


@pytest.mark.parametrize("ordner", ORDNER, ids=lambda p: p.name)
def test_meta_und_csvs_heissen_zusammen(ordner: Path):
    """Genau eine Meta-Datei, und die drei CSVs tragen ihren Namen."""
    meta = reference.meta_path(ordner)
    for ebene in EBENEN:
        datei = ordner / f"{meta.stem}-{ebene}.csv"
        assert datei.is_file(), f"{datei.name} fehlt — anzulegen mit scripts/wahl_einfrieren.py"


@pytest.mark.parametrize("ordner", ORDNER, ids=lambda p: p.name)
def test_meta_ist_vollstaendig(ordner: Path):
    meta = json.loads(reference.meta_path(ordner).read_text(encoding="utf-8"))
    assert set(meta) >= {"quelle", "sitze_gesamt", "parteien", "sitzverteilung"}
    assert set(meta["quelle"]) >= {"titel", "url", "abgerufen"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["quelle"]["abgerufen"])

    indizes = [p["index"] for p in meta["parteien"]]
    assert indizes == sorted(indizes), "Die Listen stehen in Spaltenreihenfolge — sie ist der Schlüssel zur CSV."
    assert len(set(indizes)) == len(indizes), "Zwei Listen auf derselben Spalte"
    labels = [p["label"] for p in meta["parteien"]]
    assert len(set(labels)) == len(labels), (
        "Doppeltes Label: reference.load schlüsselt die Sitzverteilung über „label“ auf den Slug — "
        "ein doppeltes zählt die Sitze der falschen Liste zu.")

    assert len(meta["sitzverteilung"]) == meta["sitze_gesamt"], (
        f"{len(meta['sitzverteilung'])} Mandate bei {meta['sitze_gesamt']} Sitzen")
    for m in meta["sitzverteilung"]:
        assert set(m) >= {"party", "name", "district", "kind"}
        assert m["party"] in labels, f"Mandat für „{m['party']}“, die in „parteien“ fehlt"


@pytest.mark.parametrize("ordner", ORDNER, ids=lambda p: p.name)
def test_reference_load_kommt_mit_jedem_ordner_zurecht(ordner: Path):
    """Der eigentliche Zweck: Die Hochrechnung soll jede Vorwahl lesen können."""
    ref = reference.load(ordner)
    meta = json.loads(reference.meta_path(ordner).read_text(encoding="utf-8"))
    assert ref.seats_total == meta["sitze_gesamt"]
    assert sum(ref.seats_by_slug.values()) == meta["sitze_gesamt"]
    assert len(ref.districts) == 133, "Oldenburg hat 133 Wahlbezirke — 2021 wie 2026"
    assert ref.city.valid_votes and ref.city.valid_votes > 0
    # Die Anteile summieren sich auf 100 %, solange jede Liste einen Slug hat.
    if all(p.get("slug") for p in meta["parteien"]):
        assert abs(sum(ref.share_by_slug.values()) - 100) < 0.5


def test_beide_spaltenschemata_liegen_im_bestand():
    """2021 hieß die Listenstimme ``D<n>_liste`` und die Personenstimme
    ``D<n>_<k>``; 2026 heißen sie ``D<n>_1`` und ``D<n>_2_<k>``.
    ``votemanager.parse`` unterscheidet sie an der Endung ``_liste`` — dieser
    Test ist der Beweis, dass beide Schemata wirklich im Bestand liegen und
    der Parser nicht nur eines von ihnen je gesehen hat.

    **Achtung, naheliegender Fehlschluss:** ``D1_1`` steht in BEIDEN Köpfen —
    2021 ist es die Personenstimme für Listenplatz 1. Die Unterscheidung
    taugt nur über ``_liste`` bzw. ``D1_2_1``."""
    koepfe = {}
    for ordner in ORDNER:
        praefix = reference.meta_path(ordner).stem
        koepfe[ordner.name] = (ordner / f"{praefix}-stadt.csv").read_text(
            encoding="utf-8-sig").splitlines()[0].split(";")

    assert "D1_liste" in koepfe["referenz-2021"], "2021 ist das alte Schema"
    assert "D1_2_1" not in koepfe["referenz-2021"]
    assert "D1_liste" not in koepfe["referenz-2026"], "2026 ist das neue Schema"
    assert "D1_2_1" in koepfe["referenz-2026"]
    for name, kopf in koepfe.items():
        fehlend = [s for s in votemanager.REQUIRED_COLUMNS if s not in kopf]
        assert not fehlend, f"{name}: Kopfzeile ohne {fehlend}"


def test_2026_ist_fertig_ausgezaehlt_und_deckungsgleich():
    """Der Wahlabend selbst: 133 von 133 Bezirken, und die nachgerechnete
    Sitzverteilung deckt sich mit der, die der Votemanager ausgewiesen hat."""
    ordner = KOMMUNALWAHL / "referenz-2026"
    meta = json.loads((ordner / "ratswahl-2026.json").read_text(encoding="utf-8"))
    stadt = votemanager.parse((ordner / "ratswahl-2026-stadt.csv").read_text(encoding="utf-8-sig"))[0]
    assert stadt.reports_received == stadt.reports_expected == 133

    gerechnet: dict[str, int] = {}
    nach_label = {p["label"]: p["slug"] for p in meta["parteien"]}
    for m in meta["sitzverteilung"]:
        slug = nach_label[m["party"]]
        gerechnet[slug] = gerechnet.get(slug, 0) + 1
    assert gerechnet == meta["sitze_votemanager"], (
        "Nachgerechnete und ausgewiesene Sitzverteilung weichen ab — "
        "scripts/wahl_einfrieren.py hätte das abgefangen; hier steht die Datei also falsch im Repo.")


def test_verlauf_2026_endet_ausgezaehlt():
    """Der Minutenverlauf des Abends ist nicht wiederholbar — wenn er im Repo
    liegt, muss er wenigstens bis zum Ende reichen."""
    punkte = json.loads((KOMMUNALWAHL / "referenz-2026" / "verlauf.json").read_text(encoding="utf-8"))
    assert len(punkte) > 50
    assert [p["at"] for p in punkte] == sorted(p["at"] for p in punkte)
    assert punkte[-1]["districts_counted"] == 133
    assert sum(punkte[-1]["seats"].values()) == 52
