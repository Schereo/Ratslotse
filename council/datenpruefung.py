"""Stehende Datenprüfungen — was im Bestand nie vorkommen darf, einmal am Tag
nachgezählt (Plan „Akte“, Phase 6; ``docs/plan-akte.md``).

**Wozu.** Die Fehler vom Herbst 2026 hatten eins gemeinsam: Sie standen
wochenlang im Bestand, bevor eine Antwort sie sichtbar machte. Die Antworten
der Verwaltung lagen im ``answer``-Feld der Ratsbeiträge (Sprenger und Piening
unter Behrens, entdeckt am 30.09.); „gilt als behandelt“ stand als
„angenommen“ da; Kurzfassungen nannten abgelehnte Anträge beschlossen. Jede
Regel hier hat entweder schon einmal eine falsche Antwort erzeugt oder hält
fest, was der Akten-Aufbau garantieren soll.

**Wie oft gemeldet wird.** Der Herzschlag (``scripts/check_herzschlag.py``)
ruft das einmal am Tag. Zwei Sorten Regeln:

- **Bestandsregeln** — im ganzen Bestand null Verstöße gemessen. Jeder
  Verstoß wird gemeldet, solange er steht; die Behebung ist ein Ops-Lauf.
- **Stromregeln** — über das, was NEU ist: seit dem letzten Lauf extrahierte
  Beiträge, Sitzungen, die seitdem die Protokoll-Frist überschritten haben.
  Sonst käme jeden Tag dieselbe Mail über denselben Altfall.

Die Kennzahlen stehen außerdem in ``job_runs`` (Admin-Panel → Cron-Jobs),
auch wenn nichts gemeldet wird.

**Gemessen am Prod-Abzug vom 01.10.2026** — daher die Schwellen:

| Regel | Bestand |
|---|---|
| Ergebnis widerspricht dem Abstimmungssatz | 0 von 8.674 Hauptpunkten |
| Kurzfassung nennt nicht Gefasstes als gefasst | 387 Sätze + 43 „einfach erklärt“ im Altbestand, seit Juli 0 |
| Antwort im Feld eines Ratsbeitrags | 0 von 52.804 (nach der Neuextraktion vom 30.09.) |
| eine Person, zwei Parteien in einer Sitzung | 24 im ganzen Bestand, 3 in 2026 |
| Protokoll fehlt nach 10 Wochen | 2 von 62 Sitzungen seit April |
| Hauptpunkt ohne Grundakte | 0 (599 in 2026) |
| Wortbeiträge ohne Grundakte | 19–25 % (Mitteilungen, Anfragen, Fragestunde) |
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from council.outcome_note import NOT_ADOPTED, states_outcome
from council.parties import normalize_party
from council.votes import normalize_outcome

#: Ab wann ein fehlendes Protokoll gemeldet wird. Die Stadt stellt Protokolle
#: nach 4–7 Wochen ein (Plan, Phase 0.5); zehn Wochen liegen klar dahinter.
PROTOKOLL_FRIST_TAGE = 70
#: Wie weit die Kurzfassungs-Regel zurückschaut. Der Altbestand (vor #1497)
#: wäre sonst eine tägliche Mail ohne Neuigkeit; seit Juli steht dort 0.
KURZFASSUNG_TAGE = 120
#: Die Grundakten werden nächtlich in ``check_protocols`` gebaut.
AKTEN_ALTER_H = 36
#: Über welchen Zeitraum die Akten-Regeln zählen.
AKTEN_FENSTER_TAGE = 90
#: Anteil der Wortbeiträge ohne Grundakte, ab dem die Kopplung über den
#: TOP als kaputt gilt — gemessen 19–25 %. Erst ab ``AKTEN_MIN_BEITRAEGE``,
#: ein ruhiges Quartal hat sonst zu wenig für einen Anteil.
BEITRAEGE_OHNE_AKTE_MAX = 0.40
AKTEN_MIN_BEITRAEGE = 200
#: So viele Kennungen nennt eine Meldung höchstens.
ZEIGEN = 5


def _ids(werte: list) -> str:
    rest = len(werte) - ZEIGEN
    return ", ".join(str(w) for w in werte[:ZEIGEN]) + (f" und {rest} weitere" if rest > 0 else "")


def ergebnis_gegen_rohtext(store: Any) -> list[int]:
    """Hauptpunkte, deren ``outcome`` dem Abstimmungssatz widerspricht."""
    return [r["id"] for r in store.pruef_hauptbeschluesse()
            if normalize_outcome(r["outcome"], r["raw_result"], "decision") != r["outcome"]]


def kurzfassung_ohne_ergebnis(store: Any, seit_datum: str) -> list[tuple[int, str]]:
    """(id, Feld) der nicht gefassten Hauptpunkte, deren Kurzfassung das
    Ergebnis nicht nennt (``outcome_note.states_outcome``)."""
    return [(r["id"], feld) for r in store.pruef_hauptbeschluesse(seit_datum)
            if r["outcome"] in NOT_ADOPTED
            for feld in ("summary", "simple_summary")
            if not states_outcome(r["outcome"], r[feld])]


def antwort_im_beitrag(beitraege: list[dict]) -> list[int]:
    """Ratsbeiträge mit gefülltem ``answer`` — der Fehler vom 30.09.2026:
    Die Antwort der Verwaltung gehört in einen eigenen Eintrag."""
    return [b["id"] for b in beitraege
            if b["kind"] == "speech" and (b.get("answer") or "").strip()]


def partei_widerspruch(beitraege: list[dict]) -> list[tuple[int, str, list[str]]]:
    """(Sitzung, Person, Parteien): eine Person mit zwei Parteien in einer
    Sitzung. Schreibweisen zählen nicht (``parties.normalize_party``)."""
    je: dict[tuple[int, str], set[str]] = defaultdict(set)
    for b in beitraege:
        partei = normalize_party(b.get("party"))
        if partei and b.get("speaker"):
            je[(b["ksinr"], b["speaker"])].add(partei)
    return [(ks, sp, sorted(p)) for (ks, sp), p in sorted(je.items()) if len(p) > 1]


def protokoll_verzug(store: Any, seit: date, heute: date) -> list[dict]:
    """Sitzungen, die seit ``seit`` die Protokoll-Frist überschritten haben —
    jede genau einmal, an dem Tag, an dem sie drüber fällt."""
    frist = timedelta(days=PROTOKOLL_FRIST_TAGE)
    von, bis = seit - frist + timedelta(days=1), heute - frist
    if von > bis:
        return []
    return store.pruef_sitzungen_ohne_beschluss(von.isoformat(), bis.isoformat())


def _stunden_seit(zeitpunkt: str, jetzt: datetime) -> float:
    t = datetime.fromisoformat(zeitpunkt)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return round((jetzt - t).total_seconds() / 3600, 1)


def pruefen(store: Any, seit: str, jetzt: datetime | None = None) -> dict:
    """Alle Regeln. ``seit``: Beginn des Fensters für Neues (UTC, ISO, ohne
    Zone — so stehen ``extracted_at`` und ``job_runs.started_at``).

    Gibt ``{"kennzahlen": {...}, "befunde": [Text, …]}`` zurück; ein Befund
    ist ein fertiger Absatz für die Mail.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    heute = jetzt.date()
    k: dict[str, Any] = {}
    befunde: list[str] = []

    falsch = ergebnis_gegen_rohtext(store)
    k["ergebnis_widerspricht"] = len(falsch)
    if falsch:
        befunde.append(
            f"<b>{len(falsch)} Ergebnis(se) widersprechen dem Abstimmungssatz</b> "
            f"(Beschluss {_ids(falsch)}) — etwa „gilt als behandelt“ als angenommen. "
            "Beheben: <code>ops-settled-ergebnis.yml</code>.")

    kurz = kurzfassung_ohne_ergebnis(store, (heute - timedelta(days=KURZFASSUNG_TAGE)).isoformat())
    k["kurzfassung_ohne_ergebnis"] = len(kurz)
    if kurz:
        befunde.append(
            f"<b>{len(kurz)} Kurzfassung(en) nennen einen nicht gefassten Beschluss "
            f"nicht als solchen</b> (Beschluss/Feld {_ids([f'{i}/{f}' for i, f in kurz])}). "
            "Beheben: <code>ops-settled-ergebnis.yml modus=kurzfassungen</code>.")

    beitraege = store.pruef_beitraege_seit(seit)
    k["beitraege_neu"] = len(beitraege)
    antwort = antwort_im_beitrag(beitraege)
    k["antwort_im_beitrag"] = len(antwort)
    if antwort:
        befunde.append(
            f"<b>{len(antwort)} neue Ratsbeiträge tragen eine Antwort im eigenen Feld</b> "
            f"(Beitrag {_ids(antwort)}) — die Antwort der Verwaltung gehört in einen "
            "eigenen Eintrag. Das war der Fehler vom 30.09.2026; die Extraktion ist "
            "zurückgefallen.")
    zwei = partei_widerspruch(beitraege)
    k["partei_widerspruch"] = len(zwei)
    if zwei:
        befunde.append(
            f"<b>{len(zwei)} Person(en) mit zwei Parteien in einer Sitzung</b>: "
            + _ids([f"{sp} ({' / '.join(p)}, Sitzung {ks})" for ks, sp, p in zwei]) + ".")

    seit_tag = datetime.fromisoformat(seit).date()
    verzug = protokoll_verzug(store, seit_tag, heute)
    k["protokoll_ueberfaellig_neu"] = len(verzug)
    if verzug:
        befunde.append(
            f"<b>Seit über {PROTOKOLL_FRIST_TAGE // 7} Wochen kein Protokoll</b>: "
            + _ids([f"{s['committee']} am {s['session_date']}" for s in verzug])
            + ". Üblich sind 4–7 Wochen — fehlt es bei der Stadt oder bei uns?")

    stand = store.pruef_akten_stand()
    if stand is None:
        k["akten"] = "keine"
    else:
        alter = _stunden_seit(stand, jetzt)
        k["akten_alter_h"] = alter
        if alter > AKTEN_ALTER_H:
            befunde.append(
                f"<b>Die Grundakten sind {alter} Stunden alt</b> — der nächtliche Aufbau in "
                "<code>check_protocols</code> lief nicht. Von Hand: "
                "<code>scripts/build_matters.py</code>.")
        fenster = (heute - timedelta(days=AKTEN_FENSTER_TAGE)).isoformat()
        waisen = store.pruef_akten_waisen(fenster)
        k["akten_waisen"] = len(waisen)
        if waisen:
            befunde.append(
                f"<b>{len(waisen)} Hauptpunkt(e) ohne Grundakte</b> (Beschluss {_ids(waisen)}) "
                "— jeder Beschluss gehört in genau eine.")
        alle, ohne = store.pruef_beitraege_ohne_akte(fenster)
        anteil = round(ohne / alle, 3) if alle else 0.0
        k["beitraege_ohne_akte_anteil"] = anteil
        if alle >= AKTEN_MIN_BEITRAEGE and anteil > BEITRAEGE_OHNE_AKTE_MAX:
            befunde.append(
                f"<b>{anteil:.0%} der Wortbeiträge ohne Grundakte</b> ({ohne} von {alle}, "
                f"{AKTEN_FENSTER_TAGE} Tage; üblich 19–25 %) — die Kopplung über den TOP "
                "greift nicht mehr.")

    k["befunde"] = len(befunde)
    return {"kennzahlen": k, "befunde": befunde}
