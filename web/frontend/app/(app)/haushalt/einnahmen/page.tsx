"use client";

// /haushalt/einnahmen — „Woher kommt das Geld?" (Design H2-07, davor H-13).
//
// Die Landkarte aller Einnahmequellen. Neu in dieser Runde: Sie sind nicht
// mehr nach Betrag sortiert, sondern **nach Entscheidungsmacht gruppiert**.
//
// Warum das die eigentliche Arbeit ist: Nach Betrag sortiert trug jede Karte
// ihr Spielraum-Zeichen selbst — man musste sieben Karten lesen und im Kopf
// zusammenzählen, um die Aussage zu bekommen. Jetzt ist die Gruppierung die
// Aussage, und das Zeichen steht einmal an der Abschnittsüberschrift.
//
// Beträge sind IST-Werte des jüngsten Jahres (Open-Data), keine Planwerte —
// das steht auch so auf der Seite.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltDaten, deMio, spendenGremien, spendenJahre, spendenLaufend } from "@/lib/haushalt";
import { ZeitreiheMini } from "@/components/grafik/zeitreihe";
import { LueckenFeld } from "@/components/grafik/luecken-feld";
import { SPIELRAUM_LABEL, STEUERARTEN, Spielraum } from "@/lib/haushalt-steuern";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { FinanzausgleichDaempfer } from "@/components/haushalt/finanzausgleich-daempfer";
import { ZuweisungDreiteilig } from "@/components/haushalt/zuweisung-dreiteilig";
import { cn } from "@/lib/utils";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

/** Drei Striche als Spielraum-Marke — gefüllt, halb, gestrichelt.
 *
 *  `hoch` ist die Balkenhöhe in Viertel-rem: an der Abschnittsüberschrift
 *  klein (Wiedererkennung), in der Legende noch kleiner. */
function SpielraumMarke({ stufe, klasse }: { stufe: Spielraum; klasse: string }) {
  const gefuellt = stufe === "frei" ? 3 : stufe === "begrenzt" ? 2 : 0;
  return (
    <span className="flex flex-none gap-0.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span key={i} className={cn(
          "w-1 rounded-sm", klasse,
          i < gefuellt
            ? stufe === "frei" ? "bg-[color:var(--hh-ein-0)]" : "bg-[color:var(--hh-ein-2)]"
            : stufe === "keiner" ? "border border-dashed border-border" : "bg-muted",
        )} />
      ))}
    </span>
  );
}

/** Was die drei Stufen bedeuten — eine Zeile, die den Gruppentitel trägt.
 *
 *  Bewusst kein Text über „die meisten Einnahmen": Welche Gruppe wie groß
 *  ist, rechnet die Seite unten aus den Daten aus. */
const GRUPPEN: { stufe: Spielraum; titel: string; text: string }[] = [
  {
    stufe: "frei",
    titel: "Der Rat entscheidet",
    text: "Der Rat beschließt den Satz selbst — jedes Jahr mit dem Haushalt.",
  },
  {
    stufe: "begrenzt",
    titel: "Begrenzt",
    text: "Der Rat beschließt, darf aber gesetzlich nicht frei wählen.",
  },
  {
    stufe: "keiner",
    titel: "Kein Einfluss",
    text: "Höhe und Verteilung legen Bund und Land fest.",
  },
];

export default function EinnahmenPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Einnahmen werden geladen …</div>;
  }

  const jahr = Math.max(...data.steuern.map((s) => s.jahr), 0);
  const betragFuer = (art: string | null) => {
    if (!art) return null;
    return data.steuern.find((s) => s.jahr === jahr && s.art === art)?.betrag ?? null;
  };
  const zuweisungJahr = data.steuerkraft.filter((k) => k.zuweisungen != null).at(-1);
  // Der vollständige Ausgleich aus den Tabellen des Landes (Tausend Euro).
  // Optional: Ohne einen Lauf von scripts/ingest_staedtevergleich.py ist das
  // Feld leer, und die Seite zeigt weiter nur die Schlüsselzuweisungen.
  const ausgleich = (data.finanzausgleich ?? []).filter((f) => f.nettobetrag != null).at(-1);
  const gesamt = data.steuern.find((s) => s.jahr === jahr && s.art === "insgesamt")?.betrag ?? null;

  // Karten: Betrag aus den Daten, innerhalb der Gruppe nach Betrag sortiert
  // (Quellen ohne Zahl ans Ende).
  const karten = STEUERARTEN.map((a) => ({
    art: a,
    betrag: a.slug === "schluesselzuweisungen" ? zuweisungJahr?.zuweisungen ?? null : betragFuer(a.datenArt),
    jahr: a.slug === "schluesselzuweisungen" ? zuweisungJahr?.jahr ?? jahr : jahr,
  })).sort((a, b) => (b.betrag ?? -1) - (a.betrag ?? -1));

  const gruppen = GRUPPEN
    .map((g) => ({ ...g, karten: karten.filter((k) => k.art.spielraum === g.stufe) }))
    .filter((g) => g.karten.length > 0);
  const frei = karten.filter((k) => k.art.spielraum === "frei").length;

  const spendenReihe = spendenJahre(data);
  const spendenLauf = spendenLaufend(data);
  const spendenGrem = spendenGremien(data);
  const spendenOhne = data.spenden?.ohne_beleg ?? [];
  const spendenLetztes = spendenReihe[spendenReihe.length - 1];
  const spendenGeld = spendenGrem.Rat.betrag + spendenGrem.Verwaltungsausschuss.betrag;

  const quellen: QuellenSchluessel[] = ["steuern", "steuerkraft", "hebesaetze",
    ...(spendenReihe.length ? (["spenden"] as const) : [])];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Woher das Geld kommt</span>
      </div>

      <div className="@container/kopf">
        {/* Die Überschrift zählt aus den Daten. Der Entwurf schrieb „drei von
            neun" fest — es sind weder drei noch neun, und beides ändert sich,
            sobald eine Einnahmeart dazukommt. */}
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">
          Bei {frei} von {karten.length} Einnahmequellen kann der Rat wirklich drehen
        </h1>
        {/* Zwei Absätze, zwei Spalten: Der Aufhänger und der Jahres-Hinweis
            sagen Verschiedenes und standen untereinander — zusammen nutzten
            sie 618 von 1136 px, rechts blieb die halbe Seite leer. Die
            Zeilenlänge bleibt, wo sie war (66–70 Zeichen); sie zu verbreitern
            hätte den Platz gefüllt und das Lesen verschlechtert. Schwelle am
            CONTAINER, nicht am Fenster (Designsprache §4): Am Desktop liegt
            der Kopf neben der 240-px-Seitenleiste, auf dem iPad nicht —
            dieselbe Fensterbreite meint zwei verschiedene Platzangebote, und
            bei 1024 px Fenster wären zwei Spalten je 344 px breit. */}
        <div className="mt-2 grid gap-x-8 gap-y-2 @5xl/kopf:grid-cols-2">
          <p className="max-w-[70ch] text-sm leading-relaxed text-foreground/90">
            Die Debatte „die Stadt soll sich das Geld doch besorgen“ läuft meistens an den
            Zuständigkeiten vorbei. Deshalb sortieren wir die Einnahmequellen nicht nach Größe,
            sondern <strong>nach Entscheidungsmacht</strong>. Gezählt sind Quellen, nicht Euro.
          </p>
          {/* Der Jahres-Sprung gehört nach oben, nicht ans Seitenende. Wer von
              der Übersicht kommt, hat dort Planzahlen des kommenden Jahres
              gesehen; hier stehen abgerechnete Werte eines früheren. Ohne den
              Hinweis liest man beide Seiten als dieselbe Rechnung und wundert
              sich über die Differenz. */}
          <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Achtung beim Jahr: Bei den Steuern stehen hier <strong>abgerechnete Beträge
            aus {jahr}</strong> — was wirklich geflossen ist. Die Übersicht zeigt dagegen den
            <em>Plan</em> für ein späteres Jahr. Beide Zahlen sind richtig, sie beantworten nur
            verschiedene Fragen. Jede Karte nennt ihr Jahr selbst — die Schlüsselzuweisungen
            laufen dem Rest voraus.
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
        <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          Spielraum des Rats
        </p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
          {(["frei", "begrenzt", "keiner"] as Spielraum[]).map((s) => (
            <span key={s} className="inline-flex items-center gap-2 text-[11.5px]">
              <SpielraumMarke stufe={s} klasse="h-3" />
              {SPIELRAUM_LABEL[s]}
            </span>
          ))}
        </div>
      </div>

      {gruppen.map((g) => (
        <div key={g.stufe}>
          <div className="mb-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <SpielraumMarke stufe={g.stufe} klasse="h-4" />
            <span className="text-[14.5px] font-bold">{g.titel}</span>
            <span className="text-[12.5px] text-muted-foreground">{g.text}</span>
            <span className="hidden h-px flex-1 bg-border sm:block" />
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {g.karten.map(({ art, betrag, jahr: bJahr }) => (
              <Link key={art.slug} href={`/haushalt/steuer?art=${art.slug}`}
                className={cn(
                  "flex flex-col rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/40",
                  // Die erste Gruppe trägt einen Primär-Tint: Sie ist die
                  // Antwort auf die Frage, mit der Leute herkommen.
                  g.stufe === "frei" ? "border-primary/25 bg-primary/[0.04]" : "border-border",
                )}>
                <p className="text-[13px] font-bold leading-snug">{art.titel}</p>
                {betrag != null ? (
                  <p className="mt-1.5 font-display text-[20px] font-bold leading-none tracking-tight tabular-nums">
                    {deMio(betrag / 1e6)}
                    <span className="text-[11px] font-semibold text-muted-foreground">
                      &#8239;Mio.
                    </span>
                    <span className="ml-1 font-sans text-[10px] font-normal text-muted-foreground">
                      {bJahr}
                      <Beleg q={art.slug === "schluesselzuweisungen" ? "steuerkraft" : "steuern"} />
                    </span>
                  </p>
                ) : (
                  <p className="mt-1.5 text-[12px] text-muted-foreground">
                    Betrag noch nicht eingelesen
                  </p>
                )}
                <p className="mt-1.5 text-[11.5px] leading-snug text-foreground/75">{art.stellschraube}</p>
                <p className="mt-auto pt-1.5 text-[11.5px] font-semibold text-primary">Steckbrief öffnen →</p>
              </Link>
            ))}
          </div>
        </div>
      ))}

      {/* Der Dämpfer schließt die Seite ab, weil er erklärt, warum selbst die
          erste Gruppe weniger Spielraum hat, als sie verspricht. Er nennt
          bewusst keinen Faktor — Begründung im Kopf der Komponente. */}
      <FinanzausgleichDaempfer steuerkraft={data.steuerkraft} />

      {/* Direkt unter der Kurve, weil er sie einordnet: Was dort als
          „Schlüsselzuweisungen" steht, sind zwei von drei Komponenten. Der
          Block ersetzt die Zahl nicht, er stellt die vollständige daneben
          (council/steuerkraft.py). */}
      <ZuweisungDreiteilig reihe={data.finanzausgleich} />

      {/* Der Satz verglich bis 16.08. die Steuern eines Ist-Jahres mit den
          Ausgaben eines Planjahres („deckt nur einen Teil dessen, was die
          Stadt ausgibt") — zwei Zahlen aus zwei Rechnungen, deren Differenz
          nichts bedeutet. Jetzt bleibt der Vergleich innerhalb derselben
          Quelle: Steuern gegen Steuern plus Zuweisungen.

          Die Zuweisungen tragen ihr eigenes Jahr im Satz, seit die
          Jahres-Korrektur am Datensatz 1106 die beiden Reihen auseinander-
          gezogen hat: Die Steuern enden beim letzten abgerechneten Jahr, der
          Finanzausgleich steht schon für das laufende Ausgleichsjahr fest.
          Ein gemeinsames „brachten 2025" wäre für eine der beiden Zahlen
          falsch. */}
      {gesamt != null && (
        <LottiErklaert
          titel="Was diese Beträge zusammen sind — und was nicht"
          /* Seit 17.08. nennt der Satz den VOLLEN Ausgleich, wenn er vorliegt:
             Die Schlüsselzuweisungen allein sind zwei von drei Komponenten,
             und ein Satz, der ausdrücklich zusammenzählt, darf nicht die
             engere Zahl nehmen. Fehlt der Landesbestand (frische Datenbank),
             bleibt es bei der bisherigen Formulierung — samt dem Wort
             „Schlüsselzuweisungen", das dann auch genau stimmt. */
          text={`Alle Steuern zusammen brachten ${jahr} rund ${deMio(gesamt / 1e6)} Millionen Euro`
            + (ausgleich?.nettobetrag
              ? `. Dazu kommen die Zuweisungen des Landes: für das Ausgleichsjahr `
                + `${ausgleich.jahr} rund ${deMio(ausgleich.nettobetrag / 1000)} Millionen `
                + `— Schlüsselzuweisungen für Gemeinde- und Kreisaufgaben plus die `
                + `Zuweisungen für übertragene staatliche Aufgaben`
              : zuweisungJahr?.zuweisungen
                ? `. Dazu kommen die Schlüsselzuweisungen des Landes: für das Ausgleichsjahr `
                  + `${zuweisungJahr.jahr} rund ${deMio(zuweisungJahr.zuweisungen / 1e6)} Millionen`
                : "")
            + ". Das ist noch nicht alles, was die Stadt einnimmt: Gebühren, Kostenerstattungen"
            + " und zweckgebundene Zuschüsse kommen hinzu, und die stehen nicht in diesen"
            + " Datensätzen. Die Gesamtsumme aller Einnahmen steht auf der Übersicht."}
        />
      )}

      {/* „Auch das sind Einnahmen" — die Zuwendungen, die die Stadt annimmt.
          Steht bewusst direkt hinter dem Erklärkasten: Dessen Schlusssatz
          sagt, dass die Steuern nicht alles sind, und das hier ist ein Posten,
          den sonst niemand ausweist.

          Klein gehalten, und zwar aus zwei Gründen. Erstens ist der Betrag
          klein: 0,8 Mio. € neben rund 280 Mio. € Steuern — eine große Kachel
          behauptete ein Gewicht, das die Zahl nicht hat. Zweitens ist die
          eigentliche Auskunft nicht die Summe, sondern die Aufteilung: gleich
          viele Vorlagen in beiden Gremien, fast das ganze Geld beim Rat. Das
          ist die Schwelle von 2.000 Euro, sichtbar gemacht.

          Was hier NICHT steht: wer gespendet hat. Die Namen stehen nur in der
          Anlage „Zuwendungsliste", die nicht im Bestand ist — und der Satz
          darüber ist Teil des Blocks, nicht eine Fußnote. */}
      {spendenLetztes && (
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Auch das sind Einnahmen
          </h2>
          <div className="mt-2.5 flex flex-col gap-4 @container/spenden sm:flex-row sm:items-start sm:gap-6">
            <div className="flex-none">
              <p className="text-[12.5px] font-semibold">
                Angenommene Zuwendungen {spendenLetztes.jahr}
              </p>
              {/* Auf den Euro genau, nicht gerundet: Diese Summe IST exakt —
                  sie ist die Summe von Ratsbeschlüssen, nicht eine
                  Hochrechnung. „789 Tsd. €" wäre hier eine Ungenauigkeit, die
                  die Quelle gar nicht hat. */}
              <p className="mt-0.5 font-display text-[24px] font-bold leading-none tabular-nums">
                {Math.round(spendenLetztes.betrag).toLocaleString("de-DE")}
                <span className="ml-1 text-[13px] font-semibold text-muted-foreground">€</span>
                <Beleg q="spenden" />
              </p>
              <p className="mt-1 text-[11.5px] text-muted-foreground">
                aus {spendenLetztes.vorlagen} Beschlüssen
              </p>
            </div>
            {spendenReihe.length > 1 && (
              <div className="min-w-0 flex-1">
                {/* Endpunkt in Tausend, wie die große Zahl daneben — zwei
                    Einheiten in einem Block ließen die Kurve und die Kennzahl
                    wie zwei verschiedene Reihen aussehen. */}
                <ZeitreiheMini
                  reihe={spendenReihe.map((j) => ({ jahr: j.jahr, wert: j.betrag }))}
                  format={(v) => `${Math.round(v / 1000).toLocaleString("de-DE")} Tsd.`}
                  ariaLabel={
                    `Angenommene Zuwendungen je Jahr, ${spendenReihe[0].jahr} bis `
                    + `${spendenLetztes.jahr}: von `
                    + `${Math.round(spendenReihe[0].betrag).toLocaleString("de-DE")} auf `
                    + `${Math.round(spendenLetztes.betrag).toLocaleString("de-DE")} Euro. `
                    + `Höchststand ${Math.round(Math.max(...spendenReihe.map((j) => j.betrag)))
                      .toLocaleString("de-DE")} Euro.`}
                />
              </div>
            )}
          </div>

          <dl className="mt-3.5 flex flex-col gap-2.5 border-t border-border pt-3">
            <div>
              <dt className="text-[12.5px] font-semibold">
                Wer entscheidet, hängt an 2.000 Euro
              </dt>
              <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                Über eine einzelne Zuwendung bis 100 Euro entscheidet die
                Oberbürgermeisterin oder der Oberbürgermeister allein, bis 2.000 Euro der
                Verwaltungsausschuss, darüber der Rat. Beide Gremien behandeln seit 2018
                ungefähr gleich viele Vorlagen — {spendenGrem.Rat.vorlagen} der Rat,{" "}
                {spendenGrem.Verwaltungsausschuss.vorlagen} der Verwaltungsausschuss —,
                aber{" "}
                {spendenGeld > 0
                  ? Math.round((spendenGrem.Rat.betrag / spendenGeld) * 100)
                  : 0}{" "}
                Prozent des Geldes laufen über den Rat.
              </dd>
            </div>
            <div>
              <dt className="text-[12.5px] font-semibold">Wir zeigen die Summe, nicht die Gebenden</dt>
              <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                Wer gespendet hat und wofür, steht ausschließlich in der Anlage
                „Zuwendungsliste“ zur jeweiligen Vorlage. Die lesen wir nicht ein. Der
                Ratsbeschluss macht die Summe öffentlich — die Liste dahinter bleibt es
                nicht, und dabei bleibt es auch hier.
              </dd>
            </div>
            {spendenLauf && (
              <div>
                <dt className="text-[12.5px] font-semibold">{spendenLauf.jahr} läuft noch</dt>
                <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                  Bis jetzt {Math.round(spendenLauf.betrag).toLocaleString("de-DE")} €
                  aus {spendenLauf.vorlagen} Beschlüssen. Das Jahr steht deshalb nicht
                  in der Kurve: Es wäre ein Rückgang zu sehen, den es nicht gibt.
                </dd>
              </div>
            )}
            {spendenOhne.length > 0 && (
              <div>
                <dt className="text-[12.5px] font-semibold">
                  {spendenOhne.length}{" "}
                  {spendenOhne.length === 1 ? "Beschluss fehlt" : "Beschlüsse fehlen"} in
                  dieser Reihe
                </dt>
                {/* Der Satz sagt, was der Reihe FEHLT — nicht, dass wir gut
                    geprüft haben. „Statt ungeprüft mitzuzählen" stand hier bis
                    zuletzt und war genau die Selbstvergewisserung, die
                    DESIGNSPRACHE.md § 7 als Anti-Pattern führt. */}
                <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
                  Ihre Beträge sind in den Summen oben nicht enthalten. In diesen
                  Vorlagen steht der beschlossene Betrag entweder kein zweites Mal,
                  oder die beiden Stellen widersprechen sich:
                </dd>
                {/* <LueckenFeld> statt einer eigenen Liste: Es ist die Textform
                    für Lücken im Baukasten, und sie ist bewusst nie
                    einklappbar (H4-A). Sechs Sätze machen den Block länger —
                    das ist der Preis dafür, dass keine Vorlage stillschweigend
                    aus der Summe fällt. */}
                <dd className="mt-1.5 flex flex-col gap-1.5">
                  {spendenOhne.map((v) => (
                    <LueckenFeld
                      key={v.vorlage_nr}
                      label={v.vorlage_nr}
                      grund={v.grund}
                      datum={v.sitzung
                        ? new Date(v.sitzung).toLocaleDateString("de-DE")
                        : undefined}
                    />
                  ))}
                </dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* Bis 17.08. stand hier ein einziger Absatz von 550 Zeichen, ohne
          Rahmen zwischen zwei Karten. Er beantwortet drei verschiedene Fragen
          — welches Jahr die Beträge tragen, wessen Einteilung die drei Stufen
          sind, warum die Schlüsselzuweisungen aus der Reihe fallen —, und wer
          nur eine davon hatte, musste alle drei lesen. Jetzt trägt jede ihre
          eigene Zeile; der Wortlaut ist derselbe geblieben. */}
      <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Zum Lesen dieser Seite
        </h2>
        <dl className="mt-2.5 flex flex-col gap-2.5">
          <div>
            <dt className="text-[12.5px] font-semibold">Die Beträge sind Ist-Werte</dt>
            <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Also abgerechnete Einnahmen, nicht die Planzahlen des Haushalts. Die Aufteilung der
              geplanten Erträge nach Arten lesen wir noch ein; bis dahin zeigen wir hier lieber,
              was wirklich geflossen ist.
            </dd>
          </div>
          <div>
            <dt className="text-[12.5px] font-semibold">Die drei Stufen sind unsere Einteilung</dt>
            <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Sie ordnet die Einnahmen nach der Rechtslage — eine amtliche Kategorie ist das nicht.
            </dd>
          </div>
          <div>
            <dt className="text-[12.5px] font-semibold">Die Schlüsselzuweisungen zählen anders</dt>
            <dd className="mt-0.5 max-w-[80ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Das Land setzt sie je Ausgleichsjahr fest, deshalb steht dort auch das laufende Jahr
              schon mit einem festen Betrag — das Jahr an der Zahl sagt, welches gemeint ist.
            </dd>
          </div>
        </dl>
      </section>

      <SchrittWeiter href="/haushalt/einnahmen" />

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
