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
