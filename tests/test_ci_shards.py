"""Die CI schneidet zwei Suiten in Teile — und kein Teil darf verloren gehen.

Seit 11/2026 laufen die Python-Suite auf zwei und die Browsertests auf acht
Läufern (``.github/workflows/test.yml``, ``e2e.yml``). Schneller wird die CI
dadurch nur, solange die Teile zusammen noch DIE GANZE Suite sind. Der Fehler,
gegen den diese Datei gebaut ist, hat keine Fehlermeldung: Ein Teil, den kein
Läufer fährt, ist nicht rot, sondern fehlt — alle Prüfungen grün, ein Achtel
der Tests nie gelaufen.

Drei Stellen können das auslösen, und jede hat hier ihren Test:

* die Zuordnung selbst (Datei → Teil),
* die Matrix im Workflow (eine Lücke oder ein doppelter Eintrag),
* die Sammelprüfung ``test``, an deren Namen der Merge hängt.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.ci_shards import parse_shard, shard_of

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FRONTEND = ROOT / "web" / "frontend"
PLANNER = FRONTEND / "tests" / "shard-specs.mjs"

_NODE = shutil.which("node")
needs_node = pytest.mark.skipif(_NODE is None, reason="Node fehlt")


# --- Python-Suite: Datei → Teil ---------------------------------------------

def _test_files() -> list[str]:
    return sorted(f"tests/{p.name}" for p in (ROOT / "tests").glob("test_*.py"))


@pytest.mark.parametrize("total", [1, 2, 3, 5])
def test_jede_testdatei_laeuft_in_genau_einem_teil(total):
    files = _test_files()
    by_shard = {i: [f for f in files if shard_of(f, total) == i] for i in range(1, total + 1)}
    assert sorted(f for part in by_shard.values() for f in part) == files


def test_die_zuordnung_ist_in_jedem_prozess_dieselbe():
    """Jeder xdist-Arbeiter schneidet für sich. Mit Pythons ``hash()`` — je
    Prozess gesalzen — liefen Tests doppelt oder gar nicht, und zwar bei jedem
    Lauf andere. Die festen Werte hier ändern sich nur, wenn jemand die
    Prüfsumme austauscht."""
    assert [shard_of("tests/test_health.py", n) for n in (2, 3, 8)] == [2, 1, 4]


def test_zwei_teile_sind_ungefaehr_gleich_gross():
    """Die CI kauft mit dem zweiten Läufer Wartezeit. Schnitte die Prüfsumme
    schief, wartete jeder Pull Request weiter auf den großen Teil."""
    files = _test_files()
    first = sum(1 for f in files if shard_of(f, 2) == 1)
    assert 0.4 <= first / len(files) <= 0.6, (
        f"{first} von {len(files)} Testdateien in Teil 1 — die Aufteilung in "
        "tests/ci_shards.py verteilt nicht mehr gleichmäßig.")


@pytest.mark.parametrize("spec", ["0/2", "3/2", "1", "a/b", "1/0", "1/2/3"])
def test_ein_teil_den_es_nicht_gibt_wird_abgewiesen(spec):
    """``--shard 3/2`` wählte still NICHTS aus — null Tests, alles grün."""
    with pytest.raises(ValueError):
        parse_shard(spec)


def test_ein_gueltiger_teil_wird_gelesen():
    assert parse_shard("2/3") == (2, 3)


# --- Die Matrix in den Workflows --------------------------------------------

def _matrix_shards(workflow: str) -> list[int]:
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    found = re.findall(r"^\s+shard: \[([\d,\s]+)\]\s*$", text, re.M)
    assert len(found) == 1, f"{workflow}: genau eine Zeile `shard: [...]` erwartet, gefunden {len(found)}"
    return [int(n) for n in found[0].split(",")]


@pytest.mark.parametrize("workflow", ["test.yml", "e2e.yml"])
def test_die_matrix_zaehlt_lueckenlos_ab_eins(workflow):
    """Die Gesamtzahl kommt aus ``strategy.job-total``, also aus der LÄNGE der
    Liste. ``[1, 2, 4]`` hieße: Teil 3 von 3 fährt niemand. ``[1, 1, 2]``
    ebenso — und beides wäre grün."""
    shards = _matrix_shards(workflow)
    assert shards == list(range(1, len(shards) + 1)), (
        f"{workflow}: `shard: {shards}` muss lückenlos von 1 bis {len(shards)} zählen.")


def _code_lines(workflow: str) -> str:
    """Der Workflow ohne Kommentarzeilen — die Begründungen daneben nennen
    dieselben Wörter."""
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_die_python_suite_nimmt_teil_und_gesamtzahl_aus_der_matrix():
    """Eine von Hand geschriebene Gesamtzahl (``--shard … /2``) überlebt die
    nächste Änderung der Matrix nicht — und drei Läufer mit ``/2`` führen ein
    Drittel der Arbeit doppelt aus, statt etwas auszulassen. Umgekehrt ließe
    ``/3`` bei zwei Läufern ein Drittel aus."""
    assert ("pytest tests/ -q -n auto --shard ${{ matrix.shard }}/${{ strategy.job-total }}"
            in _code_lines("test.yml"))


def test_die_browsertests_nehmen_teil_und_gesamtzahl_aus_der_matrix():
    code = _code_lines("e2e.yml")
    assert "SHARD: ${{ matrix.shard }}" in code and "SHARDS: ${{ strategy.job-total }}" in code
    assert 'node tests/shard-specs.mjs "$SHARD" "$SHARDS"' in code
    # Ohne Dateien führe Playwright die ganze Suite; der alte Schnitt nach
    # Anzahl darf nicht daneben stehen bleiben.
    assert "npx playwright test $SPECS" in code and "--shard=" not in code


def test_der_merge_haengt_weiter_an_einer_pruefung_namens_test():
    """Die Regel für ``main`` verlangt die Prüfung ``test``, und
    ``scripts/merge_wenn_gruen.py`` ebenso. Nach der Aufteilung gibt es sie
    nur noch, weil ein eigener Auftrag so heißt und die anderen einsammelt.

    ``if: always()`` gehört dazu: Ohne das wird der Auftrag ÜBERSPRUNGEN,
    sobald ein Teil rot ist, und „übersprungen" gilt als bestanden.
    """
    yaml = pytest.importorskip("yaml")
    jobs = yaml.safe_load((WORKFLOWS / "test.yml").read_text(encoding="utf-8"))["jobs"]
    gate = jobs["test"]
    assert "name" not in gate, "Der Auftrag muss `test` heißen — ein `name:` benennt die Prüfung um."
    others = sorted(set(jobs) - {"test"})
    assert sorted(gate["needs"]) == others, (
        f"`test` muss ALLE anderen Aufträge einsammeln ({others}), sonst ist "
        "ein roter darunter kein Hindernis für den Merge.")
    assert gate["if"] == "always()"
    assert "needs.*.result" in json.dumps(gate["steps"])

    from scripts.merge_wenn_gruen import PFLICHTPRUEFUNG
    assert PFLICHTPRUEFUNG == "test"


# --- Browsertests: Datei → Teil ---------------------------------------------

def _plan(total: int) -> list[list[str]]:
    assert _NODE is not None
    out = subprocess.run([_NODE, str(PLANNER), "--plan", str(total), "--json"],
                         capture_output=True, text=True, check=True, cwd=FRONTEND).stdout
    return json.loads(out)


def _spec_files() -> list[str]:
    return sorted(p.name for p in (FRONTEND / "tests" / "e2e").glob("*.spec.ts"))


@needs_node
@pytest.mark.parametrize("total", [1, 4, 8, 12])
def test_jede_spec_datei_laeuft_in_genau_einem_teil(total):
    planned = [f for part in _plan(total) for f in part]
    assert sorted(planned) == _spec_files()


@needs_node
def test_die_matrix_der_browsertests_hat_keinen_leeren_teil():
    total = len(_matrix_shards("e2e.yml"))
    empty = [i + 1 for i, part in enumerate(_plan(total)) if not part]
    assert not empty, f"Teil(e) {empty} von {total} bekämen keine Datei — die Matrix in e2e.yml ist zu groß."


@needs_node
def test_die_teile_der_browsertests_sind_ausgewogen():
    """Der Sinn der Verteilung nach Dauer: Der längste Teil bestimmt die
    Wartezeit. Laufen die Zahlen davon — die Suite wächst, die Dauern in
    ``e2e-durations.json`` veralten —, meldet sich das hier, mit dem Befehl."""
    seconds = json.loads((FRONTEND / "tests" / "e2e-durations.json").read_text(encoding="utf-8"))["seconds"]
    known = sorted(seconds.values())
    fallback = known[len(known) // 2]
    total = len(_matrix_shards("e2e.yml"))
    weights = [sum(seconds.get(f, fallback) for f in part) for part in _plan(total)]
    mean = sum(weights) / len(weights)
    assert max(weights) <= 1.25 * mean, (
        f"Der längste Teil trägt {max(weights) / 60:.1f} min bei einem Schnitt von "
        f"{mean / 60:.1f} min. Dauern neu ziehen: python scripts/e2e_durations.py --write")


@needs_node
def test_eine_spec_datei_ohne_gemessene_dauer_laeuft_trotzdem():
    """Die Dauern entscheiden über die Balance, nie über die Abdeckung: Eine
    neue Datei steht in keiner Messung und muss trotzdem in einem Teil
    landen — mit mittlerem Gewicht, nicht mit null."""
    assert _NODE is not None
    script = (
        f"import {{ planShards }} from {json.dumps(PLANNER.as_uri())};"
        "console.log(JSON.stringify(planShards(['a', 'b', 'c', 'neu'], { a: 10, b: 6, c: 2, weg: 99 }, 2)));"
    )
    shards = json.loads(subprocess.run([_NODE, "--input-type=module", "-e", script],
                                       capture_output=True, text=True, check=True).stdout)
    assert sorted(f for s in shards for f in s["files"]) == ["a", "b", "c", "neu"]
    # „neu" wiegt den mittleren bekannten Wert (6), „weg" gibt es nicht mehr.
    assert sorted(s["weight"] for s in shards) == [12, 12]


def test_die_dauern_werden_aus_den_zeilen_des_reporters_gelesen():
    """Ändert Playwright das Format seiner Ergebniszeile, liest
    ``e2e_durations.py`` nichts mehr — und sagt das (statt eine leere Datei
    zu schreiben). Hier steht, welches Format es erwartet."""
    from scripts.e2e_durations import parse_log

    log = "\n".join([
        "browser\tBrowsertests\t2026-11-22T15:06:20Z   ✓   1 [setup] › tests/e2e/auth.setup.ts:22:6 › Sitzungen anlegen (1.1s)",
        "browser\tBrowsertests\t2026-11-22T15:06:25Z   ✓   2 [chromium] › tests/e2e/27-plaene.spec.ts:38:5 › der Reiter heißt „Pläne“ (7.0s)",
        "browser\tBrowsertests\t2026-11-22T15:06:26Z   ✓   3 [chromium] › tests/e2e/27-plaene.spec.ts:52:5 › zweiter (850ms)",
        "browser\tBrowsertests\t2026-11-22T15:06:40Z   ✘   4 [chromium] › tests/e2e/04-council.spec.ts:126:7 › Ratsinformationssystem › lädt neu (1.2m)",
    ])
    assert parse_log(log) == pytest.approx({"27-plaene.spec.ts": 7.85, "04-council.spec.ts": 72.0})
