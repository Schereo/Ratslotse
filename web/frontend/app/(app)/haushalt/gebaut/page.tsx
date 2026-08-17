"use client";

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
// TODO(Datenpfad): Die H3-03-Beschriftung nennt die gemessene Differenz
// („1,3 Mio. € Differenz im Dokument"). Der Betrag entsteht beim Ingest
// (`council/investitionen_ist.py`, `lies()["verworfen"]`), wird aber nicht
// gespeichert — der Endpunkt `/council/haushalt/gebaut` liefert nur die
// Jahre. Sobald `verworfen` mit Differenz persistiert und ausgeliefert wird,
// gehört der Betrag in den Lücken-Grund; bis dahin bleibt er weg statt
// hart codiert.
//
// KEINE BEWERTUNGSFARBEN (components/grafik/hantel.tsx). Ein hoher Balken
// ist keine gute Nachricht und ein niedriger keine schlechte: 2020 steht
// oben, weil ein zweistelliger Millionenbetrag unter „Sonstige
// Investitionstätigkeit" fällt — was das ist, sagt die Quelle nicht, und wir
// erfinden es nicht dazu.

import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  GebautDaten, Herkunft, deMioEuro, groessterPosten,
  herkunftVon, juengsteReihe, reihen,
} from "@/lib/haushalt-gebaut";
import { NahtSaeulen, type NahtJahr } from "@/components/grafik/naht-saeulen";
import { Anteilsbalken } from "@/components/haushalt/anteilsbalken";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";

const QUELLEN = ["gebaut"] as const;

/** Warum ein Jahrgang fehlt — der Satz am <LueckenFeld>. Ohne Betrag, s.
 *  TODO(Datenpfad) im Kopf dieser Datei. */
const LUECKE_GRUND = "verworfen: die Auszahlungsarten ergeben in der "
  + "Quelltabelle nicht die ausgewiesene Summe daneben";

/** Die Töne der „Wofür"-Aufteilung — dunkel nach hell, in der Spaltenfolge
 *  der Quelle. Neutrale Ausgaben-Rampe; sechs reichen, mehr Arten führt
 *  keine der beiden Tabellen. */
const TOENE = ["var(--hh-aus-0)", "var(--hh-aus-2)", "var(--hh-aus-4)",
  "var(--hh-aus-6)", "var(--hh-aus-1)", "var(--hh-aus-3)"];

/** Wo eine Angabe im Dokument steht — dieselbe Bauart wie auf der
 *  Schulden-Seite und bewusst nicht geteilt: Die Seiten sollen einander nicht
 *  brechen. */
function Fundstelle({ h }: { h: Herkunft | null }) {
  if (!h?.fundstelle) return null;
  return (
    <div className="border-t border-dashed border-border pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
        {h.fundstelle}{h.stand ? ` · ${h.stand}` : ""}
      </p>
    </div>
  );
}

export default function GebautPage() {
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
      for (const z of r.jahre) {
        js.push({
          jahr: z.jahr,
          teile: z.arten.map((a) => ({ art: a.titel, wert: a.betrag / 1e6 })),
        });
      }
      for (const j of r.fehlend) js.push({ jahr: j, fehlt: LUECKE_GRUND });
    }
    return js.sort((a, b) => a.jahr - b.jahr);
  }, [alle]);

  // Die Naht liegt zwischen dem letzten Jahr der älteren und dem ersten der
  // jüngeren Reihe — gerechnet aus den Daten, nicht hart codiert.
  const naht = useMemo(() => {
    const alt = aeltere[0];
    if (!alt || !juengste) return undefined;
    const links = alt.jahre[alt.jahre.length - 1].jahr;
    const rechts = juengste.jahre[0].jahr;
    return {
      zwischen: [links, rechts] as [number, number],
      text: `Links ${alt.titel}, rechts ${juengste.titel} — zwei Regelwerke `
        + `mit eigenen Auszahlungsarten und eigenen Namen. Vergleichen ja, `
        + `verrechnen nein.`,
    };
  }, [aeltere, juengste]);

  const alleFehlend = useMemo(
    () => alle.flatMap((r) => r.fehlend).sort((a, b) => a - b), [alle]);

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Investitionszahlen werden geladen …
    </div>;
  }
  if (!data || !juengste || juengste.jahre.length < 2) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite sind die Rechnungsergebnisse noch nicht eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  const letzter = juengste.jahre[juengste.jahre.length - 1];
  const erster = nahtJahre.find((j) => !("fehlt" in j));
  const hLetzter = herkunftVon(data, letzter.herkunft_id);
  const quelleUrl = hLetzter?.url ?? null;
  const gross = groessterPosten(letzter);

  return (
    <Quellenkontext schluessel={[...QUELLEN]} jahr={letzter.jahr}>
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stadtfinanzen Oldenburg · Schritt 8
            </p>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Was wurde davon wirklich gebaut?
            </h1>
            <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
              Der Haushaltsplan sagt, was die Stadt bauen und kaufen will. Hier steht,
              was im Jahr {letzter.jahr} tatsächlich abgeflossen ist:{" "}
              {deMioEuro(letzter.insgesamt)}&#8239;Mio.&nbsp;€.
            </p>
          </div>
          {quelleUrl && (
            <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
              className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
              <FileText className="h-3.5 w-3.5" /> Quelle öffnen
            </a>
          )}
        </div>

        {/* Der Kopf: die Zahl und die Abgrenzung. Die Abgrenzung ist hier so
            wichtig wie der Betrag — „60,8 Mio. € gebaut" liest sich als das
            Gesamtbild der städtischen Bautätigkeit, und das ist es nicht: Der
            Eigenbetrieb Gebäudewirtschaft baut daneben und steht nicht drin. */}
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Haushaltsjahr {letzter.jahr} · Rechnungsergebnis
          </p>
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                {deMioEuro(letzter.insgesamt)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                ausgezahlt für Investitionen<Beleg q="gebaut" />
              </p>
            </div>
            {gross && (
              <div>
                <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                  {deMioEuro(gross.betrag)}&#8239;Mio.&nbsp;€
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
          text={"Eine Stadt führt zwei Bücher. Im einen steht, was ein Jahr verbraucht: "
            + "Gehälter, Strom, Zuschüsse — und von einer neuen Schule nur der kleine "
            + "Teil, der in diesem Jahr an Wert verliert. Im anderen steht, was die "
            + "Stadt anlegt: das Grundstück, der Bau, die Feuerwehrfahrzeuge, in dem "
            + "Jahr, in dem das Geld den Konto verlässt. Diese Seite liest das zweite "
            + "Buch. Deshalb „Auszahlungen“ — und deshalb lassen sich die Beträge hier "
            + "mit denen aus dem ersten Buch nicht zusammenzählen."}
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
              {erster?.jahr}&nbsp;bis&nbsp;{letzter.jahr} — nicht die Pläne, sondern die
              Kassenlage danach.{" "}
              {naht && <>Die Naht {naht.zwischen[0]}/{naht.zwischen[1]} ist echt: Die Stadt
              wechselte das Rechnungswesen, links und rechts zählen andere Regeln.</>}
            </p>
          </div>
          <NahtSaeulen
            jahre={nahtJahre}
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
              Die Naht wird nicht geglättet
            </p>
            <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Zum 1. Januar {juengste.jahre[0].jahr} stellte die Stadt ihr Rechnungswesen
              von der Kameralistik auf die doppelte Buchführung um. Das Statistische
              Jahrbuch führt die Jahre davor in einer eigenen Tabelle, mit eigenen Posten
              und unter einem eigenen Namen — dort heißen sie „Ausgaben für eigene
              Investitionen“, hier „Auszahlungen für Investitionstätigkeiten“. Ein
              Verlauf, zwei Regelwerke: vergleichen ja, verrechnen nein. Die
              Auszahlungsarten sind im Bild zu Gruppen gebündelt; die Ableseleiste
              trennt alle.
            </p>
          </section>
          <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              {alleFehlend.length === 1
                ? `${alleFehlend[0]} ist verworfen — im Bild, nicht in der Fußnote`
                : "Verworfene Jahrgänge — im Bild, nicht in der Fußnote"}
            </p>
            <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Für {alleFehlend.join(", ")} ergeben die einzelnen Auszahlungsarten in der
              Quelltabelle nicht den Betrag, der daneben als Summe ausgewiesen ist.
              Welche Zahl danebenliegt, sagt die Tabelle nicht, und eine zweite Quelle
              gibt es nicht — deshalb {alleFehlend.length === 1
                ? "steht der Jahrgang"
                : "stehen die Jahrgänge"}{" "}
              als beschriftete Lücke im Bild statt in geschätzter Höhe. Lieber eine
              Lücke als eine Zahl, die sich selbst widerspricht.
            </p>
          </section>
        </div>

        {/* Wofür — der jüngste Jahrgang aufgeschlüsselt. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <Anteilsbalken
            titel={`Wofür ${letzter.jahr}`}
            segmente={letzter.arten.map((a, i) => ({
              label: a.titel, wert: a.betrag / 1e6,
              farbe: TOENE[Math.min(i, TOENE.length - 1)],
            }))}
            gesamt={letzter.insgesamt / 1e6}
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

        {/* Warum hier keine Quote steht — eigener Block, kein Kleingedrucktes.
            Es ist die Zahl, nach der jede Leserin als Nächstes sucht. */}
        <section className="rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Warum hier keine „Umsetzungsquote“ steht
          </p>
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Naheliegend wäre, diese Beträge gegen den Plan zu rechnen und daraus einen
            Prozentsatz zu machen — „so viel vom Geplanten wurde gebaut“. Diese Zahl
            steht in keinem Dokument, und ihre beiden Hälften zählen nicht dasselbe:
          </p>
          <ul className="mt-2 flex max-w-[76ch] list-disc flex-col gap-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90">
            <li>
              <strong>Der Plan</strong> steht im Finanzhaushalt des Haushaltsplans,
              gegliedert nach Teilhaushalten — also danach, welches Amt das Geld
              ausgibt.{" "}
              <Link href="/haushalt/investitionen" className="font-semibold text-primary">
                Was wird gebaut?
              </Link>{" "}
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
            und keine sagt, dass ihre Gesamtsumme dieselbe Menge zählt. Beide Seiten
            stehen deshalb nebeneinander und nicht in einem Bruch.
          </p>
        </section>

        {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. */}
        <section className="rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Was diese Zahlen nicht sagen
          </p>
          <ul className="mt-2 flex max-w-[76ch] list-disc flex-col gap-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90">
            <li>
              <strong>Nicht die ganze Bautätigkeit der Stadt.</strong> Gezählt wird die
              Kernverwaltung. Was der Eigenbetrieb Gebäudewirtschaft und Hochbau baut —
              seit {juengste.jahre[0].jahr} ein großer Teil des städtischen Hochbaus —,
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

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
      </div>
    </Quellenkontext>
  );
}
