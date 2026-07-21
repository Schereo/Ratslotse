"""Terminierte Sitzungen ohne veröffentlichte Tagesordnung (RIS-Kalender).

SessionNet verlinkt eine Sitzung erst, wenn ihre Tagesordnung online ist —
vorher steht sie nur als Text im Kalender (kein __ksinr im HTML). Diese Tests
sichern das Kalender-Parsing und den Merge in upcoming_sessions ab.
"""
from __future__ import annotations

from datetime import date, timedelta

from bs4 import BeautifulSoup

from council.scraper import (
    AgendaItem,
    CouncilSession,
    _extract_rss_scheduled,
    _extract_scheduled,
    _extract_session_ids,
)
from council.store import CouncilStore

# Reales Markup von buergerinfo.oldenburg.de/si0040.php (21.07.2026), gekürzt:
# eine Zeile ohne Link (Tagesordnung folgt), eine mit Link (veröffentlicht).
CALENDAR_HTML = """
<table>
<tr>
  <td class="smc-table-cell-block-991 smc-table-cell-heading smc_fct_day_991"><span class="weekday">13</span> <a title="Donnerstag" class="weekday">Do</a></td>
  <td class="smc-t-cn991 smc_fct_day"><span class="weekday">13</span></td>
  <td class="smc-t-cn991 smc_fct_daytext"><a title="Donnerstag" class="weekday">Do</a></td>
  <td data-label="Sitzung" class="smc-t-cl991 silink"><div class="smc-el-h ">Ausschuss f&uuml;r Stadtgr&uuml;n, Umwelt und Klima<!--SMCINFO:si.bi --></div><ul class="list-inline smc-detail-list"><li class="list-inline-item">17:00&nbsp;Uhr</li><li class="list-inline-item">Alte Fleiwa, Industriestra&szlig;e 1d, Sitzungssaal 1/2</li></ul></td>
  <td data-label="Mandant" class="smc-t-cl991 pagel pagel3"></td>
  <td data-label="Dokumente" class="smc-t-cl991 sidocs"></td>
</tr>
<tr>
  <td class="smc-t-cn991 smc_fct_day"><span class="weekday">27</span></td>
  <td class="smc-t-cn991 smc_fct_daytext"><a title="Donnerstag" class="weekday">Do</a></td>
  <td data-label="Sitzung" class="smc-t-cl991 silink"><div class="smc-el-h "><a href="si0057.php?__ksinr=4711">Rat der Stadt</a></div><ul class="list-inline smc-detail-list"><li class="list-inline-item">16:00&nbsp;Uhr</li><li class="list-inline-item">Kulturzentrum PFL, Peterstra&szlig;e 3</li></ul></td>
</tr>
</table>
"""


def test_extract_scheduled_parses_rows_without_links():
    soup = BeautifulSoup(CALENDAR_HTML, "html.parser")
    rows = _extract_scheduled(soup, 2026, 8)
    assert len(rows) == 2
    first = rows[0]
    assert first.committee == "Ausschuss für Stadtgrün, Umwelt und Klima"
    assert first.session_date == "2026-08-13"
    assert first.session_time == "17:00"
    assert first.location == "Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2"
    # Zeile MIT Link wird ebenfalls erfasst (Merge dedupliziert später).
    assert rows[1].committee == "Rat der Stadt"
    assert rows[1].session_date == "2026-08-27"
    # Verlinkte IDs kommen weiterhin aus den hrefs.
    assert _extract_session_ids(soup) == [4711]


# Reales Format des RIS-RSS-Feeds (rssfeed.php?filter=s, 21.07.2026) — er
# listet auch nichtöffentliche Gremien, die die Kalenderansicht auslässt.
RSS_XML = """<?xml version="1.0" encoding="UTF-8"?> <rss version="0.91"> <channel>
<title>Ratsinformationen der Stadt Oldenburg</title>
<item> <title>Sitzung: Verwaltungsausschuss 17.08.2026</title>
<description>Gremium: Verwaltungsausschuss Datum: 17.08.2026 Zeit: 17:00 Uhr Ort: Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2</description>
<category>Sitzungen</category> </item>
<item> <title>Vorlage: 26/0815</title> <description>Irgendeine Vorlage</description> </item>
</channel> </rss>"""


def test_extract_rss_scheduled():
    rows = _extract_rss_scheduled(RSS_XML)
    assert len(rows) == 1
    assert rows[0].committee == "Verwaltungsausschuss"
    assert rows[0].session_date == "2026-08-17"
    assert rows[0].session_time == "17:00"
    assert rows[0].location == "Alte Fleiwa, Industriestraße 1d, Sitzungssaal 1/2"


def _scheduled(committee: str, day_offset: int, time_: str = "17:00"):
    from council.scraper import ScheduledSession
    return ScheduledSession(
        committee=committee,
        session_date=(date.today() + timedelta(days=day_offset)).isoformat(),
        session_time=time_,
        location="Alte Fleiwa",
    )


def test_upcoming_sessions_merges_scheduled(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    future = (date.today() + timedelta(days=30)).isoformat()
    store.save_session(CouncilSession(
        ksinr=100, committee="Verkehrsausschuss", session_date=future,
        session_time="17:00", location="Fleiwa",
        agenda_items=[AgendaItem(item_number="Ö 1", title="Radweg")],
    ))
    store.replace_scheduled_sessions([
        _scheduled("Kulturausschuss", 20),
        # Gleiches Gremium + Datum wie die echte Sitzung → wird verdeckt.
        _scheduled("Verkehrsausschuss", 30),
    ])

    rows = store.upcoming_sessions()
    assert [(r["committee"], r["ksinr"], r["n_items"]) for r in rows] == [
        ("Kulturausschuss", None, 0),
        ("Verkehrsausschuss", 100, 1),
    ]
    store.close()


def test_replace_scheduled_sessions_is_full_swap(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store.replace_scheduled_sessions([_scheduled("Kulturausschuss", 10)])
    store.replace_scheduled_sessions([_scheduled("Jugendhilfeausschuss", 12)])
    rows = store.upcoming_sessions()
    assert [r["committee"] for r in rows] == ["Jugendhilfeausschuss"]
    # Vergangene Termine tauchen nicht auf.
    store.replace_scheduled_sessions([_scheduled("Kulturausschuss", -3)])
    assert store.upcoming_sessions() == []
    store.close()
