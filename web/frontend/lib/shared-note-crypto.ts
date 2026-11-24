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
   - Inviting a specific account: every account has a key pair (ECDH P-256),
     the private half wrapped with its own data key. A member seals the note
     key for the invitee's public key (ephemeral ECDH + HKDF + AES-GCM, the
     AAD binds it to the note and to the invitee). The safety code is a short
     digest of a public key that two people can compare.

   Pure WebCrypto; the tests run the same code under Node. */

import { fromB64, toB64 } from "@/lib/notiz-krypto";

const enc = new TextEncoder();
type Bytes = Uint8Array;

export interface Sealed { iv: string; ct: string }

const random = (n: number): Bytes => crypto.getRandomValues(new Uint8Array(n));

const KEY_AAD = enc.encode("ratslotse-geteilter-schluessel-v1");
const INVITE_INFO = enc.encode("ratslotse-einladung-v1");
const VERIFIER_INFO = enc.encode("ratslotse-einladung-nachweis-v1");
const IDENTITY_AAD = enc.encode("ratslotse-identitaet-v1");
const GRANT_INFO = enc.encode("ratslotse-uebergabe-v1");
const ECDH = { name: "ECDH", namedCurve: "P-256" } as const;

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

/* ---- Inviting a specific account ---------------------------------------- */

/** The own key pair: public raw (65 bytes, base64), private as a
 *  non-extractable key. */
export interface Identity { publicKey: string; privateKey: CryptoKey }

/** What the server keeps (`PUT /shared-notes/identity`). */
export interface StoredIdentity { public_key: string; private_iv: string; private_ct: string }

export async function newIdentity(dk: CryptoKey): Promise<{ identity: Identity; stored: StoredIdentity }> {
  const pair = await crypto.subtle.generateKey(ECDH, true, ["deriveBits"]);
  const pub = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", pair.privateKey));
  const sealed = await seal(dk, pkcs8, IDENTITY_AAD);
  const privateKey = await crypto.subtle.importKey("pkcs8", pkcs8, ECDH, false, ["deriveBits"]);
  pkcs8.fill(0);
  return {
    identity: { publicKey: toB64(pub), privateKey },
    stored: { public_key: toB64(pub), private_iv: sealed.iv, private_ct: sealed.ct },
  };
}

/** `null`: not openable with this data key, or the halves do not belong together. */
export async function openIdentity(dk: CryptoKey, stored: StoredIdentity): Promise<Identity | null> {
  const pkcs8 = await open(dk, { iv: stored.private_iv, ct: stored.private_ct }, IDENTITY_AAD);
  if (!pkcs8) return null;
  try {
    // Gehört der private Teil zum öffentlichen, der beim Server liegt? Sonst
    // verpackten andere für einen Schlüssel, den hier niemand öffnen kann.
    const probe = await crypto.subtle.importKey("pkcs8", pkcs8, ECDH, true, ["deriveBits"]);
    const jwk = await crypto.subtle.exportKey("jwk", probe);
    const pub = fromB64(stored.public_key);
    const xy = toB64Url(pub.slice(1, 33)) + "." + toB64Url(pub.slice(33));
    if (pub[0] !== 4 || `${jwk.x}.${jwk.y}` !== xy) return null;
    const privateKey = await crypto.subtle.importKey("pkcs8", pkcs8, ECDH, false, ["deriveBits"]);
    return { publicKey: stored.public_key, privateKey };
  } catch {
    return null;
  } finally {
    pkcs8.fill(0);
  }
}

export interface Grant { epk: string; iv: string; ct: string }

const grantAad = (noteId: string, userId: number) => enc.encode(`ratslotse-uebergabe|${noteId}|${userId}`);

async function grantKey(shared: Bytes, epk: Bytes, recipient: Bytes): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", shared, "HKDF", false, ["deriveKey"]);
  const salt = new Uint8Array(epk.length + recipient.length);
  salt.set(epk);
  salt.set(recipient, epk.length);
  return crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt, info: GRANT_INFO }, base,
    { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

/** The note key sealed for one account's public key. */
export async function grantFor(nk: NoteKey, recipientPublic: string, noteId: string, recipientId: number): Promise<Grant> {
  const rpub = fromB64(recipientPublic);
  const recipient = await crypto.subtle.importKey("raw", rpub, ECDH, false, []);
  const eph = await crypto.subtle.generateKey(ECDH, false, ["deriveBits"]);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: recipient }, eph.privateKey, 256));
  const epk = new Uint8Array(await crypto.subtle.exportKey("raw", eph.publicKey));
  const s = await seal(await grantKey(shared, epk, rpub), nk.raw, grantAad(noteId, recipientId));
  shared.fill(0);
  return { epk: toB64(epk), iv: s.iv, ct: s.ct };
}

/** `null`: not for this key pair, not for this note or not for this account. */
export async function openGrant(me: Identity, grant: Grant, noteId: string, myId: number): Promise<NoteKey | null> {
  try {
    const epk = fromB64(grant.epk);
    const pub = await crypto.subtle.importKey("raw", epk, ECDH, false, []);
    const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: pub }, me.privateKey, 256));
    const raw = await open(await grantKey(shared, epk, fromB64(me.publicKey)), grant, grantAad(noteId, myId));
    shared.fill(0);
    return raw && raw.length === 32 ? noteKeyFromRaw(raw) : null;
  } catch {
    return null;
  }
}

/** Five groups of five digits from the SHA-256 of a public key — short
 *  enough to read out on the phone, long enough that nobody forges a match. */
export async function safetyCode(publicKey: string): Promise<string> {
  const h = new Uint8Array(await crypto.subtle.digest("SHA-256", fromB64(publicKey)));
  const groups: string[] = [];
  for (let i = 0; i < 15; i += 3) groups.push(String(((h[i] << 16) | (h[i + 1] << 8) | h[i + 2]) % 100000).padStart(5, "0"));
  return groups.join(" ");
}
