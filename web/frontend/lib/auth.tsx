"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { AppleCredential } from "./apple";
import { api, ApiError, setUnauthorizedHandler } from "./api";
import { loadToken, setToken } from "./token";
import { unregisterPush } from "./push";
import { kontoDatenRaeumen } from "./konto-raeumen";
import { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
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

  const refresh = useCallback(async () => {
    try {
      const u = await api.get<User>("/auth/me");
      // Die App bekommt hier ein frisch datiertes Token — wegschreiben, sonst
      // läuft das gespeicherte irgendwann ab und der Login kommt zurück. Im
      // Web ist das Feld null (die Sitzung steckt im Cookie), also passiert
      // nichts.
      if (u.access_token) await setToken(u.access_token);
      setUser(u);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await loadToken(); // hydrate the stored bearer token (native app) before the first /me
      await refresh();
      setLoading(false);
    })();
  }, [refresh]);

  const queryClient = useQueryClient();

  // Clear state when any API call reports the session expired. Mit dem Konto
  // geht auch, was es zwischengespeichert hat (F8/F17) — nur der gerettete
  // Entwurf bleibt, er soll nach der Anmeldung zurückkommen.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      queryClient.clear();
      kontoDatenRaeumen({ mitEntwurf: false });
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

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
    // Was das Konto im Tab hinterlassen hat, gehört nicht der nächsten
    // Person an diesem Gerät (zweite Sicherheitsprüfung, F8/F17).
    queryClient.clear();
    kontoDatenRaeumen({ mitEntwurf: true });
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginWithApple, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
