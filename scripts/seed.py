#!/usr/bin/env python3
"""Seed the catalogue with realistic demo data for exercising the UI/analytics.

Generates, for a single demo user who owns everything (the app is owner-scoped
and auth-gated):

* 1 user   — log in with these credentials to see the data.
* 64 projects — varied domains, languages, packages; unique names and color ids.
* ~180 days of work-log entries — weekday-weighted, a few "busy" projects
  dominating, so the analytics (totals, per-project, per-kind, per-day) have
  real shape.

The data is written by driving the actual repositories, not by hand-authoring
JSON — so it is validated through the live Pydantic models and stays correct as
the schema evolves (owner_id, color_id ranges, migrations, ...).

Determinism: a fixed RNG seed and a fixed "today" anchor make every run
reproducible. Re-running resets the target files unless --no-reset is given.

Usage:
    PYTHONPATH=src python3 scripts/seed.py [--out DIR] [--no-reset]

Defaults write to ./data (the app's default DB location). To seed the running
container instead, run this inside it so it writes to the mounted volume:
    docker compose exec api python3 /app/scripts/seed.py --out /data
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from master_plan.api.repository import ProjectRepository
from master_plan.api.user_repository import UserRepository
from master_plan.api.work_repository import WorkLogRepository
from master_plan.models.auth import UserRegistration
from master_plan.models.project import (
    DependencyScope,
    Language,
    Package,
    PackageEcosystem,
    Project,
)
from master_plan.models.work_log import Complexity, WorkEntry, WorkKind

# --- demo account ----------------------------------------------------------
DEMO_EMAIL = "demo@faz.ai"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo-pass-2026"

# --- reproducibility -------------------------------------------------------
RNG_SEED = 20260718
TODAY = date(2026, 7, 18)  # anchor so performed_at is stable across runs
DAYS = 180

# --- project vocabulary ----------------------------------------------------
# Each domain carries a plausible language pool and a package pool keyed by the
# primary language, so generated projects read as real codebases.
DOMAINS: list[dict] = [
    {
        "domain": "developer-tooling", "subs": ["cataloguing", "linting", "ci"],
        "langs": [Language.PYTHON, Language.RUST, Language.TYPESCRIPT],
    },
    {
        "domain": "data-platform", "subs": ["ingestion", "warehouse", "streaming"],
        "langs": [Language.PYTHON, Language.SCALA, Language.SQL, Language.JAVA],
    },
    {
        "domain": "fintech", "subs": ["payments", "ledger", "risk"],
        "langs": [Language.JAVA, Language.KOTLIN, Language.GO, Language.PYTHON],
    },
    {
        "domain": "ml-infra", "subs": ["training", "serving", "feature-store"],
        "langs": [Language.PYTHON, Language.CPP, Language.RUST],
    },
    {
        "domain": "web", "subs": ["storefront", "dashboard", "cms"],
        "langs": [Language.TYPESCRIPT, Language.JAVASCRIPT, Language.CSS, Language.HTML],
    },
    {
        "domain": "mobile", "subs": ["ios", "android", "cross-platform"],
        "langs": [Language.SWIFT, Language.KOTLIN, Language.TYPESCRIPT],
    },
    {
        "domain": "devops", "subs": ["orchestration", "observability", "provisioning"],
        "langs": [Language.GO, Language.SHELL, Language.PYTHON],
    },
    {
        "domain": "security", "subs": ["scanning", "identity", "secrets"],
        "langs": [Language.RUST, Language.GO, Language.PYTHON],
    },
    {
        "domain": "gaming", "subs": ["engine", "netcode", "tooling"],
        "langs": [Language.CPP, Language.CSHARP, Language.LUA],
    },
    {
        "domain": "research", "subs": ["simulation", "analysis", "viz"],
        "langs": [Language.JULIA, Language.R, Language.PYTHON],
    },
]

PACKAGES: dict[Language, list[tuple[str, PackageEcosystem]]] = {
    Language.PYTHON: [("pydantic", PackageEcosystem.PYPI), ("fastapi", PackageEcosystem.PYPI),
                      ("numpy", PackageEcosystem.PYPI), ("httpx", PackageEcosystem.PYPI),
                      ("sqlalchemy", PackageEcosystem.PYPI)],
    Language.TYPESCRIPT: [("svelte", PackageEcosystem.NPM), ("vite", PackageEcosystem.NPM),
                          ("zod", PackageEcosystem.NPM), ("react", PackageEcosystem.NPM)],
    Language.JAVASCRIPT: [("express", PackageEcosystem.NPM), ("lodash", PackageEcosystem.NPM)],
    Language.RUST: [("serde", PackageEcosystem.CARGO), ("tokio", PackageEcosystem.CARGO),
                    ("clap", PackageEcosystem.CARGO), ("axum", PackageEcosystem.CARGO)],
    Language.GO: [("cobra", PackageEcosystem.GO_MODULES), ("gin", PackageEcosystem.GO_MODULES)],
    Language.JAVA: [("spring-boot", PackageEcosystem.MAVEN), ("guava", PackageEcosystem.MAVEN)],
    Language.KOTLIN: [("ktor", PackageEcosystem.MAVEN), ("coroutines", PackageEcosystem.MAVEN)],
    Language.SCALA: [("akka", PackageEcosystem.MAVEN), ("cats", PackageEcosystem.MAVEN)],
    Language.CPP: [("boost", PackageEcosystem.SYSTEM), ("eigen", PackageEcosystem.SYSTEM)],
    Language.CSHARP: [("newtonsoft.json", PackageEcosystem.NUGET)],
    Language.SWIFT: [("alamofire", PackageEcosystem.OTHER)],
    Language.JULIA: [("DataFrames", PackageEcosystem.OTHER)],
    Language.R: [("tidyverse", PackageEcosystem.OTHER)],
    Language.SQL: [("dbt", PackageEcosystem.PYPI)],
}

NAME_HEADS = [
    "atlas", "nimbus", "quartz", "vertex", "pulsar", "cobalt", "helix", "onyx",
    "delta", "sable", "cinder", "harbor", "lumen", "cypress", "orbit", "flux",
    "sierra", "tundra", "beacon", "mosaic", "cascade", "vault", "prism", "relay",
    "summit", "canyon", "meridian", "zephyr", "quill", "amber", "basalt", "drift",
]
NAME_TAILS = [
    "gateway", "engine", "pipeline", "forge", "sync", "mesh", "core", "runner",
    "hub", "ledger", "index", "stream", "bridge", "planner", "compass", "vault",
]


def build_projects(rng: random.Random) -> list[Project]:
    """Construct 64 unique, valid projects with color ids 1..64."""
    names: set[str] = set()
    projects: list[Project] = []
    color_id = 1
    while len(projects) < 64:
        spec = DOMAINS[len(projects) % len(DOMAINS)]
        head = rng.choice(NAME_HEADS)
        tail = rng.choice(NAME_TAILS)
        name = f"{head}-{tail}"
        if name in names:
            continue
        names.add(name)

        # 1–3 languages from the domain pool; the first is primary.
        k = rng.randint(1, min(3, len(spec["langs"])))
        langs = rng.sample(spec["langs"], k)
        primary = langs[0]

        # 1–4 packages drawn from the languages actually used.
        pkgs: list[Package] = []
        seen_keys: set[tuple[PackageEcosystem, str]] = set()
        for _ in range(rng.randint(1, 4)):
            lang = rng.choice(langs)
            pool = PACKAGES.get(lang)
            if not pool:
                continue
            pkg_name, eco = rng.choice(pool)
            key = (eco, pkg_name.lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            pkgs.append(Package(
                name=pkg_name,
                ecosystem=eco,
                version=f"{rng.randint(0, 4)}.{rng.randint(0, 20)}.{rng.randint(0, 9)}",
                scope=rng.choice([DependencyScope.RUNTIME, DependencyScope.RUNTIME,
                                  DependencyScope.DEV, DependencyScope.TEST]),
            ))

        sub = rng.choice(spec["subs"])
        projects.append(Project(
            name=name,
            color_id=color_id,
            domain=spec["domain"],
            sub_domain=sub,
            purpose=f"{sub.capitalize()} service for the {spec['domain']} domain.",
            languages=langs,
            primary_language=primary,
            packages=pkgs,
            repository=f"https://git.faz.ai/faz/{name}",
            description=f"A {spec['domain']} project focused on {sub}.",
            tags=rng.sample(["internal", "core", "experimental", "oss", "legacy",
                             "priority"], rng.randint(0, 3)),
        ))
        color_id += 1
    return projects


# Work-log shape --------------------------------------------------------------
KIND_WEIGHTS = [
    (WorkKind.FEATURE, 30), (WorkKind.BUGFIX, 22), (WorkKind.REFACTOR, 12),
    (WorkKind.TEST, 10), (WorkKind.REVIEW, 8), (WorkKind.DOCS, 6),
    (WorkKind.INFRA, 5), (WorkKind.RESEARCH, 3), (WorkKind.PLANNING, 2),
    (WorkKind.MEETING, 2),
]
MINUTE_CHOICES = [15, 20, 25, 30, 30, 45, 60, 60, 90, 120, 150, 180, 240]
COMPLEXITY_CHOICES = [None, None, Complexity.XS, Complexity.S, Complexity.S,
                      Complexity.M, Complexity.M, Complexity.L, Complexity.XL]
SUMMARIES = {
    WorkKind.FEATURE: ["implement {n} endpoint", "add {n} support", "wire up {n} flow"],
    WorkKind.BUGFIX: ["fix {n} crash", "patch {n} regression", "handle {n} edge case"],
    WorkKind.REFACTOR: ["extract {n} module", "simplify {n} logic", "tidy {n} internals"],
    WorkKind.TEST: ["cover {n} paths", "add {n} integration tests"],
    WorkKind.REVIEW: ["review {n} PR", "pair on {n}"],
    WorkKind.DOCS: ["document {n}", "write {n} runbook"],
    WorkKind.INFRA: ["provision {n} pipeline", "tune {n} deploy"],
    WorkKind.RESEARCH: ["spike {n} approach", "benchmark {n}"],
    WorkKind.PLANNING: ["scope {n} milestone"],
    WorkKind.MEETING: ["sync on {n}"],
}


def build_entries(rng: random.Random, projects: list[Project]) -> list[WorkEntry]:
    """Generate ~180 days of weekday-weighted entries with skewed project focus."""
    # Zipf-like weights: a handful of projects absorb most of the effort.
    ranked = projects[:]
    rng.shuffle(ranked)
    weights = [1.0 / (i + 1) for i in range(len(ranked))]

    kinds = [k for k, _ in KIND_WEIGHTS]
    kind_w = [w for _, w in KIND_WEIGHTS]

    entries: list[WorkEntry] = []
    for offset in range(DAYS):
        day = TODAY - timedelta(days=DAYS - 1 - offset)
        weekday = day.weekday()  # 0=Mon .. 6=Sun
        if weekday >= 5:  # weekend: usually quiet
            count = rng.choices([0, 1, 2], weights=[70, 22, 8])[0]
        else:
            count = rng.choices([0, 1, 2, 3, 4, 5], weights=[8, 20, 28, 24, 14, 6])[0]

        for _ in range(count):
            project = rng.choices(ranked, weights=weights)[0]
            kind = rng.choices(kinds, weights=kind_w)[0]
            noun = project.sub_domain or project.domain
            summary = rng.choice(SUMMARIES[kind]).format(n=noun)
            stamp = datetime.combine(
                day,
                time(hour=rng.randint(8, 19), minute=rng.choice([0, 15, 30, 45])),
                tzinfo=timezone.utc,
            )
            entries.append(WorkEntry(
                project=project.name,
                performed_at=stamp,
                minutes=rng.choice(MINUTE_CHOICES),
                kind=kind,
                summary=summary,
                complexity=rng.choice(COMPLEXITY_CHOICES),
                tags=rng.sample(["focus", "oncall", "pairing", "blocked"],
                                rng.randint(0, 2)),
            ))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo catalogue + work log.")
    parser.add_argument("--out", default="./data", help="output directory (default ./data)")
    parser.add_argument("--no-reset", action="store_true",
                        help="append to existing files instead of replacing them")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    projects_db = out / "projects.json"
    worklog_db = out / "work_entries.json"
    users_db = out / "users.json"

    if not args.no_reset:
        for path in (projects_db, worklog_db, users_db):
            path.unlink(missing_ok=True)

    rng = random.Random(RNG_SEED)

    # 1) demo user (the owner of everything)
    users = UserRepository(users_db)
    existing = users.get_by_identifier(DEMO_USERNAME)
    if existing is None:
        owner = users.create(UserRegistration(
            email=DEMO_EMAIL, username=DEMO_USERNAME,
            password=DEMO_PASSWORD, password_confirm=DEMO_PASSWORD,
        ))
    else:
        owner = existing
    owner_id = owner.id

    # 2) projects
    project_repo = ProjectRepository(projects_db)
    projects = build_projects(rng)
    for project in projects:
        project_repo.create(project, owner_id)

    # 3) work log
    work_repo = WorkLogRepository(worklog_db)
    entries = build_entries(rng, projects)
    for entry in entries:
        work_repo.create(entry, owner_id)

    total_minutes = sum(e.minutes for e in entries)
    print("Seed complete.")
    print(f"  user      : {DEMO_USERNAME} / {DEMO_PASSWORD}  ({DEMO_EMAIL})")
    print(f"  projects  : {len(projects)}  (color ids 1..{len(projects)})")
    print(f"  entries   : {len(entries)} over {DAYS} days")
    print(f"  logged    : {total_minutes} min  (~{total_minutes / 60:.0f} h)")
    print(f"  written to: {projects_db}, {worklog_db}, {users_db}")


if __name__ == "__main__":
    main()
