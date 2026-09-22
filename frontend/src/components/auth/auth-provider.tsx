"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  clearSession,
  getStoredToken,
  getStoredUser,
  storeSession,
} from "@/lib/auth-storage";
import { login as apiLogin } from "@/lib/api-client";
import { Loader } from "@/components/ui/loader";

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
      const data = await apiLogin(email, password);
      setToken(data.access_token);
      setUser(data.user);
      storeSession(data.access_token, data.user);
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
    return <Loader fullScreen />;
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
    return <Loader fullScreen />;
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
