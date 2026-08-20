"use client";

// Der Kassenzettel: der Haushalt pro Kopf (Entwurf H2-02).
//
// 883,9 Millionen Euro sind keine Größe, die jemand fühlt. Rund 5.005 Euro je
// Einwohnerin und Einwohner sind eine. Der Zettel teilt jede Zeile des
// Ergebnishaushalts durch die amtliche Einwohnerzahl — dieselbe Reihenfolge,
// dieselben Verhältnisse, nur in einer Einheit, die man mit dem eigenen Leben
// vergleichen kann. Er löst auf der Übersicht zwei ältere Bausteine ab
// (`LottiVergleich` und den Rücklagen-Hinweis), die dieselbe Zahl vorher
// zweimal genannt haben.
//
// GERENDERT wird der Bon seit dem Grafik-Baukasten von
// `components/grafik/kassenzettel.tsx` (GB-13) — dort wohnen Papierkante,
// Bonzeilen, die automatische Rundungszeile, der sichtbare Teiler unterm
// Zettel und der Pflicht-Kasten „Was diese Zahl nicht ist". HIER wohnt die
// Rechnung: welcher Posten auf den Bon kommt, was er je Kopf kostet und
// welche Karten daneben stehen.
//
// Sechs Dinge, die man beim Weiterbauen kennen muss:
//
//  1. **Die Einwohnerzahl kommt aus den Daten, nie aus dem Kopf.** Der Entwurf
//     rechnete mit 175.000 und kam auf 5.051 €. Amtlich sind es 176.614
//     (`council_einwohner`, Haushaltsjahr 2025, Stichtag 31.12.2024) — und
//     damit 5.005 €. Alle Pro-Kopf-Zahlen des Entwurfs liegen rund 0,9 % zu
//     hoch. Für 2026 führt die Stadt noch keine Einwohnerzahl, deshalb steht
//     das Bezugsjahr an der Zahl.
//  2. **Immer aus Rohwerten teilen, nie aus gerundeten Millionen.** Das
//     geplante Minus sind 71.057.496 €, also 402 € je Kopf. Über die
//     angezeigten „71,1 Mio." gerechnet kämen 403 € heraus — dieselbe Falle,
//     die in `tafel.tsx` und `gegenbalken.tsx` schon einmal zugeschnappt ist.
//  3. **Der Zettel läuft nur fürs jüngste Planjahr.** `council_einwohner`
//     endet mit dem Haushaltsjahr 2025; der Endpunkt liefert nur die jüngste
//     Zeile. Den Plan von 2020 durch die Einwohnerzahl von 2025 zu teilen wäre
//     ein stiller Fehler von rund 4 %, deshalb gibt es hier keinen
//     Jahresumschalter.
//  4. **Kein Konsumgüter-Vergleich.** „So viele Currywürste" verharmlost und
//     erklärt nichts. Greifbar wird die Zahl über die letzte Zeile des Zettels:
//     wie viel davon aus dem Ersparten kommt und wie viel Erspartes danach
//     noch übrig ist. Das steht in den Daten, ein Warenkorb nicht.
//  5. **Keine Bewertungsfarben.** Signal-Orange markiert ausschließlich die
//     Differenz („aus dem Ersparten"), nicht „schlecht". Begründung in
//     `hantel.tsx`.
//  6. **Jahresabhängige Sätze werden gerechnet.** 2020–2022 plante die Stadt
//     einen Überschuss; „aus dem Ersparten" wäre dort schlicht falsch. Der
//     Zettel schaltet auf „bleibt übrig" um, und die Reichweite des Ersparten
//     erscheint nur, wenn es überhaupt ein Minus gibt.
//
// Der Kasten „Was diese Zahl nicht ist" führt VIER Punkte: Bezugskreis,
// Herkunft, fehlender Investitionsteil, Vergleichsfalle. „Keine Rechnung —
// niemand überweist diesen Betrag" ist seit 16.08. gestrichen (das weiß jede
// Leserin); beim Umzug auf den Baukasten stand kurzzeitig beides UND der
// Bezugskreis doppelt („Geteilt wird durch alle" neben „Alle zählen mit") —
// ein Merge-Rest, hier bereinigt.

import { Beleg } from "@/components/haushalt/quelle";
import {
  BonZeile, Kassenzettel as KassenzettelBon, NichtAussage,
} from "@/components/grafik/kassenzettel";
import { BEREICH_NACH_SCHLUESSEL, bereichKanon } from "@/lib/haushalt-bereiche";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import {
  HaushaltAuswahl, RUECKLAGE_MIO, RUECKLAGE_STAND,
  bereiche, deMio, mio, quellenLabel, summe,
} from "@/lib/haushalt";
import { cn } from "@/lib/utils";

const de = (n: number) => n.toLocaleString("de-DE");

/** Ab welchem Jahr das Ersparte zu Jahresbeginn aufgebraucht wäre, bliebe das
 *  geplante Minus so. Eine Division, keine Prognose der Stadt — und `null`,
 *  wenn sie über 40 Jahre nicht aufgeht: Dann trägt der Satz nichts mehr. */
function ruecklageLeerAb(defizitEuro: number, abJahr: number): number | null {
  if (defizitEuro <= 0) return null;
  let rest = RUECKLAGE_MIO * 1e6;
  let jahr = abJahr;
  while (rest > 0 && jahr < abJahr + 40) {
    rest -= defizitEuro;
    jahr += 1;
  }
  return rest > 0 ? null : jahr;
}

/** Anteil der Transferaufwendungen an den Aufwendungen eines Teilhaushalts —
 *  aus dem jüngsten Jahresabschluss, der beides hergibt.
 *
 *  Wofür: „570 € Finanzen" liest sich auf einem Bon wie der Preis der
 *  Kämmerei. Tatsächlich ist der Löwenanteil Geld, das die Stadt nur
 *  weiterreicht (Gewerbesteuer- und Finanzausgleichsumlage). Der Anteil wird
 *  gerechnet und mit seinem Jahr angeschrieben, statt als feste Zahl zu
 *  veralten. */
function transferAnteil(daten: HaushaltAuswahl<"ergebnisrechnung" | "jahre">, thhNr: number): {
  jahr: number; prozent: number;
} | null {
  const posten = daten.ergebnisrechnung ?? [];
  const jahre = [...new Set(posten.filter((p) => p.thh_nr === thhNr).map((p) => p.jahr))]
    .sort((a, b) => b - a);
  for (const jahr of jahre) {
    const wert = (nr: number) => posten.find(
      (p) => p.jahr === jahr && p.thh_nr === thhNr && p.nr === nr)?.ergebnis ?? null;
    const transfer = wert(18);
    const gesamt = wert(20);
    if (transfer != null && gesamt != null && gesamt > 0) {
      return { jahr, prozent: Math.round((transfer / gesamt) * 100) };
    }
  }
  return null;
}

/** Welche Belege der Zettel für dieses Jahr wirklich zitiert.
 *
 *  Die Seite meldet ihre Quellen vorab an (`Quellenkontext`), und die
 *  Nummerierung läuft über genau diese Liste. Meldet sie eine Quelle an, die
 *  der Zettel dann gar nicht braucht, steht im Verzeichnis ein Beleg für
 *  nichts; meldet sie eine zu wenig an, verschluckt `Beleg` den Chip
 *  stillschweigend. Deshalb sagt der Zettel es selbst — `plan` nicht, die
 *  trägt die Seite ohnehin schon für die Anzeigetafel. */
export function kassenzettelQuellen(daten: HaushaltAuswahl<"ergebnisrechnung" | "jahre">, jahr: number): QuellenSchluessel[] {
  const g = summe(daten.jahre[String(jahr)] ?? []);
  if (!g || g.aufwendungen == null) return [];
  const q: QuellenSchluessel[] = ["einwohner"];
  if (g.ertraege != null && g.ertraege < g.aufwendungen) q.push("ruecklage");
  if (transferAnteil(daten, BEREICH_NACH_SCHLUESSEL.finanzen.thh)) {
    q.push("ergebnisrechnung_thh");
  }
  return q;
}

function Karte({ kicker, children, className }: {
  kicker: string; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("rounded-2xl border border-border bg-card p-4 shadow-sm", className)}>
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        {kicker}
      </p>
      {children}
    </div>
  );
}

/** Die vier Grenzen der Pro-Kopf-Zahl — Pflicht-Prop des Bons (GB-13).
 *  Was hier steht, muss jemandem etwas sagen, das er nicht ohnehin weiß;
 *  geblieben ist, was überrascht (Begründung im Kopfkommentar). */
const NICHT_AUSSAGEN: NichtAussage[] = [
  {
    kern: "Geteilt wird durch alle.",
    text: "Auch durch Kinder, Rentner*innen und Menschen ohne eigenes Einkommen — "
      + "nicht durch die Zahl der Steuerzahlenden.",
  },
  {
    kern: "Das Geld kommt nicht nur aus Oldenburg.",
    text: "Ein großer Teil sind Zuweisungen des Landes und Anteile an Bundessteuern.",
  },
  {
    // Die Bon-Metapher legt nahe, man kaufe hier Dinge; der Ergebnishaushalt
    // enthält aber keine einzige Investition.
    kern: "Nichts Neues gebaut.",
    // Der Satz endete bis 19.08.2026 mit „… den wir noch nicht eingelesen
    // haben". Das stimmt seit den Investitions-Schichten nicht mehr: Der
    // Finanzhaushalt steht auf `/haushalt/investitionen`, samt der einzelnen
    // Vorhaben aus dem Investitionsprogramm. Geblieben ist die eigentliche
    // Aussage — die beiden Haushalte sind nicht addierbar, und deshalb steckt
    // in „227 € für Kultur und Sport" keine neue Sporthalle.
    text: "Der Zettel zeigt den Ergebnishaushalt, also das Laufende eines Jahres samt "
      + "Abschreibungen auf vorhandene Gebäude. Neubauten, Fahrzeuge und Grundstücke "
      + "stehen in einem eigenen Haushalt — dem Finanzhaushalt, den „Was wird gebaut?" "
      + "zeigt. Die beiden lassen sich nicht zusammenzählen.",
  },
  {
    kern: "Städtevergleiche hinken.",
    text: "Oldenburg ist kreisfrei und trägt Aufgaben, die anderswo der Landkreis "
      + "zahlt — pro Kopf steht die Stadt dadurch automatisch höher.",
  },
];

export function Kassenzettel({ daten, jahr, einwohner, className }: {
  daten: HaushaltAuswahl<"ergebnisrechnung" | "jahre">;
  /** Das jüngste Planjahr — der Zettel läuft bewusst nur dafür (s. o.). */
  jahr: number;
  /** Amtliche Bezugsgröße samt ihrem Haushaltsjahr. */
  einwohner: { jahr: number; einwohner: number };
  className?: string;
}) {
  const zeilen = daten.jahre[String(jahr)] ?? [];
  const gesamt = summe(zeilen);
  const kopf = einwohner.einwohner;
  if (!gesamt || gesamt.aufwendungen == null || kopf <= 0) return null;

  const jeKopf = (euro: number) => Math.round(euro / kopf);

  const posten = bereiche(zeilen)
    .filter((z) => z.aufwendungen != null && z.aufwendungen > 0)
    .map((z) => ({
      roh: z.bereich,
      kanon: bereichKanon(z.bereich),
      euro: z.aufwendungen as number,
      wert: jeKopf(z.aufwendungen as number),
    }))
    .sort((a, b) => b.euro - a.euro);

  const summeJeKopf = jeKopf(gesamt.aufwendungen);
  const einJeKopf = gesamt.ertraege != null ? jeKopf(gesamt.ertraege) : null;
  // Aus Rohwerten, nicht aus den angezeigten Millionen — sonst 403 statt 402.
  const saldoEuro = gesamt.ertraege != null ? gesamt.ertraege - gesamt.aufwendungen : null;
  const fehltEuro = saldoEuro != null && saldoEuro < 0 ? -saldoEuro : null;
  const ueberEuro = saldoEuro != null && saldoEuro > 0 ? saldoEuro : null;

  const ruecklageJeKopf = jeKopf(RUECKLAGE_MIO * 1e6);
  const restJeKopf = fehltEuro != null ? jeKopf(RUECKLAGE_MIO * 1e6 - fehltEuro) : null;
  const leerAb = fehltEuro != null ? ruecklageLeerAb(fehltEuro, jahr) : null;

  const quelle = quellenLabel(zeilen, jahr);
  const finanzen = BEREICH_NACH_SCHLUESSEL.finanzen;
  const finanzenZeile = posten.find((p) => p.kanon.schluessel === "finanzen");
  const transfer = transferAnteil(daten, finanzen.thh);
  const gross = posten.slice(0, 2);

  const bezahltMit: BonZeile[] | undefined = einJeKopf != null ? [
    { label: `Einnahmen ${jahr}`, wert: einJeKopf },
    ...(fehltEuro != null
      ? [{ label: "aus dem Ersparten", wert: jeKopf(fehltEuro), ton: "signal" as const }] : []),
    ...(ueberEuro != null
      ? [{ label: "bleibt übrig", wert: jeKopf(ueberEuro) }] : []),
  ] : undefined;

  return (
    <section
      aria-labelledby="kassenzettel-titel"
      className={cn("rounded-2xl border border-border bg-background p-4 sm:p-5", className)}
    >
      <KassenzettelBon
        titel="Stadt Oldenburg"
        untertitel={`Haushaltsplan ${jahr}`}
        stempel={<>je Einwohner*in<Beleg q="einwohner" /></>}
        posten={posten.map((p) => ({
          label: p.kanon.kurz,
          wert: p.wert,
          ton: p.wert < 100 ? ("leise" as const) : undefined,
        }))}
        summe={summeJeKopf}
        summeLabel={<>Summe<Beleg q="plan" /></>}
        bezahltMit={bezahltMit}
        teiler={{
          zahl: kopf,
          einheit: "Einwohner*innen",
          stichtag: `31.12.${einwohner.jahr - 1}`,
          quelle: <>amtliche Zahl der Stadt<Beleg q="einwohner" /></>,
        }}
        nichtAussagen={NICHT_AUSSAGEN}
        fuss={restJeKopf != null ? (
          <div className="mt-3 space-y-1.5 border-t border-dashed border-border pt-3 text-[11px] text-muted-foreground">
            {/* „Erspartes noch vorhanden 1.114 €" stand so im Entwurf und
                war ein Rechenfehler: Das ist der Stand VOR dem Zugriff
                dieses Jahres. Deshalb zwei Zeilen statt einer. */}
            <div className="flex items-baseline justify-between gap-3">
              <span>Erspartes vor diesem Jahr<Beleg q="ruecklage" /></span>
              <span className="flex-none tabular-nums">{de(ruecklageJeKopf)}&nbsp;€</span>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <span>danach noch</span>
              <span className="flex-none font-medium tabular-nums text-foreground">
                {de(restJeKopf)}&nbsp;€
              </span>
            </div>
          </div>
        ) : undefined}
        // Nicht „ÜBERSICHT ERGEBNISHAUSHALT · S. 1": Der Jahrgang 2024
        // stammt aus einer CSV, nicht aus einer PDF-Seite.
        quelle={quelle.text}
        daneben={
          <div>
            <h2 id="kassenzettel-titel"
              className="font-display text-[21px] font-bold leading-tight tracking-tight sm:text-[25px]">
              Was die Stadt pro Kopf ausgibt
            </h2>
            <p className="mt-2.5 max-w-[58ch] text-[13.5px] leading-relaxed text-foreground/90 sm:text-[14.5px]">
              Millionenbeträge lassen sich nicht fühlen. Teilt man die geplanten
              Ausgaben von {deMio(mio(gesamt.aufwendungen))}&#8239;Mio.&nbsp;€ durch die
              Einwohnerzahl, wird daraus ein Betrag, den man mit dem eigenen Leben
              vergleichen kann
              {gross.length === 2 && (
                <> — <strong className="font-semibold">
                  {de(gross[0].wert)}&nbsp;€ für {gross[0].kanon.name},{" "}
                  {de(gross[1].wert)}&nbsp;€ für {gross[1].kanon.name}
                </strong></>
              )}.
            </p>
          </div>
        }
        danach={
          <>
            <div className="grid gap-3.5 @2xl/zettel:grid-cols-2">
              <Karte kicker="So wird gerechnet">
                <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">
                  Geplante Aufwendungen {jahr}{" "}
                  <span className="font-mono">{de(gesamt.aufwendungen)}&nbsp;€</span>
                  <Beleg q="plan" /> geteilt durch{" "}
                  <span className="font-mono">{de(kopf)}</span> Einwohner*innen
                  <Beleg q="einwohner" /> ={" "}
                  <strong className="font-semibold">{de(summeJeKopf)}&nbsp;€</strong>.
                </p>
                <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                  Die Einwohnerzahl ist die des Haushaltsjahrs {einwohner.jahr} — Stichtag
                  31.12.{einwohner.jahr - 1}
                  {einwohner.jahr < jahr && <>; für {jahr} führt die Stadt noch keine.
                    Ist Oldenburg seither gewachsen, liegt der Betrag je Kopf etwas
                    niedriger</>}. Unsere Rechnung, keine amtliche Kennzahl.
                </p>
              </Karte>

              {fehltEuro != null && (
                <Karte kicker="Das Ersparte">
                  <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">
                    Das Minus wird aus der Rücklage von rund {RUECKLAGE_MIO}&#8239;Mio.&nbsp;€
                    gedeckt<Beleg q="ruecklage" /> — {de(ruecklageJeKopf)}&nbsp;€ je Kopf, von
                    denen dieses Jahr {de(jeKopf(fehltEuro))}&nbsp;€ abgehen.
                    {leerAb != null && <> Bliebe es bei einem Minus dieser Größe, wäre das
                      Ersparte zu Beginn von {leerAb} aufgebraucht. Was dann geschieht,
                      entscheidet der Rat.</>}
                  </p>
                  <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                    Rechnerische Reichweite, keine Prognose der Stadt. {RUECKLAGE_STAND}.
                  </p>
                </Karte>
              )}
            </div>

            {/* Eine Zeile des Bons liest sich anders, als sie gemeint ist. */}
            {finanzenZeile && (
              <p className="text-[11.5px] leading-relaxed text-muted-foreground">
                Eine Zeile führt in die Irre: Die {de(finanzenZeile.wert)}&nbsp;€ bei{" "}
                <strong className="font-semibold text-foreground">{finanzen.kurz}</strong> sind
                nicht der Preis der Kämmerei. In diesem Teilhaushalt bucht die Stadt auch, was
                sie nur weiterreicht — Gewerbesteuer- und Finanzausgleichsumlage
                {transfer && <>; im Jahresabschluss {transfer.jahr} waren {transfer.prozent}&nbsp;%
                  der Aufwendungen dieses Bereichs solche Transferzahlungen<Beleg q="ergebnisrechnung_thh" /></>}.
              </p>
            )}
          </>
        }
      />
    </section>
  );
}
