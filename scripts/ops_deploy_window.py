"""Unterscheidet das Deploy-Fenster vom echten Ausfall.

Der Anpinger (`ops-erreichbarkeit.yml`) prüft alle zehn Minuten von außen, ob
ratslotse.de antwortet. Er kann aber nicht sehen, WARUM es nicht antwortet —
und die beiden Gründe sehen von außen identisch aus:

* Ein Release deployt gerade. `deploy.yml` setzt dafür die Wartungsbarriere
  `data/.release-maintenance`; solange sie liegt, antwortet `/api/health` mit
  503, und während des Cutovers steht der API-Dienst ganz. Das dauert rund
  anderthalb Minuten und ist der gewollte Zustand.
* Ein Deploy ist abgebrochen und die Barriere steht seither fest. Genau das
  war am 07.09.2026 der Fall: 74 Minuten API-Ausfall, gemerkt erst, als sich
  jemand nicht anmelden konnte. Dafür ist der Anpinger gebaut.

Am 10.09.2026 fiel die Probe in das erste Fenster: Barriere um 20:15:21
gesetzt, alle drei Versuche (20:15:38, 20:16:00, 20:16:22) sahen `/api/health`
503, um 20:16:49 lief die Seite wieder — 85 Sekunden, Vor- und Rauchprobe je
49/49 grün, Deploy grün. Die Alarm-Mail war ein Fehlalarm, und ein Melder, der
Fehlalarme schickt, wird nach dem dritten nicht mehr gelesen.

Der Unterschied steht auf dem Server: **wie alt** die Barriere ist. Frisch
heißt „es deployt gerade", alt heißt „es hängt". Diese Datei trifft aus dem
Alter die Entscheidung — damit sie einen Test hat und nicht als Bedingung in
einer YAML-Zeile steht.

Zwei Eigenschaften sind Absicht:

* **Die Unterdrückung hat eine Obergrenze.** Nach ``LIMIT_SECONDS`` gilt jede
  Barriere als hängend, egal was gerade läuft. Ein abgebrochener Deploy wird
  also höchstens um ein Prüfintervall verzögert gemeldet, nie verschluckt.
* **Sie braucht einen positiven Nachweis.** Ohne lesbares Alter — kein
  Marker, keine SSH-Verbindung, unverständliche Antwort — wird alarmiert. Ein
  Fehler in diesem Pfad fällt damit auf den Zustand vor diesem Skript zurück,
  nicht in die Stille.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

# Ab wann eine stehende Barriere nicht mehr als „Deploy läuft" durchgeht.
# Gemessener Cutover am 10.09.2026: 88 Sekunden. Zehn Minuten sind das Siebenfache
# und liegen weit unter dem Ausfall, den der Anpinger fangen soll (74 Minuten).
LIMIT_SECONDS = 600

# Was der Workflow über SSH zurückbekommt, wenn es kein Alter gibt.
NO_MARKER = "keine"
UNREACHABLE = "unerreichbar"


def evaluate(age: str, findings: str = "",
             limit: int = LIMIT_SECONDS) -> tuple[bool, str]:
    """Unterdrücken? Dazu die Begründung im Klartext.

    ``age`` ist das Alter der Wartungsbarriere in Sekunden, wie der Server es
    gemeldet hat — oder ``keine``/``unerreichbar``. Gerechnet wird auf dem
    Server, damit keine Uhrendifferenz zwischen Runner und VPS eingeht.
    """
    findings = findings.strip()
    betroffen = f" Betroffen:{' ' + findings if findings else ' —'}"

    if age.strip() == UNREACHABLE:
        return False, ("Der Server antwortet nicht auf SSH. Das ist mehr als ein "
                       "Deploy-Fenster." + betroffen)
    if age.strip() == NO_MARKER:
        return False, ("Auf dem Server liegt keine Wartungsbarriere — es deployt "
                       "niemand." + betroffen)
    try:
        seconds = int(age.strip())
    except ValueError:
        # Der Wert selbst gehört NICHT in den Text: Er wird in die Alarm-Mail
        # und über SSH in eine Shell weitergereicht. Im Schritt-Protokoll steht
        # er ohnehin.
        return False, ("Das Alter der Wartungsbarriere kam unlesbar zurück; "
                       "im Zweifel wird gemeldet." + betroffen)
    if seconds < 0:
        return False, (f"Die Wartungsbarriere trägt einen Zeitstempel aus der "
                       f"Zukunft ({seconds} s); im Zweifel wird gemeldet." + betroffen)
    if seconds >= limit:
        return False, (f"Die Wartungsbarriere steht seit {seconds // 60} Minuten. "
                       "Ein Deploy dauert Minuten, nicht so lange — sie hängt." + betroffen)
    return True, (f"Die Wartungsbarriere steht seit {seconds} s: Ein Deploy läuft "
                  f"gerade. Kein Alarm, solange sie jünger als {limit // 60} Minuten "
                  "ist." + betroffen)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--age", required=True,
                   help=f"Alter der Barriere in Sekunden, '{NO_MARKER}' oder "
                        f"'{UNREACHABLE}'")
    p.add_argument("--findings", default="", help="Was der Anpinger nicht erreicht hat")
    p.add_argument("--limit", type=int, default=LIMIT_SECONDS,
                   help="Obergrenze der Unterdrückung in Sekunden")
    a = p.parse_args(argv)

    suppressed, reason = evaluate(a.age, a.findings, a.limit)
    print(("UNTERDRÜCKT: " if suppressed else "ALARM: ") + reason)

    # Die Begründung landet in der Alarm-Mail, und die schickt der Workflow
    # über SSH durch eine einfach gequotete Shell-Zeile. Ein Anführungszeichen
    # darin zerlegte den Befehl; Zeilenumbrüche zerlegten das Ausgabeformat von
    # GitHub Actions. Beides kann hier gar nicht erst entstehen.
    reason = " ".join(reason.replace("'", "").split())

    ziel = os.environ.get("GITHUB_OUTPUT")
    if ziel:
        with Path(ziel).open("a", encoding="utf-8") as fh:
            fh.write(f"suppressed={'1' if suppressed else '0'}\n")
            fh.write(f"reason={reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
