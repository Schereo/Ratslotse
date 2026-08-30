import * as React from "react";
import { cn } from "@/lib/utils";
import { RefreshCw } from "lucide-react";
import { Mascot, type MascotPose } from "@/components/mascot";
import { Button } from "./button";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-border bg-card text-card-foreground shadow-sm", className)} {...props} />;
}

type BadgeColor = "slate" | "blue" | "green" | "amber" | "red";

export function Badge({ children, color = "slate", className }: { children: React.ReactNode; color?: BadgeColor; className?: string }) {
  const colors: Record<BadgeColor, string> = {
    slate: "bg-muted text-muted-foreground",
    blue: "bg-primary/10 text-primary",
    green: "bg-green-100 text-green-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-destructive/10 text-destructive",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", colors[color], className)}>
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center p-8", className)}>
      {/* 600 ms statt 1 s Umdrehung: ein schnellerer Spinner lässt dieselbe
          Ladezeit kürzer wirken (wahrgenommene Performance). */}
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-primary [animation-duration:600ms]" />
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  icon: Icon,
  mascot,
  action,
}: {
  title: string;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  /** Lotti statt Icon zeigen — Pose passend zum Kontext (search/sleep/confused/…). */
  mascot?: MascotPose;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-border bg-card px-6 py-12 text-center">
      {mascot ? (
        <Mascot pose={mascot} className="mb-3 h-24 w-24" />
      ) : (
        Icon && (
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Icon className="h-6 w-6" />
          </span>
        )
      )}
      <p className="font-medium text-foreground">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Fehlgeschlagene Abfrage — mit Knopf statt Bitte (Design 29a, P4).
 *
 *  Vorher endeten Ladefehler als roter Satz „… Bitte Seite neu laden." — die
 *  Bitte an die Nutzer*in, unsere Arbeit zu machen. Ein Funkloch in der Bahn
 *  reichte, und die Seite blieb kaputt, bis jemand den Browser bemühte. Dabei
 *  liegt `refetch()` in jeder dieser Abfragen bereit: Ein Tipp genügt, der Rest
 *  der Seite bleibt stehen.
 *
 *  Gleiche Bauform wie {@link EmptyState}, nur Lotti ratlos statt schlafend.
 */
export function ErrorState({
  title = "Das hat nicht geklappt",
  hint = "Sieht nach einem Verbindungsproblem aus.",
  onRetry,
  busy,
}: {
  title?: string;
  hint?: string;
  onRetry?: () => void;
  /** Läuft der neue Versuch gerade? Beschriftet den Knopf um. */
  busy?: boolean;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center rounded-xl border border-dashed border-border bg-card px-6 py-12 text-center"
    >
      {/* `schuettelt-kopf` ist die gebackene Fehler-Regung — „das ging schief". */}
      <Mascot regung="schuettelt-kopf" className="mb-3 h-24 w-24" />
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{hint}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} disabled={busy} className="mt-4">
          <RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} />
          {busy ? "Wird geladen…" : "Nochmal versuchen"}
        </Button>
      )}
    </div>
  );
}
