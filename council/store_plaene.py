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
        # Ein TOP kann mehrere Zeilen tragen: den Hauptbeschluss und die Einzelabstimmungen
        # über Änderungsanträge (``kind = 'subvote'``), alle unter derselben TOP-Nummer. Zum
        # Plan gehört der Hauptbeschluss — sonst steht ein beschlossener Plan als „abgelehnt“
        # da, weil ein Änderungsantrag scheiterte (gemessen 10.11.2026: 44 Punkte, 17 mit
        # falschem Ergebnis, darunter der Ratsbeschluss zur Ernährungsstrategie).
        decisions: dict[tuple, tuple] = {}
        for ksinr, number, decision_id, outcome in self._conn.execute(
                "SELECT ksinr, item_number, id, outcome FROM council_decisions "
                "ORDER BY (kind = 'subvote'), position, id"):
            decisions.setdefault((ksinr, number), (decision_id, outcome))
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

    def mandate_decisions(self) -> list[dict]:
        """Alle Beschlüsse zu einer Vorlage, mit Beschlusstext und Sitzung — für die Suche nach
        Aufträgen an die Verwaltung (``council/open_mandates.py``)."""
        return [dict(r) for r in self._conn.execute(
            """SELECT d.id, d.title, d.template_number, d.outcome, d.official_text,
                      s.session_date, s.committee
               FROM council_decisions d JOIN council_sessions s ON s.ksinr = d.ksinr
               WHERE d.template_number IS NOT NULL""")]

    def agenda_titles(self) -> list[dict]:
        """Jeder Tagesordnungspunkt mit Titel, Datum, Gremium und Vorlage."""
        return [dict(r) for r in self._conn.execute(
            """SELECT a.title, a.template_number, s.session_date AS date, s.committee
               FROM council_agenda_items a JOIN council_sessions s ON s.ksinr = a.ksinr
               WHERE a.title IS NOT NULL""")]

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

    # ── Orte zum Plan (Karte, Mein Viertel) ───────────────────────────────

    def plan_decision_places(self, plan_key: str, roles: tuple[str, ...], relations: tuple[str, ...],
                             kinds: tuple[str, ...], min_confidence: float) -> list[dict]:
        """Orte, die die Beschlüsse eines Plans nennen — nur konkrete Orte mit Koordinaten in der Stadt,
        sicher zugeordnet und nicht redaktionell verworfen. Eine Zeile je Ort und Beschluss, jüngste zuerst."""
        if not (roles or relations) or not kinds:
            return []
        r_marks, l_marks, k_marks = (",".join("?" * len(x)) or "NULL" for x in (roles, relations, kinds))
        rows = self._conn.execute(
            f"""WITH dec AS (
                  SELECT decision_id FROM council_plan_items
                   WHERE plan_key = ? AND decision_id IS NOT NULL AND role IN ({r_marks})
                  UNION
                  SELECT decision_id FROM council_plan_links
                   WHERE plan_key = ? AND decision_id IS NOT NULL AND relation IN ({l_marks}))
                SELECT l.slug, l.name, l.kind, l.lat, l.lon, l.geojson,
                       d.id AS decision_id, d.title, s.session_date
                  FROM dec
                  JOIN council_decision_locations dl ON dl.decision_id = dec.decision_id
                  JOIN council_locations l ON l.slug = dl.location_slug
                  JOIN council_decisions d ON d.id = dec.decision_id
                  JOIN council_sessions s ON s.ksinr = d.ksinr
                  LEFT JOIN council_place_reviews r ON r.location_slug = l.slug
                 WHERE l.lat IS NOT NULL AND l.lon IS NOT NULL AND l.local_area_id IS NOT NULL
                   AND l.kind IN ({k_marks}) AND dl.confidence >= ?
                   AND (r.status IS NULL OR r.status != 'rejected')
                 ORDER BY s.session_date DESC, d.id DESC""",
            (plan_key, *roles, plan_key, *relations, *kinds, min_confidence)).fetchall()
        return [dict(r) for r in rows]

    def plan_catalog_places(self, slugs: list[str]) -> dict[str, dict]:
        """Orte aus dem Ortskatalog mit Koordinaten — je Slug (für die Orte der Maßnahmen)."""
        slugs = sorted({s for s in slugs if s})
        if not slugs:
            return {}
        rows = self._conn.execute(
            f"""SELECT slug, name, kind, lat, lon, geojson FROM council_locations
                 WHERE slug IN ({",".join("?" * len(slugs))}) AND lat IS NOT NULL AND lon IS NOT NULL""",
            slugs).fetchall()
        return {r["slug"]: dict(r) for r in rows}

    def plan_catalog_names(self, kinds: tuple[str, ...]) -> list[dict]:
        """Alle konkreten Orte des Katalogs mit Koordinaten — für den Abgleich mit Maßnahmentiteln
        (``scripts/plan_orte.py``)."""
        rows = self._conn.execute(
            f"""SELECT slug, name, kind FROM council_locations
                 WHERE lat IS NOT NULL AND lon IS NOT NULL AND local_area_id IS NOT NULL
                   AND kind IN ({",".join("?" * len(kinds))})""", kinds).fetchall()
        return [dict(r) for r in rows]

    def plan_place_areas(self, slugs: list[str]) -> dict[str, dict[str, float]]:
        """Zu welchen Ortsbereichen (``place_id``) ein Ort gehört, mit Anteil — eine Straße kann in mehreren
        liegen; der Bereich mit dem größten Teil hat den Anteil 1."""
        slugs = sorted({s for s in slugs if s})
        if not slugs:
            return {}
        out: dict[str, dict[str, float]] = {}
        for r in self._conn.execute(
                f"""SELECT location_slug, place_id, share FROM council_location_districts
                     WHERE place_id IS NOT NULL AND location_slug IN ({",".join("?" * len(slugs))})""", slugs):
            out.setdefault(r["location_slug"], {})[r["place_id"]] = float(r["share"] if r["share"] is not None else 1.0)
        return out

    # ── Haushalt zum Plan (nur mit dem Recht ``budget`` gezeigt) ──────────

    #: Die Haushaltstabellen, in denen ein Plan beim Namen genannt sein kann — je Tabelle die Felder,
    #: die gesucht werden, und der Schlüssel einer Zeile. Nur diese, kein freies SQL.
    PLAN_BUDGET_TABLES: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
        "products": ("council_products", ("legal_basis", "short_description", "product_name"), ("product_no", "year")),
        "investments": ("council_investment_measures", ("label", "details"), ("code", "year")),
        "amendments": ("council_budget_amendments", ("explanation", "label"), ("budget_year", "list_key", "year", "seq")),
        "amendments_cash": ("council_budget_amendments_cash", ("explanation", "label"), ("budget_year", "list_key", "year", "seq")),
    }

    def plan_budget_matches(self, table: str, term: str) -> list[dict]:
        """Zeilen einer Haushaltstabelle, in deren Textfeldern ``term`` vorkommt (Groß-/Kleinschreibung
        egal) — für den Vorschlag in ``scripts/plan_haushalt.py``, nicht für die Seite."""
        name, fields, _key = self.PLAN_BUDGET_TABLES[table]
        where = " OR ".join(f"lower(coalesce({f}, '')) LIKE ?" for f in fields)
        rows = self._conn.execute(f"SELECT * FROM {name} WHERE {where}", [f"%{term.lower()}%"] * len(fields)).fetchall()
        return [dict(r) for r in rows]

    def plan_budget_rows(self, table: str, key: dict) -> list[dict]:
        """Die Zeilen zu einem Verweis aus ``council/plan_budget.json``: bei Produkten und Investitionen
        alle Jahre der Nummer, bei Änderungslisten die eine Zeile."""
        name, _fields, columns = self.PLAN_BUDGET_TABLES[table]
        used = [c for c in columns if c in key]
        # Eine Änderung ist eine Zeile — ohne ihren vollen Schlüssel träfe der Verweis fremde Zeilen.
        if not used or (table.startswith("amendments") and len(used) != len(columns)):
            return []
        where = " AND ".join(f"{c} = ?" for c in used)
        rows = self._conn.execute(f"SELECT * FROM {name} WHERE {where}", [key[c] for c in used]).fetchall()
        return [dict(r) for r in rows]
