// Client for the public, unauthenticated entry point.

import { apiGet } from "./http";

export interface PublicInfo {
  service: string;
  version: string;
  authenticated: boolean;
  message: string;
  public_routes: string[];
  authenticated_routes: string[];
}

/** Fetch the public service info. Requires no bearer token. */
export function getPublic(): Promise<PublicInfo> {
  return apiGet<PublicInfo>("/api/public");
}
