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
