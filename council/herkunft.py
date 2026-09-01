"""Woher eine gespeicherte Zahl stammt — ein Format für alle Finanz-Schichten.

Der Haushalts-Bereich trug seine Herkunft bis 08/2026 in drei verschiedenen
Schreibweisen: ``source_label``/``source_url`` in den einen Tabellen,
``label``/``url`` in der nächsten, ``source_url`` in den vier ältesten. Und
überall fehlte dasselbe: die Fundstelle **im** Dokument, die bestandene
Rechenprobe und ein Anker, der einen Dokumentwechsel überlebt.

Warum eine eigene Tabelle statt Spalten je Tabelle
---------------------------------------------------
Beide Wege standen zur Wahl. Entschieden hat der Blick auf die Schichten, die
noch kommen — Konzernabschluss, Beteiligungsbericht, Finanzhaushalt,
Stellenplan, Schuldenzeitreihe:

1. **Eine Tabelle trägt Zeilen aus verschiedenen Dokumenten.** Bei den
   Beteiligungen ist das der Normalfall: Dieselbe Kennzahl steht im
   Konzernabschluss, im Einzelabschluss der Gesellschaft und im
   Beteiligungsbericht — mit verschiedenen Stichtagen und
   Konsolidierungsstufen. Als Spaltensatz ließe sich das zwar auch je Zeile
   führen; als eigener Datensatz ist es aber **eine ID**, und die Frage „ist
   das dieselbe Herkunft?" beantwortet ein Vergleich statt neun Vergleichen.
2. **Ein neues Herkunftsfeld darf nicht neun ALTER TABLE kosten.** Käme
   morgen die Konsolidierungsstufe dazu, wäre das hier genau eine Spalte an
   genau einer Stelle — und alle Schichten hätten sie sofort.
3. **Wiederholung.** Ein Jahresabschluss-Jahrgang schreibt rund 200 Zeilen
   Ergebnisrechnung, alle aus demselben Dokument, an derselben Fundstelle,
   mit derselben Probe. Als Spalten wäre das dieselbe Angabe 200-mal.

Der Preis ist ein Join. Er fällt auf einer Tabelle mit einigen hundert Zeilen
nicht ins Gewicht, und die Lesewege des Bereichs holen ohnehin ganze
Jahrgänge auf einmal.

Was die alten Spalten angeht: Sie **bleiben**. ``source_label``,
``source_url`` und ``source_url`` stehen weiter dort, wo sie standen, und
werden weiter aus derselben Angabe gefüllt. Sie zu entfernen hieße, neun
Tabellen neu zu schreiben — darunter vier, deren Inhalt nur über einen
Download von oldenburg.de wiederzubeschaffen wäre. Der Gewinn wäre kosmetisch,
das Risiko echt. ``herkunft_id`` ist ab jetzt der kanonische Weg; die alten
Spalten sind die Rückfallebene, die kein Lesepfad zu ändern zwingt.

Was hier **nicht** hingehört
-----------------------------
Was von Zeile zu Zeile schwankt, bleibt an der Zeile. Die
Prüfungsfeststellungen führen ihre Textziffer und ihre Seite selbst — das ist
ihre Fundstelle, und sie ist je Feststellung eine andere. Die Herkunft
beschreibt das **Dokument und den Abschnitt**, aus dem ein Lauf gelesen hat,
nicht die Zeile darin.

Für einen neuen Parser
-----------------------
Drei Dinge, mehr nicht (ausführlich in ``docs-site/.../haushalt.md``):

1. Eine :class:`Herkunft` bauen — ``kind`` und ``probe`` sind Pflicht, alles
   andere so vollständig, wie das Dokument es hergibt.
2. Sie an die ``save_*``-Methode des Stores geben. Die trägt sie ein und
   verknüpft die Zeilen (``store.merke_herkunft``).
3. Die Zieltabelle in :data:`HERKUNFT_TABELLEN` eintragen. Damit bekommt sie
   ihre ``herkunft_id``-Spalte, und ``store.herkunft_luecken()`` meldet ab
   sofort jede Zeile darin, die ohne Herkunft geschrieben wurde.

Vergessen ist damit nicht unmöglich, aber laut: Eine :class:`Herkunft` ohne
Probe lässt sich gar nicht erst bauen (``ValueError``), und eine Tabelle, die
ihre ``herkunft_id`` nicht füllt, steht nach jedem Lauf im Protokoll.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

#: Woher ein Dokument stammt. Absichtlich dieselben Werte wie
#: ``Finanzquelle.herkunft`` in ``council/finanzquellen.py`` — dort steht, ob
#: der Cron eine Schicht selbst nachziehen darf, hier, was ein Leser über die
#: Zahl vor sich wissen muss.
ARTEN: dict[str, str] = {
    "ris": "Anlage zu einer Ratsvorlage im Bürgerinformationssystem",
    "opendata": "Datensatz des Open-Data-Portals der Stadt Oldenburg",
    "city": "Veröffentlichung auf oldenburg.de",
    # Der dritte Fall, und der einzige, der nicht von der Stadt kommt: eine
    # Landesbehörde. Er ist der Grund, warum ein Städtevergleich überhaupt
    # tragfähig ist — dieselbe Kennzahl für alle Gemeinden, nach demselben
    # Gesetz gerechnet, von einer Stelle. Der Cron lädt hier nichts nach; die
    # beiden Quellen erscheinen einmal jährlich und werden von Hand geholt
    # (s. council/staedtevergleich.py).
    "lsn": "Statistischer Bericht des Landesamts für Statistik Niedersachsen",
}

#: Der ausdrückliche Verzicht. Keine Quelle darf ohne Angabe gespeichert
#: werden — aber manche tragen schlicht keine Rechenprobe, und das zu sagen
#: ist eine Angabe. Die Portal-CSVs sind der Fall: eine Zeile je Jahr, keine
#: Summe, gegen die sich etwas prüfen ließe.
UNGEPRUEFT = "ungeprueft"

#: Der Altbestand. Zeilen, die vor der Vereinheitlichung geschrieben wurden,
#: **sind** durch eine Probe gegangen — welche, steht nicht dabei. Diese
#: Marke sagt genau das, statt eine zu behaupten. Sie ist nichts, was ein
#: Parser je setzen sollte: Sie entsteht ausschließlich beim Nachrüsten
#: (``CouncilStore._migrate_herkunft``) und verschwindet, sobald der Jahrgang
#: das nächste Mal eingelesen wird.
UNBEKANNT = "unbekannt"

#: Die Rechenproben, die der Bereich kennt — Name → was sie zeigt.
#:
#: Der Text ist für Leserinnen geschrieben, nicht für uns: Er landet über die
#: API im Beleg-Chip und beantwortet dort die Frage „warum soll ich das
#: glauben?". Wer eine neue Probe baut, trägt sie hier ein; ein unbekannter
#: Name fliegt beim Bauen der :class:`Herkunft` auf.
PROBEN: dict[str, str] = {
    # Die Änderungslisten zum Haushalt (council/aenderungslisten.py) — was der
    # Entwurf im Verfahren noch geändert wurde. Zwei Proben aus der
    # „Zusammenstellung der Veränderungen“ am Ende jedes Dokuments.
    "aenderungsliste_summen":
        "Jede Zeile der Zusammenstellung geht in sich auf: Erträge minus "
        "Aufwendungen ist der gedruckte Saldo.",
    "aenderungsliste_positionen":
        "Die Summe der gelesenen Einzelpositionen trifft je Planjahr die "
        "Zusammenstellung — die Zeile, die dieses Dokument summiert, oder "
        "bei kumulierten Beschluss-Dateien Endsumme minus Entwurf. Stünde "
        "ein Betrag in der falschen Spalte, ginge genau das nicht auf.",
    "aenderungsliste_erlaeuterungen":
        "Die Erläuterungs-Texte folgen den gedruckten Tabellenlinien: Jeder "
        "Absatz steht in dem Zeilenband, in dem auch seine Position steht — "
        "zugeordnet wird über die Geometrie des Dokuments, nicht über "
        "Abstands-Schätzung; ohne eindeutiges Band bleibt das Feld leer.",
    "aenderungsliste_fhh_zeilen":
        "Jede Zeile des Finanzhaushalts rechnet sich selbst vor: Soll laut "
        "Entwurf plus Einzahlung plus Auszahlung ergibt das neue Soll. Diese "
        "Probe läuft an JEDER Position, nicht nur an der Schlusssumme — "
        "stünde ein Betrag eine Spalte daneben, ginge sie nicht auf.",
    "aenderungsliste_urheber":
        "Wo das Dokument je Position einen Vorschlagenden nennt, wird die "
        "Zuordnung gerechnet: Die Summe der Positionen jedes Urhebers muss "
        "seine eigene Zeile in der Zusammenstellung treffen. Geht auch nur "
        "eine Gruppe nicht auf, gilt das Dokument als ungelesen.",
    # Die Gebührenbedarfsberechnung (council/gebuehren.py) — die Rechnung, aus
    # der die Abfall- und Straßenreinigungsgebühren entstehen. Zwei Proben,
    # beide aus dem Dokument selbst und voneinander unabhängig.
    "gebuehren_kaskade":
        "Die Kalkulationskosten minus alle Abzüge, die das Dokument selbst "
        "benennt, ergeben die Kosten, die durch Gebühren zu decken sind.",
    "gebuehren_division":
        "Diese Kosten, geteilt durch die Bezugsmenge, ergeben die gedruckte "
        "Gebühr — Menge und Gebühr stehen an anderer Stelle als die Kaskade.",
    "gebuehrensaetze_anzahl":
        "Anlage 4 enthält jede der zwölf ausdrücklich benannten Tarifarten "
        "genau einmal — eine fehlende oder zusätzliche Zahl verwirft die Zeile.",
    "gebuehrensaetze_eckwerte":
        "Die Gebühr je Mg und die Straßenreinigungsgebühr aus Anlage 4 stimmen "
        "mit den getrennt errechneten Vorschlägen in Anlagen 1 und 3 überein.",
    "gebuehrensaetze_vorjahresvergleich":
        "Vorschlag und Vorjahressatz ergeben die in Anlage 4 gedruckte "
        "prozentuale Veränderung — für jede der zwölf Tarifarten nachgerechnet.",
    # Die Haushaltssatzung (council/haushaltssatzung.py) — der Rahmen, den der
    # Rat dem Haushaltsplan gibt: Kreditermächtigung, Dispo-Höchstbetrag,
    # Verpflichtungsermächtigungen und der Finanzhaushalt als Ganzes.
    "satzung_finanzhaushalt":
        "Die Satzung nennt unter § 1 die drei Einzahlungs- und die drei "
        "Auszahlungszeilen des Finanzhaushalts einzeln — und darunter noch "
        "einmal ihre Summe. Beide Summen sind nachgerechnet.",
    "satzung_hebesatz":
        "Der Hebesatz aus § 5 der Satzung steht auch in Tabelle 1105 des "
        "Statistischen Jahrbuchs: zwei Dokumente aus zwei Häusern.",
    # Die Kernzahl aus dem Beschlusstext, bestätigt durch die Anlage
    # (council/wirtschaftsplan_kernzahl.py) — die einzige Probe des Bereichs,
    # die über ZWEI Dokumente geht.
    "wirtschaftsplan_kernzahl":
        "Die Zahl, über die der Rat abstimmt, steht im Beschlusstext der "
        "Vorlage — und dieselbe Zahl steht in der beigefügten Anlage. Zwei "
        "getrennte Dokumente, unabhängig gesetzt.",
    # Der zweite Satz über Geld in derselben Vorlage: die Investitionen des
    # Vermögensplans, geprüft an ihrer eigenen Finanzierung.
    "wirtschaftsplan_investitionen":
        "Der Beschlusstext nennt die Investitionen des Vermögensplans und "
        "gleich daneben, woraus sie finanziert werden — Kreditaufnahme und "
        "eigene Mittel ergeben zusammen die Summe.",
    # Die Erfolgspläne aus den Anlagen (council/wirtschaftsplan_tabelle.py) —
    # für die Betriebe, die im Beschlusstext keine Zahl nennen.
    "wirtschaftsplan_spalten":
        "In jeder Spalte des Erfolgsplans gilt die Rechnung des Dokuments: "
        "Erträge − Aufwendungen = Ergebnis. Geprüft werden alle Spalten, "
        "gespeichert nur das Planjahr.",
    "wirtschaftsplan_prosa":
        "Der Satz unter der Tabelle nennt dieselben beiden Summen wie die "
        "Planspalte — zwei unabhängig gesetzte Stellen desselben Dokuments.",
    # Die Wirtschaftspläne der Eigenbetriebe (council/wirtschaftsplan.py) —
    # die einzige Schicht, deren Quelle die VORLAGE ist und keine Anlage.
    "wirtschaftsplan_erfolgsplan":
        "Der Beschlusstext rechnet sich selbst vor: Erträge − Aufwendungen − "
        "steuerliche Aufwendungen = Jahresergebnis. Über alle acht Jahrgänge "
        "auf den Cent.",
    "wirtschaftsplan_jahr":
        "Das Haushaltsjahr steht im Beschlusstext und im Titel der Vorlage — "
        "beide müssen dasselbe sagen. Eine Vorlage vom Oktober beschließt das "
        "FOLGENDE Jahr.",
    "summenzeile":
        "Die Teilbeträge ergeben die Summenzeile des Dokuments (Toleranz 1 %).",
    "strukturprobe":
        "Innerhalb der Ergebnisrechnung geht die Rechnung des Dokuments auf: "
        "Erträge (Posten 12) − Aufwendungen (Posten 20) = ordentliches Ergebnis "
        "(Posten 21), in Plan und Ist.",
    "summenprobe":
        "Die Teilhaushalte summieren sich auf die Gesamtrechnung desselben "
        "Dokuments — sonst wäre für einen Teilhaushalt die falsche, in sich "
        "stimmige Tabelle gelesen worden.",
    "vorjahreskette":
        "Das Ergebnis eines Jahres steht im Jahresabschluss des Folgejahres "
        "noch einmal als Vorjahreswert und stimmt damit überein.",
    # Finanzrechnung der Kernverwaltung, Abschnitt 4.1 desselben
    # Jahresabschlusses (council/finanzberichte.py). Die erste ist die
    # Pflicht-Probe: Sie deckt jede Zahl ab, die auf der Seite steht. Die
    # beiden anderen decken je eine Spalte bzw. den Schwanz der Tabelle und
    # kosten, wenn sie reißen, nur diesen Teil.
    "finanzkaskade":
        "Die Finanzrechnung rechnet sich selbst vor, und jede Stufe hängt an "
        "der vorigen: Die Einzahlungsarten ergeben die Summe der Einzahlungen, "
        "die Auszahlungsarten die der Auszahlungen, beide zusammen den Saldo — "
        "für die laufende Verwaltung und für die Investitionen, und beide "
        "Salden zusammen den Finanzmittelsaldo. Geprüft im Ist wie im Ansatz.",
    "finanz_ermaechtigungen":
        "Auch die übertragenen Ermächtigungen aus Vorjahren addieren sich in "
        "jedem Block auf die Summenzeile, die dieselbe Tabelle daneben "
        "ausweist. Wo das nicht aufgeht, fehlt die Spalte ganz.",
    "finanz_bestandskette":
        "Die Kasse schließt: Anfangsbestand plus Finanzmittelveränderung plus "
        "die haushaltsunwirksamen Vorgänge ergeben den Endbestand, den das "
        "Dokument ausweist.",
    "kassenkette":
        "Der Kassenbestand am Jahresende steht im Jahresabschluss des "
        "Folgejahres noch einmal als Anfangsbestand — zwei Dokumente, "
        "dieselbe Zahl.",
    # Bilanz der Stadt, Abschnitt 2.1 desselben Jahresabschlusses
    # (council/bilanz.py). Die erste ist die Pflicht-Probe; ohne sie kommt
    # kein Stichtag herein. Die letzte ist die stärkste — sie stellt zwei
    # getrennt gelesene Tabellen gegeneinander.
    "bilanz_ausgleich":
        "Die Bilanz geht auf: Was die Stadt hat, und was davon wem zusteht, "
        "ergeben auf den Cent denselben Betrag. Eine Bilanz, bei der das "
        "nicht stimmt, ist keine.",
    "bilanzsumme_gedruckt":
        "Die Bilanzsumme, die das Dokument unter die Tabelle druckt, ist "
        "dieselbe, die sich aus den einzelnen Posten ergibt — eine dritte "
        "Bestätigung neben den beiden Seiten.",
    "rueckstellungs_gliederung":
        "Die Rückstellungen für Pensionen und die für Beihilfe ergeben "
        "zusammen genau den Sammelposten, den die Bilanz eine Zeile darüber "
        "ausweist. Damit steht fest, welche der beiden Zahlen gemeint ist, "
        "die im Umlauf sind.",
    "bilanz_vorjahreskette":
        "Jede Bilanz führt zwei Stichtage nebeneinander. Der ältere davon "
        "steht im Jahresabschluss des Vorjahres noch einmal als aktueller "
        "Stand — zwei getrennt gelesene Dokumente, für jeden Hauptposten "
        "dieselbe Zahl.",
    "bilanz_kassenprobe":
        "Der Kassenbestand steht zweimal im selben Heft, zehn Seiten "
        "auseinander und in zwei verschieden gebauten Tabellen: als "
        "Bilanzposition „Liquide Mittel“ und als „Endbestand an "
        "Zahlungsmitteln“ der Finanzrechnung. Beide werden getrennt gelesen "
        "und stimmen überein.",
    "bilanz_erlaeuterung":
        "Der Anhang erläutert die Bilanz Position für Position. Dass jeder "
        "Text an der Position steht, zu der er gehört, ist hier geprüft: Die "
        "neun Abschnitte tragen die Namen der neun Hauptposten, in genau "
        "deren Reihenfolge.",
    "abweichungstext":
        "Die Erläuterung nennt ihre Abweichung doppelt, als Betrag und als "
        "Prozentsatz; beide passen zu der Tabellenzeile, die derselbe "
        "Jahrgang für diesen Posten führt.",
    "produktzeile":
        "Je Produktzeile: Erträge − Aufwendungen = ordentliches Ergebnis.",
    # Gesamtergebnishaushalt der Haushaltspläne (council/ergebnishaushalt.py).
    # Die zweite Probe ist die wichtigere: Sie entscheidet, welche der sechs
    # Spalten als beschlossener Ansatz gespeichert wird.
    "ergebnishaushalt_summenzeilen":
        "Der Haushaltsplan rechnet sich in jeder seiner sechs Jahresspalten "
        "selbst vor: Die Einnahmearten ergeben die Summe der Erträge, die "
        "Ausgabearten die Summe der Aufwendungen, und beide zusammen das "
        "ausgewiesene Ergebnis.",
    "ergebnishaushalt_planspalte":
        "Das Jahr, über das der Rat wirklich entscheidet, ist im Plan "
        "hervorgehoben und steht in jeder Zeile ein zweites Mal. Diese "
        "Wiederholung zeigt in allen gelesenen Zeilen auf dieselbe Spalte — "
        "damit ist der beschlossene Ansatz von der mittelfristigen "
        "Finanzplanung getrennt, ohne sich auf die Reihenfolge zu verlassen.",
    # Stellenplan (council/stellenplan.py). Vier Proben, die zusammen die
    # Tabelle tragen — Teil B hat die vierte nicht, weil er nur eine Gruppe
    # führt und deren Summe zugleich die Gesamtsumme ist.
    "stellenplan_spaltenprobe":
        "Der Stellenplan nummeriert seine Spalten selbst, auf jeder Seite "
        "neu — und nennt überall dieselbe Zahl. Damit steht fest, welche "
        "Spalte die geplanten Stellen sind und welche die besetzten.",
    "stellenplan_gruppensummen":
        "Die einzelnen Amtsbezeichnungen ergeben die Summe ihrer Gruppe, die "
        "der Plan selbst ausweist („Summe Laufbahngruppe 2“) — und zwar in "
        "jeder Spalte, nicht nur bei den geplanten Stellen.",
    "stellenplan_besetzung":
        "Die Rechnung hinter den unbesetzten Stellen geht auf: besetzte plus "
        "unbesetzte Stellen ergeben genau die Zahl der Stellen, die der Plan "
        "für den Stichtag ausweist.",
    "stellenplan_gesamtsumme":
        "Die Gruppensummen ergeben zusammen die Gesamtzeile des Plans. Der "
        "Stellenplan führt sie zweimal hintereinander; beide stimmen.",
    "legende_und_verzeichnis":
        "Die Randmarke der Feststellung steht in der Legende dieses Berichts, "
        "ihre Textziffer in seinem Inhaltsverzeichnis.",
    "eingangsformel":
        "Der Bericht nennt in seiner Eingangsformel die Kernverwaltung als "
        "geprüfte Stelle — nicht einen Eigenbetrieb oder eine Stiftung.",
    "textextrakt":
        "Der Buchstabenanteil des Volltexts belegt, dass das PDF eine "
        "Zeichenzuordnung mitbringt und kein Glyphen-Salat ist.",
    # Konzern Stadt Oldenburg (council/konzernabschluss.py). Die ersten drei
    # stehen im Gesamtabschluss nebeneinander und sichern ihn gemeinsam ab:
    # Erst wenn alle drei aufgehen, kommt ein Jahrgang herein.
    "konzern_ergebnisprobe":
        "In der Ergebnisrechnung des Konzerns geht die Rechnung des Dokuments "
        "auf: Summe der ordentlichen Erträge − Summe der ordentlichen "
        "Aufwendungen = ordentliches Ergebnis.",
    "konzern_ausserordentlich":
        "Dasselbe für die einmaligen Posten: außerordentliche Erträge − "
        "außerordentliche Aufwendungen = außerordentliches Ergebnis.",
    "konzern_gesamtergebnis":
        "Beide Teile zusammen ergeben das ausgewiesene Gesamtjahresergebnis — "
        "die Tabelle ist also von oben bis unten in sich consistent.",
    "konzern_traegersumme":
        "Die einbezogenen Betriebe und Gesellschaften ergeben zusammen mit der "
        "Verrechnung untereinander genau die Summe, die der Bericht ausweist.",
    "konzern_querprobe":
        "Dieselbe Summe steht an zwei Stellen des Berichts — in der "
        "Ergebnisrechnung des Konzerns und in der Aufstellung, wer wie viel "
        "beiträgt. Beide stimmen überein.",
    "konzern_zeilenprobe":
        "Je Betrieb nennt der Bericht Jahr, Vorjahr und Veränderung; die "
        "Veränderung ist die Differenz der beiden anderen.",
    # Städtevergleich aus der amtlichen Statistik (council/staedtevergleich.py).
    "lsn_zweijahresueberlappung":
        "Jede Ausgabe des Finanzausgleichs nennt zwei Jahre nebeneinander. Das "
        "ältere davon steht in der Ausgabe des Vorjahres noch einmal — beide "
        "stammen aus verschiedenen Veröffentlichungen und stimmen trotzdem für "
        "jede der 403 Gemeinden überein.",
    "lsn_hebesatzprobe":
        "Die Rechnung, die eine Grundsteuer oder Gewerbesteuer ausmacht, geht "
        "auf: Grundbetrag mal Hebesatz ergibt das Aufkommen, das die Tabelle "
        "ausweist. Bei der Gewerbesteuer zusätzlich, dass nach Abzug der "
        "Umlage genau der Betrag bleibt, den wir zeigen.",
    # Gewerbesteuerstatistik des LSN (council/gewerbesteuerstatistik.py). Drei
    # Proben, die aufeinander aufbauen: die Rechnung in der Zeile, dieselbe
    # Zeile im zweiten Blatt, und ein Wert daraus gegen ein Dokument aus einem
    # anderen Haus.
    "gewst_summenprobe":
        "Jeder Fall ist entweder eine reine Festsetzung oder eine Zerlegung. "
        "Beide Gruppen ergeben zusammen genau die Gesamtzahl, die dieselbe "
        "Zeile ausweist — für die Betriebe, für die zahlenden darunter und "
        "für den Steuermessbetrag.",
    "gewst_blattprobe":
        "Derselbe Bericht führt die Stadt zweimal: in der Tabelle der "
        "kreisfreien Städte und in der aller Gemeinden. Beide sind "
        "verschieden gebaut und nennen trotzdem dieselben Zahlen.",
    "gewst_hebesatzprobe":
        "Der Hebesatz, den das Landesamt seiner Statistik nachrichtlich "
        "beilegt, steht auch im Statistischen Jahrbuch der Stadt — zwei "
        "Häuser, dieselbe Zahl für dasselbe Jahr.",
    # Die drei Komponenten des Finanzausgleichs (council/steuerkraft.py). Die
    # zweite ist die stärkere: Sie prüft nicht innerhalb eines Dokuments,
    # sondern eine Landesbehörde gegen die Bücher der Stadt.
    "kfa_komponentenprobe":
        "Die drei Bestandteile der Zuweisung — für Gemeindeaufgaben, für "
        "Kreisaufgaben und für die übertragenen staatlichen Aufgaben — ergeben "
        "nach Abzug der Finanzausgleichsumlage genau den Nettobetrag, den "
        "dieselbe Zeile ausweist. Für alle acht kreisfreien Städte und beide "
        "Jahre, die eine Ausgabe führt.",
    "kfa_jahrbuchabgleich":
        "Was das Land als Zuweisung festsetzt, taucht in den Büchern der Stadt "
        "wieder auf: Tabelle 1103 des Statistischen Jahrbuchs nennt unter "
        "„Finanzzuweisungen“ für 2023 und 2024 auf das Tausend genau denselben "
        "Betrag. Für 2025 stehen 79.785 gegen 79.787 Tausend Euro — dort ist "
        "das Rechnungsergebnis der Stadt noch vorläufig.",
    "lsn_dreijahresmittel":
        "Der ausgewiesene Dreijahresdurchschnitt ist tatsächlich das Mittel "
        "der drei Jahreswerte daneben — und geteilt durch die Einwohnerzahl, "
        "die dieselbe Zeile mitliefert, ergibt er den Pro-Kopf-Wert, den die "
        "Tabelle nennt.",
    # Investitionen aus dem Finanzhaushalt (council/investitionen.py). Die
    # einzige Portal-CSV des Bereichs, die eine Probe mitbringt.
    "investitionen_summenzeile":
        "Die Teilhaushalte ergeben zusammen genau die Summenzeile, die dieselbe "
        "Datei ausweist — in beiden Spalten, bei den Einzahlungen wie bei den "
        "Auszahlungen.",
    # Die Ist-Investitionen aus den Tabellen 1107/1107-1 des Statistischen
    # Jahrbuchs (council/investitionen_ist.py). Die einzige Probe, die diese
    # Tabelle hergibt — es gibt keine Pro-Kopf-Spalte, keine zweite Ausgabe und
    # keinen Spiegel im Open-Data-Portal, gegen die sich gegenprüfen ließe. Was
    # sie reißt, wird deshalb ganz verworfen und nicht halb übernommen.
    "investitionen_ist_zeilensumme":
        "Die Auszahlungsarten des Jahres — Baumaßnahmen, Grundstücke, "
        "bewegliches Vermögen und die übrigen — ergeben zusammen genau den "
        "Betrag, den dieselbe Zeile daneben als Summe ausweist.",
    # Investitionsprogramm, Anlage 004 des Haushaltsplans
    # (council/investitionsprogramm.py). Drei Proben, die das Dokument selbst
    # rechnet; erst wenn alle drei aufgehen, kommt ein Jahrgang herein. Die
    # zweite ist die stärkste — sie verbindet zwei Stellen, die siebzig Seiten
    # auseinanderliegen.
    "investitionsprogramm_abschnitt":
        "Die einzelnen Vorhaben eines Teilhaushalts ergeben zusammen genau die "
        "Gesamtsumme, die das Investitionsprogramm am Ende seines Abschnitts "
        "ausweist.",
    "investitionsprogramm_wiederholung":
        "Jede dieser Teilhaushaltssummen steht ein zweites Mal im Dokument — "
        "rund siebzig Seiten früher, in der Übersicht über alle Teilhaushalte. "
        "Beide Stellen stimmen überein.",
    "investitionsprogramm_kopftabelle":
        "In dieser Übersicht ergeben die Teilhaushalte zusammen genau die "
        "Gesamtsumme des Investitionsprogramms.",
    # Schuldenzeitreihe aus Tabelle 1108 des Statistischen Jahrbuchs
    # (council/schulden.py). Die zweite ist die stärkere: Ihr Divisor kommt aus
    # einer anderen Veröffentlichung der Stadt, und 2022 ist sie die einzige,
    # die den Jahrgang noch trägt.
    "schulden_summenzeile":
        "Die vier Schuldenarten der Tabelle — Kreditmarkt, öffentliche "
        "Sondermittel, Gebietskörperschaften und Eigenbetriebe — ergeben "
        "zusammen genau die Summe, die daneben ausgewiesen ist.",
    "schulden_prokopf":
        "Die ausgewiesene Gesamtschuld, geteilt durch die Einwohnerzahl aus "
        "dem Open-Data-Datensatz der Stadt, ergibt den Betrag je Einwohner*in, "
        "den dieselbe Zeile nennt. Beide Seiten stammen aus verschiedenen "
        "Veröffentlichungen und beziehen sich auf denselben Stichtag.",
    # Die lange Ausgabenreihe aus Datensatz 1102 (council/ausgabenreihe.py).
    # Drei Proben, und sie greifen gestaffelt: Die erste trägt jede der 54
    # Zeilen, die zweite die 24 Jahre mit zwei Quellen, die dritte die acht mit
    # Jahresabschluss. Was ein Jahrgang bestanden hat, steht an seiner Zeile.
    "ausgabenreihe_prokopf":
        "Die Tabelle rechnet sich selbst vor: Der Betrag des Jahres, geteilt "
        "durch die Einwohnerzahl derselben Zeile, ergibt den Betrag je "
        "Einwohner*in, den dieselbe Zeile daneben ausweist. Diese Rechnung "
        "trägt jedes Jahr der Reihe — auch die dreißig, für die es keine "
        "zweite Quelle gibt.",
    "ausgabenreihe_zweitquelle":
        "Dieselbe Reihe steht an zwei Stellen: im Statistischen Jahrbuch der "
        "Stadt und im Open-Data-Portal. Beide werden getrennt gelesen, und für "
        "dieses Jahr nennen sie denselben Betrag.",
    "ausgabenreihe_jahresabschluss":
        "Der Betrag deckt sich mit dem Jahresabschluss desselben Jahres. "
        "Verglichen wird gegen die Ergebnisrechnung der Kernverwaltung, und "
        "die zählt eine Kleinigkeit weniger: Die Statistik nimmt die "
        "Gesamtergebnisrechnung, also Kernhaushalt und nicht rechtsfähige "
        "Stiftungen zusammen. Genau um deren Aufwendungen liegen die beiden "
        "auseinander — gemessen zwischen 0,03 und 0,05 Prozent.",
    # Zuwendungen an die Stadt aus den Ratsbeschlüssen (council/spenden.py).
    # Die erste ist die Pflicht-Probe; ohne sie kommt keine Vorlage herein. Die
    # zweite ist die stärkere — sie stellt zwei getrennt erzeugte Dokumente
    # gegeneinander —, kann aber ausfallen, ohne dass die Zeile fällt: Wenn der
    # Rat die vorgeschlagene Liste ändert, sollen Vorschlag und Beschluss
    # auseinandergehen.
    "integrierte_schulden_kernhaushalt":
        "Der Tabellenband der Statistischen Ämter weist die Schulden des "
        "Kernhaushalts getrennt aus. Dieser Wert stimmt mit der "
        "Geldschulden-Position der städtischen Bilanz überein — zwei "
        "Behörden, zwei Wege, dieselbe Zahl.",
    "anlagen_ahk_kette":
        "Der Anlagenspiegel nennt Anfangsstand, Zugänge, Abgänge und "
        "Umbuchungen einzeln — zusammen ergeben sie den ausgewiesenen "
        "Endstand des Vermögens.",
    "anlagen_abschreibungskette":
        "Dieselbe Rechnung für die Abschreibungen: aufgelaufener Stand, "
        "Abschreibung des Jahres, Auflösungen für Abgänge und Zuschreibungen "
        "ergeben den ausgewiesenen Endstand.",
    "assets_book_value":
        "Anschaffungswert minus aufgelaufener Abschreibung ist der Buchwert, "
        "den die Tabelle in ihrer letzten Spalte selbst ausweist.",
    "anlagen_gegen_bilanz":
        "Derselbe Buchwert steht in der Bilanz desselben Jahresabschlusses — "
        "zwei Tabellen im selben Heft, unabhängig voneinander erstellt.",
    "anlagen_umbuchungssaldo":
        "Bis 2020 zeigt die Vorlage keine Umbuchungen zwischen den "
        "Vermögensarten. Was einer Position dadurch fehlt, ist einer anderen "
        "zugewachsen: Über alle Positionen hebt es sich auf null auf.",
    "kennzahlen_gegen_bilanz":
        "Drei der dreizehn Kennzahlen lassen sich aus der Bilanz desselben "
        "Abschlusses nachrechnen — Anlagenintensität, Infrastrukturquote und "
        "Eigenkapitalquote. Unser Ergebnis stimmt mit dem gedruckten auf die "
        "letzte Nachkommastelle überein.",
    "kennzahlen_vermoegensprobe":
        "„Vermögen je Einwohner*in“ mal „Anzahl der "
        "Einwohnenden“ — zwei Zeilen derselben Tabelle — ergibt genau "
        "die Bilanzsumme ohne "
        "Rechnungsabgrenzung, wie die Bilanz sie ausweist.",
    "kennzahlen_ueberlappung":
        "Jeder Rechenschaftsbericht druckt fünf Jahre, die Berichte "
        "überlappen sich also. Wo zwei Berichte dieselbe Zahl zeigen, ist es "
        "dieselbe Zahl — und wo nicht, hat die Stadt sie nachträglich "
        "korrigiert; das steht dann dabei.",
    "buergschaft_kette":
        "Der Jahresabschluss nennt den Bürgschaftsbestand am Anfang und am "
        "Ende des Jahres. Der Anfangswert steht im Abschluss des Vorjahres "
        "noch einmal als Endwert — zwei getrennte Dokumente, dieselbe Zahl.",
    "buergschaft_tabelle":
        "Der Betrag steht auf den Cent in der Übersichtstabelle des "
        "Jahresabschlusses, nicht nur als gerundete Millionenangabe im Text.",
    "spenden_zweitstelle":
        "Der angenommene Betrag steht zweimal in derselben Vorlage: einmal im "
        "Beschlussvorschlag, einmal im Abschnitt zu den finanziellen "
        "Auswirkungen. Dort entweder als dieselbe Zahl oder zerlegt in "
        "Mehrerträge und Sachspenden — und diese Zerlegung addiert sich auf "
        "den Cent genau auf den Gesamtbetrag.",
    "spenden_protokollabgleich":
        "Was die Vorlage vorschlägt, hat der Rat auch beschlossen: Das "
        "Sitzungsprotokoll nennt denselben Betrag wie der Beschlussvorschlag. "
        "Zwei getrennt erzeugte Dokumente, dieselbe Zahl.",
    # Die beiden Steuertabellen des Jahrbuchs (council/steuertabellen.py).
    # 1103 stellt Plan neben Ist je Steuerart, 1105 führt die Hebesätze seit
    # 1980. Beide hängen an derselben dritten Tabelle — 1104, unserer
    # Ist-Reihe —, und beide brauchen sie für dasselbe: die Prüfung der
    # JAHRESBESCHRIFTUNG. Datensatz 1106 hat gezeigt, was eine ungeprüfte
    # kostet.
    "steuerplan_summenzeile":
        "Die einzelnen Steuerarten und die Finanzzuweisungen ergeben zusammen "
        "genau die Zeile „insgesamt“, die dieselbe Tabelle ausweist — und zwar "
        "in jeder ihrer sechs Spalten: im Haushaltsplan wie im "
        "Rechnungsergebnis, für jedes der drei Jahre.",
    "steuerplan_anteilsprobe":
        "Neben jedem Betrag druckt die Tabelle seinen Anteil an der "
        "Gesamtsumme. Der Betrag, geteilt durch die Summe, ergibt genau diesen "
        "Prozentsatz — damit steht fest, dass jeder Betrag in der Spalte steht, "
        "in der wir ihn gelesen haben.",
    "steuerplan_istabgleich":
        "Das Rechnungsergebnis dieser Tabelle steht ein zweites Mal in Tabelle "
        "1104, die ihre Jahre einzeln beschriftet. Beide werden getrennt "
        "gelesen und nennen für jede Steuerart denselben Betrag. Damit ist "
        "auch die Jahresbeschriftung geprüft: Ein Jahrgang, für den die zweite "
        "Tabelle nichts hergibt, kommt gar nicht erst herein.",
    "hebesatz_spaltenkopf":
        "Welche der drei Spalten die Grundsteuer A, die Grundsteuer B und die "
        "Gewerbesteuer ist, steht im Tabellenkopf und wird dort gelesen — "
        "nicht aus der Reihenfolge geraten.",
    "hebesatz_treppe":
        "Die Tabelle führt nach ihrer eigenen Fußnote nur die Jahre, in denen "
        "sich ein Hebesatz geändert hat. Jede Zeile unterscheidet sich deshalb "
        "von der vorhergehenden — eine Wiederholung wäre ein Fehler.",
    "hebesatz_sprungjahr":
        "Wo der Hebesatz der Grundsteuer stieg, zieht das Aufkommen im "
        "genannten Jahr stärker an als im Jahr danach — nachgerechnet an der "
        "Ist-Reihe der Tabelle 1104. Unterstellt man die Änderung ein Jahr "
        "später, geht die Rechnung nicht mehr auf. Damit ist ausgeschlossen, "
        "dass die Jahresspalte um ein Jahr verrutscht ist.",
    # Beteiligungsbericht nach § 151 NKomVG (council/beteiligungsbericht.py).
    # Die ersten beiden stehen im Dokument selbst, die dritte spannt sich über
    # mehrere Jahrgänge — zusammen decken sie auch das jüngste Berichtsjahr,
    # das noch in keinem zweiten Bericht steht.
    "beteiligung_seitenprobe":
        "Der Bericht sagt zweimal, wo diese Gesellschaft steht: Sein "
        "Inhaltsverzeichnis nennt die Seite, und auf genau dieser Seite steht "
        "ihre Gliederungsnummer. Damit gehört der Abschnitt nachweislich zu "
        "ihr und nicht zur Gesellschaft davor.",
    "beteiligung_bilanzprobe":
        "Die Bilanz der Gesellschaft weist ihre Summe zweimal aus — einmal "
        "unter den Aktiva, einmal unter den Passiva —, und die "
        "Kennzahlen-Tabelle desselben Abschnitts nennt sie ein drittes Mal. "
        "Alle drei stimmen überein.",
    "beteiligung_ergebnisprobe":
        "Die Gewinn- und Verlustrechnung der Gesellschaft schließt mit genau "
        "dem Jahresergebnis, das die Kennzahlen-Tabelle desselben Abschnitts "
        "führt.",
    "beteiligung_spaltenprobe":
        "Der Bericht führt die Aufsichtsorgane als zweispaltige Tabelle — "
        "links die Namen, rechts die Ämter —, und der Textextrakt liest erst "
        "die eine Spalte, dann die andere. Beide Listen sind gleich lang; "
        "damit gehört der n-te Name nachweislich zum n-ten Amt. Wo die "
        "Längen auseinanderlaufen, steht bei dieser Gesellschaft an keinem "
        "Namen ein Amt.",
    "beteiligung_anteilsprobe":
        "Die Anteile der Gesellschafter ergeben zusammen genau das "
        "Stammkapital, das dieselbe Tabelle als Summe ausweist — und ihre "
        "Prozentsätze zusammen 100.",
    "beteiligung_ueberlappung":
        "Jeder Beteiligungsbericht führt vier bis fünf Jahre nebeneinander. "
        "Dieses Jahr steht deshalb in mehreren Berichten — verschiedene "
        "Veröffentlichungen, dieselbe Zahl.",
    # Nachbewilligungen nach § 117 NKomVG (council/nachbewilligungen.py). Die
    # zweite ist die härteste Probe des ganzen Bereichs: Sie stellt nicht zwei
    # Stellen eines Dokuments gegeneinander, sondern unseren Bestand gegen ein
    # amtliches Dokument — und der nennt dieselben Fälle mit Vorlagen-Nummern,
    # also mit einem echten Schlüssel statt einer Ähnlichkeit.
    "nachbewilligung_volltext":
        "Der Betrag, den der Titel der Vorlage nennt, steht in ihrem Volltext "
        "noch einmal. Damit ist ausgeschlossen, dass die Nummer aus dem Titel "
        "eine Jahreszahl, eine Teilhaushaltsnummer oder der Deckungsbetrag "
        "war.",
    "nachbewilligung_ratsabgleich":
        "Der Rechenschaftsbericht der Stadt führt dieselben Nachbewilligungen "
        "noch einmal auf, mit ihren Vorlagen-Nummern und nach Entscheidungsweg "
        "getrennt. Für die Jahre mit Bericht ist geprüft, ob unsere Fälle "
        "seine sind und unsere Summe seine Summe — die gemessene Abweichung "
        "steht dabei.",
    "nachbewilligung_tabellenprobe":
        "Das Kapitel rechnet sich selbst vor: Die vier Entscheidungswege "
        "ergeben zusammen die Summenzeile der Tabelle, und beide Spalten "
        "zusammen die Gesamtsumme, die derselbe Abschnitt im Fließtext nennt. "
        "Wo das nicht aufgeht, widerspricht sich das Dokument — dann steht "
        "hier, um wie viel.",
    UNGEPRUEFT:
        "Diese Angabe trägt keine Rechenprobe — es gibt im Dokument nichts, "
        "wogegen sie sich prüfen ließe. Übernommen wie veröffentlicht.",
    UNBEKANNT:
        "Aus dem Bestand vor der Herkunfts-Vereinheitlichung übernommen. Die "
        "Zeilen haben eine Probe bestanden — welche, hielt der alte Bestand "
        "nicht fest. Der nächste Einlese-Lauf trägt es nach.",
}

#: Jede Tabelle, deren Zeilen eine ``herkunft_id`` tragen.
#:
#: Diese Liste ist die Arbeitsanweisung fürs **Anlegen**: Sie legt die Spalte
#: an (``CouncilStore._migrate_herkunft``) und füllt sie beim Nachrüsten aus
#: den alten Feldern (``_HERKUNFT_ALTFELDER``). Wer eine Tabelle hier
#: vergisst, bekommt keine Spalte — trägt seine Tabelle die ``herkunft_id``
#: aber schon im ``CREATE TABLE`` (so die neueren), fällt das Vergessen beim
#: Anlegen gar nicht auf.
#:
#: **Geprüft und aufgeräumt wird deshalb nicht nach dieser Liste, sondern
#: nach dem Schema** (``CouncilStore._herkunft_verweistabellen()``): Sonst
#: verlöre eine hier vergessene Tabelle beim Aufräumen still ihre Herkünfte,
#: und die Lücken-Meldung schwiege dazu. Die Begründung steht dort.
HERKUNFT_TABELLEN: tuple[str, ...] = (
    "council_haushalt",
    "council_steuern",
    "council_steuerkraft",
    "council_einwohner",
    "council_ergebnisrechnung",
    # Die Kassensicht aus demselben Jahresabschluss — neu, ohne Altbestand,
    # Herkunft ausschließlich über `herkunft_id`.
    "council_finanzrechnung",
    # Die Vermögensseite aus demselben Jahresabschluss (Abschnitt 2.1) und
    # die Erläuterungen des Anhangs dazu (6.2.1–6.2.9) — ebenso.
    "council_bilanz",
    "council_bilanz_erlaeuterungen",
    "council_abweichungsgruende",
    "council_pruefbericht_quellen",
    "council_produkte",
    "council_pruefberichte",
    # Beide neu mit dem Konzern-Bereich und ohne Altbestand: Sie führen ihre
    # Herkunft ausschließlich über `herkunft_id`, tragen also keine
    # `source_label`/`source_url`-Spalten mehr, aus denen etwas nachzutragen
    # wäre (s. `CouncilStore._HERKUNFT_ALTFELDER`).
    "council_konzern_posten",
    "council_konzern_traeger",
    # Der Städtevergleich aus den LSN-Tabellen — ebenfalls ohne Altbestand und
    # deshalb ausschließlich über `herkunft_id` belegt.
    "council_staedtevergleich",
    # Und die Gewerbesteuerstatistik desselben Landesamts.
    "council_gewerbesteuerstatistik",
    # Die Planjahre aus dem Gesamtergebnishaushalt — neu, ohne Altbestand.
    "council_ergebnishaushalt",
    # Die Investitionen des Finanzhaushalts — neu, ohne Altbestand.
    "council_investitionen",
    # Die einzelnen Vorhaben aus Anlage 004 des Haushaltsplans — ebenso.
    "council_investitionsmassnahmen",
    # Und das Ist dazu, die Rechnungsergebnisse aus dem Statistischen Jahrbuch.
    # Zwei Tabellen, weil die Arten je Jahrgang verschieden viele sind: die
    # Summe steht in der einen, die Aufteilung in der anderen.
    "council_investitionen_ist",
    "council_investitionen_ist_arten",
    # Und die Gegenprobe dazu: die verworfenen Jahrgänge mit ihrer gemessenen
    # Differenz. Auch eine Lücke ist eine Auskunft und trägt deshalb die
    # Herkunft des Laufs, der sie festgestellt hat.
    "council_investitionen_ist_verworfen",
    # Der Stellenplan — ebenso.
    "council_stellenplan",
    # Die Schuldenzeitreihe aus dem Statistischen Jahrbuch — ebenfalls neu und
    # ausschließlich über `herkunft_id` belegt.
    "council_schulden",
    # Die lange Ausgabenreihe seit 1972 (Datensatz 1102) — ebenso.
    "council_ausgabenreihe",
    # Nachbewilligungen nach § 117 NKomVG. Drei Tabellen aus zwei Quellen:
    # Die erste liest das Ratsinformationssystem, die beiden anderen Kapitel 3
    # des Rechenschaftsberichts — verschiedene Dokumente, verschiedene Proben,
    # deshalb je eigene Herkunft.
    "council_nachbewilligungen",
    "council_nachbewilligung_jahre",
    "council_nachbewilligung_kanaele",
    # Die angenommenen Zuwendungen je Vorlage (council/spenden.py). Die einzige
    # Schicht des Bereichs, deren Quelle im eigenen Bestand liegt: Sie liest
    # Ratsbeschlüsse, nicht ein Dokument von oldenburg.de. Jede Zeile trägt
    # deshalb die Herkunft **ihrer** Vorlage, nicht die eines Jahrgangs.
    "council_spenden",
    "council_spenden_verworfen",
    # Die beiden Steuertabellen des Jahrbuchs: Plan neben Ist je Steuerart
    # (1103) und die Hebesätze seit 1980 (1105). Beide neu, ohne Altbestand.
    "council_steuerplan",
    "council_hebesaetze",
    # Bedarfsrechnung und die zwölf konkreten Tarife aus deren Anlage 4.
    "council_gebuehren",
    "council_gebuehrensaetze",
    # Der Beteiligungsbericht (council/beteiligungsbericht.py). Die Texte
    # stehen bewusst mit dabei: Sie tragen `UNGEPRUEFT`, aber sie tragen eine
    # Herkunft — Dokument, Abschnitt und Seite. „Keine Probe" ist etwas
    # anderes als „keine Quelle".
    "council_gesellschaften",
    "council_gesellschaft_texte",
    "council_gesellschaft_kennzahlen",
    "council_gesellschaft_personen",
    "council_gesellschaft_eigentuemer",
)


def _proben_normalisieren(roh: str | Sequence[str]) -> str:
    """Ein oder mehrere Probennamen → ein kanonischer, geprüfter String.

    Mehrere sind der Normalfall und nicht die Ausnahme: Die Gesamtrechnung
    eines Jahresabschlusses besteht die Strukturprobe **und** hängt in der
    Vorjahres-Kette. Beides zu nennen ist ehrlicher, als sich für eine zu
    entscheiden."""
    namen = [roh] if isinstance(roh, str) else list(roh)
    namen = [n.strip() for n in namen if n and n.strip()]
    if not namen:
        raise ValueError(
            "Herkunft ohne Probe. Womit ist die Zahl abgesichert? Trägt die "
            "Quelle keine Rechenprobe, ist das ausdrücklich zu sagen: "
            "probe=herkunft.UNGEPRUEFT.")
    for n in namen:
        if n not in PROBEN:
            raise ValueError(
                f"Unbekannte Probe {n!r}. Bekannt sind: {', '.join(sorted(PROBEN))}. "
                "Eine neue Probe gehört mit einem Satz für Leser*innen nach "
                "council/herkunft.py:PROBEN.")
    for allein in (UNGEPRUEFT, UNBEKANNT):
        if allein in namen and len(namen) > 1:
            raise ValueError(
                f"{allein!r} neben einer benannten Probe ist ein Widerspruch — "
                "entweder ist die Probe bekannt oder nicht.")
    # Reihenfolge des Aufrufers bleibt (sie erzählt, was zuerst greift),
    # Doppelnennungen fallen weg.
    gesehen: list[str] = []
    for n in namen:
        if n not in gesehen:
            gesehen.append(n)
    return ",".join(gesehen)


@dataclass(frozen=True)
class Herkunft:
    """Woher **ein Lauf** seine Zeilen genommen hat.

    Pflicht sind ``art`` und ``probe`` — ohne sie lässt sich der Datensatz
    nicht bauen. Dazu muss mindestens einer der beiden Verweise stehen:
    ``document_id`` (der stabile Anker) oder ``url``. Eine Herkunft, die auf
    nichts zeigt, wäre eine Behauptung.

    ``citation`` bleibt leer, solange ein Parser sie nicht kennt — leer ist
    hier ehrlicher als geraten. Sie wird nachgerüstet, wo sie bekannt ist.
    """

    #: Schlüssel aus :data:`ARTEN`.
    kind: str
    #: Name(n) aus :data:`PROBEN`, oder :data:`UNGEPRUEFT`.
    probe: str | Sequence[str]
    #: ``council_anlagen.document_id`` — überlebt Label- und URL-Wechsel.
    #: Der Gesamtabschluss 2016 heißt im Bürgerinfo schlicht „Anlage"; wer
    #: über das Label ankert, verliert ihn beim nächsten Umbenennen.
    document_id: int | None = None
    #: Wie das Dokument heißt — für Menschen, nicht als Schlüssel.
    label: str | None = None
    url: str | None = None
    #: Wo im Dokument: „Abschnitt 6.3.1", „Übersicht Ergebnishaushalt",
    #: „Datensatz 1104". Bei 300 Seiten ist die URL allein zu wenig.
    citation: str | None = None
    #: Seitenzahl, falls das Dokument eine trägt — macht aus dem Link einen
    #: Sprung (``…pdf#page=161``).
    page: int | None = None
    #: Der Messwert der Probe, wo sie einen liefert: „0,02 % Abweichung".
    #: Belegt, dass sie wirklich lief und nicht nur behauptet wird.
    probe_result: str | None = None
    #: Stichtag/Datenstand des Inhalts — nicht der Abrufzeitpunkt. Bei den
    #: Beteiligungen der Punkt, an dem sich Konzern- und Einzelabschluss
    #: unterscheiden.
    as_of: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ARTEN:
            raise ValueError(
                f"Unbekannte Quellenart {self.kind!r}. Bekannt sind: "
                f"{', '.join(sorted(ARTEN))}.")
        # Der Aufrufer darf einen Namen oder eine Liste übergeben; gespeichert
        # wird immer die kanonische, geprüfte Fassung.
        object.__setattr__(self, "probe", _proben_normalisieren(self.probe))
        if self.document_id is None and not self.url:
            raise ValueError(
                "Herkunft ohne Verweis: mindestens document_id (der stabile "
                "Anker aus council_anlagen) oder url muss stehen.")

    @property
    def probes(self) -> list[str]:
        """Die Probennamen einzeln."""
        return [n for n in str(self.probe).split(",") if n]

    @property
    def geprueft(self) -> bool:
        """Trägt diese Quelle überhaupt eine Rechenprobe?

        ``UNBEKANNT`` gilt als geprüft: Diese Zeilen **haben** eine Probe
        bestanden, nur ist nicht festgehalten, welche. Nur ``UNGEPRUEFT``
        heißt, dass es keine gab."""
        return self.probes != [UNGEPRUEFT]

    def felder(self) -> dict:
        """Die Spaltenwerte für ``council_herkunft`` (ohne ``fetched_at``)."""
        return {"kind": self.kind, "document_id": self.document_id,
                "label": self.label, "url": self.url,
                "citation": self.citation, "page": self.page,
                "probe": str(self.probe), "probe_result": self.probe_result,
                "as_of": self.as_of}

    def key(self) -> str:
        """Inhaltlicher Fingerabdruck — macht das Eintragen idempotent.

        Bewusst **ohne** ``fetched_at``: Wann wir zuletzt nachgesehen haben,
        ändert nicht, woher die Zahl kommt. Läge der Zeitpunkt im Schlüssel,
        legte jeder Lauf einen neuen Datensatz an und die Tabelle wüchse mit
        der Zahl der Läufe statt mit der Zahl der Quellen.

        Ein Hash statt eines UNIQUE-Index über die neun Spalten, weil SQLite
        ``NULL`` in einem UNIQUE-Index nicht als gleich behandelt: Zwei
        Herkünfte ohne Seitenzahl wären dort verschieden und lägen doppelt."""
        roh = json.dumps(self.felder(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def probe_texte(probe: str | None) -> list[str]:
    """Die Erklärsätze zu einer gespeicherten Probenliste — für die API.

    Unbekannte Namen (eine Probe, die es einmal gab und heute nicht mehr)
    fallen still weg: Die Oberfläche soll den Beleg zeigen können, auch wenn
    ein alter Bestand einen Namen trägt, den der Code nicht mehr kennt."""
    return [PROBEN[n] for n in (probe or "").split(",") if n in PROBEN]
