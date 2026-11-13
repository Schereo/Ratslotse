# Plan: Was die Wahlprogramme zu einem Tagesordnungspunkt sagen

Tim, 13.11.2026: Zu einem Tagesordnungspunkt soll sichtbar werden, wie eine
Partei „basierend auf dem Wahlprogramm“ dazu steht — „dann würde man Stellen
aus dem Wahlprogramm zitieren, die man dann den Ratsmitgliedern vorlegen kann“.
Später sollen Parteien ihre Programme selbst hochladen können.

## Was die Seite zeigt

Die Karte „Was die Wahlprogramme dazu sagen“ auf der Punkt-Seite (Schalter
`wahlprogramm-am-punkt`): je Liste im Rat höchstens eine Einordnung —
„Programm spricht dafür“ oder „Programm spricht dagegen“ — mit wörtlichem
Zitat, Seitenzahl und Link zum Programm. Darüber steht das Anliegen des
Punkts, auf das sich „dafür“ und „dagegen“ beziehen; darunter die Listen, in
deren Programm keine passende Stelle gefunden wurde.

**Bewusst nicht:** eine Wahrscheinlichkeit oder Vorhersage der Abstimmung.
Die ließe sich nicht belegen, das Zitat schon. Keine Ampelfarben — Grün und
Rot heißen auf dieser Seite angenommen und abgelehnt.

## Bestand

`kommunalwahl/programme/<slug>.txt`: Volltexte zur Ratswahl 2026 mit
Seitenmarken, Belegkette in `quellen/manifest.json`. Zehn Listen sitzen im
Rat und haben ein Programm (Grüne 13, SPD 12, CDU 7, Linke 7, AfD 5, FDP 2,
Volt 2, BSW 1, Bürger Bündnis 1, Echt Oldenburg 1; die Piraten haben keins).
`council/wahlprogramme.py` schneidet sie in 1.274 Abschnitte, ohne Text zu
verlieren — ein Zitat muss sich wörtlich wiederfinden lassen.

## Kette (`council/programm_bezug.py`)

1. **Suchen**, ohne Modell: je Liste die vier nächsten Abschnitte
   (Einbettungen) plus bis zu zwei, die ein markantes Wort des Titels
   wörtlich tragen.
2. **Einordnen**, GPT-6 Luna, zwei Durchgänge: erst das Anliegen des Punkts
   benennen (ein reiner Bericht hat keins → keine Einordnung), dann je Liste
   dafür / dagegen / nichts, mit wörtlicher Stelle. Die Durchgänge werden
   vereinigt; je Liste bleiben bis zu drei Zitate als Alternativen.
3. **Prüfen im Code**: Das Zitat steht wörtlich im Programm dieser Liste; die
   Seitenzahl kommt aus der Fundstelle.
4. **Prüfen mit GPT-6 Sol**: Trägt das Zitat die Einordnung, stimmt die
   Richtung, ist es für sich allein verständlich, betrifft es den Kern des
   Punkts — und meint es die Maßnahme selbst (`measure`) oder einen
   ausdrücklichen Grundsatz, unter den sie unmittelbar fällt (`principle`)?
   Ein bloß geteiltes Ziel reicht nicht. Ohne Urteil keine Aussage.

Gespeichert je Vorlage (`template_program_stances`), neu nur, wenn sich Punkt
oder Programme ändern. Erzeugt im Cron `vorlagen_dossiers` als dritte Stufe
und für den Bestand mit `--bestand --programme` (Ops-Schritt `programme`).

## Messung (lokaler Abzug, 13.11.2026)

- **Erster Versuch ohne Prüfer**, zwölf politische Punkte: 33 Einordnungen.
  Zur Zweckentfremdungssatzung vier klare Stellen (FDP ausdrücklich dagegen)
  — zu „Preiswerte Wohnungen bei der Klävemann-Stiftung“ aber bei acht von
  neun Listen ein „dafür“, weil jedes Programm günstigen Wohnraum will.
- **Zu strenge Fassung** (nur dieselbe Maßnahme): Die allgemeinen Treffer
  waren weg, aber auch „Steuererhöhungen lehnen wir grundsätzlich ab“ zur
  Grundsteuer C. Daraus die Unterscheidung Maßnahme / Grundsatz.
- **Fertige Kette**, 57 Vorlagen ab 08/2026: 33 mit Anliegen, 8 mit Karte
  (14 %), 19 Einordnungen, 0,002 $ je Vorlage. Von Hand gelesen: 15 klar
  richtig, 4 fragwürdig (ein Zitat ohne eigenen Sinn, zweimal nur eine
  Nebenbedingung getroffen, einmal recht allgemein). Daraufhin zwei weitere
  Prüfkriterien (für sich verständlich, Kern statt Nebenbedingung): Von den
  19 bleiben 14, darunter keins der drei klar fragwürdigen.
- **Stabilität**: Die Ablehnung der Zweckentfremdungssatzung durch die FDP
  fehlte in einem von vier Läufen — der Prüfer ließ „lehnen jede Form von
  Enteignung durch eine Zweckentfremdungssatzung ab“ nicht als Ablehnung der
  Satzung gelten, „Ablehnung von Enteignungen und einer
  Zweckentfremdungssatzung“ eine Seite weiter schon. Seit den
  Alternativ-Zitaten kommt sie in jedem Lauf.

Nicht möglich: der Abgleich mit dem tatsächlichen Abstimmungsverhalten. Die
Protokolle halten je Fraktion nur selten fest, wie sie gestimmt hat
(`council_decision_votes` hat eine Zeile).

## Offen

- Bestand der letzten zwölf Monate auf dev erzeugen und 50 Einordnungen von
  Hand sichten (Tor für den Schalter auf Prod).
- Nach der Abstimmung daneben stellen, wie die Fraktion gestimmt hat — sobald
  die Protokolle das hergeben.
- Upload durch die Parteien: eigene Rolle, Freigabe, Regeln für neue Fassungen.
- Beschluss-Seite und App.
