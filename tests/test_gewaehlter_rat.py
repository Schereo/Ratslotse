"""Der gewählte Rat: 52 Personen aus dem Wahlergebnis, bevor sie in den
Protokollen stehen (``web/backend/app/election/elected.py``).

Was hier festgehalten wird:

- **Dieselben Sitze wie der Wahlabend.** Die Liste rechnet nicht selbst,
  sondern liest ``archive.night(...)["mandates"]``. Eine Abweichung von der
  Sitzverteilung der Meta-Datei hieße, dass eine Person eine Seite bekommt,
  die keinen Sitz hat.
- **Derselbe Slug wie die Personen-Seite.** Sonst führte der Link aus der
  Liste für die 27 Wiedergewählten auf ein leeres Profil.
- **Mandatswechsel nur mit Namen vom Stimmzettel.** Ein Tippfehler in der
  Nachfolge bricht das Laden ab, statt eine erfundene Person anzulegen.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive, elected, elections  # noqa: E402

WAHL = "ratswahl-2026"


def _slug(name: str) -> str:
    # Wie CouncilStore._person_slug im Kern: Titel weg, klein, Bindestriche.
    import re
    import unicodedata
    n = re.sub(r"^(Dr\.|Prof\.)\s+", "", name)
    n = n.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")


def _history(found: dict[str, dict] | None = None):
    """Ersatz für ``CouncilStore.council_history``: Nachname → Treffer."""
    found = found or {}

    def history(people, before):
        assert before == "2026-11-01"
        return [found.get(last, {"slug": None, "terms": []}) for _first, last in people]
    return history


@pytest.fixture(autouse=True)
def _frisch():
    archive.reset()
    elected._load.cache_clear()
    yield
    archive.reset()
    elected._load.cache_clear()


def test_zweiundfuenfzig_sitze_wie_in_der_meta_datei():
    rat = elected.council(_slug, _history(), {}, WAHL)
    assert rat is not None
    assert rat["seats"] == 52 and len(rat["members"]) == 52
    meta = json.loads((WURZEL / "kommunalwahl/referenz-2026/ratswahl-2026.json").read_text(encoding="utf-8"))
    erwartet = Counter(m["party"] for m in meta["sitzverteilung"])
    assert Counter(m["list_short"] for m in rat["members"]) == erwartet


def test_kopf_und_steckbrief():
    rat = elected.council(_slug, _history(), {}, WAHL)
    assert rat is not None
    assert rat["term_start"] == "2026-11-01"
    assert rat["status"] in ("vorlaeufig", "amtlich")
    menge = next(m for m in rat["members"] if m["name"] == "Susanne Menge")
    assert (menge["list"], menge["area"], menge["position"]) == ("gruene", 1, 1)
    assert menge["occupation"] and menge["born"]
    # Jeder Sitz hat Beruf oder Jahrgang aus dem Register — sonst fand der
    # Abgleich den Namen nicht.
    assert all(m["born"] for m in rat["members"])


def test_titel_steht_vor_dem_vornamen():
    assert elected.display_name("Dr. Giesers, Benjamin") == "Dr. Benjamin Giesers"
    assert elected.display_name("Menge, Susanne") == "Susanne Menge"
    assert elected.display_name("Paul, Andreas Michael") == "Andreas Michael Paul"


def test_bekannte_profile_werden_markiert():
    known = {"susanne-menge": "council", "lena-nzume": "advisory"}
    rat = elected.council(_slug, _history({
        "Menge": {"slug": "susanne-menge", "terms": [2011, 2021]},
        "Bernhardt": {"slug": None, "terms": [2016]},
    }), known, WAHL)
    assert rat is not None
    nach_slug = {m["slug"]: m for m in rat["members"]}
    menge = nach_slug["susanne-menge"]
    assert menge["has_profile"] and menge["council_status"] == "current"
    assert menge["council_terms"] == [2011, 2021]
    # Beraten ist kein Mandat: Profil ja, im Rat nein.
    assert nach_slug["lena-nzume"]["has_profile"] and nach_slug["lena-nzume"]["council_status"] == "new"
    assert not nach_slug["pia-schlieker"]["has_profile"]
    # Nur in einer früheren Wahlperiode: „former", nicht „current".
    assert nach_slug["kurt-bernhardt"]["council_status"] == "former"


def test_der_treffer_bestimmt_den_slug():
    """Der Stimmzettel sagt „Drügemöller, Ruth", das Profil heißt
    „ruth-regina-druegemoeller" — der Link muss dorthin führen."""
    rat = elected.council(_slug, _history({
        "Drügemöller": {"slug": "ruth-regina-druegemoeller", "terms": [2021]},
    }), {"ruth-regina-druegemoeller": "council"}, WAHL)
    assert rat is not None
    ruth = next(m for m in rat["members"] if m["name"] == "Ruth Drügemöller")
    assert ruth["slug"] == "ruth-regina-druegemoeller" and ruth["has_profile"]
    assert ruth["council_status"] == "current"


def test_titel_faellt_beim_nachnamen_weg():
    assert elected.split_name("Dr. Giesers, Benjamin") == ("Benjamin", "Giesers")
    assert elected.split_name("Eilers-Dörfler, Germaid") == ("Germaid", "Eilers-Dörfler")


def _mit_wechseln(tmp_path, monkeypatch, changes: list[dict]):
    wahl = elections.get(WAHL)
    assert wahl is not None and wahl.archive_folder is not None
    ordner = tmp_path / "archiv"
    shutil.copytree(wahl.archive_folder, ordner)
    (ordner / elected.CHANGES_FILE).write_text(json.dumps({"changes": changes}), encoding="utf-8")
    kopie = replace(wahl, archive_folder=ordner)
    monkeypatch.setattr(elections, "get", lambda slug: kopie if slug == WAHL else None)


def test_nachfolge_ersetzt_den_sitz(tmp_path, monkeypatch):
    # Die Nachfolge ist hier frei gewählt, nur vom Stimmzettel: Wer wirklich
    # nachrückt, sagt die Stadt, nicht dieser Test.
    from app.election import register
    wahl = elections.get(WAHL)
    assert wahl is not None and wahl.register_path is not None
    spd = register.load(wahl.register_path).by_slug("spd")
    assert spd is not None
    nachfolge = spd.candidates(2)[-1].name
    _mit_wechseln(tmp_path, monkeypatch, [
        {"name": "Prange, Ulf", "list": "spd", "reason": "Amt als Oberbürgermeister", "successor": nachfolge},
    ])
    rat = elected.council(_slug, _history(), {}, WAHL)
    assert rat is not None
    namen = {m["name"] for m in rat["members"]}
    assert "Ulf Prange" not in namen and elected.display_name(nachfolge) in namen
    assert len(rat["members"]) == 52
    assert rat["vacancies"][0]["successor"] == elected.display_name(nachfolge)
    neu = next(m for m in rat["members"] if m["name"] == elected.display_name(nachfolge))
    assert neu["mandate"] == "successor" and neu["votes"] is None


def test_nachfolge_muss_auf_der_liste_stehen(tmp_path, monkeypatch):
    _mit_wechseln(tmp_path, monkeypatch, [
        {"name": "Prange, Ulf", "list": "spd", "reason": "x", "successor": "Mustermann, Erika"},
    ])
    with pytest.raises(ValueError, match="nicht auf der Liste"):
        elected._load(WAHL)
    # Nach außen: keine Liste statt einer falschen.
    elected._load.cache_clear()
    assert elected.council(_slug, _history(), {}, WAHL) is None


def test_endpunkt_liefert_denselben_slug_wie_die_personen_seite(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.deps import get_council_store

    class Store:
        def list_members(self):
            return [{"slug": "susanne-menge", "art": "council"}]

        def person_slug(self, name):
            return _slug(name)

        def personen_kanon(self):
            return {}

        def council_history(self, people, before):
            return [{"slug": "susanne-menge", "terms": [2021]} if last == "Menge"
                    else {"slug": None, "terms": []} for _f, last in people]

    app.dependency_overrides[get_council_store] = lambda: Store()
    try:
        c = TestClient(app)
        r = c.get("/api/council/elected")
        assert r.status_code == 200
        assert len(r.json()["members"]) == 52
        r = c.get("/api/council/elected/susanne-menge")
        assert r.status_code == 200 and r.json()["council_status"] == "current"
        assert c.get("/api/council/elected/niemand-da").status_code == 404
    finally:
        app.dependency_overrides.pop(get_council_store, None)


# ------------------------------------------------- der Abgleich im Bestand

def test_ratsgeschichte_findet_zweiten_vornamen_und_perioden(tmp_path):
    """Tims Befund 23.09.2026: „Drügemöller, Ruth" stand als neu im Rat, weil
    Protokolle und Ratsinformationssystem sie „Ruth Regina Drügemöller"
    nennen. Und: Wer nur in einer früheren Wahlperiode saß, ist nicht neu."""
    from council.store import CouncilStore
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        with store._conn:
            store._conn.executemany(
                "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                "location, fetched_at) VALUES (?, ?, ?, '', '', datetime('now'))",
                [(1, "Rat", "2019-03-01"), (2, "Rat", "2023-05-01"), (3, "Sport", "2024-01-10")])
            store._conn.executemany(
                "INSERT INTO council_attendance (ksinr, name, party, role) VALUES (?, ?, 'X', ?)",
                [(2, "Ruth Regina Drügemöller", "member"),
                 (1, "Güzel Tulan", "member"),
                 (3, "Heike Boldt", "member"),          # nur Ausschuss
                 (2, "Anna Maier", "member"), (2, "Anna Beate Maier", "member")])  # zwei Treffer
            store._conn.execute(
                "INSERT INTO council_persons (kpenr, name, current_faction, fetched_at) "
                "VALUES (7, 'Kurt Bernhardt', 'Grüne', datetime('now'))")
            store._conn.executemany(
                "INSERT INTO council_memberships (kpenr, committee, role, valid_from, valid_until, "
                "fetched_at) VALUES (7, 'Rat', 'Ratsmitglied', ?, ?, datetime('now'))",
                [("2001-11-01", "2011-10-31"), ("2016-11-01", None)])
        h = store.council_history([("Ruth", "Drügemöller"), ("Güzel", "Tulan"), ("Heike", "Boldt"),
                                   ("Kurt", "Bernhardt"), ("Anna", "Maier"), ("Pia", "Schlieker")],
                                  "2026-11-01")
        assert h[0] == {"slug": "ruth-regina-druegemoeller", "terms": [2021]}
        assert h[1]["terms"] == [2016]                       # früher, nicht zuletzt
        assert h[2]["terms"] == [] and h[2]["slug"] == "heike-boldt"
        # Offenes Mandat seit 2016 zählt bis zum Tag vor der neuen Periode —
        # nicht in sie hinein.
        assert h[3]["terms"] == [2001, 2006, 2016, 2021]
        # Zwei verschiedene Personen passen: lieber keine Geschichte als die
        # eines Namensvetters.
        assert h[4] == {"slug": None, "terms": []}
        assert h[5] == {"slug": None, "terms": []}
    finally:
        store.close()
