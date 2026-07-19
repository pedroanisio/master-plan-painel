---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Codex GPT-5 via Codex"
  date: "2026-07-19"
---

# master-plan-painel

## Why We Built This

We believe personal and team work should not disappear into scattered notes,
memory, and half-remembered context. When a person maintains many codebases,
the hard part is often not writing the next change; it is knowing what each
project is for, what effort has already gone into it, and where attention has
actually been spent.

The status quo makes this knowledge fragile. Project intent lives in one place,
dependencies in another, work history somewhere else, and the owner is left to
reconstruct the story later. This project exists to keep that story visible.

---

## How We Approach This

- **Purpose before inventory** — A project record must explain why the codebase
  exists, not merely list its parts.
- **Actual work over estimates** — The work log records time already spent; it
  should not become a forecasting or performance-pressure system.
- **Simple storage, explicit limits** — Local, readable files are preferred
  until the project truly needs a database or concurrent writers.
- **Trust is earned at the boundary** — User input, credentials, server errors,
  and generated output are treated as things to validate, not things to assume.
- **Private by default** — Each user should see and change only their own
  catalogue, work log, and keys.

---

## What It Does

### Core Capabilities

- Catalogues codebases by name, purpose, domain, language, dependencies, tags,
  repository, description, and display color.
- Logs completed work against projects with date, duration, kind, summary,
  complexity, and tags.
- Reports totals by project, work kind, and day so attention patterns are
  visible.
- Provides authenticated access through browser sessions and scoped API keys.
- Serves a Svelte user interface backed by a FastAPI API and JSON persistence.

### What This Is Not

This project does **not**:

- Replace a project management system, issue tracker, or roadmap tool.
- Estimate future effort or rank people by productivity.
- Optimize for multi-worker writes or large-team concurrent editing while it
  uses JSON-file persistence.
- Treat generated or external data as correct without validation.

---

## Who This Is For

- **Maintainers with many codebases** — They get a durable view of what each
  project is for and where work has gone.
- **Small technical teams** — They can share a lightweight catalogue without
  adopting a heavy management platform.
- **Future contributors** — They can judge proposed changes against stable
  purpose, privacy, validation, and storage principles.
