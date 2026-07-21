"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Mascot } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { cn } from "@/lib/utils";

type Pause = {
  active: boolean;
  label: string | null;
  until: string | null;              // letzter Pausentag (ISO)
  next_session_date: string | null;  // nächste veröffentlichte Sitzung (ISO)
  note: string;
};

const fmtShort = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "short" });

/** Sitzungspause-Hinweis (RL-402, Design 2a): ruhige Verlaufs-Fläche mit
 *  Wellen-Textur, schlafender Lotti (Saison-Outfit automatisch) und rechts
 *  einer „WIEDER AB"-Kachel. `compact` = einzeilige Variante für die
 *  Sitzungen-Seite und mobile Ansichten. Erscheint nur bei aktiver Pause;
 *  API und Felder unverändert (/council/sitzungspause). */
export function SitzungspauseBanner({ className, compact = false }: { className?: string; compact?: boolean }) {
  const theme = useMascotTheme();
  const { data } = useQuery({
    queryKey: ["sitzungspause"],
    queryFn: () => api.get<Pause>("/council/sitzungspause"),
    staleTime: 60 * 60 * 1000, // ändert sich höchstens täglich
  });

  if (!data?.active) return null;

  // Kachel rechts: bekannter Folgetermin gewinnt; sonst das Ferien-Ende.
  // Ohne beides („Keine Termine veröffentlicht") trägt der Text allein.
  const kachel = data.next_session_date
    ? { kicker: "Wieder ab", value: fmtShort(data.next_session_date) }
    : data.until
      ? { kicker: "Pause", value: `bis ${fmtShort(data.until)}` }
      : null;

  if (compact) {
    return (
      <div
        role="status"
        className={cn(
          "bg-waves flex items-center gap-3 rounded-xl border border-border bg-gradient-to-r from-[#eaf5fd] to-background p-3 dark:from-muted/40 dark:to-card",
          className,
        )}
      >
        <Mascot pose="sleep" theme={theme} decorative className="h-10 w-10 shrink-0" />
        <p className="min-w-0 flex-1 text-sm text-foreground">
          <span className="font-display font-bold">{data.label}</span>
          {kachel && (
            <span className="text-muted-foreground">
              {" · "}{kachel.kicker === "Wieder ab" ? `wieder ab ${kachel.value}` : kachel.value}
            </span>
          )}
        </p>
      </div>
    );
  }

  return (
    <div
      role="status"
      className={cn(
        "bg-waves flex flex-wrap items-center gap-4 rounded-2xl border border-border bg-gradient-to-r from-[#eaf5fd] to-background p-4 dark:from-muted/40 dark:to-card sm:p-5",
        className,
      )}
    >
      <Mascot pose="sleep" theme={theme} bob decorative className="h-16 w-16 shrink-0 sm:h-20 sm:w-20" />
      <div className="min-w-0 flex-1 basis-56">
        <p className="font-display text-lg font-bold text-foreground">{data.label}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">{data.note}</p>
      </div>
      {kachel && (
        <div className="shrink-0 rounded-xl border border-border bg-card px-4 py-2.5 text-center shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {kachel.kicker}
          </p>
          <p className="font-display text-lg font-bold text-foreground">{kachel.value}</p>
        </div>
      )}
    </div>
  );
}
