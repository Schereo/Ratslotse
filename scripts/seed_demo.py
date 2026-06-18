#!/usr/bin/env python3
"""Seed the databases with realistic demo data for local pipeline testing.

The production databases are populated only by live scraping (NWZ login +
council site). That makes the AI pipeline (daily digest, council watcher,
committee summaries) impossible to exercise locally without credentials.

This script writes a self-contained, synthetic-but-realistic dataset:

  * several whole NWZ editions (full article bodies, mixed topics) across
    consecutive days, so the digest classifier has real true/false positives;
  * several council sessions — past and future — with agenda items, so the
    watcher (future sessions) and the session follow-up (past sessions) both
    have data to chew on;
  * a demo Telegram user with topics + committee subscriptions, so the
    per-user flows have something to match against.

All demo rows use high, reserved IDs (catalogs/ksinr ≥ 900000, a dedicated
demo chat_id) so they never collide with real scraped data and can be removed
again with ``--reset``.

Usage::

    python scripts/seed_demo.py            # seed (idempotent — overwrites demo rows)
    python scripts/seed_demo.py --reset    # remove all demo rows, then seed
    python scripts/seed_demo.py --clear    # only remove demo rows, don't seed

Target DBs default to ``data/nwz.sqlite`` / ``data/council.sqlite`` (the paths
the cron scripts read), overridable via the ``NWZ_DB`` / ``COUNCIL_DB`` env vars.
No LLM or network calls are made.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nwz.api import Edition  # noqa: E402
from nwz.parse import Article  # noqa: E402
from nwz.store import Store  # noqa: E402
from council.scraper import AgendaItem, CouncilSession  # noqa: E402
from council.store import CouncilStore  # noqa: E402

# Reserved ID ranges so demo rows never collide with real scraped data.
DEMO_CATALOG_BASE = 900_000
DEMO_KSINR_BASE = 900_000
DEMO_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID") or 999_000_001)
DEMO_FOLDER = 8389  # "Oldenburger Nachrichten" (see nwz.api.TITLES)


# --------------------------------------------------------------------------- #
# Demo content
# --------------------------------------------------------------------------- #

def _article(
    seq: int,
    page: int,
    category: str,
    title: str,
    subtitle: str,
    authors: list[str],
    body: str,
    priority: int = 0,
) -> Article:
    """Build an Article. refid mimics the NWZ 'articleid/PAGE/seq' format."""
    refid = f"{DEMO_CATALOG_BASE + seq}/{page}/{seq}"
    return Article(
        refid=refid,
        external_id=f"demo-{seq}",
        page=page,
        category_number=None,
        category_name=category,
        title=title,
        subtitle=subtitle,
        authors=authors,
        content_html=f"<p>{body}</p>",
        content_text=body,
        priority=priority,
    )


# Each edition is (offset_in_days_before_today, [articles]). The themes are
# chosen to give the topic matcher genuine positives AND tempting negatives
# (keyword overlap, nationwide-not-local, thematic-kinship) — mirroring the
# distinctions the eval cases in eval/cases.json test for.
EDITION_ARTICLES: list[tuple[int, list[Article]]] = [
    (2, [
        _article(
            1, 3, "Politik",
            "Stadtrat gibt grünes Licht für neues Fußballstadion",
            "Ratsmehrheit beschließt Förderung von 12 Millionen Euro",
            ["Anna Brink"],
            "Der Oldenburger Stadtrat hat in seiner Sitzung am Montag den Neubau eines "
            "Fußballstadions am Marschweg beschlossen. Mit 28 zu 19 Stimmen votierte die "
            "Mehrheit für eine städtische Förderung von zwölf Millionen Euro. Das Stadion "
            "soll bis 2028 fertig sein. Die Fraktion von Volt stimmte geschlossen dafür, die "
            "Grünen enthielten sich. Der VfB Oldenburg begrüßte die Entscheidung, Kritiker "
            "warnen vor den Folgekosten.",
            priority=9,
        ),
        _article(
            2, 5, "Lokales",
            "Neuer Radweg entlang der Nadorster Straße eröffnet",
            "Zwei Kilometer geschützte Spur für Radfahrer",
            ["Tim Sänger"],
            "Auf der Nadorster Straße in Oldenburg ist am Dienstag ein neuer, baulich "
            "getrennter Radweg eröffnet worden. Die Stadt investierte rund 800.000 Euro in "
            "den Ausbau des zwei Kilometer langen Abschnitts. Der ADFC lobte das Projekt als "
            "Schritt hin zu einem durchgängigen Radverkehrsnetz.",
            priority=6,
        ),
        _article(
            3, 8, "Kultur",
            "Oldenburger Kulturnacht lockt tausende Besucher",
            "Über 40 Veranstaltungsorte beteiligt",
            ["Marie Lux"],
            "Die diesjährige Kulturnacht in Oldenburg war ein voller Erfolg. An mehr als "
            "40 Orten in der Innenstadt gab es Konzerte, Lesungen und Ausstellungen. Die "
            "Veranstalter zählten mehrere tausend Besucher.",
            priority=3,
        ),
    ]),
    (1, [
        _article(
            4, 4, "Politik",
            "Volt Oldenburg stellt Kandidatenliste für Kommunalwahl 2026 vor",
            "Junge Partei tritt erstmals mit eigener Liste an",
            ["Anna Brink"],
            "Die Partei Volt hat ihre Liste für die Kommunalwahl 2026 in Oldenburg "
            "vorgestellt. Spitzenkandidatin ist die 29-jährige Informatikerin Lena Voß. "
            "Volt will sich vor allem für Digitalisierung der Verwaltung und den Ausbau des "
            "Radverkehrs einsetzen. Die Wahl findet am 13. September 2026 statt.",
            priority=8,
        ),
        _article(
            5, 6, "Wirtschaft",
            "Grüne fordern bundesweit höhere CO2-Bepreisung",
            "Parteitag in Berlin beschließt Klimaprogramm",
            ["dpa"],
            "Auf ihrem Bundesparteitag in Berlin haben die Grünen eine deutliche Anhebung "
            "der CO2-Bepreisung gefordert. Das Programm sieht zudem ein Tempolimit auf "
            "Autobahnen vor. Ein Bezug zu Oldenburg besteht nicht; es handelt sich um "
            "bundespolitische Beschlüsse.",
            priority=4,
        ),
        _article(
            6, 7, "Sport",
            "Handball: VfL Oldenburg verliert Heimspiel",
            "Knappe Niederlage gegen Tabellenführer",
            ["Jan Ros"],
            "Die Handballerinnen des VfL Oldenburg haben ihr Heimspiel am Samstag mit 27:29 "
            "verloren. Trotz starker zweiter Halbzeit reichte es nicht gegen den "
            "Tabellenführer. Mit Fußball oder dem geplanten Stadion hat die Partie nichts zu tun.",
            priority=5,
        ),
        _article(
            7, 9, "Lokales",
            "Stadt pflanzt 500 neue Bäume im Schlossgarten",
            "Programm gegen Hitzeinseln gestartet",
            ["Marie Lux"],
            "Die Stadt Oldenburg hat im Schlossgarten und entlang mehrerer Straßen 500 neue "
            "Bäume gepflanzt. Das Programm soll die Aufheizung der Innenstadt im Sommer "
            "abmildern. Die Maßnahme ist Teil des städtischen Klimaanpassungskonzepts.",
            priority=4,
        ),
    ]),
    (0, [
        _article(
            8, 3, "Politik",
            "Bauausschuss berät über Bebauungsplan für den Alten Hafen",
            "Anwohner kritisieren geplante Bauhöhe",
            ["Tim Sänger"],
            "Der Bauausschuss der Stadt Oldenburg wird in seiner nächsten Sitzung über den "
            "Bebauungsplan für das Areal am Alten Hafen entscheiden. Geplant sind Wohnungen "
            "und Gewerbe. Anwohnerinitiativen kritisieren die vorgesehene Bauhöhe von bis zu "
            "sieben Geschossen.",
            priority=7,
        ),
        _article(
            9, 5, "Lokales",
            "Neue Tempo-30-Zonen rund um Oldenburger Schulen",
            "Stadt reagiert auf Elternproteste",
            ["Anna Brink"],
            "Rund um sechs Oldenburger Grundschulen gelten ab sofort Tempo-30-Zonen. Die "
            "Stadt reagiert damit auf wiederholte Beschwerden von Eltern über zu schnellen "
            "Autoverkehr. Auch die Radverkehrsführung an den betroffenen Kreuzungen wird "
            "angepasst.",
            priority=6,
        ),
        _article(
            10, 11, "Vermischtes",
            "Wochenmarkt feiert 150-jähriges Bestehen",
            "Jubiläumsfest auf dem Rathausmarkt",
            ["Marie Lux"],
            "Der Oldenburger Wochenmarkt feiert in diesem Jahr sein 150-jähriges Bestehen. "
            "Zum Jubiläum gibt es ein großes Fest auf dem Rathausmarkt mit regionalen "
            "Erzeugern und Musik.",
            priority=2,
        ),
    ]),
]


def _session(
    seq: int,
    committee: str,
    day_offset: int,
    time: str,
    location: str,
    items: list[AgendaItem],
) -> CouncilSession:
    session_date = (date.today() + timedelta(days=day_offset)).isoformat()
    return CouncilSession(
        ksinr=DEMO_KSINR_BASE + seq,
        committee=committee,
        session_date=session_date,
        session_time=time,
        location=location,
        agenda_items=items,
    )


def build_sessions() -> list[CouncilSession]:
    return [
        # Future session with real content (watcher + committee summary path).
        _session(
            1, "Bauausschuss", day_offset=8, time="18:00", location="Rathaus, Saal A",
            items=[
                AgendaItem("Ö 1", "Genehmigung der Tagesordnung"),  # routine
                AgendaItem("Ö 2", "Bebauungsplan Nr. 742 – Alter Hafen", vorlage_nr="26/0411"),
                AgendaItem("Ö 3", "Radwegekonzept Innenstadt – Sachstandsbericht", vorlage_nr="26/0418"),
                AgendaItem("Ö 4", "Einwohnerfragestunde"),  # routine
                AgendaItem("N 1", "Personalangelegenheit", is_public=False),
            ],
        ),
        # Future session, stadium topic (overlaps with NWZ stadium article).
        _session(
            2, "Stadtentwicklungsausschuss", day_offset=15, time="17:00", location="Rathaus, Saal B",
            items=[
                AgendaItem("Ö 1", "Genehmigung der Niederschrift"),  # routine
                AgendaItem("Ö 2", "Neubau Fußballstadion Marschweg – Finanzierung", vorlage_nr="26/0395"),
                AgendaItem("Ö 3", "Klimaanpassungskonzept – Baumpflanzprogramm", vorlage_nr="26/0402"),
            ],
        ),
        # Future session with ONLY routine items (tests has_content=false path).
        _session(
            3, "Finanzausschuss", day_offset=22, time="16:00", location="Rathaus, Saal C",
            items=[
                AgendaItem("Ö 1", "Genehmigung der Tagesordnung"),
                AgendaItem("Ö 2", "Mitteilungen der Verwaltung"),
                AgendaItem("Ö 3", "Anfragen und Verschiedenes"),
            ],
        ),
        # Past session (session follow-up path: looks for NWZ coverage after).
        _session(
            4, "Rat der Stadt", day_offset=-12, time="16:00", location="Rathaus, Ratssaal",
            items=[
                AgendaItem("Ö 1", "Genehmigung der Tagesordnung"),
                AgendaItem("Ö 2", "Neubau Fußballstadion Marschweg – Grundsatzbeschluss", vorlage_nr="26/0380"),
                AgendaItem("Ö 3", "Haushaltssatzung 2026", vorlage_nr="26/0355"),
            ],
        ),
    ]


COMMITTEES: list[tuple[str, int | None]] = [
    ("Bauausschuss", None),
    ("Stadtentwicklungsausschuss", None),
    ("Finanzausschuss", None),
    ("Rat der Stadt", None),
]

TOPICS: list[tuple[str, str]] = [
    ("Stadion Oldenburg",
     "Neubau und Finanzierung des Fußballstadions am Marschweg in Oldenburg, "
     "Entscheidungen des Stadtrats dazu. Kein allgemeiner Sport."),
    ("Volt Oldenburg",
     "Aktivitäten, Abstimmungsverhalten und Kandidaten der Partei Volt in der "
     "Oldenburger Kommunalpolitik. Keine bundesweiten Volt-Nachrichten."),
    ("Radverkehr Oldenburg",
     "Ausbau von Radwegen, Radverkehrsführung und Verkehrsberuhigung in Oldenburg."),
]


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #

def _nwz_path() -> Path:
    return Path(os.environ.get("NWZ_DB") or ROOT / "data" / "nwz.sqlite")


def _council_path() -> Path:
    return Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def clear_demo(store: Store, council: CouncilStore) -> None:
    """Remove only demo-owned rows (reserved IDs / demo chat) from both DBs."""
    conn = store._conn
    with conn:
        conn.execute("DELETE FROM articles WHERE catalog >= ?", (DEMO_CATALOG_BASE,))
        conn.execute("DELETE FROM articles_fts WHERE catalog >= ?", (DEMO_CATALOG_BASE,))
        conn.execute("DELETE FROM editions WHERE catalog >= ?", (DEMO_CATALOG_BASE,))
        conn.execute("DELETE FROM topics WHERE chat_id = ?", (DEMO_CHAT_ID,))
        conn.execute("DELETE FROM committee_subscriptions WHERE chat_id = ?", (DEMO_CHAT_ID,))
        conn.execute("DELETE FROM article_topic_matches WHERE chat_id = ?", (DEMO_CHAT_ID,))
        conn.execute("DELETE FROM topic_classified_editions WHERE chat_id = ?", (DEMO_CHAT_ID,))
        conn.execute("DELETE FROM users WHERE chat_id = ?", (DEMO_CHAT_ID,))
    ccon = council._conn
    with ccon:
        ccon.execute("DELETE FROM council_agenda_items WHERE ksinr >= ?", (DEMO_KSINR_BASE,))
        ccon.execute("DELETE FROM council_sessions WHERE ksinr >= ?", (DEMO_KSINR_BASE,))
        ccon.execute("DELETE FROM committee_summaries WHERE ksinr >= ?", (DEMO_KSINR_BASE,))
        ccon.execute("DELETE FROM council_alerts_sent WHERE ksinr >= ?", (DEMO_KSINR_BASE,))
        ccon.execute("DELETE FROM committee_notifications WHERE ksinr >= ?", (DEMO_KSINR_BASE,))
        ccon.execute("DELETE FROM session_followups_sent WHERE ksinr >= ?", (DEMO_KSINR_BASE,))


def seed(store: Store, council: CouncilStore) -> dict[str, int]:
    # --- NWZ editions + articles ---
    n_articles = 0
    for offset, articles in EDITION_ARTICLES:
        pub_date = (date.today() - timedelta(days=offset)).isoformat()
        catalog = DEMO_CATALOG_BASE + offset  # stable per day → re-runs overwrite
        edition = Edition(
            customer="nwz",
            folder=DEMO_FOLDER,
            catalog=catalog,
            title="Oldenburger Nachrichten (Demo)",
            publication_date=pub_date,
            pages=max((a.page for a in articles), default=1),
            content_version=1,
        )
        # refids carry a global seq, but catalog must match the edition we save.
        for a in articles:
            a.refid = f"{catalog}/{a.page}/{a.refid.split('/')[-1]}"
        store.save_edition(edition, articles)
        n_articles += len(articles)

    # --- demo Telegram user + topics + subscriptions ---
    store.add_user(DEMO_CHAT_ID, "demo")
    for name, desc in TOPICS:
        store.add_topic(DEMO_CHAT_ID, name, desc)
    for committee, _ in COMMITTEES:
        store.subscribe(DEMO_CHAT_ID, committee)

    # --- council committees + sessions ---
    council.save_committees(COMMITTEES)
    sessions = build_sessions()
    for s in sessions:
        council.save_session(s)

    return {
        "editions": len(EDITION_ARTICLES),
        "articles": n_articles,
        "topics": len(TOPICS),
        "subscriptions": len(COMMITTEES),
        "sessions": len(sessions),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data for local pipeline testing")
    parser.add_argument("--reset", action="store_true", help="Remove demo rows before seeding")
    parser.add_argument("--clear", action="store_true", help="Only remove demo rows, don't seed")
    args = parser.parse_args()

    nwz_path, council_path = _nwz_path(), _council_path()
    print(f"NWZ DB     : {nwz_path}")
    print(f"Council DB : {council_path}")
    print(f"Demo chat_id: {DEMO_CHAT_ID}\n")

    store = Store(nwz_path)
    council = CouncilStore(str(council_path))
    try:
        if args.reset or args.clear:
            clear_demo(store, council)
            print("Removed existing demo rows.")
        if args.clear:
            print("Done (--clear: nothing seeded).")
            return

        # Idempotency: topics would otherwise duplicate on re-run.
        if not (args.reset):
            store._conn.execute("DELETE FROM topics WHERE chat_id = ?", (DEMO_CHAT_ID,))
            store._conn.commit()

        stats = seed(store, council)
        print("Seeded demo data:")
        for k, v in stats.items():
            print(f"  {k:14}: {v}")
        print("\nNWZ editions now in DB:")
        for row in store.edition_summary():
            print(f"  {row[0]}  {row[1]}  ({row[3]} Artikel)")
        print("\nUpcoming council sessions now in DB:")
        for s in council.upcoming_sessions(limit=10):
            print(f"  {s['session_date']}  {s['committee']}  ({s['n_items']} TOP)")
    finally:
        store.close()
        council.close()


if __name__ == "__main__":
    main()
