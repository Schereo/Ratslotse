"""Wächter: Jeder Dialekt mit ``inline_texts`` muss in ``extract_inline`` stehen.

**Warum es diesen Test braucht.** `allris_classic.inline_texts` und
`hannover_sim.inline_texts` funktionierten beide — an echten Fixtures und im
Fixture-Test geprüft —, aber `pipeline.extract_inline` kannte nur `rubin` und
`oldenburg`. Der Dialekt fiel im `else`-Zweig auf ``return 0``, ohne Fehler,
ohne Auffälligkeit. Ergebnis: 25.729 Hannoveraner Vorlagen ohne einen
einzigen Satz Text, nach einem 2:50-Stunden-Lauf mit 28.381 Abrufen — die
Adapter-Tests waren grün, weil sie `inline_texts` direkt aufrufen, nie über
`extract_inline`. Gemessen 11.09.2026.

Der nächste Dialekt mit ``inline_texts`` bekommt dieselbe Lücke, wenn ihn
niemand hier einträgt — deshalb liest dieser Test den Quelltext von
``extract_inline`` und hält ihn gegen jeden Adapter, der die Methode
tatsächlich definiert.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil

import council.cities.adapters as adapters_paket
import council.cities.pipeline as pipeline


def _dialekte_mit_inline_texts() -> set[str]:
    """Jeder Dialekt, dessen Adapter ``inline_texts`` selbst definiert.

    Nicht über eine Instanz geprüft (``hasattr``) — das fände auch eine
    geerbte oder zufällig gleichnamige Methode. Der Quelltext der Klasse
    selbst muss sie definieren.
    """
    treffer: set[str] = set()
    for modinfo in pkgutil.iter_modules(adapters_paket.__path__):
        if modinfo.name.startswith("_"):
            continue
        modul = importlib.import_module(f"council.cities.adapters.{modinfo.name}")
        for name, obj in vars(modul).items():
            if not (inspect.isclass(obj) and hasattr(obj, "dialect")):
                continue
            if "inline_texts" in obj.__dict__:
                treffer.add(obj.dialect)  # type: ignore[attr-defined]
    return treffer


def test_jeder_inline_texts_dialekt_steht_im_dispatcher():
    quelltext = inspect.getsource(pipeline.extract_inline)
    fehlend = [d for d in sorted(_dialekte_mit_inline_texts())
              if f'"{d}"' not in quelltext and f"'{d}'" not in quelltext]
    assert not fehlend, (
        f"{fehlend} definieren inline_texts, fehlen aber im "
        f"dialect-Dispatcher von pipeline.extract_inline — genau die Lücke, "
        f"die Hannovers 25.729 Vorlagen ohne Text ließ. Eintrag ergänzen.")


def test_der_dispatcher_nennt_keinen_dialekt_ohne_inline_texts():
    """Die Gegenrichtung: ein Eintrag, den kein Adapter mehr braucht.

    Verwaist er, sieht das nach einer Fähigkeit aus, die es gar nicht gibt.
    """
    vorhanden = _dialekte_mit_inline_texts()
    quelltext = inspect.getsource(pipeline.extract_inline)
    for zeile in quelltext.splitlines():
        zeile = zeile.strip()
        if not zeile.startswith(("if spec.dialect ==", "elif spec.dialect ==")):
            continue
        dialekt = zeile.split("==")[1].strip().strip('"\':')
        assert dialekt in vorhanden, (
            f"{dialekt!r} steht im Dispatcher, aber kein Adapter definiert "
            f"dafür inline_texts mehr — toter Zweig, aufräumen.")
