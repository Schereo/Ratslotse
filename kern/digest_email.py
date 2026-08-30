"""Die Ratslotse-E-Mail: Hülle und Bausteine.

Alles inline gestylt und ohne Layout-Tabellen — das überlebt die meisten
Mail-Programme. Bilder kommen als absolute HTTPS-Adresse von ratslotse.de;
etwas anderes lädt kein Client.

Zum Dunkelmodus: Apple Mail und Outlook färben helle Flächen eigenmächtig um.
Deshalb steht die Marke NICHT als blauer Text auf Weiß (den dreht der Client zu
Blau auf Schwarz und der Kontrast bricht weg), sondern als Bildmarke mit
eigenem Hintergrund — die bleibt in beiden Modi, wie sie ist. Aus demselben
Grund trägt jede Mail oben einen **Mail-Helden**: eine 3D-Lotti-Szene mit
eingebackenem Himmel (``web/frontend/public/mail/held-*.png``, gebaut von
``scripts/mail_helden/bauen.py``) — ein Bild mit eigenem Hintergrund statt
einer Farbfläche, die ein Client umfärben könnte.
"""
from __future__ import annotations

import html
import os

# Eigene Konstante statt Import aus kern.notify: notify → delivery →
# digest_email wäre ein Ring. Beide lesen dieselbe Umgebungsvariable.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://ratslotse.de").rstrip("/")


def absolut(pfad_oder_url: str) -> str:
    """App-Pfad → volle Adresse. In einer E-Mail gibt es keine Basis, gegen die
    ein relativer Link aufgelöst werden könnte. Was schon absolut ist (etwa ein
    Ratsinfo-Link), bleibt unangetastet."""
    ziel = (pfad_oder_url or "").strip()
    if not ziel:
        return APP_BASE_URL
    return f"{APP_BASE_URL}{ziel}" if ziel.startswith("/") else ziel

# Bildmarke (256×256, runde Kachel mit eigenem Hintergrund) — liegt im
# öffentlichen Verzeichnis des Frontends.
LOGO_URL = f"{APP_BASE_URL}/logo-mark.png"

# Innen DOPPELTE Anführungszeichen: Die style-Attribute dieser Datei sind
# einfach gequotet — mit 'Segoe UI' endete das Attribut mitten im Font-Stack,
# und alles dahinter (Farbe, Hintergrund!) fiel je nach Client weg.
_FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif'
_MONO = '"SF Mono",SFMono-Regular,Consolas,"Liberation Mono",Menlo,monospace'
_BLAU = "#0764a6"      # Hafenblau, --primary
_TEXT = "#0f172a"
_GRAU = "#64748b"
_LEISE = "#94a3b8"
_LINIE = "#e2e8f0"
_SEITE = "#eef4f9"     # Seiten-Grund hinter der Karte, nah an der App-Seite
_RAHMEN = "#dbe5ee"    # Kartenrahmen, hsl(208 32% 89%)

# Die Mail-Helden: je Anlass eine 3D-Lotti-Szene (600×210, geliefert in 2×).
# Wer eine Mail baut, wählt hier — nicht mit einem freien Dateinamen.
HELDEN: dict[str, str] = {
    "meldung": "Lotti liest in einem Papierstapel",
    "willkommen": "Lotti und ein Küken winken zur Begrüßung",
    "passwort": "Lotti grübelt unter einem Fragezeichen",
    "freigeschaltet": "Lotti jubelt mit Küken, Krabbe und Konfetti",
    "abschied": "Lotti winkt zum Abschied, ein Herz über ihr",
    "erinnerung": "Lotti erklärt zwei Küken etwas an einer Tafel",
    "feedback": "Lotti hört aufmerksam zu",
    "alarm": "Lotti staunt mit ausgebreiteten Flügeln",
}


def held_bild(held: str | None) -> str:
    """Der Bildstreifen oben in der Karte. ``None`` = Karte ohne Helden."""
    if not held:
        return ""
    alt = HELDEN[held]
    return (
        f"<img src='{APP_BASE_URL}/mail/held-{held}.png' width='598' alt='{_esc(alt)}' "
        "style='display:block;width:100%;height:auto;border:0'>"
    )


def _esc(text: str) -> str:
    return html.escape(text or "")


def _display_date(pub_date: str) -> str:
    d = (pub_date or "").split("-")
    return f"{d[2]}.{d[1]}.{d[0]}" if len(d) == 3 else pub_date


def kopfzeile(unterzeile: str = "") -> str:
    """Bildmarke + Wortmarke, optional mit einer ruhigen zweiten Zeile.

    Die EINE Tabelle in dieser Datei, und zwar mit Grund: Outlook unter Windows
    rendert mit der Word-Engine und kennt weder `flex` noch `gap` — Logo und
    Schriftzug lägen dort untereinander statt nebeneinander. Für zwei Zellen
    nebeneinander ist die Tabelle in E-Mails das robuste Mittel, nicht das
    veraltete.
    """
    zweite = (
        f"<div style='margin-top:3px;color:{_GRAU};font-size:13px'>{_esc(unterzeile)}</div>"
        if unterzeile else ""
    )
    return (
        "<table role='presentation' cellpadding='0' cellspacing='0' border='0'><tr>"
        "<td style='padding-right:12px;vertical-align:middle'>"
        f"<img src='{LOGO_URL}' width='44' height='44' alt='Ratslotse' "
        "style='width:44px;height:44px;border-radius:11px;display:block;border:0'>"
        "</td>"
        "<td style='vertical-align:middle'>"
        f"<div style='font-size:19px;font-weight:700;color:{_BLAU};line-height:1.15'>Ratslotse</div>"
        f"{zweite}"
        "</td></tr></table>"
    )


def knopf(pfad_oder_url: str, beschriftung: str) -> str:
    """DIE eine Handlung der Mail. Bewusst ein gefüllter Block statt eines
    Textlinks: In der Mail ist er der Weg zurück in die App."""
    return (
        f"<div style='margin-top:20px'><a href='{absolut(pfad_oder_url)}' "
        f"style='display:inline-block;background:{_BLAU};color:#ffffff;text-decoration:none;"
        "padding:11px 20px;border-radius:10px;font-size:15px;font-weight:600'>"
        f"{_esc(beschriftung)}</a></div>"
    )


def nebenlink(url: str, beschriftung: str) -> str:
    """Kleiner Verweis nach draußen (Ratsinformationssystem) — bewusst leiser
    als der Knopf: Die Quelle soll erreichbar sein, aber nicht der Hauptweg."""
    return (
        f"<div style='margin-top:10px'><a href='{url}' "
        f"style='color:{_GRAU};text-decoration:underline;font-size:13px'>{_esc(beschriftung)}</a></div>"
    )


def gremium_abo_begruendung(gremium: str, mit_aenderungs_schalter: bool = False) -> str:
    """„Warum bekommst du das?" unter einer Gremien-Meldung (N1).

    Die Zeile gehört in den **Meldungskörper**, nicht in die Mail-Hülle: Nur so
    klebt sie im Bündel an ihrem Abschnitt. Die ``?zeig=``-Parameter heben auf
    der Zielseite genau den Schalter hervor, um den es geht, und überleben als
    Query (anders als ein ``#``-Anker) den Login-Umweg über ``?weiter=``.
    """
    def link(pfad: str, text: str) -> str:
        return (f"<a href=\"{absolut(pfad)}\" style='color:{_GRAU};"
                f"text-decoration:underline'>{_esc(text)}</a>")

    # Seit dem 28.08.2026 haben die Abos eine eigene Seite; vorher waren sie
    # ein Block unter „Meine Themen", den `?zeig=abos` hervorhob. Ältere Mails
    # tragen den alten Link noch — `/topics` leitet ihn deshalb weiter.
    wege = link("/abos", "Gremien-Abos verwalten")
    if mit_aenderungs_schalter:
        wege += " &middot; " + link("/account?zeig=n1_aenderung",
                                    "Nur Änderungs-Meldungen abschalten")
    return (
        f"<div style='margin-top:18px;color:{_GRAU};font-size:12px;line-height:1.6'>"
        f"Du bekommst diese Meldung, weil du das Gremium „{_esc(gremium)}“ abonniert hast."
        f"<br>{wege}</div>"
    )


def liste(zeilen: list[str]) -> str:
    """Aufzählung statt Fließtext. Vorher standen die Tagesordnungspunkte als
    eine einzige, mit Semikolons verkettete Wand — auf dem Telefon zehn Zeilen
    ohne Halt, in denen man den eigenen Punkt nicht wiederfand."""
    if not zeilen:
        return ""
    posten = "".join(
        f"<li style='margin:0 0 8px;padding:0'>{z}</li>" for z in zeilen
    )
    return f"<ul style='margin:14px 0 0;padding-left:20px;font-size:15px;line-height:1.5'>{posten}</ul>"


def buendel(posten: list[dict]) -> str:
    """Mehrere fällige Meldungen als EINE Mail — mit vollem Inhalt je Abschnitt.

    Vorher war das Bündel eine nackte Linkliste aus den Titeln, obwohl jede
    Meldung ihren fertig gebauten Inhalt (Sitzungskopf, Zusammenfassung, Knopf)
    schon in der Warteschlange liegen hatte — der wurde weggeworfen. Jetzt sagt
    die Mail, warum sie bündelt, und jeder Posten steht mit allem da, was seine
    Einzel-Mail auch gehabt hätte.

    ``posten``: Warteschlangen-Zeilen mit ``title``, ``body_html``, ``url``.
    Die Überschrift jedes Abschnitts verlinkt auf das Ziel der Meldung — sie
    ist der Rückweg für Sorten, deren Körper selbst keinen Knopf trägt (N5).
    """
    n = len(posten)
    teile = [
        "<p style='margin:0'>Heute gibt es gleich mehrere Neuigkeiten für dich. "
        "Damit dein Postfach ruhig bleibt, schickt Ratslotse sie nicht einzeln, "
        f"sondern gesammelt — hier sind alle {n} in einer E-Mail:</p>"
    ]
    for p in posten:
        teile.append(
            f"<div style='margin-top:24px;border-top:1px solid {_LINIE};padding-top:18px'>"
            f"<a href=\"{absolut(p['url'])}\" style='color:{_BLAU};font-size:16px;"
            f"font-weight:700;text-decoration:none;line-height:1.3'>{_esc(p['title'])}</a>"
            f"<div style='margin-top:10px'>{p['body_html']}</div>"
            "</div>"
        )
    # Ohne Zeilenumbrüche zusammensetzen: Die Mail-Hülle rendert mit
    # ``white-space:pre-wrap`` — jedes ``\n`` zwischen den Blöcken würde dort
    # zu einer sichtbaren Leerzeile.
    return "".join(teile)


def render_html_email(
    subject: str,
    body_html_or_text: str,
    greeting_name: str | None = None,
    unterzeile: str = "",
    *,
    held: str | None = "meldung",
    kicker: str | None = None,
    titel: str | None = None,
    fusszeile: str | None = None,
) -> str:
    """Eine fertig formatierte Nachricht in die Ratslotse-Hülle setzen.

    Aufbau: Seiten-Grund → Kopfzeile → weiße Karte (Mail-Held oben, Inhalt
    darunter) → Fuß. ``held`` wählt die Lotti-Szene über der Nachricht
    (Schlüssel aus ``HELDEN``, ``None`` = ohne Bild); ``kicker`` und ``titel``
    setzen eine Überschrift über den Text — Benachrichtigungen lassen beides
    weg, weil ihr Körper seinen Kopf schon mitbringt. ``fusszeile`` ersetzt
    das Abmelde-Kleingedruckte (fertiges HTML; ``""`` = gar keins) — die
    Bestätigungs-Mail etwa geht an Konten, die noch gar keine Zustellung
    gewählt haben.

    ``body_html_or_text`` darf Telegram-Erbe mit ``\\n`` enthalten — deshalb
    steht ``white-space:pre-wrap`` am Textblock. Wer sauberes HTML liefert
    (Absätze, Listen), bekommt es unverändert gerendert.
    """
    kopf = ""
    if kicker:
        kopf += (
            f"<div style='font-family:{_MONO};font-size:11px;letter-spacing:.11em;"
            f"text-transform:uppercase;color:{_GRAU}'>{_esc(kicker)}</div>"
        )
    if titel:
        kopf += (
            f"<div style='margin-top:{6 if kicker else 0}px;font-size:21px;font-weight:700;"
            f"color:{_TEXT};line-height:1.3'>{_esc(titel)}</div>"
        )
    greeting = (
        f"<div style='margin-top:{16 if kopf else 0}px;font-size:15px;color:{_TEXT}'>"
        f"Moin {_esc(greeting_name)},</div>"
        if greeting_name else ""
    )
    abstand = 14 if (kopf or greeting) else 0
    return (
        f"<div style='margin:0;padding:28px 12px;background:{_SEITE}'>"
        f"<div style='max-width:600px;margin:0 auto;font-family:{_FONT};color:{_TEXT}'>"
        f"<div style='padding:0 6px 14px'>{kopfzeile(unterzeile)}</div>"
        f"<div style='background:#ffffff;border:1px solid {_RAHMEN};border-radius:18px;overflow:hidden'>"
        f"{held_bild(held)}"
        f"<div style='padding:24px 24px 28px'>"
        f"{kopf}{greeting}"
        f"<div style='margin-top:{abstand}px;white-space:pre-wrap;font-size:15px;line-height:1.55'>"
        f"{body_html_or_text}</div>"
        "</div></div>"
        f"{_fuss(fusszeile)}"
        "</div></div>"
    )


def _fuss(fusszeile: str | None) -> str:
    """Unter der Karte: der Rückweg in die App plus Kleingedrucktes."""
    if fusszeile is None:
        hinweis = _abmelde_hinweis()
    elif fusszeile:
        hinweis = (
            f"<div style='margin-top:10px;color:{_LEISE};font-size:12px;line-height:1.5'>"
            f"{fusszeile}</div>"
        )
    else:
        hinweis = ""
    return (
        "<div style='padding:18px 6px 6px'>"
        f"<a href='{APP_BASE_URL}' style='color:{_BLAU};text-decoration:none;"
        "font-size:14px;font-weight:600'>Zu Ratslotse &rarr;</a>"
        f"{hinweis}"
        "</div>"
    )


def _abmelde_hinweis() -> str:
    """Kleingedruckte Fußzeile mit dem Weg zum Abschalten — „Mein Konto" ist ein
    echter Link auf die Zustellungs-Schalter, kein bloßer Seitenname zum
    Selbst-Suchen (Tims Wunsch 26.08.2026)."""
    return (
        f"<div style='margin-top:10px;color:{_LEISE};font-size:12px;line-height:1.5'>"
        "Du bekommst diese E-Mail, weil du bei Ratslotse die E-Mail-Zustellung aktiviert hast. "
        f"Den Kanal änderst du jederzeit unter <a href='{APP_BASE_URL}/account?zeig=zustellung' "
        f"style='color:{_LEISE};text-decoration:underline'>„Mein Konto“</a>.</div>"
    )
