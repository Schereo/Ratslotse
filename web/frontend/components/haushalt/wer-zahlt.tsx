"use client";

// „Und welche Firmen zahlen das?" — die häufigste Rückfrage zur Gewerbesteuer,
// und die einzige auf dieser Seite, die niemand beantworten darf.
//
// Der Block hat deshalb eine andere Aufgabe als seine Nachbarn: Er zeigt keine
// Zahl, die wir haben, sondern erklärt eine, die es nicht gibt — und was an
// ihre Stelle tritt. Drei Regeln, aus denen er gebaut ist:
//
//  1. **Der Rechtsgrund zuerst.** Was ein einzelnes Unternehmen zahlt, fällt
//     unter das Steuergeheimnis (§ 30 AO). Das ist keine Lücke unseres
//     Bestands, die wir irgendwann schließen — es ist die Rechtslage, und sie
//     gilt auch für die Kämmerei und gegenüber dem Rat. Ohne diesen Satz liest
//     sich der Block wie eine Ankündigung.
//  2. **Der Hinweis aus den Daten, ausdrücklich als Hinweis.** Wie stark das
//     Aufkommen von Jahr zu Jahr springt, steht in derselben Tabelle, aus der
//     die Kurve oben kommt. Verglichen wird mit der Grundsteuer, und zwar aus
//     einem Grund: Bei beiden setzt der Rat einen Hebesatz, beide stehen im
//     selben Datensatz — nur eine der beiden hängt am Gewinn. Der Vergleich
//     mit den anderen Spalten wäre unfair (die Getränkesteuer wird seit 1994
//     nicht mehr erhoben und „schwankt" deshalb um 100 %, die
//     Vergnügungssteuer bewegt Beträge um 3 Mio. €).
//  3. **Kein Superlativ und kein Name.** „Die unruhigste Einnahme der Stadt"
//     wäre falsch gewesen — nachgemessen liegt die Vergnügungssteuer mit 14,9 %
//     fast gleichauf. Und wer die größten Zahler wären, bliebe geraten, auch
//     wenn die Namen naheliegen. Der Block benennt stattdessen den Weg, auf dem
//     man sich der Frage nähert (die Zerlegung nach Arbeitslöhnen), und wo
//     dieser Weg bricht.
//
// Alle Zahlen rechnet die Komponente aus den übergebenen Reihen. Keine steht
// im Quelltext — dieselbe Lehre wie beim Hebesatz „439" (siehe
// `lib/haushalt-steuern.ts`), der hier jahrelang als Konstante stand und nur
// zufällig stimmte.

import { Beleg } from "@/components/haushalt/quelle";
import { GlossaryText } from "@/components/glossary-text";

type SteuerZeile = { jahr: number; art: string; betrag: number | null };
type Hebesatz = { jahr: number; hebesatz: number; vorheriger: number | null };

/** Ab wann ein Jahressprung „groß" heißt. Die Schwelle ist gesetzt, nicht
 *  gemessen — deshalb steht sie im Text, den der Block ausgibt. */
const SPRUNG = 15;

/** Die Ist-Reihe einer Steuerart, aufsteigend und ohne Lücken-Jahre. */
function reihe(zeilen: SteuerZeile[], art: string | null) {
  if (!art) return [];
  return zeilen
    .filter((z) => z.art === art && z.betrag != null && z.betrag > 0)
    .map((z) => ({ jahr: z.jahr, betrag: z.betrag as number }))
    .sort((a, b) => a.jahr - b.jahr);
}

/** Die Veränderung gegenüber dem Vorjahr, in Prozent — je Jahrespaar eines.
 *
 *  Nur unmittelbar aufeinanderfolgende Jahre: Läge im Datensatz eine Lücke,
 *  verglichen wir sonst über sie hinweg und schrieben einen Zweijahres-Sprung
 *  als Jahressprung. */
function aenderungen(r: { jahr: number; betrag: number }[]) {
  return r.slice(1)
    .map((z, i) => ({ jahr: z.jahr, vorjahr: r[i].jahr,
                      prozent: ((z.betrag - r[i].betrag) / r[i].betrag) * 100 }))
    .filter((p) => p.jahr === p.vorjahr + 1);
}

function deProzent(v: number, stellen = 1): string {
  return v.toLocaleString("de-DE", {
    minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

/** Eine Vergleichszeile: Label · Balken · Wert (Baustein RG-04). */
function Zeile({ label, wert, anteil, farbe }: {
  label: string; wert: string; anteil: number; farbe: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-[104px] flex-none text-[12px] leading-tight text-foreground/85 sm:w-[128px]">
        {label}
      </span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted/60">
        <span className="block h-full rounded-full"
          style={{ width: `${Math.max(anteil, 3)}%`, background: farbe }} />
      </span>
      <span className="w-[62px] flex-none text-right font-display text-[15px] font-bold tabular-nums">
        {wert}<span className="text-[11px] font-semibold text-muted-foreground">&nbsp;%</span>
      </span>
    </div>
  );
}

export function WerZahlt({ steuern, art, vergleichArt, vergleichTitel, hebesaetze }: {
  steuern: SteuerZeile[];
  /** Die Schreibweise der Gewerbesteuer in `council_steuern.art`. */
  art: string | null;
  /** Die Steuer, gegen die gemessen wird — die andere mit einem Hebesatz. */
  vergleichArt: string | null;
  vergleichTitel: string;
  /** Die Hebesatz-Treppe DIESER Steuer, für die Frage, ob ein Sprung am Rat lag. */
  hebesaetze: Hebesatz[];
}) {
  const eigen = reihe(steuern, art);
  const andere = reihe(steuern, vergleichArt);

  // Beide Reihen auf denselben Zeitraum: Ein Mittelwert über 28 Jahre neben
  // einem über 12 verglichen zwei verschiedene Epochen und hieße trotzdem
  // „im Schnitt".
  const von = Math.max(eigen[0]?.jahr ?? 0, andere[0]?.jahr ?? 0);
  const bis = Math.min(eigen.at(-1)?.jahr ?? 0, andere.at(-1)?.jahr ?? 0);
  const imFenster = (r: { jahr: number; betrag: number }[]) =>
    r.filter((z) => z.jahr >= von && z.jahr <= bis);

  const eigenAend = aenderungen(imFenster(eigen));
  const andereAend = aenderungen(imFenster(andere));
  // Unter fünf Jahrespaaren ist ein Mittelwert eine Anekdote. Dann bleibt der
  // Messteil weg — der Rechtsgrund steht trotzdem, er hängt an keiner Reihe.
  const misst = eigenAend.length >= 5 && andereAend.length >= 5;

  const mittel = (a: { prozent: number }[]) =>
    a.reduce((s, p) => s + Math.abs(p.prozent), 0) / a.length;
  const eigenMittel = misst ? mittel(eigenAend) : 0;
  const andereMittel = misst ? mittel(andereAend) : 0;
  const skala = Math.max(eigenMittel, andereMittel) || 1;

  const spruenge = eigenAend.filter((p) => Math.abs(p.prozent) > SPRUNG);
  const andereSpruenge = andereAend.filter((p) => Math.abs(p.prozent) > SPRUNG);

  // Hat der Rat in einem Sprungjahr den Hebesatz angefasst? Ausgezählt statt
  // behauptet: Steht im Bestand irgendwann ein Sprung, der doch auf einem
  // Beschluss beruht, sagt der Satz das dann auch.
  //
  // NUR ECHTE ÄNDERUNGEN — dieselbe Bedingung wie in `hebesatz-treppe.tsx`.
  // Tabelle 1105 führt ein Jahr, sobald sich IRGENDEIN Realsteuer-Hebesatz
  // geändert hat, nicht nur der dieser Steuer: 2002 stieg die Grundsteuer,
  // die Gewerbesteuer stand unverändert bei 410 %. Ohne diesen Filter zählte
  // 2002 als Ratsbeschluss, obwohl der Rat an dieser Steuer nichts tat — und
  // der Block schrieb den größten Sprung der Reihe dem falschen Grund zu
  // (gesehen in der Vorschau am 24.08.2026).
  const beschlussJahre = new Set(
    hebesaetze
      .filter((z) => z.vorheriger != null && z.hebesatz !== z.vorheriger)
      .map((z) => z.jahr)
      .filter((j) => j > von && j <= bis));
  const mitBeschluss = spruenge.filter((p) => beschlussJahre.has(p.jahr)).length;

  return (
    <section className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wer zahlt das eigentlich
        </p>
        {misst && (
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            Ist-Jahre {von}–{bis}
          </span>
        )}
      </div>

      <p className="mt-2 max-w-[74ch] text-[13px] leading-relaxed text-foreground/90">
        <strong>Welche Unternehmen die größten Beträge zahlen, darf niemand nennen.</strong>{" "}
        Was eine einzelne Firma an Gewerbesteuer zahlt, fällt unter das{" "}
        <GlossaryText text="Steuergeheimnis" /> (§ 30 Abgabenordnung). Die Kämmerei kennt die
        Namen, veröffentlichen darf sie sie nicht — auch nicht gegenüber dem Rat. In
        Haushaltsberatungen ist deshalb höchstens von „einem Großzahler“ die Rede. Das ist keine
        Lücke, die wir noch schließen: Es gibt keine Kommune in Deutschland, die eine solche
        Liste veröffentlichen dürfte.
      </p>

      {misst && (
        <div className="mt-3 rounded-xl border border-border bg-muted/25 p-3">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Veränderung zum Vorjahr, im Mittel {von}–{bis}
          </p>
          <div className="mt-2.5 flex flex-col gap-2">
            <Zeile label="Gewerbesteuer" wert={deProzent(eigenMittel)}
              anteil={(eigenMittel / skala) * 100} farbe="var(--hh-ein-0)" />
            <Zeile label={vergleichTitel} wert={deProzent(andereMittel)}
              anteil={(andereMittel / skala) * 100} farbe="var(--hh-ein-3)" />
          </div>
          <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
            Unsere Rechnung aus der Ist-Reihe beider Steuern — Beträge ohne Vorzeichen
            gemittelt, damit sich ein gutes und ein schlechtes Jahr nicht aufheben.
            <Beleg q="steuern" />
          </p>
        </div>
      )}

      {misst && (
        <p className="mt-3 max-w-[74ch] text-[13px] leading-relaxed text-foreground/90">
          <strong>Was die Zahlen trotzdem verraten.</strong> Bei beiden Steuern beschließt der
          Rat einen <GlossaryText text="Hebesatz" />, beide stehen im selben Datensatz — die
          Gewerbesteuer bewegt sich trotzdem um ein Vielfaches stärker. In{" "}
          {spruenge.length} der {eigenAend.length} Jahre sprang sie um mehr als {SPRUNG}&nbsp;%,
          die {vergleichTitel}{" "}
          {andereSpruenge.length === 0 ? "in keinem einzigen" : `in ${andereSpruenge.length}`}.
          {mitBeschluss === 0
            ? " In keinem dieser Sprungjahre hatte der Rat den Hebesatz angefasst — was sich"
              + " bewegte, waren die Gewinne."
            : ` In ${mitBeschluss} dieser Jahre hatte der Rat auch den Hebesatz geändert; die`
              + " übrigen Sprünge kamen aus den Gewinnen."}{" "}
          Das <strong>legt nahe</strong>, dass einige wenige große Zahler den Ausschlag geben —
          ein Beweis ist es nicht, denn Gewinne brechen auch dann gemeinsam ein, wenn viele sie
          machen.
        </p>
      )}

      <div className="mt-3 grid gap-x-8 gap-y-3 border-t border-dashed border-border pt-3 @3xl:grid-cols-2">
        <div>
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-primary">
            Woran man sich herantasten kann
          </p>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-[12.5px] leading-relaxed text-foreground/85">
            <li>
              <strong>Die Steuer folgt der Lohnsumme, nicht der Zentrale.</strong> Hat ein
              Unternehmen Standorte in mehreren Gemeinden, wird seine Gewerbesteuer unter ihnen
              aufgeteilt (<GlossaryText text="Zerlegung" />, § 29 Gewerbesteuergesetz) —
              Maßstab sind die Arbeitslöhne je Standort. Wer hier viele Menschen beschäftigt,
              lässt hier auch einen großen Teil seiner Steuer.
            </li>
            <li>
              <strong>Deshalb sind die großen Arbeitgeber der beste öffentliche
              Anhaltspunkt</strong> — die einzige Größe, die überhaupt veröffentlicht wird und
              mit der Steuer zu tun hat.
            </li>
          </ul>
        </div>
        <div>
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Wo die Näherung bricht
          </p>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-[12.5px] leading-relaxed text-foreground/85">
            <li>
              <strong>Die Lohnsumme verteilt die Steuer, sie erzeugt sie nicht.</strong> Wie
              hoch sie überhaupt ausfällt, hängt am Gewinn. Ein Verlustjahr — oder ein Verlust
              aus früheren Jahren, der noch verrechnet wird — setzt auch einen großen
              Arbeitgeber auf null.
            </li>
            <li>
              <strong>Nicht jeder Große zahlt sie.</strong> Gemeinnützige Träger sind
              befreit, öffentliche Einrichtungen sind kein Gewerbebetrieb, Freiberufler und
              Landwirte zahlen ohnehin keine Gewerbesteuer. Wer in einer Beschäftigtenliste
              weit oben steht, kann in dieser Summe komplett fehlen.
            </li>
            <li>
              <strong>Und umgekehrt.</strong> Eine gewinnstarke Gesellschaft mit wenig Personal
              steht in keiner Arbeitgeberliste vorn und kann trotzdem einer der größten Zahler
              sein.
            </li>
          </ul>
        </div>
      </div>

      <p className="mt-3 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Namen nennen wir deshalb keine: Jede Liste an dieser Stelle wäre geraten.
      </p>
    </section>
  );
}
