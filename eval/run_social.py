#!/usr/bin/env python3
"""Social-Karten: der Kartentext und sein Kritiker, je eine Suite.

    python eval/pruefstand.py --suite social-text,kritiker --modell openai/gpt-6-luna --laeufe 2

Beide Suiten bauen den Kontext wie der Betrieb (``social_text.kontext`` aus
``store.agenda_item_material``). **Lokal fehlen die Anlagen-Volltexte**
(``scripts/lokale_daten.py`` lässt sie weg), das Modell sieht hier also nur
die Vorlage — für den Vergleich zweier Modelle ist das gleich, die Zahlen sind
aber nicht die des Betriebs.

**Social-Text** (``social_card_text``). Geschmack prüft kein Modell. Die
Suite prüft, was sich buchstäblich prüfen lässt — mit denselben Netzen, die
auch im Betrieb vor dem Speichern stehen (``kritiker.pruefe``,
``social_text.ueberschrift_pruefen``): keine Zahl, die nicht in der Quelle
steht, keine Wertung, kein vorweggenommenes Ergebnis, kein Aktenzeichen,
Erklärzeile höchstens 240 und Überschrift höchstens 60 Zeichen, gültiges
JSON mit beiden Teilen. Gemessen wird der ERSTE Entwurf: Der Betrieb darf
zweimal ansetzen und verwirft, was durchfällt — ein Modell, das öfter
durchfällt, kostet dort den zweiten Aufruf oder die Karte.

* Hauptkennzahl: Anteil der Punkte, deren erster Entwurf sauber ist.
* Harter Befund: ein INHALTLICHER Mangel (Zahl ohne Beleg, Wertung,
  vorweggenommenes Ergebnis, Aktenzeichen) — in Text oder Überschrift. Länge
  und Form sind weich: Der Betrieb kürzt, das Ergebnis bleibt wahr.

**Kritiker** (``social_critic``). 18 Sätze zu neun echten Punkten: neun, die
gedeckt sind, und neun, in denen genau EINE harte Angabe vertauscht ist —
Antragsteller, Ort, wer zahlt, wer entschieden hat. Die gedeckten sind sechs
gespeicherte Kartentexte, jede Angabe in der Vorlage nachgelesen, dazu drei,
die dort nachgeschärft wurden: Im ersten Lauf verwarf der Kritiker zwei
gespeicherte Texte, und beide Male hatte er recht („prüft seit 18. August",
wo die Vorlage „wird … aufnehmen" sagt; „erfasst nur Ja, Nein und
Enthaltungen", wo sie auch Anwesenheiten nennt) — sie stehen deshalb in
berichtigter Form hier. Zahlen sind dabei die Ausnahme, weil die fängt schon die
Stufe davor. Die eine Zahl-Falle ist der Fall aus dem Kopf von
``council/kritiker.py``: „69 Hektar bis 2027" steht in der Vorlage, aber als
gesetzliches Ziel, nicht als das, was der Plan ausweist — dort ließ der
Kritiker am 30.08.2026 durch.

* Hauptkennzahl: Anteil richtig (gedeckt / nicht gedeckt).
* Harter Befund: ein vertauschter Satz, der als gedeckt durchgeht — er ginge
  ungeprüft auf die Karte. Ein fälschlich verworfener Satz kostet nur die
  Karte.
* Ein Ausfall des Aufrufs lässt ``pruefe_llm`` im Betrieb durch (siehe dort);
  hier zählt er als eigener Befund, nicht als „gedeckt".
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

FAELLE_TEXT = WURZEL / "eval" / "cases_social.json"
FAELLE_KRITIKER = WURZEL / "eval" / "cases_critic.json"

#: Welche Mängel inhaltlich sind (hart) — die übrigen sind Länge und Form.
_INHALT = ("wertet", "nimmt das Ergebnis vorweg", "Aktenzeichen", "Zahl steht nicht")


def _store():
    from council.store import CouncilStore
    return CouncilStore(Path(os.environ.get("COUNCIL_DB") or WURZEL / "data" / "council.sqlite"))


def _kontext(store, ksinr: int, nummer: str) -> str:
    from council import social_text
    material = store.agenda_item_material(ksinr, [nummer])
    if not material:
        raise LookupError(f"{ksinr} {nummer}: nicht in der Ratsdatenbank")
    punkt = material[0]
    anlagen = store.anlagen_fuer(punkt["kvonr"]) if punkt.get("kvonr") else []
    return social_text.kontext(punkt, anlagen)[0]


# --------------------------------------------------------------------------- #
# Kartentext
# --------------------------------------------------------------------------- #

def text_bewerten(fall_id: str, roh: str, ktx: str) -> dict:
    """Erster Entwurf gegen die Netze des Betriebs — rein, offline testbar."""
    from council import kritiker, social_text
    try:
        antwort = json.loads(roh)
        text = social_text._eine_zeile(antwort.get("text"))
        kopf = antwort.get("headline")
    except (json.JSONDecodeError, AttributeError):
        return {"id": fall_id, "maengel": ["kein gültiges JSON"], "hart": [], "text": roh[:200]}
    maengel = kritiker.pruefe(text, ktx) if text else ["leer"]
    _, kopf_mangel = social_text.ueberschrift_pruefen(kopf, ktx)
    if kopf_mangel:
        maengel.append(f"Überschrift: {kopf_mangel}")
    return {"id": fall_id, "maengel": maengel,
            "hart": [m for m in maengel if any(k in m for k in _INHALT)],
            "text": text, "ueberschrift": kopf, "laenge": len(text)}


def lauf_text() -> dict:
    from council import social_text
    from kern import prompts
    store = _store()
    zeilen = []
    try:
        for fall in json.loads(FAELLE_TEXT.read_text(encoding="utf-8")):
            fid = f"{fall['ksinr']} {fall['item_number']}"
            ktx = _kontext(store, fall["ksinr"], fall["item_number"])
            try:
                roh = social_text._antwort(prompts.get("social_card_text_system"),
                                           prompts.render("social_card_text_user", kontext=ktx))
            except social_text.AnbieterFehler as e:
                zeilen.append({"id": fid, "maengel": ["Anbieterfehler"], "hart": [],
                               "fehler": str(e)[:200]})
                continue
            zeilen.append(text_bewerten(fid, roh, ktx))
    finally:
        store.close()
    return {"n_cases": len(zeilen),
            "sauber": sum(1 for z in zeilen if not z["maengel"]),
            "hart": sum(1 for z in zeilen if z["hart"]),
            "zu_lang": sum(1 for z in zeilen if any("zu lang" in m for m in z["maengel"])),
            "fehlgeschlagen": sum(1 for z in zeilen if z.get("fehler")),
            "faelle": zeilen}


# --------------------------------------------------------------------------- #
# Kritiker
# --------------------------------------------------------------------------- #

def lauf_kritiker() -> dict:
    from council import kritiker
    from kern import llm
    store = _store()
    zeilen = []
    ausfall: list[str] = []
    # ``pruefe_llm`` lässt bei einem Ausfall durch; hier soll der Ausfall
    # sichtbar sein, nicht als „gedeckt" zählen.
    vorher = llm.chat_complete

    def merken(**kw):
        try:
            return vorher(**kw)
        except Exception:
            ausfall.append(kw.get("_feature") or "?")
            raise

    llm.chat_complete = merken
    try:
        for fall in json.loads(FAELLE_KRITIKER.read_text(encoding="utf-8")):
            ktx = _kontext(store, fall["ksinr"], fall["item_number"])
            n = len(ausfall)
            gedeckt, grund = kritiker.pruefe_llm(fall["text"], ktx)
            if len(ausfall) > n:
                zeilen.append({"id": fall["id"], "soll": fall["gedeckt"], "ist": None,
                               "richtig": False, "durchgelassen": False, "grund": "Ausfall"})
                continue
            zeilen.append({"id": fall["id"], "soll": fall["gedeckt"], "ist": gedeckt,
                           "richtig": gedeckt == fall["gedeckt"],
                           "durchgelassen": gedeckt and not fall["gedeckt"], "grund": grund})
    finally:
        llm.chat_complete = vorher
        store.close()
    return {"n_cases": len(zeilen),
            "quote": round(sum(z["richtig"] for z in zeilen) / len(zeilen), 4) if zeilen else None,
            "durchgelassen": [z["id"] for z in zeilen if z["durchgelassen"]],
            "zu_unrecht_verworfen": [z["id"] for z in zeilen if z["soll"] and z["ist"] is False],
            "ausfaelle": sum(1 for z in zeilen if z["ist"] is None),
            "faelle": zeilen}


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(WURZEL / ".env")
    wahl = sys.argv[1] if len(sys.argv) > 1 else "text"
    erg = lauf_text() if wahl == "text" else lauf_kritiker()
    for z in erg["faelle"]:
        print(f"  {z['id']:24} {json.dumps({k: v for k, v in z.items() if k != 'id'}, ensure_ascii=False)}")
    print({k: v for k, v in erg.items() if k != "faelle"})
