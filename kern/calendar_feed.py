"""Das Kalender-Abo: die Sitzungen eines Kontos als ICS-Feed.

Eine Adresse je Konto (``/api/calendar/<token>.ics``), die Apple Kalender,
Google Kalender und Outlook alle paar Stunden abrufen. Drin sind die Sitzungen
der abonnierten Ausschüsse und jede Sitzung, auf deren Tagesordnung ein
eigenes Thema steht — die kommenden plus die letzten sechs Wochen, damit der
Kalender nicht bei heute anfängt.

**Der Termin ist der Teaser, nicht der Ersatz.** Tims Sorge (05.09.2026):
Wer den Kalender abonniert, kommt nie wieder. Deshalb trägt jeder Termin das,
was nur Ratslotse hat — die wichtigsten Punkte mit ihrem Grund, die Treffer zu
den eigenen Themen — und endet mit dem Link zur Sitzungsseite, hinter dem
Tagesordnung, Vorlagen und später das Ergebnis liegen. Der Feed ist lebendig:
Eine Sitzung, die vorbei ist, sagt im selben Termin, dass die Ergebnisse mit
dem Protokoll auf Ratslotse erscheinen; sobald Beschlüsse da sind, nennt sie
deren Zahl. Der Kalender ändert sich also unter der Hand, und der Weg zurück
steht in jedem Eintrag.

Die Bewertung der Punkte ist dieselbe wie auf der Wochenkarte und in der
Sitzungsliste (``CouncilStore.sitzungs_highlights``) — ein Begriff, überall
gleich.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

#: Wie weit der Feed zurückreicht. Sechs Wochen: Die letzten Sitzungen bleiben
#: sichtbar, und ihre Termine wandeln sich, sobald Beschlüsse eintreffen.
PAST_DAYS = 42
#: Wie viele kommende Sitzungen höchstens — mehr als ein Vierteljahr kennt das
#: Ratsinfo ohnehin nicht.
UPCOMING_LIMIT = 300
#: Die Sitzung dauert im Ratsinfo nirgends „bis"; drei Stunden sind die Kappe
#: der LIVE-Karte (``council.live``), der Rat selbst sitzt länger.
DEFAULT_HOURS = 3
COUNCIL_HOURS = 4
#: Höchstens so viele hervorgehobene Punkte je Termin.
HIGHLIGHTS_PER_SESSION = 3
#: Erinnerung am Vorabend — nur für Sitzungen mit einem Treffer zu einem
#: eigenen Thema; alle anderen Termine bleiben still.
REMINDER_HOUR = 18

_COUNCIL_NAMES = {"rat", "stadtrat", "rat der stadt", "rat der stadt oldenburg", "rat der stadt oldenburg (oldb)"}

# Vollständige Zonendefinition statt bloßem TZID (wie ``lib/ics.ts`` im Web):
# Ein Kalender, der Europe/Berlin nicht kennt, legte den Termin sonst in UTC
# ab — im Sommer zwei Stunden zu früh.
VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Berlin",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def is_council(committee: str | None) -> bool:
    return (committee or "").strip().lower() in _COUNCIL_NAMES


def short_committee(name: str) -> str:
    """Kurzname wie ``shortCommittee`` im Web: Präfix „Ausschuss für …" weg,
    „und" → „&", ein einzelnes „…ausschuss" auf seinen Kern. Nie stumpf
    abschneiden — der volle Name bleibt in der Beschreibung."""
    s = (name or "").strip()
    if s.lower().startswith("rat der stadt"):
        return "Rat"
    s = re.sub(r"^Ausschuss für (den |die |das )?", "", s)
    s = re.sub(r"^Betriebsausschuss (Eigenbetrieb )?", "", s)
    if re.fullmatch(r"\S+ausschuss", s, re.IGNORECASE):
        s = re.sub(r"s?ausschuss$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+und\s+", " & ", s).strip()
    return s if len(s) >= 2 else name


def _esc(text: str) -> str:
    """RFC 5545 §3.3.11: Backslash, Zeilenumbruch, Komma, Semikolon."""
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold(line: str) -> list[str]:
    """RFC 5545 §3.1: Zeilen über 75 Oktett umbrechen, Folgezeile mit einem
    Leerzeichen. Gemessen in UTF-8-Bytes, und nie mitten in einem Zeichen."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return [line]
    out: list[str] = []
    chunk = b""
    limit = 75
    for ch in line:
        b = ch.encode("utf-8")
        if len(chunk) + len(b) > limit:
            out.append(chunk.decode("utf-8"))
            chunk = b" " + b
            limit = 75
        else:
            chunk += b
    if chunk:
        out.append(chunk.decode("utf-8"))
    return out


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "sitzung"


def _local(day: str, time: str | None) -> datetime | None:
    """Sitzungsbeginn in Europe/Berlin — ``None`` ohne brauchbare Uhrzeit."""
    try:
        d = date.fromisoformat(day[:10])
    except ValueError:
        return None
    t = (time or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", t)
    if not m:
        return None
    return datetime(d.year, d.month, d.day, int(m.group(1)), int(m.group(2)), tzinfo=BERLIN)


def _stamp_local(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def _stamp_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def session_url(base_url: str, session: dict, item_number: str | None = None) -> str:
    """Die eigenständige Sitzungsseite — ohne Konto lesbar, deshalb der
    richtige Ort für einen Link aus dem Kalender (dieselbe Adresse wie das
    Teilen in der App, ``AppRouter.universalLink``). Ohne Nummer bleibt es bei
    der Liste."""
    ksinr = session.get("ksinr")
    if not ksinr:
        return f"{base_url}/council?tab=sessions"
    url = f"{base_url}/council/sitzung?ksinr={int(ksinr)}"
    if item_number:
        url += "&top=" + quote(item_number, safe="")
    return url


def select_sessions(*, council, ratslotse, owner_id: int, today: date | None = None) -> list[dict]:
    """Die Sitzungen dieses Kontos: kommende plus die letzten sechs Wochen,
    gefiltert auf abonnierte Ausschüsse und Themen-Treffer. Ohne ein einziges
    Abo kommt alles — ein leerer Kalender erklärte nichts; die Karte in der
    App sagt dazu, dass Abos die Auswahl schärfen. Jede Sitzung trägt danach
    ``my_topic_items`` und ``highlights`` wie in der Sitzungsliste."""
    today = today or date.today()
    since = (today - timedelta(days=PAST_DAYS)).isoformat()
    recent = [s for s in council.recent_sessions(limit=200) if (s.get("session_date") or "") >= since]
    upcoming = council.upcoming_sessions(limit=UPCOMING_LIMIT)
    sessions = list(reversed(recent)) + upcoming
    ksinrs = [s["ksinr"] for s in sessions if s.get("ksinr")]
    mine = ratslotse.agenda_matches_for_owner(owner_id, ksinrs)
    subs = set(ratslotse.get_subscriptions(owner_id))

    def wanted(s: dict) -> bool:
        if s.get("ksinr") and mine.get(s["ksinr"]):
            return True
        return not subs or s.get("committee") in subs

    chosen = [s for s in sessions if wanted(s)]
    chosen_ids = [s["ksinr"] for s in chosen if s.get("ksinr")]
    highlights = council.sitzungs_highlights(chosen_ids, meine=mine, max_je_sitzung=HIGHLIGHTS_PER_SESSION)
    for s in chosen:
        k = s.get("ksinr") or 0
        s["my_topic_items"] = mine.get(k, [])
        s["highlights"] = highlights.get(k, [])
    return chosen


def build_feed(*, user: dict, council, ratslotse, base_url: str, now: datetime | None = None) -> str:
    """Der ganze Kalender als ICS-Text (CRLF, gefaltet)."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(BERLIN).date()
    base_url = base_url.rstrip("/")
    sessions = select_sessions(council=council, ratslotse=ratslotse, owner_id=user["id"], today=today)
    counts = council.beschluss_zahl_je_sitzung([s["ksinr"] for s in sessions if s.get("ksinr")])

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Ratslotse//Kalender-Abo//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Ratslotse – Oldenburger Rat",
        "X-WR-CALDESC:" + _esc(
            "Sitzungen deiner Ausschüsse und zu deinen Themen, mit den wichtigsten "
            "Punkten. Tagesordnung, Einordnung und Ergebnisse auf ratslotse.de."
        ),
        "X-WR-TIMEZONE:Europe/Berlin",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
        *VTIMEZONE,
    ]
    for s in sessions:
        lines.extend(_event(s, base_url=base_url, now=now, today=today, decisions=counts.get(s.get("ksinr") or 0, 0)))
    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"


def _event(s: dict, *, base_url: str, now: datetime, today: date, decisions: int) -> list[str]:
    committee = s.get("committee") or "Gremium"
    short = short_committee(committee)
    day = (s.get("session_date") or "")[:10]
    start = _local(day, s.get("session_time"))
    hours = COUNCIL_HOURS if is_council(committee) else DEFAULT_HOURS
    ksinr = s.get("ksinr")
    uid = f"sitzung-{int(ksinr)}@ratslotse.de" if ksinr else f"termin-{_slug(committee)}-{day}@ratslotse.de"
    url = session_url(base_url, s)
    is_past = day < today.isoformat()
    topics = s.get("my_topic_items") or []

    out = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_stamp_utc(now)}"]
    if start:
        out.append(f"DTSTART;TZID=Europe/Berlin:{_stamp_local(start)}")
        out.append(f"DTEND;TZID=Europe/Berlin:{_stamp_local(start + timedelta(hours=hours))}")
    else:
        d = date.fromisoformat(day)
        out.append(f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}")
        out.append(f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}")
    out.append("SUMMARY:" + _esc(short if not topics else f"{short} · dein Thema"))
    if s.get("location"):
        out.append("LOCATION:" + _esc(str(s["location"])))
    out.append(f"URL:{url}")
    out.append("DESCRIPTION:" + _esc(_description(
        s, committee=committee, url=url, base_url=base_url, is_past=is_past, decisions=decisions,
    )))
    out.append("CATEGORIES:" + _esc("Ratslotse"))
    out.append(f"STATUS:{'CONFIRMED' if ksinr else 'TENTATIVE'}")

    # Erinnerung am Vorabend — nur mit eigenem Thema, nur für Kommendes.
    if topics and start and not is_past:
        reminder = datetime.combine(start.date() - timedelta(days=1), datetime.min.time(), tzinfo=BERLIN)
        reminder = reminder.replace(hour=REMINDER_HOUR)
        names = sorted({t.get("topic_name") for t in topics if t.get("topic_name")})
        out.extend([
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:" + _esc(f"Morgen im {short}: " + ", ".join(names) if names else f"Morgen im {short}"),
            f"TRIGGER;VALUE=DATE-TIME:{_stamp_utc(reminder)}",
            "END:VALARM",
        ])
    out.append("END:VEVENT")
    return out


def _description(s: dict, *, committee: str, url: str, base_url: str, is_past: bool, decisions: int) -> str:
    """Der Text im Termin — Wichtiges zuerst, dann der Weg zurück."""
    parts: list[str] = []
    highlights = s.get("highlights") or []
    topics = s.get("my_topic_items") or []
    by_item: dict[str, list[str]] = {}
    for t in topics:
        by_item.setdefault(t.get("item_number") or "", []).append(t.get("topic_name") or "")

    if highlights:
        parts.append("Wichtig auf der Tagesordnung:")
        for h in highlights:
            title = h.get("titel_kurz") or h.get("title") or ""
            line = f"• {h.get('item_number', '')} {title}".strip()
            if h.get("topic_name"):
                line += f" (dein Thema: {h['topic_name']})"
            elif h.get("top") and h.get("wichtig_grund"):
                line += f" – {h['wichtig_grund']}"
            parts.append(line)
    shown = {h.get("item_number") for h in highlights}
    rest = [(nr, names) for nr, names in by_item.items() if nr not in shown]
    if rest:
        parts.append("Zu deinen Themen: " + "; ".join(
            f"{nr} ({', '.join(n for n in names if n)})" for nr, names in rest
        ))

    n_items = int(s.get("n_items") or 0)
    if s.get("ksinr"):
        if n_items:
            parts.append(f"{n_items} öffentliche Punkte insgesamt.")
    else:
        parts.append("Die Tagesordnung veröffentlicht das Ratsinfo einige Tage vor der Sitzung.")

    if is_past:
        if decisions:
            parts.append(f"{decisions} {'Beschluss liegt' if decisions == 1 else 'Beschlüsse liegen'} vor – mit Ergebnis und Einordnung auf Ratslotse.")
        else:
            parts.append("Die Ergebnisse folgen mit dem Protokoll, oft erst Wochen später – Ratslotse meldet sich, sobald sie da sind.")

    parts.append("")
    parts.append("Tagesordnung, Vorlagen und Ergebnis auf Ratslotse:")
    parts.append(url)
    # Der Kurzname steht im Titel; der amtliche nur, wenn er sich unterscheidet.
    if short_committee(committee) != committee:
        parts.append(f"Amtlicher Name: {committee}. Ende der Sitzung geschätzt.")
    else:
        parts.append("Ende der Sitzung geschätzt.")
    return "\n".join(parts)
