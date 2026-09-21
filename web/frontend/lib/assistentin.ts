/**
 * Was Lotti vom Bildschirm mitbekommt — die reine Logik, ohne React.
 *
 * **Die Regel dahinter.** Das Backend bekommt den normalisierten Pfad, die
 * Kennungen aus der Adresszeile und höchstens den Text des Elements, auf das
 * jemand gezeigt hat. **Nie die Query als ganze**: `?q=…` wäre eine
 * Suchanfrage, und die geht niemanden etwas an — dieselbe Grenze, die
 * `lib/aufrufe-melden.ts` für die Seitenaufrufe zieht.
 *
 * **Warum hier und nicht in der Komponente.** Jede Funktion in dieser Datei
 * ist rein und damit prüfbar (`assistentin.test.ts`). Die Grenzfälle — eine
 * Markierung, die im Lotti-Fenster selbst beginnt; ein Pfad mit
 * angehängtem Schrägstrich aus dem statischen Export — sind in einem
 * Browsertest kaum herstellbar und hier eine Zeile.
 */

/** Die Kennungen, die eine Seite über ihre Query trägt. */
export type Refs = {
  decision_id?: number;
  ksinr?: number;
  slug?: string;
  place_id?: string;
  year?: number;
  area?: string;
};

/** Was das Fenster ans Backend schickt. */
export type Bildschirm = {
  route: string;
  page_title: string;
  heading: string;
  element: { key: string | null; title: string; text: string } | null;
  selection: string;
  refs: Refs;
};

/** Die beiden DOM-Konstanten, die diese Datei braucht — als Zahl statt über
 *  das globale `Node`. Grund: Die Logik-Tests laufen ohne DOM-Nachbildung
 *  (web/frontend/CLAUDE.md: „Browser-Speicher ohne jsdom"), und dort gibt es
 *  kein `Node`. Die Werte stehen im DOM-Standard fest und ändern sich nicht. */
const ELEMENT_NODE = 1;
const POSITION_FOLLOWING = 4;

/** Die vier Register von `/council` — sie sind Seiten, keine Filter.
 *  Dieselbe Aufzählung wie in `kern/seitenaufrufe.py::COUNCIL_TABS`; steht
 *  sie auseinander, erklärt Lotti das falsche Register. */
const COUNCIL_TABS = ["decisions", "sessions", "themen", "analysis"];

/**
 * Pfad + Query → die Route, unter der das Backend sein Wissen ablegt.
 *
 * Spiegelt `kern/seitenaufrufe.py::normalisieren`: Schrägstrich am Ende weg
 * (der statische Export hängt ihn an), Query weg — mit der einen Ausnahme
 * `?tab=` auf `/council`, wo vier Register hinter einer Adresse liegen.
 */
export function routeAus(pathname: string | null | undefined, search = ""): string {
  let p = String(pathname ?? "/").split("?")[0].split("#")[0];
  if (!p.startsWith("/")) return "/";
  if (p.length > 1) p = p.replace(/\/+$/, "") || "/";
  if (p === "/council") {
    const tab = new URLSearchParams(search).get("tab");
    if (tab && COUNCIL_TABS.includes(tab)) return `/council?tab=${tab}`;
  }
  return p;
}

/**
 * Die Kennungen aus der Query — und nur sie.
 *
 * **Die Route entscheidet mit, und das ist kein Luxus.** `?id=` bedeutet nicht
 * überall dasselbe: Auf der Beschluss-Seite ist es eine Nummer
 * (`/council/decision?id=8525`), auf der Ort-Seite ein Kürzel
 * (`/council/ort?id=neu-donnerschwee`, siehe `lib/routes.ts::ortHref`). Ohne
 * die Route las die erste Fassung den Ort als Beschluss-Nummer, `Number()`
 * ergab `NaN`, und die Kennung fiel still heraus — Lotti wusste auf der
 * Ort-Seite nicht, um welchen Ort es geht. Gefunden hat das der Wächter gegen
 * umbenannte Werte, nicht ein Test dieses Moduls.
 *
 * Was hier nicht steht, kommt nicht mit: Ein neuer Parameter muss sich
 * entscheiden, statt mitzurutschen.
 */
export function refsAus(search = "", route = ""): Refs {
  const p = new URLSearchParams(search);
  const refs: Refs = {};
  const zahl = (wert: string | null): number | undefined => {
    const n = Number(wert);
    return wert && Number.isSafeInteger(n) && n > 0 ? n : undefined;
  };
  const id = p.get("id");
  if (route === "/council/ort") {
    // Hier ist `?id=` das Ortskürzel, keine Nummer.
    if (id) refs.place_id = id.slice(0, 120);
  } else {
    const n = zahl(id);
    if (n) refs.decision_id = n;
  }
  const ksinr = zahl(p.get("ksinr"));
  if (ksinr) refs.ksinr = ksinr;
  const jahr = zahl(p.get("year"));
  if (jahr && jahr >= 1990 && jahr <= 2100) refs.year = jahr;
  // Personen- und Themen-Seite (`lib/routes.ts`: personHref, themaHref).
  const slug = p.get("slug");
  if (slug) refs.slug = slug.slice(0, 120);
  // Die Stadtkarte wählt ihr Viertel über `?ort=` (karteHref). Das ist ein
  // Parametername unserer eigenen Adressen, kein gespeicherter Wert.
  const karte = p.get("ort");
  if (karte && !refs.place_id) refs.place_id = karte.slice(0, 120);
  // Bereichs-Steckbrief (`?name=`) und Steuer-Steckbrief (`?art=`) zeigen
  // beide auf einen Ausschnitt derselben Seite — im Backend heißt das `area`.
  const bereich = p.get("name") ?? p.get("art");
  if (bereich) refs.area = bereich.slice(0, 120);
  return refs;
}

/** Leerraum falten und hart schneiden — wie `assistant.kuerze` im Backend. */
export function kuerze(text: string, max: number): string {
  const sauber = (text ?? "").replace(/\s+/g, " ").trim();
  if (sauber.length <= max) return sauber;
  // An der Zeichen-, nicht an der Byte-Grenze schneiden: `slice` auf einem
  // String mit Emoji zerlegt sonst ein Surrogatpaar.
  return [...sauber].slice(0, max).join("").trimEnd() + " …";
}

/** Ein Name ist erst ab drei Zeichen ein Name.
 *
 *  **Sonst zerstört er die Seite, statt sich zu schützen:** Ein Konto, das
 *  „Al" heißt, hätte aus „Alexanderfeld" ein „exanderfeld" gemacht — und
 *  Lotti hätte über einen Stadtteil geredet, den es nicht gibt. Dieselbe
 *  Grenze steht im Backend (`council/assistant.py::ohne_namen`); laufen die
 *  beiden auseinander, streicht der eine, was der andere stehen lässt.
 */
const NAME_MIN = 3;

/** Regex-Sonderzeichen entschärfen — ein Anzeigename ist freier Text. */
function maskiere(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Den Anzeigenamen des Kontos aus einem Seitentext streichen.
 *
 * **Warum überhaupt.** Auf `/dashboard` ist die `h1` „Moin, Ratsfrau!" — der
 * Anzeigename steht also in der Überschrift, und die geht als `heading` ans
 * Backend, in die Kontext-Pille und in den Titel des gespeicherten Gesprächs.
 * Regel 9 des Assistentin-Plans („Anzeigename, E-Mail, Rolle als Wort: nie")
 * war damit auf der meistbesuchten Seite verletzt — nicht durch das Konto,
 * sondern durch die Seite.
 *
 * **An den Wortgrenzen**, nicht als blinder Textersatz: „Ina" steckt in
 * „Inanspruchnahme", „Jan" in „Januar". Ein Buchstabe davor oder dahinter
 * heißt: Das ist ein anderes Wort.
 */
export function ohneNamen(text: string, name?: string | null): string {
  const roh = (name ?? "").trim();
  if (!text || roh.length < NAME_MIN) return text;
  // Jeder Bestandteil einzeln: „Anna Musterfrau" steht in der Überschrift
  // oft nur als „Anna". Kurze Teile („de", „van") bleiben stehen.
  const teile = [roh, ...roh.split(/\s+/)].filter((t) => t.length >= NAME_MIN);
  let aus = text;
  for (const teil of teile) {
    aus = aus.replace(new RegExp(`(^|[^\\p{L}])${maskiere(teil)}(?![\\p{L}])`, "giu"), "$1");
  }
  // Was der Name hinterlässt: „Moin, !" → „Moin!"
  return aus.replace(/\s+([,;:!?.])/g, "$1").replace(/[,;:]\s*([!?.])/g, "$1")
    .replace(/\s{2,}/g, " ").trim();
}

/** Eine Überschrift, die nur grüßt — „Moin!", „Hallo!", „Guten Morgen!". */
const GRUSS_RE = /^(moin|hallo|hi|hey|guten (morgen|tag|abend)|willkommen)\b[\s!.,…]*$/i;

/**
 * Die Seitenüberschrift, wie Lotti sie sehen darf.
 *
 * Die `h1` ohne den Anzeigenamen — und ist danach nur noch ein Gruß übrig,
 * gar nichts: „Moin!" sagt nicht, auf welcher Seite jemand steht. Das
 * Fenster schickt dann `heading = ""`, und das Backend fällt auf den
 * Seitentitel zurück (dort „Heute").
 */
export function seitenUeberschrift(dok: Document, name?: string | null): string {
  const h1 = ohneNamen(dok.querySelector("h1")?.textContent?.trim() ?? "", name);
  return GRUSS_RE.test(h1) ? "" : h1;
}

/**
 * Der Titel des Browserfensters ohne den Namen der Anwendung.
 *
 * Er ist der Ersatz für eine Seite, deren `h1` nur grüßt — und die einzige
 * Stelle, an der der Client den kuratierten Seitennamen bekommt, ohne die
 * Titel aus `kern/knowledge.py` ein zweites Mal zu führen. Deshalb trägt
 * `/dashboard` seit diesem Riegel ein eigenes `metadata.title = "Heute"`.
 */
export function seitenTitel(dok: Document): string {
  return (dok.title ?? "").replace(/\s*[–—|]\s*Ratslotse\s*$/, "").trim();
}

/**
 * Wie die Seite im Fenster heißt — in der Kontext-Pille und in der Zäsur.
 *
 * Die `h1` ohne Namen und ohne Gruß, sonst der Fenstertitel. **Eine
 * Route→Titel-Tabelle entsteht hier bewusst nicht**: Die kuratierten Namen
 * stehen in `kern/knowledge.py::PAGES`, und eine zweite Liste im Client
 * veraltete lautlos — genau die Doppelung, die PR 10 vermieden hat.
 */
export function seitenName(dok: Document, name?: string | null): string {
  return seitenUeberschrift(dok, name) || seitenTitel(dok);
}

/** Eine Runde im Verlauf, soweit die reine Logik sie braucht. */
export type VerlaufsRunde = {
  /** Die normalisierte Route, auf der gefragt wurde (`routeAus`). Alte Runden
   *  aus dem `sessionStorage` haben sie nicht — sie zählen als fremd. */
  route?: string;
  /** Wie die Seite damals hieß (`seitenName`). Fehlt sie, tut es die Route. */
  seite?: string;
  answer: string;
  fehler?: boolean;
};

/**
 * Die Runden, die als Gedächtnis in den Prompt gehen — **nur die dieser
 * Seite**.
 *
 * **Warum nicht einfach die letzten drei.** Der Verlauf überlebt den
 * Seitenwechsel (das ist gewollt), das Gedächtnis darf es nicht: Auf der
 * Schulden-Seite standen am 21.09.2026 als Vorgeschichte drei Runden von der
 * Personen-Seite im Prompt — Lotti bezog „das" und „dieser Beschluss" dann
 * auf etwas, was gar nicht mehr auf dem Bildschirm war. Fremde Runden bleiben
 * **sichtbar** (man hat sie ja gestellt), sie reisen nur nicht mit.
 *
 * Leere und fehlgeschlagene Runden fallen wie bisher heraus: Eine
 * Fehlermeldung als „Antwort" im Prompt lehrt das Modell nichts.
 */
export function gedaechtnis<T extends VerlaufsRunde>(
  turns: T[], route: string, max = 3,
): T[] {
  return turns.filter((t) => t.answer && !t.fehler && t.route === route).slice(-max);
}

/**
 * Die Zäsur über einer Runde: „Jetzt auf: Schulden" — oder nichts.
 *
 * Gesetzt wird sie genau dann, wenn diese Runde auf einer **anderen** Seite
 * gestellt wurde als die davor. Über der ersten Runde steht keine: Dort ist
 * noch nichts gewechselt, und „Jetzt auf: Heute" als erste Zeile eines leeren
 * Verlaufs wäre Zierrat.
 */
export function zaesur<T extends VerlaufsRunde>(turns: T[], i: number): string | null {
  if (i <= 0 || i >= turns.length) return null;
  const jetzt = turns[i];
  if (jetzt.route === turns[i - 1].route) return null;
  // Gekürzt: Ein Beschlusstitel ist gern 90 Zeichen lang, und in Versalien
  // über drei Zeilen wäre die stille Zeile lauter als die Antwort darunter.
  const name = jetzt.seite || jetzt.route || "";
  return name ? kuerze(name, 60) : null;
}

/**
 * Der Überschriften-Pfad über einem Element: „Schulden › Rate-Treppe".
 *
 * Gesucht wird die nächste Überschrift ÜBER dem Element (in Dokument-
 * reihenfolge rückwärts) und die `h1` der Seite. Beides zusammen sagt
 * Lotti, wo auf der Seite sie gerade ist — ohne den Seitentext mitzuschicken.
 *
 * `name` ist der Anzeigename des Kontos; er wird gestrichen (s.
 * :func:`seitenUeberschrift`).
 */
export function ueberschriftenPfad(el: Element | null, dok: Document,
                                   name?: string | null): string {
  const h1 = seitenUeberschrift(dok, name);
  if (!el) return kuerze(h1, 200);
  const koepfe = [...dok.querySelectorAll("h2, h3")];
  let naechster = "";
  for (const k of koepfe) {
    // `compareDocumentPosition`: steht der Kopf VOR dem Element?
    if (k.compareDocumentPosition(el) & POSITION_FOLLOWING) {
      naechster = k.textContent?.trim() ?? "";
    }
  }
  const teile = [h1, ohneNamen(naechster, name)].filter(Boolean);
  return kuerze(teile.join(" › "), 200);
}

/**
 * Der markierte Text — aber nur, wenn er wirklich auf der Seite steht.
 *
 * Drei Ausschlüsse, alle gemessen an dem, was sonst passiert:
 * - **Im Lotti-Fenster selbst** markiert man, um zu zitieren, nicht um zu
 *   fragen. Ohne diesen Ausschluss fragte Lotti sich selbst.
 * - **In einem Eingabefeld** ist die Markierung getippter Text der Person;
 *   der gehört ihr, nicht dem Prompt.
 * - **Unter drei Zeichen** ist es ein Klick, keine Auswahl.
 */
export function auswahlText(sel: Selection | null, tabu: Element | null): string {
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return "";
  const knoten = sel.anchorNode;
  if (!knoten) return "";
  const el = knoten.nodeType === ELEMENT_NODE
    ? (knoten as Element)
    : knoten.parentElement;
  if (!el) return "";
  if (tabu && tabu.contains(el)) return "";
  if (el.closest("input, textarea, [contenteditable='true']")) return "";
  const text = kuerze(sel.toString(), 1000);
  return text.length >= 3 ? text : "";
}

/**
 * Der Text eines erklärbaren Elements — der einzige Seiteninhalt, der
 * mitgeht.
 *
 * Geerntet wird ausschließlich dieses Element: keine Nachbarn, keine Seite,
 * kein DOM. Wer auf die Rate-Treppe zeigt, meint die Rate-Treppe.
 */
export function ernteElement(el: HTMLElement): { key: string | null; title: string; text: string } {
  const key = el.getAttribute("data-erklaer");
  const titel = el.getAttribute("data-erklaer-titel")
    ?? el.querySelector("h2, h3, h4, [data-erklaer-kopf]")?.textContent
    ?? "";
  return {
    key: key ? kuerze(key, 80) : null,
    title: kuerze(titel, 200),
    text: kuerze(el.innerText ?? el.textContent ?? "", 1200),
  };
}

/**
 * Antworttext und Weiterreichung trennen.
 *
 * Der Server schneidet die `WEITER:`-Zeile ab, bevor er streamt — diese
 * Funktion ist der Gürtel zum Hosenträger: Reißt der Strom und kommt der Text
 * über `replace` als ganzes, steckt die Zeile noch darin.
 */
export function trenneWeiter(text: string): { text: string; next: "ratsfrage" | null } {
  const i = text.lastIndexOf("WEITER:");
  if (i < 0) return { text: text.trim(), next: null };
  const ziel = text.slice(i + 7).trim().split(/\s/)[0]?.replace(/[.,;:]$/, "").toLowerCase();
  return { text: text.slice(0, i).trim(), next: ziel === "ratsfrage" ? "ratsfrage" : null };
}

/** Eine Runde, soweit die Daumen-Regel sie braucht. */
export type BewertbareRunde = {
  answer: string;
  fehler?: boolean;
  /** Der Modus aus dem `done`-Rahmen: `"explain"` (Modell) oder
   *  `"deterministic"` (Glossar, Seiten-Wissen, Kurzfassung). Während des
   *  Stroms `null` — dann steht der Daumen noch nicht. */
  mode?: string | null;
  /** Kam die Antwort aus dem Ratsarchiv (der zweite Antwortweg im Fenster)? */
  ratsfrage?: boolean;
};

/**
 * Bekommt diese Runde einen Daumen?
 *
 * **Nur unter einer Antwort, die ein Modell geschrieben hat** — Lottis
 * Erklärung (`mode === "explain"`) und die Ratsantwort aus dem Fenster
 * (`ratsfrage`, die denselben Weg wie „Frag den Rat" nimmt und dort seit
 * jeher bewertbar ist).
 *
 * **Nicht unter deterministischen Antworten** (`mode === "deterministic"`:
 * Glossar-Eintrag, Seiten-Wissen, „Lotti erklärt's einfach"). Die sind
 * geprüfter Text, den das Fenster nur durchreicht; ein Daumen darunter
 * bewertete das Glossar, nicht die Assistentin — und landete in derselben
 * Quote wie ihre Erklärungen, die damit nicht mehr zu lesen wäre.
 *
 * Während des Stroms ist `mode` noch `null`: Der Daumen erscheint erst mit
 * dem `done`-Rahmen, und das ist richtig so — bewerten kann man erst, was
 * fertig dasteht.
 */
export function daumenZeigen(t: BewertbareRunde): boolean {
  if (!t.answer || t.fehler) return false;
  return t.ratsfrage === true || t.mode === "explain";
}
