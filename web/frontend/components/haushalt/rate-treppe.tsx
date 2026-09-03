"use client";

// Die Hebesatz-Treppe (Steuer-Steckbrief) — 45 Jahre, neun Entscheidungen.
//
// WARUM EINE TREPPE UND KEINE KURVE. Tabelle 1105 führt nur die Jahre, in
// denen sich ein Satz geändert hat (ihre Fußnote sagt das selbst). Zwischen
// zwei Zeilen gilt der Satz unverändert weiter — die Jahre dazwischen fehlen
// also nicht, sie ändern nichts. Eine gerade Verbindung zeigte einen
// langsamen Anstieg über zehn Jahre, wo der Rat einmal entschieden hat.
// Deshalb `<Zeitreihe treppe>` (GB-01, `curveStepAfter`).
//
// WARUM NICHT GB-11 (Zeitstrahl). Der Zeitstrahl war der naheliegende
// Kandidat und ist der falsche: Er ist ein VERFAHRENS-Strahl — Stationen auf
// einer Monatsskala mit „Du bist hier"-Pin und Terminen aus dem
// Ratskalender. Er hat **keine Wertachse**. Die Aussage dieser Reihe ist aber
// genau ein Wert: 300 % (1980) → 539 % (2025). Auf einem Strahl wären das
// neun Textschnipsel; man könnte nicht sehen, dass sich der Satz fast
// verdoppelt hat. Die Form muss die Aussage tragen, nicht der Beschriftung
// überlassen.
//
// DER PFLICHT-KONTEXT. Ein Hebesatz allein sagt nicht, was die Leute zahlen:
// Er wirkt auf eine Bemessungsgrundlage, die Bund und Land festlegen — und
// die kann sich gleichzeitig ändern. 2025 ist der Beweis: Der
// Grundsteuer-B-Satz stieg um 21 %, das Aufkommen SANK um 4,6 %, weil die
// Reform alle Messbeträge neu festsetzte. Deshalb steht unter der Treppe zu
// jeder Änderung das Aufkommen desselben Jahres — aus derselben Quelle, und
// nicht als Fußnote, sondern in derselben Zeile.
//
// KEINE BEWERTUNGSFARBEN. Ein steigender Hebesatz ist keine schlechte
// Nachricht und ein fallendes Aufkommen keine gute; beide Richtungen tragen
// dieselbe neutrale Auszeichnung.

import { useState } from "react";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import { cn } from "@/lib/utils";
import { Einordnung } from "@/components/grafik/einordnung";
import { deZahl, mitVorzeichen } from "@/components/grafik/format";
import { deMio } from "@/lib/haushalt";
import type { HebesatzZeile } from "@/lib/haushalt";

/** Eine Änderung, mit dem, was sie im selben Jahr bewirkt hat. */
type Stufe = {
  year: number;
  rate: number;
  prior_rate: number | null;
  /** Aufkommen im Änderungsjahr und im Jahr davor, in Euro. */
  aufkommen: { vorher: number; nachher: number } | null;
  /** Grund, falls sich auch die Bemessungsgrundlage änderte. */
  bemessung: string | null;
};

export function HebesatzTreppe({
  series, zweitreihe, zweitLabel, title, aufkommen, aufkommenLabel,
  bemessungNeu, abgrenzung, grundlage, beleg, aufkommenBeleg,
}: {
  /** Die Änderungsjahre DIESER Steuer, aufsteigend. */
  series: HebesatzZeile[];
  /** Zweiter Satz derselben Steuer in derselben Einheit (Grundsteuer A neben B). */
  zweitreihe?: HebesatzZeile[];
  zweitLabel?: string;
  title: string;
  /** Die Ist-Reihe dieser Steuer, `{year: euro}` — der Pflicht-Kontext. */
  aufkommen: Record<number, number>;
  /** Wie das Aufkommen heißt. Bei der Grundsteuer NICHT dasselbe wie der
   *  Hebesatz daneben: Der offene Datensatz führt A und B in einer Spalte. */
  aufkommenLabel: string;
  bemessungNeu: Record<string, string>;
  abgrenzung: string;
  /** Woran die Bemessungsgrundlage DIESER Steuer hängt — ein Satz, der die
   *  Zeilen darüber erklärt.
   *
   *  Ohne ihn liest sich die Liste falsch herum: Bei der Gewerbesteuer fiel
   *  2011 das Aufkommen um 5,9 %, obwohl der Rat den Hebesatz erhöhte. Wer nur
   *  die beiden Zahlen sieht, schließt daraus, ein höherer Satz bringe weniger
   *  Geld. Tatsächlich sind es die Gewinne, die sich bewegt haben. */
  grundlage?: string;
  beleg?: React.ReactNode;
  aufkommenBeleg?: React.ReactNode;
}) {
  // Bild ↔ Liste (seit 02.09.): `vonListe` ist das Jahr unter dem Zeiger in
  // der Liste (wählt die Stufe im Bild), `vomBild` das Jahr, das das Bild
  // gerade zeigt (hebt die Zeile hervor). Zwei Werte, damit nichts kreist.
  const [vonListe, setVonListe] = useState<number | null>(null);
  const [vomBild, setVomBild] = useState<number | null>(null);
  if (series.length < 2) return null;
  const sortiert = [...series].sort((a, b) => a.year - b.year);

  const stufen: Stufe[] = sortiert.map((z) => {
    const vorher = aufkommen[z.year - 1];
    const nachher = aufkommen[z.year];
    return {
      year: z.year,
      rate: z.rate,
      prior_rate: z.prior_rate,
      aufkommen: vorher != null && nachher != null ? { vorher, nachher } : null,
      bemessung: bemessungNeu[String(z.year)] ?? null,
    };
  });

  // Nur die Jahre, in denen sich DIESER Satz geändert hat. Die Tabelle führt
  // eine Zeile, sobald sich EINER der drei Sätze bewegt — 1997 etwa änderte
  // nur die Gewerbesteuer. Ein „445 → 445 %" im Steckbrief der Grundsteuer
  // wäre eine Änderung, die es nicht gab.
  const echteAenderungen = stufen.filter(
    (s) => s.prior_rate == null || s.rate !== s.prior_rate);
  const erste = sortiert[0];
  const letzte = sortiert[sortiert.length - 1];
  const ohneAufkommen = echteAenderungen.filter(
    (s) => s.prior_rate != null && !s.aufkommen).map((s) => s.year);


  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Der Hebesatz im Rat
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {erste.year}–{letzte.year} · {echteAenderungen.length - 1}{" "}
          {echteAenderungen.length - 1 === 1 ? "Änderung" : "Änderungen"}
        </span>
      </div>
      <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
        Diese eine Zahl beschließt der Rat. Sie gilt, bis er sie wieder ändert —
        deshalb ist das eine Treppe und keine Kurve: Zwischen zwei Stufen ist
        nichts passiert, nicht etwas Unbekanntes.
      </p>

      <div className="mt-3">
        <Zeitreihe
          treppe
          series={sortiert.map((z) => ({ year: z.year, value: z.rate }))}
          zweitreihe={zweitreihe && zweitreihe.length >= 2 && zweitLabel
            ? {
              label: zweitLabel,
              series: [...zweitreihe].sort((a, b) => a.year - b.year)
                .map((z) => ({ year: z.year, value: z.rate })),
              format: (v) => `${deZahl(v, 0)} %`,
            }
            : undefined}
          unit="%"
          nachkomma={0}
          format={(v) => deZahl(v, 0)}
          ariaTitel={`Hebesatz der ${title} von ${erste.year} bis ${letzte.year},`
            + ` ${echteAenderungen.length - 1} Änderungen, zuletzt`
            + ` ${deZahl(letzte.rate, 0)} Prozent`}
          /* Keine `tabelle`: Die Werte stehen unten ohnehin einzeln — und dort
             mit dem Aufkommen daneben, ohne das ein Hebesatz irreführt. */
          note="Prozentpunkte · Jahr überfahren, antippen oder mit den Pfeiltasten wechseln. Die Liste darunter zeigt mit."
          beleg={beleg}
          aktivesJahr={vonListe}
          onAktivesJahr={setVomBild}
        />
      </div>

      {/* Der Pflicht-Kontext: was die Änderung im selben Jahr bewirkt hat. */}
      <div className="mt-3 border-t border-dashed border-border pt-3">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
          Was sich wann geändert hat — und was hereinkam
        </p>
        <ul className="mt-2 flex flex-col gap-2">
          {echteAenderungen.filter((s) => s.prior_rate != null).map((s) => {
            const punkte = s.rate - (s.prior_rate as number);
            const relativ = (s.rate / (s.prior_rate as number) - 1) * 100;
            const auf = s.aufkommen;
            const aufRelativ = auf ? (auf.nachher / auf.vorher - 1) * 100 : null;
            const hervorgehoben = vomBild === s.year;
            return (
              /* Die Zeile zeigt auf ihre Stufe und die Stufe auf ihre Zeile:
                 Zeigen oder Fokus wählt das Jahr im Bild, das Bild hebt die
                 Zeile hervor. `tabIndex` macht die Zeile zum Tastaturziel. */
              <li
                key={s.year}
                tabIndex={0}
                onMouseEnter={() => setVonListe(s.year)}
                onMouseLeave={() => setVonListe(null)}
                onFocus={() => setVonListe(s.year)}
                onBlur={() => setVonListe(null)}
                className={cn(
                  "rounded-xl p-2.5 transition-colors duration-200",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
                  hervorgehoben ? "bg-primary/[0.07] ring-1 ring-inset ring-primary/25" : "bg-muted/30",
                )}
              >
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {s.year}
                  </span>
                  <span className="text-[12.5px] font-semibold tabular-nums">
                    {deZahl(s.prior_rate, 0)} → {deZahl(s.rate, 0)}&nbsp;%
                  </span>
                  <span className="text-[11.5px] tabular-nums text-muted-foreground">
                    {mitVorzeichen(punkte, 0)} Punkte · {mitVorzeichen(relativ)}&nbsp;%
                  </span>
                </div>
                {auf && aufRelativ != null && (
                  <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                    {aufkommenLabel} im selben Jahr:{" "}
                    <span className="tabular-nums text-foreground/85">
                      {deMio(auf.vorher / 1e6)} → {deMio(auf.nachher / 1e6)}&nbsp;Mio.&nbsp;€
                      {" "}({mitVorzeichen(aufRelativ)}&nbsp;%)
                    </span>
                    {aufkommenBeleg}
                  </p>
                )}
                {s.bemessung && (
                  /* Gestrichelt = „nicht von uns / gehört dazu" (Designsprache
                     §4). Kein Warn-Gelb: Eine Reform ist keine Störung. */
                  <p className="mt-1.5 rounded-lg border border-dashed border-border p-2 text-[11.5px] leading-relaxed text-foreground/80">
                    {s.bemessung}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="mt-3">
        <Einordnung
          satz={<>Ein Hebesatz allein sagt nicht, was jemand zahlt. Er wird mit
            einem Messbetrag multipliziert, den das Finanzamt nach Bundes- und
            Landesrecht festsetzt — ändert sich der, verschiebt sich das
            Ergebnis, ohne dass der Rat etwas beschlossen hätte.
            {grundlage ? <> {grundlage}</> : null}</>}
          gemessen={`${echteAenderungen.length - 1} Änderungen in `
            + `${letzte.year - erste.year} Jahren`}
          nichtAussagen={[
            `Die Tabelle nennt nur Änderungsjahre. Zwischen zwei Stufen ist der Satz unverändert geblieben — wir rechnen dort nichts dazwischen.`,
            `Abgrenzung der Quelle: ${abgrenzung}`,
            ...(ohneAufkommen.length
              ? [`Für ${ohneAufkommen.join(", ")} steht kein Aufkommen daneben: Die Reihe der Steuereinnahmen beginnt erst 1998.`]
              : []),
          ]}
        />
      </div>
    </div>
  );
}
