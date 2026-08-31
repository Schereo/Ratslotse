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
//  4. **Der Nenner darf gesagt werden.** Seit 08/2026 steht er auch da: Wie
//     viele Betriebe erfasst sind und wie viele davon überhaupt zahlen,
//     veröffentlicht das Landesamt für Statistik je Gemeinde
//     (`council/trade_tax_statistics.py`). Zwei Dinge gehören zwingend
//     daneben, und beide stehen im Block: Das ist die **Veranlagung**, nicht
//     das Aufkommen der Kurve weiter oben (Messbetrag mal Hebesatz lag in den
//     prüfbaren Jahren zwischen 13 % darunter und 27 % darüber) — und der
//     Jahrgang ist ein anderer, weil die Statistik rund fünf Jahre nachhinkt.
//     Was die Statistik NICHT hergibt, ist die Konzentration: Größenklassen des
//     Gewerbeertrags gibt es nur fürs Land. Deshalb steht hier kein
//     „x % tragen y %", sondern die Aufteilung, die je Gemeinde veröffentlicht
//     wird — reine Festsetzung gegen Zerlegung.
//
// Alle Zahlen rechnet die Komponente aus den übergebenen Reihen. Keine steht
// im Quelltext — dieselbe Lehre wie beim Hebesatz „439" (siehe
// `lib/haushalt-taxes.ts`), der hier jahrelang als Konstante stand und nur
// zufällig stimmte.

import { Beleg } from "@/components/haushalt/quelle";
import { Gesetz } from "@/components/haushalt/gesetz";
import { GlossaryText } from "@/components/glossary-text";
import type { GewerbesteuerstatistikZeile } from "@/lib/haushalt";

type SteuerZeile = { year: number; art: string; amount: number | null };
type Hebesatz = { year: number; rate: number; prior_rate: number | null };

/** Ab wann ein Jahressprung „groß" heißt. Die Schwelle ist gesetzt, nicht
 *  gemessen — deshalb steht sie im Text, den der Block ausgibt. */
const SPRUNG = 15;

/** Die Ist-Reihe einer Steuerart, aufsteigend und ohne Lücken-Jahre. */
function series(zeilen: SteuerZeile[], art: string | null) {
  if (!art) return [];
  return zeilen
    .filter((z) => z.art === art && z.amount != null && z.amount > 0)
    .map((z) => ({ year: z.year, amount: z.amount as number }))
    .sort((a, b) => a.year - b.year);
}

/** Die Veränderung gegenüber dem Vorjahr, in Prozent — je Jahrespaar eines.
 *
 *  Nur unmittelbar aufeinanderfolgende Jahre: Läge im Datensatz eine Lücke,
 *  verglichen wir sonst über sie hinweg und schrieben einen Zweijahres-Sprung
 *  als Jahressprung. */
function aenderungen(r: { year: number; amount: number }[]) {
  return r.slice(1)
    .map((z, i) => ({ year: z.year, prior_year: r[i].year,
                      percent: ((z.amount - r[i].amount) / r[i].amount) * 100 }))
    .filter((p) => p.year === p.prior_year + 1);
}

function deProzent(v: number, stellen = 1): string {
  return v.toLocaleString("de-DE", {
    minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

function deZahl(v: number): string {
  return Math.round(v).toLocaleString("de-DE");
}

/** Eine Zahl mit ihrer Erklärung darunter — die drei Kacheln des Nenners.
 *
 *  `betont` markiert die eine Zahl, um die es geht (wie viele zahlen). Die
 *  beiden anderen sind ihr Bezug; alle drei gleich laut zu setzen hieße, die
 *  Frage nicht zu beantworten. */
function Kennzahl({ wert, einheit, label, betont = false }: {
  wert: string; einheit?: string; label: string; betont?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className={betont
        ? "font-display text-[24px] font-bold leading-none tabular-nums text-primary"
        : "font-display text-[24px] font-bold leading-none tabular-nums text-foreground"}>
        {wert}
        {einheit && (
          <span className="ml-0.5 text-[14px] font-semibold text-muted-foreground">
            {einheit}
          </span>
        )}
      </span>
      <span className="text-[11.5px] leading-snug text-muted-foreground">{label}</span>
    </div>
  );
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

export function WerZahlt({ taxes, art, vergleichArt, vergleichTitel, tax_rates,
                           statistik = null, statistikKurz = "",
                           statistikAbgrenzung = "" }: {
  taxes: SteuerZeile[];
  /** Die Schreibweise der Gewerbesteuer in `council_steuern.art`. */
  art: string | null;
  /** Die Steuer, gegen die gemessen wird — die andere mit einem Hebesatz. */
  vergleichArt: string | null;
  vergleichTitel: string;
  /** Die Hebesatz-Treppe DIESER Steuer, für die Frage, ob ein Sprung am Rat lag. */
  tax_rates: Hebesatz[];
  /** Der jüngste Erhebungsjahrgang der Gewerbesteuerstatistik — der Nenner.
   *  `null`, solange der Ingest auf dieser Maschine nicht lief; dann bleibt
   *  der Block, was er vorher war. */
  statistik?: GewerbesteuerstatistikZeile | null;
  /** Der eine Satz, ohne den die Zahlen irreführen — steht immer sichtbar. */
  statistikKurz?: string;
  /** Der Rest der Abgrenzung, im Wortlaut der API. Steht hinter „Was diese
   *  Zahlen genau umfassen" — und **nicht** hier im Quelltext, sonst driftet
   *  er gegen die Angabe an den Daten. */
  statistikAbgrenzung?: string;
}) {
  const eigen = series(taxes, art);
  const andere = series(taxes, vergleichArt);

  // Beide Reihen auf denselben Zeitraum: Ein Mittelwert über 28 Jahre neben
  // einem über 12 verglichen zwei verschiedene Epochen und hieße trotzdem
  // „im Schnitt".
  const von = Math.max(eigen[0]?.year ?? 0, andere[0]?.year ?? 0);
  const bis = Math.min(eigen.at(-1)?.year ?? 0, andere.at(-1)?.year ?? 0);
  const imFenster = (r: { year: number; amount: number }[]) =>
    r.filter((z) => z.year >= von && z.year <= bis);

  const eigenAend = aenderungen(imFenster(eigen));
  const andereAend = aenderungen(imFenster(andere));
  // Unter fünf Jahrespaaren ist ein Mittelwert eine Anekdote. Dann bleibt der
  // Messteil weg — der Rechtsgrund steht trotzdem, er hängt an keiner Reihe.
  const misst = eigenAend.length >= 5 && andereAend.length >= 5;

  const mittel = (a: { percent: number }[]) =>
    a.reduce((s, p) => s + Math.abs(p.percent), 0) / a.length;
  const eigenMittel = misst ? mittel(eigenAend) : 0;
  const andereMittel = misst ? mittel(andereAend) : 0;
  const skala = Math.max(eigenMittel, andereMittel) || 1;

  const spruenge = eigenAend.filter((p) => Math.abs(p.percent) > SPRUNG);
  const andereSpruenge = andereAend.filter((p) => Math.abs(p.percent) > SPRUNG);

  // Hat der Rat in einem Sprungjahr den Hebesatz angefasst? Ausgezählt statt
  // behauptet: Steht im Bestand irgendwann ein Sprung, der doch auf einem
  // Beschluss beruht, sagt der Satz das dann auch.
  //
  // NUR ECHTE ÄNDERUNGEN — dieselbe Bedingung wie in `rate-treppe.tsx`.
  // Tabelle 1105 führt ein Jahr, sobald sich IRGENDEIN Realsteuer-Hebesatz
  // geändert hat, nicht nur der dieser Steuer: 2002 stieg die Grundsteuer,
  // die Gewerbesteuer stand unverändert bei 410 %. Ohne diesen Filter zählte
  // 2002 als Ratsbeschluss, obwohl der Rat an dieser Steuer nichts tat — und
  // der Block schrieb den größten Sprung der Reihe dem falschen Grund zu
  // (gesehen in der Vorschau am 24.08.2026).
  const beschlussJahre = new Set(
    tax_rates
      .filter((z) => z.prior_rate != null && z.rate !== z.prior_rate)
      .map((z) => z.year)
      .filter((j) => j > von && j <= bis));
  const mitBeschluss = spruenge.filter((p) => beschlussJahre.has(p.year)).length;

  // --- Der Nenner ---------------------------------------------------------
  // Alles gerechnet, nichts geschrieben: Kommt ein neuer Erhebungsjahrgang
  // herein, ändern sich die Sätze mit. Der Zerlegungs-Anteil bleibt weg, wo
  // ein Betrag der Geheimhaltung unterliegt (`tax_base_eur === null`) —
  // dann gibt es keinen Nenner, durch den sich teilen ließe. Für Oldenburg
  // ist das in keinem der Jahrgänge 2017–2021 der Fall, für Salzgitter und
  // Wolfsburg in jedem.
  const ohneSteuer = statistik ? statistik.cases - statistik.cases_positive : 0;
  const zahlenAnteil = statistik && statistik.cases
    ? (statistik.cases_positive / statistik.cases) * 100 : 0;
  const zerlegtAnteil = statistik?.tax_base_eur && statistik.apportioned_assessment_eur != null
    ? (statistik.apportioned_assessment_eur / statistik.tax_base_eur) * 100 : null;
  // Wie viel mehr eine zerlegte Betriebsstätte trägt als eine rein örtliche
  // Firma — je zahlendem Fall, nicht je Fall: Wer die Betriebe ohne
  // Steuermessbetrag mitteilte, vergliche zwei Zahlen, in denen unterschiedlich
  // viele Nullen stecken.
  const je = (amount: number | null, cases: number | null) =>
    amount != null && cases ? amount / cases : null;
  const jeZerlegt = je(statistik?.apportioned_assessment_eur ?? null,
                       statistik?.apportionments_positive ?? null);
  const jeOertlich = je(statistik?.assessment_tax_base_eur ?? null,
                        statistik?.assessments_positive ?? null);
  const zerlegtFaktor = jeZerlegt && jeOertlich ? jeZerlegt / jeOertlich : null;

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
        <GlossaryText text="Steuergeheimnis" /> (§ 30 Abgabenordnung<Gesetz g="ao-30" />). Die
        Kämmerei kennt die
        Namen, veröffentlichen darf sie sie nicht — auch nicht gegenüber dem Rat. In
        Haushaltsberatungen ist deshalb höchstens von „einem Großzahler“ die Rede. Das ist keine
        Lücke, die wir noch schließen: Es gibt keine Kommune in Deutschland, die eine solche
        Liste veröffentlichen dürfte.
      </p>

      {/* Nennen darf man sie nicht — zählen schon. Der Nenner steht direkt
          unter dem Rechtsgrund, weil er die Frage ist, die dort offenbleibt.
          Er kommt aus der Statistik des Landesamts und trägt deshalb ein
          eigenes Jahr; das steht daneben, nicht im Kleingedruckten. */}
      {statistik && (
        <div className="mt-3 rounded-xl border border-border bg-muted/25 p-3">
          <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wie viele es sind
            </p>
            <span className="font-mono text-[9.5px] uppercase text-muted-foreground">
              Erhebungsjahr {statistik.year}
            </span>
          </div>

          <div className="mt-3 grid gap-3 @sm:grid-cols-3">
            <Kennzahl
              wert={deZahl(statistik.cases)}
              label="Betriebe und Betriebsstätten sind in Oldenburg erfasst" />
            <Kennzahl betont
              wert={deZahl(statistik.cases_positive)}
              label={`davon zahlen überhaupt Gewerbesteuer — ${deProzent(zahlenAnteil, 0)}\u00a0%`} />
            {zerlegtAnteil != null && statistik.apportionments_positive != null && (
              <Kennzahl
                wert={deProzent(zerlegtAnteil)} einheit="%"
                label={`des Steuermessbetrags kommen von ${deZahl(statistik.apportionments_positive)} `
                       + "Betriebsstätten größerer Firmen"} />
            )}
          </div>

          {/* Sechs Zeilen Kleingedrucktes standen hier bis zum 26.08.2026 am
              Stück und erschlugen die drei Zahlen darüber (Tim). Sichtbar
              bleibt, was die Zahlen sonst irreführen ließe; der Rest ist einen
              Klick entfernt und nicht weg. WELCHER SATZ SICHTBAR BLEIBT,
              entscheidet die API (`ABGRENZUNG_KURZ`) und nicht diese Datei —
              das ist eine Aussage über die Daten, keine über das Layout. */}
          <div className="mt-3 border-t border-dashed border-border pt-2.5">
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              Die übrigen {deZahl(ohneSteuer)} hatten einen Steuermessbetrag von null — Verlust,
              Freibetrag oder gar kein Gewerbeertrag. {statistikKurz}
              <Beleg q="lsn_gewerbesteuer" />
            </p>
            {statistikAbgrenzung && (
              <details className="group mt-1.5">
                <summary className="cursor-pointer list-none text-[11px] font-semibold text-primary marker:content-none">
                  <span className="group-open:hidden">Was diese Zahlen exact umfassen</span>
                  <span className="hidden group-open:inline">Weniger</span>
                </summary>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
                  {statistikAbgrenzung}
                </p>
              </details>
            )}
          </div>
        </div>
      )}

      {misst && (
        <div className="mt-3 rounded-xl border border-border bg-muted/25 p-3">
          {/* DIE ÜBERSCHRIFT HAT HIER ZWEIMAL IN DIE IRRE GEFÜHRT. „Veränderung
              zum Vorjahr, im Mittel 1998–2025" stand über zwei Balken mit
              13,2 % und 2,8 % — gelesen wurde daraus „die Gewerbesteuer ist um
              13,2 % gestiegen" bzw. „über den Zeitraum um 13,2 % gewachsen"
              (Tim, 26.08.2026). Beides ist falsch: Der Balken misst, wie weit
              es in EINEM Jahr ausschlägt, in beide Richtungen.

              Deshalb steht der Lesesatz jetzt VOR den Balken und nicht als
              Fußnote darunter — er ist die Einheit der Zahl, nicht ihre
              Methode. Was die Zahl NICHT ist, steht ausdrücklich dabei: Eine
              Grafik, die zwei plausible Lesarten hat, muss die falsche
              benennen, sonst gewinnt sie. */}
          <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wie stark es von Jahr zu Jahr schwankt
            </p>
            <span className="font-mono text-[9.5px] uppercase text-muted-foreground">
              {eigenAend.length} Jahrespaare {von}–{bis}
            </span>
          </div>

          <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">
            Um so viel bewegte sich das Aufkommen in einem durchschnittlichen Jahr —
            nach oben oder nach unten:
          </p>

          <div className="mt-2.5 flex flex-col gap-2">
            <Zeile label="Gewerbesteuer" wert={deProzent(eigenMittel)}
              anteil={(eigenMittel / skala) * 100} farbe="var(--hh-ein-0)" />
            <Zeile label={vergleichTitel} wert={deProzent(andereMittel)}
              anteil={(andereMittel / skala) * 100} farbe="var(--hh-ein-3)" />
          </div>
          <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
            <strong className="font-semibold text-foreground/80">Nicht</strong> gemeint ist die
            Veränderung über den ganzen Zeitraum — die steht in der Kurve oben. Hier zählt jedes
            Jahr einzeln: Unsere Rechnung aus der Ist-Reihe beider Steuern, Ausschläge ohne
            Vorzeichen gemittelt, damit sich ein gutes und ein schlechtes Jahr nicht aufheben.
            <Beleg q="taxes" />
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
            Welche öffentlichen Daten Anhaltspunkte geben
          </p>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-[12.5px] leading-relaxed text-foreground/85">
            <li>
              <strong>Die Steuer folgt der Lohnsumme, nicht der Zentrale.</strong> Hat ein
              Unternehmen Standorte in mehreren Gemeinden, wird seine Gewerbesteuer unter ihnen
              aufgeteilt (<GlossaryText text="Zerlegung" />, § 29
              Gewerbesteuergesetz<Gesetz g="gewstg-29" />) —
              Maßstab sind die Arbeitslöhne je Standort. Wer hier viele Menschen beschäftigt,
              lässt hier auch einen großen Teil seiner Steuer.
              {zerlegtAnteil != null && zerlegtFaktor != null && statistik && (
                <>
                  {" "}Dieser Weg trägt den größeren Teil: {deProzent(zerlegtAnteil)}&nbsp;% des
                  Steuermessbetrags kamen {statistik.year} aus zerlegten Betriebsstätten, und je
                  zahlendem Fall war das rund das{" "}
                  {deProzent(zerlegtFaktor)}-Fache einer Firma, die nur hier sitzt.
                </>
              )}
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
        Deshalb nennen wir keine Unternehmen. Aus den öffentlich verfügbaren Daten lässt
        sich keine belastbare Rangliste der Gewerbesteuerzahlenden ableiten.
      </p>
    </section>
  );
}
