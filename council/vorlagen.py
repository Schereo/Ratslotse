"""Fetch and store Vorlagen (Beschlussvorlagen, Anträge, Berichte) as full text.

A Vorlage is the document a decision is ABOUT: it carries the Sachverhalt and the
Begründung — the *why* behind a Beschluss, which the protocol only records the
outcome of. The vo0050 page itself holds only metadata (Betreff, Nr., Art); the
content lives in the attached "Vorlage" PDF, so we download that and extract its
text (``pypdf``). No LLM here — ingestion is pure network + parsing; consumers
(Q&A context, FTS, decision pages) work on the raw text.

Anlagen: every further document on the page is recorded with label + link. In
Oldenburg the ORIGINAL fraction motions live here ("Antrag der SPD-Fraktion vom
…") — there is no Vorlagen-Art "Antrag". Anlagen whose label looks like a motion
also get their PDF text ingested plus the submitting parties (Antragsteller,
recognised via council.parties); maps/balance sheets stay link-only.
"""
from __future__ import annotations

import io
import re

import requests
import pypdf
from bs4 import BeautifulSoup

from council.parties import parties_in_text

BASE = "https://buergerinfo.oldenburg.de"

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"

# Section headings that start the substantive part of a Vorlage. A heading only
# counts at the start of a line, either standalone or directly followed by ":" —
# the bare words also appear mid-sentence ("… in der Begründung des Antrages …").
# Two tiers: Sachverhalt/Begründung/Anlass/Bericht carry the actual reasoning;
# "Beschlussvorschlag" is only a fallback because it usually just repeats what
# the decision row already shows — and it appears BEFORE the Sachverhalt.
_HEADING = r"Sachverhalt(?:\s+und\s+Begründung)?|Sach-\s*und\s*Rechtslage|Begründung|Ausgangslage|Anlass|Bericht"
_SECTION_RE = re.compile(rf"^(?:{_HEADING})(?::|\s*$)")
_FALLBACK_SECTION_RE = re.compile(r"^Beschlussvorschlag(?::|\s*$)")
# Per-page boilerplate that pypdf interleaves with the content.
_NOISE_RE = re.compile(
    r"^(Seite:?\s*\d+\s*/\s*\d+.*|Ausdruck vom:.*|Vorlagen?-?\s*Nr\.?:.*|\s*-\s*\d+\s*-\s*)$"
)
# Der Verwaltungs-Schwanz am Ende jeder Vorlage. Die Anlagen-Liste steht auf der
# Beschluss-Seite schon als „Dokumente & Anlagen"; hinter der Überschrift folgt
# außerdem oft der ANGEHÄNGTE Anlagentext, der mit dem Sachverhalt nichts mehr
# zu tun hat. Die Unterschrift setzt das PDF-Textlayer gesperrt
# („D r . S v e n U h r h a n") — als Fließtext gelesen reiner Buchstabensalat.
_ANLAGEN_RE = re.compile(r"^Anlagen?\s*:?\s*$")
#: Der „Auswirkungen"-Block — auf der Beschluss-Seite stehen seine beiden
#: Hälften schon als eigene Karten („Was kostet das?", „Klima-Check"). Bis
#: #1211 blieb er trotzdem im Auszug, weil die Regex-Ernte ihn nur für 64 von
#: 5079 Vorlagen gefüllt hatte — ein Schnitt hätte die Angabe damals ersatzlos
#: verloren. Der Schnitt hängt deshalb bis heute nicht am Vorhandensein der
#: ÜBERSCHRIFT, sondern am ``ohne_auswirkungen``-Schalter, den der Aufrufer nur
#: setzt, wenn die Karten den Block wirklich zeigen (s. ``excerpt``).
_AUSWIRKUNGEN_RE = re.compile(r"^(?:Finanzielle\s+)?Auswirkungen\s*:?\s*$")
#: Woran der Block endet. „Klimarelevante Auswirkungen:" führt die alte Form
#: als EIGENEN Abschnitt, und den erntet niemand — er beendet den Finanzblock
#: also, statt mit ihm zu verschwinden.
_AUSWIRKUNGEN_ENDE_RE = re.compile(
    r"^(?:Finanzielle|Klimarelevante)?\s*Auswirkungen\s*:?\s*$")
#: Karten gibt es nur für „a) Finanzen" und „b) Klima". Viele Vorlagen führen
#: darunter noch „c) Weitere" und „d) Abwägung und Bewertung der Verwaltung" —
#: 696 davon mit echtem Inhalt, den sonst nichts auf der Seite zeigt. Der
#: Schnitt endet deshalb HIER und nicht am Ende des Blocks. Trifft das Muster
#: versehentlich einen Listenpunkt im Klima-Text, bleibt nur etwas mehr stehen
#: als nötig — der Fehler zeigt in die harmlose Richtung.
#: „Abwägung und Bewertung der Verwaltung:" führen manche Vorlagen als „d)",
#: andere ohne Buchstaben — die zweite Form fiel sonst unter den Schnitt.
_AUSWIRKUNGEN_REST_RE = re.compile(r"^[c-z]\)|^Abwägung\s+und\s+Bewertung")
#: Der Briefschluss. In der ALTEN Form steht der Block ganz am Ende des
#: Anschreibens — ohne diese Marke lief der Schnitt bis ans Textende und
#: verschluckte Unterschrift samt angehängtem Anlagentext gleich mit. Das wäre
#: zwar meist Verwaltungs-Schwanz, aber es ist nicht der Block, um den es hier
#: geht: Der Schnitt soll das Doppelte entfernen, nicht nebenbei aufräumen.
_SCHLUSSZEILE_RE = re.compile(
    r"^(?:In\s+Vertretung|Im\s+Auftrage?|gez\.)\b|^(?:\S\s){4,}\S\s*$")
#: Die beiden Unterpunkte. Je eine Karte, also je einzeln geschnitten: Erntet
#: die Regex nur eine der beiden Hälften (etwa weil „a) Finanzen:" einen
#: Doppelpunkt trägt oder der Text auf derselben Zeile weiterläuft), darf die
#: ANDERE nicht mit verschwinden — sie steht dann auf keiner Karte.
#: Das doppelte „a) a) Finanzen" gibt es im Bestand wirklich.
_A_FINANZEN_RE = re.compile(r"^a\)\s*(?:a\)\s*)?Finanzen")
_B_KLIMA_RE = re.compile(r"^b\)\s*(?:b\)\s*)?Klima")
#: Mindest-Substanz vor dem Anlagen-Schnitt: In einigen Vorlagen steht die
#: Überschrift schon im Kopf, und ein leerer Auszug wäre schlimmer als ein
#: langer.
_MIN_BODY_CHARS = 300
# „In Vertretung" nur mit gesperrtem Namen dahinter — „Im Auftrag der
# Unfallforschung der Versicherer …" ist ein Satzanfang, keine Unterschrift.
_SIGNATURE_RE = re.compile(
    r"\s*(?:In\s+Vertretung|Im\s+Auftrage?|gez\.)\s+(?:\S\s){2,}\S\s*$"
)
#: Der gesperrte Name allein — manche Vorlagen unterschreiben ohne Formel.
_SPACED_NAME_RE = re.compile(r"\s(?:\S\s){5,}\S\s*$")


def parse_vorlage_page(html: str) -> dict | None:
    """Extract metadata, the main PDF link and the Anlagen list from a vo0050 page.

    Returns ``{template_number, title, art, document_id, document_url, anlagen}`` —
    ``anlagen`` is ``[{document_id, url, label}]`` for every further document
    (PDF fields ``None`` when the page has no public "Vorlage" document) — or
    ``None`` when the page is no Vorlage at all (invalid kvonr)."""
    soup = BeautifulSoup(html, "html.parser")
    title_cell = soup.find(class_="vobetr")
    nr_cell = soup.find(class_="voname")
    if title_cell is None and nr_cell is None:
        return None
    art_cell = soup.find(class_="vovaname")

    # Every document renders two links (icon + label). Collect per document_id;
    # the non-empty text is the label. Label "Vorlage" = the main document.
    docs: dict[int, dict] = {}
    for a in soup.find_all("a", href=True):
        if "getfile.php" not in a["href"]:
            continue
        href = a["href"] if a["href"].startswith("http") else f"{BASE}/{a['href'].lstrip('/')}"
        m = re.search(r"id=(\d+)", href)
        if not m:
            continue
        doc_id = int(m.group(1))
        entry = docs.setdefault(doc_id, {"document_id": doc_id, "url": href, "label": ""})
        text = a.get_text(" ", strip=True)
        if text and not entry["label"]:
            entry["label"] = text

    document_id = document_url = None
    anlagen: list[dict] = []
    for entry in docs.values():
        if entry["label"] == "Vorlage" and document_id is None:
            document_id, document_url = entry["document_id"], entry["url"]
        else:
            anlagen.append(entry)

    return {
        "template_number": nr_cell.get_text(" ", strip=True) if nr_cell else "",
        "title": title_cell.get_text(" ", strip=True) if title_cell else "",
        "kind": art_cell.get_text(" ", strip=True) if art_cell else "",
        "document_id": document_id,
        "document_url": document_url,
        "anlagen": anlagen,
    }


def _pdf_text(url: str) -> tuple[str, int]:
    """Download a PDF and return (text, n_pages). Mirrors protocols.extract_pdf_text
    but keeps this module free of the LLM import chain."""
    r = _session.get(url, timeout=45)
    r.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    return text, len(reader.pages)


# Anlagen whose label smells like a fraction motion get their text ingested.
# Broad on purpose ("Antrag auf Aufhebung …" from an investor also matches) —
# the Antragsteller party filter keeps the statistics clean.
_ANTRAG_LABEL_RE = re.compile(r"\b(antr[aä]g|anfrage)", re.IGNORECASE)


def _build_anlage_rows(anlagen: list[dict], skip_document_ids: frozenset = frozenset()) -> list[dict]:
    """Rows for ``CouncilStore.save_anlagen``: motion-like Anlagen get PDF text +
    Antragsteller (from the label, else the first PDF page); everything else is
    recorded link-only (status ``listed``). Already-known document_ids are kept
    link-only so daily re-scans don't re-download their PDFs."""
    rows: list[dict] = []
    for a in anlagen:
        row = {**a, "is_motion": 0, "applicants": [], "raw_text": "", "n_pages": 0,
               "status": "listed"}
        if _ANTRAG_LABEL_RE.search(a["label"] or "") and a["document_id"] not in skip_document_ids:
            row["is_motion"] = 1
            try:
                text, n_pages = _pdf_text(a["url"])
                row["raw_text"], row["n_pages"] = text, n_pages
                row["status"] = "ok" if len(text.strip()) >= 50 else "empty"
            except Exception:  # noqa: BLE001 — ein kaputtes Anlagen-PDF kippt nicht den ganzen kvonr
                row["status"] = "failed"
            # 4000 statt 1500 Zeichen: bei Anträgen mit langem Briefkopf stehen
            # die Fraktionen erst nach der Anrede — 1500 ließ 37 % leer.
            row["applicants"] = parties_in_text(a["label"]) or parties_in_text(row["raw_text"][:4000])
        rows.append(row)
    return rows


def fetch_vorlage(kvonr: int) -> dict | None:
    """Full ingestion for one Vorlage: metadata from vo0050, text from the main
    PDF, plus the Anlagen rows (motions with text, the rest link-only) under
    ``row["anlagen"]``.

    ``status`` is one of ``ok`` (text extracted), ``empty`` (PDF has no text
    layer — scanned) or ``no_pdf`` (no public document). ``None`` for an invalid
    kvonr. Network errors on the MAIN document propagate — the caller decides
    between retry and mark-failed."""
    r = _session.get(f"{BASE}/vo0050.php", params={"__kvonr": kvonr}, timeout=20)
    r.raise_for_status()
    meta = parse_vorlage_page(r.text)
    if meta is None:
        return None
    anlagen = _build_anlage_rows(meta.pop("anlagen"))
    row = {"kvonr": kvonr, **meta, "raw_text": "", "n_pages": 0, "status": "no_pdf",
           "anlagen": anlagen}
    if meta["document_url"]:
        text, n_pages = _pdf_text(meta["document_url"])
        row["raw_text"] = text
        row["n_pages"] = n_pages
        row["status"] = "ok" if len(text.strip()) >= 50 else "empty"
    return row


def fetch_anlagen(kvonr: int, skip_document_ids: frozenset = frozenset()) -> list[dict] | None:
    """Anlagen-only pass for an already-ingested Vorlage (historical catch-up and
    the daily re-scan of recent sessions — Änderungsanträge often appear on the
    page days after the Vorlage itself). Does NOT touch the main Vorlage PDF.
    ``None`` for an invalid kvonr; network errors on the page propagate."""
    r = _session.get(f"{BASE}/vo0050.php", params={"__kvonr": kvonr}, timeout=20)
    r.raise_for_status()
    meta = parse_vorlage_page(r.text)
    if meta is None:
        return None
    return _build_anlage_rows(meta["anlagen"], skip_document_ids)


def _entzeilen(lines: list[str]) -> list[str]:
    """PDF-Zeilenumbrüche zu Fließtext joinen: Das Text-Layer bricht Zeilen hart
    nach Satzbreite um, was auf der Beschluss-Seite als wilde Umbrüche mitten im
    Satz landete. Kurze Label-Zeilen („Anlass:") und Aufzählungspunkte bleiben
    eigene Zeilen, Silbentrennungen am Zeilenende werden zusammengezogen."""
    out: list[str] = []
    for ln in lines:
        ist_label = ln.endswith(":") and len(ln) <= 40
        # Aufzählungszeichen mit Text — und allein stehende Striche (PDF-
        # Bullet-Artefakt): Ohne die Solo-Variante wurde „-" erst angejoint
        # und dann vom Silbentrennungs-Zweig verschluckt (Review-Befund E5).
        ist_liste = bool(re.match(r"^(?:[-•–]\s|[-•–]$|\d+[.)]\s|[a-z]\)\s)", ln))
        vor_label = bool(out) and out[-1].endswith(":") and len(out[-1]) <= 40
        vor_liste = bool(out) and re.match(r"^[-•–]$", out[-1])
        if out and not ist_label and not ist_liste and not vor_label:
            if vor_liste:
                out[-1] = out[-1] + " " + ln         # Solo-Strich + Folgetext = Listenpunkt
            elif out[-1].endswith("-") and len(out[-1]) > 1 and out[-1][-2].isalpha():
                # Silbentrennung am Zeilenende: „einge-" + „schränkt" →
                # „eingeschränkt"; bei großgeschriebener Fortsetzung bleibt der
                # Bindestrich („Weser-" + „Ems" → „Weser-Ems", Befund E4).
                if ln[:1].islower():
                    out[-1] = out[-1][:-1] + ln
                else:
                    out[-1] = out[-1] + ln
            else:
                out[-1] = out[-1] + " " + ln
        else:
            out.append(ln)
    return out


def _kern(text: str) -> str:
    """Nur Buchstaben und Ziffern — Vergleichsform für „steht das schon auf der
    Karte?". Muss die PDF-Silbentrennung überstehen: Der Kartentext trägt
    „Verwaltungs- aufwand" (``ernte`` klebt Zeilen bloß aneinander), der Auszug
    heilt daraus „Verwaltungsaufwand" (``_entzeilen``). Als Fließtext sind das
    zwei verschiedene Zeichenketten, als Kern derselbe.

    ``isalnum`` statt einer Zeichenklasse: Ein handgeschriebener Bereich wie
    ``a-zà-öø-ÿ`` lässt ausgerechnet das ß draußen (U+00DF liegt davor) — aus
    „Veräußerung" würde „veräuerung"."""
    return "".join(c for c in text.lower() if c.isalnum())


def _deckt_ab(karte: str | None, zeilen: list[str]) -> bool:
    """Trägt die Karte den ganzen Block — oder nur seinen Anfang?

    ``ernte`` kappt ``financial_impact`` bei 800 Zeichen (``climate_impact``
    bei 2500), und zwar an der Satzgrenze und damit OHNE Auslassungszeichen:
    Der gekappte Wert sieht aus wie ein vollständiger. Über den Bestand
    gemessen sind 142 Finanz- und 3 Klima-Angaben so gekappt, im Schnitt um
    knapp 500 Zeichen. Würde der Auszug den Block trotzdem hergeben, wären
    diese 500 Zeichen auf der ganzen Seite nirgends mehr zu lesen. Deshalb
    weicht der Schnitt hier zurück und lässt den Block stehen."""
    if not karte:
        return False
    return _kern(" ".join(zeilen)) in _kern(karte)


def _schneide_auswirkungen(body: list[str], karte_finanzen: str | None,
                           karte_klima: str | None) -> list[str]:
    """Den „Auswirkungen"-Block herausnehmen — HERAUSNEHMEN, nicht abschneiden,
    und nur die Hälfte, die ihre Karte nachweislich vollständig trägt.

    Bei 137 der 4760 Vorlagen mit diesem Block folgt dahinter noch ein
    Sachabschnitt, fast immer die „Begründung". Ein Schnitt bis zum Textende
    (wie beim Anlagen-Schwanz) verlöre sie — der Block endet deshalb am
    nächsten Header, und was danach kommt, bleibt stehen.

    Je Hälfte einzeln entschieden, weil die Ernte regelmäßig nur eine der
    beiden trifft: „a) Finanzen:" mit Doppelpunkt oder mit Text auf derselben
    Zeile geht ihr durch, „b) Klima" darunter nicht. Ein gemeinsamer Schnitt
    nähme dann auch die Hälfte mit, die auf keiner Karte steht.
    """
    gelesen = 0
    kopf = None
    for i, ln in enumerate(body):
        if gelesen >= _MIN_BODY_CHARS and _AUSWIRKUNGEN_RE.match(ln):
            kopf = i
            break
        gelesen += len(ln) + 1
    if kopf is None:
        return body
    ende = next((j for j in range(kopf + 1, len(body))
                 if _SECTION_RE.match(body[j]) or _ANLAGEN_RE.match(body[j])
                 or _AUSWIRKUNGEN_ENDE_RE.match(body[j])
                 or _AUSWIRKUNGEN_REST_RE.match(body[j])
                 or _SCHLUSSZEILE_RE.match(body[j])), len(body))
    # Alte Form (bis 2021): Die Überschrift „Finanzielle Auswirkungen:" IST der
    # Finanzblock, Unterpunkte gibt es dort nicht.
    if "Finanzielle" in body[kopf]:
        if _deckt_ab(karte_finanzen, body[kopf + 1:ende]):
            return body[:kopf] + body[ende:]
        return body

    fa = next((j for j in range(kopf + 1, ende) if _A_FINANZEN_RE.match(body[j])), None)
    fb = next((j for j in range(kopf + 1, ende) if _B_KLIMA_RE.match(body[j])), None)
    weg: set[int] = set()
    if fa is not None:
        bis = fb if fb is not None and fb > fa else ende
        # Ohne die Überschrift selbst vergleichen — auf der Karte steht sie nicht.
        rumpf = [_A_FINANZEN_RE.sub("", body[fa], count=1), *body[fa + 1:bis]]
        if _deckt_ab(karte_finanzen, rumpf):
            weg |= set(range(fa, bis))
    if fb is not None:
        rumpf = [_B_KLIMA_RE.sub("", body[fb], count=1), *body[fb + 1:ende]]
        if _deckt_ab(karte_klima, rumpf):
            weg |= set(range(fb, ende))
    if not weg:
        return body
    # Die Überschrift „Auswirkungen:" nur mitnehmen, wenn darunter nichts
    # stehen bleibt — sonst leitet sie ins Leere.
    if all(j in weg for j in range(kopf + 1, ende)):
        weg.add(kopf)
    return [ln for j, ln in enumerate(body) if j not in weg]


def excerpt(raw_text: str, chars: int | None = 400, *,
            karte_finanzen: str | None = None,
            karte_klima: str | None = None) -> str:
    """A readable excerpt of a Vorlage text: starts at the first substantive
    section (Sachverhalt/Begründung/…) when one is found, drops per-page
    boilerplate lines and the administrative tail (Anlagen list, signature),
    collapses whitespace. ``chars=None`` keeps the whole text — the Beschluss
    page shows it complete. Empty string when there is no text.

    ``karte_finanzen``/``karte_klima`` sind die beiden Karten der Beschluss-
    Seite („Was kostet das?", „Klima-Check"). Wer sie mitgibt, sagt damit:
    Nimm aus dem Auszug heraus, was hier schon steht — aber nur, was hier
    WIRKLICH steht. Übergeben wird der Text und nicht bloß ein Ja/Nein, weil
    beides sonst nicht zu entscheiden wäre: ob die Karte den Block ganz trägt
    oder nur seinen Anfang (s. ``_deckt_ab``), und ob sie überhaupt zu diesem
    Rohtext gehört — eine noch nicht nachgetragene Spalte passt dann eben
    nicht, und der Block bleibt stehen, statt ersatzlos zu verschwinden.
    **Der Vorgabewert ist ``False``, und das ist keine Bequemlichkeit.** Diese
    Funktion bedient zwei Fälle: die Beschluss-Seite, wo der Block als eigene
    Karte daneben steht und im Auszug doppelt wäre — und das Chunking für
    Einbettungen, Volltextsuche und KI-Frage (``council/embeddings.py``), wo
    er der einzige Ort ist, an dem „was kostet das" überhaupt auffindbar
    steht. Ihn dort mit herauszuschneiden hieße, eine Frage nach den Kosten
    unbeantwortbar zu machen. Nur der Aufrufer weiß, in welchem der beiden
    Fälle er ist — und die Seite setzt den Schalter genau dann, wenn die
    Karten den Block wirklich tragen."""
    if not raw_text:
        return ""
    lines = [ln.strip() for ln in raw_text.splitlines()]
    kept = [ln for ln in lines if ln and not _NOISE_RE.match(ln)]
    start = next((i for i, ln in enumerate(kept) if _SECTION_RE.match(ln)), None)
    if start is None:
        start = next((i for i, ln in enumerate(kept) if _FALLBACK_SECTION_RE.match(ln)), 0)
    body = kept[start:]
    gelesen = 0
    for i, ln in enumerate(body):
        if gelesen >= _MIN_BODY_CHARS and _ANLAGEN_RE.match(ln):
            body = body[:i]
            break
        gelesen += len(ln) + 1
    if karte_finanzen or karte_klima:
        body = _schneide_auswirkungen(body, karte_finanzen, karte_klima)
    text = "\n".join(_entzeilen(body))
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = _SIGNATURE_RE.sub("", text).rstrip()
    text = _SPACED_NAME_RE.sub("", text).rstrip()
    if chars is not None and len(text) > chars:
        # Cut at a word boundary so the ellipsis doesn't split a word.
        cut = text[:chars].rsplit(" ", 1)[0]
        text = cut + " …"
    return text
