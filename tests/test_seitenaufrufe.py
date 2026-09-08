"""Die anonyme Seitenzählung — was sie zählt und was sie nicht speichert.

Der Zähler ist der einzige offene Schreib-Endpunkt, den jeder Browser bei
jedem Seitenwechsel trifft. Zwei Dinge müssen deshalb festgehalten sein: dass
nichts Persönliches hineinkommt (die Felder), und dass die Positivliste mit
dem Seitenbaum des Frontends mitwächst (sonst verschwinden neue Seiten still
in der Sammelzeile und sähen aus wie „wird nicht benutzt").
"""
from __future__ import annotations

from pathlib import Path

from kern import seitenaufrufe as sa
from kern.store import Store

WURZEL = Path(__file__).resolve().parents[1]
APP = WURZEL / "web" / "frontend" / "app"


# ---------------------------------------------------------------- Normalisieren

def test_query_kommt_nie_mit():
    """Die Query trägt hier alles Persönliche — Beschluss-id, Suchbegriff, Token."""
    assert sa.normalisieren("/council/decision?id=8525") == "/council/decision"
    assert sa.normalisieren("/g?t=AoyVwc") == "/g"
    assert sa.normalisieren("/council?q=wohnungsnot+kreyenbrueck") == "/council"
    assert sa.normalisieren("/fragen#antwort-3") == "/fragen"


def test_unbekanntes_wird_zusammengefasst_nicht_repariert():
    """Ein fremder Browser darf die Tabelle weder aufblähen noch beschriften."""
    for roh in ("/etwas/erfundenes", "../../etc/passwd", "/-suchbegriff-als-pfad",
                "keine-fuehrende-schraege"):
        assert sa.normalisieren(roh) == sa.ANDERE, roh
    # Leer und None sind kein Angriff, sondern ein Client ohne Pfad — die
    # Startseite ist die richtige Annahme, nicht die Sammelzeile.
    assert sa.normalisieren("") == "/" and sa.normalisieren(None) == "/"


def test_dynamische_segmente_werden_zusammengefasst():
    assert sa.normalisieren("/kommunalwahl/liste/spd") == "/kommunalwahl/liste/{slug}"
    assert sa.normalisieren("/kommunalwahl/thema/verkehr") == "/kommunalwahl/thema/{slug}"


def test_angehaengter_schraegstrich_trifft_dieselbe_zeile():
    """Der statische Export der App hängt einen an — sonst zählte er doppelt."""
    assert sa.normalisieren("/dashboard/") == sa.normalisieren("/dashboard") == "/dashboard"
    assert sa.normalisieren("/") == "/"


def test_die_vier_ratsbereiche_bleiben_unterscheidbar():
    """Suche, Sitzungen, Themen und Analyse sind eine Seite mit ?tab=.

    Ohne diese Ausnahme fielen die vier meistbenutzten Bereiche in eine Zeile
    zusammen — und die Frage „welche Bereiche benutzen die Leute?" wäre gerade
    mit dem Werkzeug unbeantwortbar, das für sie gebaut wurde.
    """
    for tab in sa.COUNCIL_TABS:
        assert sa.normalisieren(f"/council?tab={tab}") == f"/council?tab={tab}"
    # Und trotzdem: ein Suchbegriff daneben kommt NICHT mit.
    assert sa.normalisieren("/council?q=wohnungsnot&tab=sessions") == "/council?tab=sessions"
    assert sa.normalisieren("/council?q=wohnungsnot") == "/council"
    assert sa.normalisieren("/council?tab=erfunden") == "/council"


def test_fremde_clients_werden_zu_web():
    assert sa.client_normalisieren("IOS") == "ios"
    assert sa.client_normalisieren("<script>") == "web"
    assert sa.client_normalisieren(None) == "web"


# ------------------------------------------------------------------ Der Wächter

def _routen_des_frontends() -> set[str]:
    """Jede Seite, die Next tatsächlich ausliefert, als Pfad."""
    routen = set()
    for datei in APP.rglob("page.tsx"):
        teile = []
        for teil in datei.relative_to(APP).parent.parts:
            if teil.startswith("(") and teil.endswith(")"):
                continue  # Gruppierung, taucht in der Adresse nicht auf
            teile.append("{slug}" if teil.startswith("[") else teil)
        routen.add("/" + "/".join(teile) if teile else "/")
    return routen


def test_positivliste_deckt_den_seitenbaum_ab():
    """Eine neue Seite gehört in ``ROUTEN`` — sonst zählt sie als „/andere".

    Der Fehler wäre still und irreführend: Die neue Seite stünde in der
    Statistik auf null, und das läse sich wie „niemand geht dort hin".
    """
    fehlend = sorted(r for r in _routen_des_frontends() if sa.normalisieren(r) == sa.ANDERE)
    assert not fehlend, (
        "Diese Seiten des Frontends fehlen in kern/seitenaufrufe.py::ROUTEN "
        f"und würden als {sa.ANDERE} gezählt: {fehlend}"
    )


def test_keine_toten_eintraege_in_der_liste():
    """Und die Gegenrichtung: ein Muster, das keine Seite mehr hat, fliegt raus."""
    echt = _routen_des_frontends()
    # Die Sammelzeile hat naturgemäß keine Seite.
    # Die ?tab=-Varianten haben keine eigene Seite (sie sind /council) und
    # werden über COUNCIL_TABS gehalten, nicht über den Seitenbaum.
    tot = sorted(r for r in sa.ROUTEN
                 if r != sa.ANDERE and "?" not in r and r not in echt)
    assert not tot, f"Stehen in ROUTEN, aber es gibt keine solche Seite mehr: {tot}"


# ----------------------------------------------------------------- Was gespeichert wird

def test_gespeichert_wird_nur_was_erlaubt_ist(tmp_path):
    """Die Tabelle trägt vier Merkmale und zwei Zähler — mehr gibt es nicht."""
    store = Store(tmp_path / "r.sqlite")
    spalten = {r[1] for r in store._conn.execute("PRAGMA table_info(page_views)")}
    assert spalten == {"day", "route", "client", "logged_in", "count", "sessions"}
    verboten = {"owner_id", "user_id", "ip", "referrer", "user_agent", "query", "session_id"}
    assert not (spalten & verboten)
    store.close()


def test_zaehlen_summiert_und_trennt_angemeldet(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    store.merke_seitenaufruf("/", "web", angemeldet=False, erster=True)
    store.merke_seitenaufruf("/", "web", angemeldet=False)
    store.merke_seitenaufruf("/", "web", angemeldet=True, erster=True)

    daten = store.seitenaufrufe()

    assert daten["total"] == 3
    assert daten["sessions"] == 2, "Nur die beiden ersten Aufrufe je Tab"
    assert daten["anonymous"] == 2
    assert daten["pages"][0] == {"route": "/", "n": 3, "sessions": 2}
    store.close()


def test_zaehlen_bricht_nie_einen_request(tmp_path):
    """Wie `record_activity`: ein Zähler, der wirft, ist schlimmer als keiner."""
    store = Store(tmp_path / "r.sqlite")
    store._conn.execute("DROP TABLE page_views")
    store.merke_seitenaufruf("/", "web")  # darf nicht werfen
    store.close()


def test_seitenaufrufe_ohne_daten_ist_kein_fehler(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    daten = store.seitenaufrufe()
    assert daten["total"] == 0 and daten["series"] == [] and daten["pages"] == []
    store.close()


def test_alte_tage_fallen_aus_dem_fenster(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO page_views (day, route, client, logged_in, count, sessions)"
            " VALUES ('2020-01-01', '/', 'web', 0, 99, 9)")
    store.merke_seitenaufruf("/", "web")
    assert store.seitenaufrufe(30)["total"] == 1
    store.close()


def test_modul_nennt_die_ausgelassenen_felder():
    """Die Begründung steht im Modul, nicht nur im Pull Request.

    Wer ein Feld ergänzt, soll den Absatz lesen müssen, der erklärt, warum
    Query, Referrer und User-Agent bewusst fehlen — dasselbe Muster wie bei
    ``kern/fehler.py``.
    """
    quelle = (WURZEL / "kern" / "seitenaufrufe.py").read_text(encoding="utf-8")
    for wort in ("Query", "Referrer", "User-Agent", "Kennung"):
        assert wort in quelle, wort
