/* Passkeys zum Anmelden (seit 11/2026) — und mit derselben Abfrage der
   Schlüssel zu den Notizen.

   Der Server prüft die Anmeldung gegen den öffentlichen Schlüssel
   (`web/backend/app/passkeys.py`). Zugleich fragt der Browser die
   Erweiterung PRF an: Zu einem festen Salz liefert nur dieser Passkey ein
   festes Geheimnis. Daraus entsteht hier, auf dem Gerät, der Schlüssel, der
   den Notiz-Datenschlüssel verpackt (`lib/notiz-passkey.ts`, `passkeyKek`).
   Das Geheimnis geht nie an den Server — `alsJson` lässt
   `clientExtensionResults` weg, und das Backend verwirft sie ohnehin.

   Bei der Anmeldung weiß noch niemand, welcher Passkey kommt; `evalByCredential`
   geht ohne `allowCredentials` nicht. Deshalb ein festes Salz für alle
   Anmelde-Passkeys (`ANMELDE_SALZ`). Das ist kein Geheimnis und muss keins
   sein: Das Geheimnis steckt im Passkey, das Salz trennt nur den Zweck. */

import { api, ApiError } from "@/lib/api";
import * as krypto from "@/lib/notiz-krypto";
import { meldeFehler } from "@/lib/fehler-melden";
import { browserFehler, fromB64url, geraeteName, imSchritt, keinPrf, passkeyKek, PasskeyFehler, prfBytes, TECHNISCH, toB64url } from "@/lib/notiz-passkey";
import type { User } from "@/lib/types";
import type { ApiAntwort } from "@/lib/vertrag";

/** SHA-256 von „ratslotse-passkey-notizen-v1“ — steht so in `note_passkeys.prf_salt`. */
export const ANMELDE_SALZ_B64 = "5MnwhF9xlXWJRKjXOzZmPPe88kNNx+zhKCJHRsu15G4=";
const salz = () => krypto.fromB64(ANMELDE_SALZ_B64);

export type KontoPasskeys = ApiAntwort<"/account/passkeys">;
export type KontoPasskey = KontoPasskeys["passkeys"][number];
type Json = Record<string, unknown>;

/** Was nach einer Abfrage übrig bleibt: welcher Passkey, und sein PRF-Geheimnis
 *  (falls der Browser es geliefert hat — Safari tut das beim Anlegen nicht). */
export interface PrfTreffer { credentialId: string; prf: Uint8Array | null }

export function passkeyAnmeldungMoeglich(): boolean {
  return typeof window !== "undefined" && !!window.PublicKeyCredential && !!navigator.credentials;
}

// ---- Optionen vom Server → Browser ---------------------------------------------

function erstellOptionen(o: Json): PublicKeyCredentialCreationOptions {
  const user = o.user as { id: string; name: string; displayName: string };
  return {
    ...(o as unknown as PublicKeyCredentialCreationOptions),
    challenge: fromB64url(o.challenge as string),
    user: { ...user, id: fromB64url(user.id) },
    excludeCredentials: ((o.excludeCredentials as { id: string; type: "public-key" }[] | undefined) ?? [])
      .map((c) => ({ type: "public-key" as const, id: fromB64url(c.id) })),
    extensions: { prf: { eval: { first: salz() } } } as AuthenticationExtensionsClientInputs,
  };
}

function abfrageOptionen(o: Json, mitPrf: boolean): PublicKeyCredentialRequestOptions {
  return {
    ...(o as unknown as PublicKeyCredentialRequestOptions),
    challenge: fromB64url(o.challenge as string),
    allowCredentials: ((o.allowCredentials as { id: string }[] | undefined) ?? [])
      .map((c) => ({ type: "public-key" as const, id: fromB64url(c.id) })),
    ...(mitPrf ? { extensions: { prf: { eval: { first: salz() } } } as AuthenticationExtensionsClientInputs } : {}),
  };
}

// ---- Browser → Server (ohne das PRF-Geheimnis) ----------------------------------

const b64 = (b: ArrayBuffer) => toB64url(new Uint8Array(b));

export function registrierungAlsJson(c: PublicKeyCredential): Json {
  const r = c.response as AuthenticatorAttestationResponse;
  return {
    id: c.id, rawId: b64(c.rawId), type: "public-key",
    response: { clientDataJSON: b64(r.clientDataJSON), attestationObject: b64(r.attestationObject),
      transports: typeof r.getTransports === "function" ? r.getTransports() : [] },
  };
}

export function bestaetigungAlsJson(c: PublicKeyCredential): Json {
  const r = c.response as AuthenticatorAssertionResponse;
  return {
    id: c.id, rawId: b64(c.rawId), type: "public-key",
    response: { clientDataJSON: b64(r.clientDataJSON), authenticatorData: b64(r.authenticatorData),
      signature: b64(r.signature), userHandle: r.userHandle ? b64(r.userHandle) : null },
  };
}

function prfRoh(c: PublicKeyCredential): unknown {
  const ext = c.getClientExtensionResults() as { prf?: { results?: { first?: unknown } } };
  return ext.prf?.results?.first;
}

/** Das PRF-Ergebnis als frische Bytes, `null` wenn es fehlt oder nichts taugt
 *  (`prfBytes` in `lib/notiz-passkey.ts`). */
function prfVon(c: PublicKeyCredential): Uint8Array | null {
  return prfBytes(prfRoh(c));
}

function fehlerUebersetzen(e: unknown, schritt: string): never {
  const name = (e as { name?: string })?.name;
  if (name === "NotAllowedError" || name === "AbortError") throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
  if (name === "InvalidStateError") throw new PasskeyFehler("schon-da", "Auf diesem Gerät gibt es schon einen Passkey für dein Konto.");
  if (name === "NotSupportedError" || name === "SecurityError") {
    throw new PasskeyFehler("nicht-unterstuetzt", "Dieser Browser kann hier keinen Passkey benutzen.");
  }
  throw browserFehler(e, schritt);
}

/** Der Satz für die Oberfläche — nie die rohe Ausnahme des Browsers.
 *  `null` heißt: nichts zeigen (abgebrochen ist kein Fehler). */
export function passkeyFehlerText(err: unknown): string | null {
  if (err instanceof PasskeyFehler) return err.art === "abgebrochen" ? null : err.message;
  if (err instanceof ApiError) return err.message;
  const x = browserFehler(err, "");
  if (x instanceof PasskeyFehler) return x.message;
  // Eigene Fehler dieses Codes tragen schon einen deutschen Satz.
  return err instanceof Error && err.message ? err.message : TECHNISCH;
}

/** Was der Browser abgelehnt hat, ins Fehlerprotokoll (Admin → Fehler) — mit
 *  dem Schritt, an dem es hakte. Geht nur an den eigenen Server, ohne Konto
 *  und ohne Inhalt (`lib/fehler-melden.ts`); die Meldung des Browsers ist ein
 *  fester Satz aus seinem Inneren. Abbrüche, Serverantworten und die übrigen
 *  PasskeyFehler sind gewollte Ausgänge und bleiben draußen. */
export function passkeyFehlerMelden(err: unknown, schritt = "ohne Angabe"): void {
  const x = err instanceof PasskeyFehler ? err : browserFehler(err, schritt);
  // Ein unbrauchbares PRF-Ergebnis ist für die Oberfläche „kann der Browser
  // nicht“, fürs Protokoll aber ein Befund (es trägt dann eine Ursache).
  if (!(x instanceof PasskeyFehler) || !(x.art === "technisch" || (x.art === "nicht-unterstuetzt" && x.ursache))) return;
  meldeFehler(Object.assign(new Error(`Passkey/Notizen, ${x.schritt ?? schritt}: ${x.ursache ?? ""}`), { name: "PasskeyFehler" }));
}

async function anlegen(optionen: Json): Promise<PublicKeyCredential> {
  try {
    const c = await navigator.credentials.create({ publicKey: erstellOptionen(optionen) }) as PublicKeyCredential | null;
    if (!c) throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
    return c;
  } catch (e) {
    if (e instanceof PasskeyFehler) throw e;
    fehlerUebersetzen(e, "Passkey anlegen");
  }
}

async function abfragen(optionen: Json, mitPrf: boolean, signal?: AbortSignal,
  mediation?: CredentialMediationRequirement): Promise<PublicKeyCredential> {
  try {
    const c = await navigator.credentials.get({ publicKey: abfrageOptionen(optionen, mitPrf), signal, mediation }) as PublicKeyCredential | null;
    if (!c) throw new PasskeyFehler("abgebrochen", "Abgebrochen.");
    return c;
  } catch (e) {
    if (e instanceof PasskeyFehler) throw e;
    fehlerUebersetzen(e, "Passkey abfragen");
  }
}

const geraet = () => geraeteName(typeof navigator === "undefined" ? "" : navigator.userAgent);

// ---- Die vier Wege ------------------------------------------------------------

/** Registrieren: Adresse und Name prüft der Server VOR der Abfrage am Gerät. */
export async function mitPasskeyRegistrieren(email: string, name: string): Promise<{ user: User; treffer: PrfTreffer }> {
  const { public_key } = await api.post<ApiAntwort<"/auth/passkey/signup/options", "post">>(
    "/auth/passkey/signup/options", { email, display_name: name });
  const c = await anlegen(public_key);
  const user = await api.post<User>("/auth/passkey/signup", { credential: registrierungAlsJson(c), label: geraet() });
  return { user, treffer: { credentialId: b64(c.rawId), prf: prfVon(c) } };
}

/** Anmelden. `mediation: "conditional"` für das Ausfüllen im Adressfeld. */
export async function mitPasskeyAnmelden(opts: { signal?: AbortSignal; mediation?: CredentialMediationRequirement } = {}):
  Promise<{ user: User; treffer: PrfTreffer }> {
  const { public_key } = await api.post<ApiAntwort<"/auth/passkey/login/options", "post">>("/auth/passkey/login/options");
  const c = await abfragen(public_key, true, opts.signal, opts.mediation);
  const user = await api.post<User>("/auth/passkey/login", { credential: bestaetigungAlsJson(c) });
  return { user, treffer: { credentialId: b64(c.rawId), prf: prfVon(c) } };
}

/** Im Konto einen weiteren Passkey anlegen. */
export async function kontoPasskeyHinzufuegen(): Promise<{ liste: KontoPasskeys; treffer: PrfTreffer }> {
  const { public_key } = await api.post<ApiAntwort<"/account/passkeys/options", "post">>("/account/passkeys/options");
  const c = await anlegen(public_key);
  const liste = await api.post<KontoPasskeys>("/account/passkeys", { credential: registrierungAlsJson(c), label: geraet() });
  return { liste, treffer: { credentialId: b64(c.rawId), prf: prfVon(c) } };
}

/** Bestätigen beim Löschen oder Adresswechsel — ohne PRF, es geht nur um „bist du es". */
export async function passkeyBestaetigung(): Promise<Json> {
  const { public_key } = await api.post<ApiAntwort<"/auth/passkey/login/options", "post">>("/auth/passkey/login/options");
  return bestaetigungAlsJson(await abfragen(public_key, false));
}

export const kontoPasskeysLaden = () => api.get<KontoPasskeys>("/account/passkeys");
export const kontoPasskeyEntfernen = (id: number) => api.del<KontoPasskeys>(`/account/passkeys/${id}`);

// ---- Notizen mit derselben Abfrage ------------------------------------------------

/** Das PRF-Geheimnis eines Anmelde-Passkeys für die Notizen nutzen. Offen
 *  bleiben sie dann auf diesem Gerät bis zum Abmelden — wie beim Einrichten
 *  mit Passkey vorgewählt („Auf diesem Gerät offen lassen“):
 *  - Notizen mit diesem Passkey eingerichtet → gleich entsperren.
 *  - Noch gar nicht eingerichtet → still einrichten (neuer Datenschlüssel,
 *    mit diesem Passkey verpackt).
 *  - Eingerichtet, aber mit anderem Schlüssel → für diese Sitzung merken;
 *    beim nächsten Entsperren kommt der Passkey dazu (`lib/notizen.ts`).
 *  Fehlt das Geheimnis (Safari beim Anlegen), passiert nichts: Dann fragt das
 *  Schloss beim ersten Notieren einmal nach. Scheitert hier etwas, ist die
 *  Anmeldung trotzdem gelungen — deshalb schluckt der Aufrufer Fehler. */
export async function notizenMitPasskey(owner: number, treffer: PrfTreffer): Promise<"offen" | "eingerichtet" | "gemerkt" | "nichts"> {
  if (!treffer.prf) return "nichts";
  const notizen = await import("@/lib/notizen");
  const prf = treffer.prf;
  const kek = await imSchritt("Schlüssel ableiten", () => passkeyKek(prf));
  let keys;
  try {
    keys = await notizen.fetchKeys();
  } catch (e) {
    // 403: Adresse noch unbestätigt — merken, nach der Bestätigung geht es
    // in diesem Tab ohne neue Abfrage weiter. 404: Notizen sind aus.
    if (e instanceof ApiError && e.status === 403) {
      notizen.merkeAnmeldePasskey(owner, treffer.credentialId, kek);
      return "gemerkt";
    }
    return "nichts";
  }
  if (keys.configured && keys.keys) {
    const zeile = keys.passkeys.find((p) => p.credential_id === treffer.credentialId && p.prf_salt === ANMELDE_SALZ_B64);
    const dk = zeile ? await krypto.unwrap(zeile.wrapped_key, kek) : null;
    if (dk) {
      await notizen.setSessionKey(owner, dk, true);
      return "offen";
    }
    notizen.merkeAnmeldePasskey(owner, treffer.credentialId, kek);
    return "gemerkt";
  }
  await notizenEinrichtenMitKek(owner, treffer.credentialId, kek);
  return "eingerichtet";
}

/** Neue Notiz-Schlüssel, verpackt mit dem Schlüssel aus einem Anmelde-Passkey. */
export async function notizenEinrichtenMitKek(owner: number, credentialId: string, kek: CryptoKey) {
  const notizen = await import("@/lib/notizen");
  const { dk, basis } = await imSchritt("neuer Schlüssel", () => krypto.neuerSchluessel());
  const wrapped_key = await imSchritt("verpacken", () => krypto.wrap(dk, kek));
  const k = await notizen.createKeysMitPasskey(basis, { credential_id: credentialId, prf_salt: ANMELDE_SALZ_B64, wrapped_key, label: geraet() });
  const sitzung = await imSchritt("Sitzungsschlüssel", () => krypto.nurBenutzbar(dk));
  await notizen.setSessionKey(owner, sitzung, true);
  notizen.vergissAnmeldePasskey();
  return { keys: k, dk: sitzung };
}

/** Für die Notizen einen Passkey besorgen, der zugleich anmeldet — wenn die
 *  Passkey-Anmeldung an ist. Erst der aus dieser Sitzung (keine Abfrage),
 *  dann einer der vorhandenen Anmelde-Passkeys, sonst ein neuer. */
export async function notizPasskeyBesorgen(owner: number): Promise<{ credentialId: string; kek: CryptoKey }> {
  const notizen = await import("@/lib/notizen");
  const gemerkt = notizen.anmeldePasskey(owner);
  if (gemerkt) return gemerkt;
  const { passkeys } = await kontoPasskeysLaden();
  if (passkeys.length > 0) {
    const evalByCredential: Record<string, { first: Uint8Array }> = {};
    for (const p of passkeys) evalByCredential[p.credential_id] = { first: salz() };
    let c: PublicKeyCredential | null;
    try {
      c = await navigator.credentials.get({
        publicKey: {
          challenge: crypto.getRandomValues(new Uint8Array(32)),
          allowCredentials: passkeys.map((p) => ({ type: "public-key" as const, id: fromB64url(p.credential_id) })),
          userVerification: "required", timeout: 120_000,
          extensions: { prf: { evalByCredential } } as AuthenticationExtensionsClientInputs,
        },
      }) as PublicKeyCredential | null;
    } catch (e) {
      fehlerUebersetzen(e, "Passkey abfragen");
    }
    const prf = c ? prfVon(c) : null;
    if (!c || !prf) throw keinPrf(c ? prfRoh(c) : undefined, "Passkey abfragen");
    return { credentialId: b64(c.rawId), kek: await imSchritt("Schlüssel ableiten", () => passkeyKek(prf)) };
  }
  const { treffer } = await kontoPasskeyHinzufuegen();
  let prf = treffer.prf;
  if (!prf) {
    // Safari liefert PRF beim Anlegen nicht (oder leer) — einmal nachfragen.
    const c = await abfragen({ challenge: toB64url(crypto.getRandomValues(new Uint8Array(32))),
      allowCredentials: [{ id: treffer.credentialId, type: "public-key" }], userVerification: "required", timeout: 120_000 }, true);
    prf = prfVon(c);
    if (!prf) throw keinPrf(prfRoh(c), "Passkey abfragen");
  }
  const geheimnis = prf;
  return { credentialId: treffer.credentialId, kek: await imSchritt("Schlüssel ableiten", () => passkeyKek(geheimnis)) };
}

/** Nach einer Anmeldung per Passkey: Ist er noch keiner für die Notizen, kommt
 *  er dazu, sobald der Datenschlüssel (exportierbar) offen ist. */
export async function anmeldePasskeyNachtragen(owner: number, keyVersion: number, dkExportierbar: CryptoKey) {
  const notizen = await import("@/lib/notizen");
  const gemerkt = notizen.anmeldePasskey(owner);
  if (!gemerkt) return null;
  const k = await notizen.addPasskey(keyVersion, {
    credential_id: gemerkt.credentialId, prf_salt: ANMELDE_SALZ_B64,
    wrapped_key: await imSchritt("verpacken", () => krypto.wrap(dkExportierbar, gemerkt.kek)), label: geraet(),
  });
  notizen.vergissAnmeldePasskey();
  return k;
}

/** Für Einrichten und „Passkey hinzufügen“ bei den Notizen: einen
 *  Anmelde-Passkey besorgen (`notizPasskeyBesorgen`) und den exportierbaren
 *  Datenschlüssel damit verpacken. */
export async function notizVerpackungMitKontoPasskey(owner: number, dkExportierbar: CryptoKey) {
  const { credentialId, kek } = await notizPasskeyBesorgen(owner);
  (await import("@/lib/notizen")).vergissAnmeldePasskey();
  const wrapped_key = await imSchritt("verpacken", () => krypto.wrap(dkExportierbar, kek));
  return { credential_id: credentialId, prf_salt: ANMELDE_SALZ_B64, wrapped_key, label: geraet() };
}
