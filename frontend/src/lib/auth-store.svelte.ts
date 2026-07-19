// Reactive authentication session, persisted to localStorage.
//
// The store owns the single source of truth for "who is signed in" and the
// bearer token. http.ts reads the token through getToken() so every API
// request carries the Authorization header once a session exists.
//
// SLIDING SESSION: tokens are short-lived (1h). The store proactively calls
// POST /api/auth/refresh a few minutes before expiry to mint a fresh token, so
// an active user is never logged out mid-work. If a refresh genuinely fails
// (401 — the token already expired), the session is cleared and the user must
// sign in again. Transient failures (offline, 5xx) are retried, not logged out.
//
// ARCHITECTURAL NOTE: the token in localStorage is trusted only as an opaque
// credential to replay to the server. Its claims are never read client-side to
// make authorization decisions — the server verifies the signature on every
// request (see master_plan.api.security.decode_token).

import { refresh as refreshToken } from "./auth-api";
import type { AuthResponse, User } from "./auth-types";
import { ApiError } from "./http";

const STORAGE_KEY = "master-plan.session";

// Renew this long before the token's expiry, so a slow request still lands in
// time. Clamped so a near-expired restored token refreshes almost immediately.
const REFRESH_SKEW_MS = 5 * 60 * 1000; // 5 minutes
const MIN_DELAY_MS = 10 * 1000; // never busy-loop
const RETRY_DELAY_MS = 60 * 1000; // transient-failure backoff

interface StoredSession {
  token: string;
  user: User;
  // Absolute expiry (epoch ms) so scheduling survives a page reload.
  expiresAt: number | null;
}

// Non-reactive mirror of the token for http.ts (avoids importing $state into a
// plain .ts module and any load-order coupling).
let currentToken: string | null = null;
let refreshTimer: ReturnType<typeof setTimeout> | undefined;

function read(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    if (typeof parsed?.token === "string" && parsed.user) {
      return {
        token: parsed.token,
        user: parsed.user as User,
        expiresAt: typeof parsed.expiresAt === "number" ? parsed.expiresAt : null,
      };
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

function armTimer(delayMs: number): void {
  if (refreshTimer !== undefined) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => void runRefresh(), Math.max(0, delayMs));
}

/** Schedule the next proactive refresh from an absolute expiry (epoch ms). */
function scheduleRefresh(expiresAt: number | null): void {
  if (refreshTimer !== undefined) {
    clearTimeout(refreshTimer);
    refreshTimer = undefined;
  }
  if (expiresAt === null) return;
  armTimer(Math.max(MIN_DELAY_MS, expiresAt - Date.now() - REFRESH_SKEW_MS));
}

/** Renew the token; log out only on a definitive 401, retry transient errors. */
async function runRefresh(): Promise<void> {
  if (currentToken === null) return;
  try {
    setSession(await refreshToken());
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearSession(); // token is gone — force re-login
    } else {
      armTimer(RETRY_DELAY_MS); // offline / server hiccup — keep the session, retry
    }
  }
}

/** Persist a successful register/login/refresh response as the active session. */
export function setSession(auth: AuthResponse): void {
  currentToken = auth.token.access_token;
  session.user = auth.user;
  const expiresAt =
    typeof auth.token.expires_in === "number" ? Date.now() + auth.token.expires_in * 1000 : null;
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ token: currentToken, user: auth.user, expiresAt }),
    );
  } catch {
    // Storage may be unavailable (private mode); the in-memory session still
    // works for the current page load.
  }
  scheduleRefresh(expiresAt);
}

/** Clear the session (sign out) and cancel any pending refresh. */
export function clearSession(): void {
  currentToken = null;
  session.user = null;
  if (refreshTimer !== undefined) {
    clearTimeout(refreshTimer);
    refreshTimer = undefined;
  }
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures on clear.
  }
}

// Restored session: schedule its refresh. A token already past its window
// refreshes on the MIN_DELAY floor; if that 401s, the user is signed out.
if (initial) scheduleRefresh(initial.expiresAt);
