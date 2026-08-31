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

**Die Lage-Metadaten lügen.** Von drei AWB-Jahrgängen tragen zwei ``/Rotate``
passend zum Inhalt, einer nicht: 208461 hat eine hochkant-MediaBox, das Bild
darin liegt aber quer. Wer ``/Rotate`` folgt, dreht bei zwei von drei Jahrgängen
falsch. Wir folgen ihm gar nicht — das eingebettete Bild geht so, wie es
gescannt wurde, an das Modell. Auf der um 90° liegenden 200-dpi-Seite gingen
alle 24 Rechenproben auf; die Modelle kommen mit der Drehung zurecht, unsere
Metadaten nicht.

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
3. Zahlen exact so schreiben, wie sie dastehen: 1.234.567,89 bleibt
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

    antwort = chat_complete(
        model=model,
        temperature=TEMPERATUR,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": bild.als_data_url()}},
        ]}],
        _feature="anlagen_ocr",
    )
    text = (antwort.choices[0].message.content or "").strip()
    return text[:MAX_SEITE]


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

    @property
    def vollstaendig(self) -> bool:
        return self.uebersprungen == 0


def lies_pdf(daten: bytes, model: str = MODEL, max_seiten: int | None = None,
             dpi: int = 200) -> Lesung:
    """Ein ganzes PDF lesen, Seite für Seite.

    Der Vollständigkeitszähler ist Absicht: Eine fehlende Seite lässt jede
    nachgelagerte Rechenprobe *weniger* prüfen, nicht scheitern. Ohne diese
    Zahl sähe ein halb gelesenes Dokument aus wie ein ganz gelesenes.
    """
    leser = pypdf.PdfReader(io.BytesIO(daten))
    seiten = leser.pages if max_seiten is None else leser.pages[:max_seiten]
    teile: list[str] = []
    gelesen = uebersprungen = 0
    wege: set[str] = set()

    for nr, page in enumerate(seiten, start=1):
        try:
            bild = seite_als_bild(page, dpi=dpi)
        except OcrFehler:
            uebersprungen += 1
            teile.append(PLATZHALTER.format(nr=nr))
            continue
        wege.add(bild.weg)
        text = lies_seite(bild, model=model)
        if len(text) >= MIN_SEITE:
            gelesen += 1
        teile.append(text)

    ganz = "\n\n".join(teile).strip()
    return Lesung(
        text=ganz, seiten=len(seiten), gelesen=gelesen,
        uebersprungen=uebersprungen, skalen=tuple(skalenhinweise(ganz)),
        modell=model, weg="+".join(sorted(wege)) or "keiner",
    )
