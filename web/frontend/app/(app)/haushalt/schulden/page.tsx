"use client";

// /haushalt/schulden — „Wie viel Schulden hat Oldenburg?"
//
// Eine der häufigsten Fragen an den Haushalt, und der Bereich konnte sie bis
// jetzt nicht beantworten. Die Antwort ist eine Zahl — aber sie ist nur dann
// eine Antwort, wenn danebensteht, WAS sie zählt.
//
// DIE ABGRENZUNG IST DER GANZE PUNKT. Bei Kommunalschulden gibt es zwei
// Werte, die beide „die Schulden der Stadt" heißen: die der Stadt als
// Rechtsträger (Kernhaushalt plus Eigenbetriebe — das hier) und die des
// Konzerns mit allen Beteiligungen. Sie unterscheiden sich um ein Vielfaches.
// Deshalb steht die Abgrenzung nicht im Kleingedruckten, sondern direkt an
// der großen Zahl, und deshalb kommt ihr Wortlaut aus dem Backend
// (`council/schulden.py`) statt aus dieser Datei: Zwei Formulierungen für
// dieselbe Grenze wären zwei Grenzen.
//
// KEINE DRAMATISIERUNG, und das ist hier keine Zurückhaltung, sondern
// Genauigkeit: Über dreißig Jahre sind die Schulden absolut gestiegen und je
// Einwohner*in gesunken — die Stadt ist in derselben Zeit stark gewachsen.
// Wer nur die absolute Kurve zeigt, verkauft Bevölkerungswachstum als
// Schuldenaufbau. Deshalb der Umschalter, und deshalb nennt der Fließtext
// beide Richtungen.
//
// KEINE BEWERTUNGSFARBEN (components/grafik/hantel.tsx). Kein Rot für
// „viel". Die beiden größten Sprünge der Reihe zeigen, warum: 2001 fiel die
// Schuld um 139 Mio., weil die Stadt die Stadtentwässerung abgab — kein
// Sparerfolg. 2010 sprang eine Spalte um 100 Mio., ohne dass sich die Summe
// bewegte — eine Umbuchung. Farbe kann das nicht unterscheiden, Text schon.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { deMio } from "@/lib/haushalt";
import {
  Ansicht, Herkunft, SchuldenDaten, aufteilungen, deEuro, herkunftVon,
  juengsteZinslast, ohneAufteilung, punkte,
} from "@/lib/haushalt-schulden";
import { SchuldenKurve } from "@/components/haushalt/schulden-kurve";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";

const QUELLEN = ["schulden"] as const;

/** Wo eine Angabe im Dokument steht: welcher Abschnitt, welcher Stand. Das
 *  Quellenverzeichnis am Seitenende beschreibt die Quelle der ganzen Seite;
 *  das hier gehört an die einzelne Zahl und ist der Grund, warum man sie in
 *  einem mehrseitigen PDF wiederfindet.
 *
 *  BEWUSST OHNE UNSERE PROBEN. Die erste Fassung dieser Seite zeigte hier die
 *  Sätze aus `herkunft.PROBEN` und darunter „Gemessen: Summenprobe 30 von
 *  31". Das sagt etwas über uns und nichts über die Schulden der Stadt —
 *  Selbstvergewisserung (DESIGNSPRACHE.md § 7), und `konzern/page.tsx` hat
 *  denselben Block am 16.08. aus demselben Grund verloren. Die Proben laufen
 *  unverändert weiter, die API liefert sie weiter, Tests halten sie fest und
 *  die Technik-Doku beschreibt sie. Nur die Zurschaustellung ist weg.
 *
 *  Was **inhaltlich** aus einer gerissenen Probe folgt, bleibt selbstver-
 *  ständlich stehen: dass für 2022 die Aufteilung fehlt, steht als Satz an
 *  der Aufteilung — das ist eine Grenze der Zahlen und keine Auskunft über
 *  unsere Sorgfalt.
 *
 *  Bewusst dieselbe Bauart wie in `konzern/page.tsx` und `vergleich/page.tsx`
 *  und bewusst nicht geteilt — die drei Seiten sollen einander nicht brechen. */
function Fundstelle({ h }: { h: Herkunft | null }) {
  // Ohne Fundstelle nichts — sonst bliebe eine Überschrift ohne Inhalt stehen.
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

export default function SchuldenPage() {
  const { data, loading } = useFetch<SchuldenDaten>("/council/haushalt/schulden");
  const [ansicht, setAnsicht] = useState<Ansicht>("insgesamt");

  const reihe = data?.reihe ?? [];
  const kurve = useMemo(() => punkte(reihe, ansicht), [reihe, ansicht]);
  const teilung = useMemo(() => aufteilungen(reihe), [reihe]);
  const luecken = useMemo(() => ohneAufteilung(reihe), [reihe]);
  // Die Zinslinie in der Kurve (H4-13) — nur in der absoluten Ansicht: Die
  // Quelle weist keinen Pro-Kopf-Zins aus, und wir dividieren nicht selbst.
  const zinsreihe = useMemo(
    () => (ansicht === "insgesamt"
      ? (data?.zinslast ?? []).map((z) => ({ jahr: z.jahr, wert: z.aufwand / 1e6 }))
      : undefined),
    [data, ansicht]);

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Schuldenzahlen werden geladen …
    </div>;
  }
  // Ohne eingelesene Zeitreihe gibt es diese Seite nicht — lieber ein
  // ehrlicher Hinweis als eine Seite voller Striche.
  if (!data || reihe.length < 2) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite ist die Schuldenzeitreihe noch nicht eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  const letzter = reihe[reihe.length - 1];
  const erster = reihe[0];
  const hLetzter = herkunftVon(data, letzter.herkunft_id);
  const quelleUrl = hLetzter?.url ?? null;

  // Die Richtungen über die ganze Reihe — gerechnet, nicht geschrieben: Eine
  // Seite, die „gestiegen" als Text trägt, wird mit dem nächsten Jahrgang
  // still falsch.
  const deltaAbs = letzter.insgesamt - erster.insgesamt;
  const proKopfDa = letzter.je_einwohner != null && erster.je_einwohner != null;
  const deltaKopf = proKopfDa ? letzter.je_einwohner! - erster.je_einwohner! : null;
  const gegenlaeufig = deltaKopf != null && Math.sign(deltaAbs) !== Math.sign(deltaKopf);

  // Der jüngste Jahrgang mit belegter Aufteilung — die Aufteilung ist nicht
  // für jedes Jahr gedeckt, und der Kopf soll dann nicht leer bleiben.
  const jTeilung = teilung.at(-1) ?? null;

  return (
    <Quellenkontext schluessel={[...QUELLEN]} jahr={letzter.jahr}>
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stadtfinanzen Oldenburg
            </p>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Wie viel Schulden hat Oldenburg?
            </h1>
            <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
              Ende {letzter.jahr} waren es {deMio(letzter.insgesamt / 1e6)}&#8239;Mio.&nbsp;€.
              Was diese Zahl zählt und was nicht, steht direkt darunter — bei Schulden
              ist das der Unterschied zwischen zwei Antworten.
            </p>
          </div>
          {quelleUrl && (
            <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
              className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
              <FileText className="h-3.5 w-3.5" /> Quelle öffnen
            </a>
          )}
        </div>

        {/* Der Kopf: zwei Zahlen und die Abgrenzung. Mehr nicht — die
            Abgrenzung ist hier so wichtig wie die Beträge und steht deshalb
            in derselben Karte, nicht in einer Fußnote weiter unten. */}
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stand 31.12.{letzter.jahr}
          </p>
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                {deMio(letzter.insgesamt / 1e6)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                insgesamt<Beleg q="schulden" />
              </p>
            </div>
            {letzter.je_einwohner != null && (
              <div>
                <p className="font-display text-[28px] font-bold leading-none tracking-tight tabular-nums sm:text-[32px]">
                  {deEuro(letzter.je_einwohner)}&nbsp;€
                </p>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  je Einwohner*in<Beleg q="schulden" />
                </p>
              </div>
            )}
          </div>
          {/* Der Wortlaut kommt aus dem Backend — s. Kopfkommentar. */}
          <p className="max-w-[76ch] rounded-xl bg-muted/60 px-3 py-2.5 text-[13px] leading-relaxed text-foreground/90">
            <strong>Gezählt wird:</strong> {data.abgrenzung}
          </p>
          {letzter.revidiert === 1 && (
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              Die Stadt hat die Werte für {letzter.jahr} nachträglich korrigiert; hier steht
              der korrigierte Stand.
            </p>
          )}
          <Fundstelle h={hLetzter} />
        </section>

        {/* WAS DER BESTAND IM JAHR KOSTET.
            Der Schuldenstand allein sagt wenig — 337 Mio. € sind eine Zahl ohne
            Erfahrungswert. Die Zinslast übersetzt sie in etwas, das jedes Jahr
            im Haushalt steht und mit allem anderen konkurriert.

            Sie kommt aus einer ANDEREN Quelle als der Bestand darüber: Der
            Stand steht im Statistischen Jahrbuch, die Zinsen im geprüften
            Jahresabschluss. Deshalb ein eigener Beleg und ein eigenes Jahr —
            die Abschlüsse enden früher als die Zeitreihe, und beide am selben
            Jahr aufzuhängen hieße, für die Zinsen dauerhaft nichts zu zeigen. */}
        {(() => {
          const zins = juengsteZinslast(data);
          if (!zins) return null;
          const hZins = herkunftVon(data, zins.herkunft_id);
          return (
            <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Was der Schuldenstand im Jahr kostet
              </p>
              <p className="mt-2 font-display text-[26px] font-extrabold leading-none tracking-tight text-foreground">
                {deMio(zins.aufwand / 1e6)}&#8239;Mio.&nbsp;€
              </p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
                Zinsen im Jahr {zins.jahr} — aus dem Jahresabschluss
                <Beleg q="jahresabschluss" />, nicht aus der Reihe oben.
              </p>
              <p className="mt-2.5 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
                <strong>Zinsen, nicht Tilgung.</strong> Was die Stadt an ihren Krediten
                zurückzahlt, mindert den Schuldenstand und ist kein Aufwand — es steht im
                Finanzhaushalt und nicht in dieser Rechnung. Beide Beträge zusammenzuzählen
                ergäbe eine Zahl, die in keinem Dokument steht.
              </p>
              <Fundstelle h={hZins} />
            </section>
          );
        })()}

        <LottiErklaert
          titel="Warum es zwei Schuldenzahlen gibt"
          text={"Die Stadt hat Betriebe, die zu ihr gehören, und Gesellschaften, die ihr "
            + "gehören. Das ist nicht dasselbe: Ein Eigenbetrieb wie die Gebäudewirtschaft "
            + "ist rechtlich die Stadt — seine Schulden sind ihre Schulden. Eine GmbH oder "
            + "eine Anstalt wie das Klinikum ist eine eigene Rechtsperson und schuldet für "
            + "sich. Diese Seite zählt die erste Sorte mit und die zweite nicht. Deshalb "
            + "verschwanden die Kliniken 1999 aus der Reihe: Nicht ihre Schulden waren weg, "
            + "sondern ihre Rechtsform war eine andere geworden."}
        />

        {/* Die Zeitreihe */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {erster.jahr} bis {letzter.jahr}
          </p>
          <Segmented<Ansicht>
            value={ansicht}
            onChange={setAnsicht}
            options={[
              { value: "insgesamt", label: "Insgesamt" },
              { value: "je_einwohner", label: "Je Einwohner*in" },
            ]}
          />
        </div>
        <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
          {/* Zinslinie und 2010-Annotation direkt im Bild (H4-13): Was der
              Bestand im Jahr kostet, auf derselben Skala — und der Knick von
              2010 mit seiner Erklärung am Ort des Knicks. Der ganze Satz samt
              Beleg steht darunter in „Zwei Sprünge, die keine Politik waren". */}
          <SchuldenKurve
            punkte={kurve}
            ansicht={ansicht}
            zweitreihe={zinsreihe}
            zweitreiheLabel="Zinslast p. a."
            annotationen={ansicht === "insgesamt" ? [{
              jahr: 2010,
              kurz: "108,9 Mio. umgebucht",
              text: "2010 übertrug die Stadt 108,9 Mio. € Kredite an den neuen "
                + "Eigenbetrieb Gebäudewirtschaft — eine Spalte sprang, die Summe "
                + "kaum. Kein Tilgungswunder.",
            }] : []}
          />
          {/* Die beiden Richtungen nebeneinander — der Grund, warum es den
              Umschalter überhaupt gibt. Gerechnet, nicht geschrieben. */}
          {gegenlaeufig && (
            <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Über {letzter.jahr - erster.jahr} Jahre gehen die beiden Ansichten
              auseinander: Insgesamt hat die Stadt heute{" "}
              {deMio(Math.abs(deltaAbs) / 1e6)}&#8239;Mio.&nbsp;€{" "}
              {deltaAbs > 0 ? "mehr" : "weniger"} Schulden als {erster.jahr}, je
              Einwohner*in aber {deEuro(Math.abs(deltaKopf!))}&nbsp;€{" "}
              {deltaKopf! > 0 ? "mehr" : "weniger"} — die Zahl der Einwohner*innen ist in
              derselben Zeit gewachsen.
            </p>
          )}
          <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Alle Beträge in Euro des jeweiligen Jahres — die Teuerung ist nicht
            herausgerechnet. Ein Teil der Bewegung ist also verändertes Preisniveau.
          </p>
        </section>

        {/* Was hinter den zwei größten Sprüngen steckt. Beides steht als
            Fußnote in der Quelltabelle — deshalb darf es hier stehen. Ohne
            diesen Block liest sich die Kurve als Spar- und Schuldenpolitik,
            und beides wäre falsch. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Zwei Sprünge, die keine Politik waren
          </p>
          <ul className="mt-2 flex max-w-[76ch] list-disc flex-col gap-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90">
            <li>
              <strong>2001 fiel die Schuld um mehr als die Hälfte.</strong> Die Stadt
              übertrug die Stadtentwässerung an den Oldenburgisch-Ostfriesischen
              Wasserverband; der übernahm dabei Darlehen über 139,5&#8239;Mio.&nbsp;€.
              Kein Abbau, sondern ein Übergang mit der Aufgabe.<Beleg q="schulden" />
            </li>
            <li>
              <strong>2010 verschob sich eine Spalte um 108,9&#8239;Mio.&nbsp;€</strong>,
              ohne dass die Summe folgte: Die Stadt gründete den Eigenbetrieb
              Gebäudewirtschaft und Hochbau und übertrug ihm diesen Teil ihres
              Kreditportfolios. Dieselbe Stadt, dieselben Schulden, andere
              Spalte.<Beleg q="schulden" />
            </li>
          </ul>
        </section>

        {/* Die Aufteilung — nur wo sie belegt ist. */}
        {jTeilung && (
          <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Wer schuldet was ({jTeilung.jahr})
              </p>
              <span className="font-mono text-[10px] uppercase text-muted-foreground">
                {teilung.length} von {reihe.length} Jahren aufgeschlüsselt
              </span>
            </div>
            {/* --hh-aus-0 und --hh-aus-2, NICHT aus-3: Die Segmente tragen
                eine Beschriftung, und dafür verlangt die Designsprache (§4)
                4,5 : 1 gegen `--hh-seg-text`. Gemessen am 16.08.2026 hält
                aus-2 das in beiden Themes (hell 4,72 · dunkel 5,76), aus-3
                in keinem (3,18 · 4,04). */}
            <div className="mt-3 flex h-7 w-full overflow-hidden rounded-lg">
              {([
                ["Verwaltung", jTeilung.kern, "var(--hh-aus-0)"],
                ["Eigenbetriebe", jTeilung.eigenbetriebe, "var(--hh-aus-2)"],
              ] as const).map(([label, wert, farbe]) => {
                const anteil = (wert / (jTeilung.kern + jTeilung.eigenbetriebe)) * 100;
                return (
                  <div key={label} className="flex items-center px-2"
                    style={{ width: `${anteil}%`, background: farbe }}>
                    {anteil > 18 && (
                      <span className="truncate font-mono text-[10.5px] font-semibold"
                        style={{ color: "var(--hh-seg-text)" }}>
                        {Math.round(anteil)}&nbsp;%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <dl className="mt-2.5 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px]">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 flex-none rounded-sm"
                  style={{ background: "var(--hh-aus-0)" }} />
                <dt className="text-muted-foreground">Verwaltung</dt>
                <dd className="font-semibold tabular-nums">
                  {deMio(jTeilung.kern / 1e6)}&#8239;Mio.&nbsp;€
                </dd>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 flex-none rounded-sm"
                  style={{ background: "var(--hh-aus-2)" }} />
                <dt className="text-muted-foreground">Eigenbetriebe</dt>
                <dd className="font-semibold tabular-nums">
                  {deMio(jTeilung.eigenbetriebe / 1e6)}&#8239;Mio.&nbsp;€
                </dd>
              </div>
            </dl>
            <p className="mt-2 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Beides schuldet dieselbe Stadt — die Trennung zeigt nur, in welchem Buch es
              steht. Rechtlich haftet sie für die Eigenbetriebe genauso wie für die
              Verwaltung.
            </p>
            {/* Die Lücke benennen statt sie als Null zu zeichnen. */}
            {luecken.length > 0 && (
              <p className="mt-2 max-w-[76ch] border-t border-dashed border-border pt-2 text-[12px] leading-relaxed text-muted-foreground">
                Für {luecken.map((z) => z.jahr).join(", ")} fehlt die Aufteilung: Dort
                {luecken.length === 1 ? " ergibt " : " ergeben "}
                die Summe der einzelnen Schuldenarten in der Quelltabelle nicht den Betrag,
                der daneben als Gesamtschuld ausgewiesen ist. Welche Spalte danebenliegt,
                sagt die Tabelle nicht — die Gesamtschuld{" "}
                {luecken.length === 1 ? "dieses Jahres" : "dieser Jahre"} steht, die
                Aufschlüsselung nicht.
              </p>
            )}
          </section>
        )}

        {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. */}
        <section className="rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Was diese Zahl nicht sagt
          </p>
          <ul className="mt-2 flex max-w-[76ch] list-disc flex-col gap-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90">
            <li>
              <strong>Nicht der Konzern.</strong> Klinikum, Busse, Bäder und die
              städtischen Gesellschaften schulden auf eigene Rechnung und stehen hier
              nicht. Was neben dem Haushalt noch läuft, zeigt{" "}
              <Link href="/haushalt/konzern" className="font-semibold text-primary">
                „Und ist das die ganze Stadt?"
              </Link>{" "}
              — eine Schuldenzahl für diese Ebene führen wir nicht, weil die
              Pflichtanlage des Gesamtabschlusses im PDF keinen auslesbaren Text trägt.
            </li>
            <li>
              <strong>Ein Bestand, kein Jahr.</strong> Hier steht, was am 31. Dezember
              offen war — nicht, was die Stadt in dem Jahr eingenommen oder ausgegeben
              hat. Mit den Zahlen auf{" "}
              <Link href="/haushalt" className="font-semibold text-primary">/haushalt</Link>{" "}
              ist dieser Wert <strong>nicht verrechenbar</strong>.
            </li>
            <li>
              <strong>Kein Urteil über „zu viel".</strong> Ob ein Schuldenstand tragbar
              ist, hängt daran, was mit dem Geld gebaut wurde und was die Stadt
              erwirtschaftet. Diese Seite zeigt den Verlauf, nicht seine Bewertung.
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
