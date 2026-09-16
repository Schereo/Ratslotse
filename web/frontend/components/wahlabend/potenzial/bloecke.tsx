"use client";

// Unter der Einsatzliste folgen Briefwahl, die Vergleiche mit 2021 und 2014
// sowie die methodischen Vorbehalte aus `caveats`.

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

function mitVorzeichen(wert: number): string {
  return `${wert > 0 ? "+" : wert < 0 ? "−" : ""}${zahl(Math.abs(wert))}`;
}

export function Briefwahl({ p }: { p: Potenzial }) {
  const brief = p.districts.filter((z) => z.postal);
  const rohr = brief.reduce((s, z) => s + z.rohr, 0);
  const prange = brief.reduce((s, z) => s + z.prange, 0);
  const pool = brief.reduce((s, z) => s + z.pool, 0);
  return (
    <Block kicker="Briefwahl" titel="Rohrs Stimmen bei der Briefwahl">
      <div className="mt-4 grid gap-4 rounded-2xl border border-border bg-card p-5 sm:grid-cols-[auto_1fr] sm:gap-8">
        <div className="flex gap-8">
          <Grosszahl wert={prozent(p.rohr_pct_postal)} name="Rohr per Brief" />
          <Grosszahl wert={prozent(p.rohr_pct_urn)} name="Rohr an der Urne" />
        </div>
        <div className="text-[13.5px] leading-relaxed text-muted-foreground">
          <p>
            Die Prozentwerte beziehen sich nur auf Stimmen für Rohr und Prange. In den {brief.length} Briefwahlbezirken
            erhielt Rohr <strong className="font-semibold text-foreground">{zahl(rohr)} Stimmen und Prange {zahl(prange)}</strong>.
            Hinzu kommen {zahl(pool)} Stimmen für ausgeschiedene Kandidaturen. Auch 2021 war der Briefwahlanteil des
            grünen Kandidaten höher: Fuhrhop erreichte {prozent(p.lessons_2021.fuhrhop_pct_postal_runoff)} per Brief und{" "}
            {prozent(p.lessons_2021.fuhrhop_pct_urn_runoff)} an der Urne.
          </p>
          <p className="mt-2">
            Wer per Brief wählt, ist am Wahltag nicht auf den Weg zum Wahllokal angewiesen. Wer die Unterlagen schon
            bei der Hauptwahl auch für die Stichwahl beantragt hat, erhält sie laut Stadt automatisch. Andernfalls
            müssen sie für die Stichwahl neu beantragt werden. Ab dem 21. September ist das persönlich im Wahlbüro
            möglich; dort kann auch direkt gewählt werden. Aktuelle Hinweise und Fristen stehen auf oldenburg.de.
          </p>
        </div>
      </div>
    </Block>
  );
}

export function Lehren2021({ p }: { p: Potenzial }) {
  const l = p.lessons_2021;
  const beschriftung = ["Niedrigster Erstwahlanteil", "Zweites Fünftel", "Mittleres Fünftel", "Viertes Fünftel", "Höchster Erstwahlanteil"];
  return (
    <Block kicker="2021" titel="Krogmann gegen Fuhrhop: Was zeigt der Vergleich?">
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
          <div className={KICKER}>Fuhrhops Stimmen nach Wahlbezirken</div>
          <h3 className="mt-2 text-[16px] font-semibold leading-snug">Auch außerhalb seiner Hochburgen legte Fuhrhop zu.</h3>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
            Verglichen wird seine Stimmenzahl in denselben Urnenbezirken im ersten Wahlgang und in der Stichwahl.
          </p>
          <div className="mt-4 space-y-3 border-l-2 border-primary/35 pl-4 text-[13px]">
            <div>
              <div className={KICKER}>Wo sein Stimmenanteil zuvor niedrig war</div>
              <p className="mt-1 font-medium">Seine Stimmenzahl hat sich mehr als verdoppelt.</p>
            </div>
            <div>
              <div className={KICKER}>In seinen Hochburgen</div>
              <p className="mt-1 font-medium">Seine Stimmenzahl stieg ebenfalls, aber weniger stark.</p>
            </div>
          </div>
          <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">
            Die Bezirksergebnisse verraten nicht, wer seine Stimme gewechselt hat. Zudem fand die Stichwahl 2021 am
            Tag der Bundestagswahl statt. Das Muster lässt sich nicht einfach auf 2026 übertragen.
          </p>
          <details className="mt-4 border-t border-border pt-3 text-[12.5px] leading-relaxed text-muted-foreground">
            <summary className="cursor-pointer font-medium text-foreground">Alle fünf Gruppen und die Berechnung anzeigen</summary>
            <p className="mt-2">
              Die Urnenbezirke sind nach Fuhrhops Stimmenanteil im ersten Wahlgang in fünf Gruppen geordnet.
              Für jede Gruppe wird seine Stimmenzahl in der Stichwahl durch die Stimmenzahl im ersten Wahlgang geteilt.
              Der erste Wert bedeutet zum Beispiel: Aus 100 Stimmen wurden rechnerisch 228.
            </p>
            <ul className="mt-2 space-y-1">
              {l.fuhrhop_growth_by_fifth.map((x, i) => (
                <li key={i} className="flex justify-between gap-4">
                  <span>{beschriftung[i] ?? `${i + 1}. Fünftel`}</span>
                  <span className="font-mono tabular-nums text-foreground">× {x.toFixed(2).replace(".", ",")}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      </div>
    </Block>
  );
}

/** 2014 ergänzt den Vergleich mit 2021: Die Stichwahl fand zwei Wochen nach
 *  der Hauptwahl statt, ohne weitere Wahl am selben Tag. Die Gesamtzahlen
 *  zeigen Veränderungen der Beteiligung, aber nicht, wer erneut abstimmte. */
export function Lehren2014({ p }: { p: Potenzial }) {
  const l = p.lessons_2014;
  const zuKrogmann = l.krogmann_runoff - l.krogmann_first;
  const zuBaak = l.baak_runoff - l.baak_first;
  return (
    <Block kicker="Der Vergleich 2014" titel="Krogmann gegen Baak: die Stichwahl ohne Bundestagswahl">
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className="flex flex-wrap gap-x-8 gap-y-4">
            <Grosszahl wert={`${zahl(l.voters_first)} → ${zahl(l.voters_runoff)}`} name="Wählende, Hauptwahl → Stichwahl" />
            <Grosszahl wert={prozent(l.return_rate_pct)} name="der Wählendenzahl im ersten Wahlgang" />
          </div>
          <div className="mt-4 divide-y divide-border text-[13px]">
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann (SPD)</span><span className="font-mono tabular-nums">{zahl(l.krogmann_first)} → {zahl(l.krogmann_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Baak (CDU)</span><span className="font-mono tabular-nums">{zahl(l.baak_first)} → {zahl(l.baak_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Ausgeschieden: Rieken (Grüne), Kreuzwieser (WFO)</span><span className="font-mono tabular-nums">{zahl(l.eliminated_first)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann-Anteil Urne</span><span className="font-mono tabular-nums">{prozent(l.krogmann_pct_urn_first)} → {prozent(l.krogmann_pct_urn_runoff)}</span></div>
            <div className="flex justify-between py-1.5"><span className="text-muted-foreground">Krogmann-Anteil Brief</span><span className="font-mono tabular-nums">{prozent(l.krogmann_pct_postal_first)} → {prozent(l.krogmann_pct_postal_runoff)}</span></div>
          </div>
          <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
            {l.note} Im ersten Wahlgang entfielen {zahl(l.eliminated_first)} Stimmen auf die später ausgeschiedenen
            Kandidaturen. Krogmann gewann in der Stichwahl {zahl(zuKrogmann)} Stimmen hinzu, Baak {zahl(zuBaak)}.
            Wie sich diese Veränderungen zusammensetzen, lässt sich aus den Gesamtergebnissen nicht ablesen.
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-card p-5">
          <div className={KICKER}>Stimmenzahlen nach Stärke im ersten Wahlgang</div>
          <h3 className="mt-2 text-[16px] font-semibold leading-snug">Was änderte sich in schwachen und starken Bezirken?</h3>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
            Für jeden Kandidaten vergleichen wir seine 18 schwächsten und 18 stärksten Urnenbezirke. Entscheidend ist
            sein eigener Stimmenanteil im ersten Wahlgang; deshalb sind es bei Krogmann und Baak nicht dieselben Bezirke.
          </p>
          <div className="mt-4 space-y-4">
            {([
              { name: "Krogmann (SPD)", groups: l.krogmann_strength },
              { name: "Baak (CDU)", groups: l.baak_strength },
            ] as const).map(({ name, groups }) => (
              <div key={name} className="border-t border-border pt-3">
                <h4 className="text-[14px] font-semibold">{name}</h4>
                <div className="mt-2 grid grid-cols-2 gap-3">
                  {(["weak", "strong"] as const).map((key) => {
                    const g = groups[key];
                    return (
                      <div key={key}>
                        <div className={KICKER}>{key === "weak" ? "Schwächste 18" : "Stärkste 18"} Bezirke</div>
                        <div className="mt-1 font-display text-[23px] font-bold tabular-nums leading-none tracking-tight">
                          {mitVorzeichen(g.change)}
                        </div>
                        <div className="mt-1 text-[12px] text-muted-foreground">
                          Stimmen {g.change < 0 ? "weniger" : "mehr"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl bg-primary/5 p-3 text-[13px] leading-relaxed">
            <strong className="font-semibold">Fazit:</strong> In ihren zuvor schwächsten Bezirken legten beide
            Kandidaten zu. In seinen stärksten Bezirken gewann Krogmann weniger hinzu, Baak verlor dort leicht. Die
            Bezirksdaten zeigen nicht, welche Menschen ihre Wahl änderten oder warum. Ob sich das 2026 wiederholt, ist offen.
          </div>
          <details className="mt-4 border-t border-border pt-3 text-[12.5px] leading-relaxed text-muted-foreground">
            <summary className="cursor-pointer font-medium text-foreground">Ausgangszahlen und Berechnung anzeigen</summary>
            <p className="mt-2">
              Verglichen werden je Kandidat die 18 Urnenbezirke mit dem niedrigsten und höchsten eigenen Stimmenanteil
              im ersten Wahlgang, von insgesamt 88 Urnenbezirken. Briefwahlbezirke sind nicht enthalten.
            </p>
            <ul className="mt-2 space-y-1">
              {([
                { name: "Krogmann", groups: l.krogmann_strength },
                { name: "Baak", groups: l.baak_strength },
              ] as const).flatMap(({ name, groups }) => (["weak", "strong"] as const).map((key) => {
                const g = groups[key];
                return (
                  <li key={`${name}-${key}`}>
                    {name}, {key === "weak" ? "schwächste" : "stärkste"} Bezirke: {zahl(g.first)} → {zahl(g.runoff)} Stimmen
                    ({mitVorzeichen(g.change_pct)} %)
                  </li>
                );
              }))}
            </ul>
          </details>
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
            Quellen sind die Ergebnisse aus 133 Wahlbezirken vom 13. September 2026, die Open-Data-Datei der Ratswahl
            vom selben Tag und die amtlichen Bezirksdaten der Stichwahlen 2021 und 2014. Die Bezirksgrenzen stammen
            aus openGEOdata der Stadt. Die Berechnungen wurden von Ratslotse erstellt, nicht von einem Institut.
          </span>
        </li>
      </ul>
    </Block>
  );
}
