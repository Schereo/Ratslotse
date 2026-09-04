"use client";

import { createContext, useContext, useEffect, useRef, useState, ReactNode, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { AppleCredential } from "./apple";
import { api, ApiError, setUnauthorizedHandler } from "./api";
import { loadToken, setToken } from "./token";
import { unregisterPush } from "./push";
import { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  loginWithApple: (cred: AppleCredential) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();
  const clearPrivateQueries = useCallback(() => {
    queryClient.removeQueries({
      predicate: (query) => query.meta?.privateData === true,
    });
  }, [queryClient]);
  const authenticatedUserId = useRef<number | null>(null);
  const acceptAuthenticatedUser = useCallback((nextUser: User) => {
    if (authenticatedUserId.current !== nextUser.id) clearPrivateQueries();
    authenticatedUserId.current = nextUser.id;
    setUser(nextUser);
  }, [clearPrivateQueries]);
  const forgetAuthenticatedUser = useCallback(() => {
    authenticatedUserId.current = null;
    setUser(null);
    clearPrivateQueries();
  }, [clearPrivateQueries]);

  const refresh = useCallback(async () => {
    try {
      const u = await api.get<User>("/auth/me");
      // Die App bekommt hier ein frisch datiertes Token — wegschreiben, sonst
      // läuft das gespeicherte irgendwann ab und der Login kommt zurück. Im
      // Web ist das Feld null (die Sitzung steckt im Cookie), also passiert
      // nichts.
      if (u.access_token) await setToken(u.access_token);
      acceptAuthenticatedUser(u);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) forgetAuthenticatedUser();
    }
  }, [acceptAuthenticatedUser, forgetAuthenticatedUser]);

  useEffect(() => {
    (async () => {
      await loadToken(); // hydrate the stored bearer token (native app) before the first /me
      await refresh();
      setLoading(false);
    })();
  }, [refresh]);

  // Clear state when any API call reports the session expired.
  useEffect(() => {
    setUnauthorizedHandler(forgetAuthenticatedUser);
    return () => setUnauthorizedHandler(null);
  }, [forgetAuthenticatedUser]);

  const login = async (email: string, password: string) => {
    const u = await api.post<User>("/auth/login", { email, password });
    await setToken(u.access_token ?? null); // persist bearer token (native app only)
    acceptAuthenticatedUser(u);
  };

  const register = async (email: string, password: string, displayName?: string) => {
    const u = await api.post<User>("/auth/register", { email, password, display_name: displayName || null });
    await setToken(u.access_token ?? null);
    acceptAuthenticatedUser(u);
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
    acceptAuthenticatedUser(u);
  };

  const logout = async () => {
    await unregisterPush(); // while still authenticated — stops pushes for this account
    await api.post("/auth/logout");
    await setToken(null);
    forgetAuthenticatedUser();
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
