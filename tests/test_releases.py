"""„Neu bei Ratslotse": die Form der Einträge und der Weg der Ankündigung.

Drei Sorten Prüfung stehen hier:

1. **Der Bestand ist wohlgeformt.** Ein Eintrag mit fünf Highlights oder einem
   externen Link fiele sonst erst auf, wenn die Karte auf Prod steht.
2. **Nur die großen Sachen** (Tims Regel 07.09.2026). Die Registry hat dafür
   zwei harte Schranken — Patch-Versionen dürfen gar keinen Eintrag haben, und
   mehr als vier Highlights gibt es nicht. Ein Wächter ist hier besser als eine
   Bitte im Review: Die Versuchung, „das noch schnell mitzunehmen", kommt
   genau in dem Moment, in dem niemand mehr hinsieht.
3. **Wer bekommt was.** Die Hochwassermarke, die zwei verpassten Releases und
   der Versand, der zweimal gedrückt nichts doppelt schickt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern import news, notify, releases  # noqa: E402
from kern.store import Store  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "ratslotse.sqlite"))
    yield s
    s.close()


def _konto(store: Store, email: str = "a@example.org", created: str = "2020-01-01T00:00:00") -> int:
    uid = store.create_web_user(email, "hash", status="active", email_verified=True)
    with store._conn:
        store._conn.execute("UPDATE web_users SET created_at = ? WHERE id = ?", (created, uid))
    return uid


# --------------------------------------------------------------------------
# (1) + (2) Form und Auswahl
# --------------------------------------------------------------------------

def test_der_bestand_ist_wohlgeformt():
    for release in releases.RELEASES:
        assert releases.VERSION.match(release.version), release.version
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", release.date), release.version
        assert release.title.strip()
        for h in release.highlights:
            assert h.title.strip() and h.text.strip()
            assert len(h.title) <= 60, f"{release.version}: Titel zu lang für die Karte"


def test_nur_grosse_releases_bekommen_eine_karte():
    """Ein Eintrag für x.y.Z ist ein Fix — der gehört in den Changelog."""
    schlecht = [r.version for r in releases.RELEASES
                if not releases.is_feature_release(r.version)]
    assert not schlecht, (
        "Diese Einträge sind Patch-Releases und dürfen keine Karte haben: "
        f"{schlecht}. Nur x.y.0 kündigt etwas an — alles andere steht im "
        "Changelog.")


def test_hoechstens_vier_highlights():
    zu_viel = [(r.version, len(r.highlights)) for r in releases.RELEASES
               if not 1 <= len(r.highlights) <= releases.MAX_HIGHLIGHTS]
    assert not zu_viel, (
        f"Ein Eintrag hat 1 bis {releases.MAX_HIGHLIGHTS} Highlights: {zu_viel}. "
        "Mehr liest niemand auf einer Karte — streiche das schwächste.")


def test_jedes_highlight_zeigt_in_die_app():
    """Dieselbe Regel wie bei den Benachrichtigungen (``notify.ist_app_pfad``):
    Eine externe Adresse lässt den Tipp in der nativen App wortlos ins Leere
    laufen. Nebeneffekt: Was man sich nirgends ansehen kann, ist keine Karte
    wert — das hält Optimierungen von selbst draußen."""
    for release in releases.RELEASES:
        for h in release.highlights:
            assert notify.ist_app_pfad(h.url), f"{release.version}: {h.url!r}"


def test_jede_version_steht_auch_im_changelog():
    """Die Karte ist die Kurzfassung eines Abschnitts, nicht seine Konkurrenz.
    Fehlt der Abschnitt, ist entweder die Version falsch getippt oder der
    Versionsschnitt vergessen worden."""
    changelog = (WURZEL / "CHANGELOG.md").read_text(encoding="utf-8")
    for release in releases.RELEASES:
        assert f"## [{release.version}]" in changelog, (
            f"{release.version} hat eine Karte, aber keinen Changelog-Abschnitt.")


def test_die_liste_steht_neueste_zuerst():
    keys = [releases.version_key(r.version) for r in releases.RELEASES]
    assert keys == sorted(keys, reverse=True)
    assert len({r.version for r in releases.RELEASES}) == len(releases.RELEASES), \
        "Eine Version steht zweimal in der Registry."


def test_versionen_werden_als_zahlen_verglichen():
    """Als Zeichenkette stünde „2.10.0" vor „2.9.0" — genau der Vergleich, den
    die Hochwassermarke braucht."""
    assert releases.version_key("2.10.0") > releases.version_key("2.9.0")
    assert releases.is_feature_release("3.0.0") and not releases.is_feature_release("3.0.1")
    with pytest.raises(ValueError):
        releases.version_key("2.3")


# --------------------------------------------------------------------------
# (3) Wer sieht was
# --------------------------------------------------------------------------

def test_zwei_verpasste_releases_kommen_beide(monkeypatch):
    monkeypatch.setattr(releases, "RELEASES", (
        releases.Release("2.4.0", "2026-11-01", "Vier", (
            releases.Highlight("A", "…", "/dashboard"),)),
        releases.Release("2.3.0", "2026-10-01", "Drei", (
            releases.Highlight("B", "…", "/dashboard"),)),
    ))
    offen, weitere = releases.pending_for("2.2.0", "2026-01-01T00:00:00")
    assert [r.version for r in offen] == ["2.4.0", "2.3.0"]
    assert weitere == 0


def test_wer_wegklickt_sieht_nichts_mehr(monkeypatch):
    monkeypatch.setattr(releases, "RELEASES", (
        releases.Release("2.3.0", "2026-10-01", "Drei", (
            releases.Highlight("B", "…", "/dashboard"),)),
    ))
    assert releases.pending_for("2.3.0", "2026-01-01")[0] == []
    # Auch eine höhere Marke deckt ab — die Marke ist ein Hochwasserstand.
    assert releases.pending_for("2.9.0", "2026-01-01")[0] == []


def test_ein_neues_konto_bekommt_keine_karte(monkeypatch):
    """Wer nach dem Release dazugekommen ist, hatte das Feature von Anfang an."""
    monkeypatch.setattr(releases, "RELEASES", (
        releases.Release("2.3.0", "2026-10-01", "Drei", (
            releases.Highlight("B", "…", "/dashboard"),)),
    ))
    assert releases.pending_for(None, "2026-12-01T10:00:00")[0] == []
    assert [r.version for r in releases.pending_for(None, "2026-09-01T10:00:00")[0]] == ["2.3.0"]


def test_die_karte_waechst_nicht_mit_der_abwesenheit(monkeypatch):
    monkeypatch.setattr(releases, "RELEASES", tuple(
        releases.Release(f"2.{n}.0", f"2026-{n:02d}-01", "x", (
            releases.Highlight("A", "…", "/dashboard"),))
        for n in range(9, 4, -1)
    ))
    offen, weitere = releases.pending_for(None, "2020-01-01")
    assert len(offen) == releases.CARD_LIMIT
    assert weitere == 5 - releases.CARD_LIMIT


def test_die_marke_sinkt_nie(store):
    uid = _konto(store)
    assert store.set_news_seen(uid, "2.3.0") == "2.3.0"
    # Ein Nachzügler-Klick aus einem alten Tab darf nicht zurückdrehen.
    assert store.set_news_seen(uid, "2.2.0") == "2.3.0"
    assert store.set_news_seen(uid, "2.10.0") == "2.10.0"
    # Müll lässt sie unberührt, statt zu werfen: Es ist eine Wisch-Geste.
    assert store.set_news_seen(uid, "quatsch") == "2.10.0"


# --------------------------------------------------------------------------
# (3b) Der Versand
# --------------------------------------------------------------------------

RELEASE = releases.Release(
    "2.3.0", "2026-10-01", "Drei neue Sachen",
    (releases.Highlight("Sitzungen teilen", "Geht jetzt.", "/council?tab=sessions"),
     releases.Highlight("Kalender-Abo", "Auch das.", "/abos")),
)


def test_die_ankuendigung_geht_durch_die_warteschlange(store):
    """Nicht an ``send_email`` vorbei: Nur so greifen Aus-Schalter, Nachtruhe
    und Tagesgrenze (kern/CLAUDE.md)."""
    uid = _konto(store)
    bilanz = news.announce(store, RELEASE)
    assert bilanz == {"recipients": 1, "queued": 1, "skipped": 0}
    offen = store.due_notifications(uid, "2999-01-01")
    assert [p["kind"] for p in offen] == [notify.N7_NEWS]
    assert offen[0]["url"] == "/dashboard"
    assert "Sitzungen teilen" in offen[0]["body_html"]
    assert offen[0]["push_text"] == "Sitzungen teilen · Kalender-Abo"


def test_zweimal_druecken_schickt_nichts_doppelt(store):
    _konto(store)
    assert news.announce(store, RELEASE)["queued"] == 1
    assert news.announce(store, RELEASE) == {"recipients": 0, "queued": 0, "skipped": 0}


def test_wer_die_karte_schon_sah_bekommt_keine_mail(store):
    """Die Mail ist für die, die nicht von selbst vorbeikommen."""
    uid = _konto(store)
    store.set_news_seen(uid, RELEASE.version)
    assert news.recipients(store, RELEASE) == []


def test_ein_abgeschalteter_anlass_gilt_als_erledigt(store):
    """``einreihen`` reiht nichts ein — der Versand muss das Konto trotzdem
    abhaken, sonst fragt ihn jeder weitere Lauf erneut."""
    uid = _konto(store)
    store.set_notify_prefs(uid, {notify.N7_NEWS: False})
    bilanz = news.announce(store, RELEASE)
    assert bilanz == {"recipients": 1, "queued": 0, "skipped": 1}
    assert store.due_notifications(uid, "2999-01-01") == []
    assert news.recipients(store, RELEASE) == []


def test_wer_nichts_hoeren_will_bekommt_auch_das_nicht(store):
    uid = _konto(store)
    store.set_delivery_channel(uid, notify.KANAL_AUS)
    assert news.announce(store, RELEASE)["queued"] == 0
    assert store.due_notifications(uid, "2999-01-01") == []


def test_ein_konto_juenger_als_das_release_wird_nicht_angeschrieben(store):
    _konto(store, "neu@example.org", created="2026-12-01T00:00:00")
    assert news.recipients(store, RELEASE) == []


def test_nur_bestaetigte_aktive_konten(store):
    store.create_web_user("pending@example.org", "h", status="pending", email_verified=True)
    store.create_web_user("unbestaetigt@example.org", "h", status="active", email_verified=False)
    assert news.recipients(store, RELEASE) == []


def test_der_probe_versand_veraendert_keine_marke(store):
    """Die Probe an das eigene Konto ist kein Versand — sie darf niemanden
    aus der Empfängerliste nehmen."""
    _konto(store)
    news.body_html(RELEASE)  # baut nur den Text
    assert len(news.recipients(store, RELEASE)) == 1
