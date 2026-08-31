"use client";

// „Und ist das die ganze Stadt?" — der ERSTE Abschnitt von /haushalt/konzern.
//
// Fünfte und letzte Zusammenlegung (21.08.2026): Vier Seiten beantworteten
// diese eine Frage — die Summe (hier), die Gesellschaften einzeln, ihre
// Wirtschaftspläne und die Gebühren, die daraus folgen.

// /haushalt/konzern — „Und ist das die ganze Stadt?"
//
// Die Seite hat genau eine Aussage, und alles auf ihr dient dieser einen: Was
// die sechs Seiten davor zeigen, ist die Kernverwaltung. Klinikum, Busse,
// Bäder und die Gebäudewirtschaft führen eigene Bücher und tauchen im
// Haushalt bestenfalls als Zuschusszeile auf. Zusammen bewegen sie noch
// einmal gut die Hälfte davon.
//
// Leserichtung: die Lücke als Zahl → was ein Gesamtabschluss überhaupt ist →
// die Lücke über die Jahre → wer dazugehört → was der Vergleich NICHT kann
// → Quellen.
//
// HIER STAND BIS 16.08. EIN BLOCK „Dieselbe Zahl, zwei Quellen": acht Zeilen
// Tabelle, in denen für jedes Jahr dieselbe Zahl zweimal danebenstand und in
// der dritten Spalte „unter 1 Tsd. €". Das war Selbstvergewisserung, keine
// Information — die Seite bewies sich selbst, statt jemandem etwas zu
// erklären („du musst nicht beweisen anhand von einer Tabelle, dass deine
// Zahlen richtig sind", Tim 16.08.). Die PRÜFUNG ist geblieben: Das Backend
// rechnet sie weiter (`gegenprobe` in `routers/council.py`), Tests halten sie
// fest (`test_konzernabschluss.py::test_gegenprobe_gegen_die_kernverwaltung`,
// `test_backend_api.py::test_haushalt_konzern_liefert_luecke_und_gegenprobe`),
// und die Technik-Doku beschreibt sie. Nur die Zurschaustellung ist weg.
//
// WARUM DIE GRENZEN NICHT AM ENDE VERSTECKT SIND, sondern einen eigenen
// Block bekommen: Ein Gesamtabschluss ist kein Haushalt. Er kommt zwei Jahre
// später, folgt anderen Regeln und ist mit den Planzahlen auf /haushalt nicht
// verrechenbar. Wer diese Seite liest und danach 1.242 gegen 883 Mio. rechnet,
// hat etwas falsch verstanden, das wir ihm gesagt haben müssten.
//
// KEINE BEWERTUNGSFARBEN, wie im ganzen Bereich (components/grafik/hantel.tsx).

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { deMio } from "@/lib/haushalt";
import {
  Herkunft, KonzernDaten, herkunftVon, jahrDaten, juengstesVergleichsjahr,
  kernAnteil, konsolidierung, traegerJahre, traegerListe,
} from "@/lib/haushalt-konzern";
import { KonzernLuecke, LueckeArt } from "@/components/haushalt/konzern-luecke";
import { KonzernTraegerListe } from "@/components/haushalt/konzern-traeger";
import { Beleg } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

// Nur was auf dieser Seite auch zitiert wird: „jahresabschluss" stand hier,
// solange der Gegenproben-Block stand — er war die einzige Stelle mit einem
// Beleg darauf. Ein Schlüssel ohne Fußnote im Text wäre ein Eintrag im
// Verzeichnis, auf den nichts zeigt.

/** Wo eine Angabe im Dokument steht: welcher Abschnitt, welcher Stand. Das
 *  Quellenverzeichnis am Seitenende beschreibt die Quelle der ganzen Seite;
 *  das hier gehört an die einzelne Zahl und ist der Grund, warum man sie in
 *  einem 300-Seiten-PDF wiederfindet.
 *
 *  HIER STANDEN BIS 16.08. AUCH UNSERE PROBEN: die Sätze aus
 *  `herkunft.PROBEN` und darunter „Gemessen: 0,00 % Abweichung". Das sagte
 *  etwas über uns und nichts über den Haushalt — dieselbe
 *  Selbstvergewisserung wie die Gegenproben-Tabelle, die auf dieser Seite
 *  stand (DESIGNSPRACHE.md § 7). Die Proben laufen unverändert weiter, die
 *  API liefert sie weiter, Tests halten sie fest und die Technik-Doku
 *  beschreibt sie. Nur die Zurschaustellung ist weg. */
function Fundstelle({ h, className }: { h: Herkunft | null; className?: string }) {
  // Ohne Fundstelle nichts — sonst bliebe eine Überschrift ohne Inhalt stehen.
  // Der Abstand kommt deshalb per `className` von außen statt aus einem
  // Wrapper-<div>: Ein leerer Wrapper mit `mt-3` hinterließe genau die Lücke,
  // die dieses `return null` vermeiden soll.
  if (!h?.fundstelle) return null;
  return (
    <div className={cn("border-t border-dashed border-border pt-2.5", className)}>
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {h.fundstelle}{h.stand ? ` · ${h.stand}` : ""}
      </p>
    </div>
  );
}

/** Die Kernaussage als Zahl — bewusst zwei Beträge und ein Anteil, mehr nicht.
 *  Der Anteil ist unsere Rechnung und steht als solche gekennzeichnet. */
function Lueckenkopf({ daten, year }: { daten: KonzernDaten; year: number }) {
  const a = kernAnteil(daten, year, "revenues");
  if (!a) return null;
  const prozent = Math.round(a.anteil * 100);
  const rest = a.konzern - a.kern;
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Haushaltsjahr {year} · ordentliche Erträge
        </p>
        <p className="mt-1.5 max-w-[70ch] text-sm leading-relaxed text-foreground/90">
          Der Haushalts-Bereich zeigt die <GlossaryText text="Kernverwaltung" />:{" "}
          <strong>{deMio(a.kern / 1e6)}&#8239;Mio.&nbsp;€</strong>. Rechnet die Stadt ihre
          Betriebe und Beteiligungen dazu, sind es{" "}
          <strong>{deMio(a.konzern / 1e6)}&#8239;Mio.&nbsp;€</strong>
          <Beleg q="gesamtabschluss" /> — noch einmal {deMio(rest / 1e6)}&#8239;Mio.&nbsp;€
          obendrauf.
        </p>
      </div>
      {/* Der Anteil als Streifen: eine Zeile, zwei Töne, keine Torte —
          bei zwei Werten ist ein Kreis nur ein umständliches Rechteck. */}
      <div>
        <div className="flex h-7 w-full overflow-hidden rounded-lg">
          <div className="flex items-center justify-end pr-2"
            style={{ width: `${prozent}%`, background: "var(--hh-ein-0)" }}>
            <span className="font-mono text-[10.5px] font-semibold"
              style={{ color: "var(--hh-seg-text)" }}>{prozent}&nbsp;%</span>
          </div>
          <div className="flex flex-1 items-center pl-2" style={{ background: "var(--hh-ein-4)" }}>
            <span className="font-mono text-[10.5px] font-semibold text-foreground/70">
              {100 - prozent}&nbsp;%
            </span>
          </div>
        </div>
        <p className="mt-1.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
          Unsere Rechnung: Kernverwaltung geteilt durch Konzernsumme, beides aus derselben
          Tabelle des Prüfberichts. Keine amtliche Kennzahl — die Stadt weist sie so nicht aus.
        </p>
      </div>
    </div>
  );
}

export function KonzernAbschnitt({ onBestand }: {
  /** Meldet den jüngsten Kernhaushalt-Anteil nach oben — die Seitenbühne im
   *  Kopf zeigt denselben Anteilsbalken wie dieser Abschnitt, aus derselben
   *  Antwort (H5-02). Erträge, wie im Vergleichsbalken unten. */
  onBestand?: (b: { anteil: number; year: number } | null) => void;
} = {}) {
  const { data, loading } = useFetch<KonzernDaten>("/council/haushalt/konzern");

  useEffect(() => {
    if (!onBestand || loading) return;
    const year = data ? juengstesVergleichsjahr(data) : null;
    const a = data && year != null ? kernAnteil(data, year) : null;
    onBestand(year != null && a ? { anteil: a.anteil, year } : null);
  }, [onBestand, loading, data]);
  const [art, setArt] = useState<LueckeArt>("revenues");
  const [year, setJahr] = useState<number | null>(null);

  const jahre = useMemo(() => (data ? traegerJahre(data, art) : []), [data, art]);
  const aktJahr = year && jahre.includes(year) ? year : jahre.at(-1) ?? null;
  const kopfJahr = data ? juengstesVergleichsjahr(data) : null;

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Zahlen des Konzerns werden geladen …
    </div>;
  }
  // Ohne eingelesene Gesamtabschlüsse gibt es diese Seite nicht — lieber ein
  // ehrlicher Hinweis als eine Seite voller Striche.
  if (!data || !data.konzern.length || !kopfJahr) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite sind noch keine Gesamtabschlüsse eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  const jd = aktJahr ? jahrDaten(data, aktJahr) : null;
  const zeilen = aktJahr ? traegerListe(data, aktJahr, art) : [];
  const verrechnung = aktJahr ? konsolidierung(data, aktJahr, art) : null;
  const summe = jd ? (art === "revenues" ? jd.revenues_total : jd.expenses_total) : null;
  // Die Trägeraufstellung hat ihre eigene Herkunft (Abschnitt 4.1.1), nicht
  // die der Postentabelle — sie steht anderswo und ist anders geprüft.
  const hTraeger = herkunftVon(data, (zeilen[0] ?? verrechnung)?.herkunft_id);
  const quelleUrl = herkunftVon(data, jd?.herkunft_id)?.url ?? null;

  return (
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
              Und ist das die ganze Stadt?
            </h2>
            <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
              Nein. Der Haushalt zeigt die Verwaltung. Klinikum, Busse, Bäder und die
              städtischen Gebäude führen eigene Bücher — hier stehen sie zum ersten Mal
              in einer Rechnung.
            </p>
          </div>
          {quelleUrl && (
            <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
              className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
              <FileText className="h-3.5 w-3.5" /> Quelle öffnen
            </a>
          )}
        </div>

        <Lueckenkopf daten={data} year={kopfJahr} />

        <LottiErklaert
          titel="Was ist ein Gesamtabschluss?"
          text={"Viele städtische Aufgaben liegen bei Eigenbetrieben oder Gesellschaften. "
            + "Im Gesamtabschluss führt die Stadt deren Abschlüsse mit dem eigenen Abschluss "
            + "zusammen. Geschäfte innerhalb des Konzerns werden dabei herausgerechnet, damit "
            + "dieselben Erträge und Aufwendungen nicht doppelt erscheinen. Das nennt sich "
            + "Konsolidierung."}
        />

        {/* Umschalter Erträge/Aufwendungen — dieselbe Frage, andere Seite der
            Rechnung. Er steuert die Lücke UND die Trägerliste, damit nicht
            zwei Blöcke verschiedene Dinge zeigen. */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Die Lücke über die Jahre
          </p>
          <Segmented<LueckeArt>
            value={art}
            onChange={setArt}
            options={[
              { value: "revenues", label: "Einnahmen" },
              { value: "expenses", label: "Ausgaben" },
            ]}
          />
        </div>
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <KonzernLuecke daten={data} art={art} />
          <Fundstelle h={herkunftVon(data, jd?.herkunft_id)} />
        </div>

        {/* Wer dazugehört */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wer gehört dazu?
            </p>
            {jahre.length > 1 && (
              <div className="flex flex-wrap gap-1">
                {jahre.map((j) => (
                  <button key={j} type="button" onClick={() => setJahr(j)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 font-mono text-[11px] tabular-nums transition-colors",
                      j === aktJahr
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-muted-foreground hover:border-primary/40",
                    )}>
                    {j}
                  </button>
                ))}
              </div>
            )}
          </div>
          <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            {art === "revenues" ? "Einnahmen" : "Ausgaben"} {aktJahr}, aufgeteilt auf die
            Betriebe und Gesellschaften, die die Stadt in ihre Rechnung einbezieht.
            <Beleg q="gesamtabschluss" />
          </p>
          <div className="mt-3">
            <KonzernTraegerListe zeilen={zeilen} verrechnung={verrechnung}
              summe={summe ?? null} />
          </div>
          <Fundstelle h={hTraeger} className="mt-3" />
        </section>

        {/* Die Grenzen — eigener Block, nicht Kleingedrucktes.
            ZWEI SPALTEN AUF BREITEN KARTEN. Die Liste stand in einem
            `max-w-[76ch]`, und auf einem breiten Bildschirm blieb daneben die
            halbe Karte leer (Tim, 21.08.2026). Die Designsprache sagt dazu
            selbst: „ein eigenes `max-w-*` auf einem Raster verschenkt genau
            den Platz, den das Gerät hat" (§ 4).

            Die volle Breite in EINER Spalte wäre aber der falsche Tausch —
            bei 1.400 px stünden dort rund 220 Zeichen je Zeile, und das liest
            niemand mehr zurück an den Zeilenanfang. Zwei Spalten füllen die
            Fläche und halten die Zeile lesbar.

            `@container` und nicht `lg:`, wie überall in diesem Bereich: Am
            Desktop liegt die Karte neben einer 240-px-Seitenleiste, auf dem
            iPad nicht — dieselbe Fensterbreite meint zwei verschiedene
            Platzangebote. Deshalb misst die Schwelle die KARTE. */}
        <section className="@container rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Was dieser Vergleich nicht kann
          </p>
          <ul className="mt-2 grid list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:grid-cols-2">
            <li>
              <strong>Ein Gesamtabschluss ist kein Haushalt.</strong> Er rechnet ab, was war,
              und folgt dabei kaufmännischen Regeln. Die Planzahlen auf{" "}
              <Link href="/haushalt" className="font-semibold text-primary">/haushalt</Link>{" "}
              sind mit diesen Zahlen <strong>nicht verrechenbar</strong> — auch nicht durch
              Subtraktion.
            </li>
            <li>
              <strong>Er kommt spät.</strong> Der Bericht zum Jahr {kopfJahr} lag dem Rat erst
              rund zwei Jahre später vor. Die aktuellen Haushaltszahlen sind immer neuer
              als die aktuellsten Konzernzahlen.
            </li>
            <li>
              <strong>Nicht alles ist drin.</strong> Beteiligungen, die zu klein sind, um das
              Bild zu verändern, bleiben außen vor — Sparkassenzweckverband, OOWV, EWE und
              andere. Welche das sind, entscheidet die Stadt in ihrer
              Gesamtabschlussrichtlinie; im Bericht steht es als Grafik, die wir nicht
              maschinell auslesen können.
            </li>
            <li>
              <strong>Schulden stehen hier nicht.</strong> Der Bericht führt eine
              Schuldenübersicht als Pflichtanlage, deren Seite im PDF jedoch keinen
              maschinenlesbaren Text enthält. Deshalb weisen wir daraus keine Beträge aus.
              Für die Stadt als Rechtsträger — Verwaltung und Eigenbetriebe, ohne die
              Gesellschaften auf dieser Seite — gibt es dagegen Zahlen seit 1995:{" "}
              <Link href="/haushalt/schulden" className="font-semibold text-primary">
                Wie viel Schulden hat Oldenburg?
              </Link>
            </li>
          </ul>
        </section>


        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

      </div>
  );
}
