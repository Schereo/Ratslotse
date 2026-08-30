"""N5 „Morgen wird darüber gesprochen" und N6 „Die Woche im Rat" (Design 30a).

Beide sind Abend-Anlässe um 18 Uhr und beide **standardmäßig aus** — deshalb
wohnen sie in einem Modul und laufen aus einem Cron (``scripts/abendmeldungen.py``):

* **N5 · Vorabend.** Erinnerung für alle, die zuhören gehen oder vorher noch
  eine Mail an ihre Fraktion schreiben wollen. Nutzt ausschließlich die schon
  gespeicherten Treffer aus N1/N2 (``council_agenda_matches`` und die
  Gremien-Abos) — keine neue Klassifikation, kein Sprachmodell.
* **N6 · Wochenüberblick.** Sonntags eine Nachricht für alles. Wer ihn
  einschaltet, kann N1–N3 guten Gewissens ausschalten. Fällt in Sitzungspausen
  ersatzlos aus: Ohne Beschlüsse in der Woche gibt es nichts zu berichten —
  „nie ohne Ereignis" (30a, Grenze 3).

Zur Herkunft von N6: Das Artboard nimmt an, „die Digest-Strecke aus
digest_email.py läuft bereits — sie bekommt nur eine Push-Kurzfassung dazu."
Das trifft nicht zu. ``kern/digest_email.py`` rendert nur die Mail-Hülle
(``render_html_email``); einen wöchentlichen Digest-Job gibt es nicht und gab es
nicht. N6 ist deshalb hier neu gebaut — auf ``council_topic_matches``, also den
Beschluss-Treffern zu den eigenen Themen.
"""
from __future__ import annotations

import html
import logging
from datetime import date, timedelta

from kern import digest_email, notify

logger = logging.getLogger("council.abendmeldungen")

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")


def _datum(iso: str) -> str:
    teile = str(iso or "")[:10].split("-")
    try:
        return f"{int(teile[2])}. {MONATE[int(teile[1]) - 1]}"
    except (ValueError, IndexError):
        return str(iso or "")


# --------------------------------------------------------------- N5 ----------

def _n5_text(sitzung: dict, tops: list[dict]) -> tuple[str, str]:
    """Titel + HTML der Vorabend-Erinnerung.

    Der Titel nennt den **Tag**, nicht „Morgen". Eingereiht wird um 18 Uhr am
    Vorabend, zugestellt aber erst, wenn die Grenzen aus 30a es zulassen: Waren
    an dem Tag schon zwei Meldungen draußen, wartet die Erinnerung bis zum
    nächsten Morgen — und „Morgen, 16:45 Uhr" hieß dann in Wahrheit heute
    (Tims Befund 17.08.2026). Ein Datum stimmt in jedem Fenster.
    """
    zeit = f", {sitzung['session_time']} Uhr" if sitzung.get("session_time") else ""
    wann = f"{_datum(sitzung['session_date'])}{zeit}"
    if tops:
        namen = sorted({t["topic_name"] for t in tops})
        titel = f"{wann}: {namen[0]} im {sitzung['committee']}" if len(namen) == 1 \
            else f"{wann}: deine Themen im {sitzung['committee']}"
        zeilen = "".join(
            f"<li style='margin-bottom:4px'>TOP {t['item_number']} — {t['topic_name']}</li>"
            for t in tops)
        html = (f"<p>{sitzung['committee']} am {_datum(sitzung['session_date'])}{zeit}"
                + (f", {sitzung['location']}" if sitzung.get("location") else "") + ".</p>"
                f"<ul style='margin:0;padding-left:18px'>{zeilen}</ul>")
    else:
        titel = f"{wann}: {sitzung['committee']} tagt"
        html = (f"<p>{sitzung['committee']} am {_datum(sitzung['session_date'])}{zeit}"
                + (f", {sitzung['location']}" if sitzung.get("location") else "") + ".</p>")
    return titel, html


def vorabend(council_store, ratslotse_store, heute: date | None = None) -> int:
    """N5: Für alle Sitzungen von morgen die Erinnerungen einreihen.

    Empfänger sind, wer für diese Sitzung einen Themen-Treffer hat **oder** das
    Gremium abonniert hat — dieselben zwei Wege wie bei N1/N2, nur ohne neue
    Klassifikation.
    """
    heute = heute or date.today()
    morgen = (heute + timedelta(days=1)).isoformat()
    eingereiht = 0

    for sitzung in council_store.sessions_on(morgen):
        ksinr = sitzung.get("ksinr")
        if not ksinr:
            continue  # nur terminiert, ohne Tagesordnung — nichts zu erinnern
        empfaenger: dict[int, list[dict]] = {}
        for owner_id in ratslotse_store.owners_with_agenda_match(ksinr):
            empfaenger[owner_id] = ratslotse_store.agenda_matches_for_owner(
                owner_id, [ksinr]).get(ksinr, [])
        for owner_id in ratslotse_store.owners_subscribed_to(sitzung["committee"]):
            empfaenger.setdefault(owner_id, [])

        for owner_id, tops in empfaenger.items():
            titel, html = _n5_text(sitzung, tops)
            if notify.einreihen(ratslotse_store, owner_id, notify.N5_VORABEND, titel, html,
                                f"/council?tab=sessions&ksinr={ksinr}"):
                eingereiht += 1
    return eingereiht


# --------------------------------------------------------------- N6 ----------

ERGEBNIS_WORT = {
    "angenommen": "angenommen", "abgelehnt": "abgelehnt", "vertagt": "vertagt",
    "zur_kenntnis": "zur Kenntnis genommen", "kein_beschluss": "ohne Beschluss",
}


def _n6_text(beschluesse: list[dict]) -> tuple[str, str]:
    zaehler: dict[str, int] = {}
    for d in beschluesse:
        wort = ERGEBNIS_WORT.get(d.get("outcome") or "", "entschieden")
        zaehler[wort] = zaehler.get(wort, 0) + 1
    n = len(beschluesse)
    titel = f"Diese Woche: {n} {'Beschluss' if n == 1 else 'Beschlüsse'} zu deinen Themen"
    bilanz = ", ".join(f"{k} {w}" for w, k in sorted(zaehler.items(), key=lambda x: -x[1]))
    # Absolute Links: In einer E-Mail gibt es keine Basis, gegen die
    # ``/council/…`` aufgelöst werden könnte — relativ wären sie dort tot.
    zeilen = "".join(
        f"<li style='margin-bottom:6px'>"
        f"<a href=\"{digest_email.absolut(f'/council/decision?id={d["id"]}')}\">"
        f"{html.escape((d.get('title') or 'Beschluss').strip())}</a>"
        f" — {ERGEBNIS_WORT.get(d.get('outcome') or '', 'entschieden')}</li>"
        for d in beschluesse[:10])
    rest = "" if n <= 10 else f"<p>… und {n - 10} weitere.</p>"
    return titel, f"<p>{bilanz}.</p><ul style='margin:0;padding-left:18px'>{zeilen}</ul>{rest}"


def wochenueberblick(council_store, ratslotse_store, heute: date | None = None) -> int:
    """N6: Sonntags eine Nachricht mit den Beschlüssen der Woche zu den eigenen
    Themen. Ohne Treffer passiert nichts — die App schweigt lieber."""
    heute = heute or date.today()
    seit = (heute - timedelta(days=7)).isoformat()
    eingereiht = 0

    for owner_id in ratslotse_store.owners_with_topic_matches_since(seit):
        ids = ratslotse_store.topic_match_decision_ids_since(owner_id, seit)
        if not ids:
            continue
        beschluesse = council_store.get_decisions_by_ids(ids)
        if not beschluesse:
            continue
        titel, html = _n6_text(beschluesse)
        if notify.einreihen(ratslotse_store, owner_id, notify.N6_WOCHE, titel, html, "/topics"):
            eingereiht += 1
    return eingereiht
