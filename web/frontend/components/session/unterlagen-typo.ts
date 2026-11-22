/* Die Stufen der Karte „Aus den Unterlagen“ — an EINER Stelle, damit Vorlage,
   Dossier, Änderungsanträge und das Mitlesen dieselbe Hierarchie tragen.
   Tim, 13.11.2026: „unterschiedlich große Headings … wenig Struktur, nicht
   einheitlich, schlechte visuelle Hierarchie“. Von oben nach unten:

   Kartentitel  Bricolage 20/700 — einmal je Karte
   Abschnitt    Mono-Kicker 13, Versalien — die einzige Überschriften-Stufe darunter
   Inhalt       Leserolle `lese` — Aussagen, Bedeutung, Wortlaut, Diff
   Meta         Leserolle `meta` — Absender, Fundstelle, „Bisher“/„Neu“, Stand
   Hinweis      Leserolle `hinweis`, kursiv — Begründung und Randnotizen

   Mono-Versalien gibt es nur für Abschnitte: Eine Fundstelle in derselben
   Schrift („AUSSCHUSS FÜR ALLGEMEINE ANGELEGENHEITEN“) sah aus wie eine
   weitere Überschrift. */

export const KARTENTITEL = "font-display text-xl font-bold leading-snug text-foreground";
export const ABSCHNITT = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
export const INHALT = "text-lese text-foreground";
export const META = "text-meta text-muted-foreground";
export const HINWEIS = "text-hinweis italic text-muted-foreground";
export const ZITAT = "border-l-2 border-border pl-3 text-lese text-foreground";
