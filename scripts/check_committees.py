#!/usr/bin/env python3
"""Send committee meeting summaries to subscribed users.
Run daily via cron: 0 7 * * *
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from kern import notify
from kern.store import Store
from kern import digest_email
from council.store import CouncilStore
from council.scraper import CouncilScraper
from council.agenda_diff import (anlagen_schluessel, diff_html, diff_satz,
                                 diff_tagesordnung, hat_aenderungen,
                                 nur_nummern_versatz)
from council import social_text
from council.committee_summary import sitzungskopf, summarize_agenda_items
from council.dringlichkeit import ist_dringlichkeitsantrag
from council.ergebnisse import sitzung_href

RATSLOTSE_DB = ROOT / "data" / "ratslotse.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _agenda_hash(agenda_items) -> str:
    """Stable fingerprint of the agenda; changes if any item is added/edited/removed.

    Seit 18.08.2026 zählen auch die Anhänge (per getfile-id) mit — eine neue
    Anlage an einem TOP ist eine meldenswerte Änderung (Tims Wunsch). Der
    einmalige Hash-Sprung durch die Formatänderung bleibt stumm: Der Diff
    gegen den alten Snapshot findet nichts Nennbares, und genau dieser Fall
    zieht den Stand nur nach, ohne zu melden."""
    payload = "\n".join(
        f"{i.item_number}\t{i.title}\t{i.template_number or ''}\t{int(i.is_public)}\t"
        f"{','.join(anlagen_schluessel(i.anlagen))}"
        for i in agenda_items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stunden_bis(session_date: str, session_time: str) -> float:
    """Stunden von jetzt bis zum Sitzungsbeginn — negativ, wenn sie vorbei ist.

    Für das 48-Stunden-Fenster der Änderungsmeldung (Design 30a). Ohne
    brauchbare Zeitangabe zählt 18 Uhr; Ratssitzungen beginnen abends, und die
    Entscheidung „noch melden oder nicht" verträgt die Unschärfe.
    """
    from datetime import datetime

    try:
        tag = datetime.strptime(str(session_date)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0.0  # unbekanntes Datum → wie „steht kurz bevor" behandeln
    stunde, minute = 18, 0
    try:
        stunde, minute = (int(x) for x in str(session_time or "")[:5].split(":"))
    except ValueError:
        pass
    beginn = tag.replace(hour=stunde, minute=minute)
    return (beginn - datetime.now()).total_seconds() / 3600


_ALT_LINK = re.compile(r"\s*<a href=\"[^\"]*si0057[^\"]*\">[^<]*</a>\s*$")
_ALT_KOPF = re.compile(r"\A<b>[^<]*</b>\n📅[^\n]*\n(?:📍[^\n]*\n)?\n")


def _kartentexte(council_store: CouncilStore, ksinr: int) -> dict[str, str]:
    """Kartentexte dieser Sitzung — fehlende sofort schreiben.

    Warum hier und nicht erst im Nachtlauf (Tims Auftrag 30.08.26): Diese Mail
    geht raus, sobald eine Tagesordnung erscheint. ``social_kartentexte.py``
    läuft am nächsten Morgen um 7:45 — die Mail trüge bis dahin die
    titelbasierte Kurzfassung („Der Ausschuss berät über den Bebauungsplan
    837") statt des Satzes aus Vorlage und Anlagen („Geplant ist ein
    Wohngebiet auf 8,6 Hektar nördlich Eßkamp mit 110 Wohneinheiten"). Und
    weil der Block der Mail gecacht wird (``save_summary``), stünde die
    schwächere Fassung dort dauerhaft fest.

    Teurer wird es dadurch nicht: Die Texte würden ohnehin geschrieben, nur
    später — ``agenda_item_social`` ist der Zwischenspeicher für beide Wege.

    Best effort, wie die Kurzfassungen selbst: Schlägt der Lauf fehl, nimmt
    die Mail, was schon da ist. Eine Sitzung mit außergewöhnlich langer
    Tagesordnung wird gedeckelt (``social_text.MAIL_MAX``); was übrig bleibt,
    holt der Nachtlauf — und es steht im Log, statt still zu fehlen.
    """
    try:
        gesucht, geschrieben = social_text.schreibe_fehlende(
            council_store, ksinr=ksinr, limit=social_text.MAIL_MAX)
        if gesucht:
            print(f"  Kartentexte: {geschrieben}/{gesucht} geschrieben")
        if gesucht >= social_text.MAIL_MAX:
            print(f"  ⚠️ Deckel bei {social_text.MAIL_MAX} Punkten erreicht — "
                  f"der Rest bekommt seinen Kartentext im Nachtlauf")
    except Exception as exc:  # noqa: BLE001 — Anreicherung ist Kür, nie Blocker
        print(f"  ⚠️ Kartentexte für {ksinr} fehlgeschlagen: {exc!r} — "
              f"die Mail nimmt die Kurzfassungen")
    try:
        return council_store.agenda_social_texts(ksinr)
    except Exception:  # noqa: BLE001
        return {}


def _aufzaehlung(council_store: CouncilStore, ksinr: int, punkte: list[dict]) -> str:
    """Die Aufzählung der Mail — je Punkt der bessere der beiden Sätze.

    Der Kartentext schlägt die Kurzfassung, weil er Vorlage UND Anlagen
    gesehen hat; die Kurzfassung entsteht allein aus dem Titel und bleibt der
    Rückfall (dieselbe Reihenfolge wie in der App, ``store.agenda_items``).

    Und die Kennung eines Dringlichkeitsantrags heißt in der Mail, was sie
    ist: „DZT 1" ist eine Nummer, die wir selbst vergeben haben — im
    Ratsinformationssystem sucht man sie vergeblich.
    """
    kartentexte = _kartentexte(council_store, ksinr)
    zeilen = []
    for p in punkte:
        nummer = p["number"]
        text = kartentexte.get(nummer) or p["summary"]
        mark = "Dringlichkeitsantrag" if ist_dringlichkeitsantrag(nummer) else nummer
        zeilen.append(f"• <b>{mark}</b>: {text}")
    return "\n".join(zeilen)


def _ohne_altlink(summary: str | None) -> str | None:
    """Gecachte Zusammenfassungen aus der Zeit, als `summarize_agenda` den
    Ratsinfo-Link selbst anhängte. Ohne diesen Schnitt stünden in der Mail zwei
    Wege zur Tagesordnung — der alte im Text, der neue als Knopf darunter.
    Neu erzeugte Zusammenfassungen enthalten den Link nicht mehr, der Ausdruck
    trifft dann einfach nichts."""
    return summary if summary is None else _ALT_LINK.sub("", summary)


def _ohne_altkopf(summary: str | None) -> str | None:
    """Dasselbe für den Kopf, den `summarize_agenda` früher mitcachte.

    In diesen Altbeständen steckt eine Ortsmarke ohne Ort (der Ort fehlte in
    den Sitzungsdaten). Der Kopf kommt jetzt frisch vom Aufrufer — der alte
    muss also weg, sonst stünde er zweimal in der Mail, einmal davon falsch.
    """
    return summary if summary is None else _ALT_KOPF.sub("", summary)


def _push_kurz(html: str, limit: int = 180) -> str:
    """HTML zu einem Push-tauglichen Kurztext einstampfen — wie
    ``kern.delivery._plain``, nur ohne den Mail-Kopf davor."""
    t = re.sub(r"<[^>]+>", "", html or "")
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: limit - 1] + "…") if len(t) > limit else t


def _diff_fuer(alt: list[dict] | None, jetzt: list[dict]) -> dict | None:
    """Der Diff zweier Stände mit den Migrations-Schutzgittern — oder ``None``
    ohne Vergleichsbasis (Stand von vor der Snapshot-Zeit)."""
    if alt is None:
        return None
    # Altbestand: Snapshots von vor dem 17.08.2026 enthalten nur die
    # öffentlichen Punkte und kein is_public. Gegen die neue Vollliste
    # verglichen gälte jeder nichtöffentliche TOP als frisch eingefügt —
    # deshalb wird dann auch die neue Seite auf die öffentlichen beschnitten.
    if not any("is_public" in i for i in alt):
        jetzt = [i for i in jetzt if i.get("is_public", True)]
    # Gleiche Migrations-Falle bei den Anhängen (seit 18.08.2026 im Snapshot):
    # Kennt der Altstand keine Anlagen, würde jeder Anhang als „neu" gelten —
    # dann werden sie auf beiden Seiten aus dem Vergleich genommen.
    if not any("anlagen" in i for i in alt):
        jetzt = [{k: v for k, v in i.items() if k != "anlagen"} for i in jetzt]
    return diff_tagesordnung(alt, jetzt)


def _aenderungs_teil(alt: list[dict] | None, jetzt: list[dict]) -> str | None:
    """Der Diff-Block einer Änderungsmeldung — drei Ausgänge:

    * ``None`` — keine Vergleichsbasis (Stand von vor der Snapshot-Zeit).
      Dann geht die vollständige Tagesordnung raus, wie eh und je.
    * ``""`` — der Hash ist anders, die Tagesordnung liest sich aber gleich
      (etwa nur eine andere Reihenfolge im Quelltext). Dazu gibt es nichts zu
      sagen; der Aufrufer meldet dann gar nicht.
    * sonst die farbmarkierte Liste der Unterschiede.
    """
    d = _diff_fuer(alt, jetzt)
    if d is None:
        return None
    return diff_html(d) if hat_aenderungen(d) else ""


def main() -> dict:
    """Gibt die Kennzahlen des Laufs für die Cron-Übersicht zurück."""
    ratslotse_store = Store(RATSLOTSE_DB)
    all_subs = ratslotse_store.get_all_subscriptions()       # {owner_id: [committee_name]}
    targets = ratslotse_store.get_subscription_targets()     # {owner_id: {channel, chat, email}}

    # Daten werden auch OHNE Abonnements aktualisiert — die Web-App zeigt
    # Sitzungen und Terminplan für alle Nutzer*innen, nicht nur Abonnenten.
    council_store = CouncilStore(COUNCIL_DB)
    scraper = CouncilScraper()

    print("Refreshing committee list from Gremienübersicht…")
    committees = scraper.fetch_committee_list()
    council_store.save_committees(committees)
    print(f"  Saved {len(committees)} committees")

    print("Scanning upcoming council sessions…")
    session_ids, scheduled = scraper.upcoming_calendar(months_ahead=3)
    # Terminierte Sitzungen ohne veröffentlichte Tagesordnung (kein ksinr im
    # Kalender-HTML) — sonst bleibt ein frisch publizierter Terminplan unsichtbar.
    council_store.replace_scheduled_sessions(scheduled)
    print(f"  Found {len(session_ids)} sessions with agenda, {len(scheduled)} scheduled dates")

    notifications_sent = 0

    for ksinr in session_ids:
        session = scraper.fetch_session(ksinr)
        if not session:
            continue

        council_store.save_session(session)

        if not all_subs:
            continue
        if not session.is_future or not session.agenda_items:
            continue

        # Compute agenda hash once; drives both caching and change detection.
        agenda_hash = _agenda_hash(session.agenda_items)
        # Den Stand zu diesem Hash einfrieren: save_session hat die Items
        # bereits ERSETZT — ohne Snapshot gäbe es für die Diff-Änderungsmeldung
        # (Tims Wunsch 12.08.) keine Vergleichsbasis.
        #
        # Gespeichert wird, was auch in den Hash eingeht: ALLE Punkte samt
        # Öffentlichkeits-Merkmal. Vorher waren es nur die öffentlichen — der
        # Diff sah damit weniger als die Änderungserkennung, und eine Änderung
        # im nichtöffentlichen Teil erzeugte eine Mail ohne jede Aussage. Die
        # Titel der nichtöffentlichen TOPs stehen ohnehin im Ratsinfo und auf
        # der Sitzungsseite der App (dort mit „nichtöffentlich"-Marke).
        snapshot_items = [{"item_number": i.item_number, "title": i.title,
                           "template_number": i.template_number or "",
                           "is_public": bool(i.is_public),
                           # Anhänge mit Label: Der Diff nennt neue Anlagen
                           # beim Namen, nicht nur „irgendwas ist anders".
                           "anlagen": [{"label": e.get("label") or "Anlage",
                                        "url": e.get("url") or ""}
                                       for e in (i.anlagen or [])]}
                          for i in session.agenda_items]
        # Chronik VOR dem Einfrieren: Ist dieser Hash neu, ist der bisher
        # jüngste Snapshot der Vorher-Stand — die Sitzungsseite zeigt daraus
        # „Zuletzt geändert" (Tims Wunsch 18.08.: die Push sagt den Satz, die
        # App die Einzelheiten). Owner-unabhängig, eine Zeile je neuem Stand.
        try:
            if council_store.get_agenda_snapshot(ksinr, agenda_hash) is None:
                basis = council_store.get_latest_agenda_snapshot(ksinr)
                d_chronik = _diff_fuer(basis, snapshot_items)
                if d_chronik is not None and hat_aenderungen(d_chronik):
                    council_store.save_agenda_change(ksinr, d_chronik)
        except Exception as exc:  # noqa: BLE001 — Chronik ist Zusatz, nie Blocker
            print(f"  ⚠️ Änderungs-Chronik für {ksinr} fehlgeschlagen: {exc!r}")
        council_store.save_agenda_snapshot(ksinr, agenda_hash, snapshot_items)

        # Categorise subscribers:
        # - pending_new:    never notified before
        # - pending_update: notified before but the agenda has since changed
        # Rows migrated from before hash-tracking have hash==''; treat them as
        # "already notified, skip" to avoid a one-off spurious update blast.
        pending_new: list[int] = []
        pending_update: list[int] = []
        # Design 30a: Eine Änderungsmeldung lohnt nur kurz vor der Sitzung.
        # Ändert sich eine Tagesordnung drei Wochen vorher, ist das Verwaltung,
        # keine Nachricht — und für die Betroffenen nur eine Störung mehr.
        nah_dran = _stunden_bis(session.session_date, session.session_time) <= 48
        for owner_id, names in all_subs.items():
            if session.committee not in names:
                continue
            # „Themen-Treffer gewinnt": Wer für diese Sitzung schon weiß, welcher
            # TOP ihn betrifft (aus check_council), braucht die Gremien-Meldung
            # nicht zusätzlich.
            if ratslotse_store.has_agenda_match(owner_id, ksinr):
                continue
            last_hash = council_store.get_last_notified_hash(ksinr, owner_id)
            if last_hash is None:
                pending_new.append(owner_id)
            elif last_hash and last_hash != agenda_hash and nah_dran:
                pending_update.append(owner_id)

        if not pending_new and not pending_update:
            continue

        # The summary depends only on the session — compute once and cache.
        # A cached '' means "only routine TOPs" (still a valid cache hit).
        summary = _ohne_altkopf(_ohne_altlink(council_store.get_cached_summary(ksinr, agenda_hash)))
        if summary is None:
            try:
                # Strukturiert holen: dieselben Sätze stehen in der Mail UND
                # (seit Tims Wunsch 12.08.) unter den TOPs in der App.
                punkte = summarize_agenda_items(
                    committee=session.committee,
                    session_date=session.session_date,
                    agenda_items=session.agenda_items,
                )
                if punkte is None:
                    summary = None
                else:
                    council_store.save_item_summaries(ksinr, agenda_hash, punkte)
                    summary = _aufzaehlung(council_store, ksinr, punkte)
            except Exception as exc:  # noqa: BLE001
                # Ein LLM-Fehler bei EINER Sitzung (Provider-Content-Filter, ein
                # unretrybarer API-Fehler, kaputte Antwort) darf nicht den ganzen
                # Lauf für alle Konten abbrechen. summary=None ist ein gültiger
                # Zustand: Die Benachrichtigung geht dann ohne Zusammenfassung
                # raus (nur mit Link), und die nächste Runde versucht es erneut.
                print(f"  ⚠️ summarize_agenda fehlgeschlagen für {session.committee} "
                      f"am {session.session_date}: {exc!r} — Meldung geht ohne Zusammenfassung raus")
                summary = None
            # None = LLM-Antwort unbrauchbar → NICHT cachen (sonst stünde für
            # diese Tagesordnung dauerhaft eine falsche Aussage fest); die
            # Benachrichtigung geht trotzdem raus, nur ohne Zusammenfassung.
            if summary is not None:
                council_store.save_summary(ksinr, agenda_hash, summary)

        # Der Weg zurück in die App ist derselbe, egal ob die Zusammenfassung
        # geklappt hat: Knopf auf die Sitzung, Ratsinfo als leiser Nebenlink.
        wege = (digest_email.knopf(sitzung_href(ksinr), "Tagesordnung ansehen")
                + digest_email.nebenlink(session.url, "Im Ratsinformationssystem öffnen"))
        # „Warum bekommst du das?" — mit Direktlink auf den Schalter, um den es
        # geht. Die Änderungs-Meldung nennt zusätzlich ihren eigenen
        # Abschalt-Weg: Abo behalten, nur die Änderungs-Meldungen loswerden.
        reason = digest_email.gremium_abo_begruendung(session.committee)
        grund_update = digest_email.gremium_abo_begruendung(
            session.committee, mit_aenderungs_schalter=True)
        # Ein Kopf für alle drei Fälle, aus frischen Sitzungsdaten — vorher gab
        # es zwei: einen aus der Zusammenfassung (mit deutschem Datum) und
        # einen hier (mit ISO-Datum), je nachdem, ob das LLM geliefert hatte.
        kopf = sitzungskopf(session.committee, session.session_date,
                            session.session_time, session.location)

        if summary:
            base_message = kopf + "\n\n" + summary + wege
        elif summary == "":
            base_message = kopf + "<p>Die Tagesordnung enthält nur Routine-Punkte.</p>" + wege
        else:  # Zusammenfassung fehlgeschlagen — nichts behaupten, nur verlinken.
            base_message = kopf + wege

        subject = f"{session.committee}: Tagesordnung ist da"
        # Push-Vorschau ohne den Mail-Kopf (Tims Wunsch 18.08.): Datum und
        # Sitzungsort stehen dort nur im Weg — die Sache zuerst.
        push_neu = (_push_kurz(summary) if summary
                    else "Die Tagesordnung enthält nur Routine-Punkte." if summary == ""
                    else None)
        for owner_id in pending_new:
            if owner_id not in targets:
                continue
            print(f"  {session.session_date} {session.committee} → owner {owner_id} (neu)")
            notify.einreihen(ratslotse_store, owner_id, notify.N1_TAGESORDNUNG,
                             subject, base_message + reason, sitzung_href(ksinr),
                             push_text=push_neu)
            council_store.mark_notified(ksinr, owner_id, agenda_hash)
            notifications_sent += 1

        # Änderungs-Meldung als DIFF (Tims Wunsch 12.08.): nur was sich
        # geändert hat — Neues grün, Verschobenes/Umformuliertes gelb,
        # Entferntes rot. Die Vergleichsbasis ist der Snapshot des Standes,
        # über den der jeweilige Owner zuletzt informiert wurde; Owner können
        # verschiedene Stände kennen, deshalb je last_hash ein eigenes Diff.
        # Ohne Snapshot (Bestand von vor diesem Feature) kommt die
        # bisherige Voll-Mail.
        update_prefix = "<p><b>Die Tagesordnung hat sich geändert.</b></p>\n"
        update_subject = f"{session.committee}: Tagesordnung geändert"
        diff_je_hash: dict[str, dict | None] = {}   # Diff je Vorher-Stand; None = keine Basis
        for owner_id in pending_update:
            if owner_id not in targets:
                continue
            last_hash = council_store.get_last_notified_hash(ksinr, owner_id) or ""
            if last_hash not in diff_je_hash:
                diff_je_hash[last_hash] = _diff_fuer(
                    council_store.get_agenda_snapshot(ksinr, last_hash), snapshot_items)
            d = diff_je_hash[last_hash]
            if d is not None and not hat_aenderungen(d):
                # Der Hash ist anders, die Tagesordnung liest sich aber gleich
                # (etwa nur die Reihenfolge im Quelltext). „Details einzelner
                # Punkte wurden angepasst" stand hier früher — ein Satz, der
                # niemandem sagt, was los ist, und genau deshalb weg muss
                # (Tims Befund 17.08.). Stand nachziehen, nicht melden.
                council_store.mark_notified(ksinr, owner_id, agenda_hash)
                continue
            if d is not None and nur_nummern_versatz(d):
                # Oben fiel ein Punkt weg oder kam einer dazu, der Rest ist
                # geschlossen nachgerückt: gleiche Punkte, gleiche Reihenfolge,
                # neue Nummern. Dafür will niemand eine Mail (Tims Entscheidung
                # 26.08.) — die Sitzungsseite zeigt es weiter unter „Zuletzt
                # geändert". Der Stand wird trotzdem nachgezogen, sonst käme
                # die Verschiebung mit der nächsten echten Änderung nachträglich
                # doch noch als Meldung heraus.
                print(f"  {session.session_date} {session.committee} → owner {owner_id} "
                      f"(nur Nummern-Versatz, keine Meldung)")
                council_store.mark_notified(ksinr, owner_id, agenda_hash)
                continue
            if d is not None:
                nachricht = update_prefix + kopf + diff_html(d) + wege + grund_update
                # Die Push-Vorschau nennt die Änderungsart statt Datum und
                # Ort; die Einzelheiten zeigt die Sitzungsseite hinterm Tap
                # (Tims Wunsch 18.08.).
                push_kurz = diff_satz(d) or None
            else:
                # Ohne Vergleichsbasis (Meldung von vor der Snapshot-Zeit)
                # kommt die volle Liste — dann soll die Mail aber SAGEN, dass
                # sie den ganzen Stand zeigt, statt so zu tun, als wäre alles
                # davon neu (Tims Befund 18.08. an der Jugendhilfe-Mail).
                ohne_basis = ("<p>Was exact sich geändert hat, lässt sich für diese "
                              "Sitzung nicht mehr nachvollziehen — hier ist der "
                              "aktuelle Stand der Tagesordnung.</p>\n")
                nachricht = update_prefix + ohne_basis + base_message + grund_update
                push_kurz = "Tippe für den aktuellen Stand der Tagesordnung."
            print(f"  {session.session_date} {session.committee} → owner {owner_id} "
                  f"(Änderung{', Diff' if d is not None else ''})")
            # Eigener Anlass seit Tims Wunsch 26.08.2026: „Ich möchte zwar die
            # Tagesordnung bekommen, aber nicht über jede Änderung informiert
            # werden." Hängt in `gewuenscht` am N1-Elternteil.
            notify.einreihen(ratslotse_store, owner_id, notify.N1_AENDERUNG,
                             update_subject, nachricht, sitzung_href(ksinr),
                             push_text=push_kurz)
            council_store.mark_notified(ksinr, owner_id, agenda_hash)
            notifications_sent += 1

    # Tragweite der frisch importierten Tagesordnungspunkte bewerten — die
    # Wochen-Karte hebt danach hervor. Läuft hier statt in einem eigenen Cron,
    # weil genau hier die neuen Tagesordnungen hereinkommen; ein Fehler darf
    # den Meldungs-Lauf nicht abbrechen.
    #
    # Der Store wird ERST DANACH geschlossen. Stand `close()` davor, warf jeder
    # Zugriff hier `ProgrammingError: Cannot operate on a closed database`, der
    # except-Zweig schluckte ihn, und der Lauf meldete trotzdem „ok" mit
    # „Tragweite bewertet: 0" — vier Tage lang unbemerkt (19.08.26).
    bewertet = 0
    offen: list = []
    tragweite_fehler: str | None = None
    try:
        from council.impact import BATCH_SIZE, rate_agenda_batch

        offen = council_store.agenda_items_needing_impact(limit=200)
        for i, it in enumerate(offen):
            it["id"] = i
        nach_id = {it["id"]: it for it in offen}
        for start in range(0, len(offen), BATCH_SIZE):
            for iid, score, reason in rate_agenda_batch(offen[start : start + BATCH_SIZE]):
                it = nach_id.get(iid)
                if it:
                    council_store.save_agenda_impact(it["ksinr"], it["item_number"], score, reason)
                    bewertet += 1
        if offen:
            print(f"  Tragweite: {bewertet}/{len(offen)} Tagesordnungspunkte bewertet")
    except Exception as exc:  # noqa: BLE001
        tragweite_fehler = repr(exc)
        print(f"  ⚠️ Tragweite-Bewertung fehlgeschlagen: {exc!r} — Karte nutzt solange die Regeln")

    council_store.close()

    # Der 7-Uhr-Lauf ist zugleich der Wecker der Warteschlange: Was über Nacht
    # anfiel (Nachtruhe 21–7), geht jetzt raus.
    stats: dict = {}
    zugestellt = notify.zustellen(ratslotse_store, stats=stats)
    ratslotse_store.close()

    print(f"Done — {notifications_sent} Meldung(en) eingereiht, {zugestellt} zugestellt.")
    indicators = {
        "Gremien": len(committees),
        "Sitzungen mit Tagesordnung": len(session_ids),
        "Termine im Kalender": len(scheduled),
        "Benachrichtigungen": notifications_sent,
        "Tragweite bewertet": bewertet,
        "Tragweite offen": len(offen),
        **stats,
    }

    # Offene Punkte, aber kein einziger bewertet: Das ist ein Ausfall, kein
    # Zustand — und muss als Ausfall gemeldet werden. Vorher stand hier nur
    # eine Kennzahl „0", die niemandem auffiel. Erst hier werfen, damit die
    # Meldungen oben trotzdem alle rausgegangen sind.
    if offen and not bewertet:
        for k, v in indicators.items():
            print(f"  {k}: {v}")
        raise RuntimeError(
            f"Tragweite-Bewertung hat 0 von {len(offen)} Punkten bewertet"
            + (f" — {tragweite_fehler}" if tragweite_fehler else
               " — das Modell lieferte für keinen Batch ein verwertbares Ergebnis"))
    return indicators


if __name__ == "__main__":
    from kern.alerts import run_guarded
    run_guarded("check_committees", main)
