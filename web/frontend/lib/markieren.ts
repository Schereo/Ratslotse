/**
 * „Markieren statt Modus": Wer auf der Seite Text markiert, bekommt an der
 * Markierung einen kleinen Knopf „Lotti fragen" — die reine Logik dazu.
 *
 * **Warum es den Erklär-Modus nicht mehr gibt** (Tim, 23.09.2026): „Dieses
 * ‚Frag mich zu dieser Seite‘ und dann kann man irgendwas anklicken — das ist
 * so mega komisch, keiner versteht, wie das funktioniert, selbst bei mir hat
 * es gedauert." Ein Modus verlangt, dass man erst weiß, dass es ihn gibt, und
 * dann, was er mit einem macht. Markieren kennt jede*r schon; der Knopf
 * antwortet auf eine Handlung, die gerade passiert ist, statt auf eine, die
 * man erst lernen muss.
 *
 * **Warum hier und nicht in der Komponente.** Grenzen (wie lang, wie kurz)
 * und die Lage des Knopfs sind reine Rechnungen; im Browsertest ist ein
 * Knopf am unteren Fensterrand oder eine 3.000-Zeichen-Markierung mühsam
 * herzustellen, hier ist es eine Zeile (`markieren.test.ts`).
 */
import { auswahlErlaubt, kuerze } from "./assistentin";

/** Die längste Markierung, die mitgeht — **dieselbe Zahl wie
 *  `council/assistant.py::SELECTION_MAX`**, die `POST /council/explain` als
 *  `max_length` durchsetzt. Laufen die beiden auseinander, antwortet der
 *  Server mit 422, und im Fenster steht „Dazu kann ich gerade nichts sagen". */
export const SELECTION_MAX = 1000;

/** Ab zwei Zeichen ist es eine Auswahl: „VE" oder „ÖV" sind Abkürzungen, nach
 *  denen man fragen will. Ein einzelnes Zeichen ist ein verrutschter Klick. */
export const MARKIERUNG_MIN = 2;

/** Wie viel vom Zitat im Verlauf steht — ein ganzer Absatz als Frage-Blase
 *  wäre lauter als die Antwort darunter. Mitgeschickt wird trotzdem alles. */
export const ZITAT_ANZEIGE_MAX = 80;

/**
 * Die Markierung, so wie sie ans Backend geht — oder `null`, wenn sie keine
 * ist.
 *
 * Gefaltet (Zeilenumbrüche aus Tabellen werden Leerzeichen) und, wenn nötig,
 * **so gekürzt, dass sie samt „ …" in `SELECTION_MAX` passt** (`kuerze`
 * zählt das Auslassungszeichen seit #1512 mit). Das Flag `gekuerzt` sagt dem
 * Fenster, dass es das dazuschreiben soll.
 */
export function markierungAufbereiten(roh: string | null | undefined):
  { text: string; gekuerzt: boolean } | null {
  const sauber = kuerze(roh ?? "", Number.MAX_SAFE_INTEGER);
  if ([...sauber].length < MARKIERUNG_MIN) return null;
  if ([...sauber].length <= SELECTION_MAX) return { text: sauber, gekuerzt: false };
  return { text: kuerze(sauber, SELECTION_MAX), gekuerzt: true };
}

/** Die Marken um den markierten Teil in seiner Zeile. **Dieselben Zeichen wie
 *  in `council/assistant.py::MARKE_AUF/MARKE_ZU`** — dort wird der Teil
 *  wieder herausgelöst (Glossar-Abkürzung) und dem Modell erklärt. */
export const MARKE_AUF = "»";
export const MARKE_ZU = "«";

/** Leerraum falten, aber die Ränder zur Markierung stehen lassen: „Oldenburg
 *  · »8,0 Mio. €«" braucht das Leerzeichen vor der Marke, „Kredit»aufnahme«"
 *  darf keins bekommen. Stehen die Marken-Zeichen schon auf der Seite, werden
 *  sie zu einfachen Anführungszeichen — sonst wüsste der Server nicht mehr,
 *  welches Paar unseres ist. */
function falteKontext(text: string): string {
  return (text ?? "").replace(/\s+/g, " ").replace(/[»«]/g, "\"");
}

/**
 * Die Markierung IN IHRER ZEILE: `Mai 2026 · Kreditaufnahme · Bäderbetrieb
 * Oldenburg · »8,0 Mio. €« · 3,43 %`.
 *
 * **Der Fehler, gegen den das steht** (Review zu #1517, 23.09.2026): Auf
 * `/haushalt/schulden` stehen im Baustein „Kredite und Zinsen" ZWEI Kredite
 * über 8,0 Mio. € des Bäderbetriebs. Markiert war der aus der Zeile „Mai 2026
 * … 3,43 %"; mitgeschickt wurden die drei Wörter und der ganze Baustein —
 * und Lotti erklärte den anderen (06.08.2026, 3,46 %). Die Frage war
 * mehrdeutig, nicht das Modell schlecht: Nur die Zeile sagt, WELCHE 8,0 Mio.
 * gemeint sind.
 *
 * `vor` und `nach` sind der Text der Zeile vor und nach der Markierung.
 * Ist beides leer (die Markierung IST die Zeile), bleibt es beim markierten
 * Text allein. Passt die Zeile samt Marken nicht in `SELECTION_MAX`, wird
 * sie um die Markierung herum gekürzt — die Markierung selbst nie. Ist schon
 * die Markierung zu lang, geht nur sie (gekürzt) mit.
 */
export function markierungInZeile(vor: string, markiert: string, nach: string):
  { text: string; gekuerzt: boolean } | null {
  const m = markierungAufbereiten(markiert);
  if (!m) return null;
  let links = [...falteKontext(vor).trimStart()];
  let rechts = [...falteKontext(nach).trimEnd()];
  if (!links.join("").trim() && !rechts.join("").trim()) return m;
  if (m.gekuerzt) return m;
  const kern = [...`${MARKE_AUF}${m.text}${MARKE_ZU}`];
  const frei = SELECTION_MAX - kern.length;
  if (links.length + rechts.length > frei) {
    // Beide Seiten bekommen die Hälfte; was eine nicht braucht, bekommt die
    // andere. Je gekürzter Seite kostet das „… " zwei Zeichen.
    const ELL = 2;
    let l = Math.min(links.length, Math.floor(frei / 2));
    let r = Math.min(rechts.length, frei - l);
    l = Math.min(links.length, frei - r);
    if (l < links.length) l = Math.max(0, l - ELL);
    if (r < rechts.length) r = Math.max(0, r - ELL);
    links = l < links.length ? [..."… ", ...links.slice(links.length - l)] : links;
    rechts = r < rechts.length ? [...rechts.slice(0, r), ..." …"] : rechts;
  }
  return { text: [...links, ...kern, ...rechts].join(""), gekuerzt: false };
}

/** Der markierte Text der Seite, bereit für den Prompt — oder "".
 *
 *  Die Ausschlüsse (Lottis Fenster, Eingabefelder) stehen in
 *  `assistentin.ts::auswahlErlaubt`, Länge und Kürzung hier. */
export function auswahlText(sel: Selection | null, tabu: Element | null,
                            fokus: Element | null = null): string {
  if (!auswahlErlaubt(sel, tabu, fokus)) return "";
  return markierungAufbereiten(sel!.toString())?.text ?? "";
}

/** Eine Frage samt Zitat, wie sie im Verlauf steht und als Gedächtnis
 *  mitgeht: „„391,5 Mio. €“ — Was bedeutet das?".
 *
 *  **Warum auch im Gedächtnis.** Die Frage selbst ist „Was bedeutet das?" —
 *  ohne das Zitat hätte ein „und warum so viel?" in der nächsten Runde nichts,
 *  worauf es sich beziehen kann, sobald die Markierung weg ist. */
export function frageMitZitat(t: { question: string; zitat?: string | null }): string {
  if (!t.zitat) return t.question;
  const zitat = `„${kuerze(t.zitat, ZITAT_ANZEIGE_MAX)}“`;
  return t.question ? `${zitat} — ${t.question}` : zitat;
}

export type Rechteck = { top: number; bottom: number; left: number; right: number };

export type KnopfLage = {
  /** Linke obere Ecke des Knopfs, in Fenster-Koordinaten (`position: fixed`). */
  x: number;
  y: number;
  /** `unter`: unter dem Ende der Markierung (der Normalfall). `ueber`: über
   *  ihrem Anfang, weil unten kein Platz war. `rand`: Die Markierung füllt
   *  den ganzen Bildschirm — dann am unteren Rand, und ein Stück Text liegt
   *  unter dem Knopf, weil es keinen Platz gibt, an dem keiner liegt. */
  lage: "unter" | "ueber" | "rand";
};

/**
 * Wo der Knopf steht — oder `null`, wenn die Markierung aus dem Bild ist.
 *
 * **Unter dem Ende, nicht darüber.** Über der Markierung sitzt auf dem Handy
 * das Auswahlmenü des Systems (iOS „Kopieren · Nachschlagen …", Android
 * dasselbe als schwebende Leiste); ein Knopf dort läge darunter oder
 * darüber, und beides ist falsch. Unter dem Ende sitzt dafür der Anfasser,
 * mit dem man die Auswahl verlängert — deshalb ist `abstand` am Touchgerät
 * größer als der Anfasser hoch ist (die Komponente wählt ihn).
 *
 * **Nie über dem Text.** Passt der Knopf unten nicht mehr ins Fenster
 * (Markierung ganz unten), steht er über dem ANFANG. Nur wenn beides nicht
 * geht, weil die Markierung den ganzen Bildschirm füllt, klebt er am Rand.
 *
 * Waagrecht mittig unter dem Ende der Auswahl, im Fenster gehalten.
 */
export function knopfPosition(opts: {
  start: Rechteck;
  ende: Rechteck;
  knopf: { breite: number; hoehe: number };
  fenster: { breite: number; hoehe: number };
  abstand: number;
  /** Mindestabstand zu jedem Fensterrand. */
  rand?: number;
  /** Was unten nicht zur Seite gehört (die Tab-Leiste auf dem Handy). */
  unten?: number;
}): KnopfLage | null {
  const { start, ende, knopf, fenster, abstand } = opts;
  const rand = opts.rand ?? 8;
  const unten = Math.max(0, opts.unten ?? 0);
  const boden = fenster.hoehe - unten - rand;
  // Weggescrollt: Keine Zeile der Markierung ist mehr zu sehen. Ein Knopf,
  // der auf etwas zeigt, das man nicht sieht, zeigt auf nichts.
  if (ende.bottom < 0 || start.top > fenster.hoehe - unten) return null;

  const mitte = ende.right;
  const maxX = Math.max(rand, fenster.breite - knopf.breite - rand);
  const x = Math.round(Math.min(Math.max(mitte - knopf.breite / 2, rand), maxX));

  const yUnter = ende.bottom + abstand;
  if (yUnter >= rand && yUnter + knopf.hoehe <= boden) {
    return { x, y: Math.round(yUnter), lage: "unter" };
  }
  const yUeber = start.top - abstand - knopf.hoehe;
  if (yUeber >= rand && yUeber + knopf.hoehe <= boden) {
    return { x, y: Math.round(yUeber), lage: "ueber" };
  }
  return { x, y: Math.round(Math.max(rand, boden - knopf.hoehe)), lage: "rand" };
}
