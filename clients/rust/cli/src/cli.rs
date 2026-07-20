//! Argument surface (clap derive). Types are as narrow as the domain allows so
//! invalid states are unrepresentable (closed enums, ranged integers).

use clap::{Args, Parser, Subcommand, ValueEnum};

/// Operate the master-plan-painel API from the terminal.
///
/// EXAMPLES:
///   mp projects list
///   mp projects get 751c5beb…
///   mp work log --project master-plan-app --minutes 30 --kind infra --summary "Deploy"
///   mp report --days 30
///   mp --json projects list | jq '.[].name'
///
/// AUTH: export MASTER_PLAN_API_KEY=mpk_…  (or pass --api-key).
/// Target another server with MASTER_PLAN_API_URL or --url.
#[derive(Debug, Parser)]
#[command(name = "mp", version, about, long_about, propagate_version = true)]
pub struct Cli {
    /// API base URL.
    #[arg(
        long,
        global = true,
        env = "MASTER_PLAN_API_URL",
        default_value = "https://build-journal.dev"
    )]
    pub url: String,

    /// API key (`mpk_…`). Prefer the env var to keep it out of shell history.
    #[arg(
        long,
        global = true,
        env = "MASTER_PLAN_API_KEY",
        hide_env_values = true
    )]
    pub api_key: Option<String>,

    /// Emit raw JSON instead of formatted tables (for scripts / jq).
    #[arg(long, global = true)]
    pub json: bool,

    /// When to colorize output.
    #[arg(long, global = true, value_enum, default_value_t = ColorChoice::Auto)]
    pub color: ColorChoice,

    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum ColorChoice {
    /// Colorize only when stdout is a TTY and NO_COLOR is unset.
    Auto,
    Always,
    Never,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Check the API is reachable and healthy.
    Health,
    /// Manage projects (codebases in the catalogue).
    #[command(subcommand)]
    Projects(ProjectsCmd),
    /// Log and inspect work entries.
    #[command(subcommand)]
    Work(WorkCmd),
    /// Show an aggregated work report.
    Report(ReportArgs),
    /// Generate a shell completion script (bash|zsh|fish|powershell|elvish).
    Completions {
        /// Target shell.
        shell: clap_complete::Shell,
    },
}

#[derive(Debug, Subcommand)]
pub enum ProjectsCmd {
    /// List all projects.
    List,
    /// Show one project by id.
    Get {
        /// Project id (full or unambiguous prefix as accepted by the server).
        id: String,
    },
    /// Create a project.
    Create(ProjectCreateArgs),
    /// Delete a project by id.
    Delete {
        /// Project id.
        id: String,
        /// Skip the confirmation prompt.
        #[arg(long, short = 'y')]
        yes: bool,
    },
}

#[derive(Debug, Args)]
pub struct ProjectCreateArgs {
    /// Project name (unique per owner).
    #[arg(long)]
    pub name: String,
    /// Palette colour id (1–256, unique per owner).
    #[arg(long, value_parser = clap::value_parser!(u32).range(1..=256))]
    pub color_id: u32,
    /// Top-level domain, e.g. developer-tooling.
    #[arg(long)]
    pub domain: String,
    /// What the codebase exists to do.
    #[arg(long)]
    pub purpose: String,
    /// Language (repeatable); at least one required.
    #[arg(long = "language", value_name = "LANG", required = true)]
    pub languages: Vec<String>,
    /// Primary language (defaults server-side to the first selected).
    #[arg(long)]
    pub primary_language: Option<String>,
    /// Optional sub-domain.
    #[arg(long)]
    pub sub_domain: Option<String>,
    /// Repository URL or path.
    #[arg(long)]
    pub repository: Option<String>,
    /// Free-text description.
    #[arg(long)]
    pub description: Option<String>,
    /// Tag (repeatable).
    #[arg(long = "tag", value_name = "TAG")]
    pub tags: Vec<String>,
}

#[derive(Debug, Subcommand)]
pub enum WorkCmd {
    /// List work entries (newest first), optionally filtered by project.
    List {
        /// Only entries for this project name.
        #[arg(long)]
        project: Option<String>,
        /// Show at most this many rows.
        #[arg(long)]
        limit: Option<usize>,
    },
    /// Log a work session.
    Log(WorkLogArgs),
    /// Delete a work entry by id.
    Delete {
        /// Entry id.
        id: String,
        #[arg(long, short = 'y')]
        yes: bool,
    },
}

#[derive(Debug, Args)]
pub struct WorkLogArgs {
    /// Project name to log against.
    #[arg(long)]
    pub project: String,
    /// Duration in minutes (>= 1).
    #[arg(long, value_parser = clap::value_parser!(u32).range(1..))]
    pub minutes: u32,
    /// Kind of work.
    #[arg(long, value_enum)]
    pub kind: Kind,
    /// One-line summary.
    #[arg(long)]
    pub summary: Option<String>,
    /// Complexity (t-shirt size).
    #[arg(long, value_enum)]
    pub complexity: Option<Complexity>,
    /// Tag (repeatable).
    #[arg(long = "tag", value_name = "TAG")]
    pub tags: Vec<String>,
    /// When it happened (RFC3339). Defaults to now (UTC).
    #[arg(long, value_name = "RFC3339")]
    pub at: Option<String>,
}

#[derive(Debug, Args)]
pub struct ReportArgs {
    /// Window in days (omit for all-time).
    #[arg(long)]
    pub days: Option<u32>,
    /// Restrict to one project.
    #[arg(long)]
    pub project: Option<String>,
}

/// Kinds of work, mirroring the server's closed set.
#[derive(Debug, Clone, Copy, ValueEnum)]
#[value(rename_all = "lowercase")]
pub enum Kind {
    Feature,
    Bugfix,
    Refactor,
    Docs,
    Test,
    Review,
    Research,
    Planning,
    Infra,
    Maintenance,
    Meeting,
    Other,
}

impl Kind {
    pub fn as_str(self) -> &'static str {
        use Kind::*;
        match self {
            Feature => "feature",
            Bugfix => "bugfix",
            Refactor => "refactor",
            Docs => "docs",
            Test => "test",
            Review => "review",
            Research => "research",
            Planning => "planning",
            Infra => "infra",
            Maintenance => "maintenance",
            Meeting => "meeting",
            Other => "other",
        }
    }
}

/// Complexity t-shirt sizes.
#[derive(Debug, Clone, Copy, ValueEnum)]
pub enum Complexity {
    #[value(name = "XS")]
    Xs,
    #[value(name = "S")]
    S,
    #[value(name = "M")]
    M,
    #[value(name = "L")]
    L,
    #[value(name = "XL")]
    Xl,
}

impl Complexity {
    pub fn as_str(self) -> &'static str {
        match self {
            Complexity::Xs => "XS",
            Complexity::S => "S",
            Complexity::M => "M",
            Complexity::L => "L",
            Complexity::Xl => "XL",
        }
    }
}
