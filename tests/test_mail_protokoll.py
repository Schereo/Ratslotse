"""Wächter: das Mail-Protokoll und die Markierung der Mail-Links.

**Warum es das Protokoll gibt.** Bis 09/2026 war „welche Mails hat diese
Person bekommen?" nur im Resend-Dashboard zu beantworten — also außerhalb des
eigenen Systems. ``notification_queue`` kannte nur die Ratsmeldungen, und auch
die nur als *eingereiht*; Bestätigungslink, Passwort-Reset und
Setup-Erinnerung hinterließen gar nichts.

**Was hier festgehalten wird**, in der Reihenfolge, in der es kaputtgehen
kann:

1. Die Positivliste ``MAIL_ANLAESSE`` kennt **jede** Meldungssorte aus
   ``kern/notify.py``. Ein neuer Anlass dort ohne Eintrag hier landete sonst
   still als ``andere`` — die Statistik sähe vollständig aus und wäre es
   nicht.
2. Ein unbekannter Anlass wird zu ``andere``, statt eine eigene Zeile
   anzulegen: Der Wert kommt über ``?von=`` aus einem **fremden Browser**
   zurück (dieselbe Begründung wie bei ``kern/seitenaufrufe.py``).
3. Die Link-Markierung fasst nur eigene Adressen an und markiert nie doppelt.
4. Das Protokoll lässt einen Versand nie scheitern.
"""
from __future__ import annotations

import sqlite3

import pytest

from kern import notify
from kern.mail_links import PARAM, markiere, markiere_link
from kern.store import MAIL_ANLAESSE, MAIL_ANLASS_ANDERE, USER_OWNED_TABLES, mail_anlass

BASIS = "https://ratslotse.de"


def test_jede_meldungssorte_steht_in_der_positivliste():
    """Jedes ``notify.N…`` muss ein Anlass sein — sonst zählt es als ``andere``."""
    sorten = {wert for name, wert in vars(notify).items()
              if name.startswith("N") and name[1:2].isdigit() and isinstance(wert, str)}
    assert sorten, "keine Meldungssorten gefunden — hat sich die Namensgebung geändert?"
    fehlt = sorten - MAIL_ANLAESSE
    assert not fehlt, (
        f"Diese Meldungssorten fehlen in kern.store.MAIL_ANLAESSE: {sorted(fehlt)}. "
        "Ohne Eintrag landen ihre Mails still als „andere“ im Protokoll.")


def test_unbekannter_anlass_wird_gesammelt():
    assert mail_anlass("n2_thema") == "n2_thema"
    assert mail_anlass("N2_THEMA") == "n2_thema"
    assert mail_anlass("<script>") == MAIL_ANLASS_ANDERE
    assert mail_anlass(None) == MAIL_ANLASS_ANDERE
    assert mail_anlass("") == MAIL_ANLASS_ANDERE


def test_email_log_haengt_am_konto():
    """Eine nutzerbezogene Tabelle gehört in die Löschliste (DSGVO Art. 17)."""
    assert ("email_log", "owner_id") in USER_OWNED_TABLES


@pytest.mark.parametrize("url,erwartet", [
    (f"{BASIS}/dashboard", f"{BASIS}/dashboard?{PARAM}=n2_thema"),
    (f"{BASIS}/council?tab=sessions", f"{BASIS}/council?tab=sessions&{PARAM}=n2_thema"),
    # Fremde Adressen bleiben unangetastet — eine fremde Seite erfährt nicht
    # einmal, dass jemand aus einer Mail kam.
    ("https://ratsinfo.oldenburg.de/vorlage/123", "https://ratsinfo.oldenburg.de/vorlage/123"),
    ("mailto:moin@example.org", "mailto:moin@example.org"),
    ("#abschnitt", "#abschnitt"),
    # Schon markiert: kein zweites Mal.
    (f"{BASIS}/x?{PARAM}=n1_tagesordnung", f"{BASIS}/x?{PARAM}=n1_tagesordnung"),
])
def test_nur_eigene_links_werden_markiert(url, erwartet):
    assert markiere_link(url, "n2_thema", BASIS) == erwartet


def test_fragment_bleibt_hinten():
    """Der Parameter gehört vor die Sprungmarke, sonst ist er Teil von ihr."""
    assert markiere_link(f"{BASIS}/hilfe#faq", "n6_woche", BASIS) == \
        f"{BASIS}/hilfe?{PARAM}=n6_woche#faq"


def test_markiere_ohne_anlass_aendert_nichts():
    html = f'<a href="{BASIS}/dashboard">Los</a>'
    assert markiere(html, None, BASIS) == html
    assert markiere(html, "", BASIS) == html


def test_markiere_beide_anfuehrungszeichen():
    html = f"""<a href='{BASIS}/a'>A</a><a href="{BASIS}/b">B</a>"""
    raus = markiere(html, "n3_result", BASIS)
    assert f"{BASIS}/a?{PARAM}=n3_result" in raus
    assert f"{BASIS}/b?{PARAM}=n3_result" in raus


def test_mail_haelt_ihre_huelle_zusammen():
    """Die Markierung läuft über das FERTIGE HTML — auch die Fußzeile trägt sie."""
    from kern.digest_email import render_html_email
    html = render_html_email("Test", "<p>Moin</p>", anlass="n1_tagesordnung")
    assert f"{PARAM}=n1_tagesordnung" in html
    # Der Fuß-Link „Zu Ratslotse" ist der, den es vorher nur ohne Markierung gab.
    assert html.count(f"{PARAM}=n1_tagesordnung") >= 2


def test_protokoll_laesst_versand_nie_scheitern(tmp_path):
    """Ein kaputtes Protokoll darf keine Mail mitreißen — die ist längst raus."""
    from kern.store import Store
    store = Store(str(tmp_path / "t.sqlite"))
    uid = store.create_web_user("moin@example.org", "hash")
    store._conn.execute("DROP TABLE email_log")
    store.protokolliere_mail(uid, "n2_thema", "Betreff")  # wirft nicht
    store._conn.execute(
        "CREATE TABLE email_log (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, "
        "anlass TEXT NOT NULL, subject TEXT NOT NULL, sent_at TEXT NOT NULL, "
        "ok INTEGER NOT NULL DEFAULT 1, message_id TEXT)")


def test_zusammenfassung_zaehlt_nur_gelungene(tmp_path):
    from kern.store import Store
    store = Store(str(tmp_path / "t.sqlite"))
    uid = store.create_web_user("moin@example.org", "hash")
    store.protokolliere_mail(uid, "n2_thema", "A")
    store.protokolliere_mail(uid, "n2_thema", "B")
    store.protokolliere_mail(uid, "n1_tagesordnung", "C", ok=False)
    zus = store.mail_zusammenfassung(uid, tage=30)
    assert zus["gesamt"] == 2
    assert zus["je_anlass"] == {"n2_thema": 2}
    assert zus["gescheitert"] == 1
    # Der gescheiterte Versand steht trotzdem in der Liste: Er ist die Zeile,
    # die erklärt, warum jemand nichts bekommen hat.
    assert [r["ok"] for r in store.mails_fuer_konto(uid)].count(False) == 1


def test_rueckkehr_zaehlt_ohne_konto(tmp_path):
    from kern.store import Store
    store = Store(str(tmp_path / "t.sqlite"))
    store.merke_mail_rueckkehr("n2_thema", angemeldet=True)
    store.merke_mail_rueckkehr("n2_thema", angemeldet=True)
    store.merke_mail_rueckkehr("erfunden", angemeldet=False)
    statistik = store.mail_statistik(tage=30)
    assert statistik["rueckkehr"] == 3
    gezaehlt = {r["anlass"]: r["rueckkehr"] for r in statistik["rueckkehr_je_anlass"]}
    assert gezaehlt["n2_thema"] == 2
    # Ein erfundener Anlass aus einem fremden Browser legt keine eigene Zeile an.
    assert gezaehlt[MAIL_ANLASS_ANDERE] == 1
    spalten = {r[1] for r in store._conn.execute("PRAGMA table_info(mail_returns)")}
    assert "owner_id" not in spalten, "Die Rückkehr wird bewusst OHNE Konto gezählt."


def test_mailhistorie_blaettert_stabil_auch_bei_gleichem_zeitpunkt(tmp_path):
    """Ältere Mails bleiben erreichbar, ohne andere Konten oder Doppelungen."""
    from kern.store import Store
    store = Store(str(tmp_path / "t.sqlite"))
    uid = store.create_web_user("moin@example.org", "hash")
    andere = store.create_web_user("anders@example.org", "hash")
    for i in range(45):
        store.protokolliere_mail(uid, "n2_thema", f"Mail {i}",
                                 ok=i % 3 != 0, jetzt="2026-09-17T12:00:00+00:00")
        store.protokolliere_mail(andere, "n2_thema", "Fremdes Konto")
    seiten = [store.mails_fuer_konto(uid, limit=20, offset=n) for n in (0, 20, 40, 60)]
    assert [len(s) for s in seiten] == [20, 20, 5, 0]
    assert [r["subject"] for s in seiten for r in s] == [f"Mail {i}" for i in reversed(range(45))]
    assert sum(not r["ok"] for s in seiten for r in s) == 15


def test_loeschen_nimmt_das_protokoll_mit(tmp_path):
    """Nach dem Löschen eines Kontos darf keine Mailzeile übrig bleiben."""
    from kern.store import Store
    store = Store(str(tmp_path / "t.sqlite"))
    uid = store.create_web_user("moin@example.org", "hash")
    store.protokolliere_mail(uid, "n2_thema", "A")
    store.delete_web_user(uid)
    with sqlite3.connect(str(tmp_path / "t.sqlite")) as conn:
        rest = conn.execute("SELECT COUNT(*) FROM email_log WHERE owner_id = ?", (uid,)).fetchone()[0]
    assert rest == 0
