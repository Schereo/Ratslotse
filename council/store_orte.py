"""Orte: Katalog, Geocodierung, Stadtteile, Kartenpunkte.

**Der zweite Schnitt an ``store.py``** (nach dem Haushalt). Wie dort über den
Aufrufkegel bestimmt: was die vier Orts-Endpunkte (``/places``,
``/place/{id}``, ``/districts``, ``/entities-map``) und die beiden
Geocoding-Skripte am Store aufrufen, plus deren eigene Aufrufe an ``self``.

Sechs allgemeine Beschluss-Helfer sind ausdrücklich drüben geblieben
(``_decision_where``, ``search_decisions``, ``count_decisions``,
``_decision_row``, ``decision_ids_for_party``, ``close``): Die Orts-Seiten
BENUTZEN sie, aber sie gehören dem Beschluss-Kern. Gemessen: Keine der hier
umgezogenen Methoden ruft eine davon — die Grenze läuft also wirklich
dazwischen.

Was hier liegt, ist die Ortszuordnung in ihren zwei Hälften: das Nachtragen
(``backfill_*``, ``rebuild_*``, ``fix_*``, ``merge_location_variants``) und
das Abfragen (``all_places``, ``public_place``, ``city_map_points``,
``location_matches_for_decisions``). Beide Hälften sind aufeinander
angewiesen und lagen bisher über 900 Zeilen verstreut.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

#: Ortsarten, die einen PUNKT auf der Karte rechtfertigen — im Unterschied zu
#: Sammelbegriffen („Innenstadt") und Verwaltungsebenen.
CONCRETE_LOCATION_KINDS = {

    "street", "square", "building", "water",
    "facility", "structure", "route",
}


class OrteMixin:
    """Die Orts-Abfragen von :class:`council.store.CouncilStore`.

    Nur zum Mitvererben; ``self._conn`` und die Beschluss-Helfer kommen
    von dort.
    """

    def _reviewed_places(self) -> tuple:
        """Als eigene Orte freigegebene Kandidaten im Katalogformat liefern."""
        from council import places

        rows = self._conn.execute(
            """SELECT r.*, l.name AS observed_name, l.lat, l.lon
               FROM council_place_reviews r
               JOIN council_locations l ON l.slug = r.location_slug
               WHERE r.status = 'approved' ORDER BY COALESCE(r.name,l.name)"""
        ).fetchall()
        static = {place.id: place for place in places.all_places()}
        out = []
        for row in rows:
            parent = static.get(row["parent_id"])
            if parent and not parent.is_primary:
                parent = None
            try:
                aliases = tuple(str(value).strip() for value in json.loads(row["aliases"] or "[]")
                                if str(value).strip())
            except (TypeError, json.JSONDecodeError):
                aliases = ()
            observed = (row["observed_name"] or "").strip()
            if observed and observed.casefold() != (row["name"] or observed).casefold():
                aliases = tuple(dict.fromkeys((*aliases, observed)))
            out.append(places.Place(
                id=row["place_id"] or row["location_slug"],
                name=row["name"] or observed,
                kind=row["kind"] or "neighborhood",
                aliases=aliases,
                electoral_districts=parent.electoral_districts if parent else (),
                parent_ids=(parent.id,) if parent else (),
                description=row["description"] or None,
                source_ids=(),
                filterable=True,
                quiz_enabled=bool(row["quiz_enabled"]),
                lat=row["lat"], lon=row["lon"],
            ))
        return tuple(out)

    def all_places(self) -> tuple:
        """Versionierter Basiskatalog plus redaktionell freigegebene Orte."""
        from dataclasses import replace
        from council import places
        if self._runtime_places_cache is None:
            base = [*places.all_places(), *self._reviewed_places()]
            alias_values: dict[str, list[str]] = {}
            for row in self._conn.execute(
                """SELECT r.canonical_place_id,r.aliases,l.name
                   FROM council_place_reviews r
                   JOIN council_locations l ON l.slug=r.location_slug
                   WHERE r.status='alias' AND r.canonical_place_id IS NOT NULL"""
            ):
                values = [row["name"]]
                try:
                    values += [str(value).strip() for value in json.loads(row["aliases"] or "[]")
                               if str(value).strip()]
                except (TypeError, json.JSONDecodeError):
                    pass
                alias_values.setdefault(row["canonical_place_id"], []).extend(values)
            self._runtime_places_cache = tuple(
                replace(place, aliases=tuple(dict.fromkeys((*place.aliases, *alias_values[place.id]))))
                if place.id in alias_values else place
                for place in base
            )
        return self._runtime_places_cache

    def resolve_place(self, value: str | None):
        """Statische und freigegebene Orte sowie geprüfte Aliase auflösen."""
        from council import places
        from council.locations import location_slug

        static = places.resolve(value)
        if static:
            return static
        key = location_slug(value or "")
        if not key:
            return None
        for place in self.all_places():
            if key in {location_slug(v) for v in (place.id, place.name, *place.aliases)}:
                return place
        if self._place_aliases_cache is None:
            self._place_aliases_cache = {
                row["location_slug"]: row["canonical_place_id"]
                for row in self._conn.execute(
                    "SELECT location_slug,canonical_place_id FROM council_place_reviews "
                    "WHERE status='alias' AND canonical_place_id IS NOT NULL")
            }
        canonical_place_id = self._place_aliases_cache.get(key)
        if canonical_place_id:
            return next((place for place in self.all_places()
                         if place.id == canonical_place_id), None)
        return None

    def primary_parents(self, place) -> tuple:
        if not place:
            return ()
        if place.is_primary:
            return (place,)
        parents = {candidate.id: candidate for candidate in self.all_places()
                   if candidate.is_primary}
        return tuple(parents[parent_id] for parent_id in place.parent_ids
                     if parent_id in parents)

    def public_place(self, place) -> dict:
        """API-Darstellung eines statischen oder redaktionellen Orts."""
        from dataclasses import asdict
        from council import places

        if places.resolve(place.id):
            return places.public_place(place)
        row = asdict(place)
        row["kind_label"] = places.kind_label(place.kind)
        row["parents"] = [
            {"id": parent.id, "name": parent.name, "kind": parent.kind}
            for parent in self.primary_parents(place)
        ]
        review = self._conn.execute(
            "SELECT source_url FROM council_place_reviews WHERE place_id=? AND status='approved'",
            (place.id,),
        ).fetchone()
        row["sources"] = ([{"id": "redaktionell", "type": "web",
                            "title": "Redaktionell geprüfte Quelle",
                            "url": review["source_url"]}]
                          if review and review["source_url"] else [])
        return row

    def public_place_catalog(self) -> dict:
        from council import places
        data = places.public_catalog()
        data["places"] = [self.public_place(place) for place in self.all_places()]
        return data

    @staticmethod
    def _place_location_condition(place, *, nur_hauptbereich: bool = False) -> tuple[str, list]:
        """SQL-Bedingung auf Alias ``l`` für einen kanonischen Katalogort.

        ``nur_hauptbereich`` schaltet die Mehrfach-Zugehörigkeit ab. Zwei
        Fragen, die verschieden zu beantworten sind:

        *„Welche Beschlüsse betreffen den Ziegelhof?"* — die Alexanderstraße
        läuft dort durch, also gehört „Ausbauplanung Alexanderstraße" dazu.
        Weite Bedingung.

        *„Welche THEMEN schlage ich für den Ziegelhof vor?"* — hier zählt eine
        Entität mit, sobald sie in irgendeinem Beschluss zusammen mit der
        Alexanderstraße vorkommt. Mit der weiten Bedingung schlug das
        Ehnernviertel plötzlich „Hallensichel-Ost" und „Entlastungsstraße
        Fliegerhorst" vor — Fliegerhorst-Themen, die über eine Straße
        hereingeschwappt sind und die richtigen Vorschläge verdrängten.
        Deshalb hier der Hauptbereich.

        Die Vorschläge sind damit eine Teilmenge des Beschlussfilters, nie das
        Gegenteil: Was vorgeschlagen wird, findet sich auch im Filter wieder.
        """
        from council.locations import location_slug

        if place.is_primary and nur_hauptbereich:
            return "(l.local_area_id = ? OR l.district = ?)", [place.id, place.name]
        if place.is_primary:
            # ZUSÄTZLICH über die Zugehörigkeits-Tabelle, nicht statt der
            # Spalte. Eine Straße durch fünf Ortsbereiche gehört in alle fünf
            # Filter (siehe ``rebuild_location_districts``) — aber die Spalte
            # bleibt daneben stehen: Sie ist immer gefüllt, die Tabelle wird
            # erst von einem Lauf aufgebaut. Landete der Code vor dem ersten
            # Lauf, fände der Stadtteil-Filter sonst gar nichts mehr. So kann
            # er nur mehr finden als vorher, nie weniger.
            return ("(l.local_area_id = ? OR l.district = ? OR l.slug IN ("
                    "SELECT location_slug FROM council_location_districts "
                    "WHERE place_id = ? OR district = ?))",
                    [place.id, place.name, place.id, place.name])
        slugs = list(dict.fromkeys(location_slug(value)
                                   for value in (place.name, *place.aliases)))
        return (f"(l.place_id = ? OR l.slug IN ({','.join('?' * len(slugs))}))",
                [place.id, *slugs])

    def decision_location_place_stats(self) -> list[dict]:
        """Belegte Katalogorte mit Beschlusszahlen, über stabile IDs gruppiert."""
        vote_ph = ",".join("?" * len(self._VOTE_OUTCOMES))
        report_ph = ",".join("?" * len(self._REPORT_OUTCOMES))
        out: list[dict] = []
        for place in self.all_places():
            if not place.filterable:
                continue
            condition, params = self._place_location_condition(place)
            row = self._conn.execute(
                f"""SELECT COUNT(DISTINCT dl.decision_id) AS count,
                           COUNT(DISTINCT CASE WHEN d.outcome IN ({vote_ph})
                                               THEN dl.decision_id END) AS vote_count,
                           COUNT(DISTINCT CASE WHEN d.outcome IN ({report_ph}) OR d.outcome IS NULL
                                               THEN dl.decision_id END) AS report_count
                    FROM council_decision_locations dl
                    JOIN council_locations l ON l.slug = dl.location_slug
                    JOIN council_decisions d ON d.id = dl.decision_id
                    WHERE {condition} AND d.kind = 'decision'""",
                [*self._VOTE_OUTCOMES, *self._REPORT_OUTCOMES, *params],
            ).fetchone()
            if row and row["count"]:
                out.append({"place_id": place.id, "name": place.name,
                            "count": row["count"], "vote_count": row["vote_count"],
                            "report_count": row["report_count"]})
        return out

    def location_matches_for_decisions(
        self,
        ids: list[int],
        *,
        district: str = "",
        location_slug: str = "",
        per_decision: int = 4,
    ) -> dict[int, list[dict]]:
        """Belegte Ortslinks eines Suchtreffers innerhalb eines Stadtteils.

        Die Fundstelle wird bewusst mitgeliefert: Der Filter soll nicht nur
        Treffer einschränken, sondern die Ortszuordnung in der Liste
        nachvollziehbar und damit manuell prüfbar machen.
        """
        if not ids or not (district or location_slug):
            return {}
        if location_slug:
            condition, condition_params = "l.slug = ?", [location_slug]
        else:
            place = self.resolve_place(district)
            if not place:
                return {}
            condition, condition_params = self._place_location_condition(place)
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"""SELECT dl.decision_id, l.name, l.district, l.place_id, l.local_area_id,
                       l.lat, l.lon, dl.source,
                       dl.evidence, dl.method, dl.confidence
                FROM council_decision_locations dl
                JOIN council_locations l ON l.slug = dl.location_slug
                WHERE dl.decision_id IN ({ph}) AND {condition}
                ORDER BY dl.decision_id, dl.confidence DESC, l.name""",
            [*ids, *condition_params],
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for row in rows:
            matches = out.setdefault(row["decision_id"], [])
            if len(matches) < max(1, int(per_decision)):
                matches.append({key: row[key] for key in (
                    "name", "district", "place_id", "local_area_id", "lat", "lon",
                    "source", "evidence", "method", "confidence"
                )})
        return out

    def locations_to_geocode(self, limit: int | None = None,
                             retry_failed: bool = False) -> list[dict]:
        """Orte, die noch geokodiert werden müssen.

        ``retry_failed`` nimmt auch die mit, bei denen es schon einmal
        misslungen ist (``geo_tried = 1``, aber keine Koordinaten). Ohne diesen
        Weg blieben sie für immer liegen: Auf Prod standen so 706 Orte, obwohl
        ein erneuter Versuch für „Postweg", „Stubbenweg", „Ziegelweg" und
        „Haaren" auf Anhieb Treffer lieferte — Overpass und Nominatim antworten
        nicht jeden Tag gleich.
        """
        bedingung = ("(l.geo_tried = 0 OR l.lat IS NULL)" if retry_failed
                     else "l.geo_tried = 0")
        sql = (
            "SELECT l.slug, l.name, l.kind, COUNT(dl.decision_id) AS n "
            "FROM council_locations l JOIN council_decision_locations dl "
            f"ON dl.location_slug = l.slug WHERE {bedingung} "
            "GROUP BY l.slug ORDER BY n DESC, l.name"
        )
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (int(limit),)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def location_districts(self, slugs: list[str]) -> dict[str, set[str]]:
        """Zu welchen Ortsbereichen ein Ort gehört — je Slug, klein geschrieben.

        Ein Ort kann in mehreren liegen (die Alexanderstraße in fünf). Wer
        wissen will, ob etwas im eigenen Stadtteil liegt, fragt hier und nicht
        die eine Hauptspalte ``council_locations.district``.
        """
        slugs = [s for s in slugs if s]
        if not slugs:
            return {}
        platz = ",".join("?" * len(slugs))
        out: dict[str, set[str]] = {}
        for r in self._conn.execute(
            f"SELECT location_slug, district FROM council_location_districts "
            f"WHERE location_slug IN ({platz})", slugs).fetchall():
            out.setdefault(r["location_slug"], set()).add((r["district"] or "").casefold())
        return out

    def street_locations_to_refine(self, limit: int | None = None) -> list[dict]:
        """Straßen ohne vollständige Geometrie — Einzelsegment oder gar keine.

        Nominatim gibt zu einem Straßennamen den Weg zurück, der zufällig
        zuerst passt — bei „Tweelbäker Tredde" ein 800-m-Stück von 2,4 km.
        Overpass gibt alle Segmente (``MultiLineString``). Woran man das
        auseinanderhält: an der Geometrie-Art. Alles, was für eine Straße
        KEIN ``MultiLineString`` ist, stammt aus dem Einzel-Segment-Weg.

        Ohne Geometrie zählen sie mit: Bei ihnen hat der Geocoder einmal
        nichts gefunden (``geo_tried = 1``, kein Umriss) — im
        Straßen-Schnappschuss stehen sie trotzdem oft.

        Das ist eine Reparatur des Bestands, kein Dauerlauf: Neue Orte gehen
        seit der ``kind``-Weiche in ``geocode_entities._is_street`` von
        vornherein an Overpass. Am Prod-Bestand (03.09.2026) betrifft es 430
        Straßen mit Einzelsegment, 96 davon mit einem Namen, den kein Muster
        als Straße erkennt, plus 140 ohne jede Geometrie.
        """
        sql = (
            "SELECT l.slug, l.name, l.kind, l.geojson, COUNT(dl.decision_id) AS n "
            "FROM council_locations l LEFT JOIN council_decision_locations dl "
            "ON dl.location_slug = l.slug "
            "WHERE l.kind IN ('street','square') "
            "AND (l.geojson IS NULL OR l.geojson NOT LIKE '%MultiLineString%') "
            "GROUP BY l.slug ORDER BY n DESC, l.name"
        )
        args: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            args = (int(limit),)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def street_location_names(self) -> list[str]:
        """Die Namen ALLER Straßen und Plätze — der Prüfstein für einen
        Straßen-Schnappschuss.

        Ob eine Schnappschuss-Datei zu dieser Stadt gehört, misst man an der
        Überdeckung mit dem gesamten Bestand, nicht an der Zahl der
        Änderungen: Ist alles Reparierbare repariert, ändert ein richtiger
        Schnappschuss null Zeilen — und wäre nach der einfachen Regel
        fälschlich „die falsche Datei".
        """
        return [r["name"] for r in self._conn.execute(
            "SELECT name FROM council_locations "
            "WHERE kind IN ('street','square') AND name IS NOT NULL AND name <> ''")]

    def street_entities_to_refine(self) -> list[dict]:
        """Entitäten ohne vollständige Straßen-Geometrie.

        Eine Entität, die eine Straße IST („Nadorster Straße"), trägt ihren
        eigenen Punkt in ``council_entity_meta`` — er ist der Rückfall der
        Stadtteil-Zuordnung und der Pin auf der Stadtkarte. Auch er stammt aus
        demselben Einzel-Segment-Weg und ist damit derselbe Fehler.
        """
        return [dict(r) for r in self._conn.execute(
            "SELECT e.slug, e.name, m.geojson FROM council_entities e "
            "JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE e.kind IN ('place', 'project') "
            "AND (m.geojson IS NULL OR m.geojson NOT LIKE '%MultiLineString%')")]

    def apply_curated_location_geocodes(self) -> int:
        """Schwierige Ratsorte vor dem freien Geocoder reproduzierbar verorten."""
        from council import geo
        from council.locations import curated_location_geocodes

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        updates = []
        for slug, point in curated_location_geocodes().items():
            lat, lon = point["lat"], point["lon"]
            district = geo.ortsbereich_for(lat, lon)
            primary = self.resolve_place(district)
            updates.append((lat, lon, district, primary.id if primary else None,
                            now, slug, lat, lon))
        if not updates:
            return 0
        with self._conn:
            before = self._conn.total_changes
            self._conn.executemany(
                """UPDATE council_locations
                   SET lat=?,lon=?,geojson=NULL,district=?,local_area_id=?,
                       geo_tried=1,updated_at=?
                   WHERE slug=? AND (
                       lat IS NULL OR lon IS NULL OR ABS(lat-?) > 0.00000001
                       OR ABS(lon-?) > 0.00000001)""",
                updates,
            )
            changed = self._conn.total_changes - before
        if changed:
            self._runtime_places_cache = None
        return changed

    def hydrate_location_geo_from_entities(self) -> int:
        """Vorhandene, gleichnamige Entitäts-Geocodes ohne Netzaufruf übernehmen."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                """UPDATE council_locations
                   SET lat = (SELECT m.lat FROM council_entity_meta m
                              WHERE m.slug = council_locations.slug),
                       lon = (SELECT m.lon FROM council_entity_meta m
                              WHERE m.slug = council_locations.slug),
                       geojson = (SELECT m.geojson FROM council_entity_meta m
                                  WHERE m.slug = council_locations.slug),
                       geo_tried = 1, updated_at = ?
                   WHERE geo_tried = 0 AND EXISTS (
                       SELECT 1 FROM council_entity_meta m
                       WHERE m.slug = council_locations.slug
                         AND m.lat IS NOT NULL AND m.lon IS NOT NULL)""", (now,))
        return cur.rowcount

    def merge_location_variants(self) -> int:
        """Schreibvarianten desselben Ortes zu einem Eintrag zusammenführen.

        „Alte Fleiwa" und „AlteFleiwa", „Marschwegstadion" und
        „Marschweg-Stadion", „GS Röwekamp" und „Grundschule Röwekamp" standen
        als getrennte Orte in den Daten — mit getrennten Beschlusslisten, damit
        halbierten Zählern und zweimal derselben Sache in einer
        Vorschlagsliste. Am Prod-Bestand (01.09.2026): 66 Gruppen mit 132
        Einträgen.

        **Welche Schreibweise überlebt**, entscheidet in dieser Reihenfolge:
        die meisten Beschluss-Verweise (so schreibt es die Ratsverwaltung
        überwiegend); dann keine einzelnen Buchstaben-Fragmente (die stammen
        aus der PDF-Extraktion — „Kasin o- platz"); dann die meisten
        Buchstaben; zuletzt alphabetisch, damit der Lauf reproduzierbar ist.

        Geodaten und Stadtteil werden zusammengezogen: Hat der Gewinner keine,
        erbt er sie von einer Variante. Genau davon lebt der Fall „Kennedy
        straße" (stand auf Eversten) neben „Kennedystraße" (Bloherfelde) —
        nach dem Zusammenführen gibt es nur noch eine Antwort.
        """
        from council.locations import variant_key

        gruppen: dict[str, list] = {}
        for row in self._conn.execute(
            "SELECT slug,name,district,place_id,local_area_id,lat,lon,geojson,geo_tried,kind "
            "FROM council_locations"
        ).fetchall():
            gruppen.setdefault(variant_key(row["name"]), []).append(dict(row))

        zaehler = {r["location_slug"]: r["n"] for r in self._conn.execute(
            "SELECT location_slug, COUNT(*) AS n FROM council_decision_locations "
            "GROUP BY location_slug")}

        def rang(zeile):
            name = zeile["name"] or ""
            fragmente = sum(1 for w in re.findall(r"[^\W\d_]+", name) if len(w) == 1)
            return (-zaehler.get(zeile["slug"], 0), fragmente,
                    -sum(c.isalpha() for c in name), name)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        zusammengefuehrt = 0
        for _, zeilen in gruppen.items():
            if len(zeilen) < 2:
                continue
            zeilen.sort(key=rang)
            sieger, verlierer = zeilen[0], zeilen[1:]
            geerbt = {}
            for feld in ("district", "place_id", "local_area_id", "lat", "lon", "geojson"):
                if sieger[feld] is None:
                    for v in verlierer:
                        if v[feld] is not None:
                            geerbt[feld] = v[feld]
                            break
            with self._conn:
                for v in verlierer:
                    self._conn.execute(
                        "UPDATE OR IGNORE council_decision_locations SET location_slug=? "
                        "WHERE location_slug=?", (sieger["slug"], v["slug"]))
                    # Was beim Umhängen auf eine schon vorhandene Zeile stieß,
                    # ist eine Dublette und darf jetzt weg.
                    self._conn.execute(
                        "DELETE FROM council_decision_locations WHERE location_slug=?",
                        (v["slug"],))
                    self._conn.execute(
                        "UPDATE OR IGNORE council_place_reviews SET location_slug=? "
                        "WHERE location_slug=?", (sieger["slug"], v["slug"]))
                    self._conn.execute(
                        "DELETE FROM council_place_reviews WHERE location_slug=?", (v["slug"],))
                    self._conn.execute(
                        "DELETE FROM council_location_districts WHERE location_slug=?",
                        (v["slug"],))
                    self._conn.execute(
                        "DELETE FROM council_locations WHERE slug=?", (v["slug"],))
                if geerbt:
                    felder = ",".join(f"{k}=?" for k in geerbt)
                    self._conn.execute(
                        f"UPDATE council_locations SET {felder},updated_at=? WHERE slug=?",
                        (*geerbt.values(), now, sieger["slug"]))
            zusammengefuehrt += len(verlierer)
        return zusammengefuehrt

    def rebuild_location_districts(self) -> int:
        """Die Ortsbereichs-Zugehörigkeit neu aufbauen — mehrere je Ort erlaubt.

        ``council_locations.district`` trägt genau einen Stadtteil, den
        überwiegenden. Für die Anzeige ist das richtig; zum Filtern ist es zu
        wenig. Die Alexanderstraße verläuft zu 38 % in Bürgerfelde, zu 20 % in
        Alexandersfeld, zu 18 % im Ziegelhof, zu 13 % im Ehnernviertel und zu
        10 % in Dietrichsfeld — mit einer Spalte sehen vier Viertel ihre eigene
        Straße nicht. Am Prod-Bestand (01.09.2026) betrifft das 99 Orte mit
        zusammen rund 1.700 Beschluss-Zuordnungen.

        **Gleichnamige Orte bekommen nur ihren eigenen Bereich.** Die Fläche,
        die ein Kartendienst für „Ofenerdiek" liefert, schwappt nach Nadorst —
        aber unser Katalog-Umriss IST die Definition von Ofenerdiek. 25 solcher
        Orte gibt es; sie würden sonst ihre Nachbarn einfärben.
        """
        from council import geo, places

        eponym = set()
        for place in places.primary_places():
            eponym.update(v.strip().casefold() for v in (place.name, *place.aliases))
        nach_name = {p.name: p for p in places.primary_places()}

        zeilen = []
        for row in self._conn.execute(
            "SELECT slug,name,district,geojson FROM council_locations "
            "WHERE district IS NOT NULL"
        ).fetchall():
            bereiche = {row["district"]: 1.0}
            if (row["geojson"]
                    and (row["name"] or "").strip().casefold() not in eponym):
                stimmen = geo.ortsbereiche_der_geometrie(row["geojson"])
                gesamt = sum(stimmen.values()) or 1
                for name, punkte in stimmen.items():
                    anteil = punkte / gesamt
                    if (anteil >= self.ORTSBEREICH_ANTEIL
                            and punkte >= self.ORTSBEREICH_MINDESTPUNKTE):
                        bereiche[name] = max(bereiche.get(name, 0.0), anteil)
            for name, anteil in bereiche.items():
                place = nach_name.get(name)
                zeilen.append((row["slug"], name, place.id if place else None, anteil))
        with self._conn:
            self._conn.execute("DELETE FROM council_location_districts")
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_location_districts "
                "(location_slug,district,place_id,share) VALUES (?,?,?,?)", zeilen)
        return len(zeilen)

    def clear_code_only_districts(self) -> int:
        """Nackten Kennungen den Stadtteil nehmen — den Verweis aber lassen.

        „A 293", „A 29", „M-821": Diese Orte kommen über den Entitäten-Kanal
        herein, der weder durch die Ortsprüfung noch durch die Beiwerk-Regel
        läuft. Dass sie in einem Beschluss vorkommen, stimmt ja auch — die
        Autobahn wird erwähnt. Falsch ist nur der Stadtteil: Eine Autobahn
        quert die halbe Stadt, und „A 293 → Nadorst" schickt jemanden in ein
        Viertel, mit dem der Beschluss nichts zu tun hat.

        Deshalb bleibt der Verweis stehen und nur die Verortung fällt weg. Auf
        dem Prod-Bestand (01.09.2026) sind das sechs Zuordnungen.
        """
        from council.locations import _CODE_ONLY_RE

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        betroffen = [
            (now, row["slug"])
            for row in self._conn.execute(
                "SELECT slug, name FROM council_locations WHERE district IS NOT NULL")
            if _CODE_ONLY_RE.match((row["name"] or "").strip())
        ]
        if betroffen:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET district=NULL,local_area_id=NULL,"
                    "updated_at=? WHERE slug=?", betroffen)
        return len(betroffen)

    def backfill_location_districts(self) -> int:
        """Stadtteil für ältere oder übernommene Ortskoordinaten lokal ableiten.

        **Die Geometrie schlägt den Punkt.** Vorher entschied allein
        ``ortsbereich_for(lat, lon)`` — also der Mittelpunkt der Bounding-Box.
        Bei Flächen geht das; bei Straßen liegt dieser Punkt oft NEBEN der
        Straße, und der Ort blieb ohne Stadtteil. Auf dem Prod-Bestand
        (01.09.2026 gemessen) traf das u. a. „Alter Postweg" (verläuft
        vollständig in Kreyenbrück), „Ziegelweg", „Haaren" und „Tweelbäker See".
        Der Punkt bleibt der Rückfall für Orte ohne Geometrie.
        """
        from council import geo, places
        from council.locations import _CODE_ONLY_RE

        rows = self._conn.execute(
            "SELECT slug,name,lat,lon,geojson FROM council_locations "
            "WHERE lat IS NOT NULL AND lon IS NOT NULL "
            "AND (district IS NULL OR district = '')"
        ).fetchall()
        updates = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            # Nackte Kennungen bekommen keinen Stadtteil — siehe
            # ``clear_code_only_districts``. Der Riegel gehört HIER hin und
            # nicht nur ins Aufräumen: Sonst füllt der nächste Lauf wieder auf,
            # was der letzte gerade geleert hat.
            if _CODE_ONLY_RE.match((row["name"] or "").strip()):
                continue
            district = (geo.ortsbereich_der_geometrie(row["geojson"])
                        or geo.ortsbereich_for(row["lat"], row["lon"]))
            if district:
                place = places.resolve(district)
                updates.append((district, place.id if place else None, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET district=?,local_area_id=?,updated_at=? WHERE slug=?",
                    updates,
                )
        return len(updates)

    def fix_contradicting_districts(self) -> int:
        """Eingetragene Stadtteile korrigieren, die der Geometrie widersprechen.

        ``backfill_location_districts`` füllt nur LEERE Felder. Was einmal falsch
        drinsteht, bleibt — und auf dem Prod-Bestand (01.09.2026 geprüft) waren
        das 20 Orte mit zusammen 205 Beschluss-Zuordnungen: „Am Bahndamm" (65)
        stand auf Drielake, verläuft aber in Drielaker-Moor; „Sandweg" (49) auf
        Osternburg, liegt aber in Drielaker-Moor; „Bremer Straße" (28) umgekehrt.

        Korrigiert wird **nur der klare Widerspruch**: Der eingetragene Bereich
        wird von der Geometrie überhaupt nicht berührt. Eine Straße, die durch
        drei Bereiche läuft und mit einem davon eingetragen ist, bleibt
        unangetastet — sie ist nicht falsch, nur unvollständig.

        Und der neue Bereich braucht mindestens zwei Stützpunkte, damit nicht
        ein einzelner Ausreißer einer sonst fremden Geometrie entscheidet.
        """
        from council import geo, places

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        updates = []
        for row in self._conn.execute(
            "SELECT slug, district, geojson FROM council_locations "
            "WHERE district IS NOT NULL AND geojson IS NOT NULL"
        ).fetchall():
            stimmen = geo.ortsbereiche_der_geometrie(row["geojson"])
            if not stimmen or row["district"] in stimmen:
                continue
            name, gewicht = sorted(stimmen.items(), key=lambda t: (-t[1], t[0]))[0]
            if gewicht < 2:
                continue
            place = places.resolve(name)
            updates.append((name, place.id if place else None, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET district=?,local_area_id=?,updated_at=? "
                    "WHERE slug=?", updates)
        return len(updates)

    def fix_eponymous_districts(self) -> int:
        """Ein Ort, der EXAKT wie ein Stadtteil heißt, IST dieser Stadtteil.

        Auf Prod stand ein Ort namens „Drielake" (18 Zuordnungen) auf
        „Drielaker-Moor" — der Geocoder hatte für den Namen eine Fläche im
        Nachbarbereich gefunden. Bei exakter Namensgleichheit ist der Katalog
        stärker als jede Geokodierung; er ist die Definition des Bereichs.

        Bewusst nur EXAKTE Gleichheit (inkl. Aliasen), kein Teiltreffer:
        „Grundschule Drielake" bleibt der Geokodierung überlassen, denn eine
        Schule kann sehr wohl im Nachbarbereich stehen.
        """
        from council import places

        nach_name = {}
        for place in places.primary_places():
            for variante in (place.name, *place.aliases):
                nach_name[variante.casefold()] = place
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        updates = []
        for row in self._conn.execute(
            "SELECT slug, name, district FROM council_locations"
        ).fetchall():
            place = nach_name.get((row["name"] or "").strip().casefold())
            if place and row["district"] != place.name:
                updates.append((place.name, place.id, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET district=?,local_area_id=?,updated_at=? "
                    "WHERE slug=?", updates)
        return len(updates)

    def backfill_location_districts_from_name(self) -> int:
        """Stadtteil aus dem NAMEN des Ortes ableiten — der billige Rest.

        Viele Orte tragen ihren Stadtteil im eigenen Namen und werden trotzdem
        nie geocodiert: „Oberschule Ofenerdiek", „GS Drielake", „OBS Eversten",
        „Bürgerhaus Ofenerdiek", „Fliegerhorst-Innenstadt". Auf dem Prod-Bestand
        (01.09.2026) waren das 71 Orte mit 176 Beschluss-Zuordnungen, die ohne
        diese Regel unsichtbar blieben — kein Geocoder wird je „GS Drielake"
        finden.

        **Nur bei EINDEUTIGEM Treffer.** Nennt ein Name zwei Ortsbereiche
        („Entlastungsstraße Fliegerhorst-Wechloy"), bleibt der Ort lieber ohne
        Zuordnung als mit einer geratenen. Und nur, wo keine Koordinaten
        vorliegen: Wo es Geometrie gibt, ist die verlässlicher als ein Wortlaut.
        """
        import re

        from council import places

        muster = []
        for place in places.primary_places():
            namen = sorted({place.name, *place.aliases}, key=len, reverse=True)
            muster.append((place, re.compile(
                r"\b(" + "|".join(re.escape(n) for n in namen) + r")\b", re.IGNORECASE)))

        rows = self._conn.execute(
            "SELECT slug,name FROM council_locations "
            "WHERE lat IS NULL AND (district IS NULL OR district = '')"
        ).fetchall()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        updates = []
        for row in rows:
            treffer = [place for place, regex in muster if regex.search(row["name"] or "")]
            if len(treffer) == 1:
                updates.append((treffer[0].name, treffer[0].id, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET district=?,local_area_id=?,updated_at=? WHERE slug=?",
                    updates,
                )
        return len(updates)

    def backfill_location_place_ids(self) -> int:
        """Katalog- und Eltern-IDs für bestehende Ortsbeobachtungen nachziehen."""
        from council import geo

        rows = self._conn.execute(
            "SELECT slug,name,lat,lon,district,place_id,local_area_id FROM council_locations"
        ).fetchall()
        updates = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            exact = self.resolve_place(row["name"])
            primary = self.resolve_place(row["district"])
            if primary and not primary.is_primary:
                primary = None
            if not primary and exact:
                parents = self.primary_parents(exact)
                primary = parents[0] if len(parents) == 1 else None
            if not primary and row["lat"] is not None and row["lon"] is not None:
                primary = self.resolve_place(geo.ortsbereich_for(row["lat"], row["lon"]))
            place_id = exact.id if exact else None
            primary_id = primary.id if primary else None
            primary_name = primary.name if primary else row["district"]
            if (place_id, primary_id, primary_name) != (
                    row["place_id"], row["local_area_id"], row["district"]):
                updates.append((place_id, primary_id, primary_name, now, row["slug"]))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_locations SET place_id=?,local_area_id=?,district=?,updated_at=? "
                    "WHERE slug=?", updates)
        return len(updates)

    def set_location_geo(self, slug: str, lat: float | None, lon: float | None,
                         geojson: str | None) -> None:
        """Koordinaten eines Ortes setzen — und den Stadtteil daraus ableiten.

        Zwei Fälle, die vorher eine Zeile waren — und genau darin lag der Fehler:

        * **Kein Ergebnis** (``lat is None``): Das Geocoding ist misslungen und
          wird nur als „versucht" vermerkt. Ein Fehlschlag weiß nichts, also
          darf er nichts wegnehmen. Vorher schrieb die Methode auch hier
          ``district = NULL`` — auf dem Prod-Snapshot löschte der
          Wiederholungslauf damit genau die Stadtteile wieder, die die
          Namensregel zuvor gesetzt hatte („Oberschule Ofenerdiek").
        * **Ergebnis außerhalb Oldenburgs**: Ein Treffer, der in keinem
          Ortsbereich liegt, ist ein Beleg — der Ort gehört nicht hierher, und
          ein alter Stadtteil an ihm wäre falsch. Der wird gelöscht.

        Und der Stadtteil kommt aus der GEOMETRIE, wenn es eine gibt: Bei einer
        Straße liegt der Bounding-Box-Mittelpunkt oft neben ihr.
        """
        from council import geo, places

        hat_ergebnis = lat is not None and lon is not None
        district = geo.ortsbereich_der_geometrie(geojson)
        if not district and hat_ergebnis:
            district = geo.ortsbereich_for(lat, lon)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            if district or hat_ergebnis:
                primary = places.resolve(district) if district else None
                self._conn.execute(
                    "UPDATE council_locations SET lat=?, lon=?, geojson=?, district=?, "
                    "local_area_id=?, geo_tried=1, updated_at=? WHERE slug=?",
                    (lat, lon, geojson, district, primary.id if primary else None, now, slug))
            else:
                # Fehlschlag: nur als versucht vermerken, Stadtteil unangetastet.
                self._conn.execute(
                    "UPDATE council_locations SET lat=NULL, lon=NULL, geojson=NULL, "
                    "geo_tried=1, updated_at=? WHERE slug=?", (now, slug))

    def list_entities_geo(self) -> list[dict]:
        """Geocoded entities (points) for the city-wide map — slug, name, kind, n, lat, lon."""
        return [{**dict(r), "target": "thema"} for r in self._conn.execute(
            "SELECT e.slug, e.name, e.kind, e.n, m.lat, m.lon "
            "FROM council_entities e JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE m.lat IS NOT NULL AND m.lon IS NOT NULL ORDER BY e.n DESC")]

    def decision_location_map_points(self, min_decisions: int = 3) -> list[dict]:
        """Belastbare Beschlussorte für die Stadtkarte.

        Konkrete Straßen, Plätze, Gebäude, Gewässer, Anlagen, Bauwerke und
        Verkehrswege werden ab drei Beschlüssen automatisch gezeigt. Unscharfe
        Gebietsbegriffe müssen erst redaktionell freigegeben werden;
        verworfene Kandidaten bleiben draußen.
        """
        rows = self._conn.execute(
            """SELECT l.slug,l.name,l.kind,l.lat,l.lon,l.place_id,l.local_area_id,
                      r.status AS review_status,r.kind AS review_kind,
                      COUNT(DISTINCT dl.decision_id) AS n,
                      MAX(cs.session_date) AS last_date,
                      COUNT(DISTINCT CASE WHEN cs.session_date >= date('now','-12 months')
                                           THEN dl.decision_id END) AS n_recent
               FROM council_locations l
               JOIN council_decision_locations dl ON dl.location_slug=l.slug
               JOIN council_decisions d ON d.id=dl.decision_id AND d.kind='decision'
               JOIN council_sessions cs ON cs.ksinr=d.ksinr
               LEFT JOIN council_place_reviews r ON r.location_slug=l.slug
               WHERE l.lat IS NOT NULL AND l.lon IS NOT NULL
                 AND l.local_area_id IS NOT NULL
               GROUP BY l.slug
               ORDER BY n DESC,l.name"""
        ).fetchall()
        out = []
        for row in rows:
            if row["review_status"] == "rejected":
                continue
            place = self.resolve_place(row["place_id"] or row["name"])
            approved = row["review_status"] in {"approved", "alias"}
            reviewed_concrete = row["review_status"] == "concrete"
            effective_kind = (row["review_kind"] if reviewed_concrete else row["kind"])
            # Flächendeckende Ortsbereiche sind bereits als Filter und Umriss
            # vorhanden; als riesige Sammelpunkte würden sie die exakten Orte
            # überdecken. Kuratierte Teilräume dürfen dagegen auf die Karte.
            catalog_secondary = bool(place and not place.is_primary)
            if not (approved or reviewed_concrete or catalog_secondary or
                    (effective_kind in CONCRETE_LOCATION_KINDS and
                     row["n"] >= max(1, int(min_decisions)))):
                continue
            target = "ort" if place and (approved or catalog_secondary) else "location"
            out.append({
                "slug": row["slug"], "name": place.name if place else row["name"],
                "kind": "beschlussort", "n": row["n"], "lat": row["lat"], "lon": row["lon"],
                "target": target, "place_id": place.id if target == "ort" else None,
                "location_slug": row["slug"], "local_area_id": row["local_area_id"],
                "last_date": row["last_date"], "n_recent": row["n_recent"],
            })
        return out

    def city_map_points(self) -> list[dict]:
        """Themen und Beschlussorte zusammenführen; der präzisere Ortslink gewinnt."""
        by_slug = {row["slug"]: row for row in self.list_entities_geo()}
        for row in self.decision_location_map_points():
            by_slug[row["slug"]] = row
        return sorted(by_slug.values(), key=lambda row: (-row["n"], row["name"]))

    def entities_to_geocode(self) -> list[dict]:
        """Place/street/area entities not yet geocoded — for the geocode backfill."""
        rows = self._conn.execute(
            "SELECT e.slug, e.name, e.kind FROM council_entities e "
            "LEFT JOIN council_entity_meta m ON m.slug = e.slug "
            "WHERE e.kind = 'place' AND (m.geo_tried IS NULL OR m.geo_tried = 0) ORDER BY e.n DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def set_entity_geo(self, slug: str, lat: float | None, lon: float | None, geojson: str | None) -> None:
        """Store geocoding result (or mark as tried with NULLs) for an entity slug."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_entity_meta(slug, lat, lon, geojson, geo_tried) VALUES (?,?,?,?,1) "
                "ON CONFLICT(slug) DO UPDATE SET lat=excluded.lat, lon=excluded.lon, "
                "geojson=excluded.geojson, geo_tried=1", (slug, lat, lon, geojson))

    def reset_geo(self) -> int:
        """Clear all geocoding (lat/lon/geojson, geo_tried) so it can be recomputed —
        e.g. after improving the geocoder. Keeps descriptions. Returns rows reset."""
        with self._conn:
            cur = self._conn.execute(
                "UPDATE council_entity_meta SET lat=NULL, lon=NULL, geojson=NULL, geo_tried=0 "
                "WHERE geo_tried=1 OR lat IS NOT NULL")
        return cur.rowcount

    # ----------------------------------------------------------------
    # Die SCHREIBSEITE der Ortszuordnung — aus demselben Grund nachgezogen
    # wie beim Haushalt (#1023): Der erste Kegel ging von den Endpunkten
    # aus und kannte die Ingest-Skripte nicht.
    # ----------------------------------------------------------------

    def decision_location_batches(self, *, batch_size: int = 12,
                                  pending_only: bool = True,
                                  limit: int | None = None):
        """Beschlüsse samt Vorlage speicherschonend in Batches liefern.

        Im Tageslauf kommen nur ungescannte Vorgänge oder solche mit einer
        später geladenen Vorlage zurück. ``pending_only=False`` ist der
        bewusste Voll-Backfill nach dem Leeren der Scan-Tabelle.
        """
        inner = """SELECT d.id, d.title, d.official_text, d.template_number,
                      COALESCE(
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.raw_text FROM council_templates v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1)
                      ) AS vorlage_text,
                      COALESCE(
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.kvonr = d.kvonr AND v.status = 'ok' LIMIT 1),
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.status = 'ok' AND v.template_number = d.template_number
                         ORDER BY v.kvonr DESC LIMIT 1),
                        (SELECT v.fetched_at FROM council_templates v
                         WHERE v.status = 'ok' AND d.template_number IS NOT NULL
                           AND instr(d.template_number, v.template_number || '/') = 1
                         ORDER BY v.kvonr DESC LIMIT 1),
                        ''
                      ) AS vorlage_fetched_at,
                      s.source_hash AS existing_source_hash,
                      s.scanned_at
               FROM council_decisions d
               LEFT JOIN council_decision_location_scans s ON s.decision_id = d.id
               WHERE d.kind = 'decision'"""
        sql = f"SELECT * FROM ({inner}) q"
        if pending_only:
            sql += (" WHERE existing_source_hash IS NULL OR "
                    "(vorlage_fetched_at != '' AND "
                    "datetime(vorlage_fetched_at) > datetime(scanned_at))")
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += f" LIMIT {max(0, int(limit))}"
        cursor = self._conn.execute(sql)
        while True:
            rows = cursor.fetchmany(max(1, int(batch_size)))
            if not rows:
                break
            yield [dict(r) for r in rows]

    def place_observations_for_decisions(self, ids: list[int]) -> dict[int, list[dict]]:
        """Einmalige alte NER-Orte als günstige Startbasis übernehmen."""
        if not ids:
            return {}
        ph = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT decision_id, name FROM council_entity_obs "
            f"WHERE kind = 'place' AND decision_id IN ({ph})", ids).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["decision_id"], []).append({
                "name": r["name"], "kind": "other", "source": "official_text",
                "evidence": r["name"], "method": "entity_obs", "confidence": 0.86,
            })
        return out

    def location_candidates(self, status_filter: str = "pending", *, limit: int = 200,
                            min_decisions: int = 3) -> list[dict]:
        """Häufige, noch nicht statisch katalogisierte Ortsnamen samt Belegen."""
        status_filter = status_filter if status_filter in {
            "pending", "concrete", "approved", "alias", "rejected", "all"
        } else "pending"
        # Auch zur Laufzeit freigegebene Katalogorte zählen als bekannt. So
        # verschwinden nach dem Backfill nicht nur statische Stadtteile,
        # sondern ebenso Schreibvarianten neuer redaktioneller Orte aus
        # der offenen Kandidatenliste.
        known_ids = sorted(place.id for place in self.all_places())
        review_where = ""
        review_params: list = []
        if status_filter == "pending":
            review_where = "AND r.status IS NULL"
        elif status_filter != "all":
            review_where = "AND r.status = ?"
            review_params.append(status_filter)
        known_placeholders = ",".join("?" for _ in known_ids)
        known_where = (
            f"AND (r.status IS NOT NULL OR l.place_id IS NULL "
            f"OR l.place_id NOT IN ({known_placeholders}))"
            if known_ids else ""
        )
        # Die offene Liste ist eine Prioritätenliste, kein Dump aller einmalig
        # erwähnten Namen. Bereits geprüfte Einträge müssen dagegen auch dann
        # sichtbar bleiben, wenn sie nur in einem Beschluss vorkommen.
        effective_min = max(1, int(min_decisions)) if status_filter == "pending" else 1
        rows = self._conn.execute(
            f"""SELECT l.*, r.status AS review_status, r.place_id AS review_place_id,
                      r.name AS review_name, r.kind AS review_kind, r.parent_id,
                      r.aliases, r.description, r.source_url, r.quiz_enabled,
                      r.canonical_place_id, r.note, r.updated_by, r.updated_at AS reviewed_at,
                      COUNT(DISTINCT dl.decision_id) AS decision_count,
                      MAX(cs.session_date) AS last_date,
                      AVG(dl.confidence) AS avg_confidence
               FROM council_locations l
               JOIN council_decision_locations dl ON dl.location_slug=l.slug
               JOIN council_decisions d ON d.id=dl.decision_id AND d.kind='decision'
               JOIN council_sessions cs ON cs.ksinr=d.ksinr
               LEFT JOIN council_place_reviews r ON r.location_slug=l.slug
               WHERE l.kind IN ('district','area','other') {review_where} {known_where}
               GROUP BY l.slug
               HAVING COUNT(DISTINCT dl.decision_id) >= ?
               ORDER BY decision_count DESC, last_date DESC, l.name
               LIMIT ?""", (*review_params, *known_ids, effective_min,
                              max(1, min(int(limit), 500)))
        ).fetchall()
        out = []
        for row in rows:
            state = row["review_status"] or "pending"
            evidence = self._conn.execute(
                """SELECT d.id,d.title,cs.session_date,dl.evidence,dl.method,dl.confidence
                   FROM council_decision_locations dl
                   JOIN council_decisions d ON d.id=dl.decision_id
                   JOIN council_sessions cs ON cs.ksinr=d.ksinr
                   WHERE dl.location_slug=? AND d.kind='decision'
                   ORDER BY cs.session_date DESC,d.id DESC LIMIT 3""",
                (row["slug"],),
            ).fetchall()
            item = dict(row)
            item["status"] = state
            try:
                item["aliases"] = json.loads(row["aliases"] or "[]")
            except (TypeError, json.JSONDecodeError):
                item["aliases"] = []
            item["evidence"] = [dict(sample) for sample in evidence]
            out.append(item)
        return out

    def review_location_candidate(self, location_slug: str, *, status: str,
                                  place_id: str | None = None, name: str | None = None,
                                  kind: str | None = None, parent_id: str | None = None,
                                  aliases: list[str] | None = None,
                                  description: str | None = None,
                                  source_url: str | None = None,
                                  quiz_enabled: bool = False,
                                  canonical_place_id: str | None = None,
                                  note: str | None = None,
                                  updated_by: str | None = None) -> dict:
        """Redaktionelles Urteil speichern und stabile IDs an Rohorte schreiben."""
        from council import places
        from council.locations import location_slug as slugify

        if status not in {"concrete", "approved", "alias", "rejected"}:
            raise ValueError("Unbekannter Prüfstatus")
        observed = self._conn.execute(
            "SELECT * FROM council_locations WHERE slug=?", (location_slug,)).fetchone()
        if not observed:
            raise KeyError(location_slug)
        allowed_kinds = {key for key in places.catalog()["kinds"] if key != "local_area"}
        if status == "approved":
            place_id = slugify(place_id or name or observed["name"])
            name = (name or observed["name"]).strip()
            kind = kind or "neighborhood"
            if not place_id or not name or kind not in allowed_kinds:
                raise ValueError("Freigegebener Ort braucht Name, gültige ID und Ortstyp")
            if not (source_url or "").startswith(("https://", "http://")):
                raise ValueError("Freigegebener Ort braucht eine Quellen-URL")
            if places.resolve(place_id) or any(p.id == place_id for p in self._reviewed_places()
                                                if p.id != observed["place_id"]):
                raise ValueError("Orts-ID ist bereits vergeben")
            parent = places.resolve(parent_id) if parent_id else None
            if parent_id and (not parent or not parent.is_primary):
                raise ValueError("Elternort muss ein primärer Ortsbereich sein")
        elif status == "concrete":
            name = (name or observed["name"]).strip()
            if not name or kind not in CONCRETE_LOCATION_KINDS:
                raise ValueError("Konkreter Ort braucht Name und gültigen Ortstyp")
            # Konkrete Punkte bleiben exakte Fundorte und werden absichtlich
            # nicht Teil des flächigen Ortskatalogs.
            place_id = None
            canonical_place_id = None
            parent_id = observed["local_area_id"]
            source_url = None
            quiz_enabled = False
        elif status == "alias":
            target = self.resolve_place(canonical_place_id)
            if not target:
                raise ValueError("Alias-Ziel ist unbekannt")
            canonical_place_id = target.id
            parents = self.primary_parents(target)
            parent_id = parents[0].id if len(parents) == 1 else None
            place_id = target.id
        else:
            place_id = None
            parent_id = None
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        clean_aliases = list(dict.fromkeys(value.strip() for value in (aliases or []) if value.strip()))
        with self._conn:
            self._conn.execute(
                """INSERT INTO council_place_reviews
                   (location_slug,status,place_id,name,kind,parent_id,aliases,description,
                    source_url,quiz_enabled,canonical_place_id,note,updated_by,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(location_slug) DO UPDATE SET
                    status=excluded.status,place_id=excluded.place_id,name=excluded.name,
                    kind=excluded.kind,parent_id=excluded.parent_id,aliases=excluded.aliases,
                    description=excluded.description,source_url=excluded.source_url,
                    quiz_enabled=excluded.quiz_enabled,
                    canonical_place_id=excluded.canonical_place_id,note=excluded.note,
                    updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (location_slug, status, place_id, name, kind, parent_id,
                 json.dumps(clean_aliases, ensure_ascii=False), description, source_url,
                 int(quiz_enabled), canonical_place_id, note, updated_by, now),
            )
            if status == "concrete":
                self._conn.execute(
                    "UPDATE council_locations SET place_id=NULL,updated_at=? WHERE slug=?",
                    (now, location_slug),
                )
            else:
                self._conn.execute(
                    "UPDATE council_locations SET place_id=?,local_area_id=?,updated_at=? WHERE slug=?",
                    (place_id, parent_id, now, location_slug),
                )
        self._runtime_places_cache = None
        self._place_aliases_cache = None
        return next(item for item in self.location_candidates("all", limit=500)
                    if item["slug"] == location_slug)

    def save_decision_locations(self, decision_id: int, rows: list[dict],
                                source_hash: str | None) -> int:
        """Zuordnungen eines Beschlusses atomar ersetzen und ggf. Scanstand merken.

        ``source_hash=None`` speichert sichere Regex-/Bestandsfunde nach einem
        LLM-Fehler, markiert den Vorgang aber nicht als fertig: der nächste
        inkrementelle Lauf versucht die semantische Ergänzung erneut.
        """
        from council.locations import location_slug

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        by_slug: dict[str, dict] = {}
        for row in rows:
            slug = row.get("slug") or location_slug(row.get("name") or "")
            if not slug:
                continue
            if slug not in by_slug or float(row.get("confidence") or 0) > float(by_slug[slug].get("confidence") or 0):
                by_slug[slug] = row
        with self._conn:
            self._conn.execute(
                "DELETE FROM council_decision_locations WHERE decision_id = ?", (decision_id,))
            for slug, row in by_slug.items():
                place = self.resolve_place(row.get("name"))
                parents = self.primary_parents(place)
                primary = parents[0] if len(parents) == 1 else None
                self._conn.execute(
                    "INSERT INTO council_locations"
                    "(slug,name,kind,district,place_id,local_area_id,updated_at) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, kind=excluded.kind, "
                    "place_id=COALESCE(excluded.place_id,council_locations.place_id), "
                    "local_area_id=COALESCE(excluded.local_area_id,council_locations.local_area_id), "
                    "district=COALESCE(excluded.district,council_locations.district), "
                    "updated_at=excluded.updated_at",
                    (slug, place.name if place else row["name"],
                     "district" if place and place.is_primary else row.get("kind") or "other",
                     primary.name if primary else None, place.id if place else None,
                     primary.id if primary else None, now),
                )
                self._conn.execute(
                    "INSERT INTO council_decision_locations "
                    "(decision_id,location_slug,source,evidence,method,confidence,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (decision_id, slug, row.get("source") or "official_text",
                     (row.get("evidence") or row["name"])[:500], row.get("method") or "llm",
                     max(0.0, min(1.0, float(row.get("confidence") or 0))), now),
                )
            if source_hash is not None:
                self._conn.execute(
                    "INSERT INTO council_decision_location_scans(decision_id,source_hash,scanned_at) "
                    "VALUES (?,?,?) ON CONFLICT(decision_id) DO UPDATE SET "
                    "source_hash=excluded.source_hash, scanned_at=excluded.scanned_at",
                    (decision_id, source_hash, now),
                )
        return len(by_slug)

    def reset_decision_location_scans(self) -> None:
        """Vollständigen Neu-Lauf erlauben; Geocodes der Orte bleiben erhalten."""
        with self._conn:
            self._conn.execute("DELETE FROM council_decision_locations")
            self._conn.execute("DELETE FROM council_decision_location_scans")
