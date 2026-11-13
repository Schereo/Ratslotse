"""Spezialleser für zwei Dokumentarten, die als Fließtext nichts taugen
(docs/plan-vorlagen-aufbereiten.md § 2.4, Schritt 17). Ohne Modell.

**Prüfvermerke** im Schlussbericht des Rechnungsprüfungsamts: Am linken Rand
steht fett eine Kennung — B (Beanstandung), WB (wiederholte Beanstandung),
H (Hinweis), K (Korrektur/Klärung) — neben dem Absatz, auf den sie sich
bezieht; darüber die Textziffer als fette Überschrift („3.2.3
Software-Inventur"). Im Fließtext verschwindet die Kennung zwischen den
Zeilen. Beispiel: Schlussbericht 2025 (Vorlage 26/0674) mit 5 B, 3 WB und
10 H — vorher stand davon im Dossier nichts.

**Abwägungstabellen** einer Bauleitplanung: je Stellungnahme ein Kopf
(„Nr.: 3 · Schreiben vom … · Bürger 2"), links die Stellungnahme, rechts der
Prüfungsvorschlag der Verwaltung. Ins Dossier gehören laut Plan nur **Zahl
und Ergebnis**, nie Absender — Einwendungen nennen Privatpersonen. Der Leser
zählt deshalb nur: Stellungnahmen (Öffentlichkeit gegen Behörden und
Verbände) und die Formeln der Prüfungsvorschläge („wird gefolgt", „wird nicht
gefolgt", „wird zur Kenntnis genommen").
"""
from __future__ import annotations

import re
from typing import TypedDict

CODES = {"B": "Beanstandung", "WB": "Wiederholte Beanstandung", "H": "Hinweis", "K": "Korrektur/Klärung"}
#: Die Kennung steht am Rand, der Text beginnt weiter rechts. Die Legende auf
#: den ersten Seiten setzt sie eingerückt — die zählt nicht mit.
RAND_BIS = 66
_TZ = re.compile(r"^\d{1,2}(?:\.\d{1,2})+\.?$")


class Pruefvermerk(TypedDict):
    code: str
    label: str
    tz: str | None
    heading: str | None
    text: str
    page: int


def _zeilen(seite) -> list[tuple[float, float, float, bool, str]]:
    """(x0, y0, y1, fett, Text) je Zeile, von oben nach unten. „fett" gilt für
    den ERSTEN Teil der Zeile — die Randkennung und ihr Absatz stehen oft in
    derselben Zeile („WB ⇥ Das Rechnungsprüfungsamt beanstandet …")."""
    out = []
    for b in seite.get_text("dict")["blocks"]:
        for z in b.get("lines", []):
            spans = [s for s in z["spans"] if s["text"].strip()]
            t = " ".join(s["text"] for s in z["spans"]).strip()
            if t and spans:
                fett = "Bold" in spans[0]["font"] or bool(spans[0]["flags"] & 16)
                out.append((z["bbox"][0], z["bbox"][1], z["bbox"][3], fett, t))
    return sorted(out, key=lambda z: (round(z[1]), z[0]))


_RANDKENNUNG = re.compile(r"^(WB|B|H|K)(?:\s+(.*))?$")


def pruefvermerke(pdf_bytes: bytes) -> list[Pruefvermerk]:
    """Die Prüfvermerke eines Schlussberichts: Kennung, Textziffer, Überschrift,
    der Absatz neben der Kennung und die Seite. Leer, wenn keiner am Rand steht."""
    import pymupdf  # noqa: PLC0415 — bewusst optional (constraints.txt)

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out: list[Pruefvermerk] = []
    tz = kopf = None
    for n, seite in enumerate(doc, 1):
        zeilen = _zeilen(seite)
        for i, (x0, y0, y1, fett, t) in enumerate(zeilen):
            if fett and _TZ.match(t):
                # „3.2.3" und der Titel stehen als zwei Zeilen auf derselben Höhe.
                tz = t.rstrip(".")
                kopf = next((z[4] for z in zeilen if z is not zeilen[i] and abs(z[1] - y0) < 3 and z[0] > x0), None)
                continue
            m = _RANDKENNUNG.match(t)
            if not (fett and m and x0 < RAND_BIS):
                continue
            code = m.group(1)
            # Der Absatz: der Rest der Kennungszeile, dann die Zeilen rechts vom
            # Rand ab dieser Höhe, bis eine Lücke kommt.
            absatz, unten = ([m.group(2)] if m.group(2) else []), (y1 if m.group(2) else None)
            hoehe = (y1 - y0) or 12
            for z in zeilen:
                if z[0] < RAND_BIS or z[1] < y0 - 3:
                    continue
                if unten is not None and z[1] - unten > hoehe * 1.2:
                    break
                absatz.append(z[4])
                unten = z[2]
            text = re.sub(r"(\w)- (\w)", r"\1\2", " ".join(absatz)).replace("!", " ")
            out.append({"code": code, "label": CODES[code], "tz": tz, "heading": kopf,
                        "text": re.sub(r"\s+", " ", text).strip()[:600], "page": n})
    return out


def pruefvermerke_zusammenfassung(vermerke: list[Pruefvermerk]) -> str | None:
    """„3 Beanstandungen, 2 wiederholte Beanstandungen, 10 Hinweise"."""
    if not vermerke:
        return None
    mehrzahl = {"B": "Beanstandungen", "WB": "wiederholte Beanstandungen", "H": "Hinweise", "K": "Korrekturen/Klärungen"}
    einzahl = {"B": "Beanstandung", "WB": "wiederholte Beanstandung", "H": "Hinweis", "K": "Korrektur/Klärung"}
    teile = []
    for c in ("B", "WB", "K", "H"):
        k = sum(1 for v in vermerke if v["code"] == c)
        if k:
            teile.append(f"{k} {einzahl[c] if k == 1 else mehrzahl[c]}")
    return ", ".join(teile)


# ---- Abwägungstabelle ------------------------------------------------------

#: Jeder Tabellenkopf trägt die fette Spalte „Schreiben vom:". „Nr.:" taugt
#: nicht als Anker — im B-Plan 837 zerfällt es einmal in „N" und „r.:".
_KOPF = re.compile(r"^Schreiben\b")
_SCHREIBEN = re.compile(r"^(?:(?:E-Mail|Schreiben|Brief|Fax)(?:\s+vom)?\s*)?(?:\d{1,2}\.\d{1,2}\.\d{2,4})?\s*")
_OEFFENTLICHKEIT = re.compile(r"^(?:Bürger(?:in)?|Einwender(?:in)?|Privat\w*|Anlieger\w*|Eigentümer\w*|"
                              r"Anwohner\w*|Öffentlichkeit)\b", re.I)
_ERGEBNIS = {
    "gefolgt": re.compile(r"wird\s+(?:teilweise\s+)?gefolgt|wird\s+berücksichtigt|werden\s+berücksichtigt|"
                          r"wird\s+(?:entsprechend\s+)?(?:ergänzt|angepasst|geändert)", re.I),
    "nicht_gefolgt": re.compile(r"wird\s+nicht\s+gefolgt|nicht\s+berücksichtigt|wird\s+zurückgewiesen", re.I),
    "kenntnis": re.compile(r"zur\s+Kenntnis\s+genommen", re.I),
}


class Abwaegung(TypedDict):
    statements: int
    public: int
    institutions: int
    followed: int
    not_followed: int
    noted: int
    pages: int


def abwaegung(pdf_bytes: bytes) -> Abwaegung | None:
    """Zahl der Stellungnahmen und die Ergebnisse der Prüfungsvorschläge.
    ``None`` ohne erkennbare Tabelle (Scan, anderes Layout)."""
    import pymupdf  # noqa: PLC0415

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    n = oeff = 0
    rechts: list[str] = []
    for seite in doc:
        zeilen = _zeilen(seite)
        mitte = seite.rect.width / 2
        for i, (x0, y0, _y1, fett, t) in enumerate(zeilen):
            if fett and _KOPF.match(t) and x0 < mitte / 2:
                n += 1
                # Absender: die erste nicht fette Zeile rechts neben „Schreiben vom",
                # zwei Zeilen tiefer — nur seine Art wird gezählt, nie der Name.
                # „E-Mail vom 25.05.2026" steht mal als eigene Zeile, mal mit dem
                # Absender in einer — die Angabe zum Schreiben fällt weg.
                absender = [rest for z in zeilen[i + 1:i + 12] if not z[3] and x0 - 5 <= z[0] < mitte
                            and (rest := _SCHREIBEN.sub("", z[4]).strip())]
                if absender and _OEFFENTLICHKEIT.match(absender[0]):
                    oeff += 1
            elif x0 > mitte - 30:
                rechts.append(t)
    if not n:
        return None
    text = re.sub(r"(\w)- (\w)", r"\1\2", " ".join(rechts))
    nicht = len(_ERGEBNIS["nicht_gefolgt"].findall(text))
    return {"statements": n, "public": oeff, "institutions": n - oeff,
            "followed": len(_ERGEBNIS["gefolgt"].findall(text)),
            "not_followed": nicht, "noted": len(_ERGEBNIS["kenntnis"].findall(text)),
            "pages": doc.page_count}
