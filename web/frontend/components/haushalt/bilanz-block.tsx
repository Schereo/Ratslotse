"use client";

// <BilanzBlock> — die Vermögensseite, auf /haushalt/schulden.
//
// WARUM HIER UND NICHT AUF EINER EIGENEN SEITE. Die Seite darüber beantwortet
// „wie viel Schulden hat Oldenburg?" mit 294,9 Mio. €, und die naheliegende
// Anschlussfrage lautet: „Kredite hat die Stadt also kaum — dann hat sie ja
// keine Schulden?" Die Antwort steht in der Bilanz, und sie ist ein
// Vielfaches der Kreditschulden: die Pensionsrückstellungen. Als eigene Seite
// stünde sie neben dem Gespräch, in das sie gehört (und wäre ein 17. Schritt
// in einem Wegweiser, der bei 16 gezählt ist).
//
// DREI ZAHLEN, DIE MAN VERWECHSELN KANN, und die diese Datei deshalb
// auseinanderhält:
//
//   Geldschulden (Bilanz 2.1)            43,7 Mio. €   Kredite bei Banken
//   Schulden (Bilanz 2.)                207,1 Mio. €   alle Verbindlichkeiten
//   Schulden (Statistisches Jahrbuch)   294,9 Mio. €   Stadt inkl. Eigenbetriebe
//
// Alle drei stimmen, alle drei heißen „Schulden". Der Block zeigt deshalb die
// erste (sie ist die, die zur Rückstellung kontrastiert) und benennt die
// Abgrenzung an Ort und Stelle.
//
// DIE 207,1 MIO. € SIND EIN BUCHUNGSARTEFAKT, und ohne den Erläuterungstext
// wäre die Zahl still falsch: 2024 muss die Stadt dieselben Cash-Pooling-
// Mittel auf beiden Bilanzseiten ausweisen (138,2 Mio. €, Gegenposten im
// Finanzvermögen). Der Text kommt aus Abschnitt 6.2.7 des Dokuments, im
// Wortlaut. **Ohne ihn wird die Zahl nicht gezeigt** — das ist keine
// Vorsichtsmaßnahme, sondern die Bedingung, unter der sie stimmt.
//
// KEINE BEWERTUNGSFARBEN (DESIGNSPRACHE § 7). Hohe Pensionsrückstellungen
// sind kein Rot wert: Es sind zugesagte Leistungen, für die Rücklagen
// gebildet werden — dass sie in der Bilanz stehen, ist das Gegenteil eines
// Versäumnisses. Signal-Orange kommt hier gar nicht vor; der <Gegenbalken>
// hielte es für den Rest zur Basis bereit, und einen Rest gibt es nicht: Eine
// Bilanz geht auf.
//
// DER <Gegenbalken> (GB-04) IST HIER DIE RICHTIGE FORM, und das ist die
// Ausnahme und nicht die Regel: Seine Bauart — zwei Leisten auf EINER
// gemeinsamen Basis, asymmetrische 100 % nicht konstruierbar — ist genau die
// Definition einer Bilanz. Beide Zeilen füllen die Basis exakt, deshalb
// zeigt er weder Rest noch Zeilensumme. Was er NICHT trägt, ist die
// eigentliche Schlagzeile (Pension gegen Kredit): 312 gegen 44 von 1.480 sind
// 21 % gegen 3 %, und nebeneinandergelegt verschwindet der Punkt. Die steht
// deshalb darunter als zwei Zahlen und ein Satz.

import { useFetch } from "@/lib/use-fetch";
import { deMio } from "@/lib/haushalt";
import { Gegenbalken } from "@/components/grafik/gegenbalken";
import { Einordnung } from "@/components/grafik/einordnung";
import { Beleg } from "@/components/haushalt/quelle";
import {
  BilanzDaten, cashPoolingHinweis, juengsterStichtag, segmente, vielfaches,
} from "@/lib/haushalt-bilanz";

/** Ein Vielfaches als Wort — „das Siebenfache". Nur bis zwölf und nur, wenn
 *  der Wert nah genug an einer ganzen Zahl liegt; sonst steht die Zahl da
 *  („das 7,4-Fache"). Gerundet zu behaupten, es sei „das Siebenfache", wenn
 *  es 7,4 ist, wäre eine kleine Übertreibung — und in einem Bereich, dessen
 *  ganzer Zweck Nachrechenbarkeit ist, eine zu viel. */
const WORTE = ["", "", "Doppelte", "Dreifache", "Vierfache", "Fünffache",
  "Sechsfache", "Siebenfache", "Achtfache", "Neunfache", "Zehnfache",
  "Elffache", "Zwölffache"];

function vielfachesText(v: number): string {
  const nah = Math.round(v);
  if (nah >= 2 && nah < WORTE.length && Math.abs(v - nah) <= 0.15) {
    return `das ${WORTE[nah]}`;
  }
  return `das ${deMio(v)}-Fache`;
}

export function BilanzBlock() {
  const { data } = useFetch<BilanzDaten>("/council/haushalt/bilanz");
  const s = juengsterStichtag(data);
  // Ohne vollständige Bilanz gibt es diesen Block nicht. Kein Platzhalter,
  // keine halbe Bilanz: Eine Vermögensseite, bei der ein Hauptposten fehlt,
  // gleicht sich nicht aus und behauptete eine Summe, die nicht stimmt.
  if (!data || !s) return null;

  const p = s.posten;
  const pension = p.pensionen_gesamt?.wert ?? null;
  const nurPension = p.pensionsrueckstellungen?.wert ?? null;
  const beihilfe = p.beihilferueckstellungen?.wert ?? null;
  const kredite = p.geldschulden?.wert ?? null;
  const v = vielfaches(s);
  const cash = cashPoolingHinweis(data, s.year);

  return (
    <>
      {/* WAS DIE STADT HAT — die Bilanz als Ganzes. */}
      <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Und was hat die Stadt? · Bilanz zum 31.12.{s.year}
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {data.jahre.length} Stichtage · {data.jahre[0]}–{data.jahre[data.jahre.length - 1]}
          </span>
        </div>
        <p className="font-display text-[26px] font-bold leading-none tracking-tight tabular-nums sm:text-[30px]">
          {deMio(s.bilanzsumme / 1e6)}&#8239;Mio.&nbsp;€<Beleg q="bilanz" />
        </p>
        <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
          Die Bilanz zeigt auf der Aktivseite, worin das Vermögen gebunden ist. Die
          Passivseite zeigt, wie dieses Vermögen finanziert ist. Beide Seiten ergeben
          definitionsgemäß dieselbe Bilanzsumme.
        </p>
        <Gegenbalken
          className="mt-1"
          basis={s.bilanzsumme / 1e6}
          nachkomma={1}
          zeilen={[
            { titel: "Worin es steckt", rampe: "ein", segmente: segmente(s, "aktiva") },
            { titel: "Wem es zusteht", rampe: "aus", segmente: segmente(s, "passiva") },
          ]}
        />
        <Einordnung
          satz={<>
            „Wem es zusteht“ beschreibt die Finanzierung des Vermögens. Eigenkapital
            ist der nicht fremdfinanzierte Anteil; Rückstellungen bilden Verpflichtungen
            ab, deren genaue Höhe oder Fälligkeit noch nicht feststeht.
          </>}
          nichtAussagen={[
            "Ein Stichtag, kein Jahr. Diese Beträge sind mit den Einnahmen und "
            + "Ausgaben auf den übrigen Seiten nicht verrechenbar.",
            "Kein Verkaufswert. Straßen, Schulen und Grünflächen stehen mit ihrem "
            + "Buchwert in der Bilanz — verkäuflich sind sie deshalb nicht.",
            "Nur die Kernverwaltung. Die Eigenbetriebe und Gesellschaften haben "
            + "eigene Bilanzen; hier stehen sie nur mit dem Wert der Beteiligung.",
          ]}
        />
      </section>

      {/* DIE SCHLAGZEILE: Pension gegen Kredit. */}
      {pension != null && kredite != null && (
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Die größte Verpflichtung ist kein Kredit
          </p>
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                {deMio(pension / 1e6)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                Pensionen und Beihilfe<Beleg q="bilanz" />
              </p>
            </div>
            <div>
              <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums text-muted-foreground sm:text-[32px]">
                {deMio(kredite / 1e6)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                Kredite bei Banken<Beleg q="bilanz" />
              </p>
            </div>
          </div>
          <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Die Stadt hat ihren Beamt*innen Ruhegehalt zugesagt. Was sie dafür
            zurücklegen muss, ist{" "}
            {v != null && <strong>{vielfachesText(v)} dessen, was sie an Krediten
              schuldet</strong>}
            {v == null && <strong>ein Vielfaches ihrer Kredite</strong>} — und es
            steht in keiner der Kredit-Schuldenzahlen weiter oben. Pensionsrückstellungen
            sind keine Bankkredite, sondern bilanzierte künftige Verpflichtungen.
          </p>

          {/* DIE ZWEI ZAHLEN, DIE BEIDE SO HEISSEN. Wer irgendwo „266 Mio."
              liest und hier „312 Mio.", soll hier erfahren, warum beides
              stimmt — statt eine der beiden für falsch zu halten. */}
          {nurPension != null && beihilfe != null && (
            <div className="rounded-xl bg-muted/60 px-3 py-2.5">
              <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
                <strong>Warum zwei unterschiedliche Beträge genannt werden.</strong> Die Bilanz führt die
                Zusagen in einer Zeile zusammen und schlüsselt sie darunter auf:{" "}
                {deMio(nurPension / 1e6)}&#8239;Mio.&nbsp;€ für die Pensionen selbst
                und {deMio(beihilfe / 1e6)}&#8239;Mio.&nbsp;€ für die Beihilfe zu
                deren Krankheitskosten. Zusammen sind das die{" "}
                {deMio(pension / 1e6)}&#8239;Mio.&nbsp;€ von oben. Wo eine dieser
                Zahlen ohne die andere steht, ist meistens die Beihilfe der
                Unterschied.<Beleg q="bilanz" />
              </p>
            </div>
          )}
        </section>
      )}

      {/* DER SPRUNG, DER KEINER IST. Nur mit dem Erläuterungstext — s. Kopf. */}
      {cash && p.schulden && (
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Warum die Bilanz {s.year} plötzlich {deMio(p.schulden.wert / 1e6)}&#8239;Mio.&nbsp;€
            Schulden ausweist
          </p>
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Die Bilanz zählt unter „Schulden" alle Verbindlichkeiten, nicht nur
            Kredite — und dieser Posten ist {s.year} sprunghaft gewachsen, ohne dass
            die Stadt Geld aufgenommen hätte. Was dahintersteckt, schreibt der
            Jahresabschluss selbst:
          </p>
          {/* Der Wortlaut der Verwaltung, nicht unsere Zusammenfassung — dieselbe
              Machart wie <Warum> auf /haushalt/plan-ist. Gekürzt wäre er schnell
              etwas anderes; die Absätze kommen so aus dem Dokument. */}
          <div className="mt-2.5 flex flex-col gap-2 border-l-2 border-border pl-3">
            {cash.text.split("\n\n").map((absatz, i) => (
              <p key={i} className="max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
                {absatz}
              </p>
            ))}
          </div>
          <p className="mt-2.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Jahresabschluss {s.year}, Abschnitt 6.2.7 — Wortlaut der Verwaltung
          </p>
        </section>
      )}
    </>
  );
}
