"use client";

/* Notizen verwalten im Konto (Schalter `notizen`): Passkeys, Notfall-Code,
   Passphrase, alle herunterladen, auf diesem Gerät sperren, neu anfangen.

   Alles, was eine Verpackung neu anlegt (weiterer Passkey, Code, Passphrase),
   braucht den Datenschlüssel einmal exportierbar — dafür fragt es den
   vorhandenen Passkey (oder die Passphrase) noch einmal. Der Sitzungsschlüssel
   bleibt dabei, was er ist: nicht exportierbar.

   Herunterladen entschlüsselt im Browser; die Datei entsteht dort und geht
   nirgendwohin (`docs/plan-notizen-verschluesselt.md`, § 3). */

import { useEffect, useState } from "react";
import { Fingerprint } from "lucide-react";
import { Card, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import * as krypto from "@/lib/notiz-krypto";
import { mitPasskeyEntsperren, passkeyAnlegen, passkeyMoeglich, PasskeyFehler } from "@/lib/notiz-passkey";
import { notizVerpackungMitKontoPasskey } from "@/lib/passkey";
import { useFeature } from "@/lib/features";
import {
  addPasskey, deletePasskey, fetchKeys, lock, MIN_PASSPHRASE, resetNotes, rewrapKeys, sessionKey, setRecovery,
  type NoteDoc, type NoteKeysState,
} from "@/lib/notizen";
import type { ApiAntwort } from "@/lib/vertrag";

const FELD = "min-h-11 w-full rounded-xl border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const KNOPF = "inline-flex min-h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-60";
const TITEL = "text-sm font-semibold text-foreground";

export function NotizenVerwalten() {
  const { user } = useAuth();
  const owner = user?.id ?? null;
  const mitAnmeldung = useFeature("passkey-anmeldung");
  const [keys, setKeys] = useState<NoteKeysState | null>(null);
  const [alt, setAlt] = useState("");
  const [neu, setNeu] = useState("");
  const [meldung, setMeldung] = useState<string | null>(null);
  const [arbeit, setArbeit] = useState(false);
  const [loeschen, setLoeschen] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [kannPasskey, setKannPasskey] = useState(false);

  useEffect(() => {
    if (owner != null) fetchKeys().then(setKeys).catch(() => setKeys(null));
    void passkeyMoeglich().then(setKannPasskey);
  }, [owner]);

  if (owner == null || !keys) return null;
  const k = keys.keys;
  const name = user?.email ?? `Konto ${owner}`;

  /** Den Datenschlüssel einmal exportierbar: über einen Passkey, sonst über
   *  die bisherige Passphrase aus dem Feld. */
  const exportierbar = async (): Promise<CryptoKey | null> => {
    if (!k) return null;
    if (keys.passkeys.length > 0 && kannPasskey) return mitPasskeyEntsperren(keys.passkeys, true);
    const dk = alt ? await krypto.unlockWithPassphrase(k, alt, true) : null;
    if (!dk) setMeldung(alt ? "Die bisherige Passphrase passt nicht." : "Bitte zuerst die bisherige Passphrase eingeben.");
    return dk;
  };

  /** Ein Schritt mit Arbeitsanzeige und Meldung; ein abgebrochener Passkey ist kein Fehler. */
  const schritt = async (fn: () => Promise<string | null | void>) => {
    setArbeit(true);
    setMeldung(null);
    try {
      const m = await fn();
      if (m) setMeldung(m);
    } catch (e) {
      setMeldung(e instanceof PasskeyFehler
        ? (e.art === "abgebrochen" ? "Abgebrochen." : e.message)
        : e instanceof Error ? e.message : String(e));
    } finally {
      setArbeit(false);
    }
  };

  const wege = keys.passkeys.length + (k?.wrapped_passphrase ? 1 : 0) + (k?.wrapped_recovery ? 1 : 0);
  const brauchtAlt = !!k?.wrapped_passphrase && !(keys.passkeys.length > 0 && kannPasskey);

  return (
    <Card className="p-6">
      <h2 className="font-semibold text-foreground">Notizen</h2>
      {!keys.configured || !k ? (
        <p className="mt-1 text-sm text-muted-foreground">
          Noch nicht eingerichtet. Das geht an jedem Tagesordnungspunkt und Beschluss unter „Meine Notiz“.
        </p>
      ) : (
        <div className="mt-3 space-y-5">
          <section className="space-y-2">
            <h3 className={TITEL}>Passkeys</h3>
            {keys.passkeys.length === 0 ? (
              <p className="text-sm text-muted-foreground">Noch keiner. Mit einem Passkey entsperrst du deine Notizen per Face ID, Touch ID oder Gerätesperre.</p>
            ) : (
              <ul className="divide-y divide-border rounded-xl border border-border">
                {keys.passkeys.map((p) => (
                  <li key={p.id} className="flex min-h-11 items-center justify-between gap-3 px-3 py-2 text-sm">
                    <span className="min-w-0">
                      <span className="text-foreground">{p.label || "Passkey"}</span>
                      <span className="ml-2 text-muted-foreground">seit {formatDate(p.created_at)}</span>
                    </span>
                    <button type="button" className="text-sm font-medium text-destructive hover:underline disabled:text-muted-foreground disabled:no-underline"
                      disabled={arbeit || wege <= 1} title={wege <= 1 ? "Der letzte Schlüssel zu deinen Notizen bleibt." : undefined}
                      onClick={() => schritt(async () => { setKeys(await deletePasskey(p.id)); return "Passkey entfernt."; })}>
                      Entfernen
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {kannPasskey && (
              <button type="button" className={KNOPF} disabled={arbeit || (brauchtAlt && !alt)}
                onClick={() => schritt(async () => {
                  const dk = await exportierbar();
                  if (!dk) return;
                  setKeys(await addPasskey(k.key_version, mitAnmeldung
                    ? await notizVerpackungMitKontoPasskey(owner, dk)
                    : await passkeyAnlegen(dk, owner, name)));
                  return "Passkey hinzugefügt.";
                })}>
                <Fingerprint className="mr-1.5 h-4 w-4" aria-hidden /> Passkey hinzufügen
              </button>
            )}
          </section>

          <section className="space-y-2">
            <h3 className={TITEL}>Notfall-Code</h3>
            <p className="text-sm text-muted-foreground">
              {k.wrapped_recovery
                ? "Ist angelegt. Ein neuer ersetzt den alten."
                : "Freiwillig: ein Code zum Ausdrucken, falls alle Passkeys einmal weg sind."}
            </p>
            {code ? (
              <div className="space-y-2">
                <p className="select-all rounded-xl border border-dashed border-border bg-muted px-3 py-2 text-center font-mono text-sm tracking-wider text-foreground [overflow-wrap:anywhere]"
                  aria-label="Notfall-Code">{code}</p>
                <p className="text-hinweis text-muted-foreground">Nur jetzt zu sehen. Schreib ihn auf oder druck ihn aus.</p>
                <button type="button" className={KNOPF} onClick={() => setCode(null)}>Fertig</button>
              </div>
            ) : (
              <button type="button" className={KNOPF} disabled={arbeit || (brauchtAlt && !alt)}
                onClick={() => schritt(async () => {
                  const dk = await exportierbar();
                  if (!dk) return;
                  const neuerCode = await krypto.notfallCode(dk, k.salt);
                  setKeys(await setRecovery(k.key_version, neuerCode.wrapped_recovery));
                  setCode(neuerCode.recoveryCode);
                })}>
                {k.wrapped_recovery ? "Neuen Notfall-Code erzeugen" : "Notfall-Code erstellen"}
              </button>
            )}
          </section>

          <form className="space-y-2" onSubmit={(e) => {
            e.preventDefault();
            if (neu.length < MIN_PASSPHRASE) return;
            void schritt(async () => {
              const dk = await exportierbar();
              if (!dk) return;
              setKeys(await rewrapKeys(k.key_version, await krypto.rewrap(dk, neu, k.salt, k.iterations)));
              setAlt(""); setNeu("");
              return k.wrapped_passphrase
                ? "Neue Passphrase gilt. Deine Notizen und die übrigen Schlüssel bleiben, wie sie sind."
                : "Passphrase angelegt — für Browser ohne Passkey.";
            });
          }}>
            <h3 className={TITEL}>{k.wrapped_passphrase ? "Passphrase ändern" : "Passphrase (freiwillig)"}</h3>
            {!k.wrapped_passphrase && (
              <p className="text-sm text-muted-foreground">Ein Rückfall für Browser, die keinen Passkey können.</p>
            )}
            {k.wrapped_passphrase && (
              <input type="password" aria-label="Bisherige Notiz-Passphrase" placeholder="Bisherige Passphrase" autoComplete="current-password"
                value={alt} onChange={(e) => setAlt(e.target.value)} className={FELD} />
            )}
            <input type="password" aria-label="Neue Notiz-Passphrase" placeholder={`Neue Passphrase (mindestens ${MIN_PASSPHRASE} Zeichen)`}
              autoComplete="new-password" value={neu} onChange={(e) => setNeu(e.target.value)} className={FELD} />
            <button type="submit" className={KNOPF} disabled={arbeit || (brauchtAlt && !alt) || neu.length < MIN_PASSPHRASE}>
              {arbeit ? "Rechnet …" : k.wrapped_passphrase ? "Passphrase ändern" : "Passphrase anlegen"}
            </button>
          </form>

          <div className="flex flex-wrap gap-2">
            <button type="button" className={KNOPF} disabled={arbeit} onClick={() => schritt(async () => {
              const dk = sessionKey(owner) ?? await exportierbar();
              if (!dk) return;
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
            })}>Alle herunterladen</button>
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
                  Löscht alle Notizen und alle Schlüssel. Das lässt sich nicht rückgängig machen — gedacht für den Fall,
                  dass kein Weg mehr zu den Notizen führt.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="inline-flex min-h-11 items-center rounded-xl bg-destructive px-4 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                    onClick={async () => {
                      const r = await resetNotes();
                      await lock(owner);
                      setKeys({ configured: false, keys: null, passkeys: [] });
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
