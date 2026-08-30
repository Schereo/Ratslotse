"""Der Kritiker: Prüft jeden Kartentext, bevor er gespeichert wird.

Warum es ihn gibt — gemessen am ersten Produktionslauf (30.08.2026, 22
Texte für die Woche 31.8.–6.9.):

* „… um **69 Hektar** bis 2027 und **89 Hektar** bis 2032 auszuweisen."
  Beide Zahlen stehen in der Vorlage — aber als GESETZLICHE ZIELE. Der Plan
  selbst weist 91,84 Hektar aus. Ein Zahlenvergleich allein fängt das nicht.
* „… Aufwertung von **fünf** P + R Standorten." Dieser Punkt hat gar keine
  Vorlage; das Modell sah nur den Titel und erfand die Fünf.
* „Die Kosten trägt die **Baugruppe**." In der Vorlage steht „von Eigentümern
  beziehungsweise den Antragstellern".

Drei Fehler auf 22 Texte, zwei davon frei erfunden. Für einen Kanal, der
unbeaufsichtigt läuft, ist das zu viel — und alle drei fielen nur auf, weil
ein Mensch sie gegengelesen hat.

Zwei Stufen, in dieser Reihenfolge:

1. ``pruefe`` — deterministisch, kostenlos, nicht diskutabel. Fängt
   erfundene Zahlen, Wertungen, vorweggenommene Ergebnisse, Aktenzeichen.
2. ``pruefe_llm`` — der zweite Blick für alles, was keine Zahl ist: Steht
   diese Behauptung so in der Quelle? Fängt die „Baugruppe".

Was durchfällt, wird NICHT gespeichert. Der Bot fällt dann auf die
Kurzfassung zurück — dröge, aber vom Ratslotse gedeckt.

GRENZEN, gemessen an denselben 22 Texten (30.08.2026):

* Die deterministische Stufe hatte NULL Fehlalarme und fing beide erfundenen
  Mengen („94 Hektar", „fünf Standorte").
* Die LLM-Stufe verwarf 3 von 22; zwei davon zu Recht (die Karte schrieb
  „Geplant ist die Beauftragung", laut Vorlage war der Vergabebeschluss
  längst gefasst).
* Sie fing „Die Kosten trägt die Baugruppe" — und ließ „69 Hektar bis 2027
  und 89 Hektar bis 2032 ausweisen" DURCH. Beide Zahlen stehen in der
  Vorlage, nur eben als gesetzliche Ziele und nicht als das, was der Plan
  ausweist. Umgekehrt verwarf sie den korrigierten Satz mit „91,84 Hektar
  Sonderbaufläche", der wörtlich gedeckt ist.

Der Kritiker senkt das Risiko, er beseitigt es nicht. Wer einen Post ohne
Gegenlesen rausschickt, tut das weiterhin auf eigenes Risiko — nur eben mit
zwei Netzen statt keinem.
"""
from __future__ import annotations

import json
import os
import re

from kern import llm, prompts

#: Der Kritiker liest 40.000 bis 60.000 Zeichen Vorlage und soll darin eine
#: einzelne Angabe wiederfinden. Das kleine Modell scheiterte daran: Es
#: verwarf „110 Wohnungen" und „5.000 Euro", die beide wörtlich in der
#: Quelle stehen (8 Fehlalarme auf 22 Texte, gemessen 30.08.26). Deshalb
#: dasselbe Modell, das auch die Tragweite bewertet.
MODEL = os.environ.get("COUNCIL_KRITIKER_MODEL", "deepseek/deepseek-v4-pro")

#: Wertende Wörter. Dieselbe Liste, die der Prompt verbietet — hier noch
#: einmal als Netz: Ein Prompt ist eine Bitte, das hier ist eine Prüfung.
_WERTUNG_RE = re.compile(
    r"\b(wichtig(e|er|es|en)?|bedeutend|bedeutsam|erheblich|gravierend|"
    r"risiko|risiken|riskant|chance|chancen|umstritten|ehrgeizig|dringend|"
    r"wegweisend|zukunftsweisend|dramatisch|massiv|besorgniserregend|"
    r"begrüßenswert|fragwürdig|überfällig)\b", re.IGNORECASE)

#: Vorweggenommene Ergebnisse. Die Sitzung hat noch nicht stattgefunden —
#: „Der Rat beschließt" behauptet einen Beschluss, den es nicht gibt.
_ERGEBNIS_RE = re.compile(
    r"\b(beschließt|beschlossen|stimmt zu|zugestimmt|lehnt ab|abgelehnt|"
    r"angenommen|verabschiedet|entschieden)\b", re.IGNORECASE)

#: Aktenzeichen, die aus einem anderen Dokument stammen: „[26/0666]".
_AKTENZEICHEN_RE = re.compile(r"\[\s*\d{2}/\d{2,4}(?:/\d+)*\s*\]")

#: Zahlen im Text. Auch „13.500.000", „91,84", „8,6" — Tausenderpunkte und
#: Dezimalkomma gehören zur Zahl, sonst zerfiele jede Summe in Bruchstücke.
_ZAHL_RE = re.compile(r"\d[\d.,]*")

#: Jahreszahlen brauchen keinen Beleg — „bis 2032" schlüge sonst ständig an.
_JAHR_RE = re.compile(r"^(?:19[5-9]\d|20[0-9]\d)$")


def _braucht_beleg(text: str, treffer: re.Match) -> bool:
    """Muss diese Zahl in der Quelle stehen?

    Nein bei Jahreszahlen („bis 2032"), bei Ordnungszahlen („die 1.
    Änderungssatzung") und bei Paragrafen („§ 246e"). Ja bei allem anderen —
    auch bei kleinen Zahlen: Der P+R-Punkt vom 31.08.2026 hatte gar keine
    Vorlage, und genau dort erfand das Modell „fünf Standorte". Eine pauschale
    Freistellung kleiner Zahlen hätte den Fall durchgelassen.
    """
    roh = treffer.group(0)
    zahl = roh.strip(".,")
    if _JAHR_RE.match(zahl):
        return False
    if "§" in text[max(0, treffer.start() - 2):treffer.start()]:
        return False
    # Ordnungszahl: „die 1. Änderungssatzung", „der 3. Bauabschnitt". Der
    # Punkt gehört zum Treffer, weil die Regex ihn mitnimmt — er steht also
    # NICHT dahinter im Text.
    return not (roh.endswith(".") and zahl.isdigit() and len(zahl) <= 2)


MAX_ZEICHEN = 240


#: Zahlwörter, die eine MENGE behaupten. „eins/ein" fehlt bewusst — das ist
#: im Deutschen meist der unbestimmte Artikel („ein Darlehen").
#:
#: Sie sind belegpflichtig wie Ziffern, und zwar aus einem gemessenen Grund:
#: Der P+R-Punkt vom 31.08.2026 hatte gar keine Vorlage, und das Modell
#: schrieb „fünf P + R Standorte". Als Ziffer hätte die Prüfung sie gefangen,
#: als Wort rutschte sie durch.
_MENGENWORT_RE = re.compile(
    r"\b(zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf)\b", re.IGNORECASE)

_WORT_ZAHL = {"zwei": "2", "drei": "3", "vier": "4", "fünf": "5", "sechs": "6",
              "sieben": "7", "acht": "8", "neun": "9", "zehn": "10", "elf": "11",
              "zwölf": "12"}


def _zahlen(text: str) -> set[str]:
    """Alle belegpflichtigen Mengenangaben des Textes — Ziffern und Zahlwörter."""
    raus = {m.group(0).strip(".,") for m in _ZAHL_RE.finditer(text)
            if m.group(0).strip(".,") and _braucht_beleg(text, m)}
    raus |= {m.group(0).lower() for m in _MENGENWORT_RE.finditer(text)}
    return raus


#: Zahlwörter, wie Vorlagen sie schreiben: „innerhalb von zehn Jahren"
#: (Baumfällungs-Vorlage 26/0331). Die Karte macht daraus „10 Jahren" — und
#: eine Zahlenprüfung ohne diese Brücke meldete einen Fehler, wo keiner ist.
#: Am ersten Produktionslauf gemessen: genau ein Fehlalarm auf 22 Texte,
#: und es war dieser.
_ZAHLWORT = {
    "1": "eins", "2": "zwei", "3": "drei", "4": "vier", "5": "fünf", "6": "sechs",
    "7": "sieben", "8": "acht", "9": "neun", "10": "zehn", "11": "elf", "12": "zwölf",
}


def _varianten(zahl: str) -> set[str]:
    """Schreibweisen derselben Zahl, wie sie in Vorlagen vorkommen.

    „13.500.000" steht dort auch als „13.500.000,00", „13,5 Mio" oder
    „13500000". Ohne diese Varianten meldete die Prüfung Fehlalarm bei
    korrekten Texten — und ein Wächter, der ständig grundlos anschlägt, wird
    abgeschaltet.
    """
    if ziffer := _WORT_ZAHL.get(zahl.lower()):
        return {zahl.lower(), ziffer}
    roh = zahl.replace(".", "").replace(",", ".")
    raus = {zahl, roh, zahl.replace(".", ""), zahl.replace(",", ".")}
    try:
        wert = float(roh)
    except ValueError:
        return raus
    if wert.is_integer():
        ganz = int(wert)
        raus |= {f"{ganz:,}".replace(",", "."), str(ganz)}
        if wort := _ZAHLWORT.get(str(ganz)):
            raus.add(wort)
        # „13.500.000" ist in der Vorlage oft „13,5 Mio" / „13,5 Millionen".
        for teiler, _ in ((1_000_000, "Mio"), (1_000, "Tsd")):
            if ganz >= teiler:
                gekuerzt = ganz / teiler
                raus.add(f"{gekuerzt:.1f}".replace(".", ",").rstrip("0").rstrip(","))
                if gekuerzt.is_integer():
                    raus.add(str(int(gekuerzt)))
    return {v for v in raus if v}


def pruefe(text: str, quelle: str) -> list[str]:
    """Beanstandungen — leere Liste heißt: durchgelassen.

    ``quelle`` ist der Kontext, den das Modell gesehen hat (Vorlage, Anlagen,
    Titel). Jede Zahl im Text muss dort vorkommen; erfunden wird hier nichts.
    """
    maengel: list[str] = []
    if not text.strip():
        return ["leer"]
    if len(text) > MAX_ZEICHEN:
        maengel.append(f"zu lang ({len(text)} Zeichen, erlaubt {MAX_ZEICHEN})")
    if m := _WERTUNG_RE.search(text):
        maengel.append(f"wertet: „{m.group(0)}“")
    if m := _ERGEBNIS_RE.search(text):
        maengel.append(f"nimmt das Ergebnis vorweg: „{m.group(0)}“")
    if m := _AKTENZEICHEN_RE.search(text):
        maengel.append(f"Aktenzeichen: {m.group(0)}")

    quelle_kompakt = quelle.replace(".", "").replace(",", ".")
    for zahl in _zahlen(text):
        if not any(v in quelle or v in quelle_kompakt for v in _varianten(zahl)):
            maengel.append(f"Zahl steht nicht in der Quelle: {zahl}")
    return maengel


def _steht_da(zitat: str, quelle: str) -> bool:
    """Trägt dieses Zitat wirklich eine Stelle der Quelle?

    Nicht Buchstabe für Buchstabe: Modelle stellen beim Zitieren um („Die
    Sonderbaufläche wurde von … reduziert" statt „wurde die Sonderbaufläche
    von … reduziert"), und ein Wortlaut-Vergleich verwarf deshalb auch
    nachweislich richtige Sätze (gemessen 30.08.26).

    Geprüft werden die TRAGENDEN Wörter: Zahlen und Wörter ab sechs Zeichen.
    Sie alle müssen in der Quelle vorkommen. Ein erfundenes Zitat scheitert
    daran zuverlässig — seine Eigennamen und Zahlen gibt es dort nicht.
    """
    z = " ".join((zitat or "").split())
    quelle_klein = " ".join(quelle.split()).casefold()
    tragend = [w.strip(".,;:()„“\"'") for w in z.split()]
    tragend = [w for w in tragend if len(w) >= 6 or any(c.isdigit() for c in w)]
    if len(tragend) < 2:
        return False          # zu wenig Substanz, um etwas zu belegen
    return all(w.casefold() in quelle_klein for w in tragend)


def pruefe_llm(text: str, quelle: str) -> tuple[bool, str]:
    """Zweiter Blick für alles, was keine Zahl ist: Ist jede harte Angabe belegt?

    Das Modell liefert wörtliche Zitate; ob es die Stellen wirklich gibt,
    prüft ``_steht_da`` deterministisch nach. Ein Modell, das ein Zitat
    erfindet, um durchzukommen, fällt damit auf.

    (True, "") heißt gedeckt. Fällt der Aufruf aus, wird DURCHGELASSEN — der
    Text hat die deterministische Prüfung ja bestanden, und ein Netzfehler
    darf nicht die halbe Wochenvorschau leeren.

    Warum das Modell BELEGT statt zu URTEILEN: Die erste Fassung fragte „ist
    das gedeckt?" und verwarf 21 von 22 Texten — auch „91,84 Hektar
    Sonderbaufläche", das wörtlich in der Vorlage steht. Ein Wächter, der
    alles verwirft, leert nur die Karten (gemessen 30.08.26).
    """
    system = prompts.get("social_kritiker_system")
    user = prompts.render("social_kritiker_user", quelle=quelle[:60_000], text=text)
    try:
        resp = llm.chat_complete(
            model=MODEL, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=600, _feature="social_kritiker")
        roh = (resp.choices[0].message.content or "").strip()
        if roh.startswith("```"):
            roh = roh.strip("`")
            roh = roh[roh.find("{"):]
        antwort = json.loads(roh)
    except Exception:  # noqa: BLE001 — siehe Docstring
        return True, ""

    if antwort.get("gedeckt") is False:
        return False, " ".join(str(antwort.get("grund") or "ohne Grund").split())[:200]

    # „Gedeckt" gilt nur mit Beleg: Jedes genannte Zitat muss in der Quelle
    # stehen. Erfundene Belege sind das eine Schlupfloch dieser Bauart.
    for zitat in (antwort.get("belege") or []):
        if not _steht_da(str(zitat), quelle):
            return False, f"Beleg steht nicht in der Quelle: „{str(zitat)[:80]}“"
    return True, ""
