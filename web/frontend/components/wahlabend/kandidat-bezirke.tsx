"use client";

// Eine Kandidatur, aufgefaltet in ihre Wahlbezirke.
//
// Tims Frage vom 15.09.2026: „wenn ich Personen nach Wahlbezirk filtern kann,
// dann ist doch jeder Person auch Stimmen in dem Bezirk zugeordnet oder
// nicht?" — Ja. Jede Kandidatur hat Stimmen in JEDEM Wahlbezirk ihres
// Wahlbereichs, 15 bis 24 Zahlen. Eine Spalte könnte davon keine zeigen;
// diese Tafel zeigt alle.
//
// Zwei Prozentwerte, weil sie zwei verschiedene Fragen beantworten:
//   • „von 1.598"    — wo kam ihr Ergebnis her? 71 von 1.598 = 4 %; die
//                      Spalte summiert sich auf 100 %.
//   • „von SPD hier" — wie viele der SPD-Stimmen in DIESEM Lokal gingen an
//                      sie persönlich?
// Tims Einwand 15.09.: „davon" und „der Liste" verstand niemand, und die
// Hover-Erklärungen waren kompliziert. Deshalb stehen jetzt die Bezugsgrößen
// selbst in der Überschrift, und jeder Tooltip ist ein Satz mit den Zahlen
// dieser Zeile statt einer Definition.
// Geholt wird erst beim Aufklappen (`enabled`), nicht für 383 Zeilen auf Vorrat.
//
// Die Abfrage lebt im Hook, die Tafel bekommt fertige Daten: Die ZEILE
// braucht den Ladezustand (Spinner statt Pfeil, Aufklappen erst, wenn die
// Zahlen da sind — sonst fährt der Bereich auf Spinner-Höhe auf und springt
// beim Eintreffen ein zweites Mal; dasselbe Muster wie die Tagesordnung im
// Sitzungen-Reiter).

import { useQuery } from "@tanstack/react-query";
import { KICKER } from "@/components/wahlabend/bausteine";
import { api } from "@/lib/api";
import { kandidatPfad, prozent, zahl, type KandidatDetail } from "@/lib/wahlabend";

export function useKandidatBezirke({ party, area, position, probe, counted, rueckblick, offen }: {
  party: string;
  area: number;
  position: number;
  probe: string | null;
  counted: string | null;
  rueckblick: string | null;
  offen: boolean;
}) {
  const pfad = kandidatPfad(probe, counted, rueckblick, party, area, position);
  return useQuery({
    queryKey: ["wahlabend-kandidat", pfad],
    queryFn: () => api.get<KandidatDetail>(pfad),
    enabled: offen,
    staleTime: rueckblick ? Infinity : 30_000,
  });
}

/** Die Tafel — ohne eigenen Rahmen; den gibt der Drawer, in dem sie steht. */
export function KandidatBezirke({ detail, fehler }: { detail: KandidatDetail | undefined; fehler: boolean }) {
  if (fehler) {
    return <p className="py-2 text-[12.5px] text-muted-foreground">Die Wahlbezirke ließen sich gerade nicht laden.</p>;
  }
  if (!detail) return null;

  const mit = detail.districts.filter((b) => b.votes !== null);
  const max = Math.max(0, ...mit.map((b) => b.votes ?? 0));
  const gezaehlt = detail.districts.filter((b) => b.counted).length;

  return (
    <div>
      <p className={KICKER}>Wo die Stimmen herkamen</p>
      <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">
        {zahl(detail.votes)} Personenstimmen aus {zahl(detail.districts.length)} Wahlbezirken des Wahlbereichs{" "}
        {detail.area_roman} · {detail.area_name}
        {gezaehlt < detail.districts.length ? ` — ${zahl(gezaehlt)} davon ausgezählt` : ""}. Stärkster zuerst.
      </p>
      {/* Die Spaltenköpfe stehen einmal oben statt 21-mal in der Zeile —
          auf dem Handy passte „7,3 % ihrer Stimmen" sonst neben keinen
          Namen mehr. */}
      <div aria-hidden className="mt-3 flex items-center gap-2.5 border-b border-border/60 pb-1 font-mono text-[9.5px] uppercase tracking-[0.11em] text-muted-foreground">
        <span className="min-w-0 flex-1">Wahlbezirk</span>
        <span className="w-14 flex-none text-right">Stimmen</span>
        {/* Die Bezugsgröße steht in der Überschrift: „von 1.598" heißt, die
            Prozentzahl misst an den Gesamtstimmen dieser Kandidatur. */}
        <span className="w-[4.5rem] flex-none text-right" title={`Anteil an allen ${zahl(detail.votes)} Personenstimmen dieser Kandidatur`}>von {zahl(detail.votes)}</span>
        <span className="hidden w-24 flex-none text-right sm:block" title={`Anteil an allen ${detail.party_short}-Stimmen im jeweiligen Wahlbezirk`}>von {detail.party_short} hier</span>
      </div>
      <ol className="divide-y divide-border/60">
        {detail.districts.map((b) => (
          <li key={b.number} className="flex items-center gap-2.5 py-1.5">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[12.5px] font-medium">
                {b.name}
                {/* Die Bezirksnamen der Briefwahl heißen schon so — der
                    Zusatz steht nur da, wo er etwas hinzufügt. */}
                {b.postal && !/briefwahl/i.test(b.name) ? (
                  <span className="ml-1 text-[11px] font-normal text-muted-foreground">Briefwahl</span>
                ) : null}
              </span>
              <span aria-hidden className="mt-1 block h-1 w-full overflow-hidden rounded-full bg-foreground/10">
                <span
                  className="block h-full rounded-full bg-foreground/35"
                  style={{ width: max > 0 && b.votes ? `${Math.max(1.5, (100 * b.votes) / max)}%` : "0%" }}
                />
              </span>
            </span>
            <span className="w-14 flex-none text-right text-[12.5px] font-semibold tabular-nums">{zahl(b.votes)}</span>
            <span
              className="w-[4.5rem] flex-none text-right text-[11px] text-muted-foreground tabular-nums"
              title={b.votes === null ? undefined
                : `${zahl(b.votes)} von ${zahl(detail.votes)} Personenstimmen kamen aus diesem Wahlbezirk — ${prozent(b.share_pct)}`}
            >
              {prozent(b.share_pct)}
            </span>
            <span
              className="hidden w-24 flex-none text-right text-[11px] text-muted-foreground tabular-nums sm:block"
              title={b.party_share_pct === null ? undefined
                : `Hier gingen ${prozent(b.party_share_pct)} aller ${detail.party_short}-Stimmen an diese Kandidatur`}
            >
              {prozent(b.party_share_pct)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
