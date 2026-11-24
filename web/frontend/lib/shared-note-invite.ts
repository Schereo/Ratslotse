/* Inviting a specific account to a shared note (Schalter `notizen-teilen`;
   server side in `web/backend/app/routers/shared_notes.py`).

   1. A member invites by address. The server answers the same whether the
      account exists or not; if it does, the account gets mail or push.
   2. The invitee accepts — that needs their key pair (`ensureIdentity`).
   3. The browser of any member who has the note open seals the note key for
      the invitee's public key (`grantPending`).
   4. The invitee opens it with their private key, wraps it with their own
      data key and joins (`joinInvitation`).

   Why the token: the list of who waits comes from the server. Granting to
   whatever it lists would let a dishonest server invent an invitee and
   collect the note key. So the inviting browser writes a random token into
   the note itself (a Y.Map in the encrypted document, which the server can
   neither read nor forge) and sends the same token along. A member grants
   only to waiting entries whose token is in the note — and removes it
   afterwards, so it works once. */

import type * as Y from "yjs";
import { api } from "@/lib/api";
import {
  grantFor, newIdentity, openGrant, openIdentity, wrapForMe, type Identity, type NoteKey,
} from "@/lib/shared-note-crypto";
import { toB64 } from "@/lib/notiz-krypto";
import type { ApiAntwort } from "@/lib/vertrag";

type IdentityState = ApiAntwort<"/shared-notes/identity">;
type Note = ApiAntwort<"/shared-notes">["notes"][number];
export type Invitation = ApiAntwort<"/shared-notes">["invitations"][number];

/** The own key pair — created (or replaced, if the stored one no longer
 *  opens) on first use. */
export async function ensureIdentity(dk: CryptoKey, keyVersion: number): Promise<Identity> {
  const r = await api.get<IdentityState>("/shared-notes/identity");
  if (r.identity) {
    const i = await openIdentity(dk, r.identity);
    if (i) return i;
  }
  const { identity, stored } = await newIdentity(dk);
  await api.put("/shared-notes/identity", { ...stored, key_version: keyVersion });
  return identity;
}

export async function acceptInvitation(inv: Pick<Invitation, "id">, dk: CryptoKey, keyVersion: number): Promise<Invitation> {
  await ensureIdentity(dk, keyVersion);
  return api.post<Invitation>(`/note-invites/address/${encodeURIComponent(inv.id)}/accept`);
}

export async function declineInvitation(inv: Pick<Invitation, "id">): Promise<void> {
  await api.post(`/note-invites/address/${encodeURIComponent(inv.id)}/decline`);
}

/** Open the handover and join; `null` if it does not open with this key pair. */
export async function joinInvitation(inv: Invitation, dk: CryptoKey, keyVersion: number, meId: number): Promise<Note | null> {
  if (!inv.grant) return null;
  const me = await ensureIdentity(dk, keyVersion);
  const nk = await openGrant(me, inv.grant, inv.note_id, meId);
  if (!nk) return null;
  const w = await wrapForMe(dk, nk);
  return api.post<Note>(`/note-invites/address/${encodeURIComponent(inv.id)}/join`,
    { key_iv: w.iv, key_ct: w.ct, key_version: keyVersion });
}

/** Where the tokens live inside the shared document. */
export const INVITES_MAP = "invites";
const TOKEN_TAGE = 14;

interface Vermerk { by: number; at: number }

/** A fresh token for one invitation, recorded in the note. */
export function recordInvite(doc: Y.Doc, by: number): string {
  const token = toB64(crypto.getRandomValues(new Uint8Array(16)));
  doc.getMap<Vermerk>(INVITES_MAP).set(token, { by, at: Date.now() });
  return token;
}

export function forgetInvite(doc: Y.Doc, token: string): void {
  doc.getMap<Vermerk>(INVITES_MAP).delete(token);
}

/** Is this token one a member of the note put there — and not too old? */
export function isRecorded(doc: Y.Doc, token: string, now = Date.now()): boolean {
  const v = token ? doc.getMap<Vermerk>(INVITES_MAP).get(token) : undefined;
  return Boolean(v && typeof v.at === "number" && now - v.at <= TOKEN_TAGE * 86_400_000);
}

/** Seal the note key for everyone who accepted, is waiting AND was invited
 *  from inside the note (token found in the document). Returns how many
 *  went through (a 409 means another member was faster). */
export async function grantPending(note: Pick<Note, "id" | "pending">, nk: NoteKey, doc: Y.Doc,
  skip: Set<string>): Promise<number> {
  let n = 0;
  for (const p of note.pending) {
    if (skip.has(p.invite_id) || !isRecorded(doc, p.token)) continue;
    skip.add(p.invite_id);
    try {
      const g = await grantFor(nk, p.public_key, note.id, p.user_id);
      await api.post(`/shared-notes/${encodeURIComponent(note.id)}/grants/${encodeURIComponent(p.invite_id)}`,
        { ...g, for_key: p.public_key });
      forgetInvite(doc, p.token);
      n += 1;
    } catch { /* jemand anderes war schneller, oder der Schlüssel hat sich geändert */ }
  }
  return n;
}
