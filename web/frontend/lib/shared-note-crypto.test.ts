import { describe, expect, it } from "vitest";
import {
  fromB64Url, grantFor, inviteVerifier, makeInvite, newIdentity, newNoteKey, openBlob, openGrant, openIdentity,
  openInvite, sealBlob, toB64Url, unwrapForMe, wrapForMe,
} from "./shared-note-crypto";

const dk = () => crypto.subtle.importKey("raw", crypto.getRandomValues(new Uint8Array(32)), { name: "AES-GCM" }, false,
  ["encrypt", "decrypt"]);
const text = (s: string) => new TextEncoder().encode(s);

describe("Schlüssel gemeinsamer Notizen", () => {
  it("jedes Mitglied packt mit seinem eigenen Datenschlüssel, ein fremder öffnet nichts", async () => {
    const nk = await newNoteKey();
    const anna = await dk();
    const verpackt = await wrapForMe(anna, nk);
    const zurueck = await unwrapForMe(anna, verpackt);
    expect(zurueck?.raw).toEqual(nk.raw);
    expect(await unwrapForMe(await dk(), verpackt)).toBeNull();
  });

  it("die Einladung öffnet nur das Geheimnis aus dem Anker", async () => {
    const nk = await newNoteKey();
    const { secret, sealed } = await makeInvite(nk);
    expect(secret).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect((await openInvite(secret, sealed))?.raw).toEqual(nk.raw);
    const anderes = (await makeInvite(nk)).secret;
    expect(await openInvite(anderes, sealed)).toBeNull();
    expect(await openInvite(secret.slice(0, 20), sealed)).toBeNull();
    expect(await openInvite("kein+gültiges/zeichen", sealed)).toBeNull();
  });

  it("der Nachweis passt zum Hash beim Server und öffnet selbst nichts", async () => {
    const nk = await newNoteKey();
    const { secret, sealed, verifierHash } = await makeInvite(nk);
    const v = await inviteVerifier(secret);
    const b64 = (u: Uint8Array) => btoa(String.fromCharCode(...u));
    const raw = Uint8Array.from(atob(v!), (c) => c.charCodeAt(0));
    expect(raw.length).toBe(32);
    expect(b64(new Uint8Array(await crypto.subtle.digest("SHA-256", raw)))).toBe(verifierHash);
    // Ein anderes Geheimnis ergibt einen anderen Nachweis.
    expect(await inviteVerifier((await makeInvite(nk)).secret)).not.toBe(v);
    expect(await inviteVerifier(secret.slice(0, 20))).toBeNull();
    // Als Schlüssel benutzt, öffnet der Nachweis die Einladung nicht.
    const alsSchluessel = await crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, ["decrypt"]);
    const iv = Uint8Array.from(atob(sealed.iv), (c) => c.charCodeAt(0));
    const ct = Uint8Array.from(atob(sealed.ct), (c) => c.charCodeAt(0));
    await expect(crypto.subtle.decrypt({ name: "AES-GCM", iv, additionalData: text("ratslotse-geteilter-schluessel-v1") },
      alsSchluessel, ct)).rejects.toThrow();
  });

  it("Inhalte gehören zu ihrer Notiz und ihrer Art", async () => {
    const nk = await newNoteKey();
    const blob = await sealBlob(nk, "notiz-a", "update", text("Hallo"));
    expect(new TextDecoder().decode((await openBlob(nk, "notiz-a", "update", blob))!)).toBe("Hallo");
    expect(await openBlob(nk, "notiz-b", "update", blob)).toBeNull();
    expect(await openBlob(nk, "notiz-a", "snapshot", blob)).toBeNull();
    expect(await openBlob(await newNoteKey(), "notiz-a", "update", blob)).toBeNull();
  });

  it("base64url hin und zurück", () => {
    const u = new Uint8Array([251, 255, 0, 62, 63]);
    expect(fromB64Url(toB64Url(u))).toEqual(u);
    expect(toB64Url(u)).not.toMatch(/[+/=]/);
  });
});

describe("Einladen per Adresse", () => {
  it("das Schlüsselpaar öffnet nur der eigene Datenschlüssel, und die Hälften gehören zusammen", async () => {
    const ben = await dk();
    const { identity, stored } = await newIdentity(ben);
    expect(stored.public_key).toBe(identity.publicKey);
    expect((await openIdentity(ben, stored))?.publicKey).toBe(stored.public_key);
    expect(await openIdentity(await dk(), stored)).toBeNull();
    // Ein fremder öffentlicher Schlüssel neben dem eigenen privaten fällt auf.
    const fremd = (await newIdentity(ben)).stored.public_key;
    expect(await openIdentity(ben, { ...stored, public_key: fremd })).toBeNull();
  });

  it("die Übergabe öffnet nur das eingeladene Konto, für diese Notiz", async () => {
    const nk = await newNoteKey();
    const ben = (await newIdentity(await dk())).identity;
    const carla = (await newIdentity(await dk())).identity;
    const g = await grantFor(nk, ben.publicKey, "notiz-a", 17);
    expect((await openGrant(ben, g, "notiz-a", 17))?.raw).toEqual(nk.raw);
    expect(await openGrant(carla, g, "notiz-a", 17)).toBeNull();
    expect(await openGrant(ben, g, "notiz-b", 17)).toBeNull();
    expect(await openGrant(ben, g, "notiz-a", 18)).toBeNull();
    expect(await openGrant(ben, { ...g, ct: g.ct.slice(0, -4) + "AAA=" }, "notiz-a", 17)).toBeNull();
  });
});
