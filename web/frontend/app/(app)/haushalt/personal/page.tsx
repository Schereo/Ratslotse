"use client";

// /haushalt/personal — „Wer macht die Arbeit?" (Boards H3-01, H4-05)
//
// Die Seite hat eine Aussage, und sie ist die Fortsetzung eines Satzes, der
// im Bereich schon steht: In `components/grafik/hantel.tsx` heißt es,
// Minderausgaben seien nicht automatisch gut — „nicht gebaut, Stellen
// unbesetzt". Hier stehen diese Stellen. Das tragende Bild ist die WAFFEL
// (GB-06): ein Quadrat je zehn Stellen, die unbesetzten als Signal-Umriss —
// aus „18 %" wird ein zählbares Bild, ohne zu bewerten.
//
// DIE WAFFEL ZÄHLT DEN STICHTAGS-BESTAND, NICHT DEN PLAN. Die Besetzung
// gehört zur Vorjahresspalte (s. lib/haushalt-stellenplan.ts): Der Plan 2026
// nennt 815 Stellen — und daneben, wie es am 30.6.2025 aussah: 796 Stellen,
// 143,71 davon unbesetzt. Alle Quadrate einer Waffel tragen deshalb DENSELBEN
// Stichtag; die 815 stehen als Zahl in der Überschrift, mit ihrem eigenen
// Datum. Eine Waffel über die Planstellen mit „besetzt"-Quadraten wäre genau
// die Über-Kreuz-Rechnung, die diese Seite ausschließt.
//
// DREI DINGE, DIE HIER BEWUSST NICHT STEHEN (als Chips auch auf der Seite):
//
//  * **Keine Summe A+B.** Sie steht in keinem Dokument — der Plan führt
//    Beamt*innen und Tarifbeschäftigte getrennt, mit eigenen Tabellen.
//  * **Keine Bewertungsfarbe an der Lücke.** Weder Rot noch Grün: Eine
//    unbesetzte Stelle kann bedeuten, dass niemand zu finden war, dass eine
//    Stelle absichtlich frei gehalten wird oder dass gerade jemand wechselt.
//  * **Keine Umrechnung in Köpfe oder in Euro.** Der Plan zählt Stellen;
//    beides ließe sich schätzen, und beides wäre dann unsere Zahl.
//
// DER TEIL-UMSCHALTER erzählt einen Vergleich, keinen Wettbewerb — er
// steuert Waffel, Jahrgangs-Paare und die Detail-Liste zugleich. Der
// Jahr-Umschalter darunter betrifft nur die Detail-Liste.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import {
  StellenTeil, StellenplanDaten, TEILE, TEIL_LABEL,
  deDatum, deStellen, fehlt, gesamt, groessteLuecken, herkunftVon,
  jahrgaengeMitTeil, luecke,
} from "@/lib/haushalt-stellenplan";
import { StellenPaare, StellenPaareLegende } from "@/components/haushalt/stellen-verlauf";
import { Waffel } from "@/components/grafik/waffel";
import { Einordnung } from "@/components/grafik/einordnung";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

const QUELLEN = ["stellenplan"] as const;

/** Warum ein Teil in einem Jahrgang fehlt. „Gibt es nicht" und „steht im PDF,
 *  ist aber nicht lesbar" sind zwei verschiedene Auskünfte, und nur die
 *  zweite stimmt hier (Stellenplan 2026, Teil B). */
const FEHLT_GRUND = "das PDF gibt hier Zeichen-Nummern statt Buchstaben aus; "
  + "bleibt leer, bis die Stadt neu veröffentlicht";

/** Unsere einzige Division auf der Seite — der unbesetzte Anteil aus
 *  `luecke()`, gerundet auf ganze Prozent. */
function pct(anteil: number): string {
  return (anteil * 100).toLocaleString("de-DE", { maximumFractionDigits: 0 });
}

/** Die Herkunft einer Angabe im Klartext — dasselbe Muster wie auf
 *  /haushalt/konzern: Das Quellenverzeichnis am Seitenende beschreibt die
 *  Quelle der ganzen Seite, das hier gehört an die einzelne Zahl. */
function Fundstelle({ daten, id }: { daten: StellenplanDaten; id: number | null }) {
  const h = herkunftVon(daten, id);
  if (!h) return null;
  return (
    <div className="border-t border-dashed border-border pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      {h.fundstelle && (
        <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
          {h.fundstelle}{h.stand ? ` · ${h.stand}` : ""}
        </p>
      )}
    </div>
  );
}

export default function PersonalPage() {
  const [jahr, setJahr] = useState<number | null>(null);
  const [teil, setTeil] = useState<StellenTeil>("A");
  // Detailtabelle mobil hinter „alle Gruppen zeigen" (H4-05); ab Tablet
  // immer offen — die Klassen dazu stehen in globals.css (gb-nur-mobil).
  const [gruppenOffen, setGruppenOffen] = useState(false);
  const jahrgaenge = useFetch<StellenplanDaten>("/council/haushalt/stellenplan");
  const alle = jahrgaenge.data?.jahrgaenge ?? [];
  const aktJahr = jahr && alle.includes(jahr) ? jahr : alle.at(-1) ?? null;

  // Die Einzelposten kommen nur für das gewählte Jahr — rund 190 Zeilen je
  // Jahrgang, und die Seite zeigt davon acht.
  const detail = useFetch<StellenplanDaten>(
    aktJahr ? `/council/haushalt/stellenplan?jahrgang=${aktJahr}` : null);
  const daten = detail.data ?? jahrgaenge.data;

  // Eine Skala je Teil (H3-01): A und B stehen nie gleichzeitig im Bild,
  // und innerhalb eines Teils soll die Schere über die Jahrgänge lesbar
  // sein. Obergrenze ist der größte Wert, den ein Balken zeigen kann.
  const skala = useMemo(() => Math.max(
    1, ...(daten?.summen ?? [])
      .filter((z) => z.teil === teil)
      .flatMap((z) => [z.stellen_plan, z.besetzt])), [daten, teil]);

  if (jahrgaenge.loading) {
    return <div className="py-16 text-center text-sm text-muted-foreground">
      Der Stellenplan wird geladen …
    </div>;
  }
  if (!daten || !daten.summen.length || !aktJahr) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Für diese Seite ist noch kein Stellenplan eingelesen.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  // Der jüngste Jahrgang, für den der GEWÄHLTE Teil vorliegt — für Teil B
  // ist das 2025, weil 2026 im PDF nicht lesbar ist. Die Lücke selbst steht
  // in den Jahrgangs-Zeilen, nicht versteckt in einer Fußnote.
  const teilJahre = jahrgaengeMitTeil(daten, teil);
  const teilNeu = teilJahre.at(-1) ?? null;
  const kern = teilNeu ? gesamt(daten, teilNeu, teil) : null;
  const kernLuecke = luecke(kern);

  const detailZeilen = detail.data?.zeilen ?? [];
  const luecken = groessteLuecken(detailZeilen, teil);
  const teilGesamt = gesamt(daten, aktJahr, teil);
  const teilFehlt = fehlt(daten, aktJahr, teil);
  const quelleUrl = herkunftVon(daten, kern?.herkunft_id)?.url ?? null;

  // Der Vergleichs-Satz unterm Umschalter — gerechnet, nicht behauptet:
  // erster und letzter Plan je Teil, dazu der jüngste unbesetzte Anteil.
  const vergleich = TEILE.map((t) => {
    const js = jahrgaengeMitTeil(daten, t);
    const von = js.length ? gesamt(daten, js[0], t) : null;
    const bis = js.length > 1 ? gesamt(daten, js[js.length - 1], t) : null;
    const l = luecke(bis ?? von);
    return von && bis && l ? {
      teil: t,
      spanne: `${deStellen(von.stellen_plan)} → ${deStellen(bis.stellen_plan)}`,
      anteil: pct(l.anteil),
    } : null;
  });
  const [vglA, vglB] = vergleich;

  return (
    <Quellenkontext schluessel={[...QUELLEN]} jahr={aktJahr}>
      <div className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stadtfinanzen Oldenburg · Schritt 5
            </p>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Wer macht die Arbeit?
            </h1>
            <p className="mt-1.5 max-w-[64ch] text-sm leading-relaxed text-muted-foreground">
              Personal ist der größte Ausgabenblock der Stadt. Wie viele Stellen dahinterstehen,
              legt der Rat mit dem Haushalt fest — im Stellenplan, Zeile für Zeile.
            </p>
          </div>
          {quelleUrl && (
            <a href={quelleUrl} target="_blank" rel="noopener noreferrer"
              className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
              <FileText className="h-3.5 w-3.5" /> Quelle öffnen
            </a>
          )}
        </div>

        {/* Das tragende Bild (H3-01): Waffel links, Jahrgangs-Paare rechts —
            mobil untereinander, der Umschalter volle Breite (H4-05). */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2.5">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stellenplan · {TEIL_LABEL[teil]}<Beleg q="stellenplan" />
            </p>
            <Segmented<StellenTeil> value={teil} onChange={setTeil}
              className="w-full min-[480px]:w-auto [&_button]:min-h-[44px] sm:[&_button]:min-h-0"
              options={[
                { value: "A", label: "Teil A · Beamt*innen" },
                { value: "B", label: "Teil B · Tarif" },
              ]} />
          </div>

          <div className="mt-4 grid gap-6 breit:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] breit:gap-8">
            {/* Links: die Kernzahl und die Waffel. */}
            <div className="flex flex-col gap-3">
              {kern && kernLuecke ? (
                <>
                  <h2 className="max-w-[26ch] font-display text-[21px] font-bold leading-snug tracking-tight">
                    {deStellen(kern.stellen_plan)} Stellen hält die Stadt {teilNeu} vor —
                    rund {pct(kernLuecke.anteil)}&nbsp;% waren zuletzt unbesetzt
                  </h2>
                  <p className="max-w-[58ch] text-[13px] leading-relaxed text-foreground/90">
                    Jedes Quadrat sind zehn Stellen — gezeigt sind die{" "}
                    {deStellen(kernLuecke.stellen)} Stellen, die es am Stichtag{" "}
                    <strong>{deDatum(kernLuecke.stichtag)}</strong> gab; die umrandeten
                    davon waren nicht besetzt. Die Besetzung wird immer ein Jahr
                    versetzt erhoben.
                  </p>
                  <Waffel
                    gesamt={kernLuecke.stellen}
                    proQuadrat={10}
                    einheit="Stellen"
                    grundLabel="besetzt"
                    markiert={{
                      anzahl: kernLuecke.nicht_besetzt,
                      grund: `unbesetzt · rund ${pct(kernLuecke.anteil)} %`,
                      stichtag: deDatum(kernLuecke.stichtag),
                    }}
                  />
                </>
              ) : (
                <p className="text-[13px] leading-relaxed text-muted-foreground">
                  Für {TEIL_LABEL[teil]} liegt kein Jahrgang lesbar vor.
                </p>
              )}

              {/* Der Kasten steht VOR der ersten Zahl-Interaktion — auf jedem
                  Gerät (H4-05). */}
              <div className="max-w-[58ch] rounded-xl bg-muted/40 p-3 text-[12.5px] leading-relaxed text-foreground/90">
                <strong>Warum wir hier nicht einfach subtrahieren:</strong> Die
                Stellenzahl gilt fürs Planjahr, die Besetzung für den Stichtag des
                Vorjahres. „Stellen − besetzt“ über Kreuz wäre eine erfundene Zahl —
                deshalb stehen beide Angaben getrennt, jede mit ihrem Datum.
              </div>
            </div>

            {/* Rechts: die Schere über die Jahrgänge — Besetzung als eigene
                Spalte, nie verrechnet. */}
            <div className="flex min-w-0 flex-col gap-2.5">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                  Je Jahrgang
                </h3>
                <span className="flex-none font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                  Stellen · besetzt
                </span>
              </div>
              <StellenPaare
                skala={skala}
                aktJahr={teilNeu}
                zeilen={alle.map((j) => ({
                  jahrgang: j,
                  zeile: gesamt(daten, j, teil),
                  fehlt: FEHLT_GRUND,
                }))}
              />
              <StellenPaareLegende />
              {vglA && vglB && (
                <Einordnung className="mt-1" satz={<>
                  <strong>Der Umschalter erzählt einen Vergleich, keinen
                  Wettbewerb:</strong> Beamt*innenstellen wachsen ({vglA.spanne}),
                  Tarifstellen auch ({vglB.spanne}) — unbesetzt bleiben beide,
                  zuletzt rund {vglA.anteil}&nbsp;% hier, rund {vglB.anteil}&nbsp;% dort.
                </>} />
              )}
            </div>
          </div>
        </section>

        {/* Was diese Seite bewusst nicht zeigt — sichtbar, nicht Kleingedrucktes
            (H3-01); die Chips bleiben auf jedem Gerät stehen (H4-A). */}
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Bewusst nicht auf der Seite
          </span>
          {["keine Summe A+B — steht in keinem Dokument",
            "keine Namen, keine Organigramme",
            "keine Ist-Personalausgaben je Gruppe"].map((c) => (
            <span key={c}
              className="rounded-full border border-dashed border-border px-2.5 py-1 text-[11px] text-muted-foreground">
              {c}
            </span>
          ))}
        </div>

        <LottiErklaert
          titel="Was ist ein Stellenplan?"
          text={"Der Rat beschließt mit dem Haushalt nicht nur, wie viel Geld die Stadt "
            + "ausgeben darf, sondern auch, wie viele Stellen sie haben darf — für jede "
            + "Amtsbezeichnung einzeln. Gezählt werden Stellen, nicht Menschen: Zwei "
            + "Personen in Teilzeit teilen sich eine Stelle, und eine halbe Stelle steht "
            + "als 0,50 da. Wer die Stelle bekommt, entscheidet die Verwaltung; ob es die "
            + "Stelle gibt, entscheidet der Rat."}
        />

        {/* Der Satz, um den es geht — und die einzige Stelle, an der die
            Seite die Zahl deutet. Sie deutet sie in beide Richtungen. */}
        <p className="max-w-[76ch] rounded-xl bg-muted/40 p-3 text-[13px] leading-relaxed text-foreground/90">
          Unbesetzte Stellen sind weder ein Sparerfolg noch ein Versäumnis. Sie erklären
          aber, warum die Personalausgaben im{" "}
          <Link href="/haushalt/plan-ist" className="font-semibold text-primary">
            Jahresabschluss
          </Link>{" "}
          oft unter dem Plan bleiben: Das Geld war eingeplant, die Stelle stand im Plan —
          besetzt war sie nicht. Ob niemand zu finden war, ob gerade jemand wechselte oder
          ob eine Stelle bewusst frei blieb, sagt der Stellenplan nicht.
        </p>

        {/* Wo die Lücken am größten sind — die Einzelposten des gewählten
            Jahres, mobil hinter „alle Gruppen zeigen" (H4-05). */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wo die Lücken am größten sind · {TEIL_LABEL[teil]}
            </h2>
            {alle.length > 1 && (
              <div className="flex flex-wrap gap-1">
                {alle.map((j) => (
                  <button key={j} type="button" onClick={() => setJahr(j)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 font-mono text-[11px] tabular-nums transition-colors",
                      j === aktJahr
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-muted-foreground hover:border-primary/40",
                    )}>
                    {j}
                  </button>
                ))}
              </div>
            )}
          </div>

          {teilFehlt ? (
            <p className="mt-2.5 max-w-[76ch] text-[13px] leading-relaxed text-muted-foreground">
              Für {aktJahr} liegt {TEIL_LABEL[teil]} nicht vor: Das PDF des Stellenplans gibt
              auf diesen Seiten keine Buchstaben aus, sondern Zeichen-Nummern. Wir könnten die
              Zahlen nur raten, und das tun wir nicht.
            </p>
          ) : !detail.data ? (
            <p className="mt-2.5 text-[13px] text-muted-foreground">Wird geladen …</p>
          ) : luecken.length === 0 ? (
            <p className="mt-2.5 text-[13px] text-muted-foreground">
              Für {aktJahr} weist der Plan in {TEIL_LABEL[teil]} keine unbesetzten Stellen aus.
            </p>
          ) : (
            <>
              <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
                Die acht Amtsbezeichnungen mit den meisten unbesetzten Stellen, Stand{" "}
                {deDatum(teilGesamt?.stichtag ?? null)}.
              </p>
              {!gruppenOffen && (
                <button type="button" onClick={() => setGruppenOffen(true)}
                  className="gb-nur-mobil mt-2 text-[12px] font-semibold text-primary">
                  Alle Gruppen zeigen
                </button>
              )}
              <div className={gruppenOffen ? undefined : "gb-ab-tablet"}>
                <ul className="mt-3 flex flex-col divide-y divide-border">
                  {luecken.map((z) => (
                    <li key={`${z.lfd_nr}-${z.besoldung}`}
                      className="flex items-baseline gap-3 py-2 first:pt-0">
                      <span className="min-w-0 flex-1">
                        <span className="text-[13px] font-medium">{z.bezeichnung}</span>
                        {z.besoldung && (
                          <span className="ml-2 font-mono text-[10.5px] text-muted-foreground">
                            {z.besoldung}
                          </span>
                        )}
                      </span>
                      <span className="flex-none font-mono text-[12px] tabular-nums text-muted-foreground">
                        {deStellen(z.stellen_vorjahr)} Stellen
                      </span>
                      <span className="w-[5.5rem] flex-none text-right font-display text-[14px] font-bold tabular-nums">
                        {deStellen(z.nicht_besetzt)}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
                  Rechts die unbesetzten Stellen, daneben wie viele es in dieser Zeile insgesamt
                  gab. Die Bezeichnungen sind Amtsbezeichnungen aus dem Besoldungsrecht, keine
                  Berufsbezeichnungen — hinter „Stadtoberinspektor/-in" steckt kein Beruf,
                  sondern eine Besoldungsstufe, auf der sehr verschiedene Aufgaben liegen.
                </p>
              </div>
              <div className="mt-3">
                <Fundstelle daten={daten} id={teilGesamt?.herkunft_id ?? null} />
              </div>
            </>
          )}
        </section>

        {/* Die Grenzen — eigener Block, nicht Kleingedrucktes. */}
        <section className="rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Was diese Zahlen nicht hergeben
          </p>
          <ul className="mt-2 flex max-w-[76ch] list-disc flex-col gap-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90">
            <li>
              <strong>Stellen sind keine Menschen.</strong> Eine Stelle kann sich auf zwei
              Personen in Teilzeit verteilen, und eine halbe Stelle steht als 0,50 im Plan.
              Wie viele Menschen für die Stadt arbeiten, sagt der Stellenplan nicht.
            </li>
            <li>
              <strong>Nur die Kernverwaltung.</strong> Klinikum, Bäder, Busse und die
              Gebäudewirtschaft führen eigene Wirtschaftspläne und stehen hier nicht drin —
              was das ausmacht, zeigt{" "}
              <Link href="/haushalt/konzern" className="font-semibold text-primary">
                der Blick auf den ganzen Konzern
              </Link>.
            </li>
            <li>
              <strong>Zwei Zeitpunkte in einer Tabelle.</strong> Die geplanten Stellen gelten
              für das Haushaltsjahr, die Besetzung für einen Stichtag im Jahr davor. Beide
              Zahlen voneinander abzuziehen ergäbe eine Lücke, die es so nie gab.
            </li>
            <li>
              <strong>Es ist der Entwurf der Verwaltung.</strong> Der Stellenplan hängt an der
              Vorlage, mit der der Haushalt eingebracht wird. Was der Rat in den Beratungen
              noch ändert, steht nicht darin.
            </li>
            <li>
              <strong>Kein Vergleich mit anderen Städten.</strong> Die Stadt hat genau diesen
              Vergleich 2018 selbst angestellt und im selben Dokument entwertet — nachzulesen
              beim{" "}
              <Link href="/haushalt/vergleich" className="font-semibold text-primary">
                Städtevergleich
              </Link>.
            </li>
          </ul>
        </section>

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

        <SchrittWeiter href="/haushalt/personal" />

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
      </div>
    </Quellenkontext>
  );
}
