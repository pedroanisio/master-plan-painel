// Types mirroring the backend auth models (master_plan.models.auth) and the
// auth schemas (master_plan.api.auth_schemas).

export const ROLES = ["viewer", "editor", "admin"] as const;
export type Role = (typeof ROLES)[number];

// The secret-free user returned by the API.
export interface User {
  email: string;
  username: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
}

// Body for POST /api/auth/register.
export interface RegisterInput {
  email: string;
  username: string;
  full_name: string | null;
  password: string;
  password_confirm: string;
}

// Body for POST /api/auth/login.
export interface LoginInput {
  identifier: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number | null;
}

// Returned by both register and login.
export interface AuthResponse {
  user: User;
  token: Token;
}
