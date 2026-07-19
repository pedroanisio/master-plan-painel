// Shared fetch helpers for the API clients.
//
// ARCHITECTURAL REQUIREMENT (PALS's LAW): server responses are untrusted input.
// Every non-2xx response is turned into a thrown ApiError carrying the backend
// error envelope (code, message, field details, request id), rather than being
// silently ignored. Parsing is defensive: a malformed or non-envelope body
// falls back to the HTTP status line.

import { getToken } from "./auth-store.svelte";

/** A single field-level validation problem from the error envelope. */
export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    /** Stable, machine-readable code from the envelope (e.g. "duplicate_name"). */
    public readonly code: string | null = null,
    /** Field-level validation problems, when the backend supplied them. */
    public readonly details: FieldError[] = [],
    /** Correlates with the server log line; surface it in bug reports. */
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Build request headers, adding the bearer token when a session exists. */
function authHeaders(base: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...base, Authorization: `Bearer ${token}` } : base;
}

async function parseError(response: Response): Promise<never> {
  let message = `${response.status} ${response.statusText}`;
  let code: string | null = null;
  let details: FieldError[] = [];
  let requestId: string | null = response.headers.get("X-Request-ID");
  try {
    const body = await response.json();
    // Primary contract: the unified error envelope {error: {code, message, ...}}.
    const err = body?.error;
    if (err && typeof err.message === "string") {
      message = err.message;
      code = typeof err.code === "string" ? err.code : null;
      requestId = typeof err.request_id === "string" ? err.request_id : requestId;
      if (Array.isArray(err.details)) {
        details = err.details
          .filter(
            (d: unknown): d is FieldError =>
              !!d &&
              typeof (d as FieldError).field === "string" &&
              typeof (d as FieldError).message === "string",
          )
          .map((d: FieldError) => ({ field: d.field, message: d.message }));
      }
    } else if (typeof body?.detail === "string") {
      // Defensive fallback for any response not yet on the envelope.
      message = body.detail;
    }
  } catch {
    // Non-JSON body; keep the status line.
  }
  throw new ApiError(response.status, message, code, details, requestId);
}

export async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function apiSend<T>(
  method: "POST" | "PUT" | "PATCH",
  url: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function apiDelete(url: string): Promise<void> {
  const res = await fetch(url, { method: "DELETE", headers: authHeaders() });
  if (!res.ok) await parseError(res);
}
