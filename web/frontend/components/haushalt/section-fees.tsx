"use client";

// „Was du dafür zahlst" — der VIERTE Abschnitt von /haushalt/konzern.
//
// Bis zum 21.08.2026 die eigene Seite /haushalt/gebuehren. Sie steht hinter
// den Wirtschaftsplänen, weil die Abfallgebühren aus genau einem davon
// kalkuliert werden — dem des Abfallwirtschaftsbetriebs.

// /haushalt/gebuehren — was Sie dafür zahlen.
//
// Diese Seite steht direkt hinter „Was planen die Betriebe?": Dort erfährt
// man, was der Abfallwirtschaftsbetrieb sich vornimmt — hier, was daraus für
// die Leute wird. Von allen Zahlen des Haushalts landet keine so direkt im
// Portemonnaie.
//
// DREI ENTSCHEIDUNGEN, die diese Seite trägt:
//
//  1. **Die Rechnung wird gezeigt, nicht nur ihr Ergebnis.** Eine Gebühr von
//     151,21 € je Tonne sagt für sich nichts. Erst die Kaskade darüber — was
//     der Bereich kostet, was Dritte tragen, was aus Vorjahren ausgeglichen
//     wird — macht sie nachvollziehbar. Deshalb steht sie ausgeschrieben da
//     und nicht als Fußnote.
//  2. **Keine Bewertungsfarben.** Eine steigende Gebühr ist nicht „schlecht" —
//     sie kann eine gestiegene Entsorgungspauschale sein oder eine
//     Unterdeckung aus dem Vorjahr. Die Seite zeigt den Verlauf und seine
//     Bestandteile, nicht ihr Urteil (dieselbe Regel wie im ganzen Bereich).
//  3. **Die Abfallsammlung bekommt keine erfundene Durchschnittsgebühr.** Sie
//     erhebt eine Grundgebühr UND eine Gebühr je Liter Behältervolumen. Statt
//     einer einzelnen Division zeigt ihre Karte deshalb die ausdrücklich
//     benannten Tarife aus Anlage 4.

import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  GebuehrenZeile, GebuehrensatzZeile, HaushaltAuswahl, deMio, haushaltUrl, herkunftVon,
} from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import type { Herkunft } from "@/lib/herkunft";
import { deZahl } from "@/components/grafik/format";
import {
  Beleg, Dokumentbeleg,
} from "@/components/haushalt/source";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import type { JahrPunkt } from "@/components/grafik/daten";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";

// `provenance` mit: Jeder Bereich hat seine eigene Fundstelle in derselben
// Datei („Gebührenbedarfsberechnung 2026, Straßenreinigung"), und die ist
// der Unterschied zwischen einem 40-Seiten-PDF und einer Stelle darin.
/** Was dieser Abschnitt braucht. Die SEITE holt es zusammen mit den
 *  Wirtschaftsplänen in EINEM Aufruf — beide Abschnitte brauchen `provenance`,
 *  und `useFetch` hat keinen Zwischenspeicher. */
export type GebuehrenDaten = HaushaltAuswahl<
  "fees" | "fee_rates" | "provenance"
>;

/** Was der Bereich macht — eine Zeile, damit die Zahl einen Gegenstand hat. */
const WAS_ES_IST: Record<string, string> = {
  waste_treatment:
    "Was mit Rest- und Bioabfall passiert, nachdem er abgeholt wurde: "
    + "Behandlung, Verwertung, Deponienachsorge.",
  waste_collection:
    "Das Abholen selbst — Tonnen, Sperrmüll, Grüngut, Wertstoffberatung.",
  street_cleaning:
    "Kehren, Winterdienst und Reinigung der öffentlichen Straßen.",
};

/** Wonach die Gebühr bemessen wird, in einem Satz für Leser*innen. */
const MASSSTAB: Record<string, string> = {
  Mg: "je Tonne angelieferten Abfalls",
  "Meter Quadratwurzel":
    "je Meter Quadratwurzel — ein Flächenmaß der Straßenreinigungssatzung, "
    + "das große und kleine Grundstücke ins Verhältnis setzt",
  Liter: "je Liter Behältervolumen",
};

function Euro({ value, stellen = 0 }: { value: number; stellen?: number }) {
  return <>{deZahl(value, stellen)}&nbsp;€</>;
}

/** Eine Kaskadenzeile: Bezeichnung links, Betrag rechts. */
function Zeile({ label, value, summe = false }: {
  label: string; value: number; summe?: boolean;
}) {
  return (
    <div className={
      "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 "
      + (summe ? "border-t border-border pt-1.5 mt-1.5 font-semibold" : "")
    }>
      <span className={summe ? "text-[13px]" : "text-[12.5px] text-muted-foreground"}>
        {label}
      </span>
      <span className="tabular-nums text-[13px]">
        <Euro value={value} />
      </span>
    </div>
  );
}

function Tarifliste({ tarife }: { tarife: GebuehrensatzZeile[] }) {
  if (!tarife.length) return null;
  const year = tarife[0].year;
  return (
    <div className="mt-3 rounded-xl border border-border bg-muted/25 px-3 py-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[12.5px] font-semibold">Konkrete Tarifvorschläge {year}</p>
        <span className="font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
          Anlage 4
        </span>
      </div>
      <dl className="mt-2 grid gap-x-5 gap-y-1.5 sm:grid-cols-2">
        {tarife.map((t) => (
          <div key={t.key}
            className="flex items-baseline justify-between gap-3 border-t border-border/70 pt-1.5">
            <dt className="min-w-0 text-[11.5px] leading-snug text-muted-foreground">
              {t.label}
            </dt>
            <dd className="max-w-[48%] flex-none text-right tabular-nums">
              <span className="block text-[12px] font-semibold">
                <Euro value={t.amount} stellen={2} />
              </span>
              <span className="block text-[10.5px] leading-snug text-muted-foreground">
                {t.unit}
                {t.change_pct != null && t.change_pct !== 0 && (
                  <> · {t.change_pct > 0 ? "+" : ""}
                    {deZahl(t.change_pct, 2)}&#8239;%</>
                )}
              </span>
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
        Das sind die ausdrücklich benannten Vorschläge der Verwaltung, keine
        aus den Gesamtkosten errechnete Durchschnittsgebühr.<Beleg q="fees" />
      </p>
    </div>
  );
}

function BereichsKarte({ zeilen, tarife, herkunftFuer }: {
  zeilen: GebuehrenZeile[];
  tarife: GebuehrensatzZeile[];
  /** Die Suche, nicht das Ergebnis — welche Zeile die jüngste ist,
   *  entscheidet diese Karte selbst. */
  herkunftFuer: (id: number | null) => Herkunft | null;
}) {
  const nach = [...zeilen].sort((a, b) => a.year - b.year);
  const letzte = nach[nach.length - 1];
  // Fehlende Jahre stehen als Lücke MIT Grund in der Reihe: 2022 hat die
  // Stadt keine Bedarfsberechnung ins Ratsinformationssystem gestellt — bis
  // 02.09.2026 hieß das in der Grafik „ohne Wert und ohne Grund".
  const mitGebuehr = nach.filter((z) => z.fee != null);
  const series: JahrPunkt[] = [];
  if (mitGebuehr.length) {
    const vorhanden = new Map(mitGebuehr.map((z) => [z.year, z.fee as number]));
    for (let j = mitGebuehr[0].year; j <= mitGebuehr[mitGebuehr.length - 1].year; j++) {
      const fee = vorhanden.get(j);
      series.push(fee != null
        ? { year: j, value: fee }
        : { year: j, fehlt: "keine Gebührenbedarfsberechnung im Ratsinformationssystem" });
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-[16px] font-bold leading-tight">
          {letzte.area_name}
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          Berechnung {letzte.year}
        </span>
      </div>
      {WAS_ES_IST[letzte.area] && (
        <p className="mt-1 max-w-[62ch] text-[12.5px] leading-relaxed text-foreground/80">
          {WAS_ES_IST[letzte.area]}
        </p>
      )}

      {/* Die Rechnung ausgeschrieben. Sie ist der Grund, dass die Zahl unten
          nachvollziehbar ist — als Fußnote wäre sie wertlos. */}
      <div className="mt-3">
        <Zeile label={`Was der Bereich ${letzte.year} kostet`}
          value={letzte.cost_calculation} />
        <Zeile label="davon getragen von Dritten, Erlösen und Vorjahren"
          value={letzte.deductions} />
        <Zeile label="Von den Gebühren zu decken"
          value={letzte.costs_to_cover} summe />
      </div>

      {letzte.fee != null && letzte.reference_quantity != null ? (
        <div className="mt-3 rounded-xl bg-muted/40 px-3 py-2.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4">
            <span className="text-[12.5px] text-muted-foreground">
              geteilt durch {deZahl(letzte.reference_quantity, 0)}{" "}
              {letzte.reference_unit}
            </span>
            <span className="font-display text-[17px] font-bold tabular-nums">
              <Euro value={letzte.fee} stellen={3} />
            </span>
          </div>
          <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
            {MASSSTAB[letzte.reference_unit ?? ""] ?? "je Bezugseinheit"}
            {letzte.fee_proposed != null && (
              <> · dem Rat vorgeschlagen:{" "}
                <strong className="text-foreground">
                  <Euro value={letzte.fee_proposed} stellen={2} />
                </strong>
              </>
            )}
          </p>
        </div>
      ) : tarife.length === 0 ? (
        // KEINE ERFUNDENE ZAHL. Die Abfallsammlung erhebt eine Grundgebühr und
        // eine Gebühr je Liter — eine einzelne Division gibt es dort nicht.
        <p className="mt-3 rounded-xl border border-border px-3 py-2.5
                      text-[12.5px] leading-relaxed text-muted-foreground">
          Hier steht <strong>keine einzelne Gebühr</strong>: Die Abfallsammlung
          wird über eine Grundgebühr je Haushalt <em>und</em> eine Gebühr je
          Liter Behältervolumen abgerechnet. Eine Zahl „je Einheit" ließe sich
          daraus nur erfinden.
        </p>
      ) : null}

      {/* Bei Behandlung und Straßenreinigung steht der konkrete Vorschlag
          bereits direkt an der Division. Nur die mehrteilige Abfallsammlung
          braucht die vollständige Tarifliste statt einer Einzelzahl. */}
      <Tarifliste tarife={letzte.fee == null ? tarife : []} />

      <div className="mt-2.5">
        <p className="text-[12px] leading-relaxed text-muted-foreground">
          <Beleg q="fees" />{" "}
          Nachgerechnet: Die Kalkulationskosten minus alle Abzüge ergeben die zu
          deckenden Kosten
          {letzte.fee != null && <>, und diese geteilt durch die Menge die
            Gebühr</>}.
        </p>
        <Dokumentbeleg h={herkunftFuer(letzte.herkunft_id)}
          vorlageNr={letzte.template_number} />
      </div>

      {series.length >= 3 && (
        <div className="mt-3">
          <Zeitreihe
            series={series}
            unit="€"
            nachkomma={2}
            title="Gebühr im Zeitverlauf"
            // Ohne Jahresspanne: Die Zeitreihe hängt sie selbst an, und
            // zweimal gelesen klingt es wie ein Fehler.
            ariaTitel={`Gebühr ${letzte.area_name}, in Euro `
              + `${MASSSTAB[letzte.reference_unit ?? ""] ?? ""}`}
          />
        </div>
      )}
    </section>
  );
}

export function GebuehrenAbschnitt({ data, loading }: {
  data: GebuehrenDaten | null; loading: boolean;
}) {
  const nachBereich = useMemo(() => {
    const zeilen = data?.fees ?? [];
    const gruppen = new Map<string, GebuehrenZeile[]>();
    for (const z of zeilen) {
      const liste = gruppen.get(z.area) ?? [];
      liste.push(z);
      gruppen.set(z.area, liste);
    }
    // Feste Reihenfolge: erst das Abholen, dann die Behandlung, dann die
    // Straße — so, wie der Abfall den Weg nimmt.
    const ordnung = ["waste_collection", "waste_treatment", "street_cleaning"];
    return [...gruppen.entries()]
      .sort((a, b) => ordnung.indexOf(a[0]) - ordnung.indexOf(b[0]))
      .map(([, v]) => v);
  }, [data]);

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Gebührenberechnungen werden geladen …
    </div>;
  }
  if (!nachBereich.length) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite sind die Gebührenbedarfsberechnungen noch nicht
        eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">
          Zurück zum Haushalt
        </Link>
      </div>
    );
  }

  const years = nachBereich.flat().map((z) => z.year);
  const juengstes = Math.max(...years);
  const aeltestes = Math.min(...years);
  const tarifJahr = Math.max(0, ...(data?.fee_rates ?? []).map((z) => z.year));

  return (
      <div className="flex flex-col gap-4">
        <header>
          <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
            Was du dafür zahlst
          </h2>
          <p className="mt-2 max-w-[68ch] text-[13.5px] leading-relaxed text-foreground/85">
            Abfall- und Straßenreinigungsgebühren werden jährlich anhand der erwarteten
            Kosten kalkuliert und dem Rat zur Entscheidung vorgelegt. Hier zeigen wir
            diese Gebührenbedarfsberechnungen für die Jahre{" "}
            {aeltestes} bis {juengstes}.
          </p>
        </header>

        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Warum das eine eigene Rechnung ist
          </p>
          <p className="mt-2 max-w-[68ch] text-[13px] leading-relaxed text-foreground/85">
            Gebühren sollen die Kosten der jeweiligen Leistung decken, dürfen aber keine
            dauerhaften Überschüsse für den allgemeinen Haushalt erzeugen. Deshalb fließen
            Über- oder Unterdeckungen früherer Jahre in spätere Kalkulationen ein. Der Rat
            entscheidet über die Satzung und die zugrunde gelegten Kosten; der rechnerische
            Gebührensatz ergibt sich anschließend aus Kosten und erwarteter Nutzungsmenge.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {nachBereich.map((zeilen) => (
            <BereichsKarte key={zeilen[0].area} zeilen={zeilen}
              tarife={(data?.fee_rates ?? [])
                .filter((z) => z.year === tarifJahr && z.area === zeilen[0].area)}
              herkunftFuer={(id) => herkunftVon(data, id)} />
          ))}
        </div>

        <LottiErklaert
          title="Warum steigt meine Müllgebühr?"
          text={"Gebühren ändern sich vor allem, wenn die erwarteten Kosten oder Mengen "
            + "steigen oder sinken. Auch Über- und Unterdeckungen aus Vorjahren werden "
            + "in späteren Kalkulationen ausgeglichen."}
        />

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

      </div>
  );
}
