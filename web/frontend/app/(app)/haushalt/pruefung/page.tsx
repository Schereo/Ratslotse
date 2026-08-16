"use client";

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
// - Keine Bewertungsfarben (siehe components/haushalt/marke.tsx).
// - Wo die Verwaltung geantwortet hat, steht die Antwort daneben.
//
// Leserichtung: Was ist das → wie viel ist es → was heißen die Marken → was
// steht seit Jahren offen (die eigentliche Nachricht) → Bericht für Bericht.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, ExternalLink } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  Feststellung, PruefberichtDaten, belegLink, markenZaehlen, markeRang,
  nachAbschnitt, wiederholungsketten,
} from "@/lib/haushalt-pruefung";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { MarkePille } from "@/components/haushalt/marke";
import { cn } from "@/lib/utils";

const QUELLEN: QuellenSchluessel[] = ["pruefbericht", "jahresabschluss"];

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
        <MarkePille marke={f.marke} name={f.marke_name} klein />
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {zeigeJahr && <>{f.jahr} · </>}
          Textziffer {f.textziffer}
          {f.seite != null && <> · Seite {f.seite}</>}
        </span>
      </div>
      <Wortlaut text={f.text} />
      {f.folgeabsatz && (
        <div className="pl-3">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
            Im Bericht direkt darauf
          </p>
          <div className="mt-1"><Wortlaut text={f.folgeabsatz} gedaempft /></div>
        </div>
      )}
      {link && (
        <a href={link} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 pl-3 text-[11.5px] font-semibold text-primary">
          Im Schlussbericht {f.jahr} nachlesen
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}

/** Kettenband: je Jahrgang eine Zelle mit der Marke, die der Abschnitt dort
 *  trug — leer, wo der Bericht nichts vermerkt hat. Das ist der ganze Punkt
 *  einer „wiederholten Beanstandung": Man sieht die Reihe, nicht nur das Wort. */
function Kettenband({ jahre, eintraege }: { jahre: number[]; eintraege: Feststellung[] }) {
  return (
    <div className="scrollbar-none -mx-0.5 flex gap-1 overflow-x-auto px-0.5 py-0.5">
      {jahre.map((jahr) => {
        const hier = eintraege.filter((f) => f.jahr === jahr)
          .sort((a, b) => markeRang(a.marke) - markeRang(b.marke));
        const marke = hier[0]?.marke;
        const schwer = marke === "B" || marke === "WB";
        return (
          <div key={jahr} className={cn(
            "flex flex-none flex-col items-center rounded-lg border px-2 py-1",
            marke ? (schwer ? "border-foreground/25 bg-card" : "border-border bg-card") : "border-dashed border-border",
          )}>
            <span className={cn(
              "font-mono text-[11px] leading-none",
              schwer ? "font-bold text-foreground" : "text-muted-foreground",
            )}>
              {marke ?? "·"}
            </span>
            <span className="mt-1 font-mono text-[9px] leading-none text-muted-foreground">{jahr}</span>
          </div>
        );
      })}
    </div>
  );
}

function PruefungInner() {
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<PruefberichtDaten>("/council/haushalt/pruefberichte");
  const [offen, setOffen] = useState<string | null>(null);

  const jahre = data?.jahre ?? [];
  const jahr = gewaehltesJahr && jahre.includes(gewaehltesJahr) ? gewaehltesJahr : jahre.at(-1) ?? null;
  const alle = useMemo(() => data?.feststellungen ?? [], [data]);
  const ketten = useMemo(() => wiederholungsketten(alle), [alle]);
  const zahl = useMemo(() => markenZaehlen(alle), [alle]);
  const gruppen = useMemo(() => (jahr ? nachAbschnitt(alle, jahr) : []), [alle, jahr]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!jahr || !alle.length) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt bisher ein ausgelesener Schlussbericht vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const marken = Object.keys(data.legende).sort((a, b) => markeRang(a) - markeRang(b));
  const hinweise = zahl["H"] ?? 0;
  const beanstandungen = (zahl["B"] ?? 0) + (zahl["WB"] ?? 0);

  return (
    <Quellenkontext schluessel={QUELLEN}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Die Prüfung</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">
          Was das Rechnungsprüfungsamt beanstandet
        </h1>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Jeder Jahresabschluss der Stadt wird geprüft — von einer eigenen Stelle, die dem Rat
          berichtet und nicht der Verwaltungsspitze untersteht. Ihre Befunde stehen in einem
          Schlussbericht, der als Anlage an einer Ratsvorlage hängt. Hier sind sie einzeln
          aufgeführt, im Wortlaut und mit der Fundstelle.
        </p>
      </div>

      {/* Wie viel ist es — und wovon das meiste. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {jahre.length} geprüfte Jahresabschlüsse · {jahre[0]}–{jahre.at(-1)}
        </p>
        <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-foreground/90">
          In diesen Berichten stehen{" "}
          <strong>{alle.length} Feststellungen</strong><Beleg q="pruefbericht" />. Die große
          Mehrheit sind <strong>{hinweise} Hinweise</strong> — Dinge, die künftig zu beachten
          sind. Als Beanstandung, also als bedeutsamer Mangel, sind{" "}
          <strong>{beanstandungen}</strong> ausgewiesen, davon {zahl["WB"] ?? 0} als wiederholt:
          ein Mangel, der schon in einem Vorjahr festgestellt und noch nicht ausgeräumt war.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/60 pt-3">
          {marken.map((m) => (
            <span key={m} className="inline-flex items-baseline gap-1.5">
              <MarkePille marke={m} name={data.legende[m].name} />
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
              <dt className="flex-none"><MarkePille marke={m} name={data.legende[m].name} klein /></dt>
              <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                {data.legende[m].erlaeuterung ?? "—"}
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
        titel="Wer hier eigentlich prüft"
        text="Das Rechnungsprüfungsamt gehört zur Stadt, arbeitet aber für den Rat und nicht für die Verwaltungsspitze. Es schaut jedes Jahr nach, ob der Jahresabschluss stimmt und ob nach den Regeln gewirtschaftet wurde. Ein Hinweis ist dabei kein Vorwurf, sondern eine Notiz für das nächste Mal — erst eine Beanstandung meint einen bedeutsamen Mangel."
      />

      {/* Die eigentliche Nachricht: was seit Jahren offen ist. */}
      {ketten.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Was über Jahre offen blieb
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {ketten.length} Themen · {jahre[0]}–{jahre.at(-1)}
            </span>
          </div>
          <p className="mb-3 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Hier steht nur, was das Rechnungsprüfungsamt selbst als <em>wiederholte</em>{" "}
            Beanstandung ausgewiesen hat — also seine eigene Aussage, dass ein Mangel aus einem
            Vorjahr noch offen war. Zugeordnet wird über den Abschnitt des Berichts; die
            Textziffern verschieben sich zwischen den Jahrgängen.
          </p>
          <div className="flex flex-col gap-3">
            {ketten.map((k) => {
              const auf = offen === k.schluessel;
              return (
                <div key={k.schluessel} className="border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <div className="min-w-0">
                      <p className="font-display text-[15px] font-bold leading-snug tracking-tight">
                        {k.titel}
                      </p>
                      <p className="mt-0.5 text-[12px] text-muted-foreground">
                        In {k.beanstandet.length} von {jahre.length} Berichten beanstandet
                        {k.beanstandet.length > 0 && <> · zuletzt {k.beanstandet.at(-1)}</>}
                      </p>
                    </div>
                    <div className="flex-none"><Kettenband jahre={jahre} eintraege={k.eintraege} /></div>
                  </div>
                  <button type="button" onClick={() => setOffen(auf ? null : k.schluessel)}
                    aria-expanded={auf}
                    className="mt-1.5 text-[12px] font-semibold text-primary">
                    {auf ? "Wortlaut ausblenden" : `Wortlaut aller ${k.eintraege.length} Feststellungen`}
                  </button>
                  {auf && (
                    <div className="mt-2.5 flex flex-col gap-3">
                      {k.eintraege.map((f) => (
                        <FeststellungsZeile key={`${f.jahr}-${f.lfd}`} f={f} zeigeJahr />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bericht für Bericht */}
      <div className="flex flex-col gap-1.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Geprüfter Jahresabschluss
        </span>
        <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
          <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
            {jahre.map((j) => (
              <Link key={j} href={`/haushalt/pruefung?jahr=${j}`} scroll={false}
                className={cn("rounded-full px-3 py-1 text-[12.5px]",
                  j === jahr ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
                {j}
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Schlussbericht zum Jahresabschluss {jahr}
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {alle.filter((f) => f.jahr === jahr).length} Feststellungen · {gruppen.length} Abschnitte
          </span>
        </div>
        <div className="mt-3 flex flex-col gap-4">
          {gruppen.map((g) => (
            <div key={g.textziffer} className="border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
              <p className="font-display text-[14.5px] font-bold leading-snug tracking-tight">
                <span className="font-mono text-[11px] font-medium text-muted-foreground">{g.textziffer}</span>{" "}
                {g.abschnitt}
              </p>
              <div className="mt-2.5 flex flex-col gap-3">
                {g.eintraege.map((f) => <FeststellungsZeile key={f.lfd} f={f} />)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Es erscheinen nur Jahrgänge, deren Schlussbericht die Prüfung besteht: Jede Marke muss in
        der Legende des Berichts erklärt sein und unter einer Textziffer seines
        Inhaltsverzeichnisses stehen.
        {data.ohne_bericht.length > 0 && (
          <>
            {" "}Für {data.ohne_bericht.join(", ")} liegt ein ausgelesener Jahresabschluss vor, der
            Schlussbericht aber nicht in lesbarer Form — sein PDF bringt keine Zeichenzuordnung
            mit, und eine zweite Kopie gibt es nicht<Beleg q="pruefbericht" />. Wir lesen dann
            lieber nichts als etwas Geratenes.
          </>
        )}{" "}
        Die Feststellungen stehen im Wortlaut des Berichts; Zeilenumbrüche des PDF-Textes sind
        zusammengezogen, sonst ist nichts verändert.
      </p>

      <Quellenverzeichnis schluessel={QUELLEN} />
    </div>
    </Quellenkontext>
  );
}

export default function PruefungPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}>
      <PruefungInner />
    </Suspense>
  );
}
