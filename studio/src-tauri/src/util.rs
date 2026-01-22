//! Utility functions for Sunwell Studio.
//!
//! Provides helpers for spawning sunwell CLI commands with proper
//! fallback logic for different Python environments.

use serde::de::DeserializeOwned;
use std::process::Command;

/// Sanitize a string by removing control characters that break JSON parsing.
///
/// Keeps printable characters plus newlines, carriage returns, and tabs.
/// LLM outputs sometimes contain control characters (e.g., `\u0000`) that
/// cause JSON parsers to fail.
///
/// Note: This is now only used internally by `parse_json_safe()` as a fallback.
fn sanitize_json_string(input: &str) -> String {
    input
        .chars()
        .filter(|c| !c.is_control() || *c == '\n' || *c == '\r' || *c == '\t')
        .collect()
}

/// Parse JSON with lazy sanitization of control characters.
///
/// Uses a try-then-sanitize approach per RFC-091:
/// - Fast path: Try direct parse (99%+ of cases after Python sanitization)
/// - Slow path: On control character error, sanitize and retry
///
/// Use this instead of `serde_json::from_str` when parsing output from
/// CLI commands or LLM responses, which may contain control characters.
pub fn parse_json_safe<T: DeserializeOwned>(json_str: &str) -> Result<T, serde_json::Error> {
    // Fast path: try direct parse
    match serde_json::from_str(json_str) {
        Ok(v) => Ok(v),
        Err(e) if e.to_string().contains("control character") => {
            // Slow path: sanitize and retry
            serde_json::from_str(&sanitize_json_string(json_str))
        }
        Err(e) => Err(e),
    }
}

/// Create a Command to run a sunwell CLI subcommand.
///
/// Tries multiple strategies to find the sunwell executable:
/// 1. Direct `sunwell` command (if globally installed)
/// 2. `python -m sunwell.cli` (module invocation)
/// 3. `python3 -m sunwell.cli` (explicit python3)
///
/// Returns a Command configured to run the sunwell CLI.
/// Caller should add arguments and execute.
///
/// # Example
/// ```
/// let output = sunwell_command()
///     .args(["project", "analyze", "--json"])
///     .current_dir(&project_path)
///     .output()?;
/// ```
pub fn sunwell_command() -> Command {
    // Strategy 1: Try direct sunwell command
    if which_sunwell().is_some() {
        return Command::new("sunwell");
    }

    // Strategy 2: Try python -m sunwell.cli
    if let Some(python) = find_python() {
        let mut cmd = Command::new(python);
        cmd.args(["-m", "sunwell.cli"]);
        return cmd;
    }

    // Fallback: Try sunwell anyway (will give a clear error)
    Command::new("sunwell")
}

/// Check if `sunwell` is available in PATH.
fn which_sunwell() -> Option<std::path::PathBuf> {
    which::which("sunwell").ok()
}

/// Find a working Python interpreter.
fn find_python() -> Option<&'static str> {
    for python in ["python3", "python"] {
        if which::which(python).is_ok() {
            // Verify it can import sunwell
            let check = Command::new(python)
                .args(["-c", "import sunwell"])
                .output();
            
            if let Ok(output) = check {
                if output.status.success() {
                    return Some(python);
                }
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sunwell_command_returns_command() {
        let cmd = sunwell_command();
        // Just verify it doesn't panic
        assert!(cmd.get_program().to_string_lossy().len() > 0);
    }
}
