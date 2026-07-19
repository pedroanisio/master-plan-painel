// Typed client for the work-log API.

import { apiDelete, apiGet, apiSend } from "./http";
import type { WorkEntryInput, WorkEntryRecord, WorkSummary } from "./work-types";

const BASE = "/api/work-entries";

export function listWorkEntries(project?: string): Promise<WorkEntryRecord[]> {
  const query = project ? `?project=${encodeURIComponent(project)}` : "";
  return apiGet<WorkEntryRecord[]>(`${BASE}${query}`);
}

export function getWorkEntry(id: string): Promise<WorkEntryRecord> {
  return apiGet<WorkEntryRecord>(`${BASE}/${encodeURIComponent(id)}`);
}

export function createWorkEntry(input: WorkEntryInput): Promise<WorkEntryRecord> {
  return apiSend<WorkEntryRecord>("POST", BASE, input);
}

export function updateWorkEntry(
  id: string,
  input: WorkEntryInput,
): Promise<WorkEntryRecord> {
  return apiSend<WorkEntryRecord>("PUT", `${BASE}/${encodeURIComponent(id)}`, input);
}

export function deleteWorkEntry(id: string): Promise<void> {
  return apiDelete(`${BASE}/${encodeURIComponent(id)}`);
}

export function getWorkSummary(): Promise<WorkSummary> {
  return apiGet<WorkSummary>("/api/work-summary");
}
