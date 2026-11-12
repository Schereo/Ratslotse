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

        from council.parties import parties_in_text  # noqa: PLC0415

        out, labels = [], set()
        # An der Vorlage zuerst: Dasselbe Dokument liegt oft unter zwei Kennungen
        # an Vorlage und Punkt („Anlage Geschäftsordnung"); gleiches Label heißt
        # dann ein Eintrag.
        for did, d in sorted(docs.items(), key=lambda kv: kv[1]["source"] != "template_attachment"):
            schluessel = " ".join((d["label"] or "").lower().split())
            if d["source"] != "template" and schluessel in labels:
                continue
            labels.add(schluessel)
            sb = steckbriefe.get(did) or {}
            art = "template" if d["source"] == "template" else (sb.get("doc_type") or document_types.classify(d["label"]))
            out.append({**d, "doc_type": art, "applicants": sb.get("applicants") or parties_in_text(d["label"]),
                        "n_pages": sb.get("n_pages"), "is_scan": bool(sb.get("is_scan"))})
        out.sort(key=lambda d: (document_types.rank(d["doc_type"]), d["first_seen"] or "", d["label"]))
        return out

    # ---- Antrags-Auszüge (council/motions.py, PR 9) ------------------------

    def motion_extract(self, document_id: int) -> dict | None:
        r = self._conn.execute("SELECT * FROM motion_extracts WHERE document_id = ?", (int(document_id),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["payload"] = json.loads(d["payload"]) if d["payload"] else None
        return d

    def save_motion_extract(self, document_id: int, *, base_subject_key: str | None, base_hash: str | None,
                            text_hash: str, status: str, payload: dict | None, prompt_version: int,
                            model: str | None, cost_usd: float | None) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO motion_extracts (document_id, base_subject_key, base_hash, text_hash, "
                "status, payload, prompt_version, model, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (int(document_id), base_subject_key, base_hash, text_hash, status,
                 json.dumps(payload, ensure_ascii=False) if payload is not None else None, prompt_version,
                 model, cost_usd, datetime.now(UTC).isoformat(timespec="seconds")))

    def _dokument_text(self, document_id: int) -> tuple[str | None, str | None, str | None]:
        """(Text, Label, URL) eines Dokuments — an der Vorlage oder am Punkt."""
        r = self._conn.execute(
            "SELECT raw_text, label, url FROM council_attachments WHERE document_id = ? AND raw_text IS NOT NULL "
            "AND raw_text != ''", (int(document_id),)).fetchone() or self._conn.execute(
            "SELECT raw_text, label, url FROM council_agenda_attachments WHERE document_id = ? "
            "AND raw_text IS NOT NULL AND raw_text != '' LIMIT 1", (int(document_id),)).fetchone()
        return (r["raw_text"], r["label"], r["url"]) if r else (None, None, None)

    def motion_material(self, document_id: int, ksinr: int, item_number: str) -> dict | None:
        """Was ``motions.extract`` braucht: Antrag, Vorlage des Punkts (mit
        Seiten), Regelwerke am Punkt (für §-Anker). ``None`` ohne Antragstext."""
        from council import evidence  # noqa: PLC0415

        text, label, url = self._dokument_text(document_id)
        if not text:
            return None
        sb = self.document_profiles([document_id]).get(int(document_id)) or {}
        motion = {"document_id": int(document_id), "label": label, "url": url, "text": text,
                  "pages": evidence.pages_from_offsets(text, sb.get("page_offsets"))}
        punkt = self._conn.execute(
            "SELECT template_number FROM council_agenda_items WHERE ksinr = ? AND item_number = ?",
            (int(ksinr), item_number)).fetchone()
        tn = (punkt["template_number"] or "").strip() if punkt else ""
        template = None
        if tn:
            v = self.get_vorlage_by_nr(tn)
            if v and v.get("status") == "ok":
                off = (self.document_profiles([v["document_id"]]).get(v["document_id"]) or {}).get("page_offsets") \
                    if v.get("document_id") else None
                template = {"template_number": tn, "document_id": v.get("document_id"),
                            "proposed_decision": v.get("proposed_decision"), "raw_text": v.get("raw_text"),
                            "pages": evidence.pages_from_offsets(v.get("raw_text") or "", off)}
        statutes = []
        for d in self.item_documents(int(ksinr), item_number):
            if d["doc_type"] in ("statute", "synopsis") and d["document_id"] != int(document_id):
                st_text, st_label, _ = self._dokument_text(d["document_id"])
                if st_text:
                    off = (self.document_profiles([d["document_id"]]).get(d["document_id"]) or {}).get("page_offsets")
                    statutes.append({"document_id": d["document_id"], "label": st_label, "text": st_text,
                                     "pages": evidence.pages_from_offsets(st_text, off)})
        return {"motion": motion, "template": template, "statutes": statutes, "item_template": tn or None,
                "base_subject_key": f"tn:{tn}" if tn else f"doc:{document_id}"}

    def antraege_kommender_punkte(self, seit: str, bis: str) -> list[dict]:
        """(ksinr, Punkt, document_id) aller Anträge an Punkten von Sitzungen
        zwischen ``seit`` und ``bis`` — an der Vorlage oder am Punkt."""
        punkte = self._conn.execute(
            "SELECT a.ksinr, a.item_number FROM council_agenda_items a JOIN council_sessions s ON s.ksinr = a.ksinr "
            "WHERE s.session_date BETWEEN ? AND ? AND a.is_public = 1 ORDER BY s.session_date", (seit, bis)).fetchall()
        out, gesehen = [], set()
        for p in punkte:
            for d in self.item_documents(p["ksinr"], p["item_number"]):
                if d["doc_type"] in ("amendment", "motion") and d["document_id"] not in gesehen:
                    gesehen.add(d["document_id"])
                    out.append({"ksinr": p["ksinr"], "item_number": p["item_number"], "document_id": d["document_id"]})
        return out

    def item_amendments(self, ksinr: int, item_number: str) -> list[dict]:
        """Die gelesenen Anträge eines Punkts für die Anzeige (Plan § 6.1,
        Punkt 3): je Antrag Antragsteller, Ziel, Muster, alt/neu, Wortdiff,
        Bedeutung, Begründung, die Nummer in der Gegenlese-Liste — und nach dem
        Protokoll das Ergebnis der Teilabstimmung, wenn sie sich eindeutig
        zuordnen lässt."""
        import re  # noqa: PLC0415

        from council import motions  # noqa: PLC0415

        docs = [d for d in self.item_documents(int(ksinr), item_number) if d.get("url")]
        nummer = {d["document_id"]: n for n, d in enumerate(docs, 1)}
        subs = None
        out = []
        for d in docs:
            if d["doc_type"] not in ("amendment", "motion"):
                continue
            ex = self.motion_extract(d["document_id"])
            p = (ex or {}).get("payload") if ex and ex.get("status") == "ok" else None
            eintrag = {"document_id": d["document_id"], "list_no": nummer[d["document_id"]], "label": d["label"],
                       "url": d["url"], "doc_type": d["doc_type"],
                       "applicants": (p or {}).get("applicants") or d["applicants"],
                       "read": p is not None, "outcome": None, "decision_id": None}
            if p:
                for k in ("target", "pattern", "before", "after", "diff", "meaning", "reason", "base_template", "base_missing"):
                    eintrag[k] = p.get(k)
                if subs is None:
                    nr = re.sub(r"^\D+", "", item_number).strip()
                    subs = [dict(r) | {"factions": json.loads(r["factions"] or "[]")} for r in self._conn.execute(
                        "SELECT id, title, factions, outcome FROM council_decisions WHERE ksinr = ? "
                        "AND kind = 'subvote' AND parent_item = ?", (int(ksinr), nr))]
                treffer = motions.match_subvote({"applicants": eintrag["applicants"], "label": d["label"],
                                                 "target": p.get("target"),
                                                 "meaning": (p.get("meaning") or {}).get("text")}, subs)
                if treffer:
                    sv = next(s for s in subs if s["id"] == treffer)
                    eintrag["outcome"], eintrag["decision_id"] = sv["outcome"], sv["id"]
            out.append(eintrag)
        return out

    def amendment_summary(self, ksinr: int, item_number: str) -> tuple[int, list[str]]:
        """(Zahl der Änderungsanträge, Antragsteller) — für die Karte der Sitzungsseite."""
        n, parteien = 0, []
        for d in self.item_documents(int(ksinr), item_number):
            if d["doc_type"] == "amendment":
                n += 1
                for p in d["applicants"]:
                    if p not in parteien:
                        parteien.append(p)
        return n, parteien

    def agenda_item_for_decision(self, ksinr: int, item_number: str | None) -> str | None:
        """„Ö 5" zur Beschluss-Nummer „5" derselben Sitzung."""
        import re  # noqa: PLC0415

        ziel = (item_number or "").strip()
        for r in self._conn.execute("SELECT item_number FROM council_agenda_items WHERE ksinr = ?", (int(ksinr),)):
            if re.sub(r"^\D+", "", r["item_number"]).strip() == ziel:
                return r["item_number"]
        return None
    # ---- Dossier je Vorlage (council/template_dossier.py, PR 12) -----------

    def dossier_material(self, template_number: str) -> dict | None:
        """Vorlage, Form und die Unterlagen aller Stationen — ohne Anträge
        (die haben ihren eigenen Auszug). ``None`` ohne Vorlagentext."""
        from council import dossier_harvest  # noqa: PLC0415

        v = self.get_vorlage_by_nr(template_number)
        if not v or v.get("status") != "ok" or not (v.get("raw_text") or "").strip():
            return None
        punkt = self._conn.execute(
            "SELECT a.ksinr, a.item_number FROM council_agenda_items a JOIN council_sessions s ON s.ksinr = a.ksinr "
            "WHERE a.template_number = ? ORDER BY s.session_date DESC LIMIT 1", (template_number,)).fetchone()
        docs = []
        for d in (self.item_documents(punkt["ksinr"], punkt["item_number"]) if punkt else []):
            if d["doc_type"] in ("template", "amendment", "motion"):
                continue
            text, _, _ = self._dokument_text(d["document_id"])
            sb = self.document_profiles([d["document_id"]]).get(d["document_id"]) or {}
            docs.append({**d, "text": text or "", "page_offsets": sb.get("page_offsets")})
        docs.sort(key=lambda d: (d["doc_type"], d["document_id"]))   # deterministisch: Prompt-Cache
        return {"template": {**v, "template_number": template_number}, "documents": docs,
                "form": dossier_harvest.form(v.get("title"), v.get("kind"), [d["doc_type"] for d in docs])}

    def template_dossier(self, subject_key: str, sources_hash: str | None = None) -> dict | None:
        """Ein Dossier — zur Quellenlage ``sources_hash`` oder das jüngste fertige."""
        if sources_hash:
            r = self._conn.execute("SELECT * FROM template_dossiers WHERE subject_key = ? AND sources_hash = ?",
                                   (subject_key, sources_hash)).fetchone()
        else:
            r = self._conn.execute("SELECT * FROM template_dossiers WHERE subject_key = ? AND status = 'ok' "
                                   "ORDER BY created_at DESC LIMIT 1", (subject_key,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["payload"] = json.loads(d["payload"]) if d["payload"] else None
        return d

    def dossier_sperren(self, subject_key: str, sources_hash: str) -> bool:
        """Sperre in der Datenbank statt im Prozess (gilt über uvicorn-Worker
        hinweg): ``True``, wenn dieser Aufrufer erzeugen darf."""
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with self._conn:
            r = self._conn.execute("SELECT status, started_at FROM template_dossiers WHERE subject_key = ? "
                                   "AND sources_hash = ?", (subject_key, sources_hash)).fetchone()
            if r and r["status"] == "running" and r["started_at"] and r["started_at"] > \
                    datetime.fromtimestamp(datetime.now(UTC).timestamp() - 300, UTC).isoformat(timespec="seconds"):
                return False
            self._conn.execute(
                "INSERT INTO template_dossiers (subject_key, sources_hash, prompt_version, status, started_at, created_at) "
                "VALUES (?, ?, 0, 'running', ?, ?) ON CONFLICT(subject_key, sources_hash) DO UPDATE SET "
                "status = 'running', started_at = excluded.started_at", (subject_key, sources_hash, jetzt, jetzt))
        return True

    def save_template_dossier(self, subject_key: str, sources_hash: str, *, status: str, form: str | None,
                              payload: dict | None, model: str | None, cost_usd: float | None,
                              prompt_version: int) -> None:
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO template_dossiers (subject_key, sources_hash, prompt_version, model, form, status, "
                "payload, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(subject_key, sources_hash) "
                "DO UPDATE SET prompt_version = excluded.prompt_version, model = excluded.model, form = excluded.form, "
                "status = excluded.status, payload = excluded.payload, cost_usd = excluded.cost_usd, "
                "created_at = excluded.created_at",
                (subject_key, sources_hash, prompt_version, model, form, status,
                 json.dumps(payload, ensure_ascii=False) if payload is not None else None, cost_usd, jetzt))

    def vorlagen_kommender_sitzungen(self, seit: str, bis: str) -> list[str]:
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT a.template_number FROM council_agenda_items a JOIN council_sessions s ON s.ksinr = a.ksinr "
            "WHERE s.session_date BETWEEN ? AND ? AND a.is_public = 1 AND COALESCE(a.template_number, '') != '' "
            "ORDER BY s.session_date", (seit, bis))]
