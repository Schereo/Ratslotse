"use client";

// <Treemap> — Größenordnung als Fläche (GB-08, Board H4-06).
//
// Kachel = Vorhaben, Fläche = Gesamtsumme: 1 mm² ist überall gleich viel
// Geld. Das Layout rechnet `treemapSquarify` aus d3-hierarchy ZUR LAUFZEIT —
// je Jahrgang, je Filter neu. Genau der Fall, in dem Handrechnen (wie im
// Artboard) nicht skaliert.
//
// DIE REST-KACHEL IST PFLICHT, kein Feature: Die Masse der kleinen Vorhaben
// ist selbst eine Größe. Wer nur die Top-Kacheln zeigte, behauptete, das
// Programm bestünde aus zwölf Projekten — tatsächlich sind es Tausende, und
// ihre Summe verdient dieselbe ehrliche Fläche. Ab der Rest-Kachel übernimmt
// die Suche. Ihre Schraffur ist NEUTRAL (muted), nicht die orange
// Lücken-Schraffur: Gebündelt ist keine Lücke und keine Abweichung.
//
// NUR POSITIVE WERTE: Eine Fläche kann keinen negativen Betrag zeigen —
// „weniger als nichts" gibt es als Geometrie nicht. Die Komponente wirft
// nicht-positive Knoten deshalb mit einer sichtbaren Zeile heraus, statt sie
// still zu verschlucken (Tilgungen und Zuschüsse stehen mit Minus im
// Programm; die Seite erklärt sie in ihrer Liste).
//
// FARBE = GRUPPE (Teilhaushalt) aus der Ausgaben-Rampe; KEINE
// Bewertungsfarben (components/grafik/hantel.tsx). Suchtreffer heben sich
// per UMRISS hervor (Primärfarbe — finden, nicht bewerten).
//
// BESCHRIFTUNG: Schmale Kacheln beschriften vertikal; unter 40 px zeigt erst
// Antippen (oder der Fokus) den Namen — jede Kachel ist ein Knopf, die
// aktive steht als Zeile unter dem Bild. Deshalb HTML statt SVG: Knöpfe mit
// echtem Fokusring, umbruchfähiger Text, `aria-label` je Kachel.
//
// MOBIL (H4-A, eingebaut, kein Prop): Unter 520 px Containerbreite rendert
// die Komponente stattdessen eine <RanglisteSchiene> — gleiche Daten, gleiche
// Sortierung. Flächen-Labels wären auf 390 px schlicht unlesbar.

import { useMemo, useState, type ReactNode } from "react";
import { hierarchy, treemap, treemapSquarify } from "d3-hierarchy";
import { betrag, deMio } from "@/components/grafik/format";
import { RanglisteSchiene } from "@/components/grafik/rangliste-schiene";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type TreemapKnoten = {
  /** Eindeutiger Schlüssel (z. B. IPSP-Code) — `name` allein ist es nicht. */
  key: string;
  name: string;
  /** In Euro, > 0 — s. Kopfkommentar. */
  wert: number;
  gruppe: string;
  /** Eine Zusatzzeile für Detail und Rangliste („Stadtentwicklung"). */
  zusatz?: string;
};

const NEUTRALE_SCHRAFFUR =
  "repeating-linear-gradient(135deg, hsl(var(--muted-foreground) / 0.16) 0 3px, transparent 3px 6px)";

export function Treemap({
  knoten, farbe, buendelnAb = 12, treffer, aufRest, restHinweis, beleg,
}: {
  knoten: TreemapKnoten[];
  /** Farbe je Gruppe — EIN Schlüssel für Bild und Legende, von der Seite
   *  vergeben, damit er mit deren übrigen Bildern übereinstimmt. */
  farbe: (gruppe: string) => string;
  /** Ab diesem Rang bündelt die Rest-Kachel (Pflichtteil). */
  buendelnAb?: number;
  /** Schlüssel der Suchtreffer — Kacheln darin bekommen einen Umriss. */
  treffer?: Set<string>;
  /** Antippen der Rest-Kachel — üblicherweise: die Suche fokussieren. */
  aufRest?: () => void;
  /** Satz auf der Rest-Kachel, Default: „Ab hier übernimmt die Suche." */
  restHinweis?: string;
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: ReactNode;
}) {
  const { box, breite } = useBreite();
  const [aktiv, setAktiv] = useState<string | null>(null);

  const positive = useMemo(
    () => knoten.filter((k) => k.wert > 0).sort((a, b) => b.wert - a.wert),
    [knoten]);
  const verworfen = knoten.length - positive.length;

  const top = positive.slice(0, buendelnAb);
  const rest = positive.slice(buendelnAb);
  const restSumme = rest.reduce((s, k) => s + k.wert, 0);

  type Blatt = TreemapKnoten & { rest?: boolean };
  const hoehe = Math.round(Math.min(Math.max(breite * 0.56, 300), 440));

  const blaetter = useMemo(() => {
    if (breite < 520 || !top.length) return [];
    const kinder: Blatt[] = [...top];
    if (rest.length) {
      kinder.push({
        key: "__rest__", rest: true, wert: restSumme, gruppe: "",
        name: `+ ${rest.length.toLocaleString("de-DE")} weitere Vorhaben`,
      });
    }
    const wurzel = hierarchy<{ children?: Blatt[]; wert?: number }>({ children: kinder })
      .sum((d) => d.wert ?? 0)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    return treemap<{ children?: Blatt[]; wert?: number }>()
      .tile(treemapSquarify)
      .size([breite, hoehe])
      .paddingInner(3)(wurzel)
      .leaves();
    // `breite` steckt in `hoehe` mit drin; top/rest hängen an `knoten`.
  }, [breite, hoehe, top, rest, restSumme]);

  if (!positive.length) return null;

  const geld = (euro: number) => {
    const b = betrag(euro);
    return `${b.wert} ${b.einheit}`;
  };

  // Mobil: dieselben Daten, dieselbe Sortierung — als Rangliste mit Schiene.
  if (breite < 520) {
    return (
      <div ref={box} className="flex flex-col gap-2.5">
        <RanglisteSchiene
          einheit="Mio. €" nachkomma={1}
          zeilen={top.map((k) => ({
            label: k.name,
            wert: k.wert / 1e6,
            hervorgehoben: treffer?.has(k.key),
            zusatz: k.zusatz,
          }))}
          beleg={beleg}
        />
        {rest.length > 0 && (
          <p className="border-t border-dashed border-border pt-2 text-[11.5px] leading-relaxed text-muted-foreground">
            + {rest.length.toLocaleString("de-DE")} weitere Vorhaben · zusammen{" "}
            <span className="font-semibold tabular-nums text-foreground">{geld(restSumme)}</span>.{" "}
            {restHinweis ?? "Ab hier übernimmt die Suche."}
          </p>
        )}
        {verworfen > 0 && (
          <p className="text-[10.5px] leading-relaxed text-muted-foreground">
            {verworfen.toLocaleString("de-DE")} Vorhaben stehen mit null oder minus im
            Programm — eine Fläche kann das nicht zeigen, die Liste unten schon.
          </p>
        )}
      </div>
    );
  }

  const aktiverKnoten = aktiv === "__rest__"
    ? null
    : positive.find((k) => k.key === aktiv) ?? null;
  const gruppen = [...new Set(top.map((k) => k.gruppe))];

  return (
    <div ref={box} className="flex flex-col gap-2.5">
      <div className="relative" style={{ height: hoehe }} role="group"
        aria-label={`Kachelfläche: die ${top.length} größten Vorhaben, Fläche nach Gesamtsumme`}>
        {blaetter.map((b) => {
          const d = b.data as Blatt;
          const w = b.x1 - b.x0, h = b.y1 - b.y0;
          const schmalKachel = w < 64;
          const winzig = w < 40 || h < 34;
          const istTreffer = !d.rest && treffer?.has(d.key);
          const beschriftet = !winzig && (h >= 40 || w >= 64);
          return (
            <button
              key={d.key}
              type="button"
              onClick={() => (d.rest ? aufRest?.() : setAktiv(d.key))}
              onFocus={() => !d.rest && setAktiv(d.key)}
              aria-label={d.rest
                ? `${d.name}, zusammen ${geld(d.wert)}. ${restHinweis ?? "Ab hier übernimmt die Suche."}`
                : `${d.name}${d.zusatz ? `, ${d.zusatz}` : ""}: ${geld(d.wert)}`}
              className={cn(
                "absolute overflow-hidden rounded-[4px] text-left transition-shadow",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
                istTreffer && "z-10 ring-2 ring-primary ring-offset-1 ring-offset-card",
                aktiv === d.key && !d.rest && "z-10 ring-1 ring-foreground/50",
              )}
              style={{
                left: b.x0, top: b.y0, width: w, height: h,
                background: d.rest ? undefined : farbe(d.gruppe),
                backgroundImage: d.rest ? NEUTRALE_SCHRAFFUR : undefined,
                border: d.rest ? "1px dashed hsl(var(--border))" : undefined,
              }}
            >
              {d.rest ? (
                <span className="flex h-full flex-col justify-between p-2">
                  <span className="text-[11.5px] font-semibold leading-tight text-foreground/85">
                    {d.name}
                  </span>
                  <span className="text-[10.5px] leading-snug text-muted-foreground">
                    zusammen{" "}
                    <span className="font-semibold tabular-nums text-foreground/85">
                      {geld(d.wert)}
                    </span>
                    {w >= 150 && h >= 76 && (
                      <> · {restHinweis ?? "Ab hier übernimmt die Suche."}</>
                    )}
                  </span>
                </span>
              ) : beschriftet ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "flex h-full p-1.5",
                    schmalKachel
                      ? "flex-row-reverse items-start justify-end"
                      : "flex-col justify-between",
                  )}
                  style={{ color: "var(--hh-seg-text)" }}
                >
                  {/* Schmale Kacheln beschriften vertikal (GB-08). */}
                  <span
                    className={cn(
                      "min-h-0 overflow-hidden text-[11px] font-medium leading-tight",
                      schmalKachel && "[writing-mode:vertical-rl]",
                    )}
                  >
                    {d.name}
                  </span>
                  {/* Immer in Mio. mit einer Nachkommastelle — gemischte
                      Einheiten je Kachel („48,2" neben „750" Tsd.) wären ein
                      stiller Maßstabswechsel. Die Einheit steht in der
                      Legende, einmal für alle. */}
                  <span className="flex-none text-[11px] font-bold tabular-nums">
                    {deMio(d.wert / 1e6)}
                  </span>
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {/* Die aktive Kachel als Zeile — auch für Kacheln, die zu klein für
          eine Beschriftung sind: Antippen oder Fokus zeigt sie hier. */}
      <p className="min-h-[1.25rem] text-[12px] leading-snug text-muted-foreground" aria-live="polite">
        {aktiverKnoten ? (
          <>
            <span className="font-semibold text-foreground">{aktiverKnoten.name}</span>
            {aktiverKnoten.zusatz ? ` · ${aktiverKnoten.zusatz}` : ""} ·{" "}
            <span className="font-semibold tabular-nums text-foreground">
              {geld(aktiverKnoten.wert)}
            </span>
          </>
        ) : (
          "Kachel antippen oder mit Tab ansteuern — hier steht dann Name und Summe."
        )}
      </p>

      {/* Legende: EIN Farbschlüssel je Gruppe, plus die Rest-Schraffur. */}
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
        <span className="font-mono text-[9.5px] uppercase tracking-[0.09em]">
          Fläche = Gesamtsumme · Zahlen in Mio. €
        </span>
        {gruppen.map((g) => (
          <span key={g} className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="h-2.5 w-2.5 flex-none rounded-[2px]"
              style={{ background: farbe(g) }} />
            {g}
          </span>
        ))}
        {rest.length > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true"
              className="h-2.5 w-2.5 flex-none rounded-[2px] border border-dashed border-border"
              style={{ backgroundImage: NEUTRALE_SCHRAFFUR }} />
            gebündelte kleine Vorhaben
          </span>
        )}
        {beleg}
      </div>

      {verworfen > 0 && (
        <p className="text-[10.5px] leading-relaxed text-muted-foreground">
          {verworfen.toLocaleString("de-DE")} Vorhaben stehen mit null oder minus im
          Programm (Tilgungen, Zuschüsse, Verkäufe) — eine Fläche kann das nicht
          zeigen, die Liste unten schon.
        </p>
      )}
    </div>
  );
}
