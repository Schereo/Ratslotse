"""Der Kohorten-Trichter (Plan „Sehen und Zurückholen", Teil A / PR 1).

Die Fallen, gegen die diese Tests gebaut sind, stammen aus der Auswertung vom
08.09.2026 — beide hatten dort zu einer falschen Lesart geführt:

* Eine Kohorte, die noch keine 30 Tage alt ist, KANN „noch da nach 30 Tagen"
  nicht erreicht haben. Zählte man sie als Misserfolg, sähe jede frische Woche
  wie ein Totalausfall aus.
* Betreiber- und Testkonten sind hier keine Randgröße: An jenem Tag stammten
  15.209 von 23.888 Zugriffen aus einem einzigen Konto.
"""
from __future__ import annotations

from datetime import date, timedelta

from kern.store import Store


def _konto(store: Store, uid: int, *, tage_her: int, email: str = "a@example.org",
           verified: int = 1, setup_started: str | None = None,
           setup_done: str | None = None, role: str = "user") -> date:
    reg = date.today() - timedelta(days=tage_her)
    with store._conn:
        store._conn.execute(
            "INSERT INTO web_users (id, email, password_hash, role, status, created_at,"
            " email_verified, setup_started_at, setup_done_at)"
            " VALUES (?, ?, 'x', ?, 'active', ?, ?, ?, ?)",
            (uid, email, role, reg.isoformat() + "T09:00:00", verified,
             setup_started, setup_done))
    return reg


def _aktiv(store: Store, uid: int, tag: date, feature: str = "session") -> None:
    with store._conn:
        store._conn.execute(
            "INSERT INTO user_activity (owner_id, day, feature, client, count)"
            " VALUES (?, ?, ?, 'web', 1)", (uid, tag.isoformat(), feature))


def _stufe(daten: dict, key: str) -> dict:
    return next(s for s in daten["total"] if s["key"] == key)


def test_junge_kohorte_zaehlt_nicht_als_misserfolg(tmp_path):
    """Ein Konto von gestern ist bei „Tag 30" weder Erfolg noch Misserfolg."""
    store = Store(tmp_path / "r.sqlite")
    _konto(store, 1, tage_her=1)

    daten = store.admin_kohorten()

    assert _stufe(daten, "registriert")["n"] == 1
    tag30 = _stufe(daten, "tag30")
    assert tag30["eligible"] == 0, "Ein Konto von gestern kann Tag 30 nicht erreicht haben"
    assert tag30["n"] == 0
    assert daten["kennzahlen"]["tag30"] is None, (
        "Eine Quote aus null möglichen Konten ist keine 0 %, sondern keine Aussage"
    )
    store.close()


def test_zweiter_tag_zaehlt_nur_einen_WEITEREN_tag(tmp_path):
    """Wer sich anmeldet, ist am Anmeldetag aktiv — das ist keine Rückkehr."""
    store = Store(tmp_path / "r.sqlite")
    reg = _konto(store, 1, tage_her=10)
    _aktiv(store, 1, reg)                       # nur der Anmeldetag
    reg2 = _konto(store, 2, tage_her=10, email="b@example.org")
    _aktiv(store, 2, reg2)
    _aktiv(store, 2, reg2 + timedelta(days=1))  # kam wieder

    daten = store.admin_kohorten()

    tag2 = _stufe(daten, "tag2")
    assert tag2["eligible"] == 2
    assert tag2["n"] == 1, "Nur Konto 2 war an einem WEITEREN Tag da"
    assert daten["kennzahlen"]["tag2"] == 0.5
    store.close()


def test_haken_zaehlt_nur_binnen_24_stunden(tmp_path):
    """Der Haken ist die Frage, ob die Einrichtung beim ERSTEN Besuch greift."""
    store = Store(tmp_path / "r.sqlite")
    reg = _konto(store, 1, tage_her=20)
    reg2 = _konto(store, 2, tage_her=20, email="b@example.org")
    with store._conn:
        store._conn.execute(
            "INSERT INTO topics (owner_id, name, description, created_at) VALUES (1, 'T', '', ?)",
            (reg.isoformat() + "T10:00:00",))
        store._conn.execute(
            "INSERT INTO committee_subscriptions (owner_id, committee_name, created_at)"
            " VALUES (2, 'Rat', ?)", ((reg2 + timedelta(days=5)).isoformat() + "T10:00:00",))

    haken = _stufe(store.admin_kohorten(), "haken")

    assert haken["n"] == 1, "Konto 2 hat erst nach fünf Tagen etwas angelegt"
    store.close()


def test_betreiber_und_testkonten_fallen_heraus(tmp_path):
    """Sonst misst die Statistik überwiegend das eigene Klicken."""
    store = Store(tmp_path / "r.sqlite")
    _konto(store, 1, tage_her=3, email="echt@example.org")
    _konto(store, 2, tage_her=3, email="chef@example.org", role="admin")
    _konto(store, 3, tage_her=3, email="tester@example.net")

    daten = store.admin_kohorten(ausschluss_domains=["example.net"])

    assert _stufe(daten, "registriert")["n"] == 1
    assert daten["excluded"] == 2
    store.close()


def test_rolle_aus_der_rollentabelle_zaehlt_auch(tmp_path):
    """Geprüft wird gegen die Rollentabelle, nicht nur gegen `web_users.role`."""
    store = Store(tmp_path / "r.sqlite")
    _konto(store, 1, tage_her=3, email="echt@example.org")
    _konto(store, 2, tage_her=3, email="admin@example.org")
    with store._conn:
        store._conn.execute(
            "INSERT INTO web_user_roles (user_id, role, granted_at) VALUES (2, 'admin', ?)",
            (date.today().isoformat(),))

    assert _stufe(store.admin_kohorten(), "registriert")["n"] == 1
    store.close()


def test_ratsmitglieder_bleiben_drin(tmp_path):
    """Ausgeschlossen wird das RECHT `admin` — nicht „hat überhaupt eine Rolle".

    Die erste Fassung warf jedes Konto mit einer Rollenzeile hinaus und traf
    damit die Ratsmitglieder mit, also die aufmerksamsten echten Nutzer*innen.
    """
    store = Store(tmp_path / "r.sqlite")
    _konto(store, 1, tage_her=3, email="buerger@example.org")
    _konto(store, 2, tage_her=3, email="rat@example.org", role="council_member")
    _konto(store, 3, tage_her=3, email="chef@example.org", role="admin")
    with store._conn:
        store._conn.execute(
            "INSERT INTO web_user_roles (user_id, role, granted_at) VALUES (2, 'council_member', ?)",
            (date.today().isoformat(),))

    daten = store.admin_kohorten()

    assert _stufe(daten, "registriert")["n"] == 2, "Nur das Admin-Konto fällt heraus"
    assert daten["excluded"] == 1
    store.close()


def test_kohorten_liegen_auf_wochen(tmp_path):
    """Je Registrierungswoche eine Zeile, Montag als Schlüssel."""
    store = Store(tmp_path / "r.sqlite")
    _konto(store, 1, tage_her=2, email="a@example.org")
    _konto(store, 2, tage_her=9, email="b@example.org")

    daten = store.admin_kohorten(wochen=4)

    assert len(daten["cohorts"]) == 2
    for k in daten["cohorts"]:
        assert date.fromisoformat(k["week"]).weekday() == 0, "Wochenschlüssel ist der Montag"
    assert sum(k["n"] for k in daten["cohorts"]) == 2


def test_sackgassen_quote_zaehlt_antworten_ohne_quelle(tmp_path):
    """Der Anteil der Antworten, die nichts belegen konnten."""
    store = Store(tmp_path / "r.sqlite")
    heute = date.today().isoformat()
    with store._conn:
        store._conn.execute("INSERT INTO qa_conversations (id, user_id, title, created, updated)"
                            " VALUES (1, 1, 't', ?, ?)", (heute, heute))
        for i, quellen in enumerate(['{"cited": [1, 2]}', '{"cited": []}', "null"]):
            store._conn.execute(
                "INSERT INTO qa_conversation_turns (conversation_id, user_id, question, answer,"
                " sources, created) VALUES (1, 1, 'f', 'a', ?, ?)", (quellen, heute))

    assert store.sackgassen_quote() == round(2 / 3, 3)
    store.close()


def test_fragen_median_ignoriert_den_ausreisser(tmp_path):
    """Ein Konto mit 108 Fragen darf die Zahl nicht allein bestimmen."""
    store = Store(tmp_path / "r.sqlite")
    heute = date.today()
    for uid, fragen in ((1, 108), (2, 1), (3, 0)):
        _aktiv(store, uid, heute)
        if fragen:
            with store._conn:
                store._conn.execute(
                    "INSERT INTO user_activity (owner_id, day, feature, client, count)"
                    " VALUES (?, ?, 'ai_question', 'web', ?)", (uid, heute.isoformat(), fragen))

    assert store.fragen_median_je_konto() == 1.0
    store.close()


def test_vorzeitraum_und_basis_liegen_bei(tmp_path):
    """Die Oberfläche zeigt Veränderung und „n von m" — beides kommt vom Server.

    Ein Stand allein („43 %") sagt weder, ob das 3 von 7 sind, noch ob es im
    Zeitraum davor 60 % waren (Tims Rückmeldung 09.09.2026).
    """
    store = Store(tmp_path / "r.sqlite")
    # Eine Anmeldung in der Spanne davor (vor mehr als acht Wochen), zwei jetzt.
    _konto(store, 1, tage_her=70, email="alt@example.org")
    _konto(store, 2, tage_her=3, email="neu@example.org")
    _konto(store, 3, tage_her=4, email="neuer@example.org")

    daten = store.admin_kohorten(wochen=8)

    assert set(daten["previous"]) == set(daten["kennzahlen"])
    assert daten["basis"]["vorher_n"] == 1
    assert daten["basis"]["haken"] == (0, 2)
    store.close()


def test_sackgassen_basis_mit_versatz_trennt_die_zeitraeume(tmp_path):
    from datetime import date, timedelta
    store = Store(tmp_path / "r.sqlite")
    heute = date.today()
    with store._conn:
        store._conn.execute("INSERT INTO qa_conversations (id, user_id, title, created, updated)"
                            " VALUES (1, 1, 't', ?, ?)", (heute.isoformat(), heute.isoformat()))
        for tage, quellen in ((2, '{"cited": []}'), (2, '{"cited": [1]}'), (100, '{"cited": []}')):
            store._conn.execute(
                "INSERT INTO qa_conversation_turns (conversation_id, user_id, question, answer,"
                " sources, created) VALUES (1, 1, 'f', 'a', ?, ?)",
                (quellen, (heute - timedelta(days=tage)).isoformat() + "T10:00:00"))

    assert store.sackgassen_basis(90) == (1, 2)
    assert store.sackgassen_basis(90, versatz=90) == (1, 1)
    store.close()
