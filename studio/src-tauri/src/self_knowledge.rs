//! Self-Knowledge Tauri Commands (RFC-085)
//!
//! Provides Studio access to Sunwell's self-knowledge capabilities:
//! - Source introspection
//! - Analysis patterns
//! - Proposal management

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
use crate::util::{parse_json_safe, sunwell_command};
use serde::{Deserialize, Serialize};

// =============================================================================
// Types (matching Python sunwell.self.types)
// =============================================================================

/// Symbol information from source introspection.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolInfo {
    pub name: String,
    pub kind: String, // "class", "function", "method", "variable"
    pub line: u32,
    pub signature: Option<String>,
    pub docstring: Option<String>,
}

/// Search result from semantic search.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub module: String,
    pub symbol: String,
    pub score: f64,
    pub snippet: String,
}

/// Pattern report from analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternReport {
    pub tool_frequencies: std::collections::HashMap<String, u32>,
    pub avg_latency_ms: f64,
    pub error_rate: f64,
    pub top_errors: Vec<String>,
}

/// Failure report from analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailureReport {
    pub total_failures: u32,
    pub by_category: std::collections::HashMap<String, u32>,
    pub recent: Vec<FailureEntry>,
}

/// Individual failure entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailureEntry {
    pub tool_name: String,
    pub error: String,
    pub timestamp: String,
}

/// Proposal summary for listing.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposalSummary {
    pub id: String,
    pub title: String,
    pub status: String,
    pub created_at: String,
    pub files_changed: u32,
}

/// Detailed proposal info.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposalDetail {
    pub id: String,
    pub title: String,
    pub description: String,
    pub status: String,
    pub changes: Vec<FileChange>,
    pub test_result: Option<TestResult>,
    pub created_at: String,
}

/// File change in a proposal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileChange {
    pub path: String,
    pub change_type: String, // "modify", "create", "delete"
    pub diff_preview: Option<String>,
}

/// Test result for a proposal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestResult {
    pub passed: bool,
    pub tests_run: u32,
    pub tests_passed: u32,
    pub tests_failed: u32,
    pub duration_ms: u32,
}

// =============================================================================
// Source Introspection Commands
// =============================================================================

/// Get source code for a Sunwell module.
#[tauri::command]
pub async fn self_get_module_source(module: String) -> Result<String, String> {
    let output = sunwell_command()
        .args(["self", "source", "read", &module, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(FileNotFound, "Module '{}' not found: {}", module, stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(stdout.to_string())
}

/// Find a symbol in Sunwell's source code.
#[tauri::command]
pub async fn self_find_symbol(module: String, symbol: String) -> Result<SymbolInfo, String> {
    let output = sunwell_command()
        .args(["self", "source", "find", &module, &symbol, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(ToolNotFound, "Symbol '{}' not found in {}: {}", symbol, module, stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse symbol info: {}", e).to_json())
}

/// List all Sunwell modules.
#[tauri::command]
pub async fn self_list_modules() -> Result<Vec<String>, String> {
    let output = sunwell_command()
        .args(["self", "source", "list", "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(RuntimeProcessFailed, "Failed to list modules: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse modules: {}", e).to_json())
}

/// Semantic search in Sunwell's source code.
#[tauri::command]
pub async fn self_search_source(query: String, limit: Option<u32>) -> Result<Vec<SearchResult>, String> {
    let limit_str = limit.unwrap_or(10).to_string();
    let output = sunwell_command()
        .args(["self", "source", "search", &query, "--limit", &limit_str, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Search failed: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse search results: {}", e).to_json())
}

// =============================================================================
// Analysis Commands
// =============================================================================

/// Get tool usage patterns from recent executions.
#[tauri::command]
pub async fn self_get_patterns(scope: Option<String>) -> Result<PatternReport, String> {
    let scope = scope.unwrap_or_else(|| "session".to_string());
    let output = sunwell_command()
        .args(["self", "analysis", "patterns", "--scope", &scope, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Pattern analysis failed: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse patterns: {}", e).to_json())
}

/// Get recent failures and their categories.
#[tauri::command]
pub async fn self_get_failures(limit: Option<u32>) -> Result<FailureReport, String> {
    let limit_str = limit.unwrap_or(20).to_string();
    let output = sunwell_command()
        .args(["self", "analysis", "failures", "--limit", &limit_str, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Failure analysis failed: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse failures: {}", e).to_json())
}

// =============================================================================
// Proposal Commands
// =============================================================================

/// List all self-improvement proposals.
#[tauri::command]
pub async fn self_list_proposals(status: Option<String>) -> Result<Vec<ProposalSummary>, String> {
    let mut args = vec!["self", "proposals", "list", "--json"];
    let status_owned: String;
    if let Some(s) = status {
        status_owned = s;
        args.extend(["--status", &status_owned]);
    }

    let output = sunwell_command()
        .args(&args)
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(RuntimeProcessFailed, "Failed to list proposals: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse proposals: {}", e).to_json())
}

/// Get detailed info about a specific proposal.
#[tauri::command]
pub async fn self_get_proposal(proposal_id: String) -> Result<ProposalDetail, String> {
    let output = sunwell_command()
        .args(["self", "proposals", "show", &proposal_id, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(ToolNotFound, "Proposal '{}' not found: {}", proposal_id, stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse proposal: {}", e).to_json())
}

/// Test a proposal in the sandbox.
#[tauri::command]
pub async fn self_test_proposal(proposal_id: String) -> Result<TestResult, String> {
    let output = sunwell_command()
        .args(["self", "proposals", "test", &proposal_id, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(ValidationScriptFailed, "Test failed: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse test result: {}", e).to_json())
}

/// Approve a proposal for application.
#[tauri::command]
pub async fn self_approve_proposal(proposal_id: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["self", "proposals", "approve", &proposal_id])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(ToolPermissionDenied, "Approval failed: {}", stderr).to_json());
    }

    Ok(())
}

/// Apply an approved proposal.
#[tauri::command]
pub async fn self_apply_proposal(proposal_id: String) -> Result<String, String> {
    let output = sunwell_command()
        .args(["self", "proposals", "apply", &proposal_id, "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Apply failed: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(stdout.to_string())
}

/// Rollback an applied proposal.
#[tauri::command]
pub async fn self_rollback_proposal(proposal_id: String) -> Result<(), String> {
    let output = sunwell_command()
        .args(["self", "proposals", "rollback", &proposal_id])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(SkillExecutionFailed, "Rollback failed: {}", stderr).to_json());
    }

    Ok(())
}

// =============================================================================
// Summary / Dashboard Commands
// =============================================================================

/// Get overall self-knowledge summary for dashboard display.
#[derive(Debug, Serialize, Deserialize)]
pub struct SelfKnowledgeSummary {
    pub modules_count: u32,
    pub recent_executions: u32,
    pub error_rate: f64,
    pub pending_proposals: u32,
    pub applied_proposals: u32,
    pub source_root: String,
}

#[tauri::command]
pub async fn self_get_summary() -> Result<SelfKnowledgeSummary, String> {
    let output = sunwell_command()
        .args(["self", "summary", "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(sunwell_err!(RuntimeProcessFailed, "Summary failed: {}", stderr).to_json());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_json_safe(&stdout)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse summary: {}", e).to_json())
}
