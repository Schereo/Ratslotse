"use client";

/* Notizen verwalten im Konto (Schalter `notizen`): Passphrase ändern, alle
   herunterladen, auf diesem Gerät sperren, neu anfangen.

   Herunterladen entschlüsselt im Browser; die Datei entsteht dort und geht
   nirgendwohin (`docs/plan-notizen-verschluesselt.md`, § 3). */

import { useEffect, useState } from "react";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import * as krypto from "@/lib/notiz-krypto";
import {
  fetchKeys, lock, MIN_PASSPHRASE, resetNotes, rewrapKeys, sessionKey,
  type NoteDoc, type NoteKeysState,
} from "@/lib/notizen";
import type { ApiAntwort } from "@/lib/vertrag";

const FELD = "min-h-11 w-full rounded-xl border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const KNOPF = "inline-flex min-h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-60";

export function NotizenVerwalten() {
  const { user } = useAuth();
  const owner = user?.id ?? null;
  const [keys, setKeys] = useState<NoteKeysState | null>(null);
  const [alt, setAlt] = useState("");
  const [neu, setNeu] = useState("");
  const [meldung, setMeldung] = useState<string | null>(null);
  const [arbeit, setArbeit] = useState(false);
  const [loeschen, setLoeschen] = useState(false);
  const [exportPass, setExportPass] = useState<string | null>(null);

  useEffect(() => {
    if (owner != null) fetchKeys().then(setKeys).catch(() => setKeys(null));
  }, [owner]);

  if (owner == null || !keys) return null;
  const k = keys.keys;

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Notizen</h2>
      {!keys.configured || !k ? (
        <p className="mt-1 text-sm text-muted-foreground">
          Noch nicht eingerichtet. Das geht an jedem Tagesordnungspunkt und Beschluss unter „Meine Notiz“.
        </p>
      ) : (
        <div className="mt-3 space-y-5">
          <form className="space-y-2" onSubmit={async (e) => {
            e.preventDefault();
            if (neu.length < MIN_PASSPHRASE) return;
            setArbeit(true);
            setMeldung(null);
            try {
              const dk = await krypto.unlockWithPassphrase(k, alt, true);
              if (!dk) { setMeldung("Die bisherige Passphrase passt nicht."); return; }
              const verpackt = await krypto.rewrap(dk, neu, k.salt, k.iterations);
              setKeys(await rewrapKeys(k.key_version, verpackt));
              setAlt(""); setNeu("");
              setMeldung("Neue Passphrase gilt. Deine Notizen und der Wiederherstellungscode bleiben, wie sie sind.");
            } catch (e2) {
              setMeldung(e2 instanceof Error ? e2.message : String(e2));
            } finally {
              setArbeit(false);
            }
          }}>
            <h3 className="text-sm font-semibold text-foreground">Passphrase ändern</h3>
            <input type="password" aria-label="Bisherige Notiz-Passphrase" placeholder="Bisherige Passphrase" autoComplete="current-password"
              value={alt} onChange={(e) => setAlt(e.target.value)} className={FELD} />
            <input type="password" aria-label="Neue Notiz-Passphrase" placeholder={`Neue Passphrase (mindestens ${MIN_PASSPHRASE} Zeichen)`}
              autoComplete="new-password" value={neu} onChange={(e) => setNeu(e.target.value)} className={FELD} />
            <button type="submit" className={KNOPF} disabled={arbeit || !alt || neu.length < MIN_PASSPHRASE}>
              {arbeit ? "Rechnet …" : "Passphrase ändern"}
            </button>
          </form>

          {exportPass != null && (
            <input type="password" aria-label="Notiz-Passphrase zum Entschlüsseln" placeholder="Notiz-Passphrase zum Entschlüsseln"
              autoComplete="current-password" value={exportPass} onChange={(e) => setExportPass(e.target.value)} className={FELD} />
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" className={KNOPF} onClick={async () => {
              const dk = sessionKey(owner) ?? (exportPass ? await krypto.unlockWithPassphrase(k, exportPass) : null);
              if (!dk) {
                if (exportPass) setMeldung("Diese Passphrase passt nicht.");
                setExportPass((x) => x ?? "");
                return;
              }
              const { notes } = await api.get<ApiAntwort<"/notes">>("/notes");
              const klar = await Promise.all(notes.map(async (n) => ({
                ziel: n.target_kind === "decision" ? `Beschluss ${n.target_key}` : `Punkt ${n.target_key.replace("|", " · ")}`,
                geaendert: n.updated_at,
                text: (await krypto.decryptNote<NoteDoc>(dk, krypto.aad(n.target_kind, n.target_key, n.kind), n.iv, n.ciphertext))?.text ?? null,
              })));
              const url = URL.createObjectURL(new Blob([JSON.stringify(klar, null, 2)], { type: "application/json" }));
              const a = Object.assign(document.createElement("a"), { href: url, download: "ratslotse-notizen.json" });
              a.click();
              URL.revokeObjectURL(url);
              setExportPass(null);
            }}>{exportPass != null ? "Entschlüsseln und herunterladen" : "Alle herunterladen"}</button>
            <button type="button" className={KNOPF} onClick={async () => {
              await lock(owner);
              setMeldung("Auf diesem Gerät gesperrt.");
            }}>Auf diesem Gerät sperren</button>
          </div>

          <div className="border-t border-border pt-4">
            {!loeschen ? (
              <button type="button" className="text-sm font-medium text-destructive hover:underline" onClick={() => setLoeschen(true)}>
                Neu anfangen …
              </button>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-foreground">
                  Löscht alle Notizen und die Schlüssel. Das lässt sich nicht rückgängig machen — gedacht für den Fall,
                  dass Passphrase und Wiederherstellungscode verloren sind.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="inline-flex min-h-11 items-center rounded-xl bg-destructive px-4 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                    onClick={async () => {
                      const r = await resetNotes();
                      await lock(owner);
                      setKeys({ configured: false, keys: null });
                      setLoeschen(false);
                      setMeldung(r.deleted === 1 ? "Eine Notiz gelöscht." : `${r.deleted} Notizen gelöscht.`);
                    }}>Alles löschen</button>
                  <button type="button" className={KNOPF} onClick={() => setLoeschen(false)}>Abbrechen</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {meldung && <p className="mt-3 text-sm text-muted-foreground" aria-live="polite">{meldung}</p>}
    </Card>
  );
}
