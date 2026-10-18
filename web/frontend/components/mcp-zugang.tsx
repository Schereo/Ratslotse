"use client";

/**
 * „Eigener Agent (MCP)" — persönliche Schlüssel für den MCP-Server.
 *
 * Nur sichtbar mit dem Recht `mcp` (Rolle „MCP-Zugang") und dem Schalter
 * `mcp-server`. Die Sperre selbst sitzt am Backend; diese Karte ist die
 * Höflichkeit davor.
 *
 * Das Geheimnis steht genau EINMAL hier — direkt nach dem Ausstellen, samt
 * fertiger Zeile für Claude Code. Danach kennt der Server nur noch den Hash,
 * und die Liste zeigt die ersten Zeichen zum Wiedererkennen.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Copy, KeyRound, Link2, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFeature } from "@/lib/features";
import { hatRecht } from "@/lib/rechte";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { Button, Card, ConfirmDialog, Input, Label, toast } from "@/components/ui";

type Schluessel = ApiAntwort<"/account/mcp-tokens", "get">["tokens"][number];
type Verbindung = ApiAntwort<"/account/mcp-grants", "get">["grants"][number];
type Ausgestellt = ApiAntwort<"/account/mcp-tokens", "post">;

const SCHLUESSEL = ["mcp-tokens"] as const;
const VERBINDUNGEN = ["mcp-grants"] as const;

function datum(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", { day: "numeric", month: "short", year: "numeric" });
}

async function kopieren(text: string, was: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(`${was} kopiert.`);
  } catch {
    toast.error(`${was} konnte nicht kopiert werden.`);
  }
}

export function McpCard() {
  const { user } = useAuth();
  const an = useFeature("mcp-server");
  if (!an || !hatRecht(user, "mcp")) return null;
  return <McpKarte />;
}

function McpKarte() {
  const qc = useQueryClient();
  const [label, setLabel] = useState("");
  const [neu, setNeu] = useState<Ausgestellt | null>(null);
  const [loeschen, setLoeschen] = useState<Schluessel | null>(null);
  const [trennen, setTrennen] = useState<Verbindung | null>(null);

  const liste = useQuery({ queryKey: SCHLUESSEL, queryFn: () => vertrag.get("/account/mcp-tokens") });
  const verbunden = useQuery({ queryKey: VERBINDUNGEN, queryFn: () => vertrag.get("/account/mcp-grants") });

  const verbindungTrennen = useMutation({
    mutationFn: (id: number) =>
      api.del<ApiAntwort<"/account/mcp-grants/{grant_id}", "delete">>(`/account/mcp-grants/${id}`),
    onSuccess: () => {
      toast.success("Agent getrennt.");
      void qc.invalidateQueries({ queryKey: VERBINDUNGEN });
    },
    onError: () => toast.error("Der Agent konnte nicht getrennt werden."),
  });

  const ausstellen = useMutation({
    mutationFn: () => vertrag.post("/account/mcp-tokens", { label: label.trim() }),
    onSuccess: (daten) => {
      setNeu(daten);
      setLabel("");
      void qc.invalidateQueries({ queryKey: SCHLUESSEL });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Schlüssel konnte nicht ausgestellt werden."),
  });

  const zurueckziehen = useMutation({
    mutationFn: (id: number) =>
      api.del<ApiAntwort<"/account/mcp-tokens/{token_id}", "delete">>(`/account/mcp-tokens/${id}`),
    onSuccess: () => {
      toast.success("Schlüssel zurückgezogen.");
      void qc.invalidateQueries({ queryKey: SCHLUESSEL });
    },
    onError: () => toast.error("Schlüssel konnte nicht zurückgezogen werden."),
  });

  const daten = liste.data;
  const voll = !!daten && daten.tokens.length >= daten.max;
  const befehl = neu
    ? `claude mcp add --transport http ratslotse ${neu.endpoint} --header "Authorization: Bearer ${neu.secret}"`
    : "";

  return (
    <Card className="p-6">
      <h2 className="flex items-center gap-2 font-semibold text-foreground">
        <Bot className="h-4 w-4 text-primary" aria-hidden />
        Eigener Agent (MCP)
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Schließ Claude, ChatGPT, Cursor oder einen anderen MCP-fähigen Agenten an die Ratsdaten an.
        Er sucht dann selbst in Beschlüssen, Vorlagen und Tagesordnungen. Er kann nur lesen, und der
        Haushalt ist nicht dabei.
      </p>

      {daten && (
        <div className="mt-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Server-Adresse</p>
          <div className="mt-1 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-lg border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[12px] text-foreground">
              {daten.endpoint}
            </code>
            <Button type="button" variant="secondary" size="sm" onClick={() => void kopieren(daten.endpoint, "Adresse")}
              aria-label="Server-Adresse kopieren">
              <Copy />
            </Button>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            ChatGPT, Claude im Browser und auf dem iPad brauchen nur diese Adresse. Beim Verbinden
            meldest du dich hier an und gibst den Agenten frei. Für Claude Code, Cursor und andere
            Programme geht auch ein Schlüssel.
          </p>
        </div>
      )}

      {verbunden.data && verbunden.data.grants.length > 0 && (
        <div className="mt-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Verbundene Agenten</p>
          <ul className="mt-1 divide-y divide-border/60 border-y border-border/60">
            {verbunden.data.grants.map((g) => (
              <li key={g.id} className="flex items-center gap-3 py-2.5">
                <Link2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{g.client_name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    <span className="font-mono">{g.redirect_host}</span>
                    {" · "}
                    {g.last_used
                      ? `zuletzt ${datum(g.last_used)}, ${g.calls.toLocaleString("de-DE")} ${g.calls === 1 ? "Aufruf" : "Aufrufe"}`
                      : `verbunden ${datum(g.created)}, noch nicht benutzt`}
                  </p>
                </div>
                <button type="button" onClick={() => setTrennen(g)} aria-label={`„${g.client_name}" trennen`}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-destructive">
                  <Trash2 className="h-4 w-4" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {neu && (
        <div className="mt-4 rounded-lg border border-primary/30 bg-primary/[0.04] p-3" role="status">
          <p className="text-sm font-medium text-foreground">Dein Schlüssel für „{neu.token.label}"</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Er steht nur jetzt hier. Kopier ihn in deinen Agenten; wenn er verloren geht, stell einfach einen neuen aus.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded-md bg-background px-2 py-1.5 font-mono text-[12px] text-foreground">
              {neu.secret}
            </code>
            <Button type="button" size="sm" onClick={() => void kopieren(neu.secret, "Schlüssel")}
              aria-label="Schlüssel kopieren">
              <Copy />
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">Für Claude Code im Terminal:</p>
          <div className="mt-1 flex items-start gap-2">
            <code className="min-w-0 flex-1 break-all rounded-md bg-background px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground">
              {befehl}
            </code>
            <Button type="button" variant="secondary" size="sm" onClick={() => void kopieren(befehl, "Befehl")}
              aria-label="Befehl kopieren">
              <Copy />
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Andere Agenten fragen nach Adresse und Kopfzeile: <span className="font-mono">Authorization: Bearer …</span>
          </p>
          <button type="button" onClick={() => setNeu(null)}
            className="mt-3 text-xs font-medium text-primary hover:underline">
            Gespeichert, ausblenden
          </button>
        </div>
      )}

      {liste.isPending && <p className="mt-4 text-xs text-muted-foreground">Schlüssel werden geladen …</p>}
      {liste.isError && (
        <p className="mt-4 text-xs text-muted-foreground">
          Die Schlüssel konnten nicht geladen werden.{" "}
          <button type="button" className="font-medium text-primary hover:underline" onClick={() => void liste.refetch()}>
            Noch einmal
          </button>
        </p>
      )}

      {daten && daten.tokens.length > 0 && (
        <p className="mt-5 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Persönliche Schlüssel</p>
      )}
      {daten && daten.tokens.length > 0 && (
        <ul className="mt-1 divide-y divide-border/60 border-y border-border/60">
          {daten.tokens.map((t) => (
            <li key={t.id} className="flex items-center gap-3 py-2.5">
              <KeyRound className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{t.label}</p>
                <p className="truncate text-xs text-muted-foreground">
                  <span className="font-mono">{t.prefix}…</span>
                  {" · "}
                  {t.last_used
                    ? `zuletzt ${datum(t.last_used)}, ${t.calls.toLocaleString("de-DE")} ${t.calls === 1 ? "Aufruf" : "Aufrufe"}`
                    : `ausgestellt ${datum(t.created)}, noch nicht benutzt`}
                </p>
              </div>
              <button type="button" onClick={() => setLoeschen(t)} aria-label={`Schlüssel „${t.label}" zurückziehen`}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-destructive">
                <Trash2 className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}

      {daten && (
        <form className="mt-4 flex flex-wrap items-end gap-2"
          onSubmit={(e) => { e.preventDefault(); if (label.trim()) ausstellen.mutate(); }}>
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label htmlFor="mcp-label">Wofür ist der Schlüssel?</Label>
            <Input id="mcp-label" value={label} maxLength={60} placeholder="z. B. Claude Desktop"
              onChange={(e) => setLabel(e.target.value)} disabled={voll} />
          </div>
          <Button type="submit" disabled={voll || !label.trim() || ausstellen.isPending}>
            {ausstellen.isPending ? "Stelle aus …" : "Schlüssel ausstellen"}
          </Button>
          {voll && (
            <p className="w-full text-xs text-muted-foreground">
              Du hast {daten.max} Schlüssel, mehr gehen nicht. Zieh einen alten zurück, um einen neuen auszustellen.
            </p>
          )}
        </form>
      )}

      <ConfirmDialog
        open={!!loeschen}
        onOpenChange={(o) => { if (!o) setLoeschen(null); }}
        title="Schlüssel zurückziehen?"
        description={loeschen ? `Der Agent mit „${loeschen.label}" verliert sofort den Zugang. Das lässt sich nicht rückgängig machen.` : ""}
        confirmLabel="Zurückziehen"
        variant="danger"
        onConfirm={() => { if (loeschen) zurueckziehen.mutate(loeschen.id); setLoeschen(null); }}
      />
      <ConfirmDialog
        open={!!trennen}
        onOpenChange={(o) => { if (!o) setTrennen(null); }}
        title="Agent trennen?"
        description={trennen ? `„${trennen.client_name}" verliert sofort den Zugang. Neu verbinden geht jederzeit, mit einer neuen Freigabe.` : ""}
        confirmLabel="Trennen"
        variant="danger"
        onConfirm={() => { if (trennen) verbindungTrennen.mutate(trennen.id); setTrennen(null); }}
      />
    </Card>
  );
}
