"use client";

// Nachbewilligungen nach § 117 NKomVG — der Block unter „Warum es anders kam"
// auf /haushalt/plan-ist.
//
// DIE FRAGE. „Wo ist der Haushalt aus dem Ruder gelaufen, um wie viel — und
// wer hat zugestimmt?" Nach § 117 NKomVG braucht jede Ausgabe, die im
// beschlossenen Haushalt nicht (oder nicht in dieser Höhe) steht, eine eigene
// Bewilligung. Seit 2018 sind das 161 Vorlagen.
//
// DIE EINE REGEL, DIE DIESEN BLOCK BAUT. Der Rat ist nicht der einzige Weg.
// Der Rechenschaftsbericht zählt VIER: Rat, Oberbürgermeister, Fachdienst 200
// per Haushaltsvermerk, Eilentscheidungen. Und der Ratsanteil sinkt — 89 %
// (2022), 84 % (2023), 73 % (2024), während die Gesamtsumme sich mehr als
// verdoppelt hat. Wer nur die Ratsbeschlüsse zeigt, zeigt eine schrumpfende
// Teilmenge, als wäre sie das Ganze.
//
// Deshalb steht hier die Gesamtsumme oben und die Rats-Liste darunter, nie
// umgekehrt — und die Liste sagt in ihrer Kopfzeile, welcher Anteil sie ist.
// Für Jahre ohne Rechenschaftsbericht (2018–2021, 2025 f.) gibt es diesen
// Nenner nicht; dann sagt der Block das, statt die Rats-Summe stillschweigend
// als Gesamtsumme auszugeben.
//
// KEINE BEWERTUNGSFARBEN. Eine Nachbewilligung ist kein Skandal:
// Tarifabschlüsse und Baukostensteigerungen sind der Normalfall, und
// „außerplanmäßig" heißt gedeckt-aber-umgewidmet, nicht ungedeckt — jede
// Vorlage nennt ihre Deckung. Der Satz „In acht Jahren wurde keine
// Nachbewilligung abgelehnt" steht nüchtern da, ohne Kommentar. Signal-Orange
// erscheint nur dort, wo es laut DESIGNSPRACHE.md hingehört: an Differenzen.
//
// WIDERSPRÜCHE WERDEN ANGEZEIGT, NICHT REPARIERT. Zwei der drei Berichte
// widersprechen sich selbst (2022: 288.000 € zwischen Fließtext und eigener
// Tabelle; 2023: eine Zelle mit Anzahl 0 und trotzdem einem Betrag). Was die
// Tabellenprobe gefunden hat, steht als Satz am Jahr — `probe_text` kommt
// fertig formuliert aus `council/supplementary_approvals.py`, damit Seite und Test
// dieselbe Aussage tragen.

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import {
  HaushaltAuswahl, Nachbewilligung, NachbewilligungsJahr, NachbewilligungsKanal,
  kanalAnzahl, kanalBetrag, nachbewilligungGesamt, nachbewilligungenFuerJahr,
  nachbewilligungsJahre, ratsAnteil,
} from "@/lib/haushalt";
import {
  RanglisteSchiene, type RanglisteZeile,
} from "@/components/grafik/rangliste-schiene";
import { Beleg } from "@/components/haushalt/source";
import { decisionHref } from "@/lib/routes";
import { cn } from "@/lib/utils";

/** Ein Euro-Betrag in Millionen, deutsch. */
function mio(value: number): string {
  return (value / 1e6).toLocaleString("de-DE", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

/** Volle Euro, deutsch — für die Einzelposten, wo Millionen zu grob wären. */
function euro(value: number): string {
  return value.toLocaleString("de-DE", { maximumFractionDigits: 0 });
}

/** Die vier Entscheidungswege als Rangliste — `<RanglisteSchiene>` (GB-03).
 *
 *  Warum diese Form und keine eigene: Die Seite **komponiert** Grafiken aus
 *  `components/grafik/`, sie zeichnet nicht selbst (grafik/README.md). Die
 *  Schiene bringt genau das mit, was hier gebraucht wird — sichtbare
 *  Null-Basis (ohne sie schwebten die Balken), `hervorgehoben` zum Finden
 *  statt zum Bewerten, und unter 480 px wandert das Label von selbst über den
 *  Balken. Das ist hier keine Kleinigkeit: „Gemäß Haushaltsvermerk durch den
 *  Fachdienst 200" braucht 312 px, und abgeschnitten wäre ausgerechnet die
 *  Auskunft weg, um die es in diesem Block geht — **wer** entschieden hat.
 *
 *  Und bewusst **kein** gestapelter 100-%-Balken: Die vier Wege sind sehr
 *  ungleich groß (2024 trägt der Rat 73 %, die Eilentscheidungen 0 %), in
 *  einem Stapel wären zwei der vier Segmente unbeschriftbar dünn.
 *
 *  Die Reihenfolge ist die des Rechenschaftsberichts, nicht die nach Größe:
 *  Der Bericht führt Rat, Oberbürgermeister, Fachdienst 200, Eilentscheidung
 *  — und `<RanglisteSchiene>` sortiert nicht selbst, sie zeigt, was sie
 *  bekommt. Die Reihenfolge ist eine Angabe der Quelle wie die Zahlen. */
function KanalRangliste({ channels, beleg }: {
  channels: NachbewilligungsKanal[]; beleg: ReactNode;
}) {
  const zeilen: RanglisteZeile[] = channels.map((k) => {
    const count = kanalAnzahl(k);
    return {
      label: k.label,
      value: kanalBetrag(k) / 1e6,
      // Der Rat ist die Zeile, um die es geht — hervorgehoben heißt „hier
      // schauen", nicht „das ist die gute".
      hervorgehoben: k.channel === "council",
      zusatz: count === 1 ? "1 Fall" : `${count} Fälle`,
    };
  });
  return (
    <RanglisteSchiene zeilen={zeilen} unit="Mio.&nbsp;€" nachkomma={2}
      beleg={beleg} />
  );
}

/** Die Liste der Rats-Bewilligungen eines Jahres, größte zuerst.
 *
 *  Ab acht Zeilen hinter einen Auslöser (H4-A: nie ersatzlos) — die fünf
 *  größten stehen immer. Jede Zeile verlinkt über ihre Vorlagen-Nummer auf
 *  die vorhandene Beschluss-Seite; wo wir keine Beschlusszeile haben, bleibt
 *  der Titel unverlinkt statt auf eine erfundene Seite zu zeigen. */
function RatsListe({ posten }: { posten: Nachbewilligung[] }) {
  const [alle, setAlle] = useState(false);
  const sichtbar = alle ? posten : posten.slice(0, 5);
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {sichtbar.map((n) => {
        const title = (
          <span className="text-[12.5px] leading-snug">{n.title}</span>
        );
        return (
          <div key={n.template_number}
            className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border-t border-border/60 pt-1.5 first:border-t-0 first:pt-0">
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              {n.decision_id != null ? (
                <Link href={decisionHref(n.decision_id)}
                  className="text-[12.5px] leading-snug text-primary hover:underline">
                  {n.title}
                </Link>
              ) : title}
              <span className="font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground">
                {n.template_number}
                {n.category === "unbudgeted" && " · außerplanmäßig"}
                {n.in_plenary === 0 && " · im Fachausschuss beschlossen"}
              </span>
            </span>
            <span className="whitespace-nowrap text-right text-[12px] font-semibold tabular-nums">
              {euro(n.amount ?? 0)}&nbsp;€
            </span>
          </div>
        );
      })}
      {posten.length > 5 && (
        <button type="button" onClick={() => setAlle((a) => !a)}
          aria-expanded={alle}
          className="mt-1 inline-flex min-h-[36px] items-center gap-1 self-start text-[12.5px] font-semibold text-primary">
          {alle ? "Weniger zeigen" : `Alle ${posten.length} zeigen`}
          <ChevronDown size={14} strokeWidth={2}
            className={cn("transition-transform", alle && "rotate-180")} />
        </button>
      )}
    </div>
  );
}

export function NachbewilligungsBlock({ daten, year }: {
  daten: HaushaltAuswahl<"supplementary_approvals">; year: number;
}) {
  const alleJahre = nachbewilligungsJahre(daten);
  const unseres = alleJahre.find((j) => j.year === year);
  const bericht: NachbewilligungsJahr | undefined =
    (daten.supplementary_approvals?.years ?? []).find((j) => j.year === year);
  const posten = nachbewilligungenFuerJahr(daten, year);
  // Ohne jede Zahl gar nichts zeigen — eine Überschrift über einer leeren
  // Fläche behauptet, es habe nichts gegeben.
  if (!unseres && !bericht) return null;

  const gesamt = bericht ? nachbewilligungGesamt(bericht) : null;
  const anteil = bericht ? ratsAnteil(bericht) : null;
  const ratsKanal = bericht?.channels.find((k) => k.channel === "council");
  const ratsZeile = ratsKanal ? kanalBetrag(ratsKanal) : null;
  // Der Vergleichswert für den Satz über die Entwicklung: das früheste Jahr,
  // für das ein Bericht vorliegt.
  const n_reports = (daten.supplementary_approvals?.years ?? [])
    .slice().sort((a, b) => a.year - b.year);
  const erstes = n_reports[0];
  const zeigtEntwicklung = erstes && bericht && erstes.year !== bericht.year;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Nachträglich bewilligte Ausgaben · {year}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {n_reports.length
            ? `${n_reports[0].year}–${n_reports[n_reports.length - 1].year} mit Gesamtsicht`
            : "Ratsbeschlüsse seit 2018"}
        </span>
      </div>

      <p className="max-w-[74ch] text-[13px] leading-relaxed text-foreground/90">
        Reicht ein Haushaltsansatz nicht aus oder fehlt er vollständig, kann eine
        über- oder außerplanmäßige Ausgabe nach § 117 NKomVG bewilligt werden.{" "}
        <strong className="font-semibold">Außerplanmäßig bedeutet nicht automatisch
        ungedeckt:</strong> Die Vorlagen nennen jeweils eine Deckung. „Überplanmäßig“
        heißt, dass ein vorhandener Ansatz nicht ausreicht; „außerplanmäßig“, dass
        für diesen Zweck kein Ansatz besteht.
      </p>

      {gesamt != null && (
        <div className="mt-4">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
            Insgesamt nachbewilligt {year}
          </p>
          <p className="mt-0.5 font-[var(--font-bricolage),system-ui] text-[26px] font-bold leading-none tabular-nums">
            {mio(gesamt)}&#8239;Mio.&nbsp;€
            <Beleg q="jahresabschluss" />
          </p>
          {zeigtEntwicklung && (
            <p className="mt-2 max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
              {erstes.year} waren es {mio(nachbewilligungGesamt(erstes))}&#8239;Mio.&nbsp;€.
              {anteil != null && ratsAnteil(erstes) != null && (
                <>
                  {" "}Der Anteil, über den der Rat selbst abgestimmt hat, lag
                  damals bei{" "}
                  {ratsAnteil(erstes)!.toLocaleString("de-DE", { maximumFractionDigits: 0 })}
                  &nbsp;% und liegt {year} bei{" "}
                  <span className="font-semibold text-signal">
                    {anteil.toLocaleString("de-DE", { maximumFractionDigits: 0 })}&nbsp;%
                  </span>.
                </>
              )}
            </p>
          )}
        </div>
      )}

      {bericht && (
        <div className="mt-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Wer über die Bewilligung entscheidet
            {/* Der Chip hängt an der Überschrift — unter den Balken stand er
                allein in einer Zeile (Durchsicht 02.09.2026). */}
            <Beleg q="jahresabschluss" />
          </p>
          <div className="mt-2.5">
            <KanalRangliste channels={bericht.channels} beleg={null} />
          </div>
          <p className="mt-3 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Der Rechenschaftsbericht unterscheidet vier Entscheidungswege. Nur einer
            führt über eine Abstimmung im Rat; in den übrigen Fällen entscheidet die
            Verwaltung oder es handelt sich um eine Eilentscheidung. Der Rat wird
            darüber unterrichtet.
          </p>
          {bericht.commitments_amount != null
            && bericht.commitments_amount > 0 && (
            <p className="mt-2 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Nicht enthalten: {mio(bericht.commitments_amount)}&#8239;Mio.&nbsp;€
              an Verpflichtungsermächtigungen. Sie erlauben, künftige Jahre zu
              binden, und fließen in diesem Jahr nicht — der Bericht zählt sie
              deshalb getrennt, und wir addieren sie nirgends dazu.
            </p>
          )}
          {bericht.probe_ok === 0 && bericht.probe_text && (
            <p className="mt-2 max-w-[74ch] rounded-lg border border-border bg-muted/40 p-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              <span className="font-semibold text-foreground/90">
                Der Bericht widerspricht sich an dieser Stelle selbst.
              </span>{" "}
              {bericht.probe_text} Wir geben beide Zahlen so wieder, wie sie im
              Dokument stehen, und rechnen nichts glatt.
            </p>
          )}
        </div>
      )}

      {posten.length > 0 && (
        <div className="mt-4 border-t border-border/60 pt-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Die einzelnen Beschlüsse
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {posten.length} {posten.length === 1 ? "Vorlage" : "Vorlagen"}
              {unseres && ` · ${mio(unseres.summe)} Mio. €`}
            </span>
          </div>
          <RatsListe posten={posten} />
          <p className="mt-3 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Die Vorlagen, über die Rat oder Finanzausschuss entschieden haben
            <Beleg q="ratsbeschluss" />; jede führt auf ihre Beschluss-Seite.
            {gesamt != null && anteil != null && (
              <>
                {" "}Sie sind der Teil, über den öffentlich abgestimmt wurde —{" "}
                {anteil.toLocaleString("de-DE", { maximumFractionDigits: 0 })}
                &nbsp;% der Gesamtsumme oben, nicht die Gesamtsumme selbst.
              </>
            )}
            {unseres && unseres.sammelberichte > 0 && (
              <>
                {" "}Die Fälle unter 50.000&nbsp;€ entscheidet der Rat gar
                nicht; über sie berichtet die Verwaltung einmal jährlich
                gesammelt.
              </>
            )}
          </p>
          {/* Die Definitionsdifferenz gehört als Satz auf die Seite, nicht in
              eine Fußnote: Sie erklärt, warum die Summe dieser Liste nicht
              exakt der Rats-Zeile oben entspricht — 2024 sind es 924.453,71 €,
              verteilt auf drei Vorlagen, die niedriger gebucht als beantragt
              wurden. Kein Fehler, sondern zwei verschiedene Fragen. */}
          {unseres && bericht && ratsZeile != null
            && Math.abs(unseres.summe - ratsZeile) > 1 && (
            <p className="mt-2 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Die Liste nennt, was die Vorlagen beantragt haben; die Zeile oben,
              was am Ende gebucht wurde — deshalb weichen die Summen leicht ab.
            </p>
          )}
        </div>
      )}

      {!bericht && (
        <p className="mt-3 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
          Für {year} liegt noch kein Rechenschaftsbericht vor. Wie viel
          insgesamt nachbewilligt wurde — also auch das, was die Verwaltung
          ohne den Rat entschieden hat —, steht erst dort. Was hier zu sehen
          ist, sind ausschließlich die Beschlüsse aus Rat und Fachausschuss.
        </p>
      )}
    </div>
  );
}

/** Der nüchterne Nebenbefund über die ganze Reihe — ein Satz, keine Wertung.
 *
 *  Er steht getrennt vom Jahresblock, weil er nicht zu einem Jahr gehört,
 *  sondern zu allen: In acht Jahren ist keine Nachbewilligung abgelehnt
 *  worden. Das ist ein Befund über den Bestand, kein Vorwurf — die Vorlagen
 *  sind vorher im Fachausschuss beraten, und was dort keine Mehrheit findet,
 *  erreicht den Rat meist gar nicht erst. */
export function NachbewilligungsBefund({ daten }: { daten: HaushaltAuswahl<"supplementary_approvals"> }) {
  const serie = (daten.supplementary_approvals?.serie ?? [])
    .filter((n) => n.kind !== "threshold");
  if (serie.length < 20) return null;
  const years = serie.map((n) => n.year).filter((j): j is number => j != null);
  const beschlossen = serie.filter((n) => n.decided === 1).length;
  // Die Differenz wird ausgeschrieben statt verschwiegen — sonst fragt sich
  // jede*r, was mit dem Rest passiert ist, und die naheliegende Vermutung
  // („abgelehnt") wäre genau die falsche. Es sind zwei Gruppen: Vorlagen, mit
  // denen der Rat nur unterrichtet wurde (entschieden hat der
  // Oberbürgermeister oder eine Eilentscheidung), und solche, zu denen im
  // Bestand kein Ergebnis steht.
  const unterrichtet = serie.filter(
    (n) => n.decided === 0 && n.committees.length > 0).length;
  const ohneErgebnis = serie.length - beschlossen - unterrichtet;
  return (
    <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
      Seit {Math.min(...years)} sind {serie.length} solcher Vorlagen in Rat und
      Fachausschuss aufgerufen worden. {beschlossen} wurden beschlossen, keine
      abgelehnt.
      {unterrichtet > 0 && (
        <> Bei {unterrichtet} wurde der Rat nur unterrichtet — entschieden
        hatte sie der Oberbürgermeister oder eine Eilentscheidung.</>
      )}
      {ohneErgebnis > 0 && (
        <> Zu {ohneErgebnis} liegt uns kein Ergebnis vor.</>
      )}
    </p>
  );
}
