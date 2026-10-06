"""Herzschlag: Kostenalarm und die still wirkungslose Selbstprüfung (Review 05.10.2026)."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kern import usage
from kern.store import Store

WURZEL = Path(__file__).resolve().parents[1]


def _modul():
    spec = importlib.util.spec_from_file_location(
        "check_herzschlag_kosten", WURZEL / "scripts" / "check_herzschlag.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # type: ignore[union-attr]
    return m


herzschlag = _modul()


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    """Eigene Konten- und Kosten-DB, keine Rats-DB, Mails abgefangen."""
    konten = tmp_path / "ratslotse.sqlite"
    Store(konten).close()
    monkeypatch.setenv("RATSLOTSE_DB", str(konten))
    monkeypatch.setenv("RATSLOTSE_SQLITE", str(konten))
    monkeypatch.setenv("COUNCIL_DB", str(tmp_path / "fehlt.sqlite"))
    monkeypatch.delenv(herzschlag.KOSTEN_ALARM_VAR, raising=False)
    mails: list[tuple[str, str]] = []
    import kern.alerts as alerts
    monkeypatch.setattr(alerts, "notify_admin",
                        lambda text, betreff=None, fusszeile=None: mails.append((betreff, text)))
    # Alle Jobs gelten als frisch — sonst meldet der Herzschlag stumme Jobs.
    monkeypatch.setattr(herzschlag, "schweigende", lambda store: [])
    return {"konten": konten, "mails": mails}


def _kosten_gestern(db: Path, feature: str, usd: float | None, n: int = 1,
                    pin: int = 0, pout: int = 0) -> None:
    """Zeilen mit einem UTC-Zeitstempel mitten im gestrigen Ortstag."""
    gestern_mittag = datetime.fromisoformat(herzschlag.gestern() + "T12:00:00").astimezone(timezone.utc)
    usage._connect().close()   # Tabelle anlegen
    with sqlite3.connect(db) as conn:
        for _ in range(n):
            conn.execute("INSERT INTO llm_usage(ts, feature, model, prompt_tokens, completion_tokens, "
                         "cost_usd) VALUES (?,?,?,?,?,?)",
                         (gestern_mittag.strftime("%Y-%m-%d %H:%M:%S"), feature,
                          "openai/gpt-6-luna", pin, pout, usd))


def test_tageskosten_summiert_echte_und_geschaetzte_kosten(umgebung):
    _kosten_gestern(umgebung["konten"], "qa_answer", 0.5, n=4)
    # Ohne cost_usd: Schätzung aus PRICES (1 Mio. Eingabe-Tokens Luna = 0,10 $).
    _kosten_gestern(umgebung["konten"], "simple_summary", None, pin=1_000_000)
    k = usage.tageskosten(herzschlag.gestern())
    assert k["calls"] == 5
    assert k["usd"] == pytest.approx(2.1)
    assert k["features"][0] == ("qa_answer", 2.0)
    # Ein anderer Tag zählt nicht.
    assert usage.tageskosten("2000-01-01")["usd"] == 0


def test_hohe_kosten_melden_sich(umgebung):
    _kosten_gestern(umgebung["konten"], "qa_answer", 1.5, n=4)   # 6 $ > 5 $
    k = herzschlag.main()
    assert k["llm_kosten_gestern_usd"] == pytest.approx(6.0)
    assert [b for b, _ in umgebung["mails"]] == ["Ratslotse – hohe Modellkosten"]
    assert "qa_answer: 6.00 $" in umgebung["mails"][0][1]


def test_der_alltag_weckt_niemanden(umgebung):
    _kosten_gestern(umgebung["konten"], "qa_answer", 0.5, n=4)   # 2 $
    herzschlag.main()
    assert umgebung["mails"] == []


def test_die_schwelle_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.delenv(herzschlag.KOSTEN_ALARM_VAR, raising=False)
    assert herzschlag.kostenschwelle() == herzschlag.KOSTEN_ALARM_VORGABE
    monkeypatch.setenv(herzschlag.KOSTEN_ALARM_VAR, "12,5")
    assert herzschlag.kostenschwelle() == 12.5
    monkeypatch.setenv(herzschlag.KOSTEN_ALARM_VAR, "0")
    assert herzschlag.kostenschwelle() is None
    # Ein Tippfehler schaltet den Alarm NICHT ab.
    monkeypatch.setenv(herzschlag.KOSTEN_ALARM_VAR, "fünf")
    assert herzschlag.kostenschwelle() == herzschlag.KOSTEN_ALARM_VORGABE


def _urteile_gestern(db: Path, verdicts: list[str], stage: str = "model") -> None:
    gestern = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    with sqlite3.connect(db) as conn:
        for v in verdicts:
            conn.execute("INSERT INTO assistant_checks (created, route, verdict, stage, categories, "
                         "reasons) VALUES (?, '/', ?, ?, ?, ?)",
                         (gestern + "T10:00:00", v, stage, json.dumps([]), json.dumps([])))


def test_eine_stumme_selbstpruefung_meldet_sich(umgebung):
    """Fällt das Prüfer-Modell weg, urteilt ``judge`` still „unknown“ — das
    sah im Panel aus wie „nichts zu beanstanden“."""
    _urteile_gestern(umgebung["konten"], ["unknown"] * 6 + ["good"])
    # Die Regel-Stufe urteilt nie „unknown“ und verdünnt das Signal nicht.
    _urteile_gestern(umgebung["konten"], ["good"] * 20, stage="rules")
    k = herzschlag.main()
    assert (k["pruefer_urteile_gestern"], k["pruefer_unknown_gestern"]) == (7, 6)
    assert [b for b, _ in umgebung["mails"]] == ["Ratslotse – Selbstprüfung ohne Urteil"]


def test_einzelne_unknown_sind_kein_alarm(umgebung):
    _urteile_gestern(umgebung["konten"], ["unknown"] * 2 + ["good"] * 10)
    herzschlag.main()
    assert umgebung["mails"] == []


def test_zu_wenige_urteile_sind_kein_alarm(umgebung):
    """Ein einzelner Zeitüberschreiter um 3 Uhr ist 100 % „unknown“ — und nichts."""
    _urteile_gestern(umgebung["konten"], ["unknown"] * (herzschlag.PRUEFER_MIN_URTEILE - 1))
    herzschlag.main()
    assert umgebung["mails"] == []
