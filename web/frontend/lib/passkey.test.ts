import { describe, expect, it } from "vitest";
import { fromB64, toB64 } from "./notiz-krypto";
import { ApiError } from "./api";
import { PasskeyFehler, TECHNISCH } from "./notiz-passkey";
import { ANMELDE_SALZ_B64, bestaetigungAlsJson, passkeyFehlerText, registrierungAlsJson } from "./passkey";

describe("Anmelde-Salz", () => {
  it("ist SHA-256 von „ratslotse-passkey-notizen-v1“ — steht so in note_passkeys", async () => {
    const roh = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("ratslotse-passkey-notizen-v1"));
    expect(toB64(new Uint8Array(roh))).toBe(ANMELDE_SALZ_B64);
    expect(fromB64(ANMELDE_SALZ_B64)).toHaveLength(32);
  });
});

/** Ein Ergebnis von `navigator.credentials`, wie der Browser es liefert —
 *  samt PRF-Geheimnis in den Erweiterungen. */
function schein(response: object): PublicKeyCredential {
  return {
    id: "AQID", rawId: new Uint8Array([1, 2, 3]).buffer, type: "public-key", response,
    getClientExtensionResults: () => ({ prf: { enabled: true, results: { first: new Uint8Array(32).fill(7).buffer } } }),
  } as unknown as PublicKeyCredential;
}

const puffer = (...b: number[]) => new Uint8Array(b).buffer;

describe("Was an den Server geht", () => {
  it("die Registrierung ohne Erweiterungen — das PRF-Geheimnis bleibt auf dem Gerät", () => {
    const json = registrierungAlsJson(schein({
      clientDataJSON: puffer(123, 125), attestationObject: puffer(0xa0), getTransports: () => ["internal"],
    }));
    expect(json).toEqual({
      id: "AQID", rawId: "AQID", type: "public-key",
      response: { clientDataJSON: "e30", attestationObject: "oA", transports: ["internal"] },
    });
    expect(JSON.stringify(json)).not.toContain("prf");
  });

  it("die Anmeldung ohne Erweiterungen, mit Nutzerkennung als Base64url", () => {
    const json = bestaetigungAlsJson(schein({
      clientDataJSON: puffer(123, 125), authenticatorData: puffer(1), signature: puffer(0xfb, 0xff), userHandle: puffer(0xff, 0xfe),
    }));
    expect(json.response).toEqual({ clientDataJSON: "e30", authenticatorData: "AQ", signature: "-_8", userHandle: "__4" });
    expect(JSON.stringify(json)).not.toContain("prf");
  });
});

describe("Was unter dem Knopf steht", () => {
  it("nie die rohe Ausnahme des Browsers", () => {
    const roh = new DOMException("Data provided to an operation does not meet requirements", "DataError");
    expect(passkeyFehlerText(roh)).toBe(TECHNISCH);
  });

  it("abgebrochen ist kein Fehler, Serverantworten und eigene Sätze bleiben", () => {
    expect(passkeyFehlerText(new PasskeyFehler("abgebrochen", "Abgebrochen."))).toBeNull();
    expect(passkeyFehlerText(new ApiError(409, "Diese Adresse ist schon vergeben."))).toBe("Diese Adresse ist schon vergeben.");
    expect(passkeyFehlerText(new PasskeyFehler("schon-da", "Auf diesem Gerät gibt es schon einen Passkey für dein Konto.")))
      .toBe("Auf diesem Gerät gibt es schon einen Passkey für dein Konto.");
    expect(passkeyFehlerText("kaputt")).toBe(TECHNISCH);
  });
});
