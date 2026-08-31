"use client";

// Der Steckbrief einer städtischen Gesellschaft (H3-02, Detailansicht von
// /haushalt/beteiligungen).
//
// WARUM ER UMGEBAUT WURDE: Vorher goss die Seite fünf Abschnitte des
// Beteiligungsberichts nacheinander als Rohtext aus (bis 2.660 Zeichen am
// Stück, `whitespace-pre-line`), und darunter stand eine Zahlenliste. Zwei
// der fünf Abschnitte sind aber gar kein Fließtext: „Beteiligungsverhältnisse"
// ist eine Tabelle, „Besetzung der Aufsichtsorgane" eine Personenliste. Als
// Absatz gesetzt, sahen beide aus wie Text und lasen sich wie keiner.
//
// DREI FORMEN STATT EINER (jede hält ihre Regel):
//
//  1. **Die Zahlen stehen oben.** Jahresergebnis, Bilanzsumme,
//     Eigenkapitalquote sind das, wonach jemand hier sucht — sie standen im
//     Keller unter 4.000 Zeichen Prosa. Jede trägt ihr eigenes Jahr, denn die
//     Reihen enden nicht alle gleich (die Großleitstelle führt im Bericht für
//     2024 die Jahre bis 2021). KEINE BEWERTUNGSFARBEN: kein Rot am Verlust,
//     keine Pfeile, keine Ampel. Ein Verkehrsbetrieb mit Verlust erfüllt
//     seinen Auftrag — deshalb ist die <Einordnung> Pflichtteil.
//  2. **Wem sie gehört, wird ein Streifen.** Anteile sind Größen, keine
//     Sätze. Der Balken kommt aus dem Baukasten (`<Anteilsbalken>`), die
//     Beschriftung aus der QUELLE: Euro und Prozent stehen nur da, wo der
//     Bericht sie nennt — eine aus dem Betrag gerechnete Quote hätte sonst
//     dieselbe Autorität wie eine gedruckte.
//  3. **Wer sie beaufsichtigt, wird zu Personen.** Mit Partei-Punkt und Link
//     ins Personenverzeichnis, in derselben Sprache wie die Personen-Badges
//     der KI-Antworten (`parteiDot`/`parteiKuerzel` aus qa-bausteine) — nicht
//     in einer dritten. Wer keinen Eintrag hat, bleibt ein Element ohne Link;
//     erfunden wird nichts.
//
// `position: null` HEISST UNBEKANNT, NICHT „KEINE". Der Bericht führt Namen
// und Funktionen in zwei getrennten Spalten; paaren lassen sie sich nur nach
// Position, und das nur bei exakt gleicher Länge. Wo die Probe scheitert
// (`roles_assignable === false`), zeigt die Seite die Namen OHNE Ämter
// und sagt in einem Satz, warum. Der Vorsitz bleibt trotzdem stehen: Er
// steht in der Namenszeile selbst („…, Vorsitzende"), nicht in der Spalte.
//
// ALLES NEUE IST OPTIONAL. Fehlen `personen`/`eigentuemer` (ältere API) oder
// bleiben sie für eine Gesellschaft leer (Probe nicht bestanden), steht der
// Rohtext des Abschnitts da wie bisher — kein leerer Block, kein Spinner ins
// Nichts.
//
// UND KEINE SELBSTVERGEWISSERUNG (DESIGNSPRACHE § 7): Die Seite führt nicht
// vor, wie gründlich geprüft wurde. Die eine Ausnahme bleibt: Wo eine Zahl
// FEHLT, sagt sie es — das ist eine Auskunft über die Quelle, keine Selbstlob.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronDown } from "lucide-react";
import {
  ABSCHNITTE, Aufsichtsperson, BeteiligungsDaten, Eigentuemer, Gesellschaft,
  KENNZAHL_TITEL, Kennzahl, RECHTSFORM_TITEL,
  absatzVorschau, anteilsGewicht, aufsichtsgruppen,
  aufsichtspersonen, eigentuemerVon, einordnungFuer, eur, gremiumName, herkunftVon,
  percent, rechtsform, reihen, textVon, wertText,
} from "@/lib/haushalt-beteiligungen";
import { personHref } from "@/lib/routes";
import type { JahrPunkt } from "@/components/grafik/daten";
import { deZahl } from "@/components/grafik/format";
import { ZeitreiheMini } from "@/components/grafik/zeitreihe";
import { Einordnung } from "@/components/grafik/einordnung";
import { Anteilsbalken } from "@/components/haushalt/anteilsbalken";
import { FormZeichen } from "@/components/haushalt/konzernkarte";
import { Beleg } from "@/components/haushalt/source";
import { parteiDot, parteiKuerzel } from "@/components/qa-bausteine";
import { cn } from "@/lib/utils";

/** Die Kennzahlen im Kopf, in dieser Reihenfolge. */
const TRIO = ["jahresergebnis", "bilanzsumme", "eigenkapitalquote"] as const;

/** Die Überschriften der Abschnitte, aus EINER Quelle (`ABSCHNITTE`): Sonst
 *  hieße derselbe Abschnitt in der Struktur-Fassung anders als im Rückfall
 *  auf den Wortlaut. */
const TITEL: Record<string, string> = Object.fromEntries(
  ABSCHNITTE.map((a) => [a.key, a.title]));

/** Wo eine Angabe im Dokument steht — bei 200 Seiten der Unterschied zwischen
 *  „steht in dem PDF" und „steht auf Seite 178, Abschnitt 2.4.8". */
export function Fundstelle({ h, className }: {
  h: ReturnType<typeof herkunftVon>; className?: string;
}) {
  if (!h?.citation) return null;
  const ziel = h.page && h.url ? `${h.url}#page=${h.page}` : h.url;
  return (
    <div className={cn("border-t border-dashed border-border pt-2.5", className)}>
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher das stammt
      </p>
      <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {h.label ?? "Beteiligungsbericht"}, {h.citation}
        {h.page ? `, Seite ${h.page}` : ""}
        {ziel && (
          <>
            {" · "}
            <a href={ziel} target="_blank" rel="noopener noreferrer"
              className="font-semibold text-primary">
              Dokument öffnen
            </a>
          </>
        )}
      </p>
    </div>
  );
}

/** Die Karten-Hülle aller Abschnitte: Kicker links, ehrliche Zähl-/
 *  Zeitraum-Angabe rechts (Designsprache § 5). */
function Abschnitt({ kicker, zusatz, className, children }: {
  kicker: string; zusatz?: string; className?: string; children: React.ReactNode;
}) {
  return (
    <section className={cn("rounded-2xl border border-border bg-card p-4 shadow-sm", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {kicker}
        </p>
        {zusatz && (
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            {zusatz}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}

/** Die Zeitreihe als `JahrPunkt[]` für den Baukasten: Werte in Mio. €, ohne
 *  erfundene Zwischenjahre — was der Bericht nicht nennt, bleibt Lücke. */
function ergebnisReihe(ergebnisse: Kennzahl[]): JahrPunkt[] {
  return ergebnisse.map((k) => ({ year: k.year, value: k.value / 1_000_000 }));
}

/** Eine Zahl im Kopf: Kennzahl, Jahr, Betrag — und wo nichts dasteht, der
 *  Satz, dass nichts dasteht. */
function Kopfzahl({ title, k }: { title: string; k: Kennzahl | null }) {
  return (
    <div className="min-w-0">
      <dt className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        {title} {k ? k.year : ""}
      </dt>
      {k ? (
        <dd className="font-display text-[21px] font-bold leading-tight tracking-tight tabular-nums">
          {wertText(k)}
          <Beleg q="beteiligungsbericht" />
        </dd>
      ) : (
        <dd className="mt-0.5 text-[12px] leading-snug text-muted-foreground">
          nennt der Bericht nicht
        </dd>
      )}
    </div>
  );
}

/** Der Kopf: die drei Zahlen, der Verlauf daneben, die Einordnung darunter.
 *
 *  Jede Zahl trägt ihr eigenes Jahr, weil die Reihen verschieden weit
 *  reichen — ein gemeinsames „Stand 2024" über allen dreien wäre für die
 *  Eigenkapitalquote schlicht falsch. */
function Zahlenkopf({ daten, g }: { daten: BeteiligungsDaten; g: Gesellschaft }) {
  const alleReihen = useMemo(() => reihen(daten, g.company), [daten, g.company]);
  const ergebnisse = alleReihen.get("jahresergebnis") ?? [];
  const series = ergebnisReihe(ergebnisse);
  const von = ergebnisse[0]?.year, bis = ergebnisse[ergebnisse.length - 1]?.year;
  const quote = alleReihen.get("eigenkapitalquote") ?? [];
  // Die Eigenkapitalquote des jüngsten Jahres trägt keine Probe und steht
  // deshalb nicht im Bestand (Begründung: council/beteiligungsbericht.py).
  // Eine stumme Lücke sähe nach Fehler aus.
  const quoteFehlt = !!ergebnisse.length && !!quote.length
    && quote[quote.length - 1].year < ergebnisse[ergebnisse.length - 1].year;
  const herkunft = herkunftVon(daten, ergebnisse[ergebnisse.length - 1]?.herkunft_id
    ?? g.herkunft_id);

  return (
    <Abschnitt kicker="Die Zahlen aus dem Bericht"
      zusatz={von && bis ? `${von}–${bis}` : undefined}
      className="@container/zahlen">
      {/* Die drei Zahlen hängen zusammen und stehen deshalb beieinander, statt
          sich als Raster über die ganze Kartenbreite zu verteilen: Auf 1440 px
          lägen sonst 40 cm zwischen Ergebnis und Quote. */}
      <div className="mt-2.5 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <dl className="flex min-w-[220px] flex-1 flex-wrap gap-x-10 gap-y-3">
          {TRIO.map((k) => {
            const liste = alleReihen.get(k) ?? [];
            return (
              <Kopfzahl key={k} title={KENNZAHL_TITEL[k]}
                k={liste[liste.length - 1] ?? null} />
            );
          })}
        </dl>
        {series.length >= 2 && (
          <div className="w-[168px] flex-none">
            <ZeitreiheMini
              series={series}
              format={(v) => deZahl(v, 1)}
              ariaLabel={`Jahresergebnis ${von} bis ${bis} in Mio. Euro: ${ergebnisse
                .map((k) => `${k.year} ${eur(k.value)}`).join(", ")}.`}
            />
            <p className="mt-0.5 text-center font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
              Jahresergebnis in Mio. €
            </p>
          </div>
        )}
      </div>

      <Einordnung satz={einordnungFuer(daten, g, ergebnisse)} className="mt-3" />

      {quoteFehlt && (
        <p className="mt-2.5 max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
          Für {bis} steht die Eigenkapitalquote noch nicht dabei: Der Bericht nennt sie,
          rechnet sie aber nirgends vor. Sobald sie im nächsten Bericht ein zweites Mal
          steht, kommt sie hinzu.
        </p>
      )}
      <Fundstelle h={herkunft} className="mt-3" />
    </Abschnitt>
  );
}

/** „Was die Gesellschaft tut": erster Absatz sichtbar, der Rest hinter einem
 *  Auslöser. Weglassen heißt hinter einen Auslöser, nie ersatzlos (H4-A) —
 *  gekürzt wird die Darstellung, nicht der Wortlaut. */
function Auftrag({ text, herkunft }: {
  text: string; herkunft: ReturnType<typeof herkunftVon>;
}) {
  const [offen, setOffen] = useState(false);
  const { kopf, rest } = useMemo(() => absatzVorschau(text), [text]);

  return (
    <Abschnitt kicker={TITEL.gegenstand}>
      <p className="mt-1.5 max-w-[76ch] whitespace-pre-line text-[13.5px] leading-relaxed text-foreground/90">
        {kopf}
      </p>
      {rest && (
        <>
          {offen && (
            <p className="mt-2 max-w-[76ch] whitespace-pre-line text-[13.5px] leading-relaxed text-foreground/90">
              {rest}
            </p>
          )}
          <button type="button" onClick={() => setOffen(!offen)} aria-expanded={offen}
            className="mt-2 inline-flex min-h-[36px] items-center gap-1 text-[12.5px] font-semibold text-primary">
            {offen ? "Wortlaut einklappen" : "Ganzen Wortlaut zeigen"}
            <ChevronDown size={14} strokeWidth={2}
              className={cn("transition-transform", offen && "rotate-180")} />
          </button>
        </>
      )}
      <Fundstelle h={herkunft} className="mt-3" />
    </Abschnitt>
  );
}

/** „Wem sie gehört" als Anteilsstreifen.
 *
 *  Die Farben kommen aus der Einnahmen-Rampe (`--hh-ein-*`, dunkel nach
 *  hell in der Reihenfolge des Berichts) — nie aus Ampelfarben: Ein
 *  Mitgesellschafter ist nicht „gelb". Beschriftet wird nur, was in der
 *  Quelle steht: Betrag, wo der Bericht Euro nennt, Quote, wo er Prozent
 *  nennt, beides, wo beides dasteht. */
function Eigentuemerstreifen({ liste, herkunft }: {
  liste: Eigentuemer[]; herkunft: ReturnType<typeof herkunftVon>;
}) {
  const summe = liste.reduce((n, e) => n + anteilsGewicht(e), 0);
  if (!(summe > 0)) return null;
  const segmente = liste.map((e, i) => ({
    label: e.name,
    value: anteilsGewicht(e),
    farbe: `var(--hh-ein-${Math.min(i, 6)})`,
  }));

  return (
    <Abschnitt kicker={TITEL.beteiligungsverhaeltnisse}
      zusatz={`${liste.length} Anteilseigner`}>
      <div className="mt-2.5">
        <Anteilsbalken segmente={segmente} gesamt={summe} legende={false} hoehe={16} />
        <ul className="mt-2.5 flex flex-col gap-1.5">
          {liste.map((e, i) => (
            <li key={`${e.name}-${i}`} className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 text-[12.5px]">
              <span aria-hidden="true" className="mt-1 h-2.5 w-2.5 flex-none rounded-[3px]"
                style={{ background: `var(--hh-ein-${Math.min(i, 6)})` }} />
              <span className="min-w-0 flex-1 leading-snug">{e.name}</span>
              {e.amount_eur != null && (
                <span className="flex-none tabular-nums text-muted-foreground">
                  {eur(e.amount_eur)}
                </span>
              )}
              {e.share_pct != null && (
                <span className="w-[62px] flex-none text-right font-semibold tabular-nums">
                  {percent(e.share_pct)}
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-2.5 max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
        Angaben aus der Gesellschaftertabelle des Berichts. Beträge und Quoten stehen so da,
        wie sie gedruckt sind — gerechnet wird hier nichts.
      </p>
      <Fundstelle h={herkunft} className="mt-3" />
    </Abschnitt>
  );
}

/** Eine Person im Aufsichtsorgan.
 *
 *  Wer im Personenverzeichnis steht, wird verlinkt (`personHref`) und trägt
 *  seinen Partei-Punkt; wer nicht, bleibt ein schlichtes Element ohne Link —
 *  ein toter Link wäre schlimmer als keiner. Der Punkt ist ein 8-px-Punkt und
 *  keine Fläche (Designsprache § 2): Eine parteigefärbte Karte machte aus
 *  einem Aufsichtsmandat ein Plakat. */
function Person({ p, zeigeFunktion }: { p: Aufsichtsperson; zeigeFunktion: boolean }) {
  const dot = p.party ? parteiDot(p.party) : null;
  const zusatz = [zeigeFunktion ? p.position : null, p.note].filter(Boolean).join(" · ");

  return (
    <li className="min-w-0 rounded-xl border border-border px-3 py-2">
      <span className="flex flex-wrap items-baseline gap-x-1.5">
        {/* Der Punkt steht nur, wo eine Partei dasteht. Ein Platzhalter für
            „keine" sähe aus wie „unbekannt" — eine Beschäftigtenvertreterin
            hat schlicht keine Fraktion. */}
        {dot && (
          <span aria-hidden="true" className="h-2 w-2 flex-none translate-y-[-1px] rounded-full"
            style={{
              background: dot.bg,
              boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
            }} />
        )}
        {p.slug ? (
          <Link href={personHref(p.slug)}
            className="text-[13px] font-semibold leading-snug text-foreground hover:text-primary hover:underline">
            {p.name}
          </Link>
        ) : (
          <span className="text-[13px] font-semibold leading-snug">{p.name}</span>
        )}
        {p.party && (
          <span className="text-[10.5px] font-medium text-muted-foreground">
            {parteiKuerzel(p.party)}
          </span>
        )}
      </span>
      {zusatz && (
        <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">
          {zusatz}
        </span>
      )}
    </li>
  );
}

/** „Wer sie beaufsichtigt": die Mitglieder, nach Funktion gebündelt. */
function Aufsichtsorgan({ personen, zuordenbar, herkunft }: {
  personen: Aufsichtsperson[]; zuordenbar: boolean;
  herkunft: ReturnType<typeof herkunftVon>;
}) {
  const gruppen = useMemo(() => aufsichtsgruppen(personen, zuordenbar),
    [personen, zuordenbar]);
  const committee = gremiumName(personen);

  return (
    <Abschnitt kicker={TITEL.aufsichtsorgane} className="@container/organ"
      zusatz={`${personen.length} ${personen.length === 1 ? "Person" : "Personen"}`}>
      {/* Kein „x von y Namen wiedergefunden": Wie gut unser Abgleich mit dem
          Personenverzeichnis läuft, ist kein Seiteninhalt (DESIGNSPRACHE § 7).
          Wer einen Eintrag hat, ist verlinkt — das sieht man. */}
      {committee && (
        <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/90">
          Das Aufsichtsorgan ist der {committee}.
        </p>
      )}

      <div className="mt-3 flex flex-col gap-3">
        {gruppen.map((gr) => (
          <div key={gr.key}>
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              {gr.title}
            </p>
            <ul className="mt-1.5 grid gap-1.5 @xl/organ:grid-cols-2 @4xl/organ:grid-cols-3">
              {gr.personen.map((p, i) => (
                <Person key={`${p.name}-${i}`} p={p}
                  zeigeFunktion={gr.key === "chair" && zuordenbar} />
              ))}
            </ul>
          </div>
        ))}
      </div>

      {!zuordenbar && (
        <p className="mt-3 max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
          Welches Amt zu welchem Namen gehört, gibt der Bericht hier nicht her: Er führt
          Namen und Funktionen in zwei getrennten Spalten, und die beiden Listen sind
          verschieden lang. Deshalb stehen die Namen ohne Amt; eine eindeutige Zuordnung
          ist aus dieser Tabelle nicht möglich.
        </p>
      )}
      <Fundstelle h={herkunft} className="mt-3" />
    </Abschnitt>
  );
}

/** Ein Abschnitt, der Fließtext bleibt — und der Rückfall für jeden
 *  Abschnitt, dessen Struktur die Probe nicht bestanden hat.
 *
 *  `whitespace-pre-line`, weil der Bericht in den Listen-Abschnitten je
 *  Eintrag eine Zeile setzt: Zu einem Absatz verschmolzen wären sie unlesbar. */
function Rohtext({ kicker, text, herkunft, note }: {
  kicker: string; text: string; herkunft: ReturnType<typeof herkunftVon>;
  note?: string;
}) {
  return (
    <Abschnitt kicker={kicker}>
      <p className="mt-1.5 max-w-[76ch] whitespace-pre-line text-[13px] leading-relaxed text-foreground/90">
        {text}
      </p>
      {note && (
        <p className="mt-2.5 max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
          {note}
        </p>
      )}
      <Fundstelle h={herkunft} className="mt-3" />
    </Abschnitt>
  );
}

/** Die Zeitreihe einer Kennzahl — als Tabelle, und das ist keine
 *  Bequemlichkeit: Die Reihen sind vier bis acht Werte lang, teils
 *  lückenhaft, und drei Gesellschaften weisen durchgehend 0,00 € aus
 *  (Ergebnisabführung). Eine Kurve daraus zeigte vor allem die Lücken als
 *  Knicke — die Verlaufs-Form zeigt die Sparkline im Kopf. */
function Reihe({ daten, zeilen }: { daten: BeteiligungsDaten; zeilen: Kennzahl[] }) {
  if (!zeilen.length) return null;
  const h = herkunftVon(daten, zeilen[zeilen.length - 1].herkunft_id);
  return (
    <div>
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        {KENNZAHL_TITEL[zeilen[0].indicator]}
      </p>
      <dl className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1.5">
        {zeilen.map((k) => (
          <div key={k.year} className="flex flex-col">
            <dt className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {k.year}
            </dt>
            <dd className="font-display text-[15px] font-semibold tabular-nums">
              {wertText(k)}
            </dd>
          </div>
        ))}
      </dl>
      <Fundstelle h={h} className="mt-2.5" />
    </div>
  );
}

export function Steckbrief({ daten, g, zurueck }: {
  daten: BeteiligungsDaten; g: Gesellschaft; zurueck: () => void;
}) {
  const alleReihen = useMemo(() => reihen(daten, g.company), [daten, g.company]);
  const vergleich = daten.konzernvergleich.find((z) => z.company === g.company);
  const form = rechtsform(g);

  const personen = useMemo(() => aufsichtspersonen(daten, g.company),
    [daten, g.company]);
  const eigentuemer = useMemo(() => eigentuemerVon(daten, g.company),
    [daten, g.company]);
  const text = (key: string) => textVon(daten, g.company, key);
  const gegenstand = text("gegenstand");
  const besitz = text("beteiligungsverhaeltnisse");
  const organe = text("aufsichtsorgane");
  const beteiligungen = text("beteiligungen");
  const haushalt = text("haushalt");

  return (
    <div className="flex flex-col gap-3">
      <button type="button" onClick={zurueck}
        className="group flex items-center gap-1.5 self-start text-[13px] font-semibold text-primary">
        <ArrowLeft size={14} strokeWidth={2}
          className="transition-transform group-hover:-translate-x-0.5" />
        Alle Gesellschaften
      </button>

      <div>
        <p className="flex items-center gap-1.5 font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {form && <FormZeichen form={form} className="h-3 w-3" />}
          {form ? RECHTSFORM_TITEL[form] : "Städtische Einheit"} · Bericht {g.report_year}
        </p>
        <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
          {g.name}
        </h1>
      </div>

      <Zahlenkopf daten={daten} g={g} />

      {gegenstand && (
        <Auftrag text={gegenstand.text} herkunft={herkunftVon(daten, gegenstand.herkunft_id)} />
      )}

      {/* Struktur, wo die Probe sie hergibt — sonst der Wortlaut. */}
      {eigentuemer.length > 0 ? (
        <Eigentuemerstreifen liste={eigentuemer}
          herkunft={herkunftVon(daten, eigentuemer[0].herkunft_id ?? besitz?.herkunft_id ?? null)} />
      ) : besitz ? (
        <Rohtext kicker={TITEL.beteiligungsverhaeltnisse} text={besitz.text}
          herkunft={herkunftVon(daten, besitz.herkunft_id)} />
      ) : null}

      {personen.length > 0 ? (
        <Aufsichtsorgan personen={personen}
          // Ohne Angabe gilt „unbekannt": Eine alte API, die das Feld nicht
          // kennt, darf keine Ämter behaupten.
          zuordenbar={g.roles_assignable === true}
          herkunft={herkunftVon(daten, personen[0].herkunft_id ?? organe?.herkunft_id ?? null)} />
      ) : organe ? (
        <Rohtext kicker={TITEL.aufsichtsorgane} text={organe.text}
          herkunft={herkunftVon(daten, organe.herkunft_id)} />
      ) : null}

      {/* Zwei kurze Abschnitte — je ein bis drei Sätze. Nebeneinander, wo der
          Platz da ist: untereinander ergäben sie zwei fast leere Karten. */}
      {(beteiligungen || haushalt) && (
        <div className={cn("grid gap-3", beteiligungen && haushalt && "breit:grid-cols-2")}>
          {beteiligungen && (
            <Rohtext kicker={TITEL.beteiligungen} text={beteiligungen.text}
              herkunft={herkunftVon(daten, beteiligungen.herkunft_id)} />
          )}
          {haushalt && (
            <Rohtext kicker={TITEL.haushalt} text={haushalt.text}
              herkunft={herkunftVon(daten, haushalt.herkunft_id)} />
          )}
        </div>
      )}

      <Abschnitt kicker="Alle Jahre, die der Bericht führt">
        <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          Dieselben drei Kennzahlen, vollständig statt nur im jüngsten Jahr.
          <Beleg q="beteiligungsbericht" />
        </p>
        <div className="mt-3 flex flex-col gap-4">
          {TRIO.map((k) => (
            <Reihe key={k} daten={daten} zeilen={alleReihen.get(k) ?? []} />
          ))}
        </div>
      </Abschnitt>

      {vergleich && (
        <Abschnitt kicker="Dieselbe Gesellschaft im Gesamtabschluss">
          <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Der{" "}
            <Link href="/haushalt/konzern" className="font-semibold text-primary">
              Gesamtabschluss
            </Link>{" "}
            führt {g.name} als eigenen Aufgabenträger. Er rechnet anders: Dort zählen nur
            die ordentlichen Erträge und Aufwendungen, hier steht das vollständige
            Jahresergebnis der Gesellschaft.
          </p>
          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                Beitrag im Konzern {vergleich.year}
              </dt>
              <dd className="font-display text-[17px] font-bold tabular-nums">
                {eur(vergleich.konzern_beitrag)}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                Jahresergebnis {vergleich.year}
              </dt>
              <dd className="font-display text-[17px] font-bold tabular-nums">
                {eur(vergleich.jahresergebnis)}
              </dd>
            </div>
          </dl>
        </Abschnitt>
      )}
    </div>
  );
}
