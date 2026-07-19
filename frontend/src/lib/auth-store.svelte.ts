// Reactive authentication session, persisted to localStorage.
//
// The store owns the single source of truth for "who is signed in" and the
// bearer token. http.ts reads the token through getToken() so every API
// request carries the Authorization header once a session exists.
//
// ARCHITECTURAL NOTE: the token in localStorage is trusted only as an opaque
// credential to replay to the server. Its claims are never read client-side to
// make authorization decisions — the server verifies the signature on every
// request (see master_plan.api.security.decode_token).

import type { AuthResponse, User } from "./auth-types";

const STORAGE_KEY = "master-plan.session";

interface StoredSession {
  token: string;
  user: User;
}

// Non-reactive mirror of the token for http.ts (avoids importing $state into a
// plain .ts module and any load-order coupling).
let currentToken: string | null = null;

function read(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    if (typeof parsed?.token === "string" && parsed.user) {
      return { token: parsed.token, user: parsed.user as User };
    }
  } catch {
    // Corrupt/unavailable storage: treat as signed out.
  }
  return null;
}

// Reactive session state. Components read `session.user` to render identity.
const initial = read();
currentToken = initial?.token ?? null;

export const session = $state<{ user: User | null }>({
  user: initial?.user ?? null,
});

/** The current bearer token, or null when signed out. Used by http.ts. */
export function getToken(): string | null {
  return currentToken;
}

/** Persist a successful register/login response as the active session. */
export function setSession(auth: AuthResponse): void {
  currentToken = auth.token.access_token;
  session.user = auth.user;
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ token: auth.token.access_token, user: auth.user }),
    );
  } catch {
    // Storage may be unavailable (private mode); the in-memory session still
    // works for the current page load.
  }
}

/** Clear the session (sign out). */
export function clearSession(): void {
  currentToken = null;
  session.user = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures on clear.
  }
}
