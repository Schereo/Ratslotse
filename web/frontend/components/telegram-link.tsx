"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, Card, Spinner } from "@/components/ui";

interface LinkCode {
  code: string;
  bot_username: string;
  expires_in_minutes: number;
}
interface LinkStatus {
  linked: boolean;
  telegram_chat_id: number | null;
}

function useCountdown(expiresInMinutes: number | null) {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (expiresInMinutes === null) { setSecondsLeft(null); return; }
    startRef.current = Date.now();
    setSecondsLeft(expiresInMinutes * 60);
    const id = setInterval(() => {
      const elapsed = Math.floor((Date.now() - (startRef.current ?? Date.now())) / 1000);
      const remaining = expiresInMinutes * 60 - elapsed;
      if (remaining <= 0) { setSecondsLeft(0); clearInterval(id); }
      else setSecondsLeft(remaining);
    }, 1000);
    return () => clearInterval(id);
  }, [expiresInMinutes]);

  return secondsLeft;
}

/** Telegram account linking — used standalone on /link and inside "Mein Konto". */
export function TelegramLink() {
  const { user, refresh } = useAuth();
  const [code, setCode] = useState<LinkCode | null>(null);

  const statusQuery = useQuery({
    queryKey: ["link-status"],
    queryFn: () => api.get<LinkStatus>("/link/status"),
    refetchInterval: (query) => {
      const isLinked = query.state.data?.linked || user?.linked;
      return code && !isLinked ? 3000 : false;
    },
  });

  const requestMutation = useMutation({
    mutationFn: () => api.post<LinkCode>("/link/request"),
    onSuccess: (c) => { setCode(c); },
  });

  const countdown = useCountdown(code?.expires_in_minutes ?? null);
  const expired = countdown !== null && countdown <= 0;

  const statusData = statusQuery.data;
  const linked = statusData?.linked || user?.linked;

  // Refresh auth user once the bot redeems the code
  if (statusData?.linked && !user?.linked) {
    refresh();
  }

  if (statusQuery.isPending) return <Spinner />;

  if (linked) {
    return (
      <Card className="p-6">
        <h2 className="font-semibold text-foreground">Telegram</h2>
        <div className="mt-3 flex items-center gap-3">
          <Badge color="green">Verbunden</Badge>
          <span className="text-sm text-muted-foreground">
            Chat-ID: {statusData?.telegram_chat_id ?? user?.telegram_chat_id}
          </span>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          Dein Konto ist mit Telegram verknüpft. Themen und Abos werden mit deinem Bot-Chat geteilt.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Telegram verbinden</h2>
      {!code ? (
        <>
          <p className="mt-2 text-sm text-muted-foreground">
            Erzeuge einen Verbindungscode und sende ihn dem Bot. So wird dein Konto freigeschaltet.
          </p>
          <Button className="mt-4" onClick={() => requestMutation.mutate()} disabled={requestMutation.isPending}>
            {requestMutation.isPending ? "Erzeuge…" : "Verbindungscode erzeugen"}
          </Button>
        </>
      ) : (
        <div className="mt-2">
          <ol className="list-decimal space-y-3 pl-5 text-sm text-muted-foreground">
            <li>
              Öffne den Bot:{" "}
              <a
                href={`https://t.me/${code.bot_username}`}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-primary hover:underline"
              >
                @{code.bot_username}
              </a>
            </li>
            <li>
              Sende diese Nachricht:
              <div className="mt-1 flex items-center gap-2">
                <code className="rounded-lg bg-muted px-3 py-1.5 font-mono text-base font-semibold tracking-wider text-foreground">
                  /verbinden {code.code}
                </code>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => navigator.clipboard?.writeText(`/verbinden ${code.code}`)}
                >
                  Kopieren
                </Button>
              </div>
            </li>
            <li>Diese Seite aktualisiert sich automatisch, sobald die Verbindung steht.</li>
          </ol>
          {expired ? (
            <p className="mt-4 text-xs text-destructive font-medium">Code abgelaufen — bitte neuen Code erzeugen.</p>
          ) : countdown !== null ? (
            <p className="mt-4 text-xs text-muted-foreground">
              Code gültig noch {Math.floor(countdown / 60)}:{String(countdown % 60).padStart(2, "0")} min
            </p>
          ) : (
            <p className="mt-4 text-xs text-muted-foreground">Der Code ist {code.expires_in_minutes} Minuten gültig.</p>
          )}
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-primary" />
            Warte auf Bestätigung…
          </div>
        </div>
      )}
    </Card>
  );
}
