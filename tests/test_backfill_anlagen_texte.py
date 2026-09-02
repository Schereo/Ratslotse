"""Auswahl des Anlagen-Backfills (scripts/backfill_anlagen_texte.py).

Geprüft wird die **Auswahl**, nicht der PDF-Extraktor: Welche Anlagen holt ein
Lauf, und welche lässt er in Ruhe. Genau dort versteckt sich der Fehler, den
`--gekappte` beheben soll — eine an der alten Grenze abgeschnittene Anlage
steht auf ``ok`` und käme nie wieder an die Reihe.
"""
import scripts.backfill_anlagen_texte as bf
from council.store import CouncilStore


def _anlage(store: CouncilStore, document_id: int, label: str,
            text: str, status: str = "ok") -> None:
    with store._conn:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "INSERT OR REPLACE INTO council_attachments "
            "(document_id, kvonr, label, url, raw_text, n_pages, fetched_at, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (document_id, 1, label, f"https://example.org/{document_id}.pdf",
             text, 300, "2026-08-18T00:00:00", status))


def _bestand(tmp_path):
    """Drei Anlagen: eine ungeholt, eine gekappt, eine vollständig."""
    store = CouncilStore(tmp_path / "council.sqlite")
    _anlage(store, 1, "Jahresabschluss 2019 Stadt Oldenburg", "", status="listed")
    # Exakt an der früheren Grenze — also damals abgeschnitten.
    _anlage(store, 2, "Jahresabschluss 2022 der Kernverwaltung",
            "x" * bf.FRUEHERE_GRENZEN[0])
    # Krumme Länge: vollständig geladen, nichts nachzuholen.
    _anlage(store, 3, "Gutachten Verkehrsplanung", "y" * 12_345)
    store.close()
    return tmp_path / "council.sqlite"


def _geholte(monkeypatch, db, **kw) -> set[int]:
    """`process` laufen lassen, ohne das Netz anzufassen — und mitschreiben,
    welche Dokumente es angefasst hätte."""
    gesehen: set[int] = set()

    def falscher_extraktor(url: str):
        gesehen.add(int(url.rsplit("/", 1)[1].split(".")[0]))
        return ("Neuer, vollständiger Text " * 50, 300)

    monkeypatch.setattr(bf, "_pdf_text", falscher_extraktor)
    bf.process(db, None, 2, retry_failed=False, **kw)
    return gesehen


def test_ohne_schalter_bleiben_gekappte_anlagen_liegen(tmp_path, monkeypatch):
    """Der Normalfall — und zugleich der Grund, warum es den Schalter braucht.

    Ein Lauf ohne `--gekappte` fasst nur ungeholte Anlagen an. Die an der alten
    Grenze abgeschnittene bleibt liegen, obwohl ihr Text unvollständig ist.
    """
    db = _bestand(tmp_path)
    assert _geholte(monkeypatch, db) == {1}


def test_mit_schalter_kommen_die_gekappten_dazu(tmp_path, monkeypatch):
    db = _bestand(tmp_path)
    # Dokument 3 ist vollständig (krumme Länge) und bleibt auch jetzt in Ruhe —
    # sonst zöge jede Erhöhung der Grenze den ganzen Bestand neu.
    assert _geholte(monkeypatch, db, gekappte=True) == {1, 2}


def test_der_finanz_filter_gilt_auch_fuer_die_gekappten(tmp_path, monkeypatch):
    """Die Klammer-Falle: `A AND B OR C` läse sich als `(A AND B) OR C`.

    Ohne Klammern fiele der `--nur-finanz`-Filter für die gekappten Anlagen weg
    — ein Lauf, der 293 Dokumente meint, holte plötzlich alle. Dokument 3 ist
    hier die Probe: krumme Länge UND kein Finanz-Label.
    """
    db = _bestand(tmp_path)
    store = CouncilStore(db)
    # Ein gekapptes Dokument OHNE Finanz-Label — es darf nicht mitkommen.
    _anlage(store, 4, "Gutachten Lärmschutz", "z" * bf.FRUEHERE_GRENZEN[0])
    store.close()

    geholt = _geholte(monkeypatch, db, gekappte=True, nur_finanz=True)
    assert 2 in geholt, "der gekappte Jahresabschluss gehört dazu"
    assert 4 not in geholt, "ein gekapptes Gutachten ist keine Finanz-Anlage"
    assert 3 not in geholt


def test_die_neue_grenze_laesst_die_jahresabschluesse_ganz_durch(tmp_path, monkeypatch):
    """Die Grenze muss über dem längsten gemessenen Dokument liegen.

    Der Jahresabschluss 2022 hat 709.076 Zeichen (gemessen 18.08.2026). Bei
    400.000 fehlte Abschnitt 8; die neue Grenze trägt ihn mit Luft.
    """
    assert bf.MAX_TEXT > 709_076
    assert all(g < bf.MAX_TEXT for g in bf.FRUEHERE_GRENZEN)


def _glyphen_bestand(tmp_path):
    """Zwei Anlagen auf `ok`: eine mit echtem Text, eine mit Glyphen-Rauschen —
    dazu ein Nicht-Finanz-Dokument mit demselben Rauschen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    _anlage(store, 5, "Jahresabschluss 2023 der Kernverwaltung", "Ordentliche Erträge " * 500)
    # Der Fall 295296: kaputte Zeichenzuordnung, kein einziger Buchstabe.
    _anlage(store, 6, "Schlussbericht des Rechnungsprüfungsamtes 2024", "/12 /8 /6 □ /13 " * 2000)
    _anlage(store, 7, "Gutachten Lärmkartierung", "/12 /8 /6 □ /13 " * 2000)
    store.close()
    return tmp_path / "council.sqlite"


def _status(db) -> dict[int, tuple[str, int]]:
    store = CouncilStore(db)
    try:
        return {r[0]: (r[1], len(r[2] or "")) for r in store._conn.execute(  # noqa: SLF001
            "SELECT document_id, status, raw_text FROM council_attachments")}
    finally:
        store.close()


def test_ohne_schalter_bleibt_das_glyphen_dokument_auf_ok(tmp_path, monkeypatch):
    """Der Zustand, in dem der Schlussbericht 2024 zwei Wochen lag: `ok`, und
    damit für jeden Lauf erledigt — obwohl niemand ihn lesen konnte."""
    db = _glyphen_bestand(tmp_path)
    _geholte(monkeypatch, db)
    assert _status(db)[6][0] == "ok"


def test_mit_schalter_geht_das_glyphen_dokument_an_die_ocr(tmp_path, monkeypatch):
    db = _glyphen_bestand(tmp_path)
    _geholte(monkeypatch, db, glyphen=True)
    stand = _status(db)
    assert stand[6] == ("empty", 0)
    # Echter Text bleibt, wie er ist — die Schwelle trifft nur Rauschen.
    assert stand[5][0] == "ok" and stand[5][1] > 0


def test_der_finanz_filter_gilt_auch_fuer_die_glyphen(tmp_path, monkeypatch):
    """`--nur-finanz` ist im Ops-Lauf die Regel; das Gutachten bleibt liegen,
    der Schlussbericht nicht."""
    db = _glyphen_bestand(tmp_path)
    _geholte(monkeypatch, db, glyphen=True, nur_finanz=True)
    stand = _status(db)
    assert stand[6][0] == "empty"
    assert stand[7][0] == "ok"
