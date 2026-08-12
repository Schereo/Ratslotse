"""Diff zweier Tagesordnungs-Stände für die Änderungs-Meldung (Tims Wunsch
12.08.): Statt der kompletten Liste nennt die Mail nur, was sich geändert hat
— Neues grün, Geändertes/Verschobenes gelb, Entferntes rot.

Der Vergleich läuft zuerst über den TITEL (die stabile Identität eines
Punktes): Wird ein TOP eingeschoben, verschieben sich alle Nachfolge-NUMMERN
— ein Nummern-Diff würde dann die halbe Tagesordnung gelb färben, obwohl nur
ein Punkt neu ist.
"""
from __future__ import annotations


def _norm_titel(titel: str) -> str:
    return " ".join(str(titel or "").split()).lower()


def diff_tagesordnung(alt: list[dict], neu: list[dict]) -> dict:
    """{"neu": [item], "entfernt": [item], "verschoben": [(alt, neu)],
    "umformuliert": [(alt, neu)]} — Items sind dicts mit item_number/title/
    vorlage_nr. Nur öffentliche Punkte vergleichen ist Sache des Aufrufers."""
    alt_nach_titel: dict[str, dict] = {}
    for i in alt:
        alt_nach_titel.setdefault(_norm_titel(i.get("title")), i)
    neu_nach_titel: dict[str, dict] = {}
    for i in neu:
        neu_nach_titel.setdefault(_norm_titel(i.get("title")), i)
    alt_nach_nummer = {str(i.get("item_number")): i for i in alt}

    ergebnis = {"neu": [], "entfernt": [], "verschoben": [], "umformuliert": []}
    for i in neu:
        t = _norm_titel(i.get("title"))
        vorher = alt_nach_titel.get(t)
        if vorher is not None:
            if str(vorher.get("item_number")) != str(i.get("item_number")):
                ergebnis["verschoben"].append((vorher, i))
            continue
        # Titel neu — trägt die Nummer vorher einen ANDEREN Titel, ist der
        # Punkt umformuliert worden (gleiche Stelle, neuer Wortlaut) …
        an_nummer = alt_nach_nummer.get(str(i.get("item_number")))
        if an_nummer is not None and _norm_titel(an_nummer.get("title")) not in neu_nach_titel:
            ergebnis["umformuliert"].append((an_nummer, i))
        else:  # … sonst ist er schlicht neu.
            ergebnis["neu"].append(i)
    umformuliert_alt = {_norm_titel(a.get("title")) for a, _ in ergebnis["umformuliert"]}
    for i in alt:
        t = _norm_titel(i.get("title"))
        if t not in neu_nach_titel and t not in umformuliert_alt:
            ergebnis["entfernt"].append(i)
    return ergebnis


def hat_aenderungen(diff: dict) -> bool:
    return any(diff[k] for k in ("neu", "entfernt", "verschoben", "umformuliert"))


def _esc(text: str) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _zeile(farbe: str, inhalt: str, durchgestrichen: bool = False) -> str:
    deko = "text-decoration:line-through;" if durchgestrichen else ""
    return (f"<li style='margin:0 0 8px;padding:0 0 0 10px;border-left:3px solid {farbe};"
            f"list-style:none'><span style='{deko}'>{inhalt}</span></li>")


def diff_html(diff: dict) -> str:
    """Die Unterschiede als kompakte, farbmarkierte Liste (E-Mail-tauglich:
    Inline-Styles, Farbbalken statt Hintergrund — übersteht Dark-Mode-Mails)."""
    GRUEN, GELB, ROT = "#2f9e44", "#e8a303", "#d64545"
    zeilen: list[str] = []
    for i in diff["neu"]:
        zeilen.append(_zeile(GRUEN, f"<b>Neu · TOP {_esc(i.get('item_number'))}</b> — {_esc(i.get('title'))}"))
    for a, n in diff["umformuliert"]:
        zeilen.append(_zeile(GELB, f"<b>Geändert · TOP {_esc(n.get('item_number'))}</b> — {_esc(n.get('title'))}"
                                   f"<br><span style='color:#8a8f98;font-size:13px'>vorher: {_esc(a.get('title'))}</span>"))
    for a, n in diff["verschoben"]:
        zeilen.append(_zeile(GELB, f"<b>Verschoben · TOP {_esc(a.get('item_number'))} → {_esc(n.get('item_number'))}</b>"
                                   f" — {_esc(n.get('title'))}"))
    for i in diff["entfernt"]:
        zeilen.append(_zeile(ROT, f"<b>Entfernt · TOP {_esc(i.get('item_number'))}</b> — {_esc(i.get('title'))}",
                             durchgestrichen=True))
    if not zeilen:
        return ""
    return f"<ul style='margin:14px 0 0;padding:0;font-size:15px;line-height:1.5'>{''.join(zeilen)}</ul>"
