"""Der Cron muss jeden registrierten Leser auch aufrufen können.

**Warum das ein Test ist.** `scripts/check_finanzdaten.py` ruft für jede
Finanzquelle mit eigenem Leser ``q.einlesen(store, p, nur_fehlende=True)``.
Ob eine Funktion diesen Aufruf annimmt, sagt keine Typprüfung: ``einlesen`` ist
als ``Callable[..., dict]`` deklariert, und ``...`` heißt „irgendwas". Ein Leser
mit abweichender Signatur fällt deshalb durch **kein** Netz — bis er im
laufenden Cron einen ``TypeError`` wirft.

Genau das ist am 03.09.2026 passiert: ``lies_kennzahlen(store, p)`` war seit
jeher ohne ``nur_fehlende`` registriert. Aufgefallen ist es erst auf **Prod**,
mitten im Lauf, nachdem der Haushaltsvollzug bereits geschrieben war — und
zwar nur, weil der Job ein Konto hat, das Alarm schlägt. Der Trockenlauf
(``--trocken``) sieht es prinzipiell nicht: Er meldet, was er täte, und ruft
die Leser gar nicht auf.

Der Test bindet die Signatur gegen den **echten** Aufruf, ohne etwas
auszuführen — er braucht weder Datenbank noch Netz.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.finanzquellen import QUELLEN  # noqa: E402

#: Wie der Cron ruft. Steht hier als Wert und wird unten gegen den Quelltext
#: gehalten — sonst veraltet die Kopie, und der Test prüft ab dem nächsten
#: Umbau die Vergangenheit.
CRON_ARGUMENTE = {"nur_fehlende": True}
CRON_SKRIPT = WURZEL / "scripts" / "check_finanzdaten.py"


def test_der_test_kennt_den_echten_aufruf():
    """Sicherung gegen den stillen Ausfall: Ändert jemand den Aufruf im Cron,
    prüft der Test unten sonst weiter die alte Form — grün und wertlos."""
    quelle = CRON_SKRIPT.read_text(encoding="utf-8")
    aufrufe = re.findall(r"\.einlesen\(([^)]*)\)", quelle)
    assert aufrufe, (
        f"In {CRON_SKRIPT.name} steht kein `.einlesen(...)` mehr — dann ruft "
        "der Cron die Leser anders und dieser Test prüft ins Leere.")
    for aufruf in aufrufe:
        schluessel = set(re.findall(r"(\w+)\s*=", aufruf))
        assert schluessel == set(CRON_ARGUMENTE), (
            f"Der Cron ruft `.einlesen({aufruf})` — dieser Test kennt aber "
            f"{sorted(CRON_ARGUMENTE)}. CRON_ARGUMENTE hier nachziehen.")


def test_jeder_registrierte_leser_passt_zum_cron_aufruf():
    """Die eigentliche Prüfung — für jede Quelle einzeln, mit Namen im Fehler.

    ``Signature.bind`` wirft denselben ``TypeError``, den der Cron bekäme, nur
    eben hier und ohne Datenbank.
    """
    schlecht: list[str] = []
    for key, q in sorted(QUELLEN.items()):
        if q.einlesen is None:
            continue
        try:
            inspect.signature(q.einlesen).bind(object(), object(), **CRON_ARGUMENTE)
        except TypeError as exc:
            schlecht.append(f"{key} → {q.einlesen.__name__}(): {exc}")
    assert not schlecht, (
        "Diese Leser kann der Cron nicht aufrufen — er stürzt beim ersten "
        "Dokument ab, das sie betrifft:\n  " + "\n  ".join(schlecht) +
        "\n\nBeheben: den fehlenden Parameter in die Signatur aufnehmen und "
        "auch benutzen (das Muster steht in `lies_jahresabschluesse`: alles "
        "lesen, nur Fehlendes speichern).")


def test_es_gibt_ueberhaupt_registrierte_leser():
    """Findet der Test keine einzige Quelle mit `einlesen`, liefe er über eine
    leere Liste und wäre grün, ohne etwas zu tun."""
    mit_leser = [k for k, q in QUELLEN.items() if q.einlesen is not None]
    assert len(mit_leser) >= 8, (
        f"nur {len(mit_leser)} Quellen mit eigenem Leser — Registry umgebaut?")


def test_nur_fehlende_wird_auch_benutzt_und_nicht_nur_angenommen():
    """Ein Parameter, den eine Funktion annimmt und ignoriert, ist schlimmer
    als keiner: Der Cron hielte den Lauf für eingeschränkt, und die Funktion
    schriebe trotzdem jedes Mal alles.

    Geprüft wird die Eigenschaft grob am Quelltext — jeder Leser muss den Wert
    an `source.vorhandene(...)` weiterreichen. Das ist die eine Stelle, an der
    er im ganzen Modul etwas bewirkt.
    """
    quelle = (WURZEL / "council" / "finanzquellen.py").read_text(encoding="utf-8")
    ohne: list[str] = []
    for key, q in sorted(QUELLEN.items()):
        if q.einlesen is None:
            continue
        name = q.einlesen.__name__
        m = re.search(rf"^def {re.escape(name)}\(.*?(?=^def |\Z)", quelle,
                      re.S | re.M)
        assert m, f"{name} nicht im Quelltext gefunden"
        if "vorhandene(" not in m.group(0):
            ohne.append(f"{key} → {name}()")
    assert not ohne, (
        "Diese Leser nehmen `nur_fehlende` an, reichen es aber nie an "
        "`source.vorhandene(...)` weiter — der Cron glaubt dann, er schränke "
        "ein, und sie schreiben trotzdem alles:\n  " + "\n  ".join(ohne))
