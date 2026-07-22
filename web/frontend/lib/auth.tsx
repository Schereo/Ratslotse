"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { api, ApiError, setUnauthorizedHandler } from "./api";
import { loadToken, setToken } from "./token";
import { unregisterPush } from "./push";
import { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  loginWithApple: (identityToken: string) => Promise<void>;
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

  // Clear state when any API call reports the session expired.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = async (email: string, password: string) => {
    const u = await api.post<User>("/auth/login", { email, password });
    await setToken(u.access_token ?? null); // persist bearer token (native app only)
    setUser(u);
  };

  const register = async (email: string, password: string, displayName?: string) => {
    const u = await api.post<User>("/auth/register", { email, password, display_name: displayName || null });
    await setToken(u.access_token ?? null);
    setUser(u);
  };

  const loginWithApple = async (identityToken: string) => {
    // RL-1002: Backend verifiziert das Token gegen Apples JWKS und meldet an
    // (bzw. verknüpft/erstellt das Konto).
    const u = await api.post<User>("/auth/apple", { identity_token: identityToken });
    await setToken(u.access_token ?? null);
    setUser(u);
  };

  const logout = async () => {
    await unregisterPush(); // while still authenticated — stops pushes for this account
    await api.post("/auth/logout");
    await setToken(null);
    setUser(null);
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
