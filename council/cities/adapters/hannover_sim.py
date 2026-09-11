"""Hannover SIM — der Eigenbau auf Lotus Notes/Domino, ohne OParl.

**Wofür.** Hannover (535 k Einwohner, die größte Stadt im Vergleich) betreibt
kein ALLRIS, kein SessionNet, keine der vier Standard-Bauformen. Ihr
„Sitzungsmanagement" (SIM) ist ein IBM-Notes/Domino-Webserver
(`e-government.hannover-stadt.de/lhhsimwebre.nsf`), verlinkt von
`hannover.de/Leben-in-der-Region-Hannover/Politik`. Historie ab 2003,
öffentlich und ohne Wicket- oder Formular-Zustand — jede Seite ist ein
schlichtes GET.

**Ein zweiter Host existierte auch:** `ris.hannit.de/public/` — ALLRIS net,
betrieben vom städtischen IT-Dienstleister hannIT, ebenfalls von der
Rathaus-Seite verlinkt. Er trägt eine ausdrückliche Zugriffssperre gegen
automatisierte Zugriffe (ALTCHA-Challenge, „Zum Schutz vor automatisierten
Zugriffen"). Die wird nicht umgangen — dieselbe Regel wie bei Göttingens
Cloudflare-Sperre (s. ``docs/plan-cities-phase5.md``, PR 36c-Nachtrag):
eine bewusste Absage an automatisierten Zugriff ist eine Absage, keine
Aufgabe. Gelesen wird deshalb SIM.

**Drei Arten Gremien, drei Adressmuster** (gemessen 11.09.2026):

- **Ratsversammlung** (das Plenum): `Termine.xsp` ohne Parameter.
- **33 Ausschüsse**: `Termine.xsp?view=Termine&grem=<Kürzel>`, Kürzel aus
  `Ausschuesse.xsp`.
- **13 Stadtbezirksräte**: `Termine.xsp?view=Termine<Kürzel>` (kein
  ``grem=``, das Kürzel steht im ``view``-Wert selbst), Kürzel aus
  `AuswahlStadtbezirke.xsp`.

Alle drei Listen sind **eine** Seite ohne Blätterung — 189 bis 273 Sitzungen
je Gremium, älteste ab 2003, alles auf einem GET.

**Der Verwaltungsausschuss veröffentlicht keine einzige Sitzungsseite.** Er
steht in keiner der drei Listen und hat kein Kürzel; er taucht ausschließlich
als unverlinkter Text in der Beratungsfolge von Vorlagen auf
(``13.08.2026: Verwaltungsausschuss: Einstimmig`` — ohne ``<a>``). Seine
Beratungen werden trotzdem aufgenommen (ohne Sitzungs- oder Gremienbezug,
nur Datum und Ergebnis), aber es gibt für ihn keinen Adapter-seitigen
Umweg — was nicht veröffentlicht ist, bleibt unveröffentlicht.

**Eine Vorlage (Drucksache) trägt ihren Text selbst, wie in Hildesheim.**
Jede ``DS/…``-Seite hat einen Abschnitt „Inhalt der Drucksache" mit dem
vollständigen Text; eine ``Druckversion.pdf`` gibt es zusätzlich, aber sie
ist redundant. Deshalb ``fetch_files=False`` und Text über ``inline_texts``.

**Die Beratungsfolge (``Beratungsverlauf``) ist die einzige verlässliche
Ergebnisquelle.** Jede Station verlinkt — wenn die Sitzung veröffentlicht
ist — direkt auf deren Seite; darüber lässt sich Beratung und Ergebnis ohne
Titel-Abgleich eindeutig zuordnen (kein Raten wie bei anderen Städten).

**Tagesordnungspunkt-Seiten (``TOPS/…``) werden NICHT gelesen.** Sie dienen
nur als Kennung. Gemessen: 22 von 25 geprüften Punkten einer Sitzung tragen
auf ihrer eigenen Seite den Satz „Die zu diesem Tagesordnungspunkt
vorliegenden Dokumente und Beratungsergebnisse sind vertraulich und daher
nicht zur Veröffentlichung im Internet freigegeben" — direkt neben dem
Ergebnis, das die Seite trotzdem zeigt. Keine der 39 geprüften ``DS/…``-Seiten
trug diesen Satz; ihre Beratungsfolge ist ohne Einschränkung öffentlich.
Ergebnisse werden deshalb ausschließlich aus der Beratungsfolge der Vorlage
gelesen. Punkte ohne Vorlage (Formalpunkte, mündliche Berichte) bleiben ohne
Ergebnis — eine ehrliche Lücke, keine Vermutung über einen als vertraulich
bezeichneten Text.

**Eine Ergebnis-Schreibweise, die keine Zustimmungs- oder Ablehnungswörter
trägt:** reine Stimmenzahlen wie „6 Stimmen dafür, 5 Stimmen dagegen,
0 Enthaltungen". ``model.outcome`` kennt keine Zahlen; hier wird deshalb
direkt verglichen (dafür > dagegen → angenommen, dafür < dagegen →
abgelehnt, gleich → offen, keine Vermutung).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from council.cities.adapters._common import attr, normalize_title
from council.cities.model import (AgendaItem, Batch, Consultation, Meeting,
                                  Organization, Outcome, Paper, org_kind,
                                  outcome, paper_kind)
from council.cities.oparl import OParlClient
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.adapters.hannover_sim")

#: Eine Vorlagen-Nummer wie „1.", „1.1." — echte Tagesordnungspunkte.
#: Trifft NICHT auf römische Ziffern („I.", Abschnitts-Überschriften wie
#: „Ö F F E N T L I C H E R T E I L") und NICHT auf „24. ff." (die
#: gebündelte Marke für „Nichtöffentliche Tagesordnungspunkte" — Hannover
#: zeigt nichtöffentliche Punkte nie einzeln, nur diesen einen Sammelverweis
#: je Sitzung). Ein Filter auf dieses Muster erledigt beide Fälle zugleich,
#: ohne die Icon-Dateinamen des Seitenaufbaus zu kennen.
_TOP_NR = re.compile(r"^\d+(\.\d+)*\.?$")

_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_ZEIT = re.compile(r"(\d{1,2}):(\d{2})\s*Uhr")

#: Eine Beratungsfolge-Zeile: „DD.MM.YYYY: Gremium" oder
#: „DD.MM.YYYY: Gremium: Ergebnis". Das Ergebnis fehlt für zukünftige
#: Sitzungen, die noch keinen Termin haben; Zeilen wie „Zukünftig: …" (ganz
#: ohne Datum) sind noch nicht terminierte Überweisungen und werden nicht
#: erfasst — es gibt dafür noch keine Sitzung, an die sie gehören könnten.
_STATION_RE = re.compile(
    r"^(\d{2}\.\d{2}\.\d{4})\s*:\s*([^:]+?)\s*(?::\s*(.+))?$", re.S)

#: „6 Stimmen dafür, 5 Stimmen dagegen, 0 Enthaltungen" — als GANZER Text,
#: nicht als Teilstück: Eine erzählende Passage wie „… fand bei 4 Ja-Stimmen,
#: 6 Nein-Stimmen … nicht die erforderliche 2/3-Mehrheit" enthält ähnliche
#: Zahlen, ist aber kein Beschlussergebnis, sondern eine Verfahrensfrage
#: (Dringlichkeit einer TO-Erweiterung) — ein Teiltreffer würde sie falsch
#: als Sachentscheidung einordnen.
_STIMMEN_RE = re.compile(
    r"^(\d+)\s*Stimmen\s+dafür,\s*(\d+)\s*Stimmen\s+dagegen"
    r"(?:,?\s*(?:und\s+)?\d*\s*Enthaltung(?:en)?)?\.?$", re.I)


def _text(knoten) -> str:
    return " ".join(knoten.get_text(" ", strip=True).split()) if knoten else ""


def _iso(datum: str | None, zeit: str | None = None) -> str | None:
    d = _DATUM.search(datum or "")
    if not d:
        return None
    tag = f"{d.group(3)}-{d.group(2)}-{d.group(1)}"
    u = _ZEIT.search(zeit or "")
    return f"{tag}T{int(u.group(1)):02d}:{u.group(2)}:00" if u else tag


def _ergebnis_einordnen(text: str) -> Outcome:
    """Ergebnistext → Outcome — mit einem numerischen Sonderfall.

    Reine Stimmenzahlen ohne Zustimmungs- oder Ablehnungswort kennt
    ``model.outcome`` nicht; hier werden sie direkt verglichen. Bei
    Stimmengleichheit wird NICHTS vermutet — Hannovers Geschäftsordnung dazu
    ist nicht gemessen, und eine geratene Regel wäre in beide Richtungen ein
    erfundenes Ergebnis.
    """
    m = _STIMMEN_RE.match(text.strip())
    if m:
        dafuer, dagegen = int(m.group(1)), int(m.group(2))
        if dafuer > dagegen:
            return Outcome.ACCEPTED
        if dafuer < dagegen:
            return Outcome.REJECTED
        return Outcome.NONE
    return outcome(text)


class HannoverSimAdapter:
    """Liest Hannovers Notes/Domino-Sitzungsmanagement."""

    dialect = "hannover_sim"

    # ---------------------------------------------------------------- Suche

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        if not spec.system_url:
            raise ValueError(f"{spec.id}: keine Adresse in der Registry")
        wurzel = spec.system_url.rstrip("/")
        return {"body": {"id": wurzel, "web": wurzel}, "license": None,
                "name": spec.name}

    # -------------------------------------------------------------- Gremien

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]:
        """Ratsversammlung, Ausschüsse und Stadtbezirksräte — drei Quellen.

        Jedes Gremium trägt seine eigene Sitzungslisten-Adresse
        (``meetings_url``) aus der Seite, auf der es gefunden wurde — nicht
        aus einem nachgebauten Muster. Die drei Adressformen sind
        unterschiedlich genug (``grem=`` gegen ``view=Termine<Kürzel>``
        gegen gar keinen Parameter), dass ein Muster mehr raten als lesen
        hieße.
        """
        wurzel = body["id"]
        yield self._org(client, f"{wurzel}/Termine.xsp", "Ratsversammlung",
                        f"{wurzel}/Termine.xsp")
        try:
            html = client.get_text(f"{wurzel}/Ausschuesse.xsp")
        except Exception as e:  # noqa: BLE001 — ohne Ausschüsse läuft der Rest
            logger.info("%s: Ausschussliste nicht lesbar (%s)", client.body_id,
                        type(e).__name__)
            html = ""
        gesehen: set[str] = set()
        for a in BeautifulSoup(html, "html.parser").find_all(
                "a", href=re.compile(r"grem=")):
            code = re.search(r"grem=([^&\"]+)", attr(a, "href"))
            name = _text(a)
            if not code or not name or code.group(1) in gesehen:
                continue
            gesehen.add(code.group(1))
            yield self._org(client, f"{wurzel}/Ausschuss/{code.group(1)}", name,
                            urljoin(f"{wurzel}/", attr(a, "href")))
        try:
            html2 = client.get_text(f"{wurzel}/AuswahlStadtbezirke.xsp")
        except Exception as e:  # noqa: BLE001
            logger.info("%s: Stadtbezirksliste nicht lesbar (%s)", client.body_id,
                        type(e).__name__)
            html2 = ""
        for a in BeautifulSoup(html2, "html.parser").find_all(
                "a", href=re.compile(r"view=Termine")):
            code = re.search(r"view=(Termine\w+)", attr(a, "href"))
            name = " ".join(_text(a).split())
            if not code or not name or code.group(1) in gesehen:
                continue
            gesehen.add(code.group(1))
            yield self._org(client, f"{wurzel}/Stadtbezirk/{code.group(1)}", name,
                            urljoin(f"{wurzel}/", attr(a, "href")))

    @staticmethod
    def _org(client: OParlClient, kennung: str, name: str, meetings_url: str) -> dict:
        obj = {"id": kennung, "name": name, "meetings_url": meetings_url}
        client.raw.put_raw_object(client.body_id, "organization", kennung, obj)
        return obj

    # ------------------------------------------------------------ Sitzungen

    def iter_meetings(self, client: OParlClient, body: dict,
                      since: str) -> Iterator[dict]:
        """Je Gremium seine Sitzungsliste — eine ungeblätterte Seite."""
        wurzel = body["id"]
        gesehen: set[str] = set()
        for org in client.raw.raw_objects(client.body_id, "organization"):
            url = org.get("meetings_url")
            if not url:
                continue
            try:
                liste = client.get_text(url)
            except Exception as e:  # noqa: BLE001 — ein Gremium, nicht der Lauf
                logger.info("%s: Sitzungsliste %s nicht lesbar (%s)",
                            client.body_id, org.get("name"), type(e).__name__)
                continue
            for m in re.finditer(r'href="?(TM/(\d{8})_[^"\s>]+)"?', liste):
                pfad, datum = m.group(1), m.group(2)
                if since and f"{datum[:4]}-{datum[4:6]}-{datum[6:]}" < since:
                    continue
                kennung = urljoin(f"{wurzel}/", pfad)
                if kennung in gesehen:
                    continue
                gesehen.add(kennung)
                try:
                    html = client.get_text(kennung)
                except Exception as e:  # noqa: BLE001 — eine Sitzung, nicht der Lauf
                    logger.info("%s: Sitzung %s nicht lesbar (%s)", client.body_id,
                                pfad, type(e).__name__)
                    continue
                obj = {"id": kennung, "html": html}
                client.raw.put_raw_object(client.body_id, "meeting", kennung, obj)
                yield obj
        logger.info("%s: %s Sitzungen", client.body_id, len(gesehen))

    # ------------------------------------------------------------- Vorlagen

    def iter_papers(self, client: OParlClient, body: dict,
                    since: str) -> Iterator[dict]:
        """Die Drucksachen, die an den geholten Sitzungen hängen."""
        wurzel = body["id"]
        gesehen: set[str] = set()
        for roh in client.raw.raw_objects(client.body_id, "meeting"):
            for pfad in re.findall(r'href=(DS/[\w\-]+)\s', roh.get("html") or ""):
                if pfad in gesehen:
                    continue
                gesehen.add(pfad)
                kennung = urljoin(f"{wurzel}/", pfad)
                try:
                    html = client.get_text(kennung)
                except Exception as e:  # noqa: BLE001 — eine Vorlage, nicht der Lauf
                    logger.info("%s: Vorlage %s nicht lesbar (%s)", client.body_id,
                                pfad, type(e).__name__)
                    continue
                obj = {"id": kennung, "html": html}
                client.raw.put_raw_object(client.body_id, "paper", kennung, obj)
                yield obj

    # --------------------------------------------------------- Normalisieren

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        organizations = [
            Organization(o["id"], body_id, o.get("name") or "", None,
                         org_kind(o.get("name") or ""))
            for o in raw.raw_objects(body_id, "organization")
            if isinstance(o, dict) and o.get("id")]
        gremien = {normalize_title(o.name): o.id for o in organizations}

        meetings: list[Meeting] = []
        items: list[AgendaItem] = []
        # (meeting_id, paper_id) -> Position des Punktes in `items`, damit
        # die Beratungsfolge der Vorlage ihr Ergebnis an den richtigen Punkt
        # zurückschreiben kann — über die Kennung, nie über den Titel.
        punkt_je_station: dict[tuple[str, str], int] = {}
        for roh in raw.raw_objects(body_id, "meeting"):
            html = roh.get("html")
            if not html:
                continue
            m_id = roh["id"]
            suppe = BeautifulSoup(html, "html.parser")
            kopf = self._kopf(suppe)
            meetings.append(Meeting(
                m_id, body_id, self._gremium_id(gremien, kopf.get("Gremium", "")),
                self._titel(suppe) or kopf.get("Gremium") or "Sitzung",
                _iso(kopf.get("Sitzungsdatum"), kopf.get("Beginn"))))
            wurzel = m_id.split("/TM/")[0]
            for i, (nummer, name, ziel) in enumerate(self._punkte(suppe), 1):
                kennung = urljoin(f"{wurzel}/", ziel)
                items.append(AgendaItem(kennung, m_id, name, nummer, i, public=True))
                if ziel.startswith("DS/"):
                    punkt_je_station[(m_id, urljoin(f"{wurzel}/", ziel))] = len(items) - 1

        papers: list[Paper] = []
        consultations: list[Consultation] = []
        for roh in raw.raw_objects(body_id, "paper"):
            html = roh.get("html")
            if not html:
                continue
            p_id = roh["id"]
            suppe = BeautifulSoup(html, "html.parser")
            art, nr, titel = self._kopfdaten(suppe)
            stationen = self._beratungsfolge(suppe)
            daten = sorted(s["datum"] for s in stationen if s["datum"])
            papers.append(Paper(
                p_id, body_id, titel or "", reference=nr, date=daten[0] if daten else None,
                paper_type_raw=art, kind=paper_kind(art), web=p_id))
            for s in stationen:
                ergebnis = s["ergebnis"]
                erg = _ergebnis_einordnen(ergebnis) if ergebnis else Outcome.NONE
                punkt_i = punkt_je_station.get((s["meeting_id"], p_id)) if s["meeting_id"] else None
                if punkt_i is not None and ergebnis:
                    items[punkt_i] = replace(items[punkt_i], result_raw=ergebnis, outcome=erg)
                consultations.append(Consultation(
                    f"{p_id}:{s['meeting_id'] or s['datum']}", p_id,
                    meeting_id=s["meeting_id"],
                    agenda_item_id=items[punkt_i].id if punkt_i is not None else None,
                    organization_id=self._gremium_id(gremien, s["gremium"]),
                    role_raw=ergebnis))

        return Batch(organizations=organizations, meetings=meetings,
                     agenda_items=items, papers=papers, files=[],
                     consultations=consultations)

    # ------------------------------------------------------------- Bausteine

    @staticmethod
    def _gremium_id(gremien: dict[str, str], text: str) -> str | None:
        """Ein Gremienname → seine Kennung, auch mit Klammerzusatz.

        „Ratsversammlung (Sondersitzung)" ist dieselbe Ratsversammlung, nur
        außerplanmäßig — der Zusatz ändert das Gremium nicht. Ohne den
        Nachschlag ohne Klammer fanden zwei von 119 Sitzungen einer
        Stichprobe ihr Gremium nicht (11.09.2026). Eine ECHTE gemeinsame
        Sitzung („Stadtentwicklungs- und Bauausschuss gemeinsam mit
        Stadtbezirksrat Nord, …") bleibt absichtlich ohne Treffer — das
        Klammer-Entfernen träfe dort nichts, weil kein einzelnes Gremium den
        ganzen Namen trägt, und das ist richtig so: Eine gemeinsame Sitzung
        einem der beteiligten Gremien zuzuschlagen wäre erfunden.
        """
        treffer = gremien.get(normalize_title(text))
        if treffer:
            return treffer
        ohne_klammer = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
        return gremien.get(normalize_title(ohne_klammer))

    @staticmethod
    def _kopf(suppe: BeautifulSoup) -> dict[str, str]:
        """``termin_info``-Tabelle: Gremium, Sitzungsdatum, Beginn, …"""
        tabelle = suppe.find("table", id="termin_info")
        aus: dict[str, str] = {}
        if not tabelle:
            return aus
        for tr in tabelle.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                aus[_text(th).rstrip(":")] = _text(td)
        return aus

    @staticmethod
    def _titel(suppe: BeautifulSoup) -> str:
        h2 = suppe.find("h2", class_="grid12")
        return _text(h2)[:400] if h2 else ""

    @staticmethod
    def _punkte(suppe: BeautifulSoup) -> list[tuple[str, str, str]]:
        """Die Tagesordnung: ``(nummer, name, ziel)`` echter Punkte.

        Abschnitts-Überschriften (römische Ziffern) und die gebündelte Marke
        für nichtöffentliche Punkte fallen über ``_TOP_NR`` heraus — beide
        haben keine reine Dezimalnummer.
        """
        tabelle = suppe.find("table", id="view:viewPanel1")
        if not tabelle:
            return []
        raus: list[tuple[str, str, str]] = []
        for tr in tabelle.find_all("tr"):
            zellen = tr.find_all("td", attrs={"role": "gridcell"})
            if len(zellen) < 2:
                continue
            nummer = _text(zellen[-2])
            if not _TOP_NR.match(nummer):
                continue
            a = zellen[-1].find("a")
            if not a or not a.get("href"):
                continue
            raus.append((nummer.rstrip("."), _text(a), attr(a, "href").strip()))
        return raus

    @staticmethod
    def _kopfdaten(suppe: BeautifulSoup) -> tuple[str | None, str | None, str]:
        """``(Art, Aktenzeichen, Titel)`` aus ``<h2>Art Nr. Ref: Titel</h2>``."""
        h2 = suppe.find("h2", class_="grid12")
        if not h2:
            return None, None, ""
        roh = _text(h2)
        m = re.match(r"([^:]+?)\s*Nr\.\s*([^:]+):\s*(.*)", roh)
        if not m:
            return None, None, roh[:400]
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()[:400]

    def _beratungsfolge(self, suppe: BeautifulSoup) -> list[dict]:
        """Die Stationen einer Vorlage aus ``<ul class="bf">``.

        Jede Zeile trägt Datum, Gremium und — wenn die Sitzung
        veröffentlicht ist — einen Verweis auf sie; darüber wird die Station
        eindeutig einer Sitzung zugeordnet, ohne Titel zu vergleichen.
        Zeilen ohne Datum (``Zukünftig: …``) sind noch nicht terminierte
        Überweisungen und werden übersprungen.
        """
        ul = suppe.find("ul", class_="bf")
        if not ul:
            return []
        raus: list[dict] = []
        for li in ul.find_all("li"):
            m = _STATION_RE.match(_text(li))
            if not m:
                continue
            a = li.find("a")
            meeting_id = attr(a, "href").strip() if a and a.get("href") else None
            raus.append({
                "datum": _iso(m.group(1)), "gremium": m.group(2).strip(),
                "meeting_id": meeting_id,
                "ergebnis": (m.group(3) or "").strip() or None})
        return raus

    def inline_texts(self, raw: CitiesStore, body_id: str) -> Iterator[tuple[str, str]]:
        """Der „Inhalt der Drucksache" — er steht in der Seite, nicht im PDF."""
        for roh in raw.raw_objects(body_id, "paper"):
            html = roh.get("html")
            if not html:
                continue
            block = BeautifulSoup(html, "html.parser").find(id="a2")
            text = _text(block)
            if text:
                yield roh["id"], text
