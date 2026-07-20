//! `mp` — command-line client for the master-plan-painel API.

mod cli;
mod env_file;
mod output;

use anyhow::{anyhow, Context, Result};
use chrono::{SecondsFormat, Utc};
use clap::{CommandFactory, Parser};
use cli::{Cli, Command, ProjectsCmd, WorkCmd};
use is_terminal::IsTerminal;
use master_plan_sdk::{Client, Project, ProjectInput, WorkEntryInput, WorkReport};
use output::{ellipsize, hm, short, table, Ui};
use std::io::Write;

fn main() {
    // Load the nearest `.env` before clap parses, so the `[env: …]` fallbacks
    // (MASTER_PLAN_API_KEY / _API_URL) can come from the file. Real environment
    // variables are never overwritten, and an explicit flag still wins.
    let _ = env_file::load();

    let cli = Cli::parse();
    let ui = Ui::new(cli.color, cli.json);
    if let Err(err) = run(&cli, &ui) {
        // Human-readable error to stderr; primary output stays on stdout.
        eprintln!("{} {err:#}", ui.red("error:"));
        std::process::exit(1);
    }
}

fn run(cli: &Cli, ui: &Ui) -> Result<()> {
    // `completions` needs no network / API key.
    if let Command::Completions { shell } = &cli.command {
        let mut cmd = Cli::command();
        clap_complete::generate(*shell, &mut cmd, "mp", &mut std::io::stdout());
        return Ok(());
    }

    let key = cli
        .api_key
        .clone()
        .ok_or_else(|| anyhow!("no API key — set MASTER_PLAN_API_KEY or pass --api-key <mpk_…>"))?;
    let client = Client::new(&cli.url, key).context("building API client")?;

    match &cli.command {
        Command::Health => health(&client, ui)?,
        Command::Projects(cmd) => projects(&client, ui, cmd)?,
        Command::Work(cmd) => work(&client, ui, cmd)?,
        Command::Report(args) => report(&client, ui, args.days, args.project.as_deref())?,
        Command::Completions { .. } => unreachable!("handled above"),
    }
    Ok(())
}

// -- health -------------------------------------------------------------------

fn health(client: &Client, ui: &Ui) -> Result<()> {
    let h = client.health()?;
    if ui.json {
        return print_json(&h);
    }
    let mark = if h.status == "ok" {
        ui.green("●")
    } else {
        ui.yellow("●")
    };
    println!("{mark} {} — {}", h.status, ui.dim(client.base_url()));
    Ok(())
}

// -- projects -----------------------------------------------------------------

fn projects(client: &Client, ui: &Ui, cmd: &ProjectsCmd) -> Result<()> {
    match cmd {
        ProjectsCmd::List => {
            let items = client.list_projects()?;
            if ui.json {
                return print_json(&items);
            }
            if items.is_empty() {
                println!("{}", ui.dim("No projects."));
                return Ok(());
            }
            let rows: Vec<Vec<String>> = items
                .iter()
                .map(|p| {
                    vec![
                        short(&p.id, 8),
                        ui.cyan(&p.name),
                        domain_of(p),
                        ellipsize(&p.languages.join(", "), 24),
                        p.packages.len().to_string(),
                    ]
                })
                .collect();
            table(&["ID", "NAME", "DOMAIN", "LANGUAGES", "PKGS"], &rows, ui);
            eprintln!("{}", ui.dim(&format!("{} project(s)", items.len())));
        }
        ProjectsCmd::Get { id } => {
            let p = client.get_project(id)?;
            if ui.json {
                return print_json(&p);
            }
            print_project(&p, ui);
        }
        ProjectsCmd::Create(a) => {
            let input = ProjectInput {
                name: a.name.clone(),
                color_id: a.color_id,
                domain: a.domain.clone(),
                sub_domain: a.sub_domain.clone(),
                purpose: a.purpose.clone(),
                languages: a.languages.clone(),
                primary_language: a.primary_language.clone(),
                packages: Vec::new(),
                repository: a.repository.clone(),
                description: a.description.clone(),
                tags: a.tags.clone(),
            };
            let p = client.create_project(&input)?;
            if ui.json {
                return print_json(&p);
            }
            println!(
                "{} created project {} {}",
                ui.green("✓"),
                ui.bold(&p.name),
                ui.dim(&format!("({})", short(&p.id, 8)))
            );
        }
        ProjectsCmd::Delete { id, yes } => {
            let name = client
                .get_project(id)
                .map(|p| p.name)
                .unwrap_or_else(|_| id.clone());
            if !confirm(ui, &format!("Delete project “{name}”?"), *yes)? {
                println!("{}", ui.dim("Aborted."));
                return Ok(());
            }
            client.delete_project(id)?;
            println!("{} deleted {name}", ui.green("✓"));
        }
    }
    Ok(())
}

// -- work ---------------------------------------------------------------------

fn work(client: &Client, ui: &Ui, cmd: &WorkCmd) -> Result<()> {
    match cmd {
        WorkCmd::List { project, limit } => {
            let mut items = client.list_work_entries()?;
            if let Some(p) = project {
                items.retain(|e| &e.project == p);
            }
            // Newest first.
            items.sort_by(|a, b| b.performed_at.cmp(&a.performed_at));
            if let Some(n) = limit {
                items.truncate(*n);
            }
            if ui.json {
                return print_json(&items);
            }
            if items.is_empty() {
                println!("{}", ui.dim("No work entries."));
                return Ok(());
            }
            let rows: Vec<Vec<String>> = items
                .iter()
                .map(|e| {
                    vec![
                        short(&e.id, 8),
                        when(&e.performed_at),
                        ui.cyan(&e.project),
                        e.kind.clone(),
                        hm(e.minutes),
                        e.complexity.clone().unwrap_or_else(|| "—".into()),
                        ellipsize(e.summary.as_deref().unwrap_or("—"), 40),
                    ]
                })
                .collect();
            table(
                &["ID", "WHEN", "PROJECT", "KIND", "TIME", "CX", "SUMMARY"],
                &rows,
                ui,
            );
            let total: u32 = items.iter().map(|e| e.minutes).sum();
            eprintln!(
                "{}",
                ui.dim(&format!("{} entr(ies) · {}", items.len(), hm(total)))
            );
        }
        WorkCmd::Log(a) => {
            let performed_at =
                a.at.clone()
                    .unwrap_or_else(|| Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true));
            let input = WorkEntryInput {
                project: a.project.clone(),
                performed_at,
                minutes: a.minutes,
                kind: a.kind.as_str().to_string(),
                summary: a.summary.clone(),
                complexity: a.complexity.map(|c| c.as_str().to_string()),
                tags: a.tags.clone(),
            };
            let e = client.create_work_entry(&input)?;
            if ui.json {
                return print_json(&e);
            }
            println!(
                "{} logged {} · {} on {} {}",
                ui.green("✓"),
                ui.bold(&hm(e.minutes)),
                e.kind,
                ui.cyan(&e.project),
                ui.dim(&format!("({})", short(&e.id, 8)))
            );
        }
        WorkCmd::Delete { id, yes } => {
            if !confirm(ui, &format!("Delete work entry {}?", short(id, 8)), *yes)? {
                println!("{}", ui.dim("Aborted."));
                return Ok(());
            }
            client.delete_work_entry(id)?;
            println!("{} deleted entry {}", ui.green("✓"), short(id, 8));
        }
    }
    Ok(())
}

// -- report -------------------------------------------------------------------

fn report(client: &Client, ui: &Ui, days: Option<u32>, project: Option<&str>) -> Result<()> {
    let r: WorkReport = client.work_report(days, project)?;
    if ui.json {
        return print_json(&r);
    }
    let range = match &r.from_date {
        Some(from) => format!("{from} → {}", r.to_date),
        None => format!("all time → {}", r.to_date),
    };
    let scope = r.project.clone().unwrap_or_else(|| "all projects".into());
    println!("{}  {}", ui.bold(&scope), ui.dim(&range));
    if r.entry_count == 0 {
        println!("{}", ui.dim("No work logged in this period."));
        return Ok(());
    }
    println!(
        "  total {}   entries {}   active days {}   avg/active {}",
        ui.bold(&hm(r.total_minutes)),
        r.entry_count,
        r.active_days,
        hm(r.avg_minutes_per_active_day.round() as u32),
    );
    if !r.by_project.is_empty() {
        println!("\n{}", ui.dim("BY PROJECT"));
        print_breakdown(&r.by_project, ui);
    }
    if !r.by_kind.is_empty() {
        println!("\n{}", ui.dim("BY KIND"));
        print_breakdown(&r.by_kind, ui);
    }
    Ok(())
}

fn print_breakdown(map: &std::collections::BTreeMap<String, u32>, ui: &Ui) {
    let max = map.values().copied().max().unwrap_or(1).max(1);
    let mut pairs: Vec<(&String, &u32)> = map.iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(a.1));
    let rows: Vec<Vec<String>> = pairs
        .iter()
        .map(|(name, mins)| {
            let bar_len = ((**mins as f64 / max as f64) * 24.0).round() as usize;
            vec![
                ellipsize(name, 22),
                ui.cyan(&"█".repeat(bar_len.max(1))),
                hm(**mins),
            ]
        })
        .collect();
    table(&["", "", ""], &rows, ui);
}

// -- helpers ------------------------------------------------------------------

fn domain_of(p: &Project) -> String {
    match &p.sub_domain {
        Some(sub) if !sub.is_empty() => format!("{}/{}", p.domain, sub),
        _ => p.domain.clone(),
    }
}

/// Trim an RFC3339 timestamp to `YYYY-MM-DD HH:MM` for compact display.
fn when(iso: &str) -> String {
    let compact: String = iso.chars().take(16).collect();
    compact.replace('T', " ")
}

fn print_project(p: &Project, ui: &Ui) {
    println!("{}  {}", ui.bold(&p.name), ui.dim(&p.id));
    let field = |label: &str, value: &str| {
        println!("  {}  {}", ui.dim(&format!("{label:<14}")), value);
    };
    field("domain", &domain_of(p));
    field("color id", &p.color_id.to_string());
    field("primary lang", p.primary_language.as_deref().unwrap_or("—"));
    field("languages", &p.languages.join(", "));
    if let Some(repo) = &p.repository {
        field("repository", repo);
    }
    if !p.tags.is_empty() {
        field("tags", &p.tags.join(", "));
    }
    field("purpose", &p.purpose);
    if let Some(desc) = &p.description {
        field("description", desc);
    }
    if p.packages.is_empty() {
        field("packages", &ui.dim("none"));
    } else {
        println!("  {}", ui.dim(&format!("packages ({})", p.packages.len())));
        let rows: Vec<Vec<String>> = p
            .packages
            .iter()
            .map(|pkg| {
                vec![
                    format!("    {}", pkg.name),
                    pkg.ecosystem.clone(),
                    pkg.version.clone().unwrap_or_else(|| "—".into()),
                    pkg.scope.clone(),
                    pkg.extras.join(", "),
                ]
            })
            .collect();
        table(
            &["  NAME", "ECOSYSTEM", "VERSION", "SCOPE", "EXTRAS"],
            &rows,
            ui,
        );
    }
}

fn print_json<T: serde::Serialize>(value: &T) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(value)?);
    Ok(())
}

/// Ask for confirmation on a destructive action. Returns `true` to proceed.
/// Non-interactive (no TTY) without `--yes` is a hard error, not a silent yes.
fn confirm(ui: &Ui, prompt: &str, yes: bool) -> Result<bool> {
    if yes {
        return Ok(true);
    }
    if !std::io::stdin().is_terminal() {
        return Err(anyhow!(
            "{prompt} refusing without confirmation in a non-interactive shell — pass --yes"
        ));
    }
    eprint!("{} {} {}", ui.yellow("?"), prompt, ui.dim("[y/N] "));
    std::io::stderr().flush().ok();
    let mut line = String::new();
    std::io::stdin().read_line(&mut line)?;
    Ok(matches!(line.trim(), "y" | "Y" | "yes" | "Yes"))
}
