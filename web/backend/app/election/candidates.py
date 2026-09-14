"""Alle Kandidaturen einer Ratswahl als eine Rangliste — ``/api/wahlabend/kandidaten``.

Anlass (Tim, 14.09.2026, Abend nach der Ratswahl): „Ich bin schon irritiert,
wie manche von der AfD so viele Direkt-Kandidatinnen-Stimmen bekommen
konnten. Generell fände ich eine Liste aller Kandidat*innen mit Angabe
persönliche Stimmen und auch nach Partei sortierbar interessant."

Die Wahlabend-Seite kennt die Personenstimmen längst — aber nur je Liste und
Wahlbereich, sechs Karten tief. Die Frage „wer hat stadtweit die meisten
Personenstimmen?" ließ sich damit nicht beantworten, ohne 16 Listen
durchzuklicken. Hier steht dieselbe Menge als EINE Liste, mit zwei Zahlen,
die die Frage nach dem „wie" beantworten:

- ``party_share_pct`` je Person: ihr Anteil an allen Stimmen ihrer Liste im
  Wahlbereich. Wer 22 % der Stimmen seiner Liste auf sich zieht, hat sie
  getragen — egal wie viele Stimmen das absolut sind.
- ``personal_pct`` je Liste, stadtweit: wie viel von dem, was die Liste
  bekam, an Personen ging statt an die Liste. Gemessen 2026: SPD 50 %, CDU
  48 %, Grüne 35 %, AfD 36 % — die AfD-Wähler*innen stimmen also NICHT
  auffällig personenbezogen; ihre Spitzenwerte kommen daher, dass sich die
  Personenstimmen auf sehr wenige Namen konzentrieren.

Sortieren und Filtern passiert HIER, nicht im Browser (Tims Regel: Logik ins
Backend — Web und App zeigen dieselbe Liste). Die Rangnummer ist stadtweit
und bleibt es auch gefiltert: Platz 7 der Stadt ist Platz 7, auch wenn nur
die eigene Liste gezeigt wird.

**Der Wahlbezirk ist die eine Ausnahme** (Tims Wunsch 15.09.2026: „ein
fünfter Filter … der Wahlbezirk heißt"). Er ist kein Merkmal einer
Kandidatur — wer antritt, steht in einem WAHLBEREICH und bekommt in jedem
seiner 15 bis 24 Wahlbezirke Stimmen; als Spalte gäbe es also nicht einen
Wert, sondern zwanzig. Als FILTER ergibt er dagegen genau eine Frage, die
sonst niemand beantworten kann: „Wer hat in meinem Wahllokal die meisten
Personenstimmen?" Dann sind Stimmen, Anteil und Rang die dieses Bezirks —
ein stadtweiter Rang neben Bezirks-Stimmen wäre eine Zahl aus einer anderen
Rechnung.
"""
from __future__ import annotations

from ..antworten import (
    ElectionAreaRef,
    ElectionCandidateParty,
    ElectionCandidateRanking,
    ElectionCandidateRow,
    ElectionDistrictRef,
    ElectionNight,
)

SORTS = ("votes", "party", "area", "name")


def _pct(part: int | None, whole: int | None) -> float | None:
    if part is None or not whole:
        return None
    return round(100.0 * part / whole, 1)


def _rows(night: ElectionNight, hochburgen: dict | None = None) -> list[ElectionCandidateRow]:
    """Jede Kandidatur als flache Zeile — noch ohne Rang."""
    farbe = {p["slug"]: p for p in night["parties"]}
    out: list[ElectionCandidateRow] = []
    for area in night["areas"]:
        for ap in area["parties"]:
            p = farbe.get(ap["slug"])
            if p is None:
                continue
            for c in ap["candidates"]:
                out.append(ElectionCandidateRow(
                    rank=None,
                    party=p["slug"], party_short=p["short"], color=p["color"], color_dark=p["color_dark"],
                    area=area["number"], area_roman=area["roman"], area_name=area["name"],
                    position=c["position"], name=c["name"], occupation=c["occupation"], born=c["born"],
                    votes=c["votes"],
                    party_share_pct=_pct(c["votes"], ap["votes"]),
                    elected=c["elected"], projected_elected=c["projected_elected"],
                    votes_to_seat=c["votes_to_seat"],
                    **_hochburg(hochburgen, p["slug"], area["number"], c["position"]),
                ))
    return out


def _hochburg(hochburgen: dict | None, slug: str, bereich: int, platz: int) -> dict:
    """Die vier Felder zur Hochburg — leer, wenn es keine Personenstimmen gibt."""
    eintrag = (hochburgen or {}).get((slug, platz, bereich))
    if eintrag is None:
        return {"top_district": None, "top_district_name": "",
                "top_district_votes": None, "top_district_postal": False}
    stimmen, nr, name, brief = eintrag
    return {"top_district": nr, "top_district_name": name,
            "top_district_votes": stimmen, "top_district_postal": brief}


def _ranked(rows: list[ElectionCandidateRow]) -> list[ElectionCandidateRow]:
    """Rang nach Stimmen, stadtweit. Gleichstand teilt den Rang (1, 2, 2, 4) —
    wer gleich viele Stimmen hat, steht nicht zufällig vor dem anderen."""
    mit = sorted((r for r in rows if r["votes"] is not None), key=lambda r: -(r["votes"] or 0))
    rang = 0
    for i, r in enumerate(mit, start=1):
        if i == 1 or r["votes"] != mit[i - 2]["votes"]:
            rang = i
        r["rank"] = rang
    return rows


def _sorted(rows: list[ElectionCandidateRow], sort: str, order: dict[str, int]) -> list[ElectionCandidateRow]:
    def stimmen(r: ElectionCandidateRow) -> tuple:
        # Ohne Stimmen ans Ende, dort in Stimmzettel-Reihenfolge — so sieht die
        # Liste vor der Auszählung nicht wie ein Zufall aus.
        return (r["votes"] is None, -(r["votes"] or 0), order.get(r["party"], 99), r["area"], r["position"])

    if sort == "party":
        return sorted(rows, key=lambda r: (order.get(r["party"], 99),) + stimmen(r))
    if sort == "area":
        return sorted(rows, key=lambda r: (r["area"],) + stimmen(r))
    if sort == "name":
        return sorted(rows, key=lambda r: (r["name"].casefold(), r["area"]))
    return sorted(rows, key=stimmen)


def _parties(night: ElectionNight) -> list[ElectionCandidateParty]:
    out: list[ElectionCandidateParty] = []
    for p in night["parties"]:
        liste = personen = 0
        gezaehlt = False
        for a in night["areas"]:
            for ap in a["parties"]:
                if ap["slug"] != p["slug"]:
                    continue
                if ap["list_votes"] is not None:
                    liste += ap["list_votes"]
                    gezaehlt = True
                if ap["candidate_votes"] is not None:
                    personen += ap["candidate_votes"]
                    gezaehlt = True
        out.append(ElectionCandidateParty(
            slug=p["slug"], short=p["short"], name=p["name"], color=p["color"], color_dark=p["color_dark"],
            candidates_total=p["candidates_total"],
            list_votes=liste if gezaehlt else None,
            candidate_votes=personen if gezaehlt else None,
            personal_pct=_pct(personen, liste + personen) if gezaehlt else None,
        ))
    return out


def _im_bezirk(rows: list[ElectionCandidateRow], bezirk: dict) -> list[ElectionCandidateRow]:
    """Dieselben Kandidaturen, aber mit den Zahlen EINES Wahlbezirks.

    Gezeigt werden die des Wahlbereichs, zu dem der Bezirk gehört — andere
    stehen dort gar nicht auf dem Stimmzettel. ``votes`` wird zur Zahl aus
    diesem Wahllokal, ``party_share_pct`` zum Anteil an allen Stimmen der
    eigenen Liste DORT. Was der Bezirk nicht meldet (noch nicht ausgezählt),
    bleibt ``None`` — und nicht 0, das wäre eine Aussage.
    """
    listen = bezirk["lists"]
    aus: list[ElectionCandidateRow] = []
    for r in rows:
        if r["area"] != bezirk["area"]:
            continue
        eintrag = listen.get(r["party"])
        stimmen = (eintrag or {}).get("candidates", {}).get(r["position"]) if eintrag else None
        gesamt = (eintrag or {}).get("total") if eintrag else None
        aus.append(ElectionCandidateRow(
            **{**r, "votes": stimmen, "party_share_pct": _pct(stimmen, gesamt),
               # Der Abstand zum Sitz ist eine Rechnung über den ganzen
               # Wahlbereich; im Bezirk hat er keine Bedeutung.
               "votes_to_seat": None, "rank": None},
        ))
    return aus


def ranking(night: ElectionNight, *, sort: str = "votes", party: str | None = None,
            area: int | None = None, bezirk: dict | None = None,
            bezirke: list[ElectionDistrictRef] | None = None,
            hochburgen: dict | None = None) -> ElectionCandidateRanking:
    """Die Rangliste zu einem Stand — sortiert, gefiltert, mit stadtweitem Rang.

    ``bezirk`` (aus ``service.district_candidates``) schaltet auf einen
    Wahlbezirk um: dann zählen dessen Zahlen, und der Rang ist der in diesem
    Wahllokal.
    """
    if sort not in SORTS:
        raise ValueError(f"unbekannte Sortierung: {sort!r} (erlaubt: {', '.join(SORTS)})")
    order = {p["slug"]: p["index"] for p in night["parties"]}
    alle = _ranked(_rows(night, hochburgen))
    if bezirk is not None:
        # Im Bezirk wird neu gerechnet UND neu gereiht — der stadtweite Rang
        # gehört zu stadtweiten Stimmen.
        alle = _ranked(_im_bezirk(alle, bezirk))
        area = bezirk["area"]
    rows = [r for r in alle
            if (party is None or r["party"] == party) and (area is None or r["area"] == area)]
    return ElectionCandidateRanking(
        dataset=night["dataset"], phase=night["phase"],
        person_votes_available=night["person_votes_available"],
        election=night["election"],
        sort=sort, party=party, area=area,
        district=bezirk["number"] if bezirk else None,
        district_name=bezirk["name"] if bezirk else "",
        districts=list(bezirke or ()),
        total=len(alle), shown=len(rows),
        parties=_parties(night),
        areas=[ElectionAreaRef(number=a["number"], roman=a["roman"], name=a["name"]) for a in night["areas"]],
        rows=_sorted(rows, sort, order),
    )
