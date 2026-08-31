"""Warteschlange und harte Grenzen für Benachrichtigungen (Design 30a).

Bis hierher schickte jeder Anlass direkt los, sobald er etwas fand. Bei mehreren
Gremien-Abos konnten daraus an einem Sitzungstag beliebig viele Meldungen
werden, und ein Beschluss um 22:40 Uhr klingelte um 22:40 Uhr.

30a stellt vier Grenzen über *alle* Anlässe. Zwei davon sind hier zu Hause:

* **Höchstens zwei am Tag.** Pro Person, nicht pro Anlass. Fällt mehr an, wird
  gebündelt statt gestapelt — die letzte freie Zustellung des Tages nimmt alles
  Übrige als eine Nachricht mit. Nichts geht verloren, nichts wird zur Flut.
  Ausnahme sind die **termingebundenen** Anlässe (s. ``TERMINGEBUNDEN``): Sie
  haben ihren eigenen Vorrat von zwei am Tag.
* **Nachtruhe 21–7 Uhr.** Ratssitzungen enden regelmäßig nach 22 Uhr. Was danach
  entschieden wird, wartet bis zum Morgen — nichts im Rat ist so dringend, dass
  es jemanden weckt.

Die beiden anderen Grenzen stehen nicht hier, sondern in der Bauweise:
*nie ohne Ereignis* (es gibt schlicht keine Funktion, die ohne Ratsvorgang
einreiht) und *jede Mitteilung landet auf einer echten Seite* — ``url`` ist ein
Pflichtfeld, kein Vorgabewert auf die Startseite.

Ablauf: Die Cron-Jobs **reihen ein** (``einreihen``) und stoßen am Ende ihres
Laufs die **Zustellung** an (``zustellen``). Damit braucht es keinen eigenen
Cron-Eintrag: ``check_committees`` läuft um 7 Uhr und leert damit genau dann,
was die Nacht über liegen geblieben ist.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger("kern.notify")

#: Für Links in E-Mails — dort ist ein App-Pfad allein wertlos.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://ratslotse.de").rstrip("/")

# Ortszeit ist maßgeblich: „nichts zwischen 21 und 7 Uhr" meint 21 Uhr in
# Oldenburg, nicht in UTC. Gespeichert wird trotzdem UTC (wie überall sonst).
ZONE = ZoneInfo("Europe/Berlin")

NACHTRUHE_AB = 21   # ab 21:00 Ortszeit geht nichts mehr raus
NACHTRUHE_BIS = 7   # … bis 7:00 Ortszeit
TAGESGRENZE = 2     # höchstens zwei Zustellungen pro Person und Tag

#: Anlässe aus 30a/B. Der Schlüssel steht so in der Warteschlange und in den
#: Schaltern der Einstellungs-Seite.
N1_TAGESORDNUNG = "n1_tagesordnung"
#: Unter-Option von N1 (Tims Wunsch 26.08.2026): „Ich möchte zwar die
#: Tagesordnung bekommen, aber nicht über jede Änderung informiert werden."
#: Greift nur, solange N1 selbst an ist — siehe ``gewuenscht``.
N1_AENDERUNG = "n1_aenderung"
N2_THEMA = "n2_thema"
N3_ERGEBNIS = "n3_result"
N4_VORGANG = "n4_vorgang"
N5_VORABEND = "n5_vorabend"
N6_WOCHE = "n6_woche"

#: Anlässe, die an einen Termin gebunden sind: Kommen sie einen Tag später, sind
#: sie nicht verspätet, sondern wertlos — die Sitzung hat dann stattgefunden.
#: Sie bekommen deshalb einen eigenen Vorrat von ``TAGESGRENZE`` Zustellungen am
#: Tag (Tims Wunsch 17.08.2026: „die Morgen-Erinnerung soll immer am Vortag
#: kommen, egal wie viele Meldungen es schon gab"). Vorher teilten sie sich
#: einen Topf mit allem anderen — und weil der Vorabend-Lauf um 18 Uhr der
#: letzte des Tages ist, verlor die Erinnerung diesen Wettlauf regelmäßig: Am
#: 16.08.2026 lag sie ab 18 Uhr fertig da und ging erst am nächsten Morgen
#: raus, am Sitzungstag selbst.
#:
#: Es bleibt bei einem *eigenen* Topf statt bei „gar keine Grenze": Ein
#: Sitzungsabend mit drei Gremien soll nicht drei Erinnerungen einzeln
#: schicken — ab der dritten wird auch hier gebündelt.
TERMINGEBUNDEN = frozenset({N5_VORABEND})

#: Vorgaben aus 30a/B: drei an, drei aus. N5 und N6 sind bewusst aus — die
#: meisten brauchen keinen Kalender, sondern das Ergebnis; und wer den
#: Wochenüberblick will, schaltet dafür N1–N3 ab.
NOTIFY_DEFAULTS: dict[str, bool] = {
    N1_TAGESORDNUNG: True,
    N1_AENDERUNG: True,
    N2_THEMA: True,
    N3_ERGEBNIS: True,
    N4_VORGANG: True,
    N5_VORABEND: False,
    N6_WOCHE: False,
}

#: Beschriftungen für die Einstellungs-Seite (30a/E) — hier, damit Backend und
#: Oberfläche dieselbe Liste benutzen und keine Art vergessen wird.
NOTIFY_LABELS: dict[str, tuple[str, str]] = {
    N1_TAGESORDNUNG: ("Tagesordnung in meinen Gremien",
                      "Sobald ein abonniertes Gremium seine Tagesordnung veröffentlicht"),
    N1_AENDERUNG: ("Änderungen an Tagesordnungen",
                   "Wenn sich eine schon gemeldete Tagesordnung kurz vor der Sitzung noch einmal ändert"),
    N2_THEMA: ("Meine Themen auf einer Tagesordnung",
               "Wenn ein Thema von dir auf den Tisch kommt — auch in Gremien ohne Abo"),
    N3_ERGEBNIS: ("Ergebnisse zu meinen Themen",
                  "Wenn der Rat entschieden hat. Kommt mit dem Protokoll, oft erst Wochen später"),
    N4_VORGANG: ("Verfolgte Vorgänge",
                 "Neue Stationen einer Vorlage, der du folgst — endet automatisch"),
    N5_VORABEND: ("Erinnerung am Vorabend",
                  "18 Uhr, wenn morgen etwas ansteht"),
    N6_WOCHE: ("Wochenüberblick",
               "Sonntag 18 Uhr, alles in einer Nachricht"),
}


#: Unter-Optionen: Anlass → übergeordneter Anlass. Eine Unter-Option wirkt nur,
#: solange ihr Elternteil an ist — wer „Tagesordnung in meinen Gremien"
#: abschaltet, bekommt auch keine Änderungs-Meldungen dazu, egal wie der
#: Unter-Schalter steht. Die Einstellungs-Seite rückt sie entsprechend ein.
NOTIFY_PARENT: dict[str, str] = {
    N1_AENDERUNG: N1_TAGESORDNUNG,
}


#: Zustellweg „gar nicht". Wer das wählt, hört von Ratslotse nichts mehr —
#: keine Meldung, kein Bündel, keine Erinnerung.
KANAL_AUS = "off"


def zustellung_aus(store, owner_id: int) -> bool:
    """Hat dieses Konto Benachrichtigungen ganz abgeschaltet?"""
    try:
        return store.get_delivery_channel(owner_id) == KANAL_AUS
    except AttributeError:
        # Ältere/abgespeckte Store-Doubles in Tests kennen die Abfrage nicht.
        # Im Zweifel weiterschicken: Ein Fehler hier darf niemanden versehentlich
        # stumm stellen — die Umkehrung wäre der teurere Irrtum.
        return False


def gewuenscht(store, owner_id: int, art: str) -> bool:
    """Will dieses Konto diesen Anlass? Unbekannte Arten gelten als gewünscht —
    ein neuer Anlass soll nicht versehentlich still sein.

    Der Zustellweg zählt mit: Bei ``off`` ist die Antwort für jeden Anlass nein.
    Die Prüfung gehört hierher und nicht erst in die Zustellung — sonst füllte
    sich die Warteschlange mit Meldungen, die nie jemand bekommt, und sie
    zählten gegen die Tagesgrenze. Wer sie später wieder anschaltet, bekäme
    dann eine Nachlieferung aus der Zeit, in der er ausdrücklich nichts wollte.
    """
    if zustellung_aus(store, owner_id):
        return False
    prefs = store.get_notify_prefs(owner_id)

    def an(a: str) -> bool:
        return bool(prefs.get(a, NOTIFY_DEFAULTS.get(a, True)))

    # Unter-Optionen hängen an ihrem Elternteil: „Änderungen an Tagesordnungen"
    # ohne „Tagesordnung in meinen Gremien" ergäbe Meldungen über Änderungen an
    # etwas, das man nie bekommen hat.
    eltern = NOTIFY_PARENT.get(art)
    if eltern and not an(eltern):
        return False
    return an(art)


def _jetzt(jetzt: datetime | None = None) -> datetime:
    return (jetzt or datetime.now(timezone.utc)).astimezone(timezone.utc)


def naechstes_fenster(jetzt: datetime | None = None) -> datetime:
    """Frühester Zeitpunkt, zu dem zugestellt werden darf (UTC).

    Innerhalb der Nachtruhe ist das der kommende 7-Uhr-Morgen in Ortszeit,
    sonst der Moment selbst.
    """
    n = _jetzt(jetzt)
    lokal = n.astimezone(ZONE)
    if lokal.hour >= NACHTRUHE_AB:
        ziel = (lokal + timedelta(days=1)).replace(hour=NACHTRUHE_BIS, minute=0, second=0, microsecond=0)
    elif lokal.hour < NACHTRUHE_BIS:
        ziel = lokal.replace(hour=NACHTRUHE_BIS, minute=0, second=0, microsecond=0)
    else:
        return n
    return ziel.astimezone(timezone.utc)


def ist_nachtruhe(jetzt: datetime | None = None) -> bool:
    lokal = _jetzt(jetzt).astimezone(ZONE)
    return lokal.hour >= NACHTRUHE_AB or lokal.hour < NACHTRUHE_BIS


def _tag(zeitpunkt: datetime) -> str:
    """Kalendertag in Ortszeit — die Bezugsgröße der Tagesgrenze."""
    return zeitpunkt.astimezone(ZONE).date().isoformat()


def ist_app_pfad(url: str) -> bool:
    """Zeigt diese Adresse auf eine Seite *dieser* App?

    ``//fremde.example`` und ``https://…`` sind für den Browser Ziele außerhalb;
    der Tap-Handler der App (``lib/push.ts``) navigiert ausschließlich zu
    Pfaden, die mit einem einzelnen Schrägstrich beginnen.
    """
    return bool(url) and url.startswith("/") and not url.startswith("//")


def einreihen(store, owner_id: int, kind: str, titel: str, html: str, url: str,
              jetzt: datetime | None = None, push_text: str | None = None) -> int:
    """Eine Benachrichtigung in die Warteschlange legen. Gibt ihre id zurück.

    ``url`` ist Pflicht (Grenze 4): Antippen muss den Beschluss oder die
    Tagesordnung öffnen, nie nur die Startseite. Und es muss ein **App-Pfad**
    sein: Der Tap-Handler in ``lib/push.ts`` navigiert nur zu Adressen, die mit
    ``/`` beginnen — eine externe Ratsinfo-URL lässt ihn wortlos nichts tun,
    die App bleibt auf der Startseite stehen. Genau so ist es N1 und N2
    passiert; die Prüfung hier ist die Lehre daraus.
    """
    if not url:
        raise ValueError("Jede Benachrichtigung braucht ein Ziel (30a, Grenze 4).")
    if not ist_app_pfad(url):
        raise ValueError(
            f"Ziel muss ein App-Pfad sein (mit / beginnend), war: {url!r}. "
            "Externe Links gehören in den Meldungstext, nicht ins Tap-Ziel."
        )
    # Abgeschaltete Anlässe gar nicht erst einreihen — sonst zählten sie
    # gegen die Tagesgrenze, ohne je zugestellt zu werden.
    if not gewuenscht(store, owner_id, kind):
        return 0
    n = _jetzt(jetzt)
    return store.enqueue_notification(
        owner_id=owner_id, kind=kind, title=titel, body_html=html, url=url,
        created_at=n.isoformat(timespec="seconds"),
        deliver_after=naechstes_fenster(n).isoformat(timespec="seconds"),
        push_text=push_text,
    )


def _buendel(posten: list[dict]) -> tuple[str, str, str, str]:
    """Aus mehreren Fälligen eine Nachricht machen (titel, html, url, push_text).

    Das Tap-Ziel ist bewusst die Übersicht: Ein Bündel hat mehrere Ereignisse,
    also kann es nicht auf eine einzelne Seite zeigen — „Heute" listet sie alle.
    Die Mail selbst baut ``digest_email.buendel``: volle Inhalte je Abschnitt
    statt einer nackten Linkliste. Der Push-Text bleibt trotzdem die Titelzeile
    der Posten — die Vorschau soll die Sachen nennen, nicht den Einleitungssatz
    der Mail.
    """
    from kern import digest_email

    titel = f"{len(posten)} Neuigkeiten aus dem Rat"
    push_text = " · ".join(p["title"] for p in posten)
    if len(push_text) > 180:
        push_text = push_text[:179] + "…"
    return titel, digest_email.buendel(posten), "/dashboard", push_text


def zustellen(store, jetzt: datetime | None = None, stats: dict | None = None) -> int:
    """Fällige Benachrichtigungen ausliefern — unter den Grenzen aus 30a/C.

    Gibt die Zahl der tatsächlich verschickten Nachrichten zurück (ein Bündel
    zählt als eine). Alles, was heute nicht mehr durchpasst, bleibt in der
    Warteschlange und kommt morgen im Bündel mit. Was gar nicht rausging (etwa
    weil der Mailversand streikt), bleibt liegen und wird erneut versucht —
    siehe ``_zustellen_fuer``.
    """
    n = _jetzt(jetzt)
    if ist_nachtruhe(n):
        return 0

    heute = _tag(n)
    jetzt_iso = n.isoformat(timespec="seconds")
    verschickt = 0
    for owner_id in store.owners_with_due_notifications(jetzt_iso):
        # Ein Konto darf den Lauf nicht abbrechen. Vorher riss ein einzelner
        # Fehler (kaputter Datensatz, Ausfall beim Versand) alle nachfolgenden
        # Konten mit — die bekamen an diesem Tag gar nichts mehr.
        try:
            verschickt += _zustellen_fuer(store, owner_id, heute, jetzt_iso)
        except Exception:   # noqa: BLE001 — bewusst breit, s. o.
            logger.exception("Zustellung für Konto %s fehlgeschlagen", owner_id)

    if stats is not None:
        stats["Zugestellte Benachrichtigungen"] = verschickt
    return verschickt


def _zustellen_fuer(store, owner_id: int, heute: str, jetzt_iso: str) -> int:
    """Die fälligen Meldungen *eines* Kontos. Gibt die Zahl der Zustellungen zurück."""
    from kern.delivery import deliver_message

    owner = store.get_owner_delivery(owner_id)
    if not owner:
        return 0
    # Abgeschaltet? Dann ist das hier nicht bloß ein leerer Versand, sondern
    # Altbestand: Meldungen, die vor dem Abschalten eingereiht wurden. Sie
    # werden verworfen statt dreimal vergeblich verschickt — sonst lägen sie
    # noch da, wenn jemand kurz darauf wieder einschaltet.
    if owner.get("delivery_channel") == KANAL_AUS:
        weg = store.drop_pending_notifications(owner_id)
        if weg:
            logger.info("owner %s hat abgeschaltet — %d wartende Meldung(en) verworfen",
                        owner_id, weg)
        return 0
    offen = store.due_notifications(owner_id, jetzt_iso)
    if not offen:
        return 0

    def _abschicken(posten_ids: list[int], html: str, titel: str, url: str, gebuendelt: bool,
                    push_text: str | None = None) -> bool:
        """Einmal zustellen und das Ergebnis verbuchen.

        ``deliver_message`` schluckt Fehler und meldet über den Rückgabewert,
        welche Kanäle tatsächlich bedient wurden. Eine leere Liste heißt: Es ist
        **nichts** rausgegangen. Früher wurde trotzdem ``sent_at`` gesetzt — ein
        Resend-Ausfall ließ Meldungen also lautlos für immer verschwinden.
        """
        channels = deliver_message(owner, html, email_subject=titel, push_url=url,
                                  push_text=push_text)
        if not channels:
            store.bump_notification_attempts(posten_ids)
            logger.warning("owner %s: Zustellung erfolglos, %d Meldung(en) bleiben in der "
                           "Warteschlange", owner_id, len(posten_ids))
            return False
        store.mark_notification_sent(posten_ids, jetzt_iso, bundled=gebuendelt)
        return True

    def _topf(posten: list[dict], schon: int, name: str) -> int:
        """Ein Kontingent abarbeiten: einzeln, solange Platz ist, Rest als Bündel."""
        if not posten:
            return 0
        frei = TAGESGRENZE - schon
        if frei <= 0:
            logger.info("owner %s: Tagesgrenze (%s) erreicht, %d warten auf morgen",
                        owner_id, name, len(posten))
            return 0
        # Passt alles einzeln? Sonst nimmt die letzte freie Zustellung den Rest
        # als ein Bündel mit — „ab der dritten wird gebündelt statt gestapelt".
        einzeln = posten if len(posten) <= frei else posten[: frei - 1]
        rest = posten[len(einzeln):]
        n = 0
        for p in einzeln:
            # Kurztext nur bei Einzelzustellung — ein Bündel baut seinen
            # eigenen Sammel-Text.
            if _abschicken([p["id"]], p["body_html"], p["title"], p["url"], False,
                           push_text=p.get("push_text")):
                n += 1
        if rest:
            titel, html, url, push_text = _buendel(rest)
            if _abschicken([p["id"] for p in rest], html, titel, url, True,
                           push_text=push_text):
                n += 1
        return n

    # Zwei Kontingente statt einem. Ein Bündel enthält damit immer nur Posten
    # EINER Sorte — nur deshalb darf die Tagesgrenze je Sorte nach `kind`
    # zählen (ein gemischtes Bündel wäre in beiden Töpfen eine Zustellung).
    termin = [p for p in offen if p["kind"] in TERMINGEBUNDEN]
    uebrige = [p for p in offen if p["kind"] not in TERMINGEBUNDEN]
    schon_termin = store.notifications_sent_on(owner_id, heute, TERMINGEBUNDEN)
    schon_uebrige = store.notifications_sent_on(owner_id, heute, TERMINGEBUNDEN, ohne=True)
    return (_topf(termin, schon_termin, "termingebunden")
            + _topf(uebrige, schon_uebrige, "übrige"))
