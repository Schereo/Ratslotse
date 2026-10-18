"""Frische Sitzungen in „Frag den Rat" — Auswertung der echten Fragen vom 11.10.2026.

* „Was ist gestern beim allgemeinen Ausschuss rausgekommen?" (29.09.) fand die
  Sitzung vom 28.09. nicht: Der amtliche Name „Ausschuss für Allgemeine
  Angelegenheiten" stand nicht in der Frage, und „rausgekommen" zählte nicht
  als Sitzungswort — damit fiel auch das aufgelöste „gestern" weg.
* Brokhausen (24.09.): „im Mai vertagt", obwohl der Punkt danach zweimal
  wieder auf der Tagesordnung stand.
* „Wo finde ich Ergebnisse der Ausschusssitzung?" bekam einen Beschluss von 2022.
"""
import datetime
from unittest import mock

from council import qa
from council.store import CouncilStore


def _store(tmp_path) -> CouncilStore:
    st = CouncilStore(tmp_path / "c.sqlite")
    c = st._conn  # noqa: SLF001
    with c:
        for ksinr, gremium, tag in [
                (1, "Ausschuss für Stadtplanung und Bauen", "2026-05-21"),
                (2, "Ausschuss für Stadtplanung und Bauen", "2026-06-18"),
                (3, "Ausschuss für Stadtplanung und Bauen", "2026-08-27"),
                (4, "Ausschuss für Allgemeine Angelegenheiten", "2026-09-28"),
                (5, "Rat", "2026-11-30")]:
            c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
                      "location, fetched_at) VALUES (?,?,?,?,?,?)",
                      (ksinr, gremium, tag, "17:00", "Alte Fleiwa", "2026-10-01"))
        c.execute("INSERT INTO council_decisions (ksinr, position, item_number, title, outcome, "
                  "template_number, kind) VALUES (1, 1, 'Ö 11.3', "
                  "'Bebauungsplan 869 - Aufstellungsbeschluss', 'postponed', '26/0395', 'item')")
        for ksinr, nr, titel in [
                (1, "Ö 11.3", "Bebauungsplan 869 - Aufstellungsbeschluss Beschluss: vertagt"),
                (2, "Ö 8.3", "Bebauungsplan 869 - Aufstellungsbeschluss Beschluss: zurückgestellt/abgesetzt"),
                (3, "Ö 11.3", "Bebauungsplan 869 - Aufstellungsbeschluss"),
                (5, "Ö 4", "Bebauungsplan 869 - Aufstellungsbeschluss")]:
            c.execute("INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, "
                      "is_public) VALUES (?,?,?,?,?)", (ksinr, nr, titel, "26/0395", 1))
        c.execute("INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, "
                  "is_public) VALUES (4, 'Ö 5', 'Dienstreise nach Groningen - Beschluss', '26/0700', 1)")
    return st


def test_stationen_nach_dem_beschluss(tmp_path):
    st = _store(tmp_path)
    rows = st.agenda_since_decisions(["26/0395"], today="2026-09-24")
    assert [(r["session_date"], r["outcome"]) for r in rows] == [
        ("2026-06-18", "zurückgestellt/abgesetzt"), ("2026-08-27", None)]
    assert rows[0]["title"] == "Bebauungsplan 869 - Aufstellungsbeschluss"
    text = qa.seither_block(rows)
    assert "18.06.2026, Ausschuss für Stadtplanung und Bauen" in text
    assert "laut Tagesordnung: zurückgestellt/abgesetzt" in text
    assert "Protokoll mit dem Ergebnis liegt noch nicht vor" in text
    assert "NIE mit [id]" in text
    # Künftige Sitzungen sind kein „seither" — die zeigt „Wie es weitergeht".
    assert all(r["session_date"] <= "2026-09-24" for r in rows)
    st.close()


def test_ohne_beschluss_keine_station(tmp_path):
    st = _store(tmp_path)
    assert st.agenda_since_decisions(["26/0700"], today="2026-10-11") == []
    assert qa.seither_block([]) == ""
    st.close()


class _Heute(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 29)


def test_gestern_beim_allgemeinen_ausschuss(tmp_path):
    st = _store(tmp_path)
    with mock.patch("datetime.date", _Heute):
        r = qa.finde_sitzungen(st, "was ist gestern beim allgemeinen Ausschuss rausgekommen?")
    assert [(s["committee"], s["session_date"]) for s in r] == [
        ("Ausschuss für Allgemeine Angelegenheiten", "2026-09-28")]
    assert r[0]["agenda"] and not r[0]["decision_ids"]
    st.close()


def test_fundortfrage():
    assert qa.fundortfrage("wo finde ich Ergebnisse der Ausschusssitzung")
    assert qa.fundortfrage("Wann kommt das Protokoll?")
    assert not qa.fundortfrage("Wo soll das neue Stadion gebaut werden?")
    messages, _ = qa._answer_messages("wo finde ich Ergebnisse der Ausschusssitzung", [],
                                      typ="topic", extra_block=qa.FUNDORT_BLOCK)
    assert "buergerinfo.oldenburg.de" in messages[0]["content"]
