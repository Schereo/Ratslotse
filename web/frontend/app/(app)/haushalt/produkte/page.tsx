"use client";

// /haushalt/produkte — „Was kostet eigentlich …?"
//
// Die häufigste Bürgerfrage zum Haushalt ist keine nach Teilhaushalten,
// sondern nach einer konkreten Sache: das Stadtarchiv, die Feuerwehr, das
// Schwimmbad. Die Produktebene beantwortet genau das — und die Steckbriefe
// der Teilhaushaltspläne liefern dazu, was die Aufgabe umfasst, worauf sie
// beruht und wie viel Spielraum die Stadt bei ihr sieht.
//
// Zwei Dinge, die diese Seite NICHT tut:
// - Sie färbt nichts ein. Ein teures Produkt ist nicht schlecht, ein Produkt
//   ohne Spielraum nicht verdächtig (Designsprache: keine Bewertungsfarben im
//   Haushalt).
// - Sie reicht kein Verwaltungsdeutsch ungefiltert durch. „übertragender
//   Wirkungskreis" bekommt eine Erklärung (Glossar), „Grad der
//   Beeinflussbarkeit: niedrig" wird zu einem Satz, den man lesen kann.
//
// Query-Param statt dynamischem Segment (?nr=P10.111023): Der Capacitor-Export
// (output: export) kennt die Produktnummern zur Bauzeit nicht — dieselbe
// Konvention wie /haushalt/bereich?name= und /haushalt/steuer?art=.
//
// Gesucht und gefiltert wird SERVERSEITIG: Mit dem Steckbrief trägt jede der
// knapp 400 Zeilen mehrere hundert Zeichen Fließtext.

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronRight, Building2, Scale, Search, X } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  HaushaltDaten, Produkt, ProdukteAntwort, SPIELRAUM_TEXT, Spielraum,
  bereichSlug, betrag,
} from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

const QUELLEN: QuellenSchluessel[] = ["teilhaushalt", "plan"];
const STUFEN: Spielraum[] = ["niedrig", "mittel", "hoch"];

/** Zuschussbedarf in Euro — was das Produkt die Stadt unterm Strich kostet.
 *  `ergebnis` ist negativ, wenn es zuschussbedürftig ist. */
function netto(p: Produkt): number {
  return -(p.ergebnis ?? 0);
}

/** Aufeinanderfolgende Jahre zu Spannen bündeln: [2019, 2020, 2022] →
 *  „2019–2020, 2022". */
function jahresspannen(jahre: number[]): string {
  const sortiert = [...jahre].sort((a, b) => a - b);
  const teile: string[] = [];
  let von = sortiert[0], bis = sortiert[0];
  for (const j of sortiert.slice(1)) {
    if (j === bis + 1) { bis = j; continue; }
    teile.push(von === bis ? String(von) : `${von}–${bis}`);
    von = bis = j;
  }
  if (von != null) teile.push(von === bis ? String(von) : `${von}–${bis}`);
  return teile.join(", ");
}

/** Abdeckungs-Badge (H4-04): Nicht jedes Jahr deckt jeden Teilhaushalt —
 *  ein Produkt, das erst ab 2021 vorliegt, sagt das, statt wie eine
 *  durchgehende Reihe auszusehen.
 *
 *  Vollständige Abdeckung ist die unauffällige Auskunft und verschwindet in
 *  der Trefferliste auf schmalen Karten (`knapp`); die LÜCKE bleibt immer
 *  sichtbar — Lücken zeigen geht vor (H4-A). Kein Signal-Orange: Eine Lücke
 *  im Bestand ist die Lücken-Konvention (gestrichelt), keine Abweichung des
 *  Produkts. */
function AbdeckungsBadge({ jahre, alle, knapp }: {
  jahre?: number[]; alle: number[]; knapp?: boolean;
}) {
  // Mit nur einem Jahrgang im Bestand gäbe es nichts abzudecken.
  if (!jahre?.length || alle.length < 2) return null;
  const fehlt = alle.filter((j) => !jahre.includes(j));
  if (!fehlt.length) {
    return (
      <span className={cn(
        "items-center gap-1 rounded border border-border px-1.5 py-0.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground",
        knapp ? "hidden @2xl/treffer:inline-flex" : "inline-flex",
      )}>
        <Check aria-hidden className="h-3 w-3" />
        {Math.min(...alle)}–{Math.max(...alle)}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded border border-dashed border-border px-1.5 py-0.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
      ohne {jahresspannen(fehlt)}
    </span>
  );
}

/** Bigramme eines Suchbegriffs — der „Ähnlich klingen"-Vergleich des
 *  Leerzustands. Bewusst reine Zeichenähnlichkeit (Dice über Bigramme),
 *  keine Semantik: Für „Feuerwer" findet sie die Feuerwehr, für „Zoo"
 *  findet sie ehrlich nichts — dann bleibt der Satz, dass Produkte wie im
 *  Haushaltsplan heißen. */
function bigramme(s: string): Set<string> {
  const out = new Set<string>();
  for (const wort of s.toLowerCase().replace(/[^a-zäöüß0-9]+/g, " ").trim().split(/\s+/)) {
    for (let i = 0; i < wort.length - 1; i++) out.add(wort.slice(i, i + 2));
  }
  return out;
}

function aehnlichkeit(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let gemeinsam = 0;
  for (const g of a) if (b.has(g)) gemeinsam += 1;
  return (2 * gemeinsam) / (a.size + b.size);
}

/** Eine Zeile der Trefferliste. Der Balken zeigt den Anteil am teuersten
 *  Treffer — Hafenblau, nicht Ampelfarben: teuer ist keine Note. */
function Treffer({ p, max, aktiv, alleJahre }: {
  p: Produkt; max: number; aktiv: boolean; alleJahre: number[];
}) {
  const n = netto(p);
  const b = betrag(Math.abs(n));
  return (
    <Link
      href={`/haushalt/produkte?nr=${encodeURIComponent(p.produkt_nr)}`}
      scroll
      className={cn(
        // `min-w-0`: Ein Rasterkind ist von Haus aus `min-width: auto` und
        // damit so breit wie sein längster Produktname — auf 375 px schob die
        // Karte die ganze Seite 64 px nach rechts. Erst damit greift das
        // `truncate` der Zeilen darin.
        "group block min-w-0 rounded-xl border border-border bg-card p-3 shadow-sm transition-colors hover:border-primary/40",
        aktiv && "border-primary/50 bg-primary/[0.04]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13.5px] font-semibold leading-snug">{p.produkt_name}</p>
          <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            {p.produkt_nr}{p.amt ? ` · ${p.amt}` : ""}
          </p>
        </div>
        <span className="flex-none text-right">
          <span className="block font-display text-[15px] font-bold leading-none tabular-nums">
            {n < 0 && "+"}{b.wert}
          </span>
          <span className="mt-0.5 block font-mono text-[9.5px] uppercase text-muted-foreground">
            {b.einheit}
          </span>
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary/60"
          style={{ width: `${Math.max((Math.abs(n) / max) * 100, 1.5)}%` }} />
      </div>
      {(p.beeinflussbarkeit || (p.jahre && alleJahre.length > 1)) && (
        <p className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
          <span>
            {p.beeinflussbarkeit && (
              <>Spielraum der Stadt: <span className="font-semibold text-foreground/80">
                {SPIELRAUM_TEXT[p.beeinflussbarkeit].kurz}
              </span></>
            )}
          </span>
          <AbdeckungsBadge jahre={p.jahre} alle={alleJahre} knapp />
        </p>
      )}
    </Link>
  );
}

/** Der Steckbrief eines Produkts — Kosten, Zuständigkeit, was drinsteckt,
 *  worauf es beruht, wie viel Spielraum. Fehlende Felder bleiben weg; eine
 *  Lücke wird nicht mit einer Vermutung gefüllt. */
function Steckbrief({ p, jahr, alleJahre }: { p: Produkt; jahr: number; alleJahre: number[] }) {
  const n = netto(p);
  const gross = betrag(Math.abs(n));
  const aus = betrag(p.aufwendungen ?? 0);
  const ein = betrag(p.ertraege ?? 0);
  const spielraum = p.beeinflussbarkeit ? SPIELRAUM_TEXT[p.beeinflussbarkeit] : null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {p.produkt_nr} · Haushaltsjahr {jahr}
        </p>
        <h2 className="mt-1 font-display text-[22px] font-bold leading-tight tracking-tight sm:text-2xl">
          {p.produkt_name}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
          {p.amt && (
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" />{p.amt}
            </span>
          )}
          {p.thh_name && (
            <>
              <span aria-hidden>·</span>
              <Link href={`/haushalt/bereich?name=${bereichSlug(p.thh_name)}`}
                className="font-semibold text-primary hover:underline">
                {p.thh_name}
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Kosten. Keine Bewertungsfarbe — der Betrag steht für sich. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was es die Stadt kostet
        </p>
        <p className="mt-1.5 font-display text-[30px] font-bold leading-none tracking-tight tabular-nums">
          {n < 0 && "+"}{gross.wert}
          <span className="text-base font-semibold text-muted-foreground">&#8239;{gross.einheit}</span>
          <Beleg q="teilhaushalt" />
        </p>
        <p className="mt-2 max-w-[62ch] text-[12.5px] leading-relaxed text-foreground/85">
          {n > 0 ? (
            <>Geplant für {jahr}: <strong>{aus.wert}&#8239;{aus.einheit}</strong> Ausgaben,
              davon holt das Produkt <strong>{ein.wert}&#8239;{ein.einheit}</strong> selbst herein
              (Gebühren, Erstattungen). Der Rest kommt aus allgemeinen Steuermitteln.</>
          ) : (
            <>Dieses Produkt trägt sich {jahr} selbst: {ein.wert}&#8239;{ein.einheit} Einnahmen
              stehen {aus.wert}&#8239;{aus.einheit} Ausgaben gegenüber.</>
          )}
        </p>
        {/* Zwei Ehrlichkeits-Zeilen, auf jedem Gerät (H4-04): Ist-Zahlen gibt
            es je Produkt NICHT — und wie weit das Produkt im Bestand
            zurückreicht, steht als Abdeckung dabei (in der Trefferliste
            trägt das nur der Lücken-Fall, hier immer). */}
        <p className="mt-2 border-t border-border/60 pt-2 text-[11.5px] leading-relaxed text-muted-foreground">
          Planzahlen: Was die Aufgabe tatsächlich gekostet hat, weist der Haushalt auf
          Produktebene nicht aus.
          {p.jahre && p.jahre.length > 0 && alleJahre.length > 1 && (() => {
            const fehlt = alleJahre.filter((j) => !p.jahre!.includes(j));
            return (
              <> Im Bestand liegt das Produkt für {jahresspannen(p.jahre)}
                {fehlt.length > 0 && <> — ohne {jahresspannen(fehlt)}, dort liegt der
                  Teilhaushaltsplan nicht auslesbar vor</>}.</>
            );
          })()}
        </p>
      </div>

      {p.kurzbeschreibung && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was dahintersteckt
          </p>
          <p className="max-w-[70ch] text-[13.5px] leading-relaxed text-foreground/90">
            <GlossaryText text={p.kurzbeschreibung} />
          </p>
          {p.zielgruppe && (
            <p className="mt-3 border-t border-border/60 pt-2.5 text-[12.5px] leading-relaxed text-muted-foreground">
              <span className="font-semibold text-foreground/80">Für wen: </span>
              <GlossaryText text={p.zielgruppe} />
            </p>
          )}
        </div>
      )}

      {(spielraum || p.beeinflussbarkeit_roh || p.wirkungskreis) && (
        <div className="rounded-2xl border border-primary/20 bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
            Wie viel Spielraum die Stadt hat
          </p>
          {spielraum ? (
            <>
              {/* Die Stufen als Skala, nicht als Ampel: gefüllt = diese Stufe.
                  Hafenblau, weil „kaum Spielraum" kein Missstand ist. */}
              <div className="mt-2.5 flex items-center gap-1.5" aria-hidden>
                {STUFEN.map((s) => (
                  <span key={s} className={cn(
                    "h-1.5 flex-1 rounded-full",
                    s === p.beeinflussbarkeit ? "bg-primary" : "bg-muted",
                  )} />
                ))}
              </div>
              <p className="mt-2 text-[13.5px] font-semibold">{spielraum.kurz}</p>
              <p className="mt-1 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
                {spielraum.lang}
              </p>
            </>
          ) : p.beeinflussbarkeit_roh ? (
            <p className="mt-2 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
              Der Plan gibt hier keine der drei Stufen an, sondern schreibt:{" "}
              <em>„{p.beeinflussbarkeit_roh}"</em>. Wir sortieren das bewusst nicht ein.
            </p>
          ) : null}
          <p className="mt-2.5 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Selbstauskunft der Stadt aus dem Teilhaushaltsplan
            {p.beeinflussbarkeit && p.beeinflussbarkeit_roh
              && p.beeinflussbarkeit_roh.toLowerCase() !== p.beeinflussbarkeit
              && <> (dort im Wortlaut „{p.beeinflussbarkeit_roh}“)</>}
            {" "}— keine Bewertung von uns.<Beleg q="teilhaushalt" />
          </p>
          {p.wirkungskreis && (
            <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/85">
              <span className="font-semibold">Wirkungskreis: </span>
              <GlossaryText text={p.wirkungskreis} />
            </p>
          )}
        </div>
      )}

      {p.auftragsgrundlage && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            <Scale className="h-3.5 w-3.5" /> Worauf die Aufgabe beruht
          </p>
          <p className="max-w-[70ch] text-[13px] leading-relaxed text-foreground/90">
            {p.auftragsgrundlage}
          </p>
          <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
            Im Wortlaut des Teilhaushaltsplans — Gesetze, Satzungen und Verträge, aus denen
            sich die Aufgabe ergibt.<Beleg q="teilhaushalt" />
          </p>
        </div>
      )}

      <div className="rounded-2xl border border-dashed border-border bg-card p-4">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Weiterlesen
        </p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px] font-semibold text-primary">
          <Link href={`/council?q=${encodeURIComponent(p.produkt_name.split(",")[0])}`}
            className="inline-flex items-center gap-1.5">
            <Search className="h-3.5 w-3.5" /> Beschlüsse dazu suchen
          </Link>
          {p.thh_name && (
            <Link href={`/haushalt/bereich?name=${bereichSlug(p.thh_name)}`}>
              Bereich „{p.thh_name}“ ansehen →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

function ProdukteInner() {
  const router = useRouter();
  const params = useSearchParams();
  const nr = params.get("nr") ?? "";

  const [suche, setSuche] = useState("");
  const [entprellt, setEntprellt] = useState("");
  const [amt, setAmt] = useState("");
  const [spielraum, setSpielraum] = useState<Spielraum | "">("");

  // Getippt wird schnell, geladen wird langsam: Ohne Entprellung schickt jede
  // Taste eine Anfrage.
  useEffect(() => {
    const t = setTimeout(() => setEntprellt(suche), 250);
    return () => clearTimeout(t);
  }, [suche]);

  const uebersicht = useFetch<HaushaltDaten>("/council/haushalt");
  // Jüngstes Jahr mit Produktebene. Die Liste kommt aus der Übersicht, damit
  // die Seite kein Jahr rät, das es nicht gibt.
  const jahr = useMemo(() => {
    const jahre = uebersicht.data?.produkt_jahre ?? [];
    return jahre.length ? Math.max(...jahre) : null;
  }, [uebersicht.data]);

  const abfrage = useMemo(() => {
    if (!jahr) return null;
    const p = new URLSearchParams({ jahr: String(jahr) });
    if (entprellt.trim()) p.set("q", entprellt.trim());
    if (amt) p.set("amt", amt);
    if (spielraum) p.set("spielraum", spielraum);
    if (nr) p.set("nr", nr);
    return `/council/haushalt/produkte?${p}`;
  }, [jahr, entprellt, amt, spielraum, nr]);

  const { data, loading } = useFetch<ProdukteAntwort>(abfrage);

  // Leerzustand mit „Ähnlich klingen" (H4-04): Erst wenn die gefilterte
  // Suche wirklich leer ist, wird einmal die ungefilterte Liste geholt und
  // nach Zeichenähnlichkeit durchsucht. `useFetch(null)` überspringt — der
  // Hook läuft immer, die Anfrage nur im Leerfall.
  const leer = !loading && data != null && data.produkte.length === 0
    && entprellt.trim().length >= 2 && !amt && !spielraum;
  const { data: alleDaten } = useFetch<ProdukteAntwort>(
    leer && jahr ? `/council/haushalt/produkte?jahr=${jahr}` : null);
  const vorschlaege = useMemo(() => {
    if (!leer || !alleDaten) return [];
    const q = bigramme(entprellt);
    return alleDaten.produkte
      .map((p) => ({ p, wert: aehnlichkeit(q, bigramme(p.produkt_name)) }))
      .filter((x) => x.wert >= 0.25)
      .sort((a, b) => b.wert - a.wert)
      .slice(0, 3)
      .map((x) => x.p);
  }, [leer, alleDaten, entprellt]);

  if (uebersicht.loading || (loading && !data)) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Produkte werden geladen …</div>;
  }
  if (!jahr) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt die Produktebene ausgelesen vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const produkte = data?.produkte ?? [];
  const alleJahre = data?.alle_jahre ?? uebersicht.data?.produkt_jahre ?? [];
  const maxWert = Math.max(...produkte.map((p) => Math.abs(netto(p))), 1);
  const gefiltert = Boolean(entprellt.trim() || amt || spielraum);
  const aemter = data?.facetten?.aemter ?? [];
  const stufen = data?.facetten?.spielraum ?? {};
  const gesamt = aemter.reduce((s, a) => s + a.anzahl, 0);
  const mitBeschreibung = data?.facetten?.mit_feld?.kurzbeschreibung ?? 0;
  const aktiv = data?.produkt ?? null;

  return (
    <Quellenkontext schluessel={QUELLEN} jahr={jahr}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Was kostet eigentlich …?</span>
        </div>

        <div className="@container/kopf">
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[26px]">
            Was kostet eigentlich …?
          </h1>
          {/* Zwei Absätze, zwei Spalten — dieselbe Stelle wie im Kopf von
              „Woher das Geld kommt": Aufhänger und Jahres-Hinweis standen
              untereinander und ließen rechts 493 von 1136 px leer, während
              die Lotti-Karte direkt darunter die volle Breite nahm. Die
              Zeilenlänge bleibt bei 68 Zeichen. Schwelle am CONTAINER
              (Designsprache §4), weil die Seitenleiste am Desktop 240 px vom
              Platz nimmt und dieselbe Fensterbreite auf dem iPad mehr hergibt. */}
          <div className="mt-2 grid gap-x-8 gap-y-2 @5xl/kopf:grid-cols-2">
            <p className="max-w-[68ch] text-[15px] leading-relaxed text-foreground/90">
              Der Haushalt ist in <GlossaryText text="Produkte" /> gegliedert — einzelne Aufgaben mit
              eigener Nummer, eigenem Budget und zuständigem Amt. Hier stehen{" "}
              <strong>{gesamt}</strong> davon aus dem Haushaltsjahr {jahr}: was sie kosten, was
              dahintersteckt und wie viel Spielraum die Stadt bei ihnen sieht.
            </p>
            {/* Der Jahres-Sprung stand bisher nur ganz unten im Abdeckungs-Block.
                Wer von der Übersicht kommt, hat dort ein späteres Planjahr
                gesehen und rechnet die Beträge hier sonst dagegen. */}
            <p className="max-w-[68ch] text-[12.5px] leading-relaxed text-muted-foreground">
              {jahr} ist das jüngste Jahr, für das die Teilhaushaltspläne maschinell auslesbar
              vorliegen — die Beträge lassen sich deshalb nicht mit denen der Übersicht
              verrechnen. Auch die Namen stehen im Wortlaut des Plans: Wir kürzen nichts ab,
              aber wir schreiben seine Abkürzungen auch nicht aus.
            </p>
          </div>
        </div>

        <LottiErklaert
          titel="Warum das interessant ist"
          text={"Bei einem Produkt steht nicht nur der Betrag, sondern auch der Grad der "
            + "Beeinflussbarkeit — die Selbstauskunft der Stadt, wie viel sie hier überhaupt "
            + "ändern könnte. Das macht aus einer Zahl eine Antwort auf die Frage, worüber der "
            + "Rat streiten kann und worüber nicht."}
        />

        {/* Suche + Filter */}
        <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              value={suche}
              onChange={(e) => setSuche(e.target.value)}
              placeholder="Archiv, Feuerwehr, Schwimmbad …"
              aria-label="Produkte durchsuchen"
              className="h-11 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-[14px] outline-none transition-colors focus:border-primary/50"
            />
          </label>

          <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Amt
              </span>
              <select value={amt} onChange={(e) => setAmt(e.target.value)}
                className="h-9 w-full rounded-lg border border-border bg-background px-2 text-[12.5px] outline-none focus:border-primary/50">
                <option value="">Alle Ämter ({gesamt})</option>
                {aemter.map((a) => (
                  <option key={a.amt} value={a.amt}>{a.amt} ({a.anzahl})</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Spielraum der Stadt
              </span>
              <select value={spielraum} onChange={(e) => setSpielraum(e.target.value as Spielraum | "")}
                className="h-9 w-full rounded-lg border border-border bg-background px-2 text-[12.5px] outline-none focus:border-primary/50">
                <option value="">Egal</option>
                {STUFEN.map((s) => (
                  <option key={s} value={s} disabled={!stufen[s]}>
                    {SPIELRAUM_TEXT[s].kurz} ({stufen[s] ?? 0})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-2.5">
            <p className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {produkte.length} {produkte.length === 1 ? "Treffer" : "Treffer"}
              {gefiltert && ` von ${gesamt}`} · sortiert nach Kosten
            </p>
            {gefiltert && (
              <button type="button"
                onClick={() => { setSuche(""); setAmt(""); setSpielraum(""); }}
                className="inline-flex items-center gap-1 text-[11.5px] font-semibold text-primary">
                <X className="h-3.5 w-3.5" /> Filter zurücksetzen
              </button>
            )}
          </div>
        </div>

        {/* Steckbrief: über der Liste, damit ein Treffer auf 375 px nicht
            unterhalb von 400 Zeilen landet. */}
        {aktiv && (
          <section aria-label={`Steckbrief ${aktiv.produkt_name}`}
            className="rounded-2xl border border-primary/25 bg-primary/[0.03] p-3.5 sm:p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
                Steckbrief
              </p>
              <button type="button" onClick={() => router.push("/haushalt/produkte")}
                className="inline-flex items-center gap-1 text-[11.5px] font-semibold text-muted-foreground hover:text-foreground">
                <X className="h-3.5 w-3.5" /> Schließen
              </button>
            </div>
            <Steckbrief p={aktiv} jahr={jahr} alleJahre={alleJahre} />
          </section>
        )}
        {nr && !aktiv && !loading && (
          <p className="rounded-xl border border-dashed border-border bg-card p-4 text-center text-[12.5px] text-muted-foreground">
            Ein Produkt mit der Nummer „{nr}“ liegt für {jahr} nicht vor.
          </p>
        )}

        {produkte.length ? (
          /* Spaltenzahl am Container, nicht am Fenster (Designsprache §4):
             Am Desktop liegt die Liste neben der Seitenleiste, auf dem iPad
             nicht — dieselbe Fensterbreite meint zwei Platzangebote. */
          <div className="@container/treffer">
            <div className="grid gap-2 @3xl/treffer:grid-cols-2">
              {produkte.map((p) => (
                <Treffer key={p.produkt_nr} p={p} max={maxWert} aktiv={p.produkt_nr === nr}
                  alleJahre={alleJahre} />
              ))}
            </div>
          </div>
        ) : (
          /* Leerzustand (H4-04): Der Suchbegriff steht drin, ähnlich
             klingende Produktnamen sind antippbar — und der Satz, WARUM man
             nichts findet, bleibt auch ohne Vorschläge stehen. */
          <div className="rounded-2xl border-2 border-dashed border-border bg-muted/40 p-8 text-center">
            <p className="mx-auto max-w-[46ch] text-[13px] leading-relaxed text-foreground/80">
              {entprellt.trim()
                ? <>Zu <strong>„{entprellt.trim()}“</strong> finden wir kein Produkt.</>
                : <>Mit diesen Filtern bleibt kein Produkt übrig.</>}
            </p>
            {vorschlaege.length > 0 && (
              <div className="mx-auto mt-3 flex max-w-[62ch] flex-wrap items-center justify-center gap-1.5">
                <span className="text-[12px] text-muted-foreground">Ähnlich klingt:</span>
                {vorschlaege.map((p) => (
                  <button key={p.produkt_nr} type="button" onClick={() => setSuche(p.produkt_name)}
                    className="rounded-full border border-primary/30 bg-card px-2.5 py-1 text-[12px] font-semibold text-primary transition-colors hover:border-primary/60">
                    {p.produkt_name}
                  </button>
                ))}
              </div>
            )}
            <p className="mx-auto mt-3 max-w-[46ch] text-[12px] leading-relaxed text-muted-foreground">
              Produkte heißen wie im Haushaltsplan — nicht immer wie im Alltag: Das
              Stadtarchiv steht dort als „Archivierung“.
            </p>
          </div>
        )}

        {/* Abdeckung ehrlich: was die Produktebene erklärt und was nicht. */}
        <div className="@container/abdeckung rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Wie vollständig das ist
          </p>
          {/* Zwei Angaben, zwei Spalten: „wie viel der Ausgaben" und „wie viele
              Steckbriefe" messen Verschiedenes und standen untereinander — die
              Karte blieb rechts auf 584 von 1136 px leer. Die Zeilenlänge
              bleibt bei 70 Zeichen (Designsprache §4); breiter zu setzen wäre
              schlechter zu lesen, nicht besser. */}
          <div className="mt-2 grid gap-x-8 gap-y-2 @5xl/abdeckung:grid-cols-2">
            <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
              {/* toLocaleString, nicht die nackte Zahl: Der Wert kam als 81.7
                  mit englischem Punkt auf die Seite — mitten in einem Text, der
                  sonst durchgehend Komma schreibt. */}
              {data?.abdeckung_prozent != null ? (
                <>Die {gesamt} Produkte erklären{" "}
                  <strong>{data.abdeckung_prozent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%</strong> der
                  für {jahr} geplanten Ausgaben.<Beleg q="plan" /> Nicht jeder Teilhaushalt liegt für
                  jedes Jahr als auslesbares Dokument vor — dies ist also ein Ausschnitt, kein
                  Vollbild.</>
              ) : (
                <>Nicht jeder Teilhaushalt liegt für jedes Jahr als auslesbares Dokument vor —
                  dies ist ein Ausschnitt, kein Vollbild.</>
              )}
            </p>
            <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
              Einen Steckbrief mit Kurzbeschreibung tragen <strong>{mitBeschreibung} von {gesamt}</strong>{" "}
              Produkten; die übrigen führt der Plan ohne Beschreibungstext. Wo ein Feld fehlt, steht
              hier nichts — wir füllen keine Lücke mit einer Vermutung.
            </p>
          </div>
        </div>

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function ProduktePage() {
  // useSearchParams braucht eine Suspense-Grenze (Export-Konvention).
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Produkte werden geladen …</div>}>
      <ProdukteInner />
    </Suspense>
  );
}
