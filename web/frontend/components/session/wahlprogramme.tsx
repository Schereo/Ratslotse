"use client";

/* „Was die Wahlprogramme dazu sagen“ auf der Punkt-Seite (Schalter
   `wahlprogramm-am-punkt`, `council/programm_bezug.py`): je Liste im Rat, ob
   ihr Programm zur Ratswahl 2026 für oder gegen das Anliegen des Punkts
   spricht — mit der wörtlichen Stelle zum Vorlegen (Tim, 13.11.2026).

   Bewusst keine Vorhersage: kein „stimmt wahrscheinlich zu“, keine
   Prozentzahl. Das Zitat ist belegt, eine Abstimmung nicht. Deshalb auch
   keine Ampelfarben — Grün und Rot heißen auf dieser Seite angenommen und
   abgelehnt. Richtung trägt ein Zeichen, die Partei ihr Punkt. */

import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { normalizeParty, partyBrand } from "@/components/decision-ui";
import { KiStern } from "@/components/ki-stern";
import { ABSCHNITT, KARTENTITEL, META, ZITAT } from "@/components/session/unterlagen-typo";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";

export type ProgrammBezug = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["program_stances"]>;
type Einordnung = ProgrammBezug["parties"][number];

const HINWEIS = "Automatisch aus den Wahlprogrammen zur Ratswahl 2026 zugeordnet und geprüft. Die Zitate sind wörtlich; wie eine Fraktion abstimmt, sagen sie nicht.";

function Richtung({ e }: { e: Einordnung }) {
  const dafuer = e.stance === "for";
  const Zeichen = dafuer ? ArrowUp : ArrowDown;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border py-0.5 pl-1.5 pr-2 text-[11px] font-medium",
      dafuer ? "border-primary/25 bg-primary/5 text-foreground" : "border-border bg-muted text-foreground")}>
      <Zeichen className={cn("h-3 w-3", dafuer ? "text-primary" : "text-muted-foreground")} strokeWidth={2.5} aria-hidden />
      {dafuer ? "Programm spricht dafür" : "Programm spricht dagegen"}
    </span>
  );
}

function Liste({ e }: { e: Einordnung }) {
  const brand = partyBrand(normalizeParty(e.label));
  const fundstelle = e.page ? `Wahlprogramm, S. ${e.page}` : "Wahlprogramm";
  return (
    <li className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: brand?.bg ?? "hsl(var(--muted-foreground))" }} />
        <span className="text-sm font-semibold text-foreground">{e.label}</span>
        <Richtung e={e} />
        {e.basis === "principle" && <span className={META}>aus einem Grundsatz des Programms</span>}
      </div>
      <blockquote className={cn(ZITAT, "mt-2")}>„{e.quote}“</blockquote>
      <p className={cn(META, "mt-1.5")}>{e.reason}</p>
      <p className={cn(META, "mt-0.5")}>
        {e.program_url ? (
          <a href={e.program_url} target="_blank" rel="noreferrer" title={e.program_title}
            className="inline-flex min-h-8 items-center gap-1 underline decoration-dashed underline-offset-2 hover:text-foreground">
            {fundstelle} <ExternalLink className="h-3 w-3 flex-none" aria-hidden />
          </a>
        ) : fundstelle}
      </p>
    </li>
  );
}

export function Wahlprogramme({ bezug }: { bezug?: ProgrammBezug | null }) {
  if (!bezug?.parties.length) return null;
  return (
    <section aria-labelledby="wahlprogramme" className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h2 id="wahlprogramme" className={cn(KARTENTITEL, "flex items-center gap-1")}>
        Was die Wahlprogramme dazu sagen
        <KiStern text={HINWEIS} />
      </h2>
      {bezug.concern && (
        <p className={cn(META, "mt-1")}>
          <span className={cn(ABSCHNITT, "mr-1.5")}>Worum es geht</span>{bezug.concern}
        </p>
      )}
      <ul className="mt-4 flex flex-col gap-4">
        {bezug.parties.map((e) => <Liste key={e.slug} e={e} />)}
      </ul>
      {bezug.silent.length > 0 && (
        <p className={cn(META, "mt-4 border-t border-border pt-3")}>
          Keine passende Stelle gefunden in den Programmen von: {bezug.silent.join(", ")}
        </p>
      )}
    </section>
  );
}
