"use client";

// „Zu welchem Zins?" — der Block auf der Schulden-Seite unter der Zinslast.
//
// Die Zinslast (Posten 17) sagt, was der Bestand im Jahr kostet. Dieser Block
// sagt, was NEUES Geld kostet und was die Umschuldungen bringen — aus den
// Unterrichtungen des Rates. Drei Zeilen, keine Tabelle: die jüngsten
// Kreditaufnahmen mit Zinssatz, das Umschuldungsvolumen des Jahres mit der
// Ersparnis, und die Lücke im Bestand als Satz.

import { Beleg } from "@/components/haushalt/source";
import { Fundstelle } from "@/components/haushalt/fundstelle";
import { deMio } from "@/lib/haushalt";
import {
  deProzent, deZeitraum, istInnenfinanzierung, juengsteZinssaetze, type KrediteDaten,
} from "@/lib/haushalt-kredite";

export function KrediteBlock({ daten }: { daten: KrediteDaten | null }) {
  if (!daten || !daten.items.length) return null;
  const zins = juengsteZinssaetze(daten);
  const juengst = zins[0] ?? null;
  const umschuldung = daten.latest_refinancing;
  const mitErsparnis = [...daten.refinancing_by_year].reverse().find((j) => j.saving > 0) ?? null;
  const hKopf = juengst?.herkunft_id != null ? daten.provenance[String(juengst.herkunft_id)] ?? null : null;
  return (
    <section id="kredite" className="scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Zu welchem Zins die Stadt sich Geld leiht<Beleg q="loans" h={hKopf} />
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          Unterrichtungen {daten.coverage.from?.slice(0, 4)}–{daten.coverage.to?.slice(0, 4)}
          {" · "}{daten.coverage.notices} Berichte
        </span>
      </div>

      {juengst && (
        <>
          <p className="mt-2 font-display text-[26px] font-extrabold leading-none tracking-tight text-foreground">
            {deProzent(juengst.rate_pct)}
          </p>
          <p className="mt-1.5 max-w-[68ch] text-[12.5px] leading-relaxed text-muted-foreground">
            {daten.kind_names[juengst.kind]}{juengst.borrower ? ` · ${juengst.borrower}` : ""}
            {juengst.amount != null && <> · {deMio(juengst.amount / 1e6)}&#8239;Mio.&nbsp;€</>}
            {juengst.decided_at ? `, Kreditentscheidung vom ${juengst.decided_at.split("-").reverse().join(".")}` : ""}
            {juengst.fixed_years ? `, Zinsbindung ${juengst.fixed_years} Jahre` : ""}
            {" — "}Bericht {deZeitraum(juengst.period_from, juengst.period_to)}.
          </p>
        </>
      )}

      {zins.length > 1 && (
        <ul className="mt-3 flex flex-col gap-1 border-t border-dashed border-border pt-3 text-[12.5px]">
          {zins.slice(1).map((p) => (
            <li key={`${p.template_number}-${p.seq}`} className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="text-muted-foreground">
                {deZeitraum(p.period_from, p.period_to)} · {daten.kind_names[p.kind]}
                {p.borrower ? ` · ${p.borrower}` : ""}
                {p.amount != null ? ` · ${deMio(p.amount / 1e6)} Mio. €` : ""}
              </span>
              <span className="font-semibold tabular-nums text-foreground">
                {deProzent(p.rate_pct)}{istInnenfinanzierung(p) ? " (Innenfinanzierung)" : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      {umschuldung && umschuldung.amount != null && (
        <p className="mt-3 max-w-[68ch] border-t border-dashed border-border pt-3 text-[12.5px] leading-relaxed text-foreground/85">
          <strong>Umschuldungen.</strong> Zuletzt hat die Stadt Kommunalkredite über{" "}
          {deMio(umschuldung.amount / 1e6)}&#8239;Mio.&nbsp;€ umgeschuldet
          (Bericht {deZeitraum(umschuldung.period_from, umschuldung.period_to)}). Diese Kredite
          laufen in Dreimonats-Tranchen und werden jedes Quartal neu ausgeschrieben — eine
          Jahressumme zählte dasselbe Geld viermal.
          {mitErsparnis && (
            <> {mitErsparnis.year} bezifferte die Verwaltung die Ersparnis gegenüber herkömmlicher
              Kommunalkreditfinanzierung mit{" "}
              {Math.round(mitErsparnis.saving).toLocaleString("de-DE")}&#8239;€ in {mitErsparnis.saving_notices}{" "}
              {mitErsparnis.saving_notices === 1 ? "Bericht" : "Berichten"}; für die späteren Jahre nennt sie keine Zahl.
            </>
          )}
        </p>
      )}

      <p className="mt-2.5 max-w-[68ch] text-[12px] leading-relaxed text-muted-foreground">
        {daten.scope_note}
        {daten.coverage.gaps.length > 0 && (
          <> Im Bestand fehlen die Jahre{" "}
            {daten.coverage.gaps.map((g) => (g.from === g.to ? `${g.from}` : `${g.from}–${g.to}`)).join(", ")}.
          </>
        )}
      </p>
      <Fundstelle h={hKopf} className="mt-3" />
    </section>
  );
}
