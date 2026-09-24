"use client";

// „Fördermittel von außen" — Karte auf /haushalt/einnahmen (Plan
// Haushalt-Blickwinkel, B2).
//
// Die Quellen sind die Listen der Geber selbst: die Liste der Vorhaben der
// EU-Strukturfonds in Niedersachsen (EFRE, ESF) und der Förderkatalog des
// Bundes. Übernommen sind nur die Stadt und ihre Gesellschaften, über eine
// nachgesehene Namensliste (council/foerdermittel.py).
//
// KEIN RANG, KEINE BEWERTUNGSFARBE (Tims Entscheidung 24.09.2026): Die
// Vorhaben stehen nach Beginn, jüngstes zuerst — die Frage der Karte ist
// „was läuft gerade?", nicht „wer hat am meisten bekommen?". Beträge in
// Vordergrundfarbe.
//
// Die Filter laufen im Browser: rund hundert Zeilen, die ohnehin geladen
// sind. Die Summen je Geber rechnet das Backend.
//
// Die RATSSEITE (council/foerder_vorlagen.py) steht an zwei Stellen: je
// Vorhaben die Vorlagen, die es erkennbar meinen, und darunter die
// Förderanträge, die der Rat beraten hat. Die Anträge stehen bewusst
// GETRENNT von den Bewilligungen — die meisten gehören zu Programmen, die in
// keiner der beiden Listen stehen, und ein Antrag ist keine Zusage.

import Link from "next/link";
import { useMemo, useState } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deMio } from "@/lib/haushalt";
import { deZahl } from "@/components/grafik/format";
import { Beleg } from "@/components/haushalt/source";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { cn } from "@/lib/utils";
import { decisionHref } from "@/lib/routes";
import { STUFE_TEXT, stufe } from "@/lib/zeitleiste";

type Antwort = ApiAntwort<"/council/budget/grants-received">;
type Zeile = Antwort["rows"][number];
type Vorlage = Antwort["applications"][number];
type Geber = "alle" | "eu" | "bund";

const SICHTBAR = 8;
const ANTRAEGE_SICHTBAR = 5;

/** Die Ressortkürzel des Förderkatalogs im Klartext. */
const RESSORT: Record<string, string> = {
  BMFTR: "Bundesforschungsministerium",
  BMUKN: "Bundesumweltministerium",
  BMV: "Bundesverkehrsministerium",
  BMWE: "Bundeswirtschaftsministerium",
  BMAS: "Bundesarbeitsministerium",
  BMI: "Bundesinnenministerium",
  BMWSB: "Bundesbauministerium",
  BMG: "Bundesgesundheitsministerium",
  BMBFSFJ: "Bundesfamilienministerium",
  BMLEH: "Bundeslandwirtschaftsministerium",
};

const euro = (v: number | null | undefined) => (v == null ? "—" : `${deZahl(v, 0)} €`);
const jahr = (iso: string | null) => (iso ? iso.slice(0, 4) : "?");
const datum = (iso: string | null) => (iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : null);

function geberText(z: Zeile): string {
  if (z.funder === "EU") return z.program ?? "EU";
  return RESSORT[z.funder] ?? z.funder;
}

/** „Vorlage 23/0896" als Link auf die letzte Beratung, sonst als Text. */
function VorlageLink({ v }: { v: Vorlage }) {
  const text = `Vorlage ${v.template_number}`;
  return v.decision_id != null
    ? <Link href={decisionHref(v.decision_id)} className="font-medium text-primary hover:underline">{text}</Link>
    : <span className="font-medium text-foreground">{text}</span>;
}

function Beratung({ v }: { v: Vorlage }) {
  if (!v.date) return null;
  return <>{v.committee ?? "Rat"}, {datum(v.date)}, {STUFE_TEXT[stufe(v.outcome)]}</>;
}

export function FoerdermittelKarte() {
  const { data } = useFetch<Antwort>("/council/budget/grants-received");
  const [geber, setGeber] = useState<Geber>("alle");
  const [alleZeigen, setAlleZeigen] = useState(false);
  const [alleAntraege, setAlleAntraege] = useState(false);

  const zeilen = useMemo(
    () => (data?.rows ?? []).filter((z) =>
      geber === "alle" || (geber === "eu") === (z.funder === "EU")),
    [data, geber]);
  if (!data || data.rows.length === 0) return null;

  const summe = (g: string) => data.totals.find((t) => t.group === g);
  const eu = summe("eu");
  const bund = summe("bund");
  const zeigen = alleZeigen ? zeilen : zeilen.slice(0, SICHTBAR);
  const euStand = data.lists
    .filter((l) => l.source !== "foekat" && l.list_as_of)
    .map((l) => l.list_as_of as string)
    .sort()
    .at(-1);
  const gesellschaften = new Set(data.rows.map((z) => z.recipient_key).filter((k) => k !== "city")).size;

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="min-w-0 max-w-[76ch]">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Fördermittel von außen · Spielraum begrenzt
        </p>
        <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
          Was EU und Bund in einzelne Vorhaben der Stadt stecken<Beleg q="grants_received" />
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-foreground/90">
          Neben Steuern und Zuweisungen bekommt die Stadt Geld für bestimmte Vorhaben — aber nur,
          wenn sie sich bewirbt und den Zuschlag erhält. Den Rest trägt sie selbst. Die Listen der
          Geber führen {data.rows.length} solche Vorhaben der Stadt
          {gesellschaften > 0 && ` und von ${gesellschaften} ihrer Gesellschaften`}.
        </p>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2">
        {[{ g: "eu" as const, t: eu, label: "Von der EU (EFRE und ESF)" },
          { g: "bund" as const, t: bund, label: "Vom Bund (Förderkatalog)" }].map(({ g, t, label }) => t && (
          <div key={g} className="rounded-xl border border-border bg-background/60 p-3">
            <dt className="text-[12px] text-muted-foreground">{label}</dt>
            <dd className="mt-1 font-display text-[22px] font-bold leading-none tabular-nums text-foreground">
              {deMio(t.amount / 1e6)}
              <span className="ml-1 text-[13px] font-semibold text-muted-foreground">Mio.&nbsp;€</span>
            </dd>
            <dd className="mt-1 text-[11.5px] text-muted-foreground">
              bewilligt für {t.n} Vorhaben
            </dd>
          </div>
        ))}
      </dl>

      <div role="group" aria-label="Geber wählen" className="flex flex-wrap gap-1.5">
        {([["alle", "Alle"], ["eu", "EU"], ["bund", "Bund"]] as [Geber, string][]).map(([g, t]) => (
          <button key={g} type="button" aria-pressed={geber === g}
            onClick={() => { setGeber(g); setAlleZeigen(false); }}
            className={cn(
              "min-h-[32px] rounded-full border px-3 text-[12.5px] font-medium",
              geber === g ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:border-primary/40")}>
            {t}
          </button>
        ))}
      </div>

      <ZahlenTabelle spalten={[{ title: "Vorhaben" }, { title: "Laufzeit" }, { title: "Bewilligt", zahl: true }]}>
        {zeigen.map((z) => (
          <tr key={`${z.source}-${z.source_id}`}>
            <TextZelle>
              <span className="font-semibold text-foreground">{z.title}</span>
              <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted-foreground">
                {data.recipients[z.recipient_key] ?? z.recipient} · {geberText(z)}
              </span>
              {z.templates.length > 0 && (
                <span className="mt-1 block text-[11.5px] leading-relaxed text-muted-foreground">
                  Im Rat:{" "}
                  {z.templates.map((v, i) => (
                    <span key={v.template_number}>
                      {i > 0 && " · "}
                      <VorlageLink v={v} /> {v.title.replace(/\s[-–]\s*(Bericht|Beschluss)\s*-?$/, "")}
                    </span>
                  ))}
                </span>
              )}
            </TextZelle>
            <TextZelle className="whitespace-nowrap font-mono text-[11.5px] text-muted-foreground">
              {jahr(z.start)}–{jahr(z.end)}
            </TextZelle>
            <BetragZelle euro={z.amount_granted} label="Bewilligt" text={euro(z.amount_granted)}
              className="font-medium text-foreground dark:text-foreground" />
          </tr>
        ))}
      </ZahlenTabelle>
      {zeilen.length > SICHTBAR && (
        <button type="button" onClick={() => setAlleZeigen((o) => !o)}
          className="w-fit text-[12.5px] font-semibold text-primary">
          {alleZeigen ? "Weniger zeigen" : `Alle ${zeilen.length} Vorhaben zeigen`}
        </button>
      )}

      {data.applications.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <h3 className="text-[14px] font-semibold text-foreground">Beantragt laut Rat</h3>
          <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
            {data.applications.length} Vorlagen, mit denen die Stadt Fördergeld beantragt oder sich um
            ein Programm bewirbt. Ein Antrag ist keine Zusage — und die meisten Programme hier
            (etwa die Sanierung von Sportstätten) stehen in keiner der beiden Listen oben.
          </p>
          <ul className="flex flex-col divide-y divide-border">
            {(alleAntraege ? data.applications : data.applications.slice(0, ANTRAEGE_SICHTBAR)).map((v) => (
              <li key={v.template_number} className="py-2">
                <span className="block text-[13px] font-medium leading-snug text-foreground">{v.title}</span>
                <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
                  <VorlageLink v={v} />{v.date && <> · <Beratung v={v} /></>}
                </span>
              </li>
            ))}
          </ul>
          {data.applications.length > ANTRAEGE_SICHTBAR && (
            <button type="button" onClick={() => setAlleAntraege((o) => !o)}
              className="w-fit text-[12.5px] font-semibold text-primary">
              {alleAntraege ? "Weniger zeigen" : `Alle ${data.applications.length} Anträge zeigen`}
            </button>
          )}
        </div>
      )}

      <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Bewilligt heißt zugesagt, nicht ausgezahlt. Die EU-Beträge sind der Unionsbeitrag aus der
        Liste der Vorhaben{euStand ? ` (Stand ${datum(euStand)})` : ""}, die Bundesbeträge der
        Bundesanteil laut Förderkatalog. Was hier fehlt: die Städtebauförderung und reine
        Landesprogramme — sie stehen in keiner der beiden Listen. Gezählt sind nur die Stadt und
        ihre Gesellschaften, nicht Vereine oder Unternehmen in Oldenburg. „Im Rat“ steht an
        einem Vorhaben nur, wenn eine Vorlage es erkennbar meint: Betrag und Name stehen im Text,
        oder ihr Titel steht im Titel des Vorhabens.
      </p>
    </section>
  );
}
