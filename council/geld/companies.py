"""Der Beteiligungsbericht — die städtischen Gesellschaften einzeln.

Die KI-Frage kannte bis 09/2026 nur die SUMME dieser Einheiten: Der
Gesamtabschluss (`konzern`) sagt, wie viel Klinikum, Busse und Bäder zusammen
bewegen. „Wem gehört die GSG?", „Wie viel Verlust macht die VWG?", „Wer sitzt
im Aufsichtsrat?" beantwortete er nicht — die Antwort kam aus dem
Ergebnishaushalt, in dem keine dieser Zahlen steht.

Diese Facette ist die Gegenrichtung: **eine Gesellschaft, nicht die Summe.**
Sie spiegelt den Steckbrief von /haushalt/konzern
(`components/haushalt/beteiligung-steckbrief.tsx`) und zeigt darum genau das,
was dort steht — Zahlenkopf, Anteile, Aufsichtsorgan —, nicht mehr.

DREI GRENZEN, DIE IM BAUSTEIN SELBST STEHEN MÜSSEN:

* **Die Zahlen gehören der Gesellschaft, nicht dem Haushalt.** Ein
  Jahresergebnis der VWG ist kein Haushaltsposten und mit keinem Betrag des
  Stadthaushalts verrechenbar. Was im Haushalt ankommt, sagt der Abschnitt
  „Was sie für den städtischen Haushalt bedeutet" — und der steht als Satz
  der Quelle da, nicht als unsere Rechnung.
* **Ein Minus ist keine Note.** Ein Verkehrsbetrieb mit Verlust erfüllt
  seinen Auftrag; die Seite verbietet sich dafür ausdrücklich jede
  Bewertungsfarbe (`section-gesellschaften.tsx`). Im Prompt tut das ein Satz.
* **Personen nur, soweit der Bericht sie zuordnet.** ``roles_assignable = 0``
  heißt: ALLE Ämter dieser Gesellschaft sind unbekannt (die Namen-/Ämter-Probe
  des Parsers riss), nicht „die meisten". Dann steht hier kein Amt.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "companies"

#: Die Kurznamen der Gesellschaften, die im Bestand WIRKLICH vorkommen
#: (gemessen an `council_companies`, Berichte 2022–2024). Bewusst kuratiert
#: statt aus der Datenbank gezogen: Erkannt wird am rohen Fragewortlaut, und
#: der läuft ohne Datenbank — sonst hinge die Facette an einem Ingest-Stand.
#:
#: NICHT DRIN, obwohl naheliegend: „Stadtwerke" (die gibt es in Oldenburg
#: nicht, Versorger ist die EWE), „OOWV", „Flughafen", „EWE" — die EWE ist
#: Mitgesellschafterin der VWG, aber keine Beteiligung der Stadt, und „EWE"
#: steckt außerdem in „bEWEgen".
#:
#: UND KEIN „stadion": Das Wort ist in Oldenburg ein Thema, keine Gesellschaft
#: („Wie ist der Stand beim Stadion?"). Die beiden Stadion-Gesellschaften
#: kommen über ihren vollen Namen.
_KURZNAMEN = (
    r"klinikum|volkshochschule|abfallwirtschaftsbetrieb|baederbetrieb|\bbaeder\b|"
    r"grossleitstelle|weser ems hall|technologie und gruenderzentrum|"
    r"oldenburg tourismus|tourismus und marketing|verkehr und wasser|"
    r"gebaeudewirtschaft|stadionplanungsgesellschaft|stadion oldenburg|"
    r"\bgsg\b|\bvwg\b|\bawb\b|\btgo\b|\bvhs\b|\botm\b|\bbbgo\b|\begh\b"
)

#: „Beteiligung" und „Gesellschaft" tragen im Deutschen zwei ganz andere
#: Bedeutungen, und beide sind in einem Ratskontext häufiger als die gemeinte:
#: die Bürgerbeteiligung am Bebauungsplan und die Gesellschaft als
#: Öffentlichkeit. Sie fallen VOR dem Abgleich weg — als Wort, nicht als
#: Nachbedingung: „Gibt es eine Bürgerbeteiligung?" enthält sonst weiterhin
#: „beteiligung" und feuert.
_NICHT = re.compile(
    r"\w*buergerbeteiligung|oeffentlichkeitsbeteiligung|planungsbeteiligung|"
    r"beteiligungsverfahren|traegerbeteiligung|elternbeteiligung|"
    r"beteiligungsformat|stadtgesellschaft|zivilgesellschaft|"
    r"gesellschaftlich\w*|gesellschaft als ganzes")
_TRIFFT = re.compile(
    r"beteiligungsbericht|\bbeteiligung(?:en)?\b|gesellschaft|\bgmbh\b|"
    r"\bmbh\b|\bggmbh\b|\bag\b|\baoer\b|anstalt oeffentlichen rechts|"
    r"tochtergesellschaft|tochterunternehmen|\btoechter\b|"
    r"wem gehoer|gesellschafter|anteilseigner|beteiligungsquote|"
    r"haelt die stadt|stadt haelt|aufsichtsrat|verwaltungsrat|"
    r"betriebsausschuss|geschaeftsfuehr|"
    r"staedtische\w* (?:unternehmen|betriebe|firmen)|kommunale\w* unternehmen|"
    + _KURZNAMEN)

#: Wörter, die die FACETTE auslösen und deshalb kein Suchbegriff sein können.
#: „Welche Beteiligungen hat die Stadt?" trüge sonst „Beteiligungen" in den
#: Abgleich — und träfe damit ausgerechnet die beiden Komplementär-GmbHs
#: („… Beteiligungs-GmbH"), also die zwei leersten Steckbriefe des Berichts
#: statt des Überblicks, nach dem gefragt war.
#: Die Kennzahl-Wörter stehen mit drin, und das ist keine Vorsicht, sondern
#: gemessen: „Jahresergebnis" hat den Wortstamm „jahres" und steckt damit in
#: jedem Zweck-Abschnitt, der irgendwo „Jahres…" schreibt — „Wie hoch war das
#: Jahresergebnis des Klinikums?" zog so die Bäderbetriebsgesellschaft mit.
_KEIN_SUCHWORT = {
    "beteiligung", "beteiligungen", "beteiligungsbericht", "gesellschaft",
    "gesellschaften", "gesellschafter", "gmbh", "mbh", "ggmbh", "aoer",
    "unternehmen", "firma", "firmen", "stadt", "staedtisch", "staedtische",
    "staedtischen", "oldenburg", "kommunal", "kommunale", "anteil", "anteile",
    "tochter", "toechter", "konzern", "eigenbetrieb", "eigenbetriebe",
    "jahresergebnis", "ergebnis", "bilanzsumme", "eigenkapitalquote",
    "kennzahl", "kennzahlen", "gewinn", "verlust", "jahr", "jahre",
}

#: Rechtsform aus der Gliederungsnummer des Berichts — dieselbe Herleitung wie
#: im Frontend (`lib/haushalt-beteiligungen.ts`, `rechtsform`): Der Bericht
#: gliedert selbst nach 2.2 Eigenbetriebe · 2.3 AöR · 2.4 privatrechtlich. Der
#: Name taugt dafür nicht („Abfallwirtschaftsbetrieb Stadt Oldenburg" trägt
#: sein „Eigenbetrieb" nicht im Namen).
_FORMEN = {"2": "Eigenbetrieb", "3": "Anstalt öffentlichen Rechts",
           "4": "GmbH / Co. KG"}
_KENNZAHL_TITEL = {"jahresergebnis": "Jahresergebnis",
                   "bilanzsumme": "Bilanzsumme",
                   "eigenkapitalquote": "Eigenkapitalquote"}
_OHNE_FORM = "ohne Form im Bericht"


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Fragt der Wortlaut nach einer städtischen Gesellschaft?

    ``facets`` bleibt ungenutzt, und das ist Absicht: `konzern` feuert bei
    „klinikum" ebenfalls. Beide sollen kommen — der Gesamtabschluss ist die
    Summe, diese Facette die einzelne Gesellschaft.
    """
    return bool(_TRIFFT.search(_NICHT.sub(" ", text)))


def _form(classification: str | None) -> str | None:
    """Rechtsform aus der Gliederungsnummer — ``None`` bei unbekannter Gruppe,
    damit nie eine falsche danebensteht."""
    teile = (classification or "").split(".")
    return _FORMEN.get(teile[1]) if len(teile) > 1 else None


def _glatt(text: str | None) -> str:
    """Der PDF-Extrakt als ein Fließtext.

    Der Bericht ist zweispaltig gesetzt und trennt am Zeilenende
    („Verkehrsleistun-\\ngen"). Im Prompt wäre das ein zerrissenes Wort, das
    ein Modell entweder falsch zitiert oder still repariert. Zusammenfügen ist
    keine Umformulierung — es stellt das Wort wieder her, das im Bericht
    steht."""
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", (text or "").replace("\r", ""))
    return re.sub(r"\s+", " ", t).strip()


def _kurz(text: str | None, grenze: int) -> str:
    """Der Anfang eines Abschnitts, am Satzende geschnitten."""
    t = _glatt(text)
    if len(t) <= grenze:
        return t
    punkt = t.rfind(". ", 0, grenze)
    if punkt > grenze * 0.4:
        return t[:punkt + 1]
    return t[:t.rfind(" ", 0, grenze)] + " …"


class Store(StoreBasis):
    """Store-Mixin: der Beteiligungsbericht zu einer Frage."""

    def companies_context(self, terms: list[str],
                          year: int | None = None) -> dict | None:
        """Bis zu zwei Gesellschaften zur Frage — oder der Überblick.

        Der Jahrgang hat hier ZWEI Achsen, und sie fallen auseinander: Der
        BERICHT ist immer der jüngste (er ist die Quelle, nicht der
        Gegenstand), das BEZUGSJAHR der Kennzahl kommt aus der Frage. Der
        Bericht 2024 führt Kennzahlen bis 2024 — für die Großleitstelle aber
        nur bis 2021. Deshalb trägt jede Kennzahl ihr eigenes Jahr, genau wie
        im Steckbrief der Seite.
        """
        try:
            bericht = self._conn.execute(
                "SELECT MAX(report_year) FROM council_companies").fetchone()[0]
            if bericht is None:
                return None
            jahr, weicht = geld.jahrgang(
                self._conn, "council_company_indicators", "year", year)
            reihen = self._conn.execute(
                "SELECT g.company, g.name, g.classification, g.page, g.herkunft_id, "
                "       t.text AS purpose "
                "FROM council_companies g "
                "LEFT JOIN council_company_texts t "
                "  ON t.report_year = g.report_year AND t.company = g.company "
                " AND t.section = 'business_purpose' "
                "WHERE g.report_year = ? ORDER BY g.classification",
                (bericht,)).fetchall()
            if not reihen:
                return None
            # `year_asked` steht NUR da, wenn der gefragte Jahrgang fehlt —
            # die Konvention aller Geld-Facetten seit 09/2026 (`qa._jahr_hinweis`).
            abweichung = {"year_asked": year} if weicht else {}
            treffer = self._passende(reihen, terms)
            if treffer:
                return {"report_year": bericht, "year": jahr, **abweichung,
                        "overview": None,
                        "companies": [self._gesellschaft(r, bericht, jahr)
                                      for r in treffer],
                        "beleg": self._beleg(treffer[0]["herkunft_id"])}
            return {"report_year": bericht, "year": jahr, **abweichung,
                    "companies": [],
                    "overview": self._ueberblick(reihen, bericht, jahr),
                    "beleg": self._beleg(reihen[0]["herkunft_id"])}
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None

    def _passende(self, reihen, terms: list[str]) -> list:
        """Die höchstens zwei Gesellschaften, die die Begriffe meinen.

        NUR DER HÖCHSTE PUNKTESTAND ZÄHLT, nicht die ersten zwei der Liste:
        Wer nach dem Klinikum fragt, trifft es mit zwei Begriffen und eine
        zweite Gesellschaft mit einem — die ritte sonst als gleichrangiger
        Steckbrief mit, obwohl die Frage sie nicht meint.

        Und ein SCHWACHES Signal ist der Überblick, keine Auswahl: Teilen sich
        vier oder mehr Gesellschaften denselben Punktestand 1, hat die Frage
        keine bestimmte gemeint — zwei davon zu zeigen hieße raten."""
        woerter = [w for w in terms
                   if geld.falte(w) not in _KEIN_SUCHWORT and len(w) > 2]
        punkte = [(self._trifft(f"{r['name']} {r['company']} {r['purpose'] or ''}",
                                woerter), r) for r in reihen]
        beste = max((p[0] for p in punkte), default=0)
        if not beste:
            return []
        treffer = [r for n, r in punkte if n == beste]
        if beste == 1 and len(treffer) >= 4:
            return []
        return treffer[:2]

    def _gesellschaft(self, r, bericht: int, jahr: int | None) -> dict:
        """Ein Steckbrief: Zahlen, Eigner, Aufsichtsorgan, Haushaltsbezug."""
        kennzahlen = []
        for art in ("jahresergebnis", "bilanzsumme", "eigenkapitalquote"):
            k = self._conn.execute(
                "SELECT year, value, unit FROM council_company_indicators "
                "WHERE company = ? AND indicator = ? AND year <= ? "
                "ORDER BY year DESC LIMIT 1", (r["company"], art, jahr)).fetchone()
            if k:
                kennzahlen.append({"kind": art, **dict(k)})
        eigner = [dict(e) for e in self._conn.execute(
            "SELECT name, amount_eur, share_pct FROM council_company_owners "
            "WHERE report_year = ? AND company = ? ORDER BY sort_order",
            (bericht, r["company"])).fetchall()]
        personen = self._conn.execute(
            "SELECT committee, name, position, chair_role, roles_assignable "
            "FROM council_company_people WHERE report_year = ? AND company = ? "
            "ORDER BY sort_order", (bericht, r["company"])).fetchall()
        haushalt = self._conn.execute(
            "SELECT text FROM council_company_texts WHERE report_year = ? "
            "AND company = ? AND section = 'budget_impact'",
            (bericht, r["company"])).fetchone()
        return {
            "company": r["company"], "name": r["name"],
            "legal_form": _form(r["classification"]),
            "classification": r["classification"], "page": r["page"],
            "purpose": r["purpose"],
            "budget_impact": haushalt["text"] if haushalt else None,
            "indicators": kennzahlen, "owners": eigner,
            "body": self._gremium(personen),
        }

    @staticmethod
    def _gremium(personen) -> dict | None:
        """Das Aufsichtsorgan: Name, Größe, Vorsitz — und wie viele aus dem Rat.

        NICHT die ganze Liste. Zwölf Namen je Gesellschaft wären die Hälfte
        des Zeichenbudgets für eine Auskunft, die der Steckbrief der Seite
        vollständig und verlinkt zeigt; hier zählt, wer dem Gremium vorsitzt
        und wie stark der Rat darin vertreten ist."""
        if not personen:
            return None
        vorsitz = next((p for p in personen if p["chair_role"] == "chair"), None)
        namen = {p["committee"] for p in personen}
        return {
            "committee": namen.pop() if len(namen) == 1 else "Aufsichtsorgan",
            "count": len(personen),
            "chair": dict(vorsitz) if vorsitz else None,
            "council_members": sum(1 for p in personen
                                   if (p["position"] or "").startswith("Ratsmitglied")),
            "roles_assignable": all(p["roles_assignable"] for p in personen),
        }

    def _ueberblick(self, reihen, bericht: int, jahr: int | None) -> dict:
        """Ohne Begriffstreffer: wie viele, welche Form, welche die größten.

        Die Summe der Jahresergebnisse steht hier, weil „Was bringen die
        Beteiligungen zusammen?" ohne sie unbeantwortet bliebe — mit der Zahl,
        wie viele Gesellschaften sie trägt, und mit dem Satz im Baustein, dass
        sie NICHT das Konzernergebnis ist."""
        formen: dict[str, int] = {}
        for r in reihen:
            form = _form(r["classification"]) or _OHNE_FORM
            formen[form] = formen.get(form, 0) + 1
        namen = {r["company"]: r["name"] for r in reihen}
        groesste = []
        for k in self._conn.execute(
                "SELECT company, year, value FROM council_company_indicators "
                "WHERE indicator = 'bilanzsumme' AND year <= ? "
                "GROUP BY company HAVING year = MAX(year) "
                "ORDER BY value DESC LIMIT 5", (jahr,)).fetchall():
            if k["company"] not in namen:
                continue
            anteil = self._conn.execute(
                "SELECT share_pct FROM council_company_owners "
                "WHERE report_year = ? AND company = ? "
                "AND name LIKE 'Stadt Oldenburg%'",
                (bericht, k["company"])).fetchone()
            groesste.append({"name": namen[k["company"]], "year": k["year"],
                             "bilanzsumme": k["value"],
                             "share_pct": anteil["share_pct"] if anteil else None})
        summe = self._conn.execute(
            "SELECT SUM(value), COUNT(*) FROM council_company_indicators "
            "WHERE indicator = 'jahresergebnis' AND year = ?", (jahr,)).fetchone()
        return {"count": len(reihen), "forms": sorted(formen.items()),
                "largest": groesste,
                "results_sum": summe[0], "results_n": summe[1]}


def _kennzahl(k: dict) -> str:
    titel = _KENNZAHL_TITEL.get(k["kind"], k["kind"])
    wert = geld.de_prozent(k["value"]) if k["unit"] != "eur" else geld.de_betrag(k["value"])
    return f"{titel} {k['year']}: {wert}"


#: Die Null im Jahresergebnis ist eine ANGABE, keine fehlende Zahl — und ohne
#: diesen Satz die gefährlichste Zeile des Bausteins: „Wie viel Verlust macht
#: die VWG?" beantwortete ein Modell sonst mit „keinen". Wortgleich mit der
#: Einordnung der Seite (`lib/haushalt-beteiligungen.ts`, `einordnungFuer`).
_NULL_IST_VERTRAG = (
    "Die Null ist Vertragslage, kein ausgeglichenes Geschäft: Der Betrieb "
    "führt sein Ergebnis an die Stadt ab oder bekommt es ausgeglichen. Was "
    "ihn die Stadt kostet, sagt allein die Zeile „Für den Stadthaushalt“.")


def _gesellschaft_zeilen(g: dict, voll: bool) -> list[str]:
    """Ein Steckbrief. ``voll=False`` ist die zweite Gesellschaft: Sie steht
    zur Einordnung daneben, nicht als zweite Antwort — Zweck, Zahlen, Eigner,
    kein Gremium und kein Haushaltsbezug."""
    stelle = [t for t in (g.get("legal_form"),
                          f"Abschnitt {g['classification']}",
                          f"S. {g['page']}" if g.get("page") else None) if t]
    zeilen = [f"- {g['name']} ({', '.join(stelle)})"]
    if g.get("purpose"):
        zeilen.append("  - Zweck laut Bericht: "
                      + _kurz(g["purpose"], 170 if voll else 110))
    if g.get("indicators"):
        zeilen.append("  - " + "; ".join(_kennzahl(k) for k in g["indicators"]))
    if any(k["kind"] == "jahresergebnis" and k["value"] == 0
           for k in g.get("indicators") or []):
        zeilen.append(f"  - {_NULL_IST_VERTRAG}")
    eigner = [f"{e['name']} {geld.de_prozent(e['share_pct'])}" for e in (g.get("owners") or [])
              if e.get("share_pct") is not None]
    if eigner:
        rest = len(eigner) - 3
        zeilen.append("  - Eigner: " + ", ".join(eigner[:3])
                      + (f" und {rest} weitere" if rest > 0 else ""))
    if not voll:
        return zeilen
    if g.get("budget_impact"):
        zeilen.append(f"  - Für den Stadthaushalt: {_kurz(g['budget_impact'], 200)}")
    k = g.get("body")
    if k:
        satz = f"  - {k['committee']}: {k['count']} Mitglieder"
        if k.get("chair"):
            amt = (f" ({k['chair']['position']})"
                   if k["roles_assignable"] and k["chair"].get("position") else "")
            satz += f", Vorsitz {k['chair']['name']}{amt}"
        if k.get("council_members"):
            satz += f", davon {k['council_members']} Ratsmitglieder"
        zeilen.append(satz + ". Weitere Namen stehen nur im Bericht — nenne keine.")
    return zeilen


def _ueberblick_zeilen(u: dict, jahr: int | None) -> list[str]:
    zeilen = [f"- {u['count']} Gesellschaften und Betriebe führt der Bericht: "
              + ", ".join(f"{n}× {form}" for form, n in u["forms"])]
    for g in u["largest"]:
        anteil = (f", Anteil der Stadt {geld.de_prozent(g['share_pct'])}"
                  if g.get("share_pct") is not None else "")
        zeilen.append(f"  - {g['name']}: Bilanzsumme {geld.de_betrag(g['bilanzsumme'])} "
                      f"({g['year']}){anteil}")
    if u.get("results_sum") is not None and u.get("results_n"):
        zeilen.append(f"- Die {u['results_n']} Jahresergebnisse, die der Bericht für "
                      f"{jahr} nennt, ergeben zusammen {geld.de_betrag(u['results_sum'])}. "
                      "Das ist NICHT das Konzernergebnis — der Gesamtabschluss rechnet "
                      "die Verflechtungen zwischen den Einheiten erst heraus.")
    return zeilen


def _kopf_beleg(data: dict) -> dict | None:
    """Welche Fundstelle in den Kopf gehört.

    Die volle nur bei EINER Gesellschaft. Stehen zwei nebeneinander — oder
    der Überblick über alle —, pinnte die Fundstelle der ersten den ganzen
    Baustein auf einen Abschnitt, in dem die anderen nicht stehen. Dann nennt
    der Kopf nur das Dokument; der Abschnitt steht an jeder Gesellschaft."""
    b = data.get("beleg")
    if not b:
        return None
    if len(data.get("companies") or []) == 1:
        return b
    return {"label": b.get("label"), "as_of": b.get("as_of")}


def block(data: dict | None) -> str:
    """Der Prompt-Baustein — Steckbrief oder Überblick."""
    if not data or not (data.get("companies") or data.get("overview")):
        return ""
    zeilen = ([z for i, g in enumerate(data["companies"])
               for z in _gesellschaft_zeilen(g, i == 0)]
              if data.get("companies")
              else _ueberblick_zeilen(data["overview"], data.get("year")))
    if data.get("year_asked"):
        zeilen.append(f"- ACHTUNG: Für {data['year_asked']} führt der Bericht keine "
                      f"Kennzahlen; oben steht der jüngste Stand ({data['year']}). Sag "
                      f"das ausdrücklich dazu und gib die Zahlen nicht für "
                      f"{data['year_asked']} aus.")
    return (f"\nSTÄDTISCHE GESELLSCHAFTEN (Beteiligungsbericht {data['report_year']} "
            "nach § 151 NKomVG).\nNutze das, wenn nach einer einzelnen Gesellschaft, "
            "ihren Eignern, ihren Zahlen\noder ihren Aufsichtsorganen gefragt ist. "
            "DIESE ZAHLEN GEHÖREN DER GESELLSCHAFT,\nnicht dem Stadthaushalt: Sie "
            "stehen in keinem Haushaltsplan und sind mit dessen\nBeträgen nicht "
            "verrechenbar. Was im Haushalt ankommt, steht — wenn überhaupt —\nin der "
            "Zeile „Für den Stadthaushalt“. Ein Verlust ist hier keine Note: Bus und\n"
            "Bäder sollen bezahlbar sein, nicht profitabel. Nie mit [id] zitieren"
            + geld.beleg_text(_kopf_beleg(data), stand=True) + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="companies_context", erkennen=recognize, block=block,
    # 1.834 Zeichen an der dev-Datenbank gemessen (VWG mit abweichendem
    # Jahrgang, also mit jedem optionalen Satz); die Grenze liegt knapp
    # darüber. Zwei Gesellschaften nebeneinander bleiben darunter, weil die
    # zweite nur ihre Zahlen trägt (s. `_gesellschaft_zeilen`).
    mixin=Store, rang=40, grenze=1900,
    probefrage="Wem gehört die GSG Oldenburg?")
