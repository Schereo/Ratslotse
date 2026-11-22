"""Texte der Anlagen an Tagesordnungspunkten nachladen und einordnen
(docs/plan-vorlagen-aufbereiten.md, PR 6).

Bis 11/2026 hatte eine Punkt-Anlage nur dann Text, wenn sie ein
Dringlichkeitsantrag war oder der MCP-Server sie auf Zuruf geladen hatte
(lokal 11 von 1.250). Gerade Änderungsanträge hängen aber am Punkt, nicht an
der Vorlage — und manche verraten sich erst im Text („2026-10-31 Reduzierung
Anzahl beratende Mitglieder" ist ein Änderungsantrag der Grünen).

Geladen wird für kommende und jüngst vergangene Sitzungen, höchstens ``limit``
PDFs je Lauf, eines je Sekunde. Ein geladener Text überlebt das Neu-Einlesen
der Sitzung (``save_session`` übernimmt ihn je URL); der Steckbrief steht
unter der getfile-Kennung in ``council_documents``.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from council import document_types, unterlagen_seiten, vorlagen
from council.parties import parties_in_text

MIN_TEXT = 50


def steckbrief(label: str | None, seiten: list[str], text: str) -> dict:
    """Art, Antragsteller, Seiten, Scan, Seitenanfänge — aus geladenem Text."""
    return {
        "doc_type": document_types.classify(label, text),
        "applicants": parties_in_text(label) or parties_in_text(text[:4000]),
        "n_pages": len(seiten),
        "is_scan": len(text.strip()) < MIN_TEXT,
        "page_offsets": unterlagen_seiten.anchor_offsets(seiten, text) if text.strip() else None,
        "text_hash": unterlagen_seiten.text_hash(text),
    }


def nachladen(store, *, tage_zurueck: int = 7, limit: int = 30, pause: float = 1.0) -> dict:
    seit = (date.today() - timedelta(days=tage_zurueck)).isoformat()
    offen = store.punkt_anlagen_ohne_text(seit)
    gesehen: set[int] = set()
    geladen = fehler = antraege = 0
    for a in offen:
        if a["document_id"] in gesehen or geladen + fehler >= limit:
            continue
        gesehen.add(a["document_id"])
        try:
            seiten = vorlagen.pdf_seiten_laden(a["url"])
        except Exception as exc:  # noqa: BLE001 — ein PDF kippt nicht den Lauf
            fehler += 1
            print(f"  Punkt-Anlage {a['document_id']}: {exc!r}", flush=True)
            continue
        text = "\n".join(seiten)
        store.set_punkt_anlagentext(a["url"], text if len(text.strip()) >= MIN_TEXT else "")
        sb = steckbrief(a["label"], seiten, text)
        store.save_document_profile(a["document_id"], **sb)
        geladen += 1
        antraege += sb["doc_type"] in ("amendment", "motion", "report_request")
        time.sleep(pause)
    return {"offen": len({a["document_id"] for a in offen}), "geladen": geladen,
            "antraege": antraege, "fehler": fehler}
