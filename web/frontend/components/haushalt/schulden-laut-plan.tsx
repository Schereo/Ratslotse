"use client";

// „Was die Pläne erwarten" — Block auf /haushalt/schulden (Plan
// Haushalt-Datenquellen, PR 3b).
//
// Quelle: die Übersichten des Haushaltsplans (Anlage 003). Sie nennen je
// Plan den VORAUSSICHTLICHEN Schuldenstand zu Beginn des Planjahres —
// für den Kernhaushalt UND je Eigenbetrieb, nach Schuldenart — und die
// Fälligkeiten der Verpflichtungsermächtigungen.
//
// Was die Seite damit sagt, und was bewusst nicht:
// - Kernhaushalt: Die Erwartung traf das spätere Ist (Jahrbuch-Reihe oben)
//   bis auf 1.000 €. Das wird aus den Daten gerechnet, nicht behauptet.
// - Eigenbetriebe: nur die Plan-Werte, KEIN Vergleich mit der Jahrbuch-Spalte
//   „Eigenbetriebe" — die zählt einen anderen Kreis (alle kaufmännisch
//   geführten Einrichtungen) und läge scheinbar daneben.
// - Keine Bewertungsfarbe: Ein steigender Kreditstand der Bäder heißt, dass
//   gebaut wird, nicht dass etwas schiefgeht.

import { useMemo } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deMio } from "@/lib/haushalt";
import { Beleg } from "@/components/haushalt/source";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";

type Antwort = ApiAntwort<"/council/budget/debt">;

const KREDITE = "1.2";
const KURZ: Record<string, string> = {
  "Kernhaushalt": "Kernhaushalt",
  "Eigenbetrieb Gebäudewirtschaft und Hochbau": "Gebäudewirtschaft",
  "Eigenbetrieb Bäder": "Bäder",
};
const mioText = (euro: number | null | undefined) =>
  euro == null ? "—" : `${deMio(euro / 1e6)} Mio. €`;

export function SchuldenLautPlan() {
  const { data } = useFetch<Antwort>("/council/budget/debt");
  const plan = useMemo(() => data?.debt_plan ?? [], [data]);
  const ve = useMemo(() => data?.commitments ?? [], [data]);

  const jahre = useMemo(() => [...new Set(plan.map((z) => z.budget_year))].sort((a, b) => a - b), [plan]);
  const kredite = (jahr: number, entity: string) =>
    plan.find((z) => z.budget_year === jahr && z.entity === entity && z.code === KREDITE)?.start_expected ?? null;

  // Die Treffsicherheit beim Kernhaushalt: erwarteter Stand zu Beginn des
  // Planjahres gegen die Kreditmarkt-Schulden der Jahrbuch-Reihe zum Ende des
  // Vorjahres — dieselbe Abgrenzung (Kredite für Investitionen).
  const treffer = useMemo(() => {
    // `series` ist im Vertrag untypisiert (Altbestand der Jahrbuch-Reihe).
    const reihe = (data?.series ?? []) as { year: number; credit_market?: number | null }[];
    const ist = new Map(reihe.map((s) => [s.year, s.credit_market ?? null] as const));
    return jahre.map((j) => {
      const erwartet = kredite(j, "Kernhaushalt");
      const wirklich = ist.get(j - 1);
      return erwartet != null && wirklich != null ? Math.abs(erwartet - wirklich) : null;
    }).filter((d): d is number => d != null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, jahre]);

  if (jahre.length < 2) return null;
  const erstes = jahre[0], letztes = jahre[jahre.length - 1];
  const betriebe = (j: number) => ["Eigenbetrieb Gebäudewirtschaft und Hochbau", "Eigenbetrieb Bäder"]
    .reduce((s, e) => s + (kredite(j, e) ?? 0), 0);
  const veJahre = [...new Set(ve.map((z) => z.budget_year))].sort((a, b) => a - b);
  const veLetzt = ve.filter((z) => z.budget_year === letztes);
  const veSumme = veLetzt.reduce((s, z) => s + z.amount, 0);

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="max-w-[76ch]">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Laut Haushaltsplan · Pläne {erstes}–{letztes}
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          Der Plan {letztes} erwartet {mioText(betriebe(letztes))} Kredite bei Gebäudewirtschaft
          und Bädern — im Plan {erstes} waren es {mioText(betriebe(erstes))}
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-foreground/90">
          Jeder Haushaltsplan nennt, mit welchem Schuldenstand die Stadt voraussichtlich ins
          Planjahr geht — für den Kernhaushalt und für jeden Eigenbetrieb<Beleg q="debt_plan" />.
          Der Kernhaushalt baut seine Kredite ab, von {mioText(kredite(erstes, "Kernhaushalt"))} auf{" "}
          {mioText(kredite(letztes, "Kernhaushalt"))}
          {treffer.length >= 3 && Math.max(...treffer) <= 1000 && (
            <>; die Erwartung traf in allen {treffer.length} überprüfbaren Jahren das spätere Ist bis auf
              höchstens 1.000&nbsp;€</>
          )}. Gebaut wird in den Eigenbetrieben — Schulen und Kitas über die Gebäudewirtschaft,
          Schwimmbäder über den Bäderbetrieb —, und dort wachsen die Kredite.
        </p>
      </div>

      <ZahlenTabelle
        spalten={[
          { title: "Plan" },
          { title: "Kernhaushalt", zahl: true },
          { title: "Gebäudewirtschaft", zahl: true },
          { title: "Bäder", zahl: true },
        ]}
      >
        {jahre.slice().reverse().map((j) => (
          <tr key={j}>
            <TextZelle>
              <span className="font-semibold text-foreground">Anfang {j}</span>
              <span className="ml-2 font-mono text-[10px] text-muted-foreground">erwartet im Plan {j}</span>
            </TextZelle>
            {Object.keys(KURZ).map((e) => (
              <BetragZelle key={e} euro={kredite(j, e)} label={KURZ[e]} text={mioText(kredite(j, e))}
                className="text-foreground dark:text-foreground" />
            ))}
          </tr>
        ))}
      </ZahlenTabelle>
      <p className="-mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
        Kredite für Investitionen, voraussichtlicher Stand zu Beginn des Planjahres. Die Übersicht
        nennt dazu die übrigen Verbindlichkeiten (Lieferungen, Transfers, Sonstiges) — sie sind keine
        aufgenommenen Kredite und stehen deshalb nicht in dieser Tabelle.
      </p>

      {veLetzt.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-dashed border-border pt-3">
          <h3 className="text-[14.5px] font-semibold leading-snug text-foreground">
            Aufträge auf Rechnung späterer Jahre: {mioText(veSumme)} im Plan {letztes}
          </h3>
          <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Mit einer Verpflichtungsermächtigung darf die Stadt schon im Planjahr Aufträge vergeben, die
            sie erst später bezahlt<Beleg q="debt_plan" />. Aus dem Plan {letztes} werden fällig:{" "}
            {veLetzt.map((z) => `${z.due_year} ${mioText(z.amount)}`).join(" · ")}.
          </p>
          {veJahre.length >= 3 && (
            <ul className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] tabular-nums text-muted-foreground">
              <li className="font-sans font-medium">Verpflichtungsermächtigungen je Plan:</li>
              {veJahre.map((j) => (
                <li key={j}>
                  {j}: {mioText(ve.filter((z) => z.budget_year === j).reduce((s, z) => s + z.amount, 0))}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
