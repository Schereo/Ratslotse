"""Wer hat einen Tagesordnungspunkt beantragt — und wer nur etwas daran ändern wollen?

Die Protokoll-Extraktion (``council/protocols.py``) füllt ``factions`` je TOP mit
den „Fraktionen, die zu diesem TOP Anträge/Änderungslisten stellten". Ein
Änderungsantrag zu einer Verwaltungsvorlage landet damit AUCH am Hauptbeschluss
— und wurde überall als Antragsteller gelesen. Befund 03.10.2026: Die
Stadionvergabe (Beschluss 20947, Vorlage 26/0396, eine Verwaltungsvorlage) trug
``["CDU"]`` nur wegen des CDU-Änderungsantrags 20948; die Beschluss-Seite zeigte
„Antrag von: CDU", Frag den Rat schrieb „beruhte auf einem CDU-Antrag", und die
Partei-Auswertung zählte die Vergabe als angenommenen CDU-Antrag.

Die Änderungsanträge stehen ohnehin als eigene Zeilen (``kind='subvote'``) mit
ihren Fraktionen da. Deshalb gilt seit 10/2026:

- ``factions`` am **Hauptbeschluss** trägt nur noch, was nicht schon als
  Teilabstimmung desselben TOPs erfasst ist (:func:`main_item_factions`).
  Eine Fraktion, die der Titel selbst nennt („… (CDU-Fraktion vom 08.11.2023)"),
  bleibt immer stehen — sie hat den Punkt beantragt, auch wenn sie ihn danach
  selbst noch ändern wollte.
- Ob der Rest **sicher** der Antragsteller ist, sagt :func:`applicants_named`:
  nur dann, wenn der Titel jede Fraktion nennt. Sonst kann es auch eine
  Änderungsliste sein, die das Protokoll nicht als Teilabstimmung führt — die
  Oberflächen schreiben dann ehrlich „Anträge im TOP von" statt „Antrag von".

Reine Funktionen ohne Datenbank: ``save_protocol`` wendet sie beim Import an,
die Migration einmal auf den Bestand, ``_decision_row`` liest den Titel-Befund.
"""
from __future__ import annotations

from council.parties import _RULES, normalize_party


def _key(faction: str) -> str:
    """Vergleichsschlüssel: kanonische Partei, sonst das kleingeschriebene Label
    („CDU-Fraktion" und „CDU" sind dieselbe Fraktion)."""
    return normalize_party(faction) or faction.strip().lower()


def faction_named_in_title(faction: str, title: str | None) -> bool:
    """Nennt der TOP-Titel diese Fraktion? Für erkannte Parteien über dieselben
    Stichwörter wie ``normalize_party`` („grünen" trifft „Fraktion Bündnis
    90/Die Grünen"), sonst über das ganze Label („Lokale Agenda 21")."""
    low = (title or "").lower()
    if not low or not faction or not faction.strip():
        return False
    canonical = normalize_party(faction)
    if canonical:
        needles = next((n for n, label in _RULES if label == canonical), ())
        return any(n in low for n in needles)
    return faction.strip().lower() in low


def main_item_factions(factions: list[str] | None, title: str | None,
                       subvote_factions: list[str] | None) -> list[str]:
    """``factions`` eines Hauptbeschlusses ohne die Fraktionen, die nur über eine
    eigene Teilabstimmung (Änderungs-/Geschäftsordnungsantrag) dazukamen.

    Idempotent: ein zweiter Lauf auf dem Ergebnis ändert nichts mehr."""
    amended = {_key(f) for f in subvote_factions or [] if f and str(f).strip()}
    out: list[str] = []
    for f in factions or []:
        if not f or not str(f).strip():
            continue
        if _key(f) in amended and not faction_named_in_title(f, title):
            continue
        out.append(f)
    return out


def applicants_named(factions: list[str] | None, title: str | None) -> bool:
    """True, wenn der Titel JEDE Fraktion nennt — dann ist „Antrag von" belegt.
    Ohne Fraktionen False (dann gibt es nichts zu beschriften)."""
    real = [f for f in factions or [] if f and str(f).strip()]
    return bool(real) and all(faction_named_in_title(f, title) for f in real)
