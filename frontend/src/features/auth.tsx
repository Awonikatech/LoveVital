import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { onSessionChange, refreshSession, setAccessToken, setCartToken } from "@/services/api";
import { storeApi } from "@/services/store";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: { full_name: string; email: string; password: string; phone?: string }) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
  isStaff: boolean;
  can: (perm: string) => boolean;
}

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  useEffect(() => {
    const off = onSessionChange((t) => setUser(t ? t.user : null));
    refreshSession().finally(() => setReady(true));
    return () => {
      off();
    };
  }, []);

  const afterAuth = useCallback(
    (u: User, token: string) => {
      setAccessToken(token);
      setUser(u);
      qc.invalidateQueries({ queryKey: ["cart"] });
      qc.invalidateQueries({ queryKey: ["wishlist"] });
      return u;
    },
    [qc],
  );

  const login = useCallback(async (email: string, password: string) => {
    const r = await storeApi.login(email, password);
    return afterAuth(r.user, r.access_token);
  }, [afterAuth]);

  const register = useCallback(async (data: { full_name: string; email: string; password: string; phone?: string }) => {
    const r = await storeApi.register(data);
    return afterAuth(r.user, r.access_token);
  }, [afterAuth]);

  const logout = useCallback(async () => {
    try {
      await storeApi.logout();
    } finally {
      setAccessToken(null);
      setUser(null);
      setCartToken(null);
      qc.clear();
    }
  }, [qc]);

  const value = useMemo<AuthState>(() => {
    const perms = new Set(user?.permissions ?? []);
    return {
      user, ready, login, register, logout, setUser,
      isStaff: !!user?.roles.some((r) => r === "admin" || r === "staff"),
      can: (p: string) => perms.has("*") || perms.has(p) || perms.has(p.split(":")[0] + ":*"),
    };
  }, [user, ready, login, register, logout]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
