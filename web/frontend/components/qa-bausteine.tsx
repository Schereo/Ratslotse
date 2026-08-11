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

import { useState } from "react";
import { ChevronDown, ExternalLink, MessageSquarePlus } from "lucide-react";
import { cn } from "@/lib/utils";
// Reine Beleg-/Datums-Logik liegt in lib/qa-belege.ts — ohne "use client",
// damit auch die Server-Komponente app/g sie AUFRUFEN kann (aus einem
// Client-Modul kämen dort nur Referenzen an, keine Funktionen).
import {
  ANL_EXACT_RE, ANL_SOURCE, anlagenBuchstaben, anlagenNr, BELEG_SPLIT_RE,
  CITE_EXACT_RE, CITE_SOURCE, citationIds, datenEindeutschen, fmtDatumKurz,
} from "@/lib/qa-belege";

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
  anlBuchstaben, onAnlage, anlageHref, ankerPrefix, berichtKoepfe }: {
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
}) {
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
          ? <strong key={`${keyBase}-${i}-${j}`} className="font-semibold">{s.slice(2, -2)}</strong>
          : <span key={`${keyBase}-${i}-${j}`}>{s}</span>);
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
          {d.sprecher ?? "Ohne Namen"}{d.partei ? ` (${d.partei})` : ""}
          <span className="ml-1.5 font-normal text-muted-foreground">· {artLabel[d.art] ?? d.art}</span>
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
                          {" "}— {p.kernaussage.sprecher ?? "ohne Namen"}{p.kernaussage.datum ? `, ${p.kernaussage.datum}` : ""}
                        </span>
                      </p>
                    )}
                    {istOffen && p.beitraege_liste && (
                      <ul className="mt-2 space-y-2 border-l-2 border-border/70 pl-2.5">
                        {p.beitraege_liste.map((b, bi) => (
                          <li key={bi} className="text-[12px] leading-snug">
                            <p className="font-mono text-[10px] text-muted-foreground">
                              {b.sprecher ?? "Ohne Namen"} · {b.datum}
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
