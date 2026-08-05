"""Die Ratslotse-E-Mail: Hülle und Bausteine.

Alles inline gestylt und ohne Layout-Tabellen — das überlebt die meisten
Mail-Programme. Bilder kommen als absolute HTTPS-Adresse von ratslotse.de;
etwas anderes lädt kein Client.

Zum Dunkelmodus: Apple Mail und Outlook färben helle Flächen eigenmächtig um.
Deshalb steht die Marke NICHT als blauer Text auf Weiß (den dreht der Client zu
Blau auf Schwarz und der Kontrast bricht weg), sondern als Bildmarke mit
eigenem Hintergrund — die bleibt in beiden Modi, wie sie ist.
"""
from __future__ import annotations

import html
import os

# Eigene Konstante statt Import aus nwz.notify: notify → delivery →
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

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_BLAU = "#0764a6"      # Hafenblau, --primary
_TEXT = "#0f172a"
_GRAU = "#64748b"
_LEISE = "#94a3b8"
_LINIE = "#e2e8f0"


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


def render_html_email(
    subject: str,
    body_html_or_text: str,
    greeting_name: str | None = None,
    unterzeile: str = "",
) -> str:
    """Eine fertig formatierte Nachricht in die Ratslotse-Hülle setzen.

    ``body_html_or_text`` darf Telegram-Erbe mit ``\\n`` enthalten — deshalb
    steht ``white-space:pre-wrap`` am Textblock. Wer sauberes HTML liefert
    (Absätze, Listen), bekommt es unverändert gerendert.
    """
    greeting = (
        f"<div style='margin-top:22px;font-size:15px;color:{_TEXT}'>Moin {_esc(greeting_name)},</div>"
        if greeting_name else ""
    )
    return (
        f"<div style='max-width:600px;margin:0 auto;padding:24px 16px;font-family:{_FONT};"
        f"color:{_TEXT};background:#ffffff'>"
        f"{kopfzeile(unterzeile)}"
        f"{greeting}"
        f"<div style='margin-top:14px;white-space:pre-wrap;font-size:15px;line-height:1.55'>"
        f"{body_html_or_text}</div>"
        f"<hr style='margin:28px 0 16px;border:none;border-top:1px solid {_LINIE}'>"
        f"<a href='{APP_BASE_URL}' style='color:{_BLAU};text-decoration:none;font-size:14px'>"
        "Zu Ratslotse &rarr;</a>"
        f"<div style='margin-top:14px;color:{_LEISE};font-size:12px;line-height:1.5'>"
        "Du bekommst diese E-Mail, weil du bei Ratslotse die E-Mail-Zustellung aktiviert hast. "
        "Den Kanal änderst du jederzeit unter „Mein Konto“.</div>"
        "</div>"
    )


def _wrap(display_date: str, inner_html: str, topics_url: str) -> str:
    """Hülle der alten Digest-Mail."""
    return (
        f"<div style='max-width:600px;margin:0 auto;padding:24px 16px;font-family:{_FONT};"
        f"color:{_TEXT};background:#ffffff'>"
        f"{kopfzeile(display_date)}"
        f"<div style='margin-top:20px'>{inner_html}</div>"
        f"<hr style='margin:28px 0 16px;border:none;border-top:1px solid {_LINIE}'>"
        f"<a href='{topics_url}' style='color:{_BLAU};text-decoration:none;font-size:14px'>"
        "Themen &amp; Treffer im Web verwalten &rarr;</a>"
        f"<div style='margin-top:14px;color:{_LEISE};font-size:12px;line-height:1.5'>"
        "Du bekommst diese E-Mail, weil du bei Ratslotse die E-Mail-Zustellung aktiviert hast. "
        "Den Kanal änderst du jederzeit unter „Mein Konto“.</div>"
        "</div>"
    )
