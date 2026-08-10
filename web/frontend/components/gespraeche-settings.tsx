"use client";

import { useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { Button, Card, toast } from "@/components/ui";
import { apiUrl, authHeaders } from "@/lib/api";

/** Konto-Einstellung „Gespräche speichern" (Design 6a②): beidseitig änderbar
 *  zur Erstnutzungs-Frage im Ratsgespräch. Der Ausschalt-Dialog entscheidet
 *  getrennt, was mit bestehenden Gesprächen passiert — Schalter und Daten
 *  sind bewusst zwei Handlungen. */
export function GespraecheCard() {
  const [einstellung, setEinstellung] = useState<number | null | undefined>(undefined);
  const [anzahl, setAnzahl] = useState(0);
  const [frageLoeschen, setFrageLoeschen] = useState(false);

  useEffect(() => {
    fetch(apiUrl("/council/gespraeche"), { credentials: "include", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => {
        if (!b) return;
        setEinstellung(b.einstellung);
        setAnzahl((b.gespraeche ?? []).length);
      })
      .catch(() => {});
  }, []);

  const setzen = async (an: boolean) => {
    const vorher = einstellung;
    setEinstellung(an ? 1 : 0);
    setFrageLoeschen(!an && anzahl > 0);
    try {
      const r = await fetch(apiUrl("/council/gespraeche/einstellung"), {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ an }),
      });
      if (!r.ok) throw new Error();
    } catch {
      // Gerade bei diesem Datenschutz-Schalter darf die Anzeige nicht vom
      // Server abweichen — Zustand zurückrollen (Befund F13).
      setEinstellung(vorher);
      setFrageLoeschen(false);
      toast.error("Einstellung konnte nicht gespeichert werden.");
    }
  };

  const alleLoeschen = async () => {
    try {
      const r = await fetch(apiUrl("/council/gespraeche"), {
        method: "DELETE", credentials: "include", headers: authHeaders(),
      });
      if (!r.ok) throw new Error();
      setAnzahl(0);
      setFrageLoeschen(false);
      toast.success("Alle gespeicherten Gespräche gelöscht.");
    } catch {
      toast.error("Löschen fehlgeschlagen.");
    }
  };

  return (
    <Card className="p-6">
      <h2 className="flex items-center gap-2 font-semibold text-foreground">
        <MessagesSquare className="h-4 w-4 text-primary" aria-hidden />
        Gespräche
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Deine „Frag den Rat"-Verläufe liegen in deinem Konto und stehen auf allen
        Geräten unter „Gespräche".
      </p>

      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-foreground">Gespräche speichern</span>
        <div className="flex gap-1 rounded-full border border-border p-0.5">
          <button type="button" onClick={() => void setzen(true)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${einstellung === 1 ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
            An
          </button>
          <button type="button" onClick={() => void setzen(false)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${einstellung === 0 ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
            Aus
          </button>
        </div>
      </div>
      {einstellung === null && (
        <p className="mt-2 text-xs text-muted-foreground/80">
          Noch nicht entschieden — Lotti fragt dich beim nächsten Ratsgespräch.
        </p>
      )}

      {/* 6a②: Ausschalt-Dialog — neue Gespräche werden nicht mehr gespeichert,
          was mit den bestehenden passiert, entscheidet diese Frage. */}
      {frageLoeschen ? (
        <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
          <p className="text-sm font-medium text-foreground">Speichern ist aus.</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Was soll mit deinen {anzahl} gespeicherten Gesprächen passieren?
          </p>
          <div className="mt-2.5 flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setFrageLoeschen(false)}>Behalten</Button>
            <Button size="sm" variant="danger" onClick={() => void alleLoeschen()}>Alle löschen</Button>
          </div>
        </div>
      ) : anzahl > 0 ? (
        <button type="button" onClick={() => void alleLoeschen()}
          className="mt-4 text-xs font-medium text-destructive hover:underline">
          Alle gespeicherten Gespräche löschen ({anzahl})
        </button>
      ) : null}
    </Card>
  );
}
