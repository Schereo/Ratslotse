"""Fördervorhaben ↔ Ratsvorlagen (council/foerder_vorlagen.py).

Die Fälle sind die, an denen die Regeln am 24.09.2026 gegen die ganze
Ratsdatenbank eingestellt wurden — Titel und Beträge echt, Texte gekürzt.
"""
from pathlib import Path
import sys

from council import foerder_vorlagen as fv


def _vorhaben(title, amount, start, end=None, sid="x"):
    return {"source": "efre", "source_id": sid, "title": title, "amount_granted": amount,
            "start": start, "end": end}


def _fuell(n):
    """n Vorlagen, die ein Wort häufig machen."""
    return [{"template_number": f"22/{900 + i}", "title": "Irgendwas", "raw_text": "Neue Technologien"}
            for i in range(n)]


ABSCHLUSS = {"template_number": "23/0896", "title": "Abschlussbericht Förderprogramm Perspektive Innenstadt -Bericht",
             "raw_text": "Temporäre Eislaufbahn auf dem Schlossplatz 99.000,00 € Zuschuss"}


def test_betrag_und_seltenes_wort():
    v = fv.verknuepfe([_vorhaben("Temporäre Eislaufbahn in der Oldenburger Innenstadt", 99000, "2022-07-15")],
                      [ABSCHLUSS])
    assert [(x.template_number, x.basis) for x in v] == [("23/0896", "amount")]


def test_betrag_allein_reicht_nicht():
    """Gleicher Betrag, aber nur ein häufiges Wort — Smart-City-Fall."""
    vorlagen = _fuell(20) + [{"template_number": "21/0138", "title": "Bewerbung als Smart City Modellprojekt",
                              "raw_text": "Neue Technologien … 100.000 €"}]
    assert fv.verknuepfe([_vorhaben("Neue Technologien", 100000, "2021-01-01")],
                         vorlagen) == []


def test_betrag_grenzen():
    m = fv._betrag_muster(90000)
    assert m.search("für 90.000 € bewilligt") and m.search("90.000,00 Euro")
    assert not m.search("190.000 €") and not m.search("90.000,50") and not m.search("90.000.000")
    assert fv._betrag_muster(14181.75).search("14.181,75 €")


def test_titel_im_titel_und_zeitfenster():
    wwnw = {"template_number": "21/0437", "title": "Wärmewende Nordwest - Bericht", "raw_text": ""}
    pflaster = {"template_number": "23/0262", "title": "Aufpflasterungen an der Peterstraße", "raw_text": ""}
    v = fv.verknuepfe([
        _vorhaben("Verbundvorhaben Wärmewende Nordwest: Digitalisierung", 810283, "2021-04-16", "2025-12-31", "a"),
        _vorhaben("KSI: Aufpflasterungen der getrennten Geh- und Radwege, Peterstraße", 429000, "2026-06-01", sid="b"),
    ], [wwnw, pflaster])
    assert [(x.source_id, x.template_number, x.basis) for x in v] == [("a", "21/0437", "title")]


def test_antraege_ohne_eigene_programme():
    assert fv.ist_antrag("Förderantrag Skatehalle Oldenburg - Beschluss")
    assert fv.ist_antrag("Bäderbetrieb (BBO): Teilnahme Stadt Oldenburg am Bundesprogramm „Sanierung …“")
    assert not fv.ist_antrag("Förderprogramm Photovoltaik: Richtlinienänderung - Beschluss")
    assert not fv.ist_antrag("Änderung der Förderrichtlinie \"Förderprogramm energetische Altbausanierung\"")
    assert not fv.ist_antrag("Sanierungsgebiet Mittlere Innenstadt Übernahme des nicht durch Städtebaufördermittel …")


def test_endpunkt_traegt_vorlagen_und_antraege(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
    from app.routers.council import haushalt_foerdermittel
    from council import foerdermittel as fm
    from council import herkunft
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        store._conn.executemany(
            "INSERT INTO council_templates (kvonr, template_number, title, raw_text, fetched_at) "
            "VALUES (?,?,?,?,'2026-09-24')",
            [(1, "23/0896", ABSCHLUSS["title"], ABSCHLUSS["raw_text"]),
             (2, "25/0893", "Förderantrag Skatehalle Oldenburg - Beschluss", "")])
        store.save_foerdermittel("efre", "2014-2020", [fm.Vorhaben(
            source="efre", source_id="h1", recipient="Stadt Oldenburg", recipient_key="city",
            title="Temporäre Eislaufbahn in der Oldenburger Innenstadt", summary=None, funder="EU",
            program="EFRE 2014-2020", amount_total=None, amount_granted=99000.0,
            start="2022-07-15", end="2023-03-31")], list_as_of=None, list_url="https://example.org/l.xlsx",
            herkunft=herkunft.Herkunft(kind="eu", probe=[fm.PROBE_EU], url="https://example.org/l.xlsx",
                                       label="Liste"))
        vorhaben = store.get_foerdermittel()
        vorlagen = [dict(r) for r in store._conn.execute(
            "SELECT template_number, title, raw_text FROM council_templates")]
        store.save_foerder_verweise(fv.verknuepfe(vorhaben, vorlagen))
        a = haushalt_foerdermittel(_user={}, store=store)
        assert [t["template_number"] for t in a["rows"][0]["templates"]] == ["23/0896"]
        assert [t["template_number"] for t in a["applications"]] == ["25/0893"]
    finally:
        store.close()
