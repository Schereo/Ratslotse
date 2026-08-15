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
  "Erschließung":
    "Die Herstellung von Straßen, Wegen, Kanälen und Leitungen, damit ein Grundstück bebaut und genutzt werden kann.",
  "Nutzungsänderung":
    "Wenn ein Gebäude künftig anders genutzt wird als bisher (z. B. Laden statt Wohnung) — oft genehmigungspflichtig.",
  "Sanierungsgebiet":
    "Ein förmlich festgelegtes Gebiet, das die Stadt gezielt städtebaulich aufwertet (Städtebauförderung).",
  "Haushalt":
    "Der Plan der Stadt über ihre Einnahmen und Ausgaben, jährlich vom Rat beschlossen.",
  "Doppelhaushalt":
    "Ein Haushalt, der gleich für zwei Jahre auf einmal beschlossen wird.",
  "Bürgerbegehren":
    "Ein Weg, mit dem Bürger:innen einen Bürgerentscheid zu einer kommunalen Frage erzwingen können — wenn genug Unterschriften zusammenkommen.",
  "Bürgerentscheid":
    "Eine direkte Abstimmung der Bürger:innen über eine kommunale Sachfrage, so bindend wie ein Ratsbeschluss.",
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
    "Steuer auf Grundstücke und Gebäude, gezahlt von Eigentümerinnen und Eigentümern — über die Nebenkosten meist auch von Mieterinnen und Mietern. Den Hebesatz beschließt der Rat.",
  "Haushaltssatzung":
    "Der förmliche Beschluss, mit dem der Rat den Haushalt in Kraft setzt — darin stehen auch die Hebesätze für das Jahr.",
  "Doppik":
    "Die kaufmännische Buchführung der Kommunen: Sie zeigt nicht nur Zahlungen, sondern auch den Werteverzehr (etwa Abnutzung von Gebäuden).",
};
