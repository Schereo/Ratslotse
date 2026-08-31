"use client";

// Haushalts-Labor 2.0 (Entwürfe vom 24.08.2026, Tims Freigabe: „so bauen“).
//
// AUS ZWEI REGLERN WERDEN DREI WERKBÄNKE. Das Labor von Runde 2 hatte genau
// zwei Stellschrauben und war nach einem Zug durchgespielt — für ein Werkzeug
// mit eigener Adresse (Schritt 12 seit #707) zu wenig Werkstatt. Jetzt:
//
//   * **Einnahmen** — Gewerbesteuer (mit Städte-Leiter und eigener Historie),
//     Grundsteuer B (neu, mit belegter Aufteilung), Hundesteuer (neu, als
//     Anti-Stammtisch-Regler), Gebühren als absichtlich gesperrte Schraube.
//   * **Ausgaben** — die freiwilligen Teilhaushalte, seit 24.08. in beide
//     Richtungen: kürzen wie aufstocken („heute“ in der Mitte).
//   * **Investitionen & Finanzierung** — Vorhaben-Schalter und der
//     Kredit-Schalter; bewusst mit EIGENEN Zielgrößen (Kasse, Schulden),
//     weil Investitionen die Ergebnis-Lücke fast nicht bewegen. Ihre
//     Schalter rechnen deshalb NICHT in den Lücken-Balken hinein.
//
// Der ZUSTAND aller Werkbänke liegt hier, nicht in den Panels: Wer die
// Werkbank wechselt, verliert nichts (die Panels werden unmontiert — die
// Lehre aus #705 gilt auch innerhalb einer Seite).
//
// NEU IN DER ERGEBNIS-SPALTE:
//   * Der **Rücklagen-Pfad**: „reicht rechnerisch 2,7 Jahre“ wird eine Kurve
//     über die Planjahre mit Kipp-Jahr — aus den Jahresergebnissen des
//     Gesamtergebnishaushalts (Entwurf!), die eigene Wirkung konstant
//     fortgeschrieben. Ohne diese Reihe fällt die Karte auf die alte
//     Reichweiten-Rechnung zurück.
//   * Die **Dämpfer-Spanne**: Der Finanzausgleich wird weiter NICHT
//     verrechnet (Regel seit Runde 1) — aber die Unsicherheit wird gezeigt,
//     als Spanne aus den echten Ausgleichsjahren statt als Fußnote.
//
// UNVERÄNDERTE REGELN:
//  1. Nur Regler, für die es echte Zahlen gibt — fehlt eine Reihe,
//     verschwindet der Regler, statt mit einer Schätzung zu rechnen.
//  2. „Was dagegen rechnet“ ist immer sichtbar, nicht ausklappbar.
//  3. Produktzahlen und Städtewerte sind Vergleich, nie Rechengrundlage.
//
// AUFBAU: Werkbank-Wahl und Szenario-Chips über die volle Breite, darunter
// links das aktive Panel, rechts die Ergebnis-Spalte (330 px, klebend). Auf
// Mobil klebt die kompakte Ergebnis-Karte über der Tab-Leiste (H4-16) —
// dieselbe Mechanik wie bisher, Andockkante `TABLEISTE_HOEHE`.

import { useMemo, useState, type CSSProperties } from "react";
import { RotateCcw } from "lucide-react";
import { TABLEISTE_HOEHE } from "@/components/nav";
import {
  HaushaltAuswahl, PLAN_ART_LABEL, Produkt, bereiche, deMio, juengsteRuecklage,
  jahreSortiert, mio, planGegenIst, summe,
} from "@/lib/haushalt";
import { PFLICHT_ZUORDNUNG } from "@/lib/haushalt-pflicht";
import {
  daempferSpanne, grundsteuerAnteilA, hebesatzHeute, letzterSteuerbetrag,
  planjahrErgebnisse, ruecklagenPfad, staedteHebesaetze,
} from "@/lib/haushalt-labor";
import type { VergleichDaten } from "@/lib/haushalt-vergleich";
import type { ProgrammDaten } from "@/lib/haushalt-investitionsprogramm";
import type { SchuldenDaten } from "@/lib/haushalt-schulden";
import { Beleg } from "@/components/haushalt/quelle";
import { EinnahmenWerkbank } from "@/components/haushalt/labor-einnahmen";
import { AusgabenWerkbank } from "@/components/haushalt/labor-ausgaben";
import { InvestWerkbank } from "@/components/haushalt/labor-invest";
import { RuecklagenPfadGrafik } from "@/components/haushalt/ruecklagen-pfad";
import { cn } from "@/lib/utils";

const MAX_KUERZUNG = 30;
/** Spielraum der Hebesatz-Regler in Punkten, beide Richtungen. ±50 war zu
 *  eng (Tims Befund 26.08.2026): Wolfsburg stand im 2025er-Städtevergleich
 *  bei 360 % — von Oldenburgs 439 aus 79 Punkte runter und mit ±50
 *  unerreichbar. ±100 deckt jede Stadt der Leiter UND die eigene Reihe seit
 *  1980 (370–439) in beide Richtungen, rund und symmetrisch. Die
 *  Je-Punkt-Rechnung bleibt der erklärte lineare Überschlag — auch am
 *  Anschlag steht „bei unveränderten Gewinnen" daneben. */
const MAX_PUNKTE = 100;
const MAX_HUNDE = 100;

function eur(v: number): string {
  return v.toLocaleString("de-DE", { maximumFractionDigits: 0 });
}

/** Geplant gegen tatsächlich (Jahresabschlüsse) — der Maßstab dafür, wie
 *  belastbar die Zahl ist, gegen die hier angerechnet wird. */
function PlanIst({ daten }: { daten: HaushaltAuswahl<"ergebnisrechnung"> }) {
  const reihe = planGegenIst(daten);
  if (reihe.length < 2) return null;
  const spanne = Math.max(...reihe.flatMap((r) => [Math.abs(r.plan), Math.abs(r.ist)]));
  const besser = reihe.filter((r) => r.delta > 0).length;
  const deltas = reihe.map((r) => r.delta).sort((a, b) => a - b);
  // Jahrgänge, deren „geplant" nicht der nackte Ansatz ist (2018, 2020).
  const abweichenderBezug = reihe.filter((r) => r.planArt !== "ansatz");

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Wie verlässlich ist der Plan?
      </p>
      <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/85">
        {besser === reihe.length ? (
          <>In <strong>allen {reihe.length} Jahren</strong>, für die ein Jahresabschluss vorliegt,
          fiel das Ergebnis besser aus als geplant — zwischen {deMio(deltas[0])} und{" "}
          {deMio(deltas[deltas.length - 1])}&#8239;Mio.&nbsp;€.</>
        ) : (
          <>In {besser} von {reihe.length} Jahren fiel das Ergebnis besser aus als geplant.</>
        )}
      </p>
      <div className="mt-3 flex flex-col gap-2">
        {reihe.map((r) => (
          <div key={r.year} className="flex items-center gap-2.5">
            <span className="w-9 shrink-0 font-mono text-[11px] text-muted-foreground">{r.year}</span>
            {/* Zwei Balken an gemeinsamer Nulllinie: Plan grau, Ist blau. */}
            <span className="relative h-6 min-w-0 flex-1">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              {[{ v: r.plan, farbe: "var(--hh-aus-4)", top: "top-0.5" },
                { v: r.ist, farbe: "var(--hh-ein-1)", top: "top-[13px]" }].map(({ v, farbe, top }, i) => (
                <span key={i} className={cn("absolute h-[10px] rounded-[2px]", top)}
                  style={{
                    background: farbe,
                    left: v < 0 ? `${50 - (Math.abs(v) / spanne) * 50}%` : "50%",
                    width: `${Math.max((Math.abs(v) / spanne) * 50, 0.8)}%`,
                  }} />
              ))}
            </span>
            <span className="w-[100px] shrink-0 text-right font-mono text-[11px] tabular-nums">
              <span className="text-muted-foreground">{deMio(r.plan)}</span>
              <span className="mx-1 text-muted-foreground">→</span>
              <span className="font-semibold">{deMio(r.ist)}</span>
              {/* Jahrgänge, deren „geplant" nicht der nackte Ansatz ist,
                  tragen ein Sternchen — die Fußnote sagt, was gemeint ist. */}
              <span className="w-2 text-left text-muted-foreground">
                {r.planArt !== "ansatz" ? "*" : " "}
              </span>
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-[9px] w-3 rounded-[2px]" style={{ background: "var(--hh-aus-4)" }} />geplant
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-[9px] w-3 rounded-[2px]" style={{ background: "var(--hh-ein-1)" }} />tatsächlich
        </span>
        <span>· Jahresergebnis in Mio.&nbsp;€</span>
      </div>
      <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Aus den Jahresabschlüssen der Stadt <Beleg q="jahresabschluss" /> — ordentliches plus außerordentliches
        Ergebnis. Das heißt nicht, dass das Minus oben unecht wäre: Es heißt, dass ein Plan Vorsicht
        einpreist. Für {reihe[reihe.length - 1].year + 1} und später liegt noch kein Abschluss vor.
        {abweichenderBezug.length > 0 && (
          <>
            {" "}* In {abweichenderBezug.map((r) => r.year).join(" und ")} vergleicht der
            Abschluss nicht mit dem ursprünglichen Ansatz, sondern mit dem fortgeschriebenen
            Plan ({[...new Set(abweichenderBezug.map((r) => PLAN_ART_LABEL[r.planArt]))].join(", ")}
            ) — so rechnet die Stadt dort selbst.
          </>
        )}
      </p>
    </div>
  );
}

type Werkbank = "einnahmen" | "ausgaben" | "invest";

const WERKBAENKE: { id: Werkbank; nr: number; titel: string; zielgroesse: string }[] = [
  { id: "einnahmen", nr: 1, titel: "Einnahmen", zielgroesse: "Zielgröße: die Lücke" },
  { id: "ausgaben", nr: 2, titel: "Ausgaben", zielgroesse: "Zielgröße: die Lücke" },
  { id: "invest", nr: 3, titel: "Investitionen & Finanzierung", zielgroesse: "Zielgröße: Kasse & Schulden" },
];

export function Labor({ daten, produkte, produktJahr, vergleich, programm, schulden }: {
  daten: HaushaltAuswahl<"jahre" | "steuern" | "steuerkraft" | "einwohner"
    | "ergebnisrechnung" | "hebesaetze" | "ergebnishaushalt" | "gebuehren"
    | "haushaltssatzung" | "ruecklage">;
  produkte: Produkt[];
  produktJahr: number | null;
  vergleich: VergleichDaten | null;
  programm: ProgrammDaten | null;
  schulden: SchuldenDaten | null;
}) {
  const [werkbank, setWerkbank] = useState<Werkbank>("einnahmen");
  const [punkte, setPunkte] = useState(0);
  const [grundstPunkte, setGrundstPunkte] = useState(0);
  const [hundePct, setHundePct] = useState(0);
  // Prozentuale ÄNDERUNG je freiwilligem Teilhaushalt — negativ = kürzen,
  // positiv = aufstocken. Bis 24.08.2026 hieß der Zustand `kuerzung` und
  // konnte nur in eine Richtung (Tims Befund: „ein bisschen random, dass man
  // viele Regler nicht in die andere Richtung schieben kann") — dieselbe
  // Symmetrie wie an den Hebesatz-Reglern gilt jetzt überall.
  const [aenderung, setAenderung] = useState<Record<string, number>>({});
  const [vorhabenAus, setVorhabenAus] = useState<Record<string, boolean>>({});
  const [kredit, setKredit] = useState(false);

  const basis = useMemo(() => {
    const jahre = jahreSortiert(daten);
    const year = jahre[jahre.length - 1];
    const zeilen = daten.jahre[String(year)] ?? [];
    const g = summe(zeilen);
    const defizit = g?.revenues != null && g?.expenses != null
      ? mio(g.expenses - g.revenues) ?? 0 : 0;
    const freiwillig = bereiche(zeilen)
      .filter((z) => PFLICHT_ZUORDNUNG[z.area]?.stufe === "freiwillig")
      .map((z) => ({ area: z.area, aus: mio(z.expenses) ?? 0 }))
      .sort((a, b) => b.aus - a.aus);
    const kraft = daten.steuerkraft.filter((k) => k.messzahl != null && k.zuweisungen != null).slice(-2);
    return { year, defizit, freiwillig, kraft };
  }, [daten]);

  // Die Grundlagen der drei Einnahme-Regler — jeder aus seiner Reihe, keiner
  // ohne (Regel 1). Die Grundsteuer braucht ZWEI Belege zugleich: den
  // B-Hebesatz UND die Aufteilung des gemeinsamen Aufkommens „A+B“ aus dem
  // Realsteuervergleich des Landes — fehlt einer, zeigt die Werkbank den
  // ehrlichen Kasten von früher statt des Reglers.
  const gewst = hebesatzHeute(daten.hebesaetze?.zeilen, "Gewerbesteuer");
  const grundst = hebesatzHeute(daten.hebesaetze?.zeilen, "Grundsteuer B");
  const gewstBetrag = letzterSteuerbetrag(daten.steuern, "Gewerbesteuer (-umlage)");
  const grundstBetrag = letzterSteuerbetrag(daten.steuern, "Grundsteuer A+B");
  // Die Zeile „sonstige Steuern“ IST die Hundesteuer — der Abgleich mit
  // Jahrbuch 1103 beweist es jahrgangsweise (council/steuertabellen.py).
  const hunde = letzterSteuerbetrag(daten.steuern, "sonstige Steuern");
  const anteilA = useMemo(() => grundsteuerAnteilA(vergleich), [vergleich]);
  const staedte = useMemo(
    () => staedteHebesaetze(vergleich, "hebesatz_gewerbesteuer"), [vergleich]);

  const proPunktGewst = gewstBetrag && gewst ? gewstBetrag.amount / 1e6 / gewst.satz : 0;
  const proPunktGrundst = grundstBetrag && grundst && anteilA != null
    ? (grundstBetrag.amount * (1 - anteilA)) / 1e6 / grundst.satz : null;

  const einwohner = daten.einwohner?.einwohner ?? 0;
  const mehrEinnahmen = Math.round(
    (proPunktGewst * punkte
      + (proPunktGrundst ?? 0) * grundstPunkte
      + (hunde ? (hunde.amount / 1e6) * (hundePct / 100) : 0)) * 10) / 10;
  // Negativ gedrehte Bereiche sparen, aufgestockte kosten — `gespart` darf
  // deshalb negativ werden und heißt dann ehrlich „mehr ausgegeben“.
  const gespart = Math.round(
    basis.freiwillig.reduce((s, f) => s - (f.aus * (aenderung[f.area] ?? 0)) / 100, 0) * 10) / 10;
  const wirkung = mehrEinnahmen + gespart;
  const neuesDefizit = Math.round((basis.defizit - wirkung) * 10) / 10;
  const geschlossen = basis.defizit > 0
    ? Math.max(0, Math.min(100, (wirkung / basis.defizit) * 100)) : 0;
  // Was ginge maximal? Beantwortet die Frage, die jeder als zweites stellt.
  const maxWirkung = Math.round(
    (proPunktGewst * MAX_PUNKTE
      + (proPunktGrundst ?? 0) * MAX_PUNKTE
      + (hunde ? (hunde.amount / 1e6) * (MAX_HUNDE / 100) : 0)
      + basis.freiwillig.reduce((s, f) => s + (f.aus * MAX_KUERZUNG) / 100, 0)) * 10) / 10;

  // Der Rücklagen-Pfad über die Planjahre — und sein Vorgänger als Rückfall:
  // Ohne die Reihe des Gesamtergebnishaushalts bleibt die alte
  // Reichweiten-Division stehen.
  const planjahre = useMemo(
    () => planjahrErgebnisse(daten.ergebnishaushalt), [daten.ergebnishaushalt]);
  const ruecklage = juengsteRuecklage(daten);
  const ruecklageMio = (ruecklage?.state_after_result ?? 0) / 1e6;
  const pfadOhne = planjahre && ruecklageMio > 0
    ? ruecklagenPfad(planjahre.reihe, 0, ruecklageMio) : null;
  const pfadMit = planjahre && ruecklageMio > 0
    ? ruecklagenPfad(planjahre.reihe, wirkung, ruecklageMio) : null;
  const daempfer = useMemo(() => daempferSpanne(daten.steuerkraft), [daten.steuerkraft]);
  const reichweiteVorher = basis.defizit > 0 && ruecklageMio > 0
    ? ruecklageMio / basis.defizit : Infinity;
  const reichweiteNachher = neuesDefizit > 0 && ruecklageMio > 0
    ? ruecklageMio / neuesDefizit : Infinity;

  const lueckeGeaendert = punkte !== 0 || grundstPunkte !== 0 || hundePct !== 0
    || Object.values(aenderung).some((v) => v !== 0);
  // Gestrichene Investitionen — für den Hinweis in der Ergebnis-Karte, WARUM
  // sich das Minus dort nicht bewegt (Tims Befund 26.08.2026: Schalter aus,
  // Zahl unverändert, „zurücksetzen" erscheint — und nichts erklärt es).
  // Gleicher Schlüssel wie in der Invest-Werkbank: code || bezeichnung.
  const investGestrichenMio = useMemo(() => {
    const jahrInv = programm?.jahre.at(-1) ?? null;
    if (jahrInv == null) return 0;
    const summe = (programm?.massnahmen ?? [])
      .filter((z) => z.year === jahrInv && vorhabenAus[z.code || z.label])
      .reduce((s, z) => s + z.grand_total, 0);
    return Math.round((summe / 1e6) * 10) / 10;
  }, [programm, vorhabenAus]);
  const etwasGeaendert = lueckeGeaendert || kredit
    || Object.values(vorhabenAus).some(Boolean);

  const anteilText = (m: number) =>
    basis.defizit > 0 ? `${Math.round((m / basis.defizit) * 100)} % der Lücke` : "";
  const jeEinwohner = (m: number) =>
    einwohner > 0 ? `${eur((m * 1e6) / einwohner)} € je Einwohner*in` : "";

  const zuruecksetzen = () => {
    setPunkte(0); setGrundstPunkte(0); setHundePct(0);
    setAenderung({}); setVorhabenAus({}); setKredit(false);
  };
  const alle = (pct: number) =>
    Object.fromEntries(basis.freiwillig.map((f) => [f.area, pct]));
  const szenarien = [
    { label: "+20 Punkte Hebesatz", punkte: 20, grundst: 0, hunde: 0, pct: 0 },
    { label: "10 % weniger für die Kür", punkte: 0, grundst: 0, hunde: 0, pct: -10 },
    { label: "Alles auf Anschlag", punkte: MAX_PUNKTE,
      grundst: proPunktGrundst != null ? MAX_PUNKTE : 0,
      hunde: hunde ? MAX_HUNDE : 0, pct: -MAX_KUERZUNG },
  ];

  // Die Bestandteile des Ergebnis-Satzes, je nach Vorzeichen benannt —
  // „−2,7 Mio. € mehr eingenommen“ wäre eine Zahl mit falschem Verb. Seit die
  // Regler in beide Richtungen laufen, kann jede Komponente jedes Vorzeichen
  // tragen, auch gemischt (Hebesatz runter, Kultur rauf).
  const satzteile: string[] = [];
  if (mehrEinnahmen > 0) satzteile.push(`${deMio(mehrEinnahmen)} Mio. € mehr eingenommen`);
  if (mehrEinnahmen < 0) satzteile.push(`${deMio(-mehrEinnahmen)} Mio. € weniger eingenommen`);
  if (gespart > 0) satzteile.push(`${deMio(gespart)} Mio. € gespart`);
  if (gespart < 0) satzteile.push(`${deMio(-gespart)} Mio. € mehr ausgegeben`);

  // Zwei Bausteine, die an verschiedenen Stellen gebraucht werden. Bewusst
  // als Funktionen aufgerufen (`{ergebnisKarte(...)}`), nicht als
  // Kind-Komponenten gerendert: Sonst wäre es bei jedem Reglerzug ein neuer
  // Komponententyp — React würde den Teilbaum samt Fokus neu aufbauen.
  const ergebnisKarte = ({ kompakt }: { kompakt?: boolean }) => (
    <div className={cn("rounded-2xl border border-signal/40 bg-card p-4",
      kompakt ? "shadow-[0_6px_16px_-10px_rgba(2,32,71,0.5)]" : "shadow-sm")}>
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
          Dein Haushalt {basis.year}
        </p>
        {etwasGeaendert && (
          <button type="button" onClick={zuruecksetzen}
            className="inline-flex items-center gap-1 text-[11.5px] font-semibold text-primary">
            <RotateCcw className="h-3 w-3" /> zurücksetzen
          </button>
        )}
      </div>

      <div className={cn(kompakt && "flex flex-wrap items-baseline gap-x-3")}>
        <p className={cn("text-[11.5px] text-muted-foreground", kompakt ? "order-2" : "mt-2")}>
          {/* Der Beleg an der Zahl, gegen die alles gerechnet wird: Erträge
              minus Aufwendungen des jüngsten Haushaltsansatzes. */}
          Minus am Jahresende<Beleg q="plan" />
        </p>
        <p className={cn("font-display font-bold leading-tight tabular-nums",
          kompakt ? "text-[24px]" : "text-[26px]")}>
          {neuesDefizit > 0 ? deMio(neuesDefizit) : "0,0"}
          <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
          {lueckeGeaendert && (
            <span className="ml-2 align-middle font-sans text-[13px] text-muted-foreground line-through">
              {deMio(basis.defizit)}
            </span>
          )}
        </p>
      </div>

      {/* Die Lücke als Balken — in BEIDE Richtungen (Tims Befund 26.08.2026:
          „wäre cool, wenn der Balken auch in eine andere Richtung gehen
          könnte"). Netto positiv: die Füllung ist der geschlossene Teil,
          aufgeteilt auf Einnahmen- und Spar-Farbe. Damit die Füllung bei
          gemischten Vorzeichen (Hebesatz hoch, Kultur auch) nie mehr zeigt
          als netto wirkt, werden die positiven Anteile auf die Netto-Wirkung
          skaliert — vorher zeigte der Balken die Brutto-Anteile und
          überzeichnete. Netto negativ: dieselbe Fläche läuft in
          Signal-Orange von links und heißt „so viel kommt zur Lücke DAZU"
          — der Satz darunter beziffert es. */}
      {(() => {
        const posSumme = Math.max(0, mehrEinnahmen) + Math.max(0, gespart);
        const skala = wirkung > 0 && posSumme > 0 ? wirkung / posSumme : 0;
        const anteil = (m: number) =>
          basis.defizit > 0 ? Math.max(0, Math.min(100, (m / basis.defizit) * 100)) : 0;
        return (
          <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-muted">
            {wirkung < 0 ? (
              <span className="h-full transition-[width] duration-200"
                style={{ width: `${anteil(-wirkung)}%`, background: "hsl(var(--signal))" }} />
            ) : (
              <>
                <span className="h-full transition-[width] duration-200"
                  style={{ width: `${anteil(Math.max(0, mehrEinnahmen) * skala)}%`,
                    background: "var(--hh-ein-0)" }} />
                <span className="h-full transition-[width] duration-200"
                  style={{ width: `${anteil(Math.max(0, gespart) * skala)}%`,
                    background: "var(--hh-aus-2)" }} />
              </>
            )}
          </div>
        );
      })()}
      <p className="mt-1.5 text-[12px] leading-relaxed">
        {!lueckeGeaendert ? (
          <span className="text-muted-foreground">
            Noch keine Annahmen verändert — die Regler {kompakt ? "oben" : "links"} füllen diesen Balken.
          </span>
        ) : wirkung > 0 ? (
          <><strong>{Math.round(geschlossen)}&#8239;% der Lücke</strong> geschlossen
          {satzteile.length > 0 && <> — {satzteile.join(", ")}</>}.</>
        ) : wirkung < 0 ? (
          // Auch das ist ein Ergebnis, kein Fehler: Wer Kultur aufstockt oder
          // den Hebesatz senkt, soll den Preis sehen, nicht einen leeren Balken.
          <><strong>Das Minus wächst um {deMio(-wirkung)}&#8239;Mio.&nbsp;€</strong>
          {satzteile.length > 0 && <> — {satzteile.join(", ")}</>}.</>
        ) : (
          <><strong>Unterm Strich ±0</strong>
          {satzteile.length > 0 && <> — {satzteile.join(", ")} gleichen sich aus</>}.</>
        )}
      </p>

      {/* Warum bewegt sich das Minus nicht, obwohl ich gestrichen habe?
          Investitionen wirken auf Kasse und Schuldenpfad, nicht auf diese
          Zahl — ohne den Satz sieht der Schalter kaputt aus. */}
      {investGestrichenMio > 0 && (
        <p className="mt-2 rounded-lg bg-muted/50 p-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">
            {deMio(investGestrichenMio)}&#8239;Mio.&nbsp;€ Investitionen gestrichen
          </strong>{" "}
          — das schont Kasse und Schuldenpfad (Werkbank „Investieren"), aber dieses
          Minus fast nicht: Im Jahresergebnis stehen von Investitionen nur die
          Abschreibungen. Deshalb ändert sich die Zahl oben nicht.
        </p>
      )}

      {/* Die Dämpfer-Spanne: weiterhin NICHT verrechnet, aber sichtbar —
          beziffert aus den echten Ausgleichsjahren, kein fester Faktor. */}
      {!kompakt && mehrEinnahmen > 0 && daempfer && (
        <p className="mt-2 rounded-lg bg-muted/50 p-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Nach Finanzausgleich:</strong> Von{" "}
          {deMio(mehrEinnahmen)}&#8239;Mio.&nbsp;€ mehr Steuerkraft blieben erfahrungsgemäß{" "}
          <span className="tabular-nums">
            {deMio(mehrEinnahmen * daempfer.verbleibVon)} bis {deMio(mehrEinnahmen * daempfer.verbleibBis)}
          </span>&#8239;Mio.&nbsp;€ übrig <Beleg q="steuerkraft" /> — die Spanne aus{" "}
          {daempfer.paare} Ausgleichsjahren. Verrechnet wird sie nicht: Auch der Landestopf
          schwankt, die Richtung kann kippen.
        </p>
      )}

      {!kompakt && rueckhalt()}
    </div>
  );

  /** Rücklage und Obergrenze — auf dem Desktop Teil der Ergebnis-Karte, auf
   *  Mobil eine eigene Karte unter den Reglern (die klebende oben bleibt so
   *  flach genug, um nicht den halben Schirm zu belegen). */
  const rueckhalt = ({ trenner = true }: { trenner?: boolean } = {}) => (
    <>
      <div className={trenner ? "mt-3 border-t border-border/60 pt-3" : "mt-2"}>
        {pfadOhne && pfadMit ? (
          <>
            <p className="text-[11.5px] text-muted-foreground">
              {kredit ? "Rücklage bliebe stehen" : "Rücklage kippt rechnerisch"}
            </p>
            {kredit ? (
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                Liefe das Minus über Kredite, bliebe die Rücklage stehen — dafür wüchse
                der Schuldenstand Jahr für Jahr, und Zinsen kämen ins Minus dazu. Die
                Zahlen dahinter stehen in der Werkbank „Investitionen &amp; Finanzierung“.
              </p>
            ) : (
              <>
                <p className="font-display text-[20px] font-bold tabular-nums">
                  {pfadMit.kippjahr != null ? (
                    <>
                      {pfadMit.kippjahr}
                      {/* Der Durchgestrichene nur, wenn sich wirklich etwas
                          verschiebt — „2028 statt 2028“ wäre Rauschen. */}
                      {pfadOhne.kippjahr != null && pfadOhne.kippjahr !== pfadMit.kippjahr && (
                        <span className="ml-2 align-middle font-sans text-[13px] text-muted-foreground line-through">
                          {pfadOhne.kippjahr}
                        </span>
                      )}
                    </>
                  ) : (
                    <>nicht bis {pfadMit.letztesPlanjahr}</>
                  )}
                </p>
                <RuecklagenPfadGrafik ohne={pfadOhne} mit={pfadMit} />
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10.5px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-[2px] w-3.5 rounded-full" style={{ background: "var(--hh-aus-4)" }} />
                    ohne Änderung
                  </span>
                  {lueckeGeaendert && (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="h-[2.5px] w-3.5 rounded-full bg-primary" />
                      dein Szenario
                    </span>
                  )}
                </p>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                  {deMio(ruecklageMio)}&#8239;Mio.&nbsp;€ Rücklage <Beleg q="ruecklage" /> gegen die
                  Jahresergebnisse der Planjahre <Beleg q="ergebnishaushalt" /> — Entwurf der
                  Verwaltung, Finanzplanung nach §&nbsp;8 NKomVG, deine Wirkung konstant
                  fortgeschrieben. Hinter {pfadMit.letztesPlanjahr} liegen keine Planzahlen.
                  Unsere Rechnung, keine Prognose der Stadt.
                </p>
              </>
            )}
          </>
        ) : ruecklageMio > 0 ? (
          <>
            <p className="text-[11.5px] text-muted-foreground">Rücklage reicht rechnerisch</p>
            <p className="font-display text-[20px] font-bold tabular-nums">
              {reichweiteNachher === Infinity
                ? "unbegrenzt"
                : `${reichweiteNachher.toLocaleString("de-DE", { maximumFractionDigits: 1 })} Jahre`}
              {lueckeGeaendert && reichweiteVorher !== Infinity && (
                <span className="ml-2 align-middle font-sans text-[13px] text-muted-foreground line-through">
                  {reichweiteVorher.toLocaleString("de-DE", { maximumFractionDigits: 1 })}
                </span>
              )}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              {deMio(ruecklageMio)}&#8239;Mio.&nbsp;€ Rücklage <Beleg q="ruecklage" /> geteilt durch das Minus —
              unsere Rechnung, keine Prognose der Stadt.
              {/* Der Schlüssel `ergebnishaushalt` gehört zum Pfad oben; im
                  Rückfall ohne die Reihe bliebe er stumm — deshalb hängt er
                  hier an der Auskunft, WARUM nur die einfache Division steht. */}
              {" "}Für den Rücklagen-Pfad fehlt gerade die Planjahres-Reihe des
              Gesamtergebnishaushalts <Beleg q="ergebnishaushalt" />.
            </p>
          </>
        ) : (
          <p className="text-[11.5px] leading-relaxed text-muted-foreground">
            Für die Rücklagen-Rechnung liegt noch kein geprüfter Bilanzstand vor.
          </p>
        )}
      </div>
      {maxWirkung < basis.defizit && (
        <p className="mt-3 rounded-lg bg-muted/50 p-2.5 text-[12px] leading-relaxed">
          Mit den hier abgebildeten Änderungen lassen sich höchstens {deMio(maxWirkung)}&#8239;Mio.&nbsp;€
          ausgleichen. Selbst bei den maximalen Einstellungen bliebe ein Minus von{" "}
          {deMio(Math.round((basis.defizit - maxWirkung) * 10) / 10)}&#8239;Mio.&nbsp;€.
          Weitere Maßnahmen wären notwendig.
        </p>
      )}
    </>
  );

  return (
    <div className="@container/labor flex flex-col gap-3">
      {/* Die drei Werkbänke — auf schmalen Schirmen eine wischbare Zeile,
          mit Platz ein Dreierraster. Die Schwelle hängt an der
          CONTAINER-Breite, nicht am Fenster (Designsprache §4). */}
      <div className="flex gap-2 overflow-x-auto pb-0.5 @3xl/labor:grid @3xl/labor:grid-cols-3 @3xl/labor:overflow-visible @3xl/labor:pb-0">
        {WERKBAENKE.map((w) => (
          <button key={w.id} type="button" aria-pressed={werkbank === w.id}
            onClick={() => setWerkbank(w.id)}
            className={cn(
              "min-w-[190px] shrink-0 rounded-2xl border p-3 text-left transition-colors @3xl/labor:min-w-0",
              werkbank === w.id
                ? "border-primary/40 bg-primary/5"
                : "border-border bg-card hover:border-primary/40",
            )}>
            <span className={cn("font-mono text-[9.5px] font-medium uppercase tracking-[0.11em]",
              werkbank === w.id ? "text-primary" : "text-muted-foreground")}>
              Werkbank {w.nr}{werkbank === w.id && " · aktiv"}
            </span>
            <span className="mt-0.5 block font-display text-[14.5px] font-bold leading-snug text-foreground">
              {w.titel}
            </span>
            <span className="mt-0.5 block text-[11px] text-muted-foreground">{w.zielgroesse}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
          Zum Ausprobieren
        </span>
        {szenarien.map((s) => {
          const aktiv = punkte === s.punkte && grundstPunkte === s.grundst
            && hundePct === s.hunde
            && basis.freiwillig.every((f) => (aenderung[f.area] ?? 0) === s.pct);
          return (
            <button key={s.label} type="button"
              onClick={() => {
                setPunkte(s.punkte); setGrundstPunkte(s.grundst);
                setHundePct(s.hunde); setAenderung(alle(s.pct));
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
                aktiv
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-card text-foreground/80 hover:border-primary/40",
              )}>
              {s.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-3 lg:grid lg:grid-cols-[1fr_330px] lg:items-start">
        {/* Das aktive Panel. Der Zustand ALLER Werkbänke liegt oben — ein
            Wechsel montiert das Panel ab, verliert aber nichts. */}
        <div className="flex flex-col gap-3">
          {werkbank === "einnahmen" && (
            <EinnahmenWerkbank
              basisJahr={basis.year}
              punkte={punkte} setPunkte={setPunkte}
              gewst={gewst} proPunktGewst={proPunktGewst}
              gewstBasisJahr={gewstBetrag?.year ?? null}
              grundstPunkte={grundstPunkte} setGrundstPunkte={setGrundstPunkte}
              grundst={grundst} proPunktGrundst={proPunktGrundst} anteilA={anteilA}
              hundePct={hundePct} setHundePct={setHundePct} hunde={hunde}
              staedte={staedte}
              historie={(daten.hebesaetze?.zeilen ?? []).filter((z) => z.art === "Gewerbesteuer")}
              gebuehren={daten.gebuehren}
              maxPunkte={MAX_PUNKTE}
              jeEinwohner={jeEinwohner} anteilText={anteilText}
            />
          )}
          {werkbank === "ausgaben" && (
            <AusgabenWerkbank
              freiwillig={basis.freiwillig}
              produkte={produkte} produktJahr={produktJahr} basisJahr={basis.year}
              aenderung={aenderung}
              setAenderung={(area, pct) => setAenderung((k) => ({ ...k, [area]: pct }))}
              maxProzent={MAX_KUERZUNG}
              jeEinwohner={jeEinwohner} anteilText={anteilText}
            />
          )}
          {werkbank === "invest" && (
            <InvestWerkbank
              programm={programm} schulden={schulden}
              satzung={daten.haushaltssatzung}
              vorhabenAus={vorhabenAus}
              toggleVorhaben={(s) => setVorhabenAus((v) => ({ ...v, [s]: !v[s] }))}
              kredit={kredit} setKredit={setKredit}
              neuesDefizit={neuesDefizit}
            />
          )}

          {/* Mobil klebt das Ergebnis am UNTEREN Rand, über der Tab-Leiste
              (H4-16): Das Ergebnis folgt der Bewegung — der Daumen ist unten,
              der Regler in der Mitte, die Wirkung direkt darunter, live bei
              jedem Zug. Als LETZTES Kind der Regler-Spalte klebt sie nur,
              solange es etwas zu drehen gibt, und legt sich danach an ihren
              Platz — dieselbe Mechanik wie die Ableseleiste des Baukastens
              (`.gb-ablese-leiste`); die Andockkante ist `TABLEISTE_HOEHE`,
              nie eine eigene Zahl (Designsprache § 5). z-30: über der eigenen
              Spalte, unter Kopf- und Tab-Leiste. */}
          <div
            className="sticky z-30 lg:hidden"
            style={{ bottom: `calc(${TABLEISTE_HOEHE} + 0.5rem)` } as CSSProperties}
          >
            {ergebnisKarte({ kompakt: true })}
          </div>
        </div>

        {/* Die Ergebnis-Spalte (Desktop) bzw. der Rückhalt unter den Reglern
            (Mobil). Hier steht NUR, was sich beim Drehen mitbewegt — der
            Rest ist Nachschlagestoff und steht unter dem Ganzen. */}
        <div className="flex flex-col gap-3 lg:sticky lg:top-4 lg:self-start">
          <div className="hidden lg:block">{ergebnisKarte({})}</div>
          {/* Auf Mobil trägt die klebende Karte oben die Zahl — hier steht nur,
              was sie aushält, ohne das Minus ein zweites Mal zu wiederholen. */}
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm lg:hidden">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Was die Rücklage aushält
            </p>
            {rueckhalt({ trenner: false })}
          </div>
        </div>
      </div>

      {/* DIE ZWEI KONTEXT-KARTEN über die volle Breite: In die Rail gehört,
          was sich bei jedem Reglerzug mitbewegt — diese beiden stehen fest
          (Messwerte und Vorgeschichte: Git-Historie dieser Datei, 17.08.).
          Zwei Spalten, weil sie parallele Einwände sind — man liest sie
          nebeneinander, nicht nacheinander. Die Schwelle hängt am CONTAINER
          (`@container/labor`), nicht an der Fensterbreite (Designsprache §4). */}
      <div className="grid gap-3 @3xl/labor:grid-cols-2 @3xl/labor:items-start">
        <PlanIst daten={daten} />

        {/* Immer sichtbar, nie ausklappbar. */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was dagegen rechnet
          </p>
          <ul className="mt-2.5 max-w-[76ch] space-y-2.5 text-[12px] leading-relaxed text-foreground/85">
            <li>
              <strong>Die Umlage.</strong> Von der Gewerbesteuer geht ein Anteil an Bund und Land.
              Wie viel exact, führt der offene Datensatz nicht getrennt aus — die Zahl oben ist
              bereits ein Netto-Wert nach Umlage, ein zusätzlicher Punkt bringt aber ebenfalls
              weniger als brutto.
            </li>
            <li>
              <strong>Das Land rechnet gegen.</strong> Höhere eigene Steuerkraft senkt die
              Schlüsselzuweisungen — wie stark, zeigt die Spanne an der Ergebnis-Karte.
              {basis.kraft.length === 2 && (
                <>
                  {" "}Zuletzt: {basis.kraft[0].year} auf {basis.kraft[1].year} stieg die
                  Steuerkraft um {deMio(((basis.kraft[1].messzahl ?? 0) - (basis.kraft[0].messzahl ?? 0)) / 1e6)}
                  &#8239;Mio.&nbsp;€ und die Zuweisung um{" "}
                  {deMio(((basis.kraft[1].zuweisungen ?? 0) - (basis.kraft[0].zuweisungen ?? 0)) / 1e6)}
                  {/* Keine feste Aussage über dritte Jahrgänge, die basis.kraft
                      gar nicht führt — was immer gilt, ist die Mechanik
                      (Vorgeschichte: Git-Historie dieser Datei). */}
                  &#8239;Mio.&nbsp;€ — die Richtung kann von Jahr zu Jahr wechseln, weil auch der
                  Landestopf schwankt, aus dem das Land verteilt.
                </>
              )}
            </li>
            <li>
              <strong>Ausgaben steigen weiter.</strong> Tarifabschlüsse, Preise und wachsende
              Pflichtaufgaben treiben den Haushalt Jahr für Jahr — unser Modell hält sie fest.
            </li>
          </ul>
          <p className="mt-2.5 max-w-[76ch] border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
            Das Ergebnis oben ist deshalb eine <strong>vereinfachte Obergrenze</strong>. Es
            berücksichtigt diese Folgewirkungen nicht vollständig.
          </p>
        </div>
      </div>
    </div>
  );
}
