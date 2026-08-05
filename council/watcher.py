from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nwz import digest_email, llm, notify, prompts
from .ergebnisse import sitzung_href
from .scraper import CouncilScraper, CouncilSession
from .store import CouncilStore

BASE_URL = "https://buergerinfo.oldenburg.de"
MODEL = "openai/gpt-4o-mini"


def _classify_agenda(session: CouncilSession, topics: list[dict]) -> dict[int, list[str]]:
    """
    Returns {topic_id: [item_numbers_matched]}.
    Only called for future sessions with agenda items.
    """
    if not session.agenda_items or not topics:
        return {}

    items_text = "\n".join(
        f"{i.item_number}: {i.title}" + (f" [{i.vorlage_nr}]" if i.vorlage_nr else "")
        for i in session.agenda_items
        if i.is_public
    )
    topics_text = "\n".join(
        f"{idx + 1}. {t['name']}: {t['description']}"
        for idx, t in enumerate(topics)
    )

    system = prompts.get("council_watcher_system")
    prompt = prompts.render(
        "council_watcher_user",
        committee=session.committee,
        session_date=session.session_date,
        items_text=items_text,
        topics_text=topics_text,
    )

    resp = llm.chat_complete(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
    )
    data = json.loads(resp.choices[0].message.content)

    result: dict[int, list[str]] = {}
    for m in data.get("matches", []):
        idx = m.get("topic_index", 0) - 1
        nums = m.get("item_numbers", [])
        if 0 <= idx < len(topics) and nums:
            result[idx] = nums
    return result


def _datum(iso: str) -> str:
    """„2026-08-18" → „18. August"."""
    MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
              "August", "September", "Oktober", "November", "Dezember")
    teile = str(iso or "")[:10].split("-")
    if len(teile) != 3:
        return str(iso or "")
    try:
        return f"{int(teile[2])}. {MONATE[int(teile[1]) - 1]}"
    except (ValueError, IndexError):
        return iso


def _einzeilig(text: str, grenze: int = 90) -> str:
    """Für Betreff und Push-Titel: eine Zeile, kein Zeilenumbruch, gekappt.

    Themennamen kommen von Nutzer:innen. Ein Zeilenumbruch darin hat in einer
    Betreffzeile nichts zu suchen (Mail-Header sind zeilenbasiert), und ein
    Roman auch nicht — Mail-Programme und die Mitteilungszentrale schneiden
    sowieso ab, dann lieber kontrolliert und mit Auslassungszeichen.
    """
    sauber = " ".join(str(text or "").split())
    return sauber if len(sauber) <= grenze else sauber[: grenze - 1].rstrip() + "…"


def _titel_thema(session: CouncilSession, topic_name: str) -> str:
    return f"„{_einzeilig(topic_name)}“ kommt auf den Tisch"


def _format_alert(session: CouncilSession, topic_matches: dict[int, list[str]], topics: list[dict]) -> str:
    """N2 — dein Thema steht auf einer Tagesordnung.

    Design 30a: das Ereignis berichten, nicht die App vorführen.

    Die Tagesordnungspunkte stehen als Liste, nicht als semikolon-verkettete
    Zeile: Bei einem Thema, das ein halbes Dutzend TOPs trifft, wurde daraus
    ein Absatz, in dem der eigene Punkt nicht mehr auffindbar war.

    Der Knopf führt in die App auf genau diese Sitzung (der ksinr-Deep-Link
    klappt ihre Tagesordnung auf); das Ratsinformationssystem bleibt als
    leiser Nebenlink erreichbar — es ist die Quelle, aber nicht der Ort, an dem
    man weiterliest.
    """
    item_map = {i.item_number: i for i in session.agenda_items}
    zeilen = []
    for topic_idx, item_numbers in topic_matches.items():
        for num in item_numbers:
            item = item_map.get(num)
            titel = _esc(item.title) if item else _esc(num)
            zeilen.append(f"<b>TOP {_esc(num)}</b> — {titel}")

    wann = _datum(session.session_date)
    if session.session_time:
        wann += f", {_esc(session.session_time)} Uhr"
    kopf = (f"<p style='margin:0'>Auf der Tagesordnung von <b>{_esc(session.committee)}</b> "
            f"am {wann} steht etwas zu deinem Thema:</p>")
    return (
        kopf
        + digest_email.liste(zeilen)
        + digest_email.knopf(sitzung_href(session.ksinr), "Tagesordnung ansehen")
        + digest_email.nebenlink(session.url, "Im Ratsinformationssystem öffnen")
    )




def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _melden(nwz_store, owner: dict, art: str, titel: str, html: str, url: str,
            deliver_message) -> None:
    """Eine Meldung abgeben — über die Warteschlange, wenn es sie gibt.

    Design 30a: Alle Anlässe laufen durch ``nwz.notify``, sonst greifen die
    Grenzen (zwei am Tag, Nachtruhe) nicht. Ohne ``nwz_store`` — in Tests und
    bei Direktaufrufen — bleibt der bisherige Sofortversand, damit dieser Pfad
    weiter ohne Datenbank prüfbar ist.
    """
    if nwz_store is None:
        deliver_message(owner, html, email_subject=titel, push_url=url)
        return
    notify.einreihen(nwz_store, owner["owner_id"], art, titel, html, url)


def _agenda_hash(agenda_items) -> str:
    """Stabiler Fingerabdruck der Tagesordnung — ändert sich, sobald ein TOP
    hinzukommt, wegfällt oder umformuliert wird."""
    import hashlib

    payload = "\n".join(
        f"{i.item_number}\t{i.title}\t{i.vorlage_nr or ''}\t{int(i.is_public)}"
        for i in agenda_items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_watcher(
    db_path: str | Path,
    owners: list[dict],
    months_ahead: int = 3,
    nwz_store=None,
    stats: dict | None = None,
) -> list[str]:
    """
    Scrape upcoming sessions once, classify their agendas per owner, persist
    the matches (RL-902) and send alerts. Returns the alert messages sent.

    owners: get_all_owner_digests()-Zeilen — je {owner_id, topics: [TopicRow],
            delivery_channel, email, push_tokens}.
    nwz_store: offener nwz.store.Store für die Treffer-Persistenz; ohne ihn
            (Tests) wird klassifiziert und alarmiert, aber nichts gemerkt —
            dann läuft die Klassifikation beim nächsten Mal erneut.
    stats: optionales dict, in das der Lauf seine Kennzahlen schreibt (für die
            Cron-Übersicht im Admin-Panel).
    """
    from nwz.delivery import deliver_message

    scraper = CouncilScraper()
    store = CouncilStore(db_path)

    print("Scanning council calendar…")
    session_ids, scheduled = scraper.upcoming_calendar(months_ahead=months_ahead)
    # Terminplan mitschreiben: Sitzungen ohne veröffentlichte Tagesordnung
    # haben noch keinen ksinr, sollen aber in der App schon sichtbar sein.
    store.replace_scheduled_sessions(scheduled)
    print(f"  Found {len(session_ids)} sessions with agenda, {len(scheduled)} scheduled dates")
    if stats is not None:
        stats["Sitzungen mit Tagesordnung"] = len(session_ids)
        stats["Termine im Kalender"] = len(scheduled)

    alerts_sent: list[str] = []

    for ksinr in session_ids:
        session = scraper.fetch_session(ksinr)
        if not session:
            continue

        store.save_session(session)

        # Nur kommende Sitzungen mit Tagesordnung sind für Themen relevant.
        if not session.is_future or not session.agenda_items:
            continue

        agenda_hash = _agenda_hash(session.agenda_items)

        for owner in owners:
            # Je Nutzer:in klassifizieren — aber nur, wenn sich die
            # Tagesordnung seit ihrer letzten Klassifikation geändert hat.
            if nwz_store is not None:
                known = nwz_store.agenda_classified_hash(owner["owner_id"], ksinr)
                if known == agenda_hash:
                    continue

            topics = [
                {"id": t.id, "name": t.name, "description": t.description}
                for t in owner["topics"]
            ]

            matches: dict[int, list[str]] = {}
            if topics:
                print(f"  {session.session_date} {session.committee}: "
                      f"{len(session.agenda_items)} items → classifying for owner {owner['owner_id']}…")
                matches = _classify_agenda(session, topics)

                if nwz_store is not None:
                    nwz_store.replace_agenda_matches(
                        owner["owner_id"], ksinr, agenda_hash,
                        {topics[idx]["id"]: nums for idx, nums in matches.items()},
                    )

            for topic_idx, item_numbers in matches.items():
                topic_id = topics[topic_idx]["id"]
                if store.alert_already_sent(ksinr, topic_id):
                    continue
                msg = _format_alert(session, {topic_idx: item_numbers}, topics)
                print(f"    Match: topic={topics[topic_idx]['name']!r} items={item_numbers}")
                # Pfad, nicht session.url: Die App springt beim Antippen nur
                # bei einem /-Pfad (lib/push.ts) — mit der Ratsinfo-Adresse
                # passierte schlicht nichts. Die getroffenen TOPs gehen mit ins
                # Ziel: Die App klappt die Sitzung nicht nur auf, sondern
                # springt zu genau diesen Zeilen. Ohne das landete man am
                # Sitzungskopf und musste die Tagesordnung selbst suchen.
                _melden(nwz_store, owner, notify.N2_THEMA,
                        _titel_thema(session, topics[topic_idx]["name"]), msg,
                        sitzung_href(ksinr, item_numbers), deliver_message)
                alerts_sent.append(msg)
                store.mark_alert_sent(ksinr, topic_id)

            # N1 (Design 30a): Tagesordnung in einem abonnierten Gremium.
            # Reiner Stringabgleich VOR jedem Sprachmodell — kein Token, keine
            # Kosten. Der Themen-Treffer gewinnt: Wer oben schon gehört hat,
            # welcher TOP ihn betrifft, braucht nicht zusätzlich die Meldung,
            # dass das Haus überhaupt tagt.

    store.close()
    return alerts_sent
