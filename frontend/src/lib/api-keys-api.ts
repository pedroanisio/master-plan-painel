// Typed client for the API-key management endpoints (session-authenticated).

import { apiDelete, apiGet, apiSend } from "./http";
import type { ApiKeyCreateInput, ApiKeyCreated, ApiKeyPublic } from "./api-key-types";

const BASE = "/api/auth/api-keys";

export function listApiKeys(): Promise<ApiKeyPublic[]> {
  return apiGet<ApiKeyPublic[]>(BASE);
}

/** Create a key. The returned `token` is shown once and never again. */
export function createApiKey(input: ApiKeyCreateInput): Promise<ApiKeyCreated> {
  return apiSend<ApiKeyCreated>("POST", BASE, input);
}

export function revokeApiKey(id: string): Promise<void> {
  return apiDelete(`${BASE}/${encodeURIComponent(id)}`);
}
