"""Eine Person, zwei Namensformen (``council/namensformen.py``).

Dieselbe Person steht in den Anwesenheitslisten unter zwei Namensformen; ohne
Zuordnung zerfällt sie in zwei Profile mit je einem Teil ihrer Sitzungen.
Geprüft wird hier beides: dass die Zusammenführung greift **und** dass sie
Namensvettern in Ruhe lässt.
"""
from __future__ import annotations

import pytest

from council import namensformen
from council.store import CouncilStore


# --- die reine Regel ------------------------------------------------------

def test_kanonisch_nimmt_die_juengste_fundstelle():
    """Es entscheidet allein das Datum — nicht die Länge des Namens und nicht,
    wie oft eine Form vorkommt. Bei Wolff ist die **kürzere** Form die jüngste,
    bei Harms die längere; beide Richtungen müssen aus derselben Regel fallen."""
    kanon = namensformen.kanonisch({
        "tim-harms": ("2026-04-21", 133),
        "tim-ebbeke-harms": ("2026-06-01", 2),
        "christine-wolff": ("2026-06-01", 183),
        "christine-berta-wolff": ("2023-01-25", 31),
    })
    assert kanon["tim-harms"] == "tim-ebbeke-harms"
    assert kanon["christine-berta-wolff"] == "christine-wolff"
    # Die kanonische Form zeigt nicht auf sich selbst.
    assert "tim-ebbeke-harms" not in kanon and "christine-wolff" not in kanon


def test_kanonisch_haelt_alte_links_am_leben():
    """Kommt eine Namensform im Bestand gar nicht (mehr) vor, zeigt sie
    trotzdem auf die belegte — sonst liefe ein geteilter Link ins Leere."""
    kanon = namensformen.kanonisch({"tim-harms": ("2026-04-21", 133)})
    assert kanon["tim-ebbeke-harms"] == "tim-harms"
    # Ohne jede Fundstelle gibt es nichts zu führen.
    assert namensformen.kanonisch({}) == {}


def test_gruppen_sind_disjunkt():
    """Eine Namensform darf nur zu einer Person gehören — sonst hinge das
    Ergebnis davon ab, welche Gruppe zuerst gelesen wird."""
    alle = [s for g in namensformen.GRUPPEN for s in g]
    assert len(alle) == len(set(alle))
    assert all(len(g) >= 2 for g in namensformen.GRUPPEN)


def test_verdachtsfaelle_meldet_aber_verschmilzt_nicht():
    paare = namensformen.verdachtsfaelle({
        # ein Verdachtspaar: gleicher Vor- und Nachname, nie zusammen gesehen
        "anna-krause": {1, 2},
        "anna-maria-krause": {3},
        # Namensvettern: verschiedene Vornamen → keine Meldung
        "sebastian-rohe": {1},
        "georg-rohe": {1, 2},
        # gleicher Vorname UND Nachname, aber gemeinsame Sitzung → zwei Menschen
        "peter-behrens": {5},
        "peter-jan-behrens": {5, 6},
    })
    gemeldet = {(p["a"], p["b"]) for p in paare}
    assert ("anna-krause", "anna-maria-krause") in gemeldet
    assert not any("rohe" in a or "rohe" in b for a, b in gemeldet)
    assert not any("behrens" in a for a, b in gemeldet)
    # Gemeldet heißt: ungeprüft. Zusammengeführt wird davon nichts.
    assert all(p["gefuehrt"] is False for p in paare)


# --- der Bestand ----------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    """Die drei geführten Gruppen plus ein Namensvetter, der es nicht ist."""
    st = CouncilStore(tmp_path / "c.sqlite")
    with st._conn:
        st._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (?, ?, ?, '', '', datetime('now'))",
            [(1, "Rat", "2024-01-10"), (2, "Rat", "2026-05-21"),
             (3, "Schulausschuss", "2022-03-16"), (4, "Schulausschuss", "2022-05-03"),
             (5, "Rat", "2019-11-05"), (6, "Rat", "2026-06-01")])
        st._conn.executemany(
            "INSERT INTO council_attendance (ksinr, name, party, role) VALUES (?, ?, ?, ?)",
            [(1, "Tim Harms", "Bündnis 90/Die Grünen", "member"),
             (2, "Tim Ebbeke Harms", "Bündnis 90/Die Grünen", "member"),
             (1, "Dr. Ingo Harms", "CDU", "member"),
             (2, "Dr. Ingo Harms", "CDU", "member"),
             (3, "Jan Freede", "Verwaltung", "administration"),
             (4, "Jan Reinder Freede", "Verwaltung", "administration"),
             (5, "Christine Berta Wolff", "Bündnis 90/Die Grünen", "member"),
             (6, "Christine Wolff", "Bündnis 90/Die Grünen", "member")])
        st._conn.executemany(
            "INSERT INTO council_speeches (ksinr, position, speaker, party, kind, top, "
            "text, extracted_at) VALUES (?, ?, ?, 'Bündnis 90/Die Grünen', 'rede', 'Ö 1', ?, "
            "datetime('now'))",
            [(1, 1, "Tim Harms", "Unter der älteren Namensform"),
             (2, 2, "Ratsherr Ebbeke Harms", "Unter der jüngeren Namensform"),
             (2, 3, "Dr. Ingo Harms", "Der Namensvetter")])
    try:
        yield st
    finally:
        st.close()


def test_verzeichnis_fuehrt_eine_person_einmal(store):
    members = {m["slug"]: m for m in store.list_members()}
    # Zwei Namensformen, ein Eintrag — unter der Form der jüngsten Fundstelle.
    assert "tim-harms" not in members
    assert members["tim-ebbeke-harms"]["name"] == "Tim Ebbeke Harms"
    assert members["tim-ebbeke-harms"]["n"] == 2          # Summe beider Formen
    # Bei Wolff ist die kürzere Form die jüngste.
    assert "christine-berta-wolff" not in members
    assert members["christine-wolff"]["name"] == "Christine Wolff"
    assert members["christine-wolff"]["n"] == 2
    # Der Namensvetter bleibt eine eigene Person.
    assert members["ingo-harms"]["name"] == "Dr. Ingo Harms"
    assert members["ingo-harms"]["n"] == 2


def test_verzeichnis_findet_auch_die_aeltere_form(store):
    [harms] = [m for m in store.list_members() if m["slug"] == "tim-ebbeke-harms"]
    assert set(harms["formen"]) == {"Tim Harms", "Tim Ebbeke Harms"}


def test_alter_slug_landet_beim_kanonischen_profil(store):
    alt = store.member_detail("tim-harms")
    neu = store.member_detail("tim-ebbeke-harms")
    assert alt is not None and neu is not None
    assert alt["slug"] == neu["slug"] == "tim-ebbeke-harms"   # Adresse ist die aktuelle
    assert alt["name"] == "Tim Ebbeke Harms"
    assert alt["n_sessions"] == 2                             # Historie ist die Summe
    assert alt["active_from"] == "2024-01-10" and alt["active_to"] == "2026-05-21"
    assert store.member_name("tim-harms") == "Tim Ebbeke Harms"
    # Der Namensvetter zieht nichts davon an sich.
    assert store.member_detail("ingo-harms")["n_sessions"] == 2


def test_wortbeitraege_sind_die_summe_beider_formen(store):
    d = store.member_detail("tim-harms")
    texte = {w["text"] for w in d["speeches"]}
    assert texte == {"Unter der älteren Namensform", "Unter der jüngeren Namensform"}
    assert d["speeches_total"] == 2
    # „Dr. Ingo Harms" trägt denselben Nachnamen und bleibt trotzdem draußen.
    assert store.member_detail("ingo-harms")["speeches_total"] == 1


def test_lexikon_fuehrt_verwaltung_und_rat_je_einmal(store):
    lex = {p["slug"]: p for p in store.personen_lexikon()}
    # Verwaltungszweig (steht in keinem Mitglieder-Verzeichnis).
    assert "jan-freede" not in lex
    assert lex["jan-reinder-freede"]["name"] == "Jan Reinder Freede"
    assert lex["jan-reinder-freede"]["art"] == "city"
    assert (lex["jan-reinder-freede"]["von"], lex["jan-reinder-freede"]["bis"]) == ("2022", "2022")
    # Ratszweig: genau ein Harms mit Vornamen Tim — sonst gäbe der Badge-Matcher
    # bei zwei gleich benannten Kandidaten absichtlich auf.
    tim = [p for p in lex.values() if p["nachname"] == "harms" and p["vorname"] == "tim"]
    assert len(tim) == 1 and tim[0]["slug"] == "tim-ebbeke-harms"


def test_kanon_karte_zeigt_auf_die_juengste_form(store):
    kanon = store.personen_kanon()
    assert kanon == {"tim-harms": "tim-ebbeke-harms",
                     "jan-freede": "jan-reinder-freede",
                     "christine-berta-wolff": "christine-wolff"}
    assert store.person_slug("Tim Harms") == "tim-ebbeke-harms"
    assert store.person_slug("Dr. Ingo Harms") == "ingo-harms"
    assert store.personen_namensformen("tim-harms") == ["Tim Ebbeke Harms", "Tim Harms"]
