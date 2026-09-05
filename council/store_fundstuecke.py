"""Fundstücke, Themenfeld-Rückblicke und der Social-Text.

Neunter und letzter Schnitt an ``store.py``. Drei kleine Bestände, die
dasselbe tun: Sie machen aus dem Ratsbetrieb etwas zum Lesen — die Karte des
Tages, den Rückblick auf ein Themenfeld, den Satz unter einem Bild.

Die Beschluss-Kennzahlen, die sie dafür abfragen (``count_decisions_since``,
``top_amount_since``, ``most_interesting_recent``, ``decision_votes_for``,
``anlagen_fuer``), sind NICHT mitgekommen: Sie zählen Beschlüsse und gehören
dem Beschluss-Kern, auch wenn hier der einzige Leser sitzt.
"""
from __future__ import annotations

from datetime import datetime
from council.store_basis import StoreBasis

class FundstueckeMixin(StoreBasis):
    """Fundstücke, Rückblicke, Social-Text — nur zum Mitvererben."""

    #: Gewichte des Fundwerts. Erzählbarkeit zählt etwas mehr als Tragweite
    #: — ein Haushaltsbeschluss ist bedeutend, aber kein Fundstück. Die
    #: Sperren darunter sind der eigentliche Hebel: Ohne sie gewinnt die
    #: Kuriosität, weil sie leichter hohe Interest-Werte erreicht.
    FUND_GEWICHT_INTERESSE = 0.55

    FUND_GEWICHT_TRAGWEITE = 0.45

    FUND_MIN_INTERESSE = 50

    FUND_MIN_TRAGWEITE = 50

    def save_social_text(self, ksinr: int, item_number: str, text: str,
                         source: str) -> None:
        """Kartentext eines TOP festhalten (siehe agenda_item_social)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO agenda_item_social "
                "(ksinr, item_number, text, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (ksinr, item_number, text, source, now))

    def fundstueck_candidates(
        self, *, mmdd: str | None = None, exclude_ids: set[int] | None = None, limit: int = 10
    ) -> list[dict]:
        """Kandidaten fürs Fundstück, bester Gesamtwert zuerst.

        ZWEI Werte, nicht einer. Bis 20.08.26 entschied allein ``interest``
        — und der misst Erzählbarkeit, nicht Bedeutung. Herausgekommen sind
        „Straßenbenennung Rotkäppchenweg" (Interesse 90, Tragweite 35) und
        „Modellvorhaben Cannabis" (Interesse 90, Tragweite 5), zweimal in
        derselben Woche sogar zwei Straßenbenennungen. Kurios, aber kein
        Fund, über den man reden will (Tims Befund).

        Ein Fundstück braucht beides: Es muss etwas BEDEUTEN und sich
        erzählen lassen. Deshalb ein gewichteter Mittelwert und ein
        Mindestmaß an Tragweite als Sperre — sonst gewinnt die Kuriosität
        wieder allein.

        ``mmdd`` („07-22") filtert auf Jahrestage (gleicher Kalendertag,
        früheres Jahr).
        """
        exclude = exclude_ids or set()
        sql = """SELECT d.id, d.title, d.official_text, d.summary, d.outcome, d.vote,
                        d.amount_eur, d.interest, d.impact, d.no_votes,
                        cs.committee, cs.session_date,
                        (? * d.interest + ? * d.impact) AS fundwert
                 FROM council_decisions d
                 JOIN council_sessions cs ON cs.ksinr = d.ksinr
                 WHERE d.kind = 'decision'
                   AND d.interest IS NOT NULL AND d.impact IS NOT NULL
                   AND d.interest >= ? AND d.impact >= ?
                   AND cs.session_date < date('now')"""
        args: list = [self.FUND_GEWICHT_INTERESSE, self.FUND_GEWICHT_TRAGWEITE,
                      self.FUND_MIN_INTERESSE, self.FUND_MIN_TRAGWEITE]
        if mmdd:
            sql += " AND strftime('%m-%d', cs.session_date) = ?"
            args.append(mmdd)
        sql += " ORDER BY fundwert DESC, cs.session_date DESC LIMIT ?"
        args.append(limit + len(exclude))
        rows = [dict(r) for r in self._conn.execute(sql, args).fetchall()]
        return [r for r in rows if r["id"] not in exclude][:limit]

    def get_fundstueck(self, day: str) -> dict | None:
        """Fundstück eines Tages inklusive Beschluss-Metadaten."""
        row = self._conn.execute(
            """SELECT f.day, f.kicker, f.story, f.decision_id,
                      d.title, d.outcome, d.vote, cs.committee, cs.session_date
               FROM council_daily_finds f
               JOIN council_decisions d ON d.id = f.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE f.day = ?""",
            (day,),
        ).fetchone()
        return dict(row) if row else None

    def save_fundstueck(self, day: str, decision_id: int, kicker: str, story: str) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT INTO council_daily_finds (day, decision_id, kicker, story, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(day) DO UPDATE SET
                     decision_id = excluded.decision_id, kicker = excluded.kicker,
                     story = excluded.story, created_at = excluded.created_at""",
                (day, decision_id, kicker, story, datetime.now().isoformat(timespec="seconds")),
            )

    def fundstueck_days_present(self, days: list[str]) -> set[str]:
        if not days:
            return set()
        marks = ",".join("?" for _ in days)
        rows = self._conn.execute(
            f"SELECT day FROM council_daily_finds WHERE day IN ({marks})", days
        ).fetchall()
        return {r["day"] for r in rows}

    def recent_fundstueck_decision_ids(self, within_days: int = 180) -> set[int]:
        """Zuletzt verwendete Beschlüsse — nicht zweimal kurz nacheinander zeigen."""
        rows = self._conn.execute(
            "SELECT decision_id FROM council_daily_finds WHERE day >= date('now', ?)",
            (f"-{int(within_days)} days",),
        ).fetchall()
        return {r["decision_id"] for r in rows}

    def recent_fundstueck_titles(self, within_days: int = 45) -> list[str]:
        """Titel der zuletzt gezeigten Fundstücke — Grundlage der
        Themen-Sperre.

        Die ID-Sperre allein reicht nicht: Ein Großprojekt zieht sich über
        viele EINZELNE Beschlüsse (Stadionneubau, Gründung der GmbH,
        Ausfallbürgschaft, Grundstücksübertragung, Anmietung der Halle).
        Alle haben hohe Werte, keiner wiederholt einen anderen — und
        zusammen ergäben sie eine Woche lang dieselbe Geschichte.
        """
        rows = self._conn.execute(
            """SELECT d.title FROM council_daily_finds f
               JOIN council_decisions d ON d.id = f.decision_id
               WHERE f.day >= date('now', ?)""",
            (f"-{int(within_days)} days",),
        ).fetchall()
        return [r["title"] or "" for r in rows]

    def save_field_recap(self, policy_field: str, summary: str, n_decisions: int,
                         period_from: str, period_to: str, generated_at: str) -> None:
        """Upsert the recap for one policy field (replaces the previous one)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO council_field_recaps "
                "(policy_field, summary, n_decisions, period_from, period_to, generated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (policy_field, summary, n_decisions, period_from, period_to, generated_at),
            )

    def get_field_recaps(self) -> list[dict]:
        """All field recaps, busiest field first."""
        rows = self._conn.execute(
            "SELECT policy_field, summary, n_decisions, period_from, period_to, generated_at "
            "FROM council_field_recaps ORDER BY n_decisions DESC, policy_field"
        ).fetchall()
        return [dict(r) for r in rows]

    def field_recaps_by_key(self) -> dict[str, dict]:
        """{policy_field: recap-row} — for the cron's freshness check."""
        return {r["policy_field"]: r for r in self.get_field_recaps()}
