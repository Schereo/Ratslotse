"""Prüfungsfeststellungen aus den Schlussberichten des Rechnungsprüfungsamts.

Das Rechnungsprüfungsamt (RPA) prüft jeden Jahresabschluss der Stadt und legt
dem Rat einen Schlussbericht vor. Der Bericht hängt als PDF-Anlage an einer
Ratsvorlage (``council_anlagen``) und wird dort nie wieder gelesen — dabei
steht in ihm die einzige regelmäßige, förmliche Kontrolle der Verwaltung
durch eine eigene Stelle.

Greifbar ist das, weil der Bericht seine Feststellungen mit **Randmarken**
auszeichnet und deren Bedeutung selbst in den Vorbemerkungen erklärt::

    Randbemerkungen:
     B   Beanstandung — festgestellter bedeutsamer Mangel
     WB  Wiederholte Beanstandung — ein bereits in Vorjahren festgestellter
         bedeutsamer Mangel, der noch nicht ausgeräumt … worden ist
     H   Hinweis — zur künftigen Beachtung …
     K   Korrektur/Klärung — für künftige Abschlüsse erforderlich

Im Fließtext steht die Marke am Zeilenanfang, der Befund folgt dahinter.

Wie die Finanzparser (``council/finanzberichte.py``) ist auch dieser bewusst
misstrauisch. Statt einer Rechenprobe gilt hier ein **Konsistenz-Check**, den
das Dokument selbst hergibt:

1. Es gibt eine Legende, und nur die dort erklärten Marken zählen. Eine Marke
   ohne Legendeneintrag ist ein Extraktionsartefakt, keine Feststellung.
2. Jede Marke muss unter einer **Textziffer** stehen, die im
   Inhaltsverzeichnis geführt wird (das Verzeichnis überschreibt die Spalte
   ausdrücklich mit „Textziffer").
3. Der Textblock endet an der nächsten Marke oder der nächsten
   Abschnittsüberschrift — nie „so viele Zeichen".

Was diese Klammer nicht erfüllt, wird verworfen und gezählt, nicht geraten.

Nicht gelesen wird der Jahrgang **2024**: Sein PDF bringt keine
Zeichenzuordnung mit, der Volltext besteht aus Glyphen-Indizes. Er scheitert
schon an :func:`erkenne_jahrgang` — ohne Sonderfall, weil der Textanfang
schlicht nicht passt.
"""
from __future__ import annotations

import re

#: Die vier Marken des Randmarken-Systems. Mehr gibt es nicht; was sonst am
#: Zeilenanfang steht, ist keine Feststellung.
MARKEN = ("B", "WB", "H", "K")

#: So beginnt der Volltext eines Schlussberichts über die **Kernverwaltung**.
#: Die Labels taugen zur Unterscheidung nicht: „Schlussbericht JA 2017"
#: (``document_id`` 192039) ist der Bericht zum Eigenbetrieb
#: Gebäudewirtschaft, und ein gutes Dutzend weiterer Anlagen betrifft
#: Klävemann-Stiftung, VOSS, AWB oder EGH — alle mit ähnlichem Titel und
#: derselben Jahreszahl. Der Textanfang trennt sauber: Die Stiftungsberichte
#: schreiben „…über die Prüfung des Jahresabschlusses **zum 31. Dezember**".
#:
#: KEIN ``^``-ANKER MEHR (seit 20.08.2026). Er hat nie die Arbeit gemacht —
#: die leistet „der Stadt Oldenburg“ am Ende: Die Stiftungs- und
#: Eigenbetriebsberichte schreiben dort „…des Jahresabschlusses **zum 31.
#: Dezember**“ und fallen schon daran durch, egal wo im Text sie stehen.
#:
#: Der Anker stand nur da, weil der PDF-Textextrakt zufällig mit dem Titel
#: begann. Der Schlussbericht 2024 hat keine brauchbare Textebene und muss
#: per OCR gelesen werden — und dort steht davor, was auf dem Papier eben
#: auch davorsteht: der Briefkopf. Mit Anker fiel der Jahrgang durch, ohne
#: dass irgendetwas an ihm falsch war.
_ANFANG = re.compile(
    r"Schlussbericht des Rechnungsprüfungsamtes über die Prüfung "
    r"des Jahresabschlusses (20\d\d) der Stadt Oldenburg")

#: Zeile der Legende: Marke, dann der Name der Marke („Beanstandung").
#: Die Schreibweise schwankt zwischen den Jahrgängen zwischen „B Beanstandung"
#: (2017/2018) und „ B  Beanstandung" (ab 2019), deshalb großzügig im
#: Zwischenraum — hier steht die Marke ohnehin allein auf der Zeile.
_LEGENDE_ZEILE = re.compile(r"^[ \t]*(B|WB|H|K)[ \t]+([A-ZÄÖÜ][^\n]{3,60})$", re.M)

#: Marke im Fließtext: Zeilenanfang, Marke, **zwei** Leerzeichen, dann Text.
#: Die zwei Leerzeichen sind nicht kosmetisch — sie sind der Abstand der
#: Randspalte und trennen die Marke von der Unterschrift „K R U P K E"
#: (Leiterin des Rechnungsprüfungsamtes), die am Berichtsende in gesperrter
#: Schrift steht und mit einem Leerzeichen sonst als „K"-Marke durchginge.
_MARKE_IM_TEXT = re.compile(r"\n[ \t]{0,4}(WB|B|H|K)[ \t]{2}(?=\S)")

#: Zeile des Inhaltsverzeichnisses: „3.1.3  Gesetzeskonformität … 20".
_IVZ_ZEILE = re.compile(
    r"^[ \t]*(\d+(?:\.\d+)*)\.?[ \t]+(\S[^\n]*?)[ \t]+(\d{1,3})[ \t]*$", re.M)

#: Abschnittsüberschrift im Fließtext — dieselbe Form, nur ohne Seitenzahl.
#: Übernommen wird sie erst, wenn Nummer **und** Titel zum Verzeichnis passen
#: (siehe :func:`_ueberschriften`); ohne diese Prüfung fiele jede Aufzählung
#: im Text („1. die Prüfung des Jahresabschlusses,") als Überschrift an.
_UEBERSCHRIFT = re.compile(r"^[ \t]*(\d+(?:\.\d+)*)\.?[ \t]+(\S[^\n]{0,90})$", re.M)

#: Seitenkopf/-fuß, der mitten in einem Textblock steht und dort nichts zu
#: suchen hat. Zwei Formen: „R e c h n u n g s p r ü f u n g s a m t <Datum> …
#: Schlussbericht 2017 Seite 6" (2017/2018) und „Stadt Oldenburg (Oldb) -
#: Rechnungsprüfungsamt <Datum> … des Jahresabschlusses 2023 Seite 46".
#:
#: Zwei Fallen stecken hier drin, beide teuer bezahlt: Die Buchstaben der
#: gesperrten Schreibweise brauchen ein **verbindliches** Trennzeichen
#: (``\s`` statt ``\s?``) — sonst passt das Muster auch auf das Wort
#: „Rechnungsprüfungsamt" mitten im Satz und frisst von dort bis zur nächsten
#: „Seite n" den halben Befund weg. Und der Kopf steht immer am Zeilenanfang;
#: ohne diesen Anker greift das Muster in laufende Sätze hinein.
_SEITENFURNITUR = re.compile(
    r"^[ \t]*(?:Stadt Oldenburg \(Oldb\)\s*[-–]\s*Rechnungsprüfungsamt"
    r"|R\se\sc\sh\sn\su\sn\sg\ss\sp\sr\sü\sf\su\sn\sg\ss\sa\sm\st)"
    r".{0,220}?Seite\s+\d{1,3}", re.S | re.M)

#: „Seite 46" aus dem Seitenkopf — die Fundstelle, auf die ein Leser blättert.
_SEITENZAHL = re.compile(r"Seite\s+(\d{1,3})\s*\n")

#: Absatzumbruch im PDF-Extrakt: eine Zeile, auf der nur Leerraum steht.
_ABSATZ = re.compile(r"\n[ \t]*\n")

#: Wörter, vor denen ein Trennstrich am Zeilenende **kein** Trennstrich ist,
#: sondern ein Ergänzungsstrich: „Ertrags-\nund Aufwandsseite" bleibt
#: „Ertrags- und Aufwandsseite", nicht „Ertragsund".
_ERGAENZUNG = {"und", "oder", "sowie", "bzw", "beziehungsweise", "wie", "als",
               "noch", "je", "bis"}

#: Kürzeste Feststellung, die wir gelten lassen — ein Rückfallnetz gegen
#: Marken, hinter denen nur ein Satzrest steht. Die Schwelle ist bewusst
#: niedrig: Der kürzeste echte Befund im Bestand 2017–2023 ist „Die
#: Buchungsdokumentation ist weiter zu optimieren." mit 51 Zeichen, und die
#: Nacharbeiten-Übersicht der Verwaltung zum Prüfbericht 2020 führt genau ihn
#: als laufende Nummer 1. Eine strengere Schwelle hätte ihn verschluckt.
MIN_LAENGE = 40

#: Wie weit vorne der Titel stehen muss. 400 reichten, solange der
#: Textextrakt mit ihm begann; per OCR steht der Briefkopf davor und
#: schiebt ihn um rund 60 Zeichen nach hinten. 800 lässt Luft für einen
#: längeren Briefkopf und hält den Titel trotzdem am Anfang des Dokuments
#: fest — mitten im Bericht wird ein Schlussbericht ohnehin nicht noch
#: einmal betitelt.
KOPF_ZEICHEN = 800

#: Längster Absatz, der noch als „was direkt darauf folgt" durchgeht. Darüber
#: ist es kein Nachsatz mehr, sondern der nächste Erzählschritt des Berichts.
FOLGEABSATZ_MAX = 700


def erkenne_jahrgang(text: str) -> int | None:
    """Prüfen, ob dieser Anlagentext ein RPA-Schlussbericht der Kernverwaltung
    ist — und zu welchem Jahresabschluss er gehört.

    Der Abgleich läuft über den **Textanfang**, nicht über das Label, und der
    Text wird dafür vorher in seinen Zwischenräumen normalisiert: Im PDF-
    Extrakt steht der Titel über vier Zeilen („Schlussbericht\\ndes
    Rechnungsprüfungsamtes über die\\nPrüfung des Jahresabschlusses 2017\\n…"),
    ein ``LIKE 'Schlussbericht des …'`` in SQL findet also nichts.

    Liefert das Jahr des geprüften Abschlusses oder ``None``.
    """
    flach = re.sub(r"\s+", " ", (text or "")[:KOPF_ZEICHEN]).strip()
    m = _ANFANG.search(flach)
    return int(m.group(1)) if m else None


def parse_legende(text: str) -> dict[str, dict]:
    """Die Randmarken-Legende aus den Vorbemerkungen.

    Liefert ``{"WB": {"name": "Wiederholte Beanstandung", "explanation":
    "ein bereits in Vorjahren festgestellter … Mangel, der noch nicht
    ausgeräumt … worden ist"}, …}``.

    Sie ist das Maß für alles Weitere: Der Jahrgang 2023 erklärt nur B, WB und
    H — und trägt im Text folgerichtig auch kein K. Eine Marke ohne
    Legendeneintrag zu übernehmen hieße, dem Dokument etwas zu unterstellen,
    was es nicht sagt.

    Die Erläuterung wird mitgelesen, weil die Marken auf der Seite **erklärt**
    und nicht bewertet werden sollen — und die beste Erklärung ist die, die
    das Rechnungsprüfungsamt selbst gibt.
    """
    start = text.find("Randbemerkungen")
    if start < 0:
        return {}
    # Die Legende endet, wo der Bericht anfängt. Ohne diese Grenze zieht die
    # letzte Marke (2017–2022 „K", 2023 „H") den halben Abschnitt 1.1 als
    # ihre Erläuterung hinter sich her.
    block = text[start:_koerper_beginn(text, start)]
    stellen = list(_LEGENDE_ZEILE.finditer(block))
    legende: dict[str, dict] = {}
    for i, m in enumerate(stellen):
        if m.group(1) in legende:
            continue
        ende = stellen[i + 1].start() if i + 1 < len(stellen) else len(block)
        legende[m.group(1)] = {
            "name": m.group(2).strip().rstrip("."),
            "explanation": saeubern(block[m.end():ende]).rstrip(".") or None,
        }
    return legende


def _koerper_beginn(text: str, legende_start: int) -> int:
    """Beginn des eigentlichen Berichts (Textziffer 1).

    Wichtig für die Zählung: Die Legende selbst schreibt die vier Marken in
    genau der Form, die auch im Fließtext gilt. Wer davor zu zählen beginnt,
    zählt jede Marke einmal zu oft — für 2019–2023 exakt +1 je Marke.
    """
    stelle = text.find("Grundlagen der Prüfung", legende_start)
    if stelle < 0:
        return legende_start
    zeilenanfang = text.rfind("\n", 0, stelle)
    return zeilenanfang if zeilenanfang > 0 else stelle


def parse_inhaltsverzeichnis(text: str) -> dict[str, str]:
    """Textziffern des Berichts: ``{"3.1.3": "Gesetzeskonformität, …"}``.

    Das Verzeichnis überschreibt seine erste Spalte selbst mit „Textziffer" —
    die Nummern sind also keine Erfindung dieses Parsers, sondern die
    Fundstellen-Systematik des Dokuments.
    """
    start = text.lower().find("inhaltsverzeichnis")
    if start < 0:
        return {}
    grenzen = [i for i in (text.find("Verzeichnis der Abkürzungen"),
                           text.find("Randbemerkungen")) if i > start]
    ende = min(grenzen) if grenzen else start + 8000
    ivz: dict[str, str] = {}
    for m in _IVZ_ZEILE.finditer(text[start:ende]):
        ivz.setdefault(m.group(1), m.group(2).strip())
    return ivz


def _norm(s: str) -> str:
    """Titel auf seine Buchstaben eindampfen — der PDF-Extrakt setzt in
    Überschriften gern zusätzliche Leerzeichen („Gesetzeskonformit ät")."""
    return re.sub(r"[^0-9a-zäöüß]", "", s.lower())


def _ueberschriften(text: str, ab: int, ivz: dict[str, str]) -> list[tuple[int, str, str]]:
    """Fundstellen der Abschnittsüberschriften im Fließtext, aufsteigend.

    Eine Zeile gilt nur als Überschrift, wenn ihre Nummer im
    Inhaltsverzeichnis steht **und** ihr Titel zu dem dort verzeichneten
    passt. Der erste Treffer je Nummer gewinnt: Was danach kommt, sind
    Rückverweise im Text („siehe Textziffer 4.6").
    """
    gefunden: list[tuple[int, str, str]] = []
    gesehen: set[str] = set()
    for m in _UEBERSCHRIFT.finditer(text, ab):
        nr = m.group(1)
        soll = ivz.get(nr)
        if soll is None or nr in gesehen:
            continue
        ist, erwartet = _norm(m.group(2)), _norm(soll)
        if not (ist.startswith(erwartet[:14]) or erwartet.startswith(ist[:14])):
            continue
        gesehen.add(nr)
        gefunden.append((m.start(), nr, soll))
    gefunden.sort()
    return gefunden


def saeubern(roh: str) -> str:
    """Rohen Textblock in lesbare Prosa überführen.

    Zwei Eingriffe, beide auf Layout-Artefakte des PDF-Extrakts beschränkt:

    - **Seitenfurnitur** (Kopfzeile mit Amt, Datum, Berichtstitel und
      „Seite n") fällt weg — sie steht mitten im Satz, wenn eine Feststellung
      über einen Seitenumbruch läuft.
    - **Silbentrennung** am Zeilenende wird zusammengezogen
      („Bescheini-\\ngungen" → „Bescheinigungen"). Zwei Ausnahmen, weil der
      Strich dort keine Trennung ist: vor einem Ergänzungswort
      („Ertrags-\\nund" → „Ertrags- und") und vor einem Großbuchstaben
      („Programm-\\nUpdates" → „Programm-Updates").

    **Nicht** repariert werden Leerzeichen mitten im Wort („Schlussberi
    chten"). Sie kommen in den Jahrgängen 2017 und 2021 vor und ließen sich
    nur raten — und Raten ist in diesem Repo die falsche Antwort. Der Link auf
    das Originaldokument steht an jeder Feststellung.
    """
    text = _SEITENFURNITUR.sub(" ", roh)

    def verbinden(m: re.Match) -> str:
        wort = m.group(1)
        if wort.lower() in _ERGAENZUNG:
            return "- " + wort   # Ergänzungsstrich: „Ertrags- und Aufwandsseite"
        if wort[:1].isupper():
            return "-" + wort    # echter Bindestrich: „Programm-Updates"
        return wort              # Silbentrennung: „Bescheini-gungen"

    text = re.sub(r"-[ \t]*\n[ \t]*(\w+)", verbinden, text)
    return re.sub(r"\s+", " ", text).strip()


def _absaetze(block: str) -> list[str]:
    """Einen Textblock in vollständige Absätze zerlegen.

    „Vollständig" heißt: Der Absatz endet auf ein Satzzeichen. Das ist nicht
    Kosmetik, sondern die Reparatur für Befunde, die über einen Seitenumbruch
    laufen — der Umbruch hinterlässt im Extrakt eine Leerzeile mitten im Satz,
    und ein naiver Absatz-Split würde dort abschneiden. Endet ein Stück nicht
    satzfertig, wird das nächste angehängt.
    """
    fertige: list[str] = []
    offen = ""
    for stueck in _ABSATZ.split(_SEITENFURNITUR.sub(" ", block)):
        offen = f"{offen}\n\n{stueck}" if offen else stueck
        text = saeubern(offen)
        if text.endswith((".", "!", "?", ":", "“", "\"")):
            fertige.append(text)
            offen = ""
    rest = saeubern(offen)
    if rest:
        fertige.append(rest)
    return [t for t in fertige if t]


def parse_feststellungen(text: str) -> dict:
    """Alle Prüfungsfeststellungen eines Schlussberichts.

    Liefert ``{year, legende, feststellungen, verworfen}``. Jede Feststellung
    trägt ``{seq, mark, mark_name, mark_explanation, chain, text_number,
    section, page, text, follow_paragraph}`` — also alles, was zum Nachschlagen
    im Originaldokument nötig ist.

    ``text`` ist der **erste vollständige Absatz** hinter der Marke, nicht der
    ganze Block bis zur nächsten Überschrift. Der Block ist die harte Grenze
    (siehe oben), aber die Feststellung selbst ist der Absatz: Was danach
    kommt, ist mal die Antwort der Verwaltung, mal eine Tabelle, mal der
    nächste Erzählschritt des Berichts. Alles davon unter die Marke zu
    schreiben hieße, dem Rechnungsprüfungsamt Sätze als Beanstandung
    zuzurechnen, die es nicht so gemeint hat.

    ``follow_paragraph`` hält genau den einen Absatz fest, der im Bericht direkt
    darauf folgt (sofern es ihn im selben Block gibt). Dort steht oft die
    Gegenseite — „Die Verwaltung hat hierzu erklärt, dass eine entsprechende
    Umsetzung bis 31.12.2024 erfolgen soll." —, und die gehört zu einer
    fairen Darstellung dazu. Er wird getrennt geführt und getrennt angezeigt,
    damit klar bleibt, was Feststellung ist und was Umfeld.

    ``verworfen`` ist keine Fußnote, sondern Teil des Ergebnisses: Wer den
    Ingest liest, soll sehen, wie viel der Parser hat liegen lassen und warum.
    Bleibt die Zahl klein, stimmt die Klammer; wird sie groß, hat sich das
    Dokumentformat geändert und es ist Zeit für einen Blick, nicht für eine
    gelockerte Regel.
    """
    year = erkenne_jahrgang(text)
    legende = parse_legende(text)
    ivz = parse_inhaltsverzeichnis(text)
    leer = {"year": year, "legende": legende, "feststellungen": [],
            "verworfen": []}
    if year is None or not legende or not ivz:
        return leer

    ab = _koerper_beginn(text, text.find("Randbemerkungen"))
    kapitel = _ueberschriften(text, ab, ivz)
    if not kapitel:
        return leer

    marken = [(m.start(), m.group(1)) for m in _MARKE_IM_TEXT.finditer(text, ab)]
    # Ein Textblock endet an der nächsten Marke ODER der nächsten Überschrift,
    # je nachdem, was zuerst kommt.
    grenzen = sorted([p for p, _, _ in kapitel] + [p for p, _ in marken])

    feststellungen: list[dict] = []
    verworfen: list[dict] = []
    for pos, mark in marken:
        if mark not in legende:
            verworfen.append({"mark": mark, "reason": "nicht in der Legende erklärt"})
            continue
        kapitel_hier = [k for k in kapitel if k[0] < pos]
        if not kapitel_hier:
            verworfen.append({"mark": mark, "reason": "keine Textziffer davor"})
            continue
        _, text_number, section = kapitel_hier[-1]
        ende = next((g for g in grenzen if g > pos), len(text))
        absaetze = _absaetze(text[pos:ende])
        if not absaetze:
            verworfen.append({"mark": mark, "text_number": text_number,
                              "reason": "kein Textblock hinter der Marke"})
            continue
        inhalt = re.sub(r"^(?:WB|B|H|K)\s+", "", absaetze[0])
        if len(inhalt) < MIN_LAENGE:
            verworfen.append({"mark": mark, "text_number": text_number,
                              "reason": f"Textblock zu kurz ({len(inhalt)} Zeichen)"})
            continue
        folge = absaetze[1] if len(absaetze) > 1 else None
        if folge and len(folge) > FOLGEABSATZ_MAX:
            folge = None  # so lang ist keine Antwort mehr, das ist der Bericht
        seiten = _SEITENZAHL.findall(text[:pos])
        feststellungen.append({
            "seq": len(feststellungen) + 1,
            "mark": mark,
            "mark_name": legende[mark]["name"],
            "mark_explanation": legende[mark]["explanation"],
            "chain": kettenschluessel(section),
            "text_number": text_number,
            "section": section,
            "page": int(seiten[-1]) if seiten else None,
            "text": inhalt,
            "follow_paragraph": folge,
        })
    return {"year": year, "legende": legende,
            "feststellungen": feststellungen, "verworfen": verworfen}


def kettenschluessel(section: str) -> str:
    """Schlüssel, unter dem dieselbe Sache über Jahrgänge hinweg zusammenfindet.

    Eine wiederholte Beanstandung (WB) sagt von selbst, dass sie schon einmal
    dastand — sie sagt nur nicht, wo. Der Abschnittstitel tut das: „Plan-Ist-
    Vergleich" trägt von 2017 bis 2023 in jedem Bericht eine WB, das ist die
    längste offene Kette im Bestand. Die Textziffer taugt dafür **nicht**, sie
    verschiebt sich zwischen den Jahrgängen.

    Klammerzusätze fallen weg, weil sie kommen und gehen („Internes
    Kontrollsystem (IKS)" 2017–2019 heißt ab 2020 „Internes Kontrollsystem").
    """
    ohne_klammer = re.sub(r"\([^)]*\)", " ", section or "")
    return re.sub(r"[^a-zäöüß]", "", ohne_klammer.lower())
