"""„Mein Viertel": Vorhaben je Ortsbereich — Lese- und Schreibseite.

Was hier liegt, ruft genau eine Ecke: der Register-Lauf (``council/viertel.py``,
``scripts/build_district_projects.py``) und die Endpunkte unter
``/api/districts``. Die Orts-Pipeline selbst (welcher Beschluss nennt welchen
Ort) bleibt in ``store_orte.py`` — hier wird sie nur gelesen.

**Warum ein eigenes Register und kein Filter über die Orts-Tabellen.** Die
Orts-Pipeline sagt, dass ein Beschluss einen Ort *nennt*. Für „Was ändert sich
in meinem Viertel" reicht das nicht: Gemessen am 05.09.2026 gehörte rund die
Hälfte der so gefundenen Beschlüsse nicht ins Viertel (stadtweite Berichte mit
Beispielort, das Klinikum, Gedenktitel mit Straßennamen). Die zweite Stufe
(``council_district_reviews``) hält das Urteil je Beschluss UND Ortsbereich
fest, die Bündelung (``council_district_projects``) macht aus Ausschuss- und
Ratsbeschluss, Aufstellungs- und Satzungsbeschluss EIN Vorhaben mit Stand.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from council.store_basis import StoreBasis
from kern.dbfehler import tabelle_fehlt

#: Was als Vorhaben auf die Tafel darf. Darunter bleibt es im Register, aber
#: unsichtbar — die Schwelle ist die eine Stellschraube für Tims Messlatte
#: „nahezu 100 %": lieber ein Vorhaben zu wenig als eines aus dem falschen
#: Viertel.
PROJECT_MIN_CONFIDENCE = 90

#: Ab so vielen Konten, die „Gehört nicht hierher" gesagt haben, verschwindet
#: ein Vorhaben von der Tafel. Eins reicht nicht — sonst nähme ein Tippfehler
#: allen anderen die Karte weg; zwei unabhängige Stimmen sind ein Signal.
PROJECT_HIDE_REPORTS = 2

#: Wie weit zurück Beschlüsse als Kandidaten zählen (Monate). Ein Vorhaben
#: lebt über Jahre, aber ein Beschluss von 2019 sagt nichts über 2027 —
#: 24 Monate war die Messgrundlage des PoC.
CANDIDATE_MONTHS = 24

#: Ab diesem Flächenanteil im Ortsbereich zählt ein Ort als „dort". Eine
#: Straße, die zu 15 % durch das Viertel läuft, gehört in den Beschlussfilter
#: (dort will man sie sehen), aber nicht auf die Vorhaben-Tafel.
CANDIDATE_MIN_SHARE = 0.5

#: Ortsarten, deren Name in einer Vorhaben-Bezeichnung des Investitions-
#: programms als Ortsbezug zählt. Gebäude und Sammelbegriffe („Feuerwehr",
#: „Stadion") trafen im PoC Vorhaben aus der ganzen Stadt.
_INVESTMENT_LOCATION_KINDS = ("street", "square", "water")

_STRICT_METHODS = ("district_list", "place_catalog")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ViertelMixin(StoreBasis):
    """Die Viertel-Abfragen von :class:`council.store.CouncilStore` — nur zum Mitvererben."""

    if TYPE_CHECKING:
        # Zwei Nachbar-Methoden, die dieses Mixin am zusammengesetzten Store
        # aufruft. Zur Laufzeit steht hier nichts — die Auflösung läuft wie
        # immer über die MRO von ``CouncilStore``; für die Typprüfung leiht
        # sich die Klasse die Signatur beim Eigentümer, damit beide nicht
        # auseinanderlaufen. In ``StoreBasis`` gehören sie nicht: Die
        # beschreibt den gemeinsamen Nenner, nicht die Kopplung zweier Nachbarn.
        from council.store_orte import OrteMixin
        from council.store_presse import PresseMixin

        resolve_place = OrteMixin.resolve_place
        list_beteiligungen = PresseMixin.list_beteiligungen

    # ------------------------------------------------------------ Kandidaten

    def district_candidates(self, place, *, since: str | None = None,
                            min_share: float = CANDIDATE_MIN_SHARE) -> list[dict]:
        """Beschlüsse, deren erkannte Orte im Ortsbereich liegen — mit allem,
        was die zweite Stufe zum Urteilen braucht.

        Je Beschluss: die Orte (mit Anteil, Quelle, Methode), ob mindestens
        einer davon *streng* erkannt wurde (aus dem Titel, der Stadtteil-Liste
        oder dem Katalog), welche anderen Ortsbereiche dieselben Orte berühren,
        und der Vorlagentext, soweit er da ist.
        """
        if since is None:
            since = _months_ago(CANDIDATE_MONTHS)
        rows = self._conn.execute(
            """
            SELECT d.id, d.title, d.summary, d.official_text, d.outcome, d.kind, d.kvonr,
                   se.session_date, se.committee,
                   dl.source, dl.method, dl.evidence,
                   l.slug AS location_slug, l.name AS location, l.kind AS location_kind, ld.share
            FROM council_decision_locations dl
            JOIN council_locations l ON l.slug = dl.location_slug
            JOIN council_location_districts ld ON ld.location_slug = dl.location_slug
            JOIN council_decisions d ON d.id = dl.decision_id
            JOIN council_sessions se ON se.ksinr = d.ksinr
            WHERE (ld.place_id = ? OR ld.district = ?) AND se.session_date >= ? AND ld.share >= ?
            ORDER BY se.session_date DESC, d.id
            """, (place.id, place.name, since, min_share)).fetchall()
        by_id: dict[int, dict] = {}
        for r in rows:
            d = by_id.setdefault(r["id"], {
                "id": r["id"], "title": r["title"], "summary": r["summary"],
                "official_text": r["official_text"], "outcome": r["outcome"], "kind": r["kind"],
                "kvonr": r["kvonr"], "date": r["session_date"], "committee": r["committee"],
                "locations": [], "strict": False, "other_districts": [],
            })
            strict = r["source"] == "title" or r["method"] in _STRICT_METHODS
            d["locations"].append({
                "slug": r["location_slug"], "name": r["location"], "kind": r["location_kind"],
                "share": round(r["share"], 2), "source": r["source"], "method": r["method"],
                "evidence": (r["evidence"] or "")[:160], "strict": strict,
            })
            d["strict"] = d["strict"] or strict
        for d in by_id.values():
            others = self._conn.execute(
                "SELECT DISTINCT ld.district FROM council_decision_locations dl "
                "JOIN council_location_districts ld ON ld.location_slug = dl.location_slug "
                "WHERE dl.decision_id = ? AND ld.district != ? AND ld.share >= ?",
                (d["id"], place.name, min_share)).fetchall()
            d["other_districts"] = [o[0] for o in others]
            d["namesakes"] = self._namesakes(d["locations"], place)
            if d["kvonr"]:
                t = self._conn.execute(
                    "SELECT raw_text, proposed_decision, financial_impact FROM council_templates "
                    "WHERE kvonr = ?", (d["kvonr"],)).fetchone()
                if t:
                    d["template_text"] = t["raw_text"] or None
                    d["proposed_decision"] = (t["proposed_decision"] or "")[:600] or None
                    d["financial_impact"] = (t["financial_impact"] or "")[:300] or None
        return list(by_id.values())

    def _namesakes(self, locations: list[dict], place) -> list[dict]:
        """ANDERE Katalog-Orte anderer Ortsbereiche, die einen dieser Namen
        tragen oder enthalten.

        Der eine Fehler des PoC: „Schießstand" steht im Katalog als Fläche in
        Eversten (die Straße Am Schießstand), gemeint war der alte Schießstand
        auf dem Fliegerhorst. Beide Einträge existieren — die zweite Stufe
        muss nur wissen, dass es sie gibt.

        Nicht gemeint: derselbe Ort, der zu einem kleineren Teil auch im
        Nachbar-Ortsbereich liegt (die Sandkruger Straße läuft weiter nach
        Bümmerstede), und Hausnummern-Varianten („Cloppenburger Straße 35").
        """
        out: list[dict] = []
        eigene = {loc["slug"] for loc in locations}
        for loc in locations:
            name = loc["name"]
            # Der Ortsbereich selbst (Stadtteil-Liste) hat keine Namensvettern,
            # nur Zusammensetzungen — „Sportpark Osternburg" liegt in Tweelbäke
            # und macht einen Beschluss über Osternburg nicht zweideutig.
            if len(name) < 5 or loc.get("kind") == "district" or name == place.name:
                continue
            rows = self._conn.execute(
                "SELECT l.slug, l.name, ld.district FROM council_locations l "
                "JOIN council_location_districts ld ON ld.location_slug = l.slug "
                "WHERE ld.district != ? AND ld.share >= 0.5 AND (l.name = ? OR l.name LIKE ?) "
                "LIMIT 8", (place.name, name, f"%{name}%")).fetchall()
            ganzes_wort = re.compile(r"(?:^|[^A-Za-zÄÖÜäöüß])" + re.escape(name) + r"(?:$|[^a-zäöüß])")
            for r in rows:
                if r["slug"] in eigene or not ganzes_wort.search(r["name"]):
                    continue
                if re.match(re.escape(name) + r"\s*\d", r["name"]):
                    continue
                if not any(o["name"] == r["name"] and o["district"] == r["district"] for o in out):
                    out.append({"name": r["name"], "district": r["district"]})
        return out

    # --------------------------------------------------------------- Urteile

    def district_reviews(self, place_id: str) -> dict[int, dict]:
        """Die gespeicherten Urteile eines Ortsbereichs, je decision_id."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM council_district_reviews WHERE place_id = ?", (place_id,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        return {r["decision_id"]: dict(r) for r in rows}

    def save_district_reviews(self, place_id: str, reviews: list[dict], model: str) -> int:
        """Urteile eintragen oder ersetzen; ``source_hash`` macht den Lauf idempotent."""
        now = _now()
        with self._conn:
            self._conn.executemany(
                "INSERT INTO council_district_reviews (decision_id, place_id, relation, changes, what, "
                "when_text, stage, category, confidence, reason, source_hash, model, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(decision_id, place_id) DO UPDATE SET relation=excluded.relation, "
                "changes=excluded.changes, what=excluded.what, when_text=excluded.when_text, "
                "stage=excluded.stage, category=excluded.category, confidence=excluded.confidence, "
                "reason=excluded.reason, source_hash=excluded.source_hash, model=excluded.model, "
                "updated_at=excluded.updated_at",
                [(r["decision_id"], place_id, r["relation"], 1 if r.get("changes") else 0,
                  (r.get("what") or "")[:300], r.get("when"), r.get("stage"), r.get("category"),
                  int(r.get("confidence") or 0), (r.get("reason") or "")[:300],
                  r["source_hash"], model, now) for r in reviews])
        return len(reviews)

    # -------------------------------------------------------------- Vorhaben

    def replace_district_projects(self, place_id: str, projects: list[dict]) -> int:
        """Die Vorhaben eines Ortsbereichs komplett ersetzen — EINE Transaktion.

        ``project_key`` = ``place_id:<kleinste decision_id>`` bleibt über Läufe
        stabil, solange der älteste Beschluss des Vorhabens derselbe bleibt.
        Daran hängen die Meldungen; ein Vorhaben, das beim nächsten Lauf anders
        geschnitten wird, verliert sie im schlimmsten Fall — und nicht mehr.
        """
        now = _now()
        with self._conn:
            alte = [r[0] for r in self._conn.execute(
                "SELECT id FROM council_district_projects WHERE place_id = ?", (place_id,)).fetchall()]
            if alte:
                ph = ",".join("?" * len(alte))
                self._conn.execute(
                    f"DELETE FROM council_district_project_decisions WHERE project_id IN ({ph})", alte)
                self._conn.execute("DELETE FROM council_district_projects WHERE place_id = ?", (place_id,))
            for p in projects:
                ids = sorted({int(i) for i in p.get("decision_ids") or []})
                if not ids:
                    continue
                dates = self._conn.execute(
                    f"SELECT MIN(se.session_date), MAX(se.session_date) FROM council_decisions d "
                    f"JOIN council_sessions se ON se.ksinr = d.ksinr WHERE d.id IN ({','.join('?' * len(ids))})",
                    ids).fetchone()
                cur = self._conn.execute(
                    "INSERT INTO council_district_projects (place_id, project_key, name, what, stage, "
                    "when_text, category, confidence, first_date, last_date, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (place_id, f"{place_id}:{ids[0]}", (p.get("name") or "")[:80], (p.get("what") or "")[:600],
                     p.get("stage") or "planning", p.get("when"), p.get("category") or "other",
                     int(p.get("confidence") or 0), dates[0], dates[1], now))
                self._conn.executemany(
                    "INSERT OR IGNORE INTO council_district_project_decisions (project_id, decision_id) "
                    "VALUES (?, ?)", [(cur.lastrowid, i) for i in ids])
        return len(projects)

    def district_projects(self, place_id: str, *, min_confidence: int = PROJECT_MIN_CONFIDENCE,
                          include_hidden: bool = False) -> list[dict]:
        """Die Vorhaben eines Ortsbereichs mit ihren Beschlüssen, sichtbare zuerst nach Stand."""
        try:
            rows = self._conn.execute(
                "SELECT p.*, (SELECT COUNT(*) FROM council_district_project_reports r "
                "WHERE r.project_key = p.project_key) AS report_count "
                "FROM council_district_projects p WHERE p.place_id = ? AND p.confidence >= ? "
                "ORDER BY p.last_date DESC, p.id", (place_id, min_confidence)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        out = []
        for r in rows:
            hidden = r["report_count"] >= PROJECT_HIDE_REPORTS
            if hidden and not include_hidden:
                continue
            decisions = self._conn.execute(
                "SELECT d.id, d.title, d.outcome, se.session_date AS date, se.committee "
                "FROM council_district_project_decisions pd "
                "JOIN council_decisions d ON d.id = pd.decision_id "
                "JOIN council_sessions se ON se.ksinr = d.ksinr "
                "WHERE pd.project_id = ? ORDER BY se.session_date DESC, d.id DESC", (r["id"],)).fetchall()
            ids = [d["id"] for d in decisions]
            locations = self._project_locations(ids, place_id) if ids else []
            out.append({
                "id": r["id"], "project_key": r["project_key"], "place_id": r["place_id"],
                "name": r["name"], "what": r["what"], "stage": r["stage"], "when": r["when_text"],
                "category": r["category"], "confidence": r["confidence"],
                "first_date": r["first_date"], "last_date": r["last_date"],
                "report_count": r["report_count"], "hidden": hidden,
                "decisions": [dict(d) for d in decisions],
                "locations": locations,
            })
        return out

    def _project_locations(self, decision_ids: list[int], place_id: str) -> list[dict]:
        """Die Orte eines Vorhabens für die Karte: Punkt plus Linie, wo es eine gibt.

        Nur Orte, die im Ortsbereich liegen (Anteil ≥ 0,5) und Koordinaten
        haben. Eine Straße bekommt ihre Geometrie mit — ein Pin am
        Bounding-Box-Mittelpunkt läge bei einer Straße um die Ecke NEBEN ihr
        (dieselbe Falle wie in ``geo.ortsbereiche_der_geometrie``).
        """
        ph = ",".join("?" * len(decision_ids))
        rows = self._conn.execute(
            f"SELECT DISTINCT l.slug, l.name, l.kind, l.lat, l.lon, l.geojson "
            f"FROM council_decision_locations dl JOIN council_locations l ON l.slug = dl.location_slug "
            f"JOIN council_location_districts ld ON ld.location_slug = l.slug "
            f"WHERE dl.decision_id IN ({ph}) AND (ld.place_id = ? OR ld.district = (SELECT name FROM ("
            f"SELECT ? AS name))) AND ld.share >= ? AND l.lat IS NOT NULL AND l.lon IS NOT NULL "
            f"AND l.kind != 'district' ORDER BY l.kind, l.name",
            (*decision_ids, place_id, self._place_name(place_id), CANDIDATE_MIN_SHARE)).fetchall()
        from council import geo
        place_name = self._place_name(place_id)
        # Die Texte des Vorhabens entscheiden, welcher Ort Gegenstand ist und
        # welcher nur eine Abschnittsgrenze („Am Schmeel bis Brahmweg") — in
        # Stufen: Titel vor Zusammenfassung vor Beschlusstext vor Vorlage vor
        # der Fundstelle der Orts-Pipeline (s. ``ortsrollen``). Die Vorlage
        # wird gesucht wie dort (``store_orte``): über kvonr, sonst über die
        # Vorlagen-Nummer — am 06.09.2026 hing sie bei „Tweelbäker Tredde"
        # nur an der Nummer, und ein Join allein über kvonr fand sie nicht.
        stufen: list[list[str]] = [[], [], [], [], []]
        for d in self._conn.execute(
                f"SELECT d.title, d.summary, d.official_text, COALESCE("
                f"(SELECT v.raw_text FROM council_templates v WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1), "
                f"(SELECT v.raw_text FROM council_templates v WHERE v.status = 'ok' "
                f" AND v.template_number = d.template_number ORDER BY v.kvonr DESC LIMIT 1)) AS raw_text "
                f"FROM council_decisions d WHERE d.id IN ({ph})",
                decision_ids).fetchall():
            for i, k in enumerate(("title", "summary", "official_text", "raw_text")):
                if d[k]:
                    stufen[i].append(d[k][:20000])
        for e in self._conn.execute(
                f"SELECT DISTINCT evidence FROM council_decision_locations WHERE decision_id IN ({ph})",
                decision_ids).fetchall():
            if e["evidence"]:
                stufen[4].append(e["evidence"])
        rollen = ortsrollen([r["name"] for r in rows], ["\n\n".join(t) for t in stufen],
                            kinds={r["name"]: r["kind"] for r in rows})
        out = []
        for r in rows:
            geometry = None
            lat, lon = r["lat"], r["lon"]
            if r["geojson"]:
                try:
                    g = json.loads(r["geojson"])
                except ValueError:
                    g = None
                if isinstance(g, dict) and g.get("type") in ("LineString", "MultiLineString"):
                    # Eine lange Straße bekommt nur ihr Stück im Viertel — und
                    # ihren Pin auf dieses Stück, nicht auf die Mitte der ganzen
                    # Straße, die außerhalb liegen kann.
                    geometry = geo.auf_ortsbereich_beschneiden(g, place_name)
                    mitte = geo.linien_mittelpunkt(geometry)
                    if mitte:
                        lat, lon = mitte
                elif isinstance(g, dict) and g.get("type") in ("Polygon", "MultiPolygon"):
                    geometry = g
            out.append({"slug": r["slug"], "name": r["name"], "kind": r["kind"],
                        "lat": lat, "lon": lon, "geometry": geometry,
                        "role": rollen.get(r["name"], "subject")})
        out.extend(self._bplan_locations(stufen[0], place_name))
        return out

    #: Ab diesem Flächenanteil im Ortsbereich gehört ein Bebauungsplan auf die
    #: Tafel. Niedriger als bei Straßen (0,5): Ein Plan wie „Fliegerhorst/
    #: Alexanderstraße" liegt zu einem guten Teil im Nachbarbereich, und wer
    #: den Beschluss dazu auf der Tafel sieht, soll auch die Fläche sehen.
    BPLAN_MIN_SHARE = 0.3

    def _bplan_locations(self, titles: list[str], place_name: str) -> list[dict]:
        """Die Geltungsbereiche der Bebauungspläne, die die Beschlusstitel eines
        Vorhabens nennen (``bplan.plannummern_im_titel``) — als Fläche auf der
        Karte, wo OpenStreetMap noch nichts kennt, weil noch nichts gebaut ist.

        Je Titel gilt der erste Schlüssel, zu dem es einen Umring gibt: die
        Änderung vor dem Ursprungsplan. Ein Plan zählt nur, wenn er zu
        ``BPLAN_MIN_SHARE`` in diesem Ortsbereich liegt — sonst zöge ein
        stadtweit genannter Plan Flächen aus fremden Vierteln herein.
        """
        from council import bplan, geo
        je_titel = [bplan.plannummern_im_titel(t) for t in titles]
        alle = [k for keys in je_titel for k in keys]
        if not alle:
            return []
        umringe = self.bplan_outlines_by_keys(alle)
        out: list[dict] = []
        gesehen: set[str] = set()
        for keys in je_titel:
            treffer = next((umringe[k] for k in keys if k in umringe), None)
            if not treffer or treffer["key"] in gesehen:
                continue
            gesehen.add(treffer["key"])
            try:
                geometrie = json.loads(treffer["geojson"])
            except (TypeError, ValueError):
                continue
            anteile = geo.ortsbereiche_der_geometrie(geometrie)
            gesamt = sum(anteile.values()) or 1
            if anteile.get(place_name, 0) / gesamt < self.BPLAN_MIN_SHARE:
                continue
            if treffer["lat"] is None or treffer["lon"] is None:
                continue
            out.append({
                "slug": f"bplan-{treffer['key'].lower().replace(' ', '-')}",
                "name": f"Bebauungsplan {treffer['nr']}",
                "kind": "bplan", "lat": treffer["lat"], "lon": treffer["lon"],
                "geometry": geometrie, "role": "subject",
                "plan": {
                    "nr": treffer["nr"], "name": treffer["name"], "status": treffer["status"],
                    "resolution_date": treffer["resolution_date"],
                    "adoption_date": treffer["adoption_date"],
                    "effective_date": treffer["effective_date"],
                    "note": treffer["note"],
                    "source": bplan.QUELLE_LABEL, "source_url": bplan.QUELLE_URL,
                },
            })
        return out

    def _place_name(self, place_id: str) -> str:
        place = self.resolve_place(place_id)
        return place.name if place else place_id

    def district_projects_overview(self, *, min_confidence: int = PROJECT_MIN_CONFIDENCE) -> dict[str, dict]:
        """Je Ortsbereich: wie viele Vorhaben, wann zuletzt etwas dazukam."""
        try:
            rows = self._conn.execute(
                "SELECT place_id, COUNT(*) AS n, MAX(last_date) AS last_date, MAX(updated_at) AS updated_at "
                "FROM council_district_projects WHERE confidence >= ? GROUP BY place_id",
                (min_confidence,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        out = {r["place_id"]: {"count": r["n"], "last_date": r["last_date"], "updated_at": r["updated_at"],
                               "stages": {}}
               for r in rows}
        # Die Stände je Ortsbereich tragen die Wärmekarte der Auswahl: Wo
        # gebaut wird, ist mehr los als wo nur eine Idee steht.
        for r in self._conn.execute(
                "SELECT place_id, stage, COUNT(*) AS n FROM council_district_projects "
                "WHERE confidence >= ? GROUP BY place_id, stage", (min_confidence,)):
            out[r["place_id"]]["stages"][r["stage"]] = r["n"]
        return out

    #: Reihenfolge der Stände für die Stadt-Highlights: was gerade passiert,
    #: zuerst. Abgelehnt und fertig sind kein Blickfang.
    _HIGHLIGHT_ORDER = ("building", "decided", "planning", "idea")

    def district_highlights(self, *, limit: int = 6,
                            min_confidence: int = PROJECT_MIN_CONFIDENCE) -> list[dict]:
        """Die Vorhaben, die stadtweit gerade am meisten hergeben — für die
        Auswahl-Seite, bevor man ein Viertel gewählt hat.

        Reihenfolge: im Bau vor beschlossen vor Planung, dazwischen die mit
        Termin vor denen ohne, dann das jüngste zuerst. Und **je Ortsbereich
        höchstens eines**, solange die Auswahl reicht: Sechs Karten aus
        Eversten sagen nichts über die Stadt, sie sagen, dass Eversten groß ist.
        Vorhaben, die zwei Konten als falsch verortet gemeldet haben, bleiben
        weg — wie auf der Tafel.
        """
        order = " ".join(f"WHEN '{s}' THEN {i}" for i, s in enumerate(self._HIGHLIGHT_ORDER))
        try:
            rows = self._conn.execute(
                "SELECT p.id, p.project_key, p.place_id, p.name, p.what, p.stage, p.when_text, "
                "p.category, p.last_date, (SELECT COUNT(*) FROM council_district_project_reports r "
                "WHERE r.project_key = p.project_key) AS report_count "
                "FROM council_district_projects p WHERE p.confidence >= ? "
                f"AND p.stage IN ({','.join('?' * len(self._HIGHLIGHT_ORDER))}) "
                f"ORDER BY CASE p.stage {order} ELSE 9 END, (p.when_text IS NULL), p.last_date DESC, p.id "
                "LIMIT ?", (min_confidence, *self._HIGHLIGHT_ORDER, limit * 8)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        rows = [r for r in rows if r["report_count"] < PROJECT_HIDE_REPORTS]
        gewaehlt: list = []
        gesehen: set[str] = set()
        for r in rows:
            if r["place_id"] in gesehen:
                continue
            gesehen.add(r["place_id"])
            gewaehlt.append(r)
            if len(gewaehlt) >= limit:
                break
        if len(gewaehlt) < limit:
            rest = [r for r in rows if r not in gewaehlt]
            gewaehlt.extend(rest[: limit - len(gewaehlt)])
        return [{
            "id": r["id"], "place_id": r["place_id"], "place_name": self._place_name(r["place_id"]),
            "name": r["name"], "what": r["what"], "stage": r["stage"], "when": r["when_text"],
            "category": r["category"], "last_date": r["last_date"],
        } for r in gewaehlt]

    def district_lookup_streets(self, q: str, *, limit: int = 6) -> list[dict]:
        """Straßen und Plätze zu einer Eingabe, mit dem Ortsbereich, in dem sie
        liegen — die Antwort auf „Ich wohne in der …".

        Nur Orte, die ein Beschluss je genannt hat (das ist der Bestand von
        ``council_locations``), und nur mit einem Flächenanteil ab
        ``CANDIDATE_MIN_SHARE``: Eine Straße, die durch drei Viertel läuft,
        bekommt das, in dem ihr größtes Stück liegt. Ein Anfang gewinnt vor
        einem Treffer mittendrin, Kürzeres vor Längerem — „Haupt" soll die
        Hauptstraße zeigen, nicht „Hauptstraße 12–14".
        """
        q = (q or "").strip()
        if len(q) < 2:
            return []
        like = q.replace("%", "").replace("_", "")
        try:
            rows = self._conn.execute(
                "SELECT l.slug, l.name, l.kind, ld.place_id, MAX(ld.share) AS share "
                "FROM council_locations l JOIN council_location_districts ld ON ld.location_slug = l.slug "
                "WHERE l.kind IN ('street', 'square') AND ld.place_id IS NOT NULL AND ld.share >= ? "
                "AND l.name LIKE ? ESCAPE '\\' "
                "GROUP BY l.slug ORDER BY (l.name LIKE ? ESCAPE '\\') DESC, LENGTH(l.name), l.name LIMIT ?",
                (CANDIDATE_MIN_SHARE, f"%{like}%", f"{like}%", limit * 3)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        # „Ziegelhofstr", „Ziegelhofstraße" und „Ziegelhofstr. 125-127" sind
        # derselbe Ort; Abkürzung und Hausnummer sind nur die Schreibweise
        # einer Vorlage. Je Schlüssel bleibt die ausgeschriebene Form ohne
        # Nummer — sie ist die, die man selbst eintippen würde.
        beste: dict[tuple[str, str], sqlite3.Row] = {}
        reihenfolge: list[tuple[str, str]] = []
        for r in rows:
            key = (_street_key(r["name"]), r["place_id"])
            if key not in beste:
                beste[key] = r
                reihenfolge.append(key)
            elif _street_rank(r["name"]) > _street_rank(beste[key]["name"]):
                beste[key] = r
        return [{"slug": r["slug"], "name": r["name"], "kind": r["kind"],
                 "place_id": r["place_id"], "place_name": self._place_name(r["place_id"])}
                for r in (beste[k] for k in reihenfolge[:limit])]

    def district_projects_updated_at(self, place_id: str) -> str | None:
        try:
            row = self._conn.execute(
                "SELECT MAX(updated_at) FROM council_district_projects WHERE place_id = ?",
                (place_id,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return row[0] if row else None

    def save_district_project_report(self, project_key: str, place_id: str, owner_id: int,
                                     reason: str | None) -> bool:
        """„Gehört nicht hierher" — einmal je Konto und Vorhaben. False, wenn schon gemeldet."""
        with self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO council_district_project_reports "
                "(project_key, place_id, owner_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_key, place_id, owner_id, (reason or "")[:300] or None, _now()))
        return cur.rowcount == 1

    def district_project_by_id(self, project_id: int) -> dict | None:
        try:
            row = self._conn.execute(
                "SELECT id, place_id, project_key, name FROM council_district_projects WHERE id = ?",
                (project_id,)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return dict(row) if row else None

    def district_project_report_count(self, project_key: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM council_district_project_reports WHERE project_key = ?",
            (project_key,)).fetchone()
        return int(row[0]) if row else 0

    def district_project_reports_by(self, owner_id: int, place_id: str) -> set[str]:
        try:
            rows = self._conn.execute(
                "SELECT project_key FROM council_district_project_reports WHERE owner_id = ? AND place_id = ?",
                (owner_id, place_id)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return set()
        return {r[0] for r in rows}

    # -------------------------------------------------------- Weitere Quellen

    def district_location_names(self, place, *, kinds: tuple[str, ...] | None = None,
                                min_share: float = CANDIDATE_MIN_SHARE) -> list[str]:
        """Die Ortsnamen des Ortsbereichs (länge-absteigend, längster Treffer gewinnt)."""
        sql = ("SELECT DISTINCT l.name FROM council_locations l JOIN council_location_districts ld "
               "ON ld.location_slug = l.slug WHERE (ld.place_id = ? OR ld.district = ?) AND ld.share >= ?")
        args: list = [place.id, place.name, min_share]
        if kinds:
            sql += f" AND l.kind IN ({','.join('?' * len(kinds))})"
            args += list(kinds)
        rows = self._conn.execute(sql, args).fetchall()
        return sorted({r[0] for r in rows if r[0] and len(r[0]) >= 6}, key=len, reverse=True)

    def district_investments(self, place) -> list[dict]:
        """Vorhaben des jüngsten Investitionsprogramms, deren Bezeichnung eine
        Straße oder einen Platz des Ortsbereichs nennt — mit Programmjahr und Summe."""
        try:
            jahr = self._conn.execute(
                "SELECT MAX(year) FROM council_investment_measures").fetchone()[0]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        if not jahr:
            return []
        names = self.district_location_names(place, kinds=_INVESTMENT_LOCATION_KINDS)
        if not names:
            return []
        rows = self._conn.execute(
            "SELECT code, label, grand_total FROM council_investment_measures "
            "WHERE year = ? AND level = 'measure' AND grand_total > 0 ORDER BY grand_total DESC",
            (jahr,)).fetchall()
        out = []
        for r in rows:
            label = r["label"] or ""
            for name in names:
                if re.search(re.escape(name) + r"(?![a-zäöüß])", label, re.IGNORECASE):
                    out.append({"programme_year": jahr, "code": r["code"], "label": label,
                                "total_eur": r["grand_total"], "location": name})
                    break
        return out

    def district_upcoming_items(self, place, *, days: int = 60) -> list[dict]:
        """Tagesordnungspunkte kommender Sitzungen, deren Titel einen Ort des
        Ortsbereichs (oder ihn selbst) nennt — der Haken für „Mitreden": Da
        wird demnächst entschieden, und Einwohner*innen dürfen fragen."""
        from council.locations import affects_whole_city
        today = date.today().isoformat()
        bis = date.fromordinal(date.today().toordinal() + days).isoformat()
        # Nur Straßen, Plätze, Flächen — ein Gebäude wie das Klinikum steht
        # zwar im Viertel, wirkt aber stadtweit; das ist die Erfahrung der
        # zweiten Stufe, und hier gibt es keine.
        names = self.district_location_names(place, kinds=("street", "square", "area", "water")) + [place.name]
        rows = self._conn.execute(
            "SELECT a.id, a.ksinr, a.item_number, a.title, a.kvonr, se.session_date, se.session_time, "
            "se.committee FROM council_agenda_items a JOIN council_sessions se ON se.ksinr = a.ksinr "
            "WHERE se.session_date >= ? AND se.session_date <= ? AND a.is_public = 1 "
            "ORDER BY se.session_date, se.session_time, a.id", (today, bis)).fetchall()
        out = []
        for r in rows:
            title = r["title"] or ""
            if affects_whole_city(title):
                continue
            hit = next((n for n in names if re.search(re.escape(n) + r"(?![a-zäöüß])", title, re.IGNORECASE)), None)
            if hit:
                out.append({"id": r["id"], "ksinr": r["ksinr"], "item_number": r["item_number"],
                            "title": title, "kvonr": r["kvonr"], "session_date": r["session_date"],
                            "session_time": r["session_time"], "committee": r["committee"], "location": hit})
        return out

    def district_participations(self, place) -> list[dict]:
        """Laufende Bauleitplan-Beteiligungen (planungsbeteiligung.de) mit Ortsbezug hierher."""
        names = self.district_location_names(place) + [place.name]
        out = []
        for b in self.list_beteiligungen(nur_laufende=True):
            text = f"{b.get('title') or ''} {b.get('ort') or ''}"
            if any(re.search(re.escape(n) + r"(?![a-zäöüß])", text, re.IGNORECASE) for n in names):
                out.append({"title": b.get("title"), "place": b.get("ort"), "step": b.get("schritt"),
                            "valid_from": b.get("valid_from"), "valid_until": b.get("valid_until"),
                            "url": b.get("url"), "plan_nrs": b.get("plan_nrs") or []})
        return out


def _street_key(name: str) -> str:
    """Schreibweisen einer Straße auf einen Schlüssel: Hausnummern weg,
    „straße"/„str."/„str" gleich."""
    base = re.sub(r"[\s.,]*\d.*$", "", name).lower().strip()
    return re.sub(r"stra(ß|ss)e\b|str\.?\b", "str", base)


def _street_rank(name: str) -> int:
    """Welche Schreibweise gezeigt wird: ohne Hausnummer vor mit, ausgeschrieben vor abgekürzt."""
    return (0 if re.search(r"\d", name) else 2) + (1 if re.search(r"stra(ß|ss)e", name, re.IGNORECASE) else 0)


#: Wörter, die vor einem Ortsnamen sagen: Das ist eine GRENZE des Abschnitts,
#: nicht der Ort, an dem sich etwas ändert. „Tweelbäker Tredde (Am Schmeel bis
#: Brahmweg)" baut die Tredde aus — Am Schmeel und Brahmweg bleiben, wie sie
#: sind (Tims Befund 06.09.2026: als Linie markiert sahen sie betroffen aus).
_GRENZWORT = r"(?:zwischen|von|vom|ab|bis|bis\s+zur|bis\s+zum|bis\s+an|in\s+höhe|höhe|und)"
_GRENZ_VOR_RE = re.compile(_GRENZWORT + r"\s+(?:der|dem|des|die|das)?\s*$", re.IGNORECASE)


def ortsrollen(names: list[str], texts: list[str], kinds: dict[str, str] | None = None) -> dict[str, str]:
    """Je Ortsname ``subject`` (dort ändert sich etwas), ``boundary`` (nur
    Abschnittsgrenze: „von X bis Y") oder ``context`` (eine Straße, die den
    Ort nur benennt: „Quartier Am Schmeel", „Flächen Am Schmeel/Brahmweg").

    ``texts`` sind Stufen in absteigender Verbindlichkeit (Titel, Zusammen-
    fassung, Beschlusstext, Vorlage, Fundstelle der Orts-Pipeline). **Die
    erste Stufe, die den Namen nennt, entscheidet.** Dort ist er Grenze, wenn
    jede Fundstelle hinter einem Grenzwort steht („zwischen X und Y", „von X
    bis Y", „(X bis Y)", „ab X", „in Höhe X") oder in einem Satz übers
    Straßennetz („bindet … an"). Eine **Straße** (``kinds``) ist darüber
    hinaus nur Gegenstand, wenn ein Satz mit ihr von Bauen an der Straße
    spricht (Ausbau, Sanierung, Kreuzung, Radweg, …) — sonst ist sie Bezug:
    Beim Wohnquartier Krusenbusch stehen Am Schmeel, Tredde und Brahmweg in
    jedem Titel, gebaut wird auf den Flächen dahinter. Flächen, Gebäude und
    Plätze bleiben Gegenstand, sobald sie frei stehen.

    Warum Stufen und nicht ein Blob: Die Vorlage erzählt auch drumherum —
    über alle Fundstellen gerechnet machte ein Satz übers Straßennetz Am
    Schmeel wieder zum Gegenstand, obwohl der Titel „(Am Schmeel bis
    Brahmweg)" die Rolle längst geklärt hat (Krusenbusch, 06.09.2026). Kommt
    ein Name nirgends vor (Katalog-Variante), bleibt er Gegenstand: Lieber
    einmal zu viel markiert als still verschwunden.
    """
    rollen: dict[str, str] = {}
    for name in names:
        muster = re.compile(re.escape(name) + r"(?![a-zäöüß])", re.IGNORECASE)
        rollen[name] = "subject"
        for blob in texts:
            treffer = list(muster.finditer(blob or ""))
            if not treffer:
                continue
            if all(_ist_grenzfund(blob, m) for m in treffer):
                rollen[name] = "boundary"
            elif (kinds or {}).get(name) == "street" and not any(_BAUWORT_RE.search(_satz(blob, m)) for m in treffer):
                rollen[name] = "context"
            break
    return rollen


_BEZUGSSATZ_RE = re.compile(r"\b(?:bindet|binden|anbind|angebunden|Anbindung)", re.IGNORECASE)
#: Woran man erkennt, dass an der Straße selbst gebaut wird.
_BAUWORT_RE = re.compile(
    r"ausbau|ausgebaut|sanier|umbau|umgebaut|neubau|erneuer|instandsetz|straßenbau|fahrbahn|gehweg|radweg"
    r"|fußweg|querung|kreuzung|einmündung|verkehrsberuhig|tempo|sperrung|umleitung|beleuchtung|stellplätz"
    r"|baumaßnahm|bauabschnitt|umgestalt|markierung|ampel|lichtsignal|haltestelle|asphalt|pflaster|parkplatz"
    r"|straßenraum|verkehrsführung|einbahn|schulweg|zebrastreifen|fahrradstraße|straßenverkehr|verkehrssicher",
    re.IGNORECASE)


def _satz(blob: str, m: re.Match) -> str:
    # Satzgrenze ist der Punkt (oder eine Leerzeile zwischen zwei Titeln),
    # nicht der Zeilenumbruch — der PDF-Text der Vorlagen bricht mitten im
    # Satz um („die Straßen\nDießelweg, …").
    anfang = max(blob.rfind(z, 0, m.start()) for z in (".", "!", "?", "\n\n")) + 1
    ende = min((i for i in (blob.find(z, m.end()) for z in (".", "!", "?", "\n\n")) if i >= 0), default=len(blob))
    return blob[anfang:ende]


def _ist_grenzfund(blob: str, m: re.Match) -> bool:
    davor = blob[max(0, m.start() - 40):m.start()]
    danach = blob[m.end():m.end() + 12]
    if _GRENZ_VOR_RE.search(davor):
        return True
    # „… bindet die Straßen Dießelweg und Brahmweg an die Straße Am Schmeel
    # an": ein Satz über das Straßennetz, kein Vorhaben an diesen Straßen.
    if _BEZUGSSATZ_RE.search(_satz(blob, m)):
        return True
    if not re.match(r"\s*(?:bis|und)\s", danach, re.IGNORECASE):
        return False
    return ("zwischen" in davor.lower() or "(" in davor[-3:] or bool(re.search(r"\bvon\b", davor, re.IGNORECASE))
            or re.match(r"\s*bis\s", danach, re.IGNORECASE) is not None)


def _months_ago(months: int) -> str:
    heute = date.today()
    monat = heute.month - months
    jahr = heute.year
    while monat <= 0:
        monat += 12
        jahr -= 1
    return date(jahr, monat, min(heute.day, 28)).isoformat()


def project_key_ids(project: dict) -> list[int]:
    """Hilfe für Tests und Skripte: die Beschluss-IDs eines Vorhabens, sortiert."""
    return sorted({int(i) for i in project.get("decision_ids") or []})


__all__ = ["ViertelMixin", "PROJECT_MIN_CONFIDENCE", "PROJECT_HIDE_REPORTS", "CANDIDATE_MONTHS",
           "CANDIDATE_MIN_SHARE", "project_key_ids", "ortsrollen", "json"]
