---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-07-19"
---

# Rust SDK & CLI — master-plan-painel

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

A Cargo workspace with two crates:

| Crate | What it is |
|---|---|
| [`master-plan-sdk`](sdk/) | Typed, blocking HTTP client for the API. API-key auth (`X-API-Key`), structured errors that parse the `{"error":{…}}` envelope. |
| [`master-plan-cli`](cli/) | The `mp` binary — a human-first CLI over the SDK. |

## Install

**From a release** (no Rust toolchain needed) — grab the archive for your
platform from the [Releases page](https://github.com/pedroanisio/master-plan-painel/releases),
verify it against `SHA256SUMS`, and put `mp` on your PATH:

```bash
V=0.1.0; T=x86_64-unknown-linux-gnu
curl -LO https://github.com/pedroanisio/master-plan-painel/releases/download/cli-v$V/mp-$V-$T.tar.gz
curl -LO https://github.com/pedroanisio/master-plan-painel/releases/download/cli-v$V/SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
tar -xzf mp-$V-$T.tar.gz
install -m755 mp-$V-$T/mp ~/.local/bin/mp    # any dir on your PATH
mp --version
```

Prebuilt targets: Linux `x86_64` (gnu + static musl) and `aarch64`, macOS
Apple Silicon and Intel, Windows `x86_64`.

**From source:**

```bash
cargo install --path clients/rust/cli        # installs into ~/.cargo/bin
```

Shell completions:

```bash
mp completions zsh > ~/.zfunc/_mp            # bash | zsh | fish | powershell | elvish
```

## Build

```bash
cd clients/rust
cargo build --release        # binary at target/release/mp
cargo test                   # SDK unit tests (no network)
cargo clippy --all-targets   # lints
cargo fmt --all --check      # formatting gate (same as CI)
```

## Configure

Both read the environment (CLI flags override):

| Variable | Default | Meaning |
|---|---|---|
| `MASTER_PLAN_API_URL` | `https://build-journal.dev` | API base URL |
| `MASTER_PLAN_API_KEY` | — (required) | an `mpk_…` API key; the key acts as its owner |

Values may also come from a **`.env` file** — `mp` searches the working
directory and each parent, loading the nearest one at startup. Precedence is
`--flag` > real environment variable > `.env`, so a variable already exported is
never overwritten. Keep `.env` out of version control (it already is).

## Releasing

Releases are automated by
[`.github/workflows/cli-release.yml`](../../.github/workflows/cli-release.yml),
triggered by a `cli-v*` tag (the `cli-` prefix keeps CLI releases distinct from
app/API releases in this repo).

1. Bump `version` under `[workspace.package]` in `clients/rust/Cargo.toml`.
2. Move the entries in [`CHANGELOG.md`](./CHANGELOG.md) from *Unreleased* into
   the new version.
3. Commit, then tag and push:

   ```bash
   git tag cli-v0.1.0
   git push origin cli-v0.1.0
   ```

The workflow **fails fast if the tag version and `Cargo.toml` disagree**, then
builds every target, and publishes the archives plus a `SHA256SUMS` file to a
GitHub Release. Re-running against an existing tag re-uploads assets
(`--clobber`) rather than creating a duplicate release.

Every push/PR touching `clients/rust/**` is gated by
[`cli-ci.yml`](../../.github/workflows/cli-ci.yml): `cargo fmt --check`,
`clippy -D warnings`, `cargo test`, and a locked release build.

## CLI usage

```bash
export MASTER_PLAN_API_KEY=mpk_…

mp health
mp projects list
mp projects get <id>
mp projects create --name recipe-forge --color-id 2 --domain developer-tooling \
  --purpose "…" --language rust --tag framework
mp work log --project master-plan-app --minutes 30 --kind feature \
  --summary "…" --complexity M --tag rust
mp work list --project master-plan-app
mp report --days 30
mp --json projects list | jq '.[].name'      # machine-readable
mp completions zsh > _mp                      # shell completions
```

Conventions:
- Primary output → stdout; status/notes → stderr, so pipelines stay clean.
- `--json` emits raw JSON; otherwise aligned, colorized tables.
- `--color auto|always|never` (auto respects TTY detection and `NO_COLOR`).
- Destructive commands (`delete`) prompt for confirmation; in a non-interactive
  shell they refuse unless `--yes` is passed.
- Exit code `0` on success, `1` on error (message printed to stderr).

## SDK usage

```rust
use master_plan_sdk::{Client, WorkEntryInput};

let client = Client::from_env()?;
for p in client.list_projects()? {
    println!("{}  {}", p.name, p.domain);
}
# Ok::<(), master_plan_sdk::Error>(())
```

---

Up to the [project root](../../README.md).
