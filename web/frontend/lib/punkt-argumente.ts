/* Argumente und Fraktionen auf der Punkt-Seite (Schalter `punkt-argumente`,
   Plan `docs/plan-punkt-argumente.md`). Was hier steht, formt Text und
   Adressen; die Seite `app/(app)/council/punkt/` zeichnet nur.

   Urheber, Gremium und Datum kommen aus der Quelle (Server), nicht vom
   Modell — hier wird nur zusammengesetzt. */

import type { ApiAntwort } from "@/lib/vertrag";

type Detail = ApiAntwort<"/council/session/{ksinr}/item">;
export type ItemArguments = NonNullable<Detail["arguments"]>;
export type Statement = ItemArguments["further"]["pro"][number];
export type Issue = ItemArguments["issues"][number];

function datum(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

/** „Ratsherr Niederstein (Grüne) · Verkehrsausschuss · 23.06.2025" — ohne
 *  Person bei der Vorlage („Verwaltung · Vorlage 25/0397"). */
export function attribution(a: Statement, { party = true }: { party?: boolean } = {}): string {
  const wer = a.speaker ?? (a.source.kind === "template" ? "Verwaltung" : null);
  const teile = [
    wer ? `${wer}${party && a.party ? ` (${a.party})` : ""}` : (party && a.party) || null,
    a.body,
    a.date ? datum(a.date) : null,
  ].filter((x): x is string => !!x);
  return teile.join(" · ");
}

/** Wie die Fundstelle heißt: „Protokoll, S. 4", „Protokoll", „im Ratsinfo"
 *  (die Vorlage steht schon in der Zeile davor). */
export function sourceLabel(a: Statement): string {
  if (a.source.kind === "template") return "im Ratsinfo";
  return a.source.page ? `Protokoll, S. ${a.source.page}` : "Protokoll";
}

/** „7 dafür · 9 dagegen oder mit Bedenken" */
export function countLine(args: ItemArguments): string {
  return `${args.pro_count} dafür · ${args.contra_count} dagegen oder mit Bedenken`;
}

/** Woraus die Argumente stammen: „aus 12 Wortbeiträgen und der Vorlage". */
export function basisLine(args: ItemArguments): string {
  const alle = [...args.issues.flatMap((i) => [...i.pro, ...i.contra]), ...args.further.pro, ...args.further.contra];
  const reden = new Set(alle.filter((a) => a.source.kind === "speech").map((a) => a.source.id)).size;
  const vorlage = alle.some((a) => a.source.kind === "template");
  const teile = [
    reden ? `${reden} ${reden === 1 ? "Wortbeitrag" : "Wortbeiträgen"}` : null,
    vorlage ? "der Vorlage" : null,
  ].filter(Boolean);
  return teile.length ? `aus ${teile.join(" und ")}` : "";
}

/** Mit Bezug-Chip ins Ratsgespräch: die Frage des Streitpunkts, der Punkt als
 *  Gegenstand, der Streitpunkt selbst als Baustein (`element_title`/`_text`).
 *  Der Text bleibt kurz — er reist in der Adresse. */
export function askHref(ksinr: number, itemNumber: string, issue: Issue): string {
  const zeile = (seite: string, xs: Statement[]) =>
    xs.length ? `${seite}: ${xs.map((a) => a.text).join(" ")}` : "";
  const text = [zeile("Dafür", issue.pro), zeile("Dagegen", issue.contra)].filter(Boolean).join(" ").slice(0, 600);
  const q = new URLSearchParams({
    q: issue.question, chip: "1", ksinr: String(ksinr), top: itemNumber,
    streit: issue.question.slice(0, 200), streit_text: text,
  });
  return `/fragen?${q.toString()}`;
}
