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

from kern import llm, prompts

from .impact import vorlagen_kern

MODEL = "openai/gpt-4o-mini"

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
    if punkt.get("amt"):
        teile.append(f"Federführung: {punkt['amt']}")
    if punkt.get("beschlussvorschlag"):
        teile.append("Beschlussvorschlag (ein VORSCHLAG, noch kein Beschluss): "
                     + _eine_zeile(punkt["beschlussvorschlag"])[:4000])
    if punkt.get("finanz_check"):
        teile.append("Kosten laut Vorlage: " + _eine_zeile(punkt["finanz_check"])[:2000])
    if punkt.get("klima_check"):
        teile.append("Klimawirkung laut Vorlage: "
                     + _eine_zeile(punkt["klima_check"])[:1200])

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
        marke = "Antrag" if a.get("is_antrag") else "Anlage"
        wer = f" von {a['antragsteller']}" if a.get("antragsteller") else ""
        teile.append(f"{marke}{wer} – {a.get('label') or 'ohne Titel'}: {text}")
        budget -= len(text)
        genutzt += 1

    quelle = "titel"
    if kern or punkt.get("beschlussvorschlag"):
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
        if text:
            return text[:MAX_ZEICHEN].strip(), quelle
    return None
