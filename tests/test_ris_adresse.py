"""Die Adresse des Ratsinformationssystems: eine Stelle, ein Umzug, ein Alarm.

Im 11/2026 zog die Stadt das Ratsinfo von ``buergerinfo.oldenburg.de`` nach
``ratsinfo.oldenburg.de/bi`` um. Der alte Host leitete jede Adresse auf die
Startseite um; der Abruf lief weiter, fand nichts und meldete „0 Termine“ —
tagelang, ohne Fehler (Geschichte in ``council/ris.py``).

Vier Zusagen, deren Bruch still bliebe:

- **Eine Stelle.** Der Host steht in ``council/ris.py`` und ``lib/ris.ts`` und
  sonst nirgends. Elf verstreute Konstanten waren der Grund, warum der Umzug
  elf Dateien brauchte.
- **Der Umzug alter Adressen** trifft jede Form und nichts anderes — und die
  Dokumentnummer bleibt die Identität eines Anhangs. Sonst wäre nach dem
  Umzug jede Anlage „neu“ und jedes Abo bekäme eine Änderungsmeldung.
- **Der Bestand** zieht beim Start um, einmal, samt Herkunfts-Fingerabdruck.
- **Der Alarm**: Ein dauerhafter Umzug, ein fremder Host, ein leerer Kalender
  sind FEHLER, kein leeres Ergebnis.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import Mock, call

import pytest

from council import agenda_diff, ris
from council.scraper import CouncilScraper
from council.store import CouncilStore

WURZEL = Path(__file__).resolve().parents[1]
ALT = "buergerinfo.oldenburg.de"


# ------------------------------------------------------------ eine Stelle

#: Wo der frühere Host stehen DARF — mit Grund. Alles andere ist eine zweite
#: Stelle, die beim nächsten Umzug vergessen wird.
ERLAUBT = {
    "council/ris.py": "die eine Stelle: FORMER_HOSTS und die Geschichte des Umzugs",
    "council/store_schema.py": "Docstring der Migration, die den Bestand umzieht",
    "council/cities/adapters/oldenburg.py":
        "Kennung des Body-Objekts im Städte-Speicher — eine Zeichenkette, keine Adresse",
    "web/frontend/lib/ris.ts": "RIS_FRUEHER und die Geschichte des Umzugs",
    "web/frontend/lib/haushalt-dokumente.test.ts": "prüft, dass frühere Adressen erkannt bleiben",
}
QUELLTEXT = ("council", "kern", "scripts", "eval", "web/backend/app", "web/frontend/app",
             "web/frontend/components", "web/frontend/lib", "ios/Ratslotse",
             "ios/Packages/RatslotseAPI/Sources")
ENDUNGEN = {".py", ".ts", ".tsx", ".swift", ".json", ".mjs"}


def _treffer() -> set[str]:
    aus: set[str] = set()
    for ordner in QUELLTEXT:
        basis = WURZEL / ordner
        if not basis.exists():
            continue
        for datei in basis.rglob("*"):
            if (datei.suffix in ENDUNGEN and "node_modules" not in datei.parts
                    and "__pycache__" not in datei.parts and datei.is_file()
                    and ALT in datei.read_text(encoding="utf-8", errors="ignore")):
                aus.add(datei.relative_to(WURZEL).as_posix())
    return aus


def test_der_fruehere_host_steht_nur_wo_er_stehen_darf():
    fremd = sorted(_treffer() - set(ERLAUBT))
    assert not fremd, (
        f"Diese Dateien nennen den früheren Host {ALT}:\n  " + "\n  ".join(fremd)
        + "\n\nBeheben: die Adresse über council/ris.py (page_url, session_url, "
          "template_url, file_url) bzw. web/frontend/lib/ris.ts bauen. Steht er dort "
          "zu Recht, mit Grund in ERLAUBT aufnehmen.")


def test_keine_ausnahme_ist_ueberfluessig():
    """Die Gegenrichtung: Eine Erlaubnis, die niemand braucht, fliegt raus."""
    treffer = _treffer()
    tot = sorted(k for k in ERLAUBT if k not in treffer)
    assert not tot, f"Stehen in ERLAUBT, nennen den Host aber nicht mehr: {tot}"


def test_frontend_und_backend_meinen_denselben_host():
    ts = (WURZEL / "web/frontend/lib/ris.ts").read_text(encoding="utf-8")
    host = re.search(r'RIS_HOST = "([^"]+)"', ts)
    assert host and host.group(1) == ris.HOST
    assert "`https://${RIS_HOST}/bi`" in ts and ris.BASE == f"https://{ris.HOST}/bi"
    for frueher in ris.FORMER_HOSTS:
        assert f'"{frueher}"' in ts, f"lib/ris.ts kennt den früheren Host {frueher} nicht"


# ---------------------------------------------------------------- Umzug

@pytest.mark.parametrize("alt, neu", [
    ("https://buergerinfo.oldenburg.de/getfile.php?id=7&type=do",
     "https://ratsinfo.oldenburg.de/bi/getfile.asp?id=7&type=do"),
    ("https://buergerinfo.oldenburg.de/si0057.php?__ksinr=42",
     "https://ratsinfo.oldenburg.de/bi/si0057.asp?__ksinr=42"),
    ("http://buergerinfo.oldenburg.de", "https://ratsinfo.oldenburg.de/bi"),
    ("https://buergerinfo.oldenburg.de/", "https://ratsinfo.oldenburg.de/bi/"),
    # Die Vorlagen-Recherche hieß auf dem alten Host anders.
    ("https://buergerinfo.oldenburg.de/vo040.asp", "https://ratsinfo.oldenburg.de/bi/vo0040.asp"),
    # Fremdes bleibt Zeichen für Zeichen stehen — auch mit .php.
    ("https://www.oldenburg.de/seite.php?x=1", "https://www.oldenburg.de/seite.php?x=1"),
    ("/council/decision?id=8525", "/council/decision?id=8525"),
])
def test_fruehere_adressen_ziehen_um(alt, neu):
    assert ris.current(alt) == neu
    assert ris.current(neu) == neu          # zweimal angewandt ändert nichts


def test_umzug_trifft_adressen_mitten_im_text_und_in_json():
    text = json.dumps({"anlagen": [{"label": "Lageplan",
                                    "url": "https://buergerinfo.oldenburg.de/getfile.php?id=9&type=do"}],
                       "hinweis": "siehe https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=3."})
    neu = json.loads(ris.current(text))
    assert neu["anlagen"][0]["url"] == ris.file_url(9)
    assert neu["hinweis"] == f"siehe {ris.template_url(3)}."
    assert ris.current_in({"a": [text, 5, None]})["a"][1:] == [5, None]
    assert ris.current(None) is None and ris.current("") == ""


def test_die_dokumentnummer_bleibt_die_identitaet_eines_anhangs():
    """DER Schutz vor der Mail-Flut. Der Tagesordnungs-Hash und der
    Anlagen-Diff hängen an ``anlagen_schluessel``; träfe das Muster nur die
    alte Endung, sähe nach dem Umzug jede Anlage jeder Sitzung neu aus — und
    ``check_committees`` meldete allen Abos eine geänderte Tagesordnung."""
    alt = [{"label": "Vorlage", "url": "https://buergerinfo.oldenburg.de/getfile.php?id=315885&type=do"}]
    neu = [{"label": "Vorlage", "url": ris.file_url(315885)}]
    assert agenda_diff.anlagen_schluessel(alt) == agenda_diff.anlagen_schluessel(neu) == ["315885"]


def test_die_dokumentkennung_einer_anlage_kommt_aus_alter_wie_neuer_adresse():
    """``council_agenda_attachments.document_id`` wird bei jedem Abgleich aus
    der Adresse gelesen; an ihr hängen Steckbrief, Seiten und Antrags-Auszug.
    Träfe das Muster nur ``getfile.php``, bliebe sie für jede neu gelesene
    Anlage leer — und nichts davon fände sein Dokument wieder."""
    from council.store_sitzungen import dokument_id

    assert dokument_id("https://buergerinfo.oldenburg.de/getfile.php?id=315885&type=do") == 315885
    assert dokument_id(ris.file_url(315885)) == 315885
    assert dokument_id(ris.template_url(7)) is None and dokument_id(None) is None


# --------------------------------------------------------------- Bestand

def _fingerabdruck(zeile) -> str:
    """Der Schlüssel, den ein Ingest für diese Zeile rechnen würde — über
    ``Herkunft.key`` selbst, nicht über eine Kopie der Formel."""
    from council.herkunft import Herkunft

    return Herkunft(kind=zeile["kind"], probe=zeile["probe"], document_id=zeile["document_id"],
                    label=zeile["label"], url=zeile["url"], citation=zeile["citation"],
                    page=zeile["page"], probe_result=zeile["probe_result"],
                    as_of=zeile["as_of"]).key()


def test_der_bestand_zieht_beim_start_um_und_nur_einmal(tmp_path):
    """Eine gewachsene Datenbank: alte Adressen in Anlagen, Vorlagen, im
    Tagesordnungs-Schnappschuss und in einer Herkunft — und ein Protokolltext,
    der die alte Adresse ZITIERT. Der bleibt, wie er geschrieben wurde."""
    pfad = str(tmp_path / "council.sqlite")
    CouncilStore(pfad).close()
    alt_datei = "https://buergerinfo.oldenburg.de/getfile.php?id=11&type=do"
    alt_seite = "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=7"
    zitat = "Die Unterlagen stehen unter https://buergerinfo.oldenburg.de bereit."
    store = CouncilStore(pfad)
    c = store._conn
    with c:
        c.execute("INSERT INTO council_templates (kvonr, template_number, title, document_url, "
                  "raw_text, fetched_at, status) VALUES (7, '26/0007', 'T', ?, ?, 'x', 'ok')",
                  (alt_datei, zitat))
        c.execute("INSERT INTO agenda_snapshots (ksinr, agenda_hash, items_json, created_at) "
                  "VALUES (1, 'h', ?, 'x')", (json.dumps([{"anlagen": [{"url": alt_datei}]}]),))
        c.execute("INSERT INTO council_provenance (key, kind, document_id, label, url, citation, "
                  "page, probe, probe_result, as_of, fetched_at) "
                  "VALUES ('alt', 'ris', NULL, 'Vorlage', ?, NULL, NULL, 'unknown', NULL, NULL, 'x')",
                  (alt_seite,))
        c.execute("DELETE FROM council_migration_marks WHERE marke = 'ratsinfo_host_2026_11'")
    store.close()

    store = CouncilStore(pfad)           # der Start nach dem Deploy
    c = store._conn
    vorlage = c.execute("SELECT document_url, raw_text FROM council_templates WHERE kvonr = 7").fetchone()
    assert vorlage["document_url"] == ris.file_url(11)
    assert vorlage["raw_text"] == zitat                      # Dokumenttext bleibt
    schnappschuss = json.loads(c.execute("SELECT items_json FROM agenda_snapshots").fetchone()[0])
    assert schnappschuss[0]["anlagen"][0]["url"] == ris.file_url(11)
    herkunft = c.execute("SELECT * FROM council_provenance").fetchone()
    assert herkunft["url"] == ris.template_url(7)
    # Der Fingerabdruck passt zur neuen Adresse: Der nächste Ingest findet die Zeile wieder.
    assert herkunft["key"] == _fingerabdruck(herkunft)

    # Zweiter Start: nichts mehr zu tun, und eine NEU eingetragene alte Adresse
    # bleibt liegen — die Marke steht (einmalig, nicht bei jedem Start).
    with c:
        c.execute("UPDATE council_templates SET document_url = ? WHERE kvonr = 7", (alt_datei,))
    store.close()
    store = CouncilStore(pfad)
    assert store._conn.execute(
        "SELECT document_url FROM council_templates WHERE kvonr = 7").fetchone()[0] == alt_datei
    store.close()


# ----------------------------------------------------------------- Alarm

class _Antwort:
    def __init__(self, url, status=200, text="<meta name=\"sessionnet\" content=\"V:050506\"/>",
                 history=(), headers=None):
        self.url, self.status_code, self.text = url, status, text
        self.history, self.headers = list(history), headers or {}
        self.ok = status < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(self.status_code)


def test_get_wiederholt_timeout_bis_zum_erfolg(monkeypatch):
    pausen = Mock()
    monkeypatch.setattr(ris.time, "sleep", pausen)
    erfolg = _Antwort(ris.page_url("si0040"))
    session = Mock()
    session.get.side_effect = [ris.requests.Timeout("kurzer Aussetzer"), erfolg]

    assert ris.get(session, "si0040") is erfolg
    assert session.get.call_count == 2
    pausen.assert_called_once_with(2)


def test_get_gibt_dauerhaften_timeout_nach_drei_versuchen_weiter(monkeypatch):
    pausen = Mock()
    monkeypatch.setattr(ris.time, "sleep", pausen)
    timeout = ris.requests.Timeout("weiterhin nicht erreichbar")
    session = Mock()
    session.get.side_effect = timeout

    with pytest.raises(ris.requests.Timeout) as fehler:
        ris.get(session, "si0040")

    assert fehler.value is timeout
    assert session.get.call_count == 3
    assert pausen.call_args_list == [call(2), call(5)]


def test_get_wiederholt_ris_error_nicht(monkeypatch):
    pausen = Mock()
    monkeypatch.setattr(ris.time, "sleep", pausen)
    hop = _Antwort(ris.page_url("si0040"), 301,
                   headers={"Location": "https://anderswo.example/ris/"})
    session = Mock()
    session.get.return_value = _Antwort(ris.page_url("si0040"), history=[hop])

    with pytest.raises(ris.RisError, match="dauerhaft umgezogen"):
        ris.get(session, "si0040")

    assert session.get.call_count == 1
    pausen.assert_not_called()


def test_ein_dauerhafter_umzug_ist_ein_fehler():
    """Genau das Bild vom 11/2026: 301 auf die Startseite eines anderen Hosts."""
    hop = _Antwort(ris.page_url("si0040"), 301, headers={"Location": "https://anderswo.example/ris/"})
    ziel = _Antwort("https://anderswo.example/ris/")
    with pytest.raises(ris.RisError, match="dauerhaft umgezogen"):
        ris.check(_Antwort(ris.page_url("si0040"), history=[hop]))
    with pytest.raises(ris.RisError):
        ris.check(_Antwort(ziel.url, history=[hop]))


def test_ein_fremder_host_und_eine_fremde_seite_sind_fehler():
    with pytest.raises(ris.RisError, match="fremden Host"):
        ris.check(_Antwort("https://www.oldenburg.de/wartung.html"))
    with pytest.raises(ris.RisError, match="keine SessionNet-Seite"):
        ris.check(_Antwort(ris.page_url("si0040"), text="<html>Wartungsarbeiten</html>"), html=True)


def test_die_interne_weiterleitung_von_sessionnet_bleibt_erlaubt():
    """Eine Sitzung ohne veröffentlichte Tagesordnung antwortet mit 302 — das
    ist der Normalfall und darf keinen Alarm auslösen."""
    hop = _Antwort(ris.page_url("to0040", __ksinr=1), 302,
                   headers={"Location": ris.session_url(1)})
    antwort = _Antwort(ris.session_url(1), history=[hop])
    assert ris.check(antwort, html=True) is antwort


def test_ein_leerer_kalender_ueber_monate_ist_ein_fehler(monkeypatch):
    """„Termine im Kalender: 0“ stand Lauf für Lauf im Admin-Panel. Vier
    Monate ohne einen Termin gibt es nicht — auch nicht in der Sommerpause."""
    scraper = CouncilScraper(delay=0)
    monkeypatch.setattr(scraper, "calendar_month", lambda y, m: ([], []))
    monkeypatch.setattr(scraper, "rss_scheduled", list)
    with pytest.raises(ris.RisError, match="Kalender"):
        scraper.upcoming_calendar(months_ahead=3)


def test_ein_voller_kalender_laeuft_durch(monkeypatch):
    scraper = CouncilScraper(delay=0)
    monkeypatch.setattr(scraper, "calendar_month", lambda y, m: ([4642], []))
    monkeypatch.setattr(scraper, "rss_scheduled", list)
    assert scraper.upcoming_calendar(months_ahead=1)[0] == [4642]


class _Sitzung:
    """Eine ``requests.Session``, die Seiten nach ihrem Namen ausgibt."""
    def __init__(self, seiten):
        self.seiten, self.headers = seiten, {}

    def get(self, url, params=None, timeout=None):
        seite = url.rsplit("/", 1)[-1].split(".")[0]
        antwort = self.seiten[seite]
        if isinstance(antwort, Exception):
            raise antwort
        return antwort


KALENDER = ('<meta name="sessionnet" content="V:050506"/><table>'
            + "".join(f'<tr><td class="smc_fct_day">{t}</td></tr>' for t in range(1, 31))
            + "</table>")


def test_die_tagesprobe_ist_still_wenn_alles_stimmt():
    aus = ris.probe(_Sitzung({
        "si0040": _Antwort(ris.page_url("si0040"), text=KALENDER),
        "rssfeed": _Antwort(ris.page_url("rssfeed"), text='<?xml version="1.0"?><rss><item/></rss>'),
    }))
    assert aus["befunde"] == []
    assert aus["kennzahlen"]["ris_kalender_tage"] == 30
    assert aus["kennzahlen"]["ris_rss_eintraege"] == 1


def test_die_tagesprobe_meldet_umzug_und_verlorenes_geruest():
    hop = _Antwort(ris.page_url("si0040"), 301, headers={"Location": "https://neu.example/"})
    umzug = ris.probe(_Sitzung({"si0040": _Antwort("https://neu.example/", history=[hop])}))
    assert len(umzug["befunde"]) == 1 and "antwortet nicht wie erwartet" in umzug["befunde"][0]

    leer = ris.probe(_Sitzung({
        "si0040": _Antwort(ris.page_url("si0040")),          # SessionNet, aber ohne Tageszeilen
        "rssfeed": _Antwort(ris.page_url("rssfeed"), text="<rss></rss>"),
    }))
    assert any("Gerüst verloren" in b for b in leer["befunde"])


def test_der_herzschlag_stellt_das_ratsinfo_an_die_spitze(monkeypatch):
    """Der Befund steht zuerst und gibt der Mail ihren Betreff — ohne das
    Ratsinfo kommt nichts Neues herein, egal was sonst läuft."""
    import sys

    sys.path.insert(0, str(WURZEL / "scripts"))
    import check_herzschlag as h
    from kern import alerts

    post: list[tuple[str, str]] = []
    monkeypatch.setattr(alerts, "notify_admin",
                        lambda text, betreff="", **_k: post.append((betreff, text)))
    monkeypatch.setattr(h, "ratsinfo", lambda: {
        "kennzahlen": {"ris_kalender_tage": 0},
        "befunde": ["<b>Das Ratsinformationssystem antwortet nicht wie erwartet</b>: 301"]})
    kennzahlen = h.main()
    assert post and post[0][0] == "Ratslotse – Ratsinfo liefert nicht"
    assert post[0][1].startswith("<b>Das Ratsinformationssystem antwortet nicht")
    assert kennzahlen["ris_kalender_tage"] == 0


def test_die_probe_laeuft_in_der_suite_nie_gegen_das_netz():
    import os
    import sys

    sys.path.insert(0, str(WURZEL / "scripts"))
    import check_herzschlag as h

    assert os.environ.get("RATSLOTSE_RIS_PROBE") == "0"
    assert h.ratsinfo() == {"kennzahlen": {}, "befunde": []}
