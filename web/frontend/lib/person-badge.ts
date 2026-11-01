/**
 * Was am Personen-Badge der KI-Antworten Regel ist, ohne React: das Label und
 * die Frage, ob ein Nachname im Fließtext überhaupt als Name dasteht.
 * Gezeichnet wird das Badge in `components/qa-bausteine.tsx`.
 *
 * **Dieselben Regeln stehen in der App** (`QuestionsView.swift`:
 * `questionPersonBadgeLabel`, `questionHasNameSignal`);
 * `tests/test_personen_badge_gleich.py` hält die Wortlisten beider gleich.
 */

const _PARTEI_KUERZEL: [RegExp, string][] = [
  [/grün/i, "Grüne"], [/linke/i, "Linke"], [/spd/i, "SPD"], [/cdu/i, "CDU"],
  [/bsw/i, "BSW"], [/afd/i, "AfD"], [/^volt$/i, "Volt"], [/^fdp$/i, "FDP"],
  [/fdp\/volt/i, "FDP/Volt"], [/für oldenburg/i, "FO"], [/piraten/i, "Piraten"],
];

/** Das kurze Parteilabel neben einem Namen. Exportiert, weil dieselbe
 *  Schreibweise auch außerhalb der KI-Antworten gilt (Aufsichtsorgane im
 *  Beteiligungs-Steckbrief) — zwei Listen mit „Grüne" und „GRÜNE" wären zwei
 *  Sprachen für dieselbe Fraktion. */
export function parteiKuerzel(label: string | null): string {
  for (const [re, k] of _PARTEI_KUERZEL) if (label && re.test(label)) return k;
  return "Rat";
}

/** Was auf dem Badge STEHT — „ehem.", „Stadt", „beratend", „Aufsicht" oder das
 *  Parteikürzel. Muss mit `PersonBadge` deckungsgleich bleiben:
 *  `SprecherName` entscheidet daran, ob die Fraktion daneben noch etwas
 *  hinzufügt oder nur dasselbe wiederholt. */
export function personBadgeLabel(p: { aktiv: boolean; art: string; party: string | null }): string {
  return !p.aktiv ? "ehem."
    : p.art === "city" ? "Stadt"
    : p.art === "participation" ? "Aufsicht"
    // Beratende Ausschuss-Mitglieder sind keine Ratsleute: „Rat" (das Ergebnis
    // von parteiKuerzel(null)) behauptete bei ihnen ein Mandat, das sie nicht
    // haben (Tims Skiba-Befund 21.08.2026). Bis 11/2026 stand hier der
    // Datenbankwert „advisory" — beim Umbenennen der Werte ins Englische
    // (#950) war das Label mit umbenannt worden.
    : p.art === "advisory" ? "beratend"
    : parteiKuerzel(p.party);
}

// ---------------------------------------------------------------------------
// Steht der Nachname ALS NAME da — oder ist er nur ein Wort?
// ---------------------------------------------------------------------------
//
// Das Badge hing bis 11/2026 an jedem großgeschriebenen Wort, das im Lexikon
// genau einer Person gehört. Nachnamen sind aber oft gewöhnliche Wörter: Lotti
// antwortete „Danke der Nachfrage!" und bekam das Badge von André Danke
// (beratendes Mitglied, Tims Befund 01.11.2026). Gemessen über die 622
// gespeicherten Antworten auf dev: 48 von 203 Badges waren so falsch, 44 davon
// das Wort „Streit" (Tim Streit, Stadtverwaltung), dazu „Bremer Heerstraße"
// und „Eversten Holz".
//
// Ein eindeutiger Nachname bekommt sein Badge deshalb nur noch, wenn der Text
// ihn als Namen ausweist: ein Vorname davor („Ulf Prange", auch „Jonas
// Christopher Höpken"), eine Anrede oder ein Amt davor („Herr Adler",
// „SPD-Ratsmitglied Prange", „Einwohnerin Pieper"), ein Verb des Sagens direkt
// daneben („Sprenger sagte", „kritisierte Höpken", „sprach sich Prange") oder
// eine Parteiklammer dahinter („Prange (SPD)"). Dieselbe Vorsicht wie bei den
// Namensvettern (Tims Oltmanns-Befund): lieber kein Badge als ein geratenes.
// Mit diesem Modul nachgemessen: 144 Badges bleiben, alle 48 falschen sind
// weg, und 11 echte Nennungen ohne solches Zeichen gehen mit („während Höpken
// …", „**Sander**, …").

const fold = (t: string) =>
  t.toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss");

/** Anreden, die als eigenes Wort vor dem Namen stehen (gefaltet, ohne Punkt). */
export const NAME_TITLES = ["herr", "herrn", "frau", "dr", "prof"];

/** Ämter und Rollen — als Wortende, damit Zusammensetzungen mitzählen:
 *  „SPD-Ratsmitglied", „Oberbürgermeister", „BSW-Vertreter", „Einwohnerin". */
export const NAME_OFFICE_ENDINGS = [
  "ratsmitglied", "ratsherr", "ratsherrn", "ratsfrau", "mitglied",
  "buergermeister", "buergermeisterin", "stadtrat", "stadtraetin",
  "stadtbaurat", "stadtbauraetin", "kaemmerer", "kaemmerin",
  "beigeordnete", "beigeordneter", "dezernent", "dezernentin",
  "vorsitzende", "vorsitzender", "vertreter", "vertreterin",
  "sprecher", "sprecherin", "redner", "rednerin",
  "leiter", "leiterin", "einwohner", "einwohnerin",
];

/** Verben des Sagens und Stellungnehmens (gefaltet, Präteritum Singular; die
 *  Prüfung nimmt „-n"/„-en" für den Plural dazu). Nur solche, die ein
 *  gewöhnliches Wort nicht tun kann: „zeigte" fehlt mit Absicht, denn „der
 *  Streit zeigte, dass …". */
export const NAME_VERBS = [
  "sagte", "sprach", "betonte", "kritisierte", "verwies", "erklaerte",
  "forderte", "beantragte", "bezeichnete", "aeusserte", "ergaenzte", "wandte",
  "schlug", "begruesste", "erwartete", "unterstuetzte", "fragte", "antwortete",
  "meinte", "warnte", "mahnte", "entgegnete", "widersprach", "plaedierte",
  "berichtete", "regte", "lehnte", "stimmte", "kuendigte", "wuenschte",
  "bemaengelte", "bedauerte", "lobte", "bat", "raeumte", "monierte",
  "sicherte", "schilderte", "nannte", "verlangte", "wies", "beklagte",
  "bekraeftigte", "erinnerte", "appellierte", "versprach", "bestaetigte",
  "begruendete", "vertrat",
];

/** Namenspartikel zwischen Anrede und Nachnamen: „Ratsherr van Ellen". */
export const NAME_PARTICLES = ["van", "von", "de", "ter", "ten"];

const TITLES = new Set(NAME_TITLES);
const PARTICLES = new Set(NAME_PARTICLES);
const OFFICE_RE = new RegExp(`(${NAME_OFFICE_ENDINGS.join("|")})$`);
const VERB_RE = new RegExp(`^(${NAME_VERBS.join("|")})(n|en)?$`);

/** Das Wort, das direkt vor `pos` endet — nur wenn dazwischen nichts als
 *  Leerraum steht. Ein Satzzeichen trennt („sagte. Krogmann" ist kein
 *  Sprecher); einzige Ausnahme ist der Abkürzungspunkt („Dr. Baak"). */
function wordBefore(text: string, pos: number): { word: string; start: number } | null {
  const head = text.slice(0, pos);
  const m = head.match(/([A-Za-zÄÖÜäöüßÀ-ÿ-]+)(\.?)\s+$/);
  if (!m) return null;
  const word = fold(m[1]);
  if (m[2] && !TITLES.has(word)) return null;
  return { word, start: head.length - m[0].length };
}

function wordAfter(text: string, pos: number): string | null {
  const m = text.slice(pos).match(/^\s+([A-Za-zÄÖÜäöüß]+)/);
  return m ? fold(m[1]) : null;
}

/** `start`/`end` umschließen den Nachnamen in `text`; `firstName` ist der
 *  gefaltete Vorname aus dem Lexikon. */
export function hasNameSignal(text: string, start: number, end: number,
                              firstName: string | null | undefined): boolean {
  let before = wordBefore(text, start);
  if (before && PARTICLES.has(before.word)) before = wordBefore(text, before.start);
  if (before) {
    const given = new Set((firstName || "").split(/[\s-]+/).filter(Boolean));
    if (firstName) given.add(firstName);
    if (given.has(before.word)) return true;
    if (TITLES.has(before.word) || OFFICE_RE.test(before.word)) return true;
    if (VERB_RE.test(before.word)) return true;
    // „sprach sich Prange für … aus"
    if (before.word === "sich") {
      const further = wordBefore(text, before.start);
      if (further && VERB_RE.test(further.word)) return true;
    }
  }
  const after = wordAfter(text, end);
  if (after && VERB_RE.test(after)) return true;
  const bracket = text.slice(end).match(/^\s*\(([^()]{2,60})\)/);
  return !!bracket && parteiKuerzel(bracket[1]) !== "Rat";
}
