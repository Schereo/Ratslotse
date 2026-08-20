"""Gescannte Anlagen lesen — und die Trennung, die dabei die eigentliche Arbeit tut.

Der Lauf schreibt ``status='ocr'`` und nicht ``'ok'``. Das ist keine Kosmetik:
'ok' zöge jeden gelesenen Scan in die Chunk-Vektoren und damit in Antworten der
KI-Frage — darunter 54 Förderanträge von Vereinen mit Ansprechpartnerinnen,
Anschriften und Unterschriften. Die Finanz-Parser müssen den Text trotzdem
sehen. Genau diese beiden Sätze prüfen die ersten zwei Tests; sie sind der
Grund, dass die Datei existiert.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council import ocr  # noqa: E402
from council.store import CouncilStore  # noqa: E402

# Ein Wirtschaftsplan-Label, das die Finanzquellen-Registry erkennt.
LABEL_FINANZ = "Wirtschaftsplan 2019 Abfallwirtschaftsbetrieb"
TEXT = "Gesamtleistung\t24.058.098\nGesamtkosten\t23.346.848\n" * 12


def _store_mit_anlage(tmp_path: Path, status: str) -> CouncilStore:
    store = CouncilStore(tmp_path / f"c_{status}.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_anlagen (document_id, kvonr, label, url, raw_text, "
            "n_pages, fetched_at, status, ocr_modell) "
            "VALUES (4711, 99, ?, 'https://x/4711', ?, 36, datetime('now'), ?, ?)",
            (LABEL_FINANZ, TEXT, status, "modell/x" if status == "ocr" else None))
    return store


# --------------------------------------------------------------------------
# (a) Gelesener Scan ist ganz normaler Anlagentext
# --------------------------------------------------------------------------

def test_gelesener_scan_ist_durchsuchbar(tmp_path):
    """Bis zum 20.08.2026 schrieb der Lauf `status='ocr'` und hielt den Text
    damit pauschal aus der Suche. Das war der falsche Ort für die Sperre:
    Sie traf die HERKUNFT des Textes statt dessen, was darin steht — und
    schloss den AWB-Wirtschaftsplan, den Prüfbericht und das
    Investitionsprogramm gleich mit aus.

    Ein gescannter Wirtschaftsplan ist so durchsuchbar wie ein getippter.
    Wie er gelesen wurde, steht in `ocr_modell`."""
    store = _store_mit_anlage(tmp_path, "ok")
    try:
        offen = store.anlagen_missing_embeddings()
        assert [z["document_id"] for z in offen] == [4711]
        zeile = store._conn.execute(
            "SELECT ocr_modell FROM council_anlagen WHERE document_id=4711").fetchone()
        assert zeile["ocr_modell"] is None or isinstance(zeile["ocr_modell"], str)
    finally:
        store.close()


def test_die_finanz_parser_sehen_den_text_ohnehin(tmp_path):
    """`Erkennung.where()` filtert bewusst NICHT auf den Status — daran hat
    sich nichts geändert, und der Test hält es fest."""
    from council import finanzquellen as fq

    store = _store_mit_anlage(tmp_path, "ok")
    try:
        quelle = fq.QUELLEN["wirtschaftsplan"]
        sql, werte = quelle.erkennung.abfrage("document_id, label")
        gefunden = [r["document_id"] for r in store._conn.execute(sql, werte).fetchall()]
        assert 4711 in gefunden
        assert "status" not in sql.lower()
    finally:
        store.close()


def test_ein_zweiter_lauf_bezahlt_nichts_doppelt(tmp_path):
    """Die Arbeitsliste nimmt nur 'empty' — 'ok' ist erledigt."""
    from scripts.backfill_anlagen_ocr import kandidaten

    store = _store_mit_anlage(tmp_path, "ok")
    try:
        assert kandidaten(store, False, None, None) == []
        with store._conn:
            store._conn.execute(
                "UPDATE council_anlagen SET status='empty' WHERE document_id=4711")
        assert [k["document_id"] for k in kandidaten(store, False, None, None)] == [4711]
    finally:
        store.close()


def test_altstaende_mit_ocr_status_werden_gehoben(tmp_path):
    """`status='ocr'` gab es genau einen Tag lang (20.08.2026), solange
    gelesener Scan-Text pauschal aus der Suche gehalten wurde.

    Die Migration hebt solche Zeilen beim Öffnen der Datenbank auf 'ok' —
    NICHT der OCR-Lauf. Der Text ist ja in Ordnung, nur sein Status war es
    nicht; ihn neu lesen zu lassen kostete Geld für nichts."""
    from scripts.backfill_anlagen_ocr import kandidaten

    from council.store import CouncilStore

    # Erst die Altzeile anlegen, dann die Datenbank neu öffnen — so wie es im
    # Betrieb passiert: Die Zeile stand schon da, als der neue Code kam.
    _store_mit_anlage(tmp_path, "ocr").close()
    store = CouncilStore(tmp_path / "c_ocr.sqlite")
    try:
        status = store._conn.execute(
            "SELECT status FROM council_anlagen WHERE document_id=4711").fetchone()[0]
        assert status == "ok", "der Altstand wird gehoben, nicht neu gelesen"
        assert kandidaten(store, False, None, None) == []
        # Und er ist damit durchsuchbar — genau darum ging es.
        assert [z["document_id"] for z in store.anlagen_missing_embeddings()] == [4711]
    finally:
        store.close()


# --------------------------------------------------------------------------
# (b) Die Einheit, die unsere Rechenprobe nicht sieht
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text, erwartet", [
    ("Erfolgsplan 2019 in TEUR\nGesamtleistung 24.058", ["in TEUR"]),
    ("Angaben in Mio. €", ["in Mio. €"]),
    ("alle Werte in T€ ausgewiesen", ["in T€"]),
    ("Beträge in Tausend Euro", ["in Tausend"]),
    ("Gesamtleistung 24.058.098 EUR", []),
])
def test_skalenhinweise(text, erwartet):
    """„in TEUR" in der Kopfzeile setzt die Größenordnung jeder Zahl darunter —
    und die Spaltenprobe des Bereichs ist skaleninvariant, sieht das also
    prinzipiell nicht. Deshalb wird die Angabe eigens gesucht."""
    assert ocr.skalenhinweise(text) == erwartet


def test_skalenhinweise_ohne_dubletten():
    text = "in TEUR\n...\nin TEUR\n...\nin Mio. EUR"
    assert ocr.skalenhinweise(text) == ["in TEUR", "in Mio. EUR"]


# --------------------------------------------------------------------------
# (c) Seite → Bild, ohne neue Abhängigkeit
# --------------------------------------------------------------------------

class _Mediabox:
    width, height = 842.0, 595.0        # A4 quer, wie die AWB-Scans


class _PilBild:
    """Nur `size` — mehr braucht `_deckt_die_seite` nicht."""

    def __init__(self, size):
        self.size = size


class _Bild:
    def __init__(self, name, daten=b"\xff\xd8\xff\xe0JPEG", size=(3507, 2480)):
        self.name = name
        self.data = daten
        # 3507x2480 px auf 842x595 pt = 300 dpi: ein echter Scan.
        self.image = _PilBild(size) if size else None


class _Seite:
    def __init__(self, *bilder, text=""):
        self.images = list(bilder)
        self.mediabox = _Mediabox()
        self._text = text

    def extract_text(self):
        return self._text


def test_ein_eingebettetes_bild_wird_durchgereicht():
    """Der Scan selbst geht weiter — keine Neukodierung, kein Renderer, keine
    neue Abhängigkeit im Deployment."""
    bild = ocr.seite_als_bild(_Seite(_Bild("s0.jpg")))
    assert bild.weg == "eingebettet"
    assert bild.mime == "image/jpeg"
    assert bild.als_data_url().startswith("data:image/jpeg;base64,")


def test_zwei_bilder_werden_gerendert_statt_geraten(monkeypatch):
    """Briefkopf-Logo plus Scan: Dann ist nicht entscheidbar, welches Bild die
    Seite IST. Raten wäre hier die schlechtere Antwort als rendern."""
    gerufen = []
    monkeypatch.setattr(ocr, "_gerendert",
                        lambda s, dpi: gerufen.append(dpi) or ocr.Seitenbild(b"x", "image/png", "gerendert"))
    assert ocr.seite_als_bild(_Seite(_Bild("logo.png"), _Bild("scan.jpg"))).weg == "gerendert"
    assert gerufen == [200]


def test_unbekanntes_bildformat_wird_gerendert(monkeypatch):
    """Ein TIFF im PDF nimmt kein Sehmodell an."""
    monkeypatch.setattr(ocr, "_gerendert",
                        lambda s, dpi: ocr.Seitenbild(b"x", "image/png", "gerendert"))
    assert ocr.seite_als_bild(_Seite(_Bild("s0.tiff"))).weg == "gerendert"


def test_ohne_renderer_bleibt_die_seite_ungelesen(monkeypatch):
    """Eine Lücke ist im Haushalts-Bereich ein zulässiger Zustand, eine
    geratene Zahl nicht — deshalb ein Fehler und kein Notbehelf."""
    import builtins

    echt = builtins.__import__          # VOR dem Patch festhalten, sonst ruft
    ohne = {"pypdfium2", "pymupdf"}     # sich der Ersatz selbst auf

    def kein_renderer(name, *a, **k):
        if name in ohne:
            raise ImportError(f"no {name}")
        return echt(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", kein_renderer)
    with pytest.raises(ocr.OcrFehler) as fehler:
        ocr.seite_als_bild(_Seite())
    assert "pypdfium2" in str(fehler.value)


# --------------------------------------------------------------------------
# (d) Vollständigkeit ist keine Richtigkeit
# --------------------------------------------------------------------------

def test_uebersprungene_seiten_werden_gezaehlt(monkeypatch, tmp_path):
    """Der Fehler, den eine Rechenprobe prinzipiell NICHT findet: Fehlt eine
    Zeile, prüft die Probe weniger — und geht auf. Ein Modell hat im Testlauf
    genau das getan (18 statt 24 Proben, alle grün)."""
    seiten = [_Seite(_Bild("a.jpg")), _Seite(), _Seite(_Bild("c.jpg"))]

    class _Leser:
        pages = seiten

    monkeypatch.setattr(ocr.pypdf, "PdfReader", lambda *_a, **_k: _Leser())
    monkeypatch.setattr(ocr, "_gerendert",
                        lambda *_a, **_k: (_ for _ in ()).throw(ocr.OcrFehler("kein Renderer")))
    monkeypatch.setattr(ocr, "lies_seite", lambda bild, model=None: "Zeile " * 20)

    lesung = ocr.lies_pdf(b"%PDF-1.4")
    assert lesung.seiten == 3
    assert lesung.gelesen == 2
    assert lesung.uebersprungen == 1
    assert lesung.vollstaendig is False
    assert "[Seite 2: nicht lesbar gemacht]" in lesung.text


def test_vollstaendig_gelesen(monkeypatch):
    class _Leser:
        pages = [_Seite(_Bild("a.jpg")), _Seite(_Bild("b.jpg"))]

    monkeypatch.setattr(ocr.pypdf, "PdfReader", lambda *_a, **_k: _Leser())
    monkeypatch.setattr(ocr, "lies_seite", lambda bild, model=None: "in TEUR " + "x " * 30)
    lesung = ocr.lies_pdf(b"%PDF-1.4")
    assert lesung.vollstaendig and lesung.gelesen == 2
    assert lesung.skalen == ("in TEUR",)
    assert lesung.weg == "eingebettet"


# --------------------------------------------------------------------------
# (e) Der Prompt trägt vier Anweisungen, die aus Fehlläufen stammen
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stichwort, warum", [
    ("NICHTS AUSLASSEN", "ein Modell ließ eine Summenzeile ersatzlos weg"),
    ("in TEUR", "Allzweck-Sehmodelle löschen laufende Kopfzeilen als Rauschen"),
    ("1.234.567,89", "deutsche Beträge nicht umformatieren lassen"),
    ("[unleserlich]", "nicht raten, wo nichts zu entziffern ist"),
])
def test_prompt_behaelt_seine_regeln(stichwort, warum):
    assert stichwort in ocr.PROMPT, warum


def test_temperatur_ist_null():
    """Wiederholbarkeit ist die Voraussetzung dafür, dass Uneinigkeit zweier
    Modelle überhaupt etwas bedeutet."""
    assert ocr.TEMPERATUR == 0.0


# --------------------------------------------------------------------------
# (g) Der Download — und warum er die Sitzung des Repos braucht
# --------------------------------------------------------------------------

def test_der_download_nutzt_den_browser_user_agent():
    """Mit dem Standard-UA von `requests` antwortet das Bürgerinfo 403.

    Der erste Lauf auf der Dev-VM (20.08.2026) hat das vorgeführt: sechs
    Anlagen geladen, zwei abgewiesen — und eine davon war der
    AWB-Wirtschaftsplan 2020, also ein ganzer Jahrgang, der still fehlte."""
    from scripts.backfill_anlagen_ocr import _session

    assert _session.headers.get("User-Agent") == "Mozilla/5.0"


def test_ein_403_wird_wiederholt(monkeypatch):
    """403 heißt beim Bürgerinfo nicht nur „falscher User-Agent", sondern auch
    „zu schnell". Ein zweiter Versuch kostet nichts und rettet den Jahrgang."""
    import requests

    from scripts import backfill_anlagen_ocr as b

    versuche = []

    class _Antwort:
        content = b"%PDF-1.4"

        def raise_for_status(self):
            versuche.append(1)
            if len(versuche) < 3:
                raise requests.HTTPError("403 Client Error: Forbidden")

    monkeypatch.setattr(b._session, "get", lambda *_a, **_k: _Antwort())
    monkeypatch.setattr(b.time, "sleep", lambda _s: None)
    assert b._hole("https://x/1") == b"%PDF-1.4"
    assert len(versuche) == 3, "erst der dritte Versuch ging durch"


def test_ein_dauerhaftes_403_faellt_durch(monkeypatch):
    """Sonst hinge der Lauf ewig — und eine Anlage, die es wirklich nicht
    gibt, stünde als „gelesen" da."""
    import requests

    from scripts import backfill_anlagen_ocr as b

    class _Antwort:
        content = b""

        def raise_for_status(self):
            raise requests.HTTPError("403 Client Error: Forbidden")

    monkeypatch.setattr(b._session, "get", lambda *_a, **_k: _Antwort())
    monkeypatch.setattr(b.time, "sleep", lambda _s: None)
    with pytest.raises(requests.HTTPError):
        b._hole("https://x/1")


# --------------------------------------------------------------------------
# (h) Ein Logo ist nicht die Seite
# --------------------------------------------------------------------------

def test_ein_briefkopf_logo_wird_nicht_fuer_die_seite_gehalten(monkeypatch):
    """DER FALL, DER DIESE PRÜFUNG ERZWUNGEN HAT (20.08.2026):

    Seite 1 des RPA-Schlussberichts 2024 ist eine Vektorseite mit **einem**
    Briefkopf-Logo. Die alte Regel („genau ein Bild = der Scan") schickte also
    das Logo ans Sehmodell und bekam „Stadt Oldenburg | Rechnungsprüfungsamt"
    zurück — 62 Zeichen, die aussahen wie ein Ergebnis.

    Gemessen: Logo 528×195 px auf A4 = 64 dpi. Der AWB-Scan: 3507×2480 px auf
    derselben Fläche = 300 dpi."""
    gerendert = []
    monkeypatch.setattr(ocr, "_gerendert", lambda s, dpi: gerendert.append(1)
                        or ocr.Seitenbild(b"x", "image/png", "gerendert"))

    logo = _Bild("logo.jpg", size=(528, 195))
    seite = _Seite(logo, text="Ein Deckblatt mit Fließtext darauf." * 5)
    seite.mediabox = type("_MB", (), {"width": 595.0, "height": 842.0})()

    assert ocr.seite_als_bild(seite).weg == "gerendert"
    assert gerendert, "eine 64-dpi-Grafik ist kein Seitenscan"


def test_ein_seitenfuellender_scan_geht_unveraendert_durch():
    """Die Gegenprobe — sonst wäre die Prüfung oben nur eine Blockade."""
    bild = ocr.seite_als_bild(_Seite(_Bild("s0.jpg", size=(3507, 2480))))
    assert bild.weg == "eingebettet"


def test_ohne_pillow_entscheidet_die_textebene(monkeypatch):
    """Ist die Pixelgröße nicht zu haben, gilt: Eine Seite mit lesbarem Text
    ist keine gescannte Seite."""
    monkeypatch.setattr(ocr, "_gerendert",
                        lambda s, dpi: ocr.Seitenbild(b"x", "image/png", "gerendert"))
    mit_text = _Seite(_Bild("x.jpg", size=None), text="Lesbarer Fließtext." * 10)
    ohne_text = _Seite(_Bild("x.jpg", size=None), text="")
    assert ocr.seite_als_bild(mit_text).weg == "gerendert"
    assert ocr.seite_als_bild(ohne_text).weg == "eingebettet"


# --------------------------------------------------------------------------
# (i) Platzhalter sind kein Text
# --------------------------------------------------------------------------

def test_null_gelesene_seiten_werden_nicht_gespeichert(monkeypatch, tmp_path):
    """DER FALL, DER DAS ERZWUNGEN HAT (20.08.2026):

    Drei Dokumente ohne Renderer lieferten 737 bzw. 3253 Zeichen — und zwar
    ausschließlich die Platzhalter „[Seite N: nicht lesbar gemacht]". Die
    Längenprüfung ließ sie durch, und sie standen danach mit `status='ocr'` im
    Bestand: gelesen aussehend, ohne einen einzigen Buchstaben vom Papier.

    `gelesen == 0` heißt nichts gelesen, egal wie lang der Text ist."""
    from scripts import backfill_anlagen_ocr as b

    store = _store_mit_anlage(tmp_path, "empty")
    try:
        leer = ocr.Lesung(
            text="[Seite 1: nicht lesbar gemacht]\n" * 22,
            seiten=22, gelesen=0, uebersprungen=22, skalen=(),
            modell="modell/x", weg="keiner")
        assert len(leer.text) > ocr.MIN_SEITE, "der Platzhalter ist lang genug"

        monkeypatch.setattr(b, "_hole", lambda url: b"%PDF-1.4")
        monkeypatch.setattr(b.ocr, "lies_pdf", lambda *_a, **_k: leer)
        stats = b.process(Path(store._conn.execute("PRAGMA database_list")
                               .fetchone()[2]),
                          nur_finanz=False, document_id=4711, limit=None,
                          workers=1, max_seiten=120, model="modell/x",
                          trocken=False)
        assert stats["gelesen"] == 0 and stats["ohne_text"] == 1
    finally:
        store.close()

    # Und die Anlage steht weiter auf der Arbeitsliste.
    from council.store import CouncilStore
    nach = CouncilStore(tmp_path / "c_empty.sqlite")
    try:
        zeile = nach._conn.execute(
            "SELECT status, raw_text FROM council_anlagen WHERE document_id=4711"
        ).fetchone()
        assert zeile["status"] == "empty", (
            "ein Dokument ohne gelesene Seite bleibt auf der Arbeitsliste")
    finally:
        nach.close()


def test_platzhalter_anlagen_kommen_zurueck_auf_die_arbeitsliste(tmp_path):
    """Ein Lauf ohne Renderer hat am 20.08.2026 drei Anlagen hinterlassen,
    deren Text nur aus Platzhaltern bestand. Sie sähen für jeden späteren Lauf
    erledigt aus und wären es nie gewesen."""
    from scripts.backfill_anlagen_ocr import kandidaten

    store = _store_mit_anlage(tmp_path, "ok")
    try:
        # Zuerst: ein echter Text bleibt erledigt.
        assert kandidaten(store, False, None, None) == []

        with store._conn:
            store._conn.execute(
                "UPDATE council_anlagen SET raw_text = ? WHERE document_id = 4711",
                ("\n".join(ocr.PLATZHALTER.format(nr=n) for n in range(1, 23)),))
        zurueck = kandidaten(store, False, None, None)
        assert [k["document_id"] for k in zurueck] == [4711], (
            "eine Anlage, die nur Platzhalter trägt, ist nicht gelesen")
    finally:
        store.close()




def test_ein_zu_grosses_bild_wird_gerendert(monkeypatch):
    """Anlage 188884 trägt einen Scan von über 30 MB. Die Gegenstelle wies ihn
    mit „413 — Downloaded image content cannot exceed 30MB" ab, und die
    Anlage blieb als einzige von 227 ungelesen.

    Gerendert bei 200 dpi sind es ein paar hundert Kilobyte — die Vorlage hat
    ohnehin mehr Auflösung, als ein Sehmodell nutzt."""
    monkeypatch.setattr(ocr, "_gerendert",
                        lambda s, dpi: ocr.Seitenbild(b"x", "image/png", "gerendert"))
    riesig = _Bild("s0.jpg", daten=b"\xff\xd8" * (ocr.MAX_BILD_BYTES // 2 + 1))
    assert ocr.seite_als_bild(_Seite(riesig)).weg == "gerendert"


def test_ein_normal_grosses_bild_geht_weiter_durch():
    """Die Gegenprobe — sonst wäre die Grenze nur eine Bremse."""
    assert ocr.seite_als_bild(_Seite(_Bild("s0.jpg"))).weg == "eingebettet"
