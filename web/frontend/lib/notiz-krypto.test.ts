import { describe, expect, it } from "vitest";
import {
  aad, decryptNote, encodeRecovery, encryptNote, fromB64, parseRecovery, rewrap, setup, toB64,
  unlockWithPassphrase, unlockWithRecovery,
} from "./notiz-krypto";

const fill = (n: number, b: number) => new Uint8Array(n).fill(b);
const hex = (s: string) => new Uint8Array(s.match(/../g)!.map((h) => parseInt(h, 16)));
const PASS = "korrekt Pferd Batterie Heftklammer";
const ZIEL = aad("agenda_item", "4654|Ö 11.1", "note");

/* Testvektoren — dieselben muss die App (CryptoKit) bestehen. Eingaben:
   DK = 32 × 0x11, Salz = 16 × 0x22, Code = 20 × 0x33, IV = 12 × 0x44,
   600.000 Runden, Passphrase wie oben. */
const VEKTOR = {
  salt: "IiIiIiIiIiIiIiIiIiIiIg==",
  wrapped_passphrase: "KZBQ5RLifL4peGycImj2c/TFMBLLQD6pyJn5xC+fiNRbFyGjeDlT9A==",
  wrapped_recovery: "9HwcefHPWDI9QlFn+K8vRoyz3naFbfeXB9Ea5l/dfpcD/68sZgdhgw==",
  code: "6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK",
  iv: "RERERERERERERERE",
  ciphertext: "t2c8CzJMBg3L3v7+QIwFjf+vogGYRlCkozaPQw77GOslQbf6gzCYHfo/jpJlYbwJEEk5",
};

describe("Bausteine gegen veröffentlichte Vektoren", () => {
  it("PBKDF2-HMAC-SHA-256 (RFC 7914, § 11)", async () => {
    const basis = await crypto.subtle.importKey("raw", new TextEncoder().encode("passwd"), "PBKDF2", false, ["deriveBits"]);
    const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: new TextEncoder().encode("salt"), iterations: 1 }, basis, 512);
    expect(toB64(new Uint8Array(bits))).toBe(toB64(hex(
      "55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc49ca9cccf179b645991664b39d77ef317c71b845b1e30bd509112041d3a19783")));
  });
  it("AES-KW mit 256-Bit-Schlüssel (RFC 3394, § 4.6)", async () => {
    const kek = await crypto.subtle.importKey("raw", hex("000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F"), "AES-KW", false, ["wrapKey"]);
    const daten = await crypto.subtle.importKey("raw", hex("00112233445566778899AABBCCDDEEFF000102030405060708090A0B0C0D0E0F"), "AES-GCM", true, ["encrypt"]);
    const w = new Uint8Array(await crypto.subtle.wrapKey("raw", daten, kek, "AES-KW"));
    expect(toB64(w)).toBe(toB64(hex("28C9F404C4B810F4CBCCB35CFB87F8263F5786E2D80ED326CBC7F0E71A99F43BFB988B9B7A02DD21")));
  });
});

describe("Notiz-Schlüssel", () => {
  it("Testvektor: Einrichten, Verpacken, Verschlüsseln", async () => {
    const r = await setup(PASS, { dk: fill(32, 0x11), salt: fill(16, 0x22), code: fill(20, 0x33) });
    expect(r.keys).toEqual({ key_version: 1, kdf: "pbkdf2-sha256", iterations: 600_000, salt: VEKTOR.salt,
      wrapped_passphrase: VEKTOR.wrapped_passphrase, wrapped_recovery: VEKTOR.wrapped_recovery });
    expect(r.recoveryCode).toBe(VEKTOR.code);
    const n = await encryptNote(r.dk, ZIEL, { text: "Nachfragen: Kosten 2027?" }, fill(12, 0x44));
    expect(n).toEqual({ iv: VEKTOR.iv, ciphertext: VEKTOR.ciphertext });
  });

  it("entsperren mit Passphrase; die falsche scheitert sauber", async () => {
    const keys = { ...VEKTOR, iterations: 600_000 };
    const dk = await unlockWithPassphrase(keys, PASS);
    expect(await decryptNote(dk!, ZIEL, VEKTOR.iv, VEKTOR.ciphertext)).toEqual({ text: "Nachfragen: Kosten 2027?" });
    expect(await unlockWithPassphrase(keys, "korrekt Pferd Batterie")).toBeNull();
    // Nicht exportierbar: Wer die Sitzung kapert, bekommt den Schlüssel nicht heraus.
    await expect(crypto.subtle.exportKey("raw", dk!)).rejects.toThrow();
  });

  it("Wiederherstellung über den Code, auch klein und mit Verwechslern getippt", async () => {
    const getippt = "6csk 6csk-6CSK6CSK 6CSK-6CSK-6CSK-6CSK";
    const dk = await unlockWithRecovery(VEKTOR, getippt);
    expect(await decryptNote(dk!, ZIEL, VEKTOR.iv, VEKTOR.ciphertext)).toEqual({ text: "Nachfragen: Kosten 2027?" });
    expect(await unlockWithRecovery(VEKTOR, "6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSM")).toBeNull();
    expect(await unlockWithRecovery(VEKTOR, "zu kurz")).toBeNull();
  });

  it("neue Passphrase: alte Notizen bleiben lesbar, die alte Passphrase nicht", async () => {
    const dk = await unlockWithRecovery(VEKTOR, VEKTOR.code);
    const neu = await rewrap(dk!, "ganz neue Passphrase", VEKTOR.salt);
    const keys = { ...VEKTOR, ...neu };
    const wieder = await unlockWithPassphrase(keys, "ganz neue Passphrase");
    expect(await decryptNote(wieder!, ZIEL, VEKTOR.iv, VEKTOR.ciphertext)).toEqual({ text: "Nachfragen: Kosten 2027?" });
    expect(await unlockWithPassphrase(keys, PASS)).toBeNull();
    // Der Code öffnet weiter: Er ist nicht mitverpackt worden.
    expect(await unlockWithRecovery(keys, VEKTOR.code)).not.toBeNull();
  });
});

describe("Notizen", () => {
  it("frischer IV je Speichern, kein Klartext im Geheimtext", async () => {
    const r = await setup(PASS, { iterations: 300_000 });
    const a = await encryptNote(r.dk, ZIEL, { text: "Geheimnis am Rathausmarkt" });
    const b = await encryptNote(r.dk, ZIEL, { text: "Geheimnis am Rathausmarkt" });
    expect(a.iv).not.toBe(b.iv);
    expect(a.ciphertext).not.toBe(b.ciphertext);
    expect(new TextDecoder().decode(fromB64(a.ciphertext))).not.toContain("Rathausmarkt");
  });

  it("eine an einen anderen Punkt gehängte Notiz lässt sich nicht lesen", async () => {
    const dk = await unlockWithPassphrase({ ...VEKTOR, iterations: 600_000 }, PASS);
    const fremd = aad("agenda_item", "4654|Ö 9", "note");
    expect(await decryptNote(dk!, fremd, VEKTOR.iv, VEKTOR.ciphertext)).toBeNull();
  });
});

describe("Wiederherstellungscode", () => {
  it("hin und zurück, 8 Gruppen zu 4", () => {
    const roh = crypto.getRandomValues(new Uint8Array(20));
    const code = encodeRecovery(roh);
    expect(code).toMatch(/^([0-9A-HJKMNP-TV-Z]{4}-){7}[0-9A-HJKMNP-TV-Z]{4}$/);
    expect(parseRecovery(code)).toEqual(roh);
    expect(parseRecovery(code.replace(/-/g, " ").toLowerCase())).toEqual(roh);
    expect(parseRecovery("UUUU-UUUU-UUUU-UUUU-UUUU-UUUU-UUUU-UUUU")).toBeNull();   // U gibt es nicht
  });
});
