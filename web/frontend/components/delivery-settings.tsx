"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Moon } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isNativeApp } from "@/lib/platform";
import { enablePush } from "@/lib/push";
import { Button, Card, Switch, toast } from "@/components/ui";
import type { DeliveryChannel, User } from "@/lib/types";

/** Ein Anlass aus 30a/B — was das Backend über sich selbst erzählt.
 *  `parent`: Unter-Option, die nur wirkt, solange der Eltern-Anlass an ist —
 *  sie wird eingerückt und ist ohne Elternteil nicht bedienbar. */
type NotifyKind = {
  key: string; label: string; hint: string; default: boolean; enabled: boolean;
  parent?: string | null;
};
type NotifyPrefs = {
  kinds: NotifyKind[];
  limits: { per_day: number; quiet_from: number; quiet_to: number };
};

/** Benachrichtigungen-Karte (RL-702, Design 6a; erweitert nach 30a/E):
 *  **erst wo, dann wofür.** Oben E-Mail und Push als unabhängige Schalter
 *  (intern weiter der eine delivery_channel: email | push | both), darunter die
 *  sechs Anlässe einzeln abschaltbar, dann die Nachtruhe als Hinweis und der
 *  Test.
 *
 *  Die Anlass-Liste kommt vom Server (`GET /account/notifications`) statt hier
 *  hartkodiert zu stehen: Sonst fiele ein neu dazugekommener Anlass erst auf,
 *  wenn sich jemand über eine unabschaltbare Meldung ärgert. */
export function DeliverySettings() {
  const { user, refresh } = useAuth();
  // Detected after mount to avoid a hydration mismatch between the static export
  // (rendered as web) and the app runtime.
  const [native, setNative] = useState(false);
  useEffect(() => { setNative(isNativeApp()); }, []);

  const mutation = useMutation({
    mutationFn: (channel: DeliveryChannel) =>
      api.put<User>("/account/delivery", { delivery_channel: channel }),
    onSuccess: (_d, channel) => {
      refresh();
      toast.success(
        channel === "off"
          ? "Benachrichtigungen sind aus. Du kannst sie jederzeit wieder anschalten."
          : "Zustellung aktualisiert.",
      );
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Konnte nicht gespeichert werden."),
  });

  const testMutation = useMutation({
    mutationFn: () => api.post<{ sent: string[] }>("/account/test-notification", {}),
    onSuccess: (d) =>
      d.sent.length > 0
        ? toast.success(`Test unterwegs: ${d.sent.map((s) => (s === "email" ? "E-Mail" : "Push")).join(" + ")}.`)
        : toast.error("Kein Kanal konnte zustellen — Push braucht die App, E-Mail den Versand-Dienst."),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Test konnte nicht gesendet werden."),
  });

  const qc = useQueryClient();
  const prefsQuery = useQuery({
    queryKey: ["notify-prefs"],
    queryFn: () => api.get<NotifyPrefs>("/account/notifications"),
  });
  const kindMutation = useMutation({
    mutationFn: (prefs: Record<string, boolean>) =>
      api.put<NotifyPrefs>("/account/notifications", { prefs }),
    onSuccess: (d) => qc.setQueryData(["notify-prefs"], d),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Konnte nicht gespeichert werden."),
  });

  const toggleKind = (key: string, next: boolean) => {
    const alle = Object.fromEntries(
      (prefsQuery.data?.kinds ?? []).map((k) => [k.key, k.key === key ? next : k.enabled]),
    );
    kindMutation.mutate(alle);
  };

  // ?zeig= aus der URL — Deep-Link aus den E-Mails („Mein Konto"-Fußzeile,
  // „Nur Änderungs-Meldungen abschalten"): zum gemeinten Schalter springen und
  // ihn kurz hervorheben. `zustellung` meint den Kanal-Block, alles andere den
  // Anlass mit diesem Schlüssel. Bewusst window.location statt useSearchParams
  // (der statische MOBILE-Export bricht an der Suspense-Grenze, wie in
  // lib/public-routes.ts) — und als Query statt #-Anker, weil nur Pfad + Query
  // den Login-Umweg über ?weiter= überleben.
  const [flashZiel, setFlashZiel] = useState<string | null>(null);
  const jumped = useRef(false);
  const prefsData = prefsQuery.data;
  useEffect(() => {
    if (jumped.current) return;
    const zeig = new URLSearchParams(window.location.search).get("zeig");
    if (!zeig) return;
    // Anlass-Zeilen existieren erst, wenn die Liste vom Server da ist.
    if (zeig !== "zustellung" && !prefsData) return;
    jumped.current = true;
    // Nach dem Rendern springen, nicht währenddessen (Muster aus badges.tsx).
    setTimeout(() => {
      const id = zeig === "zustellung" ? "zustellung" : `anlass-${zeig}`;
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
      setFlashZiel(zeig);
      setTimeout(() => setFlashZiel(null), 2200);
    }, 50);
  }, [prefsData]);

  const current = user?.delivery_channel ?? "email";
  const emailOn = current === "email" || current === "both";
  const pushOn = current === "push" || current === "both";
  const alleAus = !emailOn && !pushOn;
  // Push nur in der App aktivierbar; ist er (auf einem anderen Gerät) schon an,
  // bleibt der Schalter auch im Web sichtbar/bedienbar.
  const pushAvailable = native || pushOn;

  /** Beide Schalter aus heißt aus — und wird auch so gespeichert.
   *
   *  Hier stand eine Sperre („Mindestens ein Kanal muss an bleiben"), und das
   *  Backend kannte gar keinen anderen Wert. Wer nichts mehr hören wollte,
   *  musste stattdessen die sechs Anlass-Schalter einzeln umlegen — sechs
   *  Handgriffe für etwas, das eine Person als einen denkt, und niemand fand
   *  sie. Eine App, die man nicht abstellen kann, verliert man ganz. */
  const apply = (email: boolean, push: boolean) => {
    mutation.mutate(email && push ? "both" : email ? "email" : push ? "push" : "off");
  };

  const togglePush = async (next: boolean) => {
    if (next) {
      const ok = await enablePush();
      if (!ok) {
        toast.error("Bitte Mitteilungen für Ratslotse in den Geräte-Einstellungen erlauben.");
        return;
      }
    }
    apply(emailOn, next);
  };

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Benachrichtigungen</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {alleAus
          ? "Aus — Ratslotse meldet sich nicht. Alles Weitere findest du in der App."
          : prefsQuery.data
            ? `Höchstens ${prefsQuery.data.limits.per_day} am Tag. Nachts nie.`
            : "Für neue Beschlüsse zu deinen Themen und abonnierte Tagesordnungen."}
      </p>
      <div
        id="zustellung"
        className={`mt-4 space-y-3 scroll-mt-24 rounded-xl transition-shadow ${
          flashZiel === "zustellung" ? "ring-2 ring-primary bg-primary/[0.07]" : ""
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">E-Mail</p>
            <p className="truncate text-xs text-muted-foreground">an {user?.email}</p>
          </div>
          <Switch
            checked={emailOn}
            aria-label="E-Mail-Benachrichtigungen"
            disabled={mutation.isPending}
            onCheckedChange={(v) => apply(v, pushOn)}
          />
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">Push</p>
            <p className="text-xs text-muted-foreground">
              {pushAvailable ? "Mitteilung direkt auf dieses Gerät." : "Nur in der App verfügbar."}
            </p>
          </div>
          <Switch
            checked={pushOn}
            aria-label="Push-Benachrichtigungen"
            disabled={!pushAvailable || mutation.isPending}
            onCheckedChange={togglePush}
          />
        </div>
      </div>
      {/* „Wofür" — die sechs Anlässe aus 30a/B, jeder einzeln abschaltbar.
          Ist gar kein Kanal an, hätten sie keine Wirkung: Sie bleiben sichtbar
          (die Einstellung geht ja nicht verloren), aber sichtbar wirkungslos —
          ein bedienbarer Schalter, der nichts tut, wäre die schlechtere Lüge.

          Bewusst KEIN aria-hidden dabei: Die Ausgrauung ist die sichtbare
          Hälfte dieser Auskunft, der Zusatz an der Überschrift die hörbare.
          Wer den Block ausblendet, nimmt Screenreader-Nutzenden beides. */}
      {prefsQuery.data && (
        <div className={`mt-6 border-t border-border pt-5 ${alleAus ? "opacity-45" : ""}`}>
          <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            Wofür {alleAus && <span className="font-medium normal-case tracking-normal">— erst wieder, wenn ein Kanal an ist</span>}
          </p>
          <div className="mt-3 space-y-3">
            {prefsQuery.data.kinds.map((k) => {
              // Unter-Option (z. B. „Änderungen an Tagesordnungen" unter N1):
              // eingerückt, und ohne den Eltern-Anlass sichtbar wirkungslos —
              // das Backend würde sie ohnehin nicht zustellen.
              const elternAn = !k.parent
                || (prefsQuery.data?.kinds.find((p) => p.key === k.parent)?.enabled ?? true);
              return (
                <div
                  key={k.key}
                  id={`anlass-${k.key}`}
                  className={`flex items-center justify-between gap-3 scroll-mt-24 rounded-lg transition-shadow ${
                    k.parent ? "ml-3 border-l-2 border-border pl-3" : ""
                  } ${!elternAn ? "opacity-45" : ""} ${
                    flashZiel === k.key ? "ring-2 ring-primary bg-primary/[0.07]" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">{k.label}</p>
                    <p className="text-xs leading-relaxed text-muted-foreground">{k.hint}</p>
                  </div>
                  <Switch
                    checked={k.enabled}
                    aria-label={k.label}
                    disabled={alleAus || !elternAn || kindMutation.isPending}
                    onCheckedChange={(v) => toggleKind(k.key, v)}
                  />
                </div>
              );
            })}
          </div>
          {/* Nachtruhe: eine Zusicherung, kein Schalter — sie gilt immer. */}
          <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-muted/60 px-3.5 py-3">
            <Moon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="text-xs leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Nachtruhe</span> — nichts zwischen{" "}
              {prefsQuery.data.limits.quiet_from}:00 und {prefsQuery.data.limits.quiet_to}:00 Uhr.
              Was abends entschieden wird, kommt am Morgen an.
            </p>
          </div>
        </div>
      )}

      {/* Ohne Kanal gibt es nichts zu testen — der Knopf würde zuverlässig
          „Kein Kanal konnte zustellen" melden und wie ein Fehler aussehen. */}
      {!alleAus && (
        <Button
          variant="secondary"
          size="sm"
          className="mt-5"
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
        >
          <BellRing /> {testMutation.isPending ? "Sende…" : "Test-Benachrichtigung senden"}
        </Button>
      )}
    </Card>
  );
}
