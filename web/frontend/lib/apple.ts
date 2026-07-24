import { isNativeApp } from "./platform";

/** Sign in with Apple (RL-1002): in der nativen App über das Apple-SDK,
 *  im Browser über „Sign in with Apple JS" (Popup-Flow mit der Services ID
 *  de.ratslotse.web). Beide Wege liefern ein Identity-Token, das das Backend
 *  gegen Apples JWKS prüft — Schlüssel oder Secrets braucht keiner davon. */

const APPLE_WEB_CLIENT_ID = "de.ratslotse.web";
// Der Web-Flow funktioniert nur auf Domains, die an der Services ID
// registriert sind — sonst bliebe der Button eine Sackgasse (z. B. localhost).
const REGISTERED_WEB_HOSTS = /(^|\.)ratslotse\.de$/;

type AppleIdSdk = {
  auth: {
    init: (config: {
      clientId: string;
      scope: string;
      redirectURI: string;
      usePopup: boolean;
    }) => void;
    signIn: () => Promise<{
      authorization?: { id_token?: string };
      // Apple liefert den Namen NUR bei der allerersten Autorisierung und
      // NICHT im Identity-Token — er kommt hier separat und ist danach für
      // immer weg (bis man Ratslotse in den Apple-ID-Einstellungen löst).
      user?: { name?: { firstName?: string; lastName?: string } };
    }>;
  };
};

/** Was eine Apple-Anmeldung liefert: das signierte Token — und beim ersten
 *  Mal den Namen. Das Backend übernimmt ihn nur für frische Konten. */
export type AppleCredential = {
  identityToken: string;
  givenName: string;
  familyName: string;
};

export function appleSignInAvailable(): boolean {
  if (isNativeApp()) return true;
  return typeof window !== "undefined" && REGISTERED_WEB_HOSTS.test(window.location.hostname);
}

async function loadAppleJs(): Promise<AppleIdSdk | null> {
  const w = window as unknown as { AppleID?: AppleIdSdk };
  if (w.AppleID) return w.AppleID;
  await new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    // Achtung: Apples SDK-Pfad ist versioniert + lokalisiert — der ältere
    // „…/static/jwt/…"-Pfad liefert inzwischen 403.
    s.src = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/de_DE/appleid.auth.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Apple-Script nicht ladbar"));
    document.head.appendChild(s);
  });
  return w.AppleID ?? null;
}

export async function appleCredential(): Promise<AppleCredential | null> {
  if (isNativeApp()) {
    try {
      const { SignInWithApple } = await import("@capacitor-community/apple-sign-in");
      const result = await SignInWithApple.authorize({
        // Auf iOS läuft die native ASAuthorization; clientId/redirectURI sind
        // dort ohne Bedeutung, das Plugin verlangt sie aber im Options-Typ.
        clientId: "de.ratslotse.app",
        redirectURI: "https://ratslotse.de",
        scopes: "email name",
      });
      const token = result.response?.identityToken;
      if (!token) return null;
      return {
        identityToken: token,
        givenName: result.response?.givenName ?? "",
        familyName: result.response?.familyName ?? "",
      };
    } catch {
      // Abbruch durch die Nutzer:in oder fehlende Capability — kein Fehlerfall.
      return null;
    }
  }

  try {
    const AppleID = await loadAppleJs();
    if (!AppleID) return null;
    AppleID.auth.init({
      clientId: APPLE_WEB_CLIENT_ID,
      scope: "email name",
      // Muss exakt einer bei Apple registrierten Return-URL entsprechen.
      redirectURI: `${window.location.origin}/login`,
      usePopup: true,
    });
    const result = await AppleID.auth.signIn();
    const token = result?.authorization?.id_token;
    if (!token) return null;
    return {
      identityToken: token,
      givenName: result.user?.name?.firstName ?? "",
      familyName: result.user?.name?.lastName ?? "",
    };
  } catch {
    // Popup geschlossen/abgebrochen — kein Fehlerfall.
    return null;
  }
}

/** Nur das Token — für die Re-Authentifizierung (Konto verknüpfen/löschen),
 *  wo der Name keine Rolle spielt. */
export async function appleIdentityToken(): Promise<string | null> {
  return (await appleCredential())?.identityToken ?? null;
}
