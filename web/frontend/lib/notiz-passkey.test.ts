import { describe, expect, it } from "vitest";
import { encryptNote, decryptNote, aad, neuerSchluessel, nurBenutzbar, notfallCode, unlockWithRecovery, unwrap, wrap } from "./notiz-krypto";
import { fromB64url, geraeteName, passkeyKek, toB64url } from "./notiz-passkey";

describe("Base64url für Passkey-Kennungen", () => {
  it("hin und zurück, ohne Füllzeichen und ohne + /", () => {
    for (const n of [1, 15, 16, 31, 32, 64]) {
      const roh = crypto.getRandomValues(new Uint8Array(n));
      const s = toB64url(roh);
      expect(s).toMatch(/^[A-Za-z0-9_-]+$/);
      expect([...fromB64url(s)]).toEqual([...roh]);
    }
  });
});

describe("geraeteName", () => {
  it("nennt grob das Gerät", () => {
    expect(geraeteName("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)")).toBe("iPhone");
    expect(geraeteName("Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0)")).toBe("Mac");
    expect(geraeteName("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")).toBe("Windows");
    expect(geraeteName("Mozilla/5.0 (Linux; Android 15)")).toBe("Android");
    expect(geraeteName("")).toBe("Gerät");
  });
});

describe("Verpacken mit dem PRF-Geheimnis", () => {
  it("dasselbe Geheimnis packt aus, ein anderes nicht", async () => {
    const { dk } = await neuerSchluessel();
    const prf = new Uint8Array(32).fill(0x5a);
    const verpackt = await wrap(dk, await passkeyKek(prf));
    expect(await unwrap(verpackt, await passkeyKek(prf))).not.toBeNull();
    expect(await unwrap(verpackt, await passkeyKek(new Uint8Array(32).fill(0x5b)))).toBeNull();
  });

  it("eine mit dem Passkey-Schlüssel geschriebene Notiz liest der Notfall-Code genauso", async () => {
    const { dk, basis } = await neuerSchluessel();
    const sitzung = await nurBenutzbar(dk);
    const ziel = aad("decision", "8525", "note");
    const blob = await encryptNote(sitzung, ziel, { text: "Kosten 2027 nachfragen" });
    const code = await notfallCode(dk, basis.salt);
    const ausCode = await unlockWithRecovery({ salt: basis.salt, wrapped_recovery: code.wrapped_recovery }, code.recoveryCode);
    expect(await decryptNote(ausCode!, ziel, blob.iv, blob.ciphertext)).toEqual({ text: "Kosten 2027 nachfragen" });
    // Die Sitzungsfassung gibt den Schlüssel nicht heraus.
    await expect(crypto.subtle.exportKey("raw", sitzung)).rejects.toThrow();
  });

  it("ohne Passphrase oder Code gibt es nichts zu entsperren", async () => {
    expect(await unlockWithRecovery({ salt: "IiIiIiIiIiIiIiIiIiIiIg==", wrapped_recovery: null }, "6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK")).toBeNull();
  });
});
