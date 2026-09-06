"""Kurze, allgemeinverständliche Erklärungen der Fachwörter, über die man in
Ratsunterlagen stolpert — „Ausfallbürgschaft", „Aufwandsspaltung",
„Verpflichtungsermächtigung".

**Einzige Quelle.** Die Erklärungen standen bis 09/2026 nur im Frontend
(`web/frontend/lib/glossary.ts`) und waren damit für die KI-Frage unerreichbar:
Das Modell antwortet ausschließlich aus dem, was im Prompt steht, und dort
stand keine einzige Definition. „Was ist eine Ausfallbürgschaft?" hing deshalb
am Zufall der Beschluss-Suche — mal erklärte ein zitierter Beschluss den
Begriff nebenbei mit, mal kam „die Beschlüsse definieren nicht, was das ist"
(beides gemessen, 04.09.2026, dieselbe Frage).

Jetzt liegen sie hier, wie die Prompts als Code und nicht als Datenbankinhalt:
im PR sichtbar, mit Diff und Historie. Die TypeScript-Datei wird daraus
erzeugt (``scripts/glossar_ts.py``), ``scripts/pruefe.py`` hält beide
gegeneinander.

Wer einen Begriff ergänzt: Er muss in den Unterlagen **wirklich vorkommen**
(die Auswahl unten ist an 9.059 Beschlüssen und 4.000 Vorlagen gemessen), und
die Erklärung muss ohne ein zweites Fachwort auskommen. Erfundene Fachwörter
gehören hier nicht hin.
"""
from __future__ import annotations

import re

#: Begriff → Erklärung in Alltagssprache. Schlüssel ist die Grundform; gematcht
#: wird ab Wortanfang mit beliebiger Buchstaben-Endung, sodass Beugungen
#: („Bebauungsplans", „Vergnügungsstätten") mitgefunden werden. Ein Kompositum
#: braucht einen EIGENEN Eintrag: „Bürgschaft" greift bei
#: „Ausfallbürgschaft" nicht, weil der Begriff dort nicht am Wortanfang steht.
BEGRIFFE: dict[str, str] = {
    "Vergnügungsstätte":
        "Betriebe wie Spielhallen, Wettbüros, Diskotheken oder Bordelle. Im Baurecht eine eigene Nutzungsart, die die Stadt über Bebauungspläne räumlich steuern kann.",
    "Bebauungsplan":
        "Eine kommunale Satzung, die für ein bestimmtes Gebiet verbindlich festlegt, was und wie dort gebaut werden darf.",
    "Flächennutzungsplan":
        "Der grobe Plan für die künftige Nutzung des ganzen Stadtgebiets (Wohnen, Gewerbe, Grün …) — Grundlage für die genaueren Bebauungspläne.",
    "Bauleitplanung":
        "Oberbegriff für Flächennutzungs- und Bebauungsplan: die vorausschauende Steuerung der baulichen Entwicklung durch die Stadt.",
    "Aufstellungsbeschluss":
        "Der formale Startschuss des Rats, einen Bebauungsplan für ein Gebiet zu erarbeiten.",
    "Satzung":
        "Eine ortsrechtliche Vorschrift, die der Stadtrat für die Stadt beschließt — quasi ein Gesetz auf kommunaler Ebene.",
    "Vorlage":
        "Die schriftliche Beschlussvorlage der Verwaltung für den Rat — mit Sachverhalt, Begründung und Beschlussvorschlag.",
    "Tagesordnung":
        "Die Liste der Punkte, die in einer Sitzung behandelt werden.",
    "Niederschrift":
        "Das offizielle Protokoll einer Sitzung.",
    "Fraktion":
        "Der Zusammenschluss der Ratsmitglieder einer Partei (oder mehrerer) im Stadtrat.",
    "interfraktionell":
        "Von mehreren Fraktionen gemeinsam getragen (z. B. ein gemeinsamer Antrag).",
    "Ausschuss":
        "Ein kleineres Fachgremium des Rats (z. B. Bau- oder Finanzausschuss), das Entscheidungen vorbereitet.",
    # Homonym-Falle: In Produkt-Steckbriefen der Stadt („Erschließung der
    # Archivbestände") meint das Wort das Ordnen und Verzeichnen, nicht den
    # Straßenbau. Der Zusatz steht hier, weil die Erklärung sonst genau dort
    # falsch wäre, wo sie automatisch erscheint.
    "Erschließung":
        "Im Baurecht: die Herstellung von Straßen, Wegen, Kanälen und Leitungen, damit ein Grundstück bebaut und genutzt werden kann. In anderen Zusammenhängen meint das Wort etwas anderes — bei Archiven zum Beispiel das Ordnen und Verzeichnen von Beständen.",
    "Nutzungsänderung":
        "Wenn ein Gebäude künftig anders genutzt wird als bisher (z. B. Laden statt Wohnung) — oft genehmigungspflichtig.",
    "Sanierungsgebiet":
        "Ein förmlich festgelegtes Gebiet, das die Stadt gezielt städtebaulich aufwertet (Städtebauförderung).",
    "Haushalt":
        "Der Plan der Stadt über ihre Einnahmen und Ausgaben, jährlich vom Rat beschlossen.",
    "Doppelhaushalt":
        "Ein Haushalt, der gleich für zwei Jahre auf einmal beschlossen wird.",
    "Bürgerbegehren":
        "Ein Weg, mit dem Bürger*innen einen Bürgerentscheid zu einer kommunalen Frage erzwingen können — wenn genug Unterschriften zusammenkommen.",
    "Bürgerentscheid":
        "Eine direkte Abstimmung der Bürger*innen über eine kommunale Sachfrage, so bindend wie ein Ratsbeschluss.",
    "Konzession":
        "Eine behördliche Erlaubnis, ein bestimmtes Gewerbe oder Recht auszuüben (z. B. Strom- oder Gasnetz zu betreiben).",
    # Krankenhaus-Versorgungsstufen (niedersächsische Krankenhausplanung) —
    # tauchen in Fragen zum Klinikum auf.
    "Maximalversorgung":
        "Die höchste Krankenhaus-Stufe: deckt praktisch alle Fachrichtungen ab, inklusive hochspezialisierter Medizin — in der Region meist nur ein Haus (hier: das Klinikum Oldenburg).",
    "Schwerpunktversorgung":
        "Die zweithöchste Krankenhaus-Stufe: deutlich mehr Fachabteilungen als die Grundversorgung, aber nicht das komplette Spektrum eines Maximalversorgers.",
    "Grundversorgung":
        "Die Basis-Stufe eines Krankenhauses: Innere Medizin und Chirurgie für die wohnortnahe Standardversorgung.",
    "Fachkrankenhaus":
        "Ein Krankenhaus, das auf ein bestimmtes Gebiet spezialisiert ist (z. B. Psychiatrie oder Lungenheilkunde), statt die volle Breite anzubieten.",
    # Haushalts-Begriffe (kommunale Doppik) — für die Haushalts-Quizfragen.
    "Ergebnishaushalt":
        "Der Teil des Haushalts, der alle Erträge (z. B. Steuern, Zuweisungen, Gebühren) und Aufwendungen (z. B. Personal, Sozialleistungen) eines Jahres gegenüberstellt.",
    "Finanzhaushalt":
        "Der Teil des Haushalts, der die tatsächlichen Geldflüsse zeigt — alle Ein- und Auszahlungen, auch für Investitionen und Kredite.",
    "Teilhaushalt":
        "Ein Abschnitt des städtischen Haushalts für einen Aufgabenbereich (z. B. „Soziales und Gesundheit“ oder „Schule und Bildung“) — grob vergleichbar mit einem Ressort.",
    "Pflichtaufgabe":
        "Aufgaben, die die Stadt per Bundes- oder Landesgesetz erfüllen MUSS (z. B. Sozialleistungen, Schulträgerschaft) — dieses Geld ist gebunden, der Rat kann es kaum umschichten.",
    "freiwillige Leistung":
        "Aufgaben, die die Stadt übernehmen KANN, aber nicht muss (z. B. Kultur- und Sportförderung, Zuschüsse an Vereine) — hier hat der Rat den größten Gestaltungsspielraum.",
    "Schlüsselzuweisung":
        "Geld, das das Land nach einem festen Verteilschlüssel an die Kommunen zahlt, um unterschiedliche Finanzkraft auszugleichen.",
    "Gewerbesteuer":
        "Steuer, die Unternehmen an ihre Stadt zahlen — eine der wichtigsten eigenen Einnahmequellen der Kommunen; den Hebesatz legt der Rat fest.",
    "Rücklage":
        "Erspartes der Stadt aus Überschüssen früherer Jahre — daraus können geplante Defizite ausgeglichen werden.",
    # Ergänzt 16.08.2026 für den Haushalts-Bereich: die Wörter, über die man
    # beim Lesen einer Haushaltsseite zuerst stolpert.
    "Ertrag":
        "Das Fachwort für Einnahmen im Haushalt — alles, was der Stadt in einem Jahr zusteht: Steuern, Zuweisungen, Gebühren.",
    "Aufwendung":
        "Das Fachwort für Ausgaben im Haushalt — Personal, Sozialleistungen, Zuschüsse, Gebäudekosten.",
    "ordentliche Erträge":
        "Die regelmäßigen Einnahmen des laufenden Betriebs — ohne einmalige Sondereffekte wie den Verkauf eines Grundstücks.",
    "ordentliche Aufwendungen":
        "Die regelmäßigen Ausgaben des laufenden Betriebs — Investitionen wie ein Schulneubau zählen extra.",
    "Zuschussbedarf":
        "Was ein Bereich die Stadt unterm Strich kostet: seine Ausgaben minus die Einnahmen, die er selbst erwirtschaftet. Der Rest wird aus allgemeinen Steuermitteln bezahlt.",
    "Kostendeckungsgrad":
        "Wie viel Prozent seiner Ausgaben ein Bereich durch eigene Einnahmen (Gebühren, Erstattungen) selbst deckt.",
    "Hebesatz":
        "Ein Prozentwert, den der Rat jedes Jahr beschließt. Er wird auf den vom Finanzamt errechneten Messbetrag angewendet und bestimmt so, wie hoch Gewerbe- und Grundsteuer in Oldenburg tatsächlich ausfallen.",
    "Messbetrag":
        "Zwischenschritt bei Gewerbe- und Grundsteuer: Das Finanzamt rechnet Gewinn bzw. Grundstückswert nach bundesweit gleichen Regeln in eine Zahl um. Erst der Hebesatz der Stadt macht daraus den Steuerbetrag.",
    # Ergänzt 24.08.2026 für den Block „Wer zahlt das eigentlich" auf dem
    # Gewerbesteuer-Steckbrief.
    "Steuergeheimnis":
        "Die Pflicht der Finanzverwaltung, Verhältnisse einzelner Steuerzahler für sich zu behalten (§ 30 Abgabenordnung). Sie gilt auch für die Stadt: Was ein bestimmtes Unternehmen an Gewerbesteuer zahlt, darf sie weder veröffentlichen noch dem Rat mitteilen.",
    "Zerlegung":
        "Die Aufteilung der Gewerbesteuer eines Unternehmens auf alle Gemeinden, in denen es Standorte hat. Maßstab sind die Arbeitslöhne je Standort — nicht der Sitz der Zentrale.",
    "Messzahl":
        "Der bundesweit einheitliche Prozentsatz, mit dem aus dem Gewinn der Messbetrag errechnet wird (bei der Gewerbesteuer 3,5 %).",
    "Steuerkraftmesszahl":
        "Eine Rechengröße des Landes dafür, wie viel Steuerkraft eine Stadt hat. Sie bestimmt mit, wie viel Geld sie aus dem Finanzausgleich bekommt.",
    "Finanzausgleich":
        "Das System, mit dem das Land Geld an seine Städte und Gemeinden verteilt, damit ärmere Kommunen ihre Aufgaben trotzdem erfüllen können.",
    "Gewerbesteuerumlage":
        "Ein Anteil der Gewerbesteuer, den die Stadt an Bund und Land weiterreichen muss — von jedem eingenommenen Euro bleibt ihr also nicht alles.",
    "Grundsteuer":
        "Steuer auf Grundstücke und Gebäude, gezahlt von Eigentümer*innen — über die Nebenkosten meist auch von Mieter*innen. Den Hebesatz beschließt der Rat.",
    "Haushaltssatzung":
        "Der förmliche Beschluss, mit dem der Rat den Haushalt in Kraft setzt — darin stehen auch die Hebesätze für das Jahr.",
    "Doppik":
        "Die kaufmännische Buchführung der Kommunen: Sie zeigt nicht nur Zahlungen, sondern auch den Werteverzehr (etwa Abnutzung von Gebäuden).",
    # Wörter aus den Produkt-Steckbriefen der Teilhaushaltspläne. Sie stehen dort
    # im Verwaltungsdeutsch der Stadt; ungefiltert durchgereicht wäre die
    # Produktseite unlesbar. Beide Wirkungskreis-Formen sind erklärt, weil die
    # Pläne beide Schreibweisen führen („übertragend" ist ihr eigener Tippfehler).
    "Produkt":
        "Die kleinste Einheit des städtischen Haushalts: eine einzelne Aufgabe mit eigener Nummer, eigenem Budget und einem zuständigen Amt — zum Beispiel „Archivierung“ oder „Brand- und Katastrophenschutz“.",
    "Auftragsgrundlage":
        "Die Gesetze, Verträge und Satzungen, auf denen eine städtische Aufgabe beruht — die Antwort auf „Warum macht die Stadt das überhaupt?“.",
    "Wirkungskreis":
        "Ob die Stadt eine Aufgabe in eigener Verantwortung erledigt oder im Auftrag von Bund und Land. Das entscheidet, wer die Regeln setzt — und wer bei Streit das letzte Wort hat.",
    "eigener Wirkungskreis":
        "Die Stadt erledigt die Aufgabe in eigener Verantwortung. Der Rat kann über das Wie entscheiden; das Land prüft nur, ob alles rechtmäßig ist.",
    "übertragener Wirkungskreis":
        "Die Stadt erledigt die Aufgabe im Auftrag von Bund oder Land und ist dabei an deren Weisungen gebunden — der Rat hat hier praktisch nichts zu entscheiden.",
    "übertragender Wirkungskreis":
        "Schreibweise der Haushaltspläne für den übertragenen Wirkungskreis: Die Stadt erledigt die Aufgabe im Auftrag von Bund oder Land und ist an deren Weisungen gebunden.",
    "Grad der Beeinflussbarkeit":
        "Die Selbstauskunft der Stadt, wie viel Spielraum sie bei einer Aufgabe hat — von „niedrig“ (Kosten und Umfang stehen praktisch fest) bis „hoch“ (der Rat kann weitgehend selbst bestimmen).",
    # Ergänzt 16.08.2026: die Wörter, die im Haushalts-Bereich auf der Seite
    # stehen, ohne dass sie dort jemand erklärt — vor allem die Vokabeln aus den
    # Jahresabschlüssen und aus dem Schlussbericht des Rechnungsprüfungsamts.
    "Ansatz":
        "Der Betrag, den der Rat für eine Position in den Haushalt geschrieben hat — der Plan, bevor das Jahr läuft. Am Jahresende wird verglichen, was daraus wurde.",
    "Nachtragshaushalt":
        "Eine Änderung des laufenden Haushalts, die der Rat mitten im Jahr beschließt, wenn sich Einnahmen oder Ausgaben deutlich anders entwickeln als geplant.",
    "Gesamtermächtigung":
        "Alles, was die Verwaltung in einem Jahr ausgeben durfte: der ursprüngliche Ansatz, ein etwaiger Nachtrag und Reste, die aus dem Vorjahr übertragen wurden. Manche Jahresabschlüsse vergleichen dagegen statt gegen den ursprünglichen Plan — die Abweichung fällt dann kleiner aus.",
    "Ertragsart":
        "Die Gliederung der Einnahmen nach ihrer Herkunft — Steuern, Zuweisungen, Gebühren, Kostenerstattungen und so weiter. Der Jahresabschluss führt sie als nummerierte Posten.",
    "Aufwandsart":
        "Die Gliederung der Ausgaben nach ihrer Art — Personal, Sachaufwand, Transferleistungen, Abschreibungen. Das Gegenstück zur Ertragsart.",
    "Jahresabschluss":
        "Die Abrechnung eines Haushaltsjahres: Was tatsächlich eingenommen und ausgegeben wurde, jeweils neben dem, was geplant war. Er erscheint erst ein bis zwei Jahre nach dem Jahr, das er abrechnet.",
    "Ergebnisrechnung":
        "Der Teil des Jahresabschlusses, der Erträge und Aufwendungen gegenüberstellt — das tatsächliche Gegenstück zum geplanten Ergebnishaushalt.",
    "ordentliches Ergebnis":
        "Erträge minus Aufwendungen aus dem laufenden Betrieb eines Jahres. Ist es negativ, hat die Stadt in diesem Jahr mehr verbraucht, als sie eingenommen hat.",
    "Jahresergebnis":
        "Das Ergebnis des ganzen Jahres: das ordentliche Ergebnis plus einmalige, außerordentliche Posten wie den Verkauf eines Grundstücks.",
    "Kernverwaltung":
        "Die Stadtverwaltung selbst — ohne ihre Eigenbetriebe und Beteiligungen, die eigene Bücher führen.",
    "Rechnungsprüfungsamt":
        "Die Stelle, die den Jahresabschluss der Stadt prüft. Sie gehört zur Stadt, berichtet aber dem Rat und nicht der Verwaltungsspitze.",
    "Schlussbericht":
        "Der Bericht, mit dem das Rechnungsprüfungsamt seine Prüfung eines Jahresabschlusses abschließt — mit allen Beanstandungen und Hinweisen im Wortlaut.",
    "Textziffer":
        "Die durchlaufende Nummer eines Abschnitts in einem amtlichen Bericht — die Adresse, unter der man eine Feststellung wiederfindet.",
    # Ergänzt mit /haushalt/konzern: die Vokabeln des Gesamtabschlusses. Sie
    # stehen unvermeidlich auf der Seite (sie sind die Namen der Sache), und
    # ungeklärt ist jedes einzelne ein Grund wegzuklicken.
    "Gesamtabschluss":
        "Die Rechnung, die einmal im Jahr alles zusammenzieht, was der Stadt gehört: die Verwaltung selbst, ihre Eigenbetriebe und ihre Gesellschaften. Sie zeigt die Stadt so, als wäre sie ein einziges Unternehmen — daher auch „Konzernabschluss“.",
    "Konzernabschluss":
        "Anderes Wort für den Gesamtabschluss: die Rechnung, die Stadtverwaltung, Eigenbetriebe und städtische Gesellschaften zu einer einzigen zusammenfasst.",
    "Konsolidierung":
        "Das Herausrechnen der Geschäfte, die städtische Betriebe miteinander machen. Zahlt die Stadt ihrem Klinikum einen Zuschuss, ist das für den einen Ausgabe und für den anderen Einnahme — in einer gemeinsamen Rechnung stünde es doppelt. Deshalb wird es abgezogen.",
    "Konsolidierungskreis":
        "Die Liste der Betriebe und Gesellschaften, die in den Gesamtabschluss einbezogen werden. Wer zu klein ist, um das Bild zu verändern, bleibt draußen.",
    "Eigenbetrieb":
        "Ein Betrieb der Stadt mit eigener Buchführung und eigenem Wirtschaftsplan, aber ohne eigene Rechtsform — er gehört rechtlich weiter zur Stadt. In Oldenburg zum Beispiel die Gebäudewirtschaft, die Abfallwirtschaft und der Bäderbetrieb.",
    "Aufgabenträger":
        "Sammelbegriff des Gesamtabschlusses für alles, was für die Stadt Aufgaben erledigt: die Verwaltung selbst, ihre Eigenbetriebe, Anstalten und Gesellschaften.",
    "Anstalt des öffentlichen Rechts":
        "Eine rechtlich selbstständige Einrichtung in öffentlicher Hand — sie hat eigene Organe und eigene Bücher, gehört aber weiterhin der Stadt. Das Klinikum Oldenburg ist eine.",
    # Zweite Homonym-Falle nach „Erschließung": Seit die Erklärungen auch im
    # Antworttext der KI-Frage unterringelt werden, trifft dieser Eintrag auch
    # „Beteiligung der Öffentlichkeit" — und dort wäre der Unternehmensanteil
    # schlicht falsch. Deshalb steht die zweite Bedeutung mit im Satz.
    "Beteiligung":
        "Ein Anteil der Stadt an einem Unternehmen. Bei einer Mehrheit bestimmt sie mit, bei kleineren Anteilen sitzt sie eher mit am Tisch als am Steuer. In der Bauleitplanung meint das Wort etwas anderes: die Schritte, in denen Bürger*innen zu einem Plan Stellung nehmen können.",
    "Eigenkapitalmethode":
        "Ein Weg, ein Unternehmen in die Gesamtrechnung aufzunehmen, an dem die Stadt zwar beteiligt ist, das sie aber nicht allein bestimmt: Statt aller Einnahmen und Ausgaben fließt nur der Anteil am Wert des Unternehmens ein. Fachlich auch „Equity-Methode“.",
    "Equity-Methode":
        "Anderes Wort für die Eigenkapitalmethode: Von einem Unternehmen, an dem die Stadt nur beteiligt ist, geht nicht das ganze Geschäft in die Gesamtrechnung ein, sondern nur der Anteil an seinem Wert.",
    "Vollkonsolidierung":
        "Die vollständige Aufnahme eines Betriebs in die Gesamtrechnung: Alle seine Einnahmen und Ausgaben zählen mit, so als gehörten sie der Stadt direkt.",
    # ── Bilanz, Anlagen, Bürgschaften, Kennzahlen ──────────────────────────
    # Diese siebzehn kamen mit den Schichten 08/2026 dazu. Jeder Begriff steht
    # wörtlich auf mindestens einer Seite des Haushalts-Bereichs; erfundene
    # Fachwörter gehören hier nicht hin.
    "Bilanzsumme":
        "Alles zusammen, was der Stadt am 31. Dezember gehört — und, von der anderen Seite gelesen, woher es finanziert ist. Für Oldenburg waren das Ende 2024 rund 1,48 Milliarden Euro. Viele Kennzahlen sind ein Anteil davon.",
    "Bilanz":
        "Die Aufstellung, was der Stadt an einem Stichtag gehört und wem es zusteht. Anders als der Haushalt zählt sie kein Jahr, sondern einen Tag — ihre Beträge lassen sich deshalb nicht mit Einnahmen und Ausgaben verrechnen.",
    "Nettoposition":
        "Das Eigenkapital der Stadt: der Teil des Vermögens, der nach Abzug aller Schulden und Verpflichtungen übrig bleibt. In der kommunalen Buchführung heißt er nicht Eigenkapital, sondern Nettoposition.",
    "Sonderposten":
        "Geld, das die Stadt für eine bestimmte Anschaffung bekommen hat — meist Zuschüsse von Land oder Bund. Es steht auf der Passivseite und wird über die Jahre aufgelöst, parallel zur Abnutzung dessen, was davon gebaut wurde.",
    "Rechnungsabgrenzung":
        "Beträge, die im alten Jahr geflossen sind, aber ins neue gehören (oder umgekehrt) — zum Beispiel eine im Dezember gezahlte Versicherung für das Folgejahr. Sie werden getrennt ausgewiesen, damit jedes Jahr trägt, was zu ihm gehört.",
    "Sachvermögen":
        "Alles Angefasste, was der Stadt gehört: Grundstücke, Gebäude, Straßen, Fahrzeuge, Maschinen. 2024 waren das rund 606 Millionen Euro und damit gut 41 % der Bilanzsumme.",
    "Infrastrukturvermögen":
        "Der Teil des Sachvermögens, der öffentlich zugänglich ist und nicht verkauft werden kann: Straßen, Wege, Plätze, Brücken, Kanäle, Gleisanlagen.",
    "Abschreibung":
        "Der jährlich gebuchte Wertverlust einer Anschaffung. Eine Schule kostet einmal Geld, hält aber Jahrzehnte — deshalb wird ihr Wert über die Nutzungsdauer verteilt und Jahr für Jahr ein Stück davon als Aufwand gebucht.",
    "Buchwert":
        "Was ein Gegenstand in den Büchern der Stadt noch wert ist: der Anschaffungspreis minus alles, was bisher abgeschrieben wurde. Nicht zu verwechseln mit dem Preis, den er am Markt brächte.",
    "Anlagenspiegel":
        "Die Tabelle im Jahresabschluss, die für jede Vermögensart zeigt, was im Jahr dazukam, was abging und wie viel abgeschrieben wurde. Aus ihr lässt sich ablesen, ob die Stadt schneller aufbaut, als ihr Bestand verfällt.",
    "Bürgschaft":
        "Ein Versprechen der Stadt, für den Kredit eines anderen einzustehen, falls der nicht zahlen kann. Es kostet zunächst nichts und taucht deshalb in keiner Ausgabe auf — Ende 2024 stand die Stadt so für 220,3 Millionen Euro gerade.",
    "Eventualverbindlichkeit":
        "Eine Verpflichtung, die nur unter einer Bedingung fällig wird — typischerweise eine Bürgschaft. Sie steht nicht in der Bilanz selbst, sondern in ihrem Anhang, weil offen ist, ob sie je zu zahlen ist.",
    "Rückstellung":
        "Geld, das die Stadt für eine absehbare, aber noch nicht fällige Zahlung zurücklegt — etwa für Pensionen ihrer Beamt*innen oder für den Teil der Bürgschaften, bei dem ein Ausfall erwartet wird.",
    "Eigenkapitalquote":
        "Wie viel des Vermögens der Stadt wirklich ihres ist, in Prozent der Bilanzsumme. Sie wird in zwei Fassungen gedruckt: ohne und mit den Sonderposten, also den Zuschüssen von Land und Bund.",
    "Anlagenintensität":
        "Welcher Anteil des Vermögens in Sachwerten steckt — Gebäuden, Straßen, Fahrzeugen. Ein hoher Wert heißt weder gut noch schlecht: Er sagt, dass viel gebunden und wenig beweglich ist.",
    "Steuerquote":
        "Welcher Anteil der laufenden Ausgaben durch Steuern gedeckt ist. Je höher sie liegt, desto weniger hängt die Stadt an Zuweisungen von Land und Bund.",
    "Rechenschaftsbericht":
        "Der erklärende Text zum Jahresabschluss: Er sagt in Worten, was die Zahlen bedeuten, warum etwas anders kam als geplant und wie viel im Jahr nachbewilligt wurde. Am Ende steht eine Anlage mit dreizehn Kennzahlen samt ihren Rechenwegen.",

    # ── Ratsverfahren ─────────────────────────────────────────────────────
    # Die Wörter, mit denen der Rat über sich selbst spricht. Sie stehen in
    # jeder zweiten Tagesordnung, erklärt sie aber nirgends. Zahlen in
    # Klammern: in wie vielen der 9.059 Beschlüsse das Wort vorkommt
    # (gemessen 04.09.2026) — was hier steht, begegnet einem wirklich.
    "Verwaltungsausschuss":  # 170
        "Der kleine Kreis, in dem die Ratsarbeit zusammenläuft: der Oberbürgermeister und Vertreter*innen der Fraktionen. Er tagt nichtöffentlich, bereitet die Ratssitzungen vor und entscheidet in eiligen Fällen selbst.",
    "Tagesordnungspunkt":  # 385
        "Ein einzelner Punkt einer Sitzung, mit eigener Nummer. Ein „Ö“ davor heißt öffentlich, ein „N“ nichtöffentlich.",
    "Beratungsfolge":  # 3.982 Vorlagen
        "Der Weg, den eine Vorlage durch die Gremien nimmt: erst der Fachausschuss, dann der Verwaltungsausschuss, am Ende der Rat. Sie steht auf jeder Vorlage und sagt, wer wann darüber redet.",
    "Beschlussvorlage":  # 29
        "Das Papier, mit dem die Verwaltung dem Rat eine Entscheidung vorschlägt: der Sachverhalt, die Begründung und der Satz, über den am Ende abgestimmt wird.",
    "Änderungsantrag":  # 409
        "Ein Antrag, der eine vorliegende Vorlage nicht ablehnt, sondern in Teilen ändern will. Über ihn wird vor der Vorlage selbst abgestimmt.",
    "Leitantrag":  # 212
        "Der große inhaltliche Antrag einer oder mehrerer Fraktionen zu einem Thema — meist mit vielen Punkten, oft zum Haushalt. Er gibt die Linie vor, die Einzelanträge füllen sie aus.",
    "Vertagung":  # 120
        "Ein Punkt wird nicht entschieden, sondern auf eine spätere Sitzung geschoben — meist, weil noch Auskünfte fehlen.",
    "Dringlichkeit":  # 11
        "Die Begründung dafür, einen Punkt kurzfristig auf die Tagesordnung zu setzen, obwohl die Frist dafür abgelaufen ist. Der Rat muss der Dringlichkeit zustimmen, bevor er über die Sache selbst redet.",
    "Kenntnisnahme":  # 70
        "Der Rat nimmt einen Bericht zur Kenntnis: Er hört ihn an, ohne etwas zu beschließen. Das ist keine Zustimmung, sondern die Feststellung, dass die Information angekommen ist.",
    "Unterrichtung":  # 156
        "Ein Punkt, mit dem die Verwaltung den Rat über etwas informiert. Entschieden wird dabei nichts.",
    "Sachstandsbericht":  # 174
        "Ein Zwischenbericht der Verwaltung: Wie weit ist ein Vorhaben, was ist seit dem letzten Bericht passiert. Er wird zur Kenntnis genommen, nicht beschlossen.",
    "Anfrage":  # 35
        "Das Fragerecht der Ratsmitglieder: eine Frage an die Verwaltung, die diese in der Sitzung oder schriftlich beantworten muss. Ein Beschluss kommt dabei nicht heraus.",
    "Resolution":  # 26
        "Eine gemeinsame Erklärung des Rats zu einem Thema, für das er selbst nicht zuständig ist — meist an Land oder Bund gerichtet. Sie bindet niemanden, ist aber ein politisches Signal.",
    "Eilentscheidung":  # 8
        "Eine Entscheidung, die getroffen wird, ohne dass das zuständige Gremium vorher tagen konnte, weil die Sache keinen Aufschub duldet. Sie wird ihm nachträglich vorgelegt.",
    "Entlastung":  # 222
        "Der förmliche Beschluss, dass der Rat mit der Kassenführung eines Jahres einverstanden ist — eine Quittung, kein Lob.",
    # Kein Fachwort, sondern eine Homonym-Sperre: Ohne eigenen Eintrag hätte
    # „Entlastungsstraße" (53 Beschlüsse, meist am Fliegerhorst) die Erklärung
    # der Kassen-Entlastung darüber bekommen — der längere Begriff gewinnt und
    # sagt hier das Richtige. Dasselbe Muster wie der Zusatz bei
    # „Erschließung", nur sauberer.
    "Entlastungsstraße":  # 53
        "Eine neue Straße, die eine bestehende vom Verkehr entlasten soll. Mit der Entlastung eines Haushaltsjahres hat sie nichts zu tun.",

    # ── Geld: Ermächtigungen, Kredite, Betriebe ───────────────────────────
    "Ausfallbürgschaft":  # 40
        "Eine Bürgschaft, bei der die Stadt erst dann zahlt, wenn die Bank beim eigentlichen Schuldner alles versucht hat und trotzdem leer ausgeht. Sie kostet zunächst nichts und taucht deshalb in keiner Ausgabe auf — fällig wird sie nur im Ernstfall.",
    "Verpflichtungsermächtigung":  # 79
        "Die Erlaubnis des Rats, heute etwas zu bestellen, das erst in späteren Jahren bezahlt wird — etwa einen Bau über drei Jahre. Im laufenden Haushalt fließt dafür noch kein Geld, gebunden ist es trotzdem.",
    "Kreditermächtigung":  # Haushaltssatzung
        "Die Obergrenze, bis zu der die Stadt in einem Jahr neue Kredite aufnehmen darf. Der Rat beschließt sie in der Haushaltssatzung; ausschöpfen muss die Stadt sie nicht.",
    "überplanmäßig":  # 197
        "Eine Ausgabe, die höher ausfällt, als im Haushalt dafür eingeplant war. Sie braucht eine eigene Zustimmung, bevor das Geld ausgegeben werden darf.",
    "außerplanmäßig":  # 101
        "Eine Ausgabe für etwas, das im Haushalt überhaupt nicht vorgesehen war. Auch sie braucht eine eigene Zustimmung.",
    "Kreditrichtlinie":  # 138
        "Die Regeln, die der Rat der Verwaltung für Kredite setzt: was sie aufnehmen darf, mit welchen Laufzeiten und welcher Absicherung. Sie wird regelmäßig neu beschlossen.",
    "Umschuldung":  # 91
        "Ein alter Kredit wird durch einen neuen ersetzt, meist wegen besserer Zinsen. Die Schulden werden dadurch nicht weniger — nur die Bedingungen ändern sich.",
    "Derivat":  # 76
        "Ein Zusatzgeschäft zu einem Kredit, das den Zins absichert: Die Stadt tauscht zum Beispiel einen schwankenden gegen einen festen Zinssatz. Es ist kein eigener Kredit, verändert aber, was der Kredit am Ende kostet.",
    "Wirtschaftsplan":  # 140
        "Der Haushalt eines städtischen Betriebs — Gebäudewirtschaft, Abfallwirtschaft, Bäder. Er besteht aus Erfolgsplan und Vermögensplan und wird vom Rat beschlossen wie der Haushalt der Stadt selbst.",
    "Erfolgsplan":  # 73
        "Der Teil des Wirtschaftsplans, der Einnahmen und Ausgaben des laufenden Betriebs gegenüberstellt — das Gegenstück zum Ergebnishaushalt der Stadt.",
    "Vermögensplan":  # 75
        "Der Teil des Wirtschaftsplans, in dem die Investitionen stehen: was gebaut oder gekauft wird und woher das Geld dafür kommt.",
    "Jahresüberschuss":  # 111
        "Was ein Betrieb in einem Jahr mehr eingenommen als ausgegeben hat.",
    "Jahresfehlbetrag":  # 71
        "Das Gegenteil des Jahresüberschusses: Ein Betrieb hat mehr ausgegeben als eingenommen. Wer den Fehlbetrag trägt, steht im Beschluss dazu.",
    "Zuwendung":  # 247
        "Geld, das die Stadt an Vereine, Verbände oder Einrichtungen gibt, ohne dafür eine Leistung zu kaufen — ein Zuschuss für einen festgelegten Zweck, über den hinterher abgerechnet wird.",
    "Gebührenbedarfsberechnung":  # 7 (+ Haushalts-Bereich)
        "Die Rechnung hinter einer Gebühr: Was kostet die Leistung, wie viele nehmen sie in Anspruch, wie viel muss jede*r zahlen, damit die Kosten gedeckt sind. Sie ist die Begründung jeder Gebührenänderung.",
    "AöR":  # 47
        "Kurz für Anstalt des öffentlichen Rechts: eine rechtlich selbstständige Einrichtung, die weiterhin der Stadt gehört, aber eigene Organe und eigene Bücher hat. Das Klinikum Oldenburg ist eine.",

    # ── Straßenausbau und Beiträge ────────────────────────────────────────
    # Der unverständlichste Wortcluster des ganzen Bestands: „Aufwands-
    # spaltungsbeschluss" steht 183 Mal in den Beschlüssen und nirgends sonst
    # im Leben.
    "Straßenausbaubeitrag":  # 149
        "Der Anteil an den Kosten für den Ausbau einer Straße, den die Anlieger zahlen — nicht für eine neue Straße, sondern für die Erneuerung einer vorhandenen. Wie viel, regelt eine Satzung des Rats.",
    "Aufwandsspaltung":  # 186
        "Ein Beschluss, der die Kosten eines Straßenausbaus nach Bestandteilen trennt — Fahrbahn, Gehweg, Beleuchtung, Entwässerung. So kann die Stadt einen fertigen Teil schon abrechnen, während der Rest noch gebaut wird.",
    "Teileinrichtung":  # 178
        "Ein einzelner Bestandteil einer Straße: Fahrbahn, Gehweg, Radweg, Parkstreifen, Beleuchtung, Grün oder Entwässerung. Die Beiträge werden für jede Teileinrichtung getrennt gerechnet.",
    "Widmung":  # 58
        "Der förmliche Akt, mit dem eine Fläche zur öffentlichen Straße wird. Erst danach darf sie jede*r benutzen — und die Stadt muss sie unterhalten.",
    "Einziehung":  # 32
        "Das Gegenstück zur Widmung: Eine Straße verliert ihre Eigenschaft als öffentlicher Weg, etwa weil dort gebaut werden soll.",

    # ── Bauleitplanung: die Schritte eines Bebauungsplans ─────────────────
    "vorhabenbezogen":  # 96
        "Ein Bebauungsplan, der auf ein ganz bestimmtes Vorhaben zugeschnitten ist: Wer bauen will, legt selbst einen Plan vor und verpflichtet sich vertraglich, ihn in einer Frist umzusetzen.",
    "Auslegung":  # 113
        "Die Wochen, in denen ein Planentwurf öffentlich einsehbar ist und jede*r dazu schriftlich Stellung nehmen kann — der zentrale Beteiligungsschritt im Baurecht. Mit „Auslegung“ ist hier nicht die Deutung eines Textes gemeint.",
    "Öffentlichkeitsbeteiligung":  # 85
        "Der Sammelbegriff für die Schritte, in denen Bürger*innen zu einem Plan Stellung nehmen können: früh im Verfahren zu den Grundzügen, später zum fertigen Entwurf.",
    "Abwägung":  # 28
        "Die Pflicht, vor einem Planbeschluss alle Interessen gegeneinander zu gewichten — Wohnen gegen Lärm, Natur gegen Gewerbe. Jede Einwendung muss dabei behandelt und das Ergebnis begründet werden.",
    "Grundzüge der Planung":  # 93
        "Der Kern eines Bebauungsplans, der sein Gesicht ausmacht. Werden sie nicht berührt, darf die Stadt ihn in einem vereinfachten Verfahren ändern — mit weniger Beteiligungsschritten.",
    "Satzungsbeschluss":  # 122
        "Der letzte Schritt eines Bebauungsplans: Der Rat beschließt ihn als Satzung, damit wird er verbindliches Recht.",
    "Geltungsbereich":  # 55
        "Das Gebiet, für das ein Plan oder eine Satzung gilt — auf der Planzeichnung als Linie eingetragen.",
    "Veränderungssperre":  # 59
        "Ein Beschluss, der das Bauen in einem Gebiet vorübergehend stoppt, solange dort ein Bebauungsplan erarbeitet wird. Er verhindert, dass Fakten geschaffen werden, bevor der Plan steht.",
    "Innenentwicklung":  # 11
        "Bauen im schon bebauten Bereich statt am Stadtrand: Baulücken, Brachen, Aufstockungen. Bebauungspläne dafür laufen in einem vereinfachten Verfahren.",
    "Erhaltungssatzung":  # 21
        "Eine Satzung, nach der in einem Gebiet nicht ohne Weiteres abgerissen oder umgebaut werden darf — um das Ortsbild zu schützen oder die Zusammensetzung der Bewohnerschaft zu erhalten.",
    "Erbbaurecht":  # 38
        "Das Recht, auf einem fremden Grundstück zu bauen, meist für 60 bis 99 Jahre gegen eine jährliche Zahlung. Die Stadt gibt das Grundstück so aus der Hand, ohne es zu verkaufen.",
    "Vorkaufsrecht":  # 7
        "Das Recht der Stadt, beim Verkauf bestimmter Grundstücke selbst einzusteigen — zu dem Preis, den Käufer und Verkäufer ausgehandelt haben.",
    "Fortschreibung":  # 103
        "Die Aktualisierung eines Plans oder Konzepts, ohne es neu zu erfinden: Zahlen, Ziele und Maßnahmen werden auf den heutigen Stand gebracht.",

    # ── Aufsicht und Zusammenarbeit ───────────────────────────────────────
    "Kommunalaufsicht":  # 9
        "Die Behörde, die prüft, ob die Stadt sich an Recht und Gesetz hält — für Oldenburg das Land Niedersachsen. Manche Beschlüsse, etwa zum Haushalt, brauchen ihre Genehmigung.",
    "Zweckverband":  # 8
        "Ein Zusammenschluss mehrerer Kommunen für eine gemeinsame Aufgabe, mit eigener Verwaltung und eigenem Haushalt.",
}


#: Längster Begriff zuerst, damit „Doppelhaushalt" vor „Haushalt" greift und
#: „Satzungsbeschluss" vor „Satzung".
_SORTIERT = sorted(BEGRIFFE, key=len, reverse=True)
#: Ein Buchstabe — auch Umlaut und ß. ``\w`` schlösse Ziffern und ``_`` ein,
#: ``[A-Za-z]`` verlöre die Umlaute.
_BUCHSTABE = r"[^\W\d_]"
#: Wortanfang (kein Buchstabe davor) + Begriff + Buchstaben-Endung. Damit
#: greifen Beugungen („Bebauungsplans", „Vergnügungsstätten"), aber KEINE
#: Komposita, die den Begriff hinten tragen — „Ausfallbürgschaft" ist deshalb
#: ein eigener Eintrag und kein Treffer auf „Bürgschaft". Wortgleich mit der
#: Regel im Frontend (``components/glossary-text.tsx``): Was die Antwort im
#: Text unterringelt, hat das Modell auch im Prompt gehabt.
_TREFFER = re.compile(
    rf"(?<!{_BUCHSTABE})({'|'.join(re.escape(b) for b in _SORTIERT)}){_BUCHSTABE}*",
    re.IGNORECASE)
_KANON = {b.lower(): b for b in BEGRIFFE}


def finde(text: str, max_n: int = 3) -> list[dict]:
    """Die erklärten Fachbegriffe in einem Text, in Reihenfolge des Auftauchens.

    Liefert je Treffer ``begriff`` (die Grundform aus :data:`BEGRIFFE`),
    ``treffer`` (die Form, die wirklich dasteht) und ``erklaerung``. Jeder
    Begriff kommt höchstens einmal vor — dieselbe Erklärung zweimal im Prompt
    kostet nur Platz.
    """
    gefunden: list[dict] = []
    gesehen: set[str] = set()
    for m in _TREFFER.finditer(text or ""):
        begriff = _KANON.get(m.group(1).lower())
        if not begriff or begriff in gesehen:
            continue
        gesehen.add(begriff)
        gefunden.append({"begriff": begriff, "treffer": m.group(0),
                         "erklaerung": BEGRIFFE[begriff]})
        if len(gefunden) >= max_n:
            break
    return gefunden
