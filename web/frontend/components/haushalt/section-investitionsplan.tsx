"use client";

// „Was baut und kauft die Stadt?" — der ERSTE Abschnitt von
// /haushalt/investitionen: der PLAN.
//
// Bis zum 21.08.2026 die eigene Seite. Zusammengelegt mit „Was wurde davon
// wirklich gebaut?": Plan und Ist derselben Sache standen in zwei
// verschiedenen Etappen, und wer wissen wollte, was aus einem Vorhaben
// geworden ist, musste die Seite wechseln. Der Rahmen liegt bei der Seite
// (Begründung: `section-termine.tsx`).

// /haushalt/investitionen — „Was baut und kauft die Stadt?"
//
// Die Seite füllt die größte Lücke des Bereichs: Alle Seiten davor zeigen den
// **Ergebnishaushalt** — laufende Erträge und Aufwendungen. Darin steht keine
// einzige Investition. Ein Schulneubau taucht dort nur als Abschreibung auf,
// verteilt über Jahrzehnte, lange nachdem gebaut wurde. Wer bis hierher gelesen
// hat, hat noch nicht eine Zahl über Neubauten, Fahrzeuge oder Grundstücke
// gesehen.
//
// Leserichtung: die eine Zahl (und wie klein sie neben dem Gesamthaushalt ist)
// → in welchen Bereichen → was dagegensteht (Zuschüsse, Verkäufe) → über die
// Jahre → was ein Finanzhaushalt überhaupt ist → was diese Zahlen NICHT sagen
// → Quellen.
//
// DER WICHTIGSTE ABSATZ IST DER MIT DEN GRENZEN, und er steht deshalb nicht
// am Ende versteckt, sondern als eigener Block. Zwei Sätze müssen hängen
// bleiben, sonst nimmt jemand diese Seite für etwas, das sie nicht ist:
//
//  1. **Es sind Planzahlen.** Der Datensatz ist der Haushaltsplan. Was am
//     Jahresende wirklich verbaut wurde, steht nicht darin — und bei
//     Investitionen ist der Abstand notorisch groß (Planung zieht sich,
//     Aufträge werden nicht vergeben). „So viel wird gebaut" wäre eine
//     Behauptung über etwas, das die Quelle nicht hergibt.
//  2. **Kein einzelnes Vorhaben.** Die Quelle sagt „Verkehr und Straßenbau:
//     10,5 Mio. €", nicht welche Straße. Die häufigste Frage an diese Seite
//     („wird MEINE Schule saniert?") beantwortet sie nicht, und sie sagt das.
//
// KEINE BEWERTUNGSFARBEN, wie im ganzen Bereich (components/grafik/hantel.tsx):
// Ein Bereich mit hohen Investitionen ist nicht „gut", einer mit niedrigen
// nicht „schlecht" — in dem einen wird gerade eine Schule gebaut, im anderen
// nicht. Die Segmente kommen aus der Ausgabenrampe, das Signal-Orange bleibt
// der Marke vorbehalten.
//
// UND KEINE SELBSTVERGEWISSERUNG (DESIGNSPRACHE.md §7): Dass die Summenprobe
// der Datei aufgeht, steht in `council/investitionen.py` und in den Tests, im
// Beleg als Messwert — aber nicht als Absatz auf der Seite. Was hier steht,
// ist die Quelle, was unsere eigene Rechnung ist, und wo die Zahlen enden.

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { amount, deMio, mio } from "@/lib/haushalt";
import {
  Herkunft, InvestitionenDaten, InvestitionsZeile, finanzhaushaltJahr,
  gesamtJahr, herkunftVon, investitionsAnteil, netto, series, teilhaushalte,
} from "@/lib/haushalt-investitionen";
import {
  ProgrammDaten, count, passenderJahrgang,
} from "@/lib/haushalt-investitionsprogramm";
import { Beleg } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Vorhaben } from "@/components/haushalt/vorhaben";
import { cn } from "@/lib/utils";


/** Anker des Summen-Blocks — Ziel des Rückwegs aus den Vorhaben. */
const ANKER_BEREICHE = "bereiche";

/** Die Herkunft einer Angabe im Klartext — dieselbe Form wie auf
 *  `/haushalt/konzern`: welcher Abschnitt, welcher Stand.
 *
 *  HIER STANDEN BIS 16.08. AUCH UNSERE PROBEN — die Sätze aus
 *  `herkunft.PROBEN` und darunter „Gemessen: 0,00 € Restbetrag“. Das sagt
 *  etwas über uns und nichts über den Haushalt (DESIGNSPRACHE.md § 7); auf
 *  `/haushalt/konzern` ist es aus demselben Grund verschwunden. Die Proben
 *  laufen unverändert weiter, die API liefert sie weiter, Tests halten sie
 *  fest und die Technik-Doku beschreibt sie. Nur die Zurschaustellung ist weg.
 *  Gehört an die einzelne Zahl; das Verzeichnis am Seitenende beschreibt die
 *  Quelle der ganzen Seite. */
function Fundstelle({ h }: { h: Herkunft | null }) {
  if (!h) return null;
  return (
    <div className="border-t border-dashed border-border pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      {h.citation && (
        <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
          {h.citation}{h.stand ? ` · ${h.stand}` : ""}
        </p>
      )}
    </div>
  );
}

/** Eine Zeile der Rangliste: Bereich, Balken, Betrag — und was dagegensteht.
 *
 *  Der Balken misst an den Auszahlungen des größten Bereichs, nicht an der
 *  Gesamtsumme: Sonst wäre die längste Strecke halb so lang wie das Feld und
 *  die zehn kleinen Bereiche unsichtbar. */
function Rang({ zeile, skala, aufVorhaben, vorhandene }: {
  zeile: InvestitionsZeile;
  skala: number;
  /** Der Weg nach unten: von der Summe zu den einzelnen Vorhaben. */
  aufVorhaben: (thhNr: number) => void;
  /** Wie viele Vorhaben das Investitionsprogramm für diesen Bereich führt —
   *  0, wenn der Jahrgang dort fehlt. Dann gibt es nichts zu öffnen, und die
   *  Zeile bleibt eine Zeile statt zu einem Knopf zu werden, der nichts tut. */
  vorhandene: number;
}) {
  const aus = amount(zeile.outflows);
  const gegen = zeile.inflows > 0 ? amount(zeile.inflows) : null;
  const breite = skala > 0 ? Math.max(0.6, (zeile.outflows / skala) * 100) : 0;
  const gegenAnteil = zeile.outflows > 0
    ? (zeile.inflows / zeile.outflows) * 100
    : 0;
  return (
    <li className="flex flex-col gap-1.5 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-[13px] font-medium leading-snug">{zeile.label}</span>
        <span className="flex-none font-display text-[15px] font-bold tabular-nums">
          {aus.wert}
          <span className="ml-1 text-[10.5px] font-medium text-muted-foreground">
            {aus.einheit}
          </span>
        </span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted/60"
        role="img"
        aria-label={`${zeile.label}: ${aus.wert} ${aus.einheit} geplante Auszahlungen`}
      >
        <div
          className="h-full rounded-full bg-[var(--hh-aus-2)]"
          style={{ width: `${breite}%` }}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        {gegen ? (
          <p className="text-[11px] leading-snug text-muted-foreground">
            <span className="font-medium text-foreground/80">Davon gedeckt:</span>{" "}
            {gegen.wert} {gegen.einheit} durch Zuschüsse, Verkäufe oder Beiträge
            {gegenAnteil > 0 && (
              <> · {gegenAnteil.toLocaleString("de-DE", { maximumFractionDigits: 0 })} %</>
            )}
          </p>
        ) : <span />}
        {vorhandene > 0 && (
          <button
            type="button"
            onClick={() => aufVorhaben(zeile.sub_budget_no)}
            className="text-[11px] text-primary hover:underline"
          >
            {vorhandene} einzelne Vorhaben ansehen
          </button>
        )}
      </div>
    </li>
  );
}

export function InvestitionsplanAbschnitt({ onBestand }: {
  /** Meldet den Vorhaben-Bestand des Investitionsprogramms nach oben — die
   *  Seitenbühne im Kopf zählt dieselben Maßnahmen wie die Vorhaben-Listen
   *  dieses Abschnitts, aus derselben Antwort (H5-02). Über alle Jahrgänge,
   *  damit die Zahl nicht am Jahr-Umschalter hängt. */
  onBestand?: (b: { vorhaben: number; von: number; bis: number } | null) => void;
} = {}) {
  const { data, loading } = useFetch<InvestitionenDaten>("/council/haushalt/investitionen");
  // Die Vorhaben kommen aus einer anderen Quelle (Haushaltsplan statt
  // Open-Data-Portal) und reichen weiter zurück. Eigener Abruf, eigene
  // Jahresliste — zusammengelegt wäre einer von beiden immer beschnitten.
  const { data: programm, loading: programmLaedt } = useFetch<ProgrammDaten>(
    "/council/haushalt/investitionsprogramm");

  useEffect(() => {
    if (!onBestand || programmLaedt) return;
    if (!programm?.massnahmen.length || !programm.jahre.length) { onBestand(null); return; }
    onBestand({
      vorhaben: programm.massnahmen.length,
      von: Math.min(...programm.jahre),
      bis: Math.max(...programm.jahre),
    });
  }, [onBestand, programm, programmLaedt]);
  const jahre = useMemo(() => [...(data?.jahre ?? [])].sort((a, b) => a - b), [data]);
  const [year, setJahr] = useState<number | null>(null);
  const aktJahr = year ?? (jahre.length ? jahre[jahre.length - 1] : null);

  // Welcher Bereich in den Vorhaben offen ist, steht in der URL: Ein Link auf
  // ein einzelnes Vorhaben soll teilbar sein, und der Zurück-Knopf des
  // Browsers soll ihn schließen. Query-Parameter statt Route-Segment, weil der
  // Export (Capacitor) keine dynamischen Segmente kennt.
  const router = useRouter();
  const params = useSearchParams();
  const gewaehlterBereich = Number(params.get("area")) || null;
  const setBereich = (thhNr: number | null) => {
    const q = new URLSearchParams(params.toString());
    if (thhNr == null) q.delete("area");
    else q.set("area", String(thhNr));
    const s = q.toString();
    router.replace(s ? `/haushalt/investitionen?${s}` : "/haushalt/investitionen",
                   { scroll: false });
  };
  const programmJahr = passenderJahrgang(programm?.jahre ?? [], aktJahr);

  const zeilen = useMemo(
    () => (aktJahr != null ? teilhaushalte(data, aktJahr) : []),
    [data, aktJahr],
  );
  const gesamt = aktJahr != null ? gesamtJahr(data, aktJahr) : null;
  const bezug = aktJahr != null ? finanzhaushaltJahr(data, aktJahr) : null;
  const anteil = aktJahr != null ? investitionsAnteil(data, aktJahr) : null;
  const uebrig = netto(gesamt);

  // Der Vorhaben-Explorer unter dieser Rangliste braucht weiterhin einen
  // Farbschlüssel für seine Kachelfläche. Die Rangliste selbst verwendet
  // bewusst nur eine Farbe: Dort bedeutet die Balkenlänge bereits die Höhe
  // der Auszahlung, eine zweite Farbcodierung würde nichts hinzufügen.
  //
  // Die STUFE wird dem Explorer mitgegeben, nicht nur das fertige Token: Die
  // Kachelfläche schreibt Text auf ihre Flächen, und ob der hell oder dunkel
  // sein muss, hängt genau an dieser Zahl (`grafik/kachelflaeche.ts`,
  // `rampenText`).
  const stufe = useMemo(() => {
    const zu = new Map<number, number>();
    zeilen.forEach((z, i) => zu.set(z.sub_budget_no, Math.min(i, 9)));
    return (thhNr: number) => zu.get(thhNr) ?? 9;
  }, [zeilen]);
  const farbe = useMemo(
    () => (thhNr: number) => `var(--hh-aus-${stufe(thhNr)})`, [stufe]);

  const skala = zeilen.length ? zeilen[0].outflows : 0;
  const h = herkunftVon(data, gesamt?.herkunft_id);
  const hBezug = herkunftVon(data, bezug?.herkunft_id);
  const zeitreihe = series(data);

  if (loading) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Investitionen werden geladen …
      </div>
    );
  }

  if (!data || !jahre.length || aktJahr == null || !gesamt) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Was gebaut wird</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Für die Investitionen liegt noch kein Jahrgang vor.
        </p>
      </div>
    );
  }

  const ausMio = mio(gesamt.outflows);
  const einMio = mio(gesamt.inflows);

  return (
      <div className="flex flex-col gap-4">
        <header className="flex flex-col gap-2">
          <h2 className="font-display text-xl font-bold leading-tight tracking-tight sm:text-[22px]">
            Was baut und kauft die Stadt?
          </h2>
          <p className="max-w-[70ch] text-[13.5px] leading-relaxed text-foreground/90">
            Die übrigen Haushaltsseiten zeigen vor allem den laufenden Betrieb:
            Personal, Zuschüsse, Energie oder Mieten. Neubauten, Fahrzeuge und
            Grundstücke werden dagegen im Finanzhaushalt geplant. Diese Seite zeigt
            diesen Teil des Haushalts.
          </p>
        </header>

        {/* Die Anzeigetafel: eine Zahl, um die es geht. Zur Farb- und
            Rampenbindung siehe `.hh-tafel` in app/globals.css. */}
        <section className="hh-tafel rounded-2xl p-4 sm:p-5">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Geplante Investitionen {aktJahr}
          </p>
          <div className="mt-2 flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="font-display text-[34px] font-bold leading-none tracking-tight tabular-nums sm:text-[42px]">
                {deMio(ausMio)}
                <span className="ml-2 text-[15px] font-semibold text-muted-foreground">
                  Mio. €
                </span>
              </p>
              <p className="mt-1.5 text-[11.5px] leading-none text-muted-foreground">
                Auszahlungen<Beleg q="investitionen" />
              </p>
            </div>
            <div>
              <p className="font-display text-[21px] font-bold leading-none tracking-tight tabular-nums">
                {deMio(einMio)}
                <span className="ml-1.5 text-[11px] font-semibold text-muted-foreground">
                  Mio. €
                </span>
              </p>
              <p className="mt-1.5 text-[11.5px] leading-none text-muted-foreground">
                Einzahlungen
              </p>
            </div>
            <div>
              <p className="font-display text-[21px] font-bold leading-none tracking-tight tabular-nums">
                {deMio(mio(uebrig))}
                <span className="ml-1.5 text-[11px] font-semibold text-muted-foreground">
                  Mio. €
                </span>
              </p>
              <p className="mt-1.5 text-[11.5px] leading-none text-muted-foreground">
                bleiben an der Stadt
              </p>
            </div>
          </div>

          {/* Die Einordnung, ohne die die große Zahl nichts bedeutet — und
              ausdrücklich als UNSERE Rechnung gekennzeichnet. */}
          {anteil != null && bezug && (
            <p className="mt-3.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Der ganze Finanzhaushalt {aktJahr} umfasst{" "}
              <strong className="font-semibold text-foreground/90">
                {deMio(mio(bezug.outflows))} Mio. €
              </strong>{" "}
              Auszahlungen — Investitionen sind davon{" "}
              <strong className="font-semibold text-foreground/90">
                {anteil.toLocaleString("de-DE", { maximumFractionDigits: 1 })} %
              </strong>
              . Der Anteil ist unsere Rechnung; die beiden Beträge stehen so in der Quelle.
            </p>
          )}

          {jahre.length > 1 && (
            <div className="mt-5 flex justify-end border-t border-border pt-4">
              <Segmented
                value={String(aktJahr)}
                onChange={(v) => setJahr(Number(v))}
                options={jahre.map((j) => ({ value: String(j), label: String(j) }))}
              />
            </div>
          )}
        </section>

        <LottiErklaert
          titel="Zwei Haushalte, nicht einer"
          text={
            "Ergebnis- und Finanzhaushalt betrachten dieselbe Tätigkeit aus zwei Perspektiven. " +
            "Im Ergebnishaushalt stehen die laufenden Aufwendungen eines Jahres, etwa Löhne, " +
            "Strom und Zuschüsse. Der Finanzhaushalt erfasst Ein- und Auszahlungen, darunter " +
            "auch Investitionen in Gebäude, Fahrzeuge oder Grundstücke. Ein Neubau verursacht " +
            "dort während der Bauzeit Auszahlungen; im Ergebnishaushalt erscheint sein " +
            "Werteverzehr später über jährliche Abschreibungen."
          }
        />

        <section
          id={ANKER_BEREICHE}
          className="scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-display text-[15.5px] font-bold tracking-tight">
              Geplante Auszahlungen nach Bereich
            </h2>
            <span className="font-mono text-[9.5px] uppercase tracking-[0.11em] text-muted-foreground">
              {zeilen.length} Teilhaushalte · {aktJahr}
            </span>
          </div>

          <div className="mt-3.5 rounded-xl bg-muted/45 px-3.5 py-3 text-[11.5px] leading-relaxed text-muted-foreground">
            <p>
              <span className="font-semibold text-foreground">So liest du die Grafik:</span>{" "}
              Je länger der blaue Balken, desto höher sind die geplanten
              Auszahlungen. Alle Balken verwenden denselben Maßstab; der größte
              Bereich füllt die ganze Breite aus. Wie viel durch Zuschüsse,
              Verkäufe oder Beiträge gedeckt wird, steht jeweils als Betrag und
              Anteil darunter.
            </p>
          </div>

          <ul className="mt-2 divide-y divide-[color:var(--border)]">
            {zeilen.map((z) => (
              <Rang
                key={z.sub_budget_no}
                zeile={z}
                skala={skala}
                vorhandene={programmJahr != null
                  ? count(programm, programmJahr, z.sub_budget_no) : 0}
                aufVorhaben={(nr) => {
                  setBereich(nr);
                  document.getElementById("vorhaben")
                    ?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              />
            ))}
          </ul>

          <p className="mt-3.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Die Bereiche heißen im Haushalt „Teilhaushalte“ — dieselbe Einteilung
            wie unter{" "}
            <Link href="/haushalt/bereiche" className="text-primary hover:underline">
              Was steckt hinter den Namen?
            </Link>
            . Hohe Investitionsauszahlungen bedeuten zunächst nur, dass in diesem
            Bereich größere Anschaffungen oder Baumaßnahmen geplant sind.
          </p>
          {/* Dieselbe Falle wie bei den Erträgen auf /haushalt (dort steht sie
              in `BEREICH_TEXTE.finanzen`): Ein Teilhaushalt ist der Ort, an dem
              gebucht wird — nicht zwingend der, an dem gebaut wird. Bei der
              zentralen Finanzwirtschaft ist der Unterschied am größten, und
              genau die steht hier oft weit oben. Was dort im Einzelnen liegt,
              sagt der Datensatz nicht, und wir behaupten es auch nicht. */}
          <p className="mt-2 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Ein Teilhaushalt ist dabei der Ort, an dem gebucht wird — nicht immer
            der, an dem gebaut wird. Bei „Finanzmanagement und Recht" verbucht die
            Kämmerei auch, was der ganzen Stadt zugutekommt. Wie sich eine solche
            Summe im Einzelnen zusammensetzt, sagt dieser Datensatz nicht.
          </p>

          <div className="mt-4">
            <Fundstelle h={h} />
          </div>
        </section>

        {programmJahr != null && (
          <Vorhaben
            daten={programm}
            year={programmJahr}
            gewaehlt={gewaehlterBereich}
            aufWaehlen={setBereich}
            zurueckAnker={ANKER_BEREICHE}
            // Derselbe Farbschlüssel wie im Überblicksbalken oben — die
            // Kachelfläche des Explorers und die Rangliste je Bereich sollen
            // denselben Teilhaushalt in derselben Rampenstufe zeigen.
            farbeVonThh={farbe}
            stufeVonThh={stufe}
          />
        )}

        {zeitreihe.length > 1 && (
          <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
            <h2 className="font-display text-[15.5px] font-bold tracking-tight">
              Über die Jahre
            </h2>
            <p className="mt-1 max-w-[86ch] text-[12.5px] leading-relaxed text-foreground/90">
              Was die Stadt sich in den einzelnen Jahren vorgenommen hat. Jede Zahl
              ist der Plan dieses Jahres, nicht das, was am Ende daraus wurde.
            </p>
            <ul className="mt-3.5 flex flex-col gap-2">
              {zeitreihe.map((z) => {
                const groesste = Math.max(...zeitreihe.map((x) => x.outflows));
                const breite = groesste > 0 ? (z.outflows / groesste) * 100 : 0;
                return (
                  <li key={z.year} className="flex items-center gap-3">
                    <span className={cn(
                      "w-10 flex-none font-mono text-[11px] tabular-nums",
                      z.year === aktJahr ? "font-semibold text-foreground" : "text-muted-foreground",
                    )}>
                      {z.year}
                    </span>
                    <span className="h-3 flex-1 overflow-hidden rounded-sm bg-muted/60">
                      <span
                        className="block h-full rounded-sm"
                        style={{
                          width: `${breite}%`,
                          background: z.year === aktJahr
                            ? "var(--hh-aus-0)" : "var(--hh-aus-3)",
                        }}
                      />
                    </span>
                    <span className="w-20 flex-none text-right font-display text-[13px] font-bold tabular-nums">
                      {deMio(mio(z.outflows))}
                      <span className="ml-1 text-[9.5px] font-medium text-muted-foreground">
                        Mio.&nbsp;€
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Der Block, der nicht ans Ende gehört. */}
        <section className="rounded-2xl border border-dashed border-border bg-muted/25 p-4 sm:p-5">
          <h2 className="font-display text-[15.5px] font-bold tracking-tight">
            Was diese Zahlen nicht sagen
          </h2>
          <ul className="mt-2.5 flex list-disc flex-col gap-2 pl-4 text-[12.5px] leading-relaxed text-foreground/90">
            <li>
              <strong className="font-semibold text-foreground">
                Schulgebäude stehen nicht im Investitionsprogramm.
              </strong>{" "}
              Der Bereich „Schule und Bildung" führt Ausstattung — Hardware,
              Software, Einrichtung — und die berufsbildenden Schulen mit Namen.
              Sanierung und Neubau der Schulgebäude verantwortet der
              Eigenbetrieb Gebäudewirtschaft und Hochbau; der hat einen eigenen
              Wirtschaftsplan, den dieser Haushalt nur erwähnt. Ob eine
              bestimmte Schule saniert wird, ist deshalb auch hier nicht
              beantwortet — was der Rat dazu beschlossen hat, findest du über
              die{" "}
              <Link href="/suche" className="text-primary hover:underline">Suche</Link>{" "}
              in den Beschlüssen.
            </li>
            <li>
              <strong className="font-semibold text-foreground">
                Die beiden Summen auf dieser Seite zählen Verschiedenes.
              </strong>{" "}
              Oben stehen die Zahlungen eines Jahres aus dem Finanzhaushalt,
              unten die Gesamtkosten der einzelnen Vorhaben über alle Jahre. Sie
              müssen sich nicht decken und tun es auch nicht — der Haushaltsplan
              schreibt selbst dazu, dass Eigenleistungen ins
              Investitionsprogramm gehören, aber nicht in den Finanzhaushalt,
              weil kein Geld dafür fließt.
            </li>
            <li>
              <strong className="font-semibold text-foreground">
                Gezeigt werden Planwerte.
              </strong>{" "}
              Der Datensatz zeigt nicht, was am Jahresende tatsächlich gebaut oder
              bezahlt wurde. Investitionen können sich verschieben, etwa wenn
              Planungen länger dauern, Vergaben scheitern oder Vorhaben erst im
              Folgejahr umgesetzt werden.
            </li>
            <li>
              <strong className="font-semibold text-foreground">
                Die Zahlen enden {jahre[jahre.length - 1]}.
              </strong>{" "}
              Die Stadt stellt diesen Datensatz erst im Jahr nach dem
              Haushaltsjahr ins Open-Data-Portal. Für das laufende Jahr gibt es
              ihn dort noch nicht — im{" "}
              <Link href="/haushalt" className="text-primary hover:underline">
                Datenstand
              </Link>{" "}
              steht, wann der nächste Jahrgang erwartet wird.
            </li>
          </ul>
          {hBezug && (
            <p className="mt-3 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Zum Gesamtbetrag des Finanzhaushalts: {hBezug.citation}
            </p>
          )}
        </section>

      </div>
  );
}
