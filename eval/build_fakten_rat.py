#!/usr/bin/env python3
"""Baut ``eval/cases_fakten_rat.json``: Faktenfragen an Frag den Rat und Lotti
außerhalb des Haushalts — mit Goldwerten aus der Datenbank.

    python eval/build_fakten_rat.py                        # schreibt die Fälle
    python eval/build_fakten_rat.py --pruefen              # vergleicht nur, schreibt nicht
    python eval/build_fakten_rat.py --stichtag 2026-09-23  # „nächste Sitzung" ab diesem Tag

**Wozu.** Der Faktencheck vom 23.09.2026 hat 14 Antworten Satz für Satz
geprüft und dabei zwei Sorten Fehler gefunden, die sich mit bloßem Hinsehen
nicht auseinanderhalten lassen: Das Modell hat etwas verdreht — oder der
Kontext hat es ihm falsch hingelegt. Die Eval (``eval/run_fakten.py``) misst
beides getrennt; dafür braucht jeder Fall Goldfakten, die man im
mitgeschnittenen Prompt UND in der Antwort suchen kann. Das Format steht in
der Spezifikation (``kanal``, ``frage``, ``gold`` mit ``art`` zahl/text/id,
``verboten``, ``quelle``) und ist für Haushalts- und Ratsfälle dasselbe.

**Woher die Goldwerte kommen.** Aus ``data/council.sqlite``, nie aus einer
Modellantwort. Jeder Fall schlägt seinen Beschluss über einen NATÜRLICHEN
Schlüssel nach (Gremium, Sitzungstag, Titelstück oder Vorlagennummer), nicht
über die Zeilen-ID: Die IDs sind je Datenbank verschieden (dev und Prod
zählen getrennt, s. ``eval/cases_qa.json`` mit ``expected_keys``). Der
Baukasten löst den Schlüssel gegen die offene Datenbank auf, prüft mit
:func:`erwarte` den Sachverhalt, auf dem der Fall beruht („abgelehnt",
„18 Gegenstimmen") — und bricht ab, wenn die Daten ihn nicht mehr tragen.
Ein stiller Goldwert, der nach einem Nachimport nicht mehr stimmt, wäre
schlimmer als gar keiner.

**Was ``text`` heißt.** ``muss`` ist eine Liste von Pflichtstücken; ein Stück
ist entweder ein Wort oder eine Liste gleichwertiger Schreibweisen
(``[["Grüne", "Grünen"]]``). Datumsangaben stehen als Text mit allen
Schreibweisen, in denen sie im Kontext (``01.06.2026`` in Frag den Rat,
``1. Juni 2026`` in Lottis Beschluss-Block, ``2026-06-01`` in Lottis
Sitzungs-Block) oder in einer Antwort vorkommen.

**Was ``verboten`` heißt.** Nur Zahlen, die in einer richtigen Antwort nicht
stehen dürfen — die Bürgschaft für die Kramermarktfläche als Bürgschaft für
die Kongresshalle, der Zuschuss für 2026 als der für 2027. Eine Zahl, die man
richtig als Vorgeschichte nennen kann (der Hebesatz vor der Reform), gehört
NICHT hierher, sonst bestraft der Abgleich die gründlichere Antwort.

**Fälle mit ``antwort_in_daten: false``** tragen kein Gold: Richtig ist,
zu sagen, dass die Daten es nicht hergeben. Jeder dieser Fälle ist gegen
Beschlüsse, Vorlagen, Pressemitteilungen und Wortbeiträge gegengeprüft (s.
``notiz``) — eine Frage, deren Antwort doch irgendwo steht, wäre ein falscher
Befund gegen das Modell.

**Lotti-Fälle** fragen so, dass sie beim Modell ankommen: kein „Was sehe ich
hier?" (das beantwortet Lotti ohne Modell) und keine Archivfrage ohne „hier"
(die reicht Lotti sofort an Frag den Rat weiter, ``archiv_sofort``).
``tests/test_fakten_rat_faelle.py`` hält beides fest.

**Zeitabhängig** sind nur die Fälle mit ``--stichtag`` (nächste Sitzung):
Sie werden beim Neubauen gegen den Stichtag neu gezogen und sagen das in der
``notiz``.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FAELLE = WURZEL / "eval" / "cases_fakten_rat.json"
DB_STANDARD = WURZEL / "data" / "council.sqlite"

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")


class BaukastenFehler(RuntimeError):
    """Die Daten tragen einen Fall nicht mehr — nachsehen, nicht überspringen."""


def erwarte(bedingung: bool, was: str) -> None:
    if not bedingung:
        raise BaukastenFehler(was)


# --------------------------------------------------------------------------- #
# Nachschlagen
# --------------------------------------------------------------------------- #

class Quelle:
    """Die Abfragen, aus denen jeder Goldwert stammt — eine Stelle, prüfbar."""

    def __init__(self, pfad: Path, stichtag: str):
        self.conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.stichtag = stichtag

    def beschluss(self, gremium: str, datum: str, *, titel: str | None = None,
                  vorlage: str | None = None, top: str | None = None) -> dict:
        sql = ("SELECT d.*, s.committee, s.session_date FROM council_decisions d "
               "JOIN council_sessions s USING(ksinr) "
               "WHERE s.committee = ? AND s.session_date = ? AND d.kind = 'decision'")
        params: list = [gremium, datum]
        if titel:
            sql += " AND d.title LIKE ?"
            params.append(f"%{titel}%")
        if vorlage:
            sql += " AND d.template_number = ?"
            params.append(vorlage)
        if top:
            sql += " AND d.item_number = ?"
            params.append(top)
        rows = [dict(r) for r in self.conn.execute(sql, params)]
        erwarte(len(rows) == 1, f"Beschluss {gremium} {datum} {titel or vorlage or top}: "
                                f"{len(rows)} Treffer statt 1")
        return rows[0]

    def vorlage(self, nummer: str) -> dict:
        r = self.conn.execute("SELECT * FROM council_templates WHERE template_number = ?",
                              (nummer,)).fetchone()
        erwarte(r is not None, f"Vorlage {nummer} fehlt")
        return dict(r)

    def presse(self, datum: str, titel: str) -> dict:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM council_press WHERE date = ? AND title LIKE ?", (datum, f"%{titel}%"))]
        erwarte(len(rows) == 1, f"Pressemitteilung {datum} „{titel}“: {len(rows)} Treffer")
        return rows[0]

    def sitzung(self, gremium: str, datum: str) -> dict:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM council_sessions WHERE committee = ? AND session_date = ?",
            (gremium, datum))]
        erwarte(len(rows) == 1, f"Sitzung {gremium} {datum}: {len(rows)} Treffer")
        return rows[0]

    def beschluesse_der_sitzung(self, ksinr: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM council_decisions WHERE ksinr = ? AND kind = 'decision'", (ksinr,))]

    def naechste_sitzung(self, gremium: str) -> dict:
        """Erster Termin NACH dem Stichtag — aus beiden Kalendern.

        ``council_sessions`` trägt die Sitzungen mit Kennung (bis wenige
        Wochen voraus), ``council_scheduled_sessions`` den Jahreskalender
        ohne Kennung. Frag den Rat liest beide (``store.upcoming_sessions``).
        """
        rows = [dict(r) for r in self.conn.execute(
            "SELECT committee, session_date, session_time, location, 'council_sessions' AS tabelle "
            "FROM council_sessions WHERE committee = ? AND session_date > ? "
            "UNION ALL SELECT committee, session_date, session_time, location, "
            "'council_scheduled_sessions' FROM council_scheduled_sessions "
            "WHERE committee = ? AND session_date > ? ORDER BY session_date, tabelle",
            (gremium, self.stichtag, gremium, self.stichtag))]
        erwarte(bool(rows), f"keine Sitzung {gremium} nach {self.stichtag}")
        return rows[0]

    def tagesordnungspunkt(self, ksinr: int, titel: str) -> dict:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM council_agenda_items WHERE ksinr = ? AND title LIKE ?",
            (ksinr, f"%{titel}%"))]
        erwarte(len(rows) == 1, f"TOP „{titel}“ in Sitzung {ksinr}: {len(rows)} Treffer")
        return rows[0]

    def person(self, name: str) -> dict:
        r = self.conn.execute("SELECT * FROM council_persons WHERE name = ?", (name,)).fetchone()
        erwarte(r is not None, f"Person {name} fehlt")
        return dict(r)

    def mitgliedschaften(self, name: str) -> list[dict]:
        """Laufende Mitgliedschaften am Stichtag (``valid_until`` leer oder später)."""
        return [dict(r) for r in self.conn.execute(
            "SELECT m.* FROM council_memberships m JOIN council_persons p USING(kpenr) "
            "WHERE p.name = ? AND (m.valid_until IS NULL OR m.valid_until > ?)",
            (name, self.stichtag))]

    def vorsitz(self, gremium: str) -> dict:
        rows = [dict(r) for r in self.conn.execute(
            "SELECT m.*, p.name, p.current_faction FROM council_memberships m "
            "JOIN council_persons p USING(kpenr) "
            "WHERE m.committee = ? AND m.role = 'Ausschussvorsitzende/r' "
            "AND (m.valid_until IS NULL OR m.valid_until > ?)", (gremium, self.stichtag))]
        erwarte(len(rows) == 1, f"Vorsitz {gremium}: {len(rows)} laufende Einträge")
        return rows[0]

    def hebesatz(self, art: str, jahr: int) -> dict:
        r = self.conn.execute("SELECT * FROM council_tax_rates WHERE kind = ? AND year = ?",
                              (art, jahr)).fetchone()
        erwarte(r is not None, f"Hebesatz {art} {jahr} fehlt")
        return dict(r)

    def beschluesse_am_ort(self, place_id: str) -> list[dict]:
        """Wie ``store.decision_ids_for_place`` — über den echten Store, damit
        die Ortszuordnung dieselbe ist, die Frag den Rat und die Ortsseite
        benutzen (Aliase, Mehrfach-Zugehörigkeit)."""
        from council.store import CouncilStore
        store = CouncilStore(self._pfad())
        return store.get_decisions_by_ids(store.decision_ids_for_place(place_id))

    def _pfad(self) -> str:
        return self.conn.execute("PRAGMA database_list").fetchone()["file"]


# --------------------------------------------------------------------------- #
# Goldwerte
# --------------------------------------------------------------------------- #

def datum_varianten(iso: str) -> list[str]:
    j, m, t = (int(x) for x in iso[:10].split("-"))
    return list(dict.fromkeys([
        f"{t:02d}.{m:02d}.{j}", f"{t}.{m}.{j}", f"{t}. {MONATE[m - 1]} {j}",
        f"{t:02d}. {MONATE[m - 1]} {j}", iso[:10]]))


def g_datum(iso: str, quelle: str) -> dict:
    return {"art": "text", "muss": [datum_varianten(iso)], "quelle": quelle}


def g_zahl(wert: float, einheit: str, bezeichnung: str, quelle: str, *,
           jahr: int | None = None, toleranz: float = 0.0) -> dict:
    g: dict = {"art": "zahl", "wert": wert, "einheit": einheit}
    if jahr is not None:
        g["jahr"] = jahr
    g.update({"bezeichnung": bezeichnung, "toleranz": toleranz, "quelle": quelle})
    return g


def g_text(muss: list, quelle: str) -> dict:
    return {"art": "text", "muss": muss, "quelle": quelle}


def g_id(d: dict) -> dict:
    return {"art": "id", "wert": d["id"], "quelle": q_beschluss(d)}


def v_zahl(wert: float, grund: str) -> dict:
    return {"art": "zahl", "wert": wert, "grund": grund}


#: Wie ein Ergebnis in einer Antwort heißen kann. Frag den Rat bekommt das
#: Ergebnis als Schlüssel (``accepted``), Lotti als Wort (``angenommen``) —
#: der Abgleich auf den Kontext sucht deshalb auch den Schlüssel.
ERGEBNIS_WOERTER = {
    "accepted": ["angenommen", "beschlossen", "zugestimmt", "beschloss", "Zustimmung", "accepted"],
    "rejected": ["abgelehnt", "lehnte", "Ablehnung", "rejected"],
    "postponed": ["vertagt", "verschoben", "abgesetzt", "postponed"],
    "noted": ["zur Kenntnis", "Kenntnis genommen", "noted"],
}


def q_beschluss(d: dict, spalte: str = "") -> str:
    teile = [f"council_decisions id={d['id']}", f"{d['committee']} {d['session_date']}"]
    if d.get("item_number"):
        teile.append(f"TOP {d['item_number']}")
    if d.get("template_number"):
        teile.append(f"Vorlage {d['template_number']}")
    return ", ".join(teile) + (f"; {spalte}" if spalte else "")


def g_ergebnis(d: dict) -> dict:
    return g_text([ERGEBNIS_WOERTER[d["outcome"]]], q_beschluss(d, f"outcome={d['outcome']}"))


def g_sitzungsdatum(d: dict) -> dict:
    return g_datum(d["session_date"], q_beschluss(d, "council_sessions.session_date"))


def g_gegenstimmen(d: dict) -> dict:
    erwarte(bool(d.get("no_votes")), f"{d['id']}: keine Gegenstimmen erfasst")
    return g_zahl(d["no_votes"], "Gegenstimmen", "Gegenstimmen", q_beschluss(d, "no_votes"))


def g_enthaltungen(d: dict) -> dict:
    erwarte(bool(d.get("abstentions")), f"{d['id']}: keine Enthaltungen erfasst")
    return g_zahl(d["abstentions"], "Enthaltungen", "Enthaltungen", q_beschluss(d, "abstentions"))


def q_presse(p: dict) -> str:
    return f"council_press id={p['id']} ({p['date']}, „{p['title']}“)"


def q_vorlage(v: dict, spalte: str = "financial_impact") -> str:
    return f"council_templates {v['template_number']} (kvonr={v['kvonr']}); {spalte}"


def fall(id: str, kanal: str, frage: str, kategorie: str, gold: list, *,
         route: str | None = None, refs: dict | None = None, antwort_in_daten: bool = True,
         verboten: list | None = None, notiz: str = "") -> dict:
    f: dict = {"id": id, "kanal": kanal}
    if kanal == "lotti":
        f["route"] = route
        f["refs"] = refs or {}
    f.update({"frage": frage, "kategorie": kategorie, "antwort_in_daten": antwort_in_daten,
              "gold": gold, "verboten": verboten or [], "notiz": notiz})
    return f


# --------------------------------------------------------------------------- #
# Die Fälle
# --------------------------------------------------------------------------- #

def stadion(q: Quelle) -> list[dict]:
    grundsatz = q.beschluss("Rat", "2024-04-15", vorlage="24/0158")
    erwarte("10.000 Besucherplätzen" in grundsatz["official_text"], "6705: 10.000 Plätze")
    planung = q.beschluss("Rat", "2023-02-27", vorlage="22/1006/1")
    erwarte("Aufnahme der Planung" in planung["official_text"], "5621: nur Planung")
    ek = q.beschluss("Rat", "2024-10-28", vorlage="24/0511/1")
    erwarte("bis zu 15 Millionen Euro" in ek["official_text"], "8659: 15 Mio. Eigenkapital")
    bau = q.beschluss("Rat", "2026-06-01", vorlage="26/0396")
    erwarte("57.339.000 Euro" in bau["official_text"] and "2.360.000 Euro" in bau["official_text"],
            "8677: Pauschalpreis und Baunebenkosten")
    erwarte(bau["no_votes"] == 18 and bau["abstentions"] == 2, "8677: 18 dagegen, 2 Enthaltungen")
    buergschaft = q.beschluss("Rat", "2026-06-01", vorlage="26/0374")
    erwarte("100 %igen Ausfallbürgschaften" in buergschaft["official_text"], "8679: 100 %")
    fvo = q.beschluss("Rat", "2026-06-01", titel="Totalunternehmers für den Neubau des Stadions")
    erwarte(fvo["outcome"] == "rejected" and fvo["no_votes"] == 31, "9330: abgelehnt, 31")
    bplan = q.beschluss("Rat", "2026-04-13", vorlage="26/0172")
    erwarte("als Satzung" in bplan["official_text"], "8540: Satzungsbeschluss")
    bplan_alt = q.beschluss("Rat", "2022-05-30", vorlage="22/0362")
    erwarte("Aufstellungsbeschluss" in bplan_alt["official_text"], "4851: Aufstellung")
    befragung = q.beschluss("Rat", "2026-02-23", titel="Einwohnerbefragung zur Finanzierung des Stadions")
    erwarte(befragung["outcome"] == "rejected", "8500: abgelehnt")
    wp26 = q.beschluss("Rat", "2025-12-15", vorlage="25/0850")
    erwarte("651.500 Euro" in wp26["official_text"], "8442: Fehlbetrag 2026")
    wp25 = q.beschluss("Rat", "2024-12-16", titel="Stadion Oldenburg GmbH & Co. KG: Wirtschaftsplan 2025")
    erwarte(wp25["amount_eur"] == 240000, "9208: 240.000 € 2025")
    vergabe = q.presse("2026-06-02", "Hellmich baut neue Arena")
    erwarte("Dagegen waren die Grünen sowie die Gruppe Für" in vergabe["text"].replace("\n", " "),
            "Presse 289: wer dagegen")
    erwarte("Hellmich" in vergabe["text"], "Presse 289: Totalunternehmer")
    eu = q.presse("2026-08-12", "EU und Kommunalaufsicht geben endgültig grünes Licht")
    erwarte("75 Millionen Euro" in eu["text"], "Presse 3112: 75 Mio. Beihilfen")
    erwarte("Ende 2028 beziehungsweise Anfang 2029" in eu["text"].replace("\n", " "),
            "Presse 3112: Fertigstellung")

    return [
        fall("rat-stadion-was-beschlossen", "rat",
             "Was hat der Rat zum Stadion an der Maastrichter Straße beschlossen?",
             "verlauf/stadion",
             [g_sitzungsdatum(grundsatz), g_sitzungsdatum(bau),
              g_zahl(57_339_000, "€", "Pauschalpreis Totalunternehmer netto",
                     q_beschluss(bau, "official_text"), toleranz=0.005),
              g_zahl(15_000_000, "€", "Eigenkapitalzuschuss der Stadt (bis zu)",
                     q_beschluss(ek, "official_text Ziff. 3"))],
             notiz="Faktencheck 23.09. (rat[0]): Beide Modelle ließen den Eigenkapitalzuschuss "
                   "von bis zu 15 Mio. € aus 8659 weg; Gemini ordnete die 50,4 Mio. € als "
                   "„Volumen“ ein (es ist die Kostengrenze für die Vergabe) und datierte eine "
                   "Rede in die falsche Sitzung."),
        fall("rat-stadion-kosten-wer-zahlt", "rat",
             "Wie viel kostet das neue Stadion und wer bezahlt es?",
             "beschluss/kosten",
             [g_zahl(57_339_000, "€", "Pauschalpreis netto", q_beschluss(bau, "official_text"),
                     toleranz=0.005),
              g_zahl(2_360_000, "€", "Baunebenkosten netto", q_beschluss(bau, "official_text"),
                     toleranz=0.01),
              g_zahl(15_000_000, "€", "Eigenkapitalzuschuss der Stadt (bis zu)",
                     q_beschluss(ek, "official_text Ziff. 3")),
              g_text([["Bürgschaft", "bürgt", "Ausfallbürgschaft"]],
                     q_beschluss(buergschaft, "official_text"))],
             notiz="Faktencheck rat[1]: Luna legte nahe, die Stadt zahle direkt nichts — 8659 "
                   "beschließt aber bis zu 15 Mio. € Eigenkapital. Fängt, ob 8659 überhaupt im "
                   "Kontext einer Kostenfrage landet."),
        fall("rat-stadion-grundsatzbeschluss", "rat",
             "Wann hat der Rat beschlossen, das Stadion an der Maastrichter Straße zu bauen?",
             "verwechslung/stadion",
             [g_sitzungsdatum(grundsatz),
              g_zahl(10_000, "Plätze", "Besucherplätze", q_beschluss(grundsatz, "official_text"))],
             notiz="Zwei ähnliche Beschlüsse: 27.02.2023 nur „Aufnahme der Planung“ (Varianten "
                   f"7.500/10.000 Plätze, id {planung['id']}), 15.04.2024 die Errichtung. Wer den "
                   "älteren als Baubeschluss nennt, hat verwechselt; ihn als Vorstufe zu nennen, "
                   "ist richtig — deshalb kein Verbot."),
        fall("rat-stadion-bplan-satzung", "rat",
             "Wann wurde der Bebauungsplan 831 für das Stadion als Satzung beschlossen?",
             "verwechslung/stadion",
             [g_sitzungsdatum(bplan)],
             notiz=f"Am 30.05.2022 (id {bplan_alt['id']}) fiel nur der Aufstellungsbeschluss; "
                   "dasselbe Planzeichen, vier Jahre früher."),
        fall("rat-stadion-wer-dagegen", "rat",
             "Welche Fraktionen haben im Juni 2026 gegen die Stadion-Vergabe gestimmt?",
             "beschluss/abstimmung",
             [g_text([["Grüne", "Grünen"], ["Für Oldenburg"]], q_presse(vergabe)),
              g_gegenstimmen(bau)],
             notiz="Das Protokoll nennt nur Zahlen (18 dagegen); WER dagegen war, steht allein in "
                   "der Pressemitteilung vom 02.06.2026. Falle: Die factions-Spalte von 8677 ist "
                   "[„CDU“] — das sind ANTRAGSTELLER (Kontext: „Antrag von: CDU“), keine "
                   "Gegenstimmen. Die CDU stimmte dafür, zwei Mitglieder enthielten sich."),
        fall("rat-stadion-baufirma", "rat",
             "Welche Firma baut das neue Stadion?",
             "beschluss/ergebnis",
             [g_text(["Hellmich"], q_presse(vergabe))],
             notiz="Der Beschluss 8677 nennt nur „den Totalunternehmer“; den Namen trägt die "
                   "Pressemitteilung."),
        fall("rat-stadion-eu-genehmigung", "rat",
             "Hat die EU-Kommission die Finanzierung des Stadions genehmigt?",
             "verlauf/stadion",
             [g_datum(eu["date"], q_presse(eu)),
              g_zahl(75_000_000, "€", "genehmigte Beihilfen", q_presse(eu))],
             notiz="Alle Ratsbeschlüsse vom 01.06.2026 stehen unter EU-Vorbehalt; die Auflösung "
                   "steht nur in der Presse (12.08.2026). Wer nur die Beschlüsse kennt, sagt "
                   "„noch offen“ — veraltet."),
        fall("rat-stadion-fertigstellung", "rat",
             "Wann soll das neue Stadion fertig sein?",
             "verlauf/stadion",
             [g_text(["2028", "2029"], q_presse(eu)),
              g_text([["1. Juli 2027", "01.07.2027", "Juli 2027"]], q_presse(eu))],
             notiz="Baubeginn 1. Juli 2027, Fertigstellung Ende 2028/Anfang 2029 — nur in "
                   "Pressemitteilungen (02.06., 05.06., 12.08.2026)."),
        fall("rat-stadion-einwohnerbefragung", "rat",
             "Gab es eine Einwohnerbefragung zum Stadion?",
             "verlauf/stadion",
             [g_ergebnis(befragung), g_sitzungsdatum(befragung), g_gegenstimmen(befragung)],
             notiz="Der Rat lehnte die Befragung zweimal ab (26.02.2024 als Teil eines "
                   "Grünen-Antrags, 23.02.2026 mit 27 Gegenstimmen); das Bürgerbegehren erklärte "
                   "der Verwaltungsausschuss am 11.05.2026 für unzulässig (nur Presse). Wer das "
                   "Bürgerbegehren für eine Befragung hält, verwechselt."),
        fall("rat-stadion-fehlbetrag-2026", "rat",
             "Mit welchem Fehlbetrag plant die Stadiongesellschaft im Jahr 2026?",
             "beschluss/kosten",
             [g_zahl(651_500, "€", "maximaler Fehlbetrag Wirtschaftsplan", q_beschluss(wp26, "official_text"),
                     jahr=2026)],
             verboten=[v_zahl(240_000, "Wirtschaftsplan 2025 (id "
                                       f"{wp25['id']}), nicht 2026")],
             notiz="Jahresfalle: Drei Wirtschaftspläne der Stadion GmbH & Co. KG stehen im Bestand "
                   "(2024: 190.000 €, 2025: 240.000 €, 2026: 651.500 €)."),
        fall("lotti-stadion-kosten", "lotti",
             "Wie viel kostet das Stadion laut diesem Beschluss?",
             "beschluss/kosten",
             [g_zahl(57_339_000, "€", "Pauschalpreis netto", q_beschluss(bau, "official_text"),
                     toleranz=0.005),
              g_zahl(2_360_000, "€", "Baunebenkosten netto", q_beschluss(bau, "official_text"),
                     toleranz=0.01)],
             route="/council/decision", refs={"decision_id": bau["id"]},
             notiz="Der Beschluss-Block trägt den amtlichen Wortlaut (600 Zeichen) — beide Zahlen "
                   "stehen darin."),
        fall("lotti-stadion-abstimmung", "lotti",
             "Wie knapp ist die Abstimmung hier ausgegangen?",
             "beschluss/abstimmung",
             [g_ergebnis(bau), g_gegenstimmen(bau), g_enthaltungen(bau)],
             route="/council/decision", refs={"decision_id": bau["id"]},
             notiz="Messung 21.09. (B3): Die Zahlen fehlten einmal ganz im Prompt; seitdem "
                   "reicht _abstimmung sie durch. Wächter dafür."),
        fall("lotti-stadion-wer-dagegen", "lotti",
             "Welche Fraktionen waren hier dagegen?",
             "beschluss/abstimmung",
             [g_text([["Grüne", "Grünen"], ["Für Oldenburg"]], q_presse(vergabe))],
             route="/council/decision", refs={"decision_id": bau["id"]},
             notiz="In den Daten steht es (Pressemitteilung 02.06.2026), im Beschluss-Block nicht. "
                   "Erwartet: Kontextfehler auf der Beschluss-Seite. Falle wie beim Rats-Fall: "
                   "Die CDU ist Antragstellerin, nicht Gegnerin."),
        fall("lotti-stadion-tu-antrag", "lotti",
             "Was wurde hier entschieden und was bedeutet das für mich?",
             "beschluss/ergebnis",
             [g_ergebnis(fvo), g_sitzungsdatum(fvo), g_gegenstimmen(fvo)],
             route="/council/decision", refs={"decision_id": fvo["id"]},
             notiz="Faktencheck lotti[4]: Gemini erfand „keine direkte Auswirkung, da abgelehnt“ "
                   "und ließ die 31 Gegenstimmen weg, die im Kontext standen."),
        fall("lotti-stadion-eigenkapital", "lotti",
             "Wie viel Geld gibt die Stadt der Stadiongesellschaft laut diesem Beschluss?",
             "beschluss/kosten",
             [g_zahl(15_000_000, "€", "Eigenkapitalzuschuss (bis zu)",
                     q_beschluss(ek, "official_text Ziff. 3 / simple_summary"))],
             route="/council/decision", refs={"decision_id": ek["id"]},
             notiz="Im amtlichen Wortlaut steht die Zahl erst nach Zeichen 1.000 — der Block "
                   "kürzt auf 600. Sie kommt nur über die Kurzfassung in den Prompt. Die "
                   "50,4 Mio. € desselben Beschlusses sind eine Kostengrenze, keine Zahlung."),
    ]


def fliegerhorst(q: Quelle) -> list[dict]:
    hallensichel = q.beschluss("Rat", "2026-04-13", vorlage="26/0210")
    erwarte(hallensichel["no_votes"] == 23, "8541: 23 Gegenstimmen")
    halle = q.beschluss("Rat", "2026-02-23", vorlage="26/0089/1")
    erwarte("Dreifeldhalle" in halle["official_text"], "8497: Dreifeldhalle")
    halle_v = q.vorlage("26/0089/1")
    erwarte("knapp unter 20 Mio. Euro" in halle_v["financial_impact"]
            and "ca. 7 Mio. Euro" in halle_v["financial_impact"], "26/0089/1: Kosten")
    sanierung = q.beschluss("Rat", "2024-09-30", vorlage="24/0540")
    erwarte("160.767.900 Euro" in sanierung["official_text"]
            and "31. Dezember 2032" in sanierung["official_text"], "7240: Rahmen und Frist")
    quote = q.beschluss("Rat", "2025-12-01", vorlage="25/0755")
    erwarte("von 50 Prozent auf 30 Prozent" in quote["official_text"], "8336: Quote")
    return [
        fall("rat-fliegerhorst-zuletzt", "rat",
             "Was hat der Rat zuletzt zum Fliegerhorst beschlossen?",
             "verlauf/fliegerhorst",
             [g_sitzungsdatum(hallensichel), g_text([["N-777 G", "777 G", "777G"]],
                                                    q_beschluss(hallensichel, "title"))],
             notiz="Jüngster Ratsbeschluss mit Fliegerhorst im Titel (Stand der Daten). Die "
                   "Ratssitzung vom 31.08.2026 hatte zwei Fliegerhorst-Anträge auf der "
                   "Tagesordnung, ihr Protokoll liegt noch nicht vor — sie sind kein Beschluss."),
        fall("rat-fliegerhorst-sporthalle", "rat",
             "Welche Sporthalle bekommt die neue Grundschule auf dem Fliegerhorst?",
             "verlauf/fliegerhorst",
             [g_text([["Dreifeldhalle", "Dreifeld", "drei Felder"]], q_beschluss(halle, "official_text")),
              g_sitzungsdatum(halle)],
             notiz="Geplant war eine Einfeldhalle; der CDU-Antrag von 2024 wurde am 23.02.2026 "
                   "angenommen."),
        fall("rat-fliegerhorst-dreifeldhalle-kosten", "rat",
             "Was soll die Dreifeldhalle auf dem Fliegerhorst kosten?",
             "verwechslung/fliegerhorst",
             [g_zahl(20_000_000, "€", "orientierende Kosten Dreifeldhalle („knapp unter“)",
                     q_vorlage(halle_v), toleranz=0.05)],
             verboten=[v_zahl(7_000_000, "orientierende Kosten der EINFELDhalle")],
             notiz="Beide Zahlen stehen im selben Absatz der Vorlage; die 7 Mio. € gelten für die "
                   "verworfene Einfeldhalle."),
        fall("lotti-fliegerhorst-sanierung", "lotti",
             "Bis wann läuft die Sanierung hier und was darf sie kosten?",
             "beschluss/kosten",
             [g_zahl(160_767_900, "€", "Gesamtkostenrahmen", q_beschluss(sanierung, "official_text"),
                     toleranz=0.005),
              g_text(["2032"], q_beschluss(sanierung, "official_text"))],
             route="/council/decision", refs={"decision_id": sanierung["id"]},
             notiz="Gesamtkosten einschließlich privater Maßnahmen, nicht städtische Ausgaben. "
                   "Die Zahl steht bei Zeichen ~560 des Wortlauts — knapp vor der 600er-Kappe."),
        fall("lotti-fliegerhorst-quote", "lotti",
             "Wie hoch ist die Quote für preiswerten Wohnraum hier jetzt?",
             "beschluss/ergebnis",
             [g_zahl(30, "%", "Quote preiswerter Wohnraum (neu)", q_beschluss(quote, "official_text"))],
             route="/council/decision", refs={"decision_id": quote["id"]},
             notiz="Die alte Quote (50 %) steht im selben Satz; sie als frühere zu nennen, ist "
                   "richtig — deshalb kein Verbot."),
        fall("lotti-ort-hallensichel", "lotti",
             "Wie weit ist der Bebauungsplan hier?",
             "ort",
             [g_sitzungsdatum(hallensichel), g_text([["Satzung", "beschlossen"]],
                                                    q_beschluss(hallensichel, "official_text"))],
             route="/council/ort", refs={"place_id": "hallensichel-ost"},
             notiz="Der Orts-Block trägt Name und Beschreibung des Orts, keine Beschlüsse — "
                   "erwartet: Kontextfehler. Falle: Ein Satzungsbeschluss zu N-777 G fiel schon "
                   "am 28.09.2020; der gültige ist der vom 13.04.2026."),
    ]


def radverkehr_und_baeder(q: Quelle) -> list[dict]:
    leitfaden = q.beschluss("Rat", "2026-06-01", vorlage="26/0221")
    erwarte(leitfaden["outcome"] == "accepted", "9307: angenommen")
    haarenesch = q.beschluss("Rat", "2025-02-24", vorlage="24/0824")
    erwarte("Beibehaltung" in haarenesch["official_text"] and haarenesch["no_votes"] == 5,
            "7533: bleibt, 5 dagegen")
    quellenweg = q.beschluss("Rat", "2022-09-26", vorlage="22/0667")
    erwarte("CDU" in quellenweg["raw_result"], "5172: CDU dagegen")
    btb = q.beschluss("Rat", "2026-06-01", vorlage="26/0353")
    erwarte(btb["vote"] == "unanimous" and "2027 bis 2030" in btb["official_text"], "9316")
    btb_v = q.vorlage("26/0353")
    fi = btb_v["financial_impact"]
    erwarte("2026: 173.000,00" in fi and "2027: 177.500,00" in fi and "2030: 191.000,00" in fi,
            "26/0353: Beträge je Jahr")
    busse = q.beschluss("Rat", "2026-06-29", vorlage="26/0414")
    erwarte("41 batterieelektrische Fahrzeuge" in busse["official_text"], "9356: 41 Busse")
    tangente = q.beschluss("Rat", "2025-12-15", titel="Tangentialbuslinien")
    erwarte(tangente["outcome"] == "rejected", "8472: abgelehnt")
    return [
        fall("rat-radverkehr-plaene", "rat",
             "Was plant die Stadt für den Radverkehr?",
             "verlauf/radverkehr",
             [g_sitzungsdatum(leitfaden), g_text([["Leitfaden"]], q_beschluss(leitfaden, "title"))],
             notiz="Faktencheck rat[2]: Gemini stellte Anträge und Berichte von 2019/2020 "
                   "(Radschnellweg-Prüfung 2020, Quellenweg-Planung 2019) ohne Jahr als heutige "
                   "Pläne dar. Der jüngste Beschluss ist der Fahrradstraßen-Leitfaden."),
        fall("rat-quellenweg-fahrradstrasse", "rat",
             "Wird der Quellenweg eine Fahrradstraße?",
             "verwechslung/radverkehr",
             [g_sitzungsdatum(quellenweg), g_ergebnis(quellenweg)],
             notiz="Mehrstufig: 2019 Planung beauftragt, 2020 umbenannt in „fahrradgerechter "
                   "Ausbau“, am 26.09.2022 beschloss der Rat die UMSETZUNG der Fahrradstraße "
                   "Quellenweg (CDU dagegen). Der Faktencheck vom 23.09. hielt die Umbenennung "
                   "von 2020 für den Endstand — der Fall prüft, ob 2022 gefunden wird."),
        fall("rat-haareneschstrasse", "rat",
             "Bleibt die Haareneschstraße eine Fahrradstraße?",
             "verlauf/radverkehr",
             [g_sitzungsdatum(haarenesch), g_gegenstimmen(haarenesch)],
             notiz="Zwei Beschlüsse zur selben Straße: 26.08.2024 (Katharinenstraße, Zuwegung) "
                   "und 24.02.2025 (Beibehaltung mit neuer Parkordnung)."),
        fall("lotti-haarenesch-abstimmung", "lotti",
             "Wie ist die Abstimmung hier ausgegangen?",
             "beschluss/abstimmung",
             [g_ergebnis(haarenesch), g_gegenstimmen(haarenesch)],
             route="/council/decision", refs={"decision_id": haarenesch["id"]}),
        fall("rat-schwimmbad-zuletzt", "rat",
             "Was wurde zuletzt zum Thema Schwimmbad beschlossen?",
             "verlauf/schwimmbad",
             [g_sitzungsdatum(btb), g_text([["BTB", "Bürgerfelder Turnerbund"]],
                                           q_beschluss(btb, "official_text")),
              g_text([["einstimmig"]], q_beschluss(btb, "vote=unanimous"))],
             notiz="Faktencheck rat[6]: beide Modelle richtig — Wächter."),
        fall("rat-btb-zuschuss-2027", "rat",
             "Mit wie viel Geld unterstützt die Stadt das BTB-Schwimmbad im Jahr 2027?",
             "verwechslung/schwimmbad",
             [g_zahl(177_500, "€", "Zuschuss BTB-Bad (Maximalbetrag)", q_vorlage(btb_v), jahr=2027)],
             verboten=[v_zahl(173_000, "Betrag für 2026"), v_zahl(191_000, "Betrag für 2030")],
             notiz="Jahresfalle: Die Vorlage nennt fünf Jahresbeträge in einer Zeile. Ob die "
                   "Vorlage (financial_impact) überhaupt in den Kontext kommt, ist Teil der Messung."),
        fall("lotti-btb-betrag", "lotti",
             "Wie viel Geld bekommt der BTB hier im Jahr 2027?",
             "beschluss/kosten",
             [g_zahl(177_500, "€", "Zuschuss BTB-Bad (Maximalbetrag)", q_vorlage(btb_v), jahr=2027)],
             verboten=[v_zahl(173_000, "Betrag für 2026"), v_zahl(191_000, "Betrag für 2030")],
             route="/council/decision", refs={"decision_id": btb["id"]},
             notiz="Beschlusstext und Kurzfassung nennen keine Beträge, nur die Vorlage — "
                   "erwartet: Kontextfehler (der Beschluss-Block reicht die Vorlage nicht durch)."),
        fall("rat-vwg-elektrobusse", "rat",
             "Wie viele Elektrobusse soll die VWG bis 2030 anschaffen?",
             "beschluss/ergebnis",
             [g_zahl(41, "Fahrzeuge", "batterieelektrische Busse bis Ende 2030",
                     q_beschluss(busse, "official_text")), g_sitzungsdatum(busse)]),
        fall("lotti-vwg-busse", "lotti",
             "Wie viele Busse werden hier angeschafft und bis wann?",
             "beschluss/ergebnis",
             [g_zahl(41, "Fahrzeuge", "batterieelektrische Busse", q_beschluss(busse, "official_text")),
              g_text(["2030"], q_beschluss(busse, "official_text"))],
             route="/council/decision", refs={"decision_id": busse["id"]}),
        fall("rat-tangentialbus-praemisse", "rat",
             "Ab wann fahren die neuen Tangentialbuslinien in Oldenburg?",
             "verwechslung/praemisse",
             [g_ergebnis(tangente), g_sitzungsdatum(tangente)],
             notiz="Falsche Prämisse: Es gibt keine beschlossenen Tangentiallinien — schon der "
                   "Prüfauftrag (FDP) wurde am 15.12.2025 abgelehnt. Ein Starttermin wäre erfunden."),
    ]


def grundsteuer(q: Quelle) -> list[dict]:
    satzung25 = q.beschluss("Rat", "2024-11-25", vorlage="24/0645")
    erwarte(satzung25["outcome"] == "accepted", "7293: angenommen")
    vertagt = q.beschluss("Rat", "2025-12-01", vorlage="25/0615")
    erwarte(vertagt["outcome"] == "postponed", "8349: vertagt")
    abgelehnt = q.beschluss("Rat", "2025-12-15", vorlage="25/0615")
    erwarte(abgelehnt["outcome"] == "rejected" and abgelehnt["no_votes"] == 43, "8468")
    v25 = q.vorlage("25/0615")
    erwarte("rund 4,42 Millionen Euro" in v25["financial_impact"], "25/0615: Mehrertrag")
    b490 = q.beschluss("Ausschuss für Finanzen und Beteiligungen", "2023-09-06", vorlage="23/0632")
    erwarte(b490["outcome"] == "rejected" and "490 v.H." in b490["official_text"], "5988")
    erwarte("steigt" in (b490["simple_summary"] or ""), "5988: Kurzfassung (fehlerhaft) unverändert")
    hb24 = q.hebesatz("Grundsteuer B", 2015)
    hb25 = q.hebesatz("Grundsteuer B", 2025)
    erwarte(hb24["rate"] == 445 and hb25["rate"] == 539, "Hebesätze B")
    q_hb = "council_tax_rates kind='Grundsteuer B'"
    return [
        fall("rat-grundsteuer-entwicklung", "rat",
             "Wie hat sich die Grundsteuer in Oldenburg entwickelt?",
             "verlauf/grundsteuer",
             [g_zahl(445, "%", "Hebesatz Grundsteuer B 2015–2024", f"{q_hb}, year=2015", jahr=2015),
              g_zahl(539, "%", "Hebesatz Grundsteuer B ab 2025", f"{q_hb}, year=2025", jahr=2025),
              g_sitzungsdatum(satzung25), g_sitzungsdatum(abgelehnt)],
             notiz="Faktencheck rat[3]: Gemini datierte die Vertagung (01.12.2025) auf November; "
                   "die Hebesätze standen gar nicht im Prompt. Die Hebesätze liegen in "
                   "council_tax_rates (Haushalts-Facette), die Beschlüsse im Archiv; der "
                   "Satzungsbeschluss selbst nennt keinen Satz („in der anliegenden Fassung“)."),
        fall("rat-grundsteuer-dezember-2025", "rat",
             "Wie ging die Abstimmung über die Grundsteuer-Satzung im Dezember 2025 aus?",
             "verlauf/grundsteuer",
             [g_ergebnis(abgelehnt), g_sitzungsdatum(abgelehnt), g_gegenstimmen(abgelehnt)],
             notiz="Zwei Ratssitzungen im Dezember: am 01.12. vertagt, am 15.12. mit 43 "
                   "Gegenstimmen abgelehnt."),
        fall("rat-grundsteuer-mehrertrag", "rat",
             "Wie viel Mehrertrag hätte die im Dezember 2025 abgelehnte Grundsteuer-Anhebung gebracht?",
             "beschluss/kosten",
             [g_zahl(4_420_000, "€", "erwartete Mehrerträge ab 2026", q_vorlage(v25), jahr=2026,
                     toleranz=0.01)]),
        fall("rat-grundsteuer-490-prozent", "rat",
             "Wurde die Grundsteuer B für 2024 auf 490 Prozent erhöht?",
             "verwechslung/grundsteuer",
             [g_ergebnis(b490), g_sitzungsdatum(b490)],
             notiz="DATENFEHLER als Falle: Beschlusstext und beide Kurzfassungen (summary, "
                   "simple_summary) von 5988 beschreiben die Erhöhung als beschlossen — das "
                   "Ergebnis ist „einstimmig abgelehnt“. Frag den Rat bekommt summary + "
                   "outcome, also einen Widerspruch im Kontext."),
        fall("lotti-grundsteuer-490", "lotti",
             "Steigt die Grundsteuer B damit auf 490 Prozent?",
             "verwechslung/grundsteuer",
             [g_ergebnis(b490)],
             route="/council/decision", refs={"decision_id": b490["id"]},
             notiz="Lottis Beschluss-Block zeigt „Abstimmung: abgelehnt, einstimmig“ und direkt "
                   "darunter die Kurzfassung „Der Satz für die Grundsteuer B steigt von 445 auf "
                   "490 Prozent“ — ein Kontext, der sich selbst widerspricht. 15 von 21 "
                   "abgelehnten Beschlüssen mit Kurzfassung tragen diesen Fehler (Stand 23.09.)."),
    ]


def weitere_beschluesse(q: Quelle) -> list[dict]:
    waerme = q.beschluss("Rat", "2026-06-01", vorlage="26/0236")
    erwarte("18 Maßnahmen" in waerme["official_text"] and waerme["no_votes"] == 5, "8683")
    lachgas = q.beschluss("Rat", "2025-09-29", titel="Lachgas")
    erwarte(lachgas["vote"] == "unanimous", "9278: einstimmig")
    obwahl = q.beschluss("Rat", "2025-10-27", vorlage="25/0676")
    erwarte("27.09.2026" in obwahl["official_text"] and "13.09.2026" in obwahl["official_text"], "8003")
    kongress = q.beschluss("Rat", "2025-06-30", vorlage="25/0332/1")
    erwarte("78.681.607,64 Euro" in kongress["official_text"], "7911: Pauschalpreis")
    b_kongress = q.beschluss("Rat", "2025-06-30", vorlage="25/0321")
    erwarte("von 50,0 Millionen Euro auf maximal 79,0 Millionen Euro" in b_kongress["official_text"],
            "7912: 50 → 79 Mio.")
    b_kramer = q.beschluss("Rat", "2026-02-23", vorlage="25/0929")
    erwarte("von 12,0 Millionen Euro auf maximal 16,9 Millionen Euro" in b_kramer["official_text"]
            and "Kramermarkt" in b_kramer["official_text"], "8478: 12 → 16,9 Mio.")
    sechs = q.beschluss("Rat", "2026-06-29", titel="Sechsfeldhalle")
    erwarte(sechs["outcome"] == "accepted", "9368: angenommen")
    sechs_vertagt = q.beschluss("Rat", "2026-06-01", titel="Sechsfeldhalle")
    erwarte(sechs_vertagt["outcome"] == "postponed", "9322: vertagt")
    sechs_presse = q.presse("2026-02-11", "Sechs Felder für Oldenburgs Hallensport")
    erwarte("31,3 Millionen Euro" in sechs_presse["text"], "Presse: 31,3 Mio.")
    zweck = q.beschluss("Rat", "2025-12-01", vorlage="25/0817")
    erwarte("Entwurf für eine Zweckentfremdungssatzung" in zweck["official_text"], "8353")
    zweck_ab = q.beschluss("Rat", "2026-06-01", vorlage="26/0337")
    erwarte(zweck_ab["raw_result"] == "abgesetzt", "9321: abgesetzt")
    vbn = q.beschluss("Rat", "2023-09-04", vorlage="23/0537")
    erwarte(vbn["outcome"] == "rejected" and "zugestimmt" in vbn["official_text"], "5914")
    reinigung = q.beschluss("Rat", "2022-11-07", titel="Eigenreinigung")
    erwarte(reinigung["outcome"] == "rejected", "5253: abgelehnt")
    scooter = q.beschluss("Rat", "2025-12-01", titel="E-Scooter-Parkzonen")
    erwarte(scooter["outcome"] == "rejected" and scooter["no_votes"] == 41, "8351")
    bezirke = q.beschluss("Rat", "2026-03-16", vorlage="26/0179")
    erwarte("einstimmig bei neun Enthaltungen" in bezirke["raw_result"]
            and bezirke["vote"] == "majority", "8426: vote-Spalte widerspricht raw_result")
    kreuzung = q.beschluss("Rat", "2024-08-26", vorlage="24/0422")
    erwarte(kreuzung["amount_eur"] == 870000, "7058: 870.000 €")
    baum = q.beschluss("Rat", "2025-06-30", vorlage="25/0387")
    erwarte(baum["no_votes"] == 15, "7920: 15 Gegenstimmen")
    baum_presse = q.presse("2026-02-22", "Baumschutzsatzung bleibt bestehen")
    erwarte("Quorum" in baum_presse["text"] and "60,58 Prozent" in baum_presse["text"], "Bürgerentscheid")

    return [
        fall("rat-waermeplan", "rat",
             "Hat der Rat den Oldenburger Wärmeplan beschlossen?",
             "beschluss/ergebnis",
             [g_sitzungsdatum(waerme), g_ergebnis(waerme),
              g_zahl(18, "Maßnahmen", "Maßnahmen des Wärmeplans", q_beschluss(waerme, "official_text")),
              g_gegenstimmen(waerme)]),
        fall("lotti-waermeplan-massnahmen", "lotti",
             "Wie viele Maßnahmen umfasst der Plan hier?",
             "beschluss/ergebnis",
             [g_zahl(18, "Maßnahmen", "Maßnahmen des Wärmeplans", q_beschluss(waerme, "official_text"))],
             route="/council/decision", refs={"decision_id": waerme["id"]}),
        fall("lotti-thema-waermeplanung", "lotti",
             "Was ist hier zur Wärmeplanung beschlossen worden?",
             "verlauf/klima",
             [g_sitzungsdatum(waerme),
              g_zahl(18, "Maßnahmen", "Maßnahmen des Wärmeplans", q_beschluss(waerme, "official_text"))],
             route="/council/thema", refs={"slug": "klima_umwelt"},
             notiz="Der Themenfeld-Block trägt nur Label und Beschreibung aus council/topics.py; "
                   "der Rückblick (council_field_recaps) nennt den Wärmeplan, kommt aber nicht in "
                   "Lottis Prompt — erwartet: Kontextfehler."),
        fall("rat-lachgas-verbot", "rat",
             "Hat Oldenburg ein Lachgas-Verbot für Minderjährige beschlossen?",
             "beschluss/ergebnis",
             [g_sitzungsdatum(lachgas), g_text([["einstimmig"]], q_beschluss(lachgas, "vote"))]),
        fall("lotti-ob-stichwahl", "lotti",
             "Wann wäre laut diesem Beschluss eine Stichwahl?",
             "beschluss/ergebnis",
             [g_datum("2026-09-27", q_beschluss(obwahl, "official_text"))],
             route="/council/decision", refs={"decision_id": obwahl["id"]},
             notiz="Im selben Satz steht der Wahltag (13.09.2026); ihn als Wahltag zu nennen ist "
                   "richtig, ihn als Stichwahl zu nennen falsch."),
        fall("rat-kongresshalle-kosten", "rat",
             "Was kostet der Neubau der Kongresshalle an der Weser-Ems-Halle?",
             "verwechslung/weser-ems-halle",
             [g_zahl(78_681_607.64, "€", "Pauschalpreis netto", q_beschluss(kongress, "official_text"),
                     toleranz=0.002)],
             verboten=[v_zahl(79_000_000, "Höchstbetrag der Ausfallbürgschaft, nicht der Baupreis")],
             notiz="Baupreis (78,68 Mio. €) und Bürgschaft (79 Mio. €) wurden in derselben Sitzung "
                   "beschlossen und liegen 0,4 % auseinander — die Toleranz ist deshalb eng."),
        fall("rat-kongresshalle-buergschaft", "rat",
             "Für welchen Betrag bürgt die Stadt beim Neubau der Kongresshalle der Weser-Ems-Halle?",
             "verwechslung/weser-ems-halle",
             [g_zahl(79_000_000, "€", "Ausfallbürgschaft Kongresshalle (Höchstbetrag)",
                     q_beschluss(b_kongress, "official_text")), g_sitzungsdatum(b_kongress)],
             verboten=[v_zahl(16_900_000, "Bürgschaft für die Park- und Kramermarktfläche "
                                          f"(id {b_kramer['id']}), nicht für die Kongresshalle")],
             notiz="Zwei Bürgschaften für dieselbe Gesellschaft, beide 2023 beschlossen und später "
                   "erhöht: Kongresshalle 50 → 79 Mio. € (30.06.2025), Kramermarktfläche "
                   "12 → 16,9 Mio. € (23.02.2026). Die jüngere ist die falsche."),
        fall("lotti-buergschaft-kongresshalle", "lotti",
             "Um wie viel wurde die Bürgschaft hier erhöht?",
             "verwechslung/weser-ems-halle",
             [g_zahl(50_000_000, "€", "Bürgschaft vorher", q_beschluss(b_kongress, "official_text")),
              g_zahl(79_000_000, "€", "Bürgschaft neu (Höchstbetrag)",
                     q_beschluss(b_kongress, "official_text"))],
             verboten=[v_zahl(16_900_000, "andere Bürgschaft (Kramermarktfläche)")],
             route="/council/decision", refs={"decision_id": b_kongress["id"]}),
        fall("lotti-buergschaft-kramermarkt", "lotti",
             "Wofür gilt die Bürgschaft hier und wie hoch ist sie?",
             "verwechslung/weser-ems-halle",
             [g_text([["Kramermarkt", "Parkfläche", "Park- und Kramermarkt"]],
                     q_beschluss(b_kramer, "official_text")),
              g_zahl(16_900_000, "€", "Bürgschaft neu (Höchstbetrag)", q_beschluss(b_kramer, "official_text"))],
             verboten=[v_zahl(79_000_000, "Bürgschaft für die Kongresshalle, nicht diese")],
             route="/council/decision", refs={"decision_id": b_kramer["id"]}),
        fall("rat-sechsfeldhalle-beschlossen", "rat",
             "Wurde die Sechsfeldhalle an der Kennedystraße beschlossen?",
             "verwechslung/sechsfeldhalle",
             [g_sitzungsdatum(sechs), g_ergebnis(sechs)],
             notiz="Derselbe Antrag stand am 01.06.2026 auf der Tagesordnung und wurde aus "
                   f"Zeitgründen vertagt (id {sechs_vertagt['id']}); beschlossen am 29.06.2026. "
                   "Wer beim 01.06. stehen bleibt, meldet einen veralteten Stand."),
        fall("rat-sechsfeldhalle-kosten", "rat",
             "Was soll die Sechsfeldhalle an der Kennedystraße kosten?",
             "beschluss/kosten",
             [g_zahl(31_300_000, "€", "erste Kostenschätzung", q_presse(sechs_presse), toleranz=0.01)],
             notiz="Der Beschluss nennt keine Kosten; die erste Schätzung steht nur in der "
                   "Pressemitteilung vom 11.02.2026."),
        fall("lotti-sechsfeldhalle-kosten", "lotti",
             "Was kostet die Halle, um die es hier geht?",
             "beschluss/kosten",
             [g_zahl(31_300_000, "€", "erste Kostenschätzung", q_presse(sechs_presse), toleranz=0.01)],
             route="/council/decision", refs={"decision_id": sechs["id"]},
             notiz="Erwartet: Kontextfehler — der Beschluss-Block kennt keine Pressemitteilungen."),
        fall("rat-zweckentfremdungssatzung", "rat",
             "Gibt es in Oldenburg inzwischen eine Zweckentfremdungssatzung?",
             "verwechslung/zweckentfremdung",
             [g_sitzungsdatum(zweck), g_text([["Entwurf"]], q_beschluss(zweck, "official_text"))],
             notiz="Beschlossen ist am 01.12.2025 nur der AUFTRAG, einen Entwurf vorzulegen; der "
                   "SPD-Antrag zum Entwurf wurde am 01.06.2026 abgesetzt. Eine Satzung gibt es "
                   "nicht — „ja, seit Dezember 2025“ wäre die Verwechslung."),
        fall("rat-vbn-tarif-2024", "rat",
             "Hat der Rat der VBN-Tarifanpassung zum 1. Januar 2024 zugestimmt?",
             "verwechslung/abgelehnt-als-angenommen",
             [g_ergebnis(vbn), g_sitzungsdatum(vbn)],
             notiz="DATENFEHLER als Falle: Beschlusstext (= Beschlussvorschlag) und beide "
                   "Kurzfassungen sagen „wird zugestimmt“, das Ergebnis ist „mehrheitlich bei zwei "
                   "Ja-Stimmen abgelehnt“."),
        fall("lotti-vbn-tarif-2024", "lotti",
             "Gelten damit ab 2024 neue Preise im VBN?",
             "verwechslung/abgelehnt-als-angenommen",
             [g_ergebnis(vbn)],
             route="/council/decision", refs={"decision_id": vbn["id"]},
             notiz="Wie lotti-grundsteuer-490: Die Kurzfassung behauptet das Gegenteil des "
                   "Ergebnisses."),
        fall("rat-eigenreinigung", "rat",
             "Reinigt die Stadt ihre Gebäude inzwischen mit eigenem Personal?",
             "verwechslung/abgelehnt-als-angenommen",
             [g_ergebnis(reinigung), g_sitzungsdatum(reinigung)],
             notiz="Antrag der Linken vom 21.10.2022, am 07.11.2022 abgelehnt. Kurzfassung: „Die "
                   "Reinigung städtischer Gebäude übernimmt die Stadt selbst“ — falsch."),
        fall("lotti-e-scooter-antrag", "lotti",
             "Was ist aus dem Antrag hier geworden?",
             "beschluss/ergebnis",
             [g_ergebnis(scooter), g_gegenstimmen(scooter)],
             route="/council/decision", refs={"decision_id": scooter["id"]},
             notiz="Einfacher Fall als Nullmessung: Alles steht im Beschluss-Block."),
        fall("rat-schulbezirke-abstimmung", "rat",
             "Wie wurde über die neuen Schulbezirke der Grundschulen abgestimmt?",
             "beschluss/abstimmung",
             [g_text([["einstimmig"]], q_beschluss(bezirke, "raw_result")),
              g_enthaltungen(bezirke), g_sitzungsdatum(bezirke)],
             notiz="DATENFEHLER als Falle: vote='majority', raw_result „einstimmig bei neun "
                   "Enthaltungen“. Frag den Rat reicht raw_result nur bei strittigen Beschlüssen "
                   "durch — hier gilt er wegen vote='majority' als strittig."),
        fall("lotti-schulbezirke-gegenstimmen", "lotti",
             "Gab es hier Gegenstimmen?",
             "beschluss/abstimmung",
             [g_text([["einstimmig", "keine Gegenstimme"]], q_beschluss(bezirke, "raw_result")),
              g_enthaltungen(bezirke)],
             route="/council/decision", refs={"decision_id": bezirke["id"]},
             notiz="Lottis _abstimmung liest vote='majority' und schreibt „mehrheitlich, 9 "
                   "Enthaltungen“ — raw_result sieht sie nicht. Erwartet: Kontext falsch "
                   "zugeordnet (mehrheitlich statt einstimmig). Achtung beim Abgleich: Das Wort "
                   "„Einstimmig“ steht in einer Prompt-Regel — ein reiner Wortfund im Prompt "
                   "meldet hier fälschlich Abdeckung; gesucht werden muss in den Kontextblöcken."),
        fall("rat-ort-kreuzung-muellersweg", "rat",
             "Wie viel Geld wurde für den Ausbau der Kreuzung Müllersweg/Bremer Heerstraße bewilligt?",
             "ort",
             [g_zahl(870_000, "€", "außerplanmäßige Mehrauszahlung", q_beschluss(kreuzung, "official_text")),
              g_sitzungsdatum(kreuzung)],
             verboten=[v_zahl(390_000, "Deckung aus „Technologiepark Wechloy“, nicht die Bewilligung"),
                       v_zahl(480_000, "Deckung aus „BG Am Bahndamm“, nicht die Bewilligung")]),
        fall("rat-baumschutzsatzung", "rat",
             "Gilt die Baumschutzsatzung in Oldenburg noch?",
             "verlauf/baumschutz",
             [g_text([["bleibt bestehen", "gilt weiterhin", "weiterhin", "bleibt in Kraft", "gilt noch"]],
                     q_presse(baum_presse)),
              g_datum(baum_presse["date"], q_presse(baum_presse)),
              g_sitzungsdatum(baum)],
             notiz="Falle: Beim Bürgerentscheid am 22.02.2026 stimmten 60,58 % FÜR die Aufhebung — "
                   "das Quorum (20 % der Stimmberechtigten) wurde aber verfehlt, die Satzung "
                   "bleibt. Beschlossen hatte der Rat sie am 30.06.2025 (15 Gegenstimmen)."),
    ]


def personen(q: Quelle) -> list[dict]:
    verkehr = q.vorsitz("Verkehrsausschuss")
    erwarte(verkehr["name"] == "Renke Meerbothe", "Vorsitz Verkehrsausschuss")
    umwelt = q.vorsitz("Ausschuss für Stadtgrün, Umwelt und Klima")
    erwarte(umwelt["name"] == "Gabriel Oliver Rohde", "Vorsitz ASUK")
    adler = q.person("Hans-Henning Adler")
    erwarte(adler["current_faction"] == "BSW", "Adler: BSW")
    sander = q.person("Andreas Sander")
    erwarte(sander["current_faction"] == "Für Oldenburg", "Sander: Für Oldenburg")
    luekermann = q.person("Jens Lükermann")
    erwarte(luekermann["current_faction"] == "Volt", "Lükermann: Volt")

    druege = {m["committee"]: m["role"] for m in q.mitgliedschaften("Ruth Regina Drügemöller")}
    erwarte(druege.get("Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau")
            == "Ausschussvorsitzende/r", "Drügemöller: Vorsitz BEGH")
    for gremium in ("Ausschuss für Stadtplanung und Bauen", "Ausschuss für Finanzen und Beteiligungen",
                    "Ausschuss für Stadtgrün, Umwelt und Klima"):
        erwarte(gremium in druege, f"Drügemöller: {gremium}")
    ellberg = {m["committee"]: m["role"] for m in q.mitgliedschaften("Bernhard Ellberg")}
    erwarte(ellberg.get("Schulausschuss") == "Ausschussvorsitzende/r", "Ellberg: Schulausschuss")
    erwarte(any(c.startswith("Ausschuss für Wirtschaftsförderung") and r == "Ausschussvorsitzende/r"
                for c, r in ellberg.items()), "Ellberg: Wirtschaftsförderung")

    q_m = "council_memberships (valid_until leer oder nach Stichtag) ⋈ council_persons"
    q_p = "council_persons.current_faction"
    return [
        fall("rat-person-vorsitz-verkehr", "rat",
             "Wer ist Vorsitzender des Verkehrsausschusses?",
             "person/ausschuss",
             [g_text(["Meerbothe"], f"{q_m}; committee='Verkehrsausschuss', role='Ausschussvorsitzende/r'")]),
        fall("rat-person-vorsitz-umwelt", "rat",
             "Wer leitet den Ausschuss für Stadtgrün, Umwelt und Klima?",
             "person/ausschuss",
             [g_text(["Rohde"], f"{q_m}; committee='Ausschuss für Stadtgrün, Umwelt und Klima', "
                                "role='Ausschussvorsitzende/r' seit 2025-08-25")],
             notiz="Wechsel im August 2025; ältere Protokolle zeigen andere Sitzungsleitungen."),
        fall("rat-person-adler-fraktion", "rat",
             "Für welche Fraktion sitzt Hans-Henning Adler im Rat?",
             "person/fraktion",
             [g_text(["BSW"], f"{q_p}; name='Hans-Henning Adler'")],
             notiz="Fraktionswechsel: bis 2023 Linke, Anfang 2024 „Bündnis Vernunft und "
                   "Gerechtigkeit“, seitdem BSW (council_attendance.party). Wer die älteren "
                   "Protokolle liest, nennt die Linke."),
        fall("rat-person-sander-gruppe", "rat",
             "Welcher Fraktion oder Gruppe gehört Andreas Sander an?",
             "person/fraktion",
             [g_text(["Für Oldenburg"], f"{q_p}; name='Andreas Sander'")],
             notiz="Bis 2024 Piratenpartei (Gruppe mit den Linken), seit 11/2024 „Für Oldenburg“. "
                   "Fraktion vs. Gruppe: „Für Oldenburg“ tritt als Gruppe auf."),
        fall("lotti-person-luekermann-partei", "lotti",
             "Für welche Partei sitzt er im Rat?",
             "person/fraktion",
             [g_text(["Volt"], f"{q_p}; name='Jens Lükermann'")],
             route="/council/person", refs={"slug": "jens-luekermann"},
             notiz="Bis 12/2024 als „FDP/Volt“ geführt (Gruppe), seitdem Volt allein. Lottis "
                   "Personen-Block trägt nur den Namen — erwartet: Kontextfehler."),
        fall("rat-person-druegemoeller-ausschuesse", "rat",
             "In welchen Ausschüssen sitzt Ruth Drügemöller?",
             "person/ausschuss",
             [g_text(["Gebäudewirtschaft", "Stadtplanung", "Finanzen"],
                     f"{q_m}; name='Ruth Regina Drügemöller'")],
             notiz="Frag den Rat erkennt die Person (finde_person) und antwortet aus ihren "
                   "Wortbeiträgen — Mitgliedschaften stehen dort nicht. Erwartet: Kontextfehler."),
        fall("rat-person-ellberg-vorsitz", "rat",
             "Welche Ausschüsse leitet Bernhard Ellberg?",
             "person/ausschuss",
             [g_text(["Schulausschuss", "Wirtschaftsförderung"], f"{q_m}; name='Bernhard Ellberg', "
                                                                 "role='Ausschussvorsitzende/r'")]),
        fall("lotti-person-druegemoeller-ausschuesse", "lotti",
             "In welchen Ausschüssen sitzt sie?",
             "person/ausschuss",
             [g_text(["Gebäudewirtschaft", "Stadtplanung", "Finanzen"],
                     f"{q_m}; name='Ruth Regina Drügemöller'")],
             route="/council/person", refs={"slug": "ruth-regina-druegemoeller"},
             notiz="Die Personenseite zeigt die Mitgliedschaften; Lottis Personen-Block trägt nur "
                   "den Namen. Erwartet: Kontextfehler."),
        fall("lotti-person-adler-fraktion", "lotti",
             "Welcher Fraktion gehört er heute an?",
             "person/fraktion",
             [g_text(["BSW"], f"{q_p}; name='Hans-Henning Adler'")],
             route="/council/person", refs={"slug": "hans-henning-adler"}),
        fall("lotti-person-meerbothe-vorsitz", "lotti",
             "Welchen Ausschuss leitet er?",
             "person/ausschuss",
             [g_text(["Verkehrsausschuss"], f"{q_m}; name='Renke Meerbothe', "
                                            "role='Ausschussvorsitzende/r'")],
             route="/council/person", refs={"slug": "renke-meerbothe"}),
    ]


def orte(q: Quelle) -> list[dict]:
    fleiwa = q.beschluss("Rat", "2026-06-01", titel="Bebauungsplan 855")
    am_ort = q.beschluesse_am_ort("alte-fleiwa")
    erwarte(bool(am_ort) and am_ort[0]["id"] == fleiwa["id"], "Alte Fleiwa: jüngster Beschluss 9319")
    hallensichel = q.beschluss("Rat", "2026-04-13", vorlage="26/0210")
    erwarte(q.beschluesse_am_ort("hallensichel-ost")[0]["id"] == hallensichel["id"],
            "Hallensichel-Ost: jüngster Beschluss 8541")
    ew = [d for d in q.beschluesse_am_ort("eversten-west") if d.get("outcome") == "accepted"]
    erwarte(bool(ew) and ew[0]["session_date"] == "2019-06-24", "Eversten-West: jüngster angenommener 2019")
    ew_rat = [d for d in ew if d["committee"] == "Rat" and d["session_date"] == "2019-06-24"]
    erwarte(len(ew_rat) >= 1, "Eversten-West: Ratsbeschluss 24.06.2019")
    q_ort = "store.decision_ids_for_place('{}') — jüngster angenommener Beschluss"
    return [
        fall("rat-ort-alte-fleiwa", "rat",
             "Was wurde zuletzt zur Alten Fleiwa beschlossen?",
             "ort",
             [g_sitzungsdatum(fleiwa), g_text(["855"], q_beschluss(fleiwa, "title"))]),
        fall("rat-ort-hallensichel", "rat",
             "Was hat der Rat zur Hallensichel-Ost beschlossen?",
             "ort",
             [g_sitzungsdatum(hallensichel), g_gegenstimmen(hallensichel)],
             notiz="Ein erster Satzungsbeschluss zu N-777 G fiel am 28.09.2020; gültig ist der "
                   "erneute vom 13.04.2026. Beide sind Ortsbeschlüsse, nur einer ist der Stand."),
        fall("rat-ort-eversten-west", "rat",
             "Was ist zuletzt in Eversten-West beschlossen worden?",
             "ort",
             [g_datum("2019-06-24", q_ort.format("eversten-west") + f", z. B. id {ew_rat[0]['id']}"),
              g_text(["2019"], q_ort.format("eversten-west"))],
             notiz="Alter Aktenstand: Der jüngste angenommene Beschluss ist von 2019 (spätere "
                   "Einträge sind Berichte). Die Antwort muss das Alter nennen, statt „aktuell“ "
                   "zu schreiben (aktenstand_regel)."),
        fall("lotti-ort-alte-fleiwa", "lotti",
             "Was wurde hier zuletzt beschlossen?",
             "ort",
             [g_sitzungsdatum(fleiwa), g_text(["855"], q_beschluss(fleiwa, "title"))],
             route="/council/ort", refs={"place_id": "alte-fleiwa"},
             notiz="Die Ortsseite listet die Beschlüsse; Lottis Orts-Block nur Name und "
                   "Beschreibung. Erwartet: Kontextfehler."),
    ]


def sitzungen(q: Quelle) -> list[dict]:
    rat_2809 = q.sitzung("Rat", "2026-09-28")
    erwarte(not q.beschluesse_der_sitzung(rat_2809["ksinr"]), "Rat 28.09.: noch keine Beschlüsse")
    top_ueber = q.tagesordnungspunkt(rat_2809["ksinr"], "Überplanmäßige Bewilligung")
    erwarte("9.512.500 Euro" in top_ueber["title"], "TOP 6.3: 9.512.500 €")
    top_klinikum = q.tagesordnungspunkt(rat_2809["ksinr"], "Klinikum Oldenburg AöR (KOL): Ausfallbürgschaft")
    top_abst = q.tagesordnungspunkt(rat_2809["ksinr"], "Transparente Dokumentation des Abstimmungsverhaltens")
    rat_2906 = q.sitzung("Rat", "2026-06-29")
    busse = q.beschluss("Rat", "2026-06-29", vorlage="26/0414")
    sechs = q.beschluss("Rat", "2026-06-29", titel="Sechsfeldhalle")
    krugweg = q.beschluss("Rat", "2026-06-29", titel="Bebauungsplan 810")
    for d in (busse, sechs, krugweg):
        erwarte(d["ksinr"] == rat_2906["ksinr"], f"{d['id']} gehört zu Rat 29.06.")
    rat_0106 = q.sitzung("Rat", "2026-06-01")
    bau = q.beschluss("Rat", "2026-06-01", vorlage="26/0396")
    buerg = q.beschluss("Rat", "2026-06-01", vorlage="26/0374")
    sport = q.sitzung("Sportausschuss", "2026-05-13")
    btb_sport = q.beschluss("Sportausschuss", "2026-05-13", titel="Schwimmbad BTB")

    erwarte("PFL" in (rat_2809["location"] or ""), "Rat 28.09.: Ort PFL")
    naechster_rat = q.naechste_sitzung("Rat")
    erwarte(naechster_rat["session_time"] == "18:00", "nächste Ratssitzung: 18:00 Uhr")
    naechster_va = q.naechste_sitzung("Verkehrsausschuss")
    q_kal = "council_sessions ∪ council_scheduled_sessions, erste {} nach Stichtag " + q.stichtag
    zeitabh = (f"ZEITABHÄNGIG: Goldwert relativ zum Stichtag {q.stichtag} gezogen — vor einem "
               "Lauf nach diesem Termin den Baukasten neu laufen lassen.")
    q_to = f"council_agenda_items ksinr={rat_2809['ksinr']}"

    return [
        fall("rat-sitzung-naechster-rat", "rat",
             "Wann tagt der Rat als Nächstes?",
             "sitzung/termin",
             [g_datum(naechster_rat["session_date"], q_kal.format("Rat-Sitzung")),
              g_text([["18:00", "18 Uhr", "18.00"]], q_kal.format("Rat-Sitzung") + "; session_time")],
             notiz=zeitabh),
        fall("rat-sitzung-naechster-verkehrsausschuss", "rat",
             "Wann ist die nächste Sitzung des Verkehrsausschusses?",
             "sitzung/termin",
             [g_datum(naechster_va["session_date"], q_kal.format("Verkehrsausschuss-Sitzung"))],
             notiz=zeitabh + " Die jüngste Sitzung (21.09.2026) liegt vor dem Stichtag und ist "
                             "die naheliegende Verwechslung."),
        fall("rat-sitzung-tagesordnung-2809", "rat",
             "Was steht bei der Ratssitzung am 28.09.2026 auf der Tagesordnung?",
             "sitzung/tagesordnung",
             [g_text(["Klinikum"], f"{q_to}, TOP {top_klinikum['item_number']}"),
              g_zahl(9_512_500, "€", "überplanmäßige Bewilligung Teilhaushalt 10",
                     f"{q_to}, TOP {top_ueber['item_number']}", toleranz=0.01),
              g_text(["Abstimmungsverhalten"], f"{q_to}, TOP {top_abst['item_number']}")],
             notiz="Künftige Sitzung ohne Beschlüsse: Die Tagesordnung ist die Antwort, und "
                   "Beschlüsse anderer Sitzungen sind es nicht (_sitzungen_block)."),
        fall("rat-sitzung-rat-2906", "rat",
             "Was hat der Rat am 29.06.2026 beschlossen?",
             "sitzung/beschluesse",
             [g_id(busse), g_id(sechs), g_id(krugweg)],
             notiz="Drei der gewichtigen Beschlüsse dieser Sitzung (34 Beschlüsse insgesamt); "
                   "finde_sitzungen soll alle vollständig in den Kontext holen."),
        fall("lotti-sitzung-2809-wann-wo", "lotti",
             "Wann und wo findet diese Sitzung statt?",
             "sitzung/termin",
             [g_datum(rat_2809["session_date"], f"council_sessions ksinr={rat_2809['ksinr']}"),
              g_text(["PFL"], f"council_sessions ksinr={rat_2809['ksinr']}; location")],
             route="/council/sitzung", refs={"ksinr": rat_2809["ksinr"]},
             notiz="Lottis Sitzungs-Block trägt Gremium und Datum, keinen Ort und keine Uhrzeit — "
                   "erwartet: Kontextfehler beim Ort."),
        fall("lotti-sitzung-2809-tagesordnung", "lotti",
             "Welche Punkte stehen hier auf der Tagesordnung?",
             "sitzung/tagesordnung",
             [g_text(["Klinikum"], f"{q_to}, TOP {top_klinikum['item_number']}"),
              g_zahl(9_512_500, "€", "überplanmäßige Bewilligung Teilhaushalt 10",
                     f"{q_to}, TOP {top_ueber['item_number']}", toleranz=0.01)],
             route="/council/sitzung", refs={"ksinr": rat_2809["ksinr"]},
             notiz="Die Seite zeigt die Tagesordnung, Lottis Block nicht. Erwartet: Kontextfehler."),
        fall("lotti-sitzung-0106-stadion", "lotti",
             "Was wurde hier in der Sitzung zum Stadion entschieden?",
             "sitzung/beschluesse",
             [g_id(bau), g_id(buerg), g_ergebnis(bau)],
             route="/council/sitzung", refs={"ksinr": rat_0106["ksinr"]},
             notiz="41 Beschlüsse in dieser Sitzung, fünf davon zum Stadion. Lottis Block kennt "
                   "keinen davon."),
        fall("lotti-sitzung-sport-1305", "lotti",
             "Was hat der Sportausschuss hier zum Schwimmbad beschlossen?",
             "sitzung/beschluesse",
             [g_text([["BTB", "Bürgerfelder Turnerbund"]], q_beschluss(btb_sport, "title")),
              g_ergebnis(btb_sport)],
             route="/council/sitzung", refs={"ksinr": sport["ksinr"]}),
        fall("lotti-thema-verkehr-zuletzt", "lotti",
             "Was wurde hier im Verkehr zuletzt beschlossen?",
             "verlauf/radverkehr",
             [g_datum(busse["session_date"],
                      "council_decisions policy_field='verkehr', jüngste angenommene (Rat 2026-06-29)")],
             route="/council/thema", refs={"slug": "verkehr"},
             notiz="Jüngste Verkehrsbeschlüsse: Rat 29.06.2026 (VWG-Antriebswende, "
                   "Bahnhofsvorplatz, Uhlhornsweg). Der Themenfeld-Block trägt keine Beschlüsse."),
    ]


def nicht_in_daten(q: Quelle) -> list[dict]:
    """Fragen, die plausibel klingen und die die Daten nicht beantworten.

    Jede ist gegen Beschlüsse (Wortlaut, Ergebnis-Satz), Vorlagen,
    Pressemitteilungen und — wo es um Abstimmungen geht — die Wortbeiträge
    gegengeprüft (23.09.2026). Die ``erwarte``-Zeilen halten die Lücke fest:
    Füllt ein neuer Import sie, bricht der Baukasten ab, statt einen falschen
    Befund gegen das Modell zu erzeugen.
    """
    c = q.conn
    # Baak kommt in der Presse vor (Innenstadt-Verein), aber nie beim Stadion.
    erwarte(c.execute("SELECT COUNT(*) FROM council_press WHERE text LIKE '%Baak%' "
                      "AND text LIKE '%Stadion%'").fetchone()[0] == 0,
            "Presse nennt Baak beim Stadion — Fall prüfen")
    waerme = q.beschluss("Rat", "2026-06-01", vorlage="26/0236")
    erwarte(waerme["no_votes"] == 5 and not any(
        w in (waerme["raw_result"] or "") for w in ("CDU", "SPD", "BSW", "AfD", "FDP", "Grün")),
        "Wärmeplan: Ergebnis-Satz nennt eine Fraktion — Fall prüfen")
    rat_3108 = q.sitzung("Rat", "2026-08-31")
    erwarte(not q.beschluesse_der_sitzung(rat_3108["ksinr"]), "Rat 31.08.: Protokoll jetzt da")
    q.tagesordnungspunkt(rat_3108["ksinr"], "Grundsteuer C")
    erwarte(c.execute("SELECT MAX(date) FROM council_press").fetchone()[0] < "2026-08-31",
            "Presse reicht über den 31.08. — Grundsteuer-C- und Sitzungsfall prüfen")
    erwarte(c.execute("SELECT COUNT(*) FROM council_press WHERE text LIKE '%Stichwahl%' "
                      "AND date >= '2026-09-27'").fetchone()[0] == 0, "Stichwahl-Ergebnis da")
    erwarte(c.execute("SELECT COUNT(*) FROM council_company_people WHERE name LIKE '%Orth%'")
            .fetchone()[0] == 0, "Stadion-Geschäftsführer in council_company_people")
    grst = q.beschluss("Rat", "2025-12-15", vorlage="25/0615")
    erwarte(grst["raw_result"].strip("- ") == "mehrheitlich mit 43 Gegenstimmen", "8468: nur Zahl")

    return [
        fall("rat-nd-einzelstimme-baak", "rat",
             "Wie hat Christoph Baak beim Stadion-Beschluss im Juni 2026 abgestimmt?",
             "nicht-in-daten/abstimmung", [], antwort_in_daten=False,
             notiz="Protokolle halten fest, WIE abgestimmt wurde, nicht WER wie. Die "
                   "Pressemitteilung vom 02.06. sagt, die CDU stimmte dafür und zwei CDU-"
                   "Mitglieder enthielten sich — ohne Namen. „Er stimmte dafür“ wäre geraten."),
        fall("rat-nd-waermeplan-wer-dagegen", "rat",
             "Welche Fraktion hat gegen den Wärmeplan gestimmt?",
             "nicht-in-daten/abstimmung", [], antwort_in_daten=False,
             notiz="Belegt sind fünf Gegenstimmen, keine Namen (raw_result, Presse 02.06.2026). "
                   "Adler (BSW) kritisierte den Plan und beantragte Vertagung (Wortbeitrag) — "
                   "daraus „die BSW stimmte dagegen“ zu machen, ist eine Folgerung, kein Beleg."),
        fall("rat-nd-grundsteuer-namen", "rat",
             "Welche Ratsmitglieder haben im Dezember 2025 für die höhere Grundsteuer gestimmt?",
             "nicht-in-daten/abstimmung", [], antwort_in_daten=False,
             notiz="Das Ergebnis lautet nur „mehrheitlich mit 43 Gegenstimmen“ (abgelehnt)."),
        fall("rat-nd-grundsteuer-c", "rat",
             "Hat der Rat die Einführung einer Grundsteuer C beschlossen?",
             "nicht-in-daten/offen", [], antwort_in_daten=False,
             notiz="Der BSW-Antrag stand am 31.08.2026 auf der Tagesordnung; das Protokoll liegt "
                   "nicht vor, die Presse reicht bis 26.08. Richtig: beantragt, Ergebnis offen."),
        fall("rat-nd-rat-3108", "rat",
             "Was hat der Rat am 31.08.2026 beschlossen?",
             "nicht-in-daten/offen", [], antwort_in_daten=False,
             notiz="Sitzung und Tagesordnung sind da, Beschlüsse nicht (Protokoll folgt Wochen "
                   "später — _sitzungen_block verlangt, das zu sagen). Beschlüsse anderer "
                   "Sitzungen sind NICHT die Antwort."),
        fall("rat-nd-stichwahl-ergebnis", "rat",
             "Wer hat die Stichwahl zum Oberbürgermeister gewonnen?",
             "nicht-in-daten/offen", [], antwort_in_daten=False,
             notiz="Stichwahl am 27.09.2026, nach dem Datenstand. Nur der Termin ist belegt "
                   "(Ratsbeschluss 27.10.2025). Sobald die Wahlergebnisse in den Daten sind, "
                   "bricht der Baukasten ab und der Fall muss neu gefasst werden."),
        fall("rat-nd-gehalt-stadion-gf", "rat",
             "Wie viel verdient der Geschäftsführer der Stadion Oldenburg GmbH?",
             "nicht-in-daten/sonstiges", [], antwort_in_daten=False,
             notiz="Der Name (Stefan Orth) steht in der Presse, eine Vergütung nirgends — weder "
                   "in Jahresabschluss-Beschlüssen noch in Vorlagen oder Beteiligungsdaten."),
        fall("lotti-nd-waermeplan-wer-dagegen", "lotti",
             "Welche Fraktionen waren hier dagegen?",
             "nicht-in-daten/abstimmung", [], antwort_in_daten=False,
             route="/council/decision", refs={"decision_id": waerme["id"]},
             notiz="Wie rat-nd-waermeplan-wer-dagegen. Richtig: fünf Gegenstimmen, wer, steht "
                   "nicht fest."),
        fall("lotti-nd-person-abstimmung", "lotti",
             "Hat er beim Stadion dafür oder dagegen gestimmt?",
             "nicht-in-daten/abstimmung", [], antwort_in_daten=False,
             route="/council/person", refs={"slug": "christoph-baak"},
             notiz="Das Seiten-Wissen sagt es selbst: „Ein Stimmverhalten gibt es hier nicht“."),
        fall("lotti-nd-sitzung-ergebnisse", "lotti",
             "Welche Ergebnisse hatte diese Sitzung?",
             "nicht-in-daten/offen", [], antwort_in_daten=False,
             route="/council/sitzung", refs={"ksinr": q.sitzung("Rat", "2026-09-28")["ksinr"]},
             notiz="Sitzung am 28.09.2026 — nach dem Datenstand, also ohne Ergebnisse. Richtig "
                   "ist, das zu sagen; Ergebnisse früherer Sitzungen sind es nicht."),
        fall("lotti-nd-ort-einwohner", "lotti",
             "Wie viele Menschen wohnen hier?",
             "nicht-in-daten/sonstiges", [], antwort_in_daten=False,
             route="/council/ort", refs={"place_id": "bloherfelde"},
             notiz="Einwohnerzahlen gibt es nur für die ganze Stadt (council_einwohner), nicht je "
                   "Stadtteil. Die städtische Zahl als Stadtteilzahl zu nennen wäre der Fehler."),
    ]


def baue(q: Quelle) -> list[dict]:
    faelle = (stadion(q) + fliegerhorst(q) + radverkehr_und_baeder(q) + grundsteuer(q)
              + weitere_beschluesse(q) + personen(q) + orte(q) + sitzungen(q) + nicht_in_daten(q))
    ids = [f["id"] for f in faelle]
    erwarte(len(ids) == len(set(ids)), "doppelte Fall-IDs")
    return faelle


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--db", default=str(DB_STANDARD))
    ap.add_argument("--stichtag", default=date.today().isoformat(),
                    help="Bezugstag für „nächste Sitzung“ und laufende Mitgliedschaften")
    ap.add_argument("--pruefen", action="store_true", help="nur vergleichen, nichts schreiben")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(WURZEL))
    faelle = baue(Quelle(Path(args.db), args.stichtag))
    text = json.dumps(faelle, ensure_ascii=False, indent=1) + "\n"
    if args.pruefen:
        alt = FAELLE.read_text(encoding="utf-8") if FAELLE.exists() else ""
        if alt == text:
            print(f"✓ {len(faelle)} Fälle, unverändert")
            return 0
        alte = {f["id"]: f for f in json.loads(alt or "[]")}
        for f in faelle:
            if alte.get(f["id"]) != f:
                print(f"  geändert/neu: {f['id']}")
        return 1
    FAELLE.write_text(text, encoding="utf-8")
    lotti = sum(f["kanal"] == "lotti" for f in faelle)
    offen = sum(not f["antwort_in_daten"] for f in faelle)
    print(f"✓ {len(faelle)} Fälle → {FAELLE.relative_to(WURZEL)} "
          f"({lotti} Lotti, {len(faelle) - lotti} Frag den Rat, {offen} ohne Antwort in den Daten)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
