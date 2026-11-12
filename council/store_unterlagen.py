"""Unterlagen: Steckbriefe je Dokument und die Unterlagen eines Punkts über
alle Stationen (docs/plan-vorlagen-aufbereiten.md, § 3.1, PR 6).

Alles hängt an der getfile-Kennung (``document_id``) — Vorlagen-PDF,
Vorlagen-Anlage und Punkt-Anlage gleichermaßen. ``council_agenda_attachments``
wird bei jedem Abgleich neu geschrieben; was am Dokument hängen bleiben soll,
steht deshalb hier in ``council_documents``.
"""
from __future__ import annotations

import json
from datetime import datetime, UTC

from council.store_basis import StoreBasis


class UnterlagenMixin(StoreBasis):

    def save_document_profile(self, document_id: int, doc_type: str, *, applicants: list[str] | None = None,
                              n_pages: int | None = None, is_scan: bool = False,
                              page_offsets: list[int] | None = None, text_hash: str | None = None) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_documents (document_id, doc_type, applicants, n_pages, is_scan, "
                "page_offsets, text_hash, classified_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(document_id) DO UPDATE SET doc_type = excluded.doc_type, "
                "applicants = excluded.applicants, n_pages = COALESCE(excluded.n_pages, n_pages), "
                "is_scan = excluded.is_scan, "
                "page_offsets = COALESCE(excluded.page_offsets, page_offsets), "
                "text_hash = COALESCE(excluded.text_hash, text_hash), classified_at = excluded.classified_at",
                (int(document_id), doc_type, json.dumps(applicants or [], ensure_ascii=False), n_pages,
                 int(bool(is_scan)), json.dumps(page_offsets) if page_offsets else None, text_hash,
                 datetime.now(UTC).isoformat(timespec="seconds")))

    def document_profiles(self, ids: list[int]) -> dict[int, dict]:
        ids = sorted({int(i) for i in ids if i})
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        out = {}
        for r in self._conn.execute(f"SELECT * FROM council_documents WHERE document_id IN ({ph})", ids):
            d = dict(r)
            d["applicants"] = json.loads(d["applicants"] or "[]")
            d["page_offsets"] = json.loads(d["page_offsets"]) if d["page_offsets"] else None
            out[d["document_id"]] = d
        return out

    def punkt_anlagen_ohne_text(self, seit: str) -> list[dict]:
        """Punkt-Anlagen kommender und jüngster Sitzungen, deren Text noch nie
        geladen wurde (``raw_text IS NULL``; ``""`` heißt „geladen, aber Scan")."""
        return [dict(r) for r in self._conn.execute(
            "SELECT DISTINCT aa.document_id, aa.label, aa.url FROM council_agenda_attachments aa "
            "JOIN council_sessions s ON s.ksinr = aa.ksinr "
            "WHERE s.session_date >= ? AND aa.raw_text IS NULL AND aa.document_id IS NOT NULL "
            "AND aa.label != 'Vorlage' ORDER BY s.session_date DESC", (seit,))]

    def set_punkt_anlagentext(self, url: str, text: str) -> None:
        """Den Text einer Punkt-Anlage setzen — an jeder Zeile mit dieser URL.
        ``save_session`` übernimmt ihn beim nächsten Abgleich (je URL)."""
        with self._conn:
            self._conn.execute("UPDATE council_agenda_attachments SET raw_text = ? WHERE url = ?", (text, url))

    def item_documents(self, ksinr: int, item_number: str) -> list[dict]:
        """Alle Unterlagen eines Punkts über alle Stationen seiner Vorlage:
        das Vorlagen-PDF, die Anlagen an der Vorlage und an jedem Punkt, an dem
        sie beraten wird — je Dokument einmal, mit Steckbrief und dem Datum,
        an dem es zuerst an einem Punkt auftauchte."""
        punkt = self._conn.execute(
            "SELECT template_number FROM council_agenda_items WHERE ksinr = ? AND item_number = ?",
            (int(ksinr), item_number)).fetchone()
        if not punkt:
            return []
        tn = (punkt["template_number"] or "").strip()
        docs: dict[int, dict] = {}

        def merke(did: int | None, label: str | None, url: str | None, quelle: str, datum: str | None = None) -> None:
            if not did:
                return
            d = docs.setdefault(int(did), {"document_id": int(did), "label": label or "Dokument",
                                           "url": url, "source": quelle, "first_seen": datum})
            if datum and (not d["first_seen"] or datum < d["first_seen"]):
                d["first_seen"] = datum

        if tn:
            base = "/".join(tn.split("/")[:2])
            v = self._conn.execute(
                "SELECT kvonr, document_id, document_url FROM council_templates WHERE template_number IN (?, ?) "
                "ORDER BY (template_number = ?) DESC, kvonr DESC LIMIT 1", (tn, base, tn)).fetchone()
            if v:
                merke(v["document_id"], f"Vorlage {tn}", v["document_url"], "template")
                for a in self._conn.execute(
                        "SELECT document_id, label, url FROM council_attachments WHERE kvonr = ?", (v["kvonr"],)):
                    merke(a["document_id"], a["label"], a["url"], "template_attachment")
            stationen = self._conn.execute(
                "SELECT aa.document_id, aa.label, aa.url, s.session_date FROM council_agenda_attachments aa "
                "JOIN council_agenda_items a ON a.ksinr = aa.ksinr AND a.item_number = aa.item_number "
                "JOIN council_sessions s ON s.ksinr = aa.ksinr WHERE a.template_number = ?", (tn,)).fetchall()
        else:
            stationen = self._conn.execute(
                "SELECT aa.document_id, aa.label, aa.url, s.session_date FROM council_agenda_attachments aa "
                "JOIN council_sessions s ON s.ksinr = aa.ksinr WHERE aa.ksinr = ? AND aa.item_number = ?",
                (int(ksinr), item_number)).fetchall()
        for a in stationen:
            # Die Punkt-Anlage „Vorlage" ist das Vorlagen-PDF selbst (498 von 504).
            if a["label"] == "Vorlage" and tn:
                continue
            merke(a["document_id"], a["label"], a["url"], "item_attachment", a["session_date"])
        steckbriefe = self.document_profiles(list(docs))
        from council import document_types  # noqa: PLC0415

        out = []
        for did, d in docs.items():
            sb = steckbriefe.get(did) or {}
            art = "template" if d["source"] == "template" else (sb.get("doc_type") or document_types.classify(d["label"]))
            out.append({**d, "doc_type": art, "applicants": sb.get("applicants") or [],
                        "n_pages": sb.get("n_pages"), "is_scan": bool(sb.get("is_scan"))})
        out.sort(key=lambda d: (document_types.rank(d["doc_type"]), d["first_seen"] or "", d["label"]))
        return out
