"use client";

// „Was das Rechnungsprüfungsamt fand" — der ERSTE Abschnitt von
// /haushalt/pruefung.
//
// Bis zum 21.08.2026 war das die ganze Seite. Zusammengelegt mit „Die
// dreizehn Zahlen": Beide beantworten dieselbe Frage — wie es gelaufen ist,
// einmal aus der Sicht der Prüfstelle, einmal aus der Selbstauskunft der
// Stadt. Der Rahmen liegt bei der Seite (Begründung: `section-termine.tsx`).

// /haushalt/pruefung — „Was das Rechnungsprüfungsamt beanstandet".
//
// Der Haushalt ist ein Plan, der Jahresabschluss die Abrechnung — und der
// Schlussbericht des Rechnungsprüfungsamts ist die einzige regelmäßige,
// förmliche Kontrolle davon durch eine eigene Stelle. Er hängt als PDF an
// einer Ratsvorlage und wird dort nie wieder gelesen.
//
// Haltung dieser Seite, weil es um Beanstandungen gegen die eigene Verwaltung
// geht: nüchtern und belegt, nie anklagend.
// - Jede Feststellung mit Jahr, Textziffer, Seite und Deeplink. Wer nachlesen
//   will, muss es können.
// - Die Marken werden ERKLÄRT, nicht bewertet — mit dem Wortlaut aus der
//   Legende des jeweiligen Berichts. Ein Hinweis ist etwas anderes als eine
//   Beanstandung, und die große Mehrheit sind Hinweise. Das steht oben, nicht
//   im Kleingedruckten.
// - Keine Bewertungsfarben (siehe components/haushalt/marke.tsx). Die Matrix
//   markiert B/WB in Signal-Orange — als Abweichungs-KATEGORIE des Berichts
//   (GB-10), nicht als Urteil von uns.
// - Wo die Verwaltung geantwortet hat, steht die Antwort daneben.
//
// SEIT H3-05 IST DIE WIEDERHOLUNGS-MATRIX DAS BILD DER SEITE: Feststellung ×
// Jahr (<KettenMatrix>, GB-10), denn die Wiederholungen sind die Geschichte —
// was seit Jahren angemahnt wird, steht als Kette. Der Jahrgang 2024 fehlt
// ersatzlos (PDF ohne Zeichenzuordnung); dieser Satz gehört auf die Seite,
// und die Spalte bleibt trotzdem stehen — die Komponente erzwingt sie in
// jeder Zeile. Das Board ist zugleich der Dunkelmodus-Nachweis der Serie:
// alles hier rechnet in Theme-Tokens, keine Sonderfarbe.
//
// Leserichtung: Was ist das → wie viel ist es (Zähler-Trio) → was heißen die
// Marken → was steht seit Jahren offen (die Matrix) → Bericht für Bericht.
//
// WARUM DER JAHRESBERICHT SEIT 17.08. EINEN KOPF UND EINEN FILTER HAT: Der
// Block „Bericht für Bericht" war die textlastigste Fläche des ganzen
// Haushalts-Bereichs — für 2018 eine einzige Karte mit 49 Feststellungen,
// 26.379 Zeichen und 8.808 px Höhe, alle im selben Gewicht untereinander.
// Die Überschrift verspricht „42 Beanstandungen", und es gab keinen Weg von
// dieser Zahl zu diesen Einträgen: Wer sie sehen wollte, musste 49 Absätze
// lesen. Drei Änderungen, keine davon nimmt etwas weg:
//
//  1. **Die Jahres-Pillen stehen jetzt IM Kartenkopf.** Sie steuern genau
//     diese Karte und standen vorher als eigener Block darüber.
//  2. **Ein Filter „Alle / nur Beanstandungen"** mit ehrlichen Zahlen an
//     beiden Knöpfen. Gefiltert wird im Browser aus dem schon geladenen
//     Bestand — die Marken-Zähler oben bleiben davon unberührt. Was der
//     Filter ausblendet, sagt eine Zeile darunter im Klartext (weglassen
//     heißt hinter einen Auslöser, nie ersatzlos, H4-A).
//  3. **Jeder Abschnitt des Berichts ist ein eigenes Feld** statt einer
//     Trennlinie. 25 Abschnitte geben dem Auge 25 Landmarken; vorher lief
//     alles als ein Strang durch.
//
// Nichts davon rührt an den Wortlaut oder an den Deeplink je Feststellung —
// Textziffer und Seite sind der halbe Wert dieser Seite.

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, ExternalLink } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  Feststellung, Kette, PruefberichtDaten, belegLink, markenZaehlen, markeRang,
  nachAbschnitt, wiederholungsketten,
} from "@/lib/haushalt-pruefung";
import { KettenMatrix, type MatrixKette } from "@/components/grafik/ketten-matrix";
import { LueckenFeld } from "@/components/grafik/luecken-field";
import { Beleg } from "@/components/haushalt/source";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { MarkePille } from "@/components/haushalt/mark";
import { cn } from "@/lib/utils";

// NUR der Prüfbericht. `jahresabschluss` stand bis zum 21.08.2026 daneben und
// bekam im Verzeichnis eine eigene Nummer — nur zeigte keine Zahl der Seite
// darauf: Sie holt ausschließlich /council/haushalt/pruefberichte. Eine
// Quelle, die nichts belegt, ist Schmuck, und Schmuck im Beleg-Apparat ist
// genau das, was das Vertrauen kostet, das er herstellen soll.

/** Wortlaut aus dem Bericht — bewusst als Zitatblock mit Randlinie, damit auf
 *  einen Blick klar ist, wo das Rechnungsprüfungsamt spricht und wo wir. */
function Wortlaut({ text, gedaempft = false }: { text: string; gedaempft?: boolean }) {
  return (
    <p className={cn(
      "border-l-2 pl-3 text-[13.5px] leading-relaxed",
      gedaempft ? "border-dashed border-border text-muted-foreground" : "border-border text-foreground/90",
    )}>
      {text}
    </p>
  );
}

/** Eine Feststellung mit allem, was zum Nachschlagen nötig ist. */
function FeststellungsZeile({ f, zeigeJahr = false }: { f: Feststellung; zeigeJahr?: boolean }) {
  const link = belegLink(f);
  return (
    <div className="flex flex-col gap-2 border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <MarkePille mark={f.mark} name={f.mark_name} klein />
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {zeigeJahr && <>{f.year} · </>}
          Textziffer {f.text_number}
          {f.page != null && <> · Seite {f.page}</>}
        </span>
      </div>
      <Wortlaut text={f.text} />
      {f.follow_paragraph && (
        <div className="pl-3">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
            Im Bericht direkt darauf
          </p>
          <div className="mt-1"><Wortlaut text={f.follow_paragraph} gedaempft /></div>
        </div>
      )}
      {link && (
        <a href={link} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 pl-3 text-[11.5px] font-semibold text-primary">
          Im Schlussbericht {f.year} nachlesen
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}

/** Der Grund, warum ein Jahrgang fehlt — die eine Lücke des Bestands, als
 *  ganzer Satz (H3-05: „Dieser Satz gehört auf die Seite"). */
const LUECKEN_GRUND = "fehlt ersatzlos: Das PDF trägt keine Zeichenzuordnung, "
  + "eine zweite Kopie existiert nicht. Die Spalte bleibt trotzdem stehen — "
  + "als Lücke, nicht als Null.";

/** Beanstandungen im Sinne des Berichts: erstmalige (B) und wiederholte (WB).
 *  Hinweise (H) und Korrekturen (K) sind ausdrücklich etwas anderes — das
 *  steht so in der Legende jedes Jahrgangs und oben auf der Seite. */
const SCHWER = new Set(["B", "WB"]);

/** Ein Abschnitt des Schlussberichts als eigenes Feld.
 *
 *  Die Tonfläche ist dieselbe wie im aufgeklappten Detail der Ketten-Matrix
 *  (`bg-muted/35`) — derselbe Inhalt soll auf einer Seite nicht zweimal
 *  verschieden aussehen. */
function AbschnittsFeld({ text_number, section, eintraege }: {
  text_number: string; section: string; eintraege: Feststellung[];
}) {
  const schwer = eintraege.filter((f) => SCHWER.has(f.mark)).length;
  return (
    <section className="rounded-xl bg-muted/35 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="min-w-0 font-display text-[14.5px] font-bold leading-snug tracking-tight">
          <span className="font-mono text-[11px] font-medium text-muted-foreground">
            {text_number}
          </span>{" "}
          {section}
        </h3>
        <span className="flex-none font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
          {eintraege.length} {eintraege.length === 1 ? "Feststellung" : "Feststellungen"}
          {schwer > 0 && <>{" · "}{schwer} beanstandet</>}
        </span>
      </div>
      <div className="mt-2.5 flex flex-col gap-3">
        {eintraege.map((f) => <FeststellungsZeile key={f.seq} f={f} />)}
      </div>
    </section>
  );
}

/** Die Wiederholungsketten in den Vertrag der <KettenMatrix> (GB-10)
 *  übersetzen: je Jahr höchstens eine Zelle, und zwar die SCHWERSTE Marke
 *  des Abschnitts in diesem Jahrgang (WB vor B vor K vor H). */
function alsMatrixKetten(ketten: Kette[], jahreAnzahl: number): MatrixKette[] {
  return ketten.map((k) => {
    const zellen: { year: number; mark: string }[] = [];
    for (const year of k.years) {
      const hier = k.eintraege.filter((f) => f.year === year)
        .sort((a, b) => markeRang(a.mark) - markeRang(b.mark));
      if (hier[0]) zellen.push({ year, mark: hier[0].mark });
    }
    return {
      key: k.key,
      title: k.title,
      untertitel: `in ${k.beanstandet.length} von ${jahreAnzahl} Berichten beanstandet`
        + (k.beanstandet.length ? ` · zuletzt ${k.beanstandet.at(-1)}` : ""),
      zellen,
    };
  });
}

export function PruefungAbschnitt({ onBestand }: {
  /** Meldet die Zählung aller Feststellungen nach oben — die Seitenbühne im
   *  Kopf zeigt dieselben Balken wie die KettenMatrix, aus derselben Antwort
   *  (H5-02). `ohneBericht` sind die Jahrgänge mit Abschluss, aber ohne
   *  Schlussbericht — die Lücke gehört in den Kopf, nicht in die Fußnote. */
  onBestand?: (b: {
    gesamt: number;
    jeJahr: { year: number; count: number }[];
    ohneBericht: number[];
  } | null) => void;
} = {}) {
  const gewaehltesJahr = Number(useSearchParams().get("year")) || null;
  const { data, loading } = useFetch<PruefberichtDaten>("/council/haushalt/pruefberichte");

  useEffect(() => {
    if (!onBestand || loading) return;
    if (!data?.findings.length) { onBestand(null); return; }
    onBestand({
      gesamt: data.findings.length,
      jeJahr: data.years.map((j) => ({
        year: j,
        count: data.findings.filter((f) => f.year === j).length,
      })),
      ohneBericht: data.without_report,
    });
  }, [onBestand, data]);
  // Der Filter des Jahresberichts. Zustand statt URL-Parameter: Ein geteilter
  // Link soll den Bericht zeigen, wie er ist — vollständig.
  const [nurSchwer, setNurSchwer] = useState(false);

  const years = data?.years ?? [];
  const year = gewaehltesJahr && years.includes(gewaehltesJahr) ? gewaehltesJahr : years.at(-1) ?? null;
  const alle = useMemo(() => data?.findings ?? [], [data]);
  const ketten = useMemo(() => wiederholungsketten(alle), [alle]);
  const matrixKetten = useMemo(
    () => alsMatrixKetten(ketten, years.length), [ketten, years.length]);
  const zahl = useMemo(() => markenZaehlen(alle), [alle]);
  const imJahr = useMemo(
    () => (year ? alle.filter((f) => f.year === year) : []), [alle, year]);
  const schwerImJahr = useMemo(
    () => imJahr.filter((f) => SCHWER.has(f.mark)).length, [imJahr]);
  // Die Zahl der Abschnitte im Kartenkopf zählt IMMER den ganzen Bericht —
  // sie beschreibt das Dokument, nicht unsere Ansicht davon.
  const abschnitteGesamt = useMemo(
    () => (year ? nachAbschnitt(imJahr, year).length : 0), [imJahr, year]);
  const gruppen = useMemo(() => (year
    ? nachAbschnitt(nurSchwer ? imJahr.filter((f) => SCHWER.has(f.mark)) : imJahr, year)
    : []), [imJahr, year, nurSchwer]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!year || !alle.length) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt bisher ein ausgelesener Schlussbericht vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const marken = Object.keys(data.legend).sort((a, b) => markeRang(a) - markeRang(b));
  const hinweise = zahl["H"] ?? 0;
  const beanstandungen = zahl["B"] ?? 0;
  const wiederholt = zahl["WB"] ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Rechnungsprüfungsamt · {years[0]}–{years.at(-1)}
        </p>
        {/* Die Überschrift wird gerechnet, nicht geschrieben — ein fester
            Satz wäre beim nächsten Jahrgang still falsch. */}
        <h2 className="mt-1 font-display text-xl font-bold tracking-tight sm:text-[22px]">
          {alle.length} Feststellungen — {wiederholt} kehren Jahr für Jahr wieder
        </h2>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Das Rechnungsprüfungsamt prüft jeden Jahresabschluss und berichtet seine
          Feststellungen dem Rat. Der Schlussbericht wird als Anlage zu einer Ratsvorlage
          veröffentlicht. Wiederholt beanstandete Themen führen wir über mehrere Jahrgänge
          zusammen; die einzelnen Feststellungen bleiben im Wortlaut des Berichts erhalten.
        </p>
      </div>

      {/* Wie viel ist es — das Zähler-Trio (H3-05), mobil als 3er-Raster
          (H4-09). Die drei Zahlen sind die Marken selbst: H, B und WB —
          erst darunter erklärt der Satz, was sie bedeuten. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {years.length} geprüfte Jahresabschlüsse · {years[0]}–{years.at(-1)}
        </p>
        <div className="mt-2.5 grid grid-cols-3 gap-2">
          {([
            { value: hinweise, name: "Hinweise" },
            { value: beanstandungen, name: "Beanstandungen" },
            { value: wiederholt, name: "wiederholt" },
          ] as const).map((t) => (
            <div key={t.name} className="rounded-xl bg-muted/45 px-3 py-2.5">
              <p className="font-display text-[26px] font-bold leading-none tracking-tight tabular-nums">
                {t.value}
              </p>
              <p className="mt-1 text-[11.5px] leading-snug text-muted-foreground">{t.name}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 max-w-[70ch] text-[13px] leading-relaxed text-foreground/90">
          In den Berichten stehen <strong>{alle.length} Feststellungen</strong>
          <Beleg q="pruefbericht" />. Hinweise benennen Punkte, die künftig beachtet werden
          sollen. Eine Beanstandung bezeichnet einen bedeutsamen Mangel. „Wiederholt“
          bedeutet, dass das Amt denselben Mangel bereits in einem früheren Bericht
          festgestellt hatte.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/60 pt-3">
          {marken.map((m) => (
            <span key={m} className="inline-flex items-baseline gap-1.5">
              <MarkePille mark={m} name={data.legend[m].name} />
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {zahl[m] ?? 0}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Die Marken erklären, nicht bewerten — mit dem Wortlaut des Berichts. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was die Marken am Seitenrand bedeuten
        </p>
        <dl className="mt-2.5 flex flex-col gap-2">
          {marken.map((m) => (
            <div key={m} className="flex flex-col gap-1 border-t border-border/60 pt-2 first:border-t-0 first:pt-0 sm:flex-row sm:items-baseline sm:gap-3">
              <dt className="flex-none"><MarkePille mark={m} name={data.legend[m].name} klein /></dt>
              <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                {data.legend[m].explanation ?? "—"}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          Wortlaut aus den Vorbemerkungen der Berichte. Welche Marken ein Bericht führt, ist nicht
          in jedem Jahrgang gleich — der Schlussbericht 2023 erklärt keine Korrekturen mehr.
        </p>
      </div>

      <LottiErklaert
        title="Wer hier eigentlich prüft"
        text="Das Rechnungsprüfungsamt gehört zur Stadt, arbeitet aber für den Rat und nicht für die Verwaltungsspitze. Es schaut jedes Jahr nach, ob der Jahresabschluss stimmt und ob nach den Regeln gewirtschaftet wurde. Ein Hinweis ist dabei kein Vorwurf, sondern eine Notiz für das nächste Mal — erst eine Beanstandung meint einen bedeutsamen Mangel."
      />

      {/* Die eigentliche Nachricht: was seit Jahren offen ist — als
          Wiederholungs-Matrix (GB-10). Kette antippen oder mit Enter öffnen
          zeigt den Wortlaut aller Feststellungen; die 2024-Lücke rendert die
          Komponente in jeder Zeile und als Satz darüber. */}
      {ketten.length > 0 ? (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wiederholungs-Ketten · was über Jahre offen blieb
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {ketten.length} Themen · {years[0]}–{years.at(-1)}
            </span>
          </div>
          <p className="mb-3 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Hier steht nur, was das Rechnungsprüfungsamt selbst als <em>wiederholte</em>{" "}
            Beanstandung ausgewiesen hat — also seine eigene Aussage, dass ein Mangel aus einem
            Vorjahr noch offen war. Zugeordnet wird über den Abschnitt des Berichts; die
            Textziffern verschieben sich zwischen den Jahrgängen. Ein „erledigt/offen" kennt
            die Quelle nicht — die Kette endet, wo der Bericht nichts mehr vermerkt.
          </p>
          <KettenMatrix
            ketten={matrixKetten}
            years={years}
            lueckenJahre={data.without_report.map((j) => ({ year: j, reason: LUECKEN_GRUND }))}
            marken={data.legend}
            beleg={<Beleg q="pruefbericht" />}
            detail={(mk) => {
              const k = ketten.find((x) => x.key === mk.key);
              if (!k) return null;
              return (
                <div className="flex flex-col gap-3 rounded-xl bg-muted/35 p-3">
                  {k.eintraege.map((f) => (
                    <FeststellungsZeile key={`${f.year}-${f.seq}`} f={f} zeigeJahr />
                  ))}
                </div>
              );
            }}
          />
        </div>
      ) : (
        /* Ohne Ketten gäbe es keine Matrix — der Lücken-Satz bleibt trotzdem
           Pflicht auf der Seite (H4-09: auf jedem Gerät). */
        data.without_report.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {data.without_report.map((j) => (
              <LueckenFeld key={j} label={String(j)} reason={LUECKEN_GRUND} />
            ))}
          </div>
        )
      )}

      {/* Bericht für Bericht. Jahreswahl und Filter gehören IN diese Karte:
          Sie steuern nur sie, und als eigener Block darüber sahen die
          Jahres-Pillen aus wie eine Seiten-Navigation. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Schlussbericht zum Jahresabschluss {year}
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {imJahr.length} Feststellungen · {abschnitteGesamt} Abschnitte
          </span>
        </div>

        <div className="mt-2.5 flex flex-col gap-2 border-b border-border/60 pb-3">
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Geprüfter Jahresabschluss
            </span>
            <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
              <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-muted/40 p-1">
                {years.map((j) => (
                  <Link key={j} href={`/haushalt/pruefung?year=${j}`} scroll={false}
                    className={cn("rounded-full px-3 py-1 text-[12.5px]",
                      j === year ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
                    {j}
                  </Link>
                ))}
              </div>
            </div>
          </div>

          {/* Der Weg von der Zahl oben zu den Einträgen. Keine Farbe, kein
              Ausrufezeichen — unterschieden wird über Gewicht, wie an der
              Marken-Pille (components/haushalt/marke.tsx). */}
          {schwerImJahr > 0 && (
            <div className="flex flex-col gap-1">
              <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Zeigen
              </span>
              <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
                <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-muted/40 p-1">
                  {([
                    [false, `Alle (${imJahr.length})`],
                    [true, `Nur Beanstandungen (${schwerImJahr})`],
                  ] as [boolean, string][]).map(([value, text]) => (
                    <button key={text} type="button" onClick={() => setNurSchwer(value)}
                      aria-pressed={nurSchwer === value}
                      className={cn("min-h-[32px] whitespace-nowrap rounded-full px-3 py-1 text-[12.5px]",
                        nurSchwer === value
                          ? "bg-card font-semibold shadow-sm"
                          : "text-foreground/70 hover:text-foreground")}>
                      {text}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {nurSchwer && (
          <p className="mt-3 max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
            {imJahr.length - schwerImJahr} Hinweise und Korrekturen sind derzeit ausgeblendet.
            Mit „Alle ({imJahr.length})“ wird der Bericht wieder vollständig angezeigt.
          </p>
        )}

        <div className="mt-3 flex flex-col gap-2.5">
          {gruppen.map((g) => (
            <AbschnittsFeld key={g.text_number} text_number={g.text_number}
              section={g.section} eintraege={g.eintraege} />
          ))}
        </div>
      </div>

      {/* Was hier fehlt und warum — plus, wie wörtlich der Text ist. Der
          Absatz begann bis 16.08. mit unserer Parser-Bedingung („Jede Marke
          muss in der Legende erklärt sein und unter einer Textziffer
          stehen"). Die Bedingung gilt weiter (`council/pruefberichte.py`,
          Doku: „Der Konsistenz-Check statt einer Rechenprobe"); auf der Seite
          war sie Selbstvergewisserung. Der fehlende Jahrgang dagegen ist eine
          echte Auskunft über die Datenlage und bleibt. DESIGNSPRACHE.md § 7. */}
      {/* Der 2024-Satz steht oben an der Matrix (LueckenFeld) — hier bleibt
          nur noch, wie wörtlich der Text ist. */}
      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Die Feststellungen stehen im Wortlaut des Berichts; Zeilenumbrüche des PDF-Textes sind
        zusammengezogen, sonst ist nichts verändert.
      </p>

    </div>
  );
}
