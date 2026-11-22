/* Notizen: Schlüssel der Sitzung, Ablage auf Wunsch, Weg zum Server
   (`docs/plan-notizen-verschluesselt.md`). Verschlüsselt wird in
   `lib/notiz-krypto.ts`; hier geht nichts im Klartext hinaus.

   Der entsperrte Datenschlüssel ist ein NICHT exportierbarer `CryptoKey`.
   Er liegt für die Sitzung im Speicher (gilt seitenübergreifend, solange der
   Tab lebt) und — nur wenn man „auf diesem Gerät merken" wählt — in
   IndexedDB, das `CryptoKey`s als solche ablegt, ohne den Schlüssel je
   herauszugeben. Abmelden räumt beides (`lib/konto-raeumen.ts`). */

import { api, ApiError } from "@/lib/api";
import * as k from "@/lib/notiz-krypto";
import type { PasskeyVerpackung } from "@/lib/notiz-passkey";
import type { ApiAntwort } from "@/lib/vertrag";

export type NoteKeysState = ApiAntwort<"/notes/keys">;
export type NoteEntry = ApiAntwort<"/notes">["notes"][number];
export type TargetKind = NoteEntry["target_kind"];
export interface NoteDoc { text: string }

// ---- Schlüssel der Sitzung ------------------------------------------------

let sitzung: { owner: number; dk: CryptoKey } | null = null;
const hoerer = new Set<() => void>();

export function sessionKey(owner: number): CryptoKey | null {
  return sitzung?.owner === owner ? sitzung.dk : null;
}

export function onKeyChange(fn: () => void): () => void {
  hoerer.add(fn);
  return () => { hoerer.delete(fn); };
}

function melden() {
  for (const fn of hoerer) fn();
}

const DB = "ratslotse-notizen";
const STORE = "schluessel";

function idb<T>(fn: (s: IDBObjectStore) => IDBRequest<T>, modus: IDBTransactionMode): Promise<T | null> {
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onerror = () => resolve(null);
      req.onsuccess = () => {
        try {
          const tx = req.result.transaction(STORE, modus);
          const r = fn(tx.objectStore(STORE));
          r.onsuccess = () => resolve(r.result ?? null);
          r.onerror = () => resolve(null);
          tx.oncomplete = () => req.result.close();
        } catch {
          resolve(null);
        }
      };
    } catch {
      // Privates Fenster, gesperrter Speicher: dann eben jedes Mal die Passphrase.
      resolve(null);
    }
  });
}

export async function setSessionKey(owner: number, dk: CryptoKey, merken: boolean): Promise<void> {
  sitzung = { owner, dk };
  if (merken) await idb((s) => s.put(dk, `konto:${owner}`), "readwrite");
  melden();
}

/** Ein gemerkter Schlüssel dieses Geräts, falls es einen gibt. */
export async function rememberedKey(owner: number): Promise<CryptoKey | null> {
  if (sessionKey(owner)) return sessionKey(owner);
  const dk = await idb<CryptoKey>((s) => s.get(`konto:${owner}`) as IDBRequest<CryptoKey>, "readonly");
  if (dk) {
    sitzung = { owner, dk };
    melden();
  }
  return dk;
}

// ---- Anmelde-Passkey dieser Sitzung (lib/passkey.ts) -------------------------
// Wer sich per Passkey anmeldet, hat dessen PRF-Geheimnis schon geliefert. War
// der Passkey noch keiner für die Notizen (oder die Adresse noch unbestätigt),
// bleibt hier der daraus abgeleitete, NICHT exportierbare Schlüssel liegen —
// nur im Speicher dieses Tabs. Beim nächsten Entsperren oder Einrichten kommt
// der Passkey dann ohne zweite Abfrage dazu. Gefährlicher als der Datenschlüssel
// selbst, der hier ebenso liegt, ist er nicht.

let anmeldung: { owner: number; credentialId: string; kek: CryptoKey } | null = null;

export function merkeAnmeldePasskey(owner: number, credentialId: string, kek: CryptoKey): void {
  anmeldung = { owner, credentialId, kek };
}

export function anmeldePasskey(owner: number): { credentialId: string; kek: CryptoKey } | null {
  return anmeldung?.owner === owner ? { credentialId: anmeldung.credentialId, kek: anmeldung.kek } : null;
}

export function vergissAnmeldePasskey(): void {
  anmeldung = null;
}

/** Sperren: Schlüssel aus Speicher und Gerät. Die Notizen bleiben beim Server. */
export async function lock(owner?: number): Promise<void> {
  sitzung = null;
  if (owner == null) anmeldung = null;
  if (owner != null) await idb((s) => s.delete(`konto:${owner}`), "readwrite");
  else await idb((s) => s.clear(), "readwrite");
  melden();
}

// ---- Server ---------------------------------------------------------------

export type NotePasskey = NoteKeysState["passkeys"][number];

export const fetchKeys = () => api.get<NoteKeysState>("/notes/keys");
export const createKeys = (keys: k.WrappedKeys) => api.put<NoteKeysState>("/notes/keys", keys);
/** Einrichten mit Passkey statt Passphrase (`lib/notiz-passkey.ts`). */
export const createKeysMitPasskey = (basis: Awaited<ReturnType<typeof k.neuerSchluessel>>["basis"], passkey: PasskeyVerpackung) =>
  api.put<NoteKeysState>("/notes/keys", { ...basis, passkey });
export const addPasskey = (keyVersion: number, passkey: PasskeyVerpackung) =>
  api.post<NoteKeysState>("/notes/passkeys", { ...passkey, key_version: keyVersion });
export const deletePasskey = (id: number) => api.del<NoteKeysState>(`/notes/passkeys/${id}`);
export const setRecovery = (keyVersion: number, wrappedRecovery: string) =>
  api.put<NoteKeysState>("/notes/keys/recovery", { key_version: keyVersion, wrapped_recovery: wrappedRecovery });
export const rewrapKeys = (keyVersion: number, neu: Awaited<ReturnType<typeof k.rewrap>>) =>
  api.put<NoteKeysState>("/notes/keys", { key_version: keyVersion, ...neu });
export const resetNotes = () => api.del<{ deleted: number }>("/notes/keys");

export type NoteArt = NoteEntry["kind"];

const pfad = (kind: TargetKind, key: string, art: NoteArt = "note") =>
  `/notes/${kind}/${encodeURIComponent(key)}/${art}`;

export interface Loaded<T> { doc: T | null; version: number; updatedAt: string; lesbar: boolean }

/** Eine Notiz (`note`) oder ein Mitschrieb (`transcript`) zu einem Ziel. */
export async function loadDoc<T>(dk: CryptoKey, kind: TargetKind, key: string, art: NoteArt): Promise<Loaded<T> | null> {
  const r = await api.get<ApiAntwort<"/notes">>(`/notes?target_kind=${kind}&target_key=${encodeURIComponent(key)}`);
  const n = r.notes.find((x) => x.kind === art);
  if (!n) return null;
  const doc = await k.decryptNote<T>(dk, k.aad(kind, key, art), n.iv, n.ciphertext);
  return { doc, version: n.version, updatedAt: n.updated_at, lesbar: doc != null };
}

export type SaveResult<T> =
  | { ok: true; version: number; updatedAt: string }
  | { ok: false; conflict: Loaded<T> | null };

export async function saveDoc<T>(dk: CryptoKey, keyVersion: number, kind: TargetKind, key: string, art: NoteArt,
  doc: T, baseVersion: number): Promise<SaveResult<T>> {
  const blob = await k.encryptNote(dk, k.aad(kind, key, art), doc);
  try {
    const n = await api.put<NoteEntry>(pfad(kind, key, art), { ...blob, key_version: keyVersion, version: baseVersion });
    return { ok: true, version: n.version, updatedAt: n.updated_at };
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 409) throw e;
    let current: NoteEntry | null = null;
    try { current = (JSON.parse(e.message) as { current?: NoteEntry | null }).current ?? null; } catch { /* nur Text */ }
    if (!current) return { ok: false, conflict: null };
    const alt = await k.decryptNote<T>(dk, k.aad(kind, key, art), current.iv, current.ciphertext);
    return { ok: false, conflict: { doc: alt, version: current.version, updatedAt: current.updated_at, lesbar: alt != null } };
  }
}

/** Alle Mitschriebe einer Sitzung: Punkt → eigenes Ergebnis. */
export async function sessionTranscripts(dk: CryptoKey, ksinr: number): Promise<Record<string, TranscriptDoc>> {
  const r = await api.get<ApiAntwort<"/notes">>("/notes?target_kind=agenda_item");
  const out: Record<string, TranscriptDoc> = {};
  for (const n of r.notes) {
    if (n.kind !== "transcript" || !n.target_key.startsWith(`${ksinr}|`)) continue;
    const doc = await k.decryptNote<TranscriptDoc>(dk, k.aad(n.target_kind, n.target_key, n.kind), n.iv, n.ciphertext);
    if (doc) out[n.target_key.slice(String(ksinr).length + 1)] = doc;
  }
  return out;
}

/** Was man beim Mitlesen festhält. `outcome` ist die EIGENE Einschätzung,
 *  nie das amtliche Ergebnis. */
export interface TranscriptDoc { text: string; outcome: "accepted" | "rejected" | "postponed" | "noted" | null }

export const deleteDoc = (kind: TargetKind, key: string, art: NoteArt = "note") => api.del<void>(pfad(kind, key, art));

/** Mindestlänge der Passphrase: Sie schützt Notizen gegen jeden, der die
 *  Datenbank bekommt — und lässt sich, anders als ein Login, nicht bremsen. */
export const MIN_PASSPHRASE = 10;
