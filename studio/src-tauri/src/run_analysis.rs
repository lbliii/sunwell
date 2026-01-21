//! Run Analysis Types (RFC-066: Intelligent Run Button)
//!
//! Types for project run analysis, matching the JSON Schema in
//! `schemas/run-analysis.schema.json`.

use serde::{Deserialize, Serialize};

/// Confidence level of the analysis.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Confidence {
    High,
    Medium,
    Low,
}

/// How the analysis was determined.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Source {
    /// AI-powered analysis
    Ai,
    /// Heuristic-based detection (no AI)
    Heuristic,
    /// Loaded from cache
    Cache,
    /// User-saved command
    User,
}

/// An alternative run command.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunCommand {
    /// The command to execute
    pub command: String,
    /// Human-readable description
    pub description: String,
    /// When to use this alternative (e.g., "for production build")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub when: Option<String>,
}

/// A prerequisite that must be satisfied before running.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Prerequisite {
    /// Human-readable description
    pub description: String,
    /// Command to satisfy this prerequisite
    pub command: String,
    /// Whether this prerequisite is already satisfied
    pub satisfied: bool,
    /// Whether this prerequisite is required (vs recommended)
    pub required: bool,
}

/// Result of analyzing how to run a project.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunAnalysis {
    /// What kind of application this is (e.g., "React + Vite application")
    pub project_type: String,
    
    /// Framework/tooling used (e.g., "Vite 5.x")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub framework: Option<String>,
    
    /// Primary language (e.g., "TypeScript")
    pub language: String,
    
    /// Primary command to run in development mode
    pub command: String,
    
    /// Human-readable description of what the command does
    pub command_description: String,
    
    /// Working directory for the command (for monorepos)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub working_dir: Option<String>,
    
    /// Alternative commands that can be used
    #[serde(default)]
    pub alternatives: Vec<RunCommand>,
    
    /// Prerequisites that must be satisfied before running
    pub prerequisites: Vec<Prerequisite>,
    
    /// Expected port the dev server will run on
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expected_port: Option<u16>,
    
    /// Expected URL the app will be available at
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expected_url: Option<String>,
    
    /// Confidence level of the analysis
    pub confidence: Confidence,
    
    /// How the analysis was determined
    pub source: Source,
    
    /// Whether this result was loaded from cache
    #[serde(default)]
    pub from_cache: bool,
    
    /// Whether the user saved this command for this project
    #[serde(default)]
    pub user_saved: bool,
}

/// A running session for a project.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunSession {
    /// Unique session identifier
    pub id: String,
    /// Path to the project being run
    pub project_path: String,
    /// Command that was executed
    pub command: String,
    /// Process ID of the running command
    pub pid: u32,
    /// Port the server is running on (if applicable)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub port: Option<u16>,
    /// Unix timestamp when the session started
    pub started_at: u64,
}

// =============================================================================
// Command Safety Validation
// =============================================================================

/// Safe command prefixes (binaries that are allowed to execute).
const SAFE_COMMAND_PREFIXES: &[&str] = &[
    // Node.js ecosystem
    "npm", "npx", "yarn", "pnpm", "bun",
    // Python ecosystem
    "python", "python3", "pip", "uv", "poetry", "pdm",
    // Rust
    "cargo", "rustc",
    // Go
    "go",
    // Build tools
    "make", "cmake", "gradle", "mvn",
    // Containers
    "docker", "docker-compose", "podman",
    // Ruby
    "ruby", "bundle", "rails",
    // PHP
    "php", "composer",
    // .NET
    "dotnet",
    // Elixir
    "mix", "elixir",
    // Java
    "java", "javac",
];

/// Dangerous patterns that should never appear in commands.
const DANGEROUS_PATTERNS: &[&str] = &[
    "rm ", "rm\t", "rmdir",
    "sudo", "su ",
    "&&", "||", ";", "|",
    ">", "<", ">>", "<<",
    "`", "$(", "${",
    "eval", "exec", "source",
    "curl ", "wget ",
    "chmod", "chown",
    "kill", "pkill",
];

/// Validate a command against the safety allowlist.
/// 
/// Returns `Ok(())` if valid, `Err(reason)` if invalid.
pub fn validate_command_safety(command: &str) -> Result<(), String> {
    let command = command.trim();
    if command.is_empty() {
        return Err("Empty command".to_string());
    }
    
    let binary = command.split_whitespace().next().unwrap_or("");
    
    // Check if binary is in allowlist
    if !SAFE_COMMAND_PREFIXES.contains(&binary) {
        return Err(format!("Command '{}' not in allowlist", binary));
    }
    
    // Check for dangerous patterns
    let command_lower = command.to_lowercase();
    for pattern in DANGEROUS_PATTERNS {
        if command_lower.contains(pattern) {
            return Err(format!("Command contains dangerous pattern: {}", pattern.trim()));
        }
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_valid_npm_commands() {
        assert!(validate_command_safety("npm run dev").is_ok());
        assert!(validate_command_safety("npm start").is_ok());
    }
    
    #[test]
    fn test_valid_python_commands() {
        assert!(validate_command_safety("python main.py").is_ok());
        assert!(validate_command_safety("python3 -m flask run").is_ok());
    }
    
    #[test]
    fn test_valid_cargo_commands() {
        assert!(validate_command_safety("cargo run").is_ok());
        assert!(validate_command_safety("cargo build --release").is_ok());
    }
    
    #[test]
    fn test_empty_command_rejected() {
        assert!(validate_command_safety("").is_err());
        assert!(validate_command_safety("   ").is_err());
    }
    
    #[test]
    fn test_unknown_binary_rejected() {
        assert!(validate_command_safety("unknown_binary arg1").is_err());
        assert!(validate_command_safety("bash script.sh").is_err());
    }
    
    #[test]
    fn test_dangerous_patterns_rejected() {
        assert!(validate_command_safety("npm run dev && rm -rf /").is_err());
        assert!(validate_command_safety("sudo npm run dev").is_err());
        assert!(validate_command_safety("npm run dev; cat /etc/passwd").is_err());
    }
    
    #[test]
    fn test_serde_roundtrip() {
        let analysis = RunAnalysis {
            project_type: "React app".to_string(),
            framework: Some("Vite".to_string()),
            language: "TypeScript".to_string(),
            command: "npm run dev".to_string(),
            command_description: "Start dev server".to_string(),
            working_dir: None,
            alternatives: vec![],
            prerequisites: vec![],
            expected_port: Some(5173),
            expected_url: Some("http://localhost:5173".to_string()),
            confidence: Confidence::High,
            source: Source::Ai,
            from_cache: false,
            user_saved: false,
        };
        
        let json = serde_json::to_string(&analysis).unwrap();
        let parsed: RunAnalysis = serde_json::from_str(&json).unwrap();
        
        assert_eq!(parsed.project_type, "React app");
        assert_eq!(parsed.confidence, Confidence::High);
        assert_eq!(parsed.source, Source::Ai);
    }
}
