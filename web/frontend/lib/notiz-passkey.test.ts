import { describe, expect, it } from "vitest";
import { encryptNote, decryptNote, aad, neuerSchluessel, nurBenutzbar, notfallCode, unlockWithRecovery, unwrap, wrap } from "./notiz-krypto";
import { browserFehler, fromB64url, geraeteName, imSchritt, passkeyKek, PasskeyFehler, prfBeschreibung, prfBytes, TECHNISCH, toB64url } from "./notiz-passkey";

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

  it("ergibt dieselben Bytes wie die App (Testvektor aus `PasskeysTests.swift`)", async () => {
    // PRF = 32 × 0x5a, DK = 32 × 0x11. Ändert sich hier etwas, schließt derselbe
    // Passkey im Browser auf und in der App nicht mehr.
    const dk = await crypto.subtle.importKey("raw", new Uint8Array(32).fill(0x11), { name: "AES-GCM" }, true,
      ["encrypt", "decrypt"]);
    expect(await wrap(dk, await passkeyKek(new Uint8Array(32).fill(0x5a))))
      .toBe("waaUYZJ0tt9nEz/QzsW1KcByiM15SL79fCqUXiHHzi+Kn7T2/i5PwA==");
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

describe("Rohe Ausnahmen des Browsers", () => {
  // 12.11.2026, Tims Safari: nur dieser Satz stand unter „Mit Passkey einrichten“.
  const safari = () => new DOMException("Data provided to an operation does not meet requirements", "DataError");

  it("werden zu einem deutschen Satz, Schritt und Ursache bleiben fürs Protokoll", () => {
    const x = browserFehler(safari(), "verpacken");
    expect(x).toBeInstanceOf(PasskeyFehler);
    const f = x as PasskeyFehler;
    expect(f.art).toBe("technisch");
    expect(f.message).toBe(TECHNISCH);
    expect(f.message).not.toMatch(/Data provided/);
    expect(f.schritt).toBe("verpacken");
    expect(f.ursache).toBe("DataError: Data provided to an operation does not meet requirements");
  });

  it("ein TypeError aus WebCrypto ebenso", () => {
    expect((browserFehler(new TypeError("Type error"), "Schlüssel ableiten") as PasskeyFehler).art).toBe("technisch");
  });

  it("eigene Fehler mit deutschem Satz bleiben, wie sie sind", () => {
    const eigen = new PasskeyFehler("passt-nicht", "Dieser Passkey passt nicht zu deinen Notizen.");
    expect(browserFehler(eigen, "x")).toBe(eigen);
    const server = new Error("Die Adresse ist noch nicht bestätigt.");
    expect(browserFehler(server, "x")).toBe(server);
  });

  it("imSchritt übersetzt eine Ablehnung und reicht ein Ergebnis durch", async () => {
    await expect(imSchritt("neuer Schlüssel", async () => 7)).resolves.toBe(7);
    await expect(imSchritt("verpacken", async () => { throw safari(); }))
      .rejects.toMatchObject({ art: "technisch", schritt: "verpacken", message: TECHNISCH });
  });

  it("eine echte WebCrypto-Ablehnung kommt als PasskeyFehler an", async () => {
    // AES verlangt 16, 24 oder 32 Byte — genau diese Ablehnung heißt in Safari „DataError“.
    const zuKurz = imSchritt("Sitzungsschlüssel", () =>
      crypto.subtle.importKey("raw", new Uint8Array(31), { name: "AES-GCM" }, false, ["encrypt"]));
    await expect(zuKurz).rejects.toMatchObject({ art: "technisch", schritt: "Sitzungsschlüssel" });
  });
});

describe("PRF-Ergebnis prüfen (13.11.2026: „Schlüssel ableiten: DataError“ in Safari)", () => {
  it("leer, fehlend oder kein Puffer taugt nicht", () => {
    expect(prfBytes(undefined)).toBeNull();
    expect(prfBytes(new ArrayBuffer(0))).toBeNull();
    expect(prfBytes("c2NobMO8c3NlbA")).toBeNull();
    expect(prfBytes({ byteLength: 32 })).toBeNull();
  });

  it("ein abgetrennter (detached) Puffer taugt nicht", () => {
    const b = new ArrayBuffer(32);
    structuredClone(b, { transfer: [b] });
    expect(b.byteLength).toBe(0);
    expect(prfBytes(b)).toBeNull();
  });

  it("eine Sicht in einen größeren Puffer wird zu genau ihren Bytes kopiert", () => {
    const gross = new Uint8Array(64).fill(1);
    gross.fill(0x5a, 16, 48);
    const roh = prfBytes(gross.subarray(16, 48))!;
    expect(roh.byteLength).toBe(32);
    expect(roh.buffer.byteLength).toBe(32);
    expect([...roh]).toEqual(new Array(32).fill(0x5a));
  });

  it("dieselben Bytes über eine Sicht ergeben denselben Schlüssel wie der Testvektor", async () => {
    const dk = await crypto.subtle.importKey("raw", new Uint8Array(32).fill(0x11), { name: "AES-GCM" }, true,
      ["encrypt", "decrypt"]);
    const gross = new Uint8Array(48);
    gross.fill(0x5a, 8, 40);
    expect(await wrap(dk, await passkeyKek(gross.subarray(8, 40))))
      .toBe("waaUYZJ0tt9nEz/QzsW1KcByiM15SL79fCqUXiHHzi+Kn7T2/i5PwA==");
  });

  it("ein leeres Geheimnis führt zur Passphrase und nennt fürs Protokoll Art und Länge", async () => {
    await expect(passkeyKek(new ArrayBuffer(0))).rejects.toMatchObject({
      art: "nicht-unterstuetzt", schritt: "Schlüssel ableiten", ursache: "PRF unbrauchbar: ArrayBuffer, 0 B" });
  });

  it("eine Zahlenliste (1Password in Zen/Firefox) gilt als dieselben Bytes", async () => {
    const liste = new Array(32).fill(0x5a);
    expect([...prfBytes(liste)!]).toEqual(liste);
    expect([...prfBytes(Object.fromEntries(liste.map((n, i) => [String(i), n])))!]).toEqual(liste);
    // derselbe Schlüssel wie aus echten Bytes — Browser und App schließen weiter gleich auf
    const dk = await crypto.subtle.importKey("raw", new Uint8Array(32).fill(0x11), { name: "AES-GCM" }, true,
      ["encrypt", "decrypt"]);
    expect(await wrap(dk, await passkeyKek(liste as unknown as BufferSource)))
      .toBe("waaUYZJ0tt9nEz/QzsW1KcByiM15SL79fCqUXiHHzi+Kn7T2/i5PwA==");
  });

  it("eine Liste, die keine Bytes sind, taugt nicht", () => {
    expect(prfBytes(new Array(32).fill(256))).toBeNull();
    expect(prfBytes(new Array(32).fill(1.5))).toBeNull();
    expect(prfBytes(new Array(32).fill("1"))).toBeNull();
    expect(prfBytes([1, 2, 3])).toBeNull();
    expect(prfBytes({ a: 1 })).toBeNull();
  });

  it("die Beschreibung verrät nie die Bytes", () => {
    expect(prfBeschreibung([1, 2, 3])).toBe("Array, 3 Werte");
    expect(prfBeschreibung(new Uint8Array([1, 2, 3]))).toBe("Uint8Array, 3 B");
    expect(prfBeschreibung(undefined)).toBe("fehlt");
    expect(prfBeschreibung("geheim")).toBe("string");
  });
});
