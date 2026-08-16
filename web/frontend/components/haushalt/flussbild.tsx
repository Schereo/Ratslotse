"use client";

// Flussbild „Woher — ein Topf — Wohin" (Design H-18).
//
// WARUM KEIN SANKEY. Ein durchgehendes Band von „Gewerbesteuer" nach
// „Soziales" behauptet eine Zweckbindung, die es im kommunalen Haushalt nicht
// gibt: Alle Einnahmen finanzieren gemeinsam alle Ausgaben, nur wenige
// zweckgebundene Zuweisungen sind davon ausgenommen. Jede durchgezogene Linie
// wäre also erfunden — deshalb hat der Gegenbalken (H-03) bewusst gar keine.
//
// Was hier stattdessen steht: ein KOLLEKTORKNOTEN. Links laufen die
// Einnahmearten in EINEN Knoten, rechts laufen die Bereiche aus demselben
// Knoten wieder heraus. Kein Band überquert die Mitte. Dass alles durch einen
// Topf läuft, IST die Aussage des Bildes — und sie stimmt. Der Satz dazu steht
// über der Grafik, nicht in einer Fußnote.
//
// Drei Regeln, an denen sich alles andere ausrichtet:
//
//  1. EINE SKALA. Links und rechts rechnen mit demselben Euro-pro-Pixel-Wert.
//     Die Seiten haben unterschiedlich viele Bänder und damit unterschiedlich
//     viele Zwischenräume — der Faktor wird deshalb aus der Seite mit den
//     MEISTEN Zwischenräumen gebildet und für beide benutzt. Die kürzere Seite
//     bleibt kürzer, statt auf gleiche Höhe gestreckt zu werden.
//  2. DIE VIEWBOX IST SO BREIT WIE DER CONTAINER. Steht dort ein fester Wert,
//     skaliert der Browser das ganze Bild samt Schrift (bei 486 px Container
//     und viewBox 660 landen 12-px-Labels als 8,8 px auf dem Schirm). Gemessen
//     statt geraten — dieselbe Lehre wie in zeitreihe.tsx.
//  3. MOBIL WIRD UMGEBAUT, NICHT GESCHRUMPFT. Unter 620 px Containerbreite
//     gibt es keine Bänder mehr, sondern zwei gestapelte Listen mit dem Topf
//     dazwischen. Ein zusammengeschobenes Flussbild wäre unlesbar.
//  4. DAS BILD ZEIGT DAS JAHR DER SEITE — ODER KEINES. Fehlen die Daten,
//     benennt `Luecke` die Lücke und bietet das jüngste vollständige Jahr zum
//     Anklicken an. Ersatzweise ein anderes Jahr zu zeichnen wäre bequemer und
//     stünde doch unter einer Jahreszahl, die niemand gewählt hat.
//
// KEINE BEWERTUNGSFARBEN: `--hh-ein-*` und `--hh-aus-*` unterscheiden
// Kategorien, sie benoten nicht. Kein Grün, kein Rot. Signal-Orange steht wie
// überall im Bereich nur an den Ehrlichkeits-Bändern (Rücklage, Lücke).

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ArrowRight, X } from "lucide-react";
import { Segmented } from "@/components/ui";
import {
  FlussBand, FlussDaten, FlussSeite, HaushaltDaten,
  deMio, fasseKleineZusammen, flussJahre, flussbild, mio,
} from "@/lib/haushalt";
import { ausblick, type Antwort as DatenstandAntwort } from "@/components/haushalt/datenstand";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

type Seite = "herkunft" | "verwendung";

/** Ab dieser Containerbreite gibt es Bänder; darunter zwei Listen. */
const SCHWELLE_BREIT = 620;
/** Ein Band bekommt nur dann eine eigene Beschriftung, wenn es mindestens so
 *  viel der Skala trägt — sonst steht es im Sammelposten. Lesbarkeits-, keine
 *  Relevanzentscheidung: Ein 4-px-Band ist seiner Zeile nicht zuzuordnen. */
const MINDEST_ANTEIL = 0.05;

/** Die Farbrampe wird über die tatsächliche Bänderzahl VERTEILT, statt Stufe
 *  für Stufe abgeräumt zu werden — und sie endet vor ihrem hellsten Ende.
 *  Im Gegenbalken liegen die Segmente aneinander, dort trägt auch ein
 *  90-%-Helligkeitston noch; ein freistehendes Band in dieser Farbe ist auf
 *  weißer Karte schlicht nicht mehr da. Bei mehr Bändern als Stufen wiederholt
 *  sich ein Ton — das ist verkraftbar, weil jedes Band seine eigene
 *  Beschriftung trägt und die Farbe hier nichts kodiert außer „nicht dasselbe". */
const LETZTE_STUFE: Record<Seite, number> = { herkunft: 4, verwendung: 6 };

const stufe = (seite: Seite, i: number, n: number) =>
  n <= 1 ? 0 : Math.round((i / (n - 1)) * LETZTE_STUFE[seite]);

const farbe = (seite: Seite, i: number, n: number, art: FlussBand["art"]) => {
  if (art !== "posten") return undefined; // Sonderbänder tragen ihr Muster
  const s = stufe(seite, i, n);
  return seite === "herkunft" ? `var(--hh-ein-${s})` : `var(--hh-aus-${s})`;
};

/** Ein Band als Schlauch konstanter Dicke: links am Knoten, rechts am Topf.
 *  Zwei Kubiken, oben hin und unten zurück. */
function schlauch(x0: number, y0: number, x1: number, y1: number, dicke: number) {
  const mx = (x0 + x1) / 2;
  return [
    `M${x0},${y0}`,
    `C${mx},${y0} ${mx},${y1} ${x1},${y1}`,
    `L${x1},${y1 + dicke}`,
    `C${mx},${y1 + dicke} ${mx},${y0 + dicke} ${x0},${y0 + dicke}`,
    "Z",
  ].join(" ");
}

/** Beschriftungen entzerren, ohne die Reihenfolge zu ändern: erst von oben
 *  nach unten auf Mindestabstand schieben, dann den Überlauf unten wieder
 *  nach oben zurückdrücken. Ohne das kleben die Zeilen dünner Bänder
 *  aufeinander, sobald zwei kleine Posten benachbart sind. */
function entzerre(zentren: number[], mindest: number, unten: number): number[] {
  const y = [...zentren];
  for (let i = 1; i < y.length; i++) y[i] = Math.max(y[i], y[i - 1] + mindest);
  if (y.length) y[y.length - 1] = Math.min(y[y.length - 1], unten);
  for (let i = y.length - 2; i >= 0; i--) y[i] = Math.min(y[i], y[i + 1] - mindest);
  return y;
}

/** Eine Seite als gestapelte Bänder: Position und Dicke jedes Bandes. */
function stapeln(baender: FlussBand[], faktor: number, gap: number, start: number) {
  let y = start;
  return baender.map((b) => {
    const dicke = b.wert * faktor;
    const oben = y;
    y += dicke + gap;
    return { band: b, oben, dicke, mitte: oben + dicke / 2 };
  });
}

/** Die aufgeklappte Auflistung eines Sammelpostens — dieselbe Grammatik wie
 *  die Detail-Box des Gegenbalkens (Karte mit Schließen-Knopf). */
function SammelPanel({ seite, teile, skala, onClose }: {
  seite: Seite; teile: FlussBand[]; skala: number; onClose: () => void;
}) {
  const groesste = Math.max(...teile.map((t) => t.wert), 1);
  return (
    <div className="mt-3 rounded-xl border border-border bg-card p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {seite === "herkunft" ? "Die kleineren Einnahmearten" : "Die kleineren Bereiche"}
        </p>
        <button type="button" onClick={onClose} aria-label="Schließen"
          className="-mr-0.5 -mt-0.5 rounded p-0.5 text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-2 flex flex-col gap-1.5">
        {[...teile].sort((a, b) => b.wert - a.wert).map((t) => (
          <div key={t.id} className="grid grid-cols-[minmax(0,1fr)_70px_auto] items-center gap-x-2.5">
            <span className="truncate text-[12px]" title={t.lang}>{t.lang}</span>
            <span className="h-1.5 rounded-full bg-muted">
              <span className="block h-full rounded-full"
                style={{ width: `${(t.wert / groesste) * 100}%`, background: farbe(seite, 2, 4, "posten") }} />
            </span>
            <span className="whitespace-nowrap text-right text-[12px] tabular-nums">
              {deMio(mio(t.wert))}&#8239;Mio.
            </span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Zusammen {deMio(mio(teile.reduce((s, t) => s + t.wert, 0)))}&#8239;Mio.&nbsp;€ —
        {" "}{((teile.reduce((s, t) => s + t.wert, 0) / skala) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })}
        &nbsp;% von allem.
      </p>
    </div>
  );
}

/** Listen-Fassung für schmale Bildschirme: zwei Stapel, der Topf dazwischen.
 *  Bewusst dieselben Zahlen und dieselbe Bündelung wie die Bänder — nur ohne
 *  Geometrie, die auf 320 px nicht mehr lesbar wäre. */
function Listen({ bild, offen, setOffen }: {
  bild: FlussDaten;
  offen: Seite | null;
  setOffen: (s: Seite | null) => void;
}) {
  const seiten: { key: Seite; titel: string; hint: string; daten: FlussSeite }[] = [
    { key: "herkunft", titel: "Woher das Geld kommt", hint: "Einnahmearten", daten: bild.herkunft },
    { key: "verwendung", titel: "Wofür es ausgegeben wird", hint: "Bereiche", daten: bild.verwendung },
  ];
  return (
    <div>
      {seiten.map(({ key, titel, hint, daten }, si) => {
        const { gezeigt, gebuendelt } = fasseKleineZusammen(daten.baender, bild.skala, MINDEST_ANTEIL);
        return (
          <div key={key}>
            {si === 1 && <Topf bild={bild} />}
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <p className="text-[12.5px] font-semibold">{titel}</p>
              <span className="font-mono text-[10px] uppercase text-muted-foreground">
                {hint} · {deMio(mio(daten.gesamt))}&#8239;Mio.
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {gezeigt.map((b, i) => (
                <ListenZeile key={b.id} band={b} seite={key} rang={i} anzahl={gezeigt.length}
                  skala={bild.skala} sammel={b.id === "weitere"} offen={offen === key}
                  onToggle={() => setOffen(offen === key ? null : key)} />
              ))}
            </div>
            {offen === key && gebuendelt.length > 0 && (
              <SammelPanel seite={key} teile={gebuendelt} skala={bild.skala}
                onClose={() => setOffen(null)} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Eine Zeile der Listenfassung: Name, Balken auf der gemeinsamen Skala,
 *  Betrag. Der Balken misst gegen dieselbe Skala wie die Bänder — sonst
 *  erzählten Listen- und Bandfassung zwei verschiedene Geschichten. */
function ListenZeile({ band, seite, rang, anzahl, skala, sammel, offen, onToggle }: {
  band: FlussBand; seite: Seite; rang: number; anzahl: number; skala: number;
  sammel: boolean; offen: boolean; onToggle: () => void;
}) {
  const anteil = (band.wert / skala) * 100;
  const inhalt = (
    <>
      <span className="flex items-baseline justify-between gap-2.5">
        <span className={cn("min-w-0 truncate text-[12.5px]",
          sammel && "font-semibold text-primary underline decoration-dotted")} title={band.lang}>
          {band.art === "posten" ? band.label : band.lang}
        </span>
        <span className="flex-none text-[12px] tabular-nums">
          {deMio(mio(band.wert))}<span className="text-muted-foreground">&#8239;Mio.</span>
        </span>
      </span>
      <span className="mt-1 block h-2.5 w-full">
        {band.art === "posten" ? (
          <span className="block h-full rounded-[3px]"
            style={{ width: `${anteil}%`, background: farbe(seite, rang, anzahl, band.art) }} />
        ) : (
          <span className="hh-schraffur block h-full rounded-[3px] border border-dashed border-signal"
            style={{ width: `${anteil}%` }} />
        )}
      </span>
    </>
  );
  return sammel ? (
    <button type="button" onClick={onToggle} aria-expanded={offen} className="block w-full text-left">
      {inhalt}
    </button>
  ) : (
    <div>{inhalt}</div>
  );
}

/** Der Kollektorknoten als eigener Block (Listen-Fassung) — er trägt die
 *  Aussage, deshalb steht sie in ihm und nicht darunter. */
function Topf({ bild }: { bild: FlussDaten }) {
  return (
    <div className="my-3 rounded-xl border border-border bg-muted/70 px-3 py-2.5">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Alles in einer Kasse
      </p>
      <p className="mt-1 font-display text-[19px] font-bold tabular-nums tracking-tight">
        {deMio(mio(bild.skala))}<span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
      </p>
      <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
        Kein Posten links gehört zu einem Posten rechts: Alles fließt erst zusammen und wird
        dann verteilt.
      </p>
    </div>
  );
}

/** Was an der Stelle des Bildes steht, wenn für das gewählte Jahr die
 *  Einnahmearten fehlen.
 *
 *  Hier stand bis 16.08. ein ANDERES Jahr: das nächstgelegene mit
 *  Jahresabschluss, dazu ein Satz darüber. Der Handel war falsch herum — wer
 *  2026 gewählt hatte, sah eine Grafik von 2024, und die einzige Stelle, an
 *  der der Tausch stand, war eine Zeile über ihr. Wo Daten für das gewählte
 *  Jahr fehlen, sagt die Seite jetzt genau das (Entscheidung Tim, 16.08.).
 *
 *  Der Wortlaut ist mit Absicht ein „noch nicht": Die Aufschlüsselung
 *  EXISTIERT — sie steht für jedes Haushaltsjahr im Gesamtergebnishaushalt,
 *  wir haben sie nur noch nicht eingelesen. „Für Planjahre gibt es das nicht"
 *  wäre schon heute falsch und würde in dem Moment zur Unwahrheit erstarren,
 *  in dem der Bestand nachgezogen ist. Dieser Text verschwindet dann von
 *  selbst: Sobald `flussbild()` für das Jahr etwas liefert, steht hier das
 *  Bild — ohne dass jemand eine Formulierung nachziehen müsste.
 *
 *  Das jüngste vollständige Jahr ist ein ANGEBOT, keine Ersatzanzeige:
 *  gewechselt wird nur, wenn jemand darauf tippt. */
function Luecke({ jahr, letztes, aufJahr }: {
  jahr: number; letztes: number; aufJahr: (() => void) | null;
}) {
  return (
    <div>
      {/* Der Kicker bleibt: Ohne ihn stünde in der Karte eine Meldung ohne
          Gegenstand — man wüsste nicht, welcher Abschnitt hier fehlt. */}
      <p className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher, wohin — und was dazwischen liegt
      </p>
      <div className="rounded-lg border border-dashed border-border bg-muted/40 px-3.5 py-3">
        <p className="text-[13px] font-semibold leading-relaxed">
          Für {jahr} liegen uns die Einnahmearten noch nicht vor.
        </p>
        <p className="mt-1 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
          Womit die Stadt ihr Geld einnimmt, lesen wir aus ihren Haushaltsdokumenten ein — für
          dieses Jahr sind wir damit noch nicht durch. Statt ersatzweise ein anderes Jahr zu
          zeigen, steht hier lieber nichts.
        </p>
        <div className="mt-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <span className="text-[12px] text-muted-foreground">
            Vollständig haben wir sie zuletzt für {letztes}.
          </span>
          {aufJahr && (
            <button type="button" onClick={aufJahr}
              className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1 text-[12px] font-semibold text-primary shadow-sm">
              {letztes} ansehen <ArrowRight className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function Flussbild({ daten, jahr, onJahrWechsel }: {
  daten: HaushaltDaten;
  jahr: number;
  /** Der saubere Weg, das Angebot einzulösen — die Seite hält das Jahr.
   *  Optional, damit die Einbindung unverändert weiterläuft; ohne ihn greift
   *  die Pillen-Notlösung unten. */
  onJahrWechsel?: (jahr: number) => void;
}) {
  const [stand, setStand] = useState<"plan" | "ist">("ist");
  const [offen, setOffen] = useState<Seite | null>(null);
  const [tabelle, setTabelle] = useState(false);
  const musterId = useId().replace(/:/g, "");

  // Containerbreite messen — die viewBox bekommt genau diesen Wert, damit
  // eine SVG-Einheit ein echtes Pixel ist und die Schrift nicht mitskaliert.
  const box = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(880);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const pruefe = () => setBreite(Math.max(el.clientWidth, 280));
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const jahre = useMemo(() => flussJahre(daten), [daten]);
  // KEIN stiller Jahreswechsel: Das Bild zeigt das Jahr der Seite oder gar
  // keines. Fehlt es, tritt `Luecke` an seine Stelle (Begründung dort).
  const istBild = useMemo(() => flussbild(daten, jahr, "ist"), [daten, jahr]);
  const planBild = useMemo(() => flussbild(daten, jahr, "plan"), [daten, jahr]);
  const bild = stand === "ist" ? istBild ?? planBild : planBild ?? istBild;

  // `flussJahre` ist aufsteigend — das jüngste vollständige Jahr steht hinten.
  const letztes = jahre.length ? jahre[jahre.length - 1] : null;
  // Für den Ersatzfall: dasselbe noch einmal für das jüngste Jahr. Muss ein
  // Hook sein und vor jedem `return` stehen.
  const letztesIst = useMemo(
    () => (letztes == null ? null : flussbild(daten, letztes, "ist")), [daten, letztes]);
  const letztesPlan = useMemo(
    () => (letztes == null ? null : flussbild(daten, letztes, "plan")), [daten, letztes]);
  // Wann die Stadt den fehlenden Jahrgang üblicherweise vorlegt — derselbe
  // Satz, den der Datenstand am Seitenfuß baut, statt einer zweiten Fassung.
  const { data: stand_ } = useFetch<DatenstandAntwort>("/council/haushalt/datenstand");
  const ausblickText = useMemo(() => {
    const schicht = stand_?.schichten.find((x) => x.key === "jahresabschluss");
    return schicht && stand_ ? ausblick(schicht, stand_.heute).text : null;
  }, [stand_]);

  // NOTLÖSUNG, solange `onJahrWechsel` nicht verdrahtet ist: Das Jahr hält
  // `app/(app)/haushalt/page.tsx`, und die Jahres-Pillen dort tragen bereits
  // ein `data-jahr` (die Seite scrollt sich damit selbst zurecht). Wir tippen
  // also die Pille an, statt einen zweiten Jahres-Zustand aufzumachen.
  // Geprüft wird VOR dem Zeichnen: Lieber kein Knopf als ein toter Knopf.
  const [pilleDa, setPilleDa] = useState(false);
  useEffect(() => {
    if (onJahrWechsel || letztes == null) { setPilleDa(false); return; }
    setPilleDa(!!document.querySelector(`[data-jahr="${letztes}"]`));
  }, [onJahrWechsel, letztes, jahr]);

  const aufLetztes = letztes == null || (!onJahrWechsel && !pilleDa) ? null : () => {
    if (onJahrWechsel) { onJahrWechsel(letztes); return; }
    document.querySelector<HTMLElement>(`[data-jahr="${letztes}"]`)?.click();
  };

  // Ohne ein einziges Jahr mit Abschluss gibt es nichts zu sagen und nichts
  // anzubieten — dann bleibt der Block leer wie bisher (die Seite blendet ihn
  // in dem Fall ohnehin ganz aus).
  if (letztes == null) return null;

  // Fehlt das gewählte Jahr, zeigen wir das jüngste vollständige — aber die
  // Ansage steht ÜBER dem Bild, nicht als Fußnote darunter. Bis 16.08. stand
  // hier gar kein Bild; der Hinweis allein ließ die Karte leer, obwohl wir
  // etwas zu zeigen haben. Der Fehler der Fassung davor war nicht das
  // Ersatzjahr, sondern dass der Tausch versteckt war (Entscheidung Tim).
  const ersatz = !bild;
  const zeigJahr = ersatz ? letztes : jahr;
  const zeigBild = bild ?? (stand === "ist" ? letztesIst ?? letztesPlan : letztesPlan ?? letztesIst);
  if (!zeigBild) return <Luecke jahr={jahr} letztes={letztes} aufJahr={aufLetztes} />;

  const echterStand: "plan" | "ist" = zeigBild.stand;
  const beideStaende = !!istBild && !!planBild;
  const schmal = breite < SCHWELLE_BREIT;

  const saldoMio = mio(zeigBild.saldo) ?? 0;
  // Nur die Seite benennen, die WIRKLICH klemmt: „792,6 statt 792,6 bei den
  // Ausgaben" ist keine Auskunft, sondern Rauschen.
  const luecken = ([
    { seite: "Einnahmen", s: zeigBild.herkunft },
    { seite: "Ausgaben", s: zeigBild.verwendung },
  ] as const)
    .filter(({ s }) => Math.abs(s.gesamt - s.teile) > 0.02 * s.gesamt)
    .map(({ seite, s }) => ({
      seite, teile: deMio(mio(s.teile)), gesamt: deMio(mio(s.gesamt)),
    }));

  return (
    <div>
      {/* Der Hinweis steht ÜBER dem Bild und nennt beides: dass hier ein
          anderes Jahr steht, und wann das gewählte zu erwarten ist. Der
          Termin kommt aus demselben Endpunkt wie der Datenstand am Seitenfuß
          — eine zweite Fassung desselben Satzes würde auseinanderlaufen. */}
      {ersatz && (
        <div className="mb-2.5 rounded-lg border border-dashed border-border bg-muted/40 px-3.5 py-2.5">
          <p className="text-[13px] font-semibold leading-relaxed">
            Für {jahr} liegen uns die Einnahmearten noch nicht vor — hier steht {zeigJahr}.
          </p>
          <p className="mt-1 max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
            Woher das Geld kommt, steht erst im Jahresabschluss.{" "}
            {ausblickText ?? "Er wird üblicherweise im September des Folgejahres vorgelegt."}{" "}
            Bis dahin zeigt diese Grafik das jüngste Jahr, für das die Aufschlüsselung vorliegt.
          </p>
        </div>
      )}

      <div className="mb-1.5 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Woher, wohin — und was dazwischen liegt
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {echterStand === "ist" ? `Jahresabschluss ${zeigBild.jahr}` : `Haushaltsplan ${zeigBild.jahr}`} · Mio. Euro
        </span>
      </div>

      {/* Die Aussage des Bildes gehört AN das Bild, nicht in eine Fußnote. */}
      <p className="mb-2.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
        Die Stadt hat <strong>eine Kasse</strong>. Was links hereinkommt, ist nicht für einen
        bestimmten Zweck reserviert — es fließt erst zusammen, und dann entscheidet der Rat,
        wofür alles zusammen ausgegeben wird. Deshalb führt hier kein Band von links nach
        rechts durch.
      </p>

      {beideStaende && (
        <div className="mb-3 flex justify-end">
          <Segmented value={echterStand} onChange={setStand} options={[
            { value: "plan", label: "geplant" },
            { value: "ist", label: "tatsächlich" },
          ]} />
        </div>
      )}

      <div ref={box}>
        {!zeigBild.aufgeschluesselt ? (
          // Ehrlich statt gestreckt: Wenn die Einzelposten die ausgewiesene
          // Summe nicht tragen, wird nichts hochgerechnet und nichts gedehnt.
          <p className="rounded-lg border border-dashed border-signal/60 bg-card px-3 py-2.5 text-[12px] leading-relaxed text-foreground/85">
            Die Einzelposten dieses Jahres ergeben zusammen nicht die ausgewiesene Summe:{" "}
            {luecken.map((l) => `bei den ${l.seite} ${l.teile} statt ${l.gesamt}`).join(", ")}
            &#8239;Mio.&nbsp;€. Wir haben also nicht alle Zeilen des Dokuments lesen können. Ein Bild
            daraus wäre gestreckt — die Zahlen stehen deshalb nur in der Tabelle.
          </p>
        ) : schmal ? (
          <Listen bild={zeigBild} offen={offen} setOffen={setOffen} />
        ) : (
          <Baender bild={zeigBild} breite={breite} musterId={musterId}
            offen={offen} setOffen={setOffen} />
        )}
      </div>

      {offen && !schmal && zeigBild.aufgeschluesselt && (() => {
        const seite = offen === "herkunft" ? zeigBild.herkunft : zeigBild.verwendung;
        const { gebuendelt } = fasseKleineZusammen(seite.baender, zeigBild.skala, MINDEST_ANTEIL);
        return gebuendelt.length ? (
          <SammelPanel seite={offen} teile={gebuendelt} skala={zeigBild.skala}
            onClose={() => setOffen(null)} />
        ) : null;
      })()}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2.5">
        <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
          <span className="h-2.5 w-4 rounded-[2px]" style={{ background: "var(--hh-ein-0)" }} />
          Einnahmearten
        </span>
        <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
          <span className="h-2.5 w-4 rounded-[2px]" style={{ background: "var(--hh-aus-0)" }} />
          Bereiche
        </span>
        {saldoMio !== 0 && (
          <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
            <span className="hh-schraffur h-2.5 w-4 rounded-[2px] border border-dashed border-signal" />
            {saldoMio < 0 ? "aus dem Ersparten" : "bleibt übrig"}
          </span>
        )}
        <button type="button" onClick={() => setTabelle((t) => !t)}
          className="ml-auto text-[12px] font-semibold text-primary">
          {tabelle ? "Zahlen ausblenden" : "Zahlen anzeigen"}
        </button>
      </div>

      {tabelle && <Tabelle bild={zeigBild} />}

      {/* Die Skalen-Erklärung gehört nur unter ein Bild, das es auch gibt. */}
      {zeigBild.aufgeschluesselt && (
        <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
          Die Bandbreiten links und rechts liegen auf derselben Skala:{" "}
          {deMio(mio(zeigBild.summeLinks))}&#8239;Mio.&nbsp;€ hier wie dort.{" "}
          {saldoMio < 0
            ? `Weil die Stadt ${deMio(-saldoMio)} Mio. mehr ausgibt als sie einnimmt, trägt die linke Seite ein zusätzliches Band „aus dem Ersparten“ — sonst wären die Seiten nicht gleich lang.`
            : saldoMio > 0
              ? `Weil ${deMio(saldoMio)} Mio. übrig bleiben, trägt die rechte Seite ein zusätzliches Band „bleibt übrig“ — sonst wären die Seiten nicht gleich lang.`
              : "Einnahmen und Ausgaben liegen gleichauf."}
          {!zeigBild.stimmt && " Die Summenprobe geht nicht auf — die Grafik zeigt das, statt zu strecken."}
        </p>
      )}
    </div>
  );
}

/** Die Bandfassung. Sitzt in einer eigenen Komponente, weil sie das ganze
 *  Koordinatensystem aufspannt und sonst die Lesbarkeit der Hülle frisst. */
function Baender({ bild, breite, musterId, offen, setOffen }: {
  bild: FlussDaten;
  breite: number;
  musterId: string;
  offen: Seite | null;
  setOffen: (s: Seite | null) => void;
}) {
  const links = fasseKleineZusammen(bild.herkunft.baender, bild.skala, MINDEST_ANTEIL);
  const rechts = fasseKleineZusammen(bild.verwendung.baender, bild.skala, MINDEST_ANTEIL);
  const nL = links.gezeigt.length, nR = rechts.gezeigt.length;

  const W = breite;
  const LABEL = Math.round(Math.min(Math.max(W * 0.215, 126), 206));
  const KNOTEN = 8;
  const TOPF = W < 780 ? 44 : 56;
  const bandBreite = Math.max((W - 2 * LABEL - 2 * KNOTEN - TOPF) / 2, 40);
  const xKnotenL = LABEL;
  const xBandL = LABEL + KNOTEN;
  const xTopf = xBandL + bandBreite;
  const xTopfEnde = xTopf + TOPF;
  const xBandRende = xTopfEnde + bandBreite;

  const GAP = 6;
  const ZEILE = 16; // Mindestabstand zweier Beschriftungen
  const OBEN = 34, UNTEN = 30;
  const stapelHoehe = Math.max(300, 22 * Math.max(nL, nR));
  // EINE Skala: Der Faktor kommt aus der Seite mit den meisten Zwischenräumen
  // und gilt für beide. Die kürzere Seite bleibt kürzer.
  const nutz = stapelHoehe - GAP * Math.max(nL - 1, nR - 1, 0);
  const faktor = nutz / bild.skala;
  const hoeheL = links.gezeigt.reduce((s, b) => s + b.wert * faktor, 0) + GAP * (nL - 1);
  const hoeheR = rechts.gezeigt.reduce((s, b) => s + b.wert * faktor, 0) + GAP * (nR - 1);
  const hoeheTopf = bild.skala * faktor;
  const mitteY = OBEN + stapelHoehe / 2;
  const H = OBEN + stapelHoehe + UNTEN;

  const stapelL = stapeln(links.gezeigt, faktor, GAP, mitteY - hoeheL / 2);
  const stapelR = stapeln(rechts.gezeigt, faktor, GAP, mitteY - hoeheR / 2);
  const topfOben = mitteY - hoeheTopf / 2;
  // Am Topf liegen die Bänder LÜCKENLOS aneinander — das ist der Punkt: Innen
  // ist es ein Betrag, keine Sammlung von Töpfchen.
  const slotL = stapeln(links.gezeigt, faktor, 0, topfOben);
  const slotR = stapeln(rechts.gezeigt, faktor, 0, topfOben);

  const labelL = entzerre(stapelL.map((s) => s.mitte), ZEILE, OBEN + stapelHoehe);
  const labelR = entzerre(stapelR.map((s) => s.mitte), ZEILE, OBEN + stapelHoehe);

  const beschreibung = (s: typeof stapelL) =>
    s.map(({ band }) => `${band.lang} ${deMio(mio(band.wert))}`).join(", ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img"
      aria-label={
        `Woher das Geld der Stadt kommt und wofür es ausgegeben wird, ${bild.jahr}, in Mio. Euro. ` +
        `Alle Einnahmen laufen in eine gemeinsame Kasse von ${deMio(mio(bild.skala))} Mio. Euro und werden von dort verteilt; ` +
        `es gibt keine Zuordnung einzelner Einnahmen zu einzelnen Ausgaben. ` +
        `Herkunft: ${beschreibung(stapelL)}. ` +
        `Verwendung: ${beschreibung(stapelR)}.`
      }>
      <defs>
        {/* Schraffur wie .hh-schraffur, aber als SVG-Muster — eine CSS-
            Hintergrundfläche greift auf einem Pfad nicht. */}
        <pattern id={`schraffur-${musterId}`} width="6" height="6"
          patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="hsl(var(--card))" />
          <line x1="0" y1="0" x2="0" y2="6" strokeWidth="3" stroke="hsl(19 92% 55% / 0.35)" />
        </pattern>
      </defs>

      {/* Bänder zuerst, damit Knoten und Topf sauber darüber liegen. */}
      {stapelL.map((s, i) => (
        <path key={s.band.id}
          d={schlauch(xBandL, s.oben, xTopf, slotL[i].oben, s.dicke)}
          fill={s.band.art === "posten" ? farbe("herkunft", i, nL, s.band.art) : `url(#schraffur-${musterId})`}
          opacity={s.band.art === "posten" ? 0.82 : 0.9}
          stroke={s.band.art === "posten" ? "none" : "hsl(var(--signal))"}
          strokeDasharray={s.band.art === "posten" ? undefined : "4 3"}
          strokeWidth={s.band.art === "posten" ? 0 : 1} />
      ))}
      {stapelR.map((s, i) => (
        <path key={s.band.id}
          d={schlauch(xTopfEnde, slotR[i].oben, xBandRende, s.oben, s.dicke)}
          fill={s.band.art === "posten" ? farbe("verwendung", i, nR, s.band.art) : `url(#schraffur-${musterId})`}
          opacity={s.band.art === "posten" ? 0.82 : 0.9}
          stroke={s.band.art === "posten" ? "none" : "hsl(var(--signal))"}
          strokeDasharray={s.band.art === "posten" ? undefined : "4 3"}
          strokeWidth={s.band.art === "posten" ? 0 : 1} />
      ))}

      {/* Knoten außen: die Kante, an der ein Posten anfasst. */}
      {stapelL.map((s, i) => (
        <rect key={s.band.id} x={xKnotenL} y={s.oben} width={KNOTEN} height={Math.max(s.dicke, 1.5)}
          rx={2} fill={s.band.art === "posten" ? farbe("herkunft", i, nL, s.band.art) : "hsl(var(--signal))"} />
      ))}
      {stapelR.map((s, i) => (
        <rect key={s.band.id} x={xBandRende} y={s.oben} width={KNOTEN} height={Math.max(s.dicke, 1.5)}
          rx={2} fill={s.band.art === "posten" ? farbe("verwendung", i, nR, s.band.art) : "hsl(var(--signal))"} />
      ))}

      {/* Der Kollektorknoten: eine geschlossene Fläche, kein Durchgang. */}
      <rect x={xTopf} y={topfOben} width={TOPF} height={hoeheTopf} rx={6}
        className="fill-muted stroke-border" strokeWidth={1} />
      <text x={xTopf + TOPF / 2} y={topfOben - 12} textAnchor="middle" fontSize={10.5}
        className="fill-muted-foreground font-mono" letterSpacing="0.09em">
        EINE KASSE
      </text>
      <text x={xTopf + TOPF / 2} y={topfOben + hoeheTopf + 17} textAnchor="middle"
        fontSize={13} fontWeight={700} className="fill-foreground">
        {deMio(mio(bild.skala))}
      </text>
      <text x={xTopf + TOPF / 2} y={topfOben + hoeheTopf + 29} textAnchor="middle"
        fontSize={10} className="fill-muted-foreground font-mono">
        MIO. EURO
      </text>
      <text x={xTopf + TOPF / 2} y={topfOben + hoeheTopf / 2} textAnchor="middle"
        fontSize={11.5} fontWeight={600} className="fill-muted-foreground"
        transform={`rotate(-90 ${xTopf + TOPF / 2} ${topfOben + hoeheTopf / 2})`}>
        Alles Geld der Stadt
      </text>

      {/* Beschriftungen als HTML im foreignObject: echtes Kürzen mit Auslassung
          statt abgeschnittener Ziffern (eine gekappte 169,2 liest sich als 16). */}
      {stapelL.map((s, i) => (
        <Beschriftung key={s.band.id} x={0} y={labelL[i]} breite={LABEL - 10} rechtsbuendig
          band={s.band} istSammel={s.band.id === "weitere"} offen={offen === "herkunft"}
          onToggle={() => setOffen(offen === "herkunft" ? null : "herkunft")} />
      ))}
      {stapelR.map((s, i) => (
        <Beschriftung key={s.band.id} x={xBandRende + KNOTEN + 10} y={labelR[i]} breite={LABEL - 10}
          band={s.band} istSammel={s.band.id === "weitere"} offen={offen === "verwendung"}
          onToggle={() => setOffen(offen === "verwendung" ? null : "verwendung")} />
      ))}

      <text x={0} y={16} fontSize={11.5} fontWeight={600} className="fill-foreground">Woher</text>
      <text x={W} y={16} textAnchor="end" fontSize={11.5} fontWeight={600} className="fill-foreground">Wohin</text>
    </svg>
  );
}

function Beschriftung({ x, y, breite, band, rechtsbuendig = false, istSammel, offen, onToggle }: {
  x: number; y: number; breite: number; band: FlussBand;
  rechtsbuendig?: boolean; istSammel: boolean; offen: boolean; onToggle: () => void;
}) {
  const inhalt = (
    <>
      <span className={cn("min-w-0 truncate", istSammel && "font-semibold text-primary underline decoration-dotted")}
        title={band.lang}>
        {band.art === "posten" ? band.label : band.lang}
      </span>
      <span className="flex-none tabular-nums text-muted-foreground">{deMio(mio(band.wert))}</span>
    </>
  );
  return (
    <foreignObject x={x} y={y - 9} width={breite} height={19}>
      {istSammel ? (
        <button type="button" onClick={onToggle} aria-expanded={offen}
          className={cn("flex w-full items-baseline gap-1.5 text-[11.5px] leading-[19px]",
            rechtsbuendig && "justify-end")}>
          {inhalt}
        </button>
      ) : (
        <div className={cn("flex w-full items-baseline gap-1.5 text-[11.5px] leading-[19px]",
          rechtsbuendig && "justify-end")}>
          {inhalt}
        </div>
      )}
    </foreignObject>
  );
}

/** Nicht-Chart-Entsprechung: alle Posten, ungebündelt, mit Anteil — und die
 *  Summenprobe als eigene Zeile, nicht als Behauptung im Fließtext. */
function Tabelle({ bild }: { bild: FlussDaten }) {
  const zeilen = (baender: FlussBand[]) =>
    [...baender].sort((a, b) => b.wert - a.wert).map((b) => (
      <tr key={b.id} className="border-t border-border/60">
        <td className="py-1 pr-2">{b.lang}</td>
        <td className="py-1 pr-2 text-right">{deMio(mio(b.wert))}</td>
        <td className="py-1 text-right text-muted-foreground">
          {((b.wert / bild.skala) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%
        </td>
      </tr>
    ));
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[380px] text-[12px] tabular-nums">
        <thead>
          <tr className="text-left font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            <th className="py-1 pr-2 font-medium">Posten</th>
            <th className="py-1 pr-2 text-right font-medium">Mio. €</th>
            <th className="py-1 text-right font-medium">Anteil</th>
          </tr>
        </thead>
        <tbody>
          <tr><td colSpan={3} className="pt-2 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            Woher — {bild.stand === "ist" ? "tatsächlich" : "geplant"} {bild.jahr}
          </td></tr>
          {zeilen(bild.herkunft.baender)}
          <tr className="border-t-2 border-border font-semibold">
            <td className="py-1 pr-2">Summe links</td>
            <td className="py-1 pr-2 text-right">{deMio(mio(bild.summeLinks))}</td>
            <td className="py-1 text-right">100&nbsp;%</td>
          </tr>
          <tr><td colSpan={3} className="pt-3 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            Wohin — {bild.stand === "ist" ? "tatsächlich" : "geplant"} {bild.jahr}
          </td></tr>
          {zeilen(bild.verwendung.baender)}
          <tr className="border-t-2 border-border font-semibold">
            <td className="py-1 pr-2">Summe rechts</td>
            <td className="py-1 pr-2 text-right">{deMio(mio(bild.summeRechts))}</td>
            <td className="py-1 text-right">100&nbsp;%</td>
          </tr>
        </tbody>
      </table>
      <p className={cn("mt-2 text-[11px] leading-relaxed",
        bild.stimmt ? "text-muted-foreground" : "text-signal")}>
        {bild.stimmt
          ? `Summenprobe: beide Seiten ${deMio(mio(bild.summeLinks))} Mio. € — dieselbe Skala, nichts gestreckt.`
          : `Summenprobe: links ${deMio(mio(bild.summeLinks))}, rechts ${deMio(mio(bild.summeRechts))} Mio. € — die Seiten gehen nicht auf.`}
      </p>
    </div>
  );
}
