"""What a council page SHOWS, as lines for Lotti's prompt.

**Wozu.** Die Fakten-Eval (``docs/fakten-eval.md``, 23.09.2026) fand auf den
Rats-Seiten dasselbe Muster: Die Seite zeigte die Antwort, Lottis Prompt
nicht. Auf einer Sitzungsseite stand die Tagesordnung, Lotti kannte Gremium
und Datum; auf einer Personenseite standen die Ausschüsse, Lotti kannte den
Namen. Gemessen mit GPT-6 Luna: 17 Kontextfehler auf den Seitentypen Sitzung,
Person, Ort und Thema — kein Modell kann daraus eine gute Antwort machen
(Tim: „Wenn wir im Kontext schon Mist haben, kann das beste Modell nichts
Gutes draus machen.“).

**Die Regel: nur, was die Seite selbst zeigt.** Jede Funktion hier liest
dieselben Store-Methoden wie der Endpunkt, von dem die Seite lebt
(``/council/session/{ksinr}``, ``/council/person/{slug}``,
``/council/place/{id}``, ``/council/entity/{slug}``, ``/council/decision/{id}``)
— nachgeschlagen über die Kennung aus der Adresszeile, nie über eine Suche
und nie aus dem Browser übernommen. Was die Seite NICHT zeigt, kommt auch
hier nicht hinein: keine Pressemitteilungen zum Beschluss (die Seite verlinkt
nur eine NWZ-Suche, und eine Verknüpfung Beschluss → Pressemitteilung gibt es
nicht — sie zu erraten wäre die Suche, die dieses Modul nicht macht), keine
Ergebnisse nichtöffentlicher Tagesordnungspunkte, keine Wortbeiträge im
Wortlaut.

**Rechte.** Alle fünf Endpunkte sind ohne Anmeldung lesbar (s.
``decision_detail``); was hier steht, sieht also jedes Konto auf der Seite.
Der Haushalts-Anschluss einer Beschluss-Seite (``budget_link``) bleibt
draußen, weil er am Recht ``budget`` hängt.

**Deckel statt Vollständigkeit.** Eine Rats-Tagesordnung hat bis zu 60
öffentliche Punkte (Rat 01.06.2026: 57 Punkte, 5.486 Zeichen Titel); jede
Liste ist deshalb gedeckelt, jeder Titel gekürzt. Die Zahlen stehen bei den
Konstanten.

**Fremdtext.** Titel, Wortlaut und Beschreibungen hier stammen aus
Ratsunterlagen. Die Zeilen gehen in ``assistant._record_block``, der den
ganzen Block zwischen Marker setzt — dieselbe Regel wie für Element-Text und
Markierung.

**Robust gegen dünne Stores.** Die Tests reichen Attrappen mit drei Methoden
herein, alte Datenbanken kennen manche Tabelle nicht: Jede Abfrage läuft über
:func:`_frage`, und was fehlt, fällt weg, statt die Erklärung zu kippen.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from typing import Any

#: Tagesordnungspunkte je Sitzung. 60 deckt jede Sitzung im Bestand bis auf
#: Ausreißer (Rat 01.06.2026: 57 öffentliche Punkte).
AGENDA_MAX = 60
#: Titel eines Tagesordnungspunkts. 160 Zeichen tragen den Gegenstand samt
#: Betrag („Überplanmäßige Bewilligung von Mehraufwendungen in Höhe von
#: 9.512.500 Euro für den Teilhaushalt 10, …“ — der Betrag steht bei Zeichen 60).
AGENDA_TITEL_MAX = 160
#: Beschlüsse in einer Liste (Ort, Thema, Themenfeld): die jüngsten zuerst,
#: wie die Seite sie ordnet.
BESCHLUESSE_MAX = 8
BESCHLUSS_TITEL_MAX = 160
#: „Finanzielle Auswirkungen“ der Vorlage — auf der Beschluss-Seite die Karte
#: „Was kostet das?“. Beim BTB-Zuschuss (26/0353) stehen alle fünf
#: Jahresbeträge in den ersten 330 Zeichen.
FINANZEN_MAX = 700
#: Gremien einer Person: laufende vollständig (höchstens so viele), frühere
#: nur die jüngsten.
GREMIEN_MAX = 12
FRUEHERE_GREMIEN_MAX = 6
#: Der maschinelle Rückblick eines Themenfelds (``council_field_recaps``).
RUECKBLICK_MAX = 900
BESCHREIBUNG_MAX = 500

_ENTITY_ART = {"place": "Ort", "organisation": "Organisation", "project": "Projekt"}


def kuerze(text: str | None, max_len: int) -> str:
    """Leerraum falten und hart schneiden — wie ``assistant.kuerze``.

    Hier noch einmal, weil ``assistant`` dieses Modul importiert; ein Import
    zurück wäre ein Ring.
    """
    sauber = " ".join((text or "").split())
    return sauber if len(sauber) <= max_len else sauber[:max_len].rstrip() + " …"


def _frage(fn: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    """Eine Store-Abfrage, die fehlen oder werfen darf — dann ``None``."""
    if fn is None:
        return None
    try:
        return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001 — ein fehlender Beleg ist kein Fehler
        return None


def _datum(iso: str | None) -> str:
    from council.ergebnisse import datum_lang
    return datum_lang(iso or "") if iso else "unbekanntem Datum"


def _ergebnis(outcome: str | None) -> str:
    from council.ergebnisse import ERGEBNIS_WORT
    return ERGEBNIS_WORT.get(str(outcome), str(outcome)) if outcome else ""


def decision_line(d: dict, *, gremium: bool = True) -> str:
    """„1. Juni 2026, Rat: „…“ — angenommen (Nr. 8677)“ — eine Zeile je Beschluss.

    Die Nummer steht dabei, weil sie der einzige eindeutige Name eines
    Beschlusses ist: Zwei Beschlüsse derselben Sitzung tragen oft fast
    denselben Titel (Stadion 01.06.2026: fünf).
    """
    kopf = _datum(d.get("session_date"))
    if gremium and d.get("committee"):
        kopf += f", {d['committee']}"
    ergebnis = _ergebnis(d.get("outcome"))
    return (f"{kopf}: „{kuerze(d.get('title'), BESCHLUSS_TITEL_MAX)}“"
            + (f" — {ergebnis}" if ergebnis else "")
            + (f" (Nr. {d['id']})" if d.get("id") else ""))


# --------------------------------------------------------------------------- #
# Beschluss
# --------------------------------------------------------------------------- #

def decision_extra(store, d: dict) -> list[str]:
    """Was die Beschluss-Seite über den Block hinaus zeigt.

    * ``raw_result`` — der Wortlaut des Protokolls unter dem Abstimmungsbalken
      („einstimmig bei neun Enthaltungen“). Ohne ihn las Lotti aus
      ``vote = majority`` ein „mehrheitlich“, wo das Protokoll „einstimmig“
      sagt (Fall ``lotti-schulbezirke-gegenstimmen``).
    * die **finanziellen Auswirkungen** der Vorlage — auf der Seite die Karte
      „Was kostet das?“. Beschlusstext und Kurzfassung nennen beim
      BTB-Zuschuss keinen Betrag, die Vorlage alle fünf (Fall
      ``lotti-btb-betrag``).
    """
    zeilen: list[str] = []
    roh = (d.get("raw_result") or "").strip(" -–\n\t")
    if roh:
        zeilen.append(f"  Im Protokoll steht zur Abstimmung wörtlich: „{kuerze(roh, 200)}“")
    nummer = d.get("template_number")
    if nummer:
        v = _frage(getattr(store, "get_vorlage_by_nr", None), nummer) or {}
        finanzen = (v.get("financial_impact") or "").strip()
        if finanzen:
            zeilen.append("  Finanzielle Auswirkungen laut Vorlage "
                          f"{nummer}: {kuerze(finanzen, FINANZEN_MAX)}")
    return zeilen


# --------------------------------------------------------------------------- #
# Sitzung
# --------------------------------------------------------------------------- #

def _top_key(nummer: str | None) -> str:
    """„Ö 6.1“ → „6.1“ — wie ``topKey`` im Frontend (``tagesordnung.tsx``)."""
    return re.sub(r"^[^\W\d_]+\s+", "", (nummer or "").strip()).strip()


#: Das Ratsinformationssystem hängt das Ergebnis an den Titel an: „… -
#: Beschluss Beschluss: ungeändert beschlossen Abstimmung: Ja: 10, Nein: 1“ —
#: bei 9.658 von 19.470 Tagesordnungspunkten (23.09.2026).
_RIS_ERGEBNIS = re.compile(r"\s+Beschluss:\s+(?P<ergebnis>\S.*)$")


def _titel_und_ris_ergebnis(titel: str | None) -> tuple[str, str]:
    """Titel und angehängtes RIS-Ergebnis getrennt.

    Getrennt, weil der Titel gekürzt wird und das Ergebnis am Ende stünde —
    genau das Stück, das die Kürzung abschnitte. Liegt ein Beschluss aus dem
    Protokoll vor, gilt der; das RIS-Ergebnis ist dann doppelt.
    """
    m = _RIS_ERGEBNIS.search(titel or "")
    if not m:
        return titel or "", ""
    return (titel or "")[:m.start()], m.group("ergebnis").strip()


def session_lines(store, ksinr: int, heute: date | None = None) -> list[str]:
    """Kopf, Ort und Tagesordnung samt Ergebnissen — wie ``/council/sitzung``.

    **Ergebnisse nur für öffentliche Punkte**, wie auf der Seite
    (``it.is_public ? outcomeByItem[…] : undefined``). Nichtöffentliche Punkte
    heißen im Bestand ohnehin „gesperrte Information“; sie stehen hier nur als
    Zahl, statt 20 Zeilen desselben Worts in den Prompt zu legen.

    **Ob sie schon war**, steht ausdrücklich dabei: „Welche Ergebnisse hatte
    diese Sitzung?“ zu einer Sitzung nächste Woche ist keine Frage nach
    Ergebnissen früherer Sitzungen (Fall ``lotti-nd-sitzung-ergebnisse``).
    """
    s = _frage(getattr(store, "get_session", None), int(ksinr))
    if not s:
        return []
    heute = heute or date.today()
    tag = str(s.get("session_date") or "")[:10]
    wann = _datum(tag)
    if s.get("session_time"):
        wann += f", {str(s['session_time'])[:5]} Uhr"
    kopf = f"Die Sitzung auf dieser Seite: {s.get('committee') or 'Gremium unbekannt'} am {wann}"
    zeilen = [kopf]
    zeilen.append(f"  Sitzungsort: {kuerze(s.get('location'), 160)}" if s.get("location")
                  else "  Sitzungsort: noch nicht angegeben")
    if tag:
        zeilen.append("  Die Sitzung liegt in der ZUKUNFT — Ergebnisse gibt es noch keine."
                      if tag > heute.isoformat() else
                      "  Die Sitzung hat heute stattgefunden bzw. findet heute statt."
                      if tag == heute.isoformat() else "  Die Sitzung hat bereits stattgefunden.")

    vorsitz = [a.get("name") for a in (_frage(getattr(store, "get_attendance", None), int(ksinr))
                                       or []) if a.get("role") == "chair" and a.get("name")]
    if vorsitz:
        zeilen.append(f"  Vorsitz laut Anwesenheitsliste: {', '.join(dict.fromkeys(vorsitz))}")

    punkte = _frage(getattr(store, "agenda_items", None), int(ksinr)) or []
    if not punkte:
        zeilen.append("  Tagesordnung: liegt noch nicht vor.")
        return zeilen

    beschluesse: dict[str, dict] = {}
    for d in _frage(getattr(store, "get_decisions", None), int(ksinr)) or []:
        if d.get("kind", "decision") == "decision" and d.get("item_number"):
            beschluesse.setdefault(_top_key(d["item_number"]), d)
    video: dict[str, dict] = {}
    for v in _frage(getattr(store, "get_video_results", None), int(ksinr)) or []:
        key = re.sub(r"^[ÖN]\s+", "", str(v.get("item_number") or ""), flags=re.I).strip()
        video.setdefault(key, v)

    oeffentlich = [p for p in punkte if p.get("is_public", 1)]
    geheim = len(punkte) - len(oeffentlich)
    mit_ergebnis = sum(1 for p in oeffentlich if _top_key(p.get("item_number")) in beschluesse)
    zeilen.append(f"  Tagesordnung ({len(oeffentlich)} öffentliche Punkte"
                  + (f", davon {mit_ergebnis} mit Ergebnis aus dem Protokoll" if mit_ergebnis
                     else ", noch ohne Protokoll") + "):")
    for p in oeffentlich[:AGENDA_MAX]:
        nr = (p.get("item_number") or "").strip()
        titel, ris = _titel_und_ris_ergebnis(p.get("title"))
        zeile = f"    {nr} {kuerze(titel, AGENDA_TITEL_MAX)}".rstrip()
        d = beschluesse.get(_top_key(nr))
        v = video.get(re.sub(r"^[ÖN]\s+", "", nr, flags=re.I).strip())
        if d:
            ergebnis = _ergebnis(d.get("outcome"))
            zeile += (f" — {ergebnis}" if ergebnis else "") + (f" (Nr. {d['id']})" if d.get("id") else "")
        elif ris:
            zeile += f" — laut Ratsinformationssystem: {kuerze(ris, 90)}"
        elif v and v.get("outcome"):
            zeile += f" — vorläufig laut Videoaufzeichnung: {str(v['outcome']).replace('_', ' ')}"
        zeilen.append(zeile)
    if len(oeffentlich) > AGENDA_MAX:
        zeilen.append(f"    … und {len(oeffentlich) - AGENDA_MAX} weitere Punkte")
    if geheim:
        zeilen.append(f"  Nichtöffentlicher Teil: {geheim} Punkte, Inhalt nicht veröffentlicht.")
    return zeilen


# --------------------------------------------------------------------------- #
# Person
# --------------------------------------------------------------------------- #

def _rolle(rolle: str | None) -> str:
    """„Ausschussmitglied“ und „Ratsmitglied“ sagen nichts, was die Liste
    nicht schon sagt; Vorsitz und Stellvertretung schon."""
    r = (rolle or "").strip()
    return "" if not r or r.lower() in ("ausschussmitglied", "ratsmitglied", "mitglied") else r


def person_lines(store, slug: str) -> list[str]:
    """Zugehörigkeit, Gremien und Zeitraum — wie ``/council/person``.

    **Laufende Mitgliedschaften aus dem Ratsinformationssystem**
    (``council_memberships`` ohne ``valid_until``), so wie die Seite sie als
    „aktuell“ zeigt. Die Gremien aus den Anwesenheitslisten zählen dagegen
    alle Sitzungen seit 2011 — als Antwort auf „In welchen Ausschüssen sitzt
    sie?“ wären sie eine Liste von damals.

    **Kein Wortbeitrag im Wortlaut**, nur ihre Zahl: Die Seite zeigt sie, aber
    sie sind Protokolltext von Dritten und je Person Hunderte Zeilen; wer
    wissen will, was jemand gesagt hat, fragt das Archiv.
    """
    d = _frage(getattr(store, "member_detail", None), slug)
    if not d:
        v = _frage(getattr(store, "verwaltung_detail", None), slug)
        if v:
            zeilen = [f"Die Person auf dieser Seite: {v.get('name')} — Verwaltung"
                      + (f", {v['role']}" if v.get("role") else "")]
            if v.get("speeches_total"):
                zeilen.append(f"  Wortbeiträge in den Protokollen: {v['speeches_total']}")
            return zeilen
        name = (_frage(getattr(store, "member_name", None), slug)
                or _frage(getattr(store, "verwaltung_name", None), slug))
        return [f"Die Person auf dieser Seite: {name}"] if name else []

    if d.get("kind") == "advisory":
        wer = "beratendes Mitglied in Ausschüssen (kein Ratsmandat)" + (
            f", entsandt von {d['organisation']}" if d.get("organisation") else "")
    else:
        wer = "Ratsmitglied" + (f", heute {d['party']}" if d.get("party") else "")
    zeilen = [f"Die Person auf dieser Seite: {d.get('name')} — {wer}"]
    if d.get("n_sessions"):
        zeilen.append(f"  In Sitzungen anwesend: {d['n_sessions']}, vom "
                      f"{_datum(d.get('active_from'))} bis zum {_datum(d.get('active_to'))}")
    phasen = d.get("faction_timeline") or []
    if len(phasen) > 1:
        zeilen.append("  Fraktion bzw. Gruppe im Zeitverlauf (laut Anwesenheitslisten): "
                      + "; ".join(f"{p['label']} ({str(p['first'])[:7]} bis {str(p['last'])[:7]})"
                                  for p in phasen))
    ris = d.get("ris") or {}
    if ris.get("current_faction") and ris["current_faction"] != d.get("party"):
        zeilen.append(f"  Fraktion laut Ratsinformationssystem: {ris['current_faction']}")
    mitgliedschaften = ris.get("memberships") or []
    laufend = [m for m in mitgliedschaften if not m.get("valid_until")]
    frueher = [m for m in mitgliedschaften if m.get("valid_until")]

    def gremium(m: dict, mit_zeit: bool) -> str:
        rolle = _rolle(m.get("role"))
        teile = [x for x in (rolle, (f"seit {str(m.get('valid_from'))[:7]}" if not mit_zeit
                                     else f"{str(m.get('valid_from'))[:7]} bis "
                                          f"{str(m.get('valid_until'))[:7]}")) if x]
        return f"{m.get('committee')} ({', '.join(teile)})" if teile else str(m.get("committee"))

    if laufend:
        zeilen.append("  Aktuelle Mitgliedschaften (Ratsinformationssystem): "
                      + "; ".join(gremium(m, False) for m in laufend[:GREMIEN_MAX]))
    elif d.get("committees"):
        # Ohne RIS-Stammdaten bleibt nur die Anwesenheit — dann ausdrücklich
        # als das, was sie ist.
        zeilen.append("  Gremien laut Anwesenheitslisten (alle Jahre, Sitzungen): "
                      + "; ".join(f"{c['committee']} ({c['n']}{', Vorsitz' if c.get('chair') else ''})"
                                  for c in d["committees"][:GREMIEN_MAX]))
    if frueher:
        zeilen.append("  Frühere Mitgliedschaften: "
                      + "; ".join(gremium(m, True) for m in frueher[:FRUEHERE_GREMIEN_MAX]))
    if d.get("speeches_total"):
        zeilen.append(f"  Wortbeiträge in den Protokollen: {d['speeches_total']}")
    return zeilen


# --------------------------------------------------------------------------- #
# Ort
# --------------------------------------------------------------------------- #

def place_lines(store, place_id: str) -> list[str]:
    """Der Ort und seine jüngsten Beschlüsse — wie ``/council/ort``."""
    ort = _frage(getattr(store, "resolve_place", None), str(place_id))
    if not ort:
        return []
    zeilen = [f"Der Ort auf dieser Seite: {ort.name} ({ort.kind})"
              + (f" — {kuerze(ort.description, 400)}" if ort.description else "")]
    gesamt = _frage(getattr(store, "count_decisions", None), district=ort.id)
    liste = _frage(getattr(store, "search_decisions", None), district=ort.id,
                   limit=BESCHLUESSE_MAX) or []
    if liste:
        zeilen.append(f"  Beschlüsse, deren Text diesen Ort nennt: {gesamt or len(liste)}"
                      "; die jüngsten zuerst:")
        zeilen += [f"    · {decision_line(d)}" for d in liste]
    elif gesamt == 0:
        zeilen.append("  Zu diesem Ort ist kein Beschluss erfasst.")
    return zeilen


# --------------------------------------------------------------------------- #
# Thema (Entität) und Themenfeld
# --------------------------------------------------------------------------- #

def entity_lines(store, slug: str) -> list[str]:
    """Ein Thema — Projekt, Organisation oder Ort — wie ``/council/thema``.

    **Die Seite ist eine Entitäten-Seite**, kein Themenfeld: ``themaHref``
    führt auf ``/council/entity/{slug}`` (Fliegerhorst, Stadtsportbund, …).
    Bis 23.09.2026 las Lotti den Slug nur als Themenfeld-Schlüssel aus
    ``POLICY_FIELDS`` — auf jeder echten Themen-Seite also ins Leere.
    """
    e = _frage(getattr(store, "entity_detail", None), slug)
    if not e:
        return []
    ent = e.get("entity") or {}
    beschluesse = e.get("decisions") or []
    zeilen = [f"Das Thema auf dieser Seite: {ent.get('name')} "
              f"({_ENTITY_ART.get(str(ent.get('kind')), 'Thema')}) — "
              f"{len(beschluesse)} Beschlüsse"]
    if e.get("description"):
        zeilen.append(f"  Beschreibung (maschinell zusammengefasst): "
                      f"{kuerze(e['description'], BESCHREIBUNG_MAX)}")
    if e.get("money"):
        from council import geld
        zeilen.append(f"  In den Beschlüssen erkannte Beträge, zusammen: {geld.de_betrag(e['money'])}")
    if beschluesse:
        zeilen.append("  Die jüngsten Beschlüsse:")
        zeilen += [f"    · {decision_line(d)}" for d in beschluesse[:BESCHLUESSE_MAX]]
    return zeilen


def field_lines(store, slug: str) -> list[str]:
    """Ein Themenfeld: Label, Rückblick und die jüngsten Beschlüsse.

    Die Themenfeld-Rückblicke stehen im Register „Themen“ und in der
    Auswertung; wer mit einem Feld-Schlüssel auf ``/council/thema`` landet,
    bekommt dasselbe, was diese Karten zeigen.
    """
    from council.topics import POLICY_FIELDS
    feld = POLICY_FIELDS.get(str(slug))
    if not feld:
        return []
    zeilen = [f"Das Themenfeld auf dieser Seite: {feld[0]} — {feld[1]}"]
    rueckblick = (_frage(getattr(store, "field_recaps_by_key", None)) or {}).get(str(slug))
    if rueckblick and rueckblick.get("summary"):
        zeitraum = " bis ".join(_datum(rueckblick[k]) for k in ("period_from", "period_to")
                                if rueckblick.get(k))
        zeilen.append("  Rückblick (maschinell zusammengefasst"
                      + (f", {zeitraum}" if zeitraum else "") + "): "
                      + kuerze(rueckblick["summary"], RUECKBLICK_MAX))
    liste = _frage(getattr(store, "search_decisions", None), field=str(slug),
                   limit=BESCHLUESSE_MAX) or []
    if liste:
        zeilen.append("  Die jüngsten Beschlüsse in diesem Feld:")
        zeilen += [f"    · {decision_line(d)}" for d in liste]
    return zeilen
