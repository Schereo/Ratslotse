"use client";

// „Wie viel Spielraum genutzt wurde" — der Maßstab unter dem Labor.
//
// WARUM DIESE KARTE HIER STEHT. Das Labor lässt Regler bewegen und rechnet
// Millionen aus; was es bis zum 30.08.2026 nicht sagte, ist die Größe, gegen
// die man das halten müsste: Wie viel hat der Rat im echten Verfahren
// bewegt? Ohne diesen Maßstab ist jede Zahl aus dem Labor eine ohne Gefühl —
// „5 Mio. €" liest sich wahlweise als Kleinigkeit oder als Umsturz.
//
// Die Antwort steht in der „Zusammenstellung der Veränderungen" jeder
// Änderungsliste, die seit #734 gelesen wird: Sie weist den
// Verwaltungsentwurf und die Endsumme nebeneinander aus. Dazwischen liegt
// alles, was das Verfahren geändert hat — und die Zeilen dazwischen sagen,
// wer es geändert hat.
//
// ZWEI ARTEN VON ÄNDERUNG, und die Karte darf sie nicht gegeneinander
// ausspielen: Die Listen der VERWALTUNG sind Fortschreibungen ihres eigenen
// Entwurfs — die November-Steuerschätzung, ein neuer Tarifabschluss, eine
// geänderte Umlage. Die Listen der FRAKTIONEN sind die politisch gewollten
// Änderungen. Dass die ersten meist ein Vielfaches der zweiten bewegen, ist
// deshalb KEIN Befund über politische Durchsetzungskraft, sondern über die
// Natur der beiden Listen. Genau dieser Satz steht auch auf der Karte: Ohne
// ihn wäre die Grafik eine Wertung, die die Daten nicht hergeben.

import {
  AenderungslistenDaten, VerfahrensWeg, deltaBetrag, verfahrensWeg,
} from "@/lib/haushalt-aenderungslisten";
import { Anteilsbalken } from "@/components/haushalt/anteilsbalken";
import { Beleg } from "@/components/haushalt/quelle";
import { parteiDot } from "@/components/qa-bausteine";
import { cn } from "@/lib/utils";

const NEUTRAL = { bg: "hsl(209 18% 65%)", ring: false };

function Mio({ euro }: { euro: number }) {
  return (
    <span className={cn("whitespace-nowrap font-mono text-[12px] tabular-nums",
      euro < 0 ? "text-signal" : "text-foreground")}>
      {deltaBetrag(euro)}
    </span>
  );
}

/** Ein Saldo als Zeile des Wegs: Beschriftung links, Betrag rechts.
 *
 *  KEIN `flex-wrap`: Bricht die Zeile um, rutscht der Betrag linksbündig
 *  unter seine Beschriftung und liest sich als eigener Posten — auf 390 px
 *  war „Vom Finanzausschuss beschlossen" genau so auseinandergefallen.
 *  Stattdessen darf die BESCHRIFTUNG umbrechen (`min-w-0`), während der
 *  Betrag als unteilbarer Block rechts stehen bleibt. */
function WegZeile({ label, euro, stark }: {
  label: string; euro: number; stark?: boolean;
}) {
  return (
    <p className="flex items-baseline gap-x-3">
      <span className={cn("min-w-0 text-[12.5px]",
        stark ? "font-semibold text-foreground" : "text-muted-foreground")}>
        {label}
      </span>
      <span className={cn("ml-auto flex-none whitespace-nowrap font-mono text-[12.5px] tabular-nums",
        stark ? "font-semibold" : "",
        euro < 0 ? "text-signal" : "text-foreground")}>
        {deltaBetrag(euro)}
      </span>
    </p>
  );
}

export function VerfahrensWegKarte({ daten, jahrgang, className }: {
  daten: AenderungslistenDaten | null;
  /** Der Jahrgang, mit dem das Labor rechnet — nicht der neueste im Bestand:
   *  Ein Maßstab aus einem anderen Jahr als die Lücke wäre keiner. */
  jahrgang: number | null;
  className?: string;
}) {
  const weg: VerfahrensWeg | null = verfahrensWeg(daten, jahrgang);
  if (!weg || weg.bewegt === 0) return null;

  // Der Balken zerlegt eine Summe in Teile — das trägt nur, wenn die Teile in
  // dieselbe Richtung zeigen wie das Ganze. 2021 taten sie es nicht (Verw. II
  // +2,78 Mio., Verw. I −0,65, Politik −1,73): Ein gestapelter Balken hätte
  // dort eine Zerlegung gemalt, die es nicht gibt. Dann bleiben die Zahlen
  // stehen und die Grafik weg — sie ist die Zugabe, nicht die Aussage.
  const gleichgerichtet = weg.bewegt !== 0
    && Math.sign(weg.verwaltung || weg.bewegt) === Math.sign(weg.bewegt)
    && Math.sign(weg.politik || weg.bewegt) === Math.sign(weg.bewegt);
  const politikAnteil = weg.bewegt !== 0
    ? Math.abs(weg.politik) / Math.abs(weg.bewegt) * 100 : 0;

  return (
    <div className={cn("rounded-2xl border border-border bg-card p-4 shadow-sm", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wie viel im echten Verfahren bewegt wurde
        </h2>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          Haushalt {weg.jahrgang}
        </span>
      </div>

      <p className="mt-1 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Bevor du hier Regler bewegst: So weit ist der Haushalt {weg.jahrgang} im
        echten Verfahren gewandert — vom Entwurf der Verwaltung bis zu dem
        Stand, den{weg.beschlossen
          ? " der Finanzausschuss beschlossen hat"
          : " die Verwaltung zuletzt vorgelegt hat"}. Die Zahlen kommen aus der
        Zusammenstellung der Änderungslisten, nicht aus einer Schätzung.
      </p>

      <div className="mt-3 flex flex-col gap-1 rounded-xl bg-muted/40 p-3">
        <WegZeile label={`Entwurf der Verwaltung ${weg.jahrgang}`} euro={weg.entwurf} />
        <WegZeile
          label={weg.beschlossen
            ? "Vom Finanzausschuss beschlossen"
            : "Letzter Stand der Verwaltungslisten"}
          euro={weg.ende}
        />
        <div className="mt-1 border-t border-border/60 pt-1.5">
          <WegZeile label="Das Verfahren bewegte" euro={weg.bewegt} stark />
        </div>
      </div>

      {gleichgerichtet && (
        <Anteilsbalken
          className="mt-3"
          titel="Woher diese Bewegung kam"
          gesamt={Math.abs(weg.bewegt)}
          einheit="€"
          segmente={[
            { label: "Listen der Verwaltung", wert: Math.abs(weg.verwaltung),
              farbe: "var(--hh-aus-2)" },
            { label: "Listen der Fraktionen", wert: Math.abs(weg.politik),
              farbe: "var(--hh-aus-5)" },
          ]}
        />
      )}

      {!gleichgerichtet && (
        <div className="mt-3 flex flex-col gap-1">
          <WegZeile label="davon Listen der Verwaltung" euro={weg.verwaltung} />
          <WegZeile label="davon Listen der Fraktionen" euro={weg.politik} />
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Die Listen zogen in verschiedene Richtungen — deshalb steht hier
            keine Aufteilungs-Grafik: Sie würde eine Zerlegung zeigen, die es
            nicht gibt.
          </p>
        </div>
      )}

      {weg.politikZeilen.length > 0 && (
        <div className="mt-3 flex flex-col gap-1.5">
          {weg.politikZeilen.map((s) => {
            const dot = s.label.includes("/") ? NEUTRAL : parteiDot(s.label);
            return (
              <p key={s.label} className="flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
                <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-foreground">
                  <span aria-hidden className="h-2 w-2 flex-none rounded-full"
                    style={{
                      background: dot.bg,
                      boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
                    }} />
                  {s.label}
                </span>
                <Mio euro={s.saldo} />
              </p>
            );
          })}
        </div>
      )}

      <p className="mt-3 max-w-[70ch] text-[11px] leading-relaxed text-muted-foreground">
        {weg.politikZeilen.length > 0 ? (
          <>
            Die Listen der Fraktionen machen{" "}
            <strong className="font-semibold text-foreground">
              {politikAnteil < 1
                ? "weniger als 1 %"
                : `rund ${Math.round(politikAnteil)} %`}
            </strong>{" "}
            dieser Bewegung aus. Das ist kein Maß für politische Durchsetzung,
            sondern für die Natur der beiden Listenarten: Die Verwaltung
            schreibt mit ihren Listen den eigenen Entwurf fort — neue
            Steuerschätzung, Tarifabschluss, geänderte Umlagen. Die Fraktionen
            ändern, was sie politisch anders wollen; das sind einzelne Posten,
            keine Neuberechnung des ganzen Plans.
          </>
        ) : (
          <>
            Für diesen Jahrgang liegt keine Beschluss-Datei des
            Finanzausschusses vor — was die Fraktionen bewegt haben, steht
            deshalb in keiner Zahl hier. Der Weg endet beim letzten Stand der
            Verwaltung.
          </>
        )}{" "}
        <Beleg q="aenderungsliste" h={weg.herkunft} />
      </p>
    </div>
  );
}
