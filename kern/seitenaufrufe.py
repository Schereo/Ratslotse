"""Wie oft welche Seite aufgerufen wurde — ohne zu wissen, von wem.

**Warum es das gibt.** Bis 09/2026 war die anonyme Nutzung von Ratslotse
vollständig unbeobachtet: Der Reverse-Proxy schreibt kein Zugriffslog, im
Frontend steckt keine Analytik. Wer die Startseite ansah, einen geteilten
Beschluss öffnete oder das Changelog las, hinterließ keine Spur. „Wir hatten
viele neue Besucher" war damit ein Gefühl, das sich weder bestätigen noch
widerlegen ließ — messbar war ausschließlich, wer sich **registriert**.

**Warum selbst gebaut.** Dieselbe Begründung wie bei ``kern/fehler.py``:
Plausible, Umami & Co. sind ein weiterer Empfänger für Daten aus fremden
Browsern. In einem Projekt, das bei den Sprachmodellen China-Anbieter
ausschließt und Zero-Data-Retention verlangt, wäre das ein Bruch im Muster.

**Was gezählt wird:** Tag, Seitenmuster, Client, angemeldet ja/nein. Vier
Merkmale, alle grob, alle nur als Summe.

**Was NICHT erhoben wird**, und das ist der wichtigere Teil:

* **Keine Kennung.** Kein Cookie, kein Fingerabdruck, keine ID. Zwei Aufrufe
  derselben Person sind ununterscheidbar von zweien verschiedener.
* **Keine Query.** Sie trägt hier alles Interessante — ``?id=8525`` sagt,
  welchen Beschluss jemand gelesen hat, ``?q=…`` wäre eine Suchanfrage.
  Deshalb kommt sie gar nicht erst mit; der Pfad allein ist stumpf genug.
* **Kein Referrer, kein User-Agent, keine IP.** Der Referrer verriete die
  Herkunft, der User-Agent ist ein guter Teil eines Fingerabdrucks.
* **Kein Konto.** Nur das Ja/Nein „war jemand angemeldet" — das trennt
  Besucher von Nutzer*innen, ohne zu sagen, wer.

**Warum eine Positivliste und keine Maskierung.** ``kern/fehler.py``
maskiert Zahlen im Pfad und lässt den Rest durch; das reicht dort, weil die
Route aus dem eigenen Router kommt. Hier schickt ein **fremder Browser** den
Pfad, und alles, was durchkommt, landet als eigene Zeile in der Tabelle. Ein
unbekannter Pfad wird deshalb nicht repariert, sondern zu ``/andere``
zusammengefasst: Die Tabelle kann damit nur Zeilen enthalten, die hier
aufgezählt sind — weder ein untergeschobener Suchbegriff noch ein Skript, das
sie mit erfundenen Pfaden aufbläht.

``tests/test_seitenaufrufe.py`` hält die Liste gegen den echten Seitenbaum des
Frontends: Eine neue Seite, die hier fehlt, fällt auf, statt still als
„/andere" zu verschwinden.
"""
from __future__ import annotations

import re

#: Die Sammelzeile für alles, was nicht in der Liste steht.
ANDERE = "/andere"

#: Für unbekannte Werte in den beiden dynamischen Segmenten. Ein Listen- oder
#: Themen-Kürzel ist zwar nichts Persönliches, aber es begrenzt die Zeilenzahl.
PLATZHALTER = "{slug}"

#: Jede Seite des Frontends, wie sie in der Adresszeile steht. Detailseiten
#: fehlen hier nicht — sie tragen ihre Kennung in der QUERY
#: (``/council/decision?id=8525``), und die kommt nicht mit. Deshalb ist diese
#: Liste vollständig und trotzdem kurz.
ROUTEN: frozenset[str] = frozenset({
    # öffentlich
    "/", "/login", "/register", "/forgot-password", "/reset-password",
    "/verify-email", "/hilfe", "/impressum", "/datenschutz",
    "/barrierefreiheit", "/changelog", "/g",
    "/kommunalwahl", "/kommunalwahl/check", "/kommunalwahl/methodik",
    "/kommunalwahl/naehe", f"/kommunalwahl/liste/{PLATZHALTER}",
    f"/kommunalwahl/thema/{PLATZHALTER}",
    "/wahlabend",
    # Ratsinhalte (die vier geteilten Detailseiten und das Stöbern)
    "/council", "/council/decision", "/council/sitzung", "/council/thema",
    "/council/person", "/council/ort", "/council/ideen",
    # angemeldete Fläche
    # „Suche", „Sitzungen", „Themen" und „Analyse" sind KEINE eigenen Seiten —
    # sie sind /council mit einem ?tab=, siehe COUNCIL_TABS.
    "/dashboard", "/fragen", "/karte", "/viertel",
    "/topics", "/abos", "/bookmarks", "/quiz", "/quiz/stats",
    "/account", "/admin",
    # Haushalt
    "/haushalt", "/haushalt/bereich", "/haushalt/einnahmen",
    "/haushalt/investitionen", "/haushalt/konzern", "/haushalt/labor",
    "/haushalt/mitreden", "/haushalt/personal", "/haushalt/pflicht",
    "/haushalt/plan-ist", "/haushalt/produkte", "/haushalt/pruefung",
    "/haushalt/schulden", "/haushalt/steuer", "/haushalt/vergleich",
    ANDERE,
} | {f"/council?tab={t}" for t in ("decisions", "sessions", "themen", "analysis")})

#: **Die eine Ausnahme von „Query kommt nie mit".** Suche, Sitzungen, Themen
#: und Analyse sind nicht vier Seiten, sondern EINE (``/council``) mit einem
#: ``?tab=``. Ohne diese Ausnahme fielen die vier meistbenutzten Bereiche der
#: App in eine einzige Zeile zusammen — und ausgerechnet die Frage „welche
#: Bereiche benutzen die Leute?" bliebe unbeantwortet.
#:
#: Erlaubt ist deshalb genau dieser eine Parameter mit genau diesen vier
#: Werten; sie stehen als feste Aufzählung im Code (``TAB_META`` in
#: ``app/(app)/council/view.tsx``) und sagen nichts über eine Person. Jeder
#: andere Parameter — ``?q=``, ``?id=``, ``?ksinr=`` — wird weiterhin
#: abgeschnitten, bevor irgendetwas gespeichert wird.
COUNCIL_TABS: frozenset[str] = frozenset({"decisions", "sessions", "themen", "analysis"})

#: Die beiden Seiten mit einem dynamischen Segment.
_DYNAMISCH: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^/kommunalwahl/liste/[^/]+$"), f"/kommunalwahl/liste/{PLATZHALTER}"),
    (re.compile(r"^/kommunalwahl/thema/[^/]+$"), f"/kommunalwahl/thema/{PLATZHALTER}"),
)

#: Erlaubte Clients — alles andere wird zu ``web``, wie in ``app/clients.py``.
CLIENTS: frozenset[str] = frozenset({"web", "ios", "android", "app"})


def normalisieren(pfad: str | None) -> str:
    """Ein gemeldeter Pfad → ein Muster aus ``ROUTEN``, sonst ``/andere``.

    Nachsichtig gegenüber Schreibweisen, streng gegenüber Inhalten: Ein
    angehängter Schrägstrich (den der statische Export erzeugt) trifft
    dieselbe Zeile, ein unbekannter Pfad landet in der Sammelzeile.
    """
    p = (pfad or "/").strip()
    # Die Query wird abgeschnitten und nicht etwa die ganze Meldung verworfen —
    # verwerfen hieße, dass ein Client-Fehler die Zählung still halbiert.
    # Einzige Ausnahme: `?tab=` auf /council, siehe COUNCIL_TABS.
    tab = ""
    if "?" in p:
        p, _, query = p.partition("?")
        for teil in query.split("&"):
            name, _, wert = teil.partition("=")
            if name == "tab" and wert in COUNCIL_TABS:
                tab = wert
    if "#" in p:
        p = p.split("#", 1)[0]
    if not p.startswith("/"):
        return ANDERE
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/") or "/"
    if p == "/council" and tab:
        return f"/council?tab={tab}"
    if p in ROUTEN:
        return p
    for muster, ziel in _DYNAMISCH:
        if muster.match(p):
            return ziel
    return ANDERE


def client_normalisieren(client: str | None) -> str:
    """``web`` | ``ios`` | ``android`` | ``app`` — nie etwas anderes."""
    c = (client or "").strip().lower()
    return c if c in CLIENTS else "web"
