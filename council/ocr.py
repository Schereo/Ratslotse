"""Gescannte Anlagen lesen — Seite als Bild an ein Sehmodell.

235 Anlagen stehen auf ``status='empty'``: PDFs ohne Textebene, für die
``backfill_anlagen_texte.py`` nichts zu holen hatte. Darunter die
Wirtschaftspläne des Abfallwirtschaftsbetriebs 2019–2021 — drei Jahrgänge, die
dem Haushalts-Bereich bis heute fehlen.

DREI ENTSCHEIDUNGEN, DIE VORHER GEMESSEN WURDEN (19./20.08.2026):

**Wir rastern selbst, statt das PDF hochzuladen.** OpenRouter hat ein
``file-parser``-Plugin, das PDFs annimmt. Es läuft über OpenRouters *eigenen*
Mistral-Schlüssel — unser ``provider``-Block aus ``kern.llm`` steuert nur die
Modell-Endpunkte, nicht den Parser. Der OCR-Schritt liefe damit still an
``NWZ_OPENROUTER_ROUTING`` vorbei, also an der Anbieter-Sperre und der
Zero-Data-Retention-Pflicht. Ein Bild in einer ganz normalen
``chat_complete``-Nachricht tut das nicht.

**Wir brauchen dafür keinen Renderer.** Jede Seite dieser Scans ist genau *ein*
eingebettetes JPEG; ``pypdf`` gibt es unverändert heraus. Damit kommt keine
neue Abhängigkeit ins Deployment — dieselbe Zurückhaltung, mit der `fastembed`
bewusst außerhalb von ``requirements.txt`` steht. Nur für Seiten, die aus
Vektoren bestehen (der Schlussbericht des Rechnungsprüfungsamts), wird ein
Renderer gebraucht; der ist optional und fehlt er, bleibt die Seite ungelesen
statt falsch gelesen.

**Die Lage-Metadaten lügen — die Lage kommt aus dem Bild.** Gemessen an
sechs Scan-Dokumenten (17.10.2026): ``/Rotate`` und die Platzierungsmatrix
sagen, wie ein BETRACHTER die Seite zeigt, nicht, ob der Text darin aufrecht
steht. Beim Konzernabschluss 2013 (188333) hätten sie richtig aufgerichtet, bei
den AWB-Plänen 2019/2021 (193959, 224533) ein schon aufrechtes Bild seitlich
gedreht, bei 2020/2022 (208461, 240156) gar nichts gesagt. Wir folgen ihnen
deshalb weiterhin nicht.

Seitlich liegende Seiten werden aber AUFGERICHTET (:func:`aufrichten`) — bis
10/2026 gingen sie so an das Modell, wie sie gescannt wurden, weil die AWB-
Proben auch seitlich aufgingen. Das war zu kurz gemessen: In zweispaltigen
Tabellen verrutschen seitlich gelesen die Zeilen. Beim Konzern 2013 bestand
Sonnet alle drei Summenproben mit vier falschen Zellen, bei AWB 2020 standen
alle Beträge eines Blocks eine Beschriftung zu tief — und keine Summenprobe
merkt, wenn die richtige Zahl am falschen Posten steht.

**Aufrichten ist kein Allheilmittel** (Neulesen des Bestands, 17.10.2026,
19 Dokumente): Beim AWB-Prüfbericht 2018 Teil 2 (206874, GuV) verschob die
AUFRECHTE Lesung die Beträge ab Posten 10 um eine Zeile, die seitliche erst ab
Posten 13 — Auslöser sind „davon"-Zeilen mit eigenem Betrag im Text. Gefangen
hat es die Überlappungsprobe der Eigenbetriebe (zwei Berichte, zwei Zahlen →
„strittig"), nicht eine Summenprobe. Das Dokument steht deshalb wieder mit
seiner alten Lesung im Bestand; alle übrigen Datenschichten blieben beim
Neulesen Zeile für Zeile gleich.

WAS DIESES MODUL BEWUSST NICHT TUT: Es normalisiert keine Zahlen. „1.234,56"
bleibt „1.234,56". Wer das Modell rechnen oder umformatieren lässt, verliert
die Probe, mit der der Haushalts-Bereich arbeitet — und bekommt dafür eine
Zahl, die plausibel aussieht. Umgerechnet wird in Python, sichtbar und
prüfbar.
"""
from __future__ import annotations

import base64
import io
import os
import re
import zlib
from dataclasses import dataclass

import pypdf

#: Das Sehmodell. Gemessen an zwei echten AWB-Seiten (300 dpi gerade,
#: 200 dpi quer) gegen die Rechenprobe des Projekts: 24 von 24 Summenzeilen
#: gingen auf, in beiden Läufen, zeichengleich zu Sonnet und zu Gemini Flash.
#: Bei 0,0024 $ je Seite.
MODEL = os.environ.get("COUNCIL_OCR_MODEL") or "google/gemini-3.1-flash-lite"

#: Der Zweitleser für Dokumente, aus denen Zahlen in die Datenbank gehen.
#: Uneinigkeit ist ein Prüffall, kein Mittelwert — gemittelt würde aus zwei
#: verschiedenen Ziffern eine dritte, die auf keinem Papier steht.
MODEL_ZWEIT = os.environ.get("COUNCIL_OCR_MODEL_ZWEIT") or "anthropic/claude-sonnet-4.6"
#: Ab wie vielen Zeilen mit Beträgen eine Seite den Zweitleser bekommt.
#: Fließtext ohne Zahlentabelle kann keine Zeile vertauschen, die ein Parser
#: liest — ihn ein zweites Mal lesen zu lassen, kostete nur.
ZWEIT_AB_ZEILEN = 3

#: Temperatur 0. Zwei Läufe desselben Modells lieferten über 114 Zahlenzellen
#: keine einzige Abweichung — diese Wiederholbarkeit ist die Voraussetzung
#: dafür, dass Uneinigkeit ZWEIER Modelle überhaupt etwas bedeutet.
TEMPERATUR = 0.0

#: Was anstelle einer Seite steht, die sich nicht in ein Bild verwandeln ließ.
#:
#: Er hat einen NAMEN, weil ihn zwei Stellen kennen müssen: Hier wird er
#: geschrieben, und `backfill_anlagen_ocr.kandidaten()` erkennt daran eine
#: Anlage, die zwar `status='ocr'` trägt, aber nichts vom Papier enthält.
PLATZHALTER = "[Seite {nr}: nicht lesbar gemacht]"

#: Kürzer als das gilt eine Seite als ungelesen. Eine leere Rückseite gibt es
#: in diesen Scans durchaus; sie zählt als gelesen-und-leer, nicht als Fehler.
MIN_SEITE = 40

#: Obergrenze je Seite — fängt eine Schleife ab, bevor sie die Datenbank füllt.
#: Eine A4-Tabellenseite dieser Scans liefert 1.500 bis 4.000 Zeichen.
MAX_SEITE = 40_000


class OcrFehler(RuntimeError):
    """Eine Seite ließ sich nicht in ein Bild verwandeln."""


# --------------------------------------------------------------------------
# Seite → Bild
# --------------------------------------------------------------------------

#: Was ein Sehmodell annimmt. Alles andere wird gerendert statt durchgereicht.
_BILDTYPEN = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".webp": "image/webp"}


@dataclass(frozen=True)
class Seitenbild:
    daten: bytes
    mime: str
    #: „eingebettet" oder „gerendert" — steht später in der Herkunft.
    weg: str
    #: Um wie viel Grad (gegen den Uhrzeigersinn) :func:`aufrichten` die Seite
    #: gedreht hat. 0 heißt: lag schon aufrecht, oder es war nicht zu klären.
    drehung: int = 0

    def als_data_url(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.daten).decode('ascii')}"


#: Ab wie vielen Punkten je Zoll ein eingebettetes Bild als *die Seite* gilt.
#:
#: DER FALL, DER DIESE SCHWELLE ERZWUNGEN HAT (20.08.2026): Seite 1 des
#: RPA-Schlussberichts 2024 ist eine Vektorseite mit **einem** Briefkopf-Logo.
#: Die alte Regel („genau ein Bild = der Scan") schickte also das LOGO an das
#: Sehmodell, nicht die Seite — und bekam „Stadt Oldenburg | Rechnungsprüfungs-
#: amt" zurück, 62 Zeichen, die aussahen wie ein Ergebnis.
#:
#: Gemessen: Das Logo ist 528×195 px auf einer A4-Seite → **64 dpi** quer und
#: rund 17 dpi hoch. Die AWB-Scans sind 3507×2480 px auf derselben Fläche →
#: **300 dpi** in beiden Richtungen. Zwischen 64 und 300 ist viel Platz; 100
#: liegt weit genug von beidem entfernt, dass weder ein Logo durchrutscht noch
#: ein schlechter 150-dpi-Scan abgewiesen wird.
MIN_DPI = 100

#: Größer darf ein eingebettetes Bild nicht sein, sonst wird die Seite
#: gerendert statt durchgereicht.
#:
#: DER FALL (20.08.2026): Anlage 188884 trägt einen Scan von über 30 MB. Die
#: Gegenstelle wies ihn mit „413 — Downloaded image content cannot exceed
#: 30MB" ab, und die Anlage blieb als einzige von 227 ungelesen. Das Rendern
#: bei 200 dpi macht daraus ein paar hundert Kilobyte, ohne dass ein
#: Buchstabe verloren geht — die Vorlage hat ja ohnehin mehr Auflösung, als
#: ein Sehmodell nutzt.
#:
#: 20 MB und nicht 30: Base64 bläht die Daten um ein Drittel auf, und die
#: Grenze der Gegenstelle gilt für das, was dort ankommt.
MAX_BILD_BYTES = 20 * 1024 * 1024


def _deckt_die_seite(page, im) -> bool:
    """Ist dieses eingebettete Bild plausibel die ganze Seite?

    Ohne Pillow lässt sich die Pixelgröße nicht immer bestimmen; dann
    entscheidet die Textebene: Eine Seite mit lesbarem Text ist keine
    gescannte Seite, egal was für ein Bild darauf klebt.
    """
    try:
        breite_pt = float(page.mediabox.width)
        hoehe_pt = float(page.mediabox.height)
    except Exception:  # noqa: BLE001
        return False
    if not (breite_pt > 0 and hoehe_pt > 0):
        return False

    groesse = getattr(getattr(im, "image", None), "size", None)
    if groesse is None:
        # Kein Pillow: Die Textebene entscheidet. Ein echter Scan hat keine.
        try:
            return len((page.extract_text() or "").strip()) < MIN_SEITE
        except Exception:  # noqa: BLE001
            return False
    breite_px, hoehe_px = groesse
    return (breite_px / (breite_pt / 72.0) >= MIN_DPI
            and hoehe_px / (hoehe_pt / 72.0) >= MIN_DPI)


def seite_als_bild(page, dpi: int = 200) -> Seitenbild:
    """Eine PDF-Seite als Bild — ohne neue Abhängigkeit, wo es geht.

    Erster Weg: Trägt die Seite **genau ein** eingebettetes Bild, und deckt
    dieses Bild die Seite auch wirklich ab, dann IST es der Scan. Es geht
    unverändert weiter — keine Neukodierung, kein Qualitätsverlust, kein
    Renderer.

    Beide Bedingungen zählen. „Genau ein Bild" allein reichte nicht: Eine
    Vektorseite mit Briefkopf-Logo erfüllt das auch, und dann wandert das Logo
    ans Modell statt der Seite (s. ``MIN_DPI``).
    """
    try:
        bilder = list(getattr(page, "images", []))
    except Exception:  # noqa: BLE001 — eine kaputte Ressource ist kein Grund aufzugeben
        bilder = []
    if len(bilder) == 1:
        im = bilder[0]
        endung = os.path.splitext(getattr(im, "name", "") or "")[1].lower()
        mime = _BILDTYPEN.get(endung)
        if (mime and im.data and len(im.data) <= MAX_BILD_BYTES
                and _deckt_die_seite(page, im)):
            return Seitenbild(im.data, mime, "eingebettet")
    return _gerendert(page, dpi)


def _gerendert(page, dpi: int) -> Seitenbild:
    """Fallback für Vektorseiten. Braucht einen Renderer — bewusst optional.

    Fehlt er, bleibt die Seite **ungelesen**. Das ist die richtige Richtung:
    Eine Lücke ist im Haushalts-Bereich ein zulässiger Zustand, eine geratene
    Zahl nicht.

    Bevorzugt ``pypdfium2``: ein Wheel mit gebündeltem pdfium, keine
    Systemabhängigkeit, BSD/Apache. ``pymupdf`` geht auch, ist aber schwerer
    und AGPL — es steht nur als zweite Wahl da, weil manche Umgebung es schon
    mitbringt. Keines von beiden gehört in ``requirements.txt``: dieselbe
    Zurückhaltung wie bei `fastembed`.
    """
    # ERST den Renderer suchen, dann das Ein-Seiten-PDF bauen. Andersherum
    # bezahlt jede Seite den Umbau, bevor sie erfährt, dass niemand sie
    # rendern kann.
    renderer = None
    for name in ("pypdfium2", "pymupdf"):
        try:
            renderer = __import__(name)
            break
        except ImportError:
            continue
    if renderer is None:  # pragma: no cover — hängt an der Umgebung
        raise OcrFehler(
            "Diese Seite trägt kein seitenfüllendes Bild und müsste gerendert "
            "werden. Dafür fehlt ein Renderer (bewusst nicht in "
            "requirements.txt, wie fastembed): pip install pypdfium2")

    schreiber = pypdf.PdfWriter()
    schreiber.add_page(page)
    puffer = io.BytesIO()
    schreiber.write(puffer)
    roh = puffer.getvalue()

    # AUFLÖSUNG HALBIEREN, BIS ES PASST. Eine A4-Seite bei 200 dpi ist ein
    # paar hundert Kilobyte — ein Verkehrsplan im A0-Format aber nicht.
    #
    # DER FALL (20.08.2026): Anlage 188884 („Verkehrsregelung
    # Johann-Justus-Weg", 11 Seiten) scheiterte dreimal an „413 — Downloaded
    # image content cannot exceed 30MB". Beim ersten Mal hielt ich das
    # eingebettete Bild für die Ursache und deckelte es (`MAX_BILD_BYTES`) —
    # der 413 blieb. Es war die gerenderte Seite selbst: A0 bei 200 dpi sind
    # rund 6.600 × 9.400 Pixel.
    #
    # Halbiert wird höchstens dreimal (200 → 100 → 50 → 25 dpi). Darunter ist
    # nichts mehr zu lesen, und dann bleibt die Seite lieber ungelesen als
    # falsch gelesen.
    for versuch in range(4):
        aufloesung = dpi / (2 ** versuch)
        bild = _einmal_rendern(renderer, roh, aufloesung)
        if len(bild) <= MAX_BILD_BYTES or versuch == 3:
            if len(bild) > MAX_BILD_BYTES:
                raise OcrFehler(
                    f"Die Seite bleibt auch bei {aufloesung:.0f} dpi "
                    f"{len(bild) / 1e6:.1f} MB groß — vermutlich ein Plan im "
                    "Großformat. Ungelesen ist hier besser als unlesbar.")
            return Seitenbild(bild, "image/png", "gerendert")
    raise OcrFehler("unerreichbar")  # pragma: no cover


def _einmal_rendern(renderer, roh: bytes, dpi: float) -> bytes:
    """Eine Seite bei genau dieser Auflösung — als PNG-Bytes."""
    if renderer.__name__ == "pypdfium2":
        dok = renderer.PdfDocument(roh)
        try:
            bild = dok[0].render(scale=dpi / 72.0).to_pil()
            aus = io.BytesIO()
            bild.save(aus, format="PNG")
            return aus.getvalue()
        finally:
            dok.close()

    dok = renderer.open(stream=roh, filetype="pdf")
    try:
        return dok[0].get_pixmap(dpi=int(dpi)).tobytes("png")
    finally:
        dok.close()


# --------------------------------------------------------------------------
# Lage: seitlich liegende Seiten aufrichten
# --------------------------------------------------------------------------
#
# Zwei Schritte, weil jeder für sich gemessen nur das eine kann
# (17.10.2026, 200 Scanseiten aus sechs Dokumenten, Wahrheit am Bild):
#
# 1. ACHSE aus den Pixeln: Laufen die Zeilen waagerecht oder senkrecht?
#    Textzeilen machen das Tintenprofil quer zu ihnen feinkörnig (Zeile,
#    Lücke, Zeile); längs mitteln sich die Buchstaben weg. 200 von 200
#    richtig, kostenlos. Oben/unten können Pixel dagegen NICHT: Ziffern
#    haben alle Versalhöhe, das Mittelband fehlt — das beste Merkmal kam auf
#    Zahlentabellen auf 160 von 200.
# 2. RICHTUNG aus einem Vergleich: Dasselbe Bild in drei Drehungen (0°, 90°,
#    270°), und das Sehmodell sagt, welche aufrecht steht. 157 von 157
#    richtig, darunter 30 aufrechte Seiten, die es unverändert ließ. Nach der
#    Richtung FRAGEN taugt nicht: „Uhrzeigersinn oder gegen?" beantwortete
#    das Modell für jede der 127 Seiten gleich, egal wie sie lag.
#
# Die 0° stehen mit zur Wahl, damit eine falsch eingestufte Achse nichts
# verdreht. Gefragt wird nur bei senkrechter Achse — eine aufrechte Seite
# kostet nichts extra, eine seitliche rund 0,0008 $.

#: Die Frage für den Vergleich. Die Fassungen werden je Seite anders
#: gemischt: Eine Vorliebe für einen Buchstaben schlüge sonst durch.
LAGE_PROMPT = (
    "Hier sind drei Fassungen derselben gescannten Seite, unterschiedlich "
    "gedreht. In welcher Fassung steht der Text aufrecht und ist normal von "
    "links nach rechts lesbar? Antworte mit genau einem Buchstaben: A, B oder C.")

#: Die Kantenlänge, auf die das Bild für die Achse verkleinert wird — bei
#: dieser Auflösung gemessen. Kleiner verschwimmen die Zeilenlücken.
_ACHSE_PX = 2000
#: Fensterbreite der Glättung in Pixeln (bei ``_ACHSE_PX``): breiter als eine
#: Zeile, schmaler als eine Tabellenspalte.
_FENSTER = 41
#: Weniger Tinte als das gilt als leere Seite — sie wird nicht gedreht.
_MIN_TINTE = 0.001


def _feinenergie(profil) -> float:
    import numpy as np  # noqa: PLC0415 — nur wer aufrichtet, braucht es

    p = profil.astype(float)
    glatt = np.convolve(p, np.ones(_FENSTER) / _FENSTER, mode="same")
    return float(((p - glatt) ** 2).sum() / max(1.0, (p ** 2).sum()))


def zeilen_senkrecht(bild) -> bool:
    """Laufen die Textzeilen dieses PIL-Bildes senkrecht?"""
    import numpy as np  # noqa: PLC0415

    grau = bild.convert("L")
    grau.thumbnail((_ACHSE_PX, _ACHSE_PX))
    tinte = np.asarray(grau, dtype=np.float32) < 128
    if tinte.mean() < _MIN_TINTE:
        return False
    return _feinenergie(tinte.sum(0)) > _feinenergie(tinte.sum(1))


def _klein(bild) -> str:
    kopie = bild.copy()
    kopie.thumbnail((900, 900))
    puffer = io.BytesIO()
    kopie.save(puffer, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(puffer.getvalue()).decode("ascii")


def aufrecht_waehlen(bild, model: str = MODEL) -> int | None:
    """Welche Drehung (0, 90 oder 270 Grad gegen den Uhrzeigersinn) stellt das
    Bild aufrecht? ``None``, wenn die Antwort keine der drei ist."""
    from kern.llm import chat_complete  # noqa: PLC0415

    # Reihenfolge aus dem Bildinhalt: je Seite anders, aber wiederholbar.
    reihen = ((0, 90, 270), (90, 270, 0), (270, 0, 90))
    kandidaten = reihen[zlib.crc32(bild.tobytes()[:65536]) % 3]
    inhalt: list[dict] = [{"type": "text", "text": LAGE_PROMPT}]
    for name, grad in zip("ABC", kandidaten, strict=True):
        inhalt += [{"type": "text", "text": f"Fassung {name}:"},
                   {"type": "image_url",
                    "image_url": {"url": _klein(bild.rotate(grad, expand=True))}}]
    antwort = chat_complete(model=model, temperature=TEMPERATUR,
                            messages=[{"role": "user", "content": inhalt}],
                            _feature="attachment_ocr")
    buchstabe = (antwort.choices[0].message.content or "").strip().upper()[:1]
    return dict(zip("ABC", kandidaten, strict=True)).get(buchstabe)


def aufrichten(bild: Seitenbild, model: str = MODEL) -> Seitenbild:
    """Eine seitlich liegende Seite aufrecht stellen — sonst unverändert.

    Unverändert heißt auch: Wo etwas fehlt (Pillow, numpy, ein lesbares
    Bild, eine eindeutige Antwort), geht die Seite so weiter wie bis 10/2026.
    Das ist kein stiller Fehler, sondern der alte, gemessene Zustand."""
    try:
        from PIL import Image  # noqa: PLC0415

        pil = Image.open(io.BytesIO(bild.daten))
        pil.load()
        if not zeilen_senkrecht(pil):
            return bild
        grad = aufrecht_waehlen(pil, model=model)
    except Exception:  # noqa: BLE001 — Aufrichten ist eine Verbesserung, keine Bedingung
        return bild
    if not grad:
        return bild
    gedreht = pil.convert("RGB").rotate(grad, expand=True)
    puffer = io.BytesIO()
    gedreht.save(puffer, "JPEG", quality=90)
    return Seitenbild(puffer.getvalue(), "image/jpeg", bild.weg, drehung=grad)


def seitliche_seiten(daten: bytes, max_seiten: int | None = None) -> list[int]:
    """Die Seitennummern eines PDF, deren Zeilen senkrecht laufen — nur aus
    den Pixeln, ohne Modellaufruf. Sagt vorher, ob sich Aufrichten lohnt."""
    from PIL import Image  # noqa: PLC0415

    leser = pypdf.PdfReader(io.BytesIO(daten))
    seiten = leser.pages if max_seiten is None else leser.pages[:max_seiten]
    aus: list[int] = []
    for nr, page in enumerate(seiten, start=1):
        try:
            bild = Image.open(io.BytesIO(seite_als_bild(page).daten))
            if zeilen_senkrecht(bild):
                aus.append(nr)
        except Exception:  # noqa: BLE001 — eine unlesbare Seite ist keine seitliche
            continue
    return aus


# --------------------------------------------------------------------------
# Bild → Text
# --------------------------------------------------------------------------

#: Drei der vier Anweisungen stehen hier, weil sie an echten Läufen
#: fehlgeschlagen sind, nicht weil sie gut klingen:
#:
#: - **Nichts auslassen.** Ein Modell ließ auf der gedrehten Seite eine
#:   Summenzeile ersatzlos weg. Die restlichen 18 Proben gingen auf — ein
#:   Fehler, den eine Rechenprobe prinzipiell NICHT findet, weil sie dann
#:   einfach weniger prüft.
#: - **Kopf- und Fußzeilen mitnehmen.** Allzweck-Sehmodelle halten laufende
#:   Kopfzeilen für Rauschen und löschen sie (olmOCR-Bench misst dafür 20 bis
#:   37 von 100, während Spezial-Parser bei 89 bis 97 liegen). In genau diesen
#:   Zeilen steht aber „in TEUR" — die Größenordnung jeder Zahl darunter.
#: - **Nicht umrechnen.** Deutsche Beträge bleiben deutsch.
PROMPT = """Gib den vollständigen Inhalt dieser Seite als Text wieder.

Regeln:
1. NICHTS AUSLASSEN. Jede Zeile, jede Zahl, jede Zwischen- und Summenzeile —
   auch wenn eine Zeile leer wirkt oder sich wiederholt. Lieber eine Zeile zu
   viel als eine zu wenig.
2. Kopfzeilen, Fußzeilen, Seitenzahlen, Spaltenüberschriften und Einheiten
   ("in TEUR", "in Mio. EUR", "Angaben in Euro") gehören dazu. Sie sind kein
   Rauschen — sie sagen, was die Zahlen darunter bedeuten.
3. Zahlen genau so schreiben, wie sie dastehen: 1.234.567,89 bleibt
   1.234.567,89. Nicht umrechnen, nicht runden, keine Trennzeichen ändern,
   keine Vorzeichen ergänzen oder weglassen.
4. Tabellen als Text mit Tabulatoren zwischen den Spalten, eine Zeile je
   Tabellenzeile. Die Spaltenreihenfolge bleibt wie im Bild.
5. Was du nicht sicher entziffern kannst, schreibst du als [unleserlich].
   Nicht raten, nicht ergänzen, nicht sinnvoll machen.
6. Keine Einleitung, keine Zusammenfassung, kein Kommentar. Nur der Inhalt."""


def lies_seite(bild: Seitenbild, model: str = MODEL) -> str:
    """Eine Seite lesen. Genau ein Modellaufruf, über ``kern.llm``.

    Der Umweg über ``chat_complete`` ist kein Zufall: Dort hängen das
    Anbieter-Routing (DSGVO), die Wiederholung bei 429/5xx und die
    Kostenerfassung fürs Admin-Panel dran. Ein direkter Aufruf verlöre alle
    drei auf einmal.
    """
    from kern.llm import chat_complete  # noqa: PLC0415 — hält den Importbaum flach

    answer = chat_complete(
        model=model,
        temperature=TEMPERATUR,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": bild.als_data_url()}},
        ]}],
        _feature="attachment_ocr",
    )
    text = (answer.choices[0].message.content or "").strip()
    return text[:MAX_SEITE]


# --------------------------------------------------------------------------
# Zweitleser: Zeilenversatz finden
# --------------------------------------------------------------------------
#
# DER FEHLER, DEN KEINE SUMMENPROBE SIEHT: Das Modell liest alle Beträge
# richtig, ordnet sie aber eine Zeile verschoben den Beschriftungen zu. Die
# Summe geht auf, der Posten ist falsch. Gefunden am Konzern 2013 (188333),
# AWB 2020 (208461) und AWB-Prüfbericht 2018 (206874) — seitlich wie aufrecht.
#
# Gemessen (17.10.2026): Gemini Flash Lite und Sonnet 4.6 auf denselben zehn
# Seiten. Auf allen sechs Seiten mit bekanntem Versatz waren sie sich uneinig
# (3, 5 und 10 Zeilen), auf allen vier sauberen Seiten und den drei richtig
# gelesenen einig (0). Verglichen wird über den BETRAGSSATZ einer Zeile: Steht
# dieselbe Zahlenfolge in beiden Lesungen bei verschiedenen Beschriftungen,
# hat eines der Modelle die Zeile verschoben. Welches, sagt der Vergleich
# nicht — das ist ein Prüffall, kein Mehrheitsentscheid.

#: Ein Betrag, wie ihn diese Dokumente drucken: mit Tausenderpunkt oder mit
#: Nachkommastellen. Jahreszahlen, Seitenzahlen und Postennummern sind keiner.
_BETRAG_ZEILE = re.compile(
    r"(?<![\d.,])(?:-\s?)?\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?(?!\d)"
    r"|(?<![\d.,])-?\d+,\d{2}(?!\d)")


def _beschriftung(text: str) -> str:
    return re.sub(r"[^a-zäöüß]", "", text.lower())


def _betragszeilen(text: str) -> dict[tuple, list[tuple[str, str]]]:
    """``{Betragssatz: [(eigene Beschriftung, volle Beschriftung), …]}`` je
    Zeile mit mindestens einem Betrag.

    Die Beschriftung ist auf Buchstaben eingedampft — Tabs, Markdown und
    Leerzeichen unterscheiden zwei Modelle, nicht der Inhalt. Die VOLLE
    Beschriftung nimmt die Zeilen ohne Betrag davor mit: Ein umbrochener
    Posten („1. entgeltlich erworbene Konzessionen, / … Lizenzen 41.265,00")
    steht beim einen Modell mit der ersten, beim anderen mit der letzten Zeile
    vor dem Betrag."""
    aus: dict[tuple, list[tuple[str, str]]] = {}
    offen = ""
    for zeile in (text or "").replace("*", "").replace("|", "\t").splitlines():
        betraege = tuple(b.replace(" ", "") for b in _BETRAG_ZEILE.findall(zeile))
        if not betraege:
            offen = (offen + _beschriftung(zeile))[-120:] if _beschriftung(zeile) else ""
            continue
        erster = _BETRAG_ZEILE.search(zeile)
        eigen = _beschriftung(zeile[:erster.start() if erster else 0])
        aus.setdefault(betraege, []).append((eigen, offen + eigen))
        offen = ""
    return aus


def _gleicher_posten(x: tuple[str, str], y: tuple[str, str]) -> bool:
    """Meinen zwei Zuordnungen denselben Posten?

    Ja, wenn eine Seite gar keine Beschriftung hat (Summenzeile), wenn die
    eigene Zeile der einen in der vollen Beschriftung der anderen steht
    (Umbruch), oder wenn beide auf mindestens 12 Buchstaben gleich enden —
    „B. Umlaufvermögen … erhaltene Anzahlungen auf Bestellungen" und „I.
    Vorräte … erhaltene Anzahlungen auf Bestellungen" sind derselbe Posten
    mit verschiedener Überschrift davor."""
    (eigen_a, voll_a), (eigen_b, voll_b) = x, y
    if not eigen_a or not eigen_b:
        return True
    gemeinsames_ende = len(os.path.commonprefix([eigen_a[::-1], eigen_b[::-1]]))
    return eigen_a in voll_b or eigen_b in voll_a or gemeinsames_ende >= 12


#: Bilanzen mit Aktiva und Passiva NEBENEINANDER lesen beide Modelle als
#: verschmolzene Zeilen — der Betrag rechts landet hinter einer Beschriftung
#: links, bei jedem Modell hinter einer anderen. Gemessen an fünf Bilanzen des
#: Bestands (17.10.2026): jede war „strittig", keine Zuordnung dort war eine,
#: die ein Parser liest (die Bilanz-Ingests nehmen die Summe, die auf beiden
#: Seiten stehen muss). Solche Seiten werden nicht verglichen.
_NEBENEINANDER = re.compile(r"a\s*k\s*t\s*i\s*v\s*a[\s\S]*p\s*a\s*s\s*s\s*i\s*v\s*a", re.IGNORECASE)


def nebeneinander(text: str) -> bool:
    """Steht auf dieser Seite eine Bilanz mit beiden Seiten nebeneinander?"""
    return bool(_NEBENEINANDER.search(text or ""))


@dataclass(frozen=True)
class Abgleich:
    """Was zwei Lesungen derselben Seite über einander verraten."""
    #: Betragssätze, die beide Lesungen je genau einmal kennen — nur die sind
    #: vergleichbar („0,00" steht auf zehn Zeilen und sagt nichts).
    gemeinsam: int
    #: Davon einem anderen Posten zugeordnet — der Zeilenversatz.
    versatz: int
    #: Betragssätze, die nur eine Lesung kennt (Ziffernfehler, Umbruch).
    einseitig: int
    #: Bis zu drei Beispiele ``(Beträge, Beschriftung A, Beschriftung B)``.
    beispiele: tuple = ()
    #: Bilanz mit beiden Seiten nebeneinander — nicht verglichen.
    nicht_vergleichbar: bool = False

    @property
    def strittig(self) -> bool:
        return self.versatz > 0


def abgleich(text_a: str, text_b: str) -> Abgleich:
    """Zwei Lesungen derselben Seite gegeneinander halten."""
    if nebeneinander(text_a) or nebeneinander(text_b):
        return Abgleich(gemeinsam=0, versatz=0, einseitig=0, nicht_vergleichbar=True)
    a, b = _betragszeilen(text_a), _betragszeilen(text_b)
    vergleichbar = sorted(k for k in a.keys() & b.keys()
                          if len(a[k]) == 1 and len(b[k]) == 1)
    versetzt = [k for k in vergleichbar if not _gleicher_posten(a[k][0], b[k][0])]
    return Abgleich(
        gemeinsam=len(vergleichbar), versatz=len(versetzt),
        einseitig=len(a.keys() ^ b.keys()),
        beispiele=tuple((k, a[k][0][0], b[k][0][0]) for k in versetzt[:3]))


def betragszeilen_anzahl(text: str) -> int:
    return len(_betragszeilen(text))


# --------------------------------------------------------------------------
# Was der Text über sich selbst verrät
# --------------------------------------------------------------------------

#: „in TEUR" in einer Kopfzeile setzt die Größenordnung jeder Zahl darunter.
#:
#: WARUM DAS HIER STEHT UND NICHT NUR IM PROMPT: Die Spaltenprobe des
#: Haushalts-Bereichs (`wirtschaftsplan_tabelle.py`) ist **skaleninvariant** —
#: eine Spalte, die durchgängig um den Faktor 1.000 danebenliegt, geht sauber
#: auf. Das ist der einzige bekannte Fehlermodus, den `TOLERANZ_EUR` prinzipiell
#: nicht sehen kann. Wer aus OCR-Text Zahlen speichert, muss die Einheit also
#: eigens prüfen; dieses Muster ist die Fundstelle dafür.
_SKALA = re.compile(
    r"\bin\s+(T\s?(?:EUR|€)|Tsd\.?\s*(?:EUR|€)?|Tausend|Mio\.?\s*(?:EUR|€)?|"
    r"Millionen|Mrd\.?\s*(?:EUR|€)?)", re.IGNORECASE)


def skalenhinweise(text: str) -> list[str]:
    """Alle Einheiten-Angaben im Text, in Fundreihenfolge, ohne Dubletten."""
    aus: list[str] = []
    for treffer in _SKALA.finditer(text or ""):
        wort = " ".join(treffer.group(0).split())
        if wort.lower() not in {a.lower() for a in aus}:
            aus.append(wort)
    return aus


@dataclass(frozen=True)
class Lesung:
    """Was ein OCR-Lauf über ein Dokument weiß."""
    text: str
    seiten: int
    #: Seiten, die Text geliefert haben. Weniger als ``seiten`` ist kein
    #: Fehler (leere Rückseiten), aber eine Zahl, die im Log stehen muss.
    gelesen: int
    #: Seiten, die weder eingebettet noch gerendert werden konnten.
    uebersprungen: int
    skalen: tuple[str, ...]
    modell: str
    weg: str
    #: Seiten, die vor dem Lesen aufgerichtet wurden (:func:`aufrichten`).
    gedreht: int = 0
    #: Seiten, auf denen Erst- und Zweitleser Zeilen verschieden zuordnen —
    #: leer, wenn es keinen Zweitleser gab oder beide einig waren.
    strittig: tuple[int, ...] = ()
    #: Das Modell des Zweitlesers, wenn einer mitlas.
    zweitleser: str | None = None
    #: Seiten, die der Zweitleser gelesen hat (nur die mit Zahlentabellen).
    zweit_gelesen: int = 0

    @property
    def vollstaendig(self) -> bool:
        return self.uebersprungen == 0


def lies_pdf(daten: bytes, model: str = MODEL, max_seiten: int | None = None,
             dpi: int = 200, aufrichten_an: bool = True,
             zweitleser: str | None = None) -> Lesung:
    """Ein ganzes PDF lesen, Seite für Seite.

    Der Vollständigkeitszähler ist Absicht: Eine fehlende Seite lässt jede
    nachgelagerte Rechenprobe *weniger* prüfen, nicht scheitern. Ohne diese
    Zahl sähe ein halb gelesenes Dokument aus wie ein ganz gelesenes.
    """
    leser = pypdf.PdfReader(io.BytesIO(daten))
    seiten = leser.pages if max_seiten is None else leser.pages[:max_seiten]
    teile: list[str] = []
    gelesen = uebersprungen = gedreht = zweit_gelesen = 0
    strittig: list[int] = []
    wege: set[str] = set()

    for nr, page in enumerate(seiten, start=1):
        try:
            bild = seite_als_bild(page, dpi=dpi)
        except OcrFehler:
            uebersprungen += 1
            teile.append(PLATZHALTER.format(nr=nr))
            continue
        if aufrichten_an:
            bild = aufrichten(bild)
            gedreht += 1 if bild.drehung else 0
        wege.add(bild.weg)
        text = lies_seite(bild, model=model)
        if len(text) >= MIN_SEITE:
            gelesen += 1
        teile.append(text)
        if (zweitleser and betragszeilen_anzahl(text) >= ZWEIT_AB_ZEILEN
                and not nebeneinander(text)):
            zweit_gelesen += 1
            if abgleich(text, lies_seite(bild, model=zweitleser)).strittig:
                strittig.append(nr)

    ganz = "\n\n".join(teile).strip()
    return Lesung(
        text=ganz, seiten=len(seiten), gelesen=gelesen,
        uebersprungen=uebersprungen, skalen=tuple(skalenhinweise(ganz)),
        modell=model, weg="+".join(sorted(wege)) or "keiner", gedreht=gedreht,
        strittig=tuple(strittig), zweitleser=zweitleser, zweit_gelesen=zweit_gelesen,
    )
