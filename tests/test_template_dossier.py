"""Dossier je Vorlage (council/template_dossier.py) — ohne Netz, Modell gemockt."""
from __future__ import annotations

from council import dossier_harvest, template_dossier

V = ("Beschlussvorschlag:\nDen Ausschüssen gehören je fünf beratende Mitglieder an.\n \nAnlass:\n"
     "Die beratenden Mitglieder erhalten ein Sitzungsgeld in Höhe von 35,00 Euro je Sitzung.\n"
     "Ausdruck vom: 22.10.2026\nSeite: 2/2\nNach der Konstituierung des Jugendparlaments entscheidet der Rat "
     "über ein sechstes Mitglied. Es entstehen keine weiteren Kosten für die Stadt.")


def _material():
    return {"template": {"template_number": "26/0796", "title": "Beratende Mitglieder - Beschluss", "raw_text": V,
                         "proposed_decision": "Den Ausschüssen gehören je fünf beratende Mitglieder an.",
                         "office": "Büro des Oberbürgermeisters", "document_id": 315090},
            "documents": [], "form": "F1"}


def test_form_ohne_modell():
    assert dossier_harvest.form("Bebauungsplan 837 - Satzungsbeschluss", "Beschlussvorlage", []) == "F5"
    assert dossier_harvest.form("Jahresabschluss 2025 - Beschluss", "Beschlussvorlage", []) == "F4"
    assert dossier_harvest.form("Kommunales Toilettenkonzept - Sachstand - Bericht", "Berichtsvorlage", []) == "F7"
    assert dossier_harvest.form("Satzung zur Änderung der Entschädigungssatzung - Beschluss", None, []) == "F3"
    assert dossier_harvest.form("Widmung der Straße Pellwormer Weg - Beschluss", None, []) == "F1"


def test_kandidaten_mit_seite():
    from council import unterlagen_seiten
    k = dossier_harvest.candidates(V, unterlagen_seiten.template_page_offsets(V))
    assert {"value": "35,00 Euro", "page": 1} in k["amounts"]
    assert any(d["value"] == "22.10.2026" for d in k["dates"])


def test_eingabe_mit_seitenmarken_und_fakten():
    nutzer, quellen, h = template_dossier.build_input(_material())
    assert "— [V1] Seite 2 —" in nutzer and "FESTE FAKTEN" in nutzer and "Büro des Oberbürgermeisters" in nutzer
    assert quellen["V1"]["pages"] and len(quellen["V1"]["pages"]) == 2
    assert h == template_dossier.build_input(_material())[2]   # stabil für den Cache und die Geschichte


def test_pruefung_haelt_belegtes_und_markiert_status():
    _, quellen, _ = template_dossier.build_input(_material())
    payload = {
        "proposal": {"status": "found", "plain": [{"text": "Je Ausschuss sollen fünf beratende Mitglieder dazukommen.",
                                                   "quote": "Den Ausschüssen gehören je fünf beratende Mitglieder an.", "source": "V1", "page": 1}]},
        "costs": {"status": "found", "items": [
            {"text": "Das Sitzungsgeld beträgt 35 Euro je Sitzung.", "quote": "Sitzungsgeld in Höhe von 35,00 Euro je Sitzung",
             "source": "V1", "page": 2, "amount_eur": 35, "recurrence": "unknown"},
            {"text": "Es kostet 99 Euro.", "quote": "Sitzungsgeld in Höhe von 35,00 Euro je Sitzung", "source": "V1", "amount_eur": 99}]},
        "changes": {"status": "found", "items": [{"text": "erfunden", "quote": "Dieser Satz steht nirgends in der Vorlage drin", "source": "V1"}]},
        "next": {"status": "found", "dates": [], "open": [{"text": "Über ein sechstes Mitglied soll der Rat nach dem Jugendparlament entscheiden.",
                                                          "quote": "Nach der Konstituierung des Jugendparlaments entscheidet der Rat über ein sechstes Mitglied",
                                                          "source": "V1"}]},
        "affected": {"status": "absent"},
        "documents": [{"source": "A7", "gist": {"text": "x", "quote": "y", "source": "A7"}}],
    }
    out = template_dossier.verify(payload, quellen, "F1")
    assert out["proposal"]["status"] == "found" and out["proposal"]["plain"][0]["page"] == 1
    assert len(out["costs"]["items"]) == 1 and out["costs"]["items"][0]["amount_eur"] == 35
    assert out["costs"]["items"][0]["page"] == 1                   # Seite berichtigt (Zitat steht auf S. 1)
    assert out["changes"]["status"] == "unsupported"              # gefunden, nicht belegbar — nie „steht nicht drin"
    assert out["affected"]["status"] == "absent"
    assert out["next"]["open"][0]["source"] == "V1"
    assert out["documents"] == []                                  # Anlage ohne Text: still übergangen
    assert any(d["reason"] == "Zitat steht nicht wörtlich in der Quelle" for d in out["dropped"])


def test_ansicht_mit_beleg_seite_und_pdf_sprung(tmp_path):
    from datetime import date, timedelta

    from council.scraper import AgendaItem, CouncilSession
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        tag = (date.today() + timedelta(days=5)).isoformat()
        store.save_vorlage({"kvonr": 30260, "template_number": "26/0796", "title": "Beratende Mitglieder - Beschluss",
                            "kind": "Beschlussvorlage", "document_id": 315090,
                            "document_url": "https://buergerinfo.oldenburg.de/getfile.php?id=315090&type=do",
                            "raw_text": V, "n_pages": 2, "status": "ok"})
        store.save_session(CouncilSession(ksinr=4709, committee="Rat", session_date=tag, session_time="18:00",
                                          location="PFL", agenda_items=[AgendaItem(
                                              item_number="Ö 13.2", title="Beratende Mitglieder", template_number="26/0796",
                                              kvonr=30260, is_public=True, anlagen=[])]))
        _, quellen, h = template_dossier.build_input(store.dossier_material("26/0796"))
        payload = template_dossier.verify({"costs": {"items": [
            {"text": "Das Sitzungsgeld beträgt 35 Euro je Sitzung.", "quote": "Sitzungsgeld in Höhe von 35,00 Euro je Sitzung",
             "source": "V1", "page": 1, "amount_eur": 35, "recurrence": "yearly"}]}}, quellen, "F1")
        store.save_template_dossier("tn:26/0796", h, status="ok", form="F1", payload=payload, model="m",
                                    cost_usd=0.001, prompt_version=1)
        v = store.item_dossier_view(4709, "Ö 13.2")
        kosten = next(s for s in v["sections"] if s["key"] == "costs")
        a = kosten["statements"][0]
        assert a["list_no"] == 1 and a["url"].endswith("#page=1") and a["doc_label"] == "Vorlage 26/0796"
        # Wächter (Plan § 3.4): kein Beleg ohne Dokument, keiner auf die Startseite oder vo0050.
        for sec in v["sections"]:
            for x in sec["statements"]:
                assert x["url"] and "getfile.php?id=" in x["url"] and "vo0050" not in x["url"]
        assert store.dossier_cost_label("26/0796") == "35 € jährlich"
        assert store.dossier_lines(4709, "Ö 13.2") == ["Was es kostet: Das Sitzungsgeld beträgt 35 Euro je Sitzung. (Vorlage 26/0796, S. 1)"]
    finally:
        store.close()


def test_kein_ersatzmodell_im_lauf(monkeypatch):
    """Das Ersatzmodell hielt das Gold-Tor nicht (83 % < 85 %) — der Lauf wartet
    lieber auf den nächsten Takt, als schlechter zu schreiben."""
    from types import SimpleNamespace

    from kern import llm

    gesehen = {}

    def fake(**kw):
        gesehen.update(kw)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="{}"))],
                               usage=None)

    monkeypatch.setattr(llm, "chat_complete", fake)
    m = {"template": {"template_number": "26/0001", "title": "T", "raw_text": V, "document_id": 1,
                      "office": None, "proposed_decision": None}, "form": "F1", "documents": []}
    try:
        template_dossier.generate(m, batch=True)
    except Exception:  # noqa: BLE001 — nur der Aufruf interessiert hier
        pass
    assert gesehen["_ersatz"] == [] and gesehen["_geduld"] is True


# --- Lange Anlagen (Tim, 14.11.2026: Aktionsplan, 4 % gelesen) -------------------

def _bericht(seiten: list[str]) -> dict:
    text, offsets = "", []
    for s in seiten:
        offsets.append(len(text))
        text += s + "\n"
    return {"document_id": 1, "label": "Aktionsplan", "doc_type": "report", "text": text, "page_offsets": offsets}


_FUELL = " ".join(["Die Fachberatungsstellen arbeiten seit Jahren eng zusammen."] * 8)


def _langer_bericht() -> dict:
    seiten = ["Aktionsplan gegen Gewalt", "Impressum Herausgegeben von der Stadt " + _FUELL,
              "Inhalt Grußwort ........................ 1\n1 Einleitung ........ 3\n2 Ergebnisse ......... 9\n"
              "3 Maßnahmen ........ 20\n4 Anhang ........ 40\n" + _FUELL,
              "1 Vorwort des Oberbürgermeisters Liebe Lesende, " + _FUELL]
    seiten += [f"Seite {i}: " + _FUELL for i in range(5, 40)]
    seiten[24] = "Maßnahme 12: Das Schutzhaus Hanna erhält 14 weitere Plätze, Kosten 250.000 Euro bis Ende 2027. " + _FUELL
    return _bericht(seiten)


def test_anteile_reihum_kuerzeste_zuerst():
    a = template_dossier._anteile({"A1": 3_000, "A2": 200_000, "A3": 50_000}, 100_000)
    assert a["A1"] == 3_000                                   # die kurze ganz
    assert a["A3"] == 48_500 and a["A2"] == 48_500            # den Rest teilen sich die übrigen
    groß = template_dossier._anteile({"A1": 500_000}, 100_000)
    assert groß["A1"] == template_dossier.ANLAGE_MAX          # nie mehr als der Deckel
    assert template_dossier._anteile({}, 100_000) == {}


def test_vorspann_nur_vorn():
    assert template_dossier._ist_vorspann("Aktionsplan", 1, 40)
    assert template_dossier._ist_vorspann("Inhalt 1 Einleitung ....... 3\n2 Ergebnisse ....... 9\n3 A ....... 5\n4 B ....... 7\n" + _FUELL, 3, 40)
    assert template_dossier._ist_vorspann("2 Jürgen Krogmann Oberbürgermeister Vorwort der Gleichstellungsbeauftragten " + _FUELL, 4, 40)
    assert not template_dossier._ist_vorspann("Vorwort " + _FUELL, 30, 40)    # mitten im Dokument kein Vorspann
    assert not template_dossier._ist_vorspann(_FUELL, 4, 40)


def test_lange_anlage_ohne_vorspann_mit_gewichtigen_seiten_und_luecken():
    d = _langer_bericht()
    block = template_dossier._seitenauswahl("A1", d["text"], d["page_offsets"], 6_000, frozenset({"schutzhaus"}))
    assert "Seite 25 —" in block and "Schutzhaus Hanna" in block           # Maßnahme mit Betrag und Termin
    assert "Impressum" not in block and "Vorwort" not in block and "......" not in block
    assert "nicht gelesen …]" in block                                     # Lücken stehen da
    nummern = [int(n) for n in __import__("re").findall(r"Seite (\d+) —", block)]
    assert nummern == sorted(nummern) and len(block) <= 6_000 + 400


def _alte_pruefsumme(m: dict) -> str:
    import hashlib, json
    from kern import foreign_text
    grundlage = [foreign_text.defuse(V)[0], [d["text"] for d in m["documents"]], "F1", template_dossier.PROMPT_VERSION]
    return hashlib.sha256(json.dumps(grundlage, ensure_ascii=False).encode()).hexdigest()[:16]


def test_ohne_lese_anlage_bleibt_die_pruefsumme():
    # Vorlagen ohne Lese-Anlage: kein Neulauf für den Bestand.
    m = _material()
    assert template_dossier.build_input(m)[2] == _alte_pruefsumme(m)
    m["documents"] = [{**_bericht(["Fotos " + _FUELL]), "doc_type": "presentation"}]
    assert template_dossier.build_input(m)[2] == _alte_pruefsumme(m)


def test_kurze_anlage_steht_ganz_da_mit_eigenen_kandidaten():
    m = _material()
    m["documents"] = [_bericht(["Seite eins " + _FUELL, "Am 01.03.2027 kostet es 4.500 Euro. " + _FUELL])]
    nutzer, quellen, h = template_dossier.build_input(m)
    assert "— [A1] Seite 1 —" in nutzer and "— [A1] Seite 2 —" in nutzer and "nicht gelesen" not in nutzer
    assert '"kandidaten_A1"' in nutzer and '"value": "4.500 Euro"' in nutzer
    assert h != _alte_pruefsumme(m)            # neue Eingabe → einmal neu erzeugt


def test_lange_anlage_wird_weiter_gelesen_und_neu_erzeugt():
    m = _material()
    m["documents"] = [_langer_bericht()]
    nutzer, quellen, h = template_dossier.build_input(m)
    assert "Schutzhaus Hanna" in nutzer                       # Seite 25 — früher nach 12.000 Zeichen abgeschnitten
    assert len(nutzer) > template_dossier.ANLAGE_ZEICHEN
    assert quellen["A1"]["text"] == m["documents"][0]["text"]  # belegt wird gegen die GANZE Anlage
    # Kandidaten nur von gelesenen Seiten, mit ihrer Seite.
    assert {"value": "250.000 Euro", "page": 25} in __import__("json").loads(
        nutzer.split("FESTE FAKTEN (aus der Vorlage, ohne Modell):\n")[1].split("\n\nDOKUMENTE")[0])["kandidaten_A1"]["amounts"]
    alt = template_dossier.build_input({**m, "documents": [{**m["documents"][0], "text": m["documents"][0]["text"][:5_000]}]})[2]
    assert h != alt
