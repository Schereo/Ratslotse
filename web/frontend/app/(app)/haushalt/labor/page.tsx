"use client";

// /haushalt/labor — das Haushalts-Labor (Design H-19, Empfehlung: freies
// Panel, Ergebnis klebt). Zum Ausprobieren, nicht zum Beschließen.
//
// EHRLICHKEIT IST HIER DIE HAUPTSACHE. Drei Regeln, die der Entwurf setzt und
// die hier technisch durchgehalten werden:
//  1. Nur Regler, für die es echte Zahlen gibt. Für die Grundsteuer fehlt der
//     Betrag je Punkt (das Portal führt A und B in einer Spalte) — also kein
//     Regler, sondern ein sichtbares „fehlt uns noch".
//  2. „Was dagegen rechnet" ist immer sichtbar, nicht ausklappbar.
//  3. Der Finanzausgleichs-Dämpfer wird NICHT als fester Faktor verrechnet.
//     Der Entwurf schlug „34 Cent je Euro" vor (aus 2023→2024). Der Blick auf
//     alle Jahre zeigt: 2024→2025 stiegen Steuerkraft UND Zuweisungen. Der
//     Effekt ist systematisch real, seine Höhe hängt aber am Landestopf. Wir
//     zeigen ihn deshalb als benannte, unbezifferte Gegenbuchung — mit den
//     echten Jahreszahlen daneben, damit sich jeder selbst ein Bild macht.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, RotateCcw } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  HaushaltDaten, RUECKLAGE_MIO, bereiche, deMio, jahreSortiert, mio, summe,
} from "@/lib/haushalt";
import { PFLICHT_ZUORDNUNG } from "@/lib/haushalt-pflicht";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

const GEWST_HEBESATZ = 439;

export default function LaborPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const [punkte, setPunkte] = useState(0);
  const [kuerzung, setKuerzung] = useState<Record<string, number>>({});

  const basis = useMemo(() => {
    if (!data) return null;
    const jahre = jahreSortiert(data);
    const jahr = jahre[jahre.length - 1];
    const zeilen = data.jahre[String(jahr)] ?? [];
    const g = summe(zeilen);
    const defizit = g?.ertraege != null && g?.aufwendungen != null
      ? mio(g.aufwendungen - g.ertraege) ?? 0 : 0;
    const gewst = data.steuern
      .filter((s) => s.art === "Gewerbesteuer (-umlage)" && s.betrag)
      .sort((a, b) => a.jahr - b.jahr).at(-1);
    const freiwillig = bereiche(zeilen)
      .filter((z) => PFLICHT_ZUORDNUNG[z.bereich]?.stufe === "freiwillig")
      .map((z) => ({ bereich: z.bereich, aus: mio(z.aufwendungen) ?? 0 }))
      .sort((a, b) => b.aus - a.aus);
    const kraft = data.steuerkraft.filter((k) => k.messzahl != null && k.zuweisungen != null).slice(-2);
    return { jahr, defizit, gewst, freiwillig, kraft };
  }, [data]);

  if (loading || !data || !basis) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Labor wird geladen …</div>;
  }

  const proPunkt = basis.gewst ? (basis.gewst.betrag as number) / 1e6 / GEWST_HEBESATZ : 0;
  const mehrEinnahmen = Math.round(proPunkt * punkte * 10) / 10;
  const gespart = basis.freiwillig.reduce(
    (s, f) => s + (f.aus * (kuerzung[f.bereich] ?? 0)) / 100, 0);
  const neuesDefizit = Math.round((basis.defizit - mehrEinnahmen - gespart) * 10) / 10;
  const reichweiteVorher = basis.defizit > 0 ? RUECKLAGE_MIO / basis.defizit : Infinity;
  const reichweiteNachher = neuesDefizit > 0 ? RUECKLAGE_MIO / neuesDefizit : Infinity;
  const etwasGeaendert = punkte !== 0 || Object.values(kuerzung).some((v) => v > 0);

  const quellen: QuellenSchluessel[] = ["plan", "steuern", "steuerkraft", "hebesaetze", "ruecklage"];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Haushalts-Labor</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">Haushalts-Labor</h1>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Was passiert, wenn der Rat an den Stellschrauben dreht? Hier kannst du es ausprobieren.
          Das ist eine Rechnung zum Verstehen — kein Vorschlag und schon gar kein Beschluss.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-3">
          {/* Einnahmen drehen */}
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Einnahmen drehen
            </p>
            <div className="mt-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <label htmlFor="gewst" className="text-[13px] font-semibold">Gewerbesteuer</label>
                <span className="font-mono text-[13px] tabular-nums">
                  <span className={cn(punkte !== 0 && "text-muted-foreground line-through")}>
                    {GEWST_HEBESATZ}&nbsp;%
                  </span>
                  {punkte !== 0 && (
                    <strong className="ml-2 text-signal">
                      {GEWST_HEBESATZ + punkte}&nbsp;% ({punkte > 0 ? "+" : ""}{punkte})
                    </strong>
                  )}
                </span>
              </div>
              <input
                id="gewst" type="range" min={-50} max={50} step={5} value={punkte}
                onChange={(e) => setPunkte(Number(e.target.value))}
                className="mt-2 w-full accent-[color:hsl(var(--primary))]"
              />
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
                Ein Punkt brachte {basis.jahr && basis.gewst ? `${basis.gewst.jahr}` : ""} überschlagen{" "}
                {deMio(proPunkt)}&#8239;Mio.&nbsp;€ <Beleg q="steuern" /> — bei unveränderten Gewinnen.
              </p>
            </div>
            <div className="mt-3 rounded-xl border border-dashed border-border p-3">
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
            <div className="mt-3 flex flex-col gap-3.5">
              {basis.freiwillig.map((f) => (
                <div key={f.bereich}>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <label htmlFor={f.bereich} className="text-[13px] font-semibold">{f.bereich}</label>
                    <span className="font-mono text-[13px] tabular-nums">
                      <span className={cn((kuerzung[f.bereich] ?? 0) > 0 && "text-muted-foreground line-through")}>
                        {deMio(f.aus)}
                      </span>
                      {(kuerzung[f.bereich] ?? 0) > 0 && (
                        <strong className="ml-2 text-signal">
                          {deMio(f.aus * (1 - (kuerzung[f.bereich] ?? 0) / 100))} (−{kuerzung[f.bereich]}&nbsp;%)
                        </strong>
                      )}
                    </span>
                  </div>
                  <input
                    id={f.bereich} type="range" min={0} max={30} step={5}
                    value={kuerzung[f.bereich] ?? 0}
                    onChange={(e) => setKuerzung((k) => ({ ...k, [f.bereich]: Number(e.target.value) }))}
                    className="mt-2 w-full accent-[color:hsl(var(--primary))]"
                  />
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
              Nur ganze Teilhaushalte, nur prozentual: Einzelne Einrichtungen können wir nicht
              rechnen, solange die Produktebene fehlt — und ein Beschluss wäre das ohnehin nicht.
            </p>
          </div>
        </div>

        {/* Ergebnis, klebt auf dem Desktop */}
        <div className="flex flex-col gap-3 lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-2xl border border-signal/40 bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
              Dein Haushalt
            </p>
            <div className="mt-3">
              <p className="text-[11.5px] text-muted-foreground">Minus am Jahresende</p>
              <p className="font-display text-[26px] font-bold tabular-nums">
                {neuesDefizit > 0 ? deMio(neuesDefizit) : "0,0"}
                <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
                {etwasGeaendert && (
                  <span className="ml-2 align-middle font-sans text-[13px] text-muted-foreground line-through">
                    {deMio(basis.defizit)}
                  </span>
                )}
              </p>
            </div>
            <div className="mt-3 border-t border-border/60 pt-3">
              <p className="text-[11.5px] text-muted-foreground">Rücklage reicht rechnerisch</p>
              <p className="font-display text-[22px] font-bold tabular-nums">
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
            {etwasGeaendert && neuesDefizit > 0 && (
              <p className="mt-3 rounded-lg bg-muted/50 p-2.5 text-[12px] leading-relaxed">
                Deine Änderungen wirken. Ein ausgeglichener Haushalt wäre damit noch nicht erreicht.
              </p>
            )}
            {etwasGeaendert && (
              <button type="button"
                onClick={() => { setPunkte(0); setKuerzung({}); }}
                className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-primary">
                <RotateCcw className="h-3.5 w-3.5" /> Szenario zurücksetzen
              </button>
            )}
          </div>

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

      <LottiErklaert
        titel="Warum das kein Sparvorschlag ist"
        text="Dieses Labor rechnet mit ganzen Bereichen und festen Annahmen. Ein echter Haushalt entsteht anders: Die Verwaltung rechnet jede Position durch, Ausschüsse beraten monatelang, und am Ende stimmt der Rat ab. Was du hier siehst, ist ein Gefühl für Größenordnungen — mehr nicht, aber auch nicht weniger."
      />

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
