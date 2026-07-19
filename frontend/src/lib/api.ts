// Typed client for the Project CRUDL API.

import { ApiError, apiDelete, apiGet, apiSend } from "./http";
import type { ProjectInput, ProjectRecord } from "./types";

export { ApiError };

const BASE = "/api/projects";

export function listProjects(): Promise<ProjectRecord[]> {
  return apiGet<ProjectRecord[]>(BASE);
}

export function getProject(id: string): Promise<ProjectRecord> {
  return apiGet<ProjectRecord>(`${BASE}/${encodeURIComponent(id)}`);
}

export function createProject(input: ProjectInput): Promise<ProjectRecord> {
  return apiSend<ProjectRecord>("POST", BASE, input);
}

export function updateProject(
  id: string,
  input: ProjectInput,
): Promise<ProjectRecord> {
  return apiSend<ProjectRecord>("PUT", `${BASE}/${encodeURIComponent(id)}`, input);
}

export function deleteProject(id: string): Promise<void> {
  return apiDelete(`${BASE}/${encodeURIComponent(id)}`);
}
