"use client";

// /haushalt/steuer?art=… — Steuer-Steckbrief (Design H-10/H-11/H-12).
//
// Ein Template für zwei Extreme: eine Steuer, deren Hebesatz der Rat setzt
// (Gewerbesteuer), und eine Einnahme, bei der er gar nichts entscheidet
// (Schlüsselzuweisungen, Einkommensteueranteil). Die dritte Stufe bleibt
// deshalb immer stehen — bei „Nichts." nur gestrichelt und ohne Signal.
//
// Reihenfolge nach H-10: erst „Wer entscheidet was" (die Frage, mit der Leute
// kommen), dann die Ist-Kurve, dann Hebesatz-Historie und Überschlag.

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltAuswahl, haushaltUrl, deMio } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import {
  STEUERARTEN, SPIELRAUM_LABEL, type SteuerArt, steuerartNachSlug,
} from "@/lib/haushalt-taxes";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/source";
import { LottiErklaert, LottiVergleich } from "@/components/haushalt/lotti-erklaert";
import { IstKurve } from "@/components/haushalt/ist-kurve";
import { SteuerPlanIst } from "@/components/haushalt/steuer-plan-ist";
import { EntgeltePlanIst } from "@/components/haushalt/entgelte-plan-ist";
import { EntgelteBereiche } from "@/components/haushalt/entgelte-bereiche";
import { HebesatzTreppe } from "@/components/haushalt/rate-treppe";
import { Seitenbuehne, ZaehlZahl } from "@/components/haushalt/seitenbuehne";
import { AbgelehnteStufe } from "@/components/haushalt/abgelehnte-stufe";
import { Grenzen } from "@/components/haushalt/steuer-grenzen";
import { WerZahlt } from "@/components/haushalt/wer-zahlt";
import { Gesetz } from "@/components/haushalt/gesetz";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

/** Die Einnahmeart zu `?art=…` — auch wenn im Query nicht der Slug steht.
 *
 *  Derselbe Grund wie beim Bereichs-Steckbrief: Wer den Link weitergibt oder
 *  tippt, schreibt den Titel („Gebühren und Beiträge") statt des Slugs. Der
 *  Vergleich läuft über eine Fassung ohne Trenn- und Sonderzeichen, auf BEIDEN
 *  Seiten dieselbe — geraten wird nichts, nur verschieden geschrieben. */
function steuerartFinden(eingang: string): SteuerArt | undefined {
  const treffer = steuerartNachSlug(eingang);
  if (treffer) return treffer;
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "");
  const gesucht = norm(eingang);
  if (!gesucht) return undefined;
  return STEUERARTEN.find((a) => norm(a.slug) === gesucht || norm(a.title) === gesucht);
}

/** Ein von Hand gepflegter Befund zu **einem** Haushaltsjahr: Die Verwaltung
 *  schlug höhere Hebesätze vor, der Rat lehnte ab.
 *
 *  Er steht hier und nicht in einer Tabelle, weil ihn keine hergibt — ein
 *  abgelehnter Vorschlag hinterlässt keine Zeile in `council_hebesaetze`
 *  (dort stehen nur Änderungen, und es gab keine).
 *
 *  **Deshalb trägt er sein Jahr als Feld und wird daran geprüft.** Bis
 *  19.08.2026 hing die Karte allein an `slug === "gewerbesteuer"` und stand
 *  damit ohne jede Jahresprüfung — ab dem Haushalt 2027 hätte sie eine
 *  überholte Aussage als aktuelle ausgegeben, und nichts hätte angeschlagen.
 *  Jetzt verschwindet sie von selbst, sobald der Bestand ein neueres
 *  Haushaltsjahr führt. Wer sie für das neue Jahr wiederhaben will, prüft den
 *  Beschluss und zieht `year` nach — sichtbar, statt still. */
const HEBESATZ_ABGELEHNT = {
  year: 2026,
  steuer: "gewerbesteuer",
  satz: "Die Verwaltung schlug vor, die Hebesätze zu erhöhen. Der Rat lehnte ab.",
};

function SteuerInner() {
  const slug = useSearchParams().get("art") ?? "gewerbesteuer";
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER));
  // Die Satzung kommt in einem EIGENEN Aufruf (wie auf /haushalt/schulden):
  // Sie trägt nur den vorgeschlagenen Hebesatz für den Befund unten, und der
  // Hauptaufruf dieser Seite soll dafür nicht wachsen.
  const { data: satzungDaten } = useFetch<
    HaushaltAuswahl<typeof SATZUNG_FELDER[number]>>(haushaltUrl(SATZUNG_FELDER));
  const art = steuerartFinden(slug);

  const series = useMemo(() => {
    if (!data || !art?.datenArt) return [];
    return data.taxes
      .filter((s) => s.kind === art.datenArt && s.amount != null && s.amount > 0)
      .map((s) => ({ year: s.year, amount: s.amount as number }))
      .sort((a, b) => a.year - b.year);
  }, [data, art]);

  // Der zweite Weg an die Zahl: die Ergebnisrechnung des Jahresabschlusses.
  // Nur die Gesamt-Zeilen der Kernverwaltung (`sub_budget_no === null`) — die
  // Teilhaushalte kommen weiter unten als Aufschlüsselung, addiert werden sie
  // hier nie: Sie ergeben dieselbe Summe noch einmal.
  const entgelt = useMemo(() => {
    if (!data || !art?.ergebnisPosten) return [];
    return (data.income_statement ?? [])
      .filter((z) => z.nr === art.ergebnisPosten && z.sub_budget_no === null)
      .sort((a, b) => a.year - b.year);
  }, [data, art]);

  if (!art) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Diese Einnahmeart kennen wir nicht.{" "}
        <Link href="/haushalt/einnahmen" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }
  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Steckbrief wird geladen …</div>;
  }

  // Schlüsselzuweisungen kommen aus der Steuerkraft-Tabelle, nicht aus den Steuern.
  const zuw = data.tax_capacity.filter((k) => k.allocations != null);
  const istZuweisung = art.slug === "schluesselzuweisungen";
  const zuwReihe = istZuweisung
    ? zuw.map((k) => ({ year: k.year, amount: k.allocations as number }))
    : [];
  // Die dritte Herkunft: der Jahresabschluss. `result` ist nullbar — ein
  // Jahrgang, dessen Posten noch nicht gelesen ist, bekommt keinen Punkt auf
  // der Kurve statt einer Null.
  const istEntgelt = !!art.ergebnisPosten;
  const entgeltReihe = entgelt
    .filter((z) => z.result != null)
    .map((z) => ({ year: z.year, amount: z.result as number }));

  const anzeigeReihe = istZuweisung ? zuwReihe : istEntgelt ? entgeltReihe : series;
  const letzte = anzeigeReihe.at(-1);

  // Der Anteil braucht seinen Nenner IM TEXT: „3 %" ohne „wovon" ist keine
  // Aussage. Und der Nenner ist nicht überall derselbe — Steuern misst man an
  // den Steuereinnahmen, Gebühren an allen ordentlichen Erträgen. Beides steht
  // in derselben Quelle wie der Zähler, gemischt wird nie.
  const bezug: { value: number | null; was: string } | null = istZuweisung
    ? null
    : istEntgelt
      ? {
          value: (data.income_statement ?? []).find(
            (z) => z.nr === 12 && z.sub_budget_no === null && z.year === letzte?.year,
          )?.result ?? null,
          was: "aller ordentlichen Erträge",
        }
      : {
          value: data.taxes.find(
            (s) => s.year === letzte?.year && s.kind === "total",
          )?.amount ?? null,
          was: "aller Steuereinnahmen",
        };
  const anteil = letzte && bezug?.value ? Math.round((letzte.amount / bezug.value) * 100) : null;
  const population = data.population?.population ?? 0;

  // Welche Quelle den Hauptbetrag trägt — einmal bestimmt, überall derselbe
  // Beleg-Chip. Drei Stellen zeigten ihn vorher einzeln an, und eine vierte
  // hätte die Reihe still zerrissen.
  const hauptQuelle: QuellenSchluessel = istZuweisung
    ? "tax_capacity" : istEntgelt ? "jahresabschluss" : "taxes";

  // Plan neben Ist — nur diese Steuer, nur die Jahrgänge, die Tabelle 1103
  // führt (drei je Ausgabe). `datenArt` ist derselbe Schlüssel wie in der
  // Ist-Reihe; daran hängt im Ingest auch die Prüfung der Jahresbeschriftung.
  const planIst = (data.tax_plan?.zeilen ?? [])
    .filter((z) => art.datenArt && z.kind === art.datenArt);

  // Die Hebesatz-Treppe dieser Steuer. Zwei Reihen nur bei der Grundsteuer
  // (B und A, dieselbe Einheit, derselbe Beschluss).
  const hebeAlle = data.tax_rates?.zeilen ?? [];
  const hebeHaupt = art.hebesatzArten?.[0]
    ? hebeAlle.filter((z) => z.kind === art.hebesatzArten![0]) : [];
  const hebeZweit = art.hebesatzArten?.[1]
    ? hebeAlle.filter((z) => z.kind === art.hebesatzArten![1]) : [];

  // Der Nenner zur Gewerbesteuer: wie viele Betriebe sie aufbringen
  // (Gewerbesteuerstatistik des Landesamts). Genommen wird der JÜNGSTE
  // Erhebungsjahrgang — und das ist nicht das jüngste Jahr der Kurve darüber:
  // Die Statistik erscheint rund fünf Jahre nach dem Erhebungsjahr. Dass beide
  // Zahlen aus verschiedenen Jahren stammen, schreibt der Block selbst an.
  const statistik = art.slug === "gewerbesteuer"
    ? (data.trade_tax_statistics?.zeilen ?? []).at(-1) ?? null
    : null;

  // Das Jahr, für das gerade ein Haushalt gilt — das jüngste mit einem
  // beschlossenen Ansatz. Daran hängt, ob der Befund unten noch der aktuelle
  // ist; `budgeted_years` führt die Finanzplanungsjahre bewusst nicht mit.
  const aktuellerHaushalt = data.budgeted_years?.at(-1) ?? null;

  // Der Hebesatz, der im Jahr des Aufkommens GALT.
  //
  // Tabelle 1105 führt nur die Änderungsjahre — ein Satz gilt bis zur nächsten
  // Änderung. Gesucht ist deshalb die letzte Stufe mit `year <= letzte.year`
  // und nicht etwa die jüngste Zeile der Reihe: Läge das Aufkommen ein Jahr
  // hinter einer frischen Erhöhung zurück (der Normalfall, das Ist kommt
  // später als der Beschluss), teilte man sonst durch einen Satz, der für
  // dieses Geld nie gegolten hat.
  //
  // Bis 19.08.2026 stand hier `art.rate` — eine Zahl im Quelltext
  // (`439` für die Gewerbesteuer). Sie stimmte zufällig, weil der Rat den Satz
  // seit 2015 nicht angefasst hat; der nächste Beschluss hätte sie still
  // falsch gemacht, während die echte Reihe schon danebenlag.
  const hebesatzGalt = letzte
    ? hebeHaupt.filter((z) => z.year <= letzte.year).at(-1) ?? null
    : null;
  const punktSatz = hebesatzGalt?.rate ?? null;

  // Ein Hebesatzpunkt, überschlagen aus dem Ist — bewusst als Überschlag
  // benannt. Nur wo Betrag und Hebesatz dieselbe Steuer meinen: Bei der
  // Grundsteuer tun sie das nicht (siehe `punktUnmoeglich`).
  const proPunkt = punktSatz && letzte && !art.punktUnmoeglich
    ? letzte.amount / punktSatz : null;

  // Für den Befund weiter unten („die Verwaltung schlug vor, der Rat lehnte
  // ab") zwei Zahlen — und zwar bewusst aus ZWEI Quellen:
  //
  //  * `geltendeStufe` ist die jüngste Zeile der Hebesatz-Reihe (Tabelle
  //    1105), also der Satz, der HEUTE gilt. Nicht `hebesatzGalt`: Der ist
  //    auf das letzte Ist-Jahr bezogen und damit die falsche Bezugsgröße für
  //    einen Vorschlag, der ein späteres Haushaltsjahr betrifft.
  //  * `vorgeschlagen` ist § 5 der Haushaltssatzung desselben Jahrgangs. Im
  //    Ratsinformationssystem liegen ausschließlich Verwaltungsentwürfe
  //    (`lib/haushalt.ts`, `HaushaltssatzungZeile`) — genau deshalb steht dort
  //    der Vorschlag, den der Rat abgelehnt hat, und nicht das Ergebnis.
  //    Trägt der Bestand ihn nicht oder liegt er nicht über dem geltenden
  //    Satz, zeigt die Grafik keine Höhe (die Komponente entscheidet das).
  const geltendeStufe = hebeHaupt.at(-1) ?? null;
  const vorgeschlagen = (satzungDaten?.budget_bylaw ?? [])
    .find((z) => z.year === HEBESATZ_ABGELEHNT.year && z.supplement === 0)
    ?.trade_tax_rate ?? null;

  // Das Aufkommen als `{year: euro}` — der Pflicht-Kontext neben jedem
  // Hebesatz-Sprung. Ohne ihn liest sich „+21 %" als „alle zahlen 21 % mehr",
  // und das war 2025 nachweislich falsch.
  const aufkommen: Record<number, number> = {};
  for (const s of series) aufkommen[s.year] = s.amount;

  // Die Quellen dieser Seite in Lese-Reihenfolge — daraus zählt der Provider
  // die Fußnoten-Nummern.
  //
  // „haushaltssatzung" nur, wo der abgelehnte Vorschlag auch steht: Die
  // Fußnoten dieser Seite sollen keine Quelle führen, aus der auf der
  // gezeigten Seite keine Zahl stammt.
  const zeigtBefund = art.slug === HEBESATZ_ABGELEHNT.steuer
    && aktuellerHaushalt === HEBESATZ_ABGELEHNT.year;
  const quellen: QuellenSchluessel[] = istZuweisung
    ? ["tax_capacity", "plan"]
    : istEntgelt
      ? ["jahresabschluss", "ergebnisrechnung_thh"]
      : ["taxes", ...(planIst.length ? (["tax_plan"] as const) : []),
         "tax_rates", ...(zeigtBefund ? (["budget_bylaw"] as const) : []),
         /* Die Landesstatistik steht nur im Verzeichnis, wenn ihre Zahlen auch
            auf der Seite stehen — sonst führte die Fußnotenliste eine Quelle,
            aus der hier nichts stammt (dieselbe Regel wie bei
            „haushaltssatzung" darüber). */
         ...(statistik ? (["lsn_gewerbesteuer"] as const) : [])];

  return (
    <Quellenkontext keys={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <Link href="/haushalt/einnahmen" className="hover:text-foreground">Woher das Geld kommt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">{art.title}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[26px]">{art.title}</h1>
          <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-foreground/90">
            <GlossaryText text={art.kurz} />
          </p>
        </div>
        {/* Wo keine Zahl steht, steht der Satz, dass keine dasteht — und warum.
            Bis 17.08. fiel die Kennzahl-Karte bei „Gebühren und Beiträge"
            ersatzlos weg: Der Steckbrief begann dann mit dem Erklärkasten, und
            die fehlende Zahl sah aus wie eine, an die niemand gedacht hat. Auf
            der Landkarte (/haushalt/einnahmen) trägt dieselbe Einnahmeart
            längst ein „Betrag noch nicht eingelesen"; zwei Seiten dürfen zur
            selben Lücke nicht Verschiedenes sagen. */}
        {!letzte && (
          <div className="w-full flex-none rounded-2xl border border-dashed border-border bg-card p-4 sm:w-[260px]">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Betrag
            </p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Keiner der offenen Datensätze führt diese Einnahme als eigene Zeile — deshalb
              steht hier keine Zahl. Geschätzt wird nichts.
            </p>
          </div>
        )}
        {letzte && (
          <div className="w-full flex-none rounded-2xl border border-border bg-card p-4 shadow-sm sm:w-[210px]">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              {istZuweisung ? `Erhalten ${letzte.year}` : `Eingenommen ${letzte.year}`}
            </p>
            <p className="mt-1.5 font-display text-[27px] font-bold leading-none tracking-tight tabular-nums text-[color:var(--hh-ein-0)]">
              {deMio(letzte.amount / 1e6)}
              <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
              <Beleg q={hauptQuelle} />
            </p>
            {anteil != null && (
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
                {anteil}&nbsp;% {bezug!.was} ({deMio(bezug!.value! / 1e6)}&#8239;Mio.&nbsp;€)
              </p>
            )}
          </div>
        )}
      </div>

      {/* Die Bühne (H5-02/H5-09): Steckbriefe tragen keine Schritt-Nummer,
          die Bühne gibt ihnen trotzdem ein Gesicht. Die eine Zahl ist der
          Hebesatz — die Stellschraube des Rats —, nicht der Betrag (der steht
          in der Kennzahl-Karte oben, mit eigenem Jahr). Nur wo eine
          Hebesatz-Reihe vorliegt (Realsteuern); erfunden wird keine. */}
      {(() => {
        const series = [...hebeHaupt].sort((a, b) => a.year - b.year);
        const akt = series.at(-1);
        if (series.length < 2 || !akt) return null;
        const stufen = series.slice(-4);
        const min = Math.min(...stufen.map((z) => z.rate));
        const max = Math.max(...stufen.map((z) => z.rate));
        const hoehe = (w: number) => (max > min ? 12 + ((w - min) / (max - min)) * 28 : 24);
        return (
          <Seitenbuehne
            kicker={`Steuer-Steckbrief · Hebesatz ${art.hebesatzArten?.[0] ?? art.title}`}
            zahl={<><ZaehlZahl value={akt.rate} />&#8239;% seit {akt.year}</>}
            sub={`davor ${series.length - 1} ${series.length - 1 === 1 ? "Änderung" : "Änderungen"} seit ${series[0].year} — beschlossen jeweils vom Rat`}
            minibild={{
              href: "#rate",
              label: "Hebesatz-Treppe — klickt zur ganzen Reihe seit 1980",
              skizze: (
                // Mit Achse und Werten (Tim, 26.08.: „komplett ohne Achse ohne
                // Daten … wenig sinnvoll"): Erste und letzte Stufe tragen
                // ihren Satz, darunter stehen die Änderungsjahre. Die Stufen
                // steigen beim Seitenaufbau nacheinander ein (sb-schritt) —
                // einmal, keine Schleife (H5-07).
                <>
                  <span className="relative block" style={{ height: 56 }}>
                    {stufen.map((z, i) => {
                      const links = (i / stufen.length) * 100;
                      const breite = 100 / stufen.length;
                      const beschriftet = i === 0 || i === stufen.length - 1;
                      return (
                        <span key={z.year}>
                          {i > 0 && (
                            <span className="sb-schritt absolute" style={{
                              left: `${links}%`,
                              bottom: Math.min(hoehe(stufen[i - 1].rate), hoehe(z.rate)),
                              height: Math.abs(hoehe(z.rate) - hoehe(stufen[i - 1].rate)),
                              borderLeft: "2px dashed var(--sb-strich)",
                              animationDelay: `${0.1 + i * 0.16}s`,
                            }} />
                          )}
                          <span className="sb-schritt absolute" style={{
                            left: `${links}%`, width: `${breite}%`,
                            bottom: hoehe(z.rate), borderTop: "3px solid var(--sb-voll)",
                            animationDelay: `${0.18 + i * 0.16}s`,
                          }} />
                          {beschriftet && (
                            <span className="sb-schritt absolute font-mono text-[9px] leading-none tabular-nums text-muted-foreground" style={{
                              [i === 0 ? "left" : "right"]: `${i === 0 ? links : 0}%`,
                              bottom: hoehe(z.rate) + 5,
                              animationDelay: `${0.26 + i * 0.16}s`,
                            }}>
                              {z.rate}&#8239;%
                            </span>
                          )}
                        </span>
                      );
                    })}
                  </span>
                  <span className="flex justify-between font-mono text-[9px] leading-none tabular-nums text-muted-foreground">
                    <span>{stufen[0].year}</span>
                    <span>{stufen[stufen.length - 1].year}</span>
                  </span>
                </>
              ),
            }}
          />
        );
      })()}

      {/* Wer entscheidet was — das didaktische Herzstück (H-10). */}
      <div className="rounded-2xl border border-primary/20 bg-card p-4 shadow-sm">
        <div className="flex items-baseline justify-between gap-3">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
            Wer entscheidet was
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            Spielraum: {SPIELRAUM_LABEL[art.spielraum]}
          </span>
        </div>
        {/* Die Spaltenzahl folgt den Stufen, nicht umgekehrt: „Gebühren und
            Beiträge" und die kleinen örtlichen Steuern haben zwei Stationen,
            und ein festes Drei-Spalten-Raster ließ dafür ein Drittel der
            Kartenbreite leer stehen. */}
        <div className={cn(
          "mt-3 grid gap-2",
          art.stufen.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-3",
        )}>
          {art.stufen.map((st) => (
            <div key={st.title} className={cn(
              "rounded-xl border p-3",
              st.rat ? "border-signal/55 bg-signal/[0.06]" : "border-border bg-muted/30",
              !st.rat && st.wer.startsWith("Rat") && "border-dashed",
            )}>
              <span className={cn(
                "inline-flex rounded-full px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide",
                st.rat ? "bg-signal text-signal-foreground" : "bg-muted text-muted-foreground",
              )}>
                {st.wer}
              </span>
              <p className="mt-2 text-[13px] font-bold leading-snug">{st.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-foreground/80">
                <GlossaryText text={st.text} />
                {/* Die Rechtsgrundlage der Stufe — führt auf den amtlichen
                    Volltext. Am Ende des Satzes und nicht als eigene Zeile:
                    Sie beantwortet eine Rückfrage, sie ist nicht die Aussage
                    der Karte. Stufen ohne einzelne Vorschrift („der Rat
                    beschließt die Satzung") tragen keinen Chip. */}
                {st.gesetz && <Gesetz g={st.gesetz} />}
              </p>
            </div>
          ))}
        </div>
        {art.beispiel && (
          <div className="mt-3 border-t border-border/60 pt-3">
            <p className="text-xs text-foreground/80">Beispiel:</p>
            <p className="mt-1.5 inline-block rounded-lg border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[12.5px]">
              {art.beispiel.rechnung}
            </p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{art.beispiel.note}</p>
          </div>
        )}
      </div>

      <LottiErklaert title={art.lotti.title} text={art.lotti.text} />

      {anzeigeReihe.length >= 2 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <IstKurve series={anzeigeReihe} />
          <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
            Quelle {istZuweisung
              ? "Schlüsselzuweisungen"
              : istEntgelt ? "Jahresabschluss" : "Steuereinnahmen"}: siehe Verzeichnis unten
            <Beleg q={hauptQuelle} />
          </p>
        </div>
      )}

      {/* Dieselbe Ordnung wie bei den Steuern: erst was hereinkam, dann was man
          erwartet hatte — nur aus der anderen Quelle. */}
      {istEntgelt && (
        <EntgeltePlanIst zeilen={entgelt} beleg={<Beleg q="jahresabschluss" />}
          keineWertung={art.planIstWertung} />
      )}

      {/* Wofür die Leute zahlen. Steht bewusst hinter der Kurve und nicht neben
          dem Betrag: Die Aufschlüsselung beantwortet die Frage „welche
          Gebühren eigentlich?", und die stellt sich, nachdem die Summe da ist. */}
      {istEntgelt && letzte && (
        <EntgelteBereiche
          zeilen={(data.income_statement ?? []).filter(
            (z) => z.nr === art.ergebnisPosten && z.sub_budget_no !== null && z.year === letzte.year,
          )}
          year={letzte.year}
          title={art.bereicheTitel}
          beleg={<Beleg q="ergebnisrechnung_thh" />}
        />
      )}

      {/* Die Grenze der Zahl — und zugleich die Brücke dorthin, wo der Rest
          steht. Beides in einem Block, weil es dieselbe Auskunft ist: Was hier
          fehlt, fehlt nicht überall. */}
      {istEntgelt && art.grenze && (
        <div className="rounded-2xl border border-dashed border-border bg-card p-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was hier nicht drinsteht
          </p>
          <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
            <GlossaryText text={art.grenze} />
          </p>
          <Link
            href="/haushalt/konzern#fees"
            className="mt-2.5 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary hover:underline"
          >
            Was du dafür zahlst — die Gebührenbedarfsberechnung
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      {/* „Geplant und geworden" steht DIREKT unter der Ist-Kurve: Die Kurve
          zeigt, was hereinkam, dieser Block, was man erwartet hatte. Weiter
          unten, hinter dem Hebesatz, verlöre er seinen Bezug. */}
      {planIst.length > 0 && (
        <SteuerPlanIst
          zeilen={planIst}
          abgrenzung={data.tax_plan?.abgrenzung ?? ""}
          beleg={<Beleg q="tax_plan" />}
        />
      )}

      {letzte && population > 0 && (
        /* „vom Land" stand hier bis 17.08. und war zu weit: Der Betrag ist
           die Schlüsselzuweisung, also zwei von drei Komponenten des
           Ausgleichs — die dritte (übertragener Wirkungskreis) fehlt darin
           und kommt ebenfalls vom Land. Der Satz benennt jetzt, was er
           teilt; die vollständige Zahl steht auf /haushalt/einnahmen. */
        <LottiVergleich
          betragMio={letzte.amount / 1e6}
          population={population}
          /* Die Steckbrief-Titel haben drei Genera; ein eingesetzter Titel ergab
             „aus der Gebühren und Beiträge". Wo der Artikel nicht passt, sagt
             `proKopfWas` den Satz selbst. */
          was={istZuweisung
            ? "an Schlüsselzuweisungen vom Land"
            : art.proKopfWas ?? `aus der ${art.title}`}
        />
      )}

      {/* „Und welche Firmen zahlen das?" — die Frage, die auf die Kurve folgt,
          und die einzige auf dieser Seite, die niemand beantworten darf.
          Sie steht HIER, weil sie an das Aufkommen anschließt („so viel kam
          herein — von wem?") und weil der Hebesatz-Teil darunter dann schon
          weiß, dass die Sprünge nicht vom Rat kommen.

          Am Slug festgemacht, und anders als beim Befund weiter unten braucht
          das keine Jahresprüfung: Der Block behauptet nichts über ein
          bestimmtes Jahr. Alles, was er an Zahlen nennt, rechnet er aus den
          übergebenen Reihen — veraltet der Bestand, veraltet die Aussage mit,
          statt stehen zu bleiben. */}
      {art.slug === "gewerbesteuer" && (
        <WerZahlt
          taxes={data.taxes}
          art={art.datenArt}
          /* Gemessen wird gegen die ANDERE Steuer mit einem Hebesatz: Nur so
             ist der Vergleich fair — gleicher Datensatz, gleiche Jahre, gleiche
             Stellschraube im Rat, und trotzdem hängt nur eine der beiden am
             Gewinn. Die Schreibweise kommt aus derselben Tabelle wie oben,
             nicht aus einem zweiten Literal daneben. */
          vergleichArt={steuerartNachSlug("grundsteuer")?.datenArt ?? null}
          vergleichTitel={steuerartNachSlug("grundsteuer")?.title ?? "Grundsteuer"}
          tax_rates={hebeHaupt}
          /* Der Nenner und der Satz, der zu ihm gehört. Beide reisen aus der
             API mit: Die Abgrenzung ist Teil der Zahl, nicht des Layouts. */
          statistik={statistik}
          statistikKurz={data.trade_tax_statistics?.abgrenzung_kurz ?? ""}
          statistikAbgrenzung={data.trade_tax_statistics?.abgrenzung ?? ""}
        />
      )}

      {/* Hebesatz + Überschlag, nur wo der Rat wirklich eine Stellschraube hat. */}
      {art.hebesatzArten && (
        <>
        {/* Die Treppe seit 1980 (Jahrbuch 1105). Bis 18.08.2026 stand hier ein
            einzelner Kasten „2025 · Rat" und darunter der Satz, eine Reihe der
            Vorjahre liege uns nicht vor. Sie lag die ganze Zeit vor — auf
            demselben Blatt wie die Steuereinnahmen, die wir längst lesen. */}
        {hebeHaupt.length >= 2 ? (
          <div id="rate" className="scroll-mt-20">
          <HebesatzTreppe
            series={hebeHaupt}
            zweitreihe={hebeZweit}
            zweitLabel={art.hebesatzArten?.[1]}
            title={art.title}
            aufkommen={aufkommen}
            /* Bei der Grundsteuer heißt das Aufkommen NICHT wie der Hebesatz
               daneben: Der offene Datensatz führt A und B in einer Spalte, die
               Sätze gelten getrennt. Dieselbe Grenze, die auch den Überschlag
               „ein Punkt mehr" verbietet (`punktUnmoeglich`). */
            aufkommenLabel={art.slug === "grundsteuer"
              ? "Grundsteuer A und B zusammen" : `${art.title}`}
            bemessungNeu={data.tax_rates?.bemessung_neu ?? {}}
            abgrenzung={data.tax_rates?.abgrenzung ?? ""}
            /* Woran die Bemessungsgrundlage hängt — sonst liest sich die Liste
               darunter falsch herum. Bei der Gewerbesteuer fiel 2011 das
               Aufkommen, obwohl der Rat den Hebesatz erhöhte; das lag an den
               Gewinnen, nicht am Beschluss. Beide Sätze stehen so schon in den
               Stufen oben („Wer entscheidet was"). */
            grundlage={
              art.slug === "gewerbesteuer"
                ? "Hier ist der Messbetrag der Gewinn der Unternehmen — er schwankt von Jahr zu Jahr stark, und zwar unabhängig davon, was der Rat beschließt."
                : art.slug === "grundsteuer"
                  ? "Hier hängt der Messbetrag am Wert des Grundstücks, den das Finanzamt festsetzt. 2025 hat es alle Werte auf einmal neu bestimmt."
                  : undefined
            }
            beleg={<Beleg q="tax_rates" />}
            aufkommenBeleg={<Beleg q="taxes" />}
          />
          </div>
        ) : (
          /* Der Rückfall, wenn die Reihe fehlt — und zwar OHNE Zahl.
             Bis 19.08.2026 stand hier ein Kasten „2025 · Rat — Hebesatz 439 %"
             aus `art.rate`, also aus dem Quelltext. Das war die schlechteste
             Stelle für eine hartkodierte Zahl: ein Beleg-Chip daneben, der auf
             Tabelle 1105 zeigte, während die Zahl gar nicht von dort kam.
             Fehlt die Reihe, hat die Seite keinen belegten Satz — dann steht
             hier nichts als der Satz, dass er fehlt. */
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Der Hebesatz im Rat
            </p>
            <p className="mt-3 rounded-lg border border-dashed border-border p-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              Für diese Steuer liegt uns die Hebesatz-Reihe gerade nicht vor.
              Wir schätzen sie nicht und nennen auch keinen einzelnen Satz,
              den wir nicht belegen können.
            </p>
          </div>
        )}

        {(zeigtBefund || proPunkt != null) && (
        <div className="grid gap-3 lg:grid-cols-[1fr_310px]">
          {zeigtBefund && (
            <div className="flex flex-col rounded-2xl border border-border bg-card p-4 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <p className="font-mono text-[10px] uppercase tracking-wide text-primary">
                  Haushalt {HEBESATZ_ABGELEHNT.year} · Rat
                </p>
                <span className="rounded-full border border-[#fecaca] bg-[#fef2f2] px-2 py-0.5 text-[10.5px] font-semibold text-[#b91c1c]">
                  Abgelehnt
                </span>
              </div>
              <p className="mt-1.5 text-[13px] font-semibold leading-snug">
                {HEBESATZ_ABGELEHNT.satz}
              </p>
              {/* Das Bild dazu — ohne geltenden Satz gar nicht: Ein
                  schraffiertes Stück ohne Bezugsgröße zeigt nichts. */}
              {geltendeStufe && (
                <AbgelehnteStufe
                  year={HEBESATZ_ABGELEHNT.year}
                  geltend={geltendeStufe.rate}
                  geltendSeit={geltendeStufe.year}
                  vorgeschlagen={vorgeschlagen}
                  proPunkt={proPunkt}
                  beleg={<Beleg q="tax_rates" />}
                  satzungBeleg={<Beleg q="budget_bylaw" />}
                />
              )}
              {/* Der Verweis auf die Treppe nur, wo eine steht: Ohne
                  eingelesene Reihe zeigt der Block darüber einen einzelnen
                  Kasten, und „die Treppe darüber" zeigte ins Leere. */}
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                Hier entscheidet die Kommunalpolitik über die Höhe der Einnahmen
                {hebeHaupt.length >= 2
                  ? ` — die Treppe darüber hätte ${HEBESATZ_ABGELEHNT.year} eine Stufe mehr bekommen.`
                  : "."}
              </p>
            </div>
          )}

          {proPunkt != null && (
            <div className="rounded-2xl border border-signal/40 bg-card p-4 shadow-sm">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
                Was brächte ein Punkt mehr?
              </p>
              <p className="mt-2 font-display text-2xl font-bold tracking-tight tabular-nums">
                ≈ {deMio(proPunkt / 1e6)}
                <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
              </p>
              {/* Die offengelegte Rechnung bleibt stehen — wer die Zahl
                  nachrechnen will, soll das können, ohne uns zu glauben. Seit
                  19.08.2026 steht das JAHR beider Größen dabei: Ohne es ließe
                  sich nicht prüfen, ob Aufkommen und Satz dasselbe Jahr
                  meinen — und genau das ist die Annahme, auf der der
                  Überschlag beruht. */}
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-foreground/80">
                Überschlagen: {deMio(letzte!.amount / 1e6)}&#8239;Mio.&nbsp;€ (Ist {letzte!.year})
                bei {punktSatz} Punkten, geteilt durch {punktSatz}.
              </p>
              {/* Hier stand bis 16.08. „Brutto — was davon in der Stadtkasse
                  bleibt, ist weniger". Falsch: Der Datensatz weist die
                  Gewerbesteuer bereits NACH Abzug der Umlage aus (siehe
                  Quellenverzeichnis), der Überschlag also auch. Was den Betrag
                  weiter drücken kann, ist der Finanzausgleich — und der lässt
                  sich nicht beziffern (components/haushalt/finanzausgleich-daempfer.tsx). */}
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
                Der Betrag ist bereits <strong>nach Abzug der Umlage</strong> an Bund und Land —
                so führt der offene Datensatz die Gewerbesteuer.<Beleg q="taxes" /> Ob das Land
                über den Finanzausgleich zusätzlich gegenrechnet, hängt an seiner Formel; wie
                stark, geben die Zahlen nicht her.
              </p>
              {/* „und Grundstückswerte" stand hier, solange die Karte auch bei
                  der Grundsteuer erschien — dort tut sie es nicht mehr. */}
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                Das ist eine vereinfachte eigene Rechnung, keine amtliche Prognose. Sie
                unterstellt unveränderte Messbeträge. Tatsächlich können sich Gewinne und
                damit das Steueraufkommen unabhängig vom Hebesatz verändern.
              </p>
              <Link href="/haushalt/labor"
                className="mt-2.5 inline-flex text-[12px] font-semibold text-primary">
                Im Labor ausprobieren →
              </Link>
            </div>
          )}
        </div>
        )}
        </>
      )}

      <Grenzen art={art} />

      <div className="flex flex-wrap gap-2">
        {STEUERARTEN.filter((a) => a.slug !== art.slug).map((a) => (
          <Link key={a.slug} href={`/haushalt/steuer?art=${a.slug}`}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-[11.5px] hover:border-primary/40">
            {a.title}
          </Link>
        ))}
      </div>

      <Quellenverzeichnis keys={quellen} />
    </div>
    </Quellenkontext>
  );
}

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
// `budgeted_years` ist die kleinste Auskunft darüber, für welches Jahr gerade
// ein Haushalt gilt (eine Liste von Zahlen). Die Seite braucht sie, damit der
// Befund zum abgelehnten Hebesatz-Vorschlag nicht überlebt, was er beschreibt.
// `income_statement` kam am 24.08.2026 dazu — der zweite Weg an die Zahl, für
// Einnahmearten, die keine Steuer sind (`ergebnisPosten`). Die Liste trägt
// alle Jahrgänge und Teilhaushalte; gefiltert wird hier, nicht im Backend, wie
// auf /haushalt/bereich und /haushalt/plan-ist auch.
const FELDER = ["taxes", "tax_capacity", "tax_plan", "tax_rates", "population",
  "budgeted_years", "income_statement", "trade_tax_statistics"] as const;
const SATZUNG_FELDER = ["budget_bylaw"] as const;

export default function SteuerPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Steckbrief wird geladen …</div>}>
      <SteuerInner />
    </Suspense>
  );
}
