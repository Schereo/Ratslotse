"""N3 „Es ist entschieden" — die Ergebnis-Meldung (Design 30a).

Die App weckte bisher **vor** der Debatte und schwieg beim Beschluss: Der
Moment, auf den alles zulief, kam nie an. Diese Meldung schließt den Vorgang.

**Wann sie kommt — und warum nicht am nächsten Morgen.** 30a setzt sie auf den
Tag nach der Sitzung („beschlossen um 22:40, zugestellt um 7 Uhr"). Das gibt die
Quelle nicht her: Beschlüsse entstehen ausschließlich aus dem Protokoll-PDF, und
das erscheint spät. Nachgemessen am 26.07.2026:

* Verkehrsausschuss 16.02. ✓ · 09.03. ✓ · 20.04. ✓ · **08.06. noch keins** (48 Tage)
* Juni-Sitzungen insgesamt: 1 von 15 mit Protokoll
* Rat 01.06.: nach rund 3,5 Wochen da — der Rat ist schneller als die Ausschüsse

Weder die Sitzungsseite noch die Beratungsfolge der Vorlage tragen das Ergebnis
vorher: Auf der Sitzungsseite kommen „angenommen", „abgelehnt", „einstimmig"
kein einziges Mal vor, und ``council_beratungen.ergebnis`` kennt nur
``Kenntnisnahme`` / ``Entscheidung`` / ``Vorberatung`` — die Beratungsart, nicht
das Ergebnis.

Die Meldung sagt deshalb **das Sitzungsdatum dazu**. Sie darf keine Frische
suggerieren, die es nicht gibt: „Beschlossen im Verkehrsausschuss am 8. Juni"
statt eines Textes, der nach „gerade eben" klingt. Ausgelöst wird sie vom
Protokoll-Import (``scripts/check_protocols.py``), nicht von der Sitzung.
"""
from __future__ import annotations

import logging

from nwz import notify

logger = logging.getLogger("council.ergebnisse")

#: Wie ein Ergebnis in der Meldung heißt.
ERGEBNIS_WORT = {
    "angenommen": "angenommen",
    "abgelehnt": "abgelehnt",
    "vertagt": "vertagt",
    "zur_kenntnis": "zur Kenntnis genommen",
    "kein_beschluss": "ohne Beschluss geblieben",
}

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")


def _datum(iso: str) -> str:
    teile = str(iso or "")[:10].split("-")
    try:
        return f"{int(teile[2])}. {MONATE[int(teile[1]) - 1]}"
    except (ValueError, IndexError):
        return str(iso or "")


def _stimmen(d: dict) -> str:
    """„einstimmig" bzw. „mehrheitlich, 11 dagegen" — nur, wenn belegt."""
    teile = []
    if d.get("vote"):
        teile.append(str(d["vote"]))
    if d.get("gegenstimmen"):
        teile.append(f"{d['gegenstimmen']} dagegen")
    if d.get("enthaltungen"):
        teile.append(f"{d['enthaltungen']} Enthaltungen")
    return ", ".join(teile)


def _titel(beschluesse: list[dict]) -> str:
    if len(beschluesse) == 1:
        d = beschluesse[0]
        wort = ERGEBNIS_WORT.get(d.get("outcome") or "", "entschieden")
        return f"{(d.get('title') or 'Dein Thema').strip()}: {wort}"
    return f"{len(beschluesse)} Entscheidungen zu deinen Themen"


def _html(beschluesse: list[dict], committee: str, session_date: str, decision_href) -> str:
    """Der Text der Meldung — mit Sitzungsdatum, weil sie Wochen später kommt."""
    wann = f"{committee} am {_datum(session_date)}"
    if len(beschluesse) == 1:
        d = beschluesse[0]
        wort = ERGEBNIS_WORT.get(d.get("outcome") or "", "entschieden")
        stimmen = _stimmen(d)
        satz = f"Im {wann} {wort}" + (f" ({stimmen})" if stimmen else "") + "."
        return (f"<p>{satz}</p>\n"
                f'<p><a href="{decision_href(d["id"])}">Zum Beschluss →</a></p>')
    zeilen = [f"<p>Im {wann} entschieden:</p>", "<ul style='margin:0;padding-left:18px'>"]
    for d in beschluesse:
        wort = ERGEBNIS_WORT.get(d.get("outcome") or "", "entschieden")
        titel = (d.get("title") or "Beschluss").strip()
        zeilen.append(f'<li style="margin-bottom:6px">'
                      f'<a href="{decision_href(d["id"])}">{titel}</a> — {wort}</li>')
    zeilen.append("</ul>")
    return "\n".join(zeilen)


def decision_href(decision_id: int) -> str:
    """Ziel einer Ergebnis-Meldung — die Beschluss-Seite (30a, Grenze 4).
    Spiegelt web/frontend/lib/routes.ts (Query-Parameter statt Pfad-Segment,
    damit der (app)-Bereich statisch exportierbar bleibt)."""
    return f"/council/decision?id={decision_id}"


def melde_ergebnisse(council_store, nwz_store, ksinrs: list[int]) -> int:
    """Für frisch geparste Sitzungen die Ergebnis-Meldungen einreihen.

    Empfänger sind die Konten, denen zu **dieser** Sitzung schon ein
    Tagesordnungspunkt gemeldet wurde (aus N1/N2) — der Vorgang, den sie kennen,
    bekommt seinen Abschluss. Wer nie etwas dazu gehört hat, wird jetzt nicht
    nachträglich behelligt.

    Mehrere Treffer einer Sitzung werden zu **einer** Meldung zusammengefasst;
    die Tagesgrenze aus nwz.notify käme sonst schnell ins Spiel.
    """
    eingereiht = 0
    for ksinr in ksinrs:
        sitzung = council_store.get_session(ksinr)
        if not sitzung:
            continue
        alle = {str(d.get("item_number") or ""): d
                for d in council_store.get_decisions(ksinr) if d.get("kind") != "subvote"}
        if not alle:
            continue

        for owner_id in nwz_store.owners_with_agenda_match(ksinr):
            if nwz_store.result_already_sent(ksinr, owner_id):
                continue
            tops = {m["item_number"] for m in
                    nwz_store.agenda_matches_for_owner(owner_id, [ksinr]).get(ksinr, [])}
            treffer = [alle[t] for t in sorted(tops) if t in alle and alle[t].get("outcome")]
            if not treffer:
                # Kein Ergebnis zu genau diesen TOPs (vertagt ohne Eintrag,
                # abweichende Nummerierung) — dann lieber schweigen.
                nwz_store.mark_result_sent(ksinr, owner_id)
                continue
            notify.einreihen(
                nwz_store, owner_id, notify.N3_ERGEBNIS,
                _titel(treffer),
                _html(treffer, sitzung["committee"], sitzung["session_date"], decision_href),
                decision_href(treffer[0]["id"]),
            )
            nwz_store.mark_result_sent(ksinr, owner_id)
            eingereiht += 1
            logger.info("N3 für owner %s, Sitzung %s: %d Beschluss/Beschlüsse",
                        owner_id, ksinr, len(treffer))
    return eingereiht
