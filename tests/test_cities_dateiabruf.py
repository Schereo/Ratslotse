"""Was ein Dokument-Abruf zurückgeben darf — und was nie.

Beide Regeln hier stammen aus derselben Wolfsburger Ernte (10.09.2026) und
haben dieselbe Form: Der Server antwortet mit HTTP 200, und trotzdem ist
nichts da. Ein Fehlercode wäre leicht zu behandeln; ein freundliches „hier,
bitte" mit dem falschen Inhalt ist es nicht.
"""
from __future__ import annotations

import requests

from council.cities.oparl import OParlClient
from council.cities.store import CitiesStore


class _Antwort:
    def __init__(self, inhalt: bytes, typ: str, status: int = 200):
        self.content = inhalt
        self.headers = {"content-type": typ}
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 500:
            raise requests.HTTPError(response=self)


class _Sitzung:
    def __init__(self, antwort):
        self.antwort = antwort
        self.headers: dict[str, str] = {}
        self.abrufe: list[str] = []

    def get(self, url, **_):
        self.abrufe.append(url)
        return self.antwort


def _client(tmp_path, antwort) -> OParlClient:
    store = CitiesStore(tmp_path / "raw.sqlite")
    return OParlClient(store, "teststadt", tmp_path / "files",
                       session=_Sitzung(antwort))


def test_eine_webseite_ist_nie_das_dokument(tmp_path):
    """ALLRIS liefert für die Anlage einer nichtöffentlichen Vorlage HTML.

    Kein Fehler, kein 403 — HTTP 200 und die Seite „Keine Information
    verfügbar". Gemessen an Wolfsburg: 444 von 1.798 Dateien. Ungeprüft
    landen sie als `.pdf` im Speicher, und die Textstufe meldet bei jedem Lauf
    „invalid pdf header" — Fehler, die wie ein Parserproblem aussehen und in
    Wahrheit eine Zugangsbeschränkung sind.
    """
    client = _client(tmp_path, _Antwort(
        b"\n<!DOCTYPE html>\n<html><body>Keine Information verf\xc3\xbcgbar</body></html>",
        "text/html; charset=utf-8"))
    assert client.get_file("https://x.example.org/anlage.pdf") is None
    client.raw.close()


def test_auch_ohne_ehrlichen_kopf_wird_html_erkannt(tmp_path):
    """Manche Server behaupten ``application/pdf`` und schicken eine Seite."""
    client = _client(tmp_path, _Antwort(
        b"<html><head><title>Fehler</title></head></html>", "application/pdf"))
    assert client.get_file("https://x.example.org/anlage.pdf") is None
    client.raw.close()


def test_ein_echtes_pdf_kommt_durch(tmp_path):
    client = _client(tmp_path, _Antwort(b"%PDF-1.7\n...", "application/pdf"))
    ergebnis = client.get_file("https://x.example.org/anlage.pdf")
    assert ergebnis is not None
    daten, mime = ergebnis
    assert daten.startswith(b"%PDF") and mime == "application/pdf"
    client.raw.close()


def test_eine_kaputte_adresse_kostet_keinen_abruf(tmp_path):
    """Ein lokaler Windows-Pfad statt eines Links — einmal in Wolfsburg.

    ``requests`` wirft dafür ``InvalidSchema``; ungefangen nahm das den
    ganzen Dateiabruf der Stadt mit. Ein anderes Schema wird nie gut, ein
    zweiter Versuch also sinnlos: gar nicht erst anfragen.
    """
    client = _client(tmp_path, _Antwort(b"%PDF-1.7", "application/pdf"))
    assert client.get_file("file:///C:/Users/vorname-n/Downloads/x.pdf") is None
    assert client.session.abrufe == [], "es darf kein Abruf stattgefunden haben"
    client.raw.close()


_ALTCHA = (b'<!DOCTYPE html>\n<html lang="de"><head><title>Zugriff pruefen</title>'
           b'<script async defer src="/public/_gate/assets/altcha.js" type="module"></script>'
           b"</head><body>Zum Schutz vor automatisierten Zugriffen</body></html>")


def test_eine_zugangspruefung_beendet_die_dateiabrufe_der_stadt(tmp_path):
    """Braunschweig, 09.11.2026: Jede Dokument-Adresse liefert die ALTCHA-Seite
    „Zugriff prüfen". Der Lauf fragte 240-mal nach. Umgangen wird sie nicht —
    aber nach der ersten hört der Lauf auf zu klopfen und sagt, warum."""
    sitzung = _Sitzung(_Antwort(_ALTCHA, "text/html; charset=UTF-8"))
    client = OParlClient(CitiesStore(tmp_path / "raw.sqlite"), "braunschweig",
                         tmp_path / "files", session=sitzung)
    assert client.get_file("https://bs.example.org/public/doc?DOLFDNR=1") is None
    assert client.files_gated
    assert client.get_file("https://bs.example.org/public/doc?DOLFDNR=2") is None
    assert len(sitzung.abrufe) == 1, "nach der Zugangsprüfung kein weiterer Abruf"
    client.raw.close()


def test_eine_gewoehnliche_webseite_sperrt_nichts(tmp_path):
    """„Keine Information verfügbar" (nichtöffentlich) ist keine Zugangsprüfung —
    die nächste Datei derselben Stadt kann ein PDF sein."""
    client = _client(tmp_path, _Antwort(
        b"<!DOCTYPE html><html><body>Keine Information verf\xc3\xbcgbar</body></html>",
        "text/html"))
    assert client.get_file("https://x.example.org/a.pdf") is None
    assert not client.files_gated
    client.raw.close()


def test_die_ernte_merkt_die_zugangspruefung(tmp_path):
    from council.cities import pipeline

    sitzung = _Sitzung(_Antwort(_ALTCHA, "text/html"))
    store = CitiesStore(tmp_path / "raw.sqlite")
    client = OParlClient(store, "braunschweig", tmp_path / "files", session=sitzung)
    offen = [{"id": f"f{i}", "access_url": f"https://bs.example.org/doc?{i}"} for i in range(5)]
    zahlen: dict = {}
    pipeline._hole(client, store, "braunschweig", offen, zahlen, "Dateien")
    assert zahlen["files_gated"] == 1 and zahlen["files_failed"] == 1
    assert len(sitzung.abrufe) == 1
    store.close()


class _KeineVerbindung(_Sitzung):
    def get(self, url, **_):
        self.abrufe.append(url)
        raise requests.ConnectTimeout("keine Verbindung")


def test_ein_server_ohne_verbindung_wird_nicht_weiter_gefragt(tmp_path, monkeypatch):
    """Potsdam, 09.11.2026: Nach ein paar Minuten nahm der Server keine
    Verbindung mehr an, und jede Datei kostete zwei Versuche à 120 s, während
    ein Deploy wartete. Nach drei Verbindungsfehlern in Folge ist Schluss."""
    from council.cities import oparl, pipeline

    monkeypatch.setattr(oparl.time, "sleep", lambda s: None)
    sitzung = _KeineVerbindung(None)
    store = CitiesStore(tmp_path / "raw.sqlite")
    client = OParlClient(store, "potsdam", tmp_path / "files", session=sitzung)
    offen = [{"id": f"f{i}", "access_url": f"https://pd.example.org/doc?{i}"} for i in range(10)]
    zahlen: dict = {}
    pipeline._hole(client, store, "potsdam", offen, zahlen, "Dateien")
    assert client.host_unreachable and zahlen["host_unreachable"] == 1
    assert len(sitzung.abrufe) == oparl.UNREACHABLE_AFTER
    store.close()


def test_der_verbindungsaufbau_hat_eine_kurze_frist():
    from council.cities import oparl
    assert oparl.TIMEOUT_FILE[0] <= 15 and oparl.TIMEOUT_JSON[0] <= 15
    assert oparl.TIMEOUT_FILE[1] >= 60, "das Lesen großer Dateien darf dauern"


def test_die_ernte_tritt_fuer_einen_deploy_zur_seite(tmp_path):
    """Der Deploy legt `data/.deploy-wartet`; die Ernte hört an der nächsten
    Datei auf, statt die Stadt zu Ende zu holen."""
    from council.cities import pipeline
    from kern.stopp import WARTET_NAME, Stopp

    (tmp_path / WARTET_NAME).touch()
    sitzung = _Sitzung(_Antwort(b"%PDF-1.7", "application/pdf"))
    store = CitiesStore(tmp_path / "raw.sqlite")
    client = OParlClient(store, "potsdam", tmp_path / "files", session=sitzung)
    offen = [{"id": f"f{i}", "access_url": f"https://pd.example.org/doc?{i}"} for i in range(3)]
    zahlen: dict = {}
    pipeline._hole(client, store, "potsdam", offen, zahlen, "Dateien", stopp=Stopp(tmp_path))
    assert "Deploy" in zahlen["abgebrochen"] and sitzung.abrufe == []
    store.close()


def test_die_kostengrenze_haelt_die_ernte_nicht_auf(tmp_path):
    from council.cities import pipeline
    from kern.stopp import Stopp

    stopp = Stopp(tmp_path, max_kosten=1.0)
    stopp.ausgeben(5.0)
    assert pipeline._soll_aufhoeren(stopp) is None
