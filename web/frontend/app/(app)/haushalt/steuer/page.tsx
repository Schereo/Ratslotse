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
import { ChevronRight, Search } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltAuswahl, haushaltUrl, deMio } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import {
  STEUERARTEN, SPIELRAUM_LABEL, type SteuerArt, steuerartNachSlug,
} from "@/lib/haushalt-steuern";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert, LottiVergleich } from "@/components/haushalt/lotti-erklaert";
import { IstKurve } from "@/components/haushalt/ist-kurve";
import { SteuerPlanIst } from "@/components/haushalt/steuer-plan-ist";
import { HebesatzTreppe } from "@/components/haushalt/hebesatz-treppe";
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
  return STEUERARTEN.find((a) => norm(a.slug) === gesucht || norm(a.titel) === gesucht);
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
 *  Beschluss und zieht `jahr` nach — sichtbar, statt still. */
const HEBESATZ_ABGELEHNT = {
  jahr: 2026,
  steuer: "gewerbesteuer",
  satz: "Die Verwaltung schlug vor, die Hebesätze zu erhöhen. Der Rat lehnte ab.",
};

function SteuerInner() {
  const slug = useSearchParams().get("art") ?? "gewerbesteuer";
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER));
  const art = steuerartFinden(slug);

  const reihe = useMemo(() => {
    if (!data || !art?.datenArt) return [];
    return data.steuern
      .filter((s) => s.art === art.datenArt && s.betrag != null && s.betrag > 0)
      .map((s) => ({ jahr: s.jahr, betrag: s.betrag as number }))
      .sort((a, b) => a.jahr - b.jahr);
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
  const zuw = data.steuerkraft.filter((k) => k.zuweisungen != null);
  const istZuweisung = art.slug === "schluesselzuweisungen";
  const zuwReihe = istZuweisung
    ? zuw.map((k) => ({ jahr: k.jahr, betrag: k.zuweisungen as number }))
    : [];
  const anzeigeReihe = istZuweisung ? zuwReihe : reihe;
  const letzte = anzeigeReihe.at(-1);
  const gesamt = data.steuern.find((s) => s.jahr === letzte?.jahr && s.art === "insgesamt")?.betrag ?? null;
  const anteil = letzte && gesamt && !istZuweisung ? Math.round((letzte.betrag / gesamt) * 100) : null;
  const einwohner = data.einwohner?.einwohner ?? 0;

  // Plan neben Ist — nur diese Steuer, nur die Jahrgänge, die Tabelle 1103
  // führt (drei je Ausgabe). `datenArt` ist derselbe Schlüssel wie in der
  // Ist-Reihe; daran hängt im Ingest auch die Prüfung der Jahresbeschriftung.
  const planIst = (data.steuerplan?.zeilen ?? [])
    .filter((z) => art.datenArt && z.art === art.datenArt);

  // Die Hebesatz-Treppe dieser Steuer. Zwei Reihen nur bei der Grundsteuer
  // (B und A, dieselbe Einheit, derselbe Beschluss).
  const hebeAlle = data.hebesaetze?.zeilen ?? [];
  const hebeHaupt = art.hebesatzArten?.[0]
    ? hebeAlle.filter((z) => z.art === art.hebesatzArten![0]) : [];
  const hebeZweit = art.hebesatzArten?.[1]
    ? hebeAlle.filter((z) => z.art === art.hebesatzArten![1]) : [];

  // Das Jahr, für das gerade ein Haushalt gilt — das jüngste mit einem
  // beschlossenen Ansatz. Daran hängt, ob der Befund unten noch der aktuelle
  // ist; `ansatz_jahre` führt die Finanzplanungsjahre bewusst nicht mit.
  const aktuellerHaushalt = data.ansatz_jahre?.at(-1) ?? null;

  // Der Hebesatz, der im Jahr des Aufkommens GALT.
  //
  // Tabelle 1105 führt nur die Änderungsjahre — ein Satz gilt bis zur nächsten
  // Änderung. Gesucht ist deshalb die letzte Stufe mit `jahr <= letzte.jahr`
  // und nicht etwa die jüngste Zeile der Reihe: Läge das Aufkommen ein Jahr
  // hinter einer frischen Erhöhung zurück (der Normalfall, das Ist kommt
  // später als der Beschluss), teilte man sonst durch einen Satz, der für
  // dieses Geld nie gegolten hat.
  //
  // Bis 19.08.2026 stand hier `art.hebesatz` — eine Zahl im Quelltext
  // (`439` für die Gewerbesteuer). Sie stimmte zufällig, weil der Rat den Satz
  // seit 2015 nicht angefasst hat; der nächste Beschluss hätte sie still
  // falsch gemacht, während die echte Reihe schon danebenlag.
  const hebesatzGalt = letzte
    ? hebeHaupt.filter((z) => z.jahr <= letzte.jahr).at(-1) ?? null
    : null;
  const punktSatz = hebesatzGalt?.hebesatz ?? null;

  // Ein Hebesatzpunkt, überschlagen aus dem Ist — bewusst als Überschlag
  // benannt. Nur wo Betrag und Hebesatz dieselbe Steuer meinen: Bei der
  // Grundsteuer tun sie das nicht (siehe `punktUnmoeglich`).
  const proPunkt = punktSatz && letzte && !art.punktUnmoeglich
    ? letzte.betrag / punktSatz : null;

  // Das Aufkommen als `{jahr: euro}` — der Pflicht-Kontext neben jedem
  // Hebesatz-Sprung. Ohne ihn liest sich „+21 %" als „alle zahlen 21 % mehr",
  // und das war 2025 nachweislich falsch.
  const aufkommen: Record<number, number> = {};
  for (const s of reihe) aufkommen[s.jahr] = s.betrag;

  // Die Quellen dieser Seite in Lese-Reihenfolge — daraus zählt der Provider
  // die Fußnoten-Nummern.
  const quellen: QuellenSchluessel[] = istZuweisung
    ? ["steuerkraft", "plan"]
    : ["steuern", ...(planIst.length ? (["steuerplan"] as const) : []),
       "hebesaetze"];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <Link href="/haushalt/einnahmen" className="hover:text-foreground">Woher das Geld kommt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">{art.titel}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[26px]">{art.titel}</h1>
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
              {istZuweisung ? `Erhalten ${letzte.jahr}` : `Eingenommen ${letzte.jahr}`}
            </p>
            <p className="mt-1.5 font-display text-[27px] font-bold leading-none tracking-tight tabular-nums text-[color:var(--hh-ein-0)]">
              {deMio(letzte.betrag / 1e6)}
              <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.</span>
              <Beleg q={istZuweisung ? "steuerkraft" : "steuern"} />
            </p>
            {anteil != null && (
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
                {anteil}&nbsp;% aller Steuereinnahmen ({deMio(gesamt! / 1e6)}&#8239;Mio.)
              </p>
            )}
          </div>
        )}
      </div>

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
            <div key={st.titel} className={cn(
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
              <p className="mt-2 text-[13px] font-bold leading-snug">{st.titel}</p>
              <p className="mt-1 text-xs leading-relaxed text-foreground/80">
                <GlossaryText text={st.text} />
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
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{art.beispiel.hinweis}</p>
          </div>
        )}
      </div>

      <LottiErklaert titel={art.lotti.titel} text={art.lotti.text} />

      {anzeigeReihe.length >= 2 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <IstKurve reihe={anzeigeReihe} />
          <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
            Quelle {istZuweisung ? "Schlüsselzuweisungen" : "Steuereinnahmen"}: siehe Verzeichnis unten
            <Beleg q={istZuweisung ? "steuerkraft" : "steuern"} />
          </p>
        </div>
      )}

      {/* „Geplant und geworden" steht DIREKT unter der Ist-Kurve: Die Kurve
          zeigt, was hereinkam, dieser Block, was man erwartet hatte. Weiter
          unten, hinter dem Hebesatz, verlöre er seinen Bezug. */}
      {planIst.length > 0 && (
        <SteuerPlanIst
          zeilen={planIst}
          abgrenzung={data.steuerplan?.abgrenzung ?? ""}
          beleg={<Beleg q="steuerplan" />}
        />
      )}

      {letzte && einwohner > 0 && (
        /* „vom Land" stand hier bis 17.08. und war zu weit: Der Betrag ist
           die Schlüsselzuweisung, also zwei von drei Komponenten des
           Ausgleichs — die dritte (übertragener Wirkungskreis) fehlt darin
           und kommt ebenfalls vom Land. Der Satz benennt jetzt, was er
           teilt; die vollständige Zahl steht auf /haushalt/einnahmen. */
        <LottiVergleich
          betragMio={letzte.betrag / 1e6}
          einwohner={einwohner}
          was={istZuweisung ? "an Schlüsselzuweisungen vom Land" : `aus der ${art.titel}`}
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
          <HebesatzTreppe
            reihe={hebeHaupt}
            zweitreihe={hebeZweit}
            zweitLabel={art.hebesatzArten?.[1]}
            titel={art.titel}
            aufkommen={aufkommen}
            /* Bei der Grundsteuer heißt das Aufkommen NICHT wie der Hebesatz
               daneben: Der offene Datensatz führt A und B in einer Spalte, die
               Sätze gelten getrennt. Dieselbe Grenze, die auch den Überschlag
               „ein Punkt mehr" verbietet (`punktUnmoeglich`). */
            aufkommenLabel={art.slug === "grundsteuer"
              ? "Grundsteuer A und B zusammen" : `${art.titel}`}
            bemessungNeu={data.hebesaetze?.bemessung_neu ?? {}}
            abgrenzung={data.hebesaetze?.abgrenzung ?? ""}
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
            beleg={<Beleg q="hebesaetze" />}
            aufkommenBeleg={<Beleg q="steuern" />}
          />
        ) : (
          /* Der Rückfall, wenn die Reihe fehlt — und zwar OHNE Zahl.
             Bis 19.08.2026 stand hier ein Kasten „2025 · Rat — Hebesatz 439 %"
             aus `art.hebesatz`, also aus dem Quelltext. Das war die schlechteste
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

        <div className="grid gap-3 lg:grid-cols-[1fr_310px]">
          {art.slug === HEBESATZ_ABGELEHNT.steuer
            && aktuellerHaushalt === HEBESATZ_ABGELEHNT.jahr && (
            <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <p className="font-mono text-[10px] uppercase tracking-wide text-primary">
                  Haushalt {HEBESATZ_ABGELEHNT.jahr} · Rat
                </p>
                <span className="rounded-full border border-[#fecaca] bg-[#fef2f2] px-2 py-0.5 text-[10.5px] font-semibold text-[#b91c1c]">
                  Abgelehnt
                </span>
              </div>
              <p className="mt-1.5 text-[13px] font-semibold leading-snug">
                {HEBESATZ_ABGELEHNT.satz}
              </p>
              {/* Der Verweis auf die Treppe nur, wo eine steht: Ohne
                  eingelesene Reihe zeigt der Block darüber einen einzelnen
                  Kasten, und „die Treppe darüber" zeigte ins Leere. */}
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                Genau hier entscheidet Kommunalpolitik über Einnahmen
                {hebeHaupt.length >= 2
                  ? ` — die Treppe darüber hätte ${HEBESATZ_ABGELEHNT.jahr} eine Stufe mehr bekommen.`
                  : "."}
              </p>
            </div>
          )}

          {art.punktUnmoeglich && (
            <div className="rounded-2xl border border-dashed border-border bg-card p-4">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Was brächte ein Punkt mehr?
              </p>
              {/* Kein Link ins Labor: Dort fehlt derselbe Regler aus demselben
                  Grund — ein Verweis verspräche, was die nächste Seite auch
                  nicht kann. */}
              <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/80">
                {art.punktUnmoeglich}
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
                Überschlagen: {deMio(letzte!.betrag / 1e6)}&#8239;Mio. (Ist {letzte!.jahr})
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
                so führt der offene Datensatz die Gewerbesteuer.<Beleg q="steuern" /> Ob das Land
                über den Finanzausgleich zusätzlich gegenrechnet, hängt an seiner Formel; wie
                stark, geben die Zahlen nicht her.
              </p>
              {/* „und Grundstückswerte" stand hier, solange die Karte auch bei
                  der Grundsteuer erschien — dort tut sie es nicht mehr. */}
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                Unsere Rechnung, keine amtliche Kennzahl: Sie unterstellt, dass die Gewinne der
                Unternehmen gleich bleiben — steigt der Hebesatz, kann sich auch daran etwas
                ändern.
              </p>
              <Link href="/haushalt/labor"
                className="mt-2.5 inline-flex text-[12px] font-semibold text-primary">
                Im Labor ausprobieren →
              </Link>
            </div>
          )}
        </div>
        </>
      )}

      <div className="rounded-2xl border border-dashed border-border bg-card p-4">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Dazu hat der Rat entschieden
        </p>
        <p className="mt-2 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
          Die automatische Verknüpfung von Beschlüssen mit Einnahmearten bauen wir noch.
          Bis dahin findet die Suche, was der Rat dazu entschieden hat.
        </p>
        <Link href={`/council?q=${encodeURIComponent(art.titel)}`}
          className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
          <Search className="h-3.5 w-3.5" /> Beschlüsse zu „{art.titel}“ suchen
        </Link>
      </div>

      <div className="flex flex-wrap gap-2">
        {STEUERARTEN.filter((a) => a.slug !== art.slug).map((a) => (
          <Link key={a.slug} href={`/haushalt/steuer?art=${a.slug}`}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-[11.5px] hover:border-primary/40">
            {a.titel}
          </Link>
        ))}
      </div>

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
// `ansatz_jahre` ist die kleinste Auskunft darüber, für welches Jahr gerade
// ein Haushalt gilt (eine Liste von Zahlen). Die Seite braucht sie, damit der
// Befund zum abgelehnten Hebesatz-Vorschlag nicht überlebt, was er beschreibt.
const FELDER = ["steuern", "steuerkraft", "steuerplan", "hebesaetze", "einwohner",
  "ansatz_jahre"] as const;

export default function SteuerPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Steckbrief wird geladen …</div>}>
      <SteuerInner />
    </Suspense>
  );
}
