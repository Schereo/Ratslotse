"use client";

// Flussbild „Woher — ein Topf — Wohin" (Design H-18) — der Haushalts-Adapter.
//
// GEZEICHNET wird seit dem Grafik-Baukasten in
// `components/grafik/flussbild.tsx` (GB-07): Dort wohnen Bänder, Listen-
// Fassung, Kollektorknoten, Sammelposten und die Regel „bewusst kein Sankey —
// alle Kurven enden im EINEN Topf". HIER wohnt alles, was den HAUSHALT
// betrifft: welches Jahr gezeigt wird, der Plan/Ist-Umschalter, die
// Summenprobe, die Tabelle und die Ehrlichkeits-Hinweise.
//
// Zwei Regeln dieser Hülle, beide älter als der Baukasten:
//
//  1. DAS BILD ZEIGT DAS JAHR DER SEITE — ODER SAGT, WAS ES ZEIGT. Fehlt das
//     gewählte Jahr, steht das jüngste vollständige da, aber die Ansage steht
//     ÜBER dem Bild, nicht in einer Fußnote (Entscheidung Tim, 16.08.): Der
//     Fehler der Fassung davor war nicht das Ersatzjahr, sondern dass der
//     Tausch versteckt war. Dieser Hinweis-Banner BLEIBT beim Baukasten-Umzug
//     unverändert erhalten.
//  2. EHRLICH STATT GESTRECKT: Ergeben die Einzelposten die ausgewiesene
//     Summe nicht (`aufgeschluesselt` falsch), wird NICHT gezeichnet — die
//     Zahlen stehen dann nur in der Tabelle.

import { useEffect, useMemo, useState } from "react";
import { ArrowRight } from "lucide-react";
import { Segmented } from "@/components/ui";
import {
  Flussbild as FlussbildGrafik, FlussPosten, FlussSeiteDaten,
  fasseKleineZusammen,
} from "@/components/grafik/flussbild";
import {
  EinnahmeartenPlan, FlussBand, FlussDaten, HaushaltAuswahl,
  deMio, einnahmearten, flussJahre, flussbild, mio,
} from "@/lib/haushalt";
import { buendelGrenze, rampenText } from "@/components/grafik/kachelflaeche";
import { Treemap, type TreemapKnoten } from "@/components/grafik/treemap";
import { Beleg } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { ausblick, type Antwort as DatenstandAntwort } from "@/components/haushalt/datenstand";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

/** Ein Band bekommt nur dann eine eigene Beschriftung, wenn es mindestens so
 *  viel der Skala trägt — sonst steht es im Sammelposten. Lesbarkeits-, keine
 *  Relevanzentscheidung: Ein 4-px-Band ist seiner Zeile nicht zuzuordnen. */
const MINDEST_ANTEIL = 0.05;

/** Letzte Stufe der Einnahmen-Rampe (`--hh-ein-0` … `--hh-ein-6`). Wer mehr
 *  Posten hat als Stufen, teilt sich die letzte — die kleinsten liegen dann
 *  farblich beieinander, was sie auch der Sache nach sind. */
const EIN_STUFEN = 6;

/** Die Haushalts-Bänder in den Baukasten-Vertrag übersetzen: `rest` und
 *  `ausgleich` sind beide Differenz-Bänder (Schraffur + Signal-Kante). */
function alsPosten(b: FlussBand): FlussPosten {
  return {
    id: b.id, label: b.label, lang: b.lang, wert: b.wert,
    art: b.art === "posten" ? "posten" : "difference",
  };
}

/** Was an der Stelle des Bildes steht, wenn für das gewählte Jahr kein
 *  vollständiges Flussbild möglich ist: **die eine Seite, die es gibt.**
 *
 *  Hier stand bis 16.08. ein ANDERES Jahr: das nächstgelegene mit
 *  Jahresabschluss, dazu ein Satz darüber. Der Handel war falsch herum — wer
 *  2026 gewählt hatte, sah eine Grafik von 2024, und die einzige Stelle, an
 *  der der Tausch stand, war eine Zeile über ihr. Wo Daten für das gewählte
 *  Jahr fehlen, sagt die Seite jetzt genau das (Entscheidung Tim, 16.08.).
 *
 *  Bis 19.08. stand hier „Für {year} liegen uns die Einnahmearten noch nicht
 *  vor" — seit #530 unwahr, sie SIND eingelesen. Seit 20.08. steht deshalb
 *  nicht mehr eine Fehlanzeige da, sondern die Herkunftsseite selbst.
 *
 *  **Warum trotzdem kein Flussbild.** Es braucht beide Seiten aus EINER
 *  Quelle. Der Gesamtergebnishaushalt führt keine Teilhaushalte (in allen acht
 *  Dokumenten kommt „THH" kein einziges Mal vor), und `council_haushalt` steht
 *  in einem anderen Stand — Entwurf gegen Beschluss. Der Abstand wird nicht
 *  behauptet, sondern gerechnet und hingeschrieben (`einnahmearten().tafel`):
 *  Für 2026 sind es 24,3 Mio. €, das Fünfhundertfache der Toleranz, mit der
 *  das Bild rechnet. Ein Bild aus beiden sähe man das nicht an.
 *
 *  Und genau deshalb steht der Abstand DA: Auf derselben Seite nennt die
 *  Anzeigetafel eine andere Ertragssumme. Zwei Zahlen nebeneinander, die
 *  dasselbe zu meinen scheinen, sind schlimmer als eine Lücke — wer sie zeigt,
 *  muss sagen, dass es zwei sind.
 *
 *  Das jüngste vollständige Jahr bleibt ein ANGEBOT, keine Ersatzanzeige:
 *  gewechselt wird nur, wenn jemand darauf tippt. */
/** Die zehn, elf Ertragsarten als Kachelfläche (GB-08).
 *
 *  Hier stand bis 24.08. eine <RanglisteSchiene>: zehn Balken auf einer
 *  Schiene von null bis zum größten Posten. Die beantwortet „wer ist größer
 *  als wer" — nicht die Frage, die über diesem Bild steht. „Woher das Geld
 *  kommen soll" ist eine Frage nach ANTEILEN an einer Summe, und die Schiene
 *  misst am Maximum, nicht an der Summe: Steuern nahmen die volle Breite ein,
 *  weil sie der größte Posten sind, nicht weil sie die halben Erträge sind.
 *  Dass sie beides sind (49,3 %), stand nirgends.
 *
 *  Die Kachelfläche misst an der Summe — 1 mm² ist überall gleich viel Geld,
 *  und die Kacheln füllen sie restlos.
 *
 *  GEBÜNDELT WIRD GEMESSEN, NICHT GERATEN (Tims Entscheidung 24.08.: ein
 *  Sammelposten, wenn er die Fläche besser ablesbar macht — er tut es). Die
 *  erste Fassung zeigte alle zehn Posten einzeln; „Eigenleistungen" (0,23 %)
 *  war damit an JEDER Breite ein unbeschrifteter Farbfleck. `buendelGrenze`
 *  rechnet den Schnitt aus der Geometrie: so viele eigene Kacheln wie möglich,
 *  aber jede — die Rest-Kachel eingeschlossen — trägt über die ganze
 *  Breitenspanne ihre Beschriftung. Für 2026 heißt das sieben Kacheln plus
 *  ein Sammelposten aus dreien.
 *
 *  Die gebündelten Posten verschwinden dabei NICHT: Ihre Namen stehen mit
 *  Betrag in `restZusatz` — als Legenden-Zeile (also auch im Ausdruck und im
 *  Screenshot), in der Ablesezeile beim Überfahren des Sammelpostens und in
 *  der Mobil-Zeile unter der Rangliste. Weglassen heißt „hinter einen
 *  Auslöser", nie ersatzlos (Baukasten-Regel, README).
 *
 *  FARBE = RANG, aus der Einnahmen-Rampe (`--hh-ein-*`, dunkel = groß) — die
 *  Reihenfolge, in der auch der Gegenbalken derselben Seite seine Segmente
 *  einfärbt. Keine zweite Farbwelt und keine Bewertungsfarben; die Rampe hat
 *  sieben Stufen, die kleinsten Posten teilen sich also die letzte.
 *
 *  TEXTFARBE nach `rampenText` — die Rampe endet auf einer Karte dicht an
 *  deren Grund, weißer Text stünde dort auf fast Weiß. Die Messung und die
 *  Grenze wohnen in `components/grafik/kachelflaeche.ts`, damit die
 *  Investitionen-Kachelfläche dieselbe Regel fährt. */
export function Herkunftskacheln({ arten }: { arten: EinnahmeartenPlan }) {
  // Ein Schlüssel für Fläche und Legende: `gruppe` ist hier die Ertragsart
  // selbst — jede Kachel ist ihre eigene Gruppe, die Legende wird damit zum
  // Verzeichnis aller Posten (auch der, die für eine Beschriftung zu klein
  // sind).
  const knoten: TreemapKnoten[] = useMemo(
    () => arten.arten.map((a) => ({
      key: String(a.nr),
      name: a.label,
      wert: a.amount,
      gruppe: a.label,
      zusatz: a.label === a.lang ? undefined : a.lang,
    })),
    [arten]);

  // `arten.arten` ist absteigend sortiert — der Rang IST die Rampenstufe.
  const stufe = useMemo(() => {
    const zu = new Map<string, number>();
    arten.arten.forEach((a, i) => zu.set(a.label, Math.min(i, EIN_STUFEN)));
    return (gruppe: string) => zu.get(gruppe) ?? EIN_STUFEN;
  }, [arten]);

  // Der gemessene Schnitt (s. Kopfkommentar) und die Aufzählung dessen, was
  // er bündelt — einmal „Mio. €" am Ende, die Legende nennt die Einheit ohnehin.
  const grenze = useMemo(
    () => buendelGrenze(arten.arten.map((a) => a.amount)), [arten]);
  const gebuendelt = arten.arten.slice(grenze);
  const restZusatz = gebuendelt.length
    ? gebuendelt.map((a) => `${a.label} ${deMio(a.amount / 1e6)}`).join(" · ")
      + "\u00a0Mio.\u00a0€"
    : undefined;

  return (
      <Treemap
      knoten={knoten}
      buendelnAb={grenze}
      farbe={(g) => `var(--hh-ein-${stufe(g)})`}
      textFarbe={(g) => rampenText("ein", stufe(g))}
      nomen="Ertragsarten"
      flaecheLabel="Fläche = Anteil an den Erträgen"
      anteil
      restZusatz={restZusatz}
      restHinweis="Antippen zeigt die einzelnen Posten."
      beleg={<Beleg q="ergebnishaushalt" />}
    />
  );
}

function NurHerkunft({ arten, letztes, aufJahr }: {
  arten: EinnahmeartenPlan; letztes: number | null; aufJahr: (() => void) | null;
}) {
  return (
    <div>
      {/* Der Kicker sagt, was hier steht — und was NICHT: Über dem vollen Bild
          heißt er „Woher, wohin — und was dazwischen liegt". Denselben Kicker
          über einer halben Grafik zu setzen, verspräche die Ausgabenseite. */}
      <p className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Geplante Einnahmearten
      </p>

      <Herkunftskacheln arten={arten} />

      <div className="mt-3 rounded-lg border border-dashed border-border bg-muted/40 px-3.5 py-3">
        <p className="text-[13px] font-semibold leading-relaxed">
          Für {arten.year} können wir bisher nur die Einnahmeseite zeigen.
        </p>
        <p className="mt-1 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
          Die Einnahmearten stammen aus Anlage 005 des von der Verwaltung eingebrachten
          Haushaltsplans {arten.planJahrgang}. Die Ausgaben nach Bereichen liegen nur aus
          dem später beschlossenen Plan vor. Ein gemeinsames Bild würde damit Entwurf und
          Beschluss vermischen. Deshalb zeigen wir die Ausgabenseite für dieses Jahr nicht.
        </p>
        {/* Der Abstand zur Anzeigetafel derselben Seite. Gerechnet, nicht
            behauptet — und nur gezeigt, wenn es ihn gibt: Bei einem Jahrgang
            ohne Tafel-Zeile stünde sonst „0 Mio. € Abstand" als Aussage da. */}
        {arten.tafel && Math.abs(arten.tafel.abstand) >= 100_000 && (
          <p className="mt-1.5 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
            Die Einnahmeposten des Entwurfs ergeben zusammen
            {" "}{deMio(arten.gesamt / 1e6)}&#8239;Mio.&nbsp;€. In der Anzeigetafel oben stehen
            {" "}{deMio(arten.tafel.revenues / 1e6)}&#8239;Mio.&nbsp;€ aus dem beschlossenen
            Plan. Der Unterschied von {deMio(Math.abs(arten.tafel.abstand) / 1e6)}&#8239;Mio.&nbsp;€
            entsteht, weil beide Zahlen aus verschiedenen Fassungen stammen.
          </p>
        )}
        {letztes != null && (
          <div className="mt-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
            <span className="text-[12px] text-muted-foreground">
              Einnahmen und Ausgaben aus demselben Datenstand liegen zuletzt für {letztes} vor.
            </span>
            {aufJahr && (
              <button type="button" onClick={aufJahr}
                className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1 text-[12px] font-semibold text-primary shadow-sm">
                {letztes} ansehen <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Der Rückfall, wenn es auch die Herkunftsseite nicht gibt — etwa auf einem
 *  Bestand, in dem der Gesamtergebnishaushalt noch nicht eingelesen ist. */
function Luecke({ year, letztes, aufJahr }: {
  year: number; letztes: number | null; aufJahr: (() => void) | null;
}) {
  return (
    <div>
      <p className="mb-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher, wohin — und was dazwischen liegt
      </p>
      <div className="rounded-lg border border-dashed border-border bg-muted/40 px-3.5 py-3">
        <p className="text-[13px] font-semibold leading-relaxed">
          Für {year} können wir den Geldfluss nicht zeichnen.
        </p>
        <p className="mt-1 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
          Für dieses Jahr fehlen die Einnahmearten. Wir zeigen deshalb keine Grafik mit
          Zahlen aus einem anderen Jahr.
        </p>
        {letztes != null && (
          <div className="mt-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
            <span className="text-[12px] text-muted-foreground">
              Vollständige Daten liegen zuletzt für {letztes} vor.
            </span>
            {aufJahr && (
              <button type="button" onClick={aufJahr}
                className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1 text-[12px] font-semibold text-primary shadow-sm">
                {letztes} ansehen <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Welche Quelle dieser Block für ein Jahr WIRKLICH zitiert.
 *
 *  Dieselbe Sorgfalt wie beim Kassenzettel (`kassenzettelQuellen`), und aus
 *  demselben Grund: Die Seite meldet ihre Quellen vorab an, und die
 *  Nummerierung im Verzeichnis läuft über genau diese Liste. Meldet sie eine
 *  Quelle an, die hier gar nicht zitiert wird, steht im Verzeichnis ein Beleg
 *  für nichts; meldet sie eine zu wenig an, verschluckt `<Beleg>` den Chip
 *  stillschweigend (`quelle.tsx`: „lieber keinen Chip als eine falsche
 *  Nummer") — die Zahl stünde dann ohne Beleg da, auf einer Seite, deren
 *  ganzer Anspruch das Gegenteil ist.
 *
 *  Die Fallunterscheidung ist dieselbe wie im Render-Zweig unten und muss es
 *  bleiben: Wo ein Flussbild steht, zitiert es den Jahresabschluss; wo für ein
 *  Planjahr die Herkunftsseite steht, den Gesamtergebnishaushalt. */
export function flussbildQuellen(
  daten: HaushaltAuswahl<"ergebnisrechnung" | "ergebnishaushalt" | "jahre">,
  year: number,
): QuellenSchluessel[] {
  if (!flussJahre(daten).length) return [];
  const bild = flussbild(daten, year, "ist") ?? flussbild(daten, year, "plan");
  if (!bild && einnahmearten(daten, year)) return ["ergebnishaushalt"];
  return ["jahresabschluss"];
}

export function Flussbild({ daten, year, onJahrWechsel }: {
  daten: HaushaltAuswahl<"ergebnisrechnung" | "ergebnishaushalt" | "jahre">;
  year: number;
  /** Der saubere Weg, das Angebot einzulösen — die Seite hält das Jahr.
   *  Optional, damit die Einbindung unverändert weiterläuft; ohne ihn greift
   *  die Pillen-Notlösung unten. */
  onJahrWechsel?: (year: number) => void;
}) {
  const [stand, setStand] = useState<"plan" | "ist">("ist");
  const [tabelle, setTabelle] = useState(false);

  const jahre = useMemo(() => flussJahre(daten), [daten]);
  // KEIN stiller Jahreswechsel: Das Bild zeigt das Jahr der Seite oder gar
  // keines. Fehlt es, tritt `Luecke` an seine Stelle (Begründung dort).
  const istBild = useMemo(() => flussbild(daten, year, "ist"), [daten, year]);
  const planBild = useMemo(() => flussbild(daten, year, "plan"), [daten, year]);
  const bild = stand === "ist" ? istBild ?? planBild : planBild ?? istBild;

  // `flussJahre` ist aufsteigend — das jüngste vollständige Jahr steht hinten.
  const letztes = jahre.length ? jahre[jahre.length - 1] : null;
  // Für den Ersatzfall: dasselbe noch einmal für das jüngste Jahr. Muss ein
  // Hook sein und vor jedem `return` stehen.
  const letztesIst = useMemo(
    () => (letztes == null ? null : flussbild(daten, letztes, "ist")), [daten, letztes]);
  const letztesPlan = useMemo(
    () => (letztes == null ? null : flussbild(daten, letztes, "plan")), [daten, letztes]);
  // Die Herkunftsseite des GEWÄHLTEN Jahres — für Planjahre die einzige, die
  // es gibt. Muss ein Hook sein und vor jedem `return` stehen.
  const nurHerkunft = useMemo(() => einnahmearten(daten, year), [daten, year]);
  // Wann die Stadt den fehlenden Jahrgang üblicherweise vorlegt — derselbe
  // Satz, den der Datenstand am Seitenfuß baut, statt einer zweiten Fassung.
  const { data: stand_ } = useFetch<DatenstandAntwort>("/council/haushalt/datenstand");
  const ausblickText = useMemo(() => {
    const schicht = stand_?.schichten.find((x) => x.key === "jahresabschluss");
    return schicht && stand_ ? ausblick(schicht, stand_.heute).text : null;
  }, [stand_]);

  // NOTLÖSUNG, solange `onJahrWechsel` nicht verdrahtet ist: Das Jahr hält
  // `app/(app)/haushalt/page.tsx`, und die Jahres-Pillen dort tragen bereits
  // ein `data-year` (die Seite scrollt sich damit selbst zurecht). Wir tippen
  // also die Pille an, statt einen zweiten Jahres-Zustand aufzumachen.
  // Geprüft wird VOR dem Zeichnen: Lieber kein Knopf als ein toter Knopf.
  const [pilleDa, setPilleDa] = useState(false);
  useEffect(() => {
    if (onJahrWechsel || letztes == null) { setPilleDa(false); return; }
    setPilleDa(!!document.querySelector(`[data-year="${letztes}"]`));
  }, [onJahrWechsel, letztes, year]);

  const aufLetztes = letztes == null || (!onJahrWechsel && !pilleDa) ? null : () => {
    if (onJahrWechsel) { onJahrWechsel(letztes); return; }
    document.querySelector<HTMLElement>(`[data-year="${letztes}"]`)?.click();
  };

  // Ohne ein einziges Jahr mit Abschluss gibt es nichts zu sagen und nichts
  // anzubieten — dann bleibt der Block leer wie bisher (die Seite blendet ihn
  // in dem Fall ohnehin ganz aus).
  if (letztes == null) return null;

  // Hat das GEWÄHLTE Jahr eigene Zahlen — wenn auch nur für eine Seite —, dann
  // gelten die, und das Ersatzjahr wird zum Angebot.
  //
  // Das schränkt die Regel vom 16.08. ein, und zwar aus ihrem eigenen Grund.
  // Sie lautete: „Fehlt das gewählte Jahr, zeigen wir das jüngste vollständige,
  // aber die Ansage steht ÜBER dem Bild" — beschlossen, weil der Hinweis allein
  // die Karte leer ließ, „obwohl wir etwas zu zeigen haben". Für Planjahre haben
  // wir seit #530 etwas Besseres zu zeigen als ein fremdes Jahr: die echten
  // Ertragsarten des gewählten. Damit ist die Prämisse jener Entscheidung für
  // diesen Fall weggefallen, nicht die Entscheidung selbst — wo es auch die
  // Herkunftsseite nicht gibt, bleibt es beim angesagten Ersatzjahr.
  if (!bild && nurHerkunft) {
    return <NurHerkunft arten={nurHerkunft} letztes={letztes} aufJahr={aufLetztes} />;
  }

  const ersatz = !bild;
  const zeigJahr = ersatz ? letztes : year;
  const zeigBild = bild ?? (stand === "ist" ? letztesIst ?? letztesPlan : letztesPlan ?? letztesIst);
  if (!zeigBild) return <Luecke year={year} letztes={letztes} aufJahr={aufLetztes} />;

  const echterStand: "plan" | "ist" = zeigBild.stand;
  const beideStaende = !!istBild && !!planBild;

  const saldoMio = mio(zeigBild.balance) ?? 0;
  // Nur die Seite benennen, die WIRKLICH klemmt: „792,6 statt 792,6 bei den
  // Ausgaben" ist keine Auskunft, sondern Rauschen.
  const luecken = ([
    { page: "Einnahmen", s: zeigBild.herkunft },
    { page: "Ausgaben", s: zeigBild.verwendung },
  ] as const)
    .filter(({ s }) => Math.abs(s.gesamt - s.teile) > 0.02 * s.gesamt)
    .map(({ page, s }) => ({
      page, teile: deMio(mio(s.teile)), gesamt: deMio(mio(s.gesamt)),
    }));

  const format = (w: number) => deMio(mio(w));
  const links: FlussSeiteDaten = {
    titel: "Woher das Geld kommt", kurz: "Woher", hint: "Einnahmearten",
    sammelTitel: "Die kleineren Einnahmearten",
    baender: zeigBild.herkunft.baender.map(alsPosten),
    gesamt: zeigBild.herkunft.gesamt,
  };
  const rechts: FlussSeiteDaten = {
    titel: "Wofür es ausgegeben wird", kurz: "Wohin", hint: "Bereiche",
    sammelTitel: "Die kleineren Bereiche",
    baender: zeigBild.verwendung.baender.map(alsPosten),
    gesamt: zeigBild.verwendung.gesamt,
  };
  const beschreibe = (s: FlussSeiteDaten) =>
    fasseKleineZusammen(s.baender, zeigBild.skala, MINDEST_ANTEIL)
      .gezeigt.map((b) => `${b.lang} ${format(b.wert)}`).join(", ");

  return (
    <div>
      {/* Der Hinweis steht ÜBER dem Bild und nennt beides: dass hier ein
          anderes Jahr steht, und wann das gewählte zu erwarten ist. Der
          Termin kommt aus demselben Endpunkt wie der Datenstand am Seitenfuß
          — eine zweite Fassung desselben Satzes würde auseinanderlaufen. */}
      {ersatz && (
        <div className="mb-2.5 rounded-lg border border-dashed border-border bg-muted/40 px-3.5 py-2.5">
          <p className="text-[13px] font-semibold leading-relaxed">
            Für {year} fehlen die Einnahmearten. Die Grafik zeigt deshalb {zeigJahr}.
          </p>
          <p className="mt-1 max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
            Die vollständige Aufschlüsselung steht erst im Jahresabschluss.{" "}
            {ausblickText ?? "Er wird üblicherweise im September des Folgejahres vorgelegt."}{" "}
            Bis dahin verwenden wir das jüngste Jahr mit vollständigen Daten.
          </p>
        </div>
      )}

      <div className="mb-1.5 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Woher das Geld kommt und wofür es eingeplant ist
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {echterStand === "ist" ? `Jahresabschluss ${zeigBild.year}` : `Haushaltsplan ${zeigBild.year}`} · Mio. Euro
        </span>
      </div>

      {/* Die Aussage des Bildes gehört AN das Bild, nicht in eine Fußnote. */}
      <p className="mb-2.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
        Viele Einnahmen sind nicht für eine bestimmte Aufgabe reserviert. Sie fließen in
        den Gesamthaushalt, und der Rat entscheidet im Rahmen der gesetzlichen Pflichten,
        wofür das Geld eingesetzt wird. Deshalb verbindet die Grafik keine einzelne
        Einnahmeart mit einem bestimmten Ausgabenbereich.
      </p>

      {beideStaende && (
        <div className="mb-3 flex justify-end">
          <Segmented value={echterStand} onChange={setStand} options={[
            { value: "plan", label: "geplant" },
            { value: "ist", label: "tatsächlich" },
          ]} />
        </div>
      )}

      {!zeigBild.aufgeschluesselt ? (
        // Ehrlich statt gestreckt: Wenn die Einzelposten die ausgewiesene
        // Summe nicht tragen, wird nichts hochgerechnet und nichts gedehnt.
        <p className="rounded-lg border border-dashed border-signal/60 bg-card px-3 py-2.5 text-[12px] leading-relaxed text-foreground/85">
          Die ausgelesenen Einzelposten ergeben nicht die ausgewiesene Gesamtsumme:{" "}
          {luecken.map((l) => `bei den ${l.page} ${l.teile} statt ${l.gesamt}`).join(", ")}
          &#8239;Mio.&nbsp;€. Damit fehlen Teile der Datengrundlage. Eine proportionale Grafik wäre
          irreführend; die verfügbaren Zahlen stehen deshalb nur in der Tabelle.
        </p>
      ) : (
        <FlussbildGrafik
          links={links}
          rechts={rechts}
          topf={{
            kurz: "Gesamthaushalt",
            lang: "Alle Einnahmen im Gesamthaushalt",
            wert: zeigBild.skala,
            satz: "Gemeinsamer Finanzierungsrahmen",
            note: "Einzelne Einnahmearten sind nicht direkt bestimmten Ausgabenbereichen "
              + "zugeordnet.",
          }}
          skala={zeigBild.skala}
          format={format}
          mindestAnteil={MINDEST_ANTEIL}
          beschreibung={
            `Woher das Geld der Stadt kommt und wofür es ausgegeben wird, ${zeigBild.year}, in Mio. Euro. ` +
            `Alle Einnahmen laufen in eine gemeinsame Kasse von ${format(zeigBild.skala)} Mio. Euro und werden von dort verteilt; ` +
            `es gibt keine Zuordnung einzelner Einnahmen zu einzelnen Ausgaben. ` +
            `Herkunft: ${beschreibe(links)}. ` +
            `Verwendung: ${beschreibe(rechts)}.`
          }
        />
      )}

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
          Beide Seiten verwenden dieselbe Skala von
          {" "}{deMio(mio(zeigBild.summeLinks))}&#8239;Mio.&nbsp;€.{" "}
          {saldoMio < 0
            ? `Das zusätzliche schraffierte Band zeigt das geplante Minus von ${deMio(-saldoMio)} Mio. €; es ist keine weitere Einnahmeart.`
            : saldoMio > 0
              ? `Das zusätzliche Band auf der Ausgabenseite zeigt den geplanten Überschuss von ${deMio(saldoMio)} Mio. €.`
              : "Die geplanten Einnahmen und Ausgaben sind gleich hoch."}
          {!zeigBild.stimmt && " Die Einzelposten stimmen nicht mit der Gesamtsumme überein; die Grafik macht diese Abweichung sichtbar."}
        </p>
      )}

      {/* Die Quellenzeile steht seit 20.08. HIER und nicht auf der Seite.
          Grund: Sie muss das benennen, was wirklich gezeichnet wurde, und das
          weiß nur diese Komponente. Auf der Seite stand sie unbedingt unter
          dem Block — auch dann, wenn dort für ein Planjahr die Herkunftsseite
          aus dem Gesamtergebnishaushalt steht (die ihren eigenen Beleg trägt).
          Dann nannte sie die falsche Quelle. */}
      <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
        Quelle: Ergebnisrechnung des jeweiligen Jahresabschlusses<Beleg q="jahresabschluss" /> —
        Einnahmearten (Posten 01–11) und Aufwendungen je Teilhaushalt (Posten 20) aus
        derselben Tabelle desselben Jahres.
      </p>
    </div>
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
            Woher — {bild.stand === "ist" ? "tatsächlich" : "geplant"} {bild.year}
          </td></tr>
          {zeilen(bild.herkunft.baender)}
          <tr className="border-t-2 border-border font-semibold">
            <td className="py-1 pr-2">Summe links</td>
            <td className="py-1 pr-2 text-right">{deMio(mio(bild.summeLinks))}</td>
            <td className="py-1 text-right">100&nbsp;%</td>
          </tr>
          <tr><td colSpan={3} className="pt-3 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            Wohin — {bild.stand === "ist" ? "tatsächlich" : "geplant"} {bild.year}
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
          ? `Prüfung der Summen: Beide Seiten ergeben ${deMio(mio(bild.summeLinks))} Mio. € und verwenden dieselbe Skala.`
          : `Prüfung der Summen: links ${deMio(mio(bild.summeLinks))}, rechts ${deMio(mio(bild.summeRechts))} Mio. €. Die Einzelwerte ergeben keine gemeinsame Gesamtsumme.`}
      </p>
    </div>
  );
}
