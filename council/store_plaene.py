"""Pläne der Stadt: Rohdaten für die Zuordnung und die Abfragen der Seiten.

Das Register selbst steht als Code in ``council/plans.py``; hier liegt nur,
was der Bestand dazu weiß (``council_plan_items``, ``council_plan_links``,
gebaut von ``council/plan_tracking.py``).
"""
from __future__ import annotations

from council.store_basis import StoreBasis


class PlaeneMixin(StoreBasis):
    """Die Plan-Abfragen — nur zum Mitvererben."""

    # ── Aufbau ─────────────────────────────────────────────────────────────
    def plan_tracking_rows(self) -> list[dict]:
        """Jeder Tagesordnungspunkt mit Sitzung, Vorlagenart und Beschluss.

        Der Beschluss hängt an Sitzung und TOP-Nummer — im Protokoll ohne das
        „Ö “ davor, das die Tagesordnung trägt.
        """
        rows = self._conn.execute(
            """SELECT a.id AS agenda_item_id, a.ksinr, a.item_number, s.session_date AS date,
                      s.committee, a.title, NULLIF(a.template_number, '') AS template_number,
                      a.kvonr, t.kind AS template_kind
               FROM council_agenda_items a
               JOIN council_sessions s ON s.ksinr = a.ksinr
               LEFT JOIN council_templates t ON t.kvonr = a.kvonr
               WHERE a.title IS NOT NULL AND a.title != ''""").fetchall()
        decisions = {(r[0], r[1]): (r[2], r[3]) for r in self._conn.execute(
            "SELECT ksinr, item_number, id, outcome FROM council_decisions")}
        out = []
        for r in rows:
            d = dict(r)
            nummer = (d["item_number"] or "").removeprefix("Ö").removeprefix("N").strip()
            decision_id, outcome = decisions.get((d["ksinr"], nummer), (None, None))
            d["decision_id"], d["outcome"] = decision_id, outcome
            out.append(d)
        return out

    def plan_citing_templates(self) -> list[tuple[str, str]]:
        """(Vorlagennummer, Text) jeder Vorlage, die eine Nummer der Form JJ/NNNN nennt."""
        return [(r[0], r[1]) for r in self._conn.execute(
            "SELECT template_number, raw_text FROM council_templates "
            "WHERE template_number IS NOT NULL AND raw_text LIKE '%/____%'")]

    def plan_measure_candidates(self) -> list[tuple[str, str]]:
        """(Vorlagennummer, Text) der Vorlagen, in denen eine Maßnahmen-Kennung stehen kann —
        grob vorgefiltert über die Plannamen; das Muster prüft ``plan_tracking``."""
        return [(r[0], r[1]) for r in self._conn.execute(
            "SELECT template_number, raw_text FROM council_templates "
            "WHERE template_number IS NOT NULL AND (raw_text LIKE '%Klimaschutz%' "
            "OR raw_text LIKE '%Wärmeplan%' OR raw_text LIKE '%Ernährungsstrategie%')")]

    def plan_templates_with_text(self) -> list[tuple[str, str, str]]:
        """(Vorlagennummer, Titel, Text) aller Vorlagen mit Text — für die Suche nach Plannamen
        (``scripts/plan_modell.py``; läuft von Hand, nicht im Cron)."""
        return [(r[0], r[1] or "", r[2]) for r in self._conn.execute(
            "SELECT template_number, title, raw_text FROM council_templates "
            "WHERE template_number IS NOT NULL AND raw_text IS NOT NULL AND raw_text != ''")]

    def plan_decisions_by_stem(self) -> dict[str, list[int]]:
        """Vorlagenstamm → Beschlüsse (alle Gremien), für den Verweis über die Nummer."""
        out: dict[str, list[int]] = {}
        for number, decision_id in self._conn.execute(
                "SELECT template_number, id FROM council_decisions WHERE template_number IS NOT NULL"):
            stem = "/".join(str(number).split("/")[:2])
            out.setdefault(stem, []).append(decision_id)
        return out

    def replace_plan_tracking(self, items: list[dict], links: list[dict]) -> None:
        """Beide Tabellen in einem Zug neu — ein abgebrochener Lauf lässt den alten Stand stehen."""
        with self.transaktion():
            self._conn.execute("DELETE FROM council_plan_items")
            self._conn.execute("DELETE FROM council_plan_links")
            self._conn.executemany(
                """INSERT INTO council_plan_items (plan_key, agenda_item_id, ksinr, item_number, date,
                       committee, title, template_number, kvonr, role, oral, decision_id, outcome)
                   VALUES (:plan_key, :agenda_item_id, :ksinr, :item_number, :date, :committee, :title,
                           :template_number, :kvonr, :role, :oral, :decision_id, :outcome)""", items)
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_plan_links
                       (plan_key, decision_id, measure_code, relation, method, confidence)
                   VALUES (:plan_key, :decision_id, :measure_code, :relation, :method, :confidence)""", links)

    # ── Lesen ──────────────────────────────────────────────────────────────
    def plan_items(self, plan_key: str | None = None) -> list[dict]:
        """Die Tagesordnungspunkte eines Plans (oder aller), ältester zuerst."""
        where, args = ("WHERE plan_key = ?", (plan_key,)) if plan_key else ("", ())
        return [dict(r) for r in self._conn.execute(
            f"SELECT * FROM council_plan_items {where} ORDER BY date, committee, agenda_item_id", args)]

    def plan_mentions(self, plan_key: str) -> list[dict]:
        """Beschlüsse, deren Vorlage den Plan über seine Nummer erwähnt — je Vorlage der jüngste."""
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.outcome, s.session_date, s.committee
               FROM council_plan_links l
               JOIN council_decisions d ON d.id = l.decision_id
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE l.plan_key = ? AND l.relation = 'mentions'
               ORDER BY s.session_date DESC, d.id DESC""", (plan_key,)).fetchall()
        seen: set[str] = set()
        out = []
        for r in rows:
            stem = "/".join(str(r["template_number"]).split("/")[:2])
            if stem in seen:
                continue
            seen.add(stem)
            out.append(dict(r))
        return out

    def plan_measure_links(self, plan_key: str) -> list[dict]:
        """Beschlüsse, deren Vorlage eine Maßnahme des Plans nennt — je Vorlage der jüngste,
        mit allen Kennungen, die sie nennt."""
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.outcome, s.session_date, s.committee, l.measure_code
               FROM council_plan_links l
               JOIN council_decisions d ON d.id = l.decision_id
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE l.plan_key = ? AND l.relation = 'names_measure'
               ORDER BY s.session_date DESC, d.id DESC""", (plan_key,)).fetchall()
        by_stem: dict[str, dict] = {}
        for r in rows:
            stem = "/".join(str(r["template_number"]).split("/")[:2])
            entry = by_stem.setdefault(stem, {**{k: r[k] for k in r.keys() if k != "measure_code"}, "codes": set(), "ids": set()})
            entry["codes"].add(r["measure_code"])
            entry["ids"].add(r["id"])
        return [{**{k: v for k, v in e.items() if k not in ("codes", "ids")},
                 "measure_codes": sorted(e["codes"]), "deliberations": len(e["ids"])} for e in by_stem.values()]

    def plan_judged_links(self, plan_key: str) -> list[dict]:
        """Beschlüsse zu Vorlagen, die laut ihrem Text der Umsetzung des Plans dienen — je Vorlage der jüngste."""
        rows = self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.outcome, s.session_date, s.committee
               FROM council_plan_links l
               JOIN council_decisions d ON d.id = l.decision_id
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE l.plan_key = ? AND l.relation = 'implements'
               ORDER BY s.session_date DESC, d.id DESC""", (plan_key,)).fetchall()
        by_stem: dict[str, dict] = {}
        for r in rows:
            stem = "/".join(str(r["template_number"]).split("/")[:2])
            entry = by_stem.setdefault(stem, {**dict(r), "ids": set()})
            entry["ids"].add(r["id"])
        return [{**{k: v for k, v in e.items() if k != "ids"}, "deliberations": len(e["ids"])} for e in by_stem.values()]

    def plan_template_kvonr(self, numbers: list[str]) -> dict[str, int]:
        """Vorlagennummer → kvonr, für Links auf die Vorlage."""
        if not numbers:
            return {}
        marks = ",".join("?" * len(numbers))
        return {r[0]: r[1] for r in self._conn.execute(
            f"SELECT template_number, kvonr FROM council_templates WHERE template_number IN ({marks})",
            numbers)}

    def plan_template_titles(self, numbers: list[str]) -> dict[str, str]:
        if not numbers:
            return {}
        marks = ",".join("?" * len(numbers))
        return {r[0]: r[1] for r in self._conn.execute(
            f"SELECT template_number, title FROM council_templates WHERE template_number IN ({marks})",
            numbers)}

    def plan_decision_at(self, template: str, date: str, committee: str) -> dict | None:
        """Der Beschluss zu einer Vorlage an Datum und Gremium (für den Kopf der Planseite)."""
        stem = "/".join(template.split("/")[:2])
        r = self._conn.execute(
            """SELECT d.id, d.outcome, d.vote FROM council_decisions d
               JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE s.session_date = ? AND s.committee = ?
                 AND (d.template_number = ? OR d.template_number LIKE ? || '/%' OR d.template_number = ?)
               ORDER BY d.template_number = ? DESC LIMIT 1""",
            (date, committee, template, stem, stem, template)).fetchone()
        return dict(r) if r else None
