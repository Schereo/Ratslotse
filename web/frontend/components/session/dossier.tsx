"use client";

/* Das belegte Dossier in „Aus den Unterlagen" (docs/plan-vorlagen-aufbereiten.md
   § 6.1): je Abschnitt kurze Sätze, jeder mit [n] — ein Tipp darauf zeigt das
   wörtliche Zitat, Dokument und Seite und springt ins PDF auf genau diese
   Seite. Gegengelesen wird die Aussage, nicht das Dokument. */

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { ABSCHNITT, INHALT } from "@/components/session/unterlagen-typo";

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

export function DossierAbschnitt({ s }: { s: Dossier["sections"][number] }) {
  return (
    <div className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className={ABSCHNITT}>{s.title}</h3>
      {s.statements.length === 0 && s.status === "stated_none" ? (
        <p className={cn(INHALT, "mt-2")}>Laut Vorlage keine.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1.5">
          {s.statements.map((a, i) => (
            <li key={i} className={cn(INHALT,
              a.kind === "not_included" && "text-muted-foreground")}>
              {a.kind === "not_included" && <span className="font-medium">Nicht Teil des Beschlusses: </span>}
              {a.date && a.kind === "dates" && <span className="font-medium">{new Date(`${a.date}T12:00:00`).toLocaleDateString("de-DE")}: </span>}
              {a.text}
              <Beleg a={a} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function dossierStand(d: Dossier): string {
  const tag = d.created_at ? new Date(d.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "numeric" }) : null;
  const n = d.documents_read;
  return [tag ? `Stand ${tag}` : null, n === 1 ? "Vorlage" : `Vorlage + ${n - 1} ${n - 1 === 1 ? "Anlage" : "Anlagen"}`]
    .filter(Boolean).join(" · ");
}
