// <LueckenFeld> — eine Lücke mit Grund und Datum (GB-00).
//
// Lücken sind im Baukasten Daten, kein Sonderfall (`{year, fehlt}` im
// Daten-Vertrag, `components/grafik/daten.ts`). Dieses Feld ist ihre
// TEXTFORM: der Satz, der sagt, WAS fehlt und WARUM — „2019 — verworfen:
// 1,3 Mio. € Differenz im Dokument". Gerendert wird er von der Grafik
// selbst (Zeitreihe, Matrix, Waffel & Co.), nie von der Seite gebastelt:
// Nur so kann keine Seite eine Lücke vergessen oder wegkürzen.
//
// ZWEI REGELN, BEIDE UNVERHANDELBAR:
//  * NIE einklappbar. H4-A: „Lücken-Hinweise bleiben immer sichtbar" —
//    deshalb hier kein <details>, kein Auslöser, keine Kompakt-Variante.
//  * Signal-Orange nur als MARKIERUNG (Schraffur-Kachel, Beschriftung),
//    nie als Fläche: Die Lücke ist eine Abweichungs-Kategorie wie in der
//    Zeitreihen-Konvention (schraffierter Kasten, `stroke-signal`), keine
//    Bewertung und kein Alarm.
//
// In der Bildfläche selbst zeichnet jede Grafik ihre Lücke weiterhin als
// schraffierten Kasten (Klasse `hh-schraffur`, gestrichelter Signal-Rand) —
// das Feld hier ist die Beschriftung dazu, unter dem Bild oder in der Karte.

import { cn } from "@/lib/utils";

export function LueckenFeld({ label, reason, datum, className }: {
  /** Was fehlt — meist die Jahreszahl („2019"), sonst der Teil
   *  („Teil B 2026"). */
  label: string;
  /** Warum es fehlt, als ganzer Grund: „verworfen: 1,3 Mio. € Differenz im
   *  Dokument", „PDF ohne lesbare Zeichen". Nie leer — eine Lücke ohne
   *  Grund ist keine Auskunft, sondern ein Loch. */
  reason: string;
  /** Stichtag der Feststellung, wo bekannt („12.08.2026"). */
  datum?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border border-dashed border-border px-3 py-2",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="hh-schraffur mt-[3px] h-3.5 w-5 flex-none rounded-[2px] border border-dashed border-signal/70"
      />
      <p className="min-w-0 text-[12px] leading-relaxed text-foreground/85">
        <span className="font-mono text-[11px] font-semibold tracking-wide text-signal">
          {label}
        </span>
        {" — "}
        {reason}
        {datum && (
          <span className="ml-1.5 whitespace-nowrap font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
            Stand {datum}
          </span>
        )}
      </p>
    </div>
  );
}
