/* Verschlüsselung der Notizen — nur hier, nur mit WebCrypto
   (`docs/plan-notizen-verschluesselt.md`, § 3).

   - Datenschlüssel DK: AES-256-GCM, entsteht auf dem Gerät.
   - Verpackt (AES-KW) zweimal: mit einem Schlüssel aus der Notiz-Passphrase
     (PBKDF2-SHA-256, 600.000 Runden, 16 Byte Salz) und mit einem aus dem
     Wiederherstellungscode (160 Bit Zufall, HKDF-SHA-256). Beim Server liegt
     nur die Verpackung.
   - Jede Notiz: AES-GCM mit frischem 12-Byte-IV; das Ziel („agenda_item|
     4654|Ö 11.1|note") ist als Zusatzdaten gebunden — der Server kann eine
     Notiz nicht unbemerkt an einen anderen Punkt hängen.

   AES-KW und AES-GCM mit festem IV sind deterministisch; die Testvektoren in
   `notiz-krypto.test.ts` sind deshalb dieselben, die die App (CryptoKit)
   bestehen muss — ohne sie wäre „Web und App lesen dieselben Daten" eine
   Behauptung. */

export const KDF = "pbkdf2-sha256" as const;
export const ITERATIONS = 600_000;
export const KEY_VERSION = 1;
const RECOVERY_INFO = "ratslotse-notizen-wiederherstellung";
/** Crockford-Base32: ohne I, L, O, U — nichts, was man beim Abtippen verwechselt. */
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

const enc = new TextEncoder();
const dec = new TextDecoder();
type Bytes = Uint8Array;
const bytes = (n: number): Bytes => crypto.getRandomValues(new Uint8Array(n));

export function toB64(u8: Uint8Array): string {
  let s = "";
  for (const b of u8) s += String.fromCharCode(b);
  return btoa(s);
}

export function fromB64(s: string): Bytes {
  const roh = atob(s);
  const out = new Uint8Array(roh.length);
  for (let i = 0; i < roh.length; i++) out[i] = roh.charCodeAt(i);
  return out;
}

/** 20 Byte → „ABCD-EFGH-…" in 8 Gruppen zu 4 Zeichen. */
export function encodeRecovery(code: Uint8Array): string {
  let bits = 0, wert = 0, out = "";
  for (const b of code) {
    wert = (wert << 8) | b;
    bits += 8;
    while (bits >= 5) {
      out += ALPHABET[(wert >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) out += ALPHABET[(wert << (5 - bits)) & 31];
  return out.match(/.{1,4}/g)!.join("-");
}

/** Abgetippter Code → 20 Byte, oder `null`. Groß/klein, Leerzeichen und
 *  Bindestriche egal; O liest sich als 0, I und L als 1. */
export function parseRecovery(eingabe: string): Bytes | null {
  const s = eingabe.toUpperCase().replace(/[\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1");
  if (s.length !== 32) return null;
  const out = new Uint8Array(20);
  let bits = 0, wert = 0, i = 0;
  for (const ch of s) {
    const v = ALPHABET.indexOf(ch);
    if (v < 0) return null;
    wert = ((wert << 5) | v) & 0xffff;
    bits += 5;
    if (bits >= 8) {
      out[i++] = (wert >>> (bits - 8)) & 0xff;
      bits -= 8;
    }
  }
  return out;
}

export async function passphraseKek(passphrase: string, salt: Bytes, iterations = ITERATIONS): Promise<CryptoKey> {
  const basis = await crypto.subtle.importKey("raw", enc.encode(passphrase.normalize("NFC")), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt, iterations }, basis,
    { name: "AES-KW", length: 256 }, false, ["wrapKey", "unwrapKey"]);
}

export async function recoveryKek(code: Bytes, salt: Bytes): Promise<CryptoKey> {
  const basis = await crypto.subtle.importKey("raw", code, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt, info: enc.encode(RECOVERY_INFO) }, basis,
    { name: "AES-KW", length: 256 }, false, ["wrapKey", "unwrapKey"]);
}

export async function wrap(dk: CryptoKey, kek: CryptoKey): Promise<string> {
  return toB64(new Uint8Array(await crypto.subtle.wrapKey("raw", dk, kek, "AES-KW")));
}

/** Auspacken; `null` bei falscher Passphrase oder falschem Code (AES-KW
 *  prüft die Unversehrtheit selbst). Nicht exportierbar, außer man will
 *  danach neu verpacken. */
export async function unwrap(wrapped: string, kek: CryptoKey, extractable = false): Promise<CryptoKey | null> {
  try {
    return await crypto.subtle.unwrapKey("raw", fromB64(wrapped), kek, "AES-KW",
      { name: "AES-GCM", length: 256 }, extractable, ["encrypt", "decrypt"]);
  } catch {
    return null;
  }
}

export interface WrappedKeys {
  key_version: number;
  kdf: typeof KDF;
  iterations: number;
  salt: string;
  wrapped_passphrase: string;
  wrapped_recovery: string;
}

/** Einrichten ohne Passphrase (Passkey, `lib/notiz-passkey.ts`): ein neuer,
 *  exportierbarer Datenschlüssel und das Salz, mit dem später eine Passphrase
 *  oder ein Notfall-Code verpackt würde. Exportierbar nur für das Verpacken;
 *  für die Sitzung gilt danach die nicht exportierbare Fassung. */
export async function neuerSchluessel(): Promise<{ dk: CryptoKey; basis: Pick<WrappedKeys, "key_version" | "kdf" | "iterations" | "salt"> }> {
  const dk = await crypto.subtle.importKey("raw", bytes(32), { name: "AES-GCM" }, true, ["encrypt", "decrypt"]);
  return { dk, basis: { key_version: KEY_VERSION, kdf: KDF, iterations: ITERATIONS, salt: toB64(bytes(16)) } };
}

/** Eine nicht exportierbare Fassung desselben Schlüssels für die Sitzung. */
export async function nurBenutzbar(dkExtractable: CryptoKey): Promise<CryptoKey> {
  const roh = await crypto.subtle.exportKey("raw", dkExtractable);
  return crypto.subtle.importKey("raw", roh, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

/** Ein Notfall-Code, freiwillig und nachträglich: verpackt denselben
 *  Datenschlüssel mit demselben Salz. */
export async function notfallCode(dkExtractable: CryptoKey, salt: string, code: Bytes = bytes(20)):
  Promise<{ recoveryCode: string; wrapped_recovery: string }> {
  return { recoveryCode: encodeRecovery(code), wrapped_recovery: await wrap(dkExtractable, await recoveryKek(code, fromB64(salt))) };
}

/** Einrichten: neuer Datenschlüssel, beide Verpackungen, der Code zum Zeigen. */
export async function setup(passphrase: string, opts: { dk?: Bytes; salt?: Bytes; code?: Bytes; iterations?: number } = {}):
  Promise<{ keys: WrappedKeys; recoveryCode: string; dk: CryptoKey }> {
  const salt = opts.salt ?? bytes(16);
  const code = opts.code ?? bytes(20);
  const iterations = opts.iterations ?? ITERATIONS;
  const roh = opts.dk ?? bytes(32);
  const exportierbar = await crypto.subtle.importKey("raw", roh, { name: "AES-GCM" }, true, ["encrypt", "decrypt"]);
  const kekP = await passphraseKek(passphrase, salt, iterations);
  const keys: WrappedKeys = {
    key_version: KEY_VERSION, kdf: KDF, iterations, salt: toB64(salt),
    wrapped_passphrase: await wrap(exportierbar, kekP),
    wrapped_recovery: await wrap(exportierbar, await recoveryKek(code, salt)),
  };
  const dk = (await unwrap(keys.wrapped_passphrase, kekP))!;
  return { keys, recoveryCode: encodeRecovery(code), dk };
}

/** Verpackungen können fehlen (seit den Passkeys: `null`). */
type Verpackt = { salt: string; iterations: number; wrapped_passphrase: string | null; wrapped_recovery: string | null };

export async function unlockWithPassphrase(keys: Pick<Verpackt, "salt" | "iterations" | "wrapped_passphrase">,
  passphrase: string, extractable = false): Promise<CryptoKey | null> {
  if (!keys.wrapped_passphrase) return null;
  return unwrap(keys.wrapped_passphrase, await passphraseKek(passphrase, fromB64(keys.salt), keys.iterations), extractable);
}

/** Mit dem Code entsperren — exportierbar, denn danach kommt eine neue Passphrase. */
export async function unlockWithRecovery(keys: Pick<Verpackt, "salt" | "wrapped_recovery">, code: string):
  Promise<CryptoKey | null> {
  const roh = parseRecovery(code);
  if (!roh || !keys.wrapped_recovery) return null;
  return unwrap(keys.wrapped_recovery, await recoveryKek(roh, fromB64(keys.salt)), true);
}

/** Neue Passphrase für einen exportierbaren Datenschlüssel. Das Salz bleibt:
 *  Der Wiederherstellungscode ist mit demselben verpackt. */
export async function rewrap(dkExtractable: CryptoKey, passphrase: string, salt: string, iterations = ITERATIONS):
  Promise<{ kdf: typeof KDF; iterations: number; salt: string; wrapped_passphrase: string }> {
  const kek = await passphraseKek(passphrase, fromB64(salt), iterations);
  return { kdf: KDF, iterations, salt, wrapped_passphrase: await wrap(dkExtractable, kek) };
}

export function aad(targetKind: string, targetKey: string, kind: string): Bytes {
  return enc.encode(`${targetKind}|${targetKey}|${kind}`);
}

export async function encryptNote(dk: CryptoKey, zusatz: Bytes, doc: unknown, iv: Bytes = bytes(12)):
  Promise<{ iv: string; ciphertext: string }> {
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: zusatz }, dk, enc.encode(JSON.stringify(doc)));
  return { iv: toB64(iv), ciphertext: toB64(new Uint8Array(ct)) };
}

/** `null`, wenn der Schlüssel nicht passt oder Ziel/Text verändert wurden. */
export async function decryptNote<T = unknown>(dk: CryptoKey, zusatz: Bytes, iv: string, ciphertext: string): Promise<T | null> {
  try {
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(iv), additionalData: zusatz }, dk, fromB64(ciphertext));
    return JSON.parse(dec.decode(pt)) as T;
  } catch {
    return null;
  }
}
