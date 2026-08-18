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
// einer Monatsskala mit „Sie sind hier"-Pin und Terminen aus dem
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

import { Zeitreihe } from "@/components/grafik/zeitreihe";
import { Einordnung } from "@/components/grafik/einordnung";
import { deZahl, mitVorzeichen } from "@/components/grafik/format";
import { deMio } from "@/lib/haushalt";
import type { HebesatzZeile } from "@/lib/haushalt";

/** Eine Änderung, mit dem, was sie im selben Jahr bewirkt hat. */
type Stufe = {
  jahr: number;
  hebesatz: number;
  vorheriger: number | null;
  /** Aufkommen im Änderungsjahr und im Jahr davor, in Euro. */
  aufkommen: { vorher: number; nachher: number } | null;
  /** Grund, falls sich auch die Bemessungsgrundlage änderte. */
  bemessung: string | null;
};

export function HebesatzTreppe({
  reihe, zweitreihe, zweitLabel, titel, aufkommen, aufkommenLabel,
  bemessungNeu, abgrenzung, grundlage, beleg, aufkommenBeleg,
}: {
  /** Die Änderungsjahre DIESER Steuer, aufsteigend. */
  reihe: HebesatzZeile[];
  /** Zweiter Satz derselben Steuer in derselben Einheit (Grundsteuer A neben B). */
  zweitreihe?: HebesatzZeile[];
  zweitLabel?: string;
  titel: string;
  /** Die Ist-Reihe dieser Steuer, `{jahr: euro}` — der Pflicht-Kontext. */
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
  if (reihe.length < 2) return null;
  const sortiert = [...reihe].sort((a, b) => a.jahr - b.jahr);

  const stufen: Stufe[] = sortiert.map((z) => {
    const vorher = aufkommen[z.jahr - 1];
    const nachher = aufkommen[z.jahr];
    return {
      jahr: z.jahr,
      hebesatz: z.hebesatz,
      vorheriger: z.vorheriger,
      aufkommen: vorher != null && nachher != null ? { vorher, nachher } : null,
      bemessung: bemessungNeu[String(z.jahr)] ?? null,
    };
  });

  // Nur die Jahre, in denen sich DIESER Satz geändert hat. Die Tabelle führt
  // eine Zeile, sobald sich EINER der drei Sätze bewegt — 1997 etwa änderte
  // nur die Gewerbesteuer. Ein „445 → 445 %" im Steckbrief der Grundsteuer
  // wäre eine Änderung, die es nicht gab.
  const echteAenderungen = stufen.filter(
    (s) => s.vorheriger == null || s.hebesatz !== s.vorheriger);
  const erste = sortiert[0];
  const letzte = sortiert[sortiert.length - 1];
  const ohneAufkommen = echteAenderungen.filter(
    (s) => s.vorheriger != null && !s.aufkommen).map((s) => s.jahr);

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Der Hebesatz im Rat
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {erste.jahr}–{letzte.jahr} · {echteAenderungen.length - 1}{" "}
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
          reihe={sortiert.map((z) => ({ jahr: z.jahr, wert: z.hebesatz }))}
          zweitreihe={zweitreihe && zweitreihe.length >= 2 && zweitLabel
            ? {
              label: zweitLabel,
              reihe: [...zweitreihe].sort((a, b) => a.jahr - b.jahr)
                .map((z) => ({ jahr: z.jahr, wert: z.hebesatz })),
              format: (v) => `${deZahl(v, 0)} %`,
            }
            : undefined}
          einheit="%"
          nachkomma={0}
          format={(v) => deZahl(v, 0)}
          ariaTitel={`Hebesatz der ${titel} von ${erste.jahr} bis ${letzte.jahr},`
            + ` ${echteAenderungen.length - 1} Änderungen, zuletzt`
            + ` ${deZahl(letzte.hebesatz, 0)} Prozent`}
          /* Keine `tabelle`: Die Werte stehen unten ohnehin einzeln — und dort
             mit dem Aufkommen daneben, ohne das ein Hebesatz irreführt. */
          hinweis="Prozentpunkte · Jahr überfahren, antippen oder mit den Pfeiltasten wechseln."
          beleg={beleg}
        />
      </div>

      {/* Der Pflicht-Kontext: was die Änderung im selben Jahr bewirkt hat. */}
      <div className="mt-3 border-t border-dashed border-border pt-3">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
          Was sich wann geändert hat — und was hereinkam
        </p>
        <ul className="mt-2 flex flex-col gap-2">
          {echteAenderungen.filter((s) => s.vorheriger != null).map((s) => {
            const punkte = s.hebesatz - (s.vorheriger as number);
            const relativ = (s.hebesatz / (s.vorheriger as number) - 1) * 100;
            const auf = s.aufkommen;
            const aufRelativ = auf ? (auf.nachher / auf.vorher - 1) * 100 : null;
            return (
              <li key={s.jahr} className="rounded-xl bg-muted/30 p-2.5">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {s.jahr}
                  </span>
                  <span className="text-[12.5px] font-semibold tabular-nums">
                    {deZahl(s.vorheriger, 0)} → {deZahl(s.hebesatz, 0)}&nbsp;%
                  </span>
                  <span className="text-[11.5px] tabular-nums text-muted-foreground">
                    {mitVorzeichen(punkte, 0)} Punkte · {mitVorzeichen(relativ)}&nbsp;%
                  </span>
                </div>
                <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                  {auf && aufRelativ != null ? (
                    <>
                      {aufkommenLabel} im selben Jahr:{" "}
                      <span className="tabular-nums text-foreground/85">
                        {deMio(auf.vorher / 1e6)} → {deMio(auf.nachher / 1e6)}&nbsp;Mio.&nbsp;€
                        {" "}({mitVorzeichen(aufRelativ)}&nbsp;%)
                      </span>
                      {aufkommenBeleg}
                    </>
                  ) : (
                    <>Was in diesem Jahr hereinkam, wissen wir nicht: Die
                      Aufkommensreihe der Stadt beginnt später.</>
                  )}
                </p>
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
            + `${letzte.jahr - erste.jahr} Jahren`}
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
