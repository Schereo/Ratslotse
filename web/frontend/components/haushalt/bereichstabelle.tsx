"use client";

// Die Bereiche des Haushalts als Tabelle (Entwürfe H2-01 unten und H2-03).
//
// Ersetzt die Karten-Kacheln der ersten Fassung. Der Gewinn ist nicht Platz,
// sondern Vergleichbarkeit: Jede Zeile zeigt in EINEM Balken, wie sich die
// Ausgaben eines Bereichs zusammensetzen — der dunkle Teil zeigt den
// Zuschussbedarf aus dem allgemeinen Haushalt, der helle die direkt im Bereich
// verbuchten Erträge. So wird
// ohne Fußnote sichtbar, dass der längste Balken nicht der ist, der die Stadt
// am meisten kostet.
//
// Vier Entscheidungen, die man beim Weiterbauen kennen muss:
//
//  1. **Alle Balken hängen an EINER Skala** (dem größten Bereich), nicht
//     zeilenweise an 100 %. Zeilenweise skaliert wären alle gleich lang und
//     der Vergleich, um den es geht, wäre weg.
//  2. **Der helle Teil heißt „nimmt der Bereich selbst ein", nicht „von Bund,
//     Land oder über Gebühren".** Für Planjahre lässt sich die Herkunft nicht
//     belegen: `council_haushalt` kennt je Bereich nur eine Ertragssumme, die
//     Aufschlüsselung nach Arten endet mit dem Jahresabschluss 2024. Und auch
//     der dunkle Teil ist nicht rein städtisch — rund ein Fünftel des
//     allgemeinen Topfes sind Schlüsselzuweisungen des Landes.
//  3. **Welche Bereiche fehlen, wird gerechnet, nicht geschrieben.** Ein
//     Bereich, der mit Überschuss abschließt, hat keinen Zuschussbedarf und
//     steht deshalb nicht in der Liste. Das sind je nach Jahrgang ein oder
//     zwei — „zwei Bereiche fehlen" als fester Satz wäre für 2023 und 2025
//     falsch.
//  4. **Der Topf-Satz nennt die Lücke mit.** „Finanzmanagement und Recht ist
//     der Topf, aus dem die anderen bezahlt werden" stimmt nur halb: Der
//     Überschuss deckt den Zuschussbedarf der übrigen Bereiche gerade NICHT,
//     und die Differenz ist exakt das geplante Minus des Jahres.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import { Segmented } from "@/components/ui";
import { Beleg } from "@/components/haushalt/quelle";
import { bereichKanon } from "@/lib/haushalt-bereiche";
import { HaushaltZeile, bereichSlug, bereiche, deMio, mio } from "@/lib/haushalt";
import { cn } from "@/lib/utils";

type Sortierung = "stadt" | "gesamt";

type Zeile = {
  /** Rohname aus der Datenbank — Slug, Link und Sortierung hängen daran. */
  roh: string;
  name: string;
  klartext: string | null;
  /** Ausgaben des Bereichs (Aufwendungen). */
  gesamt: number;
  /** Zuschussbedarf: Ausgaben minus eigene Erträge. */
  stadt: number;
  /** Eigene Erträge des Bereichs. */
  eigen: number;
};

/** Zwei Balkenstücke auf gemeinsamer Skala: dunkel = aus dem allgemeinen
 *  Topf, hell = eigene Erträge. Zusammen sind sie die Ausgaben des Bereichs.
 *
 *  Bewusst NICHT `components/haushalt/anteilsbalken.tsx`: Der schreibt seinen
 *  Nenner und eine Legende an jeden Balken, weil er einzeln steht. Hier stehen
 *  dreizehn Balken untereinander an einer gemeinsamen Skala — dieselbe
 *  Beschriftung dreizehnmal wäre Lärm, der Nenner steht in der Kopfzeile. */
function Zusammensetzungsbalken({ stadt, eigen, skala }: {
  stadt: number; eigen: number; skala: number;
}) {
  const b = (v: number) => `${Math.max((v / skala) * 100, 0)}%`;
  return (
    <span className="flex h-3.5 w-full items-center gap-[1.5px]" aria-hidden="true">
      <span className="h-full rounded-l-[3px]" style={{ width: b(stadt), background: "var(--hh-ein-0)" }} />
      <span className="h-full rounded-r-[3px]" style={{ width: b(eigen), background: "var(--hh-ein-3)" }} />
    </span>
  );
}

/** „Mio. €" an der Zahl — nur dort, wo der Spaltenkopf fehlt (unter sm).
 *  Ohne diese Zeile stünde auf dem Handy eine nackte Zahl ohne Einheit. */
function Einheit() {
  return (
    <span className="ml-0.5 text-[10px] font-medium text-muted-foreground sm:hidden">
      Mio.&nbsp;€
    </span>
  );
}

function Kopf() {
  return (
    <div className="hidden grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_64px_64px_14px] gap-x-3.5 pb-2 sm:grid">
      {["Bereich · enthaltene Aufgaben", "Finanzierung", "Zuschuss", "Ausgaben"].map((t, i) => (
        <span key={t} className={cn(
          "font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground",
          i >= 2 && "text-right",
        )}>
          {t}
          {/* Die Einheit steht in einer zweiten Zeile, nicht hinter dem Wort:
              Die Zahlenspalten sind 64 px breit, „Stadt Mio. €" liefe darüber
              hinaus. Auf schmalen Bildschirmen fehlt dieser Kopf ganz —
              dort trägt jede Zahl die Einheit selbst. */}
          {i >= 2 && <span className="block normal-case">Mio.&nbsp;€</span>}
        </span>
      ))}
      <span />
    </div>
  );
}

function Reihe({ z, skala }: { z: Zeile; skala: number }) {
  return (
    <Link
      href={`/haushalt/bereich?name=${bereichSlug(z.roh)}`}
      className="grid grid-cols-1 gap-2 border-t border-border py-3 text-[12.5px] transition-colors hover:bg-accent/60 sm:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_64px_64px_14px] sm:items-center sm:gap-x-3.5 sm:gap-y-0"
    >
      <span className="min-w-0">
        <span className="block font-semibold leading-snug">{z.name}</span>
        {z.klartext && (
          <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">{z.klartext}</span>
        )}
      </span>
      <span className="flex items-center">
        <Zusammensetzungsbalken stadt={z.stadt} eigen={z.eigen} skala={skala} />
      </span>
      <span className="flex items-baseline justify-between gap-4 sm:contents">
        <span className="tabular-nums sm:text-right">
          <span className="mr-1.5 font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground sm:hidden">Zuschuss</span>
          <span className="font-semibold">{deMio(z.stadt)}<Einheit /></span>
        </span>
        <span className="tabular-nums text-muted-foreground sm:text-right">
          <span className="mr-1.5 font-mono text-[9.5px] uppercase tracking-[0.09em] sm:hidden">Ausgaben</span>
          {deMio(z.gesamt)}<Einheit />
        </span>
      </span>
      <span className="hidden justify-self-end sm:block">
        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
      </span>
    </Link>
  );
}

/** Ein Grund, warum die hellen Teile so verschieden groß sind — Text, keine
 *  Zahl: Der Haushaltsplan weist die Aufteilung auf dieser Ebene nicht aus. */
function Grund({ titel, text }: { titel: string; text: string }) {
  return (
    <div className="border-t border-border pt-2.5 first:border-t-0 first:pt-0">
      <p className="text-[12.5px] font-semibold">{titel}</p>
      <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

export function Bereichstabelle({ zeilen, year }: { zeilen: HaushaltZeile[]; year: number }) {
  const [sortierung, setSortierung] = useState<Sortierung>("stadt");
  const [alle, setAlle] = useState(false);

  const { traeger, ueberschuss, bedarfSumme, topfSumme, luecke } = useMemo(() => {
    const teile = bereiche(zeilen);
    const traeger: Zeile[] = [];
    const ueberschuss: (Zeile & { plus: number })[] = [];
    let bedarfRoh = 0;
    let topfRoh = 0;
    for (const z of teile) {
      const kanon = bereichKanon(z.bereich);
      const gesamt = mio(z.expenses) ?? 0;
      const eigenRoh = z.revenues ?? 0;
      const result = z.result ?? 0;
      const basis: Zeile = {
        roh: z.bereich,
        name: kanon.name,
        klartext: kanon.klartext,
        gesamt,
        stadt: mio(-result) ?? 0,
        eigen: mio(eigenRoh) ?? 0,
      };
      if (result < 0) {
        bedarfRoh += -result;
        traeger.push(basis);
      } else {
        topfRoh += result;
        ueberschuss.push({ ...basis, plus: mio(result) ?? 0 });
      }
    }
    return {
      traeger,
      ueberschuss,
      bedarfSumme: mio(bedarfRoh) ?? 0,
      topfSumme: mio(topfRoh) ?? 0,
      // Aus den Rohwerten gerundet, nicht aus den beiden gerundeten Summen —
      // sonst wandert die Lücke um einen Zehntel und trifft das Defizit nicht
      // mehr, das sie erklären soll.
      luecke: mio(bedarfRoh - topfRoh) ?? 0,
    };
  }, [zeilen]);

  const sortiert = useMemo(
    () => [...traeger].sort((a, b) => (sortierung === "stadt" ? b.stadt - a.stadt : b.gesamt - a.gesamt)),
    [traeger, sortierung],
  );

  if (!sortiert.length) return null;

  // Eine Skala für alle Balken — der größte Bereich ist 100 %.
  const skala = Math.max(...sortiert.map((z) => z.gesamt), 1);
  const gezeigt = alle ? sortiert : sortiert.slice(0, 5);
  const rest = sortiert.slice(gezeigt.length);
  const restStadt = rest.reduce((s, z) => s + z.stadt, 0);
  const restGesamt = rest.reduce((s, z) => s + z.gesamt, 0);

  // Der Befund der Tabelle, aus den Daten gelesen statt hineingeschrieben:
  // Trägt der größte Ausgabenposten auch die größten Kosten für die Stadt?
  const groessteAusgabe = [...traeger].sort((a, b) => b.gesamt - a.gesamt)[0];
  const groesstenKosten = [...traeger].sort((a, b) => b.stadt - a.stadt)[0];
  const auseinander = groessteAusgabe && groesstenKosten
    && groessteAusgabe.roh !== groesstenKosten.roh;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-5 breit:flex-row breit:items-start breit:gap-7">
        <div className="min-w-0 flex-1">
          <h2 className="max-w-[46ch] text-[17px] font-bold leading-snug tracking-tight sm:text-[20px]">
            {auseinander
              ? "Hohe Ausgaben bedeuten nicht automatisch einen hohen Zuschussbedarf"
              : `Die ${traeger.length + ueberschuss.length} Bereiche im Überblick`}
          </h2>
          <p className="mt-2 max-w-[74ch] text-[13px] leading-relaxed text-foreground/85">
            Die Länge jedes Balkens zeigt die geplanten Ausgaben eines Bereichs. Der{" "}
            <strong className="font-semibold">dunkle Teil</strong> ist der Zuschussbedarf aus
            dem allgemeinen Haushalt. Der <strong className="font-semibold">helle Teil</strong>{" "}
            zeigt Erträge, die direkt in diesem Bereich verbucht werden. Zusammen ergeben
            beide Teile die geplanten Ausgaben.<Beleg q="plan" />
          </p>

          {/* „REIHENFOLGE" + Verb-Paar statt „nach Kosten für die Stadt": Der
              Umschalter sortiert nur, aber neben der Legende las er sich wie
              ein Ansichts-Wechsel — und „Ausgaben" vs. „Kosten" klang wie
              zweimal dasselbe (Tim, 24.08.). Die Verben tragen den Unterschied
              und sprechen dieselbe Sprache wie die Legende daneben. */}
          <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="shrink-0 font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
                Reihenfolge
              </span>
              <div className="scrollbar-none -mx-1 overflow-x-auto px-1">
                <Segmented className="w-max" value={sortierung} onChange={setSortierung} tone="primary"
                  options={[
                    { value: "stadt", label: "höchster Zuschuss" },
                    { value: "gesamt", label: "höchste Ausgaben" },
                  ]} />
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
              <span className="h-3 w-3 rounded-[3px]" style={{ background: "var(--hh-ein-0)" }} />
              Zuschuss aus dem allgemeinen Haushalt
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
              <span className="h-3 w-3 rounded-[3px]" style={{ background: "var(--hh-ein-3)" }} />
              im Bereich verbuchte Erträge
            </span>
          </div>

          <div className="mt-3.5">
            <Kopf />
            {gezeigt.map((z) => <Reihe key={z.roh} z={z} skala={skala} />)}
            {rest.length > 0 && (
              <button type="button" onClick={() => setAlle(true)}
                className="grid w-full grid-cols-1 gap-2 border-t border-border py-3 text-left text-[12.5px] text-muted-foreground transition-colors hover:bg-accent/60 sm:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_64px_64px_14px] sm:items-center sm:gap-x-3.5 sm:gap-y-0">
                <span className="min-w-0">
                  <span className="block font-semibold leading-snug text-foreground">
                    {rest.length} weitere {rest.length === 1 ? "Bereich" : "Bereiche"}
                  </span>
                  <span className="mt-0.5 block truncate text-[11.5px] leading-snug">
                    {rest.map((z) => z.name).join(" · ")}
                  </span>
                </span>
                <span className="hidden sm:block" />
                <span className="flex items-baseline justify-between gap-4 sm:contents">
                  <span className="tabular-nums sm:text-right">
                    <span className="mr-1.5 font-mono text-[9.5px] uppercase tracking-[0.09em] sm:hidden">Zuschuss</span>
                    {deMio(restStadt)}<Einheit />
                  </span>
                  <span className="tabular-nums sm:text-right">
                    <span className="mr-1.5 font-mono text-[9.5px] uppercase tracking-[0.09em] sm:hidden">Ausgaben</span>
                    {deMio(restGesamt)}<Einheit />
                  </span>
                </span>
                <span className="hidden justify-self-end sm:block">
                  <ChevronDown className="h-3.5 w-3.5" />
                </span>
              </button>
            )}
            {alle && sortiert.length > 5 && (
              <button type="button" onClick={() => setAlle(false)}
                className="mt-2.5 text-xs font-semibold text-primary">
                Weniger anzeigen
              </button>
            )}
          </div>

          {ueberschuss.length > 0 && (
            <div className="mt-3.5 flex items-start gap-3 border-t border-dashed border-border pt-3">
              <span className="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-primary/10">
                <Info className="h-3 w-3 text-primary" />
              </span>
              <p className="text-[12px] leading-relaxed text-muted-foreground">
                {ueberschuss.length === 1 ? "Ein Bereich wird" : `${ueberschuss.length} Bereiche werden`} in
                der Zuschussliste nicht aufgeführt, weil die dort verbuchten Erträge mindestens
                so hoch sind wie die Ausgaben:{" "}
                {/* Als Klammerzusatz und nicht als Satz mit Verb: Ein Bereich
                    heißt „nicht rechtsfähige Stiftungen", der nächste
                    „Finanzmanagement und Recht" — jede Vorlage mit Prädikat
                    wäre bei einem der beiden grammatisch falsch. */}
                {ueberschuss.map((z, i) => (
                  <span key={z.roh}>
                    {i > 0 && (i === ueberschuss.length - 1 ? " und " : ", ")}
                    <strong className="font-semibold text-foreground/90">{z.name}</strong>{" "}
                    (Ausgaben {deMio(z.gesamt)}&#8239;Mio.&nbsp;€, verbuchte Erträge {deMio(z.eigen)}&#8239;Mio.&nbsp;€,
                    Überschuss {deMio(z.plus)}&#8239;Mio.&nbsp;€)
                  </span>
                ))}
                .{" "}
                {/* Der Halbsatz „der Topf, aus dem die anderen bezahlt werden" ist
                    für sich genommen irreführend: Er weckt den Eindruck, es gehe
                    auf. Es geht nicht auf — und die Lücke ist genau das Minus. */}
                Zusammen ergeben diese Bereiche einen Überschuss von {deMio(topfSumme)}&#8239;Mio.&nbsp;€.
                In der Haushaltsrechnung gleicht er den Zuschussbedarf der übrigen Bereiche aus.{" "}
                {luecke > 0 ? (
                  <>
                    Deren Zuschussbedarf beträgt {deMio(bedarfSumme)}&#8239;Mio.&nbsp;€ und ist damit
                    {" "}{deMio(luecke)}&#8239;Mio.&nbsp;€ höher. Diese Differenz entspricht dem für
                    {" "}{year} geplanten Minus.
                  </>
                ) : (
                  <>
                    Deren Zuschussbedarf beträgt {deMio(bedarfSumme)}&#8239;Mio.&nbsp;€ und ist damit
                    {" "}{deMio(-luecke)}&#8239;Mio.&nbsp;€ niedriger. Diese Differenz entspricht dem
                    für {year} geplanten Überschuss.
                  </>
                )}
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 breit:w-[320px] breit:flex-none">
          {auseinander && (
            <div className="rounded-xl border border-signal/30 bg-signal/[0.06] p-3.5">
              <p className="text-[12.5px] leading-relaxed text-foreground/90">
                <strong className="font-semibold">{groessteAusgabe.name} plant die höchsten
                  Ausgaben, {groesstenKosten.name} benötigt den höchsten Zuschuss.</strong>{" "}
                {/* Absolut formuliert, nicht als Quote: Ein Prozentwert wäre
                    hier ein Maßstab, den es nicht gibt — kein Bereich soll
                    sich selbst finanzieren. */}
                {groessteAusgabe.name} plant {deMio(groessteAusgabe.gesamt)}&#8239;Mio.&nbsp;€ Ausgaben
                und {deMio(groessteAusgabe.eigen)}&#8239;Mio.&nbsp;€ eigene Erträge.{" "}
                {groesstenKosten.name} plant {deMio(groesstenKosten.gesamt)}&#8239;Mio.&nbsp;€ Ausgaben
                und {deMio(groesstenKosten.eigen)}&#8239;Mio.&nbsp;€ eigene Erträge. Trotz niedrigerer
                Gesamtausgaben ist dort deshalb mehr Geld aus dem allgemeinen Haushalt nötig.
              </p>
            </div>
          )}

          <div className="rounded-xl border border-border p-3.5">
            <p className="text-[13px] font-bold">Warum die hellen Teile so verschieden groß sind</p>
            <div className="mt-2.5 flex flex-col gap-2.5">
              <Grund titel="Das Gesetz sieht Erstattungen vor"
                text="Bei vielen Sozialleistungen zahlt die Stadt zunächst aus. Bund und Land erstatten anschließend einen Teil der Kosten." />
              <Grund titel="Für manche Leistungen erhebt die Stadt Gebühren"
                text="Das gilt etwa für Müllentsorgung, Friedhöfe und teilweise für Kitas. Die Gebühren sind an die jeweilige Leistung gebunden und dürfen grundsätzlich nicht über deren Kosten hinausgehen." />
              <Grund titel="Viele Aufgaben haben keine direkten Erträge"
                text="Straßen, Grünflächen, Feuerwehr oder Bibliotheken werden überwiegend aus allgemeinen Einnahmen finanziert. Ihr Balken ist deshalb fast vollständig dunkel." />
            </div>
          </div>

          <div className="rounded-xl border border-border bg-muted/40 p-3.5">
            <p className="text-[12px] leading-relaxed text-foreground/90">
              <strong className="font-semibold">Ein hoher Anteil eigener Erträge ist keine
                Bewertung der Leistung.</strong> Viele kommunale Aufgaben sollen gerade nicht
              über individuelle Zahlungen finanziert werden. Die Balken zeigen die
              Finanzierungsstruktur, nicht die Qualität der Arbeit eines Bereichs.
            </p>
          </div>

          <p className="border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
            „Zuschuss“ bezeichnet den Betrag, der nach Abzug der im Bereich verbuchten
            Erträge von seinen Aufwendungen übrig bleibt. Wie sich diese Erträge auf
            Erstattungen, Gebühren und Zuwendungen verteilen, weist der Haushaltsplan auf
            dieser Ebene nicht getrennt aus. Deshalb erklären wir die möglichen Gründe,
            nennen dafür aber keine unbelegten Anteile.<Beleg q="plan" />
          </p>
        </div>
      </div>
    </div>
  );
}
