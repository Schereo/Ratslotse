"""Diff zweier Tagesordnungs-Stände für die Änderungs-Meldung (Tims Wunsch
12.08.): Statt der kompletten Liste nennt die Mail nur, was sich geändert hat
— Neues grün, Geändertes/Verschobenes gelb, Entferntes rot.

Der Vergleich läuft zuerst über den TITEL (die stabile Identität eines
Punktes): Wird ein TOP eingeschoben, verschieben sich alle Nachfolge-NUMMERN
— ein Nummern-Diff würde dann die halbe Tagesordnung gelb färben, obwohl nur
ein Punkt neu ist.
"""
from __future__ import annotations

import re


def _norm_titel(titel: str) -> str:
    return " ".join(str(titel or "").split()).lower()


def _norm_vorlage(nr: str) -> str:
    return " ".join(str(nr or "").split())


_GETFILE_ID = re.compile(r"getfile\.php\?id=(\d+)")


def anlagen_schluessel(anlagen: list | None) -> list[str]:
    """Stabile Identität je Anhang: die getfile-id (Icon- und Textlink einer
    Zeile teilen sie, Labels schwanken), sonst die URL. Grundlage für den
    Tagesordnungs-Hash und den Anlagen-Diff."""
    out: list[str] = []
    for e in anlagen or []:
        url = str((e or {}).get("url") or "")
        m = _GETFILE_ID.search(url)
        out.append(m.group(1) if m else url)
    return sorted(out)


def diff_tagesordnung(alt: list[dict], neu: list[dict]) -> dict:
    """{"neu": [item], "entfernt": [item], "verschoben": [(alt, neu)],
    "umformuliert": [(alt, neu)], "vorlage": [(alt, neu)]} — Items sind dicts
    mit item_number/title/vorlage_nr (optional is_public). Welche Punkte
    verglichen werden, entscheidet der Aufrufer."""
    # Titel sind NICHT eindeutig: Nichtöffentliche Teile führen reihenweise
    # TOPs namens „gesperrte Information". Ein Titel→Punkt-dict ließ alle
    # Namensvettern am ERSTEN andocken — jede Änderungsmeldung einer solchen
    # Sitzung trug Phantom-Zeilen „Verschoben · N 11 → N 12" (aufgefallen an
    # der Demo-Mail vom 18.08.). Deshalb Kandidaten-LISTEN: erst binden sich
    # die nummerntreuen Paare, dann die übrigen der Reihe nach.
    alt_nach_titel: dict[str, list[dict]] = {}
    for i in alt:
        alt_nach_titel.setdefault(_norm_titel(i.get("title")), []).append(i)
    neu_nach_titel: dict[str, list[dict]] = {}
    for i in neu:
        neu_nach_titel.setdefault(_norm_titel(i.get("title")), []).append(i)
    alt_nach_nummer = {str(i.get("item_number")): i for i in alt}

    ergebnis = {"neu": [], "entfernt": [], "verschoben": [], "umformuliert": [],
                "vorlage": [], "anlagen": []}
    benutzt: set[int] = set()   # id() der verbrauchten Alt-Zeilen
    paare: list[tuple[dict, dict]] = []
    offen: list[dict] = []
    for i in neu:
        kandidaten = alt_nach_titel.get(_norm_titel(i.get("title")), [])
        treffer = next((k for k in kandidaten if id(k) not in benutzt
                        and str(k.get("item_number")) == str(i.get("item_number"))), None)
        if treffer is None:
            offen.append(i)
        else:
            benutzt.add(id(treffer))
            paare.append((treffer, i))
    rest: list[dict] = []
    for i in offen:
        kandidaten = [k for k in alt_nach_titel.get(_norm_titel(i.get("title")), [])
                      if id(k) not in benutzt]
        if kandidaten:
            benutzt.add(id(kandidaten[0]))
            paare.append((kandidaten[0], i))
        else:
            rest.append(i)

    for vorher, i in paare:
        if str(vorher.get("item_number")) != str(i.get("item_number")):
            ergebnis["verschoben"].append((vorher, i))
        elif _norm_vorlage(vorher.get("vorlage_nr")) != _norm_vorlage(i.get("vorlage_nr")):
            # Der häufigste stille Fall: Ein TOP steht ohne Vorlage auf der
            # Liste, die Verwaltung reicht sie nach. Nummer und Titel
            # bleiben, der Tagesordnungs-Hash ändert sich trotzdem — und
            # die Änderungsmeldung hatte dazu bis hierher kein Wort
            # (Tims Befund 17.08.).
            ergebnis["vorlage"].append((vorher, i))
        elif ("anlagen" in vorher and "anlagen" in i
              and anlagen_schluessel(vorher.get("anlagen"))
              != anlagen_schluessel(i.get("anlagen"))):
            # Anhänge kamen dazu oder verschwanden (Tims Wunsch 18.08.) —
            # nur wenn BEIDE Stände die Anlagen kennen; alte Snapshots
            # ohne das Feld sollen keine erfundenen Neuzugänge melden.
            # Nach der Vorlage geprüft: Eine nachgereichte Vorlage hängt
            # ihr PDF oft auch als Anlage an — das wäre sonst doppelt.
            ergebnis["anlagen"].append((vorher, i))

    for i in rest:
        # Titel neu — trägt die Nummer vorher einen ANDEREN Titel, ist der
        # Punkt umformuliert worden (gleiche Stelle, neuer Wortlaut) …
        an_nummer = alt_nach_nummer.get(str(i.get("item_number")))
        if (an_nummer is not None and id(an_nummer) not in benutzt
                and _norm_titel(an_nummer.get("title")) not in neu_nach_titel):
            benutzt.add(id(an_nummer))
            ergebnis["umformuliert"].append((an_nummer, i))
        else:  # … sonst ist er schlicht neu.
            ergebnis["neu"].append(i)
    # Entfernt ist, was keinen Partner gefunden hat — auch der überzählige
    # Namensvetter, den die Titel-Sicht früher übersah.
    ergebnis["entfernt"] = [i for i in alt if id(i) not in benutzt]
    return ergebnis


def hat_aenderungen(diff: dict) -> bool:
    return any(diff.get(k) for k in
               ("neu", "entfernt", "verschoben", "umformuliert", "vorlage", "anlagen"))


def _zaehl(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural.format(n=n)


def diff_satz(diff: dict) -> str:
    """Die Art der Änderung als ein Satz für die erste Zeile der Mail (Tims
    Wunsch 18.08.): „Was ist passiert?" soll beantwortet sein, bevor die
    Einzelliste kommt — gerade in der Push-Vorschau sieht man oft nur sie."""
    teile: list[str] = []
    if n := len(diff.get("neu", [])):
        teile.append(_zaehl(n, "ein Punkt ist neu", "{n} Punkte sind neu"))
    if n := len(diff.get("umformuliert", [])):
        teile.append(_zaehl(n, "ein Punkt wurde umformuliert", "{n} Punkte wurden umformuliert"))
    if n := len(diff.get("verschoben", [])):
        teile.append(_zaehl(n, "ein Punkt wurde verschoben", "{n} Punkte wurden verschoben"))
    nach = zurueck = anders = 0
    for a, m in diff.get("vorlage", []):
        alt_nr, neu_nr = _norm_vorlage(a.get("vorlage_nr")), _norm_vorlage(m.get("vorlage_nr"))
        if neu_nr and not alt_nr:
            nach += 1
        elif alt_nr and not neu_nr:
            zurueck += 1
        else:
            anders += 1
    if nach:
        teile.append(_zaehl(nach, "eine Vorlage wurde nachgereicht",
                            "{n} Vorlagen wurden nachgereicht"))
    if zurueck:
        teile.append(_zaehl(zurueck, "eine Vorlage wurde zurückgezogen",
                            "{n} Vorlagen wurden zurückgezogen"))
    if anders:
        teile.append(_zaehl(anders, "eine Vorlage wurde ersetzt",
                            "{n} Vorlagen wurden ersetzt"))
    if n := len(diff.get("anlagen", [])):
        teile.append(_zaehl(n, "die Anlagen zu einem Punkt haben sich geändert",
                            "die Anlagen zu {n} Punkten haben sich geändert"))
    if n := len(diff.get("entfernt", [])):
        teile.append(_zaehl(n, "ein Punkt wurde von der Tagesordnung genommen",
                            "{n} Punkte wurden von der Tagesordnung genommen"))
    if not teile:
        return ""
    satz = (", ".join(teile[:-1]) + " und " + teile[-1]) if len(teile) > 1 else teile[0]
    return satz[0].upper() + satz[1:] + "."


def _esc(text: str) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _zeile(farbe: str, inhalt: str, durchgestrichen: bool = False) -> str:
    deko = "text-decoration:line-through;" if durchgestrichen else ""
    return (f"<li style='margin:0 0 8px;padding:0 0 0 10px;border-left:3px solid {farbe};"
            f"list-style:none'><span style='{deko}'>{inhalt}</span></li>")


def _leise(text: str) -> str:
    return f"<br><span style='color:#8a8f98;font-size:13px'>{text}</span>"


def _vorlage_daten(a: dict, n: dict) -> tuple[str, str]:
    alt_nr, neu_nr = _norm_vorlage(a.get("vorlage_nr")), _norm_vorlage(n.get("vorlage_nr"))
    if neu_nr and not alt_nr:
        return "Vorlage nachgereicht", f"Vorlage {neu_nr} liegt jetzt vor"
    if alt_nr and not neu_nr:
        return "Vorlage zurückgezogen", f"vorher: Vorlage {alt_nr}"
    return "Andere Vorlage", f"{alt_nr} → {neu_nr}"


def _anlagen_daten(a: dict, n: dict) -> tuple[str, str]:
    """Dazugekommene und verschwundene Anhänge eines TOP, mit Labels — die
    getfile-id ist die Identität, Label-Wechsel allein sind keine Meldung."""
    def _nach_id(item: dict) -> dict[str, str]:
        out: dict[str, str] = {}
        for e in item.get("anlagen") or []:
            url = str((e or {}).get("url") or "")
            m = _GETFILE_ID.search(url)
            out[m.group(1) if m else url] = str((e or {}).get("label") or "Anlage")
        return out

    alt_m, neu_m = _nach_id(a), _nach_id(n)
    dazu = [neu_m[k] for k in neu_m if k not in alt_m]
    weg = [alt_m[k] for k in alt_m if k not in neu_m]

    def _liste(labels: list[str]) -> str:
        rest = len(labels) - 3
        return (", ".join(labels[:3]) + (f" und {rest} weitere" if rest > 0 else ""))

    if dazu and not weg:
        return ("Neue Anlage" if len(dazu) == 1 else "Neue Anlagen"), _liste(dazu)
    if weg and not dazu:
        return (("Anlage entfernt" if len(weg) == 1 else "Anlagen entfernt"),
                f"entfernt: {_liste(weg)}")
    return "Anlagen geändert", f"neu: {_liste(dazu)} · entfernt: {_liste(weg)}"


def diff_zeilen(diff: dict) -> list[dict]:
    """Der Diff als neutrale Zeilen — EINE Quelle für Mail-HTML und die
    App-Ansicht „Zuletzt geändert" (Tims Wunsch 18.08.). Je Zeile:
    ``art`` (neu|geaendert|verschoben|vorlage|anlagen|entfernt), ``label``
    (der fette Kopf inkl. TOP-Nummer), ``titel``, ``nichtoeffentlich`` und
    ``detail`` (leise Zusatzzeile oder None). Alles unescaped — wer HTML
    baut, escapet selbst."""
    zeilen: list[dict] = []

    def _z(art: str, label: str, item: dict, detail: str | None = None) -> None:
        zeilen.append({"art": art, "label": label,
                       "titel": str(item.get("title") or ""),
                       "nichtoeffentlich": not item.get("is_public", True),
                       "detail": detail})

    for i in diff["neu"]:
        _z("neu", f"Neu · TOP {i.get('item_number')}", i)
    for a, n in diff["umformuliert"]:
        _z("geaendert", f"Geändert · TOP {n.get('item_number')}", n,
           f"vorher: {a.get('title')}")
    for a, n in diff["verschoben"]:
        _z("verschoben", f"Verschoben · TOP {a.get('item_number')} → {n.get('item_number')}", n)
    for a, n in diff.get("vorlage", []):
        label, detail = _vorlage_daten(a, n)
        _z("vorlage", f"{label} · TOP {n.get('item_number')}", n, detail)
    for a, n in diff.get("anlagen", []):
        label, detail = _anlagen_daten(a, n)
        _z("anlagen", f"{label} · TOP {n.get('item_number')}", n, detail)
    for i in diff["entfernt"]:
        _z("entfernt", f"Entfernt · TOP {i.get('item_number')}", i)
    return zeilen


def diff_html(diff: dict) -> str:
    """Die Unterschiede als kompakte, farbmarkierte Liste (E-Mail-tauglich:
    Inline-Styles, Farbbalken statt Hintergrund — übersteht Dark-Mode-Mails),
    darüber die Änderungsart in einem Satz."""
    GRUEN, GELB, ROT = "#2f9e44", "#e8a303", "#d64545"
    farben = {"neu": GRUEN, "geaendert": GELB, "verschoben": GELB,
              "vorlage": GELB, "anlagen": GELB, "entfernt": ROT}
    zeilen: list[str] = []
    for z in diff_zeilen(diff):
        marke = (" <span style='color:#8a8f98;font-size:13px'>(nichtöffentlich)</span>"
                 if z["nichtoeffentlich"] else "")
        inhalt = f"<b>{_esc(z['label'])}</b> — {_esc(z['titel'])}{marke}"
        if z["detail"]:
            inhalt += _leise(_esc(z["detail"]))
        zeilen.append(_zeile(farben[z["art"]], inhalt,
                             durchgestrichen=z["art"] == "entfernt"))
    if not zeilen:
        return ""
    satz = diff_satz(diff)
    intro = f"<p style='margin:12px 0 0'>{_esc(satz)}</p>" if satz else ""
    return (intro
            + f"<ul style='margin:14px 0 0;padding:0;font-size:15px;line-height:1.5'>{''.join(zeilen)}</ul>")
