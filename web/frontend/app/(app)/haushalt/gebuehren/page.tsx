"use client";

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
//  3. **Die Abfallsammlung bekommt keine erfundene Gebühr.** Sie erhebt eine
//     Grundgebühr UND eine Gebühr je Liter Behältervolumen; eine einzelne
//     Division gibt es dort nicht. Ihre Karte zeigt die Kaskade und sagt
//     ausdrücklich, warum darunter keine Zahl steht.

import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  GebuehrenZeile, HaushaltAuswahl, deMio, haushaltUrl, herkunftVon,
} from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import type { Herkunft } from "@/lib/herkunft";
import { deZahl } from "@/components/grafik/format";
import {
  Beleg, Dokumentbeleg, Quellenkontext, Quellenverzeichnis,
} from "@/components/haushalt/quelle";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import type { JahrPunkt } from "@/components/grafik/daten";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

// `herkunft` mit: Jeder Bereich hat seine eigene Fundstelle in derselben
// Datei („Gebührenbedarfsberechnung 2026, Straßenreinigung"), und die ist
// der Unterschied zwischen einem 40-Seiten-PDF und einer Stelle darin.
const FELDER = ["gebuehren", "herkunft"] as const;
const QUELLEN: QuellenSchluessel[] = ["gebuehren"];

/** Was der Bereich macht — eine Zeile, damit die Zahl einen Gegenstand hat. */
const WAS_ES_IST: Record<string, string> = {
  abfallbehandlung:
    "Was mit Rest- und Bioabfall passiert, nachdem er abgeholt wurde: "
    + "Behandlung, Verwertung, Deponienachsorge.",
  abfallsammlung:
    "Das Abholen selbst — Tonnen, Sperrmüll, Grüngut, Wertstoffberatung.",
  strassenreinigung:
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

function Euro({ wert, stellen = 0 }: { wert: number; stellen?: number }) {
  return <>{deZahl(wert, stellen)}&nbsp;€</>;
}

/** Eine Kaskadenzeile: Bezeichnung links, Betrag rechts. */
function Zeile({ label, wert, summe = false }: {
  label: string; wert: number; summe?: boolean;
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
        <Euro wert={wert} />
      </span>
    </div>
  );
}

function BereichsKarte({ zeilen, juengstesJahr, herkunftFuer }: {
  zeilen: GebuehrenZeile[]; juengstesJahr: number;
  /** Die Suche, nicht das Ergebnis — welche Zeile die jüngste ist,
   *  entscheidet diese Karte selbst. */
  herkunftFuer: (id: number | null) => Herkunft | null;
}) {
  const nach = [...zeilen].sort((a, b) => a.jahr - b.jahr);
  const letzte = nach[nach.length - 1];
  const reihe: JahrPunkt[] = nach
    .filter((z) => z.gebuehr != null)
    .map((z) => ({ jahr: z.jahr, wert: z.gebuehr as number }));

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-[16px] font-bold leading-tight">
          {letzte.bereich_name}
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          Berechnung {letzte.jahr}
        </span>
      </div>
      {WAS_ES_IST[letzte.bereich] && (
        <p className="mt-1 max-w-[62ch] text-[12.5px] leading-relaxed text-foreground/80">
          {WAS_ES_IST[letzte.bereich]}
        </p>
      )}

      {/* Die Rechnung ausgeschrieben. Sie ist der Grund, dass die Zahl unten
          nachvollziehbar ist — als Fußnote wäre sie wertlos. */}
      <div className="mt-3">
        <Zeile label={`Was der Bereich ${letzte.jahr} kostet`}
          wert={letzte.kostenkalkulation} />
        <Zeile label="davon getragen von Dritten, Erlösen und Vorjahren"
          wert={letzte.abzuege} />
        <Zeile label="Von den Gebühren zu decken"
          wert={letzte.zu_deckende_kosten} summe />
      </div>

      {letzte.gebuehr != null && letzte.bezugsmenge != null ? (
        <div className="mt-3 rounded-xl bg-muted/40 px-3 py-2.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4">
            <span className="text-[12.5px] text-muted-foreground">
              geteilt durch {deZahl(letzte.bezugsmenge, 0)}{" "}
              {letzte.bezugseinheit}
            </span>
            <span className="font-display text-[17px] font-bold tabular-nums">
              <Euro wert={letzte.gebuehr} stellen={3} />
            </span>
          </div>
          <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
            {MASSSTAB[letzte.bezugseinheit ?? ""] ?? "je Bezugseinheit"}
            {letzte.gebuehrenvorschlag != null && (
              <> · dem Rat vorgeschlagen:{" "}
                <strong className="text-foreground">
                  <Euro wert={letzte.gebuehrenvorschlag} stellen={2} />
                </strong>
              </>
            )}
          </p>
        </div>
      ) : (
        // KEINE ERFUNDENE ZAHL. Die Abfallsammlung erhebt eine Grundgebühr und
        // eine Gebühr je Liter — eine einzelne Division gibt es dort nicht.
        <p className="mt-3 rounded-xl border border-border px-3 py-2.5
                      text-[12.5px] leading-relaxed text-muted-foreground">
          Hier steht <strong>keine einzelne Gebühr</strong>: Die Abfallsammlung
          wird über eine Grundgebühr je Haushalt <em>und</em> eine Gebühr je
          Liter Behältervolumen abgerechnet. Eine Zahl „je Einheit" ließe sich
          daraus nur erfinden.
        </p>
      )}

      <div className="mt-2.5">
        <p className="text-[12px] leading-relaxed text-muted-foreground">
          <Beleg q="gebuehren" />{" "}
          Nachgerechnet: Die Kalkulationskosten minus alle Abzüge ergeben die zu
          deckenden Kosten
          {letzte.gebuehr != null && <>, und diese geteilt durch die Menge die
            Gebühr</>}.
        </p>
        <Dokumentbeleg h={herkunftFuer(letzte.herkunft_id)}
          vorlageNr={letzte.vorlage_nr} />
      </div>

      {reihe.length >= 3 && (
        <div className="mt-3">
          <Zeitreihe
            reihe={reihe}
            einheit="€"
            nachkomma={2}
            titel="Gebühr im Zeitverlauf"
            // Ohne Jahresspanne: Die Zeitreihe hängt sie selbst an, und
            // zweimal gelesen klingt es wie ein Fehler.
            ariaTitel={`Gebühr ${letzte.bereich_name}, in Euro `
              + `${MASSSTAB[letzte.bezugseinheit ?? ""] ?? ""}`}
          />
        </div>
      )}
    </section>
  );
}

export default function GebuehrenPage() {
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(
    haushaltUrl(FELDER));

  const nachBereich = useMemo(() => {
    const zeilen = data?.gebuehren ?? [];
    const gruppen = new Map<string, GebuehrenZeile[]>();
    for (const z of zeilen) {
      const liste = gruppen.get(z.bereich) ?? [];
      liste.push(z);
      gruppen.set(z.bereich, liste);
    }
    // Feste Reihenfolge: erst das Abholen, dann die Behandlung, dann die
    // Straße — so, wie der Abfall den Weg nimmt.
    const ordnung = ["abfallsammlung", "abfallbehandlung", "strassenreinigung"];
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

  const jahre = nachBereich.flat().map((z) => z.jahr);
  const juengstes = Math.max(...jahre);
  const aeltestes = Math.min(...jahre);

  return (
    <Quellenkontext schluessel={QUELLEN} jahr={juengstes}>
      <div className="flex flex-col gap-4">
        <header>
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
            Stadtfinanzen Oldenburg · Schritt 14
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">
            Was Sie dafür zahlen
          </h1>
          <p className="mt-2 max-w-[68ch] text-[13.5px] leading-relaxed text-foreground/85">
            Abfall- und Straßenreinigungsgebühren stehen nicht im Haushaltsplan
            wie andere Einnahmen — sie werden jedes Jahr eigens ausgerechnet und
            dem Rat vorgelegt. Diese Rechnung steht hier, für die Jahre{" "}
            {aeltestes} bis {juengstes}.
          </p>
        </header>

        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Warum das eine eigene Rechnung ist
          </p>
          <p className="mt-2 max-w-[68ch] text-[13px] leading-relaxed text-foreground/85">
            Gebühren dürfen nur decken, was die Leistung wirklich kostet — nicht
            mehr und auf Dauer auch nicht weniger. Deshalb wird jedes Jahr
            nachgerechnet und ein Über- oder Unterschuss des Vorjahres
            eingerechnet. Was dabei herauskommt, ist keine politische Zahl,
            sondern das Ergebnis einer Division; entschieden wird über die
            Kosten, die oben hineingehen.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {nachBereich.map((zeilen) => (
            <BereichsKarte key={zeilen[0].bereich} zeilen={zeilen}
              juengstesJahr={juengstes}
              herkunftFuer={(id) => herkunftVon(data, id)} />
          ))}
        </div>

        <LottiErklaert
          titel="Warum steigt meine Müllgebühr?"
          text={"Selten, weil die Stadt mehr verdienen will — sie darf daran "
            + "gar nichts verdienen. Meistens sind es gestiegene Kosten für "
            + "die Entsorgung, oder das Vorjahr hat ein Minus hinterlassen, "
            + "das jetzt ausgeglichen wird."}
        />

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

        <SchrittWeiter href="/haushalt/gebuehren" />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}
