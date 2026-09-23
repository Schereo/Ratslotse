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
 *
 * **Auch die Lotsen-Runde (`mode === "local"`) bekommt keinen.** Sie entsteht
 * im Browser aus den Anker-Titeln der Seite, ohne Server und ohne Modell — es
 * gibt dort nichts zu benoten und niemanden, der die Note entgegennähme (der
 * Endpunkt wird nicht gerufen).
 */
export function daumenZeigen(t: BewertbareRunde): boolean {
  if (!t.answer || t.fehler) return false;
  return t.ratsfrage === true || t.mode === "explain";
}

/* ── „Zeig mir": Lotti als Lotsin auf der Seite ────────────────────────────
 *
 * Die Anker (`data-erklaer` samt `data-erklaer-titel`, gesetzt über
 * `useErklaerAnker`) sind eine **Landkarte der Seite, die der Client schon
 * hat**. Die häufigste Frage nach „Was ist das?" ist „Wo finde ich …?" — und
 * die lässt sich damit ohne einen einzigen Modellaufruf beantworten: Titel
 * gegen Frage halten, Chip anbieten, hinscrollen.
 *
 * **Warum ein Wortabgleich und kein Modell.** Derselbe Grund wie bei
 * `generische_frage` im Backend: Wo etwas steht, ist keine Ermessensfrage.
 * Ein Modell dafür kostet je Klick Geld und kann die Antwort nur
 * verschlechtern — es kennt die Titel nicht besser als der Abgleich, es
 * könnte sie aber erfinden.
 *
 * **Die Grenze:** nur Anker, nie freie DOM-Suche. Trifft nichts, geht die
 * Frage wie bisher ans Modell — mit der Ankerliste im Kontext, damit die
 * Antwort wenigstens den Baustein beim Titel nennen kann.
 */

/** Ein Baustein der Seite: sein `data-erklaer`-Schlüssel und sein Titel.
 *
 *  **Beides identifiziert ihn, nicht der Schlüssel allein.** Der Schlüssel
 *  kommt aus `useErklaerAnker(name, titel)` und ist nur so eindeutig, wie der
 *  Name es ist — auf `/haushalt/schulden` tragen zwei Zeitreihen denselben
 *  (`haushalt-schulden.zeitreihe`, „Schulden total" und „Verbürgt und selbst
 *  geschuldet"; gemessen im Browser am 22.09.2026). Ein Abgleich nur über den
 *  Schlüssel hätte die zweite verschluckt und beim Zeigen immer die erste
 *  angesprungen. */
export type Anker = { key: string; titel: string };

/** Höchstens so viele Anker gehen mit — in den Abgleich wie in den Prompt.
 *  Dieselbe Zahl wie `assistant.ANKER_MAX` im Backend; eine Seite mit 40
 *  Bausteinen (der Kassenzettel-Haushalt) machte aus der Liste sonst einen
 *  eigenen Prompt-Block von der Größe des Seitenwissens. */
export const ANKER_MAX = 20;
/** Und so lang darf ein Titel sein (Backend: `ANKER_TITEL_MAX`). */
export const ANKER_TITEL_MAX = 80;

/** Kleinschreibung ohne Umlaute — dieselbe Faltung wie
 *  `council/assistant.py::falte`. Läuft sie auseinander, erkennt der eine
 *  „Zinsen", was der andere als „zinsen" nicht findet. */
export function falte(text: string): string {
  return (text ?? "").toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9 ]+/g, " ");
}

/** Fragt jemand nach dem ORT einer Sache auf dieser Seite?
 *
 *  Gebaut wie `generische_frage`/`archivfrage` im Backend: gefaltet, am
 *  Wortlaut, deterministisch. **Bewusst eng:** „Wo wurde das beschlossen?"
 *  trifft hier nicht — das ist eine Archivfrage, und sie gehört ans Modell
 *  samt Weiterreichung, nicht an einen Chip.
 */
const _ORTSFRAGE_RE = new RegExp(
  "(?:^|\\b)(?:"
  + "wo (?:finde?|find|steht|stehen|sehe|seh|ist|sind|gibt|kann|koennte|hab|habe)\\b"
  + "|wo (?:auf|in) der seite\\b"
  + "|gibt es (?:hier|auf dieser seite)\\b"
  + "|(?:zeig|zeige|zeigst) (?:du )?(?:mir|mal)\\b"
  + "|(?:wo )?finde ich\\b"
  + ")",
);

export function ortsfrage(frage: string): boolean {
  return _ORTSFRAGE_RE.test(" " + falte(frage).split(/\s+/).join(" ").trim());
}

/** Wörter, die nichts über den gesuchten Baustein sagen.
 *
 *  Ohne sie träfe „wo finde ich die Zahlen zur Stadt" jeden Anker, in dessen
 *  Titel „die" oder „der" steckt — also die halbe Seite, und die beste
 *  Antwort stünde zufällig obenan. */
const _STOPP = new Set([
  "wo", "was", "wie", "wer", "wann", "warum", "welche", "welcher", "welches",
  "finde", "find", "findet", "steht", "stehen", "sehe", "seh", "sieht", "zeig",
  "zeige", "zeigst", "gibt", "kann", "koennte", "hab", "habe", "ist", "sind",
  "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
  "einer", "eines", "ich", "mir", "mich", "mal", "man", "es", "hier", "auf",
  "in", "im", "an", "am", "zu", "zur", "zum", "fuer", "mit", "von", "vom",
  "bei", "beim", "und", "oder", "aber", "denn", "seite", "dieser", "diese",
  "dieses", "du", "sie", "etwas", "ueber", "nach", "aus", "dazu", "davon",
  "genau", "eigentlich", "bitte", "wieviel",
  // **„Stadt" und „Oldenburg" sagen hier nichts.** Sie benennen den
  // Gegenstand der ganzen Anwendung, nicht einen Baustein — und sie stehen in
  // vielen Titeln. Gemessen am 22.09.2026 auf `/haushalt/schulden`: „Wo
  // steht, was die Stadt an Zinsen zahlt?" bot vor dieser Zeile zwei Chips an
  // und den richtigen („Kredite und Zinsen") erst an zweiter Stelle, weil
  // „Stadt" in der Bühnenüberschrift steckt.
  "stadt", "oldenburg", "stadtverwaltung", "verwaltung", "ratslotse",
]);

/** Die Inhaltswörter eines Textes — gefaltet, ohne Stoppwörter, ab 3 Zeichen. */
function inhaltswoerter(text: string): string[] {
  return falte(text).split(/\s+/)
    .filter((w) => w.length >= 3 && !_STOPP.has(w));
}

/** Ein grober Stammabgleich: gleich, oder ab fünf Zeichen Präfix des anderen.
 *
 *  **Warum fünf.** „Zins" steckt in „Zinsen" (4 Zeichen) — das soll treffen,
 *  deshalb auch das kürzere Wort als Präfix. Bei drei Zeichen träfe „ver" in
 *  „Verfahrensweg" und „Vermögen" gleichermaßen; fünf ist die Grenze, ab der
 *  ein Präfix im Deutschen meist schon der Stamm ist. Kein Stemmer: Der wäre
 *  ein Paket für eine Frage, die ein Chip beantwortet. */
function passt(a: string, b: string): boolean {
  if (a === b) return true;
  const kurz = a.length <= b.length ? a : b;
  const lang = a.length <= b.length ? b : a;
  return kurz.length >= 4 && lang.startsWith(kurz) && lang.length >= 5;
}

/**
 * Die Anker, die zur Frage passen — beste zuerst, höchstens drei.
 *
 * Gezählt werden **gemeinsame Inhaltswörter**; bei Gleichstand gewinnt die
 * Reihenfolge auf der Seite (von oben nach unten), denn die ist die einzige
 * Ordnung, die die Person selbst sieht. Ohne ein gemeinsames Inhaltswort
 * gibt es keinen Treffer — lieber ans Modell als der falsche Chip.
 */
export function ankerTreffer(frage: string, anker: Anker[]): Anker[] {
  const gesucht = inhaltswoerter(frage);
  if (!gesucht.length) return [];
  const bewertet = anker.map((a, i) => {
    const woerter = inhaltswoerter(a.titel);
    const punkte = gesucht.filter((g) => woerter.some((w) => passt(g, w))).length;
    return { a, i, punkte };
  }).filter((b) => b.punkte > 0);
  bewertet.sort((x, y) => y.punkte - x.punkte || x.i - y.i);
  return bewertet.slice(0, 3).map((b) => b.a);
}

/**
 * Alle Anker der Seite — **auch die, die gerade nicht zu sehen sind.**
 *
 * Das ist der Unterschied zum Erklär-Modus (`erklaer-modus.tsx`): Dort
 * bekommt nur ein sichtbarer Baustein ein Abzeichen, denn ein Abzeichen zeigt
 * auf etwas. Hier ist der weggescrollte Baustein genau der Punkt — „Wo finde
 * ich …?" fragt man über das, was man NICHT sieht.
 *
 * Ohne Titel kein Eintrag: Ein Schlüssel wie `haushalt-schulden.tabelle` ist
 * kein Satz, den man jemandem auf einen Chip schreibt.
 */
export function ankerListe(dok: Document): Anker[] {
  const aus: Anker[] = [];
  const gesehen = new Set<string>();
  for (const el of dok.querySelectorAll("[data-erklaer]")) {
    const key = el.getAttribute("data-erklaer") ?? "";
    const titel = kuerze(el.getAttribute("data-erklaer-titel") ?? "", ANKER_TITEL_MAX);
    // Schlüssel UND Titel: Zwei Bausteine dürfen denselben Schlüssel tragen
    // (s. `Anker`), derselbe Baustein steht aber nicht zweimal auf der Seite.
    const kennung = `${key}\u0000${titel}`;
    if (!key || !titel || gesehen.has(kennung)) continue;
    gesehen.add(kennung);
    aus.push({ key, titel });
    if (aus.length >= ANKER_MAX) break;
  }
  return aus;
}

/* ── Anschlussfragen: zwei Chips, die weiterführen ─────────────────────────
 *
 * **Deterministisch, ohne zweiten Modellaufruf.** Das Ratsgespräch lässt sich
 * seine Vorschläge vom Modell schreiben und bezahlt dafür eine eigene Runde.
 * Hier wäre das bei 0,07 Cent je Antwort ein Verdoppeln der Kosten für einen
 * Chip, den niemand drücken muss — und alles, was ein Modell vorschlagen
 * könnte, weiß das Fenster ohnehin schon: die Bausteine der Seite (die Anker)
 * und die Fachwörter der Antwort (das Glossar).
 */

/** Die Seite, auf der die Sache ausführlich steht — aus dem `done`-Rahmen
 *  (`next_page`). Route und Titel kommen aus `kern/knowledge.py`; der Server
 *  hat beides gegen die bekannten Seiten und die Rechte des Kontos geprüft,
 *  der Client navigiert nur noch. */
export type NaechsteSeite = { route: string; title: string };

/** Ein Anschluss-Chip unter einer Antwort.
 *
 *  **`{ art: "ratsfrage" }` gibt es seit 22.09.2026 nicht mehr.** Der Weg ins
 *  Archiv ist kein Angebot an die Person, sondern eine Entscheidung des
 *  Fensters: Gehört die Frage dorthin, geht Lotti von selbst (PR 23). Was
 *  bleibt, ist der stille Textlink „Im Ratsarchiv nachsehen" unter einer
 *  Erklärung — und der ist kein Chip. */
export type Anschluss =
  /** „Weiter zu: <Titel>" — die Haushalts-Seite, auf der es ausführlich steht. */
  | { art: "seite"; seite: NaechsteSeite }
  /** „<Titel> erklären" — der nächste Baustein der Seite. */
  | { art: "anker"; anker: Anker };

/** **Auch den Fachwort-Chip gibt es seit 22.09.2026 nicht mehr.** Er bot
 *  „Was heißt Aufwendung?" an, während „Aufwendungen" zwei Zeilen darüber
 *  im Antworttext schon unterstrichen war und sich dort aufklappen ließ
 *  (PR 22) — zwei Wege zu derselben geprüften Erklärung, einer davon als
 *  Bedienelement in der Fußzeile. Der Weg, der am Wort steht, ist der
 *  bessere: Er beantwortet die Frage da, wo sie entsteht. */

/** Die Kennung eines Ankers: Schlüssel UND Titel.
 *
 *  Zwei Bausteine dürfen denselben Schlüssel tragen (s. :type:`Anker`) — über
 *  den Schlüssel allein gälte der zweite als „schon erklärt", sobald jemand
 *  den ersten angetippt hat. */
export function ankerKennung(a: Anker): string {
  // Das Trennzeichen ist ein `\u0000` als ESCAPE, nicht als Zeichen im
  // Quelltext: Ein echtes Nullbyte macht die Datei für `grep`, `git diff`
  // und jede Code-Ansicht zu einer Binärdatei — sie fiel damit aus jeder
  // Durchsicht heraus (gemerkt am 22.09.2026, als kein `grep` hier mehr
  // etwas fand). Gewählt, weil es in keinem Anker-Schlüssel und in keinem
  // Titel vorkommen kann.
  return `${a.key}\u0000${a.titel}`;
}

/** So lang darf der Baustein-Name auf einem Chip sein. */
export const CHIP_TITEL_MAX = 38;

/**
 * Der Anker-Titel, wie er auf einen Chip passt.
 *
 * **Gemessen am 22.09.2026 auf `/haushalt/schulden`:** Die Bühne heißt dort
 * „Drei Zählweisen, eine Stadt · Stand 31.12.2024" — als „Erklär mir: …" war
 * das ein zweizeiliger, zentrierter Klotz, der die Chip-Reihe sprengte. Was
 * hinter dem `·` steht, ist in diesen Titeln durchweg Beiwerk (ein Stand, ein
 * Jahrgang); der Name davor ist das, was man anspricht. Der Chip nennt
 * deshalb nur ihn — gezeigt und erklärt wird trotzdem der ganze Baustein.
 */
export function chipTitel(titel: string): string {
  return kuerze((titel ?? "").split(" · ")[0], CHIP_TITEL_MAX);
}

/** Der führende Artikel eines Baustein-Titels — „Die Anzeigetafel". */
//  **Ohne `i`-Flag, und das ist kein Versehen:** JavaScript faltet mit `i`
//  auch `\p{Lu}` — die Lookahead-Bedingung „danach kommt ein Großbuchstabe"
//  träfe dann jeden Buchstaben, und aus „die letzten Jahre" würde „letzten
//  Jahre". Der Artikel steht deshalb in beiden Schreibweisen da.
const ARTIKEL_RE = /^[Dd](?:er|ie|as|en|em|es)\s+(?=\p{Lu})/u;

/**
 * Der Chip-Text zu einem Baustein — eine **Handlung**, kein Etikett.
 *
 * „Erklär mir: Die Anzeigetafel" wird „Anzeigetafel erklären" (Tim,
 * 22.09.2026: „man weiß nicht, was man anklicken soll"). Ein Chip sagt, was
 * passiert, wenn man ihn drückt; das Präfix „Erklär mir:" war die
 * Innensicht — es beschrieb, was das Fenster ans Backend schickt.
 *
 * Der führende Artikel fällt weg, damit der Satz nicht „Die Anzeigetafel
 * erklären" heißt: Auf einem 384 px breiten Chip zählt jedes Wort, und der
 * nächste Buchstabe ist ohnehin groß. **Nur vor einem Großbuchstaben**
 * — „Der Rat" verliert seinen Artikel, „die letzten Jahre" behält ihn, weil
 * dort kein Name folgt.
 */
export function erklaerAktion(titel: string): string | null {
  const name = chipTitel(titel).replace(ARTIKEL_RE, "");
  return name && chipTauglich(name) ? `${name} erklären` : null;
}

/** Höchstens so viele Wörter — danach ist es kein Name mehr, sondern ein Satz. */
export const CHIP_WORTE_MAX = 4;

/**
 * Taugt dieser Baustein-Name als Handlung auf einem Chip?
 *
 * **Gemessen am 22.09.2026 auf `/council/decision?id=2982`:** Dort heißt die
 * Kurzfassungs-Box „Lotti erklärt's einfach" — als Chip stand da „Lotti
 * erklärt's einfach erklären". Ein Titel, der selbst schon ein Satz ist, wird
 * durch das angehängte Verb albern, und ein alberner Chip beschädigt das
 * Angebot mehr, als der fehlende es kostet.
 *
 * Drei Merkmale, alle am Bestand geprüft (24 Anker-Titel im Repo): ein
 * **Apostroph** („erklärt's") und ein **Doppelpunkt** („Entgelte: geplant und
 * geworden") heißen, dass der Titel eine eigene Satzstruktur hat; **mehr als
 * vier Wörter** (nach dem Artikel) heißen dasselbe ohne Satzzeichen („Woher
 * das Geld kommt und wohin es geht").
 *
 * **Seit 22.09.2026 auch ein Komma.** „Drei Zählweisen, eine Stadt" (die
 * Bühne auf `/haushalt/schulden`) hat vier Wörter und kein Apostroph, wurde
 * also als Chip zugelassen — „Drei Zählweisen, eine Stadt erklären" liest
 * sich trotzdem wie zwei Halbsätze hintereinander, nicht wie eine Handlung.
 * Dasselbe Zeichen, derselbe Grund wie beim Doppelpunkt: Ein Komma im Titel
 * heißt, dass er selbst schon zwei Gedanken trägt.
 *
 * Gezählt wird NACH dem Artikel: „Der Weg durch die Gremien" sind vier Wörter
 * und ergibt „Weg durch die Gremien erklären" — ein Satz, den man sagen kann.
 */
export function chipTauglich(name: string): boolean {
  if (/['’:,]/.test(name)) return false;
  return name.trim().split(/\s+/).filter(Boolean).length <= CHIP_WORTE_MAX;
}

/** Bausteine, die nie auf einem Chip landen — über den Namensteil ihres
 *  Schlüssels (`useErklaerAnker(name, …)`), nicht über den Titel.
 *
 *  **`kurzfassung`** ist die Box „Lotti erklärt's einfach" auf der
 *  Beschluss-Seite. Sie IST bereits Lottis Erklärung, und zwar der
 *  deterministische Weg (`assistant.deterministic_answer`) — ein Chip
 *  „erklär mir die Erklärung" ist ein Kreis. Im Erklär-Modus bleibt sie
 *  antippbar; hier geht es nur um das unaufgeforderte Angebot. */
const ANKER_OHNE_CHIP = new Set(["kurzfassung"]);

/** Der Namensteil eines Anker-Schlüssels: `council-decision.kurzfassung` →
 *  `kurzfassung`. Die Seite davor wechselt, der Name nicht. */
function ankerName(key: string): string {
  return key.slice(key.lastIndexOf(".") + 1);
}

/** Höchstens so viele Chips je Runde.
 *
 *  **Eins, seit 22.09.2026.** Vorher zwei — plus der Archiv-Knopf, plus die
 *  Grund-Chips, plus die Daumen: sieben Bedienelemente unter EINER Antwort
 *  (Tims Bild vom Bereichs-Steckbrief). „Es ist für den User sehr
 *  überfordernd, wenn man hier tausend verschiedene Sachen anklicken kann."
 *  Jeder Chip war einzeln begründet; keiner hat die Summe angesehen. */
export const ANSCHLUSS_MAX = 1;

/**
 * Der Chip unter einer Antwort — **höchstens einer**, Vorrang Seite › Anker.
 *
 * **Der Vorrang ist die Reihenfolge des Nutzens.** Zuerst die andere
 * Haushalts-Seite: Lotti hat gerade gesagt, dass es dort ausführlich steht,
 * und der Chip ist der Weg dorthin — er schlägt den nächsten Baustein DIESER
 * Seite, weil die Antwort ihn schon benannt hat. Danach kommt dieser
 * Baustein: Er ist der Grund, warum jemand hier ist.
 *
 * **Der Wegweiser zeigt nie auf die Seite, auf der man steht** (`route`).
 * „Weiter zu: Bereichs-Steckbrief" auf dem Bereichs-Steckbrief war genau der
 * Befund; der Server streicht die eigene Seite schon aus dem Prompt und
 * verwirft die Marke — dies hier ist der Hosenträger zum Gürtel, und er
 * greift auch für eine Runde, die von einer anderen Seite stammt und deren
 * `nextPage` inzwischen hierher zeigt.
 *
 * **Nichts zweimal.** `erklaert` trägt, was in dieser Sitzung schon als
 * Baustein gefragt wurde (:func:`ankerKennung`). Ein Chip, der die Antwort
 * wiederholt, die zwei Zeilen höher steht, ist schlimmer als kein Chip.
 *
 * **Keine Chips** unter einer Fehler-Runde (dort ist der Ausweg das
 * Wiederholen, nicht das Weitergehen), unter der Lotsen-Runde
 * (`mode === "local"`, die „Zeig mir"-Antwort aus dem Browser — sie trägt ihre
 * eigenen Chips) und **unter einer Antwort aus dem Archiv**: Sie beantwortet
 * eine Frage an 9.000 Beschlüsse; ein Baustein DIESER Seite daneben ist ein
 * Themenwechsel, kein nächster Schritt (gemessen am 22.09.2026 auf
 * `/council/decision?id=2982`: „Lotti erklärt's einfach erklären" unter der
 * Auskunft, wer dagegen gestimmt hat).
 */
export function anschlussfragen(
  turn: { answer: string; fehler?: boolean; mode?: string | null;
          nextPage?: NaechsteSeite | null; ratsfrage?: boolean },
  anker: Anker[],
  erklaert: ReadonlySet<string>,
  route = "",
): Anschluss[] {
  if (!turn.answer || turn.fehler || turn.mode === "local" || turn.ratsfrage) return [];
  const aus: Anschluss[] = [];
  if (turn.nextPage && turn.nextPage.route !== route) {
    aus.push({ art: "seite", seite: turn.nextPage });
  }
  const naechster = anker.find((a) => !erklaert.has(ankerKennung(a))
    && !ANKER_OHNE_CHIP.has(ankerName(a.key)) && erklaerAktion(a.titel));
  if (naechster && aus.length < ANSCHLUSS_MAX) aus.push({ art: "anker", anker: naechster });
  return aus.slice(0, ANSCHLUSS_MAX);
}

/** So lang darf der Name eines Belegs unter einer Antwort sein.
 *
 *  Gemessen im Browser am 22.09.2026 auf `/haushalt/schulden`: Die beiden
 *  echten Belege heißen „Statistisches Jahrbuch der Stadt Oldenburg, Tabelle
 *  1108 — Stand der Verschuldung 1995 bis 2025" (99 Zeichen) und
 *  „Jahresabschluss 2024 der Kernverwaltung und ihrer nicht rechtsfähigen
 *  Stiftungen" (80). Ungekürzt füllten sie im 384-px-Fenster VIER Zeilen
 *  unter einer sechszeiligen Antwort — der Apparat wog dann fast so schwer
 *  wie die Auskunft, und genau dagegen ist diese Runde gebaut (Tim: „viel zu
 *  viele Pills … sehr überfordernd"). */
export const BELEG_NAME_MAX = 44;

/** Der Name eines Belegs, wie er unter die Antwort passt: „Jahresabschluss 2024".
 *
 *  Drei Schritte, jeder aus einem echten Titel begründet:
 *
 *  1. **Der Untertitel hinter dem Gedankenstrich fällt weg.** In den
 *     Provenienz-Titeln steht dort durchweg Beiwerk („— Stand der
 *     Verschuldung 1995 bis 2025"); das Papier heißt davor. Dieselbe Regel
 *     wie beim `·` in {@link chipTitel}.
 *  2. **Das Jahr nur, wo es fehlt.** Die RIS-Titel heißen „Beschlossener
 *     Haushaltsplan 2020"; „… 2020 2020" liest niemand als Sorgfalt.
 *  3. **Dann kappen.** Der volle Name bleibt erreichbar — er steht im
 *     `title` des Links.
 */
export function belegName(beleg: { label: string; year?: number | null }): string {
  const ohneUntertitel = (beleg.label ?? "").split(/\s[—–]\s/)[0].trim();
  const jahr = beleg.year != null && !ohneUntertitel.includes(String(beleg.year))
    ? ` ${beleg.year}` : "";
  return kuerze(ohneUntertitel + jahr, BELEG_NAME_MAX);
}
