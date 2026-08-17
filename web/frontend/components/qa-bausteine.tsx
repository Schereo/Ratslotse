"use client";

/**
 * Bausteine einer „Frag den Rat"-Antwort — geteilt zwischen dem Gespräch
 * (`council-qa.tsx`) und der öffentlichen Teilen-Seite (`app/g/page.tsx`).
 *
 * Vorher hatte die Teilen-Seite einen eigenen, ärmeren Nachbau: Debatten,
 * Presse, Anlagen und Parteien fehlten dort ganz, und ihr Markdown-Parser
 * setzte einen ganzen Absatz fett, sobald er mit „## " begann (Tims Befund
 * 10.08.). Beide Seiten rendern jetzt dieselben Komponenten — was im
 * Gespräch steht, steht auch im geteilten Link.
 *
 * Design: web/frontend/DESIGNSPRACHE.md — Mono-Kicker über jedem Block,
 * gestrichelter Rahmen für Externes, Paraphrasen kursiv ohne Anführungszeichen.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ChevronDown, ExternalLink, MessageSquarePlus } from "lucide-react";
import { cn } from "@/lib/utils";
import { personHref } from "@/lib/routes";
// Reine Beleg-/Datums-Logik liegt in lib/qa-belege.ts — ohne "use client",
// damit auch die Server-Komponente app/g sie AUFRUFEN kann (aus einem
// Client-Modul kämen dort nur Referenzen an, keine Funktionen).
import {
  ANL_EXACT_RE, ANL_SOURCE, anlagenBuchstaben, anlagenNr, BELEG_SPLIT_RE,
  CITE_EXACT_RE, CITE_SOURCE, citationIds, datenEindeutschen, fmtDatumKurz,
} from "@/lib/qa-belege";
import { apiUrl, authHeaders } from "@/lib/api";

/* ------------------------------ Typen ------------------------------ */

export type PresseHinweis = { titel: string; url: string; datum: string | null };

/** Task 33: Anlagen-Fundstelle (Gutachten, Konzept, Stellungnahme) — nur die
 *  Gründliche Recherche liefert diesen Kanal. */
export type AnlagenHinweis = {
  /** Beleg-Nummer aus dem Deep-Job; im Text steht sie als „[A<nr>]".
   *  Ältere gespeicherte Gespräche kennen das Feld nicht — dann bleibt die
   *  Karte einfach ohne Buchstabe (in diesen Texten steht auch kein Marker). */
  nr?: number | null;
  label: string | null; url: string | null;
  vorlage_nr: string | null; vorlage_titel: string | null; auszug: string;
};

/** Task 16: Wortbeitrag aus einem Sitzungsprotokoll (Rede, Anfrage,
 *  Einwohnerfrage oder Verwaltungs-Zusage) im Belege-Bereich. */
export type DebattenHinweis = {
  sprecher: string | null; partei: string | null; art: string;
  top: string | null; auszug: string; committee: string | null; datum: string | null;
};

/** Personen-Badge-Eintrag aus /council/personen-lexikon (Tims Wunsch 12.08.):
 *  Ratsmitglieder mit Partei, Verwaltung mit geerntetem Amt; `aktiv` heißt in
 *  den letzten zwölf Monaten in einer Anwesenheitsliste gesehen. */
export type PersonEintrag = {
  slug: string; name: string | null; vorname: string; nachname: string;
  /** "blocker": Gäste/Protokoll/beratende Mitglieder — nie ein Badge, aber
   *  ihr Nachname macht einen kahlen Nachnamen im Text mehrdeutig (Tims
   *  Oltmanns-Befund 12.08.). */
  art: "rat" | "stadt" | "blocker"; partei: string | null; rolle: string | null;
  aktiv: boolean; von: string | null; bis: string | null;
};

// Das Lexikon einmal je Seite laden — ein Modul-Promise statt Fetch je Turn;
// der Endpunkt ist public (auch die geteilte Seite braucht ihn) und cacht
// serverseitig sechs Stunden.
let _lexikonPromise: Promise<PersonEintrag[]> | null = null;

function usePersonenLexikon(): PersonEintrag[] {
  const [lex, setLex] = useState<PersonEintrag[]>([]);
  useEffect(() => {
    _lexikonPromise ||= fetch(apiUrl("/council/personen-lexikon"),
      { credentials: "include", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : { personen: [] }))
      .then((b) => (b?.personen ?? []) as PersonEintrag[])
      .catch(() => [] as PersonEintrag[]);
    let lebt = true;
    void _lexikonPromise.then((p) => { if (lebt) setLex(p); });
    return () => { lebt = false; };
  }, []);
  return lex;
}

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

const falteName = (t: string) =>
  t.toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss");

// Exakte Partei-Labels (gefaltet, ohne Satzzeichen) — NUR solche Klammern
// werden nach einem Badge geschluckt. „(FDP-Fraktion vom 28.07.2026)" trägt
// mehr als das Label und bleibt deshalb stehen.
const _KLAMMER_LABELS = new Set([
  "spd", "cdu", "fdp", "volt", "afd", "bsw", "linke", "die linke",
  "gruene", "die gruenen", "buendnis 90 die gruenen", "buendnis90 die gruenen",
  "fuer oldenburg", "fdp volt", "piraten", "die partei",
]);

function klammerIstParteiLabel(inhalt: string, badgePartei: string | null): boolean {
  if (!badgePartei) return false;
  const gefaltet = falteName(inhalt).replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  if (!_KLAMMER_LABELS.has(gefaltet)) return false;
  // Die Klammer muss DIESELBE Partei meinen wie das Badge daneben.
  return parteiKuerzel(inhalt) === parteiKuerzel(badgePartei);
}

/** Kleines Zugehörigkeits-Badge hinter einem Personennamen: Punkt in
 *  Parteifarbe (Verwaltung: Hafenblau „Stadt", Ehemalige: grau „ehem.") plus
 *  Kürzel; Tipp öffnet den Peek mit Rolle, belegtem Zeitraum und — bei
 *  Ratsmitgliedern — dem Link zur Personen-Seite. */
/** V-06: Sprecher-Zeilen in Debatten und Parteien-Kernaussagen sollen
 *  dieselben Badges tragen wie Namen im Fließtext. Dort läuft ein
 *  Prosa-Matcher; hier steht der Name schon isoliert da, also genügt die
 *  Nachnamen-Suche — MIT derselben Vorsichtsregel: Bei Namensvettern
 *  entscheidet ausschließlich der Vorname, sonst gibt es kein Badge
 *  (lieber keins als ein geratenes, Tims Oltmanns-Befund). */
function usePersonSuche(): (name: string) => PersonEintrag | null {
  const lexikon = usePersonenLexikon();
  const map = useMemo(() => {
    const m = new Map<string, PersonEintrag[]>();
    for (const p of lexikon || []) {
      if (!p.nachname || p.nachname.length < 3) continue;
      const l = m.get(p.nachname) || [];
      l.push(p);
      m.set(p.nachname, l);
    }
    return m;
  }, [lexikon]);
  return (name: string) => {
    const woerter = (name || "").match(/[A-ZÄÖÜ][A-Za-zÄÖÜäöüß-]{2,}/g);
    if (!woerter || map.size === 0) return null;
    const nachname = falteName(woerter[woerter.length - 1]);
    const kandidaten = map.get(nachname);
    if (!kandidaten || kandidaten.length === 0) return null;
    if (kandidaten.length === 1) {
      const p = kandidaten[0];
      return p.art === "blocker" || !p.name ? null : p;
    }
    const vornamen = woerter.slice(0, -1).map(falteName);
    const treffer = kandidaten.filter(
      (p) => p.name && vornamen.some((v) => falteName(p.name!.split(" ")[0] || "") === v));
    return treffer.length === 1 && treffer[0].art !== "blocker" ? treffer[0] : null;
  };
}

/** Sprechername mit Badge, wenn die Person eindeutig im Lexikon steht. */
export function SprecherName({ name }: { name: string }) {
  const suche = usePersonSuche();
  const p = suche(name);
  return (
    <>
      {name}
      {p && <PersonBadge p={p} />}
    </>
  );
}

export function PersonBadge({ p }: { p: PersonEintrag }) {
  const [offen, setOffen] = useState(false);
  // Das Peek wird FEST am Bildschirm positioniert und in den sichtbaren
  // Bereich geklemmt. Zwei Anläufe zuvor scheiterten je an einer anderen
  // Kante: rechts lief es aus dem Text, dann (rechtsbündig geöffnet) links
  // aus dem Bild, wenn die Person früh in der Zeile steht (Tims Befund
  // 12.08.). Mit position: fixed spielt außerdem kein overflow-hidden eines
  // Vorfahren mehr hinein. Beim Scrollen schließt es — mitwandern wäre
  // Bewegung ohne Nutzen.
  const BREITE = 256;   // = w-64
  const RAND = 8;
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  const oeffnen = () => {
    if (offen) { setOffen(false); return; }
    const r = ref.current?.getBoundingClientRect();
    if (r) {
      const links = Math.min(Math.max(r.left, RAND), window.innerWidth - BREITE - RAND);
      const platzUnten = window.innerHeight - r.bottom;
      // Unter dem Badge, außer es ist unten zu eng — dann darüber.
      const oben = platzUnten > 190 || r.top < 190 ? r.bottom + 6 : r.top - 6 - 176;
      setPos({ left: Math.max(RAND, links), top: Math.max(RAND, oben) });
    }
    setOffen(true);
  };
  useEffect(() => {
    if (!offen) return;
    const zu = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOffen(false);
    };
    const zuBeiScroll = () => setOffen(false);
    document.addEventListener("mousedown", zu);
    document.addEventListener("touchstart", zu);
    window.addEventListener("scroll", zuBeiScroll, { passive: true });
    return () => {
      document.removeEventListener("mousedown", zu);
      document.removeEventListener("touchstart", zu);
      window.removeEventListener("scroll", zuBeiScroll);
    };
  }, [offen]);

  const dot = !p.aktiv ? { bg: "hsl(209 10% 62%)", ring: false }
    : p.art === "stadt" ? { bg: "#0764a6", ring: false }
    : parteiDot(p.partei || "");
  const label = !p.aktiv ? "ehem." : p.art === "stadt" ? "Stadt" : parteiKuerzel(p.partei);
  const rolle = p.rolle
    || (p.art === "rat" ? `Ratsmitglied${p.partei ? ` · ${p.partei}` : ""}` : "Stadtverwaltung");
  const zeitraum = p.aktiv
    ? (p.von ? `In den Sitzungen seit ${p.von}` : null)
    : (p.von && p.bis ? `In den Sitzungen ${p.von}–${p.bis}` : null);

  return (
    <span ref={ref} className="relative inline-block align-baseline">
      <button type="button" onClick={oeffnen}
        aria-expanded={offen} title={`${p.name} — ${rolle}`}
        className="ml-1 inline-flex -translate-y-[1px] items-center gap-1 rounded-full border border-border bg-card px-1.5 py-px align-baseline text-[10px] font-medium leading-[14px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
        <span aria-hidden className={cn("h-[7px] w-[7px] shrink-0 rounded-full", dot.ring && "ring-1 ring-border")}
          style={{ backgroundColor: dot.bg }} />
        {label}
      </button>
      {offen && pos && (
        <span
          className="fixed z-50 block w-64 rounded-xl border border-border bg-card p-3 text-left shadow-lg"
          style={{ left: pos.left, top: pos.top }}>
          <span className="block text-[13px] font-semibold text-foreground">{p.name}</span>
          <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
            {p.aktiv ? rolle : `Ehemals: ${rolle}`}
          </span>
          {zeitraum && (
            <span className="mt-1 block text-[10.5px] text-muted-foreground/70">{zeitraum}</span>
          )}
          {p.art === "rat" && (
            /* Next-Link statt <a>: Der harte Reload warf beim Zurückkommen
               den Gesprächs-State weg (Tims Befund 12.08.) — client-seitig
               bleibt die History intakt und der Restore greift. */
            <Link href={personHref(p.slug)}
              className="mt-1.5 inline-flex items-center gap-1 text-[11.5px] font-medium text-primary hover:underline">
              Zur Personen-Seite <ArrowRight className="h-3 w-3" aria-hidden />
            </Link>
          )}
        </span>
      )}
    </span>
  );
}

export type ParteiMeinung = {
  partei: string; haltung?: "dafür" | "dagegen" | "offen" | "gewandelt";
  position: string; einig: boolean; hinweis: string | null;
  kernaussage: { text: string; sprecher: string | null; datum: string | null } | null;
  beitraege: number;
  beitraege_liste?: { sprecher: string | null; datum: string; art: string | null;
    gremium: string | null; text: string }[];
};

/* --------------------------- Antworttext ---------------------------- */

/**
 * Antworttext mit Fußnoten und SPARSAMEM Markdown: "[id]" → nummerierte Chips;
 * "**fett**" → <strong>; "- "-Zeilen → echte Liste; "## " → Zwischen-
 * überschrift (NUR diese eine Zeile, nicht der Rest des Absatzes);
 * Leerzeilen → Absätze. Streaming-fest: ein offenes "**" bleibt Text.
 *
 * Im Gespräch öffnet ein Chip das Beleg-Peek (`onJump`); auf der geteilten
 * Seite gibt es kein Peek — dort verlinkt `quelleHref` auf die Quellenliste.
 */
export function AntwortText({ text: rohtext, idToNum, onJump, quelleHref,
  anlBuchstaben, onAnlage, anlageHref, ankerPrefix, berichtKoepfe, personen }: {
  text: string; idToNum: Map<number, number>;
  onJump?: (id: number) => void;
  quelleHref?: (nummer: number) => string;
  /** Anlagen-Belege des Recherche-Berichts: nr → a/b/c. */
  anlBuchstaben?: Map<number, string>;
  onAnlage?: (nr: number) => void;
  anlageHref?: (nr: number) => string;
  /** RG-10: „## "-Köpfe bekommen ids `${ankerPrefix}-${i}` für Sprungmarken. */
  ankerPrefix?: string;
  /** RG-10: Bericht-Köpfe größer (Display-Font) statt der kompakten Task-32-Optik. */
  berichtKoepfe?: boolean;
  /** Personen-Lexikon für Zugehörigkeits-Badges hinter Namen (Tims Wunsch
   *  12.08.) — ohne Angabe lädt die Komponente es selbst (Modul-Cache). */
  personen?: PersonEintrag[];
}) {
  const lexikon = usePersonenLexikon();
  const personenEff = personen ?? lexikon;
  // Nachname → Kandidaten (Blocker zählen mit). Deterministische Regeln
  // statt LLM: Ganzwort, kapitalisiert, Badge nur bei der ERSTEN Nennung
  // einer Person. Bei Namensvettern entscheidet AUSSCHLIESSLICH der Vorname
  // davor — die frühere „einzige Aktive gewinnt"-Heuristik hängte einem
  // Gast von 2019 das Badge einer 2026er-Person um (Tims Oltmanns-Befund):
  // lieber KEIN Badge als ein geratenes.
  const personenMap = useMemo(() => {
    const m = new Map<string, PersonEintrag[]>();
    for (const p of personenEff || []) {
      if (!p.nachname || p.nachname.length < 3) continue;
      const l = m.get(p.nachname) || [];
      l.push(p);
      m.set(p.nachname, l);
    }
    return m;
  }, [personenEff]);
  const badgesGesetzt = new Set<string>();

  const mitPersonen = (s: string, keyBase: string): React.ReactNode => {
    if (personenMap.size === 0) return s;
    const re = /[A-ZÄÖÜ][A-Za-zÄÖÜäöüß-]{2,}/g;
    const teile: React.ReactNode[] = [];
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(s))) {
      const kandidaten = personenMap.get(falteName(m[0]));
      if (!kandidaten) continue;
      let p: PersonEintrag | null = null;
      if (kandidaten.length === 1) p = kandidaten[0];
      else {
        const davor = falteName((s.slice(0, m.index).trimEnd().split(/\s+/).pop() || "")
          .replace(/[^A-Za-zÄÖÜäöüß-]/g, ""));
        const perVorname = kandidaten.filter((k) => k.vorname && k.vorname === davor);
        if (perVorname.length === 1) p = perVorname[0];
      }
      if (!p || p.art === "blocker" || badgesGesetzt.has(p.slug)) continue;
      badgesGesetzt.add(p.slug);
      let ende = m.index + m[0].length;
      teile.push(s.slice(last, ende));
      teile.push(<PersonBadge key={`${keyBase}-p-${p.slug}`} p={p} />);
      // „Ulf Prange ·SPD (SPD)" — nennt der Text die Partei direkt hinter dem
      // Namen noch einmal in Klammern, ersetzt das Badge sie (Tims Befund
      // 12.08.). Geschluckt wird NUR das nackte Partei-Label derselben Partei.
      const klammer = s.slice(ende).match(/^\s*\(([^()]{2,40})\)/);
      if (klammer && klammerIstParteiLabel(klammer[1], p.partei)) {
        ende += klammer[0].length;
        re.lastIndex = ende;
      }
      last = ende;
    }
    if (teile.length === 0) return s;
    teile.push(s.slice(last));
    return teile;
  };
  // Belege ohne Gegenstück fliegen SAMT führendem Leerzeichen raus (der Deep-
  // Bericht wird roh gespeichert, nur die schnelle Antwort putzt serverseitig).
  // Ohne das bliebe „… nichts her ." mit einer Lücke vor dem Punkt stehen.
  const text = datenEindeutschen(rohtext).replace(
    new RegExp(String.raw`\s*(${CITE_SOURCE}|${ANL_SOURCE})`, "g"),
    (treffer, klammer: string) =>
      (ANL_EXACT_RE.test(klammer)
        ? anlBuchstaben?.has(anlagenNr(klammer))
        : citationIds(klammer).some((id) => idToNum.has(id)))
        ? treffer : "");
  // Laufender Kopf-Index über ALLE Blöcke — muss mit berichtAbschnitte()
  // deckungsgleich zählen, sonst springen die Chips daneben.
  let kopfIndex = -1;
  const inline = (chunk: string, keyBase: string) => {
    const parts = chunk.split(BELEG_SPLIT_RE);
    return parts.map((part, i) => {
      if (ANL_EXACT_RE.test(part)) {
        // Anlagen-Beleg: kleiner Buchstabe statt Zahl. Ohne bekannte Anlage
        // fällt der Marker weg — ein sichtbares „[A9]" wäre schlimmer als
        // gar kein Beleg.
        const nr = anlagenNr(part);
        const b = anlBuchstaben?.get(nr);
        if (!b) return null;
        const anlClass = "mx-0.5 inline-flex h-4 min-w-4 -translate-y-[3px] items-center justify-center rounded border border-primary/25 px-1 align-baseline text-[10px] font-semibold leading-none text-primary/90 no-underline transition-colors hover:bg-primary/10";
        return onAnlage ? (
          <button key={`${keyBase}-${i}`} type="button" onClick={() => onAnlage(nr)}
            title="Zur Anlage springen (Gutachten, Konzept, Stellungnahme)"
            aria-label={`Anlage ${b} anzeigen`} className={anlClass}>
            {b}
          </button>
        ) : (
          <a key={`${keyBase}-${i}`} href={anlageHref ? anlageHref(nr) : `#anlage-${nr}`}
            title="Zur Anlage springen (Gutachten, Konzept, Stellungnahme)"
            aria-label={`Anlage ${b} anzeigen`} className={anlClass}>
            {b}
          </a>
        );
      }
      if (CITE_EXACT_RE.test(part)) {
        const ids = citationIds(part).filter((id) => idToNum.has(id));
        if (ids.length === 0) return null;
        return (
          <span key={`${keyBase}-${i}`} className="whitespace-nowrap">
            {ids.map((id) => {
              const nummer = idToNum.get(id)!;
              const chipClass = "mx-0.5 inline-flex h-4 min-w-4 -translate-y-[3px] items-center justify-center rounded bg-primary/10 px-1 align-baseline text-[10px] font-semibold leading-none text-primary no-underline transition-colors hover:bg-primary/20";
              return onJump ? (
                <button key={id} type="button" onClick={() => onJump(id)}
                  title="Zur zitierten Quelle springen" aria-label={`Quelle ${nummer} anzeigen`}
                  className={chipClass}>
                  {nummer}
                </button>
              ) : (
                <a key={id} href={quelleHref ? quelleHref(nummer) : `#quelle-${nummer}`}
                  title="Zur zitierten Quelle springen" aria-label={`Quelle ${nummer} anzeigen`}
                  className={chipClass}>
                  {nummer}
                </a>
              );
            })}
          </span>
        );
      }
      const seg = part.split(/(\*\*[^*]+\*\*)/g);
      return seg.map((s, j) =>
        /^\*\*[^*]+\*\*$/.test(s)
          ? <strong key={`${keyBase}-${i}-${j}`} className="font-semibold">{mitPersonen(s.slice(2, -2), `${keyBase}-${i}-${j}`)}</strong>
          : <span key={`${keyBase}-${i}-${j}`}>{mitPersonen(s, `${keyBase}-${i}-${j}`)}</span>);
    });
  };

  const bloecke = text.split(/\n{2,}/);
  return (
    <>
      {bloecke.map((block, bi) => {
        // Drei Zeilenarten: „## "-Zwischenüberschrift (Task 32, lange
        // Antworten zu großen Themen), „- "-Listenzeile, Fließtext.
        const gruppen: { art: "kopf" | "unterkopf" | "liste" | "text"; zeilen: string[] }[] = [];
        for (const z of block.split("\n")) {
          // Listen: „- " laut Prompt, „* " (auch verschachtelt) liefern die
          // Modelle im langen Recherche-Bericht trotzdem gelegentlich.
          // „### " (und tiefer) ebenso — als Unterkopf eine Stufe kleiner,
          // OHNE Anker: Die Sprungmarken zählen nur „## "-Köpfe, ein
          // mitgezählter Unterkopf verschöbe alle Chips (Tims Befund: die
          // Rauten standen als Rohtext in der Antwort).
          const art = z.trim().startsWith("## ") ? "kopf" as const
            : /^#{1,6}\s+/.test(z.trim()) ? "unterkopf" as const
            : /^[-*]\s+/.test(z.trim()) ? "liste" as const : "text" as const;
          const g = gruppen[gruppen.length - 1];
          if (g && g.art === art && art === "liste") g.zeilen.push(z);
          else if (g && g.art === art && art === "text") g.zeilen.push(z);
          else gruppen.push({ art, zeilen: [z] });
        }
        return (
          <span key={bi} className="block [&:not(:first-child)]:mt-2.5">
            {gruppen.map((g, gi) =>
              g.art === "kopf" ? (
                <span key={gi}
                  id={ankerPrefix ? `${ankerPrefix}-${++kopfIndex}` : undefined}
                  className={cn("block scroll-mt-16 first:mt-0",
                    berichtKoepfe
                      ? "mt-4 font-display text-[15.5px] font-bold tracking-tight"
                      : "mt-3 text-[13.5px] font-bold tracking-tight")}>
                  {inline(g.zeilen[0].trim().replace(/^##\s+/, ""), `${bi}-${gi}`)}
                </span>
              ) : g.art === "unterkopf" ? (
                <span key={gi}
                  className={cn("block first:mt-0",
                    berichtKoepfe
                      ? "mt-3 font-display text-[14px] font-bold tracking-tight"
                      : "mt-2.5 text-[13px] font-bold tracking-tight")}>
                  {inline(g.zeilen[0].trim().replace(/^#{1,6}\s+/, ""), `${bi}-${gi}`)}
                </span>
              ) : g.art === "liste" ? (
                <ul key={gi} className="my-1.5 space-y-1 pl-1">
                  {g.zeilen.filter((z) => z.trim()).map((z, zi) => (
                    <li key={zi} className="flex gap-2">
                      <span aria-hidden className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-primary/60" />
                      <span className="min-w-0 whitespace-normal">{inline(z.trim().replace(/^[-*]\s+/, ""), `${bi}-${gi}-${zi}`)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span key={gi}>{inline(g.zeilen.join("\n"), `${bi}-${gi}`)}</span>
              ))}
          </span>
        );
      })}
    </>
  );
}

/**
 * Antworttext der geteilten Seite (app/g): Die Nummerierung folgt der
 * gespeicherten Quellen-Reihenfolge — die steht im Snapshot bereits in
 * Zitat-Reihenfolge. Eigene Komponente, damit die Server-Seite nur ein
 * schlichtes id-Array über die Grenze reichen muss und keine Map.
 */
export function GeteilterAntwortText({ text, quellenIds, anlagen }: {
  text: string; quellenIds: number[]; anlagen?: AnlagenHinweis[];
}) {
  const idToNum = new Map(quellenIds.map((id, i) => [id, i + 1] as const));
  return <AntwortText text={text} idToNum={idToNum}
    anlBuchstaben={anlagenBuchstaben(text, anlagen)} />;
}

/* ------------------------ Belege-Bausteine -------------------------- */

/** Task 33: Anlagen-Treffer der Gründlichen Recherche — Gutachten und
 *  Konzepte, verlinkt aufs öffentliche PDF im Ratsinformationssystem. */
export function AnlagenBlock({ anlagen, ankerPrefix, buchstaben }: {
  anlagen: AnlagenHinweis[]; ankerPrefix: string;
  /** nr → a/b/c für die im Bericht belegten Anlagen. */
  buchstaben: Map<number, string>;
}) {
  const belegt = [...buchstaben.keys()].length;
  return (
    <div className="rounded-xl border border-dashed border-border p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        Aus den Anlagen <span className="text-muted-foreground/60">· Gutachten &amp; Konzepte</span>
      </p>
      <ul className="mt-1.5 space-y-2">
        {anlagen.map((a, i) => {
          const nr = a.nr ?? i + 1;
          const b = buchstaben.get(nr);
          return (
          <li key={i} id={`${ankerPrefix}-${nr}`}
            className={cn("scroll-mt-16 text-[12.5px] leading-snug",
              // Nicht belegte Anlagen treten zurück, sobald überhaupt eine im
              // Text auftaucht — sonst sähen gelesene und benutzte Unterlagen
              // gleich aus.
              !b && belegt > 0 && "opacity-60")}>
            <a href={a.url ?? undefined} target="_blank" rel="noopener noreferrer"
              className="group flex items-baseline gap-2">
              {b && (
                <span aria-hidden
                  className="inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded border border-primary/25 px-1 text-[10px] font-semibold leading-none text-primary/90">
                  {b}
                </span>
              )}
              <span className="min-w-0 flex-1 truncate font-medium group-hover:underline">
                {a.label || "Anlage"}
              </span>
              {a.vorlage_nr && (
                <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{a.vorlage_nr}</span>
              )}
              <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden />
            </a>
            {a.vorlage_titel && (
              <p className="mt-0.5 truncate text-[11px] text-muted-foreground/80">zu: {a.vorlage_titel}</p>
            )}
            {a.auszug && (
              <p className="mt-0.5 text-muted-foreground">{a.auszug}{a.auszug.length >= 220 ? "…" : ""}</p>
            )}
          </li>
          );
        })}
      </ul>
      {belegt > 0 && belegt < anlagen.length && (
        <p className="mt-2 text-[10.5px] leading-relaxed text-muted-foreground/70">
          Die übrigen wurden gelesen, aber im Bericht nicht belegt.
        </p>
      )}
    </div>
  );
}

export function PresseBlock({ presse }: { presse: PresseHinweis[] }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        Aktuelles von der Stadt <span className="text-muted-foreground/60">· extern</span>
      </p>
      <ul className="mt-1.5 space-y-1">
        {presse.map((p) => (
          <li key={p.url}>
            <a href={p.url} target="_blank" rel="noopener noreferrer"
              className="group flex items-baseline gap-2 rounded-lg px-1.5 py-1 text-sm transition-colors hover:bg-muted">
              <span className="min-w-0 flex-1 truncate text-[12.5px] group-hover:underline">{p.titel}</span>
              <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{fmtDatumKurz(p.datum)}</span>
              <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Task 16: Wortbeiträge aus den Sitzungsprotokollen — was im Rat GESAGT
 *  wurde (Reden, Anfragen mit Verwaltungsantwort, Einwohnerfragen, Zusagen),
 *  im Unterschied zu dem, was beschlossen wurde. */
export function DebattenBlock({ debatten }: { debatten: DebattenHinweis[] }) {
  const artLabel: Record<string, string> = {
    rede: "Rede", anfrage: "Anfrage", einwohnerfrage: "Einwohnerfrage", zusage: "Zusage",
  };
  return (
    <div className="rounded-xl border border-dashed border-border p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        Aus den Ratsdebatten <span className="text-muted-foreground/60">· Protokolle</span>
      </p>
      <ul className="mt-1.5 space-y-2">
        {debatten.map((d, i) => (
          <DebattenZeile key={i} d={d} artLabel={artLabel} />
        ))}
      </ul>
      {/* Ehrlichkeit zur Quelle: Ratsprotokolle sind Verlaufsprotokolle —
          der wesentliche Inhalt in indirekter Rede, kein Wortprotokoll. */}
      <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground/60">
        Die Protokolle fassen Wortbeiträge sinngemäß zusammen — keine wörtlichen
        Zitate, ohne Anspruch auf Vollständigkeit.
      </p>
    </div>
  );
}

/** Eine Debatten-Zeile mit aufklappbarem VOLLTEXT: Der gekappte Auszug
 *  untergrub das „alles ist belegt"-Versprechen (Tims Befund 10.08.) —
 *  jetzt liefert das Backend die volle Paraphrase, die Anzeige klappt auf. */
function DebattenZeile({ d, artLabel }: { d: DebattenHinweis; artLabel: Record<string, string> }) {
  const [offen, setOffen] = useState(false);
  // Ab dieser Länge lohnt der Toggle; kürzere Beiträge stehen einfach ganz da.
  const lang = d.auszug.length > 260;
  return (
    <li className="text-[12.5px] leading-snug">
      <p className="flex items-baseline gap-2">
        <span className="min-w-0 flex-1 truncate font-medium">
          {d.sprecher ? <SprecherName name={d.sprecher} /> : "Ohne Namen"}{d.partei ? ` (${d.partei})` : ""}
          {/* Zusagen der Verwaltung sind Selbstverpflichtungen — kein
              Meinungsbeitrag unter vielen. Sie bekommen deshalb ein eigenes
              Abzeichen statt nur ein graues Wörtchen. */}
          {d.art === "zusage" ? (
            <span className="ml-1.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
              Zusage der Verwaltung
            </span>
          ) : (
            <span className="ml-1.5 font-normal text-muted-foreground">· {artLabel[d.art] ?? d.art}</span>
          )}
        </span>
        {d.datum && <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{fmtDatumKurz(d.datum)}</span>}
      </p>
      <p className={cn("mt-0.5 whitespace-pre-wrap text-muted-foreground",
        !offen && lang && "line-clamp-4")}>
        {d.auszug}
      </p>
      {lang && (
        <button type="button" onClick={() => setOffen((v) => !v)} aria-expanded={offen}
          className="mt-0.5 text-[11px] font-medium text-primary hover:underline">
          {offen ? "Weniger anzeigen" : "Ganzen Beitrag anzeigen"}
        </button>
      )}
    </li>
  );
}

/* ------------------ Baustein „Das sagen die Parteien" (RG-09) ------------------ */

/** Haltungs-Badge: Wort statt Grafik (RG-05-Verbot von Stimm-Balken gilt
 *  weiter); „offen" bekommt kein Badge — Grau neben Grau wäre nur Rauschen. */
const HALTUNG_BADGE: Record<string, { label: string; cls: string }> = {
  "dafür": { label: "dafür", cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" },
  "dagegen": { label: "dagegen", cls: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300" },
  "gewandelt": { label: "Haltung gewandelt", cls: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300" },
};

/** RG-09-Parteifarben (bewusst NICHT partyBrand aus decision-ui — das Artboard
 *  definiert eigene Dot-Farben). Gruppen (FDP/Volt, Für Oldenburg, IBO/LiVe)
 *  behalten ihr kombiniertes Label und bekommen den neutralen Dot. */
export function parteiDot(label: string): { bg: string; ring: boolean } {
  const l = label.toLowerCase();
  if (l.includes("grün")) return { bg: "#3d8f29", ring: false };
  if (l.includes("linke")) return { bg: "#e6007e", ring: false };
  if (l.includes("spd")) return { bg: "#e3000f", ring: false };
  if (l.includes("cdu")) return { bg: "#1a1a1a", ring: false };
  if (l.includes("bsw")) return { bg: "#7d254f", ring: false };
  if (l.includes("afd")) return { bg: "#009ee0", ring: false };
  if (l === "volt") return { bg: "#502379", ring: false }; // seit der Stammdaten-Auflösung eigenständig
  if (l === "fdp") return { bg: "#ffe000", ring: true }; // exakt — „FDP/Volt" ist eine Gruppe
  return { bg: "hsl(209 18% 65%)", ring: false };
}

/**
 * Die verdichteten Fraktions-Positionen (RG-09). `parteien === null` heißt
 * „wird gerade geladen" — auf der geteilten Seite gibt es diesen Zustand
 * nicht, dort kommen die Positionen aus dem Snapshot.
 */
export function ParteienListe({ parteien, ohneBeitraege = [], onFrageStellen }: {
  parteien: ParteiMeinung[] | null;
  ohneBeitraege?: string[];
  onFrageStellen?: (text: string) => void;
}) {
  // Klick auf die Zeile klappt die verdichteten Original-Beiträge auf
  // (Tims Wunsch: „auf die Partei klicken, um alle Beiträge zu sehen").
  const [offen, setOffen] = useState<string | null>(null);
  const daten = [...new Set((parteien ?? []).map((p) => p.kernaussage?.datum).filter(Boolean))];
  return (
    <div className="rounded-xl border border-border bg-card p-3.5 shadow-sm print:break-inside-avoid">
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
          Aus den Ratsdebatten
        </p>
        <p className="text-[10.5px] text-muted-foreground/70">
          {parteien === null ? "Positionen werden verdichtet …"
            : `${parteien.length} Fraktionen${daten.length === 1 ? ` · Sitzung ${daten[0]}` : ""}`}
        </p>
      </div>
      {parteien === null ? (
        <div aria-hidden className="mt-3 flex animate-pulse flex-col gap-3.5">
          {[34, 28, 40].map((w, i) => (
            <div key={i} className="flex gap-2.5">
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-muted" />
              <span className="flex flex-1 flex-col gap-1.5">
                <span className="h-2.5 rounded bg-muted" style={{ width: `${w}%` }} />
                <span className="h-2 w-[92%] rounded bg-muted/70" />
                {i !== 1 && <span className="h-2 w-[60%] rounded bg-muted/70" />}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="mt-2 flex flex-col divide-y divide-border/60">
            {parteien.map((p) => {
              const dot = parteiDot(p.partei);
              const aufklappbar = (p.beitraege_liste?.length ?? 0) > 0;
              const istOffen = offen === p.partei;
              return (
                <div key={p.partei} role={aufklappbar ? "button" : undefined}
                  tabIndex={aufklappbar ? 0 : undefined} aria-expanded={aufklappbar ? istOffen : undefined}
                  onClick={() => aufklappbar && setOffen(istOffen ? null : p.partei)}
                  onKeyDown={(e) => { if (aufklappbar && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setOffen(istOffen ? null : p.partei); } }}
                  className={cn("group relative -mx-1.5 flex gap-2.5 rounded-lg px-1.5 py-2.5 transition-colors lg:hover:bg-primary/5",
                    aufklappbar && "cursor-pointer")}>
                  <span aria-hidden className="mt-[5px] h-2 w-2 shrink-0 rounded-full"
                    style={{ background: dot.bg, boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,0.15)" : undefined }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-[12.5px] font-bold">{p.partei}</p>
                      {p.haltung && HALTUNG_BADGE[p.haltung] && (
                        <span className={cn("rounded-full px-2 py-px text-[10px] font-semibold",
                          HALTUNG_BADGE[p.haltung].cls)}>
                          {HALTUNG_BADGE[p.haltung].label}
                        </span>
                      )}
                      {/* Ehrlichkeit zur Datenbasis: aus wie vielen Wortbeiträgen
                          die Position verdichtet ist (Tims Befund 10.08.). */}
                      {p.beitraege > 0 && (
                        <span className="inline-flex items-center gap-0.5 font-mono text-[10px] text-muted-foreground/70">
                          {p.beitraege === 1 ? "1 Beitrag" : `${p.beitraege} Beiträge`}
                          {aufklappbar && (
                            <ChevronDown aria-hidden
                              className={cn("h-3 w-3 transition-transform", istOffen && "rotate-180")} />
                          )}
                        </span>
                      )}
                      {!p.einig && (
                        <span className="rounded-full bg-amber-100 px-2 py-px text-[10px] font-semibold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          uneinheitlich
                        </span>
                      )}
                      {onFrageStellen && (
                        <button type="button"
                          onClick={(e) => { e.stopPropagation(); onFrageStellen(`Was sagt ${p.partei} dazu im Detail?`); }}
                          className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10.5px] text-muted-foreground transition-opacity hover:text-foreground lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
                          title={`Was sagt ${p.partei} dazu im Detail?`}>
                          <MessageSquarePlus className="h-3 w-3" aria-hidden /> Dazu fragen
                        </button>
                      )}
                    </div>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-foreground/90">
                      {p.position}{!p.einig && p.hinweis ? ` — ${p.hinweis}` : ""}
                    </p>
                    {p.kernaussage && (
                      <p className="mt-1 text-[12px] italic leading-snug text-muted-foreground">
                        {p.kernaussage.text}
                        <span className="font-mono text-[10px] not-italic text-muted-foreground/80">
                          {" "}— {p.kernaussage.sprecher ? <SprecherName name={p.kernaussage.sprecher} /> : "ohne Namen"}{p.kernaussage.datum ? `, ${p.kernaussage.datum}` : ""}
                        </span>
                      </p>
                    )}
                    {istOffen && p.beitraege_liste && (
                      <ul className="mt-2 space-y-2 border-l-2 border-border/70 pl-2.5">
                        {p.beitraege_liste.map((b, bi) => (
                          <li key={bi} className="text-[12px] leading-snug">
                            <p className="font-mono text-[10px] text-muted-foreground">
                              {b.sprecher ? <SprecherName name={b.sprecher} /> : "Ohne Namen"} · {b.datum}
                              {b.gremium ? ` · ${b.gremium}` : ""}
                            </p>
                            <p className="mt-0.5 text-muted-foreground">{b.text}{b.text.length >= 300 ? "…" : ""}</p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-1.5 border-t border-dashed border-border pt-2 text-[10px] leading-normal text-muted-foreground/70">
            {/* Vollständigkeits-Ehrlichkeit (Tims Direktive): fehlende Fraktionen
                benennen statt still weglassen. */}
            {ohneBeitraege.length > 0 && (
              <>Keine passenden Wortbeiträge gefunden von: {ohneBeitraege.join(", ")}.{" "}</>
            )}
            Verdichtet aus den Wortbeiträgen der Sitzungsprotokolle — Paraphrasen, keine wörtlichen Zitate.
          </p>
        </>
      )}
    </div>
  );
}
