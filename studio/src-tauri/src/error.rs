//! Unified Error System for Sunwell Studio
//!
//! Provides structured error handling matching the Python error system (core/errors.py).
//! Errors serialize to JSON for the Svelte frontend to parse and display with recovery hints.
//!
//! # Usage
//!
//! ```rust
//! use crate::error::{SunwellError, ErrorCode};
//! use crate::sunwell_err;
//!
//! // Create a new error
//! let err = SunwellError::new(ErrorCode::SkillExecutionFailed, "Skill timed out");
//!
//! // With context
//! let err = sunwell_err!(FileNotFound, "Config not found: {}", path);
//!
//! // From std::io::Error
//! let err: SunwellError = io_error.into();
//! ```

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Error codes matching Python's ErrorCode enum.
/// Derived from schemas/error-codes.yaml (single source of truth).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u16)]
pub enum ErrorCode {
    // Model errors (1xxx)
    ModelNotFound = 1001,
    ModelAuthFailed = 1002,
    ModelRateLimited = 1003,
    ModelContextExceeded = 1004,
    ModelTimeout = 1005,
    ModelApiError = 1006,
    ModelToolsNotSupported = 1007,
    ModelStreamingNotSupported = 1008,
    ModelProviderUnavailable = 1009,
    ModelResponseInvalid = 1010,

    // Lens errors (2xxx)
    LensNotFound = 2001,
    LensParseError = 2002,
    LensCircularDependency = 2003,
    LensVersionConflict = 2004,
    LensMergeConflict = 2005,
    LensInvalidSchema = 2006,
    LensFountUnavailable = 2007,

    // Tool/Skill errors (3xxx)
    ToolNotFound = 3001,
    ToolPermissionDenied = 3002,
    ToolExecutionFailed = 3003,
    ToolTimeout = 3004,
    ToolInvalidArguments = 3005,
    SkillNotFound = 3101,
    SkillParseError = 3102,
    SkillExecutionFailed = 3103,
    SkillValidationFailed = 3104,
    SkillSandboxViolation = 3105,

    // Validation errors (4xxx)
    ValidationScriptFailed = 4001,
    ValidationTimeout = 4002,
    ValidationInvalidOutput = 4003,
    ValidationConfidenceLow = 4004,

    // Config errors (5xxx)
    ConfigMissing = 5001,
    ConfigInvalid = 5002,
    ConfigEnvMissing = 5003,

    // Runtime errors (6xxx)
    RuntimeStateInvalid = 6001,
    RuntimeMemoryExhausted = 6002,
    RuntimeConcurrentLimit = 6003,
    RuntimeProcessFailed = 6010,

    // IO errors (7xxx)
    NetworkUnreachable = 7001,
    NetworkTimeout = 7002,
    FileNotFound = 7003,
    FilePermissionDenied = 7004,
    FileWriteFailed = 7005,

    // Unknown/fallback
    Unknown = 0,
}

impl ErrorCode {
    /// Get the category name for this error code.
    pub fn category(&self) -> &'static str {
        match (*self as u16) / 1000 {
            1 => "model",
            2 => "lens",
            3 => "tool",
            4 => "validation",
            5 => "config",
            6 => "runtime",
            7 => "io",
            _ => "unknown",
        }
    }

    /// Whether this error is typically recoverable.
    pub fn is_recoverable(&self) -> bool {
        !matches!(
            self,
            ErrorCode::ModelAuthFailed
                | ErrorCode::ModelToolsNotSupported
                | ErrorCode::ModelStreamingNotSupported
                | ErrorCode::LensNotFound
                | ErrorCode::LensParseError
                | ErrorCode::LensCircularDependency
                | ErrorCode::LensVersionConflict
                | ErrorCode::LensMergeConflict
                | ErrorCode::LensInvalidSchema
                | ErrorCode::ToolNotFound
                | ErrorCode::ToolInvalidArguments
                | ErrorCode::SkillNotFound
                | ErrorCode::SkillParseError
                | ErrorCode::SkillSandboxViolation
                | ErrorCode::ConfigMissing
                | ErrorCode::ConfigInvalid
                | ErrorCode::ConfigEnvMissing
                | ErrorCode::RuntimeStateInvalid
                | ErrorCode::RuntimeMemoryExhausted
                | ErrorCode::FileNotFound
                | ErrorCode::FilePermissionDenied
        )
    }

    /// Default recovery hints for this error code.
    pub fn default_hints(&self) -> Vec<&'static str> {
        match self {
            ErrorCode::ModelProviderUnavailable => vec![
                "For Ollama: run 'ollama serve'",
                "Check the provider URL is correct",
                "Switch to a different provider with --provider",
            ],
            ErrorCode::ModelAuthFailed => vec![
                "Set the API key environment variable",
                "Check if your API key is valid and not expired",
                "For local models, use --provider ollama (no API key needed)",
            ],
            ErrorCode::ModelToolsNotSupported => vec![
                "Switch to a model that supports tools (e.g., llama3:8b, gpt-4o-mini)",
                "Disable tools with --no-tools flag",
            ],
            ErrorCode::ModelRateLimited => vec![
                "Wait before retrying",
                "Switch to a different model or provider",
            ],
            ErrorCode::SkillExecutionFailed => vec![
                "Check if sunwell CLI is installed",
                "Try running 'sunwell --help' to verify",
                "Verify the project path exists",
            ],
            ErrorCode::ToolExecutionFailed => vec![
                "Check if the tool is installed",
                "Try running the command manually",
                "Check permissions for the target path",
            ],
            ErrorCode::RuntimeProcessFailed => vec![
                "Check if the command exists in PATH",
                "Verify permissions",
                "Try running the command manually",
            ],
            ErrorCode::FileNotFound => vec![
                "Check if the path is correct",
                "Verify the file exists",
            ],
            ErrorCode::FilePermissionDenied => vec![
                "Check file permissions",
                "Run with appropriate permissions",
            ],
            ErrorCode::ConfigEnvMissing => vec![
                "Set the environment variable",
                "Add it to your .env file",
                "For local-first usage, use --provider ollama (no keys needed)",
            ],
            _ => vec![],
        }
    }
}

/// Structured error matching the JSON schema (schemas/error.schema.json).
///
/// This struct serializes to JSON for the Svelte frontend to parse and display
/// with structured error messages and recovery hints.
#[derive(Debug, Clone, Serialize, Deserialize, Error)]
#[error("[{error_id}] {message}")]
pub struct SunwellError {
    pub error_id: String,
    pub code: u16,
    pub category: String,
    pub message: String,
    pub recoverable: bool,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub recovery_hints: Vec<String>,
    #[serde(default, skip_serializing_if = "serde_json::Value::is_null")]
    pub context: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cause: Option<String>,
}

impl SunwellError {
    /// Create a new SunwellError with default hints.
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        let hints = code.default_hints();
        Self {
            error_id: format!("SW-{:04}", code as u16),
            code: code as u16,
            category: code.category().to_string(),
            message: message.into(),
            recoverable: code.is_recoverable(),
            recovery_hints: hints.into_iter().map(String::from).collect(),
            context: serde_json::Value::Null,
            cause: None,
        }
    }

    /// Create an error with custom recovery hints (replacing defaults).
    pub fn with_hints(mut self, hints: Vec<&str>) -> Self {
        self.recovery_hints = hints.into_iter().map(String::from).collect();
        self
    }

    /// Add cause (original error message) for debugging.
    pub fn with_cause(mut self, cause: impl Into<String>) -> Self {
        self.cause = Some(cause.into());
        self
    }

    /// Create from a standard error, preserving the original message as cause.
    pub fn from_error<E: std::error::Error>(code: ErrorCode, error: E) -> Self {
        Self::new(code, error.to_string()).with_cause(format!("{:?}", error))
    }

    /// Parse from CLI JSON output (for errors from Python subprocess).
    #[allow(dead_code)] // Tested; used when parsing CLI output
    pub fn from_cli_json(json_str: &str) -> Option<Self> {
        serde_json::from_str(json_str).ok()
    }

    /// Create an unknown error (fallback for unstructured errors).
    #[allow(dead_code)] // Tested; fallback for parse_error_string
    pub fn unknown(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Unknown, message)
    }

    /// Convert to JSON string for Tauri return.
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).unwrap_or_else(|_| self.message.clone())
    }
}

// Convenience macro for creating errors
#[macro_export]
macro_rules! sunwell_err {
    ($code:ident, $msg:expr) => {
        $crate::error::SunwellError::new($crate::error::ErrorCode::$code, $msg)
    };
    ($code:ident, $fmt:expr, $($arg:tt)*) => {
        $crate::error::SunwellError::new(
            $crate::error::ErrorCode::$code,
            format!($fmt, $($arg)*)
        )
    };
}

// Convert std::io::Error to SunwellError
impl From<std::io::Error> for SunwellError {
    fn from(e: std::io::Error) -> Self {
        match e.kind() {
            std::io::ErrorKind::NotFound => SunwellError::from_error(ErrorCode::FileNotFound, e),
            std::io::ErrorKind::PermissionDenied => {
                SunwellError::from_error(ErrorCode::FilePermissionDenied, e)
            }
            std::io::ErrorKind::ConnectionRefused
            | std::io::ErrorKind::ConnectionReset
            | std::io::ErrorKind::ConnectionAborted => {
                SunwellError::from_error(ErrorCode::NetworkUnreachable, e)
            }
            std::io::ErrorKind::TimedOut => {
                SunwellError::from_error(ErrorCode::NetworkTimeout, e)
            }
            _ => SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e),
        }
    }
}

// Convert serde_json::Error to SunwellError
impl From<serde_json::Error> for SunwellError {
    fn from(e: serde_json::Error) -> Self {
        SunwellError::from_error(ErrorCode::ConfigInvalid, e)
    }
}

/// Parse an error from a string that may be JSON or raw text.
///
/// This is useful for parsing errors from Python CLI subprocess output,
/// which may be structured JSON or raw error text.
#[allow(dead_code)] // Tested; for future CLI parsing integration
pub fn parse_error_string(s: &str) -> SunwellError {
    // Try to parse as JSON first
    if let Some(err) = SunwellError::from_cli_json(s) {
        return err;
    }

    // Try to detect common patterns and categorize
    let lower = s.to_lowercase();

    if lower.contains("not found") || lower.contains("no such file") {
        return SunwellError::new(ErrorCode::FileNotFound, s);
    }
    if lower.contains("permission denied") {
        return SunwellError::new(ErrorCode::FilePermissionDenied, s);
    }
    if lower.contains("connection refused") || lower.contains("unavailable") {
        return SunwellError::new(ErrorCode::ModelProviderUnavailable, s);
    }
    if lower.contains("rate limit") {
        return SunwellError::new(ErrorCode::ModelRateLimited, s);
    }
    if lower.contains("auth") || lower.contains("api key") || lower.contains("401") {
        return SunwellError::new(ErrorCode::ModelAuthFailed, s);
    }
    if lower.contains("timeout") {
        return SunwellError::new(ErrorCode::NetworkTimeout, s);
    }

    // Fallback to unknown
    SunwellError::unknown(s)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_creation() {
        let err = SunwellError::new(ErrorCode::SkillExecutionFailed, "Test failed");
        assert_eq!(err.error_id, "SW-3103");
        assert_eq!(err.code, 3103);
        assert_eq!(err.category, "tool");
        assert!(err.recoverable);
        assert!(!err.recovery_hints.is_empty());
    }

    #[test]
    fn test_error_serialization() {
        let err = SunwellError::new(ErrorCode::FileNotFound, "Config not found");
        let json = serde_json::to_string(&err).unwrap();
        let parsed: SunwellError = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.error_id, "SW-7003");
        assert_eq!(parsed.category, "io");
        assert!(!parsed.recoverable);
    }

    #[test]
    fn test_error_macro() {
        let err = sunwell_err!(RuntimeProcessFailed, "Process {} failed", "test");
        assert_eq!(err.error_id, "SW-6010");
        assert!(err.message.contains("test"));
    }

    #[test]
    fn test_parse_error_string() {
        // JSON parsing
        let json = r#"{"error_id":"SW-1002","code":1002,"category":"model","message":"Auth failed","recoverable":false}"#;
        let err = parse_error_string(json);
        assert_eq!(err.error_id, "SW-1002");

        // Pattern detection
        let err = parse_error_string("No such file or directory");
        assert_eq!(err.code, ErrorCode::FileNotFound as u16);

        // Fallback
        let err = parse_error_string("Something went wrong");
        assert_eq!(err.code, ErrorCode::Unknown as u16);
    }

    #[test]
    fn test_from_io_error() {
        let io_err = std::io::Error::new(std::io::ErrorKind::NotFound, "file missing");
        let err: SunwellError = io_err.into();
        assert_eq!(err.code, ErrorCode::FileNotFound as u16);
    }
}
