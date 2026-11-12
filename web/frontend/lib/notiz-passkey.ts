/* Passkeys als Schlüssel zu den Notizen (Tims Entscheidung 11.11.2026: nichts
   merken müssen — keine Passphrase, kein Pflicht-Code).

   Der Passkey meldet hier niemanden an. Er liefert über die WebAuthn-
   Erweiterung PRF zu einem Salz ein festes Geheimnis, das nur er erzeugen
   kann; daraus wird per HKDF der Schlüssel, der den Datenschlüssel verpackt
   (AES-KW, wie bei Passphrase und Code in `lib/notiz-krypto.ts`). Der Server
   bekommt Kennung, Salz und Verpackung — nie das Geheimnis.

   Wo PRF fehlt (ältere Browser, manche Android-Geräte), bleibt die
   Passphrase als Rückfall. */

import { fromB64, toB64, unwrap, wrap } from "@/lib/notiz-krypto";

const PASSKEY_INFO = "ratslotse-notizen-passkey";
const enc = new TextEncoder();

/** Was der Server je Passkey kennt (`NotePasskey` im Vertrag, ohne id). */
export interface PasskeyVerpackung { credential_id: string; prf_salt: string; wrapped_key: string; label: string }
export interface GespeicherterPasskey { credential_id: string; prf_salt: string; wrapped_key: string }

export class PasskeyFehler extends Error {
  constructor(readonly art: "nicht-unterstuetzt" | "abgebrochen" | "passt-nicht" | "schon-da", msg: string) {
    super(msg);
  }
}

export function toB64url(u8: Uint8Array): string {
  return toB64(u8).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function fromB64url(s: string): Uint8Array {
  const b = s.replace(/-/g, "+").replace(/_/g, "/");
  return fromB64(b + "=".repeat((4 - (b.length % 4)) % 4));
}

/** Ein Name für die Liste im Konto — aus dem User-Agent, nur grob. */
export function geraeteName(ua: string): string {
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android";
  if (/Macintosh|Mac OS X/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows";
  if (/Linux/.test(ua)) return "Linux";
  return "Gerät";
}

/** Kann dieser Browser Passkeys mit PRF? Ohne die Abfrage
 *  (`getClientCapabilities` fehlt) optimistisch: Scheitert das Anlegen,
 *  führt der Weg zur Passphrase. */
export async function passkeyMoeglich(): Promise<boolean> {
  if (typeof window === "undefined" || !window.PublicKeyCredential || !navigator.credentials) return false;
  const pkc = PublicKeyCredential as unknown as { getClientCapabilities?: () => Promise<Record<string, boolean>> };
  if (pkc.getClientCapabilities) {
    try {
      const caps = await pkc.getClientCapabilities();
      if ("extension:prf" in caps) return caps["extension:prf"] === true;
    } catch { /* weiter optimistisch */ }
  }
  return true;
}

/** Aus dem PRF-Geheimnis der Schlüssel, der den Datenschlüssel verpackt. */
export async function passkeyKek(prf: BufferSource): Promise<CryptoKey> {
  const basis = await crypto.subtle.importKey("raw", prf, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: enc.encode(PASSKEY_INFO) },
    basis, { name: "AES-KW", length: 256 }, false, ["wrapKey", "unwrapKey"]);
}

/** Stabil je Konto: Ein zweites Anlegen auf demselben Gerät ersetzt den alten
 *  Passkey, statt einen zweiten danebenzulegen. */
async function nutzerKennung(owner: number): Promise<Uint8Array> {
  const h = await crypto.subtle.digest("SHA-256", enc.encode(`ratslotse-notizen|${owner}`));
  return new Uint8Array(h).slice(0, 16);
}

type PrfErgebnis = { enabled?: boolean; results?: { first?: ArrayBuffer } };
const prfVon = (c: PublicKeyCredential) => (c.getClientExtensionResults() as { prf?: PrfErgebnis }).prf;

function abgebrochen(e: unknown): never {
  const name = (e as { name?: string })?.name;
  if (name === "NotAllowedError" || name === "AbortError") throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
  if (name === "NotSupportedError" || name === "SecurityError") {
    throw new PasskeyFehler("nicht-unterstuetzt", "Dieser Browser kann hier keinen Passkey anlegen.");
  }
  throw e;
}

async function abfragen(liste: { credential_id: string; prf_salt: string }[]): Promise<{ credentialId: string; prf: ArrayBuffer }> {
  const evalByCredential: Record<string, { first: Uint8Array }> = {};
  for (const p of liste) evalByCredential[p.credential_id] = { first: fromB64(p.prf_salt) };
  let cred: PublicKeyCredential | null;
  try {
    cred = await navigator.credentials.get({
      publicKey: {
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        allowCredentials: liste.map((p) => ({ type: "public-key" as const, id: fromB64url(p.credential_id) })),
        userVerification: "required",
        timeout: 120_000,
        extensions: { prf: { evalByCredential } } as AuthenticationExtensionsClientInputs,
      },
    }) as PublicKeyCredential | null;
  } catch (e) {
    abgebrochen(e);
  }
  const prf = cred ? prfVon(cred)?.results?.first : undefined;
  if (!cred || !prf) throw new PasskeyFehler("nicht-unterstuetzt", "Dieser Passkey liefert keinen Schlüssel.");
  return { credentialId: toB64url(new Uint8Array(cred.rawId)), prf };
}

/** Einen neuen Passkey anlegen und den (exportierbaren) Datenschlüssel damit
 *  verpacken. Safari und der iCloud-Schlüsselbund liefern das PRF-Geheimnis
 *  beim Anlegen nicht mit — dann gleich eine zweite Abfrage mit genau
 *  diesem Passkey. */
export async function passkeyAnlegen(dkExtractable: CryptoKey, owner: number, name: string,
  label = geraeteName(typeof navigator === "undefined" ? "" : navigator.userAgent)): Promise<PasskeyVerpackung> {
  const salt = crypto.getRandomValues(new Uint8Array(32));
  let cred: PublicKeyCredential | null;
  try {
    cred = await navigator.credentials.create({
      publicKey: {
        rp: { name: "Ratslotse Notizen" },
        user: { id: await nutzerKennung(owner), name, displayName: `${name} (Notizen)` },
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        pubKeyCredParams: [{ type: "public-key", alg: -7 }, { type: "public-key", alg: -257 }],
        authenticatorSelection: { residentKey: "required", requireResidentKey: true, userVerification: "required" },
        timeout: 120_000,
        extensions: { prf: { eval: { first: salt } } } as AuthenticationExtensionsClientInputs,
      },
    }) as PublicKeyCredential | null;
  } catch (e) {
    abgebrochen(e);
  }
  if (!cred) throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
  const ext = prfVon(cred);
  if (ext && ext.enabled === false) {
    throw new PasskeyFehler("nicht-unterstuetzt", "Dieser Passkey kann keine Notizen verschlüsseln.");
  }
  const credentialId = toB64url(new Uint8Array(cred.rawId));
  const prf = ext?.results?.first ?? (await abfragen([{ credential_id: credentialId, prf_salt: toB64(salt) }])).prf;
  return { credential_id: credentialId, prf_salt: toB64(salt), wrapped_key: await wrap(dkExtractable, await passkeyKek(prf)), label };
}

/** Mit einem der Passkeys des Kontos entsperren. `extractable` nur, wenn
 *  danach neu verpackt wird (weiterer Passkey, Notfall-Code). */
export async function mitPasskeyEntsperren(liste: GespeicherterPasskey[], extractable = false): Promise<CryptoKey> {
  if (liste.length === 0) throw new PasskeyFehler("nicht-unterstuetzt", "Kein Passkey eingerichtet.");
  const { credentialId, prf } = await abfragen(liste);
  const treffer = liste.find((p) => p.credential_id === credentialId);
  const dk = treffer ? await unwrap(treffer.wrapped_key, await passkeyKek(prf), extractable) : null;
  if (!dk) throw new PasskeyFehler("passt-nicht", "Dieser Passkey passt nicht zu deinen Notizen.");
  return dk;
}
