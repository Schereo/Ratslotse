"use client";

/* Das belegte Dossier in „Aus den Unterlagen" (docs/plan-vorlagen-aufbereiten.md
   § 6.1): je Abschnitt kurze Sätze, jeder mit [n] — ein Tipp darauf zeigt das
   wörtliche Zitat, Dokument und Seite und springt ins PDF auf genau diese
   Seite. Gegengelesen wird die Aussage, nicht das Dokument. */

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { ABSCHNITT, INHALT, META } from "@/components/session/unterlagen-typo";
import { angabenWort, aussagenGruppen } from "@/lib/unterlagen";
import { ErklaerBereich, Erklaert } from "@/components/session/begriffe";

export type Dossier = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["dossier"]>;
type Aussage = Dossier["sections"][number]["statements"][number];

export function Beleg({ a }: { a: Aussage }) {
  const [offen, setOffen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOffen((o) => !o)} aria-expanded={offen}
        aria-label={`Beleg ${a.list_no ?? ""}: ${a.doc_label ?? "Dokument"}${a.page ? `, Seite ${a.page}` : ""}`}
        className={cn("ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded px-1 align-[0.1em] font-mono text-[10px] font-medium",
          offen ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-primary/15 hover:text-foreground")}>
        {a.list_no ?? "·"}
      </button>
      {offen && (
        <span className="mt-1.5 block rounded-lg border border-border bg-muted/40 p-2.5 text-sm">
          <span className="block border-l-2 border-primary/50 pl-2.5 text-foreground/90">„{a.quote.trim()}“</span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-2 text-meta text-muted-foreground">
            {a.doc_label}{a.page ? ` · S. ${a.page}` : ""}
            {a.url && (
              <a href={a.url} target="_blank" rel="noreferrer"
                className="inline-flex min-h-8 items-center gap-1 font-medium text-primary underline decoration-dashed underline-offset-2">
                im PDF öffnen <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            )}
          </span>
        </span>
      )}
    </>
  );
}

/** Die Aussagen eines Abschnitts, nach Art gruppiert (`aussagenGruppen`):
 *  gewöhnliche Sätze als Liste, Termine als zweispaltige Reihe (Datum · was),
 *  jede weitere Art unter einer stillen Zwischenzeile. */
export function DossierAussagen({ s, className }: { s: Dossier["sections"][number]; className?: string }) {
  if (s.statements.length === 0 && s.status === "stated_none") {
    return <p className={cn(INHALT, className)}>Laut Vorlage keine.</p>;
  }
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {aussagenGruppen(s.statements).map((g, gi) => (
        <div key={gi}>
          {g.label && <p className={cn(META, "mb-1 font-medium")}>{g.label}</p>}
          {g.kind === "dates" ? (
            <ul className="flex flex-col gap-1.5">
              {g.aussagen.map((a, i) => (
                <li key={i} className={cn(INHALT, "grid grid-cols-[auto_minmax(0,1fr)] gap-x-4")}>
                  {/* `auto` statt fester Breite: Tabellenziffern machen jedes Datum
                      gleich breit, die Spalte steht also ohne Maß bündig. */}
                  <span className="whitespace-nowrap tabular-nums text-muted-foreground">
                    {a.date ? new Date(`${a.date}T12:00:00`).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—"}
                  </span>
                  <ErklaerBereich>
                    <Erklaert text={a.text} />
                    <Beleg a={a} />
                  </ErklaerBereich>
                </li>
              ))}
            </ul>
          ) : (
            <ul className="flex list-disc flex-col gap-1.5 pl-5 marker:text-muted-foreground">
              {g.aussagen.map((a, i) => (
                <li key={i} className={cn(INHALT, a.kind === "not_included" && "text-muted-foreground")}>
                  <ErklaerBereich>
                    <Erklaert text={a.text} />
                    <Beleg a={a} />
                  </ErklaerBereich>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

export function DossierAbschnitt({ s }: { s: Dossier["sections"][number] }) {
  return (
    <div className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className={ABSCHNITT}>{s.title}</h3>
      <DossierAussagen s={s} className="mt-2" />
    </div>
  );
}

/** Das Dossier als aufklappbare Gliederung (Beschluss-Seite): Die ersten
 *  `offen` Abschnitte stehen offen, die übrigen als Zeile mit ihrer Zahl —
 *  die Seite zeigt zuerst, WAS es gibt, und erst auf Wunsch alles. Zugeklappte
 *  Abschnitte bleiben im DOM und im Druck (`hidden print:block`): Wer die
 *  Seite ausdruckt, bekommt das ganze Dossier. */
export function DossierGliederung({ d, offen = 2 }: { d: Dossier; offen?: number }) {
  const [auf, setAuf] = useState<ReadonlySet<string>>(() => new Set(d.sections.slice(0, offen).map((s) => s.key)));
  const umschalten = (key: string) => setAuf((alt) => {
    const neu = new Set(alt);
    if (neu.has(key)) neu.delete(key); else neu.add(key);
    return neu;
  });
  return (
    <div className="divide-y divide-border border-t border-border">
      {d.sections.map((s) => {
        const istAuf = auf.has(s.key);
        const id = `dossier-${s.key}`;
        return (
          <section key={s.key}>
            <h3>
              <button type="button" onClick={() => umschalten(s.key)} aria-expanded={istAuf} aria-controls={id}
                className="flex min-h-11 w-full items-center justify-between gap-3 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <span className={cn(ABSCHNITT, istAuf && "text-foreground")}>{s.title}</span>
                <span className={cn(META, "flex flex-none items-center gap-1.5")}>
                  {!istAuf && angabenWort(s.statements.length || 1)}
                  <ChevronDown aria-hidden className={cn("h-4 w-4 transition-transform duration-fluss print:hidden", istAuf && "rotate-180")} />
                </span>
              </button>
            </h3>
            <div id={id} className={cn("pb-4", !istAuf && "hidden print:block")}>
              <DossierAussagen s={s} />
            </div>
          </section>
        );
      })}
    </div>
  );
}

export function dossierStand(d: Dossier): string {
  const tag = d.created_at ? new Date(d.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "numeric" }) : null;
  const n = d.documents_read;
  return [tag ? `Stand ${tag}` : null, n === 1 ? "Vorlage" : `Vorlage + ${n - 1} ${n - 1 === 1 ? "Anlage" : "Anlagen"}`]
    .filter(Boolean).join(" · ");
}
