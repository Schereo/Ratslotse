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

/** `technisch`: Der Browser selbst hat einen Schritt abgelehnt (WebCrypto,
 *  WebAuthn). `schritt` und `ursache` sind fürs Fehlerprotokoll, nie für die
 *  Oberfläche. */
export class PasskeyFehler extends Error {
  constructor(readonly art: "nicht-unterstuetzt" | "abgebrochen" | "passt-nicht" | "schon-da" | "technisch", msg: string,
    readonly schritt?: string, readonly ursache?: string) {
    super(msg);
    this.name = "PasskeyFehler";
  }
}

export const TECHNISCH = "Das hat in diesem Browser nicht geklappt. Versuch es bitte noch einmal.";

/** Was der Browser selbst wirft, trägt einen englischen Satz aus seinem
 *  Inneren — am 12.11.2026 stand so in Tims Safari nur „Data provided to an
 *  operation does not meet requirements“ unter dem Knopf, ohne Hinweis, was
 *  zu tun ist und an welcher Stelle es hakte. Daraus wird ein PasskeyFehler
 *  mit deutschem Satz; Schritt und Ursache bleiben fürs Fehlerprotokoll.
 *  Fehler mit eigenem deutschen Text (ApiError, PasskeyFehler) bleiben, wie
 *  sie sind. */
export function browserFehler(e: unknown, schritt: string): unknown {
  const vomBrowser = (typeof DOMException !== "undefined" && e instanceof DOMException) || e instanceof TypeError;
  if (!vomBrowser) return e;
  const x = e as Error;
  return new PasskeyFehler("technisch", TECHNISCH, schritt, `${x.name}: ${x.message}`.slice(0, 300));
}

/** Einen Schritt ausführen und rohe Browser-Ausnahmen übersetzen. */
export async function imSchritt<T>(schritt: string, fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e) {
    throw browserFehler(e, schritt);
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

export const KEIN_SCHLUESSEL = "Dieser Passkey liefert keinen Schlüssel.";

/** Das PRF-Ergebnis als eigene, frische Bytes — oder `null`, wenn es nichts
 *  taugt. Am 13.11.2026 scheiterte Tims Einrichten erneut, jetzt mit Schritt:
 *  „Schlüssel ableiten: DataError“ — der Passkey hatte geantwortet, aber
 *  WebCrypto nahm sein Geheimnis nicht an. Ein echtes PRF-Ergebnis sind 32
 *  Byte (HMAC-SHA-256); leer, abgetrennt (detached) oder als Objekt aus einer
 *  anderen Welt (eine Passwort-Erweiterung, die die Abfrage übernimmt) kann es
 *  trotzdem ankommen. Die Kopie löst die letzten beiden, die Länge fängt den
 *  ersten: Dann fragt das Anlegen einmal nach, statt abzubrechen. */
export function prfBytes(x: unknown): Uint8Array | null {
  if (x == null || typeof x !== "object") return null;
  let u8: Uint8Array;
  try {
    if (ArrayBuffer.isView(x)) u8 = new Uint8Array(x.buffer, x.byteOffset, x.byteLength).slice();
    else if (Object.prototype.toString.call(x) === "[object ArrayBuffer]") u8 = new Uint8Array(x as ArrayBuffer).slice();
    else return null;
  } catch {
    return null;
  }
  return u8.byteLength >= 16 ? u8 : null;
}

/** Was statt eines brauchbaren PRF-Ergebnisses kam — nur Art und Länge, nie
 *  die Bytes: fürs Fehlerprotokoll. */
export function prfBeschreibung(x: unknown): string {
  if (x === undefined) return "fehlt";
  if (x === null) return "null";
  const art = typeof x === "object" ? Object.prototype.toString.call(x).slice(8, -1) : typeof x;
  const n = (x as { byteLength?: unknown }).byteLength;
  return typeof n === "number" ? `${art}, ${n} B` : art;
}

/** Kein brauchbares Geheimnis: wie „kann der Browser nicht“ (weiter mit
 *  Passphrase), aber mit Befund fürs Fehlerprotokoll, wenn überhaupt etwas kam. */
export function keinPrf(roh: unknown, schritt: string): PasskeyFehler {
  return new PasskeyFehler("nicht-unterstuetzt", KEIN_SCHLUESSEL, schritt,
    roh === undefined ? undefined : `PRF unbrauchbar: ${prfBeschreibung(roh)}`);
}

/** Aus dem PRF-Geheimnis der Schlüssel, der den Datenschlüssel verpackt. */
export async function passkeyKek(prf: BufferSource): Promise<CryptoKey> {
  const roh = prfBytes(prf);
  if (!roh) throw keinPrf(prf, "Schlüssel ableiten");
  try {
    const basis = await crypto.subtle.importKey("raw", roh, "HKDF", false, ["deriveKey"]);
    return await crypto.subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info: enc.encode(PASSKEY_INFO) },
      basis, { name: "AES-KW", length: 256 }, false, ["wrapKey", "unwrapKey"]);
  } catch (e) {
    const f = browserFehler(e, "Schlüssel ableiten");
    if (f instanceof PasskeyFehler && f.art === "technisch") {
      throw new PasskeyFehler("technisch", TECHNISCH, "Schlüssel ableiten", `${f.ursache} [PRF ${prfBeschreibung(prf)}]`);
    }
    throw f;
  }
}

/** Stabil je Konto: Ein zweites Anlegen auf demselben Gerät ersetzt den alten
 *  Passkey, statt einen zweiten danebenzulegen. */
async function nutzerKennung(owner: number): Promise<Uint8Array> {
  const h = await crypto.subtle.digest("SHA-256", enc.encode(`ratslotse-notizen|${owner}`));
  return new Uint8Array(h).slice(0, 16);
}

type PrfErgebnis = { enabled?: boolean; results?: { first?: unknown } };
const prfVon = (c: PublicKeyCredential) => (c.getClientExtensionResults() as { prf?: PrfErgebnis }).prf;

function abgebrochen(e: unknown, schritt: string): never {
  const name = (e as { name?: string })?.name;
  if (name === "NotAllowedError" || name === "AbortError") throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
  if (name === "NotSupportedError" || name === "SecurityError") {
    throw new PasskeyFehler("nicht-unterstuetzt", "Dieser Browser kann hier keinen Passkey anlegen.");
  }
  throw browserFehler(e, schritt);
}

async function abfragen(liste: { credential_id: string; prf_salt: string }[]): Promise<{ credentialId: string; prf: Uint8Array }> {
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
    abgebrochen(e, "Passkey abfragen");
  }
  if (!cred) throw new PasskeyFehler("nicht-unterstuetzt", KEIN_SCHLUESSEL);
  const roh = prfVon(cred)?.results?.first;
  const prf = prfBytes(roh);
  if (!prf) throw keinPrf(roh, "Passkey abfragen");
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
    abgebrochen(e, "Passkey anlegen");
  }
  if (!cred) throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
  const ext = prfVon(cred);
  if (ext && ext.enabled === false) {
    throw new PasskeyFehler("nicht-unterstuetzt", "Dieser Passkey kann keine Notizen verschlüsseln.");
  }
  const credentialId = toB64url(new Uint8Array(cred.rawId));
  // Leer oder unbrauchbar zählt wie „nicht mitgeliefert“: einmal nachfragen.
  const prf = prfBytes(ext?.results?.first) ?? (await abfragen([{ credential_id: credentialId, prf_salt: toB64(salt) }])).prf;
  const kek = await imSchritt("Schlüssel ableiten", () => passkeyKek(prf));
  return { credential_id: credentialId, prf_salt: toB64(salt), wrapped_key: await imSchritt("verpacken", () => wrap(dkExtractable, kek)), label };
}

/** Mit einem der Passkeys des Kontos entsperren. `extractable` nur, wenn
 *  danach neu verpackt wird (weiterer Passkey, Notfall-Code). */
export async function mitPasskeyEntsperren(liste: GespeicherterPasskey[], extractable = false): Promise<CryptoKey> {
  if (liste.length === 0) throw new PasskeyFehler("nicht-unterstuetzt", "Kein Passkey eingerichtet.");
  const { credentialId, prf } = await abfragen(liste);
  const treffer = liste.find((p) => p.credential_id === credentialId);
  const kek = await imSchritt("Schlüssel ableiten", () => passkeyKek(prf));
  const dk = treffer ? await unwrap(treffer.wrapped_key, kek, extractable) : null;
  if (!dk) throw new PasskeyFehler("passt-nicht", "Dieser Passkey passt nicht zu deinen Notizen.");
  return dk;
}
