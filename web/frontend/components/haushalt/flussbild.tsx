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
  FlussBand, FlussDaten, HaushaltAuswahl,
  deMio, flussJahre, flussbild, mio,
} from "@/lib/haushalt";
import { ausblick, type Antwort as DatenstandAntwort } from "@/components/haushalt/datenstand";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

/** Ein Band bekommt nur dann eine eigene Beschriftung, wenn es mindestens so
 *  viel der Skala trägt — sonst steht es im Sammelposten. Lesbarkeits-, keine
 *  Relevanzentscheidung: Ein 4-px-Band ist seiner Zeile nicht zuzuordnen. */
const MINDEST_ANTEIL = 0.05;

/** Die Haushalts-Bänder in den Baukasten-Vertrag übersetzen: `rest` und
 *  `ausgleich` sind beide Differenz-Bänder (Schraffur + Signal-Kante). */
function alsPosten(b: FlussBand): FlussPosten {
  return {
    id: b.id, label: b.label, lang: b.lang, wert: b.wert,
    art: b.art === "posten" ? "posten" : "differenz",
  };
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
  daten: HaushaltAuswahl<"ergebnisrechnung">;
  jahr: number;
  /** Der saubere Weg, das Angebot einzulösen — die Seite hält das Jahr.
   *  Optional, damit die Einbindung unverändert weiterläuft; ohne ihn greift
   *  die Pillen-Notlösung unten. */
  onJahrWechsel?: (jahr: number) => void;
}) {
  const [stand, setStand] = useState<"plan" | "ist">("ist");
  const [tabelle, setTabelle] = useState(false);

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

      {!zeigBild.aufgeschluesselt ? (
        // Ehrlich statt gestreckt: Wenn die Einzelposten die ausgewiesene
        // Summe nicht tragen, wird nichts hochgerechnet und nichts gedehnt.
        <p className="rounded-lg border border-dashed border-signal/60 bg-card px-3 py-2.5 text-[12px] leading-relaxed text-foreground/85">
          Die Einzelposten dieses Jahres ergeben zusammen nicht die ausgewiesene Summe:{" "}
          {luecken.map((l) => `bei den ${l.seite} ${l.teile} statt ${l.gesamt}`).join(", ")}
          &#8239;Mio.&nbsp;€. Wir haben also nicht alle Zeilen des Dokuments lesen können. Ein Bild
          daraus wäre gestreckt — die Zahlen stehen deshalb nur in der Tabelle.
        </p>
      ) : (
        <FlussbildGrafik
          links={links}
          rechts={rechts}
          topf={{
            kurz: "Eine Kasse",
            lang: "Alles in einer Kasse",
            wert: zeigBild.skala,
            satz: "Alles Geld der Stadt",
            hinweis: "Kein Posten links gehört zu einem Posten rechts: Alles fließt erst "
              + "zusammen und wird dann verteilt.",
          }}
          skala={zeigBild.skala}
          format={format}
          mindestAnteil={MINDEST_ANTEIL}
          beschreibung={
            `Woher das Geld der Stadt kommt und wofür es ausgegeben wird, ${zeigBild.jahr}, in Mio. Euro. ` +
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
