#!/usr/bin/env python3
"""Match each user topic to the council decisions that are actually ABOUT it.

Für jedes Thema sucht der Lauf Kandidaten wie die KI-Frage (``hybrid_search``:
Vektor ∪ Vorlagen-Chunks ∪ BM25) und lässt sie vom Cross-Encoder bewerten.
Gespeichert wird in ``council_topic_matches``, was die Relevanzschwelle
schafft — nicht die ersten n einer nach Ähnlichkeit sortierten Liste. Re-run
after embed_decisions.py (the weekly enrich cron does both). fastembed is
needed (not a web dependency)::

    pip install fastembed
    python scripts/match_topics_decisions.py --schwelle -1.0 --top-k 40

Die Definition selbst („welcher Beschluss gehört zu diesem Thema") steht seit
dem 16.08.2026 nicht mehr hier, sondern in ``council.topic_intel.treffer`` —
das Bearbeiten-Blatt im Web rechnet damit vorab dasselbe aus. Vorher hatte es
eine eigene Suche mit eigener Schwelle und eigenem Deckel und zeigte deshalb
zu demselben Thema eine andere Zahl als die Themen-Karte.

Warum nicht mehr der reine Bi-Encoder mit Mindest-Cosinus: Am Bestand
gemessen (15.08.2026, 32 echte Themen) lagen ALLE 60 besten Kandidaten JEDES
Themas über der alten Schwelle 0.45 — sie hat nie etwas verworfen, und jedes
Thema bekam exakt ``--top-k`` Treffer. Die Zahl auf der Themen-Karte war
damit der Deckel, nicht der Befund. Der Grund ist bekannt (siehe
``council/embeddings.KONTEXT_RERANK_MIN``): Bi-Encoder-Cosines trennen
amtliche Kurztexte nicht, und ihr absolutes Niveau hängt am Thema (Bestwert
0.62 bei „Alte Fleiwa" gegen 0.88 bei „Stadion Oldenburg") — eine feste
Cosinus-Schwelle kann es also gar nicht geben. Der Cross-Encoder trennt mit
über einem Logit-Punkt Abstand, und dieselbe Suche findet obendrein die
Treffer, die der Vektor allein verfehlte („Vorstellung IQON" stand in keiner
der 60 besten Vektor-Kandidaten des Themas IQON, per BM25 steht es auf Platz 1).

Gemeldet wird nur, was **aktuell** ist: Ein Treffer wandert immer in die Liste
und in den Zähler, eine Mail löst er aber nur aus, wenn seine Sitzung innerhalb
der letzten sechs Monate lag (``topic_intel.vor_sechs_monaten``, dieselbe Grenze
wie „n in 6 Monaten" auf der Themen-Karte). Sonst verschickt der Lauf Post über
Beschlüsse von 2023, sobald sie erstmals über die Relevanzschwelle rutschen —
siehe ``_notify_new_matches``.

Nach einer Neu-Extraktion der Beschlüsse einmal mit ``--ohne-meldungen``
laufen lassen: Die gespeicherten Verweise zeigen dann auf gelöschte IDs, der
Lauf legt sie neu an — und ohne den Schalter hielte er das für lauter neue
Beschlüsse und meldete sie allen Konten.
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.store import CouncilStore  # noqa: E402
from council.topic_intel import DECKEL, SCHWELLE, treffer, vor_sechs_monaten  # noqa: E402,F401
from kern.store import Store  # noqa: E402
from kern import digest_email  # noqa: E402
from council.ergebnisse import datum_lang, decision_href  # noqa: E402

NWZ_DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _notify_new_matches(nwz, council, owner_id: int, topic_name: str, new_ids: list[int],
                        *, stichtag: str) -> int:
    """13a-D: EIN Push/Mail je Thema — der Titel mit der größten Tragweite
    führt (COALESCE impact, importance — nicht der erste oder kurioseste),
    Rest als „— und n weitere". Tap öffnet die Themen-Trefferliste.

    Geht über die Warteschlange (``notify.einreihen``), nicht direkt über
    ``deliver_message``. Vorher tat es das — und stand damit als einziger Anlass
    außerhalb aller Grenzen aus Design 30a: Es kam auch dann an, wenn jemand
    „Ergebnisse zu meinen Themen" abgeschaltet oder Benachrichtigungen ganz
    ausgestellt hatte, es zählte nicht gegen die zwei am Tag, und es hätte
    mitten in der Nachtruhe klingeln können.

    Der Anlass ist **N3**: „Der Rat hat zu deinem Thema entschieden." Dass der
    Treffer hier aus dem Ähnlichkeitsabgleich stammt statt aus dem Protokoll
    einer abonnierten Sitzung, ist eine Frage der Herkunft, nicht der Bedeutung
    — für die Person ist es dieselbe Nachricht und gehört unter denselben
    Schalter.

    ``stichtag`` (ISO-Datum) ist der Alters-Riegel: Gemeldet wird nur, was seit
    diesem Tag getagt hat. „Neu" heißt hier nämlich bloß „stand letzte Woche
    noch nicht in der Trefferliste" — und das trifft auch uralte Beschlüsse, die
    erst jetzt über die Relevanzschwelle rutschen. Am 30.08.2026 ging so eine
    Mail zum Thema „Grundschule Krusenbusch" raus, deren Beschluss vom
    **07.03.2023** stammte: Er stand im BM25-Fenster auf Rang 44 von 45 und kam
    mit −0,985 gegen die Schwelle −1,0 durch, weil die Vorlage Krusenbusch in
    einer Aufzählung aller Grundschulen nennt. Als Treffer ist das in Ordnung —
    er bleibt in der Liste und im Zähler stehen. Als Post ist es das nicht
    (Tim: „über die Mail würde ich immer nur über aktuelle Beschlüsse
    informieren").

    Der Riegel ist Pflichtargument, kein Vorgabewert: Wer diese Funktion neu
    aufruft, soll die Grenze bewusst setzen — ein vergessener Wert wäre genau
    die Mail, die es hier abzustellen galt.
    """
    from kern import notify

    if not nwz.get_web_user_by_id(owner_id):
        return 0                      # Konto zwischenzeitlich gelöscht
    # get_decision liefert d.* (impact/importance/amount_eur) — die schlanke
    # Batch-Query der QA-Zitate kennt diese Spalten nicht.
    decisions = [d for d in (council.get_decision(i) for i in new_ids) if d]
    # Ohne Sitzungsdatum lieber schweigen: `get_decision` verbindet mit
    # `council_sessions`, ein leeres Feld wäre also ein kaputter Datensatz —
    # kein Grund, jemanden zu wecken.
    decisions = [d for d in decisions if (d.get("session_date") or "") >= stichtag]
    if not decisions:
        return 0
    decisions.sort(key=lambda d: (d.get("impact") if d.get("impact") is not None
                                  else (d.get("importance") or 0)), reverse=True)
    lead = decisions[0]
    n = len(decisions)
    kurz = " ".join(str(topic_name or "").split())[:80]
    subject = f"Neu zu \u201e{kurz}\u201c" + (f" \u2014 {n} Beschl\u00fcsse" if n > 1 else "")
    lead_line = html.escape((lead.get("title") or "").strip())
    if lead.get("amount_eur"):
        lead_line += f" ({int(lead['amount_eur']):,} \u20ac)".replace(",", ".")
    # Der Text nannte „Meine Themen“ nur — jetzt führt ein Knopf auch dorthin,
    # und der führende Beschluss ist direkt anklickbar.
    #
    # Unter dem Titel stehen Gremium und Sitzungsdatum (Tims Wunsch vom
    # 30.08.2026). Ohne sie beantwortet die Mail ihre naheliegendste Rückfrage
    # nicht — „wann war das?" —, und amtliche Titel führen dabei sogar in die
    # Irre: Der Krusenbusch-Titel trug ein „vom 15.02.2023", das Datum der
    # Elternanfrage, während die Sitzung am 07.03.2023 stattfand.
    wann = " · ".join(t for t in ((lead.get("committee") or "").strip(),
                                  datum_lang(lead.get("session_date") or "")) if t)
    msg = (
        f"<p style='margin:0'>Neu zu deinem Thema <b>{html.escape(kurz)}</b>:</p>"
        + digest_email.liste(
            [f"<a href=\"{digest_email.absolut(decision_href(lead["id"]))}\">{lead_line}</a>"
             + (digest_email.meta(wann) if wann else "")]
            + ([f"und {n - 1} weitere"] if n > 1 else [])
        )
        + digest_email.knopf("/topics", "Alle Treffer ansehen" if n > 1 else "Beschluss ansehen")
    )
    return 1 if notify.einreihen(nwz, owner_id, notify.N3_ERGEBNIS, subject, msg, "/topics") else 0


def process(top_k: int = DECKEL, threshold: float = SCHWELLE, *, ohne_meldungen: bool = False) -> dict:
    nwz = Store(NWZ_DB)
    council = CouncilStore(COUNCIL_DB)
    try:
        # WER schon mal hingesehen hat, muss ZUERST feststehen — vor dem
        # Aufräumen. Genau nach einer Neu-Extraktion, wenn dieser Lauf am
        # nötigsten ist, zeigen ALLE Gelesen-Marken auf tote IDs; der Purge
        # räumt sie also restlos weg, und danach sähe jedes Thema aus wie eines,
        # das noch nie jemand geöffnet hat.
        gesehen_vorher = nwz.topics_mit_gelesen_stand() if ohne_meldungen else set()

        # Aufräumen: Verweise auf Beschlüsse, die es nicht mehr gibt, machen
        # aus jedem Zähler ein Versprechen, das die Suche nicht hält.
        gueltige = {r["id"] for r in council._conn.execute("SELECT id FROM council_decisions")}
        verwaist = nwz.purge_stale_topic_matches(gueltige)
        if verwaist:
            print(f"  {verwaist} tote Beschluss-Verweise entfernt "
                  f"(Treffer und Gelesen-Marken)")

        # Einmal je Lauf gerechnet, damit ein Lauf über Mitternacht nicht in der
        # Mitte die Grenze verschiebt — und mit derselben Funktion wie die
        # „n in 6 Monaten" der Themen-Karte.
        stichtag = vor_sechs_monaten().isoformat()

        by_owner = nwz.get_all_owner_topics()  # {owner_id: [TopicRow]}
        n_topics = sum(len(v) for v in by_owner.values())
        total = 0
        notified = 0
        gedeckelte = 0
        for owner_id, topics in by_owner.items():
            for t in topics:
                # RL-U15 (13a-D): „neu" = Diff gegen den letzten Lauf. Beim
                # allerersten Matching eines Themas wird nicht gepusht (der
                # „Neu"-Zähler in der App zeigt die Erst-Treffer ohnehin).
                old_ids = {m["decision_id"] for m in nwz.get_topic_decision_matches(t.id)}
                name = (t.name or "").strip()
                text = f"{name}. {t.description}".strip()
                # Bricht der Cross-Encoder weg, wirft `treffer` — und der Lauf
                # endet, statt Rauschen zu speichern. Die Treffer von letzter
                # Woche sind besser als frisches Rauschen.
                hits, gedeckelt, kandidaten = treffer(council, name, text,
                                                      deckel=top_k, schwelle=threshold)
                # als_neu=False im Reparaturlauf: Die neu angelegten Zeilen
                # dürfen nicht als Treffer dieser Woche gelten — sonst holt der
                # Wochenüberblick nach, was die abgeschalteten Meldungen gerade
                # verhindert haben.
                nwz.save_topic_decision_matches(t.id, owner_id, hits,
                                                gedeckelt=gedeckelt, kandidaten=kandidaten,
                                                als_neu=not ohne_meldungen)
                total += len(hits)
                gedeckelte += 1 if gedeckelt else 0
                # Ein Reparaturlauf ist keine Neuigkeit: Dieselben Beschlüsse
                # tragen nach einer Neu-Extraktion neue IDs, also gälte jeder
                # Treffer wieder als ungelesen. Wer die Liste schon einmal
                # geöffnet hatte, bekommt sie deshalb wieder als gelesen
                # zurück — sonst leuchtet bei JEDEM Thema wieder „n neu",
                # obwohl der Rat nichts entschieden hat.
                if ohne_meldungen and t.id in gesehen_vorher:
                    nwz.mark_topic_hits_seen(owner_id, t.id)
                new_ids = [int(did) for did, _ in hits if int(did) not in old_ids]
                if new_ids and old_ids and not ohne_meldungen:
                    notified += _notify_new_matches(nwz, council, owner_id, t.name, new_ids,
                                                    stichtag=stichtag)
        # Eingereiht ist nicht zugestellt: Ohne diesen Aufruf läge alles bis zum
        # nächsten Cron-Job (7 Uhr) still. Die Nachtruhe verschiebt ohnehin, was
        # jetzt nicht raus darf — dieser Lauf startet sonntags um 3 Uhr.
        from kern import notify

        zugestellt = notify.zustellen(nwz)
        return {"topics": n_topics, "matches": total, "notified": notified,
                "gedeckelt": gedeckelte, "zugestellt": zugestellt}
    finally:
        nwz.close()
        council.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # Der Deckel entscheidet nicht mehr, WAS ein Treffer ist — das tut die
    # Schwelle — sondern nur noch, wie viel je Thema gespeichert wird. Bei
    # breiten Themen („Fliegerhorst": 198 Beschlüsse im Bestand) greift er,
    # und dann sagt die Themen-Karte „40+" statt einer erfundenen Endzahl.
    ap.add_argument("--top-k", type=int, default=DECKEL)
    ap.add_argument("--schwelle", "--threshold", type=float, default=SCHWELLE,
                    dest="schwelle",
                    help="Mindest-Relevanz (Cross-Encoder-Logit), Vorgabe %(default)s")
    # Für Reparaturläufe: Nach einer Neu-Extraktion sind ALLE gespeicherten
    # Treffer neu — ohne diesen Schalter bekäme jedes Konto für jedes Thema
    # eine Meldung UND einen „n neu"-Zähler, obwohl der Rat nichts Neues
    # entschieden hat.
    ap.add_argument("--ohne-meldungen", action="store_true",
                    help="Treffer neu berechnen, ohne zu benachrichtigen — und "
                         "ohne schon gelesene Listen wieder auf ungelesen zu setzen")
    args = ap.parse_args()
    st = process(args.top_k, args.schwelle, ohne_meldungen=args.ohne_meldungen)
    print(f"=== done: {st['matches']} decision matches across {st['topics']} topic(s), "
          f"{st['gedeckelt']} gedeckelt ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
