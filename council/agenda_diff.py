"""Diff zweier Tagesordnungs-Stände für die Änderungs-Meldung (Tims Wunsch
12.08.): Statt der kompletten Liste nennt die Mail nur, was sich geändert hat
— Neues grün, Geändertes/Verschobenes gelb, Entferntes rot.

Der Vergleich läuft zuerst über den TITEL (die stabile Identität eines
Punktes): Wird ein TOP eingeschoben, verschieben sich alle Nachfolge-NUMMERN
— ein Nummern-Diff würde dann die halbe Tagesordnung gelb färben, obwohl nur
ein Punkt neu ist.

Was der Titel-Vergleich nicht verhindern kann: Die Nachfolge-Punkte tragen
danach trotzdem neue Nummern und werden reihenweise als „verschoben" gemeldet.
Solche Kaskaden faltet ``verschiebungs_kaskaden`` in eine Zeile zusammen
(Tims Befund 26.08.) — sie sind die harmloseste Änderung überhaupt und
verdrängten in Liste und Mail die Punkte, auf die es ankommt.
"""
from __future__ import annotations

import re


def _norm_titel(title: str) -> str:
    return " ".join(str(title or "").split()).lower()


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
    mit item_number/title/template_number (optional is_public). Welche Punkte
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

    result = {"neu": [], "entfernt": [], "verschoben": [], "umformuliert": [],
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
            result["verschoben"].append((vorher, i))
        elif _norm_vorlage(vorher.get("template_number")) != _norm_vorlage(i.get("template_number")):
            # Der häufigste stille Fall: Ein TOP steht ohne Vorlage auf der
            # Liste, die Verwaltung reicht sie nach. Nummer und Titel
            # bleiben, der Tagesordnungs-Hash ändert sich trotzdem — und
            # die Änderungsmeldung hatte dazu bis hierher kein Wort
            # (Tims Befund 17.08.).
            result["vorlage"].append((vorher, i))
        elif ("anlagen" in vorher and "anlagen" in i
              and anlagen_schluessel(vorher.get("anlagen"))
              != anlagen_schluessel(i.get("anlagen"))):
            # Anhänge kamen dazu oder verschwanden (Tims Wunsch 18.08.) —
            # nur wenn BEIDE Stände die Anlagen kennen; alte Snapshots
            # ohne das Feld sollen keine erfundenen Neuzugänge melden.
            # Nach der Vorlage geprüft: Eine nachgereichte Vorlage hängt
            # ihr PDF oft auch als Anlage an — das wäre sonst doppelt.
            result["anlagen"].append((vorher, i))

    for i in rest:
        # Titel neu — trägt die Nummer vorher einen ANDEREN Titel, ist der
        # Punkt umformuliert worden (gleiche Stelle, neuer Wortlaut) …
        an_nummer = alt_nach_nummer.get(str(i.get("item_number")))
        if (an_nummer is not None and id(an_nummer) not in benutzt
                and _norm_titel(an_nummer.get("title")) not in neu_nach_titel):
            benutzt.add(id(an_nummer))
            result["umformuliert"].append((an_nummer, i))
        else:  # … sonst ist er schlicht neu.
            result["neu"].append(i)
    # Entfernt ist, was keinen Partner gefunden hat — auch der überzählige
    # Namensvetter, den die Titel-Sicht früher übersah.
    result["entfernt"] = [i for i in alt if id(i) not in benutzt]
    return result


def hat_aenderungen(diff: dict) -> bool:
    return any(diff.get(k) for k in
               ("neu", "entfernt", "verschoben", "umformuliert", "vorlage", "anlagen"))


_TOP_NUMMER = re.compile(r"^\s*(\D*?)\s*(\d+(?:\.\d+)*)\s*$")


def _nummer_teile(nr) -> tuple[str, tuple[int, ...]] | None:
    """„Ö 33.1" → ("Ö", (33, 1)). None, wenn die Nummer nicht diesem Muster
    folgt — dann wird der Punkt nie gebündelt, sondern einzeln gemeldet."""
    m = _TOP_NUMMER.match(str(nr or ""))
    if not m:
        return None
    return m.group(1), tuple(int(t) for t in m.group(2).split("."))


def _kaskaden_schluessel(a: dict, n: dict):
    """Gehört dieses Paar zu einer Kaskade? Dann (Präfix, Versatz) — sonst
    None. Bedingung: gleicher Präfix (Ö bleibt Ö, N bleibt N), gleiche
    Untergliederung (33.1 → 32.1 zählt mit, 33.1 → 32.2 nicht) und ein
    Versatz auf der obersten Ebene."""
    ta, tn = _nummer_teile(a.get("item_number")), _nummer_teile(n.get("item_number"))
    if ta is None or tn is None:
        return None
    if ta[0] != tn[0] or ta[1][1:] != tn[1][1:] or ta[1][0] == tn[1][0]:
        return None
    return ta[0], tn[1][0] - ta[1][0]


def _alt_sortierung(paar) -> tuple[int, ...]:
    teile = _nummer_teile(paar[0].get("item_number"))
    return teile[1] if teile else ()


def _dicht(mitglieder: list) -> bool:
    """Deckt die Gruppe ihre Spanne wirklich ab? Drei Punkte mit demselben
    Versatz, aber über die halbe Tagesordnung verstreut (Ö 5, Ö 9, Ö 20),
    sind keine Kaskade — „TOP Ö 5 bis Ö 20 rücken eine Nummer" würde die
    unbeteiligten Punkte dazwischen mitbehaupten. Ein einzelnes Loch (etwa
    weil ein mitgerutschter Punkt zugleich umformuliert wurde und deshalb
    anderswo gemeldet wird) darf die Bündelung dagegen nicht kippen."""
    ebenen = {_alt_sortierung(m)[0] for m in mitglieder if _alt_sortierung(m)}
    if not ebenen:
        return False
    spanne = max(ebenen) - min(ebenen) + 1
    return len(ebenen) * 2 >= spanne


def verschiebungs_kaskaden(paare: list, mindestens: int = 3) -> tuple[list, list]:
    """Zerlegt die Verschiebungen in Kaskaden und Einzelfälle (Tims Befund
    26.08.): Wird oben ein Punkt eingeschoben oder gestrichen, rutscht der
    ganze Rest um dieselbe Zahl — vierzehn Zeilen „Verschoben · Ö 22 → Ö 21",
    die zusammen genau eine Aussage tragen. Erst ab ``mindestens`` Punkten
    mit demselben Versatz lohnt die Bündelung; zwei Zeilen sagen einzeln mehr.

    Rückgabe: ``([(versatz, [(alt, neu), …]), …], [(alt, neu), …])`` — die
    Kaskaden nach ihrer ersten alten Nummer sortiert, die Einzelfälle in der
    Reihenfolge der Tagesordnung."""
    gruppen: dict[tuple[str, int], list] = {}
    for paar in paare:
        a, n = paar[0], paar[1]
        key = _kaskaden_schluessel(a, n)
        if key is not None:
            gruppen.setdefault(key, []).append(paar)
    kaskaden = [(key[1], sorted(mitglieder, key=_alt_sortierung))
                for key, mitglieder in gruppen.items()
                if len(mitglieder) >= mindestens and _dicht(mitglieder)]
    kaskaden.sort(key=lambda k: _alt_sortierung(k[1][0]))
    gebunden = {id(paar) for _, mitglieder in kaskaden for paar in mitglieder}
    einzeln = [paar for paar in paare if id(paar) not in gebunden]
    return kaskaden, einzeln


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
    # Nachrücken und Verschieben getrennt zählen: „14 Punkte wurden verschoben"
    # klang in der Push-Vorschau nach Umbau der halben Sitzung, obwohl nur oben
    # ein Punkt wegfiel (Tims Befund 26.08.).
    kaskaden, einzeln = verschiebungs_kaskaden(diff.get("verschoben", []))
    if n := sum(len(m) for _, m in kaskaden):
        teile.append(_zaehl(n, "ein Punkt hat eine neue Nummer",
                            "{n} Punkte haben eine neue Nummer"))
    if n := len(einzeln):
        teile.append(_zaehl(n, "ein Punkt wurde verschoben", "{n} Punkte wurden verschoben"))
    nach = zurueck = anders = 0
    for a, m in diff.get("vorlage", []):
        alt_nr, neu_nr = _norm_vorlage(a.get("template_number")), _norm_vorlage(m.get("template_number"))
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
    alt_nr, neu_nr = _norm_vorlage(a.get("template_number")), _norm_vorlage(n.get("template_number"))
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


def nur_nummern_versatz(diff: dict) -> bool:
    """Besteht diese Änderung ausschließlich aus einer Nummern-Kaskade? Dann
    ist buchstäblich nichts passiert: dieselben Punkte, dieselbe Reihenfolge,
    nur eine Nummer weiter oben oder unten. Dafür will niemand eine Mail
    (Tims Entscheidung 26.08.) — auf der Sitzungsseite steht es weiterhin
    unter „Zuletzt geändert".

    Bewusst NICHT stillgelegt wird die echte Umsortierung: Wandert ein Punkt
    an eine andere Stelle, ändert sich die Reihenfolge — und wer wegen genau
    dieses Punktes kommt, muss wissen, dass er früher dran ist. Genau daran
    verläuft die Grenze zwischen Kaskade und Einzelfall."""
    if any(diff.get(k) for k in ("neu", "entfernt", "umformuliert", "vorlage", "anlagen")):
        return False
    kaskaden, einzeln = verschiebungs_kaskaden(diff.get("verschoben", []))
    if not kaskaden or einzeln:
        return False
    # Und jetzt die Falle, an der diese Regel sonst Schaden anrichtet:
    # diff_tagesordnung prüft in einer if/elif-Kette, „verschoben" schlägt
    # „vorlage" und „anlagen". Ein mitgerutschter Punkt, der ZUGLEICH seine
    # Vorlage nachgereicht bekommt, steht deshalb nur als Verschiebung in der
    # Liste — für die Anzeige verschmerzbar (eine Zeile gibt es), beim
    # Stilllegen aber fatal: die Vorlage verschwände spurlos. Darum hier noch
    # einmal von Hand nachsehen.
    for paar in (paar for _, mitglieder in kaskaden for paar in mitglieder):
        a, n = paar[0], paar[1]
        if _norm_vorlage(a.get("template_number")) != _norm_vorlage(n.get("template_number")):
            return False
        if ("anlagen" in a and "anlagen" in n
                and anlagen_schluessel(a.get("anlagen")) != anlagen_schluessel(n.get("anlagen"))):
            return False
    return True


def _kaskaden_zeile(versatz: int, mitglieder: list) -> dict:
    """Eine Kaskade als einzelne Zeile — mit dem Satz, der sie harmlos macht:
    Die Punkte selbst bleiben, nur ihre Nummern rutschen."""
    von_a = mitglieder[0][0].get("item_number")
    bis_a = mitglieder[-1][0].get("item_number")
    von_n = mitglieder[0][1].get("item_number")
    bis_n = mitglieder[-1][1].get("item_number")
    stufen = "eine Nummer" if abs(versatz) == 1 else f"{abs(versatz)} Nummern"
    richtung = "nach vorn" if versatz < 0 else "nach hinten"
    return {
        "art": "verschoben",
        "label": f"Verschoben · TOP {von_a} bis {bis_a}",
        "title": (f"{len(mitglieder)} Punkte rücken {stufen} {richtung} — "
                  f"jetzt TOP {von_n} bis {bis_n}"),
        "nichtoeffentlich": all(not m[1].get("is_public", True) for m in mitglieder),
        "detail": "Untereinander bleibt die Reihenfolge gleich",
    }


def diff_zeilen(diff: dict) -> list[dict]:
    """Der Diff als neutrale Zeilen — EINE Quelle für Mail-HTML und die
    App-Ansicht „Zuletzt geändert" (Tims Wunsch 18.08.). Je Zeile:
    ``art`` (neu|geaendert|verschoben|vorlage|anlagen|entfernt), ``label``
    (der fette Kopf inkl. TOP-Nummer), ``title``, ``nichtoeffentlich`` und
    ``detail`` (leise Zusatzzeile oder None). Alles unescaped — wer HTML
    baut, escapet selbst."""
    zeilen: list[dict] = []

    def _z(art: str, label: str, item: dict, detail: str | None = None) -> None:
        zeilen.append({"art": art, "label": label,
                       "title": str(item.get("title") or ""),
                       "nichtoeffentlich": not item.get("is_public", True),
                       "detail": detail})

    for i in diff["neu"]:
        _z("neu", f"Neu · TOP {i.get('item_number')}", i)
    for a, n in diff["umformuliert"]:
        _z("geaendert", f"Geändert · TOP {n.get('item_number')}", n,
           f"vorher: {a.get('title')}")
    kaskaden, einzeln = verschiebungs_kaskaden(diff["verschoben"])
    for paar in einzeln:
        a, n = paar[0], paar[1]
        _z("verschoben", f"Verschoben · TOP {a.get('item_number')} → {n.get('item_number')}", n)
    for versatz, mitglieder in kaskaden:
        # Die Kaskade als EINE Zeile: Was sie zu sagen hat, steht in ihr ganz
        # — welche Spanne, um wie viel, wohin. Die Einzelzeilen wiederholten
        # vierzehnmal dasselbe und drängten die echten Änderungen aus dem Blick.
        zeilen.append(_kaskaden_zeile(versatz, mitglieder))
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
        mark = (" <span style='color:#8a8f98;font-size:13px'>(nichtöffentlich)</span>"
                 if z["nichtoeffentlich"] else "")
        inhalt = f"<b>{_esc(z['label'])}</b> — {_esc(z['title'])}{mark}"
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
