/** Kurze, allgemeinverständliche Erklärungen zu Fachbegriffen aus der
 *  Kommunalpolitik & dem Baurecht. Werden im Quiz (und potenziell anderswo) als
 *  Hover/Tap-Tooltip unter den Begriff gelegt. Schlüssel = Grundform des Begriffs;
 *  gematcht wird per Wortanfang (case-insensitiv), sodass Beugungen wie
 *  „Bebauungsplans" oder „Vergnügungsstätten" mitgefunden werden. */
export const GLOSSARY: Record<string, string> = {
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
  // Homonym-Falle: In Produkt-Steckbriefen der Stadt („Erschließung der
  // Archivbestände") meint das Wort das Ordnen und Verzeichnen, nicht den
  // Straßenbau. Der Zusatz steht hier, weil die Erklärung sonst genau dort
  // falsch wäre, wo sie automatisch erscheint.
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
  // Krankenhaus-Versorgungsstufen (niedersächsische Krankenhausplanung) —
  // tauchen in Fragen zum Klinikum auf.
  "Maximalversorgung":
    "Die höchste Krankenhaus-Stufe: deckt praktisch alle Fachrichtungen ab, inklusive hochspezialisierter Medizin — in der Region meist nur ein Haus (hier: das Klinikum Oldenburg).",
  "Schwerpunktversorgung":
    "Die zweithöchste Krankenhaus-Stufe: deutlich mehr Fachabteilungen als die Grundversorgung, aber nicht das komplette Spektrum eines Maximalversorgers.",
  "Grundversorgung":
    "Die Basis-Stufe eines Krankenhauses: Innere Medizin und Chirurgie für die wohnortnahe Standardversorgung.",
  "Fachkrankenhaus":
    "Ein Krankenhaus, das auf ein bestimmtes Gebiet spezialisiert ist (z. B. Psychiatrie oder Lungenheilkunde), statt die volle Breite anzubieten.",
  // Haushalts-Begriffe (kommunale Doppik) — für die Haushalts-Quizfragen.
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
  // Ergänzt 16.08.2026 für den Haushalts-Bereich: die Wörter, über die man
  // beim Lesen einer Haushaltsseite zuerst stolpert.
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
  // Wörter aus den Produkt-Steckbriefen der Teilhaushaltspläne. Sie stehen dort
  // im Verwaltungsdeutsch der Stadt; ungefiltert durchgereicht wäre die
  // Produktseite unlesbar. Beide Wirkungskreis-Formen sind erklärt, weil die
  // Pläne beide Schreibweisen führen („übertragend" ist ihr eigener Tippfehler).
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
  // Ergänzt 16.08.2026: die Wörter, die im Haushalts-Bereich auf der Seite
  // stehen, ohne dass sie dort jemand erklärt — vor allem die Vokabeln aus den
  // Jahresabschlüssen und aus dem Schlussbericht des Rechnungsprüfungsamts.
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
  // Ergänzt mit /haushalt/konzern: die Vokabeln des Gesamtabschlusses. Sie
  // stehen unvermeidlich auf der Seite (sie sind die Namen der Sache), und
  // ungeklärt ist jedes einzelne ein Grund wegzuklicken.
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
  "Beteiligung":
    "Ein Anteil der Stadt an einem Unternehmen. Bei einer Mehrheit bestimmt sie mit, bei kleineren Anteilen sitzt sie eher mit am Tisch als am Steuer.",
  "Eigenkapitalmethode":
    "Ein Weg, ein Unternehmen in die Gesamtrechnung aufzunehmen, an dem die Stadt zwar beteiligt ist, das sie aber nicht allein bestimmt: Statt aller Einnahmen und Ausgaben fließt nur der Anteil am Wert des Unternehmens ein. Fachlich auch „Equity-Methode“.",
  "Equity-Methode":
    "Anderes Wort für die Eigenkapitalmethode: Von einem Unternehmen, an dem die Stadt nur beteiligt ist, geht nicht das ganze Geschäft in die Gesamtrechnung ein, sondern nur der Anteil an seinem Wert.",
  "Vollkonsolidierung":
    "Die vollständige Aufnahme eines Betriebs in die Gesamtrechnung: Alle seine Einnahmen und Ausgaben zählen mit, so als gehörten sie der Stadt direkt.",
};
