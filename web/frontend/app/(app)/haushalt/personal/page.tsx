"use client";

// /haushalt/personal — „Wer macht die Arbeit?"
//
// Die Seite hat eine Aussage, und sie ist die Fortsetzung eines Satzes, der
// im Bereich schon steht: In `components/haushalt/hantel.tsx` heißt es,
// Minderausgaben seien nicht automatisch gut — „nicht gebaut, Stellen
// unbesetzt". Hier stehen diese Stellen. Personal ist der größte
// Ausgabenblock der Stadt, und rund ein Sechstel bis ein Fünftel der Stellen
// war am jeweiligen Stichtag nicht besetzt. Wer die Personalausgaben unter
// Plan sieht, sieht nicht Sparsamkeit, sondern eine Suche.
//
// Leserichtung: die Lücke des jüngsten Jahres als Zahl → was ein Stellenplan
// überhaupt ist → beide Teile über die Jahre → wo die Lücken am größten sind
// → was diese Zahlen NICHT hergeben → Quellen.
//
// DREI DINGE, DIE HIER BEWUSST NICHT STEHEN:
//
//  * **Keine Bewertungsfarbe an der Lücke.** Weder Rot noch Grün: Eine
//    unbesetzte Stelle kann bedeuten, dass niemand zu finden war, dass eine
//    Stelle absichtlich frei gehalten wird oder dass gerade jemand wechselt.
//    Alle drei sehen in der Tabelle gleich aus. Begründung ausführlich in
//    `components/haushalt/stellen-verlauf.tsx`.
//  * **Kein Vergleich mit anderen Städten.** Die Stadt hat genau diesen
//    Vergleich 2018 selbst angestellt und im selben Dokument entwertet — das
//    steht auf `/haushalt/vergleich` samt Zitat und gehört nicht zweimal ins
//    Frontend.
//  * **Keine Umrechnung in Köpfe oder in Euro.** Der Plan zählt Stellen; wie
//    viele Menschen darauf arbeiten, steht nirgends, und was eine Stelle
//    kostet, hängt an der Besoldungsgruppe. Beides ließe sich schätzen, und
//    beides wäre dann unsere Zahl und nicht die der Stadt.
//
// DER JAHR-UMSCHALTER STEUERT NUR DIE DETAILS. Der Verlauf zeigt immer alle
// Jahrgänge — er IST die Entwicklung. Umgeschaltet wird, welches Jahr die
// Kernzahl und die Liste der größten Lücken zeigen.

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
import { StellenLegende, StellenVerlauf } from "@/components/haushalt/stellen-verlauf";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

const QUELLEN = ["stellenplan"] as const;

/** Warum ein Teil in einem Jahrgang fehlt. „Gibt es nicht" und „steht im PDF,
 *  ist aber nicht lesbar" sind zwei verschiedene Auskünfte, und nur die
 *  zweite stimmt hier. */
const FEHLT_GRUND = "im Dokument nicht lesbar";

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
  const jahrgaenge = useFetch<StellenplanDaten>("/council/haushalt/stellenplan");
  const alle = jahrgaenge.data?.jahrgaenge ?? [];
  const aktJahr = jahr && alle.includes(jahr) ? jahr : alle.at(-1) ?? null;

  // Die Einzelposten kommen nur für das gewählte Jahr — rund 190 Zeilen je
  // Jahrgang, und die Seite zeigt davon acht.
  const detail = useFetch<StellenplanDaten>(
    aktJahr ? `/council/haushalt/stellenplan?jahrgang=${aktJahr}` : null);
  const daten = detail.data ?? jahrgaenge.data;

  const skala = useMemo(() => Math.max(
    1, ...(daten?.summen ?? []).map((z) => z.stellen_vorjahr)), [daten]);

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

  // Die Kernzahl nimmt den jüngsten Jahrgang, für den BEIDE Teile vorliegen —
  // sonst stünde für 2026 „815 Stellen" da und die 1.700 Tarifstellen fehlten
  // wortlos. Welches Jahr das ist, steht daneben.
  const vollJahr = [...alle].reverse().find(
    (j) => TEILE.every((t) => gesamt(daten, j, t))) ?? aktJahr;
  const kopf = TEILE.map((t) => ({ teil: t, zeile: gesamt(daten, vollJahr, t) }))
    .filter((x) => x.zeile);
  const kopfLuecke = kopf.reduce(
    (s, x) => s + (x.zeile?.nicht_besetzt ?? 0), 0);
  const kopfStellen = kopf.reduce(
    (s, x) => s + (x.zeile?.stellen_vorjahr ?? 0), 0);
  const kopfStichtag = kopf[0]?.zeile?.stichtag ?? null;
  const kopfPlan = kopf.reduce((s, x) => s + (x.zeile?.stellen_plan ?? 0), 0);

  const detailZeilen = detail.data?.zeilen ?? [];
  const luecken = groessteLuecken(detailZeilen, teil);
  const teilGesamt = gesamt(daten, aktJahr, teil);
  const teilFehlt = fehlt(daten, aktJahr, teil);
  const quelleUrl = herkunftVon(daten, kopf[0]?.zeile?.herkunft_id)?.url ?? null;

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

        {/* Die Kernaussage: der Plan, und daneben die Besetzung am Stichtag.
            Zwei Zahlen, zwei Zeitpunkte — beide werden benannt. */}
        <div className="flex flex-col gap-3.5 rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div>
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stellenplan {vollJahr} · Kernverwaltung
            </p>
            <p className="mt-1.5 max-w-[72ch] text-sm leading-relaxed text-foreground/90">
              Für {vollJahr} sieht die Stadt{" "}
              <strong>{deStellen(kopfPlan)} Stellen</strong> vor
              <Beleg q="stellenplan" /> —{" "}
              {kopf.map((x, i) => (
                <span key={x.teil}>
                  {i > 0 ? " und " : ""}
                  {deStellen(x.zeile!.stellen_plan)} für {TEIL_LABEL[x.teil].toLowerCase()}
                </span>
              ))}.
            </p>
            {kopfStellen > 0 && (
              <p className="mt-2 max-w-[72ch] text-sm leading-relaxed text-foreground/90">
                Am {deDatum(kopfStichtag)} — dem Stichtag, den derselbe Plan für die Besetzung
                nennt — waren <strong>{deStellen(kopfLuecke)} Stellen nicht besetzt</strong>,
                von {deStellen(kopfStellen)}. Das ist rund{" "}
                {(kopfLuecke / kopfStellen * 100).toLocaleString("de-DE", { maximumFractionDigits: 0 })}
                &nbsp;% der Stellen, die es damals gab.
              </p>
            )}
          </div>
          {/* Der Satz, um den es geht — und die einzige Stelle, an der die
              Seite die Zahl deutet. Sie deutet sie in beide Richtungen. */}
          <p className="max-w-[72ch] rounded-xl bg-muted/40 p-3 text-[13px] leading-relaxed text-foreground/90">
            Unbesetzte Stellen sind weder ein Sparerfolg noch ein Versäumnis. Sie erklären
            aber, warum die Personalausgaben im{" "}
            <Link href="/haushalt/plan-ist" className="font-semibold text-primary">
              Jahresabschluss
            </Link>{" "}
            oft unter dem Plan bleiben: Das Geld war eingeplant, die Stelle stand im Plan —
            besetzt war sie nicht. Ob niemand zu finden war, ob gerade jemand wechselte oder
            ob eine Stelle bewusst frei blieb, sagt der Stellenplan nicht.
          </p>
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

        {/* Der Verlauf — beide Teile untereinander, gemeinsame Skala. */}
        <section className="@container/verlauf rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Stellen und Besetzung über die Jahre
            </h2>
            <span className="flex-none font-mono text-[10px] font-medium tabular-nums text-muted-foreground">
              {alle[0]}–{alle.at(-1)}
            </span>
          </div>

          {TEILE.map((t) => {
            const mit = jahrgaengeMitTeil(daten, t);
            return (
              <div key={t} className="mt-4 first:mt-3">
                <h3 className="text-[13px] font-semibold">{TEIL_LABEL[t]}</h3>
                <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                  {mit.length === alle.length
                    ? `${mit.length} Jahrgänge`
                    : `${mit.length} von ${alle.length} Jahrgängen — für `
                      + `${alle.filter((j) => !mit.includes(j)).join(", ")} `
                      + `liegt dieser Teil nicht lesbar vor`}
                </p>
                <div className="mt-2">
                  <StellenVerlauf
                    skala={skala}
                    zeilen={alle.map((j) => ({
                      jahrgang: j,
                      zeile: gesamt(daten, j, t),
                      fehlt: FEHLT_GRUND,
                    }))}
                  />
                </div>
                <div className="mt-2">
                  <StellenLegende />
                </div>
              </div>
            );
          })}

          <p className="mt-3.5 border-t border-dashed border-border pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Links die Stellen, die der Plan für sein Haushaltsjahr vorsieht. Rechts, wie es im
            Jahr davor aussah — der Plan nennt beides nebeneinander, weil zum Zeitpunkt der
            Aufstellung nur rückwärts gezählt werden kann. Die Prozentzahl ist der unbesetzte
            Anteil der Stellen des Vorjahres; sie ist unsere Division, alles andere steht so
            im Dokument.<Beleg q="stellenplan" />
          </p>
        </section>

        {/* Wo die Lücken am größten sind — die Einzelposten des gewählten Jahres. */}
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wo die Lücken am größten sind
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <Segmented<StellenTeil> value={teil} onChange={setTeil} options={[
                { value: "A", label: "Beamt*innen" },
                { value: "B", label: "Tarif" },
              ]} />
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

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
      </div>
    </Quellenkontext>
  );
}
