// Types mirroring the backend work-log models (master_plan.models.work_log).

export const WORK_KINDS = [
  "feature",
  "bugfix",
  "refactor",
  "docs",
  "test",
  "review",
  "research",
  "planning",
  "infra",
  "maintenance",
  "meeting",
  "other",
] as const;
export type WorkKind = (typeof WORK_KINDS)[number];

export const COMPLEXITIES = ["XS", "S", "M", "L", "XL"] as const;
export type Complexity = (typeof COMPLEXITIES)[number];

// Body sent on create (POST) and replace (PUT).
export interface WorkEntryInput {
  project: string;
  performed_at: string; // ISO 8601
  minutes: number;
  kind: WorkKind;
  summary: string | null;
  complexity: Complexity | null;
  tags: string[];
}

// A persisted work entry as returned by the API.
export interface WorkEntryRecord extends WorkEntryInput {
  id: string;
  owner_id: string; // id of the user that owns this entry
}

export interface WorkSummary {
  total_minutes: number;
  by_project: Record<string, number>;
  busiest_project: string | null;
}

export function emptyWorkEntry(project = ""): WorkEntryInput {
  return {
    project,
    performed_at: "",
    minutes: 30,
    kind: "feature",
    summary: null,
    complexity: null,
    tags: [],
  };
}

/** Format minutes as e.g. "2h 30m" (or "45m"). */
export function formatMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h && m) return `${h}h ${m}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}
