"""Der Kartentext für Social Media: ein Punkt, ein neutraler Satz.

Warum es diesen dritten Text neben Kurzfassung und Tragweite-Grund gibt,
steht bei der Tabelle ``agenda_item_social`` in ``store.py``. Kurz:

* ``agenda_item_summaries.summary`` entsteht **allein aus dem Titel** — der
  eigene Prompt sagt dem Modell wörtlich „Du kennst nur den Titel des
  Punktes". Mehr als eine Umformulierung der Überschrift kann dabei nicht
  herauskommen: „Der Ausschuss berät über die Verlängerung des
  Liquiditätskreditvertrages."
* ``agenda_item_impact.reason`` kennt die Vorlage — aber nur 900 Zeichen
  davon, und er begründet eine **Rangfolge**. Deshalb wertet er von Natur
  aus: „Trägt ein hohes finanzielles Risiko." Zum Sortieren ist das richtig.
  Unter einem eigenen Absender auf Instagram wird daraus die Meinung des
  Absenders zur Sache (Tims Befund 30.08.26).

Dieses Modul bekommt beides, was den anderen fehlt: **die ganze Vorlage und
die Anlagen**. Genau dort stehen die Sätze, die eine Karte tragen — dass von
8,6 Hektar nördlich Eßkamp 3,9 im Landschaftsschutzgebiet liegen, steht in
keinem Titel und in keinen 900 Zeichen.
"""
from __future__ import annotations

import json
import os

from kern import llm, prompts

from . import kritiker

from .impact import vorlagen_kern

#: Tims Vorgabe 30.08.26. Der Kontext ist der Grund: Eine Vorlage samt
#: Anlagen bringt 40.000 bis 60.000 Zeichen mit, und gpt-4o-mini fand darin
#: Angaben nicht wieder, die wörtlich dastanden — beim Kritiker gemessen,
#: 8 Fehlalarme auf 22 Texte. Luna hat 1,05 Mio Zeichen Kontext.
MODEL = os.environ.get("COUNCIL_SOCIAL_MODEL", "openai/gpt-5.6-luna")

#: Zeichenbudgets. Großzügig, aber nicht grenzenlos (Tims Vorgabe 30.08.26:
#: „so viel Kontext wie möglich").
#:
#: Die Grenze ist keine Sparmaßnahme, sondern eine Qualitätsfrage: Der
#: „Materialband Lupenpläne" einer einzigen Vorlage dieser Woche hat 400.000
#: Zeichen und besteht aus Karten. Als OCR-Text ist er Rauschen, das die
#: echten Argumente aus dem Fenster drängt. ``store.anlagen_fuer`` sortiert
#: deshalb Anträge zuerst und danach nach Länge — der Antrag einer Fraktion
#: hat 3.000 Zeichen und sagt, was jemand will.
VORLAGE_ZEICHEN = 40_000
ANLAGEN_ZEICHEN = 40_000
ANLAGE_EINZELN = 12_000
#: Was die Karte trägt. Der Satz wird gesetzt, nicht gescrollt.
MAX_ZEICHEN = 240

#: Ab welchem Anteil der Grenze ein abgeschnittener Satz noch als Text taugt.
#: Endet der letzte ganze Satz schon nach 40 Zeichen, ist der Rest die
#: eigentliche Aussage — dann lieber am Wort trennen und das mit „…" zeigen.
_SATZ_MINDEST = 0.6


def kuerzen(text: str, grenze: int = MAX_ZEICHEN) -> str:
    """Auf die Grenze kürzen, ohne ein Wort zu zerschneiden.

    ``text[:240]`` allein endete mitten im Wort: „Die Kosten können drei- bis
    viermal höher liegen als nach der Baumschutzsatzun" (Kompensations-Punkt
    des Rats vom 31.08.26). Auf einer Karte fiel das nicht auf, weil der Text
    dort ohnehin gesetzt wird — in der Tagesordnung und in der Mail steht es
    jetzt so da.

    Erst der letzte ganze Satz; taugt der nichts mehr, die letzte ganze
    Wortgrenze mit „…". Abkürzungen beenden keinen Satz: „ca.", „z. B.",
    „Nr." und alles, was auf einen einzelnen Buchstaben folgt.
    """
    text = text.strip()
    if len(text) <= grenze:
        return text
    schnitt = text[:grenze]
    ende = max(schnitt.rfind(z) for z in (". ", "! ", "? "))
    if ende > 0 and not _ist_abkuerzung(schnitt[:ende + 1]) \
            and ende + 1 >= grenze * _SATZ_MINDEST:
        return schnitt[:ende + 1].strip()
    wort = schnitt.rfind(" ")
    return (schnitt[:wort] if wort > 0 else schnitt).rstrip(" ,;:-–") + " …"


#: Was auf einen Punkt folgen kann, ohne dass ein Satz zu Ende ist. Erhoben an
#: den Kartentexten, nicht geraten — „ca." stand im Weg, seit die Karten
#: Beträge nennen.
_ABKUERZUNGEN = ("ca.", "z. B.", "u. a.", "d. h.", "Nr.", "Abs.", "Art.",
                 "Mio.", "Mrd.", "Tsd.", "evtl.", "inkl.", "bzw.", "ggf.")


def _ist_abkuerzung(bis_punkt: str) -> bool:
    """Endet ``bis_punkt`` auf einer Abkürzung statt auf einem Satzende?"""
    if any(bis_punkt.endswith(a) for a in _ABKUERZUNGEN):
        return True
    # „… 3. " — eine Ziffer oder ein einzelner Buchstabe vor dem Punkt ist
    # eine Gliederung oder Initiale, kein Satzende.
    return len(bis_punkt) >= 2 and bis_punkt[-2].isalnum() and (
        len(bis_punkt) == 2 or not bis_punkt[-3].isalnum())


def kontext(punkt: dict, anlagen: list[dict]) -> tuple[str, str]:
    """(Text fürs Modell, Herkunftsmarke) — alles, was über den Punkt vorliegt.

    Die Marke wandert in ``agenda_item_social.quelle`` und beantwortet
    später die Frage, warum ein Text dünn ist: „titel" heißt, es gab nichts
    außer der Überschrift.
    """
    teile = [f"Gremium: {punkt['committee']} am {punkt['session_date']}",
             f"Tagesordnungspunkt: {punkt['title']}"]
    if punkt.get("art"):
        teile.append(f"Art der Vorlage: {punkt['art']}")
    if punkt.get("office"):
        teile.append(f"Federführung: {punkt['office']}")
    if punkt.get("proposed_decision"):
        teile.append("Beschlussvorschlag (ein VORSCHLAG, noch kein Beschluss): "
                     + _eine_zeile(punkt["proposed_decision"])[:4000])
    if punkt.get("financial_impact"):
        teile.append("Kosten laut Vorlage: " + _eine_zeile(punkt["financial_impact"])[:2000])
    if punkt.get("climate_impact"):
        teile.append("Klimawirkung laut Vorlage: "
                     + _eine_zeile(punkt["climate_impact"])[:1200])

    kern = vorlagen_kern(punkt.get("raw_text"))
    if kern:
        teile.append(f"Vorlagentext: {kern[:VORLAGE_ZEICHEN]}")

    budget = ANLAGEN_ZEICHEN
    genutzt = 0
    for a in anlagen:
        if budget <= 0:
            break
        text = _eine_zeile(a.get("raw_text"))[:min(ANLAGE_EINZELN, budget)]
        if not text:
            continue
        mark = "Antrag" if a.get("is_motion") else "Anlage"
        wer = f" von {a['applicants']}" if a.get("applicants") else ""
        teile.append(f"{mark}{wer} – {a.get('label') or 'ohne Titel'}: {text}")
        budget -= len(text)
        genutzt += 1

    quelle = "titel"
    if kern or punkt.get("proposed_decision"):
        quelle = "vorlage+anlagen" if genutzt else "vorlage"
    return "\n\n".join(teile), quelle


def _eine_zeile(roh: str | None) -> str:
    return " ".join((roh or "").split())


def text_fuer(punkt: dict, anlagen: list[dict]) -> tuple[str, str] | None:
    """(Kartentext, Herkunft) für einen Punkt — oder None, wenn das Modell
    nichts Brauchbares liefert.

    None ist kein Fehler, sondern ein gültiges Ergebnis: Der Bot fällt dann
    auf die Kurzfassung zurück. Lieber keine Zeile als eine erfundene.
    """
    ktx, quelle = kontext(punkt, anlagen)
    system = prompts.get("social_kartentext_system")
    user = prompts.render("social_kartentext_user", kontext=ktx)

    # Zwei Versuche, und beide müssen am Kritiker vorbei. Ein zweiter Anlauf
    # lohnt, weil dasselbe Modell denselben Punkt beim nächsten Mal oft
    # sauber schreibt — die Fehler sind Streuung, kein Unvermögen: Beim
    # Windenergie-Punkt kamen an einem Nachmittag „91,84 Hektar" (richtig),
    # „69/89 Hektar" (Ziele statt Ausweisung) und „94 Hektar" (frei
    # erfunden) heraus.
    for _versuch in range(2):
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=400,
            _feature="social_kartentext",
        )
        roh = (resp.choices[0].message.content or "").strip()
        if roh.startswith("```"):
            roh = roh.strip("`")
            roh = roh[roh.find("{"):]
        try:
            text = _eine_zeile(json.loads(roh).get("text"))
        except (json.JSONDecodeError, AttributeError):
            continue
        if not text:
            continue
        text = kuerzen(text)

        maengel = kritiker.pruefe(text, ktx)
        if maengel:
            print(f"  verworfen ({punkt.get('item_number')}): {'; '.join(maengel)}")
            continue
        gedeckt, reason = kritiker.pruefe_llm(text, ktx)
        if not gedeckt:
            print(f"  verworfen ({punkt.get('item_number')}): nicht gedeckt — {reason}")
            continue
        return text, quelle
    return None


#: Wie viele Punkte einer Sitzung höchstens auf einen Rutsch geschrieben
#: werden, wenn die Tagesordnungs-Mail sie anfordert. Der Rest kommt im
#: nächsten Nachtlauf und steht in der Mail so lange mit der Kurzfassung da.
#: Eine Ratssitzung hat rund 30 inhaltliche Punkte; 40 lässt Luft, ohne dass
#: eine außergewöhnlich lange Tagesordnung den Cron-Lauf blockiert.
MAIL_MAX = 40


def _dringlichkeit_nachladen(punkt: dict) -> None:
    """Beim Dringlichkeitsantrag steht der Inhalt NUR im PDF.

    Er hat keine Vorlage — ohne diesen Griff bliebe dem Modell der Dateiname.
    Und der heißt manchmal einfach „Dringlichkeitsantrag". Best effort: Ein
    kaputtes PDF kostet den Text, nicht den Lauf.
    """
    if punkt.get("raw_text"):
        return
    from .dringlichkeit import ist_dringlichkeitsantrag  # noqa: PLC0415 — Ringschluss

    if not ist_dringlichkeitsantrag(punkt.get("item_number")):
        return
    # Der Scraper legt den Text beim Einlesen ab; hier steht nur der Rückfall
    # für Sitzungen, die vor dieser Änderung eingelesen wurden.
    if punkt.get("anlage_text"):
        punkt["raw_text"] = punkt["anlage_text"]
        return
    if not punkt.get("anlage_url"):
        return
    try:
        from .vorlagen import _pdf_text  # noqa: PLC0415 — sonst Ringschluss

        text, _seiten = _pdf_text(punkt["anlage_url"])
        punkt["raw_text"] = text
    except Exception as fehler:  # noqa: BLE001 — ein kaputtes PDF kippt keinen Lauf
        print(f"  {punkt['item_number']}: PDF nicht lesbar ({fehler})")


def _mit_anlagen(store, punkte: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Zu jedem Punkt seine Anlagen — in EINEM Rutsch, vor den Threads.

    SQLite-Verbindungen gehören einem Thread; die Aufrufe danach laufen
    parallel, die Datenbank nicht.
    """
    return [(p, store.anlagen_fuer(p["kvonr"]) if p.get("kvonr") else []) for p in punkte]


def schreibe_fehlende(store, *, limit: int | None = None, tage_voraus: int = 21,
                      mindest_wichtig: int = 0, ksinr: int | None = None,
                      workers: int = 4) -> tuple[int, int]:
    """Fehlende Kartentexte schreiben. Rückgabe: (gesucht, geschrieben).

    Zwei Aufrufer, ein Weg:

    * ``scripts/social_kartentexte.py`` — der Nachtlauf über alle kommenden
      Sitzungen.
    * ``scripts/check_committees.py`` mit ``ksinr`` — die Tagesordnungs-Mail,
      **bevor** sie ihren Text baut. Der Nachtlauf käme für sie zu spät: Die
      Mail geht raus, sobald eine Tagesordnung erscheint, und trüge sonst bis
      zum nächsten Morgen die titelbasierte Kurzfassung (Tims Auftrag
      30.08.26). Zusätzliche Kosten entstehen dadurch nicht — die Texte
      würden ohnehin geschrieben, nur später; ``agenda_item_social`` ist der
      Zwischenspeicher für beide.

    Kein Text ist ein gültiges Ergebnis (der Kritiker verwirft), dann bleibt
    es für diesen Punkt bei der Kurzfassung.
    """
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415 — nur hier

    todo = _mit_anlagen(store, store.agenda_items_needing_social_text(
        limit, tage_voraus=tage_voraus, mindest_wichtig=mindest_wichtig, ksinr=ksinr))
    for punkt, _ in todo:
        _dringlichkeit_nachladen(punkt)
    geschrieben = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for punkt, result in pool.map(lambda pa: (pa[0], text_fuer(pa[0], pa[1])), todo):
            if not result:
                continue          # kein Text ist besser als ein erfundener
            text, quelle = result
            store.save_social_text(punkt["ksinr"], punkt["item_number"], text, quelle)
            geschrieben += 1
    return len(todo), geschrieben
