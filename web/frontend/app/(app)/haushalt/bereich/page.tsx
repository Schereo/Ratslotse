"use client";

// Teilhaushalt-Dossier. Dramaturgie wie die Beschluss-Seiten: eine These, dann
// Karte für Karte der Beleg — Anzeigetafel mit Gegenbalken im Kopf,
// Brutto-gegen-Netto-Umschalter (das Lehrstück), Was steckt drin, Entwicklung.
//
// Query-Param statt dynamischem Segment (/haushalt/bereich?name=…): Der
// Capacitor-Export (output: export) kennt die Bereichs-Slugs zur Bauzeit
// nicht — dieselbe Konvention wie die Beschluss-Seite (/council/decision?id=).
//
// DREI ÄNDERUNGEN AM BESTAND, jede mit einem Grund:
//
// 1. Der Kostendeckungsgrad-Ring ist weg. Ein Ring beantwortet „wie viel
//    Prozent", die Frage der Seite ist aber „wie viele Millionen". An seine
//    Stelle trat zunächst ein Wasserfall (GB-14) neben einer kleinen
//    Kennzahlen-Karte rechts vom Titel. Beides ist seit 24.08. wieder weg,
//    aus zwei Befunden (Tim): Die drei Zahlen standen „komisch klein in der
//    Ecke", und der Wasserfall las sich nicht — dass ein Abzug an der
//    Laufsumme hängt, muss man wissen, drei unterschiedlich ausgerichtete
//    Balken sagen es nicht von selbst. Jetzt ist der Seitenkopf eine
//    Anzeigetafel wie auf dem Haushalts-Einstieg: die drei Summen in der
//    großen Tafel-Type, darunter die Rechnung als Gegenbalken (GB-04) —
//    zwei Leisten auf einer Basis, die Lücke heißt sichtbar „trägt die
//    Stadt". Dieselbe Bauform wie die Einstiegs-Tafel, also schon gelernt.
//    Der Prozentsatz bleibt als Satz erhalten, dort wo er trägt:
//    im Vergleich zweier Bereiche.
// 2. Die Bereichsnamen laufen durch `lib/haushalt-bereiche.ts`. Vorher
//    verglich diese Seite Namen über ihr erstes Wort („Personal…"), um die
//    Zeilen des Jahresabschlusses zu finden — das ging gut, solange kein
//    Bereich mit demselben Wort begann. Jetzt entscheidet der kanonische
//    Schlüssel.
// 3. Reiter statt einer sehr langen Rolle. Was NICHT hinter einem Reiter
//    verschwindet: der Brutto/Netto-Umschalter (Begründung in
//    `components/haushalt/area-reiter.tsx`).

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, ChevronRight, MessageCircle, Search } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { fragenHref } from "@/lib/routes";
import {
  ERTRAGSART_KURZ, HaushaltAuswahl, haushaltUrl, HaushaltZeile, PLAN_ART_LABEL, PlanArt,
  ProdukteAntwort, amount, bereichInfo, bereichSlug, bereiche, bereichsReihe,
  deMio, deckung, gruendeFuerBereich, jahreSortiert, mio, quellenLabel,
} from "@/lib/haushalt";
import { BEREICHE, bereichKanon, bereichSchluessel } from "@/lib/haushalt-bereiche";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/source";
import { Gegenbalken } from "@/components/grafik/gegenbalken";
import { Hantel } from "@/components/grafik/hantel";
import { Warum } from "@/components/haushalt/warum";
import { Summe } from "@/components/haushalt/tafel";
import { BereichReiter, ReiterTafel, type Reiter } from "@/components/haushalt/area-reiter";
import { Datenstand } from "@/components/haushalt/datenstand";
import { cn } from "@/lib/utils";

type ReiterId = "ueberblick" | "planist" | "source";

function Karte({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-2xl border border-border bg-card p-4 shadow-sm", className)}>
      {children}
    </div>
  );
}

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
      {children}
    </p>
  );
}

/** Woraus die eigenen Erträge eines Bereichs bestehen — aus dem Jahresabschluss.
 *
 *  Der Entwurf wollte hier einen Satz („vor allem Elternbeiträge und
 *  Landesmittel"). Der stimmt so nicht: Bei Jugend und Familie sind die
 *  öffentlich-rechtlichen Entgelte, in denen die Elternbeiträge stecken, die
 *  VIERTgrößte Position. Statt eines geschätzten Satzes steht hier die
 *  ausgelesene Aufteilung — mit dem Jahr, aus dem sie stammt. */
function EigeneErtraege({ daten, key, planEin, planJahr }: {
  daten: Daten;
  key: string | null;
  planEin: number;
  planJahr: number;
}) {
  const posten = (daten.income_statement ?? []).filter(
    (p) => p.sub_budget_name != null && bereichSchluessel(p.sub_budget_name) === key
           && p.nr >= 1 && p.nr <= 11 && (p.result ?? 0) > 0);
  if (!posten.length || !key) return null;
  const year = Math.max(...posten.map((p) => p.year));
  const arten = posten
    .filter((p) => p.year === year)
    .map((p) => ({ nr: p.nr, label: ERTRAGSART_KURZ[p.nr] ?? p.label, value: p.result as number }))
    .sort((a, b) => b.value - a.value);
  if (arten.length < 2) return null;
  const gesamt = arten.reduce((s, a) => s + a.value, 0);

  return (
    <Karte>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <Kicker>Woraus die eigenen Einnahmen bestehen</Kicker>
        <span className="font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
          Ist {year}
        </span>
      </div>
      <div className="mt-3 flex flex-col gap-1.5">
        {arten.map((a, i) => (
          <div key={a.nr} className="flex items-center gap-2.5">
            {/* Kein `truncate`: Auf 375 px wurde daraus „Zuwendungen un…" und
                „privatrechtliche E…" — zwei Zeilen sagen mehr als ein
                abgeschnittenes Wort. */}
            <span className="w-[38%] flex-none text-[12.5px] leading-snug sm:w-[44%]">{a.label}</span>
            <div className="h-3 flex-1 rounded-[3px] bg-muted">
              <div className="h-full rounded-[3px]" style={{
                width: `${(a.value / arten[0].value) * 100}%`,
                background: `var(--hh-ein-${Math.min(i, 6)})`,
              }} />
            </div>
            {/* `whitespace-nowrap`: „10,9 Mio. €" brach sonst hinter „Mio."
                um, und das € stand allein in einer zweiten Zeile. Die Einheit
                steht je Zeile, weil `amount()` sie mit der Größenordnung
                wechselt — ein gemeinsamer Kopf wäre für die kleinen Posten
                falsch. */}
            <span className="w-[86px] flex-none whitespace-nowrap text-right font-mono text-[11.5px] tabular-nums">
              {amount(a.value).value}&#8239;<span className="text-muted-foreground">{amount(a.value).unit}</span>
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
        Zusammen {amount(gesamt).value}&nbsp;{amount(gesamt).unit} — aus dem Jahresabschluss
        {" "}{year}<Beleg q="ergebnisrechnung_thh" />. Der Plan für {planJahr} weist
        {" "}{deMio(planEin)}&nbsp;Mio.&nbsp;€ aus; die Aufteilung dazu gibt es erst,
        wenn das Jahr abgerechnet ist.
      </p>
    </Karte>
  );
}

/** Den Teilhaushalt zu `?name=…` finden — und zwar auch dann, wenn im Query
 *  nicht genau der Slug steht, den die Bereichstabelle schreibt.
 *
 *  WARUM: Der Parameter heißt `name`, erwartet aber einen Slug. Wer den Link
 *  weitergibt, tippt oder aus einer Fußnote abschreibt, schreibt den
 *  Klartextnamen hinein — „?name=Finanzmanagement und Recht" lief bis 17.08.
 *  auf „Diesen Bereich kennen wir nicht", obwohl der Name exakt so im Bestand
 *  steht. Ein geteilter Link, der ins Leere führt, ist ein Fehler, kein
 *  Sonderfall.
 *
 *  Drei Stufen, jede eine echte Fassung derselben Adresse:
 *   1. der Slug, wie ihn `bereichSlug()` aus dem DB-Namen bildet;
 *   2. derselbe Slug, aus dem Eingang neu gebildet — `bereichSlug()` ist auf
 *      Slugs die Identität, fängt aber Klartext, Umlaute und Großschreibung;
 *   3. die Alias-Liste des Wörterbuchs — ein Link aus einem Jahrgang, in dem
 *      derselbe Teilhaushalt anders hieß, zeigt weiter auf denselben Bereich.
 *
 *  Geraten wird dabei nichts: Alle drei Stufen vergleichen belegte
 *  Schreibweisen, keine Ähnlichkeiten. */
function bereichAusParam(zeilen: HaushaltZeile[], eingang: string): HaushaltZeile | undefined {
  if (!eingang.trim()) return undefined;
  const liste = bereiche(zeilen);
  const gesucht = bereichSlug(eingang);
  const direkt = liste.find((r) => bereichSlug(r.area) === gesucht);
  if (direkt) return direkt;
  const kanon = BEREICHE.find((b) =>
    bereichSlug(b.name) === gesucht || b.aliase.some((a) => bereichSlug(a) === gesucht));
  if (!kanon) return undefined;
  return liste.find((r) => bereichSchluessel(r.area) === kanon.key);
}

function BereichInner() {
  const slug = useSearchParams().get("name") ?? "";
  const { data, loading } = useFetch<Daten>(haushaltUrl(FELDER));
  const [ranking, setRanking] = useState<"netto" | "brutto">("netto");
  const [reiter, setReiter] = useState<ReiterId>("ueberblick");

  const years = useMemo(() => (data ? jahreSortiert(data) : []), [data]);
  const year = years[years.length - 1];
  const zeilen = data && year ? data.years[String(year)] ?? [] : [];
  const z = bereichAusParam(zeilen, slug);
  const kanon = z ? bereichKanon(z.area) : null;

  // Produktebene: das jüngste Jahr, für das sie vorliegt — und nur für diesen
  // Teilhaushalt. Ohne Nummer (unbekannter Bereich) fragen wir gar nicht erst.
  const produktJahr = useMemo(() => {
    const js = (data?.product_years ?? []).slice().sort((a, b) => a - b);
    return js[js.length - 1] ?? null;
  }, [data]);
  const { data: produkte } = useFetch<ProdukteAntwort>(
    produktJahr != null && kanon?.sub_budget != null
      ? `/council/budget/products?year=${produktJahr}&sub_budget=${kanon.sub_budget}`
      : null);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }
  if (!z || !year || !kanon) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Diesen Bereich kennen wir nicht.{" "}
        <Link href="/haushalt/produkte#bereiche" className="font-semibold text-primary">Alle Bereiche ansehen</Link>
      </div>
    );
  }

  const aus = mio(z.expenses) ?? 0;
  const ein = mio(z.revenues) ?? 0;
  const netto = -(mio(z.result) ?? 0);
  const alle = bereiche(zeilen)
    .map((r) => ({ r, netto: -(mio(r.result) ?? 0), brutto: mio(r.expenses) ?? 0, d: deckung(r) }))
    .sort((a, b) => (ranking === "netto" ? b.netto - a.netto : b.brutto - a.brutto));
  const nachNetto = [...alle].sort((a, b) => b.netto - a.netto);
  const nachBrutto = [...alle].sort((a, b) => b.brutto - a.brutto);
  const rangNetto = nachNetto.findIndex((x) => x.r.area === z.area) + 1;
  const bruttoTop = nachBrutto[0];
  const series = bereichsReihe(data, z.area);
  const source = quellenLabel(zeilen, year);
  const info = bereichInfo(z.area);
  const maxWert = Math.max(...alle.map((x) => (ranking === "netto" ? x.netto : x.brutto)), 1);
  const d = deckung(z);

  // Der Gegenbalken rechnet mit den ROHEN Mio.-Werten, nicht den gerundeten:
  // Seine Lücke (Basis − kürzere Leiste) entsteht IN der Grafik, und aus zwei
  // schon gerundeten Beträgen gerechnet kann sie um eine Anzeigestufe von der
  // Kopfzahl abweichen — bei den nicht rechtsfähigen Stiftungen kippte durch
  // Doppelrundung einmal sogar die Richtung (dieselbe Falle, gegen die der
  // Wasserfall zuvor seine Summenprobe hatte). Auch die RICHTUNG der Rechnung
  // kommt deshalb aus den Rohwerten, damit Basis und Rest-Label nie
  // auseinanderfallen.
  const rohAus = (z.expenses ?? 0) / 1_000_000;
  const rohEin = (z.revenues ?? 0) / 1_000_000;
  const einVoran = rohEin > rohAus; // Überschuss-Fall: die Einnahmen sind die Basis
  // Kein `imBalken`: Bei EINEM Segment je Leiste stünde im Balken derselbe
  // Text, der als Legende direkt darunter steht — zweimal untereinander.
  // Auf dem Einstieg trägt der Text im Balken, weil dort 13 Segmente ihre
  // Legende entlasten.
  const balkenAus = {
    title: "Geplante Aufwendungen", rampe: "aus" as const,
    segmente: [{ label: "Aufwendungen des Bereichs", value: rohAus }],
  };
  const balkenEin = {
    title: "Geplante eigene Erträge", rampe: "ein" as const,
    segmente: [{ label: "eigene Erträge", value: rohEin }],
  };

  // Vergleichsbereich für den Kostendeckungs-Satz: der größte andere Bereich
  // nach Ausgaben. „Fast doppelt so viel" stand hier bis 16.08. als feste
  // Wendung — 283,1 zu 169,2 ist Faktor 1,67. Solche Größenverhältnisse
  // werden gerechnet und mitgeschrieben, nicht getextet.
  const vergleich = nachBrutto.find((x) => x.r.area !== z.area) ?? null;
  const faktor = vergleich && (mio(z.expenses) ?? 0) > 0
    ? Math.round((vergleich.brutto / aus) * 10) / 10 : null;

  // Zeilen des Jahresabschlusses zu diesem Teilhaushalt — über den kanonischen
  // Schlüssel, nicht über das erste Wort des Namens.
  const abschluss = (data.income_statement ?? []).filter(
    (p) => p.sub_budget_name != null && bereichSchluessel(p.sub_budget_name) === kanon.key
           && (p.nr === 12 || p.nr === 20));
  const planIstJahre = [...new Set(abschluss.map((p) => p.year))].sort((a, b) => a - b);
  const planIstZeilen = planIstJahre
    .map((j) => {
      const a = abschluss.find((p) => p.year === j && p.nr === 20);
      // `plan` ist die Bezugsgröße des jeweiligen Jahrgangs, nicht überall der
      // nackte Ansatz — 2018 und 2020 weichen ab (Fußnote unten).
      return {
        label: String(j) + (a?.plan_kind && a.plan_kind !== "budget" ? "*" : ""),
        plan: mio(a?.plan), ist: mio(a?.result),
        // Kein Erklärsatz je Jahr: Die bereichsbezogenen Erläuterungen des
        // Abschlusses stehen direkt unter der Hantel („Was der Abschluss …
        // sagt") — ein zweiter Satz in der Zeile wäre derselbe Text zweimal.
        einordnung: null,
      };
    })
    .filter((r) => r.plan != null && r.ist != null);
  const hatPlanIst = planIstZeilen.length > 0;

  const produktZeilen = (produkte?.products ?? [])
    .filter((p) => p.result != null && p.result < 0)
    .sort((a, b) => (a.result as number) - (b.result as number))
    .slice(0, 6);

  const quellen: QuellenSchluessel[] = [
    "plan",
    ...(abschluss.length ? (["ergebnisrechnung_thh"] as const) : []),
    ...(hatPlanIst ? (["jahresabschluss"] as const) : []),
    ...(produktZeilen.length ? (["teilhaushalt"] as const) : []),
  ];

  const reiterListe: Reiter<ReiterId>[] = [
    { id: "ueberblick", label: "Überblick" },
    ...(hatPlanIst ? [{ id: "planist" as const, label: "Geplant und geworden" }] : []),
    { id: "source", label: "Quelle" },
  ];
  const aktiv = reiterListe.some((r) => r.id === reiter) ? reiter : "ueberblick";

  return (
    <Quellenkontext keys={quellen} year={year}>
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt {year}</Link>
        <ChevronRight aria-hidden className="h-3 w-3" />
        <Link href="/haushalt/produkte#bereiche" className="hover:text-foreground">Alle Bereiche</Link>
        <ChevronRight aria-hidden className="h-3 w-3" />
        <span className="font-semibold text-foreground">{kanon.name}</span>
      </div>

      {/* Der Kopf ist eine Anzeigetafel (DESIGNSPRACHE § 4) — dieselbe Bauform
          wie der Haushalts-Einstieg: links die Einordnung, rechts die drei
          Summen in der großen Tafel-Type, darunter das Kern-Visual. Bis 24.08.
          standen die drei Zahlen klein in einer Eckkarte am rechten Rand, und
          zwischen ihr und den 66-ch-Absätzen blieb die Mitte leer. */}
      <div className="hh-tafel rounded-2xl p-4 sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between lg:gap-8">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">{kanon.name}</h1>
        {/* Die Zeile Klartext steht überall dort, wo der Name auftaucht — hier
            als Absatz direkt darunter (Wörterbuch, `lib/haushalt-bereiche.ts`). */}
        {kanon.klartext && (
          <p className="mt-1.5 max-w-[68ch] text-sm leading-relaxed text-muted-foreground">
            {kanon.klartext}
          </p>
        )}
        <p className="mt-2.5 max-w-[66ch] text-[15px] leading-relaxed text-foreground/90">
          {netto > 0 ? (
            rangNetto === 1 ? (
              <>Der geplante <strong>Zuschussbedarf</strong> dieses Bereichs beträgt {deMio(netto)}&#8239;Mio.&nbsp;€
                aus allgemeinen Haushaltsmitteln — mehr als bei jedem anderen Bereich
                {vergleich && faktor != null && faktor > 1 && bruttoTop.r.area !== z.area
                  ? <>, obwohl „{bereichKanon(vergleich.r.area).name}“ das {deMio(faktor)}-fache ausgibt</>
                  : null}.</>
            ) : (
              <>Der geplante Zuschussbedarf dieses Bereichs beträgt <strong>{deMio(netto)}&#8239;Mio.&nbsp;€</strong> aus
                allgemeinen Haushaltsmitteln — Platz {rangNetto} von {alle.length}.</>
            )
          ) : netto > -0.05 ? (
            // Unter 0,05 Mio. rundet `mio()` auf 0,0 — „er nimmt 0,0 Mio. €
            // mehr ein" wäre eine Zahl, die nichts sagt (nicht rechtsfähige
            // Stiftungen).
            <>Bei diesem Bereich halten sich Einnahmen und Ausgaben {year} ungefähr die Waage:
              {" "}<strong>{deMio(ein)}&#8239;Mio.&nbsp;€</strong> stehen
              {" "}<strong>{deMio(aus)}&#8239;Mio.&nbsp;€</strong> gegenüber.</>
          ) : (
            <>Für {year} sind die eigenen Erträge dieses Bereichs um{" "}
              <strong>{deMio(-netto)}&#8239;Mio.&nbsp;€</strong> höher als seine Aufwendungen.</>
          )}
        </p>
      </div>

      {/* Kennzahlen — dieselben drei Zahlen wie im Gegenbalken darunter, aber
          als Auskunft auf einen Blick. „trägt die Stadt" ist die Vokabel des
          ganzen Bereichs (Gegenbalken, Bereichskarten); „kostet die Stadt"
          wäre eine zweite für dieselbe Sache. */}
      <div className="flex flex-none flex-wrap gap-x-6 gap-y-3 sm:gap-x-7 lg:pt-1">
        <Summe label={`Aufwendungen ${year}`} value={aus} beleg={<Beleg q="plan" />} />
        <Summe label="eigene Erträge" value={ein} ton="ein" />
        {/* Dieselbe Schwelle wie unten im Balken (Rohwert-Vergleich), damit
            Kopf und Bild nie zwei verschiedene Richtungen behaupten. */}
        <Summe label={einVoran ? "Überschuss" : "Zuschussbedarf"} value={Math.abs(netto)} ton="signal" />
      </div>
      </div>

      {/* Die Rechnung als Gegenbalken (GB-04): zwei Leisten auf EINER Basis,
          die Lücke zwischen der kürzeren und der Basis trägt ihren Namen —
          Schraffur mit Signal-Kante, die Differenz-Konvention des Bereichs.
          Bei einem Überschuss dreht sich die Leserichtung um: Dann sind die
          Einnahmen die Basis, und die Lücke hinter den Ausgaben ist der
          Überschuss. Kein Rot in beiden Richtungen — ein Zuschussbedarf ist
          Daseinsvorsorge, keine Schwäche. */}
      <div className="mt-5">
        <Gegenbalken
          zeilen={einVoran ? [balkenEin, balkenAus] : [balkenAus, balkenEin]}
          basis={Math.max(rohAus, rohEin)}
          unit="Mio. €"
          restLabel={einVoran ? "Überschuss des Bereichs" : "Zuschussbedarf"}
        />
        {einVoran ? (
          <p className="mt-3 max-w-[76ch] border-t border-border/60 pt-2.5 text-[12.5px] leading-relaxed text-foreground/85">
            Dieser Bereich nimmt mehr ein, als er ausgibt — der Überschuss steht
            dem allgemeinen Topf zur Verfügung, aus dem die Zuschüsse der anderen
            Bereiche kommen.
          </p>
        ) : (
          <p className="mt-3 max-w-[76ch] border-t border-border/60 pt-2.5 text-[12.5px] leading-relaxed text-foreground/85">
            Eigene Erträge sind Gebühren, Entgelte, Erstattungen und
            zweckgebundene Zuschüsse. Den verbleibenden Zuschussbedarf finanziert
            der allgemeine Haushalt aus Steuern und Schlüsselzuweisungen.
            {/* Nur im Zuschuss-Fall: Der Prozentsatz trägt als Satz und im
                Vergleich — bei einem Überschuss gäbe es nichts zu decken, und
                auf der Finanzmanagement-Seite stand sonst ein „Bei … sind es
                60 € von 100", das sich auf nichts bezog. */}
            {d != null && (
              <> Von 100&nbsp;€ Ausgaben holt der Bereich {d}&nbsp;€ selbst herein.</>
            )}
            {d != null && vergleich?.d != null && (
              <>
                {" "}Bei „{bereichKanon(vergleich.r.area).name}“ sind es {vergleich.d}&nbsp;€ von 100.
                Der Unterschied sagt nichts darüber, wo sparsamer gewirtschaftet wird — er hängt
                daran, für welche Aufgaben Bund und Land Erstattungen zahlen und für welche nicht.
              </>
            )}
          </p>
        )}
      </div>
      </div>

      <BereichReiter reiter={reiterListe} aktiv={aktiv} onChange={setReiter} />

      <ReiterTafel id="ueberblick" aktiv={aktiv} className="flex flex-col gap-4">
        {/* Die Rechnung des Bereichs steht seit 24.08. oben auf der Tafel —
            der Überblick beginnt mit dem Blick HINTER ihre Einnahmen-Leiste. */}
        <EigeneErtraege daten={data} key={kanon.key} planEin={ein} planJahr={year} />

        {/* Brutto gegen Netto — der Umschalter IST das Lehrstück. */}
        <Karte>
          <Kicker>Brutto gegen Netto · alle Bereiche</Kicker>
          <p className="mb-3 mt-1 text-[12.5px] text-foreground/80">
            Die Sortierung zeigt entweder die gesamten Aufwendungen oder den
            verbleibenden Zuschussbedarf nach eigenen Erträgen.
          </p>
          {/* Scrollzeile: „Kosten für die Stadt (netto)" ragte auf 375 px über
              den Bildschirmrand und ließ die ganze Seite horizontal wackeln. */}
          <div className="scrollbar-none -mx-1 mb-3 overflow-x-auto px-1">
            <Segmented value={ranking} onChange={setRanking} tone="primary" className="w-max" options={[
              { value: "brutto", label: "Ausgaben (brutto)" },
              { value: "netto", label: "Kosten für die Stadt (netto)" },
            ]} />
          </div>
          {/* Eine Kopfzeile nur für die Einheit: In 60 px passt hinter jede
              Zahl kein „Mio. €", ohne die Balken zu stauchen. */}
          <p className="mb-1 text-right font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
            Mio.&nbsp;€
          </p>
          <div className="grid grid-cols-[minmax(110px,150px)_1fr_60px] items-center gap-x-2.5 gap-y-1.5 text-xs">
            {alle.slice(0, 6).map(({ r, netto: n, brutto: b }, i) => {
              const value = ranking === "netto" ? n : b;
              const ich = r.area === z.area;
              return (
                <div key={r.area} className="contents">
                  <span className={cn("truncate", ich && "font-bold")}>{bereichKanon(r.area).kurz}</span>
                  <div className="h-3.5 rounded-[3px] bg-muted">
                    <div className="h-full rounded-[3px]" style={{
                      width: `${Math.max((value / maxWert) * 100, 2)}%`,
                      background: `var(--hh-ein-${Math.min(i, 6)})`,
                    }} />
                  </div>
                  <span className={cn("text-right tabular-nums", ich && "font-bold")}>{deMio(value)}</span>
                </div>
              );
            })}
          </div>
          {bruttoTop.r.area !== nachNetto[0].r.area && (
            <p className="mt-3 rounded-lg bg-muted/60 p-2.5 text-xs leading-relaxed text-foreground/90">
              In der Brutto-Sicht steht {bereichKanon(bruttoTop.r.area).name} mit
              {" "}{deMio(bruttoTop.brutto)}&#8239;Mio.&nbsp;€ an erster Stelle. Weil dort aber
              {" "}{deMio(mio(bruttoTop.r.revenues))}&#8239;Mio.&nbsp;€ an Erstattungen und eigenen
              Einnahmen zurückfließen, bleibt {bereichKanon(nachNetto[0].r.area).name} unterm
              Strich am teuersten.
            </p>
          )}
          <Link href="/haushalt/produkte#bereiche"
            className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
            Alle {alle.length} Bereiche mit einer Zeile Klartext
            <ArrowRight aria-hidden className="h-3.5 w-3.5" />
          </Link>
        </Karte>

        {info && (
          <Karte>
            <Kicker>Was steckt drin</Kicker>
            <p className="mt-2 text-[13.5px] leading-relaxed text-foreground/90">{info}</p>
            <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              Diese redaktionelle Beschreibung beruht auf dem Vorbericht des
              Haushaltsplans; sie ist keine amtliche Gliederung.
            </p>
          </Karte>
        )}

        {/* Bis 16.08. stand hier „Die Produktebene mit Einzelbeträgen lesen wir
            erst ein". Sie ist seit #500 da — 2018–2023. Statt des Hinweises
            steht hier die Aufteilung selbst, mit dem Jahr, aus dem sie stammt,
            und dem ehrlichen Zusatz, dass sie das Kopfjahr nicht erreicht. */}
        {produktZeilen.length > 0 && produktJahr != null && (
          <Karte>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <Kicker>Was einzelne Aufgaben kosten</Kicker>
              <span className="font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
                Stand {produktJahr}
              </span>
            </div>
            <div className="mt-3 flex flex-col gap-1">
              {produktZeilen.map((p) => {
                const b = amount(-(p.result as number));
                return (
                  <Link key={p.product_no}
                    href={`/haushalt/produkte?nr=${encodeURIComponent(p.product_no)}`}
                    className="flex items-baseline gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-accent">
                    <span className="min-w-0 flex-1 truncate text-[12.5px]">{p.product_name}</span>
                    <span className="flex-none whitespace-nowrap font-mono text-[11.5px] tabular-nums">
                      {b.value}&#8239;<span className="text-muted-foreground">{b.unit}</span>
                    </span>
                  </Link>
                );
              })}
            </div>
            <p className="mt-2.5 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              {/* Bei Teilhaushalten mit genau einer bezuschussten Aufgabe stand
                  hier „Die 1 teuersten Aufgaben" — die Zahl kommt aus den
                  Daten, der Satz muss also beide Fälle können. */}
              {produktZeilen.length === 1
                ? <>Die teuerste Aufgabe dieses Bereichs nach Zuschussbedarf,</>
                : <>Die {produktZeilen.length} teuersten Aufgaben dieses Bereichs nach Zuschussbedarf,</>}
              {" "}aus dem Teilhaushaltsplan {produktJahr}<Beleg q="teilhaushalt" />. Für das
              Haushaltsjahr {year} gibt es die Produktebene noch nicht — die Stadt
              veröffentlicht sie mit den Teilplänen, und unser Bestand endet {produktJahr}.
            </p>
            <Link href="/haushalt/produkte"
              className="mt-2 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
              Alle Aufgaben durchsuchen
              <ArrowRight aria-hidden className="h-3.5 w-3.5" />
            </Link>
          </Karte>
        )}

        {/* Entwicklung — echte Reihe, sobald der Bereichsname über Jahre stabil
            ist. Der Entwurf schrieb „+44,4 Mio. seit 2020, durchgehend
            steigend" fest; beides wird hier gerechnet, und die Aussage
            „durchgehend" wird geprüft statt behauptet. */}
        <Karte>
          <div className="flex items-baseline justify-between gap-3">
            <Kicker>Entwicklung des Bereichs</Kicker>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {series.length >= 2
                ? `${series[0].year}–${series[series.length - 1].year} · ${series.length} Jahre`
                : "Noch keine Reihe"}
            </span>
          </div>
          {series.length >= 2 ? (() => {
            const werte = series.map((r) => -(mio(r.row.result) ?? 0));
            // Welche Größe die Reihe überhaupt beschreibt, entscheidet ihr
            // Vorzeichen. Ein Bereich mit Überschuss (Finanzmanagement) hat
            // durchweg negative Netto-Werte; „−80,0 Mio. € weniger
            // Zuschussbedarf" war dort eine doppelte Verneinung über einer
            // Größe, die es in diesem Bereich gar nicht gibt. Wo die Reihe die
            // Null kreuzt, gibt es keinen tragenden Begriff — dann steht nur
            // die Jahresliste, ohne große Deltazahl.
            const zuschuss = werte.every((w) => w > 0);
            const ueberschuss = werte.every((w) => w < 0);
            const groesse = zuschuss ? werte : ueberschuss ? werte.map((w) => -w) : null;
            const maxN = Math.max(...werte.map(Math.abs), 1);
            const kopf = (() => {
              if (!groesse) return null;
              const von = groesse[0];
              const bis = groesse[groesse.length - 1];
              const delta = Math.round((bis - von) * 10) / 10;
              const percent = von !== 0 ? Math.round(Math.abs(delta / von) * 100) : null;
              const monoton = groesse.every((w, i) => i === 0 || w >= groesse[i - 1])
                || groesse.every((w, i) => i === 0 || w <= groesse[i - 1]);
              return { delta, percent, monoton, von, bis, wort: zuschuss ? "Zuschussbedarf" : "Überschuss" };
            })();
            return (
              <>
                {kopf && (
                  <div className="mt-2.5 flex flex-wrap items-end gap-x-4 gap-y-1">
                    <p className="font-display text-[34px] font-bold leading-none tracking-tight tabular-nums text-signal">
                      {kopf.delta > 0 ? "+" : kopf.delta < 0 ? "−" : ""}{deMio(Math.abs(kopf.delta))}
                    </p>
                    <p className="max-w-[54ch] text-[12.5px] leading-relaxed text-foreground/85">
                      Mio.&nbsp;€ gegenüber {series[0].year}: Der {kopf.wort} des Bereichs
                      {" "}{kopf.delta >= 0 ? "stieg" : "sank"} von {deMio(kopf.von)} auf
                      {" "}{deMio(kopf.bis)}&nbsp;Mio.&nbsp;€
                      {kopf.percent != null && <> — {kopf.delta >= 0 ? "ein Plus" : "ein Minus"} von {kopf.percent}&nbsp;%</>}
                      {kopf.monoton && groesse!.length > 2 && <>, in jedem Jahr in dieselbe Richtung</>}.
                    </p>
                  </div>
                )}
                <div className="mt-3 grid grid-cols-[auto_1fr_auto_auto] items-center gap-x-3 gap-y-1 text-xs tabular-nums">
                  {series.map(({ year: j, row }, i) => (
                    <div key={j} className="contents">
                      <span className="font-mono text-muted-foreground">{j}</span>
                      <div className="h-2.5 rounded-[3px] bg-muted">
                        <div className="h-full rounded-[3px]" style={{
                          width: `${(Math.abs(werte[i]) / maxN) * 100}%`,
                          background: "var(--hh-ein-0)",
                        }} />
                      </div>
                      <span className="text-right">
                        {werte[i] > 0 ? `−${deMio(werte[i])}` : `+${deMio(-werte[i])}`}&#8239;Mio.&nbsp;€ netto
                      </span>
                      <span className="text-right text-muted-foreground">
                        {deMio(mio(row.expenses))}&#8239;Mio.&nbsp;€ Ausgaben
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
                  {series.length < years.length
                    ? <>Vor {series[0].year} führte der Plan den Bereich unter anderem Namen — die
                        Reihe beginnt dort, wo der Name belegt ist.</>
                    : <>Der Bereich heißt seit {series[0].year} unverändert; nur deshalb zeigen wir
                        die Reihe durchgehend. Wo Teilhaushalte umbenannt oder neu zugeschnitten
                        wurden, zeigen wir keine Kurve.</>}
                  {" "}Planwerte, nicht Jahresabschluss<Beleg q="plan" />.
                </p>
              </>
            );
          })() : (
            <div className="mt-3 rounded-xl border-2 border-dashed border-border bg-muted/40 p-5 text-center">
              <p className="mx-auto max-w-[52ch] text-[12.5px] leading-relaxed text-foreground/80">
                Für frühere Jahre führte der Haushaltsplan diesen Bereich unter anderem Namen —
                wir zeigen keine Kurve, bevor wir sie belegen können. Die Gesamtsummen gibt es:{" "}
                <Link href="/haushalt" className="font-semibold text-primary">Zeitreihe in der Übersicht</Link>.
              </p>
            </div>
          )}
        </Karte>

        {/* Beschlüsse: Die automatische Verknüpfung Amt → Teilhaushalt gibt es
            nicht, und sie wird hier auch nicht angedeutet. Was es gibt, ist
            die Suche — der ehrliche Weg. */}
        <div className="rounded-2xl border border-dashed border-border bg-card p-4">
          <div className="flex items-baseline justify-between gap-3">
            <Kicker>Dazu hat der Rat entschieden</Kicker>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">Verknüpfung [folgt]</span>
          </div>
          <p className="mt-2 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
            Beschlüsse mit Teilhaushalten automatisch zu verknüpfen, bauen wir noch — der
            Haushaltsplan nennt die Ämter, das Ratsinformationssystem die Gremien, und eine
            belastbare Brücke zwischen beidem haben wir nicht. Bis dahin findet die Suche
            alles, was der Rat zu diesem Bereich entschieden hat.
          </p>
          {/* Zwei Wege weiter, beide ehrlich: die Suche über den Bereichsnamen
              und eine vorformulierte Frage. Der Chip gibt dem Ratsgespräch nur
              den Fragetext mit — einen Bereichs-Kontext, den es auswerten
              könnte, gibt es nicht, und er wird hier auch nicht behauptet. */}
          <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-2">
            <Link href={`/council?q=${encodeURIComponent(kanon.name.split("/")[0].split(",")[0])}`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
              <Search aria-hidden className="h-3.5 w-3.5" />
              Beschlüsse zu „{kanon.name.split("/")[0].split(",")[0]}“ suchen
            </Link>
            <Link href={fragenHref({ q: `Was hat der Rat zuletzt zum Bereich ${kanon.name} entschieden?` })}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
              <MessageCircle aria-hidden className="h-3.5 w-3.5" />
              Frag den Rat zu diesem Bereich
            </Link>
          </div>
        </div>
      </ReiterTafel>

      {hatPlanIst && (
        <ReiterTafel id="planist" aktiv={aktiv} className="flex flex-col gap-4">
          {(() => {
            const abweichend = abschluss.filter(
              (p) => p.nr === 20 && p.plan_kind && p.plan_kind !== "budget");
            const letztesJahr = planIstJahre[planIstJahre.length - 1];
            const thhNr = abschluss.find((p) => p.sub_budget_no != null)?.sub_budget_no ?? kanon.sub_budget;
            const gruende = thhNr != null ? gruendeFuerBereich(data, letztesJahr, thhNr) : [];
            return (
              <Karte>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Kicker>Geplant und geworden</Kicker>
                  <Link href="/haushalt/plan-ist" className="text-[11.5px] font-semibold text-primary">
                    Alle Bereiche vergleichen →
                  </Link>
                </div>
                <p className="mb-3 mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
                  Ausgaben dieses Bereichs: was der Rat beschlossen hatte und was der
                  Jahresabschluss am Ende ausweist<Beleg q="ergebnisrechnung_thh" />.
                </p>
                {/* Hier eine Zeitreihe EINES Bereichs: Die Beträge liegen nah
                    beieinander, also trägt die Euro-Skala. Auf der
                    Vergleichsseite ist es umgekehrt — dort spreizen 6 bis 231
                    Mio. zu weit. */}
                {/* `alpha` hält die Jahre chronologisch — eine Zeitreihe nach
                    |Abweichung| sortiert wäre keine mehr. */}
                <Hantel zeilen={planIstZeilen} massstab="amount" sortierung="alpha" />
                {abweichend.length > 0 && (
                  <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
                    * In {[...new Set(abweichend.map((p) => p.year))].join(" und ")} vergleicht der
                    Abschluss nicht mit dem ursprünglichen Ansatz, sondern mit dem
                    fortgeschriebenen Plan
                    ({[...new Set(abweichend.map((p) => PLAN_ART_LABEL[p.plan_kind as PlanArt]))].join(", ")}).
                  </p>
                )}
                {gruende.length > 0 && (
                  <div className="mt-3 flex flex-col gap-2.5 border-t border-border/60 pt-3">
                    <Kicker>Was der Abschluss {letztesJahr} zu diesem Bereich sagt</Kicker>
                    {gruende.map((g) => (
                      <div key={g.nr} className="flex flex-col gap-1">
                        <span className="text-[12.5px] font-semibold">
                          {g.label}
                          <span className="ml-1.5 font-mono text-[11px] font-normal tabular-nums text-signal">
                            {(g.delta_meur ?? 0) > 0 ? "+" : ""}{deMio(g.delta_meur)}&#8239;Mio.&nbsp;€
                          </span>
                        </span>
                        <Warum reason={g} kompakt />
                      </div>
                    ))}
                    <p className="text-[11px] leading-relaxed text-muted-foreground">
                      Der Jahresabschluss erläutert seine Abweichungen nach Ertrags- und
                      Aufwandsarten für die ganze Stadt, nicht je Bereich<Beleg q="jahresabschluss" />.
                      Hier stehen die Erläuterungen, die diesen Bereich ausdrücklich nennen — sie
                      können also auch andere Bereiche mit betreffen.
                    </p>
                  </div>
                )}
              </Karte>
            );
          })()}
        </ReiterTafel>
      )}

      <ReiterTafel id="source" aktiv={aktiv} className="flex flex-col gap-4">
        <Karte>
          <Kicker>Diese Seite in einem Absatz</Kicker>
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Die Beträge oben sind <strong>Planwerte</strong> aus dem beschlossenen Haushaltsplan
            {" "}{year}. Sie zeigen, was der Rat vorgesehen hat, nicht das spätere Ergebnis.
            Tatsächliche Erträge und Aufwendungen veröffentlicht die Stadt im Jahresabschluss,
            der mit zeitlichem Abstand erscheint. Investitionen sind hier nicht enthalten;
            sie stehen im Finanzhaushalt.
          </p>
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Quelle dieser Seite:{" "}
            {source.url
              ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{source.text}</a>
              : source.text} · Teilhaushalt {kanon.name} · ordentliche Erträge und Aufwendungen.
          </p>
        </Karte>
        <Datenstand />
        <Quellenverzeichnis keys={quellen} />
      </ReiterTafel>
    </div>
    </Quellenkontext>
  );
}

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
const FELDER = ["years", "income_statement", "product_years", "variance_reasons"] as const;

/** Der Ausschnitt, den diese Seite holt. */
type Daten = HaushaltAuswahl<typeof FELDER[number]>;

export default function BereichPage() {
  // useSearchParams braucht eine Suspense-Grenze (Export-Konvention).
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>}>
      <BereichInner />
    </Suspense>
  );
}
