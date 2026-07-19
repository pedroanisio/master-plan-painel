// Types mirroring the backend Pydantic models (master_plan.models.project).

import { PALETTE } from "./palette";

export const LANGUAGES = [
  "python",
  "typescript",
  "javascript",
  "rust",
  "go",
  "java",
  "kotlin",
  "swift",
  "c",
  "cpp",
  "csharp",
  "ruby",
  "php",
  "scala",
  "elixir",
  "haskell",
  "lua",
  "r",
  "julia",
  "shell",
  "sql",
  "html",
  "css",
  "other",
] as const;
export type Language = (typeof LANGUAGES)[number];

export const ECOSYSTEMS = [
  "pypi",
  "npm",
  "cargo",
  "go_modules",
  "maven",
  "nuget",
  "rubygems",
  "packagist",
  "hex",
  "hackage",
  "system",
  "other",
] as const;
export type PackageEcosystem = (typeof ECOSYSTEMS)[number];

export const SCOPES = ["runtime", "dev", "test", "build", "optional"] as const;
export type DependencyScope = (typeof SCOPES)[number];

export interface Package {
  name: string;
  ecosystem: PackageEcosystem;
  version: string | null;
  scope: DependencyScope;
  extras: string[];
}

// Inclusive bounds for a project's unique display color id. The upper bound is
// the palette size: every id maps 1:1 to a distinct precomputed color, so the
// catalogue holds at most PALETTE.length projects, each visibly separable.
export const COLOR_ID_MIN = 1;
export const COLOR_ID_MAX = PALETTE.length; // 256

// Body sent on create (POST) and replace (PUT).
export interface ProjectInput {
  name: string;
  color_id: number;
  domain: string;
  sub_domain: string | null;
  purpose: string;
  languages: Language[];
  primary_language: Language | null;
  packages: Package[];
  repository: string | null;
  description: string | null;
  tags: string[];
}

// A persisted project as returned by the API.
export interface ProjectRecord extends ProjectInput {
  id: string;
  owner_id: string; // id of the user that owns this project
}

export function emptyInput(color_id = COLOR_ID_MIN): ProjectInput {
  return {
    name: "",
    color_id,
    domain: "",
    sub_domain: null,
    purpose: "",
    languages: [],
    primary_language: null,
    packages: [],
    repository: null,
    description: null,
    tags: [],
  };
}

export function emptyPackage(): Package {
  return { name: "", ecosystem: "pypi", version: null, scope: "runtime", extras: [] };
}

/**
 * Display color for a `color_id`, as a CSS `oklch()` string.
 *
 * This is the theme helper that turns a *position* (the integer id) into a
 * concrete color. It indexes the fixed {@link PALETTE} — 256 colors chosen by
 * farthest-point sampling in OKLab (see `scripts/generate-palette.mjs`) for the
 * best achievable worst-case perceptual separation at this count.
 *
 * The mapping is 1:1 across the valid range `[COLOR_ID_MIN, COLOR_ID_MAX]`.
 * Ids outside it wrap modulo the palette size — a defensive fallback so any
 * integer yields a color; it is never reached for assigned ids, since the
 * range is capped at the palette size and the repository keeps ids unique.
 */
export function colorForId(colorId: number): string {
  const size = PALETTE.length;
  const index = (((colorId - COLOR_ID_MIN) % size) + size) % size;
  return PALETTE[index];
}

/** Smallest color id in [MIN, MAX] not present in `taken`, or MIN if full. */
export function nextFreeColorId(taken: Iterable<number>): number {
  const used = new Set(taken);
  for (let c = COLOR_ID_MIN; c <= COLOR_ID_MAX; c++) {
    if (!used.has(c)) return c;
  }
  return COLOR_ID_MIN;
}
