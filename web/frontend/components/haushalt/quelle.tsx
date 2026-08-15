"use client";

// Quellen-System des Haushalts-Bereichs.
//
// Vorher trug jede Karte eine freitextliche Quellenzeile — gut gemeint, aber
// nicht nachprüfbar: Man sah nicht, WELCHE Zahl aus WELCHER Tabelle stammt,
// und ein Klick führte bestenfalls auf ein 200-seitiges PDF. Jetzt gilt die
// Fußnoten-Grammatik des Ratsgesprächs auch für Zahlen: Jede Angabe trägt
// einen kleinen Beleg-Chip, und am Seitenende steht das Verzeichnis mit
// Dokument, Fundstelle, Stand, Lizenz und Direktlink.
//
// Die Nummerierung läuft SEITENWEISE (1, 2, 3 …), nicht global über das
// Verzeichnis: Sonst trägt eine Seite mit zwei Quellen die Nummern 2 und 4,
// und die Fußnote verweist ins Leere. Welche Quellen eine Seite nutzt, sagt
// sie dem Provider — dieselbe Liste, die unten das Verzeichnis rendert.

import { createContext, useContext, useState, type ReactNode } from "react";
import { ExternalLink, FileText } from "lucide-react";
import { QuellenSchluessel, QUELLEN, Quelle } from "@/lib/haushalt-quellen";
import { cn } from "@/lib/utils";

const SeitenQuellen = createContext<QuellenSchluessel[]>([]);

/** Klammert die Seite: legt fest, welche Quellen sie nutzt und in welcher
 *  Reihenfolge sie nummeriert werden. */
export function Quellenkontext({ schluessel, children }: {
  schluessel: QuellenSchluessel[];
  children: ReactNode;
}) {
  return <SeitenQuellen.Provider value={schluessel}>{children}</SeitenQuellen.Provider>;
}

/** Beleg-Chip direkt an der Zahl. Klick öffnet die Fundstelle. */
export function Beleg({ q, className }: { q: QuellenSchluessel; className?: string }) {
  const [offen, setOffen] = useState(false);
  const seite = useContext(SeitenQuellen);
  const quelle = QUELLEN[q];
  const idx = seite.indexOf(q);
  // Quelle nicht angemeldet: lieber keinen Chip als eine falsche Nummer.
  if (idx < 0) return null;
  const nr = idx + 1;
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOffen((o) => !o)}
        aria-label={`Beleg ${nr}: ${quelle.titel}`}
        aria-expanded={offen}
        className={cn(
          "ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded bg-primary/10 align-super text-[9px] font-bold text-primary transition-colors hover:bg-primary/20",
          offen && "bg-primary text-primary-foreground",
          className,
        )}
      >
        {nr}
      </button>
      {offen && (
        <span className="absolute bottom-full left-1/2 z-20 mb-1.5 block w-[280px] -translate-x-1/2 rounded-xl border border-border bg-card p-3 text-left shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]">
          <QuelleInhalt quelle={quelle} nr={nr} />
        </span>
      )}
    </span>
  );
}

function QuelleInhalt({ quelle, nr }: { quelle: Quelle; nr: number }) {
  return (
    <>
      <span className="block text-[11.5px] font-bold leading-snug">
        {nr}. {quelle.titel}
      </span>
      <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
        {quelle.fundstelle}
      </span>
      <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
        <span>{quelle.herausgeber}</span>
        <span>·</span>
        <span>Stand {quelle.stand}</span>
        {quelle.lizenz && (<><span>·</span><span>{quelle.lizenz}</span></>)}
      </span>
      {quelle.url && (
        <a href={quelle.url} target="_blank" rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-semibold text-primary">
          {quelle.art === "csv" ? "Datensatz öffnen" : "Dokument öffnen"}
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </>
  );
}

/** Quellenverzeichnis am Seitenende — die Langfassung aller benutzten Belege. */
export function Quellenverzeichnis({ schluessel }: { schluessel: QuellenSchluessel[] }) {
  const genutzt = schluessel;
  if (!genutzt.length) return null;
  return (
    <section aria-labelledby="quellen-titel" className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <FileText className="h-3.5 w-3.5 text-muted-foreground" />
        <h2 id="quellen-titel" className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Woher diese Zahlen kommen
        </h2>
      </div>
      <ol className="mt-2.5 space-y-2.5">
        {genutzt.map((k, i) => {
          const q = QUELLEN[k];
          const nr = i + 1;
          return (
            <li key={k} className="flex gap-2.5">
              <span className="mt-0.5 inline-flex h-4 w-4 flex-none items-center justify-center rounded bg-primary/10 text-[9px] font-bold text-primary">
                {nr}
              </span>
              <div className="min-w-0">
                <p className="text-[12.5px] font-semibold leading-snug">{q.titel}</p>
                <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">{q.fundstelle}</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-2 font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
                  <span>{q.herausgeber}</span><span>·</span><span>Stand {q.stand}</span>
                  {q.lizenz && (<><span>·</span><span>{q.lizenz}</span></>)}
                </p>
                {q.url && (
                  <a href={q.url} target="_blank" rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-primary">
                    {q.art === "csv" ? "Datensatz öffnen" : "Dokument öffnen"}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Wir hosten diese Unterlagen nicht, sondern verlinken das Original. Rechenwege, die wir
        selbst gebildet haben (Anteile, Differenzen, Reichweiten), stehen an Ort und Stelle als
        solche gekennzeichnet — sie sind keine amtlichen Kennzahlen.
      </p>
    </section>
  );
}
