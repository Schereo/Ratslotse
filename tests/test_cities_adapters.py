"""Die Dialekte — gegen echte Rohobjekte aus fünf Ratsinformationssystemen.

Die Fixtures unter ``tests/fixtures/cities/`` sind gekürzte, aber
unveränderte Antworten der Schnittstellen (geholt am 07.09.2026). Sie sind
der Grund, warum diese Tests etwas beweisen: Ein selbstgebautes Beispiel
hätte genau die Eigenheiten nicht, an denen der Probelauf gescheitert ist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from council.cities.adapters import get_adapter
from council.cities.adapters._common import (
    SYNTHETISCHE_KENNUNG, link_by_title, normalize_title, parse_date,
    promote_main, zwillinge_zusammenfuehren,
)
from council.cities.adapters.allris4 import _datum_von
from council.cities.adapters.session import _magdeburg_url, url_fix_for
from council.cities.model import (
    AgendaItem, Batch, Consultation, File, FileRole, Meeting, Outcome, Paper, PaperKind,
    outcome,
)
from council.cities.store import CitiesStore

FIXTURES = Path(__file__).parent / "fixtures" / "cities"
STAEDTE = {
    "osnabrueck": "allris4",
    "braunschweig": "allris4",
    "potsdam": "allris4",
    "langenhagen": "allris4",
    # Peine ist die Stadt, die zeigt, dass „ALLRIS 4" kein Verhalten
    # garantiert: Ihre Listen sortieren neu-zuerst, alle anderen alt-zuerst.
    "peine": "allris4",
    "muenster": "session",
    "magdeburg": "session",
}


def lade(store: CitiesStore, stadt: str) -> None:
    for papier in json.loads((FIXTURES / f"{stadt}_papers.json").read_text(encoding="utf-8")):
        store.put_raw_object(stadt, "paper", papier["id"], papier)


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "raw.sqlite")
    yield s
    s.close()


@pytest.mark.parametrize("stadt,dialekt", sorted(STAEDTE.items()))
def test_normalize_baut_papiere_mit_datei_und_beratung(store, stadt, dialekt):
    lade(store, stadt)
    batch = get_adapter(dialekt).normalize(stadt, store)

    assert len(batch.papers) == 4, "jedes Rohpapier wird zu genau einem Papier"
    for p in batch.papers:
        assert p.body_id == stadt
        assert p.name, "ein Papier ohne Titel wäre in jeder Liste unsichtbar"
        assert p.kind in set(PaperKind), p.kind
        assert p.id.startswith("http"), "die OParl-Kennung ist die Objekt-URL"

    # Jedes Papier bringt ein Hauptdokument mit — bei ALLRIS als mainFile,
    # bei Somacos als Anlage mit sprechendem Namen.
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    assert len(haupt) == 4, f"{stadt}: Hauptdokumente nicht erkannt"
    for f in haupt:
        assert f.access_url and f.access_url.startswith("http")
        assert f.paper_id

    assert batch.consultations, f"{stadt}: keine Beratungsfolge"


def test_session_kennt_kein_mainfile(store):
    """Somacos hängt das Hauptdokument unter ``auxiliaryFile`` — nur der Name
    unterscheidet es von einem Lageplan."""
    lade(store, "muenster")
    roh = json.loads((FIXTURES / "muenster_papers.json").read_text(encoding="utf-8"))
    assert all("mainFile" not in p for p in roh)
    batch = get_adapter("session").normalize("muenster", store)
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    # Je Papier genau eines — und es heißt „…vorlage", auch wenn es zwischen
    # sechs Anlagen an sechster Stelle steht.
    assert len(haupt) == 4
    assert {f.name for f in haupt} == {"Beschlussvorlage", "Berichtsvorlage"}
    assert len({f.paper_id for f in haupt}) == 4


def test_ohne_erkennbares_hauptdokument_gilt_die_erste_anlage(store):
    """Sonst bekäme ein Papier, dessen Anlagen alle „Anlage 1" heißen, nie Text."""
    nur_anlagen = [File("f1", "x", FileRole.AUXILIARY, name="Anlage 1"),
                   File("f2", "x", FileRole.AUXILIARY, name="Anlage 2")]
    assert [f.role for f in promote_main(nur_anlagen)] == [FileRole.MAIN, FileRole.AUXILIARY]
    # Wo eines erkannt ist, bleibt alles, wie es ist.
    mit_haupt = [File("f1", "x", FileRole.AUXILIARY, name="Anlage 1"),
                 File("f2", "x", FileRole.MAIN, name="Beschlussvorlage")]
    assert [f.role for f in promote_main(mit_haupt)] == [FileRole.AUXILIARY, FileRole.MAIN]
    assert promote_main([]) == []


def test_magdeburg_datei_adresse_wird_umgeschrieben(store):
    """Die Schnittstelle nennt Adressen, die durchweg 404 antworten.

    Gemessen an fünf Dokumenten am 07.09.2026: sowohl ``accessUrl`` als auch
    ``downloadUrl``. Dieselben Dateien liegen unter ``getfile.asp``.
    """
    lade(store, "magdeburg")
    batch = get_adapter("session").normalize("magdeburg", store)
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    assert haupt, "Magdeburg hat Hauptdokumente"
    for f in haupt:
        assert "getfile.asp?id=" in (f.access_url or ""), f.access_url
        assert "downloadfiles" not in (f.access_url or "")
        assert "type=do" in (f.access_url or "")


def test_magdeburg_url_baut_die_kennung_ohne_fuehrende_nullen():
    datei = {"fileName": "00692749.pdf",
             "accessUrl": "https://ratsinfo.magdeburg.de/oparl/bodies/0001/downloadfiles/a/00692749.pdf"}
    assert _magdeburg_url(datei, datei["accessUrl"]) == \
        "https://ratsinfo.magdeburg.de/getfile.asp?id=692749&type=do"
    # Ohne erkennbare Nummer bleibt die Adresse, wie sie war.
    assert _magdeburg_url({"fileName": "anlage.pdf"}, "https://x/y") == "https://x/y"


def test_url_fix_greift_nur_bei_magdeburg():
    assert url_fix_for({"id": "https://ratsinfo.magdeburg.de/oparl/bodies/0001"}) is not None
    assert url_fix_for({"id": "https://oparl.stadt-muenster.de/bodies/0001"}) is None


def test_allris_leerdatum_gilt_als_unbekannt():
    """ALLRIS setzt ``created``/``modified`` bei jedem Objekt auf 2000-01-01.

    Wer den Wert für echt hält, sortiert den ganzen Bestand auf einen Tag —
    und ein Zeitfilter darauf liefert entweder alles oder nichts.
    """
    assert parse_date("2000-01-01T00:00:00+01:00") is None
    assert parse_date("2026-09-03") == "2026-09-03"
    assert parse_date(None) is None
    assert parse_date("kein Datum") is None


def test_allris_verbindet_papier_und_ergebnis_ueber_den_titel(store):
    """ALLRIS nennt in der Beratungsfolge keinen Tagesordnungspunkt.

    Ohne den Titelabgleich hätte in Osnabrück, Braunschweig und Potsdam
    **kein einziges** Papier ein Ergebnis.
    """
    lade(store, "osnabrueck")
    roh = json.loads((FIXTURES / "osnabrueck_papers.json").read_text(encoding="utf-8"))
    assert all(not c.get("agendaItem") for p in roh for c in p.get("consultation", []))

    batch = get_adapter("allris4").normalize("osnabrueck", store)
    # Ohne passende Sitzung kann auch der Abgleich nichts verbinden …
    assert not [c for c in batch.consultations if c.agenda_item_id]

    # … mit einer Sitzung, deren Punkt genauso heißt, schon.
    titel = batch.papers[0].name
    batch.meetings.append(Meeting("m1", "osnabrueck", None, "Rat", "2026-09-01T16:00"))
    batch.agenda_items.append(AgendaItem("a1", "m1", titel, result_raw="ungeändert beschlossen",
                                         outcome=Outcome.ACCEPTED))
    assert link_by_title(batch) == 1
    verbunden = [c for c in batch.consultations if c.agenda_item_id == "a1"]
    assert verbunden and "#title-match#" in verbunden[0].id, \
        "ein geratener Treffer muss als solcher erkennbar bleiben"


def test_titelabgleich_verbindet_ALLE_stationen():
    """Ausschuss und dann Rat — das ist der Normalfall, kein Widerspruch.

    Bis 09.09.2026 stand hier die Regel „nur eindeutige Treffer, sonst
    lieber kein Ergebnis als ein falsches". Sie klingt vorsichtig und war
    teuer: Weil eine Vorlage fast immer durch mindestens zwei Stationen
    läuft, traf sie fast nie zu. Potsdam kam auf 23 % Papiere mit Ergebnis,
    Braunschweig auf 42 % — gemessen fehlten 5.224 Papieren ein Ergebnis,
    obwohl ein gleichnamiger Punkt mit Ergebnis danebenlag.

    Welche Station gilt, entscheidet `store.outcome_for_paper`: erst
    `authoritative`, dann die späteste Sitzung. Die Entscheidung gehört
    dorthin, wo sie schon steht.
    """
    batch = Batch(
        papers=[Paper("p1", "x", "Bericht zur Lage")],
        meetings=[Meeting("m1", "x", None, "Ausschuss", "2026-01-01"),
                  Meeting("m2", "x", None, "Rat", "2026-02-01")],
        agenda_items=[
            AgendaItem("a1", "m1", "Bericht zur Lage", result_raw="empfohlen", outcome=Outcome.ACCEPTED),
            AgendaItem("a2", "m2", "Bericht zur Lage", result_raw="beschlossen", outcome=Outcome.ACCEPTED),
        ])
    assert link_by_title(batch) == 2
    assert {c.agenda_item_id for c in batch.consultations} == {"a1", "a2"}


def test_titelabgleich_bleibt_bei_mehrdeutigem_TITEL_stumm():
    """Wo der echte Fehler droht: zwei PAPIERE, ein Titel.

    „Antrag", „Liquiditätsstand - Bericht", „Annahme von Zuwendungen durch
    den Rat" — solche Titel gibt es dutzendfach in einer Stadt. Ein Abgleich
    darüber ist kein Abgleich, sondern Raten. Gemessen sind 27 % aller Titel
    im Bestand mehrdeutig; sie stellen 2.934 der 5.224 Papiere, die sonst
    ein Ergebnis bekämen — mehrheitlich ein falsches.
    """
    batch = Batch(
        papers=[Paper("p1", "x", "Antrag"), Paper("p2", "x", "Antrag")],
        meetings=[Meeting("m1", "x", None, "Rat", "2026-01-01")],
        agenda_items=[
            AgendaItem("a1", "m1", "Antrag", result_raw="beschlossen", outcome=Outcome.ACCEPTED),
        ])
    assert link_by_title(batch) == 0
    assert not batch.consultations


def test_titelabgleich_ruehrt_verbundene_papiere_nicht_an():
    batch = Batch(
        papers=[Paper("p1", "x", "Mehrweg fördern")],
        meetings=[Meeting("m1", "x", None, "Rat", "2026-01-01")],
        agenda_items=[AgendaItem("a1", "m1", "Mehrweg fördern")],
        consultations=[Consultation("c1", "p1", agenda_item_id="a1")])
    assert link_by_title(batch) == 0
    assert len(batch.consultations) == 1


def test_normalize_title_faellt_ueber_satzzeichen_hinweg_zusammen():
    assert normalize_title("Mehrweg fördern – Müll, Kosten") == \
        normalize_title("Mehrweg fördern  Müll Kosten")
    assert normalize_title(None) == ""


def test_normalize_ist_idempotent(store):
    """Zweimal normalisieren ändert nichts — die Stufe wird oft wiederholt."""
    lade(store, "braunschweig")
    a = get_adapter("allris4").normalize("braunschweig", store)
    b = get_adapter("allris4").normalize("braunschweig", store)
    assert a.counts() == b.counts()
    assert [p.id for p in a.papers] == [p.id for p in b.papers]


def test_normalize_liest_nur_die_letzte_fassung(store):
    """Ein geändertes Papier erzeugt eine zweite Rohzeile — aber ein Objekt."""
    lade(store, "potsdam")
    roh = json.loads((FIXTURES / "potsdam_papers.json").read_text(encoding="utf-8"))
    geaendert = dict(roh[0], name="Titel nach Korrektur")
    store.put_raw_object("potsdam", "paper", geaendert["id"], geaendert)

    batch = get_adapter("allris4").normalize("potsdam", store)
    assert len(batch.papers) == 4
    assert any(p.name == "Titel nach Korrektur" for p in batch.papers)


def test_kein_papier_traegt_eine_person(store):
    """Was der Adapter baut, enthält keine Personen — auch nicht versehentlich."""
    for stadt, dialekt in STAEDTE.items():
        lade(store, stadt)
        batch = get_adapter(dialekt).normalize(stadt, store)
        for p in batch.papers:
            assert not hasattr(p, "originator_person")
        for o in batch.organizations:
            assert "originatorPerson" not in o.name


def test_einzelne_ersatzzeichen_fliegen_aus_dem_text():
    """Python lässt ein einzelnes Surrogat im `str` zu, `encode("utf-8")`
    wirft darauf. Aus einem PDF kommt so etwas, wenn eine Schrift eine kaputte
    Zuordnungstabelle hat.

    Gemessen: Beim Backfill der Osnabrücker Historie (08.09.2026) steckte in
    genau EINEM Dokument ein \\uda00. Der Fehler entstand beim PDF-Lesen,
    schlug aber erst beim Schreiben zu — und riss die ganze Stadt mit, nach
    2.864 schon geernteten Vorlagen.
    """
    from council.cities.text import clean

    sauber = clean("Vorlage \ud800 Nr. \uda00 5")
    assert "\ud800" not in sauber and "\uda00" not in sauber
    assert sauber.encode("utf-8")  # das ist der Punkt: es geht durch
    # Ohne Surrogate bleibt der Text unangetastet.
    assert clean("Ganz normaler Text") == "Ganz normaler Text"


def test_magdeburg_bindet_ueber_die_kennung_allein(store):
    """Somacos verweist sauber — es braucht keinen Titelabgleich.

    Bis 10.09.2026 stand hier das Gegenteil: Magdeburgs Beratungen zeigten
    angeblich auf einen zweiten Kennungsraum, den die Sitzungen nicht kennen,
    und `link_within_meeting` verband sie über den Titel. Beides war der Rest
    des phase0-Imports — die Sitzungs-Fixture trug erfundene `#top-`-Kennungen
    statt der echten. Gegen die richtigen Rohobjekte gehalten nennt die
    Beratungsfolge genau die Punkte, die auch in der Sitzung stehen.

    Dieser Test ist der Wächter, der die entfernte Funktion ersetzt: Fällt er,
    verweist eine Somacos-Instanz doch wieder ins Leere, und dann braucht es
    einen Notnagel — aber einen, der zu dem passt, was dann wirklich schiefgeht.
    """
    lade(store, "magdeburg")
    sitzungen = json.loads(
        (FIXTURES / "magdeburg_meetings.json").read_text(encoding="utf-8"))
    for s in sitzungen:
        store.put_raw_object("magdeburg", "meeting", s["id"], s)
    batch = get_adapter("session").normalize("magdeburg", store)

    punkte = {a.id for a in batch.agenda_items}
    mit_punkt = [c for c in batch.consultations if c.agenda_item_id]
    gebunden = [c for c in mit_punkt if c.agenda_item_id in punkte]
    assert gebunden, "keine einzige Beratung hat ihren Tagesordnungspunkt gefunden"
    assert len(gebunden) == len(mit_punkt), \
        "eine Beratung nennt einen Punkt, den ihre Sitzung nicht kennt"
    # Und die Verbindung entsteht wirklich aus der Kennung, nicht aus einem
    # Notnagel: Kein `#title-match#` unter den gebundenen.
    assert not [c for c in gebunden if "#title-match#" in c.id]


@pytest.mark.parametrize("objekt,erwartet", [
    ({"date": "2024-05-01"}, "2024-05-01"),            # eine Vorlage
    ({"start": "2024-05-01T16:00:00+02:00"}, "2024-05-01"),  # eine Sitzung
    ({"name": "ohne alles"}, "0000-00-00"),            # undatiert gilt als alt
])
def test_listendatum_kennt_vorlage_und_sitzung(objekt, erwartet):
    """Eine Sitzung hat `start`, keine `date`.

    Die erste Fassung fragte überall nach `date`. Damit galt JEDE Sitzung als
    undatiert und also als alt, und die Rückwärts-Blätterung brach nach zwei
    Seiten ab — bei jedem Lauf. Osnabrück hatte deshalb 137 Sitzungen zu 2.864
    Vorlagen; ohne Sitzung gibt es keinen Tagesordnungspunkt und kein Ergebnis.
    """
    assert _datum_von(objekt) == erwartet


# --------------------------------------------------------------------------
# Derselbe Punkt unter zwei Kennungen (der phase0-Rest)
# --------------------------------------------------------------------------

def _batch_mit_zwillingen() -> Batch:
    """Ein Punkt, zwei Zeilen — genau wie 22.152-mal im Bestand.

    Links die Kennung, die ``scripts/cities_import_phase0.py`` erfunden hat,
    rechts die echte des Punktes. Gleiche Nummer, gleicher Titel; das Ergebnis
    trägt nur die echte, so lag es bei 92 Paaren.
    """
    return Batch(
        papers=[Paper("p1", "muenster", "Smart City Münster", reference="V/0815/2026")],
        meetings=[Meeting("https://x/meetings/1", "muenster", None, "Rat", "2026-03-01")],
        agenda_items=[
            AgendaItem("https://x/meetings/1#top-1", "https://x/meetings/1",
                       "Eingänge und Mitteilungen", number="1", position=0),
            AgendaItem("https://x/agendaitems/284259", "https://x/meetings/1",
                       "Eingänge und Mitteilungen", number="1", position=1,
                       result_raw="beschlossen", outcome=outcome("beschlossen")),
        ],
        consultations=[Consultation("c1", "p1", meeting_id="https://x/meetings/1",
                                    agenda_item_id="https://x/meetings/1#top-1")],
        files=[File("f1", "muenster", role=FileRole.RESOLUTION,
                    agenda_item_id="https://x/meetings/1#top-1")],
    )


def test_zwillinge_werden_zu_einer_zeile():
    """Die eigene Kennung des Punktes gewinnt, alles Fremde zeigt auf sie."""
    batch = _batch_mit_zwillingen()
    assert zwillinge_zusammenfuehren(batch) == 1
    assert [a.id for a in batch.agenda_items] == ["https://x/agendaitems/284259"], \
        "die erfundene Kennung ist weg, die echte bleibt"
    assert batch.consultations[0].agenda_item_id == "https://x/agendaitems/284259"
    assert batch.files[0].agenda_item_id == "https://x/agendaitems/284259"


def test_ergebnis_der_echten_kennung_gilt():
    """Wo beide ein Ergebnis tragen und sich widersprechen, gilt die Schnittstelle.

    43-mal stand im übernommenen Probelauf „beschlossen", wo die Schnittstelle
    „vertagt" sagt. Der Probelauf war abgeschrieben, die Schnittstelle ist die
    Quelle.
    """
    batch = _batch_mit_zwillingen()
    batch.agenda_items[0] = AgendaItem(
        "https://x/meetings/1#top-1", "https://x/meetings/1",
        "Eingänge und Mitteilungen", number="1", position=0,
        result_raw="beschlossen", outcome=outcome("beschlossen"))
    batch.agenda_items[1] = AgendaItem(
        "https://x/agendaitems/284259", "https://x/meetings/1",
        "Eingänge und Mitteilungen", number="1", position=1,
        result_raw="vertagt", outcome=outcome("vertagt"))
    assert zwillinge_zusammenfuehren(batch) == 1
    assert batch.agenda_items[0].outcome == Outcome.POSTPONED
    assert batch.agenda_items[0].result_raw == "vertagt"


def test_leere_echte_zeile_erbt_das_ergebnis():
    """Was der Gewinner nicht hat, darf der Verlierer beisteuern — nur das."""
    batch = _batch_mit_zwillingen()
    batch.agenda_items[0] = AgendaItem(
        "https://x/meetings/1#top-1", "https://x/meetings/1",
        "Eingänge und Mitteilungen", number="1", position=0,
        result_raw="beschlossen", outcome=outcome("beschlossen"),
        resolution_text="Der Rat beschließt.")
    batch.agenda_items[1] = AgendaItem(
        "https://x/agendaitems/284259", "https://x/meetings/1",
        "Eingänge und Mitteilungen", number="1", position=1)
    assert zwillinge_zusammenfuehren(batch) == 1
    gewinner = batch.agenda_items[0]
    assert gewinner.id == "https://x/agendaitems/284259"
    assert gewinner.outcome == Outcome.ACCEPTED
    assert gewinner.resolution_text == "Der Rat beschließt."


def test_zwei_echte_punkte_bleiben_zwei():
    """Der Fall, an dem eine Zusammenlegung nach Titel Daten zerstört hätte.

    Potsdam führt „Informationen des Jugendamtes" wirklich zweimal in einer
    Sitzung, und in Magdeburg stehen Vorlage und Änderungsantrag unter
    demselben Titel mit VERSCHIEDENEM Ergebnis. 16 solcher Fälle liegen im
    Bestand — zusammengelegt wäre einer der beiden Beschlüsse verschwunden.
    """
    batch = _batch_mit_zwillingen()
    batch.agenda_items = [
        AgendaItem("https://x/agendaitems/505237", "https://x/meetings/1",
                   "Kostenfreier Eintritt für Familien", number="6",
                   position=17, result_raw="abgelehnt", outcome=outcome("abgelehnt")),
        AgendaItem("https://x/agendaitems/505241", "https://x/meetings/1",
                   "Kostenfreier Eintritt für Familien", number="6",
                   position=18, result_raw="beschlossen", outcome=outcome("beschlossen")),
    ]
    assert zwillinge_zusammenfuehren(batch) == 0
    assert len(batch.agenda_items) == 2


def test_nur_erfundene_kennungen_bleiben_stehen():
    """Ohne Ziel wird nicht zusammengelegt — lieber doppelt als verloren.

    Eine Sitzung, die nur aus dem übernommenen Probelauf stammt und nie
    nachgeerntet wurde, hat keinen Gewinner. Ihre Punkte bleiben, wie sie sind.
    """
    batch = Batch(
        papers=[Paper("p1", "magdeburg", "Investitionen in den Messeplatz fördern",
                      reference="DS0123/26")],
        meetings=[Meeting("https://x/meetings/1", "magdeburg", None, "Stadtrat",
                          "2026-03-01")],
        agenda_items=[
            AgendaItem("https://x/meetings/1#top-4", "https://x/meetings/1",
                       "Investitionen in den Messeplatz fördern", number="4",
                       result_raw="beschlossen", outcome=outcome("beschlossen")),
            AgendaItem("https://x/meetings/1#top-4.1", "https://x/meetings/1",
                       "Investitionen in den Messeplatz fördern", number="4.1",
                       result_raw="beschlossen", outcome=outcome("beschlossen")),
        ],
        consultations=[Consultation("c1", "p1", meeting_id="https://x/meetings/1",
                                    agenda_item_id="https://x/agendaitems/999")],
    )
    vorher = [a.id for a in batch.agenda_items]
    assert zwillinge_zusammenfuehren(batch) == 0
    assert [a.id for a in batch.agenda_items] == vorher


@pytest.mark.parametrize("stadt,dialekt", sorted(STAEDTE.items()))
def test_keine_erfundenen_kennungen_aus_dem_normalisieren(store, stadt, dialekt):
    """Kein Dialekt darf eine ``#top-``-Kennung erzeugen.

    Sie kam nie von einer Schnittstelle, sondern aus
    ``scripts/cities_import_phase0.py``. Taucht sie wieder auf, liegt der
    Bestand ein zweites Mal doppelt — und das sieht man keiner Kennzahl an.
    """
    lade(store, stadt)
    batch = get_adapter(dialekt).normalize(stadt, store)
    erfunden = [a.id for a in batch.agenda_items if SYNTHETISCHE_KENNUNG in a.id]
    assert not erfunden, f"{stadt}: {len(erfunden)} erfundene Kennungen"


def test_migration_fuehrt_den_bestand_zusammen(tmp_path):
    """Die Reparatur des gewachsenen Bestands — Schema und Migration sind zwei Stellen.

    Der Batch-Weg oben hält nur, dass keine NEUEN entstehen. Die 22.152 Zeilen,
    die schon liegen, holt kein Normalisieren mehr ab: `upsert_batch` schreibt
    und ersetzt, es löscht nichts.
    """
    pfad = tmp_path / "alt.sqlite"
    s = CitiesStore(pfad)
    s.upsert_batch(_batch_mit_zwillingen())
    s._conn.execute("INSERT INTO bodies (id, name, state, ris_vendor) "
                    "VALUES ('muenster', 'Münster', 'NW', 'session')")
    s._conn.commit()
    # Auf den Stand VOR der Reparatur zurückdrehen und neu öffnen.
    s._conn.execute("UPDATE meta SET value='6' WHERE key='schema_version'")
    s._conn.commit()
    s.close()

    s = CitiesStore(pfad)
    punkte = s.agenda_items("https://x/meetings/1")
    assert [p["id"] for p in punkte] == ["https://x/agendaitems/284259"]
    assert s.duplicate_agenda_items() == {}
    beratung = s._conn.execute("SELECT agenda_item_id FROM consultations").fetchone()
    assert beratung["agenda_item_id"] == "https://x/agendaitems/284259", \
        "die Beratung hängt jetzt am überlebenden Punkt"
    s.close()


def test_normalisieren_ruft_die_zusammenfuehrung(store):
    """Der Weg, den ein Lauf geht — nicht nur die Funktion für sich.

    Eine Sitzung, deren Rohobjekt beide Kennungen desselben Punktes führt.
    Ohne den Aufruf in ``normalize_common`` kämen hier zwei Zeilen an, und
    jede Zählung über ``agenda_items`` wäre um den Faktor zwei daneben.
    """
    store.put_raw_object("muenster", "meeting", "https://x/meetings/1", {
        "id": "https://x/meetings/1",
        "name": "Rat",
        "start": "2026-03-01T16:00:00+02:00",
        "agendaItem": [
            {"id": "https://x/meetings/1#top-1", "number": "1",
             "name": "Eingänge und Mitteilungen", "public": True},
            {"id": "https://x/agendaitems/284259", "number": "1",
             "name": "Eingänge und Mitteilungen", "public": True,
             "result": "beschlossen"},
        ],
    })
    batch = get_adapter("session").normalize("muenster", store)
    assert [a.id for a in batch.agenda_items] == ["https://x/agendaitems/284259"]
    assert batch.agenda_items[0].outcome == Outcome.ACCEPTED
