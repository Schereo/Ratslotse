"use client";

// /haushalt/einnahmen — „Woher kommt das Geld?" (Design H2-07, davor H-13).
//
// Die Landkarte aller Einnahmequellen. Neu in dieser Runde: Sie sind nicht
// mehr nach Betrag sortiert, sondern **nach Entscheidungsmacht gruppiert**.
//
// Warum das die eigentliche Arbeit ist: Nach Betrag sortiert trug jede Karte
// ihr Spielraum-Zeichen selbst — man musste sieben Karten lesen und im Kopf
// zusammenzählen, um die Aussage zu bekommen. Jetzt ist die Gruppierung die
// Aussage, und das Zeichen steht einmal an der Abschnittsüberschrift.
//
// Beträge sind IST-Werte des jüngsten Jahres (Open-Data), keine Planwerte —
// das steht auch so auf der Seite.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltDaten, deMio } from "@/lib/haushalt";
import { SPIELRAUM_LABEL, STEUERARTEN, Spielraum } from "@/lib/haushalt-steuern";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { FinanzausgleichDaempfer } from "@/components/haushalt/finanzausgleich-daempfer";
import { cn } from "@/lib/utils";

/** Drei Striche als Spielraum-Marke — gefüllt, halb, gestrichelt.
 *
 *  `hoch` ist die Balkenhöhe in Viertel-rem: an der Abschnittsüberschrift
 *  klein (Wiedererkennung), in der Legende noch kleiner. */
function SpielraumMarke({ stufe, klasse }: { stufe: Spielraum; klasse: string }) {
  const gefuellt = stufe === "frei" ? 3 : stufe === "begrenzt" ? 2 : 0;
  return (
    <span className="flex flex-none gap-0.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span key={i} className={cn(
          "w-1 rounded-sm", klasse,
          i < gefuellt
            ? stufe === "frei" ? "bg-[color:var(--hh-ein-0)]" : "bg-[color:var(--hh-ein-2)]"
            : stufe === "keiner" ? "border border-dashed border-border" : "bg-muted",
        )} />
      ))}
    </span>
  );
}

/** Was die drei Stufen bedeuten — eine Zeile, die den Gruppentitel trägt.
 *
 *  Bewusst kein Text über „die meisten Einnahmen": Welche Gruppe wie groß
 *  ist, rechnet die Seite unten aus den Daten aus. */
const GRUPPEN: { stufe: Spielraum; titel: string; text: string }[] = [
  {
    stufe: "frei",
    titel: "Der Rat entscheidet",
    text: "Der Rat beschließt den Satz selbst — jedes Jahr mit dem Haushalt.",
  },
  {
    stufe: "begrenzt",
    titel: "Begrenzt",
    text: "Der Rat beschließt, darf aber gesetzlich nicht frei wählen.",
  },
  {
    stufe: "keiner",
    titel: "Kein Einfluss",
    text: "Höhe und Verteilung legen Bund und Land fest.",
  },
];

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

  // Karten: Betrag aus den Daten, innerhalb der Gruppe nach Betrag sortiert
  // (Quellen ohne Zahl ans Ende).
  const karten = STEUERARTEN.map((a) => ({
    art: a,
    betrag: a.slug === "schluesselzuweisungen" ? zuweisungJahr?.zuweisungen ?? null : betragFuer(a.datenArt),
    jahr: a.slug === "schluesselzuweisungen" ? zuweisungJahr?.jahr ?? jahr : jahr,
  })).sort((a, b) => (b.betrag ?? -1) - (a.betrag ?? -1));

  const gruppen = GRUPPEN
    .map((g) => ({ ...g, karten: karten.filter((k) => k.art.spielraum === g.stufe) }))
    .filter((g) => g.karten.length > 0);
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
        {/* Die Überschrift zählt aus den Daten. Der Entwurf schrieb „drei von
            neun" fest — es sind weder drei noch neun, und beides ändert sich,
            sobald eine Einnahmeart dazukommt. */}
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">
          Bei {frei} von {karten.length} Einnahmequellen kann der Rat wirklich drehen
        </h1>
        <p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-foreground/90">
          Die Debatte „die Stadt soll sich das Geld doch besorgen“ läuft meistens an den
          Zuständigkeiten vorbei. Deshalb sortieren wir die Einnahmequellen nicht nach Größe,
          sondern <strong>nach Entscheidungsmacht</strong>. Gezählt sind Quellen, nicht Euro.
        </p>
        {/* Der Jahres-Sprung gehört nach oben, nicht ans Seitenende. Wer von
            der Übersicht kommt, hat dort Planzahlen des kommenden Jahres
            gesehen; hier stehen abgerechnete Werte eines früheren. Ohne den
            Hinweis liest man beide Seiten als dieselbe Rechnung und wundert
            sich über die Differenz. */}
        <p className="mt-2 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
          Achtung beim Jahr: Hier stehen <strong>abgerechnete Beträge aus {jahr}</strong> — was
          wirklich geflossen ist. Die Übersicht zeigt dagegen den <em>Plan</em> für ein späteres
          Jahr. Beide Zahlen sind richtig, sie beantworten nur verschiedene Fragen.
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          Spielraum des Rats
        </p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {(["frei", "begrenzt", "keiner"] as Spielraum[]).map((s) => (
            <span key={s} className="inline-flex items-center gap-2 text-[11.5px]">
              <SpielraumMarke stufe={s} klasse="h-3" />
              {SPIELRAUM_LABEL[s]}
            </span>
          ))}
        </div>
      </div>

      {gruppen.map((g) => (
        <div key={g.stufe}>
          <div className="mb-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <SpielraumMarke stufe={g.stufe} klasse="h-4" />
            <span className="text-[14.5px] font-bold">{g.titel}</span>
            <span className="text-[12.5px] text-muted-foreground">{g.text}</span>
            <span className="hidden h-px flex-1 bg-border sm:block" />
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {g.karten.map(({ art, betrag, jahr: bJahr }) => (
              <Link key={art.slug} href={`/haushalt/steuer?art=${art.slug}`}
                className={cn(
                  "flex flex-col rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/40",
                  // Die erste Gruppe trägt einen Primär-Tint: Sie ist die
                  // Antwort auf die Frage, mit der Leute herkommen.
                  g.stufe === "frei" ? "border-primary/25 bg-primary/[0.04]" : "border-border",
                )}>
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
                <p className="mt-auto pt-1.5 text-[11.5px] font-semibold text-primary">Steckbrief öffnen →</p>
              </Link>
            ))}
          </div>
        </div>
      ))}

      {/* Der Dämpfer schließt die Seite ab, weil er erklärt, warum selbst die
          erste Gruppe weniger Spielraum hat, als sie verspricht. Er nennt
          bewusst keinen Faktor — Begründung im Kopf der Komponente. */}
      <FinanzausgleichDaempfer steuerkraft={data.steuerkraft} />

      {/* Der Satz verglich bis 16.08. die Steuern eines Ist-Jahres mit den
          Ausgaben eines Planjahres („deckt nur einen Teil dessen, was die
          Stadt ausgibt") — zwei Zahlen aus zwei Rechnungen, deren Differenz
          nichts bedeutet. Jetzt bleibt der Vergleich innerhalb derselben
          Quelle: Steuern gegen Steuern plus Zuweisungen. */}
      {gesamt != null && (
        <LottiErklaert
          titel="Was diese Beträge zusammen sind — und was nicht"
          text={`Alle Steuern zusammen brachten ${jahr} rund ${deMio(gesamt / 1e6)} Millionen Euro`
            + (zuweisungJahr?.zuweisungen
              ? `, dazu kamen ${deMio(zuweisungJahr.zuweisungen / 1e6)} Millionen Schlüsselzuweisungen vom Land`
              : "")
            + ". Das ist noch nicht alles, was die Stadt einnimmt: Gebühren, Kostenerstattungen"
            + " und zweckgebundene Zuschüsse kommen hinzu, und die stehen nicht in diesen"
            + " Datensätzen. Die Gesamtsumme aller Einnahmen steht auf der Übersicht."}
        />
      )}

      <p className="text-[11.5px] leading-relaxed text-muted-foreground">
        Alle Beträge sind <strong>Ist-Werte</strong> — also abgerechnete Einnahmen, nicht die
        Planzahlen des Haushalts. Die Aufteilung der geplanten Erträge nach Arten lesen wir
        noch ein; bis dahin zeigen wir hier lieber, was wirklich geflossen ist. Die Einteilung
        in drei Stufen ist unsere Einordnung nach der Rechtslage, keine amtliche Kategorie.
      </p>

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
