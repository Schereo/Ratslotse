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
import re
import sqlite3
from datetime import datetime

from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis


class HaushaltMixin(StoreBasis):
    """Die Haushalts-Abfragen von :class:`council.store.CouncilStore`.

    Nur zum Mitvererben gedacht; ``self._conn`` und die übrigen Helfer kommen
    von dort.
    """

    #: Welcher Beschluss zu einem Dokument der maßgebliche ist. Der Rat zuerst
    #: — eine Vorlage läuft durch mehrere Gremien, aber verabschiedet wird sie
    #: dort. Innerhalb eines Gremiums die jüngste Sitzung: Ein vertagter Punkt
    #: kommt wieder, und es gilt, was zuletzt entschieden wurde. Dieselbe
    #: Ordnung nutzt schon `vorlage_beschluesse` (s. u. „committee LIKE 'Rat%'").
    _BESCHLUSS_ORDNUNG = ("ORDER BY (cs.committee LIKE 'Rat%') DESC, "
                          "cs.session_date DESC, d.id DESC")

    #: Welches **Dokument** hinter einer Quelle des Haushalts-Bereichs steht —
    #: je Schlüssel die Tabelle, ihre Jahresspalte, eine Einschränkung und die
    #: Alt-Spalte mit der URL.
    #:
    #: Die Schlüssel sind die des Quellenverzeichnisses im Frontend
    #: (``web/frontend/lib/haushalt-quellen.ts``). Das ist Absicht und der
    #: einzige Grund, warum diese Zuordnung hier steht und nicht dort: Welche
    #: Zeile aus welchem Dokument stammt, weiß die Datenbank — das Frontend
    #: kennt nur den Absatz, der eine ganze Seite beschreibt. Wer einen
    #: Schlüssel dort ergänzt, ergänzt ihn hier; wer ihn hier vergisst,
    #: bekommt keinen kaputten Link, sondern den Rückfall auf die statische
    #: Adresse (und das Frontend schreibt dann „im Ratsinformationssystem
    #: suchen" statt „Dokument öffnen").
    #:
    #: Die Alt-Spalte ist die Rückfallebene für Bestände, die vor der
    #: Herkunfts-Vereinheitlichung (#513) geschrieben wurden: Dort steht die
    #: URL an der Datenzeile, aber noch keine ``herkunft_id``. Die beiden
    #: Konzern-Tabellen haben keine — sie sind erst mit der Herkunft
    #: entstanden (s. ``_HERKUNFT_ALTFELDER``).
    _DOKUMENT_QUELLEN: dict[str, tuple[str, str, str | None, str | None]] = {
        "plan":                 ("council_budget", "year", None, "source_url"),
        # Die zwei Ebenen eines Jahresabschlusses stehen in derselben Tabelle
        # und im selben Dokument, tragen aber verschiedene Herkünfte (eigene
        # Abschnitte, eigene Proben). Beide Schlüssel gibt es im Verzeichnis.
        "jahresabschluss":      ("council_income_statement", "year",
                                 "sub_budget_no IS NULL", "source_url"),
        "ergebnisrechnung_thh": ("council_income_statement", "year",
                                 "sub_budget_no IS NOT NULL", "source_url"),
        # Dritte Ebene desselben Dokuments: Abschnitt 4.1, die Kassensicht.
        "cash_flow_statement":       ("council_cash_flow_statement", "year", None, None),
        # Der Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — dieselbe
        # Postengliederung für Jahre ohne Abschluss.
        #
        # Der Filter auf ``kind = 'budget'`` ist hier PFLICHT und keine
        # Verfeinerung: Ein Dokument trägt sein Planjahr UND drei
        # Finanzplanungsjahre, dieselbe Jahreszahl kommt also in drei
        # Haushaltsplänen vor (2026 im Plan 2024 als Vorausschau, im Plan 2025
        # als Vorausschau, im Plan 2026 als Ansatz). Ohne den Filter stünden an
        # einer Ansatz-Zahl bis zu drei Dokumente, und zwei davon meinen etwas
        # anderes. Mit ihm gilt ``year == plan_budget_year``, und es bleibt genau
        # eines.
        "income_budget":     ("council_income_budget", "year",
                                 "t.kind = 'budget'", None),
        # Vierte Ebene: Abschnitt 2.1, die Bilanz. Der älteste Stichtag (2016)
        # stammt aus der Vorjahresspalte des Abschlusses 2017 — er trägt
        # deshalb dessen Dokument, mit eigener Fundstelle.
        "bilanz":               ("council_balance_sheet", "year", None, None),
        # Der einzige Schlüssel, hinter dem je Jahrgang MEHRERE Dokumente
        # stehen: Ein Produkt-Jahrgang verteilt sich auf zwölf bis dreizehn
        # Teilhaushalts-Anlagen (s. finanzquellen.Finanzquelle).
        "teilhaushalt":         ("council_products", "year", None, "source_url"),
        "pruefbericht":         ("council_audit_report_sources", "year", None, "url"),
        "gesamtabschluss":      ("council_group_items", "year", None, None),
        # Nur die geprüften Zeilen: Die Bezugsgröße „Gesamtbetrag des
        # Finanzhaushaltes" steht in derselben Datei, aber an einer anderen
        # Fundstelle und ohne Probe — ohne diesen Filter stünden je Jahrgang
        # zwei Dokumente im Verzeichnis, wo es eines ist.
        "investitionen":        ("council_investments", "year",
                                 "t.level = 'sub_budget'", None),
        # Alle Zeilen eines Jahrgangs teilen sich eine Herkunft; die
        # `gesamt`-Zeile gibt es genau einmal und steht hier für das Dokument.
        "investitionsprogramm": ("council_investment_measures", "year",
                                 "t.level = 'total'", None),
        # Ein Jahrgang, zwei Herkünfte (Teil A und Teil B im selben PDF, aber
        # unter verschiedenen Proben). Beide zeigen auf dieselbe Datei; die
        # Fundstelle unterscheidet sie, und `DISTINCT` fasst sie deshalb nicht
        # zusammen — genau richtig, denn ein Beleg an einer Beamtenzahl soll
        # „Teil A" sagen und nicht „Stellenplan".
        "stellenplan":          ("council_staff_plan", "budget_year", None, None),
        # Der einzige Schlüssel, dessen Jahresspalte NICHT das Datenjahr ist:
        # Ein Bericht liefert fünf Jahrgänge, gehört aber zu genau einem
        # Dokument — und das ist seines.
        "indicators":           ("council_indicators", "report_year", None, None),
        # Die drei Schichten vom 20.08.2026. Sie standen bis zum 21.08. NICHT
        # hier, und man hat es der Seite angesehen: Unter 33 Wirtschaftsplänen
        # aus sieben Betrieben stand eine einzige Quelle, deren Link auf die
        # Startseite des Ratsinformationssystems führte. Der Eintrag hier ist
        # der ganze Unterschied zwischen „kommt aus dem RIS" und „steht in
        # diesem PDF".
        #
        # Wie ``teilhaushalt`` tragen alle drei je Jahrgang MEHRERE Dokumente,
        # und das ist hier keine Eigenheit, sondern der Kern: Ein Jahrgang
        # Wirtschaftsplan besteht aus sieben Plänen von sieben Betrieben, und
        # jeder ist ein eigenes Papier mit eigener Vorlagennummer.
        "wirtschaftsplan":      ("council_business_plans", "year", None, None),
        # Nachträge tragen eine eigene Satzung und ein eigenes Dokument; der
        # Schlüssel unterscheidet sie nicht, die Fundstelle tut es.
        "budget_bylaw":     ("council_budget_bylaw", "year", None, None),
        "fees":            ("council_fees", "year", None, None),
        # Der Haushaltsvollzug trägt je Jahrgang bis zu ACHT Dokumente (vier
        # Stichtage × zwei Haushalte), und jedes ist ein eigenes Papier mit
        # eigener Vorlagennummer — dieselbe Lage wie beim Wirtschaftsplan.
        # Gefiltert wird auf die Summenzeile, damit der Join nicht jede der
        # 42 Zeilen einer Tabelle anfasst; ihre Herkunft ist dieselbe.
        "budget_execution": ("council_budget_execution", "budget_year",
                             "t.is_total = 1", None),
        # Kredite und Zinsen: je Unterrichtung eine Vorlage mit eigener
        # Herkunft — die Papierliste eines Jahrgangs sind die Berichte des
        # Jahres. `document_url` ist die Rückfallebene der Zeile.
        "loans":            ("council_loan_notices", "year", None, "document_url"),
        # Der Liquiditätsstand: je Monat die Grafik, aus der der Wert zuletzt
        # bestätigt wurde — die Papierliste eines Jahrgangs sind die Grafiken.
        "liquidity":        ("council_liquidity", "year", None, "url"),
        # Die Jahresabschlüsse der Eigenbetriebe: je Jahrgang bis zu vier
        # Prüfberichte (ein Betrieb, ein Papier), jede Kennzahl zeigt auf den
        # jüngsten Bericht, der sie nennt.
        "enterprise_accounts": ("council_enterprise_accounts", "year", None, None),
        # Die Änderungslisten zum Haushalt. Wie `wirtschaftsplan` stehen je
        # Jahrgang MEHRERE Papiere dahinter (Verw. I–III und die
        # Beschluss-Datei des AFB) — die Summen-Tabelle trägt je Dokument
        # eine Herkunft, DISTINCT macht daraus die Papierliste des Jahrgangs.
        "aenderungsliste":      ("council_budget_amendments_totals",
                                 "budget_year", None, None),
    }

    #: Jahresquellen, die KEIN Dokument im Ratsinformationssystem haben und
    #: deshalb nicht in ``_DOKUMENT_QUELLEN`` stehen — Downloads von
    #: oldenburg.de, Open Data und die Landesstatistik. Für die Frage „welche
    #: Jahrgänge deckt diese Quelle ab?" zählen sie genauso.
    _WEITERE_JAHRESQUELLEN: dict[str, tuple[str, str, str | None]] = {
        "taxes":     ("council_taxes", "year", None),
        "tax_capacity": ("council_tax_capacity", "year", None),
        "population":   ("council_einwohner", "year", None),
        "schulden":    ("council_debt", "year", None),
        "gebaut":      ("council_investments_actual", "year", None),
        "expense_series": ("council_expense_series", "year", None),
        "buergschaften": ("council_buergschaften", "year", None),
        "anlagenspiegel": ("council_fixed_assets", "year", None),
        "vermoegensgruppen": ("council_vermoegensgruppen", "year", None),
        "integrierte_schulden": ("council_integrated_debt", "year", None),
        "donations":     ("council_donations", "year", None),
        "loans":         ("council_loan_notices", "year", None),
        "liquidity":     ("council_liquidity", "year", None),
        "enterprise_accounts": ("council_enterprise_accounts", "year", None),
        "tax_plan":  ("council_tax_plan", "year", None),
        "tax_rates":  ("council_tax_rates", "year", None),
    }

    #: Ein Haushaltsjahr trägt drei Sorten Vorlagen, und sie heißen nicht
    #: einheitlich. Die Jahreszahl steht immer vorn, das Wort davor variiert
    #: („Haushalt 2026", „Haushaltsentwurf 2024", „HH 2020").
    _HH_TITEL = re.compile(r"^(?:Haushaltsentwurf|Haushalt|HH)\s*(\d{4})")

    #: Woran ein Verwaltungsentwurf als Teilhaushalts-Bericht erkennbar ist —
    #: er geht in den jeweiligen Fachausschuss, nicht in den Finanzausschuss.
    _HH_TEILBERICHT = ("Teilhaushalt", "THH", "Budget", "Stiftung")

    #: Die Schlussabstimmung trägt in jedem Jahrgang denselben Titel; die
    #: Jahreszahl darin ist das HAUSHALTSJAHR, nicht das Sitzungsjahr (der
    #: Haushalt 2023 wurde im Dezember 2022 beschlossen, der Haushalt 2026
    #: erst im Februar 2026).
    _STREIT_SATZUNG = re.compile(r"^Haushaltssatzung und Haushaltsplan\s+(\d{4})")

    #: Der Sammelpunkt, unter dem die Debatte geführt wird. Er steht nicht in
    #: jedem Protokoll als eigene Beschlusszeile — wo er fehlt, wird der
    #: Oberpunkt aus der Nummer der Schlussabstimmung abgeleitet.
    _STREIT_SAMMEL = re.compile(r"^Haushalt\s+(\d{4})\s*$")

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

    # ----------------------------------------------------------------
    # Die SCHREIBSEITE. Sie ist beim ersten Schnitt (#1012) liegen
    # geblieben: Der Aufrufkegel ging von den Haushalts-ENDPUNKTEN aus,
    # und die Ingest-Skripte standen nicht in seinen Wurzeln. 55
    # `save_*`-Methoden blieben deshalb im Kern zurück, obwohl sie
    # nirgendwo sonst gebraucht werden.
    # ----------------------------------------------------------------

    def refresh_abweichung(self, ksinr: int | None = None, template_number: str | None = None) -> int:
        """Beschluss ↔ Beschlussvorschlag vergleichen (council.ernte.deviation)
        und das Ergebnis an den Beschlüssen ablegen. Zwei Auslöser, weil Vorlage
        und Protokoll in beliebiger Reihenfolge eintreffen: nach save_protocol
        (per ksinr) und nach save_vorlage (per template_number). Nur angenommene
        Beschlüsse — eine Vertagung oder Ablehnung ist keine Textänderung."""
        from council import ernte

        sql = ("SELECT id, template_number, official_text FROM council_decisions "
               "WHERE kind = 'decision' AND outcome = 'accepted' "
               "AND official_text IS NOT NULL AND template_number IS NOT NULL")
        args: tuple = ()
        if ksinr is not None:
            sql += " AND ksinr = ?"
            args = (ksinr,)
        elif template_number is not None:
            # Auch Beschlüsse, die eine REVISION dieser Nummer zitieren
            # („22/0348/1" bei gespeicherter Basis „22/0348") — der
            # get_vorlage_by_nr-Fallback löst sie ohnehin auf (Befund E2).
            base = "/".join(template_number.split("/")[:2])
            sql += " AND (template_number IN (?, ?) OR template_number LIKE ? || '/%')"
            args = (template_number, base, template_number)
        vorschlaege: dict[str, str | None] = {}
        updates = []
        for did, nr, official_text in self._conn.execute(sql, args).fetchall():
            if nr not in vorschlaege:
                v = self.get_vorlage_by_nr(nr)
                vorschlaege[nr] = (v or {}).get("proposed_decision")
            updates.append((ernte.deviation(vorschlaege[nr], official_text), did))
        if updates:
            with self._conn:
                self._conn.executemany(
                    "UPDATE council_decisions SET deviation = ? WHERE id = ?", updates)
        return len(updates)

    def save_haushalt(self, year: int, rows: list[dict], herkunft) -> int:
        """Ergebnishaushalt eines Jahres speichern — ersetzt den bisherigen
        Stand des Jahres komplett (Re-Ingest idempotent).

        ``herkunft`` ist eine :class:`council.herkunft.Herkunft` und hat den
        früheren ``source_url``-String abgelöst: Eine URL allein sagt nicht,
        an welcher Stelle eines 300-Seiten-PDFs gelesen wurde und was die
        Zahlen absichert. ``source_url`` steht weiter in der Tabelle und wird
        aus derselben Angabe gefüllt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_budget WHERE year = ?", (year,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_budget (year, area, revenues, expenses, "
                    " result, is_total, source_url, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (year, r["area"], r.get("revenues"), r.get("expenses"),
                     r.get("result"), int(r.get("is_total", 0)),
                     herkunft.url, now, hid))
        return len(rows)

    def save_steuereinnahmen(self, rows: list[dict], herkunft) -> int:
        """Ist-Steuereinnahmen (year, art, betrag) ersetzen — Re-Ingest idempotent."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_taxes "
                "(year, kind, amount, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?)",
                [(r["year"], r["kind"], r.get("amount"), herkunft.url, now, hid)
                 for r in rows])
        return len(rows)

    def save_steuerkraft(self, rows: list[dict], herkunft) -> int:
        """Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr ersetzen.

        Anders als die Nachbar-Methoden räumt diese auch auf: Der Datensatz
        1106 liefert die **ganze** Reihe bei jedem Lauf, und seit der
        Jahres-Korrektur (``haushalt._STEUERKRAFT_VERSATZ``) trägt jede Zeile
        ein anderes Jahr als beim letzten Mal. Ein reines INSERT OR REPLACE
        ließe genau einen Jahrgang als Leiche zurück — den ältesten, den es
        nach dem Rücken nicht mehr gibt. Der stünde dann mit den Beträgen
        seines Nachfolgers in der Tabelle, und niemand käme je darauf.

        Eine leere Lieferung räumt **nichts** ab: Ein misslungener Download
        darf den Bestand nicht löschen. Der Ingest bricht in dem Fall ohnehin
        vorher ab, aber die Methode soll das auch allein aushalten.
        """
        if not rows:
            return 0
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_tax_capacity "
                "(year, tax_index, tax_capacity_per_capita, allocations, allocations_per_capita, "
                " source_url, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?)",
                [(r["year"], r.get("tax_index"), r.get("tax_capacity_per_capita"),
                  r.get("allocations"), r.get("allocations_per_capita"),
                  herkunft.url, now, hid) for r in rows])
            years = [r["year"] for r in rows]
            self._conn.execute(
                "DELETE FROM council_tax_capacity WHERE year NOT IN "
                f"({','.join('?' * len(years))})", years)
        return len(rows)

    def save_einwohner(self, rows: list[dict], herkunft) -> int:
        """Einwohnerzahlen je Jahr ersetzen (idempotent)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_einwohner "
                "(year, population, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?)",
                [(r["year"], r["population"], herkunft.url, now, hid) for r in rows])
        return len(rows)

    def save_ergebnisrechnung(self, year: int, posten: list[dict], herkunft,
                              sub_budget_no: int | None = None, sub_budget_name: str | None = None,
                              ersetzen: bool = True) -> int:
        """Ergebnisrechnung einer Ebene speichern — ohne ``sub_budget_no`` die
        Gesamtrechnung, sonst der jeweilige Teilhaushalt.

        ``ersetzen`` löscht vorher die betroffene Ebene dieses Jahres; beim
        Einlesen mehrerer Teilhaushalte nacheinander bleibt es an.

        ``herkunft`` steht, wo früher ``label, url`` standen. Die beiden
        Ebenen dieses Dokuments bekommen bewusst **verschiedene** Herkünfte:
        Sie stehen an verschiedenen Stellen des Jahresabschlusses und sind
        durch verschiedene Proben gedeckt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            if ersetzen:
                if sub_budget_no is None:
                    self._conn.execute(
                        "DELETE FROM council_income_statement WHERE year = ? AND sub_budget_no IS NULL",
                        (year,))
                else:
                    self._conn.execute(
                        "DELETE FROM council_income_statement WHERE year = ? AND sub_budget_no = ?",
                        (year, sub_budget_no))
            self._conn.executemany(
                "INSERT INTO council_income_statement (year, sub_budget_no, sub_budget_name, nr, label, "
                " prior_year, budgeted, plan, plan_kind, result, deviation, is_total, "
                " source_label, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                # `plan` fällt auf `ansatz` zurück, wenn der Aufrufer keine
                # eigene Bezugsgröße mitbringt — und zwar auch bei
                # ausdrücklichem ``None``. `p.get("plan", …)` täte das nicht:
                # Der Vorgabewert greift nur bei fehlendem Schlüssel. Dieselbe
                # Falle stand im Lesepfad (s. `get_plan_ist.plan_von`).
                [(year, sub_budget_no, sub_budget_name, p["nr"], p["label"], p.get("prior_year"),
                  p.get("budgeted"),
                  p.get("budgeted") if p.get("plan") is None else p.get("plan"),
                  p.get("plan_kind"),
                  p.get("result"), p.get("deviation"),
                  p.get("is_total", 0), herkunft.label, herkunft.url, now, hid)
                 for p in posten])
        return len(posten)

    def save_abweichungsgruende(self, year: int, gruende: list[dict], herkunft) -> int:
        """Erläuterungen zu den Plan/Ist-Abweichungen eines Jahrgangs
        ersetzen. Übergeben wird nur, was die Rechenprobe bestanden hat."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_variance_reasons WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_variance_reasons (year, nr, label, "
                " delta_meur, percent, text, source_label, source_url, fetched_at, "
                " herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(year, g["nr"], g["label"], g.get("delta_meur"), g.get("percent"),
                  g["text"], herkunft.label, herkunft.url, now, hid) for g in gruende])
        return len(gruende)

    def save_pruefbericht_quelle(self, year: int, herkunft,
                                 n_pages: int | None, readable: bool) -> None:
        """Fundstelle des RPA-Schlussberichts eines Jahrgangs merken."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_audit_report_sources "
                "(year, label, url, n_pages, readable, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (year, herkunft.label, herkunft.url, n_pages,
                 1 if readable else 0, now, hid))

    def save_finanzrechnung(self, year: int, zeilen: list[dict], herkunft) -> int:
        """Die Kassensicht eines Jahrgangs ersetzen.

        Übergeben wird nur, was ``finanzberichte.finanzprobe`` durchgelassen
        hat — die Funktion streicht Ketten, die nicht aufgehen, schon vorher
        heraus. Hier wird deshalb nichts mehr geprüft, nur geschrieben."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_cash_flow_statement WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_cash_flow_statement (year, nr, role, label, "
                " prior_year, budgeted, plan, plan_kind, result, deviation, "
                " authorization, is_total, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, z["nr"], z.get("role"), z["label"], z.get("prior_year"),
                  z.get("budgeted"), z.get("plan"), z.get("plan_kind"), z.get("result"),
                  z.get("deviation"), z.get("authorization"),
                  z.get("is_total", 0), hid, now)
                 for z in zeilen])
        return len(zeilen)

    def save_bilanz(self, year: int, posten: list[dict], herkunft) -> int:
        """Einen Bilanzstichtag ersetzen.

        Übergeben wird nur, was ``bilanz.bilanzprobe`` durchgelassen hat —
        eine Bilanz, deren Seiten nicht aufgehen, kommt dort gar nicht erst
        heraus. Hier wird deshalb nichts mehr geprüft, nur geschrieben."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_balance_sheet WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_balance_sheet (year, role, page, level, nr, "
                " label, value, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(year, p["role"], p["page"], p["level"], p.get("nr"),
                  p["label"], p["value"], hid, now) for p in posten])
        return len(posten)

    def save_bilanz_erlaeuterungen(self, year: int, abschnitte: list[dict],
                                   herkunft) -> int:
        """Die Erläuterungen des Anhangs zu einem Jahrgang ersetzen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_balance_sheet_notes WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_balance_sheet_notes (year, role, nr, "
                " heading, text, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?)",
                [(year, a["role"], a["nr"], a["heading"], a["text"], hid, now)
                 for a in abschnitte])
        return len(abschnitte)

    def save_ergebnishaushalt(self, plan_budget_year: int, zeilen: list[dict],
                              herkunft) -> int:
        """Einen Haushaltsplan-Jahrgang ersetzen — Ansatz und Finanzplanung
        zusammen, weil sie aus **einer** Tabelle eines Dokuments stammen.

        Gelöscht wird nach ``plan_budget_year``, nicht nach ``year``: Was der
        Haushalt 2026 über 2027 sagt, gehört ihm; was der Haushalt 2027 über
        2027 sagt, ist eine andere Zeile und bleibt stehen.

        Übergeben wird nur, was beide Pflicht-Proben bestanden hat — diese
        Methode prüft nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_income_budget WHERE plan_budget_year = ?",
                (plan_budget_year,))
            self._conn.executemany(
                "INSERT INTO council_income_budget (plan_budget_year, year, kind, nr, "
                " label, amount, is_total, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(plan_budget_year, z["year"], z["kind"], z["nr"], z["label"],
                  z["amount"], 1 if z.get("is_total") else 0, now, hid)
                 for z in zeilen])
        return len(zeilen)

    def ergebnishaushalt_jahrgaenge(self) -> list[int]:
        """Haushaltsplan-Jahrgänge, die eingelesen sind (aufsteigend).

        Der **Plan**-Jahrgang, nicht die Jahre darin: Ein Dokument trägt sein
        Planjahr und drei Finanzplanungsjahre, und vollständig ist es erst,
        wenn alle vier dastehen — was ``save_ergebnishaushalt`` zusammen
        schreibt oder gar nicht."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT plan_budget_year FROM council_income_budget "
                "ORDER BY plan_budget_year")]
        except sqlite3.OperationalError:
            return []

    def save_stellenplan(self, budget_year: int, part: str, zeilen: list[dict],
                         herkunft, as_of_date: str | None = None) -> int:
        """Einen Teil eines Stellenplan-Jahrgangs ersetzen.

        Ersetzt wird nach ``(budget_year, part)``, nicht nach Jahrgang: Die
        beiden Teile stehen zwar im selben PDF, kommen aber einzeln durch
        ihre Proben — im Jahrgang 2026 ist Teil B im Textextrakt unlesbar,
        Teil A tadellos. Wer nach Jahrgang löschte, risse mit dem einen den
        anderen mit.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode
        prüft nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_staff_plan WHERE budget_year = ? AND part = ?",
                (budget_year, part))
            self._conn.executemany(
                "INSERT INTO council_staff_plan (budget_year, part, row_no, kind, "
                " pay_group, seq_no, label, pay_grade, positions_planned, "
                " positions_prior_year, filled, filled_by_officials, filled_by_employees, "
                " vacant, as_of_date, consistent, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(budget_year, part, i, z["kind"], z.get("pay_group"), z.get("seq_no"),
                  z["label"], z.get("pay_grade"), z["positions_planned"],
                  z["positions_prior_year"], z["filled"], z.get("filled_by_officials"),
                  z.get("filled_by_employees"), z["vacant"], as_of_date,
                  1 if z.get("consistent", 1) else 0, now, hid)
                 for i, z in enumerate(zeilen)])
        return len(zeilen)

    def save_investitionen(self, year: int, zeilen: list[dict], gesamt: dict,
                           herkunft, finanzhaushalt: dict | None = None,
                           herkunft_finanzhaushalt=None) -> int:
        """Einen Jahrgang Investitionen ersetzen — Teilhaushalte und
        Summenzeile zusammen, weil sie aus **einer** Tabelle stammen und die
        Summenzeile das Ziel der Rechenprobe ist.

        Zwei Herkünfte, weil es zwei verschiedene Aussagen sind: Die
        Investitionen sind durch die Summenprobe der Datei gedeckt, der
        *Gesamtbetrag des Finanzhaushaltes* ist es nicht (er zählt die laufende
        Verwaltungstätigkeit mit, und nichts in der Datei summiert sich auf
        ihn). Eine gemeinsame Herkunft behauptete für ihn eine Probe, die es
        nicht gibt.

        Übergeben wird nur, was die Probe bestanden hat — diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_investments WHERE year = ?", (year,))
            werte = [(year, "sub_budget", z["sub_budget_no"], z["label"],
                      z["inflows"], z["outflows"], now, hid)
                     for z in zeilen]
            werte.append((year, "investments", 0, gesamt["label"],
                          gesamt["inflows"], gesamt["outflows"], now, hid))
            if finanzhaushalt:
                hid_fh = (self.merke_herkunft(herkunft_finanzhaushalt, fetched_at=now)
                          if herkunft_finanzhaushalt is not None else hid)
                werte.append((year, "financial_budget", 0,
                              finanzhaushalt["label"],
                              finanzhaushalt["inflows"],
                              finanzhaushalt["outflows"], now, hid_fh))
            self._conn.executemany(
                "INSERT INTO council_investments (year, level, sub_budget_no, label, "
                " inflows, outflows, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?)", werte)
        return len(werte)

    def save_investitionsprogramm(self, year: int, gelesen: dict,
                                  herkunft) -> int:
        """Einen Jahrgang Investitionsmaßnahmen ersetzen.

        Maßnahmen und beide Summenebenen zusammen, weil sie aus **einem**
        Dokument stammen und die Summen die Ziele der Rechenproben sind. Eine
        Herkunft für alles: Anders als beim Finanzhaushalt gibt es hier keine
        Zeile, die von den Proben nicht gedeckt wäre — was nicht aufgeht, kommt
        gar nicht erst herein (``investitionsprogramm.lies``).

        Übergeben wird nur, was die Proben bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_investment_measures WHERE year = ?",
                (year,))
            werte = []
            for nr, a in sorted(gelesen["abschnitte"].items()):
                for m in a["massnahmen"]:
                    werte.append((year, "measure", nr, m["code"],
                                  m["label"], m["grand_total"],
                                  " · ".join(m.get("details") or []) or None,
                                  now, hid))
                werte.append((year, "sub_budget", nr, "", a["name"],
                              a["summe"], None, now, hid))
            werte.append((year, "total", 0, "", "Gesamtinvestitionsprogramm",
                          gelesen["kopfsumme"], None, now, hid))
            self._conn.executemany(
                "INSERT INTO council_investment_measures "
                "(year, level, sub_budget_no, code, label, grand_total, "
                " details, fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?)",
                werte)
        return len(werte)

    def save_konzern_jahrgang(self, year: int, posten: list[dict],
                              entity: list[dict], herkunft,
                              herkunft_traeger=None) -> dict:
        """Einen Jahrgang des Gesamtabschlusses ersetzen — beide Ebenen.

        Zusammen, weil sie aus **einem** Dokument stammen und ein halb
        geschriebener Jahrgang für den nächsten Lauf wie ein fertiger aussähe.
        Aber mit **zwei** Herkünften: Die Posten stehen in Abschnitt 3.2, die
        Trägeraufstellung in 4.1.1, und sie sind durch verschiedene Proben
        gedeckt. Fehlt ``herkunft_traeger``, gilt dieselbe für beide.

        Übergeben wird nur, was die Proben bestanden hat — diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            hid_traeger = (self.merke_herkunft(herkunft_traeger, fetched_at=now)
                           if herkunft_traeger is not None else hid)
            self._conn.execute("DELETE FROM council_group_items WHERE year = ?", (year,))
            self._conn.execute("DELETE FROM council_group_entities WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_group_items (year, nr, label, role, "
                " amount, prior_year, is_total, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(year, p["nr"], p["label"], p.get("role"), p["amount"],
                  p.get("prior_year"), 1 if p.get("is_total") else 0, now, hid)
                 for p in posten])
            self._conn.executemany(
                "INSERT INTO council_group_entities (year, kind, entity_key, entity, "
                " amount_keur, prior_year_keur, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(year, t["kind"], t["entity_key"], t["entity"], t["amount_keur"],
                  t.get("prior_year_keur"), now, hid_traeger) for t in entity])
        return {"posten": len(posten), "entity": len(entity)}

    def save_beteiligungsbericht(self, stammdaten: list[dict], texte: list[dict],
                                 indicators: list[dict],
                                 personen: list[dict] | None = None,
                                 eigentuemer: list[dict] | None = None) -> dict:
        """Den **ganzen** Bestand des Beteiligungsberichts ersetzen.

        Ungewöhnlich für diesen Store, und mit Grund: Die Überlappungsprobe
        spannt sich über mehrere Berichte. Ob der Wert für 2022 gilt,
        entscheidet nicht der Bericht 2022 allein, sondern sein Vergleich mit
        2023 und 2024 — und `n_reports` (in wie vielen er steht) ändert sich,
        sobald ein neuer Jahrgang dazukommt. Jahrgangsweise zu schreiben
        hieße, diese Zahl in jeder zweiten Zeile veralten zu lassen.

        Das Einlesen liest deshalb immer alle vorhandenen Berichte und
        übergibt das Ergebnis in einem Stück. Übergeben wird nur, was die
        Proben bestanden hat — diese Methode prüft nichts nach, sie schreibt.

        Jede Liste bringt ihre eigene ``herkunft`` je Zeile mit: Die Kennzahlen
        eines Jahres stammen aus einem anderen Bericht als die Texte daneben,
        und die Probe ist eine andere."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            for tabelle in ("council_company_indicators",
                            "council_company_texts",
                            "council_company_people",
                            "council_company_owners",
                            "council_companies"):
                self._conn.execute(f"DELETE FROM {tabelle}")
            for z in stammdaten:
                self._conn.execute(
                    "INSERT INTO council_companies (report_year, company, "
                    " name, classification, page, consolidated_key, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["name"], z["classification"],
                     z.get("page"), z.get("consolidated_key"), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in texte:
                self._conn.execute(
                    "INSERT INTO council_company_texts (report_year, "
                    " company, section, text, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["section"], z["text"],
                     now, self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in indicators:
                self._conn.execute(
                    "INSERT INTO council_company_indicators (company, "
                    " indicator, year, value, unit, report_year, n_reports, "
                    " fetched_at, herkunft_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (z["company"], z["indicator"], z["year"], z["value"],
                     z["unit"], z["report_year"], z["n_reports"], now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in personen or []:
                self._conn.execute(
                    "INSERT INTO council_company_people (report_year, "
                    " company, sort_order, committee, name, position, "
                    " chair_role, note, roles_assignable, fetched_at, "
                    " herkunft_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["sort_order"],
                     z["committee"], z["name"], z.get("position"), z.get("chair_role"),
                     z.get("note"), int(bool(z["roles_assignable"])), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
            for z in eigentuemer or []:
                self._conn.execute(
                    "INSERT INTO council_company_owners (report_year, "
                    " company, sort_order, name, amount_eur, "
                    " share_pct, fetched_at, herkunft_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (z["report_year"], z["company"], z["sort_order"],
                     z["name"], z.get("amount_eur"), z.get("share_pct"), now,
                     self.merke_herkunft(z["herkunft"], fetched_at=now)))
        return {"gesellschaften": len(stammdaten), "texte": len(texte),
                "indicators": len(indicators), "personen": len(personen or []),
                "eigentuemer": len(eigentuemer or [])}

    def save_schulden(self, zeilen: list[dict], herkunft) -> int:
        """Schuldenjahrgänge ersetzen — je Jahr eine Zeile.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen. Wer wirklich aufräumen will, tut das von Hand.

        Übergeben wird nur, was seine Probe bestanden hat — diese Methode
        prüft nichts nach, sie schreibt. Was die Aufteilung verloren hat
        (Fall 2022, s. ``council/schulden.py``), kommt hier mit ``None`` in
        den vier Artenspalten an und bleibt auch so stehen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_debt "
                "(year, credit_market, special_funds, public_authorities, "
                " municipal_enterprises, total, per_capita, breakdown_rejected, "
                " revised, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(z["year"], z.get("credit_market"), z.get("special_funds"),
                  z.get("public_authorities"), z.get("municipal_enterprises"),
                  z["total"], z.get("per_capita"),
                  z.get("breakdown_rejected"), int(bool(z.get("revised"))),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def save_gebuehrenbedarf(self, bedarf, herkunft) -> int:
        """Einen Gebührenbereich eines Jahrgangs speichern.

        Je Bereich und Jahr eine Zeile, und je Zeile eine eigene Herkunft: Die
        drei Bereiche stehen in drei Anlagen und prüfen sich einzeln — ein
        gemeinsamer Beleg wäre für zwei von drei der falsche.
        """
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_fees "
                "(year, area, area_name, cost_calculation, deductions, "
                " costs_to_cover, reference_quantity, reference_unit, fee, "
                " fee_proposed, template_number, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bedarf.year, bedarf.area, bedarf.area_name,
                 bedarf.cost_calculation, bedarf.deductions,
                 bedarf.costs_to_cover, bedarf.reference_quantity,
                 bedarf.reference_unit, bedarf.fee,
                 bedarf.fee_proposed, bedarf.template_number,
                 probes, hid, now))
        return 1

    def save_gebuehrensaetze(self, saetze, herkuenfte) -> int:
        """Die vollständigen zwölf Tarife eines Vorschlagsjahres ersetzen."""
        saetze, herkuenfte = list(saetze), list(herkuenfte)
        if len(saetze) != len(herkuenfte):
            raise ValueError("Jeder Gebührensatz braucht genau eine Herkunft")
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            for satz, herkunft in zip(saetze, herkuenfte, strict=True):
                probes = herkunft.probe
                if not isinstance(probes, str):
                    probes = ",".join(probes)
                hid = self.merke_herkunft(herkunft, fetched_at=now)
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_fee_rates "
                    "(year, key, area, label, amount, unit, "
                    " prior_year, change_pct, template_number, probes, "
                    " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (satz.year, satz.key, satz.area, satz.label,
                     satz.amount, satz.unit, satz.prior_year,
                     satz.change_pct, satz.template_number, probes, hid, now))
        return len(saetze)

    def save_haushaltssatzung(self, satzung, herkunft) -> int:
        """Eine Haushaltssatzung speichern — ein Jahrgang, eine Fassung.

        Wie bei den Wirtschaftsplänen kommen die Proben aus der HERKUNFT und
        werden hier nicht noch einmal behauptet: Ob der Hebesatz gegen das
        Statistische Jahrbuch geprüft werden konnte, hängt daran, ob dessen
        Tabelle diesen Jahrgang schon trägt — der Parser weiß das, der Store
        nicht.
        """
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_budget_bylaw "
                "(year, supplement, version, ordinary_revenues, "
                " ordinary_expenses, extraordinary_revenues, extraordinary_expenses, "
                " in_operating, out_operating, in_capital, out_capital, "
                " in_financing, out_financing, in_total, out_total, "
                " investment_loans, commitment_authorizations, "
                " liquidity_loans, property_tax_a_rate, "
                " property_tax_b_rate, trade_tax_rate, session_date, "
                " template_number, probes, herkunft_id, fetched_at) "
                "VALUES (" + ",".join("?" * 26) + ")",
                (satzung.year, satzung.supplement, satzung.version,
                 satzung.ordinary_revenues, satzung.ordinary_expenses,
                 satzung.extraordinary_revenues, satzung.extraordinary_expenses,
                 satzung.in_operating, satzung.out_operating,
                 satzung.in_capital, satzung.out_capital,
                 satzung.in_financing, satzung.out_financing,
                 satzung.in_total, satzung.out_total,
                 satzung.investment_loans,
                 satzung.commitment_authorizations,
                 satzung.liquidity_loans,
                 satzung.property_tax_a_rate, satzung.property_tax_b_rate,
                 satzung.trade_tax_rate, satzung.session_date,
                 satzung.template_number, probes, hid, now))
        return 1

    def save_haushaltsvollzug(self, bericht, herkunft) -> int:
        """Eine Übersichtstabelle eines Finanz- und Leistungsberichts ersetzen.

        Ersetzt wird nach ``(budget_year, as_of, budget)`` — der Einheit, die
        EIN Lauf liefert. Nicht nach Jahrgang und nicht nach Stichtag: Ein
        Dokument trägt beide Haushalte, und sie kommen einzeln durch ihre
        Proben. Im Bericht zum 30.06.2024 fällt der Ergebnishaushalt an einem
        Fehler im Dokument durch, der Finanzhaushalt nicht — wer nach Stichtag
        löschte, risse den mit.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode
        prüft nichts nach, sie schreibt.
        """
        probes = herkunft.probe
        if not isinstance(probes, str):
            probes = ",".join(probes)

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "DELETE FROM council_budget_execution "
                "WHERE budget_year = ? AND as_of = ? AND budget = ?",
                (bericht.budget_year, bericht.as_of, bericht.budget))
            self._conn.executemany(
                "INSERT INTO council_budget_execution ("
                " budget_year, as_of, budget, sub_budget, kind, label, "
                " budgeted, forecast, deviation, carryover, plan_basis, "
                " is_total, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(bericht.budget_year, bericht.as_of, bericht.budget,
                  p.sub_budget, p.kind, p.label, p.budgeted, p.forecast,
                  p.deviation, p.carryover, bericht.plan_basis,
                  1 if p.is_total else 0, probes, hid, now)
                 for p in bericht.positionen])
        return len(bericht.positionen)

    def haushaltsvollzug_einheiten(self) -> set[tuple]:
        """Welche ``(Jahrgang, Stichtag, Haushalt)`` im Bestand stehen.

        Die Einheit ist die Tabelle und nicht der Jahrgang: Ein Haushaltsjahr
        besteht aus bis zu vier Stichtagen mit je zwei Haushalten. Wer je
        Jahrgang buchführt, hält 2025 nach dem Bericht zum 31. März für
        erledigt und zieht die drei folgenden Quartale nie nach."""
        try:
            return {(r[0], r[1], r[2]) for r in self._conn.execute(
                "SELECT DISTINCT budget_year, as_of, budget "
                "FROM council_budget_execution")}
        except sqlite3.OperationalError:
            return set()

    def save_buergschaften(self, zeilen: list[dict], herkunft) -> int:
        """Bürgschafts-Jahrgänge ersetzen — je Jahr eine Zeile.

        Wie bei ``save_ausgabenreihe`` wird nur ersetzt, was die Lieferung
        mitbringt: Ein Lauf, dem ein Jahrgang durchgefallen ist, räumt den
        vorher gespeicherten Stand dieses Jahrgangs nicht mit weg.

        Aufgerufen wird sie **je Herkunfts-Gruppe**, nicht einmal für die
        ganze Reihe — jeder Jahrgang steht in seinem eigenen Jahresabschluss,
        und 2021 steht sogar in dem des Folgejahres. Ein gemeinsamer Beleg
        wäre für fünf von sechs Zeilen der falsche."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_buergschaften "
                "(year, balance, exact, out_next_year, source, reason, "
                " single_amount, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["year"], z["balance"], int(bool(z.get("exact"))),
                  int(bool(z.get("out_next_year"))), z["source"], z.get("reason"),
                  z.get("single_amount"), ",".join(z.get("probes") or []),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def save_kennzahlen(self, report_year: int, zeilen: list[dict],
                        formeln: list[dict], herkunft) -> int:
        """Einen Rechenschaftsbericht ersetzen — Werte und Rechenwege zusammen.

        Ersetzt wird genau **dieser Bericht**, nicht die Jahrgänge, die er
        zeigt. Der Bericht 2024 druckt 2020–2024; wer nach Datenjahr löschte,
        risse dem Bericht 2021 vier seiner fünf Spalten heraus — und mit ihnen
        die Vergleichsstände, aus denen die Korrekturen sichtbar werden.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_indicators WHERE report_year = ?",
                               (report_year,))
            self._conn.execute("DELETE FROM council_indicator_formulas WHERE report_year = ?",
                               (report_year,))
            self._conn.executemany(
                "INSERT INTO council_indicators "
                "(report_year, indicator, year, label, value, unit, decimals, "
                " version, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(report_year, z["indicator"], z["year"], z["label"], z["value"],
                  z["unit"], z["decimals"], z.get("version"), hid, now)
                 for z in zeilen])
            self._conn.executemany(
                "INSERT INTO council_indicator_formulas "
                "(report_year, indicator, version, heading, formula, "
                " herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?)",
                [(report_year, f["indicator"], f.get("version") or 1,
                  f["heading"], f["formula"], hid, now) for f in formeln])
        return len(zeilen)

    def get_kennzahlen(self) -> list[dict]:
        """Alle Stände aller Berichte — die Belegkette, nicht die Anzeigereihe.

        Wer die Reihe will, nimmt ``council.indicators.neueste``; wer die
        Korrekturen zeigen will, braucht alle Stände.
        """
        try:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_indicators ORDER BY indicator, year, report_year")]
        except sqlite3.OperationalError:
            return []

    def save_anlagenspiegel(self, year: int, zeilen: list[dict], herkunft) -> int:
        """Den Anlagenspiegel eines Jahrgangs ersetzen.

        Je Jahrgang ein Aufruf mit einem Beleg: Die Tabelle steht in genau
        einem Dokument, anders als bei den Bürgschaften, wo ein Jahrgang im
        Abschluss des Folgejahres stehen kann.

        Ersetzt wird nur DIESER Jahrgang — ein Lauf, dem ein anderer
        durchgefallen ist, räumt dessen Stand nicht mit weg.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_fixed_assets WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_fixed_assets "
                "(year, nr, label, n_columns, cost_opening, additions, disposals, "
                " transfers, cost_closing, depreciation_opening, depreciation, depreciation_releases, "
                " write_ups, depreciation_transfers, depreciation_closing, book_value, "
                " book_value_prior_year, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, z["nr"], z["label"], z["n_columns"],
                  z["cost_opening"], z["additions"], z["disposals"], z["transfers"],
                  z["cost_closing"], z["depreciation_opening"], z["depreciation"],
                  z["depreciation_releases"], z["write_ups"], z["depreciation_transfers"],
                  z["depreciation_closing"], z["book_value"], z["book_value_prior_year"],
                  ",".join(z.get("probes") or []), hid, now) for z in zeilen])
        return len(zeilen)

    def save_vermoegensgruppen(self, year: int, gruppen: list[dict], herkunft) -> int:
        """Die Untergliederung des Infrastrukturvermögens eines Jahrgangs."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_vermoegensgruppen WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_vermoegensgruppen "
                "(year, group_name, book_value, book_value_prior_year, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(year, g["group_name"], g["book_value"], g.get("book_value_prior_year"), hid, now)
                 for g in gruppen])
        return len(gruppen)

    def save_integrierte_schulden(self, row: dict, herkunft) -> int:
        """Einen Stichtag der integrierten Schulden ersetzen."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_integrated_debt "
                "(year, ars, population, total, per_capita, core_budget, "
                " extra_budgets, other, extra_under_50, other_below_50, "
                " change, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["year"], row["ars"], row.get("population"),
                 row["total"], row.get("per_capita"),
                 row.get("core_budget"), row.get("extra_budgets"),
                 row.get("other"), row.get("extra_under_50"),
                 row.get("other_below_50"), row.get("insgesamt_change"),
                 ",".join(row.get("probes") or []), hid, now))
        return 1

    def nachbewilligungs_vorlagen(self) -> tuple[list[dict], dict[str, list[dict]]]:
        """Die Rohdaten für ``council/supplementary_approvals.aus_vorlagen``.

        → ``(vorlagen, beschluesse)`` — **erst die Vorlagen, dann die nach
        Vorlagen-Nummer gruppierten Beschlusszeilen**, genau in der
        Reihenfolge, die der Parser erwartet.

        Der Filter läuft über den **Titel**, nicht über eine Vorlagenart:
        ``art`` heißt hier „Beschlussvorlage" oder „Berichtsvorlage" und sagt
        nichts über den Inhalt. Vorgefiltert wird nur grob (SQL kennt unser
        Muster nicht); die Feinentscheidung trifft
        ``supplementary_approvals.ist_nachbewilligung``.

        **Der Join läuft über ``template_number``, nicht über ``kvonr``.** Das ist
        keine Stilfrage: ``council_decisions.kvonr`` ist im gesamten Bestand
        ``NULL`` (8.369 von 8.369 Zeilen). Ein Join darüber liefert
        schweigend null Treffer — und eine Seite, die behauptet, der Rat habe
        nie über eine Nachbewilligung entschieden."""
        try:
            vorlagen = [dict(r) for r in self._conn.execute(
                "SELECT template_number, title, proposed_decision, raw_text "
                "FROM council_templates "
                "WHERE template_number IS NOT NULL "
                "  AND (title LIKE '%planmäßig%' OR title LIKE '%planmässig%')"
            )]
            rows = [dict(r) for r in self._conn.execute(
                "SELECT d.id, d.template_number, d.outcome, d.vote, "
                "       cs.committee, cs.session_date "
                "FROM council_decisions d "
                "JOIN council_sessions cs ON cs.ksinr = d.ksinr "
                "WHERE d.template_number IS NOT NULL AND d.kind = 'decision' "
                + self._BESCHLUSS_ORDNUNG
            )]
        except sqlite3.OperationalError:
            return [], {}
        beschluesse: dict[str, list[dict]] = {}
        for r in rows:
            beschluesse.setdefault(str(r["template_number"]), []).append(r)
        return vorlagen, beschluesse

    def save_nachbewilligungen(self, zeilen: list[dict], herkunft) -> int:
        """Die RIS-Serie ersetzen — je Vorlage eine Zeile.

        Wie bei ``save_schulden`` wird nur ersetzt, was die Lieferung
        mitbringt. Übergeben wird, was der Parser gelesen hat; diese Methode
        prüft nichts nach."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_supplementary_approvals "
                "(template_number, year, title, kind, category, amount, "
                " amount_source, decided, in_plenary, council_decision, "
                " decision_id, committees, "
                " fulltext_probe, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(z["template_number"], z.get("year"), z["title"], z["kind"],
                  z["category"], z.get("amount"), z.get("amount_source"),
                  int(bool(z.get("decided"))), int(bool(z.get("in_plenary"))),
                  int(bool(z.get("council_decision"))),
                  z.get("decision_id"),
                  json.dumps(z.get("committees") or [], ensure_ascii=False),
                  int(bool(z.get("fulltext_probe"))), hid, now)
                 for z in zeilen])
        return len(zeilen)

    def save_nachbewilligung_jahr(self, year: dict, channels: list[dict],
                                  herkunft) -> int:
        """Ein Jahrgang aus Kapitel 3 des Rechenschaftsberichts.

        Jahreszeile und Kanäle wandern zusammen in **eine** Transaktion: Ein
        Bestand, in dem die Summenzeile eines Jahres steht und seine vier
        Wege fehlen, wäre genau der Zustand, den die Tabellenprobe unmöglich
        machen soll."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_supplementary_years "
                "(year, total_operating, total_capital, total_per_text, "
                " commitments_amount, probe_ok, probe_text, herkunft_id, "
                " fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (year["year"], year["total_operating"], year["total_capital"],
                 year.get("total_per_text"), year.get("commitments_amount"),
                 int(bool(year.get("probe_ok"))), year.get("probe_text"),
                 hid, now))
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_supplementary_channels "
                "(year, channel, label, count_operating, amount_operating, "
                " count_capital, amount_capital, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(year["year"], k["channel"], k["label"], k["count_operating"],
                  k["amount_operating"], k["count_capital"],
                  k["amount_capital"], hid, now) for k in channels])
        return len(channels)

    def save_spenden(self, zeilen: list[dict], verworfen: list[dict],
                     herkunft) -> int:
        """Die geprüfte Spendenreihe schreiben — je Vorlage eine Zeile.

        Anders als bei den übrigen Schichten bringt **jede Zeile ihre eigene
        Herkunft mit** (``row["herkunft"]``): Jede Vorlage ist ein eigenes
        PDF mit eigener Dokument-ID. ``herkunft`` ist die Rückfallebene für
        die verworfenen Zeilen und für Zeilen ohne eigenen Anker — sie
        beschreibt den Lauf, nicht ein Dokument.

        ``INSERT OR REPLACE``, kein ``DELETE FROM``: Eine Teillieferung
        (etwa nach einem abgebrochenen Volltext-Lauf) ersetzt nur, was sie
        mitbringt, und räumt den Bestand nicht ab."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_donations "
                "(template_number, year, session_date, amount, committee, layout, second_mention, "
                " probes, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(z["template_number"], z["year"], z["session_date"], z["amount"], z.get("committee"),
                  z.get("layout"), z["second_mention"], ",".join(z["probes"]),
                  self.merke_herkunft(z["herkunft"], fetched_at=now)
                  if z.get("herkunft") else rueck, now)
                 for z in zeilen])
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_donations_rejected "
                "(template_number, session_date, reason, herkunft_id, fetched_at) VALUES (?,?,?,?,?)",
                [(v["template_number"], v.get("session_date"), v["reason"], rueck, now)
                 for v in verworfen])
        return len(zeilen)

    def liquiditaetsanlagen(self) -> list[dict]:
        """Die Anlagen der Liquiditätsstand-Vorlagen — mit oder ohne Text.

        Über ``kvonr``, nicht über ein Label-Muster: Bis 2021 heißt die
        Anlage schlicht „Anlage", erst danach trägt sie den Titel der
        Grafik."""
        try:
            return [dict(r) for r in self._conn.execute(
                """SELECT t.template_number, a.document_id, a.label, a.url, a.raw_text,
                          a.status, a.n_pages
                     FROM council_templates t JOIN council_attachments a ON a.kvonr = t.kvonr
                    WHERE t.title LIKE 'Liquiditätsstand%'
                    ORDER BY t.template_number, a.document_id""")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def save_liquidity(self, rows: list[dict], herkunft) -> int:
        """Die Monatsreihe schreiben — je Zeile ihre Herkunft (``row["herkunft"]``),
        sonst die des Laufs. ``INSERT OR REPLACE`` je Monat."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            rueck = self.merke_herkunft(herkunft, fetched_at=now)
            for r in rows:
                hid = self.merke_herkunft(r["herkunft"], fetched_at=now) if r.get("herkunft") else rueck
                self._conn.execute(
                    "INSERT OR REPLACE INTO council_liquidity (month, year, amount, as_of, confirmations, "
                    " revised_from, document_id, url, template_number, probes, herkunft_id, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["month"], r["year"], r["amount"], r["as_of"], r.get("confirmations", 1),
                     r.get("revised_from"), r.get("document_id"), r.get("url"), r.get("template_number"),
                     ",".join(r.get("probes") or []), hid, now))
        return len(rows)

    def liquidity_einheiten(self) -> set[tuple]:
        """``(Jahr, Monat)`` je Zeile — die Einheiten des Datenstands."""
        try:
            return {(r[0], r[1]) for r in self._conn.execute(
                "SELECT year, CAST(substr(month, 6, 2) AS INTEGER) FROM council_liquidity")}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return set()

    def enterprise_account_einheiten(self) -> set[tuple]:
        """``(Jahr, Betrieb)`` je Zeile — die Einheiten des Datenstands."""
        try:
            return {(r[0], r[1]) for r in self._conn.execute(
                "SELECT DISTINCT year, enterprise FROM council_enterprise_accounts")}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return set()

    def kreditunterrichtungen(self) -> list[dict]:
        """Die Rohzeilen für ``council.loans.lies()``: Vorlagen samt Volltext.

        Breit gefasst — das Aussieben macht ``loans.erkenne()``."""
        from council.loans import TITEL_SQL
        try:
            return [dict(r) for r in self._conn.execute(
                f"""SELECT kvonr, template_number, title, raw_text, document_id, document_url
                     FROM council_templates
                    WHERE {TITEL_SQL}
                    ORDER BY template_number""")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []

    def zuwendungsbeschluesse(self) -> list[dict]:
        """Die Rohzeilen für ``council.donations.lies()``.

        Absichtlich breit gefasst (``Annahme%Zuwendung%``): Das Aussieben
        macht ``donations.erkenne()``, damit die Regel an einer Stelle steht und
        nicht halb in SQL."""
        return [dict(r) for r in self._conn.execute(
            """SELECT d.template_number, d.title AS title, d.official_text, d.outcome,
                      s.session_date AS session_date, s.committee AS gremiensitzung,
                      v.raw_text, v.document_id AS document_id,
                      v.document_url AS dokument_url
                 FROM council_decisions d
                 LEFT JOIN council_sessions s ON s.ksinr = d.ksinr
                 LEFT JOIN council_templates v ON v.template_number = d.template_number
                WHERE d.kind = 'decision' AND d.title LIKE 'Annahme%Zuwendung%'
                ORDER BY s.session_date, d.template_number""")]

    def save_steuerplan(self, zeilen: list[dict], herkunft) -> int:
        """Plan neben Ist je Steuerart — ersetzt, was die Lieferung mitbringt.

        Nicht die ganze Tabelle: Jede Ausgabe von 1103 führt nur **drei**
        Jahrgänge, und der Lauf legt mehrere Ausgaben nacheinander ab. Ein
        ``DELETE`` vor dem Schreiben löschte deshalb genau das, wofür das
        Archiv gebaut wurde — die Jahrgänge, die nur noch in einer älteren
        Ausgabe stehen.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode prüft
        nichts nach."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_tax_plan "
                "(year, kind, plan, actual, provisional, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [(z["year"], z["kind"], z["plan"], z["actual"],
                  int(bool(z.get("provisional"))), hid, now) for z in zeilen])
        return len(zeilen)

    def steuerplan_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — für den Bestandsschutz."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_tax_plan ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def save_hebesaetze(self, zeilen: list[dict], herkunft) -> int:
        """Die Hebesatz-Treppe — je Änderungsjahr und Steuerart eine Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_tax_rates "
                "(year, kind, rate, prior_rate, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(z["year"], z["kind"], z["rate"], z.get("prior_rate"),
                  hid, now) for z in zeilen])
        return len(zeilen)

    def hebesatz_jahre(self) -> list[int]:
        """Welche Änderungsjahre im Bestand stehen — für den Bestandsschutz."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT year FROM council_tax_rates ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def save_investitionen_ist(self, zeilen: list[dict], herkunft,
                               verworfen: list[dict] | None = None) -> int:
        """Investitions-Jahrgänge ersetzen — je Jahr eine Zeile plus ihre Arten.

        Ersetzt wird **nur, was die Lieferung mitbringt**, nicht die ganze
        Tabelle: Ein Lauf, dem ein Jahrgang an der Probe durchgefallen ist,
        darf den vorher gespeicherten Stand dieses Jahrgangs nicht mit
        wegräumen (derselbe Grund wie bei ``save_schulden``).

        Die Arten eines Jahrgangs werden vorher gelöscht statt nur überschrieben:
        Wechselte die Quelle ihren Spaltenschnitt, bliebe eine abgeschaffte Art
        sonst als Karteileiche stehen und die Aufteilung summierte sich auf
        mehr als die Summe daneben.

        ``verworfen`` sind die Jahrgänge, die die Probe **nicht** bestanden
        haben (``lies()["verworfen"]``): Grund und gemessene ``difference``
        werden mitgeschrieben, damit die Seite ihre Lücke beziffern kann
        statt sie nur zu behaupten. Ein Jahrgang, der jetzt durchkommt,
        verliert dabei seinen alten Lücken-Eintrag — sonst stünde er in
        beiden Tabellen und die Seite zeigte eine Lücke, die es nicht mehr
        gibt.

        Übergeben wird an ``zeilen`` nur, was seine Probe bestanden hat —
        diese Methode prüft nichts nach, sie schreibt."""
        from council import investitionen_ist as _ii

        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investments_actual "
                "(year, accounting_system, total, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?)",
                [(z["year"], z["accounting_system"], z["total"], hid, now)
                 for z in zeilen])
            self._conn.executemany(
                "DELETE FROM council_investments_actual_kinds WHERE year = ?",
                [(z["year"],) for z in zeilen])
            arten = []
            for z in zeilen:
                spalten = _ii.SPALTEN[z["accounting_system"]]
                for i, (field, title) in enumerate(spalten[:-1]):
                    if z.get(field) is None:
                        continue
                    arten.append((z["year"], field, title, i, z[field], hid, now))
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investments_actual_kinds "
                "(year, field, title, sort_order, amount, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?)", arten)
            # Ein übernommener Jahrgang ist keine Lücke mehr.
            self._conn.executemany(
                "DELETE FROM council_investments_actual_rejected WHERE year = ?",
                [(z["year"],) for z in zeilen])
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_investments_actual_rejected "
                "(year, accounting_system, reason, difference, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?)",
                [(v["year"], v["accounting_system"], v["reason"], v.get("difference"),
                  hid, now) for v in (verworfen or [])])
        return len(zeilen)

    def investitionen_ist_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen — der Bestandsschutz vergleicht
        gegen diese Zahl, bevor ein Lauf sie überschreibt."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_investments_actual ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def schulden_jahre(self) -> list[int]:
        """Welche Jahrgänge im Bestand stehen."""
        try:
            return [r[0] for r in self._conn.execute(
                "SELECT year FROM council_debt ORDER BY year")]
        except sqlite3.OperationalError:
            return []

    def einwohner_je_jahr(self) -> dict[int, int]:
        """Alle bekannten Einwohnerzahlen als ``{year: zahl}``.

        Der Divisor der Pro-Kopf-Gegenprobe (``council/schulden.py``). Bewusst
        die ganze Reihe und nicht nur der jüngste Wert wie bei
        ``einwohner_aktuell``: Geprüft wird jeder Jahrgang gegen die
        Einwohnerzahl **seines** Jahres, nicht gegen die von heute."""
        try:
            return {r[0]: r[1] for r in self._conn.execute(
                "SELECT year, population FROM council_einwohner")}
        except sqlite3.OperationalError:
            return {}

    def save_staedtevergleich(self, series: str, zeilen: list[dict], herkunft) -> int:
        """Eine Reihe des Städtevergleichs ersetzen — ``tax_capacity`` oder
        ``realsteuern``.

        Ersetzt wird **je Reihe und je betroffenem Jahr**, nicht die ganze
        Tabelle: Die beiden Reihen kommen aus verschiedenen Dateien, die zu
        verschiedenen Zeiten im Jahr erscheinen. Ein Lauf, der nur den
        Realsteuervergleich neu einliest, darf die Steuerkraft-Reihe nicht
        mitnehmen — sonst hinge der Bestand davon ab, in welcher Reihenfolge
        jemand die beiden Ingests anstößt.

        Übergeben wird nur, was seine Probe bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        years = {int(z["year"]) for z in zeilen}
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for year in sorted(years):
                self._conn.execute(
                    "DELETE FROM council_city_comparison WHERE series = ? AND year = ?",
                    (series, year))
            self._conn.executemany(
                "INSERT INTO council_city_comparison (series, year, key, "
                " city, indicator, value, unit, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(series, z["year"], z["key"], z["city"], z["indicator"],
                  z["value"], z["unit"], hid, now) for z in zeilen])
        return len(zeilen)

    def save_gewerbesteuerstatistik(self, zeilen: list[dict], herkunft) -> int:
        """Einen Erhebungsjahrgang der Gewerbesteuerstatistik ersetzen.

        Ersetzt wird **je Jahr**, nicht die ganze Tabelle: Die Jahrgänge kommen
        aus je eigenen Berichten, und ein Lauf, der 2021 nachträgt, darf 2017
        bis 2020 nicht mitnehmen. Ein Jahrgang wird dagegen vollständig
        ersetzt — das LSN gibt korrigierte Fassungen heraus (der Jahrgang 2020
        wurde am 11.02.2026 nachgebessert), und eine Korrektur, die alte Zeilen
        stehen ließe, wäre keine.

        Übergeben wird nur, was seine Proben bestanden hat; diese Methode prüft
        nichts nach, sie schreibt."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        years = {int(z["year"]) for z in zeilen}
        spalten = ("year", "key", "city", "cases", "cases_positive",
                   "tax_base_eur", "assessments", "assessments_positive",
                   "assessment_tax_base_eur", "apportionments",
                   "apportionments_positive", "apportioned_assessment_eur",
                   "rate", "confidential")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            for year in sorted(years):
                self._conn.execute(
                    "DELETE FROM council_trade_tax_statistics WHERE year = ?",
                    (year,))
            self._conn.executemany(
                f"INSERT INTO council_trade_tax_statistics "
                f"({', '.join(spalten)}, herkunft_id, fetched_at) "
                f"VALUES ({', '.join('?' * len(spalten))},?,?)",
                [tuple(z.get(s) for s in spalten) + (hid, now) for z in zeilen])
        return len(zeilen)

    def save_produkte(self, year: int, produkte: list[dict], herkunft) -> int:
        """Produkte eines Jahres einfügen/aktualisieren. Bewusst KEIN Löschen
        des Jahrgangs: Die Produkte eines Jahres verteilen sich auf mehrere
        Teilhaushalts-Dokumente, die nacheinander eingelesen werden.

        ``INSERT OR REPLACE`` ersetzt bei gleichem ``(year, product_no)`` die
        **ganze** Zeile, samt Herkunft — wer zuletzt schreibt, gewinnt. Das ist
        hier nur deshalb ungefährlich, weil der Aufrufer dafür sorgt, dass ein
        Teilhaushalt genau einmal geschrieben wird: Sechs (Jahrgang,
        Teilhaushalt)-Paare liegen doppelt im Anlagenbestand, und welches der
        beiden Dokumente in der Zeile steht, soll keine Frage der
        Sortierreihenfolge sein. Die Regel und die Messung dazu stehen in
        ``council.finanzquellen.lies_teilhaushalte``. Wer einen zweiten
        Schreibweg zu dieser Tabelle baut, braucht dieselbe Vorentscheidung —
        die Tabelle selbst kann sie nicht treffen, sie sieht nur eine Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.executemany(
                "INSERT OR REPLACE INTO council_products (year, product_no, product_name, "
                " sub_budget_no, sub_budget_name, office, revenues, expenses, result, "
                " short_description, legal_basis, controllability, "
                " controllability_raw, scope, target_group, "
                " source_label, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, p["product_no"], p["product_name"], p.get("sub_budget_no"), p.get("sub_budget_name"),
                  p.get("office"), p.get("revenues"), p.get("expenses"), p.get("result"),
                  p.get("short_description"), p.get("legal_basis"),
                  p.get("controllability"), p.get("controllability_raw"),
                  p.get("scope"), p.get("target_group"),
                  herkunft.label, herkunft.url, now, hid) for p in produkte])
        return len(produkte)

    def save_pruefbericht(self, year: int, feststellungen: list[dict], herkunft) -> int:
        """Prüfungsfeststellungen eines Schlussberichts speichern.

        Der Jahrgang wird vorher geleert: Ein Bericht ist ein Dokument, und
        ein erneuter Ingest liest dasselbe Dokument neu — Zeilen von früheren
        Läufen stehen zu lassen hieße, alte Parser-Stände zu konservieren.

        Die ``citation`` der Herkunft bleibt hier bewusst grob („Randmarken
        des Berichts"): Die genaue Fundstelle einer Feststellung ist ihre
        **Textziffer** und ihre **Seite**, und die stehen je Zeile in der
        Tabelle. Die Herkunft beschreibt das Dokument, nicht die Zeile."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self.transaktion():
            hid = self.merke_herkunft(herkunft, fetched_at=now)
            self._conn.execute("DELETE FROM council_audit_reports WHERE year = ?", (year,))
            self._conn.executemany(
                "INSERT INTO council_audit_reports (year, seq, mark, mark_name, "
                " mark_explanation, text_number, section, chain, page, text, "
                " follow_paragraph, source_label, source_url, fetched_at, herkunft_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(year, f["seq"], f["mark"], f["mark_name"], f.get("mark_explanation"),
                  f["text_number"], f["section"], f.get("chain"), f.get("page"),
                  f["text"], f.get("follow_paragraph"), herkunft.label, herkunft.url, now, hid)
                 for f in feststellungen])
        return len(feststellungen)

    def schulden_kontext(self, year: int | None = None) -> dict | None:
        """Der Schuldenstand: jüngstes Jahr, Vorjahr, höchster Stand der Reihe.

        Ein **Bestand**, kein Jahresverlauf — und genau deshalb eine eigene
        Quelle. Der Haushaltsplan sagt, was die Stadt in einem Jahr einnimmt
        und ausgibt; was am 31.12. an Krediten offen ist, sagt er nicht.

        Die Abgrenzung reist als Feld mit (``council.schulden.ABGRENZUNG``)
        und ist nicht schmückendes Beiwerk: Gezählt wird die Stadt als
        Rechtsträger — Kernhaushalt und Eigenbetriebe, ohne die rechtlich
        selbstständigen Beteiligungen. Die Konzern-Zahl heißt genauso und ist
        ein Vielfaches; ohne den Satz daneben ist „337 Mio. €" eine von zwei
        Zahlen, die beide so heißen.

        Die vier Artenspalten dürfen NULL sein (Fall 2022, s.
        ``council/schulden.py``) — dann kommt die Aufteilung nicht mit, und
        ``breakdown_rejected`` sagt, warum.
        """
        from council import schulden as _schulden

        try:
            rows = [dict(r) for r in self._conn.execute(
                "SELECT * FROM council_debt ORDER BY year")]
        except sqlite3.OperationalError:
            return None
        if not rows:
            return None
        # Das gefragte Jahr, wenn die Reihe es führt — sonst das jüngste, und
        # der Baustein sagt, dass es nicht das gefragte ist.
        idx = next((i for i, r in enumerate(rows) if r["year"] == year), len(rows) - 1)
        abweicht = year is not None and rows[idx]["year"] != year
        rows_bis = rows[:idx + 1]
        neu = rows[idx]
        arten = [(title, neu[field]) for field, title in _schulden.SPALTEN
                 if field not in ("total", "per_capita")
                 and neu.get(field) is not None]
        # Der höchste Stand der Reihe ist eine Angabe der Daten, keine
        # Bewertung: Er sagt, ob die jüngste Zahl im historischen Vergleich
        # oben oder unten liegt — sonst schwebt sie ohne jeden Maßstab.
        hoch = max(rows, key=lambda r: r["total"])
        return {
            "year": neu["year"],
            "total": neu["total"],
            "per_capita": neu.get("per_capita"),
            "arten": arten,
            "breakdown_rejected": neu.get("breakdown_rejected"),
            "revised": bool(neu.get("revised")),
            "davor": ({"year": rows_bis[-2]["year"], "total": rows_bis[-2]["total"]}
                      if len(rows_bis) > 1 else None),
            "hoch": ({"year": hoch["year"], "total": hoch["total"]}
                     if hoch["year"] != neu["year"] else None),
            "reihe_ab": rows[0]["year"],
            "abgrenzung": _schulden.ABGRENZUNG,
            **({"year_asked": year} if abweicht else {}),
            "beleg": self._beleg(neu.get("herkunft_id")),
            "weitere": self._schulden_abgrenzungen(),
            "buergschaften": self._buergschafts_kontext(),
        }

    def _schulden_abgrenzungen(self) -> list[dict]:
        """Die ANDEREN beiden Zahlen, die auch „die Schulden der Stadt" heißen.

        Es gibt drei, sie unterscheiden sich um das Siebzehnfache, und jede
        ist für ihre Abgrenzung richtig (Stand 31.12.2024):

        * **43,7 Mio. €** — die Geldschulden des Kernhaushalts allein, wie sie
          in der Bilanz des Jahresabschlusses stehen.
        * **294,9 Mio. €** — die Stadt als Rechtsträger, also mit ihren
          Eigenbetrieben. Das ist die Reihe des Statistischen Jahrbuchs, die
          Zahl im Block darüber.
        * **740,3 Mio. €** — der ganze „Konzern Stadt", anteilig nach
          Beteiligungshöhe, aus dem Tabellenband der Statistischen Ämter.

        Ohne diese Liste beantwortet die KI-Frage „Wie hoch sind die Schulden?"
        mit **einer** Zahl, und welche das ist, entscheidet der Zufall der
        Facette. Die drei nebeneinander sind die ehrliche Antwort — addiert
        werden dürfen sie nie, sie enthalten einander.
        """
        aus: list[dict] = []
        try:
            r = self._conn.execute(
                "SELECT year, value FROM council_balance_sheet WHERE role = 'financial_liabilities' "
                "ORDER BY year DESC LIMIT 1").fetchone()
            if r:
                aus.append({"art": "Kernhaushalt (nur Geldschulden)", "year": r["year"],
                            "amount": r["value"],
                            "source": "Bilanz des Jahresabschlusses"})
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
        try:
            r = self._conn.execute(
                "SELECT year, total FROM council_integrated_debt "
                "ORDER BY year DESC LIMIT 1").fetchone()
            if r:
                aus.append({"art": "Konzern Stadt (anteilig, mit Beteiligungen)",
                            "year": r["year"], "amount": r["total"],
                            "source": "Integrierte Schulden der Statistischen Ämter"})
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
        return aus

    def _buergschafts_kontext(self) -> dict | None:
        """Wofür die Stadt geradesteht — die Zahl, die in keiner Schuldenreihe steht.

        Eine Bürgschaft kostet nichts, solange sie nicht gezogen wird, und
        taucht deshalb in keiner der drei Schuldenzahlen auf. Ende 2024 waren
        es 220,3 Mio. € — das Fünffache der eigenen Geldschulden des
        Kernhaushalts. Wer nach den Schulden fragt, bekommt das dazu, aber
        ausdrücklich als **eigene** Größe: Eine Bürgschaft ist keine Schuld.
        """
        try:
            r = self._conn.execute(
                "SELECT year, balance, reason, herkunft_id FROM council_buergschaften "
                "ORDER BY year DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not r:
            return None
        rueck = None
        try:
            z = self._conn.execute(
                "SELECT value FROM council_balance_sheet WHERE role = 'guarantee_provisions' "
                "AND year = ?", (r["year"],)).fetchone()
            rueck = z["value"] if z else None
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
        return {"year": r["year"], "balance": r["balance"], "reason": r["reason"],
                "rueckstellung": rueck, "beleg": self._beleg(r["herkunft_id"])}
