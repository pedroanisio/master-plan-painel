//! Serde models mirroring the API's request/response shapes.
//!
//! Open-ended enums (ecosystem, scope, work kind, complexity) are kept as
//! `String` so the client never breaks when the server adds a new value.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// A package dependency recorded against a project.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Package {
    pub name: String,
    pub ecosystem: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    pub scope: String,
    #[serde(default)]
    pub extras: Vec<String>,
}

/// A project record as returned by the API (includes server-assigned fields).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    #[serde(default)]
    pub owner_id: String,
    pub name: String,
    pub color_id: u32,
    pub domain: String,
    #[serde(default)]
    pub sub_domain: Option<String>,
    pub purpose: String,
    #[serde(default)]
    pub languages: Vec<String>,
    #[serde(default)]
    pub primary_language: Option<String>,
    #[serde(default)]
    pub packages: Vec<Package>,
    #[serde(default)]
    pub repository: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
}

/// The writable shape for creating/replacing a project.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProjectInput {
    pub name: String,
    pub color_id: u32,
    pub domain: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sub_domain: Option<String>,
    pub purpose: String,
    pub languages: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub primary_language: Option<String>,
    #[serde(default)]
    pub packages: Vec<Package>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub repository: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
}

/// A logged unit of work as returned by the API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkEntry {
    pub id: String,
    #[serde(default)]
    pub owner_id: String,
    pub project: String,
    pub performed_at: String,
    pub minutes: u32,
    pub kind: String,
    #[serde(default)]
    pub summary: Option<String>,
    #[serde(default)]
    pub complexity: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
}

/// The writable shape for logging work.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkEntryInput {
    pub project: String,
    pub performed_at: String,
    pub minutes: u32,
    pub kind: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub complexity: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
}

/// Aggregated work report over a period.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkReport {
    #[serde(default)]
    pub from_date: Option<String>,
    #[serde(default)]
    pub to_date: String,
    #[serde(default)]
    pub project: Option<String>,
    #[serde(default)]
    pub total_minutes: u32,
    #[serde(default)]
    pub entry_count: u32,
    #[serde(default)]
    pub active_days: u32,
    #[serde(default)]
    pub avg_minutes_per_active_day: f64,
    #[serde(default)]
    pub busiest_day: Option<String>,
    #[serde(default)]
    pub busiest_project: Option<String>,
    #[serde(default)]
    pub by_project: BTreeMap<String, u32>,
    #[serde(default)]
    pub by_kind: BTreeMap<String, u32>,
    #[serde(default)]
    pub by_day: BTreeMap<String, u32>,
}

/// `GET /api/health` response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Health {
    pub status: String,
}

/// `GET /api/public` response (service advertisement).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublicInfo {
    #[serde(default)]
    pub service: String,
    #[serde(default)]
    pub version: String,
    /// Any additional fields the server includes.
    #[serde(flatten)]
    pub extra: serde_json::Value,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn project_input_skips_none_fields() {
        let input = ProjectInput {
            name: "x".into(),
            color_id: 1,
            domain: "d".into(),
            purpose: "p".into(),
            languages: vec!["python".into()],
            ..Default::default()
        };
        let json = serde_json::to_value(&input).unwrap();
        assert_eq!(json["name"], "x");
        assert_eq!(json["color_id"], 1);
        // Optional fields left None must not appear in the payload.
        assert!(json.get("sub_domain").is_none());
        assert!(json.get("repository").is_none());
    }

    #[test]
    fn project_deserializes_from_api_shape() {
        let raw = r#"{"id":"1","owner_id":"o","name":"n","color_id":2,"domain":"d",
                     "purpose":"p","languages":["python"],"packages":[],"tags":[]}"#;
        let p: Project = serde_json::from_str(raw).unwrap();
        assert_eq!(p.name, "n");
        assert_eq!(p.color_id, 2);
        assert!(p.sub_domain.is_none());
    }

    #[test]
    fn work_report_tolerates_missing_fields() {
        // Sparse payloads must still deserialize (server may omit zeros).
        let r: WorkReport = serde_json::from_str(r#"{"to_date":"2026-07-19"}"#).unwrap();
        assert_eq!(r.total_minutes, 0);
        assert_eq!(r.to_date, "2026-07-19");
    }
}
