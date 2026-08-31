"use client";

// Wer den Konzern ausmacht: eine Zeile je Aufgabenträger, mit Balken.
//
// Die Konsolidierungszeile steht BEWUSST unter einem Strich und nicht in der
// Rangliste. Sie ist kein Betrieb, sondern ein Abzug — die Geschäfte, die die
// Betriebe untereinander machen und die sonst doppelt zählten. Als neunter
// Balken in derselben Reihe sähe sie aus wie ein Träger mit negativen
// Einnahmen, und das ist sie nicht.
//
// Die Rechnung steht am Ende offen da (Träger − Verrechnung = Summe), weil
// genau sie im Dokument geprüft ist: Wir übernehmen eine Aufstellung nur,
// wenn sie aufgeht.

import { deMio } from "@/lib/haushalt";
import { ART, KURZ, KonzernTraeger } from "@/lib/haushalt-konzern";

export function KonzernTraegerListe({ zeilen, verrechnung, summe }: {
  zeilen: KonzernTraeger[];
  verrechnung: KonzernTraeger | null;
  summe: number | null;
}) {
  if (!zeilen.length) return null;
  const max = Math.max(...zeilen.map((z) => z.amount));
  return (
    <div>
      <ol className="flex flex-col gap-2">
        {zeilen.map((z, i) => (
          <li key={z.entity_key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 text-[13px] font-semibold leading-snug">
                {KURZ[z.entity_key] ?? z.entity}
              </span>
              <span className="flex-none font-mono text-[11.5px] tabular-nums text-muted-foreground">
                {deMio(z.amount / 1e6)}&#8239;Mio.&nbsp;€
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full"
                style={{
                  width: `${Math.max((z.amount / max) * 100, 1)}%`,
                  background: `var(--hh-ein-${Math.min(i, 6)})`,
                }} />
            </div>
            {ART[z.entity_key] && (
              <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                {ART[z.entity_key]}
              </p>
            )}
          </li>
        ))}
      </ol>
      {verrechnung && (
        <div className="mt-3 border-t border-dashed border-border pt-2.5">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[13px] font-semibold leading-snug">
              Verrechnung untereinander
            </span>
            <span className="flex-none font-mono text-[11.5px] tabular-nums text-muted-foreground">
              {deMio(verrechnung.amount / 1e6)}&#8239;Mio.&nbsp;€
            </span>
          </div>
          <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Geschäfte der Betriebe miteinander — der Zuschuss der Stadt ans Klinikum, die Miete,
            die sie ihrer Gebäudewirtschaft zahlt. In einer gemeinsamen Rechnung stünden sie
            zweimal, deshalb kommen sie wieder heraus.
          </p>
        </div>
      )}
      {summe != null && (
        <div className="mt-2.5 flex items-baseline justify-between gap-3 border-t border-border pt-2.5">
          <span className="text-[13px] font-bold">Konzern Stadt Oldenburg</span>
          <span className="font-display text-[15px] font-bold tabular-nums">
            {deMio(summe / 1e6)}&#8239;Mio.&nbsp;€
          </span>
        </div>
      )}
    </div>
  );
}
