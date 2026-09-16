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

/** Zwei Enden statt fünf Balken: die schwächsten Bezirke einer Kandidatur
 *  gegen ihre Hochburgen — die eine Zahl links, die andere rechts, der
 *  Befund als Satz. Die fünf Fünftel dazwischen trägt die Antwort weiter,
 *  gezeigt werden sie nicht mehr (Tims Rückmeldung 16.09.: zu kompliziert). */
function ZweiEnden({ frage, links, rechts, satz }: {
  frage: string;
  links: { wert: string; name: string };
  rechts: { wert: string; name: string };
  satz: string;
}) {
  return (
    <div>
      <div className={KICKER}>{frage}</div>
      <div className="mt-2 grid grid-cols-2 gap-4">
        <div>
          <div className="font-display text-[26px] font-bold tabular-nums leading-none tracking-tight">{links.wert}</div>
          <div className="mt-1 text-[12px] text-muted-foreground">{links.name}</div>
        </div>
        <div>
          <div className="font-display text-[26px] font-bold tabular-nums leading-none tracking-tight">{rechts.wert}</div>
          <div className="mt-1 text-[12px] text-muted-foreground">{rechts.name}</div>
        </div>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{satz}</p>
    </div>
  );
}

function mal(x: number): string {
  return `${x.toFixed(1).replace(".", ",")}-mal`;
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
            Wer per Brief wählt, wählt sicher — der Sonntag kann regnen, das Kind krank werden. Wer bei der Hauptwahl
            die Unterlagen auch für die Stichwahl angefordert hat, bekommt sie laut Stadt automatisch; alle anderen
            beantragen sie neu. Ab dem 21. September geht das auch persönlich im Wahlbüro, mit Stimmabgabe vor Ort.
            Stand und Fristen: oldenburg.de.
          </p>
        </div>
      </div>
    </Block>
  );
}

export function Lehren2021({ p }: { p: Potenzial }) {
  const l = p.lessons_2021;
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
          <ZweiEnden
            frage="Wo Fuhrhop in der Stichwahl zulegte"
            links={{ wert: mal(l.fuhrhop_growth_by_fifth[0] ?? 0), name: "so viele Stimmen wie im 1. Wahlgang — in seinen schwächsten Bezirken" }}
            rechts={{ wert: mal(l.fuhrhop_growth_by_fifth.at(-1) ?? 0), name: "in seinen Hochburgen" }}
            satz="Der Herausforderer holte sein Plus dort, wo er schwach war — in den Hochburgen war kaum noch Luft. Das ist die eine Lehre, die den Bundestagswahl-Effekt überlebt. Als Schätzung, wer wohin wanderte, taugt 2021 nicht; der Versuch lieferte Quoten über 100 %."
          />
        </div>
      </div>
    </Block>
  );
}

/** 2014 ist der zweite Vergleich: Stichwahl zwei Wochen nach der Hauptwahl, ohne
 *  andere Wahl am selben Tag. Sie zeigt, was 2021 verdeckt — wer wiederkommt
 *  und wo. Die Lager waren andere (SPD gegen CDU, die Grünen ausgeschieden),
 *  deshalb steht sie neben 2021, nicht an seiner Stelle. */
export function Lehren2014({ p }: { p: Potenzial }) {
  const l = p.lessons_2014;
  const zuKrogmann = l.krogmann_runoff - l.krogmann_first;
  const zuBaak = l.baak_runoff - l.baak_first;
  return (
    <Block kicker="Der Vergleich 2014" titel="Krogmann gegen Baak — die Stichwahl ohne Bundestagswahl">
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-wrap gap-x-8 gap-y-4">
            <Grosszahl wert={`${zahl(l.voters_first)} → ${zahl(l.voters_runoff)}`} name="Wählende, Hauptwahl → Stichwahl" />
            <Grosszahl wert={prozent(l.return_rate_pct)} name="der Wählendenzahl des 1. Wahlgangs" />
          </div>
          <div className="mt-4 divide-y divide-border text-[13px]">
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann (SPD)</span><span className="font-mono tabular-nums">{zahl(l.krogmann_first)} → {zahl(l.krogmann_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Baak (CDU)</span><span className="font-mono tabular-nums">{zahl(l.baak_first)} → {zahl(l.baak_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Ausgeschieden: Rieken (Grüne), Kreuzwieser (WFO)</span><span className="font-mono tabular-nums">{zahl(l.eliminated_first)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann-Anteil Urne</span><span className="font-mono tabular-nums">{prozent(l.krogmann_pct_urn_first)} → {prozent(l.krogmann_pct_urn_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann-Anteil Brief</span><span className="font-mono tabular-nums">{prozent(l.krogmann_pct_postal_first)} → {prozent(l.krogmann_pct_postal_runoff)}</span></div>
          </div>
          <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
            {l.note} Von den {zahl(l.eliminated_first)} Stimmen der Ausgeschiedenen kamen netto {zahl(zuKrogmann)} bei
            Krogmann an und {zahl(zuBaak)} bei Baak — der Rest blieb zu Hause oder füllte auf, was die eigene Basis
            verlor.
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5 space-y-5">
          <ZweiEnden
            frage="Wie viele in der Stichwahl wählten, in % des 1. Wahlgangs"
            links={{ wert: prozent(l.return_by_fifth[0] ?? 0, 0), name: "in Krogmanns schwächsten Bezirken" }}
            rechts={{ wert: prozent(l.return_by_fifth.at(-1) ?? 0, 0), name: "in seinen Hochburgen" }}
            satz="Die Wählendenzahl hielt in den Hochburgen des Siegers besser als dort, wo er schwach war."
          />
          <ZweiEnden
            frage="Wo Krogmann in der Stichwahl zulegte"
            links={{ wert: mal(l.krogmann_growth_by_fifth[0] ?? 0), name: "so viele Stimmen wie in der Hauptwahl — in seinen schwächsten Bezirken" }}
            rechts={{ wert: mal(l.krogmann_growth_by_fifth.at(-1) ?? 0), name: "in seinen Hochburgen" }}
            satz={`Wie Fuhrhop 2021: Das Plus kam aus den schwachen Bezirken. Baak legte kaum zu (${mal(l.baak_growth_by_fifth[0] ?? 0)} bis ${mal(l.baak_growth_by_fifth.at(-1) ?? 0)}). Beides sind Verhältnisse von Gesamtzahlen, kein Verhalten einzelner Menschen — ob es für Rohr ebenso gilt, ist eine Annahme. Der Knopf „Wie 2014“ bei der Beteiligung setzt die gemessene Quote für alle drei Lager.`}
          />
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
            Open-Data-CSV der Ratswahl am selben Tag, die Stichwahlen 2021 und 2014 (amtliche Bezirksdaten). Bezirksgrenzen: openGEOdata
            der Stadt. Gerechnet von Ratslotse, nicht von einem Institut.
          </span>
        </li>
      </ul>
    </Block>
  );
}
