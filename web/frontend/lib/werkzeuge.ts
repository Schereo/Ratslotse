/**
 * Der Auswahl-Zustand des Mehrheitsrechners (`/werkzeuge/mehrheiten`).
 *
 * Gerechnet wird im Backend (`web/backend/app/majorities.py`) — hier steht
 * nur, wie die Auswahl in der Adresse steht und wie ein Klick sie ändert.
 * Die Adresse trägt sie, damit sich eine Auswahl teilen und neu laden lässt:
 * `?gremium=rat&dabei=spd,gruene&ohne=afd`.
 */

export type Wahl = "dabei" | "ohne";

export type Auswahl = { gremium: string | null; dabei: string[]; ohne: string[] };

/** Eine kommagetrennte Liste aus der Adresse — leer, doppelt und Leerraum fallen weg. */
export function liste(roh: string | null | undefined): string[] {
  const out: string[] = [];
  for (const teil of (roh ?? "").split(",")) {
    const k = teil.trim();
    if (k && !out.includes(k)) out.push(k);
  }
  return out;
}

export function auswahlAus(params: URLSearchParams): Auswahl {
  const ohne = liste(params.get("ohne"));
  return {
    gremium: params.get("gremium") || null,
    // „ohne“ gewinnt — dieselbe Regel wie im Backend.
    dabei: liste(params.get("dabei")).filter((k) => !ohne.includes(k)),
    ohne,
  };
}

export function auswahlQuery(a: Auswahl): string {
  const q = new URLSearchParams();
  if (a.gremium) q.set("gremium", a.gremium);
  if (a.dabei.length) q.set("dabei", a.dabei.join(","));
  if (a.ohne.length) q.set("ohne", a.ohne.join(","));
  return q.toString();
}

/** Der Wert, den ein Block gerade hat. */
export function wahlVon(a: Auswahl, key: string): Wahl | null {
  if (a.dabei.includes(key)) return "dabei";
  if (a.ohne.includes(key)) return "ohne";
  return null;
}

/**
 * Ein Klick auf „dabei“ oder „ohne“: setzt den Block dorthin — und nimmt ihn,
 * wenn er dort schon stand, wieder heraus (zurück auf offen).
 */
export function umschalten(a: Auswahl, key: string, wahl: Wahl): Auswahl {
  const war = wahlVon(a, key);
  const dabei = a.dabei.filter((k) => k !== key);
  const ohne = a.ohne.filter((k) => k !== key);
  if (war !== wahl) (wahl === "dabei" ? dabei : ohne).push(key);
  return { ...a, dabei, ohne };
}

/** Eine Kombination übernehmen: Ihre Blöcke sind dabei, „ohne“ bleibt. */
export function uebernehmen(a: Auswahl, bloecke: readonly string[]): Auswahl {
  return { ...a, dabei: bloecke.filter((k) => !a.ohne.includes(k)) };
}

/**
 * Die Reihenfolge der Sitze im Halbkreis: Was dabei ist (oder in der
 * Vorschau), sitzt links — dann sieht man an der Mittellinie, ob es reicht.
 * Ausgeschlossenes sitzt ganz rechts. Innerhalb jeder Gruppe bleibt die
 * Reihenfolge des Servers.
 */
export function sitzReihenfolge<B extends { key: string }>(
  bloecke: readonly B[], vorn: readonly string[], hinten: readonly string[],
): B[] {
  const rang = (b: B) => (vorn.includes(b.key) ? 0 : hinten.includes(b.key) ? 2 : 1);
  return bloecke.map((b, i) => ({ b, i })).sort((x, y) => rang(x.b) - rang(y.b) || x.i - y.i).map((x) => x.b);
}

/** „Grüne“, „Grüne und SPD“, „Grüne, SPD und Linke“. */
export function aufzaehlung(namen: readonly string[]): string {
  if (namen.length <= 1) return namen[0] ?? "";
  return `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`;
}

/** Wie viele Zeilen der Halbkreis braucht — wenige Sitze stehen in einem Bogen. */
export function reihenFuer(sitze: number): number {
  if (sitze <= 16) return 1;
  if (sitze <= 30) return 2;
  return 3;
}

/** Die Mail, mit der man ein Werkzeug vorschlägt — Betreff und Anfang stehen schon da. */
export function vorschlagMailto(adresse: string): string {
  const betreff = "Idee für ein Werkzeug";
  const text = "Welches Werkzeug würde dir bei der Ratsarbeit helfen?\n\n";
  return `mailto:${adresse}?subject=${encodeURIComponent(betreff)}&body=${encodeURIComponent(text)}`;
}
