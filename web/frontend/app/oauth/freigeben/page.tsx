"use client";

/**
 * Freigabe-Seite für OAuth (der `authorization_endpoint` des MCP-Servers).
 *
 * Ein Agent wie ChatGPT schickt den Browser mit seinen OAuth-Parametern
 * hierher. Die Seite fragt das Backend, ob die Anfrage gültig ist
 * (`GET /api/oauth/authorize`), schickt Unangemeldete zur Anmeldung und kommt
 * mit `?weiter=` zurück. „Erlauben" und „Ablehnen" gehen an
 * `POST /api/oauth/authorize`; die Antwort nennt die Adresse, an die der
 * Browser dann geht — mit Code oder mit der Absage.
 *
 * Was zählt, ist die Rücksprungadresse, nicht der Name: Den Namen gibt sich
 * ein Agent bei der Registrierung selbst. Deshalb steht das Ziel groß da, und
 * ein Ziel auf dem eigenen Gerät (localhost, App-Schema) bekommt eine Warnung.
 * Prüfung und Sperre sitzen im Backend (`routers/mcp_oauth.py`); hier wird nur
 * gezeigt, was es sagt.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ShieldAlert, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { mitRuecksprung } from "@/lib/public-routes";
import { hatRecht } from "@/lib/rechte";
import type { ApiAntwort } from "@/lib/vertrag";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui";

type Pruefung = ApiAntwort<"/oauth/authorize", "get">;

/** Die OAuth-Parameter aus der Adresse, so wie der Agent sie geschickt hat. */
function parameter(): Record<string, string> {
  const q = new URLSearchParams(window.location.search);
  const werte: Record<string, string> = {};
  for (const k of ["response_type", "client_id", "redirect_uri", "code_challenge",
    "code_challenge_method", "state", "scope", "resource"]) {
    const v = q.get(k);
    if (v !== null) werte[k] = v;
  }
  return werte;
}

const DARF = [
  "Beschlüsse, Vorlagen und ihre Anlagen lesen",
  "Sitzungen, Tagesordnungen und Protokolle lesen",
];
const DARF_NICHT = [
  "deine Themen, Merkliste oder Gespräche sehen",
  "etwas ändern oder in deinem Namen schreiben",
];
/** Den Haushalt bekommt der Agent genau dann, wenn das Konto ihn auch hier
 *  sieht (Recht `budget`, seit 21.10.2026) — die Liste sagt es je Konto. */
const HAUSHALT_JA = "Haushaltszahlen mit ihren Belegen lesen";
const HAUSHALT_NEIN = "den Haushaltsbereich öffnen";

export default function FreigebenPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [pruefung, setPruefung] = useState<Pruefung | null>(null);
  const [ladeFehler, setLadeFehler] = useState("");
  const [busy, setBusy] = useState<"ja" | "nein" | null>(null);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const p = new URLSearchParams(parameter()).toString();
    api.get<Pruefung>(`/oauth/authorize?${p}`)
      .then((d) => {
        if (d.status === "login") {
          router.replace(mitRuecksprung("/login", window.location.pathname + window.location.search));
          return;
        }
        setPruefung(d);
      })
      .catch((e) => setLadeFehler(e instanceof ApiError ? e.message : "Die Anfrage ließ sich nicht prüfen."));
  }, [router]);

  const entscheiden = async (approve: boolean) => {
    setBusy(approve ? "ja" : "nein");
    setFehler("");
    try {
      const r = await api.post<ApiAntwort<"/oauth/authorize", "post">>(
        "/oauth/authorize", { ...parameter(), approve });
      // Weiter zum Agenten. Ein fremder Ursprung, also eine echte Navigation
      // und kein Router-Sprung; die Adresse hat das Backend gegen die
      // registrierten geprüft.
      window.location.assign(r.redirect);
    } catch (e) {
      setFehler(e instanceof ApiError ? e.message : "Das hat nicht geklappt.");
      setBusy(null);
    }
  };

  if (ladeFehler) {
    return (
      <AuthShell title="Agent verbinden" pose="confused">
        <p className="mt-3 text-sm text-muted-foreground">{ladeFehler}</p>
      </AuthShell>
    );
  }
  if (!pruefung) {
    return (
      <AuthShell title="Agent verbinden" pose="search">
        <p className="mt-3 text-sm text-muted-foreground">Anfrage wird geprüft …</p>
      </AuthShell>
    );
  }

  if (pruefung.status !== "ready") {
    return (
      <AuthShell title="Agent verbinden" pose="confused">
        <p className="mt-3 text-sm text-foreground">{pruefung.message}</p>
        {pruefung.status === "error" && !pruefung.cancel_url && (
          <p className="mt-2 text-sm text-muted-foreground">
            Leg die Verbindung im Agenten neu an. Diese Seite leitet dich nirgendwohin weiter.
          </p>
        )}
        {pruefung.cancel_url && (
          <Button type="button" variant="secondary" className="mt-5 h-11 w-full"
            onClick={() => window.location.assign(pruefung.cancel_url!)}>
            Zurück{pruefung.redirect_host ? ` zu ${pruefung.redirect_host}` : ""}
          </Button>
        )}
      </AuthShell>
    );
  }

  const aufDemGeraet = pruefung.redirect_kind === "local" || pruefung.redirect_kind === "app";

  const haushalt = hatRecht(user, "budget");

  return (
    <AuthShell title="Agent verbinden" pose="point">
      <p className="mt-3 text-[15px] leading-relaxed text-foreground">
        <span className="font-semibold">„{pruefung.client_name}“</span> möchte für dich die
        öffentlichen Ratsdaten bei Ratslotse lesen.
      </p>
      {user && (
        <p className="mt-1 text-xs text-muted-foreground">
          Angemeldet als {user.display_name || user.email}
        </p>
      )}

      <div className="mt-5 space-y-3 text-sm">
        <ul className="space-y-1.5">
          {(haushalt ? [...DARF, HAUSHALT_JA] : DARF).map((t) => (
            <li key={t} className="flex items-start gap-2 text-foreground">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#15803d] dark:text-green-400" aria-hidden />
              {t}
            </li>
          ))}
        </ul>
        <ul className="space-y-1.5">
          {(haushalt ? DARF_NICHT : [DARF_NICHT[0], HAUSHALT_NEIN, DARF_NICHT[1]]).map((t) => (
            <li key={t} className="flex items-start gap-2 text-muted-foreground">
              <X className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span><span className="sr-only">Nicht: </span>{t}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-5 rounded-xl border border-border bg-muted/40 px-3.5 py-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          Danach geht es zurück zu
        </p>
        <p className="mt-0.5 break-all font-mono text-[15px] font-semibold text-foreground">
          {pruefung.redirect_host}
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          {pruefung.client_id_host
            ? `Der Agent weist sich über ${pruefung.client_id_host} aus.`
            : "Den Namen hat sich der Agent selbst gegeben. Verlass dich auf die Adresse."}
        </p>
      </div>

      {aufDemGeraet && (
        <div className="mt-3 flex gap-2.5 rounded-xl border border-[#fde68a] bg-[#fffbeb] px-3.5 py-3 text-xs leading-relaxed text-[#92400e] dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300"
          role="note">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p>
            Das Ziel ist ein Programm auf diesem Gerät, keine Website. Erlaube das nur, wenn du
            die Verbindung gerade selbst gestartet hast, etwa im Terminal oder in deinem Editor.
          </p>
        </div>
      )}

      {pruefung.already_connected && (
        <p className="mt-3 text-xs text-muted-foreground">
          Dieser Agent ist schon verbunden. Die alte Verbindung wird ersetzt.
        </p>
      )}
      {pruefung.at_limit && (
        <p className="mt-3 text-sm text-destructive">
          Du hast schon zehn verbundene Agenten. Trenn erst einen in den Einstellungen.
        </p>
      )}
      {fehler && <p className="mt-3 text-sm text-destructive">{fehler}</p>}

      <div className="mt-6 grid grid-cols-2 gap-2">
        <Button type="button" variant="secondary" className="h-11"
          disabled={busy !== null} onClick={() => void entscheiden(false)}>
          {busy === "nein" ? "Lehne ab …" : "Ablehnen"}
        </Button>
        <Button type="button" className="h-11"
          disabled={busy !== null || pruefung.at_limit} onClick={() => void entscheiden(true)}>
          {busy === "ja" ? "Erlaube …" : "Erlauben"}
        </Button>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
        Ratslotse speichert zu deinem Konto, welche Werkzeuge der Agent aufruft und wonach er
        sucht. Damit sehen wir, wie Agenten den Zugang nutzen und wo die Suche nichts findet.
        Den Suchtext löschen wir nach 90 Tagen.
      </p>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        Trennen kannst du ihn jederzeit in den Einstellungen unter „Eigener Agent (MCP)“.
      </p>
    </AuthShell>
  );
}
