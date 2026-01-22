//! Utility functions for Sunwell Studio.
//!
//! Provides helpers for spawning sunwell CLI commands with proper
//! fallback logic for different Python environments.

use std::process::Command;

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
