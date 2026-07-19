//! Typed Rust client (SDK) for the **master-plan-painel** API.
//!
//! Authenticate with an API key (`mpk_…`) and drive the project catalogue and
//! work log:
//!
//! ```no_run
//! use master_plan_sdk::Client;
//!
//! let client = Client::from_env()?; // MASTER_PLAN_API_URL + MASTER_PLAN_API_KEY
//! for p in client.list_projects()? {
//!     println!("{:>8}  {}  ({})", &p.id[..8.min(p.id.len())], p.name, p.domain);
//! }
//! # Ok::<(), master_plan_sdk::Error>(())
//! ```

pub mod client;
pub mod error;
pub mod models;

pub use client::Client;
pub use error::{ApiErrorBody, Error, Result};
pub use models::{
    Health, Package, Project, ProjectInput, PublicInfo, WorkEntry, WorkEntryInput, WorkReport,
};
