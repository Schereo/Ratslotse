import { isNativeApp } from "./platform";

/** Sign in with Apple (RL-1002), nur in der nativen App: holt über das
 *  Apple-SDK ein Identity-Token, das das Backend gegen Apples JWKS prüft.
 *  Web-Browser sehen den Button gar nicht erst (kein Service-ID-Flow). */
export function appleSignInAvailable(): boolean {
  return isNativeApp();
}

export async function appleIdentityToken(): Promise<string | null> {
  if (!isNativeApp()) return null;
  try {
    const { SignInWithApple } = await import("@capacitor-community/apple-sign-in");
    const result = await SignInWithApple.authorize({
      // Auf iOS läuft die native ASAuthorization; clientId/redirectURI sind
      // dort ohne Bedeutung, das Plugin verlangt sie aber im Options-Typ.
      clientId: "de.ratslotse.app",
      redirectURI: "https://ratslotse.de",
      scopes: "email",
    });
    return result.response?.identityToken ?? null;
  } catch {
    // Abbruch durch die Nutzer:in oder fehlende Capability — kein Fehlerfall.
    return null;
  }
}
