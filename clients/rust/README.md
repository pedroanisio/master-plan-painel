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

## Build

```bash
cd clients/rust
cargo build --release        # binary at target/release/mp
cargo test                   # SDK unit tests (no network)
cargo clippy --all-targets   # lints
```

## Configure

Both read the environment (CLI flags override):

| Variable | Default | Meaning |
|---|---|---|
| `MASTER_PLAN_API_URL` | `https://build-journal.dev` | API base URL |
| `MASTER_PLAN_API_KEY` | — (required) | an `mpk_…` API key; the key acts as its owner |

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
