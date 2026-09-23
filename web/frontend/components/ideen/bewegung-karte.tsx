"use client";

/**
 * Eine Bewegung als Karte: dieselbe Idee in mehreren anderen Räten.
 *
 * Aufbau von oben nach unten, wie man sie liest: Worum geht es (Kicker und
 * Titel), wer (die Städte), wann und wie ging es aus (Zeitleiste und
 * Zähler), und zuletzt die Frage, für die es die Seite gibt — und in
 * Oldenburg? Die Antwort steht hinter der Signal-Marke, einem 8-px-Quadrat:
 * Signal-Orange ist Akzent, nie Fläche (Designsprache § 2).
 */
import Link from "next/link";

import { POLICY_FIELD_LABELS } from "@/components/decision-ui";
import { Jahresskala, Zeitleiste } from "@/components/ideen/zeitleiste";
import { StandPille } from "@/components/ideen/stand";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { stufe } from "@/lib/zeitleiste";

type Bewegungen = ApiAntwort<"/council/cities/movements">;
export type Bewegung = Bewegungen["items"][number];
export type Achse = Bewegungen["axis"];

/** „Osnabrück, Münster, Potsdam und 3 weitere" — die Städte nach erstem Datum. */
export function staedteZeile(b: Bewegung, hoechstens = 4): string {
  const namen = b.cities.map((c) => c.city);
  if (namen.length <= hoechstens) {
    return namen.length === 1
      ? namen[0]
      : `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`;
  }
  return `${namen.slice(0, hoechstens).join(", ")} und ${namen.length - hoechstens} weitere`;
}

export function zeitraum(b: Pick<Bewegung, "first_date" | "last_date">): string {
  const von = b.first_date?.slice(0, 4);
  const bis = b.last_date?.slice(0, 4);
  if (!von || !bis) return "";
  return von === bis ? von : `${von}–${bis}`;
}

/** Wie viele Vorlagen wie ausgingen — die zwei Zahlen, die zählen. */
export function bilanz(b: Bewegung): string {
  let ok = 0;
  let nein = 0;
  for (const p of b.timeline) {
    const s = stufe(p.outcome);
    if (s === "ok") ok++;
    if (s === "no") nein++;
  }
  const teile = [`${b.members} ${b.members === 1 ? "Vorlage" : "Vorlagen"}`];
  if (ok) teile.push(`${ok} beschlossen`);
  if (nein) teile.push(`${nein} abgelehnt`);
  return teile.join(" · ");
}

export function BewegungKarte({
  bewegung: b,
  achse,
  href,
  gross = false,
}: {
  bewegung: Bewegung;
  achse: Achse;
  href: string;
  /** Auf der Tafel: größerer Titel, die Zahl der Städte als Großzahl. */
  gross?: boolean;
}) {
  const feld = b.field ? POLICY_FIELD_LABELS[b.field] ?? b.field : null;
  const kicker = [feld, zeitraum(b)].filter(Boolean).join(" · ");
  return (
    <Link
      href={href}
      className={cn(
        "group grid content-start gap-2.5 rounded-[14px] border border-border bg-card p-4 shadow-sm",
        "transition-[border-color,box-shadow,transform] duration-tipp hover:border-primary/30",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        gross && "hover:-translate-y-px hover:shadow-md",
      )}
    >
      {kicker && (
        <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.07em] text-muted-foreground">
          {kicker}
        </div>
      )}
      <h3
        className={cn(
          "font-display font-bold leading-tight text-foreground [text-wrap:balance] group-hover:text-primary",
          gross ? "text-lg" : "text-[17px]",
        )}
      >
        {b.label}
      </h3>
      {gross ? (
        <div className="flex items-baseline gap-2 text-sm text-muted-foreground">
          <span className="font-display text-[30px] font-bold leading-none tabular-nums text-primary">
            {b.cities.length}
          </span>
          <span>Städte: {staedteZeile(b, 3)}</span>
        </div>
      ) : (
        <p className="text-sm text-foreground/90">
          <span className="font-semibold">{b.cities.length} Städte:</span> {staedteZeile(b)}
        </p>
      )}
      <div>
        <Zeitleiste achse={achse} punkte={b.timeline} />
        <Jahresskala achse={achse} className="-mt-0.5" />
      </div>
      <p className="font-mono text-meta text-muted-foreground">{bilanz(b)}</p>
      <OldenburgZeile bewegung={b} />
    </Link>
  );
}

function OldenburgZeile({ bewegung: b }: { bewegung: Bewegung }) {
  const u = b.oldenburg;
  return (
    <div className="flex gap-2 border-t border-border/70 pt-2.5">
      <span aria-hidden className="mt-1.5 h-2 w-2 shrink-0 rounded-[2px] bg-signal" />
      <div className="min-w-0 space-y-1">
        {u ? (
          <>
            <StandPille status={u.status} />
            {u.situation && <p className="text-sm text-foreground/90">{u.situation}</p>}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Ob Oldenburg das schon hat, ist noch nicht geprüft.
          </p>
        )}
      </div>
    </div>
  );
}
