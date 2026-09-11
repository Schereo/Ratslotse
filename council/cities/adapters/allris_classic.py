"""ALLRIS classic — die ``.asp``-Bauform, ohne Schnittstelle und ohne Wicket.

**Wofür.** Hildesheim (102 k Einwohner) fährt die ältere ALLRIS-Generation:
statische ``.asp``-Seiten, ISO-8859-1, keine Sitzung, kein Seitenzustand, kein
OParl. Nach der Wicket-Anwendung von ALLRIS 4 (``allris4_html.py``) ist das
die einfachere Welt — und deshalb ein eigener Dialekt, kein Sonderfall dort:
Die beiden teilen den Hersteller, aber keine einzige Adresse.

**Was gemessen wurde (11.09.2026, an Hildesheim).**

- **Der Index ist der Monatskalender, und er ist ein schlichter GET.**
  ``si010_e.asp?YY=2026&MM=09`` liefert die Sitzungen eines Monats. Kein
  Formular, kein Token, keine Blätterung — 10 bis 18 Sitzungen je Monat,
  Historie ab etwa 2007. (Es gäbe auch ``si018.asp``, aber das ist ein POST
  mit einem ``STATA``-Token aus der Seite; der Kalender kostet dasselbe und
  hat nichts davon.)
- **Der Vorlagentext steht IN der Seite, nicht in einem PDF.**
  ``vo020.asp?VOLFDNR=…`` trägt den Sachverhalt als Fließtext. Es gibt an
  Vorlagen überhaupt keine Anlagen-Verweise. Deshalb ``fetch_files=False`` in
  der Registry und der Text über ``inline_texts`` — dieselbe Bahn, die
  Oldenburg und more! rubin schon benutzen.
- **Zu jedem beratenen Punkt gibt es einen „Auszug".**
  ``to020.asp?TOLFDNR=…`` trägt Wortprotokoll, Beschluss und
  Abstimmungsergebnis — je Punkt, schon getrennt. Gemessen an vier Sitzungen:
  **70 von 90 Punkten** haben einen. Das ist die Quelle für das „Warum", und
  sie kommt ohne das Schneiden einer Niederschrift aus. Dieser Adapter legt
  die Auszugs-Adresse als Kennung des Punktes ab; der Inhalt folgt in einem
  eigenen Schritt.

**Was hier NICHT gelesen wird.** Die Vorlagenseite nennt ``Verfasser:`` und
``Bearbeiter/-in:`` mit Namen von Verwaltungsmitarbeitenden. Die gehören
nicht in den Vergleich und werden deshalb gar nicht erst aufgenommen —
Ratsmitglieder dürfen benannt werden, Beschäftigte nicht.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, timedelta

from bs4 import BeautifulSoup

from council.cities.adapters._common import (VERSCHLOSSEN, attr,
                                             eindeutige_beratungen, normalize_title,
                                             zwillinge_zusammenfuehren)
from council.cities.model import (AgendaItem, Batch, Consultation, Meeting,
                                  Organization, Paper, org_kind, outcome,
                                  paper_kind)
from council.cities.oparl import OParlClient
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.adapters.allris_classic")

#: Wie viele Kalendermonate ein Lauf höchstens ansieht. 18 Jahre Historie sind
#: 216 Monate; die Kappe schützt nur gegen ein unsinniges ``since``.
MAX_MONATE = 400

#: Wie weit zurück Auszüge geholt werden. Derselbe Zeitraum wie bei den
#: Niederschriften der anderen Städte (``pipeline.PROTOCOL_MONTHS``): Das
#: „Warum" wird für die Ideen auf der Karte gebraucht, und die liegen in
#: diesem Fenster. Ohne Grenze wären es über 10.000 Abrufe — ein Auszug je
#: beratenem Punkt, seit 2007.
AUSZUG_MONATE = 24

#: Kürzer als das ist kein Wortprotokoll, sondern eine Formel („Kenntnis
#: genommen."). Ein Abschnitt daraus gäbe dem Modell nichts zu lesen.
MIN_WORTPROTOKOLL = 40

#: Die drei Abschnitte eines Auszugs. ALLRIS bettet sie als eigene, aus RTF
#: konvertierte HTML-Dokumente hinter Sprungmarken ein.
_AUSZUG_MARKEN = re.compile(r'<a\s+name="allris(WP|BS|AE)"\s*>\s*</a>')

#: „Beschluss:" am Anfang des Beschlusstextes ist die Beschriftung, nicht der
#: Beschluss.
_OHNE_LABEL = re.compile(r"^\s*(?:Beschluss|Beschlusstext|Abstimmungsergebnis)\s*:\s*")

#: Wo der Seitenfuß anfängt. Er hängt sonst am letzten Abschnitt.
_FUSS = re.compile(r"\bzur(?:ü|ue)ck\s+Nach\s+oben\b|\bSeite\s+drucken\b")

#: ``Ö 6.1``, ``N 17``, ``6.1`` — die Nummer eines Punktes. Der Buchstabe sagt,
#: ob der Punkt öffentlich ist: Hildesheim trennt **je Zeile**, nicht über eine
#: Zwischenüberschrift „Nicht öffentlicher Teil" wie andere Städte.
_TOP_NR = re.compile(r"^(?:(Ö|N)\s*)?(\d+(?:\.\d+)*)\.?$")

_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_UHRZEIT = re.compile(r"(\d{1,2}):(\d{2})")

#: Die Kopfzeilen, deren Wert übernommen wird.
_FELDER = ("Betreff", "Gremium", "Datum", "Status", "Zeit", "Anlass", "Raum",
           "Ort", "Vorlage-Art", "Vorlagenart", "Federführend",
           "Beschlussart", "Bezugsvorlage")

#: Felder, die ein anderes Feld **beenden**, deren Wert aber nie gespeichert
#: wird: ``Verfasser`` und ``Bearbeiter/-in`` nennen Namen von
#: Verwaltungsmitarbeitenden, und die gehören nicht in den Vergleich.
#:
#: **Sie müssen trotzdem in der Regel stehen.** Der erste Entwurf ließ sie
#: einfach weg — und damit lief der Wert des Feldes DAVOR bis zum nächsten
#: bekannten Wort weiter: Jede Vorlage bekam als Art
#: „Mitteilungsvorlage Verfasser: …" samt Namen. Ein weggelassenes Feld
#: verschwindet nicht, es wandert ins Nachbarfeld.
_GRENZEN = _FELDER + ("Verfasser", "Bearbeiter/-in", "Beteiligt",
                      "Sachbearbeiter/-in", "Aktenzeichen")


def _zahl(url: str, name: str) -> str | None:
    m = re.search(rf"{name}=(\d+)", url or "")
    return m.group(1) if m else None


def _text(knoten) -> str:
    return " ".join(knoten.get_text(" ", strip=True).split()) if knoten else ""




#: Die Bereiche der städtischen Seite, die um ALLRIS herumgebaut sind. Sie
#: machen 105 der 280 kB jeder Seite aus — und sie tragen eigene Verweise auf
#: ``au020.asp``, mit generischen Beschriftungen („Der Ortsrat" unter dem
#: Menüpunkt „Achtum / Uppen"). Gemessen: Ungefiltert gewinnen diese über die
#: echten Namen, und 42 von 198 Sitzungen finden ihr Gremium nicht mehr.
_RAHMEN = ("nolis_mobil_navigation", "mobil_navigation", "topnavi", "head")


def _inhalt(html: str) -> BeautifulSoup:
    """Die Seite ohne den Rahmen der Stadt-Website.

    ALLRIS classic wird hier in das Portal der Stadt eingebettet; alles außer
    dem Inhaltsbereich ist Navigation. Wer sie stehen lässt, liest die
    Menüpunkte mit — und das ist kein Schönheitsfehler, sondern eine stumme
    Verwechslung: Das Menü verlinkt dieselben ``au020.asp``-Adressen unter
    anderen Namen.
    """
    suppe = BeautifulSoup(html, "html.parser")
    for tag in suppe(["script", "style", "noscript"]):
        tag.decompose()
    for kenn in _RAHMEN:
        for el in suppe.find_all(id=kenn):
            el.decompose()
    for el in suppe.find_all("nav"):
        el.decompose()
    return suppe


def _grunddaten(suppe: BeautifulSoup) -> dict[str, str]:
    """``Gremium: … Datum: … Status: …`` — die Kopfzeilen einer Seite.

    Gelesen wird der **Fließtext**, an den bekannten Wörtern zerlegt, nicht
    eine bestimmte Tabellenauszeichnung. ALLRIS classic setzt die Paare je
    nach Seite verschieden; ein Umbau der Tabelle ändert am Fließtext nichts.
    """
    text = _text(suppe)
    gewollt = "|".join(re.escape(f) for f in _FELDER)
    grenze = "|".join(re.escape(f) for f in _GRENZEN)
    aus: dict[str, str] = {}
    for m in re.finditer(rf"\b({gewollt}):\s*(.*?)(?=\s\b(?:{grenze}):|$)", text):
        aus.setdefault(m.group(1), m.group(2).strip()[:400])
    return aus


def _iso(datum: str | None, zeit: str | None = None) -> str | None:
    """``Mo, 31.03.2025`` + ``18:00 - 22:00`` → ``2025-03-31T18:00:00``."""
    if not datum:
        return None
    d = _DATUM.search(datum)
    if not d:
        return None
    tag = f"{d.group(3)}-{d.group(2)}-{d.group(1)}"
    u = _UHRZEIT.search(zeit or "")
    return f"{tag}T{int(u.group(1)):02d}:{u.group(2)}:00" if u else tag


def _fenster(monate: int, heute: date | None = None) -> str:
    """Der früheste Tag, für den noch Auszüge geholt werden (ISO)."""
    h = heute or date.today()
    jahr, monat = h.year, h.month - monate
    while monat <= 0:
        jahr -= 1
        monat += 12
    return f"{jahr:04d}-{monat:02d}-01"


def _monate(seit: str) -> list[tuple[int, int]]:
    """Jeden Monat von ``seit`` bis heute, neueste zuerst.

    Neueste zuerst, damit ein abgebrochener Lauf die Gegenwart schon hat —
    dieselbe Überlegung wie bei der Rückwärtsblätterung von ALLRIS 4.
    """
    m = re.match(r"(\d{4})-(\d{2})", seit or "")
    start = date(int(m.group(1)), int(m.group(2)), 1) if m else date(2007, 1, 1)
    heute = date.today()
    aus: list[tuple[int, int]] = []
    lauf = date(heute.year, heute.month, 1)
    while lauf >= start and len(aus) < MAX_MONATE:
        aus.append((lauf.year, lauf.month))
        lauf = (lauf - timedelta(days=1)).replace(day=1)
    return aus


class AllrisClassicAdapter:
    """Liest ALLRIS classic (``.asp``) über die Oberfläche."""

    dialect = "allris_classic"

    # ---------------------------------------------------------------- Suche

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        """Es gibt keine ``system``-Adresse — die Registry nennt die Wurzel."""
        if not spec.system_url:
            raise ValueError(f"{spec.id}: keine Adresse in der Registry")
        wurzel = spec.system_url.rstrip("/")
        return {"body": {"id": wurzel, "web": wurzel}, "license": None,
                "name": spec.name}

    # -------------------------------------------------------------- Gremien

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]:
        """Die Gremien aus ``au010.asp`` — eine gewöhnliche Seite mit Links."""
        wurzel = body["id"]
        try:
            html = client.get_text(f"{wurzel}/au010.asp")
        except Exception as e:  # noqa: BLE001 — ohne Gremienliste läuft der Rest
            logger.info("%s: Gremienliste nicht lesbar (%s)", client.body_id,
                        type(e).__name__)
            return
        suppe = _inhalt(html)
        gesehen: set[str] = set()
        for a in suppe.find_all("a", href=re.compile(r"au020\.asp\?.*AULFDNR=\d+")):
            nr = _zahl(attr(a, "href"), "AULFDNR")
            name = _text(a)
            if not nr or not name or nr in gesehen:
                continue
            gesehen.add(nr)
            obj = {"id": f"{wurzel}/au020.asp?AULFDNR={nr}", "name": name}
            client.raw.put_raw_object(client.body_id, "organization", obj["id"], obj)
            yield obj
        logger.info("%s: %s Gremien", client.body_id, len(gesehen))

    # ------------------------------------------------------------ Sitzungen

    def iter_meetings(self, client: OParlClient, body: dict,
                      since: str) -> Iterator[dict]:
        """Monatskalender → Sitzungsseiten."""
        wurzel = body["id"]
        gesehen: set[str] = set()
        verschlossen = auszuege = 0
        grenze = _fenster(AUSZUG_MONATE)
        for jahr, monat in _monate(since):
            try:
                kalender = client.get_text(
                    f"{wurzel}/si010_e.asp?YY={jahr}&MM={monat:02d}")
            except Exception as e:  # noqa: BLE001 — ein Monat, nicht der Lauf
                logger.info("%s: Kalender %s-%02d nicht lesbar (%s)",
                            client.body_id, jahr, monat, type(e).__name__)
                continue
            for nr in sorted(set(re.findall(r"SILFDNR=(\d+)", kalender)), reverse=True):
                if nr in gesehen:
                    continue
                gesehen.add(nr)
                kennung = f"{wurzel}/to010.asp?SILFDNR={nr}"
                try:
                    html = client.get_text(kennung)
                except Exception as e:  # noqa: BLE001 — eine Sitzung, nicht der Lauf
                    logger.info("%s: Sitzung %s nicht lesbar (%s)", client.body_id,
                                nr, type(e).__name__)
                    continue
                if VERSCHLOSSEN in html:
                    verschlossen += 1
                obj = {"id": kennung, "silfdnr": nr, "html": html}
                client.raw.put_raw_object(client.body_id, "meeting", kennung, obj)
                yield obj
                auszuege += self._auszuege(client, wurzel, html, grenze)
        logger.info("%s: %s Sitzungen (%s nicht öffentlich), %s Auszüge",
                    client.body_id, len(gesehen), verschlossen, auszuege)

    def _auszuege(self, client: OParlClient, wurzel: str, sitzung_html: str,
                  grenze: str) -> int:
        """Die Auszüge einer Sitzung — das „Warum", je Punkt schon getrennt.

        **Nur im Fenster.** Ein Auszug je beratenem Punkt heißt seit 2007 über
        10.000 Abrufe; gebraucht wird das „Warum" für die Ideen auf der Karte,
        und die liegen in den letzten zwei Jahren (``AUSZUG_MONATE``).
        """
        kopf = _grunddaten(_inhalt(sitzung_html))
        datum = _iso(kopf.get("Datum"))
        if not datum or datum < grenze:
            return 0
        geholt = 0
        for nr in sorted(set(re.findall(r"to020\.asp\?[^\"\']*TOLFDNR=(\d+)",
                                        sitzung_html))):
            kennung = f"{wurzel}/to020.asp?TOLFDNR={nr}"
            try:
                html = client.get_text(kennung)
            except Exception as e:  # noqa: BLE001 — ein Auszug, nicht der Lauf
                logger.info("%s: Auszug %s nicht lesbar (%s)", client.body_id,
                            nr, type(e).__name__)
                continue
            if VERSCHLOSSEN in html:
                continue
            client.raw.put_raw_object(client.body_id, "excerpt", kennung,
                                      {"id": kennung, "tolfdnr": nr, "html": html})
            geholt += 1
        return geholt

    # ------------------------------------------------------------- Vorlagen

    def iter_papers(self, client: OParlClient, body: dict,
                    since: str) -> Iterator[dict]:
        """Die Vorlagen, die an den geholten Sitzungen hängen.

        Es gäbe auch ``vo040.asp`` als Gesamtliste. Sie ist die falsche
        Quelle: Der Vergleich fragt, was beraten wurde, und das steht an den
        Sitzungen — eine Vorlage ohne Beratung hat keinen Ort im Vergleich.
        """
        wurzel = body["id"]
        gesehen: set[str] = set()
        for roh in client.raw.raw_objects(client.body_id, "meeting"):
            for nr in re.findall(r"VOLFDNR=(\d+)", roh.get("html") or ""):
                if nr in gesehen:
                    continue
                gesehen.add(nr)
                kennung = f"{wurzel}/vo020.asp?VOLFDNR={nr}"
                try:
                    html = client.get_text(kennung)
                except Exception as e:  # noqa: BLE001 — eine Vorlage, nicht der Lauf
                    logger.info("%s: Vorlage %s nicht lesbar (%s)", client.body_id,
                                nr, type(e).__name__)
                    continue
                obj = {"id": kennung, "volfdnr": nr, "html": html}
                client.raw.put_raw_object(client.body_id, "paper", kennung, obj)
                yield obj

    # --------------------------------------------------------- Normalisieren

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        """Aus den abgelegten Seiten dieselben Objekte wie jeder OParl-Adapter."""
        meetings: list[Meeting] = []
        items: list[AgendaItem] = []
        papers: list[Paper] = []
        consultations: list[Consultation] = []
        organizations = [
            Organization(o["id"], body_id, o.get("name") or "", None,
                         org_kind(o.get("name") or ""))
            for o in raw.raw_objects(body_id, "organization")
            if isinstance(o, dict) and o.get("id")]
        gremien = {normalize_title(o.name): o.id for o in organizations}

        verschlossen = 0
        for roh in raw.raw_objects(body_id, "meeting"):
            html = roh.get("html")
            if not html:
                continue
            # Eine nichtöffentliche Sitzung wird kein Objekt — sonst entsteht
            # je Fall ein Geist ohne Datum und ohne Tagesordnung, der in jeder
            # Kennzahl mitzählt, als fehlten UNS die Daten.
            if VERSCHLOSSEN in html:
                verschlossen += 1
                continue
            m_id = roh["id"]
            suppe = _inhalt(html)
            kopf = _grunddaten(suppe)
            meetings.append(Meeting(
                m_id, body_id,
                gremien.get(normalize_title(kopf.get("Gremium", ""))),
                self._sitzungsname(suppe, kopf),
                _iso(kopf.get("Datum"), kopf.get("Zeit")),
                state_raw=kopf.get("Status")))
            items += self._punkte(suppe, m_id, consultations)
        if verschlossen:
            logger.info("%s: %s nichtöffentliche Sitzungen übersprungen",
                        body_id, verschlossen)

        # **Das Ergebnis steht an der VORLAGE, nicht an der Sitzung.** Die
        # Tagesordnung von ALLRIS classic hat keine Ergebnisspalte; was ein
        # Punkt ergeben hat, sagt allein die Beratungsfolge seiner Vorlage.
        ergebnis_je_station: dict[tuple[str, str], str] = {}

        for roh in raw.raw_objects(body_id, "paper"):
            html = roh.get("html")
            if not html or VERSCHLOSSEN in html:
                continue
            p_id = roh["id"]
            suppe = _inhalt(html)
            kopf = _grunddaten(suppe)
            art = kopf.get("Vorlage-Art") or kopf.get("Vorlagenart")
            stationen = self._beratungsfolge(suppe)
            daten = sorted(s["datum"] for s in stationen if s["datum"])
            papers.append(Paper(
                p_id, body_id, kopf.get("Betreff") or self._titel(suppe),
                reference=self._kennzeichen(suppe),
                date=daten[0] if daten else None,
                paper_type_raw=art, kind=paper_kind(art), web=p_id))
            for s in stationen:
                if s["sitzung"] and s["ergebnis"]:
                    ergebnis_je_station[(p_id, s["sitzung"])] = s["ergebnis"]

        # Erst jetzt, wo beide Seiten vorliegen: das Ergebnis an seinen Punkt
        # und an seine Beratung. Über die POSITION ersetzt, nicht über
        # `list.index` — die Objekte sind eingefroren, und nach dem ersten
        # Ersetzen fände `index` das alte nicht mehr.
        stelle_punkt = {a.id: i for i, a in enumerate(items)}
        for i, c in enumerate(consultations):
            silfdnr = (c.meeting_id or "").rsplit("SILFDNR=", 1)[-1]
            erg = ergebnis_je_station.get((c.paper_id, silfdnr))
            if not erg:
                continue
            consultations[i] = replace(c, role_raw=erg)
            j = stelle_punkt.get(c.agenda_item_id or "")
            if j is not None:
                items[j] = replace(items[j], result_raw=erg, outcome=outcome(erg))

        # **Der Auszug schlägt die Beratungsfolge.** Er nennt die
        # Beschlussart des Punktes selbst und gilt auch für Punkte ganz ohne
        # Vorlage — deshalb läuft er NACH dem Ergebnis aus der Vorlage.
        aus_auszug = self._aus_auszuegen(raw, body_id, items)
        if aus_auszug:
            logger.info("%s: %s Punkte aus ihrem Auszug ergänzt", body_id,
                        aus_auszug)

        batch = Batch(organizations=organizations, meetings=meetings,
                      agenda_items=items, papers=papers, files=[],
                      consultations=consultations)
        zwillinge = zwillinge_zusammenfuehren(batch)
        getrennt = eindeutige_beratungen(batch.consultations)
        if zwillinge or getrennt:
            logger.info("%s: %s Zwillinge zusammengeführt, %s Kennungen getrennt",
                        body_id, zwillinge, getrennt)
        return batch

    # ------------------------------------------------------------- Bausteine

    @staticmethod
    def _titel(suppe: BeautifulSoup) -> str:
        """Der Seitentitel ohne den Sortenvorsatz („Vorlage - 26/278 - …")."""
        roh = _text(suppe.title) if suppe.title else ""
        teile = [t.strip() for t in roh.split(" - ")]
        return teile[-1][:400] if len(teile) > 1 else roh[:400]

    @staticmethod
    def _kennzeichen(suppe: BeautifulSoup) -> str | None:
        """Das Aktenzeichen („26/278") aus dem Seitentitel."""
        m = re.search(r"\b(\d{2}/\d{3,4})\b", _text(suppe.title) if suppe.title else "")
        return m.group(1) if m else None

    @staticmethod
    def _sitzungsname(suppe: BeautifulSoup, kopf: dict[str, str]) -> str:
        """„Tagesordnung - Sitzung des Rates" → „Sitzung des Rates"."""
        roh = _text(suppe.title) if suppe.title else ""
        name = roh.split(" - ", 1)[1] if " - " in roh else roh
        return (name or kopf.get("Gremium") or "Sitzung")[:400]

    def _punkte(self, suppe: BeautifulSoup, meeting_id: str,
                consultations: list[Consultation]) -> list[AgendaItem]:
        """Die Tagesordnung aus der Tabelle mit der Klasse ``tl1``.

        **Gelesen wird über die Zellklassen, nicht über Spaltennummern.** Die
        Datenzeilen tragen mehr Zellen als die Kopfzeile (Platzhalter mit
        ``colspan``), ein Abzählen ginge also schief. ``text4`` ist die
        Nummer, der Betreff die erste Zelle mit Text danach.
        """
        tabelle = next((t for t in suppe.find_all("table")
                        if "tl1" in (t.get("class") or [])), None)
        if tabelle is None:
            return []
        raus: list[AgendaItem] = []
        pos = 0
        for tr in tabelle.find_all("tr"):
            nummer_zelle = tr.find("td", class_="text4")
            if nummer_zelle is None:
                continue
            m = _TOP_NR.match(_text(nummer_zelle))
            if not m:
                continue
            zellen = tr.find_all("td")
            betreff = next((_text(td) for td in zellen[1:]
                            if _text(td) and not _TOP_NR.match(_text(td))), "")
            if not betreff:
                continue
            pos += 1
            # **Die echte Kennung ist die Auszugs-Adresse.** Einen beratenen
            # Punkt gibt es unter ``to020.asp?TOLFDNR=…`` wirklich; nur
            # Punkte ohne Auszug brauchen eine gebaute, und die trägt dann
            # richtigerweise die Marke ``#top-`` (SYNTHETISCHE_KENNUNG).
            auszug = tr.find("a", href=re.compile(r"to020\.asp\?.*TOLFDNR=\d+"))
            tol = _zahl(attr(auszug, "href"), "TOLFDNR")
            wurzel = meeting_id.split("/to010.asp")[0]
            kennung = (f"{wurzel}/to020.asp?TOLFDNR={tol}" if tol
                       else f"{meeting_id}#top-{m.group(2)}")
            raus.append(AgendaItem(
                kennung, meeting_id, betreff, m.group(2), pos,
                public=(m.group(1) != "N")))
            # Die Beratung entsteht aus DERSELBEN Zeile wie ihr Punkt — die
            # Verbindung ist damit nie zu raten. Ihr Ergebnis trägt sie noch
            # nicht; das steht nur in der Beratungsfolge der Vorlage.
            vo = tr.find("a", href=re.compile(r"vo020\.asp\?.*VOLFDNR=\d+"))
            vol = _zahl(attr(vo, "href"), "VOLFDNR")
            if vol:
                consultations.append(Consultation(
                    f"{kennung}:vo{vol}", f"{wurzel}/vo020.asp?VOLFDNR={vol}",
                    meeting_id=meeting_id, agenda_item_id=kennung))
        return raus

    @staticmethod
    def _beratungsfolge(suppe: BeautifulSoup) -> list[dict]:
        """Die Stationen einer Vorlage: Gremium, Rolle, Datum, Sitzung, Ergebnis.

        ALLRIS setzt sie über **zwei Zeilen** je Station — die erste trägt
        Gremium und Rolle, die zweite Datum, Sitzungsname und das Ergebnis.
        Wer Zeile für Zeile liest, bekommt lauter halbe Stationen.
        """
        tabelle = next((t for t in suppe.find_all("table")
                        if t.get("class") is None
                        and t.find("a", href=re.compile(r"to010\.asp"))), None)
        if tabelle is None:
            return []
        raus: list[dict] = []
        offen: dict | None = None
        for tr in tabelle.find_all("tr"):
            zellen = [_text(td) for td in tr.find_all("td")]
            werte = [z for z in zellen if z]
            if not werte:
                continue
            sitzung = tr.find("a", href=re.compile(r"to010\.asp\?.*SILFDNR=\d+"))
            if sitzung is None:
                # Zeile A: Gremium und Rolle.
                offen = {"gremium": werte[0], "rolle": werte[1] if len(werte) > 1 else "",
                         "datum": None, "sitzung": "", "ergebnis": None}
                continue
            # Zeile B: Datum, Sitzungsname, Ergebnis — und sie schließt die
            # Station ab. Ohne offene Zeile A wäre sie eine halbe Station.
            if offen is None:
                continue
            offen["datum"] = _iso(werte[0] if werte else None)
            offen["sitzung"] = _zahl(attr(sitzung, "href"), "SILFDNR") or ""
            offen["ergebnis"] = werte[2] if len(werte) > 2 else None
            raus.append(offen)
            offen = None
        return raus

    # -------------------------------------------------------------- Auszüge

    @staticmethod
    def zerlege_auszug(html: str) -> dict[str, str]:
        """``{"WP": Wortprotokoll, "BS": Beschluss, "AE": Abstimmung}``.

        ALLRIS bettet die drei Abschnitte als eigene, **aus RTF konvertierte
        HTML-Dokumente** hinter Sprungmarken (``<a name="allrisWP">``) ein —
        verschachtelte ``<html>``-Bäume mitten in der Seite. Deshalb wird am
        Rohtext geschnitten und jedes Stück für sich geparst; ein einzelner
        Parser-Lauf über das Ganze verliert die Grenzen.
        """
        marken = [(m.group(1), m.end()) for m in _AUSZUG_MARKEN.finditer(html)]
        aus: dict[str, str] = {}
        for i, (kenn, start) in enumerate(marken):
            ende = marken[i + 1][1] if i + 1 < len(marken) else len(html)
            stueck = BeautifulSoup(html[start:ende], "html.parser")
            for tag in stueck(["script", "style"]):
                tag.decompose()
            text = " ".join(stueck.get_text(" ", strip=True).split())
            # Der Seitenfuß hängt sonst am letzten Abschnitt.
            schnitt = _FUSS.search(text)
            if schnitt:
                text = text[:schnitt.start()].strip()
            if text:
                aus[kenn] = text
        return aus

    def _aus_auszuegen(self, raw: CitiesStore, body_id: str,
                       items: list[AgendaItem]) -> int:
        """Ergebnis und Beschlusstext aus den Auszügen an ihre Punkte schreiben.

        Der Auszug ist die **bessere** Quelle als die Beratungsfolge der
        Vorlage: Er nennt die ``Beschlussart`` des Punktes selbst und gilt
        auch für Punkte ganz ohne Vorlage.
        """
        stelle = {a.id: i for i, a in enumerate(items)}
        getroffen = 0
        for roh in raw.raw_objects(body_id, "excerpt"):
            html = roh.get("html")
            i = stelle.get(roh.get("id") or "")
            if not html or i is None:
                continue
            kopf = _grunddaten(_inhalt(html))
            art = (kopf.get("Beschlussart") or "").strip()
            teile = self.zerlege_auszug(html)
            # Die Beschriftung gehört nicht in den Beschlusstext.
            beschluss = _OHNE_LABEL.sub("", teile.get("BS") or "", count=1).strip()
            if not art and not beschluss:
                continue
            # „(offen)" ist ALLRIS' Wort für „noch nichts entschieden" — als
            # Ergebnis geführt wäre es die Behauptung, es gäbe eines.
            echt = art if art and art != "(offen)" else ""
            items[i] = replace(
                items[i],
                result_raw=echt or items[i].result_raw,
                outcome=outcome(echt) if echt else items[i].outcome,
                resolution_text=beschluss or items[i].resolution_text)
            getroffen += 1
        return getroffen

    def auszug_abschnitte(self, raw: CitiesStore, body_id: str) -> list[tuple]:
        """Die Wortprotokolle als Abschnitte — das „Warum" ohne PDF-Schnitt.

        Zurück kommen Zeilen für ``put_protocol_sections``:
        ``(file_id, meeting_id, ord, agenda_item_id, number, title, text)``.
        ``file_id`` ist die Adresse des Auszugs — er IST das Dokument.

        Die Punkte werden hier **noch einmal** aus der Rohablage gebaut, statt
        sie aus der Hauptdatenbank zu lesen: Der Adapter kann es ohnehin, und
        so bleibt die Regel im Adapter, wo sie hingehört.
        """
        punkte: dict[str, AgendaItem] = {}
        for roh in raw.raw_objects(body_id, "meeting"):
            html = roh.get("html")
            if not html or VERSCHLOSSEN in html:
                continue
            for a in self._punkte(_inhalt(html), roh["id"], []):
                punkte[a.id] = a
        zeilen: list[tuple] = []
        for roh in raw.raw_objects(body_id, "excerpt"):
            html, kennung = roh.get("html"), roh.get("id") or ""
            punkt = punkte.get(kennung)
            if not html or punkt is None:
                continue
            # **Ein Abschnitt ist alles, was zu diesem Punkt passiert ist** —
            # Beratung, Beschluss und Abstimmung, so wie ihn der Schnitt einer
            # Niederschrift bei den anderen Städten auch liefert. Die drei
            # getrennt abzulegen hieße, dass das Modell zum „Warum" nur die
            # halbe Geschichte liest.
            teile = self.zerlege_auszug(html)
            wort = "\n\n".join(teile[k] for k in ("WP", "BS", "AE") if teile.get(k))
            if len(wort) < MIN_WORTPROTOKOLL:
                continue
            zeilen.append((kennung, punkt.meeting_id, punkt.position,
                           punkt.id, punkt.number, punkt.name, wort))
        return zeilen

    # ------------------------------------------------------------ Volltexte

    def inline_texts(self, raw: CitiesStore, body_id: str) -> Iterator[tuple[str, str]]:
        """Der Sachverhalt einer Vorlage — er steht in der Seite, nicht im PDF.

        An Hildesheims Vorlagen hängt **kein einziger** Datei-Verweis; der
        Text ist der Seiteninhalt. Geliefert wird er unter der Kennung der
        Vorlage selbst, so wie Oldenburg und more! rubin es tun.
        """
        for roh in raw.raw_objects(body_id, "paper"):
            html = roh.get("html")
            if not html or VERSCHLOSSEN in html:
                continue
            text = self._sachverhalt(_inhalt(html))
            if text:
                yield roh["id"], text

    @staticmethod
    def _sachverhalt(suppe: BeautifulSoup) -> str:
        """Alles ab „Sachverhalt:" bis zum Ende des inhaltlichen Teils."""
        text = _text(suppe)
        i = text.find("Sachverhalt:")
        if i < 0:
            return ""
        rumpf = text[i + len("Sachverhalt:"):].strip()
        # Der Formularblock am Ende gehört nicht zum Sachverhalt.
        for ende in ("Finanzielle Auswirkungen:", "Personelle Auswirkungen:",
                     "Demografische Auswirkungen:", "Nachverfolgung"):
            j = rumpf.find(ende)
            if j > 0:
                rumpf = rumpf[:j]
        return rumpf.strip()
