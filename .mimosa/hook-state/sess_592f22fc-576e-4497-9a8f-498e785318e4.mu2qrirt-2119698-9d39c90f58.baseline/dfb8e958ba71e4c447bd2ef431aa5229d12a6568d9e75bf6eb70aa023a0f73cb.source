"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  clearSession,
  getStoredToken,
  getStoredUser,
  storeSession,
} from "@/lib/auth-storage";

interface User {
  id: string;
  email: string;
  name: string;
  tenant_id: string;
  roles: string[];
  /** Platform superuser (Phase 21/22): gates the /admin portal UI. */
  platform_admin?: boolean;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isAuthenticated: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const savedToken = getStoredToken();
    const savedUser = getStoredUser<User>();

    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(savedUser);
    } else if (savedToken || savedUser) {
      // Half-written session — drop it rather than half-authenticating.
      clearSession();
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/auth/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        },
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message ?? "Login failed");
      }

      const data = await res.json();
      const { access_token, user: userData } = data;

      setToken(access_token);
      setUser(userData);
      storeSession(access_token, userData);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    clearSession();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        isAuthenticated: !!token && !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

/** HOC/guard: redirects to /login if unauthenticated */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex space-x-2">
          <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
          <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce delay-75" />
          <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce delay-150" />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // redirect in flight
  }

  return <>{children}</>;
}

/**
 * Platform-superuser guard (Phase 22, ADR 009): wraps the /admin routes.
 * The user object carries the platform_admin flag minted at login; the
 * backend re-verifies the grant on every /admin call (≤60s revocation),
 * so this gate is UX, not security.
 */
export function PlatformAdminGuard({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
      </div>
    );
  }

  if (!isAuthenticated || !user?.platform_admin) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center space-y-2">
          <p className="text-lg font-medium text-gray-700">
            Platform administrator privileges required
          </p>
          <p className="text-sm text-gray-400">
            Your account does not have access to the admin portal.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
