"use client";

// „Wer aus diesem Bereich Zuschüsse bekommt" — der Reiter „Zuschüsse" auf
// /haushalt/bereich (Plan Haushalt-Datenquellen, PR 3).
//
// Die Quelle ist die Übersicht über die Zuweisungen und Zuschüsse an Dritte
// in Anlage 003 des Haushaltsplans: je Zuschuss Beschreibung, Betrag im
// Planjahr und im Vorjahr, Erläuterung. Vereine und Träger stehen mit Namen
// da, wie im Dokument (Tims Entscheidung 24.09.2026).
//
// Sortiert nach Betrag, weil die Frage „wohin geht das Geld?" lautet — die
// Reihenfolge des Dokuments (laufende Nummer) sagt Leser*innen nichts. Die
// Suche filtert im Browser: Es sind je Teilhaushalt höchstens rund 60
// Zeilen, die ohnehin geladen sind (Logik-ins-Backend gilt für Mengen, die
// man nicht schon hat).
//
// KEINE BEWERTUNGSFARBE: Die Beträge stehen in Vordergrundfarbe, nicht grün
// wie sonst in der Zahlentabelle — ein Zuschuss ist kein „Plus". Die
// Veränderung zum Vorjahr steht als Text daneben, ohne Pfeil.

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deMio } from "@/lib/haushalt";
import { deZahl } from "@/components/grafik/format";
import { ZeitreiheMini } from "@/components/grafik/zeitreihe";
import { Beleg } from "@/components/haushalt/source";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";

type Antwort = ApiAntwort<"/council/budget/grants">;
type Zeile = Antwort["rows"][number];

const euro = (v: number | null | undefined) => (v == null ? "—" : `${deZahl(v, 0)} €`);

/** Die Veränderung zum Vorjahr als kurzer Text — oder nichts, wo sie keine ist. */
function veraenderung(z: Zeile): string | null {
  if (z.amount == null || z.amount_prior == null) return null;
  if (z.amount_prior === 0 && z.amount > 0) return "neu im Plan";
  if (z.amount === 0 && z.amount_prior > 0) return "entfällt";
  const d = z.amount - z.amount_prior;
  if (Math.abs(d) < 1) return null;
  return `${d > 0 ? "+" : "−"}${deZahl(Math.abs(d), 0)} € zum Vorjahr`;
}

export function ZuschuesseBereich({ subBudget, bereichName }: {
  subBudget: number;
  bereichName: string;
}) {
  const { data, loading } = useFetch<Antwort>(`/council/budget/grants?sub_budget=${subBudget}`);
  const [suche, setSuche] = useState("");

  const zeilen = useMemo(() => {
    const alle = (data?.rows ?? []).slice().sort((a, b) => (b.amount ?? 0) - (a.amount ?? 0));
    const q = suche.trim().toLowerCase();
    if (!q) return alle;
    return alle.filter((z) => [z.description, z.note, z.product_name]
      .some((t) => (t ?? "").toLowerCase().includes(q)));
  }, [data, suche]);

  if (loading) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Zuschüsse werden geladen …</p>;
  }
  const jahr = data?.year;
  const alle = data?.rows ?? [];
  if (!jahr || alle.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-border bg-card p-4 text-[12.5px] leading-relaxed text-muted-foreground">
        Für diesen Bereich führt die Übersicht der Zuschüsse an Dritte im Haushaltsplan
        {jahr ? ` ${jahr}` : ""} keine Zeile.<Beleg q="grants" />
      </p>
    );
  }

  const summe = alle.reduce((s, z) => s + (z.amount ?? 0), 0);
  const summeVor = alle.reduce((s, z) => s + (z.amount_prior ?? 0), 0);
  const reihe = (data?.totals ?? []).map((t) => ({ year: t.budget_year, value: t.amount / 1e6 }));
  const erste = data?.totals?.[0];
  const groesste = alle.reduce((m, z) => ((z.amount ?? 0) > (m.amount ?? 0) ? z : m), alle[0]);
  const anteil = summe > 0 ? Math.round(((groesste.amount ?? 0) / summe) * 100) : null;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-[76ch]">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Zuschüsse an Dritte · Haushaltsplan {jahr}
          </p>
          <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
            {alle.length} Zuschüsse über zusammen {deMio(summe / 1e6)}&#8239;Mio.&nbsp;€
          </h2>
          <p className="mt-2 text-[13px] leading-relaxed text-foreground/90">
            So viel will die Stadt {jahr} aus dem Bereich „{bereichName}“ an Vereine, Träger und
            Gesellschaften geben<Beleg q="grants" />; für {jahr - 1} standen{" "}
            {deMio(summeVor / 1e6)}&#8239;Mio.&nbsp;€ im Plan.
            {anteil != null && anteil >= 30 && (
              <> Der größte Posten — {groesste.description} — macht allein {anteil}&nbsp;% davon aus.</>
            )}
          </p>
        </div>
        {reihe.length >= 3 && erste && (
          <div className="w-[168px] flex-none">
            <ZeitreiheMini
              series={reihe}
              format={(v) => deZahl(v, 1)}
              ariaLabel={`Zuschüsse an Dritte in diesem Bereich, ${reihe.map((p) =>
                `${p.year}: ${deMio(p.value)} Mio. Euro`).join(", ")}.`}
            />
            <p className="mt-0.5 text-center font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
              Summe je Plan in Mio. €
            </p>
          </div>
        )}
      </div>

      <label className="relative block max-w-[420px]">
        <span className="sr-only">Zuschüsse durchsuchen</span>
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
          placeholder="Verein, Träger oder Zweck suchen …"
          className="h-9 w-full rounded-full border border-border bg-background pl-8 pr-3 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        />
      </label>

      {zeilen.length === 0 ? (
        <p className="text-[12.5px] text-muted-foreground">Kein Zuschuss passt zu „{suche}“.</p>
      ) : (
        <ZahlenTabelle
          spalten={[
            { title: "Zuschuss" },
            { title: `Plan ${jahr}`, zahl: true },
            { title: `Vorjahr ${jahr - 1}`, zahl: true },
          ]}
        >
          {zeilen.map((z) => {
            const v = veraenderung(z);
            return (
              <tr key={z.seq}>
                <TextZelle>
                  <span className="font-semibold text-foreground">{z.description}</span>
                  {v && (
                    <span className="ml-2 whitespace-nowrap font-mono text-[10.5px] text-muted-foreground">{v}</span>
                  )}
                  {z.note && (
                    <span className="mt-0.5 block max-w-[75ch] text-[11.5px] leading-relaxed text-muted-foreground">
                      {z.note}
                    </span>
                  )}
                  {z.product_name && (
                    <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">
                      {z.product_name}{z.cash === 0 ? " · unbar" : ""}
                    </span>
                  )}
                </TextZelle>
                <BetragZelle euro={z.amount} label={`Plan ${jahr}`} text={euro(z.amount)}
                  className="font-medium text-foreground dark:text-foreground" />
                <BetragZelle euro={z.amount_prior} label={`Vorjahr ${jahr - 1}`} text={euro(z.amount_prior)}
                  className="text-muted-foreground dark:text-muted-foreground" />
              </tr>
            );
          })}
        </ZahlenTabelle>
      )}

      <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Aus der Übersicht über die Zuweisungen und Zuschüsse an Dritte, Anlage 003 des
        Haushaltsplans — der Entwurf der Verwaltung, wie er in den Rat eingebracht wurde. „Vorjahr“
        ist der Ansatz im vorigen Plan, nicht das, was tatsächlich ausgezahlt wurde.
        {erste && ` Eingelesen sind die Pläne ${erste.budget_year}–${jahr}.`}
      </p>
    </section>
  );
}
