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
        # Ein Name, kein Halbsatz: „Das Teilen-Update“ — die Version ist
        # nach ihrem Hauptfeature benannt (Tims Wunsch 08.09.2026), und der
        # Name muss auf dem Telefon in eine Zeile passen.
        assert len(release.title) <= 40, f"{release.version}: Titel ist ein Halbsatz, kein Name"
        for h in release.highlights:
            assert h.title.strip() and h.text.strip()
            assert len(h.title) <= 60, f"{release.version}: Titel zu lang für die Karte"


def test_nur_grosse_releases_bekommen_eine_karte():
    """Seit 09/2026: nur ``x.0.0``. Vorher galt jedes ``x.y.0``.

    Die Minor-Fassung war eine Bitte und wurde fünf Releases lang übergangen
    (2.3.0 bis 2.7.0 gingen alle ohne Karte raus) — die Kuratierung ist
    Handarbeit, die Clips sind eine eigene Runde. Tims Entscheidung
    21.09.2026: lieber vier Karten im Jahr, die jemand gemacht hat, als eine
    Regel, die zwanzig Mal gebrochen wird.
    """
    schlecht = [r.version for r in releases.RELEASES
                if not releases.is_feature_release(r.version)]
    assert not schlecht, (
        f"Diese Einträge dürfen keine Karte haben: {schlecht}. Nur eine "
        "Major-Version (x.0.0) kündigt an — Minor und Patch stehen im "
        "Changelog. Bestand aus der Minor-Zeit: "
        f"{sorted(releases.KARTE_BESTAND)}.")


def test_der_kartenbestand_waechst_nicht():
    """``KARTE_BESTAND`` trägt die Einträge aus der Zeit, als jede Minor eine
    Karte bekam — er ist ein Denkmal, keine Hintertür. Wer eine neue Version
    hineinschreibt, hebt die Regel von oben still wieder auf, und zwar an der
    Stelle, an der niemand sie sucht."""
    assert releases.KARTE_BESTAND == frozenset({"2.2.0"}), (
        "Der Kartenbestand hat sich geändert. Er soll nur schrumpfen: "
        "Eine neue Minor mit Karte gehört nicht hier hinein, sondern ist "
        "eine Entscheidung gegen die Regel in `kern/releases.py`.")


def test_hoechstens_vier_highlights():
    zu_viel = [(r.version, len(r.highlights)) for r in releases.RELEASES
               if not 1 <= len(r.highlights) <= releases.MAX_HIGHLIGHTS + 2]
    assert not zu_viel, (
        f"Ein Eintrag hat 1 bis {releases.MAX_HIGHLIGHTS} Highlights: {zu_viel}. "
        "Mehr liest niemand auf einer Karte — streiche das schwächste. "
        "Der Deckel liegt hier etwas höher, weil `only` Highlights auf eine "
        "Oberfläche beschränken kann; die harte Grenze JE Oberfläche prüft "
        "test_jede_oberflaeche_bekommt_wenigstens_ein_highlight.")


def test_jedes_highlight_zeigt_in_die_app():
    """Dieselbe Regel wie bei den Benachrichtigungen (``notify.ist_app_pfad``):
    Eine externe Adresse lässt den Tipp in der nativen App wortlos ins Leere
    laufen. Nebeneffekt: Was man sich nirgends ansehen kann, ist keine Karte
    wert — das hält Optimierungen von selbst draußen."""
    for release in releases.RELEASES:
        for h in release.highlights:
            assert notify.ist_app_pfad(h.url), f"{release.version}: {h.url!r}"


def test_bilder_gibt_es_ganz_oder_gar_nicht():
    """Eine Bühne mit einem Loch darin ist schlechter als eine Liste.

    Deshalb die Entweder-oder-Regel: Hat EIN Highlight ein Bild, brauchen alle
    eins — sonst fällt die Karte auf die Listenform zurück
    (``components/release-news-card.tsx``)."""
    for release in releases.RELEASES:
        mit = [h.title for h in release.highlights if h.media]
        ohne = [h.title for h in release.highlights if not h.media]
        assert not (mit and ohne), (
            f"{release.version}: {len(mit)} Highlight(s) mit Bild, {len(ohne)} ohne. "
            f"Ohne Bild: {ohne}. Entweder alle bebildern oder keins.")


def test_jede_genannte_mediendatei_existiert():
    """Ein Tippfehler im Pfad wäre sonst ein leeres Feld auf der Karte — und
    zwar erst auf Prod, weil lokal niemand die Karte aufschlägt."""
    wurzel = WURZEL / releases.MEDIA_ROOT
    fehlend = []
    for release in releases.RELEASES:
        for h in release.highlights:
            for medium in (h.media, h.media_ios):
                if not medium:
                    continue
                for feld in ("src", "poster", "cover"):
                    pfad = getattr(medium, feld)
                    if pfad and not (wurzel / pfad.lstrip("/")).exists():
                        fehlend.append(f"{release.version} · {h.title} · {feld}: {pfad}")
    assert not fehlend, (
        "Diese Mediendateien fehlen unter "
        f"{releases.MEDIA_ROOT}:\n  " + "\n  ".join(fehlend))


# --------------------------------------------------------------------------
# (1b) Die Video-Kacheln (seit 3.0.0)
# --------------------------------------------------------------------------

#: Wo die Clients die Farbnamen in Farben übersetzen. Beide müssen jeden Namen
#: aus ``releases.TILE_COLORS`` kennen — ein Name ohne Gegenstück fiele dort
#: still auf die Vorgabe zurück und sähe aus wie „noch nicht eingetragen".
FARBEN_WEB = WURZEL / "web/frontend/lib/neuigkeiten.ts"
FARBEN_IOS = WURZEL / "ios/Packages/RatslotseFeatures/Sources/RatslotseFeatures/ReleaseNewsCard.swift"


def test_kachelfarben_sind_namen_aus_der_designsprache():
    """Die Registry nennt Farben beim Namen (``signal``, ``primary``,
    ``green``), nie als Hex-Wert: Die Werte stehen in der Designsprache und je
    einmal in Web und App."""
    falsch = [(r.version, h.title, h.color) for r in releases.RELEASES
              for h in r.highlights
              if h.color is not None and h.color not in releases.TILE_COLORS]
    assert not falsch, (
        f"Unbekannte Kachelfarbe: {falsch}. Erlaubt: {sorted(releases.TILE_COLORS)} — "
        "eine neue Farbe gehört zuerst in DESIGNSPRACHE.md und in beide Clients.")


def test_beide_clients_kennen_jede_kachelfarbe():
    """Web übersetzt in einem Objekt (``signal: "#ce4709"``), die App in einem
    ``switch`` über den Namen (``case "signal":``)."""
    web = FARBEN_WEB.read_text(encoding="utf-8")
    ios = FARBEN_IOS.read_text(encoding="utf-8")
    fehlt = sorted({f"web: {f}" for f in releases.TILE_COLORS
                    if not re.search(rf"\b{f}\s*:", web)}
                   | {f"ios: {f}" for f in releases.TILE_COLORS
                      if f'case "{f}"' not in ios})
    assert not fehlt, (
        f"Diese Kachelfarben übersetzt ein Client nicht: {fehlt}. Ohne Eintrag "
        "fällt die Kachel dort still auf Hafenblau zurück — nachtragen in "
        f"{FARBEN_WEB.relative_to(WURZEL)} bzw. {FARBEN_IOS.relative_to(WURZEL)}.")


def test_die_kachelfarben_stehen_in_der_designsprache():
    """„Kein neuer Hex-Wert ohne Eintrag dort": Die drei Werte, die Web und App
    benutzen, stehen im Abschnitt zu den Neuigkeiten-Kacheln."""
    designsprache = (WURZEL / "web/frontend/DESIGNSPRACHE.md").read_text(encoding="utf-8")
    web = FARBEN_WEB.read_text(encoding="utf-8").lower()
    ios = FARBEN_IOS.read_text(encoding="utf-8").lower()
    for wert in ("#ce4709", "#0764a6", "#15803d"):
        assert wert in designsprache.lower(), f"{wert} fehlt in DESIGNSPRACHE.md"
        assert wert in web, f"{wert} fehlt in lib/neuigkeiten.ts"
        assert "0x" + wert[1:] in ios, f"{wert} fehlt in ReleaseNewsCard.swift"


def test_nebenbei_ist_keine_kachel():
    """Ein Highlight mit ``aside`` steht als Zeile „Außerdem: …" unter den
    Kacheln. Es zählt nicht zum Fortschritt — sonst müsste man es durchsehen,
    um die Karte abzuschließen —, und es bleibt immer wenigstens eine Kachel."""
    nebenbei = releases.Highlight("Klein", "…", "/fragen", aside=True)
    gross = releases.Highlight("Groß", "…", "/karte")
    rel = releases.Release("9.6.0", "2026-01-01", "x", (gross, nebenbei))
    assert [h.title for h in releases.tiles_for(rel)] == ["Groß"]
    assert [h["aside"] for h in releases.as_dict(rel)["highlights"]] == [False, True]

    for release in releases.RELEASES:
        for client in ("web", "ios"):
            if releases.highlights_for(release, client):
                assert releases.tiles_for(release, client), (
                    f"{release.version} ({client}): nur Nebenbei-Highlights, keine Kachel.")


def test_die_kachel_texte_passen_auf_die_kachel():
    """Tagline, Teaser und Knopf sind je EINE Zeile — auf einer 270 px breiten
    Kachel bzw. in einem Knopf. Längeres gehört in ``text``, das im Spieler
    unter dem Clip steht."""
    for release in releases.RELEASES:
        if release.teaser is not None:
            assert 0 < len(release.teaser) <= 80, f"{release.version}: Teaser zu lang"
        for h in release.highlights:
            if h.tagline is not None:
                assert 0 < len(h.tagline) <= 60, f"{h.title}: Tagline zu lang"
            if h.action is not None:
                assert 0 < len(h.action) <= 30, f"{h.title}: Knopf zu lang"


def test_ein_clip_nennt_seine_laenge():
    """„▶ 0:24" beantwortet vor dem Tipp, wie lange es dauert. Eine Ausgabe
    mit Kacheln (erkennbar am Teaser) nennt die Länge jedes Clips."""
    for release in releases.RELEASES:
        for h in release.highlights:
            for medium in (h.media, h.media_ios):
                if medium is None:
                    continue
                if medium.duration is not None:
                    assert 0 < medium.duration < 300, f"{h.title}: {medium.duration} s"
                elif release.teaser is not None and medium.kind == "video":
                    pytest.fail(f"{release.version} · {h.title}: Clip ohne Länge "
                                f"({medium.src}) — `ffprobe` misst sie.")


def test_die_laenge_stimmt_mit_der_datei():
    """Gemessen, nicht geschätzt: Wird ein Clip ersetzt, ohne die Zahl
    nachzuziehen, stünde auf der Kachel eine falsche Dauer. Ohne ``ffprobe``
    (CI) übersprungen — lokal, wo die Clips entstehen, gibt es ihn."""
    import shutil
    import subprocess

    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe nicht installiert")
    wurzel = WURZEL / releases.MEDIA_ROOT
    falsch = []
    for release in releases.RELEASES:
        for h in release.highlights:
            for medium in (h.media, h.media_ios):
                if not medium or medium.duration is None:
                    continue
                datei = wurzel / medium.src.lstrip("/")
                aus = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(datei)],
                    capture_output=True, text=True, check=False).stdout.strip()
                try:
                    echt = float(aus)
                except ValueError:
                    continue
                if abs(echt - medium.duration) > 0.5:
                    falsch.append(f"{medium.src}: Registry {medium.duration} s, Datei {echt:.1f} s")
    assert not falsch, "Die Länge in kern/releases.py stimmt nicht:\n  " + "\n  ".join(falsch)


def test_titelbild_farbe_und_knopf_haben_eine_vorgabe():
    """Die Clients bekommen fertige Werte: ohne Titelbild das Standbild, ohne
    Farbe Hafenblau, ohne Knopf-Text „Ausprobieren" — entschieden einmal im
    Server, nicht zweimal in Web und App."""
    clip = releases.Media(kind="video", src="/c.mp4", poster="/c.webp", alt="x" * 30)
    bild = releases.Media(kind="image", src="/b.webp", alt="x" * 30)
    titel = releases.Media(kind="video", src="/c.mp4", poster="/c.webp",
                           cover="/c-titel.webp", alt="x" * 30, duration=12.5)
    assert releases.cover_for(clip) == "/c.webp"
    assert releases.cover_for(bild) == "/b.webp"
    assert releases.cover_for(titel) == "/c-titel.webp"

    rel = releases.Release("9.5.0", "2026-01-01", "x", (
        releases.Highlight("A", "…", "/karte", media=titel, color="green",
                           tagline="Eine Zeile.", action="Karte öffnen"),
        releases.Highlight("B", "…", "/fragen", media=clip),
    ), teaser="Zwei neue Sachen.")
    d = releases.as_dict(rel)
    assert d["teaser"] == "Zwei neue Sachen."
    a, b = d["highlights"]
    assert (a["color"], a["tagline"], a["action"]) == ("green", "Eine Zeile.", "Karte öffnen")
    assert a["media"]["cover"] == "/c-titel.webp" and a["media"]["duration"] == 12.5
    assert (b["color"], b["tagline"], b["action"]) == ("primary", None, "Ausprobieren")
    assert b["media"]["cover"] == "/c.webp" and b["media"]["duration"] is None


def test_jede_oberflaeche_bekommt_wenigstens_ein_highlight():
    """Ein Highlight kann auf eine Oberfläche beschränkt sein (``only``) —
    2.2.0 hat das Glossar nur im Browser. Eine Ausgabe, die für die App gar
    nichts übrig lässt, hätte dort eine leere Bühne."""
    for release in releases.RELEASES:
        for client in ("web", "ios"):
            sichtbar = releases.highlights_for(release, client)
            assert sichtbar, f"{release.version}: für {client} bleibt nichts übrig."
            assert len(sichtbar) <= releases.MAX_HIGHLIGHTS, (
                f"{release.version}: {len(sichtbar)} Highlights für {client}.")


def test_only_kennt_nur_zwei_werte():
    erlaubt = {None, releases.NUR_WEB, releases.NUR_NATIVE}
    falsch = [(r.version, h.title, h.only) for r in releases.RELEASES
              for h in r.highlights if h.only not in erlaubt]
    assert not falsch, (
        f"`only` ist None, '{releases.NUR_WEB}' oder '{releases.NUR_NATIVE}': {falsch}")


def test_ein_nur_web_highlight_erscheint_in_der_app_nicht():
    web = releases.Media(kind="image", src="/w.webp", alt="web" * 8)
    beide = releases.Highlight("Überall", "…", "/dashboard", media=web)
    nur_web = releases.Highlight("Nur Browser", "…", "/fragen", media=web,
                                 only=releases.NUR_WEB)
    rel = releases.Release("9.7.0", "2026-01-01", "x", (beide, nur_web))
    assert [h["title"] for h in releases.as_dict(rel, "web")["highlights"]] == ["Überall", "Nur Browser"]
    assert [h["title"] for h in releases.as_dict(rel, "ios")["highlights"]] == ["Überall"]


def test_die_app_fassung_ist_ganz_oder_gar_nicht():
    """Tims Wunsch 07.09.2026: In der App sollen die Bilder aus der App kommen.

    Fehlt einem Highlight die App-Fassung, bekommt die App für die GANZE
    Ausgabe die Web-Bilder (``releases.media_for``) — ein Wechsel mitten in der
    Bühne wäre schlimmer als eine durchgehend fremde Oberfläche. Der Wächter
    meldet den halben Satz trotzdem: Er ist fast immer ein Versehen."""
    for release in releases.RELEASES:
        sichtbar = releases.highlights_for(release, "ios")
        mit = [h.title for h in sichtbar if h.media_ios]
        ohne = [h.title for h in sichtbar if not h.media_ios]
        assert not (mit and ohne), (
            f"{release.version}: App-Bilder für {len(mit)}, nicht für {ohne}. "
            "Die App bekommt deshalb überall die Web-Bilder — entweder alle "
            "aufnehmen oder keins.")


def test_die_app_bekommt_ihre_eigenen_bilder_wenn_es_sie_gibt():
    """Die Auswahl fällt serverseitig; ohne App-Fassung ist Web der Rückfall."""
    web = releases.Media(kind="image", src="/w.webp", alt="web" * 8)
    app = releases.Media(kind="image", src="/i.webp", alt="app" * 8)
    nur_web = releases.Highlight("A", "…", "/dashboard", media=web)
    beides = releases.Highlight("B", "…", "/dashboard", media=web, media_ios=app)
    assert releases.media_for(beides, "ios") is app
    assert releases.media_for(beides, "app") is app       # ältere App-Stände
    assert releases.media_for(beides, "web") is web
    assert releases.media_for(nur_web, "ios") is web      # Rückfall

    voll = releases.Release("9.9.0", "2026-01-01", "x", (beides,))
    halb = releases.Release("9.8.0", "2026-01-01", "x", (beides, nur_web))
    assert releases.has_native_media(voll) and not releases.has_native_media(halb)
    # Eine halbe App-Fassung schlägt für die GANZE Ausgabe auf Web zurück.
    assert releases.as_dict(halb, "ios")["highlights"][0]["media"]["src"] == "/w.webp"
    assert releases.as_dict(voll, "ios")["highlights"][0]["media"]["src"] == "/i.webp"


def test_alle_medien_einer_ausgabe_teilen_ein_seitenverhaeltnis():
    """Sonst springt der Kasten der Bühne beim Blättern — genau das, was die
    Bewegungsregeln vermeiden (DESIGNSPRACHE §7). Web und App dürfen sich
    unterscheiden: querformatige Fenster hier, hochkante Telefone dort."""
    for release in releases.RELEASES:
        for client, feld in (("web", "media"), ("ios", "media_ios")):
            formate = {getattr(h, feld).aspect
                       for h in releases.highlights_for(release, client)
                       if getattr(h, feld)}
            assert len(formate) <= 1, (
                f"{release.version} ({client}): mehrere Seitenverhältnisse {formate}.")


def test_ein_clip_bringt_sein_standbild_mit():
    """``prefers-reduced-motion`` zeigt das Standbild STATT des Clips — ohne
    Poster bliebe die Bühne dort leer."""
    for release in releases.RELEASES:
        for h in release.highlights:
            for medium in (h.media, h.media_ios):
                if medium and medium.kind == "video":
                    assert medium.poster, (
                        f"{release.version} · {h.title}: Clip ohne Standbild.")


def test_medien_tragen_eine_bildbeschreibung():
    for release in releases.RELEASES:
        for h in release.highlights:
            for medium in (h.media, h.media_ios):
                if medium:
                    assert len(medium.alt) > 20, f"{release.version} · {h.title}: alt zu dünn"


def test_jede_version_steht_auch_im_changelog():
    """Die Karte ist die Kurzfassung eines Abschnitts, nicht seine Konkurrenz.
    Fehlt der Abschnitt, ist entweder die Version falsch getippt oder der
    Versionsschnitt vergessen worden."""
    changelog = (WURZEL / "CHANGELOG.md").read_text(encoding="utf-8")
    geschnitten = [m.group(1) for m in re.finditer(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M)]
    for release in releases.RELEASES:
        if release.version == _naechste_major(geschnitten):
            # Die Karte entsteht VOR dem Release-PR (Clips brauchen eine
            # eigene Runde, s. kern/releases.py) — der Abschnitt kommt erst
            # mit dem Versionsschnitt. Erlaubt ist das genau für die nächste
            # Major; ein Tippfehler in der Version fällt weiter auf.
            continue
        assert f"## [{release.version}]" in changelog, (
            f"{release.version} hat eine Karte, aber keinen Changelog-Abschnitt.")


def _naechste_major(geschnitten: list[str]) -> str | None:
    if not geschnitten:
        return None
    hoechste = max(releases.version_key(v) for v in geschnitten)
    return f"{hoechste[0] + 1}.0.0"


def test_die_vorbereitete_karte_ist_genau_die_naechste_major():
    """Die Ausnahme oben ist eng: ``2.10.0`` geschnitten → nur ``3.0.0`` darf
    vorab eine Karte haben, ``3.1.0`` oder ``4.0.0`` nicht."""
    assert _naechste_major(["2.9.0", "2.10.0"]) == "3.0.0"
    assert _naechste_major(["3.0.0", "2.10.0"]) == "4.0.0"
    assert _naechste_major([]) is None


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
