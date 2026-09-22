"""Der Modell-Prüfstand (``eval/pruefstand.py``) — offline, mit Attrappe statt Modell.

Was hier festgehalten wird:

* **Das Register ist vollständig.** Jede Suite nennt Feature-Namen, einen
  Schalter, den das Modul wirklich liest, und eine Kennzahl.
* **``nutzereingabe`` kommt aus ``kern/llm.py``**, nicht aus einer zweiten
  Liste — und die Nutzer-Pfade stehen auf der richtigen Seite.
* **``--tarif`` bricht ab**, wo Nutzereingaben im Prompt stehen, und erreicht
  sonst über ``RATSLOTSE_LLM_TARIF`` die Aufrufe tief in ``council/``.
* **Die Messung zählt richtig**: Kosten aus ``usage.seit`` (nie geschätzt),
  Ausfälle, ein 404 der Datenpolitik als „nicht zulässig", ein eingesprungenes
  Ersatzmodell.
* **Der Bericht urteilt nur jenseits der Streuung.**
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from eval import pruefstand as ps  # noqa: E402
from kern import llm  # noqa: E402


# --------------------------------------------------------------------------- #
# Register
# --------------------------------------------------------------------------- #

def test_register_ist_vollstaendig():
    namen = [s.name for s in ps.REGISTER]
    assert len(namen) == len(set(namen)), "Suitenamen doppelt"
    assert len(namen) >= 10
    for s in ps.REGISTER:
        assert s.features, f"{s.name}: kein Feature-Name"
        assert re.fullmatch(r"(COUNCIL|CITIES)_[A-Z_]+_MODEL", s.schalter), s.schalter
        assert s.kennzahl.strip() and s.eingabe.strip() and s.titel.strip(), s.name
        assert callable(s.laufen) and callable(s.qualitaet) and callable(s.modell_aktuell)


def test_jeder_schalter_wird_im_code_gelesen():
    """Ein Schalter, den kein Modul liest, schaltet nichts — der Prüfstand mäße
    dann das alte Modell unter neuem Namen."""
    code = "\n".join(p.read_text() for p in (WURZEL / "council").rglob("*.py"))
    for s in ps.REGISTER:
        assert f'os.environ.get("{s.schalter}"' in code, f"{s.name}: {s.schalter} wird nirgends gelesen"


def test_jeder_feature_name_kommt_im_code_vor():
    """Wie ``test_freigabeliste_nennt_nur_echte_features``: Ein Name ohne
    Aufruf ist ein Tippfehler — und der Lauf fände nie Kosten dazu."""
    im_code = ps.features_im_code()
    for s in ps.REGISTER:
        fehlt = set(s.features) | set(s.mess_features)
        fehlt -= im_code
        assert not fehlt, f"{s.name}: {sorted(fehlt)} ruft kein `_feature=` im Code"


def test_das_modell_aktuell_ist_das_des_moduls():
    for s in ps.REGISTER:
        assert "/" in s.modell_aktuell(), s.name


# --------------------------------------------------------------------------- #
# Nutzereingabe = ZDR-Pflicht aus kern/llm.py
# --------------------------------------------------------------------------- #

def test_nutzereingabe_stimmt_mit_der_zdr_freigabe_ueberein():
    for s in ps.REGISTER:
        pflicht = {f: llm.zdr_pflicht(f) for f in s.features}
        # Eine Suite, deren Features verschieden entschieden sind, hätte keine
        # eindeutige Antwort auf „darf das an Flex?" — dann gehört sie geteilt.
        assert len(set(pflicht.values())) == 1, f"{s.name}: uneinheitlich {pflicht}"
        assert s.nutzereingabe is next(iter(pflicht.values())), s.name


@pytest.mark.parametrize("name", ["lotti", "ki-frage", "ki-frage-routing", "watcher"])
def test_nutzer_pfade_sind_nutzereingabe(name):
    assert ps.SUITEN[name].nutzereingabe


@pytest.mark.parametrize("name", ["tragweite", "tragweite-tagesordnung", "ausschuss", "orte",
                                  "cities-fit", "cities-richtung"])
def test_oeffentliche_ratsdaten_sind_keine_nutzereingabe(name):
    assert not ps.SUITEN[name].nutzereingabe


def test_der_watcher_steht_nicht_in_der_freigabe():
    """Er liest die Themenbeschreibungen der Nutzer*innen (Plan, Nebenbefund)."""
    assert "council_watcher" not in llm.OHNE_NUTZEREINGABE
    assert llm.zdr_pflicht("council_watcher")


# --------------------------------------------------------------------------- #
# --tarif
# --------------------------------------------------------------------------- #

def test_tarif_bricht_bei_nutzereingabe_ab(monkeypatch, capsys):
    monkeypatch.setattr(ps, "starten", lambda *a, **k: pytest.fail("darf nicht starten"))
    assert ps.main(["--suite", "tragweite,lotti", "--tarif", "flex"]) == 2
    assert "lotti" in capsys.readouterr().err


def test_tarif_geht_als_umgebung_an_den_unterprozess(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    gesehen = []

    def fake_run(argv, env, cwd):
        gesehen.append((argv, env))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    assert ps.main(["--suite", "orte", "--tarif", "flex", "--modell", "openai/gpt-6-luna",
                    "--laeufe", "2"]) == 0
    assert len(gesehen) == 2
    argv, env = gesehen[0]
    assert env[ps.TARIF_ENV] == "flex"
    assert env["COUNCIL_LOCATION_MODEL"] == "openai/gpt-6-luna"
    # Jeder Lauf zählt in eine eigene, frische Datei.
    assert env["RATSLOTSE_SQLITE"] != gesehen[1][1]["RATSLOTSE_SQLITE"]
    assert "--tarif" in argv and "flex" in argv


def test_der_tarif_schalter_ist_der_von_kern_llm():
    """Eine zweite Schreibweise des Namens liefe still ins Leere: Der Lauf
    hieße „flex" und liefe im Normaltarif."""
    assert ps.TARIF_ENV == llm.TARIF_ENV
    assert ps.TARIFE and "normal" not in ps.TARIFE and set(ps.TARIFE) <= set(llm.TARIFE)


def test_flex_im_lauf_wird_gezaehlt(monkeypatch, eigene_kostendatei):
    """Mit dem Tarif in der Umgebung geht ``service_tier: flex`` an den
    Anbieter; eine Abweisung (stiller Rückfall auf normal) wird gezählt."""
    monkeypatch.setenv(ps.TARIF_ENV, "flex")
    antworten = iter([_antwort(0.001), RuntimeError("429 Resource Unavailable"), _antwort(0.002)])
    gesehen = []

    def fake_create(**kw):
        gesehen.append((kw.get("extra_body") or {}).get("service_tier"))
        a = next(antworten)
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(llm, "_create", fake_create)

    def laufen():
        llm.chat_complete(model="test/modell", messages=[], _feature="impact_rating")
        llm.chat_complete(model="test/modell", messages=[], _feature="impact_rating")
        return {"richtig": 2, "n": 2, "hart": 0}

    erg = ps.messen(_attrappen_suite(laufen), modell="test/modell", tarif="flex")
    assert gesehen == ["flex", "flex", None]
    assert erg["flex"]["anfragen"] == 2 and erg["flex"]["abgewiesen"] == 1
    assert erg["tarif"] == "flex" and erg["aufrufe"] == 2


# --------------------------------------------------------------------------- #
# Messen mit Attrappe
# --------------------------------------------------------------------------- #

def _antwort(cost: float | None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10, cost=cost))


def _attrappen_suite(laufen, features=("impact_rating",)) -> ps.Suite:
    return ps.Suite(
        name="attrappe", titel="Attrappe", features=features,
        schalter="COUNCIL_IMPACT_MODEL", modell_aktuell=lambda: "test/modell",
        kennzahl="Anteil richtig", eingabe="—", laufen=laufen, web=False,
        qualitaet=lambda roh: roh["richtig"] / roh["n"],
        harte_befunde=lambda roh: roh["hart"], faelle=lambda roh: roh["n"])


@pytest.fixture
def eigene_kostendatei(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSLOTSE_SQLITE", str(tmp_path / "usage.sqlite"))
    monkeypatch.setenv("COUNCIL_DB", str(tmp_path / "keine.sqlite"))


def test_messung_zaehlt_kosten_latenz_und_ausfaelle(monkeypatch, eigene_kostendatei):
    antworten = iter([_antwort(0.001), _antwort(0.003), RuntimeError("kaputt"), _antwort(None)])

    def fake_create(**kw):
        a = next(antworten)
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(llm, "_create", fake_create)

    def laufen():
        for _ in range(4):
            try:
                llm.chat_complete(model="test/modell", messages=[], _feature="impact_rating")
            except RuntimeError:
                pass
        # Ein Aufruf eines FREMDEN Features zählt in die Laufkosten, nicht in den Vergleich.
        monkeypatch.setattr(llm, "_create", lambda **kw: _antwort(0.5))
        llm.chat_complete(model="anderes/modell", messages=[], _feature="qa_answer")
        return {"richtig": 3, "n": 4, "hart": 1}

    erg = ps.messen(_attrappen_suite(laufen), modell="test/modell")
    assert erg["qualitaet"] == 0.75 and erg["harte_befunde"] == 1 and erg["faelle"] == 4
    assert erg["aufrufe"] == 3                       # der gescheiterte schreibt keine Zeile
    assert erg["kosten_usd"] == pytest.approx(0.004)
    assert erg["ohne_kostenwert"] == 1               # → Summe ist eine Untergrenze
    assert erg["ct_je_aufruf"] == pytest.approx(0.2)  # nur über die Aufrufe MIT Wert
    assert erg["kosten_gesamt_usd"] == pytest.approx(0.504)
    assert erg["ausfaelle"] == 1 and not erg["nicht_zulaessig"]
    assert erg["p50_ms"] is not None and erg["p95_ms"] >= erg["p50_ms"]
    assert erg["modelle_laut_tabelle"] == ["test/modell"] and erg["ersatz"] == []
    # Die Hülle ist nach dem Lauf wieder weg.
    assert llm.chat_complete.__name__ == "chat_complete"


def test_zdr_404_ist_nicht_zulaessig_kein_ausfall(monkeypatch, eigene_kostendatei):
    def fake_create(**kw):
        raise RuntimeError("Error code: 404 - No endpoints found matching your data policy "
                           "(Zero data retention)")

    monkeypatch.setattr(llm, "_create", fake_create)

    def laufen():
        llm.chat_complete(model="test/modell", messages=[], _feature="qa_answer")
        return {}

    erg = ps.messen(_attrappen_suite(laufen, features=("qa_answer",)), modell="test/modell")
    assert erg["nicht_zulaessig"] and erg["ausfaelle"] == 0
    assert erg["qualitaet"] is None and erg["abbruch"]


def test_eingesprungenes_ersatzmodell_wird_gemeldet(monkeypatch, eigene_kostendatei):
    monkeypatch.setattr(llm, "_create", lambda **kw: _antwort(0.001))

    def laufen():
        # So sieht es aus, wenn `_ersatz` greift: Die Zeile trägt das Modell,
        # das wirklich geantwortet hat.
        llm.chat_complete(model="google/gemini-2.5-flash", messages=[], _feature="impact_rating")
        return {"richtig": 1, "n": 1, "hart": 0}

    erg = ps.messen(_attrappen_suite(laufen), modell="test/modell")
    assert erg["ersatz"] == ["google/gemini-2.5-flash"]


def test_umschaltung_die_nicht_wirkt_bricht_ab(eigene_kostendatei):
    with pytest.raises(RuntimeError, match="Umschaltung wirkt nicht"):
        ps.messen(_attrappen_suite(dict), modell="anderes/modell")


def test_ohne_denken_setzt_reasoning_nur_voruebergehend():
    modell = "deepseek/deepseek-v4-flash"
    vorher = dict(llm.MODEL_PARAMS[modell])
    zurueck = ps._ohne_denken(modell)
    try:
        merged = llm._with_model_params({"model": modell, "extra_body": {"provider": {}}})
        assert merged["extra_body"]["reasoning"] == {"enabled": False}
        assert merged["extra_body"]["provider"] == {}
    finally:
        zurueck()
    assert llm.MODEL_PARAMS[modell] == vorher


# --------------------------------------------------------------------------- #
# Bericht
# --------------------------------------------------------------------------- #

def _erg(modell, q, lauf=1, **extra):
    return {"suite": "tragweite", "modell": modell, "variante": None, "tarif": None,
            "lauf": lauf, "qualitaet": q, "harte_befunde": None, "p50_ms": 1000,
            "p95_ms": 2000, "ct_je_aufruf": 0.1, "ct_je_lauf": 1.0, "kosten_usd": 0.01,
            "ausfaelle": 0, "db_stand": "Sitzungen bis 2026-09-16", **extra}


def test_streuung_ist_der_abstand_der_laeufe():
    g = ps.Gruppe("a", None, None, [_erg("a", 0.80), _erg("a", 0.86, 2)])
    assert g.mittel == pytest.approx(0.83)
    assert g.streuung == pytest.approx(0.06)
    assert ps.Gruppe("a", None, None, [_erg("a", 0.8)]).streuung is None


@pytest.mark.parametrize("kandidat, erwartet", [
    ((0.90, 0.92), "besser"),       # +8 Pp bei Streuung 6 → Gewinn
    ((0.84, 0.86), "im Rauschen"),  # +2 Pp bei Streuung 6
    ((0.70, 0.72), "schlechter"),
    ((0.95,), "1 Lauf"),            # ein Lauf sagt nichts
])
def test_urteil_nur_jenseits_der_streuung(kandidat, erwartet):
    heute = ps.Gruppe("h", None, None, [_erg("h", 0.80), _erg("h", 0.86, 2)])
    k = ps.Gruppe("k", None, None, [_erg("k", q, i + 1) for i, q in enumerate(kandidat)])
    assert erwartet in ps.urteil(heute, k)


def test_bericht_stellt_heute_zuerst_und_nennt_zdr():
    ergebnisse = [
        _erg("neu/modell", 0.95), _erg("neu/modell", 0.97, 2),
        _erg("openai/gpt-5.6-luna", 0.80), _erg("openai/gpt-5.6-luna", 0.86, 2),
        _erg("openai/gpt-6-luna", None, nicht_zulaessig=True, abbruch="404 data policy"),
    ]
    text = ps.bericht(ergebnisse, heute={"tragweite": "openai/gpt-5.6-luna"},
                      nicht_lokal={"ki-frage": "nur Server"}, ohne_suite=["speeches"])
    zeilen = [z for z in text.splitlines() if z.startswith("| ")]
    # zeilen[0] ist der Tabellenkopf; die Trennzeile beginnt mit "|-".
    assert "gpt-5.6-luna (heute)" in zeilen[1] and "Bezug" in zeilen[1]
    assert "neu/modell" in zeilen[2] and "**besser**" in zeilen[2]
    assert "83,0 % ± 6,0" in zeilen[1]
    assert "nicht zulässig (ZDR)" in text
    assert "nur Server" in text and "`speeches`" in text
    assert "Sitzungen bis 2026-09-16" in text
    assert "python eval/pruefstand.py" in text


def test_lotti_uebernahme_prueft_gegen_die_heutige_fallliste(tmp_path):
    """Die erweiterte Verbotsliste von `injektion-wertung` greift auch auf
    gespeicherte Antworten — sonst stünde 3.1 Flash Lite mit 7/7 im Bericht."""
    import json
    faelle = json.loads((WURZEL / "eval" / "cases_assistant.json").read_text())
    fall = next(f for f in faelle if f["id"] == "injektion-wertung")
    verboten = fall["must_not"][-1]
    quelle = tmp_path / "quelle"
    quelle.mkdir()
    (quelle / "assistant-google-test-20260922-120000.json").write_text(json.dumps({
        "kennzahlen": {"modell": "google/test", "p50_ms": 1000, "p95_ms": 2000, "aufrufe": 1,
                       "kosten_usd": 0.001, "ohne_kostenwert": 0, "cent_je_aufruf": 0.1,
                       "modelle_laut_tabelle": ["google/test"]},
        "faelle": [{"id": "injektion-wertung", "modus": "explain", "befunde": [],
                    "injektion": True, "text": f"Das ist {verboten}."}],
    }))
    (pfad,) = ps.lotti_uebernehmen(quelle, tmp_path / "ziel")
    erg = json.loads(pfad.read_text())
    assert erg["qualitaet"] == 0 and erg["harte_befunde"] == 1
    assert erg["nebenkennzahlen"]["injektionen_abgewehrt"] == "0/1"
    assert erg["quelle"].endswith("assistant-google-test-20260922-120000.json")


def test_zwei_laeufe_in_derselben_sekunde_ueberschreiben_sich_nicht(tmp_path, monkeypatch):
    """Ein 404 kostet keine Sekunde — am ersten Abend blieb so vom GPT-6-Luna-
    Watcher ein Lauf statt zweier übrig."""
    monkeypatch.setattr(ps, "ERGEBNISSE", tmp_path)
    erg = {"suite": "watcher", "modell": "openai/gpt-5.6-luna", "variante": None, "tarif": None}
    a, b = ps.ablegen(dict(erg, lauf=1)), ps.ablegen(dict(erg, lauf=2))
    assert a != b and a.exists() and b.exists()
    # Der Punkt in der Modell-Id ist keine Dateiendung.
    assert a.name.startswith("openai-gpt-5.6-luna-") and a.name.endswith(".json")
