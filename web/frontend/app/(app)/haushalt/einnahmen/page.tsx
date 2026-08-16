"use client";

// /haushalt/einnahmen — „Woher kommt das Geld?" (Design H-13).
//
// Die Landkarte aller Einnahmequellen, sortiert nach Betrag, mit der
// Spielraum-Kodierung als eigentlicher Aussage: Bei den meisten Quellen kann
// der Rat gar nichts beschließen. Beträge sind IST-Werte des jüngsten Jahres
// (Open-Data), keine Planwerte — das steht auch so auf der Seite.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltDaten, deMio } from "@/lib/haushalt";
import { SPIELRAUM_LABEL, STEUERARTEN, Spielraum } from "@/lib/haushalt-steuern";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

/** Drei Striche als Spielraum-Marke — gefüllt, halb, gestrichelt. */
function SpielraumMarke({ stufe }: { stufe: Spielraum }) {
  const gefuellt = stufe === "frei" ? 3 : stufe === "begrenzt" ? 2 : 0;
  return (
    <span className="flex flex-none gap-0.5 pt-0.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span key={i} className={cn(
          "h-9 w-1 rounded-sm",
          i < gefuellt
            ? stufe === "frei" ? "bg-[color:var(--hh-ein-0)]" : "bg-[color:var(--hh-ein-2)]"
            : stufe === "keiner" ? "border border-dashed border-border" : "bg-muted",
        )} />
      ))}
    </span>
  );
}

export default function EinnahmenPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Einnahmen werden geladen …</div>;
  }

  const jahr = Math.max(...data.steuern.map((s) => s.jahr), 0);
  const betragFuer = (art: string | null) => {
    if (!art) return null;
    return data.steuern.find((s) => s.jahr === jahr && s.art === art)?.betrag ?? null;
  };
  const zuweisungJahr = data.steuerkraft.filter((k) => k.zuweisungen != null).at(-1);
  const gesamt = data.steuern.find((s) => s.jahr === jahr && s.art === "insgesamt")?.betrag ?? null;

  // Karten: Betrag aus den Daten, Reihenfolge nach Betrag (Quellen ohne Zahl ans Ende).
  const karten = STEUERARTEN.map((a) => ({
    art: a,
    betrag: a.slug === "schluesselzuweisungen" ? zuweisungJahr?.zuweisungen ?? null : betragFuer(a.datenArt),
    jahr: a.slug === "schluesselzuweisungen" ? zuweisungJahr?.jahr ?? jahr : jahr,
  })).sort((a, b) => (b.betrag ?? -1) - (a.betrag ?? -1));

  const frei = karten.filter((k) => k.art.spielraum === "frei").length;

  const quellen: QuellenSchluessel[] = ["steuern", "steuerkraft", "hebesaetze"];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Woher das Geld kommt</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">Woher kommt das Geld?</h1>
        <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
          {karten.length} Quellen — aber nur bei {frei} kann der Rat den Betrag wirklich beeinflussen.
          Die Striche links an jeder Karte zeigen, wie viel Spielraum Oldenburg hat.
        </p>
        {/* Der Jahres-Sprung gehört nach oben, nicht ans Seitenende. Wer von
            der Übersicht kommt, hat dort Planzahlen des kommenden Jahres
            gesehen; hier stehen abgerechnete Werte eines früheren. Ohne den
            Hinweis liest man beide Seiten als dieselbe Rechnung und wundert
            sich über die Differenz. */}
        <p className="mt-2 max-w-[66ch] text-[12.5px] leading-relaxed text-muted-foreground">
          Achtung beim Jahr: Bei den Steuern stehen hier <strong>abgerechnete Beträge
          aus {jahr}</strong> — was wirklich geflossen ist. Die Übersicht zeigt dagegen
          den <em>Plan</em> für ein späteres Jahr. Beide Zahlen sind richtig, sie beantworten nur
          verschiedene Fragen. Jede Karte nennt ihr Jahr selbst — die Schlüsselzuweisungen
          laufen dem Rest voraus.
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          Spielraum des Rats
        </p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {(["frei", "begrenzt", "keiner"] as Spielraum[]).map((s) => (
            <span key={s} className="inline-flex items-center gap-2 text-[11.5px]">
              <span className="flex gap-0.5">
                {[0, 1, 2].map((i) => {
                  const gefuellt = s === "frei" ? 3 : s === "begrenzt" ? 2 : 0;
                  return <span key={i} className={cn(
                    "h-3 w-1 rounded-sm",
                    i < gefuellt
                      ? s === "frei" ? "bg-[color:var(--hh-ein-0)]" : "bg-[color:var(--hh-ein-2)]"
                      : s === "keiner" ? "border border-dashed border-border" : "bg-muted",
                  )} />;
                })}
              </span>
              {SPIELRAUM_LABEL[s]}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {karten.map(({ art, betrag, jahr: bJahr }) => (
          <Link key={art.slug} href={`/haushalt/steuer?art=${art.slug}`}
            className="flex gap-3 rounded-xl border border-border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/40">
            <SpielraumMarke stufe={art.spielraum} />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-bold leading-snug">{art.titel}</p>
              {betrag != null ? (
                <p className="mt-1.5 font-display text-[20px] font-bold leading-none tracking-tight tabular-nums">
                  {deMio(betrag / 1e6)}
                  <span className="text-[11px] font-semibold text-muted-foreground">
                    &#8239;Mio.
                  </span>
                  <span className="ml-1 font-sans text-[10px] font-normal text-muted-foreground">
                    {bJahr}
                    <Beleg q={art.slug === "schluesselzuweisungen" ? "steuerkraft" : "steuern"} />
                  </span>
                </p>
              ) : (
                <p className="mt-1.5 text-[12px] text-muted-foreground">
                  Betrag noch nicht eingelesen
                </p>
              )}
              <p className="mt-1.5 text-[11.5px] leading-snug text-foreground/75">{art.stellschraube}</p>
              <p className="mt-1.5 text-[11.5px] font-semibold text-primary">Steckbrief öffnen →</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Der Satz verglich bis 16.08. die Steuern eines Ist-Jahres mit den
          Ausgaben eines Planjahres („deckt nur einen Teil dessen, was die
          Stadt ausgibt") — zwei Zahlen aus zwei Rechnungen, deren Differenz
          nichts bedeutet. Jetzt bleibt der Vergleich innerhalb derselben
          Quelle: Steuern gegen Steuern plus Zuweisungen.

          Die Zuweisungen tragen ihr eigenes Jahr im Satz, seit die
          Jahres-Korrektur am Datensatz 1106 die beiden Reihen auseinander-
          gezogen hat: Die Steuern enden beim letzten abgerechneten Jahr, der
          Finanzausgleich steht schon für das laufende Ausgleichsjahr fest.
          Ein gemeinsames „brachten 2025" wäre für eine der beiden Zahlen
          falsch. */}
      {gesamt != null && (
        <LottiErklaert
          titel="Was diese Beträge zusammen sind — und was nicht"
          text={`Alle Steuern zusammen brachten ${jahr} rund ${deMio(gesamt / 1e6)} Millionen Euro`
            + (zuweisungJahr?.zuweisungen
              ? `. Dazu kommen die Schlüsselzuweisungen des Landes: für das Ausgleichsjahr `
                + `${zuweisungJahr.jahr} rund ${deMio(zuweisungJahr.zuweisungen / 1e6)} Millionen`
              : "")
            + ". Das ist noch nicht alles, was die Stadt einnimmt: Gebühren, Kostenerstattungen"
            + " und zweckgebundene Zuschüsse kommen hinzu, und die stehen nicht in diesen"
            + " Datensätzen. Die Gesamtsumme aller Einnahmen steht auf der Übersicht."}
        />
      )}

      <p className="text-[11.5px] leading-relaxed text-muted-foreground">
        Die Steuerbeträge sind <strong>Ist-Werte</strong> — also abgerechnete Einnahmen, nicht die
        Planzahlen des Haushalts. Die Aufteilung der geplanten Erträge nach Arten lesen wir
        noch ein; bis dahin zeigen wir hier lieber, was wirklich geflossen ist. Die
        Schlüsselzuweisungen folgen einer anderen Logik: Das Land setzt sie je
        Ausgleichsjahr fest, deshalb steht dort auch das laufende Jahr schon mit einem
        festen Betrag — das Jahr an der Zahl sagt, welches gemeint ist.
      </p>

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
