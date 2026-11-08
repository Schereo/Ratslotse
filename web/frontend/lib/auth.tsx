"use client";

import { createContext, useContext, useEffect, useRef, useState, ReactNode, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { AppleCredential } from "./apple";
import { api, ApiError, setUnauthorizedHandler } from "./api";
import { kontoDatenRaeumen } from "./konto-raeumen";
import { User } from "./types";

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
      setUser(u);
      setAuthFehler(false);
    } catch (e) {
      // Nur ein 401 heißt „nicht angemeldet". Bis 10/2026 landete auch jeder
      // 5xx und jedes Funkloch beim ersten Laden auf der Anmeldung — bei
      // jedem Deploy also alle, die gerade eine Seite öffneten.
      if (e instanceof ApiError && e.status === 401) {
        setUser(null); setAuthFehler(false);
      } else {
        // Ein schon geladenes Konto bleibt stehen.
        setAuthFehler(true);
      }
    }
  }, []);

  // Einmal je Seitenaufruf, auch wenn der Effekt doppelt läuft (StrictMode in
  // der Entwicklung): Der erste Abruf nimmt die Antwort, die schon seit dem
  // <head> unterwegs ist (lib/early-auth.ts) — ein zweiter ginge neu ans Netz.
  const ersterAbruf = useRef<Promise<void> | null>(null);
  useEffect(() => {
    ersterAbruf.current ??= refresh();
    void ersterAbruf.current.then(() => setLoading(false));
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
    setUser(u);
  };

  const register = async (email: string, password: string, displayName: string) => {
    // Der Name ist Pflicht (Backend weist einen leeren ab) — deshalb kein
    // `|| null` mehr, das die Prüfung nur zum Server verschöbe.
    const u = await api.post<User>("/auth/register", { email, password, display_name: displayName.trim() });
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
    setUser(u);
    // Zurückgegeben, damit der Knopf sofort sehen kann, ob Apple einen Namen
    // mitgeliefert hat — `user` aus dem Context steht erst im nächsten Rendern.
    return u;
  };

  const logout = async () => {
    await api.post("/auth/logout");
    setUser(null);
    // Was das Konto im Tab hinterlassen hat, gehört nicht der nächsten
    // Person an diesem Gerät (zweite Sicherheitsprüfung, F8/F17).
    queryClient.clear();
    kontoDatenRaeumen({ mitEntwurf: true });
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
