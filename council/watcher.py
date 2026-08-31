from __future__ import annotations

import json
import os
import re
from pathlib import Path

from kern import digest_email, llm, notify, prompts
from .ergebnisse import sitzung_href
from .scraper import CouncilScraper, CouncilSession
from .store import CouncilStore

BASE_URL = "https://buergerinfo.oldenburg.de"
# Themen-Zuordnung ist Klassifikation mit kleinem JSON — hier zählt Präzision
# bei Alltagssprache. Per Env tauschbar, seit 28.08.26 Standard: gpt-5.6-luna
# (Nachfolger des zwei Jahre alten 4o-mini; Vergleich siehe council/impact.py).
MODEL = os.environ.get("COUNCIL_WATCHER_MODEL", "openai/gpt-5.6-luna")


# So viel Vorlagentext bekommt das Modell je TOP zu sehen. Der Anfang trägt
# die Substanz (Betreff, Sachverhalt); 700 Zeichen halten 27 TOPs zusammen
# unter ~20k Zeichen — komfortabel für gpt-4o-mini und billig.
_VORLAGE_AUSZUG = 700


# Der Kopf jeder Vorlage ist Formular („Ausdruck vom: … Seite: 1/4 … Amt für
# … Vorlagen-Nr.: … Beratungsfolge: …") — 700 Zeichen davon sagen NICHTS über
# den Inhalt. Die Substanz beginnt am ersten dieser Marker (gemessen an
# Oldenburger Vorlagen: „Anlass" und „Beschlussvorschlag" decken den Großteil).
_VORLAGE_START = re.compile(
    r"(Anlass|Sachverhalt|Sachdarstellung|Beschlussvorschlag|Begründung)\s*:", re.IGNORECASE)


def _vorlagen_auszuege(store, session: CouncilSession) -> dict[str, str]:
    """template_number → aussagekräftiger Auszug aus dem Vorlagentext."""
    nrs = [i.template_number for i in session.agenda_items if i.is_public and i.template_number]
    if not nrs or store is None:
        return {}
    try:
        texte = store.vorlage_texts_for(nrs)
    except Exception:  # noqa: BLE001 — Anreicherung ist Kür, nie Blocker
        return {}
    out: dict[str, str] = {}
    for nr, text in texte.items():
        sauber = " ".join(str(text or "").split())
        if len(sauber) <= 60:
            continue
        m = _VORLAGE_START.search(sauber[:3000])
        out[nr] = sauber[m.start():m.start() + _VORLAGE_AUSZUG] if m else sauber[:_VORLAGE_AUSZUG]
    return out


def _classify_agenda(session: CouncilSession, topics: list[dict],
                     store=None) -> dict[int, list[str]]:
    """
    Returns {topic_id: [item_numbers_matched]}.
    Only called for future sessions with agenda items.

    ZWEI STUFEN (Tims Wunsch 12.08.): Erst die Zuordnung über die Titel wie
    bisher, dann eine Gegenprüfung der Kandidaten am VORLAGENTEXT — „Sanierung
    Grundschule X" und „Neubau Sporthalle an der Grundschule X" klingen im
    Titel gleich nah, erst der Sachverhalt entscheidet.

    Warum nicht alles in einem Aufruf: Die Vorlagen-Auszüge im Haupt-Prompt
    haben das Modell messbar abgelenkt — es übersah dann sogar den
    offensichtlichen Titel-Treffer („Ermittlungen Abfallentsorgung
    Fliegerhorst" fiel bei Thema „Fliegerhorst" durch). Die Prüfung sieht
    deshalb nur die wenigen Kandidaten, dafür mit Text.
    """
    if not session.agenda_items or not topics:
        return {}

    items_text = "\n".join(
        f"{i.item_number}: {i.title}" + (f" [{i.template_number}]" if i.template_number else "")
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
        # Zuordnung ist Klassifikation, keine Textproduktion: Ohne
        # temperature=0 lieferte derselbe Prompt mal drei Treffer, mal keinen
        # (hier an der 27-TOP-Sitzung gemessen) — und wer benachrichtigt wird,
        # darf nicht vom Würfel abhängen.
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        # Seit die Treffer Nummer UND Titel tragen (#438), ist die Antwort
        # deutlich länger — mit 512 Token riss sie bei großen Tagesordnungen
        # mitten im JSON ab (hier beim Test an der 27-TOP-Sitzung gemessen).
        max_tokens=1200,
    )
    # Ein kaputtes/abgeschnittenes JSON darf NICHT den ganzen Cron-Lauf
    # abbrechen — dieselbe Lehre wie beim Content-Filter-DoS (#359): lieber
    # für diese Sitzung keine Treffer als für alle keine Meldungen.
    roh = (resp.choices[0].message.content or "").strip()
    if roh.startswith("```"):
        roh = roh.strip("`")
        roh = roh[roh.find("{"):]
    try:
        data = json.loads(roh)
    except json.JSONDecodeError:
        print(f"    ⚠️ Themen-Zuordnung: unbrauchbares JSON für {session.committee} "
              f"am {session.session_date} — keine Treffer für diese Sitzung")
        return {}
    if not isinstance(data, dict):
        return {}

    auszuege = _vorlagen_auszuege(store, session)
    per_nr = {i.item_number: i for i in session.agenda_items}

    # Erst alle Vorschläge einsammeln, dann prüfen: So steht vor dem ersten
    # Prüf-Aufruf fest, ob überhaupt ein Kandidat ohne Vorlage dabei ist —
    # nur dann lohnt (und kostet) das Nachladen der TOP-Kurzfassungen.
    vorschlaege: list[tuple[int, list[str]]] = []
    for m in data.get("matches", []):
        idx = m.get("topic_index", 0) - 1
        # Neues Format: [{"number", "title"}]. Der Rückfall auf ["Ö 6.1", …]
        # ohne Titel-Anker bleibt: Modelle antworten gelegentlich in der
        # älteren Form, und ein Treffer ohne Anker ist besser als keiner.
        roh = m.get("items")
        if roh is None:
            roh = [{"number": n} for n in m.get("item_numbers", [])]
        nums = _verifiziere_items(session, roh)
        if 0 <= idx < len(topics) and nums:
            vorschlaege.append((idx, nums))

    ohne_vorlage = any(
        not auszuege.get((per_nr[n].template_number or "") if n in per_nr else "")
        for _idx, nums in vorschlaege for n in nums)
    kurzfassungen = _kurzfassungen(store, session) if ohne_vorlage else {}

    result: dict[int, list[str]] = {}
    for idx, nums in vorschlaege:
        if auszuege or kurzfassungen:
            nums = _pruefe_am_text(session, topics[idx], nums, auszuege, kurzfassungen)
        if nums:
            result[idx] = nums
    return result


def _kurzfassungen(store, session: CouncilSession) -> dict[str, str]:
    """item_number → KI-Kurzfassung, für TOPs ohne Vorlage.

    Notfalls selbst erzeugt: Die Kurzfassungen entstehen sonst in
    `check_committees` — und zwar nur für Sitzungen, zu denen gerade jemand
    eine Gremien-Meldung bekommt. Genau die Sitzungen mit Themen-Treffer
    überspringt dieser Job aber („Themen-Treffer gewinnt"), sodass die
    Gegenprüfung ausgerechnet dort ohne Beleg dastünde, wo sie gebraucht wird.
    Der Aufruf kostet einen LLM-Call je Sitzung, wird gecacht und ist
    best-effort: Schlägt er fehl, bleibt es beim Titel-Urteil wie bisher.
    """
    if store is None:
        return {}
    try:
        vorhanden = store.agenda_summaries_for(session.ksinr)
        if vorhanden:
            return vorhanden
        from .committee_summary import summarize_agenda_items

        punkte = summarize_agenda_items(
            committee=session.committee, session_date=session.session_date,
            agenda_items=session.agenda_items)
        if not punkte:
            return {}
        store.save_item_summaries(session.ksinr, _agenda_hash(session.agenda_items), punkte)
        return {p["number"]: p["summary"] for p in punkte
                if p.get("number") and p.get("summary")}
    except Exception:  # noqa: BLE001 — Anreicherung ist Kür, nie Blocker
        return {}


def _pruefe_am_text(session: CouncilSession, topic: dict, nums: list[str],
                    auszuege: dict[str, str], kurzfassungen: dict[str, str]) -> list[str]:
    """Zweite Stufe: Kandidaten am Inhalt gegenprüfen, nicht nur am Titel.

    Beleg je Kandidat ist der Vorlagentext — und wo es keinen gibt, die
    KI-Kurzfassung des TOP. Der Zusatz ist der eigentliche Fix: Vorher konnte
    diese Stufe genau dort nicht greifen, wo der Titel das einzige Indiz war,
    und ließ jeden vorlagenlosen Punkt unbesehen durch. Genau so bekam „Ö 7
    Aktueller Planungsstand Spielplatz Eversten Holz" (Jugendhilfeausschuss
    19.08.2026, ohne Vorlage) die Marke „dein Thema · Wohnheim Tegelbusch"
    — und in derselben Sitzung, für ein anderes Konto, „Am Bahndamm".

    Ganz ohne Beleg (weder Vorlage noch Kurzfassung) bleibt es beim
    Titel-Urteil. Fällt der Aufruf aus, bleibt die Titel-Zuordnung stehen:
    Die Prüfung schärft, sie blockiert nie.
    """
    per_nr = {i.item_number: i for i in session.agenda_items}

    def beleg(n: str) -> tuple[str, str]:
        """(Etikett, Text) — Vorlage schlägt Kurzfassung, sie ist die Quelle."""
        item = per_nr.get(n)
        text = auszuege.get((item.template_number or "") if item else "")
        if text:
            return "Vorlage", text
        kurz = kurzfassungen.get(n) or ""
        return ("Kurzfassung", kurz) if kurz else ("", "")

    belege = {n: beleg(n) for n in nums}
    if not any(t for _label, t in belege.values()):
        return nums
    zeilen = []
    for n in nums:
        item = per_nr.get(n)
        label, text = belege[n]
        zeilen.append(f"{n}: {item.title if item else n}\n    {label or 'Vorlage'}: {text or '—'}")
    try:
        antwort = llm.chat_complete(
            model=MODEL, response_format={"type": "json_object"}, temperature=0,
            max_tokens=400,
            messages=[{"role": "user", "content": prompts.render(
                "council_watcher_pruefung", thema=topic.get("name", ""),
                beschreibung=topic.get("description", ""), kandidaten="\n".join(zeilen))}],
        )
        roh = (antwort.choices[0].message.content or "").strip()
        if roh.startswith("```"):
            roh = roh.strip("`")
            roh = roh[roh.find("{"):]
        behalten = json.loads(roh).get("hits", [])
    except Exception:  # noqa: BLE001 — Prüfung ist Schärfung, kein Blocker
        return nums
    erlaubt = {" ".join(str(x).split()).upper() for x in behalten}
    # Verworfen wird nur, wer einen Beleg HAT und ihn nicht besteht — ein Punkt
    # ohne jede Inhaltsangabe wurde nie geprüft und darf nicht stillschweigend
    # als widerlegt gelten.
    return [n for n in nums
            if " ".join(n.split()).upper() in erlaubt or not belege[n][1]]


def _falte_titel(text: str) -> str:
    t = str(text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _verifiziere_items(session: CouncilSession, roh: list) -> list[str]:
    """LLM-Treffer gegen die echte Tagesordnung prüfen (Tims Befund 12.08.:
    Ö 14.6 trug das Fliegerhorst-Label, gemeint war Ö 14.7 — das Modell
    verrutscht bei Nummern-Listen gern um eins, und der Code glaubte ihm
    blind). Regeln: Die Nummer muss existieren; widerspricht der mitgelieferte
    Titel dem Item hinter der Nummer, gewinnt der EINDEUTIGE Titel-Treffer —
    Titel verdreht das Modell viel seltener als Nummern. Ist ein Treffer
    weder über Nummer noch Titel auflösbar, fällt er weg: lieber keine
    Markierung als eine falsche. Zurück kommen kanonische Nummern."""
    items = [i for i in session.agenda_items if i.is_public]
    per_nummer = {" ".join(str(i.item_number).split()).upper(): i for i in items}
    out: list[str] = []
    for eintrag in roh:
        if isinstance(eintrag, str):
            eintrag = {"number": eintrag}
        nummer = " ".join(str(eintrag.get("number") or "").split()).upper()
        titel = _falte_titel(eintrag.get("title") or "")
        item = per_nummer.get(nummer)
        if item is None and nummer:
            # „14.7" ohne Ö/N-Präfix: nur übernehmen, wenn eindeutig.
            kandidaten = [i for i in items
                          if " ".join(str(i.item_number).split()).upper().split(" ", 1)[-1] == nummer]
            item = kandidaten[0] if len(kandidaten) == 1 else None
        if titel:
            anker = titel[:32]
            passt = item is not None and anker[:20] and anker[:20] in _falte_titel(item.title)
            if not passt:
                treffer = [i for i in items if anker and anker in _falte_titel(i.title)]
                item = treffer[0] if len(treffer) == 1 else (item if item and not treffer else None)
        if item is not None and item.item_number not in out:
            out.append(item.item_number)
    return out


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

    Themennamen kommen von Nutzer*innen. Ein Zeilenumbruch darin hat in einer
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


def _melden(ratslotse_store, owner: dict, art: str, titel: str, html: str, url: str,
            deliver_message) -> None:
    """Eine Meldung abgeben — über die Warteschlange, wenn es sie gibt.

    Design 30a: Alle Anlässe laufen durch ``kern.notify``, sonst greifen die
    Grenzen (zwei am Tag, Nachtruhe) nicht. Ohne ``ratslotse_store`` — in Tests und
    bei Direktaufrufen — bleibt der bisherige Sofortversand, damit dieser Pfad
    weiter ohne Datenbank prüfbar ist.
    """
    if ratslotse_store is None:
        deliver_message(owner, html, email_subject=titel, push_url=url)
        return
    notify.einreihen(ratslotse_store, owner["owner_id"], art, titel, html, url)


def _agenda_hash(agenda_items) -> str:
    """Stabiler Fingerabdruck der Tagesordnung — ändert sich, sobald ein TOP
    hinzukommt, wegfällt oder umformuliert wird."""
    import hashlib

    payload = "\n".join(
        f"{i.item_number}\t{i.title}\t{i.template_number or ''}\t{int(i.is_public)}"
        for i in agenda_items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_watcher(
    db_path: str | Path,
    owners: list[dict],
    months_ahead: int = 3,
    ratslotse_store=None,
    stats: dict | None = None,
) -> list[str]:
    """
    Scrape upcoming sessions once, classify their agendas per owner, persist
    the matches (RL-902) and send alerts. Returns the alert messages sent.

    owners: get_all_owner_digests()-Zeilen — je {owner_id, topics: [TopicRow],
            delivery_channel, email, push_tokens}.
    ratslotse_store: offener kern.store.Store für die Treffer-Persistenz; ohne ihn
            (Tests) wird klassifiziert und alarmiert, aber nichts gemerkt —
            dann läuft die Klassifikation beim nächsten Mal erneut.
    stats: optionales dict, in das der Lauf seine Kennzahlen schreibt (für die
            Cron-Übersicht im Admin-Panel).
    """
    from kern.delivery import deliver_message

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
            # Je Nutzer*in klassifizieren — aber nur, wenn sich die
            # Tagesordnung seit ihrer letzten Klassifikation geändert hat.
            if ratslotse_store is not None:
                known = ratslotse_store.agenda_classified_hash(owner["owner_id"], ksinr)
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
                try:
                    matches = _classify_agenda(session, topics, store=store)
                except llm.BadRequestError as exc:
                    # Ein 400 hängt am Inhalt DIESER Anfrage, nicht am System:
                    # Die Themen-Namen/Beschreibungen der Nutzer*in landen im
                    # Prompt, und ein einzelner vergifteter Text (z. B. ein als
                    # Prompt-Injection getarnter Themenname) lässt den Provider-
                    # Content-Filter anschlagen. Ohne dieses Fangnetz reißt eine
                    # solche Nutzer*in den GANZEN Cron-Lauf für alle ab — ein
                    # DoS, den jedes Konto auslösen könnte. Also nur diese
                    # Nutzer*in bei dieser Sitzung überspringen und weitermachen.
                    if llm.is_content_filter(exc):
                        print(f"    ⚠️ Content-Filter für owner {owner['owner_id']} "
                              f"(möglicher Prompt-Injection-Versuch in einem Themennamen) "
                              f"— übersprungen.")
                        if stats is not None:
                            stats["Content-Filter übersprungen"] = \
                                stats.get("Content-Filter übersprungen", 0) + 1
                    else:
                        print(f"    ⚠️ Ungültige Klassifikations-Anfrage für owner "
                              f"{owner['owner_id']}: {exc} — übersprungen.")
                    # agenda_hash NICHT als klassifiziert merken: Sobald das
                    # Thema korrigiert oder gelöscht ist, versucht der nächste
                    # Lauf es neu, statt die Nutzer*in dauerhaft leer auszugehen.
                    continue

                if ratslotse_store is not None:
                    ratslotse_store.replace_agenda_matches(
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
                _melden(ratslotse_store, owner, notify.N2_THEMA,
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
