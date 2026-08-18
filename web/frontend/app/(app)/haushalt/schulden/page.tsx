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
//
// DAS BILD IST DIE GEMEINSAME <Zeitreihe> (GB-01,
// components/grafik/zeitreihe.tsx) und keine seiten-eigene Kurve mehr. Was
// hier bleibt, sind die Entscheidungen, die diese Seite trifft:
//
//  * DIE SPRUNG-MARKEN rechnet die Grafik (`spruenge`), nicht diese Datei.
//    Eine Seite, die „2001 fiel es am stärksten" als Text trägt, wird mit dem
//    nächsten Jahrgang still falsch. Was HINTER den Sprüngen steckt, steht
//    darunter als belegter Satz — im Bild steht nur die gemessene Bewegung.
//  * DIE ZINSLINIE (H4-13) nur in der absoluten Ansicht: Einen Pro-Kopf-Zins
//    weist keine Quelle aus, und wir dividieren nicht selbst. Sie liegt auf
//    DERSELBEN Skala — dass sie fast auf der Nulllinie klebt, ist die
//    Aussage und kein Darstellungsfehler.
//  * ZWEI ANSICHTEN, weil sie über dreißig Jahre in verschiedene Richtungen
//    zeigen (s. o.). Der Umschalter steht bewusst außerhalb der Grafik: Er
//    wechselt die DATEN, nicht die Darstellung.

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
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { BilanzBlock } from "@/components/haushalt/bilanz-block";

const QUELLEN = ["schulden", "bilanz"] as const;

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
      <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {h.fundstelle}{h.stand ? ` · ${h.stand}` : ""}
      </p>
    </div>
  );
}

/** Wofür die Stadt geradesteht — Bürgschaften neben den eigenen Schulden.
 *
 *  DREI ZAHLEN, DIE NUR ZUSAMMEN STIMMEN. Das Volumen allein liest sich wie
 *  eine Rechnung, die demnächst kommt; die Rückstellung allein wie das ganze
 *  Risiko. Deshalb stehen Bestand, eigene Geldschulden und die Rückstellung
 *  für den erwarteten Ausfall in einer Zeile.
 *
 *  KEINE BEWERTUNGSFARBE. Dass der Bestand sich verdreifacht hat, ist weder
 *  gut noch schlecht — es sind Bürgschaften für die eigenen Gesellschaften,
 *  ohne die deren Kredite teurer würden. Die Kurve steigt, der Satz daneben
 *  sagt warum, das Urteil bleibt bei den Lesenden.
 *
 *  Rendert nichts, solange kein Jahresabschluss eingelesen ist. */
function BuergschaftsBlock({ daten }: { daten: SchuldenDaten | null }) {
  const b = daten?.buergschaften;
  const reihe = b?.reihe ?? [];
  if (!reihe.length) return null;

  const geld = new Map((b?.geldschulden ?? []).map((z) => [z.jahr, z.wert]));
  const rueck = new Map((b?.rueckstellung ?? []).map((z) => [z.jahr, z.wert]));
  const letzter = reihe[reihe.length - 1];
  const erster = reihe[0];
  const gsLetzt = geld.get(letzter.jahr) ?? null;
  const rsLetzt = rueck.get(letzter.jahr) ?? null;
  // Der Jahrgang, der den Sprung erklärt — der mit der genannten Einzelzahl.
  const sprung = reihe.find((z) => z.einzelbetrag != null) ?? null;
  const groesste = Math.max(...reihe.map((z) => z.bestand));

  return (
    <section className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wofür die Stadt außerdem geradesteht
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          Bürgschaften: {deMio(letzter.bestand / 1e6)}&#8239;Mio.&nbsp;€
          {gsLetzt ? (
            <span className="font-normal text-muted-foreground">
              {" "}— das {(letzter.bestand / gsLetzt).toFixed(1).replace(".", ",")}-Fache
              der eigenen Schulden
            </span>
          ) : null}
        </h2>
        <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          {b?.abgrenzung}
        </p>
      </div>

      {/* Die Reihe. Zwei Balken je Jahr: wofür die Stadt geradesteht, und was
          sie selbst schuldet. Der Vergleich IST die Aussage — 2019 lagen
          beide fast gleichauf. */}
      <ul className="flex flex-col gap-1.5">
        {reihe.map((z) => {
          const gs = geld.get(z.jahr) ?? null;
          return (
            <li key={z.jahr} className="flex items-center gap-2.5 text-[12px]">
              <span className="w-9 shrink-0 font-mono text-muted-foreground">{z.jahr}</span>
              <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 rounded-sm bg-[var(--hh-aus-0)]"
                    style={{ width: `${Math.max(2, (z.bestand / groesste) * 100)}%` }} />
                  <span className="shrink-0 font-semibold tabular-nums text-foreground">
                    {deMio(z.bestand / 1e6)}
                  </span>
                </span>
                {gs ? (
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 rounded-sm bg-[var(--hh-ein-0)] opacity-70"
                      style={{ width: `${Math.max(2, (gs / groesste) * 100)}%` }} />
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {deMio(gs / 1e6)} eigene Schulden
                    </span>
                  </span>
                ) : null}
              </span>
              {/* Die Quelle sagt selbst, wie genau sie ist — das gehört an die
                  Zahl, nicht in eine Fußnote am Seitenende. */}
              {z.aus_folgejahr ? (
                <span className="shrink-0 text-[10.5px] text-muted-foreground">
                  aus dem Abschluss {z.jahr + 1}
                </span>
              ) : z.genau ? (
                <span className="shrink-0 text-[10.5px] text-muted-foreground">
                  auf den Cent belegt
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>

      {sprung?.grund ? (
        <div className="rounded-xl border border-border bg-background/40 p-3">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Woher der Sprung {sprung.jahr} kommt
          </p>
          <p className="mt-1 max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
            {sprung.grund}
          </p>
        </div>
      ) : null}

      {rsLetzt ? (
        <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Womit die Stadt rechnet:</strong>{" "}
          Für erwartete Ausfälle stehen {deEuro(rsLetzt)}&nbsp;€ in der Bilanz
          ({letzter.jahr}) — {((rsLetzt / letzter.bestand) * 100).toFixed(2).replace(".", ",")}&nbsp;%
          des verbürgten Volumens. Die {deMio(letzter.bestand / 1e6)}&#8239;Mio.&nbsp;€ sind
          also nicht das, was die Stadt zu zahlen erwartet, sondern das, wofür sie
          im äußersten Fall einsteht.
        </p>
      ) : null}

      <p className="max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
        <strong className="text-foreground">Nicht selbst addierbar.</strong>{" "}
        Die einzelnen Bürgschafts-Beschlüsse des Rates zusammenzuzählen ergäbe eine
        falsche Summe: Verlängerungen ersetzen einander, statt sich zu addieren.
        Was hier steht, ist der Bestand, den die Stadt selbst als Bestand ausweist —
        {erster.jahr === letzter.jahr ? " ein Stichtag." : ` ${reihe.length} Stichtage.`}
      </p>

      <Fundstelle h={herkunftVon(daten, letzter.herkunft_id)} />
    </section>
  );
}

/** Die dritte Schuldenzahl — und warum alle drei stimmen.
 *
 *  DIE STAFFEL IST DIE AUSSAGE. 43,7 → 294,9 → 740,3 Mio. €: Wer eine dieser
 *  Zahlen allein hört, hält die anderen für falsch. Nebeneinander erklärt sich
 *  jede durch das, was sie mitzählt.
 *
 *  ZWEI SÄTZE SIND PFLICHT und kommen aus dem Backend, nicht von hier: dass
 *  der größte Teil aus Beteiligungen unter 50 % stammt (für die die Stadt
 *  nicht haftet), und dass daraus keine Zeitreihe werden darf. Stünden sie im
 *  Frontend, könnten sie hier vergessen werden, während die Zahl bleibt.
 *
 *  Rendert nichts ohne eingelesenen Tabellenband. */
function DritteZahlBlock({ daten }: { daten: SchuldenDaten | null }) {
  const i = daten?.integrierte_schulden;
  if (!i?.stichtag) return null;
  const s = i.stichtag;
  const reihe = daten?.reihe ?? [];
  // Der Rechtsträger-Wert desselben Stichtags — die mittlere der drei Zahlen.
  const traeger = reihe.find((z) => z.jahr === s.jahr)?.insgesamt ?? null;

  const stufen = [
    { titel: "Kernhaushalt", wert: s.kernhaushalt,
      was: "Investitionskredite der Stadtverwaltung selbst" },
    { titel: "Stadt als Rechtsträger", wert: traeger,
      was: "dazu die Eigenbetriebe — die Zahl oben auf dieser Seite" },
    { titel: "Der ganze Konzern", wert: s.insgesamt,
      was: "dazu Extrahaushalte und Beteiligungen, anteilig nach Beteiligungshöhe" },
  ].filter((x) => x.wert != null);

  return (
    <section className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Warum man drei Zahlen hört
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          43,7 · {traeger ? `${deMio(traeger / 1e6)} · ` : ""}
          {deMio(s.insgesamt / 1e6)}&#8239;Mio.&nbsp;€ — und alle drei stimmen
        </h2>
        <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          Sie zählen Verschiedenes mit. Stand 31.12.{s.jahr}:
        </p>
      </div>

      <ol className="flex flex-col gap-2">
        {stufen.map((x) => (
          <li key={x.titel}
            className="flex flex-col gap-0.5 rounded-xl border border-border bg-background/40 p-3">
            <span className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="text-[13px] font-semibold text-foreground">{x.titel}</span>
              <span className="font-semibold tabular-nums text-foreground">
                {deMio((x.wert as number) / 1e6)}&#8239;Mio.&nbsp;€
              </span>
            </span>
            <span className="text-[12px] leading-relaxed text-muted-foreground">{x.was}</span>
          </li>
        ))}
      </ol>

      {/* Der Satz, ohne den die 740 Millionen falsch gelesen werden. Er steht
          im Fließtext und nicht im Kleingedruckten — er ist die Aussage. */}
      <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
        {i.abgrenzung}
        {i.anteil_unter_50 != null ? (
          <>
            {" "}Konkret sind das{" "}
            <strong className="text-foreground">
              {(i.anteil_unter_50 * 100).toFixed(0)}&nbsp;%
            </strong>{" "}
            der Summe.
          </>
        ) : null}
      </p>

      <p className="max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
        {/* Ohne eigenen Vorspann: Der Satz aus dem Backend beginnt selbst mit
            „Nur ein Stichtag" — ein Label davor sagte dasselbe zweimal. */}
        {i.keine_reihe}
      </p>

      <Fundstelle h={herkunftVon(daten, s.herkunft_id)} />
    </section>
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
          {/* Die gemeinsame <Zeitreihe> des Baukastens (GB-01) — nicht mehr
              seiten-eigen: Zinslinie (`zweitreihe`), 2010-Marke
              (`annotationen`) und die beiden größten Bewegungen (`spruenge`)
              sind dort Vertrag.

              Zinslinie und 2010-Annotation direkt im Bild (H4-13): Was der
              Bestand im Jahr kostet, auf derselben Skala — und der Knick von
              2010 mit seiner Erklärung am Ort des Knicks. Der ganze Satz samt
              Beleg steht darunter in „Zwei Sprünge, die keine Politik waren". */}
          <Zeitreihe
            reihe={kurve}
            titel={ansicht === "insgesamt" ? "Schulden insgesamt" : "Schulden je Einwohner*in"}
            ariaTitel={`Schuldenstand ${erster.jahr} bis ${letzter.jahr}`}
            einheit={ansicht === "insgesamt" ? "Mio. €" : "€ je Einwohner*in"}
            // Millionen mit einer Stelle, Pro-Kopf-Beträge ohne — sonst stünde
            // „1.908,0 €" an einer Zahl, die die Quelle ganzzahlig ausweist.
            format={ansicht === "insgesamt" ? (v) => deMio(v) : deEuro}
            spruenge
            vorjahresdifferenz
            tabelle
            zweitreihe={zinsreihe && zinsreihe.length
              ? { label: "Zinslast p. a.", reihe: zinsreihe, format: (v) => deMio(v) }
              : undefined}
            annotationen={ansicht === "insgesamt" ? [{
              jahr: 2010,
              kurz: "108,9 Mio. umgebucht",
              text: "2010 übertrug die Stadt 108,9 Mio. € Kredite an den neuen "
                + "Eigenbetrieb Gebäudewirtschaft — eine Spalte sprang, die Summe "
                + "kaum. Kein Tilgungswunder.",
            }] : []}
            hinweis="Jahr überfahren, antippen oder mit den Pfeiltasten wechseln."
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

        {/* Was hinter den größten Sprüngen steckt. Alles steht als Fußnote in
            der Quelltabelle — deshalb darf es hier stehen. Ohne diesen Block
            liest sich die Kurve als Spar- und Schuldenpolitik, und beides wäre
            falsch.

            DIE LETZTEN ZWEI PUNKTE STEHEN NUR IN DER PRO-KOPF-ANSICHT, weil
            sie nur dort etwas verzerren: Sie liegen im NENNER. In der
            Gesamtsumme kommen sie nicht vor, und sie dort zu erwähnen hieße,
            einen Sprung zu behaupten, den man nicht sieht. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {ansicht === "insgesamt"
              ? "Zwei Sprünge, die keine Politik waren"
              : "Drei Sprünge, die keine Politik waren"}
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
            {ansicht === "je_einwohner" && (
              <li>
                <strong>2023 sank der Betrag je Einwohner*in um 36&nbsp;€ — obwohl
                die Schulden stiegen.</strong> Der Zensus 2022 zählte 4.079 Menschen
                mehr, als die Statistik bis dahin fortgeschrieben hatte. Dieselbe
                Schuld auf mehr Schultern ergibt einen kleineren Betrag; die
                Gesamtsumme wuchs im selben Jahr von 281,5 auf
                281,9&#8239;Mio.&nbsp;€.<Beleg q="schulden" />
              </li>
            )}
          </ul>
          {ansicht === "je_einwohner" && (
            /* Der Vollständigkeit halber, aber NICHT als vierter Aufzählungspunkt:
               2012 wirkte dieselbe Mechanik, trug aber nur 30 der 125 € — den Rest
               hat die Stadt wirklich aufgenommen. Als gleichrangiger Punkt neben
               2023 gelistet, würde das eine Verzerrung behaupten, die es so nicht
               gab. Die Zahlen sind aus der Reihe selbst gerechnet (Betrag geteilt
               durch Pro-Kopf-Wert ergibt den Nenner, den die Statistik benutzt). */
            <p className="mt-2.5 max-w-[76ch] text-[12px] leading-relaxed text-muted-foreground">
              Alle zehn Jahre zählt eine Volkszählung die Einwohner*innen neu, und
              die Statistik rechnet ab da mit der neuen Zahl. 2012 wirkte das
              ebenfalls, aber schwächer: Von den +125&nbsp;€ jenes Jahres gehen rund
              30&nbsp;€ auf den Zensus 2011 zurück, die übrigen 95&nbsp;€ auf echte
              Kredite. In der Ansicht „Insgesamt" kommt keiner dieser beiden
              Nenner-Effekte vor.
            </p>
          )}
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

        {/* DIE GEGENSEITE. Bis hierher stand auf dieser Seite nur, was die
            Stadt schuldet — und die naheliegende Anschlussfrage („kaum
            Kredite, also keine Schulden?") beantwortet erst die Bilanz: Die
            Pensionszusagen sind ein Vielfaches der Kredite. Der Block holt
            seine Daten selbst und rendert nichts, solange kein
            ausgeglichener Bilanzstichtag im Bestand steht. */}
        <BilanzBlock />

        {/* Wofür die Stadt geradesteht. Steht VOR den Grenzen und nicht
            darin, obwohl es eine Grenze der Schuldenzahl ist: Es ist die
            größere Zahl der Seite (2024 das Fünffache), und Zahlen, die
            größer sind als die Überschrift, gehören nicht ins
            Kleingedruckte. */}
        <BuergschaftsBlock daten={data} />

        {/* Die dritte Zahl. Steht NACH den Bürgschaften, weil sie die Frage
            beantwortet, die die beiden davor aufwerfen: „Wenn 337 nicht alles
            ist und 220 nicht dazuzählen — was schuldet die Stadt denn nun?" */}
        <DritteZahlBlock daten={data} />

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

        <SchrittWeiter href="/haushalt/schulden" />

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
      </div>
    </Quellenkontext>
  );
}
