"use client";

// „Geplant und geworden — nur diese Steuer" (Steuer-Steckbrief).
//
// Der Ansatz des Haushaltsplans neben dem Rechnungsergebnis, je Jahr eine
// Hantel (GB-05). Die Quelle ist Tabelle 1103 des Statistischen Jahrbuchs —
// die einzige, die die Plan-Seite je Steuerart überhaupt ausweist: Weder der
// Ergebnishaushalt noch die Ergebnisrechnung schlüsseln Steuern auf, beide
// führen nur „Steuern und ähnliche Abgaben" als eine Summe.
//
// WARUM DIE HANTEL UND KEINE ZWEITE KURVE. Plan und Ist sind zwei Werte zu
// EINEM Zeitpunkt; die Aussage ist der Abstand zwischen ihnen. Eine zweite
// Linie neben der Ist-Kurve darüber zeigte denselben Abstand als Fläche
// zwischen zwei Kurven — lesbar nur, wer beide gleichzeitig verfolgt. Die
// Hantel legt die Differenz auf eine Achse und macht sie zur Länge.
//
// KEINE BEWERTUNG. Eine um 42 % unterschätzte Gewerbesteuer ist nicht
// „schlecht geplant": Sie hängt an den Gewinnen weniger großer Zahler und
// schwankte in unserer eigenen Reihe zwischen 42,7 und 222,1 Mio. €. Wer sie
// vorsichtig ansetzt, vermeidet ein Loch, das im laufenden Jahr niemand mehr
// schließt. Deshalb steht hier ein Befund und keine Note — und deshalb hat die
// Hantel keine Grün/Rot-Prop, in die man eine hineinschreiben könnte.
//
// KEINE ERFUNDENE KENNZAHL. Die Quelle nennt Plan und Ist. Die Abweichung
// dazwischen ist eine Subtraktion und darf gezeigt werden; eine
// „Planungsgenauigkeit in Prozent" wäre etwas anderes — eine Note mit
// Nachkommastelle, die niemand veröffentlicht hat.

import { Hantel, type HantelZeile } from "@/components/grafik/hantel";
import { Einordnung } from "@/components/grafik/einordnung";
import { deMio } from "@/lib/haushalt";
import type { SteuerplanZeile } from "@/lib/haushalt";

export function SteuerPlanIst({ zeilen, abgrenzung, beleg }: {
  /** Nur die Zeilen DIESER Steuerart, aufsteigend nach Jahr. */
  zeilen: SteuerplanZeile[];
  /** Was die Zahlen umfassen. Angabe der Quelle, kein Frontend-Text. */
  abgrenzung: string;
  beleg?: React.ReactNode;
}) {
  if (zeilen.length < 1) return null;
  const sortiert = [...zeilen].sort((a, b) => a.year - b.year);

  const hantelZeilen: HantelZeile[] = sortiert.map((z) => ({
    label: String(z.year),
    plan: z.plan / 1e6,
    ist: z.actual / 1e6,
    // `einordnung` ist Pflicht-FELD (GB-05). `null` heißt hier genau, was es
    // heißt: Tabelle 1103 erläutert ihre Zeilen nicht — sie stellt zwei Zahlen
    // nebeneinander, mehr nicht. Wo die Quelle doch etwas über sich selbst
    // sagt, steht es da: Die jüngste Spalte heißt dort „vorläufiges
    // Rechnungsergebnis", und eine Zahl, die sich noch ändern kann, soll das
    // an sich tragen.
    einordnung: z.provisional
      ? "Das Rechnungsergebnis ist vorläufig — so weist die Tabelle es selbst aus. Es kann sich mit dem Jahresabschluss noch ändern."
      : null,
  }));

  // Die Spanne der Abweichungen, gerechnet und als solche benannt. Keine
  // Kennzahl, sondern die Zusammenfassung dessen, was die Hantel zeigt.
  const abweichungen = sortiert
    .filter((z) => z.plan > 0)
    .map((z) => (z.actual / z.plan - 1) * 100);
  const alleUeber = abweichungen.length > 1 && abweichungen.every((a) => a > 0);
  const kleinste = Math.min(...abweichungen);
  const groesste = Math.max(...abweichungen);

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Geplant und geworden
        </p>
        {/* Ehrliche Menge statt „mehrere Jahre" (Designsprache §6). */}
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {sortiert.length === 1
            ? sortiert[0].year
            : `${sortiert[0].year}–${sortiert[sortiert.length - 1].year}`}
          {" · "}{sortiert.length} {sortiert.length === 1 ? "Jahr" : "Jahre"}
        </span>
      </div>
      {/* Ohne Artikel und ohne den Titel im Satz: Die Steckbrief-Titel haben
          drei Genera („die Gewerbesteuer", „der Anteil an der Einkommensteuer",
          „Kleine örtliche Steuern"), und ein eingesetzter Titel ergab
          „für die Anteil an der Einkommensteuer". Der Titel steht ohnehin
          direkt darüber. */}
      <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
        Was im beschlossenen Haushalt stand — und was am Ende des Jahres
        tatsächlich in der Kasse war.
      </p>

      <div className="mt-3">
        <Hantel
          zeilen={hantelZeilen}
          unit="Mio. €"
          /* Jahres-Zeilen wollen ihre Chronologie, nicht die Rangfolge der
             Abweichung: Ob 2024 weiter danebenlag als 2023, liest man an der
             Länge — dass 2024 auf 2023 folgt, muss die Reihenfolge tragen. */
          sortierung="alpha"
          /* Die Legende der Hantel spricht sonst von Bereichen und
             Mehrausgaben — beides gibt es hier nicht. Eine Steuer wird nicht
             ausgegeben, sie kommt herein. */
          wovon="diese Steuer"
          keineWertung={
            <>Die Farbe ist keine Bewertung. Höhere oder niedrigere Einnahmen können
              durch die wirtschaftliche Entwicklung, vorsichtige Planung oder
              unerwartete Veränderungen entstehen. Eine Abweichung ist für sich
              genommen weder gut noch schlecht.</>
          }
          beleg={beleg}
        />
      </div>

      <div className="mt-3 border-t border-dashed border-border pt-3">
        <Einordnung
          satz={
            alleUeber
              ? <>In allen {abweichungen.length} Jahren kam mehr herein als
                  geplant, zwischen {deMio(kleinste)}&nbsp;% und {deMio(groesste)}&nbsp;%.
                  Das kann auf eine vorsichtige Planung bei schwankenden Einnahmen
                  hindeuten. Aus der Tabelle allein lässt sich jedoch nicht beurteilen,
                  warum der Ansatz so gewählt wurde.</>
              : <>Plan und Ergebnis liegen zwischen {deMio(kleinste)}&nbsp;% und{" "}
                  {deMio(groesste)}&nbsp;% auseinander. Ob eine Abweichung viel
                  oder wenig ist, hängt an der Steuer: Der Anteil an der
                  Einkommensteuer ist Monate im Voraus gut zu schätzen, die
                  Gewerbesteuer nicht.</>
          }
          nichtAussagen={[
            "Warum ein Ansatz so hoch war, wie er war, sagt diese Tabelle nicht — sie nennt Plan und Ergebnis, keine Begründung.",
            `Abgrenzung der Quelle: ${abgrenzung}`,
          ]}
        />
      </div>
    </div>
  );
}
