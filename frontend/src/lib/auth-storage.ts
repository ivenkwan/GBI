/** Centralized auth storage — single source of truth for session keys.
 *
 * The API client and the auth provider must agree on where the JWT lives;
 * they historically didn't ("token" vs "genbi_token"), which silently broke
 * authenticated API calls after login.
 */

const TOKEN_KEY = "genbi_token";
const USER_KEY = "genbi_user";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser<T>(): T | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function storeSession(token: string, user: unknown): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
