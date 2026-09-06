"""N3 „Es ist entschieden" — die Ergebnis-Meldung (Design 30a).

Die App weckte bisher **vor** der Debatte und schwieg beim Beschluss: Der
Moment, auf den alles zulief, kam nie an. Diese Meldung schließt den Vorgang.

**Wann sie kommt — und warum nicht am nächsten Morgen.** 30a setzt sie auf den
Tag nach der Sitzung („beschlossen um 22:40, zugestellt um 7 Uhr"). Das gibt die
Quelle nicht her: Beschlüsse entstehen ausschließlich aus dem Protokoll-PDF, und
das erscheint spät. Nachgemessen am 26.07.2026:

* Verkehrsausschuss 16.02. ✓ · 09.03. ✓ · 20.04. ✓ · **08.06. noch keins** (48 Tage)
* Juni-Sitzungen insgesamt: 1 von 15 mit Protokoll
* Rat 01.06.: nach rund 3,5 Wochen da — der Rat ist schneller als die Ausschüsse

Weder die Sitzungsseite noch die Beratungsfolge der Vorlage tragen das Ergebnis
vorher: Auf der Sitzungsseite kommen „angenommen", „abgelehnt", „einstimmig"
kein einziges Mal vor, und ``council_deliberations.result`` kennt nur
``Kenntnisnahme`` / ``Entscheidung`` / ``Vorberatung`` — die Beratungsart, nicht
das Ergebnis.

Die Meldung sagt deshalb **das Sitzungsdatum dazu**. Sie darf keine Frische
suggerieren, die es nicht gibt: „Beschlossen im Verkehrsausschuss am 8. Juni"
statt eines Textes, der nach „gerade eben" klingt. Ausgelöst wird sie vom
Protokoll-Import (``scripts/check_protocols.py``), nicht von der Sitzung.
"""
from __future__ import annotations

from urllib.parse import quote
import html
import logging

from kern import notify
from council import bookmarks as bookmark_logic

logger = logging.getLogger("council.ergebnisse")

#: Wie ein Ergebnis in der Meldung heißt.
ERGEBNIS_WORT = {
    "accepted": "angenommen",
    "rejected": "abgelehnt",
    "postponed": "vertagt",
    "noted": "zur Kenntnis genommen",
    "no_decision": "ohne Beschluss geblieben",
}

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")


def _datum(iso: str) -> str:
    teile = str(iso or "")[:10].split("-")
    try:
        return f"{int(teile[2])}. {MONATE[int(teile[1]) - 1]}"
    except (ValueError, IndexError):
        return str(iso or "")


def datum_lang(iso: str) -> str:
    """„7. März 2026" — mit Jahr, im Gegensatz zu ``_datum``.

    Die Protokoll-Meldung darf das Jahr weglassen: Sie kommt Wochen nach der
    Sitzung, das Jahr ist dasselbe. Der Wochenabgleich meldet dagegen alles aus
    einem halben Jahr, und ein halbes Jahr reicht über den Jahreswechsel —
    „7. März" wäre dort im Januar schlicht mehrdeutig.
    """
    teile = str(iso or "")[:10].split("-")
    try:
        return f"{int(teile[2])}. {MONATE[int(teile[1]) - 1]} {int(teile[0])}"
    except (ValueError, IndexError):
        return str(iso or "")


#: Wie ein Abstimmungsverhältnis in der Meldung heißt.
VOTE_WORT = {"unanimous": "einstimmig", "majority": "mehrheitlich"}


def _stimmen(d: dict) -> str:
    """„einstimmig" bzw. „mehrheitlich, 11 dagegen" — nur, wenn belegt."""
    teile = []
    if d.get("vote"):
        teile.append(VOTE_WORT.get(d["vote"], str(d["vote"])))
    if d.get("no_votes"):
        teile.append(f"{d['no_votes']} dagegen")
    if d.get("abstentions"):
        teile.append(f"{d['abstentions']} Enthaltungen")
    return ", ".join(teile)


def _ohne_nachsatz(text: str | None) -> str:
    """Titel ohne den amtlichen Nachsatz „- Beschluss": Dass es ein Beschluss
    ist, sagt der Brief schon — in der Zeile darunter steht das Ergebnis."""
    t = " ".join(str(text or "").split())
    for schwanz in (" - Beschluss", " – Beschluss", " - Beschlussfassung"):
        if t.endswith(schwanz):
            t = t[: -len(schwanz)]
    return t


def _kurz(text: str | None, grenze: int = 60) -> str:
    """Kurzform für Betreff und Push."""
    t = _ohne_nachsatz(text)
    return t if len(t) <= grenze else t[: grenze - 1].rstrip() + "…"


def _tragweite(d: dict) -> int:
    """Tragweite eines Beschlusses — ``impact``, ersatzweise ``importance``."""
    wert = d.get("impact")
    if wert is None:
        wert = d.get("importance")
    return int(wert or 0)


def _betrag(d: dict) -> str:
    """„57,3 Mio. €" bzw. „48.000 €" — nur, wenn ein Betrag belegt ist."""
    betrag = d.get("amount_eur")
    if not betrag:
        return ""
    if betrag >= 1_000_000:
        return f"{betrag / 1_000_000:.1f}".replace(".", ",") + " Mio. €"
    return f"{int(betrag):,}".replace(",", ".") + " €"


def _satz(d: dict) -> str:
    """„Im Verkehrsausschuss am 8. Juni angenommen (mehrheitlich, 11 dagegen)."

    Mit Sitzungsdatum — die Meldung kommt Wochen nach der Sitzung und darf
    keine Frische behaupten (siehe Modul-Doku).
    """
    wort = ERGEBNIS_WORT.get(d.get("outcome") or "", "entschieden")
    stimmen = _stimmen(d)
    wann = f"{d.get('committee') or 'Rat'} am {_datum(d.get('session_date') or '')}"
    return f"Im {wann} {wort}" + (f" ({stimmen})" if stimmen else "") + "."


def _leitkarte(d: dict, decision_href) -> str:
    """Der eine Beschluss, der eine Gruppe anführt: Titel als Link, Ergebnis
    und Stimmen, Betrag — und die „einfach erklärt"-Kurzfassung, wo es sie
    gibt. Sie steht in der Mail, damit die Person versteht, WAS entschieden
    wurde, ohne erst zu tippen; der Link bleibt der Weg zum Ganzen."""
    from kern import digest_email

    title = html.escape(_ohne_nachsatz(d.get("title")) or "Beschluss")
    betrag = _betrag(d)
    zeile = html.escape(_satz(d)) + (f" {html.escape(betrag)}." if betrag else "")
    kurz = " ".join(str(d.get("simple_summary") or "").split())
    if kurz:
        # Zwei Sätze reichen für die Mail; die Seite hat den ganzen Text.
        saetze = [t for t in kurz.split(". ") if t]
        kurz = ". ".join(saetze[:2]).rstrip(".") + "."
    einfach = (
        "<div style='margin-top:8px;padding:10px 12px;background:#f1f5f9;border-radius:10px;"
        "font-size:14px;line-height:1.5'>"
        "<span style='font-family:\"SF Mono\",SFMono-Regular,Consolas,Menlo,monospace;"
        "font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:#64748b'>"
        "Lotti erklärt’s einfach</span><br>"
        f"{html.escape(kurz)}</div>"
    ) if kurz else ""
    return (
        "<div style='margin-top:12px'>"
        f"<a href=\"{digest_email.absolut(decision_href(d['id']))}\" style='color:#0764a6;"
        f"font-size:16px;font-weight:700;text-decoration:none;line-height:1.3'>{title}</a>"
        f"{digest_email.meta(zeile)}{einfach}</div>"
    )


def _nebenzeile(d: dict, decision_href) -> str:
    from kern import digest_email

    title = html.escape(_ohne_nachsatz(d.get("title")) or "Beschluss")
    wort = ERGEBNIS_WORT.get(d.get("outcome") or "", "entschieden")
    betrag = _betrag(d)
    return (f"<a href=\"{digest_email.absolut(decision_href(d['id']))}\" "
            f"style='color:#0f172a;text-decoration:none'>{title}</a> "
            f"<span style='color:#64748b'>— {wort}{' · ' + html.escape(betrag) if betrag else ''}</span>")


def _protokoll_satz(protokolle: list[tuple[str, str]]) -> str:
    """„Neues Protokoll: Rat vom 1. Juni." bzw. „Neue Protokolle: Rat vom
    1. Juni, Stadtplanung und Bauen vom 18. Juni." — ohne Genitiv, den
    „Ausschuss für Stadtplanung und Bauen" nicht mitmacht."""
    # In Sitzungsreihenfolge, nicht in der des Laufs.
    namen = [f"<b>{html.escape(g)}</b> vom {_datum(t)}"
             for g, t in sorted(protokolle, key=lambda p: p[1])]
    if len(namen) == 1:
        return f"Neues Protokoll: {namen[0]}."
    return f"Neue Protokolle: {', '.join(namen[:-1])} und {namen[-1]}."


def schubbrief(gruppen: list[dict], protokolle: list[tuple[str, str]],
               ohne_beschluss: list[dict], decision_href,
               sitzung_href_fuer=None) -> tuple[str, str, str, str, bool]:
    """EIN Brief je Person und Protokoll-Schub (Tims Wunsch 06.09.2026).

    Vorher ging je Sitzung eine Meldung raus — bei einem Schub aus Rat und
    drei Ausschüssen also vier, die die Tagesgrenze prompt zu einem
    Sammelposten ohne Struktur bündelte. Jetzt kommt alles in einem Brief,
    gruppiert nach dem, WARUM man es bekommt: „Dein Thema · Stadion",
    „Gemerkte Punkte". Je Gruppe führt der Beschluss mit der größten
    Tragweite als Karte, der Rest steht als Liste darunter.

    ``gruppen``: ``[{"name": "Stadion", "kicker": "Dein Thema · Stadion",
    "beschluesse": [...]}]`` — jede Liste absteigend nach Tragweite.
    ``protokolle``: ``[(gremium, sitzungsdatum)]`` für den Einleitungssatz.
    ``ohne_beschluss``: gemerkte Punkte, zu denen das Protokoll keinen
    eigenen Beschluss trägt (``{"title", "ksinr", "committee",
    "session_date", "tops"}``) — sie bekommen eine ehrliche Zeile.

    Liefert ``(betreff, html, ziel, push_text, wichtig)``. ``wichtig`` ist
    gesetzt, sobald ein Beschluss ``TOP_MINDEST`` erreicht — dann darf der
    Brief an der Tagesgrenze vorbei (kern.notify.einreihen).
    """
    from council.store import CouncilStore
    from kern import digest_email

    alle = [d for g in gruppen for d in g["beschluesse"]]
    n = len(alle)
    wichtig = any(_tragweite(d) >= CouncilStore.TOP_MINDEST for d in alle)

    # Betreff, Ziel und Push-Text.
    if n == 1:
        lead = alle[0]
        wort = ERGEBNIS_WORT.get(lead.get("outcome") or "", "entschieden")
        betreff = f"{(lead.get('title') or 'Dein Thema').strip()}: {wort}"
        ziel = decision_href(lead["id"])
        push = _satz(lead)
    elif n:
        namen = [g["name"] for g in gruppen if g["beschluesse"]]
        kopf = " und ".join(namen[:2]) + (" u. a." if len(namen) > 2 else "")
        betreff = f"Entschieden: {kopf} — {n} Ergebnisse"
        ziel = "/topics"
        teile = []
        for g in gruppen:
            if not g["beschluesse"]:
                continue
            lead = g["beschluesse"][0]
            wort = ERGEBNIS_WORT.get(lead.get("outcome") or "", "entschieden")
            stimmen = f" ({lead['no_votes']} dagegen)" if lead.get("no_votes") else ""
            teile.append(f"{_kurz(g['name'], 30)}: {wort}{stimmen}")
        rest = n - len(teile)
        push = " · ".join(teile[:2])
        if rest > 0 or len(teile) > 2:
            uebrig = n - min(2, len(teile))
            push += f" · {uebrig} weitere aus {len(protokolle)} Protokoll" + \
                ("en" if len(protokolle) != 1 else "")
        if len(push) > 180:
            push = push[:179] + "…"
    else:
        # Nur gemerkte Punkte ohne erkannten Beschluss.
        erster = ohne_beschluss[0]
        betreff = f"Protokoll ist da: {erster['title']}"
        ziel = (sitzung_href_fuer(erster) if sitzung_href_fuer
                else sitzung_href(erster["ksinr"], erster.get("tops")))
        push = "Für den gemerkten Punkt wurde kein eigener Beschluss erkannt."

    # Der Brief.
    teile_html = ["<p style='margin:0'>" + _protokoll_satz(protokolle)
                  + (f" Darin {'steht eine Entscheidung' if n == 1 else f'stehen {n} Entscheidungen'} "
                     "zu dem, was du verfolgst." if n else "") + "</p>"]
    for g in gruppen:
        if not g["beschluesse"]:
            continue
        k = len(g["beschluesse"])
        teile_html.append(digest_email.abschnitt(
            g["kicker"], f"{k} {'Beschluss' if k == 1 else 'Beschlüsse'}"))
        teile_html.append(_leitkarte(g["beschluesse"][0], decision_href))
        if k > 1:
            teile_html.append(digest_email.liste(
                [_nebenzeile(d, decision_href) for d in g["beschluesse"][1:]]))
    for o in ohne_beschluss:
        teile_html.append(digest_email.abschnitt("Gemerkter Punkt", "kein Beschluss"))
        link = sitzung_href_fuer(o) if sitzung_href_fuer else sitzung_href(o["ksinr"], o.get("tops"))
        teile_html.append(
            f"<div style='margin-top:12px'><b>{html.escape(o['title'])}</b>"
            + digest_email.meta(f"{o.get('committee') or 'Rat'} · {datum_lang(o.get('session_date') or '')}")
            + "<div style='margin-top:6px;font-size:14px'>Das Protokoll ist da, aber zu diesem "
              "Punkt wurde kein eigener Beschluss erkannt — etwa weil er abgesetzt, nur beraten "
              "oder als Formalie behandelt wurde. "
            + f"<a href=\"{digest_email.absolut(link)}\" style='color:#0764a6'>Zum Punkt</a>.</div></div>"
        )
    if n > 1:
        teile_html.append(digest_email.knopf("/topics", "Alle Ergebnisse ansehen"))
    elif n == 1:
        teile_html.append(digest_email.knopf(ziel, "Zum Beschluss"))
    # Ohne Zeilenumbrüche: die Hülle rendert mit white-space:pre-wrap.
    return betreff, "".join(teile_html), ziel, push, wichtig


def decision_href(decision_id: int) -> str:
    """Ziel einer Ergebnis-Meldung — die Beschluss-Seite (30a, Grenze 4).
    Spiegelt web/frontend/lib/routes.ts (Query-Parameter statt Pfad-Segment,
    damit der (app)-Bereich statisch exportierbar bleibt)."""
    return f"/council/decision?id={decision_id}"


def sitzung_href(ksinr: int, tops: list[str] | None = None) -> str:
    """Ziel einer Tagesordnungs-Meldung — die Sitzung in der App (30a, Grenze 4).

    Bewusst ein App-Pfad und NICHT die Ratsinfo-Adresse: Der Tap-Handler der App
    (``lib/push.ts``) navigiert nur zu Zielen, die mit ``/`` beginnen. Mit der
    externen URL tat ein Antippen wortlos nichts und die App blieb auf der
    Startseite stehen. Der Ratsinfo-Link gehört in den Meldungstext.

    ``tops`` nennt die Tagesordnungspunkte, um die es in der Meldung geht — die
    App springt dann nicht nur zur Sitzung, sondern zu genau diesen Zeilen. Die
    Nummern gehen **vollständig** mit (``"Ö 6"``, nicht ``"6"``): ``Ö 6`` und
    ``N 6`` sind verschiedene Punkte, ein öffentlicher und ein nichtöffentlicher.

    Spiegelt ``sessionHref`` aus web/frontend/lib/routes.ts.
    """
    ziel = f"/council?tab=sessions&ksinr={ksinr}"
    sauber = [t.strip() for t in (tops or []) if t and t.strip()]
    if sauber:
        ziel += "&top=" + quote(",".join(sauber))
    return ziel


def melde_ergebnisse(council_store, ratslotse_store, ksinrs: list[int]) -> int:
    """Für frisch geparste Sitzungen die Ergebnis-Briefe einreihen.

    Empfänger sind die Konten, denen zu **einer dieser** Sitzungen schon ein
    Tagesordnungspunkt gemeldet wurde (aus N1/N2) oder die einen Punkt darin
    ausdrücklich gemerkt haben — der Vorgang, den sie kennen, bekommt seinen
    Abschluss. Wer nie etwas dazu gehört hat, wird nicht nachträglich
    behelligt.

    Seit dem 06.09.2026 ist es **ein Brief je Person und Lauf** (``schubbrief``),
    nicht mehr eine Meldung je Sitzung: Protokolle kommen in Schüben, und
    vier Einzelmeldungen wurden von der Tagesgrenze ohnehin zu einem
    strukturlosen Bündel. Gibt die Zahl der eingereihten Briefe zurück.
    """
    je_owner: dict[int, dict] = {}

    def eintrag(owner_id: int) -> dict:
        return je_owner.setdefault(owner_id, {
            "gruppen": {}, "ohne": [], "protokolle": [], "ksinrs": [],
            "bookmark_ids": [], "gesehen": set()})

    for ksinr in ksinrs:
        sitzung = council_store.get_session(ksinr)
        if not sitzung:
            continue
        alle = {str(d.get("item_number") or ""): d
                for d in council_store.get_decisions(ksinr) if d.get("kind") != "subvote"}

        # Ein ausdrücklich abonnierter Merkeintrag ist ein zweiter, engerer
        # Weg zum selben Ereignis. Beide Wege hier zusammenführen, damit ein
        # Konto mit Themen-Treffer UND gemerktem TOP nicht zweimal dieselbe
        # Protokoll-Veröffentlichung bekommt.
        bookmark_rows = ratslotse_store.bookmark_result_targets(ksinr)
        konkrete_bookmarks = []
        for row in bookmark_rows:
            resolved = bookmark_logic.resolve_bookmark(row, council_store)
            if resolved.get("agenda_group"):
                # Altbestand: Oberpunkte wurden vor der Blatt-TOP-Regel noch
                # akzeptiert. Kein Ergebnis versprechen, das es nicht gibt.
                ratslotse_store.set_bookmark_result_notification(row["owner_id"], row["id"], False)
                continue
            konkrete_bookmarks.append(row)
        bookmarks_by_owner: dict[int, list[dict]] = {}
        for row in konkrete_bookmarks:
            bookmarks_by_owner.setdefault(row["owner_id"], []).append(row)
        owners = set(ratslotse_store.owners_with_agenda_match(ksinr)) | set(bookmarks_by_owner)
        if not alle and not bookmarks_by_owner:
            continue

        for owner_id in sorted(owners):
            eigene_bookmarks = bookmarks_by_owner.get(owner_id, [])
            if ratslotse_store.result_already_sent(ksinr, owner_id):
                ratslotse_store.mark_bookmark_results_notified([b["id"] for b in eigene_bookmarks])
                continue
            e = eintrag(owner_id)
            e["ksinrs"].append(ksinr)
            e["bookmark_ids"] += [b["id"] for b in eigene_bookmarks]
            gefunden = 0
            # Themen-Treffer: je Thema eine Gruppe. Derselbe Beschluss kann
            # zu zwei Themen passen — er steht dann beim ersten.
            for m in ratslotse_store.agenda_matches_for_owner(owner_id, [ksinr]).get(ksinr, []):
                d = alle.get(str(m["item_number"]))
                if not d or not d.get("outcome") or d["id"] in e["gesehen"]:
                    continue
                name = (m.get("topic_name") or "Dein Thema").strip()
                e["gruppen"].setdefault(name, {"name": name, "kicker": f"Dein Thema · {name}",
                                               "beschluesse": []})["beschluesse"].append(d)
                e["gesehen"].add(d["id"])
                gefunden += 1
            # Gemerkte TOPs gegen den aktuellen Stand auflösen — nicht stumpf
            # über die gespeicherte Nummer, denn die kann sich bis zur Sitzung
            # verschoben haben.
            for bookmark in eigene_bookmarks:
                d = bookmark_logic.resolve_bookmark(bookmark, council_store).get("decision")
                if d and d.get("outcome") and d["id"] not in e["gesehen"]:
                    e["gruppen"].setdefault("Gemerkt", {"name": "Gemerkte Punkte",
                                                          "kicker": "Gemerkte Punkte",
                                                          "beschluesse": []})["beschluesse"].append(d)
                    e["gesehen"].add(d["id"])
                    gefunden += 1
            if not gefunden and eigene_bookmarks:
                # Für einen ausdrücklich gemerkten TOP ist auch „Protokoll da,
                # aber kein eigener Beschluss erkannt" eine nützliche und
                # ehrliche Antwort. Themen-Treffer allein bleiben still, wenn
                # keine belastbare Entscheidung vorliegt.
                erster = eigene_bookmarks[0]
                e["ohne"].append({
                    "title": erster.get("title") or "Gemerkter Tagesordnungspunkt",
                    "ksinr": ksinr, "committee": sitzung["committee"],
                    "session_date": sitzung["session_date"],
                    "tops": [str(b.get("item_number") or "") for b in eigene_bookmarks],
                })
            if gefunden or eigene_bookmarks:
                e["protokolle"].append((sitzung["committee"], sitzung["session_date"]))

    eingereiht = 0
    for owner_id in sorted(je_owner):
        e = je_owner[owner_id]
        gruppen = list(e["gruppen"].values())
        for g in gruppen:
            g["beschluesse"].sort(key=_tragweite, reverse=True)
        gruppen.sort(key=lambda g: _tragweite(g["beschluesse"][0]), reverse=True)
        if gruppen or e["ohne"]:
            betreff, body, ziel, push, wichtig = schubbrief(
                gruppen, e["protokolle"], e["ohne"], decision_href)
            queued = notify.einreihen(ratslotse_store, owner_id, notify.N3_ERGEBNIS,
                                      betreff, body, ziel, push_text=push, wichtig=wichtig)
            if queued:
                eingereiht += 1
            logger.info("N3 für owner %s: %d Beschluss/Beschlüsse aus %d Sitzung(en)",
                        owner_id, len(e["gesehen"]), len(e["ksinrs"]))
        for ksinr in e["ksinrs"]:
            ratslotse_store.mark_result_sent(ksinr, owner_id)
        ratslotse_store.mark_bookmark_results_notified(e["bookmark_ids"])
    return eingereiht
