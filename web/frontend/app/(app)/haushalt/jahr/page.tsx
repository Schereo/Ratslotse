"use client";

// /haushalt/jahr — „Wann der Haushalt entschieden wird" (Artboard H2-10).
//
// Die einzige Seite des Haushalts-Bereichs, die nicht aus Finanzdokumenten
// lebt, sondern aus den Ratsdaten: Beratungsfolge, Tagesordnung,
// Protokoll-Beschluss. Sie beantwortet die Frage, aus der Beteiligung
// überhaupt erst entstehen kann — wann ist es so weit, und wo darf ich hin?
//
// Was der Entwurf behauptete und die Daten nicht hergeben:
//
// - **„Der Haushalt 2026 wurde 2025 entschieden"** ist falsch, und zwar
//   ausgerechnet am Beispieljahr: Der Rat hat ihn am 9. Februar 2026
//   beschlossen, im Dezember 2025 zweimal vertagt. Über acht Jahrgänge fiel
//   die Entscheidung fünfmal erst im laufenden Haushaltsjahr. Der Satz steht
//   deshalb nirgends; die Streuung wird gerechnet und angezeigt.
// - **„Die Fachausschüsse sind der Ort, an dem sich am meisten bewegen
//   lässt"** — sie nehmen die Teilhaushalte zur Kenntnis. Abgestimmt wird im
//   Finanzausschuss und im Rat.
// - **„Die Kommunalaufsicht prüft, dann wird gezahlt"** suggeriert eine
//   Wirksamkeitsvoraussetzung, die es so nicht gibt: Die Haushaltssatzung ist
//   der Kommunalaufsicht anzuzeigen, genehmigungsbedürftig sind nur einzelne
//   Teile.
// - **Eine Vorschau auf die laufende Runde** („Sitzungstermine ansehen",
//   „Erinnerung einschalten") gibt es nicht: `council_scheduled_sessions`
//   führt keine Tagesordnung. Wir wissen nicht, welche der kommenden
//   Sitzungen die Haushaltssitzung wird, und raten es nicht.
//
// Schritt 1 (verwaltungsinterne Anmeldungen) und der Nachlauf haben in
// unserem Bestand keinen Datenpunkt. Sie stehen deshalb als Ablaufbeschreibung
// da — ohne Beleg-Chip, sichtbar abgesetzt von dem, was belegt ist.

import { useState } from "react";
import Link from "next/link";
import { ChevronRight, ExternalLink } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { sessionHref, decisionHref } from "@/lib/routes";
import {
  MONATE, WegDaten, WegRunde, WegStation, deDatum, deTagMonat, entscheidung, rhythmus,
} from "@/lib/haushalt-jahr";
import { ErgebnisAbzeichen, Jahreskreis, StationsZeile } from "@/components/haushalt/jahreskreis";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

const QUELLEN: QuellenSchluessel[] = ["ratsbeschluss"];

export default function HaushaltsjahrPage() {
  const { data, loading } = useFetch<WegDaten>("/council/haushalt/weg");
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);

  if (loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  const runden = data?.runden ?? [];
  if (!runden.length) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Zu den Haushaltsberatungen liegen uns noch keine Sitzungen vor.
      </div>
    );
  }

  const jahre = runden.map((r) => r.jahr);
  const jahr = gewaehlt != null && jahre.includes(gewaehlt) ? gewaehlt : jahre[jahre.length - 1];
  const runde = runden.find((r) => r.jahr === jahr)!;
  const rh = rhythmus(runden);
  const haeufigster = rh.entwurfMonate[0];

  return (
    <Quellenkontext schluessel={QUELLEN}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="font-semibold text-foreground">Das Haushaltsjahr</span>
        </div>

        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">
            Wann der Haushalt entschieden wird
          </h1>
          <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
            Alle Zahlen in diesem Bereich gehen auf eine einzige Entscheidung im Jahr zurück.
            Hier steht, wann sie fällt, welche Stationen sie vorher nimmt — und ab wann der
            Entwurf öffentlich einsehbar ist. Das ist der früheste Moment, in dem man mitreden
            kann.
          </p>
        </div>

        {/* Der Befund über alle Jahrgänge — gerechnet, nicht geschrieben. Ein
            fester Satz („der Haushalt wird im Dezember beschlossen") wäre für
            die Mehrheit der Jahrgänge falsch. */}
        <section className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {rh.jahrgaenge} Haushaltsjahre im Vergleich
          </p>
          <div className="mt-3 grid gap-3 @[34rem]:grid-cols-2">
            {haeufigster && (
              <Befund
                zahl={`${haeufigster.anzahl} von ${rh.jahrgaenge}`}
                text={`Haushaltsjahren wurde der Entwurf im ${MONATE[haeufigster.monat - 1]} eingebracht. Der Auftakt ist der verlässlichste Termin im ganzen Verfahren.`}
              />
            )}
            {rh.frueheste && rh.spaeteste && rh.frueheste.jahr !== rh.spaeteste.jahr && (
              <Befund
                zahl={`${deTagMonat(entscheidung(rh.frueheste)!.datum)} – ${deTagMonat(entscheidung(rh.spaeteste)!.datum)}`}
                text={`weit streut der Tag, an dem der Rat abschließend entschied — gemessen am Beginn des Haushaltsjahres am frühesten für ${rh.frueheste.jahr}, am spätesten für ${rh.spaeteste.jahr}. Ein fester Monat lässt sich daraus nicht machen.`}
              />
            )}
          </div>
          {rh.imJahrSelbst > 0 && (
            <p className="mt-3 border-t border-border/60 pt-3 text-[12.5px] leading-relaxed text-foreground/85">
              <strong>{rh.imJahrSelbst} von {rh.jahrgaenge} Haushalten</strong> wurden erst
              beschlossen, als das Haushaltsjahr bereits lief
              <Beleg q="ratsbeschluss" />. Bis dahin gilt die vorläufige Haushaltsführung: Die
              Stadt darf im Wesentlichen nur das ausgeben, wozu sie ohnehin verpflichtet ist.
            </p>
          )}
        </section>

        {/* Jahr-Umschalter. Acht Jahrgänge passen in keine Segment-Gruppe auf
            375 px — Pillen in einer scrollbaren Zeile statt gequetschter
            Tabs. */}
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1" role="group"
          aria-label="Haushaltsjahr wählen">
          {runden.map((r) => (
            <button
              key={r.jahr}
              type="button"
              onClick={() => setGewaehlt(r.jahr)}
              aria-pressed={r.jahr === jahr}
              className={cn(
                "flex-none rounded-full border px-3.5 py-1.5 font-mono text-[12px] font-medium tabular-nums transition-colors active:scale-[0.97]",
                r.jahr === jahr
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              {r.jahr}
            </button>
          ))}
        </div>

        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm @container">
          <div className="flex flex-col items-center gap-5 @[38rem]:flex-row @[38rem]:items-start @[38rem]:gap-7">
            <div className="flex w-full max-w-[320px] flex-none flex-col items-center">
              <Jahreskreis runde={runde} />
              <div className="mt-1 flex flex-wrap justify-center gap-x-4 gap-y-1.5 text-[11px] text-muted-foreground">
                <Legende art="offen">Entwurf eingebracht</Legende>
                <Legende art="voll">Beratung und Beschluss</Legende>
                {runde.fachausschuesse && <Legende art="spur">Fachausschüsse</Legende>}
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <Weg runde={runde} />
            </div>
          </div>
        </section>

        {/* Was wir nicht wissen — an derselben Stelle wie das, was wir wissen. */}
        <LottiErklaert
          titel="Und die nächste Runde?"
          text="Wann der Haushalt für das kommende Jahr beraten wird, können wir dir nicht sagen. Das Ratsinformationssystem veröffentlicht Sitzungstermine, aber erst kurz vorher auch die Tagesordnung dazu — bis dahin steht nirgends, welche der kommenden Sitzungen die Haushaltssitzung wird. Ein Datum zu raten, das dann nicht stimmt, wäre schlechter als keins."
          pose="confused"
        />

        <Nachlauf />

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

function Befund({ zahl, text }: { zahl: string; text: string }) {
  return (
    <div className="rounded-xl bg-muted/60 p-3">
      <p className="font-display text-[19px] font-bold leading-tight tabular-nums">{zahl}</p>
      <p className="mt-1 text-[12.5px] leading-relaxed text-foreground/85">{text}</p>
    </div>
  );
}

function Legende({ art, children }: {
  art: "offen" | "voll" | "spur";
  children: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn(
        art === "spur"
          ? "h-1 w-4 rounded-full bg-primary/40"
          : "h-2.5 w-2.5 rounded-full",
        art === "offen" && "border-2 border-primary bg-card",
        art === "voll" && "bg-primary",
      )} />
      {children}
    </span>
  );
}

function Weg({ runde }: { runde: WegRunde }) {
  const fach = runde.fachausschuesse;
  const letzte = entscheidung(runde);
  return (
    <div className="flex flex-col">
      {/* Vorlauf ohne Datenpunkt: Was in der Verwaltung passiert, bevor der
          Entwurf öffentlich wird, steht in keiner Sitzung — also auch bei uns
          nicht mit Datum. */}
      <Ablauf titel="Vorher, in der Verwaltung">
        Die Fachbereiche melden an, was sie im nächsten Jahr brauchen; die Kämmerei baut daraus
        einen Entwurf. Das passiert verwaltungsintern und taucht in keiner öffentlichen Sitzung
        auf — wir können dir dazu kein Datum nennen.
      </Ablauf>

      {runde.einbringung && (
        <StationsZeile station={runde.einbringung} rolle="Entwurf eingebracht">
          <p className="mt-1 text-[12.5px] leading-relaxed text-foreground/85">
            {deDatum(runde.einbringung.datum)} — ab hier sind der Entwurf und alle Zahlen
            öffentlich einsehbar.
          </p>
          <SitzungsLink station={runde.einbringung} />
        </StationsZeile>
      )}

      {fach && (
        <div className="flex gap-3 border-t border-border/70 py-3">
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Teilhaushalte in den Fachausschüssen
            </p>
            <p className="mt-1 text-[13.5px] font-bold leading-snug">
              {fach.gremien.length} Ausschüsse
              <span className="font-normal text-muted-foreground">
                {" · "}{fach.anzahl} {fach.anzahl === 1 ? "Termin" : "Termine"}
              </span>
            </p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-foreground/85">
              {fach.von === fach.bis
                ? deDatum(fach.von)
                : `${deDatum(fach.von)} bis ${deDatum(fach.bis)}`}
              {" — "}jeder Ausschuss bekommt „seinen" Teilhaushalt vorgestellt. Hier wird
              beraten und zur Kenntnis genommen; abgestimmt wird darüber im Finanzausschuss
              und im Rat.
            </p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
              {fach.gremien.join(" · ")}
            </p>
          </div>
        </div>
      )}

      {runde.stationen.map((s, i) => (
        <StationsZeile
          key={`${s.ksinr}-${i}`}
          station={s}
          rolle={s.gremium === "Rat"
            ? (s === letzte ? "Entscheidung im Rat" : "Im Rat aufgerufen")
            : "Vorberatung"}
        >
          <p className="mt-1 text-[12.5px] leading-relaxed text-foreground/85">
            {deDatum(s.datum)}
            {s.is_public === 1 && " · öffentliche Sitzung"}
          </p>
          {s.votum && <Votum votum={s.votum} />}
          <SitzungsLink station={s} />
        </StationsZeile>
      ))}

      <Ablauf titel="Danach">
        Die beschlossene Haushaltssatzung wird der Kommunalaufsicht angezeigt; genehmigen muss
        sie nur einzelne Teile, etwa den Gesamtbetrag der Kredite. Dann läuft das Haushaltsjahr,
        und erst der Jahresabschluss danach zeigt, was tatsächlich daraus geworden ist —{" "}
        <Link href="/haushalt/plan-ist" className="font-semibold text-primary">
          geplant gegen tatsächlich
        </Link>.
      </Ablauf>
    </div>
  );
}

/** Die Abstimmung über die Haushaltssatzung selbst. Die Sammelvorlage bündelt
 *  daneben Stiftungen und Eigenbetriebe — deren Voten stehen hier bewusst
 *  nicht, sonst nennte die Zeile eine Mehrheit für etwas anderes. */
function Votum({ votum }: { votum: NonNullable<WegStation["votum"]> }) {
  const teile = [votum.vote, votum.gegenstimmen != null ? `${votum.gegenstimmen} Gegenstimmen` : null,
    votum.enthaltungen ? `${votum.enthaltungen} Enthaltungen` : null].filter(Boolean);
  return (
    <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">
      Abstimmung über die Haushaltssatzung:{" "}
      <Link href={decisionHref(votum.id)} className="font-semibold text-primary">
        {votum.outcome ?? "Ergebnis im Protokoll"}
      </Link>
      {teile.length > 0 && ` · ${teile.join(", ")}`}
    </p>
  );
}

function SitzungsLink({ station }: { station: WegStation }) {
  return (
    <Link
      href={sessionHref(station.ksinr, station.top ? [station.top] : undefined)}
      className="mt-1.5 inline-flex items-center gap-1 text-[11.5px] font-semibold text-primary"
    >
      Sitzung ansehen
      {station.top && <span className="font-mono font-normal text-muted-foreground">{station.top}</span>}
      <ChevronRight className="h-3 w-3" />
    </Link>
  );
}

/** Ablaufbeschreibung ohne Datenpunkt — bewusst ohne Beleg-Chip und optisch
 *  abgesetzt, damit niemand sie für eine belegte Station hält. */
function Ablauf({ titel, children }: { titel: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 border-t border-dashed border-border py-3 first:border-t-0">
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {titel}
        </p>
        <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}

function Nachlauf() {
  return (
    <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
      <strong>Woher diese Stationen kommen.</strong> Aus der Beratungsfolge der Sammelvorlage
      „Haushalt &lt;Jahr&gt; – Beschluss" im Ratsinformationssystem, dem jeweiligen
      Tagesordnungspunkt und — wo ein Protokoll vorliegt — dem Beschluss über die
      Haushaltssatzung. Alle gezeigten Sitzungen sind öffentlich. Was die Verwaltung intern
      vorbereitet und was nach dem Beschluss mit der Kommunalaufsicht läuft, steht in keiner
      Sitzung; diese beiden Schritte sind darum als Ablauf beschrieben und nicht datiert.{" "}
      <a href="https://buergerinfo.oldenburg.de" target="_blank" rel="noopener noreferrer"
        className="inline-flex items-center gap-1 font-semibold text-primary">
        Bürgerinfo der Stadt
        <ExternalLink className="h-3 w-3" />
      </a>
    </p>
  );
}
