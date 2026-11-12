"use client";

/* „Was die Änderungsanträge wollen" (docs/plan-vorlagen-aufbereiten.md,
   § 6.1, Punkt 3): je Antrag Fraktion, Art, Stelle, alt gegen neu, Bedeutung
   und Begründung — gelesen von council/motions.py, jede Angabe belegt. Der
   KI-Stern sitzt einmal an der Überschrift; der Wortlaut alt/neu ist Zitat. */

import { ExternalLink } from "lucide-react";
import { KiStern } from "@/components/ki-stern";
import { OUTCOME_DOT_CLS, OUTCOME_WORD, normalizeParty, partyBrand } from "@/components/decision-ui";
import type { ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";
import { kurzerDiff } from "@/lib/unterlagen";

export type Antrag = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["amendments"]>[number];

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
export const MUSTER_WORT: Record<string, string> = {
  replace: "ersetzt", delete: "streicht", add: "ergänzt", rewrite: "fasst neu", counter: "Gegenvorschlag",
};

function Wortdiff({ diff }: { diff: string[][] }) {
  return (
    <p className="text-lese text-foreground">
      {kurzerDiff(diff).map(([op, text], i) => (
        <span key={i}>
          {i > 0 && " "}
          {op === "-" ? <del className="text-muted-foreground decoration-signal/70">{text}</del>
            : op === "+" ? <ins className="rounded-sm bg-signal/10 px-0.5 font-medium text-foreground no-underline">{text}</ins>
              : <span>{text}</span>}
        </span>
      ))}
    </p>
  );
}

function Zitat({ titel, text, alt }: { titel: string; text: string; alt?: boolean }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{titel}</p>
      <blockquote className={cn("mt-0.5 line-clamp-6 border-l-2 pl-3 text-[15px] leading-relaxed",
        alt ? "border-border text-muted-foreground" : "border-signal/60 text-foreground")}>„{text.trim()}“</blockquote>
    </div>
  );
}

export function AntragKarte({ a }: { a: Antrag }) {
  const partei = a.applicants[0] ? normalizeParty(a.applicants[0]) : null;
  const brand = partei ? partyBrand(partei) : null;
  const ergebnis = a.outcome as DecisionOutcome | null;
  return (
    <li className="rounded-xl border border-border p-3.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: brand?.bg ?? "hsl(var(--muted-foreground))" }} />
        <span className="text-sm font-semibold text-foreground">{a.applicants.join(", ") || "Antrag"}</span>
        {a.pattern && MUSTER_WORT[a.pattern] && (
          <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] font-medium text-foreground">{MUSTER_WORT[a.pattern]}</span>
        )}
        {ergebnis && (
          <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
            <span aria-hidden className={cn("h-2 w-2 rounded-full", OUTCOME_DOT_CLS[ergebnis])} /> {OUTCOME_WORD[ergebnis]}
          </span>
        )}
        <a href={a.url} target="_blank" rel="noreferrer" aria-label={`Antrag öffnen (Unterlage ${a.list_no})`}
          className="ml-auto inline-flex min-h-8 items-center gap-1 rounded-md px-1.5 font-mono text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground">
          [{a.list_no}] <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>
      {a.target && <p className={cn(KICKER, "mt-2")}>{a.target}</p>}
      {a.read ? (
        <div className="mt-2 flex flex-col gap-2.5">
          {a.meaning && <p className="text-lese font-medium text-foreground">{a.meaning.text}</p>}
          {a.diff && a.diff.some(([op]) => op !== "=") ? (
            <Wortdiff diff={a.diff} />
          ) : (
            <>
              {a.before && <Zitat titel="Bisher" text={a.before.quote} alt />}
              {a.after && <Zitat titel={a.pattern === "add" ? "Ergänzung" : "Neu"} text={a.after.quote} />}
            </>
          )}
          {a.base_missing && <p className="text-sm text-muted-foreground">Die geltende Fassung liegt den Unterlagen nicht bei.</p>}
          {a.base_template && <p className="text-sm text-muted-foreground">Bezieht sich auf die Fassung {a.base_template}.</p>}
          {a.reason && <p className="text-sm italic text-muted-foreground">{a.reason.text}</p>}
        </div>
      ) : (
        <p className="mt-1 text-sm text-foreground">{a.label}</p>
      )}
    </li>
  );
}

export function Aenderungsantraege({ antraege }: { antraege: Antrag[] }) {
  if (!antraege.length) return null;
  return (
    <div id="antraege" className="scroll-mt-24 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className={cn(KICKER, "flex items-center gap-1")}>
        {antraege.length === 1 ? "Was der Änderungsantrag will" : `Was die ${antraege.length} Anträge wollen`}
        {antraege.some((a) => a.read) && (
          <KiStern text="Automatisch aus den Anträgen gelesen. Alt und neu stehen im Wortlaut; verbindlich sind die Anträge im Ratsinfo." />
        )}
      </h3>
      <ul className="mt-2 flex flex-col gap-2">{antraege.map((a) => <AntragKarte key={a.document_id} a={a} />)}</ul>
    </div>
  );
}
