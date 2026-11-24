/* Inviting a specific account to a shared note (Schalter `notizen-teilen`;
   server side in `web/backend/app/routers/shared_notes.py`).

   1. A member invites by address. The server answers the same whether the
      account exists or not; if it does, the account gets mail or push.
   2. The invitee accepts — that needs their key pair (`ensureIdentity`).
   3. The browser of any member who has the note open seals the note key for
      the invitee's public key (`grantPending`).
   4. The invitee opens it with their private key, wraps it with their own
      data key and joins (`joinInvitation`).

   Safety codes: every browser remembers the public key it first saw (or
   sealed for) per account. If the server later shows another one, the
   member list says so — trust on first use, like a messenger. */

import { api } from "@/lib/api";
import {
  grantFor, newIdentity, openGrant, openIdentity, wrapForMe, type Identity, type NoteKey,
} from "@/lib/shared-note-crypto";
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

/** Seal the note key for everyone who accepted and is waiting. Returns how
 *  many went through (a 409 means another member was faster). */
export async function grantPending(note: Pick<Note, "id" | "pending">, nk: NoteKey, skip: Set<string>): Promise<number> {
  let n = 0;
  for (const p of note.pending) {
    if (skip.has(p.invite_id)) continue;
    skip.add(p.invite_id);
    const pinned = pinnedKey(p.user_id);
    // Kennt dieser Browser schon einen anderen Schlüssel für das Konto, nicht
    // still verpacken: Das Mitglied soll erst die Codes vergleichen.
    if (pinned && pinned !== p.public_key) continue;
    try {
      const g = await grantFor(nk, p.public_key, note.id, p.user_id);
      await api.post(`/shared-notes/${encodeURIComponent(note.id)}/grants/${encodeURIComponent(p.invite_id)}`,
        { ...g, for_key: p.public_key });
      pinKey(p.user_id, p.public_key);
      n += 1;
    } catch { /* jemand anderes war schneller, oder der Schlüssel hat sich geändert */ }
  }
  return n;
}

const PINS = "ratslotse:notiz-schluessel";

function pins(): Record<string, string> {
  try {
    const v = JSON.parse(localStorage.getItem(PINS) ?? "{}");
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

export function pinnedKey(userId: number): string | null {
  return pins()[String(userId)] ?? null;
}

export function pinKey(userId: number, publicKey: string): void {
  try {
    localStorage.setItem(PINS, JSON.stringify({ ...pins(), [String(userId)]: publicKey }));
  } catch { /* privat: dann eben ohne Gedächtnis */ }
}
