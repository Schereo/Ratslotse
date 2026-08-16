"use client";

// Zeitreihen-Modul (Design H-07, überarbeitet als H2-04): genau eine Aussage —
// die Schere zwischen geplanten Einnahmen und geplanten Ausgaben.
//
// WARUM EINE FLÄCHE MIT STREBEN UND NICHT ZWEI LINIEN.
// Zwei Linien zeigen zwei Größen. Die Aussage steckt aber im ABSTAND zwischen
// ihnen, und den musste die Leserin bisher selbst abmessen. Jetzt ist der
// Abstand ein eigenes Objekt: eine Fläche zwischen den Linien, an jedem Jahr
// von einer senkrechten Strebe gefasst. Die Strebe steht genau über ihrem
// Betrag in der Ergebniszeile — sehen und lesen am selben Ort.
//
// KEINE BEWERTUNGSFARBEN. Die Fläche ist in JEDEM Jahr Signal-Orange, auch in
// den Überschussjahren. Orange heißt hier „das ist die Differenz", nicht „das
// ist schlimm". Der Entwurf setzte Überschüsse grün (#15803d) und Defizite
// orange — damit wäre ein Haushaltsplus gut und ein Minus schlecht. Diese
// Wertung trifft der Haushalts-Bereich nirgends; die lange Begründung steht in
// `hantel.tsx`.
//
// PLAN IST NICHT IST — UND DAS IST HIER DIE ZWEITE AUSSAGE.
// Die Linien sind Planwerte aus den beschlossenen Haushaltsplänen. Was am
// Jahresende herauskam, steht im Jahresabschluss und widerspricht dem Plan
// regelmäßig: 2023 und 2024 plante die Stadt ein Minus und schloss mit einem
// Plus ab. Deshalb tragen die Jahre mit Abschluss zusätzlich RAUTEN auf der
// gleichen Achse (Plan = Kreis, tatsächlich = Raute, dazu eine gepunktete
// Strecke als Abweichung). Ohne diese Unterscheidung wäre eine Überschrift
// wie „Seit 2023 gibt Oldenburg mehr aus, als es einnimmt" schlicht falsch —
// geplant wird das, eingetreten ist es nicht.
//
// WAS „PLAN" HEISST, WECHSELT ÜBER DIE JAHRGÄNGE. Der Jahresabschluss misst
// nicht überall gegen dieselbe Bezugsgröße (2018 Gesamtermächtigung, 2020
// Ansatz einschließlich Nachtrag, sonst der nackte Ansatz — `plan_art`, #510).
// Solche Jahre bekommen ein Sternchen an der Jahreszahl und eine Fußnote,
// dieselbe Grammatik wie in `labor.tsx`.
//
// LÜCKEN-KONVENTION: fehlende Jahre werden nie interpoliert. Schraffierter
// Kasten, Linie und Fläche BRECHEN AB (gepunktete Stummel), Jahr in
// Signal-Orange, Wert „?". 2020–2026 ist derzeit lückenlos — die Logik bleibt
// trotzdem stehen, weil sie an der nächsten Quelle wieder greift.
//
// DIE VIEWBOX IST SO BREIT WIE IHR CONTAINER, NICHT FIX. Sonst staucht das SVG
// alles mit — bei 486 px Containerbreite landeten „16 px" Schrift als 11 px
// auf dem Schirm, und die Achsen blieben unlesbar, obwohl die Zahl im Code
// größer wurde (Tim, 16.08., zweiter Anlauf). Gemessen wird der Container des
// Diagramms, nicht der äußere Rahmen: Im zweispaltigen Layout sind das zwei
// verschiedene Breiten.
//
// MOBIL WIRD UMGEBAUT, NICHT GESCHRUMPFT (wie `flussbild.tsx`): unter 860 px
// Containerbreite fällt die zweite Spalte unter das Diagramm, unter 520 px
// wächst die Schrift und die Jahresbeschriftung dünnt aus.
//
// SIEBEN JAHRE MAL VIER GRÖSSEN PASSEN NICHT ALLE INS BILD — DIE WICHTIGSTEN
// SCHON. Dauerhaft angeschrieben sind das Ergebnis jedes Jahres (unter seiner
// Strebe), der größte Abstand und die beiden Linienenden. Die restlichen Werte
// trägt die Ableseleiste unter dem Bild (`ablesen.tsx`): Sie zeigt IMMER ein
// Jahr — im Ruhezustand das jüngste — und wechselt beim Überfahren, Antippen
// oder mit den Pfeiltasten. Kein Tooltip: Was nur beim Hovern existiert, fehlt
// im Ausdruck, im Screenshot und in der Vorlesehilfe.
//
// DIE TABELLE BLEIBT, ABER EINGEKLAPPT. Vier Größen über sieben Jahre sind 28
// Zahlen; die kann kein Liniendiagramm gleichzeitig anschreiben, ohne
// unlesbar zu werden. Die Leiste zeigt sie einzeln, die Tabelle alle
// nebeneinander — beides hat seinen Fall, und wer die Reihe vergleichen will,
// braucht die Tabelle. Sie startet deshalb zugeklappt statt zu verschwinden.

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import {
  ErgebnisPosten, HaushaltDaten, PLAN_ART_LABEL, PlanArt,
  deMio, fehlendeJahre, jahreSortiert, mio, summe,
} from "@/lib/haushalt";
import { Beleg } from "@/components/haushalt/quelle";
import {
  AbleseBeschreibung, AbleseFlaeche, AbleseMarke, AbleseStelle, AbleseWert,
  Ableseleiste, useAblesen,
} from "@/components/haushalt/ablesen";

// saldo aus den ROHWERTEN gerundet, nicht aus den gerundeten Mio. — sonst
// driftet er um 0,1 (693,9 − 728,2 = −34,3, tatsächlich sind es −34,2).
type Punkt = { jahr: number; ein: number; aus: number; saldo: number };
/** Dasselbe Jahr, aber aus dem Jahresabschluss: ordentliche Erträge (Posten
 *  12) und Aufwendungen (20), wie sie tatsächlich angefallen sind. */
type IstPunkt = Punkt & { planArt: PlanArt | null };

/** Ab dieser Containerbreite steht die Auswertung neben dem Diagramm. */
const SCHWELLE_ZWEISPALTIG = 860;
/** Ab dieser Breite des DIAGRAMMS reicht die kleine Schrift. */
const SCHWELLE_SCHMAL = 520;
const SEITE_BREITE = 296;

// Beschriftungen im Diagramm bekommen einen Kontur-Halo in Kartenfarbe, sonst
// schneiden Linien und Fläche mitten durch die Ziffern (Muster aus `ist-kurve`).
const halo = { paintOrder: "stroke", strokeWidth: 3.5, strokeLinejoin: "round" } as const;

/** Breite eines Elements — als Bruchzahl, damit die viewBox exakt der
 *  gemessenen Breite entspricht und der Skalierungsfaktor 1,0 bleibt.
 *  `clientWidth` rundet auf ganze Pixel und brächte bei 486,4 px schon 1,0008. */
function breiteVon(el: HTMLElement | null): number | null {
  if (!el) return null;
  const w = el.getBoundingClientRect().width;
  return w > 0 ? Math.max(w, 280) : null;
}

export function Zeitreihe({ daten }: { daten: HaushaltDaten }) {
  const aussen = useRef<HTMLDivElement>(null);
  const bildBox = useRef<HTMLDivElement>(null);
  // Startwerte klein: Der erste Frame läuft dann einspaltig durch, statt eine
  // zweite Spalte zu zeigen, die auf dem Telefon sofort wieder verschwindet.
  const [aussenBreite, setAussenBreite] = useState(0);
  const [breite, setBreite] = useState(560);
  const [tabelleGeschaltet, setTabelleGeschaltet] = useState<boolean | null>(null);

  useEffect(() => {
    const setzeWennGeaendert = (
      wert: number | null, setter: (n: number) => void, alt: () => number,
    ) => { if (wert != null && Math.abs(wert - alt()) > 0.5) setter(wert); };
    let letztesAussen = 0, letztesBild = 560;
    const pruefe = () => {
      setzeWennGeaendert(breiteVon(aussen.current), (n) => {
        letztesAussen = n; setAussenBreite(n);
      }, () => letztesAussen);
      setzeWennGeaendert(breiteVon(bildBox.current), (n) => {
        letztesBild = n; setBreite(n);
      }, () => letztesBild);
    };
    pruefe();
    const ro = new ResizeObserver(pruefe);
    if (aussen.current) ro.observe(aussen.current);
    if (bildBox.current) ro.observe(bildBox.current);
    return () => ro.disconnect();
  }, []);

  const breit = aussenBreite >= SCHWELLE_ZWEISPALTIG;
  const schmal = breite < SCHWELLE_SCHMAL;
  const fs = schmal
    ? { achse: 13, jahr: 14, saldo: 12.5, legende: 13, marke: 12.5 }
    : { achse: 11, jahr: 12, saldo: 11.5, legende: 12, marke: 12 };

  const jahre = jahreSortiert(daten);
  const punkte: Punkt[] = jahre
    .map((jahr) => {
      const s = summe(daten.jahre[String(jahr)] ?? []);
      const ein = mio(s?.ertraege), aus = mio(s?.aufwendungen);
      const saldo = mio((s?.ertraege ?? 0) - (s?.aufwendungen ?? 0));
      return ein != null && aus != null && saldo != null ? { jahr, ein, aus, saldo } : null;
    })
    .filter((p): p is Punkt => p !== null);

  const luecken = punkte.length >= 2 ? fehlendeJahre(punkte.map((p) => p.jahr)) : [];
  const alleJahre: number[] = [];
  if (punkte.length >= 2) {
    for (let y = punkte[0].jahr; y <= punkte[punkte.length - 1].jahr; y++) alleJahre.push(y);
  }
  // Die beiden Ablese-Haken stehen VOR dem Ausstieg: Ein Hook hinter einem
  // `return` ist kein Hook mehr, sondern ein Absturz beim nächsten Render.
  const ablesen = useAblesen(alleJahre.length, alleJahre.length - 1);
  const beschreibungId = useId();
  if (punkte.length < 2) return null;

  // --- Was tatsächlich daraus wurde (Jahresabschlüsse) --------------------
  // Posten 12 = Summe ordentliche Erträge, 20 = Summe ordentliche
  // Aufwendungen, jeweils die Kernverwaltung (thh_nr === null). Genau diese
  // Ebene trägt auch `council_haushalt` — nur so sind Plan und Ist auf
  // derselben Achse überhaupt vergleichbar. Jahrgänge, in denen ein Posten
  // fehlt, fallen ganz heraus statt halb gerechnet zu werden.
  const abschluss = daten.ergebnisrechnung ?? [];
  const istNach = new Map<number, IstPunkt>();
  for (const jahr of alleJahre) {
    const g = abschluss.filter((p) => p.jahr === jahr && p.thh_nr == null);
    const finde = (nr: number): ErgebnisPosten | undefined => g.find((p) => p.nr === nr);
    const e = finde(12), a = finde(20);
    const ein = mio(e?.ergebnis), aus = mio(a?.ergebnis);
    if (ein == null || aus == null) continue;
    const saldo = mio((e!.ergebnis as number) - (a!.ergebnis as number));
    if (saldo == null) continue;
    istNach.set(jahr, {
      jahr, ein, aus, saldo,
      planArt: (a?.plan_art ?? e?.plan_art ?? null) as PlanArt | null,
    });
  }
  const istPunkte = [...istNach.values()];
  // Jahrgänge, deren „geplant" im Abschluss nicht der nackte Ansatz ist.
  const andererBezug = istPunkte.filter((p) => p.planArt != null && p.planArt !== "ansatz");
  const bezugsJahre = new Set(andererBezug.map((p) => p.jahr));

  // --- Skala --------------------------------------------------------------
  // Ist-Werte zählen mit, sonst fielen ihre Rauten aus dem Bild.
  //
  // Die Ränder rasten auf 50er, die Gitterlinien bleiben bei den runden
  // Hundertern. Auf 100er gerundet begann die Achse bei 500, obwohl der
  // kleinste Wert 582,5 ist — ein Fünftel der Zeichenfläche blieb leer, und
  // genau dort unten wird die Schere flach und schwer zu lesen. Ein Nullpunkt
  // ist hier ohnehin keine Pflicht: Gezeigt wird der ABSTAND zweier Linien,
  // nicht die Länge eines Balkens.
  const werte = [...punkte.flatMap((p) => [p.ein, p.aus]), ...istPunkte.flatMap((p) => [p.ein, p.aus])];
  const lo = Math.floor(Math.min(...werte) / 50) * 50;
  const hi = Math.ceil(Math.max(...werte) / 50) * 50;

  const plotH = schmal ? 190 : breit ? 238 : 208;
  const YTOP = 16;
  const Y0 = YTOP + plotH;
  const yJahr = Y0 + (schmal ? 24 : 21);
  const ySaldo = yJahr + (schmal ? 19 : 16);
  const H = ySaldo + 10;

  const W = breite;
  const X0 = schmal ? 40 : 44;                       // links: Platz für „900"
  const reserve = Math.ceil(fs.legende * 2.4) + 12;  // rechts: „ein" / „aus"
  const XP = W - reserve;                            // letzter Datenpunkt
  const x = (jahr: number) =>
    X0 + 10 + ((jahr - alleJahre[0]) / Math.max(alleJahre.length - 1, 1)) * (XP - X0 - 10);
  const y = (v: number) => Y0 - ((v - lo) / Math.max(hi - lo, 1)) * (plotH - 14);

  const gitter: number[] = [];
  // Auf schmal jede zweite Linie — bei lesbarer Schrift kleben sie sonst.
  const schritt100 = schmal && (hi - lo) / 100 > 3 ? 200 : 100;
  for (let v = Math.ceil(lo / schritt100) * schritt100; v <= hi; v += schritt100) gitter.push(v);

  // Jahresabstand — die Lückenkästen dürfen nicht breiter sein als ihr Fach.
  const abstand = alleJahre.length > 1 ? x(alleJahre[1]) - x(alleJahre[0]) : 80;
  const halbeLuecke = Math.max(12, Math.min(42, abstand * 0.45));

  // Segmente: an jeder Lücke neu ansetzen (Konvention: kein Durchziehen).
  const segmente: Punkt[][] = [];
  let akt: Punkt[] = [];
  for (const jahr of alleJahre) {
    const p = punkte.find((q) => q.jahr === jahr);
    if (p) akt.push(p);
    else if (akt.length) { segmente.push(akt); akt = []; }
  }
  if (akt.length) segmente.push(akt);

  const pfad = (seg: Punkt[], key: "ein" | "aus") =>
    seg.map((p, i) => `${i ? "L" : "M"}${x(p.jahr)} ${y(p[key])}`).join(" ");
  // Die Fläche wird PRO SEGMENT geschlossen. Eine durchgehende Fläche über
  // einer fehlenden Jahresscheibe interpolierte optisch — genau das, was die
  // Lücken-Konvention verhindert.
  const flaeche = (seg: Punkt[]) =>
    `${pfad(seg, "ein")} ${[...seg].reverse().map((p) => `L${x(p.jahr)} ${y(p.aus)}`).join(" ")} Z`;

  const erster = punkte[0];
  const letzter = punkte[punkte.length - 1];
  const groessteLuecke = punkte.reduce((best, p) => (p.saldo < best.saldo ? p : best), punkte[0]);
  const letzterIst = istPunkte.length ? istPunkte[istPunkte.length - 1] : null;

  // Ab welchem Jahr durchgängig ein Minus geplant ist — die Überschrift wird
  // gerechnet, nicht geschrieben. Ein fester Satz wäre beim nächsten Jahrgang
  // still falsch (Hausregel: keine jahresabhängige Rechenaussage als Text).
  let seit: number | null = null;
  for (let i = punkte.length - 1; i >= 0; i--) {
    if (punkte[i].saldo < 0) seit = punkte[i].jahr; else break;
  }
  const titel = seit == null
    ? `Geplante Einnahmen und Ausgaben ${alleJahre[0]} bis ${alleJahre[alleJahre.length - 1]}`
    : seit === erster.jahr
      ? `In allen ${punkte.length} Jahren plant Oldenburg mit mehr Ausgaben als Einnahmen`
      // „plant", nicht „gibt aus": Für die Jahre mit Abschluss sagen die Daten
      // das Gegenteil. Der Unterschied ist der ganze Punkt dieser Grafik.
      : `Seit ${seit} plant Oldenburg mit mehr Ausgaben als Einnahmen`;

  // Das letzte Jahr VOR der Minus-Serie, das wir auch wirklich haben. Nicht
  // `seit - 1` rechnen: Fehlt ausgerechnet dieses Jahr, behauptete der Satz
  // „Bis 2022 plante die Stadt mit einem Plus" einen Plan, den wir gar nicht
  // kennen — und im Bild steht an derselben Stelle „DATEN FEHLEN"
  // (aufgefallen im Lückentest, 16.08.).
  const letztesPlus = seit == null ? null
    : punkte.filter((p) => p.jahr < seit && p.saldo >= 0).pop() ?? null;

  const wachstum = (a: number, b: number) => (a > 0 ? Math.round((b / a - 1) * 100) : null);
  const wachsAus = wachstum(erster.aus, letzter.aus);
  const wachsEin = wachstum(erster.ein, letzter.ein);

  const vorzeichen = (v: number) => `${v > 0 ? "+" : ""}${deMio(v)}`;
  const alsSatz = (v: number) =>
    `${v < 0 ? "ein Minus" : "ein Plus"} von ${deMio(Math.abs(v))} Mio. €`;

  // Zugeklappt als Vorgabe: Die Werte stehen jetzt in der Ableseleiste, die
  // Tabelle ist der vollständige Nachschlagestand für den, der vergleichen
  // will — nicht mehr die einzige Quelle der Zahlen.
  const tabelleOffen = tabelleGeschaltet ?? false;

  // --- Was die Ableseleiste je Jahr zeigt ---------------------------------
  const stellen: AbleseStelle[] = alleJahre.map((jahr) => {
    const p = punkte.find((q) => q.jahr === jahr);
    const ist = istNach.get(jahr);
    const werte: AbleseWert[] = [
      { label: "ein", wert: p ? deMio(p.ein) : "—", farbe: "var(--hh-ein-0)" },
      { label: "aus", wert: p ? deMio(p.aus) : "—", farbe: "var(--hh-aus-0)" },
      { label: "Ergebnis", wert: p ? vorzeichen(p.saldo) : "—", signal: !!p && p.saldo < 0 },
    ];
    if (istPunkte.length) {
      werte.push({ label: "tatsächlich", wert: ist ? vorzeichen(ist.saldo) : "—" });
    }
    const vorlesen = p
      ? [
          `${jahr}: geplant ${deMio(p.ein)} Millionen Euro Einnahmen,`,
          `${deMio(p.aus)} Millionen Euro Ausgaben,`,
          `Ergebnis ${alsSatz(p.saldo)}.`,
          ist ? `Tatsächlich laut Jahresabschluss ${alsSatz(ist.saldo)}.` : "Noch kein Jahresabschluss.",
        ].join(" ")
      : `${jahr}: keine Daten.`;
    return { titel: String(jahr) + (bezugsJahre.has(jahr) ? "*" : ""), werte, vorlesen };
  });
  // Ringe an den Punkten des abgelesenen Jahres — sehen und lesen am selben Ort.
  const ableseMarken = (i: number): AbleseMarke[] => {
    const p = punkte.find((q) => q.jahr === alleJahre[i]);
    return p
      ? [{ y: y(p.ein), farbe: "var(--hh-ein-0)" }, { y: y(p.aus), farbe: "var(--hh-aus-0)" }]
      : [];
  };

  const beschreibung = [
    `Geplante Einnahmen und Ausgaben ${alleJahre[0]} bis ${alleJahre[alleJahre.length - 1]} in Mio. Euro.`,
    punkte.map((p) => `${p.jahr}: ${deMio(p.ein)} zu ${deMio(p.aus)}`).join(", "),
    luecken.length ? `${luecken.join(", ")}: keine Daten.` : "",
    istPunkte.length
      ? `Tatsächlich laut Jahresabschluss: ${istPunkte.map((p) => `${p.jahr}: ${deMio(p.ein)} zu ${deMio(p.aus)}`).join(", ")}.`
      : "",
  ].filter(Boolean).join(" ");

  // --- Auswertung neben (breit) bzw. unter (schmal) dem Diagramm ----------
  // Die Tabelle steht im breiten Layout UNTER dem Diagramm, nicht daneben:
  // Nebeneinander stapelten sich Kennzahl, Tabelle und Hinweis in einer 296
  // px schmalen Spalte auf mehr als die doppelte Höhe des Diagramms — die
  // Karte war unten zu zwei Dritteln leer (gemessen 16.08.: 1030 px Karte für
  // 430 px Bild). Unter dem Bild hat die Tabelle außerdem die Breite, die eine
  // fünfspaltige Zahlentafel braucht.
  const kennzahl = wachsAus != null && wachsEin != null && (
        <div className="rounded-xl bg-muted/45 p-3.5">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Von {erster.jahr} bis {letzter.jahr}
          </p>
          <p className="mt-1.5 font-display text-[34px] font-bold leading-none tracking-tight tabular-nums">
            {wachsAus > 0 ? "+" : ""}{wachsAus}&#8239;%
          </p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/80">
            sind die geplanten Ausgaben gestiegen — von {deMio(erster.aus)} auf{" "}
            {deMio(letzter.aus)}&#8239;Mio.&nbsp;€<Beleg q="plan" />. Die geplanten Einnahmen
            wuchsen um {wachsEin > 0 ? "+" : ""}{wachsEin}&nbsp;%.
          </p>
          {/* Ohne diesen Absatz liest sich „+52 %" als Zuwachs an Spielraum. */}
          <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
            Beträge in Euro des jeweiligen Jahres — Teuerung und Tarifabschlüsse sind darin
            enthalten und nicht herausgerechnet. Dass die Reihe {erster.jahr} beginnt, ist
            eine Eigenschaft unseres Datenbestands, nicht der Stadtgeschichte.
          </p>
        </div>
  );

  const tabelle = (
      <div className="rounded-xl border border-border p-3.5">
        <div className="flex items-baseline justify-between gap-2">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Alle Jahre nebeneinander
          </p>
          <button type="button" onClick={() => setTabelleGeschaltet(!tabelleOffen)}
            aria-expanded={tabelleOffen} className="text-[11.5px] font-semibold text-primary">
            {tabelleOffen ? "Tabelle ausblenden" : `Tabelle anzeigen (${alleJahre.length} Jahre)`}
          </button>
        </div>
        {tabelleOffen && (<>
          <div className={`mt-1.5 grid ${istPunkte.length
            ? "grid-cols-[auto_1fr_1fr_1fr_1fr]" : "grid-cols-[auto_1fr_1fr_1fr]"} gap-x-2 text-[11.5px] tabular-nums`}>
            {["Jahr", "Ein", "Aus", "Ergebnis", ...(istPunkte.length ? ["tatsächlich"] : [])].map((k, i) => (
              <span key={k} className={`py-1 font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground ${i ? "text-right" : ""}`}>
                {k}
              </span>
            ))}
            {alleJahre.map((jahr) => {
              const p = punkte.find((q) => q.jahr === jahr);
              const ist = istNach.get(jahr);
              const rand = "border-t border-border/60 py-1";
              return (
                <div key={jahr} className="contents">
                  <span className={`${rand} ${p ? "" : "text-signal"}`}>
                    {jahr}{bezugsJahre.has(jahr) ? "*" : ""}
                  </span>
                  <span className={`${rand} text-right`} title={p ? undefined : "nicht auslesbar"}>{p ? deMio(p.ein) : "—"}</span>
                  <span className={`${rand} text-right`}>{p ? deMio(p.aus) : "—"}</span>
                  {/* Minus in Signal-Orange (= „hier ist die Differenz"), Plus
                      neutral. Grün stünde für „gut" — eine Bewertung, die im
                      Haushalts-Bereich nirgends vorkommt. */}
                  <span className={`${rand} text-right ${(p?.saldo ?? 0) < 0 ? "text-signal" : ""}`}>
                    {p ? vorzeichen(p.saldo) : "—"}
                  </span>
                  {istPunkte.length > 0 && (
                    <span className={`${rand} text-right ${ist ? "font-semibold" : "text-muted-foreground"}`}>
                      {ist ? vorzeichen(ist.saldo) : "—"}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
            Alle Werte in Mio.&nbsp;€, ordentliches Ergebnis
            {istPunkte.length > 0 && <>. „Tatsächlich" ist das ordentliche Ergebnis aus dem
              Jahresabschluss<Beleg q="jahresabschluss" />; für die übrigen Jahre gibt es
              noch keinen</>}.
          </p>
        </>)}
      </div>
  );

  const hinweis = (
      <div className="rounded-xl border border-dashed border-border p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Was diese Grafik nicht zeigt:</strong>{" "}
          Die Linien sind Planwerte — beschlossen, bevor das Jahr begann
          <Beleg q="plan" />.{" "}
          {letzterIst ? (
            <>Für {letzterIst.jahr} liegt der Abschluss vor: geplant war{" "}
            {alsSatz(punkte.find((p) => p.jahr === letzterIst.jahr)?.saldo ?? 0)}, tatsächlich
            wurde es {alsSatz(letzterIst.saldo)}. Ein Plan rechnet vorsichtig; das Ergebnis
            weicht regelmäßig ab.</>
          ) : (
            <>Was am Jahresende tatsächlich herauskam, steht im Jahresabschluss.</>
          )}{" "}
          <Link href="/haushalt/plan-ist" className="font-semibold text-primary">
            Plan gegen Ist
          </Link>{" "}
          stellt beides Jahr für Jahr gegenüber. Investitionen laufen außerdem in einer
          eigenen Rechnung und sind hier nicht enthalten.
        </p>
        {andererBezug.length > 0 && (
          <p className="mt-2 border-t border-dashed border-border pt-2 text-[11px] leading-relaxed text-muted-foreground">
            * Für {andererBezug.map((p) => p.jahr).join(" und ")} misst der Jahresabschluss
            nicht gegen den ursprünglichen Ansatz, sondern gegen den fortgeschriebenen Plan
            ({[...new Set(andererBezug.map((p) => PLAN_ART_LABEL[p.planArt as PlanArt]))].join(", ")}).
            Die Bezugsgröße ist dort also eine andere als in den übrigen Jahren.
          </p>
        )}
      </div>
  );

  return (
    <div ref={aussen}>
      <div className={breit ? "flex items-start gap-6" : "flex flex-col gap-4"}>
        <div className={breit ? "min-w-0 flex-1" : "min-w-0"}>
          <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Einnahmen und Ausgaben · geplant
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {alleJahre[0]}–{alleJahre[alleJahre.length - 1]} · {punkte.length} von {alleJahre.length} Jahren
            </span>
          </div>
          {/* h2 wie die übrigen Blöcke der Seite (Datenstand, Quellen): Die
              Seite hat genau ein h1, darunter je Block eine zweite Ebene. */}
          <h2 className="mt-1 font-display text-[19px] font-bold leading-snug tracking-tight sm:text-[21px]">
            {titel}
          </h2>
          <p className="mt-1.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
            {letztesPlus && (
              <>Bis {letztesPlus.jahr} plante die Stadt mit einem Plus.{" "}</>
            )}
            {groessteLuecke.saldo < 0 ? (
              <>Am weitesten liegen die geplanten Ausgaben {groessteLuecke.jahr} über den
              Einnahmen — <strong>{deMio(-groessteLuecke.saldo)}&#8239;Mio.&nbsp;€</strong>{" "}
              Abstand<Beleg q="plan" />.</>
            ) : (
              <>In keinem Jahr der Reihe liegen die geplanten Ausgaben über den Einnahmen<Beleg q="plan" />.</>
            )}
            {letzterIst && (
              <> Für {letzterIst.jahr} liegt inzwischen der Jahresabschluss vor: tatsächlich
              wurde es {alsSatz(letzterIst.saldo)}<Beleg q="jahresabschluss" />.</>
            )}
          </p>

          <div ref={bildBox} className="mt-2.5">
            {/* `role="group"`, nicht `role="img"`: Ein `img` fasst seinen
                Inhalt zu einem Objekt zusammen — die Jahres-Ziele darin wären
                für die Vorlesehilfe unsichtbar. Die Gesamtbeschreibung hängt
                daneben als sr-only-Absatz. */}
            <AbleseBeschreibung id={beschreibungId}>{beschreibung}</AbleseBeschreibung>
            <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
              aria-label={titel} aria-describedby={beschreibungId}>
              {gitter.map((v) => (
                <g key={v}>
                  <line x1={X0} y1={y(v)} x2={W - 2} y2={y(v)} className="stroke-border/60" />
                  <text x={X0 - 6} y={y(v) + 3} textAnchor="end" fontSize={fs.achse}
                    className="fill-muted-foreground font-mono">{v}</text>
                </g>
              ))}
              {/* Grundlinie: Sie liegt seit dem 50er-Raster nicht mehr
                  zwangsläufig auf einer Gitterlinie, das Bild braucht aber
                  unten einen Abschluss. */}
              <line x1={X0} y1={Y0} x2={W - 2} y2={Y0} className="stroke-border" />

              {/* Lücken-Kästen */}
              {luecken.map((jahr) => {
                const xl = x(jahr) - halbeLuecke, xr = x(jahr) + halbeLuecke;
                return (
                  <g key={jahr}>
                    <foreignObject x={xl} y={YTOP - 2} width={xr - xl} height={Y0 - YTOP + 2}>
                      <div className="hh-schraffur h-full w-full opacity-60" />
                    </foreignObject>
                    <rect x={xl} y={YTOP - 2} width={xr - xl} height={Y0 - YTOP + 2} fill="none"
                      strokeDasharray="4 3" className="stroke-signal" />
                    <text x={x(jahr)} y={(Y0 + YTOP) / 2} textAnchor="middle" fontSize={10} className="fill-signal font-mono">DATEN</text>
                    <text x={x(jahr)} y={(Y0 + YTOP) / 2 + 13} textAnchor="middle" fontSize={10} className="fill-signal font-mono">FEHLEN</text>
                  </g>
                );
              })}

              {/* DIE LÜCKE ALS OBJEKT: Fläche je Segment, dazu an jedem Jahr
                  eine Strebe. Beide in Signal-Orange, in Plus- wie in
                  Minusjahren — die Farbe markiert die Differenz, sie bewertet
                  sie nicht. */}
              {segmente.map((seg, i) => (
                <path key={`fl-${i}`} d={flaeche(seg)} className="fill-signal" opacity={0.14} />
              ))}
              {punkte.map((p) => (
                <line key={`st-${p.jahr}`} x1={x(p.jahr)} y1={y(p.ein)} x2={x(p.jahr)} y2={y(p.aus)}
                  className="stroke-signal" strokeLinecap="round"
                  strokeWidth={p.jahr === groessteLuecke.jahr ? 3 : 2}
                  opacity={p.jahr === groessteLuecke.jahr ? 0.95 : 0.6} />
              ))}

              {/* Linien: Ausgaben (Schiefer) über Einnahmen (Hafenblau) */}
              {segmente.map((seg, i) => (
                <g key={i} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" fill="none">
                  <path d={pfad(seg, "aus")} style={{ stroke: "var(--hh-aus-0)" }} />
                  <path d={pfad(seg, "ein")} style={{ stroke: "var(--hh-ein-0)" }} />
                </g>
              ))}
              {/* Gepunktete Stummel zu beiden Seiten jeder Lücke */}
              {luecken.map((jahr) => {
                const vor = punkte.filter((p) => p.jahr < jahr).pop();
                const nach = punkte.find((p) => p.jahr > jahr);
                return (
                  <g key={`stu-${jahr}`} strokeWidth={2.5} strokeDasharray="1 5" strokeLinecap="round" opacity={0.45} fill="none">
                    {vor && <>
                      <path d={`M${x(vor.jahr)} ${y(vor.aus)} L${x(jahr) - halbeLuecke} ${y(vor.aus)}`} style={{ stroke: "var(--hh-aus-0)" }} />
                      <path d={`M${x(vor.jahr)} ${y(vor.ein)} L${x(jahr) - halbeLuecke} ${y(vor.ein)}`} style={{ stroke: "var(--hh-ein-0)" }} />
                    </>}
                    {nach && <>
                      <path d={`M${x(jahr) + halbeLuecke} ${y(nach.aus)} L${x(nach.jahr)} ${y(nach.aus)}`} style={{ stroke: "var(--hh-aus-0)" }} />
                      <path d={`M${x(jahr) + halbeLuecke} ${y(nach.ein)} L${x(nach.jahr)} ${y(nach.ein)}`} style={{ stroke: "var(--hh-ein-0)" }} />
                    </>}
                  </g>
                );
              })}

              {/* Was daraus wurde: Raute statt Kreis, gepunktete Strecke als
                  Abweichung vom Plan. Andere FORM, nicht nur andere Farbe —
                  so bleibt Plan und Ist auch im Graustufendruck und im
                  Dunkelmodus unterscheidbar. */}
              {istPunkte.map((ist) => {
                const p = punkte.find((q) => q.jahr === ist.jahr);
                // Fehlt der Plan des Jahres, steht an dieser Stelle der Kasten
                // „DATEN FEHLEN" — eine Raute mittendrin läse sich als
                // Widerspruch. Die Tabelle zeigt den Abschluss trotzdem: Er
                // existiert unabhängig vom Plan, und ihn zu verschweigen wäre
                // die schlechtere Lücke. (Heute hypothetisch, 2020–2026 ist
                // lückenlos.)
                if (!p) return null;
                const raute = (cy: number, farbe: string) => {
                  const r = 4.6;
                  return <path d={`M${x(ist.jahr)} ${cy - r} L${x(ist.jahr) + r} ${cy} L${x(ist.jahr)} ${cy + r} L${x(ist.jahr) - r} ${cy} Z`}
                    className="fill-card" strokeWidth={1.9} style={{ stroke: farbe }} />;
                };
                const strecke = (von: number, bis: number, farbe: string) =>
                  Math.abs(von - bis) > 5 ? (
                    <line x1={x(ist.jahr)} y1={von} x2={x(ist.jahr)} y2={bis} strokeWidth={1.4}
                      strokeDasharray="2 2.5" opacity={0.8} style={{ stroke: farbe }} />
                  ) : null;
                return (
                  <g key={`ist-${ist.jahr}`}>
                    {strecke(y(p.aus), y(ist.aus), "var(--hh-aus-0)")}
                    {strecke(y(p.ein), y(ist.ein), "var(--hh-ein-0)")}
                    {raute(y(ist.aus), "var(--hh-aus-0)")}
                    {raute(y(ist.ein), "var(--hh-ein-0)")}
                  </g>
                );
              })}

              {/* Plan-Punkte; letztes Jahr gefüllt */}
              {punkte.map((p) => (
                <g key={p.jahr}>
                  <circle cx={x(p.jahr)} cy={y(p.ein)} r={p.jahr === letzter.jahr ? 5 : 3.5}
                    className={p.jahr === letzter.jahr ? "" : "fill-card"} strokeWidth={2}
                    style={{ stroke: "var(--hh-ein-0)", fill: p.jahr === letzter.jahr ? "var(--hh-ein-0)" : undefined }} />
                  <circle cx={x(p.jahr)} cy={y(p.aus)} r={p.jahr === letzter.jahr ? 5 : 3.5}
                    className={p.jahr === letzter.jahr ? "" : "fill-card"} strokeWidth={2}
                    style={{ stroke: "var(--hh-aus-0)", fill: p.jahr === letzter.jahr ? "var(--hh-aus-0)" : undefined }} />
                </g>
              ))}
              <text x={x(letzter.jahr) + 9} y={y(letzter.ein) + 4} fontSize={fs.legende} fontWeight={600}
                className="stroke-card" {...halo} style={{ fill: "var(--hh-ein-0)" }}>ein</text>
              <text x={x(letzter.jahr) + 9} y={y(letzter.aus) + 4} fontSize={fs.legende} fontWeight={600}
                className="stroke-card" {...halo} style={{ fill: "var(--hh-aus-0)" }}>aus</text>

              {/* Der größte Abstand trägt seinen Betrag im Bild — der Sinn der
                  Fläche ist, dass man sie sieht UND liest, ohne den Blick zur
                  Achse zu senken. Nur wenn die Strebe überhaupt Platz dafür
                  hat; sonst steht der Wert weiterhin nur unter der Achse. */}
              {(() => {
                const g = groessteLuecke;
                const hoehe = Math.abs(y(g.ein) - y(g.aus));
                if (hoehe < 22) return null;
                const rechts = x(g.jahr) < (X0 + XP) / 2;
                return (
                  <text x={x(g.jahr) + (rechts ? 8 : -8)} y={(y(g.ein) + y(g.aus)) / 2 + fs.marke / 3}
                    textAnchor={rechts ? "start" : "end"} fontSize={fs.marke} fontWeight={700}
                    className="fill-signal stroke-card" {...halo}>
                    {vorzeichen(g.saldo)}
                  </text>
                );
              })()}

              {/* Jahres-Achse + Ergebniszeile (der Betrag direkt unter seiner Strebe) */}
              {alleJahre.map((jahr, idx) => {
                const p = punkte.find((q) => q.jahr === jahr);
                const fehlt = !p;
                // Schmal: nur jedes zweite Jahr plus das letzte — sonst kleben
                // die Beschriftungen aneinander, sobald die Schrift lesbar ist.
                const zeigen = !schmal || idx % 2 === 0 || idx === alleJahre.length - 1;
                if (!zeigen) return null;
                return (
                  <g key={`ax-${jahr}`} textAnchor="middle">
                    <text x={x(jahr)} y={yJahr} fontSize={fs.jahr}
                      className={fehlt ? "fill-signal font-mono" : jahr === letzter.jahr ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
                      {jahr}{bezugsJahre.has(jahr) ? "*" : ""}
                    </text>
                    <text x={x(jahr)} y={ySaldo} fontSize={fs.saldo}
                      className={fehlt || (p?.saldo ?? 0) < 0 ? "fill-signal" : "fill-muted-foreground"}
                      fontWeight={jahr === letzter.jahr ? 600 : 400}>
                      {fehlt ? "?" : vorzeichen(p!.saldo)}
                    </text>
                  </g>
                );
              })}

              {/* Zuletzt: die Ablese-Fläche. Sie liegt über allem, sonst
                  fangen Linien und Punkte den Zeiger ab. Das Fingerziel reicht
                  bis unter die Ergebniszeile — ein Streifen über die volle
                  Höhe statt eines 3-px-Punktes. */}
              <AbleseFlaeche
                stellen={stellen} steuerung={ablesen} gruppe="Jahre der Reihe"
                x={(i) => x(alleJahre[i])} xVon={X0} xBis={W - 2}
                yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={ySaldo + 4 - YTOP}
                marken={ableseMarken}
              />
            </svg>
          </div>

          <Ableseleiste className="mt-2" stelle={stellen[ablesen.aktiv]} steuerung={ablesen}
            hinweis="Mio. € · Jahr überfahren, antippen oder mit den Pfeiltasten wechseln." />

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2">
            <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
              <span className="h-[2.5px] w-[18px] rounded" style={{ background: "var(--hh-ein-0)" }} />Einnahmen
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
              <span className="h-[2.5px] w-[18px] rounded" style={{ background: "var(--hh-aus-0)" }} />Ausgaben
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
              <span className="h-3 w-[18px] rounded-[2px] bg-signal/[0.22]" />Abstand
            </span>
            {istPunkte.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
                <svg width="13" height="13" viewBox="0 0 13 13" aria-hidden="true" className="flex-none">
                  <path d="M6.5 1.4 L11.6 6.5 L6.5 11.6 L1.4 6.5 Z" className="fill-card"
                    strokeWidth={1.9} style={{ stroke: "var(--hh-aus-0)" }} />
                </svg>
                tatsächlich
              </span>
            )}
            {luecken.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
                <span className="hh-schraffur h-3 w-[18px] rounded-[2px] border border-dashed border-signal" />Datenlücke
              </span>
            )}
          </div>
          {breit && <div className="mt-3 max-w-[560px]">{tabelle}</div>}
        </div>

        <div className={breit ? "flex flex-none flex-col gap-3" : "flex flex-col gap-3"}
          style={breit ? { width: SEITE_BREITE } : undefined}>
          {kennzahl}
          {!breit && tabelle}
          {hinweis}
        </div>
      </div>
    </div>
  );
}
