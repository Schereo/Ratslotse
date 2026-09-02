"use client";

// <Treemap> — Größenordnung als Fläche (GB-08, Board H4-06).
//
// Eine Kachel ist ein Posten, ihre Fläche seine Größe: 1 mm² ist überall
// gleich viel Geld. Gerechnet wird ZUR LAUFZEIT — je Jahrgang, je Filter neu;
// genau der Fall, in dem Handrechnen (wie im Artboard) nicht skaliert. Die
// Geometrie samt ihrer Messungen wohnt in `kachelflaeche.ts`, damit die CI
// sie nachrechnen kann.
//
// WO GEBÜNDELT WIRD, IST DIE REST-KACHEL PFLICHT, kein Feature: Die Masse der
// kleinen Vorhaben ist selbst eine Größe. Wer nur die Top-Kacheln zeigte,
// behauptete, das Programm bestünde aus zwölf Projekten — tatsächlich sind es
// Tausende, und ihre Summe verdient dieselbe ehrliche Fläche. Ab der
// Rest-Kachel übernimmt die Suche. Ihre Schraffur ist NEUTRAL (muted), nicht
// die orange Lücken-Schraffur: Gebündelt ist keine Lücke und keine Abweichung.
//
// DIE REST-KACHEL KLAPPT AUF (seit 02.09.), wo sie wenige benannte Posten
// bündelt und die Seite keinen anderen Sprung (`aufRest`) vorgibt: Antippen
// lässt sie über die ganze Fläche wachsen, und die gebündelten Posten legen
// sich als eigene Kacheln hinein — wie eine Mappe, die man öffnet. Der Kopf
// der offenen Mappe trägt den Rückweg und die Summe, jede innere Kachel
// misst ihren Anteil weiter am GANZEN (nicht am Rest): Wer „Eigenleistungen"
// aufklappt, liest 0,2 % der Erträge, nicht 7 % des Sammelpostens. Bis
// 02.09. standen die gebündelten Namen nur als Legendenzeile darunter; Tim
// wollte sie anklicken können. Escape schließt, der Fokus kehrt zur
// Rest-Kachel zurück.
//
// Zerlegt die Fläche eine GESCHLOSSENE Liste — die zehn Ertragsarten eines
// Haushaltsjahres —, rechnet die Seite den Schnitt mit `buendelGrenze()` aus
// der Geometrie, statt einen Rang zu raten: gebündelt wird genau so weit,
// dass jede Kachel (die Rest-Kachel eingeschlossen) über die ganze
// Breitenspanne ihre Beschriftung trägt. Und weil hier jeder gebündelte
// Posten einen Namen hat, den das Dokument einzeln ausweist, gibt die Seite
// `restZusatz` mit — die Aufzählung steht dann in Ablesekarte, Legende und
// Mobil-Zeile. Weglassen heißt „hinter einen Auslöser", nie ersatzlos.
//
// NUR POSITIVE WERTE: Eine Fläche kann keinen negativen Betrag zeigen —
// „weniger als nichts" gibt es als Geometrie nicht. Die Komponente wirft
// nicht-positive Knoten deshalb mit einer sichtbaren Zeile heraus, statt sie
// still zu verschlucken (Tilgungen und Zuschüsse stehen mit Minus im
// Programm; die Seite erklärt sie in ihrer Liste).
//
// FARBE = GRUPPE aus einer der beiden Rampen — Teilhaushalt auf der
// Ausgabenseite, Ertragsart auf der Einnahmenseite; KEINE Bewertungsfarben
// (components/grafik/hantel.tsx). Suchtreffer heben sich per UMRISS hervor
// (Primärfarbe — finden, nicht bewerten).
//
// WELCHE TEXTFARBE eine Kachel trägt, weiß nur die Seite: Sie hat die
// Rampenstufe vergeben. `--hh-seg-text` (Vorgabe) trägt nur am lauten Ende
// der Rampe — am leisen steht der Ton dicht an der Karte, und weißer Text
// darauf ist weg. `textFarbe` ist deshalb derselbe Schlüssel wie `farbe`, nur
// für den Text; die Grenze und ihre Messung stehen in `kachelflaeche.ts`
// (`rampenText`), damit beide Aufrufer dieselbe Regel fahren.
//
// BESCHRIFTUNG IN DREI STUFEN (`textstufe`, kachelflaeche.ts): Eine große
// Kachel setzt ihre Zahl in Bricolage 28 px mit Einheit und Anteil, eine
// mittlere 18 px, eine kleine bleibt bei der 11-px-Zeile. Die Schrift folgt
// damit der Fläche — was viel Geld ist, steht auch groß da. Jede Kachel, die
// den Platz hat, trägt ihre Einheit (`traegtEinheit`); nur die kleinsten
// verlassen sich auf die Legende. Schmale Kacheln beschriften vertikal; unter
// 40 px zeigt erst Antippen (oder der Fokus) den Namen — jede Kachel ist ein
// Knopf, die aktive steht in der Ablesekarte unter dem Bild. Deshalb HTML
// statt SVG: Knöpfe mit echtem Fokusring, umbruchfähiger Text, `aria-label`
// je Kachel.
//
// BEWEGUNG (H5-07-Regel: einmalige Staffel beim Aufbau, keine Schleife): Die
// Kacheln blenden beim ersten Aufbau der Größe nach ein, 35 ms versetzt. Wer
// den Jahrgang wechselt, sieht dieselben Kacheln an ihren neuen Platz
// gleiten — Lage und Maß sind CSS-Übergänge auf dem Knopf, der Schlüssel der
// Kachel überlebt den Wechsel. Unter dem Zeiger hebt sich eine Kachel leicht
// (Spotlight: die anderen treten auf 72 % zurück, solange der Zeiger auf der
// Fläche ist). Die Regeln stehen in `app/globals.css` unter `.kf-*`; der
// globale `prefers-reduced-motion`-Block legt alles still.
//
// KEIN TOOLTIP, aber HOVER: Die Maus setzt dieselbe Kachel aktiv wie Tippen
// und Tab — zu sehen ist sie in der Ablesekarte UNTER dem Bild, nicht in
// einem schwebenden Kasten. Das ist die Ableseleisten-Regel des Baukastens
// (GB-00): Was nur beim Hovern existiert, fehlt im Ausdruck, im Screenshot
// und in der Vorlesehilfe. Der Zeiger verlässt die Fläche wieder — die Karte
// bleibt stehen, statt zurückzuspringen; und ohne aktive Kachel trägt sie
// die Summe aller Posten, nie eine Leerstelle.
//
// DESHALB TRÄGT EINE POSTEN-KACHEL AUCH KEINE ZEIGERHAND. Sie ist technisch
// ein Knopf — Touch und Tastatur brauchen einen —, aber für die Maus ist der
// Klick folgenlos: Das Überfahren hat die Karte darunter schon gefüllt, und
// hinter der Kachel liegt kein Ziel. Tailwinds Preflight gibt jedem `button`
// `cursor: pointer`; hier versprach die Hand eine Navigation, die es nicht
// gibt (Tims Befund 24.08.). Die Ausnahme ist die Rest-Kachel: Sie führt in
// die Suche (`aufRest`) oder klappt auf, und beides ist ein Ziel.
//
// DIE WÖRTER kommen von der Seite (`nomen`, `flaecheLabel`, `verworfenSatz`):
// Die Form zählt Vorhaben, Ertragsarten oder Bereiche — die Vorgaben sind der
// Investitionen-Fall, aus dem sie stammt.
//
// MOBIL (H4-A, eingebaut, kein Prop): Unter 520 px Containerbreite rendert
// die Komponente stattdessen eine <RanglisteSchiene> — gleiche Daten, gleiche
// Sortierung. Flächen-Labels wären auf 390 px schlicht unlesbar.

import {
  useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode,
} from "react";
import { ArrowLeft, Maximize2 } from "lucide-react";
import {
  TEXTMASSE, beschriftet as traegtText, kachelHoehe, kacheln, namenszeilenStufe, schmal,
  textstufe, traegtEinheit, type Kachel as KachelGeometrie,
} from "@/components/grafik/kachelflaeche";
import { amount, deMio, deZahl } from "@/components/grafik/format";
import { RanglisteSchiene } from "@/components/grafik/rangliste-schiene";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type TreemapKnoten = {
  /** Eindeutiger Schlüssel (z. B. IPSP-Code) — `name` allein ist es nicht. */
  key: string;
  name: string;
  /** In Euro, > 0 — s. Kopfkommentar. */
  value: number;
  gruppe: string;
  /** Eine Zusatzzeile für Detail und Rangliste („Stadtentwicklung"). */
  zusatz?: string;
};

const NEUTRALE_SCHRAFFUR =
  "repeating-linear-gradient(135deg, hsl(var(--muted-foreground) / 0.16) 0 3px, transparent 3px 6px)";

const REST = "__rest__";

/** Bis zu so vielen gebündelten Posten klappt die Rest-Kachel auf. Darüber
 *  (Investitionen: Tausende) trägt die Suche — und die Seite gibt dafür
 *  `aufRest` mit. */
const AUFKLAPPBAR_BIS = 40;

/** Die offene Mappe: Kopfband für Rückweg und Summe, Rand zu den inneren
 *  Kacheln. */
const MAPPE_KOPF = 38;
const MAPPE_RAND = 6;

export function Treemap({
  knoten, farbe, textFarbe, buendelnAb = 12, treffer, aufRest, restHinweis,
  restZusatz, beleg, nomen = "Vorhaben", flaecheLabel = "Fläche = Gesamtsumme",
  verworfenSatz, anteil,
}: {
  knoten: TreemapKnoten[];
  /** Farbe je Gruppe — EIN Schlüssel für Bild und Legende, von der Seite
   *  vergeben, damit er mit deren übrigen Bildern übereinstimmt. */
  farbe: (gruppe: string) => string;
  /** Textfarbe je Gruppe. Ohne Angabe `--hh-seg-text` — s. Kopfkommentar. */
  textFarbe?: (gruppe: string) => string;
  /** Ab diesem Rang bündelt die Rest-Kachel (Pflichtteil). */
  buendelnAb?: number;
  /** Schlüssel der Suchtreffer — Kacheln darin bekommen einen Umriss. */
  treffer?: Set<string>;
  /** Antippen der Rest-Kachel — üblicherweise: die Suche fokussieren. Ohne
   *  diese Angabe klappt die Rest-Kachel stattdessen auf (bis
   *  `AUFKLAPPBAR_BIS` Posten). */
  aufRest?: () => void;
  /** Satz auf der Rest-Kachel, Default: „Ab hier übernimmt die Suche." */
  restHinweis?: string;
  /** Aufzählung dessen, was im Sammelposten steckt („Transfererträge 9,4 ·
   *  …"). Steht in Ablesekarte, Legende und Mobil-Zeile — Pflicht dem Sinn
   *  nach, wo die gebündelten Posten NAMEN tragen, die sonst nirgends mehr
   *  stünden. Ohne sie bleibt es bei der Zahl (Investitionen: 520 Namen
   *  zählt niemand auf, dort trägt die Suche). */
  restZusatz?: string;
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: ReactNode;
  /** Was hier gezählt wird, im Plural — für Rest-Kachel und Vorlesehilfe. */
  nomen?: string;
  /** Der Maßstabssatz der Legende, ohne die Einheit (die hängt die Legende
   *  selbst an): „Fläche = Anteil an den Erträgen". */
  flaecheLabel?: string;
  /** Der Satz über nicht-positive Knoten — die Vorgabe ist der
   *  Investitionen-Fall (Tilgungen, Zuschüsse, Verkäufe). */
  verworfenSatz?: (count: number) => string;
  /** Kacheln und Ablesekarte nennen zusätzlich den Anteil an der
   *  Gesamtfläche. Nur sinnvoll, wo die Kacheln ein GANZES zerlegen — im
   *  Investitionen-Fall zeigt die Fläche einen Ausschnitt, dort wäre der
   *  Anteil eine Behauptung über einen Nenner, den es nicht gibt. */
  anteil?: boolean;
}) {
  const { box, breite } = useBreite();
  const [aktiv, setAktiv] = useState<string | null>(null);
  /** Die Kachel unter dem Zeiger bzw. im Fokus — nur für das Spotlight;
   *  `aktiv` bleibt stehen, `schwebt` geht mit dem Zeiger. */
  const [schwebt, setSchwebt] = useState<string | null>(null);
  const [offen, setOffen] = useState(false);
  const restKnopf = useRef<HTMLButtonElement>(null);

  const positive = useMemo(
    () => knoten.filter((k) => k.value > 0).sort((a, b) => b.value - a.value),
    [knoten]);
  const verworfen = knoten.length - positive.length;

  const top = positive.slice(0, buendelnAb);
  const rest = positive.slice(buendelnAb);
  const restSumme = rest.reduce((s, k) => s + k.value, 0);
  const gesamt = positive.reduce((s, k) => s + k.value, 0);
  const textVon = textFarbe ?? (() => "var(--hh-seg-text)");
  const verworfenText = verworfenSatz ?? ((n: number) =>
    `${n.toLocaleString("de-DE")} ${nomen} stehen mit null oder minus im `
    + "Programm (Tilgungen, Zuschüsse, Verkäufe) — eine Fläche kann das nicht "
    + "zeigen, die Liste unten schon.");
  const restName = `+ ${rest.length.toLocaleString("de-DE")} weitere ${nomen}`;
  const restSatz = restZusatz ?? restHinweis ?? "Ab hier übernimmt die Suche.";
  const aufklappbar = !aufRest && rest.length > 0 && rest.length <= AUFKLAPPBAR_BIS;

  type Blatt = TreemapKnoten & { rest?: boolean };
  const hoehe = kachelHoehe(breite);

  const blaetter = useMemo(() => {
    if (breite < 520 || !top.length) return [];
    const kinder: Blatt[] = [...top];
    if (rest.length) {
      kinder.push({ key: REST, rest: true, value: restSumme, gruppe: "", name: restName });
    }
    return kacheln(kinder, breite, hoehe);
    // `breite` steckt in `hoehe` mit drin; top/rest hängen an `knoten`.
  }, [breite, hoehe, top, rest, restSumme, restName]);

  // Die inneren Kacheln der offenen Mappe — dieselbe Geometrie, im Rahmen
  // unter dem Kopfband.
  const innen = useMemo(() => {
    if (!offen || !aufklappbar || breite < 520) return [];
    return kacheln(rest, breite - 2 * MAPPE_RAND, hoehe - MAPPE_KOPF - MAPPE_RAND)
      .map((k) => ({ ...k, x: k.x + MAPPE_RAND, y: k.y + MAPPE_KOPF }));
  }, [offen, aufklappbar, breite, hoehe, rest]);

  // Ein neuer Datensatz (Jahrgang, Filter) schließt die Mappe: Ihr Inhalt
  // wäre ein anderer.
  useEffect(() => { setOffen(false); }, [knoten]);

  const schliessen = useCallback(() => {
    setOffen(false);
    setAktiv(REST);
    restKnopf.current?.focus();
  }, []);

  if (!positive.length) return null;

  const geld = (euro: number) => {
    const b = amount(euro);
    return `${b.value} ${b.unit}`;
  };
  const prozent = (euro: number) => deZahl((euro / gesamt) * 100, 1);

  // Mobil: dieselben Daten, dieselbe Sortierung — als Rangliste mit Schiene.
  if (breite < 520) {
    return (
      <div ref={box} className="flex flex-col gap-2.5">
        <RanglisteSchiene
          unit="Mio. €" nachkomma={1}
          zeilen={top.map((k) => ({
            label: k.name,
            value: k.value / 1e6,
            hervorgehoben: treffer?.has(k.key),
            zusatz: k.zusatz,
          }))}
          beleg={beleg}
        />
        {rest.length > 0 && (
          <p className="border-t border-dashed border-border pt-2 text-[11.5px] leading-relaxed text-muted-foreground">
            {restName} · zusammen{" "}
            <span className="font-semibold tabular-nums text-foreground">{geld(restSumme)}</span>.{" "}
            {restSatz}
          </p>
        )}
        {verworfen > 0 && (
          <p className="text-[10.5px] leading-relaxed text-muted-foreground">
            {verworfenText(verworfen)}
          </p>
        )}
      </div>
    );
  }

  const aktiverKnoten: (Pick<TreemapKnoten, "name" | "value" | "zusatz"> & { gruppe?: string; rest?: boolean }) | null =
    aktiv === REST
      ? (rest.length ? { name: restName, value: restSumme, zusatz: restZusatz, rest: true } : null)
      : positive.find((k) => k.key === aktiv) ?? null;
  const gruppen = [...new Set(top.map((k) => k.gruppe))];
  const spotlight = schwebt != null;

  const restGeometrie = blaetter.find((b) => b.daten.rest);

  return (
    <div ref={box} className="flex flex-col gap-2.5">
      <div
        className="relative" style={{ height: hoehe }} role="group"
        aria-label={`Kachelfläche: ${top.length} ${nomen}, ${flaecheLabel}`}
        onMouseLeave={() => setSchwebt(null)}
        onKeyDown={(e) => {
          if (e.key === "Escape" && offen) { e.stopPropagation(); schliessen(); }
        }}
      >
        {blaetter.map((b, i) => {
          const d = b.daten;
          if (d.rest) {
            // Die Rest-Kachel: geschlossen eine Kachel wie die anderen (nur
            // schraffiert), offen die Mappe über der ganzen Fläche.
            const g = offen ? { x: 0, y: 0, breite, hoehe } : b;
            return (
              <button
                key={REST}
                ref={restKnopf}
                type="button"
                onClick={() => {
                  if (aufRest) { aufRest(); return; }
                  if (!aufklappbar) { setAktiv(REST); return; }
                  if (offen) schliessen(); else { setOffen(true); setAktiv(REST); }
                }}
                onFocus={() => { setAktiv(REST); setSchwebt(REST); }}
                onBlur={() => setSchwebt((s) => (s === REST ? null : s))}
                onMouseEnter={() => { setAktiv(REST); setSchwebt(REST); }}
                aria-expanded={aufklappbar ? offen : undefined}
                aria-label={offen
                  ? `Mappe schließen — zurück zu allen ${nomen}`
                  : `${restName}, zusammen ${geld(restSumme)}. ${restSatz}${aufklappbar ? " Antippen klappt die Posten auf." : ""}`}
                data-schwebt={schwebt === REST && !offen}
                data-gedimmt={spotlight && schwebt !== REST && !offen}
                className={cn(
                  "kf-kachel kf-auf absolute overflow-hidden rounded-[6px] text-left",
                  "bg-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
                  aufRest || aufklappbar ? "cursor-pointer" : "cursor-default",
                  aktiv === REST && !offen && "ring-1 ring-inset ring-foreground/40",
                )}
                style={{
                  left: g.x, top: g.y, width: g.breite, height: g.hoehe,
                  zIndex: offen ? 20 : schwebt === REST ? 10 : undefined,
                  backgroundImage: NEUTRALE_SCHRAFFUR,
                  border: "1px dashed hsl(var(--border))",
                  animationDelay: `${i * 35}ms`,
                }}
              >
                {offen ? (
                  <MappenKopf nomen={nomen} anzahl={rest.length} summe={geld(restSumme)}
                    anteil={anteil ? prozent(restSumme) : undefined} />
                ) : (
                  <RestInhalt
                    name={restName} summe={geld(restSumme)} breite={g.breite} hoehe={g.hoehe}
                    hinweis={restHinweis ?? "Ab hier übernimmt die Suche."}
                    aufklappbar={aufklappbar}
                  />
                )}
              </button>
            );
          }
          return (
            <Kachel
              key={d.key}
              geometrie={b}
              daten={d}
              farbe={farbe(d.gruppe)}
              textFarbe={textVon(d.gruppe)}
              einheit="Mio. €"
              anteil={anteil ? prozent(d.value) : undefined}
              treffer={!!treffer?.has(d.key)}
              aktiv={aktiv === d.key}
              schwebt={schwebt === d.key}
              gedimmt={spotlight && schwebt !== d.key}
              verdeckt={offen}
              verzoegerung={i * 35}
              aufSchweben={(an) => {
                if (an) { setAktiv(d.key); setSchwebt(d.key); }
                else setSchwebt((s) => (s === d.key ? null : s));
              }}
              aufTippen={() => setAktiv(d.key)}
              beschreibung={`${d.name}${d.zusatz ? `, ${d.zusatz}` : ""}: ${geld(d.value)}`}
            />
          );
        })}

        {/* Die inneren Kacheln der offenen Mappe — verzögert, damit sie erst
            erscheinen, wenn die Mappe ihre Größe hat. */}
        {innen.map((b, i) => {
          const d = b.daten;
          return (
            <Kachel
              key={`innen-${d.key}`}
              geometrie={b}
              daten={d}
              farbe={farbe(d.gruppe)}
              textFarbe={textVon(d.gruppe)}
              einheit="Mio. €"
              anteil={anteil ? prozent(d.value) : undefined}
              treffer={!!treffer?.has(d.key)}
              aktiv={aktiv === d.key}
              schwebt={schwebt === d.key}
              gedimmt={spotlight && schwebt !== d.key && schwebt !== REST}
              innen
              verzoegerung={180 + i * 45}
              aufSchweben={(an) => {
                if (an) { setAktiv(d.key); setSchwebt(d.key); }
                else setSchwebt((s) => (s === d.key ? null : s));
              }}
              aufTippen={() => setAktiv(d.key)}
              beschreibung={`${d.name}${d.zusatz ? `, ${d.zusatz}` : ""}: ${geld(d.value)}`}
            />
          );
        })}
        {/* Vorlesehilfe: Der Sprung in die Mappe ist sonst nur zu sehen. */}
        {restGeometrie && (
          <span className="sr-only" aria-live="polite">
            {offen ? `${rest.length} gebündelte ${nomen} aufgeklappt.` : ""}
          </span>
        )}
      </div>

      {/* Die Ablesekarte: die aktive Kachel — oder, ohne eine, die Summe.
          Auch für Kacheln, die zu klein für eine Beschriftung sind: Antippen
          oder Fokus zeigt sie hier. */}
      <Ablesekarte
        farbe={aktiverKnoten && !aktiverKnoten.rest && aktiverKnoten.gruppe != null
          ? farbe(aktiverKnoten.gruppe) : undefined}
        schraffiert={!!aktiverKnoten?.rest}
        name={aktiverKnoten ? aktiverKnoten.name : `Alle ${positive.length.toLocaleString("de-DE")} ${nomen}`}
        zusatz={aktiverKnoten
          ? (aktiverKnoten.zusatz ?? (aktiverKnoten.rest ? restSatz : undefined))
          : "Kachel überfahren, antippen oder mit Tab ansteuern — hier steht dann Name und Summe."}
        summe={geld(aktiverKnoten ? aktiverKnoten.value : gesamt)}
        anteil={anteil && gesamt > 0
          ? (aktiverKnoten ? (aktiverKnoten.value / gesamt) * 100 : 100)
          : undefined}
      />

      {/* Legende: EIN Farbschlüssel je Gruppe, plus die Rest-Schraffur. */}
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
        <span className="font-mono text-[9.5px] uppercase tracking-[0.09em]">
          {flaecheLabel} · Zahlen in Mio. €
        </span>
        {gruppen.map((g) => (
          <span key={g} className="inline-flex items-center gap-1.5">
            <span aria-hidden="true"
              className="h-2.5 w-2.5 flex-none rounded-[2px] ring-1 ring-inset ring-foreground/15"
              style={{ background: farbe(g) }} />
            {g}
          </span>
        ))}
        {rest.length > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true"
              className="h-2.5 w-2.5 flex-none rounded-[2px] border border-dashed border-border"
              style={{ backgroundImage: NEUTRALE_SCHRAFFUR }} />
            {restZusatz ?? `gebündelte kleine ${nomen}`}
          </span>
        )}
        {beleg}
      </div>

      {verworfen > 0 && (
        <p className="text-[10.5px] leading-relaxed text-muted-foreground">
          {verworfenText(verworfen)}
        </p>
      )}
    </div>
  );
}

/** Eine Posten-Kachel: Knopf, Farbe, gestufte Beschriftung. */
function Kachel({
  geometrie: b, daten: d, farbe, textFarbe, einheit, anteil, treffer, aktiv, schwebt,
  gedimmt, verdeckt, innen, verzoegerung, aufSchweben, aufTippen, beschreibung,
}: {
  geometrie: KachelGeometrie<TreemapKnoten>;
  daten: TreemapKnoten;
  farbe: string;
  textFarbe: string;
  einheit: string;
  /** Der Anteil als fertige Zahl („49,3") — oder nichts. */
  anteil?: string;
  treffer: boolean;
  aktiv: boolean;
  schwebt: boolean;
  gedimmt: boolean;
  /** Unter der offenen Mappe: nicht erreichbar, nicht vorgelesen. */
  verdeckt?: boolean;
  /** In der offenen Mappe: über ihr. */
  innen?: boolean;
  verzoegerung: number;
  aufSchweben: (an: boolean) => void;
  aufTippen: () => void;
  beschreibung: string;
}) {
  const w = b.breite, h = b.hoehe;
  const schmalKachel = schmal(w);
  const beschriftet = traegtText(w, h);
  const stufe = schmalKachel ? "small" : textstufe(w, h);
  const mitEinheit = traegtEinheit(w, h);
  const zusatz = stufe === "large" && !!d.zusatz && h >= 170;
  const mitAnteil = !!anteil && !schmalKachel
    && (stufe === "large" || (stufe === "medium" && h >= 100));
  // Die Zusatzzeile kostet den Namen eine Zeile — sonst stünde der Block
  // über dem Zahlenblock und würde gestaucht.
  const zeilen = Math.max(1, namenszeilenStufe(stufe, w, h) - (zusatz ? 1 : 0));
  const zeile = TEXTMASSE[stufe].zeile;
  // Zahl und Anteilszeile mit festen Zeilenhöhen (s. TEXTMASSE): 28 + 4 + 16
  // = 48 ≤ 50 (groß), 18 + 2 + 14 = 34 ≤ 36 (mittel), 14 ≤ 16 (klein).
  const zahlZeile = stufe === "large" ? 28 : stufe === "medium" ? 18 : 14;
  const anteilZeile = stufe === "large" ? 16 : 14;
  const style: CSSProperties = {
    left: b.x, top: b.y, width: w, height: h,
    background: farbe,
    zIndex: schwebt || treffer ? (innen ? 40 : 10) : innen ? 30 : undefined,
    animationDelay: `${verzoegerung}ms`,
  };
  return (
    <button
      type="button"
      onClick={aufTippen}
      onFocus={() => aufSchweben(true)}
      onBlur={() => aufSchweben(false)}
      onMouseEnter={() => aufSchweben(true)}
      aria-label={beschreibung}
      aria-hidden={verdeckt || undefined}
      tabIndex={verdeckt ? -1 : undefined}
      data-schwebt={schwebt}
      data-gedimmt={gedimmt}
      className={cn(
        "kf-kachel kf-auf absolute overflow-hidden rounded-[6px] text-left",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
        // Zeigerhand nur, wo der Klick etwas tut — s. Kopfkommentar.
        "cursor-default",
        verdeckt && "pointer-events-none",
        treffer && "ring-2 ring-primary ring-offset-1 ring-offset-card",
        aktiv && !treffer && "ring-1 ring-inset ring-foreground/40",
      )}
      style={style}
    >
      {beschriftet && (
        <span
          aria-hidden="true"
          className={cn(
            "relative flex h-full",
            schmalKachel
              ? "flex-row-reverse items-start justify-end p-1.5"
              : "flex-col justify-between",
            !schmalKachel && stufe === "large" && "p-2.5",
            !schmalKachel && stufe === "medium" && "p-2",
            !schmalKachel && stufe === "small" && "p-1.5",
          )}
          style={{ color: textFarbe }}
        >
          {/* `min-h-0`, damit der Zahlenblock nie aus der Kachel rutscht —
              der Name ist ohnehin auf seine Zeilen geklemmt. Die kleine
              Stufe bekommt keinen Zwischenraum: Ihr Zeilenmaß (kachelflaeche
              .ts, MASSE) rechnet mit 12 + 16 px, jeder Pixel mehr schnitt
              „Abrissmaßnahmen" in der dritten Zeile durch. */}
          <span className={cn("flex min-h-0 flex-col", stufe !== "small" && "gap-0.5")}>
            {/* Schmale Kacheln beschriften vertikal (GB-08). */}
            <span
              className={cn(
                "min-h-0 overflow-hidden break-words",
                zeilen > 1 && "hyphens-auto",
                stufe === "large" && "text-[13.5px] font-semibold",
                stufe === "medium" && "text-[12.5px] font-semibold",
                stufe === "small" && "text-[11px] font-medium",
                schmalKachel && "[writing-mode:vertical-rl]",
              )}
              style={{
                display: "-webkit-box",
                WebkitBoxOrient: "vertical",
                WebkitLineClamp: zeilen,
                lineHeight: `${zeile}px`,
              }}
            >
              {d.name}
            </span>
            {zusatz && (
              <span className="truncate text-[11.5px] opacity-80" style={{ lineHeight: `${zeile}px` }}>
                {d.zusatz}
              </span>
            )}
          </span>
          {/* Immer in Mio. mit einer Nachkommastelle — gemischte Einheiten je
              Kachel („48,2" neben „750" Tsd.) wären ein stiller
              Maßstabswechsel. Die Einheit steht mit auf der Kachel, sobald sie
              Platz hat, und in der Legende einmal für alle. */}
          <span
            className={cn("flex-none", schmalKachel && "[writing-mode:vertical-rl]")}
            style={{ lineHeight: `${zahlZeile}px` }}
          >
            <span className={cn(
              "block whitespace-nowrap tabular-nums",
              stufe === "large" && "font-display text-[28px] font-bold tracking-tight",
              stufe === "medium" && "font-display text-[18px] font-bold tracking-tight",
              stufe === "small" && "text-[11.5px] font-bold",
            )} style={{ lineHeight: `${zahlZeile}px` }}>
              {deMio(d.value / 1e6)}
              {/* Ein geschütztes Leerzeichen statt eines Randes: Der Rand
                  stünde bei vertikaler Schrift auf der falschen Seite
                  („1,8Mio. €"). */}
              {mitEinheit && (
                <span className={cn(
                  "font-sans font-semibold opacity-85",
                  stufe === "large" && "text-[12px] tracking-normal",
                  stufe === "medium" && "text-[11px] tracking-normal",
                  stufe === "small" && "text-[10px]",
                )}>
                  {" "}
                  {einheit}
                </span>
              )}
            </span>
            {mitAnteil && (
              <span className={cn(
                "block whitespace-nowrap tabular-nums opacity-85",
                stufe === "large" ? "mt-1 text-[11.5px]" : "mt-0.5 text-[10.5px]",
              )} style={{ lineHeight: `${anteilZeile}px` }}>
                {anteil}&nbsp;% der Fläche
              </span>
            )}
          </span>
        </span>
      )}
    </button>
  );
}

/** Der Inhalt der geschlossenen Rest-Kachel. */
function RestInhalt({ name, summe, breite: w, hoehe: h, hinweis, aufklappbar }: {
  name: string; summe: string; breite: number; hoehe: number; hinweis: string;
  aufklappbar: boolean;
}) {
  // Dieselben drei Stufen wie die bunten Kacheln — die Rest-Kachel der
  // Investitionen ist die größte der Fläche und stand mit 12,5 px daneben.
  const stufe = textstufe(w, h);
  return (
    <span className={cn(
      "relative flex h-full flex-col justify-between",
      stufe === "large" ? "p-2.5" : "p-2",
    )}>
      {aufklappbar && (
        <Maximize2 aria-hidden="true"
          className="absolute right-2 top-2 h-3 w-3 text-muted-foreground/80" />
      )}
      {/* Dieselbe Trennregel wie auf den bunten Kacheln — ohne sie schnitt
          „Ertragsarten" quer ab (lang="de" trennt). */}
      <span className={cn(
        "hyphens-auto break-words pr-4 font-semibold leading-tight text-foreground/85",
        stufe === "large" && "text-[13.5px]",
        stufe === "medium" && "text-[12.5px]",
        stufe === "small" && "text-[11.5px]",
      )}>
        {name}
      </span>
      <span className="text-[10.5px] leading-snug text-muted-foreground">
        {/* „zusammen" nur, wo es die Zahl nicht verdrängt: Auf einer 100-px-
            Kachel schob das Wort die Summe aus dem Bild — die Zahl ist die
            Auskunft, das Wort Beiwerk. */}
        {w >= 150 && <>zusammen{" "}</>}
        <span className={cn(
          "whitespace-nowrap font-semibold tabular-nums text-foreground/85",
          stufe === "large" && "font-display text-[24px] font-bold leading-none tracking-tight",
          stufe === "medium" && "font-display text-[16px] font-bold leading-none tracking-tight",
        )}>
          {summe}
        </span>
        {w >= 150 && h >= 76 && (
          <span className={cn("block", stufe === "large" ? "mt-1.5 text-[11.5px]" : "mt-0.5")}>
            {hinweis}
          </span>
        )}
      </span>
    </span>
  );
}

/** Das Kopfband der offenen Mappe: Rückweg und Summe. Kein eigener Knopf —
 *  die Mappe selbst ist der Knopf, und ein Knopf im Knopf ist kein HTML. */
function MappenKopf({ nomen, anzahl, summe, anteil }: {
  nomen: string; anzahl: number; summe: string; anteil?: string;
}) {
  return (
    // Oben festgemacht: Ein Knopf zentriert seinen Inhalt senkrecht, und in
    // einer 440 px hohen Mappe läge das Kopfband sonst mitten unter den
    // inneren Kacheln (so gesehen, 02.09.).
    <span className="absolute inset-x-0 top-0 flex items-center gap-2.5 px-2 text-[11.5px]"
      style={{ height: MAPPE_KOPF }}>
      <span className="inline-flex flex-none items-center gap-1 rounded-md border border-border bg-card px-2 py-[3px] font-semibold text-primary shadow-sm">
        <ArrowLeft aria-hidden="true" className="h-3 w-3" /> Alle {nomen}
      </span>
      <span className="min-w-0 truncate text-muted-foreground">
        {anzahl.toLocaleString("de-DE")} weitere {nomen} · zusammen{" "}
        <span className="font-semibold tabular-nums text-foreground/85">{summe}</span>
        {anteil && <> · {anteil}&nbsp;% der Fläche</>}
      </span>
    </span>
  );
}

/** Die Zeile unter dem Bild, als Karte: Farbmarke, Name, Zusatz, Summe —
 *  und, wo die Fläche ein Ganzes zerlegt, der Anteil als schmaler Balken.
 *  Feste Mindesthöhe, damit nichts springt, wenn der Zusatz fehlt. */
function Ablesekarte({ farbe, schraffiert, name, zusatz, summe, anteil }: {
  farbe?: string; schraffiert: boolean; name: string; zusatz?: string;
  summe: string; anteil?: number;
}) {
  return (
    <div
      aria-live="polite"
      className="flex min-h-[58px] items-center gap-3 rounded-xl border border-border/70 bg-muted/30 px-3.5 py-2.5"
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-3.5 w-3.5 flex-none rounded-[3px] transition-colors duration-200",
          schraffiert && "border border-dashed border-border",
          !farbe && !schraffiert && "ring-1 ring-inset ring-foreground/20",
        )}
        style={{
          background: farbe,
          backgroundImage: schraffiert ? NEUTRALE_SCHRAFFUR : undefined,
        }}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold leading-snug text-foreground">{name}</span>
        {zusatz && (
          <span className="block truncate text-[11.5px] leading-snug text-muted-foreground">{zusatz}</span>
        )}
        {anteil != null && (
          <span className="mt-1.5 block h-[3px] w-full max-w-[280px] overflow-hidden rounded-full bg-border/70">
            <span
              className="block h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
              style={{ width: `${Math.max(1, Math.min(100, anteil))}%` }}
            />
          </span>
        )}
      </span>
      <span className="flex-none text-right">
        <span className="block whitespace-nowrap font-display text-[20px] font-bold leading-none tracking-tight tabular-nums text-foreground">
          {summe}
        </span>
        {anteil != null && (
          <span className="mt-1 block text-[11px] leading-none tabular-nums text-muted-foreground">
            {deZahl(anteil, 1)}&nbsp;% der Fläche
          </span>
        )}
      </span>
    </div>
  );
}
