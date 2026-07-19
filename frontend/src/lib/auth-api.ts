// Typed client for the authentication API.

import { ApiError, apiGet, apiSend } from "./http";
import type { AuthResponse, LoginInput, RegisterInput, User } from "./auth-types";

export { ApiError };

const BASE = "/api/auth";

export function register(input: RegisterInput): Promise<AuthResponse> {
  return apiSend<AuthResponse>("POST", `${BASE}/register`, input);
}

export function login(input: LoginInput): Promise<AuthResponse> {
  return apiSend<AuthResponse>("POST", `${BASE}/login`, input);
}

/** Resolve the current bearer token to its user (401 if invalid/expired). */
export function me(): Promise<User> {
  return apiGet<User>(`${BASE}/me`);
}

/**
 * Exchange the current (still-valid) session token for a fresh one.
 * Rejects with a 401 ApiError once the token has expired — the caller must
 * then sign in again. The body is empty; `{}` satisfies the JSON helper.
 */
export function refresh(): Promise<AuthResponse> {
  return apiSend<AuthResponse>("POST", `${BASE}/refresh`, {});
}
