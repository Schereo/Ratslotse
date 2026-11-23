/* Die Gegenlese-Liste eines Punkts (docs/plan-vorlagen-aufbereiten.md, § 6.1):
   Art als Wort, Label ohne Datumspräfix, Lesestoff vorn und Belegmaterial
   eingeklappt. Reihenfolge und Nummern kommen vom Backend. */

export const ART_WORT: Record<string, string> = {
  template: "Vorlage",
  amendment: "Änderungsantrag",
  motion: "Antrag",
  report_request: "Berichtsantrag",
  synopsis: "Synopse",
  statute: "Satzung/Regelwerk",
  statement: "Stellungnahme",
  objection_table: "Abwägung",
  audit_report: "Prüfbericht",
  plan: "Plan",
  report: "Bericht/Anlage",
  presentation: "Präsentation",
  other: "Anlage",
  protocol: "Protokoll",
};

/** Was man liest, um die Aufbereitung gegenzulesen — der Rest ist Belegmaterial.
 *  Dieselbe Einteilung wie im Plan (§ 2.4) und im Dossier
 *  (`council/template_dossier.py::LESESTOFF`): Ein Bericht ist Lesestoff — bis
 *  11/2026 fehlte er hier, und der Quartalsbericht, aus dem das Dossier seine
 *  Zahlen hat, stand eingeklappt unter „Weitere Unterlagen" (Tim, 23.11.2026). */
const LESESTOFF = new Set(["template", "amendment", "motion", "report_request", "synopsis", "statute", "statement", "report"]);

/** Ab so vielen Stücken Belegmaterial lohnt das Einklappen. Darunter kostet
 *  der Klick mehr, als die eingesparte Zeile bringt. */
export const EINKLAPPEN_AB = 3;

/** Wird das Belegmaterial eingeklappt? Nur, wenn es viel ist UND davor
 *  Lesestoff steht — sonst wäre die Liste zugeklappt leer. */
export function belegEinklappen(lesestoff: number, beleg: number): boolean {
  return lesestoff > 0 && beleg >= EINKLAPPEN_AB;
}

/** „2026-10-31 Reduzierung …", „2026 11 01. - Antrag …", „20241025 DIE GRÜNEN …" → ohne Datum. */
export function ohneDatum(label: string): string {
  const ohne = label
    .replace(/^\s*\d{4}[-. ]?\d{2}[-. ]?\d{2}\.?\s*(?:[-–]\s*)?/, "")
    .replace(/^\s*\d{6}\s+/, "")
    .trim();
  return ohne || label;
}

/** Abkürzungen, die in Dateinamen des Haushalts stehen — als ganzes Wort. */
const ABKUERZUNG: Record<string, string> = {
  THH: "Teilhaushalt", WP: "Wirtschaftsplan", EHH: "Ergebnishaushalt", FHH: "Finanzhaushalt",
};

/** Kurze Namen für eine Liste: was ALLE (die meisten) Titel gemeinsam haben,
 *  steht nicht in jeder Zeile. Der Haushaltsentwurf 2027 heißt 30-mal
 *  „2027 0xx Vw … Haushalt 2027 Verwaltungsentwurf“ — in der Liste stand das
 *  Unterscheidende („THH01“) mitten in Wiederholungen (Tim, 23.11.2026:
 *  „kompakter darstellen“).
 *
 *  Anfang: Wörter, die mindestens drei und 60 % der Titel teilen; eine laufende
 *  Nummer zählt als gleich. Ende: dasselbe ab 50 %. Bleibt kein Wort übrig,
 *  steht der Titel ganz da. Unter drei Titeln ändert sich nichts. */
export function kurzeTitel(labels: readonly string[]): string[] {
  const titel = labels.map(ohneDatum);
  const woerter = titel.map((t) => t.split(/\s+/).filter(Boolean));
  if (woerter.length < 3) return titel.map(ausschreiben);
  const zahl = (w: string) => /^\d+$/.test(w);
  const gleich = (a: string, b: string) => a === b || (zahl(a) && zahl(b));
  const haeufigster = (kandidaten: (string | undefined)[]): string | undefined => {
    const zaehler = new Map<string, number>();
    for (const k of kandidaten) if (k !== undefined) {
      const schluessel = zahl(k) ? "#" : k;
      zaehler.set(schluessel, (zaehler.get(schluessel) ?? 0) + 1);
    }
    let best: string | undefined, n = 0;
    for (const [k, v] of zaehler) if (v > n) { best = k; n = v; }
    return best === "#" ? "0" : best;
  };
  const passt = (w: string[], muster: string[], vonHinten: boolean) =>
    w.length > muster.length && muster.every((m, i) => gleich(vonHinten ? w[w.length - muster.length + i] : w[i], m));
  const finde = (vonHinten: boolean, anteil: number): string[] => {
    const muster: string[] = [];
    for (;;) {
      const pos = (w: string[]) => (vonHinten ? w[w.length - 1 - muster.length] : w[muster.length]);
      const kandidat = haeufigster(woerter.filter((w) => muster.length === 0 || passt(w, muster, vonHinten)).map(pos));
      if (kandidat === undefined) return muster;
      const neu = vonHinten ? [kandidat, ...muster] : [...muster, kandidat];
      const treffer = woerter.filter((w) => passt(w, neu, vonHinten)).length;
      if (treffer < Math.max(3, Math.ceil(woerter.length * anteil))) return muster;
      muster.splice(0, muster.length, ...neu);
    }
  };
  const vorn = finde(false, 0.6), hinten = finde(true, 0.5);
  return woerter.map((w, i) => {
    let rest = w;
    if (vorn.length && passt(rest, vorn, false)) rest = rest.slice(vorn.length);
    if (hinten.length && passt(rest, hinten, true)) rest = rest.slice(0, rest.length - hinten.length);
    // Eine nackte Nummer („Anlage 1“ → „1“) ist kein Name.
    return rest.some((x) => /\p{L}/u.test(x)) ? ausschreiben(rest.join(" ")) : ausschreiben(titel[i]);
  });
}

/** „THH01“ → „Teilhaushalt 01“, „WP EGH“ → „Wirtschaftsplan EGH“. */
function ausschreiben(titel: string): string {
  return titel.replace(/\b(THH|WP|EHH|FHH)(\d*)\b/g, (_, k: string, nr: string) => `${ABKUERZUNG[k]}${nr ? ` ${nr}` : ""}`);
}

export interface ListenDoc { kind: string; doc_type?: string; label: string }

export function teileListe<T extends ListenDoc>(docs: T[]): { lesestoff: T[]; beleg: T[]; protokolle: T[] } {
  const lesestoff: T[] = [], beleg: T[] = [], protokolle: T[] = [];
  for (const d of docs) {
    if (d.kind === "protocol") protokolle.push(d);
    else if (LESESTOFF.has(d.doc_type ?? (d.kind === "template" ? "template" : "other"))) lesestoff.push(d);
    else beleg.push(d);
  }
  return { lesestoff, beleg, protokolle };
}

/** Unveränderte Stücke eines Wortdiffs auf den Kontext um die Änderung
 *  kürzen — an der Satzgrenze, wenn sie in Reichweite liegt: hinten bis zum
 *  ersten Satzende, vorn ab dem letzten. Erst ohne Satzgrenze in ``weit``
 *  Wörtern bleiben ``rand`` Wörter stehen. Mit fester Wortzahl fiel bei der
 *  GO-Änderung von Volt (Rat 02.11.2026) gerade „verkürzt werden" weg: „In
 *  dringenden Fällen kann sie auf sechs Stunden …" (Tim, 13.11.2026). */
export function kurzerDiff(diff: string[][], rand = 8, weit = 24): string[][] {
  // „am 10. September“: Eine Zahl mit Punkt ist ein Datum oder eine
  // Ordnungszahl, kein Satzende — der Rest endete sonst bei „… am 10. …“.
  const satzende = (wort: string) => /[.;:!?]["“”»)]?$/.test(wort) && !/^\d+\.$/.test(wort);
  const hinten = (w: string[]): number => {
    const i = w.findIndex(satzende);
    return i >= 0 && i < weit ? i + 1 : rand;
  };
  const vorn = (w: string[]): number => {
    for (let i = w.length - 2; i >= 0 && w.length - 1 - i <= weit; i--) if (satzende(w[i])) return i + 1;
    return w.length - rand;
  };
  return diff.map(([op, text], i) => {
    if (op !== "=") return [op, text];
    const w = text.split(" ");
    const erstes = i === 0, letztes = i === diff.length - 1;
    if (erstes && letztes) return [op, text];
    if (erstes) {
      const ab = vorn(w);
      return ab <= 0 ? [op, text] : [op, "… " + w.slice(ab).join(" ")];
    }
    if (letztes) {
      const bis = hinten(w);
      return bis >= w.length ? [op, text] : [op, w.slice(0, bis).join(" ") + " …"];
    }
    const bis = hinten(w), ab = vorn(w);
    return bis >= ab ? [op, text] : [op, `${w.slice(0, bis).join(" ")} … ${w.slice(ab).join(" ")}`];
  });
}

/** Die Aussagen eines Dossier-Abschnitts nach ihrer Art gruppiert, in der
 *  Reihenfolge des Servers. Die Art trägt die zweite Gliederungsstufe:
 *  „Nicht Teil des Beschlusses“, „Deckung“, „Termine“, „Noch offen“ stehen
 *  EINMAL als Zwischenzeile, statt vor jedem Satz wiederholt zu werden
 *  (Tim, 14.11.2026: „sehr viel nicht übersichtlich formatierter Text“).
 *
 *  `label` ist `null`, wo die Abschnitts-Überschrift schon alles sagt: bei der
 *  ersten, gewöhnlichen Gruppe — und bei „Termine“, wenn der Abschnitt nichts
 *  anderes trägt. */
const GRUPPEN_WORT: Record<string, string> = {
  not_included: "Nicht Teil des Beschlusses",
  coverage: "Deckung",
  dates: "Termine",
  open: "Noch offen",
};

export interface AussagenGruppe<T> { kind: string; label: string | null; aussagen: T[] }

export function aussagenGruppen<T extends { kind: string }>(aussagen: readonly T[]): AussagenGruppe<T>[] {
  const gruppen: AussagenGruppe<T>[] = [];
  for (const a of aussagen) {
    const letzte = gruppen[gruppen.length - 1];
    if (letzte && letzte.kind === a.kind) letzte.aussagen.push(a);
    else gruppen.push({ kind: a.kind, label: GRUPPEN_WORT[a.kind] ?? null, aussagen: [a] });
  }
  if (gruppen.length === 1 && gruppen[0].kind === "dates") gruppen[0].label = null;
  return gruppen;
}

/** „3 Angaben“ — die Zahl an der zugeklappten Zeile eines Abschnitts. */
export function angabenWort(n: number): string {
  return n === 1 ? "1 Angabe" : `${n} Angaben`;
}
