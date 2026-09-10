"""Ideen-Cluster: dieselbe Sache in mehreren Städten.

Die Tests rechnen mit handgeschriebenen Vektoren, nicht mit fastembed — sonst
prüften sie das Einbettungsmodell und nicht die Gruppierung.
"""
from __future__ import annotations

import numpy as np
import pytest

from council.cities import clusters as cl
from council.cities.model import Batch, Body, Paper
from council.cities.store import CitiesStore

MODELL = "test-modell"


def vektor(*werte: float) -> bytes:
    v = np.array(werte, dtype=np.float32)
    return (v / np.linalg.norm(v)).tobytes()


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    s.upsert_body(Body("oldenburg", "Oldenburg", "NI", "oldenburg"))
    yield s
    s.close()


def idee(store: CitiesStore, kennung: str, stadt: str, titel: str,
         instrument: str, v: bytes) -> None:
    store.upsert_batch(Batch(papers=[Paper(kennung, stadt, titel)]))
    store.put_annotation("paper", kennung, "classify", "2",
                         {"field": "klima_umwelt", "transfer": "adaptable",
                          "competence": "council", "instrument": instrument,
                          "summary": "Zusammenfassung."}, "h" + kennung)
    store.put_object_embedding(cl.IDEA_KIND, kennung, MODELL, "h" + kennung, v)


# ------------------------------------------------------------------ Der Text

def test_die_idee_ist_instrument_und_zusammenfassung():
    """Kein Titel, keine Stadt, kein Datum — genau die trennen zwei Städte,
    die dasselbe tun."""
    text = cl.idea_text({"instrument": "Verpackungssteuer einführen",
                         "summary": "Eine Steuer auf Einwegverpackungen.",
                         "field": "klima_umwelt"})
    assert text.startswith("Verpackungssteuer einführen")
    assert "Einwegverpackungen" in text
    assert cl.idea_text({"instrument": None}) == "", \
        "ohne Instrument gibt es keine Idee zum Vergleichen"


# --------------------------------------------------------------- Gruppierung

def test_zwei_nahe_ideen_bilden_einen_cluster(store):
    idee(store, "os:1", "osnabrueck", "Verpackungssteuer", "Verpackungssteuer einführen",
         vektor(1.0, 0.0, 0.0))
    idee(store, "ol:1", "oldenburg", "Verpackungssteuer", "Verpackungssteuer erheben",
         vektor(0.99, 0.14, 0.0))
    zahlen = cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert zahlen["clusters"] == 1 and zahlen["members"] == 2


def test_ferne_ideen_bleiben_getrennt(store):
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Radweg bauen", vektor(0.0, 1.0))
    assert cl.build_clusters(store, MODELL, threshold=0.86, version="1")["clusters"] == 0


def test_ein_einzelnes_papier_ist_kein_cluster(store):
    """5.000 Einzelmengen in der Tabelle müsste jede Auswertung wegfiltern."""
    idee(store, "os:1", "osnabrueck", "A", "Alleinstellungsmerkmal", vektor(1.0, 0.0))
    zahlen = cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert zahlen["clusters"] == 0 and zahlen["members"] == 0


def test_die_kette_bleibt_zusammen(store):
    """Single linkage ist Absicht: Eine Idee wandert über Zwischenglieder.

    Osnabrücks „Mehrwegsystem erproben" liegt nah an Münsters „Mehrwegpfand
    einführen", das nah an Potsdams „Verpackungssteuer prüfen" — die beiden
    Enden aber nicht aneinander. Average linkage zerschnitte die Kette; genau
    sie ist die Idee, die durch die Republik läuft.
    """
    idee(store, "a", "osnabrueck", "A", "Mehrwegsystem erproben", vektor(1.0, 0.0, 0.0))
    idee(store, "b", "osnabrueck", "B", "Mehrwegpfand einführen", vektor(0.93, 0.37, 0.0))
    idee(store, "c", "oldenburg", "C", "Verpackungssteuer prüfen", vektor(0.73, 0.68, 0.0))
    zahlen = cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert zahlen["clusters"] == 1 and zahlen["members"] == 3, \
        "a–b und b–c liegen über der Schwelle, a–c nicht — die Kette hält"


# -------------------------------------------------------------------- Lesen

def test_der_cluster_nennt_seine_staedte_und_ob_oldenburg_dabei_ist(store):
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Verpackungssteuer erheben", vektor(0.99, 0.14))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    (z,) = store.cluster_stats(MODELL, "1")
    assert z["members"] == 2 and z["cities"] == 2 and z["has_oldenburg"] == 1

    mitglieder = store.cluster_of("os:1", MODELL, "1")
    assert {m["id"] for m in mitglieder} == {"os:1", "ol:1"}
    assert mitglieder[0]["score"] >= mitglieder[-1]["score"], \
        "das typischste Mitglied steht vorn, nicht das zufällig erste"


def test_ein_papier_ausserhalb_hat_keinen_cluster(store):
    idee(store, "os:1", "osnabrueck", "A", "Alleinstellung", vektor(1.0, 0.0))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert store.cluster_of("os:1", MODELL, "1") == []


def test_ein_zweiter_lauf_ersetzt_statt_zu_verdoppeln(store):
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Verpackungssteuer erheben", vektor(0.99, 0.14))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    assert sum(z["members"] for z in store.cluster_stats(MODELL, "1")) == 2


def test_zwei_fassungen_liegen_nebeneinander(store):
    """Wie bei den Annotatoren: Die neue Fassung ersetzt die alte erst, wenn
    die Messung entschieden hat."""
    idee(store, "os:1", "osnabrueck", "A", "Verpackungssteuer einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "B", "Verpackungssteuer erheben", vektor(0.99, 0.14))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")
    cl.build_clusters(store, MODELL, threshold=0.999, version="2")
    assert store.cluster_stats(MODELL, "1") and not store.cluster_stats(MODELL, "2")


# --------------------------------------------------------------- Einbetten

def test_nur_uebertragbares_wird_eingebettet(store, monkeypatch):
    """An einem Bebauungsplan stellt sich „hat das noch jemand?" nicht."""
    store.upsert_batch(Batch(papers=[
        Paper("os:1", "osnabrueck", "Übertragbar"),
        Paper("os:2", "osnabrueck", "Nur hier")]))
    for kennung, transfer in (("os:1", "adaptable"), ("os:2", "local")):
        store.put_annotation("paper", kennung, "classify", "2",
                             {"field": "klima_umwelt", "transfer": transfer,
                              "competence": "council", "instrument": "Etwas tun",
                              "summary": "x"}, "h" + kennung)
    gesehen: list[str] = []
    monkeypatch.setattr(cl, "EMBED_MODEL", MODELL)
    import council.cities.index as index_modul
    monkeypatch.setattr(index_modul, "_embed",
                        lambda texte: (gesehen.extend(texte),
                                       np.ones((len(texte), 2), dtype=np.float32))[1])
    assert cl.embed_ideas(store, MODELL) == 1
    assert len(gesehen) == 1


def test_unveraenderte_ideen_werden_nicht_neu_gerechnet(store, monkeypatch):
    store.upsert_batch(Batch(papers=[Paper("os:1", "osnabrueck", "A")]))
    store.put_annotation("paper", "os:1", "classify", "2",
                         {"field": "klima_umwelt", "transfer": "adaptable",
                          "competence": "council", "instrument": "Etwas tun",
                          "summary": "x"}, "h1")
    import council.cities.index as index_modul
    monkeypatch.setattr(index_modul, "_embed",
                        lambda texte: np.ones((len(texte), 2), dtype=np.float32))
    assert cl.embed_ideas(store, MODELL) == 1
    assert cl.embed_ideas(store, MODELL) == 0, "derselbe Text, derselbe Vektor"


# ------------------------------------------------------------ Gegenrichtung

def test_der_cluster_findet_die_fremden_gegenstuecke(store):
    """„Wie ging dieselbe Sache anderswo aus?" — die Frage am Abend vor der
    Sitzung. Sie braucht nur den Cluster und das Ergebnis je Mitglied."""
    from council.cities.model import AgendaItem, Consultation, Meeting, Outcome

    idee(store, "os:1", "osnabrueck", "Grundsteuer C prüfen",
         "Grundsteuer C einführen", vektor(1.0, 0.0))
    idee(store, "ol:1", "oldenburg", "Einführung der Grundsteuer C",
         "Grundsteuer C prüfen", vektor(0.99, 0.14))
    store.upsert_batch(Batch(
        meetings=[Meeting("os:m:1", "osnabrueck", None, "Rat", "2026-02-01")],
        agenda_items=[AgendaItem("os:a:1", "os:m:1", "Grundsteuer C",
                                 result_raw="verwiesen", outcome=Outcome.REFERRED)],
        consultations=[Consultation("os:c:1", "os:1", agenda_item_id="os:a:1")]))
    cl.build_clusters(store, MODELL, threshold=0.86, version="1")

    fremde = [m for m in store.cluster_of("ol:1", MODELL, "1")
              if m["body_id"] != "oldenburg"]
    assert [m["id"] for m in fremde] == ["os:1"]
    assert (store.outcome_for_paper("os:1") or {}).get("outcome") == "referred", \
        "ohne das Ergebnis beantwortet der Cluster die Frage nicht"


# ------------------------------------------------- Der Putz und seine Grenzen

def _pruefe_mit(monkeypatch, store, antwort: dict, mitglieder: int = 9):
    """Eine Gruppe bauen und den Prüflauf mit fester Modellantwort laufen lassen."""
    import json
    from types import SimpleNamespace
    for i in range(mitglieder):
        idee(store, f"x:{i}", "osnabrueck" if i else "oldenburg",
             f"Vorlage {i}", "Sportförderrichtlinien anpassen", vektor(1.0, i * 0.001))
    cl.build_clusters(store, MODELL, threshold=0.5, version="1")
    monkeypatch.setattr(cl, "text_hash", lambda t: "h")
    from kern import llm
    monkeypatch.setattr(llm, "chat_complete", lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(antwort)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=0.0)))
    return cl.check_clusters(store, MODELL, "1")


def test_hoechstens_ein_drittel_faellt_heraus(monkeypatch, store):
    """Die Sicherung, die den ersten Messlauf gerettet hat.

    Das Modell wählte für eine Gruppe das zu enge Label
    „Klimaschutz-Berichtswesen" und warf danach 9 von 16 Mitgliedern hinaus —
    jedes, das „Konzept" oder „Maßnahmenplan" hieß, obwohl das dieselbe Sache
    in einer anderen Stufe ist. Wer mehr als ein Drittel entfernen will, hat
    die Gruppe nicht geputzt, sondern neu definiert.
    """
    stand = _pruefe_mit(monkeypatch, store,
                        {"label": "zu eng", "drop": [f"x:{i}" for i in range(6)],
                         "reason": "passt nicht"}, mitglieder=9)
    assert stand["dropped"] == 0, "sechs von neun ist kein Putzen mehr"
    assert stand["zu_viel"] == 1
    assert len(store.cluster_of("x:0", MODELL, "1")) == 9, "die Gruppe bleibt ganz"


def test_ein_einzelnes_fremdes_mitglied_faellt_heraus(monkeypatch, store):
    """Der Normalfall: In einer großen Gruppe passt genau eines nicht."""
    stand = _pruefe_mit(monkeypatch, store,
                        {"label": "Sportförderung", "drop": ["x:3"],
                         "reason": "ein anderes Instrument"}, mitglieder=9)
    assert stand["dropped"] == 1
    übrig = {m["id"] for m in store.cluster_of("x:0", MODELL, "1")}
    assert "x:3" not in übrig and len(übrig) == 8


def test_erfundene_kennungen_werden_ignoriert(monkeypatch, store):
    """Was dem Modell nicht vorlag, kann es nicht entfernen — wie bei `fit`."""
    stand = _pruefe_mit(monkeypatch, store,
                        {"label": "x", "drop": ["gibt-es-nicht"], "reason": "…"},
                        mitglieder=9)
    assert stand["dropped"] == 0
    assert len(store.cluster_of("x:0", MODELL, "1")) == 9


def test_die_gruppierung_selbst_bleibt_unangetastet(monkeypatch, store):
    """Schicht 1 trägt keine Meinung: Der Putz steht als Annotation daneben.

    Wer wissen will, warum ein Papier nicht mehr mitzählt, sieht beides
    nebeneinander — und ein besseres Urteil kann das alte ersetzen, ohne die
    Rechnung zu wiederholen.
    """
    _pruefe_mit(monkeypatch, store,
                {"label": "x", "drop": ["x:3"], "reason": "…"}, mitglieder=9)
    roh = store._conn.execute(
        "SELECT COUNT(*) FROM idea_clusters WHERE version='1'").fetchone()[0]
    assert roh == 9, "die gerechnete Gruppe verliert kein Mitglied"
    assert store.annotation("cluster", "1:1", "cluster_check", "1") is not None


def test_der_cron_schritt_rechnet_alle_vier_stufen(monkeypatch):
    """Einbetten, gruppieren, prüfen — und die Haltung.

    Bis 10.09.2026 fehlte die vierte: `stance_all` hing an einem Handaufruf.
    Der Cron hätte neue Vorlagen gruppiert und geprüft, aber nie gefragt, ob
    der Rat die Sache wollte — und kein Test hat `run()` je gerufen, also
    fiel es nicht auf. Hier wird nicht gerechnet, nur gezählt, WAS gerufen
    wird: Ein Schritt, der stumm herausfällt, ist der Fehler, den dieser Test
    verhindert.
    """
    from council.cities import clusters

    gerufen: list[str] = []
    monkeypatch.setattr(clusters, "embed_ideas", lambda *a, **k: gerufen.append("embed") or 3)
    monkeypatch.setattr(clusters, "build_clusters",
                        lambda *a, **k: gerufen.append("build") or {"clusters": 1})
    monkeypatch.setattr(clusters, "check_clusters",
                        lambda *a, **k: gerufen.append("check") or {"checked": 1})
    monkeypatch.setattr(clusters, "stance_all",
                        lambda *a, **k: gerufen.append("stance") or {"annotated": 2})
    zahlen = clusters.run(main=None)
    assert gerufen == ["embed", "build", "check", "stance"], gerufen
    assert zahlen["stance_annotated"] == 2, "die Kennzahlen des vierten Schritts fehlen"
    assert zahlen["embedded"] == 3 and zahlen["check_checked"] == 1
