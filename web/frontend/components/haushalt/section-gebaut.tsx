"use client";

// „Was wurde davon wirklich gebaut?" — der ZWEITE Abschnitt von
// /haushalt/investitionen: das IST.
//
// Bis zum 21.08.2026 die eigene Seite /haushalt/gebaut, und zwar in einer
// anderen Etappe als der Plan. Siehe den Kopf von
// `section-investitionsplan.tsx`.

// /haushalt/gebaut — „Was wurde davon wirklich gebaut?" (Boards H3-03, H4-08)
//
// Die Gegenprobe zu /haushalt/investitionen. Dort steht, was die Stadt bauen
// und kaufen WILL (Finanzhaushalt des Haushaltsplans, Planzahlen); hier steht,
// was am Jahresende tatsächlich abgeflossen ist (Rechnungsergebnisse aus dem
// Statistischen Jahrbuch). Das tragende Bild sind die <NahtSaeulen> (GB-02):
// alle 22 Jahrgänge in EINEM Bild, der Systemwechsel 2009/2010 als sichtbare
// Naht zwischen zwei Farbwelten — die Naht wird gezeigt, nicht geglättet,
// und die Komponente rechnet nichts über sie hinweg.
//
// DIE SEITE SUBTRAHIERT NICHT, und das ist ihre wichtigste Entscheidung. Die
// naheliegende Zahl wäre „Ist ÷ Plan = Umsetzungsquote", und sie wäre die
// meistgelesene Zahl der Seite. Sie steht in keinem Dokument: Der Plan ist
// nach Teilhaushalten gegliedert, das Ist nach Auszahlungsarten und
// ausdrücklich nur für die Kernverwaltung. Der Block „Warum hier keine Quote
// steht" ist deshalb kein Kleingedrucktes, sondern eigener Inhalt.
//
// 2019 IST EINE LÜCKE, KEIN WERT: Die Auszahlungsarten ergeben in der
// Quelltabelle nicht die ausgewiesene Summe daneben; der Jahrgang steht
// deshalb nicht im Bestand (`fehlend` der API). Er bleibt als beschriftetes
// <LueckenFeld> im Bild — lieber eine Lücke als eine Zahl, die sich selbst
// widerspricht.
//
// DER BETRAG AN DER LÜCKE KOMMT AUS DEN DATEN, nie von hier: Was der
// Ingest-Lauf beim Verwerfen gemessen hat, steht seitdem in
// `council_investitionen_ist_verworfen` und kommt als `difference` je Lücke
// mit der Antwort (`fehlend`). `lueckeGrund()` unten setzt daraus den Satz
// zusammen — und lässt den Betrag weg, wo die API keinen liefert. Eine
// Jahreszahl mit fest verdrahtetem Betrag wäre eine Behauptung, die beim
// nächsten Jahrbuch still falsch wird.
//
// KEINE BEWERTUNGSFARBEN (components/grafik/hantel.tsx). Ein hoher Balken
// ist keine gute Nachricht und ein niedriger keine schlechte: 2020 steht
// oben, weil ein zweistelliger Millionenbetrag unter „Sonstige
// Investitionstätigkeit" fällt — was das ist, sagt die Quelle nicht, und wir
// erfinden es nicht dazu.

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  GebautDaten, GebautLuecke, Herkunft, deMioEuro, groessterPosten,
  herkunftVon, infrastruktur, juengsteReihe, reihen, sachvermoegen,
  strassen, verzehr,
} from "@/lib/haushalt-gebaut";
import { Gegenbalken } from "@/components/grafik/gegenbalken";
import { LueckenFeld } from "@/components/grafik/luecken-field";
import { NahtSaeulen, type NahtJahr } from "@/components/grafik/naht-saeulen";
import { Anteilsbalken } from "@/components/haushalt/anteilsbalken";
import { Beleg } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";

// `jahresabschluss` gehört dazu: Zwei Beleg-Chips dieser Seite zeigen
// darauf, und ohne den Eintrag hier rendern sie nichts — die Zahlen aus
// dem Anlagenspiegel standen bis zum 21.08.2026 ohne jeden Beleg da.

/** Warum ein Jahrgang fehlt — der Satz am <LueckenFeld>.
 *
 *  Mit Betrag, wo die API einen gemessenen führt („verworfen: 1,3 Mio. €
 *  Differenz im Dokument"), und ohne, wo nicht. Der Betrag wird hier
 *  formatiert und nirgends beziffert: Er steht in `difference` und kommt aus
 *  dem Lauf, der den Jahrgang verworfen hat.
 *
 *  Vorzeichenlos, obwohl `difference` eines trägt: Im Satz steht, wie weit die
 *  beiden Zahlen des Dokuments auseinanderliegen. Welche der sieben Zahlen
 *  danebenliegt, sagt die Tabelle nicht — ein „−" behauptete, es sei die
 *  Summe. */
function lueckeGrund(l: GebautLuecke): string {
  // Mit Betrag bleibt der Grund kurz: Die Zahl sagt bereits, worum es geht,
  // und der ganze Satz steht daneben in „Verworfene Jahrgänge". Ohne Betrag
  // muss der Grund die Auskunft allein tragen — dann wird er länger.
  const satz = "die Auszahlungsarten ergeben in der Quelltabelle nicht die "
    + "ausgewiesene Summe daneben";
  if (l.difference == null) return `verworfen: ${satz}`;
  return `verworfen: ${deMioEuro(Math.abs(l.difference))} Mio. € `
    + `Differenz im Dokument`;
}

/** Die Töne der „Wofür"-Aufteilung — dunkel nach hell, in der Spaltenfolge
 *  der Quelle. Neutrale Ausgaben-Rampe; sechs reichen, mehr Arten führt
 *  keine der beiden Tabellen. */
const TOENE = ["var(--hh-aus-0)", "var(--hh-aus-2)", "var(--hh-aus-4)",
  "var(--hh-aus-6)", "var(--hh-aus-1)", "var(--hh-aus-3)"];

/** Wo eine Angabe im Dokument steht — dieselbe Bauart wie auf der
 *  Schulden-Seite und bewusst nicht geteilt: Die Seiten sollen einander nicht
 *  brechen. */
function Fundstelle({ h }: { h: Herkunft | null }) {
  if (!h?.citation) return null;
  return (
    <div className="border-t border-dashed border-border pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
        {h.citation}{h.stand ? ` · ${h.stand}` : ""}
      </p>
    </div>
  );
}

/** Was aus den Investitionen wurde — und dass der Bestand trotzdem schrumpft.
 *
 *  DIE ZWEITE HÄLFTE DER SEITE. Bis hierher steht, was die Stadt gebaut hat.
 *  Ein Neubau ist aber im Jahr der Fertigstellung eine Investition und danach
 *  vierzig Jahre Vermögen, das sich abnutzt. Erst beides zusammen beantwortet
 *  die Frage, die eine Investitionsliste offenlässt: Baut die Stadt schneller
 *  auf, als ihr Bestand verfällt?
 *
 *  KEINE BEWERTUNGSFARBE. Dass mehr abgeschrieben als zugebaut wird, ist
 *  weder gut noch schlecht — es kann eine alternde Straße sein oder eine
 *  abgeschlossene Sanierung, die planmäßig altert. Der Gegenbalken zeigt die
 *  beiden Zahlen im selben Maßstab, der Satz daneben nennt den Faktor, das
 *  Urteil bleibt bei den Lesenden.
 *
 *  Rendert nichts, solange kein Anlagenspiegel eingelesen ist. */
function AnlagenBlock({ daten }: { daten: GebautDaten | null }) {
  const a = daten?.anlagen;
  const years = a?.years ?? [];
  const year = years[years.length - 1];
  const infra = infrastruktur(a, year);
  const sach = sachvermoegen(a, year);
  const v = verzehr(infra);
  if (!a || !year || !infra || !v) return null;

  // Die Straßenreihe gibt es erst ab 2022 — die Jahre davor sind eine Lücke
  // der QUELLE, nicht der Daten. Sie wird benannt, nicht überbrückt.
  const strassenReihe = years
    .map((j) => ({ year: j, g: strassen(a, j) }))
    .filter((x): x is { year: number; g: NonNullable<ReturnType<typeof strassen>> } => !!x.g);
  const strassenErst = strassenReihe[0];
  const strassenLetzt = strassenReihe[strassenReihe.length - 1];

  return (
    <section className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was daraus wurde
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          {v.faktor && v.faktor > 1
            ? `Beim Infrastrukturvermögen schreibt die Stadt ${deMioEuro(v.depreciation)}\u2009Mio.\u00a0€ ab und baut ${deMioEuro(v.additions)}\u2009Mio.\u00a0€ zu`
            : "Zugänge und Abschreibungen des Infrastrukturvermögens"}
        </h2>
        <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          Straßen, Brücken und Kanäle stehen mit {deMioEuro(infra.book_value)}&#8239;Mio.&nbsp;€ in der
          Bilanz {year}. Was im Jahr dazukam, steht neben dem, was im selben Jahr
          an Wert verloren ging — beide Zahlen aus derselben Tabelle des
          Jahresabschlusses. <Beleg q="jahresabschluss" />
        </p>
      </div>

      {/* Gemeinsame Basis, damit kein Maßstabsfehler konstruierbar ist (GB-04). */}
      <Gegenbalken
        // Der Baustein beschriftet „Mio. €" — also kommen auch Millionen
        // herein. Die Werte des Anlagenspiegels stehen in Euro; ohne diese
        // Umrechnung stünde „17.036.012,7 Mio. €" da.
        zeilen={[
          { titel: `Abgeschrieben ${year}`, rampe: "aus",
            segmente: [{ label: "Wertverlust des Jahres", wert: v.depreciation / 1e6 }] },
          { titel: `Zugegangen ${year}`, rampe: "ein",
            segmente: [{ label: "Neu ins Vermögen", wert: v.additions / 1e6 }] },
        ]}
        basis={Math.max(v.depreciation, v.additions) / 1e6}
        einheit="Mio. €"
        beleg={<Beleg q="jahresabschluss" />}
      />

      {v.faktor && (
        <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Das Verhältnis:</strong>{" "}
          Auf jeden zugebauten Euro kommen{" "}
          {v.faktor.toFixed(1).replace(".", ",")} Euro Abschreibung. Das ist kein
          Urteil über zu wenig Investition — eine planmäßig alternde Straße sieht
          genauso aus wie eine vernachlässigte. Was es sagt: Der Buchwert dieses
          Vermögens sinkt.
        </p>
      )}

      {strassenErst && strassenLetzt && strassenReihe.length > 1 ? (
        <div className="rounded-xl border border-border bg-background/40 p-3">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Straßen, Wege und Plätze im Einzelnen
          </p>
          <p className="mt-1 max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
            Der Jahresabschluss gliedert das Infrastrukturvermögen weiter auf.
            Allein die Straßen, Wege und Plätze sanken von{" "}
            {deMioEuro(strassenErst.g.book_value_prior_year ?? strassenErst.g.book_value)}&#8239;Mio.&nbsp;€ auf{" "}
            {deMioEuro(strassenLetzt.g.book_value)}&#8239;Mio.&nbsp;€ — der Abschluss {year} nennt das
            selbst einen <strong>Substanzverlust</strong>.
          </p>
        </div>

      ) : null}

      {strassenReihe.length > 0 && strassenReihe.length < years.length ? (
        <LueckenFeld
          label={`vor ${strassenReihe[0].year}`}
          grund="Die Jahresabschlüsse gliedern das Infrastrukturvermögen erst ab diesem Jahrgang weiter auf. Die Gesamtsumme steht für alle Jahre da."
        />
      ) : null}

      {sach && sach.spalten === 12 ? (
        <p className="max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Zu den älteren Jahrgängen.</strong>{" "}
          Bis 2020 führt die Tabelle eine Spalte weniger: Verschiebungen zwischen
          den Vermögensarten stehen dort nicht als eigene Angabe, sondern nur als
          Differenz. Sie heben sich über alle Positionen auf null auf — geprüft,
          bevor diese Zahlen hier stehen.
        </p>
      ) : null}
    </section>
  );
}

export function GebautAbschnitt({ onBestand }: {
  /** Meldet die Jahrgänge des Gebaut-Bilds nach oben — die Seitenbühne im
   *  Kopf nennt dieselbe Zahl wie die NahtSäulen, aus derselben Antwort
   *  (H5-02). `luecken` sind die Jahre, die als Lücke im Bild stehen. */
  onBestand?: (b: { jahrgaenge: number; luecken: number[] } | null) => void;
} = {}) {
  const { data, loading } = useFetch<GebautDaten>("/council/haushalt/gebaut");

  const alle = useMemo(() => reihen(data ?? null), [data]);
  const juengste = useMemo(() => juengsteReihe(data ?? null), [data]);
  const aeltere = useMemo(
    () => alle.filter((r) => r.schluessel !== juengste?.schluessel),
    [alle, juengste]);

  // Die eine Reihe des Bildes: alle Jahre beider Regelwerke aufsteigend,
  // Lücken als Daten dazwischen (GB-00-Vertrag). Werte in Mio. €.
  const nahtJahre = useMemo<NahtJahr[]>(() => {
    const js: NahtJahr[] = [];
    for (const r of alle) {
      for (const z of r.years) {
        js.push({
          year: z.year,
          teile: z.arten.map((a) => ({ art: a.titel, wert: a.amount / 1e6 })),
        });
      }
      for (const l of r.fehlend) js.push({ year: l.year, fehlt: lueckeGrund(l) });
    }
    return js.sort((a, b) => a.year - b.year);
  }, [alle]);

  useEffect(() => {
    if (!onBestand || loading) return;
    if (!nahtJahre.length) { onBestand(null); return; }
    onBestand({
      jahrgaenge: nahtJahre.filter((j) => !("fehlt" in j && j.fehlt)).length,
      luecken: nahtJahre.filter((j) => "fehlt" in j && j.fehlt).map((j) => j.year),
    });
  }, [onBestand, loading, nahtJahre]);

  // Die Naht liegt zwischen dem letzten Jahr der älteren und dem ersten der
  // jüngeren Reihe — gerechnet aus den Daten, nicht hart codiert.
  const naht = useMemo(() => {
    const alt = aeltere[0];
    if (!alt || !juengste) return undefined;
    const links = alt.years[alt.years.length - 1].year;
    const rechts = juengste.years[0].year;
    return {
      zwischen: [links, rechts] as [number, number],
      text: `Links ${alt.titel}, rechts ${juengste.titel} — zwei Regelwerke `
        + `mit eigenen Auszahlungsarten und eigenen Namen. Vergleichen ja, `
        + `verrechnen nein.`,
    };
  }, [aeltere, juengste]);

  const alleFehlend = useMemo(
    () => alle.flatMap((r) => r.fehlend).sort((a, b) => a.year - b.year), [alle]);
  // Die gemessenen Differenzen der Lücken — nur die, die eine tragen. Der
  // Satz unten nennt sie, wenn es sie gibt, und schweigt sonst.
  const gemesseneLuecken = useMemo(
    () => alleFehlend.filter((l) => l.difference != null), [alleFehlend]);

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Investitionszahlen werden geladen …
    </div>;
  }
  if (!data || !juengste || juengste.years.length < 2) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite sind die Rechnungsergebnisse noch nicht eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  const letzter = juengste.years[juengste.years.length - 1];
  const erster = nahtJahre.find((j) => !("fehlt" in j));
  const hLetzter = herkunftVon(data, letzter.herkunft_id);
  const quelleUrl = hLetzter?.url ?? null;
  const gross = groessterPosten(letzter);

  return (
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
              Was wurde davon wirklich gebaut?
            </h2>
            <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
              Der Haushaltsplan sagt, was die Stadt bauen und kaufen will. Hier steht,
              was im Jahr {letzter.year} tatsächlich abgeflossen ist:{" "}
              {deMioEuro(letzter.total)}&#8239;Mio.&nbsp;€.
            </p>
          </div>
          {quelleUrl && (
            <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
              className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
              <FileText className="h-3.5 w-3.5" /> Quelle öffnen
            </a>
          )}
        </div>

        {/* STEHT VORN, seit Plan und Ist auf einer Seite stehen (21.08.2026).
            Vorher war es der Schluss der eigenen Seite — dort las man es, NACHDEM
            man die beiden Summen gesehen hatte. Jetzt stehen sie unmittelbar
            untereinander, und die Subtraktion liegt noch näher: Der Einwand
            gehört davor.
            Warum hier keine Quote steht — eigener Block, kein Kleingedrucktes.
            Es ist die Zahl, nach der jede Leserin als Nächstes sucht. */}
        <section className="@container rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Warum hier keine „Umsetzungsquote“ steht
          </p>
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Naheliegend wäre, diese Beträge gegen den Plan zu rechnen und daraus einen
            Prozentsatz zu machen — „so viel vom Geplanten wurde gebaut“. Diese Zahl
            steht in keinem Dokument, und ihre beiden Hälften zählen nicht dasselbe:
          </p>
          <ul className="mt-2 grid list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:grid-cols-2">
            <li>
              <strong>Der Plan</strong> steht im Finanzhaushalt des Haushaltsplans,
              gegliedert nach Teilhaushalten — also danach, welches Amt das Geld
              ausgibt.{" "}
              <a href="#plan" className="font-semibold text-primary">
                Der Abschnitt darüber
              </a>{" "}
              zeigt ihn.
            </li>
            <li>
              <strong>Diese Zahlen</strong> stammen aus der Finanzrechnung der
              Kernverwaltung, gegliedert nach Auszahlungsarten — also danach, wofür es
              ausgegeben wurde.
            </li>
          </ul>
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Keine der beiden Quellen nennt die andere, keine weist eine Differenz aus,
            und keine sagt, dass ihre Gesamtsumme dieselbe Menge zählt. Beide Abschnitte
            stehen deshalb untereinander und nicht in einem Bruch — die eine Zahl von
            der anderen abzuziehen ergäbe keinen Rückstand, sondern einen Fehler.
          </p>
        </section>

        {/* Der Kopf: die Zahl und die Abgrenzung. Die Abgrenzung ist hier so
            wichtig wie der Betrag — „60,8 Mio. € gebaut" liest sich als das
            Gesamtbild der städtischen Bautätigkeit, und das ist es nicht: Der
            Eigenbetrieb Gebäudewirtschaft baut daneben und steht nicht drin. */}
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Haushaltsjahr {letzter.year} · Rechnungsergebnis
          </p>
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                {deMioEuro(letzter.total)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                ausgezahlt für Investitionen<Beleg q="gebaut" />
              </p>
            </div>
            {gross && (
              <div>
                <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                  {deMioEuro(gross.amount)}&#8239;Mio.&nbsp;€
                </p>
                <p className="mt-1 max-w-[28ch] text-[12px] text-muted-foreground">
                  größter Posten: {gross.titel}<Beleg q="gebaut" />
                </p>
              </div>
            )}
          </div>
          {/* Der Wortlaut kommt aus dem Backend — s. Kopfkommentar. */}
          <p className="max-w-[76ch] rounded-xl bg-muted/60 px-3 py-2.5 text-[13px] leading-relaxed text-foreground/90">
            <strong>Gezählt wird:</strong> {data.abgrenzung}
          </p>
          <Fundstelle h={hLetzter} />
        </section>

        <LottiErklaert
          titel="Warum „ausgezahlt“ und nicht „ausgegeben“"
          text={"Die Ergebnisrechnung zeigt den Ressourcenverbrauch eines Jahres, etwa "
            + "Gehälter, Strom, Zuschüsse und Abschreibungen. Die Finanzrechnung erfasst "
            + "dagegen, wann Geld ein- oder ausgezahlt wird — zum Beispiel für ein "
            + "Grundstück, einen Bau oder ein Feuerwehrfahrzeug. Diese Seite verwendet "
            + "die Finanzrechnung. Ihre Beträge lassen sich deshalb nicht zu den "
            + "Aufwendungen der Ergebnisrechnung addieren."}
        />

        {/* Das tragende Bild (H3-03): alle Jahrgänge, eine Naht, die Lücke
            beschriftet im Bild. Naht-Satz und Lücken-Felder rendert die
            Komponente selbst — die Seite kann sie nicht wegkürzen. */}
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div>
            <h2 className="max-w-[30ch] font-display text-[19px] font-bold leading-snug tracking-tight">
              Was eine Stadt in zwei Jahrzehnten baut
            </h2>
            <p className="mt-1.5 max-w-[72ch] text-[13px] leading-relaxed text-foreground/90">
              Tatsächlich ausgezahltes Geld für Investitionen,{" "}
              {erster?.year}&nbsp;bis&nbsp;{letzter.year} — nicht die Pläne, sondern die
              Kassenlage danach.{" "}
              {naht && <>Der Bruch {naht.zwischen[0]}/{naht.zwischen[1]} markiert einen
              Wechsel des Rechnungswesens. Die Werte davor und danach wurden nach
              unterschiedlichen Regeln ermittelt.</>}
            </p>
          </div>
          <NahtSaeulen
            years={nahtJahre}
            naht={naht}
            einheit="Mio. €"
            titel="Auszahlungen für Investitionen"
            beleg={<Beleg q="gebaut" />}
          />
          <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Alle Beträge in Euro des jeweiligen Jahres — die Teuerung ist nicht
            herausgerechnet. Ein Teil der Bewegung ist also verändertes Preisniveau.
          </p>
        </section>

        {/* Die zwei Sätze zum Bild: warum die Naht bleibt, warum 2019 fehlt. */}
        <div className="grid gap-4 breit:grid-cols-2">
          <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Warum die Zeitreihe einen Bruch hat
            </p>
            <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Zum 1. Januar {juengste.years[0].year} stellte die Stadt ihr Rechnungswesen
              von der Kameralistik auf die doppelte Buchführung um. Für frühere Jahre nennt
              das Statistische Jahrbuch „Ausgaben für eigene Investitionen“, danach
              „Auszahlungen für Investitionstätigkeiten“. Die Begriffe beruhen auf
              unterschiedlichen Regelwerken. Die Werte lassen sich zeitlich einordnen,
              aber nicht zu einer einheitlich berechneten Reihe verbinden.
            </p>
          </section>
          <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              {alleFehlend.length === 1
                ? `${alleFehlend[0].year} kann nicht ausgewiesen werden`
                : "Nicht ausweisbare Jahrgänge"}
            </p>
            <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Für {alleFehlend.map((l) => l.year).join(", ")} ergeben die einzelnen
              Auszahlungsarten in der Quelltabelle nicht den Betrag, der daneben als
              Summe ausgewiesen ist.{" "}
              {/* Die gemessene Weite der Lücke — aus den Daten, nicht aus dem
                  Gedächtnis. Ohne Messung im Bestand bleibt der Satz weg. */}
              {gemesseneLuecken.length > 0 && (
                <>Gemessen sind es{" "}
                  {gemesseneLuecken.map((l, i) => (
                    <span key={l.year}>
                      {i > 0 && (i === gemesseneLuecken.length - 1 ? " und " : ", ")}
                      {gemesseneLuecken.length > 1 && `${l.year}: `}
                      {deMioEuro(Math.abs(l.difference!))}&#8239;Mio.&nbsp;€
                    </span>
                  ))}
                  {" "}Unterschied.{" "}
                </>
              )}
              Welche Zahl danebenliegt, sagt die Tabelle nicht, und eine zweite Quelle
              gibt es nicht — deshalb {alleFehlend.length === 1
                ? "steht der Jahrgang"
                : "stehen die Jahrgänge"}{" "}
              als beschriftete Lücke im Diagramm. Einen Wert schätzen wir nicht.
            </p>
          </section>
        </div>

        {/* Wofür — der jüngste Jahrgang aufgeschlüsselt. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <Anteilsbalken
            titel={`Wofür ${letzter.year}`}
            segmente={letzter.arten.map((a, i) => ({
              label: a.titel, wert: a.amount / 1e6,
              farbe: TOENE[Math.min(i, TOENE.length - 1)],
            }))}
            gesamt={letzter.total / 1e6}
          />
          {/* „Sonstige Investitionstätigkeit" ist in den jüngeren Jahrgängen
              einer der größten Posten. Was darin steckt, sagt das Jahrbuch
              nicht — und diese Grenze gehört an die Zahl, nicht in eine
              Fußnote. */}
          <p className="mt-3 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Die Bezeichnungen sind die der Quelle. Was hinter „Sonstige
            Investitionstätigkeit“ steckt, schlüsselt das Statistische Jahrbuch nicht
            weiter auf — und es ist in den jüngeren Jahrgängen einer der größten Posten.
            Auch die anderen Zeilen nennen kein einzelnes Vorhaben: „Baumaßnahmen“ sagt
            nicht, welche Schule.
          </p>
        </section>


        {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. */}
        <section className="@container rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Was diese Zahlen nicht sagen
          </p>
          <ul className="mt-2 grid list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:grid-cols-2">
            <li>
              <strong>Nicht die ganze Bautätigkeit der Stadt.</strong> Gezählt wird die
              Kernverwaltung. Was der Eigenbetrieb Gebäudewirtschaft und Hochbau baut —
              seit {juengste.years[0].year} ein großer Teil des städtischen Hochbaus —,
              steht hier nicht, und die städtischen Gesellschaften ebenso wenig. Was
              neben dem Haushalt noch läuft, zeigt{" "}
              <Link href="/haushalt/konzern" className="font-semibold text-primary">
                „Und ist das die ganze Stadt?“
              </Link>
            </li>
            <li>
              <strong>Kein einzelnes Vorhaben.</strong> Die Tabelle sagt „Baumaßnahmen:
              16,2 Mio. €“, nicht welche Straße. Einzelne Vorhaben stehen auf der
              Planseite{" "}
              <Link href="/haushalt/investitionen" className="font-semibold text-primary">
                „Was wird gebaut?“
              </Link>{" "}
              — dort allerdings als <em>geplant</em>, nicht als abgerechnet, und ohne
              die Schulgebäude, die beim Eigenbetrieb liegen.
            </li>
            <li>
              <strong>Ein Abfluss, kein Fortschritt.</strong> Hier steht, wann Geld die
              Kasse verlassen hat — nicht, wann gebaut wurde und schon gar nicht, ob
              etwas fertig ist. Eine Abschlagszahlung im Dezember zählt für das alte
              Jahr, auch wenn der Bagger erst im März kommt.
            </li>
            <li>
              <strong>Kein Urteil über „zu wenig“.</strong> Ob eine Stadt genug
              investiert, hängt an ihrem Bestand, ihren Aufgaben und daran, was sie sich
              leisten kann. Diese Seite zeigt den Verlauf, nicht seine Bewertung.
            </li>
          </ul>
        </section>

        <AnlagenBlock daten={data} />

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

      </div>
  );
}
