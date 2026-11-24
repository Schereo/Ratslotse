/* Keys and ciphertexts of shared notes (`web/backend/app/routers/shared_notes.py`
   says what the server sees and what it does not).

   - Every shared note has its own note key: 32 random bytes, AES-256-GCM.
   - Every member keeps it wrapped with their OWN data key — the one that
     protects their private notes (`lib/notiz-krypto.ts`).
   - An invite wraps it with a random secret that only lives in the link's
     fragment (`#…`). No browser sends a fragment to a server, so the server
     never holds what opens the invite.
   - Content goes as Yjs updates, each encrypted with the note key; the AAD
     binds it to the note and to its kind, so a blob cannot be replayed into
     another note or passed off as a snapshot.

   Pure WebCrypto; the tests run the same code under Node. */

import { fromB64, toB64 } from "@/lib/notiz-krypto";

const enc = new TextEncoder();
type Bytes = Uint8Array;

export interface Sealed { iv: string; ct: string }

const random = (n: number): Bytes => crypto.getRandomValues(new Uint8Array(n));

const KEY_AAD = enc.encode("ratslotse-geteilter-schluessel-v1");
const INVITE_INFO = enc.encode("ratslotse-einladung-v1");
const VERIFIER_INFO = enc.encode("ratslotse-einladung-nachweis-v1");

async function aes(raw: Bytes, usages: KeyUsage[] = ["encrypt", "decrypt"]): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, usages);
}

async function seal(key: CryptoKey, data: Bytes, aad: Bytes): Promise<Sealed> {
  const iv = random(12);
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad }, key, data);
  return { iv: toB64(iv), ct: toB64(new Uint8Array(ct)) };
}

async function open(key: CryptoKey, s: Sealed, aad: Bytes): Promise<Bytes | null> {
  try {
    return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(s.iv), additionalData: aad },
      key, fromB64(s.ct)));
  } catch {
    return null;
  }
}

/** A note key in both forms: raw (to wrap it again — for an invite) and as
 *  a non-extractable key for the content. */
export interface NoteKey { raw: Bytes; key: CryptoKey }

export async function newNoteKey(): Promise<NoteKey> {
  const raw = random(32);
  return { raw, key: await aes(raw) };
}

export async function noteKeyFromRaw(raw: Bytes): Promise<NoteKey> {
  return { raw, key: await aes(raw) };
}

/** Wrapped with the member's own data key — what the server stores per member. */
export async function wrapForMe(dk: CryptoKey, nk: NoteKey): Promise<Sealed> {
  return seal(dk, nk.raw, KEY_AAD);
}

export async function unwrapForMe(dk: CryptoKey, s: Sealed): Promise<NoteKey | null> {
  const raw = await open(dk, s, KEY_AAD);
  return raw && raw.length === 32 ? noteKeyFromRaw(raw) : null;
}

/** base64url without padding — fits into a URL fragment as it is. */
export function toB64Url(u8: Bytes): string {
  return toB64(u8).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function fromB64Url(s: string): Bytes | null {
  if (!/^[A-Za-z0-9_-]+$/.test(s)) return null;
  const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
  try {
    return fromB64(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  } catch {
    return null;
  }
}

async function inviteKey(secret: Bytes): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", secret, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: INVITE_INFO },
    base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

/** Proof that someone holds the link's secret — derived with its own HKDF
 *  label, so it opens nothing. The server keeps only its SHA-256 and asks
 *  for the proof itself on joining: the invite id alone (visible part of the
 *  link, may end up in logs) is not enough to join. */
async function verifierBytes(secret: Bytes): Promise<Bytes> {
  const base = await crypto.subtle.importKey("raw", secret, "HKDF", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits(
    { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: VERIFIER_INFO }, base, 256));
}

/** An invite: the note key sealed with a fresh secret. The secret goes into
 *  the link's fragment; the sealed key and the hash of the proof go to the server. */
export async function makeInvite(nk: NoteKey): Promise<{ secret: string; sealed: Sealed; verifierHash: string }> {
  const secret = random(32);
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", await verifierBytes(secret)));
  return {
    secret: toB64Url(secret),
    sealed: await seal(await inviteKey(secret), nk.raw, KEY_AAD),
    verifierHash: toB64(hash),
  };
}

/** The proof to send when joining; `null` for a malformed secret. */
export async function inviteVerifier(secret: string): Promise<string | null> {
  const raw = fromB64Url(secret);
  if (!raw || raw.length !== 32) return null;
  return toB64(await verifierBytes(raw));
}

/** `null`: the secret does not fit (wrong or cut-off link). */
export async function openInvite(secret: string, sealed: Sealed): Promise<NoteKey | null> {
  const raw = fromB64Url(secret);
  if (!raw || raw.length !== 32) return null;
  const nk = await open(await inviteKey(raw), sealed, KEY_AAD);
  return nk && nk.length === 32 ? noteKeyFromRaw(nk) : null;
}

export type BlobKind = "update" | "snapshot" | "awareness";

const blobAad = (noteId: string, kind: BlobKind) => enc.encode(`ratslotse-geteilt|${noteId}|${kind}`);

export async function sealBlob(nk: NoteKey, noteId: string, kind: BlobKind, data: Bytes): Promise<Sealed> {
  return seal(nk.key, data, blobAad(noteId, kind));
}

export async function openBlob(nk: NoteKey, noteId: string, kind: BlobKind, s: Sealed): Promise<Bytes | null> {
  return open(nk.key, s, blobAad(noteId, kind));
}
