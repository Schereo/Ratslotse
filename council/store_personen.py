"""Personen: Ratsmitglieder, Verwaltung, Namensformen, Anwesenheit.

Fünfter Schnitt an ``store.py``. Hier liegt die heikelste Ecke des Bestands:
Ein Protokoll schreibt „Ratsherr Ellberg", „Bernhard Ellberg" oder
„Ausschussvorsitzender Ellberg" — und alle drei sollen auf dieselbe Person
zeigen, ohne einen Namensvetter mitzunehmen. Die Regeln dafür (``_ANREDEN``,
``_HONORIFICS``, ``namensteile``, ``_spricht_diese_person``) gehören
zusammen; sie lagen über 900 Zeilen verteilt.

Die drei Klassenattribute sind mit umgezogen: Ohne sie wären die Methoden
hier, ihre Vokabellisten aber drüben — und genau daraus ist am 02.09.2026 ein
Fehler entstanden (zwei Listen gleichen Namens, die zweite überschrieb die
erste still).

Die Wortbeitrags-Abfragen sind NICHT hier: Sie fragen über eine Person, aber
sie gehören den Wortbeiträgen.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

class PersonenMixin(StoreBasis):
    """Die Personen-Abfragen — nur zum Mitvererben."""

    # Vertretungs- und Zeit-Notizen sind keine Ämter („Für Oberbürgermeister
    # Krogmann", „bis TOP 8.2") — nur echte Amtsbezeichnungen zählen.
    _ROLLEN_RE = re.compile(
        r"(?i)^(erste[rn]?\s+)?(oberbürgermeister(in)?|stadtkämmer(er|in)|"
        r"stadtbaur(at|ätin)|stadtr(at|ätin))$")

    #: Funktionsangabe des Beteiligungsberichts, die „diese Person sitzt im
    #: Stadtrat" behauptet — mit optionalem Klammerzusatz, wie ihn der Bericht
    #: auch anderswo führt („1. Kreisrat (Vorsitzender)").
    _FUNKTION_RATSMITGLIED = re.compile(r"(?i)^ratsmitglied(\s*\(.*\))?$")

    #: Name des Plenar-Gremiums in den Sitzungsdaten. Es ist der Prüfstein für
    #: ein Ratsmandat (s. list_members) — die Ausschüsse führen daneben
    #: beratende Mitglieder, die dem Rat nicht angehören.
    PLENUM = "Rat"

    #: Wörter, die im Fraktions-Feld nur die ROLLE beschreiben („Beratendes
    #: Mitglied", „beratend", „Verwaltung") — sie benennen keine entsendende
    #: Organisation und taugen deshalb nicht als Herkunfts-Label.
    _ROLLEN_LABEL = re.compile(
        r"^(beratend\w*|beratende[sr]?\s+mitglied\w*|gast|gäste|verwaltung|"
        r"protokoll\w*|stellv\w*|vertretung|mitglied\w*)$", re.IGNORECASE)

    #: Anreden, die vor einem Namen stehen dürfen, ohne ihn zu einem anderen zu
    #: machen. Ohne die Liste hielte „Ratsfrau Hufeland" einen Vornamen für
    #: vorhanden und fiele aus der Zuordnung.
    #: Rollen zählen mit: „Ratsvorsitzender Harms" ist eine Funktion plus
    #: Nachname, kein zweiter Name — genau wie „Ratsherr Harms".
    _ANREDEN = {"ratsfrau", "ratsherr", "frau", "herr", "ratsmitglied",
                "oberbuergermeister", "oberbürgermeister", "buergermeister",
                "bürgermeister", "stadtrat", "staedtrat",
                "ratsvorsitzender", "ratsvorsitzende", "vorsitzender", "vorsitzende",
                "ausschussvorsitzender", "ausschussvorsitzende"}

    # Titel UND Anreden: „Herr Jens Freymuth" und „Jens Freymuth" sind dieselbe
    # Person — ohne die Anreden entstanden Dubletten im Mitglieder-Verzeichnis
    # (Tims Befund 10.08.). Adelspartikel („zu", „von") bleiben absichtlich
    # stehen — sie gehören zum Nachnamen.
    # Amtstitel gehören mit rein, wenn sie wie ein Vorname direkt VOR dem
    # Namen in der Anwesenheitsliste stehen — „Stadtkämmerin Dr. Julia
    # Figura" statt „Dr. Julia Figura" (Tims Figura-Befund 19.08.: Krogmann
    # bekam sein Stadt-Badge, weil sein voller Vorname im Sprecher-Text
    # stand und die Dublette auflöste — „Dr. Figura" allein hatte dazu
    # keine Chance). Ohne diese Wörter hier entstehen zwei _person_slug()
    # für dieselbe Person: das Frontend sieht zwei Kandidaten für den
    # Nachnamen und verweigert bei fehlendem Vornamen lieber jedes Badge,
    # statt eins zu raten. Dieselbe Wortliste wie in _ROLLEN_RE, nur ohne
    # das optionale „Erste[rn]"-Präfix (das steht nur im note-Feld, nie
    # direkt im name-Feld) — dafür in gefalteter UND ungefalteter Form,
    # weil _person_slug faltet (ä→ae) und namensteile() das nicht tut.
    _HONORIFICS = {"prof", "dr", "dipl", "ing", "med",
                   "herr", "frau", "ratsherr", "ratsfrau",
                   "oberbürgermeister", "oberbürgermeisterin",
                   "oberbuergermeister", "oberbuergermeisterin",
                   "stadtkämmerer", "stadtkämmerin",
                   "stadtkaemmerer", "stadtkaemmerin",
                   "stadtbaurat", "stadtbaurätin", "stadtbauraetin",
                   "stadtrat", "stadträtin", "stadtraetin"}

    #: NUR für die Anzeige: die vier Anreden, die vor einem Namen wegfallen.
    #: Sie hieß bis 02.09.2026 ebenfalls ``_ANREDEN`` — und überschrieb damit
    #: still die längere Liste weiter oben, die auch Rollen kennt
    #: („Ausschussvorsitzender Behrens"). Zwei Klassenattribute mit demselben
    #: Namen: Das zweite gewinnt, und das erste war tot. Gemessen hat das 39
    #: Wortbeiträge in zehn Sprecher-Formen gekostet — sie waren keiner Person
    #: zugeordnet.
    _ANREDEN_ANZEIGE = {"herr", "frau", "ratsherr", "ratsfrau"}

    def council_roster_before(self, ksinr: int) -> list[dict]:
        """Die Anwesenheitsliste der jüngsten Ratssitzung VOR dieser — das
        Sprecher-Verzeichnis für die Live-Verfolgung (``council/livetracker``).

        Das Protokoll der laufenden Sitzung gibt es live noch nicht; der Rat
        ist aber derselbe wie beim letzten Mal. Zurück kommen Mitglieder,
        Vorsitz und Verwaltung (Gäste und Protokollführung reden nicht zur
        Sache) mit ``name``, ``party``, ``role``. Ohne Vorgängerin mit
        Liste: leer — dann rät der Tracker die Fraktion nicht, er lässt sie
        weg."""
        from council import live as live_mod

        datum = self._conn.execute(
            "SELECT session_date FROM council_sessions WHERE ksinr = ?", (ksinr,)
        ).fetchone()
        if not datum:
            return []
        kandidaten = self._conn.execute(
            """SELECT s.ksinr, s.committee FROM council_sessions s
               WHERE s.session_date < ? AND s.ksinr <> ?
                 AND EXISTS (SELECT 1 FROM council_attendance a WHERE a.ksinr = s.ksinr)
               ORDER BY s.session_date DESC, s.ksinr DESC""",
            (datum[0], ksinr),
        ).fetchall()
        quelle = next((r["ksinr"] for r in kandidaten if live_mod.is_council(r["committee"])), None)
        if quelle is None:
            return []
        rows = self._conn.execute(
            """SELECT name, COALESCE(party, '') AS party, COALESCE(role, '') AS role
               FROM council_attendance
               WHERE ksinr = ? AND role IN ('member', 'chair', 'administration')
               ORDER BY party, name""",
            (quelle,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_attendance(self, ksinr: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT name, party, role, note FROM council_attendance WHERE ksinr = ? ORDER BY id", (ksinr,)
        ).fetchall()
        return [dict(r) for r in rows]

    def save_person(self, kpenr: int, name: str, current_faction: str | None) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "INSERT INTO council_persons (kpenr, name, current_faction, fetched_at) "
                "VALUES (?,?,?,?) ON CONFLICT(kpenr) DO UPDATE SET "
                "name=excluded.name, current_faction=excluded.current_faction, "
                "fetched_at=excluded.fetched_at",
                (kpenr, name, current_faction, now),
            )

    def save_memberships(self, kpenr: int, rows: list[dict]) -> int:
        """Replace all Gremien-Mitgliedschaften of one person (full refresh)."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute("DELETE FROM council_memberships WHERE kpenr = ?", (kpenr,))
            for r in rows:
                self._conn.execute(
                    "INSERT INTO council_memberships "
                    "(kpenr, kgrnr, committee, role, valid_from, valid_until, fetched_at) VALUES (?,?,?,?,?,?,?)",
                    (kpenr, r.get("kgrnr"), r.get("committee") or "", r.get("role"),
                     r.get("valid_from"), r.get("valid_until"), now),
                )
        return len(rows)

    def person_stammdaten_for_names(self, names: list[str]) -> dict | None:
        """RIS-Stammdaten für eine Person, gematcht über die Namens-Slugs der
        Anwesenheitsdaten: aktuelle Fraktion (RIS-Stand) + offizielle
        Gremien-Mitgliedschaften mit von/bis, neueste zuerst."""
        if not names:
            return None
        # Gefaltet auf die kanonische Namensform (:meth:`person_slug`): Das
        # Ratsinformationssystem führt seine Stammdaten unter genau einer Form,
        # die Anwesenheitslisten können eine andere nennen — ohne die Faltung
        # stünde ein Profil ohne Mandat und ohne Fraktion da.
        want = {self.person_slug(n) for n in names}
        person = None
        for r in self._conn.execute("SELECT kpenr, name, current_faction FROM council_persons"):
            if self.person_slug(r["name"]) in want:
                person = dict(r)
                break
        if not person:
            return None
        ms = self._conn.execute(
            "SELECT kgrnr, committee, role, valid_from, valid_until FROM council_memberships "
            "WHERE kpenr = ? ORDER BY (valid_until IS NULL) DESC, COALESCE(valid_until,'9999') DESC, valid_from DESC",
            (person["kpenr"],),
        ).fetchall()
        person["memberships"] = [dict(r) for r in ms]
        return person

    @classmethod
    def namensteile(cls, anzeige: str) -> tuple[str, str]:
        """„Dr. Ruth Regina Drügemöller" → ``("ruth", "druegemoeller")``.

        (vorname_gefaltet, nachname_gefaltet) — Nachname ist das letzte Token
        (Bindestrich-Namen sind EIN Token), Titel zählen nicht als Vorname.

        Steht hier als Klassenmethode und nicht mehr als Verschachtelung in
        :meth:`personen_lexikon`, weil sie außerhalb gebraucht wird: Wer einen
        Namen **gegen** das Lexikon hält (die Aufsichtsorgane des
        Beteiligungsberichts tun das), muss ihn genauso falten wie das Lexikon
        selbst. Eine zweite, leicht abweichende Faltung träfe an den Umlauten
        und Titeln nichts mehr — und niemand sähe es, weil ein Fehltreffer wie
        ein fehlender Eintrag aussieht.

        Titel-Erkennung mit abgestreiften Satzzeichen (``-Ing`` → ``ing``):
        ``_person_slug`` zerlegt an allem, was kein Buchstabe ist, und sah
        „Ing" deshalb schon immer als Titel — hier zählte der Bindestrich noch
        mit, und „Prof. Dr.-Ing. Manfred Weisensee" bekam den Vornamen „-ing".
        Zwei Faltungen desselben Namens dürfen nicht verschiedene Personen
        sehen: Die eine bildete den Slug ``manfred-weisensee``, die andere
        hielt ihn für einen Namensvetter von „Prof. Dr.-Ing. Weisensee"."""
        toks = [t for t in anzeige.replace(".", " ").split()
                if t.strip("-–—").lower() not in cls._HONORIFICS]
        if not toks:
            return "", ""
        return (cls._falte_namen(toks[0]) if len(toks) > 1 else "",
                cls._falte_namen(toks[-1]))

    @classmethod
    def tippfehler_ratsmitglied(cls, vorname: str, nachname: str,
                                position: str | None,
                                nach_paar: dict[tuple[str, str], list[dict]]
                                ) -> dict | None:
        """Der Beteiligungsbericht schreibt ein Ratsmitglied falsch — welcher
        Lexikon-Eintrag ist gemeint? ``None``, wenn die Regel nicht greift.

        Der Bericht ist ein gesetztes PDF und hat Druckfehler: „Claudia
        Oeljeschl**e**ger" (statt -schläger) und „Jens Lükerman" (statt
        -mann). Beide sitzen im Rat und stehen längst im Verzeichnis; der
        strenge Abgleich über Vor- UND Nachnamen findet sie trotzdem nicht,
        und zwei berechtigte Links auf die Personen-Seite gehen verloren.

        Geraten wird trotzdem nicht — geheilt wird nur, wo **alle drei**
        Bedingungen zusammenkommen:

        1. **Der Bericht nennt die Funktion „Ratsmitglied".** Die Quelle
           behauptet also selbst, dass diese Person im Stadtrat sitzt; wir
           suchen dann im Verzeichnis der Ratsmitglieder nach genau der
           Person, die sie meint. Ohne diese Bedingung liefe die Regel über
           alle 116 Namen des Berichts — auch über Beschäftigtenvertretungen
           und Vertreter der Mitgesellschafter, die im Rat gar nichts zu
           suchen haben und deren Nachname zufällig um einen Buchstaben neben
           dem eines Ratsmitglieds liegen darf.
        2. **Der Vorname stimmt exakt.** Ein Druckfehler trifft selten zwei
           Wörter; zwei verschiedene Menschen unterscheiden sich dagegen fast
           immer schon im Vornamen. Ohne diese Bedingung würde aus „Meier"
           ein „Meyer" und aus zwei Familien eine.
        3. **Der Nachname weicht um höchstens einen Buchstaben ab.** Das ist
           die Reichweite eines Druckfehlers — ein fehlendes „n", ein „e"
           statt „ä". Ohne diese Bedingung (etwa bei Abstand 2) fielen
           „Schmidt" und „Schmitz" zusammen.

        Jede Bedingung für sich wäre zu lose: Funktion allein heilte jeden
        Verwechsler unter 300 Ratszeilen, Vorname allein jeden Namensvetter,
        Buchstabenabstand allein jede zufällige Nachbarschaft im Alphabet.
        Zusammen treffen sie Druckfehler und nicht zwei verschiedene Menschen.

        **Mehr als ein Kandidat heißt gescheitert.** Ein fehlender Link ist
        ein fehlender Link; ein falscher ist eine Falschaussage über einen
        namentlich genannten Menschen.
        """
        if not vorname or not nachname:
            return None
        if not (position and cls._FUNKTION_RATSMITGLIED.match(position.strip())):
            return None
        treffer = [e for (v, n), liste in nach_paar.items()
                   if v == vorname and cls._ein_buchstabe_abstand(n, nachname)
                   for e in liste if e.get("art") == "council"]
        return treffer[0] if len(treffer) == 1 else None

    def personen_lexikon(self) -> list[dict]:
        """Das Personen-Lexikon für die Badges im Antwort-Text (Tims Wunsch
        12.08.): Ratsmitglieder aus dem Verzeichnis (Partei, Zeitraum,
        Personen-Seite) plus Verwaltungsleute aus den Anwesenheitslisten —
        deren Amt kommt aus den Protokoll-Notizen selbst („Stadtkämmerin",
        „Oberbürgermeister"), nicht aus Weltwissen. `aktiv` heißt: in den
        letzten zwölf Monaten in einer Anwesenheitsliste — dieselbe
        selbstheilende Regel wie bei der Parteien-Zeile; Ehemalige zeigen
        ehrlich nur den belegten Zeitraum.

        Dritte Quelle (Tims Auftrag 17.08.): die Aufsichtsorgane der
        städtischen Gesellschaften aus dem Beteiligungsbericht — Landrätin und
        Kreistagsmitglieder der Gemeinschaftsgesellschaften, Beschäftigten-
        und Mitgesellschafter-Vertretungen. Sie standen bis dahin namenlos da,
        weil sie in keiner Anwesenheitsliste des Stadtrats vorkommen. Ihre
        Rolle ist die **Funktion aus dem Bericht**, ihr Zeitraum sind die
        **Berichtsjahrgänge**, in denen sie vorkommen — mehr ist nicht belegt
        (s. :meth:`_beteiligungs_personen`)."""
        from collections import Counter, defaultdict
        from datetime import date, timedelta
        as_of_date = (date.today() - timedelta(days=365)).isoformat()
        namensteile = self.namensteile

        out: list[dict] = []
        gesehen: set[str] = set()
        for m in self.list_members():
            vor, nach = namensteile(m["name"])
            if not nach:
                continue
            gesehen.add(m["slug"])
            out.append({
                "slug": m["slug"], "name": m["name"], "vorname": vor,
                "nachname": nach,
                # „beratend" ist KEIN Ratsmandat: Ausschüsse führen Verbände,
                # Beiräte und Fachleute als beratende Mitglieder. Das Badge
                # sagt das jetzt, statt sie als Ratsleute „parteilos" zu nennen
                # (Tims Skiba-Befund 21.08.2026).
                "art": m["art"], "party": m["party"],
                "organisation": m["organisation"],
                # Nur bei Wechslern: Wer immer dieselbe Fraktion hatte, ist
                # über `party` schon erkennbar — und das Lexikon lädt jede
                # Seite mit, also bleibt es schlank (13 Personen im Bestand).
                "phasen": m["phasen"] if len(m["phasen"]) > 1 else None,
                "role": ("Beratendes Mitglied"
                          + (f" · {m['organisation']}" if m["organisation"] else "")
                          if m["art"] == "advisory" else None),
                "aktiv": bool(m["last"] and m["last"] >= as_of_date),
                "von": (m["first"] or "")[:4] or None,
                "bis": (m["last"] or "")[:4] or None,
            })

        rows = self._conn.execute(
            """SELECT a.name, a.note, cs.session_date
               FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
               WHERE a.role = 'administration' AND a.name IS NOT NULL AND a.name != ''"""
        ).fetchall()
        g: dict = defaultdict(lambda: {"names": Counter(), "roles": Counter(),
                                       "first": None, "last": None})
        for r in rows:
            sl = self.person_slug(r["name"])
            if not sl:
                continue
            e = g[sl]
            e["names"][r["name"]] += 1
            note = " ".join((r["note"] or "").split())
            if note and self._ROLLEN_RE.match(note):
                e["roles"][note] += 1
            d = r["session_date"]
            e["first"] = d if e["first"] is None else min(e["first"], d)
            e["last"] = d if e["last"] is None else max(e["last"], d)
        for sl, e in g.items():
            if sl in gesehen:  # Ratsmandat gewinnt über Gast-Auftritte der Verwaltung
                continue
            gesehen.add(sl)
            anzeige = self._anzeige_name(e["names"], sl)
            vor, nach = namensteile(anzeige)
            if not nach:
                continue
            out.append({
                "slug": sl, "name": anzeige, "vorname": vor, "nachname": nach,
                "art": "city", "party": None, "organisation": None, "phasen": None,
                "role": e["roles"].most_common(1)[0][0] if e["roles"] else None,
                "aktiv": bool(e["last"] and e["last"] >= as_of_date),
                "von": (e["first"] or "")[:4] or None,
                "bis": (e["last"] or "")[:4] or None,
            })

        # Dritte Quelle: die Aufsichtsorgane des Beteiligungsberichts. Sie
        # kommt NACH Rat und Verwaltung, weil sie nur ergänzen darf, was fehlt
        # — sonst überschriebe ein Aufsichtsratsposten ein Ratsmandat, und aus
        # der Oberbürgermeisterei würde „Vertreter Mitgesellschafter".
        # Verglichen wird über das Namenspaar und nicht über den Slug: Das
        # Verzeichnis führt „Ruth Regina Drügemöller", der Bericht „Ruth
        # Drügemöller" — verschiedene Slugs, derselbe Mensch. Als zweiter
        # Eintrag angelegt, gewönne die Bericht-Schreibweise beim Abgleich der
        # Beteiligungsseite den Stichentscheid und nähme dem Ratsmitglied
        # seine Personen-Seite weg.
        bekannt: dict[tuple[str, str], list[dict]] = {}
        for e in out:
            if e["vorname"]:
                bekannt.setdefault((e["vorname"], e["nachname"]), []).append(e)
        for p in self._beteiligungs_personen():
            if p["slug"] in gesehen or (p["vorname"], p["nachname"]) in bekannt:
                continue
            # Und auch der Druckfehler eines bekannten Ratsmitglieds ist kein
            # neuer Mensch — sonst stünde „Claudia Oeljeschleger" neben
            # „Claudia Oeljeschläger" im Verzeichnis.
            if self.tippfehler_ratsmitglied(p["vorname"], p["nachname"], p["role"], bekannt):
                continue
            gesehen.add(p["slug"])
            out.append(p)

        # Blocker (Tims Oltmanns-Befund 12.08.): Gäste, Protokollführung und
        # beratende Mitglieder bekommen NIE ein Badge — aber ihr Nachname macht
        # einen kahlen Nachnamen im Text MEHRDEUTIG. „Herr Oltmanns" (Gast vom
        # Wasserstraßen-Amt, 2019) trug sonst das Badge des einzigen
        # Lexikon-Oltmanns — eines beratenden NABU-Mitglieds von 2026.
        for (name,) in self._conn.execute(
                "SELECT DISTINCT name FROM council_attendance "
                "WHERE role NOT IN ('member','chair','administration') "
                "AND name IS NOT NULL AND name != ''"):
            sl = self.person_slug(name)
            if not sl or sl in gesehen:
                continue
            gesehen.add(sl)
            _, nach = namensteile(self._person_anzeige(name))
            if nach:
                out.append({"slug": sl, "name": None, "vorname": "", "nachname": nach,
                            "art": "blocker", "party": None, "organisation": None,
                            "phasen": None, "role": None,
                            "aktiv": False, "von": None, "bis": None})
        return out

    def _beteiligungs_personen(self) -> list[dict]:
        """Lexikon-Einträge aus den Aufsichtsorganen des Beteiligungsberichts.

        Was hier steht, steht so im amtlichen, veröffentlichten Bericht —
        **Name, Funktion und Berichtsjahrgang, sonst nichts.** Keine Partei
        (der Bericht nennt keine, und aus einem Aufsichtsmandat eine
        Zugehörigkeit zu folgern wäre erfunden), keine Zusammenführung mit
        anderen Quellen, keine Anreicherung. Ein Teil dieser Menschen sind
        Privatpersonen — Betriebsratsvorsitzende, Beschäftigtenvertretungen —,
        und ein Verzeichniseintrag macht auffindbar, was der Bericht nur
        abdruckt. Deshalb genau so viel wie belegt und keine Zeile mehr.

        - ``role`` ist die **Funktion aus dem Bericht** („Landrätin",
          „Beschäftigtenvertreter"), die häufigste, wo mehrere dastehen —
          dieselbe Haltung wie bei den Verwaltungsleuten, deren Amt aus den
          Protokoll-Notizen kommt statt aus Weltwissen.
        - ``von``/``bis`` sind **Berichtsjahrgänge**, nicht Amtszeiten: Belegt
          ist nur, in welchen Berichten die Person vorkommt. Wann sie berufen
          wurde, sagt der Bericht nicht.
        - ``aktiv`` heißt „steht im jüngsten eingelesenen Bericht". Die Berichte
          hinken der Gegenwart um Jahre hinterher; die Zwölf-Monats-Regel der
          Anwesenheitslisten träfe hier auf niemanden zu und machte jeden
          amtierenden Aufsichtsrat zum „Ehemaligen".

        Drei Sorten Zeile werden **nicht** zu Personen:

        1. **Entsendungsrechte statt Menschen.** Die TGO Besitz benennt keine
           Personen, sondern Ansprüche: „Vertreter/in der Landessparkasse zu
           Oldenburg". Der Schrägstrich ist das Erkennungszeichen des
           Berichts für diese Form — kein Personenname trägt einen.
        2. **Namen ohne Vornamen.** „Prof. Dr. Bruder" ist derselbe Mensch wie
           „Prof. Dr. Ralph Bruder", zwei Zeilen weiter im selben Bericht —
           aber ein bloßer Nachname ist von einem Namensvetter nicht zu
           unterscheiden. Dieselbe Regel, aus der die Beteiligungsseite ihre
           Links zieht (``_lexikon_zuordnung``).
        3. **Nachnamen unter drei Buchstaben.** Der Bericht ist zweispaltig
           gesetzt, und der Extrakt bricht gelegentlich mitten im Namen um
           („Jens Lükerm an", Bericht 2023). Der Badge-Matcher übergeht solche
           Nachnamen ohnehin — im Verzeichnis wären sie nur ein Mensch, den es
           nicht gibt.
        """
        from collections import Counter, defaultdict
        try:
            rows = self._conn.execute(
                "SELECT report_year, name, position FROM council_company_people "
                "WHERE name IS NOT NULL AND name != ''").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return []
        if not rows:
            return []
        jungster = max(r["report_year"] for r in rows)

        g: dict = defaultdict(lambda: {"names": Counter(), "roles": Counter(),
                                       "first": None, "last": None})
        for r in rows:
            name = r["name"]
            if "/" in name:                      # Entsendungsrecht, kein Mensch
                continue
            sl = self.person_slug(name)
            if not sl:
                continue
            e = g[sl]
            e["names"][name] += 1
            if r["position"]:
                e["roles"][r["position"]] += 1
            j = r["report_year"]
            e["first"] = j if e["first"] is None else min(e["first"], j)
            e["last"] = j if e["last"] is None else max(e["last"], j)

        out: list[dict] = []
        for sl, e in g.items():
            anzeige = self._anzeige_name(e["names"], sl)
            vor, nach = self.namensteile(anzeige)
            if not vor or len(nach) < 3:
                continue
            out.append({
                "slug": sl, "name": anzeige, "vorname": vor, "nachname": nach,
                "art": "participation", "party": None, "organisation": None, "phasen": None,
                "role": e["roles"].most_common(1)[0][0] if e["roles"] else None,
                "aktiv": e["last"] == jungster,
                "von": str(e["first"]), "bis": str(e["last"]),
            })
        return out

    def personen_suchindex(self) -> list[tuple[str, str]]:
        """(Name, Partei) aller Ratspersonen mit bekannter Fraktion — Grundlage
        für die FDP/Volt-Auflösung und den Personen-Fragetyp. Die Stammdaten
        führen die EINZEL-Partei (Lükermann=Volt, Pfeiffer=FDP), während die
        Protokolle nur das Gruppen-Label kennen."""
        return [(r["name"], r["current_faction"]) for r in self._conn.execute(
            "SELECT name, current_faction FROM council_persons "
            "WHERE current_faction IS NOT NULL AND current_faction != ''")]

    @classmethod
    def _spricht_diese_person(cls, speaker: str, vorname: str, nachname: str,
                              bekannte_teile: frozenset[str] = frozenset()) -> bool:
        """Gehört dieser Sprecher-Eintrag zu genau dieser Person?

        Die Protokolle schreiben denselben Menschen mal „Andrea Hufeland", mal
        „Hufeland", mal „Ratsfrau Hufeland" — der Nachname allein muss also
        reichen. Er reicht aber NICHT, wenn der Eintrag einen anderen Vornamen
        trägt: „Dr. Ingo Harms" ist nicht „Tim Harms". Gemessen am Bestand ist
        das selten (5 von 279 Treffern bei Harms), aber auf einer Seite, die
        *alle* Beiträge zeigt, fällt jeder Fremdbeitrag auf.

        Mehrere Sprecher in einem Eintrag („Christoph Baak, Dr. Esther
        Niewerth-Baumann") gelten für beide — da haben tatsächlich beide geredet.

        ``bekannte_teile`` sind Namensteile, die zu **derselben** Person
        gehören, aber nicht in dieser Namensform stehen (s.
        :data:`council.namensformen.GRUPPEN`). Ohne sie fiele „Ratsherr Ebbeke
        Harms" durch die Fremdnamen-Prüfung, obwohl die Person genau die ist,
        deren Seite gerade aufgeschlagen wird.
        """
        if not nachname:
            return False
        roh = cls._falte_namen(speaker)
        if cls._falte_namen(nachname) not in roh:
            return False
        if not vorname:
            return True
        v = cls._falte_namen(vorname)
        if v in roh:
            return True
        # Kein passender Vorname: nur durchlassen, wenn der Eintrag überhaupt
        # keinen führt (reiner Nachname, ggf. mit Anrede oder Titel).
        rest = [t for t in re.split(r"[^\wäöüß]+", speaker.lower()) if len(t) > 1]
        nach_teile = set(re.split(r"[^\wäöüß]+", nachname.lower()))
        for t in rest:
            if (t in nach_teile or t in bekannte_teile
                    or cls._falte_namen(t) in bekannte_teile
                    or t.rstrip(".") in cls._HONORIFICS or t in cls._ANREDEN):
                continue
            return False   # ein fremder Namensbestandteil → andere Person
        return True

    @staticmethod
    def _falte_namen(s: str) -> str:
        s = s.lower()
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            s = s.replace(a, b)
        return s

    @staticmethod
    def _person_anzeige(name: str) -> str:
        """Anzeige-Name ohne führende Anrede („Herr Jens Freymuth" → „Jens
        Freymuth") — Titel wie „Dr." bleiben, die gehören zum Namen."""
        toks = name.split()
        while toks and toks[0].lower().rstrip(".") in PersonenMixin._ANREDEN_ANZEIGE:
            toks.pop(0)
        return " ".join(toks) or name

    @staticmethod
    def _person_slug(name: str) -> str:
        s = name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        toks = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in PersonenMixin._HONORIFICS]
        return "-".join(toks)

    def personen_kanon(self) -> dict[str, str]:
        """``{Namensform → kanonische Form}`` für die geführten Gruppen.

        Welche Form kanonisch ist, entscheidet die **jüngste Fundstelle** in
        den Anwesenheitslisten — die Zuordnung selbst ist gepflegt
        (:data:`council.namensformen.GRUPPEN`), die Anzeige nicht. Zieht eine
        Quelle auf eine andere Form um, zieht die Seite beim nächsten
        Protokoll von selbst mit; niemand muss eine Liste von Anzeigenamen
        nachführen.

        Gezählt wird über ``GROUP BY name`` (rund 1.300 verschiedene Namen
        gegenüber 22.000 Zeilen) und je Instanz einmal — die Karte hängt an
        jeder Gruppierung nach Person.
        """
        if self._kanon is None:
            from council import namensformen
            fund: dict[str, tuple[str, int]] = {}
            for r in self._conn.execute(
                    """SELECT a.name, MAX(cs.session_date) d, COUNT(*) n
                       FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                       WHERE a.name IS NOT NULL AND a.name != '' GROUP BY a.name"""):
                sl = self._person_slug(r["name"])
                if not sl or not r["d"]:
                    continue
                alt = fund.get(sl)
                fund[sl] = ((max(alt[0], r["d"]), alt[1] + r["n"]) if alt
                            else (r["d"], r["n"]))
            self._kanon = namensformen.kanonisch(fund)
        return self._kanon

    def person_slug(self, name: str) -> str:
        """Slug eines Namens, auf die kanonische Namensform gefaltet.

        Der Ersatz für ``_person_slug`` überall dort, wo nach Person
        **gruppiert** wird. Ohne die Faltung bekäme dieselbe Person zwei
        Einträge im Verzeichnis, zwei Personen-Seiten mit je einem Teil ihrer
        Sitzungen und kein Badge in den KI-Antworten."""
        sl = self._person_slug(name)
        return self.personen_kanon().get(sl, sl)

    def personen_namensformen(self, slug: str) -> list[str]:
        """Die belegten Schreibweisen einer Person, die der kanonischen Form
        zuerst — für Abgleiche, die auf **Namen** laufen statt auf Slugs
        (Wortbeiträge, Suche im Verzeichnis)."""
        kanon = self.personen_kanon()
        ziel = kanon.get(slug, slug)
        gefunden: dict[str, tuple[int, str]] = {}
        for (name,) in self._conn.execute(
                "SELECT DISTINCT name FROM council_attendance "
                "WHERE name IS NOT NULL AND name != ''"):
            sl = self._person_slug(name)
            if kanon.get(sl, sl) != ziel:
                continue
            anzeige = self._person_anzeige(name)
            gefunden.setdefault(anzeige, (0 if sl == ziel else 1, anzeige))
        return [n for n, _ in sorted(gefunden.items(), key=lambda p: p[1])]

    def _anzeige_name(self, namen, slug: str) -> str:
        """Die anzuzeigende Schreibweise aus einem ``Counter`` von Rohnamen.

        Zweistufig: Die **kanonische Namensform** bestimmt, welcher Name
        angezeigt wird (jüngste Fundstelle, s. :meth:`personen_kanon`);
        innerhalb dieser Form entscheidet wie eh und je die häufigste
        Schreibweise, damit ein einzelnes „Dr." mehr oder weniger die Anzeige
        nicht umwirft. Ohne Gruppe ändert sich dadurch nichts."""
        from collections import Counter
        eigene = Counter({n: c for n, c in namen.items()
                          if self._person_slug(n) == slug})
        return self._person_anzeige((eigene or namen).most_common(1)[0][0])

    def _organisation_label(self, raw: str | None) -> str | None:
        """Die entsendende Organisation aus einem Anwesenheits-Label —
        „Fridays for Future Oldenburg", „Behindertenbeirat", „Stadtsportbund".
        None für Fraktionen, Rollenwörter und Leerwerte."""
        from council.parties import classify_faction
        if not raw or not raw.strip():
            return None
        label = " ".join(raw.split())
        if classify_faction(label)["kind"] != "unknown":
            return None          # Partei, Gruppe oder parteilos — keine Organisation
        if self._ROLLEN_LABEL.match(label):
            return None
        return label

    def _ris_ratsmitglieder(self) -> set[str]:
        """Slugs der Personen, die das RIS selbst als Ratsmitglied führt.
        Zweite Quelle neben der Plenums-Anwesenheit: Nachrücker:innen, die noch
        in keiner Ratssitzung protokolliert sind, gehören trotzdem dazu.
        Das RIS kennt nur die laufende Wahlperiode — frühere Ratsleute trägt
        die Anwesenheit."""
        try:
            rows = self._conn.execute(
                """SELECT DISTINCT p.name FROM council_persons p
                   JOIN council_memberships m ON m.kpenr = p.kpenr
                   WHERE m.role LIKE 'Ratsmitglied%' OR m.role LIKE 'Grundmandat%'""").fetchall()
        except sqlite3.OperationalError as fehler:   # Stammdaten noch nicht geholt
            if not tabelle_fehlt(fehler):
                raise
            return set()
        return {self.person_slug(r["name"]) for r in rows}

    def _ris_fraktionen(self) -> dict[str, str]:
        """``{Slug: Fraktion laut RIS-Stammdaten}`` — die Stammdaten führen die
        EINZEL-Partei, wo das Protokoll nur die Gruppe kennt."""
        try:
            rows = self._conn.execute(
                "SELECT name, current_faction FROM council_persons "
                "WHERE current_faction IS NOT NULL AND current_faction != ''").fetchall()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return {}
        return {self.person_slug(r["name"]): r["current_faction"] for r in rows}

    def _partei_der_person(self, slug: str, label: str | None,
                           phasen: dict, ris_fraktion: dict[str, str]) -> str | None:
        """Die Zugehörigkeit, die eine Person WIRKLICH hat — Gruppen-Label der
        bloßen Zusammenschlüsse aufgelöst.

        Ein Mensch ist Mitglied einer Partei, nicht einer Gruppe: „FDP/Volt"
        war ein Zusammenschluss von FDP- und Volt-Leuten, und wer ausschied,
        während es die Gruppe noch gab, blieb im Verzeichnis für immer
        „FDP/Volt" — obwohl er FDP-Mitglied ist (Tims Befund 21.08.2026).
        Aufgelöst wird über belegte Quellen: erst die RIS-Stammdaten, dann die
        eigene Anwesenheits-Historie. Ohne Beleg bleibt das Gruppen-Label
        stehen — geraten wird nicht. „Für Oldenburg" und „IBO/LiVe" sind
        eigenständige Gruppen und bleiben unangetastet (s. AUFLOESBARE_GRUPPEN).
        """
        from council.parties import AUFLOESBARE_GRUPPEN, classify_faction
        if not label:
            return None
        c = classify_faction(label)
        if c["kind"] != "group" or c["label"] not in AUFLOESBARE_GRUPPEN:
            return label
        mitglieds_parteien = set(c["parties"])
        aus_ris = classify_faction(ris_fraktion.get(slug))
        if aus_ris["kind"] == "party" and aus_ris["label"] in mitglieds_parteien:
            return aus_ris["label"]
        # Eigene Historie, jüngste zuerst: Wer irgendwann unter der Einzelpartei
        # geführt wurde, gehört ihr an.
        for lab, _zeitraum in sorted(phasen.items(), key=lambda kv: kv[1][1], reverse=True):
            if lab in mitglieds_parteien and classify_faction(lab)["kind"] == "party":
                return lab
        return label

    def _filter_parteien(self, label: str | None) -> list[str]:
        """Unter welchen Filter-Werten diese Person erscheinen soll. Parteien
        und eigenständige Gruppen stehen für sich; ein verbliebenes
        Zusammenschluss-Label („Die Linke/Piraten", wo die Auflösung nichts
        fand) zählt für BEIDE Parteien — die Person verschwindet damit nicht
        aus dem Filter, und ihre Karte nennt weiter das ehrliche Gruppen-Label."""
        from council.parties import AUFLOESBARE_GRUPPEN, classify_faction
        if not label:
            return []
        c = classify_faction(label)
        if c["kind"] == "group" and c["label"] in AUFLOESBARE_GRUPPEN:
            return list(c["parties"])
        return [c["label"]] if c["kind"] in ("party", "group") else []

    def list_members(self) -> list[dict]:
        """Council members from attendance (role member/chair), grouped by *slug* so
        title variants of the same person ("Dr. X" and "X") merge into ONE entry (and the
        React list gets unique keys). Per person: canonical (most-frequent) name, die
        **letzte aktive Fraktion** (nicht die häufigste — Wechsler wie FDP→Volt oder
        Linke→BSW würden sonst ewig unter der alten laufen), distinct sessions attended
        and committees served. The member directory.

        Zusammengefasst wird über :meth:`person_slug`, also einschließlich der
        Namensformen aus :data:`council.namensformen.GRUPPEN` — sonst stünde
        dieselbe Person zweimal im Verzeichnis, jedes Mal mit einem Teil ihrer
        Sitzungen. ``formen`` nennt die belegten Schreibweisen; das Verzeichnis
        findet damit auch, wer nach der älteren sucht."""
        from collections import Counter, defaultdict
        from council.parties import classify_faction
        rows = self._conn.execute(
            """SELECT a.name, a.ksinr, a.party, cs.committee, cs.session_date
               FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
               WHERE a.role IN ('member','chair') AND a.name IS NOT NULL AND a.name != ''"""
        ).fetchall()
        g: dict = defaultdict(lambda: {"names": Counter(), "ksinrs": set(), "committees": set(),
                                       "first": None, "last": None, "party_at": None,
                                       "plenum": 0, "org_at": None, "phasen": {}})
        for r in rows:
            sl = self.person_slug(r["name"])
            if not sl:
                continue
            e = g[sl]
            e["names"][r["name"]] += 1
            e["ksinrs"].add(r["ksinr"])
            e["committees"].add(r["committee"])
            if r["committee"] == self.PLENUM:
                e["plenum"] += 1
            d = r["session_date"]
            e["first"] = d if e["first"] is None else min(e["first"], d)
            e["last"] = d if e["last"] is None else max(e["last"], d)
            # Nur Partei/Gruppe als „aktuelle" Zugehörigkeit merken (gruppen-bewusst:
            # „FDP/Volt"→Gruppe, nicht →FDP); blanke Streusitzungen (parteilos)
            # nicht, damit das Verzeichnis nicht auf einen Ausreißer umklappt.
            c = classify_faction(r["party"])
            p = c["label"] if c["kind"] in ("party", "group") else None
            if p and (e["party_at"] is None or d >= e["party_at"][0]):
                e["party_at"] = (d, p)
            if p:
                # Jede je belegte Zugehörigkeit mit ihrem Zeitraum: Wer die
                # Fraktion gewechselt hat, wird sonst in alten Protokollzeilen
                # nicht wiedererkannt („Finke (SPD)" ist Vally Finke, auch
                # wenn sie heute für „Für Oldenburg" sitzt).
                von, bis = e["phasen"].get(p, (d, d))
                e["phasen"][p] = (min(von, d), max(bis, d))
            # Entsendende Organisation der beratenden Mitglieder: dasselbe Feld
            # trägt bei ihnen keinen Fraktions-, sondern einen Verbandsnamen.
            org = self._organisation_label(r["party"])
            if org and (e["org_at"] is None or d >= e["org_at"][0]):
                e["org_at"] = (d, org)
        ris = self._ris_ratsmitglieder()
        ris_fraktion = self._ris_fraktionen()
        out = [{"slug": sl, "name": self._anzeige_name(e["names"], sl),
                "formen": sorted({self._person_anzeige(n) for n in e["names"]}),
                "party": self._partei_der_person(
                    sl, e["party_at"][1] if e["party_at"] else None, e["phasen"], ris_fraktion),
                # „beratend" ist KEIN Ratsmandat: Wer je in einer RATSSITZUNG
                # als Mitglied geführt wurde, hat eines — die Ausschüsse führen
                # daneben Verbände, Beiräte und Fachleute (Tims Skiba-Befund
                # 21.08.2026). Das RIS zählt als zweite Quelle für Nachrücker.
                "art": "council" if (e["plenum"] or sl in ris) else "advisory",
                "organisation": e["org_at"][1] if e["org_at"] else None,
                "phasen": [{"party": lab, "von": von[:4], "bis": bis[:4]}
                           for lab, (von, bis) in sorted(e["phasen"].items(),
                                                         key=lambda kv: kv[1][0])],
                "n": len(e["ksinrs"]), "committees": len(e["committees"]),
                "first": e["first"], "last": e["last"]}
               for sl, e in g.items()]
        for m in out:
            if m["art"] == "council":
                m["organisation"] = None   # ein Mandat entsendet niemand
            m["filter_parteien"] = self._filter_parteien(m["party"])
        out.sort(key=lambda m: -m["n"])
        return out

    def member_name(self, slug: str) -> str | None:
        """Der kanonische (häufigste) Name zu einem Slug — die schlanke Auskunft
        für Endpunkte, die nicht das ganze Profil brauchen. Ohne Anrede, wie in
        ``member_detail`` und im Verzeichnis (#419)."""
        from collections import Counter
        slug = self.personen_kanon().get(slug, slug)
        namen = [r["name"] for r in self._conn.execute(
            "SELECT name FROM council_attendance WHERE role IN ('member','chair') "
            "AND name IS NOT NULL AND name != ''")]
        passend = [n for n in namen if self.person_slug(n) == slug]
        return self._anzeige_name(Counter(passend), slug) if passend else None

    def member_detail(self, slug: str) -> dict | None:
        """One member — all name variants merged by slug: party, sessions, active span,
        committees served (with counts and chair flag) and their most recent sessions.

        Der angefragte Slug wird zuerst auf die kanonische Namensform gefaltet
        (:meth:`personen_kanon`): Ein geteilter Link auf die ältere Form führt
        damit auf **dasselbe** Profil, und ``slug`` in der Antwort nennt die
        kanonische Adresse."""
        from collections import Counter
        from council.parties import classify_faction
        slug = self.personen_kanon().get(slug, slug)
        names = [r["name"] for r in self._conn.execute(
            "SELECT DISTINCT name FROM council_attendance WHERE role IN ('member','chair') "
            "AND name IS NOT NULL AND name != ''")]
        matched = [n for n in names if self.person_slug(n) == slug]
        if not matched:
            return None
        ph = ",".join("?" * len(matched))
        name = self._anzeige_name(Counter(  # kanonische Form, darin häufigste Schreibweise
            r["name"] for r in self._conn.execute(
                f"SELECT name FROM council_attendance WHERE name IN ({ph}) AND role IN ('member','chair')",
                matched)), slug)
        chairs = {r["committee"] for r in self._conn.execute(
            f"SELECT DISTINCT cs.committee FROM council_attendance a JOIN council_sessions cs ON cs.ksinr=a.ksinr "
            f"WHERE a.name IN ({ph}) AND a.role='chair'", matched)}
        committees = self._conn.execute(
            f"""SELECT cs.committee, COUNT(DISTINCT a.ksinr) n
                FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('member','chair')
                GROUP BY cs.committee ORDER BY n DESC""", matched).fetchall()
        span = self._conn.execute(
            f"""SELECT COUNT(DISTINCT a.ksinr) n, MIN(cs.session_date) first, MAX(cs.session_date) last
                FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('member','chair')""", matched).fetchone()
        recent = self._conn.execute(
            f"""SELECT cs.ksinr, cs.committee, cs.session_date FROM council_attendance a
                JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('member','chair')
                ORDER BY cs.session_date DESC LIMIT 12""", matched).fetchall()
        # Fraktions-/Gruppen-Verlauf aus der Anwesenheit: aufeinanderfolgende
        # Sitzungen derselben Zugehörigkeit zu Phasen zusammengefasst — die einzige
        # echte Zeitreihe, denn das Ratsinfo überschreibt Fraktionen rückwirkend.
        # Wichtig: `classify_faction` hält GRUPPEN als Gruppen fest (statt sie auf
        # eine Partei zu kollabieren) und blanke Label als „parteilos" — sonst
        # erschiene z. B. ein „FDP/Volt"-Gruppenmitglied fälschlich als FDP.
        runs: list[dict] = []
        for r in self._conn.execute(
            f"""SELECT cs.session_date d, a.party FROM council_attendance a
                JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('member','chair')
                ORDER BY cs.session_date""", matched):
            c = classify_faction(r["party"])
            if c["kind"] == "unknown":
                continue
            label = c["label"]
            if runs and runs[-1]["label"] == label:
                runs[-1]["last"] = r["d"]
                runs[-1]["n"] += 1
            else:
                runs.append({"label": label, "kind": c["kind"], "parties": c["parties"],
                             "first": r["d"], "last": r["d"], "n": 1})
        # Einzelne Ausreißer-Sitzungen (Tippfehler/fehlende Extraktion) zwischen
        # zwei gleichen Phasen glätten, dann angrenzende Phasen mergen.
        cleaned = [run for i, run in enumerate(runs)
                   if not (run["n"] == 1 and 0 < i < len(runs) - 1
                           and runs[i - 1]["label"] == runs[i + 1]["label"] != run["label"])]
        timeline: list[dict] = []
        for run in cleaned:
            if timeline and timeline[-1]["label"] == run["label"]:
                timeline[-1]["last"] = run["last"]
                timeline[-1]["n"] += run["n"]
            else:
                timeline.append(dict(run))
        # Wortbeiträge der Person (Personen-Paket 10.08.26): die jüngsten
        # Beiträge in voller Länge — das Beleg-Versprechen gilt auch hier.
        # Nachname = letztes Namens-Token ohne Titel (Umlaute intakt fürs LIKE).
        # Erste Seite der Wortbeiträge gleich mitliefern (die Seite soll ohne
        # zweiten Rundlauf etwas zeigen); weitere Seiten und der Gremien-Filter
        # laufen über /person/{slug}/wortbeitraege.
        wb = self.wortbeitraege_person(name, limit=10)
        # Mandat oder beratende Mitwirkung? Dieselbe Unterscheidung wie im
        # Verzeichnis (s. list_members) — und für beratende Mitglieder ist die
        # Fraktions-Zeitreihe gegenstandslos: Ihr Anwesenheits-Label nennt die
        # entsendende Organisation, kein Fraktions-Label. Ohne diese Weiche
        # stand auf ihrer Seite „Ratsmitglied · parteilos" (Tims Befund
        # 21.08.2026) — beides falsch.
        #
        # Bewusst aus den Zeilen DIESER Person statt aus `list_members()`: Das
        # Verzeichnis scannt alle 15.000 Anwesenheitszeilen, und eine
        # Personen-Seite braucht davon genau eine Person. Der Umweg kostete
        # rund 300 ms je Aufruf (gemessen 21.08.2026).
        im_plenum = self._conn.execute(
            f"""SELECT 1 FROM council_attendance a JOIN council_sessions cs ON cs.ksinr = a.ksinr
                WHERE a.name IN ({ph}) AND a.role IN ('member','chair')
                  AND cs.committee = ? LIMIT 1""", matched + [self.PLENUM]).fetchone()
        # `slug` ist hier schon die kanonische Namensform (s. Kopf der Methode).
        art = "council" if (im_plenum or slug in self._ris_ratsmitglieder()) else "advisory"
        organisation = None
        if art == "advisory":
            timeline = []
            # Jüngstes Label, das eine Organisation nennt (kein Rollenwort).
            for r in self._conn.execute(
                    f"""SELECT a.party FROM council_attendance a
                        JOIN council_sessions cs ON cs.ksinr = a.ksinr
                        WHERE a.name IN ({ph}) AND a.role IN ('member','chair')
                        ORDER BY cs.session_date DESC""", matched):
                organisation = self._organisation_label(r["party"])
                if organisation:
                    break
        aktuell = None
        if timeline:
            letzte = timeline[-1]
            phasen = {t["label"]: (t["first"], t["last"]) for t in timeline}
            aufgeloest = self._partei_der_person(
                slug, letzte["label"], phasen, self._ris_fraktionen())
            aktuell = ({"label": aufgeloest, "kind": "party", "parties": [aufgeloest]}
                       if aufgeloest != letzte["label"]
                       else {"label": letzte["label"], "kind": letzte["kind"],
                             "parties": letzte["parties"]})
        return {
            "name": name, "slug": slug,
            # Aktuelle Zugehörigkeit (Ende der geglätteten Zeitreihe) — nicht die
            # häufigste: Wechsler (FDP/Volt→Volt, Linke→BSW) zeigen sonst die alte.
            "party": aktuell["label"] if aktuell else None,
            # Der Kopf der Seite nennt dieselbe Zugehörigkeit wie das
            # Verzeichnis: Zusammenschluss-Label aufgelöst, wo es belegt ist
            # („FDP/Volt" → FDP). Die Zeitreihe darunter bleibt quellentreu —
            # sie erzählt, was die Protokolle DAMALS schrieben.
            "current_affiliation": aktuell,
            "kind": art,
            "organisation": organisation,
            "n_sessions": span["n"], "active_from": span["first"], "active_to": span["last"],
            "faction_timeline": timeline,
            "ris": self.person_stammdaten_for_names(matched),
            "committees": [{"committee": r["committee"], "n": r["n"], "chair": r["committee"] in chairs}
                           for r in committees],
            "recent": [{"ksinr": r["ksinr"], "committee": r["committee"], "session_date": r["session_date"]}
                       for r in recent],
            "speeches": wb["items"],
            "speeches_total": wb["overall"],
            "speeches_committees": wb["committees"],
        }

    def verwaltung_name(self, slug: str) -> str | None:
        """Kanonischer Name einer Verwaltungsperson zu ihrem Slug — schlanke
        Auskunft für den Wortbeiträge-Endpunkt, ohne den ganzen Lexikon-Aufbau
        aus personen_lexikon(). Gegenstück zu member_name(). Keine
        Rollen-Prüfung hier: Wer einmal einen Steckbrief hatte
        (verwaltung_detail), soll auch weitere Seiten seiner Wortbeiträge
        laden können."""
        from collections import Counter
        namen = [r["name"] for r in self._conn.execute(
            "SELECT name FROM council_attendance WHERE role = 'administration' "
            "AND name IS NOT NULL AND name != ''")]
        passend = [n for n in namen if self._person_slug(n) == slug]
        return self._person_anzeige(Counter(passend).most_common(1)[0][0]) if passend else None

    def verwaltung_detail(self, slug: str) -> dict | None:
        """Schmaler Steckbrief für Verwaltungsleute mit erkanntem Amt (Tims
        Wunsch 19.08., im Anschluss an den Figura-Badge-Fund): NUR für
        Oberbürgermeister/-in, Stadtkämmerer/-in, Stadtbaurat/-rätin,
        Stadtrat/-rätin — dieselbe Erkennung wie in personen_lexikon()
        (_ROLLEN_RE übers note-Feld). Ohne erkanntes Amt gibt es keine Seite:
        „Ein toter Link ist schlimmer als kein Link" (schon in #588 so
        entschieden, für die Aufsichtsräte-Verlinkung).

        Bewusst KEIN Nachbau von member_detail(): Fraktions-Zeitleiste,
        Vorsitz-Zähler und Gremien-Präsenz passen auf ein Mandat, nicht auf
        ein Amt — ein Oberbürgermeister sitzt kraft Amtes in praktisch jedem
        Gremium, das ist keine gewählte Mitgliedschaft. Der Zeitraum ist
        ehrlich als Jahres-Spanne der Protokoll-Erwähnungen beschriftet,
        keine amtliche Amtszeit: SessionNet selbst führt Verwaltung nicht als
        Mandatsträger:innen (council/stammdaten.py:``fetch_mandatstraeger``).

        Nutzt personen_lexikon() statt einer eigenen Aggregation — dieselbe
        Gruppierung für alle Verwaltungsleute an einer Stelle, nicht zwei
        Fassungen, die auseinanderlaufen können."""
        eintrag = next((p for p in self.personen_lexikon()
                        if p["slug"] == slug and p["art"] == "city" and p["role"]), None)
        if not eintrag:
            return None
        wb = self.wortbeitraege_person(eintrag["name"], limit=10)
        return {
            "type": "administration", "name": eintrag["name"], "slug": slug,
            "role": eintrag["role"], "aktiv": eintrag["aktiv"],
            "von": eintrag["von"], "bis": eintrag["bis"],
            "speeches": wb["items"],
            "speeches_total": wb["overall"],
            "speeches_committees": wb["committees"],
        }

    def aktive_fraktionen(self, monate: int = 12, min_beitraege: int = 5) -> list[str]:
        """Fraktions-Labels mit nennenswerten Wortbeiträgen im Zeitraum — die
        deterministische „Wer sitzt gerade im Rat"-Liste für die Vollständig-
        keits-Zeile des Parteien-Bausteins (Tims Direktive 10.08.), ohne
        kuratierte Stammdaten."""
        rows = self._conn.execute(
            "SELECT w.party, COUNT(*) n FROM council_speeches w "
            "JOIN council_sessions s ON s.ksinr = w.ksinr "
            "WHERE w.party IS NOT NULL AND w.party != '' "
            "AND s.session_date >= date('now', ?) "
            "GROUP BY w.party HAVING n >= ? ORDER BY n DESC",
            (f"-{int(monate)} months", int(min_beitraege))).fetchall()
        return [r[0] for r in rows]
