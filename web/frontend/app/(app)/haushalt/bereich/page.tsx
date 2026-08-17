"use client";

// Teilhaushalt-Dossier. Dramaturgie wie die Beschluss-Seiten: eine These, dann
// Karte für Karte der Beleg — Wasserfall, Brutto-gegen-Netto-Umschalter (das
// Lehrstück), Was steckt drin, Entwicklung.
//
// Query-Param statt dynamischem Segment (/haushalt/bereich?name=…): Der
// Capacitor-Export (output: export) kennt die Bereichs-Slugs zur Bauzeit
// nicht — dieselbe Konvention wie die Beschluss-Seite (/council/decision?id=).
//
// DREI ÄNDERUNGEN AM BESTAND, jede mit einem Grund:
//
// 1. Der Kostendeckungsgrad-Ring ist weg. Ein Ring beantwortet „wie viel
//    Prozent", die Frage der Seite ist aber „wie viele Millionen". Stattdessen
//    steht oben der Wasserfall: Ausgaben, davon abgezogen die eigenen Erträge,
//    übrig der Betrag, den die Allgemeinheit trägt — in Millionen, als eine
//    Bewegung. Der Prozentsatz bleibt als Satz erhalten, dort wo er trägt:
//    im Vergleich zweier Bereiche.
// 2. Die Bereichsnamen laufen durch `lib/haushalt-bereiche.ts`. Vorher
//    verglich diese Seite Namen über ihr erstes Wort („Personal…"), um die
//    Zeilen des Jahresabschlusses zu finden — das ging gut, solange kein
//    Bereich mit demselben Wort begann. Jetzt entscheidet der kanonische
//    Schlüssel.
// 3. Reiter statt einer sehr langen Rolle. Was NICHT hinter einem Reiter
//    verschwindet: der Brutto/Netto-Umschalter (Begründung in
//    `components/haushalt/bereich-reiter.tsx`).

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, ChevronRight, MessageCircle, Search } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { fragenHref } from "@/lib/routes";
import {
  ERTRAGSART_KURZ, HaushaltDaten, HaushaltZeile, PLAN_ART_LABEL, PlanArt,
  ProdukteAntwort, betrag, bereichInfo, bereichSlug, bereiche, bereichsReihe,
  deMio, deckung, gruendeFuerBereich, jahreSortiert, mio, quellenLabel,
} from "@/lib/haushalt";
import { bereichKanon, bereichSchluessel } from "@/lib/haushalt-bereiche";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Hantel } from "@/components/haushalt/hantel";
import { Warum } from "@/components/haushalt/warum";
import { Wasserfall, type WasserfallSchritt } from "@/components/grafik/wasserfall";
import { BereichReiter, ReiterTafel, type Reiter } from "@/components/haushalt/bereich-reiter";
import { Datenstand } from "@/components/haushalt/datenstand";
import { cn } from "@/lib/utils";

type ReiterId = "ueberblick" | "planist" | "quelle";

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

/** Kennzahl im Seitenkopf. Die Einheit hängt an jeder Zahl statt einmal am
 *  Ende der Reihe: Umbrechen die drei auf 375 px, stünde sie sonst allein in
 *  einer vierten Zeile und gehörte sichtbar zu nichts mehr. */
function Kopfzahl({ label, wert, ton, beleg }: {
  label: string; wert: number; ton?: "ein" | "signal"; beleg?: React.ReactNode;
}) {
  return (
    <div>
      <p className={cn(
        "text-[11.5px]",
        ton === "signal" ? "text-signal" : "text-muted-foreground",
      )}>{label}{beleg}</p>
      <p className={cn(
        "mt-0.5 font-display text-xl font-bold tabular-nums sm:text-[23px]",
        ton === "signal" && "text-signal",
        ton === "ein" && "text-[color:var(--hh-ein-0)]",
      )}>
        {deMio(wert)}
        <span className="ml-1 text-[11.5px] font-semibold text-muted-foreground">Mio.&nbsp;€</span>
      </p>
    </div>
  );
}

/** Woraus die eigenen Erträge eines Bereichs bestehen — aus dem Jahresabschluss.
 *
 *  Der Entwurf wollte hier einen Satz („vor allem Elternbeiträge und
 *  Landesmittel"). Der stimmt so nicht: Bei Jugend und Familie sind die
 *  öffentlich-rechtlichen Entgelte, in denen die Elternbeiträge stecken, die
 *  VIERTgrößte Position. Statt eines geschätzten Satzes steht hier die
 *  ausgelesene Aufteilung — mit dem Jahr, aus dem sie stammt. */
function EigeneErtraege({ daten, schluessel, planEin, planJahr }: {
  daten: HaushaltDaten;
  schluessel: string | null;
  planEin: number;
  planJahr: number;
}) {
  const posten = (daten.ergebnisrechnung ?? []).filter(
    (p) => p.thh_name != null && bereichSchluessel(p.thh_name) === schluessel
           && p.nr >= 1 && p.nr <= 11 && (p.ergebnis ?? 0) > 0);
  if (!posten.length || !schluessel) return null;
  const jahr = Math.max(...posten.map((p) => p.jahr));
  const arten = posten
    .filter((p) => p.jahr === jahr)
    .map((p) => ({ nr: p.nr, label: ERTRAGSART_KURZ[p.nr] ?? p.bezeichnung, wert: p.ergebnis as number }))
    .sort((a, b) => b.wert - a.wert);
  if (arten.length < 2) return null;
  const gesamt = arten.reduce((s, a) => s + a.wert, 0);

  return (
    <Karte>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <Kicker>Woraus die eigenen Einnahmen bestehen</Kicker>
        <span className="font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
          Ist {jahr}
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
                width: `${(a.wert / arten[0].wert) * 100}%`,
                background: `var(--hh-ein-${Math.min(i, 6)})`,
              }} />
            </div>
            {/* `whitespace-nowrap`: „10,9 Mio. €" brach sonst hinter „Mio."
                um, und das € stand allein in einer zweiten Zeile. Die Einheit
                steht je Zeile, weil `betrag()` sie mit der Größenordnung
                wechselt — ein gemeinsamer Kopf wäre für die kleinen Posten
                falsch. */}
            <span className="w-[86px] flex-none whitespace-nowrap text-right font-mono text-[11.5px] tabular-nums">
              {betrag(a.wert).wert}&#8239;<span className="text-muted-foreground">{betrag(a.wert).einheit}</span>
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
        Zusammen {betrag(gesamt).wert}&nbsp;{betrag(gesamt).einheit} — aus dem Jahresabschluss
        {" "}{jahr}<Beleg q="ergebnisrechnung_thh" />. Der Plan für {planJahr} weist
        {" "}{deMio(planEin)}&nbsp;Mio.&nbsp;€ aus; die Aufteilung dazu gibt es erst,
        wenn das Jahr abgerechnet ist.
      </p>
    </Karte>
  );
}

function BereichInner() {
  const slug = useSearchParams().get("name") ?? "";
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const [ranking, setRanking] = useState<"netto" | "brutto">("netto");
  const [reiter, setReiter] = useState<ReiterId>("ueberblick");

  const jahre = useMemo(() => (data ? jahreSortiert(data) : []), [data]);
  const jahr = jahre[jahre.length - 1];
  const zeilen = data && jahr ? data.jahre[String(jahr)] ?? [] : [];
  const z = bereiche(zeilen).find((r) => bereichSlug(r.bereich) === slug);
  const kanon = z ? bereichKanon(z.bereich) : null;

  // Produktebene: das jüngste Jahr, für das sie vorliegt — und nur für diesen
  // Teilhaushalt. Ohne Nummer (unbekannter Bereich) fragen wir gar nicht erst.
  const produktJahr = useMemo(() => {
    const js = (data?.produkt_jahre ?? []).slice().sort((a, b) => a - b);
    return js[js.length - 1] ?? null;
  }, [data]);
  const { data: produkte } = useFetch<ProdukteAntwort>(
    produktJahr != null && kanon?.thh != null
      ? `/council/haushalt/produkte?jahr=${produktJahr}&thh=${kanon.thh}`
      : null);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }
  if (!z || !jahr || !kanon) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Diesen Bereich kennen wir nicht.{" "}
        <Link href="/haushalt/bereiche" className="font-semibold text-primary">Alle Bereiche ansehen</Link>
      </div>
    );
  }

  const aus = mio(z.aufwendungen) ?? 0;
  const ein = mio(z.ertraege) ?? 0;
  const netto = -(mio(z.ergebnis) ?? 0);
  const alle = bereiche(zeilen)
    .map((r) => ({ r, netto: -(mio(r.ergebnis) ?? 0), brutto: mio(r.aufwendungen) ?? 0, d: deckung(r) }))
    .sort((a, b) => (ranking === "netto" ? b.netto - a.netto : b.brutto - a.brutto));
  const nachNetto = [...alle].sort((a, b) => b.netto - a.netto);
  const nachBrutto = [...alle].sort((a, b) => b.brutto - a.brutto);
  const rangNetto = nachNetto.findIndex((x) => x.r.bereich === z.bereich) + 1;
  const bruttoTop = nachBrutto[0];
  const reihe = bereichsReihe(data, z.bereich);
  const quelle = quellenLabel(zeilen, jahr);
  const info = bereichInfo(z.bereich);
  const maxWert = Math.max(...alle.map((x) => (ranking === "netto" ? x.netto : x.brutto)), 1);
  const d = deckung(z);

  // Vergleichsbereich für den Kostendeckungs-Satz: der größte andere Bereich
  // nach Ausgaben. „Fast doppelt so viel" stand hier bis 16.08. als feste
  // Wendung — 283,1 zu 169,2 ist Faktor 1,67. Solche Größenverhältnisse
  // werden gerechnet und mitgeschrieben, nicht getextet.
  const vergleich = nachBrutto.find((x) => x.r.bereich !== z.bereich) ?? null;
  const faktor = vergleich && (mio(z.aufwendungen) ?? 0) > 0
    ? Math.round((vergleich.brutto / aus) * 10) / 10 : null;

  // Zeilen des Jahresabschlusses zu diesem Teilhaushalt — über den kanonischen
  // Schlüssel, nicht über das erste Wort des Namens.
  const abschluss = (data.ergebnisrechnung ?? []).filter(
    (p) => p.thh_name != null && bereichSchluessel(p.thh_name) === kanon.schluessel
           && (p.nr === 12 || p.nr === 20));
  const planIstJahre = [...new Set(abschluss.map((p) => p.jahr))].sort((a, b) => a - b);
  const planIstZeilen = planIstJahre
    .map((j) => {
      const a = abschluss.find((p) => p.jahr === j && p.nr === 20);
      // `plan` ist die Bezugsgröße des jeweiligen Jahrgangs, nicht überall der
      // nackte Ansatz — 2018 und 2020 weichen ab (Fußnote unten).
      return {
        label: String(j) + (a?.plan_art && a.plan_art !== "ansatz" ? "*" : ""),
        plan: mio(a?.plan), ist: mio(a?.ergebnis),
      };
    })
    .filter((r) => r.plan != null && r.ist != null);
  const hatPlanIst = planIstZeilen.length > 0;

  const produktZeilen = (produkte?.produkte ?? [])
    .filter((p) => p.ergebnis != null && p.ergebnis < 0)
    .sort((a, b) => (a.ergebnis as number) - (b.ergebnis as number))
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
    { id: "quelle", label: "Quelle" },
  ];
  const aktiv = reiterListe.some((r) => r.id === reiter) ? reiter : "ueberblick";

  return (
    <Quellenkontext schluessel={quellen} jahr={jahr}>
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt {jahr}</Link>
        <ChevronRight aria-hidden className="h-3 w-3" />
        <Link href="/haushalt/bereiche" className="hover:text-foreground">Alle Bereiche</Link>
        <ChevronRight aria-hidden className="h-3 w-3" />
        <span className="font-semibold text-foreground">{kanon.name}</span>
      </div>

      {/* Kopf und Kennzahlen nebeneinander, sobald Platz ist. Die Absätze
          bleiben bei 66–68 Zeichen — längere Zeilen liest niemand gern —,
          aber der Rest der Breite stand vorher leer, weil die Kennzahlen-
          karte darunter die volle Breite nahm für drei Zahlen. */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-8">
      <div className="min-w-0 lg:flex-1">
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
              <>Unterm Strich <strong>trägt die Stadt</strong> für diesen Bereich {deMio(netto)}&#8239;Mio.&nbsp;€
                aus allgemeinen Steuermitteln — mehr als für jeden anderen
                {vergleich && faktor != null && faktor > 1 && bruttoTop.r.bereich !== z.bereich
                  ? <>, obwohl „{bereichKanon(vergleich.r.bereich).name}“ das {deMio(faktor)}-fache ausgibt</>
                  : null}.</>
            ) : (
              <>Unterm Strich trägt die Stadt für diesen Bereich <strong>{deMio(netto)}&#8239;Mio.&nbsp;€</strong> aus
                allgemeinen Steuermitteln — Platz {rangNetto} von {alle.length} nach Zuschussbedarf.</>
            )
          ) : netto > -0.05 ? (
            // Unter 0,05 Mio. rundet `mio()` auf 0,0 — „er nimmt 0,0 Mio. €
            // mehr ein" wäre eine Zahl, die nichts sagt (nicht rechtsfähige
            // Stiftungen).
            <>Bei diesem Bereich halten sich Einnahmen und Ausgaben {jahr} ungefähr die Waage:
              {" "}<strong>{deMio(ein)}&#8239;Mio.&nbsp;€</strong> stehen
              {" "}<strong>{deMio(aus)}&#8239;Mio.&nbsp;€</strong> gegenüber.</>
          ) : (
            <>Dieser Bereich trägt sich {jahr} selbst — er nimmt <strong>{deMio(-netto)}&#8239;Mio.&nbsp;€</strong> mehr
              ein, als er ausgibt.</>
          )}
        </p>
      </div>

      {/* Kennzahlen — dieselben drei Zahlen wie im Wasserfall, aber sofort
          lesbar. „trägt die Stadt" ist die Vokabel des ganzen Bereichs
          (Gegenbalken, Wasserfall, Bereichskarten); „kostet die Stadt" wäre
          eine zweite für dieselbe Sache. */}
      <div className="flex flex-none flex-wrap gap-x-8 gap-y-3 rounded-2xl border border-border bg-card px-4 py-3.5 shadow-sm lg:flex-col lg:gap-y-3.5">
        <Kopfzahl label={`Ausgaben ${jahr}`} wert={aus} beleg={<Beleg q="plan" />} />
        <Kopfzahl label="eigene Einnahmen" wert={ein} ton="ein" />
        {/* Dieselbe Schwelle wie im Wasserfall (`netto < 0`), damit Kopf und
            Bild nie zwei verschiedene Richtungen behaupten. */}
        <Kopfzahl label={netto < 0 ? "Überschuss" : "trägt die Stadt"} wert={Math.abs(netto)} ton="signal" />
      </div>
      </div>

      <BereichReiter reiter={reiterListe} aktiv={aktiv} onChange={setReiter} />

      <ReiterTafel id="ueberblick" aktiv={aktiv} className="flex flex-col gap-4">
        <Karte>
          {/* Die Rechnung als Wasserfall (GB-14, `components/grafik/`). Die
              Schritte stellt die SEITE zusammen, weil nur sie die Richtung
              kennt: Bei einem Überschuss dreht sich die Leserichtung um —
              dann steht oben, was reinkommt, und die Ausgaben sind der Abzug.
              Das Ergebnis kommt als eigener Wert mit (aus dem Rohwert
              gerundet), nicht als `aus − ein`: Beide Beträge sind schon auf
              0,1 Mio. gerundet, und bei den nicht rechtsfähigen Stiftungen
              kippte durch die Doppelrundung einmal sogar die Richtung. */}
          <Wasserfall
            kicker={netto < 0 ? "Was reinkommt, was rausgeht" : "Was rausgeht, was reinkommt"}
            einheit={`Mio. € ${jahr}`}
            schritte={(netto < 0 ? [
              { label: "Eigene Erträge des Bereichs", wert: ein, art: "start",
                farbe: "var(--hh-ein-0)" },
              { label: "Ausgaben des Bereichs", wert: aus, art: "abzug",
                farbe: "var(--hh-aus-0)",
                hinweis: "was der Bereich für seine eigenen Aufgaben braucht" },
              { label: "Überschuss des Bereichs",
                wert: Math.round(Math.abs(netto) * 10) / 10, art: "ergebnis",
                hinweis: "steht dem allgemeinen Topf zur Verfügung" },
            ] : [
              { label: "Ausgaben des Bereichs", wert: aus, art: "start" },
              { label: "eigene Erträge des Bereichs", wert: ein, art: "abzug",
                hinweis: "Gebühren, Entgelte, Erstattungen und zweckgebundene Zuschüsse" },
              { label: "trägt die Stadt",
                wert: Math.round(Math.abs(netto) * 10) / 10, art: "ergebnis",
                hinweis: "aus Steuermitteln, dem allgemeinen Topf aus Steuern und Schlüsselzuweisungen" },
            ]) as WasserfallSchritt[]}
          />
          {/* Nur im Zuschuss-Fall: Der Prozentsatz trägt als Satz und im
              Vergleich — bei einem Überschuss gäbe es nichts zu decken, und
              auf der Finanzmanagement-Seite stand sonst ein „Bei … sind es
              60 € von 100", das sich auf nichts bezog. */}
          {ein < aus && d != null && (
            <p className="mt-2.5 max-w-[74ch] border-t border-border/60 pt-2.5 text-[12.5px] leading-relaxed text-foreground/85">
              Von 100&nbsp;€ Ausgaben holt der Bereich {d}&nbsp;€ selbst herein.
              {vergleich?.d != null && (
                <>
                  {" "}Bei „{bereichKanon(vergleich.r.bereich).name}“ sind es {vergleich.d}&nbsp;€ von 100.
                  Der Unterschied sagt nichts darüber, wo sparsamer gewirtschaftet wird — er hängt
                  daran, für welche Aufgaben Bund und Land Erstattungen zahlen und für welche nicht.
                </>
              )}
            </p>
          )}
        </Karte>

        <EigeneErtraege daten={data} schluessel={kanon.schluessel} planEin={ein} planJahr={jahr} />

        {/* Brutto gegen Netto — der Umschalter IST das Lehrstück. */}
        <Karte>
          <Kicker>Brutto gegen Netto · alle Bereiche</Kicker>
          <p className="mb-3 mt-1 text-[12.5px] text-foreground/80">
            Umschalten dreht die Reihenfolge — und genau darin steckt der Punkt.
          </p>
          {/* Scrollzeile: „Kosten für die Stadt (netto)" ragte auf 375 px über
              den Bildschirmrand und ließ die ganze Seite horizontal wackeln. */}
          <div className="scrollbar-none -mx-1 mb-3 overflow-x-auto px-1">
            <Segmented value={ranking} onChange={setRanking} tone="primary" className="w-max" options={[
              { value: "brutto", label: "Ausgaben (brutto)" },
              { value: "netto", label: "Kosten für die Stadt (netto)" },
            ]} />
          </div>
          <div className="grid grid-cols-[minmax(110px,150px)_1fr_60px] items-center gap-x-2.5 gap-y-1.5 text-xs">
            {alle.slice(0, 6).map(({ r, netto: n, brutto: b }, i) => {
              const wert = ranking === "netto" ? n : b;
              const ich = r.bereich === z.bereich;
              return (
                <div key={r.bereich} className="contents">
                  <span className={cn("truncate", ich && "font-bold")}>{bereichKanon(r.bereich).kurz}</span>
                  <div className="h-3.5 rounded-[3px] bg-muted">
                    <div className="h-full rounded-[3px]" style={{
                      width: `${Math.max((wert / maxWert) * 100, 2)}%`,
                      background: `var(--hh-ein-${Math.min(i, 6)})`,
                    }} />
                  </div>
                  <span className={cn("text-right tabular-nums", ich && "font-bold")}>{deMio(wert)}</span>
                </div>
              );
            })}
          </div>
          {bruttoTop.r.bereich !== nachNetto[0].r.bereich && (
            <p className="mt-3 rounded-lg bg-muted/60 p-2.5 text-xs leading-relaxed text-foreground/90">
              In der Brutto-Sicht steht {bereichKanon(bruttoTop.r.bereich).name} mit
              {" "}{deMio(bruttoTop.brutto)}&#8239;Mio. an erster Stelle. Weil dort aber
              {" "}{deMio(mio(bruttoTop.r.ertraege))}&#8239;Mio. an Erstattungen und eigenen
              Einnahmen zurückfließen, bleibt {bereichKanon(nachNetto[0].r.bereich).name} unterm
              Strich am teuersten.
            </p>
          )}
          <Link href="/haushalt/bereiche"
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
              Redaktionelle Beschreibung nach dem Vorbericht des Haushaltsplans — keine amtliche
              Gliederung.
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
                const b = betrag(-(p.ergebnis as number));
                return (
                  <Link key={p.produkt_nr}
                    href={`/haushalt/produkte?nr=${encodeURIComponent(p.produkt_nr)}`}
                    className="flex items-baseline gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-accent">
                    <span className="min-w-0 flex-1 truncate text-[12.5px]">{p.produkt_name}</span>
                    <span className="flex-none whitespace-nowrap font-mono text-[11.5px] tabular-nums">
                      {b.wert}&#8239;<span className="text-muted-foreground">{b.einheit}</span>
                    </span>
                  </Link>
                );
              })}
            </div>
            <p className="mt-2.5 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              Die {produktZeilen.length} teuersten Aufgaben dieses Bereichs nach Zuschussbedarf,
              aus dem Teilhaushaltsplan {produktJahr}<Beleg q="teilhaushalt" />. Für das
              Haushaltsjahr {jahr} gibt es die Produktebene noch nicht — die Stadt
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
              {reihe.length >= 2
                ? `${reihe[0].jahr}–${reihe[reihe.length - 1].jahr} · ${reihe.length} Jahre`
                : "Noch keine Reihe"}
            </span>
          </div>
          {reihe.length >= 2 ? (() => {
            const werte = reihe.map((r) => -(mio(r.zeile.ergebnis) ?? 0));
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
              const prozent = von !== 0 ? Math.round(Math.abs(delta / von) * 100) : null;
              const monoton = groesse.every((w, i) => i === 0 || w >= groesse[i - 1])
                || groesse.every((w, i) => i === 0 || w <= groesse[i - 1]);
              return { delta, prozent, monoton, von, bis, wort: zuschuss ? "Zuschussbedarf" : "Überschuss" };
            })();
            return (
              <>
                {kopf && (
                  <div className="mt-2.5 flex flex-wrap items-end gap-x-4 gap-y-1">
                    <p className="font-display text-[34px] font-bold leading-none tracking-tight tabular-nums text-signal">
                      {kopf.delta > 0 ? "+" : kopf.delta < 0 ? "−" : ""}{deMio(Math.abs(kopf.delta))}
                    </p>
                    <p className="max-w-[54ch] text-[12.5px] leading-relaxed text-foreground/85">
                      Mio.&nbsp;€ gegenüber {reihe[0].jahr}: Der {kopf.wort} des Bereichs
                      {" "}{kopf.delta >= 0 ? "stieg" : "sank"} von {deMio(kopf.von)} auf
                      {" "}{deMio(kopf.bis)}&nbsp;Mio.&nbsp;€
                      {kopf.prozent != null && <> — {kopf.delta >= 0 ? "ein Plus" : "ein Minus"} von {kopf.prozent}&nbsp;%</>}
                      {kopf.monoton && groesse!.length > 2 && <>, in jedem Jahr in dieselbe Richtung</>}.
                    </p>
                  </div>
                )}
                <div className="mt-3 grid grid-cols-[auto_1fr_auto_auto] items-center gap-x-3 gap-y-1 text-xs tabular-nums">
                  {reihe.map(({ jahr: j, zeile }, i) => (
                    <div key={j} className="contents">
                      <span className="font-mono text-muted-foreground">{j}</span>
                      <div className="h-2.5 rounded-[3px] bg-muted">
                        <div className="h-full rounded-[3px]" style={{
                          width: `${(Math.abs(werte[i]) / maxN) * 100}%`,
                          background: "var(--hh-ein-0)",
                        }} />
                      </div>
                      <span className="text-right">
                        {werte[i] > 0 ? `−${deMio(werte[i])}` : `+${deMio(-werte[i])}`}&#8239;Mio. netto
                      </span>
                      <span className="text-right text-muted-foreground">
                        {deMio(mio(zeile.aufwendungen))}&#8239;Mio. Ausgaben
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
                  {reihe.length < jahre.length
                    ? <>Vor {reihe[0].jahr} führte der Plan den Bereich unter anderem Namen — die
                        Reihe beginnt dort, wo der Name belegt ist.</>
                    : <>Der Bereich heißt seit {reihe[0].jahr} unverändert; nur deshalb zeigen wir
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
              (p) => p.nr === 20 && p.plan_art && p.plan_art !== "ansatz");
            const letztesJahr = planIstJahre[planIstJahre.length - 1];
            const thhNr = abschluss.find((p) => p.thh_nr != null)?.thh_nr ?? kanon.thh;
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
                <Hantel zeilen={planIstZeilen} massstab="betrag" />
                {abweichend.length > 0 && (
                  <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
                    * In {[...new Set(abweichend.map((p) => p.jahr))].join(" und ")} vergleicht der
                    Abschluss nicht mit dem ursprünglichen Ansatz, sondern mit dem
                    fortgeschriebenen Plan
                    ({[...new Set(abweichend.map((p) => PLAN_ART_LABEL[p.plan_art as PlanArt]))].join(", ")}).
                  </p>
                )}
                {gruende.length > 0 && (
                  <div className="mt-3 flex flex-col gap-2.5 border-t border-border/60 pt-3">
                    <Kicker>Was der Abschluss {letztesJahr} zu diesem Bereich sagt</Kicker>
                    {gruende.map((g) => (
                      <div key={g.nr} className="flex flex-col gap-1">
                        <span className="text-[12.5px] font-semibold">
                          {g.bezeichnung}
                          <span className="ml-1.5 font-mono text-[11px] font-normal tabular-nums text-signal">
                            {(g.delta_mio ?? 0) > 0 ? "+" : ""}{deMio(g.delta_mio)}&#8239;Mio.
                          </span>
                        </span>
                        <Warum grund={g} kompakt />
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

      <ReiterTafel id="quelle" aktiv={aktiv} className="flex flex-col gap-4">
        <Karte>
          <Kicker>Diese Seite in einem Absatz</Kicker>
          <p className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Die Beträge oben sind <strong>Planwerte</strong> aus dem beschlossenen Haushaltsplan
            {" "}{jahr} — was der Rat vorgesehen hat, nicht, was am Ende wirklich geflossen ist.
            Was daraus wurde, steht erst im Jahresabschluss, und der liegt zwei Jahre zurück.
            Der Ergebnishaushalt zeigt außerdem nur die laufende Wirtschaft: Investitionen
            stehen im Finanzhaushalt und sind hier nicht enthalten.
          </p>
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Quelle dieser Seite:{" "}
            {quelle.url
              ? <a href={quelle.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{quelle.text}</a>
              : quelle.text} · Teilhaushalt {kanon.name} · ordentliche Erträge und Aufwendungen.
          </p>
        </Karte>
        <Datenstand />
        <Quellenverzeichnis schluessel={quellen} />
      </ReiterTafel>
    </div>
    </Quellenkontext>
  );
}

export default function BereichPage() {
  // useSearchParams braucht eine Suspense-Grenze (Export-Konvention).
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>}>
      <BereichInner />
    </Suspense>
  );
}
