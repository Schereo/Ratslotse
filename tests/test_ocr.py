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
# (a) Die Sperre: gelesen, aber nicht veröffentlicht
# --------------------------------------------------------------------------

def test_ocr_text_geht_nicht_in_die_chunk_vektoren(tmp_path):
    """`status='ocr'` hält den Text aus der Gründlichen Recherche heraus.

    Wäre er 'ok', stünden Namen und Anschriften aus Vereinsanträgen ab dem
    nächsten Embedding-Lauf in Nutzerantworten — ohne dass das jemand
    entschieden hätte."""
    store = _store_mit_anlage(tmp_path, "ocr")
    try:
        offen = store.anlagen_missing_embeddings()
        assert [z["document_id"] for z in offen] == []
    finally:
        store.close()


def test_dieselbe_anlage_als_ok_waere_drin(tmp_path):
    """Die Gegenprobe — sonst prüfte der Test oben nur, dass die Abfrage leer ist."""
    store = _store_mit_anlage(tmp_path, "ok")
    try:
        offen = store.anlagen_missing_embeddings()
        assert [z["document_id"] for z in offen] == [4711]
    finally:
        store.close()


def test_die_finanz_parser_sehen_den_ocr_text_trotzdem(tmp_path):
    """`Erkennung.where()` filtert bewusst NICHT auf den Status.

    Wer dort einmal `status='ok'` ergänzt, dreht die Sperre oben in eine
    Blockade: Die Wirtschaftspläne 2019–2021 wären gelesen und blieben doch
    unsichtbar."""
    from council import finanzquellen as fq

    store = _store_mit_anlage(tmp_path, "ocr")
    try:
        quelle = fq.QUELLEN["wirtschaftsplan"]
        sql, werte = quelle.erkennung.abfrage("document_id, label")
        gefunden = [r["document_id"] for r in store._conn.execute(sql, werte).fetchall()]
        assert 4711 in gefunden, "der OCR-Text muss für die Parser sichtbar bleiben"
        assert "status" not in sql.lower()
    finally:
        store.close()


def test_ein_zweiter_lauf_bezahlt_nichts_doppelt(tmp_path):
    """Die Arbeitsliste nimmt nur 'empty' — 'ocr' ist erledigt."""
    from scripts.backfill_anlagen_ocr import kandidaten

    store = _store_mit_anlage(tmp_path, "ocr")
    try:
        assert kandidaten(store, False, None, None) == []
        with store._conn:
            store._conn.execute(
                "UPDATE council_anlagen SET status='empty' WHERE document_id=4711")
        assert [k["document_id"] for k in kandidaten(store, False, None, None)] == [4711]
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
# (f) Die Sperre darf keine Blockade werden
# --------------------------------------------------------------------------

def test_der_ingest_liest_auch_aus_ocr_anlagen():
    """Dieselbe Marke, zwei Rollen — und nur eine davon ist eine Sperre.

    `status='ocr'` hält den Text aus den Chunk-Vektoren heraus (Test oben).
    Aus den PARSERN darf er ihn nicht heraushalten: Sonst wären die drei
    AWB-Jahrgänge 2019–2021 gelesen und trotzdem unsichtbar — genau der
    Zustand, den dieser ganze Lauf beseitigen soll.

    Der Ingest filterte bis zum 20.08.2026 auf `status == 'ok'`. Das war vor
    dem OCR-Lauf richtig und danach falsch."""
    from scripts.ingest_wirtschaftsplaene import ANLAGE_LESBAR

    assert "ocr" in ANLAGE_LESBAR, (
        "Ohne 'ocr' liest der Ingest keine gescannte Anlage mehr — die "
        "Datenschutz-Marke würde zur Blockade")
    assert "ok" in ANLAGE_LESBAR
    assert "empty" not in ANLAGE_LESBAR and "failed" not in ANLAGE_LESBAR


def test_die_herkunft_nennt_das_sehmodell():
    """Wer eine dieser Zahlen später prüft, muss wissen, dass zwischen Papier
    und Datenbank ein Modell stand. Die Spaltenprobe belegt die Rechnung, nicht
    die Ziffernerkennung."""
    from council.wirtschaftsplan import Wirtschaftsplan
    from council.wirtschaftsplan_tabelle import Spaltenprobe, herkunft_fuer

    plan = Wirtschaftsplan(
        betrieb="awb", betrieb_name="Abfallwirtschaftsbetrieb Stadt Oldenburg",
        jahr=2019, vorlage_nr="18/0741", ertraege=20_280_001.0,
        aufwendungen=19_989_470.0, steuern=0.0, ergebnis=290_531.0,
        vermoegensplan=None, verpflichtungen=None, entwurf_vom=None)
    proben = [Spaltenprobe(art="plan", jahr=2019, ertraege=20_280_001.0,
                           aufwendungen=19_989_470.0, ergebnis=290_531.0)]

    ohne = herkunft_fuer(plan, proben, url=None, dokument_id=1, label="x")
    assert "OCR" not in ohne.fundstelle and "OCR" not in ohne.probe_ergebnis

    mit = herkunft_fuer(plan, proben, url=None, dokument_id=1, label="x",
                        ocr_modell="google/gemini-3.1-flash-lite")
    assert "OCR" in mit.fundstelle
    assert "gemini-3.1-flash-lite" in mit.probe_ergebnis


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
    """Ein Lauf ohne Renderer hat am 20.08.2026 drei Anlagen mit
    `status='ocr'` hinterlassen, deren Text nur aus Platzhaltern bestand. Sie
    sähen für jeden späteren Lauf erledigt aus und wären es nie gewesen."""
    from scripts.backfill_anlagen_ocr import kandidaten

    store = _store_mit_anlage(tmp_path, "ocr")
    try:
        # Zuerst: ein echter OCR-Text bleibt erledigt.
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
