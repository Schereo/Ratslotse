"use client";

// Werkbank 1 des Haushalts-Labors: Einnahmen (Labor 2.0, Entwürfe 24.08.2026).
//
// Drei Regler und eine Schraube, die sich absichtlich nicht drehen lässt:
//
//  * **Gewerbesteuer-Hebesatz** — wie bisher, neu mit zwei Bezugsgrößen, die
//    beim Drehen mitlaufen: die Hebesätze der kreisfreien Städte als Leiter
//    (ein Hebesatz ohne Nachbarn ist nur eine Zahl) und die eigene Reihe seit
//    1980 als Treppe (der Satz gilt, bis der Rat neu entscheidet).
//  * **Grundsteuer B** — der Regler, der bis heute fehlte. Der Open-Data-Satz
//    führt A und B in einer Spalte; gerechnet wird mit dem B-Hebesatz, und
//    der Fehler dabei steht AN der Zahl: Der Realsteuervergleich des Landes
//    weist beide Aufkommen getrennt aus, A liegt im Promillebereich
//    (lib/haushalt-labor.ts: grundsteuerAnteilA). Die Reform 2025 steht als
//    Warnung daneben — Hebesatz +21 %, Aufkommen trotzdem gesunken.
//  * **Hundesteuer** — der Anti-Stammtisch-Regler: Er zeigt vor allem, wie
//    WENIG kleine Steuern ausrichten. (Die Zeile „sonstige Steuern“ des
//    Open-Data-Satzes IST die Hundesteuer — der Abgleich mit Jahrbuch 1103
//    beweist das jahrgangsweise, council/steuertabellen.py.)
//  * **Gebühren** — festgeschweißt: Kostenrechnende Einrichtungen dürfen
//    keinen Überschuss erwirtschaften. Eine sichtbare, gesperrte Schraube
//    ist hier die Aussage, kein fehlendes Feature.

import Link from "next/link";
import { Lock } from "lucide-react";
import { deMio, betrag, type GebuehrenZeile, type HebesatzZeile } from "@/lib/haushalt";
import type { StadtHebesatz } from "@/lib/haushalt-labor";
import { Beleg } from "@/components/haushalt/quelle";
import { Regler } from "@/components/haushalt/regler";
import { StaedteLeiter } from "@/components/haushalt/staedte-leiter";

/** Steuermesszahl nach § 11 GewStG — bundesweit gleich, nicht unsere Annahme. */
const MESSZAHL = 0.035;
/** Beispielbetrieb wie im Steuer-Steckbrief — dieselbe Zahl an beiden Stellen. */
const BEISPIEL_GEWINN = 100_000;

function eur(v: number): string {
  return v.toLocaleString("de-DE", { maximumFractionDigits: 0 });
}

/** Die eigene Hebesatz-Geschichte als Mini-Treppe — eine Treppe, keine Kurve:
 *  Tabelle 1105 führt nur Änderungsjahre, dazwischen gilt der Satz weiter
 *  (dieselbe Begründung wie bei der großen Treppe des Steuer-Steckbriefs). */
function HistorieTreppe({ reihe, bisJahr }: { reihe: HebesatzZeile[]; bisJahr: number }) {
  const stufen = reihe
    .filter((z) => z.hebesatz != null)
    .sort((a, b) => a.year - b.year);
  if (stufen.length < 2) return null;
  const saetze = stufen.map((z) => z.hebesatz as number);
  const [min, max] = [Math.min(...saetze), Math.max(...saetze)];
  const vonJahr = stufen[0].year;
  const breite = 280, hoehe = 44;
  const x = (year: number) => ((year - vonJahr) / Math.max(1, bisJahr - vonJahr)) * breite;
  const y = (satz: number) => 6 + (1 - (satz - min) / Math.max(1, max - min)) * (hoehe - 14);
  let pfad = "";
  stufen.forEach((z, i) => {
    const px = x(z.year), py = y(z.hebesatz as number);
    pfad += i === 0 ? `M${px},${py}` : `H${px} V${py}`;
  });
  pfad += ` H${breite}`;
  const letzte = stufen[stufen.length - 1];
  return (
    <div className="mt-2.5 border-t border-dashed border-border pt-2.5">
      <svg viewBox={`0 0 ${breite} ${hoehe}`} className="block h-11 w-full" aria-hidden>
        <path d={pfad} fill="none" strokeWidth="2" style={{ stroke: "var(--hh-ein-1)" }} />
        <circle cx={x(letzte.year)} cy={y(letzte.hebesatz as number)} r="3"
          style={{ fill: "hsl(var(--primary))" }} />
      </svg>
      <p className="mt-1 text-[10.5px] text-muted-foreground">
        Die eigene Reihe seit {vonJahr}: {letzte.hebesatz}&nbsp;% gelten seit {letzte.year}
        <Beleg q="hebesaetze" /> — wenige Entscheidungen, lange Gültigkeit.
      </p>
    </div>
  );
}

export function EinnahmenWerkbank({
  basisJahr, punkte, setPunkte, gewst, proPunktGewst, gewstBasisJahr,
  grundstPunkte, setGrundstPunkte, grundst, proPunktGrundst, anteilA,
  hundePct, setHundePct, hunde,
  staedte, historie, gebuehren,
  maxPunkte, jeEinwohner, anteilText,
}: {
  basisJahr: number;
  punkte: number; setPunkte: (v: number) => void;
  gewst: { satz: number; seit: number } | null;
  /** Mio. € je Hebesatzpunkt, überschlagen aus dem jüngsten Ist. */
  proPunktGewst: number;
  gewstBasisJahr: number | null;
  grundstPunkte: number; setGrundstPunkte: (v: number) => void;
  grundst: { satz: number; seit: number } | null;
  proPunktGrundst: number | null;
  /** Anteil der Grundsteuer A am gemeinsamen Aufkommen — aus dem LSN-Vergleich. */
  anteilA: number | null;
  hundePct: number; setHundePct: (v: number) => void;
  hunde: { year: number; betrag: number } | null;
  staedte: StadtHebesatz[];
  historie: HebesatzZeile[];
  gebuehren: GebuehrenZeile[] | undefined;
  maxPunkte: number;
  jeEinwohner: (m: number) => string;
  anteilText: (m: number) => string;
}) {
  const gewstWirkung = Math.round(proPunktGewst * punkte * 10) / 10;
  const grundstWirkung = proPunktGrundst != null
    ? Math.round(proPunktGrundst * grundstPunkte * 10) / 10 : 0;
  const hundeWirkung = hunde ? Math.round(((hunde.betrag / 1e6) * hundePct) / 100 * 10) / 10 : 0;

  // Die gesperrte Schraube braucht eine echte Zahl, sonst wäre sie nur ein
  // Icon: die umzulegenden Kosten des jüngsten Jahrgangs, alle drei Bereiche.
  const gebJahr = gebuehren?.length ? Math.max(...gebuehren.map((g) => g.year)) : null;
  const gebSumme = gebJahr != null
    ? (gebuehren ?? []).filter((g) => g.year === gebJahr)
        .reduce((s, g) => s + g.zu_deckende_kosten, 0) : null;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Einnahmen drehen
      </p>

      {/* Gewerbesteuer — kein Satz, kein Regler (Designsprache: lieber eine
          Lücke als eine Schätzung). */}
      {gewst == null ? (
        <p className="mt-3 rounded-xl border border-dashed border-border p-3 text-[12px] leading-relaxed text-muted-foreground">
          Für den Gewerbesteuer-Hebesatz liegt uns gerade keine Reihe vor —
          ohne den geltenden Satz lässt sich nicht ausrechnen, was ein Punkt
          mehr oder weniger brächte.
        </p>
      ) : (
        <div className="mt-3">
          <Regler
            id="gewst"
            label="Gewerbesteuer-Hebesatz"
            wert={punkte} min={-maxPunkte} max={maxPunkte} step={5}
            onChange={setPunkte}
            geaendert={punkte !== 0}
            ist={{ wert: 0, label: `heute ${gewst.satz} %` }}
            marken={{ min: `${gewst.satz - maxPunkte} %`, max: `${gewst.satz + maxPunkte} %` }}
            anzeige={
              punkte === 0
                ? <span className="text-muted-foreground">{gewst.satz}&nbsp;%<Beleg q="hebesaetze" /></span>
                : <strong className="text-signal">
                    {gewst.satz + punkte}&nbsp;% ({punkte > 0 ? "+" : ""}{punkte})
                  </strong>
            }
            wirkung={
              punkte === 0 ? (
                <>Ein Punkt brachte {gewstBasisJahr} überschlagen {deMio(proPunktGewst)}&#8239;Mio.&nbsp;€{" "}
                <Beleg q="steuern" /> — bei unveränderten Gewinnen.</>
              ) : (
                <>
                  <strong className="text-foreground">
                    {gewstWirkung > 0 ? "+" : ""}{deMio(gewstWirkung)}&#8239;Mio.&nbsp;€
                  </strong>{" "}
                  · {jeEinwohner(Math.abs(gewstWirkung))} · {anteilText(Math.abs(gewstWirkung))}
                  {punkte < 0 && " zusätzlich"}.
                  <br />
                  Ein Betrieb mit {eur(BEISPIEL_GEWINN)}&nbsp;€ Gewerbeertrag zahlte statt{" "}
                  {eur((BEISPIEL_GEWINN * MESSZAHL * gewst.satz) / 100)}&nbsp;€ dann{" "}
                  <strong>{eur((BEISPIEL_GEWINN * MESSZAHL * (gewst.satz + punkte)) / 100)}&nbsp;€</strong>{" "}
                  im Jahr — Messzahl 3,5&nbsp;% nach Bundesrecht, ohne Freibetrag.
                </>
              )
            }
          />
          {/* Die Leiter läuft beim Drehen mit: Wo stünde Oldenburg damit? */}
          <StaedteLeiter
            staedte={staedte}
            heute={gewst.satz}
            deinWert={gewst.satz + punkte}
            geaendert={punkte !== 0}
          />
          <HistorieTreppe reihe={historie} bisJahr={basisJahr} />
          <Link href="/haushalt/steuer?art=gewerbesteuer"
            className="mt-2.5 inline-flex text-[12px] font-semibold text-primary">
            Wer den Hebesatz beschließt →
          </Link>
        </div>
      )}

      {/* Grundsteuer B — neu. Ohne Hebesatz-Reihe ODER ohne belegte
          Aufteilung bleibt der alte, ehrliche Kasten stehen. */}
      <div className="mt-4 border-t border-border/60 pt-4">
        {grundst == null || proPunktGrundst == null ? (
          <div className="rounded-xl border border-dashed border-border p-3">
            <p className="text-[12.5px] font-semibold">Grundsteuer B</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
              Hier fehlt uns gerade die Grundlage: Der offene Datensatz führt Grundsteuer A
              und B in einer Spalte, und die belegte Aufteilung aus dem Realsteuervergleich
              des Landes liegt nicht vor. Wir schätzen nicht — sobald die Reihe da ist,
              steht der Regler hier.
            </p>
          </div>
        ) : (
          <>
            <Regler
              id="grundst"
              label="Grundsteuer B — Hebesatz"
              wert={grundstPunkte} min={-maxPunkte} max={maxPunkte} step={5}
              onChange={setGrundstPunkte}
              geaendert={grundstPunkte !== 0}
              ist={{ wert: 0, label: `heute ${grundst.satz} %` }}
              marken={{ min: `${grundst.satz - maxPunkte} %`, max: `${grundst.satz + maxPunkte} %` }}
              anzeige={
                grundstPunkte === 0
                  ? <span className="text-muted-foreground">{grundst.satz}&nbsp;%<Beleg q="hebesaetze" /></span>
                  : <strong className="text-signal">
                      {grundst.satz + grundstPunkte}&nbsp;% ({grundstPunkte > 0 ? "+" : ""}{grundstPunkte})
                    </strong>
              }
              wirkung={
                grundstPunkte === 0 ? (
                  <>Ein Punkt bringt überschlagen {betrag(proPunktGrundst * 1e6).wert}&#8239;
                  {betrag(proPunktGrundst * 1e6).einheit} <Beleg q="steuern" /> — bei
                  unveränderten Messbeträgen.</>
                ) : (
                  <>
                    <strong className="text-foreground">
                      {grundstWirkung > 0 ? "+" : ""}{deMio(grundstWirkung)}&#8239;Mio.&nbsp;€
                    </strong>{" "}
                    · {jeEinwohner(Math.abs(grundstWirkung))} · {anteilText(Math.abs(grundstWirkung))}
                    {grundstPunkte < 0 && " zusätzlich"}. Zahlen alle, die wohnen —
                    über die Nebenkosten auch Mieter*innen.
                  </>
                )
              }
            />
            <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
              Gerechnet mit dem gemeinsamen Aufkommen „Grundsteuer A+B“ und dem
              B-Hebesatz: Der Realsteuervergleich des Landes weist beide Steuern
              getrennt aus — Grundsteuer A steckt mit{" "}
              {anteilA != null
                ? <>rund {(anteilA * 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;‰</>
                : "einem Promille-Anteil"}{" "}
              darin<Beleg q="lsn_realsteuern" />. Und Vorsicht mit „mehr Hebesatz =
              mehr Geld“: 2025 stieg der B-Satz von 445 auf {grundst.satz}&nbsp;%, das
              Aufkommen sank trotzdem — die Reform setzte zugleich alle Messbeträge neu.
            </p>
          </>
        )}
      </div>

      {/* Hundesteuer — zeigt Größenordnung, nicht Sanierung. In BEIDE
          Richtungen bis zum Anschlag: verdoppeln oder ganz abschaffen — beide
          Stammtisch-Forderungen, beide winzig (Tims Symmetrie-Befund 24.08.). */}
      {hunde && (
        <div className="mt-4 border-t border-border/60 pt-4">
          <Regler
            id="hunde"
            label="Hundesteuer"
            wert={hundePct} min={-100} max={100} step={25}
            onChange={setHundePct}
            geaendert={hundePct !== 0}
            ist={{ wert: 0, label: "heute" }}
            marken={{ min: "abschaffen", max: "verdoppeln" }}
            anzeige={
              hundePct === 0
                ? <span className="text-muted-foreground">
                    {betrag(hunde.betrag).wert}&nbsp;{betrag(hunde.betrag).einheit}<Beleg q="steuern" />
                  </span>
                : <strong className="text-signal">
                    {hundePct === -100
                      ? <>0&nbsp;€ (abgeschafft)</>
                      : <>{betrag(hunde.betrag * (1 + hundePct / 100)).wert}&nbsp;
                        {betrag(hunde.betrag * (1 + hundePct / 100)).einheit}{" "}
                        ({hundePct > 0 ? "+" : "−"}{Math.abs(hundePct)}&nbsp;%)</>}
                  </strong>
            }
            wirkung={
              hundePct === 0 ? (
                <>Aufkommen {hunde.year}. Der Regler zeigt die Größenordnung in beide
                Richtungen: Sowohl eine Verdopplung als auch die Abschaffung verändern
                das Ergebnis um rund{" "}
                {anteilText(hunde.betrag / 1e6)}.</>
              ) : hundePct > 0 ? (
                <>
                  <strong className="text-foreground">+{deMio(hundeWirkung)}&#8239;Mio.&nbsp;€</strong>{" "}
                  · {anteilText(hundeWirkung)}. Damit lässt sich das Haushaltsdefizit
                  allein nicht ausgleichen.
                </>
              ) : (
                <>
                  <strong className="text-foreground">{deMio(hundeWirkung)}&#8239;Mio.&nbsp;€</strong>{" "}
                  — das Minus wächst um {anteilText(-hundeWirkung)}. Auch die Abschaffung ist
                  Symbolik, nur andersherum.
                </>
              )
            }
          />
        </div>
      )}

      {/* Die festgeschweißte Schraube. Gestrichelt = „hier dreht sich nichts“
          (Designsprache §4), das Schloss sagt: mit Absicht. */}
      <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-dashed border-border p-3">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" strokeWidth={2} />
        <div>
          <p className="text-[12.5px] font-semibold">
            Abfall- und Straßenreinigungsgebühren sind kostengebunden
          </p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
            {gebSumme != null && gebJahr != null ? (
              <>{deMio(gebSumme / 1e6)}&#8239;Mio.&nbsp;€ legt die Stadt {gebJahr} auf die
              Gebührenzahler um<Beleg q="gebuehren" /> — mehr darf es nicht sein: </>
            ) : (
              <>Der Rat kann diese Gebühren nicht zur allgemeinen Haushaltsfinanzierung erhöhen: </>
            )}
            Kostenrechnende Einrichtungen dürfen auf Dauer keinen Überschuss erwirtschaften.
            Deshalb gibt es dafür im Labor keinen frei einstellbaren Regler.{" "}
            <Link href="/haushalt/konzern#gebuehren" className="font-semibold text-primary">
              Wie die Gebühren entstehen →
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
