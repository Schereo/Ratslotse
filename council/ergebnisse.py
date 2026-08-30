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

from urllib.parse import quote
import logging

from kern import notify
from council import bookmarks as bookmark_logic

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


def datum_lang(iso: str) -> str:
    """„7. März 2026" — mit Jahr, im Gegensatz zu ``_datum``.

    Die Protokoll-Meldung darf das Jahr weglassen: Sie kommt Wochen nach der
    Sitzung, das Jahr ist dasselbe. Der Wochenabgleich meldet dagegen alles aus
    einem halben Jahr, und ein halbes Jahr reicht über den Jahreswechsel —
    „7. März" wäre dort im Januar schlicht mehrdeutig.
    """
    teile = str(iso or "")[:10].split("-")
    try:
        return f"{int(teile[2])}. {MONATE[int(teile[1]) - 1]} {int(teile[0])}"
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


def sitzung_href(ksinr: int, tops: list[str] | None = None) -> str:
    """Ziel einer Tagesordnungs-Meldung — die Sitzung in der App (30a, Grenze 4).

    Bewusst ein App-Pfad und NICHT die Ratsinfo-Adresse: Der Tap-Handler der App
    (``lib/push.ts``) navigiert nur zu Zielen, die mit ``/`` beginnen. Mit der
    externen URL tat ein Antippen wortlos nichts und die App blieb auf der
    Startseite stehen. Der Ratsinfo-Link gehört in den Meldungstext.

    ``tops`` nennt die Tagesordnungspunkte, um die es in der Meldung geht — die
    App springt dann nicht nur zur Sitzung, sondern zu genau diesen Zeilen. Die
    Nummern gehen **vollständig** mit (``"Ö 6"``, nicht ``"6"``): ``Ö 6`` und
    ``N 6`` sind verschiedene Punkte, ein öffentlicher und ein nichtöffentlicher.

    Spiegelt ``sessionHref`` aus web/frontend/lib/routes.ts.
    """
    ziel = f"/council?tab=sessions&ksinr={ksinr}"
    sauber = [t.strip() for t in (tops or []) if t and t.strip()]
    if sauber:
        ziel += "&top=" + quote(",".join(sauber))
    return ziel


def melde_ergebnisse(council_store, ratslotse_store, ksinrs: list[int]) -> int:
    """Für frisch geparste Sitzungen die Ergebnis-Meldungen einreihen.

    Empfänger sind die Konten, denen zu **dieser** Sitzung schon ein
    Tagesordnungspunkt gemeldet wurde (aus N1/N2) — der Vorgang, den sie kennen,
    bekommt seinen Abschluss. Wer nie etwas dazu gehört hat, wird jetzt nicht
    nachträglich behelligt.

    Mehrere Treffer einer Sitzung werden zu **einer** Meldung zusammengefasst;
    die Tagesgrenze aus kern.notify käme sonst schnell ins Spiel.
    """
    eingereiht = 0
    for ksinr in ksinrs:
        sitzung = council_store.get_session(ksinr)
        if not sitzung:
            continue
        alle = {str(d.get("item_number") or ""): d
                for d in council_store.get_decisions(ksinr) if d.get("kind") != "subvote"}

        # Ein ausdrücklich abonnierter Merkeintrag ist ein zweiter, engerer
        # Weg zum selben Ereignis. Beide Wege hier zusammenführen, damit ein
        # Konto mit Themen-Treffer UND gemerktem TOP nicht zweimal dieselbe
        # Protokoll-Veröffentlichung bekommt.
        bookmark_rows = ratslotse_store.bookmark_result_targets(ksinr)
        konkrete_bookmarks = []
        for row in bookmark_rows:
            resolved = bookmark_logic.resolve_bookmark(row, council_store)
            if resolved.get("agenda_group"):
                # Altbestand: Oberpunkte wurden vor der Blatt-TOP-Regel noch
                # akzeptiert. Kein Ergebnis versprechen, das es nicht gibt.
                ratslotse_store.set_bookmark_result_notification(row["owner_id"], row["id"], False)
                continue
            konkrete_bookmarks.append(row)
        bookmark_rows = konkrete_bookmarks
        bookmarks_by_owner: dict[int, list[dict]] = {}
        for row in bookmark_rows:
            bookmarks_by_owner.setdefault(row["owner_id"], []).append(row)
        owners = set(ratslotse_store.owners_with_agenda_match(ksinr)) | set(bookmarks_by_owner)
        if not alle and not bookmarks_by_owner:
            continue

        for owner_id in sorted(owners):
            eigene_bookmarks = bookmarks_by_owner.get(owner_id, [])
            if ratslotse_store.result_already_sent(ksinr, owner_id):
                ratslotse_store.mark_bookmark_results_notified([b["id"] for b in eigene_bookmarks])
                continue
            tops = {m["item_number"] for m in
                    ratslotse_store.agenda_matches_for_owner(owner_id, [ksinr]).get(ksinr, [])}
            treffer = [alle[t] for t in sorted(tops) if t in alle and alle[t].get("outcome")]
            # Gemerkte TOPs gegen den aktuellen Stand auflösen — nicht stumpf
            # über die gespeicherte Nummer, denn die kann sich bis zur Sitzung
            # verschoben haben.
            for bookmark in eigene_bookmarks:
                d = bookmark_logic.resolve_bookmark(bookmark, council_store).get("decision")
                if d and d.get("outcome") and all(x.get("id") != d.get("id") for x in treffer):
                    treffer.append(d)
            if not treffer:
                # Für einen ausdrücklich gemerkten TOP ist auch „Protokoll da,
                # aber kein eigener Beschluss erkannt" eine nützliche und
                # ehrliche Antwort. Themen-Treffer allein bleiben wie bisher
                # still, wenn keine belastbare Entscheidung vorliegt.
                if eigene_bookmarks:
                    erster = eigene_bookmarks[0]
                    titel = erster.get("title") or "Gemerkter Tagesordnungspunkt"
                    top_liste = [str(b.get("item_number") or "") for b in eigene_bookmarks]
                    ziel = sitzung_href(ksinr, top_liste)
                    queued = notify.einreihen(
                        ratslotse_store, owner_id, notify.N3_ERGEBNIS,
                        f"Protokoll ist da: {titel}",
                        (f"<p>Das Protokoll des {sitzung['committee']} vom "
                         f"{_datum(sitzung['session_date'])} ist veröffentlicht.</p>"
                         "<p>Für den gemerkten TOP wurde kein eigener Beschluss erkannt — "
                         "etwa weil er abgesetzt, nur beraten oder als Formalie behandelt wurde.</p>"
                         f'<p><a href="{ziel}">Zum gemerkten TOP →</a></p>'),
                        ziel,
                    )
                    if queued:
                        eingereiht += 1
                ratslotse_store.mark_result_sent(ksinr, owner_id)
                ratslotse_store.mark_bookmark_results_notified([b["id"] for b in eigene_bookmarks])
                continue
            notify.einreihen(
                ratslotse_store, owner_id, notify.N3_ERGEBNIS,
                _titel(treffer),
                _html(treffer, sitzung["committee"], sitzung["session_date"], decision_href),
                decision_href(treffer[0]["id"]),
            )
            ratslotse_store.mark_result_sent(ksinr, owner_id)
            ratslotse_store.mark_bookmark_results_notified([b["id"] for b in eigene_bookmarks])
            eingereiht += 1
            logger.info("N3 für owner %s, Sitzung %s: %d Beschluss/Beschlüsse",
                        owner_id, ksinr, len(treffer))
    return eingereiht
