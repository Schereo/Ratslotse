"""Sitzungen: Termine, Tagesordnungen, Gremien, Wochenvorschau.

Siebter Schnitt an ``store.py``. Hier liegt der Kalender des Rats: was wann
wo tagt, was daraufsteht, was sich daran geändert hat — und die
Wochenvorschau, die aus all dem eine Seite macht.

Nicht mitgekommen sind die Wortbeitrags- und Video-Abfragen, obwohl sie über
Sitzungen gehen: Sie gehören dem, wonach sie fragen.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from council.scraper import CouncilSession

class SitzungenMixin:
    """Die Sitzungs-Abfragen — nur zum Mitvererben."""

    def _agenda_diff_schluessel_neu(self) -> None:
        """Die Eimer-Namen in `agenda_changes.diff_json` nachziehen — einmalig.

        Der Diff liegt als JSON in der Zeile; seine obersten Schlüssel sind
        das Vokabular, das die Chronik einer Sitzung liest. Zieht der Code auf
        Englisch um und der Bestand nicht, zeigt die Chronik zu jeder alten
        Änderung „nichts geändert" — ohne Fehler.
        """
        import json as _js
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS council_migration_marks ("
                "marke TEXT PRIMARY KEY, gesetzt_am TEXT NOT NULL)")
        marke = "agenda_diff_eimer_englisch"
        if self._conn.execute(
                "SELECT 1 FROM council_migration_marks WHERE marke = ?", (marke,)).fetchone():
            return
        spalten = {r[1] for r in self._conn.execute("PRAGMA table_info(agenda_changes)")}
        if "diff_json" not in spalten:
            return
        geaendert = []
        for rid, roh in self._conn.execute(
                "SELECT rowid, diff_json FROM agenda_changes WHERE diff_json IS NOT NULL"):
            try:
                daten = _js.loads(roh)
            except (ValueError, TypeError):
                continue
            if not isinstance(daten, dict):
                continue
            neu = {self._DIFF_EIMER.get(k, k): v for k, v in daten.items()}
            if neu != daten:
                geaendert.append((_js.dumps(neu, ensure_ascii=False), rid))
        with self._conn:
            if geaendert:
                self._conn.executemany(
                    "UPDATE agenda_changes SET diff_json = ? WHERE rowid = ?", geaendert)
            self._conn.execute(
                "INSERT OR REPLACE INTO council_migration_marks(marke, gesetzt_am) "
                "VALUES (?, datetime('now'))", (marke,))
        if geaendert:
            logging.getLogger("ratslotse.council.store").warning(
                "Tagesordnungs-Diffs umgeschrieben: %d Zeilen", len(geaendert))

    def save_session(self, session: CouncilSession) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO council_sessions
                   (ksinr, committee, session_date, session_time, location, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session.ksinr, session.committee, session.session_date,
                 session.session_time, session.location, now),
            )
            self._conn.execute(
                "DELETE FROM council_agenda_items WHERE ksinr = ?", (session.ksinr,)
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_agenda_items
                   (ksinr, item_number, title, template_number, kvonr, is_public)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (session.ksinr, i.item_number, i.title,
                     i.template_number, i.kvonr, int(i.is_public))
                    for i in session.agenda_items
                ],
            )
            self._conn.execute(
                "DELETE FROM council_agenda_attachments WHERE ksinr = ?", (session.ksinr,)
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO council_agenda_attachments
                   (ksinr, item_number, label, url, raw_text) VALUES (?, ?, ?, ?, ?)""",
                [
                    (session.ksinr, i.item_number, a.get("label") or "Anlage",
                     a.get("url") or "", a.get("raw_text") or None)
                    for i in session.agenda_items
                    for a in (getattr(i, "anlagen", None) or [])
                    if a.get("url")
                ],
            )

    def replace_scheduled_sessions(self, rows: list) -> None:
        """Terminplan komplett ersetzen (rows: ScheduledSession-Objekte).

        Voller Austausch statt Upsert: Der Kalender ist die Quelle der
        Wahrheit — verlegte oder abgesagte Termine verschwinden so mit.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_scheduled_sessions")
            self._conn.executemany(
                """INSERT OR REPLACE INTO council_scheduled_sessions
                   (committee, session_date, session_time, location, fetched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [(r.committee, r.session_date, r.session_time, r.location, now) for r in rows],
            )

    def live_windows(self, day: str) -> dict[str, str]:
        """Startzeit → Startzeit der NÄCHSTEN Sitzung desselben Tages.

        Zurück kommt ``{"16:00": "16:30", "16:30": "18:00"}`` — die letzte
        Startzeit des Tages fehlt, für sie greift der Deckel aus
        ``council.live``. Warum die Nachfolgerin überhaupt ein Ende ist, steht
        im Modul-Docstring dort; zusammengesetzt wird beides in
        ``council.live.window_end``.

        Gilt für heute und später; für vergangene Tage liefert die Abfrage
        nichts (``_UPCOMING_FROM`` blickt nur nach vorn).
        """
        rows = self._conn.execute(
            f"""SELECT DISTINCT NULLIF(session_time, '') AS start
                {self._UPCOMING_FROM}
                WHERE session_date = ? AND NULLIF(session_time, '') IS NOT NULL
                ORDER BY start""",
            (day, day, day),
        ).fetchall()
        starts = [r["start"] for r in rows]
        # Gleichzeitige Sitzungen teilen sich eine Zeile und damit ihr Fenster —
        # DISTINCT hält sie zusammen, statt sie sich gegenseitig beenden zu
        # lassen (das täte ein LEAD über die Zeilen).
        return dict(zip(starts, starts[1:]))

    def sessions_on(self, tag: str) -> list[dict]:
        """Alle Sitzungen an einem Kalendertag — für die Vorabend-Erinnerung
        (Design 30a, N5). Terminierte ohne Tagesordnung kommen mit; der Aufrufer
        entscheidet, ob er sie braucht."""
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM council_sessions WHERE session_date = ? ORDER BY session_time",
            (tag,))]

    def upcoming_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Kommende Sitzungen: echte (mit ksinr/Tagesordnung) plus terminierte
        aus dem Kalender (ksinr NULL), solange keine echte Sitzung desselben
        Gremiums am selben Tag existiert."""
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            f"""SELECT * {self._UPCOMING_FROM}
                ORDER BY session_date ASC, session_time ASC
                LIMIT ? OFFSET ?""",
            (today, today, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def naechste_sitzung_je_gremium(self) -> dict[str, dict]:
        """Je Gremium der nächste anstehende Termin — für die Ausschuss-Abos,
        die zu jedem Gremium „nächste Sitzung: …" zeigen.

        Nimmt dieselbe Menge wie ``upcoming_sessions`` (``_UPCOMING_FROM``:
        echte Sitzungen plus terminierte aus dem Kalender, Dubletten am selben
        Tag verdeckt) — sonst nennt die Abo-Seite einen anderen Termin als die
        Sitzungsliste. Gremien ohne künftigen Termin fehlen im dict; der
        Aufrufer entscheidet, was er statt eines Datums schreibt.
        """
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            f"""SELECT committee, session_date, session_time {self._UPCOMING_FROM}
                ORDER BY session_date ASC, COALESCE(NULLIF(session_time, ''), '99:99') ASC""",
            (today, today),
        ).fetchall()
        naechste: dict[str, dict] = {}
        for r in rows:
            # Erste Zeile je Gremium gewinnt — die Sortierung oben hat den
            # frühesten Termin nach vorne gelegt. Termine ohne Uhrzeit
            # (``session_time`` ist NOT NULL, aber oft leer) landen am Ende
            # des Tages, sonst verdeckt der Eintrag ohne Zeit den mit.
            naechste.setdefault(r["committee"], {
                "session_date": r["session_date"],
                "session_time": r["session_time"] or None,
            })
        return naechste

    @classmethod
    def _titel_worte(cls, title: str | None) -> set[str]:
        """Tragende Wörter eines Titels — die Handhabe für „ist das dieselbe
        Sache?". Kurzes und Rubrik-Vokabular fliegt raus, sonst gälte jede
        Überschrift mit dem Wort „Antrag" als Vorhaben."""
        gefaltet = cls._falte_namen(title or "")
        worte = "".join(c if c.isalnum() else " " for c in gefaltet).split()
        return {w for w in worte if len(w) >= 5 and not w.isdigit()
                and w not in cls._RUBRIK_WORTE}

    @classmethod
    def _top_sortierung(cls, item_number: str | None) -> tuple:
        """Sortierschlüssel für eine TOP-Nummer — „Ö 5" vor „Ö 16.4".

        Lexikografisch verglichen stand „Ö 16.4" vor „Ö 5" (und „Ö 10" vor
        „Ö 2"); die Karte listete ihre Punkte damit in einer Reihenfolge, die
        es auf der Tagesordnung nicht gibt. Dieselbe Falle steht schon im
        Frontend dokumentiert (`decision/view.tsx`: „4.10 käme sonst vor 4.2").
        """
        m = cls._TOP_NUMMER_RE.match(item_number or "")
        if not m:
            return (item_number or "",), ()
        return (m.group(1),), tuple(int(t) for t in m.group(2).split(".") if t.isdigit())

    @classmethod
    def _eltern_nummer(cls, item_number: str | None) -> str | None:
        """Nummer des übergeordneten Tagesordnungspunkts — „Ö 11.3" → „Ö 11".

        ``None`` für Punkte ohne Unterebene. Bewusst rein syntaktisch: Ob es
        den Elternpunkt wirklich gibt (und ob er eine Überschrift ist), prüft
        der Aufrufer am Bestand der Sitzung.
        """
        m = cls._TOP_NUMMER_RE.match(item_number or "")
        if not m:
            return None
        praefix, nummer = m.group(1), m.group(2)
        if "." not in nummer:
            return None
        return f"{praefix} {nummer.rsplit('.', 1)[0]}"

    @classmethod
    def _titel_zerlegen(cls, title: str) -> tuple:
        """Antragsteller heraustrennen und den Titel fürs Anzeigen kürzen.

        „Bildende Kunst im Stadtmuseum (CDU-Fraktion vom 07.07.2026) - Bericht
        der Verwaltung" → („CDU-Fraktion", „Bildende Kunst im Stadtmuseum").
        Der Antragsteller gehört als eigenes Merkmal neben den Titel, nicht
        mitten hinein — sonst bleibt vom Gegenstand nichts übrig.
        """
        wer = None
        m = cls._ANTRAGSTELLER_RE.search(title or "")
        if m and cls._ANTRAG_RE.search(m.group(0)):
            wer = " ".join((m.group("wer") or "").split()) or None
            title = (title[:m.start()] + title[m.end():]).strip()
        kurz = cls._TITEL_ANHANG_RE.sub("", title or "").strip(" -–;,")
        return wer, kurz or (title or "")

    def _punkte_bewerten(self, punkte: list[dict]) -> None:
        """Wichtigkeit je Tagesordnungspunkt — deterministisch, ohne Modell.

        Die Karte trägt fünf Zeilen, die Woche bringt gut dreißig inhaltliche
        Punkte (gemessen). Es braucht also eine Auswahl, und „hat eine
        Kurzfassung" ist keine. Vier Signale, alle am Bestand geprüft:

        * **Behandlungsart** aus der Beratungsfolge — die amtliche Einstufung
          der Verwaltung: ``Entscheidung`` wiegt schwerer als ``Vorberatung``,
          die schwerer als ``Kenntnisnahme``. Kein Titel-Raten.
        * **Fraktionsantrag**: Was eine Fraktion beantragt, ist strittig und
          damit meist bedeutsamer als ein Verwaltungsbericht (Tims Beobachtung
          12.08.) — aber eben nur meist, deshalb ein Gewicht und kein Filter.
        * **Themen-Gewicht**: Nennt der Titel eine bekannte Entität, zählt
          deren Beschluss-Historie (Fliegerhorst 166, Stadtmuseum 30) —
          gedämpft, damit ein Dauerthema nicht jede Woche alles verdrängt.
        * **Vorgeschichte**: eine frühere Station derselben Vorlage. Selten
          (diese Woche 1 von 22), aber wenn, dann ein echter Hinweis.

        Bewusst NICHT verwendet: frühere BESCHLÜSSE zur selben Vorlage. Neue
        Vorlagen haben per Definition keine, und ältere erreichen uns erst mit
        dem Protokoll — gemessen 0 von 33 Punkten.
        """
        import math

        entitaeten = []
        try:
            entitaeten = [(self._falte_namen(r["name"]), r["n"]) for r in self._conn.execute(
                "SELECT name, n FROM council_entities WHERE n >= 5")
                if len(r["name"] or "") >= 4]
        except Exception:  # noqa: BLE001 — ohne Entitäten fehlt nur ein Signal
            pass

        for p in punkte:
            rang = 0.0
            art = (p.get("behandlung") or "").lower()
            if "entscheid" in art:
                rang += 3.0
            elif "vorberat" in art:
                rang += 2.0
            elif art:
                rang += 0.5          # Kenntnisnahme: informativ, nicht folgenlos
            if self._ANTRAG_RE.search(p["title"]):
                rang += 1.5
            # Bindungswirkung: Satzung, Gebühren, Haushalt, Bauleitplan — das
            # Signal, das dem Modell komplett fehlte. Eine Satzungsänderung
            # verlor gegen einen Museumsbericht, weil „Bericht + bekannter
            # Name" mehr Nebenpunkte sammelte als „Entscheidung" (Tim, 15.08.).
            if self._BINDEND_RE.search(p["title"]):
                rang += 2.0
            titel_gefaltet = f" {self._falte_namen(p['title'])} "
            gewicht = max((n for name, n in entitaeten if name and f" {name} " in titel_gefaltet),
                          default=0)
            if gewicht:
                # Gedeckelt auf 1.0: Das Gewicht misst BEKANNTHEIT („Stadtmuseum
                # kam in 30 Beschlüssen vor"), nicht die Bedeutung des heutigen
                # Punktes. Als 2.0-Bonus hat es ganze Ränge gedreht.
                rang += min(1.0, math.log10(gewicht))
            if p.get("vorgeschichte"):
                rang += 1.0
            if p.get("summary"):
                rang += 0.4          # erklärbar schlägt unerklärt bei Gleichstand
            if p.get("template_number"):
                rang += 0.2
            # Beschlussvorlage heißt: Die Verwaltung legt etwas zur
            # Entscheidung vor. Das ist unabhängig davon, welches Gremium
            # formal beschließt — und genau daran scheiterte die Auswahl
            # bisher (Tims Befund 19.08.26): Die VBN-Tarifanpassung ist eine
            # Beschlussvorlage, wird im Fachausschuss aber als „Kenntnisnahme"
            # geführt, weil der Rat entscheidet. Sie landete bei 13 von 100
            # und fiel unter die Schwelle, während ein Umsatzsteuer-Bericht
            # mit 30 auf der Karte stand.
            beschlussvorlage = "beschluss" in (p.get("kind") or "").lower()
            if beschlussvorlage:
                rang += 1.5
            for namen, bonus in self._GREMIUM_GEWICHT:
                if any(n in (p.get("committee") or "").lower() for n in namen):
                    rang += bonus
                    break
            # Gremien-Personalien sind formal Entscheidungen, aber für die
            # Öffentlichkeit selten der Rede wert („Berufung Beratendes
            # Mitglied …") — sie landeten sonst allein wegen der Behandlungsart
            # ganz oben.
            if self._PERSONALIE_RE.search(p["title"]):
                rang -= 2.0
            # Die Behandlungsart ist eine SCHRANKE, kein Summand mehr: Ein
            # Bericht zur Kenntnis kann sich nicht mehr über Nebensignale an
            # einer Entscheidung vorbeischieben. Die Deckel entsprechen den
            # Ankern des Tragweite-Prompts (Kenntnisnahme ≈ 20 von 100).
            #
            # Nicht aber für Beschlussvorlagen: Deren Prämisse — „hier wird
            # nichts entschieden" — ist schlicht falsch, das Gremium bereitet
            # dann nur die Entscheidung eines anderen vor.
            if (art and "entscheid" not in art and "vorberat" not in art
                    and not beschlussvorlage):
                rang = min(rang, 2.5)
            p["rang"] = round(max(rang, 0.0), 2)
            # Auf die Tragweite-Skala heben (0–100), damit Heuristik und
            # LLM-Bewertung vergleichbar sind: 2.5 → 30, 5 → 60, 8 → 95.
            p["wichtig"] = min(95, round(p["rang"] * 12))
            p["wichtig_quelle"] = "regeln"

    def sitzungen_im_fenster(self, tage: int = 7) -> list[dict]:
        """Jede Sitzung der kommenden ``tage`` Tage — die Grundlage der
        Wochen-Karte.

        ``location`` und die Punktzahl gehören dazu: Design 14 zeigt auf dem
        Desktop „17:00 · Ratssaal" und leitet aus ``n_items == 0`` die Zeile
        „nicht öffentlich" ab — eine Sitzung ohne einen einzigen öffentlichen
        Tagesordnungspunkt ist genau das.

        Eigene Methode, weil der Router die ksinr-Liste **vor** der Vorschau
        braucht: Die Themen-Treffer stehen in der anderen Datenbank und lassen
        sich nicht im selben SQL mitnehmen.
        """
        from datetime import date, timedelta

        heute = date.today()
        bis = (heute + timedelta(days=tage)).isoformat()
        return [dict(r) for r in self._conn.execute(
            "SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, "
            "       cs.location, COUNT(ci.id) AS n_items "
            "FROM council_sessions cs "
            "LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr AND ci.is_public = 1 "
            "WHERE cs.session_date >= ? AND cs.session_date <= ? "
            "GROUP BY cs.ksinr ORDER BY cs.session_date, cs.session_time",
            (heute.isoformat(), bis))]

    def _bewertete_punkte(self, sitzungen: list[dict],
                          meine: dict[int, list[dict]] | None = None) -> list[dict]:
        """Alle inhaltlichen Tagesordnungspunkte der ``sitzungen``, bewertet
        und nach Rang sortiert — Treffer zu eigenen Themen zuerst, dann nach
        Tragweite.

        EINE Bewertung für alle Abnehmer: die Wochenvorschau (und damit die
        Mail und der Instagram-Bot) und die Highlights je Sitzung in der
        Sitzungsliste (``sitzungs_highlights``). Vorher lebte das alles in
        ``wochenvorschau`` und galt nur für die kommenden sieben Tage; eine
        Sitzung in zwei Wochen hatte deshalb keine Highlights, obwohl ihre
        Punkte längst bewertet waren (Tims Frage 04.09.2026).
        """
        from .dringlichkeit import ist_dringlichkeitsantrag

        if not sitzungen:
            return []
        ph = ",".join("?" * len(sitzungen))
        # ``v.kind`` unterscheidet Beschluss- von Berichtsvorlage — das stärkste
        # verfügbare Signal dafür, ob überhaupt etwas entschieden werden soll.
        # Es lag bis 19.08.26 ungenutzt in der Datenbank.
        rohe = self._conn.execute(
            f"SELECT a.ksinr, a.item_number, a.title, a.template_number, a.kvonr, s.summary, "
            f"       v.kind, so.text AS social_text "
            f"FROM council_agenda_items a "
            f"LEFT JOIN agenda_item_summaries s ON s.ksinr = a.ksinr AND s.item_number = a.item_number "
            f"LEFT JOIN agenda_item_social so ON so.ksinr = a.ksinr AND so.item_number = a.item_number "
            f"LEFT JOIN council_templates v ON v.kvonr = a.kvonr "
            f"WHERE a.ksinr IN ({ph}) AND a.is_public = 1 ORDER BY a.id",
            [s["ksinr"] for s in sitzungen]).fetchall()
        nach_sitzung = {s["ksinr"]: s for s in sitzungen}

        # Überschriften-Punkte erkennen: „Ö 11 Bauleitplanung Gewerbegebiet
        # Brokhausen" trägt keine Vorlage, darunter hängen Ö 11.1 … Ö 11.4 als
        # Stationen DESSELBEN Vorhabens. Ohne diese Bündelung belegen vier
        # Stationen alle drei Plätze der Sitzung (Tims Befund 19.08.26) — und
        # die Karte zeigt dreimal denselben Bebauungsplan.
        eltern_von = {(r["ksinr"], r["item_number"]): self._eltern_nummer(r["item_number"])
                      for r in rohe}
        kinder_zahl: dict[tuple, int] = {}
        for (ksinr, _nr), eltern in eltern_von.items():
            if eltern:
                kinder_zahl[(ksinr, eltern)] = kinder_zahl.get((ksinr, eltern), 0) + 1
        # Nur ein Punkt OHNE eigene Vorlage ist eine reine Überschrift. Ein
        # Punkt mit Vorlage, unter dem Unterpunkte hängen, ist selbst Inhalt.
        #
        # Und nur, wenn er ein VORHABEN benennt statt einer Rubrik: „Anträge
        # der Fraktionen, Gruppen, Rats- und Ausschussmitglieder" trägt elf
        # völlig verschiedene Themen unter sich; die zu einer Gruppe zu
        # bündeln hieße, zehn davon nie zu zeigen. Beleg dafür, dass es
        # dieselbe Sache ist: ein tragendes Wort der Überschrift steht in
        # JEDEM Unterpunkt („Meerweg", „Brokhausen") — bei einer Rubrik in
        # keinem.
        kinder_worte: dict[tuple, list[set]] = {}
        for r in rohe:
            eltern = eltern_von.get((r["ksinr"], r["item_number"]))
            if eltern:
                kinder_worte.setdefault((r["ksinr"], eltern), []).append(
                    self._titel_worte(r["title"]))
        #
        # Zwei Dinge, die auseinandergehalten werden müssen: Eine KOPFZEILE
        # trägt selbst keinen Inhalt (weder Vorlage noch Gegenstand) und darf
        # nie als Punkt auftauchen — das gilt für Vorhaben UND Rubriken. Nur
        # die Vorhaben bündeln zusätzlich ihre Unterpunkte.
        kopfzeile = {(r["ksinr"], r["item_number"]) for r in rohe
                     if not r["template_number"] and (r["ksinr"], r["item_number"]) in kinder_worte}
        heading = {}
        for r in rohe:
            schl = (r["ksinr"], r["item_number"])
            if schl not in kopfzeile:
                continue
            eigene = self._titel_worte(r["title"])
            if any(all(w in kind for kind in kinder_worte[schl]) for w in eigene):
                heading[schl] = (r["title"] or "").strip()

        kandidaten = []
        for r in rohe:
            title = (r["title"] or "").strip()
            if not title or self._FORMALIE_RE.search(title):
                continue
            key = (r["ksinr"], r["item_number"])
            if key in kopfzeile:
                continue          # trägt keinen Inhalt, nur eine Zwischenzeile
            sitz = nach_sitzung[r["ksinr"]]
            eltern = eltern_von.get(key)
            gruppe_nr = eltern if (r["ksinr"], eltern) in heading else r["item_number"]
            kandidaten.append({
                "ksinr": r["ksinr"], "item_number": r["item_number"], "title": title,
                "summary": (r["summary"] or "").strip() or None,
                # Der Kartentext für Social Media (agenda_item_social) — kennt
                # Vorlage und Anlagen und wertet nicht. Fehlt er, bleibt es bei
                # der Kurzfassung; der Bot behandelt beides gleich.
                "social_text": (r["social_text"] or "").strip() or None,
                # Ein kurzfristig eingebrachter Antrag (council/dringlichkeit.py).
                # Die Karte sagt das dazu, statt ihn wie einen Punkt der
                # amtlichen Tagesordnung zu zeigen — er steht in keiner.
                "dringlich": ist_dringlichkeitsantrag(r["item_number"]),
                "template_number": r["template_number"], "kvonr": r["kvonr"], "kind": r["kind"],
                "committee": sitz["committee"], "session_date": sitz["session_date"],
                "gruppe_nr": gruppe_nr,
                "gruppe_titel": heading.get((r["ksinr"], gruppe_nr)),
            })

        # Wie viele Stationen hat jede Gruppe? Die Karte sagt damit „Bauleit-
        # planung Meerweg · 2 Stationen" statt zweimal fast denselben Titel.
        gruppe_gross: dict[tuple, int] = {}
        for k in kandidaten:
            schl = (k["ksinr"], k["gruppe_nr"])
            gruppe_gross[schl] = gruppe_gross.get(schl, 0) + 1
        for k in kandidaten:
            k["gruppe_stationen"] = gruppe_gross[(k["ksinr"], k["gruppe_nr"])]

        # Behandlungsart und Vorgeschichte aus der Beratungsfolge — sie kommt
        # direkt aus dem Ratsinformationssystem und hängt NICHT am Protokoll.
        kvonrs = [k["kvonr"] for k in kandidaten if k["kvonr"]]
        stationen: dict[int, list] = {}
        if kvonrs:
            ph2 = ",".join("?" * len(kvonrs))
            for b in self._conn.execute(
                    f"SELECT kvonr, date, result FROM council_deliberations "
                    f"WHERE kvonr IN ({ph2}) ORDER BY date", kvonrs):
                stationen.setdefault(b["kvonr"], []).append(dict(b))
        for k in kandidaten:
            series = stationen.get(k["kvonr"] or 0, [])
            heutige = next((b for b in series if b["date"] == k["session_date"]), None)
            k["behandlung"] = (heutige or {}).get("result")
            k["vorgeschichte"] = sum(1 for b in series if (b["date"] or "9999") < k["session_date"])
            k["applicants"], k["titel_kurz"] = self._titel_zerlegen(k["title"])

        # Eigene Themen-Treffer anheften. Der Abgleich läuft über (ksinr,
        # item_number) — dieselbe Kennung, die auch die Benachrichtigungen
        # benutzen.
        treffer = {(ksinr, m["item_number"]): m.get("topic_name")
                   for ksinr, ms in (meine or {}).items() for m in ms}
        for k in kandidaten:
            k["topic_name"] = treffer.get((k["ksinr"], k["item_number"]))

        self._punkte_bewerten(kandidaten)
        # Wo eine LLM-Tragweite vorliegt, schlägt sie die Regeln: Die Regeln
        # kennen Verfahrenssignale, die Bewertung kennt Betroffene, Geld und
        # Bindungswirkung. Beide liegen auf derselben 0–100-Skala.
        bewertet = {(r["ksinr"], r["item_number"]): (r["impact"], r["reason"])
                    for r in self._conn.execute(
                        f"SELECT ksinr, item_number, impact, reason FROM agenda_item_impact "
                        f"WHERE ksinr IN ({ph})", [s["ksinr"] for s in sitzungen])}
        from council.impact import dringlichkeits_boden, formalakt_deckel

        for k in kandidaten:
            eintrag = bewertet.get((k["ksinr"], k["item_number"]))
            if eintrag:
                k["wichtig"], k["wichtig_grund"] = eintrag[0], eintrag[1]
                k["wichtig_quelle"] = "tragweite"
            # Straßenrechtliche Formalakte (Widmung, Einziehung, Umstufung)
            # deckeln — egal ob Heuristik oder LLM sie hochgestuft hat: Die
            # Widmung „Im Technologiepark" stand als „wichtig" auf der Karte
            # (Tims Befund 18.08.). Lesezeitig, damit auch schon gespeicherte
            # Fehlbewertungen sofort verschwinden.
            deckel = formalakt_deckel(k["title"])
            if deckel is not None and k["wichtig"] > deckel:
                k["wichtig"] = deckel
                k["wichtig_grund"] = None
            # Und der Gegenpol: Dringlichkeitsanträge bekommen einen Boden.
            # Die Rubrik misst Tragweite, nicht Aktualität — dass eine
            # Fraktion die Tagesordnung für eine Sache aufmacht, wiegt sie
            # nicht mit (Tims Entscheidung 30.08.26). Der Grund des Modells
            # bleibt stehen: Er ist richtig, er wog nur die Kurzfristigkeit
            # nicht mit. Lesezeitig wie der Deckel, damit er auch für schon
            # bewertete Punkte sofort gilt.
            boden = dringlichkeits_boden(k["item_number"])
            if boden is not None and k["wichtig"] < boden:
                k["wichtig"] = boden
        # Treffer zuerst, danach nach Rang: Ein Punkt zu einem eigenen Thema ist
        # relevanter als jeder gut bewertete Fremdpunkt.
        kandidaten.sort(key=lambda p: (0 if p["topic_name"] else 1, -p["wichtig"], p["session_date"]))
        return kandidaten

    @staticmethod
    def _punkt_export(k: dict) -> dict:
        """Die Felder eines bewerteten Punktes, wie sie nach außen gehen.

        Genau EINE Stelle dafür — die Liste ``further_per_session`` baute die
        Punkte früher Feld für Feld neu zusammen, und zweimal fehlte dabei ein
        Feld (Kurzfassung, Kartentext), sodass Instagram-Karten ohne Erklärung
        standen. Wer ein Feld ergänzt, ergänzt es hier, und alle Abnehmer
        bekommen es.
        """
        return {
            "ksinr": k["ksinr"], "item_number": k["item_number"],
            "title": k["title"], "titel_kurz": k["titel_kurz"],
            "applicants": k["applicants"], "topic_name": k["topic_name"],
            "summary": k["summary"], "social_text": k.get("social_text"),
            "dringlich": k.get("dringlich", False),
            "wichtig": k["wichtig"], "wichtig_grund": k.get("wichtig_grund"),
            "template_number": k["template_number"], "kvonr": k["kvonr"],
            "committee": k["committee"], "session_date": k["session_date"],
            "gruppe_nr": k["gruppe_nr"], "gruppe_titel": k["gruppe_titel"],
            "gruppe_stationen": k["gruppe_stationen"],
        }

    def sitzungs_highlights(self, ksinrs: list[int | None],
                            meine: dict[int, list[dict]] | None = None,
                            max_je_sitzung: int = 2) -> dict[int, list[dict]]:
        """Die wichtigsten Punkte je Sitzung — für die Sitzungsliste, mit
        derselben Bewertung und derselben Schwelle wie die Wochenvorschau
        (``WICHTIG_MINDEST``; ein Treffer zu einem eigenen Thema umgeht sie).

        Je Vorhaben (``gruppe_nr``) ein Platz, höchstens ``max_je_sitzung``
        je Sitzung, innerhalb der Sitzung in Tagesordnungs-Reihenfolge.
        ``top`` markiert, was hervorgehoben gehört: ein eigenes Thema oder
        eine Tragweite ab ``TOP_MINDEST``. Sitzungen ohne einen Punkt über
        der Schwelle fehlen im Ergebnis — die Karte sagt dann nichts, statt
        etwas Beliebiges zu behaupten.
        """
        gueltig = [k for k in ksinrs if k]
        if not gueltig:
            return {}
        ph = ",".join("?" * len(gueltig))
        sitzungen = [dict(r) for r in self._conn.execute(
            f"SELECT ksinr, committee, session_date FROM council_sessions "
            f"WHERE ksinr IN ({ph})", gueltig)]
        ergebnis: dict[int, list[dict]] = {}
        gruppen: dict[int, set] = {}
        for k in self._bewertete_punkte(sitzungen, meine):
            if not k["topic_name"] and k["wichtig"] < self.WICHTIG_MINDEST:
                continue
            gesehen = gruppen.setdefault(k["ksinr"], set())
            if k["gruppe_nr"] in gesehen:
                continue
            liste = ergebnis.setdefault(k["ksinr"], [])
            if len(liste) >= max_je_sitzung:
                continue
            gesehen.add(k["gruppe_nr"])
            punkt = self._punkt_export(k)
            punkt["top"] = bool(k["topic_name"]) or k["wichtig"] >= self.TOP_MINDEST
            liste.append(punkt)
        for liste in ergebnis.values():
            liste.sort(key=lambda p: self._top_sortierung(p["item_number"]))
        return ergebnis

    def wochenvorschau(self, tage: int = 7, max_punkte: int = 5,
                       meine: dict[int, list[dict]] | None = None) -> dict:
        """Was steht in den nächsten Tagen im Rat an? — „Diese Woche im Rat".

        Bewusst nach VORN gerichtet: Beschlüsse erreichen uns erst mit dem
        Protokoll, und das dauert im Median 119 Tage (am Bestand gemessen).
        Ein Wochenrückblick aus Beschlüssen wäre also ein Rückblick auf den
        vorletzten Monat. Tagesordnungen dagegen liegen vor der Sitzung vor —
        für die kommende Woche stehen sie heute schon da.

        Ausgewählt werden inhaltliche Punkte (Formalien fliegen raus), bevorzugt
        solche mit Kurzfassung und Vorlage, und höchstens zwei je Sitzung, damit
        eine große Tagesordnung die Ausgabe nicht auffrisst.

        ``meine`` sind die Tagesordnungs-Treffer der eigenen Themen
        (``{ksinr: [{item_number, topic_name}]}``, kommt aus der anderen
        Datenbank und wird deshalb hereingereicht). Wer ein Thema getroffen
        hat, ist relevant — solche Punkte umgehen die Rang-Schwelle. Design 14
        baut darauf auf: Sitzungen mit eigenen Treffern klappen ihre Punkte
        auf, alle anderen bleiben eine ruhige Zeile.
        """
        from datetime import date, timedelta

        heute = date.today()
        bis = (heute + timedelta(days=tage)).isoformat()
        sitzungen = self.sitzungen_im_fenster(tage)
        if not sitzungen:
            return {"found": False, "from_date": heute.isoformat(), "to_date": bis,
                    "sessions": [], "items": []}

        kandidaten = self._bewertete_punkte(sitzungen, meine)
        gruppen_je_sitzung: dict[int, set] = {}
        punkte = []
        for p in kandidaten:
            # Wer ein eigenes Thema trifft, ist per Definition relevant — die
            # Rang-Schwelle gilt nur für die allgemeine Auswahl.
            if not p["topic_name"] and p["wichtig"] < self.WICHTIG_MINDEST:
                continue
            # Höchstens drei GRUPPEN je Sitzung — nicht drei Punkte. Eine
            # Bauleitplanung mit vier Stationen ist ein Vorhaben und bekommt
            # einen Platz; da die Liste nach Rang sortiert ist, ist der erste
            # Treffer einer Gruppe zugleich ihr stärkster Punkt.
            gesehen = gruppen_je_sitzung.setdefault(p["ksinr"], set())
            gruppe = p["gruppe_nr"]
            if gruppe in gesehen:
                continue
            if len(gesehen) >= 3:
                continue
            gesehen.add(gruppe)
            punkte.append(p)
            if len(punkte) >= max_punkte:
                break
        # Hervorgehoben wird, was wirklich schwer wiegt — keiner, einer oder
        # zwei. Design 14a sah genau EINEN vor; das erzwang eine Hervorhebung
        # auch in Wochen, in denen der beste Punkt ein Bericht mit 30 war, und
        # deckelte sie in Wochen mit mehreren großen Entscheidungen (Tim,
        # 15.08.). Die Schwelle liegt an den Ankern des Prompts: 55 ≈ neue
        # Richtlinie, 75 ≈ Bebauungsplan fürs Quartier.
        for p in punkte:
            p["top"] = False
        gesetzt: list[set[str]] = []
        # Ein Punkt zum eigenen Thema wird immer hervorgehoben, egal wie die
        # allgemeine Bewertung ausfällt: Für wen ein Thema angelegt ist, ist
        # genau das der Grund hinzusehen. Der Rest der Plätze geht an das,
        # was für die ganze Stadt schwer wiegt.
        eigene = sorted((p for p in punkte if p.get("topic_name")),
                        key=lambda p: -p["wichtig"])
        if eigene:
            eigene[0]["top"] = True
            gesetzt.append({w for w in self._falte_namen(eigene[0]["title"]).split()
                            if len(w) >= 6})
        for p in sorted(punkte, key=lambda p: -p["wichtig"]):
            if p["top"]:
                continue
            if len(gesetzt) >= self.TOP_MAX or p["wichtig"] < self.TOP_MINDEST:
                break
            # Nicht zweimal dieselbe Sache: In der Stadion-Woche standen der
            # Bebauungsplan UND die Flächennutzungsplan-Änderung ganz oben —
            # zwei Hervorhebungen, ein Vorgang. Zwei geteilte Schlagwörter
            # reichen als Beleg (gemessen an echten Wochen).
            worte = {w for w in self._falte_namen(p["title"]).split() if len(w) >= 6}
            if any(len(worte & frueher) >= 2 for frueher in gesetzt):
                continue
            p["top"] = True
            gesetzt.append(worte)
        punkte.sort(key=lambda p: (p["session_date"], self._top_sortierung(p["item_number"])))

        # Wie viele relevante Punkte hätte jede Sitzung — VOR dem Anzeige-
        # Deckel. Design 14 braucht das zweimal: für das Abzeichen („3 für
        # dich") und für die ehrliche Restzeile („1 weiterer Punkt"). Ohne die
        # Rohzahl würde die Karte verschweigen statt zu verkürzen, und genau
        # das verbietet Prinzip ② der Dichte-Matrix.
        relevant: dict[int, int] = {}
        # Getrennt gezählt, weil es zwei verschiedene Dinge sind: „passt zu
        # deinem Thema" und „ist allgemein wichtig". Die Karte trug beides als
        # „N für dich" — bei jemandem ohne passendes Thema war das schlicht
        # falsch (Tims Befund 15.08.).
        matches_per_session: dict[int, int] = {}
        # Und wie viele inhaltliche Themen hat die Sitzung ÜBERHAUPT — ohne
        # Formalien, ohne Überschriften-Zeilen, Stationen eines Vorhabens als
        # eines gezählt. Das ist die Zahl für „+ N weitere Tagesordnungs-
        # punkte": Die Karte nannte bisher nur die weiteren RELEVANTEN Punkte
        # („+ 1"), obwohl auf der Tagesordnung noch 26 Themen standen — das
        # klang nach einer dünnen Sitzung statt nach einer Auswahl.
        themen_je_sitzung: dict[int, set] = {}
        for k in kandidaten:
            if k["topic_name"]:
                matches_per_session[k["ksinr"]] = matches_per_session.get(k["ksinr"], 0) + 1
            if k["topic_name"] or k["wichtig"] >= self.WICHTIG_MINDEST:
                relevant[k["ksinr"]] = relevant.get(k["ksinr"], 0) + 1
            themen_je_sitzung.setdefault(k["ksinr"], set()).add(k["gruppe_nr"])
        # Die übrigen relevanten Punkte je Sitzung MIT ausliefern (Tims Wunsch
        # 18.08.): „x weitere Punkte" soll in der Karte aufklappen statt zur
        # Tagesordnung wegzunavigieren — dafür braucht die Karte die Titel.
        # kandidaten sind bereits nach Rang sortiert, die Reihenfolge bleibt.
        gezeigt = {(p["ksinr"], p["item_number"]) for p in punkte}
        further_per_session: dict[int, list[dict]] = {}
        for k in kandidaten:
            if (k["ksinr"], k["item_number"]) in gezeigt:
                continue
            if not (k["topic_name"] or k["wichtig"] >= self.WICHTIG_MINDEST):
                continue
            further_per_session.setdefault(k["ksinr"], []).append(self._punkt_export(k))
        return {
            # Seit Design 14 trägt die Karte auch die Sitzungen ohne relevante
            # Punkte (sie ersetzt „Nächste Sitzungen"). Sie hat also Inhalt,
            # sobald überhaupt eine Sitzung ansteht — vorher hing das an den
            # Punkten, und eine Woche ohne Highlight ließ die Karte verschwinden.
            "found": bool(sitzungen),
            "from_date": heute.isoformat(), "to_date": bis,
            "sessions": sitzungen,
            "items": punkte,
            "relevant_per_session": relevant,
            "further_per_session": further_per_session,
            "matches_per_session": matches_per_session,
            "matches_total": sum(1 for k in kandidaten if k["topic_name"]),
            "substantive_total": len(kandidaten),
            "substantive_per_session": {k: len(v) for k, v in themen_je_sitzung.items()},
        }

    def count_upcoming_sessions(self) -> int:
        from datetime import date
        today = date.today().isoformat()
        return self._conn.execute(
            f"SELECT COUNT(*) {self._UPCOMING_FROM}", (today, today)
        ).fetchone()[0]

    def recent_sessions(self, limit: int = 10, offset: int = 0) -> list[dict]:
        from datetime import date
        today = date.today().isoformat()
        rows = self._conn.execute(
            """SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                      COUNT(ci.id) AS n_items
               FROM council_sessions cs
               LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
               WHERE cs.session_date < ?
               GROUP BY cs.ksinr
               ORDER BY cs.session_date DESC
               LIMIT ? OFFSET ?""",
            (today, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_recent_sessions(self) -> int:
        from datetime import date
        today = date.today().isoformat()
        return self._conn.execute(
            "SELECT COUNT(*) FROM council_sessions WHERE session_date < ?", (today,)
        ).fetchone()[0]

    def mark_notified(self, ksinr: int, owner_id: int, agenda_hash: str = "") -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO committee_notifications (ksinr, owner_id, agenda_hash, sent_at) VALUES (?, ?, ?, ?)",
                (ksinr, owner_id, agenda_hash, now),
            )

    def get_last_notified_hash(self, ksinr: int, owner_id: int) -> str | None:
        """Return the agenda_hash that was last used when notifying this owner, or None if never notified.
        An empty string means the row predates hash tracking and should not trigger a re-notification."""
        row = self._conn.execute(
            "SELECT agenda_hash FROM committee_notifications WHERE ksinr = ? AND owner_id = ?",
            (ksinr, owner_id),
        ).fetchone()
        return row[0] if row is not None else None

    def get_cached_summary(self, ksinr: int, agenda_hash: str) -> str | None:
        """Return the cached summary for this session+agenda, or None on cache miss.
        A cached empty string ('') means 'only routine items' and is a valid hit."""
        row = self._conn.execute(
            "SELECT summary FROM committee_summaries WHERE ksinr = ? AND agenda_hash = ?",
            (ksinr, agenda_hash),
        ).fetchone()
        return row[0] if row is not None else None

    def save_item_summaries(self, ksinr: int, agenda_hash: str, punkte: list[dict]) -> None:
        """TOP-Zusammenfassungen ersetzen (eine Tagesordnung, ein Stand)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM agenda_item_summaries WHERE ksinr = ?", (ksinr,))
            self._conn.executemany(
                "INSERT OR REPLACE INTO agenda_item_summaries "
                "(ksinr, item_number, summary, agenda_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                [(ksinr, p["number"], p["summary"], agenda_hash, now)
                 for p in punkte if p.get("number") and p.get("summary")])

    def agenda_items_needing_social_text(self, limit: int | None = None,
                                         tage_voraus: int = 21,
                                         mindest_wichtig: int = 0,
                                         ksinr: int | None = None) -> list[dict]:
        """Kommende TOPs ohne Kartentext — samt allem, was das Modell sehen soll.

        Nur nach VORN. Der Text steht in einer Vorschau; für vergangene
        Sitzungen gibt es später den Beschluss.

        Mit ``ksinr`` genau EINE Sitzung, dann ohne Zeitfenster: Der Aufrufer
        hat sie schon in der Hand (die Tagesordnungs-Mail, sobald eine neue
        Tagesordnung erscheint), und ihr Termin kann weiter als drei Wochen
        entfernt liegen.

        Und sonst: **jeder inhaltliche Punkt**. Die Deckelung auf Tragweite
        ≥ 40 stammte aus dem Bild-Kanal — dort kommen von 97 öffentlichen
        TOPs einer Woche rund 20 auf eine Karte, der Rest wäre bezahlt und
        nie gelesen. Im Web wird jede Tagesordnung ganz gelesen, und dort
        stand unter den anderen 75 die titelbasierte Kurzfassung oder nichts
        (Tims Entscheidung 30.08.26). Ein Aufruf kostet Bruchteile eines
        Cents; die Deckelung war fürs Bild gedacht, nicht fürs Budget.

        Die Routine bleibt trotzdem draußen — „Feststellung der
        Beschlussfähigkeit" braucht keinen Text; dafür sorgt derselbe
        ``_FORMALIE_RE`` wie im Tragweite-Lauf. Und eine Bewertung ist keine
        Bedingung mehr, sondern nur noch die Reihenfolge: Was hoch bewertet
        ist, kommt zuerst dran, Unbewertetes danach.

        Der Vorlagentext kommt UNGEKÜRZT (die Auswahl trifft
        social_text.kontext, die kennt die Budgets); die Anlagen holt der
        Aufrufer über anlagen_fuer.
        """
        from datetime import date, timedelta

        heute = date.today().isoformat()
        bis = (date.today() + timedelta(days=tage_voraus)).isoformat()
        if ksinr is not None:
            heute, bis = "0000-00-00", "9999-99-99"
        sql = """SELECT a.ksinr, a.item_number, a.title, a.kvonr, a.template_number,
                        cs.committee, cs.session_date,
                        v.kind, v.office, v.proposed_decision, v.financial_impact,
                        v.climate_impact, v.raw_text,
                        i.impact,
                        -- Dringlichkeitsanträge haben keine Vorlage; ihr
                        -- ganzer Inhalt steht in dem PDF, das an der Zeile
                        -- hängt. Der Lauf holt es über diese URL nach.
                        (SELECT an.url FROM council_agenda_attachments an
                          WHERE an.ksinr = a.ksinr AND an.item_number = a.item_number
                          LIMIT 1) AS anlage_url,
                        (SELECT an.raw_text FROM council_agenda_attachments an
                          WHERE an.ksinr = a.ksinr AND an.item_number = a.item_number
                            AND an.raw_text IS NOT NULL LIMIT 1) AS anlage_text
                 FROM council_agenda_items a
                 JOIN council_sessions cs ON cs.ksinr = a.ksinr
                 LEFT JOIN agenda_item_impact i
                      ON i.ksinr = a.ksinr AND i.item_number = a.item_number
                 LEFT JOIN council_templates v ON v.kvonr = a.kvonr
                 LEFT JOIN agenda_item_social so
                        ON so.ksinr = a.ksinr AND so.item_number = a.item_number
                 WHERE a.is_public = 1 AND so.text IS NULL
                   AND COALESCE(i.impact, 0) >= ?
                   AND cs.session_date >= ? AND cs.session_date <= ?
                   AND a.title IS NOT NULL AND length(a.title) >= 8
                   -- Nur Punkte, zu denen es überhaupt etwas zu lesen gibt.
                   -- Ohne Vorlage und ohne Anlage sähe das Modell nur den
                   -- Titel — und einen Satz aus dem Titel allein gibt es
                   -- schon: die Kurzfassung. Ein zweiter wäre bezahlt und
                   -- nicht besser. Sie kommen im nächsten Lauf wieder,
                   -- sobald der Vorlagentext nachgeladen ist.
                   AND (v.raw_text IS NOT NULL OR v.proposed_decision IS NOT NULL
                        OR anlage_text IS NOT NULL)"""
        args: tuple = (mindest_wichtig, heute, bis)
        if ksinr is not None:
            sql += " AND a.ksinr = ?"
            args += (ksinr,)
        sql += " ORDER BY COALESCE(i.impact, -1) DESC, cs.session_date"
        roh = [dict(r) for r in self._conn.execute(sql, args)]
        # Formalien in Python heraus, nicht in SQL — dasselbe Muster wie in
        # `agenda_items_needing_impact`: Ein LIMIT vor dem Filter lieferte
        # sonst eine halb leere Liste, weil gut die Hälfte der Zeilen
        # „Genehmigung der Tagesordnung" heißt.
        echte = [r for r in roh if not self._FORMALIE_RE.search(r["title"] or "")]
        return echte[:limit] if limit is not None else echte

    def save_agenda_snapshot(self, ksinr: int, agenda_hash: str, items: list[dict]) -> None:
        """Öffentliche Tagesordnungspunkte zu diesem Hash einfrieren — die
        Vergleichsbasis für die Diff-Änderungsmeldung. INSERT OR IGNORE:
        Derselbe Stand wird nie überschrieben."""
        import json as _json
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO agenda_snapshots (ksinr, agenda_hash, items_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (ksinr, agenda_hash, _json.dumps(items, ensure_ascii=False), now))

    def get_agenda_snapshot(self, ksinr: int, agenda_hash: str) -> list[dict] | None:
        import json as _json
        row = self._conn.execute(
            "SELECT items_json FROM agenda_snapshots WHERE ksinr = ? AND agenda_hash = ?",
            (ksinr, agenda_hash)).fetchone()
        if row is None:
            return None
        try:
            return _json.loads(row[0])
        except ValueError:
            return None

    def get_latest_agenda_snapshot(self, ksinr: int) -> list[dict] | None:
        """Der jüngste eingefrorene Stand — die Vergleichsbasis der
        Änderungs-Chronik (unabhängig davon, wer benachrichtigt wurde)."""
        import json as _json
        row = self._conn.execute(
            "SELECT items_json FROM agenda_snapshots WHERE ksinr = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (ksinr,)).fetchone()
        if row is None:
            return None
        try:
            return _json.loads(row[0])
        except ValueError:
            return None

    def save_agenda_change(self, ksinr: int, diff: dict) -> None:
        """Eine erkannte Tagesordnungs-Änderung in die Chronik schreiben —
        die Sitzungsseite zeigt daraus „Zuletzt geändert"."""
        import json as _json
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO agenda_changes (ksinr, changed_at, diff_json) VALUES (?, ?, ?)",
                (ksinr, now, _json.dumps(diff, ensure_ascii=False)))

    def agenda_changes(self, ksinr: int, limit: int = 3) -> list[dict]:
        """Die jüngsten Änderungen einer Sitzung, neueste zuerst:
        ``[{changed_at, diff}]`` — der Diff in der Form von
        ``agenda_diff.diff_tagesordnung`` (Paare als 2er-Listen)."""
        import json as _json
        rows = self._conn.execute(
            "SELECT changed_at, diff_json FROM agenda_changes "
            "WHERE ksinr = ? ORDER BY id DESC LIMIT ?", (ksinr, limit)).fetchall()
        out: list[dict] = []
        for r in rows:
            try:
                out.append({"changed_at": r["changed_at"], "diff": _json.loads(r["diff_json"])})
            except ValueError:
                continue
        return out

    def save_summary(self, ksinr: int, agenda_hash: str, summary: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO committee_summaries (ksinr, agenda_hash, summary, created_at) VALUES (?, ?, ?, ?)",
                (ksinr, agenda_hash, summary, now),
            )

    def save_committees(self, committees: list[tuple[str, int | None]]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO committees (name, kgrnr) VALUES (?, ?)",
                [(name, kgrnr) for name, kgrnr in committees],
            )

    def get_all_committee_names(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM committees ORDER BY name"
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
        # Fallback: derive names from scraped sessions
        rows = self._conn.execute(
            "SELECT DISTINCT committee FROM council_sessions ORDER BY committee"
        ).fetchall()
        return [r[0] for r in rows]

    def agenda_summaries_for(self, ksinr: int) -> dict[str, str]:
        """{item_number: KI-Kurzfassung} einer Sitzung.

        Für TOPs ohne Vorlage ist die Kurzfassung die einzige Inhaltsangabe,
        die es gibt — und damit das einzige, woran die Themen-Zuordnung sich
        gegenprüfen lässt (siehe ``watcher._pruefe_am_text``).
        """
        return {r["item_number"]: r["summary"] for r in self._conn.execute(
            "SELECT item_number, summary FROM agenda_item_summaries WHERE ksinr = ?",
            (ksinr,)) if r["summary"]}

    def agenda_social_texts(self, ksinr: int) -> dict[str, str]:
        """{item_number: Kartentext} einer Sitzung (``agenda_item_social``).

        Der bessere der beiden Sätze: aus Vorlage UND Anlagen geschrieben,
        während die Kurzfassung nur den Titel kennt. Wer beides braucht, nimmt
        ``agenda_items`` — das legt sie nebeneinander an jeden Punkt.
        """
        return {r["item_number"]: r["text"] for r in self._conn.execute(
            "SELECT item_number, text FROM agenda_item_social WHERE ksinr = ?",
            (ksinr,)) if r["text"]}

    def agenda_wichtigkeit(self, ksinr: int) -> dict[str, int]:
        """{item_number: Tragweite 0–100} einer Sitzung (``agenda_item_impact``).

        Nur die bewerteten Punkte — wo nichts steht, steht auch hier nichts;
        eine geratene Null wäre eine Aussage, die niemand getroffen hat. Der
        Aufrufer (die Tagesordnungs-Mail) hebt danach die stärksten Punkte
        hervor.

        Die beiden lesezeitigen Korrekturen der Wochen-Karte gelten mit,
        sonst hieße derselbe Punkt an zwei Stellen verschieden wichtig:
        ``formalakt_deckel`` drückt Widmung/Einziehung/Umstufung nach unten,
        ``dringlichkeits_boden`` hebt Dringlichkeitsanträge an.
        """
        from council.impact import dringlichkeits_boden, formalakt_deckel  # noqa: PLC0415

        out: dict[str, int] = {}
        for r in self._conn.execute(
                "SELECT i.item_number, i.impact, a.title FROM agenda_item_impact i "
                "LEFT JOIN council_agenda_items a "
                "       ON a.ksinr = i.ksinr AND a.item_number = i.item_number "
                "WHERE i.ksinr = ? AND i.impact IS NOT NULL", (int(ksinr),)):
            wert = int(r["impact"])
            deckel = formalakt_deckel(r["title"])
            if deckel is not None and wert > deckel:
                wert = deckel
            boden = dringlichkeits_boden(r["item_number"])
            if boden is not None and wert < boden:
                wert = boden
            out[r["item_number"]] = wert
        return out

    def agenda_items(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT item_number, title, template_number, kvonr, is_public
               FROM council_agenda_items WHERE ksinr = ?
               ORDER BY id""",
            (ksinr,),
        ).fetchall()
        out = [dict(r) for r in rows]
        # Anhänge je TOP dazulegen (Tims Befund 12.08.) — ein Query, gruppiert.
        anl: dict[str, list[dict]] = {}
        for r in self._conn.execute(
                "SELECT item_number, label, url FROM council_agenda_attachments "
                "WHERE ksinr = ? ORDER BY id", (ksinr,)):
            anl.setdefault(r["item_number"], []).append({"label": r["label"], "url": r["url"]})
        zus = {r["item_number"]: r["summary"] for r in self._conn.execute(
            "SELECT item_number, summary FROM agenda_item_summaries WHERE ksinr = ?", (ksinr,))}
        # Der bessere der beiden Texte, wo es ihn gibt (agenda_item_social):
        # Er kennt Vorlage UND Anlagen, während `summary` allein aus dem Titel
        # entsteht („Du kennst nur den Titel des Punktes" steht wörtlich in
        # deren Prompt). Beide fahren mit — der Aufrufer entscheidet, aber die
        # Reihenfolge steht hier fest, damit Web und iOS dieselbe wählen.
        kartentext = {r["item_number"]: r["text"] for r in self._conn.execute(
            "SELECT item_number, text FROM agenda_item_social WHERE ksinr = ?", (ksinr,))}
        from .dringlichkeit import ist_dringlichkeitsantrag  # noqa: PLC0415 — Ringschluss

        for item in out:
            item["anlagen"] = anl.get(item["item_number"], [])
            item["summary"] = zus.get(item["item_number"])
            item["social_text"] = kartentext.get(item["item_number"])
            # Ein abgeleiteter Punkt, kein amtlicher (council/dringlichkeit.py).
            # Das Flag entscheidet hier und nicht im Frontend, damit Web und
            # App denselben Punkt hervorheben.
            item["dringlich"] = ist_dringlichkeitsantrag(item["item_number"])
        return out

    def sitzungen_am_monatstag(self, monat_tag: str, limit: int = 8) -> list[dict]:
        """Sitzungen an einem Monatstag (``"-06-17"``) über alle Jahre, neueste
        zuerst — löst Fragen mit Datum ohne Jahr („am 17.06.") auf
        (Sitzungs-Fragetyp der KI-Frage, ``qa.finde_sitzungen``)."""
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM council_sessions WHERE session_date LIKE ? "
            "ORDER BY session_date DESC LIMIT ?", (f"%{monat_tag}", int(limit)))]

    def decision_ids_der_sitzung(self, ksinr: int) -> list[int]:
        """Beschluss-ids einer Sitzung in Tagesordnungs-Reihenfolge, ohne
        Subvotes (die hängen als Kontext am Hauptbeschluss). Sitzungs-Fragetyp
        der KI-Frage: die Sitzung kommt damit VOLLSTÄNDIG in den Kontext."""
        return [r[0] for r in self._conn.execute(
            "SELECT id FROM council_decisions WHERE ksinr = ? AND kind = 'decision' "
            "ORDER BY position", (int(ksinr),))]

    def known_session_ids(self, ksinrs: list[int]) -> set[int]:
        """Welche dieser Sitzungs-IDs kennen wir schon? Für den Nachlauf im
        Watcher, der den Kalender rückwärts liest: Von den Sitzungen der letzten
        Monate ist fast alles längst da, und jede einzelne Seite noch einmal zu
        holen wären Dutzende Abrufe je Lauf für nichts."""
        if not ksinrs:
            return set()
        platz = ",".join("?" * len(ksinrs))
        return {r[0] for r in self._conn.execute(
            f"SELECT ksinr FROM council_sessions WHERE ksinr IN ({platz})",
            [int(k) for k in ksinrs])}

    def get_session(self, ksinr: int) -> dict | None:
        row = self._conn.execute(
            """SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                      COUNT(ci.id) AS n_items
               FROM council_sessions cs
               LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
               WHERE cs.ksinr = ?
               GROUP BY cs.ksinr""",
            (ksinr,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _session_where(query: str, committee: str, date_from: str, date_to: str) -> tuple[str, list]:
        """Filter der Sitzungssuche — eine Quelle für Liste UND Zählung. Liefen
        die auseinander, zeigte die Blätterleiste eine andere Menge an, als die
        Seiten hergeben (Muster wie _decision_where)."""
        filters: list[str] = []
        params: list = []
        if query:
            filters.append(
                """(cs.committee LIKE ? OR cs.ksinr IN (
                       SELECT ksinr FROM council_agenda_items
                       WHERE title LIKE ? OR template_number LIKE ?))"""
            )
            like = f"%{query}%"
            params += [like, like, like]
        if committee:
            filters.append("cs.committee = ?")
            params.append(committee)
        if date_from:
            filters.append("cs.session_date >= ?")
            params.append(date_from)
        if date_to:
            filters.append("cs.session_date <= ?")
            params.append(date_to)
        return ("WHERE " + " AND ".join(filters)) if filters else "", params

    def count_sessions(self, query: str = "", committee: str = "",
                       date_from: str = "", date_to: str = "") -> int:
        where, params = self._session_where(query, committee, date_from, date_to)
        # Ohne den Agenda-Join: der GROUP BY der Liste faltet ihn ohnehin wieder
        # auf eine Zeile je Sitzung zusammen.
        return self._conn.execute(
            f"SELECT COUNT(*) FROM council_sessions cs {where}", params
        ).fetchone()[0]

    def search_sessions(
        self,
        query: str = "",
        committee: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Search sessions by committee name or agenda item text. Empty query lists by date."""
        where, params = self._session_where(query, committee, date_from, date_to)
        params = [*params, limit, offset]
        rows = self._conn.execute(
            f"""SELECT cs.ksinr, cs.committee, cs.session_date, cs.session_time, cs.location,
                       COUNT(ci.id) AS n_items
                FROM council_sessions cs
                LEFT JOIN council_agenda_items ci ON ci.ksinr = cs.ksinr
                {where}
                GROUP BY cs.ksinr
                ORDER BY cs.session_date DESC
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()
        sessions = [dict(r) for r in rows]
        # When searching by text, attach the agenda items that match the query so
        # the UI can show them inline (and highlight them) without a second fetch.
        if query and sessions:
            ksinrs = [s["ksinr"] for s in sessions]
            placeholders = ",".join("?" * len(ksinrs))
            like = f"%{query}%"
            matched = self._conn.execute(
                f"""SELECT ksinr, item_number, title, template_number, kvonr, is_public
                    FROM council_agenda_items
                    WHERE ksinr IN ({placeholders}) AND (title LIKE ? OR template_number LIKE ?)
                    ORDER BY ksinr, id""",
                [*ksinrs, like, like],
            ).fetchall()
            by_ksinr: dict[int, list[dict]] = {}
            for r in matched:
                d = dict(r)
                by_ksinr.setdefault(d.pop("ksinr"), []).append(d)
            for s in sessions:
                s["matched_items"] = by_ksinr.get(s["ksinr"], [])
        return sessions

    def has_protocol(self, ksinr: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM council_protocols WHERE ksinr = ? AND status = 'ok'", (ksinr,)
        ).fetchone()
        return row is not None

    def beschlusszahl_je_gremium(self, date_from: str) -> dict[str, int]:
        """Beschlüsse je Gremium ab ``date_from`` (ISO-Datum) — für die
        Ausschuss-Abos, die je Gremium „x Beschlüsse in diesem Jahr" zeigen.

        Gezählt wird nur ``kind = 'decision'``: Änderungsanträge
        (``kind = 'subvote'``) sind keine eigenen Beschlüsse, sondern hängen
        als Kontext am Ursprungsbeschluss (Design 23a) — genau so zählt auch
        ``count_decisions`` in seiner Standardform (``include_subvotes=False``).
        Zählte man sie mit, stünde neben dem Gremium eine höhere Zahl, als die
        verlinkte Beschlussliste hergibt.

        Bewusst EINE Abfrage mit ``GROUP BY`` statt eines ``count_decisions``
        je Gremium: Die Seite lädt die Liste bei jedem Aufruf, und es sind rund
        15 Gremien. Gremien ohne Beschluss fehlen im dict (der Aufrufer setzt 0).
        """
        rows = self._conn.execute(
            """SELECT cs.committee AS committee, COUNT(*) AS n
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision' AND cs.session_date >= ?
               GROUP BY cs.committee""",
            (date_from,),
        ).fetchall()
        return {r["committee"]: r["n"] for r in rows}

    def _wiederkehr(self) -> dict[str, int]:
        """Wie oft stand dieselbe Formulierung schon auf einer Tagesordnung?

        Das Signal, das jedem Modell fehlt: „Annahme von Zuwendungen durch den
        Rat" kam 101× vor, die Haushaltssatzung 3× (einmal im Jahr). Ohne den
        Zähler hält ein Sprachmodell den Zuwendungs-Punkt für eine
        Geldentscheidung — er ist aber Verwaltungsalltag (Tim, 15.08.).
        """
        if getattr(self, "_wiederkehr_cache", None) is None:
            zaehler: dict[str, int] = {}
            for (title,) in self._conn.execute(
                    "SELECT title FROM council_agenda_items "
                    "WHERE is_public = 1 AND title IS NOT NULL"):
                key = self._wiederkehr_schluessel(title)
                if key:
                    zaehler[key] = zaehler.get(key, 0) + 1
            self._wiederkehr_cache = zaehler
        return self._wiederkehr_cache

    @classmethod
    def _wiederkehr_schluessel(cls, title: str | None) -> str:
        roh = cls._WIEDERKEHR_UNWICHTIG.sub(" ", (title or "").lower())
        roh = re.sub(r"\d+", "#", roh)
        return " ".join(re.sub(r"[^a-zäöüß# ]+", " ", roh).split())

    def agenda_items_needing_impact(self, limit: int | None = None,
                                    tage_voraus: int = 21,
                                    ksinr: int | None = None) -> list[dict]:
        """Öffentliche Tagesordnungspunkte kommender Sitzungen ohne Tragweite.

        Nur nach vorn: Die Wochen-Karte schaut voraus, und für vergangene
        Sitzungen gibt es später den Beschluss samt eigener Bewertung. Der
        Auszug kommt aus der Kurzfassung, ersatzweise aus dem Vorlagentext —
        beides liegt vor der Sitzung vor.

        Mit ``ksinr`` genau EINE Sitzung, dann ohne Zeitfenster — dieselbe
        Ausnahme wie bei ``agenda_items_needing_social_text`` und aus demselben
        Grund: Die Tagesordnungs-Mail hebt die wichtigsten Punkte hervor und
        braucht deren Bewertung, sobald die Tagesordnung erscheint. Der
        Tranchen-Lauf am Ende von ``check_committees`` käme dafür zu spät (er
        steht hinter der Meldeschleife), und eine Tagesordnung kann auch mehr
        als drei Wochen vor dem Termin veröffentlicht werden.
        """
        from datetime import date, timedelta

        heute = date.today().isoformat()
        bis = (date.today() + timedelta(days=tage_voraus)).isoformat()
        if ksinr is not None:
            heute, bis = "0000-00-00", "9999-99-99"
        sql = """SELECT a.ksinr, a.item_number, a.title, a.template_number, a.kvonr,
                        s.summary, cs.committee, cs.session_date,
                        v.proposed_decision, v.financial_impact, v.office, v.kind,
                        (SELECT COUNT(*) FROM council_deliberations b WHERE b.kvonr = a.kvonr)
                            AS stationen,
                        -- Großzügig: Die ersten ~300 Zeichen sind Briefkopf,
                        -- den `impact.vorlagen_kern` abschneidet. Bei 1200
                        -- blieb danach zu wenig Inhalt übrig.
                        -- Dringlichkeitsanträge haben keine Vorlage; ihr Text
                        -- steht am Zeilen-Dokument. Ohne dieses COALESCE
                        -- bewertete das Modell den Dateinamen — der
                        -- PAK-Antrag vom 31.08.26 kam so auf 55 und verpasste
                        -- die Karte, obwohl im PDF eine Schadstoffbelastung
                        -- eines Gewässers und Sofortmaßnahmen standen.
                        COALESCE(substr(v.raw_text, 1, 2500),
                                 (SELECT substr(an.raw_text, 1, 2500)
                                    FROM council_agenda_attachments an
                                   WHERE an.ksinr = a.ksinr
                                     AND an.item_number = a.item_number
                                     AND an.raw_text IS NOT NULL
                                   LIMIT 1)) AS sachverhalt
                 FROM council_agenda_items a
                 JOIN council_sessions cs ON cs.ksinr = a.ksinr
                 LEFT JOIN agenda_item_summaries s
                        ON s.ksinr = a.ksinr AND s.item_number = a.item_number
                 LEFT JOIN council_templates v ON v.kvonr = a.kvonr
                 LEFT JOIN agenda_item_impact i
                        ON i.ksinr = a.ksinr AND i.item_number = a.item_number
                 WHERE a.is_public = 1 AND i.impact IS NULL
                   AND cs.session_date >= ? AND cs.session_date <= ?
                   AND a.title IS NOT NULL AND length(a.title) >= 8"""
        args: tuple = (heute, bis)
        if ksinr is not None:
            sql += " AND a.ksinr = ?"
            args += (ksinr,)
        sql += " ORDER BY cs.session_date, a.id"
        if limit is not None:
            # Großzügig holen und ERST danach kürzen: Die Formalien fliegen in
            # Python raus, und von 20 Zeilen sind gut die Hälfte „Genehmigung
            # der Tagesordnung" — ein SQL-LIMIT lieferte sonst eine halb leere
            # Tranche.
            sql += " LIMIT ?"
            args += (limit * 3,)
        roh = [dict(r) for r in self._conn.execute(sql, args).fetchall()]
        # Formalien kosten nur Geld — dieselbe Regel wie in der Wochen-Karte.
        echte = [r for r in roh if not self._FORMALIE_RE.search(r["title"] or "")]
        zaehler = self._wiederkehr()
        for r in echte:
            r["wiederkehr"] = zaehler.get(self._wiederkehr_schluessel(r["title"]), 1)
            r["applicants"], _ = self._titel_zerlegen(r["title"] or "")
            series = [dict(b) for b in self._conn.execute(
                "SELECT date, result FROM council_deliberations WHERE kvonr = ? ORDER BY date",
                (r["kvonr"] or 0,))]
            heutige = next((b for b in series if b["date"] == r["session_date"]), None)
            r["behandlung"] = (heutige or {}).get("result")
        return echte[:limit] if limit is not None else echte

    def save_agenda_impact(self, ksinr: int, item_number: str,
                           score: int, reason: str | None) -> None:
        from datetime import datetime, timezone

        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO agenda_item_impact "
                "(ksinr, item_number, impact, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (ksinr, item_number, max(0, min(100, int(score))), reason,
                 datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )

    def session_dates_fuer(self, decision_ids: list[int]) -> dict[int, str]:
        """id → session_date (ISO) — für den Recency-Bonus im Ranking."""
        if not decision_ids:
            return {}
        ph = ",".join("?" * len(decision_ids))
        rows = self._conn.execute(
            f"SELECT d.id, cs.session_date FROM council_decisions d "
            f"JOIN council_sessions cs ON cs.ksinr = d.ksinr WHERE d.id IN ({ph})",
            decision_ids).fetchall()
        return {r["id"]: r["session_date"] for r in rows if r["session_date"]}

    def committee_names(self) -> set[str]:
        """Lower-cased committee names — used to keep bodies out of the topic graph."""
        return {(r[0] or "").strip().lower()
                for r in self._conn.execute("SELECT name FROM committees") if r[0]}

    def juengste_sitzungen_mit_beschluessen(self, limit: int = 2) -> list[dict]:
        """Die jüngsten vergangenen Sitzungen, zu denen Beschlüsse extrahiert
        sind — Futter für frische KI-Beispielfragen (5a/I-07). ``top_titel``
        nennt den wichtigsten Beschluss der Sitzung, damit ein Vorschlag
        konkret nach dem Inhalt fragen kann statt nur nach dem Datum."""
        rows = self._conn.execute(
            """SELECT cs.committee, cs.session_date, COUNT(*) AS n,
                      (SELECT d2.title FROM council_decisions d2
                       WHERE d2.ksinr = cs.ksinr AND d2.kind = 'decision'
                         AND d2.title IS NOT NULL
                       ORDER BY COALESCE(d2.importance, 0) DESC, d2.id LIMIT 1) AS top_titel
               FROM council_decisions d
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.kind = 'decision'
               GROUP BY d.ksinr ORDER BY cs.session_date DESC LIMIT ?""",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
