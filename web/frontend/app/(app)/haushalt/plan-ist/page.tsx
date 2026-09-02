"use client";

// /haushalt/plan-ist — „Geplant und geworden" (Design H-16/H-17).
//
// Der Haushalt ist ein Plan; was daraus wurde, steht im Jahresabschluss.
// Beides nebeneinander zu zeigen ist die interessantere Hälfte des Bereichs:
// Oldenburg nimmt seit Jahren deutlich mehr ein als geplant — wer das weiß,
// liest das geplante Defizit anders.
//
// Reihenfolge: Kernaussage → Hantel je Bereich → woran es lag (Ertragsarten)
// → Zahlen. Bewertungsfarben gibt es nirgends (siehe components/hantel.tsx).
//
// EIN ABSCHNITT IST KEIN EINORDNUNGSSATZ (Befund und Umbau 17.08.). Die
// Erläuterungen des Abschlusses sind im Median 491 Zeichen lang — acht von 45
// aber über 2.000, und die zu den „außerordentlichen Aufwendungen" in jedem
// Jahrgang zwischen 5.371 und 7.176. Dort hat die Verwaltung einen ganzen
// Abschnitt unter eine Zeile gesetzt (Einzelbeträge zu Kreyenbrück Nord,
// Käthe-Kollwitz-Straße, Fliegerhorst …). Weil dieser Text die Teilhaushalte
// beim Namen nennt, landete er über `gruendeFuerBereich` als
// Einordnungssatz IN der Hantel: gemessen 7.241 Zeichen und 1.645 px am
// Stück, mitten zwischen zwei Chart-Zeilen, in fünf von acht Jahrgängen.
//
// Gekürzt wird er trotzdem nicht — er wandert. Ab 700 Zeichen trägt die
// Hantel-Zeile nur noch den Hinweis, dass der Abschluss diesen Bereich
// ausführlich erläutert; der Wortlaut steht vollständig unten unter „Warum es
// anders kam", eingeklappt in derselben <Warum>-Grammatik wie jede andere
// Erläuterung dieser Seite. Damit bleibt die Regel von
// components/grafik/einordnung.tsx unangetastet: Was IN der Hantel steht,
// steht dort ganz.
//
// EINE ERLÄUTERUNG STEHT NUR EINMAL IM BILD (seit 17.08.). Der Jahresabschluss
// erläutert die Posten der GESAMTrechnung; welchen Bereich ein Absatz meint,
// steht im Absatz selbst („Im Teilhaushalt 10 …"). Manche nennen mehrere:
// 2024 spricht die Erläuterung zu den sonstigen Transfererträgen von
// Teilhaushalt 10 UND 11, die zu den sonstigen ordentlichen Erträgen von 2, 4
// und 5. `gruendeFuerBereich` ordnet sie deshalb — richtigerweise — jedem
// genannten Bereich zu, und die Hantel druckte denselben 505-Zeichen-Absatz
// zweimal untereinander. Das las sich wie ein Fehler. Jetzt trägt der Bereich
// mit der größten Abweichung den Wortlaut, die weiteren einen Verweis darauf.
// Gekürzt wird nichts: Der Einordnungssatz gehört zur Hantel und wird nie
// abgeschnitten (H4-07, components/grafik/einordnung.tsx).

import { Suspense, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  ErgebnisPosten, HaushaltAuswahl, haushaltUrl, PLAN_ART_LABEL, PlanArt,
  deMio, grundZuPosten, gruendeFuerBereich, kassensicht, mio, pruefberichtZuJahr,
} from "@/lib/haushalt";
import { PruefberichtDaten, wiederholungsketten } from "@/lib/haushalt-pruefung";
import { Warum } from "@/components/haushalt/warum";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/source";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { MarkePille } from "@/components/haushalt/mark";
import { Hantel, HantelMassstab } from "@/components/grafik/hantel";
import {
  NachbewilligungsBefund, NachbewilligungsBlock,
} from "@/components/haushalt/supplementary-approvals";
import { cn } from "@/lib/utils";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { Vollzug } from "@/components/haushalt/vollzug";
import { berichteUrls, type VollzugDaten } from "@/lib/haushalt-vollzug";

/** Hinweis auf die Prüfung — hier und nirgends sonst, weil das
 *  Rechnungsprüfungsamt genau diesen Vergleich seit Jahren beanstandet:
 *  „Dies widerspricht dem Grundsatz der Haushaltswahrheit."
 *
 *  Die Karte behauptet das nicht selbst, sondern zeigt den Wortlaut des
 *  jüngsten Befundes zu diesem Abschnitt — und verlinkt den Rest. Ohne Daten
 *  (Feature noch nicht eingelesen) erscheint sie gar nicht. */
function PruefungsHinweis() {
  // Nur die wiederholten Beanstandungen: Der volle Bestand ist rund 250 kB
  // Prosa und wird auf dieser Seite nirgends angezeigt.
  const { data } = useFetch<PruefberichtDaten>("/council/budget/audit-reports?mark=WB");
  const chain = useMemo(() => {
    if (!data?.findings?.length) return null;
    return wiederholungsketten(data.findings)
      .find((k) => k.key.includes("planistvergleich")) ?? null;
  }, [data]);
  if (!chain) return null;
  // Ausdrücklich die jüngste WIEDERHOLTE Beanstandung, nicht einfach den
  // letzten Eintrag: Der Abschnitt trägt in denselben Jahren auch Hinweise.
  const juengste = [...chain.eintraege].reverse().find((f) => f.mark === "WB");
  if (!juengste) return null;

  return (
    <Link href="/haushalt/pruefung"
      className="group flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <MarkePille mark={juengste.mark} name={juengste.mark_name} klein />
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          Rechnungsprüfungsamt · Schlussbericht {juengste.year} · Textziffer {juengste.text_number}
        </span>
      </div>
      <p className="border-l-2 border-border pl-3 text-[13.5px] leading-relaxed text-foreground/90">
        {juengste.text}
      </p>
      <span className="flex items-center gap-1 text-[12.5px] font-semibold text-primary">
        In {chain.years.length} von {data?.years.length} geprüften Jahren als wiederholte
        Beanstandung ausgewiesen — alle Feststellungen ansehen
        <ArrowRight size={14} strokeWidth={2} className="transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

/** Eine Zeile der Kassen-Rechnung: Beschriftung links, Betrag rechts.
 *
 *  **Keine Bewertungsfarbe.** Ein negativer Finanzmittelsaldo ist kein Rot
 *  wert: Die Stadt investiert, und Investitionen zahlt man aus Beständen. Das
 *  Vorzeichen steht als Zeichen da, nicht als Urteil — deshalb tragen alle
 *  Beträge dieselbe Textfarbe, und `stark` hebt nur die Summenzeile heraus,
 *  wie im Dokument. */
function KassenZeile({ label, note, value, stark }: {
  label: string; note?: string; value: number | null; stark?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="min-w-0">
        <span className={cn("text-[13.5px] leading-snug",
          stark ? "font-semibold text-foreground" : "text-foreground/90")}>
          {label}
        </span>
        {note && (
          <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">
            {note}
          </span>
        )}
      </dt>
      <dd className={cn("flex-none tabular-nums",
        stark ? "font-display text-[19px] font-bold" : "text-[15px] font-semibold")}>
        {value != null && value > 0 && "+"}{deMio(value)}
        <span className="ml-0.5 text-[11px] font-semibold text-muted-foreground">
          Mio.&nbsp;€
        </span>
      </dd>
    </div>
  );
}

/** Ab hier ist eine „Erläuterung" kein Einordnungssatz mehr, sondern ein
 *  Abschnitt — gemessen am Bestand: Median 491 Zeichen, die acht Ausreißer
 *  über 2.000. Der Schnitt liegt bewusst dazwischen und nicht am Ausreißer,
 *  damit ein künftiger 1.500-Zeichen-Block dieselbe Behandlung bekommt. */
const EINORDNUNG_GRENZE = 700;

type Bereich = {
  nr: number; name: string;
  aufwPlan: number | null; aufwIst: number | null;
  ertrPlan: number | null; ertrIst: number | null;
};


function PlanIstInner() {
  const gewaehltesJahr = Number(useSearchParams().get("year")) || null;
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER));
  const [zahlenOffen, setZahlenOffen] = useState(false);
  // Der Haushaltsvollzug hat seinen eigenen Jahrgang: Er läuft dem Abschluss
  // um zwei Jahre voraus. Ohne Wahl zeigt er den jüngsten; die Teilhaushalte
  // kommen nur für den gewählten Jahrgang mit (Endpunkt-Doku).
  const [vollzugWahl, setVollzugWahl] = useState<number | null>(null);
  const vollzugKopf = useFetch<VollzugDaten>("/council/budget/execution");
  const vollzugJahr = vollzugWahl ?? vollzugKopf.data?.editions.at(-1) ?? null;
  const vollzug = useFetch<VollzugDaten>(
    vollzugJahr ? `/council/budget/execution?budget_year=${vollzugJahr}` : null);
  const vollzugDaten = vollzug.data ?? vollzugKopf.data ?? null;
  // Die Berichte des Vollzug-Jahrgangs bekommen im Verzeichnis eigene
  // Nummern: Die Seite zeigt den Abschluss 2024 UND den Vollzug 2026 — über
  // den Jahrgang der Seite fände das Verzeichnis für den Vollzug die
  // falschen Papiere (die von 2024).
  const jeDokument = useMemo(() => {
    const urls = vollzugDaten && vollzugJahr ? berichteUrls(vollzugDaten, vollzugJahr) : [];
    return urls.length ? { budget_execution: urls } : {};
  }, [vollzugDaten, vollzugJahr]);
  const [massstab, setMassstab] = useState<HantelMassstab>("percent");

  const years = data?.plan_actual_years ?? [];
  const year = gewaehltesJahr && years.includes(gewaehltesJahr) ? gewaehltesJahr : years.at(-1) ?? null;

  const { gesamt, bereiche, arten, planArt, ansatzAbweichend } = useMemo(() => {
    const leer = {
      gesamt: null as null | Record<string, number | null>, bereiche: [] as Bereich[],
      arten: [] as ErgebnisPosten[], planArt: "budget" as PlanArt,
      ansatzAbweichend: null as null | { ertr: number | null; aufw: number | null },
    };
    if (!data || !year) return leer;
    const zeilen = (data.income_statement ?? []).filter((p) => p.year === year);
    const summe = (rows: ErgebnisPosten[], nr: number) => rows.find((p) => p.nr === nr);
    const g = zeilen.filter((p) => p.sub_budget_no == null);
    const e = summe(g, 12), a = summe(g, 20);

    const nrs = [...new Set(zeilen.filter((p) => p.sub_budget_no != null).map((p) => p.sub_budget_no))];
    const bereiche = nrs.map((nr) => {
      const part = zeilen.filter((p) => p.sub_budget_no === nr);
      const te = summe(part, 12), ta = summe(part, 20);
      return {
        nr, name: part[0]?.sub_budget_name ?? `Teilhaushalt ${nr}`,
        aufwPlan: mio(ta?.plan), aufwIst: mio(ta?.result),
        ertrPlan: mio(te?.plan), ertrIst: mio(te?.result),
      };
    });
    type Aufw = { aufwPlan: number | null; aufwIst: number | null };
    const abw = (b: Aufw) => (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
    bereiche.sort((x, y) => massstab === "percent"
      ? Math.abs(abw(y)) / Math.abs(y.aufwPlan || 1) - Math.abs(abw(x)) / Math.abs(x.aufwPlan || 1)
      : Math.abs(abw(y)) - Math.abs(abw(x)));

    // Woran es lag: die Ertragsarten (Posten 1–11) mit der größten Abweichung.
    const arten = g
      .filter((p) => p.nr >= 1 && p.nr <= 11 && p.deviation != null)
      .sort((x, y) => Math.abs(y.deviation ?? 0) - Math.abs(x.deviation ?? 0))
      .slice(0, 5);

    // Weicht der fortgeschriebene Plan vom ursprünglichen Ansatz ab, gehört
    // beides auf die Seite — 2020 sind das bei den Ausgaben 27 Mio. €.
    const weicht = (p?: ErgebnisPosten) =>
      p?.plan != null && p?.budgeted != null && Math.abs(p.plan - p.budgeted) > 1;

    return {
      gesamt: {
        ertrPlan: mio(e?.plan), ertrIst: mio(e?.result),
        aufwPlan: mio(a?.plan), aufwIst: mio(a?.result),
      },
      bereiche, arten,
      planArt: (a?.plan_kind ?? e?.plan_kind ?? "budget") as PlanArt,
      ansatzAbweichend: weicht(e) || weicht(a)
        ? { ertr: mio(e?.budgeted), aufw: mio(a?.budgeted) }
        : null,
    };
  }, [data, year, massstab]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!year || !gesamt) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt bisher ein ausgelesener Jahresabschluss vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  // Ohne Planwerte gibt es nichts zu vergleichen — und einen Vergleich gegen
  // eine fehlende Zahl schon gar nicht (siehe Kommentar an der Kernaussage).
  const planVorhanden = gesamt.ertrPlan != null && gesamt.aufwPlan != null;
  const ertrDiff = (gesamt.ertrIst ?? 0) - (gesamt.ertrPlan ?? 0);
  const aufwDiff = (gesamt.aufwIst ?? 0) - (gesamt.aufwPlan ?? 0);
  // DAS JAHRESERGEBNIS IST NICHT ERTRÄGE MINUS AUFWENDUNGEN.
  //
  // Erträge und Aufwendungen (Posten 12 und 20) sind die ORDENTLICHEN; ihre
  // Differenz ist das ordentliche Ergebnis (Posten 21). Das Jahresergebnis
  // ist 21 + 24, also samt außerordentlichem Ergebnis. Für 2024 sind das
  // +34,6 gegen +6,1 Mio. € — die 28,5 Mio. € dazwischen sind das
  // außerordentliche Ergebnis, und die Kachel hieß trotzdem „Tatsächliches
  // Jahresergebnis".
  //
  // `planGegenIst()` in lib/haushalt.ts rechnet seit jeher mit 21 + 24 und
  // begründet es im Docstring; diese Seite war die einzige Stelle, die der
  // Regel nicht folgte. Deshalb hier derselbe Weg statt einer zweiten Formel.
  const jahresergebnis = (art: "plan" | "result") => {
    const teile = [21, 24].map((nr) => (data.income_statement ?? []).find(
      (p) => p.year === year && p.nr === nr && p.sub_budget_no == null));
    if (teile.some((t) => !t || t[art] == null)) return null;
    return teile.reduce((s, t) => s + (t![art] as number), 0) / 1e6;
  };
  const saldoPlan = jahresergebnis("plan");
  const saldoIst = jahresergebnis("result");
  const kasse = kassensicht(data, year);
  // `ratsbeschluss` kommt dazu, sobald der Nachbewilligungs-Block etwas zu
  // zeigen hat: Seine Liste verlinkt Vorlagen aus dem Bürgerinformations-
  // system, und ein Beleg-Chip ohne angemeldete Quelle rendert nichts (siehe
  // `components/haushalt/source.tsx`) — die Zeilen stünden dann ohne Beleg da.
  const hatNachbewilligungen = (data.supplementary_approvals?.serie ?? []).length > 0;
  const quellen: QuellenSchluessel[] = [
    ...(vollzugDaten?.reporting_dates.length ? (["budget_execution"] as const) : []),
    "jahresabschluss",
    ...(kasse ? (["cash_flow_statement"] as const) : []),
    "plan",
    ...(hatNachbewilligungen ? (["ratsbeschluss"] as const) : []),
  ];
  const pruefbericht = pruefberichtZuJahr(data, year);
  // Die Zeilen der Hantel. Zwei Regeln, beide oben im Kopf begründet:
  // ein Wortlaut je Erläuterung, und nichts über EINORDNUNG_GRENZE im Bild.
  const wortlautBei = new Map<number, string>();
  const imBild = new Set<number>();
  const hantelZeilen = bereiche.map((b) => {
    const alle = b.nr == null ? [] : gruendeFuerBereich(data, year, b.nr);
    const g = alle.find((x) => x.text.length <= EINORDNUNG_GRENZE);
    let einordnung: ReactNode = null;
    if (g) {
      const schonBei = wortlautBei.get(g.nr);
      if (schonBei) {
        einordnung = (
          <>
            Denselben Absatz führt der Abschluss auch für <em>{schonBei}</em> — er nennt
            beide Bereiche in einem Satz. Der Wortlaut steht dort.
          </>
        );
      } else {
        wortlautBei.set(g.nr, b.name);
        imBild.add(g.nr);
        // Eingeklappt wie im Einnahmen-Block darüber: Fünf Zeilen Wortlaut
        // unter jeder Bereichszeile machten die Liste zum Dokument, und die
        // Seite trug zwei Muster für dieselbe Auskunft (Durchsicht 02.09.2026).
        einordnung = <Warum reason={g} kompakt />;
      }
    } else if (alle.length) {
      einordnung = (
        <>
          Diesen Bereich erläutert der Abschluss ausführlich — nicht mit einem Satz,
          sondern mit einem ganzen Abschnitt samt Einzelbeträgen. Er steht unten unter
          <em> Warum es anders kam</em>, im Wortlaut.
        </>
      );
    }
    return { label: b.name, plan: b.aufwPlan, ist: b.aufwIst, einordnung };
  });

  // Die Einnahmearten tragen ihre Erläuterung schon inline, die Hanteln ihre
  // Bereichs-Sätze auch; hier der Rest — nichts doppelt, aber auch nichts
  // verloren: Was für die Hantel zu lang war, steht genau deshalb hier.
  const obenGezeigt = new Set([...arten.map((p) => p.nr), ...imBild]);
  const uebrigeGruende = (data.variance_reasons ?? [])
    .filter((g) => g.year === year && !obenGezeigt.has(g.nr))
    .sort((a, b) => Math.abs(b.delta_meur ?? 0) - Math.abs(a.delta_meur ?? 0));

  return (
    <Quellenkontext keys={quellen} jeDokument={jeDokument} year={year}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Geplant und geworden</span>
      </div>

      <div className="flex items-start justify-between gap-5">
        <div className="min-w-0">
          <SchrittKicker href="/haushalt/plan-ist" />
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[25px]">
            Geplant und geworden
          </h1>
        </div>
        <SchrittPfad href="/haushalt/plan-ist" />
      </div>

      {/* Die Bühne (H5-02/H5-09): aus dem Satz „geplant … geworden …" werden
          zwei Zahlen — das Kopf-Paar übernimmt die Hantel-Semantik (○ Plan,
          ● geworden), die Abweichung bleibt unbewertet. Nur wenn der Jahrgang
          eine Planspalte hat: Gegen eine fehlende Zahl wird nicht verglichen
          (Regel an der Kernaussage unten). */}
      {planVorhanden && gesamt.aufwPlan != null && gesamt.aufwIst != null && (
        <Seitenbuehne
          kicker={`Jahresabschluss ${year} · Mio. € Aufwand`}
          zahl={
            <span className="flex flex-wrap items-baseline gap-x-3.5 gap-y-1">
              <span>geplant <ZaehlZahl value={gesamt.aufwPlan} nachkomma={1} /></span>
              <span aria-hidden="true" className="relative top-[-0.28em] h-0 w-9 flex-none border-t-2 border-foreground" />
              <span>geworden <ZaehlZahl value={gesamt.aufwIst} nachkomma={1} /></span>
            </span>
          }
          sub={<>
            {gesamt.aufwPlan > 0 && Math.abs(aufwDiff) >= 0.05 ? (
              <>{aufwDiff > 0 ? "+" : "−"}{(Math.abs(aufwDiff) / gesamt.aufwPlan * 100)
                .toLocaleString("de-DE", { maximumFractionDigits: 1 })}&#8239;%{" "}
                {aufwDiff > 0 ? "über" : "unter"} dem Plan — gemessen, nicht bewertet</>
            ) : (
              <>fast punktgenau — gemessen, nicht bewertet</>
            )}
          </>}
          minibild={bereiche.some((b) => b.aufwPlan != null && b.aufwIst != null) ? {
            href: "#hanteln",
            label: "Hantel: ○ Plan → ● geworden, je Bereich — klickt zu ihnen",
            skizze: (() => {
              // Schema, kein Maßstab (Tim, 26.08.: „viel zu nah aneinander"):
              // Eine Skala ab null drückte Plan- und Ist-Punkt bei ±5 %
              // Abweichung aufeinander. Der Punkt-Abstand ist deshalb
              // gespreizt — echt bleiben die RICHTUNG je Zeile und das
              // Verhältnis der Abweichungen zueinander. Die große Hantel
              // unten misst richtig; das hier ist ihre Vorschau.
              const zwei = bereiche
                .filter((b) => b.aufwPlan != null && b.aufwIst != null)
                .slice(0, 2);
              const maxAbw = Math.max(
                ...zwei.map((b) => Math.abs((b.aufwIst ?? 0) - (b.aufwPlan ?? 0))), 0.001);
              return zwei.map((b, i) => {
                const abw = (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
                const spann = 14 + (Math.abs(abw) / maxAbw) * 22;
                const planPos = abw >= 0 ? 30 + i * 10 : 58 + i * 10;
                const istPos = planPos + (abw >= 0 ? spann : -spann);
                return (
                  <span key={b.nr} className="relative block h-4">
                    <span className="absolute inset-x-0 top-[7px] h-[2px]" style={{ background: "var(--sb-blass)" }} />
                    <span className="absolute top-[7px] h-[2px]" style={{
                      left: `${Math.min(planPos, istPos)}%`,
                      width: `${Math.abs(istPos - planPos)}%`,
                      background: "var(--sb-voll)",
                    }} />
                    <span className="absolute top-[3px] h-2.5 w-2.5 rounded-full border-2 bg-card" style={{ left: `${planPos}%`, borderColor: "var(--sb-voll)" }} />
                    <span className="absolute top-[3px] h-2.5 w-2.5 rounded-full" style={{ left: `${istPos}%`, background: "var(--sb-voll)" }} />
                  </span>
                );
              });
            })(),
          } : undefined}
        />
      )}

      {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.). */}
      <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
        Der Haushalt legt fest, was die Stadt für ein Jahr erwartet und ausgeben darf.
        Der Jahresabschluss zeigt später, was tatsächlich verbucht wurde. Hier stehen Plan
        und Ergebnis nebeneinander.
      </p>

      {/* Erst die Erwartung, dann das Ergebnis: Der Haushaltsvollzug steht VOR
          den abgeschlossenen Jahren, weil er das Jahr zeigt, das gerade
          läuft — und das der Abschluss erst zwei Jahre später einholt. */}
      {vollzugDaten && vollzugJahr && vollzugDaten.reporting_dates.length > 0 && (
        <Vollzug daten={vollzugDaten} year={vollzugJahr} onYear={setVollzugWahl}
          beleg={(h) => <Beleg q="budget_execution" h={h} />} />
      )}

      <h2 className="mt-2 font-display text-[19px] font-bold tracking-tight">
        Was aus dem Plan wurde
      </h2>

      {/* Jahr-Umschalter: nur Jahre mit echtem Abschluss (scrollbar wie #497). */}
      {years.length > 1 && (
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Abgeschlossenes Haushaltsjahr
          </span>
          <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
            <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
              {years.map((j) => (
                <Link key={j} href={`/haushalt/plan-ist?year=${j}`} scroll={false}
                  className={cn("rounded-full px-3 py-1 text-[12.5px]",
                    j === year ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
                  {j}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Kernaussage — die Einnahmeseite ist die eigentliche Nachricht.
          FEHLT DER PLAN, WIRD NICHT VERGLICHEN. Wo der Jahrgang keine
          Planspalte hergibt, stand hier bis 16.08. ein Satz, der aus der
          fehlenden Zahl eine Null machte: „799,1 Mio. € eingenommen — geplant
          waren —, also 799,1 Mio. mehr". Das ist keine Lücke mehr, das ist
          eine falsche Aussage. Jetzt trägt die Seite den Ist-Wert und sagt
          dazu, dass die Bezugsgröße fehlt. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Das Haushaltsjahr {year} auf einen Blick
        </p>
        {planVorhanden ? (
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
            Die Stadt hat <strong>{deMio(gesamt.ertrIst)}&#8239;Mio.&nbsp;€ eingenommen</strong> —
            geplant waren {deMio(gesamt.ertrPlan)}<Beleg q="jahresabschluss" />
            {Math.abs(ertrDiff) >= 1 && (
              <>, also {deMio(Math.abs(ertrDiff))}&#8239;Mio.&nbsp;€ {ertrDiff > 0 ? "mehr" : "weniger"}</>
            )}. Ausgegeben hat sie <strong>{deMio(gesamt.aufwIst)}&#8239;Mio.&nbsp;€</strong> statt der
            geplanten {deMio(gesamt.aufwPlan)}
            {Math.abs(aufwDiff) >= 1 && (
              <> ({aufwDiff > 0 ? "+" : "−"}{deMio(Math.abs(aufwDiff))})</>
            )}.
          </p>
        ) : (
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
            Die Stadt hat {year} <strong>{deMio(gesamt.ertrIst)}&#8239;Mio.&nbsp;€ eingenommen</strong>{" "}
            und <strong>{deMio(gesamt.aufwIst)}&#8239;Mio.&nbsp;€</strong> ausgegeben
            <Beleg q="jahresabschluss" />. Die Planwerte der Gesamtrechnung konnten wir für
            diesen Jahrgang nicht auslesen — deshalb steht hier kein „geplant“ daneben und
            keine Abweichung. Wo der Abschluss einzelne Posten selbst mit ihrem Plan
            vergleicht, steht das weiter unten.
          </p>
        )}
        {/* Eigener Schalter, nicht `planVorhanden`: Die Kacheln hängen jetzt an
            den Posten 21 und 24, nicht mehr an den Summen 12 und 20. Ein
            Jahrgang kann die einen führen und die anderen nicht. */}
        {saldoPlan != null && saldoIst != null && (
          <div className="mt-3 grid gap-2.5 border-t border-border/60 pt-3 sm:grid-cols-2">
            <div>
              <p className="text-[11.5px] text-muted-foreground">Geplantes Jahresergebnis</p>
              <p className="font-display text-[20px] font-bold tabular-nums">
                {saldoPlan > 0 ? "+" : ""}{deMio(saldoPlan)}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
              </p>
            </div>
            <div>
              <p className="text-[11.5px] text-muted-foreground">Tatsächliches Jahresergebnis</p>
              <p className="font-display text-[20px] font-bold tabular-nums">
                {saldoIst > 0 ? "+" : ""}{deMio(saldoIst)}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
              </p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                Ordentliches und außerordentliches Ergebnis zusammen — nicht nur
                die Differenz der beiden Summen darüber.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* DIE KASSENSICHT — die andere Hälfte desselben Dokuments.
          Die Zahlen oben stammen aus der Ergebnisrechnung: Sie bucht. Ob
          dabei Geld geflossen ist, sagt sie nicht — Abschreibungen mindern
          das Ergebnis, ohne dass jemand etwas überweist, und eine
          Investition kostet sofort Geld, schlägt sich im Ergebnis aber nur
          als Abschreibung späterer Jahre nieder. Dreißig Seiten weiter im
          selben Bericht steht deshalb die Finanzrechnung, und für 2024 sagt
          sie: 22,4 Mio. € weniger in der Kasse. Wer nur die obere Zahl
          sieht, bekommt einen falschen Eindruck.

          KEINE DIFFERENZ ZWISCHEN BEIDEN. Jahresergebnis und
          Kassenveränderung werden hier nicht voneinander abgezogen — die
          Zahl stünde in keiner Quelle und hieße nichts. Gezeigt wird die
          Rechnung, die das Dokument selbst führt. */}
      {kasse && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Ergebnis und tatsächlicher Geldfluss
          </p>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
            Die Zahlen oben stammen aus der Ergebnisrechnung: Sie erfasst Erträge und
            Aufwendungen, auch wenn dabei nicht sofort Geld fließt. Die Finanzrechnung
            <Beleg q="cash_flow_statement" /> zeigt dagegen ausschließlich die tatsächlichen
            Ein- und Auszahlungen.
          </p>
          <dl className="mt-3 divide-y divide-border/60 border-t border-border/60">
            <KassenZeile
              label="Aus laufender Arbeit blieb übrig"
              note="Steuern, Gebühren und Zuweisungen minus Personal, Sachkosten und Sozialleistungen"
              value={mio(kasse.balance_operating?.result)} />
            <KassenZeile
              label="Für Investitionen floss ab"
              note={kasse.total_out_capital?.result != null
                ? `${deMio(mio(kasse.total_out_capital.result))} Mio. € ausgezahlt für Bau, Grundstücke, Geräte und Zuschüsse — abzüglich der Einzahlungen`
                : undefined}
              value={mio(kasse.balance_capital?.result)} />
            <KassenZeile
              label={kasse.cash_surplus?.label ?? "Finanzmittel-Überschuss/-Fehlbetrag"}
              value={mio(kasse.cash_surplus?.result)} stark />
            {kasse.cash_change && kasse.balance_financing && (
              <KassenZeile
                label="Nach Kredittilgung"
                note={`${deMio(mio(Math.abs(kasse.balance_financing.result ?? 0)))} Mio. € Tilgung`}
                value={mio(kasse.cash_change.result)} />
            )}
          </dl>
          {kasse.opening_balance?.result != null && kasse.closing_balance?.result != null && (
            <p className="mt-3 max-w-[70ch] text-[13px] leading-relaxed text-foreground/85">
              Am 1. Januar lagen <strong>{deMio(mio(kasse.opening_balance.result))}&#8239;Mio.&nbsp;€</strong>{" "}
              in der Kasse, am 31. Dezember{" "}
              <strong>{deMio(mio(kasse.closing_balance.result))}&#8239;Mio.&nbsp;€</strong>
              <Beleg q="cash_flow_statement" />.
            </p>
          )}
          {/* Die Ermächtigungen sind die Antwort auf die Frage, die sich beim
              Blick auf die Investitionszeile jede*r stellt: Warum wird das
              Geplante nicht gebaut? Weil ein Teil des Geldes aus Vorjahren
              stammt und die Genehmigung mitwandert — der Plan des Jahres ist
              nicht die Grenze dessen, was ausgegeben werden darf. */}
          {kasse.total_out_capital?.authorization != null && (
            <p className="mt-3 max-w-[70ch] border-t border-border/60 pt-3 text-[13px] leading-relaxed text-foreground/85">
              Ausgeben durfte die Stadt für Investitionen mehr als die geplanten{" "}
              {deMio(mio(kasse.total_out_capital.plan))}&#8239;Mio.&nbsp;€: Weitere{" "}
              <strong>{deMio(mio(kasse.total_out_capital.authorization))}&#8239;Mio.&nbsp;€</strong>{" "}
              standen als Ermächtigungen aus Vorjahren offen — bewilligtes Geld für
              Vorhaben, die noch nicht fertig sind, und das deshalb mit ins nächste Jahr
              wandert<Beleg q="cash_flow_statement" />.
            </p>
          )}
          <p className="mt-3 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Beide Rechnungen beantworten unterschiedliche Fragen. Abschreibungen mindern
            das Ergebnis, ohne eine Auszahlung auszulösen. Ein Neubau verursacht dagegen
            sofort Auszahlungen, wird in der Ergebnisrechnung aber erst über seine
            Nutzungsdauer als Aufwand erfasst. Deshalb lassen sich Jahresergebnis und
            Kassenbestand nicht direkt miteinander vergleichen.
          </p>
        </div>
      )}

      {/* Woran „geplant" hier gemessen wird. In den meisten Jahrgängen ist
          das der Haushaltsansatz; 2018 und 2020 nicht — und das ist keine
          Kleinigkeit, sondern bei den Ausgaben 2020 ein Unterschied von
          27 Mio. €. Also steht es dran, statt still unterzugehen. */}
      {ansatzAbweichend && (
        <div className="rounded-2xl border border-primary/25 bg-primary/[0.05] p-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was „geplant" in diesem Jahr heißt
          </p>
          <p className="mt-2 max-w-[70ch] text-[13px] leading-relaxed text-foreground/90">
            Für {year} vergleicht der Jahresabschluss nicht mit dem ursprünglichen Haushaltsplan,
            sondern mit dem fortgeschriebenen Plan — der Bezugsgröße{" "}
            <strong>{PLAN_ART_LABEL[planArt]}</strong>. Der Rat hatte im Ursprungsplan{" "}
            {deMio(ansatzAbweichend.ertr)}&#8239;Mio.&nbsp;€ Einnahmen und{" "}
            {deMio(ansatzAbweichend.aufw)}&#8239;Mio.&nbsp;€ Ausgaben beschlossen; unterjährig kam{" "}
            {planArt === "supplementary_budget" ? "ein Nachtragshaushalt" : "Ermächtigungen und Übertragungen"}{" "}
            hinzu. Die Zahlen unten messen gegen den fortgeschriebenen Plan — so rechnet die
            Stadt selbst<Beleg q="jahresabschluss" />.
          </p>
        </div>
      )}

      <LottiErklaert
        title="Warum ein Haushalt nie punktgenau aufgeht"
        text="Ein Haushalt wird ein Jahr im Voraus beschlossen — niemand weiß dann, wie viel Gewerbesteuer hereinkommt, welche Tarife steigen oder wie viele Kinder einen Kitaplatz brauchen. Die Stadt plant deshalb vorsichtig: lieber etwas zu wenig Einnahmen ansetzen als zu viel. Abweichungen sind normal und für sich genommen weder gut noch schlecht."
      />

      {/* Hantel je Teilhaushalt (H-16). Die Bedingung fragt nach Zeilen, die
          BEIDE Werte tragen: Sonst stand hier eine Überschrift mit Umschalter,
          Erklärtext und Legende über einer leeren Fläche — die Hantel selbst
          zeichnet ohne Planwert nichts. */}
      {bereiche.some((b) => b.aufwPlan != null && b.aufwIst != null) && (
        <div id="hanteln" className="scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Ausgaben je Bereich · {year}
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {bereiche.length} Teilhaushalte
            </span>
          </div>

          {/* Umschalter wie brutto/netto auf der Bereichsseite: Der Wechsel
              dreht die Reihenfolge, und darin steckt die Aussage. */}
          <div className="mb-3 flex flex-col gap-1.5">
            <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
              <div className="flex w-max flex-none items-center gap-1 rounded-full border border-border bg-muted/40 p-1">
                {([
                  ["percent", "Abweichung in Prozent"],
                  ["amount", "Abweichung in Millionen"],
                ] as [HantelMassstab, string][]).map(([value, text]) => (
                  <button key={value} type="button" onClick={() => setMassstab(value)}
                    className={cn("whitespace-nowrap rounded-full px-3 py-1 text-[12.5px]",
                      massstab === value
                        ? "bg-card font-semibold shadow-sm"
                        : "text-foreground/70 hover:text-foreground")}>
                    {text}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              {massstab === "percent"
                ? "Gemessen am eigenen Plan — so lässt sich ein Bereich von 231 Mio. € mit einem von 6 Mio. € vergleichen. Vorn steht, wessen Plan am weitesten danebenlag."
                : "Gemessen in Euro — vorn steht, wo am meisten Geld anders floss als geplant. Kleine Bereiche verschwinden dabei fast."}
            </p>
          </div>

          {/* Der Einordnungssatz je Hantel (H4-07) kommt aus dem Abschluss
              selbst: Abschnitt 6.3.1 erläutert die Gesamtrechnung, nennt den
              Bereich aber regelmäßig ausdrücklich („Im Teilhaushalt 10 …") —
              nur diese Nennungen werden zugeordnet (`gruendeFuerBereich`),
              nichts wird dazugedichtet. Wo der Abschluss den Bereich nicht
              nennt, steht bewusst kein Satz: `einordnung: null` ist die
              ehrliche Auskunft, kein vergessenes Feld. */}
          <Hantel massstab={massstab} schwelle={8} zeilen={hantelZeilen} />
        </div>
      )}

      {/* Woran es lag: Ertragsarten mit der größten Abweichung */}
      {arten.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Woher der Unterschied bei den Einnahmen kommt
          </p>
          <div className="mt-3 flex flex-col gap-2.5">
            {arten.map((p) => {
              const abw = mio(p.deviation) ?? 0;
              const groesste = mio(Math.max(...arten.map((x) => Math.abs(x.deviation ?? 0)))) ?? 1;
              return (
                <div key={p.nr} className="flex flex-col gap-1.5">
                  <div className="grid grid-cols-[minmax(110px,190px)_1fr_auto] items-center gap-x-3">
                    <span className="truncate text-[12.5px]">{p.label}</span>
                    <div className="h-2.5 rounded-full bg-muted">
                      <div className="h-full rounded-full bg-signal/70"
                        style={{ width: `${Math.min((Math.abs(abw) / groesste) * 100, 100)}%` }} />
                    </div>
                    <span className="whitespace-nowrap text-right text-[12px] font-semibold tabular-nums">
                      {abw > 0 ? "+" : ""}{deMio(abw)}&#8239;Mio.&nbsp;€
                    </span>
                  </div>
                  <Warum reason={grundZuPosten(data, year, p.nr)} />
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
            Abweichung zwischen Plan und Ergebnis je Einnahmeart<Beleg q="jahresabschluss" />.
            Die größten Ausschläge erklären den Unterschied oben.
          </p>
        </div>
      )}

      {/* Die übrigen erläuterten Posten — vor allem die Ausgabenseite. Der
          Jahresabschluss erläutert jede Abweichung ab 20 % gegenüber dem
          Plan; die Einnahmearten stehen schon oben, hier kommt der Rest. */}
      {uebrigeGruende.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Warum es anders kam · {year}
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {uebrigeGruende.length} weitere Posten
            </span>
          </div>
          <div className="flex flex-col gap-3">
            {uebrigeGruende.map((g) => (
              <div key={g.nr} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                  <span className="text-[12.5px] font-semibold">{g.label}</span>
                  <span className="whitespace-nowrap font-mono text-[11px] tabular-nums text-signal">
                    {(g.delta_meur ?? 0) > 0 ? "+" : ""}{deMio(g.delta_meur)}&#8239;Mio.&nbsp;€
                    {g.percent != null && (
                      <span className="text-muted-foreground">
                        {" "}({g.percent > 0 ? "+" : ""}
                        {g.percent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%)
                      </span>
                    )}
                  </span>
                </div>
                <Warum reason={g} />
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
            Erläutert wird, was um mindestens 20&nbsp;% vom Plan abweicht
            <Beleg q="jahresabschluss" />. Übernommen haben wir eine Erläuterung nur, wenn
            Betrag und Prozentsatz aus ihrer Überschrift zu der Zeile passen, die wir aus der
            Tabelle gelesen haben.
          </p>
        </div>
      )}

      {/* Warum die Nachbewilligungen GENAU HIER stehen: „Warum es anders kam"
          darüber erklärt die Abweichung mit den Worten des Jahresabschlusses —
          im Nachhinein und je Posten. Dieser Block zeigt dieselbe Abweichung
          von der anderen Seite: als Entscheidungen, die während des Jahres
          getroffen wurden, mit Datum, Betrag und Beschluss-Seite. Erst
          zusammen beantworten sie die Frage der Seite. */}
      <NachbewilligungsBlock daten={data} year={year} />

      {/* Wer den Plan gegen das Ist gelesen hat, gehört als Nächstes hierhin:
          Genau diesen Vergleich beanstandet das Rechnungsprüfungsamt. */}
      <PruefungsHinweis />

      {/* Nicht-Chart-Entsprechung (H-17 als Tabelle). Der Auslöser stand hier
          als nackter Link in einer sonst leeren Karte — man sah einen Knopf
          und nicht, wozu. Jetzt trägt die Karte denselben Kopf wie die
          anderen: Kicker links, ehrliche Zähl-/Zeitraum-Angabe rechts. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Dieselben Ausgaben als Tabelle
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {bereiche.length} Teilhaushalte · {year}
          </span>
        </div>
        <button type="button" onClick={() => setZahlenOffen((o) => !o)}
          aria-expanded={zahlenOffen}
          className="mt-1.5 inline-flex min-h-[36px] items-center gap-1 text-[12.5px] font-semibold text-primary">
          {zahlenOffen ? "Tabelle einklappen" : "Tabelle anzeigen"}
          <ChevronDown size={14} strokeWidth={2}
            className={cn("transition-transform", zahlenOffen && "rotate-180")} />
        </button>
        {zahlenOffen && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[420px] text-[12px] tabular-nums">
              <thead>
                <tr className="text-left font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  <th className="py-1 pr-2 font-medium">Bereich</th>
                  <th className="py-1 pr-2 text-right font-medium">geplant Mio.&nbsp;€</th>
                  <th className="py-1 pr-2 text-right font-medium">tatsächlich Mio.&nbsp;€</th>
                  <th className="py-1 text-right font-medium">Abweichung Mio.&nbsp;€</th>
                </tr>
              </thead>
              <tbody>
                {bereiche.map((b) => {
                  const d = (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
                  const percent = b.aufwPlan ? (d / b.aufwPlan) * 100 : 0;
                  return (
                    <tr key={b.nr} className="border-t border-border/60">
                      <td className="py-1 pr-2">{b.name}</td>
                      <td className="py-1 pr-2 text-right">{deMio(b.aufwPlan)}</td>
                      <td className="py-1 pr-2 text-right font-semibold">{deMio(b.aufwIst)}</td>
                      <td className={cn("py-1 text-right", Math.abs(percent) >= 1 && "text-signal")}>
                        {d > 0 ? "+" : ""}{deMio(d)} ({percent > 0 ? "+" : ""}
                        {percent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%)
                      </td>
                    </tr>
                  );
                })}
                <tr className="border-t-2 border-border font-semibold">
                  <td className="py-1 pr-2">Alle Ausgaben</td>
                  <td className="py-1 pr-2 text-right">{deMio(gesamt.aufwPlan)}</td>
                  <td className="py-1 pr-2 text-right">{deMio(gesamt.aufwIst)}</td>
                  <td className="py-1 text-right">{aufwDiff > 0 ? "+" : ""}{deMio(aufwDiff)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Der Abschluss ist geprüft — von einer anderen Stelle als der, die
          ihn aufgestellt hat. Das gehört dazu, ohne den Bericht auszuschlachten. */}
      {pruefbericht?.url && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Geprüft
          </p>
          <p className="mt-2 max-w-[74ch] text-[13px] leading-relaxed text-foreground/90">
            Das Rechnungsprüfungsamt hat den Jahresabschluss {year} geprüft und dazu einen
            Schlussbericht vorgelegt
            {pruefbericht.n_pages ? ` (${pruefbericht.n_pages} Seiten)` : ""}.{" "}
            <a href={pruefbericht.url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
              Schlussbericht öffnen
              <ExternalLink className="h-3 w-3" />
            </a>
          </p>
          {pruefbericht.readable === 0 && (
            <p className="mt-2 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Von diesem Jahrgang liegt uns nur das PDF vor: Der Text darin ist nicht
              maschinenlesbar hinterlegt, deshalb können wir daraus nichts zitieren oder
              durchsuchbar machen. Wer hineinsehen möchte, öffnet den Bericht direkt.
            </p>
          )}
        </div>
      )}

      {/* Warum hier nicht jedes Jahr steht — als Grenze, nicht als Prüfzeugnis.
          Bis 16.08. folgten dem ersten Halbsatz drei Rechenproben in Prosa
          („Die Summe der Teilhaushalte muss die Gesamtrechnung ergeben …").
          Die Proben gelten unverändert (`summenprobe`, `strukturprobe` und
          `vorjahreskette` in `council/finanzberichte.py`, Doku:
          „Vier Prüfungen, und keine davon ist optional"), aber sie erklären
          niemandem den Haushalt — sie beruhigen uns. DESIGNSPRACHE.md § 7. */}
      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Es erscheinen nur Jahre, für die ein Jahresabschluss vorliegt. Für das laufende und
        das kommende Haushaltsjahr gibt es naturgemäß noch keinen.
      </p>

      {/* Der Nebenbefund über die ganze Reihe — er gehört zu keinem einzelnen
          Jahr und steht deshalb hier unten, in derselben Zeilen-Grammatik wie
          die Grenzen darüber. Nüchtern, ohne Kommentar: Die Vorlagen sind
          vorher im Fachausschuss beraten, und was dort keine Mehrheit findet,
          erreicht den Rat meist gar nicht erst. */}
      <NachbewilligungsBefund daten={data} />

      <SchrittWeiter href="/haushalt/plan-ist" />

      <Quellenverzeichnis keys={quellen} />
    </div>
    </Quellenkontext>
  );
}

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
const FELDER = ["years", "income_statement", "variance_reasons", "supplementary_approvals", "plan_actual_years", "cash_flow_statement", "audit_report_sources"] as const;

export default function PlanIstPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}>
      <PlanIstInner />
    </Suspense>
  );
}
