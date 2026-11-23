import { describe, expect, it } from "vitest";
import {
  fromB64Url, makeInvite, newNoteKey, openBlob, openInvite, sealBlob, toB64Url, unwrapForMe, wrapForMe,
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
