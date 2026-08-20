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


def seite_als_bild(seite, dpi: int = 200) -> Seitenbild:
    """Eine PDF-Seite als Bild — ohne neue Abhängigkeit, wo es geht.

    Erster Weg: Trägt die Seite **genau ein** eingebettetes Bild, ist das der
    Scan selbst. Es geht unverändert weiter — keine Neukodierung, kein
    Qualitätsverlust, kein Renderer.

    Bewusst nur bei *genau einem* Bild: Eine Seite mit Briefkopf-Logo *und*
    Scan trägt zwei, und dann ist nicht entscheidbar, welches die Seite ist.
    Solche Seiten werden gerendert.
    """
    try:
        bilder = list(getattr(seite, "images", []))
    except Exception:  # noqa: BLE001 — eine kaputte Ressource ist kein Grund aufzugeben
        bilder = []
    if len(bilder) == 1:
        im = bilder[0]
        endung = os.path.splitext(getattr(im, "name", "") or "")[1].lower()
        mime = _BILDTYPEN.get(endung)
        if mime and im.data:
            return Seitenbild(im.data, mime, "eingebettet")
    return _gerendert(seite, dpi)


def _gerendert(seite, dpi: int) -> Seitenbild:
    """Fallback für Vektorseiten. Braucht PyMuPDF — bewusst optional.

    Fehlt es, bleibt die Seite **ungelesen**. Das ist die richtige Richtung:
    Eine Lücke ist im Haushalts-Bereich ein zulässiger Zustand, eine geratene
    Zahl nicht.
    """
    try:
        import pymupdf  # noqa: PLC0415 — optional, nur für Vektorseiten
    except ImportError as exc:  # pragma: no cover — hängt an der Umgebung
        raise OcrFehler(
            "Diese Seite trägt kein einzelnes eingebettetes Bild und müsste "
            "gerendert werden. Dafür fehlt PyMuPDF (bewusst nicht in "
            "requirements.txt, wie fastembed): pip install pymupdf"
        ) from exc

    # Ein Ein-Seiten-PDF bauen und rendern — `seite` ist ein pypdf-Objekt,
    # pymupdf kennt es nicht.
    schreiber = pypdf.PdfWriter()
    schreiber.add_page(seite)
    puffer = io.BytesIO()
    schreiber.write(puffer)
    dok = pymupdf.open(stream=puffer.getvalue(), filetype="pdf")
    try:
        pix = dok[0].get_pixmap(dpi=dpi)
        return Seitenbild(pix.tobytes("png"), "image/png", "gerendert")
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

    for nr, seite in enumerate(seiten, start=1):
        try:
            bild = seite_als_bild(seite, dpi=dpi)
        except OcrFehler:
            uebersprungen += 1
            teile.append(f"[Seite {nr}: nicht lesbar gemacht]")
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
