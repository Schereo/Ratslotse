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
  ErgebnisPosten, HaushaltDaten, PLAN_ART_LABEL, PlanArt,
  deMio, grundZuPosten, gruendeFuerBereich, mio, pruefberichtZuJahr,
} from "@/lib/haushalt";
import { PruefberichtDaten, wiederholungsketten } from "@/lib/haushalt-pruefung";
import { Warum } from "@/components/haushalt/warum";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { MarkePille } from "@/components/haushalt/marke";
import { Hantel, HantelMassstab } from "@/components/grafik/hantel";
import { cn } from "@/lib/utils";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

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
  const { data } = useFetch<PruefberichtDaten>("/council/haushalt/pruefberichte?marke=WB");
  const kette = useMemo(() => {
    if (!data?.feststellungen?.length) return null;
    return wiederholungsketten(data.feststellungen)
      .find((k) => k.schluessel.includes("planistvergleich")) ?? null;
  }, [data]);
  if (!kette) return null;
  // Ausdrücklich die jüngste WIEDERHOLTE Beanstandung, nicht einfach den
  // letzten Eintrag: Der Abschnitt trägt in denselben Jahren auch Hinweise.
  const juengste = [...kette.eintraege].reverse().find((f) => f.marke === "WB");
  if (!juengste) return null;

  return (
    <Link href="/haushalt/pruefung"
      className="group flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <MarkePille marke={juengste.marke} name={juengste.marke_name} klein />
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          Rechnungsprüfungsamt · Schlussbericht {juengste.jahr} · Textziffer {juengste.textziffer}
        </span>
      </div>
      <p className="border-l-2 border-border pl-3 text-[13.5px] leading-relaxed text-foreground/90">
        {juengste.text}
      </p>
      <span className="flex items-center gap-1 text-[12.5px] font-semibold text-primary">
        In {kette.jahre.length} von {data?.jahre.length} geprüften Jahren als wiederholte
        Beanstandung ausgewiesen — alle Feststellungen ansehen
        <ArrowRight size={14} strokeWidth={2} className="transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
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
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const [zahlenOffen, setZahlenOffen] = useState(false);
  const [massstab, setMassstab] = useState<HantelMassstab>("prozent");

  const jahre = data?.plan_ist_jahre ?? [];
  const jahr = gewaehltesJahr && jahre.includes(gewaehltesJahr) ? gewaehltesJahr : jahre.at(-1) ?? null;

  const { gesamt, bereiche, arten, planArt, ansatzAbweichend } = useMemo(() => {
    const leer = {
      gesamt: null as null | Record<string, number | null>, bereiche: [] as Bereich[],
      arten: [] as ErgebnisPosten[], planArt: "ansatz" as PlanArt,
      ansatzAbweichend: null as null | { ertr: number | null; aufw: number | null },
    };
    if (!data || !jahr) return leer;
    const zeilen = (data.ergebnisrechnung ?? []).filter((p) => p.jahr === jahr);
    const summe = (rows: ErgebnisPosten[], nr: number) => rows.find((p) => p.nr === nr);
    const g = zeilen.filter((p) => p.thh_nr == null);
    const e = summe(g, 12), a = summe(g, 20);

    const nrs = [...new Set(zeilen.filter((p) => p.thh_nr != null).map((p) => p.thh_nr))];
    const bereiche = nrs.map((nr) => {
      const teil = zeilen.filter((p) => p.thh_nr === nr);
      const te = summe(teil, 12), ta = summe(teil, 20);
      return {
        nr, name: teil[0]?.thh_name ?? `Teilhaushalt ${nr}`,
        aufwPlan: mio(ta?.plan), aufwIst: mio(ta?.ergebnis),
        ertrPlan: mio(te?.plan), ertrIst: mio(te?.ergebnis),
      };
    });
    type Aufw = { aufwPlan: number | null; aufwIst: number | null };
    const abw = (b: Aufw) => (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
    bereiche.sort((x, y) => massstab === "prozent"
      ? Math.abs(abw(y)) / Math.abs(y.aufwPlan || 1) - Math.abs(abw(x)) / Math.abs(x.aufwPlan || 1)
      : Math.abs(abw(y)) - Math.abs(abw(x)));

    // Woran es lag: die Ertragsarten (Posten 1–11) mit der größten Abweichung.
    const arten = g
      .filter((p) => p.nr >= 1 && p.nr <= 11 && p.abweichung != null)
      .sort((x, y) => Math.abs(y.abweichung ?? 0) - Math.abs(x.abweichung ?? 0))
      .slice(0, 5);

    // Weicht der fortgeschriebene Plan vom ursprünglichen Ansatz ab, gehört
    // beides auf die Seite — 2020 sind das bei den Ausgaben 27 Mio. €.
    const weicht = (p?: ErgebnisPosten) =>
      p?.plan != null && p?.ansatz != null && Math.abs(p.plan - p.ansatz) > 1;

    return {
      gesamt: {
        ertrPlan: mio(e?.plan), ertrIst: mio(e?.ergebnis),
        aufwPlan: mio(a?.plan), aufwIst: mio(a?.ergebnis),
      },
      bereiche, arten,
      planArt: (a?.plan_art ?? e?.plan_art ?? "ansatz") as PlanArt,
      ansatzAbweichend: weicht(e) || weicht(a)
        ? { ertr: mio(e?.ansatz), aufw: mio(a?.ansatz) }
        : null,
    };
  }, [data, jahr, massstab]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!jahr || !gesamt) {
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
  const saldoPlan = (gesamt.ertrPlan ?? 0) - (gesamt.aufwPlan ?? 0);
  const saldoIst = (gesamt.ertrIst ?? 0) - (gesamt.aufwIst ?? 0);
  const quellen: QuellenSchluessel[] = ["jahresabschluss", "plan"];
  const pruefbericht = pruefberichtZuJahr(data, jahr);
  // Die Zeilen der Hantel. Zwei Regeln, beide oben im Kopf begründet:
  // ein Wortlaut je Erläuterung, und nichts über EINORDNUNG_GRENZE im Bild.
  const wortlautBei = new Map<number, string>();
  const imBild = new Set<number>();
  const hantelZeilen = bereiche.map((b) => {
    const alle = b.nr == null ? [] : gruendeFuerBereich(data, jahr, b.nr);
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
        einordnung = (
          <>
            {g.text}{" "}
            <span className="font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground">
              — Jahresabschluss {jahr}, Abschnitt 6.3.1, Wortlaut der Verwaltung
            </span>
          </>
        );
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
  const uebrigeGruende = (data.abweichungsgruende ?? [])
    .filter((g) => g.jahr === jahr && !obenGezeigt.has(g.nr))
    .sort((a, b) => Math.abs(b.delta_mio ?? 0) - Math.abs(a.delta_mio ?? 0));

  return (
    <Quellenkontext schluessel={quellen} jahr={jahr}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Geplant und geworden</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">
          Geplant und geworden
        </h1>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Ein Haushalt ist ein Plan. Was am Jahresende wirklich zusammenkam, steht erst im
          Jahresabschluss — hier beides nebeneinander.
        </p>
      </div>

      {/* Jahr-Umschalter: nur Jahre mit echtem Abschluss (scrollbar wie #497). */}
      {jahre.length > 1 && (
        <div className="flex flex-col gap-1.5">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Abgeschlossenes Haushaltsjahr
          </span>
          <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
            <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
              {jahre.map((j) => (
                <Link key={j} href={`/haushalt/plan-ist?jahr=${j}`} scroll={false}
                  className={cn("rounded-full px-3 py-1 text-[12.5px]",
                    j === jahr ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
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
          Das Jahr {jahr} in zwei Sätzen
        </p>
        {planVorhanden ? (
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
            Die Stadt hat <strong>{deMio(gesamt.ertrIst)}&#8239;Mio.&nbsp;€ eingenommen</strong> —
            geplant waren {deMio(gesamt.ertrPlan)}<Beleg q="jahresabschluss" />
            {Math.abs(ertrDiff) >= 1 && (
              <>, also {deMio(Math.abs(ertrDiff))}&#8239;Mio. {ertrDiff > 0 ? "mehr" : "weniger"}</>
            )}. Ausgegeben hat sie <strong>{deMio(gesamt.aufwIst)}&#8239;Mio.</strong> statt der
            geplanten {deMio(gesamt.aufwPlan)}
            {Math.abs(aufwDiff) >= 1 && (
              <> ({aufwDiff > 0 ? "+" : "−"}{deMio(Math.abs(aufwDiff))})</>
            )}.
          </p>
        ) : (
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
            Die Stadt hat {jahr} <strong>{deMio(gesamt.ertrIst)}&#8239;Mio.&nbsp;€ eingenommen</strong>{" "}
            und <strong>{deMio(gesamt.aufwIst)}&#8239;Mio.</strong> ausgegeben
            <Beleg q="jahresabschluss" />. Die Planwerte der Gesamtrechnung konnten wir für
            diesen Jahrgang nicht auslesen — deshalb steht hier kein „geplant" daneben und keine
            Abweichung. Geraten wird sie nicht. Wo der Abschluss einzelne Posten selbst mit
            ihrem Plan vergleicht, steht das weiter unten.
          </p>
        )}
        {planVorhanden && (
          <div className="mt-3 grid gap-2.5 border-t border-border/60 pt-3 sm:grid-cols-2">
            <div>
              <p className="text-[11.5px] text-muted-foreground">Geplantes Jahresergebnis</p>
              <p className="font-display text-[20px] font-bold tabular-nums">
                {saldoPlan > 0 ? "+" : ""}{deMio(saldoPlan)}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.</span>
              </p>
            </div>
            <div>
              <p className="text-[11.5px] text-muted-foreground">Tatsächliches Jahresergebnis</p>
              <p className="font-display text-[20px] font-bold tabular-nums">
                {saldoIst > 0 ? "+" : ""}{deMio(saldoIst)}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.</span>
              </p>
            </div>
          </div>
        )}
      </div>

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
            Für {jahr} vergleicht der Jahresabschluss nicht mit dem ursprünglichen Haushaltsplan,
            sondern mit dem fortgeschriebenen Plan — der Bezugsgröße{" "}
            <strong>{PLAN_ART_LABEL[planArt]}</strong>. Der Rat hatte im Ursprungsplan{" "}
            {deMio(ansatzAbweichend.ertr)}&#8239;Mio.&nbsp;€ Einnahmen und{" "}
            {deMio(ansatzAbweichend.aufw)}&#8239;Mio.&nbsp;€ Ausgaben beschlossen; unterjährig kam{" "}
            {planArt === "ansatz_nachtrag" ? "ein Nachtragshaushalt" : "Ermächtigungen und Übertragungen"}{" "}
            hinzu. Die Zahlen unten messen gegen den fortgeschriebenen Plan — so rechnet die
            Stadt selbst<Beleg q="jahresabschluss" />.
          </p>
        </div>
      )}

      <LottiErklaert
        titel="Warum ein Haushalt nie punktgenau aufgeht"
        text="Ein Haushalt wird ein Jahr im Voraus beschlossen — niemand weiß dann, wie viel Gewerbesteuer hereinkommt, welche Tarife steigen oder wie viele Kinder einen Kitaplatz brauchen. Die Stadt plant deshalb vorsichtig: lieber etwas zu wenig Einnahmen ansetzen als zu viel. Abweichungen sind normal und für sich genommen weder gut noch schlecht."
      />

      {/* Hantel je Teilhaushalt (H-16). Die Bedingung fragt nach Zeilen, die
          BEIDE Werte tragen: Sonst stand hier eine Überschrift mit Umschalter,
          Erklärtext und Legende über einer leeren Fläche — die Hantel selbst
          zeichnet ohne Planwert nichts. */}
      {bereiche.some((b) => b.aufwPlan != null && b.aufwIst != null) && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Ausgaben je Bereich · {jahr}
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
                  ["prozent", "Abweichung in Prozent"],
                  ["betrag", "Abweichung in Millionen"],
                ] as [HantelMassstab, string][]).map(([wert, text]) => (
                  <button key={wert} type="button" onClick={() => setMassstab(wert)}
                    className={cn("whitespace-nowrap rounded-full px-3 py-1 text-[12.5px]",
                      massstab === wert
                        ? "bg-card font-semibold shadow-sm"
                        : "text-foreground/70 hover:text-foreground")}>
                    {text}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              {massstab === "prozent"
                ? "Gemessen am eigenen Plan — so lässt sich ein Bereich von 231 Mio. mit einem von 6 Mio. vergleichen. Vorn steht, wessen Plan am weitesten danebenlag."
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
              const abw = mio(p.abweichung) ?? 0;
              const groesste = mio(Math.max(...arten.map((x) => Math.abs(x.abweichung ?? 0)))) ?? 1;
              return (
                <div key={p.nr} className="flex flex-col gap-1.5">
                  <div className="grid grid-cols-[minmax(110px,190px)_1fr_auto] items-center gap-x-3">
                    <span className="truncate text-[12.5px]">{p.bezeichnung}</span>
                    <div className="h-2.5 rounded-full bg-muted">
                      <div className="h-full rounded-full bg-signal/70"
                        style={{ width: `${Math.min((Math.abs(abw) / groesste) * 100, 100)}%` }} />
                    </div>
                    <span className="whitespace-nowrap text-right text-[12px] font-semibold tabular-nums">
                      {abw > 0 ? "+" : ""}{deMio(abw)}&#8239;Mio.
                    </span>
                  </div>
                  <Warum grund={grundZuPosten(data, jahr, p.nr)} />
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
              Warum es anders kam · {jahr}
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {uebrigeGruende.length} weitere Posten
            </span>
          </div>
          <div className="flex flex-col gap-3">
            {uebrigeGruende.map((g) => (
              <div key={g.nr} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                  <span className="text-[12.5px] font-semibold">{g.bezeichnung}</span>
                  <span className="whitespace-nowrap font-mono text-[11px] tabular-nums text-signal">
                    {(g.delta_mio ?? 0) > 0 ? "+" : ""}{deMio(g.delta_mio)}&#8239;Mio.
                    {g.prozent != null && (
                      <span className="text-muted-foreground">
                        {" "}({g.prozent > 0 ? "+" : ""}
                        {g.prozent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%)
                      </span>
                    )}
                  </span>
                </div>
                <Warum grund={g} />
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
            {bereiche.length} Teilhaushalte · {jahr}
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
                  <th className="py-1 pr-2 text-right font-medium">geplant</th>
                  <th className="py-1 pr-2 text-right font-medium">tatsächlich</th>
                  <th className="py-1 text-right font-medium">Abweichung</th>
                </tr>
              </thead>
              <tbody>
                {bereiche.map((b) => {
                  const d = (b.aufwIst ?? 0) - (b.aufwPlan ?? 0);
                  const prozent = b.aufwPlan ? (d / b.aufwPlan) * 100 : 0;
                  return (
                    <tr key={b.nr} className="border-t border-border/60">
                      <td className="py-1 pr-2">{b.name}</td>
                      <td className="py-1 pr-2 text-right">{deMio(b.aufwPlan)}</td>
                      <td className="py-1 pr-2 text-right font-semibold">{deMio(b.aufwIst)}</td>
                      <td className={cn("py-1 text-right", Math.abs(prozent) >= 1 && "text-signal")}>
                        {d > 0 ? "+" : ""}{deMio(d)} ({prozent > 0 ? "+" : ""}
                        {prozent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%)
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
            Das Rechnungsprüfungsamt hat den Jahresabschluss {jahr} geprüft und dazu einen
            Schlussbericht vorgelegt
            {pruefbericht.n_pages ? ` (${pruefbericht.n_pages} Seiten)` : ""}.{" "}
            <a href={pruefbericht.url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
              Schlussbericht öffnen
              <ExternalLink className="h-3 w-3" />
            </a>
          </p>
          {pruefbericht.lesbar === 0 && (
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

      <SchrittWeiter href="/haushalt/plan-ist" />

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}

export default function PlanIstPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}>
      <PlanIstInner />
    </Suspense>
  );
}
