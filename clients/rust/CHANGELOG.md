---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-07-19"
---

# Changelog — `mp` CLI & Rust SDK

All notable changes to the Rust workspace (`clients/rust`) are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are published from the `cli-v<version>` tags — see
[Releasing](./README.md#releasing).

## [Unreleased]

## [0.1.0] — unreleased

Initial release of the Rust client.

### Added

- **`master-plan-sdk`** — typed Rust client over the API: projects, work
  entries, reports, and health, with a structured error type that carries the
  server's error envelope (`code`, `message`, `request_id`).
- **`mp` CLI** — API-key-driven command-line client:
  - `mp projects list | get <id> | create | delete <id>`
  - `mp work list | log --project … --minutes … --kind …`
  - `mp report --days 30 [--project …]`
  - `mp health`
  - `mp completions <bash|zsh|fish|powershell|elvish>`
  - `--json` for scriptable output, `--color` control, and `--url` / `--api-key`
    with `MASTER_PLAN_API_URL` / `MASTER_PLAN_API_KEY` fallbacks.
- **`.env` support** — the nearest `.env` (searched upward from the working
  directory) is loaded at startup. Precedence: flag > real environment
  variable > `.env`; existing variables are never overwritten.
- **Release automation** — tagging `cli-v*` builds binaries for Linux
  (x86_64 gnu/musl, aarch64), macOS (Apple Silicon and Intel), and Windows
  (x86_64), and publishes them with `SHA256SUMS` to a GitHub Release.

[Unreleased]: https://github.com/pedroanisio/master-plan-painel/compare/cli-v0.1.0...HEAD
[0.1.0]: https://github.com/pedroanisio/master-plan-painel/releases/tag/cli-v0.1.0
