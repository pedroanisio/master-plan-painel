//! Output helpers: TTY/NO_COLOR-aware coloring and simple aligned tables.
//!
//! Discipline: primary data goes to stdout; status/notes go to stderr.

use crate::cli::ColorChoice;
use is_terminal::IsTerminal;

/// Rendering context resolved once from the flags + environment.
pub struct Ui {
    pub color: bool,
    pub json: bool,
}

impl Ui {
    pub fn new(choice: ColorChoice, json: bool) -> Self {
        let color = match choice {
            ColorChoice::Always => true,
            ColorChoice::Never => false,
            // Honour https://no-color.org and only paint a real terminal.
            ColorChoice::Auto => {
                std::io::stdout().is_terminal() && std::env::var_os("NO_COLOR").is_none()
            }
        };
        Self { color, json }
    }

    fn paint(&self, code: &str, s: &str) -> String {
        if self.color {
            format!("\x1b[{code}m{s}\x1b[0m")
        } else {
            s.to_string()
        }
    }

    pub fn green(&self, s: &str) -> String {
        self.paint("32", s)
    }
    pub fn red(&self, s: &str) -> String {
        self.paint("31", s)
    }
    pub fn yellow(&self, s: &str) -> String {
        self.paint("33", s)
    }
    pub fn dim(&self, s: &str) -> String {
        self.paint("2", s)
    }
    pub fn bold(&self, s: &str) -> String {
        self.paint("1", s)
    }
    pub fn cyan(&self, s: &str) -> String {
        self.paint("36", s)
    }
}

/// First `n` chars of `s` (used to show short ids).
pub fn short(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        s.chars().take(n).collect()
    }
}

/// Truncate to `n` chars with an ellipsis when longer.
pub fn ellipsize(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let head: String = s.chars().take(n.saturating_sub(1)).collect();
        format!("{head}…")
    }
}

fn pad(s: &str, width: usize) -> String {
    let len = s.chars().count();
    if len >= width {
        s.to_string()
    } else {
        format!("{}{}", s, " ".repeat(width - len))
    }
}

/// Print a left-aligned table with a dimmed header row. `headers` and every
/// row must have the same number of columns.
pub fn table(headers: &[&str], rows: &[Vec<String>], ui: &Ui) {
    let cols = headers.len();
    let mut widths: Vec<usize> = headers.iter().map(|h| h.chars().count()).collect();
    for row in rows {
        for (i, cell) in row.iter().enumerate().take(cols) {
            widths[i] = widths[i].max(cell.chars().count());
        }
    }

    let mut header_line = String::new();
    for (i, (h, w)) in headers.iter().zip(&widths).enumerate() {
        header_line.push_str(&pad(h, *w));
        if i + 1 < cols {
            header_line.push_str("  ");
        }
    }
    println!("{}", ui.dim(&header_line));

    for row in rows {
        let mut line = String::new();
        for (i, w) in widths.iter().enumerate() {
            let cell = row.get(i).map(String::as_str).unwrap_or("");
            line.push_str(&pad(cell, *w));
            if i + 1 < cols {
                line.push_str("  ");
            }
        }
        println!("{line}");
    }
}

/// Format minutes as `Nh Mm` (or `Mm`).
pub fn hm(minutes: u32) -> String {
    let (h, m) = (minutes / 60, minutes % 60);
    if h > 0 {
        format!("{h}h {m:02}m")
    } else {
        format!("{m}m")
    }
}
