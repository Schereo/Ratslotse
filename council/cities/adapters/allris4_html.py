"""ALLRIS 4 über die Oberfläche — für Städte, deren OParl nicht antwortet.

**Wofür.** Wolfsburg, Lüneburg und Laatzen fahren ALLRIS 4 und haben die
OParl-Schnittstelle eingebaut; sie antwortet mit HTTP 500. Die Oberfläche ist
öffentlich, also wird sie gelesen. Dasselbe gilt als Rückfallebene für
Osnabrück, Braunschweig und Potsdam, falls deren Schnittstelle einmal so
aussieht.

**Was gemessen wurde (10.09.2026, an Laatzen).** ALLRIS 4 ist eine
Apache-Wicket-Anwendung, und das trennt die Seiten in zwei Klassen:

- **Die Inhaltsseiten sind zustandslose GETs.** ``to010?SILFDNR=1000073``
  liefert 22 kB mit Betreff, Gremium, Datum, Tagesordnung und den Vorlagen
  daran; ``vo020?VOLFDNR=…`` die Vorlage samt Beratungsfolge. Kein Browser,
  keine Sitzung, kein Token. Das ist der ganze Inhalt.
- **Nur der Kalender braucht Wickets Seitenzustand.** ``si010`` liefert eine
  leere Hülle; die Tabelle kommt per AJAX nach. Nachgebaut geht das für den
  laufenden Monat (``si010?0-1.0-`` mit ``Wicket-Ajax``-Kopfzeilen), aber die
  Monatsnavigation hängt an einer Seitenversion, die der Server hochzählt —
  wer sie konstruiert, bekommt leere Antworten.

Daraus folgt die Bauform: **Ein Browser nur für den Index, HTTP für alles
andere.** Der Browser ist teuer und wird deshalb nur für das gebraucht, was
ohne ihn nicht geht — ein paar Kalenderseiten je Lauf statt Tausender
Dokumentabrufe.

**Kennungen.** OParl-Städte haben stabile ``id``-URLs; hier gibt es Zahlen.
Die Kennung wird ``https://<host>/public/to010?SILFDNR=<n>`` — die Adresse,
unter der das Objekt wirklich steht. Synthetisch wäre sie auch stabil, aber
diese führt zusätzlich zum Original.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from council.cities.adapters._common import (eindeutige_beratungen, normalize_title,
                                             zwillinge_zusammenfuehren)
from council.cities.model import (AgendaItem, Batch, Consultation, File, FileRole,
                                  Meeting, Organization, Paper, org_kind,
                                  outcome, paper_kind)
from council.cities.oparl import OParlClient
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.adapters.allris4_html")

#: Wie viele Kalendermonate ein Lauf höchstens ansieht. Zwölf sind ein Jahr;
#: mehr holt der Bestandslauf über ``--since``.
MAX_MONATE = 24

_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_UHRZEIT = re.compile(r"(\d{1,2}):(\d{2})")
#: ``Ö 6.1``, ``N 17``, ``6.1`` — die Nummer eines Tagesordnungspunkts.
_TOP_NR = re.compile(r"^([ÖN]\s*)?(\d+(?:\.\d+)*)\.?$")


def _zahl(url: str, name: str) -> str | None:
    m = re.search(rf"{name}=(\d+)", url or "")
    return m.group(1) if m else None


def _text(knoten) -> str:
    return " ".join(knoten.get_text(" ", strip=True).split()) if knoten else ""


def _attr(knoten, name: str) -> str:
    """Ein Attribut als Zeichenkette — auch wenn BeautifulSoup eine Liste gibt.

    ``get`` liefert bei mehrwertigen Attributen (``class``) eine Liste; wer
    das Ergebnis blind wie eine Zeichenkette behandelt, bekommt an genau
    einer Stelle einen Absturz, den kein Test sieht.
    """
    if knoten is None:
        return ""
    wert = knoten.get(name)
    if isinstance(wert, (list, tuple)):
        return " ".join(str(x) for x in wert)
    return str(wert) if wert is not None else ""


def _kopfzeile(tabelle) -> list[str]:
    """Die Beschriftungen der ersten Zeile, kleingeschrieben.

    Gelesen wird über sie, nicht über feste Spaltennummern — eine verschobene
    Spalte liefert sonst stumm den falschen Wert.
    """
    erste = tabelle.find("tr") if tabelle is not None else None
    if erste is None or not hasattr(erste, "find_all"):
        return []
    return [_text(c).lower() for c in erste.find_all(["th", "td"])]


def _grunddaten(suppe: BeautifulSoup) -> dict:
    """``Betreff: … Gremium: … Datum: …`` — die Kopfzeilen einer Seite.

    ALLRIS 4 setzt sie als Beschriftung/Wert-Paare; welche Auszeichnung
    genau, ist je Fassung verschieden. Deshalb wird der Fließtext gelesen und
    an den bekannten Wörtern zerlegt — das überlebt einen Umbau der Tabelle.
    """
    text = _text(suppe)
    # **„Vorlageart", nicht „Vorlagenart".** Gemessen an Laatzen; ein Buchstabe,
    # und die Art jeder Vorlage bleibt leer — ohne Fehler, ohne Auffälligkeit,
    # und der ganze Vergleich hält sie für „other".
    felder = ("Betreff", "Gremium", "Datum", "Status", "Uhrzeit", "Anlass",
              "Raum", "Ort", "Vorlageart", "Vorlagenart", "Verfasser",
              "Federführend", "Bezugsdrucksache")
    muster = "|".join(felder)
    aus: dict[str, str] = {}
    for m in re.finditer(rf"\b({muster}):\s*(.*?)(?=\s\b(?:{muster}):|$)", text):
        aus.setdefault(m.group(1), m.group(2).strip()[:400])
    return aus


def _iso(datum: str | None, uhrzeit: str | None = None) -> str | None:
    if not datum:
        return None
    m = _DATUM.search(datum)
    if not m:
        return None
    tag = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    u = _UHRZEIT.search(uhrzeit or "")
    return f"{tag}T{int(u.group(1)):02d}:{u.group(2)}:00" if u else tag


class Allris4HtmlAdapter:
    """Liest ALLRIS 4 über die Oberfläche statt über OParl."""

    dialect = "allris4_html"

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
        """Die Ausschüsse aus ``gr020`` — zustandslos erreichbar."""
        wurzel = body["id"]
        try:
            html = client.get_text(f"{wurzel}/gr020")
        except Exception as e:  # noqa: BLE001 — ohne Gremienliste läuft der Rest
            logger.info("%s: Gremienliste nicht lesbar (%s)", client.body_id,
                        type(e).__name__)
            return
        suppe = BeautifulSoup(html, "html.parser")
        for a in suppe.find_all("a", href=re.compile(r"gr0\d\d\?.*GRLFDNR=\d+")):
            nr = _zahl(_attr(a, "href"), "GRLFDNR")
            name = _text(a)
            if not nr or not name:
                continue
            obj = {"id": f"{wurzel}/gr020?GRLFDNR={nr}", "name": name}
            client.raw.put_raw_object(client.body_id, "organization", obj["id"], obj)
            yield obj

    # ------------------------------------------------------------ Sitzungen

    def iter_meetings(self, client: OParlClient, body: dict,
                      since: str) -> Iterator[dict]:
        """Kalender → Sitzungsseiten. Der Index kommt aus ``kalender_ids``."""
        wurzel = body["id"]
        for nr in sorted(self.kalender_ids(client, wurzel), reverse=True):
            kennung = f"{wurzel}/to010?SILFDNR={nr}"
            try:
                html = client.get_text(f"{kennung}&refresh=false")
            except Exception as e:  # noqa: BLE001 — eine Sitzung, nicht der Lauf
                logger.info("%s: Sitzung %s nicht lesbar (%s)", client.body_id, nr,
                            type(e).__name__)
                continue
            obj = {"id": kennung, "silfdnr": nr, "html": html}
            client.raw.put_raw_object(client.body_id, "meeting", kennung, obj)
            yield obj

    def kalender_ids(self, client: OParlClient, wurzel: str) -> set[str]:
        """Welche Sitzungen gibt es? — der einzige Schritt, der einen Browser braucht.

        Wird von ``fetch`` gesetzt (``client.kalender``); ohne Browser bleibt
        der laufende Monat, den die Wicket-Antwort auch ohne Zustand hergibt.
        """
        holen = getattr(client, "kalender", None)
        if holen is not None:
            return set(holen(wurzel))
        return self.kalender_laufender_monat(client, wurzel)

    @staticmethod
    def kalender_laufender_monat(client: OParlClient, wurzel: str) -> set[str]:
        """Der laufende Monat ohne Browser — Wickets Selbstaufruf genügt dafür.

        Gemessen an Laatzen: ``si010`` liefert eine leere Hülle mit einem
        AJAX-Ziel darin; dasselbe Ziel mit ``Wicket-Ajax``-Kopfzeilen geholt,
        antwortet mit der Kalendertabelle. Für die Historie reicht das nicht
        (die Monatsnavigation hängt an einer Seitenversion) — dafür ist der
        Browser da.
        """
        try:
            huelle = client.get_text(f"{wurzel}/si010")
        except Exception:  # noqa: BLE001
            return set()
        ziel = re.search(r'"u":"(\./si010\?[^"]*-1\.0-)"', huelle)
        if not ziel:
            return set(re.findall(r"SILFDNR=(\d+)", huelle))
        url = urljoin(f"{wurzel}/", ziel.group(1).lstrip("./"))
        try:
            antwort = client.get_text(url, headers={
                "Wicket-Ajax": "true",
                "Wicket-Ajax-BaseURL": "si010",
                "Accept": "text/xml"})
        except Exception:  # noqa: BLE001
            return set()
        return set(re.findall(r"SILFDNR=(\d+)", antwort))

    # ------------------------------------------------------------ Vorlagen

    def iter_papers(self, client: OParlClient, body: dict,
                    since: str) -> Iterator[dict]:
        """Die Vorlagen, die an den geholten Sitzungen hängen.

        Eine eigene Vorlagenliste gibt es nicht ohne Wicket-Zustand — und sie
        wäre auch die falsche Quelle: Was den Vergleich interessiert, ist, was
        beraten wurde, und das steht an den Sitzungen.
        """
        wurzel = body["id"]
        gesehen: set[str] = set()
        for roh in client.raw.raw_objects(client.body_id, "meeting"):
            for nr in re.findall(r"VOLFDNR=(\d+)", roh.get("html") or ""):
                if nr in gesehen:
                    continue
                gesehen.add(nr)
                kennung = f"{wurzel}/vo020?VOLFDNR={nr}"
                try:
                    html = client.get_text(f"{kennung}&refresh=false")
                except Exception as e:  # noqa: BLE001
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
        files: list[File] = []
        consultations: list[Consultation] = []
        organizations = [
            Organization(o["id"], body_id, o.get("name") or "", None,
                         org_kind(o.get("name") or ""))
            for o in raw.raw_objects(body_id, "organization")
            if isinstance(o, dict) and o.get("id")]
        gremien = {normalize_title(o.name): o.id for o in organizations}

        for roh in raw.raw_objects(body_id, "meeting"):
            html = roh.get("html")
            if not html:
                continue
            m_id = roh["id"]
            suppe = BeautifulSoup(html, "html.parser")
            kopf = _grunddaten(suppe)
            meetings.append(Meeting(
                m_id, body_id,
                gremien.get(normalize_title(kopf.get("Gremium", ""))),
                kopf.get("Betreff") or kopf.get("Gremium") or "Sitzung",
                _iso(kopf.get("Datum"), kopf.get("Uhrzeit")),
                state_raw=kopf.get("Status")))
            files += self._dateien(suppe, m_id, body_id, meeting_id=m_id)
            items += self._punkte(suppe, m_id, body_id, consultations)

        beratungen_je_vorlage: dict[str, list[dict]] = {}
        for roh in raw.raw_objects(body_id, "paper"):
            html = roh.get("html")
            if not html:
                continue
            p_id = roh["id"]
            suppe = BeautifulSoup(html, "html.parser")
            kopf = _grunddaten(suppe)
            art = kopf.get("Vorlageart") or kopf.get("Vorlagenart")
            # Die Vorlagenseite trägt KEIN eigenes Datum — die Daten stehen in
            # der Beratungsfolge. Genommen wird die früheste Station: das ist
            # der Tag, an dem die Sache in den Gang kam.
            stationen = self._beratungsfolge(suppe)
            daten = sorted(s["datum"] for s in stationen if s["datum"])
            papers.append(Paper(
                p_id, body_id, kopf.get("Betreff") or "",
                reference=_zahl(p_id, "VOLFDNR"),
                date=daten[0] if daten else None,
                paper_type_raw=art, kind=paper_kind(art), web=p_id))
            beratungen_je_vorlage[p_id] = stationen
            files += self._dateien(suppe, p_id, body_id, paper_id=p_id)

        # Die Beratungsfolge der VORLAGE trägt eine Spalte „Beschluss"; die
        # Tagesordnung der Sitzung nur die „Zuständigkeit". Wo beides
        # vorliegt, gewinnt der Beschluss — er ist das Ergebnis, das andere
        # ist die Rolle der Station.
        sitzungsname = {m.id: normalize_title(m.name) for m in meetings}
        # Über die POSITION, nicht über `list.index`: Die Beratung ist ein
        # eingefrorenes Objekt, und nach dem ersten Ersetzen findet `index`
        # das alte nicht mehr — der Lauf bricht mitten in der Stadt ab.
        stelle = {(c.paper_id, sitzungsname.get(c.meeting_id or "")): i
                  for i, c in enumerate(consultations)}
        for p_id, stationen in beratungen_je_vorlage.items():
            for s in stationen:
                i = stelle.get((p_id, normalize_title(s["sitzung"])))
                if i is not None and s["beschluss"]:
                    consultations[i] = replace(consultations[i],
                                               role_raw=s["beschluss"])

        batch = Batch(organizations=organizations, meetings=meetings,
                      agenda_items=items, papers=papers, files=files,
                      consultations=consultations)
        # `link_within_meeting` braucht dieser Adapter nicht: Die Beratung
        # entsteht aus derselben Tabellenzeile wie ihr Tagesordnungspunkt, die
        # Verbindung ist also nie zu raten.
        zwillinge = zwillinge_zusammenfuehren(batch)
        getrennt = eindeutige_beratungen(batch.consultations)
        if zwillinge or getrennt:
            logger.info("%s: %s Zwillinge zusammengeführt, %s Kennungen getrennt",
                        body_id, zwillinge, getrennt)
        return batch

    @staticmethod
    def _beratungsfolge(suppe: BeautifulSoup) -> list[dict]:
        """Die Stationen einer Vorlage: Status, Datum, Gremium, Beschluss.

        ALLRIS 4 setzt sie über **zwei Zeilen** je Station — die erste trägt
        Status, Gremium und Beschluss, die zweite Datum und Sitzungsname.
        Wer nur Zeile für Zeile liest, bekommt lauter halbe Stationen.
        """
        tabelle = None
        for tab in suppe.find_all("table"):
            kopf = _kopfzeile(tab)
            if "gremium" in kopf and ("beschluss" in kopf or "datum" in kopf):
                tabelle = tab
                break
        if tabelle is None:
            return []
        kopf = _kopfzeile(tabelle)
        i_datum = kopf.index("datum") if "datum" in kopf else 1
        i_gremium = kopf.index("gremium") if "gremium" in kopf else 2
        i_beschluss = kopf.index("beschluss") if "beschluss" in kopf else 3
        raus: list[dict] = []
        offen: dict | None = None
        for tr in tabelle.find_all("tr")[1:]:
            werte = [_text(c) for c in tr.find_all(["td", "th"])]
            if not any(werte):
                continue
            gremium = werte[i_gremium] if i_gremium < len(werte) else ""
            datum = _iso(werte[i_datum] if i_datum < len(werte) else "")
            beschluss = werte[i_beschluss] if i_beschluss < len(werte) else ""
            if datum and offen is not None:
                offen["datum"] = datum
                offen["sitzung"] = gremium or offen["sitzung"]
                raus.append(offen)
                offen = None
            elif gremium:
                offen = {"gremium": gremium, "sitzung": gremium,
                         "datum": datum, "beschluss": beschluss or None}
                if datum:
                    raus.append(offen)
                    offen = None
        if offen is not None:
            raus.append(offen)
        return raus

    # ------------------------------------------------------------- Bausteine

    def _punkte(self, suppe: BeautifulSoup, meeting_id: str, body_id: str,
                consultations: list[Consultation]) -> list[AgendaItem]:
        """Die Tagesordnung aus ``table#toTreeTable``.

        Spalten (gemessen an Laatzen): ``+/-``, ``TOP``, ``Betreff``, zwei
        leere, ``Vorlage``, leer, ``Zuständigkeit``. Gelesen wird über die
        **Kopfzeile**, nicht über feste Spaltennummern — eine verschobene
        Spalte liefert sonst stumm falsche Werte, und genau das ist die Falle
        beim HTML-Lesen.
        """
        tabelle = suppe.find("table", id="toTreeTable") or suppe.find(
            "table", class_=re.compile("toTree"))
        if not tabelle:
            return []
        kopf = _kopfzeile(tabelle)

        def spalte(name: str, vorgabe: int) -> int:
            for i, k in enumerate(kopf):
                if name in k:
                    return i
            return vorgabe

        i_top, i_betreff = spalte("top", 1), spalte("betreff", 2)
        i_ergebnis = spalte("zuständigkeit", 7)
        raus: list[AgendaItem] = []
        oeffentlich = True
        for pos, tr in enumerate(tabelle.find_all("tr")[1:]):
            zellen = tr.find_all(["td", "th"])
            if not zellen:
                continue
            werte = [_text(c) for c in zellen]
            ganze_zeile = " ".join(werte)
            if "nicht öffentlich" in ganze_zeile.lower():
                oeffentlich = False
            elif "öffentlicher teil" in ganze_zeile.lower():
                oeffentlich = True
            nummer_roh = werte[i_top] if i_top < len(werte) else ""
            m = _TOP_NR.match(nummer_roh.strip())
            if not m:
                continue
            betreff = werte[i_betreff] if i_betreff < len(werte) else ""
            if not betreff:
                continue
            ergebnis = werte[i_ergebnis] if i_ergebnis < len(werte) else ""
            # **Die echte Kennung ist eine Adresse, keine Erfindung.** ALLRIS
            # vergibt einem Punkt mit Inhalt eine ``TOLFDNR``; die Seite dazu
            # steht unter ``to020``. Nur reine Formalpunkte („Feststellung der
            # Beschlussfähigkeit") haben keine — dort bleibt die Nummer, und
            # das Trennzeichen ``#top-`` sagt richtigerweise „selbst gebaut"
            # (``SYNTHETISCHE_KENNUNG`` in ``_common.py``). Stünde es auch an
            # den echten, hielte `zwillinge_zusammenfuehren` jeden Punkt
            # dieses Dialekts für erfunden.
            pfad = meeting_id.split("/to010")[0]
            top_link = tr.find("a", href=re.compile(r"to020|TOLFDNR=\d+"))
            nr = _zahl(_attr(top_link, "href"), "TOLFDNR")
            kennung = (f"{pfad}/to020?TOLFDNR={nr}" if nr
                       else f"{meeting_id}#top-{m.group(2)}")
            raus.append(AgendaItem(
                kennung, meeting_id, betreff, m.group(2), pos,
                public=oeffentlich, result_raw=ergebnis or None,
                outcome=outcome(ergebnis)))
            vo = tr.find("a", href=re.compile(r"vo020|VOLFDNR=\d+"))
            v = _zahl(_attr(vo, "href"), "VOLFDNR")
            if v:
                consultations.append(Consultation(
                    f"{kennung}:vo{v}", f"{pfad}/vo020?VOLFDNR={v}",
                    meeting_id=meeting_id, agenda_item_id=kennung,
                    role_raw=ergebnis or None))
        return raus

    def file_url(self, file_json: dict, url: str | None) -> str | None:
        """Die Adresse steht schon in der Datei — ALLRIS leitet nicht um."""
        return url

    @staticmethod
    def _dateien(suppe: BeautifulSoup, objekt_id: str, body_id: str,
                 paper_id: str | None = None,
                 meeting_id: str | None = None) -> list[File]:
        """Die PDFs. ALLRIS 4 legt sie unter ``wicket/resource/…/docN.pdf`` ab."""
        raus: list[File] = []
        wurzel = objekt_id.split("/to010")[0].split("/vo020")[0]
        for a in suppe.find_all("a", href=re.compile(r"\.pdf(\?|$)", re.I)):
            url = urljoin(f"{wurzel}/", _attr(a, "href").lstrip("./"))
            name = _text(a) or url.rsplit("/", 1)[-1]
            rolle = FileRole.MAIN
            klein = name.lower()
            if "niederschrift" in klein or "protokoll" in klein:
                rolle = FileRole.PROTOCOL
            elif "einladung" in klein or "bekanntmachung" in klein:
                rolle = FileRole.INVITATION
            # **Das Sammeldokument ist keine Vorlage, sondern ihr Bündel.**
            # Gemessen an Laatzen hängt an JEDER Vorlagenseite beides:
            # „Vorlage" (der Text) und „Sammeldokument" (Vorlage samt allen
            # Anlagen in einer Datei). Beide als Hauptdokument zu führen hieße:
            # jede Vorlage bekommt ihren Text doppelt, einmal umgeben vom
            # Beiwerk — und welcher der beiden in die Einordnung geht, wäre
            # Zufall der Reihenfolge.
            elif "sammeldokument" in klein or "gesamt" in klein:
                rolle = FileRole.AUXILIARY
            elif meeting_id:
                rolle = FileRole.AUXILIARY
            raus.append(File(url, body_id, rolle, paper_id=paper_id,
                             meeting_id=meeting_id, name=name or None,
                             mime="application/pdf", access_url=url))
        return raus


