"use client";

/* „Passkeys“ im Konto (Schalter `passkey-anmeldung`): auflisten, hinzufügen,
   entfernen. Ein neuer Passkey schließt, wo der Browser es kann, gleich auch
   die Notizen auf (`lib/passkey.ts`, `notizenMitPasskey`). Den letzten Weg ins
   Konto lässt der Server nicht entfernen; seine Meldung steht dann hier. */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import {
  kontoPasskeyEntfernen, kontoPasskeyHinzufuegen, kontoPasskeysLaden, notizenMitPasskey, passkeyFehlerMelden, type KontoPasskey,
  type KontoPasskeys,
} from "@/lib/passkey";
import { Button, Card, ConfirmDialog, toast } from "@/components/ui";
import { passkeyMeldung, usePasskeyAnmeldung } from "@/components/passkey-knopf";

const SCHLUESSEL = ["konto-passkeys"];

export function PasskeysCard() {
  const { user } = useAuth();
  const moeglich = usePasskeyAnmeldung();
  const qc = useQueryClient();
  const [weg, setWeg] = useState<KontoPasskey | null>(null);
  const { data } = useQuery({ queryKey: SCHLUESSEL, queryFn: kontoPasskeysLaden });

  const hinzufuegen = useMutation({
    mutationFn: async () => {
      const { liste, treffer } = await kontoPasskeyHinzufuegen();
      if (user) void notizenMitPasskey(user.id, treffer).catch((e) => passkeyFehlerMelden(e, "Notizen nach neuem Passkey"));
      return liste;
    },
    onSuccess: (liste) => {
      qc.setQueryData<KontoPasskeys>(SCHLUESSEL, liste);
      toast.success("Passkey hinzugefügt.");
    },
    onError: (err) => {
      const m = passkeyMeldung(err);
      if (m) toast.error(m);
    },
  });

  const entfernen = useMutation({
    mutationFn: (id: number) => kontoPasskeyEntfernen(id),
    onSuccess: (liste) => {
      qc.setQueryData<KontoPasskeys>(SCHLUESSEL, liste);
      toast.success("Passkey entfernt.");
    },
    onError: (err) => toast.error(passkeyMeldung(err) ?? "Entfernen fehlgeschlagen."),
  });

  const liste = data?.passkeys ?? [];
  return (
    <Card className="p-6" role="region" aria-labelledby="konto-passkeys">
      <h2 id="konto-passkeys" className="font-semibold text-foreground">Passkeys</h2>
      {liste.length === 0 && (
        <p className="mt-1 text-sm text-muted-foreground">Anmelden mit Face ID, Touch ID oder der Gerätesperre.</p>
      )}
      {liste.length > 0 && (
        <ul className="mt-3 divide-y divide-border">
          {liste.map((p) => (
            <li key={p.id} className="flex items-center gap-3 py-2.5">
              <KeyRound className="h-4 w-4 flex-none text-muted-foreground" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{p.label || "Passkey"}</p>
                <p className="text-xs text-muted-foreground">
                  {p.last_used_at ? `Zuletzt ${formatDate(p.last_used_at)}` : `Seit ${formatDate(p.created_at)}`}
                  {p.notes && " · auch für Notizen"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setWeg(p)}
                aria-label={`Passkey „${p.label || "Passkey"}“ entfernen`}
                className="inline-flex h-11 w-11 flex-none items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {moeglich && (
        <Button variant="secondary" size="sm" className="mt-4" disabled={hinzufuegen.isPending} onClick={() => hinzufuegen.mutate()}>
          <KeyRound aria-hidden />
          {hinzufuegen.isPending ? "Wartet auf den Passkey …" : "Passkey hinzufügen"}
        </Button>
      )}
      <ConfirmDialog
        open={weg != null}
        onOpenChange={(o) => { if (!o) setWeg(null); }}
        title="Passkey entfernen?"
        description={weg?.notes
          ? "Mit ihm meldest du dich dann nicht mehr an. Deine Notizen schließt er weiter auf — das entfernst du unter „Notizen“."
          : "Mit ihm meldest du dich dann nicht mehr an."}
        confirmLabel="Entfernen"
        variant="danger"
        onConfirm={() => { if (weg) entfernen.mutate(weg.id); setWeg(null); }}
      />
    </Card>
  );
}
