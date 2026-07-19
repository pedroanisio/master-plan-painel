//! The HTTP client. Every request is authenticated with the `X-API-Key` header.

use crate::error::{ApiErrorBody, Error, Result};
use crate::models::{Health, Project, ProjectInput, PublicInfo, WorkEntry, WorkEntryInput, WorkReport};
use reqwest::blocking::{Client as HttpClient, RequestBuilder, Response};
use serde::de::DeserializeOwned;

const DEFAULT_BASE_URL: &str = "https://build-journal.dev";

/// A typed client over the master-plan-painel API, authenticated with an API key.
///
/// The key acts as its owner; it can read and write that owner's projects and
/// work entries but cannot manage sessions or other keys.
#[derive(Debug, Clone)]
pub struct Client {
    base_url: String,
    api_key: String,
    http: HttpClient,
}

impl Client {
    /// Build a client for `base_url`, authenticating every request with `api_key`.
    pub fn new(base_url: impl Into<String>, api_key: impl Into<String>) -> Result<Self> {
        let api_key = api_key.into();
        if api_key.trim().is_empty() {
            return Err(Error::Config("API key is empty".into()));
        }
        let base_url = base_url.into().trim_end_matches('/').to_string();
        let http = HttpClient::builder()
            .user_agent(concat!("master-plan-sdk/", env!("CARGO_PKG_VERSION")))
            .build()?;
        Ok(Self { base_url, api_key, http })
    }

    /// Build a client from the environment: `MASTER_PLAN_API_URL`
    /// (default `https://build-journal.dev`) and `MASTER_PLAN_API_KEY` (required).
    pub fn from_env() -> Result<Self> {
        let base_url =
            std::env::var("MASTER_PLAN_API_URL").unwrap_or_else(|_| DEFAULT_BASE_URL.to_string());
        let api_key = std::env::var("MASTER_PLAN_API_KEY")
            .map_err(|_| Error::Config("MASTER_PLAN_API_KEY is not set".into()))?;
        Self::new(base_url, api_key)
    }

    /// The base URL this client targets (without the trailing slash).
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    fn url(&self, path: &str) -> String {
        format!("{}/api{}", self.base_url, path)
    }

    fn send_json<T: DeserializeOwned>(&self, rb: RequestBuilder) -> Result<T> {
        let resp = rb.header("X-API-Key", &self.api_key).send()?;
        Ok(check(resp)?.json()?)
    }

    fn send_empty(&self, rb: RequestBuilder) -> Result<()> {
        let resp = rb.header("X-API-Key", &self.api_key).send()?;
        check(resp)?;
        Ok(())
    }

    // -- health / public --------------------------------------------------

    /// `GET /api/health`
    pub fn health(&self) -> Result<Health> {
        self.send_json(self.http.get(self.url("/health")))
    }

    /// `GET /api/public`
    pub fn public(&self) -> Result<PublicInfo> {
        self.send_json(self.http.get(self.url("/public")))
    }

    // -- projects ---------------------------------------------------------

    /// `GET /api/projects`
    pub fn list_projects(&self) -> Result<Vec<Project>> {
        self.send_json(self.http.get(self.url("/projects")))
    }

    /// `GET /api/projects/{id}`
    pub fn get_project(&self, id: &str) -> Result<Project> {
        self.send_json(self.http.get(self.url(&format!("/projects/{id}"))))
    }

    /// `POST /api/projects`
    pub fn create_project(&self, input: &ProjectInput) -> Result<Project> {
        self.send_json(self.http.post(self.url("/projects")).json(input))
    }

    /// `PUT /api/projects/{id}` — full replace.
    pub fn update_project(&self, id: &str, input: &ProjectInput) -> Result<Project> {
        self.send_json(self.http.put(self.url(&format!("/projects/{id}"))).json(input))
    }

    /// `DELETE /api/projects/{id}`
    pub fn delete_project(&self, id: &str) -> Result<()> {
        self.send_empty(self.http.delete(self.url(&format!("/projects/{id}"))))
    }

    // -- work entries -----------------------------------------------------

    /// `GET /api/work-entries`
    pub fn list_work_entries(&self) -> Result<Vec<WorkEntry>> {
        self.send_json(self.http.get(self.url("/work-entries")))
    }

    /// `GET /api/work-entries/{id}`
    pub fn get_work_entry(&self, id: &str) -> Result<WorkEntry> {
        self.send_json(self.http.get(self.url(&format!("/work-entries/{id}"))))
    }

    /// `POST /api/work-entries`
    pub fn create_work_entry(&self, input: &WorkEntryInput) -> Result<WorkEntry> {
        self.send_json(self.http.post(self.url("/work-entries")).json(input))
    }

    /// `DELETE /api/work-entries/{id}`
    pub fn delete_work_entry(&self, id: &str) -> Result<()> {
        self.send_empty(self.http.delete(self.url(&format!("/work-entries/{id}"))))
    }

    // -- reports ----------------------------------------------------------

    /// `GET /api/work-report` — optionally scoped to a window and/or project.
    pub fn work_report(&self, days: Option<u32>, project: Option<&str>) -> Result<WorkReport> {
        let mut query: Vec<(&str, String)> = Vec::new();
        if let Some(d) = days {
            query.push(("days", d.to_string()));
        }
        if let Some(p) = project {
            query.push(("project", p.to_string()));
        }
        let rb = self.http.get(self.url("/work-report")).query(&query);
        self.send_json(rb)
    }
}

/// Map a non-2xx response onto a structured [`Error`], parsing the error envelope.
fn check(resp: Response) -> Result<Response> {
    let status = resp.status();
    if status.is_success() {
        return Ok(resp);
    }
    let code = status.as_u16();
    let body = resp.text().unwrap_or_default();
    Err(error_from(code, body))
}

/// Build a structured [`Error`] from a non-2xx status + body, parsing the
/// `{"error": {...}}` envelope when present. Pure — unit-testable without a
/// live server.
fn error_from(status: u16, body: String) -> Error {
    if let Ok(value) = serde_json::from_str::<serde_json::Value>(&body) {
        if let Some(err) = value.get("error") {
            if let Ok(parsed) = serde_json::from_value::<ApiErrorBody>(err.clone()) {
                return Error::Api {
                    status,
                    code: parsed.code,
                    message: parsed.message,
                    request_id: parsed.request_id,
                };
            }
        }
    }
    Error::UnexpectedStatus { status, body }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_rejects_empty_key() {
        assert!(matches!(Client::new("https://x", "   "), Err(Error::Config(_))));
    }

    #[test]
    fn new_trims_trailing_slash() {
        let client = Client::new("https://x/", "k").unwrap();
        assert_eq!(client.base_url(), "https://x");
        assert_eq!(client.url("/projects"), "https://x/api/projects");
    }

    #[test]
    fn error_from_parses_envelope() {
        let body =
            r#"{"error":{"code":"not_found","message":"Not Found","request_id":"abc"}}"#.to_string();
        match error_from(404, body) {
            Error::Api { status, code, message, request_id } => {
                assert_eq!(status, 404);
                assert_eq!(code, "not_found");
                assert_eq!(message, "Not Found");
                assert_eq!(request_id.as_deref(), Some("abc"));
            }
            other => panic!("expected Api error, got {other:?}"),
        }
    }

    #[test]
    fn error_from_falls_back_when_not_an_envelope() {
        match error_from(500, "boom".to_string()) {
            Error::UnexpectedStatus { status, body } => {
                assert_eq!(status, 500);
                assert_eq!(body, "boom");
            }
            other => panic!("expected UnexpectedStatus, got {other:?}"),
        }
    }
}
