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

// ---------------------------------------------------------------------------
// Mehrere Personen mit demselben Nachnamen — was der Text sonst noch belegt
// ---------------------------------------------------------------------------
//
// Bis 11/2026 entschied bei Namensvettern NUR das eine Wort direkt vor dem
// Nachnamen. Drei Fälle aus einer Antwort zu den Weser-Ems-Hallen (Tims Befund
// 09.11.2026) blieben dadurch ohne Badge:
//
// * „Ruth Regina Drügemöller": Das Lexikon führt sie zweimal (mit und ohne
//   Zweitnamen), beide mit Vorname Ruth — und vor dem Nachnamen steht
//   „Regina". Der volle Name im Text passt aber genau auf EINEN Eintrag.
// * „Pfeiffer" und „Paul" in Listenpunkten, die mit „**FDP** …" bzw.
//   „**AfD** …" beginnen: Unter Daniela (FDP) und Anna Pfeiffer (Caritas) bzw.
//   Andreas (AfD), Anna (Caritas) und Matthias Paul (Verwaltung) ist genau
//   eine Person dieser Fraktion im Rat. Die Partei steht im Text, nur nicht
//   direkt am Namen.
//
// Beides ist belegt, nichts davon geraten — dieselbe Regel wie bei den
// Debattenzeilen, die ihre Fraktion mitbringen.

type Kandidat = {
  name: string | null; party: string | null; art: string;
  phasen?: { party: string | null }[] | null;
};

const TITEL_IM_NAMEN = /^(dr|prof)\.?$/i;

/** Die großgeschriebenen Wörter direkt vor `pos`, nur durch Leerraum getrennt
 *  (höchstens `max`) — „Ruth Regina" vor „Drügemöller". */
export function namensWoerterDavor(text: string, pos: number, max = 3): string[] {
  const woerter: string[] = [];
  let kopf = text.slice(0, pos);
  while (woerter.length < max) {
    const m = kopf.match(/([A-ZÄÖÜ][A-Za-zÄÖÜäöüß-]+)\s+$/);
    if (!m) break;
    woerter.unshift(m[1]);
    kopf = kopf.slice(0, kopf.length - m[0].length);
  }
  return woerter;
}

/** Unter mehreren Kandidaten den, dessen voller Name genau so im Text steht. */
export function perVollname<T extends Kandidat>(kandidaten: T[], vornamen: string[],
                                                 nachname: string): T | null {
  if (vornamen.length === 0) return null;
  // Von hinten: „Laut Protokoll sagte Ruth Regina Drügemöller" — die Wörter
  // davor gehören nicht zum Namen; probiert wird die längste passende Folge.
  for (let ab = 0; ab < vornamen.length; ab++) {
    const ziel = fold([...vornamen.slice(ab), nachname].join(" "));
    const treffer = kandidaten.filter((k) => k.name && fold(
      k.name.split(/\s+/).filter((w) => !TITEL_IM_NAMEN.test(w)).join(" ")) === ziel);
    if (treffer.length === 1) return treffer[0];
  }
  return null;
}

/** FDP und Volt bilden eine Gruppe: Die Protokolle labeln mal die Gruppe
 *  („FDP/Volt"), mal die Einzelpartei. Alles andere muss exakt stimmen. */
export function parteienPassen(a: string, b: string): boolean {
  if (a === b) return true;
  const gruppe = new Set(["FDP", "Volt", "FDP/Volt"]);
  return gruppe.has(a) && gruppe.has(b) && (a === "FDP/Volt" || b === "FDP/Volt");
}

/** Die Partei, die ein Listenpunkt vorne fett nennt: „**FDP** unterstützt …". */
export function parteiAusListenpunkt(zeile: string): string | null {
  const m = zeile.trim().match(/^\*\*([^*]{2,40})\*\*/);
  if (!m) return null;
  const k = parteiKuerzel(m[1]);
  return k === "Rat" ? null : k;
}

/** Unter mehreren Kandidaten das EINE Ratsmitglied dieser Fraktion. */
export function perPartei<T extends Kandidat>(kandidaten: T[], kuerzel: string): T | null {
  const treffer = kandidaten.filter((k) => k.art === "council" && (
    parteienPassen(parteiKuerzel(k.party), kuerzel)
    || (k.phasen ?? []).some((ph) => parteienPassen(parteiKuerzel(ph.party), kuerzel))));
  return treffer.length === 1 ? treffer[0] : null;
}
