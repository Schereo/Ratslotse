// Die Stations-Bausteine des Haushalts-Wegs (/haushalt/year).
//
// Bis H3-06 hieß diese Datei `jahreskreis.tsx` und trug zusätzlich den
// Jahreskreis — eine Haushaltsrunde auf einem Kalenderjahr. Der Kreis ist
// durch den liegenden <Zeitstrahl> aus dem Grafik-Baukasten ersetzt
// (components/grafik/zeitstrahl.tsx): Ein Kreis hat kein Heute, der Strahl
// schon — und die 27-Monats-Sicht zeigt nebenbei, warum es gleichzeitig um
// drei Haushalte geht. Geblieben sind die beiden Bausteine der
// Stationsliste, die die Seite je Jahrgang weiter braucht.

import { ergebnisArt, WegStation } from "@/lib/haushalt-jahr";
import { OUTCOME_META } from "@/components/decision-ui";
import { cn } from "@/lib/utils";

/** Ergebnis-Abzeichen im Wortlaut des Ratsinformationssystems.
 *  Die Farbe folgt der Ergebnis-Grammatik der App, der Text nicht: „geändert
 *  beschlossen" ist genauer als „Angenommen", und es ist die Formulierung,
 *  unter der man den Punkt im Original wiederfindet. */
export function ErgebnisAbzeichen({ result, className }: {
  result: string | null;
  className?: string;
}) {
  if (!result) return null;
  return (
    <span className={cn(
      "shrink-0 rounded-md px-2 py-0.5 text-[11px] font-medium",
      OUTCOME_META[ergebnisArt(result)].cls,
      className,
    )}>
      {result}
    </span>
  );
}

/** Eine Station als Zeile — Datum, Gremium, Ergebnis, und wenn es in dieser
 *  Sitzung eine Abstimmung über die Haushaltssatzung gab, deren Zählung.
 *
 *  Das Abzeichen steht neben dem Kicker und darf umbrechen, nicht neben dem
 *  Gremium: „zurückgestellt/abgesetzt" ist breiter als die halbe Zeile, und
 *  daneben brach „Ausschuss für Finanzen und Beteiligungen" auf 375 px in
 *  drei Zeilen um. */
export function StationsZeile({ station, role, children }: {
  station: WegStation;
  /** Was die Station im Verfahren ist — steht über dem Gremium. */
  role: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="border-t border-border/70 py-3 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {role}
        </p>
        <ErgebnisAbzeichen result={station.result} />
      </div>
      <p className="mt-1 text-[13.5px] font-bold leading-snug">{station.committee}</p>
      {/* Der Fließtext der Station hält Lesebreite — ohne Deckel lief er über
          die volle Kartenbreite (gemessen 1.102 px, das sind bei 12,5 px
          Schrift rund 180 Zeichen je Zeile).

          `text-[12.5px]` AM DECKEL, obwohl jedes Kind seine Größe selbst setzt
          und sich hier nichts vererbt: `ch` misst die Schrift des Elements, an
          dem es steht. Ohne die Angabe maß der Deckel die geerbten 16 px des
          Body, und `76ch` waren 767 px statt 599 — der Text lief auf 122
          Zeichen je Zeile, das Breiteste im ganzen Bereich (24.08.2026).
          Mit der Größe am Kasten heißt `76ch` das, was es sagt: 599 px,
          rund 95 Zeichen — der Wert des restlichen Haushalts-Bereichs.
          Wer die Schriftgröße der Kinder ändert, zieht sie hier nach. */}
      <div className="max-w-[76ch] text-[12.5px]">{children}</div>
    </div>
  );
}
