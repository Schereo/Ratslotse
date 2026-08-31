// Woher eine gespeicherte Finanzzahl stammt — das Format, in dem
// `council_herkunft` über die Leitung kommt.
//
// Das Gegenstück zu `council/herkunft.py`. Es gibt genau EINEN Erzeuger
// (`CouncilStore.get_herkunft`, gespeist aus einer Tabelle und einer
// Dataclass) und neun Endpunkte, die sein Ergebnis unverändert durchreichen.
// Deshalb steht der Typ hier und nicht bei einer Seite.
//
// WARUM DAS FRÜHER ANDERS WAR — und warum es nicht zurück soll
//
// Bis 08/2026 schrieben fünf Dateien den Typ noch einmal aus, drei davon mit
// der Begründung: „Diese Seite soll nicht brechen, wenn der Schulden-Bereich
// seine Typen umbaut." Der Gedanke ist richtig — Bereiche sollen sich nicht
// gegenseitig festhalten —, trifft hier aber nicht zu: `Herkunft` gehört
// keinem Bereich. Es ist EIN Wire-Format, und wenn es sich ändert, müssen
// alle fünf Beschreibungen mit. Es gibt keinen Fall, in dem der
// Schulden-Bereich seine Herkunft sinnvoll allein umbaut.
//
// Was die Trennung stattdessen gebracht hat, war Drift — nachgemessen, bevor
// diese Datei entstand:
//
//   * drei der fünf kannten `document_id` nicht, obwohl die API es immer
//     mitschickt. Genau die Angabe, an der der Beleg-Chip hängt;
//   * zwei deklarierten `probe: string | null`, obwohl die Spalte NOT NULL
//     ist — die Seiten trugen totes Null-Handling;
//   * eine führte `probes` als optional, obwohl es nie fehlt.
//
// Die Seiten waren also nicht voreinander geschützt, sondern vor der
// Wahrheit. Ein Feld, das die API schickt und der Typ verschweigt, ist für
// die Oberfläche nicht vorhanden.
//
// Wer hier etwas ändert, ändert es für alle Haushalts-Seiten. Das ist keine
// Nebenwirkung, sondern der Zweck.

/** Der Ratsvorgang hinter einem Dokument: welches Gremium wann worüber
 *  entschieden hat (`CouncilStore.beschluesse_zu_dokumenten`).
 *
 *  `outcome` kommt ungefiltert — auch `vertagt` oder `abgelehnt`. Eine Zahl,
 *  deren Vorgang noch läuft, ist keine Zahl ohne Beleg; sie ist eine, bei der
 *  noch nichts entschieden ist, und das gehört dahin statt weggelassen. */
export type Ratsvorgang = {
  id: number;
  ksinr: number;
  kvonr: number | null;
  top: string | null;
  titel: string | null;
  outcome: string | null;
  vote: string | null;
  template_number: string | null;
  committee: string | null;
  datum: string | null;
};

/** Woher eine Zeile kommt — das gemeinsame Format aller Finanz-Schichten.
 *
 *  Die Feldliste folgt `council/herkunft.py` plus dem, was die Datenbank
 *  ergänzt (`id`, `fetched_at`) und was `get_herkunft` dazurechnet (`probes`,
 *  `beschluss`). */
export type Herkunft = {
  id: number;
  /** `ris` = Anlage im Ratsinformationssystem, `stadt` = Download von
   *  oldenburg.de, `lsn` = Tabelle des Landesamts für Statistik. */
  art: string;
  /** Die RIS-Dokumentnummer der Anlage — der stabile Anker, über den der
   *  Ratsvorgang gefunden wird. `null` bei `stadt`/`lsn`. */
  document_id: number | null;
  label: string | null;
  url: string | null;
  citation: string | null;
  page: number | null;
  /** Die bestandenen Proben als Schlüssel, kommagetrennt. NOT NULL in der
   *  Datenbank und im Konstruktor erzwungen — eine Zahl ohne Probe kommt
   *  nicht in den Bestand. */
  probe: string;
  /** Die Erklärsätze zu diesen Proben — kommen aus `herkunft.PROBEN` im
   *  Backend, damit sie einmal für Leser*innen geschrieben sind.
   *
   *  ACHTUNG, Namensfalle: Das gleichnamige `Herkunft.probes` in Python
   *  liefert die Proben-NAMEN, dieses Feld die ausformulierten Sätze. Beide
   *  heißen gleich und tragen Verschiedenes; wer im Backend nachschlägt,
   *  findet nicht, was hier ankommt. */
  probes: string[];
  probe_result: string | null;
  stand: string | null;
  /** „Zuletzt bestätigt", nicht „zuerst gesehen": Der Zeitstempel wandert bei
   *  jedem Lauf vorwärts, der die Zeile wiedersieht (`merke_herkunft`). */
  fetched_at: string;
  /** Der Beschluss, der das Dokument verabschiedet hat — `null`, wo keine
   *  Vorlage im Bestand steht. Ein erfundener Vorgang wäre der schlimmere
   *  Fehler. */
  official_text: Ratsvorgang | null;
};
