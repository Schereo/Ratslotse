"use client";

// Drei Blöcke unter der Einsatzliste: die Briefwahl (Rohrs bessere Hälfte),
// die Stichwahl von 2021 (was sie lehrt und was nicht) und die Vorbehalte —
// die Sätze aus `caveats`, damit niemand die Rechnung für eine Umfrage hält.

import { KICKER } from "@/components/wahlabend/bausteine";
import type { Potenzial } from "@/lib/potenzial";
import { prozent, zahl } from "@/lib/wahlabend";

function Block({ kicker, titel, children }: { kicker: string; titel: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <div className={KICKER}>{kicker}</div>
      <h2 className="mt-1 font-display text-[22px] font-bold tracking-tight">{titel}</h2>
      {children}
    </section>
  );
}

function Grosszahl({ wert, name }: { wert: string; name: string }) {
  return (
    <div>
      <div className="font-display text-[28px] font-bold tabular-nums leading-none tracking-tight">{wert}</div>
      <div className={`${KICKER} mt-1.5`}>{name}</div>
    </div>
  );
}

export function Briefwahl({ p }: { p: Potenzial }) {
  const brief = p.districts.filter((z) => z.postal);
  const rohr = brief.reduce((s, z) => s + z.rohr, 0);
  const prange = brief.reduce((s, z) => s + z.prange, 0);
  const pool = brief.reduce((s, z) => s + z.pool, 0);
  return (
    <Block kicker="Briefwahl" titel="Rohrs bessere Hälfte">
      <div className="mt-4 grid gap-4 rounded-2xl border border-border bg-card p-5 sm:grid-cols-[auto_1fr] sm:gap-8">
        <div className="flex gap-8">
          <Grosszahl wert={prozent(p.rohr_pct_postal)} name="Rohr per Brief" />
          <Grosszahl wert={prozent(p.rohr_pct_urn)} name="Rohr an der Urne" />
        </div>
        <div className="text-[13.5px] leading-relaxed text-muted-foreground">
          <p>
            Anteil an den Stimmen, die auf einen der beiden fielen. In den {brief.length} Briefwahlbezirken stand es{" "}
            <strong className="font-semibold text-foreground">{zahl(rohr)} zu {zahl(prange)}</strong> für Rohr — dort liegen außerdem{" "}
            {zahl(pool)} Stimmen der Ausgeschiedenen. 2021 hatte Fuhrhop dieselbe Schere: {prozent(p.lessons_2021.fuhrhop_pct_postal_runoff)} per
            Brief, {prozent(p.lessons_2021.fuhrhop_pct_urn_runoff)} an der Urne.
          </p>
          <p className="mt-2">
            Wer per Brief wählt, wählt sicher — der Sonntag kann regnen, das Kind krank werden. An jeder Tür gehört
            deshalb der Hinweis dazu, dass die Briefwahl für die Stichwahl neu beantragt werden muss, wenn das beim
            ersten Mal nicht mit angekreuzt war. Fristen und Antrag nennt die Stadt auf oldenburg.de.
          </p>
        </div>
      </div>
    </Block>
  );
}

export function Lehren2021({ p }: { p: Potenzial }) {
  const l = p.lessons_2021;
  const max = Math.max(...l.fuhrhop_growth_by_fifth, 1);
  const beschriftung = ["schwächstes Fünftel", "2.", "3.", "4.", "Hochburgen"];
  return (
    <Block kicker="2021" titel="Krogmann gegen Fuhrhop — was es lehrt, und was nicht">
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-wrap gap-x-8 gap-y-4">
            <Grosszahl wert={`${zahl(l.voters_first)} → ${zahl(l.voters_runoff)}`} name="Wählende, 1. Wahlgang → Stichwahl" />
          </div>
          <div className="mt-4 divide-y divide-border text-[13px]">
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Fuhrhop</span><span className="font-mono tabular-nums">{zahl(l.fuhrhop_first)} → {zahl(l.fuhrhop_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann</span><span className="font-mono tabular-nums">{zahl(l.krogmann_first)} → {zahl(l.krogmann_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Fuhrhop-Anteil Urne</span><span className="font-mono tabular-nums">{prozent(l.fuhrhop_pct_urn_first)} → {prozent(l.fuhrhop_pct_urn_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Fuhrhop-Anteil Brief</span><span className="font-mono tabular-nums">{prozent(l.fuhrhop_pct_postal_first)} → {prozent(l.fuhrhop_pct_postal_runoff)}</span></div>
          </div>
          <p className="mt-3 rounded-xl border border-amber-300/50 bg-amber-50 px-3 py-2 text-[12.5px] leading-relaxed text-amber-900 dark:border-amber-700/40 dark:bg-amber-900/25 dark:text-amber-100">
            {l.note}
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className={KICKER}>Fuhrhop, Stichwahl ÷ 1. Wahlgang, je Fünftel ihrer Bezirksstärke</div>
          <ul className="mt-3 space-y-2">
            {l.fuhrhop_growth_by_fifth.map((x, i) => (
              <li key={i} className="flex items-center gap-3 text-[13px]">
                <span className="w-32 flex-none text-muted-foreground">{beschriftung[i] ?? `${i + 1}.`}</span>
                <span className="h-3 flex-none rounded-full" style={{ width: `${(55 * x) / max}%`, background: "hsl(var(--primary) / 0.6)" }} aria-hidden />
                <span className="font-mono tabular-nums">× {x.toFixed(2).replace(".", ",")}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
            Die Herausforderin wuchs dort am stärksten, wo sie am schwächsten war — in den Hochburgen war kaum noch
            Luft. Das ist die eine Lehre, die den Bundestagswahl-Effekt überlebt: Der Zuwachs kommt aus der Diaspora.
            Als Wanderungs-Schätzung taugt 2021 dagegen nicht; der Versuch lieferte Quoten über 100 %.
          </p>
        </div>
      </div>
    </Block>
  );
}

export function Vorbehalte({ p }: { p: Potenzial }) {
  return (
    <Block kicker="Vorbehalte" titel="Was diese Seite nicht weiß">
      <ul className="mt-3 space-y-2 text-[13.5px] leading-relaxed text-muted-foreground">
        {p.caveats.map((c, i) => (
          <li key={i} className="flex gap-2.5">
            <span aria-hidden className="mt-[9px] h-1.5 w-1.5 flex-none rounded-full bg-foreground/40" />
            <span>{c}</span>
          </li>
        ))}
        <li className="flex gap-2.5">
          <span aria-hidden className="mt-[9px] h-1.5 w-1.5 flex-none rounded-full bg-foreground/40" />
          <span>
            Quellen: die 133 Wahlbezirke des ersten Wahlgangs vom 13. September 2026 (Open Data der Stadt), die
            Zweitstimmen der Ratswahl am selben Tag, die Stichwahl vom 26. September 2021. Bezirksgrenzen: openGEOdata
            der Stadt. Gerechnet von Ratslotse, nicht von einem Institut.
          </span>
        </li>
      </ul>
    </Block>
  );
}
