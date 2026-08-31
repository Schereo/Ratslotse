"""Das Statistik-Archiv — sichert es wirklich, und sichert es doppelt?

Die drei Zusagen, an denen dieser Job hängt (Modulkopf von
``scripts/archive_statistik.py``):

1. Eine **unveränderte** Datei wird nicht ein zweites Mal abgelegt — und zwar
   auch dann nicht, wenn die Gegenseite ihren ``ETag`` neu vergibt.
2. Eine **geänderte** Datei wird als neue Fassung erkannt, die alte bleibt.
3. Ein **404** beendet den Lauf nicht, sondern wird gezählt und gemeldet.

Getestet wird ohne Netz: ``main()`` nimmt Katalog und Übersichtsseiten als
Text entgegen, der Abruf wird ersetzt.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import archive_statistik as a  # noqa: E402

HEUTE = date(2026, 8, 17)
MORGEN = date(2026, 8, 18)

KATALOG = json.dumps({
    "dataset": [{
        "identifier": "abc-123",
        "title": "Steuereinnahmen",
        "modified": "2026-07-14",
        "distribution": [
            {"downloadURL": "https://opendata.oldenburg.de/sites/default/files/"
                            "1104_Steuereinnahmen_0.csv"},
            {"downloadURL": "https://opendata.oldenburg.de/sites/default/files/"
                            "1106_Steuerkraftmesszahlen-Schl%C3%BCsselzuweisung_0.csv"},
        ],
    }],
})

JAHRBUCH = """
<a href="/fileadmin/oldenburg/Benutzer/Dateien/40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf">1103</a>
<a href="/fileadmin/oldenburg/Benutzer/Dateien/40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/0803-2024.pdf">0803</a>
<a href="/fileadmin/oldenburg/Benutzer/Dateien/99_Woanders/Broschuere.pdf">nicht das Jahrbuch</a>
"""

KFA = """
<a href="https://www.statistik.niedersachsen.de/download/227086" class="download">
  KFA 2026 endg&uuml;ltig Ergebnis und Vergleichstabellen KSV (xlsx)</a>
<a href="https://www.statistik.niedersachsen.de/download/220813" class="download">
  Schl&uuml;sselzuweisungen f&uuml;r Gemeindeaufgaben 2025 - Einzelergebnisse (xlsx)</a>
"""


class Netz:
    """Ein Server, den der Test steuert: Inhalt je Adresse, ETag, 404."""

    def __init__(self, inhalte: dict[str, bytes]):
        self.inhalte = inhalte
        self.etags: dict[str, str] = {}
        self.abrufe: list[str] = []

    def antwort(self, url, etag=None, last_modified=None, session=None):
        self.abrufe.append(url)
        if url not in self.inhalte:
            raise a.AbrufFehler(f"{url}: HTTP 404")
        marke = self.etags.get(url, f'"{hash(self.inhalte[url]) & 0xffff:x}"')
        if etag and etag == marke:
            return a.Antwort(inhalt=None, etag=etag, last_modified=last_modified)
        return a.Antwort(inhalt=self.inhalte[url], etag=marke,
                         last_modified="Mon, 17 Aug 2026 05:00:00 GMT")


@pytest.fixture()
def netz(monkeypatch):
    n = Netz({
        "https://opendata.oldenburg.de/sites/default/files/1104_Steuereinnahmen_0.csv":
            b"Jahr;Gewerbesteuer\n2025;222117\n",
        "https://opendata.oldenburg.de/sites/default/files/"
        "1106_Steuerkraftmesszahlen-Schl%C3%BCsselzuweisung_0.csv":
            b"Jahr;Messzahl\n2025;300000\n",
        "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
        "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf":
            b"%PDF-1.4 Steuern 2023 bis 2025",
        "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
        "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/0803-2024.pdf":
            b"%PDF-1.4 Sozialhilfe",
        "https://www.statistik.niedersachsen.de/download/227086":
            b"PK\x03\x04 KFA 2026",
    })
    monkeypatch.setattr(a, "hole", n.antwort)
    monkeypatch.setattr(a, "PAUSE", 0)
    # Kein Mail-Versand und keine job_runs-Historie in Tests.
    monkeypatch.setattr(a, "_melden", lambda *args, **kwargs: None)
    return n


def lauf(ziel, netz_unbenutzt=None, heute=HEUTE, **rest):
    return a.main(archiv=ziel, heute=heute, still=True, katalog_text=KATALOG,
                  jahrbuch_html=JAHRBUCH, kfa_html=KFA, **rest)


# --- Zusage 1: nichts wird doppelt abgelegt ---------------------------------

def test_zweiter_lauf_legt_nichts_doppelt_ab(tmp_path, netz):
    ziel = tmp_path / "archiv"
    erst = lauf(ziel)
    assert erst["Neue Fassungen"] == 6      # 5 Dateien + der Katalog selbst
    assert erst["Fehler"] == 0

    dateien_vorher = sorted(p.relative_to(ziel) for p in ziel.rglob("*") if p.is_file())

    zweit = lauf(ziel)
    assert zweit["Neue Fassungen"] == 0
    dateien_nachher = sorted(p.relative_to(ziel) for p in ziel.rglob("*") if p.is_file())
    assert dateien_vorher == dateien_nachher


def test_zweiter_lauf_am_naechsten_tag_legt_nichts_doppelt_ab(tmp_path, netz):
    """Der Dateiname trägt das Datum — ohne Hash-Prüfung läge morgen alles
    noch einmal da."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    n = sum(1 for p in ziel.rglob("*") if p.is_file())
    assert lauf(ziel, heute=MORGEN)["Neue Fassungen"] == 0
    assert sum(1 for p in ziel.rglob("*") if p.is_file()) == n


def test_neuer_etag_ohne_neuen_inhalt_legt_nichts_ab(tmp_path, netz):
    """Ein Server, der seinen ETag neu vergibt (Neuinstallation, Cache-Umzug),
    liefert die Datei erneut aus — dieselben Bytes. Der Hash entscheidet."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    url = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf")
    netz.etags[url] = '"ganz-neu"'

    result = lauf(ziel, heute=MORGEN)
    assert result["Neue Fassungen"] == 0
    ordner = ziel / "jahrbuch" / "1103-2025-AZ.pdf"
    assert len(list(ordner.iterdir())) == 1


def test_unveraenderte_datei_wird_gar_nicht_erst_geladen(tmp_path, netz):
    """Der bedingte Abruf: Beim zweiten Lauf antwortet der Server 304, es
    fließen null Bytes."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    zweit = lauf(ziel)
    assert zweit["Geladen (MB)"] == 0.0
    assert zweit["Unverändert"] + zweit["Ohne Abruf übersprungen"] >= 5


def test_open_data_wird_bei_unveraendertem_modified_gar_nicht_angeklopft(tmp_path, netz):
    """Die billige Vorprüfung: gleiches ``modified`` + Datei liegt da = kein
    HTTP-Abruf. Das spart 186 Anfragen am Tag."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    netz.abrufe.clear()
    zweit = lauf(ziel)
    assert zweit["Ohne Abruf übersprungen"] >= 2
    assert not [u for u in netz.abrufe if "opendata.oldenburg.de/sites" in u]


def test_lsn_mappe_wird_nur_einmal_geholt(tmp_path, netz):
    """Der LSN-Server schickt weder ETag noch Last-Modified — bedingt abrufen
    geht dort nicht. Dafür ist eine Download-Nummer unveränderlich: Was einmal
    im Archiv liegt, muss nie wieder geladen werden."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    netz.abrufe.clear()
    zweit = lauf(ziel, heute=MORGEN)
    assert not [u for u in netz.abrufe if "statistik.niedersachsen.de" in u]
    assert zweit["Geladen (MB)"] == 0.0


def test_neue_lsn_nummer_wird_geholt(tmp_path, netz):
    """Eine neue Ausgabe erscheint unter einer neuen Nummer — die kennt das
    Manifest nicht und wird geladen."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    neu = "https://www.statistik.niedersachsen.de/download/239001"
    netz.inhalte[neu] = b"PK\x03\x04 KFA 2027"
    kfa_neu = KFA + (f'<a href="{neu}" class="download">KFA 2027 endg&uuml;ltig '
                     f'Ergebnis und Vergleichstabellen KSV (xlsx)</a>')
    result = a.main(archiv=ziel, heute=MORGEN, still=True, katalog_text=KATALOG,
                      jahrbuch_html=JAHRBUCH, kfa_html=kfa_neu)
    assert result["Neue Fassungen"] == 1
    assert (ziel / "kfa" /
            "kfa-2027-endgültig-ergebnis-und-vergleichstabellen-ksv-239001.xlsx").is_dir()


def test_ohne_vorpruefung_klopft_ueberall_an(tmp_path, netz):
    """Der Ausweg, falls sich eine der beiden Annahmen als falsch erweist."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    netz.abrufe.clear()
    result = lauf(ziel, heute=MORGEN, ohne_vorpruefung=True)
    assert result["Ohne Abruf übersprungen"] == 0
    assert [u for u in netz.abrufe if "statistik.niedersachsen.de" in u]
    assert result["Neue Fassungen"] == 0     # geholt, aber nichts doppelt


def test_geaendertes_modified_fuehrt_zum_abruf(tmp_path, netz):
    ziel = tmp_path / "archiv"
    lauf(ziel)
    katalog = json.loads(KATALOG)
    katalog["dataset"][0]["modified"] = "2026-08-18"
    netz.abrufe.clear()

    a.main(archiv=ziel, heute=MORGEN, still=True,
           katalog_text=json.dumps(katalog), jahrbuch_html=JAHRBUCH, kfa_html=KFA)
    assert [u for u in netz.abrufe if "1104_Steuereinnahmen" in u]


# --- Zusage 2: eine neue Fassung ist eine neue Fassung ----------------------

def test_geaenderter_inhalt_wird_neue_fassung_und_die_alte_bleibt(tmp_path, netz):
    ziel = tmp_path / "archiv"
    lauf(ziel)
    url = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf")
    netz.inhalte[url] = b"%PDF-1.4 Steuern 2024 bis 2026, neue Ausgabe"
    netz.etags[url] = '"zweite-ausgabe"'

    result = lauf(ziel, heute=MORGEN)
    assert result["Neue Fassungen"] == 1

    ordner = ziel / "jahrbuch" / "1103-2025-AZ.pdf"
    fassungen = sorted(p.name for p in ordner.iterdir())
    assert len(fassungen) == 2
    assert fassungen[0].startswith("2026-08-17_")
    assert fassungen[1].startswith("2026-08-18_")
    # Die ältere Fassung ist unangetastet — das ist der ganze Zweck.
    alt = ordner / fassungen[0]
    assert alt.read_bytes() == b"%PDF-1.4 Steuern 2023 bis 2025"


def test_neue_ausgabe_unter_neuem_namen_wird_gefunden(tmp_path, netz):
    """Der Fall, für den es den Job gibt: Die Stadt legt 1103 als Ausgabe 2026
    an, die 2025er Adresse wird 404. Die feste Adressliste hätte hier versagt —
    die Übersichtsseite liefert den neuen Namen."""
    ziel = tmp_path / "archiv"
    lauf(ziel)

    alt = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf")
    neu = alt.replace("1103-2025-AZ", "1103-2026-AZ")
    del netz.inhalte[alt]                       # weg vom Server
    netz.inhalte[neu] = b"%PDF-1.4 Steuern 2024 bis 2026"
    jahrbuch_neu = JAHRBUCH.replace("1103-2025-AZ", "1103-2026-AZ")

    result = a.main(archiv=ziel, heute=MORGEN, still=True, katalog_text=KATALOG,
                      jahrbuch_html=jahrbuch_neu, kfa_html=KFA)
    assert result["Neue Fassungen"] == 1
    assert (ziel / "jahrbuch" / "1103-2026-AZ.pdf").is_dir()
    # Und der Jahrgang 2025, den es nirgends mehr gibt, liegt weiter da.
    assert list((ziel / "jahrbuch" / "1103-2025-AZ.pdf").iterdir())


# --- Zusage 3: ein 404 beendet den Lauf nicht -------------------------------

def test_404_wird_gemeldet_und_der_lauf_laeuft_weiter(tmp_path, netz):
    ziel = tmp_path / "archiv"
    weg = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/0803-2024.pdf")
    del netz.inhalte[weg]

    result = lauf(ziel)
    assert result["Fehler"] == 1
    assert any("HTTP 404" in b and "0803-2024" in b for b in result["befund"])
    # Alles andere ist trotzdem gesichert.
    assert result["Neue Fassungen"] == 5
    assert (ziel / "jahrbuch" / "1103-2025-AZ.pdf").is_dir()
    assert (ziel / "kfa").is_dir()


def test_404_verliert_den_alten_stand_nicht(tmp_path, netz):
    """Verschwindet eine Datei vom Server, bleibt ihre gesicherte Fassung —
    und das Manifest sagt, seit wann sie fehlt."""
    ziel = tmp_path / "archiv"
    lauf(ziel)
    weg = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/0803-2024.pdf")
    del netz.inhalte[weg]

    lauf(ziel, heute=MORGEN)
    assert list((ziel / "jahrbuch" / "0803-2024.pdf").iterdir())
    manifest = a.manifest_lesen(ziel)
    assert manifest[weg]["fehler_am"] == "2026-08-18"
    assert manifest[weg]["hash"]           # der Stand von gestern steht noch da


def test_uebersichtsseite_ohne_tabellen_ist_ein_befund(tmp_path, netz):
    """Kein Absturz, aber auch kein Schweigen: Wenn die Seite plötzlich keine
    PDFs mehr trägt, hat sich ihr Aufbau geändert."""
    result = a.main(archiv=tmp_path / "archiv", heute=HEUTE, still=True,
                      katalog_text=KATALOG, jahrbuch_html="<html>nichts</html>",
                      kfa_html=KFA)
    assert any("keine Tabellen-PDFs" in b for b in result["befund"])


def test_kaputter_katalog_beendet_den_lauf_nicht(tmp_path, netz):
    result = a.main(archiv=tmp_path / "archiv", heute=HEUTE, still=True,
                      katalog_text="{kein json", jahrbuch_html=JAHRBUCH, kfa_html=KFA)
    assert any("kein gültiges JSON" in b for b in result["befund"])
    assert (tmp_path / "archiv" / "jahrbuch").is_dir()   # der Rest lief


def test_unveraenderter_katalog_faellt_auf_die_gesicherte_fassung_zurueck(tmp_path, netz):
    """Der Katalog antwortet ab dem zweiten Tag ``304``. Ohne Rückfall auf die
    gesicherte Fassung fiele die gesamte Open-Data-Prüfung an diesem Tag aus —
    still, und genau bei der Quelle, die sich am häufigsten ändert."""
    ziel = tmp_path / "archiv"
    netz.inhalte[a.KATALOG_URL] = KATALOG.encode()
    a.main(archiv=ziel, heute=HEUTE, still=True, jahrbuch_html=JAHRBUCH, kfa_html=KFA)
    assert (ziel / "opendata" / "data.json").is_dir()

    netz.abrufe.clear()
    # Zweiter Lauf, ohne katalog_text: Der Server antwortet 304.
    result = a.main(archiv=ziel, heute=MORGEN, still=True,
                      jahrbuch_html=JAHRBUCH, kfa_html=KFA)
    # Die beiden Portal-Dateien sind trotzdem geprüft worden (hier über die
    # modified-Vorprüfung, also ohne Abruf) — nicht stillschweigend ausgelassen.
    manifest = a.manifest_lesen(ziel)
    portal = [u for u in manifest if "opendata.oldenburg.de/sites" in u]
    assert len(portal) == 2
    assert all(manifest[u]["zuletzt_gesehen"] == "2026-08-17" for u in portal)
    assert result["Ohne Abruf übersprungen"] >= 2
    assert result["Fehler"] == 0


def test_kaputtes_manifest_beendet_den_lauf_nicht(tmp_path, netz):
    ziel = tmp_path / "archiv"
    lauf(ziel)
    (ziel / "manifest.json").write_text("{ kaputt")
    result = lauf(ziel, heute=MORGEN)
    assert result["Neue Fassungen"] == 0     # der Hash rettet vor Dubletten
    assert a.manifest_lesen(ziel)              # und es wird neu geschrieben


# --- Auswahl und Namen ------------------------------------------------------

def test_jahrbuch_links_nimmt_nur_das_statistik_verzeichnis():
    links = a.jahrbuch_links(JAHRBUCH)
    assert len(links) == 2
    assert all("402_Geo_und_Daten/Statistik" in u for u in links)


def test_kfa_links_nimmt_die_vergleichstabellen_und_nicht_die_einzelergebnisse():
    mappen = a.kfa_links(KFA)
    assert [u for u, _ in mappen] == ["https://www.statistik.niedersachsen.de/download/227086"]


def test_kfa_dateiname_ist_sprechend_und_stabil():
    name = a.kfa_dateiname("https://www.statistik.niedersachsen.de/download/227086",
                           "KFA 2026 endgültig Ergebnis und Vergleichstabellen KSV (xlsx)")
    assert name == "kfa-2026-endgültig-ergebnis-und-vergleichstabellen-ksv-227086.xlsx"


def test_dateiname_loest_prozentkodierung_auf_und_kann_nicht_aus_dem_ordner():
    assert a.dateiname("https://x/1106_Steuerkraft-Schl%C3%BCsselzuweisung_0.csv") \
        == "1106_Steuerkraft-Schlüsselzuweisung_0.csv"
    boese = a.dateiname("https://x/sites/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    assert "/" not in boese and ".." not in boese


def test_endung_erkennt_nur_echte_endungen():
    assert a.endung("1103-2025-AZ.pdf") == ".pdf"
    assert a.endung("daten.XLSX") == ".xlsx"
    assert a.endung("ohne-punkt") == ""
    assert a.endung("1101_Haushaltsplan_der_Stadt_Oldenburg_2025") == ""


def test_katalog_dateien_zaehlt_jede_adresse_einmal():
    eintraege = a.katalog_dateien(json.loads(KATALOG))
    assert len(eintraege) == 2
    assert {m for _, m, _ in eintraege} == {"2026-07-14"}


def test_trockenlauf_schreibt_nichts(tmp_path, netz):
    ziel = tmp_path / "archiv"
    result = lauf(ziel, trocken=True)
    assert result["Neue Fassungen"] == 0
    assert not ziel.exists() or not list(ziel.rglob("*"))


def test_der_job_steht_in_der_cron_registry():
    """Wer die crontab ändert, zieht kern/jobs.py nach — sonst schlägt die
    Überfällig-Ampel im Admin-Panel falsch an."""
    from kern.jobs import BY_KEY

    assert a.JOB in BY_KEY
    assert BY_KEY[a.JOB]["max_age_h"] >= 24
