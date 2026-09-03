from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from .dringlichkeit import zusatz_punkte

BASE = "https://buergerinfo.oldenburg.de"
_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_TIME_RE = re.compile(r"(\d{2}:\d{2})")


@dataclass
class AgendaItem:
    item_number: str        # "Ö 6.1", "N 17"
    title: str
    template_number: str = ""   # e.g. "26/0396"
    kvonr: int | None = None
    is_public: bool = True
    # Anhänge des TOP von der Sitzungsseite (Tims Befund 12.08.: sie fehlten
    # in der App komplett — gerade Fraktions-Anträge OHNE Vorlage hängen NUR
    # hier). [{"label": …, "url": absolute getfile-URL}]
    anlagen: list = field(default_factory=list)


@dataclass
class ScheduledSession:
    """Terminierte Sitzung aus dem Sitzungskalender, noch OHNE Tagesordnung.

    SessionNet verlinkt eine Sitzung erst, wenn ihre Tagesordnung
    veröffentlicht ist — vorher steht sie nur als Text im Kalender
    (kein __ksinr im HTML, si0057.php antwortet mit 302). Ohne dieses
    Parsing wären neue Terminpläne wochenlang unsichtbar.
    """
    committee: str
    session_date: str       # YYYY-MM-DD
    session_time: str = ""  # HH:MM oder ""
    location: str = ""


@dataclass
class CouncilSession:
    ksinr: int
    committee: str
    session_date: str       # YYYY-MM-DD
    session_time: str       # HH:MM
    location: str
    agenda_items: list[AgendaItem] = field(default_factory=list)

    @property
    def is_future(self) -> bool:
        return self.session_date >= date.today().isoformat()

    @property
    def url(self) -> str:
        return f"{BASE}/si0057.php?__ksinr={self.ksinr}"


_RSS_DATE_RE = re.compile(r"Datum:\s*(\d{2})\.(\d{2})\.(\d{4})")
_RSS_TIME_RE = re.compile(r"Zeit:\s*(\d{2}:\d{2})")
_RSS_ORT_RE = re.compile(r"Ort:\s*(.+)$")
_RSS_GREMIUM_RE = re.compile(r"Gremium:\s*(.+?)\s*Datum:")


def _extract_rss_scheduled(xml_text: str) -> list[ScheduledSession]:
    """Sitzungs-Items aus dem RIS-RSS-Feed (rssfeed.php?filter=s).

    Ergänzt den Kalender: nichtöffentliche Gremien (z. B. Verwaltungsausschuss)
    fehlen in der Kalenderansicht, stehen aber im Feed. Beschreibung hat das
    feste Format "Gremium: … Datum: DD.MM.YYYY Zeit: HH:MM Uhr Ort: …".
    """
    import warnings

    from bs4 import XMLParsedAsHTMLWarning

    out: list[ScheduledSession] = []
    with warnings.catch_warnings():
        # html.parser reicht für das flache RSS-Format völlig; lxml (für
        # features="xml") ist bewusst keine Abhängigkeit.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(xml_text, "html.parser")
    for item in soup.find_all("item"):
        title = item.find("title")
        desc = item.find("description")
        if not title or not desc or not title.get_text(strip=True).startswith("Sitzung:"):
            continue
        text = desc.get_text(" ", strip=True)
        m_date = _RSS_DATE_RE.search(text)
        m_gremium = _RSS_GREMIUM_RE.search(text)
        if not m_date or not m_gremium:
            continue
        d, mo, y = m_date.groups()
        m_time = _RSS_TIME_RE.search(text)
        m_ort = _RSS_ORT_RE.search(text)
        out.append(ScheduledSession(
            committee=m_gremium.group(1),
            session_date=f"{y}-{mo}-{d}",
            session_time=m_time.group(1) if m_time else "",
            location=m_ort.group(1).strip() if m_ort else "",
        ))
    return out


def _extract_session_ids(soup: BeautifulSoup) -> list[int]:
    ids: list[int] = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"__ksinr=(\d+)", a["href"])
        if m:
            ksinr = int(m.group(1))
            if ksinr not in ids:
                ids.append(ksinr)
    return ids


def _extract_location(soup: BeautifulSoup) -> str:
    """Sitzungsort von der Detailseite.

    Die Überschrift nennt ihn nicht (sie endet nach der Uhrzeit) — er steht im
    Feld „Raum" der Kopftabelle, das SessionNet mit der Klasse ``siort``
    auszeichnet. Vorher wurde er aus der Überschrift geraten, was für jede
    Sitzung einen leeren Ort ergab und in der Tagesordnungs-Mail eine nackte
    Ortsmarke ohne Ort hinterließ.
    """
    cell = soup.find("div", class_="siort") or soup.find("td", class_="siort")
    if not cell:
        return ""
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip(" ,")


def _extract_scheduled(soup: BeautifulSoup, year: int, month: int) -> list[ScheduledSession]:
    """Kalenderzeilen parsen: <td class="silink"> trägt Gremium/Zeit/Ort,
    der Tag steht in <td class="smc_fct_day"> derselben Zeile."""
    out: list[ScheduledSession] = []
    for cell in soup.find_all("td", class_="silink"):
        header = cell.find("div", class_="smc-el-h")
        committee = header.get_text(" ", strip=True) if header else ""
        if not committee:
            continue
        row = cell.find_parent("tr")
        day_cell = row.find("td", class_="smc_fct_day") if row else None
        day_text = day_cell.get_text(strip=True) if day_cell else ""
        if not day_text.isdigit():
            continue
        session_time = ""
        location_parts: list[str] = []
        for li in cell.find_all("li"):
            text = li.get_text(" ", strip=True)
            m = _TIME_RE.search(text)
            if m and not session_time:
                session_time = m.group(1)
            elif text:
                location_parts.append(text)
        out.append(ScheduledSession(
            committee=committee,
            session_date=f"{year:04d}-{month:02d}-{int(day_text):02d}",
            session_time=session_time,
            location=", ".join(location_parts),
        ))
    return out


class CouncilScraper:
    def __init__(self, delay: float = 0.5):
        self._s = requests.Session()
        self._s.headers["User-Agent"] = "Mozilla/5.0"
        self._delay = delay

    def _get(self, path: str, **params) -> BeautifulSoup:
        r = self._s.get(f"{BASE}/{path}", params=params, timeout=20)
        r.raise_for_status()
        time.sleep(self._delay)
        return BeautifulSoup(r.text, "html.parser")

    def session_ids_for_month(self, year: int, month: int) -> list[int]:
        soup = self._get("si0040.php", __cjahr=year, __cmonat=month)
        return _extract_session_ids(soup)

    def calendar_month(self, year: int, month: int) -> tuple[list[int], list[ScheduledSession]]:
        """One calendar fetch → (verlinkte Sitzungs-IDs, alle terminierten Sitzungen).

        Terminierte Sitzungen stehen auch dann im Kalender, wenn noch keine
        Tagesordnung veröffentlicht ist (dann ohne Link/ksinr).
        """
        soup = self._get("si0040.php", __cjahr=year, __cmonat=month)
        return _extract_session_ids(soup), _extract_scheduled(soup, year, month)

    def upcoming_session_ids(self, months_ahead: int = 3) -> list[int]:
        """Collect all session IDs for today's month through months_ahead months ahead."""
        return self.upcoming_calendar(months_ahead=months_ahead)[0]

    def rss_scheduled(self) -> list[ScheduledSession]:
        """Terminierte Sitzungen aus dem RSS-Feed (ergänzt nichtöffentliche
        Gremien, die die Kalenderansicht nicht listet). Best effort."""
        try:
            r = self._s.get(f"{BASE}/rssfeed.php", params={"filter": "s"}, timeout=20)
            r.raise_for_status()
            time.sleep(self._delay)
        except requests.RequestException:
            return []
        return _extract_rss_scheduled(r.text)

    def upcoming_calendar(self, months_ahead: int = 3) -> tuple[list[int], list[ScheduledSession]]:
        """Kalender von diesem Monat bis months_ahead Monate voraus:
        (verlinkte Sitzungs-IDs, terminierte Sitzungen — auch ohne Tagesordnung).
        Der RSS-Feed läuft mit ein; Duplikate filtert der Store über den
        Primärschlüssel (Gremium, Datum, Zeit)."""
        ids: list[int] = []
        scheduled: list[ScheduledSession] = []
        today = date.today()
        for delta in range(months_ahead + 1):
            target = today.replace(day=1) + timedelta(days=32 * delta)
            month_ids, month_scheduled = self.calendar_month(target.year, target.month)
            for sid in month_ids:
                if sid not in ids:
                    ids.append(sid)
            scheduled.extend(month_scheduled)
        scheduled.extend(self.rss_scheduled())
        return ids, scheduled

    def past_session_ids(self, months_back: int = 3) -> list[int]:
        """Verlinkte Sitzungs-IDs der letzten ``months_back`` Monate — der Blick
        zurück, den ``upcoming_calendar`` nicht hat.

        **Warum es den braucht.** Der Kalenderlauf ging vom laufenden Monat nur
        nach vorn. Was er in seinem Fenster verpasste — ein ausgefallener
        Cron-Lauf, eine erst kurz vor der Sitzung veröffentlichte Tagesordnung,
        eine nachträglich ins Ratsinfo eingetragene Sitzung —, sah er **nie
        wieder**: Am nächsten Tag lag der Monat hinter dem Fenster. Am
        03.09.2026 fehlten dadurch 14 der 79 verlinkten Sitzungen des Jahres
        2026, darunter die einzige Sitzung des Ausschusses für
        Wirtschaftsförderung (04.05.2026) — der Ausschuss stand auf der
        Abo-Seite bei „0 Beschlüsse 2026", obwohl er getagt hatte. Acht der
        Vierzehn liegen in einer einzigen Woche; ein Ausfall in der Woche
        darauf ist damit dauerhaft ein Loch im Bestand.

        Nur die IDs, keine Termine: Der Terminplan
        (``replace_scheduled_sessions``) beschreibt, was noch kommt, und würde
        von vergangenen Kalenderzeilen nur zugemüllt.
        """
        ids: list[int] = []
        target = date.today().replace(day=1)
        for _ in range(months_back):
            # Rückwärts über den Monatsersten: minus ein Tag landet immer im
            # Vormonat, egal wie lang der ist.
            target = (target - timedelta(days=1)).replace(day=1)
            for sid in self.session_ids_for_month(target.year, target.month):
                if sid not in ids:
                    ids.append(sid)
        return ids

    def fetch_session(self, ksinr: int) -> CouncilSession | None:
        soup = self._get("si0057.php", __ksinr=ksinr)
        h1 = soup.find("h1")
        if not h1:
            return None
        header = h1.get_text(" ", strip=True).replace("\xa0", " ")

        # Parse: "Committee - DD.MM.YYYY - HH:MM Uhr - Location"
        parts = [p.strip() for p in header.split(" - ")]
        committee = parts[0] if parts else "Unbekannt"

        date_match = _DATE_RE.search(header)
        if not date_match:
            return None
        d, mo, y = date_match.groups()
        session_date = f"{y}-{mo}-{d}"

        time_match = _TIME_RE.search(header)
        session_time = time_match.group(1) if time_match else ""

        location = _extract_location(soup)
        if not location and len(parts) >= 4:
            # Ältere Seiten trugen den Ort in der Überschrift.
            location = re.sub(r"\d{2}:\d{2}\s*Uhr", "", parts[-1]).strip()

        agenda_items = self._parse_agenda(soup)

        return CouncilSession(
            ksinr=ksinr,
            committee=committee,
            session_date=session_date,
            session_time=session_time,
            location=location,
            agenda_items=agenda_items,
        )

    def _parse_agenda(self, soup: BeautifulSoup) -> list[AgendaItem]:
        items: list[AgendaItem] = []
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            num_text = cells[0].get_text(strip=True)
            # Agenda items start with Ö or N followed by a number
            if not re.match(r"^[ÖöN]\s*\d", num_text):
                continue
            title = cells[1].get_text(" ", strip=True)
            if not title:
                continue

            template_number = ""
            kvonr: int | None = None
            if len(cells) >= 3:
                template_number = cells[2].get_text(strip=True)

            # Extract kvonr from any link in the row
            for a in row.find_all("a", href=True):
                m = re.search(r"__kvonr=(\d+)", a["href"])
                if m:
                    kvonr = int(m.group(1))
                    break

            # Dokument-Anhänge der Zeile: getfile-Links, je id einmal —
            # SessionNet setzt Icon- und Text-Link mit derselben id, das Label
            # trägt der Text-Link. Nichtöffentliche TOPs haben keine.
            anlagen: list[dict] = []
            gesehen_ids: set[str] = set()
            for a in row.find_all("a", href=True):
                m = re.search(r"getfile\.php\?id=(\d+)", a["href"])
                if not m:
                    continue
                label = a.get_text(" ", strip=True)
                if m.group(1) in gesehen_ids:
                    if label:  # Text-Link ersetzt das leere Icon-Label
                        for e in anlagen:
                            if e["_id"] == m.group(1) and not e["label"]:
                                e["label"] = label
                    continue
                gesehen_ids.add(m.group(1))
                anlagen.append({"_id": m.group(1), "label": label,
                                "url": f"{BASE}/{a['href'].lstrip('/')}"})
            for e in anlagen:
                e.pop("_id", None)
                if not e["label"]:
                    e["label"] = "Anlage"

            is_public = num_text.upper().startswith("Ö")
            items.append(AgendaItem(
                item_number=num_text,
                title=title,
                template_number=template_number,
                kvonr=kvonr,
                is_public=is_public,
                anlagen=anlagen if is_public else [],
            ))

        # Dringlichkeitsanträge haben keinen eigenen Punkt — sie hängen als
        # Dokument an „Ö 2 Genehmigung der Tagesordnung", weil dort über ihre
        # Aufnahme abgestimmt wird. Ohne diesen Schritt fallen sie durch jedes
        # Raster: Die Formalie fliegt überall heraus, und die Labels der
        # Zeilen-Dokumente liest für die Vorschau niemand (Tims Befund
        # 30.08.26, gemessen: 12 von 40 Ratssitzungen hatten einen).
        items.extend(zusatz_punkte(items))
        return items

    def fetch_committee_list(self) -> list[tuple[str, int | None]]:
        """Fetch all committees (Gremien) from the Gremienübersicht page."""
        soup = self._get("gr0040.php")
        result: list[tuple[str, int | None]] = []
        for td in soup.find_all("td", class_="grname"):
            a = td.find("a", href=True)
            if a:
                name = a.get_text(strip=True)
                m = re.search(r"__kgrnr=(\d+)", a["href"])
                kgrnr = int(m.group(1)) if m else None
            else:
                name = td.get_text(strip=True)
                kgrnr = None
            if name:
                result.append((name, kgrnr))
        return result

    def fetch_proposal_text(self, kvonr: int) -> str:
        """Fetch the full text of a Vorlage (proposal document)."""
        soup = self._get("vo0050.php", __kvonr=kvonr)
        # Main content is usually in a <div> or <td> with the proposal body
        # Strip navigation, tables with metadata, keep paragraph text
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        # The proposal text is typically in a specific content div
        content = soup.find("div", id="dokumentenbereich") or soup.find("div", class_="WordSection1")
        if content:
            return content.get_text(" ", strip=True)
        # Fallback: get all paragraph text from the page body
        body = soup.find("body")
        if body:
            paras = [p.get_text(" ", strip=True) for p in body.find_all("p")]
            return " ".join(p for p in paras if len(p) > 20)
        return ""
