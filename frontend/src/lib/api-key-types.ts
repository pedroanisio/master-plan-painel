// Types mirroring the backend API-key schemas (master_plan.api.api_key_schemas).

export const API_KEY_SCOPES = ["read", "write"] as const;
export type ApiKeyScope = (typeof API_KEY_SCOPES)[number];

// Safe view returned by the list endpoint (no secret).
export interface ApiKeyPublic {
  id: string;
  name: string;
  prefix: string;
  scopes: ApiKeyScope[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

// Creation response — carries the plaintext token exactly once.
export interface ApiKeyCreated extends ApiKeyPublic {
  token: string;
}

// Body for POST /api/auth/api-keys.
export interface ApiKeyCreateInput {
  name: string;
  scopes: ApiKeyScope[];
  expires_in_days: number | null;
}
