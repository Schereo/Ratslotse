"use client";

// /haushalt/streit — „Der Streit ums Geld".
//
// Der Bereich zeigt auf zwölf Seiten Zahlen: Plan, Ist, Produkte, Konzern,
// Prüfberichte. Keine davon zeigt, dass über diese Zahlen gestritten wurde.
// Genau das ist der Teil, den kein Open-Data-Portal liefern kann — Zahlen hat
// jedes, die Debatte hat nur, wer die Protokolle hat.
//
// Leserichtung: Jahrgang wählen → wie es ausging → wer was ändern wollte →
// was gesagt wurde → was hier fehlt → Quellen.
//
// DIE HALTUNG DIESER SEITE ist die schwierigste im ganzen Bereich, weil hier
// Personen zitiert werden und jede Anordnung eine Aussage ist. Vier Regeln,
// die man sonst unbemerkt bricht (ausführlich in lib/haushalt-streit.ts):
//
//  * **Protokollreihenfolge, nie sortiert.** Nicht nach Fraktionsgröße, nicht
//    nach Redelänge, nicht „die wichtigsten zuerst".
//  * **Eine Kürzungsregel für alle.** Jede Rede zeigt dieselbe Zeichenzahl
//    und klappt auf denselben Klick vollständig auf. Es gibt keine Auswahl
//    „der aussagekräftigsten Stellen" — die träfe jemand.
//  * **Keine Wertung, auch nicht durch Farbe.** Grün/Rot stehen ausschließlich
//    am Abstimmungs-ERGEBNIS (angenommen/abgelehnt — das ist eine Tatsache,
//    keine Note). Parteifarben bleiben 8-px-Punkte, nie Flächen
//    (Designsprache §2/§7, components/grafik/hantel.tsx).
//  * **Keine Stimmgrafik.** Das Ratsinformationssystem kennt kein
//    Stimmverhalten einzelner Ratsmitglieder, nur das Ergebnis je Abstimmung.
//
// KEIN „Stand der Daten“-Block. Der Baustein beschreibt, bis wann die neun
// FINANZschichten reichen — auf einer Seite ohne eine einzige Zahl daraus wäre
// das eine Angabe über fremde Daten. Die ehrliche Reichweite dieser Seite steht
// stattdessen am Jahrgangs-Umschalter: ab wann Protokolle im Bestand sind.
//
// UND EINE EHRLICHKEIT, die der Seite ihre Grenze setzt: Was in einer
// Änderungsliste stand — welche Position um welchen Betrag —, steht in den
// Anlagen-PDFs der Vorlage und liegt nicht als Volltext im Bestand. Die Seite
// sagt deshalb „wer wollte ändern und kam damit durch", nicht „was genau".
// Das steht im Block „Was hier fehlt", nicht im Kleingedruckten.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, ExternalLink, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { sessionHref } from "@/lib/routes";
import {
  HINWEIS_REDE, StreitAntrag, StreitDaten, StreitStation, StreitWortbeitrag,
  antragsBilanz, antragsStationen, datumLang, debattenStation, gremiumKurz,
  jahrgaenge, redenJeFraktion, runde, schlussbeschluss, vorschau,
} from "@/lib/haushalt-streit";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { OutcomeBadge, OutcomeDot } from "@/components/decision-ui";
import { parteiDot } from "@/components/qa-bausteine";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

const QUELLEN: QuellenSchluessel[] = ["ratsbeschluss"];

/** Der neutrale Punkt für kombinierte Label (Designsprache §2). */
const NEUTRAL = { bg: "hsl(209 18% 65%)", ring: false };

/** Fraktions-/Gruppenmarke: 8-px-Punkt plus Label. Nie eine Fläche — eine
 *  parteigefärbte Karte macht aus einer Wortmeldung ein Plakat.
 *
 *  Jedes Label mit Schrägstrich bekommt den NEUTRALEN Punkt, nicht die Farbe
 *  der erstbesten Partei darin. `parteiDot` sucht nach Teilzeichenketten und
 *  gäbe „SPD / CDU und FDP" das SPD-Rot — eine gemeinsame Änderungsliste
 *  dreier Fraktionen erschiene als Antrag einer einzigen. Dieselbe Regel gilt
 *  für Ratsgruppen („FDP/Volt", „Die Linke/Piraten"): Die Designsprache gibt
 *  ihnen ausdrücklich den neutralen Punkt und das kombinierte Label. */
function Fraktion({ label, unklar = false }: { label: string | null; unklar?: boolean }) {
  if (unklar) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground">
        <span aria-hidden className="h-2 w-2 rounded-full border border-dashed border-muted-foreground/60" />
        Fraktion nicht eindeutig
      </span>
    );
  }
  if (!label) return null;
  const dot = label.includes("/") ? NEUTRAL : parteiDot(label);
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-foreground">
      <span
        aria-hidden
        className="h-2 w-2 flex-none rounded-full"
        style={{
          background: dot.bg,
          boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
        }}
      />
      {label}
    </span>
  );
}

/** Eine Rede: Kopf (wer), Wortlaut (Protokoll), bei Bedarf aufklappbar.
 *  Der Wortlaut steht an einer Randlinie wie auf /haushalt/pruefung — so ist
 *  auf einen Blick klar, wo das Protokoll spricht und wo wir. */
function Rede({ b }: { b: StreitWortbeitrag }) {
  const [offen, setOffen] = useState(false);
  const { kopf, rest } = vorschau(b.text);

  return (
    <div className="border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="text-[13px] font-semibold text-foreground">{b.name}</span>
        {/* Bei Verwaltung und Sitzungsleitung sagt die Anrede die Rolle schon
            („Oberbürgermeister", „Stadtkämmerin", „Ratsvorsitzender") — ein
            zusätzliches Wort „Verwaltung" daneben wäre dieselbe Angabe zweimal. */}
        {b.rolle === "rat" && <Fraktion label={b.fraktion} unklar={b.fraktion_unklar} />}
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground/80">
          {b.anrede}
        </span>
      </div>
      <p className="mt-1.5 border-l-2 border-border pl-3 text-[13.5px] italic leading-relaxed text-foreground/90">
        {offen ? b.text : kopf}
        {!offen && rest && <span className="not-italic text-muted-foreground"> …</span>}
      </p>
      {rest && (
        <button
          type="button"
          onClick={() => setOffen((o) => !o)}
          className="mt-1.5 pl-3 text-[11.5px] font-semibold text-primary"
        >
          {offen ? "Weniger" : `Ganzen Beitrag lesen (${b.zeichen.toLocaleString("de-DE")} Zeichen)`}
        </button>
      )}
    </div>
  );
}

/** Eine Änderungsliste mit ihrem Ergebnis. */
function AntragsZeile({ a }: { a: StreitAntrag }) {
  return (
    <div className="flex flex-col gap-1 border-t border-border/60 py-2 first:border-t-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
      <div className="min-w-0">
        {a.ist_verwaltung ? (
          <span className="text-[12px] font-semibold text-muted-foreground">Verwaltung</span>
        ) : (
          <Fraktion label={a.urheber} />
        )}
        <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">{a.titel}</p>
      </div>
      <span className="flex-none">
        <OutcomeDot outcome={(a.outcome ?? null) as DecisionOutcome | null} />
      </span>
    </div>
  );
}

function StationsAntraege({ s }: { s: StreitStation }) {
  const fraktionen = s.antraege.filter((a) => !a.ist_verwaltung);
  const verwaltung = s.antraege.filter((a) => a.ist_verwaltung);
  return (
    <section className="border-t border-dashed border-border pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-foreground/70">
          {gremiumKurz(s.gremium)}
        </h3>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {datumLang(s.datum)} · {fraktionen.length} aus dem Rat
          {verwaltung.length > 0 && ` · ${verwaltung.length} der Verwaltung`}
        </span>
      </div>
      <div className="mt-1">
        {fraktionen.map((a, i) => <AntragsZeile key={`f${i}`} a={a} />)}
      </div>
      {verwaltung.length > 0 && (
        <details className="group mt-2 border-t border-dashed border-border pt-2">
          <summary className="cursor-pointer list-none text-[11.5px] font-semibold text-primary">
            {verwaltung.length} Änderungslisten der Verwaltung anzeigen
          </summary>
          {/* Getrennt, weil es keine Fraktionsanträge sind: Die Verwaltung
              schreibt ihren eigenen Entwurf fort. Zwischen den anderen
              stehend sähe es aus, als hätte jemand neunmal gewonnen. */}
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Die Verwaltung bringt eigene Änderungslisten ein — das ist kein Antrag aus dem Rat,
            sondern die Fortschreibung ihres eigenen Entwurfs, etwa wenn zwischen Entwurf und
            Beschluss neue Zahlen eintreffen.
          </p>
          <div className="mt-1">
            {verwaltung.map((a, i) => <AntragsZeile key={`v${i}`} a={a} />)}
          </div>
        </details>
      )}
    </section>
  );
}

function StreitInner() {
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<StreitDaten>("/council/haushalt/streit");

  const jahre = useMemo(() => jahrgaenge(data ?? null), [data]);
  const jahr = gewaehltesJahr && jahre.includes(gewaehltesJahr) ? gewaehltesJahr : jahre[0] ?? null;
  const r = useMemo(() => runde(data ?? null, jahr), [data, jahr]);

  const debatte = debattenStation(r);
  const schluss = schlussbeschluss(r);
  const antragsSt = antragsStationen(r);
  const bilanz = antragsBilanz(r);
  const jeFraktion = redenJeFraktion(debatte);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!jahr || !r) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für keinen Jahrgang liegt bisher ein ausgelesenes Protokoll vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  return (
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Der Streit ums Geld</span>
        </div>

        <div>
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stadtfinanzen Oldenburg · Schritt 15
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
            Der Streit ums Geld
          </h1>
          <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
            Ein Haushalt ist kein Rechenergebnis, sondern ein Kompromiss. Bevor er beschlossen
            wird, legen die Fraktionen Änderungslisten vor, und im Rat wird stundenlang darüber
            geredet. Beides steht in den Protokollen — hier ist es, Jahrgang für Jahrgang.
          </p>
        </div>

        {/* Jahrgangs-Umschalter. Query-Param statt dynamischem Segment: Der
            Capacitor-Export kennt die Jahre zur Bauzeit nicht — dieselbe
            Konvention wie /haushalt/plan-ist?jahr=… */}
        <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Haushaltsjahr
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {jahre.map((j) => (
              <Link
                key={j}
                href={`/haushalt/streit?jahr=${j}`}
                scroll={false}
                className={cn(
                  "rounded-full border px-3 py-1 font-mono text-[12px] font-medium tabular-nums transition-colors",
                  j === jahr
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                {j}
              </Link>
            ))}
          </div>
          <p className="mt-2 max-w-[70ch] text-[11.5px] leading-relaxed text-muted-foreground">
            Der Haushalt für ein Jahr wird meist im Dezember davor beschlossen — der für 2026
            erst im Februar 2026. Das Jahr hier ist das Haushaltsjahr, nicht das Sitzungsjahr.
            Protokolle liegen ab Januar 2018 im Bestand; deshalb ist der Haushalt 2019 der
            erste Jahrgang, dessen Beratung hier steht.
          </p>
        </div>

        {/* Wie es ausging. */}
        {schluss?.beschluss && (
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Wie es ausging
              </h2>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {gremiumKurz(schluss.gremium)} · {datumLang(schluss.datum)}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <OutcomeBadge outcome={(schluss.beschluss.outcome ?? null) as DecisionOutcome | null} />
              <span className="text-[13.5px] font-semibold text-foreground">
                Haushaltssatzung und Haushaltsplan {r.jahr}
              </span>
            </div>
            {schluss.beschluss.wortlaut && (
              <p className="mt-2 border-l-2 border-border pl-3 text-[13px] leading-relaxed text-foreground/90">
                {schluss.beschluss.wortlaut}
              </p>
            )}
            <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
              Wie die einzelnen Ratsmitglieder gestimmt haben, führt das Ratsinformationssystem
              nicht — es hält nur fest, ob einstimmig oder mehrheitlich beschlossen wurde und wie
              viele Gegenstimmen und Enthaltungen es gab.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-dashed border-border pt-2.5">
              <Link
                href={sessionHref(schluss.ksinr, schluss.beschluss.top ? [schluss.beschluss.top] : undefined)}
                className="text-[11.5px] font-semibold text-primary"
              >
                Sitzung im Ratsinformationssystem
              </Link>
              {schluss.protokoll_url && (
                <a
                  href={schluss.protokoll_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-primary"
                >
                  <FileText className="h-3 w-3" />
                  Protokoll als PDF
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        )}

        {/* Wer was ändern wollte. */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wer etwas ändern wollte
            </h2>
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {antragsSt.reduce((n, s) => n + s.antraege.filter((a) => !a.ist_verwaltung).length, 0)}{" "}
              Änderungslisten aus dem Rat
            </span>
          </div>
          <p className="mt-1 max-w-[66ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Über jede Liste wird einzeln abgestimmt. Dieselbe Liste kann im Ausschuss anders
            ausgehen als im Rat — deshalb stehen beide Stationen hier, nicht eine
            zusammengefasste.
          </p>

          {antragsSt.length === 0 ? (
            <p className="mt-3 border-t border-dashed border-border pt-3 text-[12.5px] leading-relaxed text-muted-foreground">
              Für diesen Jahrgang weist das Protokoll keine einzeln abgestimmten Änderungslisten
              aus. Das heißt nicht, dass es keine gab: In manchen Jahren protokolliert der Rat nur
              die Schlussabstimmung über den fertigen Haushalt.
            </p>
          ) : (
            <>
              {bilanz.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-dashed border-border pt-2.5">
                  {bilanz.map((b) => (
                    <span key={b.urheber} className="inline-flex items-center gap-1.5">
                      <Fraktion label={b.urheber} />
                      <span className="font-mono text-[10.5px] tabular-nums text-muted-foreground">
                        {b.angenommen}/{b.angenommen + b.abgelehnt} durchgekommen
                      </span>
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-3 flex flex-col gap-3.5">
                {antragsSt.map((s) => <StationsAntraege key={s.ksinr} s={s} />)}
              </div>
            </>
          )}
        </div>

        {/* Was gesagt wurde. */}
        {debatte && debatte.debatte.length > 0 && (
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Aus der Haushaltsdebatte
              </h2>
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                {debatte.debatte.length} Wortbeiträge · {gremiumKurz(debatte.gremium)},{" "}
                {datumLang(debatte.datum)}
              </span>
            </div>
            {jeFraktion.length > 0 && (
              <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
                {jeFraktion.map((f) => (
                  <span key={f.label} className="tabular-nums">
                    {f.label} {f.n}
                  </span>
                ))}
              </p>
            )}
            <p className="mt-2 max-w-[66ch] text-[12.5px] leading-relaxed text-muted-foreground">
              Alle Wortbeiträge des Tagesordnungspunkts, in der Reihenfolge des Protokolls. Jeder
              ist auf dieselbe Länge gekürzt und lässt sich vollständig aufklappen — eine Auswahl
              „der wichtigsten Stellen" träfe sonst jemand.
            </p>
            <div className="mt-3 flex flex-col gap-3 border-t border-dashed border-border pt-3">
              {debatte.debatte.map((b, i) => <Rede key={i} b={b} />)}
            </div>
            <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
              {HINWEIS_REDE}
            </p>
          </div>
        )}

        <LottiErklaert
          titel="Was eine Änderungsliste ist"
          pose="point"
          text={
            "Die Verwaltung legt einen Entwurf vor. Wer daran etwas ändern will, sammelt seine " +
            "Wünsche in einer Liste — mehr Geld hier, weniger dort. Über jede Liste stimmt der " +
            "Rat einzeln ab, und erst danach über den fertigen Haushalt."
          }
        />

        {/* Die Grenze der Seite — sichtbar, nicht im Kleingedruckten. */}
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was hier fehlt
          </h2>
          <ul className="mt-2 flex max-w-[70ch] list-disc flex-col gap-1.5 pl-4 text-[12.5px] leading-relaxed text-muted-foreground">
            <li>
              <strong className="font-semibold text-foreground">Der Inhalt der Änderungslisten.</strong>{" "}
              Welche Position eine Fraktion um welchen Betrag verschieben wollte, steht in den
              Anlagen zur Vorlage. Diese PDFs liegen nicht als Volltext vor, deshalb steht hier,
              wer etwas einbrachte und ob es durchkam — nicht, was genau darin stand.
            </li>
            <li>
              <strong className="font-semibold text-foreground">Das Stimmverhalten Einzelner.</strong>{" "}
              Das Ratsinformationssystem führt keine namentlichen Abstimmungen; nur das Ergebnis
              je Abstimmung ist bekannt.
            </li>
            <li>
              <strong className="font-semibold text-foreground">Reden außerhalb des Haushaltspunkts.</strong>{" "}
              Aufgeführt sind die Wortbeiträge unter dem Tagesordnungspunkt, unter dem der
              Haushalt beraten wurde. Über Geld wird auch anderswo gestritten.
            </li>
            <li>
              <strong className="font-semibold text-foreground">Einzelne Fraktionszuordnungen.</strong>{" "}
              Saßen zwei Ratsmitglieder mit demselben Nachnamen im Rat und nennt das Protokoll nur
              diesen, bleibt die Fraktion offen — eine geratene wäre schlimmer als eine fehlende.
            </li>
          </ul>
        </div>

        <Quellenverzeichnis schluessel={QUELLEN} />

        <Link
          href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary"
        >
          Zurück zur Übersicht über den Haushalt
          <ChevronRight
            size={14}
            strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5"
          />
        </Link>
      </div>
    </Quellenkontext>
  );
}

export default function StreitPage() {
  // useSearchParams braucht eine Suspense-Grenze (Export-Konvention).
  return (
    <Suspense
      fallback={<div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>}
    >
      <StreitInner />
    </Suspense>
  );
}
