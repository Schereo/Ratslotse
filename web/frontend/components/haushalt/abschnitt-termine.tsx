"use client";

// „Wann der Haushalt entschieden wird" — der ERSTE Abschnitt von
// /haushalt/mitreden.
//
// Bis zum 21.08.2026 war das die eigene Seite /haushalt/jahr. Sie ist mit
// „Der Streit ums Geld" und dem Haushalts-Labor zusammengelegt worden: Alle
// drei beantworten dieselbe Frage („Wie rede ich mit?"), und der Bereich war
// auf neunzehn Schritte gewachsen (Tim, 21.08.: „man wird erschlagen vor
// Inhalten"). Der Rahmen — Quellenkontext, Verzeichnis, Weiter-Karte — liegt
// jetzt bei der Seite; hier steht nur noch der Inhalt.

// /haushalt/jahr — „Wann der Haushalt entschieden wird" (H3-06/H4-14,
// davor H2-10).
//
// Die einzige Seite des Haushalts-Bereichs, die nicht aus Finanzdokumenten
// lebt, sondern aus den Ratsdaten: Beratungsfolge, Tagesordnung,
// Protokoll-Beschluss. Sie beantwortet die Frage, aus der Beteiligung
// überhaupt erst entstehen kann — wann ist es so weit, und wo darf ich hin?
//
// Das tragende Bild ist seit H3-06 der liegende <Zeitstrahl> aus dem
// Grafik-Baukasten (er ersetzt den Jahreskreis aus H2-10): Ein Kreis hat
// kein Heute — der Strahl schon, und die Sicht über mehr als zwei Jahre
// erklärt nebenbei, warum es gleichzeitig um drei Haushalte geht (einer
// läuft, einer wird abgerechnet, einer wird verhandelt). Jede Station trägt
// ihre GEMESSENE Zählangabe („in 7 von 8 Jahrgängen im Oktober") — der
// Strahl behauptet nichts, was nicht aus den Jahrgängen gezählt ist.
//
// Was der Entwurf behauptete und die Daten nicht hergeben:
//
// - **„Der Haushalt 2026 wurde 2025 entschieden"** ist falsch, und zwar
//   ausgerechnet am Beispieljahr: Der Rat hat ihn am 9. Februar 2026
//   beschlossen, im Dezember 2025 zweimal vertagt. Die Streuung wird
//   gerechnet und angezeigt, kein fester Satz geschrieben.
// - **„Die Fachausschüsse sind der Ort, an dem sich am meisten bewegen
//   lässt"** — sie nehmen die Teilhaushalte zur Kenntnis. Abgestimmt wird im
//   Finanzausschuss und im Rat.
// - **„Die Kommunalaufsicht prüft, dann wird gezahlt"** suggeriert eine
//   Wirksamkeitsvoraussetzung, die es so nicht gibt: Die Haushaltssatzung ist
//   der Kommunalaufsicht anzuzeigen, genehmigungsbedürftig sind nur einzelne
//   Teile.
//
// TODO(Datenpfad): Die Station „Genehmigung & Bekanntmachung" aus H3-06
// bekommt der Strahl bewusst NICHT — weder die Anzeige bei der
// Kommunalaufsicht noch die Bekanntmachung stehen im Ratsinformationssystem
// (keine Sitzung, kein Dokument im Bestand). Erst wenn dafür eine Quelle
// erschlossen ist (etwa das Amtsblatt), bekommt sie eine gemessene Lage;
// bis dahin beschreibt der „Danach"-Absatz den Schritt ohne Datum, statt
// eine Lage zu raten.
//
// KEINE TERMIN-KARTE MEHR (Tim, 22.08.2026: „dass hier immer die nächste
// Ratssitzung als mögliche Haushaltsdebatte angekündigt wird, das sollten
// wir nicht so darstellen"). Die Karte zeigte den nächsten Termin von
// Finanzausschuss oder Rat aus dem Ratskalender — mit ehrlichem
// Kleingedruckten, aber die Schlagzeile („Rat — Mo, 31. August, 18:00 Uhr")
// versprach im Haushalts-Kontext trotzdem eine Haushaltssitzung. Der
// Ratskalender kennt keine Tagesordnungen; ob eine Sitzung den Haushalt
// aufruft, wissen wir erst kurz vorher. Statt der Sitzung steht jetzt die
// Auskunft, die wir belegen können: der GEMESSENE Einbringungs-Monat, und
// warum wir keinen konkreten Termin ankündigen. Derselbe Grund nahm auch
// den Kalender-Pin vom Zeitstrahl: Er hängte dieselbe beliebige Sitzung an
// den Haushalts-Weg.
//
// Der Jahresabschluss steht auf dem Strahl mit „≈": Seine Lage ist aus den
// festgestellten Abschlüssen früherer Jahrgänge gemessen (Ratsvorgänge aus
// `/council/haushalt/dokumente`), kein Termin. Ohne diese Messgrundlage
// entfällt die Station — geraten wird nicht.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, ExternalLink } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { sessionHref, decisionHref } from "@/lib/routes";
import {
  MONATE, WegDaten, WegRunde, WegStation, deDatum, deTagMonat,
  entscheidung, jahresabschlussMass, monateZwischen,
  rhythmus, strahlRunde, versatzWort,
} from "@/lib/haushalt-jahr";
import type { DokumenteAntwort } from "@/lib/haushalt-dokumente";
import { Zeitstrahl, ZeitstrahlStation } from "@/components/grafik/zeitstrahl";
import { StationsZeile } from "@/components/haushalt/weg-stationen";
import { Beleg } from "@/components/haushalt/quelle";
import { cn } from "@/lib/utils";



export function TermineAbschnitt({ onBestand }: {
  /** Meldet den nächsten künftigen Termin der Beratungsfolge nach oben — die
   *  Seitenbühne im Kopf rechnet ihre Tage aus derselben Antwort wie der
   *  Zeitstrahl (H5-02). `null`, wenn keiner im Kalender steht: Die Bühne
   *  erfindet dann keinen. */
  onBestand?: (b: {
    naechster: { datum: string; gremium: string } | null;
    /** Die vier Phasen des jüngsten Haushaltswegs, für den Phasen-Strahl der
     *  Bühne (Tim, 26.08.: „der Zeitstrahl sollte wenigstens anzeigen, wo wir
     *  uns befinden, welche Phasen es gerade gibt"). Aus derselben Runde, die
     *  der große Zeitstrahl unten zeichnet. */
    phasen: { titel: string; datum: string | null; erledigt: boolean; aktuell: boolean }[];
    jahr: number;
  }) => void;
} = {}) {
  const { data, loading } = useFetch<WegDaten>("/council/haushalt/weg");
  const { data: dokumente } = useFetch<DokumenteAntwort>("/council/haushalt/dokumente");
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  // Einmal gemerkt statt je Render neu: `heute` ist Anker des Strahls.
  const heute = useMemo(() => new Date(), []);

  useEffect(() => {
    if (!onBestand || loading) return;
    if (!data?.runden.length) { onBestand({ naechster: null, phasen: [], jahr: 0 }); return; }
    const tag = `${heute.getFullYear()}-${String(heute.getMonth() + 1).padStart(2, "0")}-${String(heute.getDate()).padStart(2, "0")}`;
    const kommend = data.runden
      .flatMap((r) => r.stationen)
      .filter((st) => st.datum >= tag)
      .sort((a, b) => a.datum.localeCompare(b.datum));

    // Die Phasen der jüngsten Runde — dieselben vier Stationen, die der
    // Zeitstrahl unten ausführlich zeichnet. „erledigt" heißt: liegt hinter
    // uns; „aktuell" ist die erste, die es nicht ist. Das Haushaltsjahr gilt
    // als erreicht, sobald der Rat beschlossen hat.
    const r = data.runden[data.runden.length - 1];
    const ratsbeschluss = [...r.stationen]
      .filter((st) => st.rolle === "Entscheidung" && st.ergebnis
        && !/zurückgestellt|abgesetzt|vertagt/i.test(st.ergebnis))
      .sort((a, b) => a.datum.localeCompare(b.datum))
      .at(-1) ?? null;
    const roh = [
      { titel: "Einbringung", datum: r.einbringung?.datum ?? null },
      { titel: r.fachausschuesse ? `Beratung, ${r.fachausschuesse.anzahl}\u00d7` : "Beratung",
        datum: r.fachausschuesse?.bis ?? null },
      { titel: "Beschluss im Rat", datum: ratsbeschluss?.datum ?? null },
      { titel: `Haushaltsjahr ${r.jahr}`, datum: `${r.jahr}-01-01` },
    ];
    const erledigt = roh.map((ph) => ph.datum != null && ph.datum <= tag);
    const laufend = erledigt.findIndex((e) => !e);
    const phasen = roh.map((ph, i) => ({
      ...ph,
      erledigt: erledigt[i],
      // Läuft alles schon: die letzte Phase (das Haushaltsjahr) ist die,
      // in der wir gerade stecken.
      aktuell: laufend === -1 ? i === roh.length - 1 : i === laufend,
    }));
    onBestand({
      naechster: kommend[0]
        ? { datum: kommend[0].datum, gremium: kommend[0].gremium } : null,
      phasen,
      jahr: r.jahr,
    });
  }, [onBestand, loading, data, heute]);

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
  const abschluss = jahresabschlussMass(dokumente?.dokumente?.jahresabschluss);

  // ---- Die Stationen des Strahls: Lagen aus der laufenden Runde, --------
  // ---- Zählangaben aus allen Jahrgängen. --------------------------------
  const anker = strahlRunde(runden, heute)!;
  const stationen: ZeitstrahlStation[] = [];

  if (anker.einbringung && haeufigster) {
    stationen.push({
      label: "Einbringung",
      von: anker.einbringung.datum,
      offen: true,
      gemessen: `in ${haeufigster.anzahl} von ${rh.jahrgaenge} Jahrgängen im ${MONATE[haeufigster.monat - 1]}`,
      href: sessionHref(anker.einbringung.ksinr, anker.einbringung.top ? [anker.einbringung.top] : undefined),
    });
  }
  if (anker.fachausschuesse) {
    const fach = anker.fachausschuesse;
    stationen.push({
      label: "Ausschüsse beraten",
      von: fach.von,
      bis: fach.bis,
      gemessen: `${fach.anzahl} Termine in ${fach.gremien.length} Ausschüssen — hier entstehen die Änderungslisten`,
      href: "/haushalt/streit",
    });
  }
  const ankerEntscheidung = entscheidung(anker);
  if (ankerEntscheidung && ankerEntscheidung.gremium === "Rat") {
    stationen.push({
      label: "Ratsbeschluss",
      von: ankerEntscheidung.datum,
      gemessen: `${rh.imJahrSelbst} von ${rh.jahrgaenge} Jahrgängen erst beschlossen, als das Jahr schon lief`,
      href: sessionHref(ankerEntscheidung.ksinr, ankerEntscheidung.top ? [ankerEntscheidung.top] : undefined),
    });
  }
  stationen.push({
    label: `Haushaltsjahr ${anker.jahr}`,
    von: `${anker.jahr}-01-01`,
    bis: `${anker.jahr}-12-31`,
    gemessen: "das Geld wird ausgegeben — das Haushaltsjahr ist das Kalenderjahr",
  });
  let abschlussVon: string | null = null;
  if (abschluss) {
    const jahrVersatz = Math.floor((abschluss.medianMonate - 1) / 12);
    const monat = ((abschluss.medianMonate - 1) % 12) + 1;
    abschlussVon = `${anker.jahr + jahrVersatz}-${String(monat).padStart(2, "0")}-15`;
    stationen.push({
      label: "Jahresabschluss",
      von: abschlussVon,
      ungefaehr: true,
      gemessen: `in ${abschluss.mitVersatz} von ${abschluss.gezaehlt} Jahrgängen ${versatzWort(abschluss.versatz)} vom Rat festgestellt`,
      href: "/haushalt/plan-ist",
    });
  }

  const lebtMonate = anker.einbringung && abschlussVon
    ? monateZwischen(anker.einbringung.datum, abschlussVon)
    : null;

  return (
      <div className="flex flex-col gap-4">
        <div>
          <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
            Wann der Haushalt entschieden wird
          </h2>
          <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
            {lebtMonate
              ? `Vom ersten öffentlichen Entwurf bis zum festgestellten Jahresabschluss vergehen im vorhandenen Datenbestand durchschnittlich rund ${lebtMonate} Monate. `
              : "Die Darstellung reicht vom ersten öffentlichen Entwurf bis zum festgestellten Jahresabschluss. "}
            Die interne Vorbereitung der Verwaltung erscheint nicht im Ratsinformationssystem
            und hat deshalb keinen eigenen Termin in dieser Zeitleiste.
          </p>
        </div>

        {/* Das tragende Bild: der Strahl der laufenden Runde. Er zeigt
            nebenbei, warum gerade drei Haushalte gleichzeitig Thema sind. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Der Weg des Haushalts {anker.jahr}
            </h2>
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {rh.jahrgaenge} Jahrgänge · RIS-Sitzungsdaten
              <Beleg q="ratsbeschluss" />
            </span>
          </div>
          <Zeitstrahl className="mt-3" stationen={stationen} heute={heute} />
        </section>

        {/* Die Frage dieser Karte ist „wann geht es wieder um den Haushalt?" —
            und die ehrliche Antwort darauf ist ein gemessener Monat, kein
            Termin (Begründung im Kopf dieser Datei). */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Und die nächste Runde?
          </h2>
          <p className="mt-1.5 max-w-[70ch] text-[13px] leading-relaxed text-foreground/90">
            {haeufigster && (
              <>
                Erfahrungsgemäß beginnt sie im{" "}
                <strong>{MONATE[haeufigster.monat - 1]}</strong>: In {haeufigster.anzahl} von{" "}
                {rh.jahrgaenge} Jahrgängen wurde der nächste Entwurf in diesem Monat
                eingebracht — dann beginnt dieser Strahl von vorn.{" "}
              </>
            )}
            Welche Sitzung den Haushalt behandelt, steht erst mit der veröffentlichten
            Tagesordnung fest. Solange sie nicht vorliegt, nennen wir keinen konkreten Termin.
          </p>
          <div className="mt-3 border-t border-dashed border-border pt-2.5">
            <Link href="/council?tab=sessions" className="text-[11.5px] font-semibold text-primary">
              Alle kommenden Sitzungen im Ratskalender
            </Link>
          </div>
        </section>

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
            <p className="mt-3 max-w-[76ch] border-t border-border/60 pt-3 text-[12.5px] leading-relaxed text-foreground/85">
              <strong>{rh.imJahrSelbst} von {rh.jahrgaenge} Haushalten</strong> wurden erst
              beschlossen, als das Haushaltsjahr bereits lief
              <Beleg q="ratsbeschluss" />. Bis dahin gilt die vorläufige Haushaltsführung: Die
              Stadt darf im Wesentlichen nur das ausgeben, wozu sie ohnehin verpflichtet ist.
            </p>
          )}
        </section>

        {/* Jahr-Umschalter für die Stationsliste. Acht Jahrgänge passen in
            keine Segment-Gruppe auf 375 px — Pillen in einer scrollbaren
            Zeile statt gequetschter Tabs (H4-A: nie ein Dropdown). */}
        <div className="scrollbar-none -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [@media(min-width:744px)]:flex-wrap"
          role="group" aria-label="Haushaltsjahr wählen">
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

        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Die Stationen des Haushalts {runde.jahr}
          </h2>
          <div className="mt-2">
            <Weg runde={runde} />
          </div>
        </section>

        <Nachlauf />

      </div>
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
            <p className="mt-1 max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/85">
              {fach.von === fach.bis
                ? deDatum(fach.von)
                : `${deDatum(fach.von)} bis ${deDatum(fach.bis)}`}
              {" — "}jeder Ausschuss befasst sich mit den Teilhaushalten seines Fachgebiets.
              Die abschließenden Entscheidungen über den Gesamthaushalt treffen
              Finanzausschuss und Rat.
            </p>
            {/* Die zehn Ausschussnamen als Aufzählung statt als Wortkette:
                Aneinandergereiht liefen sie über 1.102 px in einer Zeile, und
                wo ein Name endet und der nächste beginnt, sagte nur ein
                Mittelpunkt. */}
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {fach.gremien.map((g) => (
                <li key={g}
                  className="rounded-full border border-border px-2.5 py-0.5 text-[11px] leading-relaxed text-muted-foreground">
                  {g}
                </li>
              ))}
            </ul>
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
        Die beschlossene Haushaltssatzung wird der Kommunalaufsicht angezeigt;
        genehmigungsbedürftig sind nur einzelne Teile, etwa der Gesamtbetrag der Kredite.
        Die Satzung als Ganze wartet also auf keine Freigabe. Dann läuft das Haushaltsjahr,
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
  const teile = [votum.vote, votum.no_votes != null ? `${votum.no_votes} Gegenstimmen` : null,
    votum.abstentions ? `${votum.abstentions} Enthaltungen` : null].filter(Boolean);
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
        <p className="mt-1 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
          {children}
        </p>
      </div>
    </div>
  );
}

/** Woher die Stationen stammen.
 *
 *  Bis 17.08. stand das als nackter grauer Absatz zwischen der letzten Karte
 *  und der Schritt-Leiste — die einzige Stelle der Seite ohne Karte, und
 *  ausgerechnet die Herkunftsangabe. Jetzt trägt sie dieselbe Form, die
 *  /haushalt/konzern, /haushalt/schulden und der Beteiligungs-Steckbrief für
 *  Fundstellen führen: Kicker in Versal-Mono über gestrichelter Linie, Text
 *  in Lesebreite. Der Inhalt ist unverändert. */
function Nachlauf() {
  return (
    <section className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Stationen kommen
      </p>
      {/* Dieser Absatz IST der Inhalt der Karte — hier steht neben ihm nichts,
          was die Fläche füllt. Deshalb Spalten statt bloßem Deckel
          (Designsprache §4): `86ch` allein hießen 108 Zeichen je Zeile, die
          längste Zeile des Bereichs; in zwei Spalten sind es rund 79. */}
      <p className="mt-1.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground @3xl:max-w-none @3xl:columns-2 @3xl:gap-x-8 @6xl:columns-3">
        Aus der Beratungsfolge der Sammelvorlage „Haushalt &lt;Jahr&gt; – Beschluss" im
        Ratsinformationssystem, dem jeweiligen Tagesordnungspunkt und — wo ein Protokoll
        vorliegt — dem Beschluss über die Haushaltssatzung. Alle gezeigten Sitzungen sind
        öffentlich. Was die Verwaltung intern vorbereitet und was nach dem Beschluss mit der
        Kommunalaufsicht läuft, steht in keiner Sitzung; diese beiden Schritte sind darum als
        Ablauf beschrieben und nicht datiert.
      </p>
      {/* Die Trennlinie gehört um den ganzen Block, nicht um den Link: Als
          `border-t` am `<a>` selbst reichte sie nur so weit wie sein Text und
          sah aus wie ein abgeschnittener Strich. */}
      <div className="mt-2.5 border-t border-dashed border-border pt-2.5">
        <a href="https://buergerinfo.oldenburg.de" target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-primary">
          Bürgerinfo der Stadt
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </section>
  );
}
