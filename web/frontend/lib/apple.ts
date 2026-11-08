/** Sign in with Apple (RL-1002) im Browser über „Sign in with Apple JS"
 *  (Popup-Flow mit der Services ID de.ratslotse.web). Er liefert ein
 *  Identity-Token, das das Backend gegen Apples JWKS prüft — Schlüssel oder
 *  Secrets braucht es dafür nicht. */

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

/** Hat die Person selbst abgebrochen? Nur dann darf still `null` zurückkommen.
 *
 *  Vorher fing der Code JEDEN Fehler ab und lieferte `null` — Abbruch, nicht
 *  geladenes Skript, Netzproblem sahen identisch aus. Der Knopf wertet `null`
 *  als Abbruch und schweigt, also endete jeder echte Fehler in „es passiert
 *  einfach nichts": keine Meldung, kein Log, kein Request am Server. Genau diese Blindheit machte den Ausfall unauffindbar.
 *
 *  Das Web-SDK meldet Abbruch als `popup_closed_by_user` bzw.
 *  `user_cancelled_authorize`. */
function isUserCancellation(err: unknown): boolean {
  const e = err as { error?: unknown; message?: unknown } | null;
  if (!e || typeof e !== "object") return false;
  const error = String(e.error ?? "");
  const message = String(e.message ?? "");
  return (
    error === "popup_closed_by_user" ||
    error === "user_cancelled_authorize" ||
    /cancell?ed/i.test(message)
  );
}

export async function appleCredential(): Promise<AppleCredential | null> {
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
    if (!token) {
      console.error("[apple] Web-Antwort ohne id_token", result);
      throw new Error("Apple hat kein Anmelde-Token geliefert.");
    }
    return {
      identityToken: token,
      givenName: result.user?.name?.firstName ?? "",
      familyName: result.user?.name?.lastName ?? "",
    };
  } catch (err) {
    if (isUserCancellation(err)) return null;   // Popup geschlossen — kein Fehler
    console.error("[apple] Web-Anmeldung fehlgeschlagen", err);
    throw err;
  }
}

/** Nur das Token — für die Re-Authentifizierung (Konto verknüpfen/löschen),
 *  wo der Name keine Rolle spielt. */
export async function appleIdentityToken(): Promise<string | null> {
  return (await appleCredential())?.identityToken ?? null;
}
