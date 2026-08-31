"""Zuwendungen an die Stadt — was Menschen und Firmen dem Haushalt schenken.

Achtmal bis zwölfmal im Jahr steht derselbe Punkt auf der Tagesordnung, seit
Februar 2018 lückenlos: „Annahme von Zuwendungen durch den Rat" bzw. „… durch
den Verwaltungsausschuss". Der Beschluss ist immer derselbe Satz —

    „Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von
    insgesamt 140.664,24 EUR laut anliegender Liste an."

— und die Summe darin ist das Einzige, was der Bestand über diese Einnahmeart
hergibt. Sie ist eine Auskunft, die sonst nirgends steht: Weder die
Ergebnisrechnung noch der Haushaltsplan weisen Spenden getrennt aus.

Was hier **nicht** steht, und warum
------------------------------------
**Die Namen der Gebenden.** Wer gespendet hat und wofür, steht ausschließlich
in der Anlage „Zuwendungsliste" — und die ist nicht im Bestand. Wir zeigen
deshalb die Summe und sagen, dass wir das „Wer" nicht haben. Das ist keine
technische Lücke, die sich später schließt: Es sind echte Menschen und Firmen,
die geben, und der Ratsbeschluss macht die **Summe** öffentlich, nicht die
Liste. Wer diese Datei erweitert, erweitert sie nicht um Namen.

Wie ein Betrag hier hereinkommt
--------------------------------
Der Betrag ist der, den das **Protokoll** festhält — was der Rat bzw. der
Verwaltungsausschuss beschlossen hat, nicht was die Verwaltung vorschlug. Der
Unterschied ist nicht theoretisch: In Vorlage 18/0587 schlug die Verwaltung
22.500 EUR vor, der Rat nahm 2.500 EUR an — „(ohne lfd. Nr. 2)" steht im
Protokoll. Wer den Vorschlag nähme, buchte 20.000 EUR, die nie angenommen
wurden.

Zwei Proben tragen die Reihe, und sie sind verschieden stark:

1. **Zweitstelle** (Pflicht, :data:`ZWEITSTELLE`). Dieselbe Vorlage nennt den
   Betrag ein zweites Mal — im Abschnitt „Auswirkungen a) Finanzen" (Layout ab
   2022) bzw. „Finanzielle Auswirkungen" (davor). Entweder identisch, oder als
   Zerlegung, die sich auf den **Cent** aufaddieren muss:

       Beschluss: 3.820 Euro
       a) Finanzen: Mehrerträge 2.300 Euro + sachliche Zuwendungen 1.520 Euro

   Ohne diese Probe kommt eine Vorlage nicht herein. Das ist der Grund, warum
   fünf Vorlagen fehlen und die Reihe das sagt, statt sie stillschweigend
   mitzuzählen.
2. **Protokollabgleich** (zusätzlich, :data:`PROTOKOLLABGLEICH`). Der
   Beschlussvorschlag der Vorlage nennt denselben Betrag wie das Protokoll —
   zwei getrennt erzeugte Dokumente. Wo er das nicht tut, hat der Rat die Liste
   geändert oder eines der beiden Dokumente trägt einen Zahlendreher; beides
   ist ein Befund und kein Grund, die Zeile zu verwerfen, die ihre Zweitstelle
   hat.

Die beiden Layouts
-------------------
Der Abschnitt heißt seit dem Vorlagen-Umbau „Auswirkungen: a) Finanzen"; davor
hieß er „Finanzielle Auswirkungen:". Gerechnet wird in beiden gleich. Eine
frühere Messung, die nur das neue Layout kannte, kam auf 64 belegte Zeilen und
88 Vorlagen „ohne Struktur" — die Struktur war da, sie hieß nur anders.

Drei Reparaturen am Textextrakt
--------------------------------
Die Vorlagen-PDFs zerlegen gelegentlich Zahl oder Währungswort. Alle drei
Reparaturen sind eng gefasst, damit sie nie zwei getrennte Zahlen verbinden:

* ``E UR`` / ``Eu ro`` — Leerzeichen **im Währungswort** (Vorlage 19/0821).
* ``154 .472,86`` — Leerzeichen **vor** dem Tausenderpunkt, nie dahinter
  (Vorlage 19/0293). „Teilhaushalt 06. 500,00 Euro" bliebe damit zwei Zahlen.
* ``6.000,-`` — die Kurzform für ``6.000,00`` (Protokoll zu 19/0623).

Wer Zuständigkeit erklären will
--------------------------------
Die Schwellen stehen wörtlich in 88 der 215 Beschlusszeilen (:data:`SCHWELLEN`)
und erklären nebenbei, wie kommunale Zuständigkeit funktioniert: bis 100 Euro
entscheidet der Oberbürgermeister allein, bis 2.000 Euro der
Verwaltungsausschuss, darüber der Rat. Maßgeblich ist die **einzelne**
Zuwendung, nicht die Summe der Liste — eine VA-Vorlage darf deshalb in der
Summe über 2.000 Euro liegen (22/0020: 2.746,20 Euro). Wer die Summe gegen die
Schwelle prüfen wollte, prüfte etwas, das die Regel gar nicht behauptet.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

#: Der Titel, an dem diese Vorlagen zu erkennen sind. Der Zusatz „ - Beschluss"
#: kommt vor und wird mitgenommen; die Einzahl („Annahme **einer** Zuwendung")
#: ebenso, sie ist dieselbe Sache mit einer Position weniger.
TITEL = re.compile(r"^Annahme\s+(?:von\s+Zuwendungen|einer\s+Zuwendung)\b", re.IGNORECASE)

#: Welches Gremium entscheidet — steht im Titel und nirgends sonst zuverlässig.
#: Die Sitzung, in der wir die Zeile finden, ist regelmäßig der vorberatende
#: Finanzausschuss (144 von 215 Zeilen); der Verwaltungsausschuss selbst tagt
#: nicht öffentlich und taucht im Bestand nicht als Sitzung auf.
_RAT = re.compile(r"durch\s+den\s+Rat\b", re.IGNORECASE)
_VA = re.compile(r"durch\s+den\s+Verwaltungsausschuss\b", re.IGNORECASE)

#: Wer über welche Zuwendung entscheidet (§ 111 Abs. 8 NKomVG, § 26 KomHKVO,
#: Ratsentscheidung vom 22. Februar 2010). Bezugsgröße ist die **einzelne**
#: Zuwendung. Wörtlich zitiert in 88 der 215 Beschlusszeilen.
SCHWELLEN: tuple[tuple[str, float | None, float | None], ...] = (
    ("Oberbürgermeister", None, 100.0),
    ("Verwaltungsausschuss", 100.01, 2000.0),
    ("Rat", 2000.01, None),
)

#: Die Fundstelle der Zweitstelle, in beiden Layouts.
FUNDSTELLE = 'Beschlussvorschlag und Abschnitt „Auswirkungen a) Finanzen“ ' \
             '(ältere Vorlagen: „Finanzielle Auswirkungen“)'

ZWEITSTELLE = "spenden_zweitstelle"
PROTOKOLLABGLEICH = "spenden_protokollabgleich"

# --- Zahlen lesen ----------------------------------------------------------
# Die drei Extrakt-Reparaturen stecken hier und nirgends sonst; council/money.py
# bleibt davon unberührt, weil sie auf genau diese Dokumentfamilie geeicht sind.
_NUM = r"(?:\d{1,3}(?:\s?\.\d{3})+|\d+)(?:,(?:\d+|-))?"
_CUR = r"(?:€|E\s?U\s?R|E\s?u\s?r\s?o)"
_BETRAG = re.compile(rf"({_NUM})\s*{_CUR}")

_VORSCHLAG = re.compile(r"Beschlussvorschlag\s*:?\s*(.{0,600})", re.IGNORECASE | re.DOTALL)
_FINANZ_NEU = re.compile(r"Auswirkungen\s*:?\s*\n?\s*a\)\s*Finanzen(.*?)(?=\bb\)\s*Klima|\Z)",
                         re.IGNORECASE | re.DOTALL)
_FINANZ_ALT = re.compile(r"Finanzielle\s+Auswirkungen\s*:?(.*?)"
                         r"(?=\n\s*In\s+Vertretung|\n\s*Anlage|\Z)",
                         re.IGNORECASE | re.DOTALL)

#: Auf den Cent, nicht auf den Euro: Die Zerlegungen gehen im Bestand exakt
#: auf. Eine Toleranz hier hieße, eine nicht aufgehende Rechnung zu übernehmen.
_CENT = 0.005


def de_zahl(roh: str) -> float | None:
    """„154 .472,86" → 154472.86, „6.000,-" → 6000.0."""
    s = roh.strip().replace(" ", "").rstrip("-").rstrip(",")
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".") if "," in s else s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def betraege(text: str | None) -> list[float]:
    """Alle Euro-Beträge eines Textstücks, in Lesereihenfolge."""
    out = []
    for m in _BETRAG.finditer(text or ""):
        v = de_zahl(m.group(1))
        if v is not None:
            out.append(v)
    return out


def _erster(text: str | None) -> float | None:
    b = betraege(text)
    return b[0] if b else None


def committee(title: str | None) -> str | None:
    """„Rat" oder „Verwaltungsausschuss" — aus dem Titel, sonst nirgendwo."""
    t = title or ""
    if _RAT.search(t):
        return "Rat"
    if _VA.search(t):
        return "Verwaltungsausschuss"
    return None


def zustaendig(amount: float) -> str:
    """Welches Gremium eine **einzelne** Zuwendung dieser Höhe annimmt."""
    for name, unten, oben in SCHWELLEN:
        if (unten is None or amount >= unten) and (oben is None or amount <= oben):
            return name
    return SCHWELLEN[-1][0]


def finanzabschnitt(raw: str | None) -> tuple[str | None, str | None]:
    """Der Abschnitt mit der Zweitstelle plus die Angabe, welches Layout griff."""
    if not raw:
        return None, None
    for rx, name in ((_FINANZ_NEU, "neu"), (_FINANZ_ALT, "alt")):
        m = rx.search(raw)
        if m:
            return m.group(1), name
    return None, None


def pruefe_zweitstelle(kopf: float | None, section: str | None) -> tuple[str | None, list[float]]:
    """Nennt der Finanz-Abschnitt denselben Betrag? („identical"/„split")"""
    teile = betraege(section) if section else []
    if kopf is None or not teile:
        return None, teile
    if any(abs(t - kopf) < _CENT for t in teile):
        return "identical", teile
    if abs(sum(teile) - kopf) < _CENT:
        return "split", teile
    return None, teile


def erkenne(title: str | None) -> bool:
    """Ist das eine Zuwendungs-Annahme?"""
    return bool(TITEL.search((title or "").strip()))


def lies(zeilen: Iterable[dict]) -> dict:
    """Beschlusszeilen → geprüfte Spendenreihe.

    Erwartet je Zeile: ``template_number``, ``title``, ``official_text``, ``outcome``,
    ``sitzung`` (ISO-Datum), ``raw_text`` (Volltext der Vorlage),
    ``document_id``, ``dokument_url``.

    Liefert:

    * ``vorlagen`` — je Vorlage **eine** Zeile, geprüft, mit ``probes``,
      ``amount``, ``year``, ``committee``, ``layout``.
    * ``verworfen`` — je Eintrag ``{template_number, reason}``; der Grund ist ein
      vollständiger Satz und für Leser*innen geschrieben.
    * ``years`` — die Jahresreihe, je Jahr Summe und Zahl der Vorlagen.
    * ``probes`` — Zähler, was wie oft griff.
    """
    kandidaten: list[dict] = []
    verworfen: list[dict] = []
    zaehler: Counter = Counter()

    for z in zeilen:
        if not erkenne(z.get("title")):
            continue
        zaehler["zeilen"] += 1
        nr = z.get("template_number")
        raw = z.get("raw_text")

        if (z.get("outcome") or "") != "angenommen":
            verworfen.append({"template_number": nr, "sitzung": z.get("sitzung"),
                              "reason": "Der Tagesordnungspunkt wurde nicht beschlossen — "
                                       "angenommen wurde nichts, also ist auch nichts "
                                       "eingenommen worden."})
            zaehler["nicht_beschlossen"] += 1
            continue

        kopf = _erster(z.get("official_text"))
        if kopf is None:
            verworfen.append({"template_number": nr, "sitzung": z.get("sitzung"),
                              "reason": "Das Protokoll hält für diese Sitzung keinen Betrag "
                                       "fest, sondern nur, dass angenommen wurde."})
            zaehler["ohne_protokollbetrag"] += 1
            continue

        mv = _VORSCHLAG.search(raw) if raw else None
        vorschlag = _erster(mv.group(1)) if mv else None
        section, layout = finanzabschnitt(raw)
        art, teile = pruefe_zweitstelle(kopf, section)

        if not art:
            verworfen.append({"template_number": nr, "sitzung": z.get("sitzung"),
                              "reason": _grund(raw, section, kopf, vorschlag, teile)})
            zaehler["ohne_zweitstelle"] += 1
            continue

        probes = [ZWEITSTELLE]
        if vorschlag is not None and abs(vorschlag - kopf) < _CENT:
            probes.append(PROTOKOLLABGLEICH)
            zaehler["protokollabgleich"] += 1
        zaehler[f"zweitstelle_{art}"] += 1
        zaehler[f"layout_{layout}"] += 1

        kandidaten.append({
            "template_number": nr, "amount": kopf, "sitzung": z.get("sitzung"),
            "year": int(str(z.get("sitzung"))[:4]), "committee": committee(z.get("title")),
            "layout": layout, "second_mention": art, "teile": len(teile),
            "probes": probes, "document_id": z.get("document_id"),
            "dokument_url": z.get("dokument_url"),
            "in_plenary": z.get("gremiensitzung") == "Rat",
        })

    # Je Vorlage bleibt eine Zeile: dieselbe Liste wird im vorberatenden
    # Ausschuss und im Rat behandelt. Die Rats-Zeile schlägt die Ausschuss-Zeile,
    # sonst die frühere — beide nennen denselben Betrag (im Bestand ohne
    # Ausnahme geprüft), aber die Rats-Zeile ist die Entscheidung.
    je_vorlage: dict[str, dict] = {}
    for k in sorted(kandidaten, key=lambda k: (not k["in_plenary"], k["sitzung"] or "")):
        je_vorlage.setdefault(k["template_number"], k)
    vorlagen = sorted(je_vorlage.values(), key=lambda k: (k["sitzung"] or "", k["template_number"]))

    years: dict[int, dict] = {}
    for v in vorlagen:
        e = years.setdefault(v["year"], {"year": v["year"], "amount": 0.0, "vorlagen": 0,
                                         "rat": 0, "verwaltungsausschuss": 0})
        e["amount"] += v["amount"]
        e["vorlagen"] += 1
        if v["committee"] == "Rat":
            e["rat"] += 1
        elif v["committee"] == "Verwaltungsausschuss":
            e["verwaltungsausschuss"] += 1
    for e in years.values():
        e["amount"] = round(e["amount"], 2)

    return {
        "vorlagen": vorlagen,
        "verworfen": verworfen,
        "years": [years[j] for j in sorted(years)],
        "probes": dict(zaehler),
    }


def euro(amount: float) -> str:
    """1234567.8 → „1.234.567,80" — deutsche Schreibweise für Erklärsätze."""
    return f"{amount:,.2f}".translate(str.maketrans({",": ".", ".": ","}))


def _grund(raw, section, kopf, vorschlag, teile) -> str:
    """Warum diese Zeile draußen bleibt — als Satz, nicht als Fehlercode.

    **Je Zeile steht hier nur, was an ihr besonders ist.** Der
    Auseinander-Fall („Vorschlag 22.500, Protokoll 2.500") hat bis 24.08.2026
    seine Deutung mitgetragen — „entweder hat der Rat die Liste geändert oder
    eines der beiden Dokumente trägt einen Zahlendreher; welches, sagt der
    Bestand nicht". Der Satz gilt für **jeden** Fall dieser Art und stand
    deshalb in vier von sechs Lücken-Feldern wörtlich untereinander (Tims
    Befund 24.08.). Er gehört einmal über die Liste, nicht sechsmal hinein;
    die Anzeige trägt ihn jetzt dort (``/haushalt/einnahmen``).

    Die Regel dahinter, für alle künftigen Gründe: Was an dieser einen Zeile
    steht, kommt hierher — was für die ganze Kategorie gilt, gehört an die
    Stelle, die die Kategorie überschreibt."""
    if not raw:
        return ("Der Volltext dieser Vorlage liegt nicht vor; damit gibt es keine "
                "zweite Stelle, an der sich der Betrag prüfen ließe.")
    if not section:
        return ("Die Vorlage führt keinen Abschnitt zu den finanziellen "
                "Auswirkungen — der Betrag steht nur ein einziges Mal.")
    if vorschlag is not None and kopf is not None and abs(vorschlag - kopf) >= _CENT:
        return (f"Die Vorlage schlug {euro(vorschlag)} Euro vor, das Protokoll hält "
                f"{euro(kopf)} Euro fest.")
    if teile:
        return ("Die Teilbeträge des Finanz-Abschnitts ergeben zusammen nicht den "
                "beschlossenen Betrag; im Textextrakt der Vorlage fehlt mindestens "
                "eine Zahl.")
    return ("Der Finanz-Abschnitt der Vorlage nennt keinen Betrag, gegen den sich "
            "der beschlossene prüfen ließe.")


def probennachweis(result: dict) -> str:
    """Der Messwert für die Herkunft — Zahlen, keine Adjektive."""
    p = result["probes"]
    ident = p.get("zweitstelle_identisch", 0)
    zerl = p.get("zweitstelle_zerlegung", 0)
    return (f"{ident + zerl} von {p.get('zeilen', 0)} Beschlusszeilen tragen ihre "
            f"Zweitstelle ({ident} identisch, {zerl} als Zerlegung, die auf den Cent "
            f"aufgeht); {p.get('protokollabgleich', 0)} davon nennen denselben Betrag "
            f"auch im Beschlussvorschlag der Vorlage. Belegt sind damit "
            f"{len(result['vorlagen'])} Vorlagen; {len(result['verworfen'])} "
            f"Zeilen bleiben draußen und stehen mit ihrem Grund dabei.")
