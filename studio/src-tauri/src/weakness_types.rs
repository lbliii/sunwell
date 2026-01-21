//! RFC-063: Weakness Cascade Rust types.
//!
//! Serde-serializable structs matching Python types.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Weakness type enum matching Python
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum WeaknessType {
    LowCoverage,
    HighComplexity,
    LintErrors,
    StaleCode,
    FailureProne,
    MissingTypes,
    BrokenContract,
}

/// Cascade risk level
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum CascadeRisk {
    Low,
    Medium,
    High,
    Critical,
}

/// A weakness signal for a single artifact
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeaknessSignal {
    pub artifact_id: String,
    pub file_path: String,
    pub weakness_type: WeaknessType,
    pub severity: f32,
    #[serde(default)]
    pub evidence: HashMap<String, serde_json::Value>,
}

/// Aggregated weakness score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeaknessScore {
    pub artifact_id: String,
    pub file_path: String,
    pub signals: Vec<WeaknessSignal>,
    pub fan_out: u32,
    pub depth: u32,
    pub total_severity: f32,
    pub cascade_risk: CascadeRisk,
}

/// Extracted interface contract
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedContract {
    pub artifact_id: String,
    pub file_path: String,
    pub functions: Vec<String>,
    pub classes: Vec<String>,
    pub exports: Vec<String>,
    pub interface_hash: String,
}

/// Confidence score for a completed wave
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaveConfidence {
    pub wave_num: u32,
    pub artifacts_completed: Vec<String>,
    pub tests_passed: bool,
    pub types_clean: bool,
    pub lint_clean: bool,
    pub contracts_preserved: bool,
    pub confidence: f32,
    pub deductions: Vec<String>,
    pub should_continue: bool,
}

/// Preview of cascade regeneration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CascadePreview {
    pub weak_node: String,
    pub weakness_types: Vec<String>,
    pub severity: f32,
    pub cascade_risk: CascadeRisk,
    pub direct_dependents: Vec<String>,
    pub transitive_dependents: Vec<String>,
    pub total_impacted: u32,
    pub estimated_effort: String,
    pub files_touched: Vec<String>,
    pub waves: Vec<Vec<String>>,
    pub risk_assessment: String,
    pub has_contracts: bool,
    pub has_deltas: bool,
}

/// Full weakness report for a project
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeaknessReport {
    pub project_path: String,
    pub scan_time: String,
    pub weaknesses: Vec<WeaknessScore>,
    pub total_files_scanned: u32,
    pub critical_count: u32,
    pub high_count: u32,
    pub medium_count: u32,
    pub low_count: u32,
}

/// State of an in-progress cascade execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CascadeExecution {
    pub preview: CascadePreview,
    pub current_wave: u32,
    pub wave_confidences: Vec<WaveConfidence>,
    pub auto_approve: bool,
    pub confidence_threshold: f32,
    pub max_consecutive_low_confidence: u32,
    pub consecutive_low_confidence_count: u32,
    pub escalated_to_human: bool,
    pub paused_for_approval: bool,
    pub completed: bool,
    pub aborted: bool,
    pub abort_reason: Option<String>,
    pub overall_confidence: f32,
}
