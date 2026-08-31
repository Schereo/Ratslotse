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
  HaushaltAuswahl, bereiche, deMio, juengsteRuecklage, mio, quellenLabel, summe,
} from "@/lib/haushalt";
import type { RuecklageJahr } from "@/lib/haushalt";
import { cn } from "@/lib/utils";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import type { JahrPunkt } from "@/components/grafik/daten";

const de = (n: number) => n.toLocaleString("de-DE");

/** Ab welchem Jahr das Ersparte zu Jahresbeginn aufgebraucht wäre, bliebe das
 *  geplante Minus so. Eine Division, keine Prognose der Stadt — und `null`,
 *  wenn sie über 40 Jahre nicht aufgeht: Dann trägt der Satz nichts mehr. */
function ruecklageLeerAb(
  defizitEuro: number, ruecklageEuro: number, abJahr: number,
): number | null {
  if (defizitEuro <= 0) return null;
  let rest = ruecklageEuro;
  let year = abJahr;
  while (rest > 0 && year < abJahr + 40) {
    rest -= defizitEuro;
    year += 1;
  }
  return rest > 0 ? null : year;
}

/** Die API liefert nur belastbare Bilanzwerte. Fehlende Jahre werden hier
 *  ausdrücklich ergänzt, damit die Grafik ihre Linie dort unterbricht und
 *  den Grund anschreibt, statt die beiden Nachbarjahre zu verbinden. */
function ruecklagenReihe(zeilen: RuecklageJahr[]): JahrPunkt[] {
  const sortiert = [...zeilen]
    .filter((z) => Number.isFinite(z.state_after_result))
    .sort((a, b) => a.year - b.year);
  if (!sortiert.length) return [];
  const nachJahr = new Map(sortiert.map((z) => [z.year, z]));
  const aus: JahrPunkt[] = [];
  for (let year = sortiert[0].year; year <= sortiert[sortiert.length - 1].year; year += 1) {
    const zeile = nachJahr.get(year);
    aus.push(zeile
      ? { year, wert: zeile.state_after_result / 1e6 }
      : {
          year,
          fehlt: "Für dieses Jahr liegt in den eingelesenen Jahresabschlüssen "
            + "kein belastbarer Rücklagenwert vor.",
        });
  }
  return aus;
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
  year: number; prozent: number;
} | null {
  const posten = daten.ergebnisrechnung ?? [];
  const jahre = [...new Set(posten.filter((p) => p.sub_budget_no === thhNr).map((p) => p.year))]
    .sort((a, b) => b - a);
  for (const year of jahre) {
    const wert = (nr: number) => posten.find(
      (p) => p.year === year && p.sub_budget_no === thhNr && p.nr === nr)?.result ?? null;
    const transfer = wert(18);
    const gesamt = wert(20);
    if (transfer != null && gesamt != null && gesamt > 0) {
      return { year, prozent: Math.round((transfer / gesamt) * 100) };
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
export function kassenzettelQuellen(daten: HaushaltAuswahl<"ergebnisrechnung" | "jahre">, year: number): QuellenSchluessel[] {
  const g = summe(daten.jahre[String(year)] ?? []);
  if (!g || g.expenses == null) return [];
  const q: QuellenSchluessel[] = ["einwohner"];
  if (g.revenues != null && g.revenues < g.expenses) q.push("ruecklage");
  if (transferAnteil(daten, BEREICH_NACH_SCHLUESSEL.finanzen.sub_budget)) {
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
    kern: "Die Rechnung umfasst die gesamte Bevölkerung.",
    text: "Dazu gehören auch Kinder, Rentner*innen und Menschen ohne eigenes Einkommen. "
      + "Geteilt wird nicht nur durch die Zahl der Steuerzahlenden.",
  },
  {
    kern: "Nicht alle Einnahmen stammen aus Oldenburg.",
    text: "Zur Finanzierung gehören auch Zuweisungen des Landes und Anteile an Bundessteuern.",
  },
  {
    // Die Bon-Metapher legt nahe, man kaufe hier Dinge; der Ergebnishaushalt
    // enthält aber keine einzige Investition.
    kern: "Investitionen sind nicht enthalten.",
    // Der Satz endete bis 19.08.2026 mit „… den wir noch nicht eingelesen
    // haben". Das stimmt seit den Investitions-Schichten nicht mehr: Der
    // Finanzhaushalt steht auf `/haushalt/investitionen`, samt der einzelnen
    // Vorhaben aus dem Investitionsprogramm. Geblieben ist die eigentliche
    // Aussage — die beiden Haushalte sind nicht addierbar, und deshalb steckt
    // in „227 € für Kultur und Sport" keine neue Sporthalle.
    text: "Der Zettel zeigt den Ergebnishaushalt: laufende Aufwendungen einschließlich "
      + "Abschreibungen. Neubauten, Fahrzeuge und Grundstücke stehen im Finanzhaushalt "
      + "auf der Investitionsseite. Die beiden Haushalte bilden unterschiedliche "
      + "Rechnungen und dürfen nicht einfach addiert werden.",
  },
  {
    kern: "Für Städtevergleiche reicht die Zahl allein nicht aus.",
    text: "Oldenburg ist kreisfrei und übernimmt Aufgaben, die andernorts ein Landkreis "
      + "finanziert. Dadurch fallen die Pro-Kopf-Ausgaben grundsätzlich höher aus.",
  },
];

export function Kassenzettel({ daten, year, einwohner, className }: {
  daten: HaushaltAuswahl<"ergebnisrechnung" | "jahre" | "ruecklage">;
  /** Das jüngste Planjahr — der Zettel läuft bewusst nur dafür (s. o.). */
  year: number;
  /** Amtliche Bezugsgröße samt ihrem Haushaltsjahr. */
  einwohner: { year: number; einwohner: number };
  className?: string;
}) {
  const zeilen = daten.jahre[String(year)] ?? [];
  const gesamt = summe(zeilen);
  const kopf = einwohner.einwohner;
  if (!gesamt || gesamt.expenses == null || kopf <= 0) return null;

  const jeKopf = (euro: number) => Math.round(euro / kopf);

  const posten = bereiche(zeilen)
    .filter((z) => z.expenses != null && z.expenses > 0)
    .map((z) => ({
      roh: z.area,
      kanon: bereichKanon(z.area),
      euro: z.expenses as number,
      wert: jeKopf(z.expenses as number),
    }))
    .sort((a, b) => b.euro - a.euro);

  const summeJeKopf = jeKopf(gesamt.expenses);
  const einJeKopf = gesamt.revenues != null ? jeKopf(gesamt.revenues) : null;
  // Aus Rohwerten, nicht aus den angezeigten Millionen — sonst 403 statt 402.
  const saldoEuro = gesamt.revenues != null ? gesamt.revenues - gesamt.expenses : null;
  const fehltEuro = saldoEuro != null && saldoEuro < 0 ? -saldoEuro : null;
  const ueberEuro = saldoEuro != null && saldoEuro > 0 ? saldoEuro : null;

  const ruecklage = juengsteRuecklage(daten);
  const ruecklagenVerlauf = ruecklagenReihe(daten.ruecklage ?? []);
  const ruecklageEuro = ruecklage?.state_after_result ?? null;
  const ruecklageJeKopf = ruecklageEuro != null ? jeKopf(ruecklageEuro) : null;
  const restJeKopf = fehltEuro != null && ruecklageEuro != null
    ? jeKopf(ruecklageEuro - fehltEuro) : null;
  const leerAb = fehltEuro != null && ruecklageEuro != null
    ? ruecklageLeerAb(fehltEuro, ruecklageEuro, year) : null;

  const quelle = quellenLabel(zeilen, year);
  const finanzen = BEREICH_NACH_SCHLUESSEL.finanzen;
  const finanzenZeile = posten.find((p) => p.kanon.schluessel === "finanzen");
  const transfer = transferAnteil(daten, finanzen.sub_budget);
  const gross = posten.slice(0, 2);

  const bezahltMit: BonZeile[] | undefined = einJeKopf != null ? [
    { label: `geplante Erträge ${year}`, wert: einJeKopf },
    ...(fehltEuro != null
      ? [{ label: "geplantes Minus", wert: jeKopf(fehltEuro), ton: "signal" as const }] : []),
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
        untertitel={`Haushaltsplan ${year}`}
        stempel={<>je Einwohner*in<Beleg q="einwohner" /></>}
        posten={posten.map((p) => ({
          label: p.kanon.kurz,
          wert: p.wert,
          ton: p.wert < 100 ? ("leise" as const) : undefined,
        }))}
        summe={summeJeKopf}
        summeLabel={<>Summe<Beleg q="plan" /></>}
        bezahltMit={bezahltMit}
        bezahltMitTitel="Im Plan gedeckt durch"
        teiler={{
          zahl: kopf,
          einheit: "Einwohner*innen",
          as_of_date: `31.12.${einwohner.year - 1}`,
          quelle: <>amtliche Zahl der Stadt<Beleg q="einwohner" /></>,
        }}
        nichtAussagen={NICHT_AUSSAGEN}
        fuss={restJeKopf != null && ruecklageJeKopf != null ? (
          <div className="mt-3 space-y-1.5 border-t border-dashed border-border pt-3 text-[11px] text-muted-foreground">
            {/* „Erspartes noch vorhanden 1.114 €" stand so im Entwurf und
                war ein Rechenfehler: Das ist der Stand VOR dem Zugriff
                dieses Jahres. Deshalb zwei Zeilen statt einer. */}
            <div className="flex items-baseline justify-between gap-3">
              <span>Rücklage vor dem Planjahr<Beleg q="ruecklage" /></span>
              <span className="flex-none tabular-nums">{de(ruecklageJeKopf)}&nbsp;€</span>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <span>rechnerisch danach</span>
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
              Geplante Ausgaben pro Einwohner*in
            </h2>
            <p className="mt-2.5 max-w-[58ch] text-[13.5px] leading-relaxed text-foreground/90 sm:text-[14.5px]">
              Die Stadt plant für {year} Aufwendungen von{" "}
              {deMio(mio(gesamt.expenses))}&#8239;Mio.&nbsp;€. Um diese Größenordnung
              einzuordnen, teilen wir die Summe durch die Einwohnerzahl. Das ergibt
              rechnerisch {de(summeJeKopf)}&nbsp;€ pro Einwohner*in
              {gross.length === 2 && (
                <>. Davon entfallen <strong className="font-semibold">
                  {de(gross[0].wert)}&nbsp;€ auf {gross[0].kanon.name} und{" "}
                  {de(gross[1].wert)}&nbsp;€ auf {gross[1].kanon.name}
                </strong></>
              )}.
            </p>
          </div>
        }
        danach={
          <>
            <div className="grid items-start gap-3.5 @2xl/zettel:grid-cols-2">
              <Karte kicker="So wird gerechnet">
                <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">
                  Geplante Aufwendungen {year}{" "}
                  <span className="font-mono">{de(gesamt.expenses)}&nbsp;€</span>
                  <Beleg q="plan" /> geteilt durch{" "}
                  <span className="font-mono">{de(kopf)}</span> Einwohner*innen
                  <Beleg q="einwohner" /> ={" "}
                  <strong className="font-semibold">{de(summeJeKopf)}&nbsp;€</strong>.
                </p>
                <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                  Die Einwohnerzahl gehört zum Haushaltsjahr {einwohner.year}; Stichtag ist
                  der 31.12.{einwohner.year - 1}
                  {einwohner.year < year && <>. Für {year} hat die Stadt noch keine amtliche
                    Zahl veröffentlicht. Ist die Bevölkerung seitdem gewachsen, fällt der
                    tatsächliche Pro-Kopf-Wert etwas niedriger aus</>}. Der Pro-Kopf-Betrag
                  ist unsere Rechnung und keine amtliche Kennzahl.
                </p>
              </Karte>

              {fehltEuro != null && ruecklage != null && ruecklageEuro != null
                && ruecklageJeKopf != null && (
                <Karte kicker="Geplante Entnahme aus der Rücklage">
                  <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">
                    Im Haushaltsplan soll das Minus durch die Rücklage von rund
                    {" "}{deMio(ruecklageEuro / 1e6)}&#8239;Mio.&nbsp;€ ausgeglichen werden
                    <Beleg q="ruecklage" />. Das entspricht {de(ruecklageJeKopf)}&nbsp;€ je
                    Einwohner*in; für dieses Planjahr würden rechnerisch
                    {" "}{de(jeKopf(fehltEuro))}&nbsp;€ davon benötigt.
                    {leerAb != null && <> Würde in jedem Folgejahr ein Minus derselben Größe
                      entstehen, wäre die Rücklage zu Beginn von {leerAb} aufgebraucht.</>}
                  </p>
                  <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                    Diese Rechnung veranschaulicht nur die Größenordnung. Sie ist keine
                    Prognose, denn die tatsächlichen Jahresergebnisse können deutlich vom
                    Plan abweichen. Stand: Jahresabschluss {ruecklage.year}, nach
                    Berücksichtigung des dort ausgewiesenen Jahresergebnisses.
                  </p>
                </Karte>
              )}
            </div>

            {/* Eine Zeile des Bons liest sich anders, als sie gemeint ist. */}
            {finanzenZeile && (
              <p className="text-[11.5px] leading-relaxed text-muted-foreground">
                Die {de(finanzenZeile.wert)}&nbsp;€ im Bereich{" "}
                <strong className="font-semibold text-foreground">{finanzen.kurz}</strong>{" "}
                sind nicht die Verwaltungskosten der Kämmerei. Dort verbucht die Stadt auch
                Transferzahlungen wie die Gewerbesteuer- und Finanzausgleichsumlage
                {transfer && <>; im Jahresabschluss {transfer.year} waren {transfer.prozent}&nbsp;%
                  der Aufwendungen dieses Bereichs solche Zahlungen<Beleg q="ergebnisrechnung_thh" /></>}.
              </p>
            )}
          </>
        }
        // Der allgemeine Bon-Baustein setzt `darunter` unter BEIDE Spalten.
        // Auf breiten Screens nutzt die Kurve damit auch den freien Raum
        // unter dem Papierbon; auf schmalen bleibt sie schlicht die letzte
        // volle Zeile.
        darunter={fehltEuro != null && ruecklage != null
          && ruecklagenVerlauf.length >= 2 ? (
          <Karte kicker="Rücklage im Zeitverlauf">
            <Zeitreihe
              className="mt-3"
              reihe={ruecklagenVerlauf}
              titel="Verfügbar nach Jahresergebnis"
              einheit="Mio. €"
              nachkomma={1}
              ariaTitel={`Verfügbare Überschussrücklage nach Jahresergebnis, `
                + `${ruecklagenVerlauf[0].year} bis ${ruecklage.year}`}
              vorjahresdifferenz
              tabelle
              leisteHaftet={false}
            />
          </Karte>
        ) : undefined}
      />
    </section>
  );
}
