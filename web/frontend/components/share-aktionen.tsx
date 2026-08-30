"use client";

/**
 * Aktionsleiste unter einer geteilten Antwort (Task 31c): Eingeloggte springen
 * mit einem Klick ins Ratsgespräch und fragen zur geteilten Antwort weiter
 * (?share=<token> lädt sie dort als ersten Turn); wer kein Konto hat, bekommt
 * Registrieren/Anmelden — mit `?weiter=` direkt aufs Weiterfragen, damit das
 * Ziel den Login-Umweg überlebt. Client-Insel in der Server-Seite /g.
 */
import Link from "next/link";
import { useState } from "react";
import { Flag, MessageSquarePlus, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { mitRuecksprung } from "@/lib/public-routes";
import { apiUrl } from "@/lib/api";

export function ShareAktionen({ token }: { token: string }) {
  const { user, loading } = useAuth();
  const [reportOpen, setReportOpen] = useState(false);
  const [reportState, setReportState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  if (loading) return null;
  // Seit dem Split (12.08.) wohnen geteilte Antworten auf /fragen; alte
  // /council-Links leitet die Council-Seite mitsamt share-Token dorthin um.
  const ziel = `/fragen?share=${encodeURIComponent(token)}`;
  const report = async (reason: string) => {
    setReportState("sending");
    try {
      const response = await fetch(apiUrl(`/council/qa-share/${encodeURIComponent(token)}/report`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      if (!response.ok) throw new Error("report failed");
      setReportState("sent");
      setReportOpen(false);
    } catch {
      setReportState("error");
    }
  };

  const reportControl = (
    <div className="relative">
      <button type="button" onClick={() => setReportOpen((open) => !open)}
        disabled={reportState === "sending" || reportState === "sent"}
        className="inline-flex min-h-10 items-center gap-1.5 rounded-full px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-60">
        <Flag className="h-3.5 w-3.5" aria-hidden />
        {reportState === "sent" ? "Gemeldet – danke" : "Inhalt melden"}
      </button>
      {reportOpen && (
        <div className="absolute bottom-12 left-0 z-10 w-72 rounded-xl border border-border bg-card p-3 shadow-lg">
          <p className="text-xs font-semibold">Warum möchtest du den Inhalt melden?</p>
          <div className="mt-2 grid gap-1">
            {[
              ["inappropriate", "Unangemessener Inhalt"],
              ["misleading", "Irreführende oder falsche Antwort"],
              ["privacy", "Privatsphäre / persönliche Daten"],
              ["other", "Anderer Grund"],
            ].map(([reason, label]) => (
              <button key={reason} type="button" onClick={() => void report(reason)}
                className="rounded-lg px-2.5 py-2 text-left text-xs hover:bg-muted">
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      {reportState === "error" && (
        <p role="alert" className="mt-1 text-xs text-destructive">Meldung fehlgeschlagen. Bitte später erneut versuchen.</p>
      )}
    </div>
  );

  if (user) {
    return (
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <Link href={ziel}
          className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <MessageSquarePlus className="h-4 w-4" aria-hidden />
          Im Ratsgespräch weiterfragen
        </Link>
        {reportControl}
      </div>
    );
  }
  return (
    <div className="mt-6 rounded-2xl border border-primary/20 bg-primary/5 p-4">
      <p className="text-sm font-semibold">Selbst weiterfragen?</p>
      <p className="mt-0.5 text-[13px] leading-relaxed text-muted-foreground">
        Mit einem kostenlosen Konto kannst du an diese Antwort anknüpfen und dem
        Rat eigene Fragen stellen — mit Quellen zu jedem zitierten Beschluss.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href={mitRuecksprung("/register", ziel)}
          className="inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <Sparkles className="h-3.5 w-3.5" aria-hidden /> Kostenlos registrieren
        </Link>
        <Link href={mitRuecksprung("/login", ziel)}
          className="inline-flex items-center rounded-full border border-border bg-card px-4 py-1.5 text-sm font-medium transition-colors hover:bg-muted">
          Anmelden
        </Link>
        {reportControl}
      </div>
    </div>
  );
}
