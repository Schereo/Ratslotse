"""Woher die Zahlen des Haushalts-Bereichs kommen — gezählt, nicht behauptet.

Die Frage, die ``finanzquellen.datenstand`` beantwortet, ist „bis wann reichen
die Zahlen?". Diese hier ist die Nachbarfrage: „Wie viel steckt dahinter?" —
wie viele Zahlen aus wie vielen Dokumenten, wie viele Seiten zitiert, welche
Proben sie beim Einlesen bestanden haben.

Gezählt wird aus dem Bestand bei jedem Aufruf (mit zehn Minuten Puffer), nicht
aus einer gepflegten Liste: Eine Zahl, die jemand von Hand nachziehen müsste,
wäre am Tag nach dem nächsten Ingest falsch.

**Was als „Zahl" zählt:** jede numerische Zelle einer Datentabelle, außer den
Schlüsseln — Jahre, Seiten, Kennungen, Laufnummern, Belegverweise. Das ist
eine Zählung von Werten, keine von Euro-Beträgen: Quoten und Einwohnerzahlen
gehören dazu. Deshalb steht sie im Frontend als „rund".

**Was als „Dokument" zählt:** ein eigenständiger Beleg in
``council_provenance`` — eine Ratsanlage (``document_id``) oder eine Adresse
(Liste, Datensatz, Portalseite). Ein Beleg, auf den keine Zeile mehr zeigt,
zählt nicht.
"""
from __future__ import annotations

import re
import time

from council import finanzquellen, herkunft

#: Spalten, die einen Wert ADRESSIEREN statt ihn zu tragen.
_SCHLUESSEL = re.compile(
    r"(^|_)(id|year|years|page|pages|seq|nr|no|number|rank|ksinr|kvonr|position|level|"
    r"supplement|month|sort|order|depth|row|line)$|_id$|^year_|_year$|^budget_year")

_PUFFER: dict[str, tuple[float, dict]] = {}
PUFFER_SEKUNDEN = 600


def _spalten(conn, tabelle: str) -> list[str] | None:
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
    except Exception:  # noqa: BLE001 — eine fehlende Tabelle ist kein Fehler
        return None


def _tabelle(conn, tabelle: str) -> dict | None:
    """Zeilen, Zahlen und Belege EINER Tabelle."""
    spalten = _spalten(conn, tabelle)
    if not spalten:
        return None
    zeilen = conn.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]
    werte = [c for c in spalten if not _SCHLUESSEL.search(c)]
    zahlen = 0
    if werte and zeilen:
        summe = " + ".join(f"(typeof({c}) IN ('real','integer'))" for c in werte)
        zahlen = conn.execute(f"SELECT SUM({summe}) FROM {tabelle}").fetchone()[0] or 0
    belege = ({r[0] for r in conn.execute(
        f"SELECT DISTINCT herkunft_id FROM {tabelle} WHERE herkunft_id IS NOT NULL")}
        if "herkunft_id" in spalten else set())
    return {"rows": zeilen, "numbers": int(zahlen), "belege": belege}


def zaehle(store) -> dict:
    """Gesamtzahlen und je Datenschicht (``finanzquellen.REIHENFOLGE``)."""
    conn = store._conn
    # Nach dem SCHEMA, nicht nach ``herkunft.HERKUNFT_TABELLEN``: Die Liste
    # ist die Anweisung fürs Anlegen, und fünf Tabellen mit eigener
    # ``herkunft_id`` stehen gar nicht darin (Kennzahlen, Satzung,
    # Wirtschaftspläne, Eigenbetriebs-Abschlüsse) — gezählt hätten sie null.
    namen = sorted(set(store._herkunft_verweistabellen()) | set(herkunft.HERKUNFT_TABELLEN))
    je_tabelle = {t: z for t in namen if (z := _tabelle(conn, t))}
    belege = {r[0]: r for r in conn.execute(
        "SELECT id, kind, document_id, url, page, probe FROM council_provenance")}

    def dokumente(ids: set[int]) -> set[tuple[str, str]]:
        return {(belege[i][1], str(belege[i][2] or belege[i][3])) for i in ids if i in belege}

    # Schichten, die dieselben Tabellen füllen, sind EINE Zeile: Die vier
    # Vergleiche teilen sich ``council_city_comparison`` und stünden sonst
    # viermal mit denselben 1.147 Werten da.
    gruppen: dict[tuple[str, ...], list] = {}
    for key in finanzquellen.REIHENFOLGE:
        q = finanzquellen.QUELLEN[key]
        gruppen.setdefault((q.tabelle, *q.nebentabellen), []).append(q)
    schichten = []
    for tabellen, qs in gruppen.items():
        teile = [je_tabelle[t] for t in tabellen if t in je_tabelle]
        ids = set().union(*(t["belege"] for t in teile)) if teile else set()
        stellen = list(dict.fromkeys(finanzquellen.STELLEN.get(q.herkunft, q.herkunft) for q in qs))
        schichten.append({
            "keys": [q.key for q in qs], "labels": [q.label for q in qs],
            "sources": stellen,
            "tables": len(teile),
            "rows": sum(t["rows"] for t in teile),
            "numbers": sum(t["numbers"] for t in teile),
            "documents": len(dokumente(ids)),
        })

    # Was keine Schicht als Zieltabelle führt (Änderungslisten, Spenden,
    # Hebesätze, Bürgschaften …) — sonst gingen Kopf und Liste nicht auf.
    in_schichten = {t for tabellen in gruppen for t in tabellen}
    rest = [z for t, z in je_tabelle.items() if t not in in_schichten and z["rows"]]
    rest_ids = set().union(*(t["belege"] for t in rest)) if rest else set()
    uebrige = {"tables": len(rest), "rows": sum(t["rows"] for t in rest),
               "numbers": sum(t["numbers"] for t in rest), "documents": len(dokumente(rest_ids))}

    alle_ids = set().union(*(t["belege"] for t in je_tabelle.values())) if je_tabelle else set()
    genutzt = [belege[i] for i in alle_ids if i in belege]
    docs = dokumente(alle_ids)
    je_stelle: dict[str, int] = {}
    for art, _ in docs:
        je_stelle[art] = je_stelle.get(art, 0) + 1
    proben = [p.strip() for b in genutzt for p in (b[5] or "").split(",") if p.strip()]
    return {
        "numbers": sum(t["numbers"] for t in je_tabelle.values()),
        "rows": sum(t["rows"] for t in je_tabelle.values()),
        "tables": sum(1 for t in je_tabelle.values() if t["rows"]),
        "documents": len(docs),
        "citations": len(genutzt),
        "probe_kinds": len(set(proben)),
        "probe_runs": len(proben),
        "sources": [{"kind": k, "label": finanzquellen.STELLEN.get(k, k), "documents": n}
                    for k, n in sorted(je_stelle.items(), key=lambda x: -x[1])],
        "layers": schichten,
        "other": uebrige,
    }


def gepuffert(store, schluessel: str) -> dict:
    """``zaehle`` mit zehn Minuten Puffer je Datenbank — die Zählung liest
    jede Datentabelle einmal ganz."""
    jetzt = time.monotonic()
    treffer = _PUFFER.get(schluessel)
    if treffer and jetzt - treffer[0] < PUFFER_SEKUNDEN:
        return treffer[1]
    aus = zaehle(store)
    _PUFFER[schluessel] = (jetzt, aus)
    return aus
