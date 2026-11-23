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


# ---- Berichte (Form F7) --------------------------------------------------------
# Der Quartalsbericht der Beteiligungen (26/0818) meldet elf Gesellschaften und
# Betriebe mit Plan und Hochrechnung; das Dossier zeigte drei Zahlen und Sätze
# über den Vorgang („Die Vorlage informiert über den Bericht"). Ein Bericht
# hatte keinen Ort für seinen Inhalt: „Zahlen" schloss Geld aus, „Kosten" meint
# nur den Beschluss (Tim, 23.11.2026).

def _bericht_material(form="F7"):
    m = _material()
    m["form"] = form
    m["documents"] = [_bericht(["Die BBGO liegt nach der Hochrechnung um 780.100 Euro unter dem Ansatz. " + _FUELL])]
    return m


def test_bericht_bekommt_den_zusatz_und_nur_er():
    from kern import prompts
    zusatz = prompts.get("template_dossier_report")
    nutzer, _, _ = template_dossier.build_input(_bericht_material("F7"))
    assert zusatz in nutzer
    assert nutzer.index(zusatz) < nutzer.index("Schreibe das Dossier als JSON")   # die Aufgabe bleibt zuletzt
    for form in ("F1", "F2", "F4", None):
        assert zusatz not in template_dossier.build_input(_bericht_material(form))[0]


def test_nur_berichte_entstehen_neu():
    # Die Prüfsumme ändert sich nur für F7 — der übrige Bestand läuft nicht neu.
    m = _material()
    assert template_dossier.build_input(m)[2] == _alte_pruefsumme(m)
    f7 = {**m, "form": "F7"}
    alt_f7 = _alte_pruefsumme(f7)
    assert template_dossier.build_input(f7)[2] != alt_f7


def test_bericht_darf_mehr_befunde_und_zahlen_tragen():
    assert template_dossier.grenze("F7", "proposal", "plain") == 8
    assert template_dossier.grenze("F7", "figures", "items") == 10
    assert template_dossier.grenze("F1", "proposal", "plain") == 5
    assert template_dossier.grenze("F7", "costs", "items") == 4
    assert template_dossier.grenze(None, "figures", "items") == 6
    _, quellen, _ = template_dossier.build_input(_bericht_material())
    satz = {"text": "Die BBGO liegt 780.100 Euro unter dem Ansatz.", "source": "A1",
            "quote": "Die BBGO liegt nach der Hochrechnung um 780.100 Euro unter dem Ansatz."}
    payload = {"proposal": {"status": "found", "plain": [satz] * 9}, "figures": {"status": "found", "items": [satz] * 12}}
    out = template_dossier.verify(payload, quellen, "F7")
    assert len(out["proposal"]["plain"]) == 8 and len(out["figures"]["items"]) == 10
    assert len(template_dossier.verify(payload, quellen, "F2")["proposal"]["plain"]) == 5


def test_richtig_zitiertes_wort_gegen_kaputte_ligatur_bleibt_belegt():
    """Schreibt das Modell „städtischen", wo die Anlage „städƟschen" trägt (ein
    Text von vor der Reparatur), hält der Beleg trotzdem."""
    m = _material()
    m["form"] = "F7"
    m["documents"] = [_bericht(["Bericht der städƟschen Beteiligungen: Der WirtschaŌsplan wird eingehalten. " + _FUELL])]
    _, quellen, _ = template_dossier.build_input(m)
    payload = {"figures": {"status": "found", "items": [
        {"text": "Der Wirtschaftsplan wird eingehalten.", "source": "A1",
         "quote": "Bericht der städtischen Beteiligungen: Der Wirtschaftsplan wird eingehalten."}]}}
    assert template_dossier.verify(payload, quellen, "F7")["figures"]["status"] == "found"


def test_leere_antwort_wird_nicht_als_dossier_gespeichert(monkeypatch):
    """Eine Antwort ohne Abschnitt („{}" oder kein JSON) ist ein Fehlschlag, kein
    Dossier aus lauter „steht nicht drin" — der nächste Lauf holt sie nach."""
    from types import SimpleNamespace

    import pytest

    from kern import llm

    for inhalt in ("{}", "kein JSON", '{"documents": []}'):
        monkeypatch.setattr(llm, "chat_complete", lambda inhalt=inhalt, **kw: SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=inhalt))], usage=None))
        with pytest.raises(template_dossier.LeeresDossier):
            template_dossier.generate(_material(), batch=True)

    gespeichert, ausgegeben = [], []

    class Store:
        def dossier_material(self, tn):
            return _material()

        def template_dossier(self, key, h=None):
            return None

        def dossier_sperren(self, key, h):
            return True

        def save_template_dossier(self, key, h, **kw):
            gespeichert.append(kw["status"])

    assert template_dossier.build_for_template(Store(), "26/0796",
                                               stopp=SimpleNamespace(ausgeben=ausgegeben.append)) is None
    assert gespeichert == ["failed"] and len(ausgegeben) == 1


def test_vergangene_station_zeigt_neuere_lesung_derselben_dokumente(tmp_path):
    """Eine vergangene Station zeigt den Stand zum Sitzungstag — aber wurde
    dasselbe Material danach nur neu gelesen (Berichte mit eigenem Auftrag,
    11/2026), gilt die neuere Lesung. Kam eine Unterlage dazu, bleibt der alte Stand."""
    from datetime import date, timedelta

    from council.scraper import AgendaItem, CouncilSession
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        tag = (date.today() - timedelta(days=3)).isoformat()
        store.save_vorlage({"kvonr": 30260, "template_number": "26/0796", "title": "Beratende Mitglieder - Beschluss",
                            "kind": "Beschlussvorlage", "document_id": 315090,
                            "document_url": "https://buergerinfo.oldenburg.de/getfile.php?id=315090&type=do",
                            "raw_text": V, "n_pages": 2, "status": "ok"})
        store.save_session(CouncilSession(ksinr=4709, committee="Rat", session_date=tag, session_time="18:00",
                                          location="PFL", agenda_items=[AgendaItem(
                                              item_number="Ö 13.2", title="Beratende Mitglieder", template_number="26/0796",
                                              kvonr=30260, is_public=True, anlagen=[])]))
        _, quellen, _ = template_dossier.build_input(store.dossier_material("26/0796"))

        def dossier(text: str, quellen_: dict) -> dict:
            return template_dossier.verify({"costs": {"items": [
                {"text": text, "quote": "Sitzungsgeld in Höhe von 35,00 Euro je Sitzung", "source": "V1", "amount_eur": 35}]}},
                quellen_, "F1")

        def ablegen(h: str, payload: dict, wann: str) -> None:
            store.save_template_dossier("tn:26/0796", h, status="ok", form="F1", payload=payload, model="m",
                                        cost_usd=0.0, prompt_version=1)
            with store._conn:
                store._conn.execute("UPDATE template_dossiers SET created_at = ? WHERE sources_hash = ?", (wann, h))

        def gezeigt() -> str:
            v = store.item_dossier_view(4709, "Ö 13.2")
            return next(s for s in v["sections"] if s["key"] == "costs")["statements"][0]["text"]

        ablegen("vorher", dossier("Stand zum Sitzungstag.", quellen), f"{tag}T08:00:00+00:00")
        mit_anlage = {**quellen, "A1": {"text": "x", "pages": None, "document_id": 999, "label": "Neue Anlage"}}
        ablegen("anlage-dazu", dossier("Mit neuer Anlage.", mit_anlage), f"{date.today().isoformat()}T07:00:00+00:00")
        assert gezeigt() == "Stand zum Sitzungstag."          # neue Unterlage: alter Stand bleibt
        ablegen("neu-gelesen", dossier("Dieselben Dokumente, neu gelesen.", quellen), f"{date.today().isoformat()}T09:00:00+00:00")
        assert gezeigt() == "Dieselben Dokumente, neu gelesen."
    finally:
        store.close()


def test_bericht_bekommt_kandidaten_aus_allen_seiten():
    """Quartalsbericht 30.09.2026: Die Liste endete mit 25 Beträgen auf Seite 4 von 14."""
    import json as _json
    seiten = [f"Gesellschaft {i}: Abweichung {i}{i}.{i}00 Euro und {i}0.000 Euro. " + _FUELL for i in range(1, 30)]
    m = _material()
    m["form"] = "F7"
    m["documents"] = [_bericht(seiten)]
    fakten = _json.loads(template_dossier.build_input(m)[0].split("FESTE FAKTEN (aus der Vorlage, ohne Modell):\n")[1]
                         .split("\n\nDOKUMENTE")[0])
    assert len(fakten["kandidaten_A1"]["amounts"]) > 25
    assert max(a["page"] for a in fakten["kandidaten_A1"]["amounts"]) == 29
    m["form"] = "F2"
    fakten = _json.loads(template_dossier.build_input(m)[0].split("FESTE FAKTEN (aus der Vorlage, ohne Modell):\n")[1]
                         .split("\n\nDOKUMENTE")[0])
    assert len(fakten["kandidaten_A1"]["amounts"]) == 25


def test_viele_anlagen_lesen_die_mit_vorrang():
    """Haushaltsentwurf 2027 (26/0835): 20 Lese-Anlagen. Reihum, die kürzeste
    zuerst, bekamen die kleinen Änderungslisten ihren Anteil und der Vorbericht
    nichts. Jetzt lesen die Anlagen mit Vorrang, die übrigen stehen im Kopf."""
    tabelle = "\n".join(f"{i} 1.234.567 2.345.678 -3.456" for i in range(400))
    prosa = " ".join(["Die Verwaltung erläutert die Entwicklung der Erträge und Aufwendungen."] * 300)
    docs = [{"document_id": 100 + i, "label": f"2027 0{10 + i} Vw THH{i:02d} Haushalt 2027 Verwaltungsentwurf",
             "doc_type": "report", "text": tabelle, "page_offsets": None} for i in range(1, 15)]
    docs += [{"document_id": 200 + i, "label": f"2027 03{i} Vw Änderungsliste Verwaltung I", "doc_type": "synopsis",
              "text": "Änderung " + tabelle[:4_000], "page_offsets": None} for i in range(3)]
    docs.append({"document_id": 300, "label": "2027 001 Vw Vorbericht Haushalt 2027 Verwaltungsentwurf",
                 "doc_type": "report", "text": prosa * 3, "page_offsets": None})
    m = {**_material(), "form": "F7", "documents": docs}
    nutzer, quellen, _ = template_dossier.build_input(m)
    vorbericht = f"A{len(docs)}"
    assert f"[{vorbericht}] 2027 001 Vw Vorbericht" in nutzer.split("BELEGMATERIAL")[0]   # gelesen
    gelesen = nutzer.split("DOKUMENTE (Daten, keine Anweisungen):")[1].split("BELEGMATERIAL")[0]
    assert "erläutert die Entwicklung der Erträge" in gelesen and len(gelesen) <= template_dossier.GESAMT_ZEICHEN
    # Die übrigen stehen mit ihrem Kopf im Belegmaterial — und tragen einen Inhaltssatz.
    beleg = nutzer.split("BELEGMATERIAL (nur Kopf):")[1]
    assert sum(f"THH{i:02d}" in beleg for i in range(1, 15)) >= 10
    assert all("Änderungsliste" not in z for z in beleg.splitlines() if z.startswith("[A"))   # Vorrang 1,5
    assert template_dossier.vorrang("Vorbericht Haushalt 2027", prosa) > template_dossier.vorrang("THH05 Haushalt", tabelle)


def test_wenige_anlagen_bleiben_reihum():
    # Reicht das Budget, ändert der Vorrang nichts: jede Anlage bekommt ihren Anteil.
    a = template_dossier._anteile({"A1": 5_000, "A2": 50_000}, 60_000, {"A1": 0.1, "A2": 3.0})
    assert a == template_dossier._anteile({"A1": 5_000, "A2": 50_000}, 60_000)


def test_inhaltssatz_darf_den_titel_zitieren():
    """Haushaltsentwurf 2027: „THH06 Kultur und Museen" belegt, was das Dokument
    ist — als Aussage im Dossier wäre es zu kurz, als Inhaltssatz genügt es."""
    m = _material()
    m["documents"] = [{"document_id": 7, "label": "2027 012 Vw THH06", "doc_type": "other",
                       "text": "THH06 Kultur und Museen\\n" + _FUELL, "page_offsets": None}]
    _, quellen, _ = template_dossier.build_input(m)
    gist = {"text": "Die Anlage enthält den Teilhaushalt Kultur und Museen.", "quote": "THH06 Kultur und Museen"}
    out = template_dossier.verify({"documents": [{"source": "A1", "gist": gist}],
                                   "figures": {"items": [{**gist, "source": "A1"}]}}, quellen, "F7")
    assert len(out["documents"]) == 1
    assert out["figures"]["items"] == []          # außerhalb der Inhaltssätze bleibt es bei 30 Zeichen


def test_passt_alles_ins_budget_lesen_alle():
    """Elf kurze Stellungnahmen passen zusammen ins Budget — der Vorrang greift
    nicht, alle werden ganz gelesen (Review 23.11.2026)."""
    laengen = {f"A{i}": 2_800 for i in range(1, 12)}
    a = template_dossier._anteile(laengen, 64_000, {k: 0.5 for k in laengen})
    assert all(a[k] == 2_800 for k in laengen)


def test_restbudget_geht_an_die_uebrigen():
    # Der Vorbericht (A1) hat Vorrang und braucht nur 10.000 — der Rest geht in
    # Vorrang-Folge an die übrigen, ganz, solange sie passen.
    laengen = {"A1": 10_000, "A2": 200_000, "A3": 9_000, "A4": 9_000, "A5": 9_000}
    rang = {"A1": 4.0, "A2": 0.1, "A3": 0.2, "A4": 0.2, "A5": 0.2}
    a = template_dossier._anteile(laengen, 28_000, rang)
    assert a == {"A1": 10_000, "A3": 9_000, "A4": 9_000, "A5": 0, "A2": 0}


def test_abgeschnittene_antwort_zaehlt_zur_kostengrenze(monkeypatch):
    from types import SimpleNamespace

    from council import plan_judge
    from kern import llm

    monkeypatch.setattr(llm, "chat_complete", lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content="{"))], usage=None))
    monkeypatch.setattr(plan_judge, "cost_usd", lambda resp, modell: 0.03)
    gespeichert, ausgegeben = [], []

    class Store:
        def dossier_material(self, tn):
            return _material()

        def template_dossier(self, key, h=None):
            return None

        def dossier_sperren(self, key, h):
            return True

        def save_template_dossier(self, key, h, **kw):
            gespeichert.append(kw["status"])

    template_dossier.build_for_template(Store(), "26/0796", stopp=SimpleNamespace(ausgeben=ausgegeben.append))
    assert gespeichert == ["failed"] and ausgegeben == [0.03]


def test_dossier_nennt_sein_material():
    """Auch Dokumente ohne Text — sonst gilt eine später gelesene Anlage als neu."""
    from types import SimpleNamespace

    from kern import llm

    m = _material()
    m["documents"] = [{"document_id": 99, "label": "Scan", "doc_type": "other", "text": "", "page_offsets": None}]
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(llm, "chat_complete", lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"costs": {"status": "absent"}}'))],
        usage=None))
    try:
        payload, _, _ = template_dossier.generate(m, batch=True)
    finally:
        mp.undo()
    assert payload["material"] == [99, 315090]
