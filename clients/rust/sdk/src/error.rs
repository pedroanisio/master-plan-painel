//! Error types for the SDK.

/// The `{"error": {...}}` envelope every API error response carries.
#[derive(Debug, Clone, serde::Deserialize)]
pub struct ApiErrorBody {
    pub code: String,
    pub message: String,
    #[serde(default)]
    pub request_id: Option<String>,
}

/// Anything that can go wrong talking to the API.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// A non-2xx response carrying the structured error envelope.
    #[error("API error {status} ({code}): {message}")]
    Api {
        status: u16,
        code: String,
        message: String,
        request_id: Option<String>,
    },
    /// A non-2xx response that did not match the error envelope.
    #[error("unexpected HTTP {status}: {body}")]
    UnexpectedStatus { status: u16, body: String },
    /// Transport / connection failure (DNS, TLS, timeout, …).
    #[error("request failed: {0}")]
    Transport(#[from] reqwest::Error),
    /// Client misconfiguration (e.g. an empty API key).
    #[error("configuration error: {0}")]
    Config(String),
}

impl Error {
    /// The `request_id` from the server, when the error carried one.
    pub fn request_id(&self) -> Option<&str> {
        match self {
            Error::Api { request_id, .. } => request_id.as_deref(),
            _ => None,
        }
    }
}

pub type Result<T> = std::result::Result<T, Error>;
