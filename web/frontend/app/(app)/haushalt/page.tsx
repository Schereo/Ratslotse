"use client";

// /haushalt — Stadtfinanzen-Übersicht (Entwürfe H2-01 Desktop, H2-11 mobil,
// H2-12 dunkel; die Bereichstabelle ist H2-03).
//
// Leserichtung: Jahr wählen → Anzeigetafel mit der Kernzahl und dem
// Kern-Visual (Gegenbalken, umschaltbar auf die 100-Euro-Ansicht) → was der
// Haushalt überhaupt ist → der große Weg durch die Unterseiten → der
// Kassenzettel pro Kopf samt Ersparten (die eigentliche Story) → Bereiche als
// Tabelle → woher das Geld kommt (Flussbild) → Zeitreihe. Jede Karte trägt
// ihre Quelle.
//
// Drei Dinge, die hier bewusst NICHT stehen:
//
//  * **Kein zweiter Seitentitel über der Tafel.** Die Kernzahl IST die
//    Überschrift (`<h1>` in `tafel.tsx`); ein „Wohin fließt das Geld der
//    Stadt?" darüber wäre eine zweite Überschrift für dieselbe Sache.
//  * **Keine drei Kernzahl-Karten mehr.** Ein­nahmen, Ausgaben und Differenz
//    stehen auf der Tafel neben der großen Zahl — als Karten daneben nannte
//    die Seite dieselben drei Zahlen zweimal.
//  * **Kein `LottiVergleich` und kein eigener Rücklagen-Hinweis mehr.** Beide
//    standen bis 08/2026 hier und sagten zusammen mit dem Kassenzettel
//    dieselbe Pro-Kopf-Zahl dreimal. Der Zettel (`kassenzettel.tsx`) hat sie
//    abgelöst und trägt beides: die Division und die Reichweite des Ersparten.
//    Er läuft nur fürs jüngste Planjahr — `council_einwohner` endet mit dem
//    Haushaltsjahr 2025, und den Plan von 2020 durch die Einwohnerzahl von
//    2025 zu teilen wäre ein stiller Fehler von rund 4 %.

import { useEffect, useMemo, useRef, useState } from "react";
import { Segmented } from "@/components/ui";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/source";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Wegweiser } from "@/components/haushalt/wegweiser";
import { Datenstand } from "@/components/haushalt/datenstand";
import { useFetch } from "@/lib/use-fetch";
import { Tafel } from "@/components/haushalt/tafel";
import { VollzugKarte } from "@/components/haushalt/vollzug";
import { berichteUrls, type VollzugDaten } from "@/lib/haushalt-vollzug";
import { Bereichstabelle } from "@/components/haushalt/bereichstabelle";
import { Gegenbalken } from "@/components/haushalt/gegenbalken";
import { Flussbild, flussbildQuellen } from "@/components/haushalt/flussbild";
import { Kassenzettel, kassenzettelQuellen } from "@/components/haushalt/kassenzettel";
import { Steuereuro } from "@/components/haushalt/steuereuro";
import { Zeitreihe } from "@/components/haushalt/zeitreihe";
import { NahtSaeulen, type NahtJahr } from "@/components/grafik/naht-saeulen";
import {
  AUSGABEN_QUELLE_LABEL, HaushaltAuswahl, haushaltUrl,
  ausgabenKonflikte, expense_series,
  deMio, fehlendeJahre, flussJahre, jahreSortiert, mio, quellenLabel, summe,
} from "@/lib/haushalt";

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
const FELDER = ["years", "expense_series", "income_statement", "population",
  // Die Ertragsarten der Planjahre — für Jahre ohne Jahresabschluss die
  // einzige Seite, die das Flussbild zeigen kann (Posten 01–11, `ansatz`).
  "income_budget", "reserves"] as const;

export default function HaushaltPage() {
  // Nur den Aufwands-Posten je Teilhaushalt: Das Flussbild zeichnet rechts
  // genau ihn. Die volle Ebene wären 795 statt 178 KB — bei identischem Bild.
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER, "20"));
  // Der jüngste Zwischenstand des laufenden Jahres — nur die Summenzeilen,
  // die Übersicht braucht die Teilhaushalte nicht (Endpunkt ohne Jahrgang).
  const vollzug = useFetch<VollzugDaten>("/council/budget/execution");
  // Der Bericht der Zwischenstand-Karte, einzeln nummeriert — die Karte
  // zeigt den jüngsten Stichtag, egal welches Planjahr oben gewählt ist.
  const jeDokument = useMemo(() => {
    const d = vollzug.data;
    const j = d?.reporting_dates.at(-1)?.budget_year;
    const urls = d && j ? berichteUrls(d, j) : [];
    return urls.length ? { budget_execution: urls } : {};
  }, [vollzug.data]);
  const years = useMemo(() => (data ? jahreSortiert(data) : []), [data]);
  const [year, setJahr] = useState<number | null>(null);
  const [visual, setVisual] = useState<"balken" | "euro">("balken");
  const jahrLeiste = useRef<HTMLDivElement>(null);

  const aktJahr = year ?? years[years.length - 1] ?? null;
  const zeilen = aktJahr && data ? data.years[String(aktJahr)] ?? [] : [];
  const gesamt = summe(zeilen);
  // Aus Rohwerten gerundet — 883,9 − 812,9 ergäbe 71,0, tatsächlich sind es 71,1.
  const defizit = gesamt?.revenues != null && gesamt?.expenses != null
    ? mio(gesamt.expenses - gesamt.revenues) : null;
  const luecken = fehlendeJahre(years);
  const source = aktJahr ? quellenLabel(zeilen, aktJahr) : null;

  // --- Die lange Reihe (Datensatz 1102) ------------------------------------
  // Alle Jahre mit Betrag, dazwischen die Lücken als Daten (GB-00-Vertrag).
  // Werte in Mio. €, `art` ist der Titel, den die Quelle ihrem Block gibt —
  // daraus wird die Legende, und die nennt damit beide Abgrenzungen beim
  // Namen statt „alt"/„neu".
  const lange = useMemo(() => (data ? expense_series(data) : []), [data]);
  const langeJahre = useMemo<NahtJahr[]>(() => {
    if (!data?.expense_series || lange.length < 2) return [];
    const nach = new Map(lange.map((z) => [z.year, z]));
    const js: NahtJahr[] = [];
    for (let y = lange[0].year; y <= lange[lange.length - 1].year; y++) {
      const z = nach.get(y);
      js.push(z
        ? {
            year: y,
            teile: [{
              art: data.expense_series.accounting_systems[z.accounting_system].title,
              value: z.amount / 1e6,
            }],
          }
        : { year: y, fehlt: "kein Wert in den beiden Veröffentlichungen der Stadt" });
    }
    return js;
  }, [data, lange]);

  // Das gewählte Jahr in die Scrollzeile holen — NUR waagerecht.
  // Sieben Jahre passen auf 375 px nicht nebeneinander, und die Voreinstellung
  // ist das jüngste, also das letzte: Ohne das hier stand beim Öffnen „2020"
  // links und die aktive Pille lag außerhalb des Bildes. `scrollLeft` statt
  // `scrollIntoView`, weil letzteres auch die SEITE scrollt und damit die
  // Anzeigetafel unter die Kopfzeile schieben würde.
  useEffect(() => {
    const leiste = jahrLeiste.current;
    if (!leiste || aktJahr == null) return;
    const pille = leiste.querySelector<HTMLElement>(`[data-year="${aktJahr}"]`);
    if (!pille) return;
    const ziel = pille.offsetLeft - (leiste.clientWidth - pille.offsetWidth) / 2;
    leiste.scrollLeft = Math.max(0, ziel);
  }, [aktJahr]);

  // Anker-Sprung nach dem Laden: Wer mit `#wegweiser` ankommt (der
  // Schritt-Pfad der Schritt-Seiten verlinkt hierher), trifft die Seite noch
  // im Ladezustand — der Browser hat den Anker dann längst aufgegeben, weil
  // es das Ziel nicht gab. Einmal nachspringen, sobald es gerendert ist.
  const angesprungen = useRef(false);
  useEffect(() => {
    if (loading || !data || angesprungen.current || !window.location.hash) return;
    const ziel = document.getElementById(window.location.hash.slice(1));
    if (!ziel) return;
    angesprungen.current = true;
    ziel.scrollIntoView({ block: "start" });
  }, [loading, data]);

  if (loading || !data || !aktJahr) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }

  // Der Kassenzettel braucht die amtliche Einwohnerzahl und läuft nur fürs
  // jüngste Planjahr (Begründung im Kopf dieser Datei).
  const zeigtZettel = aktJahr === years[years.length - 1] && data.population != null;

  // Angemeldet wird nur, was auf DIESER Seite auch zitiert wird — sonst stünde
  // im Verzeichnis ein Beleg für nichts, und die seitenweise Nummerierung
  // zeigte ins Leere. Reihenfolge = Leserichtung der Seite: Tafel, Zettel,
  // Flussbild.
  const quellen: QuellenSchluessel[] = [
    "plan",
    ...(vollzug.data?.reporting_dates.length ? (["budget_execution"] as const) : []),
    ...(zeigtZettel ? kassenzettelQuellen(data, aktJahr) : []),
    ...flussbildQuellen(data, aktJahr),
    ...(langeJahre.length > 0 ? (["expense_series"] as const) : []),
  ];

  // Die lange Reihe: Endpunkte, Naht und die beiden Befunde, die dazugehören.
  // Alles gerechnet, nichts geschrieben — ein fester Satz wäre beim nächsten
  // Jahrgang still falsch (Hausregel des Bereichs).
  const langErster = lange[0] ?? null;
  const langLetzter = lange[lange.length - 1] ?? null;
  const nahtAb = data.expense_series?.naht_ab ?? null;
  const konflikte = ausgabenKonflikte(data);
  // Das jüngste Jahr der Reihe steht hier, bevor sein Jahresabschluss vorliegt
  // — der eigentliche Nebengewinn dieser Quelle. Gemessen an dem, was wir an
  // Abschlüssen haben, nicht an einer Jahreszahl im Code.
  const juengsterAbschluss = Math.max(
    0, ...(data.income_statement ?? []).map((p) => p.year));
  const vorDemAbschluss =
    langLetzter && juengsterAbschluss > 0 && langLetzter.year > juengsterAbschluss
      ? langLetzter.year : null;

  return (
    <Quellenkontext keys={quellen} jeDokument={jeDokument} year={aktJahr}>
    <div className="flex flex-col gap-4">
      {/* Kopf: Jahr-Umschalter und Quelle. Der Titel der Seite steht auf der
          Anzeigetafel — hier oben nur der Kicker, damit klar ist, wo man ist. */}
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-end sm:justify-between sm:gap-5">
        <div className="min-w-0">
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stadtfinanzen Oldenburg
          </p>
          {/* Scrollt statt überzulaufen: Sieben Jahre passen auf 375 px nicht in
              eine Zeile (Tim, 16.08.). Umbrechen zerrisse die Pill-Gruppe,
              deshalb dieselbe Fade-Scrollzeile wie bei den Chips im
              Ratsgespräch — Scrollbalken ausgeblendet. */}
          <div ref={jahrLeiste}
            className="scrollbar-none -mx-1 mt-1.5 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
            <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
              {(() => {
                const alle: number[] = [];
                for (let y = years[0]; y <= years[years.length - 1]; y++) alle.push(y);
                return alle.map((y) =>
                  years.includes(y) ? (
                    <button key={y} type="button" data-year={y} onClick={() => setJahr(y)}
                      className={
                        "rounded-full px-3 py-1 text-[12.5px] " + (y === aktJahr
                          ? "bg-primary font-semibold text-primary-foreground"
                          : "text-foreground/75 hover:bg-accent")
                      }>
                      {y}
                    </button>
                  ) : (
                    <span key={y} title="Für dieses Jahr fehlen uns die Daten"
                      className="rounded-full border border-dashed border-border px-2.5 py-1 text-[12.5px] text-muted-foreground">
                      {y}
                    </span>
                  ));
              })()}
            </div>
          </div>
          {luecken.length > 0 && (
            <span className="mt-1 block text-[11.5px] text-muted-foreground">
              Für {luecken.join(", ")} liegen keine auswertbaren Daten vor. In der Zeitreihe
              bleiben diese Jahre deshalb frei.
            </span>
          )}
        </div>
        {/* Hier stand bis 16.08. ein Knopf „Haushaltsplan als PDF". Er war die
            einzige prominent verlinkte Quelle der Seite und ließ sie deshalb
            wie die einzige aussehen (Tim). Verloren ist nichts: Er trug die
            jahresgenaue PDF-Adresse — genau die zeigt der Beleg „Beschlossener
            Haushaltsplan" im Quellenverzeichnis jetzt selbst, statt wie früher
            auf die Finanz-Übersichtsseite der Stadt. */}
      </div>

      {/* Anzeigetafel (H2-01/H2-11/H2-12): Kernzahl, die drei Summen und das
          Kern-Visual auf einer Fläche, die in beiden Themes dunkel ist. */}
      <Tafel
        zeilen={zeilen}
        year={aktJahr}
        aktuell={aktJahr === years[years.length - 1]}
        aktion={
          <Segmented value={visual} onChange={setVisual} options={[
            { value: "balken", label: "Balken" },
            { value: "euro", label: "100-Euro-Ansicht" },
          ]} />
        }
      >
        {visual === "balken"
          ? <Gegenbalken zeilen={zeilen} year={aktJahr} />
          : <Steuereuro zeilen={zeilen} year={aktJahr} />}
      </Tafel>
      {/* Der Zwischenstand: Was die Verwaltung im laufenden Jahr erwartet,
          in einem Satz — die Brücke vom Plan zur Gegenprobe. */}
      {vollzug.data && vollzug.data.reporting_dates.length > 0 && (
        <VollzugKarte daten={vollzug.data} beleg={(h) => <Beleg q="budget_execution" h={h} />} />
      )}
      {source && (
        <p className="-mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
          Quelle: {source.url
            ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{source.text}</a>
            : source.text} · Ergebnishaushalt, ordentliche Erträge und Aufwendungen ·
          Rundung auf eine Nachkommastelle.
        </p>
      )}

      {/* Lotti erklärt hier zuerst den Begriff und trennt den Plan ausdrücklich
          vom späteren Ergebnis. Die Einwohnerzahl steht erst im Kassenzettel
          darunter, weil sie dort für die Pro-Kopf-Rechnung benötigt wird. */}
      <LottiErklaert
        title="Was ist der Haushalt?"
        text="Der Haushalt ist der Geldplan der Stadt für ein Jahr. Darin schätzt Oldenburg, wie viel Geld hereinkommt, und plant, wie viel für Kitas, Straßen, Feuerwehr und andere Aufgaben zur Verfügung steht. Der Rat beschließt diesen finanziellen Rahmen. Wichtig: Geplant ist noch nicht ausgegeben — was tatsächlich eingenommen und ausgegeben wurde, zeigt später der Jahresabschluss."
      />

      {/* Der Weg ist die zweite Hauptebene des Bereichs, kein Anhang hinter
          Tabellen und Detailgrafiken. Nach Tafel und Begriffserklärung kennt
          man genug, um sich für die geführte Route oder den freien Einstieg
          zu entscheiden. `id`: Der kompakte Schritt-Pfad auf jeder
          Unterseite springt genau hierher. */}
      <div id="wegweiser" className="scroll-mt-20">
        <Wegweiser />
      </div>

      {/* Der Kassenzettel (H2-02): die Kernzahl in einer Einheit, die man
          fühlt — und die Zeile, um die es politisch geht, als letzte des Bons
          („aus dem Ersparten"). */}
      {zeigtZettel && data.population ? (
        <Kassenzettel daten={data} year={aktJahr} population={data.population} />
      ) : defizit != null && defizit > 0 ? (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Abgeschlossenes Haushaltsjahr
          </p>
          <p className="mt-1.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
            Für {aktJahr} plante die Stadt ein Minus von {deMio(defizit)}&#8239;Mio.&nbsp;€.
            Wie das Jahr tatsächlich endete, zeigt der Jahresabschluss. Für dieses Jahr
            liegt er hier noch nicht vor. Deshalb übertragen wir auch den heutigen
            Rücklagenstand nicht rückwirkend auf {aktJahr}.
          </p>
        </div>
      ) : null}

      {/* Die Bereiche als Tabelle (H2-03): löst die untere Hälfte der
          Anzeigetafel auf — welcher Bereich wie viel ausgibt und wie viel
          davon die Stadt selbst trägt. */}
      <Bereichstabelle zeilen={zeilen} year={aktJahr} />

      {/* Flussbild (H-18): Einnahmearten → eine Kasse → Bereiche. Steht NACH
          dem Gegenbalken, weil es dessen linke Seite auflöst: Der Balken zeigt,
          welcher Bereich das Geld verbucht („Finanzmanagement und Recht" —
          dort laufen alle Steuern auf), das Flussbild, woher es kommt. */}
      {flussJahre(data).length > 0 && (
        <>
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
            {/* Die Quellenzeile stand bis 20.08. hier und nannte unbedingt den
                Jahresabschluss — auch dort, wo für ein Planjahr die
                Herkunftsseite aus dem Gesamtergebnishaushalt steht. Sie wohnt
                jetzt in der Komponente, die weiß, was sie gezeichnet hat. */}
            <Flussbild daten={data} year={aktJahr} />
          </div>

          <LottiErklaert
            title="Kann man Einnahmen einzelnen Ausgaben zuordnen?"
            text="Meistens nicht. Steuern und allgemeine Zuweisungen fließen in den Gesamthaushalt, aus dem die Stadt ihre verschiedenen Aufgaben finanziert. Zweckgebundene Zuschüsse und bestimmte Gebühren sind Ausnahmen. Deshalb lässt sich zum Beispiel nicht sagen, dass die Gewerbesteuer unmittelbar die Feuerwehr bezahlt."
          />
        </>
      )}

      {/* Zeitreihe (H-07) */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
        <Zeitreihe daten={data} />
        <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
          Quelle: Beschlossene Haushaltspläne {years[0]}–{years[years.length - 1]}, Stadt Oldenburg · jeweils Planwerte, nicht Jahresabschluss.
        </p>
      </div>

      {/* Die lange Reihe (Datensatz 1102). Sie steht NACH der Plan-Zeitreihe
          und ersetzt sie nicht: Dort geht es um die Schere zwischen geplanten
          Einnahmen und Ausgaben über sieben Jahre, hier um eine einzige
          Größe über 54. Beides in ein Bild zu ziehen hieße, Plan und Ist auf
          einer Achse zu mischen.

          Die Naht 2009/2010 rendert <NahtSaeulen> selbst — samt Farbwechsel,
          Trennlinie und dem Satz darunter. Die Seite kann sie nicht
          wegkürzen, und die Komponente rechnet nichts über sie hinweg. */}
      {langeJahre.length > 0 && langErster && langLetzter && data.expense_series && (
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div>
            <h2 className="max-w-[30ch] font-display text-[19px] font-bold leading-snug tracking-tight">
              Die Ausgaben der Stadt seit {langErster.year}
            </h2>
            <p className="mt-1.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
              Die Veröffentlichungen der Stadt nennen für {langErster.year} insgesamt{" "}
              {deMio(langErster.amount / 1e6)}&#8239;Mio.&nbsp;€ und für {langLetzter.year}{" "}
              {deMio(langLetzter.amount / 1e6)}&#8239;Mio.&nbsp;€ Ausgaben
              <Beleg q="expense_series" />.{" "}
              {nahtAb != null && (
                <>Zwischen {nahtAb - 1} und {nahtAb} wechselte die Stadt ihr
                Rechnungswesen. Die Werte vor und nach diesem Wechsel beruhen deshalb
                auf unterschiedlichen Abgrenzungen.</>
              )}
            </p>
          </div>
          <NahtSaeulen
            years={langeJahre}
            naht={nahtAb != null ? {
              zwischen: [nahtAb - 1, nahtAb],
              text: `Zum 1. Januar ${nahtAb} stellte die Stadt von der `
                + "Kameralistik auf die doppelte Buchführung um. Dadurch änderte "
                + "sich, welche Ausgaben die Statistik erfasst. Werte vor und nach "
                + "dem Wechsel dürfen deshalb nicht zu einer gemeinsamen Entwicklung "
                + "verrechnet werden.",
            } : undefined}
            unit="Mio. €"
            title="Ausgaben der Stadt Oldenburg"
            beleg={<Beleg q="expense_series" />}
          />
          {/* Was links und was rechts gezählt wird — in den Worten der
              Quelle, nicht in unseren. Die Legende der Grafik nennt die
              beiden Titel, hier steht, was dahintersteckt. */}
          {nahtAb != null && (
            <dl className="grid gap-3 border-t border-dashed border-border pt-3 breit:grid-cols-2">
              {([["kameral", `bis ${nahtAb - 1}`],
                 ["doppik", `ab ${nahtAb}`]] as const).map(([r, spanne]) => (
                <div key={r}>
                  <dt className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                    {spanne} · {data.expense_series!.accounting_systems[r].title}
                  </dt>
                  <dd className="mt-1 max-w-[74ch] text-[12px] leading-relaxed text-foreground/80">
                    {data.expense_series!.accounting_systems[r].abgrenzung}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Die Beträge sind nicht inflationsbereinigt. Ein Anstieg kann daher auch auf
            höhere Preise oder Tarifabschlüsse zurückgehen und bedeutet nicht automatisch
            mehr Leistungen. Eine Pro-Kopf-Reihe zeigen wir hier nicht, weil die
            Einwohnerstatistik durch die Zensusjahre 2011 und 2022 methodische Brüche hat.
          </p>
        </section>
      )}

      {/* Die zwei Befunde zur langen Reihe: der Widerspruch zwischen den
          Quellen und das Jahr, das es vor seinem Abschluss gibt. Beides sind
          Eigenschaften der Quelle, keine Selbstauskunft über unsere Arbeit —
          deshalb stehen sie als Inhalt und nicht als Fußnote. */}
      {(konflikte.length > 0 || vorDemAbschluss) && (
        <div className="grid gap-4 breit:grid-cols-2">
          {konflikte.map((k) => (
            <section key={k.year}
              className="rounded-2xl border border-border bg-card p-4 shadow-sm">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Amtliche Quellen widersprechen sich
              </p>
              <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
                Für {k.year} stehen zwei amtliche Gesamtsummen nebeneinander:{" "}
                {AUSGABEN_QUELLE_LABEL[k.source]} nennt {deMio(k.amount / 1e6)}&#8239;Mio.&nbsp;€,{" "}
                {k.conflict_source
                  ? AUSGABEN_QUELLE_LABEL[k.conflict_source]
                  : "die andere Veröffentlichung"}{" "}
                dagegen {deMio((k.conflict_amount ?? 0) / 1e6)}&#8239;Mio.&nbsp;€.
                Das sind rund{" "}
                {deMio(Math.abs((k.conflict_amount ?? 0) - k.amount) / 1e6)}
                &#8239;Mio.&nbsp;€ Unterschied. Die Grafik verwendet den ersten Wert.{" "}
                {/* Nur behaupten, was diese Zeile auch belegt hat: Der Verweis
                    auf den Abschluss steht an der Zeile als bestandene Probe.
                    Ohne ihn trägt der Wert allein die Rechnung, die in der
                    Tabelle selbst steht. */}
                {k.probes.includes("expense_series_annual_accounts") ? (
                  <>Er stimmt mit der Gesamtergebnisrechnung im Jahresabschluss {k.year}{" "}
                  überein<Beleg q="jahresabschluss" />.</>
                ) : (
                  <>Nur dieser Wert passt zu dem Pro-Kopf-Betrag in derselben
                  Tabellenzeile.</>
                )}{" "}
                Den abweichenden Wert zeigen wir mit, statt den Widerspruch zu
                verbergen.{konflikte.length === 1 && (
                  <> In den übrigen {lange.length - 1} Jahren stimmen die beiden
                  Veröffentlichungen überein.</>
                )}
              </p>
            </section>
          ))}
          {vorDemAbschluss && (
            <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                {vorDemAbschluss}: Gesamtsumme schon vor dem Jahresabschluss
              </p>
              <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
                Der jüngste verfügbare Jahresabschluss ist der von {juengsterAbschluss}.
                Die Gesamtausgaben für {vorDemAbschluss} veröffentlicht die Stadt bereits
                vor dem vollständigen Abschluss<Beleg q="expense_series" />. Die Tabelle
                zeigt aber noch nicht, wie sich die Summe auf die Bereiche verteilt oder
                wie stark das Ergebnis vom Plan abweicht. Diese Angaben folgen erst mit
                dem Jahresabschluss.
              </p>
            </section>
          )}
        </div>
      )}

      {/* Steht am Fuß und gilt für den ganzen Bereich: Wer hier ankommt, hat
          die Zahlen gesehen und fragt sich, bis wann sie reichen. */}
      <Datenstand />

      <Quellenverzeichnis keys={quellen} />
    </div>
    </Quellenkontext>
  );
}
