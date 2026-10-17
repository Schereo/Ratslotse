"""Rückmeldungen zur KI-Frage: Daumen, Gründe, freigegebene Antworten.

Dreizehnter Schnitt an ``store.py`` (10/2026). Anlass war eine neue Abfrage —
die Liste der Daumen runter fürs Admin-Panel — und die Sperrklinke in
``tests/test_store_groesse.py``: Der Kern soll nicht wachsen, und
``save_qa_feedback`` gehört ohnehin nicht zu Beschlüssen und Vorlagen.

Das Schema (``council_qa_feedback``) bleibt beim übrigen Schema in
``store_schema.py``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from council.store_basis import StoreBasis


class RueckmeldungenMixin(StoreBasis):
    """Rückmeldungen zu KI-Antworten — nur zum Mitvererben."""

    #: Die festen Gründe zum Daumen runter.
    QA_FEEDBACK_REASONS = ("wrong", "incomplete", "outdated", "off_topic")

    def save_qa_feedback(self, question: str, answer_excerpt: str | None,
                         rating: str, reason: str | None,
                         user_id: int | None = None, source: str = "ask",
                         reason_kind: str | None = None,
                         shared_answer: str | None = None) -> None:
        """Daumen hoch/runter zu einer KI-Antwort (5a/I-03).

        Ein Konto hat je **Antwort** eine Stimme: Der nachgereichte Grund und
        die korrigierte Bewertung (Daumen runter → hoch) überschreiben die
        frühere Zeile, statt sich als widersprüchliches Paar in der Tabelle zu
        stapeln — sonst zählte jede Meinungsänderung doppelt. Anonyme
        Rückmeldungen haben keinen Schlüssel und werden weiterhin angehängt.

        **Der Schlüssel ist die Antwort, nicht die Frage** — seit Lottis
        Fenster (09/2026) einen Daumen hat. Dort heißt die häufigste Frage auf
        jeder Seite gleich: „Was sehe ich hier?" steht als Vorschlags-Chip
        unter jeder Erklärung. Mit dem alten Schlüssel (Konto + Frage) hätte
        ein Konto über alle Seiten hinweg **eine einzige** Lotti-Stimme
        abgeben können, und jede weitere hätte die vorige überschrieben — die
        Quote wäre dauerhaft zu klein gewesen, ohne dass es auffällt. Der
        Antwort-Auszug unterscheidet die Seiten; ``source`` gehört mit in den
        Schlüssel, weil dieselbe Frage im Archiv etwas anderes beantwortet als
        im Fenster.
        """
        if rating not in ("up", "down"):
            raise ValueError(f"rating muss up/down sein, nicht {rating!r}")
        now = datetime.utcnow().isoformat(timespec="seconds")
        quelle = source if source in ("ask", "lotti") else "ask"
        werte = (question[:300], (answer_excerpt or "")[:500] or None, rating,
                 (reason or "").strip()[:500] or None, user_id, now)
        # Grund und freigegebene Antwort gehören zum Daumen RUNTER: Wer auf
        # „hilfreich“ umschwenkt, nimmt beides zurück — auch die Freigabe.
        art = reason_kind if rating == "down" and reason_kind in self.QA_FEEDBACK_REASONS else None
        kopie = shared_answer if rating == "down" else None
        with self._conn:
            if user_id is not None:
                # `IS` statt `=`: Eine Antwort ohne Auszug ist NULL, und NULL
                # ist mit `=` zu nichts gleich — auch nicht zu sich selbst.
                vorher = self._conn.execute(
                    "SELECT id FROM council_qa_feedback WHERE user_id = ? AND question = ? "
                    "AND answer_excerpt IS ? AND COALESCE(source, 'ask') = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (user_id, werte[0], werte[1], quelle)).fetchone()
                if vorher:
                    self._conn.execute(
                        "UPDATE council_qa_feedback SET rating = ?, "
                        "reason = ?, created = ?, reason_kind = ?, shared_answer = ? "
                        "WHERE id = ?",
                        (rating, werte[3], now, art, kopie, vorher[0]))
                    return
            self._conn.execute(
                "INSERT INTO council_qa_feedback "
                "(question, answer_excerpt, rating, reason, user_id, created, source, "
                "reason_kind, shared_answer) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*werte, quelle, art, kopie),
            )

    def daumen_runter(self, tage: int = 90) -> list[dict]:
        """Die Daumen runter aus „Frag den Rat“ der letzten ``tage`` Tage,
        jüngste zuerst — fürs Admin-Panel.

        **Ohne Konto.** Wie die Liste der Fragen ohne Antwort: Für „woran ist
        es gescheitert?“ ist die Person ohne Belang, und eine Kennung neben
        der Frage wäre ein Leseprotokoll. Die vollständige Antwort steht nur
        dabei, wo jemand sie beim Absenden ausdrücklich freigegeben hat.
        """
        seit = (datetime.now(UTC) - timedelta(days=tage)).isoformat(timespec="seconds")
        zeilen = self._conn.execute(
            "SELECT created, question, answer_excerpt, reason, reason_kind, shared_answer "
            "FROM council_qa_feedback WHERE rating = 'down' "
            "AND COALESCE(source, 'ask') = 'ask' AND created >= ? "
            "ORDER BY created DESC LIMIT 200", (seit[:19],)).fetchall()
        aus: list[dict] = []
        for z in zeilen:
            freigabe = None
            if z["shared_answer"]:
                try:
                    roh = json.loads(z["shared_answer"])
                    freigabe = {"answer": str(roh.get("answer") or ""),
                                "sources": [
                                    {k: q.get(k) for k in ("id", "title", "session_date",
                                                           "committee", "outcome")}
                                    for q in (roh.get("sources") or []) if isinstance(q, dict)]}
                except (ValueError, TypeError, AttributeError):
                    freigabe = None
            aus.append({"created": z["created"], "question": z["question"],
                        "answer_excerpt": z["answer_excerpt"], "reason": z["reason"],
                        "reason_kind": z["reason_kind"], "shared": freigabe})
        return aus
