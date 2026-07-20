//! Minimal `.env` support: load `KEY=VALUE` pairs from the nearest `.env` file.
//!
//! Loaded once at startup, *before* clap parses, so every `[env: …]` fallback
//! (`MASTER_PLAN_API_KEY`, `MASTER_PLAN_API_URL`) picks the values up.
//!
//! Precedence is deliberate and matches the usual dotenv contract:
//!
//!   `--flag`  >  a real environment variable  >  `.env`
//!
//! i.e. a variable already present in the process environment is **never**
//! overwritten by the file. Hand-rolled rather than pulling in a crate: the
//! format we need is a handful of lines and this keeps the CLI dependency-free.

use std::{
    env, fs,
    path::{Path, PathBuf},
};

/// Find the nearest `.env`, walking up from `start` to the filesystem root.
///
/// This means `mp` picks up the project's `.env` from any subdirectory.
pub fn find(start: &Path) -> Option<PathBuf> {
    let mut dir = Some(start);
    while let Some(d) = dir {
        let candidate = d.join(".env");
        if candidate.is_file() {
            return Some(candidate);
        }
        dir = d.parent();
    }
    None
}

/// Parse `.env` contents into key/value pairs.
///
/// Supports blank lines, `#` comments, an optional `export ` prefix, and
/// single/double-quoted values. An unquoted value may carry a trailing ` #`
/// comment, which is stripped.
pub fn parse(contents: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    for raw in contents.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let line = line.strip_prefix("export ").unwrap_or(line).trim_start();
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        if key.is_empty() {
            continue;
        }
        let mut value = value.trim();
        let quoted = value.len() >= 2
            && ((value.starts_with('"') && value.ends_with('"'))
                || (value.starts_with('\'') && value.ends_with('\'')));
        if quoted {
            value = &value[1..value.len() - 1];
        } else if let Some(idx) = value.find(" #") {
            value = value[..idx].trim_end();
        }
        out.push((key.to_string(), value.to_string()));
    }
    out
}

/// Load the nearest `.env` into the process environment, if one exists.
///
/// Returns the file that was applied, for optional diagnostics. Variables that
/// are already set are left untouched, so the real environment always wins.
pub fn load() -> Option<PathBuf> {
    let cwd = env::current_dir().ok()?;
    let path = find(&cwd)?;
    let contents = fs::read_to_string(&path).ok()?;
    for (key, value) in parse(&contents) {
        if env::var_os(&key).is_none() {
            env::set_var(&key, &value);
        }
    }
    Some(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_simple_pairs() {
        let got = parse("MASTER_PLAN_API_KEY=mpk_abc\nMASTER_PLAN_API_URL=http://x\n");
        assert_eq!(
            got,
            vec![
                ("MASTER_PLAN_API_KEY".into(), "mpk_abc".into()),
                ("MASTER_PLAN_API_URL".into(), "http://x".into()),
            ]
        );
    }

    #[test]
    fn skips_blanks_and_comments() {
        let got = parse("\n# a comment\n\nK=v\n");
        assert_eq!(got, vec![("K".into(), "v".into())]);
    }

    #[test]
    fn handles_export_prefix_and_spaces() {
        let got = parse("export  K = v \n");
        assert_eq!(got, vec![("K".into(), "v".into())]);
    }

    #[test]
    fn strips_matching_quotes() {
        let got = parse("A=\"quoted value\"\nB='single'\n");
        assert_eq!(
            got,
            vec![
                ("A".into(), "quoted value".into()),
                ("B".into(), "single".into()),
            ]
        );
    }

    #[test]
    fn keeps_hash_inside_quotes_but_strips_trailing_comment() {
        let got = parse("A=\"pa#ss\"\nB=plain # trailing\n");
        assert_eq!(
            got,
            vec![("A".into(), "pa#ss".into()), ("B".into(), "plain".into())]
        );
    }

    #[test]
    fn ignores_malformed_lines() {
        let got = parse("no_equals_here\n=novalue\nK=v\n");
        assert_eq!(got, vec![("K".into(), "v".into())]);
    }

    #[test]
    fn find_walks_up_to_the_nearest_env() {
        let tmp = std::env::temp_dir().join(format!("mp-envtest-{}", std::process::id()));
        let nested = tmp.join("a/b/c");
        fs::create_dir_all(&nested).unwrap();
        fs::write(tmp.join(".env"), "K=v\n").unwrap();
        assert_eq!(find(&nested), Some(tmp.join(".env")));
        fs::remove_dir_all(&tmp).ok();
    }
}
