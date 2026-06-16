"use client";

import { useEffect, useState, useCallback } from "react";
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

export default function LinkPage() {
  const { user, refresh } = useAuth();
  const [status, setStatus] = useState<LinkStatus | null>(null);
  const [code, setCode] = useState<LinkCode | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStatus = useCallback(async () => {
    const s = await api.get<LinkStatus>("/link/status");
    setStatus(s);
    return s;
  }, []);

  useEffect(() => {
    loadStatus().finally(() => setLoading(false));
  }, [loadStatus]);

  // Poll for the bot redeeming the code, then refresh the user.
  useEffect(() => {
    if (!code || status?.linked) return;
    const t = setInterval(async () => {
      const s = await loadStatus();
      if (s.linked) {
        await refresh();
        clearInterval(t);
      }
    }, 3000);
    return () => clearInterval(t);
  }, [code, status?.linked, loadStatus, refresh]);

  const requestCode = async () => {
    const c = await api.post<LinkCode>("/link/request");
    setCode(c);
  };

  if (loading) return <Spinner />;

  const linked = status?.linked || user?.linked;

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Telegram verbinden</h1>
      <p className="mt-1 text-sm text-slate-500">Verknüpfe dein Web-Konto mit dem Telegram-Bot.</p>

      {linked ? (
        <Card className="mt-6 p-6">
          <div className="flex items-center gap-3">
            <Badge color="green">Verbunden</Badge>
            <span className="text-sm text-slate-600">Chat-ID: {status?.telegram_chat_id ?? user?.telegram_chat_id}</span>
          </div>
          <p className="mt-3 text-sm text-slate-500">
            Dein Konto ist mit Telegram verknüpft. Themen und Abos werden mit deinem Bot-Chat geteilt.
          </p>
        </Card>
      ) : (
        <Card className="mt-6 p-6">
          {!code ? (
            <>
              <p className="text-sm text-slate-600">
                Erzeuge einen Verbindungscode und sende ihn dem Bot. So wird dein Konto freigeschaltet.
              </p>
              <Button className="mt-4" onClick={requestCode}>
                Verbindungscode erzeugen
              </Button>
            </>
          ) : (
            <div>
              <ol className="list-decimal space-y-3 pl-5 text-sm text-slate-600">
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
                    <code className="rounded-lg bg-slate-100 px-3 py-1.5 font-mono text-base font-semibold tracking-wider text-slate-900">
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
              <p className="mt-4 text-xs text-slate-400">Der Code ist {code.expires_in_minutes} Minuten gültig.</p>
              <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-primary" />
                Warte auf Bestätigung…
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
