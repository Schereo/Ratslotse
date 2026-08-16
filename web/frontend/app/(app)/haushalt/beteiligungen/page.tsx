"use client";

// /haushalt/beteiligungen — „Was machen die eigentlich?"
//
// Schritt 10 und die andere Hälfte von Schritt 9: Der Gesamtabschluss
// (/haushalt/konzern) sagt, wie viel Klinikum, Busse und Bäder bewegen —
// 1,24 Mrd. € statt der 799 Mio. der Kernverwaltung. Was sie damit *tun*,
// steht dort nicht. Das sagt der Beteiligungsbericht nach § 151 NKomVG.
//
// Leserichtung: die Gesellschaften als Liste → eine davon im Steckbrief
// (Auftrag, Eigentümer, Aufsichtsrat, Wirkung auf den Haushalt, Zahlenreihe)
// → was der Bericht nicht hergibt → Quellen.
//
// DETAILANSICHT ÜBER QUERY-PARAMETER (`?g=vwg`), nicht über ein
// Route-Segment: Der mobile Build ist ein statischer Export (Capacitor), und
// dynamische Segmente brauchen dort eine vorab bekannte Pfadliste. Dieselbe
// Entscheidung wie bei /haushalt/produkte (`?nr=`) und /haushalt/bereich.
//
// KEINE BEWERTUNGSFARBEN, wie im ganzen Bereich
// (components/haushalt/hantel.tsx): Kein Rot für ein negatives
// Jahresergebnis, keine Pfeile, kein Ampel-Punkt. Ein Verkehrsbetrieb, der
// Verlust macht, erfüllt seinen Auftrag — die Stadt hält ihn dafür. Wer das
// rot einfärbt, behauptet ein Versagen und meint eine Aufgabe.
//
// UND KEINE SELBSTVERGEWISSERUNG (DESIGNSPRACHE.md § 7): Die Seite zeigt
// Fundstellen — welches Dokument, welcher Abschnitt, welche Seite —, aber
// nicht unsere Rechenproben und ihre Messwerte. Dass unsere Zahlen stimmen,
// ist kein Seiteninhalt; die Proben laufen unverändert im Hintergrund
// (`council/beteiligungsbericht.py`, `tests/test_beteiligungsbericht.py`).
//
// EINE STELLE MACHT DAVON EINE AUSNAHME, und zwar begründet: Wo eine Zahl
// **fehlt**, sagt die Seite es. „2024 —" ohne Erklärung liest sich wie ein
// Fehler; „liegt erst mit dem nächsten Bericht vor" ist eine Auskunft über
// die Quelle, nicht über uns.

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Building2, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  ABSCHNITTE, BeteiligungsDaten, Gesellschaft, KENNZAHL_TITEL, Kennzahl,
  herkunftVon, juengster, reihen, sortiert, textVon, wertText,
} from "@/lib/haushalt-beteiligungen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

const QUELLEN = ["beteiligungsbericht"] as const;

/** Wo eine Angabe im Dokument steht — bei 200 Seiten der Unterschied zwischen
 *  „steht in dem PDF" und „steht auf Seite 178, Abschnitt 2.4.8".
 *
 *  Bewusst ohne unsere Proben und ihre Messwerte: dieselbe Entscheidung wie
 *  auf /haushalt/konzern (dort ausführlich begründet). */
function Fundstelle({ h, className }: {
  h: ReturnType<typeof herkunftVon>; className?: string;
}) {
  if (!h?.fundstelle) return null;
  const ziel = h.seite && h.url ? `${h.url}#page=${h.seite}` : h.url;
  return (
    <div className={cn("border-t border-dashed border-border pt-2.5", className)}>
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher das stammt
      </p>
      <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
        {h.label ?? "Beteiligungsbericht"}, {h.fundstelle}
        {h.seite ? `, Seite ${h.seite}` : ""}
        {ziel && (
          <>
            {" · "}
            <a href={ziel} target="_blank" rel="noopener noreferrer"
              className="font-semibold text-primary">
              Dokument öffnen
            </a>
          </>
        )}
      </p>
    </div>
  );
}

/** Eine Zeile der Übersicht: Name, Auftrag in einem Satz, jüngstes Ergebnis. */
function Zeile({ daten, g, onOeffnen }: {
  daten: BeteiligungsDaten; g: Gesellschaft; onOeffnen: () => void;
}) {
  const ergebnis = juengster(daten, g.gesellschaft, "jahresergebnis");
  const gegenstand = textVon(daten, g.gesellschaft, "gegenstand");
  // Der erste Satz des Gegenstands reicht als Vorschau — der ganze Absatz
  // steht im Steckbrief. Abgeschnitten wird am Satzende, nicht nach n
  // Zeichen: „Gegenstand des Unternehmens sind die Wasserversorgung und der
  // öffentl…" ist kein Satz, sondern ein Stolperer.
  const satz = gegenstand?.text.replace(/\s+/g, " ").match(/^.{20,200}?\.(?=\s|$)/)?.[0]
    ?? gegenstand?.text.replace(/\s+/g, " ").slice(0, 160);

  return (
    <button type="button" onClick={onOeffnen}
      className="group flex w-full flex-col gap-1 rounded-xl border border-border bg-card p-3 text-left shadow-sm transition-colors hover:border-primary/40">
      <div className="flex items-start justify-between gap-3">
        <span className="min-w-0 font-display text-[15px] font-semibold leading-snug">
          {g.name}
        </span>
        {ergebnis && (
          <span className="flex-none text-right">
            <span className="block font-display text-[15px] font-bold tabular-nums">
              {wertText(ergebnis)}
            </span>
            <span className="block font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
              Ergebnis {ergebnis.jahr}
            </span>
          </span>
        )}
      </div>
      {satz && (
        <span className="line-clamp-2 text-[12.5px] leading-relaxed text-muted-foreground">
          {satz}
        </span>
      )}
    </button>
  );
}

/** Die Zeitreihe einer Kennzahl als Tabelle.
 *
 *  Tabelle statt Diagramm, und das ist keine Bequemlichkeit: Die Reihen sind
 *  vier bis acht Werte lang, teils lückenhaft, und drei Gesellschaften weisen
 *  durchgehend 0,00 € aus (Ergebnisabführung). Eine Kurve daraus zeigte vor
 *  allem die Lücken als Knicke. */
function Reihe({ daten, zeilen }: { daten: BeteiligungsDaten; zeilen: Kennzahl[] }) {
  if (!zeilen.length) return null;
  const h = herkunftVon(daten, zeilen[zeilen.length - 1].herkunft_id);
  return (
    <div>
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        {KENNZAHL_TITEL[zeilen[0].kennzahl]}
      </p>
      <dl className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1.5">
        {zeilen.map((k) => (
          <div key={k.jahr} className="flex flex-col">
            <dt className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {k.jahr}
            </dt>
            <dd className="font-display text-[15px] font-semibold tabular-nums">
              {wertText(k)}
            </dd>
          </div>
        ))}
      </dl>
      <Fundstelle h={h} className="mt-2.5" />
    </div>
  );
}

function Steckbrief({ daten, g, zurueck }: {
  daten: BeteiligungsDaten; g: Gesellschaft; zurueck: () => void;
}) {
  const alleReihen = useMemo(() => reihen(daten, g.gesellschaft), [daten, g.gesellschaft]);
  const vergleich = daten.konzernvergleich.find((z) => z.gesellschaft === g.gesellschaft);
  const quote = alleReihen.get("eigenkapitalquote");
  const ergebnis = alleReihen.get("jahresergebnis");
  // Die Eigenkapitalquote des jüngsten Jahres trägt keine Probe und steht
  // deshalb nicht im Bestand (Begründung: council/beteiligungsbericht.py).
  // Eine stumme Lücke sähe nach Fehler aus.
  const quoteFehlt = !!ergebnis?.length && !!quote?.length
    && quote[quote.length - 1].jahr < ergebnis[ergebnis.length - 1].jahr;

  return (
    <div className="flex flex-col gap-4">
      <button type="button" onClick={zurueck}
        className="group flex items-center gap-1.5 self-start text-[13px] font-semibold text-primary">
        <ArrowLeft size={14} strokeWidth={2}
          className="transition-transform group-hover:-translate-x-0.5" />
        Alle Gesellschaften
      </button>

      <div>
        <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Städtische Gesellschaft · Bericht {g.bericht_jahr}
        </p>
        <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
          {g.name}
        </h1>
      </div>

      {ABSCHNITTE.map(({ key, titel }) => {
        const t = textVon(daten, g.gesellschaft, key);
        if (!t) return null;
        return (
          <section key={key} className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              {titel}
            </p>
            {/* `whitespace-pre-line`, weil der Abschnitt „Wer sie beaufsichtigt"
                eine Namensliste ist: Zu einem Absatz verschmolzen wäre sie
                unlesbar. Der Bericht setzt je Person eine Zeile. */}
            <p className="mt-1.5 max-w-[76ch] whitespace-pre-line text-[13px] leading-relaxed text-foreground/90">
              {t.text}
            </p>
            <Fundstelle h={herkunftVon(daten, t.herkunft_id)} className="mt-3" />
          </section>
        );
      })}

      <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Die Zahlen im Zeitverlauf
        </p>
        <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
          Was die Gesellschaft erwirtschaftet hat und wie groß ihre Bilanz ist.
          <Beleg q="beteiligungsbericht" />
        </p>
        <div className="mt-3 flex flex-col gap-4">
          {(["jahresergebnis", "bilanzsumme", "eigenkapitalquote"] as const).map((k) => (
            <Reihe key={k} daten={daten} zeilen={alleReihen.get(k) ?? []} />
          ))}
        </div>
        {quoteFehlt && (
          <p className="mt-3 text-[12px] leading-relaxed text-muted-foreground">
            Für {ergebnis![ergebnis!.length - 1].jahr} steht die Eigenkapitalquote noch
            nicht dabei: Der Bericht nennt sie, rechnet sie aber nirgends vor. Sobald sie
            im nächsten Bericht ein zweites Mal steht, kommt sie hinzu.
          </p>
        )}
      </section>

      {vergleich && (
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Dieselbe Gesellschaft im Gesamtabschluss
          </p>
          <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Der{" "}
            <Link href="/haushalt/konzern" className="font-semibold text-primary">
              Gesamtabschluss
            </Link>{" "}
            führt {g.name} als eigenen Aufgabenträger. Er rechnet anders: Dort zählen nur
            die ordentlichen Erträge und Aufwendungen, hier steht das vollständige
            Jahresergebnis der Gesellschaft.
          </p>
          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                Beitrag im Konzern {vergleich.jahr}
              </dt>
              <dd className="font-display text-[17px] font-bold tabular-nums">
                {wertText({ ...vergleich, wert: vergleich.konzern_beitrag,
                  einheit: "eur" } as unknown as Kennzahl)}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                Jahresergebnis {vergleich.jahr}
              </dt>
              <dd className="font-display text-[17px] font-bold tabular-nums">
                {wertText({ ...vergleich, wert: vergleich.jahresergebnis,
                  einheit: "eur" } as unknown as Kennzahl)}
              </dd>
            </div>
          </dl>
        </section>
      )}
    </div>
  );
}

function Seite() {
  const params = useSearchParams();
  const router = useRouter();
  const gewaehlt = params.get("g");
  const { data, loading } = useFetch<BeteiligungsDaten>("/council/haushalt/beteiligungen");

  const liste = useMemo(() => sortiert(data), [data]);
  const aktiv = liste.find((g) => g.gesellschaft === gewaehlt) ?? null;
  const bericht = data?.berichtsjahre?.[data.berichtsjahre.length - 1] ?? null;
  const quelleUrl = herkunftVon(data, liste[0]?.herkunft_id)?.url ?? null;

  if (loading) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Gesellschaften werden geladen …
      </div>
    );
  }
  if (!data || !liste.length) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Building2 className="h-7 w-7 text-muted-foreground" strokeWidth={1.75} />
        <p className="max-w-[46ch] text-sm leading-relaxed text-muted-foreground">
          Für den Beteiligungsbericht liegen hier noch keine Daten. Sobald der Bericht
          eingelesen ist, stehen die Gesellschaften an dieser Stelle.
        </p>
        <Link href="/haushalt" className="text-[13px] font-semibold text-primary">
          Zurück zur Übersicht
        </Link>
      </div>
    );
  }

  return (
    <Quellenkontext schluessel={[...QUELLEN]} jahr={bericht}>
      {aktiv ? (
        <div className="flex flex-col gap-4">
          <Steckbrief daten={data} g={aktiv}
            zurueck={() => router.push("/haushalt/beteiligungen")} />
          <Quellenverzeichnis schluessel={[...QUELLEN]} />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-end justify-between gap-5">
            <div className="min-w-0">
              <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Stadtfinanzen Oldenburg · Schritt 10
              </p>
              <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
                Was machen die eigentlich?
              </h1>
              <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
                Der{" "}
                <Link href="/haushalt/konzern" className="font-semibold text-primary">
                  Gesamtabschluss
                </Link>{" "}
                sagt, wie viel Geld die städtischen Betriebe bewegen. Hier steht, was sie
                damit tun, wer sie beaufsichtigt und was sie erwirtschaften.
              </p>
            </div>
            {quelleUrl && (
              <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
                className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
                <FileText className="h-3.5 w-3.5" /> Quelle öffnen
              </a>
            )}
          </div>

          <LottiErklaert
            titel="Warum hat eine Stadt Gesellschaften?"
            text={"Manche Aufgaben laufen leichter außerhalb der Verwaltung — ein "
              + "Krankenhaus oder ein Verkehrsbetrieb braucht eigene Verträge, eigenes "
              + "Personal und eine eigene Buchhaltung. Die Stadt gründet dafür Betriebe "
              + "und Gesellschaften, bleibt aber Eigentümerin und besetzt die "
              + "Aufsichtsräte. Einmal im Jahr muss sie öffentlich Rechenschaft darüber "
              + "ablegen; das ist der Beteiligungsbericht."}
          />

          <section className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Die Gesellschaften
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {liste.length} im Bericht {bericht}
              </p>
            </div>
            <div className="grid gap-2 @[768px]/haushalt:grid-cols-2">
              {liste.map((g) => (
                <Zeile key={g.gesellschaft} daten={data} g={g}
                  onOeffnen={() => router.push(
                    `/haushalt/beteiligungen?g=${encodeURIComponent(g.gesellschaft)}`)} />
              ))}
            </div>
          </section>

          {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. Dieselbe
              Entscheidung wie auf /haushalt/konzern: Wer hier eine Zahl
              herausschreibt, soll wissen, was sie nicht ist. */}
          <section className="rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
              Was dieser Bericht nicht hergibt
            </p>
            <ul className="mt-2 flex max-w-[76ch] list-disc flex-col gap-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90">
              <li>
                <strong>Er kommt spät.</strong> Der Bericht zum Geschäftsjahr erscheint
                rund zwei Jahre später. Für einzelne Gesellschaften stehen sogar noch
                ältere Zahlen darin — dann lag deren Abschluss zum Redaktionsschluss nicht
                vor.
              </li>
              <li>
                <strong>Ein Jahresergebnis von 0 € heißt nicht „nichts verdient".</strong>{" "}
                Mehrere Betriebe führen ihr Ergebnis an die Stadt ab oder bekommen es
                ausgeglichen; in ihren Büchern bleibt dann eine Null stehen. Was sie
                erwirtschaftet haben, zeigt der{" "}
                <Link href="/haushalt/konzern" className="font-semibold text-primary">
                  Gesamtabschluss
                </Link>.
              </li>
              <li>
                <strong>Die Jahrgänge vor 2022 fehlen.</strong> Die Stadt hat den Bericht
                mit dem Berichtsjahr 2022 umgestellt; davor steht die Bilanz zweispaltig
                und ohne Kennzahlen-Tabelle. Die Zahlen reichen trotzdem bis 2017 zurück,
                weil jeder Bericht mehrere Jahre nebeneinander führt.
              </li>
              <li>
                <strong>Die beschreibenden Abschnitte sind Text der Verwaltung.</strong>{" "}
                Sie stehen hier im Wortlaut, ungekürzt und ungeprüft — gegen sie lässt
                sich nichts rechnen.
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
      )}
    </Quellenkontext>
  );
}

export default function BeteiligungenSeite() {
  // useSearchParams braucht eine Suspense-Grenze (Export-Konvention).
  return (
    <Suspense fallback={
      <div className="py-16 text-center text-sm text-muted-foreground">
        Gesellschaften werden geladen …
      </div>
    }>
      <Seite />
    </Suspense>
  );
}
