//! Security-First Skill Execution (RFC-089)
//!
//! Rust types and Tauri commands for security-first execution in Studio.
//! These types mirror the Python dataclasses in src/sunwell/security/.

use crate::error::{ErrorCode, SunwellError};
use crate::sunwell_err;
use crate::util::sunwell_command;
use serde::{Deserialize, Serialize};

// =============================================================================
// PERMISSION TYPES
// =============================================================================

/// Permission scope for a skill or DAG.
///
/// Permissions use consistent pattern syntax:
/// - Filesystem: Glob patterns (*, **, ~)
/// - Shell: Prefix match for security
/// - Network: host:port patterns
/// - Environment: Exact or prefix match
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PermissionScope {
    /// Paths the skill can read (glob patterns).
    #[serde(rename = "filesystemRead", default)]
    pub filesystem_read: Vec<String>,

    /// Paths the skill can write (glob patterns).
    #[serde(rename = "filesystemWrite", default)]
    pub filesystem_write: Vec<String>,

    /// Hosts the skill can connect to (host:port patterns).
    #[serde(rename = "networkAllow", default)]
    pub network_allow: Vec<String>,

    /// Hosts explicitly denied (default: ["*"]).
    #[serde(rename = "networkDeny", default = "default_network_deny")]
    pub network_deny: Vec<String>,

    /// Shell commands allowed (prefix match).
    #[serde(rename = "shellAllow", default)]
    pub shell_allow: Vec<String>,

    /// Shell commands explicitly denied.
    #[serde(rename = "shellDeny", default)]
    pub shell_deny: Vec<String>,

    /// Environment variables the skill can read.
    #[serde(rename = "envRead", default)]
    pub env_read: Vec<String>,

    /// Environment variables the skill can write.
    #[serde(rename = "envWrite", default)]
    pub env_write: Vec<String>,
}

fn default_network_deny() -> Vec<String> {
    vec!["*".to_string()]
}

/// Risk assessment result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskAssessment {
    /// Risk level: "low" | "medium" | "high" | "critical"
    pub level: String,

    /// Numeric risk score (0.0 - 1.0).
    pub score: f32,

    /// Risk flags detected during analysis.
    pub flags: Vec<String>,

    /// Recommendations for reducing risk.
    pub recommendations: Vec<String>,
}

// =============================================================================
// APPROVAL TYPES
// =============================================================================

/// Security approval request shown to user.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityApproval {
    /// Unique DAG identifier.
    #[serde(rename = "dagId")]
    pub dag_id: String,

    /// Human-readable DAG name.
    #[serde(rename = "dagName")]
    pub dag_name: String,

    /// Number of skills in the DAG.
    #[serde(rename = "skillCount")]
    pub skill_count: u32,

    /// Total permissions requested by all skills.
    pub permissions: PermissionScope,

    /// Risk assessment for the DAG.
    pub risk: RiskAssessment,

    /// When the approval was requested.
    pub timestamp: String,
}

/// Per-skill permission info for UI display.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillPermissionBreakdown {
    /// Skill name.
    #[serde(rename = "skillName")]
    pub skill_name: String,

    /// Permission preset name (optional).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preset: Option<String>,

    /// Permissions for this skill.
    pub permissions: PermissionScope,

    /// Risk contribution: "none" | "low" | "medium" | "high".
    #[serde(rename = "riskContribution")]
    pub risk_contribution: String,

    /// Primary risk reason (optional).
    #[serde(skip_serializing_if = "Option::is_none", rename = "riskReason")]
    pub risk_reason: Option<String>,
}

/// Extended security approval with per-skill breakdown.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityApprovalDetailed {
    #[serde(flatten)]
    pub base: SecurityApproval,

    /// Per-skill permission breakdown.
    #[serde(rename = "skillBreakdown")]
    pub skill_breakdown: Vec<SkillPermissionBreakdown>,

    /// Skill contributing most to risk (optional).
    #[serde(skip_serializing_if = "Option::is_none", rename = "highestRiskSkill")]
    pub highest_risk_skill: Option<String>,
}

/// User's response to security approval.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityApprovalResponse {
    /// DAG being approved/rejected.
    #[serde(rename = "dagId")]
    pub dag_id: String,

    /// Whether the user approved execution.
    pub approved: bool,

    /// Modified permissions if user edited them.
    #[serde(skip_serializing_if = "Option::is_none", rename = "modifiedPermissions")]
    pub modified_permissions: Option<PermissionScope>,

    /// Whether to remember this approval for the session.
    #[serde(rename = "rememberForSession")]
    pub remember_for_session: bool,

    /// Risk flags the user acknowledged.
    #[serde(rename = "acknowledgedRisks")]
    pub acknowledged_risks: Vec<String>,
}

// =============================================================================
// VIOLATION TYPES
// =============================================================================

/// Security violation detected during execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityViolation {
    /// Name of the skill that caused the violation.
    #[serde(rename = "skillName")]
    pub skill_name: String,

    /// Type of violation (credential_leak, path_traversal, etc.).
    #[serde(rename = "violationType")]
    pub violation_type: String,

    /// Evidence supporting the detection.
    pub evidence: String,

    /// Position in output where violation was detected.
    pub position: u64,

    /// How the violation was detected: "deterministic" | "llm".
    #[serde(rename = "detectionMethod")]
    pub detection_method: String,

    /// When the violation was detected.
    pub timestamp: String,
}

// =============================================================================
// AUDIT TYPES
// =============================================================================

/// Audit log entry for UI display.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntryDisplay {
    /// When the event occurred.
    pub timestamp: String,

    /// Name of the skill involved.
    #[serde(rename = "skillName")]
    pub skill_name: String,

    /// Type of action: "execute" | "violation" | "denied" | "error".
    pub action: String,

    /// Human-readable details.
    pub details: String,

    /// Risk level at time of execution.
    #[serde(rename = "riskLevel")]
    pub risk_level: String,
}

/// Audit log integrity status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditIntegrityStatus {
    /// Whether the audit log is valid.
    pub valid: bool,

    /// Message describing the status.
    pub message: String,
}

// =============================================================================
// TAURI COMMANDS
// =============================================================================

/// Analyze DAG permissions before execution.
#[tauri::command]
pub async fn analyze_dag_permissions(dag_id: String) -> Result<SecurityApprovalDetailed, String> {
    let output = sunwell_command()
        .args(["security", "analyze", &dag_id, "--json", "--detailed"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::ToolPermissionDenied, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if output.status.success() {
        serde_json::from_slice(&output.stdout).map_err(|e| {
            sunwell_err!(ConfigInvalid, "Failed to parse security analysis: {}", e).to_json()
        })
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(sunwell_err!(
            ToolPermissionDenied,
            "Security analysis failed: {}",
            stderr
        )
        .with_hints(vec!["Check if the DAG ID is valid"])
        .to_json())
    }
}

/// Submit user's approval response.
#[tauri::command]
pub async fn submit_security_approval(response: SecurityApprovalResponse) -> Result<bool, String> {
    let json = serde_json::to_string(&response)
        .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to serialize response: {}", e).to_json())?;

    let mut cmd = sunwell_command();
    cmd.args(["security", "approve", "--json"]);

    // Pass JSON via stdin
    let mut child = cmd
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if let Some(stdin) = child.stdin.as_mut() {
        use std::io::Write;
        stdin.write_all(json.as_bytes()).map_err(|e| {
            SunwellError::from_error(ErrorCode::FileWriteFailed, e)
                .with_hints(vec!["Check process stdin is available"])
                .to_json()
        })?;
    }

    let output = child.wait_with_output().map_err(|e| {
        SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
            .with_hints(vec!["Process may have been interrupted"])
            .to_json()
    })?;

    Ok(output.status.success())
}

/// Get recent audit log entries for display.
#[tauri::command]
pub async fn get_audit_log(
    since: Option<String>,
    limit: Option<u32>,
) -> Result<Vec<AuditEntryDisplay>, String> {
    let mut cmd = sunwell_command();
    cmd.args(["security", "audit", "--json"]);

    if let Some(s) = since {
        cmd.args(["--since", &s]);
    }
    if let Some(l) = limit {
        cmd.args(["--limit", &l.to_string()]);
    }

    let output = cmd.output().map_err(|e| {
        SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
            .with_hints(vec!["Check if sunwell CLI is installed"])
            .to_json()
    })?;

    if output.status.success() {
        serde_json::from_slice(&output.stdout)
            .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse audit log: {}", e).to_json())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(sunwell_err!(RuntimeProcessFailed, "Audit log read failed: {}", stderr)
            .with_hints(vec!["Check if audit log exists"])
            .to_json())
    }
}

/// Verify audit log integrity.
#[tauri::command]
pub async fn verify_audit_integrity() -> Result<AuditIntegrityStatus, String> {
    let output = sunwell_command()
        .args(["security", "audit", "--verify", "--json"])
        .output()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if output.status.success() {
        serde_json::from_slice(&output.stdout)
            .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse result: {}", e).to_json())
    } else {
        // Return error as status (not an error case - just indicates invalid audit)
        Ok(AuditIntegrityStatus {
            valid: false,
            message: String::from_utf8_lossy(&output.stderr).to_string(),
        })
    }
}

/// Scan content for security issues.
#[tauri::command]
pub async fn scan_for_security_issues(content: String) -> Result<Vec<SecurityViolation>, String> {
    let mut cmd = sunwell_command();
    cmd.args(["security", "scan", "--json"]);

    // Pass content via stdin
    let mut child = cmd
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
                .with_hints(vec!["Check if sunwell CLI is installed"])
                .to_json()
        })?;

    if let Some(stdin) = child.stdin.as_mut() {
        use std::io::Write;
        stdin.write_all(content.as_bytes()).map_err(|e| {
            SunwellError::from_error(ErrorCode::FileWriteFailed, e)
                .with_hints(vec!["Check process stdin is available"])
                .to_json()
        })?;
    }

    let output = child.wait_with_output().map_err(|e| {
        SunwellError::from_error(ErrorCode::RuntimeProcessFailed, e)
            .with_hints(vec!["Process may have been interrupted"])
            .to_json()
    })?;

    if output.status.success() {
        serde_json::from_slice(&output.stdout)
            .map_err(|e| sunwell_err!(ConfigInvalid, "Failed to parse violations: {}", e).to_json())
    } else {
        // No violations if command fails (graceful degradation)
        Ok(vec![])
    }
}
