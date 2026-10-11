"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import type { AppleCredential } from "./apple";
import { api, ApiError, setUnauthorizedHandler } from "./api";
import { loadToken, setToken } from "./token";
import { unregisterPush } from "./push";
import { User } from "./types";
import { isNativeApp } from "./platform";

/** In der App: das zuletzt bestätigte Konto, für den Start im Funkloch. Der
 *  Abfrage-Zwischenspeicher überlebt dort den Neustart (RL-1103) — ohne Konto
 *  stand davor aber die Anmeldung, und die gespeicherten Daten waren wertlos.
 *  Rechte setzt ohnehin der Server durch; das hier entscheidet nur, ob die
 *  Hülle steht. */
const LETZTES_KONTO = "ratslotse.letztes-konto";
function kontoMerken(u: User | null) {
  if (!isNativeApp()) return;
  try {
    if (u) localStorage.setItem(LETZTES_KONTO, JSON.stringify({ ...u, access_token: null }));
    else localStorage.removeItem(LETZTES_KONTO);
  } catch { /* gesperrter Speicher: dann eben ohne */ }
}
function letztesKonto(): User | null {
  if (!isNativeApp()) return null;
  try {
    const roh = localStorage.getItem(LETZTES_KONTO);
    return roh ? (JSON.parse(roh) as User) : null;
  } catch { return null; }
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  /** `/auth/me` kam nicht an (Netz, 5xx, Deploy) — NICHT „abgemeldet".
   *  Die Hülle zeigt dann „antwortet gerade nicht" statt der Anmeldung. */
  authFehler: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  loginWithApple: (cred: AppleCredential) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authFehler, setAuthFehler] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const u = await api.get<User>("/auth/me");
      // Die App bekommt hier ein frisch datiertes Token — wegschreiben, sonst
      // läuft das gespeicherte irgendwann ab und der Login kommt zurück. Im
      // Web ist das Feld null (die Sitzung steckt im Cookie), also passiert
      // nichts.
      if (u.access_token) await setToken(u.access_token);
      setUser(u);
      kontoMerken(u);
      setAuthFehler(false);
    } catch (e) {
      // Nur ein 401 heißt „nicht angemeldet". Bis 10/2026 landete auch jeder
      // 5xx und jedes Funkloch beim ersten Laden auf der Anmeldung — bei
      // jedem Deploy also alle, die gerade eine Seite öffneten.
      if (e instanceof ApiError && e.status === 401) {
        setUser(null); kontoMerken(null); setAuthFehler(false);
      } else {
        setAuthFehler(true);
        setUser((jetzt) => jetzt ?? letztesKonto());
      }
    }
  }, []);

  useEffect(() => {
    (async () => {
      await loadToken(); // hydrate the stored bearer token (native app) before the first /me
      await refresh();
      setLoading(false);
    })();
  }, [refresh]);

  // Clear state when any API call reports the session expired.
  useEffect(() => {
    setUnauthorizedHandler(() => { setUser(null); kontoMerken(null); });
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = async (email: string, password: string) => {
    const u = await api.post<User>("/auth/login", { email, password });
    await setToken(u.access_token ?? null); // persist bearer token (native app only)
    setUser(u);
  };

  const register = async (email: string, password: string, displayName: string) => {
    // Der Name ist Pflicht (Backend weist einen leeren ab) — deshalb kein
    // `|| null` mehr, das die Prüfung nur zum Server verschöbe.
    const u = await api.post<User>("/auth/register", { email, password, display_name: displayName.trim() });
    await setToken(u.access_token ?? null);
    setUser(u);
  };

  const loginWithApple = async (cred: AppleCredential) => {
    // RL-1002: Backend verifiziert das Token gegen Apples JWKS und meldet an
    // (bzw. verknüpft/erstellt das Konto).
    const u = await api.post<User>("/auth/apple", {
      identity_token: cred.identityToken,
      given_name: cred.givenName,
      family_name: cred.familyName,
    });
    await setToken(u.access_token ?? null);
    setUser(u);
    // Zurückgegeben, damit der Knopf sofort sehen kann, ob Apple einen Namen
    // mitgeliefert hat — `user` aus dem Context steht erst im nächsten Rendern.
    return u;
  };

  const logout = async () => {
    await unregisterPush(); // while still authenticated — stops pushes for this account
    await api.post("/auth/logout");
    await setToken(null);
    setUser(null);
    kontoMerken(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, authFehler, login, register, loginWithApple, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
