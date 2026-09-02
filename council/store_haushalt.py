"""Der Haushalt: 81 Abfragen, die nur die Haushalts-Seiten brauchen.

**Warum getrennt.** ``council/store.py`` trug 15.744 Zeilen in EINER Klasse mit
506 Methoden. Wer dort etwas sucht, sucht lange — und wer etwas ändert, sieht
nicht, wen er trifft. Das ist der erste Schnitt: der Haushalt, weil er die
größte in sich geschlossene Ecke ist.

**Wie der Schnitt bestimmt wurde.** Nicht nach Namensmuster, sondern über den
Aufrufkegel: alles, was die 20 Haushalts-Endpunkte aufrufen, plus alles, was
diese Methoden ihrerseits an sich selbst rufen. Fünf allgemeine Helfer sind
ausdrücklich drüben geblieben (``get_herkunft``, ``find_decision_ids``,
``get_vorlage_by_nr``, ``anlagen_for_vorlage_nr``,
``beschluesse_zu_dokumenten``) — sie tragen den Haushalt mit, gehören ihm aber
nicht.

**Warum ein Mixin und keine eigene Klasse.** So ändert sich an keiner
Aufrufstelle etwas: ``store.get_haushalt(...)`` heißt weiter so, in den Routen,
in den Ingest-Skripten und in den Tests. Ein Umbau, der 500 Aufrufstellen
anfasst, wäre ein anderes Risiko als einer, der Zeilen verschiebt.

Das Schema und die Migrationen bleiben in ``store.py``: Sie gehören der
Datenbank als Ganzem, nicht einer ihrer Ecken.
"""
from __future__ import annotations

import json
import sqlite3

from kern.dbfehler import tabelle_fehlt


class HaushaltMixin:
    """Die Haushalts-Abfragen von :class:`council.store.CouncilStore`.

    Nur zum Mitvererben gedacht; ``self._conn`` und die übrigen Helfer kommen
    von dort.
    """

    def haushalt_jahrgaenge(self) -> dict[str, list[int]]:
        """Je Quellenschlüssel die Jahrgänge, die **wirklich** im Bestand
        stehen — aufsteigend, ohne Dubletten.

        Wofür: Das Quellenverzeichnis schrieb seine Datenstände von Hand
        („Jahresabschlüsse 2017–2024"), einundzwanzig Stück in
        ``lib/haushalt-quellen.ts``, mit der Bitte im Dateikopf, sie beim
        Nachziehen eines Haushaltsjahres zu aktualisieren. Genau das passiert
        naturgemäß nicht zuverlässig: Ein Ingest-Lauf zieht einen Jahrgang
        nach, die Seite behauptet weiter den alten Stand, und niemand merkt
        es — die Angabe steht ja nicht neben den Daten, sondern in einer
        anderen Datei.

        Bewusst **nicht** über ``haushalt_dokumente`` gerechnet: Das dort
        nötige „hat eine URL" ist eine andere Frage. Ein Jahrgang, der im
        Bestand steht, dessen Herkunft aber keine Adresse führt, ist für den
        Datenstand vorhanden und für den Dokumentlink nicht. Wer beides aus
        einer Abfrage nähme, verschwiege im Datenstand genau die Jahrgänge,
        die ohnehin schon am dünnsten belegt sind.

        Was hier fehlt, bleibt in der Konstante von Hand gepflegt: Die
        Ausgabe-Datumsangaben der Statistikstellen („Ausgabe vom 08.07.2026")
        stehen in keiner Tabelle, und zwei Quellen sind schlicht statisch
        (eine einzelne Ratsvorlage von 2018; „Sitzungen seit Januar 2018"
        ohne obere Grenze)."""
        quellen = {k: (t, j, f) for k, (t, j, f, _) in self._DOKUMENT_QUELLEN.items()}
        quellen.update(self._WEITERE_JAHRESQUELLEN)
        aus: dict[str, list[int]] = {}
        for key, (tabelle, jahrspalte, filter_) in quellen.items():
            sql = (f"SELECT DISTINCT t.{jahrspalte} AS year FROM {tabelle} t"
                   + (f" WHERE {filter_}" if filter_ else "")
                   + f" ORDER BY t.{jahrspalte}")
            try:
                years = [int(r["year"]) for r in self._conn.execute(sql)
                         if r["year"] is not None]
            except sqlite3.OperationalError:
                continue  # Tabelle oder Spalte gibt es in dieser DB (noch) nicht
            if years:
                aus[key] = years
        return aus

    def haushalt_dokumente(self) -> dict[str, list[dict]]:
        """Je Quellenschlüssel die Dokumente, Jahrgang für Jahrgang.

        Die Antwort auf die Frage, die das Quellenverzeichnis stellt: „Der
        Beleg steht an einer Zahl von 2021 — welches PDF ist das?" Ohne sie
        führte der Link auf die Startseite des Ratsinformationssystems, und
        ein Beleg, der nur zur Startseite führt, ist keiner.

        Bevorzugt wird ``council_provenance``: Dort steht neben der URL auch die
        **Fundstelle** im Dokument („Abschnitt 3.1") — bei 300 Seiten der
        Unterschied zwischen Nachschlagen und Suchen. Fehlt die Herkunft
        (Altbestand), tritt die URL an der Datenzeile ein; fehlt auch die,
        fällt der Jahrgang weg statt mit einer erfundenen Adresse
        dazustehen.

        Jedes Dokument aus dem Ratsinformationssystem trägt zusätzlich seinen
        ``official_text`` — den Ratsvorgang, der es verabschiedet hat (s.
        :meth:`beschluesse_zu_dokumenten`). Der Beleg sagt damit nicht nur, in
        welchem Papier die Zahl steht, sondern wann der Rat darüber entschieden
        hat. Bei den Schichten von oldenburg.de und vom Landesamt bleibt das
        Feld ``None``: Die hängen an keiner Vorlage."""
        aus: dict[str, list[dict]] = {}
        for key, (tabelle, jahrspalte, filter_, alt) in self._DOKUMENT_QUELLEN.items():
            wo = [f"{filter_}"] if filter_ else []
            url = f"COALESCE(k.url, t.{alt})" if alt else "k.url"
            sql = (f"SELECT DISTINCT t.{jahrspalte} AS year, {url} AS url, "
                   f" k.label AS label, k.citation AS citation, k.page AS page, "
                   f" k.document_id AS document_id "
                   f"FROM {tabelle} t "
                   f"LEFT JOIN council_provenance k ON k.id = t.herkunft_id"
                   + (" WHERE " + " AND ".join(wo) if wo else "")
                   + f" ORDER BY t.{jahrspalte}, url")
            try:
                rows = [dict(r) for r in self._conn.execute(sql)]
            except sqlite3.OperationalError:
                continue  # Tabelle oder Spalte gibt es in dieser DB (noch) nicht
            treffer = [r for r in rows if r["url"]]
            if treffer:
                aus[key] = treffer
        # Ein Nachschlag für den ganzen Bereich statt einer je Dokument: Der
        # Apparat einer Seite zeigt bis zu dreizehn Teilhaushalts-Anlagen, und das
        # Verzeichnis am Fuß zeigt alle Quellen auf einmal.
        beschluesse = self.beschluesse_zu_dokumenten(sorted(
            {r["document_id"] for liste in aus.values()
             for r in liste if r.get("document_id")}))
        for liste in aus.values():
            for r in liste:
                # `document_id` war nur der Schlüssel für den Nachschlag und
                # fliegt wieder raus: Was auf die Seite geht, ist der Vorgang,
                # nicht die RIS-interne Nummer des Anhangs.
                r["official_text"] = beschluesse.get(r.pop("document_id", None))
        return aus

    def get_haushalt(self, year: int) -> list[dict]:
        """Ergebnishaushalt eines Jahres (Teilhaushalte + Summenzeile)."""
        rows = self._conn.execute(
            "SELECT area, revenues, expenses, result, is_total, source_url "
            "FROM council_budget WHERE year = ? ORDER BY is_total, expenses DESC",
            (year,)).fetchall()
        return [dict(r) for r in rows]

    def haushalt_years(self) -> list[int]:
        """Alle eingelesenen Haushaltsjahre (aufsteigend) — für Trend-Fragen."""
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT year FROM council_budget ORDER BY year")]

    def get_steuereinnahmen(self) -> list[dict]:
        """Alle Ist-Steuereinnahmen, älteste zuerst (Langformat je Jahr × Art)."""
        return [dict(r) for r in self._conn.execute(
            "SELECT year, kind, amount FROM council_taxes ORDER BY year, kind")]

    def einwohner_aktuell(self) -> dict | None:
        """Jüngste bekannte Einwohnerzahl — Bezugsgröße für Pro-Kopf-Angaben."""
        try:
            r = self._conn.execute(
                "SELECT year, population FROM council_einwohner ORDER BY year DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        return dict(r) if r else None

    def get_abweichungsgruende(self, year: int | None = None) -> list[dict]:
        """Erläuterungen — ein Jahr oder alle, in Tabellenreihenfolge."""
        try:
            if year is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_variance_reasons ORDER BY year, nr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_variance_reasons WHERE year = ? ORDER BY nr",
                    (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_pruefbericht_quellen(self) -> list[dict]:
        """Alle bekannten Schlussberichte, ältester zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT year, label, url, n_pages, readable, herkunft_id "
                "FROM council_audit_report_sources ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def plan_actual_years(self) -> list[int]:
        """Jahre, für die Teilhaushalts-Ist vorliegt (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_income_statement "
                "WHERE sub_budget_no IS NOT NULL ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_ergebnisrechnung(self, year: int | None = None) -> list[dict]:
        """Ergebnisrechnung — ein Jahr oder alle, Posten in Tabellenreihenfolge."""
        if year is None:
            rows = self._conn.execute(
                "SELECT * FROM council_income_statement ORDER BY year, nr").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM council_income_statement WHERE year = ? ORDER BY nr", (year,)).fetchall()
        return [dict(r) for r in rows]

    def ergebnisrechnung_jahre(self) -> list[int]:
        """Jahre mit eingelesenem Jahresabschluss (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_income_statement ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_finanzrechnung(self, year: int | None = None) -> list[dict]:
        """Finanzrechnung — ein Jahr oder alle, Zeilen in Dokumentreihenfolge."""
        try:
            if year is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_cash_flow_statement ORDER BY year, nr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_cash_flow_statement WHERE year = ? ORDER BY nr",
                    (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_bilanz(self, year: int | None = None) -> list[dict]:
        """Bilanzposten — ein Stichtag oder alle.

        Sortiert nach Jahr, dann Aktiva vor Passiva, dann in der Reihenfolge
        des Dokuments. ``ORDER BY page DESC`` ist kein Tippfehler: ``aktiva``
        steht alphabetisch vor ``passiva``, und die Bilanz druckt die
        Aktivseite zuerst — absteigend sortiert kommt genau das heraus."""
        try:
            sql = ("SELECT * FROM council_balance_sheet {} "
                   "ORDER BY year, page ASC, level, role")
            if year is None:
                rows = self._conn.execute(sql.format("")).fetchall()
            else:
                rows = self._conn.execute(sql.format("WHERE year = ?"), (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def bilanz_jahre(self) -> list[int]:
        """Bilanzstichtage im Bestand (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_balance_sheet ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_ruecklagen(self) -> list[dict]:
        """Verfügbare Überschussrücklage nach abgeschlossenem Jahr.

        Die Bilanz zeigt den bereits umgebuchten Stand in Position 1.2.1 und
        das Ergebnis des gerade abgeschlossenen Jahres noch separat in 1.3.
        Der Vorbericht des Folgehaushalts nennt deshalb beide zusammen („unter
        Berücksichtigung des Ergebnisses"). Genau diese nachvollziehbare
        Addition liefert die Reihe; andere, zweckgebundene Rücklagen bleiben
        ausdrücklich draußen.
        """
        try:
            rows = self._conn.execute(
                "SELECT year, role, value, herkunft_id FROM council_balance_sheet "
                "WHERE role IN ('ordinary_surplus_reserve', "
                "'annual_result_balance_sheet') ORDER BY year, role").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        years: dict[int, dict] = {}
        for row in rows:
            z = years.setdefault(row["year"], {
                "year": row["year"], "reserves": None,
                "jahresergebnis": None, "state_after_result": None,
                "herkunft_id": row["herkunft_id"],
            })
            if row["role"] == "ordinary_surplus_reserve":
                z["reserves"] = row["value"]
            else:
                z["jahresergebnis"] = row["value"]
        aus = []
        for year in sorted(years):
            z = years[year]
            if z["reserves"] is None or z["jahresergebnis"] is None:
                continue
            z["state_after_result"] = z["reserves"] + z["jahresergebnis"]
            aus.append(z)
        return aus

    def get_bilanz_posten(self, role: str) -> list[dict]:
        """Eine einzelne Bilanzposition über alle Stichtage.

        Für Zahlen, die außerhalb der Bilanzseite gebraucht werden und dort
        ihre Bedeutung erst bekommen — die Geldschulden neben dem
        Bürgschaftsbestand etwa (`council/buergschaften.py`). Die ganze Bilanz
        dafür zu holen und im Aufrufer zu filtern hieße, 131 Zeilen zu laden,
        um drei zu benutzen."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_balance_sheet WHERE role = ? ORDER BY year", (role,))]
        except sqlite3.OperationalError:
            return []

    def get_bilanz_erlaeuterungen(self, year: int | None = None) -> list[dict]:
        """Erläuterungen zur Bilanz — ein Jahrgang oder alle."""
        try:
            sql = ("SELECT * FROM council_balance_sheet_notes {} "
                   "ORDER BY year, nr")
            if year is None:
                rows = self._conn.execute(sql.format("")).fetchall()
            else:
                rows = self._conn.execute(sql.format("WHERE year = ?"), (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_ergebnishaushalt(self, year: int | None = None,
                             kind: str | None = None) -> list[dict]:
        """Planzahlen je Posten — gefiltert nach Jahr und/oder Art.

        ``kind="budget"`` ist die Frage, die eine Seite fast immer meint: „was
        ist für dieses Jahr geplant?". Ohne Filter kommt auch die
        Finanzplanung mit; sie ist als solche beschriftet und darf nur so
        gezeigt werden."""
        wo, werte = [], []
        if year is not None:
            wo.append("year = ?")
            werte.append(year)
        if kind is not None:
            wo.append("kind = ?")
            werte.append(kind)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_income_budget" + satz
                + " ORDER BY year, kind, nr", werte)]
        except sqlite3.OperationalError:
            return []

    def budgeted_years(self) -> list[int]:
        """Jahre, für die ein Haushaltsansatz vorliegt (aufsteigend).

        Bewusst ohne die Finanzplanungsjahre: Eine Jahresliste, die 2029
        mitführt, wird irgendwo zu einem Umschalter, und dann steht auf der
        Seite ein Jahr, für das nie ein Haushalt aufgestellt wurde."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_income_budget "
                "WHERE kind = 'budget' ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def stellenplan_einheiten(self) -> set[tuple]:
        """Welche ``(Jahrgang, Teil)`` im Bestand stehen.

        Die Einheit ist der **Teil**, nicht der Jahrgang: Ein Jahrgang, von
        dem nur Teil A lesbar war, sähe sonst aus wie ein vollständiger — und
        eine Seite, die dann „2026: 815 Stellen" schreibt, unterschlüge die
        1.700 Tarifstellen, statt sie zu vermissen."""
        try:
            return {(r[0], r[1]) for r in self._conn.execute(
                "SELECT DISTINCT budget_year, part FROM council_staff_plan")}
        except sqlite3.OperationalError:
            return set()

    def get_stellenplan(self, kind: str | None = None,
                        budget_year: int | None = None) -> list[dict]:
        """Stellenplan-Zeilen — gefiltert nach Stufe und/oder Jahrgang.

        ``kind="total"`` ist die Frage, die die Übersichtsseite meint („wie
        viele Stellen, wie viele davon unbesetzt?"); ohne Filter kommen alle
        rund tausend Einzelposten mit."""
        wo, werte = [], []
        if kind is not None:
            wo.append("kind = ?")
            werte.append(kind)
        if budget_year is not None:
            wo.append("budget_year = ?")
            werte.append(budget_year)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_staff_plan" + satz
                + " ORDER BY budget_year, part, row_no", werte)]
        except sqlite3.OperationalError:
            return []

    def investitionen_jahre(self) -> list[int]:
        """Haushaltsjahre, für die Investitionen vorliegen (aufsteigend).

        Gezählt wird an der **Summenzeile**, nicht an irgendeiner Zeile: Sie
        kommt nur in die Tabelle, wenn die Rechenprobe aufging, und ist damit
        das Kennzeichen eines vollständigen Jahrgangs."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_investments "
                "WHERE level = 'investments' ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_investitionen(self, year: int | None = None,
                          level: str | None = None) -> list[dict]:
        """Investitionszeilen — gefiltert nach Jahr und/oder Ebene.

        Ohne Filter kommen alle drei Ebenen mit; sie sind als ``level``
        beschriftet und dürfen nur so gezeigt werden. Wer die Teilhaushalte
        addiert und das Ergebnis neben die Summenzeile stellt, zeigt zweimal
        dieselbe Zahl."""
        wo, werte = [], []
        if year is not None:
            wo.append("year = ?")
            werte.append(year)
        if level is not None:
            wo.append("level = ?")
            werte.append(level)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investments" + satz
                + " ORDER BY year, level, sub_budget_no", werte)]
        except sqlite3.OperationalError:
            return []

    def investitionsprogramm_jahre(self) -> list[int]:
        """Jahrgänge, für die ein Investitionsprogramm vorliegt (aufsteigend).

        Gezählt an der ``gesamt``-Zeile: Sie kommt nur in die Tabelle, wenn
        alle drei Proben aufgingen, und kennzeichnet damit einen vollständigen
        Jahrgang."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_investment_measures "
                "WHERE level = 'total' ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_investitionsmassnahmen(self, year: int | None = None,
                                   sub_budget_no: int | None = None,
                                   level: str | None = None) -> list[dict]:
        """Zeilen des Investitionsprogramms — nach Jahr, Teilhaushalt, Ebene.

        Ohne ``level`` kommen alle drei mit. Sie sind beschriftet und dürfen
        nur so gezeigt werden: Wer die Maßnahmen addiert und das Ergebnis neben
        die ``teilhaushalt``-Zeile stellt, zeigt zweimal dieselbe Zahl."""
        wo, werte = [], []
        if year is not None:
            wo.append("year = ?")
            werte.append(year)
        if sub_budget_no is not None:
            wo.append("sub_budget_no = ?")
            werte.append(sub_budget_no)
        if level is not None:
            wo.append("level = ?")
            werte.append(level)
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investment_measures" + satz
                + " ORDER BY year, sub_budget_no, level, code", werte)]
        except sqlite3.OperationalError:
            return []

    def konzern_jahre(self) -> list[int]:
        """Jahrgänge mit eingelesenem Gesamtabschluss (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_group_items ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_konzern_posten(self, year: int | None = None) -> list[dict]:
        """Posten der Gesamtergebnisrechnung — ein Jahrgang oder alle."""
        try:
            if year is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_group_items ORDER BY year, nr").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_group_items WHERE year = ? ORDER BY nr",
                    (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def kernverwaltung_ist(self) -> dict[int, dict]:
        """Ist-Summen der Kernverwaltung je Jahr, aus den Jahresabschlüssen.

        Nur die beiden Summenzeilen, und bewusst über die **Bezeichnung**
        gesucht statt über die Postennummer: Diese Tabelle wird sonst nirgends
        nach Nummern gefragt, und eine Nummer, die niemand nachprüft, ist
        genau die, die beim nächsten Formatwechsel still etwas anderes meint.

        Zweck ist die Gegenprobe: Der Gesamtabschluss führt die Kernverwaltung
        als eigene Trägerzeile. Beide Zahlen stammen aus verschiedenen
        Dokumenten verschiedener Jahre — dass sie übereinstimmen, ist die
        stärkste Bestätigung, die dieser Bestand hergibt."""
        try:
            rows = self._conn.execute(
                "SELECT year, label, result FROM council_income_statement "
                "WHERE sub_budget_no IS NULL AND result IS NOT NULL "
                "  AND label LIKE 'Summe ordentliche%' ORDER BY year").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        aus: dict[int, dict] = {}
        for r in rows:
            art = "revenues" if "Erträge" in r["label"] else "expenses"
            aus.setdefault(r["year"], {})[art] = r["result"]
        return aus

    def beteiligungsbericht_jahre(self) -> list[int]:
        """Berichtsjahrgänge, die eingelesen sind (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT report_year FROM council_companies "
                "ORDER BY report_year")]
        except sqlite3.OperationalError:
            return []

    def get_gesellschaften(self, report_year: int | None = None) -> list[dict]:
        """Die Gesellschaften eines Berichts — ohne Angabe die des jüngsten.

        „Der jüngste" ist hier die richtige Vorgabe und nicht Bequemlichkeit:
        Die Frage „was macht die GSG?" meint den heutigen Stand, und ein
        Bericht von 2022 nennt Aufsichtsräte, die längst ausgewechselt sind."""
        try:
            if report_year is None:
                years = self.beteiligungsbericht_jahre()
                if not years:
                    return []
                report_year = years[-1]
            rows = self._conn.execute(
                "SELECT * FROM council_companies WHERE report_year = ? "
                "ORDER BY classification", (report_year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_gesellschaft_texte(self, company: str,
                               report_year: int | None = None) -> list[dict]:
        """Die beschreibenden Abschnitte einer Gesellschaft."""
        try:
            if report_year is None:
                years = self.beteiligungsbericht_jahre()
                if not years:
                    return []
                report_year = years[-1]
            rows = self._conn.execute(
                "SELECT * FROM council_company_texts WHERE company = ? "
                "AND report_year = ?", (company, report_year)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def _gesellschaft_zeilen(self, tabelle: str, report_year: int | None,
                             ordnung: str) -> list[dict]:
        """Alle Zeilen einer Beteiligungs-Tabelle für **einen** Berichtsjahrgang.

        Ohne Jahresangabe der jüngste — dieselbe Vorgabe wie bei
        ``get_gesellschaften``, und aus demselben Grund: Wer fragt, wer im
        Aufsichtsrat sitzt, meint heute und nicht 2022.

        Ein Lesepfad für beide Tabellen, weil die Steckbrief-Seite ohnehin
        alle Gesellschaften auf einmal zeigt: 45 Einzelabfragen für 500 Zeilen
        wären eine Schleife um nichts."""
        try:
            if report_year is None:
                years = self.beteiligungsbericht_jahre()
                if not years:
                    return []
                report_year = years[-1]
            rows = self._conn.execute(
                f"SELECT * FROM {tabelle} WHERE report_year = ? "
                f"ORDER BY {ordnung}", (report_year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_gesellschaft_personen(self, report_year: int | None = None) -> list[dict]:
        """Die Aufsichtsorgane eines Berichtsjahrgangs, Person für Person.

        ``roles_assignable`` gilt je Gesellschaft: Ist es 0, ist
        ``position`` bei **allen** ihren Personen NULL (s. Tabellenkommentar
        und ``beteiligungsbericht.aufsichtsorgane``)."""
        return self._gesellschaft_zeilen("council_company_people",
                                         report_year, "company, sort_order")

    def get_gesellschaft_eigentuemer(self, report_year: int | None = None) -> list[dict]:
        """Wem die Gesellschaften gehören — ohne die Stammkapital-Summenzeile."""
        return self._gesellschaft_zeilen("council_company_owners",
                                         report_year, "company, sort_order")

    def get_gesellschaft_kennzahlen(self, company: str | None = None) -> list[dict]:
        """Die Kennzahlen-Zeitreihe — einer Gesellschaft oder aller."""
        try:
            if company is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_company_indicators "
                    "ORDER BY company, indicator, year").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_company_indicators "
                    "WHERE company = ? ORDER BY indicator, year",
                    (company,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_konzern_traeger(self, year: int | None = None) -> list[dict]:
        """Trägeraufstellung — wer wie viel zum Konzern beiträgt, in TEUR."""
        try:
            if year is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_group_entities ORDER BY year, kind, "
                    "amount_keur DESC").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_group_entities WHERE year = ? "
                    "ORDER BY kind, amount_keur DESC", (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_schulden(self) -> list[dict]:
        """Die Schuldenzeitreihe, aufsteigend nach Jahr.

        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler — der Haushalts-Bereich zeigt die Seite dann ohne
        Zeitreihe."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM council_debt ORDER BY year").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_ausgabenreihe(self) -> list[dict]:
        """Die lange Ausgabenreihe, aufsteigend nach Jahr.

        ``probes`` kommt als Liste heraus, nicht als gespeicherter String —
        das Frontend soll die Trennzeichen-Konvention nicht kennen müssen.
        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_expense_series ORDER BY year")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_gebuehren(self) -> list[dict]:
        """Alle Gebührenbereiche, ältester Jahrgang zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_fees ORDER BY year, area")]
        except sqlite3.OperationalError:
            return []

    def get_gebuehrensaetze(self) -> list[dict]:
        """Alle konkreten Tarife, jüngster Vorschlag zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_fee_rates "
                "ORDER BY year DESC, area, key")]
        except sqlite3.OperationalError:
            return []

    def get_haushalt_aenderungen_fhh(self, budget_year: int | None = None) -> dict:
        """Positionen und Summen der FHH-Änderungslisten, älteste zuerst.

        Fehlen die Tabellen (frische Datenbank ohne Ingest-Lauf), ist die
        Antwort leer statt ein Fehler — dieselbe Auskunft wie beim EHH."""
        wo, args = ("WHERE budget_year = ?", (budget_year,)) if budget_year else ("", ())
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT budget_year, list_key, year, seq, sub_budget, page_draft, product, "
                " label, planned_draft, inflow, outflow, commitment_authorizations, "
                " planned_new, explanation, author, document_id, herkunft_id "
                f"FROM council_budget_amendments_cash {wo} "
                "ORDER BY budget_year, list_key, year, seq", args)]
            summen = [dict(r) for r in self._conn.execute(
                "SELECT budget_year, list_key, year, kind, label, inflows, "
                " outflows, balance, commitment_authorizations, own, document_id, herkunft_id "
                f"FROM council_budget_amendments_cash_totals {wo} "
                "ORDER BY budget_year, list_key, year", args)]
        except sqlite3.OperationalError:
            return {"zeilen": [], "summen": []}
        return {"zeilen": zeilen, "summen": summen}

    def get_haushalt_aenderungen(self, budget_year: int | None = None) -> dict:
        """Positionen und Summen der Änderungslisten, älteste zuerst.

        Fehlen die Tabellen (frische Datenbank ohne Ingest-Lauf), ist die
        Antwort leer statt ein Fehler — dieselbe Auskunft wie bei den
        Nachbar-Schichten."""
        wo, args = ("WHERE budget_year = ?", (budget_year,)) if budget_year else ("", ())
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT budget_year, list_key, year, seq, sub_budget, page_draft, "
                " product, label, revenue, expense, explanation, "
                " author, document_id, herkunft_id FROM council_budget_amendments "
                f"{wo} ORDER BY budget_year, list_key, year, seq", args)]
            summen = [dict(r) for r in self._conn.execute(
                "SELECT budget_year, list_key, year, kind, label, revenues, "
                " expenses, balance, own, document_id, herkunft_id "
                "FROM council_budget_amendments_totals "
                f"{wo} ORDER BY budget_year, list_key, year", args)]
        except sqlite3.OperationalError:
            return {"zeilen": [], "summen": []}
        return {"zeilen": zeilen, "summen": summen}

    def get_haushaltssatzungen(self) -> list[dict]:
        """Alle Satzungs-Jahrgänge, ältester zuerst."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_budget_bylaw ORDER BY year, supplement")]
        except sqlite3.OperationalError:
            return []

    def get_haushaltsvollzug(self, budget_year: int | None = None,
                             totals_only: bool = False) -> list[dict]:
        """Vollzugs-Zeilen, ältester Stichtag zuerst.

        ``totals_only`` liefert nur die Summenzeilen — die Frage „wie läuft
        das Jahr?" braucht dreizehn Teilhaushalte nicht, und über acht
        Jahrgänge sind das der Unterschied zwischen 100 und 1.300 Zeilen."""
        wo, werte = [], []
        if budget_year is not None:
            wo.append("budget_year = ?")
            werte.append(budget_year)
        if totals_only:
            wo.append("is_total = 1")
        satz = (" WHERE " + " AND ".join(wo)) if wo else ""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_budget_execution" + satz
                + " ORDER BY budget_year, as_of, budget, sub_budget, kind",
                werte)]
        except sqlite3.OperationalError:
            return []

    def haushaltsvollzug_stichtage(self) -> list[dict]:
        """Je Jahrgang und Stichtag, welche Haushalte vorliegen.

        Das ist die Liste, aus der eine Oberfläche ihren Umschalter baut —
        und zugleich die Auskunft, wo ein Quartal fehlt: Wo ein Stichtag nur
        einen der beiden Haushalte führt, steht das hier und nicht in einer
        Lücke, die niemand sieht."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT budget_year, as_of, "
                "       GROUP_CONCAT(DISTINCT budget) AS budgets, "
                "       MIN(plan_basis) AS plan_basis "
                "FROM council_budget_execution "
                "GROUP BY budget_year, as_of ORDER BY budget_year, as_of")]
        except sqlite3.OperationalError:
            return []

    def get_wirtschaftsplaene(self, enterprise: str | None = None) -> list[dict]:
        """Die Wirtschaftspläne, ältester zuerst — je Betrieb oder alle."""
        try:
            if enterprise is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_business_plans ORDER BY enterprise, year")
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_business_plans WHERE enterprise = ? "
                    "ORDER BY year", (enterprise,))
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def get_anlagenspiegel(self) -> list[dict]:
        """Alle Zeilen, nach Jahr und Gliederung. ``probes`` als Liste."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_fixed_assets ORDER BY year, nr")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_vermoegensgruppen(self) -> list[dict]:
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_vermoegensgruppen ORDER BY year, group_name")]
        except sqlite3.OperationalError:
            return []

    def get_buergschaften(self) -> list[dict]:
        """Der Bürgschaftsbestand je Jahr, aufsteigend.

        ``exact`` und ``out_next_year`` kommen als Wahrheitswerte heraus, nicht
        als 0/1: Sie sind Angaben über die Belegqualität und werden im Frontend
        als solche gelesen, nicht gerechnet."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_buergschaften ORDER BY year")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
            r["exact"] = bool(r["exact"])
            r["out_next_year"] = bool(r["out_next_year"])
        return rows

    def get_integrierte_schulden(self) -> list[dict]:
        """Die integrierten Schulden je Stichtag, aufsteigend.

        Kommt als Liste, obwohl die Anzeige nur den jüngsten Stichtag zeigt:
        Eine zweite Ausgabe soll die erste nicht stillschweigend ersetzen —
        wer sie vergleichen will, sieht wenigstens, dass es zwei gibt (und
        findet in ``council/integrierte_schulden.KEINE_REIHE``, warum er es
        besser lässt)."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_integrated_debt ORDER BY year")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_nachbewilligungen(self) -> list[dict]:
        """Die RIS-Serie, chronologisch. ``committees`` kommt als Liste heraus."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_supplementary_approvals ORDER BY template_number")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            try:
                r["committees"] = json.loads(r.get("committees") or "[]")
            except (TypeError, ValueError):
                r["committees"] = []
        return rows

    def get_nachbewilligung_jahre(self) -> list[dict]:
        """Die Jahrgänge aus dem Rechenschaftsbericht, je mit ihren Kanälen.

        Die Kanäle hängen als Liste ``channels`` an ihrem Jahr — anders als bei
        der Herkunft, die als eigenes Verzeichnis reist: Vier Zeilen je Jahr
        sind keine Wiederholung, die sich zu vermeiden lohnte, und die Seite
        liest sie ohnehin immer zusammen."""
        try:
            years = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_supplementary_years ORDER BY year")]
            channels = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_supplementary_channels "
                "ORDER BY year, rowid")]
        except sqlite3.OperationalError:
            return []
        nach_jahr: dict[int, list[dict]] = {}
        for k in channels:
            nach_jahr.setdefault(int(k["year"]), []).append(k)
        for j in years:
            j["channels"] = nach_jahr.get(int(j["year"]), [])
        return years

    def get_liquidity(self) -> list[dict]:
        """Die Monatsreihe, aufsteigend; ``probes`` als Liste."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_liquidity ORDER BY month")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_enterprise_accounts(self, enterprise: str | None = None) -> list[dict]:
        """Alle Kennzahlen, aufsteigend nach Betrieb, Jahr, Kennzahl."""
        try:
            sql = "SELECT * FROM council_enterprise_accounts"
            args: tuple = ()
            if enterprise:
                sql += " WHERE enterprise = ?"
                args = (enterprise,)
            rows = [dict(r) for r in self._conn.execute(sql + " ORDER BY enterprise, year, metric", args)]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_loan_notices(self) -> list[dict]:
        """Die Unterrichtungen, aufsteigend nach Berichtszeitraum; ``probes`` als Liste."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_loan_notices ORDER BY period_from, template_number")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_loan_items(self) -> list[dict]:
        """Alle Posten, aufsteigend nach Berichtszeitraum, Vorlage und Nummer."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT i.*, n.period_from, n.period_to FROM council_loan_items i "
                "JOIN council_loan_notices n ON n.template_number = i.template_number "
                "ORDER BY n.period_from, i.template_number, i.seq")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def get_spenden(self) -> list[dict]:
        """Die Spendenreihe je Vorlage, aufsteigend nach Sitzungsdatum.

        ``probes`` kommt als Liste heraus. Fehlt die Tabelle (frische
        Datenbank ohne Ingest-Lauf), ist die Antwort leer statt ein Fehler."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_donations ORDER BY session_date, template_number")]
        except sqlite3.OperationalError:
            return []
        for r in rows:
            r["probes"] = [p for p in (r.get("probes") or "").split(",") if p]
        return rows

    def get_spenden_verworfen(self) -> list[dict]:
        """Die Zeilen ohne Zweitstelle, mit dem Satz, warum sie fehlen."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_donations_rejected ORDER BY session_date, template_number")]
        except sqlite3.OperationalError:
            return []

    def get_steuerplan(self) -> list[dict]:
        """Plan und Ist je Steuerart und Jahr, aufsteigend.

        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler — die Seite zeigt den Block dann schlicht nicht."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT year, kind, plan, actual, provisional FROM council_tax_plan "
                "ORDER BY year, kind")]
        except sqlite3.OperationalError:
            return []

    def get_hebesaetze(self) -> list[dict]:
        """Die Hebesätze je Änderungsjahr, aufsteigend.

        **Nur Änderungsjahre** — die Lücken dazwischen sind keine fehlenden
        Daten, sondern die Aussage: Ein Hebesatz gilt, bis der Rat ihn ändert.
        Wer diese Reihe zeichnet, zeichnet eine Treppe."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT year, kind, rate, prior_rate FROM council_tax_rates "
                "ORDER BY year, kind")]
        except sqlite3.OperationalError:
            return []

    def get_investitionen_ist(self) -> list[dict]:
        """Die Ist-Reihe, aufsteigend nach Jahr, mit ihrer Aufteilung.

        Je Jahrgang ein dict mit ``arten`` — den Auszahlungsarten in der
        Spaltenfolge der Quelle. Fehlt die Tabelle (frische Datenbank ohne
        Ingest-Lauf), ist die Antwort leer statt ein Fehler."""
        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investments_actual ORDER BY year")]
            arten = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investments_actual_kinds "
                "ORDER BY year, sort_order")]
        except sqlite3.OperationalError:
            return []
        je_jahr: dict[int, list[dict]] = {}
        for a in arten:
            je_jahr.setdefault(a["year"], []).append(
                {"field": a["field"], "title": a["title"], "amount": a["amount"]})
        for r in rows:
            r["arten"] = je_jahr.get(r["year"], [])
        return rows

    def get_investitionen_ist_verworfen(self) -> list[dict]:
        """Die verworfenen Jahrgänge, aufsteigend — je Jahr Grund und Differenz.

        Was hier steht, steht bewusst **nicht** in der Reihe: Diese Jahrgänge
        haben ihre Probe nicht bestanden. Die Tabelle beantwortet die eine
        Frage, die eine Lücke im Bild aufwirft — „wie weit lag es
        auseinander?" — und beantwortet sie mit der gemessenen Zahl statt mit
        einem Adjektiv. Fehlt die Tabelle (frische Datenbank ohne
        Ingest-Lauf), ist die Antwort leer statt ein Fehler."""
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_investments_actual_rejected ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_staedtevergleich(self, series: str | None = None) -> list[dict]:
        """Der Städtevergleich — eine Reihe oder beide.

        Sortiert nach Jahr und Stadt, damit die Oberfläche nichts umsortieren
        muss. Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die
        Antwort leer statt ein Fehler — der Haushalts-Bereich zeigt die Seite
        dann schlicht ohne Vergleichszahlen."""
        try:
            if series is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_city_comparison "
                    "ORDER BY series, year, city, indicator").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_city_comparison WHERE series = ? "
                    "ORDER BY year, city, indicator", (series,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_gewerbesteuerstatistik(self, key: str | None = None) -> list[dict]:
        """Die Gewerbesteuerstatistik — eine Stadt oder alle, aufsteigend nach Jahr.

        Fehlt die Tabelle (frische Datenbank ohne Ingest-Lauf), ist die Antwort
        leer statt ein Fehler: Der Steuer-Steckbrief zeigt den Block dann ohne
        diese Zahlen, wie bei den anderen Schichten auch."""
        try:
            if key is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_trade_tax_statistics "
                    "ORDER BY year, city").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_trade_tax_statistics "
                    "WHERE key = ? ORDER BY year", (key,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def get_produkte(self, year: int, sub_budget_no: int | None = None,
                     suche: str | None = None, office: str | None = None,
                     controllability: str | None = None,
                     limit: int | None = None) -> list[dict]:
        """Produkte eines Jahres, teuerste zuerst (nach Zuschussbedarf).

        Suche und Filter laufen bewusst HIER und nicht im Frontend: Mit dem
        Steckbrief trägt jede Zeile mehrere hundert Zeichen Fließtext — knapp
        400 davon über die Leitung zu schicken, damit der Browser sie filtert,
        wäre Verschwendung. Gesucht wird über Name, Nummer, Amt und
        Kurzbeschreibung; ``LIKE`` genügt bei dieser Menge (kein FTS nötig)."""
        wo = ["year = ?"]
        args: list = [year]
        if sub_budget_no is not None:
            wo.append("sub_budget_no = ?")
            args.append(sub_budget_no)
        if office:
            wo.append("office = ?")
            args.append(office)
        if controllability:
            wo.append("controllability = ?")
            args.append(controllability)
        if suche and suche.strip():
            # Jeder Begriff muss irgendwo vorkommen (UND über die Begriffe,
            # ODER über die Felder) — so grenzt „archiv stadt" wirklich ein.
            for wort in suche.split()[:6]:
                wo.append("(product_name LIKE ? OR product_no LIKE ? OR office LIKE ? "
                          "OR short_description LIKE ?)")
                args.extend([f"%{wort}%"] * 4)
        sql = ("SELECT * FROM council_products WHERE " + " AND ".join(wo)
               + " ORDER BY result ASC" + (" LIMIT ?" if limit else ""))
        if limit:
            args.append(limit)
        return [dict(r) for r in self._conn.execute(sql, args)]

    def product(self, year: int, product_no: str) -> dict | None:
        """Ein Produkt samt Steckbrief — die Steckbrief-Ansicht braucht es
        auch dann, wenn es durch Suche oder Filter gerade nicht in der Liste
        stünde."""
        row = self._conn.execute(
            "SELECT * FROM council_products WHERE year = ? AND product_no = ?",
            (year, product_no)).fetchone()
        return dict(row) if row else None

    def produkt_facetten(self, year: int) -> dict:
        """Womit sich die Produktliste filtern lässt — Ämter und Spielraum-
        Stufen mit Anzahl, plus wie viele Produkte überhaupt einen Steckbrief
        tragen. Letzteres gehört sichtbar auf die Seite: Ein Filter, der die
        halbe Liste verschluckt, muss sich erklären."""
        aemter = [{"office": r[0], "count": r[1]} for r in self._conn.execute(
            "SELECT office, COUNT(*) FROM council_products WHERE year = ? AND office IS NOT NULL "
            "GROUP BY office ORDER BY COUNT(*) DESC, office", (year,))]
        spielraum = {r[0]: r[1] for r in self._conn.execute(
            "SELECT controllability, COUNT(*) FROM council_products "
            "WHERE year = ? AND controllability IS NOT NULL "
            "GROUP BY controllability", (year,))}
        felder = {}
        for field in ("short_description", "legal_basis", "controllability",
                     "scope", "target_group"):
            felder[field] = self._conn.execute(
                f"SELECT COUNT(*) FROM council_products WHERE year = ? "
                f"AND {field} IS NOT NULL AND {field} != ''", (year,)).fetchone()[0]
        return {"aemter": aemter, "spielraum": spielraum, "mit_feld": felder}

    def produkte_jahre(self) -> list[int]:
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_products ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def produkt_abdeckung(self) -> dict[str, list[int]]:
        """Je Produktnummer die Jahre, in denen sie im Bestand steht.

        Nicht jedes Jahr deckt jeden Teilhaushalt (die Pläne liegen nicht für
        jeden Jahrgang auslesbar vor) — die Trefferliste soll das je Produkt
        ehrlich anschreiben können (Abdeckungs-Badge, H4-04), statt eine
        durchgehende Reihe zu suggerieren. Eine Abfrage für alle Produkte:
        Die Liste ist klein (wenige hundert Nummern), und je Treffer einzeln
        zu fragen wäre ein N+1."""
        out: dict[str, list[int]] = {}
        try:
            rows = self._conn.execute(
                "SELECT product_no, year FROM council_products ORDER BY year")
        except sqlite3.OperationalError:
            return out
        for nr, year in rows:
            out.setdefault(nr, []).append(year)
        return out

    def get_pruefberichte(self, year: int | None = None) -> list[dict]:
        """Prüfungsfeststellungen — ein Jahrgang oder alle, in Dokumentreihenfolge.

        Ohne Argument alle: Die Ketten über die Jahrgänge („seit wann steht
        das offen?") lassen sich nur aus dem Gesamtbestand bilden."""
        try:
            if year is None:
                rows = self._conn.execute(
                    "SELECT * FROM council_audit_reports ORDER BY year, seq").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM council_audit_reports WHERE year = ? ORDER BY seq",
                    (year,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def pruefbericht_jahre(self) -> list[int]:
        """Jahrgänge mit eingelesenem Schlussbericht (aufsteigend)."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_audit_reports ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def get_steuerkraft(self) -> list[dict]:
        """Steuerkraft/Zuweisungen je Jahr, älteste zuerst."""
        return [dict(r) for r in self._conn.execute(
            "SELECT year, tax_index, tax_capacity_per_capita, allocations, allocations_per_capita "
            "FROM council_tax_capacity ORDER BY year")]

    def get_finanzausgleich(self, key: str = "403000") -> list[dict]:
        """Die drei Komponenten des Finanzausgleichs für **eine** Stadt.

        Liest ``series='fiscal_equalization'`` aus ``council_city_comparison`` und
        dreht sie in eine Zeile je Ausgleichsjahr: ``{year,
        zuweisungen_gemeindeaufgaben, zuweisungen_kreisaufgaben,
        zuweisungen_uebertragener_wirkungskreis, finanzausgleichsumlage,
        nettobetrag}``, alle in **Tausend Euro** (so führt das Blatt sie).

        Warum eine eigene Lesefunktion und nicht ``get_staedtevergleich``: Die
        Haushalts-Übersicht braucht acht Zahlen je Jahr für Oldenburg, nicht
        die 240 Zeilen aller acht Städte. Die Übersicht ist mit 1,6 MB ohnehin
        die schwerste Antwort des Bereichs; der Städtevergleich hat seinen
        eigenen Endpunkt und behält ihn.
        """
        try:
            rows = self._conn.execute(
                "SELECT year, indicator, value FROM council_city_comparison "
                "WHERE series = 'fiscal_equalization' AND key = ? "
                "ORDER BY year", (key,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        nach_jahr: dict[int, dict] = {}
        for r in rows:
            nach_jahr.setdefault(int(r["year"]), {"year": int(r["year"])})[
                r["indicator"]] = r["value"]
        return [nach_jahr[j] for j in sorted(nach_jahr)]

    def buergschafts_vorlagen(self, limit: int = 40) -> list[dict]:
        """Die Ratsbeschlüsse hinter dem Bürgschaftsbestand, neueste zuerst.

        DIESE BETRÄGE DÜRFEN NIE ADDIERT WERDEN, und die Liste selbst zeigt
        warum: Unter den 21 Vorlagen im Bestand ist „Verlängerung
        Ausfallbürgschaft … über 300.000 Euro für die Volkshochschule"
        (25/0826) dieselbe Bürgschaft wie 23/0112 zwei Jahre zuvor, und
        „Anpassung Ausfallbürgschaft … Weser-Ems Halle" (25/0929) ändert eine
        bestehende. Eine Summe über die Liste zählte dieselbe Zusage mehrfach.

        Was der Bestand wirklich ist, sagt nur der Jahresabschluss
        (``council_buergschaften``) — er ist eine Stichtagsgröße und keine
        Summe von Beschlüssen. Die Liste hier ist die **Geschichte** dazu:
        wann der Rat worüber entschieden hat.

        Je Vorlage der jüngste Beschluss: Finanzausschuss und Rat entscheiden
        dieselbe Sache, und zwei Zeilen für einen Vorgang wären eine Dublette
        ohne Erkenntnisgewinn.
        """
        try:
            rows = self._conn.execute(
                """SELECT v.template_number, v.title, v.document_url,
                          MAX(s.session_date) AS date,
                          (SELECT d2.id FROM council_decisions d2
                            JOIN council_sessions s2 ON s2.ksinr = d2.ksinr
                           WHERE d2.template_number = v.template_number
                           ORDER BY s2.session_date DESC LIMIT 1) AS decision_id
                     FROM council_templates v
                     LEFT JOIN council_decisions d ON d.template_number = v.template_number
                     LEFT JOIN council_sessions s ON s.ksinr = d.ksinr
                    WHERE v.title LIKE '%bürgschaft%'
                    GROUP BY v.template_number
                    ORDER BY date DESC NULLS LAST, v.template_number DESC
                    LIMIT ?""", (limit,)).fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        return [dict(r) for r in rows]

    def haushalt_weg(self, year: int | None = None) -> list[dict]:
        """Wann ein Haushaltsjahr welche Station im Rat durchlaufen hat.

        Je Haushaltsjahr eine Runde mit drei Abschnitten:

        - ``einbringung``: die früheste Beratung einer Entwurfs-Vorlage — der
          Moment, ab dem der Entwurf öffentlich einsehbar ist,
        - ``fachausschuesse``: die Teilhaushalts-Berichte danach, als Zeitraum
          und Gremienliste (einzeln aufzuzählen hilft niemandem, es sind rund
          ein Dutzend Termine),
        - ``stationen``: die Beratungsfolge der Sammelvorlage „Haushalt
          <year> - Beschluss" bis zur Entscheidung im Rat, je Station mit dem
          Ergebnis, das die Tagesordnung ausweist.

        **Die Fensterregel** (Einbringung … letzte Beschluss-Station) ist kein
        Schönheitsfilter, sondern Notwehr gegen falsch betitelte Vorlagen:
        22/0824 heißt „Haushalt 2022 …", wurde aber im November 2022 beraten
        und gehört zur Runde 2023; 25/0643 heißt „Haushalt 2025 …" und liegt
        in der Runde 2026. Ohne die Regel zöge je ein Ausreißer den Zeitraum
        der Fachausschuss-Runde um ein volles Jahr auf.

        Ohne Sammelvorlage gibt es keine Runde: Das Haushaltsjahr 2018 wurde
        vor dem Beginn unseres Bestands (Januar 2018) beschlossen.
        """
        vorlagen: dict[int, dict[str, list[dict]]] = {}
        for r in self._conn.execute(
                "SELECT kvonr, template_number, title FROM council_templates "
                "WHERE title LIKE 'Haushalt%' OR title LIKE 'HH %'").fetchall():
            m = self._HH_TITEL.match(r["title"] or "")
            if not m:
                continue                      # „Haushaltsplan der …", „Haushaltsvermerk …"
            j = int(m.group(1))
            if year is not None and j != year:
                continue
            title = r["title"]
            if "Verwaltungsentwurf" in title:
                art = "part" if any(k in title for k in self._HH_TEILBERICHT) else "draft"
            elif "Beschluss" in title:
                art = "official_text"
            else:
                continue
            vorlagen.setdefault(j, {"draft": [], "part": [], "official_text": []})[art].append(dict(r))

        runden = []
        for j in sorted(vorlagen):
            runde = self._haushalt_runde(j, vorlagen[j])
            if runde:
                runden.append(runde)
        return runden

    def _haushalt_runde(self, year: int, teile: dict[str, list[dict]]) -> dict | None:
        """Eine Haushaltsrunde zusammensetzen — siehe ``haushalt_weg``."""
        beschluss_vorlagen = teile["official_text"]
        stationen = self._hh_beratungen([v["kvonr"] for v in beschluss_vorlagen])
        if not stationen:
            return None

        entwurf_beratungen = self._hh_beratungen(
            [v["kvonr"] for v in (*teile["draft"], *teile["part"])])
        einbringung = entwurf_beratungen[0] if entwurf_beratungen else None

        von = einbringung["date"] if einbringung else stationen[0]["date"]
        bis = stationen[-1]["date"]
        fach = [b for b in entwurf_beratungen[1:] if von <= b["date"] <= bis]

        # Der Kernhaushalt ist der Punkt, an dem tatsächlich abgestimmt wird —
        # die Sammelvorlage bündelt daneben Stiftungen und Eigenbetriebe. Der
        # Beschluss trägt den Jahrgang im Titel, deshalb ist er ohne Raten
        # zuzuordnen: über die Sitzung, nicht über eine geratene TOP-Nummer.
        votum = {}
        for d in self._conn.execute(
                "SELECT id, ksinr, item_number, outcome, vote, no_votes, abstentions "
                "FROM council_decisions WHERE kind = 'decision' AND title LIKE ? "
                "ORDER BY id", (f"Haushaltssatzung und Haushaltsplan {year}%",)).fetchall():
            votum.setdefault(d["ksinr"], dict(d))

        for s in stationen:
            s["votum"] = votum.get(s["ksinr"])

        return {
            "year": year,
            "template_number": beschluss_vorlagen[0]["template_number"] if beschluss_vorlagen else None,
            "kvonr": beschluss_vorlagen[0]["kvonr"] if beschluss_vorlagen else None,
            "einbringung": einbringung,
            "fachausschuesse": {
                "von": fach[0]["date"], "bis": fach[-1]["date"],
                "count": len(fach),
                "committees": sorted({b["committee"] for b in fach}),
            } if fach else None,
            "stationen": stationen,
        }

    def _hh_beratungen(self, kvonrs: list[int]) -> list[dict]:
        """Beratungen mehrerer Vorlagen, nach Datum sortiert, je mit dem
        Ergebnis aus der Tagesordnung.

        Die TOP-Nummer kommt aus `council_agenda_items` und nicht aus
        `council_deliberations.top`: Nur dort trägt sie das Präfix („Ö 6"), und
        „Ö 6" und „N 6" sind verschiedene Punkte."""
        if not kvonrs:
            return []
        platz = ",".join("?" * len(kvonrs))
        rows = self._conn.execute(
            f"""SELECT b.kvonr, b.date, b.committee, b.result AS role, b.is_public,
                       b.ksinr, v.template_number, v.title AS template_title,
                       a.item_number AS top, a.title AS top_titel
                  FROM council_deliberations b
                  JOIN council_templates v ON v.kvonr = b.kvonr
             LEFT JOIN council_agenda_items a ON a.ksinr = b.ksinr AND a.kvonr = b.kvonr
                 WHERE b.kvonr IN ({platz})
              ORDER BY b.date, b.committee""", kvonrs).fetchall()
        out = []
        for r in rows:
            s = dict(r)
            s["result"] = self._hh_ergebnis(s.pop("top_titel"))
            # Jede Station trägt den Schlüssel, auch wenn nur die Stationen der
            # Sammelvorlage ihn je füllen — eine Station mit und eine ohne
            # `votum` wären zwei Formen derselben Sache.
            s["votum"] = None
            out.append(s)
        return out

    @staticmethod
    def _hh_ergebnis(top_titel: str | None) -> str | None:
        """Das Ergebnis, das die Tagesordnung an den Punkt schreibt —
        „geändert beschlossen", „zurückgestellt/abgesetzt", „zur Kenntnis
        genommen". Die angehängte Stimmenzählung bleibt weg: Sie steht bei
        einem Teil der Punkte und fehlt beim Rest, taugt also nicht als
        Angabe, auf die sich eine Seite verlassen könnte."""
        if not top_titel or "Beschluss: " not in top_titel:
            return None
        rest = top_titel.split("Beschluss: ", 1)[1].strip()
        return rest.split("Abstimmung:")[0].strip() or None

    def haushalt_streit(self, year: int | None = None) -> list[dict]:
        """Die politische Auseinandersetzung um jeden Haushaltsjahrgang.

        Je Haushaltsjahr eine Runde mit ihren ``stationen`` — in Oldenburg
        sind das der Ausschuss für Finanzen und Beteiligungen und der Rat.
        Jede Station trägt:

        - ``antraege``: die Änderungslisten, die dort zur Abstimmung standen,
          mit ``author`` (Fraktion/Gruppe) und ``outcome``. Der **Inhalt**
          einer Liste — welche Position um welchen Betrag — steht nicht dabei:
          Er liegt in den Anlagen-PDFs der Vorlage, die nicht als Volltext im
          Bestand sind. Was hier steht, ist „wer wollte ändern und kam damit
          durch", nicht „was genau".
        - ``debatte``: die Wortbeiträge unter dem Sammelpunkt, in der
          Reihenfolge des Protokolls. Keine Auswahl, keine Zusammenfassung —
          wer kürzt, kürzt für alle gleich, und das tut erst die Anzeige.
        - ``official_text``: die Schlussabstimmung über die Haushaltssatzung.

        Der Ausschuss stimmt über dieselben Listen ab wie der Rat, oft mit
        anderem Ergebnis; deshalb stehen beide Stationen nebeneinander statt
        zusammengefasst.
        """
        from council import haushaltsdebatte as hd

        anker: dict[int, dict[int, dict]] = {}
        for r in self._conn.execute(
                "SELECT d.id, d.ksinr, d.item_number, d.title, d.outcome, d.vote, "
                "       d.no_votes, d.abstentions, d.raw_result, d.template_number, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.kind = 'decision' AND (d.title LIKE 'Haushaltssatzung und Haushaltsplan%' "
                "   OR d.title LIKE 'Haushalt 2%')").fetchall():
            title = (r["title"] or "").strip()
            satzung = self._STREIT_SATZUNG.match(title)
            sammel = self._STREIT_SAMMEL.match(title)
            if not satzung and not sammel:
                continue
            j = int((satzung or sammel).group(1))
            if year is not None and j != year:
                continue
            eintrag = anker.setdefault(j, {}).setdefault(r["ksinr"], {
                "ksinr": r["ksinr"],
                "committee": r["committee"],
                "date": r["session_date"],
                "top": None,
                "official_text": None,
            })
            if satzung:
                eintrag["official_text"] = {
                    "id": r["id"], "top": r["item_number"], "title": title,
                    "outcome": r["outcome"], "vote": r["vote"],
                    "no_votes": r["no_votes"], "abstentions": r["abstentions"],
                    "wortlaut": (r["raw_result"] or "").strip() or None,
                    "template_number": r["template_number"],
                }
                if not eintrag["top"]:
                    eintrag["top"] = self._streit_oberpunkt(r["item_number"])
            else:
                # Der Sammelpunkt selbst — die verlässlichste Angabe für die Debatte.
                eintrag["top"] = (r["item_number"] or "").strip() or eintrag["top"]
                if eintrag["official_text"] is None:
                    eintrag["official_text"] = {
                        "id": r["id"], "top": r["item_number"], "title": title,
                        "outcome": r["outcome"], "vote": r["vote"],
                        "no_votes": r["no_votes"], "abstentions": r["abstentions"],
                        "wortlaut": (r["raw_result"] or "").strip() or None,
                        "template_number": r["template_number"],
                    }

        runden = []
        for j in sorted(anker):
            stationen = []
            # Am selben Tag tagt erst der Ausschuss, dann der Rat — das Datum
            # allein stellt sie sonst in beliebiger Reihenfolge nebeneinander.
            for st in sorted(anker[j].values(),
                             key=lambda s: (s["date"], s["committee"] == "Rat", s["ksinr"])):
                stationen.append(self._streit_station(st, hd))
            if stationen:
                runden.append({"year": j, "stationen": stationen})
        return runden

    @staticmethod
    def _streit_oberpunkt(item_number: str | None) -> str | None:
        """Der Sammelpunkt über einer Schlussabstimmung: „6.5" → „6",
        „7.1.7" → „7.1". Unter ihm steht die Debatte, unter seinen
        Unterpunkten stehen die Abstimmungen."""
        nr = (item_number or "").strip().rstrip(".")
        if "." not in nr:
            return nr or None
        return nr.rsplit(".", 1)[0]

    def _streit_station(self, st: dict, hd) -> dict:
        """Eine Station anreichern: Änderungslisten, Debatte, Protokoll-Link."""
        ksinr, top = st["ksinr"], st["top"]

        antraege = []
        if top:
            praefix = top + "."
            for r in self._conn.execute(
                    "SELECT ksinr, item_number, title, outcome, vote FROM council_decisions "
                    "WHERE ksinr = ? AND kind = 'subvote' ORDER BY position", (ksinr,)).fetchall():
                nr = (r["item_number"] or "").strip()
                if nr != top and not nr.startswith(praefix):
                    continue
                antrag = hd.antrag_aus_zeile(dict(r))
                if antrag:
                    antraege.append(antrag.als_dict())

        prot = self._conn.execute(
            "SELECT document_url, raw_text FROM council_protocols WHERE ksinr = ?",
            (ksinr,)).fetchone()
        debatte: list[dict] = []
        if prot and prot["raw_text"] and top:
            anwesende = [dict(a) for a in self._conn.execute(
                "SELECT name, party, role FROM council_attendance WHERE ksinr = ?", (ksinr,)).fetchall()]
            # Säubern, schneiden, zerlegen — mit Gedächtnis über den Inhalt.
            # Es bleibt beim Rechnen zur Lesezeit (s. Kopf von `haushalt_streit`);
            # nur wird dasselbe Protokoll nicht bei jedem Aufruf neu zerlegt.
            debatte = hd.debatte_zu_top(prot["raw_text"], top, anwesende)

        return {
            **st,
            "antraege": antraege,
            "debatte": debatte,
            "minutes_url": prot["document_url"] if prot else None,
        }
