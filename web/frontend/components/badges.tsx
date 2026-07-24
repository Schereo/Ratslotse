"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3, Bell, CalendarDays, Compass, Map as MapIcon, Sparkles, Tags, Trophy, X,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";
import { ONBOARDING_DONE_EVENT, isOnboardingVisible } from "@/components/onboarding-flow";

/**
 * RL-U12 (Design 10a/11a/27a): Lotsen-Abzeichen — Sammeln fürs ERKUNDEN, nie
 * Konsumzwang: kein Ranking, keine Verlust-Serien, einmal verdient bleibt
 * verdient. Ereignisse melden die jeweiligen Screens über reportBadgeEvent();
 * das Verdienen erkennt der Server und liefert es einmalig als newly_earned.
 *
 * Daraus macht der BadgeCelebrator einen eigenen Marken-Moment (27a): eine
 * Karte, die unten über den laufenden Screen fährt — bewusst *kein* Vollbild,
 * sie blockiert nichts und geht nach 6 s von selbst. In der Sammlung trägt das
 * frische Abzeichen danach ein „NEU", bis es einmal angesehen wurde.
 */

type Badge = {
  id: string;
  title: string;
  hint: string;
  earned: boolean;
  progress: { current: number; target: number } | null;
};
type BadgesResponse = {
  badges: Badge[];
  earned_count: number;
  total: number;
  next: { id: string; title: string; hint: string } | null;
  newly_earned: { id: string; title: string }[];
};

const ICONS: Record<string, LucideIcon> = {
  "erste-frage": Sparkles,
  "themen-lotse": Tags,
  "quiz-serie": Trophy,
  kartograf: MapIcon,
  analyst: BarChart3,
  sitzungsgast: CalendarDays,
  fruehwarner: Bell,
  kompass: Compass,
};

const DIRTY_EVENT = "ratslotse:badges-dirty";
/** Frisch verdiente Abzeichen bis zum ersten Blick in die Sammlung (27a). */
const NEW_KEY = "ratslotse:badges-neu";
const CELEBRATION_MS = 6000;

/** Gold wie die Medaille auf der Feier-Karte — verbindet Feier und Sammlung. */
const MEDAL_GRADIENT = "linear-gradient(160deg, #FDE9B8, #F2B441 55%, #D9861F)";
const CARD_GRADIENT = "linear-gradient(160deg, hsl(213 60% 11%), hsl(210 52% 19%))";
/** Wellen-Textur in Weiß — die globale .bg-waves ist fürs helle Theme gedacht
 *  und auf dem dunklen Karten-Verlauf unsichtbar. */
const WAVES =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='24' viewBox='0 0 120 24'%3E%3Cpath d='M0 12c10-8 20-8 30 0s20 8 30 0 20-8 30 0 20 8 30 0' fill='none' stroke='%23ffffff' stroke-opacity='0.10' stroke-width='2'/%3E%3C/svg%3E\")";
const SPARKS = ["#F2B441", "#f66623", "#3db1f5", "#FDE9B8"];

function readNewIds(): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(NEW_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}
function markNewIds(ids: string[]) {
  try {
    window.localStorage.setItem(NEW_KEY, JSON.stringify([...new Set([...readNewIds(), ...ids])]));
  } catch {
    /* Privater Modus o. Ä. — das „NEU" ist Kür, nie Voraussetzung. */
  }
}
function clearNewIds() {
  try {
    window.localStorage.removeItem(NEW_KEY);
  } catch {
    /* s. o. */
  }
}

/** Ereignis melden (fire-and-forget) — Fehler stören den eigentlichen Flow nie. */
export function reportBadgeEvent(type: "frage" | "sitzung" | "tour" | "map_place", key?: string) {
  api
    .post("/badges/event", { type, key })
    .then(() => window.dispatchEvent(new Event(DIRTY_EVENT)))
    .catch(() => {});
}

function useBadges() {
  return useQuery({
    queryKey: ["badges"],
    queryFn: () => api.get<BadgesResponse>("/badges"),
    staleTime: 60_000,
  });
}

/** Erst nach dem Mount abfragen — sonst weicht der Server-Render ab. */
function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(true);
  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);
  return reduced;
}

/** Global im App-Layout: feiert neu verdiente Abzeichen — überall. */
export function BadgeCelebrator() {
  const qc = useQueryClient();
  const { data } = useBadges();
  const [queue, setQueue] = useState<{ id: string; title: string }[]>([]);
  const shown = useRef(new Set<string>());

  useEffect(() => {
    const onDirty = () => qc.invalidateQueries({ queryKey: ["badges"] });
    window.addEventListener(DIRTY_EVENT, onDirty);
    return () => window.removeEventListener(DIRTY_EVENT, onDirty);
  }, [qc]);

  // Während des Onboardings (26a) nicht dazwischenfunken: Das Anmelden
  // registriert den Push-Token und verdient damit sofort „Frühwarner" — die
  // Feier landete quer über dem Willkommens-Gruß, bevor man etwas getan hatte.
  // Nur aufschieben, nicht verschlucken: Der Server liefert `newly_earned`
  // genau EINMAL (danach gilt das Abzeichen als bekannt), also parken wir es
  // und feiern, sobald der Flow durch ist.
  const [pending, setPending] = useState<{ id: string; title: string }[]>([]);

  useEffect(() => {
    const fresh = (data?.newly_earned ?? []).filter((b) => !shown.current.has(b.id));
    if (!fresh.length) return;
    fresh.forEach((b) => shown.current.add(b.id));
    // Das „NEU" in der Sammlung schon jetzt setzen, auch wenn die Feier noch
    // wartet — es hängt am Verdienen, nicht am Zusehen.
    markNewIds(fresh.map((b) => b.id));
    setPending((p) => [...p, ...fresh]);
  }, [data]);

  useEffect(() => {
    const flush = () => {
      if (isOnboardingVisible()) return;
      setPending((p) => {
        if (!p.length) return p;
        // Mehrere auf einmal laufen NACHEINANDER durch die Warteschlange.
        // Gestapelt (wie früher die Toasts) las man keine einzige zu Ende;
        // jede Karte geht nach 6 s von selbst, „Weiter" überspringt sofort.
        setQueue((q) => [...q, ...p]);
        return [];
      });
    };
    flush();
    window.addEventListener(ONBOARDING_DONE_EVENT, flush);
    return () => window.removeEventListener(ONBOARDING_DONE_EVENT, flush);
  }, [pending]);

  const dismiss = useCallback(() => setQueue((q) => q.slice(1)), []);

  const current = queue[0];
  if (!current || !data) return null;
  return (
    <BadgeCelebration
      key={current.id}
      badge={current}
      hint={data.badges.find((b) => b.id === current.id)?.hint ?? ""}
      earnedCount={data.earned_count}
      total={data.total}
      onClose={dismiss}
    />
  );
}

/** Die Feier-Karte selbst (27a ①). */
function BadgeCelebration({
  badge,
  hint,
  earnedCount,
  total,
  onClose,
}: {
  badge: { id: string; title: string };
  hint: string;
  earnedCount: number;
  total: number;
  onClose: () => void;
}) {
  const Icon = ICONS[badge.id] ?? Sparkles;
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const t = setTimeout(onClose, CELEBRATION_MS);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "animate-badge-card-in fixed inset-x-3.5 z-[90] mx-auto max-w-[26rem]",
        // Über der Bottom-Nav bleiben (mobil, ~68 px hoch), sonst am unteren Rand.
        "bottom-[calc(5.25rem+env(safe-area-inset-bottom))] md:bottom-[calc(1.125rem+env(safe-area-inset-bottom))]",
      )}
    >
      <div
        className="relative overflow-hidden rounded-[20px] p-4 shadow-[0_18px_44px_-16px_rgba(2,20,45,0.7)]"
        style={{ backgroundImage: CARD_GRADIENT }}
      >
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{ backgroundImage: WAVES }}
        />
        {!reduced && (
          <span aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            {SPARKS.map((color, i) => (
              <span
                key={i}
                className="animate-badge-spark absolute block rounded-[1px]"
                style={{
                  left: `${18 + i * 21}%`,
                  top: 0,
                  width: 5 + (i % 2) * 2,
                  height: 9 + (i % 3) * 2,
                  backgroundColor: color,
                  animationDelay: `${i * 0.16}s`,
                }}
              />
            ))}
          </span>
        )}

        <button
          type="button"
          onClick={onClose}
          aria-label="Feier schließen"
          className="absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-full text-white/55 transition-colors hover:bg-white/10 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="relative flex items-center gap-3.5 pr-8">
          <span
            className="grid h-16 w-16 shrink-0 animate-bob place-items-center rounded-full border-[3px] border-white text-[hsl(28_75%_20%)] shadow-[0_6px_16px_-6px_rgba(0,0,0,0.6)]"
            style={{ backgroundImage: MEDAL_GRADIENT }}
          >
            <Icon className="h-7 w-7" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[9.5px] font-bold uppercase tracking-[0.16em] text-[hsl(19_92%_60%)]">
              Abzeichen freigeschaltet
            </p>
            <p className="mt-1 font-display text-xl font-extrabold leading-tight text-white">
              {badge.title}
            </p>
            <p className="mt-0.5 text-xs leading-snug text-white/70">
              {/* Der Hint endet als Aufforderung auf „.“ — vor dem Mittelpunkt weg. */}
              {hint ? `${hint.replace(/\.$/, "")} · ` : ""}
              <span className="tabular-nums">
                {earnedCount} / {total}
              </span>{" "}
              gesammelt
            </p>
          </div>
        </div>

        <div className="relative mt-3.5 flex items-center gap-2">
          <Link
            href="/account#abzeichen"
            onClick={onClose}
            className="flex h-[42px] flex-1 items-center justify-center rounded-xl bg-[hsl(19_92%_52%)] text-sm font-semibold text-white transition-colors hover:bg-[hsl(19_92%_46%)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
          >
            Sammlung ansehen
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="h-[42px] rounded-xl px-4 text-sm font-semibold text-white/75 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
          >
            Weiter
          </button>
        </div>
      </div>
    </div>
  );
}

/** Konto-Karte „Deine Lotsen-Abzeichen" (11a ④, Neu-Zustand aus 27a ④). */
export function BadgesCard() {
  const { data } = useBadges();
  const [freshIds, setFreshIds] = useState<string[]>([]);
  const jumped = useRef(false);

  useEffect(() => {
    // Der Snapshot bleibt für diesen Besuch stehen, der Speicher wird sofort
    // geleert: „NEU" markiert genau bis zum ersten Ansehen.
    setFreshIds(readNewIds());
    const t = setTimeout(clearNewIds, 1500);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    // „Sammlung ansehen" springt auf /account#abzeichen. Die Karte hängt am
    // Datenabruf und existiert beim Hash-Sprung des Browsers noch nicht —
    // also selbst scrollen, sobald sie da ist.
    if (!data || jumped.current || window.location.hash !== "#abzeichen") return;
    jumped.current = true;
    document.getElementById("abzeichen")?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [data]);

  if (!data) return null;
  return (
    <Card id="abzeichen" className="scroll-mt-24 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-foreground">Deine Lotsen-Abzeichen</h2>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-bold tabular-nums text-primary">
          {data.earned_count}/{data.total}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-4 gap-2.5">
        {data.badges.map((b) => {
          const Icon = ICONS[b.id] ?? Sparkles;
          const isNew = b.earned && freshIds.includes(b.id);
          return (
            <div
              key={b.id}
              title={b.earned ? b.title : `${b.title} — ${b.hint}`}
              className={cn(
                "relative flex flex-col items-center gap-1.5 rounded-xl border p-2 text-center",
                b.earned ? "border-primary/25 bg-primary/[0.06]" : "border-border opacity-45",
                isNew &&
                  "border-signal/40 bg-signal/[0.08] shadow-[0_0_0_4px_hsl(var(--signal)/0.25)]",
              )}
            >
              {isNew && (
                <span className="absolute -right-1 -top-1 rounded-full bg-signal px-1.5 py-px text-[8px] font-bold uppercase leading-[1.5] tracking-wide text-signal-foreground">
                  Neu
                </span>
              )}
              <span
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full",
                  isNew
                    ? "border border-white/70 text-[hsl(28_75%_20%)]"
                    : b.earned
                      ? "bg-primary/15 text-primary"
                      : "bg-muted text-muted-foreground",
                )}
                style={isNew ? { backgroundImage: MEDAL_GRADIENT } : undefined}
              >
                <Icon className="h-4.5 w-4.5" />
              </span>
              <span
                className={cn(
                  "text-[10px] leading-tight",
                  isNew ? "font-bold text-signal" : "font-medium text-foreground",
                )}
              >
                {b.title}
                {b.progress && !b.earned && (
                  <span className="block tabular-nums text-muted-foreground">
                    {b.progress.current}/{b.progress.target}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {data.next && (
        <p className="mt-3 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Als Nächstes: {data.next.title}</span>
          {" "}— {data.next.hint}
        </p>
      )}
    </Card>
  );
}
