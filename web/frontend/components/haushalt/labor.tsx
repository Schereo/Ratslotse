"use client";

// Haushalts-Labor (Design H-19, zweite Runde nach Tims Befund 16.08.:
// „random Slider mit irgendwelchen Zahlen ohne Referenz").
//
// Die Rechnung war schon vorher ehrlich, aber bezugslos: Man zog an einem
// Regler und eine Zahl änderte sich — ohne Maßstab, ohne Gefühl dafür, ob das
// viel ist. Diese Runde ergänzt vier Bezugsgrößen, alle aus echten Daten:
//
//  1. **Die Lücke als Balken.** Jede Bewegung füllt sichtbar einen Anteil des
//     Minus — „7 % geschlossen" sagt mehr als „66,0 statt 71,1".
//  2. **Wirkung je Regler**, in drei Einheiten: Millionen, Euro je Einwohner
//     und Anteil an der Lücke. Beim Hebesatz zusätzlich, was ein Betrieb mit
//     100.000 € Gewerbeertrag zahlt (Messzahl 3,5 % ist Bundesrecht).
//  3. **Was für den Betrag sonst im Haushalt steht** — übersetzt in echte
//     Produkte aus den Teilhaushalts-Plänen (#500): „so viel wie die gesamte
//     Kulturgutvermittlung".
//  4. **Der Plan gegen den Jahresabschluss.** In allen fünf vorliegenden
//     Jahren fiel das Ergebnis besser aus als geplant — ohne diesen Anker
//     wirkt das Minus wie eine feststehende Tatsache.
//
// UNVERÄNDERTE REGELN aus Runde 1:
//  1. Nur Regler, für die es echte Zahlen gibt (keine Grundsteuer — das
//     Portal führt A und B in einer Spalte).
//  2. „Was dagegen rechnet" ist immer sichtbar, nicht ausklappbar.
//  3. Der Finanzausgleichs-Dämpfer wird NICHT als fester Faktor verrechnet.
//
// NEUE REGEL dieser Runde: Die Produktzahlen sind ein **Vergleich**, keine
// Rechengrundlage. Sie stammen aus dem jüngsten auslesbaren Teilhaushaltsplan
// (2023), die Simulation rechnet mit dem aktuellen Planjahr — beides zu
// vermischen wäre eine Zahl, die es nirgends gibt.

import { useMemo, useState } from "react";
import { RotateCcw } from "lucide-react";
import {
  HaushaltDaten, PLAN_ART_LABEL, Produkt, RUECKLAGE_MIO, bereiche, deMio,
  jahreSortiert, mio, naechstesProdukt, planGegenIst, summe,
} from "@/lib/haushalt";
import { PFLICHT_ZUORDNUNG } from "@/lib/haushalt-pflicht";
import { Beleg } from "@/components/haushalt/quelle";
import { Regler } from "@/components/haushalt/regler";
import { cn } from "@/lib/utils";

const GEWST_HEBESATZ = 439;
/** Steuermesszahl nach § 11 GewStG — bundesweit gleich, nicht unsere Annahme. */
const MESSZAHL = 0.035;
/** Beispielbetrieb wie im Steuer-Steckbrief — dieselbe Zahl an beiden Stellen. */
const BEISPIEL_GEWINN = 100_000;
const MAX_KUERZUNG = 30;
const MAX_PUNKTE = 50;

function eur(v: number): string {
  return v.toLocaleString("de-DE", { maximumFractionDigits: 0 });
}

/** Geplant gegen tatsächlich (Jahresabschlüsse) — der Maßstab dafür, wie
 *  belastbar die Zahl ist, gegen die hier angerechnet wird. */
function PlanIst({ daten }: { daten: HaushaltDaten }) {
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
          <div key={r.jahr} className="flex items-center gap-2.5">
            <span className="w-9 shrink-0 font-mono text-[11px] text-muted-foreground">{r.jahr}</span>
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
                {r.planArt !== "ansatz" ? "*" : " "}
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
        einpreist. Für {reihe[reihe.length - 1].jahr + 1} und später liegt noch kein Abschluss vor.
        {abweichenderBezug.length > 0 && (
          <>
            {" "}* In {abweichenderBezug.map((r) => r.jahr).join(" und ")} vergleicht der
            Abschluss nicht mit dem ursprünglichen Ansatz, sondern mit dem fortgeschriebenen
            Plan ({[...new Set(abweichenderBezug.map((r) => PLAN_ART_LABEL[r.planArt]))].join(", ")}
            ) — so rechnet die Stadt dort selbst.
          </>
        )}
      </p>
    </div>
  );
}

export function Labor({ daten, produkte, produktJahr }: {
  daten: HaushaltDaten;
  produkte: Produkt[];
  produktJahr: number | null;
}) {
  const [punkte, setPunkte] = useState(0);
  const [kuerzung, setKuerzung] = useState<Record<string, number>>({});

  const basis = useMemo(() => {
    const jahre = jahreSortiert(daten);
    const jahr = jahre[jahre.length - 1];
    const zeilen = daten.jahre[String(jahr)] ?? [];
    const g = summe(zeilen);
    const defizit = g?.ertraege != null && g?.aufwendungen != null
      ? mio(g.aufwendungen - g.ertraege) ?? 0 : 0;
    const gewst = daten.steuern
      .filter((s) => s.art === "Gewerbesteuer (-umlage)" && s.betrag)
      .sort((a, b) => a.jahr - b.jahr).at(-1);
    const freiwillig = bereiche(zeilen)
      .filter((z) => PFLICHT_ZUORDNUNG[z.bereich]?.stufe === "freiwillig")
      .map((z) => ({ bereich: z.bereich, aus: mio(z.aufwendungen) ?? 0 }))
      .sort((a, b) => b.aus - a.aus);
    const kraft = daten.steuerkraft.filter((k) => k.messzahl != null && k.zuweisungen != null).slice(-2);
    return { jahr, defizit, gewst, freiwillig, kraft };
  }, [daten]);

  const einwohner = daten.einwohner?.einwohner ?? 0;
  const proPunkt = basis.gewst ? (basis.gewst.betrag as number) / 1e6 / GEWST_HEBESATZ : 0;
  const mehrEinnahmen = Math.round(proPunkt * punkte * 10) / 10;
  const gespart = Math.round(
    basis.freiwillig.reduce((s, f) => s + (f.aus * (kuerzung[f.bereich] ?? 0)) / 100, 0) * 10) / 10;
  const wirkung = mehrEinnahmen + gespart;
  const neuesDefizit = Math.round((basis.defizit - wirkung) * 10) / 10;
  const geschlossen = basis.defizit > 0
    ? Math.max(0, Math.min(100, (wirkung / basis.defizit) * 100)) : 0;
  // Was ginge maximal? Beantwortet die Frage, die jeder als zweites stellt.
  const maxWirkung = Math.round(
    (proPunkt * MAX_PUNKTE
      + basis.freiwillig.reduce((s, f) => s + (f.aus * MAX_KUERZUNG) / 100, 0)) * 10) / 10;
  const reichweiteVorher = basis.defizit > 0 ? RUECKLAGE_MIO / basis.defizit : Infinity;
  const reichweiteNachher = neuesDefizit > 0 ? RUECKLAGE_MIO / neuesDefizit : Infinity;
  const etwasGeaendert = punkte !== 0 || Object.values(kuerzung).some((v) => v > 0);

  const anteilText = (m: number) =>
    basis.defizit > 0 ? `${Math.round((m / basis.defizit) * 100)} % der Lücke` : "";
  const jeEinwohner = (m: number) =>
    einwohner > 0 ? `${eur((m * 1e6) / einwohner)} € je Einwohner` : "";

  const zuruecksetzen = () => { setPunkte(0); setKuerzung({}); };
  const alle = (pct: number) =>
    Object.fromEntries(basis.freiwillig.map((f) => [f.bereich, pct]));
  const szenarien = [
    { label: "+20 Punkte Hebesatz", punkte: 20, pct: 0 },
    { label: "10 % weniger für die Kür", punkte: 0, pct: 10 },
    { label: "Alles auf Anschlag", punkte: MAX_PUNKTE, pct: MAX_KUERZUNG },
  ];

  // Zwei Bausteine, die an verschiedenen Stellen gebraucht werden. Bewusst
  // als Funktionen aufgerufen (`{ergebnisKarte(...)}`), nicht als
  // Kind-Komponenten gerendert: Sonst wäre es bei jedem Reglerzug ein neuer
  // Komponententyp — React würde den Teilbaum samt Fokus neu aufbauen.
  const ergebnisKarte = ({ kompakt }: { kompakt?: boolean }) => (
    <div className={cn("rounded-2xl border border-signal/40 bg-card p-4",
      kompakt ? "shadow-[0_6px_16px_-10px_rgba(2,32,71,0.5)]" : "shadow-sm")}>
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
          Dein Haushalt {basis.jahr}
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
          Minus am Jahresende
        </p>
        <p className={cn("font-display font-bold leading-tight tabular-nums",
          kompakt ? "text-[24px]" : "text-[26px]")}>
          {neuesDefizit > 0 ? deMio(neuesDefizit) : "0,0"}
          <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
          {etwasGeaendert && (
            <span className="ml-2 align-middle font-sans text-[13px] text-muted-foreground line-through">
              {deMio(basis.defizit)}
            </span>
          )}
        </p>
      </div>

      {/* Die Lücke als Balken: was du geschlossen hast, was bleibt. */}
      <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-muted">
        <span className="h-full transition-[width] duration-200"
          style={{ width: `${basis.defizit > 0 ? (mehrEinnahmen / basis.defizit) * 100 : 0}%`,
            background: "var(--hh-ein-0)" }} />
        <span className="h-full transition-[width] duration-200"
          style={{ width: `${basis.defizit > 0 ? (gespart / basis.defizit) * 100 : 0}%`,
            background: "var(--hh-aus-2)" }} />
      </div>
      <p className="mt-1.5 text-[12px] leading-relaxed">
        {etwasGeaendert ? (
          <>
            <strong>{Math.round(geschlossen)}&#8239;% der Lücke</strong> geschlossen
            {mehrEinnahmen !== 0 && <> — {deMio(mehrEinnahmen)}&#8239;Mio. mehr eingenommen</>}
            {mehrEinnahmen !== 0 && gespart > 0 && ","}
            {gespart > 0 && <> {mehrEinnahmen === 0 ? "— " : ""}{deMio(gespart)}&#8239;Mio. gespart</>}.
          </>
        ) : (
          <span className="text-muted-foreground">
            Noch nichts gedreht — die Regler {kompakt ? "unten" : "links"} füllen diesen Balken.
          </span>
        )}
      </p>

      {!kompakt && rueckhalt()}
    </div>
  );

  /** Rücklage und Obergrenze — auf dem Desktop Teil der Ergebnis-Karte, auf
   *  Mobil eine eigene Karte unter den Reglern (die klebende oben bleibt so
   *  flach genug, um nicht den halben Schirm zu belegen). */
  const rueckhalt = ({ trenner = true }: { trenner?: boolean } = {}) => (
    <>
      <div className={trenner ? "mt-3 border-t border-border/60 pt-3" : "mt-2"}>
        <p className="text-[11.5px] text-muted-foreground">Rücklage reicht rechnerisch</p>
        <p className="font-display text-[20px] font-bold tabular-nums">
          {reichweiteNachher === Infinity
            ? "unbegrenzt"
            : `${reichweiteNachher.toLocaleString("de-DE", { maximumFractionDigits: 1 })} Jahre`}
          {etwasGeaendert && reichweiteVorher !== Infinity && (
            <span className="ml-2 align-middle font-sans text-[13px] text-muted-foreground line-through">
              {reichweiteVorher.toLocaleString("de-DE", { maximumFractionDigits: 1 })}
            </span>
          )}
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          {RUECKLAGE_MIO}&#8239;Mio. Rücklage <Beleg q="ruecklage" /> geteilt durch das Minus —
          unsere Rechnung, keine Prognose der Stadt.
        </p>
      </div>
      {maxWirkung < basis.defizit && (
        <p className="mt-3 rounded-lg bg-muted/50 p-2.5 text-[12px] leading-relaxed">
          Mehr als {deMio(maxWirkung)}&#8239;Mio. geben diese Regler nicht her — auch mit allen am
          Anschlag blieben {deMio(Math.round((basis.defizit - maxWirkung) * 10) / 10)}&#8239;Mio.&nbsp;€
          Minus. Ein ausgeglichener Haushalt braucht mehr als diese zwei Stellschrauben.
        </p>
      )}
    </>
  );

  return (
    <div className="flex flex-col gap-3 lg:grid lg:grid-cols-[1fr_330px]">
      {/* Mobil klebt die Kurzfassung über den Reglern: Sonst dreht man an
          einem Regler und sieht die Wirkung erst nach dem Scrollen. */}
      {/* Regler */}
      <div className="flex flex-col gap-3">
        {/* Mobil klebt die Kurzfassung über den Reglern: Sonst dreht man an
            einem Regler und sieht die Wirkung erst nach dem Scrollen. Sie
            steht INNERHALB dieser Spalte — so klebt sie nur, solange es etwas
            zu drehen gibt, und gibt die Kontext-Karten darunter wieder frei.
            65 px = Höhe der mobilen Kopfzeile (dieselbe Marke wie in der
            Gründlichen Recherche). */}
        <div className="sticky top-[65px] z-[var(--ebene-schwebend)] -mx-1 bg-background/85 px-1 py-1 backdrop-blur lg:hidden">
          {ergebnisKarte({ kompakt: true })}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
            Zum Ausprobieren
          </span>
          {szenarien.map((s) => {
            const aktiv = punkte === s.punkte
              && basis.freiwillig.every((f) => (kuerzung[f.bereich] ?? 0) === s.pct);
            return (
              <button key={s.label} type="button"
                onClick={() => { setPunkte(s.punkte); setKuerzung(alle(s.pct)); }}
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

        {/* Einnahmen drehen */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Einnahmen drehen
          </p>
          <div className="mt-3">
            <Regler
              id="gewst"
              label="Gewerbesteuer-Hebesatz"
              wert={punkte} min={-MAX_PUNKTE} max={MAX_PUNKTE} step={5}
              onChange={setPunkte}
              geaendert={punkte !== 0}
              ist={{ wert: 0, label: `heute ${GEWST_HEBESATZ} %` }}
              marken={{ min: `${GEWST_HEBESATZ - MAX_PUNKTE} %`, max: `${GEWST_HEBESATZ + MAX_PUNKTE} %` }}
              anzeige={
                punkte === 0
                  ? <span className="text-muted-foreground">{GEWST_HEBESATZ}&nbsp;%</span>
                  : <strong className="text-signal">
                      {GEWST_HEBESATZ + punkte}&nbsp;% ({punkte > 0 ? "+" : ""}{punkte})
                    </strong>
              }
              wirkung={
                punkte === 0 ? (
                  <>Ein Punkt brachte {basis.gewst?.jahr} überschlagen {deMio(proPunkt)}&#8239;Mio.&nbsp;€{" "}
                  <Beleg q="steuern" /> — bei unveränderten Gewinnen.</>
                ) : (
                  <>
                    <strong className="text-foreground">
                      {mehrEinnahmen > 0 ? "+" : ""}{deMio(mehrEinnahmen)}&#8239;Mio.&nbsp;€
                    </strong>{" "}
                    · {jeEinwohner(Math.abs(mehrEinnahmen))} · {anteilText(Math.abs(mehrEinnahmen))}
                    {punkte < 0 && " zusätzlich"}.
                    <br />
                    Ein Betrieb mit {eur(BEISPIEL_GEWINN)}&nbsp;€ Gewerbeertrag zahlte statt{" "}
                    {eur((BEISPIEL_GEWINN * MESSZAHL * GEWST_HEBESATZ) / 100)}&nbsp;€ dann{" "}
                    <strong>{eur((BEISPIEL_GEWINN * MESSZAHL * (GEWST_HEBESATZ + punkte)) / 100)}&nbsp;€</strong>{" "}
                    im Jahr — Messzahl 3,5&nbsp;% nach Bundesrecht, ohne Freibetrag.
                  </>
                )
              }
            />
          </div>
          <div className="mt-4 rounded-xl border border-dashed border-border p-3">
            <p className="text-[12.5px] font-semibold">Grundsteuer B</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
              Hier fehlt uns der Betrag je Hebesatzpunkt: Der offene Datensatz führt Grundsteuer A
              und B in einer Spalte zusammen. Wir schätzen ihn nicht — sobald wir die Aufteilung
              haben, kommt der Regler dazu.
            </p>
          </div>
        </div>

        {/* Freiwillige Leistungen */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Freiwillige Leistungen kürzen
          </p>
          <div className="mt-3 flex flex-col gap-4">
            {basis.freiwillig.map((f) => {
              const pct = kuerzung[f.bereich] ?? 0;
              const betrag = Math.round(f.aus * pct) / 100;
              const drin = produkte
                .filter((p) => p.thh_name === f.bereich && p.ergebnis != null && p.ergebnis < 0)
                .slice(0, 3);
              const vergleich = naechstesProdukt(produkte, betrag, f.bereich);
              return (
                <Regler
                  key={f.bereich}
                  id={f.bereich}
                  label={f.bereich}
                  wert={pct} min={0} max={MAX_KUERZUNG} step={5}
                  onChange={(v) => setKuerzung((k) => ({ ...k, [f.bereich]: v }))}
                  geaendert={pct > 0}
                  ist={{ wert: 0, label: "heute" }}
                  marken={{ min: "", max: `−${MAX_KUERZUNG} %` }}
                  anzeige={
                    pct === 0
                      ? <span className="text-muted-foreground">{deMio(f.aus)}&nbsp;Mio.</span>
                      : <>
                          <span className="text-muted-foreground line-through">{deMio(f.aus)}</span>
                          <strong className="ml-2 text-signal">
                            {deMio(f.aus - betrag)} (−{pct}&nbsp;%)
                          </strong>
                        </>
                  }
                  wirkung={
                    pct === 0 ? (
                      drin.length > 0 ? (
                        <>Darin stecken u.&nbsp;a.{" "}
                        {drin.map((p, i) => (
                          <span key={p.produkt_nr}>
                            {i > 0 && ", "}
                            {p.produkt_name} ({deMio(-(p.ergebnis as number) / 1e6)}&#8239;Mio.)
                          </span>
                        ))}.</>
                      ) : (
                        <>{deMio(f.aus)}&#8239;Mio.&nbsp;€ Aufwand im Plan {basis.jahr}.</>
                      )
                    ) : (
                      <>
                        <strong>{deMio(betrag)}&#8239;Mio.&nbsp;€ weniger</strong> ·{" "}
                        {jeEinwohner(betrag)} · {anteilText(betrag)}.
                        {vergleich && (
                          <> Ungefähr so viel, wie <strong>{vergleich.produkt_name}</strong> im
                          ganzen Jahr kostet.</>
                        )}
                      </>
                    )
                  }
                />
              );
            })}
          </div>
          <p className="mt-4 text-[11.5px] leading-relaxed text-muted-foreground">
            Nur ganze Teilhaushalte, nur prozentual: Welche Einrichtung es träfe, entscheidet kein
            Regler — und ein Beschluss wäre das ohnehin nicht.
            {produktJahr && (
              <> Die einzelnen Aufgaben daneben stammen aus dem Teilhaushaltsplan {produktJahr}{" "}
              <Beleg q="teilhaushalt" /> — zum Einordnen der Größenordnung, nicht zum Mitrechnen.</>
            )}
          </p>
        </div>
      </div>

      {/* Spalte rechts (Desktop) bzw. Kontext unter den Reglern (Mobil) */}
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

        <PlanIst daten={daten} />

        {/* Immer sichtbar, nie ausklappbar. */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was dagegen rechnet
          </p>
          <ul className="mt-2.5 space-y-2.5 text-[12px] leading-relaxed text-foreground/85">
            <li>
              <strong>Die Umlage.</strong> Von der Gewerbesteuer geht ein Anteil an Bund und Land.
              Wie viel genau, führt der offene Datensatz nicht getrennt aus — die Zahl oben ist
              bereits ein Netto-Wert nach Umlage, ein zusätzlicher Punkt bringt aber ebenfalls
              weniger als brutto.
            </li>
            <li>
              <strong>Das Land rechnet gegen.</strong> Höhere eigene Steuerkraft senkt die
              Schlüsselzuweisungen. <Beleg q="steuerkraft" />
              {basis.kraft.length === 2 && (
                <>
                  {" "}Wie stark, schwankt: {basis.kraft[0].jahr} auf {basis.kraft[1].jahr} stieg die
                  Steuerkraft um {deMio(((basis.kraft[1].messzahl ?? 0) - (basis.kraft[0].messzahl ?? 0)) / 1e6)}
                  &#8239;Mio. und die Zuweisung um{" "}
                  {deMio(((basis.kraft[1].zuweisungen ?? 0) - (basis.kraft[0].zuweisungen ?? 0)) / 1e6)}
                  &#8239;Mio. — im Jahr davor sank sie deutlich, weil auch der Landestopf schwankt.
                </>
              )}
            </li>
            <li>
              <strong>Ausgaben steigen weiter.</strong> Tarifabschlüsse, Preise und wachsende
              Pflichtaufgaben treiben den Haushalt Jahr für Jahr — unser Modell hält sie fest.
            </li>
          </ul>
          <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
            Deshalb ist das Ergebnis oben eine <strong>Obergrenze</strong>: In Wirklichkeit bliebe
            weniger übrig, als hier steht.
          </p>
        </div>
      </div>
    </div>
  );
}
