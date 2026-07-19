// Client for the work-report endpoint (period- and project-scoped effort).

import { apiGet } from "./http";

export interface WorkReport {
  days: number | null;
  from_date: string | null;
  to_date: string;
  project: string | null;
  total_minutes: number;
  entry_count: number;
  active_days: number;
  avg_minutes_per_active_day: number;
  by_project: Record<string, number>;
  by_kind: Record<string, number>;
  by_day: Record<string, number>;
  busiest_project: string | null;
  busiest_day: string | null;
}

/** Fetch a full report. `days` = 7/30/90/… (omit for all-time); optional project scope. */
export function getWorkReport(days?: number, project?: string): Promise<WorkReport> {
  const params = new URLSearchParams();
  if (days) params.set("days", String(days));
  if (project) params.set("project", project);
  const qs = params.toString();
  return apiGet<WorkReport>(`/api/work-report${qs ? `?${qs}` : ""}`);
}
