"use client";

// /haushalt/beteiligungen — „Was machen die eigentlich?" (H3-02 / H4-11)
//
// Schritt 12: Die Stadt ist mehr als das Rathaus. Der Gesamtabschluss
// (/haushalt/konzern, Schritt 11) sagt, wie viel Klinikum, Busse und Bäder
// bewegen — hier steht, WER das ist und was jede*r Einzelne tut. Die
// Arbeitsteilung der beiden Seiten ist Absicht und steht als Verweis-Karte
// am Seitenende (H4-10-Review: „hier das Ganze, dort die Gesellschaften
// einzeln").
//
// DIE FORM SAGT, WIE NAH EINE EINHEIT DER STADT STEHT: Konzernkarte und
// Karten tragen die Formen-Sprache aus `components/haushalt/konzernkarte.tsx`
// (■ Eigenbetrieb · ◆ AöR · ● GmbH/Co. KG), hergeleitet aus der Gliederung
// des Berichts selbst — deterministisch, kein Force-Layout (GB-15).
//
// BREAKPOINTS (H4-11): Ab 744 px steht die Konzernkarte voll im Seitenfluss,
// darunter die Gesellschafts-Karten im 2er-Raster. Mobil wandert die
// Konzernkarte hinter den Auslöser „Wer gehört zu wem?" (weglassen heißt
// hinter einen Auslöser, nie ersatzlos), gefiltert wird über Formen-Chips,
// die Karten stapeln einspaltig. Die Sparkline behält ihre
// Endpunkt-Beschriftung auf jedem Gerät.
//
// KEINE BEWERTUNGSFARBEN, wie im ganzen Bereich (components/haushalt/
// hantel.tsx): Kein Rot für ein negatives Jahresergebnis, keine Pfeile. Ein
// Verkehrsbetrieb, der Verlust macht, erfüllt seinen Auftrag — deshalb ist
// die EINORDNUNG Pflichtteil jeder Karte (GB-00 <Einordnung>): „−27,1 Mio."
// steht nie allein.
//
// DETAILANSICHT ÜBER QUERY-PARAMETER (`?g=vwg`), nicht über ein
// Route-Segment: Der mobile Build ist ein statischer Export (Capacitor), und
// dynamische Segmente brauchen dort eine vorab bekannte Pfadliste. Dieselbe
// Entscheidung wie bei /haushalt/produkte (`?nr=`) und /haushalt/bereich.
//
// DER STECKBRIEF SELBST steht in `components/haushalt/beteiligung-steckbrief.tsx`
// — er ist kein Textausguss mehr, sondern Zahlenkopf, Anteilsstreifen und
// Personenliste, und trägt seine Begründungen im eigenen Kopfkommentar. Diese
// Datei bleibt die Liste: Karten, Konzernkarte, Filter.
//
// KEINE BEWERTUNGSFARBEN, wie im ganzen Bereich
// (components/grafik/hantel.tsx): Kein Rot für ein negatives
// Jahresergebnis, keine Pfeile, kein Ampel-Punkt. Ein Verkehrsbetrieb, der
// Verlust macht, erfüllt seinen Auftrag — die Stadt hält ihn dafür. Wer das
// rot einfärbt, behauptet ein Versagen und meint eine Aufgabe.
//
// UND KEINE SELBSTVERGEWISSERUNG (DESIGNSPRACHE.md § 7): Die Seite zeigt
// Fundstellen, nicht unsere Rechenproben. Eine Ausnahme, begründet: Wo eine
// Zahl FEHLT, sagt die Seite es — das ist eine Auskunft über die Quelle.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Building2, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  BeteiligungsDaten, Gesellschaft, Kennzahl, RECHTSFORM_TITEL, Rechtsform,
  auftragSatz, einordnungFuer, eur, herkunftVon, rechtsform, reihen, sortiert,
  istMinderheit, stadtAnteil, wertText,
} from "@/lib/haushalt-beteiligungen";
import type { JahrPunkt } from "@/components/grafik/daten";
import { deZahl } from "@/components/grafik/format";
import { ZeitreiheMini } from "@/components/grafik/zeitreihe";
import { Einordnung } from "@/components/grafik/einordnung";
import { FormZeichen, Konzernkarte } from "@/components/haushalt/konzernkarte";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { Steckbrief } from "@/components/haushalt/beteiligung-steckbrief";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";
import {
  SchrittKicker, SchrittWeiter, schrittNummer,
} from "@/components/haushalt/schritt-weiter";

const QUELLEN = ["beteiligungsbericht"] as const;

/** Die Jahresergebnis-Reihe als Daten-Vertrag des Baukastens: Werte in
 *  Mio. €, ohne erfundene Zwischenjahre — was der Bericht nicht nennt,
 *  bleibt Lücke (die Sparkline bricht dort, `defined()`). */
function ergebnisReihe(ergebnisse: Kennzahl[]): JahrPunkt[] {
  return ergebnisse.map((k) => ({ jahr: k.jahr, wert: k.wert / 1_000_000 }));
}

/** Eine Gesellschafts-Karte (H3-02): Form, Auftrag in einem Satz, eine
 *  Kennzahl groß, Verlauf als Sparkline, Einordnung — Pflichtteil. */
function Karte({ daten, g, onOeffnen }: {
  daten: BeteiligungsDaten; g: Gesellschaft; onOeffnen: () => void;
}) {
  const form = rechtsform(g);
  const ergebnisse = useMemo(
    () => reihen(daten, g.gesellschaft).get("jahresergebnis") ?? [],
    [daten, g.gesellschaft]);
  const juengstes = ergebnisse[ergebnisse.length - 1] ?? null;
  const satz = auftragSatz(daten, g);
  const einordnung = einordnungFuer(daten, g, ergebnisse);
  const reihe = ergebnisReihe(ergebnisse);
  const von = ergebnisse[0]?.jahr, bis = juengstes?.jahr;
  const anteil = stadtAnteil(daten, g.gesellschaft);

  // Aufbau als Artikel mit aufgespanntem Öffnen-Knopf (kein Block- und kein
  // interaktiver Inhalt IN einem <button> — der Beleg-Chip ist selbst einer).
  // Die Fundstellen-Zeile liegt über dem Knopf, damit ihr Chip klickbar bleibt.
  return (
    <article className="group relative flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40">
      <button type="button" onClick={onOeffnen}
        aria-label={`${g.name} — Steckbrief öffnen`}
        className="absolute inset-0 rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary" />

      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {form && <FormZeichen form={form} minderheit={istMinderheit(anteil)} className="h-3 w-3" />}
          {form ? RECHTSFORM_TITEL[form] : "Städtische Einheit"}
          {/* Die Quote steht nur, wo der Bericht sie nennt — keine „0 %“
              für Einheiten, deren Gesellschaftertabelle er nicht führt. */}
          {anteil !== null && (
            <span className="tabular-nums">· Stadt {deZahl(anteil, Number.isInteger(anteil) ? 0 : 2)} %</span>
          )}
        </span>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
          Bericht {g.bericht_jahr}
        </span>
      </div>

      <h3 className="font-display text-[16px] font-bold leading-snug tracking-tight">
        {g.name}
      </h3>

      {satz && (
        <p className="line-clamp-2 text-[12.5px] leading-relaxed text-muted-foreground">
          {satz}
        </p>
      )}

      {juengstes ? (
        <div className="flex items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
              Ergebnis {juengstes.jahr}
            </p>
            <p className="font-display text-[22px] font-bold leading-tight tracking-tight tabular-nums">
              {wertText(juengstes)}
            </p>
          </div>
          {reihe.length >= 2 && (
            <div className="w-[128px] flex-none pb-0.5">
              <ZeitreiheMini
                reihe={reihe}
                format={(v) => deZahl(v, 1)}
                ariaLabel={`Jahresergebnis ${von} bis ${bis} in Mio. Euro: ${ergebnisse
                  .map((k) => `${k.jahr} ${eur(k.wert)}`).join(", ")}.`}
              />
            </div>
          )}
        </div>
      ) : (
        /* Wo die Zahl fehlt, sagt es die Karte — eine stumme Karte sähe nach
           Fehler aus, dabei ist es eine Auskunft über die Quelle. */
        <p className="text-[12px] leading-relaxed text-muted-foreground">
          Für diese Einheit nennt der Bericht kein Jahresergebnis, das eine
          Rechenprobe deckt — die Karte bleibt ohne Kennzahl.
        </p>
      )}

      <Einordnung satz={einordnung} className="mt-0.5" />

      <div className="relative z-10 flex items-center justify-between gap-3 border-t border-dashed border-border pt-2 text-[11px] text-muted-foreground">
        <span>
          Beteiligungsbericht {g.bericht_jahr} · Abschnitt {g.gliederung}
          <Beleg q="beteiligungsbericht" />
        </span>
        <ArrowRight size={13} strokeWidth={2}
          className="flex-none transition-transform group-hover:translate-x-0.5" />
      </div>
    </article>
  );
}


/** Formen-Filter + Suche über den Karten (H3-02 „Suche + Filter nach Form";
 *  mobil sind die Chips der Ersatz für die Konzernkarte im Fluss, H4-11). */
function Filterleiste({ liste, form, setForm, suche, setSuche }: {
  liste: Gesellschaft[];
  form: Rechtsform | null;
  setForm: (f: Rechtsform | null) => void;
  suche: string;
  setSuche: (s: string) => void;
}) {
  const zaehl = (f: Rechtsform) => liste.filter((g) => rechtsform(g) === f).length;
  const chip = (aktiv: boolean) => cn(
    "inline-flex min-h-[36px] flex-none items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] transition-colors",
    aktiv ? "border-primary bg-primary font-semibold text-primary-foreground"
      : "border-border bg-card text-foreground/80 hover:bg-accent",
  );
  return (
    <div className="flex flex-col gap-2">
      <div className="scrollbar-none -mx-1 flex items-center gap-1.5 overflow-x-auto px-1 py-0.5">
        <button type="button" onClick={() => setForm(null)} aria-pressed={form === null}
          className={chip(form === null)}>
          alle {liste.length}
        </button>
        {(Object.keys(RECHTSFORM_TITEL) as Rechtsform[]).map((f) => (
          zaehl(f) > 0 && (
            <button key={f} type="button" onClick={() => setForm(form === f ? null : f)}
              aria-pressed={form === f} className={chip(form === f)}>
              <FormZeichen form={f} ton={form === f ? "currentColor" : undefined} />
              {RECHTSFORM_TITEL[f]} · {zaehl(f)}
            </button>
          )
        ))}
      </div>
      <input
        type="search" value={suche} onChange={(e) => setSuche(e.target.value)}
        placeholder="Gesellschaft suchen — Klinikum, Bäder, Wohnen …"
        aria-label="Gesellschaft suchen"
        className="h-10 w-full rounded-xl border border-border bg-card px-3.5 text-[13.5px] shadow-sm outline-none placeholder:text-muted-foreground/70 focus:border-primary/50"
      />
    </div>
  );
}

function Seite() {
  const params = useSearchParams();
  const router = useRouter();
  const gewaehlt = params.get("g");
  const { data, loading } = useFetch<BeteiligungsDaten>("/council/haushalt/beteiligungen");
  const [form, setForm] = useState<Rechtsform | null>(null);
  const [suche, setSuche] = useState("");
  // Mobil steht die Konzernkarte hinter dem Auslöser „Wer gehört zu wem?" —
  // hinter einem Auslöser, nie ersatzlos (H4-A).
  const [karteOffen, setKarteOffen] = useState(false);

  const liste = useMemo(() => sortiert(data), [data]);
  const aktiv = liste.find((g) => g.gesellschaft === gewaehlt) ?? null;
  const bericht = data?.berichtsjahre?.[data.berichtsjahre.length - 1] ?? null;
  const jahre = data?.jahre ?? [];
  const quelleUrl = herkunftVon(data, liste[0]?.herkunft_id)?.url ?? null;

  const gefiltert = useMemo(() => {
    const q = suche.trim().toLowerCase();
    return liste.filter((g) =>
      (form === null || rechtsform(g) === form)
      && (!q || g.name.toLowerCase().includes(q)));
  }, [liste, form, suche]);

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

  const oeffne = (key: string) =>
    router.push(`/haushalt/beteiligungen?g=${encodeURIComponent(key)}`);

  // Der Anteil der Stadt je Gesellschaft — aus der Gesellschaftertabelle des
  // Berichts, die nur mit bestandener Probe im Bestand landet.
  const quote = (g: string) => stadtAnteil(data, g);

  return (
    <Quellenkontext schluessel={[...QUELLEN]} jahr={bericht}>
      {aktiv ? (
        <div className="flex flex-col gap-4">
          <Steckbrief daten={data} g={aktiv}
            zurueck={() => router.push("/haushalt/beteiligungen")} />
          <SchrittWeiter href="/haushalt/beteiligungen" />

          <Quellenverzeichnis schluessel={[...QUELLEN]} />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-end justify-between gap-5">
            <div className="min-w-0">
              <SchrittKicker href="/haushalt/beteiligungen" />
              <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
                Was machen die eigentlich?
              </h1>
              <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
                Die Stadt ist mehr als das Rathaus: {liste.length} Betriebe und
                Gesellschaften erledigen städtische Aufgaben — vom Klinikum bis zur
                Volkshochschule. Die Form sagt, wie nah sie der Stadt stehen; die Zahlen
                reichen {jahre.length ? `von ${jahre[0]} bis ${jahre.at(-1)}` : "mehrere Jahre"} zurück.
              </p>
            </div>
            {quelleUrl && (
              <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
                className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
                <FileText className="h-3.5 w-3.5" /> Quelle öffnen
              </a>
            )}
          </div>

          {/* Die Formen-Sprache — einmal erklärt, dann tragen Karte und
              Karten sie wortlos. Die vierte Zeile ist bewusst KEINE vierte
              Form, sondern ein zweites Zeichen: Die Rechtsform sagt, wie eine
              Einheit verfasst ist, der Ring sagt, wie viel davon der Stadt
              gehört. Eine GmbH bleibt eine GmbH, auch bei 34,5 %. */}
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Die Form sagt, wie nah sie der Stadt stehen
            </p>
            <dl className="mt-2 flex flex-col gap-1.5">
              <div className="flex items-baseline gap-2.5">
                <dt className="flex flex-none items-center gap-1.5">
                  <FormZeichen form="eigenbetrieb" />
                  <span className="text-[12.5px] font-semibold">Eigenbetrieb</span>
                </dt>
                <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                  Teil der Stadt, eigenes Rechnungswesen
                </dd>
              </div>
              <div className="flex items-baseline gap-2.5">
                <dt className="flex flex-none items-center gap-1.5">
                  <FormZeichen form="aoer" />
                  <span className="text-[12.5px] font-semibold">Anstalt öffentlichen Rechts</span>
                </dt>
                <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                  eigenständig, öffentlich
                </dd>
              </div>
              <div className="flex items-baseline gap-2.5">
                <dt className="flex flex-none items-center gap-1.5">
                  <FormZeichen form="gesellschaft" />
                  <span className="text-[12.5px] font-semibold">GmbH / Co. KG</span>
                </dt>
                <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                  privatrechtlich, die Stadt ist Eigentümerin
                </dd>
              </div>
              <div className="flex items-baseline gap-2.5 border-t border-dashed border-border pt-1.5">
                <dt className="flex flex-none items-center gap-1.5">
                  <FormZeichen form="gesellschaft" minderheit />
                  <span className="text-[12.5px] font-semibold">Minderheitsanteil</span>
                </dt>
                <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                  die Stadt hält weniger als die Hälfte
                  <Beleg q="beteiligungsbericht" />
                </dd>
              </div>
            </dl>
          </div>

          {/* Konzernkarte: ab 744 px im Seitenfluss (H4-11); mobil hinter dem
              Auslöser — hinter einem Auslöser, nie ersatzlos (H4-A). */}
          <div className="mobil:hidden">
            <Konzernkarte gesellschaften={liste} aufGesellschaft={oeffne} anteil={quote} />
          </div>
          <div className="ab-tablet:hidden">
            <button type="button" onClick={() => setKarteOffen(!karteOffen)}
              aria-expanded={karteOffen}
              className="flex min-h-[44px] w-full items-center justify-between rounded-2xl border border-border bg-card px-4 py-2.5 text-left shadow-sm">
              <span className="text-[13.5px] font-semibold">Wer gehört zu wem?</span>
              <span className="text-[12px] text-muted-foreground">
                {karteOffen ? "Karte ausblenden" : "Konzernkarte zeigen"}
              </span>
            </button>
            {karteOffen && (
              <Konzernkarte className="mt-2" gesellschaften={liste} aufGesellschaft={oeffne}
                anteil={quote} />
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

          <section className="flex flex-col gap-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Die Gesellschaften
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {gefiltert.length} von {liste.length} · Bericht {bericht}
              </p>
            </div>
            <Filterleiste liste={liste} form={form} setForm={setForm}
              suche={suche} setSuche={setSuche} />
            {gefiltert.length ? (
              <div className="grid gap-2.5 ab-tablet:grid-cols-2">
                {gefiltert.map((g) => (
                  <Karte key={g.gesellschaft} daten={data} g={g}
                    onOeffnen={() => oeffne(g.gesellschaft)} />
                ))}
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-[13px] text-muted-foreground">
                Zu „{suche}" findet sich keine Gesellschaft. Die Namen sind die amtlichen —
                das Klinikum heißt „Klinikum Oldenburg AöR", die Busse „Verkehr und Wasser
                GmbH".
              </p>
            )}
          </section>

          {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. Dieselbe
              Entscheidung wie auf /haushalt/konzern: Wer hier eine Zahl
              herausschreibt, soll wissen, was sie nicht ist. */}
          <section className="@container rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
              Was dieser Bericht nicht hergibt
            </p>
            <ul className="mt-2 grid list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:grid-cols-2">
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
                und ohne Kennzahlen-Tabelle. Die Zahlen reichen trotzdem bis {jahre[0] ?? 2017} zurück,
                weil jeder Bericht mehrere Jahre nebeneinander führt.
              </li>
              <li>
                <strong>Die beschreibenden Abschnitte sind Text der Verwaltung.</strong>{" "}
                Sie stehen hier im Wortlaut, ungekürzt und ungeprüft — gegen sie lässt
                sich nichts rechnen.
              </li>
              <li>
                <strong>Kein Stimmverhalten in Aufsichtsräten, keine Gehälter.</strong>{" "}
                Beides steht nicht im Bericht — die Seite behauptet es deshalb auch nicht.
              </li>
            </ul>
          </section>

          {/* Arbeitsteilung mit Schritt 11 (H4-10-Review): hier die
              Gesellschaften einzeln, dort das Ganze. */}
          <Link href="/haushalt/konzern"
            className="group flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/40">
            <span className="min-w-0">
              <span className="block font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Schritt {schrittNummer("/haushalt/konzern")} · Und ist das die ganze Stadt?
              </span>
              <span className="mt-0.5 block text-[13.5px] font-semibold leading-snug">
                Wie groß der Konzern Stadt insgesamt ist — Kernverwaltung und alle
                Einheiten zusammen — zeigt der Gesamtabschluss.
              </span>
            </span>
            <ArrowRight size={16} strokeWidth={2}
              className="flex-none text-primary transition-transform group-hover:translate-x-0.5" />
          </Link>

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
